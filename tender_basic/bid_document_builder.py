"""Build the editable V1 bid document from ProjectFacts and source format."""

from __future__ import annotations

import re
import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt

from .document_models import NormalizedDocument
from .format_extractor import BidFormatTemplate, extract_bid_format
from .models import FactStatus, FieldName, ProjectFacts
from .output_helpers import docx_value, field_label, load_output_fields
from .fact_normalizer import normalize_text_value
from .word_style_source_builder import StyleFirstSourceDocumentBuilder
from .word_safe_xml import set_east_asian_font, clean_bootstrap
from .source_format import apply_source_glyph_repairs, build_source_format_model


_BODY_FONT = "宋体"
_TITLE_FONT = "黑体"


def _set_fonts(target, font_name: str, size: float | None = None, bold: bool | None = None) -> None:
    """Set East Asian and Latin font names for a run or a style."""

    if hasattr(target, "font"):
        target.font.name = font_name
        if size is not None:
            target.font.size = Pt(size)
        if bold is not None:
            target.font.bold = bold

    set_east_asian_font(target, font_name)


def _set_run_font(run, font_name: str = _BODY_FONT, size: float = 10.5, bold: bool = False) -> None:
    _set_fonts(run, font_name, size, bold)


def _configure_styles(document: Document) -> None:
    normal = document.styles["Normal"]
    _set_fonts(normal, _BODY_FONT, 10.5, False)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    title = document.styles["Title"]
    _set_fonts(title, _TITLE_FONT, 24, True)
    title.paragraph_format.space_after = Pt(18)

    heading_1 = document.styles["Heading 1"]
    _set_fonts(heading_1, _TITLE_FONT, 16, True)
    heading_1.paragraph_format.space_before = Pt(12)
    heading_1.paragraph_format.space_after = Pt(8)

    heading_2 = document.styles["Heading 2"]
    _set_fonts(heading_2, _TITLE_FONT, 13, True)
    heading_2.paragraph_format.space_before = Pt(8)
    heading_2.paragraph_format.space_after = Pt(4)


def _configure_page(document: Document) -> None:
    for section in document.sections:
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.top_margin = Mm(25.4)
        section.bottom_margin = Mm(25.4)
        section.left_margin = Mm(25.4)
        section.right_margin = Mm(25.4)


def _add_text(document: Document, text: str, *, bold: bool = False, align=None):
    paragraph = document.add_paragraph()
    if align is not None:
        paragraph.alignment = align
    run = paragraph.add_run(text)
    _set_run_font(run, _BODY_FONT, 10.5, bold)
    return paragraph


def _set_cell_text(cell, text: str, *, bold: bool = False) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    _set_run_font(run, _BODY_FONT, 10.5, bold)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _set_table_borders(table) -> None:
    table.style = 'Table Grid'


_SOURCE_LABEL_FIELDS = {
    "项目名称": FieldName.PROJECT_NAME.value,
    "采购项目名称": FieldName.PROJECT_NAME.value,
    "项目编号": FieldName.PROJECT_NUMBER.value,
    "采购项目编号": FieldName.PROJECT_NUMBER.value,
    "采购编号": FieldName.PROJECT_NUMBER.value,
    "招标人项目编号": FieldName.PROJECT_NUMBER.value,
    "采购人项目编号": FieldName.PROJECT_NUMBER.value,
    "招标编号": FieldName.TENDER_NUMBER.value,
    "招标代理项目编号": FieldName.TENDER_NUMBER.value,
    "代理项目编号": FieldName.TENDER_NUMBER.value,
    "采购人名称": FieldName.PURCHASER.value,
    "采购人": FieldName.PURCHASER.value,
    "招标人名称": FieldName.PURCHASER.value,
    "招标人": FieldName.PURCHASER.value,
}


def _source_fact_value(project_facts: ProjectFacts, field: str) -> str | None:
    fact = getattr(project_facts.fields, field)
    if fact.status == FactStatus.RESOLVED:
        return str(fact.resolved_value)
    # Human-review status belongs in ProjectFacts/QA, not inside a source
    # tender form.  Keeping the source token/blank untouched avoids changing
    # the bidder-facing template with an internal pipeline marker.
    return None


def _source_label_field(label: str) -> str | None:
    return _SOURCE_LABEL_FIELDS.get(normalize_text_value(label).strip(" ：:"))


