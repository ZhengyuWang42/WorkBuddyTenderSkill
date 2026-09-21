"""Round 5.4 logical source structure.

PDF page fragments are not Word logical structure.  A PDF visual line is not
automatically a Word paragraph, and a PDF table fragment on one page is not
automatically one logical table.  This module reconstructs *logical* structure
from source evidence so that the Word output owns real paragraphs, rows, cells
and pagination instead of copying PDF page boundaries.

Everything here is generic: no case-specific values, no hard-coded page numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

from .source_format import SourceCell, SourceRow, SourceTable, _characters_from_runs

# Column geometry is compared with a tolerance proportional to the table width.
GRID_TOLERANCE_RATIO = 0.02
MIN_GRID_TOLERANCE_PT = 3.0
# An identity column (序号/建设内容 style) is a narrow key column.  A wide prose
# column that merely happens to hold a short value is not an identity column.
IDENTITY_MAX_WIDTH_RATIO = 0.6


@dataclass
class ContinuationFragment:
    """One PDF table fragment appended to an already-open logical table."""

    source_page: int
    table_index: int
    column_index: int
    raw_text: str
    geometry: tuple[float, float, float, float] | None
    continuation_confidence: float
    continuation_reason: str
    kind: Literal["cell_text", "rows"] = "rows"


@dataclass
class LogicalCell:
    """One logical table cell, possibly assembled from several PDF fragments."""

    column_index: int
    fragments: list[ContinuationFragment] = field(default_factory=list)

    @property
    def fragment_texts(self) -> list[str]:
        return [fragment.raw_text for fragment in self.fragments]


@dataclass
class LogicalRow:
    """One logical table row with its ordered cell fragments."""

    identity: tuple[str, ...]
    cells: list[LogicalCell]
    source_pages: list[int] = field(default_factory=list)
    continuation_of: int | None = None

    @property
    def identity_key(self) -> tuple[str, ...]:
        return self.identity


@dataclass
class LogicalTable:
    """One editable table reconstructed from one or more PDF page fragments."""

    table_id: str
    source_pages: list[int]
    fragments: list[SourceTable]
    rows: list[LogicalRow]
    continuation_evidence: list[ContinuationFragment] = field(default_factory=list)
    columns: int = 0
    #: True when this logical table's rows are already part of another logical
    #: table emitted earlier, so it is reconstruction evidence rather than an
    #: emission of its own.
    subsumed_by_head: bool = False

    @property
    def fragment_count(self) -> int:
        return len(self.fragments)


@dataclass
class TableGroupingReport:
    """Machine-readable account of the reconstruction, used by Round 5.4 QA."""

    pdf_table_fragments: int = 0
    logical_table_count: int = 0
    logical_rows: int = 0
    continuation_fragments_detected: int = 0
    continuation_fragments_merged: int = 0
    orphan_continuation_fragments: int = 0
    false_continuation_merges: int = 0
    cell_text_continuations: int = 0
    decisions: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "pdf_table_fragments": self.pdf_table_fragments,
            "logical_table_count": self.logical_table_count,
            "logical_rows": self.logical_rows,
            "continuation_fragments_detected": self.continuation_fragments_detected,
            "continuation_fragments_merged": self.continuation_fragments_merged,
            "orphan_continuation_fragments": self.orphan_continuation_fragments,
            "false_continuation_merges": self.false_continuation_merges,
            "cell_text_continuations": self.cell_text_continuations,
        }


def _visible(text: str) -> str:
    return "".join(text.split())


def _numeric_column_widths(rows: Sequence[SourceRow]) -> dict[int, float]:
    """Measured width of each column, taken from the source cell boxes."""
    widths: dict[int, float] = {}
    for row in rows:
        for cell in row.cells:
            if cell.bbox is None:
                continue
            width = abs(float(cell.bbox[2]) - float(cell.bbox[0]))
            if width > 0:
                widths.setdefault(cell.column_index, width)
    return widths


def _identity_columns(rows: Sequence[SourceRow]) -> tuple[int, ...]:
    """Columns that identify a new logical row (序号/建设内容 style).

    A column is an identity column when most rows in the fragment carry short
    non-blank values in it.  This is derived from the data, not from a header
    keyword list, so it stays generic across documents.  Value shape alone is
    not sufficient: a wide prose column can hold a short value on a fragment
    that happens to be short (for example a two-row fragment).  A key column is
    also physically narrow, so the measured column width is required as a second
    signal.  When every column has the same width that signal is uninformative
    and the value shape is used on its own.
    """
    if not rows:
        return ()
    column_count = max(
        (cell.column_index for row in rows for cell in row.cells),
        default=-1,
    ) + 1
    candidates: list[int] = []
    for column in range(column_count):
        values = [
            cell.text.strip()
            for row in rows
            for cell in row.cells
            if cell.column_index == column and cell.text.strip()
        ]
        if not values:
            continue
        filled = len(values) / max(1, len(rows))
        short = sum(1 for value in values if len(_visible(value)) <= 12) / len(values)
        if filled >= 0.5 and short >= 0.8:
            candidates.append(column)
    if not candidates:
        return ()
    widths = _numeric_column_widths(rows)
    widest = max(widths.values(), default=0.0)
    if widest <= 0:
        return tuple(candidates)
    narrow = tuple(
        column
        for column in candidates
        if widths.get(column, 0.0) <= widest * IDENTITY_MAX_WIDTH_RATIO
    )
    # A uniform grid carries no width signal, so it must not veto every column.
    return narrow or tuple(candidates)


def _grid_boundaries(table: SourceTable) -> list[float]:
    """Cumulative column boundaries of a table, including both outer edges."""
    if not table.column_widths:
        return []
    boundaries = [float(table.bbox[0])]
    for width in table.column_widths:
        boundaries.append(boundaries[-1] + float(width))
    return boundaries


def _grid_compatible(
    left: SourceTable, right: SourceTable
) -> tuple[bool, float, str]:
    """Are two fragments drawn on the same physical column grid?

    Accepts an exact match, and also the case where one fragment merges some of
    the other's adjacent columns (a PDF may detect the same grid with a different
    column count), by requiring the coarser boundary set to be a subset of the
    finer one.  The outer table extent must always agree.
    """
    left_bounds = _grid_boundaries(left)
    right_bounds = _grid_boundaries(right)
    if not left_bounds or not right_bounds:
        return False, 0.0, "no column geometry"
    tolerance = max(
        MIN_GRID_TOLERANCE_PT,
        max(left.bbox[2] - left.bbox[0], right.bbox[2] - right.bbox[0], 1.0) * GRID_TOLERANCE_RATIO,
    )
    outer = max(
        abs(left_bounds[0] - right_bounds[0]),
        abs(left_bounds[-1] - right_bounds[-1]),
    )
    if outer > tolerance:
        return False, 0.0, (
            f"table extent differs (left {left_bounds[0]:.2f}..{left_bounds[-1]:.2f}, "
            f"right {right_bounds[0]:.2f}..{right_bounds[-1]:.2f})"
        )
    coarse, fine = (
        (left_bounds, right_bounds)
        if len(left_bounds) <= len(right_bounds)
        else (right_bounds, left_bounds)
    )

    def _matched(boundary: float) -> bool:
        return any(abs(boundary - candidate) <= tolerance for candidate in fine)

    unmatched = [b for b in coarse if not _matched(b)]
    if unmatched:
        return False, 0.0, (
            f"column boundaries do not align ({len(unmatched)} unmatched, "
            f"tolerance {tolerance:.2f} pt)"
        )
    if left.columns == right.columns:
        return True, 1.0, f"identical column grid ({left.columns} columns)"
    return True, 0.7, (
        f"equivalent grid ({left.columns} vs {right.columns} columns; "
        "one fragment merges adjacent columns of the other)"
    )


def _band_extents(fragments: Sequence[tuple[int, float, SourceTable]]) -> dict[tuple[float, float], tuple[float, float]]:
    """Observed top/bottom band of each distinct table geometry.

    The band is derived from the fragments themselves rather than from an
    absolute page height, because the normalized source geometry is not always
    the PDF's own page box.  Fragments sharing one outer extent are one physical
    table, so the highest top and lowest bottom across them describe the band
    that table is laid out in.
    """
    bands: dict[tuple[float, float], tuple[float, float]] = {}
    for _page, _height, table in fragments:
        key = (round(float(table.bbox[0]), 1), round(float(table.bbox[2]), 1))
        top = float(table.bbox[1])
        bottom = float(table.bbox[3])
        if key in bands:
            known_top, known_bottom = bands[key]
            bands[key] = (min(known_top, top), max(known_bottom, bottom))
        else:
            bands[key] = (top, bottom)
    return bands


def _band_key(table: SourceTable) -> tuple[float, float]:
    return (round(float(table.bbox[0]), 1), round(float(table.bbox[2]), 1))


def _page_driven_split(
    left: SourceTable,
    right: SourceTable,
    bands: Mapping[tuple[float, float], tuple[float, float]],
) -> tuple[bool, str]:
    """Are these two fragments cut apart by a page boundary?

    The signal is that the earlier fragment runs down to the bottom of the band
    its table occupies, and the later fragment resumes at the top of that same
    band.  Both extents come from the observed fragments, so no page height is
    assumed.  A table that genuinely ends mid-page fails this test.
    """
    band = bands.get(_band_key(left))
    if band is None:
        return False, "no observed band for that table geometry"
    band_top, band_bottom = band
    tolerance = max(6.0, (band_bottom - band_top) * 0.05)
    left_bottom = float(left.bbox[3])
    right_top = float(right.bbox[1])
    closes = left_bottom >= band_bottom - tolerance
    opens = right_top <= band_top + tolerance
    if closes and opens:
        return True, (
            f"page-driven split (earlier fragment reaches the band bottom "
            f"{left_bottom:.2f} of {band_bottom:.2f}; later resumes at the band top "
            f"{right_top:.2f} of {band_top:.2f})"
        )
    return False, (
        f"not a page-driven split (earlier ends at {left_bottom:.2f} of band bottom "
        f"{band_bottom:.2f} within {tolerance:.2f} pt: {closes}; later starts at "
        f"{right_top:.2f} of band top {band_top:.2f}: {opens})"
    )


def _text_continues(left_text: str, right_text: str) -> tuple[bool, str]:
    """Does the next fragment resume the previous fragment's item?

    A long technical cell is often written as numbered sub-items (``1、…``,
    ``2、…``) and can be cut by a page boundary between them.  A numbered
    sub-item therefore continues the cell rather than starting a new one.  Only
    a full stop followed by prose that is *not* a numbered sub-item is treated
    as a completed item.
    """
    left = left_text.rstrip()
    right = right_text.strip()
    if not left or not right:
        return False, "empty fragment"
    tail = left[-1]
    head = right[0]
    if head in "（(【【":
        return False, f"next fragment opens a new bracketed item with {head!r}"
    numbered_subitem = bool(re.match(r"\d+\s*[、.)）]", right))
    if tail in "。！？!?" and not numbered_subitem:
        return False, f"previous fragment ends an item with {tail!r} and the next is not a numbered sub-item"
    if tail.isascii() != head.isascii() and not numbered_subitem:
        # A numbered sub-item legitimately starts with a digit after CJK text.
        return False, f"script change ({tail!r} -> {head!r})"
    if numbered_subitem:
        return True, f"text resumes at a numbered sub-item ({tail!r} -> {head!r})"
    return True, f"text resumes mid-item ({tail!r} -> {head!r})"


#: A pure item index.  A date, a clause number, a decimal quantity, a ratio and
#: a measurement that carries a unit are all excluded, because those do not
#: continue an item sequence.
_ITEM_INDEX_RE = re.compile(r"[0-9]{1,4}")


def _item_index(value: str) -> int | None:
    """The integer item index of an identity cell, when it is exactly one."""
    compact = _visible(value)
    if not compact or _ITEM_INDEX_RE.fullmatch(compact) is None:
        return None
    return int(compact)


def _resumes_item_sequence(previous: SourceTable, following: SourceTable) -> tuple[bool, str]:
    """Does the following fragment's opening row resume the previous index run?

    A price/quotation table cut by a page boundary commonly restarts on the new
    page at the next item index (``… 20`` then ``21 …``) instead of folding a
    half-written row, and each row is a complete item, so no cell text continues
    across the seam.  The index column is the only source evidence that the two
    fragments are one table, so it is read from the data rather than from a
    header keyword: the previous fragment's last row index must be followed by
    the next fragment's first row index, in one column, with nothing but the
    page boundary between them.
    """
    if not previous.rows or not following.rows:
        return False, "empty fragment"
    last_row = previous.rows[-1]
    first_row = following.rows[0]
    for column in range(max(previous.columns, following.columns)):
        earlier = _cell_in(last_row, column)
        later = _cell_in(first_row, column)
        if earlier is None or later is None:
            continue
        earlier_index = _item_index(earlier.text)
        later_index = _item_index(later.text)
        if earlier_index is None or later_index is None:
            continue
        if later_index == earlier_index + 1:
            return True, (
                f"item index continues across the page boundary "
                f"({earlier_index} -> {later_index} in column {column})"
            )
        return False, (
            f"item index does not continue across the page boundary "
            f"({earlier_index} -> {later_index} in column {column})"
        )
    return False, "no comparable item index column"


def _opens_with_header_row(table: SourceTable) -> bool:
    """Is the fragment's opening row a column header rather than an item?

    A continuation page resumes the data; a new table repeats its header.  The
    evidence is the row's own shape: a header row carries no numeric cell at
    all, while a data row of a numeric table always carries at least one number.
    """
    if not table.rows:
        return False
    first = table.rows[0]
    texts = [_visible(cell.text) for cell in first.cells if _visible(cell.text)]
    if not texts:
        return False
    has_number = any(re.search(r"\d", text) for text in texts)
    all_short = all(len(text) <= 12 for text in texts)
    return all_short and not has_number


def _cell_in(row: SourceRow, column: int) -> SourceCell | None:
    return next((cell for cell in row.cells if cell.column_index == column), None)


def _first_content_cell(row: SourceRow, identity: Sequence[int]) -> SourceCell | None:
    for cell in row.cells:
        if cell.column_index in identity:
            continue
        if cell.text.strip():
            return cell
    return None


def _blank_in(row: SourceRow, identity: Sequence[int]) -> bool:
    """Is every identity column of this row blank?

    A blank identity means the row does not open a new logical item, so it can
    be the tail of the row that was open at the page seam.  Cells are matched by
    ``column_index`` because a fragment may not carry every column.
    """
    if not identity:
        return False
    for column in identity:
        cell = _cell_in(row, column)
        if cell is not None and cell.text.strip():
            return False
    return True


def split_fragments(
    fragments: Sequence[tuple[int, float, SourceTable]],
) -> tuple[list[list[tuple[int, float, SourceTable]]], list[dict[str, object]]]:
    """Group consecutive PDF table fragments into logical tables.

    ``fragments`` is an ordered sequence of ``(page_number, page_height, table)``
    for table-bearing pages only.  Grouping requires a page-driven split, a
    compatible grid and syntactic text continuation; a page change alone never
    merges or splits anything.
    """
    groups: list[list[tuple[int, float, SourceTable]]] = []
    decisions: list[dict[str, object]] = []
    bands = _band_extents(fragments)
    for entry in fragments:
        page_number, page_height, table = entry
        if not groups:
            groups.append([entry])
            continue
        previous_page, previous_height, previous_table = groups[-1][-1]
        reasons: list[str] = []
        confidence = 1.0
        adjacent = page_number == previous_page + 1
        if not adjacent:
            reasons.append(f"pages are not adjacent ({previous_page} -> {page_number})")
        geometry_ok = abs(previous_height - page_height) <= 0.5
        if not geometry_ok:
            reasons.append(f"page geometry differs ({previous_height:.2f} vs {page_height:.2f})")
        edge_ok, edge_reason = _page_driven_split(previous_table, table, bands)
        if not edge_ok:
            reasons.append(edge_reason)
        grid_ok, grid_score, grid_reason = _grid_compatible(previous_table, table)
        if not grid_ok:
            reasons.append(grid_reason)
        confidence *= grid_score
        # Column roles are a property of the open logical table, not of the page
        # fragment under test: a continuation page carries no identity values at
        # all, so its own rows cannot describe the identity columns.  The group
        # head always carries the real column roles.
        identity = _identity_columns(groups[-1][0][2].rows)
        if not identity:
            identity = _identity_columns(previous_table.rows)
        first = table.rows[0] if table.rows else None
        edge_identity_blank = bool(first is not None and _blank_in(first, identity))
        text_ok = False
        text_reason = "no first row"
        if first is not None:
            cell = _first_content_cell(first, identity)
            previous_cell = None
            for row in reversed(previous_table.rows):
                if row.cells:
                    candidate = _first_content_cell(row, identity)
                    if candidate is not None:
                        previous_cell = candidate
                        break
            if cell is not None and previous_cell is not None:
                text_ok, text_reason = _text_continues(previous_cell.text, cell.text)
            else:
                text_reason = "no comparable content cell"
        # A table can also be cut between two complete rows rather than inside
        # one.  Two shapes occur in real sources, and each is decided by source
        # evidence rather than by the page change:
        #
        # * *wrapped row* -- the fragment opens with no identity value and the
        #   item text resumes mid-item, so one logical row spans the seam.
        # * *index run* -- every row is a complete item, the item index column
        #   continues across the seam, and the opening row is not a repeated
        #   column header, so one logical table spans the seam.
        index_ok, index_reason = _resumes_item_sequence(previous_table, table)
        header_repeat = _opens_with_header_row(table)
        wrapped_row = edge_identity_blank and text_ok
        indexed_run = index_ok and not header_repeat and not edge_identity_blank
        # Every signal is required.  A page change alone never merges or splits:
        # the fragments must be on adjacent pages, share one physical grid, be
        # cut apart by the page boundary, and then continue as either a wrapped
        # row or a resumed item index.  A fragment that repeats a column header,
        # or whose index does not continue, stays a separate table.
        merge = (
            adjacent
            and geometry_ok
            and edge_ok
            and grid_ok
            and (wrapped_row or indexed_run)
        )
        continuation_mode = (
            "WRAPPED_ROW" if wrapped_row else ("INDEX_RUN" if indexed_run else None)
        )
        decisions.append({
            "previous_page": previous_page,
            "page": page_number,
            "merge": merge,
            "edge_identity_blank": edge_identity_blank,
            "continuation_mode": continuation_mode,
            "opens_with_header_row": header_repeat,
            "confidence": round(confidence, 3),
            "reasons": reasons + [edge_reason, grid_reason, text_reason, index_reason],
        })
        if merge:
            groups[-1].append(entry)
        else:
            groups.append([entry])
    return groups, decisions


def _logical_rows_from_group(
    group: Sequence[tuple[int, float, SourceTable]],
    identity: Sequence[int],
    report: TableGroupingReport,
) -> tuple[list[LogicalRow], list[ContinuationFragment]]:
    """Build the logical rows of one group, folding page seams into one cell."""
    rows: list[LogicalRow] = []
    evidence: list[ContinuationFragment] = []
    for position, (page_number, _height, table) in enumerate(group):
        if position > 0:
            # Every fragment past the group head is a merged continuation
            # fragment, whichever seam shape carried it across the page
            # boundary.  ``cell_text_continuations`` counts the subset that
            # resumed one open cell; a group seam that resumes the item index
            # run instead contributes rows without a cell-text continuation.
            report.continuation_fragments_merged += 1
        for row_index, row in enumerate(table.rows):
            if position > 0 and row_index == 0 and _blank_in(row, identity):
                # The fragment's opening row has no new identity: it is the
                # tail of the logical row that was open at the page seam.
                cell = _first_content_cell(row, identity)
                if cell is not None and rows:
                    target = rows[-1]
                    while len(target.cells) <= cell.column_index:
                        target.cells.append(LogicalCell(column_index=len(target.cells)))
                    logical_cell = target.cells[cell.column_index]
                    logical_cell.fragments.append(ContinuationFragment(
                        source_page=page_number,
                        table_index=table.table_index,
                        column_index=cell.column_index,
                        raw_text=cell.text,
                        geometry=cell.bbox,
                        continuation_confidence=1.0,
                        continuation_reason="fragment row has blank identity cells and resumes the open cell",
                        kind="cell_text",
                    ))
                    target.source_pages.append(page_number)
                    report.cell_text_continuations += 1
                    evidence.append(logical_cell.fragments[-1])
                    # Any remaining content in the same row belongs to the
                    # same logical row as well.
                    for extra in row.cells:
                        if extra.column_index == cell.column_index or not extra.text.strip():
                            continue
                        while len(target.cells) <= extra.column_index:
                            target.cells.append(LogicalCell(column_index=len(target.cells)))
                        target.cells[extra.column_index].fragments.append(ContinuationFragment(
                            source_page=page_number,
                            table_index=table.table_index,
                            column_index=extra.column_index,
                            raw_text=extra.text,
                            geometry=extra.bbox,
                            continuation_confidence=1.0,
                            continuation_reason="same continuation row",
                            kind="cell_text",
                        ))
                    continue
            cells: list[LogicalCell] = []
            for cell in row.cells:
                cells.append(LogicalCell(
                    column_index=cell.column_index,
                    fragments=[ContinuationFragment(
                        source_page=page_number,
                        table_index=table.table_index,
                        column_index=cell.column_index,
                        raw_text=cell.text,
                        geometry=cell.bbox,
                        continuation_confidence=1.0,
                        continuation_reason="primary fragment",
                        kind="rows",
                    )],
                ))
            rows.append(LogicalRow(
                identity=tuple(
                    (cell.text.strip() if (cell := _cell_in(row, column)) is not None else "")
                    for column in identity
                ),
                cells=cells,
                source_pages=[page_number],
            ))
    return rows, evidence


def _best_column(cell: SourceCell, grid: Sequence[float]) -> int:
    """Map one source cell onto the widest-overlapping column of the head grid.

    A later fragment of the same logical table may be detected with fewer
    columns (for example a column that is empty on those pages is dropped and
    its neighbours widen).  The cell's measured x-range, not its positional
    index, decides which head column it belongs to.
    """
    if cell.bbox is None or len(grid) < 2:
        return cell.column_index
    x0, x1 = float(cell.bbox[0]), float(cell.bbox[2])
    best, best_overlap = cell.column_index, -1.0
    for column in range(len(grid) - 1):
        overlap = min(x1, grid[column + 1]) - max(x0, grid[column])
        if overlap > best_overlap:
            best, best_overlap = column, overlap
    return best


def _remap_columns(table: SourceTable, grid: Sequence[float]) -> SourceTable:
    """Re-index one fragment's cells onto the head grid of its logical table."""
    if len(grid) < 2 or table.columns == len(grid) - 1:
        return table
    mapping: dict[int, int] = {}
    for row in table.rows:
        for cell in row.cells:
            mapping.setdefault(cell.column_index, _best_column(cell, grid))
    if all(source == target for source, target in mapping.items()):
        return table
    rows = [
        row.model_copy(update={
            "cells": sorted(
                (cell.model_copy(update={"column_index": mapping[cell.column_index]})
                 for cell in row.cells),
                key=lambda cell: cell.column_index,
            ),
        })
        for row in table.rows
    ]
    return table.model_copy(update={
        "rows": rows,
        "columns": len(grid) - 1,
        "column_widths": list(_grid_widths(grid)),
        "merged_cells": [
            (r0, r1, mapping.get(c0, c0), mapping.get(c1, c1))
            for r0, r1, c0, c1 in table.merged_cells
        ],
    })


