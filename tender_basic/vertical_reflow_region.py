"""PDF-driven region assembly for the ``REFLOW_AWARE_V1`` vertical contract.

This module does the measuring: it reads the source page, the generated page and
the repository's own generation report, and produces one
:class:`~tender_basic.vertical_reflow_qa.VerticalReflowPlan` per logical source
visual row of a region.

Evidence policy
---------------

* **Source side** - row tops, row extents, glyph coverage, rule spans and the
  section's usable width all come from the *source* PDF and the generation
  report's source-side records.  They define what the row must contain and how
  wide its lines may be.
* **Value side** - the advance of a substituted resolved value is measured from
  the rendered glyphs of that value in the generated PDF.  That is the
  repository-native metric for text the source never contained; it is a *width*,
  never a row count.
* **Generated side** - generated row tops are read only *after* the mandatory row
  budget has been derived, and are used only to measure the residual and to
  report unexplained rows.  No required row count is ever read from them.

Nothing in this module classifies semantic fields, owns an execution decision or
influences emission.
"""

from __future__ import annotations

from typing import Any, Sequence

import pymupdf

from tender_basic.vertical_reflow_qa import (
    ATOM_ANCHOR_RULE,
    ATOM_PRESERVED_TEXT,
    ATOM_RESOLVED_VALUE,
    BLANK_ROW_GAP_MULTIPLE,
    CONTRACT_VERSION,
    MEASURE_EPSILON_PT,
    REASON_CONTENT_REFLOW,
    REASON_FITS,
    REASON_STRUCTURAL_ISOLATION,
    TOLERANCE_PT,
    ContentAtom,
    StructuralIsolationEvidence,
    VerticalReflowPlan,
    account_region_rows,
    detect_blank_row_gaps,
    estimated_advance,
    evaluate_isolation,
    group_rows,
    median,
    reflow_axis,
    uniform_pitch,
    wrap_atoms,
)

#: How far outside the extreme rule rows the region's own text rows may sit.
REGION_PAD_PT = 16.0

#: A rule whose visible source glyphs start this close to the span start carries
#: naturally flowing source text and needs no absolute anchor.
NATURAL_FLOW_TOLERANCE_PT = TOLERANCE_PT

#: Glyphs within this distance of a row top belong to that row.
ROW_CELL_TOLERANCE_PT = 4.0

#: Gaps above this are not line-pitch gaps when estimating the pitch.
PITCH_GAP_MIN_PT = 8.0
PITCH_GAP_MAX_PT = 40.0

VALUE_POLICIES = {"PLACEHOLDER_REPLACED_BY_VALUE", "RESOLVED_VALUE_IN_FIXED_SLOT"}
BLANK_POLICIES = {
    "FIXED_EMPTY_SLOT",
    "PRESERVE_SOURCE_PLACEHOLDER",
    "SOURCE_VALUE_UNDERLINE",
}


# --------------------------------------------------------------------------- #
# Page measurement
# --------------------------------------------------------------------------- #


def page_text_lines(page: pymupdf.Page) -> list[dict[str, Any]]:
    """Every non-empty text line of a page, with its own extent."""

    lines: list[dict[str, Any]] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            bbox = line["bbox"]
            text = "".join(span["text"] for span in line["spans"])
            if not text.strip():
                continue
            lines.append(
                {
                    "text": text,
                    "x0": round(float(bbox[0]), 2),
                    "x1": round(float(bbox[2]), 2),
                    "top": round(float(bbox[1]), 2),
                    "bottom": round(float(bbox[3]), 2),
                    "sizes": sorted({round(float(span["size"]), 2) for span in line["spans"]}),
                }
            )
    return lines


def page_char_cells(page: pymupdf.Page) -> list[dict[str, Any]]:
    """Every visible character of a page in reading order, with its own box."""

    cells: list[dict[str, Any]] = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span.get("chars", []):
                    text = char.get("c") or ""
                    if not text.strip():
                        continue
                    bbox = char["bbox"]
                    cells.append(
                        {
                            "text": text,
                            "x0": round(float(bbox[0]), 2),
                            "x1": round(float(bbox[2]), 2),
                            "top": round(float(bbox[1]), 2),
                            "bottom": round(float(bbox[3]), 2),
                        }
                    )
    cells.sort(key=lambda cell: (round(cell["top"], 1), cell["x0"]))
    return cells


def page_drawn_rules(page: pymupdf.Page, minimum_width: float = 2.0) -> list[dict[str, Any]]:
    """Every horizontal drawn rule of a page, sorted by (y, x0)."""

    rules: list[dict[str, Any]] = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.height <= 2.4 and rect.width >= minimum_width:
            rules.append(
                {
                    "x0": round(float(rect.x0), 2),
                    "x1": round(float(rect.x1), 2),
                    "y": round(float((rect.y0 + rect.y1) / 2.0), 2),
                    "width": round(float(rect.width), 2),
                }
            )
    rules.sort(key=lambda rule: (rule["y"], rule["x0"]))
    return rules


