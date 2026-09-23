"""Shared source vertical rhythm, independent of any DOCX emitter.

The source's vertical structure is a property of the *page*: a body paragraph,
a form block and a heading all advance their text by a line pitch that the
source itself prints, and a block boundary is a larger, single, evidence-backed
gap between two such groups.  Encoding that structure once - instead of deriving
one paragraph's ``w:spacing/@w:before`` from its own absolute y offset - is what
keeps a form's repeated rows on a shared rhythm.

This module owns the model only.  It never classifies a rule, binds a fact or
chooses a Word style; it answers one question: *given the gaps the source's own
rows exhibit, which of them are the same visual rhythm and which are real block
boundaries?*

Two quanta are deliberately kept separate:

``line_pitch``
    How far a line of text advances inside one block.  It is the source's own
    measured row-to-row pitch, so a row's spacing can be expressed in it rather
    than in an arbitrary point value.

``pitch_class``
    A representative spacing shared by every gap in the document that is within
    the sampling tolerance of it.  Two rows whose source gaps differ only by
    extraction noise therefore receive the *same* paragraph spacing, and the
    number of distinct spacing values a delivery carries stays bounded by the
    number of source-evidenced spacing levels instead of by the number of rows.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

SCHEMA = "source_vertical_rhythm/1"

#: Two source gaps this close are the same visual rhythm, not two spacings.
DEFAULT_PITCH_TOLERANCE_PT = 1.0

#: A gap at least this multiple of a block's own line pitch is a block boundary
#: rather than a continuation of the block's row progression.
BLOCK_GAP_PITCH_RATIO = 1.6

#: Spacing classes far smaller than a line pitch are the source's own sub-line
#: adjustments (table/row seam rounding); they are shared for the same reason.
MIN_SHARED_SPACING_PT = 0.0

#: A source gap below this fraction of the document's own dominant line pitch is
#: extraction noise, not a block boundary.  It is collapsed to zero so a
#: sub-line artefact can never become its own paragraph spacing.
SUB_LINE_GAP_PITCH_RATIO = 0.25

#: The renderer's natural single line height for a font, as a ratio of the font
#: size.  ``w:lineRule="auto"`` quotes a fraction of exactly this, so converting
#: a measured source baseline pitch into a Word line spacing needs it, and a
#: *relative* fit (which is what ``infer_semantic_line_spacing`` does) only
#: brackets it.
#:
#: Measured in the delivered render, not assumed.  A delivered table cell set in
#: 仿宋 at an emitted 10.0 pt with ``w:line=399`` (1.6625 lines) advanced its
#: baselines by 23.40 pt and its next lines with ``w:line=331`` (1.3791667 lines)
#: by 19.45 pt, so one line is 23.40 / 1.6625 = 14.075 pt and
#: 19.45 / 1.3791667 = 14.103 pt: 1.4076 em.  The ratio is stated rather than
#: bracketed because a *cell's* rhythm is graded on the absolute pitch it
#: renders: without it a source line set 23.40 pt below the previous one was
#: given 1.5 lines by the relative fit and rendered 21.12 pt, a 2.28 pt error on
#: a 1.0 pt tolerance.
MEASURED_NATURAL_LINE_RATIO = 1.4076

#: ``w:line`` is quoted in 240ths of a line under ``lineRule="auto"``.
LINE_UNITS_PER_LINE = 240.0


def emitted_font_size_pt(font_size_pt):
    """The point size a Word run actually carries for a source size.

    ``w:sz`` is a half-point count and python-docx *truncates* it, so a source
    span set at 10.45 pt is delivered at 10.0 pt - and a line spacing derived
    from the source size would then render its pitch 4.5% wide.  The rendered
    line height follows the delivered size, so the delivered size is what a pitch
    has to be converted with.
    """

    try:
        size = float(font_size_pt or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if size <= 0.0:
        return 0.0
    return math.floor(size * 2.0) / 2.0


def auto_line_multiple_for_pitch(font_size_pt, pitch_pt):
    """The ``w:line``/240 auto multiple that renders ``pitch_pt`` between lines.

    ``None`` when the source states no pitch, and never below one line: a pitch
    narrower than single spacing is not a line rhythm this representation should
    invent a compressed line for.
    """

    try:
        pitch = float(pitch_pt or 0.0)
    except (TypeError, ValueError):
        return None
    if pitch <= 0.0:
        return None
    size = emitted_font_size_pt(font_size_pt) or max(1.0, float(font_size_pt or 10.5))
    single = MEASURED_NATURAL_LINE_RATIO * size
    if single <= 0.0:
        return None
    units = max(
        LINE_UNITS_PER_LINE,
        round(pitch / single * LINE_UNITS_PER_LINE),
    )
    return round(units / LINE_UNITS_PER_LINE, 6)


def dominant_line_pitch(gaps, *, default: float = 0.0) -> float:
    """The pitch the source repeats most often, from its own gap population.

    This is the rhythm the document is actually set in - the mode, not the mean,
    so the many rows sharing one pitch decide it and a handful of large block
    boundaries cannot move it.
    """

    counts: dict[float, int] = {}
    for gap in gaps or ():
        value = round(float(gap), 3)
        if value > 0.0:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return float(default)
    best = max(counts.items(), key=lambda item: (item[1], -item[0]))
    return round(float(best[0]), 3)


def source_line_pitch(top_edges, *, default: float = 0.0) -> float:
    """The source's own row-to-row pitch, from the rows' measured top edges.

    The median of consecutive positive differences is used rather than the mean,
    so one widely separated pair inside the sample cannot move the rhythm of the
    block.  Returns ``default`` when the sample carries no usable pair.
    """

    tops = [float(value) for value in top_edges or () if value is not None]
    diffs = [
        round(later - earlier, 3)
        for earlier, later in zip(tops, tops[1:])
        if later - earlier > 0.05
    ]
    if not diffs:
        return float(default)
    return round(float(statistics.median(diffs)), 3)


@dataclass(frozen=True)
class SourceSpacingClass:
    """One source-evidenced paragraph spacing, shared by every gap it matches.

    ``anchor_pt`` is the gap that *founded* the class and is the only value a
    candidate gap is ever compared against.  ``value_pt`` is the class's largest
    member - the value actually written - so that sharing a spacing never advances
    the page less far than the source did.  Keeping the comparison anchored to a
    fixed value is what stops a chain of near-misses from walking one class across
    the whole gap population.
    """

    value_pt: float
    anchor_pt: float = 0.0
    members: tuple = ()
    source_gaps: tuple = ()

    @property
    def base_pt(self) -> float:
        return round(float(self.anchor_pt or self.value_pt), 3)

    def as_dict(self) -> dict:
        return {
            "value_pt": round(float(self.value_pt), 2),
            "anchor_pt": self.base_pt,
            "member_count": len(self.members),
            "source_gaps": [round(float(gap), 2) for gap in self.source_gaps],
        }


class SourceVerticalRhythm:
    """The document-wide shared spacing classes, built from the source geometry.

    Sampling happens once per build, before any paragraph is emitted, so every
    row of every block is snapped to the same shared value its own source gap
    belongs to.  A caller that has no rhythm (a synthetic fixture with no source
    page, a table cell) gets the identity behaviour: the input is returned.
    """

    def __init__(self, gaps, *, tolerance: float = DEFAULT_PITCH_TOLERANCE_PT,
                 pitch_sample=None):
        self.tolerance = max(0.01, float(tolerance))
        self.source_gaps = sorted({round(float(gap), 3) for gap in gaps or ()})
        # The document's line pitch is measured from *line-like* samples - the
        # source's own row-to-row gaps and paragraph line pitches - never from
        # the element-boundary population.  An element boundary can be far larger
        # or smaller than a line and would pull the pitch off the rhythm the text
        # is actually set in.
        self.pitch_pt = dominant_line_pitch(
            self.source_gaps if pitch_sample is None else pitch_sample
        )
        self.sub_line_max_pt = round(self.pitch_pt * SUB_LINE_GAP_PITCH_RATIO, 3)
        self.classes: list[SourceSpacingClass] = []
        self._assignment: dict[float, float] = {}
        self.collapsed_sub_line_gaps: list[float] = []
        self._build()

    def _build(self) -> None:
        for gap in self.source_gaps:
            if gap < MIN_SHARED_SPACING_PT:
                continue
            if self.sub_line_max_pt > 0.0 and gap <= self.sub_line_max_pt:
                # SUB-LINE ARTEFACT.  The gap is a fraction of one line of text, so
                # the source drew no paragraph boundary here.  It collapses to
                # zero and is recorded, so a rendering artefact can never become a
                # paragraph's own spacing.
                self.collapsed_sub_line_gaps.append(gap)
                self._assignment[gap] = 0.0
                continue
            target = self._nearest_class(gap)
            if target is None:
                self.classes.append(
                    SourceSpacingClass(
                        value_pt=gap,
                        anchor_pt=gap,
                        members=(gap,),
                        source_gaps=(gap,),
                    )
                )
                self._assignment[gap] = gap
                continue
            index = self.classes.index(target)
            # A gap within tolerance of an established class joins it: the class
            # keeps the member count it earned and contributes its own gap to the
            # class's evidence.
            members = tuple(sorted(set(target.members + (gap,))))
            # The class speaks for its *largest* member.  Snapping is sharing, not
            # compression: a gap written as its class's representative must never
            # advance the page less far than the source advanced, or a region
            # tightens until a source row is dropped.  Rounding to the class
            # minimum is exactly the defect that costs the P3 form region a row.
            representative = max(float(target.value_pt), float(gap))
            self.classes[index] = SourceSpacingClass(
                value_pt=representative,
                anchor_pt=target.base_pt,
                members=members,
                source_gaps=members,
            )
            for member in members:
                self._assignment[float(member)] = representative

    def _nearest_class(self, gap: float) -> SourceSpacingClass | None:
        best = None
        best_distance = None
        for candidate in self.classes:
            # Compared against the class's founding anchor, never its moving
            # representative, so adjoining gaps cannot chain into one class.
            distance = abs(float(candidate.base_pt) - float(gap))
            if distance <= self.tolerance and (best_distance is None or distance < best_distance):
                best = candidate
                best_distance = distance
        return best

    def snap(self, gap) -> float:
        """The shared spacing the source's own gap belongs to."""

        if gap is None:
            return 0.0
        value = max(0.0, float(gap))
        key = round(value, 3)
        if key in self._assignment:
            return float(self._assignment[key])
        if self.sub_line_max_pt > 0.0 and value <= self.sub_line_max_pt:
            return 0.0
        nearest = self._nearest_class(key)
        if nearest is not None:
            return float(nearest.value_pt)
        return value

    @property
    def distinct_values(self) -> list:
        return sorted({round(float(item.value_pt), 2) for item in self.classes})

    @property
    def class_count(self) -> int:
        return len(self.classes)

    def as_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "tolerance_pt": round(self.tolerance, 2),
            "dominant_line_pitch_pt": round(float(self.pitch_pt), 2),
            "sub_line_gap_max_pt": round(float(self.sub_line_max_pt), 2),
            "sub_line_gap_pitch_ratio": SUB_LINE_GAP_PITCH_RATIO,
            "source_gap_count": len(self.source_gaps),
            "class_count": self.class_count,
            "distinct_snapped_values": self.distinct_values,
            "collapsed_sub_line_gap_count": len(self.collapsed_sub_line_gaps),
            "collapsed_sub_line_gaps": [
                round(float(gap), 2) for gap in self.collapsed_sub_line_gaps
            ],
            "classes": [item.as_dict() for item in self.classes],
        }


