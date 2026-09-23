"""Geometry-aware source-format model for editable bid-document output.

The existing normalized document remains the fact-extraction contract.  This
module is the separate format contract: it keeps page geometry, direct PDF
span typography, editable table geometry, chrome decisions, and explicit
fill-slot metadata.  It deliberately does not resolve facts.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Mapping, Sequence

from pydantic import Field, NonNegativeInt, PositiveInt

from .document_models import (
    DocumentBlock,
    DocumentPage,
    NormalizedDocument,
    PdfTable,
    PdfTableCell,
    PdfTableElement,
    PdfTextLine,
    PdfTextSpan,
    PdfVectorLine,
)
from .models import ContractModel, FieldName, Locator, PdfLocator, PdfTableLocator, SourceType
from .source_font_policy import normalize_pdf_font_name


BaselineRole = Literal["NORMAL", "SUPERSCRIPT", "SUBSCRIPT"]
FontWeightRole = Literal["regular", "medium", "bold"]


class TypographyRole(str, Enum):
    COVER_CHAPTER = "COVER_CHAPTER"
    COVER_PROJECT_TITLE = "COVER_PROJECT_TITLE"
    COVER_DOCUMENT_TITLE = "COVER_DOCUMENT_TITLE"
    FORM_LABEL = "FORM_LABEL"
    FORM_VALUE = "FORM_VALUE"
    TABLE_LABEL = "TABLE_LABEL"
    TABLE_VALUE = "TABLE_VALUE"
    BODY = "BODY"
    LIST = "LIST"
    TABLE_HEADER = "TABLE_HEADER"
    TABLE_BODY = "TABLE_BODY"


class TextStyle(ContractModel):
    font_family_east_asia: str = "宋体"
    font_family_latin: str = "Times New Roman"
    font_size_pt: float = 10.5
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: int | None = None
    baseline_role: BaselineRole = "NORMAL"
    font_weight_role: FontWeightRole = "regular"


class DestinationStyleProfile(ContractModel):
    """Formatting owned by a destination slot, never by its fact evidence."""

    east_asia_font: str = "宋体"
    latin_font: str = "Times New Roman"
    font_size: float = 10.5
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: int | None = None
    font_weight_role: FontWeightRole = "regular"
    paragraph_alignment: Literal["left", "center", "right", "justify"] = "left"
    line_spacing: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    cell_vertical_alignment: Literal["top", "center", "bottom"] | None = None
    cell_margin_profile: dict[str, float] = Field(default_factory=dict)
    anchor_source: str = "SECTION_BODY_STYLE"


class RaisedGlyph(ContractModel):
    character: str
    base_token: str
    relative_x: float
    baseline_offset: float
    role: Literal["SUPERSCRIPT", "SUBSCRIPT"]


class CharacterGeometry(ContractModel):
    """One source character box.

    ``evidence_kind`` is load-bearing: only ``EXACT_PDF_CHAR`` geometry, taken
    from the PDF parser's own per-character records, may satisfy an exact
    boundary gate.  ``APPROXIMATED_FROM_RUN_WIDTH`` geometry is subdivided
    evenly across a run bbox and is never admissible as boundary evidence.
    """

    character: str
    x0: float
    y0: float
    x1: float
    y1: float
    baseline: float
    index: NonNegativeInt = 0
    origin: tuple[float, float] | None = None
    font: str = ""
    font_size: float = 0.0
    baseline_role: BaselineRole = "NORMAL"
    evidence_kind: Literal[
        "EXACT_PDF_CHAR", "APPROXIMATED_FROM_RUN_WIDTH"
    ] = "APPROXIMATED_FROM_RUN_WIDTH"


class TableTypographyProfile(ContractModel):
    header_style_by_column: dict[int, TextStyle] = Field(default_factory=dict)
    body_style_by_column: dict[int, TextStyle] = Field(default_factory=dict)
    body_style_by_role: dict[str, TextStyle] = Field(default_factory=dict)
    numeric_style: TextStyle | None = None
    unit_style: TextStyle | None = None


class SourceRun(ContractModel):
    """One source text span as it will be emitted into an editable run."""

    text: str
    bbox: tuple[float, float, float, float]
    font_name: str = ""
    raw_font_name: str | None = None
    font_size: float = 0.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: int | None = None
    flags: int = 0
    source_order: NonNegativeInt = 0
    baseline_role: BaselineRole = "NORMAL"
    font_weight_role: FontWeightRole = "regular"
    #: Exact per-character source geometry when the source provided it.
    #: Empty for DOCX sources and for PDF spans parsed without char records.
    characters: list[CharacterGeometry] = Field(default_factory=list)


class SourceParagraph(ContractModel):
    """One source PDF text block with direct run and paragraph geometry."""

    paragraph_id: str
    page: PositiveInt
    bbox: tuple[float, float, float, float]
    text: str
    raw_display_text: str = ""
    semantic_normalized_text: str = ""
    lines: list[PdfTextLine] = Field(default_factory=list)
    runs: list[SourceRun] = Field(default_factory=list)
    locator: Locator
    alignment: Literal["left", "center", "right", "justify"] = "left"
    first_line_indent: float = 0.0
    left_indent: float = 0.0
    right_indent: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    line_spacing: float = 0.0
    page_break_before: bool = False
    typography_role: TypographyRole = TypographyRole.BODY


class SourceCell(ContractModel):
    """One editable source table cell."""

    row_index: NonNegativeInt
    column_index: NonNegativeInt
    bbox: tuple[float, float, float, float] | None = None
    text: str = ""
    runs: list[SourceRun] = Field(default_factory=list)
    locator: PdfTableLocator
    vertical_alignment: Literal["top", "center", "bottom"] = "center"
    horizontal_alignment: Literal["left", "center", "right", "justify"] = "left"
    cell_role: Literal["HEADER", "BODY_TEXT", "NUMERIC", "UNIT"] = "BODY_TEXT"
    characters: list[CharacterGeometry] = Field(default_factory=list)
    raised_glyphs: list[RaisedGlyph] = Field(default_factory=list)
    #: Horizontal rules the source drew *inside* this cell as ``(x0, x1, y)``.
    #: The table's own borders are its geometry; a rule that is not a border is
    #: content - the underline of a value the source filled in, or the blank a
    #: fixed field leaves.  Delivering the cell without them loses the source's
    #: own emphasis.
    content_rules: list[tuple[float, float, float]] = Field(default_factory=list)
    typography_role: TypographyRole = TypographyRole.TABLE_BODY


class SourceRow(ContractModel):
    row_index: NonNegativeInt
    cells: list[SourceCell] = Field(default_factory=list)
    height: float = 0.0


class SourceTable(ContractModel):
    """One real editable table with the geometry available from the PDF."""

    page: PositiveInt
    table_index: NonNegativeInt
    bbox: tuple[float, float, float, float]
    rows: list[SourceRow] = Field(default_factory=list)
    columns: NonNegativeInt = 0
    column_widths: list[float] = Field(default_factory=list)
    row_heights: list[float] = Field(default_factory=list)
    merged_cells: list[tuple[NonNegativeInt, NonNegativeInt, NonNegativeInt, NonNegativeInt]] = Field(
        default_factory=list
    )
    border_width: float = 0.5
    typography_profile: TableTypographyProfile | None = None
    style_outliers: list[dict[str, object]] = Field(default_factory=list)


class SourcePageElement(ContractModel):
    """Source-page order reference for paragraphs and tables."""

    type: Literal["paragraph", "table"]
    index: NonNegativeInt
    bbox: tuple[float, float, float, float]


class SourceLine(ContractModel):
    """A simple editable ruled line outside a source table."""

    bbox: tuple[float, float, float, float]
    width: float = 0.5
    color: int | None = None
    orientation: Literal["horizontal", "vertical"] = "horizontal"


class SourcePage(ContractModel):
    page: PositiveInt
    width: float
    height: float
    paragraphs: list[SourceParagraph] = Field(default_factory=list)
    tables: list[SourceTable] = Field(default_factory=list)
    elements: list[SourcePageElement] = Field(default_factory=list)
    lines: list[SourceLine] = Field(default_factory=list)
    unmodeled_artwork_count: NonNegativeInt = 0
    start_y: float | None = None
    end_y: float | None = None


class SourceChromeItem(ContractModel):
    """A repeated page chrome item excluded from the editable body."""

    text: str
    page: PositiveInt
    locator: Locator
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class SourceFillSlot(ContractModel):
    """An explicitly detected source placeholder and its allowed fact fields."""

    slot_id: str
    semantic_hint: str
    slot_type: Literal[
        "PROJECT_NAME_SLOT", "PROJECT_AND_LOT_SLOT", "PROJECT_NUMBER_SLOT",
        "TENDER_NUMBER_SLOT", "PURCHASER_SLOT", "AGENCY_SLOT", "DURATION_SLOT",
        "QUALITY_SLOT", "MAX_PRICE_SLOT", "BID_DEADLINE_SLOT", "BID_OPEN_TIME_SLOT",
        "BID_BOND_AMOUNT_SLOT", "BID_BOND_FORM_SLOT", "CONSORTIUM_SLOT",
        "PROJECT_LOCATION_SLOT", "BID_OPEN_LOCATION_SLOT", "BID_VALIDITY_SLOT",
        "ELECTRONIC_PLATFORM_SLOT", "UNKNOWN_SLOT",
    ] = "UNKNOWN_SLOT"
    source_page: PositiveInt
    source_locator: Locator
    container_type: Literal["paragraph", "table_cell"]
    original_text: str
    text_start: NonNegativeInt | None = None
    text_end: NonNegativeInt | None = None
    prefix_text: str = ""
    suffix_text: str = ""
    font_name: str = ""
    font_size: float = 0.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    geometry: tuple[float, float, float, float] | None = None
    allowed_fact_fields: list[FieldName] = Field(default_factory=list)
    match_kind: Literal[
        "underline",
        "whitespace",
        "parenthetical",
        "table_blank",
        "date_signature",
    ]
    table_index: int | None = None
    row_index: int | None = None
    column_index: int | None = None
    destination_style: DestinationStyleProfile = Field(default_factory=DestinationStyleProfile)

    def model_post_init(self, __context: object) -> None:
        if self.destination_style.anchor_source != "SECTION_BODY_STYLE" or not (
            self.font_name or self.font_size or self.bold or self.italic or self.underline
        ):
            return
        family, _ = normalize_pdf_font_name(self.font_name)
        self.destination_style = DestinationStyleProfile(
            east_asia_font=family,
            latin_font="Times New Roman",
            font_size=self.font_size or 10.5,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            font_weight_role=_font_weight_role(self.font_name, self.bold),
            anchor_source="DESTINATION_SLOT_METADATA",
        )


class SourceFormatTemplate(ContractModel):
    """Complete source-driven model consumed by the DOCX builder."""

    source_heading: str | None = None
    source_locator: Locator | None = None
    source_type: SourceType | None = None
    source_pages: list[SourcePage] = Field(default_factory=list)
    fill_slots: list[SourceFillSlot] = Field(default_factory=list)
    chrome_items: list[SourceChromeItem] = Field(default_factory=list)
    layout_warnings: list[str] = Field(default_factory=list)
    artifact_filter_report: dict[str, object] = Field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.source_pages)

    @property
    def source_table_count(self) -> int:
        return sum(len(page.tables) for page in self.source_pages)


_FACT_HINTS: tuple[tuple[str, FieldName], ...] = (
    ("项目名称、标段", FieldName.PROJECT_NAME),
    ("项目名称及标段", FieldName.PROJECT_NAME),
    ("招标代理项目编号", FieldName.TENDER_NUMBER),
    ("代理项目编号", FieldName.TENDER_NUMBER),
    ("招标编号", FieldName.TENDER_NUMBER),
    ("采购人项目编号", FieldName.PROJECT_NUMBER),
    ("招标人项目编号", FieldName.PROJECT_NUMBER),
    ("采购项目编号", FieldName.PROJECT_NUMBER),
    ("采购编号", FieldName.PROJECT_NUMBER),
    ("项目编号", FieldName.PROJECT_NUMBER),
    ("采购人名称", FieldName.PURCHASER),
    ("招标人名称", FieldName.PURCHASER),
    ("采购人", FieldName.PURCHASER),
    ("招标人", FieldName.PURCHASER),
    ("采购代理机构", FieldName.TENDER_AGENCY),
    ("招标代理机构", FieldName.TENDER_AGENCY),
    ("代理机构", FieldName.TENDER_AGENCY),
    ("项目名称", FieldName.PROJECT_NAME),
    ("采购项目名称", FieldName.PROJECT_NAME),
    ("交货地点", FieldName.PROJECT_LOCATION),
    ("供货地点", FieldName.PROJECT_LOCATION),
    ("实施地点", FieldName.PROJECT_LOCATION),
    ("项目地点", FieldName.PROJECT_LOCATION),
    ("项目地址", FieldName.PROJECT_LOCATION),
    ("供货期", FieldName.DURATION),
    ("实施周期", FieldName.DURATION),
    ("履约期限", FieldName.DURATION),
    ("交付周期", FieldName.DURATION),
    ("服务期", FieldName.DURATION),
    ("工期", FieldName.DURATION),
    ("供货质量", FieldName.QUALITY_TARGET),
    ("服务质量要求", FieldName.QUALITY_TARGET),
    ("质量标准", FieldName.QUALITY_TARGET),
    ("质量目标", FieldName.QUALITY_TARGET),
    ("投标截止时间", FieldName.BID_DEADLINE),
    ("提交响应文件截止时间", FieldName.BID_DEADLINE),
    ("响应文件递交截止时间", FieldName.BID_DEADLINE),
    ("开标时间", FieldName.BID_OPEN_TIME),
    ("开标地点", FieldName.BID_OPEN_LOCATION),
    ("递交地点", FieldName.BID_OPEN_LOCATION),
    ("响应文件递交地点", FieldName.BID_OPEN_LOCATION),
    ("投标保证金金额", FieldName.BID_BOND_AMOUNT),
    ("投标保证金", FieldName.BID_BOND_AMOUNT),
    ("保证金金额", FieldName.BID_BOND_AMOUNT),
    ("投标保证金形式", FieldName.BID_BOND_FORM),
    ("保证金形式", FieldName.BID_BOND_FORM),
    ("投标有效期", FieldName.BID_VALIDITY),
    ("询比有效期", FieldName.BID_VALIDITY),
    ("电子交易平台", FieldName.ELECTRONIC_PLATFORM),
    ("交易平台", FieldName.ELECTRONIC_PLATFORM),
)

_HINTS = tuple(label for label, _field in _FACT_HINTS)
_PARENTHETICAL_RE = re.compile(r"[（(]\s*([^（）()]{1,30}?)\s*[）)]")
# A composite placeholder may nest one placeholder inside another, e.g.
# ``（项目名称（标段名称））``.  The flat parenthetical pattern cannot cross the
# inner bracket, so it would match only ``（标段名称）`` and lose the outer
# component.  This pattern captures the whole composite with its components so
# both halves can be modelled and filled independently.
_NESTED_PARENTHETICAL_RE = re.compile(
    r"[（(]\s*(?P<outer>[^（）()]{1,30}?)\s*"
    r"[（(]\s*(?P<inner>[^（）()]{1,30}?)\s*[）)]\s*[）)]"
)
_UNDERLINE_RE = re.compile(r"_{2,}|＿{2,}")
_WHITESPACE_RE = re.compile(r"[ \t]{2,}")
_DATE_SIGNATURE_RE = re.compile(r"年\s{0,5}月\s{0,5}日")
_LABEL_RE = re.compile("|".join(re.escape(label) for label in _HINTS))
_PROJECT_SENTENCE_RE = re.compile(r"贵公司(?P<slot>_{2,}|＿{2,}|\s+)项目(?:招标|询比|采购)文件")

_SLOT_TYPE_BY_FIELD = {
    FieldName.PROJECT_NAME: "PROJECT_NAME_SLOT",
    FieldName.PROJECT_NUMBER: "PROJECT_NUMBER_SLOT",
    FieldName.TENDER_NUMBER: "TENDER_NUMBER_SLOT",
    FieldName.PURCHASER: "PURCHASER_SLOT",
    FieldName.TENDER_AGENCY: "AGENCY_SLOT",
    FieldName.DURATION: "DURATION_SLOT",
    FieldName.QUALITY_TARGET: "QUALITY_SLOT",
    FieldName.MAX_PRICE: "MAX_PRICE_SLOT",
    FieldName.BID_DEADLINE: "BID_DEADLINE_SLOT",
    FieldName.BID_OPEN_TIME: "BID_OPEN_TIME_SLOT",
    FieldName.BID_BOND_AMOUNT: "BID_BOND_AMOUNT_SLOT",
    FieldName.BID_BOND_FORM: "BID_BOND_FORM_SLOT",
    FieldName.CONSORTIUM_ALLOWED: "CONSORTIUM_SLOT",
    FieldName.PROJECT_LOCATION: "PROJECT_LOCATION_SLOT",
    FieldName.BID_OPEN_LOCATION: "BID_OPEN_LOCATION_SLOT",
    FieldName.BID_VALIDITY: "BID_VALIDITY_SLOT",
    FieldName.ELECTRONIC_PLATFORM: "ELECTRONIC_PLATFORM_SLOT",
}


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def repair_pdf_font_name(value: str) -> str:
    """Repair common UTF-8-as-Latin-1 font names emitted by PDF producers."""

    text = value or ""
    if "Ã" in text or "Â" in text or "é" in text or "å" in text:
        try:
            return text.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def _field_for_hint(hint: str) -> FieldName | None:
    compact = _compact(hint).strip("：:")
    for label, field in sorted(_FACT_HINTS, key=lambda item: len(item[0]), reverse=True):
        if compact == _compact(label):
            return field
    return None


def _slot_contract(hint: str) -> tuple[str, list[FieldName]]:
    compact = _compact(hint)
    # ``strip`` removes *all* leading/trailing bracket characters, so a nested
    # composite keeps its inner bracket only.  Compare both the raw and the
    # stripped form rather than relying on one of them.
    bare = compact.strip("()（）：:")
    if bare in {"项目名称、标段", "项目名称及标段", "项目名称、标段名称"}:
        return "PROJECT_AND_LOT_SLOT", [FieldName.PROJECT_NAME, FieldName.LOT_NAME]
    # A composite placeholder written as 项目名称（标段名称） names the same
    # pair of facts as 项目名称、标段; the source just nested the brackets.
    if bare in {
        "项目名称（标段名称）", "项目名称(标段名称)",
        "项目名称（标段）", "项目名称(标段)",
        "项目名称（标段名称", "项目名称(标段名称",
        "项目名称（标段", "项目名称(标段",
    }:
        return "PROJECT_AND_LOT_SLOT", [FieldName.PROJECT_NAME, FieldName.LOT_NAME]
    field = _field_for_hint(bare)
    if field is None:
        return "UNKNOWN_SLOT", []
    return _SLOT_TYPE_BY_FIELD.get(field, "UNKNOWN_SLOT"), [field]


def _font_weight_role(font_name: str, bold: bool) -> FontWeightRole:
    compact = re.sub(r"[\s_-]+", "", font_name or "").lower()
    if bold or any(token in compact for token in ("bold", "heavy", "black")):
        return "bold"
    if any(token in compact for token in ("medium", "demi", "semibold")):
        return "medium"
    return "regular"


def _character_geometry_from_span(span: PdfTextSpan) -> list[CharacterGeometry]:
    """Carry the parser's exact character records onto the source run.

    Evidence kind is preserved verbatim so a consumer can tell real recorded
    geometry from an approximation; this function never synthesizes boxes.
    """

    return [
        CharacterGeometry(
            character=item.character,
            x0=item.bbox[0],
            y0=item.bbox[1],
            x1=item.bbox[2],
            y1=item.bbox[3],
            baseline=item.bbox[3],
            index=item.index,
            origin=item.origin,
            font=span.font_name,
            font_size=span.font_size,
            evidence_kind=item.evidence_kind,
        )
        for item in span.characters
    ]


def _source_run_from_span(span: PdfTextSpan) -> SourceRun:
    font_name = repair_pdf_font_name(span.font_name)
    return SourceRun(
        text=span.text,
        bbox=span.bbox,
        font_name=font_name,
        raw_font_name=span.font_name,
        font_size=span.font_size,
        bold=span.bold,
        italic=span.italic,
        underline=span.underline,
        color=span.color,
        flags=span.flags,
        source_order=span.source_order,
        font_weight_role=_font_weight_role(font_name, span.bold),
        characters=_character_geometry_from_span(span),
    )


_SUPERSCRIPT_MAP = str.maketrans({"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
                                  "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
                                  "⁺": "+", "⁻": "-"})
_SUBSCRIPT_MAP = str.maketrans({"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
                                "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
                                "₊": "+", "₋": "-"})
_SUPER_CHARS = set("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
_SUB_CHARS = set("₀₁₂₃₄₅₆₇₈₉₊₋")


def find_exact_character_boundary(
    run: SourceRun,
    x: float,
    tolerance_pt: float = 0.75,
) -> dict:
    """Resolve an exact character boundary of ``run`` at source position ``x``.

    A boundary is the gap between two adjacent recorded character boxes, so the
    split produces real characters on both sides.  Approximate geometry is
    rejected outright rather than resolved to its nearest synthetic edge, and a
    character straddling ``x`` disqualifies the boundary.
    """

    characters = [
        item for item in run.characters if item.evidence_kind == "EXACT_PDF_CHAR"
    ]
    result = {
        "boundary_x": round(float(x), 2),
        "tolerance_pt": tolerance_pt,
        "aligned": False,
        "character_offset": None,
        "boundary_x_pt": None,
        "boundary_error_pt": None,
        "previous_character": None,
        "next_character": None,
        "straddling_character": None,
        "evidence_kind": None,
        "character_count": len(characters),
        "run_character_count": len(run.characters),
    }
    if not characters:
        result["evidence_kind"] = (
            "APPROXIMATED_FROM_RUN_WIDTH" if run.characters else "NO_CHARACTER_GEOMETRY"
        )
        return result

    straddling = next(
        (item for item in characters if item.x0 < x - 0.01 and item.x1 > x + 0.01), None
    )
    if straddling is not None:
        result["evidence_kind"] = "EXACT_PDF_CHAR"
        result["straddling_character"] = {
            "character": straddling.character,
            "x0": round(straddling.x0, 2),
            "x1": round(straddling.x1, 2),
            "distance_to_previous_boundary_pt": round(abs(straddling.x0 - x), 2),
            "distance_to_next_boundary_pt": round(abs(straddling.x1 - x), 2),
        }
        result["previous_character"] = _character_evidence(straddling, "x0")
        result["next_character"] = _character_evidence(straddling, "x1")
        return result

    previous = [item for item in characters if item.x1 <= x + 0.01]
    following = [item for item in characters if item.x0 >= x - 0.01]
    best_previous = max(previous, key=lambda item: item.x1) if previous else None
    best_next = min(following, key=lambda item: item.x0) if following else None
    candidates = []
    if best_previous is not None:
        candidates.append((abs(best_previous.x1 - x), best_previous.x1, best_previous, "x1"))
    if best_next is not None:
        candidates.append((abs(best_next.x0 - x), best_next.x0, best_next, "x0"))
    if not candidates:
        result["evidence_kind"] = "EXACT_PDF_CHAR"
        return result
    candidates.sort(key=lambda item: item[0])
    error, boundary_x, owner, edge = candidates[0]

    result["evidence_kind"] = "EXACT_PDF_CHAR"
    result["boundary_x_pt"] = round(boundary_x, 2)
    result["boundary_error_pt"] = round(error, 2)
    result["previous_character"] = (
        _character_evidence(best_previous, "x1") if best_previous else None
    )
    result["next_character"] = (
        _character_evidence(best_next, "x0") if best_next else None
    )
    if error > tolerance_pt:
        return result

    # The offset is the number of characters before the boundary.
    if edge == "x1":
        result["character_offset"] = owner.index + 1
    else:
        result["character_offset"] = owner.index
    result["aligned"] = True
    return result


def _character_evidence(item: CharacterGeometry, edge: str) -> dict:
    return {
        "character": item.character,
        "index": item.index,
        "x0": round(item.x0, 2),
        "x1": round(item.x1, 2),
        "edge": edge,
        "evidence_kind": item.evidence_kind,
    }


def _characters_from_runs(runs: Sequence[SourceRun]) -> list[CharacterGeometry]:
    """Approximate per-character x boxes while retaining exact span geometry.

    APPROXIMATE ONLY: every box is an even subdivision of the run bbox, so this
    geometry must never satisfy an exact boundary gate (SOURCE_RULE_COMPOSITION,
    EXACT_SOURCE_SPAN splitting, INLINE_REPRESENTABLE decisions, partial-run
    underline boundaries).  Use exact character records for those.
    """

    chars: list[CharacterGeometry] = []
    for run in runs:
        count = max(1, len(run.text))
        width = (run.bbox[2] - run.bbox[0]) / count
        for index, character in enumerate(run.text):
            role: BaselineRole = (
                "SUPERSCRIPT" if character in _SUPER_CHARS else
                "SUBSCRIPT" if character in _SUB_CHARS else "NORMAL"
            )
            chars.append(CharacterGeometry(
                character=character,
                x0=run.bbox[0] + width * index,
                y0=run.bbox[1],
                x1=run.bbox[0] + width * (index + 1),
                y1=run.bbox[3],
                baseline=run.bbox[3],
                index=index,
                font=run.font_name,
                font_size=run.font_size,
                baseline_role=role,
                evidence_kind="APPROXIMATED_FROM_RUN_WIDTH",
            ))
    return chars


def _baseline_bands(runs: Sequence[SourceRun]) -> list[list[SourceRun]]:
    """Group by vertical overlap, then order each band strictly by x."""

    bands: list[list[SourceRun]] = []
    for run in sorted(runs, key=lambda item: (item.bbox[1], item.bbox[0], item.source_order)):
        height = max(1.0, run.bbox[3] - run.bbox[1])
        best: list[SourceRun] | None = None
        best_overlap = 0.0
        for band in bands:
            y0 = min(item.bbox[1] for item in band)
            y1 = max(item.bbox[3] for item in band)
            overlap = max(0.0, min(y1, run.bbox[3]) - max(y0, run.bbox[1]))
            ratio = overlap / min(height, max(1.0, y1 - y0))
            if ratio >= 0.5 and ratio > best_overlap:
                best, best_overlap = band, ratio
        if best is None:
            bands.append([run])
        else:
            best.append(run)
    bands.sort(key=lambda band: min(item.bbox[1] for item in band))
    for band in bands:
        band.sort(key=lambda item: (item.bbox[0], item.source_order))
    return bands


def reconstruct_technical_runs(runs: Sequence[SourceRun]) -> tuple[str, list[SourceRun], list[CharacterGeometry], list[RaisedGlyph]]:
    """Rebuild semantic x-order and turn raised Unicode glyphs into Word roles."""

    output_runs: list[SourceRun] = []
    raised: list[RaisedGlyph] = []
    characters = _characters_from_runs(runs)
    text_lines: list[str] = []
    for band in _baseline_bands(runs):
        line_text = ""
        for run in band:
            role: BaselineRole = "NORMAL"
            translated = run.text
            if run.text and all(char in _SUPER_CHARS for char in run.text):
                role = "SUPERSCRIPT"
                translated = run.text.translate(_SUPERSCRIPT_MAP)
            elif run.text and all(char in _SUB_CHARS for char in run.text):
                role = "SUBSCRIPT"
                translated = run.text.translate(_SUBSCRIPT_MAP)
            effective = run.model_copy(update={"text": translated, "baseline_role": role})
            if role != "NORMAL":
                base = next((item for item in reversed(output_runs) if item.baseline_role == "NORMAL"), None)
                if base is None:
                    base = next((item for item in band if item is not run and item.bbox[0] >= run.bbox[2]), None)
                if base is not None:
                    effective = effective.model_copy(update={
                        "font_name": base.font_name,
                        "font_size": base.font_size,
                        "bold": base.bold,
                        "italic": base.italic,
                        "color": base.color,
                    })
                raised.append(RaisedGlyph(
                    character=translated,
                    base_token=(base.text if base is not None else ""),
                    relative_x=run.bbox[0] - (base.bbox[0] if base is not None else run.bbox[0]),
                    baseline_offset=(base.bbox[3] - run.bbox[3]) if base is not None else 0.0,
                    role=role,
                ))
            output_runs.append(effective)
            line_text += translated
        text_lines.append(line_text)
    return "\n".join(text_lines), output_runs, characters, raised


def _text_style(run: SourceRun) -> TextStyle:
    family, _ = normalize_pdf_font_name(run.font_name)
    return TextStyle(
        font_family_east_asia=family,
        font_family_latin=family if family in {"Arial", "Calibri", "Times New Roman"} else "Times New Roman",
        font_size_pt=round(run.font_size or 10.5, 2),
        bold=run.bold,
        italic=run.italic,
        underline=run.underline,
        color=run.color,
        baseline_role=run.baseline_role,
        font_weight_role=run.font_weight_role,
    )


def _cell_role(cell: SourceCell, header: bool) -> Literal["HEADER", "BODY_TEXT", "NUMERIC", "UNIT"]:
    if header:
        return "HEADER"
    compact = _compact(cell.text)
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?%?", compact):
        return "NUMERIC"
    if compact and len(compact) <= 8 and re.fullmatch(r"(?:项|台|套|个|只|组|米|m|mm|cm|kg|t|元|%)+", compact, re.I):
        return "UNIT"
    return "BODY_TEXT"


def build_table_typography_profile(table: SourceTable) -> SourceTable:
    """Cluster same-role cells without flattening explicit source variants."""

    style_groups: dict[tuple[str, int], list[tuple[SourceCell, SourceRun, TextStyle]]] = defaultdict(list)
    updated_rows: list[SourceRow] = []
    for row in table.rows:
        cells: list[SourceCell] = []
        for cell in row.cells:
            role = _cell_role(cell, row.row_index == 0)
            current = cell.model_copy(update={
                "cell_role": role,
                "typography_role": TypographyRole.TABLE_HEADER if role == "HEADER" else TypographyRole.TABLE_BODY,
            })
            visible = next((run for run in current.runs if run.text.strip() and run.baseline_role == "NORMAL"), None)
            if visible is not None:
                style_groups[(role, cell.column_index)].append((current, visible, _text_style(visible)))
            cells.append(current)
        updated_rows.append(row.model_copy(update={"cells": cells}))

    outliers: list[dict[str, object]] = []
    dominant: dict[tuple[str, int], TextStyle] = {}
    for key, values in style_groups.items():
        counts = Counter(item[2].model_dump_json() for item in values)
        style_json, count = counts.most_common(1)[0]
        style = TextStyle.model_validate_json(style_json)
        dominant[key] = style
        for cell, _run, candidate in values:
            if candidate == style:
                continue
            repeated = counts[candidate.model_dump_json()] >= 2
            outliers.append({
                "code": "TABLE_STYLE_VARIANT",
                "row_index": cell.row_index,
                "column_index": cell.column_index,
                "cell_text": cell.text,
                "role": key[0],
                "observed": candidate.model_dump(mode="json"),
                "dominant": style.model_dump(mode="json"),
                "resolution": (
                    "PRESERVED_REPEATED_SOURCE_VARIANT"
                    if repeated else "PRESERVED_LOCAL_SOURCE_VARIATION"
                ),
            })

    header = {column: style for (role, column), style in dominant.items() if role == "HEADER"}
    body = {column: style for (role, column), style in dominant.items() if role == "BODY_TEXT"}
    by_role = {role: style for (role, _column), style in dominant.items() if role.startswith("BODY")}
    profile = TableTypographyProfile(
        header_style_by_column=header,
        body_style_by_column=body,
        body_style_by_role=by_role,
        numeric_style=next((style for (role, _), style in dominant.items() if role == "NUMERIC"), None),
        unit_style=next((style for (role, _), style in dominant.items() if role == "UNIT"), None),
    )
    return table.model_copy(update={"rows": updated_rows, "typography_profile": profile, "style_outliers": outliers})


def apply_source_glyph_repairs(
    template: "SourceFormatTemplate",
    repairs: Sequence[dict[str, object]],
) -> tuple["SourceFormatTemplate", dict[str, object]]:
    """Apply explicit geometry-backed glyph mappings, never language guesses."""

    applied: list[dict[str, object]] = []
    pages: list[SourcePage] = []
    for page in template.source_pages:
        tables: list[SourceTable] = []
        for table in page.tables:
            rows: list[SourceRow] = []
            for row in table.rows:
                cells: list[SourceCell] = []
                for cell in row.cells:
                    current = cell
                    for repair in repairs:
                        if (page.page, table.table_index, row.row_index, cell.column_index) != (
                            repair.get("page"), repair.get("table_index"), repair.get("row_index"), repair.get("column_index")
                        ):
                            continue
                        extracted, visual = str(repair.get("extracted", "")), str(repair.get("visual", ""))
                        if not extracted or extracted not in current.text or len(extracted) != len(visual):
                            continue
                        runs = [run.model_copy(update={"text": run.text.replace(extracted, visual)})
                                for run in current.runs]
                        current = current.model_copy(update={"text": current.text.replace(extracted, visual), "runs": runs})
                        applied.append(dict(repair))
                    cells.append(current)
                rows.append(row.model_copy(update={"cells": cells}))
            tables.append(build_table_typography_profile(table.model_copy(update={"rows": rows})))
        pages.append(page.model_copy(update={"tables": tables}))
    report = {
        "source_text_disagreement_count": len(applied),
        "source_glyph_mapping_warning_count": len(applied),
        "repairs": applied,
        "method": "explicit rendered-glyph evidence at recorded PDF geometry",
    }
    return template.model_copy(update={"source_pages": pages}), report


def _fallback_run(text: str, bbox: tuple[float, float, float, float]) -> SourceRun:
    return SourceRun(text=text, bbox=bbox, font_name="", font_size=10.5)


def _has_justified_geometry(block: DocumentBlock, page_width: float) -> bool:
    """Return true only when the PDF supplies both paragraph edges.

    A long line is not, by itself, evidence of justification.  Require at
    least two physical lines with a common left edge and a common right edge;
    the final line may be shorter, as it is in a normally justified Word
    paragraph.  This keeps paragraph alignment a geometry decision rather
    than a positioning shortcut.
    """
    lines = [line for line in block.lines if line.text.strip()]
    if len(lines) < 2:
        return False
    body = lines[:-1]
    if not body:
        return False
    left = [float(line.bbox[0]) for line in body]
    right = [float(line.bbox[2]) for line in body]
    common_width = min(right) - max(left)
    if common_width < page_width * 0.55:
        return False
    return max(left) - min(left) <= 8.0 and max(right) - min(right) <= 12.0


def _block_alignment(block: DocumentBlock, page_width: float) -> Literal["left", "center", "right", "justify"]:
    x0, _y0, x1, _y1 = block.bbox
    center = (x0 + x1) / 2.0
    page_center = page_width / 2.0
    if abs(center - page_center) <= max(8.0, page_width * 0.035):
        return "center"
    if x0 >= page_width * 0.58:
        return "right"
    if _has_justified_geometry(block, page_width):
        return "justify"
    return "left"


def _paragraph_from_block(block: DocumentBlock, page: DocumentPage) -> SourceParagraph:
    lines = list(block.lines)
    # The blocks API is the source-text authority.  Dict lines provide direct
    # typography and geometry, but may omit glyphs represented as embedded
    # images or private-use font characters.  Keeping block.text here prevents
    # a formatting reconstruction from deleting source wording merely because
    # the low-level span stream is incomplete.
    source_text = block.raw_display_text or block.text
    reconstructed_lines = "\n".join(line.text for line in lines)
    if reconstructed_lines and re.sub(r"\s+", "", reconstructed_lines) == re.sub(r"\s+", "", block.text):
        source_text = reconstructed_lines
    runs = [
        _source_run_from_span(span)
        for line in lines
        for span in line.spans
        if span.text
    ]
    if not runs and block.text:
        runs = [_fallback_run(block.text, block.bbox)]
    line_gaps: list[float] = []
    for previous, current in zip(lines, lines[1:]):
        gap = current.bbox[1] - previous.bbox[3]
        if math.isfinite(gap) and gap >= 0:
            line_gaps.append(gap)
    # ``line_spacing`` stores the gap between adjacent PDF line boxes.  A
    # single-line block has no inter-line gap; using the full glyph height as
    # a spacing value would double the Word line height and clip the text box.
    line_spacing = sum(line_gaps) / len(line_gaps) if line_gaps else 0.0
    line_xs = [line.bbox[0] for line in lines] or [block.bbox[0]]
    min_x = min(line_xs)
    first_indent = max(0.0, line_xs[0] - min_x) if line_xs else 0.0
    return SourceParagraph(
        paragraph_id=f"PDF:P:{page.page_number}:B:{block.block_index}",
        page=page.page_number,
        bbox=block.bbox,
        text=source_text,
        raw_display_text=source_text,
        semantic_normalized_text=block.semantic_normalized_text or block.text,
        lines=lines,
        runs=runs,
        locator=block.locator,
        alignment=_block_alignment(block, page.width),
        first_line_indent=first_indent,
        left_indent=max(0.0, block.bbox[0]),
        right_indent=max(0.0, page.width - block.bbox[2]),
        line_spacing=line_spacing,
        page_break_before=False,
    )


def _span_in_region(span: PdfTextSpan, region: tuple[float, float, float, float]) -> bool:
    center_x = (span.bbox[0] + span.bbox[2]) / 2.0
    center_y = (span.bbox[1] + span.bbox[3]) / 2.0
    return (
        region[0] - 1.0 <= center_x <= region[2] + 1.0
        and region[1] - 1.0 <= center_y <= region[3] + 1.0
    )


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2]-bbox[0]) * max(0.0, bbox[3]-bbox[1])


def _intersection_area(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    return max(0.0, min(left[2],right[2])-max(left[0],right[0])) * max(
        0.0, min(left[3],right[3])-max(left[1],right[1])
    )


def _span_is_overlay(span: PdfTextSpan, page_size: tuple[float, float] | None) -> bool:
    """Geometry-only watermark/artifact signal; text is never blacklisted."""
    width=max(0.0,span.bbox[2]-span.bbox[0])
    height=max(0.0,span.bbox[3]-span.bbox[1])
    if width <= 0 or height <= 0:
        return False
    if page_size:
        page_width,page_height=page_size
        area_ratio=_bbox_area(span.bbox)/max(1.0,page_width*page_height)
        if area_ratio >= .035 and (len(_compact(span.text)) >= 8 or height >= page_height*.18):
            return True
    return height >= max(width*1.8, span.font_size*4.0) and len(_compact(span.text)) <= 32


def _span_owned_by_cell(
    span: PdfTextSpan,
    cell_bbox: tuple[float, float, float, float] | None,
) -> bool:
    if cell_bbox is None:
        return True
    span_area=_bbox_area(span.bbox)
    overlap=_intersection_area(span.bbox,cell_bbox)
    return _span_in_region(span,cell_bbox) or (span_area > 0 and overlap/span_area >= .60)


def _artifact_stat(report, key, value):
    if report is None:
        return
    if key not in report:
        report[key]=[] if key.endswith('_details') else 0
    if isinstance(report[key],list):
        report[key].append(value)
    else:
        report[key]=int(report[key])+1


def _clean_table_cell_text(
    cell: PdfTableCell,
    chrome_regions: Sequence[tuple[float, float, float, float]],
    chrome_keys: set[str] | None = None,
    *,
    page_spans: Sequence[PdfTextSpan] = (),
    page_size: tuple[float, float] | None = None,
    artifact_report: dict[str, object] | None = None,
) -> tuple[str, list[SourceRun]]:
    """Use direct, geometrically owned spans for table text.

    PyMuPDF's table text fallback may place a page-layer watermark fragment
    into a cell even when the page text span is elsewhere.  A raw fallback is
    accepted only when there is no overlay evidence; direct short business
    values remain valid when their span is owned by the cell.
    """

    # Only a short raw fallback with no owned direct spans needs page-layer
    # artifact arbitration.  Adjacent legitimate spans may intersect a large
    # table rectangle; recording each of those as an artifact was noisy and
    # incorrectly removed valid business text.
    page_candidates=[]
    raw=cell.text or ''
    if cell.bbox is not None and raw.strip() and len(_compact(raw)) <= 8 and not cell.spans:
        seen_candidates=set()
        for span in page_spans:
            overlap=_intersection_area(span.bbox,cell.bbox)
            if overlap <= 0 or not _span_is_overlay(span,page_size):
                continue
            key=(span.text,tuple(round(value,2) for value in span.bbox))
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            page_candidates.append(span)
            _artifact_stat(artifact_report,'table_spans_rejected_by_geometry',1)
            _artifact_stat(artifact_report,'isolated_artifact_candidates',1)
            _artifact_stat(artifact_report,'isolated_artifact_details',{
                'page':cell.locator.page,'table_index':cell.locator.table_index,
                'row_index':cell.row_index,'column_index':cell.column_index,
                'text':span.text,'bbox':span.bbox,
                'reason':'short raw fallback overlaps a page-layer overlay but is not cell-owned',
            })

    # Some PDF producers expose a diagonal watermark as a giant text block
    # whose bounding box covers ordinary table content. Region-only masking
    # would therefore delete real labels such as ``姓名`` and ``联系电话``.
    # Prefer exact span-text chrome matching when the detector supplied keys;
    # use the geometry fallback only for callers that do not have keys.
    spans=[]
    for span in cell.spans:
        if chrome_keys and _chrome_key(span.text) in chrome_keys:
            _artifact_stat(artifact_report,'artifact_spans_removed',1)
            _artifact_stat(artifact_report,'artifact_spans_removed_details',{
                'page':cell.locator.page,'table_index':cell.locator.table_index,
                'row_index':cell.row_index,'column_index':cell.column_index,
                'text':span.text,'reason':'repeated page chrome key',
            })
            continue
        region_chrome = (not chrome_keys) and any(_span_in_region(span, region) for region in chrome_regions)
        if not span.text.strip():
            continue
        if not _span_owned_by_cell(span,cell.bbox) or region_chrome:
            _artifact_stat(artifact_report,'artifact_spans_removed',1)
            _artifact_stat(artifact_report,'artifact_spans_removed_details',{
                'page':cell.locator.page,'table_index':cell.locator.table_index,
                'row_index':cell.row_index,'column_index':cell.column_index,
                'text':span.text,'reason':'cell geometry/chrome region rejection',
            })
            continue
        if cell.bbox is not None and _span_is_overlay(span,page_size):
            coverage=_intersection_area(span.bbox,cell.bbox)/max(1.0,_bbox_area(span.bbox))
            if coverage < .75:
                _artifact_stat(artifact_report,'artifact_spans_removed',1)
                _artifact_stat(artifact_report,'artifact_spans_removed_details',{
                    'page':cell.locator.page,'table_index':cell.locator.table_index,
                    'row_index':cell.row_index,'column_index':cell.column_index,
                    'text':span.text,'reason':'large overlay span is not cell-owned',
                })
                continue
        spans.append(span)
    runs = [_source_run_from_span(span) for span in spans if span.text]
    if not runs:
        # If the detector supplied only a raw short value and an overlapping
        # page-layer overlay, reject it.  Without that evidence preserve the
        # fallback and record it for manual review.
        raw=cell.text or ''
        if raw.strip() and page_candidates and len(_compact(raw)) <= 8:
            _artifact_stat(artifact_report,'artifact_spans_removed',1)
            _artifact_stat(artifact_report,'artifact_spans_removed_details',{
                'page':cell.locator.page,'table_index':cell.locator.table_index,
                'row_index':cell.row_index,'column_index':cell.column_index,
                'text':raw,'reason':'short raw cell fallback has no owned source span',
            })
            return '', []
        if raw.strip() and len(_compact(raw)) <= 8 and not cell.spans:
            _artifact_stat(artifact_report,'suspicious_short_cell_text',1)
        return (cell.text if not cell.spans else ""), []
    direct_text, runs, _characters, _raised = reconstruct_technical_runs(runs)
    # A direct span stream can omit private-use glyphs represented as images;
    # it is still preferable to retain the clean, editable text when it has
    # meaningful coverage.  The original extracted text remains the fallback.
    return (direct_text if direct_text.strip() else cell.text), runs


def _table_cell_from_pdf(
    cell: PdfTableCell,
    chrome_regions: Sequence[tuple[float, float, float, float]] = (),
    chrome_keys: set[str] | None = None,
    *,
    page_spans: Sequence[PdfTextSpan] = (),
    page_size: tuple[float, float] | None = None,
    artifact_report: dict[str, object] | None = None,
    content_rules: Sequence[tuple[float, float, float]] = (),
) -> SourceCell:
    text, runs = _clean_table_cell_text(
        cell,
        chrome_regions,
        chrome_keys=chrome_keys,
        page_spans=page_spans,
        page_size=page_size,
        artifact_report=artifact_report,
    )
    characters = _characters_from_runs(runs)
    raised = [RaisedGlyph(
        character=run.text,
        base_token=next((prior.text for prior in reversed(runs[:index]) if prior.baseline_role == "NORMAL"), ""),
        relative_x=run.bbox[0] - (runs[index - 1].bbox[0] if index else run.bbox[0]),
        baseline_offset=(runs[index - 1].bbox[3] - run.bbox[3]) if index else 0.0,
        role=run.baseline_role,
    ) for index, run in enumerate(runs) if run.baseline_role != "NORMAL"]
    return SourceCell(
        row_index=cell.row_index,
        column_index=cell.column_index,
        bbox=cell.bbox,
        text=text,
        runs=runs,
        locator=cell.locator,
        horizontal_alignment=_cell_alignment(cell, runs),
        characters=characters,
        raised_glyphs=raised,
        content_rules=[
            (round(float(x0), 2), round(float(x1), 2), round(float(y), 2))
            for x0, x1, y in content_rules
        ],
    )


#: How far a drawn line may sit from a row boundary and still be that border.
CELL_RULE_BORDER_TOLERANCE = 1.2
#: A drawn line spanning at least this fraction of the table's width is the
#: table's own grid rather than content the source placed inside a cell.
CELL_RULE_GRID_WIDTH_RATIO = 0.9


def _table_content_rules(table: PdfTable, page_lines: Sequence[PdfVectorLine]) -> dict:
    """Horizontal rules drawn *inside* the table's cells, keyed by cell.

    A table's own grid is geometry: its borders lie on row boundaries and span
    the table.  A rule that is neither is content the source drew inside a cell -
    the underline of a filled-in value, or the blank a fixed field leaves.  Losing
    it loses the source's own emphasis, so the cell that owns it keeps it.

    The classification is the table's own geometry and the page's own drawings,
    never a page number, a table index or a literal string.
    """

    cells = [
        cell
        for row in table.rows
        for cell in row.cells
        if cell.bbox is not None
    ]
    if not cells:
        return {}
    boundaries = set()
    for cell in cells:
        boundaries.add(round(float(cell.bbox[1]), 1))
        boundaries.add(round(float(cell.bbox[3]), 1))
    table_width = float(table.bbox[2]) - float(table.bbox[0])
    found: dict = {}
    for line in page_lines or ():
        if getattr(line, "orientation", None) != "horizontal":
            continue
        x0, y0, x1, y1 = (float(value) for value in line.bbox)
        if x1 < x0:
            x0, x1 = x1, x0
        y = (y0 + y1) / 2.0
        center = (x0 + x1) / 2.0
        if not (float(table.bbox[1]) - 1.0 <= y <= float(table.bbox[3]) + 1.0):
            continue
        if not (float(table.bbox[0]) - 1.0 <= center <= float(table.bbox[2]) + 1.0):
            continue
        if table_width > 0 and (x1 - x0) >= table_width * CELL_RULE_GRID_WIDTH_RATIO:
            continue
        if any(abs(y - boundary) <= CELL_RULE_BORDER_TOLERANCE for boundary in boundaries):
            continue
        owner = next(
            (
                cell
                for cell in cells
                if float(cell.bbox[1]) - 1.0 <= y <= float(cell.bbox[3]) + 1.0
                and float(cell.bbox[0]) - 1.0 <= center <= float(cell.bbox[2]) + 1.0
            ),
            None,
        )
        if owner is None:
            continue
        found.setdefault((owner.row_index, owner.column_index), []).append(
            (x0, x1, y)
        )
    for rules in found.values():
        rules.sort(key=lambda rule: (rule[2], rule[0]))
    return found


def _cell_line_boxes(runs: Sequence[SourceRun]) -> list[tuple[float, float, float]]:
    """Group visible runs into visual lines: (y_center, x_left, x_right)."""
    visible = [run for run in runs if run.text.strip()]
    if not visible:
        return []
    lines: list[list[SourceRun]] = []
    for run in sorted(visible, key=lambda r: (round(r.bbox[1], 1), r.bbox[0])):
        y = (run.bbox[1] + run.bbox[3]) / 2.0
        placed = False
        for group in lines:
            gy = sum((r.bbox[1] + r.bbox[3]) / 2.0 for r in group) / len(group)
            if abs(y - gy) <= 3.0:
                group.append(run)
                placed = True
                break
        if not placed:
            lines.append([run])
    boxes = [
        (
            sum((r.bbox[1] + r.bbox[3]) / 2.0 for r in group) / len(group),
            min(r.bbox[0] for r in group),
            max(r.bbox[2] for r in group),
        )
        for group in lines
    ]
    return sorted(boxes, key=lambda b: b[0])


@dataclass(frozen=True)
class CellAlignmentEvidence:
    """Measured source geometry behind one cell's alignment classification."""

    alignment: Literal["left", "center", "right", "justify", "unknown"]
    reason: str
    line_count: int = 0
    left_pad: float = 0.0
    right_pad: float = 0.0
    left_spread: float = 0.0
    right_spread: float = 0.0
    center_spread: float = 0.0
    fill_ratio: float = 0.0


