"""Claude, for the resume tools. Every call here is behind a button the
owner clicks; nothing calls Claude on its own. The key comes from
ANTHROPIC_API_KEY (.env locally, the app's secrets on Community Cloud) and
is never printed. Pure apart from the API itself: no database, no Streamlit
widgets (the key lookup mirrors db.py's secrets fallback)."""

import os
import sys
from dataclasses import dataclass

import anthropic

import config
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
    try:
        response = client().messages.parse(
            model=config.AI_MODEL, max_tokens=config.AI_MAX_TOKENS, system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=resume_schema.Resume, output_config={"effort": "high"})
    except anthropic.APIError as exc:
        raise AIError(_explain(exc)) from None
    if response.stop_reason == "refusal":
        raise AIError("Claude declined this request.")
    if response.parsed_output is None:
        raise AIError("Claude's answer didn't fit the resume shape; try again.")
    usage = Usage(response.model, response.usage.input_tokens, response.usage.output_tokens)
    return response.parsed_output.model_dump(), usage