@dataclass
class SourceBlockRhythm:
    """One source text/form block's own vertical rhythm, with its evidence.

    ``line_pitch`` is the block's measured row-to-row pitch; ``gaps`` are the
    measured gaps that follow each row; ``block_gap_indices`` names the gaps
    large enough, against the block's own pitch, to be a real block boundary
    rather than a continuation of the block's row progression.  No semantic fact
    is ever placed in this model.
    """

    source_page: int | None
    block_id: str
    row_count: int = 0
    line_pitch_pt: float = 0.0
    gaps: tuple = ()
    snapped_gaps: tuple = ()
    block_gap_indices: tuple = ()
    line_spacing_rule: str | None = None
    line_spacing_value: float | None = None
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0
    evidence: str = "SOURCE_ROW_TOP_EDGES"
    confidence: float = 0.0

    def as_dict(self) -> dict:
        return {
            "source_page": self.source_page,
            "block_id": self.block_id,
            "row_count": self.row_count,
            "line_pitch_pt": round(float(self.line_pitch_pt), 2),
            "gaps": [round(float(gap), 2) for gap in self.gaps],
            "snapped_gaps": [round(float(gap), 2) for gap in self.snapped_gaps],
            "block_gap_indices": list(self.block_gap_indices),
            "block_gap_count": len(self.block_gap_indices),
            "line_spacing_rule": self.line_spacing_rule,
            "line_spacing_value": self.line_spacing_value,
            "space_before_pt": round(float(self.space_before_pt), 2),
            "space_after_pt": round(float(self.space_after_pt), 2),
            "evidence": self.evidence,
            "confidence": round(float(self.confidence), 3),
        }


