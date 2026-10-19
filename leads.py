"""The daily job-alert review's way into the database.

    python leads.py profile          what you're looking for, as JSON
    python leads.py rubric           today's date (owner's time zone) and the scoring
                                     categories, weights and thresholds, as JSON
    python leads.py known            every stored lead's dedupe key, one per line
    python leads.py add leads.json   add scored leads; prints how many were new

leads.json is a list of objects with source, title and company (required),
and any of location, work_mode, salary (text like "$120k-$140k") or
salary_min / salary_max, job_url, posted_on (YYYY-MM-DD), fit_reason, and
the scoring: fit, an object rating each rubric category 1-10 (e.g.
{"role": 9, "industry": 6, ...}), plus deal_breaker (true/false). The score
is worked out from those. A plain fit_score (1-10) is also accepted. The
same job seen before, from any site, is skipped. Nothing is added unless
every row is valid.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))

import config  # noqa: E402
import data  # noqa: E402
import logic  # noqa: E402


def main(argv: list[str]) -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        data.use_http()          # cloud sessions can't open a Postgres connection
    command = argv[0] if argv else ""
    if command == "profile":
        profile = data.job_profile()
        print(json.dumps(profile or {}, default=str, indent=2))
        return 0
    if command == "rubric":
        print(json.dumps({
            "today": data.today().isoformat(),      # the owner's date; the session clock is UTC
            "categories": [{"key": key, "label": label, "weight": weight, "what": what}
                           for key, (label, weight, what) in config.FIT_CATEGORIES.items()],
            "score": "weighted average of the ratings, to one decimal",
            "deal_breaker_cap": config.DEAL_BREAKER_CAP,
            "strong_fit": config.STRONG_FIT,
            "maybe_fit": config.MAYBE_FIT,
        }, indent=2))
        return 0
    if command == "known":
        for key in sorted(data.known_lead_keys()):
            print(key)
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
        added, skipped = data.add_leads(leads, data.today())
        print(f"added {added}, skipped {skipped} already seen")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
