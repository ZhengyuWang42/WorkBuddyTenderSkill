from __future__ import annotations

import json

import pytest
from openpyxl import load_workbook

from tender_basic.document_models import DocumentStatus
from tender_basic.models import (
    CandidateFact,
    DocxParagraphLocator,
    DocxTableLocator,
    FactStatus,
    FieldName,
    ProjectFacts,
    ProjectFields,
    ResolvedFact,
    SourceDocument,
    SourceType,
)
from tender_basic.output_helpers import load_output_fields
from tender_basic.review_builder import build_review_workbook


def _candidate(
    value: str,
    *,
    paragraph_index: int | None = None,
    table_index: int | None = None,
    row_index: int = 0,
    cell_index: int = 0,
    method: str = "label_value_same_line",
    confidence: float = 0.95,
) -> CandidateFact:
    if paragraph_index is not None:
        locator = DocxParagraphLocator(paragraph_index=paragraph_index)
    else:
        locator = DocxTableLocator(
            table_index=table_index or 0,
            row_index=row_index,
            cell_index=cell_index,
        )
    return CandidateFact(
        value=value,
        normalized_value=value,
        confidence=confidence,
        method=method,
        source_file="sample.docx",
        source_type=SourceType.DOCX,
        locator=locator,
        section="招标公告",
        evidence_text=f"字段证据：{value}",
    )


def _resolved(field: FieldName, value: str, candidates: list[CandidateFact]) -> ResolvedFact:
    return ResolvedFact(
        field=field,
        resolved_value=value,
        status=FactStatus.RESOLVED,
        confidence=max(candidate.confidence for candidate in candidates),
        candidates=candidates,
        resolution_reason="Test resolved fact.",
    )


def _review(field: FieldName, values: list[str]) -> ResolvedFact:
    candidates = [
        _candidate(value, paragraph_index=20 + index, confidence=0.8)
        for index, value in enumerate(values)
    ]
    return ResolvedFact(
        field=field,
        resolved_value=None,
        status=FactStatus.NEEDS_REVIEW,
        confidence=0.8,
        candidates=candidates,
        resolution_reason="Conflicting test candidates.",
    )


def _not_found(field: FieldName) -> ResolvedFact:
    return ResolvedFact(
        field=field,
        resolved_value=None,
        status=FactStatus.NOT_FOUND,
        confidence=0.0,
        candidates=[],
        resolution_reason="No test candidate.",
    )


def make_project_facts() -> ProjectFacts:
    fields = {}
    for field in FieldName:
        fields[field.value] = _not_found(field)

    fields[FieldName.PROJECT_NAME.value] = _resolved(
        FieldName.PROJECT_NAME,
        "测试工程",
        [
            _candidate("测试工程", paragraph_index=0),
            _candidate("测试工程", paragraph_index=1),
            _candidate("测试工程", table_index=0, row_index=0, cell_index=1, method="table_label_exact", confidence=0.98),
        ],
    )
    fields[FieldName.PROJECT_NUMBER.value] = _resolved(
        FieldName.PROJECT_NUMBER,
        "PRJ-123",
        [_candidate("PRJ-123", paragraph_index=2)],
    )
    fields[FieldName.TENDER_NUMBER.value] = _resolved(
        FieldName.TENDER_NUMBER,
        "BID-456",
        [_candidate("BID-456", paragraph_index=3)],
    )
    fields[FieldName.PURCHASER.value] = _resolved(
        FieldName.PURCHASER,
        "采购人甲",
        [_candidate("采购人甲", paragraph_index=4)],
    )
    fields[FieldName.BUDGET.value] = _resolved(
        FieldName.BUDGET,
        "80万元",
        [_candidate("80万元", paragraph_index=5)],
    )
    fields[FieldName.MAX_PRICE.value] = _resolved(
        FieldName.MAX_PRICE,
        "100万元",
        [_candidate("100万元", paragraph_index=6)],
    )
    fields[FieldName.PROJECT_LOCATION.value] = _review(
        FieldName.PROJECT_LOCATION,
        ["地点A", "地点B"],
    )

    project_fields = ProjectFields(**fields)
    return ProjectFacts.from_fields(
        source_document=SourceDocument(
            source_file="sample.docx",
            source_type=SourceType.DOCX,
        ),
        fields=project_fields,
    )


