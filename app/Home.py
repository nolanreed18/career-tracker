"""Home: where the search stands and what needs doing next."""

from datetime import timedelta

import streamlit as st

import config
import data
import logic
from ui import ATTENTION_ICONS, md, setup

setup("Career Tracker")
st.title("Career Tracker")

today = data.today()
apps = data.applications()
interviews = data.interviews()
events = data.all_events()

open_apps = apps[apps["status"].isin(config.OPEN_STATUSES)] if not apps.empty else apps
week_ago = today - timedelta(days=6)
applied_this_week = (int(apps["applied_on"].map(lambda d: not logic.blank(d) and d >= week_ago)
                         .sum()) if not apps.empty else 0)
responded, sent = logic.response_rate(apps, events)

open_col, week_col, rate_col = st.columns(3, gap="xsmall", wrap=False)
open_col.metric("Open", len(open_apps), help="Applications not yet accepted, rejected or withdrawn.")
week_col.metric("This week", applied_this_week, help="Applications sent in the last 7 days.")
rate_col.metric("Response rate", f"{responded / sent:.0%}" if sent else "—",
                help=f"{responded} of {sent} applications sent reached a screen or further.")

st.subheader("Needs attention")
items = logic.needs_attention(apps, interviews, today)
if apps.empty:
    st.info("No applications yet. Add your first one to get started.")
elif not items:
    st.success("Nothing needs attention right now.")
for n, item in enumerate(items):
    with st.container(border=True):
        text_col, button_col = st.columns([4, 1], vertical_alignment="center", wrap=False)
        text_col.markdown(f"{ATTENTION_ICONS[item.kind]} **{md(item.headline)}**  \n"
                          f"{md(item.detail)}")
        if button_col.button("Open", key=f"attention_{n}"):
            st.session_state["open_application"] = item.application_id
            st.switch_page("pages/1_Applications.py")

st.caption(f"Applications with no update for {config.FOLLOW_UP_DAYS} days are flagged for a "
           "follow-up. Logging any update, or setting a next step, clears the flag.")

add_col, win_col = st.columns(2)
if add_col.button("Add application", type="primary", width="stretch"):
    st.session_state["add_application_open"] = True
    st.switch_page("pages/1_Applications.py")
if win_col.button("Log a win", width="stretch"):
    st.switch_page("pages/4_Career_Log.py")
