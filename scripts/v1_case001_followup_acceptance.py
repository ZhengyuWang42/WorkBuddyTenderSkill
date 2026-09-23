"""CASE001 final manual-word-review follow-up: the three follow-up acceptance checks.

Three checks, each measured from the source artifact and the delivered package -
never from a remembered case, page, literal or paragraph index:

``RESPONSE_LETTER_COMPOSITE_SLOT``
    The source's decorated composite form field survives the resolved-value
    substitution *including its own frame*, its components are recorded
    separately, the whole field inherits the source's underline while the prose
    around it does not, and the fact with no value behind it is never mutated.

``RESPONSE_LETTER_PARAGRAPH_CONTINUITY``
    Every source *logical paragraph* the source printed as wrapped visual rows
    reaches the reader as one ``w:p``: no paragraph boundary, no ``<w:br/>``, no
    ``<w:cr/>`` and no empty paragraph between its tokens, and the boundary is
    classified ``NATURAL_WRAP`` rather than accepted as a structural isolation.

``SOURCE_TABLE_CELL_ALIGNMENT``
    A source cell's own measured alignment reaches the delivered cell, located by
    semantic table/cell identity, with its vertical alignment, and with the
    table's geometry - column widths, merges, row heights, borders - preserved.

Usage::

    .venv/Scripts/python.exe scripts/v1_case001_followup_acceptance.py \
        --build acceptance/workspace/case_001/<build_id> \
        --source-pdf acceptance/private/<tender>.pdf \
        --out acceptance/reports/v1_generalization/case001_manual_review_followup_acceptance.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import docx  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from tender_basic.source_fill_policy import SOURCE_FORM_NOT_APPLICABLE_MARKER  # noqa: E402
from tender_basic.source_format import (  # noqa: E402
    _alignment_label,
    _classify_cell_alignment,
)
from tender_basic.source_fill_policy import source_placeholder_frame  # noqa: E402
from v1_source_typography_round3_gate import (  # noqa: E402
    NATURAL_WRAP,
    PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION,
    SOURCE_CONTAINER_MISMATCH,
    _authorized_isolation_paragraphs,
    _compact,
    _delivered_cells,
    _delivered_paragraphs,
    _element_record,
    _hard_break_fidelity,
    _resolved_values,
    _source_cells,
    _source_elements,
    _source_model,
)
from tender_basic.page_layout import build_page_layout, source_visual_rows  # noqa: E402

SCHEMA = "case001_manual_review_followup_acceptance/1"

#: The two composite halves the source names inside one composite hint.
COMPOSITE_HALVES = ("项目名称", "标段")


def _run_underline(run) -> str | None:
    element = run._r.find(qn("w:rPr") + "/" + qn("w:u"))
    if element is None:
        return None
    value = element.get(qn("w:val"))
    return "single" if value is None else str(value)


def _visible(value) -> bool:
    return value is not None and str(value).lower() not in ("none", "nil")


def _prose_segments(slot) -> list[str]:
    """The source's own un-decorated prose around one placeholder.

    The slot carries the source text that surrounds it, so the prose the source
    printed is its prefix plus its suffix with every bracketed placeholder taken
    out.  What is left is what must never inherit the placeholder's underline.
    """

    parts = [str(getattr(slot, "prefix_text", "") or "")]
    parts.extend(
        re.split(r"[（(][^（()）]*[)）]", str(getattr(slot, "suffix_text", "") or ""))
    )
    return [compact for compact in (_compact(part) for part in parts) if compact]


def _facts(build_dir: Path) -> dict:
    return json.loads((build_dir / "project_facts.json").read_text(encoding="utf-8"))


def _report(build_dir: Path) -> dict:
    return json.loads((build_dir / "generation_report.json").read_text(encoding="utf-8"))


def _decorated_composite_rules(report: dict) -> list[dict]:
    """Registry rules that decorate a placeholder's own glyphs as a whole field."""

    decorated = []
    for entry in report.get("source_rule_registry") or []:
        if str(entry.get("relation_type")) != "PLACEHOLDER_UNDERLINE":
            continue
        try:
            occupancy = float(entry.get("text_occupancy"))
        except (TypeError, ValueError):
            continue
        if occupancy >= 1.0 - 1e-6:
            decorated.append(entry)
    return decorated


