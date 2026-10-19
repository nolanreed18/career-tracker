"""Job leads: jobs from your alert emails, scored for fit by the daily
review, and what you're looking for, which the scores are based on."""

import streamlit as st

import config
import data
import logic
from ui import card, empty, fit_badge, fit_breakdown, md, sections, setup

setup("Job Leads", "From your alert emails, scored for fit every morning")


today = data.today()


def done(message: str) -> None:
    st.session_state["flash"] = message
    st.rerun()


def describe(lead) -> str:
    location, mode = logic.value(lead.location), logic.value(lead.work_mode)
    if mode and location and mode in location.lower():
        mode = None                                 # "Remote (US) · remote"
    parts = [lead.source, location, mode, logic.salary_range(lead.salary_min, lead.salary_max)]
    found = f"found {logic.when(lead.found_on, today)}"
    return " · ".join(str(p) for p in parts if p) + f" · {found}"


section = sections("leads", ["Inbox", "Dismissed", "What I'm looking for"])

# ---- inbox ------------------------------------------------------------------

if section == "Inbox":
    leads = data.job_leads("new")
    if data.job_profile() is None:
        st.warning("Fill in **What I'm looking for** so the daily review can score jobs "
                   "for fit.")
    if leads.empty:
        empty("inbox", "No new leads",
              "Jobs from your alert emails show up here after the daily review, best fit first.")
    else:
        strong = leads["fit_score"].fillna(0) >= config.STRONG_FIT
        weak = leads["fit_score"].map(logic.is_weak)
        st.caption(f"{logic.plural(len(leads), 'new lead')}: {int(strong.sum())} strong "
                   f"(fit {config.STRONG_FIT}+), {int(weak.sum())} weak (under "
                   f"{config.MAYBE_FIT}).")
        SHOW = {"maybe": f"Worth a look ({config.MAYBE_FIT}+)",
                "strong": f"Strong only ({config.STRONG_FIT}+)", "all": "All"}
        show = st.radio("Show", list(SHOW), horizontal=True, format_func=SHOW.get,
                        key="leads_show", label_visibility="collapsed")
        if show == "strong":
            leads = leads[strong]
        elif show == "maybe":
            leads = leads[~weak]
        if leads.empty:
            empty("filter_alt", "Nothing in this view", "Choose All to see every lead.")
        for lead in leads.itertuples():
            lead_id = int(lead.lead_id)
            with card(f"lead-{lead_id}"):
                fit = fit_badge(lead.fit_score)
                title = md(lead.title)
                if url := logic.job_link(lead.job_url):       # the title opens the posting
                    title = f"[{title}]({url.replace(')', '%29').replace(' ', '%20')})"
                st.markdown(f"{fit + ' · ' if fit else ''}**{title}** — {md(lead.company)}")
                st.caption(md(describe(lead)))
                if breakdown := fit_breakdown(lead.fit_detail):
                    st.caption(breakdown)
                if logic.value(lead.fit_reason):
                    st.markdown(md(lead.fit_reason))
                move_col, dismiss_col = st.columns(2, wrap=False)
                if move_col.button("Add", key=f"move_{lead_id}", type="primary",
                                   width="stretch",
                                   help="Add to Applications as Saved, with this fit note"):
                    application_id = data.move_lead_to_applications(lead_id, today)
                    st.session_state["flash"] = "Added to Applications as Saved."
                    st.session_state["open_application"] = application_id
                    st.switch_page("pages/1_Applications.py")
                if dismiss_col.button("Dismiss", key=f"dismiss_{lead_id}", width="stretch"):
                    data.set_lead_status(lead_id, "dismissed")
                    done(f"Dismissed {lead.title} — {lead.company}.")

# ---- dismissed --------------------------------------------------------------

if section == "Dismissed":
    dismissed = data.job_leads("dismissed")
    if dismissed.empty:
        empty("delete_sweep", "Nothing dismissed", "Leads you dismiss wait here in case you change your mind.")
    for lead in dismissed.itertuples():
        lead_id = int(lead.lead_id)
        with card(f"dismissed-{lead_id}"):
            text_col, button_col = st.columns([4, 1], vertical_alignment="center", wrap=False)
            fit = fit_badge(lead.fit_score)
            text_col.markdown(f"{fit + ' · ' if fit else ''}**{md(lead.title)}** — "
                              f"{md(lead.company)}  \n{md(describe(lead))}")
            if button_col.button("Restore", key=f"restore_{lead_id}", width="stretch"):
                data.set_lead_status(lead_id, "new")
                done(f"Restored {lead.title} — {lead.company}.")

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
        about_me = st.text_area(
            "About me", value=profile.get("about_me") or "", height=200,
            placeholder="Your experience and skills, as on a resume: years, tools, "
                        "industries, highlights. Pasting your resume summary works.")
        saved = st.form_submit_button("Save", type="primary")
    if saved:
        data.save_job_profile(
            today, target_roles=target_roles, locations=locations,
            work_modes=", ".join(work_modes), min_salary=min_salary, must_haves=must_haves,
            nice_to_haves=nice_to_haves, deal_breakers=deal_breakers, about_me=about_me)
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
