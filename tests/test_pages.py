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
LEADS, APPS = (ROOT / "app" / "pages" / name for name in ("1_Job_Leads.py", "2_Applications.py"))
TODAY = date(2026, 10, 14)


PASSWORD = "correct horse"


@pytest.fixture(autouse=True)
def fixed_today(database, monkeypatch):
    monkeypatch.setattr(data, "today", lambda: TODAY)
    monkeypatch.setenv("APP_PASSWORD", PASSWORD)
    monkeypatch.setattr(theme, "_applied", None)     # a fresh process: reads the saved look


@pytest.fixture
def phone(monkeypatch):
    """The phone layout (one column, lead cards), as an iPhone's browser gets."""
    monkeypatch.setattr(ui, "device", lambda: "phone")


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
    assert widget(at.metric, "Reviewed").value == "2"            # both seeded leads
    assert widget(at.metric, "Avg fit").value != "—"
    assert widget(at.metric, "8+ waiting").value == "1"           # Gamma at 9, still new
    assert widget(at.metric, "9+ waiting").value == "1"
    assert any("2 leads in the inbox, 2 new today, 1 strong" in m.value for m in at.markdown)
    assert not any(b.label == "Log a win" for b in at.button)


def test_adding_an_application_makes_the_company_and_opens_it():
    at = run(APPS)
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
    at = run(APPS)
    click(at, "Add an application")
    widget(at.text_input, "Role").set_value("Engineer")
    click(at, "Add application")
    assert at.error[0].value == "Pick a company or type a new one."
    assert data.applications().empty
    assert widget(at.button, "Close")             # the form stayed open with its error


def test_logging_an_update_records_history_and_clears_the_step():
    app_id = seed()
    data.update_application(app_id, next_action="Call", next_action_on=TODAY)
    at = new_app(APPS)
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
    at = new_app(APPS)
    at.session_state["open_application"] = app_id
    at.run()
    widget(at.radio, "Section").set_value("Edit").run()
    assert widget(at.button, "Delete application").disabled
    widget(at.checkbox, "I want to delete this application").check().run()
    click(at, "Delete application")
    assert data.application(app_id) is None
    assert not at.exception


def test_an_interview_is_added_edited_and_deleted_on_its_application():
    seed()
    busy = int(data.applications().query("role == 'PM'")["application_id"].iloc[0])
    at = new_app(APPS)
    at.session_state["open_application"] = busy
    at.run()
    widget(at.radio, "Section").set_value("Interviews").run()
    widget(at.text_area, "How it went").set_value("Went well")
    widget(at.selectbox, "Rating").set_value("4")
    click(at, "Save")
    interview = data.interviews(busy).iloc[0]
    assert (interview["outcome_notes"], interview["rating"]) == ("Went well", 4)
    click(at, "Add an interview")
    widget(at.text_input, "Round", -1).set_value("Recruiter screen")
    click(at, "Add interview")
    assert data.interviews(busy)["round"].tolist() == ["Recruiter screen", "Onsite"]  # by date
    widget(at.checkbox, "I want to delete this interview").check().run()
    click(at, "Delete interview")
    assert data.interviews(busy)["round"].tolist() == ["Onsite"]


def test_tables_show_blanks_not_none_for_missing_values():
    seed()
    data.add_application(data.company_id_for("Acme", TODAY), "Saved one", "saved", TODAY)
    apps = run(APPS).dataframe[0].value                         # beside the open one: short
    assert list(apps.columns) == ["company", "role", "status", "resume"]
    assert "None" not in apps.astype(str).values


def test_a_company_with_no_applications_left_drops_out_of_the_picker():
    seed()
    solo = data.add_application(data.company_id_for("Solo", TODAY), "Analyst", "saved", TODAY)
    data.delete_application(solo)
    at = run(APPS)
    click(at, "Add an application")
    options = widget(at.selectbox, "Company").options
    assert "Acme" in options and "Solo" not in options


def test_sections_stay_put_after_an_action():
    seed()
    at = run(LEADS)
    widget(at.radio, "Section").set_value("What I'm looking for").run()
    click(at, "Save")
    assert widget(at.radio, "Section").value == "What I'm looking for"


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
    assert widget(at.metric, "Reviewed").value == "0"


def test_dark_mode_is_a_saved_choice_and_light_is_the_default():
    at = run(HOME)
    assert theme.current() == "light" and data.get_setting("theme") is None
    widget(at.toggle, "Dark mode").set_value(True).run()
    assert not at.exception
    assert data.get_setting("theme") == "dark" and theme.current() == "dark"
    assert run(APPS).toggle[0].value is True          # every page follows
    widget(at.toggle, "Dark mode").set_value(False).run()
    assert data.get_setting("theme") == "light" and theme.current() == "light"


def test_the_switch_follows_a_change_made_on_another_device():
    laptop = run(HOME)
    assert widget(laptop.toggle, "Dark mode").value is False
    phone = run(HOME)                                  # another device, the same app process
    widget(phone.toggle, "Dark mode").set_value(True).run()
    laptop.run()
    assert not laptop.exception
    assert widget(laptop.toggle, "Dark mode").value is True
    assert data.get_setting("theme") == "dark" and theme.current() == "dark"
    widget(phone.toggle, "Dark mode").set_value(False).run()
    laptop.run()
    assert widget(laptop.toggle, "Dark mode").value is False and theme.current() == "light"


def test_the_saved_look_is_read_once_per_process(monkeypatch):
    data.set_setting("theme", "dark")
    at = run(HOME)
    assert theme.current() == "dark" and widget(at.toggle, "Dark mode").value is True
    reads = []
    monkeypatch.setattr(data, "get_setting", lambda *args: reads.append(args) or "light")
    at.run()
    assert not at.exception and not reads               # no round trip, and no flip back
    assert theme.current() == "dark" and widget(at.toggle, "Dark mode").value is True


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
    assert widget(at.metric, "Reviewed").value == "0"
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


def test_leads_are_listed_best_fit_first_and_home_points_to_them(phone):
    seed()
    at = run(LEADS)
    assert widget(at.radio, "Show").value == "today"       # opens on today's, best first
    titles = [m.value for m in at.markdown if "**" in m.value]
    assert "Analytics Engineer" in titles[0] and ":green-badge[9/10]" in titles[0]
    assert "BI Developer" in titles[1]
    home = run(HOME)
    assert any("2 leads in the inbox, 2 new today, 1 strong" in m.value for m in home.markdown)


