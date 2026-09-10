"""Deterministic, conflict-preserving resolution for V1 ProjectFacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from .document_models import NormalizedDocument
from .fact_extractor import load_field_aliases
from .fact_normalizer import normalize_candidates
from .models import (
    CandidateFact,
    FactStatus,
    FieldName,
    ProjectFacts,
    ProjectFields,
    ResolvedFact,
    SourceDocument,
)


_DEFAULT_SOURCE_PRIORITY_PATH = (
    Path(__file__).resolve().parents[1] / "rules" / "source_priority.yaml"
)

# These are deterministic gates, not probability claims.  They match the
# fixed extraction baselines and prevent low-confidence fallback methods from
# becoming automatic facts merely because no other candidate exists.
_SINGLE_METHOD_MIN_CONFIDENCE = {
    "table_label_exact": 0.95,
    "label_value_same_line": 0.90,
    "label_value_next_line": 0.85,
}


def load_source_priority(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load source ranking entries from YAML without embedding their order."""

    priority_path = Path(path) if path is not None else _DEFAULT_SOURCE_PRIORITY_PATH
    with priority_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    entries = payload.get("priority_order", [])
    if not isinstance(entries, list):
        raise ValueError("source_priority.yaml priority_order must be a list")

    result: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or "rank" not in entry or "source_id" not in entry:
            raise ValueError("Each source priority entry needs rank and source_id")
        result.append(dict(entry))
    return result


def _label_parts(label: object) -> list[str]:
    return [part.strip() for part in str(label).split("/") if part.strip()]


def _entry_rank(entries: list[dict[str, Any]], source_id: str) -> int:
    for entry in entries:
        if entry.get("source_id") == source_id:
            try:
                return int(entry.get("rank", 0))
            except (TypeError, ValueError):
                return 0
    return 0


def _candidate_source_rank(candidate: CandidateFact, entries: list[dict[str, Any]]) -> int:
    section = candidate.section or ""
    source_file = candidate.source_file
    matched_rank: int | None = None
    for entry in entries:
        for label in _label_parts(entry.get("label", "")):
            if label and label in section:
                rank = _entry_rank(entries, str(entry.get("source_id")))
                matched_rank = rank if matched_rank is None else max(matched_rank, rank)
            if label and label in source_file:
                rank = _entry_rank(entries, str(entry.get("source_id")))
                matched_rank = rank if matched_rank is None else max(matched_rank, rank)
    if matched_rank is not None:
        return matched_rank
    # A candidate with no explicit source heading is treated as an explicit
    # body field only for ordering.  It does not acquire authority over a
    # conflicting candidate; conflicts are handled before ranking below.
    return _entry_rank(entries, "explicit_body_field")


def _candidate_sort_key(candidate: CandidateFact, entries: list[dict[str, Any]]) -> tuple[int, float]:
    return (_candidate_source_rank(candidate, entries), candidate.confidence)


def _usable_candidates(candidates: list[CandidateFact]) -> list[CandidateFact]:
    return [
        candidate
        for candidate in candidates
        if candidate.value is not None
        and str(candidate.value).strip()
        and candidate.evidence_text.strip()
    ]


def _normalized_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _locator_key(candidate: CandidateFact) -> str:
    return json.dumps(
        candidate.locator.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )


def _value_looks_like_field_label(
    value: object,
    field_aliases: Mapping[str, list[str]],
) -> bool:
    """Reject a next-line value that is actually another field label/value."""

    normalized = str(value).strip()
    for aliases in field_aliases.values():
        for alias in aliases:
            if normalized == alias:
                return True
            if re.match(re.escape(alias) + r"\s*[：:]", normalized):
                return True
    return False


def _passes_single_candidate_gate(
    candidate: CandidateFact,
    field_aliases: Mapping[str, list[str]],
) -> bool:
    """Return whether one candidate is strong enough to auto-resolve."""

    if candidate.method == "keyword_window":
        return False
    minimum = _SINGLE_METHOD_MIN_CONFIDENCE.get(candidate.method)
    if minimum is None or candidate.confidence < minimum:
        return False
    if candidate.method == "label_value_next_line" and _value_looks_like_field_label(
        candidate.value,
        field_aliases,
    ):
        return False
    return True


def _review_for_fallback_gate(
    field: FieldName,
    candidates: list[CandidateFact],
    reason: str,
) -> ResolvedFact:
    return ResolvedFact(
        field=field,
        resolved_value=None,
        status=FactStatus.NEEDS_REVIEW,
        confidence=min(candidate.confidence for candidate in candidates),
        candidates=candidates,
        resolution_reason=reason,
    )


def _confidence_for(
    candidate: CandidateFact,
    entries: list[dict[str, Any]],
    agreement_count: int,
) -> float:
    # Priority is a small ranking signal only.  It cannot remove a conflict.
    rank = _candidate_source_rank(candidate, entries)
    adjustment = min(0.02, max(0.0, rank) / 10000.0)
    agreement_bonus = min(0.03, max(0, agreement_count - 1) * 0.01)
    return min(1.0, max(0.0, candidate.confidence + adjustment + agreement_bonus))


