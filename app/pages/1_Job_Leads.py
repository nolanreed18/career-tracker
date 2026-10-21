"""Job leads: jobs from your alert emails, scored for fit by the daily
review, and what you're looking for, which the scores are based on."""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import config
import data
import logic
from ui import (
    badge,
    bump_round,
    card,
    done,
    empty,
    fit_badge,
    fit_breakdown,
    md,
    pay_badge,
    prepare_application,
    round_key,
    sections,
    setup,
)

setup("Job Leads", "From your alert emails, scored for fit every morning")


today = data.today()


def describe(lead) -> str:
    """'LinkedIn · Denver, CO · hybrid · found yesterday', markdown-safe."""
    location, mode = logic.value(lead.location), logic.value(lead.work_mode)
    if mode and location and mode in location.lower():
        mode = None                                 # "Remote (US) · remote"
    parts = [lead.source, location, mode, f"found {logic.when(lead.found_on, today)}"]
    return md(" · ".join(str(p) for p in parts if p))


def pay_line(lead) -> str:
    """The pay badge, with where an estimate came from."""
    line = pay_badge(lead.salary_min, lead.salary_max, lead.pay_source)
    if logic.value(lead.pay_source) == "estimated" and logic.value(lead.pay_note):
        line += f" · {md(lead.pay_note)}"
    return line


def lead_card(lead) -> None:
    """One lead: score, title (opens the posting), where, pay, ratings and
    reason, then Add and a "Dismiss…" pick that asks why (one reason or several)."""
    lead_id = int(lead.lead_id)
    with card(f"lead-{lead_id}"):
        fit = fit_badge(lead.fit_score)
        new = badge("blue", "New") if lead.found_on == today else ""
        title = md(lead.title)
        if url := logic.job_link(lead.job_url):       # the title opens the posting
            title = f"[{title}]({url.replace(')', '%29').replace(' ', '%20')})"
        head = " · ".join(part for part in (new, fit) if part)
        st.markdown(f"{head + ' · ' if head else ''}**{title}**\u00a0—\u00a0{md(lead.company)}")
        st.caption(f"{describe(lead)} · {pay_line(lead)}")
        if breakdown := fit_breakdown(lead.fit_detail):
            st.caption(breakdown)
        if logic.value(lead.fit_reason):
            st.markdown(md(lead.fit_reason))
        move_col, dismiss_col = st.columns(2, wrap=False)
        if move_col.button("Add", key=f"move_{lead_id}", type="primary", width="stretch",
                           help="Save it as an application, read the posting from its link and "
                                "have Claude find it on the employer's own site to apply there"):
            application_id = data.move_lead_to_applications(lead_id, today)
            with st.spinner("Saved. Reading the posting and looking for it on the employer's "
                            "site…"):
                notes = prepare_application(application_id, today)
            st.session_state["flash"] = " ".join(["Added to Applications as Saved."] + notes)
            st.session_state["open_application"] = application_id
            st.switch_page("pages/2_Applications.py")
        reasons = dismiss_col.multiselect(
            "Dismiss", config.DISMISS_REASONS, placeholder="Dismiss…",
            key=f"dismiss_{lead_id}_{round_key('leads')}", label_visibility="collapsed",
            help="Pick why, one reason or several, then tap Dismiss: the daily review "
                 "reads recent reasons")
        if reasons and st.button(f"Dismiss: {', '.join(reasons)}", key=f"dismiss_go_{lead_id}",
                                 width="stretch"):
            data.set_lead_status(lead_id, "dismissed", reasons, today)
            bump_round("leads")
            done(f"Dismissed {lead.title} — {lead.company} ({', '.join(reasons)}).")


def in_batches(frame, key: str, draw) -> None:
    """draw(lead) for the first config.LEADS_SHOWN leads, and a button for
    the next batch: a long inbox stays quick to draw on a phone."""
    batches = st.session_state.get(f"batches_{key}", 1)
    for lead in frame.head(config.LEADS_SHOWN * batches).itertuples():
        draw(lead)
    left = len(frame) - config.LEADS_SHOWN * batches
    if left > 0 and st.button(f"Show {min(config.LEADS_SHOWN, left)} more ({left} left)",
                              key=f"more_{key}", width="stretch"):
        st.session_state[f"batches_{key}"] = batches + 1
        st.rerun()


