"""Source paragraph indent semantics, independent of any DOCX emitter.

A source paragraph's left edge is not one number.  A paragraph the source set
with a *first-line indent* begins its first visual row to the right of the body
boundary and returns every wrapped row to that boundary; a paragraph set with a
*hanging indent* begins its first row at the marker column and aligns every
wrapped row to the text column; an ordinary paragraph begins every row at the
same place.  Writing the first row's own x as the paragraph's whole left indent
reproduces the source only while nothing wraps - and a source placeholder that a
resolved value replaces is exactly the thing that starts wrapping.

This module owns the model only.  It never classifies a rule, binds a fact or
chooses a Word style; it answers one question: *given the origins of a
paragraph's own source visual rows, is its first row indented, hanging, or
aligned with its wrapped rows, and against which body boundary?*

Two quantities are deliberately kept separate:

``body_left_x``
    The column the source returns this paragraph's *wrapped* rows to.  When the
    paragraph itself wraps, its own later rows measure it.  A paragraph that
    never wraps has no continuation row of its own, so its geometry alone cannot
    tell a first-line indent from a whole-paragraph indent; there the body
    boundary is the *measured* boundary of the container the paragraph lives in,
    and when even that has not been measured nothing is claimed.

``first_line_indent`` / ``hanging_indent``
    The signed distance from that boundary to the first row, split into the two
    Word-native properties rather than carried as one signed number, so a
    hanging indent can never be delivered as a whole-paragraph left indent.
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA = "source_paragraph_indent/1"

#: The paragraph's first visual row starts right of the body boundary and its
#: wrapped rows return to the body boundary.
CLASSIFICATION_FIRST_LINE = "FIRST_LINE_INDENT"

#: The paragraph's first visual row starts left of its wrapped rows: the marker
#: column, with the body column carrying every continuation.
CLASSIFICATION_HANGING = "HANGING_INDENT"

#: Every visual row of the paragraph starts in the same column.
CLASSIFICATION_NONE = "NO_SPECIAL_FIRST_LINE_INDENT"

#: Two source row origins closer than this share one column; the difference is
#: extraction noise, not an indent.
COLUMN_TOLERANCE_PT = 2.0


@dataclass(frozen=True)
class SourceParagraphIndent:
    """How one source paragraph's first visual row relates to its body column."""

    classification: str
    body_left_x: float
    first_line_x: float
    continuation_x: float | None
    first_line_indent_pt: float
    hanging_indent_pt: float
    row_count: int
    measured_continuation: bool
    evidence: str

    @property
    def word_first_line_indent_pt(self) -> float:
        """Word's ``w:ind/@w:firstLine``: positive first line, negative hanging.

        Word carries both indents in one signed attribute, so the model keeps
        them apart and converts exactly once, here, at the boundary.
        """

        return round(self.first_line_indent_pt - self.hanging_indent_pt, 4)

    def as_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "classification": self.classification,
            "body_left_x": round(float(self.body_left_x), 2),
            "first_line_x": round(float(self.first_line_x), 2),
            "continuation_x": (
                None if self.continuation_x is None else round(float(self.continuation_x), 2)
            ),
            "first_line_indent_pt": round(float(self.first_line_indent_pt), 2),
            "hanging_indent_pt": round(float(self.hanging_indent_pt), 2),
            "word_first_line_indent_pt": round(self.word_first_line_indent_pt, 2),
            "row_count": int(self.row_count),
            "measured_continuation": bool(self.measured_continuation),
            "evidence": self.evidence,
        }


def classify_source_paragraph_indent(
    row_xs,
    *,
    body_left_x=None,
    tolerance: float = COLUMN_TOLERANCE_PT,
) -> SourceParagraphIndent:
    """Classify one paragraph from the origins of its own source visual rows.

    ``row_xs`` are the visible left edges of the paragraph's source visual rows
    in reading order - same-baseline PDF fragments already grouped into one row,
    because a row the extraction split into three text objects is still one row.
    ``body_left_x`` is an externally *measured* body boundary for the paragraph's
    container, consulted only when the paragraph's own rows cannot show one: a
    paragraph that never wraps has no continuation row, and its own geometry
    then cannot distinguish a first-line indent from a whole-paragraph indent.
    Passing no boundary is the honest answer when none was measured, and the
    accepted whole-paragraph geometry is kept.
    """

    rows = [float(x) for x in row_xs if x is not None]
    if not rows:
        raise ValueError("a source paragraph indent needs at least one source row origin")
    first = rows[0]
    tail = rows[1:]
    continuation = min(tail) if tail else None

    if continuation is not None and continuation < first - tolerance:
        # The wrapped rows expose a column left of the first row: the first row
        # is indented and continuation lines return to the body boundary.
        return SourceParagraphIndent(
            classification=CLASSIFICATION_FIRST_LINE,
            body_left_x=continuation,
            first_line_x=first,
            continuation_x=continuation,
            first_line_indent_pt=first - continuation,
            hanging_indent_pt=0.0,
            row_count=len(rows),
            measured_continuation=True,
            evidence=(
                "this paragraph's own wrapped rows start at the body boundary "
                "and its first row starts right of them"
            ),
        )

    if continuation is not None and continuation > first + tolerance:
        # Markers hang in the left column; the body column carries the wrapped
        # rows.  Word centres the body column and pulls the first row left.
        return SourceParagraphIndent(
            classification=CLASSIFICATION_HANGING,
            body_left_x=continuation,
            first_line_x=first,
            continuation_x=continuation,
            first_line_indent_pt=0.0,
            hanging_indent_pt=continuation - first,
            row_count=len(rows),
            measured_continuation=True,
            evidence=(
                "this paragraph's own wrapped rows start right of its first row, "
                "so the first row is a hanging marker column"
            ),
        )

    if continuation is not None:
        # Every row shares one column.
        return SourceParagraphIndent(
            classification=CLASSIFICATION_NONE,
            body_left_x=min(rows),
            first_line_x=first,
            continuation_x=continuation,
            first_line_indent_pt=0.0,
            hanging_indent_pt=0.0,
            row_count=len(rows),
            measured_continuation=True,
            evidence="every source visual row of this paragraph starts in one column",
        )

    # A single source row: its own geometry cannot separate a first-line indent
    # from a whole-paragraph indent, so only a boundary measured elsewhere in
    # the same container is evidence enough to claim an indent.
    boundary = None if body_left_x is None else float(body_left_x)
    if boundary is not None and boundary < first - tolerance:
        return SourceParagraphIndent(
            classification=CLASSIFICATION_FIRST_LINE,
            body_left_x=boundary,
            first_line_x=first,
            continuation_x=None,
            first_line_indent_pt=first - boundary,
            hanging_indent_pt=0.0,
            row_count=1,
            measured_continuation=False,
            evidence=(
                "this paragraph has one source row, and a paragraph that wraps "
                "in the same container returns to this measured body boundary"
            ),
        )
    return SourceParagraphIndent(
        classification=CLASSIFICATION_NONE,
        body_left_x=first,
        first_line_x=first,
        continuation_x=None,
        first_line_indent_pt=0.0,
        hanging_indent_pt=0.0,
        row_count=1,
        measured_continuation=False,
        evidence=(
            "this paragraph has one source row and no wrapped row in its "
            "container was measured, so it is delivered as a single column"
        ),
    )


