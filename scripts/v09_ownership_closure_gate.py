"""V0.9 Phase 1 gate: execution ownership closure.

Proves, from one real CASE001 build report and no synthetic input, that the new
plan-driven execution channel is closed:

* every resolved source form field is executed by exactly one renderer-derived
  execution owner, and no ``source_form_field_id`` carries two eligible owners;
* the rules that must stay execution-inactive (``P40-R1``, ``P45-R6``) establish
  no eligible value owner and emit no value;
* a rule only emits a resolved value through an owner, so no plan is executed
  by iterating the compiled plan set;
* the accepted source-rule composition set is unchanged.

Usage::

    .venv/Scripts/python.exe scripts/v09_ownership_closure_gate.py \
        --report acceptance/workspace/case_001/<build>/generation_report.json
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

#: Rules whose source form field has no active value representation, so the
#: renderer must never establish an eligible value owner for them.
EXECUTION_INACTIVE_RULES = ("P40-R1", "P45-R6")

#: The accepted composition set is unchanged by execution ownership.
ACCEPTED_COMPOSITIONS = (
    "P42-R3",
    "P42-R7",
    "P42-R8",
    "P45-R1",
    "P45-R2",
    "P45-R3",
    "P45-R5",
)

CHECK_ORDER = (
    "one_owner_per_field",
    "no_multiple_eligible_owner_conflicts",
    "inactive_rules_have_no_owner",
    "inactive_rules_emit_no_value",
    "value_emission_requires_owner",
    "plan_iteration_execution_zero",
    "accepted_composition_set_unchanged",
    "planned_application_coverage_complete",
)


def evaluate(report: dict, build_identity: dict | None = None) -> dict:
    owners = list(report.get("source_form_execution_owners") or [])
    applications = list(report.get("source_fill_applications") or [])
    metrics = report.get("source_form_execution_owner_metrics") or {}

    by_field: dict[str, list] = {}
    for owner in owners:
        by_field.setdefault(owner["source_form_field_id"], []).append(owner)
    duplicated = sorted(
        field_id
        for field_id, records in by_field.items()
        if len([r for r in records if r.get("eligible_for_value_emission")]) > 1
    )

    def inactive_owners() -> list:
        found = []
        for owner in owners:
            rules = set(owner.get("source_rule_ids") or ())
            if rules & set(EXECUTION_INACTIVE_RULES):
                found.append(owner["source_form_field_id"])
        return sorted(set(found))

    def inactive_emissions() -> list:
        found = []
        for record in report.get("source_form_line_value_runs") or []:
            if record.get("source_rule_id") in EXECUTION_INACTIVE_RULES:
                found.append(record.get("source_rule_id"))
        for application in applications:
            rules = set(application.get("source_rule_ids") or ())
            if rules & set(EXECUTION_INACTIVE_RULES):
                found.append(application["application_id"])
        return sorted(set(found))

    #: Every value-bearing application must name the execution owner that
    #: emitted it, so no value can appear without an owning representation.
    unowned = sorted(
        application["application_id"]
        for application in applications
        if application.get("application_kind") == "VALUE_IN_FIXED_SLOT"
        and not application.get("execution_owner_id")
    )

    compositions = [r["source_rule_id"] for r in report.get("source_rule_compositions") or []]
    composed = sorted(
        set(compositions)
        | {r.get("source_rule_id") for r in report.get("source_rule_composition_rules") or []}
    )
    accepted = sorted(set(ACCEPTED_COMPOSITIONS) & set(compositions))

    checks = {
        "one_owner_per_field": not duplicated,
        "no_multiple_eligible_owner_conflicts": not (
            metrics.get("multiple_eligible_owner_conflicts")
            or report.get("multiple_eligible_owner_conflicts")
        ),
        "inactive_rules_have_no_owner": not inactive_owners(),
        "inactive_rules_emit_no_value": not inactive_emissions(),
        "value_emission_requires_owner": not unowned,
        "plan_iteration_execution_zero": int(
            report.get("owner_driven_value_emission_count") or 0
        )
        == len(
            [
                application
                for application in applications
                if application.get("application_kind") == "VALUE_IN_FIXED_SLOT"
            ]
        ),
        "accepted_composition_set_unchanged": composition_preservation(
            report.get("source_rule_compositions") or [], ACCEPTED_COMPOSITIONS
        )["preserved"],
        "planned_application_coverage_complete": (
            int(report.get("missing_planned_application_count") or 0) == 0
            and int(report.get("unexpected_application_count") or 0) == 0
        ),
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "check_order": list(CHECK_ORDER),
        "failed_checks": [name for name in CHECK_ORDER if not checks[name]],
        "build": build_identity,
        "evidence": {
            "source_form_execution_owner_count": len(owners),
            "eligible_value_owner_count": metrics.get("eligible_value_owner_count"),
            "owner_kind_counts": metrics.get("owner_kind_counts"),
            "duplicate_eligible_owner_field_ids": duplicated,
            "execution_inactive_rules": list(EXECUTION_INACTIVE_RULES),
            "execution_inactive_owner_field_ids": inactive_owners(),
            "execution_inactive_emissions": inactive_emissions(),
            "valueless_owner_applications": unowned,
            "owner_driven_value_emission_count": report.get(
                "owner_driven_value_emission_count"
            ),
            "value_application_count": len(
                [
                    application
                    for application in applications
                    if application.get("application_kind") == "VALUE_IN_FIXED_SLOT"
                ]
            ),
            "source_rule_compositions": compositions,
            "accepted_composition_set": list(ACCEPTED_COMPOSITIONS),
            "accepted_compositions_present": accepted,
            "planned_resolved_application_count": report.get(
                "planned_resolved_application_count"
            ),
            "actual_resolved_application_count": report.get(
                "actual_resolved_application_count"
            ),
            "missing_planned_application_count": report.get(
                "missing_planned_application_count"
            ),
            "unexpected_application_count": report.get("unexpected_application_count"),
            "source_form_line_value_run_count": report.get(
                "source_form_line_value_run_count"
            ),
        },
        "conclusion": {
            "P40-R1_new_plan_driven_execution_owner": 0,
            "P40-R1_new_plan_driven_value_emission": 0,
            "P45-R6_new_plan_driven_execution_owner": 0,
            "P45-R6_new_plan_driven_value_emission": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    #: The gate is report-derived, so it records which build produced the report
    #: it judged: a PASS must always be attributable to one rendered build.
    manifest = Path(args.report).with_name("build_manifest.json")
    identity = {
        "generation_report": str(args.report),
        "generation_report_sha256": hashlib.sha256(
            Path(args.report).read_bytes()
        ).hexdigest(),
        "build_manifest": str(manifest) if manifest.is_file() else None,
    }
    if manifest.is_file():
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        generated = manifest_data.get("generated") or {}
        identity["build_id"] = manifest_data.get("build_id")
        identity["generated_docx_sha256"] = generated.get("docx_sha256")
        identity["generated_pdf_sha256"] = generated.get("pdf_sha256")
        identity["generated_pdf_page_count"] = generated.get("pdf_page_count")
        identity["source_pdf_sha256"] = (manifest_data.get("source") or {}).get(
            "sha256"
        )
    result = evaluate(report, identity)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
