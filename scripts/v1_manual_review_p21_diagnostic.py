"""Stage 1 read-only diagnostic: composite-slot underline and source indents.

Two independent measurements, neither of which trusts the emitter's own account:

* the *generated DOCX's* OOXML: every paragraph's ``w:ind`` attributes and every
  run's ``w:u`` value.  A run whose underline is ``w:val="none"`` is an explicit
  removal, so a missing underline found here is an emitter decision and not a
  LibreOffice/Word rendering difference.
* the *source PDF's* own geometry: the visible left edge of each source visual
  row of the same paragraph (measured with the PDF reader, not read back out of
  the pipeline's model), and the horizontal rules the source drew.

The script then classifies each source paragraph's indent with the production
classifier and reports current versus proposed Word geometry for every paragraph
in the delivery, so the blast radius of a generic indent fix is measured before
production is edited.

Nothing here is keyed to a case name, a page number, a rule id or a literal
value.  The composite slot is found through the production marker constant and
the build's own recorded slot presentations.

Usage::

    python scripts/v1_manual_review_p21_diagnostic.py \\
        --build acceptance/workspace/case_001/v1_manual_fidelity_round2 \\
        --source-pdf acceptance/private/<source>.pdf \\
        --out acceptance/reports/v1_generalization/<name>.json
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
from docx.oxml.ns import qn  # noqa: E402

from tender_basic.page_layout import (  # noqa: E402
    LogicalParagraph,
    VALUE_REPLACING_POLICIES,
    build_page_layout,
    visible_box,
)
from tender_basic.source_fill_policy import (  # noqa: E402
    COMPONENT_FACT_VALUE,
    COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER,
    COMPONENT_SOURCE_TEMPLATE_LITERAL,
    SOURCE_FORM_NOT_APPLICABLE_MARKER,
)
from tender_basic.source_paragraph_indent import (  # noqa: E402
    CLASSIFICATION_FIRST_LINE,
    CLASSIFICATION_HANGING,
    CLASSIFICATION_NONE,
    COLUMN_TOLERANCE_PT,
    classify_paragraph_source_indent,
    source_row_origins,
)

SCHEMA = "v1_manual_review_p21_followup_diagnostic/1"

#: A source rule is taken to decorate a slot only when it overlaps the slot's own
#: measured extent by at least this share of the slot span.
SLOT_RULE_OVERLAP_SHARE = 0.5

INHERITED = "SLOT_DECORATION_INHERITED"
DROPPED = "SLOT_DECORATION_DROPPED"
UNAUTHORISED = "RUN_UNDERLINE_WITHOUT_SLOT_AUTHORITY"


def _underline_state(authorised: bool, emitted: bool) -> str:
    """What the delivered artifact says about the slot's decoration.

    The two facts are independent on purpose: an underline that reached the page
    without a rule to own it and a rule whose decoration never reached the page
    are different defects, and a single boolean would conflate them.
    """

    if emitted and authorised:
        return INHERITED
    if emitted:
        return UNAUTHORISED
    if authorised:
        return DROPPED
    return "NO_SLOT_DECORATION_INTENT"


def _twips_to_pt(value) -> float | None:
    if value is None:
        return None
    return round(int(value) / 20.0, 2)


def _paragraph_indent_xml(paragraph) -> dict:
    """``w:ind`` as Word stores it, plus the pt value the reader reports."""

    properties = paragraph._p.find(qn("w:pPr"))
    node = None if properties is None else properties.find(qn("w:ind"))
    raw = {} if node is None else {key.split("}")[-1]: value for key, value in node.attrib.items()}
    formatting = paragraph.paragraph_format
    left = raw.get("left", raw.get("start"))
    first_line = raw.get("firstLine")
    hanging = raw.get("hanging")
    return {
        "raw": raw,
        "left_twips": None if left is None else int(left),
        "left_pt": None if left is None else _twips_to_pt(left),
        "first_line_twips": None if first_line is None else int(first_line),
        "first_line_pt": None if first_line is None else _twips_to_pt(first_line),
        "hanging_twips": None if hanging is None else int(hanging),
        "hanging_pt": None if hanging is None else _twips_to_pt(hanging),
        "reader_left_pt": None if formatting.left_indent is None else round(formatting.left_indent.pt, 2),
        "reader_first_line_pt": (
            None if formatting.first_line_indent is None else round(formatting.first_line_indent.pt, 2)
        ),
    }


def _run_underline(run) -> dict:
    properties = run._r.find(qn("w:rPr"))
    node = None if properties is None else properties.find(qn("w:u"))
    return {
        "text": run.text,
        "underline_attr": None if node is None else node.get(qn("w:val")),
        "underline_element_present": node is not None,
        "reader_underline": run.underline,
    }


def _docx_paragraphs(path: Path) -> list[dict]:
    document = docx.Document(str(path))
    entries = []
    for index, paragraph in enumerate(document.paragraphs):
        entries.append(
            {
                "paragraph_index": index,
                "style": None if paragraph.style is None else paragraph.style.name,
                "text": paragraph.text,
                "indent": _paragraph_indent_xml(paragraph),
                "runs": [_run_underline(run) for run in paragraph.runs],
            }
        )
    return entries


def _source_lines(page) -> list[dict]:
    """Every non-empty source text line on one PDF page, in reading order."""

    lines = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            if text.strip():
                lines.append(
                    {
                        "text": text,
                        "bbox": [round(float(value), 2) for value in line["bbox"]],
                    }
                )
    lines.sort(key=lambda entry: (entry["bbox"][1], entry["bbox"][0]))
    return lines


def _source_rules(page) -> list[dict]:
    from tender_basic.geometry_rule_qa import page_rules

    rules = []
    for rule in page_rules(page, include_underlines=True):
        rules.append(
            {
                "kind": rule.get("kind"),
                "x0": round(float(rule["x0"]), 2),
                "x1": round(float(rule["x1"]), 2),
                "y": round(float(rule["y"]), 2),
                "context": rule.get("context"),
            }
        )
    rules.sort(key=lambda entry: (entry["y"], entry["x0"]))
    return rules


def _layout_by_page(source_pdf: Path, pages: set[int]) -> dict:
    from tender_basic.bid_document_builder import build_repaired_source_model
    from tender_basic.document_parser import parse_document
    from tender_basic.format_extractor import extract_bid_format

    document = parse_document(source_pdf)
    template = extract_bid_format(document)
    model, _qa = build_repaired_source_model(document, template)
    layouts = {}
    for page in model.source_pages:
        if page.page in pages:
            layouts[page.page] = build_page_layout(page)
    return layouts


def _paragraph_source_geometry(layout) -> list[dict]:
    """Per source paragraph: its own visual row origins and its classification."""

    paragraphs = [item for item in layout.elements if isinstance(item, LogicalParagraph)]
    entries = []
    for item in paragraphs:
        origins = source_row_origins(item.source_lines)
        indent = classify_paragraph_source_indent(item, container_paragraphs=paragraphs)
        entries.append(
            {
                "source_text_prefix": item.logical_text[:40],
                "kind": item.kind,
                "alignment": item.alignment_hint,
                "bbox": [round(float(value), 2) for value in item.bbox],
                "container_x0": None if item.container is None else round(float(item.container.container_x0), 2),
                "source_row_origins": [
                    {"x": round(origin, 2), "y": round(y, 2)} for origin, y in origins
                ],
                "source_first_line_x": round(visible_box(item.source_lines[0])[0], 2) if item.source_lines else None,
                "measured_container_body_left_x": indent.body_left_x
                if indent.classification
                in (CLASSIFICATION_FIRST_LINE, CLASSIFICATION_HANGING)
                else None,
                "accepted_model_left_indent_x": round(float(item.left_indent_pt), 2),
                "accepted_model_first_line_indent_pt": round(float(item.first_line_indent_pt), 2),
                "source_indent": indent.as_dict(),
            }
        )
    entries.sort(key=lambda entry: (entry["bbox"][1], entry["bbox"][0]))
    return entries


def _current_word_indent(entry: dict, page_content_x0: float, role: str) -> dict:
    """The indent the *reviewed* delivery carries, in the model's own terms.

    The active builder writes a list item's whole left indent from its first
    source row and never writes a first-line indent for it; every other element
    takes the model's own two values.  Reproducing that rule here is what makes
    the current-versus-proposed comparison a measurement of the delivery rather
    than a restatement of the fix.
    """

    if entry["alignment"] == "center":
        return {"left_pt": 0.0, "first_line_pt": 0.0, "basis": "CENTERED_LINE"}
    if role == "BODY_LIST" and entry["source_first_line_x"] is not None:
        return {
            "left_pt": round(max(0.0, entry["source_first_line_x"] - page_content_x0), 2),
            "first_line_pt": 0.0,
            "basis": "LIST_FIRST_SOURCE_ROW_AS_WHOLE_LEFT",
        }
    return {
        "left_pt": round(max(0.0, entry["accepted_model_left_indent_x"] - page_content_x0), 2),
        "first_line_pt": entry["accepted_model_first_line_indent_pt"],
        "basis": "MODEL_LEFT_AND_FIRST_LINE",
    }


def _proposed_word_indent(entry: dict, page_content_x0: float, role: str) -> dict:
    if entry["alignment"] == "center":
        return {"left_pt": 0.0, "first_line_pt": 0.0, "basis": "CENTERED_LINE"}
    indent = entry["source_indent"]
    if indent["classification"] in (CLASSIFICATION_FIRST_LINE, CLASSIFICATION_HANGING):
        return {
            "left_pt": round(max(0.0, indent["body_left_x"] - page_content_x0), 2),
            "first_line_pt": indent["word_first_line_indent_pt"],
            "basis": "SOURCE_INDENT_CLASSIFICATION",
        }
    current = _current_word_indent(entry, page_content_x0, role)
    return {**current, "basis": "ACCEPTED_" + current["basis"]}


def _role_of(entry: dict) -> str:
    text = entry["source_text_prefix"]
    if entry["kind"] == "List":
        return "BODY_LIST"
    del text
    return "FLOW_BODY"


def build_diagnostic(build_dir: Path, source_pdf: Path) -> dict:
    report = json.loads((build_dir / "generation_report.json").read_text(encoding="utf-8"))
    manifest = json.loads((build_dir / "build_manifest.json").read_text(encoding="utf-8"))
    paragraphs = _docx_paragraphs(Path(manifest["generated"]["docx"]))

    presentations = report.get("slot_value_presentations", {})
    records = presentations.get("records", [])
    composite_records = [
        record
        for record in records
        if any(
            component["kind"] == COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER
            for component in record.get("components", ())
        )
    ]
    source_pages = sorted(
        {
            int(record["source_page"])
            for record in composite_records
            if record.get("source_page") is not None
        }
    )
    # The blast radius of a generic indent fix is the whole delivery, not the
    # page the defect was reported on: every source page the builder emits is
    # measured, so a change that reaches a page nobody asked about is visible.
    emitted_pages = sorted({int(entry["page"]) for entry in report.get("section_geometry", [])})
    layouts = _layout_by_page(source_pdf, set(emitted_pages) or set(source_pages))
    source_doc = pymupdf.open(str(source_pdf))
    frames = {int(entry["page"]): entry for entry in report.get("section_geometry", [])}

    # ---- DEFECT A: the composite slot's own decoration -----------------------
    composite_paragraphs = []
    for record in composite_records:
        value = str(record["value"])
        marker_count = sum(
            1
            for component in record.get("components", ())
            if component["kind"] == COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER
        )
        separator_components = [
            component
            for component in record.get("components", ())
            if component["kind"] == COMPONENT_SOURCE_TEMPLATE_LITERAL
        ]
        fact_components = [
            component
            for component in record.get("components", ())
            if component["kind"] == COMPONENT_FACT_VALUE
        ]
        matches = [entry for entry in paragraphs if value and value in entry["text"]]
        page = int(record["source_page"])
        source_page = source_doc[page - 1]
        source_lines = _source_lines(source_page)
        rules = _source_rules(source_page)
        registry = [
            entry
            for entry in report.get("source_rule_registry", [])
            if int(entry.get("source_page", -1)) == page
        ]
        bound_rules = [
            entry
            for entry in registry
            if entry.get("authoritative_slot_id") == record["slot_id"]
        ]
        # The emitter's own emission-side authorisation: a rule bound to this
        # slot whose placeholder a resolved value replaces is the rule that owns
        # the slot's decoration, which is what lets the value that occupies the
        # slot inherit it.  This is derived from the annotated registry - the same
        # binding and policy the renderer merges into the report - so the
        # diagnostic evaluates the delivered artifact's own authority rather than
        # a second, independent guess at it.
        bound_decoration_rule_ids = sorted(
            str(entry.get("source_rule_id"))
            for entry in bound_rules
            if str(entry.get("transformation_policy")) in VALUE_REPLACING_POLICIES
            and entry.get("resolved_fact_fields")
        )
        value_is_underlined = any(
            run["reader_underline"] is True
            for entry in matches
            for run in entry["runs"]
            if run["text"] and run["text"] in value
        )
        composite_paragraphs.append(
            {
                "slot_id": record["slot_id"],
                "source_page": page,
                "value": value,
                "method": record.get("method"),
                "components": record.get("components"),
                "component_counts": {
                    "fact_value": len(fact_components),
                    "source_template_literal": len(separator_components),
                    "source_form_not_applicable_marker": marker_count,
                },
                "generated_paragraph_index": record.get("generated_paragraph_index"),
                "generated_paragraph_indexes_found": [entry["paragraph_index"] for entry in matches],
                "generated_paragraphs": [
                    {
                        "paragraph_index": entry["paragraph_index"],
                        "style": entry["style"],
                        "text": entry["text"],
                        "indent": entry["indent"],
                        "runs": entry["runs"],
                        "value_run_underlines": [
                            run["underline_attr"]
                            for run in entry["runs"]
                            if run["text"] and run["text"] in value
                        ],
                        "value_is_underlined": any(
                            run["reader_underline"] is True
                            for run in entry["runs"]
                            if run["text"] and run["text"] in value
                        ),
                        "prose_underlined_outside_value": [
                            run["text"]
                            for run in entry["runs"]
                            if run["text"] and run["text"] not in value and run["reader_underline"] is True
                        ],
                    }
                    for entry in matches
                ],
                "source_text_lines": source_lines,
                "source_rules": rules,
                "registry_rules_bound_to_slot": bound_rules,
                "registry_rules_on_page": registry,
                "underline_authority": {
                    "value_replacing_policies": sorted(VALUE_REPLACING_POLICIES),
                    "bound_decoration_rule_ids": bound_decoration_rule_ids,
                    "emission_authorised": bool(bound_decoration_rule_ids),
                    "emitted": value_is_underlined,
                    "state": _underline_state(
                        bool(bound_decoration_rule_ids), value_is_underlined
                    ),
                    "provenance": [
                        {
                            "component": str(component.get("kind")),
                            "text": str(component.get("text")),
                            "field": component.get("field"),
                            "inherited": bool(bound_decoration_rule_ids),
                        }
                        for component in record.get("components") or ()
                    ],
                    "suffix_prose_underline": any(
                        run["reader_underline"] is True
                        for entry in matches
                        for run in entry["runs"]
                        if run["text"] and run["text"] not in value
                    ),
                },
            }
        )

    defect_a = {
        "marker": SOURCE_FORM_NOT_APPLICABLE_MARKER,
        "marker_is_a_fact": presentations.get("marker_is_a_fact"),
        "marker_creates_a_fact_candidate": presentations.get("marker_creates_a_fact_candidate"),
        "composite_slot_count": len(composite_records),
        "slots": composite_paragraphs,
    }

    # ---- DEFECT B: source paragraph indent classification -------------------
    indent_rows = []
    changes = []
    for page_number in sorted(layouts):
        layout = layouts[page_number]
        frame = frames.get(page_number)
        page_content_x0 = float(frame["left_margin"]) if frame else None
        role_by_text = {}
        for record in report.get("paragraph_layout_records", []):
            box = record.get("text_bbox")
            if int(record.get("source_page", -1)) != page_number or not box:
                continue
            role_by_text[(round(float(box[1]), 2), round(float(box[0]), 2))] = record
        for entry in _paragraph_source_geometry(layout):
            key = (round(entry["bbox"][1], 2), round(entry["bbox"][0], 2))
            record = role_by_text.get(key)
            role = _role_of(entry) if record is None else str(record.get("role") or _role_of(entry))
            role = "BODY_LIST" if entry["kind"] == "List" else role
            row = {**entry, "source_page": page_number, "role": role}
            if page_content_x0 is not None:
                row["page_content_x0"] = page_content_x0
                row["current_word_indent"] = _current_word_indent(entry, page_content_x0, role)
                row["proposed_word_indent"] = _proposed_word_indent(entry, page_content_x0, role)
                row["indent_changes"] = (
                    row["current_word_indent"]["left_pt"] != row["proposed_word_indent"]["left_pt"]
                    or row["current_word_indent"]["first_line_pt"] != row["proposed_word_indent"]["first_line_pt"]
                )
                if row["indent_changes"]:
                    changes.append(
                        {
                            "source_page": page_number,
                            "source_text_prefix": entry["source_text_prefix"],
                            "classification": entry["source_indent"]["classification"],
                            "current": row["current_word_indent"],
                            "proposed": row["proposed_word_indent"],
                        }
                    )
            indent_rows.append(row)

    defect_b = {
        "classification_tolerance_pt": COLUMN_TOLERANCE_PT,
        "paragraphs": indent_rows,
        "changed_paragraph_count": len(changes),
        "changed_paragraphs": changes,
        "target_rows": [
            row
            for row in indent_rows
            if row["source_page"] in {int(record["source_page"]) for record in composite_records}
        ],
    }

    classes = {}
    for row in indent_rows:
        key = row["source_indent"]["classification"]
        classes[key] = classes.get(key, 0) + 1

    return {
        "schema": SCHEMA,
        "build_dir": str(build_dir),
        "generated_docx": str(manifest["generated"]["docx"]),
        "generated_docx_sha256": manifest["generated"]["docx_sha256"],
        "source_pdf": str(source_pdf),
        "defect_a_composite_slot_underline": defect_a,
        "defect_b_paragraph_indent": defect_b,
        "classification_histogram": classes,
        "conclusions": {
            "composite_value_underline_state": (
                DROPPED
                if any(
                    not paragraph["value_is_underlined"]
                    for slot in composite_paragraphs
                    for paragraph in slot["generated_paragraphs"]
                )
                else INHERITED
            ),
            "composite_registry_binding_relation_types": sorted(
                {
                    str(rule.get("relation_type"))
                    for slot in composite_paragraphs
                    for rule in slot["registry_rules_bound_to_slot"]
                }
            ),
            "composite_registry_binding_policies": sorted(
                {
                    str(rule.get("transformation_policy"))
                    for slot in composite_paragraphs
                    for rule in slot["registry_rules_bound_to_slot"]
                }
            ),
            "composite_bound_decoration_rule_ids": sorted(
                {
                    rule_id
                    for slot in composite_paragraphs
                    for rule_id in slot["underline_authority"]["bound_decoration_rule_ids"]
                }
            ),
            "composite_underline_states": sorted(
                {str(slot["underline_authority"]["state"]) for slot in composite_paragraphs}
            ),
            "source_indent_class_histogram": classes,
            "paragraphs_whose_word_indent_would_change": len(changes),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--source-pdf", required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    payload = build_diagnostic(Path(args.build).resolve(), Path(args.source_pdf).resolve())
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print("wrote", out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