def measured_container_body_left(
    paragraphs,
    container_x0,
    *,
    tolerance: float = COLUMN_TOLERANCE_PT,
):
    """The body boundary of one container, measured from paragraphs that wrap.

    A container's body boundary is measurable only from a paragraph that
    *actually wrapped inside it*: the wrapped rows expose the column the source
    returns its continuations to.  The boundary is confirmed only when a
    paragraph's wrapped rows start at the container's own left edge, so a
    container whose paragraphs all wrap in some inner column claims nothing and
    keeps the accepted whole-paragraph geometry.

    ``paragraphs`` are the source paragraphs of one page.  Returns the measured
    boundary x, or ``None`` when nothing in the container measured one.
    """

    target = float(container_x0)
    for paragraph in paragraphs or ():
        container = getattr(paragraph, "container", None)
        if container is None:
            continue
        if abs(float(container.container_x0) - target) > tolerance:
            continue
        origins = source_row_origins(getattr(paragraph, "source_lines", ()) or ())
        for origin, _y in origins[1:]:
            if abs(origin - target) <= tolerance:
                return target
    return None


def source_row_origins(source_lines, *, tolerance: float = 2.5):
    """Visible left edge and top edge of each source visual row, in reading order.

    Same-baseline fragments are grouped into one row first: the extraction
    routinely splits a single physical row into several text objects, and those
    objects share the row's column by construction.
    """

    from .page_layout import source_visual_rows, visible_box

    origins = []
    for row in source_visual_rows(source_lines, tolerance=tolerance):
        boxes = [visible_box(line) for line in row]
        origins.append(
            (
                min(box[0] for box in boxes),
                min(box[1] for box in boxes),
            )
        )
    return origins


#: Alignment hints under which a paragraph has no body boundary to relate its
#: first row to: a centred line is positioned from the container's centre, so
#: reading its left edge as an indent would be reading the text's own width.
CENTRED_ALIGNMENTS = frozenset({"center"})


def classify_paragraph_source_indent(
    paragraph,
    *,
    container_paragraphs=None,
    tolerance: float = COLUMN_TOLERANCE_PT,
) -> SourceParagraphIndent:
    """Classify one source paragraph, consulting its container only when it can.

    The single entry point for the model, so the emitter, the QA artifact and
    the tests cannot each derive a different indent from the same paragraph.  A
    centred line has no body boundary - its left edge is a function of its own
    text width - so it is reported as carrying no first-line indent rather than
    being measured against the container's left edge.
    """

    origins = source_row_origins(getattr(paragraph, "source_lines", ()) or ())
    row_xs = [origin for origin, _y in origins]
    alignment = str(getattr(paragraph, "alignment_hint", "") or "").lower()
    container = getattr(paragraph, "container", None)
    boundary = None
    if alignment not in CENTRED_ALIGNMENTS and container is not None and container_paragraphs:
        boundary = measured_container_body_left(
            container_paragraphs, container.container_x0, tolerance=tolerance
        )
    indent = classify_source_paragraph_indent(
        row_xs,
        body_left_x=boundary,
        tolerance=tolerance,
    )
    if alignment in CENTRED_ALIGNMENTS and row_xs:
        indent = SourceParagraphIndent(
            classification=CLASSIFICATION_NONE,
            body_left_x=row_xs[0],
            first_line_x=row_xs[0],
            continuation_x=indent.continuation_x,
            first_line_indent_pt=0.0,
            hanging_indent_pt=0.0,
            row_count=indent.row_count,
            measured_continuation=indent.measured_continuation,
            evidence="a centred line is positioned from the container centre, not from a body boundary",
        )
    return indent
