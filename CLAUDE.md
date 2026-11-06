# Career Tracker

Job search tracker. Streamlit (`app/`), Neon Postgres, Streamlit Community
Cloud from `main`. The owner is new to GitHub and coding: explain in plain
language, do the work yourself, and end with a short numbered list of anything
only they can do (accounts, secrets, clicking merge).

## The notes
This repository is the memory; chats are replaceable. Read these first:
- `docs/OVERVIEW.md`: what the app is, how it's built, where things live.
- `docs/STATUS.md`: where things stand now (replaced on each update).
- `docs/DECISIONS.md`: each rule or choice as it stands, why, and its history.
- `docs/HISTORY.md`: a dated log of changes, newest first.
- The studio's way of working: `Standards/Working with me.md` in
  github.com/nolanreed18/mothership. Secrets are named, never written down;
  where each is kept is the mothership's `Studio/Secrets.md`.

## Rules
- Every pull request that changes the app updates `docs/STATUS.md` and
  `docs/HISTORY.md` (the Docs check fails otherwise; label a tooling-only
  pull request `no-docs`). A new rule or choice goes in `docs/DECISIONS.md`.
- `.env` holds `DATABASE_URL`. **Never read, print or copy it**; use `db.py`.
  Every secret is read through `db.secret(name)` (the environment, else the
  running app's `st.secrets`): no other lookup.
- The repo and app are **public** (Streamlit's free plan allows one private
  app). `ui.setup()` puts every page behind a sign-in: Google (`st.login`, only
  emails in the `ALLOWED_EMAILS` secret) or `APP_PASSWORD`. Every page calls it
  right after `fresh.check()`, and it stays locked when neither is set up. Never commit data or secrets.
  Backups are artifacts anyone signed in to GitHub can download: the workflow
  only ever uploads them inside a 7z file locked with `BACKUP_PASSWORD`.
  Never commit real data: `data/` and `*.csv` are gitignored.
- The daily job-alert review (`DAILY_REVIEW.md`) runs in a cloud session and
  reaches the database only through `leads.py`, over Neon's HTTPS endpoint
  (`db.HttpCursor`, switched on when `CLAUDE_CODE_REMOTE` is `"true"`). Keep its
  queries to what `HttpCursor` supports: one statement each, no transactions.
  Its digest email is `app/digest.py` (pure, like `logic.py`), printed by
  `leads.py digest`; the run pastes it into Gmail, so keep it under 100 KB
  (Gmail clips, and the run re-types every byte: `config.DIGEST_CARDS` /
  `DIGEST_ROWS` cap it, test_digest checks a 100-lead day) and email-safe
  (tables, every style inline, no web fonts: Outlook on a phone drops a stylesheet).
  A new `leads.py` command also goes in `.claude/settings.json`. When the
  owner asks a Claude session to change What I'm looking for (companies to
  watch or skip, the salary floor…), it does so itself with `leads.py
  profile-save` (only the fields given change), never ad-hoc SQL, rather
  than handing the owner text to paste.
