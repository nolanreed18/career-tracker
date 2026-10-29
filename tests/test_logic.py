"""The pure calculations: needs attention, stats, formatting, CSV import."""

from datetime import date, time

import pandas as pd
import pytest

import config
import logic

TODAY = date(2026, 10, 14)            # a Wednesday


def apps(*rows) -> pd.DataFrame:
    base = {"company": "Acme", "role": "Analyst", "status": "applied",
            "applied_on": date(2026, 10, 1), "next_action": None, "next_action_on": None,
            "last_update_on": date(2026, 10, 1), "source": None}
    return pd.DataFrame([{**base, "application_id": n + 1, **row} for n, row in enumerate(rows)])


def interviews(*rows) -> pd.DataFrame:
    columns = ["application_id", "scheduled_on", "start_time", "round", "company", "role",
               "status"]
    base = {"start_time": None, "round": None, "company": "Acme", "role": "Analyst",
            "status": "interviewing"}
    return pd.DataFrame([{**base, **row} for row in rows], columns=columns)


NONE = interviews()


# ---- needs attention --------------------------------------------------------

def test_quiet_for_the_follow_up_window_is_flagged():
    items = logic.needs_attention(
        apps({"last_update_on": date(2026, 9, 30)}), NONE, TODAY, follow_up_days=14)
    assert [(i.kind, i.detail) for i in items] == [
        ("follow_up", "No update in 14 days — follow up?")]


def test_a_day_short_of_the_window_is_not():
    assert logic.needs_attention(
        apps({"last_update_on": date(2026, 10, 1)}), NONE, TODAY, follow_up_days=14) == []


def test_the_default_window_is_the_configured_one():
    quiet = apps({"last_update_on": date(2026, 10, 14) - pd.Timedelta(
        days=config.FOLLOW_UP_DAYS).to_pytimedelta()})
    assert len(logic.needs_attention(quiet, NONE, TODAY)) == 1


def test_a_due_or_overdue_next_step_comes_first_and_replaces_the_follow_up():
    items = logic.needs_attention(apps(
        {"role": "Old", "last_update_on": date(2026, 8, 1)},
        {"role": "Due", "next_action": "Email Sam", "next_action_on": TODAY,
         "last_update_on": date(2026, 8, 1)},
        {"role": "Late", "next_action": None, "next_action_on": date(2026, 10, 11)},
    ), NONE, TODAY)
    assert [(i.kind, i.headline, i.detail) for i in items] == [
        ("overdue", "Acme — Late", "Next step: 3 days overdue"),
        ("due", "Acme — Due", "Email Sam: due today"),
        ("follow_up", "Acme — Old", "No update in 74 days — follow up?"),
    ]


def test_a_future_next_step_means_nothing_to_do_yet():
    items = logic.needs_attention(apps({"next_action_on": date(2026, 10, 20),
                                        "last_update_on": date(2026, 1, 1)}), NONE, TODAY)
    assert items == []


def test_closed_applications_never_appear():
    rows = [{"status": s, "last_update_on": date(2026, 1, 1), "next_action_on": TODAY}
            for s in config.CLOSED_STATUSES]
    assert logic.needs_attention(apps(*rows), NONE, TODAY) == []


def test_saved_and_offer_get_their_own_wording():
    items = logic.needs_attention(apps(
        {"status": "saved", "applied_on": None, "last_update_on": date(2026, 9, 1)},
        {"status": "offer", "role": "Lead", "last_update_on": date(2026, 9, 20)},
    ), NONE, TODAY)
    assert [(i.kind, i.detail) for i in items] == [
        ("follow_up", "Offer open for 24 days — time to decide?"),
        ("stale_saved", "Saved 43 days ago — apply or drop it?"),
    ]


def test_upcoming_interviews_show_and_hold_off_the_follow_up():
    items = logic.needs_attention(
        apps({"last_update_on": date(2026, 9, 1)}),
        interviews({"application_id": 1, "scheduled_on": date(2026, 10, 15),
                    "start_time": time(14, 30), "round": "Onsite"}),
        TODAY)
    assert [(i.kind, i.detail) for i in items] == [("interview", "Onsite, tomorrow at 2:30 pm")]


def test_interviews_past_the_lookahead_are_not_listed_but_still_count():
    items = logic.needs_attention(
        apps({"last_update_on": date(2026, 9, 1)}),
        interviews({"application_id": 1, "scheduled_on": date(2026, 10, 30)}),
        TODAY, lookahead_days=7)
    assert items == []


def test_a_recent_past_interview_counts_as_an_update():
    recent = interviews({"application_id": 1, "scheduled_on": date(2026, 10, 10)})
    old = interviews({"application_id": 1, "scheduled_on": date(2026, 9, 10)})
    quiet = apps({"last_update_on": date(2026, 9, 1)})
    assert logic.needs_attention(quiet, recent, TODAY) == []
    assert [i.kind for i in logic.needs_attention(quiet, old, TODAY)] == ["follow_up"]


# ---- stats ------------------------------------------------------------------

def events(*rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["application_id", "status"])


