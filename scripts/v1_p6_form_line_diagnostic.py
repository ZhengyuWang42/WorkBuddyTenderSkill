"""Diagnose a delivered form-line paragraph that carries an inline ``w:br``.

Read-only.  Nothing here changes state: every value is read from the delivered
build's own artifacts (the DOCX, the generated PDF, the generation report) or
from the source PDF, and every conclusion is derived from geometry rather than
from a literal, a page number or a rule id.

The question the diagnostic answers is the one the fix depends on:

1. does the source draw the label, the fill rule and the trailing suffix as ONE
   visual row, or did the source itself break the row?
2. did the source ask for an explicit break at all?
3. what blank class does the source rule carry, so the repair preserves it?
4. does the delivered paragraph keep that one row, and if not, by how many rows
   did it grow and where did the rule end up?

It finds the paragraph generically - any delivered paragraph carrying a
non-page ``w:br`` - so it reports a defect rather than confirming a suspicion.

Known limitation (measured, not assumed): ``diagnose()`` collects the break
blanks **document-wide**, so ``form_line_break_records`` on a finding is the set
of every break blank in the document rather than that paragraph's own.  On a
document with exactly one such row - the CASE001 form line - that set is the
right one and the verdict is exact.  On a document with several, the added rows
are measured against a neighbouring row's rule and the verdict is spurious.  The
emitter's paragraph token in ``emission_id`` cannot be used to scope them: it is
the emitter's own counter, not the ``python-docx`` body index.  Scope by the
paragraph's own tab stops before trusting this tool on a multi-row document; for
CASE002 the per-row measurement lives in
``acceptance/reports/v1_generalization/case002_p6_unexpected_hardbreak_row_measure.json``.

Usage::

    .venv/Scripts/python.exe scripts/v1_p6_form_line_diagnostic.py \
        --build acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_followup \
        --source-pdf acceptance/private/<source>.pdf \
        --out acceptance/reports/v1_generalization/case001_p6_unexpected_hardbreak_diagnostic.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import docx
import pymupdf
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RULE_MAX_HEIGHT_PT = 2.4
RULE_MIN_WIDTH_PT = 6.0
ROW_TOLERANCE_PT = 1.5


def _paragraph_breaks(paragraph) -> dict:
    """Every hard break inside one delivered paragraph, with its position."""

    page_breaks = 0
    line_breaks = 0
    positions = []
    for index, run in enumerate(paragraph.runs):
        for node in run._r.findall(qn("w:br")):
            if node.get(qn("w:type")) == "page":
                page_breaks += 1
                positions.append({"run_index": index, "kind": "PAGE"})
            else:
                line_breaks += 1
                positions.append({"run_index": index, "kind": "LINE"})
    carriage_returns = len(paragraph._p.findall(".//" + qn("w:cr")))
    return {
        "line_break_count": line_breaks,
        "page_break_count": page_breaks,
        "carriage_return_count": carriage_returns,
        "break_positions": positions,
    }


def _run_records(paragraph) -> list:
    records = []
    for index, run in enumerate(paragraph.runs):
        records.append(
            {
                "run_index": index,
                "text": run.text,
                "literal_tab_characters": run.text.count("\t"),
                "tab_elements": len(run._r.findall(".//" + qn("w:tab"))),
                "line_breaks": len(
                    [
                        node
                        for node in run._r.findall(qn("w:br"))
                        if node.get(qn("w:type")) != "page"
                    ]
                ),
                "underline": run.underline,
                "bold": run.bold,
                "font_size_pt": (
                    float(run.font.size.pt) if run.font.size is not None else None
                ),
            }
        )
    return records


def _tab_stops(paragraph) -> list:
    stops = []
    for stop in paragraph.paragraph_format.tab_stops:
        stops.append(
            {
                "position_pt": round(float(stop.position.pt), 2),
                "alignment": str(stop.alignment),
                "leader": str(stop.leader),
            }
        )
    return stops


def _pdf_rules(page) -> list:
    rules = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.height <= RULE_MAX_HEIGHT_PT and rect.width >= RULE_MIN_WIDTH_PT:
            rules.append(
                {
                    "x0": round(rect.x0, 2),
                    "x1": round(rect.x1, 2),
                    "y": round((rect.y0 + rect.y1) / 2, 2),
                    "width_pt": round(rect.width, 2),
                }
            )
    rules.sort(key=lambda rule: (rule["y"], rule["x0"]))
    return rules


def _pdf_lines(page, *, top: float, bottom: float) -> list:
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            bbox = line["bbox"]
            if bbox[3] < top or bbox[1] > bottom:
                continue
            text = "".join(span["text"] for span in line["spans"])
            if not text.strip():
                continue
            lines.append(
                {
                    "text": text,
                    "x0": round(bbox[0], 2),
                    "x1": round(bbox[2], 2),
                    "top": round(bbox[1], 2),
                    "bottom": round(bbox[3], 2),
                    "center_y": round((bbox[1] + bbox[3]) / 2, 2),
                }
            )
    lines.sort(key=lambda item: (item["center_y"], item["x0"]))
    return lines


def _rows(lines: list) -> list:
    """Group text lines into visual rows by their vertical overlap."""

    rows = []
    for line in lines:
        for row in rows:
            if abs(row["center_y"] - line["center_y"]) <= ROW_TOLERANCE_PT:
                row["lines"].append(line)
                row["x0"] = min(row["x0"], line["x0"])
                row["x1"] = max(row["x1"], line["x1"])
                row["top"] = min(row["top"], line["top"])
                row["bottom"] = max(row["bottom"], line["bottom"])
                row["text"] = "".join(
                    item["text"] for item in sorted(row["lines"], key=lambda i: i["x0"])
                )
                break
        else:
            rows.append(
                {
                    "center_y": line["center_y"],
                    "top": line["top"],
                    "bottom": line["bottom"],
                    "x0": line["x0"],
                    "x1": line["x1"],
                    "text": line["text"],
                    "lines": [line],
                }
            )
    rows.sort(key=lambda row: row["center_y"])
    for index, row in enumerate(rows, start=1):
        row["row_index"] = index
    return rows


def _nearest_rule(rules: list, x0: float, x1: float, *, tolerance: float = 1.0):
    best = None
    for rule in rules:
        if abs(rule["x0"] - x0) <= tolerance and abs(rule["x1"] - x1) <= tolerance:
            if best is None or abs(rule["x0"] - x0) < abs(best["x0"] - x0):
                best = rule
    return best


def _row_containing(rules: list, lines: list, *, tolerance: float = 1.5):
    """The text rows a rule's own y sits on, if any."""

    return [
        row
        for row in lines
        if row["top"] - tolerance <= rule["y"] <= row["bottom"] + tolerance
    ]