- Claude inside the app is `app/ai.py` only: the key is `ANTHROPIC_API_KEY`
  in secrets (or `.env`), never printed; every call sits behind a button the
  owner clicks and is logged to `ai_usage` with its cost (`config.AI_MODEL`;
  the employer-site search runs on the cheaper `AI_FIND_MODEL`; `AI_PRICES`); nothing calls Claude on its own. Structured output goes
  through `resume_schema` (pydantic, every field required): `Resume` for
  the master, `Tailored` for one application's version (`tailored_resumes`,
  one row per click, never overwritten by a new click; the page keeps it to
  one page with `logic.fit_column`, the master's printed roles measured in
  lines by `logic.column_lines` at `docx_io.line_chars(template)` a line:
  the template's left column holds the roles, so that is the yardstick,
  and the prompt's `<limits>` give the master's size column by column). Word files are
  `app/docx_io.py`: the writer clones paragraphs from the owner's own resume
  (the template), never styles anything itself; `build` prints a resume,
  `letter` a cover letter. Tests stand the API in (`tests/test_ai.py`); no
  test calls Claude. `app/posting.py` reads a job posting from its link for the
  posting box (LinkedIn's guest copy; Indeed and Glassdoor refuse a server, so
  the error says to paste); tests never fetch. `ai.find_posting` (web search,
  searches priced by `AI_SEARCH_PRICE`) runs inside the Add tap on a lead and
  behind "Find it on the employer's site" (`ui.prepare_application`,
  `ui.find_company_posting`): still one click, one call, logged like the rest.
  Before the call, free and with no key needed (`ui.known_company_posting`):
  a job link that is itself a Workday, Greenhouse or Lever posting
  (`posting.employer_link`, a watched company's lead) is the answer; else
  `posting.on_careers_site` searches such a site already known for the
  employer (this application's links or another's,
  `data.company_apply_links`) for the title, and `logic.pick_posting` takes
  only a title match (after `logic.title_key`: Sr./Senior, II/2), never a
  guess; after the call, a careers-site address Claude returns is searched
  the same way. LinkedIn's guest pages don't show the employer's Apply link.
  Companies to watch (profile `watch_companies`, `logic.watch_list`):
  `leads.py watch` lists their careers sites' jobs (`posting.site_jobs`,
  sharing `_listed` with `on_careers_site`; a Workday site is searched for
  each `config.WATCH_SEARCH` word, and a job is kept only when
  `logic.watch_place` matches `config.WATCH_PLACE`), drops the known and
  skipped, and reads the first `WATCH_MAX_JOBS` postings' stated pay
  (`logic.listed_pay`) and schedule for the review to score (the rest are
  listed unread, and `problems` says so).
  `applications.apply_url` / `apply_note` / `apply_state` (`config.APPLY_STATES`,
  null = not looked for) hold what it found and where the search stands:
  `ui.apply_status` says so on the application, and the state is written
  before the call, so leaving the page mid-search loses nothing. An empty
  posting is filled from the employer's site: `posting.employer_posting`
  (an ATS feed, else the page's JSON-LD JobPosting; never loose page text),
  else Claude's word-for-word `description` (asked for only when the
  posting is missing). "Get the posting from the link" is
  `posting.from_links`: employer data, then the job link, then the employer page.
  The project bank (`career_projects`, Resume and Projects → Projects) holds each work
  and personal project in STAR detail; `logic.project_detail` scores it free
  (`config.DETAIL_CHECKS`), `ai.review_project` (`ProjectReview`) rates it,
  asks questions and drafts bullets from the person's facts only, and with
  answers rewrites the four STAR fields (the old text kept in the review's
  `before` for undo). `logic.add_to_master` puts a chosen bullet in the
  master's pool (source "project", unticked). A work-portfolio export (JSON, format
  `argus-work-portfolio`) comes in through `logic.portfolio_projects`: one entry per
  project at the master's newest employer, milestones folded into its result as the
  same work, only demonstrated skills, the summary saying how far it got and what
  isn't claimed; an upload stores it as projects text, `leads.py projects-import`
  adds it straight to the bank. A title already in the bank is never overwritten.
  When the owner asks a session to rewrite or merge projects, it uses `leads.py
  project-save` (only the fields given change), never ad-hoc SQL.
- **Never `current_date`, `now()` or the server timezone in SQL**: "today" is
  `data.today()` (America/Chicago), passed in. Dates are plain `date`s.
