from __future__ import annotations

import json
from decimal import Decimal

from tender_basic.document_models import DocumentStatus, NormalizedDocument
from tender_basic.fact_extractor import extract_candidates
from tender_basic.fact_normalizer import normalize_candidates
from tender_basic.fact_resolver import build_review_packet, resolve_project_facts
from tender_basic.models import FactStatus, FieldName, SourceType
from scripts.extract_facts import main as extract_facts_main

from test_fact_extraction import _document, _paragraph, _table


def _resolve(document: NormalizedDocument):
    return resolve_project_facts(
        document,
        normalize_candidates(extract_candidates(document)),
    )


def test_no_candidate_is_not_found_and_summary_counts_all_current_fields() -> None:
    facts = _resolve(_document(_paragraph(0, "只有无关内容")))

    assert facts.fields.bid_bond_amount.status == FactStatus.NOT_FOUND
    assert facts.fields.bid_bond_amount.resolved_value is None
    assert facts.summary.total_fields == 23
    assert facts.summary.resolved == 0
    assert facts.summary.needs_review == 0
    assert facts.summary.not_found == 23


def test_conflicting_values_require_review() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "项目名称：测试工程A"),
            _paragraph(1, "项目名称：测试工程B"),
        )
    )
    fact = facts.fields.project_name

    assert fact.status == FactStatus.NEEDS_REVIEW
    assert fact.resolved_value is None
    assert len(fact.candidates) == 2


def test_standalone_keyword_window_requires_review() -> None:
    facts = _resolve(
        _document(_paragraph(0, "本项目项目名称为“测试智慧平台项目”。"))
    )

    fact = facts.fields.project_name
    assert fact.status == FactStatus.NEEDS_REVIEW
    assert fact.resolved_value is None
    assert fact.candidates[0].method == "keyword_window"


def test_keyword_window_agrees_with_independent_explicit_candidate() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "本项目项目名称为“测试智慧平台项目”。"),
            _paragraph(1, "项目名称：测试智慧平台项目"),
        )
    )

    fact = facts.fields.project_name
    assert fact.status == FactStatus.RESOLVED
    assert fact.resolved_value == "测试智慧平台项目"
    assert {candidate.method for candidate in fact.candidates} == {
        "keyword_window",
        "label_value_same_line",
    }


def test_table_label_followed_by_another_label_is_not_used_as_value() -> None:
    facts = _resolve(
        _document(_table(0, [["项目名称", "项目编号", "PRJ-001"]]))
    )

    assert facts.fields.project_name.status == FactStatus.NOT_FOUND
    assert facts.fields.project_number.resolved_value == "PRJ-001"


def test_next_line_new_field_value_is_not_project_name() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "项目名称"),
            _paragraph(1, "项目编号：PRJ-001"),
        )
    )

    assert facts.fields.project_name.status == FactStatus.NOT_FOUND
    assert facts.fields.project_number.resolved_value == "PRJ-001"


def test_source_priority_does_not_hide_conflict() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "投标人须知前附表", "标题 1"),
            _paragraph(1, "项目名称：高优先级值"),
            _paragraph(2, "封面", "标题 1"),
            _paragraph(3, "项目名称：低优先级值"),
        )
    )

    assert facts.fields.project_name.status == FactStatus.NEEDS_REVIEW
    assert len(facts.fields.project_name.candidates) == 2


def test_equivalent_money_candidates_resolve_without_float() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "最高限价：100万元"),
            _paragraph(1, "最高限价：1,000,000元"),
        )
    )
    fact = facts.fields.max_price

    assert fact.status == FactStatus.RESOLVED
    assert {candidate.normalized_value for candidate in fact.candidates} == {"1000000"}
    assert isinstance(fact.candidates[0].normalized_value, str)
    assert not isinstance(fact.candidates[0].normalized_value, Decimal)


def test_conflicting_money_candidates_require_review() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "最高限价：100万元"),
            _paragraph(1, "最高限价：120万元"),
        )
    )

    assert facts.fields.max_price.status == FactStatus.NEEDS_REVIEW


def test_equivalent_dates_resolve() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "投标截止时间：2026年9月10日"),
            _paragraph(1, "投标截止时间：2026-09-10"),
        )
    )
    fact = facts.fields.bid_deadline

    assert fact.status == FactStatus.RESOLVED
    assert {candidate.normalized_value for candidate in fact.candidates} == {"2026-09-10"}


def test_duration_different_units_are_not_equated() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "工期：180天"),
            _paragraph(1, "工期：6个月"),
        )
    )

    assert facts.fields.duration.status == FactStatus.NEEDS_REVIEW


def test_budget_and_max_price_are_not_cross_filled() -> None:
    facts = _resolve(_document(_paragraph(0, "最高限价：100万元")))

    assert facts.fields.max_price.status == FactStatus.RESOLVED
    assert facts.fields.budget.status == FactStatus.NOT_FOUND


def test_review_packet_contains_only_conflict_evidence() -> None:
    facts = _resolve(
        _document(
            _paragraph(0, "项目名称：甲"),
            _paragraph(1, "项目名称：乙"),
            _paragraph(2, "项目编号：PRJ-001"),
        )
    )
    packet = build_review_packet(facts)

    assert [item["field"] for item in packet["review_fields"]] == ["project_name"]
    assert len(packet["review_fields"][0]["candidates"]) == 2
    assert all(item["evidence_text"] for item in packet["review_fields"][0]["candidates"])


def test_project_facts_can_be_serialized_and_revalidated() -> None:
    from tender_basic.models import ProjectFacts

    facts = _resolve(_document(_paragraph(0, "项目编号：A123")))
    round_trip = ProjectFacts.model_validate(facts.model_dump(mode="json"))

    assert round_trip.fields.project_number.resolved_value == "A123"
    assert round_trip.summary.total_fields == 23


def test_cli_writes_project_facts_and_review_packet(tmp_path) -> None:
    input_path = tmp_path / "normalized_document.json"
    output_dir = tmp_path / "facts"
    input_path.write_text(
        json.dumps(
            _document(_paragraph(0, "项目名称：CLI项目")).model_dump(mode="json"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert extract_facts_main([str(input_path), "--output", str(output_dir)]) == 0
    assert (output_dir / "project_facts.json").is_file()
    assert (output_dir / "facts_review_packet.json").is_file()


def test_cli_rejects_ocr_required_without_creating_facts(tmp_path) -> None:
    input_path = tmp_path / "scan.json"
    output_dir = tmp_path / "facts"
    scan_document = NormalizedDocument(
        source_file="scan.pdf",
        source_type=SourceType.PDF,
        status=DocumentStatus.OCR_REQUIRED,
        page_count=2,
        text_length=0,
    )
    input_path.write_text(
        json.dumps(scan_document.model_dump(mode="json")),
        encoding="utf-8",
    )

    assert extract_facts_main([str(input_path), "--output", str(output_dir)]) == 4
    assert not output_dir.exists()
