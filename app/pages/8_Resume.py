"""Resume: the master resume as data, built from your own files with
Claude's help, edited here, and exported back to Word in your own layout."""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import io

import pandas as pd

import ai
import config
import data
import docx_io
import logic
from ui import (
    badge,
    bump_round,
    card,
    claude_button,
    claude_submit,
    delete_button,
    disclosure,
    done,
    empty,
    md,
    on_phone,
    posting_button,
    round_key,
    sections,
    setup,
)

setup("Resume", "Your master resume as data: built from your files, tailored per job")

today = data.today()


if goto := st.session_state.pop("resume_goto", None):   # an action that moves the eye
    st.session_state["section_resume"] = goto
section = sections("resume", ["Master", "Projects", "Resume Builder", "Build from files"])
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ---- master ---------------------------------------------------------------------

BULLET_COLUMNS = {                  # a new row starts ticked, rank 3, from "manual"
    "in_master": st.column_config.CheckboxColumn("On master", width=100, default=True,
                                                 help="Printed on the master resume; "
                                                 "unticked bullets wait in the pool"),
    "rank": st.column_config.NumberColumn("Rank", width=60, min_value=1,
                                          max_value=config.BULLET_RANK_MAX, step=1, default=3,
                                          help="1 filler … 5 quantified, big scope"),
    "text": st.column_config.TextColumn("Bullet", width=480, default=""),
    "skills": st.column_config.TextColumn("Skills", width=160, default="",
                                          help="Comma-separated"),
    "source": st.column_config.TextColumn("Source", width=80, default="manual", disabled=True),
}
BULLET_ROW_HEIGHT = 80              # tall enough for a bullet to wrap onto four lines


def bullets_frame(bullets: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{"text": b["text"], "skills": logic.skills_text(b["skills"]),
                          "in_master": bool(b["in_master"]), "rank": int(b["rank"]),
                          "source": b["source"]} for b in bullets],
                        columns=list(BULLET_COLUMNS))


