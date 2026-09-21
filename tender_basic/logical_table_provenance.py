"""Per-logical-table provenance and cell accounting.

One source logical table is emitted as exactly one native Word table.  This
module proves that pairing from the artifacts themselves rather than from the
builder's intent:

* the generated Word tables are enumerated by **document order** from the
  ``w:body`` child sequence, so the index it reports is the index Word itself
  uses;
* each source logical table is paired with the Word table its own logical row
  texts were emitted into;
* every generated cell is classified as exact, aggregated (it carries whole
  source cells, which is what a source-format template cell does when it writes
  a label and a value into one cell) or invented, and every source cell is either
  accounted for or reported lost.

Nothing here is keyed to a case, a filename, a page number or a known literal:
the pairing is cell-content evidence and the report is a general contract.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping, Sequence

#: Cell text is compared after collapsing source whitespace, because the source
#: stores a wrapped cell as several fragments whose concatenation is the value.
_WHITESPACE = re.compile(r"\s+")

#: A source cell must be at least this long before its occurrence *inside* a
#: longer generated cell counts as evidence: a one- or two-character marker such
#: as ``1`` occurs inside unrelated text by coincidence, so only an exact
#: generated cell can account for it.
_MIN_SUBSTRING_EVIDENCE = 3


def normalize_cell_text(value: object) -> str:
    """Comparable form of one cell's text."""

    return _WHITESPACE.sub("", str(value or ""))


def logical_table_source_records(generation_report: dict) -> list[dict]:
    """Source-side provenance for every reconstructed logical table."""

    records = []
    for entry in generation_report.get("logical_tables") or ():
        records.append(
            {
                "table_id": entry.get("table_id"),
                "head_page": entry.get("head_page"),
                "head_table_index": entry.get("head_table_index"),
                "source_pages": list(entry.get("source_pages") or ()),
                "source_fragment_count": int(entry.get("fragment_count") or 0),
                "source_row_count": int(entry.get("row_count") or 0),
                "source_column_count": int(entry.get("column_count") or 0),
                "continuation_fragments": int(entry.get("fragment_count") or 0) - 1,
            }
        )
    return records


def iter_body_tables(document):
    """Every Word table in the document, in ``w:body`` document order.

    Yields ``(word_table_index, table_element)``.  The index counts only real
    ``w:tbl`` children of the body, in the order Word reads them.
    """

    body = document.element.body
    word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    index = 0
    for child in body:
        if child.tag == word_ns + "tbl":
            yield index, child
            index += 1


def _element_cell_texts(table_element) -> list[list[str]]:
    word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    rows = []
    for row in table_element.findall(word_ns + "tr"):
        cells = []
        for cell in row.findall(word_ns + "tc"):
            text = "".join(
                node.text or ""
                for node in cell.iter(word_ns + "t")
            )
            cells.append(normalize_cell_text(text))
        rows.append(cells)
    return rows


def _generated_cell_texts(document) -> dict[int, list[list[str]]]:
    return {index: _element_cell_texts(element) for index, element in iter_body_tables(document)}


def _source_row_texts(rows: Sequence[Sequence[object]]) -> list[list[list[str]]]:
    """Source rows with each cell's page fragments still separate.

    A cell value is the concatenation of its fragments; keeping them separate
    here lets ``_cell_accounting`` decide how to compare, rather than fixing the
    comparison to one representation.
    """

    return [
        [
            cell if isinstance(cell, (list, tuple)) else [cell]
            for cell in row
        ]
        for row in rows
    ]


def _match_table(
    source_rows: Sequence[Sequence[str]],
    candidates: Iterable[tuple[int, list[list[str]]]],
) -> tuple[int | None, float]:
    """The Word table that carries a logical table's own rows.

    The match is decided by how much of the source's own non-empty cell text the
    candidate contains, so a continuation table that merely looks alike cannot
    win over the table that actually holds the content.
    """

    source_tokens = [
        normalize_cell_text("".join(cell) if isinstance(cell, (list, tuple)) else cell)
        for row in source_rows
        for cell in row
    ]
    source_tokens = [token for token in source_tokens if token]
    if not source_tokens:
        return None, 0.0
    best_index = None
    best_score = 0.0
    for index, cells in candidates:
        generated = "".join(text for row in cells for text in row)
        covered = sum(1 for token in source_tokens if token in generated)
        score = covered / len(source_tokens)
        if score > best_score:
            best_index, best_score = index, score
    return best_index, round(best_score, 4)


