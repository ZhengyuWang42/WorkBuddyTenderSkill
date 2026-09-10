"""Disk-artifact delivery QA for the V1 tender outputs.

The QA layer deliberately reloads every final artifact.  It does not trust
objects returned by the builders and it does not reopen the source tender
document.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from docx import Document
from openpyxl import load_workbook

from .models import FactStatus, ProjectFacts
from .output_helpers import (
    docx_value,
    load_output_fields,
    status_display,
    value_text,
    xlsx_value,
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

XLSX_SHEET_NAMES = ["项目复核表", "字段证据", "解析异常"]
FORBIDDEN_SUBMISSION_STATUS = "READY_FOR_SUBMISSION"


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
    """Create one stable, JSON-serializable QA check record."""

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
    size = path.stat().st_size if exists else 0
    return {
        "path": path.name,
        "exists": exists,
        "size": size,
    }


def _file_check(
    checks: list[dict[str, Any]],
    *,
    artifact_name: str,
    path: Path,
) -> None:
    info = _artifact_info(path)
    if not info["exists"]:
        checks.append(
            _check(
                check_id=f"artifact_exists_{artifact_name}",
                name=f"{artifact_name} exists and is non-empty",
                status=CHECK_FAIL,
                severity=SEVERITY_ERROR,
                message=f"Required artifact does not exist: {artifact_name}.",
                expected="file with size > 0",
                actual=info,
            )
        )
    elif info["size"] <= 0:
        checks.append(
            _check(
                check_id=f"artifact_exists_{artifact_name}",
                name=f"{artifact_name} exists and is non-empty",
                status=CHECK_FAIL,
                severity=SEVERITY_ERROR,
                message=f"Required artifact is empty: {artifact_name}.",
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


def _load_project_facts(
    path: Path,
    checks: list[dict[str, Any]],
) -> ProjectFacts | None:
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


def _records(worksheet) -> list[list[object]]:
    rows: list[list[object]] = []
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        values = list(row)
        if any(value is not None and _text(value) for value in values):
            rows.append(values)
    return rows


def _headers(worksheet) -> dict[str, int]:
    rows = worksheet.iter_rows(min_row=1, max_row=1, values_only=True)
    try:
        header_row = next(rows)
    except StopIteration:
        return {}
    return {
        _text(value): index
        for index, value in enumerate(header_row)
        if _text(value)
    }


def _row_value(row: list[object], header_map: dict[str, int], header: str) -> object:
    index = header_map.get(header)
    if index is None or index >= len(row):
        return None
    return row[index]


def _load_xlsx(
    path: Path,
    checks: list[dict[str, Any]],
    field_specs,
) -> dict[str, Any] | None:
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
                expected="openpyxl workbook",
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

        if workbook.sheetnames != XLSX_SHEET_NAMES:
            checks.append(
                _check(
                    check_id="xlsx_sheet_structure",
                    name="XLSX has the three fixed sheets",
                    status=CHECK_FAIL,
                    severity=SEVERITY_ERROR,
                    message="XLSX sheet structure does not match the V1 contract.",
                    expected=XLSX_SHEET_NAMES,
                    actual=workbook.sheetnames,
                )
            )
        else:
            checks.append(
                _check(
                    check_id="xlsx_sheet_structure",
                    name="XLSX has the three fixed sheets",
                    status=CHECK_PASS,
                    severity=SEVERITY_INFO,
                    message="All three fixed XLSX sheets are present.",
                    expected=XLSX_SHEET_NAMES,
                    actual=workbook.sheetnames,
                )
            )

        all_text: list[str] = []
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows(values_only=True):
                all_text.extend(_text(value) for value in row if _text(value))

        result: dict[str, Any] = {
            "all_text": "\n".join(all_text),
            "review": {},
            "evidence_by_field": Counter(),
            "evidence_fields": set(),
            "exceptions": {},
            "exception_duplicates": [],
        }

        if "项目复核表" in workbook.sheetnames:
            worksheet = workbook["项目复核表"]
            header_map = _headers(worksheet)
            required = {"字段编码", "自动提取值", "状态"}
            missing = sorted(required - set(header_map))
            if missing:
                checks.append(
                    _check(
                        check_id="xlsx_review_headers",
                        name="XLSX review sheet headers",
                        status=CHECK_FAIL,
                        severity=SEVERITY_ERROR,
                        message="XLSX review sheet is missing required headers.",
                        expected=sorted(required),
                        actual=missing,
                    )
                )
            else:
                checks.append(
                    _check(
                        check_id="xlsx_review_headers",
                        name="XLSX review sheet headers",
                        status=CHECK_PASS,
                        severity=SEVERITY_INFO,
                        message="XLSX review sheet has required headers.",
                        expected=sorted(required),
                        actual=sorted(required),
                    )
                )
                field_header = header_map["字段编码"]
                for row in _records(worksheet):
                    field = _text(row[field_header]) if field_header < len(row) else ""
                    if not field:
                        continue
                    if field in result["review"]:
                        result.setdefault("review_duplicates", []).append(field)
                    result["review"][field] = {
                        header: _row_value(row, header_map, header)
                        for header in required
                    }

        if "字段证据" in workbook.sheetnames:
            worksheet = workbook["字段证据"]
            header_map = _headers(worksheet)
            required = {"字段编码", "证据原文"}
            missing = sorted(required - set(header_map))
            if missing:
                checks.append(
                    _check(
                        check_id="xlsx_evidence_headers",
                        name="XLSX evidence sheet headers",
                        status=CHECK_FAIL,
                        severity=SEVERITY_ERROR,
                        message="XLSX evidence sheet is missing required headers.",
                        expected=sorted(required),
                        actual=missing,
                    )
                )
            else:
                checks.append(
                    _check(
                        check_id="xlsx_evidence_headers",
                        name="XLSX evidence sheet headers",
                        status=CHECK_PASS,
                        severity=SEVERITY_INFO,
                        message="XLSX evidence sheet has required headers.",
                        expected=sorted(required),
                        actual=sorted(required),
                    )
                )
                field_header = header_map["字段编码"]
                for row in _records(worksheet):
                    field = _text(row[field_header]) if field_header < len(row) else ""
                    if field:
                        result["evidence_by_field"][field] += 1
                        result["evidence_fields"].add(field)

        if "解析异常" in workbook.sheetnames:
            worksheet = workbook["解析异常"]
            header_map = _headers(worksheet)
            required = {"字段编码", "状态"}
            missing = sorted(required - set(header_map))
            if missing:
                checks.append(
                    _check(
                        check_id="xlsx_exception_headers",
                        name="XLSX exception sheet headers",
                        status=CHECK_FAIL,
                        severity=SEVERITY_ERROR,
                        message="XLSX exception sheet is missing required headers.",
                        expected=sorted(required),
                        actual=missing,
                    )
                )
            else:
                checks.append(
                    _check(
                        check_id="xlsx_exception_headers",
                        name="XLSX exception sheet headers",
                        status=CHECK_PASS,
                        severity=SEVERITY_INFO,
                        message="XLSX exception sheet has required headers.",
                        expected=sorted(required),
                        actual=sorted(required),
                    )
                )
                field_header = header_map["字段编码"]
                status_header = header_map["状态"]
                for row in _records(worksheet):
                    field = _text(row[field_header]) if field_header < len(row) else ""
                    if not field:
                        continue
                    status_value = _text(row[status_header]) if status_header < len(row) else ""
                    if field in result["exceptions"]:
                        result["exception_duplicates"].append(field)
                    result["exceptions"][field] = status_value

        expected_fields = {spec.field for spec in field_specs}
        review_fields = set(result["review"])
        review_duplicates = result.get("review_duplicates", [])
        review_ok = review_fields == expected_fields and not review_duplicates
        checks.append(
            _check(
                check_id="xlsx_review_field_coverage",
                name="XLSX review sheet covers all V1 fields",
                status=CHECK_PASS if review_ok else CHECK_FAIL,
                severity=SEVERITY_INFO if review_ok else SEVERITY_ERROR,
                message="XLSX review sheet field coverage was checked.",
                expected={"count": len(expected_fields), "fields": sorted(expected_fields)},
                actual={
                    "count": len(review_fields),
                    "fields": sorted(review_fields),
                    "duplicates": sorted(set(review_duplicates)),
                },
            )
        )
        return result
    finally:
        workbook.close()


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


def _load_docx(
    path: Path,
    checks: list[dict[str, Any]],
    field_specs,
) -> dict[str, Any] | None:
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

    paragraph_count = len(document.paragraphs)
    table_count = len(document.tables)
    basic_structure_ok = paragraph_count > 0 and table_count > 0
    checks.append(
        _check(
            check_id="docx_reopen",
            name="DOCX can be reopened",
            status=CHECK_PASS,
            severity=SEVERITY_INFO,
            message="DOCX was reopened from disk with python-docx.",
            expected={"paragraphs": ">0", "tables": ">0"},
            actual={"paragraphs": paragraph_count, "tables": table_count},
        )
    )
    if not basic_structure_ok:
        checks.append(
            _check(
                check_id="docx_basic_structure",
                name="DOCX has paragraphs and tables",
                status=CHECK_FAIL,
                severity=SEVERITY_ERROR,
                message="DOCX does not contain the minimum paragraph/table structure.",
                expected={"paragraphs": ">0", "tables": ">0"},
                actual={"paragraphs": paragraph_count, "tables": table_count},
            )
        )
    else:
        checks.append(
            _check(
                check_id="docx_basic_structure",
                name="DOCX has paragraphs and tables",
                status=CHECK_PASS,
                severity=SEVERITY_INFO,
                message="DOCX contains paragraphs and tables.",
                expected={"paragraphs": ">0", "tables": ">0"},
                actual={"paragraphs": paragraph_count, "tables": table_count},
            )
        )

    table_text = [
        cell.text.strip()
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    ]
    paragraph_text = [paragraph.text.strip() for paragraph in document.paragraphs]
    info_mapping = _find_docx_info_table(document, field_specs)
    expected_fields = {spec.field for spec in field_specs}
    info_ok = set(info_mapping) == expected_fields and len(info_mapping) == len(expected_fields)
    checks.append(
        _check(
            check_id="docx_info_field_coverage",
            name="DOCX project information table covers all V1 fields",
            status=CHECK_PASS if info_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if info_ok else SEVERITY_ERROR,
            message="DOCX project information table field coverage was checked.",
            expected={"count": len(expected_fields), "fields": sorted(expected_fields)},
            actual={"count": len(info_mapping), "fields": sorted(info_mapping)},
        )
    )
    return {
        "document": document,
        "info": info_mapping,
        "all_text": "\n".join(paragraph_text + table_text),
    }


def _compare_outputs(
    checks: list[dict[str, Any]],
    facts: ProjectFacts,
    field_specs,
    xlsx_data: dict[str, Any] | None,
    docx_data: dict[str, Any] | None,
) -> None:
    for spec in field_specs:
        fact = getattr(facts.fields, spec.field)
        expected_xlsx = {
            "status": status_display(fact.status),
            "value": xlsx_value(fact),
        }
        actual_xlsx = None
        if xlsx_data is not None and spec.field in xlsx_data["review"]:
            actual_xlsx = xlsx_data["review"][spec.field]
            actual_xlsx = {
                "status": _text(actual_xlsx.get("状态")),
                "value": _text(actual_xlsx.get("自动提取值")),
            }
        xlsx_ok = actual_xlsx == expected_xlsx
        if fact.status in {FactStatus.NEEDS_REVIEW, FactStatus.NOT_FOUND} and actual_xlsx is not None:
            candidate_values = {
                value_text(candidate.value).strip()
                for candidate in fact.candidates
                if value_text(candidate.value).strip()
            }
            if actual_xlsx["value"] in candidate_values:
                xlsx_ok = False
        checks.append(
            _check(
                check_id=f"xlsx_field_{spec.field}",
                name=f"XLSX field value and status: {spec.field}",
                status=CHECK_PASS if xlsx_ok else CHECK_FAIL,
                severity=SEVERITY_INFO if xlsx_ok else SEVERITY_ERROR,
                message="XLSX field output matches ProjectFacts and status protection rules."
                if xlsx_ok
                else "XLSX field output does not match ProjectFacts or leaks a candidate.",
                field=spec.field,
                expected=expected_xlsx,
                actual=actual_xlsx,
            )
        )

        expected_docx = docx_value(fact)
        actual_docx = None
        if docx_data is not None and spec.field in docx_data["info"]:
            actual_docx = _text(docx_data["info"][spec.field])
        docx_ok = actual_docx == expected_docx
        if fact.status in {FactStatus.NEEDS_REVIEW, FactStatus.NOT_FOUND} and actual_docx is not None:
            candidate_values = {
                value_text(candidate.value).strip()
                for candidate in fact.candidates
                if value_text(candidate.value).strip()
            }
            if actual_docx in candidate_values:
                docx_ok = False
        checks.append(
            _check(
                check_id=f"docx_field_{spec.field}",
                name=f"DOCX field value: {spec.field}",
                status=CHECK_PASS if docx_ok else CHECK_FAIL,
                severity=SEVERITY_INFO if docx_ok else SEVERITY_ERROR,
                message="DOCX project information row matches ProjectFacts and status protection rules."
                if docx_ok
                else "DOCX project information row does not match ProjectFacts or leaks a candidate.",
                field=spec.field,
                expected=expected_docx,
                actual=actual_docx,
            )
        )

    expected_candidate_counts = Counter(
        {
            spec.field: len(getattr(facts.fields, spec.field).candidates)
            for spec in field_specs
        }
    )
    actual_candidate_counts = (
        xlsx_data["evidence_by_field"] if xlsx_data is not None else Counter()
    )
    evidence_ok = expected_candidate_counts == actual_candidate_counts
    checks.append(
        _check(
            check_id="xlsx_candidate_evidence_completeness",
            name="XLSX exports every CandidateFact",
            status=CHECK_PASS if evidence_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if evidence_ok else SEVERITY_ERROR,
            message="XLSX evidence rows match ProjectFacts candidate counts."
            if evidence_ok
            else "XLSX evidence rows do not match ProjectFacts candidate counts.",
            expected=dict(sorted(expected_candidate_counts.items())),
            actual=dict(sorted(actual_candidate_counts.items())),
        )
    )

    expected_exceptions = {
        spec.field: getattr(facts.fields, spec.field).status.value
        for spec in field_specs
        if getattr(facts.fields, spec.field).status
        in {FactStatus.NEEDS_REVIEW, FactStatus.NOT_FOUND}
    }
    actual_exceptions = (
        xlsx_data["exceptions"] if xlsx_data is not None else {}
    )
    actual_exception_codes = {
        field: next(
            (status.value for status in FactStatus if status.value in status_text),
            status_text,
        )
        for field, status_text in actual_exceptions.items()
    }
    exceptions_ok = (
        expected_exceptions == actual_exception_codes
        and not (xlsx_data or {}).get("exception_duplicates", [])
    )
    checks.append(
        _check(
            check_id="xlsx_exception_completeness",
            name="XLSX exception sheet matches unresolved fields",
            status=CHECK_PASS if exceptions_ok else CHECK_FAIL,
            severity=SEVERITY_INFO if exceptions_ok else SEVERITY_ERROR,
            message="XLSX exception rows match NEEDS_REVIEW and NOT_FOUND fields."
            if exceptions_ok
            else "XLSX exception rows do not match unresolved ProjectFacts fields.",
            expected=expected_exceptions,
            actual=actual_exception_codes,
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
        for channel, values in (
            (
                "xlsx",
                {
                    first_field: (xlsx_data or {})
                    .get("review", {})
                    .get(first_field, {})
                    .get("自动提取值"),
                    second_field: (xlsx_data or {})
                    .get("review", {})
                    .get(second_field, {})
                    .get("自动提取值"),
                },
            ),
            (
                "docx",
                {
                    first_field: (docx_data or {}).get("info", {}).get(first_field),
                    second_field: (docx_data or {}).get("info", {}).get(second_field),
                },
            ),
        ):
            values = {field: _text(value) for field, value in values.items()}
            pair_ok = values == expected_pair
            checks.append(
                _check(
                    check_id=f"{channel}_{first_field}_{second_field}_independence",
                    name=f"{channel.upper()} {label}",
                    status=CHECK_PASS if pair_ok else CHECK_FAIL,
                    severity=SEVERITY_INFO if pair_ok else SEVERITY_ERROR,
                    message=f"{channel.upper()} preserves independent field values."
                    if pair_ok
                    else f"{channel.upper()} appears to exchange independent field values.",
                    expected=expected_pair,
                    actual=values,
                )
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
    letter_lines = [paragraph.text.strip() for paragraph in document.paragraphs]
    letter_values = [
        line.split("：", 1)[1].strip()
        for line in letter_lines
        if line.startswith("投标人：")
    ]
    cover_ok = bool(cover_value) and set(cover_value.replace(" ", "")) == {"_"}
    letter_ok = bool(letter_values) and all(
        value and set(value.replace(" ", "")) == {"_"}
        for value in letter_values
    )
    passed = cover_ok and letter_ok
    checks.append(
        _check(
            check_id="docx_bidder_placeholder",
            name="DOCX bidder remains a manual placeholder",
            status=CHECK_PASS if passed else CHECK_FAIL,
            severity=SEVERITY_INFO if passed else SEVERITY_ERROR,
            message="DOCX does not fabricate a bidder identity."
            if passed
            else "DOCX bidder area is not preserved as a manual placeholder.",
            expected="underscore placeholder on cover and bid letter",
            actual={"cover": cover_value, "bid_letter": letter_values},
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
) -> dict[str, Any]:
    """Reload final disk artifacts and return a structured QA report."""

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
                expected="20 configured V1 fields",
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
                expected=20,
                actual=len(field_specs),
            )
        )

    facts = _load_project_facts(facts_path, checks) if facts_path.is_file() else None
    xlsx_data = _load_xlsx(xlsx_path, checks, field_specs) if xlsx_path.is_file() else None
    docx_data = _load_docx(docx_path, checks, field_specs) if docx_path.is_file() else None

    if facts is not None and field_specs:
        _compare_outputs(checks, facts, field_specs, xlsx_data, docx_data)
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

    _check_bidder_placeholder(checks, docx_data)
    _check_forbidden_status(checks, facts, xlsx_data, docx_data)

    errors = [check for check in checks if check["status"] == CHECK_FAIL]
    warnings = [check for check in checks if check["status"] == CHECK_WARN]
    if errors:
        overall_status = QA_FAIL
    elif facts is not None and (
        facts.summary.needs_review or facts.summary.not_found
    ):
        overall_status = QA_PASS_WITH_REVIEW
    else:
        overall_status = QA_PASS

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
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
        "artifacts": artifacts,
    }


def write_qa_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
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
