from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

from scripts.qa_delivery import main as qa_delivery_main
from tender_basic.bid_document_builder import build_bid_document
from tender_basic.delivery_qa import run_delivery_qa
from tender_basic.models import (
    CandidateFact,
    DocxParagraphLocator,
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


FIELD_VALUES = {
    "project_name": "测试工程",
    "project_number": "PRJ-123",
    "tender_number": "BID-456",
    "lot_name": "一标段",
    "lot_number": "LOT-001",
    "purchaser": "采购人甲",
    "tender_agency": "代理机构乙",
    "project_location": "上海市",
    "procurement_scope": "平台建设",
    "budget": "80万元",
    "max_price": "100万元",
    "duration": "180天",
    "quality_target": "合格",
    "bid_deadline": "2026-09-10 09:30",
    "bid_open_time": "2026-09-10 09:30",
    "bid_open_location": "线上开标",
    "bid_bond_amount": "10万元",
    "bid_bond_form": "银行保函",
    "consortium_allowed": False,
    "procurement_method": "公开招标",
}


def _candidate(value: object, index: int, *, method: str = "label_value_same_line") -> CandidateFact:
    return CandidateFact(
        value=value,
        normalized_value=value,
        confidence=0.95 if method != "keyword_window" else 0.70,
        method=method,
        source_file="qa-sample.docx",
        source_type=SourceType.DOCX,
        locator=DocxParagraphLocator(paragraph_index=index),
        section="招标公告",
        evidence_text=f"字段证据：{value}",
    )


def make_facts(
    *,
    review: tuple[str, ...] = (),
    not_found: tuple[str, ...] = (),
) -> ProjectFacts:
    review_set = set(review)
    not_found_set = set(not_found)
    values: dict[str, ResolvedFact] = {}
    for index, field in enumerate(FieldName):
        value = FIELD_VALUES[field.value]
        if field.value in not_found_set:
            values[field.value] = ResolvedFact(
                field=field,
                resolved_value=None,
                status=FactStatus.NOT_FOUND,
                confidence=0.0,
                candidates=[],
                resolution_reason="No trusted candidate was found.",
            )
        elif field.value in review_set:
            values[field.value] = ResolvedFact(
                field=field,
                resolved_value=None,
                status=FactStatus.NEEDS_REVIEW,
                confidence=0.70,
                candidates=[
                    _candidate(f"{value}候选A", index * 2),
                    _candidate(f"{value}候选B", index * 2 + 1),
                ],
                resolution_reason="Conflicting candidates require review.",
            )
        else:
            values[field.value] = ResolvedFact(
                field=field,
                resolved_value=value,
                status=FactStatus.RESOLVED,
                confidence=0.95,
                candidates=[_candidate(value, index)],
                resolution_reason="One deterministic candidate.",
            )
    return ProjectFacts.from_fields(
        source_document=SourceDocument(
            source_file="qa-sample.docx",
            source_type=SourceType.DOCX,
        ),
        fields=ProjectFields(**values),
    )


def _write_artifacts(tmp_path: Path, facts: ProjectFacts) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    facts_path = tmp_path / "project_facts.json"
    xlsx_path = tmp_path / "投标项目复核表.xlsx"
    docx_path = tmp_path / "基础投标文件.docx"
    facts_path.write_text(
        facts.model_dump_json(indent=2),
        encoding="utf-8",
    )
    build_review_workbook(facts, xlsx_path)
    build_bid_document(facts, docx_path)
    return facts_path, xlsx_path, docx_path


def _qa(tmp_path: Path, facts: ProjectFacts) -> dict:
    return run_delivery_qa(*_write_artifacts(tmp_path, facts))


def _xlsx_row(path: Path, field: str) -> int:
    workbook = load_workbook(path)
    try:
        worksheet = workbook["项目复核表"]
        for row_number in range(2, worksheet.max_row + 1):
            if worksheet.cell(row_number, 3).value == field:
                return row_number
    finally:
        workbook.close()
    raise AssertionError(f"XLSX field row not found: {field}")


def _docx_info_table(document: Document):
    labels = {spec.label for spec in load_output_fields()}
    best = None
    best_count = -1
    for table in document.tables:
        count = sum(
            1
            for row in table.rows
            if len(row.cells) >= 2 and row.cells[0].text.strip() in labels
        )
        if count > best_count:
            best = table
            best_count = count
    assert best is not None
    return best


def _set_docx_info_value(path: Path, label: str, value: str) -> None:
    document = Document(path)
    table = _docx_info_table(document)
    for row in table.rows:
        if row.cells[0].text.strip() == label:
            row.cells[1].text = value
            document.save(path)
            return
    raise AssertionError(f"DOCX field row not found: {label}")


def test_complete_consistent_output_is_pass(tmp_path: Path) -> None:
    report = _qa(tmp_path, make_facts())

    assert report["overall_status"] == "PASS"
    assert report["errors"] == []
    assert report["summary"]["candidate_count"] == 20


def test_review_and_not_found_are_pass_with_review(tmp_path: Path) -> None:
    review_report = _qa(tmp_path / "review", make_facts(review=("project_name",)))
    missing_report = _qa(tmp_path / "missing", make_facts(not_found=("bid_bond_amount",)))

    assert review_report["overall_status"] == "PASS_WITH_REVIEW"
    assert missing_report["overall_status"] == "PASS_WITH_REVIEW"
    assert review_report["errors"] == []
    assert missing_report["errors"] == []


def test_xlsx_missing_sheet_is_fail(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    workbook = load_workbook(xlsx_path)
    workbook.remove(workbook["解析异常"])
    workbook.save(xlsx_path)

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "xlsx_sheet_structure" for check in report["errors"])


def test_corrupt_docx_is_fail(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    docx_path.write_bytes(b"not a valid docx")

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "docx_reopen" for check in report["errors"])


def test_invalid_project_facts_contract_is_fail(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    facts_path.write_text("{\"fields\": {}}", encoding="utf-8")

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "project_facts_contract" for check in report["errors"])


def test_resolved_xlsx_value_corruption_is_fail(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    workbook = load_workbook(xlsx_path)
    worksheet = workbook["项目复核表"]
    worksheet.cell(_xlsx_row(xlsx_path, "project_name"), 5).value = "篡改后的值"
    workbook.save(xlsx_path)

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "xlsx_field_project_name" for check in report["errors"])


def test_resolved_docx_value_corruption_is_fail(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    _set_docx_info_value(docx_path, "项目名称", "篡改后的值")

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "docx_field_project_name" for check in report["errors"])


def test_empty_resolved_xlsx_value_is_fail(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    workbook = load_workbook(xlsx_path)
    worksheet = workbook["项目复核表"]
    worksheet.cell(_xlsx_row(xlsx_path, "project_name"), 5).value = None
    workbook.save(xlsx_path)

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "xlsx_field_project_name" for check in report["errors"])


def test_empty_resolved_docx_value_is_fail(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    _set_docx_info_value(docx_path, "项目名称", "")

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "docx_field_project_name" for check in report["errors"])


def test_number_fields_cannot_be_exchanged(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    workbook = load_workbook(xlsx_path)
    worksheet = workbook["项目复核表"]
    project_row = _xlsx_row(xlsx_path, "project_number")
    tender_row = _xlsx_row(xlsx_path, "tender_number")
    project_value = worksheet.cell(project_row, 5).value
    worksheet.cell(project_row, 5).value = worksheet.cell(tender_row, 5).value
    worksheet.cell(tender_row, 5).value = project_value
    workbook.save(xlsx_path)
    _set_docx_info_value(docx_path, "项目编号", "BID-456")
    _set_docx_info_value(docx_path, "招标编号", "PRJ-123")

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any("project_number" in check["id"] for check in report["errors"])


def test_budget_fields_cannot_be_exchanged(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    workbook = load_workbook(xlsx_path)
    worksheet = workbook["项目复核表"]
    budget_row = _xlsx_row(xlsx_path, "budget")
    max_price_row = _xlsx_row(xlsx_path, "max_price")
    budget_value = worksheet.cell(budget_row, 5).value
    worksheet.cell(budget_row, 5).value = worksheet.cell(max_price_row, 5).value
    worksheet.cell(max_price_row, 5).value = budget_value
    workbook.save(xlsx_path)
    _set_docx_info_value(docx_path, "预算金额", "100万元")
    _set_docx_info_value(docx_path, "最高限价", "80万元")

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any("budget" in check["id"] for check in report["errors"])


def test_candidate_evidence_missing_row_is_fail(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    workbook = load_workbook(xlsx_path)
    workbook["字段证据"].delete_rows(2, 1)
    workbook.save(xlsx_path)

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "xlsx_candidate_evidence_completeness" for check in report["errors"])


def test_exception_sheet_missing_row_is_fail(tmp_path: Path) -> None:
    facts = make_facts(review=("project_name",), not_found=("bid_bond_amount",))
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, facts)
    workbook = load_workbook(xlsx_path)
    workbook["解析异常"].delete_rows(2, 1)
    workbook.save(xlsx_path)

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "xlsx_exception_completeness" for check in report["errors"])


def test_needs_review_candidate_cannot_be_written_as_final_value(tmp_path: Path) -> None:
    facts = make_facts(review=("project_name",))
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, facts)
    workbook = load_workbook(xlsx_path)
    worksheet = workbook["项目复核表"]
    worksheet.cell(_xlsx_row(xlsx_path, "project_name"), 5).value = "测试工程候选A"
    workbook.save(xlsx_path)

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "xlsx_field_project_name" for check in report["errors"])


