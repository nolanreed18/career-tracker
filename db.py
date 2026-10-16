"""Shared database helpers.

DATABASE_URL comes from the environment, which scripts fill from .env next to
this file. A running Streamlit app with no .env -- Community Cloud -- falls
back to st.secrets. Neither path ever prints the value.
"""

import os
import sys
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
