"""data.py against a real (throwaway) Postgres with the real schema."""

from datetime import date, time

import psycopg
import pytest

import config
import data
import logic

TODAY = date(2026, 10, 14)


@pytest.fixture(autouse=True)
def _db(database):
    return database


def test_company_names_are_matched_whatever_the_capitalisation():
    first = data.company_id_for("Acme", TODAY)
    assert data.company_id_for("  acme ", TODAY) == first
    assert data.company_id_for("Beta", TODAY) != first
    assert data.companies()["name"].tolist() == ["Acme", "Beta"]


def test_a_new_application_starts_its_history():
    acme = data.company_id_for("Acme", TODAY)
    app_id = data.add_application(acme, " Analyst ", "applied", TODAY,
                                  applied_on=date(2026, 10, 1), source="", salary_min=90000)
    app = data.application(app_id)
    assert (app["role"], app["source"], app["salary_min"]) == ("Analyst", None, 90000)
    assert app["last_update_on"] == date(2026, 10, 1)
    history = data.events(app_id)
    assert history[["status", "happened_on"]].values.tolist() == [["applied", date(2026, 10, 1)]]


def test_applied_on_defaults_to_today_past_saved_and_stays_empty_while_saved():
    acme = data.company_id_for("Acme", TODAY)
    assert data.application(data.add_application(acme, "A", "applied", TODAY))["applied_on"] \
        == TODAY
    saved = data.add_application(acme, "B", "saved", TODAY)
    assert data.application(saved)["applied_on"] is None
    data.set_status(saved, "applied", date(2026, 10, 15), note="Sent")
    app = data.application(saved)
    assert (app["status"], app["applied_on"], app["last_update_on"]) == (
        "applied", date(2026, 10, 15), date(2026, 10, 15))
    assert data.events(saved)["note"].tolist()[-1] == "Sent"


def test_update_refuses_unknown_columns():
    acme = data.company_id_for("Acme", TODAY)
    app_id = data.add_application(acme, "A", "applied", TODAY)
    data.update_application(app_id, next_action="Call", next_action_on=TODAY)
    assert data.application(app_id)["next_action"] == "Call"
    with pytest.raises(ValueError):
        data.update_application(app_id, status="offer")      # status goes through set_status
    with pytest.raises(ValueError):
        data.add_application(acme, "B", "applied", TODAY, salary=1)


def test_a_company_with_applications_cannot_be_deleted():
    acme = data.company_id_for("Acme", TODAY)
    app_id = data.add_application(acme, "A", "applied", TODAY)
    data.add_interview(app_id, TODAY)
    with pytest.raises(data.InUse):
        data.delete_company(acme)
    data.delete_application(app_id)                 # takes its history and interviews along
    assert data.all_events().empty and data.interviews().empty
    data.delete_company(acme)
    assert data.companies().empty


def test_every_configured_value_is_allowed_by_the_schema_and_nothing_else():
    acme = data.company_id_for("Acme", TODAY)
    for status in config.STATUSES:
        data.add_application(acme, status, status, TODAY)
    for mode in config.WORK_MODES:
        data.add_application(acme, mode, "saved", TODAY, work_mode=mode)
    for kind in config.CONTACT_KINDS:
        data.add_contact(kind, TODAY, kind=kind)
    for kind in config.CAREER_KINDS:
        data.add_career_entry(kind, kind, TODAY)
    with pytest.raises(psycopg.errors.CheckViolation):
        data.add_application(acme, "x", "ghosted", TODAY)
    with pytest.raises(psycopg.errors.CheckViolation):
        data.add_career_entry("hobby", "x", TODAY)


def test_salary_and_date_ranges_are_checked():
    acme = data.company_id_for("Acme", TODAY)
    with pytest.raises(psycopg.errors.CheckViolation):
        data.add_application(acme, "x", "applied", TODAY, salary_min=100, salary_max=50)
    with pytest.raises(psycopg.errors.CheckViolation):
        data.add_position("Acme", "x", TODAY, ended_on=date(2020, 1, 1))