def bullets_from(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for row in frame.itertuples(index=False):
        if logic.blank(row.text):
            continue
        rows.append({"text": str(row.text),
                     "skills": [] if logic.blank(row.skills) else logic.skills_list(row.skills),
                     "in_master": False if logic.blank(row.in_master) else bool(row.in_master),
                     "rank": 3 if logic.blank(row.rank) else int(row.rank),
                     "source": "manual" if logic.blank(row.source) else str(row.source)})
    return rows


def role_editor(role: dict, key: str, project: bool) -> dict:
    """Inputs for one role (or project) and its bullets; the edited role."""
    label = "Project" if project else "Employer"
    if project:
        name = st.text_input(label, role["employer"], key=f"{key}_employer")
        title = location = start = end = ""
    else:
        name_col, title_col = st.columns(2)
        name = name_col.text_input(label, role["employer"], key=f"{key}_employer")
        title = title_col.text_input("Title", role["title"], key=f"{key}_title")
        loc_col, start_col, end_col = st.columns([2, 1, 1])
        location = loc_col.text_input("Location", role["location"], key=f"{key}_location")
        start = start_col.text_input("From", role["start"], key=f"{key}_start")
        end = end_col.text_input("To", role["end"], key=f"{key}_end")
    frame = st.data_editor(bullets_frame(role["bullets"]), column_config=BULLET_COLUMNS,
                           num_rows="dynamic", hide_index=True, key=f"{key}_bullets",
                           width="stretch", row_height=BULLET_ROW_HEIGHT)
    remove = st.checkbox(f"Remove this {'project' if project else 'role'}", key=f"{key}_remove",
                         help="Dropped from the master, and from the pool, when you save")
    return {"employer": name, "title": title, "location": location, "start": start, "end": end,
            "bullets": bullets_from(frame), "remove": remove}


if section == "Master":
    master = data.resume_master()
    content = None if master is None else master["content"]
    if content is None or not content.get("name") and not content.get("roles"):
        empty("description", "No master resume yet",
              "Upload your resume under Build from files and let Claude turn it into data.")
    else:
        counts = logic.resume_counts(content)
        st.caption(f"{counts['master_roles']} of {logic.plural(counts['roles'], 'role')} and "
                   f"{counts['master_projects']} of "
                   f"{logic.plural(counts['projects'], 'project')} print on the master, with "
                   f"{counts['master_bullets']} bullets; {counts['pool_bullets']} more wait in "
                   f"the pool. Last saved {master['updated_on']:%b %d, %Y}.",
                   help="A role or project prints when at least one of its bullets is ticked "
                        "On master; the rest stay in the data for tailoring.")
        st.caption("To work on a project's full story with Claude, use Projects.")
        template = data.resume_template()
        if template is None:
            st.caption("Export needs the master resume's Word file: choose it as the template "
                       "under Build from files.")
        else:
            try:
                file = docx_io.build(template, content)
            except ValueError as problem:
                st.warning(f"Couldn't lay out the Word file: {problem}")
            else:
                st.download_button(
                    "Download Word file", file, mime=DOCX, type="primary",
                    file_name=f"{logic.file_stem(content.get('name', ''), 'Resume', 'Master')}.docx")
        if content.get("conflicts"):
            with card("conflicts"):
                st.markdown(f"{badge('orange', 'Check')} **The sources disagreed on these**")
                for item in content["conflicts"]:
                    st.markdown(f"- {md(item)}")
                st.caption("Fix the right value below; the list stays until you tick "
                           "“Clear the conflicts list” and save.")

        if on_phone():
            empty("computer", "Edit the master on your computer",
                  "Its roles and bullets are wide tables. On a phone you can download it, and "
                  "Projects and Resume Builder work here.")
            st.stop()
        form_round = round_key("master")       # a fresh form after every save: no stale cells
        with st.form(f"resume_master_{form_round}"):
            st.markdown("**Contact**")
            name_col, email_col = st.columns(2)
            name = name_col.text_input("Name", content.get("name", ""))
            email = email_col.text_input("Email", content.get("email", ""))
            phone_col, link_col = st.columns(2)
            phone = phone_col.text_input("Phone", content.get("phone", ""))
            linkedin = link_col.text_input("LinkedIn", content.get("linkedin", ""))

            st.markdown("**Experience**")
            roles = [role_editor(role, f"{form_round}_role{n}", project=False)
                     for n, role in enumerate(content.get("roles", []))]
            st.markdown("**Education**")
            education = st.data_editor(
                pd.DataFrame(content.get("education", []), columns=["school", "when", "degree"]),
                column_config={"school": "School", "when": "When", "degree": "Degree and detail"},
                num_rows="dynamic", hide_index=True, key=f"{form_round}_education",
                width="stretch")
            st.markdown("**Skills**")
            skills = st.data_editor(
                pd.DataFrame(content.get("skill_groups", []), columns=["name", "skills"]),
                column_config={"name": "Group", "skills": st.column_config.TextColumn(
                    "Skills", width="large")},
                num_rows="dynamic", hide_index=True, key=f"{form_round}_skill_groups",
                width="stretch")
            st.markdown("**Personal projects**")
            projects = [role_editor(project, f"{form_round}_project{n}", project=True)
                        for n, project in enumerate(content.get("projects", []))]
            clear_conflicts = st.checkbox("Clear the conflicts list: I've checked them",
                                          value=False, disabled=not content.get("conflicts"))
            saved = st.form_submit_button("Save", type="primary")
        if saved:
            edited = {
                "name": name, "email": email, "phone": phone, "linkedin": linkedin,
                "roles": [r for r in roles if not r.pop("remove")],
                "projects": [p for p in projects if not p.pop("remove")],
                "education": [r for r in education.fillna("").to_dict("records")
                              if str(r.get("school", "")).strip()],
                "skill_groups": [r for r in skills.fillna("").to_dict("records")
                                 if str(r.get("name", "")).strip()],
                "conflicts": [] if clear_conflicts else content.get("conflicts", []),
            }
            data.save_resume_master(logic.clean_resume(edited), today)
            bump_round("master")
            done("Saved.")
        add_role, add_project = st.columns(2)
        if add_role.button("Add a role", width="stretch"):
            content["roles"].append({"employer": "New employer", "title": "", "location": "",
                                     "start": "", "end": "", "bullets": []})
            data.save_resume_master(logic.clean_resume(content), today)
            bump_round("master")
            done("Added a role: fill it in and save.")
        if add_project.button("Add a project", width="stretch"):
            content["projects"].append({"employer": "New project", "title": "", "location": "",
                                        "start": "", "end": "", "bullets": []})
            data.save_resume_master(logic.clean_resume(content), today)
            bump_round("master")
            done("Added a project: fill it in and save.")

# ---- projects ---------------------------------------------------------------------

LEVEL_COLORS = {"strong": "green", "thin": "orange", "weak": "red"}
PERSONAL = "Personal project"


def review_now(project: dict, answers: list[tuple[str, str]], content: dict) -> None:
    """One Claude review of a project: logged, saved, and (with answers) its
    facts worked into the details, the old text kept for undo."""
    profile = data.job_profile() or {}
    with st.spinner("Claude is reading the project…"):
        try:
            result, usage = ai.review_project(project, answers, logic.bullet_style(content),
                                              str(profile.get("target_roles") or ""))
        except ai.AIError as problem:
            st.error(str(problem))
            if problem.usage:
                data.log_ai_usage("review project (failed)", problem.usage.model,
                                  problem.usage.input_tokens, problem.usage.output_tokens,
                                  problem.usage.cost_usd, today)
            return
    data.log_ai_usage("review project", usage.model, usage.input_tokens, usage.output_tokens,
                      usage.cost_usd, today)
    project_id = int(project["project_id"])
    details = result.pop("details")
    changed = {}
    if any(a.strip() for _, a in answers):           # only answers may change your words
        changed = {k: v.strip() for k, v in details.items()
                   if v.strip() and v.strip() != str(project.get(k) or "").strip()}
    if changed:
        result["before"] = {k: str(project.get(k) or "") for k in changed}
        data.update_project(project_id, today, **changed)
    if logic.blank(project.get("skills")) and result["skills"]:
        data.update_project(project_id, today, skills=", ".join(result["skills"]))
    data.save_project_review(project_id, result, today)
    bump_round(f"answers_{project_id}")
    worked = f", and worked your answers into {', '.join(changed)}" if changed else ""
    done(f"Claude rates it {result['strength']}/10{worked}. Cost ${usage.cost_usd:.2f}.",
         "project_round")


def bullet_to_master(project: dict, text: str, content: dict, rank: int) -> None:
    """Put a bullet into the master's pool under the project's role."""
    updated, where = logic.add_to_master(content, project, text, rank)
    if where == "":
        st.error(f"{project['employer']} isn't an employer on the master: choose the right one "
                 "under Where, or add the role on Master.")
        return
    if where == "already":
        done("That bullet is already on the master.")
    data.save_resume_master(logic.clean_resume(updated), today)
    bump_round("master")
    done(f"Added to the master's pool under {where}. Resume Builder can pick it now; tick "
         "it On master under Master to print it on the master itself.", "project_round")


if section == "Projects":
    master = data.resume_master()
    content = {} if master is None else master["content"]
    bank = data.projects()
    st.caption("Every project in full: the problem, what you did, how it turned out. The detail "
               "score is free and shows which need more. Claude reviews one at a time, asks "
               "what's missing and words bullets from your answers; a bullet you pick goes into "
               "the master's pool, where Resume Builder chooses from it.")
    waiting = logic.import_projects(data.resume_source_texts().get("projects", ""), content,
                                    [] if bank.empty else bank["title"].tolist())
    if waiting and st.button(
            f"Import {logic.plural(len(waiting), 'project')} from your projects spreadsheet "
            "(free)", type="primary" if bank.empty else "secondary", width="stretch"):
        for fields in waiting:
            data.add_project(today, **fields)
        bump_round("project_pick")
        done(f"Imported {logic.plural(len(waiting), 'project')}. The ones needing the most "
             "detail are first.")

    employers = logic.master_employers(content)
    if disclosure("Add a project", "add_project"):
        with st.form(f"add_project_{st.session_state.get('add_project_round', 0)}"):
            new_title = st.text_input("Project")
            new_where = st.selectbox("Where", employers + [PERSONAL])
            new_summary = st.text_area("What it is, in a line or two", height=80)
            added = st.form_submit_button("Add", type="primary")
        if added:
            if not new_title.strip():
                st.error("Give the project a name.")
            else:
                employer = None if new_where == PERSONAL else new_where
                new_id = data.add_project(today, kind="work" if employer else "personal",
                                          title=new_title, employer=employer,
                                          summary=new_summary)
                st.session_state["open_project"] = new_id
                st.session_state["open_add_project"] = False
                bump_round("project_pick")
                done(f"Added {new_title.strip()}: fill in the rest below.", "add_project_round")

    if bank.empty:
        empty("work", "No projects yet",
              "Add one above, or upload your projects spreadsheet under Build from files and "
              "import it here.")
    else:
        records = bank.to_dict("records")
        details = {int(r["project_id"]): logic.project_detail(r) for r in records}
        ordered = sorted(records, key=lambda r: (details[int(r["project_id"])]["score"],
                                                 str(r["title"]).lower()))
        phone = on_phone()
        # A computer shows the list beside the open project; a phone, one under the other.
        list_area, detail_area = ((st.container(), st.container()) if phone
                                  else st.columns([2, 3], gap="large"))
        with list_area:
            levels = [d["level"] for d in details.values()]
            st.markdown(" ".join(
                badge(LEVEL_COLORS[level], f"{levels.count(level)} {name}") for level, name in
                (("strong", "strong"), ("thin", "thin"), ("weak", "need detail"))
                if levels.count(level)))
            overview = st.dataframe(
                pd.DataFrame([{
                    "Project": r["title"],
                    "Detail": details[int(r["project_id"])]["score"],
                    "Claude": (f"{r['review']['strength']}/10" if isinstance(r["review"], dict)
                               else "–")} for r in ordered]),
                hide_index=True, width="stretch",
                **({} if phone else {"on_select": "rerun", "selection_mode": "single-row",
                                     "key": round_key("projects_table")}),
                column_config={
                    "Detail": st.column_config.ProgressColumn(
                        "Detail", min_value=0, max_value=100, format="%d", width="small",
                        help="The free detail score: situation, task, action, result, a number, "
                             "skills and a bullet"),
                    "Claude": st.column_config.TextColumn("Claude", width="small")})

            ids = [int(r["project_id"]) for r in ordered]
            if not phone and overview.selection.rows and overview.selection.rows[0] < len(ids):
                st.session_state["open_project"] = ids[overview.selection.rows[0]]
                bump_round("projects_table")
            pick_key = round_key("project_pick")
            if (wanted := st.session_state.pop("open_project", None)) in ids:
                st.session_state[pick_key] = wanted
            labels = {int(r["project_id"]): f"{r['title']} · {details[int(r['project_id'])]['score']}"
                      f"/100" for r in ordered}
            picked = st.selectbox("Project", ids, format_func=labels.get, key=pick_key)
        with detail_area:
            project = data.project(picked)
            detail = details[picked]
            review = project["review"] if isinstance(project["review"], dict) else None

            score_badge = badge(LEVEL_COLORS[detail["level"]], f"Detail {detail['score']}/100")
            st.markdown(f"{score_badge} **{md(project['title'])}**")
            if detail["missing"]:
                st.caption("To strengthen it, add: " + "; ".join(detail["missing"]) + ".")
            if project["bullet"]:
                place = logic.bullet_status(content, project["bullet"])
                note = {"on the master": badge("green", "On the master"),
                        "in the pool": badge("blue", "In the master's pool")}.get(
                    place, badge("gray", "Not on the master yet"))
                st.markdown(f"{note} {md(project['bullet'])}")
                if place is None and master is not None and "[" not in project["bullet"]:
                    if st.button("Add this bullet to the master's pool", key=f"pool_{picked}"):
                        bullet_to_master(project, project["bullet"], content,
                                         logic.project_rank(review["strength"]) if review else 3)

            where_value = project["employer"] or PERSONAL
            where_options = employers + [PERSONAL]
            if where_value not in where_options:
                where_options = [where_value] + where_options
            with st.form(f"project_{picked}_{st.session_state.get('project_round', 0)}"):
                title = st.text_input("Project", project["title"])
                where_col, when_col = st.columns([2, 1])
                where = where_col.selectbox("Where", where_options,
                                            index=where_options.index(where_value))
                period = when_col.text_input("When", project["period"] or "",
                                             placeholder="Jan 2025 – Present")
                summary = st.text_area("What it is", project["summary"] or "", height=68)
                situation = st.text_area("Situation: the problem, or why it mattered",
                                         project["situation"] or "", height=110)
                task = st.text_area("Task: what you were responsible for", project["task"] or "",
                                    height=90)
                action = st.text_area("Action: what you did and how", project["action"] or "",
                                      height=160)
                result = st.text_area("Result: how it turned out, with numbers",
                                      project["result"] or "", height=110)
                skills = st.text_input("Skills (comma-separated)", project["skills"] or "")
                bullet = st.text_area("Resume bullet", project["bullet"] or "", height=80,
                                      help="The line for your resume: one of Claude's options "
                                           "below, or your own")
                saved = st.form_submit_button("Save", type="primary")
            if saved:
                if not title.strip():
                    st.error("The project needs a name.")
                else:
                    employer = None if where == PERSONAL else where
                    data.update_project(picked, today, kind="work" if employer else "personal",
                                        title=title, employer=employer, period=period,
                                        summary=summary, situation=situation, task=task,
                                        action=action, result=result, skills=skills, bullet=bullet)
                    done("Saved.", "project_round")

            st.markdown("**Claude**")
            if not ai.ready():
                st.caption("Needs the Claude key: see Build from files.")
            else:
                if review:
                    rating = badge("blue", f"Claude: {review['strength']}/10")
                    st.markdown(f"{rating} {md(review['verdict'])}")
                if claude_button("Review again" if review else "Review with Claude",
                                 f"review_{picked}", type="secondary" if review else "primary",
                                 help="Claude rates how it reads, asks what's missing and words "
                                      "bullets from your own facts (about 10 cents)"):
                    review_now(project, [], content)
                if review and review["questions"]:
                    st.markdown("**Claude's questions**")
                    st.caption("Answer what you can, a sentence each, and skip the rest. Claude "
                               "works the facts into the details above (your words stay) and "
                               "rewords the bullets.")
                    answer_key = round_key(f"answers_{picked}")
                    with st.form(answer_key):          # one tap sends every answer
                        answers = [(question, st.text_area(question, key=f"{answer_key}_{n}",
                                                           height=68))
                                   for n, question in enumerate(review["questions"])]
                        answered = claude_submit("Work my answers in", f"answers_{picked}",
                                                 help="About 10 cents")
                    if answered:
                        if any(a.strip() for _, a in answers):
                            review_now(project, answers, content)
                        else:
                            st.error("Answer at least one question first.")
                if review and review["bullets"]:
                    st.markdown("**Bullet options**")
                    for n, option in enumerate(review["bullets"]):
                        with card(f"option-{picked}-{n}"):
                            st.markdown(md(option))
                            unfilled = "[" in option
                            if unfilled:
                                st.caption("Fill in the [bracketed] part once it's in the Resume "
                                           "bullet box above, then save.")
                            use_col, pool_col = st.columns(2)
                            if use_col.button("Use this", key=f"use_{picked}_{n}", width="stretch"):
                                data.update_project(picked, today, bullet=option)
                                done("That's the project's resume bullet now.", "project_round")
                            if pool_col.button("Use it and add to the master's pool",
                                               key=f"use_pool_{picked}_{n}", width="stretch",
                                               disabled=unfilled or master is None):
                                data.update_project(picked, today, bullet=option)
                                bullet_to_master(project, option, content,
                                                 logic.project_rank(review["strength"]))
                if review and review.get("before"):
                    if st.button("Undo Claude's last change to the details", key=f"undo_{picked}"):
                        data.update_project(picked, today, **review["before"])
                        data.save_project_review(
                            picked, {k: v for k, v in review.items() if k != "before"}, today)
                        done("Put the details back as they were.", "project_round")

            if delete_button("project", f"project_{picked}"):
                data.delete_project(picked)
                bump_round("project_pick")
                done(f"Deleted {project['title']}.")

# ---- tailor -----------------------------------------------------------------------

TAILORED_ROW_HEIGHT = 96            # two narrower text columns: room for five lines
TAILORED_COLUMNS = {
    "text": st.column_config.TextColumn("Bullet", width=440, default=""),
    "original": st.column_config.TextColumn("From the master", width=320, default="",
                                            disabled=True),
    "skills": st.column_config.TextColumn("Skills", width=150, default="",
                                          help="Comma-separated"),
}


def tailored_frame(bullets: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{"text": b["text"], "original": b["original"],
                          "skills": logic.skills_text(b["skills"])} for b in bullets],
                        columns=list(TAILORED_COLUMNS))


