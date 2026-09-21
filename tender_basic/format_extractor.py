"""Deterministic extraction of the source bid-document format section.

The format extractor is intentionally separate from fact extraction.  It only
keeps source structure, fixed wording, form names, and tables.  It never
creates or resolves a ProjectFacts value.
"""

from __future__ import annotations

import re
from typing import Iterable, Literal

from pydantic import Field

from .document_models import (
    DocumentElement,
    NormalizedDocument,
    ParagraphElement,
    PdfBlockElement,
    PdfTableElement,
    TableElement,
)
from .models import ContractModel, Locator, SourceType
from .document_parser import normalize_text


FORMAT_SECTION_FOUND = "FORMAT_SECTION_FOUND"
FORMAT_SECTION_NOT_FOUND = "FORMAT_SECTION_NOT_FOUND"
FORMAT_SECTION_NEEDS_REVIEW = "FORMAT_SECTION_NEEDS_REVIEW"

FORMAT_HEADING_CANDIDATES = (
    "投标文件格式及附件",
    "响应文件格式及要求",
    "响应文件格式及附件",
    "投标文件格式要求",
    "响应文件组成",
    "投标文件格式",
    "响应文件格式",
)

_FORMAT_PHRASES = "|".join(re.escape(value) for value in FORMAT_HEADING_CANDIDATES)
_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百千万零〇0-9]+[章节篇部分条]$")
_ORDERED_RE = re.compile(
    r"^(?P<prefix>(?:第[一二三四五六七八九十百千万零〇0-9]+[章节篇部分条])|"
    r"(?:[一二三四五六七八九十百千万]+[、.．)]|\d+(?:\.\d+)*[、.．)]))"
    r"\s*(?P<body>.+)$"
)
_FORMAT_TITLE_RE = re.compile(
    rf"^(?:(?P<prefix>第[一二三四五六七八九十百千万零〇0-9]+[章节篇部分条]|"
    rf"[一二三四五六七八九十百千万]+[、.．)]|\d+(?:\.\d+)*[、.．)])"
    rf"\s*[:：]?\s*)?(?P<phrase>{_FORMAT_PHRASES})"
    rf"(?:\s*[（(][^）)]{{0,40}}[）)])?$"
)
_STYLE_LEVEL_RE = re.compile(r"(?:heading|标题)\s*([1-9])", re.IGNORECASE)
_OUTLINE_PREFIX_RE = re.compile(r"^(?P<prefix>[一二三四五六七八九十百千万零〇0-9]+)[、.．)]")


class FormatElement(ContractModel):
    """One lightweight element retained from the source format section."""

    type: Literal["heading", "paragraph", "table"]
    text: str = ""
    locator: Locator | None = None
    heading_level: int | None = Field(default=None, ge=1, le=9)
    table: object | None = None


class BidFormatTemplate(ContractModel):
    """A small, source-ordered template used to seed the bid document."""

    source_heading: str | None = None
    source_locator: Locator | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    elements: list[FormatElement] = Field(default_factory=list)
    section_status: str = FORMAT_SECTION_NOT_FOUND
    boundary_reason: str = ""
    candidate_count: int = 0
    boundary_locator: Locator | None = None

    @property
    def found(self) -> bool:
        return self.section_status == FORMAT_SECTION_FOUND

    @property
    def usable(self) -> bool:
        """Whether it is safe to use this section as the document skeleton."""

        return self.found and bool(self.elements)

    @property
    def format_source(self) -> str:
        return "SOURCE_DOCUMENT" if self.usable else "GENERIC_FALLBACK"

    def metadata(self) -> dict[str, object]:
        """Return compact QA metadata without duplicating source text."""

        return {
            "format_source": self.format_source,
            "section_status": self.section_status,
            "source_heading": self.source_heading,
            "source_locator": (
                self.source_locator.model_dump(mode="json")
                if self.source_locator is not None
                else None
            ),
            "confidence": self.confidence,
            "element_count": len(self.elements),
            "table_count": sum(element.type == "table" for element in self.elements),
            "heading_titles": [
                element.text
                for element in self.elements
                if element.type == "heading"
            ],
            "primary_heading_titles": _primary_outline_titles(self.elements),
            "boundary_reason": self.boundary_reason,
            "candidate_count": self.candidate_count,
            "boundary_locator": (
                self.boundary_locator.model_dump(mode="json")
                if self.boundary_locator is not None
                else None
            ),
        }


