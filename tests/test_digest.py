"""The digest email, rendered from leads and what needs attention."""

from datetime import date

import config
import digest
import logic

TODAY = date(2026, 10, 19)
APP = "https://tracker.example.app/"


def lead(**fields) -> dict:
    row = {"source": "LinkedIn", "title": "Analytics Engineer", "company": "Gamma",
           "location": "Denver, CO", "work_mode": None, "salary_min": None, "salary_max": None,
           "pay_source": None, "pay_note": None, "job_url": "https://example.com/j/1",
           "fit_score": 8.2, "fit_reason": "Strong on role", "fit_detail": {
               "ratings": {"role": 9, "industry": 8, "location": 10, "level": 7, "extras": 6},
               "deal_breaker": False}}
    return {**row, **fields}


def test_the_subject_counts_new_and_strong_leads():
    assert digest.subject(TODAY, []) == "Job leads Oct 19: nothing new"
    assert digest.subject(TODAY, [lead(), lead(fit_score=5)]) == "Job leads Oct 19: 2 new, 1 strong"
    assert digest.subject(TODAY, [lead()], "Gmail was down") == (
        "Job leads Oct 19: the review hit a problem")


def test_every_lead_is_shown_with_its_score_pay_posting_and_ratings():
    leads = [
        lead(),
        lead(title="BI Developer", company="Delta", fit_score=5.4, salary_min=110000,
             salary_max=130000, pay_source="estimated", pay_note="Glassdoor, Denver",
             job_url="https://example.com/j/2", fit_detail={
                 "ratings": {"role": 6, "industry": 3, "pay": 6}, "deal_breaker": False}),
        lead(title="Contractor", company="Epsilon", fit_score=4.5, location="Austin, TX",
             salary_min=90000, salary_max=90000, pay_source="listed",
             job_url="https://example.com/j/3?a=1&b=2",
             fit_detail={"ratings": {"role": 5}, "deal_breaker": True}),
        lead(title="Clerk", company="Zeta", fit_score=2.1, location="Omaha, NE", job_url=None,
             fit_detail=None, fit_reason=None),
    ]
    out = digest.render(TODAY, leads, [], APP,
                        {"emails_read": 2, "sources": {"LinkedIn": 2}, "already_known": 1,
                         "duplicates": 1})
    html = out["html"]
    assert out["subject"] == "Job leads Oct 19: 4 new, 1 strong"
    assert "Monday, October 19" in html and "4 new leads · 1 strong · 2 worth a look" in html
    assert "from 2 alert emails (LinkedIn 2)" in html
    assert f'href="{APP}Job_Leads"' in html and f'href="{APP}Applications"' in html
    assert 'href="https://example.com/j/1"' in html and "Analytics Engineer" in html
    assert 'href="https://example.com/j/3?a=1&amp;b=2"' in html          # escaped, kept whole
    assert "Top pick · 8.2" in html
    assert "Pay not listed" in html                                     # Gamma: unknown
    assert "~$110,000–$130,000" in html and "(estimate)" in html and "Glassdoor, Denver" in html
    assert "$90,000</span>" in html                                      # Epsilon: listed, plain
    assert "Role&nbsp;9" in html and "Industry&nbsp;3" in html   # chips never wrap
    assert "Deal&#8209;breaker" in html
    assert "Strong fits (8+)" in html and "Worth a look (4–7.9)" in html
    assert "Weak or unscored (1, hidden in the app until asked)" in html
    assert "2.1</strong> &nbsp;Clerk — Zeta · Omaha, NE" in html         # the compact list
    assert "Read 2 alert emails · 1 already in the tracker · 1 listed twice" in html
    assert "Role 35%" in html and "what you're looking for" in html
    assert "On your plate" not in html


def test_what_needs_doing_today_is_listed_and_the_text_version_stands_alone():
    items = [logic.Attention("overdue", 1, "Acme — Data Analyst", "Follow up: 3 days overdue",
                             date(2026, 10, 16)),
             logic.Attention("interview", 2, "Beta — PM", "Onsite, tomorrow at 10:00 am",
                             date(2026, 10, 20))]
    out = digest.render(TODAY, [lead()], items, APP, {})
    assert "On your plate today" in out["html"]
    assert "Overdue" in out["html"] and "Acme — Data Analyst" in out["html"]
    assert "Interview" in out["html"] and "Onsite, tomorrow at 10:00 am" in out["html"]
    text = out["text"]
    assert text.startswith("Job leads for Monday, October 19")
    assert "8.2  Analytics Engineer — Gamma" in text
    assert "LinkedIn · Denver, CO · Pay not listed" in text
    assert "https://example.com/j/1" in text
    assert "- Overdue: Acme — Data Analyst: Follow up: 3 days overdue" in text
    assert f"Job Leads: {APP}Job_Leads" in text
    assert "<" not in text


def test_nothing_new_and_a_problem_still_make_an_email():
    out = digest.render(TODAY, [], [], APP, {})
    assert out["subject"] == "Job leads Oct 19: nothing new"
    assert "Nothing new today." in out["html"] and "Nothing new today." in out["text"]
    assert "Top pick" not in out["html"]
    broken = digest.render(TODAY, [], [], APP, {"problem": "leads.py add refused the file"})
    assert broken["subject"].endswith("the review hit a problem")
    assert "Something went wrong." in broken["html"]
    assert "leads.py add refused the file" in broken["html"]
    assert "Something went wrong: leads.py add refused the file" in broken["text"]


def test_user_text_is_escaped_and_missing_values_are_skipped():
    out = digest.render(TODAY, [lead(title="<b>Bold</b> & co", fit_reason=None, job_url=None,
                                     location=None, fit_detail=None)], [], APP, {})
    assert "&lt;b&gt;Bold&lt;/b&gt; &amp; co" in out["html"] and "<b>Bold" not in out["html"]
    assert "None" not in out["html"] and "nan" not in out["html"]
    assert "None" not in out["text"]
    assert config.STRONG_FIT == 8                      # the section titles above assume it


def test_a_big_day_still_makes_a_small_email():
    long_url = "https://www.example.com/jobs/view/1234567890?" + "trk=" + "x" * 600
    leads = [lead(title=f"Role {n}", company=f"Company {n}", job_url=long_url + str(n),
                  fit_score=9.0 - n * 0.08, fit_reason="A reason sentence " * 8)
             for n in range(100)]                   # 100 leads: 13 strong, 50 maybe, 37 weak
    out = digest.render(TODAY, leads, [], APP, {})
    html, text = out["html"], out["text"]
    assert len(html.encode()) < 60_000 and len(text.encode()) < 12_000
    cards = html.count(f'style="{digest.CARD_STYLE};margin:0 0 10px 0"')
    assert cards == config.DIGEST_CARDS                      # 20 cards, best first
    assert "Role 0" in html and "Role 99" not in html          # the tail is a count
    assert "Role 19" in html and "Role 34 —" in html             # 20 cards, then 15 rows
    assert "Role 35 —" not in html                               # then a count
    assert "…and 28 more worth a look" in html and "…and 22 more weak or unscored" in html
    assert "trk=xxx" not in html and "trk=xxx" not in text    # 600-char links: left to the app
    assert "…and 75 more in the app." in text
    assert text.count("https://www.example.com/jobs/view/1234567890") == 0
    short = digest.render(TODAY, [lead(job_url="https://example.com/j/9")], [], APP, {})
    assert "     https://example.com/j/9" in short["text"]
