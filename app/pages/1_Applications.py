"""Applications: add one, find one, and keep it up to date."""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import config
import data
import logic
from ui import (
    STATUS_HELP,
    bump_round,
    delete_button,
    disclosure,
    empty,
    index_of,
    md,
    optional,
    round_key,
    sections,
    setup,
    status_badge,
    status_label,
)

setup("Applications", "Add one, find one, keep it up to date")


today = data.today()
companies = data.companies()
company_names = companies["name"].tolist()
FORMATS = ["phone", "video", "onsite", "take-home"]


def next_round(name: str) -> None:
    """Forms are keyed by a counter; bumping it gives a fresh, empty form."""
    st.session_state[name] = st.session_state.get(name, 0) + 1


def done(message: str, form_counter: str | None = None) -> None:
    if form_counter:
        next_round(form_counter)
    st.session_state["flash"] = message
    st.rerun()


# ---- add --------------------------------------------------------------------

add_round = st.session_state.get("add_round", 0)
if disclosure("Add an application", "add_application"):
    with st.form(f"add_application_{add_round}"):
        company = st.selectbox("Company", optional(company_names),
                               help="Pick one you've used before, or type a new one below.")
        new_company = st.text_input("…or a new company")
        role = st.text_input("Role")
        status_col, date_col = st.columns(2)
        status = status_col.selectbox("Status", config.STATUSES, index=1,
                                      format_func=status_label, help=STATUS_HELP)
        applied_on = date_col.date_input("Applied on", value=today,
                                         help="Ignored while the status is Saved.")
        job_url = st.text_input("Job posting link")
        location_col, mode_col = st.columns(2)
        location = location_col.text_input("Location")
        work_mode = mode_col.selectbox("Work mode", optional(config.WORK_MODES))
        source = st.text_input("Source", placeholder="LinkedIn, referral, company site…")
        low_col, high_col = st.columns(2)
        salary_min = low_col.number_input("Salary from ($/yr)", min_value=0, step=5000, value=None)
        salary_max = high_col.number_input("Salary to ($/yr)", min_value=0, step=5000, value=None)
        step_col, step_date_col = st.columns(2)
        next_action = step_col.text_input("Next step", placeholder="e.g. Email the recruiter")
        next_action_on = step_date_col.date_input("Next step due", value=None)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add application", type="primary")
    if submitted:
        name = new_company.strip() or company
        if not name:
            st.error("Pick a company or type a new one.")
        elif not role.strip():
            st.error("Add the role.")
        elif salary_min is not None and salary_max is not None and salary_max < salary_min:
            st.error("“Salary to” is below “Salary from”.")
        else:
            new_id = data.add_application(
                data.company_id_for(name, today), role, status, today,
                applied_on=None if status == "saved" else applied_on,
                job_url=job_url, location=location, work_mode=work_mode or None,
                source=source, salary_min=salary_min, salary_max=salary_max,
                next_action=next_action, next_action_on=next_action_on, notes=notes)
            st.session_state["open_add_application"] = False
            st.session_state[round_key("pick_application")] = new_id
            done(f"Added {role.strip()} at {name}.", "add_round")

# ---- find -------------------------------------------------------------------

apps = data.applications()
if apps.empty:
    empty("inbox", "No applications yet", "Add one above, or bring in a spreadsheet on Import.")
    st.stop()

st.subheader("Your applications")
show_col, search_col = st.columns(2)
show = show_col.radio("Show", ["Open", "Closed", "All"], horizontal=True, key="apps_show")
search = search_col.text_input("Search", placeholder="Company or role", key="apps_search")

view = apps
if show == "Open":
    view = view[view["status"].isin(config.OPEN_STATUSES)]
elif show == "Closed":
    view = view[~view["status"].isin(config.OPEN_STATUSES)]
if search.strip():
    term = search.strip()
    view = view[view["company"].str.contains(term, case=False, regex=False)
                | view["role"].str.contains(term, case=False, regex=False)]

