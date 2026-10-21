"""Every database read and write the app makes.

Reads return DataFrames (or a dict for one row). Writes take plain Python
values; dates are computed in Python ("today" comes from today() below, in
America/Chicago) and passed in, never current_date or now() in SQL.

One connection per process, in autocommit, shared by every page. Neon
suspends idle databases, so a connection idle for PING_AFTER_IDLE_S or more
is pinged before use and replaced if it has died. The first connection a
process opens also runs schema.sql -- every statement in it is "if not
exists" -- so a brand-new database gets its tables the first time the app
opens, with nothing to run by hand.
"""

import json
import sys
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import db  # noqa: E402
import logic  # noqa: E402
import resume_schema  # noqa: E402

PING_AFTER_IDLE_S = 20

_lock = threading.RLock()
_conn: psycopg.Connection | None = None
_last_used = 0.0
_schema_ready = False


class InUse(Exception):
    """A delete refused because other rows still point at this one."""


def today() -> date:
    return datetime.now(db.LOCAL_TZ).date()


# ---- connection -------------------------------------------------------------

# Changes to tables that already existed on the live database, each safe to
# run again (schema.sql only creates what's missing). _connection() runs them
# after schema.sql; leads.py runs them over HTTPS, one statement at a time.
MIGRATIONS = [
    # 2026-10: fit scores to one decimal, with the category ratings behind them.
    "alter table job_leads add column if not exists fit_detail jsonb",
    """do $$ begin
        if (select data_type from information_schema.columns
            where table_name = 'job_leads' and column_name = 'fit_score') <> 'numeric' then
            alter table job_leads alter column fit_score type numeric(3,1);
        end if;
    end $$""",
    # 2026-10: where a lead's pay came from; unknown pay is left out of the score.
    "alter table job_leads add column if not exists pay_source text "
    "check (pay_source in ('listed', 'estimated'))",
    "alter table job_leads add column if not exists pay_note text",
    "update job_leads set pay_source = 'listed' where pay_source is null "
    "and (salary_min is not null or salary_max is not null)",
    # 2026-10: why and when a lead was dismissed; companies the review skips.
    "alter table job_leads add column if not exists dismiss_reason text",
    "alter table job_leads add column if not exists dismissed_on date",
    # 2026-10: "not enough experience" joins the dismiss reasons: the CHECK is
    # remade (whatever it was called), so the live table takes the new list.
    """do $$ declare found record; begin
        for found in select conname from pg_constraint
            where conrelid = 'job_leads'::regclass and contype = 'c'
              and pg_get_constraintdef(oid) like '%dismiss_reason%' loop
            execute format('alter table job_leads drop constraint %I', found.conname);
        end loop;
        alter table job_leads add constraint job_leads_dismiss_reason_check
            check (dismiss_reason in ('wrong role', 'not enough experience', 'location', 'pay',
                                      'company', 'already applied', 'other'));
    end $$""",
    "alter table job_profile add column if not exists skip_companies text",
    # 2026-10: the job posting's text on an application, for tailoring the resume.
    "alter table applications add column if not exists posting text",
    # 2026-10: where to apply on the employer's own site, looked up when a lead is added.
    "alter table applications add column if not exists apply_url text",
    "alter table applications add column if not exists apply_note text",
]


def _connection() -> psycopg.Connection:
    global _conn, _last_used, _schema_ready
    if _conn is None or _conn.closed:
        _conn = db.connect(autocommit=True)
        if not _schema_ready:
            _conn.execute((ROOT / "schema.sql").read_text(encoding="utf-8"))
            for statement in MIGRATIONS:
                _conn.execute(statement)
            _schema_ready = True
    elif time.monotonic() - _last_used >= PING_AFTER_IDLE_S:
        try:
            _conn.execute("select 1")
        except psycopg.Error:
            reset_connection()
            _conn = db.connect(autocommit=True)
    _last_used = time.monotonic()
    return _conn


