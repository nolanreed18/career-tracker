"""The daily review's digest email, rendered from the leads it added: a
summary up top, every lead with its score, pay and posting link, what the
tracker says needs doing today, and links into the app. Pure: no database
and no Streamlit (leads.py gathers the data and prints the result).

The markup is what email clients allow: tables, every style inline (the
owner reads it in Outlook on a phone, which ignores a stylesheet), no web
fonts, and the colours of the app's light look (theme.py). It stays small
because Gmail clips mail over 100 KB and the review pastes the whole thing
into one Gmail call."""

import html
from datetime import date

import config
import logic

BLUE, CYAN, GREEN, ORANGE, RED, GRAY = "#2563eb", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e", "#64748b"
BG, CARD, BORDER, TEXT, TEXT2, MUTED = "#f8fafc", "#ffffff", "#e2e8f0", "#0f172a", "#475569", "#64748b"
YELLOW_BG, YELLOW_TEXT = "#fef9c3", "#854d0e"
FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
ATTENTION = {"overdue": (RED, "Overdue"), "due": (ORANGE, "Due today"),
             "interview": (BLUE, "Interview"), "follow_up": (ORANGE, "Follow up"),
             "stale_saved": (GRAY, "Saved")}
WARNING = "&#9888;&#xFE0E;"          # a text-style warning sign, coloured by its span
TEXT_FULL = 10                       # leads written out in full (with links) in the text version
LINK_MAX = 200                       # longer links (opaque redirects) are left to the app

def e(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def page(app_url: str, name: str = "") -> str:
    return app_url.rstrip("/") + (f"/{name}" if name else "")


def subject(today: date, leads: list[dict], problem: str | None = None) -> str:
    when = f"{today:%b} {today.day}"
    if problem:
        return f"Job leads {when}: the review hit a problem"
    if not leads:
        return f"Job leads {when}: nothing new"
    strong = sum(logic.fit_tier(lead.get("fit_score")) == "strong" for lead in leads)
    return f"Job leads {when}: {len(leads)} new, {strong} strong"


def tiers(leads: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"strong": [], "maybe": [], "weak": [], "unscored": []}
    for lead in leads:
        out[logic.fit_tier(lead.get("fit_score")) or "unscored"].append(lead)
    return out


# ---- pieces -----------------------------------------------------------------

# Styles are inline, every one: Outlook on the phone ignores a stylesheet,
# Gmail keeps one, inline works in both. bgcolor attributes back the
# backgrounds up, and nothing uses a gradient (Outlook drops the background
# and keeps the white text, which made the button vanish).
F = f"font-family:{FONT};"
TEXT_STYLE = f"{F}color:{TEXT}"
CARD_STYLE = f"border:1px solid {BORDER};border-radius:12px"
KICKER = "font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase"
CHIP = "display:inline-block;padding:2px 8px;border-radius:10px;line-height:18px"
SCALE = [(1, (225, 29, 72)), (5, (249, 115, 22)), (6.5, (217, 119, 6)), (8, (22, 163, 74)),
         (10, (4, 120, 87))]          # a 1–10 score's colour: red, orange, amber, green, emerald


def score_color(score) -> str:
    """The colour for a 1–10 score, blended along SCALE; grey when unscored."""
    score = logic.value(score)
    if score is None:
        return GRAY
    s = max(SCALE[0][0], min(SCALE[-1][0], float(score)))
    for (lo, a), (hi, b) in zip(SCALE, SCALE[1:]):
        if s <= hi:
            t = (s - lo) / (hi - lo)
            return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))
    return "#%02x%02x%02x" % SCALE[-1][1]


def tint(color: str, amount: float = 0.85) -> str:
    """The colour mixed towards white: a chip's background under its text."""
    parts = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(x + (255 - x) * amount) for x in parts)


def pill(text: str, color: str, background: str) -> str:
    """A small rounded label. Spaces in `text` should be &nbsp; so it never wraps."""
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            f'font-size:12px;font-weight:600;line-height:18px;color:{color};'
            f'background-color:{background}">{text}</span>')


def score_pill(score) -> str:
    return (f'<span style="display:inline-block;min-width:34px;text-align:center;'
            f'padding:6px 6px;border-radius:10px;font-size:17px;font-weight:700;color:#fff;'
            f'background-color:{score_color(score)}">{logic.fit_text(score) or "–"}</span>')


