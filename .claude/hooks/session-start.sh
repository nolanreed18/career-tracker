#!/bin/bash
# Claude Code cloud sessions only: install the Python packages and start a
# throwaway local Postgres for the tests, so `pytest` and `ruff` work at once.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
# Some cloud images carry Debian's own cryptography (41), which pip can't
# remove (no install record), and Authlib needs 45 or newer: the install
# below then failed and the session started without the packages. Put the
# newer one over it first; with a new enough one already there, skip it.
if ! python3 -c "import sys, cryptography; sys.exit(int(cryptography.__version__.split('.')[0]) < 45)" \
    2>/dev/null; then
  python3 -m pip install --quiet --disable-pip-version-check --ignore-installed \
    "cryptography>=45.0.1"
fi
python3 -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt

# The tests need TEST_DATABASE_URL pointing at a database they may wipe.
# Never the real (Neon) one: conftest.py refuses any neon.tech address.
if command -v pg_ctlcluster >/dev/null 2>&1; then
  version=$(ls /usr/lib/postgresql | sort -n | tail -1)
  pg_ctlcluster "$version" main start >/dev/null 2>&1 || true
  su postgres -c "psql -qtA -c \"select 1 from pg_roles where rolname = 'tracker'\"" | grep -q 1 \
    || su postgres -c "psql -q -c \"create role tracker login password 'tracker'\""
  su postgres -c "psql -qtA -c \"select 1 from pg_database where datname = 'tracker_test'\"" \
    | grep -q 1 || su postgres -c "psql -q -c 'create database tracker_test owner tracker'"
  echo 'export TEST_DATABASE_URL=postgresql://tracker:tracker@localhost:5432/tracker_test' \
    >> "$CLAUDE_ENV_FILE"
fi
