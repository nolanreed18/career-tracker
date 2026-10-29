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
    claude_button,
    claude_ready,
    done,
    empty,
    fit_badge,
    fit_breakdown,
    md,
    on_phone,
    pay_badge,
    prepare_application,
    round_key,
    sections,
    setup,
)

setup("Job Leads", "From your alert emails, scored for fit every morning")


today = data.today()
claude_on = claude_ready()       # Add also has Claude look for the employer's own posting


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
        with move_col:
            add = claude_button("Add", f"move_{lead_id}", active=claude_on, type="primary",
                                width="stretch",
                                help="Save it as an application, read the posting from its link "
                                     "and have Claude find it on the employer's own site to "
                                     "apply there (about 15 cents)")
        if add:
            application_id = data.move_lead_to_applications(lead_id, today)
            with st.spinner("Saved. Reading the posting and looking for it on the employer's "
                            "site (a minute or two; leaving the page doesn't stop it, the "
                            "application will say how it went)…"):
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
    the next batch: a long inbox stays quick to draw on a phone. A computer
    lays the cards out two across."""
    batches = st.session_state.get(f"batches_{key}", 1)
    phone = on_phone()
    for n, lead in enumerate(frame.head(config.LEADS_SHOWN * batches).itertuples()):
        if phone:
            draw(lead)
            continue
        if n % 2 == 0:
            row = st.columns(2, gap="medium")
        with row[n % 2]:
            draw(lead)
    left = len(frame) - config.LEADS_SHOWN * batches
    if left > 0 and st.button(f"Show {min(config.LEADS_SHOWN, left)} more ({left} left)",
                              key=f"more_{key}", width="stretch"):
        st.session_state[f"batches_{key}"] = batches + 1
        st.rerun()


LEAD_COLUMNS = {                     # sized to fit the page's width without scrolling
    "fit": st.column_config.NumberColumn("Fit", format="%.1f", width=52),
    "title": st.column_config.TextColumn("Title", width=310),
    "company": st.column_config.TextColumn("Company", width=150),
    "where": st.column_config.TextColumn("Where", width=145),
    "pay": st.column_config.TextColumn("Pay", width=110,
                                       help="In thousands; ~ means the daily review estimated it"),
    "source": st.column_config.TextColumn("Source", width=76),
    "found": st.column_config.DateColumn("Found", format="MMM D", width=64),
    "posting": st.column_config.LinkColumn("Posting", display_text="Open", width=64),
}


def table_view(leads, view: str) -> None:
    """A computer's inbox: every lead in a full-width, sortable table. Tick
    some and a bar above the table adds or dismisses them together, with
    their cards below it. Each Show view has its own table, so changing it
    clears the ticks."""
    bar = st.container()                     # filled once the table says what's ticked
    picked = st.dataframe(
        logic.lead_table(leads, today), hide_index=True, width="stretch",
        height=min(40 + 35 * len(leads), 680), column_config=LEAD_COLUMNS,
        on_select="rerun", selection_mode="multi-row", key=f"{round_key('leads_table')}_{view}")
    chosen = leads.iloc[[r for r in picked.selection.rows if r < len(leads)]]
    with bar:
        if chosen.empty:
            st.caption("Click a heading to sort. Tick leads to add or dismiss several at once; "
                       "their details show under the table.")
            return
        ids = [int(i) for i in chosen["lead_id"]]
        count = logic.plural(len(ids), "lead")
        too_many = len(ids) > config.BULK_ADD_MAX
        with card("bulk"):
            text_col, add_col, why_col, go_col = st.columns([2, 3, 3, 3],
                                                            vertical_alignment="center")
            text_col.markdown(f"**{count} selected**")
            with add_col:
                add = claude_button(
                    f"Add {count} to Applications", "bulk_add", active=claude_on,
                    type="primary", width="stretch", disabled=too_many,
                    help=(f"Add up to {config.BULK_ADD_MAX} at a time. " if too_many else "")
                    + "Each is saved as an application, its posting read, and Claude looks for "
                      "it on the employer's own site (about 15 cents each)")
            reasons = why_col.multiselect(
                "Dismiss the selected", config.DISMISS_REASONS,
                placeholder="Dismiss them because…", key=f"bulk_dismiss_{round_key('leads')}",
                label_visibility="collapsed",
                help="Pick why, then Dismiss: the daily review reads recent reasons")
            with go_col:
                dismiss = reasons and st.button(f"Dismiss {count}: {', '.join(reasons)}",
                                                key="bulk_dismiss_go", width="stretch")
        if add:
            notes = []
            with st.spinner(f"Saving {count} and looking for each on the employer's site "
                            "(about a minute each; leaving the page doesn't stop it)…"):
                for lead_id in ids:
                    notes += prepare_application(
                        data.move_lead_to_applications(lead_id, today), today)
            bump_round("leads_table")
            bump_round("leads")
            done(" ".join([f"Added {count} to Applications as Saved."] + notes))
        if dismiss:
            for lead_id in ids:
                data.set_lead_status(lead_id, "dismissed", reasons, today)
            bump_round("leads_table")
            bump_round("leads")
            done(f"Dismissed {count} ({', '.join(reasons)}).")
    in_batches(chosen, "chosen", lead_card)           # their cards, two across


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
                "weak": f"Weak (under {config.MAYBE_FIT})", "all": "All"}
        # The radio forgets its choice while another section is open; keep it ourselves.
        # It opens on today's arrivals when there are any, best fit first.
        kept = st.session_state.get("leads_show_kept")
        if kept not in SHOW:                       # also a choice since taken away
            kept = "today" if fresh.any() else "maybe"
            st.session_state.pop("leads_show", None)
        show = st.radio("Show", list(SHOW), horizontal=True, format_func=SHOW.get,
                        index=list(SHOW).index(kept), key="leads_show",
                        label_visibility="collapsed")
        st.session_state["leads_show_kept"] = show
        if show == "today":
            leads = leads[fresh & ~weak]                   # weak ones wait under Weak
            if hidden := int((fresh & weak).sum()):
                st.caption(f"{logic.plural(hidden, 'weak lead')} from today "
                           f"{'is' if hidden == 1 else 'are'} under Weak.")
        elif show == "maybe":
            leads = leads[~weak]
        elif show == "weak":                          # to clear out in one go
            leads = leads[weak]
        if leads.empty:
            empty("filter_alt", "Nothing in this view", "Choose All to see every lead.")
        elif on_phone():
            in_batches(leads, "inbox", lead_card)
        else:
            table_view(leads, show)

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
