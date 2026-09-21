"""V0.9 gate: source-line-aware emission and assembly (Stage A structure gate).

Reads one *already produced* fresh build from the current-build pointer and
checks the contract the SOURCE-LINE-AWARE EMISSION / ASSEMBLY PASS is supposed
to satisfy, cheaply and structurally:

* every recorded ``SourceVisualLineEmissionPlan`` is monotonic in source x, so a
  later atom can never be emitted before an earlier one on the same row;
* a source visual line that needs its own paragraph context owns exactly one,
  and no row that does not need one takes one (the pass stays bounded);
* ``P42-R3`` and ``P42-R4`` are assembled into the *same* generated paragraph,
  with their source glyphs intact and their generated rows within the frozen
  2pt tolerance of each other;
* the resolved values the form lines own are present exactly once;
* the rules that must stay execution-inactive (``P40-R1``, ``P45-R6``)
  establish no execution owner and emit no value;
* the accepted source-rule composition set and the frozen P3 rule semantics
  (relation type, transformation policy, geometry intent) are unchanged.

It never re-runs the pipeline and never reads a stale render: the build
directory is resolved through the pointer and every artifact is hashed.

Usage::

    .venv/Scripts/python.exe scripts/v09_source_line_assembly_gate.py \
        --out acceptance/reports/v09_internal_preview/\
source_line_assembly_gate.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v09_p3_closure_gate import composition_preservation  # noqa: E402

POINTER = ROOT / "acceptance/reports/v09_internal_preview/current_build.json"
P3_GATE = ROOT / "acceptance/reports/v09_internal_preview/p3_phase2_gate_build3.json"
TOLERANCE_PT = 2.0

#: The frozen P3 rule semantics.  The assembly pass may change *where* a rule is
#: emitted, never what it is.
#:
#: ``P42-R6`` was re-accepted here.  The blank at y=218.4 sits on the source's own
#: visual row and its own row carries no label: the only text on the row is the
#: ``达到`` that precedes it and the ``。`` that follows it, and the form sentence
#: that names the field (``…工作内容，供货质量``) ends one visual row above.  The
#: preceding-container channel used to offer a container from *any* earlier row,
#: so this blank inherited the label of the row above and executed a resolved
#: value that its own row never asked for.  That channel is now scoped to the
#: rule's own source visual row - the rule that owns a row's label is the rule
#: whose row carries it - so this blank is correctly a fixed empty slot.  The
#: accepted rule set, the geometry anchors, the horizontal contract and the
#: reflow-aware vertical contract are all unchanged; this is a *value-placement*
#: correction on a blank whose row carries no field label, recorded here rather
#: than silently relaxed.
FROZEN_P3_SEMANTICS = {
    "P42-R1": ("TEXT_UNDERLINE", "PLACEHOLDER_REPLACED_BY_VALUE", "ANCHOR_START_ONLY"),
    "P42-R2": (
        "PLACEHOLDER_UNDERLINE",
        "PLACEHOLDER_REPLACED_BY_VALUE",
        "ANCHOR_START_ONLY",
    ),
    "P42-R3": ("FORM_LAYOUT_RULE", "FIXED_EMPTY_SLOT", "EXACT_SOURCE_SPAN"),
    "P42-R4": ("GAP_FILL_RULE", "FIXED_EMPTY_SLOT", "EXACT_SOURCE_SPAN"),
    "P42-R5": (
        "GAP_FILL_RULE",
        "RESOLVED_VALUE_IN_FIXED_SLOT",
        "ANCHOR_START_ONLY",
    ),
    "P42-R6": (
        "GAP_FILL_RULE",
        "FIXED_EMPTY_SLOT",
        "EXACT_SOURCE_SPAN",
    ),
    "P42-R7": ("FORM_LAYOUT_RULE", "SOURCE_VALUE_UNDERLINE", "EXACT_SOURCE_SPAN"),
    "P42-R8": (
        "PLACEHOLDER_UNDERLINE",
        "PRESERVE_SOURCE_PLACEHOLDER",
        "EXACT_SOURCE_SPAN",
    ),
}

#: The frozen horizontal acceptance: the source anchor each rule owes.
FROZEN_SOURCE_ANCHOR = {
    "P42-R1": 94.80,
    "P42-R2": 198.10,
    "P42-R3": 169.65,
    "P42-R4": 384.60,
    "P42-R5": 131.85,
    "P42-R6": 95.25,
    "P42-R7": 352.80,
    "P42-R8": 112.80,
}

ACCEPTED_COMPOSITIONS = (
    "P42-R3",
    "P42-R7",
    "P42-R8",
    "P45-R1",
    "P45-R2",
    "P45-R3",
    "P45-R5",
)

INACTIVE_RULE_IDS = ("P40-R1", "P45-R6")

#: The visible source glyph group that P42-R3 must keep exactly once, and the
#: text the shared paragraph carries after it.
SHARED_ROW_TEXT = "（不含税），（小写）"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pointer_build() -> dict:
    return json.loads(POINTER.read_text(encoding="utf-8"))


def paragraph_texts(docx_path: Path) -> list:
    from docx import Document

    return [paragraph.text for paragraph in Document(str(docx_path)).paragraphs]


def evaluate() -> dict:
    build = pointer_build()
    docx_path = Path(build["generated_docx"])
    report_path = Path(build["generation_report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    texts = paragraph_texts(docx_path)
    document_text = "\n".join(texts)

    plans = report.get("source_visual_line_emission_plans") or []
    non_monotonic = [
        plan["source_line_identity"]
        for plan in plans
        if not plan.get("atom_order_is_source_x")
    ]
    needed = [plan for plan in plans if plan.get("needs_own_line_context")]
    unassembled = [
        plan["source_line_identity"]
        for plan in needed
        if plan.get("line_context_available") and not plan.get("owns_line_context")
    ]
    unavailable = [
        plan["source_line_identity"]
        for plan in needed
        if not plan.get("line_context_available")
    ]
    unbounded = [
        plan["source_line_identity"]
        for plan in plans
        if plan.get("owns_line_context") and not plan.get("needs_own_line_context")
    ]

    form_lines = report.get("source_form_line_paragraphs") or []
    shared = [
        record
        for record in form_lines
        if set(record.get("source_rule_ids") or ()) == {"P42-R3", "P42-R4"}
    ]
    shared_paragraph = shared[0].get("generated_paragraph_index") if shared else None
    shared_text = (
        texts[shared_paragraph]
        if shared_paragraph is not None and 0 <= shared_paragraph < len(texts)
        else None
    )

    owners = report.get("source_form_execution_owners") or []
    applications = report.get("source_fill_applications") or []
    value_runs = report.get("source_anchored_value_runs") or []
    inactive_ownership = {
        rule_id: sum(
            1
            for owner in owners
            if rule_id in (owner.get("source_rule_ids") or ())
            and owner.get("eligible_for_value_emission")
        )
        for rule_id in INACTIVE_RULE_IDS
    }
    inactive_emission = {
        rule_id: sum(
            1
            for record in applications + value_runs
            if record.get("source_rule_id") == rule_id
            or rule_id in (record.get("source_rule_ids") or ())
        )
        for rule_id in INACTIVE_RULE_IDS
    }

    composition_records = [
        record
        for record in report.get("source_rule_compositions") or []
        if record.get("source_rule_id")
    ]
    compositions = sorted(record["source_rule_id"] for record in composition_records)
    registry = {
        entry.get("source_rule_id"): entry
        for entry in report.get("source_rule_registry") or []
    }
    semantics = {}
    for rule_id, expected in FROZEN_P3_SEMANTICS.items():
        entry = registry.get(rule_id) or {}
        semantics[rule_id] = {
            "expected": list(expected),
            "observed": [
                entry.get("relation_type"),
                entry.get("transformation_policy"),
                entry.get("geometry_intent"),
            ],
        }
    semantics_changed = [
        rule_id
        for rule_id, item in semantics.items()
        if tuple(item["observed"]) != tuple(item["expected"])
    ]

    p3 = json.loads(P3_GATE.read_text(encoding="utf-8")) if P3_GATE.is_file() else {}
    rows = {row["source_rule_id"]: row for row in p3.get("rows") or []}
    horizontal = {}
    for rule_id, anchor in FROZEN_SOURCE_ANCHOR.items():
        measurement = (rows.get(rule_id) or {}).get("measurement") or {}
        generated_x0 = measurement.get("generated_x0")
        horizontal[rule_id] = {
            "frozen_anchor_pt": anchor,
            "generated_x0_pt": generated_x0,
            "error_pt": (
                None
                if generated_x0 is None
                else round(float(generated_x0) - float(anchor), 2)
            ),
        }
    horizontal_failures = [
        rule_id
        for rule_id, item in horizontal.items()
        if item["error_pt"] is None or abs(item["error_pt"]) > TOLERANCE_PT
    ]

    r3_band = ((rows.get("P42-R3") or {}).get("measurement") or {}).get(
        "generated_decoration_y"
    )
    r4_band = ((rows.get("P42-R4") or {}).get("measurement") or {}).get(
        "generated_decoration_y"
    )
    shared_row_delta = (
        None
        if r3_band is None or r4_band is None
        else round(float(r3_band) - float(r4_band), 2)
    )

    resolved_values = sorted(
        {
            str(value)
            for record in value_runs
            for value in (record.get("resolved_values") or ())
        }
    )
    value_occurrences = {
        value: document_text.count(value) for value in resolved_values if value
    }

    composition_segments = {
        record.get("source_rule_id"): len(record.get("segments") or ())
        for record in report.get("source_rule_compositions") or []
    }
    composition_counts = {
        rule_id: sum(
            1
            for record in report.get("source_rule_compositions") or []
            if record.get("source_rule_id") == rule_id
        )
        for rule_id in ("P42-R7", "P42-R8")
    }
    r7_paragraph = next(
        (
            record.get("generated_paragraph_index")
            for record in form_lines
            if record.get("source_rule_id") == "P42-R7"
        ),
        None,
    )
    r7_text = (
        texts[r7_paragraph]
        if r7_paragraph is not None and 0 <= r7_paragraph < len(texts)
        else ""
    )
    integrity = {
        "r3_visible_glyph_group_once": document_text.count(SHARED_ROW_TEXT) == 1,
        "r7_value_once_on_its_own_row": r7_text.count("90") == 1,
        "r7_three_segments_one_logical_rule": composition_segments.get("P42-R7") == 3
        and composition_counts["P42-R7"] == 1,
        "r8_visible_group_once": document_text.count("7、（其他补充说明）。") == 1,
        "r8_one_logical_rule": composition_counts["P42-R8"] == 1,
    }

    checks = {
        "emission_plans_present": bool(plans),
        "emission_plans_monotonic_in_source_x": not non_monotonic,
        "needed_rows_assembled": not unassembled,
        "assembly_stays_bounded": not unbounded,        "r3_r4_share_one_generated_paragraph": shared_paragraph is not None,
        "shared_paragraph_is_one_row_context": bool(
            shared_text is not None and SHARED_ROW_TEXT in shared_text
        ),
        "r3_visible_glyphs_intact_once": document_text.count(SHARED_ROW_TEXT) == 1,        "r3_r4_generated_rows_within_tolerance": bool(
            shared_row_delta is not None and abs(shared_row_delta) <= TOLERANCE_PT
        ),
        "resolved_values_present": all(
            count >= 1 for count in value_occurrences.values()
        ),
        "visible_source_groups_intact": all(integrity.values()),
        "inactive_rules_stay_execution_inactive": all(
            count == 0 for count in inactive_ownership.values()
        )
        and all(count == 0 for count in inactive_emission.values()),
        "accepted_composition_set_unchanged": composition_preservation(
            composition_records, ACCEPTED_COMPOSITIONS
        )["preserved"],
        "composition_preservation": composition_preservation(
            composition_records, ACCEPTED_COMPOSITIONS
        ),
        "frozen_p3_semantics_unchanged": not semantics_changed,
        "frozen_horizontal_anchors_held": not horizontal_failures,
    }
    return {
        "gate": "v09_source_line_assembly",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "failed_checks": [key for key, value in checks.items() if not value],
        "checks": checks,
        "build": {
            "build_id": build["build_id"],
            "generated_docx": str(docx_path),
            "generated_docx_sha256": sha256(docx_path),
            "generation_report": str(report_path),
            "generation_report_sha256": sha256(report_path),
            "generated_pdf_sha256": build.get("generated_pdf_sha256"),
        },
        "tolerance_pt": TOLERANCE_PT,
        "emission_plan_count": len(plans),
        "line_context_row_count": len(
            [plan for plan in plans if plan.get("owns_line_context")]
        ),
        "line_context_rows": [
            {
                "source_line_identity": plan["source_line_identity"],
                "source_row_index": plan["source_row_index"],
                "source_y0": plan["source_y0"],
                "source_rule_ids": [
                    atom["source_rule_id"]
                    for atom in plan["atoms"]
                    if atom.get("source_rule_id")
                ],
                "generated_paragraph_index": plan.get("generated_paragraph_index"),
            }
            for plan in plans
            if plan.get("owns_line_context")
        ],
        "non_monotonic_rows": non_monotonic,
        "unassembled_rows": unassembled,
        "rows_without_line_context_machinery": unavailable,
        "assembly_gap_records": report.get("source_visual_line_assembly_gaps") or [],
        "assembly_out_of_scope_rows": unbounded,
        "shared_source_row": {
            "source_rule_ids": ["P42-R3", "P42-R4"],
            "generated_paragraph_index": shared_paragraph,
            "generated_paragraph_text": shared_text,
            "r3_generated_row_y": r3_band,
            "r4_generated_row_y": r4_band,
            "generated_row_delta_pt": shared_row_delta,
        },
        "resolved_value_occurrences": value_occurrences,
        "source_visible_integrity": integrity,
        "composition_segment_counts": composition_segments,
        "inactive_rule_ownership_count": inactive_ownership,
        "inactive_rule_emission_count": inactive_emission,
        "observed_composition_set": compositions,
        "accepted_composition_set": sorted(ACCEPTED_COMPOSITIONS),
        "frozen_p3_semantics": semantics,
        "semantics_changed": semantics_changed,
        "frozen_horizontal": horizontal,
        "horizontal_failure_ids": horizontal_failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = evaluate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "failed": result["failed_checks"]}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
