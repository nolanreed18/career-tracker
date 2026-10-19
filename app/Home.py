"""Home: where the search stands and what needs doing next."""

from datetime import timedelta

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
events = data.all_events()

open_apps = apps[apps["status"].isin(config.OPEN_STATUSES)] if not apps.empty else apps
week_ago = today - timedelta(days=6)
applied_this_week = (int(apps["applied_on"].map(lambda d: not logic.blank(d) and d >= week_ago)
                         .sum()) if not apps.empty else 0)
responded, sent = logic.response_rate(apps, events)

open_col, week_col, rate_col = st.columns(3, gap="xsmall", wrap=False)
open_col.metric("Open", len(open_apps), border=True)
week_col.metric("This week", applied_this_week, border=True)
rate_col.metric("Response rate", f"{responded / sent:.0%}" if sent else "—", border=True)

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
            st.switch_page("pages/1_Applications.py")

new_leads, _ = logic.split_stale(data.job_leads("new"), today)
if not new_leads.empty:
    strong = int((new_leads["fit_score"].fillna(0) >= config.STRONG_FIT).sum())
    with card("leads"):
        text_col, button_col = st.columns([4, 1], vertical_alignment="center", wrap=False)
        text_col.markdown(f"{badge('blue', 'Leads')} "
                          f"{logic.plural(len(new_leads), 'new job lead')} to review"
                          + (f", {strong} strong" if strong else ""))
        if button_col.button("Review", key="review_leads", width="stretch"):
            st.switch_page("pages/7_Job_Leads.py")

st.caption(f"Applications with no update for {config.FOLLOW_UP_DAYS} days are flagged for a "
           "follow-up. Logging any update, or setting a next step, clears the flag.")

add_col, win_col = st.columns(2)
if add_col.button("Add application", type="primary", width="stretch"):
    st.session_state["open_add_application"] = True
    st.switch_page("pages/1_Applications.py")
if win_col.button("Log a win", width="stretch"):
    st.switch_page("pages/4_Career_Log.py")
