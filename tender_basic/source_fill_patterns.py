"""Round 5.6 source fill patterns.

A source fill pattern is *presentation*, not content: it records how the tender
source itself fills a field (a label plus an underlined blank, a bracketed
placeholder, a date pattern, an inline parenthetical, ...).  ProjectFacts supply
only the value; the pattern decides whether the placeholder stays, whether the
parentheses stay, whether the value keeps an underline, and how the blank is
aligned inside the source row.

The inference reads the source-format model's own slots and blanks, so it is
project independent: no case name, file name or page number is referenced.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: How a value occupies the source field.
REPLACE_PLACEHOLDER = "REPLACE_PLACEHOLDER"
APPEND_TO_LABEL = "APPEND_TO_LABEL"
FILL_BLANK = "FILL_BLANK"
REPLACE_BLANK_KEEP_PARENS = "REPLACE_BLANK_KEEP_PARENS"
PRESERVE_EMPTY_BLANK = "PRESERVE_EMPTY_BLANK"
COMPOSITE_FIELDS = "COMPOSITE_FIELDS"

REPLACEMENT_MODES = frozenset(
    {
        REPLACE_PLACEHOLDER,
        APPEND_TO_LABEL,
        FILL_BLANK,
        REPLACE_BLANK_KEEP_PARENS,
        PRESERVE_EMPTY_BLANK,
        COMPOSITE_FIELDS,
    }
)

#: Source blank kinds the pattern distinguishes.  Visually similar blanks are
#: never collapsed: an underscore run, an underlined empty region, a tab leader
#: and a drawn vector rule are different source constructs.
LITERAL_UNDERSCORE = "LITERAL_UNDERSCORE"
UNDERLINED_WHITESPACE = "UNDERLINED_WHITESPACE"
TAB_LEADER = "TAB_LEADER"
VECTOR_RULE = "VECTOR_RULE"
WHITESPACE_GAP = "WHITESPACE_GAP"
MIXED_BLANK = "MIXED_BLANK"
VALUE_WITH_UNDERLINE = "VALUE_WITH_UNDERLINE"
SOURCE_PLACEHOLDER_WITH_UNDERLINE = "SOURCE_PLACEHOLDER_WITH_UNDERLINE"

BLANK_KINDS = frozenset(
    {
        LITERAL_UNDERSCORE,
        UNDERLINED_WHITESPACE,
        TAB_LEADER,
        VECTOR_RULE,
        WHITESPACE_GAP,
        MIXED_BLANK,
    }
)

#: Blank kinds whose Word rendering must be a visible, editable line.
UNDERLINED_BLANK_KINDS = frozenset({LITERAL_UNDERSCORE, UNDERLINED_WHITESPACE, VECTOR_RULE, MIXED_BLANK})

#: How strongly the page-local source itself evidences a blank's kind.
#: ``DIRECT`` is a drawn rule or an underscore run the source really contains;
#: ``DERIVED`` is a whitespace gap measured from the source row; ``INVENTED``
#: means no page-local evidence exists and a semantic-role default was used.
EVIDENCE_DIRECT = "DIRECT"
EVIDENCE_DERIVED = "DERIVED"
EVIDENCE_INVENTED = "INVENTED"

_BLANK_KIND_BY_REPRESENTATION = {
    "LITERAL_UNDERSCORES": LITERAL_UNDERSCORE,
    "UNDERLINED_WHITESPACE": UNDERLINED_WHITESPACE,
    "TAB_LEADER": TAB_LEADER,
    "SOURCE_WHITESPACE_GAP": WHITESPACE_GAP,
    "VECTOR_LINE": VECTOR_RULE,
    "MIXED": MIXED_BLANK,
}


@dataclass
class SourceFillPattern:
    """How one source field is presented and filled."""

    locator: str = ""
    semantic_field: str = ""
    source_raw_text: str = ""
    placeholder_tokens: list[str] = field(default_factory=list)
    prefix_text: str = ""
    suffix_text: str = ""
    preserve_placeholder: bool = False
    preserve_parentheses: bool = False
    replacement_mode: str = PRESERVE_EMPTY_BLANK
    blank_kind: str = WHITESPACE_GAP
    source_blank_width: float = 0.0
    source_blank_start_x: float = 0.0
    source_blank_end_x: float = 0.0
    value_alignment: str = "left"
    font_family: str = ""
    font_size: float = 0.0
    bold: bool = False
    underline: bool = False
    underline_style: str = "single"
    paragraph_alignment: str = "left"
    first_line_indent: float = 0.0
    left_indent: float = 0.0
    right_indent: float = 0.0
    spacing_before: float = 0.0
    spacing_after: float = 0.0
    line_spacing_semantic: float = 0.0
    confidence: float = 0.0
    source_page: int = 0
    evidence: str = ""
    #: Page-local strength of this pattern's blank-kind evidence.
    evidence_kind: str = EVIDENCE_INVENTED
    composite_fields: list[str] = field(default_factory=list)

    @property
    def keeps_placeholder(self) -> bool:
        return self.preserve_placeholder

    @property
    def value_is_underlined(self) -> bool:
        """A value written into a source line keeps that visible line."""

        return self.blank_kind in UNDERLINED_BLANK_KINDS

    def style_payload(self) -> dict[str, Any]:
        """Typography the filled value inherits from the source pattern."""

        return {
            "font_family": self.font_family,
            "font_size": self.font_size,
            "bold": self.bold,
            "underline": self.value_is_underlined,
            "underline_style": self.underline_style,
        }

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["value_is_underlined"] = self.value_is_underlined
        return data


def blank_kind_for(representation_kind: Any, raw_placeholder: str = "") -> str:
    """Map a source blank representation to the Round 5.6 blank kind."""

    name = getattr(representation_kind, "value", representation_kind)
    kind = _BLANK_KIND_BY_REPRESENTATION.get(str(name), "")
    if not kind:
        kind = LITERAL_UNDERSCORE if "_" in (raw_placeholder or "") else WHITESPACE_GAP
    if kind == WHITESPACE_GAP and "_" in (raw_placeholder or ""):
        kind = LITERAL_UNDERSCORE
    return kind


def replacement_mode_for(
    *,
    blank_kind: str,
    has_prefix_label: bool,
    preserve_parentheses: bool,
    has_value: bool,
    composite_fields: list[str],
) -> str:
    if len(composite_fields) > 1:
        return COMPOSITE_FIELDS
    if not has_value:
        return PRESERVE_EMPTY_BLANK
    if preserve_parentheses:
        return REPLACE_BLANK_KEEP_PARENS
    if blank_kind in UNDERLINED_BLANK_KINDS:
        return FILL_BLANK
    return APPEND_TO_LABEL if has_prefix_label else REPLACE_PLACEHOLDER


def pattern_from_blank(
    blank: Any,
    *,
    semantic_field: str = "",
    source_raw_text: str = "",
    prefix_text: str = "",
    suffix_text: str = "",
    font_family: str = "",
    font_size: float = 0.0,
    bold: bool = False,
    paragraph_alignment: str = "left",
    line_spacing: float = 0.0,
    source_page: int = 0,
    composite_fields: list[str] | None = None,
    has_value: bool = False,
    confidence: float = 0.6,
) -> SourceFillPattern:
    """Build a pattern from one source-backed blank."""

    placeholder = str(getattr(blank, "raw_placeholder", "") or "")
    kind = blank_kind_for(getattr(blank, "representation_kind", ""), placeholder)
    tokens = [placeholder] if placeholder else []
    preserve_parentheses = placeholder.startswith(("（", "(")) and placeholder.endswith(("）", ")"))
    composite = list(composite_fields or [])
    locator = getattr(getattr(blank, "source_locator", None), "page", None)
    representation = str(
        getattr(getattr(blank, "representation_kind", ""), "value", "")
        or getattr(blank, "representation_kind", "")
    )
    if representation in {"VECTOR_LINE", "UNDERLINED_WHITESPACE", "MIXED"} or (
        representation == "LITERAL_UNDERSCORES" and placeholder
    ):
        evidence_kind = EVIDENCE_DIRECT
    elif representation == "SOURCE_WHITESPACE_GAP":
        evidence_kind = EVIDENCE_DERIVED
    else:
        evidence_kind = EVIDENCE_INVENTED
    return SourceFillPattern(
        locator=f"page {locator}" if locator else "",
        semantic_field=semantic_field,
        source_raw_text=source_raw_text or placeholder,
        placeholder_tokens=tokens,
        prefix_text=prefix_text,
        suffix_text=suffix_text,
        preserve_placeholder=bool(placeholder),
        preserve_parentheses=preserve_parentheses,
        replacement_mode=replacement_mode_for(
            blank_kind=kind,
            has_prefix_label=bool(prefix_text),
            preserve_parentheses=preserve_parentheses,
            has_value=has_value,
            composite_fields=composite,
        ),
        blank_kind=kind,
        evidence_kind=evidence_kind,
        source_blank_width=round(float(getattr(blank, "width_pt", 0.0) or 0.0), 2),
        source_blank_start_x=round(float(getattr(blank, "source_x0", 0.0) or 0.0), 2),
        source_blank_end_x=round(float(getattr(blank, "source_x1", 0.0) or 0.0), 2),
        font_family=font_family,
        font_size=round(float(font_size or 0.0), 2),
        bold=bool(bold),
        underline=kind in UNDERLINED_BLANK_KINDS,
        paragraph_alignment=paragraph_alignment,
        line_spacing_semantic=round(float(line_spacing or 0.0), 2),
        composite_fields=composite,
        confidence=confidence,
        source_page=int(source_page or locator or 0),
        evidence=f"{kind} @ x{getattr(blank, 'source_x0', 0):.1f}-{getattr(blank, 'source_x1', 0):.1f}",
    )


def infer_fill_patterns(template: Any, layouts: list[Any] | None = None) -> list[SourceFillPattern]:
    """Infer the fill patterns of every source row that carries a blank."""

    if template is None or not getattr(template, "source_pages", None):
        return []
    if layouts is None:
        from .page_layout import build_page_layout

        layouts = [build_page_layout(page) for page in template.source_pages]

    patterns: list[SourceFillPattern] = []
    for page, layout in zip(template.source_pages, layouts):
        for item in getattr(layout, "elements", []):
            for row in getattr(item, "row_geometries", []) or []:
                parts = list(getattr(row, "parts", []) or [])
                for blank in getattr(row, "blanks", []) or []:
                    field_name = str(getattr(blank, "semantic_slot", "") or "")
                    label = str(parts[0]) if parts else ""
                    tail = str(parts[-1]) if len(parts) > 2 else ""
                    size = float(
                        getattr(getattr(row, "item", None), "font_size_pt", 0.0) or 0.0
                    )
                    composite = (
                        [field_name, "lot_name"]
                        if field_name == "project_name"
                        and "标段" in f"{label}{getattr(row, 'item', None) and getattr(row.item, 'logical_text', '')}"
                        else [field_name]
                    )
                    patterns.append(
                        pattern_from_blank(
                            blank,
                            semantic_field=field_name,
                            source_raw_text=str(getattr(row.item, "logical_text", "") or ""),
                            prefix_text=label,
                            suffix_text=tail,
                            font_size=size,
                            paragraph_alignment=str(getattr(row.item, "alignment_hint", "") or "left"),
                            line_spacing=float(
                                getattr(getattr(row, "item", None), "line_pitch_pt", 0.0) or 0.0
                            ),
                            source_page=int(getattr(page, "page", 0) or 0),
                            composite_fields=composite,
                            has_value=False,
                        )
                    )
    return patterns


def pattern_index(patterns: list[SourceFillPattern]) -> dict[str, SourceFillPattern]:
    """Best pattern per semantic field (most confident, then widest blank)."""

    index: dict[str, SourceFillPattern] = {}
    for pattern in patterns:
        if not pattern.semantic_field:
            continue
        current = index.get(pattern.semantic_field)
        if current is None or (pattern.confidence, pattern.source_blank_width) > (
            current.confidence,
            current.source_blank_width,
        ):
            index[pattern.semantic_field] = pattern
    return index


__all__ = [
    "APPEND_TO_LABEL",
    "BLANK_KINDS",
    "COMPOSITE_FIELDS",
    "EVIDENCE_DERIVED",
    "EVIDENCE_DIRECT",
    "EVIDENCE_INVENTED",
    "FILL_BLANK",
    "LITERAL_UNDERSCORE",
    "MIXED_BLANK",
    "PRESERVE_EMPTY_BLANK",
    "REPLACE_BLANK_KEEP_PARENS",
    "REPLACE_PLACEHOLDER",
    "REPLACEMENT_MODES",
    "SOURCE_PLACEHOLDER_WITH_UNDERLINE",
    "SourceFillPattern",
    "TAB_LEADER",
    "UNDERLINED_BLANK_KINDS",
    "UNDERLINED_WHITESPACE",
    "VALUE_WITH_UNDERLINE",
    "VECTOR_RULE",
    "WHITESPACE_GAP",
    "blank_kind_for",
    "infer_fill_patterns",
    "pattern_from_blank",
    "pattern_index",
    "replacement_mode_for",
]
