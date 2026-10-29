"""Knobs. Anything you might want to tune lives here.

The lists below are also enforced by CHECK constraints in schema.sql; change
both together (tests/test_data.py fails if they drift apart).
"""

# An open application with no update for this many days is flagged on Home
# as needing a follow-up.
FOLLOW_UP_DAYS = 14

# Home lists interviews from today through this many days ahead.
INTERVIEW_LOOKAHEAD_DAYS = 7

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

INTERVIEW_FORMATS = ["phone", "video", "onsite", "take-home"]

# Job leads from alert emails. "moved" means it became an application.
LEAD_STATUSES = ["new", "moved", "dismissed"]

# Why a lead was dismissed: one reason or several (stored comma-separated).
# The daily review reads the recent ones as a hint of what the owner doesn't want.
# Where the employer-site search for an application stands (applications.apply_state;
# null: not looked for yet). Repeated in schema.sql's CHECK.
APPLY_STATES = ["looking", "found", "missing", "failed"]
DISMISS_REASONS = ["wrong role", "not enough experience", "too much travel", "location",
                   "pay", "company", "already applied", "other"]

# A lead still in the inbox this many days after it arrived is stale: shown
# under its own view, out of the way (a posting that old is usually gone).
LEAD_STALE_DAYS = 7

# How far back the daily review looks at dismissals, and how many it reads.
DISMISSAL_DAYS = 30
DISMISSAL_LIMIT = 30

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
# The review looks up missing pay only for a job whose role and location would
# both rate this or more: the rest aren't worth the searches.
PAY_RESEARCH_FIT = 6
PAY_RESEARCH = (
    "When the alert gives no pay, the review opens the posting for its own range, or "
    "searches the web for a recent range for that title at that company (or that "
    "title in that area) and stores it as an estimate, saying where it came from. It "
    f"only looks for jobs that rate {PAY_RESEARCH_FIT} or more on both role and location; "
    "the rest stay Pay not listed. Estimates and missing pay "
    "are marked with a yellow warning, so a listed range is never confused with a guess."
)

# Fit scores (1-10) at or above this are a strong match: highlighted in the
# app, listed first in the daily email, and what the Job Leads inbox opens on.
# 8 while only exceptional roles are worth the owner's time (7 was the
# rubric's own bar; the review's scoring doesn't change with this).
STRONG_FIT = 8
HOME_FIT_MARKS = (8.0, 9.0)   # Home counts the inbox leads at or above each of these
DIGEST_CARDS = 20             # leads shown as full cards in the digest email, best first
DIGEST_ROWS = 15              # one-line rows after that in each section; the rest is a count

# Claude, for the resume tools (app/ai.py). Every call is a button the owner
# clicks; nothing calls Claude on its own. The key is ANTHROPIC_API_KEY in the
# app's secrets (or .env locally); the model is pinned here.
AI_MODEL = "claude-opus-5-5"
# The employer-site search reads a lot of web pages for a small answer: a
# cheaper model does it, and the app checks the link against the ATS feed.
AI_FIND_MODEL = "claude-sonnet-5-5"
# Dollars per million input / output tokens, for the running cost shown in
# the app (thinking counts as output).
AI_PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}
AI_MAX_TOKENS = 32000          # thinking counts against it; a cut-off answer is an error
AI_SEARCH_PRICE = 0.01         # dollars per web search ($10 per 1,000), on top of the tokens
AI_SEARCH_MAX = 8              # searches one "find it on the employer's site" call may make
AI_FETCH_MAX = 4               # pages it may open (the careers site itself; no charge)
AI_FETCH_TOKENS = 8000         # the most of one page it reads (every page is input tokens)
AI_FIND_MAX_TOKENS = 16000     # that call's answer is a few lines, but each search and
                               # page costs output tokens too (thinking counts as well)
POSTING_PROMPT_CHARS = 3000    # how much of the posting that call is shown
# Job boards and aggregators: a posting found there is not the employer's own,
# and the search for the employer's own copy skips them.
JOB_BOARDS = ["linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com", "builtin.com",
              "dice.com", "wellfound.com", "welcometothejungle.com", "simplyhired.com",
              "monster.com", "talent.com", "jooble.org", "lensa.com", "google.com"]

# A job posting read from its link (app/posting.py): shorter than this
# and the page gave no description; longer is cut, the tail is boilerplate.
POSTING_MIN_CHARS = 200
POSTING_MAX_CHARS = 20000

# Where a piece of the master resume came from (resume_sources.kind, also a
# CHECK in schema.sql): the resume itself, a project history, a projects
# spreadsheet, or anything else worth reading.
RESUME_SOURCE_KINDS = ["resume", "history", "projects", "other"]
# Bullet strength, 1 (filler) to 5 (quantified, big scope).
BULLET_RANK_MAX = 5

# The project bank (Resume and Projects page, Projects): every work and personal project in
# full, scored for detail, with Claude to review and word it. Kinds are
# repeated in schema.sql's CHECK.
PROJECT_KINDS = ["work", "personal"]
# The free detail score: what a strong project write-up has, each worth points
# (out of 100), with what to say when it's missing. A field counts once it has
# at least that many characters; "result_number" wants a figure in the result.
DETAIL_CHECKS = [
    ("situation", 60, 15, "the problem or why it mattered (Situation)"),
    ("task", 30, 10, "what you were responsible for (Task)"),
    ("action", 150, 25, "what you did and how (Action)"),
    ("result", 40, 20, "how it turned out (Result)"),
    ("result_number", 0, 15, "a number in the result: hours, $, %, users"),
    ("skills", 2, 10, "at least two tools or skills"),
    ("bullet", 40, 5, "a resume bullet"),
]
DETAIL_STRONG = 80                   # a score at or above: green, ready
DETAIL_THIN = 50                     # at or above: orange, thin; below: red

# Scores below this are weak matches: the Job Leads inbox hides them until
# asked (they stay stored, so the same job never comes back).
MAYBE_FIT = 4

# Lead cards drawn at once on Job Leads; a button shows the next batch, so a
# long inbox stays quick to draw on a phone.
LEADS_SHOWN = 25

HOME_TOP_LEADS = 3                   # a computer's Home lists the best few waiting leads
BULK_ADD_MAX = 5                     # leads added at once from the table (each runs a site search)
