"""The daily job-alert review's way into the database.

    python3 leads.py profile          what you're looking for, as JSON, with the
                                     companies to skip and recent dismissals
    python3 leads.py profile-save changes.json
                                     change what you're looking for: only the
                                     fields given, the rest kept
    python3 leads.py rubric           today's date (owner's time zone) and the scoring
                                     categories, weights and thresholds, as JSON
    python3 leads.py known            every stored lead's dedupe key, one per line
    python3 leads.py watch            new jobs on the careers sites of the profile's
                                     companies to watch, as JSON
    python3 leads.py add leads.json   add scored leads; prints how many were new
    python3 leads.py digest run.json  the digest email for today's leads, as JSON
                                     {"subject", "html", "text"}

leads.json is a list of objects with source, title and company (required),
and any of location, work_mode, salary (text like "$120k-$140k") or
salary_min / salary_max, pay_source ("listed" or "estimated"; an estimate
needs a pay_note saying where it came from), job_url, posted_on
(YYYY-MM-DD), fit_reason, and the scoring: fit, an object rating each rubric
category 1-10 (e.g. {"role": 9, "industry": 6, ...}), plus deal_breaker
(true/false). The score is worked out from those; rate pay only when a
salary is given. A plain fit_score (1-10) is also accepted. The same job
(company and title) seen before, from any site, is skipped, as is any job
from the profile's companies to skip. Nothing is added unless every row is
valid.

watch prints {"jobs": [...], "problems": [...]}: each job not seen before,
in config.WATCH_SEARCH's places, as a leads.json row (source, company,
title, location, job_url, posted_on, and from its posting salary with
pay_source "listed" when it states one, schedule when it says one) plus a
summary of the posting to rate it by (the postings of the first
config.WATCH_MAX_JOBS jobs are read; later rows have no summary or pay, and
problems says so); a site that can't be read is a problem, not an error.

changes.json is an object of profile fields and their new values (the
fields `profile` prints, e.g. {"watch_companies": "bp https://...\nSuncor
https://..."}); a list field is given whole. A Claude session uses it when
the owner asks for a change, instead of the owner typing it into the app.

run.json gives the digest what the database doesn't know: app_url (the
app's address; required), and optionally emails_read, sources ({"LinkedIn":
4, ...}: alert emails per site), watched (jobs that came from `watch`),
already_known, duplicates, and problem (what went wrong, if anything).
"""

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))

import config  # noqa: E402
import data  # noqa: E402
import digest  # noqa: E402
import logic  # noqa: E402
import posting  # noqa: E402


def main(argv: list[str]) -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        data.use_http()          # cloud sessions can't open a Postgres connection
    command = argv[0] if argv else ""
    if command == "profile":
        profile = data.job_profile() or {}
        since = data.today() - timedelta(days=config.DISMISSAL_DAYS)
        profile["dismissed_recently"] = logic.dismissal_notes(data.dismissed_recently(since))
        print(json.dumps(profile, default=str, indent=2))
        return 0
    if command == "profile-save" and len(argv) == 2:
        changes = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        problem = profile_problem(changes)
        if problem:
            print(problem, file=sys.stderr)
            return 1
        data.migrate()                     # the live table may predate a field
        current = data.job_profile() or {}
        changed = sorted(f for f, v in changes.items() if v != current.get(f))
        data.save_job_profile(data.today(), **{
            **{field: current.get(field) for field in data.PROFILE_FIELDS}, **changes})
        print(f"saved: {', '.join(changed)}" if changed else "nothing changed")
        for name, url in logic.watch_list(changes.get("watch_companies")):
            if not posting.careers_site(url):
                print(f"note: {name}'s link isn't a Workday, Greenhouse or Lever careers "
                      "site, so the review can't watch it")
        return 0
    if command == "rubric":
        print(json.dumps({
            "today": data.today().isoformat(),      # the owner's date; the session clock is UTC
            "categories": [{"key": key, "label": label, "weight": weight, "what": what}
                           for key, (label, weight, what) in config.FIT_CATEGORIES.items()],
            "score": "weighted average of the ratings, to one decimal; a category not "
                     "rated is left out",
            "pay": {"sources": config.PAY_SOURCES, "research": config.PAY_RESEARCH,
                    "research_fit": config.PAY_RESEARCH_FIT,
                    "rule": "rate pay only when a salary is given (listed, or your "
                            "estimate with a pay_note); otherwise leave pay out of fit"},
            "schedule": {"bonus": config.SCHEDULE_BONUS,
                         "rule": "give schedule only when the alert or the posting says the "
                                 "job runs a 9/80 or 4/10 (or other compressed) week; never "
                                 "guess it from the employer"},
            "deal_breaker_cap": config.DEAL_BREAKER_CAP,
            "strong_fit": config.STRONG_FIT,
            "maybe_fit": config.MAYBE_FIT,
        }, indent=2))
        return 0
    if command == "known":
        for key in sorted(data.known_lead_keys()):
            print(key)
        return 0
    if command == "watch":
        print(json.dumps(watch(data.job_profile() or {}), default=str, indent=2))
        return 0
    if command == "add" and len(argv) == 2:
        rows = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            print("leads file must hold a JSON list", file=sys.stderr)
            return 1
        leads, problems = [], []
        for row in rows:
            lead, problem = logic.clean_lead(row)
            if problem:
                problems.append(problem)
            else:
                leads.append(lead)
        if problems:
            print("nothing added:\n" + "\n".join(problems), file=sys.stderr)
            return 1
        data.migrate()                     # the live tables may predate a column
        skip = logic.skip_list((data.job_profile() or {}).get("skip_companies"))
        kept = [lead for lead in leads if not logic.skips_company(lead["company"], skip)]
        dropped = len(leads) - len(kept)
        added, skipped = data.add_leads(kept, data.today())
        print(f"added {added}, skipped {skipped} already seen"
              + (f", dropped {dropped} from companies to skip" if dropped else ""))
        return 0
    if command == "digest" and len(argv) == 2:
        notes = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        if not isinstance(notes, dict) or not notes.get("app_url"):
            print("run.json must be a JSON object with app_url", file=sys.stderr)
            return 1
        today = data.today()
        leads = data.leads_found(today).to_dict("records")
        attention = logic.needs_attention(data.applications(), data.interviews(), today)
        waiting = data.strong_leads_waiting(today).to_dict("records")
        print(json.dumps(digest.render(today, leads, attention, notes["app_url"], notes,
                                       waiting), indent=2))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


