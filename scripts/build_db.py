"""Rebuild the Job Radar SQLite database from an events file.

Usage:
    python scripts/build_db.py                       # data/events.jsonl -> data/job_radar.db
    python scripts/build_db.py data/demo_events.jsonl data/demo.db

Each line of the events file is one job email the daily agent extracted (see agent/daily_scan.md).
This script matches every email to an application:
  - an "applied" email starts a new application, unless it is the employer's own copy of a
    job site confirmation from the same day (see find_duplicate_apply)
  - any other email (viewed, rejected, interview...) attaches to the most recent application
    at the same company that was applied for before it
  - a reply with no matching application still gets a row, flagged needs_review
"""
import json
import re
import sqlite3
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "sql" / "schema.sql"

COMPANY_SUFFIXES = r"\b(pty|ltd|limited|inc|group|australia|au|co)\b"


def company_key(name: str) -> str:
    key = name.lower()
    key = re.sub(COMPANY_SUFFIXES, " ", key)
    key = re.sub(r"[^a-z0-9 ]", " ", key)
    return re.sub(r"\s+", " ", key).strip()


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a or "", b or "").ratio()


def load_events(path: Path) -> list[dict]:
    events, seen = [], set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        e = json.loads(line)
        if e["gmail_message_id"] in seen:  # the agent re-sent an email: keep the first copy
            continue
        if not e.get("is_job_email", True):
            continue
        seen.add(e["gmail_message_id"])
        events.append(e)
    # applied emails first on the same day, so a same-day rejection finds its application
    order = {"applied": 0}
    return sorted(events, key=lambda e: (e["received_at"], order.get(e["event_type"], 1)))


def find_application(apps: list[dict], e: dict) -> dict | None:
    key = company_key(e["company"])
    candidates = [a for a in apps if similar(a["company_key"], key) >= 0.85
                  and (a["applied_date"] or "") <= e["received_at"][:10]]
    if not candidates:
        return None
    # same company, several roles: pick the closest role title, then the most recent
    return max(candidates, key=lambda a: (similar(a["role"], e.get("role")), a["applied_date"] or ""))


def find_duplicate_apply(apps: list[dict], e: dict) -> dict | None:
    # Many employers send their own "we got your application" email on top of the job site's one.
    # Same company, similar role, a different source and within a day means it's the same application.
    # Same source twice is kept as two applications: that's a real second apply.
    key = company_key(e["company"])
    day = date.fromisoformat(e["received_at"][:10])
    for a in reversed(apps):
        if (a["applied_date"] and a["source"] != e.get("source", "other")
                and similar(a["company_key"], key) >= 0.85
                and similar(a["role"], e.get("role")) >= 0.6
                and abs((day - date.fromisoformat(a["applied_date"])).days) <= 1):
            return a
    return None


def build(events_path: Path, db_path: Path) -> None:
    events = load_events(events_path)
    apps: list[dict] = []
    rows: list[tuple] = []

    for e in events:
        date = e["received_at"][:10]
        if e["event_type"] == "applied":
            app = find_duplicate_apply(apps, e)
        else:
            app = find_application(apps, e)
        if app is None:
            app = {
                "application_id": len(apps) + 1,
                "company": e["company"],
                "company_key": company_key(e["company"]),
                "role": e.get("role"),
                "source": e.get("source", "other"),
                "job_type": e.get("job_type", "unknown"),
                "applied_date": date if e["event_type"] == "applied" else None,
                "needs_review": 0 if e["event_type"] == "applied" else 1,
            }
            apps.append(app)
        if e.get("confidence", 1) < 0.7:
            app["needs_review"] = 1
        rows.append((e["gmail_message_id"], app["application_id"], e["event_type"], date,
                     e.get("confidence", 1.0), e.get("subject")))

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA.read_text())
    con.executemany(
        "INSERT INTO applications VALUES (:application_id, :company, :company_key, :role, :source,"
        " :job_type, :applied_date, :needs_review)", apps)
    con.executemany(
        "INSERT INTO events (gmail_message_id, application_id, event_type, event_date, confidence, subject)"
        " VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()

    flagged = sum(a["needs_review"] for a in apps)
    print(f"{len(events)} emails -> {len(apps)} applications ({flagged} flagged for review) -> {db_path}")
    con.close()


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "events.jsonl"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "job_radar.db"
    build(src, dst)
