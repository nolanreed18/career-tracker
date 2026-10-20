"""The daily review's digest email, rendered from the leads it added: a
summary up top, every lead with its score, pay and posting link, what the
tracker says needs doing today, and links into the app. Pure: no database
and no Streamlit (leads.py gathers the data and prints the result).

The markup is what email clients allow: tables, a short stylesheet of
classes (Gmail keeps those), no web fonts, and the colours of the app's
light look (theme.py). It stays small because Gmail clips mail over 100 KB
and the review pastes the whole thing into one Gmail call."""

import html
from datetime import date

import config
import logic

BLUE, CYAN, GREEN, ORANGE, RED, GRAY = "#2563eb", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e", "#64748b"
BG, CARD, BORDER, TEXT, TEXT2, MUTED = "#f8fafc", "#ffffff", "#e2e8f0", "#0f172a", "#475569", "#64748b"
YELLOW_BG, YELLOW_TEXT = "#fef9c3", "#854d0e"
FONT = "Inter,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
TIERS = {"strong": (GREEN, "#ecfdf5"), "maybe": (BLUE, "#eff6ff"), "weak": (GRAY, "#f1f5f9")}
ATTENTION = {"overdue": (RED, "Overdue"), "due": (ORANGE, "Due today"),
             "interview": (BLUE, "Interview"), "follow_up": (ORANGE, "Follow up"),
             "stale_saved": (GRAY, "Saved")}
WARNING = "&#9888;&#xFE0E;"          # a text-style warning sign, coloured by its span
TEXT_FULL = 10                       # leads written out in full (with links) in the text version

STYLE = f"""
body{{margin:0;padding:0;background:{BG}}}
table{{border-collapse:separate}}
.f{{font-family:{FONT};color:{TEXT}}}
.hd{{padding:26px 28px;border-radius:16px;background:{BLUE};background-image:linear-gradient(135deg,{BLUE},{CYAN});color:#ffffff}}
.k{{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}}
.cd{{background:{CARD};border:1px solid {BORDER};border-radius:12px}}
.sc{{padding:14px 16px;vertical-align:top;width:46px}}
.bd{{padding:14px 16px 14px 0;vertical-align:top;font-size:15px;line-height:22px}}
.n{{display:inline-block;min-width:34px;text-align:center;padding:6px 8px;border-radius:10px;font-size:17px;font-weight:700;color:#ffffff}}
.p{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}}
.pg{{color:{GREEN};background:#ecfdf5}}
.pn{{color:{TEXT2};background:#f1f5f9}}
.pr{{color:{RED};background:#fff1f2}}
.py{{color:{YELLOW_TEXT};background:{YELLOW_BG}}}
.pd{{color:#ffffff;background:{RED}}}
.m{{color:{MUTED};font-size:13px}}
.r{{margin-top:6px;color:{TEXT2};font-size:14px}}
.ch{{margin-top:8px;line-height:22px}}
a.t{{color:{BLUE};text-decoration:none}}
.co{{color:{TEXT2}}}
.bt{{display:inline-block;padding:10px 18px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;margin:0 8px 8px 0}}
.se{{padding:22px 0 8px 0;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
.ti{{padding:12px 10px;text-align:center}}
.ti b{{display:block;font-size:24px}}
.ti span{{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:{MUTED}}}
.wk{{padding:4px 0;font-size:13px;color:{MUTED}}}
.at{{padding:8px 0;border-bottom:1px solid {BORDER};font-size:14px}}
.ft{{padding:22px 0 0 0;font-size:12px;line-height:18px;color:{MUTED}}}
"""


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

def pill(text: str, kind: str) -> str:
    """A rounded label: kind g (good), n (neutral), r (bad), y (unverified), d (deal-breaker)."""
    return f'<span class="p p{kind}">{text}</span>'


def solid_pill(text: str, color: str) -> str:
    """A white-on-colour label (the few attention rows; inline so any colour works)."""
    return f'<span class="p" style="color:#ffffff;background:{color}">{text}</span>'


def score_pill(score) -> str:
    tier = logic.fit_tier(score)
    if tier is None:
        return pill("–", "n")
    return f'<span class="n" style="background:{TIERS[tier][0]}">{logic.fit_text(score)}</span>'


