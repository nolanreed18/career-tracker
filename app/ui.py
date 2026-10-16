"""Small helpers every page uses."""

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