def _grid_widths(grid: Sequence[float]) -> list[float]:
    return [float(grid[index + 1]) - float(grid[index]) for index in range(len(grid) - 1)]


def _join_cells(earlier: SourceCell, later: SourceCell) -> SourceCell:
    """Concatenate the two halves of one logical cell, keeping every run."""
    runs = list(earlier.runs) + list(later.runs)
    return earlier.model_copy(update={
        "text": earlier.text + later.text,
        "runs": runs,
        "characters": _characters_from_runs(runs),
        "raised_glyphs": list(earlier.raised_glyphs) + list(later.raised_glyphs),
    })


def _merge_group_source(
    group: Sequence[tuple[int, float, SourceTable]],
    identity: Sequence[int],
    head: SourceTable,
) -> SourceTable:
    """Assemble the editable source table for one logical table.

    Rows are concatenated in source order; the opening row of a continuation
    fragment is folded into the logical row that was open at the page seam,
    exactly as the logical model records it.  No source character is dropped and
    no new row is invented, so the Word table is the logical table rather than a
    copy of each PDF page fragment.
    """
    if len(group) == 1:
        return head
    # Rows are accumulated as column-indexed buckets rather than mutated in
    # place: the source fragment that opens with no new identity is folded into
    # the logical row that was open at the page seam, and every source cell is
    # either carried over or concatenated, never re-matched by value.
    buckets: list[dict[int, SourceCell]] = []
    heights: list[float] = []
    row_map: dict[tuple[int, int, int], int] = {}
    last_bottom = float(head.bbox[3])
    for position, (page_number, _height, table) in enumerate(group):
        last_bottom = max(last_bottom, float(table.bbox[3]))
        for row_index, row in enumerate(table.rows):
            folded = position > 0 and row_index == 0 and _blank_in(row, identity) and buckets
            if folded:
                bucket = buckets[-1]
                row_map[(page_number, table.table_index, row_index)] = len(buckets) - 1
                heights[-1] = max(heights[-1], row.height)
            else:
                bucket = {}
                buckets.append(bucket)
                heights.append(row.height)
                row_map[(page_number, table.table_index, row_index)] = len(buckets) - 1
            for cell in row.cells:
                prior = bucket.get(cell.column_index)
                if prior is None:
                    bucket[cell.column_index] = cell
                elif cell.text.strip() or not prior.text.strip():
                    bucket[cell.column_index] = _join_cells(prior, cell)
    rows = [
        SourceRow(
            row_index=index,
            cells=[bucket[column].model_copy(update={"row_index": index})
                   for column in sorted(bucket)],
            height=heights[index],
        )
        for index, bucket in enumerate(buckets)
    ]
    merged_cells: list[tuple[int, int, int, int]] = []
    for page_number, _height, table in group:
        for r0, r1, c0, c1 in table.merged_cells:
            mapped = [
                row_map.get((page_number, table.table_index, index))
                for index in range(r0, r1 + 1)
            ]
            if any(value is None for value in mapped):
                continue
            if mapped[-1] - mapped[0] != r1 - r0:
                # The region spans rows that the seam collapsed, so the source
                # rectangle no longer describes an editable region.
                continue
            merged_cells.append((mapped[0], mapped[-1], c0, c1))
    return head.model_copy(update={
        "rows": rows,
        "row_heights": [],
        "merged_cells": merged_cells,
        "bbox": (head.bbox[0], head.bbox[1], head.bbox[2], last_bottom),
    })


