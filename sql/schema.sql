-- Job Radar database schema (SQLite)
-- Built from data/events.jsonl by scripts/build_db.py. Never edit the .db by hand:
-- events.jsonl is the source of truth, the database can always be rebuilt.

DROP VIEW  IF EXISTS v_next_step;
DROP VIEW  IF EXISTS v_current_status;
DROP VIEW  IF EXISTS v_funnel;
DROP VIEW  IF EXISTS v_by_source;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS applications;

-- One row per job you applied to.
CREATE TABLE applications (
    application_id   INTEGER PRIMARY KEY,
    company          TEXT NOT NULL,
    company_key      TEXT NOT NULL,          -- lowercased, punctuation stripped, for matching
    role             TEXT,
    source           TEXT NOT NULL,          -- indeed | seek | linkedin | email | company_site | other
    job_type         TEXT NOT NULL,          -- casual | part_time | full_time | unknown
    applied_date     TEXT,                   -- ISO date; NULL if we only ever saw a reply
    needs_review     INTEGER NOT NULL DEFAULT 0
);

-- One row per job-related email. Every email maps to exactly one application.
CREATE TABLE events (
    event_id          INTEGER PRIMARY KEY,
    gmail_message_id  TEXT NOT NULL UNIQUE,   -- stops the same email being counted twice
    application_id    INTEGER NOT NULL REFERENCES applications(application_id),
    event_type        TEXT NOT NULL,          -- applied | viewed | assessment | interview | offer | rejected
    event_date        TEXT NOT NULL,
    confidence        REAL NOT NULL,          -- the AI's own 0-1 score
    subject           TEXT
);

CREATE INDEX idx_events_app ON events(application_id, event_date);

-- Current stage of every application.
-- Latest email wins. If the latest thing is still "applied" or "viewed" after 21 days, call it no_response.
CREATE VIEW v_current_status AS
WITH ranked AS (
    SELECT e.*,
           ROW_NUMBER() OVER (
               PARTITION BY e.application_id
               ORDER BY e.event_date DESC,
                        CASE e.event_type
                            WHEN 'offer' THEN 6 WHEN 'rejected' THEN 5 WHEN 'interview' THEN 4
                            WHEN 'assessment' THEN 3 WHEN 'viewed' THEN 2 ELSE 1 END DESC
           ) AS rn
    FROM events e
)
SELECT a.application_id, a.company, a.role, a.source, a.job_type, a.applied_date,
       r.event_date AS last_update,
       CASE
           WHEN r.event_type IN ('applied', 'viewed')
                AND julianday('now') - julianday(r.event_date) > 21 THEN 'no_response'
           ELSE r.event_type
       END AS status,
       CAST(julianday('now') - julianday(COALESCE(a.applied_date, r.event_date)) AS INTEGER) AS days_since_applied,
       a.needs_review
FROM applications a
JOIN ranked r ON r.application_id = a.application_id AND r.rn = 1;

-- How far applications get. An application counts at every stage it ever reached.
CREATE VIEW v_funnel AS
SELECT 'Applied'            AS stage, 1 AS stage_order, COUNT(*) AS n FROM applications
UNION ALL
SELECT 'Got any reply',     2, COUNT(DISTINCT application_id) FROM events
    WHERE event_type IN ('viewed', 'assessment', 'interview', 'offer', 'rejected')
UNION ALL
SELECT 'Interview or test', 3, COUNT(DISTINCT application_id) FROM events
    WHERE event_type IN ('assessment', 'interview', 'offer')
UNION ALL
SELECT 'Offer',             4, COUNT(DISTINCT application_id) FROM events
    WHERE event_type = 'offer';

-- Which job sites actually get you replies.
CREATE VIEW v_by_source AS
SELECT a.source,
       COUNT(*) AS applications,
       SUM(CASE WHEN s.status NOT IN ('applied', 'viewed', 'no_response') THEN 1 ELSE 0 END) AS got_real_reply,
       ROUND(100.0 * SUM(CASE WHEN s.status IN ('assessment', 'interview', 'offer') THEN 1 ELSE 0 END) / COUNT(*), 1)
           AS interview_rate_pct
FROM applications a
JOIN v_current_status s USING (application_id)
GROUP BY a.source
ORDER BY applications DESC;

-- What to do about each application, for the dashboard's table and reminders.
-- Following up after a week is a common rule of thumb; 21 days is where v_current_status gives up.
CREATE VIEW v_next_step AS
SELECT application_id,
       CASE
           WHEN status IN ('applied', 'viewed') AND days_since_applied >= 7 THEN 'Follow up now'
           WHEN status IN ('applied', 'viewed')
                THEN 'Follow up on ' || date(COALESCE(applied_date, last_update), '+7 days')
           WHEN status = 'no_response'                 THEN 'No reply after 21 days'
           WHEN status IN ('assessment', 'interview')  THEN 'Prepare'
           WHEN status = 'offer'                       THEN 'Decide on the offer'
           ELSE 'Closed'
       END AS next_step,
       (status IN ('applied', 'viewed') AND days_since_applied >= 7) AS follow_up
FROM v_current_status;
