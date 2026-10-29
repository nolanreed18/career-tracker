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
    assert ai.cost("claude-opus-5-5", 0, 0, searches=3) == 0.03          # $10 per 1,000
    assert ai.Usage("claude-opus-5-5", 6000, 8000, 2).cost_usd == 0.204


class FakeModels:
    def __init__(self, error=None):
        self.error = error

    def retrieve(self, model):
        if self.error:
            raise self.error
        return types.SimpleNamespace(id=model, display_name="Claude Opus 5.5")


class FakeMessages:
    """The API stood in: create() answers with the given pydantic object as
    JSON text (or any text), and the stop reason asked for."""

    def __init__(self, parsed, stop_reason="end_turn", error=None, text=None):
        self.parsed, self.stop_reason, self.error, self.calls = parsed, stop_reason, error, []
        self.text = text

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if self.text is not None:
            text = self.text
        else:
            text = "" if self.parsed is None else self.parsed.model_dump_json()
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(type="text", text=text)],
            stop_reason=self.stop_reason, model=kwargs["model"],
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
    assert call["model"] == config.AI_MODEL and call["max_tokens"] == config.AI_MAX_TOKENS
    assert '<document kind="resume">' in call["messages"][0]["content"]
    assert '<document kind="history">' in call["messages"][0]["content"]
    assert call["system"] == ai.SYSTEM and call["output_config"]["effort"] == "high"
    schema = call["output_config"]["format"]
    assert schema["type"] == "json_schema" and "roles" in schema["schema"]["properties"]


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
    assert call["system"] == ai.TAILOR_SYSTEM
    assert "cover_letter" in call["output_config"]["format"]["schema"]["properties"]
    assert '<posting company="Acme" role="Analyst">\nWe need SQL.\n</posting>' in sent
    assert '"employer": "Acme"' in sent and "s@example.com" not in sent and "conflicts" not in sent
    assert "<notes" in sent and "lead with SQL" in sent
    assert '<person name="Sample" today="October 20, 2026"/>' in sent
    assert ('<limits><roles bullets="1" characters="5"/>'                 # the printed master,
            '<projects bullets="0" characters="0"/></limits>' in sent)      # column by column
    with pytest.raises(ai.AIError, match="Paste the job posting"):
        ai.tailor(master, "   ", "Acme", "Analyst", date(2026, 10, 20))


def test_a_cut_off_refused_or_malformed_answer_is_a_plain_error_with_its_cost(monkeypatch):
    parsed = resume_schema.Resume(**resume_schema.empty())
    fake_client(monkeypatch, messages=FakeMessages(parsed, stop_reason="max_tokens"))
    with pytest.raises(ai.AIError, match="cut off") as caught:
        ai.structure_resume({"resume": "## Sample"})
    assert caught.value.usage.cost_usd == 0.184
    fake_client(monkeypatch, messages=FakeMessages(parsed, stop_reason="refusal"))
    with pytest.raises(ai.AIError, match="declined"):
        ai.structure_resume({"resume": "## Sample"})
    fake_client(monkeypatch, messages=FakeMessages(parsed, text='{"name": "Sample", "roles": '))
    with pytest.raises(ai.AIError, match="didn't fit") as caught:
        ai.structure_resume({"resume": "## Sample"})
    assert caught.value.usage.input_tokens == 6000


class FakeSearchMessages:
    """The API stood in for a web-search call: create() answers with each
    stop reason in turn (a paused turn has no text yet), counting searches."""

    def __init__(self, text, stop_reasons=("end_turn",), searches=2):
        self.text, self.stop_reasons, self.searches, self.calls = text, stop_reasons, searches, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reason = self.stop_reasons[min(len(self.calls), len(self.stop_reasons)) - 1]
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(type="text", text="" if reason == "pause_turn"
                                           else self.text)],
            stop_reason=reason, model=kwargs["model"],
            usage=types.SimpleNamespace(
                input_tokens=3000, output_tokens=500,
                server_tool_use=types.SimpleNamespace(web_search_requests=self.searches)))


FOUND = ('Here it is.\n{"url": "https://bp.wd3.myworkdayjobs.com/en-US/bpx/job/Denver/R123", '
         '"title": "Senior Development Systems Engineer", "location": "Houston, TX", '
         '"note": "Same title on bp\'s Workday site; listed in Houston.", "description": ""}')


