"""data.py against a real (throwaway) Postgres with the real schema."""

from datetime import date, time

import psycopg
import pytest

import config
import data

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


# ---- job leads --------------------------------------------------------------

def leads(*rows):
    import logic
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


def test_a_dismissed_lead_stays_dismissed_when_seen_again():
    data.add_leads(leads({"title": "Analyst"}), TODAY)
    lead_id = int(data.job_leads()["lead_id"][0])
    data.set_lead_status(lead_id, "dismissed")
    assert data.add_leads(leads({"title": "Analyst"}), TODAY) == (0, 1)
    assert data.job_leads("new").empty
    data.set_lead_status(lead_id, "new")
    assert len(data.job_leads("new")) == 1


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


def test_every_lead_status_is_allowed_by_the_schema_and_nothing_else():
    data.add_leads(leads({"title": "Analyst"}), TODAY)
    lead_id = int(data.job_leads()["lead_id"][0])
    for status in config.LEAD_STATUSES:
        data.set_lead_status(lead_id, status)
    with pytest.raises(psycopg.errors.CheckViolation):
        data.set_lead_status(lead_id, "maybe")
