"""Build the minimal three-sheet V1 tender review workbook from ProjectFacts."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import FactStatus, ProjectFacts
from .output_helpers import (
    OutputField,
    candidate_value_summary,
    field_label,
    format_locator,
    load_output_fields,
    status_display,
    summary_locator,
    value_text,
    xlsx_value,
)


REVIEW_HEADERS = [
    "序号",
    "分类",
    "字段编码",
    "字段名称",
    "自动提取值",
    "状态",
    "置信度",
    "来源位置",
    "人工复核",
    "人工修正值",
    "备注",
]

EVIDENCE_HEADERS = [
    "字段编码",
    "字段名称",
    "候选序号",
    "候选值",
    "归一化值",
    "方法",
    "置信度",
    "来源文件",
    "来源类型",
    "定位",
    "章节",
    "证据原文",
]

EXCEPTION_HEADERS = [
    "字段编码",
    "字段名称",
    "状态",
    "候选数量",
    "候选值摘要",
    "冲突/缺失说明",
    "建议人工动作",
]

_HEADER_FILL = PatternFill(fill_type="solid", fgColor="1F4E78")
_HEADER_FONT = Font(name="微软雅黑", bold=True, color="FFFFFF")
_THIN_GRAY = Side(style="thin", color="D9E2F3")
_BORDER = Border(bottom=_THIN_GRAY)
_BODY_ALIGNMENT = Alignment(vertical="top", wrap_text=True)
_HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _style_sheet(
    worksheet,
    headers: list[str],
    widths: list[float],
) -> None:
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    worksheet.row_dimensions[1].height = 28
    for index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=1, column=index, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _HEADER_ALIGNMENT
        cell.border = _BORDER
        worksheet.column_dimensions[get_column_letter(index)].width = widths[index - 1]


def _style_body(worksheet) -> None:
    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = _BODY_ALIGNMENT
            cell.border = _BORDER


def _build_review_sheet(workbook: Workbook, facts: ProjectFacts, fields: tuple[OutputField, ...]) -> None:
    worksheet = workbook.active
    worksheet.title = "项目复核表"
    _style_sheet(
        worksheet,
        REVIEW_HEADERS,
        [6, 14, 22, 20, 32, 23, 10, 30, 10, 24, 44],
    )

    for row_number, spec in enumerate(fields, start=2):
        fact = getattr(facts.fields, spec.field)
        values = [
            row_number - 1,
            spec.category,
            spec.field,
            spec.label,
            xlsx_value(fact),
            status_display(fact.status),
            fact.confidence,
            summary_locator(fact),
            "否" if fact.status == FactStatus.RESOLVED else "是",
            "",
            fact.resolution_reason,
        ]
        for column, value in enumerate(values, start=1):
            worksheet.cell(row=row_number, column=column, value=value)
        worksheet.cell(row=row_number, column=7).number_format = "0.00"
        worksheet.row_dimensions[row_number].height = 38
    worksheet.auto_filter.ref = f"A1:K{len(fields) + 1}"
    _style_body(worksheet)


def _build_evidence_sheet(
    workbook: Workbook,
    facts: ProjectFacts,
    fields: tuple[OutputField, ...],
) -> None:
    worksheet = workbook.create_sheet("字段证据")
    _style_sheet(
        worksheet,
        EVIDENCE_HEADERS,
        [22, 20, 10, 32, 22, 24, 10, 24, 12, 30, 24, 70],
    )
    row_number = 2
    for spec in fields:
        fact = getattr(facts.fields, spec.field)
        for candidate_index, candidate in enumerate(fact.candidates):
            values = [
                spec.field,
                spec.label,
                candidate_index,
                value_text(candidate.value),
                value_text(candidate.normalized_value),
                candidate.method,
                candidate.confidence,
                candidate.source_file,
                candidate.source_type.value,
                format_locator(candidate.locator),
                candidate.section or "",
                candidate.evidence_text,
            ]
            for column, value in enumerate(values, start=1):
                worksheet.cell(row=row_number, column=column, value=value)
            worksheet.cell(row=row_number, column=7).number_format = "0.00"
            worksheet.row_dimensions[row_number].height = 42
            row_number += 1
    worksheet.auto_filter.ref = f"A1:L{max(1, row_number - 1)}"
    _style_body(worksheet)


def _build_exception_sheet(
    workbook: Workbook,
    facts: ProjectFacts,
    fields: tuple[OutputField, ...],
) -> None:
    worksheet = workbook.create_sheet("解析异常")
    _style_sheet(
        worksheet,
        EXCEPTION_HEADERS,
        [22, 20, 23, 12, 48, 60, 58],
    )
    row_number = 2
    for spec in fields:
        fact = getattr(facts.fields, spec.field)
        if fact.status not in {FactStatus.NEEDS_REVIEW, FactStatus.NOT_FOUND}:
            continue
        action = (
            "建议人工核对招标文件原文并确认最终值"
            if fact.status == FactStatus.NEEDS_REVIEW
            else "建议人工查找招标公告、前附表或相关附件"
        )
        values = [
            spec.field,
            spec.label,
            status_display(fact.status),
            len(fact.candidates),
            candidate_value_summary(fact),
            fact.resolution_reason,
            action,
        ]
        for column, value in enumerate(values, start=1):
            worksheet.cell(row=row_number, column=column, value=value)
        worksheet.row_dimensions[row_number].height = 42
        row_number += 1
    worksheet.auto_filter.ref = f"A1:G{max(1, row_number - 1)}"
    _style_body(worksheet)


def _verify_workbook(path: Path) -> None:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        expected = ["项目复核表", "字段证据", "解析异常"]
        if workbook.sheetnames != expected:
            raise ValueError(f"Unexpected workbook sheets: {workbook.sheetnames}")
        for sheet_name in expected:
            if workbook[sheet_name].max_row < 1:
                raise ValueError(f"Workbook sheet is empty: {sheet_name}")
    finally:
        workbook.close()


def build_review_workbook(
    project_facts: ProjectFacts,
    output_path: str | Path,
) -> Path:
    """Create and reopen a review workbook using only a validated ProjectFacts."""

    if not isinstance(project_facts, ProjectFacts):
        raise TypeError("build_review_workbook requires a ProjectFacts instance")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = load_output_fields()
    workbook = Workbook()
    _build_review_sheet(workbook, project_facts, fields)
    _build_evidence_sheet(workbook, project_facts, fields)
    _build_exception_sheet(workbook, project_facts, fields)
    workbook.save(path)
    _verify_workbook(path)
    return path


__all__ = ["build_review_workbook"]
