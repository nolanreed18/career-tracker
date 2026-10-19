# Daily job-alert review

What the scheduled Claude task does each morning. It runs in a fresh cloud
session with the Gmail connector; `leads.py` is its only way into the
database, and the project's `.claude/settings.json` allows exactly its three
commands. Personal details (the profile, the jobs) live in the database and
the inbox, never in this public repository.

## Rules

- Read alert emails and add leads. Never apply to a job, reply to or email
  anyone but the owner, unsubscribe, delete an email, or change a job-site
  account.
- Never print, copy or write down `DATABASE_URL`, and don't look for it: run
  `leads.py` and let it connect.
- Nothing personal goes into the repository: write working files only to the
  session's scratchpad, and don't commit or push.
- If a step fails, stop, and send the owner the digest email (step 7) saying
  what failed, instead of guessing.

## Steps

1. **Check the inbox.** The connected Gmail must be the job-search inbox the
   scheduled task's prompt names (search `in:sent` for one message and read
   its sender). If it's another account, stop and say so in the run's final
   message.

2. **Find new alert emails** with `search_threads`, then `get_thread` for each
   (search previews are incomplete):

   ```
   newer_than:3d -label:job-alerts-reviewed (from:linkedin.com OR from:indeed.com
   OR from:glassdoor.com OR from:builtin.com OR from:dice.com OR from:wellfound.com
   OR from:welcometothejungle.com OR from:otta.com)
   ```

   Skip messages that aren't job lists (account notices, newsletters).

3. **Pull out every job**: title, company, location, work mode (remote /
   hybrid / onsite, if stated), salary text, the job link, posted date, and
   the source site (LinkedIn, Indeed, Glassdoor, Built In, Dice, Wellfound,
   Welcome to the Jungle). The job link is the one the email itself puts on
   that job, **kept exactly as it is**, tracking parameters and all: never
   shorten it, rebuild it from an ID, or guess a "cleaner" form, because job
   sites' bot protection blocks made-up links (Glassdoor's real link looks
   like `glassdoor.com/partner/jobListing.htm?...&jobListingId=...`). Skip
   only links that aren't a job: unsubscribe, "see all jobs", edit alert.
   Within this run, keep one copy of a job seen on several sites (prefer the
   link from the company or LinkedIn).

4. **Read what's wanted, how to score, and what's known:**

   ```
   python3 leads.py profile
   python3 leads.py rubric
   python3 leads.py known
   ```

   `profile` is what the owner is looking for. `rubric` lists the scoring
   categories with their weights and what each one means. `known` lists the
   jobs already stored as `company|title|location` (lower-case, punctuation
   dropped). Skip jobs already there.

5. **Rate each new job on every rubric category, 1–10**, against the
   profile only (never your own idea of a good job): 10 means the profile's
   ideal for that category, 5 means middling or unknown, 1 means the
   opposite of what it asks for. Then set `deal_breaker` to true if any of
   the profile's deal-breakers applies (the score is then capped, whatever
   the ratings say). Write a one-sentence `fit_reason` (under 25 words)
   naming the strongest category and the weakest, and say so when a
   requirement looks like a stretch. The score itself is worked out from
   the ratings by `leads.py add`: a weighted average, to one decimal.

6. **Save them.** Write a JSON list to the scratchpad, one object per job:
   `source`, `title`, `company` (required), and `location`, `work_mode`,
   `salary`, `job_url`, `posted_on` (YYYY-MM-DD), `fit` (an object with a
   1–10 rating for every rubric category, keyed as `rubric` lists them),
   `deal_breaker` (true/false) and `fit_reason`. Then:

   ```
   python3 leads.py add <that file>
   ```

   It prints how many were added and skipped. If it refuses the file, fix the
   rows it names and run it again.

7. **Email the owner one digest**, from the connected Gmail to that same
   job-search address:
   - Subject: `Job leads <Mon D>: N new, S strong`
   - Strong fits (7+) first, best first: score (one decimal), title —
     company, location, pay, the reason, and the link. Then a one-line
     count of the rest.
   - End with the app link the scheduled task's prompt gives (Job Leads
     page).
   - No new jobs: send a two-line "nothing new today" note instead.

8. **File the alert emails.** Label every thread read in step 2
   `job-alerts-reviewed` (create the label if missing) and remove it from the
   inbox. Leave every other email alone.

9. **Finish** with a short summary: emails read, jobs found, new, strong,
   added, and anything that went wrong.