def tailored_from(frame: pd.DataFrame) -> list[dict]:
    return [{"text": str(row.text),
             "original": "" if logic.blank(row.original) else str(row.original),
             "skills": [] if logic.blank(row.skills) else logic.skills_list(row.skills)}
            for row in frame.itertuples(index=False) if not logic.blank(row.text)]


def tailored_roles(tailored: dict, kind: str, tailor_id: int) -> list[dict]:
    """The grids for a version's roles (or projects); the edited roles."""
    edited = []
    for n, role in enumerate(tailored.get(kind, [])):
        when = f" · {role['start']} – {role['end']}" if role.get("start") else ""
        title = f" — {role['title']}" if role.get("title") else ""
        st.markdown(f"**{md(role['employer'])}**{md(title)}{md(when)}")
        frame = st.data_editor(tailored_frame(role["bullets"]), column_config=TAILORED_COLUMNS,
                               num_rows="dynamic", hide_index=True, width="stretch",
                               key=f"tailored_{tailor_id}_{kind}{n}", row_height=TAILORED_ROW_HEIGHT)
        edited.append({**role, "bullets": tailored_from(frame)})
    return edited


if section == "Resume Builder":
    master = data.resume_master()
    content = None if master is None else master["content"]
    apps = data.applications()
    open_apps = apps if apps.empty else apps[apps["status"].isin(config.OPEN_STATUSES)]
    if not content or not content.get("roles"):
        empty("description", "No master resume yet",
              "Build it under Build from files first: every tailored resume starts from it.")
    elif open_apps.empty:
        empty("inbox", "No open applications",
              "Add the job on Applications, or move a lead there, then tailor the master to it.")
    else:
        ids = [int(i) for i in open_apps["application_id"]]
        labels = logic.application_labels(open_apps)
        # The dropdown forgets its choice while another section is open; keep it ourselves.
        if (wanted := st.session_state.pop("tailor_application", None)) in ids:
            st.session_state["tailor_pick"] = wanted            # sent here from Applications
        elif st.session_state.get("tailor_pick") not in ids:
            kept = st.session_state.get("tailor_pick_kept")
            st.session_state["tailor_pick"] = kept if kept in ids else ids[0]
        picked = st.selectbox("Application", ids, format_func=lambda i: labels[i],
                              key="tailor_pick")
        st.session_state["tailor_pick_kept"] = picked
        app = data.application(picked)
        template = data.resume_template()
        line_chars = logic.LINE_CHARS if template is None else docx_io.line_chars(template)
        posting_button(app, "resume")
        with st.form(f"posting_{picked}"):
            posting = st.text_area("Job posting", value=app["posting"] or "", height=200,
                                   help="Read it from the link above, or paste the whole "
                                        "posting: Claude tailors to its words.")
            if st.form_submit_button("Save posting"):
                data.update_application(picked, posting=posting)
                done("Posting saved.")
        ready = ai.ready() and bool(app["posting"])
        steer = st.text_input("Steer Claude (optional)", key=f"steer_{picked}",
                              placeholder="e.g. lead with the Power BI work; keep the intern role")
        if claude_button("Tailor with Claude", "tailor", type="primary", disabled=not ready):
            with st.spinner("Reading the posting and choosing bullets…"):
                try:
                    result, usage = ai.tailor(content, app["posting"], app["company"],
                                              app["role"], today, steer)
                except ai.AIError as problem:
                    st.error(str(problem))
                    if problem.usage:                  # a reply came back: it still cost
                        data.log_ai_usage("tailor (failed)", problem.usage.model,
                                          problem.usage.input_tokens,
                                          problem.usage.output_tokens, problem.usage.cost_usd,
                                          today)
                else:
                    tailored = logic.fit_column(          # one page: the master's column
                        logic.clean_tailored(logic.match_endings(result, content)), content,
                        line_chars)
                    data.add_tailored(picked, tailored, steer, usage.model, today)
                    data.log_ai_usage("tailor", usage.model, usage.input_tokens,
                                      usage.output_tokens, usage.cost_usd, today)
                    bump_round("tailor_version")
                    counts = logic.tailored_counts(tailored)
                    done(f"Tailored for {app['company']}: "
                         f"{logic.plural(counts['bullets'], 'bullet')}, {counts['covered']} of "
                         f"{counts['keywords']} keywords covered. Cost ${usage.cost_usd:.2f}.")
        if not ai.ready():
            st.caption("Needs the Claude key (see Build from files).")
        elif not app["posting"]:
            st.caption("Get the posting from the link, or paste and save it, first.")
        else:
            st.caption("One Claude call picks and rewords the master's bullets for this "
                       "posting, writes the cover letter and lists what it changed. About "
                       "45 cents. Each click adds a version; earlier ones stay.")

        versions = data.tailored_versions(picked)
        if versions.empty:
            st.caption("No tailored version yet.")
        else:
            version_ids = [int(i) for i in versions["tailor_id"]]
            version_labels = {
                int(r.tailor_id): f"Version {r.version} · {logic.when(r.created_on, today)}"
                + ("" if logic.blank(r.notes) else f" · {r.notes}") for r in versions.itertuples()}
            if len(version_ids) > 1:
                tailor_id = st.selectbox("Version", version_ids, key=round_key("tailor_version"),
                                         format_func=lambda i: version_labels[i])
            else:
                tailor_id = version_ids[0]
            row = data.tailored(tailor_id)
            tailored = row["content"]
            counts = logic.tailored_counts(tailored)
            unmatched = (f", {counts['unmatched']} without a master original"
                         if counts["unmatched"] else "")
            st.caption(f"{logic.plural(counts['bullets'], 'bullet')}: {counts['kept']} as on the "
                       f"master, {counts['reworded']} reworded{unmatched} · {counts['covered']} "
                       f"of {counts['keywords']} keywords covered · {row['model']}.")
            lines = logic.column_lines(tailored.get("roles", []), line_chars)
            limit = logic.column_lines(logic.printed_roles(content.get("roles", [])), line_chars)
            if lines > limit:
                st.warning(f"Longer than the master: the experience runs about "
                           f"{logic.plural(lines - limit, 'line')} past what the master's "
                           "column holds, so Word can push Education and Skills onto a "
                           "second page. "
                           "Trim to one page drops the last bullet of the longest role until "
                           "it fits; or trim below yourself, or tailor again with the steer "
                           "“shorter”.")
                if st.button("Trim to one page", key=f"fit_{tailor_id}"):
                    fitted = logic.fit_column(tailored, content, line_chars)
                    data.save_tailored(tailor_id, fitted)
                    gone = len(fitted["changes"]) - len(tailored.get("changes", []))
                    done(f"Trimmed to one page: {logic.plural(gone, 'bullet')} left off.")
            name = content.get("name", "")
            if template is None:
                st.caption("Downloads need the master resume's Word file as the template "
                           "(Build from files).")
            else:
                try:
                    resume_file = docx_io.build(template,
                                                logic.tailored_export(content, tailored))
                    letter_file = docx_io.letter(
                        template, name, logic.contact_line(content),
                        [logic.long_date(today)]
                        + logic.letter_paragraphs(tailored.get("cover_letter", "")))
                except ValueError as problem:
                    st.warning(f"Couldn't lay out the Word files: {problem}")
                else:
                    resume_col, letter_col = st.columns(2)
                    resume_col.download_button(
                        "Download tailored resume", resume_file, mime=DOCX, type="primary",
                        file_name=f"{logic.file_stem(name, 'Resume', app['company'])}.docx",
                        width="stretch")
                    letter_col.download_button(
                        "Download cover letter", letter_file, mime=DOCX, width="stretch",
                        file_name=f"{logic.file_stem(name, 'CoverLetter', app['company'])}.docx")
            if tailored.get("fit_notes"):
                with card(f"fit-{tailor_id}"):
                    st.markdown(f"{badge('blue', 'Fit')} {md(tailored['fit_notes'])}")
            if tailored.get("keywords"):
                st.markdown("**Keywords from the posting**  \n" + " ".join(
                    badge("green" if k["covered"] else "orange", k["term"])
                    for k in tailored["keywords"]))
                st.caption("Green: shown on this resume. Orange: not shown; add it only if "
                           "it's true of you.")
            if tailored.get("changes"):
                with card(f"changes-{tailor_id}"):
                    st.markdown(f"{badge('gray', 'Changes')} **What changed from the master, "
                                "and why**")
                    for item in tailored["changes"]:
                        st.markdown(f"- {md(item)}")
            if on_phone():
                st.caption("Edit the bullets and the letter on your computer; the downloads "
                           "above work here.")
            else:
                with st.form(f"tailored_{tailor_id}"):
                    st.markdown("**Experience**")
                    roles = tailored_roles(tailored, "roles", tailor_id)
                    projects = []
                    if tailored.get("projects"):
                        st.markdown("**Personal projects**")
                        projects = tailored_roles(tailored, "projects", tailor_id)
                    st.markdown("**Skills**")
                    skills = st.data_editor(
                        pd.DataFrame(tailored.get("skill_groups", []), columns=["name", "skills"]),
                        column_config={"name": "Group", "skills": st.column_config.TextColumn(
                            "Skills", width="large")},
                        num_rows="dynamic", hide_index=True, key=f"tailored_{tailor_id}_skills",
                        width="stretch")
                    st.markdown("**Cover letter**")
                    letter_text = st.text_area(
                        "Cover letter", value=tailored.get("cover_letter", ""), height=360,
                        label_visibility="collapsed")
                    saved = st.form_submit_button("Save", type="primary")
                if saved:
                    edited = {**tailored, "roles": roles, "projects": projects,
                              "skill_groups": [r for r in skills.fillna("").to_dict("records")
                                               if str(r.get("name", "")).strip()],
                              "cover_letter": letter_text}
                    data.save_tailored(tailor_id, logic.clean_tailored(edited))
                    done("Saved.")
            if delete_button("version", f"tailored_{tailor_id}"):
                data.delete_tailored(tailor_id)
                bump_round("tailor_version")
                done("Removed that version.")