def _classify_cell_alignment(
    cell_box: tuple[float, float, float, float],
    lines: list[tuple[float, float, float]],
) -> CellAlignmentEvidence:
    """Classify alignment from source-local geometry only.

    Deliberately does not consult the semantic role, the cell text length or a
    single center measurement.  Multi-line cells are decided by which axis is
    stable; single-line cells need genuinely comparable side padding, and
    otherwise report ``unknown`` instead of guessing.
    """
    if not lines or cell_box is None:
        return CellAlignmentEvidence("unknown", "no visible source glyphs")
    width = float(cell_box[2]) - float(cell_box[0])
    if width <= 1.0:
        return CellAlignmentEvidence("unknown", "degenerate cell box")
    lefts = [b[1] for b in lines]
    rights = [b[2] for b in lines]
    centers = [(b[1] + b[2]) / 2.0 for b in lines]
    left_spread = max(lefts) - min(lefts)
    right_spread = max(rights) - min(rights)
    center_spread = max(centers) - min(centers)
    left_pad = max(0.0, min(lefts) - float(cell_box[0]))
    right_pad = max(0.0, float(cell_box[2]) - max(rights))
    pad_tolerance = max(2.0, width * 0.04)

    if len(lines) >= 2:
        # Multi-line: the stable axis identifies the alignment.
        stable = min(
            (left_spread, "left"),
            (center_spread, "center"),
            (right_spread, "right"),
            key=lambda item: item[0],
        )
        edge_tolerance = max(2.0, width * 0.03)
        # JUSTIFY: most non-final lines reach both cell edges, last line shorter.
        body = lines[:-1]
        last = lines[-1]
        if body:
            edge_pad = max(6.0, width * 0.03)
            wide = sum(
                1 for _, x0, x1 in body
                if (x0 - float(cell_box[0])) <= edge_pad
                and (float(cell_box[2]) - x1) <= edge_pad
            )
            fill_ratio = wide / len(body)
            last_width = last[2] - last[1]
            body_widths = [(x1 - x0) for _, x0, x1 in body]
            mean_body = sum(body_widths) / len(body_widths) if body_widths else 0.0
            # A justified paragraph never stretches its final line: that line
            # stays ranged left, flush with the leading edge the body lines
            # start from.  A short final line that does not share that leading
            # edge is a *centred* (or right-aligned) last line, so the cell is
            # not justified however well its body lines reach both edges - this
            # is what separates a justified cell from a cell whose text simply
            # wrapped because it is wider than the column.
            body_indents = [x0 - float(cell_box[0]) for _, x0, _ in body]
            mean_body_indent = sum(body_indents) / len(body_indents)
            last_line_is_ranged_left = (
                abs((last[1] - float(cell_box[0])) - mean_body_indent) <= edge_pad
            )
            if (
                fill_ratio >= 0.6
                and last_width < mean_body * 0.9
                and last_line_is_ranged_left
            ):
                return CellAlignmentEvidence(
                    "justify", "body lines fill both cell edges and the last line is shorter",
                    len(lines), left_pad, right_pad, left_spread, right_spread, center_spread, fill_ratio,
                )
        if stable[0] <= edge_tolerance:
            return CellAlignmentEvidence(
                stable[1], f"stable {stable[1]} axis (spread {stable[0]:.2f} pt)",
                len(lines), left_pad, right_pad, left_spread, right_spread, center_spread, 0.0,
            )
        return CellAlignmentEvidence(
            "unknown",
            f"no stable axis (left {left_spread:.2f} / center {center_spread:.2f} / right {right_spread:.2f})",
            len(lines), left_pad, right_pad, left_spread, right_spread, center_spread, 0.0,
        )

    # Single line: require comparable side padding to call it centered.
    if abs(left_pad - right_pad) <= pad_tolerance:
        return CellAlignmentEvidence(
            "center", f"balanced side padding ({left_pad:.2f} vs {right_pad:.2f} pt)",
            1, left_pad, right_pad, left_spread, right_spread, center_spread, 0.0,
        )
    if right_pad <= pad_tolerance and left_pad > right_pad:
        return CellAlignmentEvidence(
            "right", f"text flush to the right edge (right pad {right_pad:.2f} pt)",
            1, left_pad, right_pad, left_spread, right_spread, center_spread, 0.0,
        )
    if left_pad <= pad_tolerance and left_pad < right_pad:
        return CellAlignmentEvidence(
            "left", f"text flush to the left edge (left pad {left_pad:.2f} pt)",
            1, left_pad, right_pad, left_spread, right_spread, center_spread, 0.0,
        )
    # A short centred run in a wide cell can drift by half a glyph while still
    # being centred; accept that only when the side padding stays proportionate.
    if abs(left_pad - right_pad) <= max(pad_tolerance, width * 0.08):
        return CellAlignmentEvidence(
            "center", f"near-balanced side padding ({left_pad:.2f} vs {right_pad:.2f} pt)",
            1, left_pad, right_pad, left_spread, right_spread, center_spread, 0.0,
        )
    return CellAlignmentEvidence(
        "unknown",
        f"asymmetric padding with no flush edge (left {left_pad:.2f} / right {right_pad:.2f} pt)",
        1, left_pad, right_pad, left_spread, right_spread, center_spread, 0.0,
    )