def pay_html(lead: dict) -> str:
    state, text = logic.pay_state(lead.get("salary_min"), lead.get("salary_max"),
                                  lead.get("pay_source"))
    if state == "listed":
        return f'<span style="font-weight:600">{e(text)}</span>'
    label = f"{WARNING}&nbsp;{e(text)}" + ("&nbsp;(estimate)" if state == "estimated" else "")
    note = lead.get("pay_note") if state == "estimated" else None
    return pill(label, YELLOW_TEXT, YELLOW_BG) + (
        f' <span style="color:{MUTED};font-size:13px">{e(note)}</span>'
        if logic.value(note) else "")


def rating_chips(detail) -> str:
    detail = logic.value(detail)
    if not isinstance(detail, dict) or not detail.get("ratings"):
        return ""
    ratings = detail["ratings"]
    chips = []                       # smaller than pill(): the div carries the font, and
    for key, (label, _, _) in config.FIT_CATEGORIES.items():   # 20 cards × 6 chips add up
        if key not in ratings:
            continue
        n = ratings[key]
        color = score_color(n)
        chips.append(f'<span style="{CHIP};color:{color};background-color:{tint(color)}">'
                     f'{e(label.split(" ")[0])}&nbsp;{n}</span>')
    if detail.get("deal_breaker"):
        chips.insert(0, f'<span style="{CHIP};color:#fff;background-color:{RED}">'
                        'Deal&#8209;breaker</span>')
    return (f'<div style="margin-top:8px;font-size:12px;font-weight:600;line-height:26px">'
            f'{" ".join(chips)}</div>')


def where(lead: dict) -> str:
    location, mode = logic.value(lead.get("location")), logic.value(lead.get("work_mode"))
    if mode and location and mode in location.lower():
        mode = None
    return " · ".join(str(p) for p in (lead.get("source"), location, mode) if p)


def link(lead: dict) -> str | None:
    """The posting link, cleaned up; None when there is none or it is huge
    (an opaque redirect: the app has it, and the email stays small)."""
    url = logic.job_link(lead.get("job_url"))
    return url if url and len(url) <= LINK_MAX else None


def title_link(lead: dict) -> str:
    title = f"<strong>{e(lead.get('title'))}</strong>"
    url = link(lead)
    return (f'<a href="{e(url)}" style="color:{BLUE};text-decoration:none">{title}</a>'
            if url else title)


def card(extra: str = "") -> str:
    """The opening tag of a white, bordered card table."""
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'bgcolor="{CARD}" style="{CARD_STYLE}{";" + extra if extra else ""}">')


def lead_card(lead: dict) -> str:
    reason = lead.get("fit_reason")
    return (card("margin:0 0 10px 0")
            + f'<tr><td width="46" valign="top" style="padding:14px 0 14px 14px">'
            f'{score_pill(lead.get("fit_score"))}</td>'
            f'<td valign="top" style="padding:14px 16px 14px 12px;font-size:15px;'
            f'line-height:22px;{TEXT_STYLE}">{title_link(lead)} '
            f'<span style="color:{TEXT2}">— {e(lead.get("company"))}</span>'
            f'<br><span style="color:{MUTED};font-size:13px">{e(where(lead))}</span><br>'
            f'<span style="font-size:13px">{pay_html(lead)}</span>'
            + (f'<div style="margin-top:6px;color:{TEXT2};font-size:14px">{e(reason)}</div>'
               if logic.value(reason) else "")
            + rating_chips(lead.get("fit_detail")) + "</td></tr></table>")


ROW_STYLE = f"padding:4px 0;font-size:13px;color:{MUTED};{F}"


def compact_row(lead: dict, linked: bool = True) -> str:
    """One line: score, title (linked unless the link is huge), company, place."""
    url = link(lead) if linked else None
    title = e(lead.get("title"))
    if url:
        title = f'<a href="{e(url)}" style="color:{TEXT2}">{title}</a>'
    location = lead.get("location")
    return (f'<tr><td style="{ROW_STYLE}"><strong style="color:{TEXT2}">'
            f'{logic.fit_text(lead.get("fit_score")) or "–"}</strong> &nbsp;{title} — '
            f'{e(lead.get("company"))}'
            + (f" · {e(location)}" if logic.value(location) else "") + "</td></tr>")