def reset_connection() -> None:
    """Drop the shared connection; the next call opens a fresh one."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except psycopg.Error:
            pass
    _conn = None


_over_http = False


def use_http() -> None:
    """Send every query over Neon's HTTPS endpoint (db.HttpCursor) instead of
    a Postgres connection: for the daily review's cloud session, which can't
    open one. Statements then commit one at a time, and schema.sql isn't run
    (the app has made the tables)."""
    global _over_http
    _over_http = True


@contextmanager
def _cursor(row_factory=None):
    if _over_http:
        yield db.HttpCursor(row_factory)
        return
    with _lock:
        conn = _connection()
        with conn.cursor(row_factory=row_factory) as cur:
            yield cur


@contextmanager
def _transaction():
    """All-or-nothing: every statement inside commits together or not at all.
    Nests (as a savepoint) inside another _transaction(). Over HTTPS each
    statement commits on its own."""
    if _over_http:
        yield db.HttpCursor()
        return
    with _lock:
        conn = _connection()
        with conn.transaction(), conn.cursor() as cur:
            yield cur


def migrate() -> None:
    """Bring an existing database's tables up to date (MIGRATIONS), for the
    HTTPS path, which never runs schema.sql."""
    with _cursor() as cur:
        for statement in MIGRATIONS:
            cur.execute(statement)


def _read(query: str, params=None) -> pd.DataFrame:
    with _cursor() as cur:
        cur.execute(query, params)
        columns = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=columns)


def _one(query: str, params=None) -> dict | None:
    with _cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchone()


def _clean(value):
    """Strip text; blank text becomes NULL."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _insert(table: str, key: str, fields: dict) -> int:
    cleaned = {k: _clean(v) for k, v in fields.items()}
    query = sql.SQL("insert into {} ({}) values ({}) returning {}").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, cleaned)),
        sql.SQL(", ").join(map(sql.Placeholder, cleaned)),
        sql.Identifier(key),
    )
    with _cursor() as cur:
        cur.execute(query, cleaned)
        return cur.fetchone()[0]


def _update(table: str, key: str, key_value: int, fields: dict, allowed: set[str]) -> None:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"cannot update {sorted(unknown)} on {table}")
    if not fields:
        return
    cleaned = {k: _clean(v) for k, v in fields.items()}
    query = sql.SQL("update {} set {} where {} = {}").format(
        sql.Identifier(table),
        sql.SQL(", ").join(
            sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder(k)) for k in cleaned
        ),
        sql.Identifier(key),
        sql.Placeholder("_key"),
    )
    with _cursor() as cur:
        cur.execute(query, {**cleaned, "_key": key_value})


def _delete(table: str, key: str, key_value: int, in_use_message: str = "") -> None:
    query = sql.SQL("delete from {} where {} = %s").format(
        sql.Identifier(table), sql.Identifier(key))
    try:
        with _cursor() as cur:
            cur.execute(query, (key_value,))
    except psycopg.errors.IntegrityError as exc:
        # ForeignKeyViolation or RestrictViolation, depending on the Postgres version.
        raise InUse(in_use_message or "other records still use this one") from exc


# ---- companies --------------------------------------------------------------

COMPANY_FIELDS = {"name", "website", "industry", "location", "notes"}


def companies() -> pd.DataFrame:
    return _read("""
        select c.*, count(a.application_id) as applications
        from companies c left join applications a using (company_id)
        group by c.company_id
        order by lower(c.name)
    """)


def add_company(name: str, on: date, **fields) -> int:
    return _insert("companies", "company_id", {"name": name, "created_on": on, **fields})


def company_id_for(name: str, on: date) -> int:
    """The company with this name, whatever its capitalisation, made if new."""
    name = name.strip()
    with _cursor() as cur:
        cur.execute("""
            insert into companies (name, created_on) values (%s, %s)
            on conflict ((lower(name))) do nothing
            returning company_id
        """, (name, on))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("select company_id from companies where lower(name) = lower(%s)", (name,))
        return cur.fetchone()[0]


def update_company(company_id: int, **fields) -> None:
    _update("companies", "company_id", company_id, fields, COMPANY_FIELDS)


