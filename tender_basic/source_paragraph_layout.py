"""PARAGRAPH-FLOW-FIRST: the layout contract for paragraph-like Word content.

Architectural rule (``docs/V1_DECISIONS.md``, PARAGRAPH_FLOW_FIRST):

    Native Word paragraph layout is the PRIMARY layout mechanism.

    For paragraph-like source content, fidelity is expressed first by

        page / section geometry
        paragraph alignment
        left / right indent
        first-line / hanging indent
        line spacing
        paragraph before / after spacing
        font / style
        natural Word wrapping

    A tab stop is an EXCEPTION mechanism, reserved for a true discrete source
    field (several date slots, a signature/value column, an explicitly
    source-aligned multi-field row).  A tab must never be the engine that
    re-creates a paragraph's first-line indent, paragraph origin, body indent,
    centring, right alignment or ordinary continuation-line position.

    An absolute source x coordinate is EVIDENCE used to infer Word semantics.
    It does not automatically become a tab stop.

This module owns the model only.  It never classifies a rule, binds a fact or
chooses a Word style; it answers, for one paragraph-like source item:
*which Word paragraph formatting reproduces the source's own measured
geometry, and which of the source's x coordinates are paragraph formatting
rather than tab stops?*

Three quantities are kept deliberately separate:

``SourceParagraphLayoutContract``
    Every measured quantity a paragraph's placement depends on - the page
    frame, the paragraph's own body boundary, its first-line and continuation
    origins, its signed indents, its alignment, its line spacing, its
    before/after spacing and its font.  This is the primary Word layout plan.

``SourceParagraphAlignmentGeometry``
    The paragraph's own horizontal alignment, inferred from the geometry of its
    source rows (x0, x1) against the available source frame.  Never inferred
    from the paragraph's text.

``SourceCharacterIndent``
    A first-line indent that is a whole number of source characters.  Chinese
    body text indents its first line by two characters, and that is a Word
    ``w:firstLineChars``-equivalent semantic, not a tab and not a typographic
    accident of one paragraph's measurement.

Nothing here reads a page number, a rule id, a font name, a case id or a
literal string.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA = "source_paragraph_layout_contract/1"

# --------------------------------------------------------------------------- #
# Alignment classes
# --------------------------------------------------------------------------- #

#: The paragraph's rows start at the body boundary and end at their natural width.
ALIGNMENT_LEFT = "LEFT"

#: The paragraph's rows are positioned from the frame's centre.
ALIGNMENT_CENTER = "CENTER"

#: The paragraph's rows end at the frame's right edge and start at their natural x.
ALIGNMENT_RIGHT = "RIGHT"

#: The paragraph's non-final rows are stretched to the frame's right edge.
ALIGNMENT_JUSTIFY = "JUSTIFY"

#: Every row, including the final one, is stretched to the frame's right edge.
ALIGNMENT_DISTRIBUTE = "DISTRIBUTE"

ALIGNMENT_CLASSES = (
    ALIGNMENT_LEFT,
    ALIGNMENT_CENTER,
    ALIGNMENT_RIGHT,
    ALIGNMENT_JUSTIFY,
    ALIGNMENT_DISTRIBUTE,
)

#: The Word ``w:jc`` value each class asks for.
WORD_ALIGNMENT = {
    ALIGNMENT_LEFT: "left",
    ALIGNMENT_CENTER: "center",
    ALIGNMENT_RIGHT: "right",
    ALIGNMENT_JUSTIFY: "both",
    ALIGNMENT_DISTRIBUTE: "distribute",
}

#: Word alignment values that already own the paragraph's horizontal placement.
PARAGRAPH_ALIGNED = frozenset(WORD_ALIGNMENT.values())

# --------------------------------------------------------------------------- #
# Line spacing kinds (Word semantics first)
# --------------------------------------------------------------------------- #

LINE_SPACING_SINGLE = "SINGLE"
LINE_SPACING_ONE_POINT_FIVE = "ONE_POINT_FIVE"
LINE_SPACING_DOUBLE = "DOUBLE"
LINE_SPACING_EXACT = "EXACT"
LINE_SPACING_AT_LEAST = "AT_LEAST"

LINE_SPACING_KINDS = (
    LINE_SPACING_SINGLE,
    LINE_SPACING_ONE_POINT_FIVE,
    LINE_SPACING_DOUBLE,
    LINE_SPACING_EXACT,
    LINE_SPACING_AT_LEAST,
)

#: The Word auto multiple each named kind renders at.
LINE_SPACING_AUTO_MULTIPLE = {
    LINE_SPACING_SINGLE: 1.0,
    LINE_SPACING_ONE_POINT_FIVE: 1.5,
    LINE_SPACING_DOUBLE: 2.0,
}

# --------------------------------------------------------------------------- #
# First-line indent semantics
# --------------------------------------------------------------------------- #

#: The first row is indented by a whole number of source characters.
INDENT_CLASS_CHARACTERS = "FIRST_LINE_INDENT_CHARACTERS"

#: The first row is indented, but the measured offset is not a whole character.
INDENT_CLASS_MEASURED = "FIRST_LINE_INDENT_MEASURED"

#: Every row starts in one column.
INDENT_CLASS_NONE = "NO_SPECIAL_FIRST_LINE_INDENT"

#: The first row starts left of the rows it wraps into (a marker column).
INDENT_CLASS_HANGING = "HANGING_INDENT"

#: A character-counted indent must land this close to a whole character.
CHARACTER_INDENT_TOLERANCE_CHARS = 0.2

#: Below this many characters an indent is not a character indent at all.
MIN_CHARACTER_INDENT = 1.0

# --------------------------------------------------------------------------- #
# Geometry tolerances
# --------------------------------------------------------------------------- #

#: Two source x values closer than this are the same column.
COLUMN_TOLERANCE_PT = 2.0

#: How far inside the frame a row's own edge must be before its free edge counts
#: as deliberate placement rather than extraction noise.
ALIGNMENT_EDGE_TOLERANCE_PT = 3.0

#: A row is centred when its own two margins differ by no more than this.
ALIGNMENT_SYMMETRY_RATIO = 0.05

#: A centred row must be at least this far inside the frame on both sides,
#: otherwise a full-width left-aligned row would be read as centred.
MIN_CENTER_MARGIN_PT = 6.0


@dataclass(frozen=True)
class SourceCharacterIndent:
    """A first-line indent expressed in the source's own characters."""

    indent_pt: float
    font_size_pt: float
    characters: float | None
    classification: str
    evidence: str

    @property
    def is_character_indent(self) -> bool:
        return self.classification == INDENT_CLASS_CHARACTERS

    def as_dict(self) -> dict:
        return {
            "indent_pt": round(float(self.indent_pt), 2),
            "font_size_pt": round(float(self.font_size_pt), 2),
            "characters": (
                None if self.characters is None else round(float(self.characters), 3)
            ),
            "classification": self.classification,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class SourceParagraphAlignmentGeometry:
    """A paragraph's horizontal alignment, inferred from its own row geometry."""

    classification: str
    row_count: int
    frame_x0: float
    frame_x1: float
    left_gap_pt: float
    right_gap_pt: float
    center_error_pt: float
    confidence: float
    evidence: str

    @property
    def word_alignment(self) -> str:
        return WORD_ALIGNMENT[self.classification]

    @property
    def alignment_hint(self) -> str:
        """The hint the existing emitter already understands."""

        return {"both": "justify", "distribute": "justify"}.get(
            self.word_alignment, self.word_alignment
        )

    def as_dict(self) -> dict:
        return {
            "classification": self.classification,
            "row_count": int(self.row_count),
            "frame_x0": round(float(self.frame_x0), 2),
            "frame_x1": round(float(self.frame_x1), 2),
            "left_gap_pt": round(float(self.left_gap_pt), 2),
            "right_gap_pt": round(float(self.right_gap_pt), 2),
            "center_error_pt": round(float(self.center_error_pt), 2),
            "word_alignment": self.word_alignment,
            "confidence": round(float(self.confidence), 3),
            "evidence": self.evidence,
        }


def classify_source_paragraph_alignment_geometry(
    rows,
    *,
    frame_x0: float,
    frame_x1: float,
    body_x0: float | None = None,
    wrapped_rows_stretched: bool = False,
) -> SourceParagraphAlignmentGeometry:
    """Classify a paragraph's alignment from its own source row extents.

    ``rows`` is the paragraph's visual rows in reading order, each an ``(x0, x1)``
    pair in source coordinates.  ``frame_x0``/``frame_x1`` are the available
    source frame the rows were measured in.

    ``body_x0`` is the paragraph's *own* body boundary - the column its rows
    actually start from - and it is what makes this a paragraph-flow-first
    question rather than a page question.  A paragraph's rows can sit well inside
    the page frame (an indented block, a form column) and still be flush left
    *within their own column*; the frame alone cannot tell that from a centred
    line.  When a row starts at the paragraph's own body boundary, the
    paragraph's own layout explains its position and the alignment is left.

    The paragraph's *final* row is the one that states its alignment: a centred
    or right-aligned paragraph puts every row at the same alignment, while a
    justified paragraph's final row is short.  ``wrapped_rows_stretched`` is the
    independently measured justification evidence (the wrapped rows' glyph
    advances exceed the font's natural advance); it is never guessed from the
    row's width, because a short final row and a stretched row look alike.

    A single-row paragraph carries much weaker evidence than a wrapped one, so
    it reports a lower confidence rather than being forced into a class.
    """

    frame_x0 = float(frame_x0)
    frame_x1 = float(frame_x1)
    width = max(1.0, frame_x1 - frame_x0)
    explained_x0 = frame_x0 if body_x0 is None else float(body_x0)
    pairs = [
        (float(row[0]), float(row[1]))
        for row in rows or ()
        if row is not None and len(row) >= 2 and float(row[1]) > float(row[0])
    ]
    if not pairs:
        return SourceParagraphAlignmentGeometry(
            classification=ALIGNMENT_LEFT,
            row_count=0,
            frame_x0=frame_x0,
            frame_x1=frame_x1,
            left_gap_pt=0.0,
            right_gap_pt=0.0,
            center_error_pt=width / 2.0,
            confidence=0.0,
            evidence="the paragraph has no measured source row, so no alignment is claimed",
        )

    left_gap = min(pair[0] for pair in pairs) - frame_x0
    right_gap = frame_x1 - max(pair[1] for pair in pairs)
    last_x0, last_x1 = pairs[-1]
    last_left = last_x0 - frame_x0
    last_right = frame_x1 - last_x1
    last_center = (last_x0 + last_x1) / 2.0
    frame_center = (frame_x0 + frame_x1) / 2.0
    center_error = abs(last_center - frame_center)
    edge = ALIGNMENT_EDGE_TOLERANCE_PT
    # Symmetry is a small fraction of the measure, floored at the extraction
    # tolerance: a centred row is *deliberately* placed, so the test must not
    # admit a row that merely happens to sit near the middle.
    symmetry = max(MIN_CENTER_MARGIN_PT, width * ALIGNMENT_SYMMETRY_RATIO)
    # The paragraph's own column explains a row that starts there.
    at_own_body = abs(last_x0 - explained_x0) <= max(COLUMN_TOLERANCE_PT, edge)


    # JUSTIFY / DISTRIBUTE need the stretched-advance measurement: reaching the
    # right edge is *implied* by stretching, never proof of it.
    if len(pairs) >= 2 and wrapped_rows_stretched:
        wrapped = pairs[:-1]
        wrapped_reach_right = all(
            frame_x1 - pair[1] <= edge + 3.0 for pair in wrapped
        )
        if wrapped_reach_right:
            last_reaches_right = last_right <= edge + 3.0
            classification = (
                ALIGNMENT_DISTRIBUTE if last_reaches_right else ALIGNMENT_JUSTIFY
            )
            return SourceParagraphAlignmentGeometry(
                classification=classification,
                row_count=len(pairs),
                frame_x0=frame_x0,
                frame_x1=frame_x1,
                left_gap_pt=left_gap,
                right_gap_pt=right_gap,
                center_error_pt=center_error,
                confidence=0.8,
                evidence=(
                    "the paragraph's wrapped rows advance their glyphs further "
                    "apart than the font's natural advance and reach the right "
                    "edge of the measure, so the source stretched the line"
                    + (
                        "; its final row reaches the same edge, which is "
                        "distribution rather than justification"
                        if classification == ALIGNMENT_DISTRIBUTE
                        else ""
                    )
                ),
            )

    if (
        not at_own_body
        and last_left >= symmetry
        and last_right >= symmetry
        and center_error <= symmetry
    ):
        return SourceParagraphAlignmentGeometry(
            classification=ALIGNMENT_CENTER,
            row_count=len(pairs),
            frame_x0=frame_x0,
            frame_x1=frame_x1,
            left_gap_pt=left_gap,
            right_gap_pt=right_gap,
            center_error_pt=center_error,
            confidence=0.85 if len(pairs) >= 2 else 0.6,
            evidence=(
                "the paragraph's rows sit clear of both frame edges and their own "
                "centre coincides with the frame centre, which only a centred row "
                "produces"
            ),
        )

    if not at_own_body and last_right <= edge and last_left > symmetry:
        return SourceParagraphAlignmentGeometry(
            classification=ALIGNMENT_RIGHT,
            row_count=len(pairs),
            frame_x0=frame_x0,
            frame_x1=frame_x1,
            left_gap_pt=left_gap,
            right_gap_pt=right_gap,
            center_error_pt=center_error,
            confidence=0.85 if len(pairs) >= 2 else 0.6,
            evidence=(
                "the paragraph's final row ends at the frame's right edge while "
                "starting clear of its left edge, which is a right-aligned row"
            ),
        )

    return SourceParagraphAlignmentGeometry(
        classification=ALIGNMENT_LEFT,
        row_count=len(pairs),
        frame_x0=frame_x0,
        frame_x1=frame_x1,
        left_gap_pt=left_gap,
        right_gap_pt=right_gap,
        center_error_pt=center_error,
        confidence=0.7 if len(pairs) >= 2 else 0.4,
        evidence=(
            "the paragraph's rows start at the frame's own left edge and are not "
            "stretched to its right edge, so the source set them flush left"
        ),
    )


def classify_source_character_indent(
    indent_pt: float,
    font_size_pt: float,
) -> SourceCharacterIndent:
    """Express a measured first-line indent in the source's own characters.

    Chinese body text indents its first line by two characters, which Word states
    natively as ``w:firstLineChars``.  A measured offset that lands on a whole
    character within :data:`CHARACTER_INDENT_TOLERANCE_CHARS` is therefore a
    character indent; anything else is a measured indent and is delivered in
    points.  Nothing is forced to a whole character: an indent the source really
    drew at 21 pt is not "2 characters" because 2 characters would be tidier.
    """

    indent = float(indent_pt or 0.0)
    size = max(1.0, float(font_size_pt or 0.0))
    if indent <= COLUMN_TOLERANCE_PT:
        return SourceCharacterIndent(
            indent_pt=indent,
            font_size_pt=size,
            characters=None,
            classification=INDENT_CLASS_NONE,
            evidence="the paragraph's first row is not indented from its body boundary",
        )
    if indent < 0.0:
        return SourceCharacterIndent(
            indent_pt=indent,
            font_size_pt=size,
            characters=None,
            classification=INDENT_CLASS_HANGING,
            evidence=(
                "the paragraph's first row starts left of the rows it wraps into, "
                "so the offset is a hanging indent rather than a first-line indent"
            ),
        )
    characters = indent / size
    if (
        characters >= MIN_CHARACTER_INDENT
        and abs(characters - round(characters)) <= CHARACTER_INDENT_TOLERANCE_CHARS
    ):
        return SourceCharacterIndent(
            indent_pt=indent,
            font_size_pt=size,
            characters=float(round(characters)),
            classification=INDENT_CLASS_CHARACTERS,
            evidence=(
                f"the first row is indented {indent:.2f} pt at a {size:.2f} pt font, "
                f"which is {round(characters)} source characters"
            ),
        )
    return SourceCharacterIndent(
        indent_pt=indent,
        font_size_pt=size,
        characters=characters,
        classification=INDENT_CLASS_MEASURED,
        evidence=(
            f"the first row is indented {indent:.2f} pt, which is {characters:.3f} "
            f"source characters at a {size:.2f} pt font - not a whole character, so "
            "the measured point offset is delivered"
        ),
    )


@dataclass(frozen=True)
class SourceParagraphLayoutContract:
    """The PRIMARY Word layout plan for one paragraph-like source item.

    Every field is a measured source quantity or a semantic class derived from
    one.  The contract is the single place a paragraph's placement is decided, so
    a paragraph cannot be indented by one architecture and wrapped by another.
    """

    #: Page geometry.
    page_width: float = 0.0
    page_height: float = 0.0
    section_left_margin: float = 0.0
    section_right_margin: float = 0.0
    section_top_margin: float = 0.0
    section_bottom_margin: float = 0.0
    #: The paragraph's own body boundary (where its wrapped rows return to).
    paragraph_body_x0: float = 0.0
    paragraph_body_x1: float = 0.0
    #: Where the paragraph's first row and its continuation rows start.
    first_line_x0: float = 0.0
    continuation_x0: float | None = None
    #: Word indents, in points, relative to the section text margin.
    left_indent_pt: float = 0.0
    right_indent_pt: float = 0.0
    first_line_indent_pt: float = 0.0
    hanging_indent_pt: float = 0.0
    #: Horizontal alignment.
    alignment: str = ALIGNMENT_LEFT
    alignment_confidence: float = 0.0
    #: Line spacing, as a Word semantic first.
    line_spacing_kind: str = LINE_SPACING_SINGLE
    line_spacing_value: float = 1.0
    #: Paragraph spacing.
    space_before: float = 0.0
    space_after: float = 0.0
    #: Font.
    font_family: str = ""
    font_size: float = 0.0
    #: Semantic first-line indent.
    first_line_indent_class: str = INDENT_CLASS_NONE
    first_line_indent_chars: float | None = None
    #: Evidence.
    indent_evidence: str = ""
    alignment_evidence: str = ""
    spacing_evidence: str = ""
    source_evidence: str = ""
    confidence: float = 0.0

    @property
    def word_alignment(self) -> str:
        return WORD_ALIGNMENT.get(self.alignment, "left")

    @property
    def alignment_hint(self) -> str:
        """This contract's alignment in the emitter's own hint vocabulary.

        Word spells justified text ``both`` and distributed text ``distribute``;
        the builder's hints are ``left``/``center``/``right``/``justify``, so the
        two Word-only values collapse to ``justify`` here.  The contract itself
        keeps the distinction, because distribution and justification are
        different source statements about the paragraph's final row.
        """

        return {"both": "justify", "distribute": "justify"}.get(
            self.word_alignment, self.word_alignment
        )

    @property
    def word_first_line_indent_pt(self) -> float:
        """Word's signed ``w:ind/@w:firstLine``: positive indent, negative hanging."""

        return round(self.first_line_indent_pt - self.hanging_indent_pt, 4)

    @property
    def usable_text_width_pt(self) -> float:
        return max(
            0.0,
            float(self.paragraph_body_x1) - float(self.paragraph_body_x0),
        )

    @property
    def uses_paragraph_positioning(self) -> bool:
        """Whether this contract's placement is owned by paragraph formatting.

        It always is: the contract has no tab stop, because a paragraph-like
        item's placement is paragraph formatting by construction.
        """

        return True

    def as_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "page_width": round(float(self.page_width), 2),
            "page_height": round(float(self.page_height), 2),
            "section_left_margin": round(float(self.section_left_margin), 2),
            "section_right_margin": round(float(self.section_right_margin), 2),
            "section_top_margin": round(float(self.section_top_margin), 2),
            "section_bottom_margin": round(float(self.section_bottom_margin), 2),
            "paragraph_body_x0": round(float(self.paragraph_body_x0), 2),
            "paragraph_body_x1": round(float(self.paragraph_body_x1), 2),
            "first_line_x0": round(float(self.first_line_x0), 2),
            "continuation_x0": (
                None
                if self.continuation_x0 is None
                else round(float(self.continuation_x0), 2)
            ),
            "left_indent_pt": round(float(self.left_indent_pt), 4),
            "right_indent_pt": round(float(self.right_indent_pt), 4),
            "first_line_indent_pt": round(float(self.first_line_indent_pt), 4),
            "hanging_indent_pt": round(float(self.hanging_indent_pt), 4),
            "word_first_line_indent_pt": round(self.word_first_line_indent_pt, 4),
            "alignment": self.alignment,
            "word_alignment": self.word_alignment,
            "alignment_confidence": round(float(self.alignment_confidence), 3),
            "line_spacing_kind": self.line_spacing_kind,
            "line_spacing_value": round(float(self.line_spacing_value), 4),
            "space_before": round(float(self.space_before), 2),
            "space_after": round(float(self.space_after), 2),
            "font_family": self.font_family,
            "font_size": round(float(self.font_size), 2),
            "first_line_indent_class": self.first_line_indent_class,
            "first_line_indent_chars": (
                None
                if self.first_line_indent_chars is None
                else round(float(self.first_line_indent_chars), 3)
            ),
            "paragraph_positioning_owned_by": "WORD_PARAGRAPH_FORMATTING",
            "indent_evidence": self.indent_evidence,
            "alignment_evidence": self.alignment_evidence,
            "spacing_evidence": self.spacing_evidence,
            "source_evidence": self.source_evidence,
            "confidence": round(float(self.confidence), 3),
        }


