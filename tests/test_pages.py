"""Every page, run headless against the throwaway database: it draws empty and
with data, and the main forms do what they say."""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import data

ROOT = Path(__file__).resolve().parent.parent
HOME = ROOT / "app" / "Home.py"
PAGES = sorted((ROOT / "app" / "pages").glob("*.py"))
TODAY = date(2026, 10, 14)


@pytest.fixture(autouse=True)
def fixed_today(database, monkeypatch):
    monkeypatch.setattr(data, "today", lambda: TODAY)


def run(path: Path) -> AppTest:
    at = AppTest.from_file(str(path), default_timeout=30).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def widget(elements, label, nth: int = 0):
    """The nth widget with this label (-1: the last, e.g. a form below the add form)."""
    matches = [w for w in elements if w.label == label]
    assert matches, f"no widget labelled {label!r}: {[w.label for w in elements]}"
    return matches[nth]


def click(at: AppTest, label: str) -> AppTest:
    widget(at.button, label).click().run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def seed() -> int:
    acme = data.company_id_for("Acme", TODAY)
    quiet = data.add_application(acme, "Data Analyst", "applied", TODAY,
                                 applied_on=date(2026, 9, 1), source="LinkedIn",
                                 salary_min=90000, salary_max=110000)
    busy = data.add_application(data.company_id_for("Beta", TODAY), "PM", "interviewing", TODAY,
                                next_action="Send thank-you", next_action_on=date(2026, 10, 12))
    data.add_interview(busy, date(2026, 10, 15), round="Onsite")
    data.add_contact("Sam", TODAY, company_id=acme, kind="recruiter")
    data.add_career_entry("win", "Cut report time 90%", date(2026, 9, 1))
    data.add_position("Acme", "Analyst", date(2024, 1, 8), base_salary=85000)
    return quiet


@pytest.mark.parametrize("path", [HOME, *PAGES], ids=lambda p: p.stem)
def test_every_page_draws_empty(path):
    run(path)


@pytest.mark.parametrize("path", [HOME, *PAGES], ids=lambda p: p.stem)
def test_every_page_draws_with_data(path):
    seed()
    run(path)


def test_home_lists_what_needs_attention_most_urgent_first():
    seed()
    at = run(HOME)
    lines = [m.value for m in at.markdown if "**" in m.value]
    assert "Send thank-you: 2 days overdue" in lines[0]
    assert "Onsite, tomorrow" in lines[1]
    assert "No update in 43 days" in lines[2]
    assert widget(at.metric, "Open").value == "2"


def test_adding_an_application_makes_the_company_and_opens_it():
    at = run(PAGES[0])
    widget(at.text_input, "…or a new company").set_value("Gamma")
    widget(at.text_input, "Role").set_value("Engineer")
    widget(at.number_input, "Salary from ($/yr)").set_value(120000)
    click(at, "Add application")
    app = data.applications().iloc[0]
    assert (app["company"], app["role"], app["status"], app["applied_on"],
            app["salary_min"]) == ("Gamma", "Engineer", "applied", TODAY, 120000)
    assert at.success[0].value == "Added Engineer at Gamma."
    assert any("Gamma — Engineer" in m.value for m in at.markdown)


def test_an_application_needs_a_company_and_a_role():
    at = run(PAGES[0])
    widget(at.text_input, "Role").set_value("Engineer")
    click(at, "Add application")
    assert at.error[0].value == "Pick a company or type a new one."
    assert data.applications().empty


def test_logging_an_update_records_history_and_clears_the_step():
    app_id = seed()
    data.update_application(app_id, next_action="Call", next_action_on=TODAY)
    at = AppTest.from_file(str(PAGES[0]), default_timeout=30)
    at.session_state["open_application"] = app_id
    at.run()
    widget(at.selectbox, "Status", -1).set_value("screening")
    widget(at.text_input, "What happened?").set_value("Recruiter called")
    widget(at.checkbox, "The next step is done: clear it").check()
    click(at, "Log update")
    app = data.application(app_id)
    assert (app["status"], app["next_action"], app["next_action_on"]) == ("screening", None, None)
    assert data.events(app_id)["note"].tolist()[-1] == "Recruiter called"


def test_deleting_needs_the_confirmation():
    app_id = seed()
    at = AppTest.from_file(str(PAGES[0]), default_timeout=30)
    at.session_state["open_application"] = app_id
    at.run()
    assert widget(at.button, "Delete application").disabled
    widget(at.checkbox, "I want to delete this application").check().run()
    click(at, "Delete application")
    assert data.application(app_id) is None
    assert not at.exception


def test_a_company_in_use_is_not_deleted():
    seed()
    at = run(PAGES[2])
    widget(at.selectbox, "Edit a company").set_value("Acme").run()
    click(at, "Delete company")
    assert "still has applications" in at.error[0].value
    assert "Acme" in data.companies()["name"].tolist()


def test_logging_a_win():
    at = run(PAGES[3])
    widget(at.text_input, "What").set_value("Led the migration")
    click(at, "Add")
    assert data.career_entries("win")["title"].tolist() == ["Led the migration"]