def block_rhythm(
    top_edges,
    *,
    source_page=None,
    block_id="",
    rhythm: SourceVerticalRhythm | None = None,
    line_spacing_rule=None,
    line_spacing_value=None,
    space_before_pt=0.0,
    space_after_pt=0.0,
) -> SourceBlockRhythm:
    """The shared vertical rhythm of one source block, with its own evidence."""

    tops = [float(value) for value in top_edges or () if value is not None]
    gaps = tuple(
        round(later - earlier, 3) for earlier, later in zip(tops, tops[1:])
    )
    pitch = source_line_pitch(tops)
    snapped = tuple(
        round(rhythm.snap(gap), 3) if rhythm is not None else round(max(0.0, gap), 3)
        for gap in gaps
    )
    block_gap_indices = tuple(
        index
        for index, gap in enumerate(gaps)
        if pitch > 0.0 and float(gap) >= pitch * BLOCK_GAP_PITCH_RATIO
    )
    # Confidence is the share of the block's gaps that are explained by its own
    # measured pitch, so a block whose rows the source simply spaced evenly is
    # fully explained and a block with unexplained jumps is not.
    if gaps and pitch > 0.0:
        explained = sum(
            1
            for gap in gaps
            if abs(float(gap) - pitch) <= max(pitch, 1.0)
            or float(gap) < pitch * BLOCK_GAP_PITCH_RATIO
        )
        confidence = round(explained / len(gaps), 3)
    else:
        confidence = 0.0
    return SourceBlockRhythm(
        source_page=source_page,
        block_id=str(block_id),
        row_count=len(tops),
        line_pitch_pt=pitch,
        gaps=gaps,
        snapped_gaps=snapped,
        block_gap_indices=block_gap_indices,
        line_spacing_rule=line_spacing_rule,
        line_spacing_value=line_spacing_value,
        space_before_pt=space_before_pt,
        space_after_pt=space_after_pt,
    )