def _compact_text(value: str) -> str:
    """Collapse source line breaks for title classification only."""

    normalized = normalize_text(value)
    return re.sub(r"\s+", " ", normalized.replace("\n", " ")).strip(" \t:：。；;")


def _style_level(style_name: str | None) -> int | None:
    style = _compact_text(style_name or "")
    if not style:
        return None
    match = _STYLE_LEVEL_RE.search(style)
    if match:
        return int(match.group(1))
    if "heading" in style.lower() or "标题" in style:
        return 1
    return None


def _numbered_level(text: str) -> int | None:
    match = _ORDERED_RE.match(text)
    if not match:
        return None
    prefix = match.group("prefix")
    if _CHAPTER_RE.fullmatch(prefix):
        return 1 if prefix.endswith(("章", "篇", "部分")) else 2
    return 2


def _general_heading_level(text: str, style_name: str | None = None) -> int | None:
    compact = _compact_text(text)
    if not compact:
        return None
    numbered_level = _numbered_level(compact)
    if numbered_level is not None:
        return numbered_level
    styled_level = _style_level(style_name)
    if styled_level is not None:
        return styled_level
    # These are common standalone document titles.  They are safe only when
    # the complete normalized record is the title, never when the phrase is
    # merely embedded in a body paragraph.
    if compact in {"招标公告", "采购公告", "投标人须知前附表", "投标函"}:
        return 1
    return None


def _primary_outline_titles(elements: list[FormatElement]) -> list[str]:
    """Return the first source outline, excluding its repeated body headings.

    PDF extraction commonly contains a table of contents followed by the
    actual forms. Both are source content, but delivery QA needs a compact
    outline so every numbered body sentence is not treated as a chapter.
    """

    titles: list[str] = []
    seen_prefixes: set[str] = set()
    for element in elements:
        if element.type != "heading" or not element.text.strip():
            continue
        if not titles:
            titles.append(element.text)
            continue
        match = _OUTLINE_PREFIX_RE.match(_compact_text(element.text))
        if match is None:
            continue
        prefix = match.group("prefix")
        if prefix in seen_prefixes:
            break
        seen_prefixes.add(prefix)
        titles.append(element.text)
    return titles


def _format_title_match(
    text: str,
    *,
    style_name: str | None = None,
    source_type: SourceType | None = None,
) -> tuple[str, int, int] | None:
    """Return ``(title, level, score)`` only for a complete title record."""

    compact = _compact_text(text)
    if not compact:
        return None
    match = _FORMAT_TITLE_RE.fullmatch(compact)
    if match is None:
        return None

    style_level = _style_level(style_name)
    numbered_level = _numbered_level(compact)
    # A standalone exact phrase is allowed as a title record.  A phrase found
    # inside a longer sentence can never reach this point.
    level = numbered_level or style_level or 1
    score = 2
    if numbered_level is not None:
        score += 4
    if style_level is not None:
        score += 5
    if source_type == SourceType.PDF and numbered_level is None and style_level is None:
        # PDF has no style metadata.  Exact, standalone blocks are acceptable,
        # but receive less confidence than an explicit chapter title.
        score += 1
    return compact, level, score


def _element_text_and_style(element: DocumentElement) -> tuple[str, str | None, SourceType | None]:
    if isinstance(element, ParagraphElement):
        return element.paragraph.text, element.paragraph.style_name, SourceType.DOCX
    if isinstance(element, PdfBlockElement):
        return element.block.text, None, SourceType.PDF
    if isinstance(element, PdfTableElement):
        return "", None, SourceType.PDF
    return "", None, SourceType.DOCX


def _source_locator(element: DocumentElement) -> Locator | None:
    if isinstance(element, ParagraphElement):
        return element.paragraph.locator
    if isinstance(element, PdfBlockElement):
        return element.block.locator
    if isinstance(element, (TableElement, PdfTableElement)):
        for row in element.table.rows:
            for cell in row.cells:
                return cell.locator
    return None


def _table_text(element: TableElement) -> str:
    return "\n".join(
        " | ".join(cell.text for cell in row.cells).strip()
        for row in element.table.rows
        if any(cell.text.strip() for cell in row.cells)
    ).strip()