def _generation_report(build: Path) -> dict:
    """One build's own generation report."""

    return json.loads((build / "generation_report.json").read_text(encoding="utf-8"))


def diagnose(build: Path, source_pdf: Path) -> dict:
    report_path = build / "generation_report.json"
    report = _generation_report(build)
    docx_path = build / "基础投标文件.docx"
    generated_pdf = build / "基础投标文件.pdf"

    document = docx.Document(str(docx_path))
    # The generation report indexes delivered body paragraphs, so the document's
    # own paragraph stream is the matching view.
    paragraphs = list(document.paragraphs)

    inline_break_paragraphs = []
    for index, paragraph in enumerate(paragraphs):
        breaks = _paragraph_breaks(paragraph)
        if not breaks["line_break_count"] and not breaks["carriage_return_count"]:
            continue
        inline_break_paragraphs.append(
            {"paragraph_index": index, "paragraph": paragraph, "breaks": breaks}
        )

    registry = report.get("source_rule_registry") or []
    positioned = report.get("positioned_blank_records") or []
    logical = {
        record.get("paragraph_index"): record
        for record in (report.get("logical_paragraph_records") or [])
    }

    source_document = pymupdf.open(source_pdf)
    generated_document = pymupdf.open(generated_pdf)

    findings = []
    for entry in inline_break_paragraphs:
        paragraph = entry["paragraph"]
        index = entry["paragraph_index"]
        record = logical.get(index) or {}
        source_page_number = record.get("source_page")
        text_bbox = [round(float(value), 2) for value in (record.get("text_bbox") or [])]

        blanks = [
            item
            for item in positioned
            if item.get("form_layout_line_break")
        ]
        findings.append(
            {
                "generated_paragraph_index": index,
                "style": paragraph.style.name if paragraph.style else None,
                "alignment": str(paragraph.paragraph_format.alignment),
                "space_before_pt": (
                    float(paragraph.paragraph_format.space_before.pt)
                    if paragraph.paragraph_format.space_before is not None
                    else None
                ),
                "space_after_pt": (
                    float(paragraph.paragraph_format.space_after.pt)
                    if paragraph.paragraph_format.space_after is not None
                    else None
                ),
                "left_indent_pt": (
                    float(paragraph.paragraph_format.left_indent.pt)
                    if paragraph.paragraph_format.left_indent is not None
                    else None
                ),
                "first_line_indent_pt": (
                    float(paragraph.paragraph_format.first_line_indent.pt)
                    if paragraph.paragraph_format.first_line_indent is not None
                    else None
                ),
                "tab_stops": _tab_stops(paragraph),
                "paragraph_text": paragraph.text,
                "label_before_first_break": paragraph.text.split("\n")[0],
                "runs": _run_records(paragraph),
                "hard_breaks": entry["breaks"],
                "source_identity": {
                    "source_page": source_page_number,
                    "kind": record.get("kind"),
                    "role": record.get("role"),
                    "source_text": record.get("source_text"),
                    "delivered_text": record.get("text"),
                    "text_bbox": text_bbox,
                    "source_lines": record.get("source_lines"),
                    "source_baselines": record.get("source_baselines"),
                    "first_line_indent_pt": record.get("first_line_indent_pt"),
                },
                "form_line_break_records": blanks,
                "field_binding": {
                    "semantic_slot": (
                        blanks[0].get("semantic_slot") if blanks else None
                    ),
                    "owner_driven_value": bool(
                        report.get("owner_driven_value_emission_count")
                    ),
                },
            }
        )
    source_document.close()
    generated_document.close()

    return {
        "schema": "p6_form_line_diagnostic/1",
        "build": build.name,
        "generated_docx": docx_path.name,
        "generation_report": report_path.name,
        "inline_break_paragraph_count": len(inline_break_paragraphs),
        "generated_w_br_total": sum(
            entry["breaks"]["line_break_count"] for entry in inline_break_paragraphs
        ),
        "generated_w_cr_total": sum(
            entry["breaks"]["carriage_return_count"]
            for entry in inline_break_paragraphs
        ),
        "form_layout_break_count": report.get("form_layout_break_count"),
        "source_form_layout_line_count": report.get("source_form_layout_line_count"),
        "findings": findings,
        "root_cause": _root_cause(report),
        "source_rule_registry_matches": [
            item
            for item in registry
            if any(
                abs(item.get("x0", 0) - blank.get("source_x0", 0)) <= 1.0
                and abs(item.get("x1", 0) - blank.get("source_x1", 0)) <= 1.0
                for finding in findings
                for blank in finding["form_line_break_records"]
            )
        ],
    }


