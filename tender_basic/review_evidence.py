"""Grounded evidence retrieval for the 64-item tender review worksheet.

This layer is intentionally separate from ``ProjectFacts``.  A review row is
an inspection intent, not a fact field.  The deterministic retriever emits
small source-backed candidates; an optional semantic step may only select one
of those candidates.  Python validates the locator and source text before a
candidate is allowed into the workbook.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml
from pydantic import Field

from .document_models import (
    DocumentElement,
    NormalizedDocument,
    ParagraphElement,
    PdfBlockElement,
    PdfTableElement,
    TableElement,
)
from .document_parser import normalize_text
from .format_extractor import BidFormatTemplate
from .models import ContractModel, Locator, PdfLocator, PdfTableLocator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULE_PATH = ROOT / "rules" / "review_items.yaml"

EVIDENCE_STATES = (
    "FOUND",
    "MULTIPLE_FOUND",
    "NOT_APPLICABLE_CANDIDATE",
    "NOT_FOUND",
    "NEEDS_REVIEW",
)


class ReviewItemDefinition(ContractModel):
    id: str = Field(pattern=r"^R\d{3}$")
    module: str
    risk_level: str
    review_intent: str
    keyword_families: list[str] = Field(default_factory=list)
    section_hints: list[str] = Field(default_factory=list)
    priority_section_hints: list[str] = Field(default_factory=list)
    focus_terms: list[str] = Field(default_factory=list)
    negative_or_disqualifying_terms: list[str] = Field(default_factory=list)
    positive_terms: list[str] = Field(default_factory=list)
    applicability_hints: list[str] = Field(default_factory=list)
    required_focus_groups: list[list[str]] = Field(default_factory=list)
    exclusion_terms: list[str] = Field(default_factory=list)


class ReviewEvidenceCandidate(ContractModel):
    review_item_id: str = Field(pattern=r"^R\d{3}$")
    candidate_index: int = Field(ge=0)
    page: int | None = Field(default=None, ge=1)
    section: str = ""
    locator: Locator
    evidence_text: str = Field(min_length=1)
    retrieval_method: str = Field(min_length=1)
    retrieval_score: float = 0.0
    relevance_score: float = 0.0
    source_priority: float = 0.0
    final_score: float = 0.0
    # Kept for backward compatibility with the Round 4.1 packet contract.
    score: float = 0.0


class ReviewEvidenceItem(ContractModel):
    review_item_id: str = Field(pattern=r"^R\d{3}$")
    review_intent: str
    state: Literal[
        "FOUND",
        "MULTIPLE_FOUND",
        "NOT_APPLICABLE_CANDIDATE",
        "NOT_FOUND",
        "NEEDS_REVIEW",
    ]
    candidates: list[ReviewEvidenceCandidate] = Field(default_factory=list)
    evidence_text: str = Field(min_length=1)
    retrieval_stats: dict[str, float] = Field(default_factory=dict)


class ReviewSemanticClassification(ContractModel):
    """Optional WorkBuddy output that can only refer to a packet candidate."""

    review_item_id: str = Field(pattern=r"^R\d{3}$")
    candidate_index: int = Field(ge=0)
    classification: Literal[
        "SUPPORTS_REVIEW_ITEM",
        "NOT_RELEVANT",
        "POSSIBLE_RELEVANCE",
        "NOT_APPLICABLE_SIGNAL",
    ]


@dataclass(frozen=True)
class _Fragment:
    locator: Locator
    page: int | None
    section: str
    text: str
    order: tuple[int, int, int]
    context_text: str = ""
    source_kind: str = "pdf_block"


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(value).replace("\n", " ")).strip()


def _locator_key(locator: Locator) -> str:
    return json.dumps(locator.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def _source_table_cell_text(cell: Any) -> str:
    """Prefer direct PDF spans over a detector's flattened cell text.

    PyMuPDF can interleave QR/watermark artwork with a table cell's text. The
    direct spans retain source geometry, so reconstruct compact line spans and
    discard implausibly tall artwork spans deterministically.
    """

    spans = list(getattr(cell, "spans", []) or [])
    if not spans:
        return cell.text
    usable: list[Any] = []
    for span in spans:
        bbox = getattr(span, "bbox", None)
        if not bbox:
            continue
        height = abs(float(bbox[3]) - float(bbox[1]))
        font_size = float(getattr(span, "font_size", 0.0) or 0.0)
        # Ordinary text spans in these PDFs are small even when the cell is
        # tall.  Do not scale this threshold with the cell height: QR codes,
        # watermarks, and other artwork otherwise become eligible again in
        # large cells and contaminate review evidence.
        max_height = max(32.0, font_size * 3.5)
        if height > max_height:
            continue
        text = str(getattr(span, "text", "") or "")
        if text.strip():
            usable.append(span)
    if not usable:
        return cell.text

    usable.sort(key=lambda span: (float(span.bbox[1]), float(span.bbox[0])))
    lines: list[str] = []
    line_y: float | None = None
    line_parts: list[str] = []
    for span in usable:
        y = float(span.bbox[1])
        font_size = float(getattr(span, "font_size", 0.0) or 0.0)
        tolerance = max(2.0, min(5.0, font_size * 0.35))
        if line_y is None or abs(y - line_y) > tolerance:
            if line_parts:
                lines.append("".join(line_parts).strip())
            line_y = y
            line_parts = []
        line_parts.append(str(getattr(span, "text", "") or "").strip())
    if line_parts:
        lines.append("".join(line_parts).strip())
    reconstructed = "\n".join(line for line in lines if line)
    return reconstructed or cell.text


def load_review_item_definitions(
    path: str | Path | None = None,
) -> tuple[dict[str, list[str]], list[ReviewItemDefinition]]:
    """Load the centralized rule file and enforce exactly R001-R064."""

    rule_path = Path(path) if path is not None else DEFAULT_RULE_PATH
    payload = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
    families = {
        str(name): [str(term) for term in values]
        for name, values in (payload.get("families") or {}).items()
    }
    items = [ReviewItemDefinition.model_validate(item) for item in payload.get("items", [])]
    # Section priority belongs to the centralized rule file, rather than to
    # scattered per-row Python branches.  The map is applied immutably so the
    # public return shape stays compatible with Round 4.1 callers.
    priority_by_module = {
        str(module): [str(term) for term in values]
        for module, values in (payload.get("priority_sections_by_module") or {}).items()
    }
    if priority_by_module:
        items = [
            item.model_copy(
                update={
                    "priority_section_hints": priority_by_module.get(
                        item.module,
                        item.priority_section_hints,
                    )
                }
            )
            for item in items
        ]
    focus_by_id = {
        str(review_id): [str(term) for term in values]
        for review_id, values in (payload.get("focus_terms_by_id") or {}).items()
    }
    if focus_by_id:
        items = [
            item.model_copy(
                update={"focus_terms": focus_by_id.get(item.id, item.focus_terms)}
            )
            for item in items
        ]
    required_focus_groups_by_id = {
        str(review_id): [[str(term) for term in group] for group in groups]
        for review_id, groups in (payload.get("required_focus_groups_by_id") or {}).items()
    }
    exclusion_terms_by_id = {
        str(review_id): [str(term) for term in terms]
        for review_id, terms in (payload.get("exclusion_terms_by_id") or {}).items()
    }
    if required_focus_groups_by_id or exclusion_terms_by_id:
        items = [
            item.model_copy(
                update={
                    "required_focus_groups": required_focus_groups_by_id.get(
                        item.id,
                        item.required_focus_groups,
                    ),
                    "exclusion_terms": exclusion_terms_by_id.get(
                        item.id,
                        item.exclusion_terms,
                    ),
                }
            )
            for item in items
        ]
    ids = [item.id for item in items]
    expected = [f"R{index:03d}" for index in range(1, 65)]
    if ids != expected:
        raise ValueError(f"Review rules must contain ordered R001-R064; got {ids!r}")
    return families, items


def _element_text(element: DocumentElement) -> str:
    if isinstance(element, PdfBlockElement):
        return element.block.text
    if isinstance(element, ParagraphElement):
        return element.paragraph.text
    if isinstance(element, PdfTableElement):
        return ""
    if isinstance(element, TableElement):
        return ""
    return ""


def _element_locator(element: DocumentElement) -> Locator | None:
    if isinstance(element, PdfBlockElement):
        return element.block.locator
    if isinstance(element, ParagraphElement):
        return element.paragraph.locator
    if isinstance(element, (PdfTableElement, TableElement)):
        for row in element.table.rows:
            for cell in row.cells:
                return cell.locator
    return None


def _looks_like_heading(text: str) -> bool:
    value = _compact(text)
    if not value or len(value) > 90:
        return False
    structural = bool(
        re.match(
            r"^(?:第[一二三四五六七八九十百千万零〇0-9]+[章节篇部分条]|"
            r"[一二三四五六七八九十百千万]+[、.．)]|\d+(?:\.\d+)*[、.．)])",
            value,
        )
    )
    if structural:
        # A numbered clause containing a complete sentence is not a section
        # heading merely because it contains a review keyword.
        if value.endswith(("。", "；", ";", "，", ",", "：", ":")):
            return False
        return len(value) <= 42 or value.endswith(("办法", "标准", "格式", "组成", "要求", "须知", "审查", "条款", "准备"))
    marker = (
        "投标人须知", "供应商须知", "供应商须知前附表", "资格审查", "评标办法", "评审办法",
        "评审办法前附表", "评审标准", "评分标准", "投标文件格式", "响应文件格式", "报价文件格式",
        "开标", "合同条款", "电子投标", "投标文件组成", "响应文件组成",
    )
    return value in marker or (len(value) <= 32 and any(value.endswith(term) for term in marker))


def _iter_fragments(document: NormalizedDocument) -> list[_Fragment]:
    """Expose source blocks and table cells without flattening table cells."""

    fragments: list[_Fragment] = []
    seen: set[str] = set()
    current_section_by_page: dict[int, str] = {}
    page_section: dict[int, str] = {}
    table_regions: dict[int, list[tuple[float, float, float, float]]] = {}
    for table in document.tables:
        table_regions.setdefault(table.page, []).append(table.bbox)
    for element in document.elements:
        if not isinstance(element, PdfTableElement):
            continue
        table_regions.setdefault(element.table.page, []).append(element.table.bbox)

    def block_is_inside_table(block: PdfBlockElement) -> bool:
        bbox = block.block.bbox
        center_x = (bbox[0] + bbox[2]) / 2.0
        center_y = (bbox[1] + bbox[3]) / 2.0
        return any(
            region[0] - 1.0 <= center_x <= region[2] + 1.0
            and region[1] - 1.0 <= center_y <= region[3] + 1.0
            for region in table_regions.get(block.page_number, [])
        )

    # First pass: identify lightweight page-local heading context.
    for element in document.elements:
        locator = _element_locator(element)
        text = _element_text(element)
        if locator is None or not isinstance(locator, PdfLocator):
            continue
        if isinstance(element, PdfBlockElement) and block_is_inside_table(element):
            continue
        page = locator.page
        compact = _compact(text)
        if compact and _looks_like_heading(compact):
            page_section[page] = compact[:120]

    for element_index, element in enumerate(document.elements):
        if isinstance(element, PdfBlockElement):
            if block_is_inside_table(element):
                # PyMuPDF may expose a flattened block over the same geometry
                # as a recovered table.  Keep the editable cell locators and
                # suppress the duplicate/garbled block from review evidence.
                continue
            locator = element.block.locator
            text = element.block.text
            if not _compact(text):
                continue
            page = locator.page
            section = page_section.get(page, current_section_by_page.get(page, ""))
            if _looks_like_heading(text):
                current_section_by_page[page] = _compact(text)[:120]
                section = current_section_by_page[page]
            key = _locator_key(locator)
            if key not in seen:
                fragments.append(
                    _Fragment(
                        locator,
                        page,
                        section,
                        text,
                        (page, element_index, 0),
                        context_text=text,
                        source_kind="pdf_block",
                    )
                )
                seen.add(key)
        elif isinstance(element, ParagraphElement):
            locator = element.paragraph.locator
            text = element.paragraph.text
            if not _compact(text):
                continue
            fragments.append(
                _Fragment(
                    locator,
                    None,
                    element.paragraph.style_name or "",
                    text,
                    (0, element_index, 0),
                    context_text=text,
                    source_kind="docx_paragraph",
                )
            )
        elif isinstance(element, PdfTableElement):
            table = element.table
            for row in table.rows:
                row_texts = [_source_table_cell_text(cell) for cell in row.cells]
                for cell in row.cells:
                    cell_text = _source_table_cell_text(cell)
                    if not _compact(cell_text):
                        continue
                    locator = cell.locator
                    key = _locator_key(locator)
                    if key in seen:
                        continue
                    # The cell itself remains the exact source evidence.  The
                    # row context is available to scoring but is not invented
                    # into evidence_text.
                    section = page_section.get(table.page, "")
                    fragments.append(
                        _Fragment(
                            locator,
                            table.page,
                            section,
                            cell_text,
                            (table.page, table.table_index, cell.row_index * 1000 + cell.column_index),
                            context_text=" | ".join(row_texts),
                            source_kind="pdf_table_cell",
                        )
                    )
                    seen.add(key)
        elif isinstance(element, TableElement):
            table = element.table
            for row in table.rows:
                for cell in row.cells:
                    if not _compact(cell.text):
                        continue
                    locator = cell.locator
                    key = _locator_key(locator)
                    if key in seen:
                        continue
                    fragments.append(
                        _Fragment(
                            locator,
                            None,
                            "",
                            cell.text,
                            (0, table.table_index, cell.row_index * 1000 + cell.column_index),
                            context_text=" | ".join(
                                sibling.text for sibling in row.cells
                            ),
                            source_kind="docx_table_cell",
                        )
                    )
                    seen.add(key)

    # Some callers construct a NormalizedDocument with ``tables`` but without
    # corresponding PdfTableElement entries.  Retain that contract too.
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = _source_table_cell_text(cell)
                if not _compact(cell_text):
                    continue
                key = _locator_key(cell.locator)
                if key in seen:
                    continue
                fragments.append(
                    _Fragment(
                        cell.locator,
                        table.page,
                        page_section.get(table.page, ""),
                        cell_text,
                        (table.page, table.table_index, cell.row_index * 1000 + cell.column_index),
                        context_text=" | ".join(
                            _source_table_cell_text(sibling)
                            for row in table.rows
                            if row.row_index == cell.row_index
                            for sibling in row.cells
                        ),
                        source_kind="pdf_table_cell",
                    )
                )
                seen.add(key)
    return fragments


def _source_format_terms(format_template: BidFormatTemplate | None) -> list[str]:
    if format_template is None or not format_template.usable:
        return []
    terms = [format_template.source_heading or ""]
    terms.extend(
        element.text
        for element in format_template.elements
        if element.type == "heading" and element.text
    )
    return [term for term in terms if len(_compact(term)) >= 2]


def _snippet(text: str, terms: Iterable[str], limit: int = 320) -> str:
    compact = _compact(text)
    if len(compact) <= limit:
        return compact
    positions = [compact.find(term) for term in terms if term and compact.find(term) >= 0]
    start = max(0, min(positions) - 100) if positions else 0
    end = min(len(compact), start + limit)
    if start > 0:
        compact = "…" + compact[start:end]
    elif end < len(compact):
        compact = compact[:end] + "…"
    return compact


@dataclass(frozen=True)
class _RankedCandidate:
    """Internal two-stage retrieval record; never written as a raw hit list."""

    fragment: _Fragment
    direct_terms: tuple[str, ...]
    context_terms: tuple[str, ...]
    matched_families: tuple[str, ...]
    retrieval_score: float
    relevance_score: float
    source_priority: float
    final_score: float
    retrieval_method: str
    heading_only: bool = False


def _compact_terms(terms: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(_compact(term) for term in terms if _compact(term)))


def _term_weight(term: str) -> float:
    value = _compact(term)
    if value == "★":
        return 3.0
    if value in {"CA", "U盘", "光盘"}:
        return 2.5
    return min(5.0, max(1.0, len(value) / 2.5))


def _matches(text: str, terms: Iterable[str]) -> list[str]:
    compact = _compact(text)
    return [term for term in terms if _compact(term) in compact]


def _section_matches(text: str, terms: Iterable[str]) -> list[str]:
    compact = _compact(text)
    return [term for term in terms if _compact(term) and _compact(term) in compact]


def _source_format_relevance(definition: ReviewItemDefinition, text: str, format_terms: list[str]) -> float:
    if not format_terms:
        return 0.0
    if definition.module not in {"投标文件组成与格式", "签章与电子标"}:
        return 0.0
    return 2.0 if _section_matches(text, format_terms) else 0.0


def _candidate_record(
    fragment: _Fragment,
    direct_terms: list[str],
    context_terms: list[str],
    matched_families: list[str],
    definition: ReviewItemDefinition,
    format_terms: list[str],
) -> _RankedCandidate:
    section_priority_hits = _section_matches(fragment.section, definition.priority_section_hints)
    section_hint_hits = _section_matches(fragment.section, definition.section_hints)
    direct_weight = sum(_term_weight(term) for term in direct_terms)
    context_weight = sum(_term_weight(term) for term in context_terms if term not in direct_terms)
    family_coverage = min(4.0, float(len(set(matched_families))))
    focus_terms = _compact_terms(definition.focus_terms)
    focus_direct = _matches(fragment.text, focus_terms)
    focus_context = _matches(fragment.context_text, focus_terms)
    retrieval_score = direct_weight + (0.35 * context_weight)
    relevance_score = (
        direct_weight
        + (2.0 * family_coverage)
        + (4.0 if section_priority_hits else 0.0)
        + (1.25 if section_hint_hits else 0.0)
        + (2.0 if any(_compact(term) in _compact(fragment.text) for term in definition.positive_terms) else 0.0)
        + (1.0 if any(_compact(term) in _compact(fragment.text) for term in definition.negative_or_disqualifying_terms) else 0.0)
        + _source_format_relevance(definition, fragment.text, format_terms)
        + (0.75 if isinstance(fragment.locator, PdfTableLocator) else 0.0)
    )
    if focus_direct:
        relevance_score += min(4.0, 1.5 + 0.75 * len(set(focus_direct)))
    elif focus_terms and focus_context:
        relevance_score -= 0.75
    elif focus_terms:
        relevance_score -= 3.0
    # Prefer operative clauses over headings/questions.  This is deliberately
    # vocabulary-neutral: it rewards a requirement, deadline, amount, or
    # prohibition pattern regardless of the particular procurement wording.
    explicit_clause = bool(
        re.search(
            r"(?:必须|应当|应|不得|禁止|不接受|不允许|无效|否决|截止|金额|形式|"
            r"平台|上传|加密|解密|签字|盖章|密封|评分|分值|日历天|按照|要求)",
            _compact(fragment.text),
        )
    )
    if explicit_clause:
        relevance_score += 1.5
    if "是否" in _compact(fragment.text) and not re.search(
        r"(?:不接受|不允许|允许|明确接受|接受联合体后|为)",
        _compact(fragment.text),
    ):
        relevance_score -= 2.0
    source_priority = 1.0 if isinstance(fragment.locator, PdfTableLocator) else 0.75
    if section_priority_hits:
        source_priority += 2.0
    if _source_format_relevance(definition, fragment.text, format_terms):
        source_priority += 1.0
    if not direct_terms and context_terms:
        relevance_score -= 1.5
    compact_text = _compact(fragment.text)
    heading_only = _looks_like_heading(fragment.text) and len(compact_text) <= 60
    if heading_only:
        relevance_score -= 3.0
    method_parts = ["broad_keyword"]
    if context_terms and not direct_terms:
        method_parts.append("table_row_context")
    if section_priority_hits:
        method_parts.append("priority_section")
    elif section_hint_hits:
        method_parts.append("section_hint")
    if _source_format_relevance(definition, fragment.text, format_terms):
        method_parts.append("source_format")
    if isinstance(fragment.locator, PdfTableLocator):
        method_parts.append("table_cell")
    return _RankedCandidate(
        fragment=fragment,
        direct_terms=tuple(direct_terms),
        context_terms=tuple(context_terms),
        matched_families=tuple(sorted(set(matched_families))),
        retrieval_score=round(retrieval_score, 3),
        relevance_score=round(relevance_score, 3),
        source_priority=round(source_priority, 3),
        final_score=round(retrieval_score + relevance_score + source_priority, 3),
        retrieval_method="+".join(method_parts),
        heading_only=heading_only,
    )


def _dedupe_key(text: str) -> str:
    value = _compact(text)
    value = re.sub(r"[“”‘’'\"`（）()【】\[\]：:；;，,。.!！?？、/\\|]+", "", value)
    return value


def _near_duplicate(left: _RankedCandidate, right: _RankedCandidate) -> bool:
    a = _dedupe_key(left.fragment.text)
    b = _dedupe_key(right.fragment.text)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 18 and shorter in longer:
        return len(longer) - len(shorter) <= max(45, int(len(longer) * 0.35))
    if len(shorter) >= 28:
        return SequenceMatcher(None, a, b).ratio() >= 0.92
    return False


def _is_review_heading_allowed(definition: ReviewItemDefinition, candidate: _RankedCandidate) -> bool:
    if not candidate.heading_only:
        return True
    # A heading is useful evidence for format/signature rows, but a bare
    # “资格审查资料” or “评标办法” heading is not itself a requirement.
    return definition.module in {"投标文件组成与格式", "签章与电子标"}


def _looks_like_navigation(text: str) -> bool:
    """Identify TOC/index boilerplate without treating it as evidence."""

    value = text or ""
    punctuation = value.count(".") + value.count("．") + value.count("…")
    if punctuation < 3:
        return False
    compact = _compact(value)
    repeated_dots = bool(re.search(r"(?:\.{3,}|…{2,}|．{3,})", value))
    if (
        len(compact) <= 260
        and repeated_dots
        and ("…" in value or punctuation >= 8)
    ):
        return True
    # A contents block may wrap across several PDF lines and therefore exceed
    # the short-snippet limit.  Treat it as navigation when at least two lines
    # are dot leaders ending in a page number.  A single ellipsis in ordinary
    # prose is intentionally not enough.
    leader_lines = [
        line.strip()
        for line in value.splitlines()
        if re.search(r"(?:\.{3,}|…{2,}|．{3,})", line)
        and re.search(r"\d{1,4}\s*$", line)
    ]
    if len(leader_lines) >= 2:
        return True
    leader_pairs = re.findall(r"(?:\.{3,}|…{2,}|．{3,})\s*\d{1,4}", value)
    return len(leader_pairs) >= 2


def _is_bare_label(candidate: _RankedCandidate, definition: ReviewItemDefinition) -> bool:
    """Reject labels/headings that do not state an operative requirement."""

    text = _compact(candidate.fragment.text)
    if not text or len(text) > 24 or re.search(r"\d", text):
        return False
    if re.search(r"[。；;，,:：()（）]", text):
        return False
    if definition.module in {"投标文件组成与格式", "签章与电子标"}:
        return False
    if text.startswith("是否") and not re.search(r"(?:不接受|不允许|允许|明确接受|接受联合体后|为)", text):
        return True
    operative = re.compile(
        r"(?:必须|应当|不得|禁止|不接受|不允许|截止|金额|形式|地点|平台|上传|"
        r"加密|解密|签字|盖章|签章|评分|分值|超过|不超过|按照|按要求|逐条)",
    )
    if operative.search(text):
        return False
    return bool(_matches(text, _compact_terms(definition.focus_terms)))


def _is_candidate_eligible(
    candidate: _RankedCandidate,
    definition: ReviewItemDefinition,
) -> bool:
    if not _is_review_heading_allowed(definition, candidate):
        return False
    text = _compact(candidate.fragment.text)
    section = _compact(candidate.fragment.section)
    if _looks_like_navigation(text):
        return False
    if _is_bare_label(candidate, definition):
        return False
    excluded = definition.exclusion_terms and any(
        _compact(term) and _compact(term) in text
        for term in definition.exclusion_terms
    )
    if excluded:
        if not definition.required_focus_groups:
            return False
    focus_terms = _compact_terms(definition.focus_terms)
    focus_direct = _matches(candidate.fragment.text, focus_terms)
    if focus_terms and not focus_direct and candidate.direct_terms:
        return False
    if definition.required_focus_groups:
        group_hits = sum(
            any(_compact(term) and _compact(term) in text for term in group)
            for group in definition.required_focus_groups
        )
        if group_hits < len(definition.required_focus_groups):
            return False
    if definition.module == "评分项复核":
        scoring_terms = ("评标", "评审", "评分", "分值", "得分", "基准价", "详细评审")
        if not any(term in text or term in section for term in scoring_terms):
            return False
        strong_scoring_terms = ("评分", "分值", "得分", "基准价", "评标价", "异常低价", "成本价")
        # A scoring section heading alone is not evidence for a scoring row;
        # the retained snippet must state a score, criterion, formula, or
        # other operative scoring term.
        if not any(term in text for term in strong_scoring_terms):
            return False
    if definition.id == "R010" and "履约保证金" in text and not re.search(
        r"(?:投标|响应|询比)保证金",
        text,
    ):
        return False
    # A two-character generic hit such as “合同” or “参数” is recall-only
    # unless the section or a second family supplies corroborating context.
    strong_direct = [term for term in candidate.direct_terms if len(_compact(term)) >= 3 or _compact(term) in {"★", "CA"}]
    if candidate.direct_terms and not strong_direct and len(candidate.matched_families) < 2:
        return False
    if not candidate.direct_terms and candidate.context_terms:
        # Row-context recovery is accepted only when the cell is attached to a
        # useful table row and the signal is not merely a common short word.
        if not isinstance(candidate.fragment.locator, PdfTableLocator):
            return False
        if candidate.final_score < 8.0:
            return False
    return candidate.final_score >= 4.0


def _independently_useful(
    left: _RankedCandidate,
    right: _RankedCandidate,
    definition: ReviewItemDefinition,
) -> bool:
    if _near_duplicate(left, right):
        return False
    if not left.direct_terms or not right.direct_terms:
        return False
    for candidate in (left, right):
        text = _compact(candidate.fragment.text)
        if "是否" in text and not re.search(
            r"(?:不接受|不允许|允许|明确接受|接受联合体后|为)",
            text,
        ):
            return False
    focus_terms = _compact_terms(definition.focus_terms)
    left_anchors = set(_matches(left.fragment.text, focus_terms))
    right_anchors = set(_matches(right.fragment.text, focus_terms))
    if not left_anchors or not right_anchors:
        return False
    high_information = re.compile(
        r"(?:必须|应当|应|不得|禁止|不接受|不允许|无效|否决|截止|金额|形式|"
        r"时间|地点|要求|标准|方法|分值|评分|报价|保证金|联合体|密封|签章|"
        r"上传|解密|合同|履约|质保|工期|供货|交货|资格|资质|授权)",
    )
    if any(
        len(_compact(candidate.fragment.text)) < 24
        or not high_information.search(_compact(candidate.fragment.text))
        for candidate in (left, right)
    ):
        return False
    overlap = len(left_anchors & right_anchors) / max(1, min(len(left_anchors), len(right_anchors)))
    if overlap >= 0.5:
        return False
    left_families = set(left.matched_families)
    right_families = set(right.matched_families)
    if left_families != right_families and left_anchors != right_anchors:
        return True
    left_section = _compact(left.fragment.section)
    right_section = _compact(right.fragment.section)
    if left_section != right_section and left_section and right_section:
        return True
    # Two different pages in the same section are useful only when the
    # clauses contain materially different text, not repeated labels.
    return (
        len(_compact(left.fragment.text)) >= 24
        and len(_compact(right.fragment.text)) >= 24
        and left_anchors != right_anchors
        and left_families != right_families
    )


def _prune_candidates(
    ranked: list[_RankedCandidate],
    definition: ReviewItemDefinition,
) -> tuple[list[_RankedCandidate], dict[str, int]]:
    stats = {
        "duplicate_evidence_removed": 0,
        "boilerplate_removed": 0,
        "low_relevance_candidates_removed": 0,
        "repeated_chrome_removed": 0,
    }
    ranked = sorted(ranked, key=lambda item: (-item.final_score, item.fragment.order))
    deduped: list[_RankedCandidate] = []
    for candidate in ranked:
        duplicate = next((existing for existing in deduped if _near_duplicate(candidate, existing)), None)
        if duplicate is not None:
            stats["duplicate_evidence_removed"] += 1
            if _dedupe_key(candidate.fragment.text) == _dedupe_key(duplicate.fragment.text):
                stats["boilerplate_removed"] += 1
            continue
        deduped.append(candidate)
    if not deduped:
        return [], stats
    top_score = deduped[0].final_score
    # Keep a small relevance band around the best clause; this is the second
    # deterministic stage after broad keyword recall.
    survivors = [candidate for candidate in deduped if candidate.final_score >= max(4.0, top_score - 5.0)]
    stats["low_relevance_candidates_removed"] += max(0, len(deduped) - len(survivors))
    selected: list[_RankedCandidate] = []
    for candidate in survivors:
        if len(selected) >= 3:
            stats["low_relevance_candidates_removed"] += 1
            continue
        if any(not _independently_useful(candidate, existing, definition) for existing in selected):
            stats["duplicate_evidence_removed"] += 1
            continue
        selected.append(candidate)
    return selected, stats


def _electronic_signal(fragments: list[_Fragment]) -> _Fragment | None:
    signals = ("电子投标", "全流程电子", "不见面开标", "在线上传", "CA解密", "网上递交")
    for fragment in fragments:
        compact = _compact(fragment.text + " " + fragment.context_text)
        if any(signal in compact for signal in signals):
            return fragment
    return None


def _is_conflict_candidate(
    item: ReviewEvidenceItem,
    definition: ReviewItemDefinition,
) -> bool:
    if not item.candidates:
        return False
    text = " ".join(candidate.evidence_text for candidate in item.candidates)
    compact = _compact(text)
    if definition.id == "R002":
        negative = "不接受联合体" in compact or "禁止联合体" in compact
        positive = bool(
            re.search(
                r"(?<!不)(?<!是否)(?:明确接受|允许)联合体|"
                r"(?<!不)(?<!是否)接受联合体",
                compact,
            )
        )
        return negative and positive
    return False


def retrieve_review_evidence(
    document: NormalizedDocument,
    *,
    format_template: BidFormatTemplate | None = None,
    rule_path: str | Path | None = None,
) -> tuple[list[ReviewEvidenceItem], list[dict[str, Any]]]:
    """Run broad recall, deterministic pruning, and source-backed validation.

    The function deliberately returns the same two-tuple used in Round 4.1.
    Candidate scores and per-row retrieval counts are retained on the model so
    QA can explain pruning without exposing the raw recall pool in Excel.
    """

    families, definitions = load_review_item_definitions(rule_path)
    fragments = _iter_fragments(document)
    format_terms = _source_format_terms(format_template)
    packet: list[dict[str, Any]] = []
    items: list[ReviewEvidenceItem] = []
    electronic_fragment = _electronic_signal(fragments)

    for definition in definitions:
        family_terms = {
            family: _compact_terms(families.get(family, []))
            for family in definition.keyword_families
        }
        all_terms = _compact_terms(
            term
            for terms in family_terms.values()
            for term in terms
        )
        all_terms = _compact_terms(
            [
                *all_terms,
                *definition.negative_or_disqualifying_terms,
                *definition.positive_terms,
                *definition.focus_terms,
            ]
        )
        term_families = {
            term: [family for family, terms in family_terms.items() if term in terms]
            for term in all_terms
        }
        stage_one: list[_RankedCandidate] = []
        for fragment in fragments:
            direct_terms = _matches(fragment.text, all_terms)
            context_terms = _matches(fragment.context_text, all_terms)
            if not direct_terms and not context_terms:
                continue
            matched_families = [
                family
                for term in _compact_terms([*direct_terms, *context_terms])
                for family in term_families.get(term, [])
            ]
            stage_one.append(
                _candidate_record(
                    fragment,
                    direct_terms,
                    context_terms,
                    matched_families,
                    definition,
                    format_terms,
                )
            )
        stage_one.sort(key=lambda item: (-item.final_score, item.fragment.order))
        # The broad pool is intentionally bounded for memory and packet
        # stability; this is still much wider than the three snippets sent to
        # the workbook.
        stage_one = stage_one[:40]
        eligible = [
            candidate
            for candidate in stage_one
            if _is_candidate_eligible(candidate, definition)
        ]
        selected_records, prune_stats = _prune_candidates(eligible, definition)

        selected: list[ReviewEvidenceCandidate] = []
        for candidate_index, record in enumerate(selected_records):
            matched = list(record.direct_terms or record.context_terms)
            selected.append(
                ReviewEvidenceCandidate(
                    review_item_id=definition.id,
                    candidate_index=candidate_index,
                    page=record.fragment.page,
                    section=record.fragment.section,
                    locator=record.fragment.locator,
                    evidence_text=_snippet(record.fragment.text, matched),
                    retrieval_method=record.retrieval_method,
                    retrieval_score=record.retrieval_score,
                    relevance_score=record.relevance_score,
                    source_priority=record.source_priority,
                    final_score=record.final_score,
                    score=record.final_score,
                )
            )

        state: str
        if not selected:
            if definition.applicability_hints and electronic_fragment is not None:
                state = "NOT_APPLICABLE_CANDIDATE"
                selected = [
                    ReviewEvidenceCandidate(
                        review_item_id=definition.id,
                        candidate_index=0,
                        page=electronic_fragment.page,
                        section=electronic_fragment.section,
                        locator=electronic_fragment.locator,
                        evidence_text=_snippet(
                            electronic_fragment.text,
                            definition.applicability_hints,
                        ),
                        retrieval_method="applicability_signal",
                        retrieval_score=1.0,
                        relevance_score=1.0,
                        source_priority=1.0,
                        final_score=3.0,
                        score=3.0,
                    )
                ]
            else:
                # A weak, ambiguous direct hit is surfaced for a human rather
                # than promoted to positive evidence.  Bare headings and
                # generic words remain honest NOT_FOUND.
                ambiguous = next(
                    (
                        candidate
                        for candidate in stage_one
                        if not candidate.heading_only
                        and not _looks_like_navigation(candidate.fragment.text)
                        and not _is_bare_label(candidate, definition)
                        and not any(
                            _compact(term) and _compact(term) in _compact(candidate.fragment.text)
                            for term in definition.exclusion_terms
                        )
                        and candidate.direct_terms
                        and (
                            not definition.focus_terms
                            or bool(_matches(candidate.fragment.text, definition.focus_terms))
                        )
                        and (
                            not definition.required_focus_groups
                            or all(
                                any(
                                    _compact(term)
                                    and _compact(term) in _compact(candidate.fragment.text)
                                    for term in group
                                )
                                for group in definition.required_focus_groups
                            )
                        )
                        and (
                            definition.module != "评分项复核"
                            or any(
                                term in _compact(candidate.fragment.text)
                                for term in (
                                    "评分", "分值", "得分", "基准价", "评标价",
                                    "异常低价", "成本价",
                                )
                            )
                        )
                        and candidate.final_score >= 3.5
                    ),
                    None,
                )
                if ambiguous is not None:
                    selected = [
                        ReviewEvidenceCandidate(
                            review_item_id=definition.id,
                            candidate_index=0,
                            page=ambiguous.fragment.page,
                            section=ambiguous.fragment.section,
                            locator=ambiguous.fragment.locator,
                            evidence_text=_snippet(
                                ambiguous.fragment.text,
                                list(ambiguous.direct_terms),
                            ),
                            retrieval_method=ambiguous.retrieval_method,
                            retrieval_score=ambiguous.retrieval_score,
                            relevance_score=ambiguous.relevance_score,
                            source_priority=ambiguous.source_priority,
                            final_score=ambiguous.final_score,
                            score=ambiguous.final_score,
                        )
                    ]
                    state = "NEEDS_REVIEW"
                else:
                    state = "NOT_FOUND"
        else:
            state = "MULTIPLE_FOUND" if len(selected) > 1 else "FOUND"
            provisional = ReviewEvidenceItem(
                review_item_id=definition.id,
                review_intent=definition.review_intent,
                state="FOUND",
                candidates=selected,
                evidence_text="placeholder",
            )
            if _is_conflict_candidate(provisional, definition):
                state = "NEEDS_REVIEW"
            elif (
                definition.applicability_hints
                and electronic_fragment is not None
                and definition.id in {"R061", "R062"}
                and not any(
                    any(
                        term in _compact(candidate.evidence_text)
                        for term in families.get("packaging", [])
                    )
                    for candidate in selected
                )
            ):
                state = "NOT_APPLICABLE_CANDIDATE"

        if state == "FOUND":
            evidence_text = f"FOUND：{_format_candidates(selected[:1])}"
        elif state == "MULTIPLE_FOUND":
            evidence_text = f"MULTIPLE_FOUND：{_format_candidates(selected[:3])}"
        elif state == "NOT_APPLICABLE_CANDIDATE":
            evidence_text = (
                f"NOT_APPLICABLE_CANDIDATE：{_format_candidates(selected[:1])}"
                " 建议人工确认本项是否适用。"
            )
        elif state == "NEEDS_REVIEW":
            evidence_text = (
                "NEEDS_REVIEW：检出相关条款但存在适用性或表述歧义，"
                f"{_format_candidates(selected[:3])}"
            )
        else:
            evidence_text = "NOT_FOUND：未检出明确招标文件依据，需人工复核。"

        retrieval_stats = {
            "candidates_retrieved": float(len(stage_one)),
            "candidates_eligible": float(len(eligible)),
            "candidates_after_pruning": float(len(selected_records)),
            "evidence_snippets_written": float(len(selected)),
            **{key: float(value) for key, value in prune_stats.items()},
        }
        if state == "NOT_APPLICABLE_CANDIDATE" and not selected_records:
            retrieval_stats["evidence_snippets_written"] = float(len(selected))
            retrieval_stats["candidates_after_pruning"] = float(len(selected))
        item = ReviewEvidenceItem(
            review_item_id=definition.id,
            review_intent=definition.review_intent,
            state=state,  # type: ignore[arg-type]
            candidates=selected,
            evidence_text=evidence_text,
            retrieval_stats=retrieval_stats,
        )
        items.append(item)
        for candidate in selected:
            packet.append(
                {
                    "review_item_id": definition.id,
                    "review_intent": definition.review_intent,
                    "candidate_index": candidate.candidate_index,
                    "page": candidate.page,
                    "section": candidate.section,
                    "locator": candidate.locator.model_dump(mode="json"),
                    "evidence_text": candidate.evidence_text,
                    "retrieval_method": candidate.retrieval_method,
                    "retrieval_score": candidate.retrieval_score,
                    "relevance_score": candidate.relevance_score,
                    "source_priority": candidate.source_priority,
                    "final_score": candidate.final_score,
                }
            )
    return items, packet


def _format_candidates(candidates: list[ReviewEvidenceCandidate]) -> str:
    values: list[str] = []
    for candidate in candidates:
        page = f"第{candidate.page}页" if candidate.page is not None else "源文档"
        section = f" {candidate.section}" if candidate.section else ""
        values.append(f"{page}{section}：{candidate.evidence_text}")
    return "；".join(values)


def _fragment_index(document: NormalizedDocument) -> dict[str, _Fragment]:
    return {_locator_key(fragment.locator): fragment for fragment in _iter_fragments(document)}


def validate_review_evidence(
    document: NormalizedDocument,
    items: list[ReviewEvidenceItem],
    *,
    rule_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate every accepted candidate against the normalized source."""

    _families, definitions = load_review_item_definitions(rule_path)
    definition_ids = {item.id for item in definitions}
    fragments = _fragment_index(document)
    invalid: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in items:
        if item.review_item_id not in definition_ids:
            invalid.append({"item": item.review_item_id, "reason": "unknown_review_item"})
            continue
        seen_ids.add(item.review_item_id)
        for candidate in item.candidates:
            key = _locator_key(candidate.locator)
            fragment = fragments.get(key)
            if fragment is None:
                invalid.append(
                    {"item": item.review_item_id, "candidate_index": candidate.candidate_index, "reason": "invalid_locator"}
                )
                continue
            if candidate.page is not None and fragment.page != candidate.page:
                invalid.append(
                    {"item": item.review_item_id, "candidate_index": candidate.candidate_index, "reason": "page_mismatch"}
                )
            source_text = _compact(fragment.text)
            evidence_text = _compact(candidate.evidence_text).replace("…", "")
            if evidence_text and evidence_text not in source_text:
                invalid.append(
                    {
                        "item": item.review_item_id,
                        "candidate_index": candidate.candidate_index,
                        "reason": "evidence_text_not_in_source",
                    }
                )
    missing_items = sorted(definition_ids - seen_ids)
    return {
        "invalid_locators": sum(issue["reason"] in {"invalid_locator", "page_mismatch"} for issue in invalid),
        "invalid_candidates": len(invalid),
        "missing_review_items": missing_items,
        "issues": invalid,
    }


