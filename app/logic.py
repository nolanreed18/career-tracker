"""Pure calculations over the frames data.py returns: what needs attention,
the stats, formatting, and reading an imported spreadsheet. No database and
no Streamlit, so all of it is tested directly.
"""

import re
from dataclasses import dataclass
from datetime import date, time, timedelta

import pandas as pd

import config


def blank(value) -> bool:
    """None, NaN, NaT or empty text."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def value(x):
    """x, or None when blank -- for handing DataFrame cells back to Python."""
    return None if blank(x) else x


# ---- needs attention --------------------------------------------------------

@dataclass(frozen=True)
class Attention:
    kind: str            # overdue, due, interview, follow_up, stale_saved
    application_id: int
    headline: str        # "Acme — Data Analyst"
    detail: str          # "Follow up: 3 days overdue"
    on: date             # for ordering


ORDER = {"overdue": 0, "due": 0, "interview": 1, "follow_up": 2, "stale_saved": 3}


def needs_attention(apps: pd.DataFrame, interviews: pd.DataFrame, today: date,
                    follow_up_days: int = config.FOLLOW_UP_DAYS,
                    lookahead_days: int = config.INTERVIEW_LOOKAHEAD_DAYS) -> list[Attention]:
    """What to do next, most urgent first.

    - A next step dated today or earlier: due, or overdue.
    - An interview from today through lookahead_days ahead.
    - An open application with no next step, no interview coming up, and no
      update (status change, logged note, or interview) for follow_up_days:
      time to follow up -- or, if only saved, to apply or drop it.
    Closed applications (accepted, rejected, withdrawn) never appear.
    """
    items: list[Attention] = []
    last_interview: dict[int, date] = {}
    next_interview: dict[int, date] = {}
    for iv in interviews.itertuples(index=False):
        app_id, on = int(iv.application_id), iv.scheduled_on
        if on >= today:
            next_interview[app_id] = min(on, next_interview.get(app_id, on))
            if on <= today + timedelta(days=lookahead_days) and iv.status in config.OPEN_STATUSES:
                items.append(Attention(
                    "interview", app_id, f"{iv.company} — {iv.role}",
                    f"{value(iv.round) or 'Interview'}, {when(on, today)}"
                    + (f" at {clock(iv.start_time)}" if not blank(iv.start_time) else ""),
                    on))
        else:
            last_interview[app_id] = max(on, last_interview.get(app_id, on))

    for app in apps.itertuples(index=False):
        if app.status not in config.OPEN_STATUSES:
            continue
        app_id = int(app.application_id)
        headline = f"{app.company} — {app.role}"
        action_on = value(app.next_action_on)
        if action_on is not None:
            if action_on <= today:
                late = (today - action_on).days
                step = value(app.next_action) or "Next step"
                items.append(Attention(
                    "due" if late == 0 else "overdue", app_id, headline,
                    f"{step}: due today" if late == 0 else f"{step}: {plural(late, 'day')} overdue",
                    action_on))
            continue                       # a step is planned; nothing else to say
        if app_id in next_interview:
            continue                       # an interview is coming up
        last = max(app.last_update_on, last_interview.get(app_id, app.last_update_on))
        idle = (today - last).days
        if idle < follow_up_days:
            continue
        if app.status == "saved":
            items.append(Attention("stale_saved", app_id, headline,
                                   f"Saved {plural(idle, 'day')} ago — apply or drop it?", last))
        elif app.status == "offer":
            items.append(Attention("follow_up", app_id, headline,
                                   f"Offer open for {plural(idle, 'day')} — time to decide?", last))
        else:
            items.append(Attention("follow_up", app_id, headline,
                                   f"No update in {plural(idle, 'day')} — follow up?", last))

    return sorted(items, key=lambda i: (ORDER[i.kind], i.on, i.headline))


# ---- stats ------------------------------------------------------------------

def pipeline(apps: pd.DataFrame) -> pd.DataFrame:
    """How many applications are at each status, in pipeline order."""
    counts = apps["status"].value_counts() if not apps.empty else pd.Series(dtype=int)
    return pd.DataFrame({"status": config.STATUSES,
                         "applications": [int(counts.get(s, 0)) for s in config.STATUSES]})


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())          # Monday


def weekly_applications(apps: pd.DataFrame, today: date,
                        weeks: int = config.STATS_WEEKS) -> pd.DataFrame:
    """Applications sent per week (by applied date), the last `weeks` weeks
    ending with this one, zeros included."""
    this_week = week_start(today)
    starts = [this_week - timedelta(weeks=n) for n in reversed(range(weeks))]
    counts = dict.fromkeys(starts, 0)
    for applied in apps.get("applied_on", pd.Series(dtype=object)):
        if not blank(applied) and week_start(applied) in counts:
            counts[week_start(applied)] += 1
    return pd.DataFrame({"week": starts, "applications": [counts[s] for s in starts]})


def responded_ids(apps: pd.DataFrame, events: pd.DataFrame) -> set[int]:
    """Applications that ever reached a screen or further."""
    reached = set()
    if not events.empty:
        reached |= set(events.loc[events["status"].isin(config.RESPONDED_STATUSES),
                                  "application_id"].astype(int))
    if not apps.empty:
        reached |= set(apps.loc[apps["status"].isin(config.RESPONDED_STATUSES),
                                "application_id"].astype(int))
    return reached


def response_rate(apps: pd.DataFrame, events: pd.DataFrame) -> tuple[int, int]:
    """(responded, applied): of the applications actually sent, how many got
    as far as a screen. Rejections without a screen don't count as responses."""
    if apps.empty:
        return 0, 0
    sent = apps[apps["status"] != "saved"]
    reached = responded_ids(apps, events)
    return sum(int(i) in reached for i in sent["application_id"]), len(sent)


