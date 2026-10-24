"""A job posting read from its web page, for tailoring the resume: the
title, employer, place and description as text.

LinkedIn hands anyone a guest copy of a posting (its jobs-guest endpoint),
which is what fetch() reads for a LinkedIn link. Indeed and Glassdoor
answer a server with 401 or 403, so those links come back as a
PostingError that says to paste the posting instead. Any other page is
read as it is: its JobPosting data (schema.org JSON-LD, which most career
sites and applicant-tracking systems publish) when it has it, else the
page's main text. Pure except fetch() and _get().
"""

import html
import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import lxml.etree
import lxml.html

import config
import logic

# A browser's headers: LinkedIn answers a bare client with an error page.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                   "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT_S = 20
GUEST = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"
REFUSES = {"indeed.com": "Indeed", "glassdoor.com": "Glassdoor"}   # answer a server with 401/403
PASTE = "open the link and paste the posting instead."
BLOCKS = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table",
          "section", "article", "header", "footer", "blockquote", "pre", "dd", "dt"}
DROP = {"script", "style", "nav", "noscript", "svg", "iframe", "button", "form", "head",
        "footer", "aside"}


class PostingError(Exception):
    """The posting couldn't be read; the message says what to do instead."""


@dataclass
class Posting:
    title: str
    company: str
    location: str
    text: str

    def as_text(self) -> str:
        """What goes in the application's posting box: a header line, then
        the description."""
        head = " — ".join(part for part in (self.title, self.company) if part)
        if self.location:
            head = f"{head} · {self.location}" if head else self.location
        return f"{head}\n\n{self.text}" if head else self.text


def fetch(url) -> Posting:
    """The posting behind a job link. Raises PostingError when there is no
    link, the site refuses, or the page carries no description."""
    link = logic.job_link(url)
    if not link:
        raise PostingError("This application has no posting link: paste the posting instead.")
    host = urlparse(link).netloc.lower()
    for domain, site in REFUSES.items():
        if host == domain or host.endswith("." + domain):
            raise PostingError(f"{site} doesn't let the app read its postings: {PASTE}")
    if job_id := re.search(r"linkedin\.com/jobs/view/(\d+)", link):
        posting = parse_linkedin(_get(GUEST.format(job_id.group(1))))
    else:
        posting = parse_page(_get(link))
    if len(posting.text) < config.POSTING_MIN_CHARS:
        raise PostingError(f"The page didn't give the app a job description: {PASTE}")
    return posting


def _get(url: str, accept: str = HEADERS["Accept"]) -> str:
    try:
        response = httpx.get(url, headers={**HEADERS, "Accept": accept}, timeout=TIMEOUT_S,
                             follow_redirects=True)
    except httpx.HTTPError as problem:
        raise PostingError(f"Couldn't reach the posting ({type(problem).__name__}): "
                           f"{PASTE}") from problem
    if response.status_code != 200:
        raise PostingError(f"The site answered {response.status_code} instead of the posting: "
                           f"{PASTE}")
    return response.text


# ---- the employer's own copy --------------------------------------------------

# The applicant-tracking systems whose postings come as data: the page's
# address, and the address of the data behind it (their pages are built in
# the browser, so reading the page itself gives nothing).
WORKDAY = re.compile(r"^https://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?"
                     r"([^/?#]+)/job/([^?#]+)")
GREENHOUSE = re.compile(r"^https://(?:boards|job-boards)\.greenhouse\.io/([^/?#]+)/jobs/(\d+)")
LEVER = re.compile(r"^https://jobs\.lever\.co/([^/?#]+)/([0-9a-f-]{36})")


def employer_posting(url) -> Posting | None:
    """The posting as the employer's site has it, from data rather than a
    page's loose text: a Workday, Greenhouse or Lever feed, or any other
    page's JobPosting data. None when there is none, or it can't be read
    (the link is still worth keeping)."""
    url = str(url or "").strip()
    if not url.startswith("http") or logic.is_job_board(url):   # a board is not the employer
        return None
    try:
        if match := WORKDAY.match(url):
            tenant, _, site, rest = match.groups()
            data = _json(f"https://{tenant}.{match.group(2)}.myworkdayjobs.com/wday/cxs/{tenant}"
                         f"/{site}/job/{rest}")
            info = data.get("jobPostingInfo") or {}
            places = [info.get("location")] + list(info.get("additionalLocations") or [])
            return _from_html(str(info.get("title") or ""), "",
                              " / ".join(_workday_place(p) for p in places if p),
                              info.get("jobDescription"))
        if match := GREENHOUSE.match(url):
            board, job_id = match.groups()
            data = _json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}")
            return _from_html(str(data.get("title") or ""), "",
                              str((data.get("location") or {}).get("name") or ""),
                              html.unescape(str(data.get("content") or "")))
        if match := LEVER.match(url):
            company, posting_id = match.groups()
            data = _json(f"https://api.lever.co/v0/postings/{company}/{posting_id}")
            parts = [str(data.get("descriptionPlain") or "")]
            for block in data.get("lists") or []:
                parts.append(f"{block.get('text', '')}\n"
                             + text_of(lxml.html.fromstring(f"<ul>{block.get('content', '')}</ul>")))
            return Posting(str(data.get("text") or ""), "",
                           str((data.get("categories") or {}).get("location") or ""),
                           "\n\n".join(p for p in parts if p.strip())[:config.POSTING_MAX_CHARS])
        return _structured(lxml.html.fromstring(_get(url)))
    except (PostingError, ValueError, AttributeError, TypeError, lxml.etree.ParserError):
        return None