def classify_line_spacing_semantics(
    font_size_pt: float,
    baseline_pitch_pt: float = 0.0,
) -> tuple[str, float, str]:
    """Classify a source baseline pitch into a Word-native spacing semantic.

    Returns ``(kind, value, evidence)``.  A pitch within tolerance of the font's
    own single line is SINGLE; a pitch that matches 1.5- or 2-line spacing is that
    named multiple; anything else is a MULTIPLE auto value.  Nothing is ever
    delivered as an exact height: Word's auto spacing is quoted as a fraction of
    the font's own natural line height, so a source pitch is matched relatively.
    """

    from .page_layout import (
        SINGLE_LINE_PITCH_TOLERANCE_PT,
        infer_semantic_line_spacing,
    )

    size = max(1.0, float(font_size_pt or 10.5))
    pitch = max(0.0, float(baseline_pitch_pt or 0.0))
    profile = infer_semantic_line_spacing(size, pitch)
    multiple = float(profile.word_value or 1.0)
    if pitch <= 0.0 or abs(pitch - size) <= SINGLE_LINE_PITCH_TOLERANCE_PT:
        return (
            LINE_SPACING_SINGLE,
            1.0,
            "the source paragraph has no baseline pitch beyond single spacing",
        )
    for kind, value in LINE_SPACING_AUTO_MULTIPLE.items():
        if abs(multiple - value) <= 1e-9:
            return (
                kind,
                value,
                f"the source baseline pitch {pitch:.2f} pt at a {size:.2f} pt font "
                f"maps to Word's native {kind} spacing",
            )
    return (
        "MULTIPLE",
        round(multiple, 4),
        f"the source baseline pitch {pitch:.2f} pt at a {size:.2f} pt font maps to "
        f"a Word auto multiple of {multiple:.3f}, which is not a named Word rhythm",
    )


