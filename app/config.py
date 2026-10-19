"""Knobs. Anything you might want to tune lives here.

The lists below are also enforced by CHECK constraints in schema.sql; change
both together (tests/test_data.py fails if they drift apart).
"""

# An open application with no update for this many days is flagged on Home
# as needing a follow-up.
FOLLOW_UP_DAYS = 14

# Home lists interviews from today through this many days ahead.
INTERVIEW_LOOKAHEAD_DAYS = 7

# Weeks shown in the "applications per week" chart.
STATS_WEEKS = 12

# Pipeline order. The first five are open; the rest close an application.
STATUSES = [
    "saved",          # interesting, not applied yet
    "applied",
    "screening",      # recruiter or phone screen
    "interviewing",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
]
OPEN_STATUSES = ["saved", "applied", "screening", "interviewing", "offer"]
CLOSED_STATUSES = ["accepted", "rejected", "withdrawn"]

# Reaching any of these counts as a response for the response rate.
RESPONDED_STATUSES = ["screening", "interviewing", "offer", "accepted"]

WORK_MODES = ["onsite", "hybrid", "remote"]

CONTACT_KINDS = ["recruiter", "hiring manager", "referral", "colleague", "network"]

# Career log entry types.
CAREER_KINDS = ["win", "skill", "certification", "feedback", "learning"]

# Job leads from alert emails. "moved" means it became an application.
LEAD_STATUSES = ["new", "moved", "dismissed"]

# Why a lead was dismissed. The daily review reads the recent ones as a hint
# of what the owner doesn't want.
DISMISS_REASONS = ["wrong role", "location", "pay", "company", "already applied", "other"]

# A lead still in the inbox this many days after it arrived is stale: shown
# under its own view, out of the way (a posting that old is usually gone).
LEAD_STALE_DAYS = 14

# How far back the daily review looks at dismissals, and how many it reads.
DISMISSAL_DAYS = 30
DISMISSAL_LIMIT = 30

# The sites job alerts come from (DAILY_REVIEW.md reads their emails).
LEAD_SOURCES = ["LinkedIn", "Indeed", "Glassdoor", "Built In", "Dice", "Wellfound",
                "Welcome to the Jungle"]

# How a lead's fit score is built. The daily review rates each job 1-10 on
# every category against the profile (What I'm looking for); the score is the
# weighted average, to one decimal. Weights are shares of 1 and must add up
# to 1 (tests check). The descriptions are what the review goes by, and what
# the app shows under "How scoring works".
FIT_CATEGORIES = {
    "role": ("Role match", 0.35,
             "How close the day-to-day work is to the roles the profile asks for."),
    "industry": ("Industry", 0.20,
                 "The industries the profile prefers score high; unrelated ones low."),
    "location": ("Location and work mode", 0.15,
                 "The places and work modes the profile allows; its preferred area highest."),
    "pay": ("Pay", 0.15,
            "Against the profile's salary floor: well above is 10, at it 7, under it low; a "
            "researched estimate is rated the same way. Not rated when pay is unknown, so "
            "the score then rests on the other categories."),
    "level": ("Level", 0.10,
              "The level the profile asks for; entry level or executive score low."),
    "extras": ("Extras", 0.05,
               "The profile's must-haves and nice-to-haves beyond the above."),
}

# Any deal-breaker from the profile caps the score here, whatever the rest says.
DEAL_BREAKER_CAP = 3.0

# Where a lead's pay came from: "listed" in the alert or the posting, or
# "estimated" by the daily review from what it found online (pay_note says
# from what). A lead with no pay at all has neither, and no pay rating.
PAY_SOURCES = ["listed", "estimated"]

# How the daily review looks for pay when the alert doesn't give it, shown
# under "How scoring works" and printed by `leads.py rubric`.
PAY_RESEARCH = (
    "When the alert gives no pay, the review opens the posting for its own range, or "
    "searches the web for a recent range for that title at that company (or that "
    "title in that area) and stores it as an estimate, saying where it came from. Jobs that are a "
    "poor fit on role or location are left unresearched. Estimates and missing pay "
    "are marked with a yellow warning, so a listed range is never confused with a guess."
)

# Fit scores (1-10) at or above this are a strong match: highlighted in the
# app and listed first in the daily email.
STRONG_FIT = 7

# Scores below this are weak matches: the Job Leads inbox hides them until
# asked (they stay stored, so the same job never comes back).
MAYBE_FIT = 4
