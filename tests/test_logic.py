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
    assert logic.job_link(real) == real                     # the emailed link stays whole
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
