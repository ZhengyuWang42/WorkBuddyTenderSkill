"""Minimal ProjectFacts contract package for tender-basic."""

from .models import (
    CandidateFact,
    DocxParagraphLocator,
    DocxTableLocator,
    FactStatus,
    FieldName,
    Locator,
    PdfLocator,
    ProjectFacts,
    ProjectFields,
    ResolvedFact,
    SourceDocument,
    SourceType,
)

__all__ = [
    "CandidateFact",
    "DocxParagraphLocator",
    "DocxTableLocator",
    "FactStatus",
    "FieldName",
    "Locator",
    "PdfLocator",
    "ProjectFacts",
    "ProjectFields",
    "ResolvedFact",
    "SourceDocument",
    "SourceType",
]
