from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore[no-redef]

from tender_basic.document_models import (
    DocumentBlock,
    DocumentPage,
    DocumentStatus,
    NormalizedDocument,
    PdfTableCell,
    PdfTextLine,
    PdfTextSpan,
)
from tender_basic.document_parser import parse_document
from tender_basic.models import (
    CandidateFact,
    FactStatus,
    FieldName,
    PdfLocator,
    PdfTableLocator,
    ProjectFacts,
    ResolvedFact,
    SourceType,
)
from tender_basic.source_docx_builder import build_source_format_docx
from tender_basic.source_format import (
    SourceCell,
    SourceFillSlot,
    SourceFormatTemplate,
    SourcePage,
    SourcePageElement,
    SourceLine,
    SourceParagraph,
    SourceRow,
    SourceRun,
    SourceTable,
    _clean_table_cell_text,
    _paragraph_from_block,
    _paragraph_slots,
    _table_slots,
    detect_pdf_chrome,
)
from tender_basic.source_format_qa import build_source_format_qa

from test_review_builder import make_project_facts


_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = {"w": _W_NS}


def _xml(path: Path) -> etree._Element:
    with ZipFile(path) as archive:
        return etree.fromstring(archive.read("word/document.xml"))


def _xml_text(path: Path) -> str:
    return "".join(_xml(path).xpath(".//w:t/text()", namespaces=_W))


def _resolved(base: ProjectFacts, field: FieldName, value: str) -> ProjectFacts:
    candidate = CandidateFact(
        value=value,
        normalized_value=value,
        confidence=0.99,
        method="synthetic_source_slot",
        source_file="synthetic.pdf",
        source_type=SourceType.PDF,
        locator=PdfLocator(page=1, block_index=0),
        evidence_text=f"{field.value}：{value}",
    )
    fact = ResolvedFact(
        field=field,
        resolved_value=value,
        status=FactStatus.RESOLVED,
        confidence=0.99,
        candidates=[candidate],
        resolution_reason="Synthetic source-format test fact.",
    )
    fields = base.fields.model_copy(update={field.value: fact})
    return base.model_copy(update={"fields": fields})


def _paragraph(
    text: str,
    *,
    page: int = 1,
    block_index: int = 0,
    bbox: tuple[float, float, float, float] = (40.0, 40.0, 520.0, 60.0),
    font_name: str = "SimSun",
    font_size: float = 10.5,
    bold: bool = False,
) -> SourceParagraph:
    return SourceParagraph(
        paragraph_id=f"synthetic-{page}-{block_index}",
        page=page,
        bbox=bbox,
        text=text,
        runs=[
            SourceRun(
                text=text,
                bbox=bbox,
                font_name=font_name,
                font_size=font_size,
                bold=bold,
            )
        ],
        locator=PdfLocator(page=page, block_index=block_index),
    )


def _paragraph_template(
    paragraph: SourceParagraph,
    *,
    slots: list[SourceFillSlot] | None = None,
    width: float = 595.0,
    height: float = 842.0,
) -> SourceFormatTemplate:
    page = SourcePage(
        page=paragraph.page,
        width=width,
        height=height,
        paragraphs=[paragraph],
        elements=[
            SourcePageElement(
                type="paragraph",
                index=0,
                bbox=paragraph.bbox,
            )
        ],
    )
    return SourceFormatTemplate(
        source_heading=paragraph.text,
        source_locator=paragraph.locator,
        source_type=SourceType.PDF,
        source_pages=[page],
        fill_slots=slots or [],
    )


def _cell(
    table_index: int,
    row_index: int,
    column_index: int,
    text: str,
    bbox: tuple[float, float, float, float],
) -> SourceCell:
    locator = PdfTableLocator(
        page=1,
        table_index=table_index,
        row_index=row_index,
        column_index=column_index,
    )
    return SourceCell(
        row_index=row_index,
        column_index=column_index,
        bbox=bbox,
        text=text,
        runs=(
            [
                SourceRun(
                    text=text,
                    bbox=bbox,
                    font_name="SimSun",
                    font_size=10.5,
                )
            ]
            if text
            else []
        ),
        locator=locator,
    )