def _row_extents(rows) -> list[tuple[float, float]]:
    """Visible ``(x0, x1)`` of each source visual row, in reading order."""

    extents: list[tuple[float, float]] = []
    for row in rows or ():
        boxes = [
            (float(span.bbox[0]), float(span.bbox[2]))
            for span in getattr(row, "spans", ()) or ()
            if str(getattr(span, "text", "") or "").strip()
            and len(getattr(span, "bbox", ()) or ()) >= 4
        ]
        if not boxes:
            bbox = getattr(row, "bbox", None)
            if bbox is not None and len(bbox) >= 4 and float(bbox[2]) > float(bbox[0]):
                boxes = [(float(bbox[0]), float(bbox[2]))]
        if boxes:
            extents.append(
                (min(box[0] for box in boxes), max(box[1] for box in boxes))
            )
    return extents


def _first_line_indent_class(hint: str, character_indent: SourceCharacterIndent) -> str:
    """The semantic class of a paragraph's first-line indent.

    The source indent classifier's own verdict decides *whether* the first row is
    indented; the character measurement then decides *how* that indent is stated.
    A hanging indent is never restated as a character indent, because Word carries
    the two in one signed attribute and confusing them mirrors the paragraph.
    """

    if hint == "HANGING_INDENT":
        return INDENT_CLASS_HANGING
    if hint == "NO_SPECIAL_FIRST_LINE_INDENT":
        return INDENT_CLASS_NONE
    return character_indent.classification