def rhythm_metrics(
    *,
    before_values,
    after_values,
    block_records,
    heading_level_rows=(),
    boundary_values=(),
    spacing_classes=(),
) -> dict:
    """The Stage E acceptance metrics of one delivery's vertical rhythm.

    The two populations are counted separately, because they answer different
    questions and only one of them is the architectural target:

    ``before_values`` / ``after_values``
        The ``space_before`` of *repeated form rows*.  The superseded
        architecture derived each one from that row's own absolute y offset, so
        its distinct-value count equalled its row count.  The shared rhythm model
        assigns each row the source spacing level its own measured gap belongs
        to, so the distinct count collapses to the number of source-evidenced
        levels and repeated rows carry identical values.

    ``boundary_values``
        The ``space_before`` of *real source block boundaries* - a page element
        boundary whose source gap is far larger than a line pitch.  These are
        authorised to keep their own measured gap, so they are reported here
        rather than mixed into the row population.

    ``spacing_classes``
        The rhythm model's own class evidence.  A row's written spacing counts as
        explained when it is a level at least two of the source's own measured
        gaps share - the row belongs to a level the source itself repeats.
    """

    def _values(sequence):
        return [round(float(value), 2) for value in sequence or () if value is not None]

    before = _values(before_values)
    after = _values(after_values)
    boundaries = _values(boundary_values)
    shared_levels = {
        round(float(item.get("value_pt")), 2)
        for item in spacing_classes or ()
        if int(item.get("member_count", 0)) >= 2
    }
    form_pitches = [
        round(float(record.line_pitch_pt), 2)
        for record in block_records or ()
        if record.row_count > 1
    ]
    one_off_after = _singleton_values(after)
    unexplained_after = sorted(
        value for value in one_off_after if value not in shared_levels
    )
    return {
        "schema": SCHEMA,
        "before_population": "PER_ROW_ABSOLUTE_Y_OFFSET",
        "after_population": "SHARED_SOURCE_VERTICAL_RHYTHM",
        "distinct_normal_row_space_before_before": len(set(before)),
        "distinct_normal_row_space_before_after": len(set(after)),
        "distinct_row_spacing_values_before": len(set(before)),
        "distinct_row_spacing_values_after": len(set(after)),
        "distinct_row_spacing_value_reduction": len(set(before)) - len(set(after)),
        "repeated_form_row_count": len(after),
        "repeated_form_row_count_before": len(before),
        "shared_row_spacing_levels_after": sorted(set(after) & shared_levels),
        "shared_row_spacing_level_count_after": len(set(after) & shared_levels),
        "normal_form_row_pitch_variance": _variance(form_pitches),
        "normal_form_row_pitch_variance_pt2": _variance(form_pitches),
        "distinct_form_block_line_pitches": sorted(set(form_pitches)),
        "distinct_form_block_line_pitch_count": len(set(form_pitches)),
        "block_gap_count": sum(
            len(record.block_gap_indices) for record in block_records or ()
        ),
        "source_block_boundary_count": sum(
            len(record.block_gap_indices) for record in block_records or ()
        ),
        "layout_boundary_spacing_count": len(boundaries),
        "distinct_layout_boundary_spacing_values": len(set(boundaries)),
        "layout_boundary_spacings": sorted(set(boundaries)),
        "rows_receiving_unique_one_off_spacing_before": _singletons(before),
        "rows_receiving_unique_one_off_spacing_after": _singletons(after),
        "one_off_row_spacing_count_before": _singletons(before),
        "one_off_row_spacing_count_after": _singletons(after),
        "one_off_row_spacing_values_after": one_off_after,
        "unexplained_custom_row_spacing_count_after": len(unexplained_after),
        "unexplained_custom_row_spacing_values_after": unexplained_after,
        "form_block_count": len(block_records or ()),
        "heading_or_block_boundary_row_count": len(list(heading_level_rows or ())),
    }


def _variance(values) -> float:
    values = [float(value) for value in values or ()]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return round(sum((value - mean) ** 2 for value in values) / len(values), 4)


def _singletons(values) -> int:
    counts: dict[float, int] = {}
    for value in values or ():
        counts[round(float(value), 2)] = counts.get(round(float(value), 2), 0) + 1
    return sum(1 for count in counts.values() if count == 1)


def _singleton_values(values) -> list:
    counts: dict[float, int] = {}
    for value in values or ():
        counts[round(float(value), 2)] = counts.get(round(float(value), 2), 0) + 1
    return sorted(value for value, count in counts.items() if count == 1)