if view.empty:
    if show == "All":
        hint = "Clear the search to see every application."
    else:
        hint = "Try All" + (", or clear the search." if search.strip() else ".")
    empty("filter_alt", "Nothing matches", hint)
else:
    st.dataframe(
        logic.for_display(view.assign(status=view["status"].map(status_label))[
            ["company", "role", "status", "applied_on", "next_action_on", "last_update_on"]],
            dates=("applied_on", "next_action_on", "last_update_on")),
        hide_index=True, width="stretch",
        column_config={
            "company": "Company", "status": "Status",
            "role": st.column_config.TextColumn("Role", width="large"),
            "applied_on": st.column_config.DateColumn("Applied", format="MMM D"),
            "next_action_on": st.column_config.DateColumn("Next step", format="MMM D"),
            "last_update_on": st.column_config.DateColumn("Updated", format="MMM D"),
        })

labels = {int(r.application_id): f"{r.company} — {r.role}" for r in apps.itertuples()}
options = [int(i) for i in view["application_id"]]
pick_key = round_key("pick_application")
if (requested := st.session_state.pop("open_application", None)) is not None:
    st.session_state[pick_key] = requested
picked_now = st.session_state.get(pick_key)
if picked_now is not None and picked_now not in options:
    if picked_now in labels:
        options = [picked_now] + options        # opened from elsewhere; keep it on the list
    else:                                       # gone (deleted elsewhere): a fresh dropdown
        bump_round("pick_application")
        pick_key, picked_now = round_key("pick_application"), None
picked = st.selectbox(
    "Open an application", options, format_func=lambda i: labels.get(i, str(i)),
    placeholder="Choose one…", key=pick_key,
    **({} if pick_key in st.session_state else {"index": None}))

if picked is None:
    st.stop()
app = data.application(picked)
if app is None:
    st.warning("That application no longer exists.")
    st.stop()

# ---- one application --------------------------------------------------------

st.divider()
st.markdown(f"### {md(app['company'])} — {md(app['role'])}")
facts = []
if app["applied_on"]:
    facts.append(f"applied {logic.when(app['applied_on'], today)}")
if salary := logic.salary_range(app["salary_min"], app["salary_max"]):
    facts.append(salary)
facts += [x for x in (app["location"], app["work_mode"], app["source"]) if x]
st.markdown(f"{status_badge(app['status'])} {md(' · '.join(facts))}")
if app["next_action"] or app["next_action_on"]:
    due = f" — due {logic.when(app['next_action_on'], today)}" if app["next_action_on"] else ""
    st.markdown(f"**Next step:** {md(app['next_action'] or 'Next step')}{md(due)}")
if app["job_url"]:
    st.link_button("Open job posting", app["job_url"])
if app["notes"]:
    st.caption(md(app["notes"]))

section = sections("application", ["Log update", "Interviews", "Edit", "History"])

if section == "Log update":
    update_round = st.session_state.get("update_round", 0)
    with st.form(f"update_{picked}_{update_round}"):
        status_col, on_col = st.columns(2)
        new_status = status_col.selectbox(
            "Status", config.STATUSES, index=index_of(config.STATUSES, app["status"]),
            format_func=status_label, help=STATUS_HELP)
        on = on_col.date_input("On", value=today)
        note = st.text_input("What happened?", placeholder="e.g. Emailed the recruiter")
        step_col, step_date_col = st.columns(2)
        step = step_col.text_input("Next step", value=app["next_action"] or "")
        step_on = step_date_col.date_input("Next step due", value=app["next_action_on"])
        clear_step = st.checkbox("The next step is done: clear it")
        logged = st.form_submit_button("Log update", type="primary")
    st.caption("Any update, even with the status unchanged, resets the "
               f"{config.FOLLOW_UP_DAYS}-day follow-up reminder.")
    if logged:
        data.set_status(picked, new_status, on, note)
        data.update_application(picked, next_action=None if clear_step else step,
                                next_action_on=None if clear_step else step_on)
        done("Update logged.", "update_round")