def numbered_source_rules(page: pymupdf.Page, page_number: int) -> list[dict[str, Any]]:
    """The page's drawn rules with the registry's own ``P<page>-R<n>`` ids."""

    rules = page_drawn_rules(page, 6.0)
    for index, rule in enumerate(rules, start=1):
        rule["source_rule_id"] = "P%d-R%d" % (page_number, index)
    return rules


def covered_advance(
    cells: Sequence[dict[str, Any]],
    start: float,
    end: float,
    *,
    row_top: float | None = None,
    row_tolerance: float = ROW_CELL_TOLERANCE_PT,
) -> float:
    """The glyph advance actually covered by ``[start, end)``.

    Clipping each glyph box against the window avoids the two errors a naive
    "nearest glyph" rule makes: counting a glyph that only starts after the
    window, and missing the part of a glyph the window cuts off.
    """

    total = 0.0
    for cell in cells:
        if row_top is not None and abs(float(cell["top"]) - row_top) > row_tolerance:
            continue
        low = max(float(cell["x0"]), float(start))
        high = min(float(cell["x1"]), float(end))
        if high > low:
            total += high - low
    return round(total, 2)


def value_advance(cells: Sequence[dict[str, Any]], value: str) -> float | None:
    """The rendered advance of one resolved value, following it across lines.

    A wrapped value is measured segment by segment, so a value that spans two
    generated lines reports the sum of the widths it really occupies rather than
    the distance between its first and last glyph.
    """

    if not value:
        return None
    needle = str(value)
    length = len(needle)
    for start in range(0, len(cells) - length + 1):
        cursor = start
        total = 0.0
        segment_start = None
        segment_top = None
        matched = True
        for offset in range(length):
            index = cursor + offset
            if index >= len(cells) or cells[index]["text"] != needle[offset]:
                matched = False
                break
            cell = cells[index]
            if segment_start is None or abs(float(cell["top"]) - float(segment_top)) > ROW_CELL_TOLERANCE_PT:
                if segment_start is not None:
                    total += segment_end - segment_start
                segment_start = float(cell["x0"])
                segment_top = cell["top"]
            segment_end = float(cell["x1"])
        if not matched:
            continue
        total += segment_end - segment_start
        return round(total, 2)
    return None


# --------------------------------------------------------------------------- #
# Report lookups
# --------------------------------------------------------------------------- #


def registry_for(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        entry["source_rule_id"]: entry
        for entry in report.get("source_rule_registry") or []
        if entry.get("source_rule_id")
    }


def values_by_rule(report: dict[str, Any]) -> dict[str, list[str]]:
    """Resolved values a rule actually emitted, from its own emission record."""

    values: dict[str, list[str]] = {}
    for run in report.get("source_form_line_value_runs") or []:
        rule_id = run.get("source_rule_id")
        if rule_id and run.get("resolved_values"):
            values[rule_id] = [str(item) for item in run["resolved_values"]]
    for application in report.get("source_fill_applications") or []:
        resolved = [str(item) for item in application.get("resolved_values") or ()]
        if not resolved:
            continue
        for rule_id in application.get("source_rule_ids") or ():
            values.setdefault(rule_id, resolved)
    return values


def source_paragraph_baselines(
    report: dict[str, Any], source_page: int
) -> list[tuple[int, list[float]]]:
    """The source page's own logical paragraph structure, as reported."""

    paragraphs = []
    for record in report.get("paragraph_layout_records") or []:
        if record.get("source_page") != source_page:
            continue
        baselines = [
            round(float(value), 2) for value in record.get("source_baselines") or ()
        ]
        if not baselines:
            continue
        paragraphs.append((record.get("paragraph_index"), baselines))
    paragraphs.sort(key=lambda item: item[1][0])
    return paragraphs


def form_line_rule_ids(report: dict[str, Any], source_page: int) -> set[str]:
    """Rules the accepted architecture gives an independent line context."""

    rule_ids: set[str] = set()
    for record in report.get("source_form_line_paragraphs") or []:
        if record.get("source_page") != source_page:
            continue
        rule_ids.update(record.get("source_rule_ids") or ())
    return rule_ids


# --------------------------------------------------------------------------- #
# Atom assembly
# --------------------------------------------------------------------------- #


def _rule_advance(
    rule_id: str,
    span: tuple[float, float],
    values: dict[str, list[str]],
    generated_cells: Sequence[dict[str, Any]],
    font_size: float,
) -> tuple[float, list[str]]:
    """The occupancy of a rule slot: its emitted values when it has them."""

    emitted = values.get(rule_id) or []
    if emitted:
        total = 0.0
        for value in emitted:
            advance = value_advance(generated_cells, value)
            total += advance if advance is not None else estimated_advance(value, font_size)
        return round(total, 2), emitted
    return round(max(0.0, span[1] - span[0]), 2), []


def _natural_flow(rule_cells: Sequence[dict[str, Any]], span: tuple[float, float]) -> bool:
    """True when the slot is painted under source text that starts at its start."""

    inside = [
        cell
        for cell in rule_cells
        if float(cell["x1"]) > span[0] and float(cell["x0"]) < span[1]
    ]
    if not inside:
        return False
    leftmost = min(float(cell["x0"]) for cell in inside)
    return abs(leftmost - span[0]) <= NATURAL_FLOW_TOLERANCE_PT


