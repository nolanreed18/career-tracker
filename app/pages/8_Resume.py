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
from ui import badge, card, delete_button, empty, md, sections, setup

setup("Resume", "Your master resume as data: built from your files, tailored per job",
      wide=True)

today = data.today()


def done(message: str) -> None:
    st.session_state["flash"] = message
    st.rerun()


if goto := st.session_state.pop("resume_goto", None):   # an action that moves the eye
    st.session_state["section_resume"] = goto
section = sections("resume", ["Master", "Build from files"])

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
    return {"employer": name, "title": title, "location": location, "start": start, "end": end,
            "bullets": bullets_from(frame)}


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
                name = "".join(ch for ch in content.get("name", "Resume") if ch.isalnum())
                st.download_button("Download Word file", file,
                                   file_name=f"{name or 'Resume'}_Resume_Master.docx",
                                   mime="application/vnd.openxmlformats-officedocument."
                                        "wordprocessingml.document", type="primary")
        if content.get("conflicts"):
            with card("conflicts"):
                st.markdown(f"{badge('orange', 'Check')} **The sources disagreed on these**")
                for item in content["conflicts"]:
                    st.markdown(f"- {md(item)}")
                st.caption("Fix the right value below; the list stays until you tick "
                           "“Clear the conflicts list” and save.")

        with st.form("resume_master"):
            st.markdown("**Contact**")
            name_col, email_col = st.columns(2)
            name = name_col.text_input("Name", content.get("name", ""))
            email = email_col.text_input("Email", content.get("email", ""))
            phone_col, link_col = st.columns(2)
            phone = phone_col.text_input("Phone", content.get("phone", ""))
            linkedin = link_col.text_input("LinkedIn", content.get("linkedin", ""))

            st.markdown("**Experience**")
            roles = [role_editor(role, f"role{n}", project=False)
                     for n, role in enumerate(content.get("roles", []))]
            st.markdown("**Education**")
            education = st.data_editor(
                pd.DataFrame(content.get("education", []), columns=["school", "when", "degree"]),
                column_config={"school": "School", "when": "When", "degree": "Degree and detail"},
                num_rows="dynamic", hide_index=True, key="education", width="stretch")
            st.markdown("**Skills**")
            skills = st.data_editor(
                pd.DataFrame(content.get("skill_groups", []), columns=["name", "skills"]),
                column_config={"name": "Group", "skills": st.column_config.TextColumn(
                    "Skills", width="large")},
                num_rows="dynamic", hide_index=True, key="skill_groups", width="stretch")
            st.markdown("**Personal projects**")
            projects = [role_editor(project, f"project{n}", project=True)
                        for n, project in enumerate(content.get("projects", []))]
            clear_conflicts = st.checkbox("Clear the conflicts list: I've checked them",
                                          value=False, disabled=not content.get("conflicts"))
            saved = st.form_submit_button("Save", type="primary")
        if saved:
            edited = {
                "name": name, "email": email, "phone": phone, "linkedin": linkedin,
                "roles": roles, "projects": projects,
                "education": [r for r in education.fillna("").to_dict("records")
                              if str(r.get("school", "")).strip()],
                "skill_groups": [r for r in skills.fillna("").to_dict("records")
                                 if str(r.get("name", "")).strip()],
                "conflicts": [] if clear_conflicts else content.get("conflicts", []),
            }
            data.save_resume_master(logic.clean_resume(edited), today)
            done("Saved.")
        add_role, add_project = st.columns(2)
        if add_role.button("Add a role", width="stretch"):
            content["roles"].append({"employer": "New employer", "title": "", "location": "",
                                     "start": "", "end": "", "bullets": []})
            data.save_resume_master(logic.clean_resume(content), today)
            done("Added a role: fill it in and save.")
        if add_project.button("Add a project", width="stretch"):
            content["projects"].append({"employer": "New project", "title": "", "location": "",
                                        "start": "", "end": "", "bullets": []})
            data.save_resume_master(logic.clean_resume(content), today)
            done("Added a project: fill it in and save.")

# ---- build from files ---------------------------------------------------------------

KIND_LABELS = {"resume": "The master resume (Word)", "history": "Project history (Word)",
               "projects": "Projects spreadsheet (CSV)", "other": "Something else to read"}

if section == "Build from files":
    status_col, usage_col = st.columns(2)
    with status_col:
        if ai.ready():
            st.markdown(f"{badge('green', 'Key found')} Claude: `{config.AI_MODEL}`")
            if st.button("Test connection (free)"):
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
    if st.button("Build the master with Claude", type="primary", disabled=not can_build):
        with st.spinner("Reading your files…"):
            try:
                content, usage = ai.structure_resume(texts)
            except ai.AIError as problem:
                st.error(str(problem))
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
