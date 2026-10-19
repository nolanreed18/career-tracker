"""The career log -- wins, skills, certifications, feedback -- and job history.

Write wins down when they happen; they're what resumes, reviews and
interview answers are made from.
"""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import config
import data
import logic
from ui import (
    bump_round,
    card,
    delete_button,
    disclosure,
    empty,
    kind_badge,
    md,
    round_key,
    sections,
    setup,
)

setup("Career Log", "Wins, skills and feedback, written down in time")


today = data.today()
KIND_ICONS = {"win": "🏆", "skill": "🛠️", "certification": "📜", "feedback": "💬",
              "learning": "📚"}


def kind_label(kind: str) -> str:
    return f"{KIND_ICONS.get(kind, '')} {kind.capitalize()}".strip()


def done(message: str, counter: str | None = None) -> None:
    if counter:
        st.session_state[counter] = st.session_state.get(counter, 0) + 1
    st.session_state["flash"] = message
    st.rerun()


section = sections("log", ["Log", "Job history"])

# ---- log --------------------------------------------------------------------

if section == "Log":
    n = st.session_state.get("entry_round", 0)
    with st.form(f"add_entry_{n}"):
        st.markdown("**Add to the log**")
        kind_col, date_col = st.columns(2)
        kind = kind_col.selectbox("Type", config.CAREER_KINDS, format_func=kind_label)
        on = date_col.date_input("Date", value=today)
        title = st.text_input("What", placeholder="e.g. Cut report run time from 2h to 10 min")
        details = st.text_area("Details", placeholder="Context, your part, the result — "
                                                      "numbers if you have them")
        tags = st.text_input("Tags", placeholder="e.g. sql, leadership")
        added = st.form_submit_button("Add", type="primary")
    if added:
        if not title.strip():
            st.error("Add a short description in “What”.")
        else:
            data.add_career_entry(kind, title, on, details=details, tags=tags)
            done("Added to your log.", "entry_round")

    entries = data.career_entries()
    if entries.empty:
        empty("emoji_events", "Nothing logged yet", "Start with one win from the last month.")
    else:
        show = st.radio("Show", ["all"] + config.CAREER_KINDS, horizontal=True,
                        format_func=lambda k: "All" if k == "all" else kind_label(k),
                        key="log_show")
        view = entries if show == "all" else entries[entries["kind"] == show]
        if view.empty:
            empty("filter_alt", f"Nothing filed under {show.capitalize()}",
                  "Choose All to see every entry.")
        for entry in view.itertuples():
            entry_id = int(entry.entry_id)
            with card(f"entry-{entry_id}"):
                st.markdown(f"{kind_badge(entry.kind)} **{md(entry.title)}**")
                tags_text = f" · {entry.tags}" if logic.value(entry.tags) else ""
                st.caption(md(f"{entry.happened_on:%b %d, %Y}{tags_text}"))
                if logic.value(entry.details):
                    st.markdown(md(entry.details))
                with st.expander("Edit"):
                    with st.form(f"edit_entry_{entry_id}"):
                        kind_col, date_col = st.columns(2)
                        e_kind = kind_col.selectbox(
                            "Type", config.CAREER_KINDS, format_func=kind_label,
                            index=config.CAREER_KINDS.index(entry.kind))
                        e_on = date_col.date_input("Date", value=entry.happened_on)
                        e_title = st.text_input("What", value=entry.title)
                        e_details = st.text_area("Details",
                                                 value=logic.value(entry.details) or "")
                        e_tags = st.text_input("Tags", value=logic.value(entry.tags) or "")
                        saved = st.form_submit_button("Save", type="primary")
                    if saved:
                        if not e_title.strip():
                            st.error("“What” can't be blank.")
                        else:
                            data.update_career_entry(entry_id, kind=e_kind, happened_on=e_on,
                                                     title=e_title, details=e_details,
                                                     tags=e_tags)
                            done("Saved.")
                    if delete_button("entry", f"entry_{entry_id}"):
                        data.delete_career_entry(entry_id)
                        done("Deleted.")
        st.download_button(
            "Download the log (CSV)",
            entries[["happened_on", "kind", "title", "details", "tags"]].to_csv(index=False),
            file_name=f"career_log_{today:%Y%m%d}.csv", mime="text/csv")

