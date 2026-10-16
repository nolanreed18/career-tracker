"""Create the tables in the database DATABASE_URL points at.

    python apply_schema.py

Safe to re-run: every statement in schema.sql is "if not exists", so existing
tables and their rows are left alone.
"""

import sys

from db import ROOT, connect

SCHEMA = ROOT / "schema.sql"


def apply(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))


def main() -> int:
    with connect() as conn:
        apply(conn)
    print("schema applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
