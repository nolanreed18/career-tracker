"""Pure calculations over the frames data.py returns: what needs attention,
the stats, formatting, and reading an imported spreadsheet. No database and
no Streamlit, so all of it is tested directly.
"""

import calendar
import copy
import math
import re
from dataclasses import dataclass
from datetime import date, time, timedelta
from urllib.parse import urlparse

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


# ---- phone or computer --------------------------------------------------------

PHONE_AGENT = re.compile(r"iPhone|iPod|Android.+Mobile|Windows Phone|IEMobile|BlackBerry|"
                         r"Opera Mini|Mobile.+Firefox", re.I)


def device_from_agent(agent) -> str:
    """"phone" for a phone's browser (its User-Agent says so), else
    "computer": a tablet, a computer or an unknown browser gets the bigger
    layout."""
    return "phone" if PHONE_AGENT.search(str(agent or "")) else "computer"


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


# ---- pipeline ---------------------------------------------------------------

def application_labels(apps: pd.DataFrame) -> dict[int, str]:
    """{application_id: "Company — Role"} for a dropdown (plain ints: the
    database driver doesn't take numpy's), marked "· resume ready" when the
    frame says a tailored resume exists."""
    ready = apps["tailored"] > 0 if "tailored" in apps.columns else [False] * len(apps)
    return {int(r.application_id): f"{r.company} — {r.role}" + (" · resume ready" if done else "")
            for r, done in zip(apps.itertuples(), ready)}


def pipeline(apps: pd.DataFrame) -> pd.DataFrame:
    """How many applications are at each status, in pipeline order."""
    counts = apps["status"].value_counts() if not apps.empty else pd.Series(dtype=int)
    return pd.DataFrame({"status": config.STATUSES,
                         "applications": [int(counts.get(s, 0)) for s in config.STATUSES]})


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())          # Monday


def weekly_applications(apps: pd.DataFrame, today: date, weeks: int) -> pd.DataFrame:
    """Applications sent per week (by applied date), the last `weeks` weeks
    ending with this one, zeros included."""
    this_week = week_start(today)
    starts = [this_week - timedelta(weeks=n) for n in reversed(range(weeks))]
    counts = dict.fromkeys(starts, 0)
    for applied in apps.get("applied_on", pd.Series(dtype=object)):
        if not blank(applied) and week_start(applied) in counts:
            counts[week_start(applied)] += 1
    return pd.DataFrame({"week": starts, "applications": [counts[s] for s in starts]})


# ---- formatting -------------------------------------------------------------

def for_display(frame: pd.DataFrame, dates: tuple[str, ...] = ()) -> pd.DataFrame:
    """A copy for st.dataframe: missing text shows as blank rather than "None",
    and the named date columns become real dates (blank when missing)."""
    out = frame.copy()
    for column in out.columns:
        if column in dates:
            out[column] = pd.to_datetime(out[column], errors="coerce")
        elif out[column].dtype == object or pd.api.types.is_string_dtype(out[column]):
            out[column] = out[column].fillna("")
    return out


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def shorten(text: str, limit: int) -> str:
    """The text cut to limit characters at a word, with an ellipsis."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] if " " in text[:limit] else text[:limit]
    return cut.rstrip(",;:") + "…"


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


# ---- pay and work mode ----------------------------------------------------

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


# ---- job leads --------------------------------------------------------------

def words(text) -> str:
    """Text lower-cased with punctuation and extra spaces dropped, for
    matching names however a site writes them."""
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def lead_key(company, title) -> str:
    """The same job from different sites gets the same key: company and
    title, lower-cased, with punctuation and extra spaces dropped. The
    location is left out on purpose: sites word it differently ("Denver, CO",
    "Denver Metropolitan Area"), and one lead per job is enough."""
    return f"{words(company)}|{words(title)}"


def is_stale(found_on, today: date, days: int = config.LEAD_STALE_DAYS) -> bool:
    """A lead that arrived more than `days` ago (a posting that old is
    usually gone)."""
    found_on = value(found_on)
    return found_on is not None and (today - found_on).days > days


def split_stale(leads: pd.DataFrame, today: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(fresh, stale) halves of a leads frame."""
    if leads.empty:
        return leads, leads
    stale = leads["found_on"].map(lambda d: is_stale(d, today))
    return leads[~stale], leads[stale]


