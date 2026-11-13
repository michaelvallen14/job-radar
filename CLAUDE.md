# Notes for Claude Code

## What this project is
Job Radar: a job application tracker that an AI agent fills in from Gmail. It's Michael's
portfolio project for junior data / AI / automation analyst roles, so recruiters will read the code.
Read README.md and PLAN.md first.

## Rules
- `data/events.jsonl` is the source of truth. The SQLite db is always rebuilt from it, never edited.
- Real data (`data/events.jsonl`, `data/job_radar.db`, `eval/labels.csv`) must NEVER be committed
  to this public repo. It's gitignored. Only `data/demo_*` files are public.
- Business logic goes in SQL views in `sql/schema.sql` where it reasonably can. SQL is a skill
  this project is meant to show.
- Keep it simple: plain Python, pandas, SQLite, Streamlit, Plotly. Ask before adding a new dependency.
- Charts: one blue for single-series charts (#2a78d6 on light, #3987e5 on the dark dashboard), thin marks, no dual axes, labels in grey ink.
- After any change to the schema or build script, run:
  `python scripts/make_demo_data.py && python scripts/build_db.py data/demo_events.jsonl data/demo.db`
  and check the dashboard still loads.
- Writing style for README and comments: short sentences, plain words, no em dashes.

## Michael's working style
He vibe codes and wants to understand what he ships. When you write something non-obvious
(a window function, a matching rule), add a one-line comment saying why, and tell him in chat
so he can explain it in an interview.
