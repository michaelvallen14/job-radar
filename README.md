# Job Radar

**A job application tracker that fills itself in.** An AI agent reads my job emails every day,
works out which application each one belongs to and what stage it's at, and updates a dashboard.
I never type an application in by hand.

> The dashboard in this repo runs on **made-up demo data**. My real inbox data lives in a private repo.

## Why I built it

I was applying through Indeed, Seek, LinkedIn and plain email, and had no idea which ones
actually got replies. Every job site only shows its own applications, and spreadsheets die after a week.
Job Radar answers three questions from data I already have:

- How far do my applications get? (applied → reply → interview → offer)
- Which job sites are worth my time?
- How long do employers take to reply, and when should I give up on one?

## How it works

```
Gmail ──► AI agent (daily, read only) ──► events.jsonl ──► build_db.py ──► SQLite ──► Streamlit dashboard
            sorts job emails from junk       one line per      matches emails      SQL views:
            pulls company, role, stage       email, append      to applications     status, funnel,
                                             only                                   by source
```

1. **Agent** (`agent/daily_scan.md`): a scheduled AI task searches Gmail, drops junk
   (shopping, newsletters, job alerts), and writes one JSON line per job email:
   company, role, source, stage and a confidence score.
2. **Database** (`scripts/build_db.py`, `sql/schema.sql`): rebuilds SQLite from the events file.
   An "applied" email starts an application; later emails attach to it by matching the company and role.
3. **Rules in SQL** (`v_current_status`): the newest email sets the stage. No reply after
   21 days counts as "no response", because most employers never write back.
4. **Dashboard** (`app/dashboard.py`): funnel, interview rate by job site, applications per week,
   and a full list with a filter for anything the AI wasn't sure about.

## Checking the AI

The AI's output is a first draft, not the truth. Anything under 0.7 confidence gets flagged for me
to check, and `eval/` scores the AI against emails I labelled by hand.

**Accuracy on 50 hand-labelled emails:** _coming soon_

## Safety rules for the agent

- Gmail access is read only: it never sends, deletes, labels or marks anything as read.
- It never stores email bodies, only the extracted fields.
- It only ever appends to the events file and never rewrites history.
- If it finds an unusually large batch of job emails in one run, it writes nothing and reports
  the count instead, since that usually means the search went wrong.

## Run it yourself

```bash
pip install -r requirements.txt
python scripts/make_demo_data.py                               # fake emails
python scripts/build_db.py data/demo_events.jsonl data/demo.db  # build the database
streamlit run app/dashboard.py
```

## Built with

Python, SQLite, Streamlit, Plotly, and Claude (the email-reading agent, plus Claude Code as a
coding partner). I reviewed and tested all AI-written code.

## Next

- [ ] Accuracy score on 50 hand-labelled emails
- [ ] Market view: pull the job ad for each application and track which skills employers ask for
- [ ] Weekly email summary
