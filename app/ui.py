"""Small helpers every page uses."""

import hmac
import os
import time

import streamlit as st

import config

STATUS_ICONS = {
    "saved": "🔖", "applied": "📨", "screening": "📞", "interviewing": "🗣️",
    "offer": "🎉", "accepted": "✅", "rejected": "✖️", "withdrawn": "↩️",
}

ATTENTION_ICONS = {
    "overdue": "🔴", "due": "🟠", "interview": "🗓️", "follow_up": "📬", "stale_saved": "🔖",
}

# Characters Streamlit markdown would treat as formatting. `$` matters most:
# two of them ("$90k–$120k") turn the text between into a maths formula.
_MARKDOWN = str.maketrans({c: "\\" + c for c in "\\`*_[]#<>$|~"})


def setup(title: str) -> None:
    """Page config. Phone-first: one centred column."""
    st.set_page_config(
        page_title=title if title == "Career Tracker" else f"{title} · Career Tracker",
        page_icon="💼",
        layout="centered",
    )
    require_password()


SIGNED_IN = "signed_in"


def _app_password() -> str | None:
    """APP_PASSWORD from the app's secrets online, or the environment (.env)
    on a computer."""
    try:
        if "APP_PASSWORD" in st.secrets:
            return st.secrets["APP_PASSWORD"]
    except FileNotFoundError:  # no secrets file at all
        pass
    return os.environ.get("APP_PASSWORD")


def require_password() -> None:
    """Stop the page until the visitor types APP_PASSWORD.

    The app is public on Community Cloud, so this is what keeps the data
    private. With no password set it stays locked rather than open.
    """
    if st.session_state.get(SIGNED_IN):
        return
    expected = _app_password()
    if not expected:
        st.error("This app is locked: APP_PASSWORD is not set in its secrets.")
        st.stop()
    with st.form("sign_in"):
        typed = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        if hmac.compare_digest(typed.encode(), expected.encode()):
            st.session_state[SIGNED_IN] = True
            st.rerun()
        time.sleep(1)  # slows down guessing
        st.error("Wrong password.")
    st.stop()


def md(text) -> str:
    """Text safe to put inside st.markdown."""
    return "" if text is None else str(text).translate(_MARKDOWN)


def status_label(status: str) -> str:
    return f"{STATUS_ICONS.get(status, '')} {status.capitalize()}".strip()


def optional(options: list[str]) -> list[str]:
    """A selectbox's options with a leading blank for "not set"."""
    return [""] + options


def index_of(options: list, current, default: int = 0) -> int:
    return options.index(current) if current in options else default


STATUS_HELP = (
    "Saved → Applied → Screening → Interviewing → Offer, then Accepted, "
    "Rejected or Withdrawn. Open statuses: " + ", ".join(config.OPEN_STATUSES) + "."
)
