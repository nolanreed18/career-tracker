"""What every page shares: sign-in, the look, the components the stylesheet
draws (cards, pill selectors, empty states, disclosures, deletes, badges,
Claude's spark), and the employer-site posting search that Job Leads' Add
and Applications' "Find it" both run."""

import hmac
import time

import streamlit as st

import config
import data
import db
import logic
import posting
import theme

# Badge colours. Blue = in progress, green = good, orange = needs attention,
# red = overdue or closed, grey = neutral; violet marks a second category.
STATUS_COLORS = {
    "saved": "gray", "applied": "blue", "screening": "blue", "interviewing": "blue",
    "offer": "green", "accepted": "green", "rejected": "red", "withdrawn": "gray",
}
ATTENTION_COLORS = {"overdue": "red", "due": "orange", "interview": "blue",
                    "follow_up": "orange", "stale_saved": "gray"}
FIT_COLORS = {"strong": "green", "maybe": "blue", "weak": "gray"}

# Characters Streamlit markdown would treat as formatting. `$` matters most:
# two of them ("$90k–$120k") turn the text between into a maths formula.
_MARKDOWN = str.maketrans({c: "\\" + c for c in "\\`*_[]#<>$|~"})

SIGNED_IN = "signed_in"
THEME_SETTING = "theme"


def device() -> str:
    """"phone" or "computer", from what the browser says it is."""
    try:
        agent = st.context.headers.get("User-Agent", "")
    except Exception:                                  # no browser: a test or a script
        agent = ""
    return logic.device_from_agent(agent)


def on_phone() -> bool:
    return device() == "phone"