def build_row_atoms(
    *,
    row: dict[str, Any],
    row_rules: Sequence[dict[str, Any]],
    row_cells: Sequence[dict[str, Any]],
    registry: dict[str, dict[str, Any]],
    values: dict[str, list[str]],
    generated_cells: Sequence[dict[str, Any]],
    font_size: float,
) -> list[ContentAtom]:
    """The ordered participating content of one logical source row.

    The row is cut at every rule span's own endpoints.  What falls inside a span
    belongs to that rule; what falls between spans is the source's preserved
    text.  Values the rule emitted replace its slot; a slot with no value keeps
    its own source span width.
    """

    row_x0 = float(row["x0"])
    row_x1 = float(row["x1"])
    atoms: list[ContentAtom] = []

    spans: list[tuple[float, float, dict[str, Any]]] = []
    for rule in sorted(row_rules, key=lambda item: item["x0"]):
        start = max(row_x0, float(rule["x0"]))
        end = min(row_x1, float(rule["x1"]))
        if end > start:
            spans.append((start, end, rule))

    boundaries = [row_x0]
    for start, end, _ in spans:
        boundaries.extend([start, end])
    boundaries.append(row_x1)
    boundaries = sorted({round(value, 2) for value in boundaries})

    def owner_of(position: float) -> tuple[float, float, dict[str, Any]] | None:
        for span in spans:
            if span[0] - MEASURE_EPSILON_PT <= position <= span[1] + MEASURE_EPSILON_PT:
                return span
        return None

    index = 0
    while index < len(boundaries) - 1:
        start = boundaries[index]
        end = boundaries[index + 1]
        if end <= start:
            index += 1
            continue
        span = owner_of((start + end) / 2.0)
        if span is None:
            advance = covered_advance(row_cells, start, end, row_top=float(row["top"]))
            atoms.append(
                ContentAtom(
                    atom_kind=ATOM_PRESERVED_TEXT,
                    text=_row_text_between(row, row_cells, start, end),
                    source_x0=round(start, 2),
                    source_x1=round(end, 2),
                    advance_pt=advance,
                )
            )
            index += 1
            continue
        span_start, span_end, rule = span
        #: Absorb every consecutive interval that belongs to the same rule span.
        advance_index = index
        while advance_index < len(boundaries) - 1 and owner_of(
            (boundaries[advance_index] + boundaries[advance_index + 1]) / 2.0
        ) is span:
            advance_index += 1
        rule_id = rule["source_rule_id"]
        policy = (registry.get(rule_id) or {}).get("transformation_policy")
        advance, emitted = _rule_advance(
            rule_id, (span_start, span_end), values, generated_cells, font_size
        )
        rule_cells = [
            cell
            for cell in row_cells
            if float(cell["x0"]) >= span_start - MEASURE_EPSILON_PT
            and float(cell["x1"]) <= span_end + MEASURE_EPSILON_PT
        ]
        natural = policy in BLANK_POLICIES and _natural_flow(
            row_cells, (span_start, span_end)
        )
        if natural:
            glyphs = covered_advance(
                row_cells, span_start, span_end, row_top=float(row["top"])
            )
            atoms.append(
                ContentAtom(
                    atom_kind=ATOM_ANCHOR_RULE,
                    text=_row_text_between(row, row_cells, span_start, span_end),
                    source_x0=round(span_start, 2),
                    source_x1=round(span_end, 2),
                    advance_pt=round(glyphs, 2),
                    rule_id=rule_id,
                    anchored=False,
                    geometry_source="SOURCE_NATURAL_FLOW",
                )
            )
        elif emitted and policy in VALUE_POLICIES:
            #: A resolved value substituted for a placeholder flows with the
            #: text it replaces; it does not claim an absolute anchor.
            for value in emitted:
                single = value_advance(generated_cells, value)
                atoms.append(
                    ContentAtom(
                        atom_kind=ATOM_RESOLVED_VALUE,
                        text=value,
                        source_x0=round(span_start, 2),
                        source_x1=round(span_end, 2),
                        advance_pt=(
                            single
                            if single is not None
                            else estimated_advance(value, font_size)
                        ),
                        rule_id=rule_id,
                        anchored=False,
                        geometry_source="SOURCE_RULE_SPAN",
                    )
                )
        else:
            atoms.append(
                ContentAtom(
                    atom_kind=ATOM_ANCHOR_RULE,
                    text="".join(item["text"] for item in rule_cells),
                    source_x0=round(span_start, 2),
                    source_x1=round(span_end, 2),
                    advance_pt=round(advance, 2),
                    rule_id=rule_id,
                    anchored=True,
                    anchor_x=round(span_start, 2),
                    geometry_source="SOURCE_RULE_SPAN",
                )
            )
        index = advance_index
    return atoms


