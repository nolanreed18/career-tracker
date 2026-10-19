# Daily job-alert review

What the scheduled Claude task does each morning. It runs in a fresh cloud
session with the Gmail connector; `leads.py` is its only way into the
database, and the project's `.claude/settings.json` allows exactly its
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
- Use only the `leads.py` commands below for the database and the digest: no
  ad-hoc Python, no other scripts.
- If a step fails, stop, and still send the owner the digest (step 8) with
  `problem` set to what failed, instead of guessing.

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
   hybrid / onsite, if stated), the pay exactly as the email gives it (if it
   does), the job link, posted date, and the source site (LinkedIn, Indeed,
   Glassdoor, Built In, Dice, Wellfound, Welcome to the Jungle). The job link
   is the one the email itself puts on that job, **kept exactly as it is**,
   tracking parameters and all: never shorten it, rebuild it from an ID, or
   guess a "cleaner" form, because job sites' bot protection blocks made-up
   links (Glassdoor's real link looks like
   `glassdoor.com/partner/jobListing.htm?...&jobListingId=...`). Skip only
   links that aren't a job: unsubscribe, "see all jobs", edit alert. Within
   this run, the same company and title is one job, however many sites or
   cities list it: keep one copy (prefer the location closest to the
   profile, then the link from the company or LinkedIn), and count how
   many repeats you dropped.

4. **Read what's wanted, how to score, and what's known:**

   ```
   python3 leads.py profile
   python3 leads.py rubric
   python3 leads.py known
   ```

   `profile` is what the owner is looking for, plus `skip_companies` (drop
   every job from those employers before anything else; a name matches when
   it appears in the employer's name) and `dismissed_recently` (jobs the
   owner dismissed lately and why: `wrong role`, `location`, `pay`,
   `company`, `already applied` or `other`; treat each as a hint of what
   they don't want, so a job much like a dismissed one rates lower on that
   category). `rubric` gives `today` (the owner's date; the session's clock
   is UTC, which can be a day ahead), the scoring categories with their
   weights and what each one means, and the pay rules. `known` lists the
   jobs already stored as `company|title` (lower-case, punctuation
   dropped). Skip jobs already there, and count how many you skipped.

5. **Find the pay** for each new job whose email gave none, unless the job is
   plainly weak (its role or location would rate 3 or under against the
   profile: leave those unresearched).
   - First open the job link itself with the web fetch tool and read the
     posting: a range stated there is `"listed"` pay, exactly like one from
     the email (Colorado postings must state one). If the fetch fails, is
     blocked, or shows a sign-in wall, move on; don't retry or try other
     forms of the link.
   - Then, still without pay, use the web search tool, at most two searches
     per job: `"<title>" "<company>" salary`, then
     `<title> salary <city or state>`. Take, in this order: the posting's
     own range as a job board quotes it; a current range for that title at
     that company (Levels.fyi, Glassdoor, Indeed, Payscale); else a current
     range for that title, level and area. Open a result page only if its
     snippet isn't enough and the site can be fetched. Write it as `salary`
     (a range, e.g. `"$115k-$135k"`), set `pay_source` to `"estimated"`, and
     `pay_note` to where it came from, under 15 words (e.g. `"Glassdoor
     range, Senior Data Analyst, Denver"`).
   - Nothing solid: leave `salary` out. Never relabel a listed range, and
     never write an estimate as listed.

6. **Rate each new job on the rubric categories, 1–10**, against the
   profile only (never your own idea of a good job): 10 means the profile's
   ideal for that category, 5 means middling, 1 means the opposite of what it
   asks for. Rate `pay` only when the job has a salary (listed or your
   estimate), and leave it out of `fit` otherwise: the score then rests on
   the other categories. Then set `deal_breaker` to true if any of the
   profile's deal-breakers applies (the score is then capped, whatever the
   ratings say). Write a one-sentence `fit_reason` (under 25 words) naming
   the strongest category and the weakest, and say so when a requirement
   looks like a stretch. The score itself is worked out from the ratings by
   `leads.py add`: a weighted average, to one decimal.

7. **Save them.** Write a JSON list to the scratchpad, one object per job:
   `source`, `title`, `company` (required), and `location`, `work_mode`,
   `salary`, `pay_source`, `pay_note`, `job_url`, `posted_on` (YYYY-MM-DD),
   `fit` (an object with a 1–10 rating for each rubric category you rated,
   keyed as `rubric` lists them), `deal_breaker` (true/false) and
   `fit_reason`. Then:

   ```
   python3 leads.py add <that file>
   ```

   It prints how many were added, skipped as already seen, and dropped as
   companies to skip. If it refuses the file, fix the rows it names and run
   it again.

8. **Email the owner one digest.** Write `run.json` to the scratchpad:

   ```json
   {"app_url": "<the app link from the scheduled task's prompt>",
    "emails_read": 5, "sources": {"LinkedIn": 4, "Indeed": 1},
    "already_known": 2, "duplicates": 1, "problem": null}
   ```

   (`problem`: what failed, if a step did; otherwise null.) Then:

   ```
   python3 leads.py digest run.json
   ```

   It prints `subject`, `html` and `text`. Send one email with
   `send_message` from the connected Gmail to that same job-search address:
   `subject` as the subject, `html` as `htmlBody` and `text` as `body`, each
   pasted exactly as printed, without editing, shortening or reformatting.
   The digest is built from what `add` stored, so it needs step 7 done first;
   with nothing new it still sends a short note. It also reminds the owner
   of strong leads from earlier days still sitting in the inbox.

9. **File the alert emails.** Label every thread read in step 2
   `job-alerts-reviewed` (create the label if missing) and remove it from the
   inbox. Leave every other email alone.

10. **Finish** with a short summary: emails read, jobs found, new, strong,
    added, how many got a pay estimate, and anything that went wrong.
