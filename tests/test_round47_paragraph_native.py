"""Round 4.7 regressions for paragraph-native source-format layout."""

from __future__ import annotations

from zipfile import ZipFile

from docx import Document
from lxml import etree

from tender_basic.document_models import DocumentBlock, PdfTextLine, PdfTextSpan
from tender_basic.models import PdfLocator
from tender_basic.source_format import _block_alignment
from tender_basic.word_safe_source_builder import build_source_format_docx
from tender_basic.layout_qa import docx_layout_counts
from tender_basic.word_safe_scan import scan_word_safe_docx

from test_review_builder import make_project_facts
from test_round46_form_layout import _paragraph, _template
from test_source_format_fidelity import _table_template


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = {"w": W_NS}


def _xml(path):
    with ZipFile(path) as archive:
        return etree.fromstring(archive.read("word/document.xml"))


def _line(text, bbox, order=0):
    span = PdfTextSpan(
        text=text,
        bbox=bbox,
        font_name="SimSun",
        font_size=10.5,
        source_order=order,
    )
    return PdfTextLine(text=text, bbox=bbox, spans=[span], source_order=order)


def test_paragraph_position_uses_indent_and_vertical_gap_uses_spacing(tmp_path):
    first = _paragraph("第一段正文。", bbox=(96.0, 80.0, 240.0, 92.0))
    second = _paragraph("第二段正文。", block=1, bbox=(96.0, 150.0, 240.0, 162.0))
    output, report = build_source_format_docx(
        make_project_facts(), _template([first, second]), tmp_path / "position.docx"
    )
    document = Document(output)
    assert len(document.tables) == 0
    assert document.paragraphs[0].paragraph_format.left_indent.pt == 78.0
    assert document.paragraphs[1].paragraph_format.space_before.pt > 0
    assert report["synthetic_layout_tables"] == 0
    assert report["paragraph_layout_count"] == 2


def test_center_title_and_left_addressee_are_native_paragraphs(tmp_path):
    title = _paragraph("响应文件", bbox=(200.0, 80.0, 395.0, 98.0))
    title.alignment = "center"
    addressee = _paragraph("致：采购人", block=1, bbox=(72.0, 130.0, 180.0, 142.0))
    output, _ = build_source_format_docx(
        make_project_facts(), _template([title, addressee]), tmp_path / "align.docx"
    )
    document = Document(output)
    assert len(document.tables) == 0
    assert document.paragraphs[0].alignment == 1  # WD_ALIGN_PARAGRAPH.CENTER
    assert document.paragraphs[0].paragraph_format.left_indent.pt == 0
    assert document.paragraphs[1].alignment == 0  # WD_ALIGN_PARAGRAPH.LEFT


def test_geometry_backed_justified_narrative_is_not_a_positioning_hack(tmp_path):
    line1 = "本段正文具有足够长度并使用共同的右侧边界。"
    line2 = "这是最后一行。"
    paragraph = _paragraph(
        line1 + "\n" + line2,
        bbox=(72.0, 80.0, 570.0, 112.0),
        lines=[_line(line1, (72.0, 80.0, 570.0, 92.0)), _line(line2, (72.0, 100.0, 180.0, 112.0), 1)],
        runs=[
            _paragraph(line1, bbox=(72.0, 80.0, 570.0, 92.0)).runs[0],
            _paragraph(line2, bbox=(72.0, 100.0, 180.0, 112.0)).runs[0],
        ],
    )
    paragraph.alignment = "justify"
    output, _ = build_source_format_docx(
        make_project_facts(), _template([paragraph]), tmp_path / "justify.docx"
    )
    document = Document(output)
    assert len(document.tables) == 0
    assert document.paragraphs[0].alignment == 3  # WD_ALIGN_PARAGRAPH.JUSTIFY
    assert document.paragraphs[0].paragraph_format.right_indent.pt == 0

    block = DocumentBlock(
        block_index=0,
        text=line1 + line2,
        bbox=(72.0, 80.0, 570.0, 112.0),
        locator=PdfLocator(page=1, block_index=0),
        lines=[_line(line1, (72.0, 80.0, 570.0, 92.0)), _line(line2, (72.0, 100.0, 180.0, 112.0), 1)],
    )
    assert _block_alignment(block, 595.0) == "justify"