def _cell_alignment(
    cell: PdfTableCell,
    runs: Sequence[SourceRun],
) -> Literal["left", "center", "right", "justify"]:
    """Backwards-compatible wrapper returning only the alignment label."""
    return _alignment_label(cell_alignment_evidence(cell, runs))


def _alignment_label(
    evidence: CellAlignmentEvidence,
) -> Literal["left", "center", "right", "justify"]:
    """Map measured evidence onto the frozen four-value render contract.

    ``unknown`` is deliberately rendered as the contract default and must be
    reported by QA: the contract has no neutral value, so the uncertainty is
    preserved in the evidence object instead of being silently resolved.
    """
    return "left" if evidence.alignment == "unknown" else evidence.alignment


def _resolve_unknown_alignments(rows: list[SourceRow]) -> None:
    """Resolve ``unknown`` cells from the repeated source variant in their column.

    Formatting priority is source-local evidence first, then the repeated source
    variant.  A cell whose own geometry is inconclusive therefore adopts the
    majority alignment measured on the sibling cells of the same column, which
    is still source-owned evidence and never a semantic-role default.
    """
    column_count = max((len(row.cells) for row in rows), default=0)
    for column in range(column_count):
        votes: Counter[str] = Counter()
        unresolved: list[SourceCell] = []
        for row in rows:
            if column >= len(row.cells):
                continue
            cell = row.cells[column]
            evidence = cell_alignment_evidence_from_cell(cell)
            if evidence.alignment == "unknown":
                unresolved.append(cell)
            else:
                votes[evidence.alignment] += 1
        if not unresolved or not votes:
            continue
        winner, _ = votes.most_common(1)[0]
        for cell in unresolved:
            cell.horizontal_alignment = winner