def delete_company(company_id: int) -> None:
    _delete("companies", "company_id", company_id,
            "this company still has applications; delete those first")


# ---- contacts ---------------------------------------------------------------

CONTACT_FIELDS = {"company_id", "name", "title", "kind", "email", "phone", "linkedin",
                  "notes", "last_contacted_on"}


def contacts() -> pd.DataFrame:
    return _read("""
        select ct.*, co.name as company
        from contacts ct left join companies co using (company_id)
        order by lower(ct.name)
    """)


def add_contact(name: str, on: date, **fields) -> int:
    return _insert("contacts", "contact_id", {"name": name, "created_on": on, **fields})


def update_contact(contact_id: int, **fields) -> None:
    _update("contacts", "contact_id", contact_id, fields, CONTACT_FIELDS)


def delete_contact(contact_id: int) -> None:
    _delete("contacts", "contact_id", contact_id)


# ---- applications -----------------------------------------------------------

APPLICATION_FIELDS = {"company_id", "role", "job_url", "location", "work_mode", "salary_min",
                      "salary_max", "source", "applied_on", "next_action", "next_action_on",
                      "contact_id", "notes", "posting", "apply_url", "apply_note"}

_APPLICATIONS = """
    select a.*, co.name as company,
           coalesce((select max(e.happened_on) from application_events e
                     where e.application_id = a.application_id),
                    a.created_on) as last_update_on,
           (select count(*) from interviews i
            where i.application_id = a.application_id) as interviews
    from applications a join companies co using (company_id)
"""


def applications() -> pd.DataFrame:
    """Every application, newest first, with its company name, the date of its
    latest update and how many interviews it has."""
    return _read(_APPLICATIONS + """
        order by coalesce(a.applied_on, a.created_on) desc, a.application_id desc
    """)


def application(application_id: int) -> dict | None:
    return _one(_APPLICATIONS + " where a.application_id = %s", (application_id,))


def add_application(company_id: int, role: str, status: str, on: date,
                    applied_on: date | None = None, **fields) -> int:
    """A new application and its first history row, together.

    Anything past "saved" has been applied for, so applied_on defaults to
    `on`. The first history row is dated applied_on when there is one -- an
    application entered late, or imported, keeps its real age.
    """
    unknown = set(fields) - APPLICATION_FIELDS
    if unknown:
        raise ValueError(f"unknown application fields {sorted(unknown)}")
    if status != "saved" and applied_on is None:
        applied_on = on
    with _transaction():
        application_id = _insert("applications", "application_id", {
            "company_id": company_id, "role": role, "status": status,
            "applied_on": applied_on, "created_on": on, **fields,
        })
        _insert("application_events", "event_id", {
            "application_id": application_id, "status": status,
            "happened_on": applied_on or on,
        })
    return application_id


def set_status(application_id: int, status: str, on: date, note: str | None = None) -> None:
    """Log an update: the (possibly unchanged) status, the day, and a note.

    Any update resets the follow-up clock, so "Emailed the recruiter" with
    the status unchanged is a useful entry.
    """
    with _transaction() as cur:
        cur.execute("""
            update applications
            set status = %(status)s,
                applied_on = case when %(status)s <> 'saved' and applied_on is null
                                  then %(on)s else applied_on end
            where application_id = %(id)s
        """, {"status": status, "on": on, "id": application_id})
        cur.execute("""
            insert into application_events (application_id, status, happened_on, note)
            values (%s, %s, %s, %s)
        """, (application_id, status, on, _clean(note)))


def update_application(application_id: int, **fields) -> None:
    _update("applications", "application_id", application_id, fields, APPLICATION_FIELDS)


def delete_application(application_id: int) -> None:
    """Deletes its history and interviews with it."""
    _delete("applications", "application_id", application_id)


def events(application_id: int) -> pd.DataFrame:
    return _read("""
        select * from application_events where application_id = %s
        order by happened_on, event_id
    """, (application_id,))


def all_events() -> pd.DataFrame:
    return _read("select * from application_events order by happened_on, event_id")


