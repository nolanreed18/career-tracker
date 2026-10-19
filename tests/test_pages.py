"""Every page, run headless against the throwaway database: it draws empty and
with data, and the main forms do what they say."""

import os
from datetime import date, timedelta
from pathlib import Path

import psycopg
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config
import data
import logic
import theme
import ui

ROOT = Path(__file__).resolve().parent.parent
HOME = ROOT / "app" / "Home.py"
PAGES = sorted((ROOT / "app" / "pages").glob("*.py"))
TODAY = date(2026, 10, 14)


PASSWORD = "correct horse"


@pytest.fixture(autouse=True)
def fixed_today(database, monkeypatch):
    monkeypatch.setattr(data, "today", lambda: TODAY)
    monkeypatch.setenv("APP_PASSWORD", PASSWORD)


def new_app(path: Path, signed_in: bool = True) -> AppTest:
    at = AppTest.from_file(str(path), default_timeout=30)
    if signed_in:
        at.session_state[ui.SIGNED_IN] = True
    return at


def run(path: Path) -> AppTest:
    at = new_app(path).run()
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
    data.save_job_profile(TODAY, target_roles="Data Analyst", work_modes="remote, hybrid")
    data.add_leads([logic.clean_lead(r)[0] for r in (
        {"source": "LinkedIn", "title": "Analytics Engineer", "company": "Gamma",
         "salary": "$120k-$140k", "fit_score": 9, "fit_reason": "Strong dbt and SQL match",
         "job_url": "https://example.com/1"},
        {"source": "Dice", "title": "BI Developer", "company": "Delta",
         "fit": {"role": 5, "industry": 3, "location": 8, "level": 6, "extras": 4}},
    )], TODAY)
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
    assert not at.text_input                      # the form waits behind its button
    click(at, "Add an application")
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
    click(at, "Add an application")
    widget(at.text_input, "Role").set_value("Engineer")
    click(at, "Add application")
    assert at.error[0].value == "Pick a company or type a new one."
    assert data.applications().empty
    assert widget(at.button, "Close")             # the form stayed open with its error


def test_logging_an_update_records_history_and_clears_the_step():
    app_id = seed()
    data.update_application(app_id, next_action="Call", next_action_on=TODAY)
    at = new_app(PAGES[0])
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
    at = new_app(PAGES[0])
    at.session_state["open_application"] = app_id
    at.run()
    widget(at.radio, "Section").set_value("Edit").run()
    assert widget(at.button, "Delete application").disabled
    widget(at.checkbox, "I want to delete this application").check().run()
    click(at, "Delete application")
    assert data.application(app_id) is None
    assert not at.exception


def test_a_company_in_use_is_not_deleted():
    seed()
    at = run(PAGES[2])
    widget(at.selectbox, "Edit a company").set_value("Acme").run()
    assert widget(at.button, "Delete company").disabled           # tick box first
    widget(at.checkbox, "I want to delete this company").check().run()
    click(at, "Delete company")
    assert "still has applications" in at.error[0].value
    assert "Acme" in data.companies()["name"].tolist()


def test_tables_show_blanks_not_none_for_missing_values():
    seed()
    data.add_application(data.company_id_for("Acme", TODAY), "Saved one", "saved", TODAY)
    companies = run(PAGES[2]).dataframe[0].value
    assert companies["industry"].tolist() == ["", ""]           # not None, not "None"
    apps = run(PAGES[0]).dataframe[0].value
    assert apps["applied_on"].isna().sum() == 1                  # the one still Saved


def test_a_deleted_company_leaves_the_dropdown():
    seed()
    data.add_company("Solo", TODAY)
    at = run(PAGES[2])
    widget(at.selectbox, "Edit a company").set_value("Solo").run()
    widget(at.checkbox, "I want to delete this company").check().run()
    click(at, "Delete company")
    assert at.success[0].value == "Deleted Solo."
    dropdown = widget(at.selectbox, "Edit a company")
    assert dropdown.value is None and "Solo" not in dropdown.options


def test_sections_stay_put_after_an_action():
    seed()
    at = run(PAGES[2])
    widget(at.radio, "Section").set_value("Contacts").run()
    click(at, "Add a contact")
    widget(at.text_input, "Name").set_value("Ana")
    click(at, "Add contact")
    assert at.success[0].value == "Added Ana."
    assert widget(at.radio, "Section").value == "Contacts"
    assert "Ana" in data.contacts()["name"].tolist()


