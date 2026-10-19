"""Reading a Word file as text, and writing the master back in its layout."""

import pytest
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Twips
from docx.text.paragraph import Paragraph

import docx_fixture
import docx_io


def test_a_word_file_reads_as_lines_with_its_structure():
    text = docx_io.text(docx_fixture.template())
    lines = text.splitlines()
    assert lines[0].startswith("## Sample Person")
    assert "## Experience" in lines and "## Sample Employer" in lines
    assert "- Did a thing that mattered" in lines and "- A project bullet" in lines
    assert "B.S. in Something | 4.00/4.00" in lines         # plain lines stay plain, trimmed
    assert "" not in lines                                   # blanks and the column break dropped


def test_the_outline_sees_bullets_bold_and_the_column_break():
    paras = docx_io.outline(docx_fixture.template())
    kinds = [(p.style, p.bullet, p.bold, p.column_break) for p in paras if p.text or p.column_break]
    assert ("ListParagraph", True, False, False) in kinds
    assert ("NoSpacing", False, False, True) in kinds
    assert any(p.style == "Normal" and p.bold and p.text == "Sample Employer" for p in paras)


def test_the_master_is_written_in_the_templates_layout():
    out = docx_io.build(docx_fixture.template(), docx_fixture.SAMPLE)
    paras = [p for p in docx_io.outline(out) if p.text or p.column_break]
    texts = [p.text for p in paras]
    assert texts[0].startswith("Sample Person") and "sample@example.com • 555-0100" in texts[0]
    assert texts[1:4] == ["Experience", "Acme Energy",
                          "Business Analyst – Denver, CO\tJan 2025 - Present"]
    assert "Built a pipeline that saved 2 hours a day." in texts
    assert "Pool bullet, not on the master." not in texts              # in_master False
    pool_only = {**docx_fixture.SAMPLE,
                 "roles": docx_fixture.SAMPLE["roles"] + [{
                     "employer": "Gamma Corp", "title": "Analyst", "location": "Remote",
                     "start": "Jan 2024", "end": "Dec 2024", "bullets": [
                         {"text": "Pool only.", "skills": [], "source": "history", "rank": 2,
                          "in_master": False}]}],
                 "projects": [{**docx_fixture.SAMPLE["projects"][0], "bullets": []}]}
    pool_texts = [p.text for p in docx_io.outline(docx_io.build(docx_fixture.template(),
                                                                pool_only))]
    assert "Gamma Corp" not in pool_texts and "Pool only." not in pool_texts   # nothing ticked
    assert "Personal Projects" not in pool_texts                               # no project prints
    assert texts.index("Beta Chemicals") > texts.index("Acme Energy")   # order kept
    column_breaks = [p for p in paras if p.column_break]
    assert len(column_breaks) == 1
    after_break = texts[paras.index(column_breaks[0]) + 1:]
    assert after_break[:3] == ["Education", "Sample University | May 2026",
                               "M.S. in Data Science | 3.90/4.00"]
    assert after_break[3:5] == ["Applicable Skills", "Programming Languages"]
    assert after_break[-3:] == ["Personal Projects", "Workout Analyzer", "Developed a tool."]
    bullets = [p for p in paras if p.bullet]
    assert [p.text for p in bullets] == ["Built a pipeline that saved 2 hours a day.",
                                         "Led projects.", "Developed a tool."]
    assert bullets[0].style == "ListParagraph" and bullets[-1].style == "NoSpacing"


