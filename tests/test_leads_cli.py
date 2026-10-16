"""leads.py as the daily job-alert review runs it."""

import json

import pytest

import data
import leads


@pytest.fixture(autouse=True)
def _db(database):
    return database


def test_profile_prints_what_youre_looking_for(capsys):
    assert leads.main(["profile"]) == 0
    assert json.loads(capsys.readouterr().out) == {}
    data.save_job_profile(data.today(), target_roles="Data Analyst", min_salary=95000)
    assert leads.main(["profile"]) == 0
    profile = json.loads(capsys.readouterr().out)
    assert profile["target_roles"] == "Data Analyst" and profile["min_salary"] == 95000


def test_add_stores_new_leads_and_skips_ones_already_seen(tmp_path, capsys):
    file = tmp_path / "leads.json"
    file.write_text(json.dumps([
        {"source": "Dice", "title": "Data Engineer", "company": "Beta", "fit_score": 7},
        {"source": "Indeed", "title": "Analyst", "company": "Acme", "salary": "$100k"},
    ]))
    assert leads.main(["add", str(file)]) == 0
    assert "added 2, skipped 0" in capsys.readouterr().out
    assert leads.main(["add", str(file)]) == 0
    assert "added 0, skipped 2" in capsys.readouterr().out
    assert leads.main(["known"]) == 0
    assert capsys.readouterr().out.splitlines() == ["acme|analyst|", "beta|data engineer|"]


def test_one_bad_row_means_nothing_is_added(tmp_path, capsys):
    file = tmp_path / "leads.json"
    file.write_text(json.dumps([
        {"source": "Dice", "title": "Data Engineer", "company": "Beta"},
        {"source": "Dice", "title": "No company"},
    ]))
    assert leads.main(["add", str(file)]) == 1
    assert "nothing added" in capsys.readouterr().err
    assert data.job_leads().empty


def test_an_unknown_command_shows_how_to_use_it(capsys):
    assert leads.main(["dance"]) == 2
    assert "python leads.py add" in capsys.readouterr().err