def test_interviews_come_back_in_date_and_time_order():
    acme = data.company_id_for("Acme", TODAY)
    app_id = data.add_application(acme, "A", "interviewing", TODAY)
    data.add_interview(app_id, date(2026, 10, 20), start_time=time(15, 0), round="Second")
    data.add_interview(app_id, date(2026, 10, 20), start_time=time(9, 0), round="First")
    data.add_interview(app_id, date(2026, 10, 16), round="Screen")
    frame = data.interviews(app_id)
    assert frame["round"].tolist() == ["Screen", "First", "Second"]
    assert frame["company"].tolist() == ["Acme"] * 3
    assert data.interviews()["round"].tolist() == ["Screen", "First", "Second"]


def test_import_adds_everything_once():
    rows = [{"company": "Acme", "role": "A", "status": "applied", "applied_on": date(2026, 10, 1),
             "notes": "hi"},
            {"company": "acme", "role": "B", "status": "saved", "applied_on": None}]
    assert data.import_applications(rows, TODAY) == (2, 0)
    assert data.import_applications(rows, TODAY) == (0, 2)
    assert len(data.companies()) == 1 and len(data.applications()) == 2


def test_a_failed_import_adds_nothing():
    rows = [{"company": "Acme", "role": "A", "status": "applied", "applied_on": None},
            {"company": "Beta", "role": "B", "status": "nonsense", "applied_on": None}]
    with pytest.raises(psycopg.errors.CheckViolation):
        data.import_applications(rows, TODAY)
    assert data.applications().empty and data.companies().empty


def test_career_log_and_job_history():
    data.add_career_entry("win", "Shipped it", date(2026, 9, 1), tags="sql")
    entry = data.add_career_entry("skill", "dbt", date(2026, 10, 1))
    assert data.career_entries()["title"].tolist() == ["dbt", "Shipped it"]
    assert data.career_entries("win")["title"].tolist() == ["Shipped it"]
    data.update_career_entry(entry, details="  ")
    assert data.career_entries("skill")["details"].isna().all()
    job = data.add_position("Acme", "Analyst", date(2024, 1, 8), base_salary=85000)
    data.update_position(job, ended_on=date(2026, 6, 30))
    assert data.positions()["ended_on"].tolist() == [date(2026, 6, 30)]


def test_a_closed_connection_is_reopened():
    data.companies()
    data._conn.close()
    assert data.companies().empty


def test_a_connection_the_server_dropped_while_idle_is_replaced(monkeypatch, database):
    """As when Neon suspends: the next use after a quiet spell pings, finds the
    connection dead, and reconnects instead of failing the page."""
    data.companies()
    with psycopg.connect(database, autocommit=True) as other:
        other.execute("select pg_terminate_backend(%s)", (data._conn.info.backend_pid,))
    monkeypatch.setattr(data, "_last_used", 0.0)
    assert data.companies().empty


def test_a_new_database_gets_its_tables_on_first_connection(database, monkeypatch):
    with psycopg.connect(database, autocommit=True) as conn:
        conn.execute("drop table career_entries")
    monkeypatch.setattr(data, "_schema_ready", False)
    data.reset_connection()
    assert data.career_entries().empty                # recreated, not an error


def test_a_setting_is_saved_over_and_unset_means_the_default():
    assert data.get_setting("theme") is None
    assert data.get_setting("theme", "light") == "light"
    data.set_setting("theme", "dark")
    data.set_setting("theme", "light")
    assert data.get_setting("theme") == "light"


# ---- job leads --------------------------------------------------------------

def leads(*rows):
    return [logic.clean_lead({"source": "LinkedIn", "company": "Acme", **r})[0] for r in rows]


def test_the_profile_is_one_row_saved_over():
    assert data.job_profile() is None
    data.save_job_profile(TODAY, target_roles="Data Analyst", min_salary=90000)
    data.save_job_profile(date(2026, 10, 15), target_roles="Analytics Engineer")
    profile = data.job_profile()
    assert profile["target_roles"] == "Analytics Engineer"
    assert profile["min_salary"] is None                # every field is replaced
    assert profile["updated_on"] == date(2026, 10, 15)
    with pytest.raises(ValueError):
        data.save_job_profile(TODAY, favourite_colour="blue")


def test_a_job_seen_before_from_any_site_is_skipped():
    assert data.add_leads(leads({"title": "Analyst", "fit_score": 6},
                                {"title": "Engineer", "fit_score": 9}), TODAY) == (2, 0)
    again = leads({"title": "analyst", "source": "Indeed"}, {"title": "Scientist"},
                  {"title": "Scientist"})
    assert data.add_leads(again, TODAY) == (1, 2)
    assert data.job_leads("new")["title"].tolist() == ["Engineer", "Analyst", "Scientist"]
    assert len(data.known_lead_keys()) == 3


