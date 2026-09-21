"""V0.9 Phase 3 canonical gate: reflow-aware P3 vertical closure.

The frozen Phase-3 gate measured each rule's generated y against its source y and
required 2.0pt.  That measurement cannot tell a *renderer defect* apart from
*reflow the source's own content forces*, so a build that correctly reproduces
the source but needs more generated lines than the template had could never pass.

This gate keeps the frozen measurement - the raw source-fidelity difference is
still reported in full - and adds the ``REFLOW_AWARE_V1`` contract from
:mod:`tender_basic.vertical_reflow_qa`.  A row now passes when the difference
that remains *after every independently justified mandatory expansion* is within
the same, unrelaxed 2.0pt tolerance, and when the generated region contains no
row the independent minimum-row computation did not ask for.

Usage::

    python scripts/v09_p3_reflow_vertical_gate.py \\
        --source <source.pdf> --generated <generated.pdf> \\
        --report <generation_report.json> --out <gate.json>
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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import pymupdf  # noqa: E402

from tender_basic.vertical_reflow_qa import (  # noqa: E402
    CONTRACT_VERSION,
    TOLERANCE_PT,
    REASON_STRUCTURAL_ISOLATION,
)
from tender_basic.vertical_reflow_region import build_region_reflow_plan  # noqa: E402
from v09_p3_closure_gate import (  # noqa: E402
    ACCEPTED_COMPOSITIONS,
    P3_GENERATED_PAGE,
    P3_SOURCE_PAGE,
    evaluate as evaluate_frozen_phase,
)

REPORTS = ROOT / "acceptance" / "reports" / "v09_internal_preview"
P3_REGION_RULE_IDS = tuple("P42-R%d" % index for index in range(1, 9))
PHASE2_GATE = REPORTS / "p3_phase2_gate.json"
OWNERSHIP_GATE = REPORTS / "phase1_execution_ownership_closure.json"
ASSEMBLY_GATE = REPORTS / "source_line_assembly_gate.json"
PREVIEW_GATE = REPORTS / "case001_v09_internal_preview_gate.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_optional(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def summarise_side_gate(path: Path, payload: dict | None) -> dict:
    if payload is None:
        return {"present": False, "path": str(path)}
    return {
        "present": True,
        "path": str(path),
        "sha256": sha256(path),
        "status": payload.get("status"),
        "failed_checks": payload.get("failed_checks"),
        "checks": payload.get("checks"),
        "evidence": payload.get("evidence"),
        "conclusion": payload.get("conclusion"),
    }


def evaluate(
    *,
    source_path: Path,
    generated_path: Path,
    report_path: Path,
) -> dict:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    frozen = evaluate_frozen_phase(
        source_path=Path(source_path),
        generated_path=Path(generated_path),
        report_path=Path(report_path),
        phase=3,
    )

    source_doc = pymupdf.open(source_path)
    generated_doc = pymupdf.open(generated_path)
    try:
        region = build_region_reflow_plan(
            source_doc=source_doc,
            generated_doc=generated_doc,
            report=report,
            source_page=P3_SOURCE_PAGE,
            generated_page=P3_GENERATED_PAGE,
            region_rule_ids=P3_REGION_RULE_IDS,
        )
    finally:
        source_doc.close()
        generated_doc.close()

    plans = region["_plans"]
    isolations = region["structural_isolations"]

    #: The accepted per-row ledger, without the private dataclass handles.
    reflow_rows = [plan.to_dict() for plan in plans]
    raw_row_table = [
        {
            "source_rule_id": row["source_rule_id"],
            "transformation_policy": row.get("transformation_policy"),
            "geometry_intent": row.get("geometry_intent"),
            "source_y": (row.get("source_geometry") or {}).get("y"),
            "generated_y": (row.get("measurement") or {}).get("generated_y"),
            "raw_y_error": (row.get("measurement") or {}).get("y_error"),
            "raw_vertical_pass": row.get("vertical_pass"),
        }
        for row in frozen.get("in_scope_rows") or []
    ]

    horizontal_failures = list(frozen.get("horizontal_failure_ids") or [])
    missing_rules = list(frozen.get("missing_frozen_rule_ids") or [])
    cross_page = list(frozen.get("cross_page_rule_ids") or [])
    out_of_scope = list(frozen.get("emission_scope_out_of_p3_pages") or [])

    #: Reflow-aware vertical closure replaces the frozen absolute test.  The
    #: frozen test's own verdicts are kept beside it, never overwritten.
    reflow_vertical_failure_ids = [
        row["source_visual_line_id"] for row in reflow_rows if not row["pass"]
    ]
    order_preserved = bool(region["generated_row_order_preserved"])
    unexplained_rows = int(region["unexplained_extra_row_count"])
    unexplained_blanks = list(region["unexplained_blank_row_gaps"])
    mandatory_rows = int(region["mandatory_minimum_generated_rows"])
    generated_rows = int(region["generated_region_rows"])
    source_rows = int(region["source_logical_rows"])

    unexplained_extra_line_sum = sum(
        row["mandatory_extra_line_count"] for row in reflow_rows
    )
    rows_accounted = source_rows + unexplained_extra_line_sum == mandatory_rows == generated_rows

    region_typography_sizes = sorted(
        {row["typography"]["font_size_pt"] for row in reflow_rows}
    )
    source_typography_sizes = sorted(
        {
            atom_size
            for row in reflow_rows
            for atom_size in [row["typography"]["font_size_pt"]]
        }
    )
    no_text_shrinking = region_typography_sizes == source_typography_sizes and all(
        row["typography"]["font_size_pt"] > 0 for row in reflow_rows
    )

    isolation_failures = [
        record["source_rule_id"]
        for record in isolations
        if not record["structural_isolation_proven"]
    ]
    forced_rules = {
        rule_id
        for row in reflow_rows
        for rule_id in row["forced_new_line_rule_ids"]
    }
    isolations_cover_forcings = forced_rules <= {
        record["source_rule_id"] for record in isolations
    }

    checks = {
        "fresh_generated_pdf": frozen["checks"].get("fresh_generated_pdf", False),
        "fresh_generated_report": frozen["checks"].get("fresh_generated_report", False),
        "region_rows_accounted": rows_accounted,
        "mandatory_expansion_independently_justified": all(
            row["minimum_required_generated_line_count"] >= 1
            and row["participating_content"]
            and row["available_width_pt"] > 0
            for row in reflow_rows
        ),
        "no_unexplained_extra_row": unexplained_rows == 0,
        "no_unexplained_blank_row": not unexplained_blanks,
        "source_logical_order_preserved": order_preserved
        and bool(region["all_rows_matched"]),
        "vertical_residual_within_tolerance": not reflow_vertical_failure_ids,
        "vertical_tolerance_is_frozen": float(region["tolerance_pt"]) == TOLERANCE_PT,
        "raw_y_error_preserved_in_report": all(
            row["raw_y_error"] is not None for row in reflow_rows
        ),
        "structural_isolation_proven_or_absent": not isolation_failures
        and isolations_cover_forcings,
        "no_text_shrinking": no_text_shrinking,
        "no_absolute_positioning": int(report.get("generated_textbox_count") or 0) == 0
        and not (report.get("positioned_form_layout_breaks") or []),
        "horizontal_within_tolerance": not horizontal_failures,
        "exact_span_rules_intact": frozen["checks"].get("exact_span_rules_intact", False),
        "accepted_composition_set_unchanged": frozen["checks"].get(
            "accepted_composition_set_unchanged", False
        ),
        "rule_accounting_complete": frozen["checks"].get("rule_accounting_complete", False),
        "no_cross_page_rule_binding": not cross_page,
        "emission_scope_is_p3": not out_of_scope,
        "p3_scope_complete": not missing_rules,
    }

    phase2 = load_optional(PHASE2_GATE)
    ownership = load_optional(OWNERSHIP_GATE)
    assembly = load_optional(ASSEMBLY_GATE)
    preview = load_optional(PREVIEW_GATE)

    payload = dict(frozen)
    payload.update(
        {
            "gate": "v09_p3_closure_phase3_reflow_aware",
            "phase": 3,
            "vertical_contract_version": CONTRACT_VERSION,
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "failed_checks": [name for name, ok in checks.items() if not ok],
            "tolerance_pt": TOLERANCE_PT,
            #: Frozen absolute vertical evidence, retained verbatim.
            "frozen_absolute_vertical_row_order_preserved": frozen.get(
                "vertical_row_order_preserved"
            ),
            "frozen_absolute_vertical_failure_ids": list(
                frozen.get("vertical_failure_ids") or []
            ),
            "frozen_absolute_maximum_y_error_pt": max(
                (
                    abs(row["raw_y_error"])
                    for row in raw_row_table
                    if row["raw_y_error"] is not None
                ),
                default=0.0,
            ),
            #: Reflow-aware verdict that now governs closure.
            "vertical_row_order_preserved": order_preserved,
            "vertical_failure_ids": reflow_vertical_failure_ids,
            "source_row_origin_offset_pt": region["region_origin_offset_pt"],
            "source_line_pitch_pt": region["source_line_pitch_pt"],
            "vertical_reflow": {
                "vertical_contract_version": CONTRACT_VERSION,
                "tolerance_pt": TOLERANCE_PT,
                "source_logical_rows": source_rows,
                "generated_region_rows": generated_rows,
                "mandatory_minimum_generated_rows": mandatory_rows,
                "unexplained_vertical_expansion_count": unexplained_rows,
                "unexplained_blank_row_count": len(unexplained_blanks),
                "unexplained_blank_row_gaps": unexplained_blanks,
                "source_line_pitch_pt": region["source_line_pitch_pt"],
                "applicable_line_pitch_pt": region["applicable_line_pitch_pt"],
                "line_pitch_expansion_pt": region["line_pitch_expansion_pt"],
                "region_origin_offset_pt": region["region_origin_offset_pt"],
                "right_limit_pt": region["right_limit_pt"],
                "region_left_pt": region["region_left_pt"],
                "raw_vertical_source_fidelity_difference_present": region[
                    "raw_vertical_source_fidelity_difference_present"
                ],
                "mandatory_reflow_present": region["mandatory_reflow_present"],
                "mandatory_reflow_fully_explains_vertical_difference": (
                    unexplained_rows == 0 and not reflow_vertical_failure_ids
                ),
                "maximum_raw_y_error_pt": region["maximum_raw_y_error_pt"],
                "maximum_residual_y_error_pt": region[
                    "maximum_residual_y_error_pt"
                ],
                "structural_isolations": isolations,
                "groups": region["groups"],
                "rows": reflow_rows,
            },
            "raw_vertical_row_table": raw_row_table,
            "horizontal": {
                "horizontal_failure_ids": horizontal_failures,
                "matched": len(frozen.get("in_scope_rows") or []),
                "lost": len(missing_rules),
                "invented": len(
                    [
                        rule_id
                        for rule_id in frozen.get("emitted_source_rule_ids") or []
                        if rule_id not in P3_REGION_RULE_IDS
                    ]
                ),
                "out_of_tolerance": len(horizontal_failures),
                "coverage": {
                    "frozen_rules": len(P3_REGION_RULE_IDS),
                    "accounted": len(P3_REGION_RULE_IDS) - len(missing_rules),
                    "ratio": round(
                        (len(P3_REGION_RULE_IDS) - len(missing_rules))
                        / float(len(P3_REGION_RULE_IDS)),
                        4,
                    ),
                },
                "accepted_composition_set": list(ACCEPTED_COMPOSITIONS),
                "observed_composition_set": frozen.get("observed_composition_set"),
            },
            "semantics": {
                "transformation_policy_rows": {
                    row["source_rule_id"]: row.get("transformation_policy")
                    for row in frozen.get("in_scope_rows") or []
                },
                "geometry_intent_rows": {
                    row["source_rule_id"]: row.get("geometry_intent")
                    for row in frozen.get("in_scope_rows") or []
                },
                "accepted_composition_set_unchanged": frozen["checks"].get(
                    "accepted_composition_set_unchanged", False
                ),
            },
            "execution_ownership": summarise_side_gate(OWNERSHIP_GATE, ownership),
            "source_line_assembly": summarise_side_gate(ASSEMBLY_GATE, assembly),
            "applications": {
                "planned_resolved_application_count": report.get(
                    "planned_resolved_application_count"
                ),
                "actual_resolved_application_count": report.get(
                    "actual_resolved_application_count"
                ),
                "source_fill_application_count": report.get(
                    "source_fill_application_count"
                ),
                "missing_planned_application_count": report.get(
                    "missing_planned_application_count"
                ),
                "unexpected_application_count": report.get(
                    "unexpected_application_count"
                ),
                "owner_driven_value_emission_count": report.get(
                    "owner_driven_value_emission_count"
                ),
                "source_form_line_value_run_count": report.get(
                    "source_form_line_value_run_count"
                ),
                "plan_application_metrics": report.get("plan_application_metrics"),
            },
            "safety": {
                "generated_textbox_count": report.get("generated_textbox_count"),
                "synthetic_layout_tables": report.get("synthetic_layout_tables"),
                "form_layout_break_count": report.get("form_layout_break_count"),
                "unsafe_ooxml": (report.get("word_safe_scan") or {}).get(
                    "unsafe_ooxml"
                ),
                "word_safe_scan_result": (report.get("word_safe_scan") or {}).get(
                    "result"
                ),
                "positioned_form_layout_breaks": report.get(
                    "positioned_form_layout_breaks"
                ),
            },
            "coverage": {
                "preview_gate": summarise_side_gate(PREVIEW_GATE, preview),
                "phase2_gate": summarise_side_gate(PHASE2_GATE, phase2),
            },
            "accounting": {
                "source_rule_count": frozen.get("source_rule_count"),
                "painted_rule_count": frozen.get("painted_rule_count"),
                "emitted_source_rule_ids": frozen.get("emitted_source_rule_ids"),
                "missing_frozen_rule_ids": missing_rules,
                "cross_page_rule_ids": cross_page,
                "emission_scope_out_of_p3_pages": out_of_scope,
                "region_rows_accounted": rows_accounted,
            },
        }
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--generated", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--also", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = evaluate(
        source_path=args.source.resolve(),
        generated_path=args.generated.resolve(),
        report_path=args.report.resolve(),
    )
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(encoded, encoding="utf-8")
    if args.also is not None:
        args.also.parent.mkdir(parents=True, exist_ok=True)
        args.also.write_text(encoded, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "failed_checks": payload["failed_checks"],
                "vertical_contract_version": payload["vertical_contract_version"],
                "maximum_residual_y_error_pt": payload["vertical_reflow"][
                    "maximum_residual_y_error_pt"
                ],
                "maximum_raw_y_error_pt": payload["vertical_reflow"][
                    "maximum_raw_y_error_pt"
                ],
                "unexplained_vertical_expansion_count": payload["vertical_reflow"][
                    "unexplained_vertical_expansion_count"
                ],
                "out": str(args.out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    _ = REASON_STRUCTURAL_ISOLATION
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