def _replace_source_fact_placeholders(text: str, project_facts: ProjectFacts) -> str:
    """Fill only tender-fact placeholders in source-format fixed text."""

    result = text
    for label, field in sorted(_SOURCE_LABEL_FIELDS.items(), key=lambda item: len(item[0]), reverse=True):
        value = _source_fact_value(project_facts, field)
        if value is None:
            continue
        # Label + empty underline/parenthetical placeholder.  A non-empty
        # source value is left intact; facts are never inferred from format text.
        pattern = re.compile(
            rf"(?P<label>{re.escape(label)})\s*[：:]\s*"
            rf"(?P<blank>_{2,}|（[^）]*）|\([^)]*\)|(?=$|[\n\r]))"
        )
        result = pattern.sub(lambda match: f"{match.group('label')}：{value}", result)
        if field in {FieldName.PROJECT_NAME.value, FieldName.PURCHASER.value}:
            result = re.sub(
                rf"[（(]{re.escape(label)}[）)]",
                value,
                result,
            )
    return result


def _source_table_cell_text(text: str, project_facts: ProjectFacts) -> str:
    return _replace_source_fact_placeholders(text, project_facts)


def _add_source_table(
    document: Document,
    source_table: object,
    project_facts: ProjectFacts,
) -> None:
    """Rebuild a source PDF/DOCX table as an editable DOCX table."""

    rows = getattr(source_table, "rows", [])
    if not rows:
        return
    column_count = max((len(row.cells) for row in rows), default=0)
    if column_count <= 0:
        return
    table = document.add_table(rows=0, cols=column_count)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    _set_table_borders(table)
    cell_texts: list[list[str]] = []
    for row in rows:
        source_cells = getattr(row, "cells", [])
        values = [
            _source_table_cell_text(
                source_cells[index].text if index < len(source_cells) else "",
                project_facts,
            )
            for index in range(column_count)
        ]
        for index, source_cell in enumerate(source_cells):
            field = _source_label_field(source_cell.text)
            if field is None or index + 1 >= column_count:
                continue
            current_value = normalize_text_value(
                source_cells[index + 1].text if index + 1 < len(source_cells) else ""
            )
            if not current_value or set(current_value) <= {"_"}:
                resolved_value = _source_fact_value(project_facts, field)
                if resolved_value is not None:
                    values[index + 1] = resolved_value
        cell_texts.append(values)

    for values in cell_texts:
        cells = table.add_row().cells
        for index, cell in enumerate(cells):
            text = values[index] if index < len(values) else ""
            _set_cell_text(cell, text)
    _set_table_borders(table)


def _add_two_column_table(document: Document, rows: list[tuple[str, str]], header: bool = True):
    table = document.add_table(rows=1 if header else 0, cols=2)
    table.style = "Table Grid"
    table.autofit = True
    if header:
        _set_cell_text(table.rows[0].cells[0], "字段", bold=True)
        _set_cell_text(table.rows[0].cells[1], "内容", bold=True)
    for label, value in rows:
        cells = table.add_row().cells
        _set_cell_text(cells[0], label)
        _set_cell_text(cells[1], value)
    return table


def _field_rows(project_facts: ProjectFacts) -> list[tuple[str, str]]:
    fields = load_output_fields()
    return [
        (spec.label, docx_value(getattr(project_facts.fields, spec.field)))
        for spec in fields
    ]


def _add_cover(document: Document, project_facts: ProjectFacts) -> None:
    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run("投 标 文 件")
    _set_run_font(title_run, _TITLE_FONT, 24, True)

    document.add_paragraph()
    fields = load_output_fields()
    cover_field_names = {
        FieldName.PROJECT_NAME.value,
        FieldName.PROJECT_NUMBER.value,
        FieldName.TENDER_NUMBER.value,
        FieldName.LOT_NAME.value,
        FieldName.LOT_NUMBER.value,
    }
    rows = [
        (spec.label, docx_value(getattr(project_facts.fields, spec.field)))
        for spec in fields
        if spec.field in cover_field_names
    ]
    rows.extend(
        [
            ("投标人", "____________________"),
            ("日期", "______年____月____日"),
        ]
    )
    table = _add_two_column_table(document, rows)
    if table.rows:
        table.rows[0].cells[0].width = Mm(45)


