from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tender_basic.models import (
    CandidateFact,
    DocxParagraphLocator,
    DocxTableLocator,
    FactStatus,
    FieldName,
    PdfLocator,
    ProjectFacts,
    ProjectFields,
    ResolvedFact,
    SourceDocument,
    SourceType,
)


ROOT = Path(__file__).resolve().parents[1]


def make_candidate(
    *,
    source_type: SourceType = SourceType.PDF,
    locator=None,
    value: str = "示例值",
    confidence: float = 0.9,
) -> CandidateFact:
    if locator is None:
        locator = PdfLocator(page=3, block_index=12)
    return CandidateFact(
        value=value,
        normalized_value=value,
        confidence=confidence,
        method="table_label_exact",
        source_file="notice.pdf" if source_type == SourceType.PDF else "notice.docx",
        source_type=source_type,
        locator=locator,
        section="投标人须知前附表",
        evidence_text="示例字段：示例值",
    )


def make_resolved(field: FieldName, status: FactStatus = FactStatus.RESOLVED, value: str | None = None):
    if status == FactStatus.RESOLVED:
        actual_value = value or field.value
        return ResolvedFact(
            field=field,
            resolved_value=actual_value,
            status=status,
            confidence=0.9,
            candidates=[make_candidate(value=actual_value)],
            resolution_reason="单一证据候选，待后续规则复核",
        )
    if status == FactStatus.NEEDS_REVIEW:
        return ResolvedFact(
            field=field,
            resolved_value=None,
            status=status,
            confidence=0.4,
            candidates=[make_candidate(value="候选一"), make_candidate(value="候选二")],
            resolution_reason="存在多个候选值，需要人工复核",
        )
    return ResolvedFact(
        field=field,
        resolved_value=None,
        status=status,
        confidence=0.0,
        candidates=[],
        resolution_reason="没有找到可信候选",
    )


def make_fields(statuses: dict[str, FactStatus] | None = None) -> ProjectFields:
    statuses = statuses or {}
    return ProjectFields(
        **{
            field.value: make_resolved(field, statuses.get(field.value, FactStatus.RESOLVED))
            for field in FieldName
        }
    )


def make_project_facts(fields: ProjectFields) -> ProjectFacts:
    return ProjectFacts.from_fields(
        source_document=SourceDocument(source_file="notice.pdf", source_type=SourceType.PDF),
        fields=fields,
    )


def test_candidate_fact_can_be_created_and_serialized():
    candidate = make_candidate()

    payload = candidate.model_dump(mode="json")

    assert payload["value"] == "示例值"
    assert payload["normalized_value"] == "示例值"
    assert payload["locator"] == {
        "locator_type": "pdf_block",
        "page": 3,
        "block_index": 12,
    }
    assert json.loads(candidate.model_dump_json())["source_type"] == "PDF"


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_between_zero_and_one(confidence: float):
    with pytest.raises(ValidationError):
        make_candidate(confidence=confidence)


def test_resolved_fact_status_enum_accepts_only_three_v1_values():
    for status in FactStatus:
        fact = make_resolved(FieldName.PROJECT_NAME, status)
        assert fact.status is status

    with pytest.raises(ValidationError):
        ResolvedFact(
            field=FieldName.PROJECT_NAME,
            status="UNKNOWN",
            confidence=0.5,
            candidates=[],
            resolution_reason="invalid status",
        )


def test_project_number_and_tender_number_remain_independent():
    fields = make_fields()
    fields.project_number = make_resolved(
        FieldName.PROJECT_NUMBER, value="A123"
    )
    fields.tender_number = make_resolved(
        FieldName.TENDER_NUMBER, value="B456"
    )

    payload = make_project_facts(fields).model_dump(mode="json")

    assert payload["fields"]["project_number"]["resolved_value"] == "A123"
    assert payload["fields"]["tender_number"]["resolved_value"] == "B456"


def test_pdf_locator_preserves_real_page():
    candidate = make_candidate(locator=PdfLocator(page=3, block_index=12))

    assert candidate.locator.page == 3
    assert candidate.model_dump(mode="json")["locator"]["page"] == 3


def test_docx_paragraph_locator_has_no_page():
    candidate = make_candidate(
        source_type=SourceType.DOCX,
        locator=DocxParagraphLocator(paragraph_index=35),
    )

    payload = candidate.model_dump(mode="json")
    assert payload["locator"] == {
        "locator_type": "docx_paragraph",
        "paragraph_index": 35,
    }
    assert "page" not in payload["locator"]


def test_docx_table_locator_has_no_page():
    candidate = make_candidate(
        source_type=SourceType.DOCX,
        locator=DocxTableLocator(table_index=2, row_index=4, cell_index=1),
    )

    payload = candidate.model_dump(mode="json")
    assert payload["locator"] == {
        "locator_type": "docx_table_cell",
        "table_index": 2,
        "row_index": 4,
        "cell_index": 1,
    }
    assert "page" not in payload["locator"]


def test_project_facts_summary_counts_all_three_statuses():
    statuses = {
        "project_number": FactStatus.NEEDS_REVIEW,
        "tender_number": FactStatus.NOT_FOUND,
    }
    facts = make_project_facts(make_fields(statuses))

    assert facts.summary.total_fields == 23
    assert facts.summary.resolved == 21
    assert facts.summary.needs_review == 1
    assert facts.summary.not_found == 1


def test_generated_json_schema_can_be_loaded_and_describes_contract():
    schema = ProjectFacts.model_json_schema()
    schema_path = ROOT / "schemas" / "project_facts.schema.json"
    generated_schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert set(schema["properties"]["fields"]["$ref"].split("/")[-1:]) == {"ProjectFields"}
    assert generated_schema == schema
    assert len(schema["$defs"]["FieldName"]["enum"]) == 23
