"""How the search is going, in numbers."""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import config
import data
import logic
from ui import empty, setup

setup("Stats", "How the search is going, in numbers")

today = data.today()
apps = data.applications()
events = data.all_events()

if apps.empty:
    empty("bar_chart", "No stats yet", "They appear once you've added some applications.")
    st.stop()

responded, sent = logic.response_rate(apps, events)
open_count = int(apps["status"].isin(config.OPEN_STATUSES).sum())
offers = int(apps["status"].isin(["offer", "accepted"]).sum())
sent_col, rate_col, offer_col = st.columns(3, gap="xsmall", wrap=False)
sent_col.metric("Applied", sent, border=True)
rate_col.metric("Response rate", f"{responded / sent:.0%}" if sent else "—", border=True)
offer_col.metric("Offers", offers, border=True)
st.caption(f"Applied counts everything past Saved; {responded} of {sent} reached a screen or "
           "further.")

st.subheader("Pipeline")
pipe = logic.pipeline(apps)
pipe["status"] = pipe["status"].map(str.capitalize)
st.bar_chart(pipe, x="status", y="applications", x_label="", y_label="Applications",
             sort=False, horizontal=True, height=320)
st.caption(f"{open_count} open.")

st.subheader("Applications per week")
weekly = logic.weekly_applications(apps, today)
weekly["week"] = weekly["week"].map(lambda d: f"{d:%b} {d.day}")
st.bar_chart(weekly, x="week", y="applications", x_label="Week of", y_label="", sort=False)

st.subheader("What's working")
sources = logic.by_source(apps, events)
if sources.empty:
    st.caption("Nothing applied for yet.")
else:
    st.dataframe(sources, hide_index=True, width="stretch", column_config={
        "source": "Source", "applied": "Applied", "responded": "Responses",
        "rate": st.column_config.ProgressColumn("Response rate", format="percent",
                                                min_value=0, max_value=1),
    })
    st.caption("Response = reached a screen or further. Set each application's "
               "source to see which channels pay off.")
