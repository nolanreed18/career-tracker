# Overview

## What it is

Career Tracker is Nolan's own job-search tool: one place for the jobs worth
a look, the applications in flight, and the resume tailored to each one. It
is a website that works on a phone and on a computer, used by one person.
It is a public app with a sign-in, so nobody else sees the data.

It does four things:

- **Job Leads.** Every morning a scheduled Claude session reads the job-alert
  emails in the job-search Gmail and checks the careers sites of the
  companies Nolan watches. It scores each new job 1–10 against **What I'm
  looking for** (role, industry, location, pay, level, extras; a 9/80 or 4/10
  schedule earns a little more), stores it, and emails a digest. In the app,
  Nolan adds a lead as an application or dismisses it with a reason.
- **Applications.** Each job applied to, with its status history, next step,
  interviews and the job posting. Adding a lead reads the posting and looks
  for the same job on the employer's own careers site, so he can apply there
  instead of through a job board.
- **Resume and Projects.** The master resume kept as data (built from his
  Word resume and other files by Claude), a bank of work and personal
  projects in full detail, and **Resume Builder**: one click has Claude tailor
  the master to a posting, kept to one page, with a cover letter, both
  downloaded as Word files in his own layout.
- **Home.** How the lead pipeline stands, and what needs doing: overdue next
  steps, interviews this week, applications with no update for 14 days.

The [README](../README.md) describes every screen in detail, and how to set
the app up from scratch.

## How it's built

| Piece | What it is |
|---|---|
| Language | Python 3.13 |
| Screens | [Streamlit](https://streamlit.io) (`app/`) |
| Database | Postgres on [Neon](https://neon.tech) (free tier), project `career-tracker` |
| Hosting | Streamlit Community Cloud, deployed from the `main` branch; main file `app/Home.py` |
| Sign-in | Google (`st.login`, only allowed emails) or a password |
| Claude in the app | The Anthropic API, behind buttons Nolan clicks; each call's cost is logged |
| Daily review | A scheduled Claude Code cloud session following [`DAILY_REVIEW.md`](../DAILY_REVIEW.md), with the Gmail connector; it reaches the database over Neon's HTTPS endpoint through `leads.py` |
| Backups | A GitHub Actions workflow every Sunday: every table to CSV, locked in a password-protected 7z file, kept 90 days |
| Tests | `ruff` and `pytest` on every pull request, against a throwaway Postgres |

The secrets it needs are named in the README's setup steps (`DATABASE_URL`,
`APP_PASSWORD`, `ANTHROPIC_API_KEY`, `ALLOWED_EMAILS`, the `[auth]` block for
Google, and `BACKUP_PASSWORD` for the backup). Their values never go in this
repository; where each one is kept is in the mothership's
[Studio/Secrets.md](https://github.com/nolanreed18/mothership).

## Where things live

| Where | What |
|---|---|
| `app/Home.py`, `app/pages/` | The four pages: Home, Job Leads, Applications, Resume and Projects |
| `app/ui.py` | What every page shares: sign-in, layout, cards, pills, badges, the employer-site search |
| `app/data.py` | Every database read and write, and the migrations that update the live database |
| `app/logic.py` | The calculations (no database, no screens): scoring, attention, resume fitting |
| `app/config.py` | Settings and the fixed lists (statuses, scoring weights, prices) |
| `app/ai.py`, `app/resume_schema.py` | Claude calls and the shapes of their answers |
| `app/posting.py` | Reading job postings and employer careers sites (Workday, Greenhouse, Lever) |
| `app/docx_io.py` | Reading and writing Word files in the owner's own layout |
| `app/digest.py` | The daily digest email |
| `app/theme.py`, `.streamlit/config.toml` | The look (light and dark) |
| `app/fresh.py` | Reloads the app's code after Community Cloud pulls an update |
| `schema.sql`, `apply_schema.py` | The tables |
| `db.py` | Secrets and the database connection (plain, or HTTPS for cloud sessions) |
| `leads.py` | The daily review's only way into the database |
| `backup.py`, `.github/workflows/backup.yml` | The weekly backup |
| `.github/workflows/` | Tests, backup, delete merged branches, docs check |
| `.claude/` | Settings and the session-start hook for Claude Code sessions |
| `tests/`, `conftest.py` | The tests |
| [`DAILY_REVIEW.md`](../DAILY_REVIEW.md) | The morning review's steps (stays at the top level: the scheduled task reads it there) |
| [`THEME.md`](../THEME.md) | The look, written up to copy into another app |

## The other notes

- [`CLAUDE.md`](../CLAUDE.md): how to work in this repository.
- [`STATUS.md`](STATUS.md): where things stand now.
- [`DECISIONS.md`](DECISIONS.md): the rules and choices, and why.
- [`HISTORY.md`](HISTORY.md): what changed, when.