def test_weights_tabs_and_indents_follow_the_template():
    out = docx_io.build(docx_fixture.template(), docx_fixture.SAMPLE)
    _, paras = docx_io._paragraphs(out)

    def runs(p):
        return [("".join(t.text or "" for t in r.iter(qn("w:t"))), docx_io._run_bold(r))
                for r in p.findall(qn("w:r"))]

    def indent(p):
        return Paragraph(p, None).paragraph_format.left_indent

    by_text = {docx_io._text(p).strip(): p for p in paras}
    assert runs(by_text["Acme Energy"]) == [("Acme Energy", True)]
    assert indent(by_text["Acme Energy"]) == Twips(100)             # the template's 2 spaces
    school = runs(by_text["Sample University | May 2026"])
    assert school == [("Sample University ", True), ("| May 2026", False)]
    assert indent(by_text["Sample University | May 2026"]) == Twips(100)
    assert indent(by_text["M.S. in Data Science | 3.90/4.00"]) == Twips(200)     # 4 spaces
    assert indent(by_text["Built a pipeline that saved 2 hours a day."]) is None  # bullets as is
    title = by_text["Business Analyst – Denver, CO\tJan 2025 - Present"]
    assert runs(title) == [("Business Analyst – Denver, COJan 2025 - Present", False)]
    assert indent(title) == Twips(200)
    run = title.findall(qn("w:r"))[0]
    assert [c.tag for c in run if c.tag != qn("w:rPr")] == [qn("w:t"), qn("w:tab"), qn("w:t")]
    assert title.find(f"{qn('w:pPr')}/{qn('w:tabs')}/{qn('w:tab')}[@{qn('w:val')}='right']").get(
        qn("w:pos")) == "6840"                                  # dates right-align to the column
    assert by_text["Experience"].find(f"{qn('w:pPr')}/{qn('w:pBdr')}") is not None


def test_a_template_without_the_needed_examples_is_refused():
    import io

    from docx import Document
    doc = Document()
    doc.add_paragraph("Just a line")
    buffer = io.BytesIO()
    doc.save(buffer)
    with pytest.raises(ValueError, match="lacks an example of"):
        docx_io.build(buffer.getvalue(), docx_fixture.SAMPLE)


def test_headings_employers_and_long_lines_follow_the_templates_habits():
    same_employer = {**docx_fixture.SAMPLE, "roles": [
        docx_fixture.SAMPLE["roles"][0],
        {**docx_fixture.SAMPLE["roles"][1], "employer": "Acme Energy", "title": "Analyst"}],
        "skill_groups": [{"name": "Languages", "skills": ", ".join(
            f"Tool{n}" for n in range(1, 20))}]}
    paras = docx_io.outline(docx_io.build(docx_fixture.template(), same_employer))
    texts = [p.text for p in paras]
    assert texts.count("Acme Energy") == 1                   # one employer line for both roles
    assert texts.index("Analyst – Houston, TX\tJun 2023 - Dec 2024") > texts.index(
        "Built a pipeline that saved 2 hours a day.")                  # second role after the first
    assert texts[texts.index("Experience") + 1] == "Acme Energy"          # no blank after
    assert texts[texts.index("Experience") - 1] == ""                     # a blank before
    skills = texts.index("Applicable Skills")
    assert texts[skills - 1] == "" and texts[skills + 1] == "Languages"
    assert texts[texts.index("Education") - 1] == ""                     # the column break
    assert paras[texts.index("Education") - 1].column_break
    lines = [t for t in texts if t.startswith("Tool")]
    assert lines == [same_employer["skill_groups"][0]["skills"]]     # one line; Word wraps it


def test_a_letter_keeps_the_header_in_one_column():
    out = docx_io.letter(docx_fixture.template(), "Sample Person", "sample@example.com",
                         ["Dear Hiring Team,", "I built things.", "Sincerely,\nSample Person"])
    paras = docx_io.outline(out)
    texts = [p.text for p in paras if p.text]
    assert texts[0] == "Sample Person\tsample@example.com"             # a tab, not spaces
    header = next(p for p in paras if p.text.startswith("Sample Person"))
    assert header.style == "NoSpacing"
    assert texts[1:] == ["Dear Hiring Team,", "I built things.", "Sincerely,\nSample Person"]
    doc, raw = docx_io._paragraphs(out)
    assert raw[-1].find(f"{qn('w:r')}/{qn('w:br')}") is not None          # a real line break
    assert not any(p.column_break for p in paras) and not any(p.bullet for p in paras)
    cols = doc.element.body.find(qn("w:sectPr")).find(qn("w:cols"))
    assert cols.get(qn("w:num")) == "1" and len(cols) == 0
    stops = Paragraph(raw[0], None).paragraph_format.tab_stops
    page = doc.sections[-1]
    assert [(stop.alignment, stop.position) for stop in stops] == [
        (WD_TAB_ALIGNMENT.RIGHT, page.page_width - page.left_margin - page.right_margin)]