def derive_source_paragraph_layout_contract(
    item,
    *,
    frame=None,
    page_content_x0: float = 0.0,
    page_content_x1: float | None = None,
    page_width: float | None = None,
    page_height: float | None = None,
    scale: float = 1.0,
    space_before: float = 0.0,
    space_after: float = 0.0,
    source_rows=None,
) -> SourceParagraphLayoutContract:
    """Build the primary Word layout plan for one paragraph-like source item.

    ``item`` is any object carrying the page layout's paragraph evidence
    (``bbox``, ``source_lines``, ``font_size_pt``, ``line_pitch_pt``,
    ``alignment_hint``, ``source_indent``, ``source_alignment``).  ``frame`` is a
    :class:`SourceSectionPageFrame` when the caller has one.
    """

    from .source_paragraph_indent import classify_paragraph_source_indent
    from .source_paragraph_indent import source_row_origins

    if frame is not None:
        page_content_x0 = float(getattr(frame, "left_margin", page_content_x0) or page_content_x0)
        page_content_x1 = float(
            getattr(frame, "body_x1", page_content_x1 if page_content_x1 is not None else 0.0)
        )
        page_width = float(getattr(frame, "page_width", page_width or 0.0) or 0.0)
        page_height = float(getattr(frame, "page_height", page_height or 0.0) or 0.0)
        section_right_margin = float(getattr(frame, "right_margin", 0.0) or 0.0)
        section_top_margin = float(getattr(frame, "top_body_frame", 0.0) or 0.0)
        section_bottom_margin = float(getattr(frame, "bottom_body_frame", 0.0) or 0.0)
    else:
        page_width = float(page_width or 0.0)
        page_height = float(page_height or 0.0)
        if page_content_x1 is None:
            page_content_x1 = page_width - float(page_content_x0)
        section_right_margin = max(0.0, page_width - float(page_content_x1))
        section_top_margin = 0.0
        section_bottom_margin = 0.0

    body_x0 = float(page_content_x0)
    body_x1 = float(page_content_x1)
    bbox = getattr(item, "bbox", None) or (body_x0, 0.0, body_x1, 0.0)
    lines = (
        list(source_rows)
        if source_rows is not None
        else list(getattr(item, "source_lines", ()) or ())
    )
    origins = source_row_origins(lines) if lines else []
    row_xs = [origin for origin, _y in origins]
    extents = _row_extents(lines) or [(float(bbox[0]), float(bbox[2]))]

    if getattr(item, "source_indent", None) is not None:
        indent = item.source_indent
    else:
        try:
            indent = classify_paragraph_source_indent(item)
        except Exception:  # pragma: no cover - defensive geometry boundary
            indent = None
    if indent is not None:
        body_left = float(getattr(indent, "body_left_x", body_x0) or body_x0)
        first_x = float(getattr(indent, "first_line_x", body_left) or body_left)
        continuation = getattr(indent, "continuation_x", None)
        first_line_indent = float(getattr(indent, "first_line_indent_pt", 0.0) or 0.0)
        hanging = float(getattr(indent, "hanging_indent_pt", 0.0) or 0.0)
        indent_class_hint = str(getattr(indent, "classification", "") or "")
        indent_evidence = str(getattr(indent, "evidence", "") or "")
    else:
        body_left = row_xs[0] if row_xs else float(bbox[0])
        first_x = row_xs[0] if row_xs else float(bbox[0])
        continuation = min(row_xs[1:]) if len(row_xs) > 1 else None
        first_line_indent = max(0.0, first_x - body_left)
        hanging = max(0.0, body_left - first_x)
        indent_class_hint = ""
        indent_evidence = (
            "no source indent classification is available, so the paragraph's own "
            "first row origin is kept"
        )

    left_indent = round(body_left - body_x0, 4)
    right_extent = max(extent[1] for extent in extents)
    right_indent = 0.0
    overhang = right_extent - body_x1
    if overhang > COLUMN_TOLERANCE_PT:
        # A source line that runs past the stable body frame is element-level
        # geometry: the paragraph keeps its source extent through a Word-native
        # negative right indent instead of moving the section margin.
        right_indent = round(-overhang, 4)

    size = max(1.0, float(getattr(item, "font_size_pt", 0.0) or 0.0) * float(scale or 1.0))
    character_indent = classify_source_character_indent(
        max(first_line_indent, 0.0), size
    )

    wrapped_stretched = bool(
        getattr(getattr(item, "source_alignment", None), "justified", False)
    )
    # THE PARAGRAPH'S OWN COLUMN EXPLAINS ITS OWN FIRST ROW.  A body boundary is
    # only "explained" when the paragraph's *own wrapped rows* measured it: a
    # single-row paragraph with no measured continuation has its body boundary
    # defaulted to that row's own start, and reading that as an explanation would
    # make every single-row paragraph trivially left-aligned.
    measured_body_boundary = bool(
        getattr(indent, "measured_continuation", False) and len(extents) >= 2
    )
    alignment = classify_source_paragraph_alignment_geometry(
        extents,
        frame_x0=body_x0,
        frame_x1=body_x1,
        body_x0=body_left if measured_body_boundary else None,
        wrapped_rows_stretched=wrapped_stretched,
    )
    hint = str(getattr(item, "alignment_hint", "") or "").lower()
    if hint == "center" and alignment.classification != ALIGNMENT_CENTER:
        # A role whose own placement decision is stronger than the row-extent
        # inference (a centred heading, a centred form line) keeps its role.  The
        # geometry classifier still records what the rows themselves show.
        alignment = SourceParagraphAlignmentGeometry(
            classification=ALIGNMENT_CENTER,
            row_count=alignment.row_count,
            frame_x0=alignment.frame_x0,
            frame_x1=alignment.frame_x1,
            left_gap_pt=alignment.left_gap_pt,
            right_gap_pt=alignment.right_gap_pt,
            center_error_pt=alignment.center_error_pt,
            confidence=max(0.5, alignment.confidence),
            evidence=(
                "the paragraph's own role places it from the frame centre; the rows "
                "are consistent with that placement"
            ),
        )

    spacing_kind, spacing_value, spacing_evidence = classify_line_spacing_semantics(
        getattr(item, "font_size_pt", 0.0),
        float(getattr(item, "line_pitch_pt", 0.0) or 0.0) * float(scale or 1.0),
    )

    return SourceParagraphLayoutContract(
        page_width=round(page_width, 4),
        page_height=round(page_height, 4),
        section_left_margin=round(body_x0, 4),
        section_right_margin=round(section_right_margin, 4),
        section_top_margin=round(section_top_margin, 4),
        section_bottom_margin=round(section_bottom_margin, 4),
        paragraph_body_x0=round(body_left, 4),
        paragraph_body_x1=round(body_x1, 4),
        first_line_x0=round(first_x, 4),
        continuation_x0=(
            None if continuation is None else round(float(continuation), 4)
        ),
        left_indent_pt=left_indent,
        right_indent_pt=right_indent,
        first_line_indent_pt=round(max(first_line_indent, 0.0), 4),
        hanging_indent_pt=round(max(hanging, 0.0), 4),
        alignment=alignment.classification,
        alignment_confidence=round(alignment.confidence, 4),
        line_spacing_kind=spacing_kind,
        line_spacing_value=spacing_value,
        space_before=round(float(space_before or 0.0), 4),
        space_after=round(float(space_after or 0.0), 4),
        font_family=str(getattr(item, "font_name", "") or ""),
        font_size=round(size, 4),
        first_line_indent_class=_first_line_indent_class(
            indent_class_hint, character_indent
        ),
        first_line_indent_chars=character_indent.characters,
        indent_evidence=indent_evidence,
        alignment_evidence=alignment.evidence,
        spacing_evidence=spacing_evidence,
        source_evidence=(
            f"rows={len(extents)};body_x0={body_left:.2f};body_x1={body_x1:.2f};"
            f"font_size={size:.2f}"
        ),
        confidence=round(
            min(
                1.0,
                0.5 * float(getattr(indent, "row_count", 1) > 0)
                + 0.5 * alignment.confidence,
            ),
            4,
        ),
    )


