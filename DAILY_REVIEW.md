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

4. **Read what's wanted and what's known:**

   ```
   python3 leads.py profile
   python3 leads.py known
   ```

   `known` lists the jobs already stored as `company|title|location`
   (lower-case, punctuation dropped). Skip jobs already there.

5. **Score each new job 1–10** against the profile, with a one-sentence
   reason (under 25 words) naming the best match and the biggest gap:
   - **9–10**: the target role, hands-on building, preferred industry (oil &
     gas, chemicals, refining, midstream, energy), Denver area or remote, pay
     at or above the floor. The profile's "ideal example" is a 10.
   - **7–8**: strong role match with one gap (other industry, Colorado
     Springs, pay unknown).
   - **4–6**: related role or several gaps.
   - **1–3**: wrong role, entry level, outside Colorado and not remote, or
     any deal-breaker (contract / contract-to-hire, heavy travel, pure Excel
     reporting, pay well under the floor).
   Say so in the reason when a requirement looks like a stretch (e.g. "asks
   for 5+ years oil & gas operations").

6. **Save them.** Write a JSON list to the scratchpad, one object per job:
   `source`, `title`, `company` (required), and `location`, `work_mode`,
   `salary`, `job_url`, `posted_on` (YYYY-MM-DD), `fit_score`, `fit_reason`.
   Then:

   ```
   python3 leads.py add <that file>
   ```

   It prints how many were added and skipped. If it refuses the file, fix the
   rows it names and run it again.

7. **Email the owner one digest**, from the connected Gmail to that same
   job-search address:
   - Subject: `Job leads <Mon D>: N new, S strong`
   - Strong fits (7+) first, best first: score, title — company, location,
     pay, the reason, and the link. Then a one-line count of the rest.
   - End with the app link the scheduled task's prompt gives (Job Leads
     page).
   - No new jobs: send a two-line "nothing new today" note instead.

8. **File the alert emails.** Label every thread read in step 2
   `job-alerts-reviewed` (create the label if missing) and remove it from the
   inbox. Leave every other email alone.

9. **Finish** with a short summary: emails read, jobs found, new, strong,
   added, and anything that went wrong.