def test_a_long_inbox_is_drawn_a_batch_at_a_time(phone):
    data.add_leads([logic.clean_lead({"source": "Dice", "title": f"Role {n}", "company": f"Co {n}",
                                      "fit": {"role": 8}})[0]
                    for n in range(config.LEADS_SHOWN + 3)], TODAY)
    at = run(LEADS)
    cards = lambda: sum("**Role " in m.value for m in at.markdown)        # noqa: E731
    assert cards() == config.LEADS_SHOWN
    click(at, "Show 3 more (3 left)")
    assert cards() == config.LEADS_SHOWN + 3
    assert not any(b.label.startswith("Show ") for b in at.button)


def test_a_lead_shows_its_category_ratings_and_the_rules_are_explained(phone):
    seed()
    at = run(LEADS)
    widget(at.radio, "Show").set_value("today").run()
    assert any("Role\u00a05 · Industry\u00a03 · Location\u00a08" in c.value for c in at.caption)
    titles = [m.value for m in at.markdown if "BI Developer" in m.value]
    assert ":blue-badge[5.1/10]" in titles[0]
    widget(at.radio, "Section").set_value("What I'm looking for").run()
    assert any("How scoring works" in m.value for m in at.markdown)
    assert any("Role match** (35%)" in m.value for m in at.markdown)
    assert any("**Pay.**" in m.value and "estimate" in m.value for m in at.markdown)


def test_a_lead_shows_listed_pay_plainly_and_a_warning_when_pay_is_missing_or_estimated(phone):
    seed()
    data.add_leads([logic.clean_lead({
        "source": "Indeed", "title": "Data Engineer", "company": "Epsilon",
        "salary": "$130k-$150k", "pay_source": "estimated",
        "pay_note": "Levels.fyi range, Data Engineer, Denver",
        "fit": {"role": 6, "pay": 8}})[0]], TODAY)
    at = run(LEADS)
    widget(at.radio, "Show").set_value("today").run()
    captions = [c.value for c in at.caption]
    assert any("Analytics Engineer" not in c and "\\$120,000\u2060–\u2060\\$140,000" in c
               for c in captions)
    assert any(":yellow-badge[:material/warning: Pay not listed]" in c for c in captions)
    assert any(":yellow-badge[:material/warning: \\~\\$130,000\u2060–\u2060\\$150,000 (estimate)] · "
               "Levels.fyi range, Data Engineer, Denver" in c for c in captions)


def test_dismissing_a_lead_asks_why_and_restore_brings_it_back(phone):
    seed()
    at = run(LEADS)
    widget(at.radio, "Show").set_value("today").run()
    assert not any(b.label.startswith("Dismiss:") for b in at.button)   # nothing picked yet
    widget(at.multiselect, "Dismiss", 1).select("wrong role").select("too much travel").run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(data.job_leads("new")) == 2                               # picking doesn't dismiss
    click(at, "Dismiss: wrong role, too much travel")
    assert data.job_leads("new")["title"].tolist() == ["Analytics Engineer"]
    gone = data.job_leads("dismissed").iloc[0]
    assert (gone["dismiss_reason"], gone["dismissed_on"]) == ("wrong role, too much travel", TODAY)
    widget(at.radio, "Section").set_value("Dismissed").run()
    assert any(":gray-badge[wrong role] :gray-badge[too much travel] dismissed today" in m.value
               for m in at.markdown)
    click(at, "Restore")
    assert len(data.job_leads("new")) == 2
    assert data.lead(int(gone["lead_id"]))["dismiss_reason"] is None


def test_todays_leads_are_marked_new_and_old_ones_go_stale(phone):
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
    assert widget(at.radio, "Show").value == "today"       # today's come up first
    shown = [m.value for m in at.markdown if "**" in m.value and "—" in m.value]
    assert len(shown) == 2 and all(":blue-badge[New]" in m for m in shown)
    assert not any("Forgotten Engineer" in m for m in shown)
    widget(at.radio, "Show").set_value("all").run()
    shown = [m.value for m in at.markdown if "**" in m.value and "—" in m.value]
    assert len(shown) == 3 and sum(":blue-badge[New]" in m for m in shown) == 2
    assert "Analytics Engineer" in shown[0] and "Yesterday's Analyst" in shown[1]   # best first
    widget(at.radio, "Section").set_value("Stale").run()
    assert any("Forgotten Engineer" in m.value for m in at.markdown)
    home = run(HOME)
    assert any("3 leads in the inbox, 2 new today, 2 strong" in m.value for m in home.markdown)


def test_companies_to_skip_are_saved_with_the_profile():
    seed()
    at = run(LEADS)
    widget(at.radio, "Section").set_value("What I'm looking for").run()
    widget(at.text_area, "Companies to skip").set_value("Robert Half\nTEKsystems").run()
    click(at, "Save")
    assert data.job_profile()["skip_companies"] == "Robert Half\nTEKsystems"
    assert any("**Dismissals.**" in m.value for m in at.markdown)


def test_moving_a_lead_creates_the_application_and_reads_its_posting(monkeypatch, phone):
    import posting
    seed()
    monkeypatch.setattr(posting, "fetch", lambda url: posting.Posting(
        "Analytics Engineer", "Gamma", "Denver, CO", "We need dbt. " * 20))
    at = run(LEADS)
    widget(at.button, "Add").click().run()
    apps = data.applications()
    moved = apps[apps["role"] == "Analytics Engineer"].iloc[0]
    assert (moved["company"], moved["status"]) == ("Gamma", "saved")
    assert data.job_leads("moved")["title"].tolist() == ["Analytics Engineer"]
    saved = data.application(int(moved["application_id"]))
    assert saved["posting"].startswith("Analytics Engineer — Gamma · Denver, CO\n\nWe need dbt.")
    assert saved["apply_url"] is None                          # no Claude key: no search
    assert at.session_state["flash"] == ("Added to Applications as Saved. "
                                         "Posting read (260 characters).")


