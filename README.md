# Career Tracker

A private, phone-friendly tracker for a job search: job leads scored for fit,
applications and where each one stands, a master resume and project bank that
Claude tailors per job, and interviews. Streamlit front end, Neon Postgres
database, hosted free on Streamlit Community Cloud.

## What's in it

- **Home**: how the lead pipeline stands (postings reviewed, their average
  fit, and how many leads scored 8+ and 9+ still wait in the inbox), the
  inbox in one line with a Review button, and **Needs attention**: overdue
  next steps, interviews in the next 7 days, and open applications with no
  update for 14 days.
- **Job Leads**: jobs from your job-alert emails, each scored for fit, best
  first. The daily review rates every job 1–10 on six categories (role,
  industry, location, pay, level, extras) against what you're looking for;
  the score is the weighted average, to one decimal, and any deal-breaker
  caps it at 3. Pay is rated only when the job has a pay range: the one the
  alert listed, or an estimate the review found online (shown with a yellow
  warning and where it came from). When it found nothing, the lead says
  **Pay not listed** and the score rests on the other categories. Each lead
  shows its ratings, and **How scoring works** on the What I'm looking for
  section lists the categories, weights and pay rules (they live in
  `app/config.py`). Today's arrivals carry a **New** badge and the **New
  today** view (where the inbox opens) shows just them; weak matches
  (under 4) are hidden until you choose **All** or **Weak** (on a computer,
  tick them all at once to dismiss); a lead nobody touches for 7 days moves
  to **Stale**. All of
  them stay stored, so the same job (company and title) never comes back
  from any site. **Add** makes one a Saved application; **Dismiss…** asks
  why (wrong role, location, pay, company, already applied, other) and the
  daily review reads the last month of reasons as a hint. The **What I'm
  looking for** tab holds the roles, places, pay floor, must-haves,
  deal-breakers and **companies to skip** the scores are based on. Home
  shows how many new leads are waiting.