def by_source(apps: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Applications sent and responses, per source, most-used source first."""
    columns = ["source", "applied", "responded", "rate"]
    sent = apps[apps["status"] != "saved"] if not apps.empty else apps
    if sent.empty:
        return pd.DataFrame(columns=columns)
    reached = responded_ids(apps, events)
    rows = []
    for source, group in sent.groupby(sent["source"].map(lambda s: value(s) or "(not set)")):
        applied = len(group)
        responded = sum(int(i) in reached for i in group["application_id"])
        rows.append((source, applied, responded, responded / applied))
    return (pd.DataFrame(rows, columns=columns)
            .sort_values(["applied", "source"], ascending=[False, True])
            .reset_index(drop=True))


# ---- formatting -------------------------------------------------------------

def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def when(d: date, today: date) -> str:
    days = (d - today).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "yesterday"
    return f"{d:%a %b} {d.day}"


def clock(t: time) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


def money(n) -> str:
    return f"${n:,.0f}"


def salary_range(low, high) -> str:
    low, high = value(low), value(high)
    if low is not None and high is not None:
        return money(low) if low == high else f"{money(low)}–{money(high)}"
    if low is not None:
        return f"{money(low)}+"
    if high is not None:
        return f"up to {money(high)}"
    return ""


# ---- spreadsheet import -----------------------------------------------------

# Spreadsheet headers each field is recognised by, compared lower-case with
# underscores and dashes as spaces.
ALIASES = {
    "company": ["company", "company name", "employer", "organization", "organisation"],
    "role": ["role", "title", "job title", "position", "job"],
    "status": ["status", "stage"],
    "applied_on": ["applied on", "applied", "date applied", "application date", "date"],
    "job_url": ["job url", "url", "link", "job link", "posting", "job posting"],
    "location": ["location", "city"],
    "work_mode": ["work mode", "remote", "work type", "workplace", "on site"],
    "source": ["source", "found via", "where found", "found on"],
    "salary_min": ["salary min", "min salary", "salary from", "salary low"],
    "salary_max": ["salary max", "max salary", "salary to", "salary high"],
    "salary": ["salary", "salary range", "pay", "compensation"],
    "notes": ["notes", "note", "comments"],
}

STATUS_WORDS = {
    "saved": "saved", "wishlist": "saved", "interested": "saved", "to apply": "saved",
    "bookmarked": "saved",
    "applied": "applied", "submitted": "applied", "pending": "applied",
    "no response": "applied", "waiting": "applied",
    "screen": "screening", "screening": "screening", "phone screen": "screening",
    "recruiter call": "screening", "recruiter screen": "screening",
    "interview": "interviewing", "interviewing": "interviewing", "interviews": "interviewing",
    "onsite": "interviewing", "final round": "interviewing",
    "offer": "offer", "offered": "offer",
    "accepted": "accepted", "hired": "accepted",
    "rejected": "rejected", "declined": "rejected", "no": "rejected", "ghosted": "rejected",
    "closed": "rejected",
    "withdrawn": "withdrawn", "withdrew": "withdrawn",
}


def _norm(header: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(header)).strip().lower()


def match_columns(headers) -> dict[str, str]:
    """{field: spreadsheet header} for every field a header was found for."""
    by_norm = {_norm(h): h for h in headers}
    found = {}
    for field, names in ALIASES.items():
        for name in names:
            if name in by_norm and by_norm[name] not in found.values():
                found[field] = by_norm[name]
                break
    return found


def parse_money(text) -> int | None:
    """'$120k' -> 120000, '95,500' -> 95500; None if no number."""
    numbers = parse_salary(text)
    return numbers[0]


def parse_salary(text) -> tuple[int | None, int | None]:
    """'$120k-$140k' -> (120000, 140000); '90000' -> (90000, None)."""
    if blank(text):
        return None, None
    if isinstance(text, (int, float)):
        return int(text), None
    found = []
    for number, k in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*([kK])?", str(text)):
        n = float(number.replace(",", ""))
        found.append(int(round(n * 1000 if k else n)))
    if not found:
        return None, None
    return found[0], (found[1] if len(found) > 1 else None)


def parse_work_mode(text) -> str | None:
    if blank(text):
        return None
    t = str(text).lower()
    if "hybrid" in t:
        return "hybrid"
    if "remote" in t or t in ("yes", "true"):
        return "remote"
    if "site" in t or "office" in t or "person" in t:
        return "onsite"
    return None


def map_import(frame: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Rows ready for data.import_applications, and a note for each problem.

    A row needs a company and a role; one without is skipped. An unknown
    status becomes "applied" when there is an applied date, else "saved".
    Row numbers in the notes are spreadsheet rows (the header is row 1).
    """
    columns = match_columns(frame.columns)
    problems = []
    for needed in ("company", "role"):
        if needed not in columns:
            problems.append(f"No {needed} column found — expected a header like "
                            f"“{ALIASES[needed][0].title()}”.")
    if problems:
        return [], problems

    def cell(row, field):
        header = columns.get(field)
        return None if header is None else value(row[header])

    rows = []
    for index, row in frame.iterrows():
        line = index + 2 if isinstance(index, int) else index
        company, role = cell(row, "company"), cell(row, "role")
        if company is None or role is None:
            if any(not blank(v) for v in row.values):
                problems.append(f"Row {line}: skipped — needs both a company and a role.")
            continue

        applied_on = None
        raw_date = cell(row, "applied_on")
        if raw_date is not None:
            parsed = pd.to_datetime(raw_date, errors="coerce")
            if pd.isna(parsed):
                problems.append(f"Row {line}: couldn't read the date “{raw_date}”; left blank.")
            else:
                applied_on = parsed.date()

        raw_status = cell(row, "status")
        status = STATUS_WORDS.get(_norm(raw_status)) if raw_status is not None else None
        if status is None:
            status = "applied" if applied_on else "saved"
            if raw_status is not None:
                problems.append(f"Row {line}: unknown status “{raw_status}”; set to {status}.")

        low, high = parse_salary(cell(row, "salary"))
        if "salary_min" in columns:
            low = parse_money(cell(row, "salary_min"))
        if "salary_max" in columns:
            high = parse_money(cell(row, "salary_max"))
        if low is not None and high is not None and high < low:
            low, high = high, low

        mapped = {
            "company": str(company).strip(), "role": str(role).strip(), "status": status,
            "applied_on": applied_on,
            "job_url": cell(row, "job_url"), "location": cell(row, "location"),
            "work_mode": parse_work_mode(cell(row, "work_mode")),
            "source": cell(row, "source"), "salary_min": low, "salary_max": high,
            "notes": cell(row, "notes"),
        }
        rows.append({k: (str(v) if k in ("job_url", "location", "source", "notes")
                         and v is not None else v) for k, v in mapped.items()})
    return rows, problems


# ---- job leads --------------------------------------------------------------

def lead_key(company, title, location=None) -> str:
    """The same job from different sites gets the same key: company, title and
    location, lower-cased, with punctuation and extra spaces dropped."""
    def words(text) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))
    return "|".join(words(part) for part in (company, title, location))