def test_adding_a_lead_has_claude_find_it_on_the_employers_site(monkeypatch, phone):
    import ai
    import posting
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    seed()
    monkeypatch.setattr(posting, "fetch", lambda url: posting.Posting(
        "Analytics Engineer", "Gamma", "Denver, CO", "We need dbt. " * 20))
    asked = []
    monkeypatch.setattr(ai, "find_posting", lambda *args: asked.append(args) or (
        {"url": "https://boards.greenhouse.io/gamma/jobs/7", "title": "Analytics Engineer",
         "location": "", "note": "Same title on Gamma's Greenhouse board.", "description": ""},
        ai.Usage("claude-opus-5-5", 3000, 500, 2)))
    monkeypatch.setattr(posting, "employer_posting", lambda url: posting.Posting(
        "Analytics Engineer II", "", "Denver, CO", "Gamma's own words. " * 20))
    at = run(LEADS)
    widget(at.button, "Add").click().run()
    app = data.applications().query("role == 'Analytics Engineer'").iloc[0]
    saved = data.application(int(app["application_id"]))
    assert asked[0][:3] == ("Gamma", "Analytics Engineer", None)
    assert asked[0][4].startswith("Analytics Engineer — Gamma")       # the posting just read
    assert saved["apply_url"] == "https://boards.greenhouse.io/gamma/jobs/7"
    assert saved["apply_note"] == ("Listed there as Analytics Engineer II in Denver, CO. Read from "
                                   "the employer's site. Same title on Gamma's Greenhouse board.")
    assert saved["posting"].startswith("Analytics Engineer — Gamma")   # LinkedIn's copy kept
    assert saved["apply_state"] == "found"
    assert at.session_state["flash"].endswith(
        "Posting read (260 characters). Found it on the employer's site: Analytics Engineer II, "
        "Denver, CO ($0.04).")
    assert data.ai_usage_since(TODAY) == (1, 0.042)
    at = new_app(APPS)
    at.session_state["open_application"] = int(app["application_id"])
    at.run()
    assert any(c.value.startswith("Listed there as Analytics Engineer II") for c in at.caption)

    # The application: Apply on the employer's site, Applied today, and a new search.
    monkeypatch.setattr(ai, "find_posting", lambda *args: (
        {"url": "", "title": "", "location": "",
         "note": "Only on LinkedIn, as an Easy Apply posting.", "description": ""},
        ai.Usage("claude-opus-5-5", 3000, 500, 4)))
    click(at, "Find it on the employer's site")
    assert at.success[0].value == ("Not found on the employer's site: Only on LinkedIn, as an "
                                   "Easy Apply posting. ($0.06).")
    missing = data.application(int(app["application_id"]))
    assert (missing["apply_url"], missing["apply_state"]) == (None, "missing")
    assert any(c.value.startswith(":orange-badge[Not on the employer’s site] Only on LinkedIn, "
                                  "as an Easy Apply posting. Apply through the posting")
               for c in at.caption)
    click(at, "Applied today")
    assert at.success[0].value == "Marked as applied today."
    after = data.application(int(app["application_id"]))
    assert (after["status"], after["applied_on"]) == ("applied", TODAY)
    assert data.events(int(app["application_id"]))["note"].tolist()[-1] == "Applied"
    assert not any(b.label == "Applied today" for b in at.button)        # only while Saved


def test_a_glassdoor_lead_gets_its_posting_from_the_employers_site(monkeypatch, phone):
    import ai
    import posting
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    data.add_leads([logic.clean_lead({
        "source": "Glassdoor", "title": "Analytics Enablement Lead", "company": "Targa",
        "fit_score": 9, "job_url": "https://www.glassdoor.com/partner/jobListing.htm?"
                                   "jobListingId=1010305411219"})[0]], TODAY)
    asked = []
    monkeypatch.setattr(ai, "find_posting", lambda *args: asked.append(args) or (
        {"url": "https://targa.example-ats.com/jobs/4079", "title": "Analytics Enablement Lead",
         "location": "Houston, Texas", "note": "Same title on Targa's careers site.",
         "description": "POSITION SUMMARY\nTarga is seeking a lead. " * 10},
        ai.Usage("claude-sonnet-5-5", 24000, 2500, 3)))
    monkeypatch.setattr(posting, "employer_posting", lambda url: None)   # no data on the page
    at = run(LEADS)
    widget(at.button, "Add").click().run()
    assert asked[0][4] == ""                                  # Glassdoor gave nothing to send
    app = data.applications().query("company == 'Targa'").iloc[0]
    saved = data.application(int(app["application_id"]))
    assert saved["posting"].startswith("Analytics Enablement Lead — Targa · Houston, Texas\n\n"
                                       "POSITION SUMMARY\nTarga is seeking a lead.")
    flash = at.session_state["flash"]
    assert "Posting not read" not in flash                     # the employer's site filled it
    assert flash.endswith("Posting copied from there by Claude: check it before tailoring.")

    # Data on the employer's page wins over Claude's copy; a posting on hand is never replaced.
    monkeypatch.setattr(posting, "employer_posting", lambda url: posting.Posting(
        "Analytics Enablement Lead", "", "Houston, TX", "Targa's own words. " * 20))
    data.update_application(int(app["application_id"]), posting="")
    notes = ui_find(app["application_id"])
    assert notes[0].endswith("Posting read from there.")
    assert data.application(int(app["application_id"]))["posting"].startswith(
        "Analytics Enablement Lead · Houston, TX\n\nTarga's own words.")
    notes = ui_find(app["application_id"])
    assert not notes[0].endswith("Posting read from there.")  # already had one: left alone


def ui_find(application_id) -> list[str]:
    import ui
    return ui.find_company_posting(data.application(int(application_id)), TODAY)