def import_applications(rows: list[dict], on: date) -> tuple[int, int]:
    """Add rows from logic.map_import, all or none; (added, skipped).

    A row matching an existing application -- same company, role and applied
    date -- is skipped, so importing the same file twice adds nothing.
    """
    added = skipped = 0
    with _transaction() as cur:
        cur.execute("""
            select lower(co.name), lower(a.role), a.applied_on
            from applications a join companies co using (company_id)
        """)
        existing = set(cur.fetchall())
        for row in rows:
            row = dict(row)
            company = row.pop("company")
            key = (company.strip().lower(), row["role"].strip().lower(), row.get("applied_on"))
            if key in existing:
                skipped += 1
                continue
            company_id = company_id_for(company, on)
            add_application(company_id, row.pop("role"), row.pop("status"), on,
                            applied_on=row.pop("applied_on", None), **row)
            existing.add(key)
            added += 1
    return added, skipped


# ---- interviews -------------------------------------------------------------

INTERVIEW_FIELDS = {"scheduled_on", "start_time", "round", "format", "interviewers",
                    "prep_notes", "outcome_notes", "rating"}


def interviews(application_id: int | None = None) -> pd.DataFrame:
    """Interviews with their company, role and application status, in date order."""
    where = "" if application_id is None else "where i.application_id = %(id)s"
    return _read(f"""
        select i.*, co.name as company, a.role, a.status
        from interviews i
        join applications a using (application_id)
        join companies co using (company_id)
        {where}
        order by i.scheduled_on, i.start_time nulls first, i.interview_id
    """, {"id": application_id})


def add_interview(application_id: int, scheduled_on: date, **fields) -> int:
    unknown = set(fields) - INTERVIEW_FIELDS
    if unknown:
        raise ValueError(f"unknown interview fields {sorted(unknown)}")
    return _insert("interviews", "interview_id", {
        "application_id": application_id, "scheduled_on": scheduled_on, **fields})


def update_interview(interview_id: int, **fields) -> None:
    _update("interviews", "interview_id", interview_id, fields, INTERVIEW_FIELDS)


def delete_interview(interview_id: int) -> None:
    _delete("interviews", "interview_id", interview_id)


# ---- career log -------------------------------------------------------------

CAREER_FIELDS = {"kind", "title", "details", "happened_on", "tags"}


def career_entries(kind: str | None = None) -> pd.DataFrame:
    where = "" if kind is None else "where kind = %(kind)s"
    return _read(f"""
        select * from career_entries {where}
        order by happened_on desc, entry_id desc
    """, {"kind": kind})


def add_career_entry(kind: str, title: str, happened_on: date, **fields) -> int:
    return _insert("career_entries", "entry_id",
                   {"kind": kind, "title": title, "happened_on": happened_on, **fields})


def update_career_entry(entry_id: int, **fields) -> None:
    _update("career_entries", "entry_id", entry_id, fields, CAREER_FIELDS)


def delete_career_entry(entry_id: int) -> None:
    _delete("career_entries", "entry_id", entry_id)


# ---- job history ------------------------------------------------------------

POSITION_FIELDS = {"employer", "title", "started_on", "ended_on", "base_salary", "bonus",
                   "other_comp", "notes"}


def positions() -> pd.DataFrame:
    return _read("select * from positions order by started_on desc, position_id desc")


def add_position(employer: str, title: str, started_on: date, **fields) -> int:
    return _insert("positions", "position_id",
                   {"employer": employer, "title": title, "started_on": started_on, **fields})


def update_position(position_id: int, **fields) -> None:
    _update("positions", "position_id", position_id, fields, POSITION_FIELDS)


def delete_position(position_id: int) -> None:
    _delete("positions", "position_id", position_id)


# ---- job search profile -----------------------------------------------------

PROFILE_FIELDS = {"target_roles", "locations", "work_modes", "min_salary", "must_haves",
                  "nice_to_haves", "deal_breakers", "about_me", "skip_companies"}


def job_profile() -> dict | None:
    return _one("select * from job_profile where profile_id = 1")


