"""Word files for the resume tools: reading an uploaded file as text with
its structure (for Claude), and writing the master resume's data back into a
Word file modelled on the owner's own resume. No database, no Streamlit.

The writer never styles anything itself. It finds one example of each kind
of paragraph in the template (the heading with the rule under it, an
employer line, a title-and-dates line, a bullet, ...), copies it, and swaps
the text, so fonts, sizes, indents, bullets and the two-column layout stay
exactly as the owner had them."""

import copy
import io
import re
from dataclasses import dataclass

from docx import Document
from docx.oxml.ns import qn

import logic

DATE_RANGE = re.compile(r"\b(?:19|20)\d{2}\b.*?(?:-|–|—).*?(?:\b(?:19|20)\d{2}\b|present)", re.I)
DEFAULT_COLUMN_TWIPS = 6840          # the left column's width when the template doesn't say


@dataclass(frozen=True)
class Para:
    text: str
    style: str              # the style id: "Normal", "NoSpacing", "ListParagraph"
    bullet: bool
    bold: bool
    column_break: bool


# ---- reading ----------------------------------------------------------------

def _paragraphs(data: bytes):
    doc = Document(io.BytesIO(data))
    return doc, doc.element.body.findall(qn("w:p"))


def _text(p) -> str:
    return "".join(t.text or "" for t in p.iter(qn("w:t")))


def _style(p) -> str:
    style = p.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    return style.get(qn("w:val")) if style is not None else "Normal"


def _bold(p) -> bool:
    runs = p.findall(qn("w:r"))
    return any(r.find(f"{qn('w:rPr')}/{qn('w:b')}") is not None for r in runs
               if "".join(t.text or "" for t in r.iter(qn("w:t"))).strip())


def _bullet(p) -> bool:
    return p.find(f".//{qn('w:numPr')}") is not None


def _column_break(p) -> bool:
    return any(br.get(qn("w:type")) == "column" for br in p.iter(qn("w:br")))


def outline(data: bytes) -> list[Para]:
    """Every paragraph of a Word file, in order."""
    _, paras = _paragraphs(data)
    return [Para(_text(p).strip(), _style(p), _bullet(p), _bold(p), _column_break(p))
            for p in paras]


def text(data: bytes) -> str:
    """The file as plain lines for Claude: bullets start with "- ", bold
    lines (headings, employers, titles) with "## ", the rest as they are."""
    lines = []
    for para in outline(data):
        if not para.text:
            continue
        if para.bullet:
            lines.append(f"- {para.text}")
        elif para.bold:
            lines.append(f"## {para.text}")
        else:
            lines.append(para.text)
    return "\n".join(lines)


# ---- writing ----------------------------------------------------------------

KINDS = ("header", "section", "spacer", "column_break", "employer", "title", "bullet",
         "bold_line", "plain_line")


def _examples(paras) -> dict:
    """One template paragraph of each kind, found by its shape."""
    found: dict = {}
    for i, p in enumerate(paras):
        if i == 0:
            found.setdefault("header", p)
            continue
        if _column_break(p):
            found.setdefault("column_break", p)
            continue
        stripped = _text(p).strip()
        if not stripped:
            found.setdefault("spacer", p)
            continue
        style = _style(p)
        if style == "NoSpacing":
            if p.find(f"{qn('w:pPr')}/{qn('w:pBdr')}") is not None:
                found.setdefault("section", p)
            elif _bullet(p):
                found.setdefault("project_bullet", p)
            elif _bold(p):
                found.setdefault("bold_line", p)
                if "|" in stripped and len(p.findall(qn("w:r"))) >= 2:
                    found.setdefault("school_line", p)
            else:
                found.setdefault("plain_line", p)
        elif _bullet(p):
            found.setdefault("bullet", p)
        elif DATE_RANGE.search(stripped):
            found.setdefault("title", p)
        elif _bold(p):
            found.setdefault("employer", p)
    missing = [kind for kind in KINDS if kind not in found]
    if missing:
        raise ValueError("the template lacks an example of: " + ", ".join(missing))
    found.setdefault("project_bullet", found["bullet"])
    found.setdefault("school_line", found["bold_line"])
    return found


def _lead(p) -> str:
    """The leading spaces the template indents a line with."""
    raw = _text(p)
    return raw[:len(raw) - len(raw.lstrip(" "))]


def _set_run_text(run, value: str) -> None:
    for child in list(run):
        if child.tag in (qn("w:t"), qn("w:tab"), qn("w:br")):
            run.remove(child)
    for n, piece in enumerate(value.split("\t")):
        if n:
            run.append(run.makeelement(qn("w:tab"), {}))
        t = run.makeelement(qn("w:t"), {})
        t.text = piece
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        run.append(t)


def _run_bold(run) -> bool:
    return run.find(f"{qn('w:rPr')}/{qn('w:b')}") is not None