def test_logging_a_win():
    at = run(PAGES[3])
    widget(at.text_input, "What").set_value("Led the migration")
    click(at, "Add")
    assert data.career_entries("win")["title"].tolist() == ["Led the migration"]


@pytest.mark.parametrize("path", [HOME, *PAGES], ids=lambda p: p.stem)
def test_every_page_asks_for_the_password_first(path):
    seed()
    at = new_app(path, signed_in=False).run()
    assert [t.label for t in at.text_input] == ["Password"]
    assert not at.metric and not at.dataframe and "Acme" not in str(at)


def test_the_right_password_opens_the_app_and_a_wrong_one_does_not(monkeypatch):
    monkeypatch.setattr(ui.time, "sleep", lambda s: None)
    at = new_app(HOME, signed_in=False).run()
    widget(at.text_input, "Password").set_value("guess")
    click(at, "Sign in")
    assert at.error[0].value == "Wrong password."
    assert not at.metric
    widget(at.text_input, "Password").set_value(PASSWORD)
    click(at, "Sign in")
    assert widget(at.metric, "Open").value == "0"


def test_dark_mode_is_a_saved_choice_and_light_is_the_default():
    at = run(HOME)
    assert theme.current() == "light" and data.get_setting("theme") is None
    widget(at.toggle, "Dark mode").set_value(True).run()
    assert not at.exception
    assert data.get_setting("theme") == "dark" and theme.current() == "dark"
    assert run(PAGES[0]).toggle[0].value is True          # every page follows
    widget(at.toggle, "Dark mode").set_value(False).run()
    assert data.get_setting("theme") == "light" and theme.current() == "light"


def test_the_switch_follows_a_change_made_on_another_device():
    at = run(HOME)
    assert widget(at.toggle, "Dark mode").value is False
    data.set_setting("theme", "dark")                 # flipped on the phone, say
    at.run()
    assert not at.exception
    assert widget(at.toggle, "Dark mode").value is True
    assert data.get_setting("theme") == "dark" and theme.current() == "dark"
    data.set_setting("theme", "light")
    at.run()
    assert widget(at.toggle, "Dark mode").value is False and theme.current() == "light"


def test_signing_out_locks_the_app_again():
    at = run(HOME)
    click(at, "Sign out")
    assert [t.label for t in at.text_input] == ["Password"] and not at.metric


