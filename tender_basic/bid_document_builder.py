"""Build the editable V1 bid-document skeleton from ProjectFacts only."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

from .models import FieldName, ProjectFacts
from .output_helpers import docx_value, field_label, load_output_fields


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

    element = target._element
    if hasattr(element, "get_or_add_rPr"):
        rpr = element.get_or_add_rPr()
    else:
        rpr = element.rPr
        if rpr is None:
            rpr = OxmlElement("w:rPr")
            element.insert(0, rpr)
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), font_name)
    rfonts.set(qn("w:hAnsi"), font_name)
    rfonts.set(qn("w:eastAsia"), font_name)


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
    document.add_heading("项目基本信息", level=1)
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


def _verify_document(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("DOCX output is empty")
    reopened = Document(path)
    if len(reopened.paragraphs) <= 0:
        raise ValueError("DOCX output has no paragraphs")
    if len(reopened.tables) <= 0:
        raise ValueError("DOCX output has no tables")


def build_bid_document(project_facts: ProjectFacts, output_path: str | Path) -> Path:
    """Create and reopen the editable V1 document skeleton from ProjectFacts."""

    if not isinstance(project_facts, ProjectFacts):
        raise TypeError("build_bid_document requires a ProjectFacts instance")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    _configure_styles(document)
    _configure_page(document)
    document.core_properties.title = "基础投标文件"

    _add_cover(document, project_facts)
    document.add_page_break()
    _add_project_information(document, project_facts)
    document.add_page_break()
    _add_bid_letter(document, project_facts)
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
    _add_signing_checklist(document)

    document.save(path)
    _verify_document(path)
    return path


__all__ = ["build_bid_document"]