def recorded_fill_values(generation_report: dict) -> dict[str, list[str]]:
    """Resolved values this build recorded as written into the document.

    Read from the builder's own ``SourceFillApplication`` records: each entry is
    a write event for one resolved fact, so the value's presence in a generated
    cell is source-evidenced content rather than an invention.  Nothing here is
    keyed to a case, a page or a field name.
    """

    mapping: dict[str, list[str]] = {}
    for application in generation_report.get("source_fill_applications") or ():
        fields = [
            str(getattr(field, "value", field))
            for field in (application.get("fact_fields") or ())
        ]
        values = [str(value) for value in (application.get("resolved_values") or ())]
        for field in fields or ["<unattributed>"]:
            slot = mapping.setdefault(field, [])
            for value in values:
                if value and value not in slot:
                    slot.append(value)
    return mapping


def _cell_accounting(
    source_rows: Sequence[Sequence[object]],
    generated_rows: Sequence[Sequence[str]],
    *,
    recorded_fill_values: Mapping[str, Sequence[str]] | None = None,
) -> dict:
    """Lost, duplicated, aggregated and invented cell values for one table.

    A source logical cell may be assembled from several page fragments and a
    generated cell may span more than one source cell, so the comparison is made
    on whole cell values with all layout whitespace removed and it classifies
    every generated cell explicitly:

    * **exact** - the generated cell's value is one source cell's value;
    * **aggregated** - the generated cell's value *contains* one or more whole
      source cell values.  This is the source-format template case, where a form
      cell is written as ``label`` + ``value`` and the source stores the label
      and the value as separate cells, and it is recorded with the source cells
      it aggregates rather than being reported as an invention;
    * **filled from a recorded resolved fact** - the generated cell's value is
      the resolved value of a fact this build recorded as written into the
      document.  It is deliberate source-format semantics, not an invention;
    * **invented** - the generated cell's value is accounted for by neither, so
      it is not traceable to this table's source content or to a recorded fact
      write.

    A source cell is **lost** when its value occurs in no generated cell, unless
    its value is a short identifier-like fragment that only ever appears inside a
    longer source cell, which is a measurement artefact rather than a defect.
    """

    def cell_values(rows: Sequence[Sequence[object]]) -> list[str]:
        values = []
        for row in rows:
            for cell in row:
                raw = "".join(cell) if isinstance(cell, (list, tuple)) else cell
                text = normalize_cell_text(raw)
                if text:
                    values.append(text)
        return values

    source_values = cell_values(source_rows)
    generated_values = cell_values(generated_rows)
    generated_stream = "".join(generated_values)

    generated_counts: dict[str, int] = {}
    for text in generated_values:
        generated_counts[text] = generated_counts.get(text, 0) + 1
    source_counts: dict[str, int] = {}
    for text in source_values:
        source_counts[text] = source_counts.get(text, 0) + 1

    # Which source cells each generated cell carries, most specific first.
    annotated = []
    for text in generated_values:
        carried = [
            source
            for source in source_counts
            if source != text and len(source) >= _MIN_SUBSTRING_EVIDENCE and source in text
        ]
        annotated.append((text, carried))

    def carried_anywhere(source: str) -> bool:
        if source in generated_counts:
            return True
        if len(source) < _MIN_SUBSTRING_EVIDENCE:
            return False
        return source in generated_stream

    lost = [
        {"cell_text_length": len(text), "cell_text": text[:120]}
        for text, _count in sorted(source_counts.items())
        if not carried_anywhere(text)
    ]

    aggregated = []
    filled = []
    invented = []
    recorded = recorded_fill_values or {}
    for text, carried in annotated:
        if text in source_counts:
            continue
        if carried:
            aggregated.append(
                {
                    "generated_cell_text_length": len(text),
                    "aggregated_source_cell_count": len(carried),
                    "aggregated_source_cells": [item[:120] for item in carried[:10]],
                    "aggregated_source_cell_total_characters": sum(
                        len(item) for item in carried
                    ),
                    "generated_cell_coverage": round(
                        min(1.0, sum(len(item) for item in carried) / len(text)), 4
                    ),
                    "generated_cell_text": text[:120],
                }
            )
            continue
        owning = sorted(
            field
            for field, values in recorded.items()
            if any(value and value in text for value in values)
        )
        if owning:
            filled.append(
                {
                    "generated_cell_text_length": len(text),
                    "fact_fields": owning,
                    "generated_cell_text": text[:120],
                }
            )
            continue
        invented.append(
            {
                "cell_text_length": len(text),
                "generated_count": generated_counts[text],
                "cell_text": text[:120],
            }
        )

    duplicated = [
        {
            "cell_text_length": len(text),
            "source_count": count,
            "generated_count": generated_counts[text],
            "cell_text": text[:120],
        }
        for text, count in sorted(source_counts.items())
        if generated_counts.get(text, 0) > count
    ]

    source_total = len(source_values)
    covered = source_total - len(lost)
    return {
        "source_cell_count": source_total,
        "generated_cell_count": len(generated_values),
        "covered_source_cell_count": covered,
        "cell_coverage": round(covered / source_total, 4) if source_total else 1.0,
        "lost_cell_count": len(lost),
        "duplicated_cell_count": len(duplicated),
        "invented_cell_count": len(invented),
        "aggregated_cell_count": len(aggregated),
        "filled_cell_count": len(filled),
        "aggregated_source_cell_count": sum(
            item["aggregated_source_cell_count"] for item in aggregated
        ),
        "lost_cells": lost,
        "duplicated_cells": duplicated,
        "invented_cells": invented,
        "aggregated_cells": aggregated,
        "filled_cells": filled,
    }


