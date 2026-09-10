"""Deterministic candidate discovery from a NormalizedDocument.

This module deliberately stops at candidate facts.  It does not decide which
candidate is the final value for a ProjectFacts field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from .document_models import (
    NormalizedDocument,
    ParagraphElement,
    PdfBlockElement,
    TableElement,
)
from .models import (
    CandidateFact,
    FieldName,
    Locator,
    SourceType,
)
from .fact_normalizer import normalize_text_value


BASE_CONFIDENCE: Mapping[str, float] = {
    "table_label_exact": 0.98,
    "label_value_same_line": 0.95,
    "label_value_next_line": 0.85,
    "keyword_window": 0.70,
}

_DEFAULT_ALIASES_PATH = Path(__file__).resolve().parents[1] / "rules" / "field_aliases.yaml"
_MAX_TABLE_VALUE_DISTANCE = 3
_TRAILING_LABEL_PUNCTUATION = " \t\r\n:："
_VALUE_EDGE_PUNCTUATION = " \t\r\n,，;；。.!！？!?"
_QUOTE_PAIRS = {
    ("“", "”"),
    ("\"", "\""),
    ("'", "'"),
    ("‘", "’"),
    ("「", "」"),
    ("『", "』"),
    ("（", "）"),
    ("(", ")"),
}


@dataclass(frozen=True)
class _TextRecord:
    """One ordered source item used by the four small extraction rules."""

    text: str
    source_file: str
    locator: Locator
    source_type: SourceType
    section: str | None
    kind: str


def load_field_aliases(path: str | Path | None = None) -> dict[str, list[str]]:
    """Load the fixed V1 alias catalog and reject ambiguous field definitions."""

    aliases_path = Path(path) if path is not None else _DEFAULT_ALIASES_PATH
    with aliases_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    result: dict[str, list[str]] = {field.value: [] for field in FieldName}
    for field in FieldName:
        raw_aliases = payload.get(field.value, [])
        if not isinstance(raw_aliases, list):
            raise ValueError(f"Aliases for {field.value} must be a list")
        cleaned = []
        for alias in raw_aliases:
            normalized = _label_key(str(alias))
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        result[field.value] = cleaned

    # A generic alias such as "编号" would make project_number and
    # tender_number impossible to distinguish.  Keep only unambiguous aliases.
    ownership: dict[str, set[str]] = {}
    for field, field_aliases in result.items():
        for alias in field_aliases:
            ownership.setdefault(alias, set()).add(field)
    ambiguous = {alias for alias, owners in ownership.items() if len(owners) > 1}
    if ambiguous:
        for field in result:
            result[field] = [alias for alias in result[field] if alias not in ambiguous]
    return result


def _label_key(value: str) -> str:
    """Return a conservative exact-label representation."""

    return normalize_text_value(value).rstrip(_TRAILING_LABEL_PUNCTUATION)


def _aliases_by_length(aliases: Mapping[str, list[str]]) -> list[tuple[str, str]]:
    pairs = [
        (alias, field)
        for field, field_aliases in aliases.items()
        for alias in field_aliases
    ]
    return sorted(pairs, key=lambda item: len(item[0]), reverse=True)


def _alias_pattern(aliases: Mapping[str, list[str]]) -> str:
    return "|".join(
        re.escape(alias)
        for alias, _field in _aliases_by_length(aliases)
    )


def _field_for_exact_label(text: str, aliases: Mapping[str, list[str]]) -> str | None:
    label = _label_key(text)
    for field, field_aliases in aliases.items():
        if label in field_aliases:
            return field
    return None


def _field_for_label_prefix(text: str, aliases: Mapping[str, list[str]]) -> str | None:
    """Match a field label followed only by a colon, with no value."""

    normalized = normalize_text_value(text)
    for alias, field in _aliases_by_length(aliases):
        if re.fullmatch(re.escape(alias) + r"\s*[：:]?", normalized):
            return field
    return None


def _field_at_text_start(text: str, aliases: Mapping[str, list[str]]) -> str | None:
    """Match a label at the start of a record, whether it already has a value."""

    normalized = normalize_text_value(text)
    for alias, field in _aliases_by_length(aliases):
        if re.match(re.escape(alias) + r"\s*[：:]", normalized):
            return field
    return None


def _looks_like_heading(text: str, style_name: str | None = None) -> bool:
    normalized = normalize_text_value(text)
    style = normalize_text_value(style_name or "").lower()
    if not normalized:
        return False
    if "heading" in style or style.startswith("标题"):
        return True
    if re.fullmatch(r"第[^：:]{1,30}[章节篇部分条]", normalized):
        return True
    if normalized in {"招标公告", "采购公告", "投标人须知前附表", "采购公告"}:
        return True
    return False


def _clean_extracted_value(value: str) -> str:
    cleaned = value.strip().strip(_VALUE_EDGE_PUNCTUATION).strip()
    changed = True
    while changed and len(cleaned) >= 2:
        changed = False
        for opening, closing in _QUOTE_PAIRS:
            if cleaned.startswith(opening) and cleaned.endswith(closing):
                cleaned = (
                    cleaned[len(opening) : -len(closing)]
                    .strip()
                    .strip(_VALUE_EDGE_PUNCTUATION)
                    .strip()
                )
                changed = True
                break
    return cleaned


def _record_from_paragraph(
    element: ParagraphElement,
    source_file: str,
    section: str | None,
) -> _TextRecord:
    paragraph = element.paragraph
    return _TextRecord(
        text=paragraph.text,
        source_file=source_file,
        locator=paragraph.locator,
        source_type=SourceType.DOCX,
        section=section,
        kind="paragraph",
    )


def _record_from_pdf_block(
    element: PdfBlockElement,
    source_file: str,
    section: str | None,
) -> _TextRecord:
    block = element.block
    return _TextRecord(
        text=block.text,
        source_file=source_file,
        locator=block.locator,
        source_type=SourceType.PDF,
        section=section,
        kind="pdf_block",
    )


def _iter_ordered_records(document: NormalizedDocument) -> Iterable[_TextRecord]:
    """Yield PDF blocks and DOCX body items in normalized source order."""

    section: str | None = None
    for element in document.elements:
        if isinstance(element, ParagraphElement):
            paragraph = element.paragraph
            if paragraph.text and _looks_like_heading(paragraph.text, paragraph.style_name):
                section = normalize_text_value(paragraph.text)
            yield _record_from_paragraph(element, document.source_file, section)
        elif isinstance(element, PdfBlockElement):
            if element.block.text and _looks_like_heading(element.block.text):
                section = normalize_text_value(element.block.text)
            yield _record_from_pdf_block(element, document.source_file, section)
        elif isinstance(element, TableElement):
            table = element.table
            for row in table.rows:
                for cell in row.cells:
                    yield _TextRecord(
                        text=cell.text,
                        source_file=document.source_file,
                        locator=cell.locator,
                        source_type=SourceType.DOCX,
                        section=section,
                        kind="table_cell",
                    )


def _text_records(records: Iterable[_TextRecord]) -> list[_TextRecord]:
    expanded: list[_TextRecord] = []
    for record in records:
        if record.kind not in {"paragraph", "pdf_block"}:
            continue
        lines = record.text.splitlines() or [record.text]
        expanded.extend(
            _TextRecord(
                text=line,
                source_file=record.source_file,
                locator=record.locator,
                source_type=record.source_type,
                section=record.section,
                kind=record.kind,
            )
            for line in lines
        )
    return expanded


def _make_candidate(
    *,
    field: str,
    value: str,
    record: _TextRecord,
    method: str,
    evidence_text: str,
    confidence: float | None = None,
    locator: Locator | None = None,
) -> CandidateFact | None:
    cleaned_value = _clean_extracted_value(value)
    evidence = evidence_text.strip()
    if not cleaned_value or not evidence:
        return None
    # ``field`` is intentionally only the mapping key.  CandidateFact itself
    # remains unchanged and therefore stays compatible with the ProjectFacts
    # contract established in the previous stage.
    del field
    return CandidateFact(
        value=cleaned_value,
        confidence=confidence if confidence is not None else BASE_CONFIDENCE[method],
        method=method,
        source_file=record.source_file,
        source_type=record.source_type,
        locator=locator or record.locator,
        section=record.section,
        evidence_text=evidence,
    )


def _with_source_file(candidate: CandidateFact, source_file: str) -> CandidateFact:
    return candidate.model_copy(update={"source_file": source_file})


def _table_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    candidates = {field.value: [] for field in FieldName}
    section: str | None = None
    for element in document.elements:
        if isinstance(element, ParagraphElement):
            paragraph = element.paragraph
            if paragraph.text and _looks_like_heading(paragraph.text, paragraph.style_name):
                section = normalize_text_value(paragraph.text)
            continue
        if not isinstance(element, TableElement):
            if isinstance(element, PdfBlockElement) and element.block.text:
                if _looks_like_heading(element.block.text):
                    section = normalize_text_value(element.block.text)
            continue

        table = element.table
        for row in table.rows:
            cells = row.cells
            for cell_position, label_cell in enumerate(cells):
                field = _field_for_exact_label(label_cell.text, aliases)
                if field is None:
                    continue
                value_cell = None
                for offset in range(1, _MAX_TABLE_VALUE_DISTANCE + 1):
                    candidate_position = cell_position + offset
                    if candidate_position >= len(cells):
                        break
                    candidate_cell = cells[candidate_position]
                    if not normalize_text_value(candidate_cell.text):
                        continue
                    if _field_for_exact_label(candidate_cell.text, aliases) is not None:
                        break
                    value_cell = candidate_cell
                    break
                if value_cell is None:
                    continue
                evidence = " | ".join(cell.text.strip() for cell in cells if cell.text.strip())
                record = _TextRecord(
                    text=value_cell.text,
                    source_file=document.source_file,
                    locator=value_cell.locator,
                    source_type=SourceType.DOCX,
                    section=section,
                    kind="table_cell",
                )
                candidate = _make_candidate(
                    field=field,
                    value=value_cell.text,
                    record=record,
                    method="table_label_exact",
                    evidence_text=evidence,
                    locator=value_cell.locator,
                )
                if candidate is not None:
                    candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def _same_line_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    candidates = {field.value: [] for field in FieldName}
    alias_pattern = _alias_pattern(aliases)
    if not alias_pattern:
        return candidates
    label_pattern = re.compile(rf"(?P<label>{alias_pattern})\s*[：:]\s*")
    next_label_pattern = re.compile(rf"(?:{alias_pattern})\s*[：:]")

    for record in _text_records(_iter_ordered_records(document)):
        text = record.text
        for match in label_pattern.finditer(text):
            field = _field_for_exact_label(match.group("label"), aliases)
            if field is None:
                continue
            tail = text[match.end() :]
            next_label = next_label_pattern.search(tail)
            if next_label is not None:
                tail = tail[: next_label.start()]
            value = _clean_extracted_value(tail)
            if not value or _field_for_exact_label(value, aliases) is not None:
                continue
            candidate = _make_candidate(
                field=field,
                value=value,
                record=record,
                method="label_value_same_line",
                evidence_text=text,
            )
            if candidate is not None:
                candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def _next_line_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    candidates = {field.value: [] for field in FieldName}
    records = list(_iter_ordered_records(document))
    expanded_records: list[_TextRecord] = []
    for record in records:
        if record.kind in {"paragraph", "pdf_block"}:
            lines = record.text.splitlines() or [record.text]
            expanded_records.extend(
                _TextRecord(
                    text=line,
                    source_file=record.source_file,
                    locator=record.locator,
                    source_type=record.source_type,
                    section=record.section,
                    kind=record.kind,
                )
                for line in lines
            )
        else:
            expanded_records.append(record)
    records = expanded_records
    for index, record in enumerate(records):
        if record.kind not in {"paragraph", "pdf_block"}:
            continue
        field = _field_for_label_prefix(record.text, aliases)
        if field is None:
            continue
        next_record = None
        for following in records[index + 1 :]:
            if following.kind not in {"paragraph", "pdf_block"}:
                break
            if following.text.strip():
                next_record = following
                break
        if next_record is None:
            continue
        next_value = _clean_extracted_value(next_record.text)
        if not next_value:
            continue
        if (
            _field_for_label_prefix(next_record.text, aliases) is not None
            or _field_at_text_start(next_record.text, aliases) is not None
        ):
            continue
        if _looks_like_heading(next_record.text):
            continue
        evidence = f"{record.text.strip()}\n{next_record.text.strip()}"
        candidate = _make_candidate(
            field=field,
            value=next_value,
            record=next_record,
            method="label_value_next_line",
            evidence_text=evidence,
        )
        if candidate is not None:
            candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def _keyword_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    candidates = {field.value: [] for field in FieldName}
    alias_pattern = _alias_pattern(aliases)
    if not alias_pattern:
        return candidates

    relation_pattern = re.compile(
        rf"(?P<label>{alias_pattern})\s*(?:为|是|指|包括)\s*"
        rf"(?P<value>[^\n，,。；;、]+)"
    )
    boolean_pattern = re.compile(
        rf"(?<![是否])(?P<value>不接受|不允许|不得|禁止|接受|允许|可以|是|否)"
        rf"\s*(?P<label>{alias_pattern})"
    )

    for record in _text_records(_iter_ordered_records(document)):
        for pattern in (relation_pattern, boolean_pattern):
            for match in pattern.finditer(record.text):
                field = _field_for_exact_label(match.group("label"), aliases)
                if field is None:
                    continue
                value = match.group("value")
                # The boolean phrase rule is intentionally narrow.  It exists
                # to preserve the explicit negative in "不接受联合体投标";
                # it is not a general semantic classifier.
                if pattern is boolean_pattern and field != FieldName.CONSORTIUM_ALLOWED.value:
                    continue
                candidate = _make_candidate(
                    field=field,
                    value=value,
                    record=record,
                    method="keyword_window",
                    evidence_text=record.text,
                )
                if candidate is not None:
                    candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def extract_candidates(
    document: NormalizedDocument,
    aliases_path: str | Path | None = None,
) -> dict[str, list[CandidateFact]]:
    """Extract raw candidates without choosing final ProjectFacts values."""

    if document.status.value != "PARSED":
        raise ValueError(f"Fact extraction requires PARSED input, got {document.status.value}")
    if document.source_type is None:
        raise ValueError("Fact extraction requires a PDF or DOCX source type")

    aliases = load_field_aliases(aliases_path)
    candidates = {field.value: [] for field in FieldName}
    for discovered in (
        _table_candidates(document, aliases),
        _same_line_candidates(document, aliases),
        _next_line_candidates(document, aliases),
        _keyword_candidates(document, aliases),
    ):
        for field in FieldName:
            candidates[field.value].extend(discovered[field.value])
    return candidates


__all__ = [
    "BASE_CONFIDENCE",
    "extract_candidates",
    "load_field_aliases",
]
