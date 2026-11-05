---
updated: 2026-11-04
state: Live and in daily use; four pages, the morning review and weekly backups all running.
---

# Status

## Live

- **The app** runs on Streamlit Community Cloud from `main`, as last
  changed by pull request #65 (Nov 2, 2026). The app has no version
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

- Nothing. The docs were brought up to the studio's standard on Nov 4 (#66).

## Next

- Nothing is planned in the repository. Held back on purpose (#63): the
  Anthropic SDK's 2.x release, a major change, since the app imports a
  private path from the SDK; it wants a pull request of its own.

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