def clean_lead(row: dict) -> tuple[dict | None, str | None]:
    """A lead from the daily review, ready for data.add_leads, or the reason it
    was refused. Needs a source, a title and a company; salary may be given as
    salary text ("$120k–$140k") or salary_min / salary_max; a fit score must
    be 1-10."""
    source, title, company = (value(row.get(k)) for k in ("source", "title", "company"))
    if source is None or title is None or company is None:
        return None, f"needs a source, a title and a company: {row}"
    lead = {
        "source": str(source).strip(),
        "title": str(title).strip(),
        "company": str(company).strip(),
        "location": value(row.get("location")),
        "work_mode": parse_work_mode(row.get("work_mode")),
        "job_url": job_link(row.get("job_url")),
        "fit_reason": value(row.get("fit_reason")),
    }
    low, high = value(row.get("salary_min")), value(row.get("salary_max"))
    if low is None and high is None:
        low, high = parse_salary(row.get("salary"))
    low, high = (None if n is None else int(n) for n in (low, high))
    if low is not None and high is not None and high < low:
        low, high = high, low
    lead["salary_min"], lead["salary_max"] = low, high
    posted = value(row.get("posted_on"))
    if posted is not None:
        parsed = pd.to_datetime(posted, errors="coerce")
        posted = None if pd.isna(parsed) else parsed.date()
    lead["posted_on"] = posted
    score = value(row.get("fit_score"))
    if score is not None:
        try:
            score = int(round(float(score)))
        except (TypeError, ValueError):
            return None, f"fit_score isn't a number: {row}"
        if not 1 <= score <= 10:
            return None, f"fit_score must be 1-10: {row}"
    lead["fit_score"] = score
    lead["dedupe_key"] = lead_key(lead["company"], lead["title"], lead["location"])
    return lead, None


def fit_label(score) -> str:
    """'🟢 8/10' for a strong fit, '🟡 5/10' for a maybe, '⚪ 2/10' for a weak
    one, '' when unscored."""
    score = value(score)
    if score is None:
        return ""
    icon = "🟢" if score >= config.STRONG_FIT else "🟡" if score >= config.MAYBE_FIT else "⚪"
    return f"{icon} {int(score)}/10"


def is_weak(score) -> bool:
    """A scored lead below MAYBE_FIT. Unscored ones aren't weak, just unknown."""
    score = value(score)
    return score is not None and score < config.MAYBE_FIT


_GLASSDOOR_GUESS = re.compile(r"^https?://(?:www\.)?glassdoor\.com/job-listing/?\?jl=(\d+)$")


def job_link(url) -> str | None:
    """The posting link to open. A Glassdoor link rebuilt from a listing ID
    (what the first daily review stored) is turned into the form Glassdoor
    serves; anything else is kept as it is."""
    url = value(url)
    if url is None:
        return None
    url = str(url).strip()
    if match := _GLASSDOOR_GUESS.match(url):
        return f"https://www.glassdoor.com/partner/jobListing.htm?jobListingId={match.group(1)}"
    return url
