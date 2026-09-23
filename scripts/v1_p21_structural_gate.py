"""P21 structural gate: the composite slot's underline and the source's indents.

Two structural contracts are gated here, both measured from the delivered
artifact rather than from the emitter's own bookkeeping:

``COMPOSITE_SLOT_UNDERLINE``
    A source form slot whose source form has no component for one of its fields
    is delivered as one composite value: the resolved fact, the source's own
    separator and the source form's not-applicable marker.  All three occupy the
    *same* source slot, so the underline the source drew on that slot belongs to
    every one of them - and to nothing outside the slot.  The gate reads the
    OOXML ``w:u`` of the run that actually carries the composite, and the rule
    the generated PDF actually paints beneath it, so a decoration the emitter
    believes it wrote but that never reached the page is caught.

``SOURCE_PARAGRAPH_INDENT``
    Every delivered paragraph's ``w:ind/@w:left`` is the body boundary its own
    source rows return to and ``w:ind/@w:firstLine`` (or ``w:hanging``) is the
    signed offset of its first row from that boundary.  A paragraph whose source
    first row is *right* of its wrapped rows is a first-line indent and must not
    be delivered as a whole-paragraph left indent; a centred line is positioned
    from the container's centre and claims neither.

Nothing here is keyed to a case name, a page number, a rule id or a resolved
value: the composite slot is found from the presentation provenance, and the
page under audit is derived from the build's own record of where that slot came
from.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import docx  # noqa: E402
import pymupdf  # noqa: E402

from v1_manual_review_p21_diagnostic import (  # noqa: E402
    _docx_paragraphs,
    _paragraph_indent_xml,
    _run_underline,
)

SCHEMA = "v1_p21_structural_gate/1"

#: ``w:u`` values that paint a visible line.  ``none`` and a missing element both
#: mean the run carries no decoration.
VISIBLE_UNDERLINES = frozenset(
    {"single", "words", "double", "thick", "dotted", "dottedheavy", "dash",
     "dashedheavy", "dotdash", "dotdashheavy", "dotdotdash", "dotdotdashheavy",
     "wave", "wavyheavy", "wavydouble"}
)

FIRST_LINE = "FIRST_LINE_INDENT"
HANGING = "HANGING_INDENT"
NO_SPECIAL = "NO_SPECIAL_FIRST_LINE_INDENT"

#: A delivered first line may sit this far from its source first row's origin.
ORIGIN_TOLERANCE_PT = 2.0
#: A painted rule may sit this far from the text it decorates.
RULE_Y_TOLERANCE_PT = 6.0


def _visible_underline(run: dict) -> bool:
    value = run.get("underline_attr")
    if value is None:
        return bool(run.get("underline_element_present")) and bool(run.get("reader_underline"))
    return str(value).lower() in VISIBLE_UNDERLINES


def _report(build_dir: Path) -> dict:
    return json.loads((build_dir / "generation_report.json").read_text(encoding="utf-8"))


def _facts(build_dir: Path) -> dict:
    path = build_dir / "project_facts.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _section_left_margin_pt(path: Path) -> float:
    document = docx.Document(str(path))
    section = document.sections[-1]
    return float(section.left_margin.pt or 0.0)


def _composite_records(report: dict) -> list[dict]:
    """Every composed slot value that carries the source form's marker component.

    The composite is identified from its own presentation provenance - a
    non-applicable marker component next to a resolved fact component - so no
    slot id, page number or literal value is the authority.
    """

    presentations = report.get("slot_value_presentations") or {}
    composed = []
    for record in presentations.get("records") or []:
        components = list(record.get("components") or ())
        kinds = [str(component.get("kind")) for component in components]
        if "SOURCE_FORM_NOT_APPLICABLE_MARKER" not in kinds:
            continue
        if "FACT_VALUE" not in kinds:
            continue
        composed.append(record)
    return composed


def _all_slot_presentations(report: dict) -> list[dict]:
    """Every recorded slot value, whatever it resolved to."""

    presentations = report.get("slot_value_presentations") or {}
    return list(presentations.get("records") or [])


def _field_status(facts: dict, field: str) -> dict:
    fields = facts.get("fields") or {}
    entry = fields.get(field)
    return entry if isinstance(entry, dict) else {}


def _value_rendered_lines(page, needle: str) -> list[dict]:
    """The rendered line segments a value occupies, one entry per visual line.

    A resolved value can wrap, and each wrapped line carries its own painted
    stretch of the decoration, so the audit has to look under every line the
    value occupies - not under one bounding box that spans several.
    """

    charlist = []
    for block in page.get_text("rawdict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    if char["c"].strip():
                        charlist.append(
                            {
                                "c": char["c"],
                                "x0": float(char["bbox"][0]),
                                "x1": float(char["bbox"][2]),
                                "baseline": round(float(char["bbox"][3]), 0),
                            }
                        )
    sequence = [item["c"] for item in charlist]
    target = [character for character in needle if not character.isspace()]
    if not target:
        return []
    lines: dict[float, dict] = {}
    for index in range(len(sequence) - len(target) + 1):
        if sequence[index : index + len(target)] != target:
            continue
        for item in charlist[index : index + len(target)]:
            key = item["baseline"]
            entry = lines.setdefault(
                key, {"x0": item["x0"], "x1": item["x1"], "baseline": key}
            )
            entry["x0"] = min(entry["x0"], item["x0"])
            entry["x1"] = max(entry["x1"], item["x1"])
        break
    return [lines[key] for key in sorted(lines)]


def _painted_rules(page) -> list[dict]:
    from tender_basic.geometry_rule_qa import page_rules

    return [
        {
            "kind": rule.get("kind"),
            "x0": float(rule["x0"]),
            "x1": float(rule["x1"]),
            "y": float(rule["y"]),
        }
        for rule in page_rules(page, include_underlines=True)
    ]


def _painted_rule_under(page, needle: str) -> list[dict]:
    """Every painted rule that decorates a rendered line of ``needle``."""

    segments = _value_rendered_lines(page, needle)
    if not segments:
        return []
    rules = _painted_rules(page)
    hits = []
    for segment in segments:
        width = max(0.5, segment["x1"] - segment["x0"])
        best = None
        for rule in rules:
            if rule["x1"] <= segment["x0"] or rule["x0"] >= segment["x1"]:
                continue
            if not (
                segment["baseline"] - 2.0
                <= rule["y"]
                <= segment["baseline"] + RULE_Y_TOLERANCE_PT
            ):
                continue
            overlap = min(rule["x1"], segment["x1"]) - max(rule["x0"], segment["x0"])
            if overlap / width < 0.5:
                continue
            candidate = {
                "text_x0": round(segment["x0"], 2),
                "text_x1": round(segment["x1"], 2),
                "rule_x0": round(rule["x0"], 2),
                "rule_x1": round(rule["x1"], 2),
                "rule_y": round(rule["y"], 2),
                "rule_kind": rule["kind"],
                "overlap_share": round(overlap / width, 3),
            }
            if best is None or candidate["overlap_share"] > best["overlap_share"]:
                best = candidate
        hits.append({"segment": segment, "rule": best})
    return hits


def _generated_page_for_report(text: str, pdf: Path) -> tuple[int, object]:
    """The first generated page whose text contains ``text``."""

    document = pymupdf.open(pdf)
    try:
        for number in range(document.page_count):
            page = document[number]
            haystack = "".join(page.get_text().split())
            if "".join(text.split()) in haystack:
                return number + 1, page
    finally:
        pass
    return 0, None


def evaluate(build_dir: Path, source_pdf: Path) -> dict:
    build_dir = Path(build_dir)
    report = _report(build_dir)
    facts = _facts(build_dir)
    docx_path = build_dir / "基础投标文件.docx"
    pdf_path = build_dir / "基础投标文件.pdf"
    paragraphs = _docx_paragraphs(docx_path)
    page_content_x0 = _section_left_margin_pt(docx_path)
    failures: list[str] = []
    measurements: dict = {}

    # ---------------------------------------------------------------- A + C --
    composites = _composite_records(report)
    if not composites:
        failures.append("composite_slot_present")
    # Every value the build itself records as a source slot that inherited the
    # source's own underline.  A run carrying one of these is another FORM FIELD
    # the source decorated, not prose: the source may print two placeholders side
    # by side under one rule, and the second one is not the first one's sentence.
    decorated_form_field_values = {
        str(record.get("value"))
        for record in _all_slot_presentations(report)
        if record.get("source_slot_underline_inherited")
    }
    slot_records = []
    for record in composites:
        index = record.get("generated_paragraph_index")
        value = str(record.get("value") or "")
        components = list(record.get("components") or ())
        marker_components = [
            component
            for component in components
            if component.get("kind") == "SOURCE_FORM_NOT_APPLICABLE_MARKER"
        ]
        facts_components = [
            component for component in components if component.get("kind") == "FACT_VALUE"
        ]
        literals = [
            component
            for component in components
            if component.get("kind") == "SOURCE_TEMPLATE_LITERAL"
        ]
        entry = {
            "slot_id": record.get("slot_id"),
            "source_page": record.get("source_page"),
            "generated_paragraph_index": index,
            "value": value,
            "value_length": len(value),
            "fact_components": record.get("fact_components"),
            "marker_components": record.get("marker_components"),
            "source_slot_underline_inherited": record.get("source_slot_underline_inherited"),
        }
        target = (
            paragraphs[index]
            if isinstance(index, int) and 0 <= index < len(paragraphs)
            else None
        )
        entry["generated_paragraph_resolved"] = target is not None
        if target is None:
            failures.append("composite_paragraph_located")
            slot_records.append(entry)
            continue

        runs = target["runs"]
        carrier = next((run for run in runs if run["text"] == value), None)
        if carrier is None:
            carrier = next(
                (run for run in runs if value and run["text"] and run["text"] in value),
                None,
            )
        entry["carrier_run_found"] = carrier is not None
        entry["carrier_run_underline"] = (
            None if carrier is None else _visible_underline(carrier)
        )
        entry["carrier_run_underline_attr"] = (
            None if carrier is None else carrier.get("underline_attr")
        )
        entry["paragraph_indent"] = target["indent"]
        if carrier is None or not _visible_underline(carrier):
            failures.append("composite_value_run_is_underlined")

        # The prose on either side of the slot is written by its own runs and
        # keeps only its own decoration: the underline is the slot's, not the
        # sentence's.
        position = runs.index(carrier) if carrier in runs else None
        neighbours = []
        if position is not None:
            for offset in (-1, 1):
                neighbour = position + offset
                if 0 <= neighbour < len(runs):
                    neighbours.append(
                        {
                            "offset": offset,
                            "text": runs[neighbour]["text"][:24],
                            "full_text": runs[neighbour]["text"],
                            "underline": _visible_underline(runs[neighbour]),
                        }
                    )
        entry["slot_neighbour_runs"] = neighbours
        prose_neighbours = [
            item
            for item in neighbours
            if item["full_text"].strip()
            and item["underline"]
            and item["full_text"] not in decorated_form_field_values
        ]
        entry["undecorated_form_field_neighbours"] = [
            item
            for item in neighbours
            if item["full_text"] in decorated_form_field_values
        ]
        if prose_neighbours:
            failures.append("prose_outside_the_slot_is_not_underlined")

        # ------------------------------------------------------------- F ----
        marker_texts = {str(component.get("text")) for component in marker_components}
        literal_texts = {str(component.get("text")) for component in literals}
        entry["marker_texts"] = sorted(marker_texts)
        entry["marker_occurrences"] = {
            text: value.count(text) for text in marker_texts
        }
        entry["separator_occurrences"] = {
            text: value.count(text) for text in literal_texts
        }
        entry["fact_occurrences"] = {
            str(component.get("field")): value.count(str(component.get("text")))
            for component in facts_components
        }
        if not marker_texts or any(count != 1 for count in entry["marker_occurrences"].values()):
            failures.append("marker_appears_exactly_once")
        if any(count != 1 for count in entry["separator_occurrences"].values()):
            failures.append("source_separator_appears_exactly_once")
        if any(count != 1 for count in entry["fact_occurrences"].values()):
            failures.append("resolved_fact_appears_exactly_once")
        if (report.get("slot_value_presentations") or {}).get("marker_is_a_fact") is not False:
            failures.append("marker_is_not_a_fact")
        if (
            report.get("slot_value_presentations") or {}
        ).get("marker_creates_a_fact_candidate") is not False:
            failures.append("marker_creates_no_fact_candidate")
        marker_field_status = {
            field: _field_status(facts, str(field)).get("status")
            for field in record.get("marker_components") or ()
        }
        entry["marker_field_status"] = marker_field_status
        if any(str(status) != "NOT_FOUND" for status in marker_field_status.values()):
            failures.append("marker_field_keeps_its_own_status")

        # ------------------------------------------------------------- B ----
        bound = [
            item
            for item in report.get("source_rule_registry") or []
            if item.get("authoritative_slot_id") == record.get("slot_id")
        ]
        entry["bound_rules"] = [
            {
                "source_rule_id": item.get("source_rule_id"),
                "relation_type": item.get("relation_type"),
                "transformation_policy": item.get("transformation_policy"),
                "geometry_intent": item.get("geometry_intent"),
                "resolved_fact_fields": item.get("resolved_fact_fields"),
            }
            for item in bound
        ]
        # Exactly one logical source rule accounts for the slot, and it is a rule
        # whose placeholder a resolved value replaces - otherwise there is no
        # replacement value for the decoration to belong to.
        if len(bound) != 1:
            failures.append("composite_slot_rule_accounted_exactly_once")
        elif str(bound[0].get("transformation_policy")) not in {
            "PLACEHOLDER_REPLACED_BY_VALUE",
            "RESOLVED_VALUE_IN_FIXED_SLOT",
        }:
            failures.append("composite_slot_rule_replaces_its_placeholder")
        elif not bound[0].get("resolved_fact_fields"):
            failures.append("composite_slot_rule_carries_a_resolved_value")

        # ------------------------------------------------------------- D ----
        if pdf_path.exists():
            page_number, page = _generated_page_for_report(value, pdf_path)
            entry["generated_page"] = page_number
            if page is None:
                failures.append("composite_value_rendered")
            else:
                painted = _painted_rule_under(page, value)
                entry["rendered_rules_under_value"] = painted
                if not painted or any(item["rule"] is None for item in painted):
                    failures.append("composite_value_rendered_underline_present")
        slot_records.append(entry)

    measurements["composite_slots"] = slot_records

    # ------------------------------------------------------------- G/H/I/J --
    # Which paragraphs carry the generic indent contract: a paragraph whose own
    # source rows decide its Word indent.  Three populations are deliberately not
    # governed by it, and each exemption is evidence-backed rather than a silent
    # skip - a form row's geometry is owned by the source form line architecture,
    # a centred line is positioned from the container's centre, and a paragraph
    # whose origin an anchored source value has moved declares its own anchor
    # mechanism in the build's record.
    anchored_origins = {
        record.get("paragraph_index"): record
        for record in report.get("source_anchored_value_runs") or []
        if isinstance(record.get("paragraph_index"), int)
    }
    classified = [
        record
        for record in report.get("logical_paragraph_records") or []
        if record.get("source_indent") is not None
    ]
    measurements["classified_paragraph_count"] = len(classified)
    if not classified:
        failures.append("paragraph_indents_are_classified")
    histogram: dict = {}
    indent_rows = []
    exempt_rows = []
    for record in classified:
        indent = record["source_indent"]
        classification = str(indent.get("classification"))
        histogram[classification] = histogram.get(classification, 0) + 1
        left = float(record.get("left_indent_pt") or 0.0)
        first = float(record.get("first_line_indent_pt") or 0.0)
        row = {
            "paragraph_index": record.get("paragraph_index"),
            "source_page": record.get("source_page"),
            "kind": record.get("kind"),
            "alignment": record.get("alignment"),
            "classification": classification,
            "body_left_x": indent.get("body_left_x"),
            "first_line_x": indent.get("first_line_x"),
            "continuation_x": indent.get("continuation_x"),
            "measured_continuation": indent.get("measured_continuation"),
            "evidence": indent.get("evidence"),
            "word_left_pt": round(left, 2),
            "word_first_line_pt": round(first, 2),
            "source_first_row_x": record.get("source_first_row_x"),
            "generated_first_line_x": record.get("generated_first_line_x"),
            "x_error_pt": record.get("x_error_pt"),
        }
        index = record.get("paragraph_index")
        exempt = None
        if str(record.get("alignment") or "") == "center":
            exempt = "CENTRED_LINE_POSITIONED_FROM_THE_CONTAINER_CENTRE"
        elif str(record.get("kind") or "") == "FormRow":
            exempt = "SOURCE_FORM_LINE_GEOMETRY_OWNED_BY_THE_FORM_ARCHITECTURE"
        elif index in anchored_origins:
            anchor = anchored_origins[index]
            mechanism = str(anchor.get("anchor_mechanism") or "")
            if mechanism not in (
                "LINE_ORIGIN_MOVED_TO_SOURCE_ANCHOR",
                "SOURCE_POSITIONED_ANCHOR_TAB",
                "ALREADY_AT_ANCHOR",
            ):
                failures.append("anchored_paragraph_declares_its_anchor_mechanism")
            exempt = "PARAGRAPH_ORIGIN_MOVED_BY_AN_ANCHORED_SOURCE_VALUE"
            row["anchor_mechanism"] = mechanism
        if exempt is not None:
            row["exempt_reason"] = exempt
            exempt_rows.append(row)
            indent_rows.append(row)
            continue
        row["expected_left_pt"] = round(
            float(indent.get("body_left_x") or 0.0) - page_content_x0, 2
        )
        row["expected_first_line_pt"] = round(
            float(indent.get("word_first_line_indent_pt") or 0.0), 2
        )
        indent_rows.append(row)
        if abs(left - row["expected_left_pt"]) > 0.5:
            failures.append("word_left_indent_matches_the_source_body_boundary")
        if abs(first - row["expected_first_line_pt"]) > 0.5:
            failures.append("word_first_line_indent_matches_the_source_offset")
        if classification == NO_SPECIAL and abs(first) > 0.5:
            failures.append("no_special_indent_claims_no_first_line_offset")
        if classification == HANGING and first >= -0.5:
            failures.append("hanging_indent_is_negative")
        if classification == FIRST_LINE and first <= 0.5:
            failures.append("first_line_indent_is_positive")
        # A first-line indent and a hanging indent are opposite deliveries, and
        # the OOXML says which one was written.
        if classification == FIRST_LINE and _docx_hanging_twips(paragraphs, row):
            failures.append("first_line_indent_is_not_a_hanging_indent")
        # The delivered first line lands on the source's own first row origin.
        if row["source_first_row_x"] is not None and row["generated_first_line_x"] is not None:
            if (
                abs(float(row["source_first_row_x"]) - float(row["generated_first_line_x"]))
                > ORIGIN_TOLERANCE_PT
            ):
                failures.append("delivered_first_line_lands_on_the_source_first_row")
        # The paragraph's own rows must be able to show the classification: a
        # paragraph with no second column may only claim a first-line offset from
        # a measured container boundary.
        if classification in (FIRST_LINE, HANGING) and not indent.get("measured_continuation"):
            evidence = str(indent.get("evidence") or "")
            if "container" not in evidence and "wrapped rows" not in evidence:
                failures.append("indent_classification_has_source_evidence")
    measurements["classification_histogram"] = histogram
    measurements["paragraph_indents"] = indent_rows
    measurements["exempt_paragraph_count"] = len(exempt_rows)
    measurements["exempt_paragraph_reasons"] = sorted(
        {str(row["exempt_reason"]) for row in exempt_rows}
    )
    # Paragraphs outside the contract are named rather than silently dropped, so
    # the audit's coverage is visible: a source form row's geometry belongs to the
    # source form line architecture, and the rest are paragraphs that carry no
    # source text rows to classify at all.
    measurements["unclassified_paragraphs"] = [
        {
            "paragraph_index": record.get("paragraph_index"),
            "source_page": record.get("source_page"),
            "kind": record.get("kind"),
            "source_lines": record.get("source_lines"),
            "reason": (
                "SOURCE_FORM_LINE_GEOMETRY_OWNED_BY_THE_FORM_ARCHITECTURE"
                if str(record.get("kind") or "") == "FormRow"
                else "NO_SOURCE_TEXT_ROWS_TO_CLASSIFY"
            ),
        }
        for record in report.get("logical_paragraph_records") or []
        if record.get("source_indent") is None
    ]

    # Every paragraph on the composite slot's own source page is classified on
    # its own rows, never through a page- or style-wide assumption.
    pages = sorted({int(item["source_page"]) for item in slot_records if item.get("source_page")})
    page_rows = [row for row in indent_rows if row.get("source_page") in pages]
    measurements["audited_source_pages"] = pages
    measurements["audited_source_page_paragraphs"] = page_rows
    for page in pages:
        on_page = [
            record
            for record in report.get("logical_paragraph_records") or []
            if record.get("source_page") == page
            and record.get("source_lines")
            and str(record.get("kind") or "") != "FormRow"
        ]
        if not on_page:
            failures.append("audited_source_page_has_paragraphs")
        unclassified = [
            record.get("paragraph_index")
            for record in on_page
            if record.get("source_indent") is None
        ]
        if unclassified:
            failures.append("every_paragraph_on_the_page_is_classified")
        # Every body boundary a delivered paragraph claims was actually used by
        # some source row on that page.
        page_origins = set()
        for record in on_page:
            for origin in record.get("source_row_origins") or ():
                page_origins.add(round(float(origin), 2))
        for record in on_page:
            indent = record.get("source_indent")
            if not indent:
                continue
            body = round(float(indent.get("body_left_x") or 0.0), 2)
            if page_origins and body not in page_origins:
                failures.append("body_boundary_is_a_source_row_origin")

    return {
        "schema": SCHEMA,
        "gate": "v1_p21_structural",
        "build_dir": str(build_dir),
        "source_pdf": str(source_pdf),
        "docx": str(docx_path),
        "pdf": str(pdf_path),
        "status": "PASS" if not failures else "FAIL",
        "failed_checks": sorted(set(failures)),
        "measurements": measurements,
        "note": (
            "COMPOSITE_SLOT_UNDERLINE and SOURCE_PARAGRAPH_INDENT are structural "
            "contracts measured from the delivered DOCX, the generated PDF and the "
            "source's own row geometry"
        ),
    }


def _docx_hanging_twips(paragraphs: list[dict], row: dict):
    """The ``w:hanging`` the delivered paragraph actually carries, if any."""

    index = row.get("paragraph_index")
    if not isinstance(index, int) or not 0 <= index < len(paragraphs):
        return None
    return (paragraphs[index].get("indent") or {}).get("hanging_twips")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    report = evaluate(args.build, args.source_pdf)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "p21 structural gate: status=%s classified=%s composite_slots=%s failed=%s"
        % (
            report["status"],
            report["measurements"]["classified_paragraph_count"],
            len(report["measurements"]["composite_slots"]),
            report["failed_checks"],
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
