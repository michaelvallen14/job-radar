-- Job Radar database schema (SQLite)
-- Built from data/events.jsonl by scripts/build_db.py. Never edit the .db by hand:
-- events.jsonl is the source of truth, the database can always be rebuilt.

DROP VIEW  IF EXISTS v_next_step;
DROP VIEW  IF EXISTS v_current_status;
DROP VIEW  IF EXISTS v_job_group;
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

-- Office or Casual, from the job title. Most emails never say "full time", but the title does.
-- Rules run top to bottom and the first match wins: clear office words first (so "Retail Operations
-- Data Analyst" is Office), then shop-floor and hospitality words, then softer office words like
-- "receptionist", and the contract type only as a last resort. No match means it shows under All only.
CREATE VIEW v_job_group AS
WITH t AS (
    -- Pad with spaces so '% ai %' matches the word "AI" but not the "ai" inside "retail".
    SELECT application_id, job_type, ' ' || lower(COALESCE(role, '')) || ' ' AS r FROM applications
)
SELECT application_id,
       CASE
           WHEN r LIKE '%analyst%' OR r LIKE '%data%' OR r LIKE '% ai %' OR r LIKE '%automation%'
             OR r LIKE '%engineer%' OR r LIKE '%developer%' OR r LIKE '%statistic%' OR r LIKE '%insight%'
             OR r LIKE '%reporting%' OR r LIKE '%marketing%' OR r LIKE '%crm%'
             OR r LIKE '%call centre%' OR r LIKE '%appointment setter%' OR r LIKE '%cold caller%'
                THEN 'Office'
           WHEN r LIKE '%retail%' OR r LIKE '%sales%' OR r LIKE '%store%' OR r LIKE '%team member%'
             OR r LIKE '%kitchen%' OR r LIKE '%barista%' OR r LIKE '%cafe%' OR r LIKE '%wait%'
             OR r LIKE '%front of%' OR r LIKE '%all rounder%' OR r LIKE '%dishwasher%' OR r LIKE '%warehouse%'
             OR r LIKE '%packaging%' OR r LIKE '%guest%' OR r LIKE '%host%' OR r LIKE '%ticket%'
             OR r LIKE '%ambassador%' OR r LIKE '%food service%' OR r LIKE '%hospitality%'
             OR r LIKE '%christmas%' OR r LIKE '%seasonal%' OR r LIKE '%holiday%'
                THEN 'Casual'
           WHEN r LIKE '%admin%' OR r LIKE '%receptionist%' OR r LIKE '%coordinator%' OR r LIKE '%counsellor%'
             OR r LIKE '%officer%' OR r LIKE '%consultant%' OR r LIKE '%customer service%'
                THEN 'Office'
           WHEN job_type IN ('casual', 'part_time') THEN 'Casual'
           WHEN job_type = 'full_time' THEN 'Office'
       END AS job_group
FROM t;

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
SELECT a.application_id, a.company, a.role, a.source, a.job_type,
       g.job_group,   -- Office or Casual, for the dashboard's switch (see v_job_group)
       a.applied_date,
       r.event_date AS last_update,
       CASE
           WHEN r.event_type IN ('applied', 'viewed')
                AND julianday('now') - julianday(r.event_date) > 21 THEN 'no_response'
           ELSE r.event_type
       END AS status,
       CAST(julianday('now') - julianday(COALESCE(a.applied_date, r.event_date)) AS INTEGER) AS days_since_applied,
       a.needs_review
FROM applications a
JOIN ranked r ON r.application_id = a.application_id AND r.rn = 1
JOIN v_job_group g ON g.application_id = a.application_id;

-- How far applications get. An application counts at every stage it ever reached.
-- One row per stage per job_group, so the dashboard can filter with WHERE and add up n.
CREATE VIEW v_funnel AS
WITH reached AS (
    -- One row per application with a 0/1 flag for each stage it ever reached.
    SELECT s.application_id, s.job_group,
           MAX(e.event_type IN ('viewed', 'assessment', 'interview', 'offer', 'rejected')) AS got_reply,
           MAX(e.event_type IN ('assessment', 'interview', 'offer'))                       AS interview,
           MAX(e.event_type = 'offer')                                                     AS offer
    FROM v_current_status s
    JOIN events e USING (application_id)
    GROUP BY s.application_id, s.job_group
)
SELECT job_group, 'Applied'           AS stage, 1 AS stage_order, COUNT(*)       AS n FROM reached GROUP BY job_group
UNION ALL
SELECT job_group, 'Got any reply',     2,                         SUM(got_reply)      FROM reached GROUP BY job_group
UNION ALL
SELECT job_group, 'Interview or test', 3,                         SUM(interview)      FROM reached GROUP BY job_group
UNION ALL
SELECT job_group, 'Offer',             4,                         SUM(offer)          FROM reached GROUP BY job_group;

-- Which job sites actually get you replies. Counts only, per source and job_group:
-- rates can't be added up across groups, so the dashboard sums the counts first, then divides.
CREATE VIEW v_by_source AS
SELECT source, job_group,
       COUNT(*) AS applications,
       SUM(status NOT IN ('applied', 'viewed', 'no_response'))  AS got_real_reply,
       SUM(status IN ('assessment', 'interview', 'offer'))      AS reached_interview
FROM v_current_status
GROUP BY source, job_group;

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
