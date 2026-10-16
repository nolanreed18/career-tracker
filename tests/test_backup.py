"""backup.py as the weekly Actions run uses it: every table, a fresh checkout
with no data/ directory, and a failure that has to show red."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

import backup
import data

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    target = tmp_path / "data" / "backups"
    monkeypatch.setattr(backup, "BACKUP_DIR", target)
    return target


def test_every_table_in_the_schema_is_backed_up():
    schema = (ROOT / "schema.sql").read_text()
    tables = set(re.findall(r"create table if not exists (\w+)", schema))
    assert tables == {table for table, _ in backup.TABLES}


def test_a_run_writes_one_csv_per_table_with_its_rows(database, backup_dir):
    data.company_id_for("Acme", data.today())
    assert backup.main() == 0
    files = {p.name.rsplit("_", 2)[0]: p for p in backup_dir.glob("*.csv")}
    assert set(files) == {table for table, _ in backup.TABLES}
    assert files["companies"].read_text().splitlines()[1].split(",")[1] == "Acme"


def test_only_the_last_ten_runs_are_kept(backup_dir):
    backup_dir.mkdir(parents=True)
    for n in range(12):
        for table in ("companies", "applications"):
            (backup_dir / f"{table}_20260101_0000{n:02d}.csv").write_text("x\n")
    backup.prune()
    stamps = {backup.stamp_of(p) for p in backup_dir.glob("*.csv")}
    assert len(stamps) == 10 and "20260101_000000" not in stamps


def test_a_failure_keeps_nothing_and_returns_1(backup_dir):
    # No `database` fixture: the connection is refused, as with no DATABASE_URL.
    assert backup.main() == 1
    assert list(backup_dir.glob("*.csv")) == []


def test_the_script_exits_non_zero_without_database_url(tmp_path):
    """As Actions runs it with no secret: the process itself must fail."""
    for name in ("backup.py", "db.py"):
        (tmp_path / name).write_text((ROOT / name).read_text())
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    run = subprocess.run([sys.executable, "backup.py"], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 1, run.stderr
    assert "DATABASE_URL is not set" in run.stderr