def _to_format_element(element: DocumentElement) -> FormatElement | None:
    if isinstance(element, (TableElement, PdfTableElement)):
        return FormatElement(
            type="table",
            text=_table_text(element),
            locator=_source_locator(element),
            table=element.table,
        )

    text, style_name, _source_type = _element_text_and_style(element)
    if not text.strip():
        return None
    level = _general_heading_level(text, style_name)
    if level is not None:
        return FormatElement(
            type="heading",
            text=text.strip(),
            locator=_source_locator(element),
            heading_level=level,
        )
    return FormatElement(
        type="paragraph",
        text=text.strip(),
        locator=_source_locator(element),
    )


def _pdf_block_belongs_to_table(
    element: DocumentElement,
    tables: Iterable[object],
) -> bool:
    """Avoid re-emitting PDF table text blocks as flattened paragraphs."""

    if not isinstance(element, PdfBlockElement):
        return False
    block_locator = element.block.locator
    block_bbox = element.block.bbox
    block_center = (
        (block_bbox[0] + block_bbox[2]) / 2.0,
        (block_bbox[1] + block_bbox[3]) / 2.0,
    )
    for table in tables:
        if getattr(table, "page", None) != block_locator.page:
            continue
        table_bbox = getattr(table, "bbox", None)
        if not table_bbox or len(table_bbox) != 4:
            continue
        if (
            table_bbox[0] <= block_center[0] <= table_bbox[2]
            and table_bbox[1] <= block_center[1] <= table_bbox[3]
        ):
            return True
    return False


def _boundary_is_suspicious(start_index: int, boundary_index: int, total: int) -> bool:
    """Flag a likely false-positive that would absorb a large document tail."""

    span = boundary_index - start_index
    return boundary_index == total and start_index < total * 0.5 and span > 120


def _has_structured_format_content(
    document: NormalizedDocument,
    start_index: int,
    boundary_index: int,
    start_level: int,
) -> bool:
    """Recognize a long but genuine format chapter by its ordered forms.

    A real format chapter may legitimately occupy most of a PDF, especially
    when it contains detailed schedules and blank forms.  Requiring several
    numbered form headings keeps the large-tail guard for isolated false
    positives while allowing a clearly structured chapter to run to EOF.
    """

    ordered_form_count = 0
    for element in document.elements[start_index:boundary_index]:
        text, style_name, _source_type = _element_text_and_style(element)
        level = _general_heading_level(text, style_name)
        if level is not None and level > start_level:
            ordered_form_count += 1
            if ordered_form_count >= 3:
                return True
    return False


def _pdf_visual_document_boundary(
    document: NormalizedDocument,
    element: DocumentElement,
    *,
    start_page: int,
) -> bool:
    """Recognize a new, cover-like PDF document when no numbered chapter exists.

    Some tender PDFs append a government contract sample immediately after
    the bid forms without emitting a ``第九章`` heading.  A large centered
    title on a fresh page, accompanied by contract/sample wording, is strong
    boundary evidence; ordinary body mentions are not.  This deliberately
    remains a conservative PDF-only heuristic and is surfaced in
    ``boundary_reason`` for QA.
    """

    if not isinstance(element, PdfBlockElement):
        return False
    block = element.block
    if block.locator.page <= start_page:
        return False
    page = next((item for item in document.pages if item.page_number == block.locator.page), None)
    if page is None:
        return False
    if block.bbox[1] > 0.40 * max(1.0, page.height):
        return False
    title = _compact_text(block.text)
    if not title or len(title) > 80:
        return False
    page_center = page.width / 2.0
    block_center = (block.bbox[0] + block.bbox[2]) / 2.0
    centered = abs(block_center - page_center) <= max(18.0, page.width * 0.16)
    max_font_size = max(
        (span.font_size for line in block.lines for span in line.spans),
        default=0.0,
    )
    strong_title = max_font_size >= 24.0 and centered
    title_keyword = bool(re.search(r"合同|协议书|示范文本|使用说明", title))
    if not (strong_title and title_keyword):
        return False
    # Require a companion sample/document marker on the same page or the
    # immediately following page.  This avoids cutting at a single oversized
    # form heading.
    companion = any(
        candidate_text and re.search(r"示范文本|合同", candidate_text)
        for candidate in page.blocks
        for candidate_text in [_compact_text(candidate.text)]
    )
    return companion