def test_category_ratings_are_stored_with_the_lead():
    lead, _ = logic.clean_lead({"source": "Dice", "title": "A", "company": "B",
                                "fit": {"role": 8, "industry": 4}, "deal_breaker": True})
    data.add_leads([lead], TODAY)
    stored = data.job_leads().iloc[0]
    assert float(stored["fit_score"]) == config.DEAL_BREAKER_CAP
    assert stored["fit_detail"] == {"ratings": {"role": 8, "industry": 4}, "deal_breaker": True}


def test_migrate_brings_an_older_job_leads_table_up_to_date(database):
    with psycopg.connect(database, autocommit=True) as conn:        # the shape before 2026-10
        conn.execute("alter table applications drop column apply_url, drop column apply_note")
        conn.execute("alter table job_leads drop column fit_detail")
        conn.execute("alter table job_leads drop column pay_source")
        conn.execute("alter table job_leads drop column pay_note")
        conn.execute("alter table job_leads alter column fit_score type smallint")
        conn.execute("""alter table job_leads drop constraint job_leads_dismiss_reason_check,
                        add constraint job_leads_dismiss_reason_check
                            check (dismiss_reason in ('wrong role', 'other'))""")
    data.migrate()
    data.migrate()                                                   # safe to run again
    data.add_leads(leads({"title": "Analyst"}), TODAY)
    data.set_lead_status(int(data.job_leads()["lead_id"][0]), "dismissed",
                         ["not enough experience", "too much travel"], TODAY)   # the CHECK was remade
    with psycopg.connect(database, autocommit=True) as conn:
        columns = dict(conn.execute("""
            select column_name, data_type from information_schema.columns
            where table_name = 'job_leads'
              and column_name in ('fit_score', 'fit_detail', 'pay_source', 'pay_note')
        """).fetchall())
    assert columns == {"fit_score": "numeric", "fit_detail": "jsonb", "pay_source": "text",
                       "pay_note": "text"}
    app_id = data.add_application(data.company_id_for("Acme", TODAY), "A", "saved", TODAY)
    data.update_application(app_id, apply_url="https://acme.com/jobs/1")   # the columns are back




def test_a_dismissed_lead_stays_dismissed_when_seen_again():
    data.add_leads(leads({"title": "Analyst"}), TODAY)
    lead_id = int(data.job_leads()["lead_id"][0])
    data.set_lead_status(lead_id, "dismissed", "wrong role", TODAY)
    assert data.add_leads(leads({"title": "Analyst"}), TODAY) == (0, 1)
    assert data.job_leads("new").empty
    gone = data.lead(lead_id)
    assert (gone["dismiss_reason"], gone["dismissed_on"]) == ("wrong role", TODAY)
    data.set_lead_status(lead_id, "new")
    assert len(data.job_leads("new")) == 1
    back = data.lead(lead_id)
    assert back["dismiss_reason"] is None and back["dismissed_on"] is None


def test_every_dismiss_reason_is_allowed_by_the_schema_and_nothing_else():
    data.add_leads(leads({"title": "Analyst"}), TODAY)
    lead_id = int(data.job_leads()["lead_id"][0])
    for reason in config.DISMISS_REASONS:
        data.set_lead_status(lead_id, "dismissed", reason, TODAY)
    data.set_lead_status(lead_id, "dismissed", ["wrong role", "too much travel"], TODAY)
    assert data.lead(lead_id)["dismiss_reason"] == "wrong role, too much travel"   # several
    with pytest.raises(psycopg.errors.CheckViolation):
        data.set_lead_status(lead_id, "dismissed", "meh", TODAY)
    with pytest.raises(psycopg.errors.CheckViolation):
        data.set_lead_status(lead_id, "dismissed", ["wrong role", "meh"], TODAY)
    data.set_lead_status(lead_id, "dismissed", [], TODAY)
    assert data.lead(lead_id)["dismiss_reason"] is None                          # none given