def test_find_posting_searches_the_web_resumes_a_pause_and_counts_the_searches(monkeypatch):
    messages = FakeSearchMessages(FOUND, stop_reasons=("pause_turn", "end_turn"), searches=1)
    fake_client(monkeypatch, messages=messages)
    found, usage = ai.find_posting("bp", "Senior Development Systems Engineer", "Denver, CO",
                                   "LinkedIn", "Job Description " * 500)
    assert found["url"].startswith("https://bp.wd3.myworkdayjobs.com/")
    assert found["title"] == "Senior Development Systems Engineer"
    assert found["location"] == "Houston, TX"
    assert (usage.input_tokens, usage.output_tokens, usage.searches) == (6000, 1000, 2)
    assert usage.model == config.AI_FIND_MODEL == "claude-sonnet-5-5"       # the cheaper model
    assert usage.cost_usd == round(6000 * 2 / 1e6 + 1000 * 10 / 1e6 + 2 * 0.01, 4)
    first, second = messages.calls
    assert first["model"] == config.AI_FIND_MODEL
    assert first["tools"] == [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": config.AI_SEARCH_MAX,
         "blocked_domains": config.JOB_BOARDS},                   # no job-board results
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": config.AI_FETCH_MAX,
         "max_content_tokens": config.AI_FETCH_TOKENS}]           # it can open the careers site
    assert first["system"] == ai.FIND_SYSTEM and first["max_tokens"] == config.AI_FIND_MAX_TOKENS
    prompt = first["messages"][0]["content"]
    assert 'employer="bp"' in prompt and 'location="Denver, CO"' in prompt
    assert len(prompt) < config.POSTING_PROMPT_CHARS + 300                 # the posting is trimmed
    assert "copy the description" not in prompt                            # it has the posting
    assert second["messages"][1]["role"] == "assistant"                   # resumed where it paused


def test_find_posting_treats_a_job_board_link_as_not_found_and_checks_the_shape(monkeypatch):
    messages = FakeSearchMessages(
        '{"url": "https://www.linkedin.com/jobs/view/1/", "title": "Analyst", '
        '"location": "", "note": "Only on LinkedIn.", "description": "LinkedIn\'s copy"}',
        searches=3)
    fake_client(monkeypatch, messages=messages)
    found, usage = ai.find_posting("Acme", "Analyst", None, None, "")
    assert found["url"] == "" and found["note"].startswith("Found only on a job board")
    assert found["description"] == ""                                   # not the employer's
    assert usage.searches == 3
    assert messages.calls[0]["messages"][0]["content"].endswith(
        "The posting's text is missing: when you open its page, copy the description too.")
    fake_client(monkeypatch, messages=FakeSearchMessages('{"url": "", "title": "", "location": "", '
                                                         '"note": "Nothing on Acme\'s site.", '
                                                         '"description": ""}'))
    assert ai.find_posting("Acme", "Analyst", "", "", "")[0]["url"] == ""
    fake_client(monkeypatch, messages=FakeSearchMessages("No JSON at all"))
    with pytest.raises(ai.AIError, match="didn't fit") as caught:
        ai.find_posting("Acme", "Analyst", "", "", "")
    assert caught.value.usage.searches == 2
    fake_client(monkeypatch, messages=FakeSearchMessages("", stop_reasons=("refusal",)))
    with pytest.raises(ai.AIError, match="declined"):
        ai.find_posting("Acme", "Analyst", "", "", "")


REVIEW = resume_schema.ProjectReview(
    strength=6, verdict="Clear work; no outcome yet.",
    questions=["How many hours a week did it save?"],
    bullets=["Rebuilt the rates tool in Python, saving [X hours] a week"],
    skills=["Python"],
    details=resume_schema.ProjectDetails(situation="Rates came by email.", task="",
                                         action="Built a Python app. It replaced VBA.",
                                         result="Saves 6 hours a week."))


def test_a_project_review_sends_the_project_style_targets_and_answers(monkeypatch):
    messages = FakeMessages(REVIEW)
    fake_client(monkeypatch, messages=messages)
    project = {"project_id": 3, "title": "Rates", "employer": "Acme", "situation":
               "Rates came by email.", "action": "Built a Python app.", "result": None,
               "skills": float("nan"), "review": {"old": True}}
    style = {"samples": ["Built a pipeline.", "Led a team."], "typical": 180, "longest": 290}
    content, usage = ai.review_project(project, [("How many hours?", " 6 a week "),
                                                 ("How many users?", "  ")], style,
                                       "Analytics Engineer")
    assert content["strength"] == 6 and content["details"]["result"] == "Saves 6 hours a week."
    assert usage.cost_usd == 0.184
    call = messages.calls[0]
    sent = call["messages"][0]["content"]
    assert call["system"] == ai.PROJECT_SYSTEM
    assert "questions" in call["output_config"]["format"]["schema"]["properties"]
    assert '"situation": "Rates came by email."' in sent and '"result": ""' in sent
    assert '"skills": ""' in sent and "review" not in sent and "project_id" not in sent
    assert '<style typical_length="180" longest="290">\n- Built a pipeline.\n- Led a team.' in sent
    assert "<targets>\nAnalytics Engineer\n</targets>" in sent
    assert "Q: How many hours?\nA: 6 a week" in sent and "How many users?" not in sent
    messages.calls.clear()
    ai.review_project(project, [], {}, "")
    first = messages.calls[0]["messages"][0]["content"]
    assert "<answers>" not in first and "<targets>" not in first
    assert 'typical_length="200" longest="300"' in first                  # defaults
    with pytest.raises(ai.AIError, match="Write a line or two"):
        ai.review_project({"title": "Empty", "skills": "SQL"}, [], {}, "")