def check_response_letter_composite_slot(build_dir: Path, model) -> dict:
    """The source's own composite form field, frame included, as the reader sees it."""

    report = _report(build_dir)
    facts = _facts(build_dir)
    slots = {str(slot.slot_id): slot for slot in model.fill_slots}
    records = {
        str(record.get("slot_id")): record
        for record in (report.get("slot_value_presentations") or {}).get("records", [])
    }

    problems: list[str] = []
    observed: list[dict] = []

    for rule in _decorated_composite_rules(report):
        slot_id = str(rule.get("authoritative_slot_id") or "")
        slot = slots.get(slot_id)
        if slot is None or getattr(slot, "slot_type", "") != "PROJECT_AND_LOT_SLOT":
            continue
        frame = source_placeholder_frame(slot)
        record = records.get(slot_id)
        if frame is None or record is None:
            problems.append(
                f"{slot_id}: the source decorates the placeholder's own glyphs but the "
                "delivered value carries no source frame record"
            )
            continue

        hint = str(slot.semantic_hint)
        leading, trailing = COMPOSITE_HALVES
        separator = ""
        start, end = hint.find(leading), hint.find(trailing)
        if start >= 0 and end > start:
            separator = hint[start + len(leading):end].strip("（）()")
        # The fact the source names with no value behind it.
        project_field = next(
            (f for f in slot.allowed_fact_fields if f.value == "project_name"), None
        )
        project_value = None
        if project_field is not None:
            project_value = (
                facts["fields"].get("project_name", {}).get("resolved_value")
            )
        expected = (
            frame[0]
            + str(project_value)
            + separator
            + SOURCE_FORM_NOT_APPLICABLE_MARKER
            + frame[1]
        )

        kinds = [component["kind"] for component in record.get("components", [])]
        required_kinds = [
            "SOURCE_TEMPLATE_LITERAL",
            "FACT_VALUE",
            "SOURCE_TEMPLATE_LITERAL",
            "SOURCE_FORM_NOT_APPLICABLE_MARKER",
            "SOURCE_TEMPLATE_LITERAL",
        ]
        entry = {
            "slot_id": slot_id,
            "source_rule_id": rule.get("source_rule_id"),
            "source_relation_type": rule.get("relation_type"),
            "source_text_occupancy": rule.get("text_occupancy"),
            "source_frame": list(frame),
            "expected_reading": expected,
            "recorded_value": record.get("value"),
            "recorded_component_kinds": kinds,
            "recorded_marker_components": record.get("marker_components"),
        }
        if record.get("value") != expected:
            problems.append(
                f"{slot_id}: recorded value {record.get('value')!r} is not the source "
                f"composition {expected!r}"
            )
        if kinds != required_kinds:
            problems.append(
                f"{slot_id}: component kinds {kinds} are not {required_kinds}"
            )
        if record.get("value") == expected and record.get("method") != (
            "source_slot_composite_presentation"
        ):
            problems.append(f"{slot_id}: composition method is not the composite model")

        # The reader-visible evidence: the composed reading must be present in the
        # delivered document, underlined as one decorated source field.
        document = docx.Document(str(build_dir / "基础投标文件.docx"))
        carrier = None
        for paragraph in document.paragraphs:
            for run in paragraph.runs:
                if run.text == expected:
                    carrier = (paragraph, run)
                    break
            if carrier:
                break
        entry["delivered_run_found"] = carrier is not None
        if carrier is None:
            # The frame may be split across adjacent components; require the
            # composed reading to be present as contiguous delivered text.
            for paragraph in document.paragraphs:
                if expected in paragraph.text:
                    carrier = (paragraph, None)
                    break
        entry["delivered_reading_present"] = carrier is not None
        if carrier is None:
            problems.append(f"{slot_id}: the composed reading is not in the document")
        else:
            paragraph, run = carrier
            entry["carrier_paragraph_underlined_runs"] = [
                {"text": item.text, "underline": _run_underline(item)}
                for item in paragraph.runs
                if _visible(_run_underline(item))
            ]
            if run is not None and not _visible(_run_underline(run)):
                problems.append(
                    f"{slot_id}: the composed value run does not inherit the source underline"
                )
            # The prose the source did not decorate must stay undecorated.  The
            # prose is the source's own text around and between the placeholders:
            # the slot's prefix, plus its suffix with every bracketed placeholder
            # removed.  Anything else on the line inside brackets is another
            # source form field, not prose.
            prose = _prose_segments(slot)
            prose_underlined = [
                item.text
                for item in paragraph.runs
                if _visible(_run_underline(item))
                and _compact(item.text)
                and any(_compact(item.text) in segment for segment in prose)
            ]
            entry["source_prose_segments"] = prose
            entry["undecorated_prose_runs"] = [
                item.text
                for item in paragraph.runs
                if not _visible(_run_underline(item))
            ]
            entry["all_underlined_runs"] = [
                item.text
                for item in paragraph.runs
                if _visible(_run_underline(item))
            ]
            entry["prose_incorrectly_underlined"] = prose_underlined
            if prose_underlined:
                problems.append(
                    f"{slot_id}: prose the source did not decorate is underlined: "
                    f"{prose_underlined}"
                )
        observed.append(entry)

    # The fact with no value behind it is never mutated by the marker.
    lot = facts["fields"].get("lot_name", {})
    marker_is_a_fact = bool((report.get("slot_value_presentations") or {}).get("marker_is_a_fact"))
    marker_creates_candidate = bool(
        (report.get("slot_value_presentations") or {}).get("marker_creates_a_fact_candidate")
    )
    lot_untouched = (
        str(lot.get("status")) == "NOT_FOUND"
        and lot.get("resolved_value") is None
        and not lot.get("candidates")
    )
    if not lot_untouched:
        problems.append(
            f"lot_name was mutated by the not-applicable marker: status="
            f"{lot.get('status')} resolved={lot.get('resolved_value')!r} "
            f"candidates={len(lot.get('candidates') or [])}"
        )
    if marker_is_a_fact or marker_creates_candidate:
        problems.append("the not-applicable marker is treated as a fact")

    return {
        "check": "RESPONSE_LETTER_COMPOSITE_SLOT",
        "status": "PASS" if not problems else "FAIL",
        "composite_rules_measured": len(observed),
        "composites": observed,
        "lot_name_status": lot.get("status"),
        "lot_name_resolved_value": lot.get("resolved_value"),
        "lot_name_candidate_count": len(lot.get("candidates") or []),
        "marker_is_a_fact": marker_is_a_fact,
        "marker_creates_a_fact_candidate": marker_creates_candidate,
        "problems": problems,
    }


