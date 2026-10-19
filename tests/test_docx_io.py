"""Reading a Word file as text, and writing the master back in its layout."""

import pytest
from docx.oxml.ns import qn

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
    assert texts[1:4] == ["Experience", "Acme Energy", "Business Analyst – Denver, CO"
                          "Jan 2025 - Present"]
    assert "Built a pipeline that saved 2 hours a day." in texts
    assert "Pool bullet, not on the master." not in texts              # in_master False
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

    by_text = {docx_io._text(p).strip(): p for p in paras}
    assert runs(by_text["Acme Energy"]) == [("  Acme Energy", True)]           # indent kept
    school = runs(by_text["Sample University | May 2026"])
    assert school == [("  Sample University ", True), ("| May 2026", False)]
    title = by_text["Business Analyst – Denver, COJan 2025 - Present"]
    assert runs(title) == [("    Business Analyst – Denver, COJan 2025 - Present", False)]
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
