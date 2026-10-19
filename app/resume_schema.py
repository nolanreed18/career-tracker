"""The shape of the master resume as data: what Claude fills in from the
uploaded files (structured output), what the Resume page edits, and what
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


def empty() -> dict:
    return Resume(name="", email="", phone="", linkedin="", roles=[], projects=[],
                  education=[], skill_groups=[], conflicts=[]).model_dump()
