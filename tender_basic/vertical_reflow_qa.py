"""Reflow-aware vertical layout contract (``REFLOW_AWARE_V1``).

Why this exists
---------------

The frozen Phase-2/Phase-3 P3 contract asks two different questions and the
original vertical gate answered only the first one:

1. *Does the generated form region reproduce the source region's vertical
   geometry?*  The original gate compared every frozen rule's generated y with
   its source y and required the difference to be within 2.0pt.
2. *Is any difference that remains explained by reflow the source's own content
   forces on the generated page?*  The original gate had no model for this, so a
   build whose resolved values genuinely need more generated lines than the
   template has could never satisfy (1), however correctly it was laid out.

This module supplies the missing model.  It is **QA/layout evidence only**: it
never classifies semantic fields, never owns an execution decision and never
influences emission.  Nothing here is ``ProjectFacts`` authority.

The contract
------------

For every logical source visual row of a region the plan records

``minimum_required_generated_line_count``
    The fewest generated lines that can hold the row's *actual participating
    content* - the source's own visible glyph groups plus the resolved values
    that replace its placeholders - wrapped into the *source's own* usable line
    widths at the row's declared typography.

``mandatory_extra_line_count`` / ``mandatory_extra_height_pt``
    The lines above one that the content itself forces, and their height at the
    applicable line pitch.

``cumulative_mandatory_reflow_before_row_pt``
    The mandatory expansion height contributed by the rows above.

``reflow_adjusted_target_y``
    ``source_y`` advanced by every independently justified mandatory expansion
    before the row.

``raw_y_error`` / ``residual_y_error``
    The undisguised source-fidelity difference and the difference that remains
    once mandatory expansion is accounted for.  Both are always reported; the
    raw difference is never hidden.

Non-circularity
---------------

The forbidden argument is *"the generated output uses N rows, therefore N rows
are required"*.  Nothing here reads a generated row count to decide a required
row count.  The required count is produced by wrapping measured content widths
into measured source widths; the generated row count is compared against that
result afterwards, and any mismatch is reported as an *unexplained* row rather
than being absorbed.

Mandatory expansion has three independent, separately reported components:

``region_origin_offset_pt``
    The region's page-level vertical origin, measured from the region's first
    logical row (which by construction has no mandatory expansion before it).
    This is the same normalisation the frozen gate already performed through
    ``source_row_origin_offset_pt``.

``line_pitch_expansion_before_row_pt``
    ``rows_crossed * (applicable_line_pitch - source_line_pitch)``.  The source
    specifies a *line-spacing multiple*, not an absolute pitch; the applicable
    pitch is what the declared typography actually produces in the target
    renderer, measured from rendered lines.  Every source row is emitted as at
    least one generated line, so the difference is mandatory for every row
    crossed.

``cumulative_mandatory_reflow_before_row_pt``
    Rows the participating content itself forces.

Tolerance stays 2.0pt and is never relaxed or scaled.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

#: Contract identity, recorded in every report this module feeds.
CONTRACT_VERSION = "REFLOW_AWARE_V1"

#: The one accepted residual tolerance in points.  Never relaxed, never scaled.
TOLERANCE_PT = 2.0

#: Measurement slack for glyph-boundary comparisons (half a PDF point).
MEASURE_EPSILON_PT = 0.05

#: A generated row gap above this multiple of the line pitch means at least one
#: row was skipped, so an unaccounted blank row is present.
BLANK_ROW_GAP_MULTIPLE = 1.6

#: Fallback advance for a full-width CJK glyph is the font size itself; the
#: fallback for ASCII text is half of it.
FALLBACK_CJK_ADVANCE_RATIO = 1.0
FALLBACK_ASCII_ADVANCE_RATIO = 0.5

#: Fallback pitch when no rendered line evidence exists (a full-width CJK glyph).
FALLBACK_LINE_PITCH_PT = 12.0

#: Tolerance used when grouping extraction fragments into one physical row.
ROW_GROUP_TOLERANCE_PT = 6.0

ATOM_PRESERVED_TEXT = "PRESERVED_TEXT"
ATOM_RESOLVED_VALUE = "RESOLVED_VALUE"
ATOM_ANCHOR_RULE = "ANCHOR_RULE"

PLACEMENT_FLOW = "FLOW"
PLACEMENT_FORWARD_TAB = "FORWARD_TAB"
PLACEMENT_NEW_LINE = "NEW_LINE"

REASON_FITS = "FITS_ONE_GENERATED_LINE"
REASON_CONTENT_REFLOW = "MANDATORY_CONTENT_REFLOW"
REASON_STRUCTURAL_ISOLATION = "MANDATORY_STRUCTURAL_ISOLATION"


# --------------------------------------------------------------------------- #
# Content atoms and line wrapping
# --------------------------------------------------------------------------- #


@dataclass
class ContentAtom:
    """One indivisible piece of a logical source row's participating content.

    ``advance_pt`` is the atom's own measured advance width.  ``anchor_x`` is
    the absolute source x the atom must start at when it is anchored to a source
    rule span; it is ``None`` for freely flowing content and for rules that are
    painted under naturally flowing source text.
    """

    atom_kind: str
    text: str
    source_x0: float
    source_x1: float
    advance_pt: float
    rule_id: str | None = None
    anchored: bool = False
    anchor_x: float | None = None
    geometry_source: str = "SOURCE_ROW_ORIGIN"


@dataclass
class LineLayout:
    """The result of wrapping one logical row's atoms into its own line widths."""

    line_count: int
    line_ends: list[float] = field(default_factory=list)
    placements: list[dict[str, Any]] = field(default_factory=list)
    forced_new_line_rule_ids: list[str] = field(default_factory=list)


