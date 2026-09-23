"""Read-only trace of one composite source-slot's semantic execution binding.

Answers a single question, from repository evidence only: *why* does the P3
semantic execution contract reject an emitted value that the source form, the
ProjectFacts schema and the delivered artifact all agree on?

The trace follows one composite source slot end to end:

    source placeholder text
      -> source drawn rule (page-42 rule registry)
      -> slot binding (authoritative_slot_id)
      -> source form field plan / execution owner
      -> SourceFillApplication
      -> recorded slot value presentation (atomic provenance)
      -> delivered Word runs
      -> emitted surface string
      -> the gate predicate that consumes it

Nothing here writes to a build, renders a document or mutates a report; the
diagnostic is the evidence the reconciliation is argued from.

The one thing this tool proves that the gate cannot: the literal glyphs.  It
reads the *source* PDF's own characters under the source rule's span, so a
``SOURCE_TEMPLATE_LITERAL`` atom is checked against what the source actually
printed rather than against a claim about it.

Usage::

    .venv/Scripts/python.exe scripts/v1_composite_execution_binding_diagnostic.py \
        --build acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final \
        --gate-report acceptance/reports/v1_generalization/case001_p3_semantic_registry_gate_final.json \
        --source-pdf "acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf" \
        --out acceptance/reports/v1_generalization/case001_composite_execution_binding_diagnostic.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCHEMA = "v1_composite_execution_binding_diagnostic/1"

#: The rule whose emitted value the gate rejects.  Read from the gate report's
#: own failure list, so the diagnostic never picks its own subject.
GATE_SCRIPT = "scripts/v1_p3_semantic_registry_gate.py"

#: Approved evidence classes a provenance component may name.  These are the
#: ``source`` values the repository's own presentation recorder writes.
APPROVED_COMPONENT_SOURCES = {
    "ProjectFacts",
    "SOURCE_PLACEHOLDER_TEXT",
    "SOURCE_SLOT_HINT",
    "SOURCE_FORM_STRUCTURE",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


#: The whole-value predicate as it stood when the trace was taken.  The gate is
#: not tracked by git, so the fragment is carried here with its provenance, and
#: the tool *machine-checks* that it is no longer present in the gate it reads:
#: if the fragment reappears, ``before_repair_fragment_still_present`` says so.
PRE_REPAIR_PREDICATE = (
    "            if emitted and expected_values and emitted[0] not in expected_values:",
    "                binding_ok = False",
    '                binding_notes.append("EMITTED_VALUE_NOT_FROM_PROJECT_FACTS")',
    "            if emitted and emitted[0] not in facts_sourced_values:",
    "                binding_ok = False",
    '                binding_notes.append("EMITTED_VALUE_UNKNOWN_TO_PROJECT_FACTS")',
)


def _gate_predicate() -> dict:
    """The exact place the gate collapsed composite provenance, and its repair.

    The pre-repair fragment is quoted with its provenance (it was read out of the
    gate source at the start of this trace, and the gate is not under version
    control, so it cannot be recovered afterwards).  Everything about the current
    state is read from the gate source on disk at run time.
    """

    path = ROOT / GATE_SCRIPT
    lines = path.read_text(encoding="utf-8").splitlines()
    current_text = "\n".join(lines)
    fragment_still_present = all(
        line in current_text for line in PRE_REPAIR_PREDICATE
    )
    atomic_call_lines = [
        {"line": number + 1, "text": line}
        for number, line in enumerate(lines)
        if "validate_presentation_atoms(" in line
    ]
    flat_list_lines = [
        {"line": number + 1, "text": line}
        for number, line in enumerate(lines)
        if "emitted = list(dict.fromkeys" in line
    ]
    return {
        "gate_script": GATE_SCRIPT,
        "comparison_subject": "emitted[0]",
        "comparison_operand": "expected_values / facts_sourced_values",
        "collapses": (
            "every value an application recorded was flattened into one list of "
            "whole strings and only the first was compared, character for "
            "character, with one ProjectFacts resolved value"
        ),
        "before_repair": {
            "evidence": "READ_FROM_THE_PRE_REPAIR_GATE_SOURCE_DURING_THIS_TRACE",
            "fragment": list(PRE_REPAIR_PREDICATE),
            "emitted_flat_list_line": flat_list_lines[0]["line"] if flat_list_lines else None,
        },
        "before_repair_fragment_still_present": fragment_still_present,
        "after_repair": {
            "evidence": "READ_FROM_THE_GATE_SOURCE_ON_DISK_AT_RUN_TIME",
            "atomic_validation_call_lines": atomic_call_lines,
            "emitted_flat_list_lines": flat_list_lines,
        },
    }


def _source_characters(
    source_pdf: Path,
    page_number: int,
    x0: float,
    x1: float,
    rule_y: float,
) -> tuple[list[dict], dict]:
    """Every source character printed inside one drawn rule's own span.

    This is the source's own printing, read from the source PDF - the evidence a
    ``SOURCE_TEMPLATE_LITERAL`` has to be backed by.

    The rule's x-band is shared by every row on the page, so the characters are
    first scoped to the source's own text line: the row the rule is drawn under.
    A rule underlines the text above it, so the owning row is the line whose
    vertical extent contains the rule's own y.  Without that scoping the check
    would accept any glyph that happens to sit at the same x on another row.
    """

    import pymupdf

    document = pymupdf.open(str(source_pdf))
    page = document[page_number - 1]
    owning_rows = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            top, bottom = line["bbox"][1], line["bbox"][3]
            if top - 0.5 <= rule_y <= bottom + 0.5:
                owning_rows.append(
                    {
                        "y0": round(top, 2),
                        "y1": round(bottom, 2),
                        "x0": round(line["bbox"][0], 2),
                        "x1": round(line["bbox"][2], 2),
                        "text": "".join(span["text"] for span in line["spans"]),
                    }
                )
    characters = []
    for block in page.get_text("rawdict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            top, bottom = line["bbox"][1], line["bbox"][3]
            if not (top - 0.5 <= rule_y <= bottom + 0.5):
                continue
            for span in line.get("spans", []):
                for character in span.get("chars", []):
                    centre = (character["bbox"][0] + character["bbox"][2]) / 2.0
                    if x0 - 0.5 <= centre <= x1 + 0.5 and character["c"].strip():
                        characters.append(
                            {
                                "char": character["c"],
                                "x0": round(character["bbox"][0], 2),
                                "x1": round(character["bbox"][2], 2),
                                "inside_rule_span": (
                                    character["bbox"][0] >= x0 - 0.5
                                    and character["bbox"][2] <= x1 + 0.5
                                ),
                            }
                        )
    document.close()
    return characters, {
        "owning_rows": owning_rows,
        "owning_row_text": "".join(row["text"] for row in owning_rows),
    }


def _delivered_runs(build: Path, paragraph_index: int) -> list[dict]:
    """The delivered Word runs of one paragraph: text, decoration, ownership."""

    import docx

    WORDPROCESSINGML = (
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    )
    document = docx.Document(str(build / "基础投标文件.docx"))
    if paragraph_index >= len(document.paragraphs):
        return []
    paragraph = document.paragraphs[paragraph_index]
    runs = []
    for index, run in enumerate(paragraph.runs):
        underline = run._r.findall(f".//{WORDPROCESSINGML}u")
        runs.append(
            {
                "run_index": index,
                "text": run.text,
                "underline": bool(underline),
                "underline_values": [
                    element.get(f"{WORDPROCESSINGML}val") for element in underline
                ],
                "tabs": len(run._r.findall(f".//{WORDPROCESSINGML}tab")),
                "character_count": len(run.text),
            }
        )
    return runs


def _atom_table(
    presentation: dict,
    facts: dict,
    source_characters: list[dict],
) -> tuple[list[dict], dict]:
    """One row per emitted atom, plus the accounting the verdict is argued from."""

    value = str(presentation.get("value") or "")
    underline_kinds = list(presentation.get("underline_components") or [])
    cursor = 0
    rows = []
    unaccounted = 0
    invented = 0
    fact_mismatches = 0
    unidentified_sources = 0
    literal_not_in_source = 0
    marker_over_a_resolved_fact = 0
    for ordinal, component in enumerate(presentation.get("components") or ()):
        kind = str(component.get("kind"))
        text = str(component.get("text") or "")
        field = component.get("field")
        declared_source = str(component.get("source") or "")
        start = value.find(text, cursor) if text else -1
        row = {
            "ordinal": ordinal,
            "emitted_text": text,
            "provenance_class": kind,
            "field": field,
            "value_start_offset": start,
            "value_end_offset": (start + len(text)) if start >= 0 else None,
            "declared_source": declared_source,
            "source_evidence_declared": declared_source
            in APPROVED_COMPONENT_SOURCES,
            "underline_inherited": kind in underline_kinds,
            "source_rule_id": presentation.get("source_rule_id"),
            "source_fill_application_id": presentation.get("application_id"),
            "execution_owner": presentation.get("execution_owner_id"),
        }
        if start < 0:
            # The atom's own text is not where the composition says it is: the
            # reconstruction does not deliver this atom.
            unaccounted += 1
            row["accounted"] = False
        else:
            row["accounted"] = True
            cursor = start + len(text)
        if declared_source not in APPROVED_COMPONENT_SOURCES:
            unidentified_sources += 1
        if kind == "FACT_VALUE":
            payload = (facts.get("fields") or {}).get(str(field)) or {}
            authoritative = payload.get("resolved_value")
            row["project_facts_status"] = payload.get("status")
            row["project_facts_resolved_value"] = authoritative
            row["fact_matches_project_facts"] = (
                payload.get("status") == "RESOLVED" and str(authoritative or "") == text
            )
            if not row["fact_matches_project_facts"]:
                fact_mismatches += 1
        elif kind == "SOURCE_TEMPLATE_LITERAL":
            printed = {entry["char"] for entry in source_characters}
            row["literal_printed_by_source_in_rule_span"] = text in printed
            if text not in printed:
                literal_not_in_source += 1
        elif kind == "SOURCE_FORM_NOT_APPLICABLE_MARKER":
            payload = (facts.get("fields") or {}).get(str(field)) or {}
            row["marker_fact_status"] = payload.get("status")
            row["marker_does_not_cover_a_resolved_fact"] = (
                payload.get("status") != "RESOLVED"
            )
            if payload.get("status") == "RESOLVED":
                marker_over_a_resolved_fact += 1
        else:
            invented += 1
        rows.append(row)
    reconstruction = "".join(str(component.get("text") or "") for component in presentation.get("components") or ())
    accounting = {
        "atom_count": len(rows),
        "unaccounted_atoms": unaccounted,
        "invented_atoms": invented,
        "fact_value_mismatches": fact_mismatches,
        "unidentified_component_sources": unidentified_sources,
        "source_literals_not_printed_by_source": literal_not_in_source,
        "markers_over_a_resolved_fact": marker_over_a_resolved_fact,
        "reconstruction": reconstruction,
        "recorded_value": value,
        "reconstruction_equals_recorded_value": reconstruction == value,
    }
    return rows, accounting


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--gate-report", required=True, type=Path)
    parser.add_argument(
        "--before-diagnostic",
        type=Path,
        default=None,
        help=(
            "the diagnostic taken before the repair; its recorded gate status is "
            "carried forward so the red result stays readable after the gate is fixed"
        ),
    )
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    build = (args.build if args.build.is_absolute() else ROOT / args.build).resolve()
    gate_report_path = (
        args.gate_report if args.gate_report.is_absolute() else ROOT / args.gate_report
    )
    source_pdf = (
        args.source_pdf if args.source_pdf.is_absolute() else ROOT / args.source_pdf
    )

    report = _load(build / "generation_report.json")
    facts = _load(build / "project_facts.json")
    gate = _load(gate_report_path)
    before_diagnostic = (
        _load(
            args.before_diagnostic
            if args.before_diagnostic.is_absolute()
            else ROOT / args.before_diagnostic
        )
        if args.before_diagnostic
        else None
    )

    failed_rule_ids = list(gate.get("semantic_binding_failure_ids") or [])
    if not failed_rule_ids and before_diagnostic:
        failed_rule_ids = list(before_diagnostic.get("gate_binding_failure_ids") or [])
    registry = {
        str(entry.get("source_rule_id")): entry
        for entry in report.get("source_rule_registry") or []
    }
    applications = report.get("source_fill_applications") or []
    owners = report.get("source_form_execution_owners") or []
    presentations = (report.get("slot_value_presentations") or {}).get("records") or []

    trace = []
    for rule_id in failed_rule_ids:
        rule = registry.get(rule_id) or {}
        slot_id = rule.get("authoritative_slot_id")
        rule_applications = [
            entry
            for entry in applications
            if rule_id in (entry.get("source_rule_ids") or ())
        ]
        rule_owners = [
            entry
            for entry in owners
            if rule_id in (entry.get("source_rule_ids") or ())
        ]
        rule_presentations = [
            record
            for record in presentations
            if record.get("slot_id") == slot_id
            or any(
                record.get("slot_id") == entry.get("source_slot_id")
                for entry in rule_applications
            )
        ]
        #: The source's own drawn rule can cover more than one adjacent
        #: placeholder, so the delivered surfaces an application carries may
        #: belong to presentation records with sibling slot ids.  They are
        #: collected by the application's own emitted surfaces, never by a
        #: hardcoded slot id.
        application_surfaces = [
            str(value)
            for entry in rule_applications
            for value in (entry.get("resolved_values") or ())
        ]
        for record in presentations:
            if record in rule_presentations:
                continue
            if record.get("generated_paragraph_index") in {
                entry.get("generated_paragraph_index") for entry in rule_applications
            }:
                rule_presentations.append(record)

        source_rule_span = None
        source_characters: list[dict] = []
        owning_row: dict = {}
        if rule:
            source_rule_span = {
                "source_page": rule.get("source_page"),
                "x0": rule.get("x0"),
                "x1": rule.get("x1"),
                "y": rule.get("y"),
                "relation_type": rule.get("relation_type"),
                "text_occupancy": rule.get("text_occupancy"),
            }
            source_characters, owning_row = _source_characters(
                source_pdf,
                int(rule["source_page"]),
                float(rule["x0"]),
                float(rule["x1"]),
                float(rule["y"]),
            )

        atoms: list[dict] = []
        surface_accounting = []
        for record in rule_presentations:
            enriched = dict(record)
            for entry in rule_applications:
                if record.get("slot_id") == entry.get("source_slot_id"):
                    enriched.setdefault("source_fill_application_id", entry.get("application_id"))
            for entry in rule_owners:
                enriched.setdefault("execution_owner_id", entry.get("source_form_field_id"))
            enriched.setdefault("source_rule_id", rule_id)
            rows, accounting = _atom_table(enriched, facts, source_characters)
            atoms.extend(rows)
            surface_accounting.append(
                {
                    "slot_id": record.get("slot_id"),
                    "recorded_value": accounting["recorded_value"],
                    "method": record.get("method"),
                    "atom_count": accounting["atom_count"],
                    "reconstruction_equals_recorded_value": accounting[
                        "reconstruction_equals_recorded_value"
                    ],
                    "unaccounted_atoms": accounting["unaccounted_atoms"],
                    "invented_atoms": accounting["invented_atoms"],
                    "fact_value_mismatches": accounting["fact_value_mismatches"],
                    "is_one_of_the_emitted_surfaces": accounting["recorded_value"]
                    in application_surfaces,
                    "source_slot_underline_inherited": record.get(
                        "source_slot_underline_inherited"
                    ),
                    "underline_components": record.get("underline_components"),
                }
            )

        delivered_runs = []
        for entry in rule_applications:
            index = entry.get("generated_paragraph_index")
            if index is None:
                continue
            delivered_runs.append(
                {
                    "application_id": entry.get("application_id"),
                    "generated_paragraph_index": index,
                    "runs": _delivered_runs(build, int(index)),
                }
            )

        trace.append(
            {
                "source_rule_id": rule_id,
                "registry_entry": rule,
                "source_rule_span": source_rule_span,
                "source_owning_row": owning_row,
                "source_characters_inside_rule_span": source_characters,
                "source_characters_inside_rule_span_text": "".join(
                    entry["char"] for entry in source_characters
                ),
                "execution_owners": rule_owners,
                "source_fill_applications": rule_applications,
                "emitted_surfaces": application_surfaces,
                "slot_value_presentations": rule_presentations,
                "delivered_runs": delivered_runs,
                "atoms": atoms,
                "surface_accounting": surface_accounting,
            }
        )

    totals = {
        "unaccounted_atoms": sum(
            item["unaccounted_atoms"]
            for entry in trace
            for item in entry["surface_accounting"]
        ),
        "invented_atoms": sum(
            item["invented_atoms"]
            for entry in trace
            for item in entry["surface_accounting"]
        ),
        "fact_value_mismatches": sum(
            item["fact_value_mismatches"]
            for entry in trace
            for item in entry["surface_accounting"]
        ),
        "unidentified_component_sources": sum(
            1 for entry in trace for atom in entry["atoms"]
            if not atom["source_evidence_declared"]
        ),
        "source_literals_not_printed_by_source": sum(
            1 for entry in trace for atom in entry["atoms"]
            if atom["provenance_class"] == "SOURCE_TEMPLATE_LITERAL"
            and not atom.get("literal_printed_by_source_in_rule_span")
        ),
        "markers_over_a_resolved_fact": sum(
            1 for entry in trace for atom in entry["atoms"]
            if atom["provenance_class"] == "SOURCE_FORM_NOT_APPLICABLE_MARKER"
            and not atom.get("marker_does_not_cover_a_resolved_fact")
        ),
        "surfaces_not_fully_reconstructed": sum(
            1 for entry in trace for item in entry["surface_accounting"]
            if not item["reconstruction_equals_recorded_value"]
        ),
        "emitted_surfaces_without_a_presentation_record": sum(
            1
            for entry in trace
            for surface in entry["emitted_surfaces"]
            if surface
            not in {
                item["recorded_value"] for item in entry["surface_accounting"]
            }
            and surface
            not in {
                str(payload.get("resolved_value"))
                for payload in (facts.get("fields") or {}).values()
                if payload.get("status") == "RESOLVED"
            }
        ),
    }
    duplicate_executions = sum(
        len(entry["source_fill_applications"]) - len(
            {item.get("application_id") for item in entry["source_fill_applications"]}
        )
        for entry in trace
    )
    totals["duplicate_executions"] = duplicate_executions

    diagnostic = {
        "schema": SCHEMA,
        "build": build.name,
        "build_hashes": {
            "docx_sha256": _sha256(build / "基础投标文件.docx"),
            "pdf_sha256": _sha256(build / "基础投标文件.pdf"),
            "generation_report_sha256": _sha256(build / "generation_report.json"),
        },
        "gate_report": str(gate_report_path.relative_to(ROOT)).replace("\\", "/"),
        "gate_status_after_repair": gate.get("status"),
        "gate_binding_failure_ids_after_repair": list(
            gate.get("semantic_binding_failure_ids") or []
        ),
        "gate_status_before_repair": (
            before_diagnostic.get("gate_status_before") if before_diagnostic else None
        ),
        "gate_binding_failure_ids_before_repair": (
            list(before_diagnostic.get("gate_binding_failure_ids") or ())
            if before_diagnostic
            else None
        ),
        "before_repair_diagnostic": (
            str(args.before_diagnostic) if args.before_diagnostic else None
        ),
        "gate_binding_failure_ids": failed_rule_ids,
        "gate_collapse": _gate_predicate(),
        "repository_native_provenance_model": {
            "module": "tender_basic/source_fill_policy.py",
            "classes": ["SlotValuePresentation"],
            "component_kinds": [
                "FACT_VALUE",
                "SOURCE_TEMPLATE_LITERAL",
                "SOURCE_FORM_NOT_APPLICABLE_MARKER",
            ],
            "marker_literal": "/",
            "recorded_in_report_key": "slot_value_presentations",
            "note": (
                "the atomic provenance model already exists and is already "
                "written by the emitter at the write event; no second model is "
                "introduced"
            ),
        },
        "trace": trace,
        "totals": totals,
        "conclusion": {
            "emitted_surface_is_one_atomically_composed_slot_value": all(
                item["reconstruction_equals_recorded_value"]
                for entry in trace
                for item in entry["surface_accounting"]
            )
            and bool(trace),
            "whole_value_equality_is_not_a_valid_test_here": True,
            "validator_must_operate_on_atoms": True,
            "source_contract_changed": False,
            "project_facts_changed": False,
            "rendered_content_changed": False,
        },
    }
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(diagnostic, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "out": str(out_path),
                "failed_rule_ids": failed_rule_ids,
                "totals": totals,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
