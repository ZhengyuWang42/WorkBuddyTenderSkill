"""Small, explicit Pydantic contract for V1 ProjectFacts.

This module defines data structures only. It does not parse documents, call a
model, resolve facts, or generate output files.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt, model_validator


class ContractModel(BaseModel):
    """Base model with a closed contract to catch accidental extra fields."""

    model_config = ConfigDict(extra="forbid")


class FieldName(str, Enum):
    """The deliberately small V1 field catalog."""

    PROJECT_NAME = "project_name"
    PROJECT_NUMBER = "project_number"
    TENDER_NUMBER = "tender_number"
    LOT_NAME = "lot_name"
    LOT_NUMBER = "lot_number"
    PURCHASER = "purchaser"
    TENDER_AGENCY = "tender_agency"
    PROJECT_LOCATION = "project_location"
    PROCUREMENT_SCOPE = "procurement_scope"
    BUDGET = "budget"
    MAX_PRICE = "max_price"
    DURATION = "duration"
    QUALITY_TARGET = "quality_target"
    BID_DEADLINE = "bid_deadline"
    BID_OPEN_TIME = "bid_open_time"
    BID_OPEN_LOCATION = "bid_open_location"
    BID_BOND_AMOUNT = "bid_bond_amount"
    BID_BOND_FORM = "bid_bond_form"
    CONSORTIUM_ALLOWED = "consortium_allowed"
    PROCUREMENT_METHOD = "procurement_method"
    BID_VALIDITY = "bid_validity"
    SUBMISSION_METHOD = "submission_method"
    ELECTRONIC_PLATFORM = "electronic_platform"


class FactStatus(str, Enum):
    """V1 statuses for a final field."""

    RESOLVED = "RESOLVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_FOUND = "NOT_FOUND"


class ResolutionAction(str, Enum):
    """The only V1 actions allowed after WorkBuddy review."""

    SELECT_CANDIDATE = "SELECT_CANDIDATE"
    KEEP_UNRESOLVED = "KEEP_UNRESOLVED"


class SourceType(str, Enum):
    """The two document types supported by the V1 contract."""

    PDF = "PDF"
    DOCX = "DOCX"


FactValue: TypeAlias = str | int | float | bool | None


class PdfLocator(ContractModel):
    """A 1-based PDF page with an optional text block index."""

    locator_type: Literal["pdf_block"] = "pdf_block"
    page: PositiveInt
    block_index: NonNegativeInt | None = None


class PdfTableLocator(ContractModel):
    """A precise locator for one normalized PDF table cell."""

    locator_type: Literal["pdf_table_cell"] = "pdf_table_cell"
    page: PositiveInt
    table_index: NonNegativeInt
    row_index: NonNegativeInt
    column_index: NonNegativeInt


class DocxParagraphLocator(ContractModel):
    """A zero-based DOCX body paragraph index; no page is implied."""

    locator_type: Literal["docx_paragraph"] = "docx_paragraph"
    paragraph_index: NonNegativeInt


class DocxTableLocator(ContractModel):
    """A zero-based DOCX table cell location; no page is implied."""

    locator_type: Literal["docx_table_cell"] = "docx_table_cell"
    table_index: NonNegativeInt
    row_index: NonNegativeInt
    cell_index: NonNegativeInt


Locator: TypeAlias = Annotated[
    PdfLocator | PdfTableLocator | DocxParagraphLocator | DocxTableLocator,
    Field(discriminator="locator_type"),
]


class CandidateFact(ContractModel):
    """One source-backed candidate value for a ProjectFacts field."""

    value: FactValue
    normalized_value: FactValue = None
    confidence: float = Field(ge=0.0, le=1.0)
    method: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    source_type: SourceType
    locator: Locator
    section: str | None = None
    evidence_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def locator_matches_source_type(self) -> "CandidateFact":
        """Prevent a DOCX candidate from acquiring a fabricated PDF page."""

        if self.source_type == SourceType.PDF and not isinstance(
            self.locator, (PdfLocator, PdfTableLocator)
        ):
            raise ValueError("PDF candidates must use PdfLocator or PdfTableLocator")
        if self.source_type == SourceType.DOCX and isinstance(
            self.locator, (PdfLocator, PdfTableLocator)
        ):
            raise ValueError("DOCX candidates cannot use a PDF page locator")
        return self


class ResolvedFact(ContractModel):
    """The final state of one field, retaining every candidate."""

    field: FieldName
    resolved_value: FactValue = None
    status: FactStatus
    confidence: float = Field(ge=0.0, le=1.0)
    candidates: list[CandidateFact] = Field(default_factory=list)
    resolution_reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "ResolvedFact":
        if self.status == FactStatus.RESOLVED:
            if self.resolved_value is None:
                raise ValueError("RESOLVED facts require resolved_value")
            if not self.candidates:
                raise ValueError("RESOLVED facts require at least one candidate")
        elif self.status == FactStatus.NEEDS_REVIEW:
            if not self.candidates:
                raise ValueError("NEEDS_REVIEW facts require candidate evidence")
        elif self.status == FactStatus.NOT_FOUND:
            if self.resolved_value is not None:
                raise ValueError("NOT_FOUND facts cannot have resolved_value")
            if self.candidates:
                raise ValueError("NOT_FOUND facts cannot contain trusted candidates")
        return self


def _default_not_found_fact(field: FieldName) -> ResolvedFact:
    """Provide backward-compatible defaults for newly added review fields."""

    return ResolvedFact(
        field=field,
        resolved_value=None,
        status=FactStatus.NOT_FOUND,
        confidence=0.0,
        candidates=[],
        resolution_reason="No credible candidate found.",
    )


class ProjectFields(ContractModel):
    """Explicit tender facts plus the three review-template facts."""

    project_name: ResolvedFact
    project_number: ResolvedFact
    tender_number: ResolvedFact
    lot_name: ResolvedFact
    lot_number: ResolvedFact
    purchaser: ResolvedFact
    tender_agency: ResolvedFact
    project_location: ResolvedFact
    procurement_scope: ResolvedFact
    budget: ResolvedFact
    max_price: ResolvedFact
    duration: ResolvedFact
    quality_target: ResolvedFact
    bid_deadline: ResolvedFact
    bid_open_time: ResolvedFact
    bid_open_location: ResolvedFact
    bid_bond_amount: ResolvedFact
    bid_bond_form: ResolvedFact
    consortium_allowed: ResolvedFact
    procurement_method: ResolvedFact
    # Defaults let schema 1.0 ProjectFacts payloads be read without inventing
    # values for the fields introduced by the review-template contract.
    bid_validity: ResolvedFact = Field(
        default_factory=lambda: _default_not_found_fact(FieldName.BID_VALIDITY)
    )
    submission_method: ResolvedFact = Field(
        default_factory=lambda: _default_not_found_fact(FieldName.SUBMISSION_METHOD)
    )
    electronic_platform: ResolvedFact = Field(
        default_factory=lambda: _default_not_found_fact(FieldName.ELECTRONIC_PLATFORM)
    )

    @model_validator(mode="after")
    def field_names_match_keys(self) -> "ProjectFields":
        for field_name in FieldName:
            fact = getattr(self, field_name.value)
            if fact.field != field_name:
                raise ValueError(
                    f"ResolvedFact.field must match ProjectFields key {field_name.value}"
                )
        return self


class SourceDocument(ContractModel):
    """Input document identity without requiring an absolute path."""

    source_file: str = Field(min_length=1)
    source_type: SourceType


class FactSummary(ContractModel):
    """Counts for the fixed ProjectFacts field catalog."""

    total_fields: NonNegativeInt
    resolved: NonNegativeInt
    needs_review: NonNegativeInt
    not_found: NonNegativeInt

    @classmethod
    def from_fields(cls, fields: ProjectFields) -> "FactSummary":
        counts = {status: 0 for status in FactStatus}
        for field_name in FieldName:
            fact = getattr(fields, field_name.value)
            counts[fact.status] += 1
        return cls(
            total_fields=len(FieldName),
            resolved=counts[FactStatus.RESOLVED],
            needs_review=counts[FactStatus.NEEDS_REVIEW],
            not_found=counts[FactStatus.NOT_FOUND],
        )


class ProjectFacts(ContractModel):
    """The single source of truth for all future V1 outputs."""

    source_document: SourceDocument
    schema_version: str = "1.1"
    fields: ProjectFields
    summary: FactSummary

    @classmethod
    def from_fields(
        cls,
        *,
        source_document: SourceDocument,
        fields: ProjectFields,
        schema_version: str = "1.1",
    ) -> "ProjectFacts":
        return cls(
            source_document=source_document,
            schema_version=schema_version,
            fields=fields,
            summary=FactSummary.from_fields(fields),
        )

    @model_validator(mode="after")
    def summary_matches_fields(self) -> "ProjectFacts":
        expected = FactSummary.from_fields(self.fields)
        if self.summary != expected:
            raise ValueError("summary must exactly match the statuses in fields")
        return self


class ResolutionOverride(ContractModel):
    """One constrained semantic-review instruction.

    Candidate indexes are zero-based and refer to the candidate order already
    present in the corresponding ProjectFacts field.  No free-text value is
    accepted by this contract.
    """

    field: FieldName
    action: ResolutionAction
    candidate_index: NonNegativeInt | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_action_payload(self) -> "ResolutionOverride":
        if self.action == ResolutionAction.SELECT_CANDIDATE:
            if self.candidate_index is None:
                raise ValueError("SELECT_CANDIDATE requires candidate_index")
        elif self.candidate_index is not None:
            raise ValueError("KEEP_UNRESOLVED cannot include candidate_index")
        return self


class ResolutionOverrides(ContractModel):
    """A bounded set of one-time instructions for a ProjectFacts review."""

    schema_version: str = "1.0"
    resolutions: list[ResolutionOverride] = Field(default_factory=list)

    @model_validator(mode="after")
    def fields_are_unique(self) -> "ResolutionOverrides":
        fields = [resolution.field for resolution in self.resolutions]
        if len(fields) != len(set(fields)):
            raise ValueError("resolution_overrides cannot repeat a field")
        return self


class SemanticCandidateProposal(ContractModel):
    """A WorkBuddy semantic suggestion that is still source-evidence bound."""

    field: FieldName
    value: FactValue
    source_locator: Locator
    evidence_text: str = Field(min_length=1)
    reason: str = Field(min_length=1)


__all__ = [
    "CandidateFact",
    "DocxParagraphLocator",
    "DocxTableLocator",
    "FactStatus",
    "FactSummary",
    "FactValue",
    "FieldName",
    "Locator",
    "PdfLocator",
    "PdfTableLocator",
    "ProjectFacts",
    "ProjectFields",
    "ResolutionAction",
    "ResolutionOverride",
    "ResolutionOverrides",
    "ResolvedFact",
    "SemanticCandidateProposal",
    "SourceDocument",
    "SourceType",
]