def _label_line(lines: list, label: str, *, tolerance: float = ROW_TOLERANCE_PT):
    """The text line that carries a form row's label.

    A delivered row that keeps its source's form line is extracted as ONE text
    line - label, blank and suffix together - so the label is found by prefix
    rather than by equality, and the shortest such line wins.  Nothing here keys
    on a page, a paragraph index or a rule id.
    """

    wanted = label.strip()
    candidates = [
        line for line in lines if line["text"].strip().startswith(wanted)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda line: len(line["text"].strip()))


def _row_for_y(rows: list, y: float, *, tolerance: float = ROW_TOLERANCE_PT):
    """The visual row a horizontal rule's own y is drawn on."""

    for row in rows:
        if row["top"] - tolerance <= y <= row["bottom"] + tolerance:
            return row
    return None


def _row_bound_band(lines: list, label_line: dict, rule_y: float) -> list:
    """The rows spanning one form row: its label down to its own rule.

    The band is bounded by the paragraph's own evidence - the label line and the
    rule's y - so a neighbouring paragraph can never inflate the row count.
    """

    top = label_line["top"] - ROW_TOLERANCE_PT
    bottom = max(label_line["bottom"], rule_y)
    return [line for line in lines if top <= line["center_y"] <= bottom]


def _targets(diagnostic: dict, reference: dict | None) -> list:
    """The source form rows to measure, named by source evidence only.

    A row is identified by its own source page, its own label and its own rule
    span - never by a build id, a paragraph index or a rule id - so the very
    same row can be measured before and after a repair and the two measurements
    are directly comparable.
    """

    targets = []
    seen = set()
    for finding in diagnostic["findings"]:
        blank = (
            finding["form_line_break_records"][0]
            if finding["form_line_break_records"]
            else None
        )
        label = finding["label_before_first_break"]
        if blank is None or not label:
            continue
        target = {
            "label": label,
            "source_page": finding["source_identity"]["source_page"],
            "span": {
                "x0": float(blank["source_x0"]),
                "x1": float(blank["source_x1"]),
            },
            "generated_paragraph_index": finding["generated_paragraph_index"],
            "selection_basis": "delivered_inline_hard_break",
        }
        key = (target["source_page"], round(target["span"]["x0"], 1), label)
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)

    for measured in (reference or {}).get("measured", []):
        span = measured.get("declared_source_rule_span") or {}
        label = measured.get("label")
        if not label or span.get("x0") is None:
            continue
        key = (measured["source_page"], round(float(span["x0"]), 1), label)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "label": label,
                "source_page": measured["source_page"],
                "span": {"x0": float(span["x0"]), "x1": float(span["x1"])},
                "generated_paragraph_index": None,
                "selection_basis": "reference_source_row",
            }
        )
    return targets