def test_pipeline_counts_every_status_in_order():
    pipe = logic.pipeline(apps({"status": "applied"}, {"status": "applied"},
                               {"status": "offer"}))
    assert pipe["status"].tolist() == config.STATUSES
    assert dict(zip(pipe["status"], pipe["applications"]))["applied"] == 2


def test_weekly_counts_by_monday_with_zero_weeks():
    weekly = logic.weekly_applications(apps(
        {"applied_on": date(2026, 10, 12)}, {"applied_on": date(2026, 10, 14)},
        {"applied_on": date(2026, 10, 4)}, {"applied_on": None, "status": "saved"},
        {"applied_on": date(2025, 1, 1)},
    ), TODAY, weeks=3)
    assert weekly["week"].tolist() == [date(2026, 9, 28), date(2026, 10, 5), date(2026, 10, 12)]
    assert weekly["applications"].tolist() == [1, 0, 2]


def test_response_rate_counts_anything_that_reached_a_screen():
    frame = apps({"status": "rejected"}, {"status": "applied"}, {"status": "interviewing"},
                 {"status": "saved"})
    # 1 was screened before being rejected; 4 is only saved and isn't counted.
    assert logic.response_rate(frame, events((1, "applied"), (1, "screening"),
                                             (1, "rejected"))) == (2, 3)
    assert logic.response_rate(apps(), events()) == (0, 0)
    # 2 never had a screening event but an interview is on record: a response
    # (1 was screened, 3 is interviewing, so all three sent ones responded).
    interviews = pd.DataFrame({"application_id": [2]})
    assert logic.response_rate(frame, events((1, "screening")), interviews) == (3, 3)
    assert logic.by_source(frame, events(), interviews)["responded"].sum() == 2    # 2 and 3


def test_by_source():
    frame = apps({"source": "LinkedIn", "status": "applied"},
                 {"source": "LinkedIn", "status": "screening"},
                 {"source": "Referral", "status": "offer"},
                 {"source": None, "status": "applied"})
    table = logic.by_source(frame, events())
    assert table.values.tolist() == [
        ["LinkedIn", 2, 1, 0.5], ["(not set)", 1, 0, 0.0], ["Referral", 1, 1, 1.0]]


# ---- formatting -------------------------------------------------------------

def test_salary_range():
    assert logic.salary_range(90000, 110000) == "$90,000–$110,000"
    assert logic.salary_range(90000, None) == "$90,000+"
    assert logic.salary_range(float("nan"), 120000) == "up to $120,000"
    assert logic.salary_range(None, None) == ""


def test_when_and_clock():
    assert logic.when(TODAY, TODAY) == "today"
    assert logic.when(date(2026, 10, 20), TODAY) == "Tue Oct 20"
    assert logic.clock(time(0, 5)) == "12:05 am"
    assert logic.clock(time(12, 0)) == "12:00 pm"


# ---- import -----------------------------------------------------------------

def test_import_matches_loose_headers_and_reads_values():
    frame = pd.DataFrame([{
        "Company Name": " Acme ", "Job_Title": "Data Analyst", "Stage": "Phone Screen",
        "Date Applied": "10/01/2026", "Salary": "$90k - $110K", "Work-Mode": "Remote (US)",
        "Notes": "", "Unrelated": "x",
    }])
    rows, problems = logic.map_import(frame)
    assert problems == []
    assert rows == [{
        "company": "Acme", "role": "Data Analyst", "status": "screening",
        "applied_on": date(2026, 10, 1), "job_url": None, "location": None,
        "work_mode": "remote", "source": None, "salary_min": 90000, "salary_max": 110000,
        "notes": None,
    }]


def test_import_explains_what_it_skipped_or_guessed():
    frame = pd.DataFrame([
        {"Company": "Acme", "Role": "", "Status": "applied", "Applied": ""},
        {"Company": "Beta", "Role": "PM", "Status": "maybe?", "Applied": "not a date"},
        {"Company": "", "Role": "", "Status": "", "Applied": ""},
    ])
    rows, problems = logic.map_import(frame)
    assert [(r["company"], r["status"], r["applied_on"]) for r in rows] == [
        ("Beta", "saved", None)]
    assert problems == [
        "Row 2: skipped — needs both a company and a role.",
        "Row 3: couldn't read the date “not a date”; left blank.",
        "Row 3: unknown status “maybe?”; set to saved.",
    ]


def test_import_needs_company_and_role_columns():
    rows, problems = logic.map_import(pd.DataFrame([{"Name": "x"}]))
    assert rows == [] and len(problems) == 2


def test_parse_salary():
    assert logic.parse_salary("95,500") == (95500, None)
    assert logic.parse_salary("120k") == (120000, None)
    assert logic.parse_salary("competitive") == (None, None)


# ---- job leads --------------------------------------------------------------

def test_the_same_job_gets_the_same_key_whatever_the_site_or_city():
    a = logic.lead_key("Acme, Inc.", "Senior Data Analyst")
    b = logic.lead_key("acme inc", "Senior  Data Analyst ")
    assert a == b == "acme inc|senior data analyst"
    assert logic.lead_key("Acme", "Analyst") != logic.lead_key("Acme", "Senior Analyst")
    lead, _ = logic.clean_lead({"source": "Dice", "title": "Analyst", "company": "Acme",
                                "location": "Denver, CO"})
    other, _ = logic.clean_lead({"source": "LinkedIn", "title": "Analyst", "company": "ACME",
                                 "location": "Denver Metropolitan Area"})
    assert lead["dedupe_key"] == other["dedupe_key"] == "acme|analyst"