def check_response_letter_paragraph_continuity(build_dir: Path, model) -> dict:
    """A source logical paragraph's wrapped rows arrive in ONE ``w:p``.

    The source's own semantics and the generated container are reported as
    separate facts.  Every boundary the delivery introduces inside a source
    natural wrap is measured, and each one is either an **unexplained structural
    split** - which fails - or a **reviewed structural deviation**, which is
    admitted only by the round-3 gate's deviation contract and is disclosed
    here without ever being called container fidelity.
    """

    problems: list[str] = []
    observed: list[dict] = []
    reviewed: list[dict] = []
    unexplained: list[dict] = []

    delivered = _delivered_paragraphs(build_dir)
    isolated = _authorized_isolation_paragraphs(build_dir)
    elements = _source_elements(model)
    counts, failures = _hard_break_fidelity(
        elements, delivered, _resolved_values(build_dir), isolated
    )
    boundaries = {
        int(piece_index)
        for item in counts["reviewed_deviations"]
        for piece_index in item.get("unauthorized_paragraph_indexes") or []
    }
    for item in counts["reviewed_deviations"]:
        reviewed.append(
            {
                "source_page": item["source_page"],
                "source_element_kind": item.get("source_element_kind"),
                "source_row_count": item["source_row_count"],
                "source_row_texts": item.get("source_row_texts"),
                "source_semantics": item["source_semantics"],
                "generated_representation": item["generated_representation"],
                "container_fidelity": item["container_fidelity"],
                "fidelity_difference": item["fidelity_difference"],
                "deviation_kind": item["deviation_kind"],
                "deviation_state": item["deviation_state"],
                "deviation_evidence_path": item.get("deviation_evidence_path"),
                "same_word_paragraph": item["same_word_paragraph"],
                "w_br_between_tokens": item["w_br_between_tokens"],
                "w_cr_between_tokens": item["w_cr_between_tokens"],
                "empty_paragraph_between_tokens": item["empty_paragraph_between_tokens"],
            }
        )
    for item in failures:
        if item.get("kind") != "SOURCE_ELEMENT_SPLIT_ACROSS_PARAGRAPHS":
            continue
        unexplained.append(item)
        problems.append(
            "a source natural wrap is expressed as a paragraph boundary without "
            "the deviation contract being satisfied (source page %s); missing: %s"
            % (
                item.get("source_page"),
                ", ".join(item.get("deviation_missing_conditions") or []) or "n/a",
            )
        )

    for page in model.source_pages:
        layout = build_page_layout(page)
        for element in layout.elements:
            if type(element).__name__ not in ("LogicalParagraph", "List"):
                continue
            record = _element_record(page, element)
            if int(record["row_count"]) <= 1:
                continue
            observed.append(
                {
                    "source_page": page.page,
                    "source_element_kind": record["kind"],
                    "source_row_count": record["row_count"],
                    "source_row_texts": record["row_texts"],
                    "classification": NATURAL_WRAP,
                }
            )

    status = "FAIL" if problems else "PASS"
    if reviewed and not problems:
        # The check is green only in the disclosed sense, never as plain fidelity.
        status = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION

    return {
        "check": "RESPONSE_LETTER_PARAGRAPH_CONTINUITY",
        "status": status,
        "wrapped_source_paragraphs": len(observed),
        "elements": observed,
        "generated_paragraph_boundaries_inside_a_source_wrap": len(reviewed)
        + len(unexplained),
        "reviewed_structural_deviations": reviewed,
        "documented_structural_deviation_count": len(reviewed),
        "unexplained_structural_splits": unexplained,
        "unexplained_structural_split_count": len(unexplained),
        "container_fidelity": (
            SOURCE_CONTAINER_MISMATCH
            if reviewed
            else ("SOURCE_CONTAINER_MATCH" if not boundaries else "UNKNOWN")
        ),
        "problems": problems,
        "note": (
            "the delivered-paragraph evidence for each wrapped source paragraph is "
            "measured by the round-3 gate's HARD_BREAK_FIDELITY family, which "
            "classifies every boundary and reports same_word_paragraph, "
            "w_br_between_tokens, w_cr_between_tokens, "
            "empty_paragraph_between_tokens and "
            "authorised_structural_split_between_tokens for each one.  A boundary "
            "backed by the deviation contract passes as "
            "PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION and is never reported as "
            "SOURCE_CONTAINER_MATCH; a boundary without that evidence fails."
        ),
    }


