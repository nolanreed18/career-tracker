"""Home: where the search stands and what needs doing next."""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import config
import data
import logic
from ui import attention_badge, badge, card, empty, md, setup

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
if not new_leads.empty:
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

st.caption(f"Applications with no update for {config.FOLLOW_UP_DAYS} days are flagged for a "
           "follow-up. Logging any update, or setting a next step, clears the flag.")

if st.button("Add application", type="primary", width="stretch"):
    st.session_state["open_add_application"] = True
    st.switch_page("pages/2_Applications.py")
