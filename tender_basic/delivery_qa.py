"""Disk-artifact delivery QA for the template-driven V1 outputs."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

from .models import FactStatus, FieldName, ProjectFacts
from .fact_normalizer import is_resolved_value_type_valid
from .output_helpers import (
    combine_template_facts,
    docx_value,
    load_output_fields,
    template_value,
    value_text,
)
from .review_builder import (
    CHECKLIST_END_ROW,
    CHECKLIST_START_ROW,
    TEMPLATE_MANUAL_CELLS,
    TEMPLATE_TOP_CELL_MAP,
    TEMPLATE_SHEET_NAME,
)


QA_PASS = "PASS"
QA_PASS_WITH_REVIEW = "PASS_WITH_REVIEW"
QA_FAIL = "FAIL"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_WARN = "WARN"

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_ERROR = "ERROR"

FORBIDDEN_SUBMISSION_STATUS = "READY_FOR_SUBMISSION"
_FORMAT_SOURCE_RE = re.compile(r"(?:^|;)\s*format_source=([A-Z_]+)")


def _check(
    *,
    check_id: str,
    name: str,
    status: str,
    severity: str,
    message: str,
    field: str | None = None,
    expected: Any = None,
    actual: Any = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "name": name,
        "status": status,
        "severity": severity,
        "message": message,
        "field": field,
        "expected": expected,
        "actual": actual,
    }


def _text(value: object) -> str:
    if value is None:
        return ""
    return value_text(value).strip()


def _label_key(value: object) -> str:
    return "".join(_text(value).split())


def _artifact_info(path: Path) -> dict[str, Any]:
    exists = path.is_file()
    return {
        "path": path.name,
        "exists": exists,
        "size": path.stat().st_size if exists else 0,
    }


def _file_check(checks: list[dict[str, Any]], *, artifact_name: str, path: Path) -> None:
    info = _artifact_info(path)
    if not info["exists"] or info["size"] <= 0:
        checks.append(
            _check(
                check_id=f"artifact_exists_{artifact_name}",
                name=f"{artifact_name} exists and is non-empty",
                status=CHECK_FAIL,
                severity=SEVERITY_ERROR,
                message=f"Required artifact is missing or empty: {artifact_name}.",
                expected="file with size > 0",
                actual=info,
            )
        )
    else:
        checks.append(
            _check(
                check_id=f"artifact_exists_{artifact_name}",
                name=f"{artifact_name} exists and is non-empty",
                status=CHECK_PASS,
                severity=SEVERITY_INFO,
                message=f"Artifact exists and is non-empty: {artifact_name}.",
                expected="file with size > 0",
                actual=info,
            )
        )


def _load_project_facts(path: Path, checks: list[dict[str, Any]]) -> ProjectFacts | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        facts = ProjectFacts.model_validate(payload)
    except Exception as exc:
        checks.append(
            _check(
                check_id="project_facts_contract",
                name="ProjectFacts contract validation",
                status=CHECK_FAIL,
                severity=SEVERITY_ERROR,
                message=f"ProjectFacts could not be validated: {exc.__class__.__name__}.",
                expected="valid ProjectFacts JSON",
                actual="invalid",
            )
        )
        return None
    checks.append(
        _check(
            check_id="project_facts_contract",
            name="ProjectFacts contract validation",
            status=CHECK_PASS,
            severity=SEVERITY_INFO,
            message="ProjectFacts was reloaded and validated with Pydantic.",
            expected="valid ProjectFacts JSON",
            actual="valid",
        )
    )
    return facts


def _all_text(workbook) -> str:
    values: list[str] = []
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows(values_only=True):
            values.extend(_text(value) for value in row if _text(value))
    return "\n".join(values)


def _required_template_merges() -> set[str]:
    """Structural merges of the review template's title block.

    The module merges and the signature block move with the project-specific
    row count from Round 5.5 on, so they are validated by position instead of
    by the template's fixed coordinates.
    """

    return {
        "A1:N1",
        "B2:D2",
        "F2:G2",
        "I2:J2",
        "L2:N2",
        "B3:D3",
        "F3:G3",
        "I3:J3",
        "L3:N3",
        "B4:D4",
        "F4:G4",
        "I4:J4",
        "L4:N4",
        "B5:D5",
        "F5:G5",
        "I5:J5",
        "L5:N5",
    }


def _signature_merges(start_row: int) -> set[str]:
    """Signature block merges the template actually ships.

    The label and opinion spans exist on all three rows; the template's 备注
    span only exists on the first two, so those are the ones required.
    """

    merges: set[str] = set()
    for offset in range(3):
        row = start_row + offset
        merges.update({f"A{row}:C{row}", f"D{row}:H{row}"})
    merges.update({f"M{start_row}:N{start_row}", f"M{start_row + 1}:N{start_row + 1}"})
    return merges


def _locate_signature_row(worksheet) -> int:
    """Find the first signature row of the review sheet (moves with the rows)."""

    for row in range(CHECKLIST_START_ROW, worksheet.max_row + 1):
        if _text(worksheet.cell(row=row, column=1).value) == "投标小组评审意见：":
            return row
    return 75


def _review_module_labels(worksheet) -> tuple[list[str], list[int]]:
    """Resolve the effective 复核模块 label of every checklist row."""

    labels: list[str] = []
    uncovered: list[int] = []
    merge_lookup: dict[int, str] = {}
    for coordinate in worksheet.merged_cells.ranges:
        min_col, min_row, max_col, max_row = range_boundaries(str(coordinate))
        if min_col <= 2 <= max_col and min_row >= CHECKLIST_START_ROW:
            value = _text(worksheet.cell(row=min_row, column=2).value)
            for row in range(min_row, max_row + 1):
                merge_lookup[row] = value
    for row in range(CHECKLIST_START_ROW, worksheet.max_row + 1):
        first = _text(worksheet.cell(row=row, column=1).value)
        if first == "投标小组评审意见：":
            break
        if not first:
            continue
        label = _text(worksheet.cell(row=row, column=2).value) or merge_lookup.get(row, "")
        labels.append(label)
        if not label:
            uncovered.append(row)
    return labels, uncovered


def _load_xlsx(path: Path, checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        workbook = load_workbook(path, data_only=False, read_only=False)
    except Exception as exc:
        checks.append(
            _check(
                check_id="xlsx_reopen",
                name="XLSX can be reopened",
                status=CHECK_FAIL,
                severity=SEVERITY_ERROR,
                message=f"XLSX could not be reopened: {exc.__class__.__name__}.",
                expected="readable workbook",
                actual="unreadable",
            )
        )
        return None

    try:
        checks.append(
            _check(
                check_id="xlsx_reopen",
                name="XLSX can be reopened",
                status=CHECK_PASS,
                severity=SEVERITY_INFO,
                message="XLSX was reopened from disk with openpyxl.",
                expected="readable workbook",
                actual="readable",
            )
        )
        result: dict[str, Any] = {
            "all_text": _all_text(workbook),
            "sheetnames": list(workbook.sheetnames),
            "main_sheet_name": TEMPLATE_SHEET_NAME if TEMPLATE_SHEET_NAME in workbook.sheetnames else None,
            "top": {},
            "checklist_numbers": [],
            "internal_prompt_found": False,
        }
        result["internal_prompt_found"] = "自动填充" in result["all_text"]
        checks.append(
            _check(
                check_id="xlsx_no_internal_template_prompts",
                name="XLSX has no internal 自动填充 prompts",
                status=CHECK_FAIL if result["internal_prompt_found"] else CHECK_PASS,
                severity=SEVERITY_ERROR if result["internal_prompt_found"] else SEVERITY_INFO,
                message="The final user workbook does not retain internal template prompts."
                if not result["internal_prompt_found"]
                else "The final user workbook still contains an internal 自动填充 prompt.",
                expected="absent",
                actual="found" if result["internal_prompt_found"] else "absent",
            )
        )
        if TEMPLATE_SHEET_NAME not in workbook.sheetnames:
            checks.append(
                _check(
                    check_id="xlsx_template_sheet",
                    name="XLSX primary template sheet exists",
                    status=CHECK_FAIL,
                    severity=SEVERITY_ERROR,
                    message="The supplied review-template main sheet is missing.",
                    expected=TEMPLATE_SHEET_NAME,
                    actual=workbook.sheetnames,
                )
            )
            return result

        checks.append(
            _check(
                check_id="xlsx_template_sheet",
                name="XLSX primary template sheet exists",
                status=CHECK_PASS,
                severity=SEVERITY_INFO,
                message="The template main sheet is present.",
                expected=TEMPLATE_SHEET_NAME,
                actual=TEMPLATE_SHEET_NAME,
            )
        )
        worksheet = workbook[TEMPLATE_SHEET_NAME]
        actual_merges = {str(value) for value in worksheet.merged_cells.ranges}
        signature_row = _locate_signature_row(worksheet)
        required_merges = _required_template_merges() | _signature_merges(signature_row)
        module_labels, uncovered_module_rows = _review_module_labels(worksheet)
        structure_actual = {
            "dimension": worksheet.calculate_dimension(),
            "max_row": worksheet.max_row,
            "max_column": worksheet.max_column,
            "signature_row": signature_row,
            "review_row_count": len(module_labels),
            "uncovered_module_rows": uncovered_module_rows,
            "module_labels": module_labels,
            "merged_count": len(actual_merges),
            "missing_merges": sorted(required_merges - actual_merges),
        }
        structure_ok = (
            worksheet.max_row >= signature_row + 2
            and worksheet.max_column >= 13
            and not structure_actual["missing_merges"]
            and not uncovered_module_rows
        )
        checks.append(
            _check(
                check_id="xlsx_template_structure",
                name="XLSX template layout and merged cells are preserved",
                status=CHECK_PASS if structure_ok else CHECK_FAIL,
                severity=SEVERITY_INFO if structure_ok else SEVERITY_ERROR,
                message="Template title block, module column and signature block were checked."
                if structure_ok
                else "Template range, module column or signature block was changed.",
                expected={
                    "title_block_merges": sorted(_required_template_merges()),
                    "signature_merges": sorted(_signature_merges(signature_row)),
                    "every_review_row_carries_a_module": True,
                },
                actual=structure_actual,
            )
        )

        header_values = [worksheet.cell(row=8, column=column).value for column in range(1, 14)]
        required_headers = {
            "序号",
            "复核模块",
            "风险等级",
            "招标文件依据\n（章节/条款/页脚页码）",
            "初审结论",
            "二次复核",
            "三次复核",
            "备注",
        }
        header_set = {_text(value) for value in header_values}
        missing_headers = sorted(required_headers - header_set)
        header_ok = not missing_headers
        checks.append(
            _check(
                check_id="xlsx_template_headers",
                name="XLSX template checklist headers are preserved",
                status=CHECK_PASS if header_ok else CHECK_FAIL,
                severity=SEVERITY_INFO if header_ok else SEVERITY_ERROR,
                message="The 64-item checklist header row is present."
                if header_ok
                else "The checklist header row is incomplete.",
                expected=sorted(required_headers),
                actual={"missing": missing_headers, "values": header_values},
            )
        )

        numbers: list[int] = []
        stray_rows = []
        for row_number in range(CHECKLIST_START_ROW, signature_row):
            value = worksheet.cell(row=row_number, column=1).value
            if value is None or not _text(value):
                if any(
                    worksheet.cell(row=row_number, column=column).value not in (None, "")
                    for column in range(2, 14)
                ):
                    stray_rows.append(row_number)
                continue
            try:
                numbers.append(int(value))
            except (TypeError, ValueError):
                numbers.append(-1)
        result["checklist_numbers"] = numbers
        footer_labels = [
            _text(worksheet.cell(row=row, column=1).value)
            for row in range(signature_row, signature_row + 3)
        ]
        dynamic_count = len(numbers)
        checklist_ok = (
            dynamic_count >= 1
            and numbers == list(range(1, dynamic_count + 1))
            and not stray_rows
            and all(footer_labels)
        )
        checks.append(
            _check(
                check_id="xlsx_template_checklist",
                name="XLSX dynamic review rows and review footer remain",
                status=CHECK_PASS if checklist_ok else CHECK_FAIL,
                severity=SEVERITY_INFO if checklist_ok else SEVERITY_ERROR,
                message="The source-generated review rows and the end review/signature area remain in place."
                if checklist_ok
                else "The generated review rows or the review/signature area was changed.",
                expected={"numbered_items": "1..N generated from the source", "footer_rows": 3},
                actual={
                    "numbered_item_count": dynamic_count,
                    "first_item": numbers[0] if numbers else None,
                    "last_item": numbers[-1] if numbers else None,
                    "footer_labels": footer_labels,
                    "stray_rows": stray_rows,
                },
            )
        )
        result["stray_rows"] = stray_rows
        result["dynamic_review_row_count"] = dynamic_count

        result["top"] = {
            key: worksheet[address].value
            for key, address in TEMPLATE_TOP_CELL_MAP.items()
        }
        result["manual"] = {
            address: worksheet[address].value for address in TEMPLATE_MANUAL_CELLS
        }
        return result
    finally:
        workbook.close()


def _expected_template_top(facts: ProjectFacts) -> dict[str, str]:
    fields = facts.fields
    return {
        "project_name": template_value(fields.project_name),
        "project_number_and_tender_number": combine_template_facts(
            (("项目编号", fields.project_number), ("招标编号", fields.tender_number))
        ),
        "purchaser": template_value(fields.purchaser),
        "tender_agency": template_value(fields.tender_agency),
        "bid_deadline": template_value(fields.bid_deadline),
        "bid_open_time": template_value(fields.bid_open_time),
        "bid_open_location": template_value(fields.bid_open_location),
        "electronic_platform": template_value(fields.electronic_platform),
        "budget_and_max_price": combine_template_facts(
            (("预算", fields.budget), ("最高限价", fields.max_price))
        ),
        "bid_bond": combine_template_facts(
            (("金额", fields.bid_bond_amount), ("形式", fields.bid_bond_form))
        ),
        "bid_validity": template_value(fields.bid_validity),
        "submission_method": template_value(fields.submission_method),
    }


def _candidate_leak(facts: ProjectFacts, key: str, actual: str) -> bool:
    field_groups = {
        "project_name": (facts.fields.project_name,),
        "project_number_and_tender_number": (
            facts.fields.project_number,
            facts.fields.tender_number,
        ),
        "purchaser": (facts.fields.purchaser,),
        "tender_agency": (facts.fields.tender_agency,),
        "bid_deadline": (facts.fields.bid_deadline,),
        "bid_open_time": (facts.fields.bid_open_time,),
        "bid_open_location": (facts.fields.bid_open_location,),
        "electronic_platform": (facts.fields.electronic_platform,),
        "budget_and_max_price": (facts.fields.budget, facts.fields.max_price),
        "bid_bond": (facts.fields.bid_bond_amount, facts.fields.bid_bond_form),
        "bid_validity": (facts.fields.bid_validity,),
        "submission_method": (facts.fields.submission_method,),
    }
    for fact in field_groups.get(key, ()):
        if fact.status not in {FactStatus.NEEDS_REVIEW, FactStatus.NOT_FOUND}:
            continue
        for candidate in fact.candidates:
            candidate_text = value_text(candidate.value).strip()
            if candidate_text and candidate_text in actual:
                return True
    return False


def _check_xlsx_top_facts(
    checks: list[dict[str, Any]],
    facts: ProjectFacts,
    xlsx_data: dict[str, Any] | None,
) -> None:
    expected = _expected_template_top(facts)
    actual_values = (xlsx_data or {}).get("top", {})
    for key, expected_value in expected.items():
        actual_value = _text(actual_values.get(key))
        passed = actual_value == expected_value and not _candidate_leak(facts, key, actual_value)
        checks.append(
            _check(
                check_id=f"xlsx_top_{key}",
                name=f"XLSX template top field: {key}",
                status=CHECK_PASS if passed else CHECK_FAIL,
                severity=SEVERITY_INFO if passed else SEVERITY_ERROR,
                message="Template top field matches ProjectFacts and status protection rules."
                if passed
                else "Template top field is missing, mixed, or leaks an unresolved candidate.",
                field=key,
                expected=expected_value,
                actual=actual_value,
            )
        )

    manual_actual = (xlsx_data or {}).get("manual", {})
    manual_ok = all(
        _text(manual_actual.get(address)) == expected
        for address, expected in TEMPLATE_MANUAL_CELLS.items()
    )
    checks.append(
        _check(
            check_id="xlsx_manual_fields_not_guessed",
            name="XLSX manual template fields remain manual",
            status=CHECK_PASS if manual_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if manual_ok else SEVERITY_ERROR,
            message="AR, SR, tender owner, and division owner remain template prompts."
            if manual_ok
            else "A manual template field was filled or changed.",
            expected=TEMPLATE_MANUAL_CELLS,
            actual=manual_actual,
        )
    )
    submission_actual = _text(actual_values.get("submission_method"))
    submission_expected = expected["submission_method"]
    submission_ok = submission_actual == submission_expected
    procurement = facts.fields.procurement_method
    if (
        submission_ok
        and procurement.status == FactStatus.RESOLVED
        and facts.fields.submission_method.status != FactStatus.RESOLVED
        and submission_actual == _text(procurement.resolved_value)
    ):
        submission_ok = False
    checks.append(
        _check(
            check_id="xlsx_submission_method_not_procurement_method",
            name="XLSX 投标方式 does not use procurement_method",
            status=CHECK_PASS if submission_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if submission_ok else SEVERITY_ERROR,
            message="投标方式 is mapped only from submission_method, never procurement_method."
            if submission_ok
            else "投标方式 appears to have been filled from procurement_method.",
            expected=submission_expected,
            actual=submission_actual,
        )
    )


def _find_docx_info_table(document: Document, field_specs) -> dict[str, str]:
    expected_labels = {_label_key(spec.label): spec.field for spec in field_specs}
    best_mapping: dict[str, str] = {}
    for table in document.tables:
        mapping: dict[str, str] = {}
        for row in table.rows:
            if len(row.cells) < 2:
                continue
            field = expected_labels.get(_label_key(row.cells[0].text))
            if field is not None:
                mapping[field] = row.cells[1].text.strip()
        if len(mapping) > len(best_mapping):
            best_mapping = mapping
    return best_mapping


def _format_source_from_document(document: Document) -> str | None:
    subject = document.core_properties.subject or ""
    keywords = document.core_properties.keywords or ""
    for value in (subject, keywords):
        match = _FORMAT_SOURCE_RE.search(value)
        if match:
            return match.group(1)
    return None


def _direct_paragraph_text(element) -> str:
    """Read only direct paragraph runs, excluding nested text-box content."""

    values: list[str] = []
    for child in element:
        if child.tag != qn("w:r"):
            continue
        for run_child in child:
            if run_child.tag == qn("w:t") and run_child.text:
                values.append(run_child.text)
    return "".join(values)


def _visible_docx_paragraphs(document: Document) -> list[str]:
    """Return visible body and text-box paragraphs in document XML order."""

    result: list[str] = []
    body = document.element.body
    textbox_tag = qn("w:txbxContent")
    paragraph_tag = qn("w:p")
    for element in body.iter(paragraph_tag):
        nested_in_textbox = any(ancestor.tag == textbox_tag for ancestor in element.iterancestors())
        text = _direct_paragraph_text(element)
        if text or nested_in_textbox:
            result.append(text)
    return result


def _load_docx(path: Path, checks: list[dict[str, Any]], field_specs) -> dict[str, Any] | None:
    try:
        document = Document(path)
    except Exception as exc:
        checks.append(
            _check(
                check_id="docx_reopen",
                name="DOCX can be reopened",
                status=CHECK_FAIL,
                severity=SEVERITY_ERROR,
                message=f"DOCX could not be reopened: {exc.__class__.__name__}.",
                expected="readable DOCX",
                actual="unreadable",
            )
        )
        return None

    visible_paragraphs = _visible_docx_paragraphs(document)
    paragraph_count = len(visible_paragraphs)
    table_count = len(document.tables)
    format_source = _format_source_from_document(document)
    source_document_mode = format_source == "SOURCE_DOCUMENT"
    basic_structure_ok = paragraph_count > 0 and (source_document_mode or table_count > 0)
    checks.append(
        _check(
            check_id="docx_reopen",
            name="DOCX can be reopened",
            status=CHECK_PASS,
            severity=SEVERITY_INFO,
            message="DOCX was reopened from disk with python-docx.",
            expected={"paragraphs": ">0", "tables": ">=0 for SOURCE_DOCUMENT, >0 otherwise"},
            actual={"paragraphs": paragraph_count, "tables": table_count},
        )
    )
    checks.append(
        _check(
            check_id="docx_basic_structure",
            name="DOCX has paragraphs and source-format tables when required",
            status=CHECK_PASS if basic_structure_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if basic_structure_ok else SEVERITY_ERROR,
            message="DOCX contains the required paragraph/table structure."
            if basic_structure_ok
            else "DOCX does not contain the minimum paragraph/table structure for its mode.",
            expected={"paragraphs": ">0", "tables": ">=0 for SOURCE_DOCUMENT, >0 otherwise"},
            actual={"paragraphs": paragraph_count, "tables": table_count},
        )
    )
    info_mapping = _find_docx_info_table(document, field_specs)
    expected_fields = {spec.field for spec in field_specs}
    info_ok = source_document_mode or (
        set(info_mapping) == expected_fields and len(info_mapping) == len(expected_fields)
    )
    checks.append(
        _check(
            check_id="docx_info_field_coverage",
            name="DOCX project information table covers all V1 fields",
            status=CHECK_PASS if info_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if info_ok else SEVERITY_ERROR,
            message=(
                "SOURCE_DOCUMENT mode does not require a generic project information table."
                if source_document_mode
                else "DOCX project information table field coverage was checked."
            ),
            expected=(
                "not required in SOURCE_DOCUMENT mode"
                if source_document_mode
                else {"count": len(expected_fields), "fields": sorted(expected_fields)}
            ),
            actual={"count": len(info_mapping), "fields": sorted(info_mapping)},
        )
    )
    format_ok = format_source in {"SOURCE_DOCUMENT", "GENERIC_FALLBACK"}
    checks.append(
        _check(
            check_id="docx_format_source_metadata",
            name="DOCX format_source metadata is present",
            status=CHECK_PASS if format_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if format_ok else SEVERITY_ERROR,
            message="DOCX records the selected source-format or fallback mode."
            if format_ok
            else "DOCX does not record a supported format_source value.",
            expected=["SOURCE_DOCUMENT", "GENERIC_FALLBACK"],
            actual=format_source,
        )
    )
    table_text = [
        cell.text.strip()
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    ]
    paragraph_text = [paragraph.strip() for paragraph in visible_paragraphs]
    return {
        "document": document,
        "info": info_mapping,
        "format_source": format_source,
        "table_count": table_count,
        "all_text": "\n".join(paragraph_text + table_text),
    }


def _check_docx_format_metadata(
    checks: list[dict[str, Any]],
    docx_data: dict[str, Any] | None,
    expected_format_source: str | None,
    format_metadata: dict[str, Any] | None,
) -> None:
    if docx_data is None:
        return
    actual = docx_data.get("format_source")
    expected = expected_format_source or (format_metadata or {}).get("format_source")
    if expected is None:
        return
    source_ok = actual == expected
    checks.append(
        _check(
            check_id="docx_format_source_matches_pipeline",
            name="DOCX format_source matches the pipeline decision",
            status=CHECK_PASS if source_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if source_ok else SEVERITY_ERROR,
            message="DOCX format_source matches the source-format decision."
            if source_ok
            else "DOCX format_source differs from the source-format decision.",
            expected=expected,
            actual=actual,
        )
    )
    if expected == "SOURCE_DOCUMENT":
        document = docx_data["document"]
        metadata = format_metadata or {}
        actual_paragraphs = [paragraph.strip() for paragraph in _visible_docx_paragraphs(document) if paragraph.strip()]
        source_heading = _text(metadata.get("source_heading"))
        no_wrapper = not any(
            paragraph in {"投 标 文 件", "项目基本信息"}
            for paragraph in actual_paragraphs
        )
        starts_at_source = not source_heading or (
            bool(actual_paragraphs) and actual_paragraphs[0] == source_heading
        )
        checks.append(
            _check(
                check_id="docx_source_format_no_generic_wrapper",
                name="SOURCE_DOCUMENT DOCX has no generic wrapper",
                status=CHECK_PASS if no_wrapper and starts_at_source else CHECK_FAIL,
                severity=SEVERITY_INFO if no_wrapper and starts_at_source else SEVERITY_ERROR,
                message="Source-format output starts at the source heading without a generic cover."
                if no_wrapper and starts_at_source
                else "SOURCE_DOCUMENT output contains a generic wrapper or does not start at the source heading.",
                expected={"first_paragraph": source_heading, "generic_wrapper": "absent"},
                actual={"first_paragraph": actual_paragraphs[0] if actual_paragraphs else "", "generic_wrapper": not no_wrapper},
            )
        )
        expected_table_count = int(metadata.get("table_count", 0) or 0)
        actual_table_count = int(docx_data.get("table_count", 0) or 0)
        # A PDF page fragment is not a logical table.  When the pipeline reports
        # the logical table count, the DOCX must carry exactly one editable table
        # per logical table: continuation fragments are folded into the table they
        # continue, so the count is equal rather than "at least the fragment count".
        logical_table_count = int(metadata.get("logical_table_count", 0) or 0)
        orphan_continuations = int(metadata.get("orphan_continuation_fragments", 0) or 0)
        false_merges = int(metadata.get("false_continuation_merges", 0) or 0)
        if logical_table_count:
            tables_ok = (
                actual_table_count == logical_table_count
                and not orphan_continuations
                and not false_merges
            )
            expected_tables: object = {
                "logical_tables": logical_table_count,
                "pdf_table_fragments": expected_table_count,
                "output_tables": logical_table_count,
            }
            tables_message_ok = (
                "Every logical source table is one editable DOCX table; "
                "continuation page fragments are folded into it."
            )
            tables_message_bad = (
                "The DOCX table count does not match the logical table count, or a "
                "continuation fragment was orphaned or merged without evidence."
            )
        else:
            tables_ok = actual_table_count >= expected_table_count
            expected_tables = {"source_tables": expected_table_count, "output_tables": f">={expected_table_count}"}
            tables_message_ok = "Detected source-format tables are represented as editable DOCX tables."
            tables_message_bad = "Source-format table count was not preserved in the DOCX output."
        checks.append(
            _check(
                check_id="docx_source_format_tables",
                name="SOURCE_DOCUMENT tables remain editable DOCX tables",
                status=CHECK_PASS if tables_ok else CHECK_FAIL,
                severity=SEVERITY_INFO if tables_ok else SEVERITY_ERROR,
                message=tables_message_ok if tables_ok else tables_message_bad,
                expected=expected_tables,
                actual=actual_table_count,
            )
        )
    if expected != "SOURCE_DOCUMENT" or not format_metadata:
        return
    expected_titles = [
        _text(title)
        for title in format_metadata.get(
            "primary_heading_titles",
            format_metadata.get("heading_titles", []),
        )
        if _text(title)
    ]
    if not expected_titles:
        return
    actual_paragraphs = [paragraph.strip() for paragraph in _visible_docx_paragraphs(docx_data["document"]) if paragraph.strip()]
    # PDF text extraction can put a fixed placeholder and its following
    # instruction on the same source block.  SOURCE_DOCUMENT filling may also
    # replace that placeholder with a resolved purchaser/project fact.  Compare
    # the first logical heading line for order, while preserving the complete
    # source text in the generated document.
    def heading_key(value: str) -> str:
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        text = re.sub(r"\s+", " ", lines[0] if lines else "")
        text = re.sub(
            r"[（(]\s*(?:项目名称|标段名称|招标人名称|采购人名称)\s*[）)]",
            "<source-fact>",
            text,
        )
        text = re.sub(r"【(?:待人工确认|待补充)】", "<source-fact>", text)
        return re.sub(r"\s+", "", text)

    expected_heading_keys = [heading_key(title) for title in expected_titles]
    actual_heading_keys = [heading_key(title) for title in actual_paragraphs]
    position = -1
    ordered = True
    for title in expected_heading_keys:
        try:
            position = actual_heading_keys.index(title, position + 1)
        except ValueError:
            ordered = False
            break
    checks.append(
        _check(
            check_id="docx_source_format_heading_order",
            name="DOCX preserves source-format heading order",
            status=CHECK_PASS if ordered else CHECK_FAIL,
            severity=SEVERITY_INFO if ordered else SEVERITY_ERROR,
            message="Source-format headings appear in source order."
            if ordered
            else "Source-format headings are missing or out of order.",
            expected=expected_titles,
            actual=actual_paragraphs,
        )
    )


def _compare_docx_outputs(
    checks: list[dict[str, Any]],
    facts: ProjectFacts,
    field_specs,
    docx_data: dict[str, Any] | None,
) -> None:
    if docx_data is not None and docx_data.get("format_source") == "SOURCE_DOCUMENT":
        # Source-format output intentionally has no generic ProjectFacts table;
        # its fixed-form placeholders are checked by the source-format builder
        # and wrapper/table checks instead.
        return
    for spec in field_specs:
        fact = getattr(facts.fields, spec.field)
        expected = docx_value(fact)
        actual = None
        if docx_data is not None and spec.field in docx_data["info"]:
            actual = _text(docx_data["info"][spec.field])
        passed = actual == expected
        if fact.status in {FactStatus.NEEDS_REVIEW, FactStatus.NOT_FOUND} and actual is not None:
            candidate_values = {
                value_text(candidate.value).strip()
                for candidate in fact.candidates
                if value_text(candidate.value).strip()
            }
            if actual in candidate_values:
                passed = False
        checks.append(
            _check(
                check_id=f"docx_field_{spec.field}",
                name=f"DOCX field value: {spec.field}",
                status=CHECK_PASS if passed else CHECK_FAIL,
                severity=SEVERITY_INFO if passed else SEVERITY_ERROR,
                message="DOCX project information row matches ProjectFacts and status protection rules."
                if passed
                else "DOCX project information row does not match ProjectFacts or leaks a candidate.",
                field=spec.field,
                expected=expected,
                actual=actual,
            )
        )

    for first_field, second_field, label in (
        ("project_number", "tender_number", "project/tender number independence"),
        ("budget", "max_price", "budget/max-price independence"),
    ):
        first_fact = getattr(facts.fields, first_field)
        second_fact = getattr(facts.fields, second_field)
        if (
            first_fact.status != FactStatus.RESOLVED
            or second_fact.status != FactStatus.RESOLVED
            or value_text(first_fact.resolved_value) == value_text(second_fact.resolved_value)
        ):
            continue
        expected_pair = {
            first_field: value_text(first_fact.resolved_value),
            second_field: value_text(second_fact.resolved_value),
        }
        actual_pair = {
            first_field: (docx_data or {}).get("info", {}).get(first_field),
            second_field: (docx_data or {}).get("info", {}).get(second_field),
        }
        actual_pair = {field: _text(value) for field, value in actual_pair.items()}
        passed = actual_pair == expected_pair
        checks.append(
            _check(
                check_id=f"docx_{first_field}_{second_field}_independence",
                name=f"DOCX {label}",
                status=CHECK_PASS if passed else CHECK_FAIL,
                severity=SEVERITY_INFO if passed else SEVERITY_ERROR,
                message="DOCX preserves independent field values."
                if passed
                else "DOCX appears to exchange independent field values.",
                expected=expected_pair,
                actual=actual_pair,
            )
        )


def _is_placeholder(value: str) -> bool:
    compact = value.replace(" ", "").replace("\u3000", "")
    return not compact or set(compact) == {"_"}


def _is_source_bidder_instruction(value: str) -> bool:
    """Allow fixed source-format signature prompts, not company identities."""

    compact = value.replace(" ", "").replace("\u3000", "")
    if not compact.startswith(("（", "(")):
        return False
    return any(
        token in compact
        for token in ("盖", "签字", "填写", "名称", "公章", "印章", "章")
    )


def _check_bidder_placeholder(
    checks: list[dict[str, Any]],
    docx_data: dict[str, Any] | None,
) -> None:
    if docx_data is None:
        return
    document: Document = docx_data["document"]
    cover_value = None
    if document.tables:
        for row in document.tables[0].rows:
            if len(row.cells) >= 2 and _label_key(row.cells[0].text) == "投标人":
                cover_value = row.cells[1].text.strip()
                break
    observed_values: list[str] = []
    for line_value in _visible_docx_paragraphs(document):
        line = line_value.strip()
        if line.startswith("投标人：") or line.startswith("投标人:"):
            observed_values.append(re.split(r"[：:]", line, maxsplit=1)[1].strip())
    for table in document.tables:
        for row in table.rows:
            if not row.cells:
                continue
            first = row.cells[0].text.strip()
            if _label_key(first) == "投标人" and len(row.cells) >= 2:
                observed_values.append(row.cells[1].text.strip())
            elif first.startswith("投标人：") or first.startswith("投标人:"):
                observed_values.append(re.split(r"[：:]", first, maxsplit=1)[1].strip())
    generic_requires_letter = docx_data.get("format_source") == "GENERIC_FALLBACK"
    letter_ok = bool(observed_values) if generic_requires_letter else True
    source_format = docx_data.get("format_source") == "SOURCE_DOCUMENT"
    values_ok = _is_placeholder(cover_value or "") and all(
        _is_placeholder(value)
        or (source_format and _is_source_bidder_instruction(value))
        for value in observed_values
    )
    passed = (bool(cover_value) and letter_ok and values_ok) if not source_format else (
        values_ok and all(
            _is_placeholder(value) or _is_source_bidder_instruction(value)
            for value in observed_values
        )
    )
    checks.append(
        _check(
            check_id="docx_bidder_placeholder",
            name="DOCX bidder remains a manual placeholder",
            status=CHECK_PASS if passed else CHECK_FAIL,
            severity=SEVERITY_INFO if passed else SEVERITY_ERROR,
            message="DOCX does not fabricate a bidder identity."
            if passed
            else "DOCX bidder area is not preserved as a manual placeholder.",
            expected="underscore or blank bidder fields",
            actual={"cover": cover_value, "observed": observed_values},
        )
    )


def _check_project_facts_evidence(checks: list[dict[str, Any]], facts: ProjectFacts) -> None:
    candidate_count = sum(
        len(getattr(facts.fields, field.value).candidates) for field in FieldName
    )
    evidence_ok = all(
        getattr(facts.fields, field.value).candidates
        if getattr(facts.fields, field.value).status != FactStatus.NOT_FOUND
        else not getattr(facts.fields, field.value).candidates
        for field in FieldName
    )
    checks.append(
        _check(
            check_id="project_facts_candidate_evidence_integrity",
            name="ProjectFacts retains candidate evidence independently",
            status=CHECK_PASS if evidence_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if evidence_ok else SEVERITY_ERROR,
            message="Candidate evidence is checked from project_facts.json, not from the user workbook."
            if evidence_ok
            else "ProjectFacts candidate evidence does not match the status contract.",
            expected="NOT_FOUND has no candidates; other statuses retain evidence",
            actual={"candidate_count": candidate_count},
        )
    )


def _check_project_facts_value_types(
    checks: list[dict[str, Any]],
    facts: ProjectFacts,
) -> None:
    invalid = [
        field.value
        for field in FieldName
        if (
            getattr(facts.fields, field.value).status == FactStatus.RESOLVED
            and not is_resolved_value_type_valid(
                field,
                getattr(facts.fields, field.value).resolved_value,
            )
        )
    ]
    checks.append(
        _check(
            check_id="project_facts_value_types",
            name="Resolved ProjectFacts values pass field-type validation",
            status=CHECK_FAIL if invalid else CHECK_PASS,
            severity=SEVERITY_ERROR if invalid else SEVERITY_INFO,
            message="All resolved values pass their canonical field validators."
            if not invalid
            else "One or more resolved values fail their canonical field validators.",
            expected="no invalid resolved values",
            actual=invalid or "none",
        )
    )
def _check_forbidden_status(
    checks: list[dict[str, Any]],
    facts: ProjectFacts | None,
    xlsx_data: dict[str, Any] | None,
    docx_data: dict[str, Any] | None,
) -> None:
    fragments: list[str] = []
    if facts is not None:
        fragments.append(json.dumps(facts.model_dump(mode="json"), ensure_ascii=False))
    if xlsx_data is not None:
        fragments.append(xlsx_data["all_text"])
    if docx_data is not None:
        fragments.append(docx_data["all_text"])
    found = any(FORBIDDEN_SUBMISSION_STATUS in fragment for fragment in fragments)
    checks.append(
        _check(
            check_id="no_submission_ready_status",
            name="No submission-ready status is emitted",
            status=CHECK_FAIL if found else CHECK_PASS,
            severity=SEVERITY_ERROR if found else SEVERITY_INFO,
            message="A forbidden submission-ready status was found in an artifact."
            if found
            else "No forbidden submission-ready status was found.",
            expected="absent",
            actual="found" if found else "absent",
        )
    )


def run_delivery_qa(
    facts_path: str | Path,
    xlsx_path: str | Path,
    docx_path: str | Path,
    *,
    format_source: str | None = None,
    format_metadata: dict[str, Any] | None = None,
    review_evidence_qa: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reload final artifacts and return a structured template-aware QA report."""

    facts_path = Path(facts_path)
    xlsx_path = Path(xlsx_path)
    docx_path = Path(docx_path)
    checks: list[dict[str, Any]] = []
    artifacts = {
        "facts": _artifact_info(facts_path),
        "xlsx": _artifact_info(xlsx_path),
        "docx": _artifact_info(docx_path),
    }
    for artifact_name, path in (
        ("facts", facts_path),
        ("xlsx", xlsx_path),
        ("docx", docx_path),
    ):
        _file_check(checks, artifact_name=artifact_name, path=path)

    try:
        field_specs = load_output_fields()
    except Exception as exc:
        field_specs = ()
        checks.append(
            _check(
                check_id="output_field_catalog",
                name="Output field catalog is valid",
                status=CHECK_FAIL,
                severity=SEVERITY_ERROR,
                message=f"Output field catalog could not be loaded: {exc.__class__.__name__}.",
                expected="configured V1 fields",
                actual="invalid",
            )
        )
    else:
        checks.append(
            _check(
                check_id="output_field_catalog",
                name="Output field catalog is valid",
                status=CHECK_PASS,
                severity=SEVERITY_INFO,
                message="QA loaded the fixed V1 field catalog from YAML.",
                expected=len(FieldName),
                actual=len(field_specs),
            )
        )

    facts = _load_project_facts(facts_path, checks) if facts_path.is_file() else None
    xlsx_data = _load_xlsx(xlsx_path, checks) if xlsx_path.is_file() else None
    docx_data = _load_docx(docx_path, checks, field_specs) if docx_path.is_file() else None

    if facts is not None:
        _check_project_facts_evidence(checks, facts)
        _check_project_facts_value_types(checks, facts)
        _check_xlsx_top_facts(checks, facts, xlsx_data)
        _compare_docx_outputs(checks, facts, field_specs, docx_data)
        needs_review = facts.summary.needs_review
        not_found = facts.summary.not_found
        if needs_review or not_found:
            checks.append(
                _check(
                    check_id="business_review_state",
                    name="Business review state is surfaced",
                    status=CHECK_WARN,
                    severity=SEVERITY_WARNING,
                    message="ProjectFacts contains fields requiring human review or supplementation.",
                    expected={"needs_review": 0, "not_found": 0},
                    actual={"needs_review": needs_review, "not_found": not_found},
                )
            )
        else:
            checks.append(
                _check(
                    check_id="business_review_state",
                    name="Business review state is surfaced",
                    status=CHECK_PASS,
                    severity=SEVERITY_INFO,
                    message="ProjectFacts contains no NEEDS_REVIEW or NOT_FOUND fields.",
                    expected={"needs_review": 0, "not_found": 0},
                    actual={"needs_review": 0, "not_found": 0},
                )
            )

    _check_docx_format_metadata(checks, docx_data, format_source, format_metadata)
    _check_bidder_placeholder(checks, docx_data)
    _check_forbidden_status(checks, facts, xlsx_data, docx_data)
    if review_evidence_qa is not None:
        evidence_ok = (
            review_evidence_qa.get("total_review_items") == 64
            and review_evidence_qa.get("unclassified") == 0
            and review_evidence_qa.get("invalid_locators") == 0
            and review_evidence_qa.get("stray_rows") == 0
            and review_evidence_qa.get("result") == "PASS"
        )
        checks.append(
            _check(
                check_id="review_evidence_coverage",
                name="64 review items have validated evidence states",
                status=CHECK_PASS if evidence_ok else CHECK_FAIL,
                severity=SEVERITY_INFO if evidence_ok else SEVERITY_ERROR,
                message=(
                    "Review evidence states and locators passed the release contract."
                    if evidence_ok
                    else "Review evidence coverage or locator validation failed."
                ),
                expected={
                    "total_review_items": 64,
                    "unclassified": 0,
                    "invalid_locators": 0,
                    "stray_rows": 0,
                },
                actual=review_evidence_qa,
            )
        )

    errors = [check for check in checks if check["status"] == CHECK_FAIL]
    warnings = [check for check in checks if check["status"] == CHECK_WARN]
    if errors:
        overall_status = QA_FAIL
    elif facts is not None and (facts.summary.needs_review or facts.summary.not_found):
        overall_status = QA_PASS_WITH_REVIEW
    else:
        overall_status = QA_PASS

    report_format_source = (
        format_source
        or (format_metadata or {}).get("format_source")
        or (docx_data or {}).get("format_source")
        or "UNKNOWN"
    )
    summary = {
        "total_fields": facts.summary.total_fields if facts is not None else 0,
        "resolved": facts.summary.resolved if facts is not None else 0,
        "needs_review": facts.summary.needs_review if facts is not None else 0,
        "not_found": facts.summary.not_found if facts is not None else 0,
        "candidate_count": (
            sum(
                len(getattr(facts.fields, spec.field).candidates)
                for spec in field_specs
            )
            if facts is not None
            else 0
        ),
        "check_count": len(checks),
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
    return {
        "overall_status": overall_status,
        "format_source": report_format_source,
        "format_section": format_metadata or {},
        "review_evidence_qa": review_evidence_qa or {},
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
        "artifacts": artifacts,
    }


def write_qa_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def qa_exit_code(overall_status: str) -> int:
    """Business review is successful for shell orchestration; QA failure is not."""

    if overall_status in {QA_PASS, QA_PASS_WITH_REVIEW}:
        return 0
    if overall_status == QA_FAIL:
        return 2
    return 3


__all__ = [
    "CHECK_FAIL",
    "CHECK_PASS",
    "CHECK_WARN",
    "QA_FAIL",
    "QA_PASS",
    "QA_PASS_WITH_REVIEW",
    "qa_exit_code",
    "run_delivery_qa",
    "write_qa_report",
]
