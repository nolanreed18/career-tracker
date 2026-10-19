"""Small helpers every page uses: sign-in, the look, labels and badges."""

import hmac
import os
import time

import streamlit as st

import config
import data
import logic
import theme

# Icons for places that can't show a badge: selectbox options, table cells.
STATUS_ICONS = {
    "saved": "🔖", "applied": "📨", "screening": "📞", "interviewing": "🗣️",
    "offer": "🎉", "accepted": "✅", "rejected": "✖️", "withdrawn": "↩️",
}

# Badge colours. Blue = in progress, green = good, orange = needs attention,
# red = overdue or closed, grey = neutral; violet marks a second category.
STATUS_COLORS = {
    "saved": "gray", "applied": "blue", "screening": "blue", "interviewing": "blue",
    "offer": "green", "accepted": "green", "rejected": "red", "withdrawn": "gray",
}
ATTENTION_BADGES = {
    "overdue": ("red", "Overdue"), "due": ("orange", "Due"), "interview": ("blue", "Interview"),
    "follow_up": ("orange", "Follow up"), "stale_saved": ("gray", "Saved"),
}
FIT_COLORS = {"strong": "green", "maybe": "blue", "weak": "gray"}
KIND_COLORS = {"win": "green", "skill": "blue", "certification": "violet",
               "feedback": "orange", "learning": "gray"}

# Characters Streamlit markdown would treat as formatting. `$` matters most:
# two of them ("$90k–$120k") turn the text between into a maths formula.
_MARKDOWN = str.maketrans({c: "\\" + c for c in "\\`*_[]#<>$|~"})

SIGNED_IN = "signed_in"
THEME_SETTING = "theme"


def setup(title: str, subtitle: str | None = None) -> None:
    """Page config, sign-in, the look, and the page head. Phone-first: one
    centred column."""
    st.set_page_config(
        page_title=title if title == "Career Tracker" else f"{title} · Career Tracker",
        page_icon="💼",
        layout="centered",
    )
    require_password()
    appearance()
    st.title(title)
    if subtitle:
        st.html(theme.subtitle(subtitle))
    if message := st.session_state.pop("flash", None):   # what the last action did
        st.success(message)
        st.toast(message)                                # also where the eye is


# ---- the look ---------------------------------------------------------------

def appearance() -> None:
    """Apply the saved look (light unless Dark mode was switched on), draw the
    sidebar's Dark mode switch and sign-out, and add the stylesheet.

    Streamlit reads its theme options as a script run starts, so a change
    made during a run shows on the next one: after a switch, or when this
    run began with other options (the first run after the app started),
    the page reruns once.
    """
    mode = data.get_setting(THEME_SETTING)
    if mode not in theme.MODES:
        mode = theme.DEFAULT
    started_with = theme.current()
    theme.apply(mode)
    if "dark_mode" not in st.session_state or st.session_state.get("theme_shown") != mode:
        # First draw, or the choice was changed on another device: the switch
        # follows the saved choice rather than flipping it back.
        st.session_state["dark_mode"] = mode == theme.DARK
        st.session_state["theme_shown"] = mode
    with st.sidebar:
        dark = st.toggle("Dark mode", key="dark_mode")
        _account()
    picked = theme.DARK if dark else theme.LIGHT
    if picked != mode:
        data.set_setting(THEME_SETTING, picked)
        st.session_state["theme_shown"] = picked
        theme.apply(picked)
        st.rerun()
    if started_with != mode and not st.session_state.get("theme_rerun"):
        st.session_state["theme_rerun"] = True       # once: never loop on a surprise
        st.rerun()
    st.session_state["theme_rerun"] = False
    st.html(theme.stylesheet(mode))


def _account() -> None:
    if email := _google_email():
        st.html(theme.note(email))
    st.button("Sign out", on_click=sign_out, width="stretch")


def sign_out() -> None:
    st.session_state.pop(SIGNED_IN, None)
    if _google_email():
        st.logout()


def card(key: str):
    """A bordered container styled as a card (the stylesheet finds the key)."""
    return st.container(border=True, key=f"card-{key}")


def disclosure(label: str, key: str) -> bool:
    """A button that opens and closes a form below it: True while open. The
    state lives on the server, so a click that lands while the page is still
    loading can't snap it shut (an st.expander forgets it was open then)."""
    flag = f"open_{key}"
    is_open = bool(st.session_state.get(flag, False))
    if st.button("Close" if is_open else label, key=f"toggle_{key}",
                 icon=":material/close:" if is_open else ":material/add:", width="stretch"):
        st.session_state[flag] = not is_open
        st.rerun()
    return is_open