if section == "Interviews":
    for iv in data.interviews(picked).itertuples():
        at = f" at {logic.clock(iv.start_time)}" if not logic.blank(iv.start_time) else ""
        st.markdown(f"**{md(logic.value(iv.round) or 'Interview')}** — "
                    f"{logic.when(iv.scheduled_on, today)}{at}")
        extra = [x for x in (logic.value(iv.format), logic.value(iv.interviewers)) if x]
        if extra:
            st.caption(md(" · ".join(extra)))
    st.caption("Add notes and how it went on the Interviews page.")
    interview_round = st.session_state.get("interview_round", 0)
    with st.form(f"add_interview_{picked}_{interview_round}"):
        st.markdown("**Add an interview**")
        day_col, time_col = st.columns(2)
        iv_on = day_col.date_input("Date", value=today)
        iv_at = time_col.time_input("Time", value=None, step=900)
        iv_round = st.text_input("Round", placeholder="Recruiter screen, Technical, Onsite…")
        format_col, who_col = st.columns(2)
        iv_format = format_col.selectbox("Format", optional(FORMATS))
        iv_who = who_col.text_input("Interviewers")
        iv_prep = st.text_area("Prep notes")
        added = st.form_submit_button("Add interview", type="primary")
    if added:
        data.add_interview(picked, iv_on, start_time=iv_at, round=iv_round,
                           format=iv_format or None, interviewers=iv_who, prep_notes=iv_prep)
        done("Interview added.", "interview_round")

if section == "Edit":
    edit_round = st.session_state.get("edit_round", 0)
    with st.form(f"edit_{picked}_{edit_round}"):
        e_company = st.selectbox("Company", company_names,
                                 index=index_of(company_names, app["company"]))
        e_role = st.text_input("Role", value=app["role"])
        e_applied = st.date_input("Applied on", value=app["applied_on"])
        e_url = st.text_input("Job posting link", value=app["job_url"] or "")
        location_col, mode_col = st.columns(2)
        e_location = location_col.text_input("Location", value=app["location"] or "")
        modes = optional(config.WORK_MODES)
        e_mode = mode_col.selectbox("Work mode", modes, index=index_of(modes, app["work_mode"]))
        e_source = st.text_input("Source", value=app["source"] or "")
        low_col, high_col = st.columns(2)
        e_low = low_col.number_input("Salary from ($/yr)", min_value=0, step=5000,
                                     value=app["salary_min"])
        e_high = high_col.number_input("Salary to ($/yr)", min_value=0, step=5000,
                                       value=app["salary_max"])
        e_notes = st.text_area("Notes", value=app["notes"] or "")
        saved = st.form_submit_button("Save changes", type="primary")
    if saved:
        if not e_role.strip():
            st.error("The role can't be blank.")
        elif e_low is not None and e_high is not None and e_high < e_low:
            st.error("“Salary to” is below “Salary from”.")
        else:
            company_id = int(companies.loc[companies["name"] == e_company, "company_id"].iloc[0])
            data.update_application(
                picked, company_id=company_id, role=e_role, applied_on=e_applied,
                job_url=e_url, location=e_location, work_mode=e_mode or None, source=e_source,
                salary_min=e_low, salary_max=e_high, notes=e_notes)
            done("Saved.", "edit_round")

    st.divider()
    if delete_button("application", f"application_{picked}"):
        data.delete_application(picked)
        bump_round("pick_application")
        done(f"Deleted {app['role']} at {app['company']}.")

if section == "History":
    history = data.events(picked)
    st.dataframe(
        logic.for_display(history.assign(status=history["status"].map(status_label))[
            ["happened_on", "status", "note"]], dates=("happened_on",)),
        hide_index=True, width="stretch",
        column_config={"happened_on": st.column_config.DateColumn("Date", format="MMM D, YYYY"),
                       "status": "Status", "note": "Note"})