# ---- build from files ---------------------------------------------------------

KIND_LABELS = {"resume": "The master resume (Word)", "history": "Project history (Word)",
               "projects": "Projects spreadsheet (CSV)", "other": "Something else to read"}

if section == "Build from files":
    if on_phone():
        empty("computer", "Build from files on your computer",
              "Uploading Word files and building the master is easier on a bigger screen.")
        st.stop()
    status_col, usage_col = st.columns(2)
    with status_col:
        if ai.ready():
            st.markdown(f"{badge('green', 'Key found')} Claude: `{config.AI_MODEL}`")
            if claude_button("Test connection (free)", "ping"):
                try:
                    st.success(ai.ping())
                except ai.AIError as problem:
                    st.error(str(problem))
        else:
            st.markdown(f"{badge('red', 'No key')} Add ANTHROPIC_API_KEY to the app's secrets "
                        "(above the [auth] block) to use Claude here.")
    with usage_col:
        calls, cost = data.ai_usage_since(logic.month_start(today))
        st.markdown(f"{badge('gray', 'Usage')} ${cost:.2f} this month across "
                    f"{logic.plural(calls, 'Claude call')}")

    st.markdown("**Files**")
    st.caption("Upload your master resume as a Word file (it also becomes the template the "
               "export is modelled on), plus anything with more detail: a project history, a "
               "projects spreadsheet, old resumes. Claude reads them all and builds the master.")
    uploaded = st.file_uploader("Add files", type=["docx", "csv", "txt", "md"],
                                accept_multiple_files=True, key="resume_uploads")
    kind = st.selectbox("What is it?", list(KIND_LABELS), format_func=KIND_LABELS.get,
                        key="resume_kind")
    if st.button("Add", type="primary", disabled=not uploaded):
        added = 0
        for upload in uploaded:
            raw = upload.getvalue()
            lower = upload.name.lower()
            try:
                if lower.endswith(".docx"):
                    text = docx_io.text(raw)
                elif lower.endswith(".csv"):
                    text = logic.projects_text(pd.read_csv(io.BytesIO(raw)))
                else:
                    text = raw.decode("utf-8", errors="replace")
            except Exception as problem:      # a file Word or pandas can't read
                st.error(f"Couldn't read {upload.name}: {problem}")
                continue
            source_id = data.add_resume_source(
                upload.name, kind, text, raw if lower.endswith(".docx") else None, today)
            if kind == "resume" and lower.endswith(".docx"):
                data.set_resume_template(source_id, today)
            added += 1
        if added:
            done(f"Added {logic.plural(added, 'file')}.")

    sources = data.resume_sources()
    master = data.resume_master()
    template_id = None if master is None else logic.value(master["template_source_id"])
    if sources.empty:
        empty("upload_file", "No files yet", "Start with your master resume as a Word file.")
    for source in sources.itertuples():
        source_id = int(source.source_id)
        with card(f"source-{source_id}"):
            text_col, button_col = st.columns([4, 1], vertical_alignment="center", wrap=False)
            is_template = template_id is not None and int(template_id) == source_id
            tags = badge("blue", KIND_LABELS.get(source.kind, source.kind).split(" (")[0])
            if is_template:
                tags += " " + badge("green", "Template")
            text_col.markdown(f"{tags} **{md(source.filename)}**  \n"
                              f"{source.chars:,} characters of text · uploaded "
                              f"{logic.when(source.uploaded_on, today)}")
            if source.has_file and source.kind == "resume" and not is_template:
                if button_col.button("Use as template", key=f"template_{source_id}",
                                     width="stretch"):
                    data.set_resume_template(source_id, today)
                    done(f"{source.filename} is the export template.")
            if delete_button("file", f"source_{source_id}"):
                data.delete_resume_source(source_id)
                done(f"Removed {source.filename}.")

    st.markdown("**Build**")
    texts = data.resume_source_texts()
    can_build = ai.ready() and "resume" in texts
    st.caption("One Claude call reads every file above and writes the master as data: the "
               "resume's bullets word for word, extra bullets from the other files into the "
               "pool, skills tagged, and any disagreements between files listed. About "
               "30 cents. It replaces the current master, so save edits you care about "
               "first, or export them.")
    if claude_button("Build the master with Claude", "build_master", type="primary",
                     disabled=not can_build):
        with st.spinner("Reading your files…"):
            try:
                content, usage = ai.structure_resume(texts)
            except ai.AIError as problem:
                st.error(str(problem))
                if problem.usage:
                    data.log_ai_usage("structure resume (failed)", problem.usage.model,
                                      problem.usage.input_tokens, problem.usage.output_tokens,
                                      problem.usage.cost_usd, today)
            else:
                data.save_resume_master(logic.clean_resume(content), today)
                data.log_ai_usage("structure resume", usage.model, usage.input_tokens,
                                  usage.output_tokens, usage.cost_usd, today)
                counts = logic.resume_counts(content)
                st.session_state["resume_goto"] = "Master"
                done(f"Built the master: {logic.plural(counts['roles'], 'role')}, "
                     f"{counts['master_bullets']} bullets on it, {counts['pool_bullets']} in "
                     f"the pool, {logic.plural(len(content.get('conflicts', [])), 'conflict')} "
                     f"to check. Cost ${usage.cost_usd:.2f}.")
    if not ai.ready():
        st.caption("Needs the Claude key.")
    elif "resume" not in texts:
        st.caption("Needs the master resume uploaded as kind “The master resume”.")