def rows_table(leads: list[dict], linked: bool, what: str, url: str) -> str:
    """One-line rows for up to DIGEST_ROWS leads, then a count of the rest
    with a link to the app, so a big day can't make a huge email."""
    rows = "".join(compact_row(lead, linked) for lead in leads[:config.DIGEST_ROWS])
    if len(leads) > config.DIGEST_ROWS:
        rows += (f'<tr><td style="{ROW_STYLE}">…and {len(leads) - config.DIGEST_ROWS} more '
                 f'{what} <a href="{e(url)}" style="color:{CYAN}">in the app</a></td></tr>')
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            + rows + "</table>")


def section(title: str, color: str, body: str) -> str:
    return (f'<tr><td style="padding:22px 0 8px 0;font-size:12px;font-weight:700;'
            f'letter-spacing:.08em;text-transform:uppercase;color:{color};{F}">{title}</td></tr>'
            f'<tr><td>{body}</td></tr>')


def button(text: str, url: str, primary: bool = True) -> str:
    """One button cell: solid colours only (a gradient loses in Outlook)."""
    bg, fg, border = (BLUE, "#ffffff", BLUE) if primary else (CARD, BLUE, BORDER)
    return (f'<td bgcolor="{bg}" style="border-radius:8px;border:1px solid {border}">'
            f'<a href="{e(url)}" style="display:inline-block;padding:10px 18px;font-size:14px;'
            f'font-weight:600;text-decoration:none;color:{fg};{F}">{text}</a></td>')


def tile(number, label: str, color: str) -> str:
    return (f'<td style="padding:0 4px">{card()}<tr><td style="padding:12px 10px;'
            f'text-align:center;{F}"><div style="font-size:24px;font-weight:700;color:{color}">'
            f'{number}</div><div style="font-size:11px;font-weight:600;letter-spacing:.06em;'
            f'text-transform:uppercase;color:{MUTED}">{label}</div></td></tr></table></td>')


def attention_rows(items: list[logic.Attention]) -> str:
    rows = []
    for item in items:
        color, label = ATTENTION.get(item.kind, (GRAY, item.kind))
        rows.append(f'<tr><td style="padding:8px 0;border-bottom:1px solid {BORDER};'
                    f'font-size:14px;{TEXT_STYLE}">{pill(label.replace(" ", "&nbsp;"), "#fff", color)} '
                    f'<strong>{e(item.headline)}</strong><br>'
                    f'<span style="color:{TEXT2};font-size:13px">{e(item.detail)}</span>'
                    '</td></tr>')
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            + "".join(rows) + "</table>")


def note_card(color: str, background: str, kicker: str, body: str) -> str:
    """A card with a coloured left edge: the top pick, the waiting list, a problem."""
    return (f'<tr><td style="padding:12px 0 0 0"><table role="presentation" width="100%" '
            f'cellpadding="0" cellspacing="0" bgcolor="{background}" '
            f'style="{CARD_STYLE};border-left:4px solid {color}"><tr><td style="padding:14px '
            f'16px;font-size:14px;line-height:22px;{TEXT_STYLE}">'
            f'<div style="{KICKER};color:{color}">{kicker}</div>{body}</td></tr></table></td></tr>')


# ---- the email --------------------------------------------------------------