def setup(title: str, subtitle: str | None = None) -> None:
    """Page config, sign-in, the look, and the page head. A phone gets one
    centred column; a computer the full width (up to a limit), which pages
    use for side-by-side layouts."""
    st.set_page_config(
        page_title=title if title == "Career Tracker" else f"{title} · Career Tracker",
        page_icon=":material/work:",
        layout="centered" if on_phone() else "wide",
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

    The saved choice is read from the database once per process (one
    round trip fewer on every rerun after that): theme.applied() remembers
    it, and a switch on any device goes through here, so every open tab
    follows. Streamlit reads its theme options as a script run starts, so a
    change made during a run shows on the next one: after a switch, or when
    this run began with other options (the first run after the app started),
    the page reruns once. The switch itself takes its value from the mode in
    force every run, never from its own remembered state.
    """
    started_with = theme.current()
    mode = theme.applied()
    if mode is None:                                 # the first run in this process
        mode = data.get_setting(THEME_SETTING)
        if mode not in theme.MODES:
            mode = theme.DEFAULT
        theme.apply(mode)
    # The switch starts from the mode in force and is keyed by it, so a fresh
    # widget (another page: Streamlit forgets a widget's state across pages)
    # or a change made on another device never reads as a flip back. Nothing
    # is written to the widget's own session state.
    for other in theme.MODES:
        if other != mode:
            st.session_state.pop(f"dark_mode_{other}", None)
    with st.sidebar:
        dark = st.toggle("Dark mode", value=mode == theme.DARK, key=f"dark_mode_{mode}")
        _account()
    picked = theme.DARK if dark else theme.LIGHT
    if picked != mode:
        data.set_setting(THEME_SETTING, picked)
        theme.apply(picked)
        st.rerun()
    if started_with != mode and not st.session_state.get("theme_rerun"):
        st.session_state["theme_rerun"] = True       # once: never loop on a surprise
        st.rerun()
    st.session_state["theme_rerun"] = False
    st.html(theme.stylesheet(mode, phone=on_phone()))


def _account() -> None:
    if email := _google_email():
        st.html(theme.note(email))
    st.button("Sign out", on_click=sign_out, width="stretch")


def sign_out() -> None:
    st.session_state.pop(SIGNED_IN, None)
    if _google_email():
        st.logout()


def done(message: str, counter: str | None = None) -> None:
    """Finish an action: remember what happened (setup() shows it on the
    next run), bump a form's counter so it comes back empty, and rerun."""
    if counter:
        st.session_state[counter] = st.session_state.get(counter, 0) + 1
    st.session_state["flash"] = message
    st.rerun()


def posting_button(app: dict, key: str) -> None:
    """A button that reads the job posting from the application's links
    (posting.from_links: the employer's site first, then the job link) and
    saves it as the application's posting. Shown only when there is a link;
    the main action while the posting is empty."""
    if not (logic.value(app.get("job_url")) or logic.value(app.get("apply_url"))):
        return
    if st.button("Get the posting from the link", key=f"fetch_posting_{key}",
                 icon=":material/download:",
                 type="secondary" if logic.value(app.get("posting")) else "primary"):
        try:
            found, link = posting.from_links(app.get("job_url"), app.get("apply_url"))
        except posting.PostingError as problem:
            st.error(str(problem))
        else:
            data.update_application(int(app["application_id"]), posting=found.as_text())
            where = (f"{app['company']}'s site" if link == logic.job_link(app.get("apply_url"))
                     else "the job link")
            done(f"Read the posting from {where}: {found.title or app['role']}, "
                 f"{len(found.text):,} characters. Check it, then tailor.")


def known_company_posting(app: dict) -> tuple[str, str] | None:
    """Where the application's posting is on the employer's own site when the
    app can tell for free, without Claude: the job link itself when it is a
    Workday, Greenhouse or Lever posting (a watched company's lead), else a
    careers site already known for this employer (this application's links
    or another one's) searched for the title. (address, note), or None."""
    link = logic.job_link(app.get("job_url"))
    if posting.employer_link(link):
        return link, "The job link is the employer's own posting."
    known = ([app.get("apply_url"), app.get("job_url")]
             + data.company_apply_links(int(app["company_id"])))
    for site in dict.fromkeys(link for link in known if posting.careers_site(link)):
        if exact := posting.on_careers_site(site, app["role"], app.get("location")):
            return exact, "Found on the employer's careers site by its title."
    return None


def find_company_posting(app: dict, today) -> list[str]:
    """Look for the application's posting on the employer's own site and save
    the link and note. First, free: known_company_posting. Else
    ai.find_posting, logged (a failed call too); when Claude finds only the
    careers site, the app searches it for the title. Returns what to tell
    the owner."""
    import ai  # here, not at the top: the SDK is slow to import and only this needs it

    app_id = int(app["application_id"])
    # The state is on the row from the start, so the application says where the
    # search stands even when the owner leaves the page while it runs.
    data.update_application(app_id, apply_state="looking",
                            apply_note=f"Looking since {data.now():%-I:%M %p}.")
    if known := known_company_posting(app):
        return _save_found(app, known[0], "", "", known[1], "", "free")
    try:
        found, usage = ai.find_posting(app["company"], app["role"], app.get("location"),
                                       app.get("source"), app.get("posting") or "")
    except ai.AIError as problem:
        if problem.usage:
            data.log_ai_usage("find posting (failed)", problem.usage.model,
                              problem.usage.input_tokens, problem.usage.output_tokens,
                              problem.usage.cost_usd, today)
        data.update_application(app_id, apply_state="failed", apply_note=str(problem))
        return [f"Couldn't look for it on the employer's site: {problem}"]
    except BaseException:
        data.update_application(app_id, apply_state="failed",
                                apply_note="The search stopped partway.")
        raise
    data.log_ai_usage("find posting", usage.model, usage.input_tokens, usage.output_tokens,
                      usage.cost_usd, today)
    url, note = found["url"], found["note"]
    exact = posting.on_careers_site(url, found["title"] or app["role"],
                                    found["location"] or app.get("location")) if url else None
    if exact and exact != url:              # Claude reached the site; the app found the posting
        url, note = exact, "Found on the employer's careers site by its title."
    return _save_found(app, url, found["title"], found["location"], note,
                       found["description"], f"${usage.cost_usd:.2f}")


def _save_found(app: dict, url: str, title: str, location: str, note: str,
                description: str, cost: str) -> list[str]:
    """Save where the posting is on the employer's site (or that it isn't
    there), read it from there when the site has it as data, fill an empty
    posting box, and say how it went."""
    app_id = int(app["application_id"])
    checked = posting.employer_posting(url) if url else None
    if checked:
        title, location = checked.title or title, checked.location or location   # as listed there
        note = f"Read from the employer's site. {note}".strip()
    copied = ""                      # the job board wouldn't give the posting: take the employer's
    if url and not logic.value(app.get("posting")):
        if checked and len(checked.text) >= config.POSTING_MIN_CHARS:
            data.update_application(app_id, posting=checked.as_text())
            copied = " Posting read from there."
        elif len(description.strip()) >= config.POSTING_MIN_CHARS:
            text = description.strip()[:config.POSTING_MAX_CHARS]
            data.update_application(app_id, posting=posting.Posting(
                title or app["role"], app["company"], location, text).as_text())
            copied = " Posting copied from there by Claude: check it before tailoring."
    if url and location:
        note = f"Listed there as {title or app['role']} in {location}. {note}".strip()
    data.update_application(app_id, apply_url=url, apply_note=note,
                            apply_state="found" if url else "missing")
    if url:
        return [f"Found it on the employer's site: {title or app['role']}"
                + (f", {location}" if location else "") + f" ({cost})." + copied]
    return [f"Not found on the employer's site: {note} ({cost})."]


def prepare_application(application_id: int, today) -> list[str]:
    """What the Add tap on a lead does after saving the application: read
    the posting from its link, then look for it on the employer's own site:
    free when the app can tell (known_company_posting), else with Claude
    when the key is set. Each step says how it went; neither stops the
    other."""
    app = data.application(application_id)
    notes, unread = [], None
    if logic.value(app.get("job_url")) and not logic.value(app.get("posting")):
        try:
            found = posting.fetch(app["job_url"])
        except posting.PostingError as problem:
            unread = f"Posting not read: {problem}"
        else:
            app["posting"] = found.as_text()
            data.update_application(application_id, posting=app["posting"])
            notes.append(f"Posting read ({len(found.text):,} characters).")
    if known := known_company_posting(app):
        notes += _save_found(app, known[0], "", "", known[1], "", "free")
    elif claude_ready():
        notes += find_company_posting(app, today)
    if unread and not logic.value(data.application(application_id)["posting"]):
        notes.insert(0, unread)          # said only when the employer's site didn't fill it
    return notes


def apply_status(app: dict) -> None:
    """One line saying where the employer-site search stands for this
    application (applications.apply_state), with what to do next."""
    state, note = app.get("apply_state"), md(app.get("apply_note") or "")
    if state == "found":
        st.caption(note)
    elif state == "looking":
        st.caption(f"{badge('blue', 'Looking on the employer’s site')} {note} It usually "
                   "takes a minute or two, and this line updates itself. Much longer than "
                   "that: tap Find it on the employer's site to start again.")
    elif state == "missing":
        st.caption(f"{badge('orange', 'Not on the employer’s site')} {note} Apply through "
                   "the posting, or paste the employer's link under Edit if you find it.")
    elif state == "failed":
        st.caption(f"{badge('red', 'Search didn’t finish')} {note} Tap Find it on the "
                   "employer's site to try again.")
    elif claude_ready():
        st.caption("Not looked for on the employer's site yet.")


def claude_ready() -> bool:
    """Whether the Claude key is set (ai.ready; the SDK is slow to import, so
    only when asked)."""
    import ai
    return ai.ready()


def claude_button(label: str, key: str, active: bool = True, **kwargs) -> bool:
    """A button for something Claude does: its key starts "claude_", which
    the stylesheet marks with Claude's spark (active=False: an ordinary
    button, e.g. when no Claude key is set and the click won't call it)."""
    return st.button(label, key=f"{theme.CLAUDE_KEY}{key}" if active else key, **kwargs)


def claude_submit(label: str, key: str, **kwargs) -> bool:
    """A form's submit button for something Claude does, with the mark."""
    return st.form_submit_button(label, key=f"{theme.CLAUDE_KEY}{key}", **kwargs)


def find_posting_button(app: dict, key: str) -> None:
    """A button that has Claude look for the posting on the employer's own
    site and saves the link (find_company_posting); shown when the key is set."""
    if not claude_ready():
        return
    if claude_button("Find it on the employer's site", f"find_posting_{key}", width="stretch",
                     help="Claude searches the web for this posting on the employer's own "
                          "careers site, so you can apply there (about 15 cents)"):
        with st.spinner("Searching the employer's site…"):
            notes = find_company_posting(app, data.today())
        done(" ".join(notes))


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

def _app_password() -> str | None:
    return db.secret("APP_PASSWORD")


def _google_ready() -> bool:
    """Sign in with Google is set up: the [auth] section is in the secrets."""
    return db.secret("auth") is not None


def _allowed_emails() -> set[str]:
    """ALLOWED_EMAILS: who may sign in with Google, comma-separated. Kept in
    the secrets, not this public repo."""
    return {e.strip().lower() for e in str(db.secret("ALLOWED_EMAILS") or "").split(",")
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
    return badge(ATTENTION_COLORS.get(kind, "gray"),
                 logic.ATTENTION_LABELS.get(kind, kind.replace("_", " ").capitalize()))


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
    text = md(text).replace("–", "\u2060–\u2060")          # a range stays on one line
    if state == "listed":
        return text
    return badge("yellow", f":material/warning: {text}"
                 + (" (estimate)" if state == "estimated" else ""))


def schedule_badge(schedule) -> str:
    """A green badge for a compressed schedule ("9/80 schedule"); '' without one."""
    if not schedule:
        return ""
    return badge("green", "Compressed week" if schedule == "compressed week"
                 else f"{schedule} schedule")


def fit_breakdown(detail) -> str:
    """'Role 9 · Industry 6 · …' from a lead's fit_detail, with the schedule
    bonus when it has one and a red badge when a deal-breaker capped the
    score; '' when there is no breakdown."""
    detail = logic.value(detail)
    if not isinstance(detail, dict) or not (detail.get("ratings") or detail.get("schedule")):
        return ""
    ratings = detail.get("ratings") or {}
    parts = [f"{label.split(' ')[0]}\u00a0{ratings[key]}"           # no break before the number
             for key, (label, _, _) in config.FIT_CATEGORIES.items() if key in ratings]
    if detail.get("schedule"):
        parts.append(f"Schedule\u00a0+{config.SCHEDULE_BONUS:g}")
    text = " · ".join(parts)
    return f"{badge('red', 'Deal-breaker')} {text}" if detail.get("deal_breaker") else text


def optional(options: list[str]) -> list[str]:
    """A selectbox's options with a leading blank for "not set"."""
    return [""] + options


def index_of(options: list, current, default: int = 0) -> int:
    return options.index(current) if current in options else default


STATUS_HELP = (
    "Saved → Applied → Screening → Interviewing → Offer, then Accepted, "
    "Rejected or Withdrawn. Open statuses: " + ", ".join(config.OPEN_STATUSES) + "."
)