def measure(
    build: Path,
    source_pdf: Path,
    targets: list,
) -> dict:
    """Measure each source form row in the source PDF and in the delivered PDF.

    The comparison is deliberately row-level: whether the source drew the label
    and the fill rule as one visual row, and whether the delivered page still
    does.
    """

    generated_document = pymupdf.open(build / "基础投标文件.pdf")
    source_document = pymupdf.open(source_pdf)
    measurements = []
    for target in targets:
        source_page_number = target["source_page"]
        label = target["label"]
        span = target["span"]

        source_page = source_document[source_page_number - 1]
        source_all_lines = _pdf_lines(
            source_page, top=0.0, bottom=source_page.rect.height
        )
        source_label_line = _label_line(source_all_lines, label)
        source_matched_rule = _nearest_rule(
            _pdf_rules(source_page), span["x0"], span["x1"]
        )
        if source_label_line is None or source_matched_rule is None:
            continue
        source_rows = _rows(
            _row_bound_band(source_all_lines, source_label_line, source_matched_rule["y"])
        )
        source_label_row = _row_for_y(source_rows, source_label_line["center_y"])
        source_rule_row = _row_for_y(source_rows, source_matched_rule["y"])

        generated_page = None
        generated_rule = None
        generated_label_line = None
        for page_index in range(len(generated_document)):
            page = generated_document[page_index]
            matched = _nearest_rule(_pdf_rules(page), span["x0"], span["x1"])
            if matched is None:
                continue
            lines = _pdf_lines(page, top=0.0, bottom=page.rect.height)
            candidate = _label_line(lines, label)
            if candidate is None:
                continue
            generated_page = page
            generated_rule = matched
            generated_label_line = candidate
            generated_all_lines = lines
            break

        delivered_rows = []
        delivered_label_row = None
        delivered_rule_row = None
        if generated_rule is not None and generated_label_line is not None:
            delivered_rows = _rows(
                _row_bound_band(
                    generated_all_lines, generated_label_line, generated_rule["y"]
                )
            )
            delivered_label_row = _row_for_y(
                delivered_rows, generated_label_line["center_y"]
            )
            delivered_rule_row = _row_for_y(delivered_rows, generated_rule["y"])

        measurements.append(
            {
                "generated_paragraph_index": target["generated_paragraph_index"],
                "selection_basis": target["selection_basis"],
                "label": label,
                "source_page": source_page_number,
                "source_label_line": source_label_line,
                "source_rule": source_matched_rule,
                "declared_source_rule_span": span,
                "source_row_count": len(source_rows),
                "source_rows": source_rows,
                "source_label_row_index": (
                    source_label_row["row_index"] if source_label_row else None
                ),
                "source_rule_row_index": (
                    source_rule_row["row_index"] if source_rule_row else None
                ),
                "source_rule_shares_the_label_row": bool(
                    source_label_row
                    and source_rule_row
                    and source_label_row["row_index"] == source_rule_row["row_index"]
                ),
                "delivered_pdf_page": (
                    generated_page.number + 1 if generated_page is not None else None
                ),
                "delivered_label_line": generated_label_line,
                "delivered_rule": generated_rule,
                "delivered_rows": delivered_rows,
                "delivered_row_count": len(delivered_rows),
                "delivered_label_row_index": (
                    delivered_label_row["row_index"] if delivered_label_row else None
                ),
                "delivered_rule_row_index": (
                    delivered_rule_row["row_index"] if delivered_rule_row else None
                ),
                "delivered_rule_shares_the_label_row": bool(
                    delivered_label_row
                    and delivered_rule_row
                    and delivered_label_row["row_index"] == delivered_rule_row["row_index"]
                ),
                "rows_added": (
                    len(delivered_rows) - len(source_rows) if delivered_rows else None
                ),
                "rule_x0_error_pt": (
                    round(generated_rule["x0"] - span["x0"], 2)
                    if generated_rule
                    else None
                ),
                "rule_x1_error_pt": (
                    round(generated_rule["x1"] - span["x1"], 2)
                    if generated_rule
                    else None
                ),
            }
        )
    source_document.close()
    generated_document.close()
    return {"measured": measurements}