def wrap_atoms(
    atoms: Sequence[ContentAtom],
    *,
    first_line_start: float,
    line_start: float,
    right_limit: float,
    forward_reachable_rule_ids: Sequence[str] = (),
) -> LineLayout:
    """Greedily lay one logical row's atoms into the fewest generated lines.

    The model is the one Word itself implements:

    * free content flows and wraps at ``right_limit``;
    * an *anchored* atom whose anchor lies ahead of the cursor is reached with a
      forward tab, so it stays on the current line;
    * an *anchored* atom whose anchor is at or behind the cursor cannot be
      reached on the current line, because a Word tab only ever moves forward.
      The atom therefore begins a new line - exactly the structural isolation
      expansion the contract has to justify.

    Nothing here reads generated output: only the atoms' own measured widths and
    the row's own source-derived line widths.

    ``forward_reachable_rule_ids`` is the escape hatch for the one case this
    width model cannot settle on its own.  An atom's advance is a *measurement*,
    and the emitter measures it against the real font metrics; when the emitter
    recorded that the atom was in fact reached forward from its row origin, that
    measurement outranks this estimate.  Without it the estimate's rounding error
    at the anchor - a cursor a fraction of a point past the anchor the emitter
    tabbed to successfully - would demand a generated line the emission proves is
    unnecessary, and the plan would claim one more row than the page can hold.
    """

    forward = {str(rule_id) for rule_id in forward_reachable_rule_ids or ()}

    cursor = float(first_line_start)
    line_index = 0
    line_ends: list[float] = []
    placements: list[dict[str, Any]] = []
    forced: list[str] = []

    def close_line() -> None:
        line_ends.append(round(cursor, 2))

    def break_line() -> None:
        nonlocal cursor, line_index
        close_line()
        line_index += 1
        cursor = float(line_start)

    for atom in atoms:
        if atom.anchored:
            anchor = float(atom.anchor_x if atom.anchor_x is not None else atom.source_x0)
            if cursor >= anchor - MEASURE_EPSILON_PT and atom.rule_id not in forward:
                break_line()
                cursor = anchor
                if atom.rule_id:
                    forced.append(atom.rule_id)
                placements.append(
                    {
                        "atom_kind": atom.atom_kind,
                        "rule_id": atom.rule_id,
                        "placement": PLACEMENT_NEW_LINE,
                        "starts_at_pt": round(anchor, 2),
                        "line_index": line_index,
                        "reason": "backward_anchor_cannot_be_tabbed_to",
                    }
                )
            else:
                # Never move the cursor backwards: a reached-forward atom the
                # estimate had already passed keeps the further-right position.
                cursor = max(cursor, anchor)
                placements.append(
                    {
                        "atom_kind": atom.atom_kind,
                        "rule_id": atom.rule_id,
                        "placement": PLACEMENT_FORWARD_TAB,
                        "starts_at_pt": round(anchor, 2),
                        "line_index": line_index,
                        "reason": (
                            "anchor_ahead_of_cursor"
                            if atom.rule_id not in forward
                            else "emission_recorded_forward_reachable"
                        ),
                    }
                )
            cursor += max(0.0, float(atom.advance_pt))
            continue

        remaining = max(0.0, float(atom.advance_pt))
        chunk_start = cursor
        while remaining > MEASURE_EPSILON_PT:
            room = right_limit - cursor
            if room <= MEASURE_EPSILON_PT:
                break_line()
                chunk_start = cursor
                continue
            take = min(room, remaining)
            cursor += take
            remaining -= take
            if remaining > MEASURE_EPSILON_PT:
                break_line()
                chunk_start = cursor
        placements.append(
            {
                "atom_kind": atom.atom_kind,
                "rule_id": atom.rule_id,
                "placement": PLACEMENT_FLOW,
                "starts_at_pt": round(chunk_start, 2),
                "ends_at_pt": round(cursor, 2),
                "line_index": line_index,
                "reason": "free_flow",
            }
        )

    close_line()
    return LineLayout(
        line_count=len(line_ends),
        line_ends=line_ends,
        placements=placements,
        forced_new_line_rule_ids=forced,
    )