def test_stale_leads_are_the_old_ones_still_sitting_there():
    today = date(2026, 10, 19)
    assert logic.is_stale(date(2026, 10, 4), today) and not logic.is_stale(date(2026, 10, 5), today)
    assert not logic.is_stale(None, today)
    frame = pd.DataFrame({"title": ["old", "new"], "found_on": [date(2026, 9, 1), today]})
    fresh, stale = logic.split_stale(frame, today)
    assert fresh["title"].tolist() == ["new"] and stale["title"].tolist() == ["old"]
    empty = pd.DataFrame(columns=["title", "found_on"])
    assert all(f.empty for f in logic.split_stale(empty, today))


def test_companies_to_skip_match_however_the_site_writes_them():
    skip = logic.skip_list("Robert Half\nTEKsystems, Insight Global;\n")
    assert skip == ["robert half", "teksystems", "insight global"]
    assert logic.skips_company("Robert Half Technology", skip)
    assert logic.skips_company("TEKSYSTEMS, Inc.", skip)
    assert not logic.skips_company("Halfway House", skip)
    assert not logic.skips_company("Acme", []) and logic.skip_list(None) == []


def test_dismissal_notes_are_plain_records():
    frame = pd.DataFrame([{"title": "Clerk", "company": "Acme", "location": None,
                           "dismiss_reason": "wrong role", "dismissed_on": date(2026, 10, 18)}])
    assert logic.dismissal_notes(frame) == [{
        "title": "Clerk", "company": "Acme", "location": None, "reason": "wrong role",
        "dismissed_on": "2026-10-18"}]


def test_a_lead_is_cleaned_for_the_database():
    lead, problem = logic.clean_lead({
        "source": "Indeed", "title": " Data Analyst ", "company": "Acme",
        "location": "Remote (US)", "work_mode": "Remote", "salary": "$140k - $120k",
        "posted_on": "2026-10-12", "fit_score": "8", "fit_reason": "SQL-heavy, remote",
        "job_url": "https://example.com/j/1"})
    assert problem is None
    assert lead["title"] == "Data Analyst" and lead["work_mode"] == "remote"
    assert (lead["salary_min"], lead["salary_max"]) == (120000, 140000)
    assert lead["posted_on"] == date(2026, 10, 12) and lead["fit_score"] == 8
    assert lead["dedupe_key"] == "acme|data analyst"


def test_a_lead_without_a_company_or_with_a_bad_score_is_refused():
    assert logic.clean_lead({"source": "Dice", "title": "Analyst"})[0] is None
    assert logic.clean_lead({"source": "Dice", "title": "A", "company": "B",
                             "fit_score": 11})[0] is None
    assert logic.clean_lead({"source": "Dice", "title": "A", "company": "B",
                             "fit_score": "great"})[0] is None
    lead, _ = logic.clean_lead({"source": "Dice", "title": "A", "company": "B"})
    assert lead["fit_score"] is None and lead["salary_min"] is None


def test_fit_total_is_the_weighted_average_to_one_decimal_capped_by_a_deal_breaker():
    assert sum(w for _, w, _ in config.FIT_CATEGORIES.values()) == pytest.approx(1)
    tens = {k: 10 for k in config.FIT_CATEGORIES}
    assert logic.fit_total(tens) == 10
    assert logic.fit_total({"role": 9, "industry": 6, "location": 10, "pay": 8, "level": 7,
                            "extras": 6}) == 8.1
    assert logic.fit_total({"role": 8, "pay": 4}) == 6.8          # missing ones left out
    assert logic.fit_total(tens, deal_breaker=True) == config.DEAL_BREAKER_CAP
    assert logic.fit_total({"role": 2}, deal_breaker=True) == 2
    assert logic.fit_total({}) is None
    assert logic.fit_text(9) == "9" and logic.fit_text(8.3) == "8.3" and logic.fit_text(None) == ""


def test_clean_lead_scores_from_category_ratings():
    row = {"source": "Dice", "title": "A", "company": "B", "salary": "$150k",
           "fit": {"role": 9, "industry": 6, "location": 10, "pay": 8, "level": 7, "extras": 6},
           "deal_breaker": False}
    lead, problem = logic.clean_lead(row)
    assert problem is None and lead["fit_score"] == 8.1
    assert lead["fit_detail"] == {"ratings": row["fit"], "deal_breaker": False}
    capped, _ = logic.clean_lead({**row, "deal_breaker": "true"})
    assert capped["fit_score"] == config.DEAL_BREAKER_CAP
    assert capped["fit_detail"]["deal_breaker"] is True
    base = {"source": "Dice", "title": "A", "company": "B"}
    assert logic.clean_lead({**base, "fit": {"vibes": 9}})[0] is None
    assert logic.clean_lead({**base, "fit": {"role": 11}})[0] is None
    assert logic.clean_lead({**base, "fit": {"role": "great"}})[0] is None
    assert logic.clean_lead({**base, "fit": [9]})[0] is None
    plain, _ = logic.clean_lead({**base, "fit_score": "7.5"})     # the old way still works
    assert plain["fit_score"] == 7.5 and plain["fit_detail"] is None