@dataclass
class LogicalTablePlan:
    """Production plan: which Word table to emit and which fragments it owns."""

    logical_tables: list[LogicalTable]
    source_tables: list[SourceTable]
    head_keys: list[tuple[int, int]]
    continuation_map: dict[tuple[int, int], tuple[int, int]]
    report: TableGroupingReport

    def table_for(self, page: int, table_index: int) -> SourceTable | None:
        """The table to emit for a fragment, or ``None`` for a continuation."""
        key = (page, table_index)
        if key in self.continuation_map:
            return None
        index = next((i for i, head in enumerate(self.head_keys) if head == key), None)
        return None if index is None else self.source_tables[index]

    def head_page_for(self, page: int, table_index: int) -> int | None:
        """The source page whose section geometry this fragment's rows render in.

        A continuation fragment's rows were folded into the head table, and that
        table is laid out in the head fragment's section, so the continuation's
        own page never owns an emitted section of its own.  ``None`` means this
        exact fragment is not a continuation.
        """

        key = self.continuation_map.get((page, table_index))
        return None if key is None else key[0]

    def folded_page_tables(self, page: int) -> list[int]:
        """Table indexes on ``page`` whose rows were folded into another page."""

        return sorted(
            index
            for (candidate_page, index) in self.continuation_map
            if candidate_page == page
        )