def mandatory_extra_lines(minimum_lines: int, source_rows_in_paragraph: int) -> int:
    """Extra generated lines a group forces, clamped at zero."""

    return max(0, int(minimum_lines) - int(source_rows_in_paragraph))


def line_pitch_expansion(
    rows_crossed: int, generated_pitch: float, source_pitch: float
) -> float:
    """Mandatory pitch expansion accumulated over ``rows_crossed`` source rows."""

    return round(
        max(0, int(rows_crossed)) * max(0.0, generated_pitch - source_pitch), 4
    )


def next_forward_tab_stop(
    cursor: float, stops: Iterable[float], default_advance: float
) -> float:
    """The stop a forward Word tab would actually land on.

    A tab moves to the next stop strictly greater than the cursor; when no
    declared stop is ahead of it the default tab interval applies.  The result is
    what a same-line representation would be forced to use, so it is the evidence
    that a backward anchor has no same-line solution.
    """

    ahead = sorted(stop for stop in stops if stop > cursor + MEASURE_EPSILON_PT)
    if ahead:
        return round(ahead[0], 2)
    return round(cursor + default_advance, 2)


def reflow_axis(
    group_prefix_minimum_lines: Sequence[Sequence[int]],
    group_row_start_lines: Sequence[Sequence[int]] | None = None,
) -> dict[str, Any]:
    """Where mandatory extra lines land along one region's row axis.

    ``group_prefix_minimum_lines[g][k]`` is the fewest generated lines that hold
    the content of group ``g`` up to and including its ``k``-th source row.

    A group's extra lines are attributed to the row whose own content first
    needed them, and they move the axis for every row *after* that point only.
    Rows above are untouched, which is what makes the expansion propagate
    strictly downstream.

    ``group_row_start_lines[g][k]`` is the generated line the group's ``k``-th
    row itself starts on, read from the group layout's own placements.  Rows that
    share one delivered paragraph share one flow, so how far down the axis a row
    sits is that line - not the sum of the lines each earlier row's content would
    need if it ended the line, which only holds when every row is its own
    paragraph.  Without it the two figures agree on single-row groups, which is
    what the caller passes when it has no layout to read.

    ``extra_lines_attributed_to_row`` is the row's own forcing and is never
    negative: a later row that happens to fit inside an extra line an earlier row
    already paid for simply forces nothing itself.  ``extra_lines_after_region``
    is the group's *net* growth, which is what moves the rows below it; the two
    figures agree whenever no row absorbs another's extra line.
    """

    extra_self: list[int] = []
    cumulative_before: list[int] = []
    axis = 0
    for group_index, prefixes in enumerate(group_prefix_minimum_lines):
        starts = None
        if group_row_start_lines is not None and group_index < len(
            group_row_start_lines
        ):
            starts = group_row_start_lines[group_index]
        previous = 0
        for offset, prefix in enumerate(prefixes):
            self_extra = max(0, int(prefix) - (offset + 1))
            if starts is not None and offset < len(starts):
                within_group = max(0, int(starts[offset]) - offset)
            else:
                within_group = previous
            cumulative_before.append(axis + within_group)
            extra_self.append(max(0, self_extra - previous))
            previous = self_extra
        axis += max(0, int(prefixes[-1]) - len(prefixes))
    return {
        "extra_lines_attributed_to_row": extra_self,
        "cumulative_extra_lines_before_row": cumulative_before,
        "extra_lines_after_region": axis,
    }