def from_links(job_url, apply_url) -> tuple[Posting, str]:
    """The posting from an application's links, and the link it came from:
    the employer's own data first (employer_posting), then the job link
    (fetch), then the employer's page read as a page. Raises the job link's
    PostingError (the employer page's, without one) when none gives a
    description."""
    links = [link for link in (logic.job_link(apply_url), logic.job_link(job_url)) if link]
    if not links:
        raise PostingError("This application has no posting link: paste the posting instead.")
    if links[0] == logic.job_link(apply_url) and (found := employer_posting(links[0])):
        if len(found.text) >= config.POSTING_MIN_CHARS:
            return found, links[0]
    problems = []
    for link in reversed(links):                     # the job link, then the employer's page
        try:
            return fetch(link), link
        except PostingError as problem:
            problems.append(problem)
    raise problems[0]


def _workday_place(text) -> str:
    """Workday's "Country - State - City" as "City, State"; anything else as is."""
    parts = [part.strip() for part in str(text).split(" - ")]
    return f"{parts[2]}, {parts[1]}" if len(parts) == 3 else str(text).strip()


def _json(url: str) -> dict:
    data = json.loads(_get(url, accept="application/json"))
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def _from_html(title: str, company: str, location: str, description) -> Posting:
    text = text_of(lxml.html.fromstring(f"<div>{description}</div>")) if description else ""
    return Posting(title, company, location, text)


# ---- reading pages ----------------------------------------------------------

def parse_linkedin(html: str) -> Posting:
    """LinkedIn's guest copy of a posting."""
    doc = lxml.html.fromstring(html)
    description = doc.xpath('//div[contains(@class, "show-more-less-html__markup")]')
    if not description:
        raise PostingError(f"LinkedIn didn't hand over the posting this time: {PASTE}")
    return Posting(
        title=_first(doc, '//h2[contains(@class, "top-card-layout__title")]', "//h1"),
        company=_first(doc, '//a[contains(@class, "topcard__org-name-link")]'),
        location=_first(doc, '//span[contains(@class, "topcard__flavor--bullet")]'),
        text=text_of(description[0]),
    )


def parse_page(html: str) -> Posting:
    """Any other job page: its JobPosting data when it publishes some, else
    the page's main text under its heading."""
    doc = lxml.html.fromstring(html)
    if (found := _structured(doc)) is not None:
        return found
    title = _first(doc, "//h1", "//title")
    for tag in DROP:
        for element in doc.xpath(f"//{tag}"):
            element.drop_tree()
    main = doc.xpath("//main") or doc.xpath("//article") or doc.xpath("//body") or [doc]
    return Posting(title=title, company="", location="", text=text_of(main[0]))


def _structured(doc) -> Posting | None:
    """A page's JobPosting data (JSON-LD), as search engines read it; None
    when the page publishes none."""
    for script in doc.xpath('//script[contains(@type, "ld+json")]'):
        if (job := _job_posting(script.text)) is not None:
            organisation = job.get("hiringOrganization")
            place = job.get("jobLocation")
            if isinstance(place, list):
                place = place[0] if place else None
            address = place.get("address", {}) if isinstance(place, dict) else {}
            if not isinstance(address, dict):
                address = {}
            return Posting(
                title=str(job.get("title") or ""),
                company=(organisation.get("name", "") if isinstance(organisation, dict)
                         else str(organisation or "")),
                location=", ".join(str(address[k]) for k in ("addressLocality", "addressRegion")
                                   if address.get(k)),
                text=text_of(lxml.html.fromstring(f"<div>{job.get('description') or ''}</div>")),
            )
    return None


def _job_posting(text) -> dict | None:
    """The JobPosting object in a JSON-LD script, if it is one."""
    try:
        found = json.loads(text or "")
    except ValueError:
        return None
    items = found if isinstance(found, list) else [found]
    if isinstance(found, dict) and isinstance(found.get("@graph"), list):
        items = found["@graph"]
    for item in items:
        if isinstance(item, dict) and item.get("@type") == "JobPosting":
            return item
    return None


def _first(doc, *xpaths: str) -> str:
    for xpath in xpaths:
        for element in doc.xpath(xpath):
            if text := " ".join(element.text_content().split()):
                return text
    return ""


def _spaced(text: str) -> str:
    """A page's own line breaks and runs of spaces are one space, as a
    browser shows them (the breaks that matter come from the tags)."""
    return re.sub(r"\s+", " ", text)


def text_of(element) -> str:
    """The element's text with line breaks where the page had them (block
    elements, <br>, list items as bullets), whitespace tidied, capped at
    config.POSTING_MAX_CHARS."""
    parts: list[str] = []

    def walk(node) -> None:
        if not isinstance(node.tag, str):          # a comment
            return
        tag = node.tag.lower()
        if tag in DROP:
            return
        if tag == "br" or tag in BLOCKS:
            parts.append("\n")
        if tag == "li":
            parts.append("• ")
        if node.text:
            parts.append(_spaced(node.text))
        for child in node:
            walk(child)
            if child.tail:
                parts.append(_spaced(child.tail))
        if tag in BLOCKS:
            parts.append("\n")

    walk(element)
    text = re.sub(r" *\n *", "\n", "".join(parts))
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n\n(• )", r"\n\1", text)         # list items stay together
    return text.strip()[:config.POSTING_MAX_CHARS]
