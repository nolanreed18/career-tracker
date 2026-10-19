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

# The sites job alerts come from (DAILY_REVIEW.md reads their emails).
LEAD_SOURCES = ["LinkedIn", "Indeed", "Glassdoor", "Built In", "Dice", "Wellfound",
                "Welcome to the Jungle"]

# Fit scores (1-10) at or above this are a strong match: highlighted in the
# app and listed first in the daily email.
STRONG_FIT = 7