def test_for_display_blanks_missing_text_and_keeps_dates():
    frame = pd.DataFrame({"name": ["Acme", "Beta"], "industry": [None, "Energy"],
                          "applied_on": [date(2026, 10, 1), None], "n": [1.0, None]})
    shown = logic.for_display(frame, dates=("applied_on",))
    assert shown["industry"].tolist() == ["", "Energy"]
    assert shown["applied_on"].dt.date.tolist()[0] == date(2026, 10, 1)
    assert pd.isna(shown["applied_on"].iloc[1]) and pd.isna(shown["n"].iloc[1])
    assert pd.isna(frame["industry"].iloc[0])                     # the original is untouched


def test_fit_tiers():
    assert logic.fit_tier(config.STRONG_FIT) == "strong"
    assert logic.fit_tier(config.MAYBE_FIT) == "maybe"
    assert logic.fit_tier(config.MAYBE_FIT - 1) == "weak"
    assert logic.fit_tier(None) is None


def test_weak_is_below_the_maybe_line_and_unscored_is_not_weak():
    assert logic.is_weak(config.MAYBE_FIT - 1)
    assert not logic.is_weak(config.MAYBE_FIT)
    assert not logic.is_weak(None)


def test_a_rebuilt_glassdoor_link_becomes_the_form_glassdoor_serves():
    fixed = "https://www.glassdoor.com/partner/jobListing.htm?jobListingId=1010293120973"
    assert logic.job_link("https://www.glassdoor.com/job-listing?jl=1010293120973") == fixed
    assert logic.job_link("https://glassdoor.com/job-listing/?jl=1010293120973") == fixed
    real = ("https://www.glassdoor.com/partner/jobListing.htm?pos=101&jobListingId=1"
            "&utm_source=jobalert")
    assert logic.job_link(real) == fixed.replace("1010293120973", "1")   # tracking dropped
    wrapped = ("https://www.google.com/url?q=https://www.linkedin.com/comm/jobs/view/4477910397"
               "?alertAction%3Dmarkasviewed%26savedSearchId%3D162%26trk%3Dx&source=gmail")
    assert logic.job_link(wrapped) == "https://www.linkedin.com/jobs/view/4477910397/"
    assert logic.job_link("https://www.linkedin.com/jobs/view/123?refId=x") == (
        "https://www.linkedin.com/jobs/view/123/")
    assert logic.job_link("https://www.indeed.com/viewjob?jk=abc123&from=ja&tk=z") == (
        "https://www.indeed.com/viewjob?jk=abc123")
    assert logic.job_link("https://engage.indeed.com/f/a/uZGm19L7") == (
        "https://engage.indeed.com/f/a/uZGm19L7")                         # opaque: as it is
    assert logic.job_link("https://boards.greenhouse.io/x/jobs/1?gh_src=a") == (
        "https://boards.greenhouse.io/x/jobs/1?gh_src=a")
    assert logic.job_link(" https://example.com/j/1 ") == "https://example.com/j/1"
    assert logic.job_link(None) is None
    lead, _ = logic.clean_lead({"source": "Glassdoor", "title": "A", "company": "B",
                                "job_url": "https://www.glassdoor.com/job-listing?jl=5"})
    assert lead["job_url"].endswith("jobListingId=5")       # fixed on the way in, too


def test_pay_is_rated_only_against_a_salary_and_estimates_say_where_from():
    base = {"source": "Dice", "title": "A", "company": "B"}
    listed, _ = logic.clean_lead({**base, "salary": "$120k-$140k", "fit": {"role": 8, "pay": 7}})
    assert listed["pay_source"] == "listed" and listed["pay_note"] is None
    estimate, _ = logic.clean_lead({**base, "salary": "$120k-$140k", "pay_source": "Estimated",
                                    "pay_note": " Glassdoor, Denver ", "fit": {"pay": 7}})
    assert (estimate["pay_source"], estimate["pay_note"]) == ("estimated", "Glassdoor, Denver")
    unknown, _ = logic.clean_lead({**base, "fit": {"role": 8, "level": 6}})
    assert unknown["pay_source"] is None and unknown["fit_score"] == 7.6
    lead, problem = logic.clean_lead({**base, "fit": {"role": 8, "pay": 5}})
    assert lead is None and "leave pay out" in problem
    assert logic.clean_lead({**base, "salary": "$100k", "pay_source": "guessed"})[0] is None
    assert logic.clean_lead({**base, "salary": "$100k", "pay_source": "estimated"})[0] is None
    assert logic.clean_lead({**base, "pay_source": "listed"})[0] is None


def test_pay_state_tells_listed_estimated_and_unknown_apart():
    assert logic.pay_state(120000, 140000, "listed") == ("listed", "$120,000–$140,000")
    assert logic.pay_state(120000, None, "estimated") == ("estimated", "~$120,000+")
    assert logic.pay_state(None, None, None) == ("unknown", "Pay not listed")
    assert logic.pay_state(None, float("nan"), "listed") == ("unknown", "Pay not listed")