def account_region_rows(
    *,
    source_row_count: int,
    group_minimum_lines: Sequence[int],
    group_row_counts: Sequence[int],
    generated_row_count: int,
    unexplained_blank_row_count: int = 0,
) -> dict[str, Any]:
    """Account every generated row of a region against the mandatory minimum.

    A generated row is explained when the independent minimum-row computation
    asked for it.  A row nobody asked for is *unexplained*, and so is a row that
    only a blank paragraph explains: an accidental blank never earns reflow
    budget, because it carries no participating content.
    """

    extra = sum(
        max(0, int(minimum) - int(count))
        for minimum, count in zip(group_minimum_lines, group_row_counts)
    )
    mandatory = int(source_row_count) + extra
    unexplained_rows = max(0, int(generated_row_count) - mandatory)
    return {
        "source_row_count": int(source_row_count),
        "mandatory_extra_row_count": extra,
        "mandatory_minimum_row_count": mandatory,
        "generated_row_count": int(generated_row_count),
        "unexplained_extra_row_count": unexplained_rows,
        "unexplained_blank_row_count": int(unexplained_blank_row_count),
        "rows_accounted": unexplained_rows == 0
        and int(unexplained_blank_row_count) == 0
        and int(generated_row_count) == mandatory,
    }


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #


@dataclass
class VerticalReflowPlan:
    """One logical source visual row's complete reflow-aware vertical evidence."""

    source_page: int
    source_visual_line_id: str
    source_y: float
    available_width: float
    first_line_width: float
    participating_content: list[dict[str, Any]]
    typography: dict[str, Any]
    minimum_required_generated_line_count: int
    mandatory_extra_line_count: int
    mandatory_extra_height_pt: float
    expansion_reason: str
    cumulative_mandatory_reflow_before_row_pt: float
    line_pitch_expansion_before_row_pt: float
    region_origin_offset_pt: float
    reflow_adjusted_target_y: float
    actual_generated_y: float | None
    raw_y_error: float | None
    residual_y_error: float | None
    passes: bool
    forced_new_line_rule_ids: list[str] = field(default_factory=list)
    generated_paragraph_index: int | None = None
    source_rows_in_paragraph: int = 1
    row_index: int = 0
    generated_row_index: int | None = None
    generated_row_order_preserved: bool = True
    repository_line_identity: str | None = None
    paragraph_prefix_minimum_line_count: int = 1
    atom_placements: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def rounded(value: float | None) -> float | None:
            return None if value is None else round(value, 2)

        return {
            "source_page": self.source_page,
            "source_visual_line_id": self.source_visual_line_id,
            "repository_line_identity": self.repository_line_identity,
            "source_y": round(self.source_y, 2),
            "available_width_pt": round(self.available_width, 2),
            "first_line_width_pt": round(self.first_line_width, 2),
            "participating_content": self.participating_content,
            "typography": self.typography,
            "minimum_required_generated_line_count": self.minimum_required_generated_line_count,
            "paragraph_prefix_minimum_line_count": self.paragraph_prefix_minimum_line_count,
            "mandatory_extra_line_count": self.mandatory_extra_line_count,
            "mandatory_extra_height_pt": self.mandatory_extra_height_pt,
            "expansion_reason": self.expansion_reason,
            "cumulative_mandatory_reflow_before_row_pt": self.cumulative_mandatory_reflow_before_row_pt,
            "line_pitch_expansion_before_row_pt": self.line_pitch_expansion_before_row_pt,
            "region_origin_offset_pt": self.region_origin_offset_pt,
            "reflow_adjusted_target_y": rounded(self.reflow_adjusted_target_y),
            "actual_generated_y": rounded(self.actual_generated_y),
            "raw_y_error": rounded(self.raw_y_error),
            "residual_y_error": rounded(self.residual_y_error),
            "pass": bool(self.passes),
            "forced_new_line_rule_ids": list(self.forced_new_line_rule_ids),
            "generated_paragraph_index": self.generated_paragraph_index,
            "source_rows_in_paragraph": self.source_rows_in_paragraph,
            "row_index": self.row_index,
            "generated_row_index": self.generated_row_index,
            "generated_row_order_preserved": bool(self.generated_row_order_preserved),
            "atom_placements": self.atom_placements,
        }