def test_no_way_to_sign_in_set_up_keeps_the_app_locked(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD")
    at = new_app(HOME, signed_in=False).run()
    assert "no way to sign in is set up" in at.error[0].value
    assert not at.text_input and not at.metric and not at.button


@pytest.fixture
def google(monkeypatch):
    """Sign in with Google set up, for you; who is signed in is set per test."""
    monkeypatch.setattr(ui, "_google_ready", lambda: True)
    monkeypatch.setenv("ALLOWED_EMAILS", "Me@Example.com, other@example.com")

    def signed_in_as(email):
        monkeypatch.setattr(ui, "_google_email", lambda: email)
    return signed_in_as


def test_google_offers_both_ways_in_until_someone_signs_in(google):
    seed()
    google(None)
    at = new_app(HOME, signed_in=False).run()
    assert [b.label for b in at.button] == ["Sign in with Google", "Sign in with password"]
    assert not at.metric and "Acme" not in str(at)


def test_an_allowed_google_account_goes_straight_in(google):
    google("me@example.com")
    at = new_app(HOME, signed_in=False).run()
    assert widget(at.metric, "Open").value == "0"
    for path in PAGES:                              # and stays in on every page
        assert not new_app(path, signed_in=False).run().exception


def test_any_other_google_account_is_turned_away(google):
    seed()
    google("stranger@example.com")
    at = new_app(HOME, signed_in=False).run()
    assert "stranger@example.com isn't allowed" in at.error[0].value
    assert [b.label for b in at.button] == ["Sign out"]
    assert not at.metric and "Acme" not in str(at)


def test_the_sidebar_is_hidden_only_while_signed_out(google, monkeypatch):
    shown = []
    original = st.html
    monkeypatch.setattr(st, "html", lambda body, **kw: (shown.append(body), original(body, **kw)))
    google("me@example.com")
    new_app(HOME, signed_in=False).run()
    assert shown and not any(theme.LOCKED in body for body in shown)
    shown.clear()
    google(None)
    new_app(HOME, signed_in=False).run()
    assert any(theme.LOCKED in body for body in shown)


def test_google_without_allowed_emails_lets_nobody_in(google, monkeypatch):
    monkeypatch.delenv("ALLOWED_EMAILS")
    google("me@example.com")
    at = new_app(HOME, signed_in=False).run()
    assert "isn't allowed" in at.error[0].value and not at.metric


LEADS = ROOT / "app" / "pages" / "7_Job_Leads.py"


def test_leads_are_listed_best_fit_first_and_home_points_to_them():
    seed()
    at = run(LEADS)
    titles = [m.value for m in at.markdown if "**" in m.value]
    assert "Analytics Engineer" in titles[0] and ":green-badge[9/10]" in titles[0]
    assert "BI Developer" in titles[1]
    home = run(HOME)
    assert any("2 new job leads to review, 1 strong" in m.value for m in home.markdown)


def test_a_lead_shows_its_category_ratings_and_the_rules_are_explained():
    seed()
    at = run(LEADS)
    assert any("Role 5 · Industry 3 · Location 8" in c.value for c in at.caption)
    titles = [m.value for m in at.markdown if "BI Developer" in m.value]
    assert ":blue-badge[5.1/10]" in titles[0]
    widget(at.radio, "Section").set_value("What I'm looking for").run()
    assert any("How scoring works" in m.value for m in at.markdown)
    assert any("Role match** (35%)" in m.value for m in at.markdown)
    assert any("**Pay.**" in m.value and "estimate" in m.value for m in at.markdown)


def test_a_lead_shows_listed_pay_plainly_and_a_warning_when_pay_is_missing_or_estimated():
    seed()
    data.add_leads([logic.clean_lead({
        "source": "Indeed", "title": "Data Engineer", "company": "Epsilon",
        "salary": "$130k-$150k", "pay_source": "estimated",
        "pay_note": "Levels.fyi range, Data Engineer, Denver",
        "fit": {"role": 6, "pay": 8}})[0]], TODAY)
    at = run(LEADS)
    captions = [c.value for c in at.caption]
    assert any("Analytics Engineer" not in c and "\\$120,000–\\$140,000" in c for c in captions)
    assert any(":yellow-badge[:material/warning: Pay not listed]" in c for c in captions)
    assert any(":yellow-badge[:material/warning: \\~\\$130,000–\\$150,000 (estimate)] · "
               "Levels.fyi range, Data Engineer, Denver" in c for c in captions)


def test_dismissing_a_lead_asks_why_and_restore_brings_it_back():
    seed()
    at = run(LEADS)
    widget(at.selectbox, "Dismiss", 1).select("wrong role").run()
    assert not at.exception, [e.message for e in at.exception]
    assert data.job_leads("new")["title"].tolist() == ["Analytics Engineer"]
    gone = data.job_leads("dismissed").iloc[0]
    assert (gone["dismiss_reason"], gone["dismissed_on"]) == ("wrong role", TODAY)
    widget(at.radio, "Section").set_value("Dismissed").run()
    assert any(":gray-badge[wrong role] dismissed today" in m.value for m in at.markdown)
    click(at, "Restore")
    assert len(data.job_leads("new")) == 2
    assert data.lead(int(gone["lead_id"]))["dismiss_reason"] is None


def test_todays_leads_are_marked_new_and_old_ones_go_stale():
    seed()                                                  # Gamma and Delta arrive today
    data.add_leads([logic.clean_lead(r)[0] for r in (
        {"source": "Dice", "title": "Yesterday's Analyst", "company": "Eta", "fit_score": 8},
    )], TODAY - timedelta(days=1))
    data.add_leads([logic.clean_lead(r)[0] for r in (
        {"source": "Dice", "title": "Forgotten Engineer", "company": "Theta", "fit_score": 9},
    )], TODAY - timedelta(days=config.LEAD_STALE_DAYS + 1))
    at = run(LEADS)
    assert any("3 new leads: 2 today, 2 strong" in c.value and "1 stale under Stale" in c.value
               for c in at.caption)
    shown = [m.value for m in at.markdown if "**" in m.value and "—" in m.value]
    assert widget(at.radio, "Show").value == "today"       # today's batch comes up first
    assert len(shown) == 2 and all(":blue-badge[New]" in m for m in shown)
    assert not any("Forgotten Engineer" in m for m in shown)
    widget(at.radio, "Show").set_value("all").run()
    shown = [m.value for m in at.markdown if "**" in m.value and "—" in m.value]
    assert len(shown) == 3 and sum(":blue-badge[New]" in m for m in shown) == 2
    assert "Analytics Engineer" in shown[0] and "Yesterday's Analyst" in shown[1]   # best first
    widget(at.radio, "Section").set_value("Stale").run()
    assert any("Forgotten Engineer" in m.value for m in at.markdown)
    home = run(HOME)
    assert any("3 new job leads to review, 2 strong" in m.value for m in home.markdown)


def test_companies_to_skip_are_saved_with_the_profile():
    seed()
    at = run(LEADS)
    widget(at.radio, "Section").set_value("What I'm looking for").run()
    widget(at.text_area, "Companies to skip").set_value("Robert Half\nTEKsystems").run()
    click(at, "Save")
    assert data.job_profile()["skip_companies"] == "Robert Half\nTEKsystems"
    assert any("**Dismissals.**" in m.value for m in at.markdown)


def test_moving_a_lead_creates_the_application():
    seed()
    at = run(LEADS)
    widget(at.button, "Add").click().run()
    apps = data.applications()
    moved = apps[apps["role"] == "Analytics Engineer"].iloc[0]
    assert (moved["company"], moved["status"]) == ("Gamma", "saved")
    assert data.job_leads("moved")["title"].tolist() == ["Analytics Engineer"]


def test_the_profile_form_saves():
    at = run(LEADS)
    assert any("Fill in" in w.value for w in at.warning)
    widget(at.radio, "Section").set_value("What I'm looking for").run()
    widget(at.text_area, "Roles I want").set_value("Data Analyst")
    widget(at.number_input, "Lowest base salary I'd take ($/yr)").set_value(100000)
    widget(at.multiselect, "Work modes I'd take").set_value(["remote"])
    click(at, "Save")
    profile = data.job_profile()
    assert (profile["target_roles"], profile["min_salary"], profile["work_modes"]) == (
        "Data Analyst", 100000, "remote")


def test_weak_leads_are_hidden_until_asked_for():
    seed()
    data.add_leads([logic.clean_lead({
        "source": "Indeed", "title": "Excel Reporting Clerk", "company": "Epsilon",
        "fit_score": 2, "fit_reason": "Pure Excel reporting: a deal-breaker."})[0]], TODAY)
    at = run(LEADS)
    assert any("3 new leads: 3 today, 1 strong (fit 7+), 1 weak (under 4)." in c.value
               for c in at.caption)
    shown = " ".join(m.value for m in at.markdown)           # New today: weak ones wait
    assert "Analytics Engineer" in shown and "BI Developer" in shown
    assert "Excel Reporting Clerk" not in shown
    widget(at.radio, "Show").set_value("all").run()
    shown = " ".join(m.value for m in at.markdown)
    assert "Excel Reporting Clerk" in shown and "Pure Excel reporting" in shown
    widget(at.radio, "Show").set_value("strong").run()
    shown = " ".join(m.value for m in at.markdown)
    assert "Analytics Engineer" in shown and "BI Developer" not in shown


def test_todays_glassdoor_links_open_the_right_form():
    data.add_leads([logic.clean_lead({
        "source": "Glassdoor", "title": "Analyst", "company": "Zeta", "fit_score": 8})[0]], TODAY)
    lead_id = int(data.job_leads()["lead_id"][0])
    with psycopg.connect(os.environ["TEST_DATABASE_URL"], autocommit=True) as conn:
        conn.execute("update job_leads set job_url = %s where lead_id = %s",
                     ("https://www.glassdoor.com/job-listing?jl=1010293120973", lead_id))
    at = run(LEADS)
    assert any("partner/jobListing.htm?jobListingId=1010293120973" in m.value
               for m in at.markdown)