def cell_alignment_evidence_from_cell(cell: SourceCell) -> CellAlignmentEvidence:
    """Recompute alignment evidence from an already-built source cell."""
    if cell.bbox is None:
        return CellAlignmentEvidence("unknown", "source cell has no box")
    return _classify_cell_alignment(tuple(cell.bbox), _cell_line_boxes(cell.runs))


def cell_alignment_evidence(
    cell: PdfTableCell,
    runs: Sequence[SourceRun],
) -> CellAlignmentEvidence:
    """Full measured evidence for one source cell's alignment."""
    if cell.bbox is None:
        return CellAlignmentEvidence("unknown", "source cell has no box")
    return _classify_cell_alignment(tuple(cell.bbox), _cell_line_boxes(runs))


def _table_from_pdf(
    table: PdfTable,
    chrome_regions: Mapping[int, Sequence[tuple[float, float, float, float]]] | None = None,
    chrome_keys: set[str] | None = None,
    *,
    page_spans: Sequence[PdfTextSpan] = (),
    page_size: tuple[float, float] | None = None,
    artifact_report: dict[str, object] | None = None,
    page_lines: Sequence[PdfVectorLine] = (),
) -> SourceTable:
    regions = (chrome_regions or {}).get(table.page, ())
    content_rules = _table_content_rules(table, page_lines)
    rows = [
        SourceRow(
            row_index=row.row_index,
            height=(
                table.row_heights[row.row_index]
                if row.row_index < len(table.row_heights)
                else 0.0
            ),
            cells=[
                _table_cell_from_pdf(
                    cell,
                    regions,
                    chrome_keys=chrome_keys,
                    page_spans=page_spans,
                    page_size=page_size,
                    artifact_report=artifact_report,
                    content_rules=content_rules.get(
                        (cell.row_index, cell.column_index), ()
                    ),
                )
                for cell in row.cells
            ],
        )
        for row in table.rows
    ]
    _resolve_unknown_alignments(rows)
    source_table = SourceTable(
        page=table.page,
        table_index=table.table_index,
        bbox=table.bbox,
        rows=rows,
        columns=max((len(row.cells) for row in rows), default=0),
        column_widths=table.column_widths,
        row_heights=table.row_heights,
        merged_cells=table.merged_cells,
        border_width=table.border_width,
    )
    return build_table_typography_profile(source_table)