- **All SQL lives in `app/data.py`** (`backup.py`'s copy aside); calculations
  in `app/logic.py` (pure: no database, no Streamlit). Pages lay out and call
  those two, plus `ai`, `docx_io` and `posting` for what they do; the
  employer-site search flow that writes as it goes lives in `ui.py`.
- **The look lives in `app/theme.py`**: a light palette (the default) and a dark
  one as Streamlit theme options, read from the `settings` table ("theme")
  once per process and applied by `ui.setup()`, plus one stylesheet. `.streamlit/config.toml`
  must equal the light palette (`tests/test_theme.py` checks). `THEME.md`
  carries the look to other apps: its code blocks are `app/theme.py`,
  `config.toml` and ui's look helpers word for word (test_theme checks), so
  a change to one goes into THEME.md too. Pages use
  `ui.card()`, `ui.empty()` and the badge helpers rather than emoji or raw
  HTML; colour means something (blue = in progress, green = good, orange =
  attention, red = overdue/closed, grey = neutral, yellow = unverified: an
  estimate or missing pay, via `ui.pay_badge()`). Every row of choices is a
  horizontal `st.radio` (sub-pages: `ui.sections()`), which the stylesheet
  draws as the one pill selector (a grey track, the chosen one a gradient
  pill); never `st.tabs` (tabs forget their place on rerun), `st.pills`,
  `st.segmented_control` or a row of buttons;
  every delete goes through `ui.delete_button()` (tick box first); a "pick
  one" dropdown whose options can change takes `ui.round_key()` and
  `ui.bump_round()` after a delete, or it keeps showing the old choice.
- Knobs in `app/config.py`, including `FIT_CATEGORIES` (the lead-scoring
  categories and weights; `logic.fit_total` does the maths, the review rates)
  and the pay rules (`PAY_SOURCES`, `PAY_RESEARCH`; the review looks pay up only
  for jobs rating `PAY_RESEARCH_FIT`+ on role and location): pay is rated only when a
  lead has a salary, listed or estimated; `logic.clean_lead` refuses a pay
  rating without one, and unknown pay stays out of the score. A lead the alert
  or posting says runs a 9/80 or 4/10 week (`schedule` in its fit_detail,
  `logic.compressed_schedule` / `schedule_label`) scores `SCHEDULE_BONUS`
  more and wears `ui.schedule_badge`; an application's badge is read from its
  posting text. Never guessed from the employer.
  **Status / kind lists are repeated in `schema.sql` CHECKs** (statuses,
  work modes, lead statuses, `APPLY_STATES`, `PAY_SOURCES`, `DISMISS_REASONS`,
  `RESUME_SOURCE_KINDS`, `PROJECT_KINDS`): change both (tests fail if they
  drift). A `companies` row exists only while an application points at it
  (`data.delete_application` and `update_application` prune the rest). A lead's dedupe key is company|title (`logic.lead_key`); stale
  leads (`LEAD_STALE_DAYS`) are a view, not a status. Add a table → add it to `backup.TABLES` and the
  `TABLES` list in `conftest.py`.
- `schema.sql` must stay re-runnable (`if not exists`): `data.py` runs it on the
  first connection of each process (`apply_schema.py` runs only it; the tests
  use that for their throwaway database). Changing an existing table → also
  add an idempotent statement to `data.MIGRATIONS` (run after schema.sql, and
  by `leads.py add` and `profile-save` over HTTPS), so the live database
  updates itself.
- **Phone or computer**: `ui.on_phone()` (`logic.device_from_agent` on the
  User-Agent, tablets count as computers). A phone gets one centred column and the
  everyday tasks; wide editing grids show `ui.empty("computer", …)` instead.
  A computer gets the wide layout
  (`theme.COMPUTER_MAX_WIDTH`) and side-by-side views; a clickable table
  (`on_select`) puts its pick in session state and bumps its `round_key`, and
  ignores a tick past the end of its rows. Page tests run as a computer; the
  `phone` fixture switches. A button that calls Claude is `ui.claude_button` /
  `ui.claude_submit` (a "claude_" key: the stylesheet draws Claude's spark).
- Add forms sit behind `ui.disclosure()` buttons (server-side open state), not
  `st.expander`, which snaps shut when a click lands mid-load.
- Every page's first statement is `fresh.check()`: Community Cloud pulls new
  code into the running app but keeps old copies of `app/` modules loaded, so
  pages importing something new broke until a reboot. Keep it first; a new
  page gets it too.
- Pass plain Python values to psycopg, not numpy (`int(x)` on DataFrame ids).
  Put user text into `st.markdown` through `ui.md()`: `$` would become maths.
- Forms reset by bumping a counter in their key (`ui.done(message, counter)`
  bumps it, keeps the message for the next run and reruns); set a widget's
  session state only before it is drawn (or via a flag read at the top of the page).

## Tests
- `ruff check .` (unused names, import order, 100 columns) and `pytest` before
  every push. DB and page tests need
  `TEST_DATABASE_URL` (a throwaway Postgres; the cloud hook sets it, CI starts
  one). Never point it at Neon: `conftest.py` refuses, and the tests wipe it.
- Page tests use `streamlit.testing.v1.AppTest` against that database with
  `data.today` patched; new pages get a draws-empty / draws-with-data case for free.
- Work on a branch and open a pull request; `main` is what's live.

# Compact instructions
When this chat compacts, keep: every job in flight (what it is, its branch and pull request number, who runs it); the last deploy line; everything waiting on the owner and his answers so far; the owner's rules given in this chat that are not yet in CLAUDE.md or DECISIONS.md; the current batch's list of changes. Drop tool output, file contents and finished threads.