def test_the_application_says_where_the_employer_site_search_stands(monkeypatch):
    import ai
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    app_id = data.add_application(data.company_id_for("Acme", TODAY), "Analyst", "saved", TODAY)
    at = new_app(APPS)
    at.session_state["open_application"] = app_id
    at.run()
    assert any(c.value == "Not looked for on the employer's site yet." for c in at.caption)

    data.update_application(app_id, apply_state="looking", apply_note="Looking since 9:49 AM.")
    at = new_app(APPS)
    at.session_state["open_application"] = app_id
    at.run()                                                   # a search running elsewhere
    assert any(c.value.startswith(":blue-badge[Looking on the employer’s site] Looking since "
                                  "9:49 AM. It usually takes a minute or two") for c in at.caption)

    monkeypatch.setattr(ai, "find_posting", lambda *args: (_ for _ in ()).throw(
        ai.AIError("Claude is rate-limiting this key; try again in a minute.")))
    click(at, "Find it on the employer's site")
    assert at.success[0].value == ("Couldn't look for it on the employer's site: Claude is "
                                   "rate-limiting this key; try again in a minute.")
    failed = data.application(app_id)
    assert (failed["apply_state"], failed["apply_note"]) == (
        "failed", "Claude is rate-limiting this key; try again in a minute.")
    assert any(c.value.startswith(":red-badge[Search didn’t finish] Claude is rate-limiting")
               for c in at.caption)

    widget(at.radio, "Section").set_value("Edit").run()        # found it yourself: paste it
    widget(at.text_input, "Employer's apply link").set_value("https://acme.com/careers/7")
    click(at, "Save changes")
    pasted = data.application(app_id)
    assert (pasted["apply_url"], pasted["apply_state"], pasted["apply_note"]) == (
        "https://acme.com/careers/7", "found", "Link pasted by you.")
    assert any(b.label == "Apply on Acme's site" for b in at.get("link_button"))
    assert any(c.value == "Link pasted by you." for c in at.caption)
    widget(at.radio, "Section").set_value("Edit").run()
    widget(at.text_input, "Role").set_value("Senior Analyst")  # other edits leave it alone
    click(at, "Save changes")
    assert data.application(app_id)["apply_state"] == "found"
    widget(at.radio, "Section").set_value("Edit").run()
    widget(at.text_input, "Employer's apply link").set_value("")
    click(at, "Save changes")
    cleared = data.application(app_id)
    assert (cleared["apply_url"], cleared["apply_state"], cleared["apply_note"]) == (
        None, None, None)


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


def test_weak_leads_are_hidden_until_asked_for(phone):
    seed()
    data.add_leads([logic.clean_lead({
        "source": "Indeed", "title": "Excel Reporting Clerk", "company": "Epsilon",
        "fit_score": 2, "fit_reason": "Pure Excel reporting: a deal-breaker."})[0]], TODAY)
    at = run(LEADS)
    assert any("3 new leads: 3 today, 1 strong (fit 8+), 1 weak (under 4)." in c.value
               for c in at.caption)
    widget(at.radio, "Show").set_value("today").run()
    shown = " ".join(m.value for m in at.markdown)           # New today: weak ones wait
    assert "Analytics Engineer" in shown and "BI Developer" in shown
    assert "Excel Reporting Clerk" not in shown
    widget(at.radio, "Show").set_value("all").run()
    shown = " ".join(m.value for m in at.markdown)
    assert "Excel Reporting Clerk" in shown and "Pure Excel reporting" in shown
    widget(at.radio, "Show").set_value("weak").run()          # to clear them out in one go
    shown = " ".join(m.value for m in at.markdown)
    assert "Excel Reporting Clerk" in shown and "Analytics Engineer" not in shown


def test_todays_glassdoor_links_open_the_right_form(phone):
    data.add_leads([logic.clean_lead({
        "source": "Glassdoor", "title": "Analyst", "company": "Zeta", "fit_score": 8})[0]], TODAY)
    lead_id = int(data.job_leads()["lead_id"][0])
    with psycopg.connect(os.environ["TEST_DATABASE_URL"], autocommit=True) as conn:
        conn.execute("update job_leads set job_url = %s where lead_id = %s",
                     ("https://www.glassdoor.com/job-listing?jl=1010293120973", lead_id))
    at = run(LEADS)
    assert any("partner/jobListing.htm?jobListingId=1010293120973" in m.value
               for m in at.markdown)


RESUME = ROOT / "app" / "pages" / "3_Resume_and_Projects.py"


def test_resume_page_draws_empty_and_says_whether_claude_has_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = run(RESUME)
    assert any("No master resume yet" in h.value for h in at.get("html"))
    widget(at.radio, "Section").set_value("Build from files").run()
    assert any(":red-badge[No key]" in m.value for m in at.markdown)
    assert any("No files yet" in h.value for h in at.get("html"))
    assert widget(at.button, "Build the master with Claude").disabled
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Build from files").run()
    assert any(":green-badge[Key found]" in m.value for m in at.markdown)
    assert any("$0.00 this month across 0 Claude calls" in m.value for m in at.markdown)


def test_resume_page_shows_the_master_and_exports_it_in_the_templates_layout():
    import docx_fixture
    import docx_io
    source = data.add_resume_source("Resume.docx", "resume", "## Sample", docx_fixture.template(),
                                    TODAY)
    data.set_resume_template(source, TODAY)
    data.save_resume_master({**docx_fixture.SAMPLE, "conflicts": ["GPA: 3.88 in the history, "
                                                                  "3.90 on the resume"]}, TODAY)
    at = run(RESUME)
    assert any("2 of 2 roles and 1 of 1 project print on the master, with 3 bullets; 1 more "
               "wait in the pool" in c.value for c in at.caption)
    assert any("GPA: 3.88" in m.value for m in at.markdown)
    assert widget(at.text_input, "Name").value == "Sample Person"
    assert [w.value for w in at.text_input if w.label == "Employer"] == ["Acme Energy",
                                                                         "Beta Chemicals"]
    download = [b for b in at.get("download_button")]
    assert download and download[0].label == "Download Word file"
    texts = [p.text for p in docx_io.outline(docx_io.build(data.resume_template(),
                                                           data.resume_master()["content"]))]
    assert "Built a pipeline that saved 2 hours a day." in texts
    widget(at.text_input, "Name").set_value("Sample P. Person").run()
    click(at, "Save")
    master = data.resume_master()
    assert master["content"]["name"] == "Sample P. Person"
    assert master["content"]["conflicts"] == ["GPA: 3.88 in the history, 3.90 on the resume"]
    widget(at.checkbox, "Clear the conflicts list: I've checked them").check().run()
    click(at, "Save")
    assert data.resume_master()["content"]["conflicts"] == []
    click(at, "Add a role")
    assert len(data.resume_master()["content"]["roles"]) == 3
    widget(at.checkbox, "Remove this role", -1).check()                # the one just added
    widget(at.checkbox, "Remove this project").check()
    click(at, "Save")
    content = data.resume_master()["content"]
    assert [r["employer"] for r in content["roles"]] == ["Acme Energy", "Beta Chemicals"]
    assert content["projects"] == []
    assert not any(w.value for w in at.checkbox if w.label == "Remove this role")   # fresh form