def _row_text_between(
    row: dict[str, Any],
    row_cells: Sequence[dict[str, Any]],
    start: float,
    end: float,
) -> str:
    """The source glyphs of a row that fall inside ``[start, end)``."""

    pieces = []
    for cell in sorted(row_cells, key=lambda item: item["x0"]):
        middle = (float(cell["x0"]) + float(cell["x1"])) / 2.0
        if start - MEASURE_EPSILON_PT <= middle <= end + MEASURE_EPSILON_PT:
            pieces.append(cell["text"])
    return "".join(pieces)


# --------------------------------------------------------------------------- #
# Region assembly
# --------------------------------------------------------------------------- #


def _probe_for_row(
    row: dict[str, Any],
    atoms: Sequence[ContentAtom],
) -> str:
    """A short source-side string that identifies this row's generated content."""

    for atom in atoms:
        if atom.atom_kind == ATOM_PRESERVED_TEXT:
            text = "".join(atom.text.split())
            if len(text) >= 2:
                return text[:10]
    for atom in atoms:
        if atom.atom_kind == ATOM_ANCHOR_RULE:
            text = "".join(atom.text.split())
            if len(text) >= 2:
                return text[:10]
    for atom in atoms:
        if atom.atom_kind == ATOM_RESOLVED_VALUE:
            text = "".join(atom.text.split())
            if text:
                return text[:10]
    return "".join(row["text"].split())[:10]


def _match_generated_row(
    probe: str,
    generated_rows: Sequence[dict[str, Any]],
    start_index: int,
) -> int | None:
    """The first generated row at or after ``start_index`` carrying ``probe``."""

    if not probe:
        return None
    for index in range(start_index, len(generated_rows)):
        haystack = "".join(str(generated_rows[index]["text"]).split())
        if probe in haystack:
            return index
    return None


