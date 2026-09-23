"""Source-backed paragraph alignment, measured from a paragraph's own rows.

A Word paragraph's horizontal alignment is not visible in a PDF as a property:
the source only shows where the glyphs landed.  What distinguishes a justified
paragraph from a left-aligned one is therefore the *spacing between the glyphs*.
A left-aligned line is set at the font's natural advance, so every pair of
adjacent full-width glyphs is one em apart.  A justified line is stretched to
reach the right edge of the measure, so the same glyph pairs are further apart
by exactly the amount the line had to grow.

The measurement is per source visual row and per extracted span: the median
advance of a row's adjacent glyph pairs, divided by the font size the source set
that span in.  Only the rows the source *wrapped* are used, because Word never
stretches a paragraph's final line - a full final line would need no stretch
anyway, and a short one would dilute the evidence.

Nothing here reads a page number, a rule id, a font name or a literal string.
"""

from dataclasses import dataclass
from statistics import median

#: Classification of a paragraph's own source rows.
CLASSIFICATION_JUSTIFIED = "JUSTIFIED_FROM_STRETCHED_WRAPPED_ROWS"
CLASSIFICATION_LEFT = "LEFT_FROM_NATURAL_GLYPH_ADVANCE"
CLASSIFICATION_NO_WRAP_EVIDENCE = "NO_WRAP_EVIDENCE_IN_ONE_SOURCE_ROW"

#: How much a wrapped row's median glyph advance must exceed the font's natural
#: advance before the row counts as stretched.  1.5% of an em is roughly 0.18pt
#: at a 12pt body size - far outside the rounding of extracted glyph boxes and
#: far inside the stretch a justified CJK line actually needs.
GLYPH_ADVANCE_STRETCH_RATIO = 1.015

#: A row needs this many adjacent glyph pairs before its median advance is
#: meaningful.  Short markers, captions and signatures carry no evidence.
MIN_ROW_GLYPH_PAIRS = 6

#: An adjacent pair further apart than this is not a glyph advance at all but a
#: gap the extraction joined (a blank the source drew, a tab-like jump).
MAX_GLYPH_ADVANCE_PT = 40.0


@dataclass(frozen=True)
class SourceParagraphAlignment:
    """What a paragraph's own source rows say about its horizontal alignment."""

    classification: str
    row_count: int
    wrapped_row_count: int
    stretched_row_count: int
    max_glyph_advance_ratio: float | None
    evidence: str

    @property
    def justified(self) -> bool:
        return self.classification == CLASSIFICATION_JUSTIFIED

    @property
    def alignment_hint(self) -> str:
        """The Word alignment this classification asks for."""

        return "justify" if self.justified else "left"


def row_glyph_advance_ratio(row) -> float | None:
    """The largest median glyph-advance ratio any span of this row shows.

    ``None`` when the row carries too few full-width glyph pairs to measure.
    """

    ratios: list[float] = []
    for line in row or ():
        for span in getattr(line, "spans", ()) or ():
            size = float(getattr(span, "font_size", 0.0) or 0.0)
            if size <= 0:
                continue
            characters = list(getattr(span, "characters", ()) or ())
            if len(characters) < MIN_ROW_GLYPH_PAIRS:
                continue
            advances = [
                float(characters[index + 1].bbox[0]) - float(characters[index].bbox[0])
                for index in range(len(characters) - 1)
            ]
            advances = [
                value
                for value in advances
                if 0.0 < value < MAX_GLYPH_ADVANCE_PT
            ]
            if len(advances) < MIN_ROW_GLYPH_PAIRS:
                continue
            ratios.append(median(advances) / size)
    return max(ratios) if ratios else None


def classify_source_paragraph_alignment(rows) -> SourceParagraphAlignment:
    """Classify a paragraph's alignment from its own source visual rows.

    ``rows`` is the paragraph's visual rows in source order - the same rows the
    source's own wrapping produced.  A paragraph that never wrapped carries no
    evidence: one line looks identical left-aligned and justified, so it is
    reported as such rather than guessed at.
    """

    rows = list(rows or ())
    if len(rows) < 2:
        return SourceParagraphAlignment(
            classification=CLASSIFICATION_NO_WRAP_EVIDENCE,
            row_count=len(rows),
            wrapped_row_count=0,
            stretched_row_count=0,
            max_glyph_advance_ratio=None,
            evidence=(
                "the paragraph has no wrapped row, so its source rows carry no "
                "evidence of a stretched line"
            ),
        )
    wrapped_rows = rows[:-1]
    ratios = [
        ratio
        for ratio in (row_glyph_advance_ratio(row) for row in wrapped_rows)
        if ratio is not None
    ]
    if not ratios:
        return SourceParagraphAlignment(
            classification=CLASSIFICATION_NO_WRAP_EVIDENCE,
            row_count=len(rows),
            wrapped_row_count=len(wrapped_rows),
            stretched_row_count=0,
            max_glyph_advance_ratio=None,
            evidence=(
                "no wrapped row carried enough glyph pairs to measure a glyph "
                "advance"
            ),
        )
    stretched = [ratio for ratio in ratios if ratio >= GLYPH_ADVANCE_STRETCH_RATIO]
    if stretched:
        return SourceParagraphAlignment(
            classification=CLASSIFICATION_JUSTIFIED,
            row_count=len(rows),
            wrapped_row_count=len(wrapped_rows),
            stretched_row_count=len(stretched),
            max_glyph_advance_ratio=max(stretched),
            evidence=(
                "the paragraph's wrapped rows advance their glyphs further apart "
                "than the font's natural advance, which is only produced by "
                "stretching the line to the right edge of the measure"
            ),
        )
    return SourceParagraphAlignment(
        classification=CLASSIFICATION_LEFT,
        row_count=len(rows),
        wrapped_row_count=len(wrapped_rows),
        stretched_row_count=0,
        max_glyph_advance_ratio=max(ratios),
        evidence=(
            "every wrapped row advances its glyphs at the font's natural "
            "advance, so the source did not stretch the line"
        ),
    )


__all__ = [
    "CLASSIFICATION_JUSTIFIED",
    "CLASSIFICATION_LEFT",
    "CLASSIFICATION_NO_WRAP_EVIDENCE",
    "GLYPH_ADVANCE_STRETCH_RATIO",
    "MAX_GLYPH_ADVANCE_PT",
    "MIN_ROW_GLYPH_PAIRS",
    "SourceParagraphAlignment",
    "classify_source_paragraph_alignment",
    "row_glyph_advance_ratio",
]
