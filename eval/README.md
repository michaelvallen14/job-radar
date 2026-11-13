# How accurate is the AI?

The AI sorts emails and decides each one's stage. This folder is where you check it.

1. Pick 50 real job emails (mix of applied, rejected, interview, and some junk).
2. For each, write the right answer yourself in `labels.csv`:
   `gmail_message_id,is_job_email,event_type,company`
3. Run `python eval/score.py data/events.jsonl eval/labels.csv`.

It prints accuracy for each field and lists every mistake. Put the headline numbers in the main
README. "The AI got 47 of 50 stages right, here are the 3 it missed and why" is the most
convincing thing in this whole project, because it shows you check AI work instead of trusting it.

Commit `labels.csv` to the PRIVATE data repo only. It has real company names from your inbox.
