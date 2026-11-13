"""Make fake job emails for the public demo. No real inbox data ever goes in the public repo.

Usage: python scripts/make_demo_data.py   -> data/demo_events.jsonl
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
OUT = Path(__file__).resolve().parent.parent / "data" / "demo_events.jsonl"

COMPANIES = ["Northwind Retail", "Bluegum Analytics", "Harbour Bank", "Lumen Health", "Paperbark Cafe",
             "Southbank Logistics", "Copperleaf Insurance", "Tidal Energy", "Fernhill Grocers", "Atlas Telco",
             "Kestrel Consulting", "Wattle Education", "Ironbark Freight", "Seabreeze Hotels", "Quokka Software",
             "Riverbend Council", "Magpie Media", "Granite Super", "Saltwater Outfitters", "Brightline Rail"]
ROLES = {
    "full_time": ["Graduate Data Analyst", "Junior Data Analyst", "Data & Automation Analyst",
                  "Insights Analyst", "Junior AI Automation Analyst", "Reporting Analyst"],
    "casual": ["Casual Sales Assistant", "Christmas Casual Team Member", "Retail Assistant", "Barista"],
}
# How likely each outcome is, by job type. Full-time grad roles reply less and later.
OUTCOMES = {
    "full_time": [("no_reply", .55), ("rejected", .28), ("assessment", .07), ("interview", .08), ("offer", .02)],
    "casual":    [("no_reply", .50), ("rejected", .15), ("interview", .27), ("offer", .08)],
}
SOURCES = {"full_time": [("seek", .45), ("linkedin", .35), ("company_site", .15), ("email", .05)],
           "casual":    [("indeed", .7), ("seek", .25), ("email", .05)]}


def pick(pairs):
    return random.choices([p for p, _ in pairs], weights=[w for _, w in pairs])[0]


def main():
    start = datetime(2026, 9, 1, 9)
    events, msg = [], 0

    def emit(when, company, role, source, job_type, event_type, subject, conf=None):
        nonlocal msg
        msg += 1
        events.append({
            "gmail_message_id": f"demo{msg:05d}", "received_at": when.isoformat(timespec="seconds"),
            "is_job_email": True, "company": company, "role": role, "source": source,
            "job_type": job_type, "event_type": event_type, "subject": subject,
            "confidence": conf if conf is not None else round(random.uniform(.8, 1.0), 2),
        })

    for i in range(70):
        job_type = "casual" if random.random() < .45 else "full_time"
        company = random.choice(COMPANIES)
        role = random.choice(ROLES[job_type])
        source = pick(SOURCES[job_type])
        applied = start + timedelta(days=random.randint(0, 72), hours=random.randint(0, 12))
        emit(applied, company, role, source, job_type, "applied", f"Application received: {role} - {company}")

        if source in ("seek", "linkedin") and random.random() < .4:
            emit(applied + timedelta(days=random.randint(1, 6)), company, role, source, job_type, "viewed",
                 f"Your application was viewed by {company}")

        outcome = pick(OUTCOMES[job_type])
        if outcome == "no_reply":
            continue
        reply = applied + timedelta(days=random.randint(3, 10) if job_type == "casual" else random.randint(7, 30))
        if outcome in ("assessment", "interview", "offer"):
            first = "assessment" if outcome == "assessment" or (job_type == "full_time" and random.random() < .5) else "interview"
            emit(reply, company, role, source, job_type, first,
                 f"Next steps for your {role} application" if first == "interview" else f"{company}: online assessment")
            if outcome == "offer":
                emit(reply + timedelta(days=random.randint(5, 14)), company, role, source, job_type, "offer",
                     f"Offer of employment - {role}")
            elif random.random() < .6:
                emit(reply + timedelta(days=random.randint(5, 14)), company, role, source, job_type, "rejected",
                     f"Update on your application with {company}")
        else:
            emit(reply, company, role, source, job_type, "rejected", f"Your application to {company}",
                 conf=round(random.uniform(.55, 1.0), 2))

    # a few junk emails the agent is meant to drop, to show the filter working
    for j in range(5):
        msg += 1
        events.append({"gmail_message_id": f"demo{msg:05d}", "received_at": (start + timedelta(days=j * 9)).isoformat(),
                       "is_job_email": False, "company": "", "role": None, "source": "other", "job_type": "unknown",
                       "event_type": "applied", "subject": "Your cart price has been reduced!", "confidence": .99})

    today = datetime.now().isoformat()
    events = [e for e in events if e["received_at"] <= today]  # no replies from the future
    events.sort(key=lambda e: e["received_at"])
    OUT.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    print(f"wrote {len(events)} fake emails -> {OUT}")


if __name__ == "__main__":
    main()
