---
updated: 2026-11-06
state: Live and in daily use; four pages, the morning review and weekly backups all running.
---

# Status

## Live

- **The app** runs on Streamlit Community Cloud from `main`, as last
  changed by pull request #70 (Nov 6, 2026). The app has no version
  numbers; the latest merged pull request is the version.
- Four pages: Home, Job Leads, Applications, Resume and Projects. Sign-in by
  Google or password.
- Streamlit 1.66.1, Python 3.13.
- **Daily job-alert review**: a scheduled Claude session each morning
  ([`DAILY_REVIEW.md`](../DAILY_REVIEW.md)): alert emails and watched
  companies' careers sites in, scored leads and a digest email out.
- **GitHub**: only `main`; merged branches delete themselves (set Nov 3,
  2026).
- **Weekly backup**: every Sunday, a locked 7z file on the Backup run's page.
  The backup password was replaced on Nov 4, 2026 (the old one had never
  been saved); a manual run with the new one succeeded (Nov 5, 03:40 UTC).

## In progress

- Loading Nolan's work-portfolio export (19 projects) into the project bank
  (#70): 14 new projects added, and the five that were the same work as
  projects already there blended into those entries, as Nolan asked.

## Next

Nothing is under way; these two wait until wanted, each its own pull request.

- **Anthropic SDK 1.15 → 2.x** (held back in #63): `app/ai.py` imports a
  private path, `anthropic.lib._parse._transform.transform_schema`, which a
  major release can move. Replace it with the SDK's public helper (or a
  small transform of our own), then bump and run `tests/test_ai.py`.
- **Interview edit forms** on Applications sit in `st.expander`, which
  CLAUDE.md avoids for add forms: switch them to `ui.disclosure()` if a click
  ever snaps one shut.

## Needs the owner

Nothing pending.

## Known issues

- Unknown here: whether the morning review is succeeding every day (its runs
  are Claude sessions, not visible from this repository).
- The Backup run of Oct 18, 2026 failed; the ones after it succeeded. The
  cause isn't recorded.
- Backups from before Nov 4 can't be opened (their password was never
  saved), so the contacts, career entries and job history tables dropped on
  Oct 29 (#53) are gone for good.

### For Claude sessions

- Cloud sessions can't delete branches or change repository settings
  (GitHub answers 403). Merged branches delete themselves; the Delete merged
  branches workflow (#65) is the button for any left over.
- Live-database writes from a session go only through the `leads.py`
  commands meant for them.
- Streamlit 1.66: a keyed widget forgets its state when the page changes
  (why `ui.appearance` keys the Dark mode toggle by the mode in force). In
  `AppTest`, a form's values go with its submit: set a field, then click the
  submit, with no `.run()` between.
- The pill selector's CSS targets Streamlit's internal data-testids
  (`stRadioOption`): after any Streamlit bump, check the pills and Dark mode
  on screen, not just the tests.
- Watched companies: only Workday, Greenhouse and Lever careers sites can be
  read.