def test_without_pay_rescores_a_lead_rated_before_its_pay_was_known():
    detail = {"ratings": {"role": 8, "industry": 4, "pay": 5}, "deal_breaker": False}
    assert logic.without_pay(detail) == (6.5, {"ratings": {"role": 8, "industry": 4},
                                               "deal_breaker": False})
    assert logic.without_pay({"ratings": {"pay": 5}})[0] is None
    assert logic.without_pay({"ratings": {"role": 9, "pay": 2}, "deal_breaker": True})[0] == 3


def test_a_projects_spreadsheet_becomes_text_for_claude():
    frame = pd.DataFrame([
        {"Company": "FHR", "ProjectTitle": "USMCA Tool", "QuickSummary": "Compliance checks.",
         "QualityRank": 5, "Situation": "Manual tracking.", "Task": "Automate it.",
         "Action": "Built Alteryx + SQL.", "Result": "Zero misses.", "HardSkills": '["Alteryx"]'},
        {"Company": "FHR", "ProjectTitle": None, "QuickSummary": "skipped: no title"},
    ])
    text = logic.projects_text(frame)
    assert text.startswith("Project: USMCA Tool\nCompany: FHR\nRank: 5\nSummary: Compliance checks.")
    assert "Result: Zero misses." in text and "skipped" not in text
    assert logic.projects_text(pd.DataFrame(columns=["ProjectTitle"])) == ""


def test_clean_resume_tidies_and_counts():
    content = {
        "name": " Sample ", "email": "s@example.com ", "phone": "", "linkedin": "",
        "roles": [{"employer": " Acme ", "title": "Analyst", "location": "Denver", "start": "2025",
                   "end": "Present", "bullets": [
                       {"text": "  Did   x  ", "skills": [" SQL ", ""], "source": "", "rank": 9,
                        "in_master": True},
                       {"text": "   ", "skills": [], "source": "resume", "rank": 3,
                        "in_master": True}]},
                  {"employer": "  ", "title": "", "location": "", "start": "", "end": "",
                   "bullets": []}],
        "projects": [], "education": [{"school": "", "when": "", "degree": ""}],
        "skill_groups": [{"name": "Languages", "skills": "Python"}], "conflicts": [],
    }
    cleaned = logic.clean_resume(content)
    assert cleaned["name"] == "Sample" and len(cleaned["roles"]) == 1
    bullet = cleaned["roles"][0]["bullets"]
    assert bullet == [{"text": "Did x", "skills": ["SQL"], "source": "manual",
                       "rank": config.BULLET_RANK_MAX, "in_master": True}]
    assert cleaned["education"] == [] and len(cleaned["skill_groups"]) == 1
    assert logic.resume_counts(cleaned) == {"roles": 1, "projects": 0, "master_roles": 1,
                                            "master_projects": 0, "master_bullets": 1,
                                            "pool_bullets": 0}
    assert not logic.prints({"bullets": [{"in_master": False}]}) and not logic.prints({})
    assert logic.skills_text(["A", "B"]) == "A, B" and logic.skills_list(" A, B ,") == ["A", "B"]
    assert logic.month_start(date(2026, 10, 19)) == date(2026, 10, 1)


def test_a_tailored_resume_is_cleaned_counted_and_exported_in_the_masters_shape():
    tailored = {
        "fit_notes": " Strong on SQL. ", "roles": [
            {"employer": " Acme ", "title": "Analyst", "location": "Denver", "start": "Jan 2025",
             "end": "Present", "bullets": [
                 {"text": "  Did x  for finance ", "original": "Did x", "skills": [" SQL ", ""]},
                 {"text": "Did y", "original": "Did y", "skills": []},
                 {"text": "   ", "original": "Did z", "skills": []},
                 {"text": "New one", "original": "", "skills": []}]},
            {"employer": "Beta", "title": "PM", "location": "", "start": "", "end": "",
             "bullets": []}],
        "projects": [], "skill_groups": [{"name": "Languages", "skills": "SQL, Python"},
                                         {"name": " ", "skills": "x"}],
        "keywords": [{"term": "SQL", "covered": True, "where": "Did x"},
                     {"term": "Tableau", "covered": False, "where": ""},
                     {"term": " ", "covered": False, "where": ""}],
        "changes": [" Reworded Did x. ", ""], "cover_letter": " Dear Team,\n\nI did x. ",
    }
    cleaned = logic.clean_tailored(tailored)
    assert [r["employer"] for r in cleaned["roles"]] == ["Acme"]      # Beta had no bullets
    assert [b["text"] for b in cleaned["roles"][0]["bullets"]] == ["Did x for finance", "Did y",
                                                                   "New one"]
    assert cleaned["roles"][0]["bullets"][0]["skills"] == ["SQL"]
    assert len(cleaned["skill_groups"]) == 1 and len(cleaned["keywords"]) == 2
    assert cleaned["changes"] == ["Reworded Did x."] and cleaned["fit_notes"] == "Strong on SQL."
    assert logic.tailored_counts(cleaned) == {"bullets": 3, "kept": 1, "reworded": 1,
                                              "unmatched": 1, "keywords": 2, "covered": 1}
    master = {"name": "Sample", "email": "s@example.com", "phone": "", "linkedin": "in/s",
              "education": [{"school": "U", "when": "2020", "degree": "BS"}],
              "roles": [{"employer": "Old"}], "skill_groups": [{"name": "Old", "skills": "x"}]}
    export = logic.tailored_export(master, cleaned)
    assert export["name"] == "Sample" and export["education"] == master["education"]
    assert [r["employer"] for r in export["roles"]] == ["Acme"]
    assert export["roles"][0]["bullets"][0] == {"text": "Did x for finance", "skills": ["SQL"],
                                                "source": "tailored", "rank": 3,
                                                "in_master": True}
    assert export["skill_groups"] == [{"name": "Languages", "skills": "SQL, Python"}]
    assert logic.clean_resume(export)["roles"][0]["bullets"][0]["in_master"]   # printable
    assert logic.letter_paragraphs(cleaned["cover_letter"]) == ["Dear Team,", "I did x."]
    assert logic.letter_paragraphs("Hi,\r\n\r\nOne  two\nthree.\n\n\nSincerely,\nSam\n") == [
        "Hi,", "One two\nthree.", "Sincerely,\nSam"]                 # a line break kept
    assert logic.file_stem("Nolan Hughes", "Resume", "Acme Corp.") == "NolanHughes_Resume_AcmeCorp"
    assert logic.file_stem("", "") == "Resume"