def validate_semantic_classifications(
    packet: Iterable[dict[str, Any]],
    classifications: Iterable[ReviewSemanticClassification | dict[str, Any]],
) -> list[ReviewSemanticClassification]:
    """Accept only classifications that point to an existing packet candidate."""

    packet_keys = {
        (str(item.get("review_item_id")), int(item.get("candidate_index", -1)))
        for item in packet
    }
    accepted: list[ReviewSemanticClassification] = []
    for raw in classifications:
        classification = (
            raw
            if isinstance(raw, ReviewSemanticClassification)
            else ReviewSemanticClassification.model_validate(raw)
        )
        if (classification.review_item_id, classification.candidate_index) not in packet_keys:
            continue
        accepted.append(classification)
    return accepted


def review_evidence_qa(
    items: list[ReviewEvidenceItem],
    validation: dict[str, Any],
    *,
    stray_rows: int = 0,
) -> dict[str, Any]:
    counts = {state.lower(): 0 for state in EVIDENCE_STATES}
    for item in items:
        counts[item.state.lower()] += 1
    unclassified = sum(
        item.state not in EVIDENCE_STATES or not item.evidence_text.strip()
        for item in items
    )
    unclassified += len(validation.get("missing_review_items", []))
    stat_names = (
        "candidates_retrieved",
        "candidates_after_pruning",
        "evidence_snippets_written",
        "duplicate_evidence_removed",
        "boilerplate_removed",
        "low_relevance_candidates_removed",
        "repeated_chrome_removed",
    )
    totals = {
        name: sum(float(item.retrieval_stats.get(name, 0.0)) for item in items)
        for name in stat_names
    }
    written_counts = [
        int(item.retrieval_stats.get("evidence_snippets_written", len(item.candidates)))
        for item in items
    ]
    total = max(1, len(items))
    return {
        "total_review_items": len(items),
        "found": counts["found"],
        "multiple_found": counts["multiple_found"],
        "not_applicable_candidate": counts["not_applicable_candidate"],
        "not_found": counts["not_found"],
        "needs_review": counts["needs_review"],
        "unclassified": unclassified,
        "invalid_locators": int(validation.get("invalid_locators", 0)),
        "invalid_candidates": int(validation.get("invalid_candidates", 0)),
        "stray_rows": int(stray_rows),
        "average_candidates_retrieved": round(totals["candidates_retrieved"] / total, 3),
        "average_candidates_after_pruning": round(totals["candidates_after_pruning"] / total, 3),
        "average_evidence_snippets_written": round(totals["evidence_snippets_written"] / total, 3),
        "max_evidence_snippets_written": max(written_counts, default=0),
        "rows_with_more_than_3_written_snippets": sum(value > 3 for value in written_counts),
        "duplicate_evidence_removed": int(totals["duplicate_evidence_removed"]),
        "boilerplate_removed": int(totals["boilerplate_removed"]),
        "low_relevance_candidates_removed": int(totals["low_relevance_candidates_removed"]),
        "repeated_chrome_removed": int(totals["repeated_chrome_removed"]),
        "result": "PASS"
        if (
            len(items) == 64
            and unclassified == 0
            and int(validation.get("invalid_locators", 0)) == 0
            and int(stray_rows) == 0
        )
        else "FAIL",
    }


def write_review_evidence_files(
    output_dir: str | Path,
    items: list[ReviewEvidenceItem],
    packet: list[dict[str, Any]],
    qa: dict[str, Any],
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "review_evidence_packet.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "review_evidence_qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def iter_source_fragments(document: NormalizedDocument) -> list[_Fragment]:
    """Public wrapper over the shared ordered source-fragment index.

    Round 5.5 requirement extraction reuses this exact index so the review
    evidence and the source requirement index can never disagree about what the
    source contains.
    """

    return _iter_fragments(document)


__all__ = [
    "DEFAULT_RULE_PATH",
    "EVIDENCE_STATES",
    "ReviewEvidenceCandidate",
    "ReviewEvidenceItem",
    "ReviewItemDefinition",
    "ReviewSemanticClassification",
    "iter_source_fragments",
    "load_review_item_definitions",
    "retrieve_review_evidence",
    "review_evidence_qa",
    "validate_review_evidence",
    "validate_semantic_classifications",
    "write_review_evidence_files",
]
