"""Build the user-facing review workbook from the supplied XLSX template."""

from __future__ import annotations

import json
import os
import subprocess
from copy import copy
from math import ceil
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter, range_boundaries

from .document_models import NormalizedDocument
from .dynamic_review import DynamicReviewPlan
from .format_extractor import BidFormatTemplate
from .models import FactStatus, ProjectFacts
from .output_helpers import combine_template_facts, template_value
from .review_evidence import ReviewEvidenceItem


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_PATH = ROOT / "templates" / "投标项目复核表模板.xlsx"
TEMPLATE_SHEET_NAME = "投标项目复核表"
CHECKLIST_EVIDENCE_RANGE = "E9:E72"
CHECKLIST_START_ROW = 9
CHECKLIST_END_ROW = 72

TEMPLATE_TOP_CELL_MAP = {
    "project_name": "B2",
    "project_number_and_tender_number": "F2",
    "purchaser": "I2",
    "tender_agency": "L2",
    "bid_deadline": "B3",
    "bid_open_time": "F3",
    "bid_open_location": "I3",
    "electronic_platform": "L3",
    "budget_and_max_price": "B4",
    "bid_bond": "F4",
    "bid_validity": "I4",
    "submission_method": "L4",
}

TEMPLATE_MANUAL_CELLS = {
    "B5": "【填写】",
    "F5": "【填写】",
    "I5": "【填写】",
    "L5": "【填写】",
}


def _template_value(project_facts: ProjectFacts, field: str) -> str:
    return template_value(getattr(project_facts.fields, field))


def _review_locator(locator: object) -> str:
    """Use a human-readable source location in the user-facing review sheet."""

    data = locator.model_dump(mode="json")
    if "page" in data:
        return f"第{data['page']}页"
    if data.get("locator_type") == "docx_paragraph":
        return f"DOCX第{data['paragraph_index']}段"
    if data.get("locator_type") == "docx_table_cell":
        return (
            f"DOCX表{data['table_index']}行{data['row_index']}列"
            f"{data['cell_index']}"
        )
    return "源文档"


def _fact_evidence(fact) -> str | None:
    if not fact.candidates:
        return None
    method_rank = {
        "table_label_exact": 5,
        "label_value_same_line": 4,
        "labeled_multiline_value": 3,
        "label_value_next_line": 2,
        "platform_phrase": 2,
        "keyword_window": 1,
        "derived_cross_reference": 4,
    }
    candidate = max(
        fact.candidates,
        key=lambda item: (method_rank.get(item.method, 0), item.confidence),
    )
    locator = _review_locator(candidate.locator)
    evidence = " ".join(candidate.evidence_text.split())
    if len(evidence) > 110:
        evidence = evidence[:107].rstrip() + "..."
    section = " ".join(str(candidate.section or "").split())
    if section:
        return f"{locator} / {section} {evidence}".strip()
    return f"{locator} {evidence}".strip()


def _format_evidence(format_template: BidFormatTemplate | None) -> str | None:
    if format_template is None or not format_template.usable:
        return None
    locator = format_template.source_locator
    location = _review_locator(locator) if locator is not None else "源文档"
    return f"{location} {format_template.source_heading or '响应/投标文件格式'}"


def _workbook_review_evidence(item: ReviewEvidenceItem) -> str:
    """Render a compact, traceable evidence string for the fixed-width sheet.

    The packet and Markdown sample retain the longer grounded snippets. The
    template's evidence column has fixed row heights, so writing the full
    retrieval context there makes it clip into adjacent rows. Keep the state,
    page, section cue, and the strongest source text visible without changing
    the template geometry.
    """

    if not item.candidates:
        value = " ".join(item.evidence_text.split())
        return value[:150].rstrip() + ("..." if len(value) > 150 else "")

    candidate_limit = 95 if len(item.candidates) == 1 else 52
    snippets: list[str] = []
    for candidate in item.candidates[:3]:
        page = f"第{candidate.page}页" if candidate.page is not None else "源文档"
        section = " ".join(str(candidate.section or "").split())
        if len(section) > 24:
            section = section[:21].rstrip() + "..."
        source_text = " ".join(candidate.evidence_text.split())
        if len(source_text) > candidate_limit:
            source_text = source_text[: candidate_limit - 3].rstrip() + "..."
        snippets.append(" ".join(part for part in (page, section, source_text) if part))
    value = f"{item.state}：" + "；".join(snippets)
    if len(value) > 175:
        return value[:172].rstrip() + "..."
    return value