def test_roles_print_newest_first_when_every_start_is_a_month():
    assert logic.parse_month("Jan 2025") == date(2025, 1, 1)
    assert logic.parse_month("September 2023") == date(2023, 9, 1)
    assert logic.parse_month("late 2024") is None and logic.parse_month("") is None
    roles = [{"employer": "A", "start": "Jan 2025"}, {"employer": "C", "start": "Jun 2022"},
             {"employer": "B", "start": "Jan 2024"}, {"employer": "B2", "start": "Jan 2024"}]
    assert [r["employer"] for r in logic.roles_by_date(roles)] == ["A", "B", "B2", "C"]
    vague = roles + [{"employer": "D", "start": "late 2024"}]
    assert logic.roles_by_date(vague) == vague                     # one vague date: as given
    assert logic.roles_by_date([]) == []


def test_a_tailored_version_is_measured_against_the_master_and_ends_bullets_its_way():
    master = {"roles": [{"bullets": [{"text": "Did x.", "in_master": True},
                                     {"text": "Did y.", "in_master": True},
                                     {"text": "Pool bullet", "in_master": False}]}],
              "projects": [{"bullets": [{"text": "Made z", "in_master": True}]}]}
    assert logic.master_budget(master) == {"roles": {"bullets": 2, "characters": 12},
                                           "projects": {"bullets": 1, "characters": 6}}
    tailored = {"roles": [{"bullets": [{"text": "Did x for finance"}, {"text": "Did y."}]}],
                "projects": [{"bullets": [{"text": "Made z!"}]}]}
    ended = logic.match_endings(tailored, master)                  # most master bullets end "."
    assert [b["text"] for b in ended["roles"][0]["bullets"]] == ["Did x for finance.", "Did y."]
    assert ended["projects"][0]["bullets"][0]["text"] == "Made z!"
    bare = {"roles": [{"bullets": [{"text": "Did x", "in_master": True},
                                   {"text": "Did y", "in_master": True}]}]}
    stripped = logic.match_endings(tailored, bare)
    assert [b["text"] for b in stripped["roles"][0]["bullets"]] == ["Did x for finance", "Did y"]
    assert logic.match_endings(tailored, {"roles": []}) == tailored
    assert logic.place("Remote", "remote") == ["Remote"]
    assert logic.place("Denver, CO", "hybrid") == ["Denver, CO", "Hybrid"]
    assert logic.place("Plainview, TX", "remote") == ["Plainview, TX", "Remote"]
    assert logic.place(None, "onsite") == ["Onsite"] and logic.place("", None) == []


def test_application_labels_are_company_dash_role_by_plain_id():
    apps = pd.DataFrame({"application_id": [7], "company": ["Acme"], "role": ["Analyst"]})
    labels = logic.application_labels(apps)
    assert labels == {7: "Acme — Analyst"} and type(next(iter(labels))) is int


def test_a_job_board_link_is_told_from_an_employers_own_site():
    assert logic.is_job_board("https://www.linkedin.com/jobs/view/1/")
    assert logic.is_job_board("https://www.indeed.com/viewjob?jk=1") and logic.is_job_board("https://builtin.com/job/1")
    assert not logic.is_job_board("https://bp.wd3.myworkdayjobs.com/en-US/bpx/job/R1")
    assert not logic.is_job_board("https://boards.greenhouse.io/acme/jobs/1") and not logic.is_job_board(None)


def test_dismiss_reasons_are_split_from_their_stored_form():
    assert logic.dismiss_reasons("wrong role, too much travel") == ["wrong role", "too much travel"]
    assert logic.dismiss_reasons("pay") == ["pay"] and logic.dismiss_reasons(None) == []