def render(today: date, leads: list[dict], attention: list[logic.Attention], app_url: str,
           notes: dict | None = None, waiting: list[dict] = ()) -> dict:
    """{"subject", "html", "text"} for the digest. `leads` are the rows the
    review added today (data.leads_found), best first; `attention` is what
    Home would list (logic.needs_attention); `notes` may give emails_read,
    sources ({site: emails}), already_known, duplicates and problem;
    `waiting` are strong leads from earlier days still in the inbox."""
    notes = notes or {}
    waiting = list(waiting)
    problem = logic.value(notes.get("problem"))
    by_tier = tiers(leads)
    strong, maybe = by_tier["strong"], by_tier["maybe"]
    weak = by_tier["weak"] + by_tier["unscored"]
    leads_url, apps_url = page(app_url, "Job_Leads"), page(app_url, "Applications")
    emails = notes.get("emails_read")
    sources = notes.get("sources") or {}
    read_line = ""
    if emails:
        read_line = f"from {logic.plural(int(emails), 'alert email')}"
        if sources:
            read_line += " (" + ", ".join(f"{e(k)} {v}" for k, v in sources.items()) + ")"
    headline = ("The review stopped before it finished." if problem else
                "Nothing new today." if not leads else
                f"{logic.plural(len(leads), 'new lead')} · {len(strong)} strong · "
                f"{len(maybe)} worth a look" + (f" · {read_line}" if read_line else ""))

    rows = [f'<tr><td bgcolor="{BLUE}" style="padding:26px 28px;border-radius:16px;'
            f'color:#ffffff;{F}"><div style="{KICKER};color:#dbeafe">Career Tracker · daily '
            f'review</div><div style="font-size:26px;font-weight:700;margin-top:6px">'
            f'{today:%A, %B} {today.day}</div><div style="font-size:15px;margin-top:6px;'
            f'color:#eff6ff">{headline}</div></td></tr>']
    if problem:
        rows.append(note_card(RED, "#fff1f2", "Something went wrong.", e(problem)))
    if leads:
        rows.append('<tr><td style="padding:16px 0 0 0"><table role="presentation" width="100%" '
                    'cellpadding="0" cellspacing="0"><tr>'
                    + tile(len(leads), "New", BLUE) + tile(len(strong), "Strong", GREEN)
                    + tile(len(maybe), "Worth a look", CYAN) + tile(len(weak), "Weak", GRAY)
                    + "</tr></table></td></tr>")
    rows.append('<tr><td style="padding:16px 0 0 0"><table role="presentation" cellpadding="0" '
                f'cellspacing="0"><tr>{button("Open Job Leads", leads_url)}<td width="8"></td>'
                f'{button("Open Applications", apps_url, primary=False)}</tr></table></td></tr>')
    if leads:
        top = leads[0]
        reason = logic.value(top.get("fit_reason"))
        rows.append(note_card(
            score_color(top.get("fit_score")), CARD,
            f"Top pick · {logic.fit_text(top.get('fit_score')) or 'unscored'}",
            f'<div style="margin-top:4px;font-size:16px">{title_link(top)} '
            f'<span style="color:{TEXT2}">— {e(top.get("company"))}</span></div>'
            + (f'<div style="margin-top:4px;color:{TEXT2}">{e(reason)}</div>' if reason else "")))
    if waiting:
        names = "<br>".join(
            f'<strong>{logic.fit_text(w.get("fit_score"))}</strong> &nbsp;{title_link(w)} '
            f'<span style="color:{TEXT2}">— {e(w.get("company"))}</span>' for w in waiting[:5])
        more = f"<br>…and {len(waiting) - 5} more" if len(waiting) > 5 else ""
        rows.append(note_card(
            ORANGE, CARD,
            f"Still waiting · {logic.plural(len(waiting), 'strong lead')} from earlier this week",
            f'<div style="margin-top:4px">{names}{more}</div>'))
    budget = config.DIGEST_CARDS                   # full cards, best first; the rest are rows

    def tier_body(tier_leads: list[dict], what: str) -> str:
        nonlocal budget
        as_cards, as_rows = tier_leads[:budget], tier_leads[budget:]
        budget -= len(as_cards)
        return ("".join(lead_card(lead) for lead in as_cards)
                + (rows_table(as_rows, True, what, leads_url) if as_rows else ""))

    if strong:
        rows.append(section(f"Strong fits ({config.STRONG_FIT}+)", GREEN,
                            tier_body(strong, "strong fits")))
    if maybe:
        rows.append(section(f"Worth a look ({config.MAYBE_FIT}–{config.STRONG_FIT - 0.1:g})", BLUE,
                            tier_body(maybe, "worth a look")))
    if weak:
        rows.append(section(f"Weak or unscored ({len(weak)}, hidden in the app until asked)", GRAY,
                            rows_table(weak, False, "weak or unscored", leads_url)))
    if attention:
        rows.append(section("On your plate today", ORANGE, attention_rows(attention)))

    weights = " · ".join(f"{label.split(' ')[0]} {weight:.0%}"
                         for label, weight, _ in config.FIT_CATEGORIES.values())
    facts = []
    if emails:
        facts.append(f"Read {logic.plural(int(emails), 'alert email')}")
    if notes.get("already_known"):
        facts.append(f"{notes['already_known']} already in the tracker")
    if notes.get("duplicates"):
        facts.append(f"{notes['duplicates']} listed twice")
    rows.append(f'<tr><td style="padding:22px 0 0 0;font-size:12px;line-height:18px;'
                f'color:{MUTED};{F}">' + (" · ".join(facts) + "<br>" if facts else "")
                + f'Scores are weighted averages of 1–10 ratings against <a href="{e(leads_url)}" '
                f'style="color:{CYAN}">what you\'re looking for</a>: {weights}. A deal-breaker '
                f'caps the score at {config.DEAL_BREAKER_CAP:g}. '
                f'{pill(f"{WARNING}&nbsp;pay", YELLOW_TEXT, YELLOW_BG)} marks an estimate or missing '
                f'pay; pay the review couldn\'t find is left out of the score.</td></tr>')

    html_out = (f'<!DOCTYPE html><html><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width">'
                f'<title>{e(subject(today, leads, problem))}</title></head>'
                f'<body style="margin:0;padding:0;background-color:{BG}">'
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'bgcolor="{BG}"><tr><td align="center" style="padding:24px 12px">'
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="max-width:640px">' + "\n".join(rows)
                + "</table></td></tr></table></body></html>")
    return {"subject": subject(today, leads, problem), "html": html_out,
            "text": render_text(today, leads, attention, app_url, notes, waiting)}


