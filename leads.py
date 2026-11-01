"""The daily job-alert review's way into the database.

    python leads.py profile          what you're looking for, as JSON, with the
                                     companies to skip and recent dismissals
    python leads.py rubric           today's date (owner's time zone) and the scoring
                                     categories, weights and thresholds, as JSON
    python leads.py known            every stored lead's dedupe key, one per line
    python leads.py watch            new jobs on the careers sites of the profile's
                                     companies to watch, as JSON
    python leads.py add leads.json   add scored leads; prints how many were new
    python leads.py digest run.json  the digest email for today's leads, as JSON
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
summary of the posting to rate it by; a site that can't be read is a
problem, not an error.

run.json gives the digest what the database doesn't know: app_url (the
app's address; required), and optionally emails_read, sources ({"LinkedIn":
4, ...}), already_known, duplicates, and problem (what went wrong, if
anything).
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


def watch(profile: dict) -> dict:
    """New jobs on the watched companies' careers sites (see the docstring)."""
    today, known = data.today(), data.known_lead_keys()
    skip = logic.skip_list(profile.get("skip_companies"))
    jobs, problems = [], []
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
            if len(jobs) < config.WATCH_MAX_JOBS and (
                    found := posting.employer_posting(job["url"])):
                row["location"] = row["location"] or found.location
                if pay := logic.listed_pay(found.text):
                    row["salary"], row["pay_source"] = pay, "listed"
                if schedule := logic.compressed_schedule(found.text):
                    row["schedule"] = schedule
                row["summary"] = found.text[:config.WATCH_SUMMARY_CHARS]
            jobs.append(row)
    return {"jobs": jobs, "problems": problems}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
