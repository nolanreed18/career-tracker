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


def _secret(name: str):
    """A value from the app's secrets online, or the environment (.env) on a
    computer; None when it isn't set."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except FileNotFoundError:  # no secrets file at all
        pass
    return os.environ.get(name)


def _app_password() -> str | None:
    return _secret("APP_PASSWORD")


def _google_ready() -> bool:
    """Sign in with Google is set up: the [auth] section is in the secrets."""
    return _secret("auth") is not None


def _allowed_emails() -> set[str]:
    """ALLOWED_EMAILS: who may sign in with Google, comma-separated. Kept in
    the secrets, not this public repo."""
    return {e.strip().lower() for e in str(_secret("ALLOWED_EMAILS") or "").split(",")
            if e.strip()}


def _google_email() -> str | None:
    """The signed-in Google account's email, or None."""
    return (st.user.get("email") or "").lower() or None if st.user.is_logged_in else None


def require_password() -> None:
    """Stop the page until the visitor signs in.

    The app is public on Community Cloud, so this is what keeps the data
    private. Two ways in: Sign in with Google, for an email in ALLOWED_EMAILS
    (Streamlit keeps that sign-in for 30 days on the device), or typing
    APP_PASSWORD. With neither set up it stays locked rather than open.
    """
    if st.session_state.get(SIGNED_IN):
        return
    google = _google_ready()
    if google and (email := _google_email()):
        if email in _allowed_emails():
            st.session_state[SIGNED_IN] = True
            return
        st.error(f"{email} isn't allowed into this app.")
        st.button("Sign out", on_click=st.logout)
        st.stop()
    expected = _app_password()
    if not google and not expected:
        st.error("This app is locked: no way to sign in is set up in its secrets.")
        st.stop()
    if google:
        st.button("Sign in with Google", on_click=st.login, type="primary", width="stretch")
    if expected:
        with st.form("sign_in"):
            typed = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in" if not google else "Sign in with password")
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