def pay_html(lead: dict) -> str:
    state, text = logic.pay_state(lead.get("salary_min"), lead.get("salary_max"),
                                  lead.get("pay_source"))
    if state == "listed":
        return f'<span style="font-weight:600">{e(text)}</span>'
    label = f"{WARNING} {e(text)}" + (" (estimate)" if state == "estimated" else "")
    note = lead.get("pay_note") if state == "estimated" else None
    return pill(label, "y") + (
        f' <span class="m">{e(note)}</span>' if logic.value(note) else "")


def rating_chips(detail) -> str:
    detail = logic.value(detail)
    if not isinstance(detail, dict) or not detail.get("ratings"):
        return ""
    ratings = detail["ratings"]
    chips = []
    for key, (label, _, _) in config.FIT_CATEGORIES.items():
        if key not in ratings:
            continue
        n = ratings[key]
        kind = "g" if n >= config.STRONG_FIT else "n" if n >= config.MAYBE_FIT else "r"
        chips.append(pill(f"{e(label.split(' ')[0])} {n}", kind))
    if detail.get("deal_breaker"):
        chips.insert(0, pill("Deal-breaker", "d"))
    return f'<div class="ch">{" ".join(chips)}</div>'


def where(lead: dict) -> str:
    location, mode = logic.value(lead.get("location")), logic.value(lead.get("work_mode"))
    if mode and location and mode in location.lower():
        mode = None
    return " · ".join(str(p) for p in (lead.get("source"), location, mode) if p)


def title_link(lead: dict) -> str:
    title = f"<strong>{e(lead.get('title'))}</strong>"
    url = logic.job_link(lead.get("job_url"))
    return f'<a class="t" href="{e(url)}">{title}</a>' if url else title


def lead_card(lead: dict) -> str:
    reason = lead.get("fit_reason")
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="cd" '
            f'style="margin:0 0 10px 0"><tr><td class="sc">{score_pill(lead.get("fit_score"))}</td>'
            f'<td class="bd f">{title_link(lead)} <span class="co">— {e(lead.get("company"))}</span>'
            f'<br><span class="m">{e(where(lead))}</span><br>'
            f'<span style="font-size:13px">{pay_html(lead)}</span>'
            + (f'<div class="r">{e(reason)}</div>' if logic.value(reason) else "")
            + rating_chips(lead.get("fit_detail")) + "</td></tr></table>")


def compact_row(lead: dict, link: bool = True) -> str:
    url = logic.job_link(lead.get("job_url")) if link else None
    title = e(lead.get("title"))
    if url:
        title = f'<a href="{e(url)}" style="color:{TEXT2}">{title}</a>'
    location = lead.get("location")
    return (f'<tr><td class="wk f"><strong class="co">'
            f'{logic.fit_text(lead.get("fit_score")) or "–"}</strong> &nbsp;{title} — '
            f'{e(lead.get("company"))}'
            + (f" · {e(location)}" if logic.value(location) else "") + "</td></tr>")


def rows_table(leads: list[dict], link: bool, what: str, url: str) -> str:
    """One-line rows for up to DIGEST_ROWS leads, then a count of the rest
    with a link to the app, so a big day can't make a huge email."""
    rows = "".join(compact_row(lead, link) for lead in leads[:config.DIGEST_ROWS])
    if len(leads) > config.DIGEST_ROWS:
        rows += (f'<tr><td class="wk f">…and {len(leads) - config.DIGEST_ROWS} more {what} '
                 f'<a href="{e(url)}" style="color:{CYAN}">in the app</a></td></tr>')
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            + rows + "</table>")


def section(title: str, color: str, body: str) -> str:
    return (f'<tr><td class="se f" style="color:{color}">{title}</td></tr>'
            f'<tr><td>{body}</td></tr>')


def button(text: str, url: str, primary: bool = True) -> str:
    style = (f"background:{BLUE};background-image:linear-gradient(135deg,{BLUE},{CYAN});"
             "color:#ffffff" if primary else
             f"background:{CARD};color:{BLUE};border:1px solid {BORDER}")
    return f'<a class="bt f" href="{e(url)}" style="{style}">{text}</a>'


def tile(number, label: str, color: str) -> str:
    return (f'<td style="padding:0 4px"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" class="cd"><tr><td class="ti f"><b style="color:{color}">{number}</b>'
            f'<span>{label}</span></td></tr></table></td>')


