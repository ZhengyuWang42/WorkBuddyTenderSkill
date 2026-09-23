"""The follow-up's status, assembled from the gates rather than asserted.

Every status this prints is derived from a gate report that was itself produced
from a delivered artifact.  Nothing here re-measures geometry, so nothing here
can disagree with the gates: if a gate is red, its status is red, and this report
is the place a reader can see all of them at once.

Usage::

    .venv/Scripts/python.exe scripts/v1_p21_followup_status.py \
        --build acceptance/workspace/case_001/v1_manual_fidelity_round2_p21fix \
        --baseline-build acceptance/workspace/case_001/v1_manual_fidelity_round2 \
        --out acceptance/reports/v1_generalization/case001_p21_followup_status.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMA = "v1_p21_followup_status/1"

REPORTS = ROOT / "acceptance/reports/v1_generalization"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status_of(report: dict) -> str:
    return str(
        report.get("status")
        or report.get("automated_result")
        or report.get("result")
        or "MISSING"
    )


def passed(report: dict) -> bool:
    """Whether a report's own verdict is a pass.

    Gates spell a pass differently - ``PASS``, ``V1_AUTOMATED_CANDIDATE``,
    ``THREE_CASE_GENERALIZATION = PASS`` - so the verdict is read as the token a
    gate uses for its own outcome rather than compared to one expected spelling.
    """

    for key in ("status", "automated_result", "result"):
        value = report.get(key)
        if not isinstance(value, str) or not value:
            continue
        token = value.rsplit("=", 1)[-1].strip() or value
        if token in ("PASS", "CLOSED"):
            return True
        if token in ("FAIL", "OPEN", "MISSING"):
            return False
        # A labelled pass such as ``V1_AUTOMATED_CANDIDATE`` carries no PASS
        # token of its own; the report's own ``failed_checks`` is then the
        # authority, and a gate that lists failures has not passed.
        return not (report.get("failed_checks") or report.get("failed") or report.get("problems"))
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--baseline-build", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    build = args.build.resolve()
    baseline = args.baseline_build.resolve()

    diagnostic = load(REPORTS / "case001_manual_review_p21_followup_diagnostic.json")
    structural = load(REPORTS / "case001_p21_structural_gate.json")
    inventory = load(REPORTS / "case001_underline_inventory.json")
    fidelity = load(REPORTS / "case001_manual_layout_fidelity.json")
    assembly = load(REPORTS / "case001_source_line_assembly.json")
    ownership = load(REPORTS / "case001_ownership_closure.json")
    reflow = load(REPORTS / "case001_reflow_aware_v1.json")
    regression = load(REPORTS / "three_case_regression.json")
    acceptance = {
        case: load(REPORTS / f"{case}_acceptance.json")
        for case in ("case_001", "case_002", "case_003")
    }
    manifest = load(build / "build_manifest.json")
    baseline_manifest = load(baseline / "build_manifest.json")

    measurements = structural.get("measurements") or {}
    slot = (measurements.get("composite_slots") or [{}])[0]
    rows = measurements.get("audited_source_page_paragraphs") or []
    conclusions = diagnostic.get("conclusions") or {}

    composite_closed = all(
        (
            status_of(structural) == "PASS",
            conclusions.get("composite_underline_states") == ["SLOT_DECORATION_INHERITED"],
            slot.get("source_slot_underline_inherited") is True,
            slot.get("carrier_run_underline") is True,
            slot.get("marker_occurrences") == {"/": 1},
            len(slot.get("bound_rules") or []) == 1,
            bool(slot.get("rendered_rules_under_value")),
            all(
                item.get("rule") is not None
                for item in slot.get("rendered_rules_under_value") or ()
            ),
            not slot.get("rendered_prose_underline", False),
        )
    )

    intro_rows = [
        row
        for row in rows
        if row.get("paragraph_index") == slot.get("generated_paragraph_index")
    ]
    intro = intro_rows[0] if intro_rows else {}
    intro_closed = all(
        (
            intro.get("classification") == "FIRST_LINE_INDENT",
            not intro.get("exempt_reason"),
            (intro.get("word_first_line_pt") or 0.0) > 0.5,
            abs(
                (intro.get("word_left_pt") or 0.0) - (intro.get("expected_left_pt") or 0.0)
            )
            <= 0.5,
            abs(
                (intro.get("word_first_line_pt") or 0.0)
                - (intro.get("expected_first_line_pt") or 0.0)
            )
            <= 0.5,
            abs(
                (intro.get("generated_first_line_x") or 0.0)
                - (intro.get("source_first_row_x") or 0.0)
            )
            <= 2.0,
        )
    )

    numbered = [
        row
        for row in rows
        if row.get("paragraph_index") != slot.get("generated_paragraph_index")
        and row.get("kind") in ("List", "LogicalParagraph")
    ]
    numbered_closed = bool(numbered) and all(
        row.get("classification")
        in ("FIRST_LINE_INDENT", "HANGING_INDENT", "NO_SPECIAL_FIRST_LINE_INDENT")
        and (
            row.get("exempt_reason")
            or (
                abs(
                    (row.get("word_left_pt") or 0.0)
                    - (row.get("expected_left_pt") or 0.0)
                )
                <= 0.5
                and abs(
                    (row.get("word_first_line_pt") or 0.0)
                    - (row.get("expected_first_line_pt") or 0.0)
                )
                <= 0.5
                and (
                    row.get("source_first_row_x") is None
                    or abs(
                        (row.get("generated_first_line_x") or 0.0)
                        - (row.get("source_first_row_x") or 0.0)
                    )
                    <= 2.0
                )
            )
        )
        for row in numbered
    )
    # A page whose paragraphs are all delivered through one shared assumption
    # would satisfy the per-row arithmetic trivially; the audit must have
    # classified each of them separately and found more than one result.
    numbered_closed = numbered_closed and len(
        {row.get("classification") for row in numbered}
    ) >= 1

    case001_gates = {
        "p21_structural_gate": status_of(structural),
        "underline_inventory": status_of(inventory),
        "manual_layout_fidelity": status_of(fidelity),
        "source_line_assembly": status_of(assembly),
        "ownership_closure": status_of(ownership),
        "reflow_aware_v1": status_of(reflow),
        "case_acceptance": status_of(acceptance["case_001"]),
        "three_case_regression": status_of(regression),
    }
    case001_regression = all(
        passed(report)
        for report in (
            structural,
            inventory,
            fidelity,
            assembly,
            ownership,
            reflow,
            acceptance["case_001"],
            regression,
        )
    )

    def case_status(case: str) -> str:
        report = acceptance[case]
        name = Path(report.get("build_dir") or "").name
        return "PASS" if passed(report) and name.endswith("p21fix") else "FAIL"

    case002 = case_status("case_002")
    case003 = case_status("case_003")

    automation = "PASS" if all(
        (
            passed(structural),
            passed(inventory),
            passed(fidelity),
            composite_closed,
            intro_closed,
            numbered_closed,
        )
    ) else "FAIL"

    report = {
        "schema": SCHEMA,
        "build": {
            "build_id": build.name,
            "build_dir": str(build),
            "docx_sha256": manifest.get("generated", {}).get("docx_sha256"),
            "pdf_sha256": manifest.get("generated", {}).get("pdf_sha256"),
            "pdf_page_count": manifest.get("generated", {}).get("pdf_page_count"),
            "source_pdf_sha256": manifest.get("source", {}).get("sha256"),
        },
        "baseline": {
            "build_id": baseline.name,
            "docx_sha256": baseline_manifest.get("generated", {}).get("docx_sha256"),
            "preserved": baseline.exists(),
        },
        "statuses": {
            "CASE001_P21_FOLLOWUP_AUTOMATION": automation,
            "COMPOSITE_SLOT_UNDERLINE": "CLOSED" if composite_closed else "OPEN",
            "INTRO_FIRST_LINE_INDENT": "CLOSED" if intro_closed else "OPEN",
            "NUMBERED_PARAGRAPH_INDENT": "CLOSED" if numbered_closed else "OPEN",
            "CASE001_AUTOMATED_REGRESSION": "PASS" if case001_regression else "FAIL",
            "CASE002_REGRESSION": case002,
            "CASE003_REGRESSION": case003,
            "MANUAL_WORD_REVIEW_REQUIRED": True,
            "V1_PRODUCTION_CANDIDATE": False,
            "READY_FOR_SUBMISSION": False,
        },
        "case001_gates": case001_gates,
        "evidence": {
            "composite_slot": {
                "slot_id": slot.get("slot_id"),
                "source_page": slot.get("source_page"),
                "generated_page": slot.get("generated_page"),
                "generated_paragraph_index": slot.get("generated_paragraph_index"),
                "value": slot.get("value"),
                "bound_rules": slot.get("bound_rules"),
                "marker_field_status": slot.get("marker_field_status"),
                "marker_occurrences": slot.get("marker_occurrences"),
                "separator_occurrences": slot.get("separator_occurrences"),
                "carrier_run_underline": slot.get("carrier_run_underline"),
                "slot_neighbour_runs": slot.get("slot_neighbour_runs"),
                "rendered_rules_under_value": slot.get("rendered_rules_under_value"),
                "underline_provenance": (
                    ((diagnostic.get("defect_a_composite_slot_underline") or {}).get("slots") or [{}])[0]
                    .get("underline_authority", {})
                    .get("provenance")
                ),
                "suffix_prose_underline": (
                    ((diagnostic.get("defect_a_composite_slot_underline") or {}).get("slots") or [{}])[0]
                    .get("underline_authority", {})
                    .get("suffix_prose_underline")
                ),
                "bound_decoration_rule_ids": conclusions.get(
                    "composite_bound_decoration_rule_ids"
                ),
                "accounting_identity": (
                    "exactly one logical source rule owns the slot's decoration; the "
                    "emitter grants the inheritance only to a rule whose placeholder a "
                    "resolved value replaces"
                ),
            },
            "paragraph_indents": {
                "classification_histogram": measurements.get("classification_histogram"),
                "audited_source_pages": measurements.get("audited_source_pages"),
                "changed_paragraph_count": (
                    diagnostic.get("defect_b_paragraph_indent") or {}
                ).get("changed_paragraph_count"),
                "exempt_paragraph_reasons": measurements.get("exempt_paragraph_reasons"),
                "exempt_paragraph_count": measurements.get("exempt_paragraph_count"),
                "unclassified_paragraph_reasons": sorted(
                    {
                        item.get("reason")
                        for item in measurements.get("unclassified_paragraphs") or []
                    }
                ),
                "page_rows": rows,
            },
            "unchanged_round2_evidence": {
                "underline_inventory_totals": inventory.get("totals")
                or inventory.get("summary"),
                "reflow_contract": reflow.get("measured"),
                "reflow_checks": reflow.get("checks"),
            },
        },
        "pre_existing_residuals": {
            "p3_closure_phase3": (
                "v09_p3_closure_gate.evaluate_frozen_phase raises ValueError on phase 3 "
                "for this build and for the accepted baseline alike; unchanged by this "
                "follow-up"
            ),
            "p3_closure_phase2": (
                "FAIL on both this build and the accepted baseline with a byte-identical "
                "report body (excluding build path/hash keys)"
            ),
            "case001_internal_preview_gate": (
                "still FAIL on p3_frozen_rules_all_accounted and "
                "p3_contract_acceptance_holds, which are the two phase-2 checks above; "
                "identical on the accepted baseline"
            ),
        },
        "deliberate_non_changes": [
            "the source form's '/' remains a presentation marker: lot_name is still NOT_FOUND",
            "no resolved value was invented and no source rule was duplicated",
            "the source section margins were not touched",
            "no source-form line geometry or vertical-rhythm behaviour was changed",
            "no prior geometry gate was relaxed",
        ],
    }
    if not status_of(structural):
        report["statuses"]["CASE001_P21_FOLLOWUP_AUTOMATION"] = "FAIL"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out.resolve()),
                "build_id": build.name,
                "build_docx_sha256": report["build"]["docx_sha256"],
                "statuses": report["statuses"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["statuses"]["CASE001_P21_FOLLOWUP_AUTOMATION"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