@dataclass
class StructuralIsolationEvidence:
    """The six independently measured conditions for one isolation expansion."""

    rule_id: str
    source_anchor_x: float
    cursor_before_pt: float
    conditions: dict[str, bool]
    next_forward_tab_stop_pt: float
    same_line_error_pt: float
    proven: bool
    expansion_height_pt: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_rule_id": self.rule_id,
            "source_anchor_x_pt": round(self.source_anchor_x, 2),
            "cursor_before_rule_pt": round(self.cursor_before_pt, 2),
            "conditions": dict(self.conditions),
            "next_forward_tab_stop_pt": round(self.next_forward_tab_stop_pt, 2),
            "same_line_error_pt": round(self.same_line_error_pt, 2),
            "structural_isolation_proven": bool(self.proven),
            "isolation_expansion_height_pt": round(self.expansion_height_pt, 2),
        }


def evaluate_isolation(
    *,
    rule_id: str,
    source_anchor_x: float,
    cursor_before_pt: float,
    anchor_start_preserved: bool,
    preceding_content_present: bool,
    reading_order_is_source_order: bool,
    candidate_stops: Sequence[float],
    tolerance_pt: float = TOLERANCE_PT,
    default_tab_advance_pt: float = FALLBACK_LINE_PITCH_PT,
    expansion_height_pt: float = 0.0,
) -> StructuralIsolationEvidence:
    """Prove or refute one structural isolation expansion.

    All six conditions must hold.  The last two are measured, not asserted: the
    cursor the preceding source-compatible content reaches, and the error a
    forward tab would leave on the same line.
    """

    reaches_or_passes = cursor_before_pt >= source_anchor_x - MEASURE_EPSILON_PT
    stop = next_forward_tab_stop(
        cursor_before_pt, candidate_stops, default_tab_advance_pt
    )
    same_line_error = abs(stop - source_anchor_x)
    conditions = {
        "rule_representation_begins_at_source_anchor": bool(anchor_start_preserved),
        "preceding_source_content_present": bool(preceding_content_present),
        "preceding_content_reaches_or_passes_anchor": bool(reaches_or_passes),
        "reordering_would_break_source_reading_order": bool(
            reading_order_is_source_order
        ),
        #: A Word tab never moves the insertion point backwards - a property of
        #: the renderer, not of this build.
        "word_tab_cannot_move_backward": True,
        "no_same_line_representation_preserves_horizontal_contract": bool(
            same_line_error > tolerance_pt
        ),
    }
    proven = all(conditions.values())
    return StructuralIsolationEvidence(
        rule_id=rule_id,
        source_anchor_x=source_anchor_x,
        cursor_before_pt=cursor_before_pt,
        conditions=conditions,
        next_forward_tab_stop_pt=stop,
        same_line_error_pt=same_line_error,
        proven=proven,
        expansion_height_pt=expansion_height_pt if proven else 0.0,
    )


# --------------------------------------------------------------------------- #
# Pure grid helpers
# --------------------------------------------------------------------------- #


