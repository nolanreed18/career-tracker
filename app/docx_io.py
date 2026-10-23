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
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Twips
from docx.text.paragraph import Paragraph

import logic

DATE_RANGE = re.compile(r"\b(?:19|20)\d{2}\b.*?(?:-|–|—).*?(?:\b(?:19|20)\d{2}\b|present)", re.I)
DEFAULT_COLUMN_TWIPS = 6840          # the left column's width when the template doesn't say
DEFAULT_TEXT_WIDTH_TWIPS = 10620     # margin to margin, when the template doesn't say
TWIPS_PER_SPACE = 50                 # a typed space of 10-11pt text, as a paragraph indent
BULLET_INDENT_TWIPS = 720            # Word's list indent: a bullet's text starts this far in
CHAR_EMS = 0.4                       # an average character of body text, in ems
DEFAULT_HALF_POINTS = 22             # 11pt, when a bullet's run doesn't say its size


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
    """The text of a paragraph or run; a line break inside it as a newline."""
    parts = []
    for node in p.iter():
        if node.tag == qn("w:t"):
            parts.append(node.text or "")
        elif node.tag == qn("w:br") and node.get(qn("w:type")) != "column":
            parts.append("\n")
        elif node.tag == qn("w:tab") and node.getparent().tag == qn("w:r"):
            parts.append("\t")
    return "".join(parts)


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
    for n, line in enumerate(value.split("\n")):
        if n:
            run.append(run.makeelement(qn("w:br"), {}))
        for m, piece in enumerate(line.split("\t")):
            if m:
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


def _clone(example, pieces: list[tuple[str, bool | None]], lead: str = ""):
    """A copy of a template paragraph carrying new text: each (text, bold)
    piece becomes a run modelled on a run of the example with that weight,
    so an employer stays bold and a date stays regular. Where the template
    indented the line with typed spaces (lead), the copy gets a paragraph
    indent of the same width instead, so wrapped lines align and nobody
    has to count spaces when editing."""
    p = copy.deepcopy(example)
    for run in p.findall(qn("w:r")):
        p.remove(run)
    for value, bold in pieces:
        run = copy.deepcopy(_prototype(example, bold))
        _set_run_text(run, value)
        p.append(run)
    if lead:
        Paragraph(p, None).paragraph_format.left_indent = Twips(len(lead) * TWIPS_PER_SPACE)
    return p


def _set_right_tab(p, twips: int) -> None:
    for tab in p.iter(qn("w:tab")):
        if tab.get(qn("w:val")) == "right":
            tab.set(qn("w:pos"), str(twips))


def _column_width(body) -> int:
    sect = body.find(qn("w:sectPr"))
    col = None if sect is None else sect.find(f"{qn('w:cols')}/{qn('w:col')}")
    return int(col.get(qn("w:w"))) if col is not None and col.get(qn("w:w")) else DEFAULT_COLUMN_TWIPS


def _header(header, name: str, contact: str, width: int):
    """The template's name-and-contact line carrying a new name and contact:
    the name run, then one run modelled on the contact's, pushed to the
    right margin by a tab stop (the template typed spaces; a tab stop
    lands at the margin whatever the name's length)."""
    runs = header.findall(qn("w:r"))
    with_text = [r for r in runs if _text(r).strip()]
    new = copy.deepcopy(header)
    for run in new.findall(qn("w:r")):
        new.remove(run)
    name_run = copy.deepcopy(with_text[0]) if with_text else copy.deepcopy(_prototype(header, None))
    _set_run_text(name_run, name)
    new.append(name_run)
    if contact:
        model = next((r for r in with_text if "@" in _text(r)), with_text[-1] if with_text else name_run)
        contact_run = copy.deepcopy(model)
        _set_run_text(contact_run, "\t" + contact)
        new.append(contact_run)
        Paragraph(new, None).paragraph_format.tab_stops.add_tab_stop(
            Twips(width), WD_TAB_ALIGNMENT.RIGHT)
    return new


def _half_points(p) -> int:
    """The font size of a paragraph's first run, in half-points."""
    run = p.find(qn("w:r"))
    size = None if run is None else run.find(f"{qn('w:rPr')}/{qn('w:sz')}")
    value = None if size is None else size.get(qn("w:val"))
    return int(value) if value and value.isdigit() else DEFAULT_HALF_POINTS


