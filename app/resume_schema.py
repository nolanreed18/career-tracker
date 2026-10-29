"""The shape of the master resume as data: what Claude fills in from the
uploaded files (structured output), what the Resume and Projects page edits, and what
docx_io turns back into a Word file. Every field is required so the schema
is strict; empty strings and lists stand for "none"."""

from pydantic import BaseModel


class Bullet(BaseModel):
    text: str               # one resume bullet, as it would be printed
    skills: list[str]       # the tools and skills it proves ("Power BI", "SQL")
    source: str             # which uploaded file it came from, by its kind
    rank: int               # 1 (filler) to 5 (quantified result, big scope)
    in_master: bool         # printed on the master resume (False: in the pool only)


class Role(BaseModel):
    employer: str           # for a project: its name
    title: str              # for a project: ""
    location: str
    start: str              # "Jan 2025"
    end: str                # "Present" or "Dec 2024"
    bullets: list[Bullet]


class Education(BaseModel):
    school: str
    when: str               # "May 2026"
    degree: str             # "M.S. in Data Science | 3.90/4.00"


class SkillGroup(BaseModel):
    name: str               # "Programming Languages"
    skills: str             # "Python (Pandas), SQL, DAX"


class Resume(BaseModel):
    name: str
    email: str
    phone: str
    linkedin: str
    roles: list[Role]
    projects: list[Role]
    education: list[Education]
    skill_groups: list[SkillGroup]
    conflicts: list[str]    # facts the sources disagree on, for the owner to settle


class TailoredBullet(BaseModel):
    text: str               # as it will print on the tailored resume
    original: str           # the master bullet it was made from, word for word ("" if none)
    skills: list[str]


class TailoredRole(BaseModel):
    employer: str           # for a project: its name
    title: str
    location: str
    start: str
    end: str
    bullets: list[TailoredBullet]


class Keyword(BaseModel):
    term: str               # a requirement or term from the posting a screener would look for
    covered: bool           # the tailored resume shows it
    where: str              # the bullet or skill group that shows it ("" when not covered)


class Tailored(BaseModel):
    """One application's resume: the master chosen and reworded for a job
    posting, with the cover letter and what Claude did and why."""
    fit_notes: str          # for the owner only: strongest matches and honest gaps
    roles: list[TailoredRole]
    projects: list[TailoredRole]
    skill_groups: list[SkillGroup]
    keywords: list[Keyword]
    changes: list[str]      # one line per change from the master, with the reason
    cover_letter: str       # greeting to sign-off, paragraphs separated by blank lines


class ProjectDetails(BaseModel):
    situation: str          # the problem, or why the work mattered
    task: str               # what the person was responsible for
    action: str             # what they did and how
    result: str             # how it turned out, with numbers where given


class ProjectReview(BaseModel):
    """Claude's review of one project in the bank (ai.review_project)."""
    strength: int           # 1 (vague) to 10 (specific, quantified, clearly theirs)
    verdict: str            # a sentence or two: what reads well, what's missing
    questions: list[str]    # up to five questions whose answers would strengthen it most
    bullets: list[str]      # two or three resume bullets made only from the facts given
    skills: list[str]       # the tools and skills the details show
    details: ProjectDetails  # the four fields with the answers worked in (as given without)


def empty() -> dict:
    return Resume(name="", email="", phone="", linkedin="", roles=[], projects=[],
                  education=[], skill_groups=[], conflicts=[]).model_dump()


class CompanyPosting(BaseModel):
    """Where a posting lives on the employer's own site (ai.find_posting)."""
    url: str                # the posting's address there; "" when nothing fits
    title: str              # the title as that site shows it; "" when not found
    location: str           # the location as that site lists it; "" when not found
    note: str               # a sentence or two: how sure, what differs, or why not
    description: str        # the posting's text copied from that page when asked; "" otherwise