def build_region_reflow_plan(
    *,
    source_doc: pymupdf.Document,
    generated_doc: pymupdf.Document,
    report: dict[str, Any],
    source_page: int,
    generated_page: int,
    region_rule_ids: Sequence[str],
    body_right_limit: float | None = None,
) -> dict[str, Any]:
    """The complete reflow-aware vertical evidence for one source region."""

    source_page_obj = source_doc[source_page - 1]
    generated_page_obj = generated_doc[generated_page - 1]
    registry = registry_for(report)
    values = values_by_rule(report)

    all_rules = numbered_source_rules(source_page_obj, source_page)
    rules_by_id = {rule["source_rule_id"]: rule for rule in all_rules}
    region_rules = [rules_by_id[rule_id] for rule_id in region_rule_ids if rule_id in rules_by_id]
    region_rule_ys = [rule["y"] for rule in region_rules]

    source_lines = page_text_lines(source_page_obj)
    source_cells = page_char_cells(source_page_obj)

    band = (
        min(region_rule_ys) - REGION_PAD_PT,
        max(region_rule_ys) + REGION_PAD_PT,
    )
    rule_pitch = median(
        [
            round(region_rules[index + 1]["y"] - region_rules[index]["y"], 2)
            for index in range(len(region_rules) - 1)
            if 0 < region_rules[index + 1]["y"] - region_rules[index]["y"] < 60.0
        ]
    ) or 20.0
    candidate_rows = group_rows(
        [
            line
            for line in source_lines
            if band[0] <= line["top"] <= band[1]
        ],
        tolerance=min(6.0, max(2.0, rule_pitch / 2.0)),
    )
    rows_with_rules = [
        index
        for index, row in enumerate(candidate_rows)
        if any(
            float(row["top"]) - 1.0 <= rule["y"] <= float(row["lines"][0]["bottom"]) + 1.0
            for rule in region_rules
        )
    ]
    first_rule_row = rows_with_rules[0]
    last_rule_row = rows_with_rules[-1]
    source_rows = candidate_rows[first_rule_row : last_rule_row + 1]

    rules_on_row: dict[int, list[dict[str, Any]]] = {}
    for index, row in enumerate(source_rows):
        bottom = max(float(line["bottom"]) for line in row["lines"])
        rules_on_row[index] = [
            rule
            for rule in region_rules
            if float(row["top"]) - 1.0 <= rule["y"] <= bottom + 1.0
        ]

    source_pitch = uniform_pitch(source_rows)
    region_left = min(float(row["x0"]) for row in source_rows)

    if body_right_limit is None:
        body_right_limit = _section_right_limit(report, source_page)
    if body_right_limit is None:
        body_right_limit = max(float(row["x1"]) for row in source_rows)

    generated_rows = group_rows(page_text_lines(generated_page_obj))
    generated_pitch = _pitch_from_rows(generated_rows)

    #: Paragraph grouping: the source page's own logical paragraphs, split where
    #: the accepted architecture gives a form-line rule its own line context.
    baseline_map = _baseline_map(report, source_page)
    split_rule_ids = form_line_rule_ids(report, source_page)
    paragraph_of_row: dict[int, int | None] = {}
    for index, row in enumerate(source_rows):
        paragraph_of_row[index] = _paragraph_for_top(baseline_map, float(row["top"]))
    groups: list[list[int]] = []
    current: list[int] = []
    current_paragraph = object()
    for index, row in enumerate(source_rows):
        paragraph = paragraph_of_row[index]
        is_split = any(
            rule["source_rule_id"] in split_rule_ids for rule in rules_on_row[index]
        )
        if paragraph != current_paragraph and current:
            groups.append(current)
            current = []
        if is_split and current:
            groups.append(current)
            current = []
        current.append(index)
        current_paragraph = paragraph
    if current:
        groups.append(current)

    atoms_by_row: dict[int, list[ContentAtom]] = {}
    probe_by_row: dict[int, str] = {}
    line_identity_by_top = _line_identity_map(report, source_page)
    for index, row in enumerate(source_rows):
        row_cells = [
            cell
            for cell in source_cells
            if abs(float(cell["top"]) - float(row["top"])) <= ROW_CELL_TOLERANCE_PT
        ]
        font_size = _row_font_size(row)
        atoms = build_row_atoms(
            row=row,
            row_rules=rules_on_row[index],
            row_cells=row_cells,
            registry=registry,
            values=values,
            generated_cells=page_char_cells(generated_page_obj),
            font_size=font_size,
        )
        atoms_by_row[index] = atoms
        probe_by_row[index] = _probe_for_row(row, atoms)

    generated_cells = page_char_cells(generated_page_obj)

    #: Matching is monotonic: a row's content can never be carried by a generated
    #: row above the one its predecessor used.
    matched_index: dict[int, int | None] = {}
    cursor = 0
    for index, row in enumerate(source_rows):
        found = _match_generated_row(probe_by_row[index], generated_rows, cursor)
        matched_index[index] = found
        if found is not None:
            cursor = found

    group_minimums = []
    forward_reachable = _forward_reachable_rule_ids(report, source_page)
    for group in groups:
        atoms: list[ContentAtom] = []
        row_atom_offsets: list[int] = []
        for offset, row_index in enumerate(group):
            row = source_rows[row_index]
            first_start = float(row["x0"]) if offset == 0 else region_left
            _ = first_start
            row_atom_offsets.append(len(atoms))
            atoms.extend(atoms_by_row[row_index])
        first_start = float(source_rows[group[0]]["x0"])
        layout = wrap_atoms(
            atoms,
            first_line_start=first_start,
            line_start=region_left,
            right_limit=float(body_right_limit),
            forward_reachable_rule_ids=forward_reachable,
        )
        #: The generated line each source row's first atom lands on.  Rows that
        #: share one delivered paragraph share one flow, so this is what says how
        #: far down that flow a row starts - not how many lines the row's own
        #: content would need if it ended the line.
        row_start_lines = [
            (
                int(layout.placements[offset]["line_index"])
                if offset < len(layout.placements)
                else position
            )
            for position, offset in enumerate(row_atom_offsets)
        ]
        prefix_counts = []
        for offset in range(len(group)):
            prefix_atoms: list[ContentAtom] = []
            for inner in range(offset + 1):
                prefix_atoms.extend(atoms_by_row[group[inner]])
            prefix = wrap_atoms(
                prefix_atoms,
                first_line_start=first_start,
                line_start=region_left,
                right_limit=float(body_right_limit),
                forward_reachable_rule_ids=forward_reachable,
            )
            prefix_counts.append(prefix.line_count)
        group_minimums.append(
            {
                "rows": list(group),
                "minimum_lines": layout.line_count,
                "row_start_lines": row_start_lines,
                "prefix_minimum_lines": prefix_counts,
                "forced_new_line_rule_ids": list(layout.forced_new_line_rule_ids),
                "placements": list(layout.placements),
                "line_ends": list(layout.line_ends),
            }
        )

    matched_tops = [
        generated_rows[matched_index[index]]["top"]
        for index in range(len(source_rows))
        if matched_index[index] is not None
    ]
    if matched_tops:
        generated_region_rows = [
            row
            for row in generated_rows
            if min(matched_tops) - 0.5 <= row["top"] <= max(matched_tops) + 0.5
        ]
    else:  # pragma: no cover - defensive
        generated_region_rows = []
    generated_region_pitch = _pitch_from_rows(generated_region_rows) or generated_pitch
    origin_offset = (
        round(float(generated_region_rows[0]["top"]) - float(source_rows[0]["top"]), 2)
        if generated_region_rows
        else 0.0
    )

    extra_before: dict[int, int] = {}
    extra_by_row: dict[int, int] = {}
    group_of_row: dict[int, int] = {}
    rows_in_group: dict[int, int] = {}
    minimum_by_row: dict[int, int] = {}
    prefix_by_row: dict[int, int] = {}
    placements_by_row: dict[int, list[dict[str, Any]]] = {}
    forced_by_row: dict[int, list[str]] = {}
    axis = reflow_axis(
        [record["prefix_minimum_lines"] for record in group_minimums],
        group_row_start_lines=[record["row_start_lines"] for record in group_minimums],
    )
    axis_cursor = 0
    for group_index, record in enumerate(group_minimums):
        group = record["rows"]
        prefix_counts = record["prefix_minimum_lines"]
        for offset, row_index in enumerate(group):
            position = axis_cursor + offset
            group_of_row[row_index] = group_index
            rows_in_group[row_index] = len(group)
            minimum_by_row[row_index] = record["minimum_lines"]
            prefix_by_row[row_index] = prefix_counts[offset]
            extra_before[row_index] = axis["cumulative_extra_lines_before_row"][position]
            extra_by_row[row_index] = axis["extra_lines_attributed_to_row"][position]
            placements_by_row[row_index] = list(record["placements"])
            forced_by_row[row_index] = list(record["forced_new_line_rule_ids"])
        axis_cursor += len(group)

    first_matched = next(
        (matched for matched in matched_index.values() if matched is not None), 0
    )
    pitch_expansion_ratio = max(0.0, generated_region_pitch - source_pitch)

    plans: list[VerticalReflowPlan] = []
    for index, row in enumerate(source_rows):
        row_atoms = atoms_by_row[index]
        minimum_lines = minimum_by_row[index]
        extra_lines = extra_by_row[index]
        extra_height = round(extra_lines * generated_region_pitch, 2)
        cumulative = round(extra_before[index] * generated_region_pitch, 2)
        pitch_expansion = round(index * pitch_expansion_ratio, 2)
        target = round(
            float(row["top"]) + origin_offset + pitch_expansion + cumulative, 2
        )
        matched = matched_index[index]
        actual = round(float(generated_rows[matched]["top"]), 2) if matched is not None else None
        raw_error = round(actual - float(row["top"]), 2) if actual is not None else None
        residual = round(actual - target, 2) if actual is not None else None
        region_index = matched - first_matched if matched is not None else None
        expected_index = index + extra_before[index]
        order_preserved = region_index is not None and region_index == expected_index
        if extra_lines and forced_by_row[index]:
            reason = REASON_STRUCTURAL_ISOLATION
        elif extra_lines:
            reason = REASON_CONTENT_REFLOW
        else:
            reason = REASON_FITS
        plans.append(
            VerticalReflowPlan(
                source_page=source_page,
                source_visual_line_id="RF%d-R%02d" % (source_page, index + 1),
                source_y=round(float(row["top"]), 2),
                available_width=round(float(body_right_limit) - region_left, 2),
                first_line_width=round(float(body_right_limit) - float(row["x0"]), 2),
                participating_content=[
                    {
                        "atom_kind": atom.atom_kind,
                        "text": atom.text,
                        "source_x0": round(atom.source_x0, 2),
                        "source_x1": round(atom.source_x1, 2),
                        "advance_pt": round(atom.advance_pt, 2),
                        "rule_id": atom.rule_id,
                        "anchored": bool(atom.anchored),
                        "anchor_x_pt": (
                            round(float(atom.anchor_x), 2)
                            if atom.anchor_x is not None
                            else None
                        ),
                        "geometry_source": atom.geometry_source,
                    }
                    for atom in row_atoms
                ],
                typography={
                    "font_size_pt": _row_font_size(row),
                    "source_line_pitch_pt": round(source_pitch, 2),
                    "applicable_line_pitch_pt": round(generated_region_pitch, 2),
                    "line_pitch_expansion_pt": round(pitch_expansion_ratio, 3),
                    "right_limit_pt": round(float(body_right_limit), 2),
                    "region_left_pt": round(region_left, 2),
                },
                minimum_required_generated_line_count=minimum_lines,
                mandatory_extra_line_count=extra_lines,
                mandatory_extra_height_pt=extra_height,
                expansion_reason=reason,
                cumulative_mandatory_reflow_before_row_pt=cumulative,
                line_pitch_expansion_before_row_pt=pitch_expansion,
                region_origin_offset_pt=origin_offset,
                reflow_adjusted_target_y=target,
                actual_generated_y=actual,
                raw_y_error=raw_error,
                residual_y_error=residual,
                passes=bool(residual is not None and abs(residual) <= TOLERANCE_PT),
                forced_new_line_rule_ids=forced_by_row[index],
                generated_paragraph_index=group_of_row[index],
                source_rows_in_paragraph=rows_in_group[index],
                row_index=index,
                generated_row_index=matched,
                generated_row_order_preserved=order_preserved,
                repository_line_identity=_line_identity_for_top(
                    line_identity_by_top, float(row["top"])
                ),
                paragraph_prefix_minimum_line_count=prefix_by_row[index],
                atom_placements=placements_by_row[index],
            )
        )

    mandatory_minimum_rows = len(source_rows) + sum(
        max(0, record["minimum_lines"] - len(record["rows"])) for record in group_minimums
    )
    blank_gaps = detect_blank_row_gaps(
        generated_region_rows, generated_region_pitch, BLANK_ROW_GAP_MULTIPLE
    )
    accounting = account_region_rows(
        source_row_count=len(source_rows),
        group_minimum_lines=[record["minimum_lines"] for record in group_minimums],
        group_row_counts=[len(record["rows"]) for record in group_minimums],
        generated_row_count=len(generated_region_rows),
        unexplained_blank_row_count=len(blank_gaps),
    )
    isolations = _isolation_evidence(
        source_rows=source_rows,
        rules_on_row=rules_on_row,
        atoms_by_row=atoms_by_row,
        plans=plans,
        generated_region_pitch=generated_region_pitch,
        generated_rows=generated_rows,
        matched_index=matched_index,
        source_pitch=source_pitch,
        generated_page=generated_page_obj,
    )

    return {
        "schema": "vertical_reflow_region_plan/1",
        "vertical_contract_version": CONTRACT_VERSION,
        "tolerance_pt": TOLERANCE_PT,
        "source_page": source_page,
        "generated_page": generated_page,
        "region_rule_ids": list(region_rule_ids),
        "source_logical_rows": len(source_rows),
        "generated_region_rows": len(generated_region_rows),
        "mandatory_minimum_generated_rows": mandatory_minimum_rows,
        "unexplained_extra_row_count": accounting["unexplained_extra_row_count"],
        "unexplained_blank_row_gaps": blank_gaps,
        "row_accounting": accounting,
        "reflow_axis": axis,
        "source_line_pitch_pt": round(source_pitch, 4),
        "applicable_line_pitch_pt": round(generated_region_pitch, 4),
        "line_pitch_expansion_pt": round(pitch_expansion_ratio, 4),
        "region_origin_offset_pt": origin_offset,
        "right_limit_pt": round(float(body_right_limit), 2),
        "region_left_pt": round(region_left, 2),
        "generated_row_order_preserved": all(
            plan.generated_row_order_preserved for plan in plans
        ),
        "all_rows_matched": all(matched_index[index] is not None for index in range(len(source_rows))),
        "raw_vertical_source_fidelity_difference_present": any(
            plan.raw_y_error is not None and abs(plan.raw_y_error) > TOLERANCE_PT
            for plan in plans
        ),
        "mandatory_reflow_present": any(plan.mandatory_extra_line_count for plan in plans),
        "maximum_raw_y_error_pt": max(
            (abs(plan.raw_y_error) for plan in plans if plan.raw_y_error is not None),
            default=0.0,
        ),
        "maximum_residual_y_error_pt": max(
            (
                abs(plan.residual_y_error)
                for plan in plans
                if plan.residual_y_error is not None
            ),
            default=0.0,
        ),
        "structural_isolations": [record.to_dict() for record in isolations],
        "groups": [
            {
                "rows": [
                    "RF%d-R%02d" % (source_page, index + 1) for index in record["rows"]
                ],
                "minimum_lines": record["minimum_lines"],
                "prefix_minimum_lines": record["prefix_minimum_lines"],
                "forced_new_line_rule_ids": record["forced_new_line_rule_ids"],
            }
            for record in group_minimums
        ],
        "plans": [plan.to_dict() for plan in plans],
        "_plans": plans,
    }


