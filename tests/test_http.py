"""Postgres over HTTPS (db.HttpCursor), the daily review's way in from a cloud
session. Neon's endpoint is stood in for by one that runs each statement on
the throwaway database and answers in Neon's JSON shape, so nothing here
goes over the network."""

import json
import re

import psycopg
import pytest

import data
import db
import leads


@pytest.fixture
def neon(database, monkeypatch):
    """data.py over the stand-in endpoint; the statements it was sent."""
    sent = []

    def http_query(query, params):
        sent.append((query, params))
        with psycopg.connect(database, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(_as_psycopg(query), params)
            names = [c.name for c in cur.description or []]
            rows = [dict(zip(names, r)) for r in cur.fetchall()] if names else []
            reply = {"fields": [{"name": n} for n in names], "rows": rows,
                     "rowCount": cur.rowcount}
        return json.loads(json.dumps(reply, default=str))   # what crosses the wire

    monkeypatch.setattr(db, "http_query", http_query)
    data.use_http()
    return sent


def _as_psycopg(query: str) -> str:
    """$1, $2... back to psycopg's %s, for the stand-in endpoint."""
    return re.sub(r"\$\d+", "%s", query.replace("%", "%%"))


def test_placeholders_become_numbered_in_order():
    assert db.to_numbered("a = %(x)s and b = %(y)s or a = %(x)s", {"x": 1, "y": 2}) == (
        "a = $1 and b = $2 or a = $1", [1, 2])
    assert db.to_numbered("a = %s and b = %s", ("p", "q")) == ("a = $1 and b = $2", ["p", "q"])
    assert db.to_numbered("like 'x%%'", None) == ("like 'x%'", [])


def test_the_https_endpoints_are_neons():
    assert db.neon_sql_urls("ep-cool-1.us-east-2.aws.neon.tech") == [
        "https://api.us-east-2.aws.neon.tech/sql",
        "https://ep-cool-1.us-east-2.aws.neon.tech/sql",
    ]


def test_only_a_neon_database_is_sent_over_https(monkeypatch):
    monkeypatch.setattr(db, "get_dsn", lambda: "postgresql://u:p@db.example.com/x")
    with pytest.raises(RuntimeError, match="only works with a Neon database"):
        db.http_query("select 1", [])


def test_the_daily_review_works_over_https(neon, tmp_path, capsys):
    data.save_job_profile(data.today(), target_roles="Data Analyst", min_salary=95000)
    assert leads.main(["profile"]) == 0
    assert json.loads(capsys.readouterr().out)["target_roles"] == "Data Analyst"

    file = tmp_path / "leads.json"
    file.write_text(json.dumps([
        {"source": "Dice", "title": "Data Engineer", "company": "Beta", "fit_score": 7,
         "salary": "$120k-$140k", "posted_on": "2026-10-12"},
        {"source": "Indeed", "title": "Analyst", "company": "Acme"},
    ]))
    assert leads.main(["add", str(file)]) == 0
    assert "added 2, skipped 0" in capsys.readouterr().out
    assert leads.main(["add", str(file)]) == 0
    assert "added 0, skipped 2" in capsys.readouterr().out
    assert leads.main(["known"]) == 0
    assert capsys.readouterr().out.splitlines() == ["acme|analyst|", "beta|data engineer|"]
    assert all("$" in q or "select" in q.lower() for q, _ in neon)


def test_a_cloud_session_switches_leads_py_to_https(database, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(db, "http_query", lambda q, p: calls.append(q) or
                        {"fields": [{"name": "dedupe_key"}], "rows": [], "rowCount": 0})
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    assert leads.main(["known"]) == 0
    assert calls and "job_leads" in calls[0]
