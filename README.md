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

Settings you might want to change (the 14-day follow-up, the 7-day interview
window, the status list) are in `app/config.py`.

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
   so this repository and app are public. The **password screen** is what
   keeps your data private: every page asks for `APP_PASSWORD` first, and the
   app stays locked if it isn't set. Use a long password that you don't use
   anywhere else. The first time the app opens it creates its tables in the
   new database; there's nothing to run.
4. **Test the backup.** On GitHub go to **Actions → Backup → Run workflow**. A
   green check means it worked; the CSVs are on that run's page under
   **Artifacts**.

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

## Backups

`.github/workflows/backup.yml` runs `backup.py` every Sunday morning (and
whenever you click **Run workflow**). It copies every table to CSV, and
GitHub keeps each run's files for 90 days under **Actions → Backup → the
run → Artifacts**. If a run fails, GitHub emails you. Run
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
| `CLAUDE.md` | Rules for Claude when it works on this project. |