def apply_source_paragraph_layout(paragraph_format, contract: SourceParagraphLayoutContract):
    """Write a contract onto a Word paragraph's own formatting.

    This is the paragraph-flow-first application: alignment, both indents, line
    spacing and paragraph spacing are Word paragraph properties.  No tab stop is
    written, because the contract states that a paragraph-like item's placement
    is owned by paragraph formatting.
    """

    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    paragraph_format.left_indent = Pt(contract.left_indent_pt)
    paragraph_format.right_indent = Pt(contract.right_indent_pt)
    paragraph_format.first_line_indent = Pt(contract.word_first_line_indent_pt)
    paragraph_format.space_before = Pt(contract.space_before)
    paragraph_format.space_after = Pt(contract.space_after)
    if contract.line_spacing_kind in LINE_SPACING_AUTO_MULTIPLE:
        paragraph_format.line_spacing = LINE_SPACING_AUTO_MULTIPLE[
            contract.line_spacing_kind
        ]
    else:
        paragraph_format.line_spacing = float(contract.line_spacing_value or 1.0)
    paragraph_format.alignment = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "both": WD_ALIGN_PARAGRAPH.JUSTIFY,
        "distribute": WD_ALIGN_PARAGRAPH.DISTRIBUTE,
    }.get(contract.word_alignment, WD_ALIGN_PARAGRAPH.LEFT)
    return paragraph_format


