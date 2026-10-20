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

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
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


def _get(url: str) -> str:
    try:
        response = httpx.get(url, headers=HEADERS, timeout=TIMEOUT_S, follow_redirects=True)
    except httpx.HTTPError as problem:
        raise PostingError(f"Couldn't reach the posting ({type(problem).__name__}): "
                           f"{PASTE}") from problem
    if response.status_code != 200:
        raise PostingError(f"The site answered {response.status_code} instead of the posting: "
                           f"{PASTE}")
    return response.text


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
    title = _first(doc, "//h1", "//title")
    for tag in DROP:
        for element in doc.xpath(f"//{tag}"):
            element.drop_tree()
    main = doc.xpath("//main") or doc.xpath("//article") or doc.xpath("//body") or [doc]
    return Posting(title=title, company="", location="", text=text_of(main[0]))


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