def _prototype(example, bold: bool | None):
    """A run of the template paragraph to model a piece of text on: the first
    run with visible text and the wanted weight (any weight when bold is
    None), else the first run with text, else the first run."""
    runs = example.findall(qn("w:r"))
    with_text = [r for r in runs if "".join(t.text or "" for t in r.iter(qn("w:t"))).strip()]
    for run in with_text:
        if bold is None or _run_bold(run) == bold:
            return run
    return with_text[0] if with_text else runs[0]


def _clone(example, pieces: list[tuple[str, bool | None]]):
    """A copy of a template paragraph carrying new text: each (text, bold)
    piece becomes a run modelled on a run of the example with that weight,
    so an employer stays bold and a date stays regular."""
    p = copy.deepcopy(example)
    for run in p.findall(qn("w:r")):
        p.remove(run)
    for value, bold in pieces:
        run = copy.deepcopy(_prototype(example, bold))
        _set_run_text(run, value)
        p.append(run)
    return p


def _set_right_tab(p, twips: int) -> None:
    for tab in p.iter(qn("w:tab")):
        if tab.get(qn("w:val")) == "right":
            tab.set(qn("w:pos"), str(twips))


def _column_width(body) -> int:
    sect = body.find(qn("w:sectPr"))
    col = None if sect is None else sect.find(f"{qn('w:cols')}/{qn('w:col')}")
    return int(col.get(qn("w:w"))) if col is not None and col.get(qn("w:w")) else DEFAULT_COLUMN_TWIPS


def build(template: bytes, content: dict) -> bytes:
    """The master resume (resume_schema.Resume as a dict; bullets with
    in_master only, and only roles and projects that have one) as a Word
    file modelled on the template."""
    doc, paras = _paragraphs(template)
    body = doc.element.body
    ex = _examples(paras)
    lead = {kind: _lead(ex[kind]) for kind in ("employer", "title", "bold_line", "plain_line")}
    column = _column_width(body)
    end = body.find(qn("w:sectPr"))

    header = ex["header"]
    contact = " • ".join(v for v in (content.get("email"), content.get("phone"),
                                      content.get("linkedin")) if v)
    runs = [r for r in header.findall(qn("w:r"))
            if "".join(t.text or "" for t in r.iter(qn("w:t"))).strip()]
    new = copy.deepcopy(header)
    for run in new.findall(qn("w:r")):
        new.remove(run)
    name_run = copy.deepcopy(runs[0]) if runs else copy.deepcopy(_prototype(header, None))
    _set_run_text(name_run, content.get("name", ""))
    new.append(name_run)
    if contact:
        model = next((r for r in runs if "@" in _text(r)), runs[-1] if runs else name_run)
        contact_run = copy.deepcopy(model)
        _set_run_text(contact_run, "    " + contact)
        new.append(contact_run)
    body.replace(header, new)
    for p in paras[1:]:
        body.remove(p)

    out = []

    def section(title: str, first: bool = False) -> None:
        if not first:
            out.append(copy.deepcopy(ex["spacer"]))
        out.append(_clone(ex["section"], [(title, True)]))
        out.append(copy.deepcopy(ex["spacer"]))

    section("Experience", first=True)
    for role in content.get("roles", []):
        if not logic.prints(role):             # nothing ticked: the role stays off the page
            continue
        out.append(_clone(ex["employer"], [(lead["employer"] + role["employer"], True)]))
        where = " – ".join(v for v in (role.get("title"), role.get("location")) if v)
        when = " - ".join(v for v in (role.get("start"), role.get("end")) if v)
        line = _clone(ex["title"], [(lead["title"] + where + ("\t" + when if when else ""), False)])
        _set_right_tab(line, column)
        out.append(line)
        for bullet in role.get("bullets", []):
            if bullet.get("in_master"):
                out.append(_clone(ex["bullet"], [(bullet["text"], None)]))

    out.append(copy.deepcopy(ex["column_break"]))
    section("Education", first=True)
    for edu in content.get("education", []):
        when = f"| {edu['when']}" if edu.get("when") else ""
        out.append(_clone(ex["school_line"], [(lead["bold_line"] + edu["school"] + " ", True),
                                              (when, False)]))
        if edu.get("degree"):
            out.append(_clone(ex["plain_line"], [(lead["plain_line"] + edu["degree"], False)]))
    section("Applicable Skills")
    for group in content.get("skill_groups", []):
        out.append(_clone(ex["bold_line"], [(lead["bold_line"] + group["name"], True)]))
        out.append(_clone(ex["plain_line"], [(lead["plain_line"] + group["skills"], False)]))
    projects = [p for p in content.get("projects", []) if logic.prints(p)]
    if projects:
        section("Personal Projects")
        for project in projects:
            out.append(_clone(ex["bold_line"], [(lead["bold_line"] + project["employer"], True)]))
            for bullet in project.get("bullets", []):
                if bullet.get("in_master"):
                    out.append(_clone(ex["project_bullet"], [(bullet["text"], None)]))

    for p in out:
        end.addprevious(p)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