def _add_project_information(document: Document, project_facts: ProjectFacts) -> None:
    heading = document.add_paragraph()
    heading.paragraph_format.space_before = Pt(6)
    heading.paragraph_format.space_after = Pt(8)
    run = heading.add_run("项目基本信息")
    _set_run_font(run, _TITLE_FONT, 16, True)
    _add_two_column_table(document, _field_rows(project_facts))


def _add_bid_letter(document: Document, project_facts: ProjectFacts) -> None:
    document.add_heading("一、投标函", level=1)
    purchaser = docx_value(project_facts.fields.purchaser)
    _add_text(document, f"致：{purchaser}")
    _add_text(document, "我方已认真阅读本项目招标文件，现按招标文件要求提交投标文件。")
    rows = []
    for field_name in (
        FieldName.PROJECT_NAME.value,
        FieldName.PROJECT_NUMBER.value,
        FieldName.TENDER_NUMBER.value,
        FieldName.LOT_NAME.value,
        FieldName.DURATION.value,
        FieldName.QUALITY_TARGET.value,
    ):
        rows.append((field_label(field_name), docx_value(getattr(project_facts.fields, field_name))))
    _add_two_column_table(document, rows)
    document.add_paragraph()
    _add_text(document, "投标人：________________")
    _add_text(document, "法定代表人或授权代表：________________")
    _add_text(document, "日期：________________")


def _add_skeleton_section(document: Document, title: str, items: list[str]) -> None:
    document.add_heading(title, level=1)
    for item in items:
        document.add_heading(item, level=2)
        _add_text(document, "【待按招标文件目录及实际材料补充】")


def _add_signing_checklist(document: Document) -> None:
    document.add_heading("签字盖章复核提示", level=1)
    for item in (
        "□ 法定代表人或授权代表签字位置已检查",
        "□ 投标人盖章位置已检查",
        "□ 日期填写已检查",
        "□ 正副本/电子文件要求已检查",
    ):
        _add_text(document, item)


def _add_source_format(
    document: Document,
    template: BidFormatTemplate,
    project_facts: ProjectFacts,
) -> None:
    """Append the source-ordered format elements as the bid skeleton."""

    for element in template.elements:
        if element.type == "heading":
            document.add_heading(
                _replace_source_fact_placeholders(element.text, project_facts),
                level=element.heading_level or 2,
            )
        elif element.type == "paragraph":
            _add_text(document, _replace_source_fact_placeholders(element.text, project_facts))
        elif element.type == "table":
            _add_source_table(document, element.table, project_facts)


def _add_generic_fallback(document: Document) -> None:
    """Keep the existing generic skeleton for documents without source format."""

    _add_skeleton_section(
        document,
        "二、资格审查文件",
        [
            "2.1 营业执照",
            "2.2 法定代表人身份证明",
            "2.3 授权委托书",
            "2.4 资格证明材料",
            "2.5 其他资格材料",
        ],
    )
    _add_skeleton_section(
        document,
        "三、商务响应文件",
        ["3.1 商务条款响应", "3.2 合同条款响应", "3.3 服务期限/工期响应"],
    )
    _add_skeleton_section(
        document,
        "四、技术响应文件",
        [
            "4.1 技术响应说明",
            "4.2 技术参数响应",
            "4.3 实施/服务方案",
            "4.4 质量保证措施",
        ],
    )
    _add_skeleton_section(document, "五、报价文件", ["5.1 开标一览表", "5.2 投标报价明细"])
    _add_skeleton_section(document, "六、其他材料", [])
    _add_text(
        document,
        "【提示：本目录为基础工作骨架，正式投标前须依据招标文件目录及评分标准调整。】",
    )


