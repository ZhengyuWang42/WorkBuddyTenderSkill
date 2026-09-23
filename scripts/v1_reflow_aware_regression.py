"""The ``REFLOW_AWARE_V1`` region contract, measured without the frozen phase.

``v09_p3_reflow_vertical_gate.py`` reports the reflow-aware contract *beside* the
frozen absolute one, and it evaluates the frozen phase first.  The frozen phase
currently raises before it returns a verdict on the accepted baseline
(``v09_p3_closure_gate.evaluate_frozen_phase`` reduces over an empty measured-row
list for phase 3), so the wrapper gate cannot reach the contract it exists to
report.

This script measures the reflow-aware contract directly and compares it against a
baseline build.  It replaces no gate: the frozen phase's verdict is not produced
here and is not claimed.  What it does assert is that the region's delivered
vertical geometry still satisfies ``REFLOW_AWARE_V1`` under the same unrelaxed
2.0pt tolerance, and that this build's region ledger is identical to the
baseline's - so a change elsewhere in the pipeline cannot quietly move the
accepted region while the wrapper gate is unavailable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import pymupdf  # noqa: E402

from v09_p3_reflow_vertical_gate import (  # noqa: E402
    P3_GENERATED_PAGE,
    P3_REGION_RULE_IDS,
    P3_SOURCE_PAGE,
    build_region_reflow_plan,
)

SCHEMA = "v1_reflow_aware_regression/1"


def _measure(build: Path, source_pdf: Path) -> dict:
    report = json.loads((build / "generation_report.json").read_text(encoding="utf-8"))
    source_doc = pymupdf.open(source_pdf)
    generated_doc = pymupdf.open(build / "基础投标文件.pdf")
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
    plans = [plan.to_dict() for plan in region["_plans"]]
    failure_ids = [row["source_visual_line_id"] for row in plans if not row["pass"]]
    return {
        "vertical_contract_version": region["vertical_contract_version"],
        "tolerance_pt": region["tolerance_pt"],
        "maximum_residual_y_error_pt": region["maximum_residual_y_error_pt"],
        "maximum_raw_y_error_pt": region["maximum_raw_y_error_pt"],
        "row_accounting": region["row_accounting"],
        "generated_row_order_preserved": region["generated_row_order_preserved"],
        "unexplained_extra_row_count": region["unexplained_extra_row_count"],
        "unexplained_blank_row_gaps": list(region["unexplained_blank_row_gaps"]),
        "structural_isolation_count": len(region["structural_isolations"]),
        "applicable_line_pitch_pt": region["applicable_line_pitch_pt"],
        "source_line_pitch_pt": region["source_line_pitch_pt"],
        "region_left_pt": region["region_left_pt"],
        "plan_count": len(plans),
        "reflow_vertical_failure_ids": failure_ids,
        "plan_verdicts": [
            {"source_visual_line_id": row["source_visual_line_id"], "pass": row["pass"]}
            for row in plans
        ],
    }


def evaluate(
    build: Path,
    baseline: Path,
    source_pdf: Path,
    accept_ledger_change: str | None = None,
) -> dict:
    build = Path(build)
    current = _measure(build, source_pdf)
    baseline_measurement = _measure(Path(baseline), source_pdf)
    checks = {
        "reflow_aware_contract_is_v1": (
            current["vertical_contract_version"] == baseline_measurement["vertical_contract_version"]
            == "REFLOW_AWARE_V1"
        ),
        "region_row_budget_is_accounted": bool(current["row_accounting"]["rows_accounted"]),
        "no_unexplained_extra_row": current["unexplained_extra_row_count"] == 0,
        "no_unexplained_blank_row": not current["unexplained_blank_row_gaps"],
        "generated_row_order_is_preserved": bool(current["generated_row_order_preserved"]),
        "every_region_row_passes": not current["reflow_vertical_failure_ids"],
        "residual_within_the_unrelaxed_tolerance": (
            current["maximum_residual_y_error_pt"] <= current["tolerance_pt"]
        ),
        "tolerance_is_not_relaxed": current["tolerance_pt"] == baseline_measurement["tolerance_pt"],
        "region_ledger_matches_the_baseline": (
            current["plan_verdicts"] == baseline_measurement["plan_verdicts"]
            and current["maximum_residual_y_error_pt"]
            == baseline_measurement["maximum_residual_y_error_pt"]
            and current["maximum_raw_y_error_pt"] == baseline_measurement["maximum_raw_y_error_pt"]
            and current["row_accounting"] == baseline_measurement["row_accounting"]
        ),
    }

    #: A difference the review itself asked for is *disclosed*, never silent: the
    #: raw comparison stays in ``checks`` exactly as measured, the difference is
    #: named with its cause and figures, and the verdict counts it as accepted.
    accepted: list[dict] = []
    if accept_ledger_change and not checks["region_ledger_matches_the_baseline"]:
        accepted.append(
            {
                "check": "region_ledger_matches_the_baseline",
                "reason": accept_ledger_change,
                "baseline_build": str(baseline),
                "differences": _ledger_differences(current, baseline_measurement),
            }
        )
    accepted_checks = {item["check"] for item in accepted}
    failed = sorted(
        name
        for name, passed in checks.items()
        if not passed and name not in accepted_checks
    )
    return {
        "schema": SCHEMA,
        "gate": "v1_reflow_aware_regression",
        "used_by": "v09_p3_reflow_vertical_gate.REFLOW_AWARE_V1",
        "build_dir": str(build),
        "baseline_build_dir": str(baseline),
        "source_pdf": str(source_pdf),
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "accepted_differences": accepted,
        "failed_checks": failed,
        "measured": current,
        "baseline_measured": baseline_measurement,
        "frozen_phase": {
            "available": False,
            "reason": (
                "v09_p3_closure_gate.evaluate_frozen_phase raises ValueError for phase 3 "
                "on the accepted baseline as well as on this build, so the wrapper gate "
                "v09_p3_reflow_vertical_gate.py cannot return a verdict; the frozen "
                "phase is neither claimed nor relaxed here"
            ),
        },
    }


def _ledger_differences(current: dict, baseline: dict) -> dict:
    """The measured ledger difference, row by row, for the disclosure."""

    current_rows = {row["source_visual_line_id"]: row["pass"] for row in current["plan_verdicts"]}
    baseline_rows = {
        row["source_visual_line_id"]: row["pass"] for row in baseline["plan_verdicts"]
    }
    return {
        "row_accounting": {
            "current": current["row_accounting"],
            "baseline": baseline["row_accounting"],
        },
        "maximum_residual_y_error_pt": {
            "current": current["maximum_residual_y_error_pt"],
            "baseline": baseline["maximum_residual_y_error_pt"],
        },
        "maximum_raw_y_error_pt": {
            "current": current["maximum_raw_y_error_pt"],
            "baseline": baseline["maximum_raw_y_error_pt"],
        },
        "rows_with_a_changed_verdict": sorted(
            row_id
            for row_id in set(current_rows) | set(baseline_rows)
            if current_rows.get(row_id) != baseline_rows.get(row_id)
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--baseline-build", required=True, type=Path)
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--accept-ledger-change",
        default=None,
        help=(
            "reason this build's region ledger may differ from the baseline's; the raw "
            "comparison is still reported, and the difference is recorded in the report"
        ),
    )
    args = parser.parse_args(argv)

    report = evaluate(
        args.build, args.baseline_build, args.source_pdf, args.accept_ledger_change
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "reflow-aware: status=%s residual=%s tolerance=%s plans=%s failed=%s accepted=%s"
        % (
            report["status"],
            report["measured"]["maximum_residual_y_error_pt"],
            report["measured"]["tolerance_pt"],
            report["measured"]["plan_count"],
            report["failed_checks"],
            [item["check"] for item in report["accepted_differences"]],
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