def _checklist_evidence(
    project_facts: ProjectFacts,
    *,
    normalized_document: NormalizedDocument | None = None,
    format_template: BidFormatTemplate | None = None,
    review_evidence: list[ReviewEvidenceItem] | None = None,
) -> list[list[str]]:
    """Populate the existing template evidence cells without adding rows."""

    if review_evidence is not None:
        by_id = {
            item.review_item_id: _workbook_review_evidence(item)
            for item in review_evidence
        }
        return [
            [
                by_id.get(
                    f"R{number:03d}",
                    "NOT_FOUND：未检出明确招标文件依据，需人工复核。",
                )
            ]
            for number in range(1, 65)
        ]

    fields = project_facts.fields
    evidence = {
        "consortium": _fact_evidence(fields.consortium_allowed),
        "deadline": _fact_evidence(fields.bid_deadline),
        "open_location": _fact_evidence(fields.bid_open_location),
        "max_price": _fact_evidence(fields.max_price),
        "budget": _fact_evidence(fields.budget),
        "bond_amount": _fact_evidence(fields.bid_bond_amount),
        "bond_form": _fact_evidence(fields.bid_bond_form),
        "validity": _fact_evidence(fields.bid_validity),
        "project_name": _fact_evidence(fields.project_name),
        "project_number": _fact_evidence(fields.project_number),
        "tender_number": _fact_evidence(fields.tender_number),
        "format": _format_evidence(format_template),
    }
    del normalized_document  # reserved for future locator rendering; facts remain SSOT.
    row_text = {
        10: evidence["consortium"],
        11: "；".join(value for value in (evidence["deadline"], evidence["open_location"]) if value),
        16: "；".join(value for value in (evidence["budget"], evidence["max_price"]) if value),
        18: "；".join(value for value in (evidence["bond_amount"], evidence["bond_form"]) if value),
        21: "；".join(
            value
            for value in (
                evidence["project_name"],
                evidence["project_number"],
                evidence["tender_number"],
            )
            if value
        ),
        31: "；".join(value for value in (evidence["validity"], evidence["format"]) if value),
        63: "；".join(value for value in (evidence["bond_amount"], evidence["bond_form"]) if value),
    }
    return [
        [row_text.get(row, "") or "【待核对】"]
        for row in range(CHECKLIST_START_ROW, CHECKLIST_END_ROW + 1)
    ]