def test_building_the_master_lands_on_the_master_section(monkeypatch):
    import ai
    import docx_fixture
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    data.add_resume_source("Resume.docx", "resume", "## Sample", docx_fixture.template(), TODAY)
    monkeypatch.setattr(ai, "structure_resume",
                        lambda texts: (docx_fixture.SAMPLE, ai.Usage("claude-opus-5-5", 6000, 8000)))
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Build from files").run()
    click(at, "Build the master with Claude")
    assert widget(at.radio, "Section").value == "Master"
    assert any("Built the master: 2 roles, 3 bullets on it, 1 in the pool, 0 conflicts to check. "
               "Cost $0.18." in s.value for s in at.success)
    assert data.resume_master()["content"]["name"] == "Sample Person"
    assert data.ai_usage_since(TODAY)[0] == 1


def test_tailor_section_waits_for_a_master_and_an_open_application():
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Resume Builder").run()
    assert any("No master resume yet" in h.value for h in at.get("html"))
    import docx_fixture
    data.save_resume_master(docx_fixture.SAMPLE, TODAY)
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Resume Builder").run()
    assert any("No open applications" in h.value for h in at.get("html"))


TAILORED = {
    "fit_notes": "Strong on SQL; no Tableau.",
    "roles": [{"employer": "Acme Energy", "title": "Business Analyst", "location": "Denver, CO",
               "start": "Jan 2025", "end": "Present", "bullets": [
                   {"text": "Built a SQL pipeline that saved 2 hours a day.",
                    "original": "Built a pipeline that saved 2 hours a day.", "skills": ["SQL"]}]}],
    "projects": [], "skill_groups": [{"name": "Programming Languages", "skills": "SQL, Python"}],
    "keywords": [{"term": "SQL", "covered": True, "where": "the pipeline bullet"},
                 {"term": "Tableau", "covered": False, "where": ""}],
    "changes": ["Named SQL in the pipeline bullet: the posting leads with it."],
    "cover_letter": "Dear Hiring Team,\n\nI built the pipeline.\n\nSincerely,\nSample Person",
}


def test_tailor_section_makes_a_version_with_both_downloads_and_saves_edits(monkeypatch):
    import ai
    import docx_fixture
    import docx_io
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    source = data.add_resume_source("Resume.docx", "resume", "## Sample", docx_fixture.template(),
                                    TODAY)
    data.set_resume_template(source, TODAY)
    data.save_resume_master(docx_fixture.SAMPLE, TODAY)
    app_id = data.add_application(data.company_id_for("Acme Corp.", TODAY), "Analyst", "saved",
                                  TODAY)
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Resume Builder").run()
    assert widget(at.button, "Tailor with Claude").disabled          # no posting yet
    widget(at.text_area, "Job posting").set_value("We need SQL and Tableau.")
    click(at, "Save posting")
    assert data.application(app_id)["posting"] == "We need SQL and Tableau."
    assert not widget(at.button, "Tailor with Claude").disabled
    calls = []
    monkeypatch.setattr(ai, "tailor", lambda *args: calls.append(args) or (
        TAILORED, ai.Usage("claude-opus-5-5", 6000, 8000)))
    widget(at.text_input, "Steer Claude (optional)").set_value("lead with SQL")
    click(at, "Tailor with Claude")
    assert calls[0][1:] == ("We need SQL and Tableau.", "Acme Corp.", "Analyst", TODAY,
                            "lead with SQL")
    assert any("Tailored for Acme Corp.: 1 bullet, 1 of 2 keywords covered. Cost $0.18." in s.value
               for s in at.success)
    assert [b.label for b in at.get("download_button")] == ["Download tailored resume",
                                                            "Download cover letter"]
    assert any(":green-badge[SQL] :orange-badge[Tableau]" in m.value for m in at.markdown)
    assert any("1 bullet: 0 as on the master, 1 reworded" in c.value for c in at.caption)
    assert data.ai_usage_since(TODAY)[0] == 1
    version = data.tailored_versions(app_id).iloc[0]
    assert (version["version"], version["notes"]) == (1, "lead with SQL")
    export = docx_io.build(data.resume_template(), logic.tailored_export(
        docx_fixture.SAMPLE, data.tailored(int(version["tailor_id"]))["content"]))
    texts = [p.text for p in docx_io.outline(export)]
    assert "Built a SQL pipeline that saved 2 hours a day." in texts
    assert "Beta Chemicals" not in texts                              # not in the tailored set
    widget(at.text_area, "Cover letter").set_value("Dear Hiring Team,\n\nEdited.")
    click(at, "Save")
    saved = data.tailored(int(version["tailor_id"]))["content"]
    assert saved["cover_letter"] == "Dear Hiring Team,\n\nEdited."
    assert saved["roles"][0]["bullets"][0]["original"] == "Built a pipeline that saved 2 hours a day."


def test_a_tailored_version_longer_than_the_master_gets_a_warning():
    import docx_fixture
    data.save_resume_master(docx_fixture.SAMPLE, TODAY)
    app_id = data.add_application(data.company_id_for("Acme Corp.", TODAY), "Analyst", "saved",
                                  TODAY, posting="We need SQL.")
    long = {**TAILORED, "roles": [{**TAILORED["roles"][0], "bullets": [
        {"text": f"Bullet {n} " * 12, "original": "", "skills": []} for n in range(3)]}]}
    tailor_id = data.add_tailored(app_id, logic.clean_tailored(long), None, "m", TODAY)
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Resume Builder").run()
    assert any("Longer than the master" in w.value for w in at.warning)   # 8 lines against 6
    click(at, "Trim to one page")
    assert any("Trimmed to one page: 1 bullet left off." in s.value for s in at.success)
    assert not at.warning
    saved = data.tailored(tailor_id)["content"]
    assert [b["text"][:8] for b in saved["roles"][0]["bullets"]] == ["Bullet 0", "Bullet 1"]
    assert saved["changes"][-1].startswith("Left off the last bullet under Acme Energy")