def skip_list(text) -> list[str]:
    """The profile's companies to skip, one per line or comma, normalised."""
    if blank(text):
        return []
    return [w for w in (words(part) for part in re.split(r"[\n,;]+", str(text))) if w]


def skips_company(company, skip: list[str]) -> bool:
    """Whether a lead's company is on the skip list: the same words, or a
    skip entry contained in the name ("robert half" matches "Robert Half
    Technology")."""
    name = words(company)
    return any(entry == name or f" {entry} " in f" {name} " for entry in skip)


def dismiss_reasons(text) -> list[str]:
    """A lead's dismiss reasons, stored comma-separated, as a list."""
    return [part for part in str(text or "").split(", ") if part]


def dismissal_notes(dismissed: pd.DataFrame) -> list[dict]:
    """Recent dismissals as plain records for the daily review: title,
    company, location, reason and date."""
    notes = []
    for row in dismissed.itertuples(index=False):
        notes.append({"title": row.title, "company": row.company,
                      "location": value(row.location), "reason": value(row.dismiss_reason),
                      "dismissed_on": (None if blank(row.dismissed_on)
                                       else str(row.dismissed_on))})
    return notes


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
    source_of_pay, note = value(row.get("pay_source")), value(row.get("pay_note"))
    if low is None and high is None:
        if source_of_pay is not None:
            return None, f"pay_source given but no salary: {row}"
    else:
        source_of_pay = str(source_of_pay or "listed").strip().lower()
        if source_of_pay not in config.PAY_SOURCES:
            return None, f"pay_source must be one of {config.PAY_SOURCES}: {row}"
        if source_of_pay == "estimated" and note is None:
            return None, f"an estimated salary needs a pay_note saying where it came from: {row}"
    lead["pay_source"] = source_of_pay
    lead["pay_note"] = None if note is None else str(note).strip()
    posted = value(row.get("posted_on"))
    if posted is not None:
        parsed = pd.to_datetime(posted, errors="coerce")
        posted = None if pd.isna(parsed) else parsed.date()
    lead["posted_on"] = posted
    ratings = row.get("fit")
    if ratings:
        if not isinstance(ratings, dict):
            return None, f"fit must be an object of category ratings: {row}"
        unknown = set(ratings) - set(config.FIT_CATEGORIES)
        if unknown:
            return None, f"unknown fit categories {sorted(unknown)}: {row}"
        if "pay" in ratings and lead["pay_source"] is None:
            return None, ("pay was rated but no salary is given: leave pay out of fit when "
                          f"it's unknown, or give the salary (and pay_source): {row}")
        cleaned = {}
        for category, rating in ratings.items():
            try:
                rating = float(rating)
            except (TypeError, ValueError):
                return None, f"fit rating for {category} isn't a number: {row}"
            if not 1 <= rating <= 10:
                return None, f"fit rating for {category} must be 1-10: {row}"
            cleaned[category] = int(round(rating))
        deal_breaker = str(row.get("deal_breaker", "")).strip().lower() in ("true", "yes", "1")
        lead["fit_score"] = fit_total(cleaned, deal_breaker)
        lead["fit_detail"] = {"ratings": cleaned, "deal_breaker": deal_breaker}
    else:
        score = value(row.get("fit_score"))
        if score is not None:
            try:
                score = round(float(score), 1)
            except (TypeError, ValueError):
                return None, f"fit_score isn't a number: {row}"
            if not 1 <= score <= 10:
                return None, f"fit_score must be 1-10: {row}"
        lead["fit_score"] = score
        lead["fit_detail"] = None
    lead["dedupe_key"] = lead_key(lead["company"], lead["title"])
    return lead, None


def fit_total(ratings: dict, deal_breaker: bool = False) -> float | None:
    """The score from category ratings (1-10 each): their weighted average
    (config.FIT_CATEGORIES), to one decimal, capped at DEAL_BREAKER_CAP when a
    deal-breaker applies. Categories not rated are left out of the average.
    None when nothing is rated."""
    weights = {k: config.FIT_CATEGORIES[k][1] for k in ratings if k in config.FIT_CATEGORIES}
    if not weights:
        return None
    total = sum(ratings[k] * w for k, w in weights.items()) / sum(weights.values())
    if deal_breaker:
        total = min(total, config.DEAL_BREAKER_CAP)
    return round(total, 1)



