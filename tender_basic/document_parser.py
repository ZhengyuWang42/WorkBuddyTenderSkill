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
    TableElement,
)
from .models import DocxParagraphLocator, DocxTableLocator, PdfLocator, SourceType


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


def _parse_pdf(path: Path) -> NormalizedDocument:
    pdf = fitz.open(str(path))
    try:
        pages: list[DocumentPage] = []
        elements: list[DocumentElement] = []

        for page_zero_index, page in enumerate(pdf):
            page_number = page_zero_index + 1
            blocks: list[DocumentBlock] = []
            raw_blocks = page.get_text("blocks")

            for block_index, raw_block in enumerate(raw_blocks):
                raw_text = raw_block[4] if len(raw_block) > 4 else ""
                text = normalize_text(raw_text if isinstance(raw_text, str) else str(raw_text))
                raw_type = raw_block[6] if len(raw_block) > 6 else None
                block = DocumentBlock(
                    block_index=block_index,
                    text=text,
                    bbox=_safe_bbox(raw_block),
                    block_type=_pdf_block_type(raw_type),
                    locator=PdfLocator(page=page_number, block_index=block_index),
                )
                blocks.append(block)
                elements.append(PdfBlockElement(page_number=page_number, block=block))

            pages.append(DocumentPage(page_number=page_number, blocks=blocks))

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
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
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