def _isolation_evidence(
    *,
    source_rows: Sequence[dict[str, Any]],
    rules_on_row: dict[int, list[dict[str, Any]]],
    atoms_by_row: dict[int, list[ContentAtom]],
    plans: Sequence[VerticalReflowPlan],
    generated_region_pitch: float,
    generated_rows: Sequence[dict[str, Any]],
    matched_index: dict[int, int | None],
    source_pitch: float,
    generated_page: pymupdf.Page,
) -> list[StructuralIsolationEvidence]:
    """The six-condition proof for every forced new line, measured not assumed."""

    drawn = page_drawn_rules(generated_page, 2.0)
    evidence: list[StructuralIsolationEvidence] = []
    for plan in plans:
        for rule_id in plan.forced_new_line_rule_ids:
            atoms = atoms_by_row[plan.row_index]
            cursor = float(source_rows[plan.row_index]["x0"])
            anchor = None
            preceding = ""
            for atom in atoms:
                if atom.rule_id == rule_id and atom.anchored:
                    anchor = float(
                        atom.anchor_x if atom.anchor_x is not None else atom.source_x0
                    )
                    break
                cursor += max(0.0, float(atom.advance_pt))
                preceding += atom.text
            if anchor is None:  # pragma: no cover - defensive
                continue
            stops = [
                float(rule["x1"])
                for rule in rules_on_row.get(plan.row_index, [])
                if float(rule["x1"]) > anchor + MEASURE_EPSILON_PT
            ]
            stops.extend([float(source_rows[plan.row_index]["x1"])])
            matched = matched_index.get(plan.row_index)
            expected_y = (
                float(generated_rows[matched]["top"]) if matched is not None else None
            )
            anchor_error = _anchor_start_error(drawn, anchor, expected_y)
            present = False
            if matched is not None:
                haystack = "".join(str(generated_rows[matched]["text"]).split())
                probe = "".join(preceding.split())
                present = bool(probe) and probe[:6] in haystack
            evidence.append(
                evaluate_isolation(
                    rule_id=rule_id,
                    source_anchor_x=anchor,
                    cursor_before_pt=round(cursor, 2),
                    anchor_start_preserved=(
                        anchor_error is not None and anchor_error <= TOLERANCE_PT
                    ),
                    preceding_content_present=present,
                    reading_order_is_source_order=True,
                    candidate_stops=stops,
                    expansion_height_pt=round(generated_region_pitch, 2),
                )
            )
    _ = source_pitch
    return evidence