def save_job_profile(on: date, **fields) -> None:
    """Create or replace what you're looking for (there is only one)."""
    unknown = set(fields) - PROFILE_FIELDS
    if unknown:
        raise ValueError(f"unknown profile fields {sorted(unknown)}")
    cleaned = {k: _clean(fields.get(k)) for k in sorted(PROFILE_FIELDS)}
    columns = ["profile_id", *cleaned, "updated_on"]
    query = sql.SQL("""
        insert into job_profile ({columns}) values ({values})
        on conflict (profile_id) do update set {updates}
    """).format(
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        values=sql.SQL(", ").join(map(sql.Placeholder, columns)),
        updates=sql.SQL(", ").join(
            sql.SQL("{0} = excluded.{0}").format(sql.Identifier(c)) for c in columns[1:]),
    )
    with _cursor() as cur:
        cur.execute(query, {"profile_id": 1, **cleaned, "updated_on": on})


# ---- job leads --------------------------------------------------------------

def job_leads(status: str | None = None) -> pd.DataFrame:
    """Leads, best fit first (unscored last), then newest."""
    where = "" if status is None else "where status = %(status)s"
    return _read(f"""
        select * from job_leads {where}
        order by fit_score desc nulls last, found_on desc, lead_id desc
    """, {"status": status})


def lead(lead_id: int) -> dict | None:
    return _one("select * from job_leads where lead_id = %s", (lead_id,))


def lead_stats(marks: tuple[float, ...] = config.HOME_FIT_MARKS) -> dict:
    """How the lead pipeline stands: how many postings the review has scored
    in all (reviewed), their average fit, and how many still sit new in the
    inbox at or above each mark (waiting, in the marks' order)."""
    counts = ", ".join(
        f"count(*) filter (where status = 'new' and fit_score >= %s) as waiting_{n}"
        for n in range(len(marks)))
    row = _one(f"""
        select count(*) as reviewed, avg(fit_score) as average_fit{", " + counts if marks else ""}
        from job_leads
    """, tuple(marks)) or {}
    return {"reviewed": int(row.get("reviewed") or 0),
            "average_fit": None if row.get("average_fit") is None else float(row["average_fit"]),
            "waiting": [int(row.get(f"waiting_{n}") or 0) for n in range(len(marks))]}


def leads_found(on: date) -> pd.DataFrame:
    """The leads one daily review added (found that day, still new), best
    fit first: what its digest reports."""
    return _read("""
        select * from job_leads where found_on = %s and status = 'new'
        order by fit_score desc nulls last, lead_id
    """, (on,))


def add_leads(leads: list[dict], on: date) -> tuple[int, int]:
    """Add cleaned leads (logic.clean_lead), all or none; (added, skipped).

    A lead whose dedupe_key is already stored -- the same job seen before,
    from any site -- is skipped, whatever became of the first one.
    """
    added = 0
    with _transaction() as cur:
        for row in leads:
            row = {k: _clean(v) for k, v in row.items()}
            if isinstance(row.get("fit_detail"), dict):
                row["fit_detail"] = json.dumps(row["fit_detail"])   # sent as text, cast below
            columns = [*row, "found_on", "status"]
            values = [sql.SQL("{}::jsonb").format(sql.Placeholder(c)) if c == "fit_detail"
                      else sql.Placeholder(c) for c in columns]
            cur.execute(sql.SQL("""
                insert into job_leads ({}) values ({})
                on conflict (dedupe_key) do nothing
            """).format(sql.SQL(", ").join(map(sql.Identifier, columns)),
                        sql.SQL(", ").join(values)),
                {**row, "found_on": on, "status": "new"})
            added += cur.rowcount
    return added, len(leads) - added


def known_lead_keys() -> set[str]:
    with _cursor() as cur:
        cur.execute("select dedupe_key from job_leads")
        return {row[0] for row in cur.fetchall()}