- **Applications**: add one, filter and search, then for each application log
  updates (status changes or plain notes), set the next step, add interviews
  (with prep notes, then "how it went" and a 1–5 rating), edit, and see its
  full history. **Add** on a lead saves it here, reads the
  posting from its link and has Claude search for the same posting on the
  employer's own careers site (about 15 cents), so the application opens with
  **Apply on the employer's site** and never needs LinkedIn's Easy Apply;
  when the job board won't hand the posting over (Indeed, Glassdoor), the
  description comes from the employer's site instead (the page's own job
  data, or Claude's word-for-word copy, flagged for you to check);
  **Applied today** logs the application in one tap. That search takes a
  minute or two and keeps going if you leave the page: a line on the
  application says where it stands (looking, found, not on the employer's
  site, didn't finish, or not looked for yet), and **Edit** takes the
  employer's link when you find it yourself.
- **Resume and Projects**: your master resume as data. Under **Build from
  files** you upload your resume as a Word file (it becomes the template every export is
  modelled on) plus anything with more detail: a project history, a projects
  spreadsheet, old resumes. One click asks Claude to turn them into the
  master: the resume's bullets word for word, extra bullets from the other
  files into a pool, skills tagged, and any disagreements between files
  listed for you to settle. The **Master** section is where you edit it
  (roles, bullets, which bullets print, education, skills, projects) and
  download it as a Word file in your own layout; a role or project prints
  only when at least one of its bullets is ticked **On master**.
  **Projects** is where your work and personal projects live in full
  (situation, task, action, result, skills, and the resume bullet you chose),
  imported in one free click from your projects spreadsheet. Each gets a free
  detail score out of 100 that lists what it's missing, weakest first. Claude
  reviews one at a time (about 10 cents): it rates how it reads, asks the few
  questions that would strengthen it, works your answers into the details
  (your words stay, and one click undoes it) and offers bullets built only
  from your facts, with a [bracketed] placeholder where a number would help.
  The bullet you pick can go straight into the master's pool, where Resume
  Builder chooses from it. Under
  **Resume Builder** you pick an open application, get its job posting from
  the posting link in one click (LinkedIn hands it over; Indeed and Glassdoor
  don't, so those you paste, also on the application's **Posting** section),
  and one click has Claude choose
  and reword the master's bullets for that posting, write the cover
  letter, mark which of the posting's keywords the resume shows, and list
  every change with its reason. Each click is a new version; you edit the
  bullets and the letter, and download both as Word files in your layout.
  A version stays one page: Claude gets the master's size column by column
  (the roles fill the left one, education, skills and projects the right),
  and a version whose experience would still run past the master's is
  trimmed, last bullet of the longest role first, with a line under
  **Changes** saying so (a **Trim to one page** button does the same to an
  older version). Every Claude call is a
  button you click, costs about 45 cents (30 to build the master), and is
  counted on the page.

Settings you might want to change (the 14-day follow-up, the 7-day interview
window, the status list, the Claude model) are in `app/config.py`.

**Look and feel.** The app opens in a light look; the **Dark mode** switch in
the sidebar (tap ≫ at the top left on a phone) flips it, and the choice is
saved in the database, so every device follows. Every row of choices (a
page's sections, the lead filters, Open/Closed/All) is the same
pill selector: a grey track with the chosen one in the blue gradient. Both
looks, and the fonts, badges, cards and that selector, are defined in
`app/theme.py`; `.streamlit/config.toml`
carries the light look so the first paint already matches.

**Phone or computer.** The app tells from your browser whether it's on a
phone (an iPad counts as a computer). A phone keeps to
the everyday tasks: triaging leads as cards, opening an application, applying,
logging updates, interviews, Projects and Resume Builder downloads; the wide
editing tables (the master's grids, a tailored version's grids, Build from
files) say to use the computer. A computer
uses the full width: Home puts what needs attention beside your best waiting
leads, the pipeline and this week's numbers; Job Leads is a sortable table
where you tick several leads and add (up to five at a time) or dismiss them
together, their cards below; Applications and Projects show the list beside the
open one, and a click on a row opens it.

**Claude's mark.** Every button that calls Claude carries a small Claude spark
(`ui.claude_button`), so you can see what costs a few cents before you tap it.

## First-time setup (once)

1. **Create the database.** Sign in at [neon.tech](https://neon.tech) with the
   account you use for the Fitness app, click **New project**, and name it
   `career-tracker`. Keep it separate from the Fitness database. On the project
   dashboard click **Connect** and copy the connection string; it starts
   `postgresql://`. That string is the database's password: never paste it
   into a file that goes to GitHub.
2. **Add it to GitHub for the weekly backup.** In this repository go to
   **Settings → Secrets and variables → Actions → New repository secret**.
   Name it `DATABASE_URL` and paste the connection string as the value.
   Then add a second secret named `BACKUP_PASSWORD`: a long password you make
   up and **keep somewhere safe** (a password manager). The backups are locked
   with it, and without it they can't be opened.
3. **Put it online.** At [share.streamlit.io](https://share.streamlit.io)
   click **Create app** and deploy from GitHub, as for the Fitness app:
   - **Repository:** `nolanreed18/career-tracker`, **Branch:** `main`
   - **Main file path:** `app/Home.py`
   - **Advanced settings → Python version:** `3.13`
   - **Advanced settings → Secrets:**

     ```toml
     DATABASE_URL = "postgresql://…the string from Neon…"
     APP_PASSWORD = "a password you choose"
     ANTHROPIC_API_KEY = "…a key from console.anthropic.com, for Resume and Projects…"
     ```

   The Claude key is optional: without it Resume and Projects still shows and
   edits the master, and only the "Build the master with Claude" button is
   off. Make the key in a workspace of its own with a monthly spend limit.

   Streamlit's free plan allows one private app, and the Fitness app uses it,
   so this repository and app are public. The **sign-in screen** is what
   keeps your data private: every page asks you to sign in first, and the
   app stays locked if no way in is set up. Use a long password that you
   don't use anywhere else. To sign in with Google instead of typing it, see
   **Sign in with Google** below. The first time the app opens it creates its tables in the
   new database; there's nothing to run.
4. **Test the backup.** On GitHub go to **Actions → Backup → Run workflow**. A
   green check means it worked; the CSVs are on that run's page under
   **Artifacts**.

## Sign in with Google (optional)

Instead of typing the password, sign in with your Google account; Streamlit
keeps you signed in for 30 days on each device. Only the emails in
`ALLOWED_EMAILS` get in; any other Google account is turned away. The
password keeps working as a second way in.

1. In the [Google Cloud console](https://console.cloud.google.com), make a
   project named `career-tracker`. Under **Google Auth Platform**: give it a
   name and your email (**Branding**), choose **External** and add your Gmail
   as a test user (**Audience**), then **Clients → Create client → Web
   application** with this authorized redirect URI:
   `https://career-t-sm3yxhk6uhay9v9ntftttu.streamlit.app/oauth2callback`.
   Copy the client ID and client secret.
2. In the app's Streamlit **Settings → Secrets**, add these. The plain lines
   must come **above** the `[auth]` line:

   ```toml
   DATABASE_URL = "…unchanged…"
   APP_PASSWORD = "…unchanged…"
   ALLOWED_EMAILS = "you@gmail.com"

   [auth]
   redirect_uri = "https://career-t-sm3yxhk6uhay9v9ntftttu.streamlit.app/oauth2callback"
   cookie_secret = "…a long random string you make up…"
   client_id = "…from Google…"
   client_secret = "…from Google…"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

## Running it on your computer

Python 3.13, to match `.python-version`. From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
streamlit run app/Home.py
```

It opens at `http://localhost:8501`. It needs a file named `.env` in this
folder with two lines, `DATABASE_URL=postgresql://…` (the string from Neon)
and `APP_PASSWORD=…` (the password the app asks for), plus
`ANTHROPIC_API_KEY=…` if you want the Claude buttons on Resume and Projects;
`.env` is never uploaded to GitHub. `Ctrl+C` stops it.

`python apply_schema.py` creates the tables by hand. The app does this itself,
and it's safe to run again: it never deletes anything.

## Daily job-alert review

Job sites email alerts to the job-search Gmail. Every morning a scheduled
Claude task follows [`DAILY_REVIEW.md`](DAILY_REVIEW.md): it reads the new
alert emails, looks up pay for the promising jobs whose alert gave none,
scores each job 1–10 against **Job Leads → What I'm looking for**, adds the new ones to
the Job Leads page, emails the digest, and files the alert emails under the
`job-alerts-reviewed` label.

The digest (`app/digest.py`, rendered by `leads.py digest`) is one email in
the app's colours: the day's counts, the top pick, a reminder of strong
leads from earlier days still waiting, every lead with its score, pay,
ratings and posting link, what Home says needs doing today, and buttons
into the app.

It runs in a Claude cloud session, which reaches the database through
Neon's HTTPS endpoint (`db.HttpCursor`) because it can't open a normal
Postgres connection. The cloud environment needs `*.neon.tech` in its
allowed domains and `DATABASE_URL` as an environment variable, and
`.claude/settings.json` allows exactly the `leads.py` commands it runs. For
the pay lookup it opens the posting and salary sites when the environment's
network access allows them (Allowed domains: linkedin.com, indeed.com,
glassdoor.com, levels.fyi, payscale.com, salary.com), and falls back to web
search otherwise.

## Backups

`.github/workflows/backup.yml` runs `backup.py` every Sunday morning (and
whenever you click **Run workflow**). It copies every table to CSV and locks
the CSVs in a password-protected file, `career-tracker-backup.7z`, using
`BACKUP_PASSWORD`. That's needed because the repo is public, and anyone signed
in to GitHub can download a public repo's run files. GitHub keeps each run's
file for 90 days under **Actions → Backup → the run → Artifacts**. To open
one, unzip the download, then open the `.7z` file with
[7-Zip](https://www.7-zip.org) (Windows) or
[The Unarchiver](https://theunarchiver.com) or Keka (Mac) and type the backup
password. If a run fails, or `BACKUP_PASSWORD` isn't set, GitHub emails you. Run
`python backup.py` yourself for a copy in `data/backups/` on your computer;
`data/` is never uploaded to GitHub.

## Tests

```bash
ruff check .
pytest
```

The page and database tests need a **throwaway** Postgres. They empty the
database they're given, so they look for `TEST_DATABASE_URL` and refuse any
Neon address. Without it they're skipped and only the pure-logic tests run.
GitHub Actions (`.github/workflows/tests.yml`) starts a throwaway Postgres
and runs everything on every pull request. Claude Code cloud sessions set one
up automatically (`.claude/hooks/session-start.sh`).

## How the files fit together

| File | What it is |
|---|---|
| `app/Home.py`, `app/pages/` | The pages. The number in each filename is its order in the menu. |
| `app/data.py` | Every database read and write. |
| `app/logic.py` | The calculations (needs attention, stats, import), with no database. |
| `app/config.py` | Settings. |
| `schema.sql`, `apply_schema.py` | The tables (created automatically when the app first connects), and a script to create them by hand. |
| `db.py` | Finds `DATABASE_URL` (in `.env`, or Streamlit secrets when online). |
| `backup.py` | Dumps every table to CSV. |
| `app/digest.py` | The daily digest email, built from the day's leads. |
| `app/ai.py` | Claude, for Resume and Projects and Applications: the key, a connection check, building the master from your files, tailoring, finding postings and reviewing projects. |
| `app/docx_io.py` | Reads Word files as text and writes the master resume back in your own layout. |
| `app/resume_schema.py` | The shape of the master resume as data, a tailored version and a project review. |
| `leads.py` | How the daily job-alert review reads your profile, adds leads and builds the digest. |
| `CLAUDE.md` | Rules for Claude when it works on this project. |
