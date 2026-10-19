"""Companies you're looking at and the people you know there."""

import streamlit as st

import fresh

fresh.check()                   # after a redeploy: no stale copies of the app's modules

import config
import data
import logic
from ui import (
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
)

setup("Companies & Contacts", "Who you're looking at, and who you know there")


today = data.today()


def done(message: str, counter: str | None = None) -> None:
    if counter:
        st.session_state[counter] = st.session_state.get(counter, 0) + 1
    st.session_state["flash"] = message
    st.rerun()


companies = data.companies()
company_names = companies["name"].tolist()
# Plain ints: the database driver doesn't take numpy's.
company_ids = {name: int(i) for name, i in zip(companies["name"], companies["company_id"])}

section = sections("companies", ["Companies", "Contacts"])

# ---- companies --------------------------------------------------------------

if section == "Companies":
    if disclosure("Add a company", "add_company"):
        n = st.session_state.get("company_round", 0)
        with st.form(f"add_company_{n}"):
            name = st.text_input("Name")
            website = st.text_input("Website")
            industry_col, location_col = st.columns(2)
            industry = industry_col.text_input("Industry")
            location = location_col.text_input("Location")
            notes = st.text_area("Notes", placeholder="Why it's interesting, culture, pay…")
            added = st.form_submit_button("Add company", type="primary")
        if added:
            if not name.strip():
                st.error("Add the company's name.")
            elif name.strip().lower() in (c.lower() for c in company_names):
                st.error(f"{name.strip()} is already on the list.")
            else:
                data.add_company(name, today, website=website, industry=industry,
                                 location=location, notes=notes)
                done(f"Added {name.strip()}.", "company_round")

    if companies.empty:
        empty("domain", "No companies yet",
              "They're added for you with each application, or add one above.")
    else:
        st.dataframe(
            companies[["name", "industry", "location", "applications"]], hide_index=True,
            width="stretch",
            column_config={"name": "Company", "industry": "Industry", "location": "Location",
                           "applications": "Applications"})
        picked = st.selectbox("Edit a company", company_names, index=None,
                              placeholder="Choose one…", key=round_key("pick_company"))
        if picked:
            row = companies[companies["name"] == picked].iloc[0]
            company_id = int(row["company_id"])
            with st.form(f"edit_company_{company_id}"):
                e_name = st.text_input("Name", value=picked)
                e_website = st.text_input("Website", value=logic.value(row["website"]) or "")
                industry_col, location_col = st.columns(2)
                e_industry = industry_col.text_input(
                    "Industry", value=logic.value(row["industry"]) or "")
                e_location = location_col.text_input(
                    "Location", value=logic.value(row["location"]) or "")
                e_notes = st.text_area("Notes", value=logic.value(row["notes"]) or "")
                saved = st.form_submit_button("Save", type="primary")
            if saved:
                taken = {c.lower() for c in company_names} - {picked.lower()}
                if not e_name.strip():
                    st.error("The name can't be blank.")
                elif e_name.strip().lower() in taken:
                    st.error(f"{e_name.strip()} is already on the list.")
                else:
                    data.update_company(company_id, name=e_name, website=e_website,
                                        industry=e_industry, location=e_location,
                                        notes=e_notes)
                    if e_name.strip() != picked:
                        bump_round("pick_company")      # the old name is no longer a choice
                    done("Saved.")
            if delete_button("company", f"company_{company_id}"):
                try:
                    data.delete_company(company_id)
                except data.InUse as exc:
                    st.error(f"Can't delete: {exc}.")
                else:
                    bump_round("pick_company")
                    done(f"Deleted {picked}.")

# ---- contacts ---------------------------------------------------------------

if section == "Contacts":
    contacts = data.contacts()
    kinds = optional(config.CONTACT_KINDS)
    company_choices = optional(company_names)

    if disclosure("Add a contact", "add_contact"):
        n = st.session_state.get("contact_round", 0)
        with st.form(f"add_contact_{n}"):
            name = st.text_input("Name")
            title_col, kind_col = st.columns(2)
            title = title_col.text_input("Title")
            kind = kind_col.selectbox("Relationship", kinds)
            company = st.selectbox("Company", company_choices)
            email_col, phone_col = st.columns(2)
            email = email_col.text_input("Email")
            phone = phone_col.text_input("Phone")
            linkedin = st.text_input("LinkedIn")
            last = st.date_input("Last contacted", value=None)
            notes = st.text_area("Notes")
            added = st.form_submit_button("Add contact", type="primary")
        if added:
            if not name.strip():
                st.error("Add the contact's name.")
            else:
                data.add_contact(name, today, company_id=company_ids.get(company),
                                 title=title, kind=kind or None, email=email, phone=phone,
                                 linkedin=linkedin, last_contacted_on=last, notes=notes)
                done(f"Added {name.strip()}.", "contact_round")

    if contacts.empty:
        empty("group", "No contacts yet", "Recruiters, hiring managers and referrals go here.")
    else:
        st.dataframe(
            contacts[["name", "company", "title", "kind", "last_contacted_on"]],
            hide_index=True, width="stretch",
            column_config={
                "name": "Name", "company": "Company", "title": "Title",
                "kind": "Relationship",
                "last_contacted_on": st.column_config.DateColumn("Last contacted",
                                                                 format="MMM D, YYYY"),
            })
        labels = {int(r.contact_id): (f"{r.name} ({r.company})" if logic.value(r.company)
                                      else r.name) for r in contacts.itertuples()}
        picked = st.selectbox("Open a contact", list(labels), format_func=labels.get,
                              index=None, placeholder="Choose one…",
                              key=round_key("pick_contact"))
        if picked is not None:
            row = contacts[contacts["contact_id"] == picked].iloc[0]
            details = [logic.value(row[c]) for c in ("email", "phone", "linkedin")]
            if any(details):
                st.caption(md(" · ".join(d for d in details if d)))
            if st.button("Contacted today", key=f"contacted_{picked}"):
                data.update_contact(picked, last_contacted_on=today)
                done(f"Marked {row['name']} as contacted today.")
            with st.form(f"edit_contact_{picked}"):
                e_name = st.text_input("Name", value=row["name"])
                title_col, kind_col = st.columns(2)
                e_title = title_col.text_input("Title", value=logic.value(row["title"]) or "")
                e_kind = kind_col.selectbox("Relationship", kinds,
                                            index=index_of(kinds, logic.value(row["kind"])))
                e_company = st.selectbox(
                    "Company", company_choices,
                    index=index_of(company_choices, logic.value(row["company"])))
                email_col, phone_col = st.columns(2)
                e_email = email_col.text_input("Email", value=logic.value(row["email"]) or "")
                e_phone = phone_col.text_input("Phone", value=logic.value(row["phone"]) or "")
                e_linkedin = st.text_input("LinkedIn", value=logic.value(row["linkedin"]) or "")
                e_last = st.date_input("Last contacted",
                                       value=logic.value(row["last_contacted_on"]))
                e_notes = st.text_area("Notes", value=logic.value(row["notes"]) or "")
                saved = st.form_submit_button("Save", type="primary")
            if saved:
                if not e_name.strip():
                    st.error("The name can't be blank.")
                else:
                    data.update_contact(picked, name=e_name, title=e_title, kind=e_kind or None,
                                        company_id=company_ids.get(e_company), email=e_email,
                                        phone=e_phone, linkedin=e_linkedin,
                                        last_contacted_on=e_last, notes=e_notes)
                    done("Saved.")
            if delete_button("contact", f"contact_{picked}"):
                data.delete_contact(picked)
                bump_round("pick_contact")
                done(f"Deleted {row['name']}.")
