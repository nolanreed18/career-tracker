"""Dump every table to timestamped CSVs in data/backups/.

    python backup.py

One run writes one CSV per table, each stamped with the same local
(America/Chicago) timestamp, and keeps the ten most recent runs. It also runs
weekly in GitHub Actions (.github/workflows/backup.yml), which keeps each
run's CSVs as a downloadable artifact. data/ is gitignored: it holds personal
information.

A run that fails part-way removes what it had written -- half a run would
look like a backup and not be one -- and exits non-zero, so a scheduled run
shows red.
"""

import sys
from datetime import datetime
from pathlib import Path

from db import LOCAL_TZ, ROOT, connect

BACKUP_DIR = ROOT / "data" / "backups"
KEEP_RUNS = 10
STAMP_FORMAT = "%Y%m%d_%H%M%S"

# Every table in schema.sql. tests/test_backup.py checks none is missing.
TABLES = [
    ("companies", "company_id"),
    ("contacts", "contact_id"),
    ("applications", "application_id"),
    ("application_events", "event_id"),
    ("interviews", "interview_id"),
    ("career_entries", "entry_id"),
    ("positions", "position_id"),
    ("job_profile", "profile_id"),
    ("job_leads", "lead_id"),
    ("settings", "key"),
]


def stamp_of(path: Path) -> str:
    """The run timestamp at the end of a backup filename, or '' if none."""
    parts = path.stem.rsplit("_", 2)
    return "_".join(parts[-2:]) if len(parts) >= 3 else ""


def prune(keep: int = KEEP_RUNS) -> list[Path]:
    """Delete every file from all but the `keep` most recent runs, whole runs
    at a time."""
    stamps = sorted({stamp_of(p) for p in BACKUP_DIR.glob("*.csv")} - {""})
    doomed = set(stamps[:-keep]) if len(stamps) > keep else set()
    removed = [p for p in sorted(BACKUP_DIR.glob("*.csv")) if stamp_of(p) in doomed]
    for path in removed:
        path.unlink()
    return removed


def dump(stamp: str) -> list[tuple[Path, int]]:
    """Every table to its CSV; (path, rows) for each."""
    written = []
    with connect() as conn, conn.cursor() as cur:
        for table, key in TABLES:
            path = BACKUP_DIR / f"{table}_{stamp}.csv"
            with open(path, "w", newline="", encoding="utf-8") as handle:
                with cur.copy(f"copy (select * from {table} order by {key}) "
                              "to stdout with (format csv, header)") as copy:
                    for chunk in copy:
                        handle.write(bytes(chunk).decode("utf-8"))
            with open(path, encoding="utf-8") as handle:
                rows = max(sum(1 for _ in handle) - 1, 0)   # minus the header
            written.append((path, rows))
    return written


def main() -> int:
    """One backup run; 0 when every table was written, 1 otherwise."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(LOCAL_TZ).strftime(STAMP_FORMAT)
    try:
        written = dump(stamp)
    except (Exception, SystemExit) as exc:
        # Never the connection string: db.get_dsn's message names only the variable.
        for path in BACKUP_DIR.glob(f"*_{stamp}.csv"):
            path.unlink()
        print(f"backup {stamp} failed, nothing kept: {exc}", file=sys.stderr)
        return 1

    print(f"backup {stamp} -> {BACKUP_DIR}")
    for path, rows in written:
        print(f"  {path.name:<44} {rows:>7,} rows")
    removed = prune()
    if removed:
        print(f"pruned {len(removed)} file(s) from old runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
