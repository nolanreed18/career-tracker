"""Claude, for the resume tools. Every call here is behind a button the
owner clicks; nothing calls Claude on its own. The key comes from
ANTHROPIC_API_KEY (.env locally, the app's secrets on Community Cloud) and
is never printed. Pure apart from the API itself: no database, no Streamlit
widgets (the key lookup mirrors db.py's secrets fallback)."""

import json
import os
import sys
from dataclasses import dataclass
from datetime import date

import anthropic

import config
import logic
import resume_schema

SYSTEM = """You turn a person's career documents into structured resume data.
Rules:
- Bullets that are on the master resume are copied word for word, in the
  same order, with in_master true and source "resume". Never rewrite them.
- Every other document adds bullets to the pool with in_master false and
  source set to that document's kind. Write each as a finished resume
  bullet: past tense (present for a current role), a strong verb, the
  result and the scale when the source gives them, under 40 words.
  Merge the same project from several sources into one bullet, keeping
  the fullest numbers.
- Work that a master bullet already covers gets no pool bullet, however
  differently another document words it: the pool holds only work the
  master leaves out, or a distinct extra result. No two bullets in the
  whole answer describe the same work.
- Never invent a fact, a number, a tool or an employer. If two sources
  disagree (a date, a GPA, a figure), keep the master resume's version and
  list the disagreement in conflicts, naming both values.
- Dates are "Mon YYYY" (Jan 2024) or "Present". When a source is vague
  ("late 2024"), use the nearest month and name the guess in conflicts.
- skills lists the tools and skills the bullet shows (short names).
- rank: 5 = quantified result and wide scope, 3 = solid, 1 = filler.
- Education and skill groups come from the master resume as written.
- Projects are personal or academic projects, each like a role with
  employer = the project's name and title "".
"""


TAILOR_SYSTEM = """You tailor a person's master resume to one job posting and write the
cover letter. The master is given as data: roles with every bullet, printed
(in_master true) or waiting in the pool, with the skills each proves.
Rules:
- Every bullet comes from the master, printed or pool: choose the ones that
  best prove what the posting asks for, most relevant first within each
  role. Put the master's text in original, word for word.
- Reword only to mirror the posting's own terms and to tighten. Keep every
  fact, number, tool and employer as the master states them; never add a
  skill, tool, date or result the master lacks. A bullet left as it is has
  text equal to original.
- Keep each role's employer, title, location and dates exactly, and the
  roles' order. Drop a role only when nothing in it serves the posting, and
  never the current or most recent role.
- person gives the name to sign the letter with and today's date: count
  years of experience and whether a degree is finished from that date,
  never from a guess.
- One page, like the master: limits gives how many bullets the master
  prints and how many characters they total; stay within both, trimming
  words before dropping a bullet.
- Within a role keep the tense the master's printed bullets use there,
  and end bullets as the master ends them (no full stop when it has none).
- skill_groups: the master's groups with the relevant skills first; keep
  anything the posting mentions, add nothing the master lacks.
- keywords: the posting's 10 to 20 requirements and terms a screener would
  search for, each marked covered when the tailored resume shows it, with
  where it shows.
- changes: one line per bullet reworded, swapped in from the pool or
  dropped, and per skills change, with the reason.
- fit_notes: for the person only, three or four sentences: the strongest
  matches and the honest gaps.
- cover_letter: three or four short paragraphs from greeting ("Dear Hiring
  Team" unless the posting names someone) to a sign-off with the person's
  name; specific to this company and role; built only on facts from the
  master; plain and confident, no clichés; under 300 words.
"""


class AIError(Exception):
    """Something the owner should read: no key, a refused key, a refusal."""


@dataclass(frozen=True)
class Usage:
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def cost_usd(self) -> float:
        return cost(self.model, self.input_tokens, self.output_tokens)


def cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Dollars for one call, from config.AI_PRICES (0 for an unknown model)."""
    per_in, per_out = config.AI_PRICES.get(model, (0.0, 0.0))
    return round(input_tokens * per_in / 1e6 + output_tokens * per_out / 1e6, 4)


def _streamlit_secret() -> str | None:
    st = sys.modules.get("streamlit")
    if st is None:
        return None
    from streamlit import runtime

    if not runtime.exists():
        return None
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None


def api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or _streamlit_secret() or None


def ready() -> bool:
    return api_key() is not None


def client() -> anthropic.Anthropic:
    key = api_key()
    if not key:
        raise AIError("No ANTHROPIC_API_KEY in the app's secrets (or .env locally).")
    return anthropic.Anthropic(api_key=key, max_retries=2, timeout=600.0)


def _explain(exc: Exception) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "Claude refused the key. Check ANTHROPIC_API_KEY in the app's secrets."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "The key isn't allowed to do this (a workspace or spend limit?)."
    if isinstance(exc, anthropic.NotFoundError):
        return f"The model {config.AI_MODEL} isn't available to this key."
    if isinstance(exc, anthropic.RateLimitError):
        return "Claude is rate-limiting this key; try again in a minute."
    if isinstance(exc, anthropic.APIStatusError):
        return f"Claude answered with an error ({exc.status_code}): {exc.message}"
    if isinstance(exc, anthropic.APIConnectionError):
        return "Couldn't reach Claude (network)."
    return str(exc)


def ping() -> str:
    """Confirm the key works with a free call; the model's display name."""
    try:
        model = client().models.retrieve(config.AI_MODEL)
    except anthropic.APIError as exc:
        raise AIError(_explain(exc)) from None
    return f"Connected: {model.display_name}"


def _parse(system: str, prompt: str, shape) -> tuple[dict, Usage]:
    """One structured-output call: the answer as a dict in the given pydantic
    shape (validated by the SDK) and what it cost. Refusals and API errors
    become AIError with a plain message."""
    try:
        response = client().messages.parse(
            model=config.AI_MODEL, max_tokens=config.AI_MAX_TOKENS, system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=shape, output_config={"effort": "high"})
    except anthropic.APIError as exc:
        raise AIError(_explain(exc)) from None
    if response.stop_reason == "refusal":
        raise AIError("Claude declined this request.")
    if response.parsed_output is None:
        raise AIError("Claude's answer didn't fit the expected shape; try again.")
    usage = Usage(response.model, response.usage.input_tokens, response.usage.output_tokens)
    return response.parsed_output.model_dump(), usage


def structure_resume(sources: dict[str, str]) -> tuple[dict, Usage]:
    """The master resume as data (resume_schema.Resume) from the uploaded
    files' text, keyed by kind ("resume" must be present), and what the call
    cost. One call, structured output; the result is validated by the SDK."""
    if "resume" not in sources:
        raise AIError("Upload the master resume first: it anchors everything else.")
    parts = [f"<document kind=\"{kind}\">\n{text.strip()}\n</document>"
             for kind, text in sources.items()]
    prompt = ("Structure these documents into the resume schema. The one of kind "
              "\"resume\" is the master resume.\n\n" + "\n\n".join(parts))
    return _parse(SYSTEM, prompt, resume_schema.Resume)


def master_for_prompt(master: dict) -> dict:
    """The master as Claude needs it for tailoring: roles, projects, skill
    groups and education; no contact details, no conflicts."""
    return {key: master.get(key, []) for key in ("roles", "projects", "skill_groups",
                                                 "education")}


def tailor(master: dict, posting: str, company: str, role: str, today: date,
           notes: str = "") -> tuple[dict, Usage]:
    """The master tailored to one posting (resume_schema.Tailored as a dict:
    chosen and reworded bullets, skills, keyword coverage, the list of
    changes, the cover letter) and what the call cost. One call. The
    person's name and today's date go along, so the letter is signed and
    tenure is counted right; the master's printed size is the page budget."""
    if not posting.strip():
        raise AIError("Paste the job posting first: Claude tailors to its words.")
    budget = logic.master_budget(master)
    prompt = (f"<person name=\"{master.get('name', '')}\" today=\"{logic.long_date(today)}\"/>\n"
              f"<limits bullets=\"{budget['bullets']}\" characters=\"{budget['characters']}\"/>\n\n"
              f"<master>\n{json.dumps(master_for_prompt(master), indent=1)}\n</master>\n\n"
              f"<posting company=\"{company}\" role=\"{role}\">\n{posting.strip()}\n</posting>\n\n")
    if notes.strip():
        prompt += f"<notes from=\"the person\">\n{notes.strip()}\n</notes>\n\n"
    prompt += "Tailor the master resume to this posting and write the cover letter."
    return _parse(TAILOR_SYSTEM, prompt, resume_schema.Tailored)