def _table_template(*, merged: bool = False) -> tuple[SourceFormatTemplate, SourceFillSlot]:
    table_index = 0
    rows = [
        SourceRow(
            row_index=0,
            height=28.0,
            cells=[
                _cell(table_index, 0, 0, "项目名称", (40, 100, 140, 128)),
                _cell(table_index, 0, 1, "", (140, 100, 340, 128)),
            ],
        ),
        SourceRow(
            row_index=1,
            height=24.0,
            cells=[
                _cell(table_index, 1, 0, "质量标准", (40, 128, 140, 152)),
                _cell(table_index, 1, 1, "原模板固定质量标准", (140, 128, 340, 152)),
            ],
        ),
    ]
    table = SourceTable(
        page=1,
        table_index=table_index,
        bbox=(40, 100, 340, 152),
        rows=rows,
        columns=2,
        column_widths=[100.0, 200.0],
        row_heights=[28.0, 24.0],
        merged_cells=[(0, 0, 0, 1)] if merged else [],
    )
    slot = SourceFillSlot(
        slot_id="table-slot-0",
        semantic_hint="项目名称",
        source_page=1,
        source_locator=rows[0].cells[1].locator,
        container_type="table_cell",
        original_text="",
        font_name="SimSun",
        font_size=10.5,
        geometry=rows[0].cells[1].bbox,
        allowed_fact_fields=[FieldName.PROJECT_NAME],
        match_kind="table_blank",
        table_index=0,
        row_index=0,
        column_index=1,
    )
    page = SourcePage(
        page=1,
        width=595.0,
        height=842.0,
        tables=[table],
        elements=[SourcePageElement(type="table", index=0, bbox=table.bbox)],
    )
    return (
        SourceFormatTemplate(
            source_heading="源格式表格",
            source_locator=PdfLocator(page=1, block_index=0),
            source_type=SourceType.PDF,
            source_pages=[page],
            fill_slots=[slot],
        ),
        slot,
    )


def test_pdf_font_span_metadata_and_geometry_are_retained(tmp_path: Path) -> None:
    source = tmp_path / "font-span.pdf"
    pdf = fitz.open()
    page = pdf.new_page(width=500, height=300)
    page.insert_text((120, 80), "第六章 投标文件格式", fontname="helv", fontsize=14)
    pdf.save(source)
    pdf.close()

    normalized = parse_document(source)
    span = normalized.pages[0].blocks[0].lines[0].spans[0]

    assert span.text
    assert span.font_name
    assert span.font_size == pytest.approx(14.0)
    assert span.bbox[2] > span.bbox[0]
    assert span.bbox[3] > span.bbox[1]


def test_pdf_vector_rules_are_retained_for_form_lines(tmp_path: Path) -> None:
    source = tmp_path / "rules.pdf"
    pdf = fitz.open()
    page = pdf.new_page(width=500, height=300)
    page.draw_line((100, 120), (400, 120), color=(0, 0, 0), width=0.6)
    page.insert_text((60, 60), "This source page contains enough text for parsing.")
    pdf.save(source)
    pdf.close()

    normalized = parse_document(source)

    assert normalized.status is not None
    assert any(line.orientation == "horizontal" for line in normalized.pages[0].vector_lines)


def test_source_paragraph_alignment_and_line_geometry_are_retained() -> None:
    span = PdfTextSpan(
        text="居中标题",
        bbox=(245.0, 100.0, 350.0, 116.0),
        font_name="FangSong",
        font_size=12.0,
        source_order=0,
    )
    line = PdfTextLine(
        text=span.text,
        bbox=span.bbox,
        spans=[span],
        source_order=0,
    )
    block = DocumentBlock(
        block_index=0,
        text="居中标题",
        bbox=span.bbox,
        locator=PdfLocator(page=1, block_index=0),
        lines=[line],
    )
    paragraph = _paragraph_from_block(
        block,
        DocumentPage(page_number=1, width=595.0, height=842.0, blocks=[block]),
    )

    assert paragraph.alignment == "center"
    assert paragraph.runs[0].font_name == "FangSong"
    assert paragraph.line_spacing == 0
    assert paragraph.bbox == span.bbox


def test_fill_slot_detection_covers_underline_whitespace_parenthetical_and_date() -> None:
    paragraph = _paragraph(
        "项目名称：________ 供货期  日历天 （项目编号） 年    月    日"
    )
    slots = _paragraph_slots(paragraph, 0)
    kinds = {slot.match_kind for slot in slots}

    assert kinds == {"underline", "whitespace", "parenthetical", "date_signature"}
    assert any(slot.semantic_hint == "项目名称" for slot in slots)
    assert any(slot.semantic_hint == "项目编号" for slot in slots)
    assert any(slot.semantic_hint == "供货期" for slot in slots)
    assert all(slot.geometry is not None for slot in slots)