def test_application_labels_mark_the_ones_with_a_tailored_resume():
    apps = pd.DataFrame({"application_id": [1, 2], "company": ["Acme", "Beta"],
                         "role": ["Analyst", "PM"], "tailored": [2, 0]})
    assert logic.application_labels(apps) == {1: "Acme — Analyst · resume ready", 2: "Beta — PM"}


def test_a_column_of_roles_is_counted_in_lines_the_way_the_template_lays_it_out():
    roles = [{"employer": "A", "title": "T1", "bullets": [{"text": "x" * 150}, {"text": "y" * 76}]},
             {"employer": "A", "title": "T2", "bullets": [{"text": "z" * 75}]},
             {"employer": "B", "title": "T3", "bullets": []}]
    # A once, two title lines, 2 + 2 + 1 lines of bullets; B prints nothing
    assert logic.column_lines(roles, 75) == 1 + 1 + 4 + 1 + 1
    assert logic.column_lines([], 75) == 0
    assert logic.printed_roles([{"employer": "A", "bullets": [
        {"text": "on", "in_master": True}, {"text": "pool", "in_master": False}]},
        {"employer": "B", "bullets": [{"text": "pool", "in_master": False}]}]) == [
        {"employer": "A", "bullets": [{"text": "on", "in_master": True}]}]


def test_a_tailored_version_is_trimmed_to_the_masters_experience_column():
    master = {"roles": [
        {"employer": "A", "title": "T1", "bullets": [{"text": "a" * 150, "in_master": True},
                                                     {"text": "b" * 150, "in_master": True},
                                                     {"text": "pool", "in_master": False}]},
        {"employer": "B", "title": "T2", "bullets": [{"text": "c" * 60, "in_master": True}]}]}
    assert logic.column_lines(logic.printed_roles(master["roles"]), 75) == 9
    over = {"roles": [
        {"employer": "A", "title": "T1", "bullets": [{"text": "Kept first " * 13},
                                                     {"text": "Kept second " * 12},
                                                     {"text": "The least relevant bullet " * 5}]},
        {"employer": "B", "title": "T2", "bullets": [{"text": "d" * 60}]}],
        "changes": ["Reworded a bullet."]}
    assert logic.column_lines(over["roles"], 75) == 11
    fitted = logic.fit_column(over, master, 75)
    assert [len(r["bullets"]) for r in fitted["roles"]] == [2, 1]           # A's last went
    assert fitted["changes"] == ["Reworded a bullet.", "Left off the last bullet under A "
                                 "(“The least relevant bullet The least relevant bullet The…”): "
                                 "the experience column was full."]
    assert [len(r["bullets"]) for r in over["roles"]] == [3, 1]             # the input untouched
    assert logic.fit_column(fitted, master, 75) == fitted                   # fits: unchanged
    # the first role keeps a bullet however long; a role left with none goes
    tall = {"roles": [{"employer": "A", "title": "T1", "bullets": [{"text": "e" * 300}]},
                      {"employer": "B", "title": "T2", "bullets": [{"text": "f" * 300}]}]}
    assert [r["employer"] for r in logic.fit_column(tall, master, 75)["roles"]] == ["A"]
    assert logic.fit_column({"roles": tall["roles"][:1]}, master, 75)["roles"] == tall["roles"][:1]
    assert logic.fit_column({}, master, 75) == {"changes": [], "roles": []}


def test_shorten_cuts_at_a_word():
    assert logic.shorten("Built and manage the system", 12) == "Built and…"
    assert logic.shorten("Built and manage the system", 40) == "Built and manage the system"
    assert logic.shorten("  spaced   out  ", 40) == "spaced out"
    assert logic.shorten("Unbroken" * 3, 10) == "UnbrokenUn…"


# ---- project bank ---------------------------------------------------------------

FULL_PROJECT = {"situation": "Schedulers rebuilt freight rates by hand every week from emails.",
                "task": "Own the rates tool end to end.",
                "action": "Rebuilt the VBA tool as a Python web app with validation, an "
                          "audit trail and accounting integration, moved the data to MySQL, "
                          "then trained the schedulers.",
                "result": "Cut rate updates from 6 hours to 20 minutes a week.",
                "skills": "Python, Panel, MySQL", "bullet": "Rebuilt the freight-rate tool "
                                                             "in Python, cutting updates 90%"}


def test_a_projects_detail_score_says_what_is_missing():
    full = logic.project_detail(FULL_PROJECT)
    assert full == {"score": 100, "missing": [], "level": "strong"}
    empty = logic.project_detail({})
    assert (empty["score"], empty["level"], len(empty["missing"])) == (0, "weak", 7)
    no_number = logic.project_detail({**FULL_PROJECT, "result": "Schedulers trust the rates "
                                                                "now and stopped rebuilding them."})
    assert (no_number["score"], no_number["level"]) == (85, "strong")
    assert no_number["missing"] == ["a number in the result: hours, $, %, users"]
    thin = logic.project_detail({**FULL_PROJECT, "task": None, "result": float("nan"),
                                 "skills": "Python"})
    assert (thin["score"], thin["level"]) == (45, "weak")      # NaN and None count as empty
    assert logic.project_detail({**FULL_PROJECT, "action": "Built it.", "bullet": ""}) == {
        "score": 70, "level": "thin",
        "missing": ["what you did and how (Action)", "a resume bullet"]}