def render_text(today: date, leads: list[dict], attention: list[logic.Attention],
                app_url: str, notes: dict, waiting: list[dict] = ()) -> str:
    """The plain-text alternative, for clients that don't show HTML."""
    lines = [f"Job leads for {today:%A, %B} {today.day}", ""]
    problem = logic.value(notes.get("problem"))
    if problem:
        lines += [f"Something went wrong: {problem}", ""]
    if waiting:
        lines.append(f"Still waiting in your inbox: {logic.plural(len(waiting), 'strong lead')}"
                     " from earlier this week: "
                     + "; ".join(f"{logic.fit_text(w.get('fit_score'))} {w.get('title')} — "
                                 f"{w.get('company')}" for w in waiting[:5]))
        lines.append("")
    if not leads:
        lines.append("Nothing new today.")
    by_tier = tiers(leads)
    full = by_tier["strong"][:TEXT_FULL]           # in full, with their links
    others = by_tier["strong"][TEXT_FULL:] + by_tier["maybe"] + by_tier["weak"] + by_tier["unscored"]
    for lead in full:
        state, pay = logic.pay_state(lead.get("salary_min"), lead.get("salary_max"),
                                     lead.get("pay_source"))
        if state == "estimated":
            pay += " (estimate)"
        lines.append(f"{logic.fit_text(lead.get('fit_score')) or '-'}  {lead.get('title')} — "
                     f"{lead.get('company')}")
        lines.append(f"     {where(lead)} · {pay}")
        if logic.value(lead.get("fit_reason")):
            lines.append(f"     {lead['fit_reason']}")
        if link(lead):
            lines.append(f"     {link(lead)}")
        lines.append("")
    for lead in others[:config.DIGEST_ROWS]:
        lines.append(f"{logic.fit_text(lead.get('fit_score')) or '-'}  {lead.get('title')} — "
                     f"{lead.get('company')} · {where(lead)}")
    if len(others) > config.DIGEST_ROWS:
        lines.append(f"…and {len(others) - config.DIGEST_ROWS} more in the app.")
    if others:
        lines.append("")
    if attention:
        lines.append("On your plate today:")
        lines += [f"- {ATTENTION.get(i.kind, (None, i.kind))[1]}: {i.headline}: {i.detail}"
                  for i in attention]
        lines.append("")
    lines.append(f"Job Leads: {page(app_url, 'Job_Leads')}")
    lines.append(f"Applications: {page(app_url, 'Applications')}")
    return "\n".join(lines)