def test_the_header_doesnt_repeat_a_remote_location():
    app_id = data.add_application(data.company_id_for("Acme", TODAY), "Analyst", "applied", TODAY,
                                  location="Remote", work_mode="remote", source="LinkedIn")
    at = new_app(APPS)
    at.session_state["open_application"] = app_id
    at.run()
    assert any(m.value.endswith("applied today · Remote · LinkedIn") for m in at.markdown)


def test_the_tailor_section_keeps_its_application_across_sections():
    import docx_fixture
    data.save_resume_master(docx_fixture.SAMPLE, TODAY)
    first = data.add_application(data.company_id_for("Acme", TODAY), "Analyst", "saved", TODAY)
    second = data.add_application(data.company_id_for("Beta", TODAY), "PM", "saved", TODAY)
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Resume Builder").run()
    widget(at.selectbox, "Application").set_value(first).run()
    assert widget(at.selectbox, "Application").value == first
    widget(at.radio, "Section").set_value("Master").run()
    widget(at.radio, "Section").set_value("Resume Builder").run()
    assert widget(at.selectbox, "Application").value == first      # not back to the newest
    at.session_state["tailor_application"] = second                 # sent from Applications
    widget(at.radio, "Section").set_value("Resume Builder").run()
    assert widget(at.selectbox, "Application").value == second


def test_the_posting_can_be_read_from_the_link_or_the_error_says_to_paste(monkeypatch):
    import docx_fixture
    import posting
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")        # so only the posting gates Tailor
    data.save_resume_master(docx_fixture.SAMPLE, TODAY)
    app_id = data.add_application(data.company_id_for("Acme", TODAY), "Analyst", "saved", TODAY,
                                  job_url="https://www.linkedin.com/jobs/view/123/")
    monkeypatch.setattr(posting, "fetch", lambda url: posting.Posting(
        "Analyst II", "Acme Corp", "Denver, CO", "We need SQL. " * 20))
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Resume Builder").run()
    assert widget(at.button, "Tailor with Claude").disabled
    click(at, "Get the posting from the link")
    saved = data.application(app_id)["posting"]
    assert saved.startswith("Analyst II — Acme Corp · Denver, CO\n\nWe need SQL.")
    assert any("Read the posting from the job link: Analyst II, 260 characters." in s.value
               for s in at.success)
    assert widget(at.text_area, "Job posting").value == saved
    assert not widget(at.button, "Tailor with Claude").disabled

    def refused(url):
        raise posting.PostingError("Indeed doesn't let the app read its postings: paste it.")
    monkeypatch.setattr(posting, "fetch", refused)
    click(at, "Get the posting from the link")
    assert at.error[0].value.startswith("Indeed doesn't let the app read")
    assert data.application(app_id)["posting"] == saved                   # kept

    # With the employer's link found, the employer's own data comes first.
    data.update_application(app_id, apply_url="https://acme.wd1.myworkdayjobs.com/x/job/D/A_1")
    monkeypatch.setattr(posting, "employer_posting", lambda url: posting.Posting(
        "Analyst II", "", "Omaha, NE", "Acme's own words. " * 20))
    click(at, "Get the posting from the link")
    assert data.application(app_id)["posting"].startswith("Analyst II · Omaha, NE\n\nAcme's own")
    assert any("Read the posting from Acme's site: Analyst II, 360 characters." in s.value
               for s in at.success)


def test_the_posting_section_offers_the_link_only_when_there_is_one():
    app_id = seed()                                                        # no job link
    at = new_app(APPS)
    at.session_state["open_application"] = app_id
    at.run()
    widget(at.radio, "Section").set_value("Posting").run()
    assert not any(b.label == "Get the posting from the link" for b in at.button)
    data.update_application(app_id, apply_url="https://acme.com/careers/9")   # the employer's
    at.run()
    assert any(b.label == "Get the posting from the link" for b in at.button)


def test_an_application_shows_its_resume_flag_and_opens_resume_builder():
    app_id = seed()
    at = new_app(APPS)
    at.session_state["open_application"] = app_id
    at.run()
    table = at.dataframe[0].value
    assert "resume" in table.columns and not table["resume"].any()
    assert not any("Resume ready" in m.value for m in at.markdown)
    data.add_tailored(app_id, {"roles": [], "cover_letter": "Dear"}, None, "m", TODAY)
    at.run()
    assert at.dataframe[0].value.set_index("role").loc["Data Analyst", "resume"]
    assert any(":green-badge[Resume ready] 1 tailored version with cover letter" in m.value
               for m in at.markdown)
    widget(at.button, "Resume Builder").click().run()     # the page switch itself is outside AppTest
    assert at.session_state["tailor_application"] == app_id
    assert at.session_state["resume_goto"] == "Resume Builder"


def test_the_posting_section_saves_the_job_posting():
    app_id = seed()
    at = new_app(APPS)
    at.session_state["open_application"] = app_id
    at.run()
    widget(at.radio, "Section").set_value("Posting").run()
    assert widget(at.button, "Tailor the resume for this job").disabled
    widget(at.text_area, "Job posting").set_value("  A long posting.  ")
    click(at, "Save posting")
    assert data.application(app_id)["posting"] == "A long posting."
    assert not widget(at.button, "Tailor the resume for this job").disabled


SPREADSHEET = """Project: Rates tool
Company: AE
Rank: 5
Situation: Rates came by email and schedulers retyped every one of them each week by hand.
Task: Own the rates tool.
Action: Rebuilt the VBA tool as a Python web app with validation, an audit trail and accounting
integration, then trained the schedulers on it and retired the spreadsheet.
Result: Rate updates went from 6 hours to 20 minutes a week.
Skills: Python, MySQL

Project: Valve study
Company: Beta
Situation: Leaks."""


