"""V0.9 evidence: persist the compiled CASE001 source-form plan.

QA/debug artifact only.  Production never reads this file back.  The plan is
read from the *current build's* generation report, so the artifact always
describes the build it was taken from and never a stale run.

Usage::

    .venv/Scripts/python.exe scripts/v09_write_source_form_plan.py \
        --report acceptance/workspace/case_001/<build>/generation_report.json \
        --out acceptance/reports/v09_internal_preview/source_form_plan_case001.json
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

P3_ORDER = ["P42-R%d" % index for index in range(1, 9)]


def build_artifact(report: dict, report_path: Path) -> dict:
    registry = report.get("source_rule_registry") or []
    by_id = {entry["source_rule_id"]: entry for entry in registry}
    compiled = {
        record["source_rule_id"]: record
        for record in report.get("source_form_field_plans") or []
    }

    def rule_plan(rule_id: str) -> dict:
        entry = by_id.get(rule_id, {})
        plan = compiled.get(rule_id, {})
        return {
            "source_rule_id": rule_id,
            "source_page": entry.get("source_page"),
            "source_x0": entry.get("x0"),
            "source_x1": entry.get("x1"),
            "source_y": entry.get("y"),
            "authoritative_slot_id": entry.get("authoritative_slot_id"),
            "authoritative_slot_binding": entry.get("authoritative_slot_binding"),
            "allowed_fact_fields": entry.get("allowed_fact_fields"),
            "resolved_fact_fields": entry.get("resolved_fact_fields"),
            "transformation_policy": plan.get("transformation_policy"),
            "planned_fact_fields": plan.get("planned_fact_fields"),
            "registry_transformation_policy": entry.get("transformation_policy"),
            "geometry_intent": entry.get("geometry_intent"),
        }

    rows = [rule_plan(rule_id) for rule_id in P3_ORDER]
    owners = report.get("source_form_execution_owners") or []
    applications = report.get("source_fill_applications") or []
    value_runs = report.get("source_form_line_value_runs") or []

    def execution_for(rule_id: str) -> dict | None:
        owner = next(
            (item for item in owners if rule_id in (item.get("source_rule_ids") or ())),
            None,
        )
        application = next(
            (
                item
                for item in applications
                if rule_id in (item.get("source_rule_ids") or ())
            ),
            None,
        )
        run = next(
            (item for item in value_runs if item.get("source_rule_id") == rule_id), None
        )
        if owner is None and application is None and run is None:
            return None
        return {
            "execution_owner_id": (owner or {}).get("source_form_field_id"),
            "owner_kind": (owner or {}).get("owner_kind"),
            "representation_type": (owner or {}).get("representation_type"),
            "eligible_for_value_emission": (owner or {}).get(
                "eligible_for_value_emission"
            ),
            "application_id": (application or {}).get("application_id"),
            "application_kind": (application or {}).get("application_kind"),
            "emitted_values": list((application or {}).get("resolved_values") or ()),
            "emitted_fact_fields": list((application or {}).get("fact_fields") or ()),
            "anchor_mechanism": (run or {}).get("anchor_mechanism"),
            "geometry_intent": (run or {}).get("geometry_intent"),
        }

    return {
        "artifact": "source_form_plan_case001",
        "purpose": "QA/debug output only; production must not read this file",
        "compiled_from": "document-wide pre-render source-form compiler",
        "source_report": str(report_path),
        "source_report_sha256": hashlib.sha256(
            Path(report_path).read_bytes()
        ).hexdigest(),
        "p3_planned_scope": P3_ORDER,
        "p3_rule_plans": [
            row | {"execution": execution_for(row["source_rule_id"])} for row in rows
        ],
        "document_wide_rule_plans": [
            {
                "source_rule_id": record["source_rule_id"],
                "source_page": record.get("source_page"),
                "transformation_policy": record.get("transformation_policy"),
                "planned_fact_fields": record.get("planned_fact_fields"),
                "geometry_intent": (
                    (by_id.get(record["source_rule_id"]) or {}).get("geometry_intent")
                ),
                "has_execution_owner": any(
                    record["source_rule_id"] in (owner.get("source_rule_ids") or ())
                    for owner in owners
                ),
            }
            for record in report.get("source_form_field_plans") or []
            if record["source_rule_id"] not in P3_ORDER
        ],
        "counts": {
            "source_rules_total": len(registry),
            "p3_rules": len(P3_ORDER),
            "compiled_field_plans": len(compiled),
            "document_wide_rule_plans": sum(
                1
                for record in report.get("source_form_field_plans") or []
                if record["source_rule_id"] not in P3_ORDER
            ),
            "execution_owners": len(owners),
            "value_applications": len(
                [
                    item
                    for item in applications
                    if item.get("application_kind") == "VALUE_IN_FIXED_SLOT"
                ]
            ),
        },
        "p3_policy_pass_count": sum(
            1
            for row in rows
            if row["transformation_policy"] not in (None, "UNRESOLVED")
        ),
        "persisted_evidence": [
            "compiled per-rule transformation policy and planned fact fields",
            "registry authoritative slot binding",
            "execution owner that emitted each field",
            "SourceFillApplication execution provenance",
            "emission mechanism and geometry intent for owner-driven values",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    artifact = build_artifact(report, args.report)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "counts": artifact["counts"],
                "p3_policy_pass_count": artifact["p3_policy_pass_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