def _root_cause(report: dict) -> dict:
    """Why the emitter opened a form line, from its own recorded evidence.

    The emitter records the cursor reach it measured at the moment it decided.
    Comparing that reach with the blank's own source start says whether the
    blank was forward-reachable: an overshoot of zero means the cursor was
    standing exactly on the blank's start, so no break was needed to reach it.
    """

    breaks = report.get("positioned_form_layout_breaks") or []
    records = []
    for record in breaks:
        source_x0 = record.get("source_x0")
        reach = record.get("previous_reach_pt")
        overshoot = record.get("overshoot_pt")
        reachable = (
            source_x0 is not None
            and reach is not None
            and float(source_x0) >= float(reach) - 1.0
        )
        records.append(
            {
                "source_x0": source_x0,
                "source_x1": record.get("source_x1"),
                "previous_reach_pt": reach,
                "overshoot_pt": overshoot,
                "recorded_reason": record.get("reason"),
                "blank_was_forward_reachable": reachable,
            }
        )
    reachable_only = bool(records) and all(
        record["blank_was_forward_reachable"] for record in records
    )
    return {
        "emitter_path": (
            "tender_basic/word_safe_source_builder.py::_render_positioned_blank"
        ),
        "emitting_condition": (
            "not managed and not in_table_cell and "
            '(paragraph_so_far.strip("\\t") or blank_x0 + 1.0 < reach)'
        ),
        "authorising_clause": 'paragraph_so_far.strip("\\t")',
        "geometric_clause": "blank_x0 + 1.0 < reach",
        "classification": (
            "FORM_BLANK_REPRESENTATION_FORCED_BREAK"
            if reachable_only
            else "OTHER_PROVEN_CAUSE"
        ),
        "proven": (
            "the geometric clause was false - the blank's own source start was "
            "at or ahead of the cursor - so only the text-presence clause "
            'paragraph_so_far.strip("\\t") authorised the break'
            if reachable_only
            else "the geometric clause was true"
        ),
        "records": records,
        "form_layout_break_count": report.get("form_layout_break_count"),
        "not_a_semantic_break": True,
        "not_the_reviewed_p3_deviation": True,
    }