# --------------------------------------------------------------------------- #
# Positioning-tab audit (PARAGRAPH_FLOW_FIRST architecture gate)
# --------------------------------------------------------------------------- #

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: Diagnostic counter names the gate reads.
POSITIONING_TAB_COUNT = "PARAGRAPH_POSITIONING_TAB_COUNT"
CENTER_HACK_COUNT = "CENTER_ALIGNMENT_HACK_COUNT"
RIGHT_HACK_COUNT = "RIGHT_ALIGNMENT_HACK_COUNT"
FIRST_LINE_TAB_HACK_COUNT = "FIRST_LINE_TAB_HACK_COUNT"

#: A leading whitespace run this long is a placement attempt, not prose spacing.
MIN_HACK_WHITESPACE_UNITS = 2


def _paragraph_prefix(paragraph):
    """The paragraph's leading content before its first visible glyph.

    Returns ``(tabs, space_units, has_visible_text)`` where ``space_units`` counts
    a normal space as a quarter em and an ideographic space as one em, matching the
    emitter's own advance model.

    Only *run content* is read.  A tab stop declared in ``w:pPr/w:tabs`` is a
    position the paragraph offers Word, not a cursor move the paragraph performs,
    and counting it would turn every paragraph that declares its own stops into a
    positioning hack.
    """

    tabs = 0
    units = 0.0
    visible = False
    for run in paragraph.findall(W + "r"):
        for node in run.iter():
            if node.tag == W + "tab":
                if not visible:
                    tabs += 1
                continue
            if node.tag in (W + "br", W + "cr"):
                # A break ends the line under inspection: nothing it carries can
                # be a leading placement of this line's first text.
                visible = True
                continue
            if node.tag != W + "t":
                continue
            if visible:
                continue
            for character in node.text or "":
                if character == "\t":
                    tabs += 1
                elif character == "\u3000":
                    units += 1.0
                elif character.isspace():
                    units += 0.25
                else:
                    visible = True
                    break
    return tabs, units, visible