def test_underline_fill_inherits_source_run_style_without_heading_leak(tmp_path: Path) -> None:
    paragraph = _paragraph(
        "项目名称：________",
        font_name="FangSong",
        font_size=12.0,
        bold=True,
    )
    template = _paragraph_template(paragraph, slots=_paragraph_slots(paragraph, 0))
    facts = _resolved(make_project_facts(), FieldName.PROJECT_NAME, "测试工程")
    output = tmp_path / "underline.docx"

    _path, report = build_source_format_docx(facts, template, output)
    xml = etree.tostring(_xml(output), encoding="unicode")
    text = _xml_text(output)

    assert "测试工程" in text
    assert "仿宋" in xml
    assert "<w:b" in xml
    assert "w:val=\"single\"" in xml
    assert "w:pStyle" not in xml
    assert report["fill_slots_filled"] == 1


def test_blank_space_fill_keeps_source_fixed_unit_once(tmp_path: Path) -> None:
    paragraph = _paragraph("供货期        日历天")
    template = _paragraph_template(paragraph, slots=_paragraph_slots(paragraph, 0))
    facts = _resolved(make_project_facts(), FieldName.DURATION, "90日历天")
    output = tmp_path / "space-slot.docx"

    build_source_format_docx(facts, template, output)
    compact = re.sub(r"\s+", "", _xml_text(output))

    assert "供货期90日历天" in compact
    assert "90日历天日历天" not in compact


def test_parenthetical_fill_is_constrained_to_resolved_fact(tmp_path: Path) -> None:
    paragraph = _paragraph("项目编号：（项目编号）")
    template = _paragraph_template(paragraph, slots=_paragraph_slots(paragraph, 0))
    facts = _resolved(make_project_facts(), FieldName.PROJECT_NUMBER, "PRJ-123")
    output = tmp_path / "parenthetical.docx"

    build_source_format_docx(facts, template, output)
    text = _xml_text(output)

    assert "项目编号：PRJ-123" in text
    assert "（项目编号）" not in text


def test_table_cell_fill_preserves_fixed_template_value(tmp_path: Path) -> None:
    template, _slot = _table_template()
    facts = _resolved(make_project_facts(), FieldName.PROJECT_NAME, "测试工程")
    output = tmp_path / "table-fill.docx"

    build_source_format_docx(facts, template, output)
    document_text = _xml_text(output)

    assert "测试工程" in document_text
    assert "原模板固定质量标准" in document_text
    assert len(_xml(output).xpath(".//w:tbl", namespaces=_W)) == 1


def test_multiline_table_cell_spans_keep_source_line_breaks(tmp_path: Path) -> None:
    template, _slot = _table_template()
    table = template.source_pages[0].tables[0]
    table.rows[1].cells[1] = SourceCell(
        row_index=1,
        column_index=1,
        bbox=(140, 128, 340, 152),
        text="第一行\n第二行",
        runs=[
            SourceRun(text="第一行", bbox=(145, 130, 180, 140), font_name="SimSun", font_size=10.5),
            SourceRun(text="第二行", bbox=(145, 143, 180, 153), font_name="SimSun", font_size=10.5),
        ],
        locator=PdfTableLocator(page=1, table_index=0, row_index=1, column_index=1),
    )
    output = tmp_path / "multiline-table-cell.docx"

    build_source_format_docx(make_project_facts(), template, output)

    assert _xml(output).xpath(".//w:tbl//w:br", namespaces=_W)


def test_fixed_table_value_does_not_create_a_later_remark_slot() -> None:
    table = SourceTable(
        page=1,
        table_index=0,
        bbox=(40, 100, 340, 160),
        columns=4,
        rows=[
            SourceRow(
                row_index=0,
                height=28.0,
                cells=[
                    _cell(0, 0, 0, "8", (40, 100, 70, 128)),
                    _cell(0, 0, 1, "投标有效期", (70, 100, 170, 128)),
                    _cell(0, 0, 2, "90 日历天", (170, 100, 290, 128)),
                    _cell(0, 0, 3, "", (290, 100, 340, 128)),
                ],
            )
        ],
    )
    assert _table_slots(table, 0) == []


def test_table_chrome_span_is_removed_without_deleting_real_cell_text() -> None:
    normal = PdfTextSpan(
        text="姓名：",
        bbox=(20.0, 20.0, 50.0, 32.0),
        font_name="SimSun",
        font_size=10.0,
        source_order=0,
    )
    watermark = PdfTextSpan(
        text="重复水印",
        bbox=(0.0, 0.0, 100.0, 100.0),
        font_name="SimSun",
        font_size=10.0,
        source_order=1,
    )
    cell = PdfTableCell(
        row_index=0,
        column_index=0,
        text="姓名：\n重复水印",
        bbox=(0.0, 0.0, 120.0, 120.0),
        locator=PdfTableLocator(page=1, table_index=0, row_index=0, column_index=0),
        spans=[normal, watermark],
    )
    text, runs = _clean_table_cell_text(cell, (), chrome_keys={"重复水印"})
    assert text == "姓名："
    assert [run.text for run in runs] == ["姓名："]


