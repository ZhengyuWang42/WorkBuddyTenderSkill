"""Pydantic models for the document-normalization stage only.

These models describe where source text is and how it is ordered. They do not
assign any text to a ProjectFacts field.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import Field, NonNegativeInt, PositiveInt, model_validator

from .models import (
    ContractModel,
    DocxParagraphLocator,
    DocxTableLocator,
    PdfLocator,
    PdfTableLocator,
    SourceType,
)


class DocumentStatus(str, Enum):
    PARSED = "PARSED"
    OCR_REQUIRED = "OCR_REQUIRED"
    PARSE_ERROR = "PARSE_ERROR"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"


class PdfCharacterGeometry(ContractModel):
    """One exact character box from the PDF parser's own character records.

    ``evidence_kind`` distinguishes real recorded geometry from geometry that
    was approximated by subdividing a run bbox.  Only ``EXACT_PDF_CHAR`` may
    support an exact character-boundary decision.
    """

    index: NonNegativeInt = 0
    character: str
    bbox: tuple[float, float, float, float]
    origin: tuple[float, float] | None = None
    evidence_kind: Literal[
        "EXACT_PDF_CHAR", "APPROXIMATED_FROM_RUN_WIDTH"
    ] = "EXACT_PDF_CHAR"


class PdfTextSpan(ContractModel):
    """Direct PDF text-span metadata kept for source-format reconstruction.

    The fact extractor may use the normalized text, but the format builder
    must be able to use the original span geometry and typography.  PyMuPDF's
    flags are converted to the small set of visual attributes that can be
    represented reliably in an editable DOCX.
    """

    text: str
    bbox: tuple[float, float, float, float]
    font_name: str = ""
    font_size: float = 0.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: int | None = None
    flags: int = 0
    source_order: NonNegativeInt = 0
    #: Exact per-character geometry, when the parser recorded it.  Optional so
    #: that documents normalized before this field existed still load, and so
    #: that sources without character records stay valid.
    characters: list[PdfCharacterGeometry] = Field(default_factory=list)


class PdfTextLine(ContractModel):
    """One PDF line with its direct text spans and geometry."""

    text: str
    bbox: tuple[float, float, float, float]
    spans: list[PdfTextSpan] = Field(default_factory=list)
    source_order: NonNegativeInt = 0


class PdfVectorLine(ContractModel):
    """A simple horizontal/vertical PDF vector line kept for form fidelity."""

    bbox: tuple[float, float, float, float]
    width: float = 0.5
    color: int | None = None
    orientation: Literal["horizontal", "vertical"] = "horizontal"


class DocumentBlock(ContractModel):
    """One PDF block in the original page order."""

    block_index: NonNegativeInt
    text: str
    raw_display_text: str = ""
    semantic_normalized_text: str = ""
    bbox: tuple[float, float, float, float]
    block_type: str = "unknown"
    locator: PdfLocator
    lines: list[PdfTextLine] = Field(default_factory=list)

    @model_validator(mode="after")
    def locator_matches_block(self) -> "DocumentBlock":
        if self.locator.block_index != self.block_index:
            raise ValueError("PDF block locator must match block_index")
        return self


class DocumentPage(ContractModel):
    """One PDF page; page_number is always 1-based."""

    page_number: PositiveInt
    blocks: list[DocumentBlock] = Field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    vector_lines: list[PdfVectorLine] = Field(default_factory=list)
    # Non-text page artwork (for example a seal image) is counted separately
    # so source-format reconstruction can report anything it did not turn into
    # editable content instead of silently dropping it.
    unmodeled_artwork_count: NonNegativeInt = 0

    @model_validator(mode="after")
    def locators_match_page(self) -> "DocumentPage":
        for block in self.blocks:
            if block.locator.page != self.page_number:
                raise ValueError("PDF block locator must match page_number")
        return self


class DocumentParagraph(ContractModel):
    """One top-level DOCX body paragraph with a zero-based index."""

    paragraph_index: NonNegativeInt
    text: str
    style_name: str | None = None
    locator: DocxParagraphLocator

    @model_validator(mode="after")
    def locator_matches_paragraph(self) -> "DocumentParagraph":
        if self.locator.paragraph_index != self.paragraph_index:
            raise ValueError("DOCX paragraph locator must match paragraph_index")
        return self


class DocumentCell(ContractModel):
    """One DOCX table cell; cell text may contain normalized newlines."""

    cell_index: NonNegativeInt
    text: str
    locator: DocxTableLocator


class DocumentRow(ContractModel):
    row_index: NonNegativeInt
    cells: list[DocumentCell] = Field(default_factory=list)

    @model_validator(mode="after")
    def locators_match_row(self) -> "DocumentRow":
        for cell in self.cells:
            if cell.locator.row_index != self.row_index:
                raise ValueError("DOCX cell locator must match row_index")
        return self


class DocumentTable(ContractModel):
    table_index: NonNegativeInt
    rows: list[DocumentRow] = Field(default_factory=list)

    @model_validator(mode="after")
    def locators_match_table(self) -> "DocumentTable":
        for row in self.rows:
            for cell in row.cells:
                if cell.locator.table_index != self.table_index:
                    raise ValueError("DOCX cell locator must match table_index")
        return self


class PdfTableCell(ContractModel):
    """One cell recovered from a PDF table detector."""

    row_index: NonNegativeInt
    column_index: NonNegativeInt
    text: str = ""
    bbox: tuple[float, float, float, float] | None = None
    locator: PdfTableLocator
    spans: list[PdfTextSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def locator_matches_cell_page(self) -> "PdfTableCell":
        return self


class PdfTableRow(ContractModel):
    """One ordered row in a PDF table."""

    row_index: NonNegativeInt
    cells: list[PdfTableCell] = Field(default_factory=list)

    @model_validator(mode="after")
    def cell_rows_match(self) -> "PdfTableRow":
        for cell in self.cells:
            if cell.row_index != self.row_index:
                raise ValueError("PDF table cell row_index must match its row")
        return self


class PdfTable(ContractModel):
    """Minimal PDF table representation retained alongside PDF text blocks."""

    page: PositiveInt
    table_index: NonNegativeInt
    bbox: tuple[float, float, float, float]
    rows: list[PdfTableRow] = Field(default_factory=list)
    column_widths: list[float] = Field(default_factory=list)
    row_heights: list[float] = Field(default_factory=list)
    # Each tuple is (row_start, row_end, column_start, column_end), inclusive.
    # PyMuPDF exposes repeated cell rectangles for many horizontal merges; the
    # normalized model keeps that topology without pretending to recover
    # complex spanning semantics when the PDF does not expose them reliably.
    merged_cells: list[tuple[NonNegativeInt, NonNegativeInt, NonNegativeInt, NonNegativeInt]] = Field(
        default_factory=list
    )
    border_width: float = 0.5

    @model_validator(mode="after")
    def cell_locators_match_page(self) -> "PdfTable":
        for row in self.rows:
            for cell in row.cells:
                if cell.locator.page != self.page:
                    raise ValueError("PDF table cell locator must match table page")
        return self


class PdfBlockElement(ContractModel):
    type: Literal["pdf_block"] = "pdf_block"
    page_number: PositiveInt
    block: DocumentBlock

    @model_validator(mode="after")
    def locator_matches_page(self) -> "PdfBlockElement":
        if self.block.locator.page != self.page_number:
            raise ValueError("PDF element page_number must match block locator")
        return self


class ParagraphElement(ContractModel):
    type: Literal["paragraph"] = "paragraph"
    paragraph: DocumentParagraph


class TableElement(ContractModel):
    type: Literal["table"] = "table"
    table: DocumentTable


class PdfTableElement(ContractModel):
    type: Literal["pdf_table"] = "pdf_table"
    table: PdfTable


DocumentElement: TypeAlias = Annotated[
    PdfBlockElement | ParagraphElement | TableElement | PdfTableElement,
    Field(discriminator="type"),
]


class NormalizedDocument(ContractModel):
    """Portable, ordered source representation for later fact extraction."""

    schema_version: str = "1.1"
    source_file: str = Field(min_length=1)
    source_type: SourceType | None
    status: DocumentStatus
    page_count: NonNegativeInt
    text_length: NonNegativeInt
    pages: list[DocumentPage] = Field(default_factory=list)
    tables: list[PdfTable] = Field(default_factory=list)
    elements: list[DocumentElement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "DocumentBlock",
    "PdfTextLine",
    "PdfTextSpan",
    "PdfVectorLine",
    "DocumentElement",
    "DocumentPage",
    "DocumentParagraph",
    "DocumentRow",
    "DocumentStatus",
    "DocumentTable",
    "DocumentCell",
    "PdfTable",
    "PdfTableCell",
    "PdfTableRow",
    "NormalizedDocument",
    "ParagraphElement",
    "PdfBlockElement",
    "TableElement",
    "PdfTableElement",
]