def _row_by_field(worksheet, field_code: str) -> tuple:
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        if row[2] == field_code:
            return row
    raise AssertionError(f"Field row not found: {field_code}")


def test_review_workbook_has_three_sheets_and_twenty_fixed_fields(tmp_path) -> None:
    output = tmp_path / "投标项目复核表.xlsx"
    build_review_workbook(make_project_facts(), output)

    workbook = load_workbook(output, read_only=False, data_only=False)
    try:
        assert workbook.sheetnames == ["项目复核表", "字段证据", "解析异常"]
        worksheet = workbook["项目复核表"]
        assert worksheet.max_row == 21
        assert worksheet.freeze_panes == "A2"
        assert worksheet.auto_filter.ref == "A1:K21"
        assert [row[2].value for row in worksheet.iter_rows(min_row=2)] == [
            spec.field for spec in load_output_fields()
        ]
    finally:
        workbook.close()


def test_review_workbook_preserves_statuses_and_separate_numbers(tmp_path) -> None:
    output = tmp_path / "review.xlsx"
    build_review_workbook(make_project_facts(), output)
    workbook = load_workbook(output, read_only=True, data_only=False)
    try:
        worksheet = workbook["项目复核表"]
        project_number = _row_by_field(worksheet, "project_number")
        tender_number = _row_by_field(worksheet, "tender_number")
        review = _row_by_field(worksheet, "project_location")
        missing = _row_by_field(worksheet, "bid_bond_amount")

        assert project_number[4] == "PRJ-123"
        assert tender_number[4] == "BID-456"
        assert project_number[4] != tender_number[4]
        assert project_number[5] == "已解析 (RESOLVED)"
        assert review[4] == "【存在冲突，见字段证据】"
        assert review[5] == "需复核 (NEEDS_REVIEW)"
        assert review[8] == "是"
        assert missing[4] == "【未找到】"
        assert missing[5] == "未找到 (NOT_FOUND)"
    finally:
        workbook.close()


def test_review_workbook_exports_every_candidate_and_only_exceptions(tmp_path) -> None:
    output = tmp_path / "review.xlsx"
    build_review_workbook(make_project_facts(), output)
    workbook = load_workbook(output, read_only=True, data_only=False)
    try:
        evidence = workbook["字段证据"]
        project_name_rows = [
            row for row in evidence.iter_rows(min_row=2, values_only=True)
            if row[0] == "project_name"
        ]
        assert len(project_name_rows) == 3
        assert all(row[11] for row in project_name_rows)

        exceptions = workbook["解析异常"]
        exception_codes = {row[0] for row in exceptions.iter_rows(min_row=2, values_only=True)}
        assert exception_codes == {
            "project_location",
            "lot_name",
            "lot_number",
            "tender_agency",
            "procurement_scope",
            "duration",
            "quality_target",
            "bid_deadline",
            "bid_open_time",
            "bid_open_location",
            "bid_bond_amount",
            "bid_bond_form",
            "consortium_allowed",
            "procurement_method",
        }
        assert all(
            "NEEDS_REVIEW" in row[2] or "NOT_FOUND" in row[2]
            for row in exceptions.iter_rows(min_row=2, values_only=True)
        )
    finally:
        workbook.close()


def test_review_builder_requires_project_facts_ssot(tmp_path) -> None:
    with pytest.raises(TypeError):
        build_review_workbook(tmp_path / "not-project-facts.json", tmp_path / "review.xlsx")
