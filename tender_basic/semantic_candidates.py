"""Evidence-bound semantic candidate augmentation.

WorkBuddy may propose a value after reviewing a gap packet, but this module is
the only Python boundary that can turn that proposal back into a candidate.
The proposal is never treated as a final fact and is rejected when its source
locator or evidence cannot be verified against the normalized document.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .document_models import (
    NormalizedDocument,
    ParagraphElement,
    PdfBlockElement,
    PdfTableElement,
    TableElement,
)
from .fact_normalizer import normalize_field_value, normalize_text_value, is_value_type_valid
from .fact_resolver import resolve_project_facts
from .models import (
    CandidateFact,
    DocxParagraphLocator,
    DocxTableLocator,
    FactStatus,
    FieldName,
    PdfLocator,
    PdfTableLocator,
    ProjectFacts,
    SemanticCandidateProposal,
    SourceType,
)


def build_fact_gap_packet(project_facts: ProjectFacts) -> dict[str, Any]:
    """Build the P0 review input for unresolved fields only."""

    gaps: list[dict[str, Any]] = []
    for field in FieldName:
        fact = getattr(project_facts.fields, field.value)
        if fact.status not in {FactStatus.NEEDS_REVIEW, FactStatus.NOT_FOUND}:
            continue
        gaps.append(
            {
                "priority": "P0",
                "field": field.value,
                "status": fact.status.value,
                "resolution_reason": fact.resolution_reason,
                "candidates": [
                    {
                        "candidate_index": index,
                        **candidate.model_dump(mode="json"),
                    }
                    for index, candidate in enumerate(fact.candidates)
                ],
            }
        )
    return {
        "schema_version": project_facts.schema_version,
        "source_document": project_facts.source_document.model_dump(mode="json"),
        "allowed_fields": [field.value for field in FieldName],
        "gaps": gaps,
        "instructions": (
            "Return SemanticCandidateProposal objects only. Do not create a fact "
            "without an exact normalized-document locator and matching evidence_text."
        ),
    }


def _compact(value: object) -> str:
    return re.sub(r"\s+", "", normalize_text_value(value))


def _source_text_for_locator(
    document: NormalizedDocument,
    locator: object,
) -> str | None:
    if isinstance(locator, PdfLocator):
        for page in document.pages:
            if page.page_number != locator.page:
                continue
            if locator.block_index is None:
                return "\n".join(block.text for block in page.blocks)
            for block in page.blocks:
                if block.block_index == locator.block_index:
                    return block.text
        return None
    if isinstance(locator, PdfTableLocator):
        for table in document.tables:
            if table.page != locator.page or table.table_index != locator.table_index:
                continue
            for row in table.rows:
                if row.row_index != locator.row_index:
                    continue
                for cell in row.cells:
                    if cell.column_index == locator.column_index:
                        return cell.text
        return None
    if isinstance(locator, DocxParagraphLocator):
        for element in document.elements:
            if isinstance(element, ParagraphElement):
                if element.paragraph.paragraph_index == locator.paragraph_index:
                    return element.paragraph.text
        return None
    if isinstance(locator, DocxTableLocator):
        for element in document.elements:
            if isinstance(element, TableElement):
                table = element.table
                if table.table_index != locator.table_index:
                    continue
                for row in table.rows:
                    if row.row_index != locator.row_index:
                        continue
                    for cell in row.cells:
                        if cell.cell_index == locator.cell_index:
                            return cell.text
        return None
    return None


def _evidence_matches(source_text: str, evidence_text: str) -> bool:
    source = _compact(source_text)
    evidence = _compact(evidence_text)
    # Evidence may be a faithful excerpt of the located source item, but it
    # may not contain extra model-authored text around that item.
    return bool(evidence and evidence in source)


def _value_is_supported_by_evidence(
    field: FieldName,
    value: object,
    evidence_text: str,
) -> bool:
    value_compact = _compact(value)
    evidence_compact = _compact(evidence_text)
    if value_compact and value_compact in evidence_compact:
        return True
    normalized_value = normalize_field_value(field.value, value)
    normalized_evidence = normalize_field_value(field.value, evidence_text)
    if normalized_value is None:
        return False
    return normalized_evidence == normalized_value


def validate_semantic_candidate_proposal(
    proposal: SemanticCandidateProposal | dict[str, Any],
    document: NormalizedDocument,
) -> tuple[CandidateFact | None, str | None]:
    """Validate one proposal and convert it into a source-backed candidate."""

    try:
        parsed = (
            proposal
            if isinstance(proposal, SemanticCandidateProposal)
            else SemanticCandidateProposal.model_validate(proposal)
        )
    except Exception as exc:
        return None, f"proposal_contract_invalid:{exc.__class__.__name__}"

    if document.source_type is None or document.status.value != "PARSED":
        return None, "document_not_available_for_semantic_validation"
    source_text = _source_text_for_locator(document, parsed.source_locator)
    if source_text is None:
        return None, "source_locator_not_found"
    if not _evidence_matches(source_text, parsed.evidence_text):
        return None, "evidence_text_does_not_match_locator"
    if not _value_is_supported_by_evidence(parsed.field, parsed.value, parsed.evidence_text):
        return None, "value_not_directly_supported_by_evidence"
    if not is_value_type_valid(parsed.field, parsed.value):
        return None, "value_type_validation_failed"

    return (
        CandidateFact(
            value=parsed.value,
            normalized_value=normalize_field_value(parsed.field.value, parsed.value),
            confidence=0.80,
            method="semantic_evidence_review",
            source_file=document.source_file,
            source_type=document.source_type,
            locator=parsed.source_locator,
            evidence_text=parsed.evidence_text.strip(),
            section=None,
        ),
        None,
    )


def apply_semantic_candidate_proposals(
    document: NormalizedDocument,
    baseline_facts: ProjectFacts,
    proposals: Iterable[SemanticCandidateProposal | dict[str, Any]],
    *,
    source_priority_path: str | None = None,
) -> tuple[ProjectFacts, dict[str, Any]]:
    """Accept validated proposals, then re-run the deterministic resolver."""

    candidates = {
        field.value: list(getattr(baseline_facts.fields, field.value).candidates)
        for field in FieldName
    }
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, proposal in enumerate(proposals):
        candidate, reason = validate_semantic_candidate_proposal(proposal, document)
        if candidate is None:
            rejected.append({"proposal_index": index, "reason": reason})
            continue
        field = (
            proposal.field.value
            if isinstance(proposal, SemanticCandidateProposal)
            else str(proposal.get("field"))
        )
        candidates[field].append(candidate)
        accepted.append(
            {
                "proposal_index": index,
                "field": field,
                "candidate": candidate.model_dump(mode="json"),
            }
        )

    reviewed = resolve_project_facts(
        document,
        candidates,
        source_priority_path=source_priority_path,
    )
    return reviewed, {
        "accepted": accepted,
        "rejected": rejected,
        "model_can_only_propose": True,
    }


__all__ = [
    "apply_semantic_candidate_proposals",
    "build_fact_gap_packet",
    "validate_semantic_candidate_proposal",
]