def _reference_rule_match(reference: dict | None) -> dict:
    """The source rule's own class, taken from the reference diagnostic.

    A repaired build has no hard break left to point at the rule, so the rule's
    class comes from the reference measurement of the same source row.
    """

    matches = (reference or {}).get("source_rule_registry_matches") or []
    return matches[0] if matches else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--source-pdf", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--reference-diagnostic",
        help=(
            "An earlier diagnostic of the same source form row(s).  Its source "
            "rows are re-measured in --build, so a repaired build proves the row "
            "is delivered intact and not merely free of hard breaks."
        ),
    )
    parser.add_argument(
        "--before-build",
        help=(
            "The build the defect was found in.  The same source rows are "
            "measured there as well, so one artifact carries the before and the "
            "after of the same evidence."
        ),
    )
    args = parser.parse_args(argv)

    build = Path(args.build).resolve()
    source_pdf = Path(args.source_pdf).resolve()
    reference = None
    if args.reference_diagnostic:
        reference = json.loads(
            Path(args.reference_diagnostic).read_text(encoding="utf-8")
        )

    diagnostic = diagnose(build, source_pdf)
    diagnostic["reference_diagnostic"] = (
        str(Path(args.reference_diagnostic)) if args.reference_diagnostic else None
    )
    targets = _targets(diagnostic, reference)
    diagnostic.update(measure(build, source_pdf, targets))
    if args.before_build:
        before_build = Path(args.before_build).resolve()
        diagnostic["before_build"] = before_build.name
        diagnostic["measured_before"] = measure(
            before_build, source_pdf, targets
        )["measured"]
        # The closure artifact has to explain the defect **as it was found**: the
        # build under test is repaired by construction, so its own report no
        # longer carries the break the root cause accounts for.  Read the cause
        # from the build the defect was reported in, and keep both readable.
        diagnostic["root_cause_before"] = _root_cause(
            _generation_report(before_build)
        )
        diagnostic["root_cause"] = diagnostic["root_cause_before"]

    conclusions = []
    rule_match = (
        (diagnostic["source_rule_registry_matches"] or [{}])[0]
        if diagnostic["source_rule_registry_matches"]
        else _reference_rule_match(reference)
    )
    for measured in diagnostic["measured"]:
        same_row = bool(measured["source_rule_shares_the_label_row"])
        delivered_split = not bool(measured["delivered_rule_shares_the_label_row"])
        conclusions.append(
            {
                "generated_paragraph_index": measured["generated_paragraph_index"],
                "selection_basis": measured["selection_basis"],
                "label": measured["label"],
                "source_rule_shares_the_label_row": same_row,
                "source_explicit_break_semantics": (
                    measured["source_row_count"] > 1
                ),
                "delivered_rule_shares_the_label_row": bool(
                    measured["delivered_rule_shares_the_label_row"]
                ),
                "source_blank_class": rule_match.get("transformation_policy"),
                "source_blank_geometry_intent": rule_match.get("geometry_intent"),
                "source_authoritative_slot": rule_match.get(
                    "authoritative_slot_binding"
                ),
                "source_rule_id": rule_match.get("source_rule_id"),
                "source_row_count": measured["source_row_count"],
                "delivered_row_count": measured["delivered_row_count"],
                "rows_added": measured["rows_added"],
                "rule_span_preserved": (
                    measured["rule_x0_error_pt"] is not None
                    and abs(measured["rule_x0_error_pt"]) <= 2.0
                    and abs(measured["rule_x1_error_pt"]) <= 2.0
                ),
                "rule_x0_error_pt": measured["rule_x0_error_pt"],
                "rule_x1_error_pt": measured["rule_x1_error_pt"],
                "verdict": (
                    "UNEXPECTED_HARD_BREAK_IN_ONE_SOURCE_ROW"
                    if same_row and delivered_split
                    else "FIDELITY_PRESERVED"
                ),
            }
        )
    diagnostic["conclusions"] = conclusions
    diagnostic["conclusions_before"] = [
        {
            "label": item["label"],
            "delivered_row_count": item["delivered_row_count"],
            "rows_added": item["rows_added"],
            "delivered_rule_shares_the_label_row": item[
                "delivered_rule_shares_the_label_row"
            ],
            "rule_span_preserved": (
                item["rule_x0_error_pt"] is not None
                and abs(item["rule_x0_error_pt"]) <= 2.0
                and abs(item["rule_x1_error_pt"]) <= 2.0
            ),
            "rule_x0_error_pt": item["rule_x0_error_pt"],
            "rule_x1_error_pt": item["rule_x1_error_pt"],
            "verdict": (
                "FIDELITY_PRESERVED"
                if item["delivered_rule_shares_the_label_row"]
                else "UNEXPECTED_HARD_BREAK_IN_ONE_SOURCE_ROW"
            ),
        }
        for item in diagnostic.get("measured_before", [])
        if item.get("source_rule_shares_the_label_row")
    ]
    diagnostic["verdict"] = (
        "P6_SOURCE_ROW_CONTINUITY_CLOSED"
        if conclusions
        and all(
            item["verdict"] == "FIDELITY_PRESERVED" and item["rule_span_preserved"]
            for item in conclusions
        )
        else "UNEXPECTED_HARD_BREAK_IN_ONE_SOURCE_ROW"
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(diagnostic, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "inline_break_paragraphs": diagnostic["inline_break_paragraph_count"],
                "generated_w_br_total": diagnostic["generated_w_br_total"],
                "verdicts": [item["verdict"] for item in conclusions],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