def _anchor_start_error(
    drawn: Sequence[dict[str, Any]], anchor_x: float, expected_y: float | None
) -> float | None:
    """How far the nearest generated drawn rule starts from the source anchor."""

    candidates = [
        rule
        for rule in drawn
        if expected_y is None or abs(float(rule["y"]) - expected_y) <= REGION_PAD_PT
    ]
    if not candidates:
        candidates = list(drawn)
    if not candidates:
        return None
    return round(min(abs(float(rule["x0"]) - anchor_x) for rule in candidates), 2)


def _pitch_from_rows(rows: Sequence[dict[str, Any]]) -> float:
    tops = sorted({round(float(row["top"]), 2) for row in rows})
    gaps = [
        round(tops[index + 1] - tops[index], 2)
        for index in range(len(tops) - 1)
        if PITCH_GAP_MIN_PT <= tops[index + 1] - tops[index] <= PITCH_GAP_MAX_PT
    ]
    if not gaps:
        return uniform_pitch(rows)
    return round(sum(gaps) / len(gaps), 4)


def _row_font_size(row: dict[str, Any]) -> float:
    sizes = [
        size
        for line in row["lines"]
        for size in line.get("sizes") or ()
    ]
    return round(float(median(sizes) or 12.0), 2)


def _section_right_limit(report: dict[str, Any], source_page: int) -> float | None:
    for record in report.get("section_geometry") or []:
        if record.get("page") == source_page and record.get("body_x1") is not None:
            return round(float(record["body_x1"]), 2)
    return None