def pay_state(salary_min, salary_max, pay_source) -> tuple[str, str]:
    """('listed', '$120,000–$140,000'), ('estimated', '~$120,000–$140,000') or
    ('unknown', 'Pay not listed'): how sure a lead's pay is, and the text."""
    text = salary_range(salary_min, salary_max)
    if not text:
        return "unknown", "Pay not listed"
    if value(pay_source) == "estimated":
        return "estimated", f"~{text}"
    return "listed", text


def fit_text(score) -> str:
    """'9' or '8.3': a score without a needless '.0'."""
    score = value(score)
    return "" if score is None else f"{float(score):g}"


def fit_tier(score) -> str | None:
    """'strong' (STRONG_FIT and up), 'maybe' (MAYBE_FIT and up), 'weak', or
    None when unscored."""
    score = value(score)
    if score is None:
        return None
    score = float(score)
    return ("strong" if score >= config.STRONG_FIT
            else "maybe" if score >= config.MAYBE_FIT else "weak")


def is_weak(score) -> bool:
    """A scored lead below MAYBE_FIT. Unscored ones aren't weak, just unknown."""
    return fit_tier(score) == "weak"


_GLASSDOOR_GUESS = re.compile(r"^https?://(?:www\.)?glassdoor\.com/job-listing/?\?jl=(\d+)$")
_LINKEDIN_JOB = re.compile(r"^https?://(?:www\.)?linkedin\.com/(?:comm/)?jobs/view/(\d+)")
_INDEED_JOB = re.compile(r"^https?://(?:www\.)?indeed\.com/(?:viewjob|rc/clk|pagead/clk)\b")


def is_job_board(url) -> bool:
    """True for a link on a job board or aggregator (config.JOB_BOARDS), as
    against an employer's own site."""
    host = urlparse(str(url or "")).netloc.lower()
    return any(host == board or host.endswith("." + board) for board in config.JOB_BOARDS)


def job_link(url) -> str | None:
    """The posting link to open, cleaned: a Google or alert-email redirect is
    unwrapped to the page it points at; LinkedIn, Indeed and Glassdoor
    postings lose their tracking parameters (a LinkedIn alert link runs to
    600 characters; the posting itself needs only its id). Anything else is
    kept as it is."""
    from urllib.parse import parse_qs, unquote, urlsplit

    url = value(url)
    if url is None:
        return None
    url = str(url).strip()
    parts = urlsplit(url)
    if parts.netloc.endswith("google.com") and parts.path == "/url":        # a redirect
        inner = parse_qs(parts.query).get("q") or parse_qs(parts.query).get("url")
        if inner:
            return job_link(unquote(inner[0]))
    if match := _GLASSDOOR_GUESS.match(url):
        return f"https://www.glassdoor.com/partner/jobListing.htm?jobListingId={match.group(1)}"
    if parts.netloc.endswith("glassdoor.com"):
        listing = parse_qs(parts.query).get("jobListingId")
        if listing and listing[0].isdigit():
            return f"https://www.glassdoor.com/partner/jobListing.htm?jobListingId={listing[0]}"
    if match := _LINKEDIN_JOB.match(url):
        return f"https://www.linkedin.com/jobs/view/{match.group(1)}/"
    if _INDEED_JOB.match(url):
        key = parse_qs(parts.query).get("jk")
        if key:
            return f"https://www.indeed.com/viewjob?jk={key[0]}"
    return url


# ---- master resume ------------------------------------------------------------

PROJECT_COLUMNS = {
    "title": ["projecttitle", "project title", "project", "title", "name"],
    "company": ["company", "employer"],
    "summary": ["quicksummary", "quick summary", "summary"],
    "rank": ["qualityrank", "quality rank", "rank"],
    "situation": ["situation"], "task": ["task"], "action": ["action"], "result": ["result"],
    "skills": ["hardskills", "hard skills", "skills", "tools"],
}


