# Decisions

Each rule or choice as it stands now, why, and how it got there (dates in
America/Chicago, pull request numbers in brackets). When a decision changes,
rewrite its "Now" and "Why" and add a line to its history. The working rules
for Claude sessions are in [`CLAUDE.md`](../CLAUDE.md); this file explains them.

## Public app and repository, behind a sign-in

**Now:** The repository and the app are public. Every page asks for a
sign-in first: Google (only emails in `ALLOWED_EMAILS`) or `APP_PASSWORD`.
With neither set up, the app stays locked.
**Why:** Streamlit's free plan allows one private app, and the Fitness app
uses it.
**History:**
- 2026-10-16: password gate on every page (#2).
- 2026-10-16: Sign in with Google added, the password kept as a second way in (#6).
- 2026-10-18: Google sign-in fixed on Community Cloud by adding httpx (#7).

## Backups are locked before GitHub keeps them

**Now:** Every Sunday the Backup workflow copies every table to CSV and
uploads only a 7z file locked with `BACKUP_PASSWORD`. Without that secret the
run fails before touching the database.
**Why:** Anyone signed in to GitHub can download a public repository's run
files.
**History:**
- 2026-10-16: weekly CSV backup (#1), then encrypted (#3).

## One database, Neon Postgres; the live database updates itself

**Now:** Neon Postgres, its own project, separate from the Fitness app's.
`schema.sql` is re-runnable and runs on each process's first connection;
changes to existing tables go in `data.MIGRATIONS`, which are safe to run
again.
**Why:** The same setup as the Fitness app; nobody has to run anything
against the live database by hand.
**History:**
- 2026-10-16: chosen at the start (#1).
- 2026-10-18: `data.MIGRATIONS` added for category scoring (#14).

## Code is split by job

**Now:** All SQL in `app/data.py`; calculations in `app/logic.py` (no
database, no screens); pages only lay out and call those. Settings and fixed
lists in `app/config.py`, with the lists repeated in `schema.sql`'s checks
(tests fail when they drift).
**Why:** Pure logic is easy to test; one place for each kind of thing.
**History:**
- 2026-10-16: set at the start (#1).

## "Today" is Chicago's day

**Now:** `data.today()` (America/Chicago) is passed into queries; never the
database's or server's clock.
**Why:** Cloud machines run on UTC; the first digest, run in the evening,
was dated the next day.
**History:**
- 2026-10-16: rule set (#1).
- 2026-10-18: the digest takes `today` from `leads.py rubric` (#15).

## The daily review is a Claude session, reaching the database over HTTPS

**Now:** A scheduled Claude Code cloud session follows `DAILY_REVIEW.md`
each morning. Its only way into the database is `leads.py` (commands
allowed one by one in `.claude/settings.json`), over Neon's HTTPS endpoint.
`DAILY_REVIEW.md` stays at the top of the repository, where the task reads it.
**Why:** A cloud session can't open a normal Postgres connection, and the
review should be able to do exactly what it needs and nothing else.
**History:**
- 2026-10-18: `leads.py` commands allowed for cloud sessions, the HTTPS endpoint and the runbook (#8); links kept exactly as emailed (#9).
- 2026-11-01: `leads.py watch` (#57) and `profile-save` (#58) added.

## How leads are scored

**Now:** Six categories rated 1–10 (role, industry, location, pay, level,
extras), weighted in `config.FIT_CATEGORIES`; a deal-breaker caps the score
at 3. Pay is rated only when there is a salary (listed, or an estimate the
review found); unknown pay stays out of the score. The review looks up pay
only for jobs rating 6+ on role and location. A 9/80 or 4/10 schedule
adds half a point, only when the alert or posting says so. "Strong" means 8+.
**Why:** Visible weights make a score explainable; guessing pay or schedule
would mislead.
**History:**
- 2026-10-16: one 1–10 score per lead (#5).
- 2026-10-18: scored by category with weights (#14).
- 2026-10-19: unknown pay left out (#18).
- 2026-10-21: strong raised to 8+, as Nolan wants only exceptional roles for now (#40).
- 2026-10-29: pay looked up only for promising jobs (#53).
- 2026-11-01: schedule bonus (#56).

## A lead is the same job by company and title

**Now:** The dedupe key is company|title, so the same job from another site
is stored once and never comes back. A lead untouched for 7 days is shown as
stale (a view, not a status).
**Why:** The location differed between sites for the same job.
**History:**
- 2026-10-16: company, title and location (#5).
- 2026-10-19: location dropped from the key; stale view added at 14 days (#20).
- 2026-10-29: stale after 7 days (#53).

## Companies to watch: their own careers sites, checked each morning

**Now:** Nolan lists companies on What I'm looking for; the review lists
their Workday, Greenhouse or Lever jobs placed in Colorado and adds the new
ones. Claude sessions change the profile with `leads.py profile-save` when
asked, never ad-hoc SQL.
**Why:** Rather than signing up for every employer's email alerts; the
careers sites often list jobs before the job boards. Nolan would rather
Claude make profile changes than be handed text to paste.
**History:**
- 2026-11-01: watch list (#57), profile-save (#58), Denver City, Texas excluded (#59).

## Apply on the employer's site, found free first

**Now:** Adding a lead looks for the same posting on the employer's careers
site. Free first (the link itself, or a known Workday, Greenhouse or Lever
site searched for the exact title); only then a Claude web search, on the
cheaper model. A job board never counts as the employer. Where the search
stands is saved on the application before the call.
**Why:** LinkedIn's guest pages no longer show the Apply link, and applying
on the employer's site avoids Easy Apply. Searches cost money; a near-miss
title is worse than none.
**History:**
- 2026-10-20: Add reads the posting and searches with Claude (#36, #37, #38).
- 2026-10-22: the search moved to the cheaper model (#42).
- 2026-10-24: search state saved on the application (#44); posting from the employer's data (#45).
- 2026-11-01: free careers-site search by title (#55); free lookup runs even without the key (#61).

## Claude only when clicked, with its cost logged

**Now:** Claude in the app is `app/ai.py` only. Every call is a button Nolan
clicks (marked with Claude's spark), logged to `ai_usage` with its cost,
including failed calls. Nothing calls Claude on its own.
**Why:** Each call costs cents; Nolan should see what costs before tapping.
**History:**
- 2026-10-19: introduced with the master resume (#22).
- 2026-10-20: a cut-off or malformed answer is a plain error with its cost (#27).
- 2026-10-29: Claude's spark on every Claude button (#48).

## Work-portfolio exports come in as they were written

**Now:** A work-portfolio export (JSON) becomes one project-bank entry per
project, at the master's newest employer. Dated milestones go into that
project's result, marked as part of the same work; only demonstrated skills
are kept (planned ones aren't); the summary says how far the project got
(delivered, in progress, prototype, planned), whether Nolan's own part still
needs confirming, and what the export says isn't claimed. A project whose
title is already in the bank is left alone.
**Why:** The export keeps careful limits (no double-counted results, no
claims beyond the evidence); Claude's review and the bullets it drafts should
see them. Nothing Nolan has edited or reviewed is overwritten.
**History:**
- 2026-11-06: added (#70).

## Resumes in Nolan's own layout, one page

**Now:** Word files are written by copying paragraphs from Nolan's own
resume (the template), never styled by the app. A tailored version is kept
to the master's printed size, column by column, trimmed last bullet of the
longest role first. Each tailoring click is a new version; nothing is
overwritten.
**Why:** The layout stays his; one version ran onto a second page.
**History:**
- 2026-10-19: master resume (#22), tailoring and cover letter (#24), indents and tab stops (#25).
- 2026-10-23: one-page fit by column (#43).

## Four pages

**Now:** Home, Job Leads, Applications, Resume and Projects. Interviews live
on their application.
**Why:** The search runs on daily leads; the other pages went unused.
**History:**
- 2026-10-16: seven pages incl. Companies & Contacts, Career Log, Stats, Import (#1).
- 2026-10-29: Companies & Contacts and Career Log dropped (#50); Interviews, Stats, Import dropped, and their tables removed from the live database (#53).

## One look, light by default

**Now:** `app/theme.py` holds a light and a dark palette and one
stylesheet; the Dark mode choice is saved in the database so every device
follows. Every row of choices is the same pill selector (never tabs, which
forget their place). Colour means something; no emoji. `THEME.md` carries
the look to other apps word for word, checked by a test.
**Why:** A calm, consistent screen; tabs jumped back after every click.
**History:**
- 2026-10-18: new look, light and dark (#11); sections as pills (#13).
- 2026-10-29: one pill selector everywhere (#51, #52); THEME.md (#54).
- 2026-11-01: emoji removed (#61); Dark mode switch fixed for Streamlit 1.66 (#64).

## Phone or computer, told from the browser

**Now:** A phone gets one column and the everyday tasks; a computer gets
the wide layout and side-by-side views. Tablets count as computers.
**Why:** The wide editing grids can't be used on a phone; a computer was
wasting its width.
**History:**
- 2026-10-29: two layouts (#48); the manual Layout switch removed (#53).

## The app reloads its own code after an update

**Now:** Every page's first statement is `fresh.check()`.
**Why:** Community Cloud keeps old copies of modules loaded after pulling
new code, which broke pages until a reboot.
**History:**
- 2026-10-19: added (#16).

## The digest email stays small and plain

**Now:** At most 20 cards and 15 rows per section, every style inline, no
web fonts, under 100 KB.
**Why:** Gmail clips big emails, the run re-types every byte, and Outlook on
a phone drops stylesheets.
**History:**
- 2026-10-19: digest redesigned (#18).
- 2026-10-20: size budget (#30), inline styles (#33).

## Work arrives through pull requests, with notes kept current

**Now:** Every change is on a branch with a pull request; `main` is live.
Lint and tests run on every pull request. Every pull request that changes
the app updates `docs/STATUS.md` and `docs/HISTORY.md`, checked by the docs
check (the `no-docs` label skips it for tooling-only changes).
**Why:** The repository is the memory; any fresh chat should know the app
as well as the last one did.
**History:**
- 2026-10-16: tests on every pull request (#1).
- 2026-11-02: workflow to delete merged branches (#65).
- 2026-11-04: the five notes and the docs check (#66).