def test_single_line_form_uses_tab_leader_and_no_layout_table(tmp_path):
    form = _paragraph(
        "投标人：____（盖单位公章）",
        bbox=(72.0, 80.0, 280.0, 92.0),
    )
    output, report = build_source_format_docx(
        make_project_facts(), _template([form]), tmp_path / "form-line.docx"
    )
    document = Document(output)
    assert len(document.tables) == 0
    assert len(document.paragraphs) == 1
    assert "\t" in document.paragraphs[0].text
    assert "____" in document.paragraphs[0].text
    assert "\u00a0" not in document.paragraphs[0].text
    tabs = _xml(output).xpath(".//w:tabs/w:tab", namespaces=W)
    # python-docx's WD_TAB_LEADER.LINES serializes as the OOXML
    # ``underscore`` leader value.
    assert not any(tab.get(f"{{{W_NS}}}leader") == "underscore" for tab in tabs)
    assert report["tab_stop_usage"]["form_tab_leader_count"] == 0
    assert docx_layout_counts(output)["layout_tab_hack"] == 0


def test_date_line_and_multi_field_line_remain_one_paragraph(tmp_path):
    date = _paragraph("____年____月____日", bbox=(72.0, 80.0, 280.0, 92.0))
    fields = _paragraph(
        "姓名：____ 性别：____ 年龄：____ 职务：____",
        block=1,
        bbox=(72.0, 120.0, 420.0, 132.0),
    )
    output, report = build_source_format_docx(
        make_project_facts(), _template([date, fields]), tmp_path / "rows.docx"
    )
    document = Document(output)
    assert len(document.tables) == 0
    assert len(document.paragraphs) == 2
    assert document.paragraphs[0].text.count("____") == 3
    assert document.paragraphs[1].text.count("____") == 4
    assert report["synthetic_layout_tables"] == 0


def test_hanging_list_and_nested_hanging_list_are_paragraphs(tmp_path):
    """Nested list items stay their own paragraphs at their own source origin.

    Neither fixture item wraps, so the source shows no continuation column for
    them and no first-line indent is claimed; each keeps its own source x.  The
    structural claim - one Word paragraph per source list item, no synthetic
    table - is what the source actually justifies.
    """

    main = _paragraph("1、主要条款内容很长，续行必须回到正文锚点。", bbox=(96.0, 80.0, 520.0, 92.0))
    nested = _paragraph("（1）嵌套条款", block=1, bbox=(82.0, 110.0, 360.0, 122.0))
    output, report = build_source_format_docx(
        make_project_facts(), _template([main, nested]), tmp_path / "hanging.docx"
    )
    document = Document(output)
    assert len(document.tables) == 0
    assert len(document.paragraphs) == 2
    for paragraph, source_x in zip(document.paragraphs, (96.0, 82.0)):
        formatting = paragraph.paragraph_format
        assert (formatting.left_indent.pt or 0) + (formatting.first_line_indent.pt or 0) == source_x - 18.0
    assert report["logical_paragraph_records"]
    list_records = [
        record for record in report["logical_paragraph_records"] if record["kind"] == "List"
    ]
    assert list_records
    assert all(
        record["source_indent"]["classification"] == "NO_SPECIAL_FIRST_LINE_INDENT"
        for record in list_records
    )


def test_real_source_table_stays_table_and_word_safe(tmp_path):
    template, _ = _table_template()
    output, report = build_source_format_docx(
        make_project_facts(), template, tmp_path / "real-table.docx"
    )
    document = Document(output)
    assert len(document.tables) == 1
    assert report["source_real_tables"] == 1
    assert report["generated_real_tables"] == 1
    assert report["synthetic_layout_tables"] == 0
    assert scan_word_safe_docx(output)["result"] == "PASS"


def test_form_label_never_creates_a_synthetic_table(tmp_path):
    rows = [
        _paragraph("项目编号：", bbox=(72.0, 80.0, 150.0, 92.0)),
        _paragraph("地址：____", block=1, bbox=(72.0, 110.0, 260.0, 122.0)),
    ]
    output, report = build_source_format_docx(
        make_project_facts(), _template(rows), tmp_path / "form-no-table.docx"
    )
    document = Document(output)
    assert len(document.tables) == 0
    assert report["form_layout_table_count"] == 0
    assert all(paragraph._p.tag.endswith("}p") for paragraph in document.paragraphs)