def test_a_short_company_name_finds_its_employer_on_the_master():
    employers = ["Flint Hills Resources (Koch, Inc.)", "Chevron Phillips Chemical Company LLC"]
    assert logic.match_employer("FHR", employers) == employers[0]
    assert logic.match_employer("CPChem", employers) == employers[1]
    assert logic.match_employer("koch", employers) == employers[0]          # part of the name
    assert logic.match_employer("Chevron Phillips Chemical Company LLC", employers) == employers[1]
    assert logic.match_employer("HR", employers) is None                    # not from the start
    assert logic.match_employer("Acme", employers) is None
    assert logic.match_employer(None, employers) is None


PROJECTS_TEXT = """Project: Freight rates
Company: FHR
Rank: 5
Summary: The rates tool
Situation: Rates came by email.
Schedulers retyped them.
Action: Built a Python app.
Result: 6 hours to 20 minutes a week.
Skills: Python, MySQL

Project: Fitness tracker
Summary: A workout planner
Action: Built it in VBA.

Project: Valve study
Company: Acme Valves
Situation: Leaks."""


def test_the_projects_spreadsheets_text_reads_back_into_projects():
    found = logic.parse_projects_text(PROJECTS_TEXT)
    assert [f["title"] for f in found] == ["Freight rates", "Fitness tracker", "Valve study"]
    assert found[0]["situation"] == "Rates came by email.\nSchedulers retyped them."
    assert found[0]["employer"] == "FHR" and "rank" not in found[0]
    assert found[1]["action"] == "Built it in VBA." and "employer" not in found[1]
    assert logic.parse_projects_text("") == [] and logic.parse_projects_text(None) == []
    master = {"roles": [{"employer": "Flint Hills Resources (Koch, Inc.)", "bullets": []}]}
    ready = logic.import_projects(PROJECTS_TEXT, master, ["fitness tracker"])   # one is in
    assert [(p["title"], p["employer"], p["kind"]) for p in ready] == [
        ("Freight rates", "Flint Hills Resources (Koch, Inc.)", "work"),
        ("Valve study", "Acme Valves", "work")]                  # kept as written when unknown
    assert logic.import_projects(PROJECTS_TEXT, None, [])[1]["kind"] == "personal"
    assert logic.master_employers({"roles": [{"employer": "A"}, {"employer": "B"},
                                             {"employer": "A"}]}) == ["A", "B"]


def test_a_projects_bullet_goes_into_the_masters_pool_where_it_belongs():
    master = {"roles": [
        {"employer": "Acme", "title": "Engineer", "start": "Jun 2023", "end": "Dec 2024",
         "bullets": [{"text": "Old work.", "in_master": True}]},
        {"employer": "Acme", "title": "Analyst", "start": "Jan 2025", "end": "Present",
         "bullets": [{"text": "Built a pipeline.", "in_master": False}]}],
        "projects": [{"employer": "Fitness tracker", "bullets": []}]}
    work = {"title": "Rates", "employer": "Acme", "skills": "Python, SQL"}
    added, where = logic.add_to_master(master, work, "  Rebuilt the rates tool. ", 4)
    assert where == "Acme — Analyst"                                       # the newest role
    assert added["roles"][1]["bullets"][-1] == {"text": "Rebuilt the rates tool.",
                                                "skills": ["Python", "SQL"], "source": "project",
                                                "rank": 4, "in_master": False}
    assert len(master["roles"][1]["bullets"]) == 1                          # the input untouched
    assert logic.bullet_status(added, "rebuilt the  rates tool.") == "in the pool"
    assert logic.bullet_status(added, "Old work.") == "on the master"
    assert logic.bullet_status(added, "Something else") is None
    assert logic.add_to_master(added, work, "Rebuilt the rates tool.", 4)[1] == "already"
    assert logic.add_to_master(master, {**work, "employer": "Beta"}, "x", 3)[1] == ""
    personal, where = logic.add_to_master(master, {"title": "Fitness tracker"}, "Built it.", 3)
    assert where == "Fitness tracker" and personal["projects"][0]["bullets"][0]["text"] == "Built it."
    fresh, where = logic.add_to_master(master, {"title": "Budget app"}, "Built a budget.", 3)
    assert where == "Budget app" and fresh["projects"][-1]["employer"] == "Budget app"
    assert [logic.project_rank(s) for s in (1, 5, 8, 10, None, "x")] == [1, 2, 4, 5, 3, 3]


def test_bullet_style_samples_the_newest_roles_printed_bullets():
    master = {"roles": [
        {"employer": "Old", "start": "Jan 2020", "bullets": [{"text": "x" * 300,
                                                               "in_master": True}]},
        {"employer": "New", "start": "Jan 2025", "bullets": [
            {"text": "a" * 100, "in_master": True}, {"text": "pool", "in_master": False},
            {"text": "b" * 200, "in_master": True}]}], "projects": []}
    style = logic.bullet_style(master)
    assert style == {"samples": ["a" * 100, "b" * 200], "typical": 200, "longest": 300}
    assert logic.bullet_style(None) == {"samples": [], "typical": 200, "longest": 300}