def profile_problem(changes) -> str | None:
    """Why a profile-save file can't be used, or None."""
    if not isinstance(changes, dict) or not changes:
        return "changes.json must hold a JSON object of profile fields to change"
    unknown = set(changes) - data.PROFILE_FIELDS
    if unknown:
        return (f"unknown profile fields {sorted(unknown)}; the fields are "
                f"{sorted(data.PROFILE_FIELDS)}")
    salary = changes.get("min_salary")
    if salary is not None and (isinstance(salary, bool) or not isinstance(salary, int)
                               or salary < 0):
        return "min_salary must be a whole number of dollars a year, or null"
    for field, value in changes.items():
        if field != "min_salary" and value is not None and not isinstance(value, str):
            return f"{field} must be text (lines separated by \\n), or null"
    return None


def watch(profile: dict) -> dict:
    """New jobs on the watched companies' careers sites (see the docstring)."""
    today, known = data.today(), data.known_lead_keys()
    skip = logic.skip_list(profile.get("skip_companies"))
    jobs, problems, unread = [], [], 0
    for name, url in logic.watch_list(profile.get("watch_companies")):
        listed = posting.site_jobs(url)
        if listed is None:
            problems.append(f"{name}: couldn't read {url} (a Workday, Greenhouse or Lever "
                            "careers site)")
            continue
        for job in listed:
            key = logic.lead_key(name, job["title"])
            if key in known or logic.skips_company(name, skip):
                continue
            known.add(key)
            row = {"source": f"{name} careers site", "company": name, "title": job["title"],
                   "location": job["location"], "job_url": job["url"],
                   "posted_on": logic.workday_posted(job["posted"], today)}
            if len(jobs) >= config.WATCH_MAX_JOBS:
                unread += 1                      # listed, but its posting wasn't read
            elif found := posting.employer_posting(job["url"]):
                if not row["location"] and found.location and not logic.watch_place(
                        found.location):
                    continue                     # its several places are all elsewhere
                row["location"] = row["location"] or found.location
                if pay := logic.listed_pay(found.text):
                    row["salary"], row["pay_source"] = pay, "listed"
                if schedule := logic.compressed_schedule(found.text):
                    row["schedule"] = schedule
                row["summary"] = found.text[:config.WATCH_SUMMARY_CHARS]
            jobs.append(row)
    if unread:
        problems.append(f"{unread} jobs past the first {config.WATCH_MAX_JOBS}: their postings "
                        "weren't read, so they have no summary or pay (rate them from the "
                        "title and location, or look the posting up as in step 5)")
    return {"jobs": jobs, "problems": problems}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