def dismissed_card(lead) -> None:
    lead_id = int(lead.lead_id)
    with card(f"dismissed-{lead_id}"):
        text_col, button_col = st.columns([4, 1], vertical_alignment="center", wrap=False)
        fit = fit_badge(lead.fit_score)
        why = ""
        if logic.value(lead.dismiss_reason):
            why = " ".join(badge("gray", r) for r in logic.dismiss_reasons(lead.dismiss_reason))
            if logic.value(lead.dismissed_on):
                why += f" dismissed {logic.when(lead.dismissed_on, today)}"
            why += "  \n"
        text_col.markdown(f"{fit + ' · ' if fit else ''}**{md(lead.title)}**\u00a0—\u00a0"
                          f"{md(lead.company)}  \n{why}{describe(lead)} · {pay_line(lead)}")
        if button_col.button("Restore", key=f"restore_{lead_id}", width="stretch"):
            data.set_lead_status(lead_id, "new")
            bump_round("leads")
            done(f"Restored {lead.title} — {lead.company}.")


section = sections("leads", ["Inbox", "Stale", "Dismissed", "What I'm looking for"])

# ---- inbox ------------------------------------------------------------------

if section == "Inbox":
    leads, stale = logic.split_stale(data.job_leads("new"), today)
    if data.job_profile() is None:
        st.warning("Fill in **What I'm looking for** so the daily review can score jobs "
                   "for fit.")
    if leads.empty:
        empty("inbox", "No new leads",
              "Jobs from your alert emails show up here after the daily review, best fit first."
              + (f" {logic.plural(len(stale), 'older lead')} under Stale." if len(stale) else ""))
    else:
        strong = leads["fit_score"].fillna(0) >= config.STRONG_FIT
        weak = leads["fit_score"].map(logic.is_weak)
        fresh = leads["found_on"] == today
        st.caption(f"{logic.plural(len(leads), 'new lead')}: {int(fresh.sum())} today, "
                   f"{int(strong.sum())} strong (fit {config.STRONG_FIT}+), {int(weak.sum())} "
                   f"weak (under {config.MAYBE_FIT})"
                   + (f"; {len(stale)} stale under Stale." if len(stale) else "."))
        SHOW = {"today": "New today", "maybe": f"Worth a look ({config.MAYBE_FIT}+, any day)",
                "strong": f"Strong only ({config.STRONG_FIT}+)", "all": "All"}
        # The radio forgets its choice while another section is open; keep it ourselves.
        # It opens on the strong ones when there are any: the rest can wait.
        kept = st.session_state.get("leads_show_kept", "strong" if strong.any()
                                    else "today" if fresh.any() else "maybe")
        show = st.radio("Show", list(SHOW), horizontal=True, format_func=SHOW.get,
                        index=list(SHOW).index(kept), key="leads_show",
                        label_visibility="collapsed")
        st.session_state["leads_show_kept"] = show
        if show == "today":
            leads = leads[fresh & ~weak]                   # weak ones wait under All
            if hidden := int((fresh & weak).sum()):
                st.caption(f"{logic.plural(hidden, 'weak lead')} from today "
                           f"{'is' if hidden == 1 else 'are'} under All.")
        elif show == "strong":
            leads = leads[strong]
        elif show == "maybe":
            leads = leads[~weak]
        if leads.empty:
            empty("filter_alt", "Nothing in this view", "Choose All to see every lead.")
        in_batches(leads, "inbox", lead_card)

# ---- stale ------------------------------------------------------------------

if section == "Stale":
    _, stale = logic.split_stale(data.job_leads("new"), today)
    st.caption(f"Leads that arrived more than {config.LEAD_STALE_DAYS} days ago and were never "
               "added or dismissed. Postings this old are often closed; they stay here so the "
               "same job never comes back as new.")
    if stale.empty:
        empty("history", "Nothing stale", "Leads drop in here after "
              f"{config.LEAD_STALE_DAYS} days in the inbox.")
    in_batches(stale, "stale", lead_card)