def sections(key: str, names: list[str]) -> str:
    """A page's sub-pages as pills. Unlike st.tabs, the chosen one stays put
    when an action reruns the page."""
    with st.container(key=f"sections-{key}"):
        return st.radio("Section", names, horizontal=True, key=f"section_{key}",
                        label_visibility="collapsed")


def delete_button(what: str, key: str) -> bool:
    """A Delete button that needs its tick box first: nothing goes in one click."""
    sure = st.checkbox(f"I want to delete this {what}", key=f"sure_{key}")
    return st.button(f"Delete {what}", disabled=not sure, key=f"delete_{key}")


def round_key(name: str) -> str:
    """A widget key with a counter in it. A widget whose options change (a
    "pick one" dropdown after a delete) keeps showing its old choice; a new
    key (bump_round) gives a fresh widget instead."""
    return f"{name}_{st.session_state.get(f'{name}_round', 0)}"


def bump_round(name: str) -> None:
    st.session_state[f"{name}_round"] = st.session_state.get(f"{name}_round", 0) + 1


def empty(icon: str, title: str, text: str) -> None:
    """An empty state: a Material Symbols icon name, a heading, one sentence
    saying why it's empty and what to do."""
    st.html(theme.empty_state(icon, title, text))


# ---- sign-in ----------------------------------------------------------------

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
    """The signed-in Google account's email, or None (st.user only works once
    the [auth] secrets exist)."""
    if not _google_ready() or not st.user.is_logged_in:
        return None
    return (st.user.get("email") or "").lower() or None


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
        _locked_look()
        st.error(f"{email} isn't allowed into this app.")
        st.button("Sign out", on_click=st.logout)
        st.stop()
    _locked_look()
    st.title("Career Tracker")
    expected = _app_password()
    if not google and not expected:
        st.error("This app is locked: no way to sign in is set up in its secrets.")
        st.stop()
    st.html(theme.subtitle("Sign in to continue"))
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


def _locked_look() -> None:
    """The stylesheet plus the sidebar hidden: only for a page that stops at
    sign-in (a signed-in run must not hide its own sidebar)."""
    st.html(theme.stylesheet(theme.current() or theme.DEFAULT))
    st.html(theme.LOCKED)


# ---- text and labels --------------------------------------------------------

def md(text) -> str:
    """Text safe to put inside st.markdown."""
    return "" if text is None else str(text).translate(_MARKDOWN)


def badge(color: str, text: str) -> str:
    """A coloured markdown badge (:blue-badge[text])."""
    return f":{color}-badge[{text}]"


def status_badge(status: str) -> str:
    return badge(STATUS_COLORS.get(status, "gray"), status.capitalize())


def attention_badge(kind: str) -> str:
    color, text = ATTENTION_BADGES.get(kind, ("gray", kind.replace("_", " ").capitalize()))
    return badge(color, text)


def fit_badge(score) -> str:
    """':green-badge[8/10]' for a strong fit, blue for a maybe, grey for a
    weak one, '' when unscored."""
    tier = logic.fit_tier(score)
    return "" if tier is None else badge(FIT_COLORS[tier], f"{logic.fit_text(score)}/10")


def pay_badge(salary_min, salary_max, pay_source) -> str:
    """The pay as markdown: the range as plain text when it was listed, a
    yellow warning badge with the range when the daily review estimated it,
    and a yellow warning badge saying so when it's not known at all."""
    state, text = logic.pay_state(salary_min, salary_max, pay_source)
    if state == "listed":
        return md(text)
    return badge("yellow", f":material/warning: {md(text)}"
                 + (" (estimate)" if state == "estimated" else ""))


def fit_breakdown(detail) -> str:
    """'Role 9 · Industry 6 · …' from a lead's fit_detail, with a red badge
    when a deal-breaker capped the score; '' when there is no breakdown."""
    detail = logic.value(detail)
    if not isinstance(detail, dict) or not detail.get("ratings"):
        return ""
    ratings = detail["ratings"]
    parts = [f"{label.split(' ')[0]} {ratings[key]}"
             for key, (label, _, _) in config.FIT_CATEGORIES.items() if key in ratings]
    text = " · ".join(parts)
    return f"{badge('red', 'Deal-breaker')} {text}" if detail.get("deal_breaker") else text


def kind_badge(kind: str) -> str:
    return badge(KIND_COLORS.get(kind, "gray"), kind.capitalize())


def status_label(status: str) -> str:
    """Icon plus name, for selectbox options and table cells."""
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
