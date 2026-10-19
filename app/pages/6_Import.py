"""Bring applications in from a spreadsheet (CSV)."""

import pandas as pd
import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import data
import logic
from ui import md, setup, status_label

setup("Import", "Bring applications in from a spreadsheet")

st.markdown(
    "Upload a CSV of applications (in Excel or Google Sheets: **File → Download → CSV**). "
    "Each row needs a **company** and a **role**; the other columns are optional: "
    "status, date applied, link, location, work mode, source, salary, notes. "
    "Headers are matched loosely — “Company Name” or “Job Title” work too.")

template = pd.DataFrame([{
    "Company": "Acme", "Role": "Data Analyst", "Status": "Applied",
    "Date Applied": "2026-10-01", "Link": "https://example.com/jobs/1", "Location": "Chicago",
    "Work Mode": "Hybrid", "Source": "LinkedIn", "Salary": "$90k-$110k", "Notes": "",
}])
st.download_button("Download a template", template.to_csv(index=False),
                   file_name="applications_template.csv", mime="text/csv")

upload = st.file_uploader("CSV file", type=["csv"])
if upload is None:
    st.stop()

try:
    frame = pd.read_csv(upload, dtype=str, keep_default_na=False)
except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
    st.error(f"Couldn't read that file as CSV: {exc}")
    st.stop()

rows, problems = logic.map_import(frame)
for problem in problems:
    st.warning(md(problem))
if not rows:
    st.stop()

columns = logic.match_columns(frame.columns)
st.caption(md("Matched columns: " + ", ".join(f"{header} → {field}"
                                               for field, header in columns.items())))
preview = pd.DataFrame(rows)
preview["status"] = preview["status"].map(status_label)
preview["salary"] = [logic.salary_range(r["salary_min"], r["salary_max"]) for r in rows]
st.dataframe(preview[["company", "role", "status", "applied_on", "location", "source", "salary"]],
             hide_index=True, width="stretch")

if st.button(f"Import {logic.plural(len(rows), 'application')}", type="primary"):
    added, skipped = data.import_applications(rows, data.today())
    note = f" Skipped {skipped} already in the tracker." if skipped else ""
    st.success(f"Imported {logic.plural(added, 'application')}.{note}")
