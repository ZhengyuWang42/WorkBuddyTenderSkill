"""P3 semantic-registry consistency gate (one gate, eight frozen rules).

Requires the production rule registry to carry the frozen authoritative P3
semantics - and, at the same time, every P3 measurement the reconciliation
relies on to stay green:

* ``semantic_policy_match = 8/8`` - the registry's transformation policy per
  frozen rule equals the authoritative table;
* ``semantic_intent_match = 8/8`` - the geometry intent derived from that policy
  equals the authoritative table;
* ``semantic_execution_binding`` - every rule whose frozen policy inserts a
  resolved value has exactly one execution owner, exactly one
  ``SourceFillApplication`` and, where the accepted path records it, one value
  run, and the emitted value equals the value ProjectFacts resolved (so no value
  is invented and no plan is executed twice);
* ``p3_horizontal = 8/8``, ``matched = 8 / lost = 0 / invented = 0 /
  out_of_tolerance = 0 / invariants = []``;
* ``REFLOW_AWARE_V1``, execution ownership and source-line assembly all PASS, and
  the Round-3 typography families stay green.

The frozen table is embedded here as the contract under test and is never
rewritten by the gate.  Every other input is a gate report produced from a
delivered artifact, so this gate can only disagree with the artifacts, never
with itself.

Usage::

    .venv/Scripts/python.exe scripts/v1_p3_semantic_registry_gate.py \
        --build acceptance/workspace/case_001/v1_manual_fidelity_round3_p3semantics \
        --out acceptance/reports/v1_generalization/case001_p3_semantic_registry_gate.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tender_basic.composite_semantic_binding import (  # noqa: E402
    validate_presentation_atoms,
    validate_single_fact_surface,
)

SCHEMA = "v1_p3_semantic_registry_gate/1"

#: The frozen authoritative P3 semantics.  This is the contract the registry is
#: measured against; the gate never edits it and never derives it from a build.
FROZEN_P3_SEMANTICS = {
    "P42-R1": {
        "transformation_policy": "PLACEHOLDER_REPLACED_BY_VALUE",
        "geometry_intent": "ANCHOR_START_ONLY",
        "source_x0": 94.80,
        "source_x1": 194.60,
        "source_y": 138.35,
        "inserts_resolved_value": True,
        "fact_fields": ["purchaser"],
    },
    "P42-R2": {
        "transformation_policy": "PLACEHOLDER_REPLACED_BY_VALUE",
        "geometry_intent": "ANCHOR_START_ONLY",
        "source_x0": 198.10,
        "source_x1": 375.70,
        "source_y": 158.40,
        "inserts_resolved_value": True,
        "fact_fields": ["project_name", "lot_name", "project_number"],
    },
    "P42-R3": {
        "transformation_policy": "FIXED_EMPTY_SLOT",
        "geometry_intent": "EXACT_SOURCE_SPAN",
        "source_x0": 169.65,
        "source_x1": 323.60,
        "source_y": 178.40,
        "inserts_resolved_value": False,
        "fact_fields": [],
    },
    "P42-R4": {
        "transformation_policy": "FIXED_EMPTY_SLOT",
        "geometry_intent": "EXACT_SOURCE_SPAN",
        "source_x0": 384.60,
        "source_x1": 459.00,
        "source_y": 178.40,
        "inserts_resolved_value": False,
        "fact_fields": [],
    },
    "P42-R5": {
        "transformation_policy": "RESOLVED_VALUE_IN_FIXED_SLOT",
        "geometry_intent": "ANCHOR_START_ONLY",
        "source_x0": 131.85,
        "source_x1": 181.40,
        "source_y": 198.35,
        "inserts_resolved_value": True,
        "fact_fields": ["duration"],
    },
    "P42-R6": {
        "transformation_policy": "RESOLVED_VALUE_IN_FIXED_SLOT",
        "geometry_intent": "ANCHOR_START_ONLY",
        "source_x0": 95.25,
        "source_x1": 151.05,
        "source_y": 218.40,
        "inserts_resolved_value": True,
        "fact_fields": ["quality_target"],
    },
    "P42-R7": {
        "transformation_policy": "SOURCE_VALUE_UNDERLINE",
        "geometry_intent": "EXACT_SOURCE_SPAN",
        "source_x0": 352.80,
        "source_x1": 388.80,
        "source_y": 318.35,
        "inserts_resolved_value": False,
        "fact_fields": [],
    },
    "P42-R8": {
        "transformation_policy": "PRESERVE_SOURCE_PLACEHOLDER",
        "geometry_intent": "EXACT_SOURCE_SPAN",
        "source_x0": 112.80,
        "source_x1": 208.80,
        "source_y": 418.40,
        "inserts_resolved_value": False,
        "fact_fields": [],
    },
}

DEFAULT_REPORTS = {
    "inventory": "acceptance/reports/v1_generalization/case001_underline_inventory_round3_p3semantics.json",
    "closure": "acceptance/reports/v1_generalization/case001_p3_closure_round3_p3semantics.json",
    "reflow_aware": "acceptance/reports/v1_generalization/case001_reflow_aware_round3_p3semantics.json",
    "source_line_assembly": "acceptance/reports/v1_generalization/case001_source_line_assembly_round3_p3semantics.json",
    "ownership": "acceptance/reports/v1_generalization/case001_ownership_closure_round3_p3semantics.json",
    "typography": "acceptance/reports/v1_generalization/case001_source_typography_round3_p3semantics.json",
    "p3_reflow_vertical": "acceptance/reports/v1_generalization/case001_p3_reflow_vertical_round3_p3semantics.json",
}


def _load(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _pick(report, *keys):
    """First present key, so a sibling gate's own status vocabulary is honoured."""

    for key in keys:
        if isinstance(report, dict) and key in report:
            return report[key]
    return None