def resolve_field(
    field: str | FieldName,
    candidates: list[CandidateFact],
    source_priority: list[dict[str, Any]],
    field_aliases: Mapping[str, list[str]] | None = None,
) -> ResolvedFact:
    """Resolve one field while preserving all evidence and exposing conflicts."""

    field_name = field.value if isinstance(field, FieldName) else str(field)
    field_enum = FieldName(field_name)
    aliases = field_aliases if field_aliases is not None else load_field_aliases()
    usable = _usable_candidates(candidates)
    if not usable:
        return ResolvedFact(
            field=field_enum,
            resolved_value=None,
            status=FactStatus.NOT_FOUND,
            confidence=0.0,
            candidates=[],
            resolution_reason="No credible candidate found.",
        )

    groups: dict[str, list[CandidateFact]] = {}
    for candidate in usable:
        groups.setdefault(_normalized_key(candidate.normalized_value), []).append(candidate)

    if len(groups) > 1:
        return ResolvedFact(
            field=field_enum,
            resolved_value=None,
            status=FactStatus.NEEDS_REVIEW,
            confidence=min(candidate.confidence for candidate in usable),
            candidates=usable,
            resolution_reason="Conflicting candidate values remain after normalization.",
        )

    keyword_candidates = [
        candidate for candidate in usable if candidate.method == "keyword_window"
    ]
    if keyword_candidates:
        supporting_candidates = [
            candidate
            for candidate in usable
            if candidate.method != "keyword_window"
            and _passes_single_candidate_gate(candidate, aliases)
        ]
        has_independent_support = any(
            all(_locator_key(candidate) != _locator_key(keyword) for keyword in keyword_candidates)
            for candidate in supporting_candidates
        )
        if not has_independent_support:
            return _review_for_fallback_gate(
                field_enum,
                usable,
                "Standalone keyword_window evidence requires review; no independent high-quality candidate agrees.",
            )

    if len(usable) == 1 and not _passes_single_candidate_gate(usable[0], aliases):
        if usable[0].method == "keyword_window":
            reason = "Standalone keyword_window evidence requires review."
        elif usable[0].method == "label_value_next_line":
            reason = "Single next-line candidate did not pass the deterministic quality gate."
        else:
            reason = "Single candidate did not pass the deterministic quality gate."
        return _review_for_fallback_gate(field_enum, usable, reason)

    chosen = max(usable, key=lambda item: _candidate_sort_key(item, source_priority))
    confidence = _confidence_for(chosen, source_priority, len(usable))
    if len(usable) == 1:
        reason = "Single credible candidate after deterministic validation."
    else:
        reason = "Multiple candidates agree after normalization."
    resolved_value = chosen.value
    if (
        field_enum == FieldName.CONSORTIUM_ALLOWED
        and isinstance(chosen.normalized_value, bool)
    ):
        # Keep the original phrase in CandidateFact.value/evidence while
        # exposing the deterministic boolean contract at field level.
        resolved_value = chosen.normalized_value
    return ResolvedFact(
        field=field_enum,
        resolved_value=resolved_value,
        status=FactStatus.RESOLVED,
        confidence=confidence,
        candidates=usable,
        resolution_reason=reason,
    )


def resolve_project_facts(
    document: NormalizedDocument,
    candidates_by_field: Mapping[str, list[CandidateFact]],
    source_priority_path: str | Path | None = None,
) -> ProjectFacts:
    """Resolve all and only the fixed V1 fields into the existing contract."""

    source_priority = load_source_priority(source_priority_path)
    field_aliases = load_field_aliases()
    # Normalize at the resolution boundary as well as in the CLI.  This keeps
    # direct library callers on the same deterministic path without changing
    # CandidateFact.value.
    normalized_input = normalize_candidates(candidates_by_field)

    resolved = {
        field.value: resolve_field(
            field,
            normalized_input[field.value],
            source_priority,
            field_aliases,
        )
        for field in FieldName
    }
    fields = ProjectFields(**resolved)
    return ProjectFacts.from_fields(
        source_document=SourceDocument(
            source_file=document.source_file,
            source_type=document.source_type,
        ),
        fields=fields,
        schema_version=document.schema_version,
    )


def build_review_packet(project_facts: ProjectFacts) -> dict[str, Any]:
    """Build the small conflict-only packet intended for later human review."""

    review_fields: list[dict[str, Any]] = []
    for field in FieldName:
        resolved = getattr(project_facts.fields, field.value)
        if resolved.status != FactStatus.NEEDS_REVIEW:
            continue
        review_fields.append(
            {
                "field": field.value,
                "status": resolved.status.value,
                "resolution_reason": resolved.resolution_reason,
                "candidates": [
                    {
                        "candidate_index": index,
                        **candidate.model_dump(mode="json"),
                    }
                    for index, candidate in enumerate(resolved.candidates)
                ],
            }
        )

    return {
        "schema_version": project_facts.schema_version,
        "source_document": project_facts.source_document.source_file,
        "review_fields": review_fields,
    }


__all__ = [
    "build_review_packet",
    "load_source_priority",
    "resolve_field",
    "resolve_project_facts",
]