def build_logical_tables(
    fragments: Sequence[tuple[int, float, SourceTable]],
    *,
    table_id_prefix: str = "logical",
) -> tuple[list[LogicalTable], TableGroupingReport]:
    """Reconstruct logical tables and their rows from PDF fragments."""
    plan = build_logical_source_tables(fragments, table_id_prefix=table_id_prefix)
    return plan.logical_tables, plan.report


def build_logical_source_tables(
    fragments: Sequence[tuple[int, float, SourceTable]],
    *,
    table_id_prefix: str = "logical",
) -> LogicalTablePlan:
    """Reconstruct logical tables and their editable Word tables.

    This is the production entry point: the emitter writes one Word table per
    logical table, not one per PDF page fragment.
    """
    groups, decisions = split_fragments(fragments)
    report = TableGroupingReport(
        pdf_table_fragments=len(fragments),
        logical_table_count=len(groups),
        decisions=decisions,
    )
    logical_tables: list[LogicalTable] = []
    source_tables: list[SourceTable] = []
    head_keys: list[tuple[int, int]] = []
    continuation_map: dict[tuple[int, int], tuple[int, int]] = {}
    for group_index, group in enumerate(groups):
        head_table = group[0][2]
        grid = _grid_boundaries(head_table)
        remapped = [
            (page, height, _remap_columns(table, grid)) for page, height, table in group
        ]
        identity = _identity_columns(head_table.rows)
        if not identity:
            identity = _identity_columns(remapped[-1][2].rows)
        rows, evidence = _logical_rows_from_group(remapped, identity, report)
        head_key = (head_table.page, head_table.table_index)
        logical_tables.append(LogicalTable(
            table_id=f"{table_id_prefix}_{group_index}",
            source_pages=[page for page, _height, _table in group],
            fragments=[table for _page, _height, table in group],
            rows=rows,
            continuation_evidence=evidence,
            columns=head_table.columns,
            # A group with more than one fragment is exactly a head fragment plus
            # the continuation fragments folded into it.
            subsumed_by_head=len(group) > 1,
        ))
        merged = _merge_group_source(remapped, identity, head_table)
        source_tables.append(merged)
        head_keys.append(head_key)
        for page_number, _height, table in group[1:]:
            continuation_map[(page_number, table.table_index)] = head_key
        report.logical_rows += len(rows)
    report.continuation_fragments_detected = report.continuation_fragments_merged
    # Every fragment past the first is a continuation candidate; any candidate
    # that was not merged is an orphan.
    report.orphan_continuation_fragments = max(
        0, report.pdf_table_fragments - report.logical_table_count - report.continuation_fragments_merged
    )
    return LogicalTablePlan(
        logical_tables=logical_tables,
        source_tables=source_tables,
        head_keys=head_keys,
        continuation_map=continuation_map,
        report=report,
    )