def test_table_merge_width_and_height_are_retained(tmp_path: Path) -> None:
    template, _slot = _table_template(merged=True)
    output = tmp_path / "table-geometry.docx"

    build_source_format_docx(make_project_facts(), template, output)
    root = _xml(output)
    grid_widths = [
        int(value.get(f"{{{_W_NS}}}w", "0"))
        for value in root.xpath(".//w:tblGrid/w:gridCol", namespaces=_W)
    ]

    assert len(grid_widths) == 2
    assert sum(grid_widths) == pytest.approx(6000, abs=40)
    assert root.xpath(".//w:gridSpan", namespaces=_W)
    assert root.xpath(".//w:trHeight", namespaces=_W)


def test_unknown_fact_and_bidder_specific_placeholder_stay_source_unchanged(tmp_path: Path) -> None:
    paragraph = _paragraph("项目地点：________；投标人：（投标人名称）")
    template = _paragraph_template(paragraph, slots=_paragraph_slots(paragraph, 0))
    output = tmp_path / "unknown.docx"

    build_source_format_docx(make_project_facts(), template, output)
    text = _xml_text(output)

    assert "项目地点：________" in text
    assert "投标人：（投标人名称）" in text
    assert "待人工确认" not in text
    assert "待补充" not in text


def test_pdf_chrome_detection_is_repetition_and_geometry_bound() -> None:
    pages = []
    for page_number in (1, 2, 3):
        repeated = DocumentBlock(
            block_index=0,
            text="平台水印",
            bbox=(100.0, 20.0, 400.0, 180.0),
            locator=PdfLocator(page=page_number, block_index=0),
        )
        body = DocumentBlock(
            block_index=1,
            text=f"正文{page_number}",
            bbox=(80.0, 240.0, 500.0, 260.0),
            locator=PdfLocator(page=page_number, block_index=1),
        )
        pages.append(
            DocumentPage(
                page_number=page_number,
                width=500.0,
                height=300.0,
                blocks=[repeated, body],
            )
        )
    document = NormalizedDocument(
        source_file="chrome.pdf",
        source_type=SourceType.PDF,
        status=DocumentStatus.PARSED,
        page_count=3,
        text_length=30,
        pages=pages,
    )

    chrome = detect_pdf_chrome(document, [1, 2, 3])

    assert len(chrome) == 3
    assert {item.text for item in chrome} == {"平台水印"}


def test_page_break_and_mixed_page_section_count_are_preserved(tmp_path: Path) -> None:
    first = _paragraph("第一页固定文本", page=1)
    second = _paragraph("第二页固定文本", page=2)
    template = SourceFormatTemplate(
        source_heading="第一页固定文本",
        source_locator=first.locator,
        source_type=SourceType.PDF,
        source_pages=[
            SourcePage(
                page=1,
                width=595.0,
                height=842.0,
                paragraphs=[first],
                elements=[SourcePageElement(type="paragraph", index=0, bbox=first.bbox)],
            ),
            SourcePage(
                page=2,
                width=841.0,
                height=595.0,
                paragraphs=[second],
                elements=[SourcePageElement(type="paragraph", index=0, bbox=second.bbox)],
            ),
        ],
    )
    output = tmp_path / "mixed-pages.docx"

    build_source_format_docx(make_project_facts(), template, output)
    root = _xml(output)
    report = build_source_format_qa(template, make_project_facts(), output)

    assert len(root.xpath(".//w:sectPr", namespaces=_W)) == 2
    assert not root.xpath('.//w:br[@w:type="page"]', namespaces=_W)
    assert report["page_count_generated"] == 2


def test_source_rule_is_emitted_as_a_positioned_editable_line(tmp_path: Path) -> None:
    paragraph = _paragraph("表单字段")
    template = _paragraph_template(paragraph)
    template.source_pages[0].lines = [
        SourceLine(bbox=(100.0, 100.0, 300.0, 100.0), width=0.6, color=0)
    ]
    output = tmp_path / "source-rule.docx"

    _path, report = build_source_format_docx(make_project_facts(), template, output)

    assert report["source_line_count"] == 1
    assert report["generated_line_count"] == 1
    assert "Source rule" in etree.tostring(_xml(output), encoding="unicode")


def test_font_repair_is_recorded_in_generation_report(tmp_path: Path) -> None:
    paragraph = _paragraph("字体修复", font_name="宋体")
    paragraph.runs[0].raw_font_name = "å®ä½"
    template = _paragraph_template(paragraph)
    output = tmp_path / "font-repair.docx"

    _path, report = build_source_format_docx(make_project_facts(), template, output)

    assert any("FONT_NAME_REPAIRED" in marker for marker in report["font_repairs"])
