"""Home: where the search stands and what needs doing next."""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

from datetime import timedelta

import config
import data
import logic
from ui import (
    attention_badge,
    badge,
    card,
    empty,
    fit_badge,
    md,
    on_phone,
    pay_badge,
    setup,
    status_badge,
)

today = data.today()
setup("Career Tracker", f"{today:%A, %B %-d}")
apps = data.applications()
interviews = data.interviews()

stats = data.lead_stats()
tiles = st.columns(2 + len(config.HOME_FIT_MARKS), gap="xsmall", wrap=False)
tiles[0].metric("Reviewed", stats["reviewed"], border=True)
tiles[1].metric("Avg fit", "—" if stats["average_fit"] is None
                else logic.fit_text(round(stats["average_fit"], 1)), border=True)
for tile, mark, waiting in zip(tiles[2:], config.HOME_FIT_MARKS, stats["waiting"]):
    tile.metric(f"{mark:g}+ waiting", waiting, border=True)
st.caption("Reviewed: postings the daily review has scored, and their average fit. Waiting: "
           "leads at that score or better still in the inbox, not yet added or dismissed.")

new_leads, _ = logic.split_stale(data.job_leads("new"), today)


def leads_panel(top: int = 0) -> None:
    """The inbox in a line, with a button to it; on a computer also the
    best few leads waiting."""
    if new_leads.empty:
        return
    strong = int((new_leads["fit_score"].fillna(0) >= config.STRONG_FIT).sum())
    found_today = int((new_leads["found_on"] == today).sum())
    with card("leads"):
        text_col, button_col = st.columns([4, 1], vertical_alignment="center", wrap=False)
        text_col.markdown(f"{badge('blue', 'Leads')} "
                          f"{logic.plural(len(new_leads), 'lead')} in the inbox"
                          + (f", {found_today} new today" if found_today else "")
                          + (f", {strong} strong" if strong else ""))
        if button_col.button("Review", key="review_leads", width="stretch"):
            st.switch_page("pages/1_Job_Leads.py")
        if top:
            best = new_leads.sort_values("fit_score", ascending=False, na_position="last")
            for lead in best.head(top).itertuples():
                fit = fit_badge(lead.fit_score)
                st.markdown(f"{fit + ' ' if fit else ''}{md(lead.title)} — {md(lead.company)}"
                            f" · {pay_badge(lead.salary_min, lead.salary_max, lead.pay_source)}")


def attention_panel() -> None:
    st.subheader("Needs attention")
    items = logic.needs_attention(apps, interviews, today)
    if apps.empty:
        empty("inbox", "No applications yet", "Add your first one to get started.")
    elif not items:
        empty("task_alt", "Nothing needs attention",
              "Overdue steps, follow-ups and upcoming interviews show up here.")
    for n, item in enumerate(items):
        with card(f"attention-{n}"):
            text_col, button_col = st.columns([4, 1], vertical_alignment="center", wrap=False)
            text_col.markdown(f"{attention_badge(item.kind)} **{md(item.headline)}**  \n"
                              f"{md(item.detail)}")
            if button_col.button("Open", key=f"attention_{n}", width="stretch"):
                st.session_state["open_application"] = item.application_id
                st.switch_page("pages/2_Applications.py")

    st.caption(f"Applications with no update for {config.FOLLOW_UP_DAYS} days are flagged for "
               "a follow-up. Logging any update, or setting a next step, clears the flag.")
    if st.button("Add application", type="primary", width="stretch"):
        st.session_state["open_add_application"] = True
        st.switch_page("pages/2_Applications.py")


def overview_panel() -> None:
    """A computer's side panel: where the open applications stand and how
    this week compares."""
    st.subheader("Pipeline")
    open_apps = apps[apps["status"].isin(config.OPEN_STATUSES)] if not apps.empty else apps
    counts = logic.pipeline(open_apps)
    counts = counts[counts["applications"] > 0]
    if counts.empty:
        st.caption("No open applications.")
    else:
        st.markdown("  ".join(f"{status_badge(r.status)} **{r.applications}**"
                              for r in counts.itertuples()))
    weeks = logic.weekly_applications(apps, today, weeks=2)
    this_week, last_week = int(weeks["applications"].iloc[-1]), int(weeks["applications"].iloc[0])
    soon = 0 if interviews.empty else int(
        ((interviews["scheduled_on"] >= today)
         & (interviews["scheduled_on"] <= today + timedelta(days=14))).sum())
    week_col, soon_col = st.columns(2, gap="small")
    week_col.metric("Applied this week", this_week, delta=this_week - last_week,
                    border=True, help="Against last week")
    soon_col.metric("Interviews, 2 weeks", soon, border=True)


if on_phone():                            # one column: the inbox, then what needs doing
    leads_panel()
    attention_panel()
else:                                     # a computer: what needs doing beside the overview
    main_col, side_col = st.columns([3, 2], gap="large")
    with main_col:
        attention_panel()
    with side_col:
        leads_panel(top=config.HOME_TOP_LEADS)
        overview_panel()