def _document_frame(root) -> tuple[float, float]:
    """``(section_left_margin_pt, usable_text_width_pt)`` of the document.

    Read from the document's own ``w:sectPr``: the audit works on the parsed
    OOXML, so it must not depend on a python-docx object's part graph.  A
    document with no explicit ``w:pgMar`` keeps Word's defaults (one inch on
    Letter), which is what Word itself would lay the text out against.
    """

    page_width = 612.0
    left = 72.0
    right = 72.0
    section = root.find(".//" + W + "sectPr")
    if section is not None:
        size = section.find(W + "pgSz")
        if size is not None and size.get(W + "w"):
            try:
                page_width = float(size.get(W + "w")) / 20.0
            except ValueError:
                page_width = 612.0
        margins = section.find(W + "pgMar")
        if margins is not None:
            for attribute, fallback in ((W + "left", left), (W + "right", right)):
                raw = margins.get(attribute)
                try:
                    value = float(raw) / 20.0
                except (TypeError, ValueError):
                    value = fallback
                if attribute == W + "left":
                    left = value
                else:
                    right = value
    return left, max(1.0, page_width - left - right)


def _text_advance(text: str, size_pt: float) -> float:
    total = 0.0
    for character in text or "":
        if character == "\u3000":
            total += size_pt
        elif character.isspace():
            total += size_pt * 0.25
        elif ord(character) > 0x2E80:
            total += size_pt
        else:
            total += size_pt * 0.5
    return total