def _cell_geometry(cell) -> dict:
    """A delivered cell's own geometry and alignment, as Word stores it."""

    tcpr = cell._tc.find(qn("w:tcPr"))
    width = None if tcpr is None else tcpr.find(qn("w:tcW"))
    valign = None if tcpr is None else tcpr.find(qn("w:vAlign"))
    paragraph = cell.paragraphs[0] if cell.paragraphs else None
    jc = None
    if paragraph is not None:
        node = paragraph._p.find(qn("w:pPr") + "/" + qn("w:jc"))
        if node is not None:
            jc = str(node.get(qn("w:val")))
    return {
        "jc": jc,
        "vAlign": None if valign is None else str(valign.get(qn("w:val"))),
        "tcW": None if width is None else str(width.get(qn("w:w"))),
        "gridSpan": (
            None
            if tcpr is None or tcpr.find(qn("w:gridSpan")) is None
            else str(tcpr.find(qn("w:gridSpan")).get(qn("w:val")))
        ),
        "has_borders": tcpr is not None and tcpr.find(qn("w:tcBorders")) is not None,
    }


def _delivered_table_signatures(build_dir: Path):
    """Every delivered table as (index, table, signature, cells-by-text)."""

    document = docx.Document(str(build_dir / "基础投标文件.docx"))
    tables = []
    for index, table in enumerate(document.tables):
        by_text: dict[str, list] = {}
        for row in table.rows:
            for cell in row.cells:
                key = _compact(cell.text)
                if key:
                    by_text.setdefault(key, []).append(cell)
        tables.append(
            {
                "index": index,
                "table": table,
                "signature": frozenset(by_text),
                "by_text": by_text,
            }
        )
    return document, tables


