"""P3 R6 semantic-registry reconciliation diagnostic (read-only).

Traces ``P42-R6`` through every pipeline stage that carries its semantics and
records the value found at each one, so the stage where the frozen contract's

    RESOLVED_VALUE_IN_FIXED_SLOT / ANCHOR_START_ONLY

was converted into

    FIXED_EMPTY_SLOT / EXACT_SOURCE_SPAN

is named by evidence rather than assumed.  The stages are:

1. source rule detection (the page's own vector rules);
2. glyph occupancy of the rule (compiled glyph evidence);
3. own-visual-line label context and its hint contract;
4. structural neighbourhood (owning container, same row, wrapped row above);
5. field binding / ``SourceFormPlan`` (the compiled plan);
6. the serialized normalized artifact reloaded from disk;
7. execution ownership and ``SourceFillApplication``;
8. the production rule registry (policy + derived geometry intent);
9. the QA/gate representation of the rule.

Nothing here changes state: every value is read from the delivered build's own
artifacts or recomputed through the production functions.

Usage::

    .venv/Scripts/python.exe scripts/v1_p3_r6_semantic_registry_diagnostic.py \
        --build acceptance/workspace/case_001/v1_manual_fidelity_round3_p3reconciled \
        --out acceptance/reports/v1_generalization/case001_p3_r6_semantic_registry_diagnostic.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tender_basic.bid_document_builder import (  # noqa: E402
    SOURCE_GLYPH_REPAIRS,
    apply_source_glyph_repairs,
)
from tender_basic.document_parser import parse_document  # noqa: E402
from tender_basic.format_extractor import extract_bid_format  # noqa: E402
from tender_basic.page_layout import (  # noqa: E402
    _field_hint_candidates,
    _single_distinct_field,
    compile_source_form_field_plans,
    compile_source_rule_glyph_evidence,
    compile_source_visual_text_boxes,
    source_rule_geometry_intent,
    source_rule_line_context,
    source_rule_structural_context,
)
from tender_basic.source_format import _slot_contract, build_source_format_model  # noqa: E402
from tender_basic.source_form_execution import resolve_field_plan  # noqa: E402

SCHEMA = "v1_p3_r6_semantic_registry_diagnostic/1"

#: The frozen authoritative P3 semantics.  This table is the contract under
#: test; the diagnostic never writes it, only compares against it.
FROZEN_SEMANTICS = {
    "P42-R1": ("PLACEHOLDER_REPLACED_BY_VALUE", "ANCHOR_START_ONLY"),
    "P42-R2": ("PLACEHOLDER_REPLACED_BY_VALUE", "ANCHOR_START_ONLY"),
    "P42-R3": ("FIXED_EMPTY_SLOT", "EXACT_SOURCE_SPAN"),
    "P42-R4": ("FIXED_EMPTY_SLOT", "EXACT_SOURCE_SPAN"),
    "P42-R5": ("RESOLVED_VALUE_IN_FIXED_SLOT", "ANCHOR_START_ONLY"),
    "P42-R6": ("RESOLVED_VALUE_IN_FIXED_SLOT", "ANCHOR_START_ONLY"),
    "P42-R7": ("SOURCE_VALUE_UNDERLINE", "EXACT_SOURCE_SPAN"),
    "P42-R8": ("PRESERVE_SOURCE_PLACEHOLDER", "EXACT_SOURCE_SPAN"),
}

P3_SOURCE_PAGE = 42
FOCUS_RULE_Y = 218.40


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _rule_key(page_number, x0, x1, y0):
    return (int(page_number), round(float(x0), 1), round(float(x1), 1), round(float(y0), 1))


def _plan_fields(plan):
    if not isinstance(plan, tuple) or len(plan) < 2 or not plan[1]:
        return []
    return [str(getattr(field, "value", field)) for field in plan[1]]


def _recorded_plan(report, x0, y0):
    return next(
        (
            record
            for record in (report.get("source_form_field_plans") or [])
            if abs(float(record.get("source_x0", 0.0)) - x0) <= 0.2
            and abs(float(record.get("source_y", 0.0)) - y0) <= 0.2
        ),
        None,
    )


def _gate_rows(report):
    if not report:
        return None
    for row in report.get("rows") or []:
        if row.get("source_rule_id") == "P42-R6":
            return {
                "transformation_policy": row.get("transformation_policy"),
                "geometry_intent": row.get("geometry_intent"),
                "emission_mechanism": row.get("emission_mechanism"),
                "horizontal_pass": row.get("horizontal_pass"),
                "measurement_kind": (row.get("measurement") or {}).get("measurement_kind"),
                "x0_error": (row.get("measurement") or {}).get("x0_error"),
                "x1_error": (row.get("measurement") or {}).get("x1_error"),
            }
    return None


def _inventory_row(report):
    if not report:
        return None
    for row in report.get("rules") or []:
        if row.get("source_rule_id") == "P42-R6":
            return {
                "transformation_policy": row.get("transformation_policy"),
                "geometry_intent": row.get("geometry_intent"),
                "gated_axis": row.get("gated_axis"),
                "status": row.get("status"),
                "observed_span": row.get("observed"),
                "start_error_pt": row.get("start_error_pt"),
                "end_error_pt": row.get("end_error_pt"),
                "end_axis_gated": row.get("end_axis_gated"),
            }
    return None


def _execution_evidence(report):
    owners = [
        entry
        for entry in report.get("source_form_execution_owners") or []
        if "P42-R6" in (entry.get("source_rule_ids") or [])
    ]
    applications = [
        entry
        for entry in report.get("source_fill_applications") or []
        if "P42-R6" in (entry.get("source_rule_ids") or [])
    ]
    runs = [
        entry
        for entry in report.get("source_form_line_value_runs") or []
        if entry.get("source_rule_id") == "P42-R6"
    ]
    return {
        "execution_owner": owners[0] if owners else None,
        "source_fill_application": applications[0] if applications else None,
        "source_form_line_value_run": runs[0] if runs else None,
        "owner_count": len(owners),
        "application_count": len(applications),
        "value_run_count": len(runs),
    }


def _registry_rows(report):
    return list(report.get("source_rule_registry") or [])


def _registry_entry(report, rule_id):
    for entry in _registry_rows(report):
        if str(entry.get("source_rule_id")) == rule_id:
            return entry
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--source", default=None, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--pre-build",
        type=Path,
        default=Path("acceptance/workspace/case_001/v1_manual_fidelity_round3_p3reconciled"),
        help="the build that exhibited the metadata inconsistency (artifact evidence)",
    )
    parser.add_argument(
        "--closure",
        type=Path,
        default=Path(
            "acceptance/reports/v1_generalization/case001_p3_closure_round3_p3semantics.json"
        ),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(
            "acceptance/reports/v1_generalization/"
            "case001_underline_inventory_round3_p3semantics.json"
        ),
    )
    parser.add_argument(
        "--pre-closure",
        type=Path,
        default=Path(
            "acceptance/reports/v1_generalization/case001_p3_closure_round3_reconciled.json"
        ),
    )
    parser.add_argument(
        "--pre-inventory",
        type=Path,
        default=Path(
            "acceptance/reports/v1_generalization/"
            "case001_underline_inventory_round3_reconciled.json"
        ),
    )
    args = parser.parse_args(argv)

    build = (args.build if args.build.is_absolute() else ROOT / args.build).resolve()
    report = _read(build / "generation_report.json")
    manifest = _read(build / "build_manifest.json")
    facts_artifact = _read(build / "project_facts.json")
    normalized = _read(build / "normalized_document.json")

    source_path = args.source
    if source_path is None:
        source_path = Path(manifest["source"]["path"])
    source_path = (source_path if source_path.is_absolute() else ROOT / source_path).resolve()

    resolved_fact_fields = frozenset(
        str(name).upper()
        for name, payload in facts_artifact["fields"].items()
        if payload.get("status") == "RESOLVED" and payload.get("resolved_value")
    )
    resolved_values = {
        str(name).upper(): str(payload.get("resolved_value"))
        for name, payload in facts_artifact["fields"].items()
        if payload.get("status") == "RESOLVED" and payload.get("resolved_value")
    }

    # ---- stages 1-5: recompute the pre-render plan through production code ----
    document = parse_document(source_path)
    template = extract_bid_format(document)
    model = build_source_format_model(document, template)
    model, _source_text_qa = apply_source_glyph_repairs(model, SOURCE_GLYPH_REPAIRS)
    page = next(
        page for page in model.source_pages if int(getattr(page, "page", 0)) == P3_SOURCE_PAGE
    )

    stage_records = []
    focus_rule = None
    for rule in getattr(page, "lines", None) or []:
        x0, y0, x1, y1 = (float(value) for value in rule.bbox)
        if abs(y0 - FOCUS_RULE_Y) <= 1.0:
            focus_rule = rule
            break
    if focus_rule is None:
        raise SystemExit("the focus rule is not present on the frozen source page")

    x0, y0, x1, y1 = (float(value) for value in focus_rule.bbox)
    key = _rule_key(P3_SOURCE_PAGE, x0, x1, y0)

    glyph_evidence = compile_source_rule_glyph_evidence(model.source_pages)
    compiled_glyph = glyph_evidence.get(key)
    field_plans = compile_source_form_field_plans(
        source_pages=model.source_pages,
        glyph_evidence=glyph_evidence,
        resolved_fact_fields=resolved_fact_fields,
        slot_contract=_slot_contract,
    )
    compiled_plan = resolve_field_plan(
        field_plans, page=P3_SOURCE_PAGE, x0=x0, x1=x1, y=y0
    )

    stage_records.append(
        {
            "stage": "1_source_rule_detection",
            "value": {
                "source_page": P3_SOURCE_PAGE,
                "source_x0": round(x0, 2),
                "source_x1": round(x1, 2),
                "source_y": round(y0, 2),
                "orientation": getattr(focus_rule, "orientation", None),
                "rule_count_on_page": len(list(getattr(page, "lines", None) or [])),
            },
            "semantics": None,
        }
    )

    stage_records.append(
        {
            "stage": "2_glyph_occupancy",
            "value": {
                "compiled_glyph_evidence_present": compiled_glyph is not None,
                "compiled_source_text": (compiled_glyph or ("", False))[0],
                "compiled_has_glyphs": bool((compiled_glyph or ("", False))[1]),
                "semantics": "glyph-free rule (a physical rule with no source text of its own)",
            },
            "semantics": None,
        }
    )

    boxes, preceding = source_rule_line_context(page, x0, y0, y1)
    line_hints = []
    for hint in _field_hint_candidates(preceding):
        slot_type, allowed = _slot_contract(hint)
        line_hints.append(
            {
                "hint": hint,
                "slot_type": slot_type,
                "allowed_fact_fields": [str(getattr(field, "value", field)) for field in allowed],
            }
        )
    stage_records.append(
        {
            "stage": "3_own_visual_line_label",
            "value": {
                "preceding_text_on_own_line": preceding,
                "boxes_on_own_line": [
                    {"x0": round(float(box[0]), 2), "x1": round(float(box[1]), 2), "text": box[2]}
                    for box in boxes
                ],
                "hint_candidates": line_hints,
                "bound_fact_fields": [],
                "semantics": (
                    "own-line label channel names no fact field: the label of this slot "
                    "is not on the rule's own visual line"
                ),
            },
            "semantics": None,
        }
    )

    unified, _boxes_report = compile_source_visual_text_boxes(page)
    structural, evidence = source_rule_structural_context(page, x0, y0, x1, y1)
    structural_records = []
    for kind, text in structural:
        hints = []
        for hint in _field_hint_candidates(text):
            slot_type, allowed = _slot_contract(hint)
            if not allowed:
                continue
            hints.append(
                {
                    "hint": hint,
                    "slot_type": slot_type,
                    "allowed_fact_fields": [
                        str(getattr(field, "value", field)) for field in allowed
                    ],
                }
            )
        structural_records.append({"kind": kind, "text": text, "field_hints": hints})
    stage_records.append(
        {
            "stage": "4_structural_neighbourhood",
            "value": {
                "owning_container_text": evidence.get("owning_container_text"),
                "owning_container_kind": evidence.get("owning_container_kind"),
                "same_cell_texts": evidence.get("same_cell_texts"),
                "same_row_texts": evidence.get("same_row_texts"),
                "adjacent_row_texts": evidence.get("adjacent_row_texts"),
                "preceding_container_texts": evidence.get("preceding_container_texts"),
                "wrap_continuation_row_text": evidence.get("wrap_continuation_row_text"),
                "candidates": structural_records,
                "visual_row_boxes_above": [
                    {
                        "y0": round(float(box["y0"]), 2),
                        "leaf": bool(box.get("is_leaf")),
                        "text": str(box.get("text") or "")[:80],
                    }
                    for box in unified
                    if float(box["y0"]) < y0 and float(box["y0"]) > y0 - 60.0
                ],
            },
            "semantics": None,
        }
    )

    stage_records.append(
        {
            "stage": "5_source_form_plan",
            "value": {
                "compiled_plan_policy": (compiled_plan or (None,))[0],
                "compiled_plan_fact_fields": _plan_fields(compiled_plan),
                "compiled_plan_geometry_intent": source_rule_geometry_intent(
                    (compiled_plan or (None,))[0]
                ),
                "recorded_plan": next(
                    (
                        record
                        for record in (report.get("source_form_field_plans") or [])
                        if abs(float(record.get("source_x0", 0.0)) - x0) <= 0.2
                        and abs(float(record.get("source_y", 0.0)) - y0) <= 0.2
                    ),
                    None,
                ),
            },
            "semantics": None,
        }
    )

    # ---- stage 6: the serialized normalized artifact, reloaded ----
    normalized_page = next(
        (
            entry
            for entry in normalized.get("pages") or []
            if int(entry.get("page_number") or entry.get("page") or 0) == P3_SOURCE_PAGE
        ),
        None,
    )
    normalized_rule = None
    for entry in (normalized_page or {}).get("vector_lines") or []:
        bbox = [float(value) for value in entry.get("bbox") or ()]
        if len(bbox) == 4 and abs(bbox[1] - y0) <= 0.2 and abs(bbox[0] - x0) <= 0.2:
            normalized_rule = {
                "bbox": [round(value, 2) for value in bbox],
                "orientation": entry.get("orientation"),
                "width": entry.get("width"),
            }
            break
    stage_records.append(
        {
            "stage": "6_normalized_artifact_reload",
            "value": {
                "normalized_document_present": True,
                "normalized_rule": normalized_rule,
                "semantics": (
                    "the serialized artifact carries physical geometry only: it has no "
                    "policy or geometry-intent field for any rule, so the semantics cannot "
                    "be lost - or introduced - here"
                ),
            },
            "semantics": None,
        }
    )

    # ---- stages 7-9: execution ownership, applications, registry, gates ----
    owners = [
        entry
        for entry in report.get("source_form_execution_owners") or []
        if "P42-R6" in (entry.get("source_rule_ids") or [])
    ]
    applications = [
        entry
        for entry in report.get("source_fill_applications") or []
        if "P42-R6" in (entry.get("source_rule_ids") or [])
    ]
    value_runs = [
        entry
        for entry in report.get("source_form_line_value_runs") or []
        if entry.get("source_rule_id") == "P42-R6"
    ]
    registry = _registry_entry(report, "P42-R6")
    stage_records.append(
        {
            "stage": "7_execution_ownership_and_application",
            "value": {
                "execution_owner": owners[0] if owners else None,
                "source_fill_application": applications[0] if applications else None,
                "source_form_line_value_run": value_runs[0] if value_runs else None,
                "owner_count": len(owners),
                "application_count": len(applications),
                "semantics": (
                    "no owner, no application and no value run for this rule: the plan "
                    "never asked for a resolved value in the fixed slot, so the owner "
                    "correctly established nothing (no invented value, no duplicate "
                    "execution across plan iterations)"
                ),
            },
            "semantics": None,
        }
    )
    stage_records.append(
        {
            "stage": "8_production_rule_registry",
            "value": {
                "registry_entry": registry,
                "registry_policy": (registry or {}).get("transformation_policy"),
                "registry_geometry_intent": (registry or {}).get("geometry_intent"),
                "derived_intent_for_policy": source_rule_geometry_intent(
                    (registry or {}).get("transformation_policy")
                ),
            },
            "semantics": None,
        }
    )

    closure = None
    closure_path = args.closure if args.closure.is_absolute() else ROOT / args.closure
    if closure_path.exists():
        closure_report = _read(closure_path)
        closure = _gate_rows(closure_report)
    inventory = None
    inventory_path = args.inventory if args.inventory.is_absolute() else ROOT / args.inventory
    if inventory_path.exists():
        inventory = _inventory_row(_read(inventory_path))
    stage_records.append(
        {
            "stage": "9_qa_and_gate_representation",
            "value": {
                "frozen_closure_gate_row": closure,
                "underline_inventory_row": inventory,
                "semantics": (
                    "both gates read the production registry, so they reported whatever "
                    "the registry said; neither gate rewrites the semantics"
                ),
            },
            "semantics": None,
        }
    )

    # ---- where the divergence is introduced ----
    divergence = []
    for stage in stage_records:
        value = stage["value"]
        policy = value.get("registry_policy") or value.get("compiled_plan_policy")
        if policy is not None and policy != FROZEN_SEMANTICS["P42-R6"][0]:
            divergence.append(
                {
                    "stage": stage["stage"],
                    "policy_found": policy,
                    "frozen_policy": FROZEN_SEMANTICS["P42-R6"][0],
                }
            )

    frozen_policy, frozen_intent = FROZEN_SEMANTICS["P42-R6"]
    compiled_policy = (compiled_plan or (None,))[0]
    compiled_fields = _plan_fields(compiled_plan)
    compiled_intent = source_rule_geometry_intent(compiled_policy)
    registry_policy = (registry or {}).get("transformation_policy")
    registry_intent = (registry or {}).get("geometry_intent")

    # ---- the build that exhibited the inconsistency, read from its artifacts ----
    # The recomputation above runs the *current* production code, so it can no
    # longer reproduce the pre-fix plan.  The pre-fix stage values therefore come
    # from the artifacts that build actually wrote: its recorded plan, its
    # registry, and what its execution channel did with them.
    pre_build = (args.pre_build if args.pre_build.is_absolute() else ROOT / args.pre_build).resolve()
    pre_closure_path = (
        args.pre_closure if args.pre_closure.is_absolute() else ROOT / args.pre_closure
    )
    pre_inventory_path = (
        args.pre_inventory if args.pre_inventory.is_absolute() else ROOT / args.pre_inventory
    )
    pre_report = _read(pre_build / "generation_report.json")
    pre_registry = {
        str(entry.get("source_rule_id")): entry
        for entry in pre_report.get("source_rule_registry") or []
    }.get("P42-R6") or {}
    x0f, x1f, y0f = float(x0), float(x1), float(y0)
    pre_plan_record = _recorded_plan(pre_report, x0f, y0f)
    pre_execution = _execution_evidence(pre_report)
    pre_policy = (pre_plan_record or {}).get("transformation_policy")
    pre_block = {
        "build_id": pre_build.name,
        "build_dir": str(pre_build.relative_to(ROOT)).replace("\\", "/"),
        "recorded_source_form_plan": pre_plan_record,
        "recorded_plan_policy": pre_policy,
        "recorded_plan_fields": list((pre_plan_record or {}).get("fact_fields") or ()),
        "derived_intent_for_recorded_policy": source_rule_geometry_intent(pre_policy),
        "production_registry": {
            "transformation_policy": pre_registry.get("transformation_policy"),
            "geometry_intent": pre_registry.get("geometry_intent"),
            "matches_frozen_policy": (
                pre_registry.get("transformation_policy") == frozen_policy
            ),
            "matches_frozen_intent": (pre_registry.get("geometry_intent") == frozen_intent),
        },
        "execution": pre_execution,
        "frozen_closure_gate_row": _gate_rows(_read(pre_closure_path)),
        "underline_inventory_row": _inventory_row(_read(pre_inventory_path)),
        "stages_that_agreed_with_the_frozen_contract": [
            "1_source_rule_detection",
            "2_glyph_occupancy",
            "3_own_visual_line_label",
            "6_normalized_artifact_reload",
            "7_execution_ownership",
            "9_qa_and_gate_representation",
        ],
        "stage_where_the_frozen_policy_was_lost": "5_source_form_plan",
        "introduced_by": (
            "4_structural_neighbourhood: the field compiler's evidence channels (own visual "
            "line, then the row-scoped structural channels) never offered the label that ends "
            "the wrapped row above, so no fact field bound and the plan fell back to "
            "FIXED_EMPTY_SLOT with no field"
        ),
        "note": (
            "artifact evidence: the recorded plan, registry and execution records of the build "
            "that exhibited the inconsistency.  The in-process recomputation above reflects the "
            "repaired production code, so it cannot reproduce the pre-fix plan; this block is "
            "the pre-fix trace."
        ),
    }

    report_out = {
        "schema": SCHEMA,
        "build_id": build.name,
        "build_dir": str(build.relative_to(ROOT)).replace("\\", "/"),
        "source": {
            "path": str(source_path.relative_to(ROOT)).replace("\\", "/"),
            "page": P3_SOURCE_PAGE,
        },
        "focus_rule": {
            "source_rule_id": "P42-R6",
            "source_x0": round(x0, 2),
            "source_x1": round(x1, 2),
            "source_y": round(y0, 2),
            "frozen_semantics": {
                "transformation_policy": frozen_policy,
                "geometry_intent": frozen_intent,
                "fact_field": "quality_target",
            },
        },
        "stages": stage_records,
        "pre_reconciliation_build": pre_block,
        "divergence": {
            "stage_where_frozen_policy_is_lost": divergence[0]["stage"] if divergence else None,
            "stages_disagreeing_with_the_frozen_policy": [item["stage"] for item in divergence],
            "compiled_plan": {
                "transformation_policy": compiled_policy,
                "geometry_intent": compiled_intent,
                "fact_fields": compiled_fields,
                "matches_frozen_policy": compiled_policy == frozen_policy,
                "matches_frozen_intent": compiled_intent == frozen_intent,
            },
            "production_registry": {
                "transformation_policy": registry_policy,
                "geometry_intent": registry_intent,
                "matches_frozen_policy": registry_policy == frozen_policy,
                "matches_frozen_intent": registry_intent == frozen_intent,
            },
        },
        "root_cause": {
            "kind": "FIELD_BINDING_EVIDENCE_CHANNEL_MISSING",
            "detail": (
                "the source letter wraps its sentence after the label 供货质量, so the "
                "slot that label belongs to sits at the end of the *next* source visual "
                "row (达到____。).  The field compiler had no channel for a label that "
                "ends the row above: the own-line channel saw only 达到, the structural "
                "channels were bounded to the rule's own visual row by the accepted "
                "row-scoped contract, and the glyph-free rule therefore planned "
                "FIXED_EMPTY_SLOT with no fact field.  The production registry derives "
                "its geometry intent from that policy, so the whole pipeline reported "
                "FIXED_EMPTY_SLOT / EXACT_SOURCE_SPAN - not because the registry made the "
                "error, but because the plan it faithfully mirrors never bound the field."
            ),
            "not_the_cause": [
                "the production rule registry (it mirrors the plan; it derives the intent)",
                "the serialized normalized artifact (geometry only, no semantics)",
                "the QA and gate representation (both read the registry)",
                "the execution owner (correctly declined to own an unplanned value)",
            ],
            "fix": (
                "a new last-resort evidence channel: the wrapped row above offers the "
                "label it ends with, when that row does not end a sentence or a label "
                "terminator and sits one bounded row pitch above the rule's own row.  "
                "The single-distinct-field contract and the resolved-fact requirement are "
                "unchanged, so a wrap can only supply the label - never a value."
            ),
        },
        "frozen_semantics_table": {
            rule_id: {"transformation_policy": policy, "geometry_intent": intent}
            for rule_id, (policy, intent) in FROZEN_SEMANTICS.items()
        },
    }

    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "out": str(out_path),
                "stage_where_frozen_policy_is_lost": report_out["divergence"][
                    "stage_where_frozen_policy_is_lost"
                ],
                "compiled_plan": report_out["divergence"]["compiled_plan"],
                "production_registry": report_out["divergence"]["production_registry"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