def audit_docx_paragraph_positioning(path) -> dict:
    """Audit an emitted DOCX for paragraphs positioned by tabs instead of formatting.

    Four counters are produced, all of which the paragraph-flow-first architecture
    requires to be zero:

    ``PARAGRAPH_POSITIONING_TAB_COUNT``
        paragraphs whose first content element is a tab that re-creates the
        paragraph's own origin or indent (a default-tab fallthrough or a
        first-line indent written as a tab);
    ``CENTER_ALIGNMENT_HACK_COUNT`` / ``RIGHT_ALIGNMENT_HACK_COUNT``
        paragraphs that reach the frame's centre or right edge with a leading
        whitespace run while their own alignment property does not say so;
    ``FIRST_LINE_TAB_HACK_COUNT``
        paragraphs whose first tab stop sits at or before their own effective line
        origin - the exact signature of a first-line indent, or a paragraph
        origin, written as a tab.  Both the stop and the paragraph's indents are
        read on the same ruler (the section text margin), which is the origin Word
        measures ``w:tab/@w:pos`` from.

    Nothing here reads a page number, a text literal or a case identity.
    """

    from lxml import etree
    from zipfile import ZipFile

    counters = {
        POSITIONING_TAB_COUNT: 0,
        CENTER_HACK_COUNT: 0,
        RIGHT_HACK_COUNT: 0,
        FIRST_LINE_TAB_HACK_COUNT: 0,
    }
    records: list[dict] = []
    with ZipFile(path) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    section_left_pt, frame_width = _document_frame(root)
    for index, paragraph in enumerate(root.iter(W + "p")):
        tabs, space_units, visible = _paragraph_prefix(paragraph)
        if not visible and tabs == 0 and space_units == 0.0:
            continue
        properties = paragraph.find(W + "pPr")
        declared = []
        alignment = None
        left_indent = 0.0
        first_line_indent = 0.0
        if properties is not None:
            jc = properties.find(W + "jc")
            alignment = None if jc is None else jc.get(W + "val")
            ind = properties.find(W + "ind")
            if ind is not None:
                left_indent = float(ind.get(W + "left") or 0.0)
                first_line_indent = float(ind.get(W + "firstLine") or 0.0)
            declared = [
                float(tab.get(W + "pos") or 0.0)
                for tab in properties.iter(W + "tab")
            ]
        # ``w:tab/@w:pos`` and the paragraph's own indents are both measured from
        # the same ruler origin (the section text margin - the frozen
        # ``WORD_TAB_REFERENCE_MODEL``), so the two are directly comparable and
        # neither carries the section margin.  Folding the margin into only one of
        # them would compare a ruler position against a page position and report
        # every dated or anchored row as a hack.
        origin_offset_pt = (left_indent + first_line_indent) / 20.0
        size = _first_run_size(paragraph)
        prefix_width = space_units * size

        reasons = []
        if tabs:
            first_stop = min(declared) / 20.0 if declared else None
            if first_stop is None:
                reasons.append("LEADING_TAB_WITHOUT_DECLARED_STOP")
            elif first_stop <= origin_offset_pt + COLUMN_TOLERANCE_PT:
                reasons.append("LEADING_TAB_REPRODUCES_PARAGRAPH_ORIGIN")
        if reasons:
            counters[FIRST_LINE_TAB_HACK_COUNT] += 1
            counters[POSITIONING_TAB_COUNT] += 1

        if space_units >= MIN_HACK_WHITESPACE_UNITS and alignment not in (
            "center",
            "right",
        ):
            frame = frame_width
            text = "".join(node.text or "" for node in paragraph.iter(W + "t"))
            text = text.lstrip(" \u3000\t")
            text_advance = _text_advance(text, size)
            if frame > 0.0 and prefix_width + text_advance <= frame:
                # Where the whitespace actually PUT the text: its own centre and
                # its own right edge, measured from the frame.
                text_center = prefix_width + text_advance / 2.0
                text_right = prefix_width + text_advance
                tolerance = max(ALIGNMENT_EDGE_TOLERANCE_PT, frame * 0.02)
                if abs(frame - text_right) <= tolerance:
                    counters[RIGHT_HACK_COUNT] += 1
                    reasons.append("WHITESPACE_REACHES_FRAME_RIGHT")
                elif abs(text_center - frame / 2.0) <= tolerance:
                    counters[CENTER_HACK_COUNT] += 1
                    reasons.append("WHITESPACE_REACHES_FRAME_CENTRE")
        if reasons:
            records.append(
                {
                    "paragraph_index": index,
                    "reasons": reasons,
                    "leading_tabs": tabs,
                    "leading_space_units": round(space_units, 3),
                    "declared_tab_positions_twips": declared,
                    "alignment": alignment,
                }
            )
    return {
        "counters": counters,
        "records": records,
        "positioning_tab_free": counters[POSITIONING_TAB_COUNT] == 0,
        "alignment_property_owned": (
            counters[CENTER_HACK_COUNT] == 0 and counters[RIGHT_HACK_COUNT] == 0
        ),
    }


def _first_run_size(paragraph) -> float:
    """The run size of the paragraph's first sized run, in points."""

    for node in paragraph.iter(W + "rPr"):
        size = node.find(W + "sz")
        if size is not None and size.get(W + "val"):
            try:
                return float(size.get(W + "val")) / 2.0
            except ValueError:
                continue
    return 10.5


__all__ = [
    "ALIGNMENT_CENTER",
    "ALIGNMENT_CLASSES",
    "ALIGNMENT_DISTRIBUTE",
    "ALIGNMENT_JUSTIFY",
    "ALIGNMENT_LEFT",
    "ALIGNMENT_RIGHT",
    "ALIGNMENT_EDGE_TOLERANCE_PT",
    "CHARACTER_INDENT_TOLERANCE_CHARS",
    "CENTER_HACK_COUNT",
    "COLUMN_TOLERANCE_PT",
    "FIRST_LINE_TAB_HACK_COUNT",
    "INDENT_CLASS_CHARACTERS",
    "INDENT_CLASS_HANGING",
    "INDENT_CLASS_MEASURED",
    "INDENT_CLASS_NONE",
    "LINE_SPACING_AT_LEAST",
    "LINE_SPACING_AUTO_MULTIPLE",
    "LINE_SPACING_DOUBLE",
    "LINE_SPACING_EXACT",
    "LINE_SPACING_KINDS",
    "LINE_SPACING_ONE_POINT_FIVE",
    "LINE_SPACING_SINGLE",
    "MIN_CHARACTER_INDENT",
    "PARAGRAPH_ALIGNED",
    "POSITIONING_TAB_COUNT",
    "RIGHT_HACK_COUNT",
    "SCHEMA",
    "WORD_ALIGNMENT",
    "SourceCharacterIndent",
    "SourceParagraphAlignmentGeometry",
    "SourceParagraphLayoutContract",
    "apply_source_paragraph_layout",
    "audit_docx_paragraph_positioning",
    "classify_line_spacing_semantics",
    "classify_source_character_indent",
    "classify_source_paragraph_alignment_geometry",
    "derive_source_paragraph_layout_contract",
]