def group_rows(
    lines: Sequence[dict[str, Any]], tolerance: float = ROW_GROUP_TOLERANCE_PT
) -> list[dict[str, Any]]:
    """Group extraction lines into physical rows by agreeing tops."""

    ordered = sorted(lines, key=lambda item: (item["top"], item["x0"]))
    rows: list[dict[str, Any]] = []
    for line in ordered:
        if rows and abs(line["top"] - rows[-1]["top"]) <= tolerance:
            rows[-1]["lines"].append(line)
            rows[-1]["x0"] = min(rows[-1]["x0"], line["x0"])
            rows[-1]["x1"] = max(rows[-1]["x1"], line["x1"])
            continue
        rows.append(
            {
                "top": round(float(line["top"]), 2),
                "x0": float(line["x0"]),
                "x1": float(line["x1"]),
                "lines": [line],
            }
        )
    for row in rows:
        row["text"] = "".join(line["text"] for line in row["lines"])
        row["x0"] = round(row["x0"], 2)
        row["x1"] = round(row["x1"], 2)
    return rows


def uniform_pitch(rows: Sequence[dict[str, Any]]) -> float:
    """The row pitch a region actually uses, averaged over its own row grid.

    Averaging (rather than differencing one pair) keeps the value stable against
    extraction rounding of individual row tops.
    """

    tops = sorted({float(row["top"]) for row in rows})
    if len(tops) < 2:
        return FALLBACK_LINE_PITCH_PT
    return (tops[-1] - tops[0]) / float(len(tops) - 1)


def detect_blank_row_gaps(
    rows: Sequence[dict[str, Any]],
    pitch: float,
    multiple: float = BLANK_ROW_GAP_MULTIPLE,
) -> list[dict[str, Any]]:
    """Gaps in a row grid that only an unaccounted blank row can explain."""

    tops = sorted({float(row["top"]) for row in rows})
    gaps = []
    for index in range(len(tops) - 1):
        delta = tops[index + 1] - tops[index]
        if delta > pitch * multiple:
            gaps.append(
                {
                    "after_y": round(tops[index], 2),
                    "before_y": round(tops[index + 1], 2),
                    "gap_pt": round(delta, 2),
                    "pitch_multiple": round(delta / pitch, 2) if pitch else None,
                }
            )
    return gaps


def median(values: Sequence[float]) -> float | None:
    ordered = sorted(value for value in values if value is not None)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def is_full_width(character: str) -> bool:
    """A CJK / full-width glyph advances a full em; ASCII advances roughly half."""

    code = ord(character)
    return (
        0x1100 <= code <= 0x115F
        or 0x2E80 <= code <= 0xA4CF
        or 0xAC00 <= code <= 0xD7A3
        or 0xF900 <= code <= 0xFAFF
        or 0xFE30 <= code <= 0xFE6F
        or 0xFF00 <= code <= 0xFF60
        or 0xFFE0 <= code <= 0xFFE6
    )


def estimated_advance(text: str, font_size_pt: float) -> float:
    """A conservative advance estimate when no rendered glyph evidence exists."""

    total = 0.0
    for character in text:
        total += font_size_pt * (
            FALLBACK_CJK_ADVANCE_RATIO
            if is_full_width(character)
            else FALLBACK_ASCII_ADVANCE_RATIO
        )
    return round(total, 2)


__all__ = [
    "ATOM_ANCHOR_RULE",
    "ATOM_PRESERVED_TEXT",
    "ATOM_RESOLVED_VALUE",
    "BLANK_ROW_GAP_MULTIPLE",
    "CONTRACT_VERSION",
    "ContentAtom",
    "LineLayout",
    "MEASURE_EPSILON_PT",
    "PLACEMENT_FLOW",
    "PLACEMENT_FORWARD_TAB",
    "PLACEMENT_NEW_LINE",
    "REASON_CONTENT_REFLOW",
    "REASON_FITS",
    "REASON_STRUCTURAL_ISOLATION",
    "ROW_GROUP_TOLERANCE_PT",
    "StructuralIsolationEvidence",
    "TOLERANCE_PT",
    "VerticalReflowPlan",
    "account_region_rows",
    "detect_blank_row_gaps",
    "estimated_advance",
    "evaluate_isolation",
    "group_rows",
    "is_full_width",
    "line_pitch_expansion",
    "mandatory_extra_lines",
    "median",
    "next_forward_tab_stop",
    "reflow_axis",
    "uniform_pitch",
    "wrap_atoms",
]