def test_recent_dismissals_and_strong_leads_still_waiting():
    data.add_leads(leads({"title": "Old strong", "fit_score": 8}), date(2026, 9, 1))  # stale
    data.add_leads(leads({"title": "Waiting", "fit_score": 8.5}), date(2026, 10, 12))
    data.add_leads(leads({"title": "Weak", "fit_score": 5}), date(2026, 10, 12))
    data.add_leads(leads({"title": "Today", "fit_score": 9}), TODAY)
    data.add_leads(leads({"title": "Gone", "fit_score": 9}), date(2026, 10, 13))
    stored = data.job_leads().set_index("title")
    data.set_lead_status(int(stored.loc["Gone", "lead_id"]), "dismissed", "company",
                         date(2026, 10, 13))
    data.set_lead_status(int(stored.loc["Weak", "lead_id"]), "dismissed", "pay",
                         date(2026, 9, 1))
    assert data.strong_leads_waiting(TODAY)["title"].tolist() == ["Waiting"]
    recent = data.dismissed_recently(date(2026, 10, 1))
    assert recent["title"].tolist() == ["Gone"] and recent["dismiss_reason"][0] == "company"




def test_moving_a_lead_makes_a_saved_application_with_the_fit_in_its_notes():
    data.add_leads(leads({"title": "Analyst", "salary": "$90k-$110k", "work_mode": "hybrid",
                          "job_url": "https://example.com/1", "fit_score": 8,
                          "fit_reason": "Strong SQL match"}), TODAY)
    lead_id = int(data.job_leads()["lead_id"][0])
    app_id = data.move_lead_to_applications(lead_id, TODAY)
    app = data.application(app_id)
    assert (app["company"], app["role"], app["status"], app["source"]) == (
        "Acme", "Analyst", "saved", "LinkedIn")
    assert (app["salary_min"], app["salary_max"], app["work_mode"]) == (90000, 110000, "hybrid")
    assert app["notes"] == "Fit 8/10: Strong SQL match"
    moved = data.lead(lead_id)
    assert (moved["status"], moved["application_id"]) == ("moved", app_id)
    data.delete_application(app_id)                 # the lead stays, unlinked
    assert data.lead(lead_id)["application_id"] is None


def test_an_estimated_pay_is_noted_on_the_application_a_lead_becomes():
    data.add_leads(leads({"title": "Analyst", "salary": "$90k-$110k", "pay_source": "estimated",
                          "pay_note": "Glassdoor, Denver", "fit": {"role": 7, "pay": 6}}), TODAY)
    app = data.application(data.move_lead_to_applications(int(data.job_leads()["lead_id"][0]),
                                                          TODAY))
    assert app["notes"] == "Fit 6.7/10\nPay is the daily review's estimate (Glassdoor, Denver)."


def test_leads_found_are_one_days_new_leads_best_first():
    data.add_leads(leads({"title": "Old"}), date(2026, 10, 13))
    data.add_leads(leads({"title": "Weak", "fit_score": 3}) + leads({"title": "Good", "fit_score": 8})
                   + leads({"title": "Gone"}), TODAY)
    data.set_lead_status(int(data.job_leads()[data.job_leads()["title"] == "Gone"]["lead_id"]
                             .iloc[0]), "dismissed")
    assert data.leads_found(TODAY)["title"].tolist() == ["Good", "Weak"]


def test_every_lead_status_is_allowed_by_the_schema_and_nothing_else():
    data.add_leads(leads({"title": "Analyst"}), TODAY)
    lead_id = int(data.job_leads()["lead_id"][0])
    for status in config.LEAD_STATUSES:
        data.set_lead_status(lead_id, status)
    with pytest.raises(psycopg.errors.CheckViolation):
        data.set_lead_status(lead_id, "maybe")


def test_the_master_resume_its_sources_and_the_template_round_trip():
    assert data.resume_master() is None and data.resume_template() is None
    first = data.add_resume_source("Resume.docx", "resume", "## Sample", b"PK-word-file", TODAY)
    data.add_resume_source("History.docx", "history", "Project: x", None, date(2026, 10, 10))
    data.set_resume_template(first, TODAY)
    assert data.resume_template() == b"PK-word-file"
    assert data.resume_master()["content"]["roles"] == []        # a placeholder row for now
    content = {"name": "Sample", "email": "", "phone": "", "linkedin": "", "roles": [],
               "projects": [], "education": [], "skill_groups": [], "conflicts": ["x"]}
    data.save_resume_master(content, TODAY)
    master = data.resume_master()
    assert master["content"] == content and master["template_source_id"] == first
    assert master["updated_on"] == TODAY
    assert data.resume_source_texts() == {"resume": "## Sample", "history": "Project: x"}
    sources = data.resume_sources()
    assert sources["filename"].tolist() == ["Resume.docx", "History.docx"]
    assert sources["has_file"].tolist() == [True, False] and sources["chars"].tolist() == [9, 10]
    again = data.add_resume_source("resume.docx", "resume", "## Newer", b"PK2", TODAY)
    assert again != first and len(data.resume_sources()) == 2    # same name: replaced
    assert data.resume_template() is None                         # the template row was replaced
    data.delete_resume_source(again)
    assert data.resume_sources()["filename"].tolist() == ["History.docx"]


