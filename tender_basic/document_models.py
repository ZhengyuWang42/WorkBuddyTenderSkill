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
    SourceType,
)


class DocumentStatus(str, Enum):
    PARSED = "PARSED"
    OCR_REQUIRED = "OCR_REQUIRED"
    PARSE_ERROR = "PARSE_ERROR"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"


class DocumentBlock(ContractModel):
    """One PDF block in the original page order."""

    block_index: NonNegativeInt
    text: str
    bbox: tuple[float, float, float, float]
    block_type: str = "unknown"
    locator: PdfLocator

    @model_validator(mode="after")
    def locator_matches_block(self) -> "DocumentBlock":
        if self.locator.block_index != self.block_index:
            raise ValueError("PDF block locator must match block_index")
        return self


class DocumentPage(ContractModel):
    """One PDF page; page_number is always 1-based."""

    page_number: PositiveInt
    blocks: list[DocumentBlock] = Field(default_factory=list)

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


DocumentElement: TypeAlias = Annotated[
    PdfBlockElement | ParagraphElement | TableElement,
    Field(discriminator="type"),
]


class NormalizedDocument(ContractModel):
    """Portable, ordered source representation for later fact extraction."""

    schema_version: str = "1.0"
    source_file: str = Field(min_length=1)
    source_type: SourceType | None
    status: DocumentStatus
    page_count: NonNegativeInt
    text_length: NonNegativeInt
    pages: list[DocumentPage] = Field(default_factory=list)
    elements: list[DocumentElement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "DocumentBlock",
    "DocumentElement",
    "DocumentPage",
    "DocumentParagraph",
    "DocumentRow",
    "DocumentStatus",
    "DocumentTable",
    "DocumentCell",
    "NormalizedDocument",
    "ParagraphElement",
    "PdfBlockElement",
    "TableElement",
]
