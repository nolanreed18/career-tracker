"""Put app/ on sys.path and keep every test off the real database.

Tests that need a database ask for the `database` fixture, which points the
app at TEST_DATABASE_URL -- a throwaway Postgres (GitHub Actions starts one
for each run) -- and empties it before each test. Without TEST_DATABASE_URL
those tests are skipped. Any other attempt to connect fails the test, so the
real DATABASE_URL in .env is never touched.
"""

import os
import sys
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

import apply_schema  # noqa: E402
import data  # noqa: E402
import db  # noqa: E402

TABLES = ("companies, contacts, applications, application_events, interviews, "
          "career_entries, positions, job_profile, job_leads, settings")


@pytest.fixture(autouse=True)
def no_real_database(monkeypatch):
    def refuse():
        raise RuntimeError("tests must not reach the real database: use the `database` fixture")

    monkeypatch.setattr(db, "get_dsn", refuse)
    # Never over HTTPS in tests (a cloud session sets CLAUDE_CODE_REMOTE).
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    monkeypatch.setattr(data, "_over_http", False)
    data.reset_connection()
    yield
    data.reset_connection()


@pytest.fixture(scope="session")
def test_database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set (see README: Tests)")
    if "neon.tech" in url:
        pytest.fail("TEST_DATABASE_URL must be a throwaway database, never Neon")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f"drop table if exists {TABLES} cascade")
        apply_schema.apply(conn)
    return url


@pytest.fixture
def database(test_database_url, monkeypatch):
    """An empty database with the current schema, used by data.py and scripts."""
    monkeypatch.setattr(db, "get_dsn", lambda: test_database_url)
    with psycopg.connect(test_database_url, autocommit=True) as conn:
        conn.execute(f"truncate {TABLES} restart identity cascade")
    data.reset_connection()
    return test_database_url