def test_every_resume_source_kind_is_allowed_by_the_schema_and_nothing_else():
    for kind in config.RESUME_SOURCE_KINDS:
        data.add_resume_source(f"{kind}.txt", kind, "x", None, TODAY)
    with pytest.raises(psycopg.errors.CheckViolation):
        data.add_resume_source("odd.txt", "diary", "x", None, TODAY)


def test_claude_usage_adds_up_from_a_date():
    data.log_ai_usage("structure resume", "claude-opus-5-5", 6000, 8000, 0.184, TODAY)
    data.log_ai_usage("structure resume", "claude-opus-5-5", 1000, 1000, 0.024, date(2026, 9, 1))
    assert data.ai_usage_since(date(2026, 10, 1)) == (1, 0.184)
    assert data.ai_usage_since(date(2026, 9, 1)) == (2, 0.208)
    assert data.ai_usage_since(date(2027, 1, 1)) == (0, 0.0)


def test_a_posting_and_tailored_versions_live_with_the_application():
    acme = data.company_id_for("Acme", TODAY)
    app_id = data.add_application(acme, "Analyst", "saved", TODAY)
    data.update_application(app_id, posting="  We need SQL.  ")
    assert data.application(app_id)["posting"] == "We need SQL."
    data.update_application(app_id, apply_url="https://acme.com/jobs/1", apply_note="Sure.")
    assert data.application(app_id)["apply_url"] == "https://acme.com/jobs/1"
    data.update_application(app_id, apply_url="", apply_note="Not found.")
    assert data.application(app_id)["apply_url"] is None               # blank is none
    first = data.add_tailored(app_id, {"roles": [], "cover_letter": "Dear"}, "  ", "m-1", TODAY)
    second = data.add_tailored(app_id, {"roles": [1]}, "lead with SQL", "m-1", TODAY)
    versions = data.tailored_versions(app_id)
    assert versions["version"].tolist() == [2, 1]
    assert versions["tailor_id"].tolist() == [second, first]
    assert versions["notes"].iloc[0] == "lead with SQL" and versions["notes"].isna().tolist() == [
        False, True]
    assert data.tailored(first)["content"] == {"roles": [], "cover_letter": "Dear"}
    data.save_tailored(first, {"roles": [], "cover_letter": "Dear Team"})
    assert data.tailored(first)["content"]["cover_letter"] == "Dear Team"
    data.delete_tailored(second)
    assert data.tailored_versions(app_id)["version"].tolist() == [1]
    data.delete_application(app_id)                       # takes its versions with it
    assert data.tailored(first) is None




def test_lead_stats_count_the_reviewed_the_average_and_the_inbox_above_each_mark():
    assert data.lead_stats() == {"reviewed": 0, "average_fit": None, "waiting": [0, 0]}
    data.add_leads(leads({"title": "A", "fit_score": 9.2}, {"title": "B", "fit_score": 8.1},
                         {"title": "C", "fit_score": 5.0}, {"title": "D"}), TODAY)
    stats = data.lead_stats()
    assert stats["reviewed"] == 4 and stats["waiting"] == [2, 1]
    assert round(stats["average_fit"], 2) == round((9.2 + 8.1 + 5.0) / 3, 2)   # unscored skipped
    top = int(data.job_leads("new").iloc[0]["lead_id"])
    data.move_lead_to_applications(top, TODAY)                     # A leaves the inbox
    assert data.lead_stats()["waiting"] == [1, 0] and data.lead_stats()["reviewed"] == 4
    assert data.lead_stats(marks=(7.0,))["waiting"] == [1]