def extract_bid_format(document: NormalizedDocument) -> BidFormatTemplate:
    """Find and normalize a source format section from a normalized document.

    Matching is restricted to complete title-like records.  In particular, a
    body paragraph containing ``投标文件格式`` does not start extraction.
    """

    if not isinstance(document, NormalizedDocument):
        raise TypeError("extract_bid_format requires a NormalizedDocument instance")
    if document.status.value != "PARSED":
        return BidFormatTemplate(
            section_status=FORMAT_SECTION_NOT_FOUND,
            boundary_reason=f"Source document is not PARSED: {document.status.value}.",
        )

    candidates: list[tuple[int, int, int, str, int]] = []
    for index, element in enumerate(document.elements):
        text, style_name, source_type = _element_text_and_style(element)
        match = _format_title_match(
            text,
            style_name=style_name,
            source_type=source_type,
        )
        if match is None:
            continue
        title, level, score = match
        candidates.append((score, -index, index, title, level))

    if not candidates:
        return BidFormatTemplate(
            section_status=FORMAT_SECTION_NOT_FOUND,
            boundary_reason="No complete title-type source format heading was found.",
        )

    # Prefer heading-styled/chapter-qualified matches, then preserve source
    # order for equally strong matches.
    score, _negative_index, start_index, source_heading, start_level = max(candidates)
    start_locator = _source_locator(document.elements[start_index])
    start_page = getattr(start_locator, "page", None)
    if start_page is None:
        start_page = 1
    boundary_index = len(document.elements)
    for index in range(start_index + 1, len(document.elements)):
        element = document.elements[index]
        text, style_name, _source_type = _element_text_and_style(element)
        level = _general_heading_level(text, style_name)
        if level is not None and level <= start_level:
            boundary_index = index
            break
        if _pdf_visual_document_boundary(document, element, start_page=start_page):
            boundary_index = index
            break

    boundary_locator = (
        _source_locator(document.elements[boundary_index])
        if boundary_index < len(document.elements)
        else None
    )

    if boundary_index < len(document.elements):
        boundary_element = document.elements[boundary_index]
        if _pdf_visual_document_boundary(document, boundary_element, start_page=start_page):
            boundary_reason = "Stopped at a visually distinct cover-like source document boundary."
        else:
            boundary_reason = "Stopped at the next same-level or higher-level heading."
    else:
        boundary_reason = "Section extends to the end of the normalized document."
    if _boundary_is_suspicious(start_index, boundary_index, len(document.elements)) and not _has_structured_format_content(
        document,
        start_index,
        boundary_index,
        start_level,
    ):
        return BidFormatTemplate(
            source_heading=source_heading,
            source_locator=_source_locator(document.elements[start_index]),
            confidence=min(0.45, 0.70 + score / 100.0),
            section_status=FORMAT_SECTION_NEEDS_REVIEW,
            boundary_reason=(
                "No reliable later heading was found before a large document tail; "
                "the source section was not copied."
            ),
            candidate_count=len(candidates),
            boundary_locator=boundary_locator,
        )

    elements: list[FormatElement] = []
    for element in document.elements[start_index:boundary_index]:
        if _pdf_block_belongs_to_table(element, document.tables):
            continue
        normalized = _to_format_element(element)
        if normalized is not None:
            elements.append(normalized)

    if not elements:
        return BidFormatTemplate(
            source_heading=source_heading,
            source_locator=_source_locator(document.elements[start_index]),
            confidence=0.0,
            section_status=FORMAT_SECTION_NEEDS_REVIEW,
            boundary_reason="The matched source format heading had no copyable elements.",
            candidate_count=len(candidates),
            boundary_locator=boundary_locator,
        )

    confidence = min(0.99, 0.70 + score / 30.0)
    return BidFormatTemplate(
        source_heading=source_heading,
        source_locator=_source_locator(document.elements[start_index]),
        confidence=confidence,
        elements=elements,
        section_status=FORMAT_SECTION_FOUND,
        boundary_reason=boundary_reason,
        candidate_count=len(candidates),
        boundary_locator=boundary_locator,
    )


def extract_format_template(document: NormalizedDocument) -> BidFormatTemplate:
    """Backward-friendly alias for callers that use the generic name."""

    return extract_bid_format(document)


__all__ = [
    "BidFormatTemplate",
    "FORMAT_HEADING_CANDIDATES",
    "FORMAT_SECTION_FOUND",
    "FORMAT_SECTION_NEEDS_REVIEW",
    "FORMAT_SECTION_NOT_FOUND",
    "FormatElement",
    "extract_bid_format",
    "extract_format_template",
]
