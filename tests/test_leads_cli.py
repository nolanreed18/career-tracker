"""leads.py as the daily job-alert review runs it."""

import json
from datetime import timedelta

import pytest

import config
import data
import leads
import logic


@pytest.fixture(autouse=True)
def _db(database):
    return database


def test_profile_prints_what_youre_looking_for_and_recent_dismissals(capsys):
    assert leads.main(["profile"]) == 0
    assert json.loads(capsys.readouterr().out) == {"dismissed_recently": []}
    data.save_job_profile(data.today(), target_roles="Data Analyst", min_salary=95000,
                          skip_companies="Robert Half")
    data.add_leads([logic.clean_lead({"source": "Dice", "title": "Clerk", "company": "Acme",
                                      "location": "Omaha, NE"})[0]], data.today())
    data.set_lead_status(int(data.job_leads()["lead_id"][0]), "dismissed", "location",
                         data.today())
    assert leads.main(["profile"]) == 0
    profile = json.loads(capsys.readouterr().out)
    assert profile["target_roles"] == "Data Analyst" and profile["min_salary"] == 95000
    assert profile["skip_companies"] == "Robert Half"
    assert profile["dismissed_recently"] == [{
        "title": "Clerk", "company": "Acme", "location": "Omaha, NE", "reason": "location",
        "dismissed_on": data.today().isoformat()}]


def test_rubric_prints_the_scoring_categories(capsys):
    assert leads.main(["rubric"]) == 0
    rubric = json.loads(capsys.readouterr().out)
    assert [c["key"] for c in rubric["categories"]] == list(config.FIT_CATEGORIES)
    assert sum(c["weight"] for c in rubric["categories"]) == pytest.approx(1)
    assert rubric["strong_fit"] == config.STRONG_FIT
    assert rubric["today"] == data.today().isoformat()      # the owner's date, for the digest


def test_add_stores_new_leads_and_skips_ones_already_seen(tmp_path, capsys):
    file = tmp_path / "leads.json"
    file.write_text(json.dumps([
        {"source": "Dice", "title": "Data Engineer", "company": "Beta",
         "salary": "$130k-$150k", "pay_source": "estimated",
         "pay_note": "Glassdoor range, Data Engineer, Denver",
         "fit": {"role": 8, "industry": 7, "location": 6, "pay": 7, "level": 8, "extras": 5},
         "deal_breaker": False},
        {"source": "Indeed", "title": "Analyst", "company": "Acme", "salary": "$100k"},
    ]))
    assert leads.main(["add", str(file)]) == 0
    assert "added 2, skipped 0" in capsys.readouterr().out
    stored = data.job_leads()
    beta = stored[stored["company"] == "Beta"].iloc[0]
    assert float(beta["fit_score"]) == 7.2 and beta["fit_detail"]["ratings"]["role"] == 8
    assert (beta["pay_source"], beta["salary_max"]) == ("estimated", 150000)
    assert stored[stored["company"] == "Acme"].iloc[0]["pay_source"] == "listed"
    assert leads.main(["add", str(file)]) == 0
    assert "added 0, skipped 2" in capsys.readouterr().out
    assert leads.main(["known"]) == 0
    assert capsys.readouterr().out.splitlines() == ["acme|analyst", "beta|data engineer"]


def test_jobs_from_companies_to_skip_are_dropped(tmp_path, capsys):
    data.save_job_profile(data.today(), target_roles="Analyst",
                          skip_companies="Robert Half\nTEKsystems")
    file = tmp_path / "leads.json"
    file.write_text(json.dumps([
        {"source": "Dice", "title": "Analyst", "company": "Robert Half Technology"},
        {"source": "Dice", "title": "Analyst", "company": "Acme"},
    ]))
    assert leads.main(["add", str(file)]) == 0
    assert "added 1, skipped 0 already seen, dropped 1 from companies to skip" in (
        capsys.readouterr().out)
    assert data.job_leads()["company"].tolist() == ["Acme"]


def test_one_bad_row_means_nothing_is_added(tmp_path, capsys):
    file = tmp_path / "leads.json"
    file.write_text(json.dumps([
        {"source": "Dice", "title": "Data Engineer", "company": "Beta"},
        {"source": "Dice", "title": "No company"},
    ]))
    assert leads.main(["add", str(file)]) == 1
    assert "nothing added" in capsys.readouterr().err
    assert data.job_leads().empty
    file.write_text(json.dumps([              # pay rated with no salary to rate it against
        {"source": "Dice", "title": "Data Engineer", "company": "Beta", "fit": {"pay": 5}},
    ]))
    assert leads.main(["add", str(file)]) == 1
    assert "leave pay out" in capsys.readouterr().err
    assert data.job_leads().empty


def test_rubric_spells_out_the_pay_rules(capsys):
    assert leads.main(["rubric"]) == 0
    rubric = json.loads(capsys.readouterr().out)
    assert rubric["pay"]["sources"] == config.PAY_SOURCES
    assert "estimate" in rubric["pay"]["rule"] and rubric["pay"]["research"] == config.PAY_RESEARCH


def test_digest_renders_todays_leads_and_what_needs_doing(tmp_path, capsys):
    today = data.today()
    data.add_leads([logic.clean_lead({
        "source": "LinkedIn", "title": "Analytics Engineer", "company": "Gamma",
        "location": "Denver, CO", "job_url": "https://example.com/j/1",
        "fit": {"role": 9, "industry": 8, "location": 10, "level": 7, "extras": 6},
        "fit_reason": "Strong on role; pay unknown"})[0]], today)
    acme = data.company_id_for("Acme", today)
    data.add_application(acme, "Data Analyst", "applied", today, next_action="Chase recruiter",
                         next_action_on=today)
    data.add_leads([logic.clean_lead({                     # a strong lead from two days ago
        "source": "Dice", "title": "BI Developer", "company": "Delta", "fit_score": 8.5})[0]],
        today - timedelta(days=2))
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"app_url": "https://tracker.example.app/", "emails_read": 3,
                               "sources": {"LinkedIn": 3}, "already_known": 1}))
    assert leads.main(["digest", str(run)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["subject"] == f"Job leads {today:%b} {today.day}: 1 new, 1 strong"
    assert 'href="https://example.com/j/1"' in out["html"]
    assert "Analytics Engineer" in out["html"] and "Pay not listed" in out["html"]
    assert "https://tracker.example.app/Job_Leads" in out["html"]
    assert "Chase recruiter: due today" in out["html"]
    assert "Still waiting · 1 strong lead from earlier this week" in out["html"]
    assert "BI Developer" in out["html"] and "Still waiting in your inbox" in out["text"]
    assert "Read 3 alert emails" in out["html"] and "1 already in the tracker" in out["html"]
    assert "Analytics Engineer — Gamma" in out["text"]
    assert "https://example.com/j/1" in out["text"]

    run.write_text(json.dumps({"emails_read": 3}))
    assert leads.main(["digest", str(run)]) == 1
    assert "app_url" in capsys.readouterr().err


def test_an_unknown_command_shows_how_to_use_it(capsys):
    assert leads.main(["dance"]) == 2
    assert "python leads.py add" in capsys.readouterr().err