def _source_line_from_pdf(line: PdfVectorLine) -> SourceLine:
    return SourceLine(
        bbox=line.bbox,
        width=line.width,
        color=line.color,
        orientation=line.orientation,
    )


def _bbox_contains(outer: tuple[float, float, float, float], inner: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = outer
    cx = (inner[0] + inner[2]) / 2.0
    cy = (inner[1] + inner[3]) / 2.0
    return x0 - 1.0 <= cx <= x1 + 1.0 and y0 - 1.0 <= cy <= y1 + 1.0


def _table_keys_from_elements(elements: Sequence[object]) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    for element in elements:
        if getattr(element, "type", None) != "table":
            continue
        table = getattr(element, "table", None)
        if table is not None and hasattr(table, "page") and hasattr(table, "table_index"):
            keys.add((int(table.page), int(table.table_index)))
    return keys


def _chrome_key(text: str) -> str:
    return _compact(text).strip("|丨-—_ ")


def detect_pdf_chrome(
    document: NormalizedDocument,
    page_numbers: Sequence[int],
) -> list[SourceChromeItem]:
    """Detect only repeated top/bottom text or obvious page-number chrome."""

    if not page_numbers:
        return []
    pages = {page.page_number: page for page in document.pages if page.page_number in page_numbers}
    occurrences: dict[str, list[tuple[int, DocumentBlock]]] = defaultdict(list)
    for page_number, page in pages.items():
        for block in page.blocks:
            text = _chrome_key(block.text)
            if not text:
                continue
            # PyMuPDF may expose table-cell text as page blocks.  A short
            # numeric cell value must not be mistaken for the page marker just
            # because it is repeated down a data table.  Keep real page-edge
            # markers eligible for detection, while leaving all table-owned
            # numeric content to table-cell ownership.
            if (re.fullmatch(r"(?:第)?\d+(?:页)?", text)
                    and any(
                        table.page == page_number
                        and _bbox_contains(table.bbox, block.bbox)
                        for table in document.tables
                    )):
                continue
            occurrences[text].append((page_number, block))

    threshold = max(2, math.ceil(len(pages) * 0.40))
    chrome: list[SourceChromeItem] = []
    for text, values in occurrences.items():
        page_set = {page_number for page_number, _block in values}
        is_page_number = bool(re.fullmatch(r"(?:第)?\d+(?:页)?", text))
        repeated = len(page_set) >= threshold
        for page_number, block in values:
            page = pages[page_number]
            top_or_bottom = (
                block.bbox[1] <= max(100.0, page.height * 0.14)
                or block.bbox[3] >= page.height - max(60.0, page.height * 0.10)
            )
            large_overlay = block.bbox[3] - block.bbox[1] >= page.height * 0.20
            timestamp = bool(re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2}", re.sub(r"\s+", " ", block.text).strip()))
            if not is_page_number and not (repeated and (top_or_bottom or large_overlay or timestamp)):
                continue
            if is_page_number:
                reason = "numeric page marker at page edge"
                confidence = 0.98
            elif top_or_bottom:
                reason = "repeated top/bottom text across source-format pages"
                confidence = 0.90
            else:
                reason = "repeated full-page overlay/chrome across source-format pages"
                confidence = 0.88
            chrome.append(
                SourceChromeItem(
                    text=block.text,
                    page=page_number,
                    locator=block.locator,
                    reason=reason,
                    confidence=confidence,
                )
            )
    return chrome


def _slot_geometry(
    paragraph: SourceParagraph,
    start: int,
    end: int,
) -> tuple[float, float, float, float]:
    # Map character positions to runs when possible.  If a PDF span has no
    # exact character metrics, retain the paragraph geometry rather than
    # inventing a narrower rectangle.
    cursor = 0
    selected: list[tuple[float, float, float, float]] = []
    for run in paragraph.runs:
        run_start, run_end = cursor, cursor + len(run.text)
        if run_end > start and run_start < end:
            selected.append(run.bbox)
        cursor = run_end
    if not selected:
        return paragraph.bbox
    return (
        min(box[0] for box in selected),
        min(box[1] for box in selected),
        max(box[2] for box in selected),
        max(box[3] for box in selected),
    )


def _slot_for_match(
    *,
    paragraph: SourceParagraph,
    match: re.Match[str],
    match_kind: Literal["underline", "whitespace", "parenthetical", "date_signature"],
    hint: str,
    slot_number: int,
    container_type: Literal["paragraph", "table_cell"] = "paragraph",
    locator: Locator | None = None,
    table_index: int | None = None,
    row_index: int | None = None,
    column_index: int | None = None,
) -> SourceFillSlot:
    slot_type, allowed_fields = _slot_contract(hint)
    original = match.group(0)
    return SourceFillSlot(
        slot_id=f"slot-{paragraph.page}-{slot_number}",
        semantic_hint=hint,
        slot_type=slot_type,
        source_page=paragraph.page,
        source_locator=locator or paragraph.locator,
        container_type=container_type,
        original_text=original,
        text_start=match.start(),
        text_end=match.end(),
        prefix_text=paragraph.text[: match.start()],
        suffix_text=paragraph.text[match.end() :],
        font_name=paragraph.runs[0].font_name if paragraph.runs else "",
        font_size=paragraph.runs[0].font_size if paragraph.runs else 0.0,
        bold=paragraph.runs[0].bold if paragraph.runs else False,
        italic=paragraph.runs[0].italic if paragraph.runs else False,
        underline=match_kind == "underline",
        geometry=_slot_geometry(paragraph, match.start(), match.end()),
        allowed_fact_fields=allowed_fields,
        match_kind=match_kind,
        table_index=table_index,
        row_index=row_index,
        column_index=column_index,
    )


def _paragraph_slots(
    paragraph: SourceParagraph,
    slot_start: int,
) -> list[SourceFillSlot]:
    slots: list[SourceFillSlot] = []
    text = paragraph.text
    # Parentheticals are only slots for known tender fact hints.  Supplier,
    # person, signature, price and bank-account parentheticals intentionally
    # yield no allowed fact field and therefore remain untouched.
    # Composite nested placeholders are claimed first so the flat pattern does
    # not consume only their inner bracket.
    nested_spans: list[tuple[int, int]] = []
    for nested in _NESTED_PARENTHETICAL_RE.finditer(text):
        composite = f"{nested.group('outer')}（{nested.group('inner')}）"
        _slot_type, allowed = _slot_contract(composite)
        if not allowed:
            continue
        nested_spans.append((nested.start(), nested.end()))
        slots.append(
            _slot_for_match(
                paragraph=paragraph,
                match=nested,
                match_kind="parenthetical",
                hint=composite,
                slot_number=slot_start + len(slots),
            )
        )
    for match in _PARENTHETICAL_RE.finditer(text):
        if any(start <= match.start() and match.end() <= end for start, end in nested_spans):
            continue
        _slot_type, allowed = _slot_contract(match.group(1))
        if not allowed:
            continue
        slots.append(
            _slot_for_match(
                paragraph=paragraph,
                match=match,
                match_kind="parenthetical",
                hint=match.group(1),
                slot_number=slot_start + len(slots),
            )
        )
    label_matches = list(_LABEL_RE.finditer(text))
    for label_match in label_matches:
        label = label_match.group(0)
        field = _field_for_hint(label)
        if field is None:
            continue
        tail = text[label_match.end() :]
        tail_match = re.match(r"\s*[：:]?\s*(?P<slot>_{2,}|＿{2,}|[ \t]{2,})", tail)
        if tail_match is None:
            continue
        slot_start_abs = label_match.end() + tail_match.start("slot")
        slot_end_abs = label_match.end() + tail_match.end("slot")
        match = re.match(re.escape(text[slot_start_abs:slot_end_abs]), text[slot_start_abs:])
        if match is None:
            continue
        # Build an absolute-position match compatible with the helper.
        class _AbsoluteMatch:
            def group(self, _index: int = 0) -> str:
                return text[slot_start_abs:slot_end_abs]

            def start(self) -> int:
                return slot_start_abs

            def end(self) -> int:
                return slot_end_abs

        kind: Literal["underline", "whitespace"] = (
            "underline" if set(text[slot_start_abs:slot_end_abs]) <= {"_", "＿"} else "whitespace"
        )
        slots.append(
            _slot_for_match(
                paragraph=paragraph,
                match=_AbsoluteMatch(),  # type: ignore[arg-type]
                match_kind=kind,
                hint=label,
                slot_number=slot_start + len(slots),
            )
        )
    for match in _PROJECT_SENTENCE_RE.finditer(text):
        slot_start_abs, slot_end_abs = match.start("slot"), match.end("slot")

        class _SentenceMatch:
            def group(self, _index: int = 0) -> str:
                return text[slot_start_abs:slot_end_abs]

            def start(self) -> int:
                return slot_start_abs

            def end(self) -> int:
                return slot_end_abs

        slots.append(_slot_for_match(
            paragraph=paragraph,
            match=_SentenceMatch(),  # type: ignore[arg-type]
            match_kind="underline" if "_" in match.group("slot") or "＿" in match.group("slot") else "whitespace",
            hint="项目名称",
            slot_number=slot_start + len(slots),
        ))
    for match in _DATE_SIGNATURE_RE.finditer(text):
        slots.append(
            _slot_for_match(
                paragraph=paragraph,
                match=match,
                match_kind="date_signature",
                hint="签字日期",
                slot_number=slot_start + len(slots),
            )
        )
    return slots


def _vector_rule_slot(paragraph: SourceParagraph, lines: Sequence[SourceLine], slot_number: int) -> SourceFillSlot | None:
    """Recover a labeled blank represented by a PDF vector rule, not spaces."""

    compact = _compact(paragraph.text)
    label = next((candidate for candidate in sorted(_HINTS, key=len, reverse=True)
                  if compact.rstrip("：:").endswith(_compact(candidate))), None)
    if label is None:
        return None
    field = _field_for_hint(label)
    if field is None:
        return None
    candidates = [line for line in lines if line.orientation == "horizontal"
                  and line.bbox[0] >= paragraph.bbox[2] - 8
                  and paragraph.bbox[1] - 5 <= line.bbox[1] <= paragraph.bbox[3] + 8]
    if not candidates:
        return None
    rule = min(candidates, key=lambda line: abs(line.bbox[1] - paragraph.bbox[3]))
    slot_type, allowed = _slot_contract(label)
    return SourceFillSlot(
        slot_id=f"slot-{paragraph.page}-{slot_number}",
        semantic_hint=label,
        slot_type=slot_type,
        source_page=paragraph.page,
        source_locator=paragraph.locator,
        container_type="paragraph",
        original_text="",
        text_start=len(paragraph.text),
        text_end=len(paragraph.text),
        prefix_text=paragraph.text,
        suffix_text="",
        font_name=paragraph.runs[-1].font_name if paragraph.runs else "",
        font_size=paragraph.runs[-1].font_size if paragraph.runs else 0.0,
        bold=paragraph.runs[-1].bold if paragraph.runs else False,
        italic=paragraph.runs[-1].italic if paragraph.runs else False,
        underline=True,
        geometry=rule.bbox,
        allowed_fact_fields=allowed,
        match_kind="whitespace",
    )


def _label_only_slot(paragraph: SourceParagraph, slot_number: int) -> SourceFillSlot | None:
    compact = _compact(paragraph.text)
    label = next((candidate for candidate in sorted(_HINTS, key=len, reverse=True)
                  if compact in {_compact(candidate), _compact(candidate) + "：", _compact(candidate) + ":"}), None)
    if label is None:
        return None
    slot_type, allowed = _slot_contract(label)
    if not allowed:
        return None
    return SourceFillSlot(
        slot_id=f"slot-{paragraph.page}-{slot_number}", semantic_hint=label, slot_type=slot_type,
        source_page=paragraph.page, source_locator=paragraph.locator, container_type="paragraph",
        original_text="", text_start=len(paragraph.text), text_end=len(paragraph.text),
        prefix_text=paragraph.text, suffix_text="", font_name=paragraph.runs[-1].font_name if paragraph.runs else "",
        font_size=paragraph.runs[-1].font_size if paragraph.runs else 0.0,
        bold=paragraph.runs[-1].bold if paragraph.runs else False,
        italic=paragraph.runs[-1].italic if paragraph.runs else False,
        underline=True, geometry=(paragraph.bbox[2] + 5, paragraph.bbox[1], paragraph.bbox[2] + 125, paragraph.bbox[3]),
        allowed_fact_fields=allowed, match_kind="whitespace",
    )


def _table_slots(table: SourceTable, slot_start: int) -> list[SourceFillSlot]:
    slots: list[SourceFillSlot] = []
    for row in table.rows:
        labels: list[tuple[str, FieldName, SourceCell]] = []
        for cell in row.cells:
            field = _field_for_hint(cell.text)
            if field is not None:
                labels.append((cell.text, field, cell))
        for label, field, label_cell in labels:
            candidates = [
                candidate_cell
                for candidate_cell in row.cells
                if candidate_cell.column_index > label_cell.column_index
            ]
            if not candidates:
                continue
            # The nearest cell is the value cell for a labeled table row. If
            # it already has source text, that text is fixed template content;
            # do not scan farther right into a remark/signature column and
            # mistake an unrelated blank cell for the value slot.
            candidate_cell = min(candidates, key=lambda cell: cell.column_index)
            if candidate_cell.text.strip() and not _UNDERLINE_RE.fullmatch(candidate_cell.text.strip()):
                continue
            paragraph = SourceParagraph(
                paragraph_id=f"PDF:T:{table.page}:{table.table_index}:R:{row.row_index}:C:{candidate_cell.column_index}",
                page=table.page,
                bbox=candidate_cell.bbox or table.bbox,
                text=candidate_cell.text,
                runs=candidate_cell.runs,
                locator=PdfLocator(page=table.page, block_index=0),
            )
            original = candidate_cell.text
            slots.append(
                SourceFillSlot(
                    slot_id=f"slot-{table.page}-{slot_start + len(slots)}",
                    semantic_hint=label,
                    slot_type=_SLOT_TYPE_BY_FIELD.get(field, "UNKNOWN_SLOT"),
                    source_page=table.page,
                    source_locator=candidate_cell.locator,
                    container_type="table_cell",
                    original_text=original,
                    prefix_text="",
                    suffix_text="",
                    font_name=candidate_cell.runs[0].font_name if candidate_cell.runs else "",
                    font_size=candidate_cell.runs[0].font_size if candidate_cell.runs else 0.0,
                    bold=candidate_cell.runs[0].bold if candidate_cell.runs else False,
                    italic=candidate_cell.runs[0].italic if candidate_cell.runs else False,
                    underline=bool(original.strip()),
                    geometry=candidate_cell.bbox,
                    allowed_fact_fields=[field],
                    match_kind="table_blank",
                    table_index=table.table_index,
                    row_index=row.row_index,
                    column_index=candidate_cell.column_index,
                )
            )
    # Parenthetical/underlined slots embedded in table cells are covered too.
    for row in table.rows:
        for cell in row.cells:
            if not cell.text:
                continue
            paragraph = SourceParagraph(
                paragraph_id=f"PDF:T:{table.page}:{table.table_index}:R:{row.row_index}:C:{cell.column_index}",
                page=table.page,
                bbox=cell.bbox or table.bbox,
                text=cell.text,
                runs=cell.runs,
                locator=PdfLocator(page=table.page, block_index=0),
            )
            embedded = _paragraph_slots(paragraph, slot_start + len(slots))
            for slot in embedded:
                slots.append(
                    slot.model_copy(
                        update={
                            "container_type": "table_cell",
                            "source_locator": cell.locator,
                            "table_index": table.table_index,
                            "row_index": row.row_index,
                            "column_index": cell.column_index,
                        }
                    )
                )
    return slots


def _profile_from_style(
    style: TextStyle,
    *,
    paragraph_alignment: str = "left",
    line_spacing: float = 0.0,
    space_before: float = 0.0,
    space_after: float = 0.0,
    cell_vertical_alignment: str | None = None,
    anchor_source: str,
) -> DestinationStyleProfile:
    return DestinationStyleProfile(
        east_asia_font=style.font_family_east_asia,
        latin_font=style.font_family_latin,
        font_size=style.font_size_pt,
        bold=style.bold,
        italic=style.italic,
        underline=style.underline,
        color=style.color,
        font_weight_role=style.font_weight_role,
        paragraph_alignment=paragraph_alignment,
        line_spacing=line_spacing,
        space_before=space_before,
        space_after=space_after,
        cell_vertical_alignment=cell_vertical_alignment,
        cell_margin_profile={"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0}
        if cell_vertical_alignment is not None else {},
        anchor_source=anchor_source,
    )


def _destination_style_for_slot(slot: SourceFillSlot, pages: Sequence[SourcePage]) -> DestinationStyleProfile:
    page = next((item for item in pages if item.page == slot.source_page), None)
    if page is None:
        return slot.destination_style
    if slot.container_type == "paragraph":
        paragraph = next((item for item in page.paragraphs
                          if item.locator.model_dump_json() == slot.source_locator.model_dump_json()), None)
        if paragraph is None:
            return slot.destination_style
        run = None
        cursor = 0
        for candidate in paragraph.runs:
            end = cursor + len(candidate.text)
            if slot.text_start is not None and slot.text_end is not None and (
                end > slot.text_start and cursor < max(slot.text_end, slot.text_start + 1)
            ):
                run = candidate
                break
            cursor = end
        run = run or next((candidate for candidate in reversed(paragraph.runs) if candidate.text.strip()), None)
        if run is None:
            return slot.destination_style
        semantic_alignment = paragraph.alignment
        compact = _compact(paragraph.text)
        if len(compact) > 40 or (re.search(r"[，。；？！]", paragraph.text) and not re.fullmatch(
            r"\s*[^：:\r\n]{1,24}[：:]\s*", paragraph.text
        )):
            semantic_alignment = "justify" if paragraph.alignment == "justify" else "left"
        return _profile_from_style(
            _text_style(run), paragraph_alignment=semantic_alignment,
            line_spacing=paragraph.line_spacing, space_before=paragraph.space_before,
            space_after=paragraph.space_after, anchor_source="DESTINATION_PLACEHOLDER_RUN",
        )

    table = next((item for item in page.tables if item.table_index == slot.table_index), None)
    if table is None or slot.row_index is None or slot.column_index is None:
        return slot.destination_style
    row = next((item for item in table.rows if item.row_index == slot.row_index), None)
    cell = next((item for item in row.cells if item.column_index == slot.column_index), None) if row else None
    style = None
    anchor_source = "SECTION_BODY_STYLE"
    if cell is not None:
        run = next((candidate for candidate in cell.runs if candidate.text.strip()), None)
        if run is not None:
            style, anchor_source = _text_style(run), "DESTINATION_CELL_RUN"
    if style is None and row is not None:
        # A paired label is the strongest source-backed anchor for an empty
        # value cell; it must win over unrelated fact-evidence typography.
        peers = [candidate for candidate in row.cells if candidate.column_index < slot.column_index
                 and candidate.text.strip() and candidate.runs]
        if peers:
            peer = max(peers, key=lambda candidate: candidate.column_index)
            run = next((candidate for candidate in peer.runs if candidate.text.strip()), peer.runs[0])
            style, anchor_source = _text_style(run), "SAME_ROW_SEMANTIC_PEER"
    profile = table.typography_profile
    if style is None and profile is not None:
        style = profile.body_style_by_column.get(slot.column_index)
        if style is not None:
            anchor_source = "DOMINANT_COLUMN_ROLE"
    if style is None and profile is not None and profile.body_style_by_role:
        style = next(iter(profile.body_style_by_role.values()))
        anchor_source = "DOMINANT_TABLE_BODY"
    style = style or TextStyle()
    return _profile_from_style(
        style, paragraph_alignment="left",
        line_spacing=max(style.font_size_pt * 1.05, 1.0),
        cell_vertical_alignment=cell.vertical_alignment if cell is not None else "center",
        anchor_source=anchor_source,
    )


def build_source_format_model(
    document: NormalizedDocument,
    bid_format: object,
) -> SourceFormatTemplate:
    """Build geometry-aware pages from a deterministic BidFormatTemplate."""

    if document.source_type != SourceType.PDF:
        return SourceFormatTemplate(
            source_heading=getattr(bid_format, "source_heading", None),
            source_locator=getattr(bid_format, "source_locator", None),
            source_type=document.source_type,
            layout_warnings=["DOCX source format has no PDF span geometry; use source DOCX editing path."],
        )

    source_locator = getattr(bid_format, "source_locator", None)
    start_page = getattr(source_locator, "page", None)
    if start_page is None:
        return SourceFormatTemplate(
            source_heading=getattr(bid_format, "source_heading", None),
            source_locator=source_locator,
            source_type=SourceType.PDF,
            layout_warnings=["Source format locator has no page."],
        )

    template_elements = getattr(bid_format, "elements", []) or []
    format_pages: list[int] = []
    for element in template_elements:
        locator = getattr(element, "locator", None)
        page = getattr(locator, "page", None)
        if page is not None:
            format_pages.append(int(page))
        table = getattr(element, "table", None)
        table_page = getattr(table, "page", None)
        if table_page is not None:
            format_pages.append(int(table_page))
    end_page = max(format_pages or [start_page])
    page_numbers = list(range(int(start_page), end_page + 1))
    chrome_items = detect_pdf_chrome(document, page_numbers)
    chrome_keys = {_chrome_key(item.text) for item in chrome_items}
    # Numeric page markers are valid source values in form cells (for example
    # ``90 日历天``). They are removed only when they occur at the page edge,
    # never by exact text matching against table-cell spans.
    chrome_span_keys = {
        _chrome_key(item.text)
        for item in chrome_items
        if item.reason != "numeric page marker at page edge"
    }
    chrome_locator_keys = {
        (
            int(item.page),
            getattr(item.locator, "block_index", None),
        )
        for item in chrome_items
    }
    chrome_regions: dict[int, list[tuple[float, float, float, float]]] = defaultdict(list)
    for page in document.pages:
        for block in page.blocks:
            if (page.page_number, block.block_index) in chrome_locator_keys:
                chrome_regions[page.page_number].append(block.bbox)
    source_table_keys = _table_keys_from_elements(template_elements)

    start_y: float | None = None
    start_block_index = getattr(source_locator, "block_index", None)
    if start_block_index is not None:
        start_page_model = next((p for p in document.pages if p.page_number == start_page), None)
        if start_page_model is not None:
            start_block = next(
                (block for block in start_page_model.blocks if block.block_index == start_block_index),
                None,
            )
            if start_block is not None:
                start_y = start_block.bbox[1]

    boundary_locator = getattr(bid_format, "boundary_locator", None)
    end_y: float | None = None
    if boundary_locator is not None and getattr(boundary_locator, "page", None) == end_page:
        boundary_page = next((p for p in document.pages if p.page_number == end_page), None)
        boundary_block = next(
            (
                block
                for block in (boundary_page.blocks if boundary_page is not None else [])
                if block.block_index == getattr(boundary_locator, "block_index", None)
            ),
            None,
        )
        if boundary_block is not None:
            end_y = boundary_block.bbox[1]

    pages: list[SourcePage] = []
    fill_slots: list[SourceFillSlot] = []
    warnings: list[str] = []
    artifact_report: dict[str, object] = {
        'isolated_artifact_candidates': 0,
        'artifact_spans_removed': 0,
        'table_spans_rejected_by_geometry': 0,
        'suspicious_short_cell_text': 0,
        'isolated_artifact_details': [],
        'artifact_spans_removed_details': [],
    }
    if chrome_items:
        warnings.append(f"Excluded {len(chrome_items)} repeated PDF chrome items by exact-text/geometry repetition.")

    for page_number in page_numbers:
        page = next((item for item in document.pages if item.page_number == page_number), None)
        if page is None:
            warnings.append(f"Missing normalized page {page_number} in source format range.")
            continue
        page_paragraphs: list[SourceParagraph] = []
        page_tables: list[SourceTable] = []
        page_elements: list[SourcePageElement] = []
        for block in page.blocks:
            if not block.text.strip():
                continue
            if page_number == start_page and start_y is not None and block.bbox[3] < start_y - 1.0:
                continue
            if page_number == end_page and end_y is not None and block.bbox[1] >= end_y:
                continue
            # A diagonal watermark can repeat the actual cover title.
            # Exclude only the geometry-verified occurrence, never every
            # block sharing its text.
            if (page_number, block.block_index) in chrome_locator_keys:
                continue
            if any(_bbox_contains(table.bbox, block.bbox) for table in document.tables if table.page == page_number):
                continue
            paragraph = _paragraph_from_block(block, page)
            paragraph.space_after = 0.0
            page_paragraphs.append(paragraph)
            page_elements.append(SourcePageElement(type="paragraph", index=len(page_paragraphs) - 1, bbox=paragraph.bbox))

        for table in document.tables:
            if table.page != page_number or (page_number, table.table_index) not in source_table_keys:
                continue
            if page_number == start_page and start_y is not None and table.bbox[3] < start_y - 1.0:
                continue
            if page_number == end_page and end_y is not None and table.bbox[1] >= end_y:
                continue
            source_table = _table_from_pdf(
                table,
                chrome_regions,
                chrome_keys=chrome_span_keys,
                page_spans=[
                    span
                    for block in page.blocks
                    for line in block.lines
                    for span in line.spans
                ],
                page_size=(page.width, page.height),
                artifact_report=artifact_report,
                page_lines=page.vector_lines,
            )
            page_tables.append(source_table)
            page_elements.append(SourcePageElement(type="table", index=len(page_tables) - 1, bbox=source_table.bbox))

        source_lines = [
            _source_line_from_pdf(line)
            for line in page.vector_lines
            if not any(_bbox_contains(table.bbox, line.bbox) for table in page_tables)
        ]

        page_elements.sort(key=lambda element: (element.bbox[1], element.bbox[0], element.type))
        classified_paragraphs: list[SourceParagraph] = []
        for paragraph in page_paragraphs:
            compact = _compact(paragraph.text)
            if page_number == int(start_page) and compact == _compact(getattr(bid_format, "source_heading", "") or ""):
                typography_role = TypographyRole.COVER_CHAPTER
            elif page_number == int(start_page) and compact in {"响应文件", "投标文件", "报价文件"}:
                typography_role = TypographyRole.COVER_DOCUMENT_TITLE
            elif page_number == int(start_page) and paragraph.alignment == "center" and max(
                (run.font_size for run in paragraph.runs), default=0.0
            ) >= 16.0:
                typography_role = TypographyRole.COVER_PROJECT_TITLE
            elif re.match(r"^\s*[^：:\r\n]{1,40}[：:]", paragraph.text):
                typography_role = TypographyRole.FORM_LABEL
            else:
                typography_role = TypographyRole.BODY
            classified_paragraphs.append(paragraph.model_copy(update={"typography_role": typography_role}))
        page_paragraphs = classified_paragraphs
        source_page = SourcePage(
            page=page_number,
            width=page.width or 595.0,
            height=page.height or 842.0,
            paragraphs=page_paragraphs,
            tables=page_tables,
            elements=page_elements,
            lines=source_lines,
            unmodeled_artwork_count=page.unmodeled_artwork_count,
            start_y=start_y if page_number == start_page else None,
            end_y=end_y if page_number == end_page else None,
        )
        pages.append(source_page)
        for paragraph in page_paragraphs:
            paragraph_slots = _paragraph_slots(paragraph, len(fill_slots))
            fill_slots.extend(paragraph_slots)
            if not paragraph_slots:
                vector_slot = _vector_rule_slot(paragraph, source_lines, len(fill_slots))
                if vector_slot is not None:
                    fill_slots.append(vector_slot)
                else:
                    implicit_slot = _label_only_slot(paragraph, len(fill_slots))
                    if implicit_slot is not None:
                        fill_slots.append(implicit_slot)
        for table in page_tables:
            fill_slots.extend(_table_slots(table, len(fill_slots)))
        if page.unmodeled_artwork_count:
            warnings.append(
                f"page={page_number}: {page.unmodeled_artwork_count} non-text PDF artwork item(s) "
                "were not reconstructed as editable artwork; visual review required."
            )

    if artifact_report['artifact_spans_removed']:
        warnings.append(
            f"Rejected {artifact_report['artifact_spans_removed']} table text artifact candidate(s) "
            "using source geometry/overlay evidence; manual inspection remains required."
        )

    # De-duplicate slots created by a parenthetical and label detector seeing
    # the same text.  Stable geometry + locator makes this deterministic.
    unique_slots: list[SourceFillSlot] = []
    seen_slots: set[tuple[str, str, str]] = set()
    for slot in fill_slots:
        key = (
            slot.source_locator.model_dump_json(),
            slot.original_text,
            ",".join(field.value for field in slot.allowed_fact_fields),
        )
        if key in seen_slots:
            continue
        seen_slots.add(key)
        unique_slots.append(slot)

    unique_slots = [slot.model_copy(update={
        "destination_style": _destination_style_for_slot(slot, pages)
    }) for slot in unique_slots]

    return SourceFormatTemplate(
        source_heading=getattr(bid_format, "source_heading", None),
        source_locator=source_locator,
        source_type=SourceType.PDF,
        source_pages=pages,
        fill_slots=unique_slots,
        chrome_items=chrome_items,
        layout_warnings=warnings,
        artifact_filter_report=artifact_report,
    )


__all__ = [
    "CharacterGeometry",
    "DestinationStyleProfile",
    "RaisedGlyph",
    "SourceCell",
    "SourceChromeItem",
    "SourceFillSlot",
    "SourceFormatTemplate",
    "SourcePage",
    "SourcePageElement",
    "SourceLine",
    "SourceParagraph",
    "SourceRow",
    "SourceRun",
    "SourceTable",
    "TableTypographyProfile",
    "TextStyle",
    "TypographyRole",
    "build_table_typography_profile",
    "build_source_format_model",
    "detect_pdf_chrome",
    "apply_source_glyph_repairs",
    "repair_pdf_font_name",
    "reconstruct_technical_runs",
]
