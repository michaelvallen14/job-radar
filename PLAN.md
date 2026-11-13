# Build plan

Already done in this starter: schema + SQL views, build script, fake demo data, a first dashboard,
the agent prompt, and the accuracy-check script. Everything below is yours to do, roughly in order.

## Week 1: get it running on real emails

- [ ] **Run the demo locally.** Follow "Run it yourself" in the README. Click around the dashboard.
- [ ] **Make two GitHub repos.**
  - `job-radar` PUBLIC: this code + demo data.
  - `job-radar-data` PRIVATE: holds `data/events.jsonl` and `data/state.json` only.
- [ ] **Set up the daily agent.** Create a Claude scheduled task (once a day, e.g. 7:43pm) with the
  prompt in `agent/daily_scan.md`. Run it once by hand first and read every line it wrote.
- [ ] **Backfill.** First run uses `last_scan` = 2026-09-01, so it picks up everything since then.
  You already have 8+ Indeed applications from 12 Nov alone.
- [ ] **Point the dashboard at real data.** Copy `events.jsonl` from the private repo into
  `data/`, run `python scripts/build_db.py`, then `streamlit run app/dashboard.py`.
  (Later: a small script that pulls the private repo first.)

## Week 2: make it trustworthy

- [ ] **Hand-label 50 emails** in `eval/labels.csv` and run `eval/score.py`. Fix the agent prompt
  for whatever it gets wrong (job alerts counted as applications is the likely one). Re-score.
- [ ] **Check the matching.** Open the "AI wasn't sure" filter. Look for rejections attached to the
  wrong application. If the same company keeps breaking, improve `find_application()`.
- [ ] **Write the README accuracy line** with the real number.

## Week 3: make it portfolio-ready

- [ ] **Deploy the demo** on Streamlit Community Cloud (free, connects to the public repo).
  Put the live link at the top of the README.
- [ ] **Screenshot + 2-line description** for your portfolio site and LinkedIn.
- [ ] **Add it to your resume** as the first project. Draft bullets once you have the accuracy number:
  - Built an AI agent that reads my job emails daily and tracks every application automatically,
    with read-only access, no stored email bodies and a stop rule for bad runs
  - Modelled applications and status changes in SQLite with SQL views for stage, funnel and
    reply rate by job site; dashboard in Streamlit
  - Measured the AI against 50 hand-labelled emails: XX% stage accuracy

## Later (only once the above is done)
- Market view: skills employers ask for, from the ads you applied to.
- Weekly summary email: "6 applied, 1 interview, Seek replies 2x faster than Indeed".

## Things that can go wrong
- **Job alert emails** ("10 new jobs for you") look like applications. The prompt tells the agent
  to drop them; check that it does.
- **Same company, two roles.** Matching picks the closest role title. Check these by hand.
- **Employers that never email.** That's what the 21-day "no response" rule is for.
- **Indeed and Seek don't always send "viewed" or "rejected" emails**, so some statuses will be
  stuck at "applied" until day 21. That's a limit of the data, and worth saying in the README.