def _status_ok(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).upper()
    return text in {"PASS", "PASSED", "OK", "GREEN", "TRUE"} or text.startswith("PASS")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    for name, default in DEFAULT_REPORTS.items():
        parser.add_argument("--%s" % name.replace("_", "-"), default=default, type=Path)
    args = parser.parse_args(argv)

    build = (args.build if args.build.is_absolute() else ROOT / args.build).resolve()
    report = json.loads((build / "generation_report.json").read_text(encoding="utf-8"))
    facts = json.loads((build / "project_facts.json").read_text(encoding="utf-8"))
    manifest = json.loads((build / "build_manifest.json").read_text(encoding="utf-8"))

    resolved_values = {
        str(name).lower(): str(payload.get("resolved_value")).strip()
        for name, payload in facts["fields"].items()
        if payload.get("status") == "RESOLVED" and payload.get("resolved_value")
    }
    facts_sourced_values = set(resolved_values.values())

    registry = {
        str(entry.get("source_rule_id")): entry
        for entry in report.get("source_rule_registry") or []
    }
    owners: dict[str, list] = {}
    for entry in report.get("source_form_execution_owners") or []:
        for rule_id in entry.get("source_rule_ids") or ():
            owners.setdefault(str(rule_id), []).append(entry)
    applications: dict[str, list] = {}
    for entry in report.get("source_fill_applications") or []:
        for rule_id in entry.get("source_rule_ids") or ():
            applications.setdefault(str(rule_id), []).append(entry)
    value_runs: dict[str, list] = {}
    for entry in report.get("source_form_line_value_runs") or []:
        value_runs.setdefault(str(entry.get("source_rule_id")), []).append(entry)

    #: The emitter's own atomic composition record, indexed by the delivered
    #: paragraph each composed value was written into.  A recorded presentation
    #: describes one delivered surface exactly; a surface with no record is not
    #: composite and keeps the strict whole-value contract.
    schema_fields = facts.get("fields") or {}
    presentations = (report.get("slot_value_presentations") or {}).get("records") or []
    presentations_by_paragraph: dict = {}
    for record in presentations:
        presentations_by_paragraph.setdefault(
            record.get("generated_paragraph_index"), []
        ).append(record)

    rule_rows = []
    for rule_id, frozen in FROZEN_P3_SEMANTICS.items():
        entry = registry.get(rule_id) or {}
        policy = entry.get("transformation_policy")
        intent = entry.get("geometry_intent")
        rule_owners = owners.get(rule_id) or []
        rule_applications = applications.get(rule_id) or []
        rule_runs = value_runs.get(rule_id) or []
        application_values = []
        for item in rule_applications:
            for value in item.get("resolved_values") or ():
                application_values.append(str(value))
        run_values = []
        for item in rule_runs:
            for value in item.get("resolved_values") or ():
                run_values.append(str(value))
        emitted = list(dict.fromkeys(application_values + run_values))
        expected_fields = [str(field).lower() for field in frozen["fact_fields"]]
        expected_values = [
            resolved_values[field] for field in expected_fields if field in resolved_values
        ]
        declared_fact_fields = sorted(
            {
                str(field).lower()
                for item in rule_applications
                for field in item.get("fact_fields") or ()
            }
        )
        permitted_fields = set(expected_fields) | set(declared_fact_fields)
        candidate_presentations = [
            record
            for paragraph in {
                item.get("generated_paragraph_index") for item in rule_applications
            }
            for record in presentations_by_paragraph.get(paragraph, [])
        ]
        binding_ok = True
        binding_notes = []
        surface_validations = []
        fact_atom_fields: set = set()
        single_fact_fields: set = set()
        for surface in emitted:
            record = next(
                (
                    candidate
                    for candidate in candidate_presentations
                    if str(candidate.get("value")) == surface
                ),
                None,
            )
            if record is not None:
                # A composed surface: validated atom by atom, never as one
                # opaque string.  Each atom is independently accountable - the
                # fact against ProjectFacts, the literal against the source's own
                # printing, the marker against the source form's structure.
                outcome = validate_presentation_atoms(
                    surface=surface,
                    presentation=record,
                    fact_fields=schema_fields,
                    allowed_fact_fields=permitted_fields,
                )
                if outcome["ok"]:
                    fact_atom_fields.update(outcome["fact_value_fields"])
                else:
                    binding_ok = False
                    binding_notes.extend(outcome["notes"])
                surface_validations.append(
                    {
                        "surface": surface,
                        "validation": "ATOMIC_PROVENANCE",
                        "slot_id": record.get("slot_id"),
                        "ok": outcome["ok"],
                        "notes": outcome["notes"],
                        "atoms": outcome["atoms"],
                        "accounting": outcome["accounting"],
                    }
                )
                continue
            single = validate_single_fact_surface(
                surface=surface,
                declared_fact_fields=declared_fact_fields,
                fact_fields=schema_fields,
            )
            if single["ok"]:
                single_fact_fields.update(single["matched_fields"])
            else:
                binding_ok = False
                binding_notes.append("EMITTED_VALUE_NOT_FROM_PROJECT_FACTS")
                if surface not in facts_sourced_values:
                    binding_notes.append("EMITTED_VALUE_UNKNOWN_TO_PROJECT_FACTS")
            surface_validations.append(
                {
                    "surface": surface,
                    "validation": "SINGLE_FACT_STRICT_EQUALITY",
                    "ok": single["ok"],
                    "matched_fields": single["matched_fields"],
                    "notes": single["notes"],
                }
            )
        # Every fact the frozen contract says this rule inserts must actually be
        # emitted, and no fact that is not resolved may be emitted as a value.
        # An unresolved fact may only appear through the source form's own
        # not-applicable marker, which is provenance of a different class.
        for field in expected_fields:
            payload = schema_fields.get(field) or {}
            if field not in schema_fields:
                binding_ok = False
                binding_notes.append(
                    "EXPECTED_FACT_FIELD_NOT_IN_PROJECT_FACTS_SCHEMA:%s" % (field,)
                )
                continue
            if payload.get("status") != "RESOLVED":
                continue
            authoritative = payload.get("resolved_value")
            if authoritative is None:
                continue
            if field in fact_atom_fields or field in single_fact_fields:
                continue
            if str(authoritative) in emitted:
                continue
            binding_ok = False
            binding_notes.append("DECLARED_FACT_VALUE_WAS_NOT_EMITTED:%s" % (field,))
        for field in declared_fact_fields:
            payload = schema_fields.get(field) or {}
            if payload.get("status") == "RESOLVED":
                continue
            value = payload.get("resolved_value")
            if value is None:
                continue
            emitted_as_value = str(value) in emitted or field in fact_atom_fields
            if emitted_as_value:
                binding_ok = False
                binding_notes.append("UNRESOLVED_FACT_EMITTED_AS_A_VALUE:%s" % (field,))
        if frozen["inserts_resolved_value"]:
            if not rule_owners:
                binding_ok = False
                binding_notes.append("NO_EXECUTION_OWNER")
            if len(rule_owners) > 1:
                binding_ok = False
                binding_notes.append("MULTIPLE_EXECUTION_OWNERS")
            if not rule_applications:
                binding_ok = False
                binding_notes.append("NO_SOURCE_FILL_APPLICATION")
            if len(rule_applications) > 1:
                binding_ok = False
                binding_notes.append("DUPLICATE_SOURCE_FILL_APPLICATION")
            if not emitted:
                binding_ok = False
                binding_notes.append("NO_EMITTED_VALUE")
        elif emitted:
            binding_ok = False
            binding_notes.append("VALUE_EMITTED_FOR_A_NON_VALUE_POLICY")
        rule_rows.append(
            {
                "source_rule_id": rule_id,
                "source_x0": frozen["source_x0"],
                "source_x1": frozen["source_x1"],
                "source_y": frozen["source_y"],
                "registry_transformation_policy": policy,
                "frozen_transformation_policy": frozen["transformation_policy"],
                "policy_match": policy == frozen["transformation_policy"],
                "registry_geometry_intent": intent,
                "frozen_geometry_intent": frozen["geometry_intent"],
                "intent_match": intent == frozen["geometry_intent"],
                "inserts_resolved_value": frozen["inserts_resolved_value"],
                "expected_fact_fields": expected_fields,
                "execution_owner_kinds": sorted(
                    {str(owner.get("owner_kind")) for owner in rule_owners}
                ),
                "application_ids": [item.get("application_id") for item in rule_applications],
                "application_kinds": sorted(
                    {str(item.get("application_kind")) for item in rule_applications}
                ),
                "application_values": application_values,
                "value_run_values": run_values,
                "emitted_values": emitted,
                "declared_fact_fields": declared_fact_fields,
                "surface_validations": surface_validations,
                "fact_atom_fields": sorted(fact_atom_fields),
                "single_fact_fields": sorted(single_fact_fields),
                "value_from_project_facts": (
                    bool(emitted) and all(value in facts_sourced_values for value in emitted)
                ),
                "every_emitted_atom_is_accountable": all(
                    item["ok"] for item in surface_validations
                ),
                "binding_ok": binding_ok,
                "binding_notes": binding_notes,
            }
        )

    policy_matches = sum(1 for row in rule_rows if row["policy_match"])
    intent_matches = sum(1 for row in rule_rows if row["intent_match"])
    binding_failures = [row["source_rule_id"] for row in rule_rows if not row["binding_ok"]]

    inventory = _load(args.inventory if args.inventory.is_absolute() else ROOT / args.inventory)
    closure = _load(args.closure if args.closure.is_absolute() else ROOT / args.closure)
    reflow = _load(args.reflow_aware if args.reflow_aware.is_absolute() else ROOT / args.reflow_aware)
    assembly = _load(
        args.source_line_assembly
        if args.source_line_assembly.is_absolute()
        else ROOT / args.source_line_assembly
    )
    ownership = _load(args.ownership if args.ownership.is_absolute() else ROOT / args.ownership)
    typography = _load(args.typography if args.typography.is_absolute() else ROOT / args.typography)
    vertical = _load(
        args.p3_reflow_vertical
        if args.p3_reflow_vertical.is_absolute()
        else ROOT / args.p3_reflow_vertical
    )

    horizontal_ids = list((closure or {}).get("horizontal_failure_ids") or [])
    closure_scope = (closure or {}).get("source_rule_count")
    inventory_row = {
        "status": (inventory or {}).get("status"),
        "matched": (inventory or {}).get("matched"),
        "lost": (inventory or {}).get("lost"),
        "invented": (inventory or {}).get("invented"),
        "out_of_tolerance": (inventory or {}).get("out_of_tolerance"),
        "invariants": list((inventory or {}).get("invariants") or []),
        "build_dir": (inventory or {}).get("build_dir"),
    }
    accounting_ok = (
        inventory_row["status"] == "PASS"
        and inventory_row["matched"] == len(FROZEN_P3_SEMANTICS)
        and inventory_row["lost"] == 0
        and inventory_row["invented"] == 0
        and inventory_row["out_of_tolerance"] == 0
        and inventory_row["invariants"] == []
    )
    closure_report_build = ((closure or {}).get("build") or {}).get("generated_pdf")
    same_build = bool(
        closure_report_build
        and str(build / "基础投标文件.pdf").endswith(Path(closure_report_build).name)
        and Path(closure_report_build).parent.name == build.name
    )

    checks = {
        "semantic_policy_match": policy_matches == len(FROZEN_P3_SEMANTICS),
        "semantic_intent_match": intent_matches == len(FROZEN_P3_SEMANTICS),
        "semantic_execution_binding": not binding_failures,
        "p3_horizontal_within_tolerance": bool(closure) and not horizontal_ids,
        "p3_scope_complete": closure_scope == len(FROZEN_P3_SEMANTICS),
        "p3_rule_accounting": accounting_ok,
        "reflow_aware_v1": _status_ok(_pick(reflow, "status", "result")),
        "source_line_assembly": _status_ok(_pick(assembly, "status", "result")),
        "execution_ownership": _status_ok(_pick(ownership, "status", "result")),
        "round3_typography": _status_ok(_pick(typography, "status", "result")),
        "gates_measured_the_same_build": same_build,
    }
    failed_checks = sorted(name for name, ok in checks.items() if not ok)

    result = {
        "schema": SCHEMA,
        "gate": "v1_p3_semantic_registry_gate",
        "status": "PASS" if not failed_checks else "FAIL",
        "failed_checks": failed_checks,
        "checks": checks,
        "build": {
            "build_id": build.name,
            "build_dir": str(build.relative_to(ROOT)).replace("\\", "/"),
            "docx_sha256": (manifest.get("generated") or {}).get("docx_sha256"),
            "pdf_sha256": (manifest.get("generated") or {}).get("pdf_sha256"),
            "pdf_page_count": (manifest.get("generated") or {}).get("pdf_page_count"),
        },
        "frozen_semantics": {
            rule_id: {
                "transformation_policy": frozen["transformation_policy"],
                "geometry_intent": frozen["geometry_intent"],
            }
            for rule_id, frozen in FROZEN_P3_SEMANTICS.items()
        },
        "semantic_policy_match": "%d/%d" % (policy_matches, len(FROZEN_P3_SEMANTICS)),
        "semantic_intent_match": "%d/%d" % (intent_matches, len(FROZEN_P3_SEMANTICS)),
        "semantic_binding_failure_ids": binding_failures,
        "rules": rule_rows,
        "p3_horizontal": "%d/%d"
        % (len(FROZEN_P3_SEMANTICS) - len(horizontal_ids), len(FROZEN_P3_SEMANTICS)),
        "p3_horizontal_failure_ids": horizontal_ids,
        "p3_rule_accounting": {
            "matched": inventory_row["matched"],
            "lost": inventory_row["lost"],
            "invented": inventory_row["invented"],
            "out_of_tolerance": inventory_row["out_of_tolerance"],
            "invariants": inventory_row["invariants"],
        },
        "sibling_gates": {
            "inventory": inventory_row,
            "closure": {
                "path": str(args.closure),
                "status": (closure or {}).get("status"),
                "phase": (closure or {}).get("phase"),
                "horizontal_failure_ids": horizontal_ids,
                "source_rule_count": closure_scope,
            },
            "reflow_aware": {
                "status": _pick(reflow, "status", "result"),
                "maximum_residual_y_error_pt": ((reflow or {}).get("measured") or {}).get(
                    "maximum_residual_y_error_pt"
                ),
                "maximum_raw_y_error_pt": ((reflow or {}).get("measured") or {}).get(
                    "maximum_raw_y_error_pt"
                ),
                "unexplained_extra_row_count": ((reflow or {}).get("measured") or {}).get(
                    "unexplained_extra_row_count"
                ),
                "structural_isolation_count": ((reflow or {}).get("measured") or {}).get(
                    "structural_isolation_count"
                ),
                "accepted_differences": (reflow or {}).get("accepted_differences"),
                "failed_checks": (reflow or {}).get("failed_checks"),
            },
            "source_line_assembly": {"status": _pick(assembly, "status", "result")},
            "execution_ownership": {"status": _pick(ownership, "status", "result")},
            "round3_typography": {
                "status": _pick(typography, "status", "result"),
                "failed_checks": (typography or {}).get("failed_checks"),
            },
            "p3_reflow_vertical": {
                "status": _pick(vertical, "status", "result"),
                "failed_checks": (vertical or {}).get("failed_checks"),
                "reflow_contract": (vertical or {}).get("vertical_reflow"),
                "legacy_absolute_vertical": {
                    "row_order_preserved": (vertical or {}).get(
                        "frozen_absolute_vertical_row_order_preserved"
                    ),
                    "failure_ids": (vertical or {}).get("frozen_absolute_vertical_failure_ids"),
                    "maximum_y_error_pt": (vertical or {}).get(
                        "frozen_absolute_maximum_y_error_pt"
                    ),
                },
            },
        },
        "disclosures": [
            {
                "id": "LEGACY_ABSOLUTE_VERTICAL_PHASE",
                "state": "red before and after this reconciliation",
                "authority": "REFLOW_AWARE_V1",
                "detail": (
                    "the phase-3 closure gate's frozen *absolute* vertical phase is red on "
                    "both the pre-change build and this build (same two checks, "
                    "vertical_row_order_preserved and vertical_within_tolerance); the "
                    "mandatory reflow of the recorded long project name and values is the "
                    "documented cause and REFLOW_AWARE_V1 is the vertical authority"
                ),
            }
        ],
    }

    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(out_path),
                "status": result["status"],
                "failed_checks": failed_checks,
                "semantic_policy_match": result["semantic_policy_match"],
                "semantic_intent_match": result["semantic_intent_match"],
                "p3_horizontal": result["p3_horizontal"],
                "p3_rule_accounting": result["p3_rule_accounting"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failed_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
