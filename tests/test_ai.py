"""Claude for the resume tools, with the API stood in for: no key, a refused
key, a refusal, and a good answer with its cost."""

import types
from datetime import date

import anthropic
import httpx2 as httpx  # the SDK's HTTP library (not the httpx package)
import pytest

import ai
import config
import resume_schema


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_the_key_comes_from_the_environment_and_nothing_runs_without_it(monkeypatch):
    assert not ai.ready()
    with pytest.raises(ai.AIError, match="No ANTHROPIC_API_KEY"):
        ai.client()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert ai.ready() and isinstance(ai.client(), anthropic.Anthropic)


def test_cost_follows_the_price_table():
    assert ai.cost("claude-opus-5-5", 1_000_000, 0) == config.AI_PRICES["claude-opus-5-5"][0]
    assert ai.cost("claude-opus-5-5", 6000, 8000) == 0.184
    assert ai.cost("unknown-model", 6000, 8000) == 0
    assert ai.Usage("claude-opus-5-5", 6000, 8000).cost_usd == 0.184


class FakeModels:
    def __init__(self, error=None):
        self.error = error

    def retrieve(self, model):
        if self.error:
            raise self.error
        return types.SimpleNamespace(id=model, display_name="Claude Opus 5.5")


class FakeMessages:
    def __init__(self, parsed, stop_reason="end_turn", error=None):
        self.parsed, self.stop_reason, self.error, self.calls = parsed, stop_reason, error, []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return types.SimpleNamespace(
            parsed_output=self.parsed, stop_reason=self.stop_reason, model=kwargs["model"],
            usage=types.SimpleNamespace(input_tokens=6000, output_tokens=8000))


def fake_client(monkeypatch, models=None, messages=None):
    client = types.SimpleNamespace(models=models or FakeModels(), messages=messages)
    monkeypatch.setattr(ai, "client", lambda: client)
    return client


def api_error(cls, status):
    request = httpx.Request("GET", "https://api.anthropic.com/v1/x")
    response = httpx.Response(status, request=request)
    return cls("nope", response=response, body=None)


def test_ping_reports_the_model_or_explains_the_refusal(monkeypatch):
    fake_client(monkeypatch)
    assert ai.ping() == "Connected: Claude Opus 5.5"
    fake_client(monkeypatch, models=FakeModels(api_error(anthropic.AuthenticationError, 401)))
    with pytest.raises(ai.AIError, match="refused the key"):
        ai.ping()
    fake_client(monkeypatch, models=FakeModels(api_error(anthropic.NotFoundError, 404)))
    with pytest.raises(ai.AIError, match="isn't available"):
        ai.ping()


def test_structure_resume_sends_every_file_and_returns_data_with_its_cost(monkeypatch):
    parsed = resume_schema.Resume(
        name="Sample", email="s@example.com", phone="", linkedin="",
        roles=[resume_schema.Role(employer="Acme", title="Analyst", location="Denver", start="2025",
                                  end="Present", bullets=[resume_schema.Bullet(
                                      text="Did x", skills=["SQL"], source="resume", rank=4,
                                      in_master=True)])],
        projects=[], education=[], skill_groups=[], conflicts=["GPA 3.88 vs 3.90"])
    messages = FakeMessages(parsed)
    fake_client(monkeypatch, messages=messages)
    content, usage = ai.structure_resume({"resume": "## Acme", "history": "Project: x"})
    assert content["roles"][0]["bullets"][0]["text"] == "Did x"
    assert content["conflicts"] == ["GPA 3.88 vs 3.90"]
    assert (usage.model, usage.input_tokens, usage.output_tokens) == ("claude-opus-5-5", 6000, 8000)
    call = messages.calls[0]
    assert call["model"] == config.AI_MODEL and call["output_format"] is resume_schema.Resume
    assert '<document kind="resume">' in call["messages"][0]["content"]
    assert '<document kind="history">' in call["messages"][0]["content"]
    assert call["system"] == ai.SYSTEM and call["output_config"] == {"effort": "high"}


def test_structure_resume_needs_the_resume_and_handles_a_refusal(monkeypatch):
    fake_client(monkeypatch, messages=FakeMessages(None))
    with pytest.raises(ai.AIError, match="Upload the master resume first"):
        ai.structure_resume({"history": "x"})
    fake_client(monkeypatch, messages=FakeMessages(None, stop_reason="refusal"))
    with pytest.raises(ai.AIError, match="declined"):
        ai.structure_resume({"resume": "x"})
    fake_client(monkeypatch, messages=FakeMessages(None, error=api_error(anthropic.RateLimitError, 429)))
    with pytest.raises(ai.AIError, match="rate-limiting"):
        ai.structure_resume({"resume": "x"})


def test_tailor_sends_the_master_the_posting_and_the_steer(monkeypatch):
    parsed = resume_schema.Tailored(
        fit_notes="Strong on SQL.", roles=[resume_schema.TailoredRole(
            employer="Acme", title="Analyst", location="Denver", start="2025", end="Present",
            bullets=[resume_schema.TailoredBullet(text="Did x for finance", original="Did x",
                                                  skills=["SQL"])])],
        projects=[], skill_groups=[resume_schema.SkillGroup(name="Languages", skills="SQL")],
        keywords=[resume_schema.Keyword(term="SQL", covered=True, where="Did x for finance")],
        changes=["Reworded 'Did x' to name finance, which the posting leads with."],
        cover_letter="Dear Hiring Team,\n\nI did x.\n\nSincerely,\nSample")
    messages = FakeMessages(parsed)
    fake_client(monkeypatch, messages=messages)
    master = {"name": "Sample", "email": "s@example.com", "roles": [{"employer": "Acme"}],
              "projects": [], "skill_groups": [], "education": [], "conflicts": ["x"]}
    master["roles"] = [{"employer": "Acme", "bullets": [
        {"text": "Did x", "in_master": True}, {"text": "Pool", "in_master": False}]}]
    content, usage = ai.tailor(master, "  We need SQL.  ", "Acme", "Analyst", date(2026, 10, 20),
                               "lead with SQL")
    assert content["roles"][0]["bullets"][0]["original"] == "Did x"
    assert content["keywords"] == [{"term": "SQL", "covered": True, "where": "Did x for finance"}]
    assert usage.cost_usd == 0.184
    call = messages.calls[0]
    sent = call["messages"][0]["content"]
    assert call["system"] == ai.TAILOR_SYSTEM and call["output_format"] is resume_schema.Tailored
    assert '<posting company="Acme" role="Analyst">\nWe need SQL.\n</posting>' in sent
    assert '"employer": "Acme"' in sent and "s@example.com" not in sent and "conflicts" not in sent
    assert "<notes" in sent and "lead with SQL" in sent
    assert '<person name="Sample" today="October 20, 2026"/>' in sent
    assert '<limits bullets="1" characters="5"/>' in sent              # the printed master
    with pytest.raises(ai.AIError, match="Paste the job posting"):
        ai.tailor(master, "   ", "Acme", "Analyst", date(2026, 10, 20))
