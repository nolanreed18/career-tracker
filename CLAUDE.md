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
  Its digest email is `app/digest.py` (pure, like `logic.py`), printed by
  `leads.py digest`; the run pastes it into Gmail, so keep it under 100 KB
  (Gmail clips) and email-safe (tables, the class stylesheet, no web fonts).
  A new `leads.py` command also goes in `.claude/settings.json`.
- **Never `current_date`, `now()` or the server timezone in SQL**: "today" is
  `data.today()` (America/Chicago), passed in. Dates are plain `date`s.
- **All SQL lives in `app/data.py`**; calculations in `app/logic.py` (pure: no
  database, no Streamlit). Pages only lay out and call those two.
- **The look lives in `app/theme.py`**: a light palette (the default) and a dark
  one as Streamlit theme options, applied per run by `ui.setup()` from the
  `settings` table ("theme"), plus one stylesheet. `.streamlit/config.toml`
  must equal the light palette (`tests/test_theme.py` checks). Pages use
  `ui.card()`, `ui.empty()` and the badge helpers rather than emoji or raw
  HTML; colour means something (blue = in progress, green = good, orange =
  attention, red = overdue/closed, grey = neutral, yellow = unverified: an
  estimate or missing pay, via `ui.pay_badge()`). Sub-pages are
  `ui.sections()` pills, never `st.tabs` (tabs forget their place on rerun);
  every delete goes through `ui.delete_button()` (tick box first); a "pick
  one" dropdown whose options can change takes `ui.round_key()` and
  `ui.bump_round()` after a delete, or it keeps showing the old choice.
- Knobs in `app/config.py`, including `FIT_CATEGORIES` (the lead-scoring
  categories and weights; `logic.fit_total` does the maths, the review rates)
  and the pay rules (`PAY_SOURCES`, `PAY_RESEARCH`): pay is rated only when a
  lead has a salary, listed or estimated; `logic.clean_lead` refuses a pay
  rating without one, and unknown pay stays out of the score.
  **Status / kind lists are repeated in `schema.sql` CHECKs** (statuses,
  kinds, lead statuses, `DISMISS_REASONS`): change both (tests fail if they
  drift). A lead's dedupe key is company|title (`logic.lead_key`); stale
  leads (`LEAD_STALE_DAYS`) are a view, not a status. Add a table → add it to `backup.TABLES` and the
  `TABLES` list in `conftest.py`.
- `schema.sql` must stay re-runnable (`if not exists`): `data.py` runs it on the
  first connection of each process. Changing an existing table → also add an
  idempotent statement to `data.MIGRATIONS` (run after schema.sql, and by
  `leads.py add` over HTTPS), so the live database updates itself.
- Add forms sit behind `ui.disclosure()` buttons (server-side open state), not
  `st.expander`, which snaps shut when a click lands mid-load.
- Every page's first statement is `fresh.check()`: Community Cloud pulls new
  code into the running app but keeps old copies of `app/` modules loaded, so
  pages importing something new broke until a reboot. Keep it first; a new
  page gets it too.
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
