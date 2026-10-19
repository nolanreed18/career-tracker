"""Interviews: what's coming up, how past ones went."""

import streamlit as st

import config
import data
import logic
from ui import empty, md, optional, setup

setup("Interviews", "What's coming up, and how past ones went")

if message := st.session_state.pop("flash", None):
    st.success(message)

today = data.today()
FORMATS = ["phone", "video", "onsite", "take-home"]
RATINGS = ["", "1 — rough", "2", "3 — okay", "4", "5 — great"]


def rating_index(rating) -> int:
    return 0 if logic.blank(rating) else int(rating)


def done(message: str) -> None:
    st.session_state["flash"] = message
    st.rerun()


apps = data.applications()
open_apps = apps[apps["status"].isin(config.OPEN_STATUSES)] if not apps.empty else apps
with st.expander("Add an interview", icon=":material/add:"):
    if open_apps.empty:
        st.caption("Add an application first; interviews belong to one.")
    else:
        labels = {int(r.application_id): f"{r.company} — {r.role}"
                  for r in open_apps.itertuples()}
        n = st.session_state.get("iv_add_round", 0)
        with st.form(f"add_interview_{n}"):
            application_id = st.selectbox("Application", list(labels),
                                          format_func=labels.get)
            day_col, time_col = st.columns(2)
            on = day_col.date_input("Date", value=today)
            at = time_col.time_input("Time", value=None, step=900)
            round_ = st.text_input("Round", placeholder="Recruiter screen, Technical, Onsite…")
            format_col, who_col = st.columns(2)
            format_ = format_col.selectbox("Format", optional(FORMATS))
            who = who_col.text_input("Interviewers")
            prep = st.text_area("Prep notes")
            added = st.form_submit_button("Add interview", type="primary")
        if added:
            data.add_interview(application_id, on, start_time=at, round=round_,
                               format=format_ or None, interviewers=who, prep_notes=prep)
            st.session_state["iv_add_round"] = n + 1
            done("Interview added.")

interviews = data.interviews()
if interviews.empty:
    empty("event", "No interviews yet", "Add one above, or from an application's Interviews tab.")
    st.stop()

upcoming = interviews[interviews["scheduled_on"] >= today]
past = interviews[interviews["scheduled_on"] < today].iloc[::-1]   # most recent first

for heading, frame in (("Upcoming", upcoming), ("Past", past)):
    st.subheader(heading)
    if frame.empty:
        st.caption("None.")
    for iv in frame.itertuples():
        iv_id = int(iv.interview_id)
        at = f" at {logic.clock(iv.start_time)}" if not logic.blank(iv.start_time) else ""
        title = (f"{iv.company} — {iv.role} · {logic.value(iv.round) or 'Interview'} · "
                 f"{logic.when(iv.scheduled_on, today)}{at}")
        with st.expander(title, icon=":material/event:" if heading == "Upcoming"
                         else ":material/history:"):
            with st.form(f"interview_{iv_id}"):
                day_col, time_col = st.columns(2)
                e_on = day_col.date_input("Date", value=iv.scheduled_on)
                e_at = time_col.time_input("Time", value=logic.value(iv.start_time), step=900)
                e_round = st.text_input("Round", value=logic.value(iv.round) or "")
                formats = optional(FORMATS)
                format_col, who_col = st.columns(2)
                e_format = format_col.selectbox(
                    "Format", formats,
                    index=formats.index(iv.format) if iv.format in formats else 0)
                e_who = who_col.text_input("Interviewers", value=logic.value(iv.interviewers) or "")
                e_prep = st.text_area("Prep notes", value=logic.value(iv.prep_notes) or "")
                e_outcome = st.text_area("How it went", value=logic.value(iv.outcome_notes) or "",
                                         placeholder="Questions asked, what went well, "
                                                     "what to work on")
                e_rating = st.selectbox("Rating", RATINGS, index=rating_index(iv.rating))
                saved = st.form_submit_button("Save", type="primary")
            if saved:
                data.update_interview(
                    iv_id, scheduled_on=e_on, start_time=e_at, round=e_round,
                    format=e_format or None, interviewers=e_who, prep_notes=e_prep,
                    outcome_notes=e_outcome,
                    rating=RATINGS.index(e_rating) or None)
                done("Interview saved.")
            if st.button("Delete interview", key=f"delete_interview_{iv_id}"):
                data.delete_interview(iv_id)
                done("Interview deleted.")

st.caption(md(f"Interviews in the next {config.INTERVIEW_LOOKAHEAD_DAYS} days also show on Home."))