# ---- job history ------------------------------------------------------------

if section == "Job history":
    if disclosure("Add a job", "add_position"):
        n = st.session_state.get("position_round", 0)
        with st.form(f"add_position_{n}"):
            employer = st.text_input("Employer")
            title = st.text_input("Title")
            start_col, end_col = st.columns(2)
            started = start_col.date_input("Started", value=None)
            ended = end_col.date_input("Ended", value=None, help="Leave blank for your current job.")
            base_col, bonus_col = st.columns(2)
            base = base_col.number_input("Base salary ($/yr)", min_value=0, step=1000, value=None)
            bonus = bonus_col.number_input("Bonus ($/yr)", min_value=0, step=1000, value=None)
            other = st.text_input("Other pay", placeholder="Equity, 401k match, sign-on…")
            notes = st.text_area("Notes")
            added = st.form_submit_button("Add job", type="primary")
        if added:
            if not employer.strip() or not title.strip() or started is None:
                st.error("Employer, title and start date are needed.")
            elif ended is not None and ended < started:
                st.error("The end date is before the start date.")
            else:
                data.add_position(employer, title, started, ended_on=ended, base_salary=base,
                                  bonus=bonus, other_comp=other, notes=notes)
                done(f"Added {title.strip()} at {employer.strip()}.", "position_round")

    jobs = data.positions()
    if jobs.empty:
        empty("work", "No jobs yet", "Add your current one, with pay, so raises and offers "
              "have something to be compared against.")
    else:
        st.dataframe(
            logic.for_display(jobs.assign(
                ended_on=jobs["ended_on"].map(lambda d: "now" if logic.blank(d) else f"{d:%b %Y}"),
                started_on=jobs["started_on"].map(lambda d: f"{d:%b %Y}"))[
                ["employer", "title", "started_on", "ended_on", "base_salary", "bonus"]]),
            hide_index=True, width="stretch",
            column_config={
                "employer": "Employer", "title": "Title", "started_on": "From",
                "ended_on": "To",
                "base_salary": st.column_config.NumberColumn("Base", format="$%d"),
                "bonus": st.column_config.NumberColumn("Bonus", format="$%d"),
            })
        labels = {int(r.position_id): f"{r.title} at {r.employer}" for r in jobs.itertuples()}
        picked = st.selectbox("Edit a job", list(labels), format_func=labels.get, index=None,
                              placeholder="Choose one…", key=round_key("pick_position"))
        if picked is not None:
            row = jobs[jobs["position_id"] == picked].iloc[0]
            with st.form(f"edit_position_{picked}"):
                e_employer = st.text_input("Employer", value=row["employer"])
                e_title = st.text_input("Title", value=row["title"])
                start_col, end_col = st.columns(2)
                e_started = start_col.date_input("Started", value=row["started_on"])
                e_ended = end_col.date_input("Ended", value=logic.value(row["ended_on"]))
                base_col, bonus_col = st.columns(2)
                as_int = (lambda v: None if logic.blank(v) else int(v))
                e_base = base_col.number_input("Base salary ($/yr)", min_value=0, step=1000,
                                               value=as_int(row["base_salary"]))
                e_bonus = bonus_col.number_input("Bonus ($/yr)", min_value=0, step=1000,
                                                 value=as_int(row["bonus"]))
                e_other = st.text_input("Other pay", value=logic.value(row["other_comp"]) or "")
                e_notes = st.text_area("Notes", value=logic.value(row["notes"]) or "")
                saved = st.form_submit_button("Save", type="primary")
            if saved:
                if not e_employer.strip() or not e_title.strip() or e_started is None:
                    st.error("Employer, title and start date are needed.")
                elif e_ended is not None and e_ended < e_started:
                    st.error("The end date is before the start date.")
                else:
                    data.update_position(picked, employer=e_employer, title=e_title,
                                         started_on=e_started, ended_on=e_ended,
                                         base_salary=e_base, bonus=e_bonus,
                                         other_comp=e_other, notes=e_notes)
                    done("Saved.")
            if delete_button("job", f"position_{picked}"):
                data.delete_position(picked)
                bump_round("pick_position")
                done("Deleted.")