def audit_logical_tables(generation_report: dict, document, source_rows_by_table: dict) -> dict:
    """Pair every logical table with its generated Word table and account cells.

    ``source_rows_by_table`` maps a logical table id to its source logical cell
    texts (``list[list[str]]``), supplied by the caller from the reconstruction
    plan so this audit reads the source structure, not the rendered output.
    """

    source_records = logical_table_source_records(generation_report)
    generated = list(_generated_cell_texts(document).items())
    filled_values = recorded_fill_values(generation_report)
    used: set[int] = set()
    records = []
    for record in source_records:
        rows = _source_row_texts(source_rows_by_table.get(record["table_id"]) or ())
        available = [(index, cells) for index, cells in generated if index not in used]
        word_index, score = _match_table(rows, available)
        if word_index is None:
            word_index, score = _match_table(rows, generated)
        generated_rows = dict(generated).get(word_index, [])
        if word_index is not None:
            used.add(word_index)
        accounting = _cell_accounting(
            rows, generated_rows, recorded_fill_values=filled_values
        )
        records.append(
            {
                **record,
                "generated_word_table_index": word_index,
                "generated_word_table_match_score": score,
                "generated_row_count": len(generated_rows),
                "generated_column_count": max(
                    (len(row) for row in generated_rows), default=0
                ),
                "editable_word_table": word_index is not None,
                **accounting,
            }
        )
    return {
        "logical_table_provenance_schema": "logical_table_provenance/1",
        "logical_table_count": len(records),
        "generated_word_table_count": len(generated),
        "unpaired_generated_word_table_count": len(
            [index for index, _cells in generated if index not in used]
        ),
        "total_source_cell_count": sum(r["source_cell_count"] for r in records),
        "total_lost_cell_count": sum(r["lost_cell_count"] for r in records),
        "total_duplicated_cell_count": sum(r["duplicated_cell_count"] for r in records),
        "total_invented_cell_count": sum(r["invented_cell_count"] for r in records),
        "total_aggregated_cell_count": sum(r["aggregated_cell_count"] for r in records),
        "total_filled_cell_count": sum(r["filled_cell_count"] for r in records),
        "total_aggregated_source_cell_count": sum(
            r["aggregated_source_cell_count"] for r in records
        ),
        "recorded_fill_field_count": len(filled_values),
        "tables": records,
    }


def provenance_for_plan(document, plan, *, source_rows, fill_applications=()) -> dict:
    """Provenance for one build's logical-table plan.

    ``plan`` is the compiled ``LogicalTablePlan`` the emitter consumed,
    ``source_rows`` maps each logical table id to its source logical cell texts
    and ``fill_applications`` are the recorded resolved-fact writes, so a builder
    records provenance from the same structure and the same write events it
    rendered rather than from a second reconstruction.

    Each source cell may be given as one string or as the page fragments that
    were assembled into it; both forms describe the same value.
    """

    report = {
        "logical_tables": [
            {
                "table_id": logical.table_id,
                "head_page": plan.head_keys[index][0],
                "head_table_index": plan.head_keys[index][1],
                "source_pages": logical.source_pages,
                "fragment_count": len(logical.fragments),
                "row_count": len(logical.rows),
                "column_count": logical.columns,
            }
            for index, logical in enumerate(plan.logical_tables)
        ],
        "source_fill_applications": [
            item.as_dict() if hasattr(item, "as_dict") else item
            for item in (fill_applications or ())
        ],
    }
    return audit_logical_tables(report, document, source_rows)


def source_rows_for_plan(plan) -> dict:
    """Each logical table's source cell texts, from the reconstruction itself."""

    return {
        logical.table_id: [
            [fragment.raw_text for fragment in cell.fragments]
            for row in logical.rows
            for cell in row.cells
        ]
        for logical in plan.logical_tables
    }


__all__ = [
    "audit_logical_tables",
    "iter_body_tables",
    "logical_table_source_records",
    "normalize_cell_text",
    "provenance_for_plan",
    "recorded_fill_values",
    "source_rows_for_plan",
]