def set_lead_status(lead_id: int, status: str, reason: str | None = None,
                    on: date | None = None) -> None:
    """Dismiss a lead (with why, and when), or bring a dismissed one back as
    new, which clears both."""
    if status != "dismissed":
        reason, on = None, None
    with _cursor() as cur:
        cur.execute("""
            update job_leads set status = %s, dismiss_reason = %s, dismissed_on = %s
            where lead_id = %s
        """, (status, reason, on, lead_id))


def dismissed_recently(since: date, limit: int = config.DISMISSAL_LIMIT) -> pd.DataFrame:
    """Leads dismissed on or after `since`, latest first: what the daily
    review reads as a hint of what the owner doesn't want."""
    return _read("""
        select title, company, location, dismiss_reason, dismissed_on from job_leads
        where status = 'dismissed' and dismissed_on >= %s
        order by dismissed_on desc, lead_id desc limit %s
    """, (since, limit))


def strong_leads_waiting(today: date) -> pd.DataFrame:
    """Strong leads from earlier days still sitting new in the inbox (not yet
    stale), best first: the digest's reminder."""
    return _read("""
        select * from job_leads
        where status = 'new' and found_on < %s and found_on > %s and fit_score >= %s
        order by fit_score desc, found_on desc, lead_id
    """, (today, today - timedelta(days=config.LEAD_STALE_DAYS), config.STRONG_FIT))


def move_lead_to_applications(lead_id: int, on: date) -> int:
    """The lead as a new "saved" application (its company made if new), the
    fit score and reason in its notes; the lead is marked moved."""
    with _transaction() as cur:
        row = lead(lead_id)
        notes = None
        if row["fit_score"] is not None:
            notes = f"Fit {logic.fit_text(row['fit_score'])}/10" + (
                f": {row['fit_reason']}" if row["fit_reason"] else "")
        if row["pay_source"] == "estimated":
            estimate = "Pay is the daily review's estimate" + (
                f" ({row['pay_note']})." if row["pay_note"] else ".")
            notes = f"{notes}\n{estimate}" if notes else estimate
        application_id = add_application(
            company_id_for(row["company"], on), row["title"], "saved", on,
            job_url=row["job_url"], location=row["location"], work_mode=row["work_mode"],
            salary_min=row["salary_min"], salary_max=row["salary_max"],
            source=row["source"], notes=notes)
        cur.execute("""
            update job_leads set status = 'moved', application_id = %s where lead_id = %s
        """, (application_id, lead_id))
    return application_id


# ---- master resume ----------------------------------------------------------

def resume_master() -> dict | None:
    """The master resume as data (resume_schema.Resume as a dict), with
    template_source_id and updated_on; None before the first build."""
    return _one("select content, template_source_id, updated_on from resume_master "
                "where profile_id = 1")


def save_resume_master(content: dict, on: date) -> None:
    """Create or replace the master resume's data (the template choice stays)."""
    with _cursor() as cur:
        cur.execute("""
            insert into resume_master (profile_id, content, template_source_id, updated_on)
            values (1, %s::jsonb, null, %s)
            on conflict (profile_id) do update
                set content = excluded.content, updated_on = excluded.updated_on
        """, (json.dumps(content), on))


def tailored_versions(application_id: int) -> pd.DataFrame:
    """Every tailored version of one application's resume, newest first
    (tailor_id, version, notes, model, created_on)."""
    return _read("""
        select tailor_id, version, notes, model, created_on from tailored_resumes
        where application_id = %s order by version desc
    """, (application_id,))


def tailored(tailor_id: int) -> dict | None:
    """One tailored version with its content (resume_schema.Tailored as a dict)."""
    return _one("select * from tailored_resumes where tailor_id = %s", (tailor_id,))


def add_tailored(application_id: int, content: dict, notes: str | None, model: str,
                 on: date) -> int:
    """A new version of the application's tailored resume, numbered after the last."""
    with _cursor() as cur:
        cur.execute("""
            insert into tailored_resumes (application_id, version, content, notes, model,
                                          created_on)
            select %s, coalesce(max(version), 0) + 1, %s::jsonb, %s, %s, %s
            from tailored_resumes where application_id = %s
            returning tailor_id
        """, (application_id, json.dumps(content), _clean(notes), model, on, application_id))
        return cur.fetchone()[0]