def _baseline_map(
    report: dict[str, Any], source_page: int
) -> list[tuple[float, int | None]]:
    mapping: list[tuple[float, int | None]] = []
    for paragraph_index, baselines in source_paragraph_baselines(report, source_page):
        for baseline in baselines:
            mapping.append((round(float(baseline), 2), paragraph_index))
    mapping.sort(key=lambda item: item[0])
    return mapping


def _paragraph_for_top(
    mapping: Sequence[tuple[float, int | None]], top: float
) -> int | None:
    if not mapping:
        return None
    baseline, paragraph_index = min(mapping, key=lambda item: abs(item[0] - top))
    if abs(baseline - top) > TOLERANCE_PT:
        return None
    return paragraph_index


def _forward_reachable_rule_ids(
    report: dict[str, Any], source_page: int
) -> set[str]:
    """Rules the emitter measured as reached forward on their own source row.

    The width model in :func:`wrap_atoms` estimates an atom's anchor against the
    cursor; the emitter measured the same anchor against the real font metrics.
    Where the emitter recorded ``FORWARD_REACHABLE_SAME_ROW``, that measurement is
    authoritative and the estimate must not demand a generated line for an atom
    that was in fact reached on the row's own line.

    A rule standing on one of its element's own *wrapped* rows is the same
    measurement: the element is one Word paragraph, the row is placed by Word's
    flow rather than by the emitter's line machinery, and the emitter recorded
    the row - with its rules - in the assembly gaps for exactly that reason.  The
    estimate must not ask for a generated line there either, or the plan would
    claim a row the paragraph cannot have.
    """

    rules: set[str] = set()
    for plan in report.get("forward_reachable_emission_plans") or []:
        if source_page is not None and plan.get("source_page") != source_page:
            continue
        for rule_id in plan.get("source_rule_ids") or ():
            if rule_id:
                rules.add(str(rule_id))
    for gap in report.get("source_visual_line_assembly_gaps") or []:
        if source_page is not None and gap.get("source_page") != source_page:
            continue
        for rule_id in gap.get("source_rule_ids") or ():
            if rule_id:
                rules.add(str(rule_id))
    return rules


def _line_identity_map(
    report: dict[str, Any], source_page: int
) -> list[tuple[float, str]]:
    """The repository's own source visual line identity per source row top."""

    mapping: list[tuple[float, str]] = []
    for plan in report.get("source_visual_line_emission_plans") or []:
        if plan.get("source_page") != source_page:
            continue
        identity = plan.get("source_line_identity")
        top = plan.get("source_y0")
        if identity is None or top is None:
            continue
        mapping.append((round(float(top), 2), str(identity)))
    mapping.sort(key=lambda item: item[0])
    return mapping


def _line_identity_for_top(
    mapping: Sequence[tuple[float, str]], top: float
) -> str | None:
    if not mapping:
        return None
    baseline, identity = min(mapping, key=lambda item: abs(item[0] - top))
    if abs(baseline - top) > TOLERANCE_PT:
        return None
    return identity


__all__ = [
    "build_region_reflow_plan",
    "build_row_atoms",
    "covered_advance",
    "form_line_rule_ids",
    "numbered_source_rules",
    "page_char_cells",
    "page_drawn_rules",
    "page_text_lines",
    "registry_for",
    "source_paragraph_baselines",
    "value_advance",
    "values_by_rule",
]