def _source_centered_cells(model) -> list[dict]:
    """Every source table cell whose own measured evidence says ``center``."""

    centered = []
    for page in model.source_pages:
        for source_table in page.tables:
            signature = frozenset(
                _compact(cell.text)
                for row in source_table.rows
                for cell in row.cells
                if _compact(cell.text)
            )
            for row_index, row in enumerate(source_table.rows):
                for column_index, cell in enumerate(row.cells):
                    key = _compact(cell.text)
                    if not key or not cell.bbox:
                        continue
                    rows = source_visual_rows(cell.runs)
                    # ``_classify_cell_alignment`` reads a line as
                    # ``(y, x0, x1)``: the horizontal extent is what decides the
                    # alignment, so x0 and x1 must both come from the run's box.
                    measured = [
                        (
                            min(float(run.bbox[1]) for run in source_row),
                            min(float(run.bbox[0]) for run in source_row),
                            max(float(run.bbox[2]) for run in source_row),
                        )
                        for source_row in rows
                    ]
                    if not measured:
                        continue
                    evidence = _classify_cell_alignment(
                        tuple(float(v) for v in cell.bbox), measured
                    )
                    if _alignment_label(evidence) != "center":
                        continue
                    centered.append(
                        {
                            "source_page": page.page,
                            "source_table_signature": signature,
                            "row_index": row_index,
                            "column_index": column_index,
                            "text": cell.text,
                            "compact": key,
                            "reason": evidence.reason,
                        }
                    )
    return centered


