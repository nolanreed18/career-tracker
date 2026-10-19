# Career Tracker

A private, phone-friendly tracker for a job search and a career: applications
and where each one stands, companies and contacts, interviews, and a running
log of wins, skills and job history. Streamlit front end, Neon Postgres
database, hosted free on Streamlit Community Cloud.

## What's in it

- **Home**: open applications, applications sent this week, response rate, and
  **Needs attention**: overdue next steps, interviews in the next 7 days, and
  open applications with no update for 14 days.
- **Applications**: add one, filter and search, then for each application log
  updates (status changes or plain notes), set the next step, add interviews,
  edit, and see its full history.
- **Interviews**: upcoming and past, with prep notes, "how it went" and a 1–5
  rating.
- **Companies & Contacts**: companies (added for you with each application),
  plus recruiters, referrals and network contacts with "last contacted" dates.
- **Career Log**: wins, skills, certifications, feedback and things learned,
  with a CSV download. A **Job history** tab keeps past jobs and pay.
- **Stats**: pipeline by stage, applications per week, and response rate by
  source.
- **Import**: bring in applications from a spreadsheet saved as CSV. Headers
  are matched loosely, and importing the same file twice adds nothing.
- **Job Leads**: jobs from your job-alert emails, each scored for fit, best
  first. The daily review rates every job 1–10 on six categories (role,
  industry, location, pay, level, extras) against what you're looking for;
  the score is the weighted average, to one decimal, and any deal-breaker
  caps it at 3. Each lead shows its ratings, and **How scoring works** on the
  What I'm looking for section lists the categories and weights (they live
  in `app/config.py`). Weak matches (under 4) are hidden until you choose
  **All**; they stay stored so the same job never comes back.
  **Add** makes one a Saved application; **Dismiss** hides it. The
  **What I'm looking for** tab holds the roles, places, pay floor, must-haves
  and deal-breakers the scores are based on. Home shows how many new leads are
  waiting.

Settings you might want to change (the 14-day follow-up, the 7-day interview
window, the status list) are in `app/config.py`.

**Look and feel.** The app opens in a light look; the **Dark mode** switch in
the sidebar (tap ≫ at the top left on a phone) flips it, and the choice is
saved in the database, so every device follows. Both looks, and the fonts,
badges and cards, are defined in `app/theme.py`; `.streamlit/config.toml`
carries the light look so the first paint already matches.

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
     ```

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
and `APP_PASSWORD=…` (the password the app asks for);
`.env` is never uploaded to GitHub. `Ctrl+C` stops it.

`python apply_schema.py` creates the tables by hand. The app does this itself,
and it's safe to run again: it never deletes anything.

## Daily job-alert review

Job sites email alerts to the job-search Gmail. Every morning a scheduled
Claude task follows [`DAILY_REVIEW.md`](DAILY_REVIEW.md): it reads the new
alert emails, scores each job 1–10 against **Job Leads → What I'm looking
for**, adds the new ones to the Job Leads page, emails a short digest of the
best, and files the alert emails under the `job-alerts-reviewed` label.

It runs in a Claude cloud session, which reaches the database through
Neon's HTTPS endpoint (`db.HttpCursor`) because it can't open a normal
Postgres connection. The cloud environment needs `*.neon.tech` in its
allowed domains and `DATABASE_URL` as an environment variable, and
`.claude/settings.json` allows exactly the three `leads.py` commands it runs.

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
| `leads.py` | How the daily job-alert review reads your profile and adds leads. |
| `CLAUDE.md` | Rules for Claude when it works on this project. |