def _template_writes(
    project_facts: ProjectFacts,
    *,
    normalized_document: NormalizedDocument | None = None,
    format_template: BidFormatTemplate | None = None,
    review_evidence: list[ReviewEvidenceItem] | None = None,
) -> dict[str, object]:
    """Prepare only the cells allowed by the supplied template contract."""

    fields = project_facts.fields
    return {
        "B2": _template_value(project_facts, "project_name"),
        "F2": combine_template_facts(
            (
                ("项目编号", fields.project_number),
                ("招标编号", fields.tender_number),
            )
        ),
        "I2": _template_value(project_facts, "purchaser"),
        "L2": _template_value(project_facts, "tender_agency"),
        "B3": _template_value(project_facts, "bid_deadline"),
        "F3": _template_value(project_facts, "bid_open_time"),
        "I3": _template_value(project_facts, "bid_open_location"),
        "L3": _template_value(project_facts, "electronic_platform"),
        "B4": combine_template_facts(
            (
                ("预算", fields.budget),
                ("最高限价", fields.max_price),
            )
        ),
        "F4": combine_template_facts(
            (
                ("金额", fields.bid_bond_amount),
                ("形式", fields.bid_bond_form),
            )
        ),
        "I4": _template_value(project_facts, "bid_validity"),
        # ProjectFacts has procurement_method, but it is not submission_method.
        "L4": _template_value(project_facts, "submission_method"),
        # No V1 ProjectFacts fields exist for these manual inputs.
        "B5": TEMPLATE_MANUAL_CELLS["B5"],
        "F5": TEMPLATE_MANUAL_CELLS["F5"],
        "I5": TEMPLATE_MANUAL_CELLS["I5"],
        "L5": TEMPLATE_MANUAL_CELLS["L5"],
        # No deterministic row-level evidence is attached to the 64-item list
        # in this V1 pass. Keep the template's review workflow explicit.
        CHECKLIST_EVIDENCE_RANGE: _checklist_evidence(
            project_facts,
            normalized_document=normalized_document,
            format_template=format_template,
            review_evidence=review_evidence,
        ),
    }


def _artifact_runtime() -> tuple[Path, Path] | None:
    """Locate the bundled Node runtime without relying on global packages."""

    configured_node = os.environ.get("WBTENDER_BUNDLED_NODE")
    configured_modules = os.environ.get("WBTENDER_ARTIFACT_NODE_MODULES")
    node_candidates = [
        Path(configured_node) if configured_node else None,
        Path(
            "C:/Users/WPG/.cache/codex-runtimes/"
            "codex-primary-runtime/dependencies/node/bin/node.exe"
        ),
    ]
    for node_path in node_candidates:
        if node_path is None or not node_path.is_file():
            continue
        module_path = (
            Path(configured_modules)
            if configured_modules
            else node_path.parents[1] / "node_modules"
        )
        artifact_entry = module_path / "@oai" / "artifact-tool" / "dist" / "artifact_tool.mjs"
        if artifact_entry.is_file():
            return node_path, module_path
    return None