def test_projects_import_score_review_and_feed_the_master(monkeypatch):
    import ai
    import docx_fixture
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    data.save_resume_master(docx_fixture.SAMPLE, TODAY)
    data.add_resume_source("Projects.csv", "projects", SPREADSHEET, None, TODAY)
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Projects").run()
    assert not at.exception
    click(at, "Import 2 projects from your projects spreadsheet (free)")
    bank = data.projects().set_index("title")
    assert bank.loc["Rates tool", "employer"] == "Acme Energy"             # "AE"
    assert bank.loc["Valve study", "employer"] == "Beta Chemicals"
    assert not any(b.label.startswith("Import") for b in at.button)       # nothing left to import
    assert any(m.value == ":green-badge[1 strong] :red-badge[1 need detail]"   # no "0 thin"
               for m in at.markdown)
    assert at.dataframe[0].value["Project"].tolist() == ["Valve study", "Rates tool"]  # weakest first
    valves, rates = int(bank.loc["Valve study", "project_id"]), int(bank.loc["Rates tool",
                                                                             "project_id"])
    assert widget(at.selectbox, "Project").value == valves
    assert any(c.value.startswith("To strengthen it, add: the problem or why it mattered "
                                  "(Situation); what you were responsible for (Task)")
               for c in at.caption)

    widget(at.selectbox, "Project").set_value(rates).run()
    widget(at.text_area, "Task: what you were responsible for").set_value("Owned it end to end.")
    click(at, "Save")
    assert data.project(rates)["task"] == "Owned it end to end."

    calls = []

    def review(project, answers, style, targets):
        calls.append((project["title"], answers, style["samples"]))
        action = project["action"] + (" It now serves 12 schedulers." if answers else "")
        return ({"strength": 6, "verdict": "Clear work.", "questions": ["How many people use it?"],
                 "bullets": ["Rebuilt the rates tool, saving [X hours] a week",
                             "Rebuilt the freight-rate tool in Python, cutting weekly updates "
                             "from 6 hours to 20 minutes"],
                 "skills": ["Python", "MySQL"],
                 "details": {"situation": project["situation"], "task": project["task"],
                             "action": action, "result": project["result"]}},
                ai.Usage("claude-opus-5-5", 6000, 8000))
    monkeypatch.setattr(ai, "review_project", review)
    click(at, "Review with Claude")
    assert calls[0] == ("Rates tool", [], ["Built a pipeline that saved 2 hours a day."])
    assert at.success[0].value == "Claude rates it 6/10. Cost $0.18."
    saved = data.project(rates)
    assert saved["review"]["strength"] == 6 and "before" not in saved["review"]
    assert saved["action"].endswith("retired the spreadsheet.")             # no answers: unchanged
    assert data.ai_usage_since(TODAY) == (1, 0.184)
    assert any(":blue-badge[Claude: 6/10] Clear work." in m.value for m in at.markdown)

    click(at, "Work my answers in")                                        # nothing answered
    assert at.error[0].value == "Answer at least one question first." and len(calls) == 1
    widget(at.text_area, "How many people use it?").set_value("Twelve schedulers.")
    click(at, "Work my answers in")
    assert calls[1][1] == [("How many people use it?", "Twelve schedulers.")]
    assert at.success[0].value == ("Claude rates it 6/10, and worked your answers into action. "
                                   "Cost $0.18.")
    assert data.project(rates)["action"].endswith("It now serves 12 schedulers.")
    click(at, "Undo Claude's last change to the details")
    assert data.project(rates)["action"].endswith("retired the spreadsheet.")
    assert "before" not in data.project(rates)["review"]

    assert widget(at.button, "Use it and add to the master's pool").disabled  # [X hours] to fill
    widget(at.button, "Use this").click().run()
    assert data.project(rates)["bullet"] == "Rebuilt the rates tool, saving [X hours] a week"
    widget(at.button, "Use it and add to the master's pool", 1).click().run()
    assert not at.exception
    bullet = data.project(rates)["bullet"]
    assert bullet.startswith("Rebuilt the freight-rate tool in Python")
    assert at.success[0].value.startswith("Added to the master's pool under Acme Energy — "
                                          "Business Analyst.")
    pool = data.resume_master()["content"]["roles"][0]["bullets"][-1]
    assert (pool["text"], pool["source"], pool["rank"], pool["in_master"]) == (
        bullet, "project", 3, False)
    assert any(m.value.startswith(":blue-badge[In the master's pool]") for m in at.markdown)

    click(at, "Add a project")
    widget(at.text_input, "Project").set_value("Budget app")
    widget(at.selectbox, "Where").set_value("Personal project")
    click(at, "Add")
    budget_id = int(data.projects().set_index("title").loc["Budget app", "project_id"])
    budget = data.project(budget_id)
    assert (budget["kind"], budget["employer"]) == ("personal", None)
    assert widget(at.selectbox, "Project").value == budget_id                 # opened
    assert any(m.value.endswith("**Budget app**") for m in at.markdown)
    widget(at.checkbox, "I want to delete this project").check().run()
    click(at, "Delete project")
    assert "Budget app" not in data.projects()["title"].tolist()


def test_projects_draws_empty_and_without_a_claude_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Projects").run()
    assert not at.exception and not at.dataframe
    data.add_project(TODAY, kind="personal", title="Budget app", summary="A budget.")
    at.run()
    assert any(c.value == "Needs the Claude key: see Build from files." for c in at.caption)
    assert not any(b.label == "Review with Claude" for b in at.button)


def test_resume_sources_are_listed_with_the_template_marked_and_can_be_removed():
    import docx_fixture
    source = data.add_resume_source("Resume.docx", "resume", "## Sample", docx_fixture.template(),
                                    TODAY)
    data.set_resume_template(source, TODAY)
    data.add_resume_source("Projects.csv", "projects", "Project: x", None, TODAY)
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Build from files").run()
    listed = [m.value for m in at.markdown if "**" in m.value and ".docx" in m.value
              or ".csv" in m.value]
    assert any(":green-badge[Template]" in m and "Resume.docx" in m for m in listed)
    assert any(":blue-badge[Projects spreadsheet]" in m for m in listed)
    widget(at.checkbox, "I want to delete this file").check().run()      # newest first: the CSV
    widget(at.button, "Delete file").click().run()
    assert data.resume_sources()["filename"].tolist() == ["Resume.docx"]


