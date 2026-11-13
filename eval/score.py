"""Score the AI's email reading against your own hand labels.

Usage: python eval/score.py data/events.jsonl eval/labels.csv
labels.csv columns: gmail_message_id,is_job_email,event_type,company
"""
import csv
import json
import sys


def norm(v):
    return str(v).strip().lower()


def main(events_path, labels_path):
    ai = {}
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                e = json.loads(line)
                ai[e["gmail_message_id"]] = e
    with open(labels_path, encoding="utf-8") as f:
        labels = list(csv.DictReader(f))

    fields = ["is_job_email", "event_type", "company"]
    right = {k: 0 for k in fields}
    counted = {k: 0 for k in fields}
    mistakes = []
    for lab in labels:
        e = ai.get(lab["gmail_message_id"])
        if e is None:
            mistakes.append((lab["gmail_message_id"], "missing", "AI never saw this email", ""))
            continue
        for k in fields:
            if k != "is_job_email" and norm(lab["is_job_email"]) != "true":
                continue  # stage and company only matter for real job emails
            counted[k] += 1
            if norm(e.get(k)) == norm(lab[k]):
                right[k] += 1
            else:
                mistakes.append((lab["gmail_message_id"], k, e.get(k), lab[k]))

    print(f"{len(labels)} hand-labelled emails")
    for k in fields:
        if counted[k]:
            print(f"  {k:<13} {right[k]}/{counted[k]} right ({right[k] / counted[k]:.0%})")
    if mistakes:
        print("\nMistakes (email id, field, AI said, you said):")
        for m in mistakes:
            print("  ", *m)


if __name__ == "__main__":
    main(*sys.argv[1:3])