def _build_with_artifact_tool(
    template_path: Path,
    output_path: Path,
    writes: dict[str, object],
) -> bool:
    runtime = _artifact_runtime()
    if runtime is None:
        return False
    node_path, node_modules = runtime
    script_path = Path(__file__).with_name("artifact_review_builder.mjs")
    payload = {
        "template_path": str(template_path.resolve()),
        "output_path": str(output_path.resolve()),
        "sheet_name": TEMPLATE_SHEET_NAME,
        "node_modules_dir": str(node_modules.resolve()),
        "writes": writes,
    }
    completed = subprocess.run(
        [str(node_path), str(script_path)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"artifact-tool XLSX build failed: {details}")
    return True


def _template_has_stray_review_row(template_path: Path) -> bool:
    """Detect the legacy unnumbered row shipped between R054 and R055."""

    workbook = load_workbook(template_path, data_only=False, read_only=False)
    try:
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        for row in range(CHECKLIST_START_ROW, 74):
            if worksheet.cell(row=row, column=1).value is None:
                label = str(worksheet.cell(row=row, column=2).value or "").strip()
                if label == "投标保证金":
                    return True
        return False
    finally:
        workbook.close()


def _cell_snapshot(cell) -> dict[str, object]:
    return {
        "value": cell.value,
        "style": copy(cell._style) if cell.has_style else None,
        "number_format": cell.number_format,
        "font": copy(cell.font),
        "fill": copy(cell.fill),
        "border": copy(cell.border),
        "alignment": copy(cell.alignment),
        "protection": copy(cell.protection),
        "hyperlink": copy(cell.hyperlink) if cell.hyperlink else None,
        "comment": copy(cell.comment) if cell.comment else None,
    }


def _restore_cell_snapshot(cell, snapshot: dict[str, object]) -> None:
    cell.value = snapshot["value"]
    if snapshot["style"] is not None:
        cell._style = copy(snapshot["style"])
    cell.number_format = snapshot["number_format"]
    cell.font = copy(snapshot["font"])
    cell.fill = copy(snapshot["fill"])
    cell.border = copy(snapshot["border"])
    cell.alignment = copy(snapshot["alignment"])
    cell.protection = copy(snapshot["protection"])
    cell._hyperlink = copy(snapshot["hyperlink"]) if snapshot["hyperlink"] else None
    cell.comment = copy(snapshot["comment"]) if snapshot["comment"] else None


def _normalize_checklist_layout(workbook) -> int:
    """Remove the supplied template's legacy stray row in-place.

    The operation shifts the existing R055-R064 rows upward by one row, keeps
    the row formatting, and shifts only the affected module merges.  It never
    inserts a new evidence row and returns the number of removed stray rows.
    """

    worksheet = workbook[TEMPLATE_SHEET_NAME]
    stray_row = None
    for row in range(CHECKLIST_START_ROW, 74):
        if worksheet.cell(row=row, column=1).value is None:
            label = str(worksheet.cell(row=row, column=2).value or "").strip()
            if label == "投标保证金":
                stray_row = row
                break
    if stray_row is None:
        return 0

    old_last_row = 73
    max_column = max(worksheet.max_column, 14)
    row_snapshots = {
        row: [
            _cell_snapshot(worksheet.cell(row=row, column=column))
            for column in range(1, max_column + 1)
        ]
        for row in range(stray_row + 1, old_last_row + 1)
    }
    dimension_snapshots = {
        row: {
            "height": worksheet.row_dimensions[row].height,
            "hidden": worksheet.row_dimensions[row].hidden,
            "outlineLevel": worksheet.row_dimensions[row].outlineLevel,
        }
        for row in range(stray_row + 1, old_last_row + 1)
    }
    merge_snapshots = [str(value) for value in worksheet.merged_cells.ranges]
    affected_merges: list[str] = []
    for coordinate in merge_snapshots:
        _min_col, min_row, _max_col, max_row = range_boundaries(coordinate)
        if min_row <= old_last_row and max_row >= stray_row:
            affected_merges.append(coordinate)
            worksheet.unmerge_cells(coordinate)

    for source_row in range(stray_row + 1, old_last_row + 1):
        target_row = source_row - 1
        for column, snapshot in enumerate(row_snapshots[source_row], start=1):
            _restore_cell_snapshot(worksheet.cell(row=target_row, column=column), snapshot)
        source_dimension = dimension_snapshots[source_row]
        target_dimension = worksheet.row_dimensions[target_row]
        target_dimension.height = source_dimension["height"]
        target_dimension.hidden = source_dimension["hidden"]
        target_dimension.outlineLevel = source_dimension["outlineLevel"]

    # The old last checklist row is now unused.  Keep its row object, but
    # remove values so the numbered sequence is exactly 1..64.
    for column in range(1, max_column + 1):
        worksheet.cell(row=old_last_row, column=column).value = None

    for coordinate in affected_merges:
        min_col, min_row, max_col, max_row = range_boundaries(coordinate)
        shifted_min_row = min_row - 1 if min_row > stray_row else min_row
        if max_row == old_last_row:
            # A merge that reached the last checklist row keeps covering it, so
            # every numbered row still carries its 复核模块 label.
            shifted_max_row = old_last_row
        else:
            shifted_max_row = max_row - 1 if max_row > stray_row else max_row
        shifted = (
            f"{get_column_letter(min_col)}{shifted_min_row}:"
            f"{get_column_letter(max_col)}{shifted_max_row}"
        )
        worksheet.merge_cells(shifted)
    return 1


def _build_with_openpyxl(
    template_path: Path,
    output_path: Path,
    writes: dict[str, object],
) -> None:
    """Portable fallback for installations without the bundled JS runtime."""

    workbook = load_workbook(template_path, data_only=False, read_only=False)
    try:
        if TEMPLATE_SHEET_NAME not in workbook.sheetnames:
            raise ValueError(f"Template sheet not found: {TEMPLATE_SHEET_NAME}")
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        _normalize_checklist_layout(workbook)
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        for address, value in writes.items():
            if isinstance(value, list) and value and isinstance(value[0], list):
                min_col, min_row, _max_col, _max_row = range_boundaries(address)
                for row_offset, row_values in enumerate(value):
                    for col_offset, cell_value in enumerate(row_values):
                        worksheet.cell(
                            row=min_row + row_offset,
                            column=min_col + col_offset,
                            value=cell_value,
                        )
            else:
                worksheet[address] = value
        workbook.save(output_path)
    finally:
        workbook.close()


def _fit_evidence_row_heights(path: Path) -> None:
    """Give populated evidence rows enough height without changing the template grid."""

    workbook = load_workbook(path, data_only=False, read_only=False)
    try:
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        for row in range(CHECKLIST_START_ROW, CHECKLIST_END_ROW + 1):
            value = str(worksheet.cell(row=row, column=5).value or "")
            if not value:
                continue
            # The template's evidence column is about 50 character units wide;
            # use a conservative line width for mixed Chinese/Latin evidence.
            line_count = max(1, ceil(len(value) / 38))
            original = worksheet.row_dimensions[row].height or 15.0
            worksheet.row_dimensions[row].height = max(
                original,
                min(90.0, 15.0 * line_count + 8.0),
            )
        workbook.save(path)
    finally:
        workbook.close()


def _verify_workbook(path: Path) -> None:
    workbook = load_workbook(path, data_only=False, read_only=False)
    try:
        if not workbook.sheetnames or workbook.sheetnames[0] != TEMPLATE_SHEET_NAME:
            raise ValueError(f"Primary template sheet is missing: {workbook.sheetnames}")
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        if worksheet.max_row < 77 or worksheet.max_column < 13:
            raise ValueError("Template main sheet no longer covers A1:M77")
        required_merges = {
            "A1:N1",
            "B2:D2",
            "F2:G2",
            "I2:J2",
            "L2:N2",
            "B9:B22",
            "B23:B30",
            "B31:B37",
            "B38:B46",
            "B47:B56",
            "B57:B62",
            "B63:B68",
            # The last module group is extended to the final checklist row when
            # the template's stray row is removed, so every numbered row keeps a
            # 复核模块 label.
            "B69:B73",
            "A75:C75",
            "A76:C76",
            "A77:C77",
        }
        actual_merges = {str(value) for value in worksheet.merged_cells.ranges}
        missing_merges = sorted(required_merges - actual_merges)
        if missing_merges:
            raise ValueError(f"Template merged cells were not preserved: {missing_merges}")
        numbers = [
            worksheet.cell(row=row, column=1).value
            for row in range(CHECKLIST_START_ROW, CHECKLIST_END_ROW + 1)
        ]
        if numbers != list(range(1, 65)) or worksheet.cell(row=73, column=1).value not in (None, ""):
            raise ValueError("Review template must contain exactly numbered items 1..64 with no stray row")
        if worksheet["L4"].value == "公开招标":
            raise ValueError("Submission method must remain a review placeholder")
        if any(
            "自动填充" in str(cell.value)
            for row in worksheet.iter_rows()
            for cell in row
            if cell.value is not None
        ):
            raise ValueError("Template output must not retain internal 自动填充 prompts")
        for address, expected in TEMPLATE_MANUAL_CELLS.items():
            if worksheet[address].value != expected:
                raise ValueError(f"Manual template field was overwritten: {address}")
    finally:
        workbook.close()


SIGNATURE_LABELS: tuple[str, ...] = ("投标小组评审意见：", "分总评审意见：", "大区投标负责人评审意见：")
SIGNATURE_MERGES: tuple[str, ...] = ("A{c}:C{c}", "D{c}:H{c}", "M{c}:N{c}")
#: Rough character capacity of the review requirement column (D) and the
#: evidence column (E); used only to size rows so nothing is visually clipped.
_REQUIREMENT_LINE_CHARS = 34
_MAX_ROW_HEIGHT = 409.0


def _dynamic_row_height(cell_text: str, evidence: str) -> float:
    lines = 0
    for value in (cell_text, evidence):
        for segment in str(value).split("\n"):
            lines += max(1, ceil(len(segment) / _REQUIREMENT_LINE_CHARS))
    return min(_MAX_ROW_HEIGHT, max(15.0, 14.0 * lines + 6.0))


def _build_dynamic_review_rows(
    worksheet,
    plan: "DynamicReviewPlan",
) -> list[list[object]]:
    """Replace the fixed 1..64 checklist span with the dynamic review rows.

    The template's business structure (title block, column titles, module
    column, initial/second/third review columns, signature block) is preserved;
    only the substantive rows become project-specific.
    """

    from .dynamic_review import order_review_items

    items = order_review_items(plan.items)
    donor_row = CHECKLIST_START_ROW
    donours = {
        column: _cell_snapshot(worksheet.cell(row=donor_row, column=column))
        for column in range(1, worksheet.max_column + 1)
    }
    signature_donors = {
        row: {
            column: _cell_snapshot(worksheet.cell(row=row, column=column))
            for column in range(1, worksheet.max_column + 1)
        }
        for row in (75, 76, 77)
    }

    # Drop the fixed checklist and its module merges before rewriting.
    for coordinate in [str(value) for value in worksheet.merged_cells.ranges]:
        min_col, min_row, max_col, max_row = range_boundaries(coordinate)
        if min_row >= CHECKLIST_START_ROW and max_row <= 73:
            worksheet.unmerge_cells(coordinate)
        elif min_row >= 74:
            worksheet.unmerge_cells(coordinate)
    for row in range(CHECKLIST_START_ROW, 78):
        for column in range(1, worksheet.max_column + 1):
            worksheet.cell(row=row, column=column).value = None

    rows: list[list[object]] = []
    module_groups: list[tuple[int, int, str]] = []
    for index, item in enumerate(items):
        row = CHECKLIST_START_ROW + index
        evidence = f"{item.source_locator} {item.source_evidence[:110]}"
        evidence += f"（源条款 {len(item.source_requirement_ids)} 条：{item.source_requirement_ids[0]}）"
        values: list[object] = [None] * worksheet.max_column
        values[0] = index + 1
        values[1] = item.module
        values[2] = item.risk_level
        values[3] = item.cell_text
        values[4] = evidence
        values[5] = "待核对"
        values[8] = "待复核"
        values[12] = (
            f"类型：{item.requirement_type}/{item.submodule or item.topic}"
            + (f"；关联事实：{item.related_project_fact}" if item.related_project_fact else "")
        )
        rows.append(values)
        if not module_groups or module_groups[-1][2] != item.module:
            module_groups.append((row, row, item.module))
        else:
            module_groups[-1] = (module_groups[-1][0], row, item.module)

    for index, values in enumerate(rows):
        row = CHECKLIST_START_ROW + index
        for column, value in enumerate(values, start=1):
            cell = worksheet.cell(row=row, column=column)
            snapshot = donours.get(column)
            if snapshot is not None:
                snapshot = dict(snapshot)
                snapshot["value"] = value
                _restore_cell_snapshot(cell, snapshot)
            else:
                cell.value = value
        worksheet.row_dimensions[row].height = _dynamic_row_height(
            str(values[3] or ""), str(values[4] or "")
        )

    for start, end, module in module_groups:
        if end > start:
            worksheet.merge_cells(start_row=start, start_column=2, end_row=end, end_column=2)
        worksheet.cell(row=start, column=2).value = module
    if module_groups:
        worksheet.cell(row=module_groups[0][0], column=2).alignment = copy(
            donours[2]["alignment"]
        )

    signature_start = CHECKLIST_START_ROW + len(rows) + 1
    for offset, label in enumerate(SIGNATURE_LABELS):
        row = signature_start + offset
        for column in range(1, worksheet.max_column + 1):
            snapshot = dict(signature_donors[75 + offset][column])
            snapshot["value"] = None
            _restore_cell_snapshot(worksheet.cell(row=row, column=column), snapshot)
        worksheet.cell(row=row, column=1).value = label
        worksheet.cell(row=row, column=9).value = "签字："
        worksheet.cell(row=row, column=11).value = "日期：年 月 日"
        for template in SIGNATURE_MERGES:
            worksheet.merge_cells(template.format(c=row))
        worksheet.row_dimensions[row].height = 18.0
    # Drop the now-unused tail rows of the template.
    for row in range(signature_start + len(SIGNATURE_LABELS), max(worksheet.max_row, 78) + 1):
        for column in range(1, worksheet.max_column + 1):
            worksheet.cell(row=row, column=column).value = None
    return rows


def _verify_dynamic_workbook(path: Path, expected_rows: int) -> None:
    workbook = load_workbook(path, data_only=False, read_only=False)
    try:
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        numbers = [
            worksheet.cell(row=row, column=1).value
            for row in range(CHECKLIST_START_ROW, CHECKLIST_START_ROW + expected_rows)
        ]
        if numbers != list(range(1, expected_rows + 1)):
            raise ValueError("Dynamic review rows are not numbered 1..N without gaps")
        if worksheet.cell(row=CHECKLIST_START_ROW + expected_rows, column=1).value is not None:
            raise ValueError("Dynamic review sheet has an unexpected numbered row after the last item")
        for row in range(CHECKLIST_START_ROW, CHECKLIST_START_ROW + expected_rows):
            for column in (3, 4, 5):
                if not str(worksheet.cell(row=row, column=column).value or "").strip():
                    raise ValueError(
                        f"Dynamic review row {row} is missing column {column}"
                    )
        signature_row = CHECKLIST_START_ROW + expected_rows + 1
        if worksheet.cell(row=signature_row, column=1).value != SIGNATURE_LABELS[0]:
            raise ValueError("Dynamic review sheet lost its signature block")
        if any(
            "自动填充" in str(cell.value)
            for row in worksheet.iter_rows()
            for cell in row
            if cell.value is not None
        ):
            raise ValueError("Dynamic review output retained internal 自动填充 prompts")
        for address, expected in TEMPLATE_MANUAL_CELLS.items():
            if worksheet[address].value != expected:
                raise ValueError(f"Manual template field was overwritten: {address}")
        if str(worksheet["D8"].value or "").strip() != (
            "招标文件要求 / 核验标准----复核要点（不限制死）"
        ):
            raise ValueError("Dynamic review sheet lost its requirement column title")
    finally:
        workbook.close()


def build_review_workbook(
    project_facts: ProjectFacts,
    output_path: str | Path,
    template_path: str | Path | None = None,
    *,
    normalized_document: NormalizedDocument | None = None,
    format_template: BidFormatTemplate | None = None,
    review_evidence: list[ReviewEvidenceItem] | None = None,
    dynamic_plan: "DynamicReviewPlan | None" = None,
) -> Path:
    """Copy the supplied review template and fill only approved cells.

    With ``dynamic_plan`` the substantive checklist rows become the
    project-specific dynamic review items; without it the legacy fixed-row
    behaviour is retained for callers that still supply the 64-item taxonomy.
    """

    if not isinstance(project_facts, ProjectFacts):
        raise TypeError("build_review_workbook requires a ProjectFacts instance")
    source_path = Path(template_path) if template_path is not None else DEFAULT_TEMPLATE_PATH
    if not source_path.is_file():
        raise FileNotFoundError(f"Review workbook template does not exist: {source_path}")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writes = _template_writes(
        project_facts,
        normalized_document=normalized_document,
        format_template=format_template,
        review_evidence=review_evidence,
    )
    if dynamic_plan is not None:
        _build_dynamic_workbook(source_path, path, writes, dynamic_plan)
        return path
    used_artifact_tool = (
        not _template_has_stray_review_row(source_path)
        and _build_with_artifact_tool(source_path, path, writes)
    )
    if not used_artifact_tool:
        _build_with_openpyxl(source_path, path, writes)
    _fit_evidence_row_heights(path)
    _verify_workbook(path)
    return path


def _build_dynamic_workbook(
    template_path: Path,
    output_path: Path,
    writes: dict[str, object],
    plan: "DynamicReviewPlan",
) -> None:
    workbook = load_workbook(template_path, data_only=False, read_only=False)
    try:
        if TEMPLATE_SHEET_NAME not in workbook.sheetnames:
            raise ValueError(f"Template sheet not found: {TEMPLATE_SHEET_NAME}")
        _normalize_checklist_layout(workbook)
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        for address, value in writes.items():
            if address == CHECKLIST_EVIDENCE_RANGE:
                continue
            if isinstance(value, list) and value and isinstance(value[0], list):
                min_col, min_row, _max_col, _max_row = range_boundaries(address)
                for row_offset, row_values in enumerate(value):
                    for col_offset, cell_value in enumerate(row_values):
                        worksheet.cell(
                            row=min_row + row_offset,
                            column=min_col + col_offset,
                            value=cell_value,
                        )
            else:
                worksheet[address] = value
        _build_dynamic_review_rows(worksheet, plan)
        workbook.save(output_path)
    finally:
        workbook.close()
    _verify_dynamic_workbook(output_path, len(plan.items))


def read_dynamic_review_rows(path: Path) -> list[list[object]]:
    """Read back the written dynamic rows for the workbook QA cross-check."""

    workbook = load_workbook(path, data_only=False, read_only=False)
    try:
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        rows: list[list[object]] = []
        for row in range(CHECKLIST_START_ROW, worksheet.max_row + 1):
            if str(worksheet.cell(row=row, column=1).value or "").strip() == SIGNATURE_LABELS[0]:
                break
            if worksheet.cell(row=row, column=1).value in (None, ""):
                continue
            rows.append(
                [
                    worksheet.cell(row=row, column=column).value
                    for column in range(1, worksheet.max_column + 1)
                ]
            )
        return rows
    finally:
        workbook.close()


def count_stray_review_rows(path: str | Path) -> int:
    """Count unnumbered non-empty rows inside the checklist span.

    The span is dynamic from Round 5.5 on: it runs from the first checklist row
    to the row before the signature block, so a project-specific row count does
    not hide a stray template row.
    """

    workbook = load_workbook(path, data_only=False, read_only=False)
    try:
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        last_row = CHECKLIST_END_ROW + 1
        for row in range(CHECKLIST_START_ROW, worksheet.max_row + 1):
            if str(worksheet.cell(row=row, column=1).value or "").strip() == SIGNATURE_LABELS[0]:
                last_row = row - 1
                break
        return sum(
            1
            for row in range(CHECKLIST_START_ROW, last_row + 1)
            if worksheet.cell(row=row, column=1).value in (None, "")
            and any(
                worksheet.cell(row=row, column=column).value not in (None, "")
                for column in range(2, 14)
            )
        )
    finally:
        workbook.close()


__all__ = [
    "CHECKLIST_EVIDENCE_RANGE",
    "CHECKLIST_START_ROW",
    "CHECKLIST_END_ROW",
    "DEFAULT_TEMPLATE_PATH",
    "SIGNATURE_LABELS",
    "TEMPLATE_MANUAL_CELLS",
    "TEMPLATE_SHEET_NAME",
    "TEMPLATE_TOP_CELL_MAP",
    "build_review_workbook",
    "count_stray_review_rows",
    "read_dynamic_review_rows",
]