# ---- dismissed --------------------------------------------------------------

if section == "Dismissed":
    dismissed = data.job_leads("dismissed")
    if dismissed.empty:
        empty("delete_sweep", "Nothing dismissed", "Leads you dismiss wait here in case you change your mind.")
    in_batches(dismissed, "dismissed", dismissed_card)

# ---- profile ----------------------------------------------------------------

if section == "What I'm looking for":
    profile = data.job_profile() or {}
    st.caption("The daily review reads this to score each job from 1 to 10. Plain "
               "sentences are fine; the more specific, the better the scores.")
    if profile:
        st.caption(f"Last saved {profile['updated_on']:%b %d, %Y}.")
    with st.form("job_profile"):
        target_roles = st.text_area(
            "Roles I want", value=profile.get("target_roles") or "",
            placeholder="e.g. Data Analyst, Analytics Engineer; mid or senior level")
        locations = st.text_input(
            "Where", value=profile.get("locations") or "",
            placeholder="e.g. Chicago area, or remote anywhere in the US")
        work_modes = st.multiselect(
            "Work modes I'd take", config.WORK_MODES,
            default=[m.strip() for m in (profile.get("work_modes") or "").split(",")
                     if m.strip() in config.WORK_MODES])
        min_salary = st.number_input("Lowest base salary I'd take ($/yr)", min_value=0,
                                     step=5000, value=profile.get("min_salary"))
        must_haves = st.text_area("Must-haves", value=profile.get("must_haves") or "",
                                  placeholder="e.g. SQL-heavy work, a real data team")
        nice_to_haves = st.text_area("Nice to have", value=profile.get("nice_to_haves") or "",
                                     placeholder="e.g. healthcare or fintech, 4-day week")
        deal_breakers = st.text_area("Deal-breakers", value=profile.get("deal_breakers") or "",
                                     placeholder="e.g. 100% travel, commission-only, "
                                                 "contract-to-hire")
        skip_companies = st.text_area(
            "Companies to skip", value=profile.get("skip_companies") or "",
            placeholder="One per line, e.g. staffing agencies or a company you've ruled out",
            help="The daily review drops their jobs before scoring. A name matches when it "
                 "appears in the employer's name, so \"Robert Half\" also catches "
                 "\"Robert Half Technology\".")
        about_me = st.text_area(
            "About me", value=profile.get("about_me") or "", height=200,
            placeholder="Your experience and skills, as on a resume: years, tools, "
                        "industries, highlights. Pasting your resume summary works.")
        saved = st.form_submit_button("Save", type="primary")
    if saved:
        data.save_job_profile(
            today, target_roles=target_roles, locations=locations,
            work_modes=", ".join(work_modes), min_salary=min_salary, must_haves=must_haves,
            nice_to_haves=nice_to_haves, deal_breakers=deal_breakers, about_me=about_me,
            skip_companies=skip_companies)
        done("Saved. The next daily review will use it.")

    with card("scoring"):
        st.markdown("**How scoring works**")
        st.markdown("The daily review rates each job 1–10 on every category below, against "
                    "what's written above; the score is the weighted average, to one decimal.")
        st.markdown("\n".join(f"- **{label}** ({weight:.0%}): {what}"
                              for label, weight, what in config.FIT_CATEGORIES.values()))
        st.caption(f"Any deal-breaker caps the score at {config.DEAL_BREAKER_CAP:g}. "
                   f"{config.STRONG_FIT}+ is a strong fit, {config.MAYBE_FIT}+ is worth a look. "
                   "The weights live in app/config.py.")
        st.markdown(f"**Pay.** {config.PAY_RESEARCH}")
        st.markdown(f"**Dismissals.** When you dismiss a lead you say why; the review reads "
                    f"the last {config.DISMISSAL_DAYS} days of reasons as a hint of what you "
                    "don't want, alongside the companies to skip above. Leads nobody touches "
                    f"for {config.LEAD_STALE_DAYS} days move to Stale.")
        st.caption(f"{pay_badge(120000, 140000, 'estimated')} means the review's estimate; "
                   f"{pay_badge(None, None, None)} means nothing was found, and the score "
                   "ignores pay.")
