"""Reading a job posting from its page: LinkedIn's guest copy, a page with
JobPosting data, a plain page; and fetch() deciding what to read, with the
network stood in (no test fetches anything)."""

import httpx
import pytest

import config
import posting

LINKEDIN = """<section><h2 class="top-card-layout__title">Senior Analyst</h2>
<a class="topcard__org-name-link">bp</a>
<span class="topcard__flavor topcard__flavor--bullet">Denver, CO</span>
<div class="show-more-less-html__markup"><strong>Job Description<br><br></strong>We build
things.<ul><li>SQL &amp; Python</li><li>Power BI</li></ul><p>Pay: $100k</p></div></section>"""

JSON_LD = """<html><head><title>Analyst - Acme</title><script type="application/ld+json">
{"@context": "https://schema.org", "@type": "JobPosting", "title": "Analyst",
 "hiringOrganization": {"@type": "Organization", "name": "Acme"},
 "jobLocation": {"@type": "Place", "address": {"addressLocality": "Omaha", "addressRegion": "NE"}},
 "description": "<p>Build <b>dashboards</b>.</p><ul><li>SQL</li></ul>"}</script></head>
<body><nav>Menu</nav><main><h1>Analyst</h1><p>Build dashboards.</p></main></body></html>"""

PLAIN = ("<html><head><title>Data Engineer | Beta</title><script>var x = 1</script></head>"
         "<body><nav>Home</nav><main><h1>Data Engineer</h1><p>Remote role.</p><!-- c -->"
         "<p>Needs Python.</p></main><footer>© Beta</footer></body></html>")


def test_linkedins_guest_copy_gives_title_employer_place_and_text():
    found = posting.parse_linkedin(LINKEDIN)
    assert (found.title, found.company, found.location) == ("Senior Analyst", "bp", "Denver, CO")
    assert found.text == "Job Description\n\nWe build things.\n• SQL & Python\n• Power BI\n\nPay: $100k"
    assert found.as_text().startswith("Senior Analyst — bp · Denver, CO\n\nJob Description\n\n")
    with pytest.raises(posting.PostingError, match="didn't hand over"):
        posting.parse_linkedin("<html><body>Sign in to view this job</body></html>")


def test_a_page_with_job_posting_data_is_read_from_it():
    found = posting.parse_page(JSON_LD)
    assert (found.title, found.company, found.location) == ("Analyst", "Acme", "Omaha, NE")
    assert found.text == "Build dashboards.\n• SQL"


def test_a_plain_page_is_read_as_its_heading_and_main_text():
    found = posting.parse_page(PLAIN)
    assert (found.title, found.company, found.location) == ("Data Engineer", "", "")
    assert found.text == "Data Engineer\n\nRemote role.\n\nNeeds Python."     # no menu, no footer
    assert posting.Posting("", "", "", "Just text").as_text() == "Just text"


def test_text_is_capped(monkeypatch):
    monkeypatch.setattr(config, "POSTING_MAX_CHARS", 12)
    assert posting.text_of(posting.lxml.html.fromstring("<p>" + "word " * 20 + "</p>")) == "word word wo"


def test_fetch_reads_linkedin_through_its_guest_copy(monkeypatch):
    asked = []
    long_copy = LINKEDIN.replace("We build\nthings.", "We build things. " * 20)
    monkeypatch.setattr(posting, "_get", lambda url: asked.append(url) or long_copy)
    found = posting.fetch("https://www.google.com/url?q=https://www.linkedin.com/jobs/view/"
                          "4476631322/%3FrefId%3Dx&source=gmail")        # as an alert stores it
    assert asked == ["https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4476631322"]
    assert found.title == "Senior Analyst" and len(found.text) > config.POSTING_MIN_CHARS
    with pytest.raises(posting.PostingError, match="didn't give the app a job description"):
        monkeypatch.setattr(posting, "_get", lambda url: LINKEDIN)          # a stub of a page
        posting.fetch("https://www.linkedin.com/jobs/view/1/")


def test_fetch_refuses_sites_that_refuse_a_server_without_asking_them(monkeypatch):
    monkeypatch.setattr(posting, "_get", lambda url: pytest.fail("fetched"))
    with pytest.raises(posting.PostingError, match="Indeed doesn't let the app read"):
        posting.fetch("https://www.indeed.com/viewjob?jk=abc")
    with pytest.raises(posting.PostingError, match="Glassdoor doesn't let"):
        posting.fetch("https://www.glassdoor.com/partner/jobListing.htm?jobListingId=1")
    with pytest.raises(posting.PostingError, match="no posting link"):
        posting.fetch(None)


