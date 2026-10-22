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
    delete_button,
    done,
    empty,
    md,
    posting_button,
    round_key,
    sections,
    setup,
)

setup("Resume", "Your master resume as data: built from your files, tailored per job",
      wide=True)

today = data.today()


if goto := st.session_state.pop("resume_goto", None):   # an action that moves the eye
    st.session_state["section_resume"] = goto
section = sections("resume", ["Master", "Resume Builder", "Build from files"])
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
        if st.button("Tailor with Claude", type="primary", disabled=not ready):
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
                    tailored = logic.clean_tailored(logic.match_endings(result, content))
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
            budget, length = logic.master_budget(content), logic.tailored_chars(tailored)
            if length > budget["characters"] * logic.PAGE_SLACK:
                st.warning(f"Longer than the master ({length:,} characters of bullets against "
                           f"{budget['characters']:,}): it may run onto a second page. Trim a "
                           "bullet or two below, or tailor again with the steer “shorter”.")
            template = data.resume_template()
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
                letter_text = st.text_area("Cover letter", value=tailored.get("cover_letter", ""),
                                           height=360, label_visibility="collapsed")
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
