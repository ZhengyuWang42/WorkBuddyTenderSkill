"""Document normalization for one PDF or DOCX input.

This module preserves source text, structure, order, and locators. It does not
assign text to ProjectFacts fields and does not call an LLM.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

try:  # Prefer the current PyMuPDF import name; retain compatibility with older releases.
    import pymupdf as fitz
except ImportError:  # pragma: no cover - exercised only with older PyMuPDF versions.
    import fitz  # type: ignore[no-redef]

from .document_models import (
    DocumentBlock,
    DocumentCell,
    DocumentElement,
    DocumentPage,
    DocumentParagraph,
    DocumentRow,
    DocumentStatus,
    DocumentTable,
    NormalizedDocument,
    ParagraphElement,
    PdfBlockElement,
    PdfTable,
    PdfTableCell,
    PdfTableElement,
    PdfTableRow,
    PdfTextLine,
    PdfCharacterGeometry,
    PdfTextSpan,
    PdfVectorLine,
    TableElement,
)
from .models import (
    DocxParagraphLocator,
    DocxTableLocator,
    PdfLocator,
    PdfTableLocator,
    SourceType,
)


EXIT_PARSED = 0
EXIT_UNSUPPORTED_FORMAT = 2
EXIT_PARSE_ERROR = 3
EXIT_OCR_REQUIRED = 4

OCR_WARNING = "PDF appears image-based or has insufficient extractable text."
PDF_MIN_TEXT_CHARS_PER_PAGE = 20
PDF_MIN_TEXT_PAGE_RATIO = 0.5
PDF_MIN_AVERAGE_CHARS_PER_PAGE = 20

_SUPPORTED_SUFFIXES = {
    ".pdf": SourceType.PDF,
    ".docx": SourceType.DOCX,
}


def normalize_text(value: str) -> str:
    """Normalize whitespace and controls without rewriting source wording."""

    value = value.replace("\r\n", "\n").replace("\r", "\n")
    safe_chars = []
    for char in value:
        if char in {"\n", "\t"} or (ord(char) >= 32 and char != "\x7f"):
            safe_chars.append(char)

    normalized_lines = []
    for line in "".join(safe_chars).split("\n"):
        normalized_lines.append(re.sub(r"[ \t]+", " ", line).strip())

    while normalized_lines and normalized_lines[0] == "":
        normalized_lines.pop(0)
    while normalized_lines and normalized_lines[-1] == "":
        normalized_lines.pop()
    return "\n".join(normalized_lines)


def raw_display_text(value: str) -> str:
    # Preserve printable source characters and horizontal whitespace for rendering.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    safe = "".join(char for char in value if char in {"\n", "\t"} or (ord(char) >= 32 and char != "\x7f"))
    return safe.strip("\n")


def _line_text(value: str) -> str:
    """Represent embedded newlines inside one stable lines-view record."""

    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\n").replace("\t", " ")


def _source_type_for_path(path: Path) -> SourceType | None:
    return _SUPPORTED_SUFFIXES.get(path.suffix.lower())


def _source_file_name(path: Path) -> str:
    return path.name or str(path)


def _error_document(
    path: Path,
    *,
    source_type: SourceType | None,
    status: DocumentStatus,
    warning: str,
) -> NormalizedDocument:
    return NormalizedDocument(
        source_file=_source_file_name(path),
        source_type=source_type,
        status=status,
        page_count=0,
        text_length=0,
        warnings=[warning],
    )


def _safe_bbox(raw_block: tuple[object, ...]) -> tuple[float, float, float, float]:
    values = []
    for value in raw_block[:4]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        values.append(number if math.isfinite(number) else 0.0)
    while len(values) < 4:
        values.append(0.0)
    return tuple(values[:4])  # type: ignore[return-value]


def _pdf_block_type(raw_type: object) -> str:
    names = {
        0: "text",
        1: "image",
        2: "vector",
        3: "xref",
    }
    try:
        numeric_type = int(raw_type)
    except (TypeError, ValueError):
        return "unknown"
    return names.get(numeric_type, f"unknown:{numeric_type}")


def _pdf_text_span(raw_span: dict[str, object], source_order: int) -> PdfTextSpan | None:
    raw_text = raw_span.get("text", "")
    text = raw_text if isinstance(raw_text, str) else str(raw_text or "")
    raw_chars = raw_span.get("chars", [])
    if not text and isinstance(raw_chars, list):
        pieces = []
        previous = None
        try:
            span_size = float(raw_span.get("size", 0.0) or 0.0)
        except (TypeError, ValueError):
            span_size = 0.0
        for raw_char in raw_chars:
            if not isinstance(raw_char, dict):
                continue
            char = raw_char.get("c", "")
            char = char if isinstance(char, str) else str(char or "")
            bbox = raw_char.get("bbox")
            if previous is not None and isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                previous_char, previous_bbox = previous
                gap = float(bbox[0]) - float(previous_bbox[2])
                ascii_boundary = (
                    (previous_char.isascii() and previous_char.isalnum())
                    or (char.isascii() and char.isalnum())
                )
                if ascii_boundary and not previous_char.isspace() and not char.isspace() and gap >= max(2.0, span_size * .22):
                    pieces.append(" ")
            pieces.append(char)
            if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                previous = (char, bbox)
        text = "".join(pieces)
    if not text:
        return None
    raw_bbox = raw_span.get("bbox")
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) < 4:
        return None
    try:
        flags = int(raw_span.get("flags", 0) or 0)
    except (TypeError, ValueError):
        flags = 0
    try:
        font_size = float(raw_span.get("size", 0.0) or 0.0)
    except (TypeError, ValueError):
        font_size = 0.0
    raw_font = raw_span.get("font", "")
    font_name = raw_font if isinstance(raw_font, str) else str(raw_font or "")
    raw_color = raw_span.get("color")
    try:
        color = int(raw_color) if raw_color is not None else None
    except (TypeError, ValueError):
        color = None
    # Exact per-character geometry, captured before it is discarded.  These
    # boxes are PyMuPDF's own records, never a subdivision of the run bbox.
    characters: list[PdfCharacterGeometry] = []
    if isinstance(raw_chars, list):
        for char_index, raw_char in enumerate(raw_chars):
            if not isinstance(raw_char, dict):
                continue
            raw_char_text = raw_char.get("c", "")
            raw_char_text = (
                raw_char_text if isinstance(raw_char_text, str) else str(raw_char_text or "")
            )
            char_bbox = raw_char.get("bbox")
            if not isinstance(char_bbox, (list, tuple)) or len(char_bbox) < 4:
                continue
            raw_origin = raw_char.get("origin")
            origin = None
            if isinstance(raw_origin, (list, tuple)) and len(raw_origin) >= 2:
                try:
                    origin = (round(float(raw_origin[0]), 2), round(float(raw_origin[1]), 2))
                except (TypeError, ValueError):
                    origin = None
            characters.append(
                PdfCharacterGeometry(
                    index=char_index,
                    character=raw_char_text,
                    # Geometry is stored at 0.01 pt, far finer than any
                    # boundary tolerance, and keeps the persisted normalized
                    # document from carrying PyMuPDF's full float expansion.
                    bbox=tuple(
                        round(float(value), 2)
                        for value in _safe_bbox(tuple(char_bbox))
                    ),
                    origin=origin,
                    evidence_kind="EXACT_PDF_CHAR",
                )
            )
    return PdfTextSpan(
        text=text,
        bbox=_safe_bbox(tuple(raw_bbox)),
        font_name=font_name,
        font_size=font_size,
        # PyMuPDF uses bit 16 for bold and bit 2 for italic in its text flags.
        bold=bool(flags & 16),
        italic=bool(flags & 2),
        underline=False,
        color=color,
        flags=flags,
        source_order=source_order,
        characters=characters,
    )


def _pdf_text_lines(raw_block: dict[str, object]) -> list[PdfTextLine]:
    lines: list[PdfTextLine] = []
    raw_lines = raw_block.get("lines", [])
    if not isinstance(raw_lines, list):
        return lines
    span_order = 0
    for line_index, raw_line in enumerate(raw_lines):
        if not isinstance(raw_line, dict):
            continue
        raw_spans = raw_line.get("spans", [])
        spans: list[PdfTextSpan] = []
        if isinstance(raw_spans, list):
            for raw_span in raw_spans:
                if not isinstance(raw_span, dict):
                    continue
                span = _pdf_text_span(raw_span, span_order)
                span_order += 1
                if span is not None:
                    spans.append(span)
        if not spans:
            continue
        raw_bbox = raw_line.get("bbox")
        if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) < 4:
            x0 = min(span.bbox[0] for span in spans)
            y0 = min(span.bbox[1] for span in spans)
            x1 = max(span.bbox[2] for span in spans)
            y1 = max(span.bbox[3] for span in spans)
            bbox = (x0, y0, x1, y1)
        else:
            bbox = _safe_bbox(tuple(raw_bbox))
        lines.append(
            PdfTextLine(
                text="".join(span.text for span in spans),
                bbox=bbox,
                spans=spans,
                source_order=line_index,
            )
        )
    return lines


def _span_center(span: PdfTextSpan) -> tuple[float, float]:
    return (
        (span.bbox[0] + span.bbox[2]) / 2.0,
        (span.bbox[1] + span.bbox[3]) / 2.0,
    )


def _line_center(line: PdfTextLine) -> tuple[float, float]:
    return (
        (line.bbox[0] + line.bbox[2]) / 2.0,
        (line.bbox[1] + line.bbox[3]) / 2.0,
    )


def _pdf_vector_lines(page: object) -> list[PdfVectorLine]:
    """Extract only simple ruled lines; ordinary table lines are filtered later."""

    try:
        drawings = page.get_drawings()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return []
    lines: list[PdfVectorLine] = []
    for drawing in drawings or []:
        try:
            width = float(drawing.get("width", 0.5) or 0.5)
        except (TypeError, ValueError):
            width = 0.5
        raw_color = drawing.get("color")
        color: int | None = None
        if isinstance(raw_color, (tuple, list)) and len(raw_color) >= 3:
            try:
                rgb = [max(0, min(255, int(round(float(value) * 255)))) for value in raw_color[:3]]
                color = (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]
            except (TypeError, ValueError):
                color = None
        for item in drawing.get("items", []) or []:
            if not isinstance(item, (tuple, list)) or len(item) < 2:
                continue
            if item[0] == "l" and len(item) >= 3:
                start, end = item[1], item[2]
                try:
                    x0, y0 = float(start.x), float(start.y)
                    x1, y1 = float(end.x), float(end.y)
                except (AttributeError, TypeError, ValueError):
                    continue
            elif item[0] == "re":
                rectangle = item[1]
                try:
                    x0 = float(rectangle.x0)
                    y0 = float(rectangle.y0)
                    x1 = float(rectangle.x1)
                    y1 = float(rectangle.y1)
                except (AttributeError, TypeError, ValueError):
                    try:
                        x0, y0, x1, y1 = (float(value) for value in rectangle[:4])
                    except (TypeError, ValueError, IndexError):
                        continue
            else:
                continue
            if abs(y1 - y0) <= 1.5:
                orientation = "horizontal"
            elif abs(x1 - x0) <= 1.5:
                orientation = "vertical"
            else:
                continue
            lines.append(
                PdfVectorLine(
                    bbox=(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)),
                    width=max(0.1, width),
                    color=color,
                    orientation=orientation,
                )
            )
    return lines


def _pdf_unmodeled_artwork_count(
    page: object,
    table_bboxes: Iterable[tuple[float, float, float, float]],
) -> int:
    """Count non-text artwork outside detected tables for source QA.

    This intentionally reports only sizeable image fills. PDF text outlines,
    tiny scan fragments, underlines, and table border primitives are not
    artwork gaps: text remains editable and table geometry is reconstructed by
    the table model.
    """

    try:
        bbox_log = page.get_bboxlog()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return 0
    tables = list(table_bboxes)
    count = 0
    for entry in bbox_log or []:
        if not isinstance(entry, (tuple, list)) or len(entry) < 2:
            continue
        kind = str(entry[0])
        if kind != "fill-image":
            continue
        try:
            bbox = _safe_bbox(tuple(entry[1]))
        except TypeError:
            continue
        center_x = (bbox[0] + bbox[2]) / 2.0
        center_y = (bbox[1] + bbox[3]) / 2.0
        if (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) < 1000.0:
            continue
        if any(
            table[0] - 1.0 <= center_x <= table[2] + 1.0
            and table[1] - 1.0 <= center_y <= table[3] + 1.0
            for table in tables
        ):
            continue
        count += 1
    return count


def _pdf_lines_for_block(
    block_bbox: tuple[float, float, float, float],
    dict_lines: list[tuple[tuple[float, float, float, float], list[PdfTextLine]]],
    block_text: str = "",
) -> list[PdfTextLine]:
    """Attach direct PDF lines to a ``get_text('blocks')`` block by geometry.

    ``page.get_text('dict')`` is not guaranteed to have the same block array
    as ``page.get_text('blocks')``: embedded glyph images and other low-level
    objects can add dozens of dict entries.  Index-based pairing therefore
    silently assigns typography from one source paragraph to another.  The
    block API remains the text-preservation authority; dict lines are matched
    to it by their line centers instead.
    """

    x0, y0, x1, y1 = block_bbox
    block_text_key = re.sub(r"\s+", "", block_text or "")
    selected: list[PdfTextLine] = []
    for dict_bbox, lines in dict_lines:
        for line in lines:
            center_x, center_y = _line_center(line)
            # A repeated diagonal watermark may have a very large bbox whose
            # center happens to fall inside an ordinary body block.  Require
            # the whole direct line rectangle to fit the block as well as its
            # center; this keeps low-level span metadata from contaminating a
            # neighboring paragraph.
            line_x0, line_y0, line_x1, line_y1 = line.bbox
            line_inside_block = (
                line_x0 >= x0 - 1.5
                and line_x1 <= x1 + 1.5
                and line_y0 >= y0 - 1.5
                and line_y1 <= y1 + 1.5
            )
            line_text_key = re.sub(r"\s+", "", line.text or "")
            # A large watermark block can geometrically contain ordinary body
            # lines even though its text payload is only the watermark. Keep
            # direct typography only when the line text belongs to the block
            # text; this is deliberately conservative for ambiguous overlap.
            text_belongs_to_block = (
                not block_text_key
                or not line_text_key
                or line_text_key in block_text_key
            )
            if (
                line_inside_block
                and x0 - 1.5 <= center_x <= x1 + 1.5
                and y0 - 1.5 <= center_y <= y1 + 1.5
                and text_belongs_to_block
            ):
                selected.append(line)
    selected.sort(key=lambda line: (line.bbox[1], line.bbox[0], line.source_order))
    return selected


def _parse_pdf_table(
    table: object,
    page_number: int,
    table_index: int,
    page_spans: list[PdfTextSpan] | None = None,
) -> PdfTable | None:
    """Convert one PyMuPDF Table into the small normalized table contract."""

    extract = getattr(table, "extract", None)
    if not callable(extract):
        return None
    raw_rows = extract() or []
    rows_as_lists = [list(row or []) for row in raw_rows]
    column_count = max(
        int(getattr(table, "col_count", 0) or 0),
        max((len(row) for row in rows_as_lists), default=0),
    )
    if not rows_as_lists or column_count <= 0:
        return None

    raw_cells = list(getattr(table, "cells", []) or [])
    raw_bboxes: list[tuple[float, float, float, float] | None] = []
    for raw_cell in raw_cells:
        if raw_cell is None:
            raw_bboxes.append(None)
        else:
            try:
                raw_bboxes.append(_safe_bbox(tuple(raw_cell)))
            except TypeError:
                raw_bboxes.append(None)

    # PyMuPDF's ``Table.cells`` is column-major for some tables while
    # ``Table.extract()`` is row-major.  Pairing the two arrays by flat index
    # silently moved every value into another row/column.  Recover the grid
    # from the cell rectangles instead; this also gives us a deterministic
    # basis for horizontal/vertical merges and geometry metadata.
    x_edges = sorted(
        {
            round(value, 2)
            for bbox in raw_bboxes
            if bbox is not None
            for value in (bbox[0], bbox[2])
        }
    )
    y_edges = sorted(
        {
            round(value, 2)
            for bbox in raw_bboxes
            if bbox is not None
            for value in (bbox[1], bbox[3])
        }
    )

    def edge_index(value: float, edges: list[float]) -> int | None:
        if not edges:
            return None
        distances = [(abs(edge - value), index) for index, edge in enumerate(edges)]
        distance, index = min(distances)
        return index if distance <= 1.0 else None

    grid_bboxes: dict[tuple[int, int], tuple[float, float, float, float]] = {}
    merge_ranges: set[tuple[int, int, int, int]] = set()
    for bbox in raw_bboxes:
        if bbox is None:
            continue
        x_start = edge_index(bbox[0], x_edges)
        x_end = edge_index(bbox[2], x_edges)
        y_start = edge_index(bbox[1], y_edges)
        y_end = edge_index(bbox[3], y_edges)
        if None in {x_start, x_end, y_start, y_end}:
            continue
        assert x_start is not None and x_end is not None
        assert y_start is not None and y_end is not None
        row_start, row_end = y_start, y_end - 1
        column_start, column_end = x_start, x_end - 1
        if row_start < 0 or column_start < 0:
            continue
        if row_end >= len(rows_as_lists) or column_end >= column_count:
            continue
        for row_index in range(row_start, row_end + 1):
            for column_index in range(column_start, column_end + 1):
                # Prefer the smallest rectangle if a malformed PDF exposes
                # overlapping geometry; ordinary tables have one owner.
                current = grid_bboxes.get((row_index, column_index))
                if current is None or (
                    (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                    < (current[2] - current[0]) * (current[3] - current[1])
                ):
                    grid_bboxes[(row_index, column_index)] = bbox
        if row_end > row_start or column_end > column_start:
            merge_ranges.add((row_start, row_end, column_start, column_end))
    rows: list[PdfTableRow] = []
    for row_index, raw_row in enumerate(rows_as_lists):
        cells: list[PdfTableCell] = []
        for column_index in range(column_count):
            raw_value = raw_row[column_index] if column_index < len(raw_row) else ""
            value = normalize_text(raw_value if isinstance(raw_value, str) else str(raw_value or ""))
            bbox = grid_bboxes.get((row_index, column_index))
            cell_spans: list[PdfTextSpan] = []
            if bbox is not None and page_spans:
                for span in page_spans:
                    center_x, center_y = _span_center(span)
                    if bbox[0] - 1.0 <= center_x <= bbox[2] + 1.0 and bbox[1] - 1.0 <= center_y <= bbox[3] + 1.0:
                        cell_spans.append(span)
            cells.append(
                PdfTableCell(
                    row_index=row_index,
                    column_index=column_index,
                    text=value,
                    bbox=bbox,
                    locator=PdfTableLocator(
                        page=page_number,
                        table_index=table_index,
                        row_index=row_index,
                        column_index=column_index,
                    ),
                    spans=cell_spans,
                )
            )
        rows.append(PdfTableRow(row_index=row_index, cells=cells))

    raw_table_bbox = getattr(table, "bbox", (0.0, 0.0, 0.0, 0.0))
    table_bbox = _safe_bbox(tuple(raw_table_bbox))
    row_heights = [
        y_edges[index + 1] - y_edges[index]
        if index + 1 < len(y_edges)
        else 0.0
        for index in range(len(rows_as_lists))
    ]
    column_widths = [
        x_edges[index + 1] - x_edges[index]
        if index + 1 < len(x_edges)
        else 0.0
        for index in range(column_count)
    ]

    return PdfTable(
        page=page_number,
        table_index=table_index,
        bbox=table_bbox,
        rows=rows,
        column_widths=column_widths,
        row_heights=row_heights,
        merged_cells=sorted(merge_ranges),
    )


def _parse_pdf(path: Path) -> NormalizedDocument:
    pdf = fitz.open(str(path))
    try:
        pages: list[DocumentPage] = []
        elements: list[DocumentElement] = []
        tables: list[PdfTable] = []

        for page_zero_index, page in enumerate(pdf):
            page_number = page_zero_index + 1
            blocks: list[DocumentBlock] = []
            raw_blocks = page.get_text("blocks")
            raw_dict = page.get_text("rawdict")
            raw_dict_blocks = raw_dict.get("blocks", []) if isinstance(raw_dict, dict) else []
            page_spans: list[PdfTextSpan] = []
            dict_lines: list[tuple[tuple[float, float, float, float], list[PdfTextLine]]] = []
            if isinstance(raw_dict_blocks, list):
                for raw_dict_block in raw_dict_blocks:
                    if not isinstance(raw_dict_block, dict):
                        continue
                    lines_for_block = _pdf_text_lines(raw_dict_block)
                    raw_dict_bbox = raw_dict_block.get("bbox")
                    if isinstance(raw_dict_bbox, (list, tuple)) and len(raw_dict_bbox) >= 4:
                        dict_lines.append((_safe_bbox(tuple(raw_dict_bbox)), lines_for_block))
                    page_spans.extend(
                        span for line in lines_for_block for span in line.spans
                    )

            for block_index, raw_block in enumerate(raw_blocks):
                raw_text = raw_block[4] if len(raw_block) > 4 else ""
                raw_value = raw_text if isinstance(raw_text, str) else str(raw_text)
                text = normalize_text(raw_value)
                raw_type = raw_block[6] if len(raw_block) > 6 else None
                block = DocumentBlock(
                    block_index=block_index,
                    text=text,
                    raw_display_text=raw_display_text(raw_value),
                    semantic_normalized_text=text,
                    bbox=_safe_bbox(raw_block),
                    block_type=_pdf_block_type(raw_type),
                    locator=PdfLocator(page=page_number, block_index=block_index),
                    lines=_pdf_lines_for_block(
                        _safe_bbox(raw_block),
                        dict_lines,
                        block_text=text,
                    ),
                )
                blocks.append(block)

            page_elements: list[tuple[float, int, DocumentElement]] = [
                (
                    block.bbox[1],
                    index,
                    PdfBlockElement(page_number=page_number, block=block),
                )
                for index, block in enumerate(blocks)
            ]
            try:
                table_finder = page.find_tables()
                raw_tables = list(getattr(table_finder, "tables", []) or [])
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                raw_tables = []
                # A PDF without a table detector or with an unsupported page
                # remains a valid text document; retain the fact for QA/debugging.
                if str(exc):
                    # Keep the warning local to this document instead of
                    # changing the parser status.
                    pass

            for raw_table_index, raw_table in enumerate(raw_tables):
                normalized_table = _parse_pdf_table(
                    raw_table,
                    page_number,
                    raw_table_index,
                    page_spans,
                )
                if normalized_table is None:
                    continue
                tables.append(normalized_table)
                page_elements.append(
                    (
                        normalized_table.bbox[1],
                        len(blocks) + raw_table_index,
                        PdfTableElement(table=normalized_table),
                    )
                )

            page_tables = [table for table in tables if table.page == page_number]

            page_elements.sort(key=lambda item: (item[0], item[1]))
            elements.extend(item[2] for item in page_elements)

            pages.append(
                DocumentPage(
                    page_number=page_number,
                    blocks=blocks,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    vector_lines=_pdf_vector_lines(page),
                    unmodeled_artwork_count=_pdf_unmodeled_artwork_count(
                        page,
                        [table.bbox for table in page_tables],
                    ),
                )
            )

        page_count = len(pages)
        text_length = sum(len(block.text) for page in pages for block in page.blocks)
        text_page_count = sum(
            1
            for page in pages
            if sum(len(block.text) for block in page.blocks) >= PDF_MIN_TEXT_CHARS_PER_PAGE
        )
        average_chars_per_page = text_length / page_count if page_count else 0.0

        if page_count == 0:
            return _error_document(
                path,
                source_type=SourceType.PDF,
                status=DocumentStatus.PARSE_ERROR,
                warning="PDF contains no pages.",
            )

        warnings: list[str] = []
        text_page_ratio = text_page_count / page_count
        ocr_required = (
            text_length == 0
            or text_length < PDF_MIN_TEXT_CHARS_PER_PAGE
            or (
                page_count >= 2
                and (
                    text_page_ratio < PDF_MIN_TEXT_PAGE_RATIO
                    or average_chars_per_page < PDF_MIN_AVERAGE_CHARS_PER_PAGE
                )
            )
        )
        status = DocumentStatus.PARSED
        if ocr_required:
            status = DocumentStatus.OCR_REQUIRED
            warnings.append(OCR_WARNING)

        return NormalizedDocument(
            source_file=_source_file_name(path),
            source_type=SourceType.PDF,
            status=status,
            page_count=page_count,
            text_length=text_length,
            pages=pages,
            tables=tables,
            elements=elements,
            warnings=warnings,
        )
    finally:
        pdf.close()


def _paragraph_style_name(paragraph: Paragraph) -> str | None:
    try:
        return paragraph.style.name if paragraph.style is not None else None
    except (AttributeError, KeyError):
        return None


def _cell_text(cell: object) -> str:
    paragraphs = getattr(cell, "paragraphs", [])
    paragraph_texts = [normalize_text(paragraph.text) for paragraph in paragraphs]
    return "\n".join(paragraph_texts)


def _parse_table(table: Table, table_index: int, warnings: list[str]) -> DocumentTable:
    rows: list[DocumentRow] = []
    for row_index, row in enumerate(table.rows):
        cells: list[DocumentCell] = []
        for cell_index, cell in enumerate(row.cells):
            if getattr(cell, "tables", []):
                warnings.append(
                    f"Nested DOCX table at table={table_index}, row={row_index}, "
                    f"cell={cell_index} is not separately normalized."
                )
            cells.append(
                DocumentCell(
                    cell_index=cell_index,
                    text=_cell_text(cell),
                    locator=DocxTableLocator(
                        table_index=table_index,
                        row_index=row_index,
                        cell_index=cell_index,
                    ),
                )
            )
        rows.append(DocumentRow(row_index=row_index, cells=cells))
    return DocumentTable(table_index=table_index, rows=rows)


def _parse_docx(path: Path) -> NormalizedDocument:
    document = DocxDocument(str(path))
    elements: list[DocumentElement] = []
    warnings: list[str] = []
    paragraph_index = 0
    table_index = 0

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            normalized_paragraph = DocumentParagraph(
                paragraph_index=paragraph_index,
                text=normalize_text(paragraph.text),
                style_name=_paragraph_style_name(paragraph),
                locator=DocxParagraphLocator(paragraph_index=paragraph_index),
            )
            elements.append(ParagraphElement(paragraph=normalized_paragraph))
            paragraph_index += 1
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            normalized_table = _parse_table(table, table_index, warnings)
            elements.append(TableElement(table=normalized_table))
            table_index += 1

    text_length = 0
    for element in elements:
        if isinstance(element, ParagraphElement):
            text_length += len(element.paragraph.text)
        elif isinstance(element, TableElement):
            text_length += sum(
                len(cell.text)
                for row in element.table.rows
                for cell in row.cells
            )

    return NormalizedDocument(
        source_file=_source_file_name(path),
        source_type=SourceType.DOCX,
        status=DocumentStatus.PARSED,
        page_count=0,
        text_length=text_length,
        pages=[],
        elements=elements,
        warnings=warnings,
    )


def parse_document(input_file: str | Path) -> NormalizedDocument:
    """Parse one supported document into a status-bearing normalized model."""

    path = Path(input_file)
    source_type = _source_type_for_path(path)
    if source_type is None:
        return _error_document(
            path,
            source_type=None,
            status=DocumentStatus.UNSUPPORTED_FORMAT,
            warning=f"Unsupported document format: {path.suffix or '<none>'}.",
        )
    if not path.is_file():
        return _error_document(
            path,
            source_type=source_type,
            status=DocumentStatus.PARSE_ERROR,
            warning="Input file does not exist or is not a regular file.",
        )

    try:
        if source_type == SourceType.PDF:
            return _parse_pdf(path)
        return _parse_docx(path)
    except Exception as exc:
        return _error_document(
            path,
            source_type=source_type,
            status=DocumentStatus.PARSE_ERROR,
            warning=f"{source_type.value} parse failed: {exc.__class__.__name__}: {exc}",
        )


def render_lines(document: NormalizedDocument) -> str:
    """Render one stable, source-locator-prefixed record per source item."""

    lines: list[str] = []
    if document.source_type == SourceType.PDF:
        for page in document.pages:
            for block in page.blocks:
                if block.text:
                    lines.append(
                        f"[PDF:P:{page.page_number}:B:{block.block_index}] "
                        f"{_line_text(block.text)}"
                    )
            for table in document.tables:
                if table.page != page.page_number:
                    continue
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text:
                            lines.append(
                                f"[PDF:T:{table.page}:T:{table.table_index}:"
                                f"R:{cell.row_index}:C:{cell.column_index}] "
                                f"{_line_text(cell.text)}"
                            )
        return "\n".join(lines) + ("\n" if lines else "")

    for element in document.elements:
        if isinstance(element, ParagraphElement):
            paragraph = element.paragraph
            if paragraph.text:
                lines.append(
                    f"[DOCX:P:{paragraph.paragraph_index}] {_line_text(paragraph.text)}"
                )
        elif isinstance(element, TableElement):
            for row in element.table.rows:
                for cell in row.cells:
                    lines.append(
                        f"[DOCX:T:{element.table.table_index}:R:{row.row_index}:C:{cell.cell_index}] "
                        f"{_line_text(cell.text)}"
                    )
    return "\n".join(lines) + ("\n" if lines else "")


def write_normalized_outputs(
    document: NormalizedDocument,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Write the two normalization artifacts and return their paths."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "normalized_document.json"
    lines_path = output_path / "document.lines.txt"

    payload = document.model_dump(mode="json")
    # Serialized compactly, without pretty-print indentation: the field set and
    # every value are unchanged, so this is a pure representation saving.  Note
    # that ``exclude_defaults`` must NOT be used here - it strips the ``type``
    # discriminator from ``elements`` members whose tag equals the field
    # default, and the document then fails to reload.
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with lines_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_lines(document))
    return json_path, lines_path


def exit_code_for_status(status: DocumentStatus) -> int:
    return {
        DocumentStatus.PARSED: EXIT_PARSED,
        DocumentStatus.UNSUPPORTED_FORMAT: EXIT_UNSUPPORTED_FORMAT,
        DocumentStatus.PARSE_ERROR: EXIT_PARSE_ERROR,
        DocumentStatus.OCR_REQUIRED: EXIT_OCR_REQUIRED,
    }[status]


__all__ = [
    "EXIT_OCR_REQUIRED",
    "EXIT_PARSED",
    "EXIT_PARSE_ERROR",
    "EXIT_UNSUPPORTED_FORMAT",
    "OCR_WARNING",
    "exit_code_for_status",
    "normalize_text",
    "parse_document",
    "render_lines",
    "write_normalized_outputs",
]
