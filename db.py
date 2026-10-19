"""Shared database helpers.

DATABASE_URL comes from the environment, which scripts fill from .env next to
this file. A running Streamlit app with no .env -- Community Cloud -- falls
back to st.secrets. Neither path ever prints the value.
"""

import datetime
import decimal
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

# The project's one timezone. "Today" is always computed from this in Python
# and passed into queries; no query uses current_date, now(), or the server
# timezone.
LOCAL_TZ = ZoneInfo("America/Chicago")

# Explicit path: python-dotenv's default search starts from the caller's
# directory, which is not necessarily the project root.
load_dotenv(ROOT / ".env")


def _streamlit_secret() -> str | None:
    """DATABASE_URL from st.secrets, but only inside a running Streamlit app.

    Looked up through sys.modules so a script never imports Streamlit, and
    gated on runtime.exists() so a script keeps the .env message.
    """
    st = sys.modules.get("streamlit")
    if st is None:
        return None
    from streamlit import runtime

    if not runtime.exists():
        return None
    try:
        return st.secrets["DATABASE_URL"]
    except (KeyError, FileNotFoundError):  # no such key, or no secrets at all
        return None


def get_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL") or _streamlit_secret()
    if not dsn:
        raise SystemExit(
            "DATABASE_URL is not set. Add it to .env at the project root, "
            "or to the app's secrets on Streamlit Community Cloud."
        )
    return dsn


def connect(**kwargs) -> psycopg.Connection:
    """Open a connection. Caller manages the transaction unless autocommit."""
    return psycopg.connect(get_dsn(), **kwargs)


# ---- Postgres over HTTPS ----------------------------------------------------
#
# Claude's cloud sessions (the daily job-alert review) reach the internet only
# through an HTTPS proxy, so a Postgres connection on port 5432 hangs there.
# Neon also answers SQL over HTTPS, its official serverless method; leads.py
# switches data.py onto it. The app itself never uses this path. The
# connection string goes only to Neon's own endpoint, never into output.

HTTP_TIMEOUT_S = 30


def neon_sql_urls(host: str) -> list[str]:
    """Where Neon answers SQL over HTTPS for this database host: its regional
    "api." endpoint, then the database's own host."""
    region = host.split(".", 1)[1] if "." in host else host
    return [f"https://api.{region}/sql", f"https://{host}/sql"]


def http_query(query: str, params: list) -> dict:
    """One statement through Neon's HTTPS endpoint; its JSON reply
    ({"fields": [...], "rows": [...], "rowCount": n})."""
    dsn = get_dsn()
    host = urllib.parse.urlparse(dsn).hostname or ""
    if not host.endswith(".neon.tech"):
        raise RuntimeError("SQL over HTTPS only works with a Neon database")
    body = json.dumps({"query": query, "params": params}).encode()
    headers = {"Neon-Connection-String": dsn, "Content-Type": "application/json"}
    problem = "no endpoint answered"
    for url in neon_sql_urls(host):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace").replace(dsn, "<DATABASE_URL>")
            if exc.code == 404:
                problem = f"{url} not found"
                continue
            raise RuntimeError(f"database error ({exc.code}): {detail[:300]}") from None
        except urllib.error.URLError as exc:
            problem = f"{url}: {exc.reason}"
    raise RuntimeError(f"couldn't reach the database over HTTPS ({problem})")


_PLACEHOLDER = re.compile(r"%\((\w+)\)s|%s|%%")


def to_numbered(query: str, params) -> tuple[str, list]:
    """psycopg's %s / %(name)s placeholders as Postgres $1, $2..., with the
    values in that order."""
    values: list = []
    numbers: dict[str, int] = {}
    positional = None if isinstance(params, dict) else iter(params or ())

    def swap(match: re.Match) -> str:
        if match.group(0) == "%%":
            return "%"
        if name := match.group(1):
            if name not in numbers:
                values.append(params[name])
                numbers[name] = len(values)
            return f"${numbers[name]}"
        values.append(next(positional))
        return f"${len(values)}"

    return _PLACEHOLDER.sub(swap, query), values


class _Column:
    def __init__(self, name: str):
        self.name = name


# Neon's JSON carries dates, times and numerics as text, and says each
# column's Postgres type (its OID) in "fields": turn them back into what a
# psycopg cursor would give, so logic.py's date arithmetic works over HTTPS.
_PARSERS = {
    20: int, 21: int, 23: int,                                  # int8, int2, int4
    700: float, 701: float,                                     # float4, float8
    1700: decimal.Decimal,                                      # numeric
    1082: datetime.date.fromisoformat,                          # date
    1083: datetime.time.fromisoformat,                          # time
    1114: datetime.datetime.fromisoformat,                      # timestamp
    1184: datetime.datetime.fromisoformat,                      # timestamptz
}


def typed(value, type_oid):
    """A cell from Neon's reply as its Python type, when it came as text."""
    parser = _PARSERS.get(type_oid)
    if parser is None or value is None or not isinstance(value, str):
        return value
    try:
        return parser(value)
    except (TypeError, ValueError):
        return value


class HttpCursor:
    """Just enough of a psycopg cursor for data.py, over Neon's HTTPS
    endpoint. Each statement stands alone: there are no transactions."""

    def __init__(self, row_factory=None):
        self.dict_rows = row_factory is not None
        self.rows: list = []
        self.description: list = []
        self.rowcount = -1

    def execute(self, query, params=None):
        if not isinstance(query, str):
            query = query.as_string(None)
        text, values = to_numbered(query, params)
        values = [v if v is None or isinstance(v, (bool, int, float)) else str(v)
                  for v in values]
        reply = http_query(text, values)
        fields = reply.get("fields", [])
        names = [field["name"] for field in fields]
        types = {field["name"]: field.get("dataTypeID") for field in fields}
        self.description = [_Column(n) for n in names]
        self.rowcount = reply.get("rowCount", -1)
        rows = [{n: typed(row[n], types[n]) for n in names} for row in reply.get("rows", [])]
        self.rows = rows if self.dict_rows else [tuple(row[n] for n in names) for row in rows]
        return self

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows
