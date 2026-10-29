"""Applications: add one, find one, and keep it up to date."""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import config
import data
import logic
from ui import (
    STATUS_HELP,
    apply_status,
    badge,
    bump_round,
    delete_button,
    disclosure,
    done,
    empty,
    find_posting_button,
    index_of,
    md,
    on_phone,
    optional,
    posting_button,
    round_key,
    sections,
    setup,
    status_badge,
    status_label,
)

setup("Applications", "Add one, find one, keep it up to date")

RATINGS = ["", "1 — rough", "2", "3 — okay", "4", "5 — great"]


def rating_index(rating) -> int:
    return 0 if logic.blank(rating) else int(rating)


today = data.today()
companies = data.companies()
# Ones still in use: a company whose applications were all deleted drops out.
company_names = companies.loc[companies["applications"] > 0, "name"].tolist()


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
    empty("inbox", "No applications yet", "Add one above, or add a lead from Job Leads.")
    st.stop()

phone = on_phone()
# A computer shows the list beside the open application; a phone, one under the other.
list_area, detail_area = ((st.container(), st.container()) if phone
                          else st.columns([7, 6], gap="large"))

with list_area:
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
    elif not phone:                                 # a phone picks from the list below instead
        st.caption("Click a row to open it.")
        table = st.dataframe(                   # beside the open one: who, what, where it stands
            view.assign(status=view["status"].map(status_label), resume=view["tailored"] > 0)[
                ["company", "role", "status", "resume"]],
            hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
            key=round_key("apps_table"),
            column_config={
                "company": st.column_config.TextColumn("Company", width=105),
                "role": st.column_config.TextColumn("Role", width=210),
                "status": st.column_config.TextColumn("Status", width=105),
                "resume": st.column_config.CheckboxColumn("Resume", width=60, disabled=True,
                                                          help="A tailored resume exists"),
            })
        if table.selection.rows and table.selection.rows[0] < len(view):   # a click opens it
            st.session_state["open_application"] = int(
                view.iloc[table.selection.rows[0]]["application_id"])
            bump_round("apps_table")

    labels = logic.application_labels(apps)
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

with detail_area:
    if picked is None:
        if not phone:
            empty("ads_click", "Pick an application", "Click a row on the left, or choose one "
                  "from the list.")
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
    facts += (logic.place(app["location"], app["work_mode"])
              + ([app["source"]] if app["source"] else []))
    st.markdown(f"{status_badge(app['status'])} {md(' · '.join(facts))}")
    if app["tailored"]:
        st.markdown(f"{badge('green', 'Resume ready')} "
                    f"{logic.plural(int(app['tailored']), 'tailored version')} with cover letter, "
                    "on Resume Builder")
    if app["next_action"] or app["next_action_on"]:
        due = (f" — due {logic.when(app['next_action_on'], today)}"
               if app["next_action_on"] else "")
        st.markdown(f"**Next step:** {md(app['next_action'] or 'Next step')}{md(due)}")
    if app["apply_url"]:
        apply_col, open_col = st.columns(2)
        apply_col.link_button(f"Apply on {app['company']}'s site", app["apply_url"], type="primary",
                              width="stretch")
        if app["job_url"]:
            open_col.link_button("Open the posting", app["job_url"], width="stretch")
    elif app["job_url"]:
        st.link_button("Open job posting", app["job_url"])
    apply_status(app)
    if app["apply_state"] == "looking":
        @st.fragment(run_every=5)
        def still_looking() -> None:    # a search started elsewhere: redraw when it ends
            if data.application(picked)["apply_state"] != "looking":
                st.rerun()
        still_looking()
    if app["notes"]:
        st.caption(md(app["notes"]))
    resume_col, applied_col = st.columns(2)
    if resume_col.button("Resume Builder", icon=":material/auto_awesome:", width="stretch",
                         type="secondary" if app["tailored"] else "primary",
                         help="Tailor the resume and cover letter to this job"):
        st.session_state["tailor_application"] = picked
        st.session_state["resume_goto"] = "Resume Builder"
        st.switch_page("pages/3_Resume_and_Projects.py")
    if app["status"] == "saved" and applied_col.button(
            "Applied today", icon=":material/send:", width="stretch",
            help="Marks it Applied as of today and starts the follow-up clock"):
        data.set_status(picked, "applied", today,
                        "Applied on the employer's site" if app["apply_url"] else "Applied")
        done("Marked as applied today.")
    find_posting_button(app, "application")      # its own row: the label is long

    section = sections("application", ["Log update", "Interviews", "Posting", "Edit", "History"])

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
            iv_id = int(iv.interview_id)
            at = f" at {logic.clock(iv.start_time)}" if not logic.blank(iv.start_time) else ""
            with st.expander(f"{logic.value(iv.round) or 'Interview'} · "
                             f"{logic.when(iv.scheduled_on, today)}{at}",
                             icon=":material/event:" if iv.scheduled_on >= today
                             else ":material/history:"):
                with st.form(f"interview_{iv_id}"):
                    day_col, time_col = st.columns(2)
                    e_on = day_col.date_input("Date", value=iv.scheduled_on)
                    e_at = time_col.time_input("Time", value=logic.value(iv.start_time),
                                               step=900)
                    e_round = st.text_input("Round", value=logic.value(iv.round) or "")
                    formats = optional(config.INTERVIEW_FORMATS)
                    format_col, who_col = st.columns(2)
                    e_format = format_col.selectbox(
                        "Format", formats,
                        index=formats.index(iv.format) if iv.format in formats else 0)
                    e_who = who_col.text_input("Interviewers",
                                               value=logic.value(iv.interviewers) or "")
                    e_prep = st.text_area("Prep notes", value=logic.value(iv.prep_notes) or "")
                    e_outcome = st.text_area(
                        "How it went", value=logic.value(iv.outcome_notes) or "",
                        placeholder="Questions asked, what went well, what to work on")
                    e_rating = st.selectbox("Rating", RATINGS, index=rating_index(iv.rating))
                    saved = st.form_submit_button("Save", type="primary")
                if saved:
                    data.update_interview(
                        iv_id, scheduled_on=e_on, start_time=e_at, round=e_round,
                        format=e_format or None, interviewers=e_who, prep_notes=e_prep,
                        outcome_notes=e_outcome, rating=RATINGS.index(e_rating) or None)
                    done("Interview saved.")
                if delete_button("interview", f"interview_{iv_id}"):
                    data.delete_interview(iv_id)
                    done("Interview deleted.")
        if disclosure("Add an interview", f"add_interview_{picked}"):
            interview_round = st.session_state.get("interview_round", 0)
            with st.form(f"add_interview_{picked}_{interview_round}"):
                day_col, time_col = st.columns(2)
                iv_on = day_col.date_input("Date", value=today)
                iv_at = time_col.time_input("Time", value=None, step=900)
                iv_round = st.text_input("Round",
                                         placeholder="Recruiter screen, Technical, Onsite…")
                format_col, who_col = st.columns(2)
                iv_format = format_col.selectbox("Format", optional(config.INTERVIEW_FORMATS))
                iv_who = who_col.text_input("Interviewers")
                iv_prep = st.text_area("Prep notes")
                added = st.form_submit_button("Add interview", type="primary")
            if added:
                data.add_interview(picked, iv_on, start_time=iv_at, round=iv_round,
                                   format=iv_format or None, interviewers=iv_who,
                                   prep_notes=iv_prep)
                done("Interview added.", "interview_round")

    if section == "Posting":
        posting_button(app, "application")
        with st.form(f"posting_{picked}"):
            posting = st.text_area("Job posting", value=app["posting"] or "", height=260,
                                   help="Read it from the link above, or paste the whole posting: "
                                        "Claude tailors the resume to its words.")
            saved_posting = st.form_submit_button("Save posting", type="primary")
        if saved_posting:
            data.update_application(picked, posting=posting)
            done("Posting saved.")
        versions = data.tailored_versions(picked)
        if not versions.empty:
            st.caption(f"{logic.plural(len(versions), 'tailored version')} on Resume and Projects, "
                       f"the latest {logic.when(versions['created_on'].iloc[0], today)}.")
        if st.button("Tailor the resume for this job", icon=":material/auto_awesome:",
                     disabled=not app["posting"]):
            st.session_state["tailor_application"] = picked
            st.session_state["resume_goto"] = "Resume Builder"
            st.switch_page("pages/3_Resume_and_Projects.py")
        if not app["posting"]:
            st.caption("Get or save the posting first: tailoring reads it.")

    if section == "Edit":
        edit_round = st.session_state.get("edit_round", 0)
        with st.form(f"edit_{picked}_{edit_round}"):
            e_company = st.selectbox("Company", company_names,
                                     index=index_of(company_names, app["company"]))
            e_role = st.text_input("Role", value=app["role"])
            e_applied = st.date_input("Applied on", value=app["applied_on"])
            e_url = st.text_input("Job posting link", value=app["job_url"] or "")
            e_apply = st.text_input("Employer's apply link", value=app["apply_url"] or "",
                                    help="The same posting on the employer's own careers site, "
                                         "when you found it yourself")
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
                company_id = int(
                    companies.loc[companies["name"] == e_company, "company_id"].iloc[0])
                pasted = {}
                if (e_apply.strip() or None) != app["apply_url"]:         # the link changed by hand
                    pasted = {"apply_url": e_apply,
                              "apply_state": "found" if e_apply.strip() else None,
                              "apply_note": "Link pasted by you." if e_apply.strip() else None}
                data.update_application(
                    picked, company_id=company_id, role=e_role, applied_on=e_applied,
                    job_url=e_url, location=e_location, work_mode=e_mode or None, source=e_source,
                    salary_min=e_low, salary_max=e_high, notes=e_notes, **pasted)
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