def line_chars(template: bytes) -> int:
    """About how many characters one line of a bullet holds in the
    template's left column: its width less the list indent, over an average
    character at the bullet's font size (a half-point is ten twips)."""
    doc, paras = _paragraphs(template)
    bullet = next((p for p in paras[1:] if _bullet(p)), None)
    char = (DEFAULT_HALF_POINTS if bullet is None else _half_points(bullet)) * 10 * CHAR_EMS
    return max(20, int((_column_width(doc.element.body) - BULLET_INDENT_TWIPS) / char))


def _text_width(*sections) -> int:
    """Margin to margin, from the first section that says its page size."""
    for sect in sections:
        size = None if sect is None else sect.find(qn("w:pgSz"))
        margins = None if sect is None else sect.find(qn("w:pgMar"))
        if size is not None and margins is not None and size.get(qn("w:w")):
            left = margins.get(qn("w:left")) or margins.get(qn("w:start")) or "0"
            right = margins.get(qn("w:right")) or margins.get(qn("w:end")) or "0"
            return int(size.get(qn("w:w"))) - int(left) - int(right)
    return DEFAULT_TEXT_WIDTH_TWIPS


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

    width = _text_width(ex["header"].find(f"{qn('w:pPr')}/{qn('w:sectPr')}"), end)
    body.replace(ex["header"], _header(ex["header"], content.get("name", ""),
                                       logic.contact_line(content), width))
    for p in paras[1:]:
        body.remove(p)

    out = []

    def section(title: str, spacer_before: bool = True) -> None:
        if spacer_before:
            out.append(copy.deepcopy(ex["spacer"]))
        out.append(_clone(ex["section"], [(title, True)]))

    section("Experience")
    last_employer = None
    for role in logic.roles_by_date(content.get("roles", [])):     # newest first
        if not logic.prints(role):             # nothing ticked: the role stays off the page
            continue
        if role["employer"] != last_employer:  # one employer line for roles there in a row
            out.append(_clone(ex["employer"], [(role["employer"], True)], lead["employer"]))
            last_employer = role["employer"]
        where = " – ".join(v for v in (role.get("title"), role.get("location")) if v)
        when = " - ".join(v for v in (role.get("start"), role.get("end")) if v)
        line = _clone(ex["title"], [(where + ("\t" + when if when else ""), False)], lead["title"])
        _set_right_tab(line, column)
        out.append(line)
        for bullet in role.get("bullets", []):
            if bullet.get("in_master"):
                out.append(_clone(ex["bullet"], [(bullet["text"], None)]))

    out.append(copy.deepcopy(ex["column_break"]))
    section("Education", spacer_before=False)
    for edu in content.get("education", []):
        when = f"| {edu['when']}" if edu.get("when") else ""
        out.append(_clone(ex["school_line"], [(edu["school"] + " ", True), (when, False)],
                          lead["bold_line"]))
        if edu.get("degree"):
            out.append(_clone(ex["plain_line"], [(edu["degree"], False)], lead["plain_line"]))
    section("Applicable Skills")
    for group in content.get("skill_groups", []):
        out.append(_clone(ex["bold_line"], [(group["name"], True)], lead["bold_line"]))
        out.append(_clone(ex["plain_line"], [(group["skills"], False)], lead["plain_line"]))
    projects = [p for p in content.get("projects", []) if logic.prints(p)]
    if projects:
        section("Personal Projects")
        for project in projects:
            out.append(_clone(ex["bold_line"], [(project["employer"], True)], lead["bold_line"]))
            for bullet in project.get("bullets", []):
                if bullet.get("in_master"):
                    out.append(_clone(ex["project_bullet"], [(bullet["text"], None)]))

    for p in out:
        end.addprevious(p)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def letter(template: bytes, name: str, contact: str, paragraphs: list[str]) -> bytes:
    """A letter in the template's look: its name-and-contact line, then the
    paragraphs as plain lines (a blank line between), in one column."""
    doc, paras = _paragraphs(template)
    body = doc.element.body
    ex = _examples(paras)
    end = body.find(qn("w:sectPr"))
    width = _text_width(ex["header"].find(f"{qn('w:pPr')}/{qn('w:sectPr')}"), end)
    body.replace(ex["header"], _header(ex["header"], name, contact, width))
    for p in paras[1:]:
        body.remove(p)
    cols = end.find(qn("w:cols"))
    if cols is not None:                       # the resume's two columns become one
        for col in list(cols):
            cols.remove(col)
        cols.set(qn("w:num"), "1")
        cols.attrib.pop(qn("w:equalWidth"), None)
    for text in paragraphs:
        end.addprevious(copy.deepcopy(ex["spacer"]))
        end.addprevious(_clone(ex["plain_line"], [(text, False)]))
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