def test_fetch_turns_a_refusal_or_a_dead_network_into_advice(monkeypatch):
    class Response:
        status_code, text = 403, "forbidden"
    monkeypatch.setattr(posting.httpx, "get", lambda *args, **kwargs: Response())
    with pytest.raises(posting.PostingError, match="answered 403"):
        posting.fetch("https://jobs.example.com/analyst")

    def dead(*args, **kwargs):
        raise httpx.ConnectError("no route")
    monkeypatch.setattr(posting.httpx, "get", dead)
    with pytest.raises(posting.PostingError, match=r"Couldn't reach the posting \(ConnectError\)"):
        posting.fetch("https://jobs.example.com/analyst")


WORKDAY = """{"jobPostingInfo": {"title": "Senior Development Systems Engineer",
  "jobDescription": "<p>Job Description</p><p>bpx energy builds things.</p><ul><li>SQL</li></ul>",
  "location": "United States of America - Texas - Houston",
  "additionalLocations": ["United States of America - Colorado - Denver"], "jobReqId": "RQ117112"}}"""


def test_a_workday_link_is_read_from_its_data_feed(monkeypatch):
    asked = []
    monkeypatch.setattr(posting, "_get", lambda url, accept=None: asked.append((url, accept)) or WORKDAY)
    found = posting.employer_posting("https://bpinternational.wd3.myworkdayjobs.com/en-US/bpCareers/job/"
                                     "United-States-of-America---Texas---Houston/"
                                     "Senior-Development-Systems-Engineer_RQ117112?source=x")
    assert asked == [("https://bpinternational.wd3.myworkdayjobs.com/wday/cxs/bpinternational/bpCareers/"
                      "job/United-States-of-America---Texas---Houston/"
                      "Senior-Development-Systems-Engineer_RQ117112", "application/json")]
    assert found.title == "Senior Development Systems Engineer"
    assert found.location == ("United States of America - Texas - Houston, "
                              "United States of America - Colorado - Denver")
    assert found.text == "Job Description\n\nbpx energy builds things.\n• SQL"


def test_greenhouse_and_lever_links_are_read_from_their_feeds(monkeypatch):
    monkeypatch.setattr(posting, "_get", lambda url, accept=None: (
        '{"title": "Analyst", "location": {"name": "Denver, CO"}, '
        '"content": "&lt;p&gt;Build &lt;b&gt;dashboards&lt;/b&gt;.&lt;/p&gt;"}'))
    found = posting.employer_posting("https://boards.greenhouse.io/acme/jobs/4012345")
    assert (found.title, found.location, found.text) == ("Analyst", "Denver, CO", "Build dashboards.")
    monkeypatch.setattr(posting, "_get", lambda url, accept=None: (
        '{"text": "Data Engineer", "categories": {"location": "Remote"}, '
        '"descriptionPlain": "Remote role.", "lists": [{"text": "Requirements", '
        '"content": "<li>Python</li><li>SQL</li>"}]}'))
    found = posting.employer_posting("https://jobs.lever.co/acme/0f8b1c2d-1234-4abc-9def-1234567890ab")
    assert (found.title, found.location) == ("Data Engineer", "Remote")
    assert found.text == "Remote role.\n\nRequirements\n• Python\n• SQL"


def test_other_links_and_unreadable_feeds_give_nothing_without_an_error(monkeypatch):
    monkeypatch.setattr(posting, "_get", lambda url, accept=None: pytest.fail("fetched"))
    assert posting.employer_posting("https://careers.acme.com/jobs/1") is None
    assert posting.employer_posting(None) is None
    monkeypatch.setattr(posting, "_get", lambda url, accept=None: "<html>not json</html>")
    assert posting.employer_posting("https://boards.greenhouse.io/acme/jobs/1") is None

    def refused(url, accept=None):
        raise posting.PostingError("The site answered 403 instead of the posting: paste it.")
    monkeypatch.setattr(posting, "_get", refused)
    assert posting.employer_posting("https://acme.wd5.myworkdayjobs.com/jobs/job/Denver/Analyst_R1") is None