def _verify_document(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("DOCX output is empty")
    reopened = Document(path)
    if len(reopened.paragraphs) <= 0:
        raise ValueError("DOCX output has no paragraphs")


def build_bid_document(
    project_facts: ProjectFacts,
    output_path: str | Path,
    *,
    normalized_document: NormalizedDocument | None = None,
    format_template: BidFormatTemplate | None = None,
    generation_report_path: str | Path | None = None,
    source_path: str | Path | None = None,
) -> Path:
    """Create and reopen the editable V1 document skeleton from ProjectFacts."""

    return _build_bid_document(
        project_facts,
        output_path,
        normalized_document=normalized_document,
        format_template=format_template,
        generation_report_path=generation_report_path,
        source_path=source_path,
    )


# Geometry-backed glyph mappings where the PDF's ToUnicode map disagrees with
# the rendered glyph.  Both the DOCX builder and the source-format QA consume
# this single list, so the QA compares the emitted document with the model that
# actually produced it instead of with an unrepaired copy.
SOURCE_GLYPH_REPAIRS: list[dict[str, object]] = [
    {
        "page": 48,
        "table_index": 0,
        "row_index": 0,
        "column_index": 6,
        "extracted": "今",
        "visual": "含",
        "geometry": [407.64, 117.54, 418.09, 127.99],
        "evidence": "rendered PDF glyph is 含 while ToUnicode extraction returns 今",
    },
]


def build_repaired_source_model(
    normalized_document: NormalizedDocument,
    format_template: BidFormatTemplate,
):
    """Build the source-format model with the production glyph repairs applied."""

    model = build_source_format_model(normalized_document, format_template)
    return apply_source_glyph_repairs(model, SOURCE_GLYPH_REPAIRS)


def _build_bid_document(
    project_facts: ProjectFacts,
    output_path: str | Path,
    *,
    normalized_document: NormalizedDocument | None,
    format_template: BidFormatTemplate | None,
    generation_report_path: str | Path | None = None,
    source_path: str | Path | None = None,
) -> Path:
    if not isinstance(project_facts, ProjectFacts):
        raise TypeError("build_bid_document requires a ProjectFacts instance")
    if normalized_document is not None and not isinstance(normalized_document, NormalizedDocument):
        raise TypeError("normalized_document must be a NormalizedDocument instance")
    if format_template is not None and not isinstance(format_template, BidFormatTemplate):
        raise TypeError("format_template must be a BidFormatTemplate instance")
    if format_template is None and normalized_document is not None:
        format_template = extract_bid_format(normalized_document)

    format_source = format_template.format_source if format_template is not None else "GENERIC_FALLBACK"
    section_status = (
        format_template.section_status
        if format_template is not None
        else "FORMAT_SECTION_NOT_FOUND"
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    clean_bootstrap(document)
    _configure_styles(document)
    _configure_page(document)
    document.core_properties.title = "基础投标文件"

    if format_template is not None and format_template.usable:
        source_model = (
            build_source_format_model(normalized_document, format_template)
            if normalized_document is not None
            else None
        )
        if source_model is not None and source_model.source_pages:
            source_model, source_text_qa = apply_source_glyph_repairs(
                source_model, SOURCE_GLYPH_REPAIRS)
            output, _report = StyleFirstSourceDocumentBuilder(
                project_facts,
                source_model,
                source_text_qa=source_text_qa,
                source_path=source_path,
            ).build(path, generation_report_path)
            return output
        _add_source_format(document, format_template, project_facts)
    else:
        _add_cover(document, project_facts)
        document.add_page_break()
        _add_project_information(document, project_facts)
        document.add_page_break()
        _add_bid_letter(document, project_facts)
        _add_generic_fallback(document)
        _add_signing_checklist(document)

    # Keep the output mode in OOXML metadata so QA can verify the selected
    # product shape without exposing implementation notes in the visible file.
    document.core_properties.subject = f"format_source={format_source}"
    document.core_properties.keywords = (
        f"format_source={format_source}; section_status={section_status}"
    )

    document.save(path)
    _verify_document(path)
    if generation_report_path is not None:
        report_path = Path(generation_report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "format_source": format_source,
                    "architecture": "generic_fallback" if format_source == "GENERIC_FALLBACK" else "legacy_source_order",
                    "fill_slots_detected": 0,
                    "fill_slots_filled": 0,
                    "fill_slots_left_blank": 0,
                    "font_substitutions": [],
                    "font_repairs": [],
                    "layout_warnings": [
                        "DOCX source has no PDF geometry model; source-order reconstruction retained for compatibility."
                    ]
                    if format_source == "SOURCE_DOCUMENT"
                    else [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return path


def build_bid_document_with_source(
    project_facts: ProjectFacts,
    output_path: str | Path,
    *,
    normalized_document: NormalizedDocument | None = None,
    format_template: BidFormatTemplate | None = None,
    generation_report_path: str | Path | None = None,
) -> Path:
    """Build using source format when available, while keeping the old API."""

    return _build_bid_document(
        project_facts,
        output_path,
        normalized_document=normalized_document,
        format_template=format_template,
        generation_report_path=generation_report_path,
    )


__all__ = ["build_bid_document", "build_bid_document_with_source"]