def save_tailored(tailor_id: int, content: dict) -> None:
    """Replace a version's content after the owner edits it."""
    with _cursor() as cur:
        cur.execute("update tailored_resumes set content = %s::jsonb where tailor_id = %s",
                    (json.dumps(content), tailor_id))


def delete_tailored(tailor_id: int) -> None:
    _delete("tailored_resumes", "tailor_id", tailor_id)


def set_resume_template(source_id: int | None, on: date) -> None:
    """Which uploaded Word file the export is modelled on (None: none)."""
    with _cursor() as cur:
        cur.execute("""
            insert into resume_master (profile_id, content, template_source_id, updated_on)
            values (1, %s::jsonb, %s, %s)
            on conflict (profile_id) do update set template_source_id = excluded.template_source_id
        """, (json.dumps(resume_schema.empty()), source_id, on))


def resume_template() -> bytes | None:
    """The Word file the export is modelled on, or None."""
    row = _one("""
        select s.bytes from resume_master m join resume_sources s on s.source_id = m.template_source_id
        where m.profile_id = 1 and s.bytes is not null
    """)
    return None if row is None else bytes(row["bytes"])


def resume_sources() -> pd.DataFrame:
    """The uploaded files, newest first: id, filename, kind, uploaded_on, how
    much text each gave, and whether the file itself is kept."""
    return _read("""
        select source_id, filename, kind, uploaded_on, length(text) as chars,
               bytes is not null as has_file
        from resume_sources order by uploaded_on desc, source_id desc
    """)


def resume_source_texts() -> dict[str, str]:
    """What Claude reads: every source's text, keyed by kind (several of a
    kind are joined, newest first)."""
    frame = _read("select kind, text from resume_sources order by uploaded_on desc, source_id desc")
    texts: dict[str, str] = {}
    for row in frame.itertuples(index=False):
        texts[row.kind] = (texts[row.kind] + "\n\n" + row.text) if row.kind in texts else row.text
    return texts


def add_resume_source(filename: str, kind: str, text: str, data: bytes | None, on: date) -> int:
    """Keep an uploaded file's text (and the file itself for a Word resume);
    a file of the same name replaces the earlier copy."""
    with _transaction() as cur:
        cur.execute("delete from resume_sources where lower(filename) = lower(%s)", (filename,))
        cur.execute("""
            insert into resume_sources (filename, kind, text, bytes, uploaded_on)
            values (%s, %s, %s, %s, %s) returning source_id
        """, (filename.strip(), kind, text, data, on))
        return cur.fetchone()[0]


def delete_resume_source(source_id: int) -> None:
    with _cursor() as cur:
        cur.execute("delete from resume_sources where source_id = %s", (source_id,))


def log_ai_usage(kind: str, model: str, input_tokens: int, output_tokens: int,
                 cost_usd: float, on: date) -> None:
    with _cursor() as cur:
        cur.execute("""
            insert into ai_usage (kind, model, input_tokens, output_tokens, cost_usd, happened_on)
            values (%s, %s, %s, %s, %s, %s)
        """, (kind, model, input_tokens, output_tokens, cost_usd, on))


def ai_usage_since(since: date) -> tuple[int, float]:
    """(calls, dollars) spent on Claude from a date on."""
    row = _one("select count(*) as calls, coalesce(sum(cost_usd), 0) as cost from ai_usage "
               "where happened_on >= %s", (since,))
    return int(row["calls"]), float(row["cost"])


# ---- settings ---------------------------------------------------------------

def get_setting(key: str, default: str | None = None) -> str | None:
    """A saved app setting (e.g. "theme"), or the default when unset."""
    row = _one("select value from settings where key = %s", (key,))
    return default if row is None else row["value"]


def set_setting(key: str, value: str) -> None:
    with _cursor() as cur:
        cur.execute("""
            insert into settings (key, value) values (%s, %s)
            on conflict (key) do update set value = excluded.value
        """, (key, value))
