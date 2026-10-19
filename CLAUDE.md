# Career Tracker

Job search + career log. Streamlit (`app/`), Neon Postgres, Streamlit Community
Cloud from `main`. The owner is new to GitHub and coding: explain in plain
language, do the work yourself, and end with a short numbered list of anything
only they can do (accounts, secrets, clicking merge).

## Rules
- `.env` holds `DATABASE_URL`. **Never read, print or copy it**; use `db.py`.
- The repo and app are **public** (Streamlit's free plan allows one private
  app). `ui.setup()` puts every page behind a sign-in: Google (`st.login`, only
  emails in the `ALLOWED_EMAILS` secret) or `APP_PASSWORD`. Every page calls it
  first, and it stays locked when neither is set up. Never commit data or secrets.
  Backups are artifacts anyone signed in to GitHub can download: the workflow
  only ever uploads them inside a 7z file locked with `BACKUP_PASSWORD`.
  Never commit real data: `data/` and `*.csv` are gitignored.
- The daily job-alert review (`DAILY_REVIEW.md`) runs in a cloud session and
  reaches the database only through `leads.py`, over Neon's HTTPS endpoint
  (`db.HttpCursor`, switched on when `CLAUDE_CODE_REMOTE` is set). Keep its
  queries to what `HttpCursor` supports: one statement each, no transactions.
- **Never `current_date`, `now()` or the server timezone in SQL**: "today" is
  `data.today()` (America/Chicago), passed in. Dates are plain `date`s.
- **All SQL lives in `app/data.py`**; calculations in `app/logic.py` (pure: no
  database, no Streamlit). Pages only lay out and call those two.
- Knobs in `app/config.py`. **Status / kind lists are repeated in `schema.sql`
  CHECKs**: change both (tests fail if they drift). Add a table → add it to
  `backup.TABLES` and the `TABLES` list in `conftest.py`.
- `schema.sql` must stay re-runnable (`if not exists`): `data.py` runs it on the
  first connection of each process. Changing an existing
  table needs a migration script for the live database; tell the owner to run it.
- Pass plain Python values to psycopg, not numpy (`int(x)` on DataFrame ids).
  Put user text into `st.markdown` through `ui.md()`: `$` would become maths.
- Forms reset by bumping a counter in their key; set a widget's session state
  only before it is drawn (or via a flag read at the top of the page).

## Tests
- `ruff check .` and `pytest` before every push. DB and page tests need
  `TEST_DATABASE_URL` (a throwaway Postgres; the cloud hook sets it, CI starts
  one). Never point it at Neon: `conftest.py` refuses, and the tests wipe it.
- Page tests use `streamlit.testing.v1.AppTest` against that database with
  `data.today` patched; new pages get a draws-empty / draws-with-data case for free.
- Work on a branch and open a pull request; `main` is what's live.