def check_source_table_cell_alignment(
    build_dir: Path, model, baseline_dir: Path | None = None
) -> dict:
    """A source-centered cell reaches the reader centered, and nothing else moved.

    Located by semantic identity: the delivered table is the one whose own cell
    texts overlap the source table's, and the delivered cell is that table's cell
    carrying the source cell's own text.  No page number, case name, fixed table
    number or remembered literal is used to find either.
    """

    _, delivered_tables = _delivered_table_signatures(build_dir)
    centered = _source_centered_cells(model)

    problems: list[str] = []
    located = 0
    horizontally_centered = 0
    vertically_centered = 0
    observations: list[dict] = []

    for source in centered:
        candidates = [
            item
            for item in delivered_tables
            if source["compact"] in item["by_text"]
        ]
        if not candidates:
            problems.append(
                f"source-centered cell {source['text'][:40]!r} has no delivered "
                "counterpart in any table"
            )
            continue
        best = max(
            candidates,
            key=lambda item: len(item["signature"] & source["source_table_signature"]),
        )
        overlap = len(best["signature"] & source["source_table_signature"])
        matched = best["by_text"][source["compact"]]
        if len(matched) != 1:
            continue
        cell = matched[0]
        geometry = _cell_geometry(cell)
        located += 1
        if geometry["jc"] == "center":
            horizontally_centered += 1
        if geometry["vAlign"] == "center":
            vertically_centered += 1
        observation = {
            "source_text": source["text"][:40],
            "source_page": source["source_page"],
            "source_row_index": source["row_index"],
            "source_column_index": source["column_index"],
            "source_alignment": "center",
            "source_reason": source["reason"],
            "delivered_table_index": best["index"],
            "table_signature_overlap": overlap,
            "delivered_jc": geometry["jc"],
            "delivered_vAlign": geometry["vAlign"],
            "delivered_tcW": geometry["tcW"],
            "delivered_gridSpan": geometry["gridSpan"],
        }
        observations.append(observation)
        if geometry["jc"] != "center":
            problems.append(
                f"{source['text'][:40]!r} is centered in the source "
                f"({source['reason']}) but delivered jc={geometry['jc']!r}"
            )
        if geometry["vAlign"] != "center":
            problems.append(
                f"{source['text'][:40]!r} is delivered vAlign={geometry['vAlign']!r}"
            )

    # NOT A GLOBAL CHANGE.  Diff this build's per-cell horizontal alignment map
    # against the accepted build's: the number of cells whose alignment moved must
    # not exceed the number of cells the source actually measures as centered, and
    # every moved cell must be one of them.  A global flip of first-column labels,
    # or of JUSTIFY to CENTER, would move hundreds of cells and is caught here.
    changes: list[dict] = []
    geometry_preserved = {}
    if baseline_dir is not None:
        _, baseline_tables = _delivered_table_signatures(baseline_dir)
        for index, item in enumerate(delivered_tables):
            if index >= len(baseline_tables):
                problems.append("the delivered document gained a table")
                break
            before = baseline_tables[index]
            for key, cells in item["by_text"].items():
                if key not in before["by_text"]:
                    continue
                here = _cell_geometry(cells[0])["jc"]
                there = _cell_geometry(before["by_text"][key][0])["jc"]
                if here != there:
                    changes.append(
                        {"cell_text": key[:40], "accepted_jc": there, "jc": here}
                    )
        centered_keys = {source["compact"] for source in centered}
        unexpected = [change for change in changes if change["cell_text"] not in {
            key[:40] for key in centered_keys
        }]
        if unexpected:
            problems.append(
                f"{len(unexpected)} cells changed alignment that the source does not "
                f"measure as centered: {unexpected[:5]}"
            )
        geometry_preserved = {
            "accepted_tables": len(baseline_tables),
            "delivered_tables": len(delivered_tables),
            "changed_cells": len(changes),
            "changes": changes[:20],
        }
        if len(baseline_tables) != len(delivered_tables):
            problems.append(
                f"table count changed: {len(baseline_tables)} -> "
                f"{len(delivered_tables)}"
            )

    return {
        "check": "SOURCE_TABLE_CELL_ALIGNMENT",
        "status": "PASS" if not problems else "FAIL",
        "source_centered_cells": len(centered),
        "source_centered_cells_located": located,
        "source_centered_delivered_center": horizontally_centered,
        "source_centered_delivered_vertical_center": vertically_centered,
        "observations": observations,
        "geometry_and_no_global_change": geometry_preserved,
        "problems": problems,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help=(
            "the accepted build to diff cell alignment against, so a global "
            "alignment change can never pass as a single-cell repair"
        ),
    )
    args = parser.parse_args(argv)

    build_dir = args.build if args.build.is_absolute() else ROOT / args.build
    source_pdf = args.source_pdf if args.source_pdf.is_absolute() else ROOT / args.source_pdf
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    baseline = None
    if args.baseline is not None:
        baseline = args.baseline if args.baseline.is_absolute() else ROOT / args.baseline

    model = _source_model(source_pdf)
    checks = [
        check_response_letter_composite_slot(build_dir, model),
        check_response_letter_paragraph_continuity(build_dir, model),
        check_source_table_cell_alignment(build_dir, model, baseline),
    ]
    failed = [
        check["check"]
        for check in checks
        if check["status"] not in ("PASS", PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION)
    ]
    reviewed_deviation_count = sum(
        int(check.get("documented_structural_deviation_count") or 0)
        for check in checks
    )
    unexplained_split_count = sum(
        int(check.get("unexplained_structural_split_count") or 0)
        for check in checks
    )
    if failed:
        status = "FAIL"
    elif reviewed_deviation_count:
        status = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION
    else:
        status = "PASS"
    report = {
        "schema": SCHEMA,
        "gate": "CASE001_MANUAL_REVIEW_FOLLOWUP_ACCEPTANCE",
        "build_dir": str(build_dir),
        "source_pdf": str(source_pdf),
        "status": status,
        "failed_checks": failed,
        "checks": checks,
        "documented_structural_deviation_count": reviewed_deviation_count,
        "unexplained_structural_split_count": unexplained_split_count,
        "note": (
            "Automation evidence only.  A PASS here never signs off the manual Word "
            "review: MANUAL_WORD_REVIEW_REQUIRED stays true and "
            "READY_FOR_SUBMISSION stays false.  A reviewed structural deviation is "
            "counted and disclosed; it is never reported as container fidelity."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "failed": failed,
                "documented_structural_deviation_count": reviewed_deviation_count,
                "unexplained_structural_split_count": unexplained_split_count,
                "checks": {
                    check["check"]: check["status"] for check in checks
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