def _norm(header: str) -> str:
    """A spreadsheet header lower-cased, with underscores and dashes as spaces."""
    return re.sub(r"[\s_\-]+", " ", str(header)).strip().lower()


def projects_text(frame: pd.DataFrame) -> str:
    """A projects spreadsheet (one row per project, STAR-style columns) as
    plain text for Claude, one block per project."""
    columns = {}
    by_norm = {_norm(c).replace(" ", ""): c for c in frame.columns}
    for field, names in PROJECT_COLUMNS.items():
        for name in names:
            if name.replace(" ", "") in by_norm:
                columns[field] = by_norm[name.replace(" ", "")]
                break
    blocks = []
    for _, row in frame.iterrows():
        title = value(row.get(columns.get("title")))
        if title is None:
            continue
        lines = [f"Project: {str(title).strip()}"]
        for field in ("company", "rank", "summary", "situation", "task", "action", "result",
                      "skills"):
            text = value(row.get(columns.get(field)))
            if isinstance(text, float) and text.is_integer():
                text = int(text)                            # a rank of 5, not 5.0
            if text is not None:
                lines.append(f"{field.capitalize()}: {str(text).strip()}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def clean_resume(content: dict) -> dict:
    """The master resume's data tidied for saving: text stripped, empty
    bullets and roles dropped, ranks kept to 1..BULLET_RANK_MAX."""
    import resume_schema

    resume = resume_schema.Resume.model_validate(content)
    for group in (resume.roles, resume.projects):
        for role in group:
            role.employer, role.title = role.employer.strip(), role.title.strip()
            role.location, role.start, role.end = (role.location.strip(), role.start.strip(),
                                                   role.end.strip())
            kept = []
            for bullet in role.bullets:
                bullet.text = " ".join(bullet.text.split())
                if not bullet.text:
                    continue
                bullet.skills = [s.strip() for s in bullet.skills if s.strip()]
                bullet.rank = max(1, min(config.BULLET_RANK_MAX, int(bullet.rank)))
                bullet.source = bullet.source.strip() or "manual"
                kept.append(bullet)
            role.bullets = kept
        group[:] = [role for role in group if role.employer]
    resume.education = [e for e in resume.education if e.school.strip()]
    resume.skill_groups = [g for g in resume.skill_groups if g.name.strip()]
    resume.name, resume.email = resume.name.strip(), resume.email.strip()
    resume.phone, resume.linkedin = resume.phone.strip(), resume.linkedin.strip()
    return resume.model_dump()


def prints(role: dict) -> bool:
    """Whether a role or project goes on the printed master: it does when at
    least one of its bullets is ticked in_master."""
    return any(b.get("in_master") for b in role.get("bullets", []))


def resume_counts(content: dict) -> dict:
    """How much the master holds: roles and projects (and how many of them
    print), bullets on the master and bullets waiting in the pool."""
    on, pool = 0, 0
    roles, projects = list(content.get("roles", [])), list(content.get("projects", []))
    for role in roles + projects:
        for bullet in role.get("bullets", []):
            if bullet.get("in_master"):
                on += 1
            else:
                pool += 1
    return {"roles": len(roles), "projects": len(projects),
            "master_roles": sum(prints(r) for r in roles),
            "master_projects": sum(prints(p) for p in projects),
            "master_bullets": on, "pool_bullets": pool}


def month_start(d: date) -> date:
    return d.replace(day=1)


def skills_text(skills) -> str:
    return ", ".join(skills) if isinstance(skills, list) else str(skills or "")


def skills_list(text) -> list[str]:
    if isinstance(text, list):
        return [s.strip() for s in text if str(s).strip()]
    return [s.strip() for s in str(text or "").split(",") if s.strip()]


# ---- tailored resumes ---------------------------------------------------------

def clean_tailored(content: dict) -> dict:
    """A tailored resume's data tidied for saving: text stripped, empty
    bullets dropped, roles with no bullets dropped (a tailored role is what
    prints), blank keywords and changes dropped."""
    import resume_schema

    tailored = resume_schema.Tailored.model_validate(content)
    for group in (tailored.roles, tailored.projects):
        for role in group:
            role.employer, role.title = role.employer.strip(), role.title.strip()
            role.location, role.start, role.end = (role.location.strip(), role.start.strip(),
                                                   role.end.strip())
            kept = []
            for bullet in role.bullets:
                bullet.text = " ".join(bullet.text.split())
                if not bullet.text:
                    continue
                bullet.original = " ".join(bullet.original.split())
                bullet.skills = [s.strip() for s in bullet.skills if s.strip()]
                kept.append(bullet)
            role.bullets = kept
        group[:] = [role for role in group if role.employer and role.bullets]
    tailored.skill_groups = [g for g in tailored.skill_groups if g.name.strip()]
    tailored.keywords = [k for k in tailored.keywords if k.term.strip()]
    tailored.changes = [c.strip() for c in tailored.changes if c.strip()]
    tailored.fit_notes = tailored.fit_notes.strip()
    tailored.cover_letter = tailored.cover_letter.strip()
    return tailored.model_dump()


def tailored_export(master: dict, tailored: dict) -> dict:
    """The tailored resume in the master's shape (resume_schema.Resume), so
    docx_io.build prints it: contact line and education from the master,
    roles, projects and skills from the tailored version, every bullet on."""
    def roles(items: list[dict]) -> list[dict]:
        return [{"employer": r["employer"], "title": r["title"], "location": r["location"],
                 "start": r["start"], "end": r["end"],
                 "bullets": [{"text": b["text"], "skills": list(b.get("skills", [])),
                              "source": "tailored", "rank": 3, "in_master": True}
                             for b in r["bullets"]]} for r in items]
    return {"name": master.get("name", ""), "email": master.get("email", ""),
            "phone": master.get("phone", ""), "linkedin": master.get("linkedin", ""),
            "roles": roles(tailored.get("roles", [])),
            "projects": roles(tailored.get("projects", [])),
            "education": list(master.get("education", [])),
            "skill_groups": list(tailored.get("skill_groups", [])), "conflicts": []}


def tailored_counts(tailored: dict) -> dict:
    """What a tailored version did: bullets printed, how many kept word for
    word, reworded, or without a master original; keywords and covered."""
    bullets = [b for role in list(tailored.get("roles", [])) + list(tailored.get("projects", []))
               for b in role.get("bullets", [])]
    kept = sum(1 for b in bullets if b.get("original") and b["text"] == b["original"])
    unmatched = sum(1 for b in bullets if not b.get("original"))
    keywords = list(tailored.get("keywords", []))
    return {"bullets": len(bullets), "kept": kept, "reworded": len(bullets) - kept - unmatched,
            "unmatched": unmatched, "keywords": len(keywords),
            "covered": sum(1 for k in keywords if k.get("covered"))}


def letter_paragraphs(text: str) -> list[str]:
    """A cover letter's paragraphs: split on blank lines, spaces tidied, a
    single line break (a sign-off above the name) kept."""
    paragraphs = []
    for part in text.replace("\r\n", "\n").split("\n\n"):
        lines = [" ".join(line.split()) for line in part.split("\n")]
        lines = [line for line in lines if line]
        if lines:
            paragraphs.append("\n".join(lines))
    return paragraphs


def file_stem(*parts: str) -> str:
    """A file name from names: letters and digits only, parts joined with _
    ("Nolan Hughes", "Resume", "Acme Corp" -> NolanHughes_Resume_AcmeCorp)."""
    cleaned = ["".join(ch for ch in part if ch.isalnum()) for part in parts]
    return "_".join(c for c in cleaned if c) or "Resume"


# ---- project bank -----------------------------------------------------------

PROJECT_TEXT_FIELDS = {"company": "employer", "summary": "summary", "situation": "situation",
                       "task": "task", "action": "action", "result": "result",
                       "skills": "skills"}


def _text(value_) -> str:
    return "" if blank(value_) else str(value_).strip()


def project_detail(project: dict) -> dict:
    """The free detail score of one project (config.DETAIL_CHECKS): points
    out of 100, what's missing in plain words, and a level for its colour
    ("strong", "thin" or "weak")."""
    score, missing = 0, []
    for field, minimum, points, label in config.DETAIL_CHECKS:
        if field == "result_number":
            met = bool(re.search(r"\d", _text(project.get("result"))))
        elif field == "skills":
            met = len(skills_list(_text(project.get("skills")))) >= minimum
        else:
            met = len(_text(project.get(field))) >= minimum
        if met:
            score += points
        else:
            missing.append(label)
    level = ("strong" if score >= config.DETAIL_STRONG
             else "thin" if score >= config.DETAIL_THIN else "weak")
    return {"score": score, "missing": missing, "level": level}


def _abbreviates(short: str, words: list[str], first: bool = True) -> bool:
    """Whether short spells the words' starts in order ("fhr": Flint Hills
    Resources; "cpchem": Chevron Phillips CHEMical). A word may be skipped,
    except the first."""
    if not short:
        return True
    if not words:
        return False
    word = words[0]
    for k in range(min(len(word), len(short)), 0 if first else -1, -1):
        if word[:k] == short[:k] and _abbreviates(short[k:], words[1:], first=False):
            return True
    return False


def match_employer(name, employers: list[str]) -> str | None:
    """The employer in employers that name stands for: the same name, one
    containing the other, or an abbreviation of it ("FHR"); None when none
    fits."""
    name = _text(name)
    if not name:
        return None
    short = re.sub(r"[^a-z]", "", name.lower())
    for employer in employers:
        full = employer.lower()
        if name.lower() == full or name.lower() in full or full in name.lower():
            return employer
    for employer in employers:
        words = re.findall(r"[a-z]+", employer.lower())
        if short and _abbreviates(short, words):
            return employer
    return None


def parse_projects_text(text) -> list[dict]:
    """The projects in a projects spreadsheet's text (projects_text's
    blocks: "Project: …" then "Company: …", "Situation: …" lines, a field
    running on until the next one), as project-bank fields."""
    found = []
    for block in re.split(r"(?m)^(?=Project: )", _text(text)):
        if not block.startswith("Project: "):
            continue
        fields, current = {}, None
        for line in block.splitlines():
            label, _, rest = line.partition(": ")
            key = label.strip().lower()
            if key == "project" and "title" not in fields:
                fields["title"], current = rest.strip(), "title"
            elif key in PROJECT_TEXT_FIELDS and rest:
                current = PROJECT_TEXT_FIELDS[key]
                fields[current] = rest.strip()
            elif key == "rank" and rest:
                current = None
            elif current and current != "title":
                fields[current] = f"{fields[current]}\n{line}".strip()
        if fields.get("title"):
            found.append(fields)
    return found


def master_employers(master: dict | None) -> list[str]:
    """The employers on the master resume, in its order, once each."""
    return list(dict.fromkeys(r["employer"] for r in (master or {}).get("roles", [])
                              if r.get("employer")))


def import_projects(text, master: dict | None, known_titles) -> list[dict]:
    """The spreadsheet's projects not yet in the bank (by title), ready to
    add: the employer matched to the master's, work when it has one."""
    known = {str(t).strip().lower() for t in known_titles}
    employers = master_employers(master)
    out = []
    for fields in parse_projects_text(text):
        if fields["title"].lower() in known:
            continue
        employer = (match_employer(fields.get("employer"), employers)
                    or _text(fields.get("employer")) or None)
        out.append({**fields, "employer": employer, "kind": "work" if employer else "personal"})
        known.add(fields["title"].lower())
    return out


def _same_text(a, b) -> bool:
    return " ".join(_text(a).lower().split()) == " ".join(_text(b).lower().split())


def bullet_status(master: dict | None, text) -> str | None:
    """Where a bullet sits on the master: "on the master" (ticked), "in the
    pool", or None when it isn't there."""
    for role in list((master or {}).get("roles", [])) + list((master or {}).get("projects", [])):
        for bullet in role.get("bullets", []):
            if _same_text(bullet.get("text"), text):
                return "on the master" if bullet.get("in_master") else "in the pool"
    return None


def project_rank(strength) -> int:
    """A bullet's rank (1-5) from Claude's 1-10 strength for its project."""
    try:
        return max(1, min(config.BULLET_RANK_MAX, round(int(strength) / 2)))
    except (TypeError, ValueError):
        return 3


def add_to_master(master: dict, project: dict, text: str, rank: int) -> tuple[dict, str]:
    """The master with text added to its pool (unticked, source "project"):
    under the newest role at the project's employer, or for a personal
    project under the master project of that name (made when missing). Also
    returns where it went: "" when a work project's employer isn't on the
    master, "already" when the bullet is there."""
    out = copy.deepcopy(master)
    if bullet_status(out, text):
        return out, "already"
    bullet = {"text": " ".join(_text(text).split()),
              "skills": skills_list(_text(project.get("skills"))),
              "source": "project", "rank": rank, "in_master": False}
    if _text(project.get("employer")):
        roles = [r for r in roles_by_date(out.get("roles", []))
                 if _same_text(r.get("employer"), project["employer"])]
        if not roles:
            return out, ""
        role = roles[0]
        role.setdefault("bullets", []).append(bullet)
        return out, " — ".join(p for p in (role["employer"], role.get("title")) if p)
    name = _text(project.get("title"))
    target = next((p for p in out.setdefault("projects", []) if _same_text(p.get("employer"), name)),
                  None)
    if target is None:
        target = {"employer": name, "title": "", "location": "", "start": "", "end": "",
                  "bullets": []}
        out["projects"].append(target)
    target.setdefault("bullets", []).append(bullet)
    return out, name


def bullet_style(master: dict | None) -> dict:
    """How the master's printed bullets read, for Claude to match: a few
    samples from the newest role and their usual and longest length."""
    printed = _printed(master or {})
    newest = roles_by_date((master or {}).get("roles", []))
    samples = [b["text"] for b in (newest[0]["bullets"] if newest else []) if b.get("in_master")]
    lengths = sorted(len(t) for t in printed)
    return {"samples": samples[:4],
            "typical": lengths[len(lengths) // 2] if lengths else 200,
            "longest": lengths[-1] if lengths else 300}


def contact_line(master: dict) -> str:
    """The resume's contact line: email, phone and LinkedIn, dotted."""
    return " • ".join(v for v in (master.get("email"), master.get("phone"),
                                  master.get("linkedin")) if v)


def long_date(d: date) -> str:
    """October 19, 2026: how a letter is dated."""
    return f"{d:%B} {d.day}, {d.year}"


MONTHS = {name.lower(): n for n, name in enumerate(calendar.month_abbr) if name}
LINE_CHARS = 75                      # characters a bullet's line holds when the template can't say
EMPLOYER_LINES = 1                   # the employer line above its roles
ROLE_LINES = 1                       # a role's title-and-dates line


def parse_month(text) -> date | None:
    """'Jan 2025' or 'January 2025' as the first of that month; None otherwise."""
    parts = str(text or "").strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    month = MONTHS.get(parts[0][:3].lower())
    return date(int(parts[1]), month, 1) if month else None


def roles_by_date(roles: list[dict]) -> list[dict]:
    """Roles newest first by start month, when every start reads as one
    ("Jan 2025"); otherwise in the order given. A side role held alongside
    another lands where its start date puts it."""
    starts = [parse_month(r.get("start")) for r in roles]
    if not roles or any(s is None for s in starts):
        return list(roles)
    order = sorted(range(len(roles)), key=lambda i: starts[i], reverse=True)
    return [roles[i] for i in order]


def _printed(master: dict) -> list[str]:
    return [b["text"] for role in list(master.get("roles", [])) + list(master.get("projects", []))
            for b in role.get("bullets", []) if b.get("in_master")]


def printed_roles(items: list[dict]) -> list[dict]:
    """The master's roles (or projects) as they print: in_master bullets
    only, and only the roles that have one."""
    out = []
    for role in items:
        bullets = [b for b in role.get("bullets", []) if b.get("in_master")]
        if bullets:
            out.append({**role, "bullets": bullets})
    return out


def master_budget(master: dict) -> dict:
    """What the printed master holds, column by column: the roles' bullets
    and their characters (the left column of the page) and the projects'
    (the right), the one-page budget a tailored version has to fit."""
    def measure(items: list[dict]) -> dict:
        texts = [b["text"] for role in printed_roles(items) for b in role["bullets"]]
        return {"bullets": len(texts), "characters": sum(len(t) for t in texts)}
    return {"roles": measure(list(master.get("roles", []))),
            "projects": measure(list(master.get("projects", [])))}


def column_lines(roles: list[dict], line_chars: int = LINE_CHARS) -> int:
    """About how many lines a column of roles takes: an employer line above
    each run of roles there, a title line each, and every bullet's lines at
    line_chars characters a line. Every bullet given counts (the master's
    go through printed_roles first)."""
    lines, last = 0, None
    for role in roles:
        bullets = role.get("bullets", [])
        if not bullets:
            continue
        if role.get("employer") != last:
            lines += EMPLOYER_LINES
            last = role.get("employer")
        lines += ROLE_LINES + sum(math.ceil(len(b["text"]) / line_chars) for b in bullets)
    return lines


def fit_column(tailored: dict, master: dict, line_chars: int = LINE_CHARS) -> dict:
    """The tailored version cut to the master's experience column (the
    master's printed roles fit the page; its lines are the yardstick): while
    the tailored roles need more, the last bullet goes from the role with
    the most (its least relevant, the way Claude orders them), and changes
    says so. The first role keeps a bullet; a role left with none goes."""
    out = copy.deepcopy(tailored)
    out.setdefault("changes", [])
    roles = out.setdefault("roles", [])
    limit = column_lines(printed_roles(list(master.get("roles", []))), line_chars)
    while column_lines(roles, line_chars) > limit:
        spare = [r for n, r in enumerate(roles) if len(r.get("bullets", [])) > (n == 0)]
        if not spare:
            break
        role = max(spare, key=lambda r: len(r["bullets"]))
        dropped = role["bullets"].pop()
        out["changes"].append(f"Left off the last bullet under {role.get('employer', '')} "
                              f"(“{shorten(dropped['text'], 60)}”): the experience column "
                              "was full.")
        if not role["bullets"]:
            roles.remove(role)
    return out


def match_endings(tailored: dict, master: dict) -> dict:
    """The tailored bullets ending as the master's printed ones do: with a
    full stop when most of the master's have one, without when most don't."""
    printed = _printed(master)
    if not printed:
        return tailored
    with_stop = sum(t.rstrip().endswith(".") for t in printed) * 2 > len(printed)
    out = copy.deepcopy(tailored)
    for role in list(out.get("roles", [])) + list(out.get("projects", [])):
        for bullet in role.get("bullets", []):
            text = bullet["text"].rstrip()
            if with_stop and text and not text.endswith((".", "!", "?")):
                text += "."
            elif not with_stop:
                text = text.rstrip(".")
            bullet["text"] = text
    return out


def lead_table(leads: pd.DataFrame, today: date) -> pd.DataFrame:
    """Leads as a computer's table shows them, one row each in the leads'
    order: fit, title, company, where, pay in thousands (with ~ when the
    daily review estimated it), source, the day it was found, and the
    posting link."""
    rows = []
    for lead in leads.itertuples():
        pay = salary_short(lead.salary_min, lead.salary_max)
        if pay and value(lead.pay_source) == "estimated":
            pay = f"~{pay}"
        rows.append({"fit": None if blank(lead.fit_score) else float(lead.fit_score),
                     "title": lead.title, "company": lead.company,
                     "where": " · ".join(place(lead.location, lead.work_mode)),
                     "pay": pay or "—", "source": value(lead.source) or "",
                     "found": lead.found_on, "posting": job_link(lead.job_url)})
    return pd.DataFrame(rows, columns=["fit", "title", "company", "where", "pay", "source",
                                       "found", "posting"])


def salary_short(low, high) -> str:
    """A pay range in thousands for a narrow column: "$135k–$160k"."""
    def k(amount) -> str:
        return f"${round(float(amount) / 1000):g}k"
    low, high = value(low), value(high)
    if low is not None and high is not None:
        return k(low) if low == high else f"{k(low)}–{k(high)}"
    if low is not None:
        return f"{k(low)}+"
    if high is not None:
        return f"up to {k(high)}"
    return ""


def place(location, work_mode) -> list[str]:
    """Location and work mode for a header: the mode capitalised, and left
    out when it only repeats the location ("Remote · remote")."""
    where = "" if blank(location) else str(location).strip()
    mode = "" if blank(work_mode) else str(work_mode).strip().capitalize()
    if where and mode and where.lower() == mode.lower():
        mode = ""
    return [part for part in (where, mode) if part]
