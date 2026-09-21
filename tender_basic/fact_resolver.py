"""Deterministic, conflict-preserving resolution for V1 ProjectFacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from .document_models import NormalizedDocument
from .fact_extractor import load_field_aliases
from .fact_normalizer import (
    COMPACT_TEXT_FIELDS,
    DATE_FIELDS,
    MONEY_FIELDS,
    TIME_SPAN_FIELDS,
    is_value_type_valid,
    normalize_candidates,
    normalize_date_time,
)
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
    "labeled_multiline_value": 0.85,
    "standalone_title_candidate": 0.65,
    "platform_phrase": 0.75,
    "lot_value_context": 0.92,
    "lot_section_heading": 0.88,
    "lot_cover_title": 0.72,
    # WorkBuddy proposals are still only candidates, but they have already
    # passed the locator/evidence/value-type boundary in semantic_candidates.
    "semantic_evidence_review": 0.80,
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


def _explicit_keyword_candidate(field: FieldName, candidate: CandidateFact) -> bool:
    """Allow only two narrow keyword shapes with an unambiguous contract."""

    evidence = re.sub(r"\s+", "", candidate.evidence_text)
    value = re.sub(r"\s+", "", str(candidate.value))
    if field == FieldName.CONSORTIUM_ALLOWED:
        return (
            "联合体" in evidence
            and any(token in evidence for token in ("不接受联合体", "不允许联合体", "接受联合体"))
            and candidate.normalized_value in {True, False}
        )
    if field == FieldName.PROCUREMENT_METHOD:
        allowed = {
            "公开招标",
            "邀请招标",
            "竞争性谈判",
            "竞争性磋商",
            "询价",
            "询比",
            "单一来源",
        }
        return (
            any(token in evidence for token in ("招标方式", "采购方式"))
            and value in allowed
        )
    return False


def _compact_for_prefix(value: object) -> str:
    return re.sub(r"[\s，,。；;：:、.!！？!?（）()（）]", "", str(value))


def _drop_truncated_candidates(candidates: list[CandidateFact]) -> list[CandidateFact]:
    """Drop only obvious PDF truncation fragments, preserving real conflicts."""

    result: list[CandidateFact] = []
    for candidate in candidates:
        candidate_text = _compact_for_prefix(candidate.normalized_value or candidate.value)
        truncated = False
        if len(candidate_text) >= 4:
            for other in candidates:
                if other is candidate:
                    continue
                other_text = _compact_for_prefix(other.normalized_value or other.value)
                if (
                    len(other_text) > len(candidate_text) + 2
                    and other_text.startswith(candidate_text)
                    and other.confidence >= candidate.confidence
                ):
                    truncated = True
                    break
                # A PDF block can end in a longer but unfinished suffix while
                # the table/complete block contains the same value.  Only
                # remove that shape when the complete value is stronger and
                # the extra suffix is short enough to be layout residue.
                if (
                    len(candidate_text) > len(other_text) + 2
                    and candidate_text.startswith(other_text)
                    and candidate.confidence < other.confidence
                    and len(candidate_text) - len(other_text) <= 32
                    and not str(candidate.value).rstrip().endswith(("。", ";", "；", ")", "）"))
                ):
                    truncated = True
                    break
                if (
                    len(candidate_text) > len(other_text)
                    and candidate_text.startswith(other_text)
                    and candidate.confidence <= other.confidence
                    and len(candidate_text) - len(other_text) <= 3
                    and isinstance(candidate.value, str)
                    and re.search(r"\s+[^\s]{1,3}$", candidate.value)
                    and getattr(candidate.locator, "locator_type", "") == "pdf_table_cell"
                ):
                    truncated = True
                    break
                # A split table cell may expose only the tail of a longer
                # value (for example the last few characters of a project
                # title).  It is not an independent conflicting fact.
                if (
                    len(candidate_text) >= 4
                    and len(candidate_text) * 2 <= len(other_text)
                    and candidate_text in other_text
                    and candidate.confidence < other.confidence
                ):
                    truncated = True
                    break
                # A block that begins mid-word is the tail of a value the
                # extractor also captured whole.  Being a strict suffix of a
                # stronger candidate is evidence of truncation even when the
                # fragment is short, which the length-ratio rule above misses.
                if (
                    len(candidate_text) >= 2
                    and len(other_text) > len(candidate_text)
                    and other_text.endswith(candidate_text)
                    and candidate.confidence <= other.confidence
                ):
                    truncated = True
                    break
        if not truncated:
            result.append(candidate)
    return result


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

    usable = _drop_truncated_candidates(usable)
    valid_candidates = [
        candidate
        for candidate in usable
        if is_value_type_valid(field_enum, candidate.value)
    ]
    if not valid_candidates:
        return _review_for_fallback_gate(
            field_enum,
            usable,
            "Candidate evidence exists but no candidate passed the field value-type validator.",
        )

    groups: dict[str, list[CandidateFact]] = {}
    for candidate in valid_candidates:
        groups.setdefault(_normalized_key(candidate.normalized_value), []).append(candidate)

    if len(groups) > 1:
        return ResolvedFact(
            field=field_enum,
            resolved_value=None,
            status=FactStatus.NEEDS_REVIEW,
            confidence=min(candidate.confidence for candidate in valid_candidates),
            candidates=usable,
            resolution_reason="Conflicting candidate values remain after normalization.",
        )

    keyword_candidates = [
        candidate for candidate in valid_candidates if candidate.method == "keyword_window"
    ]
    if keyword_candidates:
        supporting_candidates = [
            candidate
            for candidate in valid_candidates
            if candidate.method != "keyword_window"
            and _passes_single_candidate_gate(candidate, aliases)
        ]
        has_independent_support = any(
            all(_locator_key(candidate) != _locator_key(keyword) for keyword in keyword_candidates)
            for candidate in supporting_candidates
        )
        keyword_is_explicit = all(
            _explicit_keyword_candidate(field_enum, candidate)
            for candidate in keyword_candidates
        )
        if not has_independent_support and not keyword_is_explicit:
            return _review_for_fallback_gate(
                field_enum,
                usable,
                "Standalone keyword_window evidence requires review; no independent high-quality candidate agrees.",
            )

    if len(valid_candidates) == 1 and not _passes_single_candidate_gate(
        valid_candidates[0], aliases
    ) and not _explicit_keyword_candidate(field_enum, valid_candidates[0]):
        if valid_candidates[0].method == "keyword_window":
            reason = "Standalone keyword_window evidence requires review."
        elif valid_candidates[0].method == "label_value_next_line":
            reason = "Single next-line candidate did not pass the deterministic quality gate."
        else:
            reason = "Single candidate did not pass the deterministic quality gate."
        return _review_for_fallback_gate(field_enum, usable, reason)

    chosen = max(valid_candidates, key=lambda item: _candidate_sort_key(item, source_priority))
    confidence = _confidence_for(chosen, source_priority, len(valid_candidates))
    if len(valid_candidates) == 1:
        reason = "Single credible candidate after deterministic validation."
    else:
        reason = "Multiple candidates agree after normalization."
    resolved_value = chosen.value
    if field_name in MONEY_FIELDS | DATE_FIELDS | TIME_SPAN_FIELDS | COMPACT_TEXT_FIELDS:
        resolved_value = chosen.normalized_value
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


_CROSS_REFERENCE_OPEN_TIME_RE = re.compile(
    r"^同(?:投标|提交响应文件|响应文件递交|响应文件提交).{0,8}截止(?:时间)?$"
)


def _derive_open_time_from_deadline(
    open_time_fact: ResolvedFact,
    deadline_fact: ResolvedFact,
) -> ResolvedFact:
    """Resolve an explicit same-deadline phrase only from a concrete deadline."""

    if deadline_fact.status != FactStatus.RESOLVED:
        return open_time_fact
    deadline_value = normalize_date_time(deadline_fact.resolved_value)
    if deadline_value is None:
        return open_time_fact
    references = [
        candidate
        for candidate in open_time_fact.candidates
        if _CROSS_REFERENCE_OPEN_TIME_RE.fullmatch(
            re.sub(r"\s+", "", str(candidate.value))
        )
    ]
    if not references:
        return open_time_fact
    reference = references[0]
    derived_candidate = reference.model_copy(
        update={
            "value": deadline_value,
            "normalized_value": deadline_value,
            "method": "derived_cross_reference",
            "confidence": min(reference.confidence, deadline_fact.confidence),
            "evidence_text": (
                f"{reference.evidence_text.strip()}；交叉引用投标截止时间："
                f"{deadline_value}；来源证据："
                f"{deadline_fact.candidates[0].evidence_text.strip()}"
            ),
        }
    )
    return ResolvedFact(
        field=FieldName.BID_OPEN_TIME,
        resolved_value=deadline_value,
        status=FactStatus.RESOLVED,
        confidence=derived_candidate.confidence,
        candidates=[*open_time_fact.candidates, derived_candidate],
        resolution_reason="Resolved by deterministic cross-reference to bid_deadline.",
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
    resolved[FieldName.BID_OPEN_TIME.value] = _derive_open_time_from_deadline(
        resolved[FieldName.BID_OPEN_TIME.value],
        resolved[FieldName.BID_DEADLINE.value],
    )
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