# ---- phone and computer -----------------------------------------------------------

def test_home_on_a_computer_adds_the_best_leads_and_the_pipeline():
    seed()
    at = run(HOME)                                          # no browser: the computer layout
    assert any(h.value == "Pipeline" for h in at.subheader)
    assert any(m.value.startswith(":green-badge[9/10] Analytics Engineer — Gamma")
               for m in at.markdown)                         # the best lead waiting
    assert any(m.value == ":blue-badge[Applied] **1**  :violet-badge[Interviewing] **1**"
               or ("[Applied] **1**" in m.value and "[Interviewing] **1**" in m.value)
               for m in at.markdown)
    assert [m.label for m in at.metric][-2:] == ["Applied this week", "Interviews, 2 weeks"]


def test_home_on_a_phone_keeps_to_the_inbox_and_what_needs_doing(phone):
    seed()
    at = run(HOME)
    assert not any(h.value == "Pipeline" for h in at.subheader)
    assert any(h.value == "Needs attention" for h in at.subheader)


def test_a_computer_opens_an_application_by_clicking_its_row():
    quiet = seed()
    at = run(APPS)
    assert any("Pick an application" in h.value for h in at.get("html"))
    row = at.dataframe[0].value["company"].tolist().index("Acme")
    at.session_state["apps_table_0"] = {"selection": {"rows": [row], "columns": []}}
    at.run()
    assert not at.exception
    assert widget(at.selectbox, "Open an application").value == quiet
    assert any(m.value.startswith("### Acme — Data Analyst") for m in at.markdown)


def test_a_phone_picks_an_application_from_the_list_without_the_table(phone):
    seed()
    at = run(APPS)
    assert not at.dataframe
    assert widget(at.selectbox, "Open an application").value is None


def test_a_computer_sees_the_inbox_as_a_table_and_acts_on_several_leads(monkeypatch):
    import ui as page_ui
    data.add_leads([logic.clean_lead({"source": "LinkedIn", "title": f"Analyst {n}",
                                      "company": f"Co {n}", "fit": {"role": 9 - n % 3},
                                      "salary": "$120k-$140k"})[0] for n in range(10)], TODAY)
    at = run(LEADS)
    assert at.dataframe and not any(r.label == "View" for r in at.radio)    # always the table
    widget(at.radio, "Show").set_value("all").run()
    table = at.dataframe[0].value
    assert len(table) == 10 and table["pay"].iloc[0] == "$120k–$140k"
    assert any(c.value.startswith("Click a heading to sort.") for c in at.caption)

    titles = table["title"].tolist()

    def tick(rows):            # a browser sends the ticks with every rerun; the harness doesn't
        turn = at.session_state["leads_table_round"] if "leads_table_round" in at.session_state \
            else 0
        at.session_state[f"leads_table_{turn}_all"] = {"selection": {"rows": rows,
                                                                       "columns": []}}

    tick([0, 1])
    at.run()
    assert any(m.value == "**2 leads selected**" for m in at.markdown)
    assert sum("**" in m.value and "Analyst" in m.value for m in at.markdown) >= 2   # their cards
    tick([0, 1])
    widget(at.multiselect, "Dismiss the selected").set_value(["wrong role", "pay"]).run()
    tick([0, 1])
    click(at, "Dismiss 2 leads: wrong role, pay")
    gone = data.job_leads("dismissed")
    assert sorted(gone["title"]) == sorted(titles[:2])
    assert set(gone["dismiss_reason"]) == {"wrong role, pay"}

    monkeypatch.setattr(page_ui, "prepare_application", lambda app_id, today: ["Searched."])
    tick([0])
    at.run()
    tick([0])
    click(at, "Add 1 lead to Applications")
    assert at.success[0].value == "Added 1 lead to Applications as Saved. Searched."
    assert data.applications()["role"].tolist() == [titles[2]]

    tick(list(range(4)))
    at.run()
    assert not widget(at.button, "Add 4 leads to Applications").disabled
    tick(list(range(6)))
    at.run()
    assert widget(at.button, "Add 6 leads to Applications").disabled     # over the limit
    tick([0, 99])                                         # a stale tick past the end: ignored
    at.run()
    assert not at.exception and any(m.value == "**1 lead selected**" for m in at.markdown)
    assert any(b.label == "Add" for b in at.button)          # the ticked one's card, below


def test_a_computer_opens_a_project_by_clicking_its_row():
    first = data.add_project(TODAY, kind="work", title="Alpha", summary="A.")
    second = data.add_project(TODAY, kind="work", title="Beta", summary="B.")
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Projects").run()
    row = at.dataframe[0].value["Project"].tolist().index("Beta")
    at.session_state["projects_table_0"] = {"selection": {"rows": [row], "columns": []}}
    at.run()
    assert not at.exception
    assert widget(at.selectbox, "Project").value == second != first


def test_a_phone_leaves_the_wide_resume_editing_to_the_computer(phone):
    import docx_fixture
    data.save_resume_master(docx_fixture.SAMPLE, TODAY)
    at = run(RESUME)
    assert any("Edit the master on your computer" in h.value for h in at.get("html"))
    assert not any(w.label == "Name" for w in at.text_input)          # no editing grids
    widget(at.radio, "Section").set_value("Build from files").run()
    assert any("Build from files on your computer" in h.value for h in at.get("html"))
    assert not at.get("file_uploader")


def test_claude_powered_buttons_carry_the_claude_mark(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    seed()
    monkeypatch.setattr(ui, "device", lambda: "phone")             # lead cards
    at = run(LEADS)
    assert any(b.label == "Add" for b in at.button)
    assert all(b.key.startswith("claude_move_") for b in at.button if b.label == "Add")
    monkeypatch.setattr(ui, "device", lambda: "computer")
    at = run(RESUME)
    widget(at.radio, "Section").set_value("Build from files").run()
    assert widget(at.button, "Test connection (free)").key == "claude_ping"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setattr(ui, "device", lambda: "phone")
    at = run(LEADS)
    assert all(b.key.startswith("move_") for b in at.button if b.label == "Add")   # no key: plain