def test_not_found_cannot_be_filled_with_another_field_value(tmp_path: Path) -> None:
    facts = make_facts(not_found=("bid_bond_amount",))
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, facts)
    _set_docx_info_value(docx_path, "投标保证金金额", "80万元")

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "docx_field_bid_bond_amount" for check in report["errors"])


def test_fabricated_bidder_and_submission_ready_status_are_failures(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(tmp_path, make_facts())
    document = Document(docx_path)
    document.tables[0].rows[-2].cells[1].text = "虚构公司"
    document.add_paragraph("READY_FOR_SUBMISSION")
    document.save(docx_path)

    report = run_delivery_qa(facts_path, xlsx_path, docx_path)

    assert report["overall_status"] == "FAIL"
    assert any(check["id"] == "docx_bidder_placeholder" for check in report["errors"])
    assert any(check["id"] == "no_submission_ready_status" for check in report["errors"])


def test_qa_cli_writes_structured_report(tmp_path: Path) -> None:
    facts_path, xlsx_path, docx_path = _write_artifacts(
        tmp_path, make_facts(review=("project_name",))
    )
    report_path = tmp_path / "qa_report.json"

    code = qa_delivery_main(
        [
            "--facts",
            str(facts_path),
            "--xlsx",
            str(xlsx_path),
            "--docx",
            str(docx_path),
            "--output",
            str(report_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 0
    assert report["overall_status"] == "PASS_WITH_REVIEW"
    assert isinstance(report["checks"], list)
    assert isinstance(report["errors"], list)
    assert isinstance(report["warnings"], list)