def attention_rows(items: list[logic.Attention]) -> str:
    rows = []
    for item in items:
        color, label = ATTENTION.get(item.kind, (GRAY, item.kind))
        rows.append(f'<tr><td class="at f">{solid_pill(label, color)} '
                    f'<strong>{e(item.headline)}</strong><br>'
                    f'<span class="co" style="font-size:13px">{e(item.detail)}</span></td></tr>')
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            + "".join(rows) + "</table>")


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

    rows = [f'<tr><td class="hd f"><div class="k" style="opacity:.85">Career Tracker · daily review</div>'
            f'<div style="font-size:26px;font-weight:700;margin-top:6px">{today:%A, %B} {today.day}</div>'
            f'<div style="font-size:15px;margin-top:6px;opacity:.95">{headline}</div></td></tr>']
    if problem:
        rows.append(f'<tr><td style="padding:16px 0 0 0"><table role="presentation" width="100%" '
                    f'cellpadding="0" cellspacing="0" class="cd" style="background:#fff1f2;'
                    f'border-color:{RED}"><tr><td class="f" style="padding:14px 16px;font-size:14px">'
                    f'<strong style="color:{RED}">Something went wrong.</strong> {e(problem)}'
                    f'</td></tr></table></td></tr>')
    if leads:
        rows.append('<tr><td style="padding:16px 0 0 0"><table role="presentation" width="100%" '
                    'cellpadding="0" cellspacing="0"><tr>'
                    + tile(len(leads), "New", BLUE) + tile(len(strong), "Strong", GREEN)
                    + tile(len(maybe), "Worth a look", CYAN) + tile(len(weak), "Weak", GRAY)
                    + "</tr></table></td></tr>")
    rows.append(f'<tr><td style="padding:16px 0 0 0">{button("Open Job Leads", leads_url)}'
                f'{button("Open Applications", apps_url, primary=False)}</td></tr>')
    if leads:
        top = leads[0]
        reason = logic.value(top.get("fit_reason"))
        color = TIERS[logic.fit_tier(top.get("fit_score")) or "weak"][0]
        rows.append(f'<tr><td style="padding:12px 0 0 0"><table role="presentation" width="100%" '
                    f'cellpadding="0" cellspacing="0" class="cd" style="border-left:4px solid {color}">'
                    f'<tr><td class="f" style="padding:14px 16px;font-size:14px">'
                    f'<div class="k" style="color:{MUTED}">Top pick · '
                    f'{logic.fit_text(top.get("fit_score")) or "unscored"}</div>'
                    f'<div style="margin-top:4px;font-size:16px">{title_link(top)} '
                    f'<span class="co">— {e(top.get("company"))}</span></div>'
                    + (f'<div class="r" style="margin-top:4px">{e(reason)}</div>' if reason else "")
                    + "</td></tr></table></td></tr>")
    if waiting:
        names = "<br>".join(
            f'<strong>{logic.fit_text(w.get("fit_score"))}</strong> &nbsp;{title_link(w)} '
            f'<span class="co">— {e(w.get("company"))}</span>' for w in waiting[:5])
        more = f"<br>…and {len(waiting) - 5} more" if len(waiting) > 5 else ""
        rows.append(f'<tr><td style="padding:12px 0 0 0"><table role="presentation" width="100%" '
                    f'cellpadding="0" cellspacing="0" class="cd" style="border-left:4px solid {ORANGE}">'
                    f'<tr><td class="f" style="padding:14px 16px;font-size:14px;line-height:22px">'
                    f'<div class="k" style="color:{ORANGE}">Still waiting · '
                    f'{logic.plural(len(waiting), "strong lead")} from earlier this week</div>'
                    f'<div style="margin-top:4px">{names}{more}</div></td></tr></table></td></tr>')
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
    rows.append('<tr><td class="ft f">' + (" · ".join(facts) + "<br>" if facts else "")
                + f'Scores are weighted averages of 1–10 ratings against <a href="{e(leads_url)}" '
                f'style="color:{CYAN}">what you\'re looking for</a>: {weights}. A deal-breaker '
                f'caps the score at {config.DEAL_BREAKER_CAP:g}. '
                f'{pill(f"{WARNING} pay", "y")} marks an estimate or missing '
                f'pay; pay the review couldn\'t find is left out of the score.</td></tr>')

    html_out = (f'<!DOCTYPE html><html><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width">'
                f'<title>{e(subject(today, leads, problem))}</title><style>{STYLE}</style></head>'
                f'<body><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="background:{BG}"><tr><td align="center" style="padding:24px 12px">'
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
        if url := logic.job_link(lead.get("job_url")):
            lines.append(f"     {url}")
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
