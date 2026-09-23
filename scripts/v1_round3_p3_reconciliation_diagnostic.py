"""Round-3 P3 contract reconciliation: same-build endpoint measurement.

Answers one question for every frozen P3 rule, on a build that already exists:

* what the source drew (the frozen source span, its policy and geometry intent),
* what the build rendered (both painted endpoints, both errors, the painted
  segments the rule owns, and the representation the emitter used),
* whether justification moved the delivered text advance and/or the rule's own
  geometry,
* and, for every disagreement the previous inventory reported, which of the
  admissible causes explains it.

Nothing here changes a contract: the tolerance, the policies and the source
spans are the frozen ones.  Only the *measurement implementation* is current -
one rule's ink is measured from the page's own drawn segments, so a rule the
emitter painted as several segments, or one a neighbouring glyph's underline
touches, measures as the span the source drew.

Usage::

    python scripts/v1_round3_p3_reconciliation_diagnostic.py \
        --source-pdf <tender.pdf> \
        --build round3_pre=<build dir> --build round3_post=<build dir> \
        --old-inventory acceptance/reports/v1_generalization/case001_underline_inventory_round3.json \
        --out acceptance/reports/v1_generalization/case001_round3_p3_contract_reconciliation_diagnostic.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA = "v1_round3_p3_contract_reconciliation_diagnostic/1"

P3_SOURCE_PAGE = 42
TOLERANCE_PT = 2.0

#: The frozen P3 contract, as authorised.  The diagnostic asserts the build's
#: registry against it and never re-baselines a span.
FROZEN_CONTRACT = [
    {
        "source_rule_id": "P42-R1",
        "transformation_policy": "PLACEHOLDER_REPLACED_BY_VALUE",
        "geometry_intent": "ANCHOR_START_ONLY",
        "source_x0": 94.8,
        "source_x1": 194.6,
        "source_y": 138.35,
    },
    {
        "source_rule_id": "P42-R2",
        "transformation_policy": "PLACEHOLDER_REPLACED_BY_VALUE",
        "geometry_intent": "ANCHOR_START_ONLY",
        "source_x0": 198.1,
        "source_x1": 375.7,
        "source_y": 158.4,
    },
    {
        "source_rule_id": "P42-R3",
        "transformation_policy": "FIXED_EMPTY_SLOT",
        "geometry_intent": "EXACT_SOURCE_SPAN",
        "source_x0": 169.65,
        "source_x1": 323.6,
        "source_y": 178.4,
    },
    {
        "source_rule_id": "P42-R4",
        "transformation_policy": "FIXED_EMPTY_SLOT",
        "geometry_intent": "EXACT_SOURCE_SPAN",
        "source_x0": 384.6,
        "source_x1": 459.0,
        "source_y": 178.4,
    },
    {
        "source_rule_id": "P42-R5",
        "transformation_policy": "RESOLVED_VALUE_IN_FIXED_SLOT",
        "geometry_intent": "ANCHOR_START_ONLY",
        "source_x0": 131.85,
        "source_x1": 181.4,
        "source_y": 198.35,
    },
    {
        "source_rule_id": "P42-R6",
        "transformation_policy": "RESOLVED_VALUE_IN_FIXED_SLOT",
        "geometry_intent": "ANCHOR_START_ONLY",
        "source_x0": 95.25,
        "source_x1": 151.05,
        "source_y": 218.4,
    },
    {
        "source_rule_id": "P42-R7",
        "transformation_policy": "SOURCE_VALUE_UNDERLINE",
        "geometry_intent": "EXACT_SOURCE_SPAN",
        "source_x0": 352.8,
        "source_x1": 388.8,
        "source_y": 318.35,
    },
    {
        "source_rule_id": "P42-R8",
        "transformation_policy": "PRESERVE_SOURCE_PLACEHOLDER",
        "geometry_intent": "EXACT_SOURCE_SPAN",
        "source_x0": 112.8,
        "source_x1": 208.8,
        "source_y": 418.4,
    },
]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inventory_module():
    return _load_module("v1_underline_inventory", REPO_ROOT / "scripts" / "v1_underline_inventory.py")


def _report(build_dir: Path) -> dict:
    return json.loads((build_dir / "generation_report.json").read_text(encoding="utf-8"))


def _registry_by_id(report: dict) -> dict:
    return {
        str(entry.get("source_rule_id")): entry
        for entry in report.get("source_rule_registry") or []
    }


def _composition_by_id(report: dict) -> dict:
    return {
        str(entry.get("source_rule_id")): entry
        for entry in report.get("source_rule_compositions") or []
    }


def _positioned_by_id(report: dict) -> dict:
    return {
        str(entry.get("source_rule_id")): entry
        for entry in report.get("positioned_blank_records") or []
        if entry.get("source_rule_id")
    }


def _isolation_by_rule(report: dict) -> dict:
    """Paragraph context the build gave each rule, keyed by rule id."""

    records: dict[str, dict] = {}
    for key in ("structural_isolation_rows", "source_form_line_paragraphs"):
        for record in report.get(key) or []:
            rule_ids = record.get("source_rule_ids") or [record.get("source_rule_id")]
            for rule_id in rule_ids:
                if not rule_id:
                    continue
                records.setdefault(str(rule_id), {})[key] = {
                    "generated_paragraph_index": record.get(
                        "generated_paragraph_index"
                    ),
                    "isolation_reason": record.get("isolation_reason"),
                    "space_before_pt": record.get("space_before_pt"),
                    "space_after_pt": record.get("space_after_pt"),
                    "paragraph_format": record.get("paragraph_format"),
                }
    return records


def _paragraph_index_by_rule(report: dict) -> dict:
    """The delivered paragraph each rule's visual line was assembled into."""

    indexes: dict[str, int] = {}
    for plan in report.get("source_visual_line_emission_plans") or []:
        index = plan.get("generated_paragraph_index")
        if index is None:
            continue
        for rule_id in plan.get("source_rule_ids") or []:
            indexes.setdefault(str(rule_id), int(index))
    return indexes


def _delivered_lines(generated_pdf: Path) -> dict:
    """Measured text lines with their per-character advance, by page."""

    import pymupdf  # noqa: PLC0415

    document = pymupdf.open(str(generated_pdf))
    lines: dict[int, list[dict]] = {}
    for page_index in range(document.page_count):
        page = document[page_index]
        rows = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text = "".join(span.get("text", "") for span in line.get("spans", []))
                compact = "".join(text.split())
                if not compact:
                    continue
                chars = [
                    char
                    for span in line.get("spans", [])
                    for char in span.get("chars", [])
                    if char.get("c", "").strip()
                ]
                sizes = [float(span.get("size") or 0.0) for span in line.get("spans", [])]
                size = max(sizes) if sizes else 0.0
                width = float(line["bbox"][2]) - float(line["bbox"][0])
                rows.append(
                    {
                        "y": round(float(line["bbox"][1]), 2),
                        "y1": round(float(line["bbox"][3]), 2),
                        "x0": round(float(line["bbox"][0]), 2),
                        "x1": round(float(line["bbox"][2]), 2),
                        "text": text[:80],
                        "char_count": len(chars) or len(compact),
                        "font_size_pt": round(size, 2),
                        "advance_per_char_pt": (
                            round(width / max(1, len(chars) or len(compact)), 3)
                        ),
                        "text_advance_ratio": (
                            round(
                                (width / max(1, len(chars) or len(compact)))
                                / size,
                                4,
                            )
                            if size
                            else None
                        ),
                    }
                )
        lines[page_index + 1] = rows
    document.close()
    return lines


def _run_identity(build_dir: Path, paragraph_index: int | None) -> dict:
    """The delivered runs of the rule's own paragraph, and its underline runs."""

    if paragraph_index is None:
        return {}
    import docx  # noqa: PLC0415
    from docx.oxml.ns import qn  # noqa: PLC0415

    document = docx.Document(str(build_dir / "基础投标文件.docx"))
    paragraphs = document.paragraphs
    if not 0 <= paragraph_index < len(paragraphs):
        return {}
    paragraph = paragraphs[paragraph_index]
    justified = paragraph.alignment is not None and int(paragraph.alignment) in (3, 4)
    breaks = len(paragraph._p.findall(".//" + qn("w:br")))
    runs = []
    for run in paragraph.runs:
        underline = run.font.underline
        runs.append(
            {
                "text": run.text[:60],
                "underline": None if underline is None else bool(underline),
                "bold": bool(run.font.bold),
            }
        )
    return {
        "paragraph_index": paragraph_index,
        "text": paragraph.text[:120],
        "alignment": None if paragraph.alignment is None else str(paragraph.alignment),
        "justified": bool(justified),
        "hard_breaks": breaks,
        "space_before_pt": (
            None
            if paragraph.paragraph_format.space_before is None
            else round(paragraph.paragraph_format.space_before.pt, 2)
        ),
        "space_after_pt": (
            None
            if paragraph.paragraph_format.space_after is None
            else round(paragraph.paragraph_format.space_after.pt, 2)
        ),
        "underline_runs": [run for run in runs if run["underline"]],
    }


def _representation(rule_id: str, report: dict) -> dict:
    """How the build says it painted this rule, and from what."""

    composition = _composition_by_id(report).get(rule_id)
    if composition:
        return {
            "recorded": "SOURCE_RULE_COMPOSITION",
            "geometry_policy": composition.get("geometry_policy"),
            "representation_type": composition.get("representation_type"),
            "logical_rule_emission_count": composition.get("logical_rule_emission_count"),
            "segments": [
                {
                    "segment_type": segment.get("segment_type"),
                    "source_x0": segment.get("source_x0"),
                    "source_x1": segment.get("source_x1"),
                    "needs_anchor": segment.get("needs_anchor"),
                    "reachability": segment.get("reachability"),
                }
                for segment in composition.get("segments") or []
            ],
        }
    positioned = _positioned_by_id(report).get(rule_id)
    if positioned:
        return {
            "recorded": "POSITIONED_BLANK",
            "emission_id": positioned.get("emission_id"),
            "emission_mechanism": positioned.get("emission_mechanism"),
            "representation_kind": positioned.get("representation_kind"),
            "anchor_tab": positioned.get("anchor_tab"),
            "paragraph_origin_pt": positioned.get("paragraph_origin_pt"),
            "reach_pt": positioned.get("reach_pt"),
            "emitted_advance_pt": positioned.get("emitted_advance_pt"),
            "cursor_text_tail": positioned.get("cursor_text_tail"),
        }
    return {"recorded": "NO_POSITIONED_RECORD"}


def _observed_representation(rule: dict, page_origin_pt: float | None) -> str:
    """What the delivered ink itself shows, independent of the build's record."""

    observed = rule.get("observed") or {}
    x0 = observed.get("x0")
    source_x0 = rule.get("source_x0")
    if x0 is None or source_x0 is None:
        return "NOT_PAINTED"
    if abs(float(x0) - float(source_x0)) <= TOLERANCE_PT:
        return "SOURCE_ANCHORED_RULE"
    if page_origin_pt is not None and abs(float(x0) - float(page_origin_pt)) <= TOLERANCE_PT:
        return "FLOW_CURSOR_INLINE_BLANK"
    return "DISPLACED_RULE"


def _measure_build(
    label: str,
    build_dir: Path,
    source_pdf: Path,
    inventory,
) -> dict:
    report = _report(build_dir)
    inventory_result = inventory.build_inventory(
        build_dir, source_pdf, label=label
    )
    registry = _registry_by_id(report)
    isolation = _isolation_by_rule(report)
    paragraph_indexes = _paragraph_index_by_rule(report)
    lines = _delivered_lines(build_dir / "基础投标文件.pdf")
    generated_page = int(inventory_result["response_letter_generated_page"])
    page_lines = lines.get(generated_page) or []

    rules = []
    invariants = []
    contract_registry_notes = []
    for frozen in FROZEN_CONTRACT:
        rule_id = frozen["source_rule_id"]
        measured = next(
            (item for item in inventory_result["rules"] if item["source_rule_id"] == rule_id),
            None,
        )
        if measured is None:
            # A rule the source drew but the page mapping never reached: measured
            # against the frozen span with no painted rule at all.
            measured = {
                "source_rule_id": rule_id,
                "status": "ABSENT_FROM_MEASUREMENT",
                "observed": {},
                "start_error_pt": None,
                "end_error_pt": None,
                "deviation_pt": None,
            }
        entry = dict(registry.get(rule_id) or {})
        observed = measured.get("observed") or {}
        rule_lines = [
            line
            for line in page_lines
            if observed.get("y") is not None
            and 0.0 <= float(observed["y"]) - float(line["y"]) <= 20.0
        ]
        owning_line = min(
            rule_lines,
            key=lambda line: abs(float(observed["y"]) - float(line["y"])),
            default=None,
        )
        paragraph_index = paragraph_indexes.get(rule_id)
        if paragraph_index is None:
            for record in (isolation.get(rule_id) or {}).values():
                if record.get("generated_paragraph_index") is not None:
                    paragraph_index = int(record["generated_paragraph_index"])
                    break
        source_width = float(frozen["source_x1"]) - float(frozen["source_x0"])
        painted_width = (
            None
            if observed.get("x0") is None
            else round(float(observed["x1"]) - float(observed["x0"]), 2)
        )
        width_error = (
            None if painted_width is None else round(abs(painted_width - source_width), 2)
        )
        policy_match = str(entry.get("transformation_policy") or "") == frozen[
            "transformation_policy"
        ]
        intent_match = str(entry.get("geometry_intent") or "") == frozen["geometry_intent"]
        record = {
            "source_rule_id": rule_id,
            "source_page": P3_SOURCE_PAGE,
            "source": {
                "x0": frozen["source_x0"],
                "x1": frozen["source_x1"],
                "y": frozen["source_y"],
                "width_pt": round(source_width, 2),
            },
            "contract": {
                "transformation_policy": frozen["transformation_policy"],
                "geometry_intent": frozen["geometry_intent"],
                "tolerance_pt": TOLERANCE_PT,
                "endpoints_owed": (
                    "BOTH"
                    if frozen["geometry_intent"] == "EXACT_SOURCE_SPAN"
                    else "START_ANCHOR"
                ),
            },
            "registry": {
                "transformation_policy": entry.get("transformation_policy"),
                "geometry_intent": entry.get("geometry_intent"),
                "relation_type": entry.get("relation_type"),
                "authoritative_slot_id": entry.get("authoritative_slot_id"),
                "policy_matches_frozen_contract": policy_match,
                "intent_matches_frozen_contract": intent_match,
            },
            "generated": {
                "painted_x0": observed.get("x0"),
                "painted_x1": observed.get("x1"),
                "painted_y": observed.get("y"),
                "x0_error_pt": measured.get("start_error_pt"),
                "x1_error_pt": measured.get("end_error_pt"),
                "gated_deviation_pt": measured.get("deviation_pt"),
                "gated_axis": measured.get("gated_axis"),
                "width_pt": painted_width,
                "width_error_pt": width_error,
                "painted_segments": measured.get("painted_segments") or [],
                "status": measured.get("status"),
                "measurement": measured.get("measurement"),
            },
            "representation": _representation(rule_id, report),
            "observed_representation": _observed_representation(
                measured, (owning_line or {}).get("x0")
            ),
            "paragraph": {
                "generated_paragraph_index": paragraph_index,
                "isolation": isolation.get(rule_id) or {},
                "run_identity": _run_identity(build_dir, paragraph_index),
            },
            "justification_effect": {
                "delivered_line_justified": (
                    None if owning_line is None else None
                ),
                "owning_line": owning_line,
                "delivered_text_advance_ratio": (
                    None if owning_line is None else owning_line["text_advance_ratio"]
                ),
                "text_advance_stretched_by_justification": (
                    None
                    if owning_line is None
                    else bool(
                        (owning_line["text_advance_ratio"] or 0.0) > 1.01
                    )
                ),
                "rule_geometry_changed": (
                    None if width_error is None else bool(width_error > TOLERANCE_PT)
                ),
            },
        }
        rules.append(record)

        if not policy_match:
            contract_registry_notes.append(
                {
                    "kind": "REGISTRY_POLICY_DIFFERS_FROM_FROZEN_CONTRACT_LISTING",
                    "source_rule_id": rule_id,
                    "frozen_contract_listing": frozen["transformation_policy"],
                    "registry_and_gate_policy": entry.get("transformation_policy"),
                    "delivered_geometry_satisfies_both_readings": (
                        deviation is not None and float(deviation) <= TOLERANCE_PT
                    ),
                }
            )
        if not intent_match:
            contract_registry_notes.append(
                {
                    "kind": "REGISTRY_INTENT_DIFFERS_FROM_FROZEN_CONTRACT_LISTING",
                    "source_rule_id": rule_id,
                    "frozen_contract_listing": frozen["geometry_intent"],
                    "registry_and_gate_intent": entry.get("geometry_intent"),
                    "delivered_geometry_satisfies_both_readings": (
                        deviation is not None and float(deviation) <= TOLERANCE_PT
                    ),
                }
            )
        deviation = measured.get("deviation_pt")
        if deviation is None or float(deviation) > TOLERANCE_PT:
            invariants.append(
                {
                    "kind": "RULE_GEOMETRY_OUTSIDE_FROZEN_TOLERANCE",
                    "source_rule_id": rule_id,
                    "geometry_intent": frozen["geometry_intent"],
                    "deviation_pt": deviation,
                    "tolerance_pt": TOLERANCE_PT,
                }
            )

    matched = sum(1 for rule in rules if rule["generated"]["status"] == "MATCHED")
    return {
        "label": label,
        "build_dir": str(build_dir),
        "docx_sha256": (
            json.loads((build_dir / "build_manifest.json").read_text(encoding="utf-8"))
            .get("docx_sha256")
            if (build_dir / "build_manifest.json").exists()
            else None
        ),
        "rules": rules,
        "accounting": {
            "matched": matched,
            "lost": inventory_result["lost"],
            "invented": inventory_result["invented"],
            "out_of_tolerance": inventory_result["out_of_tolerance"],
            "invariants": invariants,
            "contract_registry_notes": contract_registry_notes,
            "inventory_status": inventory_result["status"],
            "isolated_paragraphs": [
                {
                    "source_rule_ids": (
                        isolation.get(rule["source_rule_id"], {})
                        .get("structural_isolation_rows", {})
                        .get("isolation_reason")
                    ),
                    "generated_paragraph_index": (
                        isolation.get(rule["source_rule_id"], {})
                        .get("structural_isolation_rows", {})
                        .get("generated_paragraph_index")
                    ),
                }
                for rule in rules
                if isolation.get(rule["source_rule_id"], {}).get(
                    "structural_isolation_rows"
                )
            ],
            "unclaimed_fragments": inventory_result.get("unclaimed_fragments") or [],
        },
    }


def _classify(old_entry: dict, measurement: dict) -> dict:
    """Which admissible cause explains one old disagreement.

    The categories are decided from measurements on the build the old inventory
    itself measured, never from a rule id: a rule whose own ink was outside the
    frozen tolerance was an ``ACTUAL_RENDER_REGRESSION`` (even when a later build
    renders it correctly); one whose own ink was inside the tolerance was
    mis-measured by the old model - ``NEIGHBOUR_RULE_MERGE`` when the old span was
    wider than the rule's own run, ``OBSOLETE_MEASUREMENT_MODEL`` when the old
    model could not see the rule at all.  An old invented entry that the same ink
    line already accounts for was ``DOUBLE_ACCOUNTING``; one that is a fragment of
    a measured rule's own underline was a ``TEXT_DECORATION_MISCLASSIFICATION``.
    """

    rule_id = old_entry.get("source_rule_id")
    rule = next(
        (
            item
            for item in measurement["rules"]
            if item["source_rule_id"] == rule_id
        ),
        None,
    ) if rule_id else None
    old_observed = old_entry.get("observed") or {}
    old_invented = "x0" in old_entry and "source_rule_id" not in old_entry

    if old_invented:
        old_x0 = float(old_entry["x0"])
        old_x1 = float(old_entry["x1"])
        old_y = float(old_entry["y"])
        for item in measurement["rules"]:
            for segment in item["generated"]["painted_segments"] or []:
                if (
                    abs(float(segment["x0"]) - old_x0) <= 0.5
                    and abs(float(segment["x1"]) - old_x1) <= 0.5
                    and abs(float(segment["y"]) - old_y) <= 0.5
                ):
                    return {
                        "classification": "DOUBLE_ACCOUNTING",
                        "evidence": (
                            "the ink this entry called invented is the ink %s is "
                            "measured by" % item["source_rule_id"]
                        ),
                        "owner_rule_ids": [item["source_rule_id"]],
                    }
        for item in measurement["rules"]:
            for segment in item["generated"]["painted_segments"] or []:
                if abs(float(segment["y"]) - old_y) > 1.0:
                    continue
                if not (
                    old_x1 < float(segment["x0"]) - 1.0
                    or old_x0 > float(segment["x1"]) + 1.0
                ):
                    return {
                        "classification": "DOUBLE_ACCOUNTING",
                        "evidence": (
                            "the entry's span is the same underline line %s is already "
                            "measured by, so that ink was counted twice"
                            % item["source_rule_id"]
                        ),
                        "owner_rule_ids": [item["source_rule_id"]],
                    }
        for fragment in measurement["accounting"]["unclaimed_fragments"]:
            if (
                abs(float(fragment["x0"]) - old_x0) <= 0.5
                and abs(float(fragment["x1"]) - old_x1) <= 0.5
                and abs(float(fragment["y"]) - old_y) <= 0.5
            ):
                return {
                    "classification": "TEXT_DECORATION_MISCLASSIFICATION",
                    "evidence": (
                        "the ink is a fragment of a measured rule's own underline on "
                        "the same line, not a rule of its own"
                    ),
                }
        return {
            "classification": "OTHER_PROVEN_CAUSE",
            "evidence": "the ink is claimed by no rule and by no measured underline",
        }

    if rule is None:
        return {
            "classification": "OTHER_PROVEN_CAUSE",
            "evidence": "the rule the old report named is not part of the frozen contract",
        }

    generated = rule["generated"]
    deviation = generated["gated_deviation_pt"]
    segments = generated["painted_segments"] or []
    if deviation is None or float(deviation) > TOLERANCE_PT:
        return {
            "classification": "ACTUAL_RENDER_REGRESSION",
            "evidence": (
                "the rule's own ink measures %s pt from the frozen source geometry in "
                "the build the old inventory measured (tolerance %.1f pt)"
                % (deviation, TOLERANCE_PT)
            ),
            "painted": [generated["painted_x0"], generated["painted_x1"]],
            "source": [rule["source"]["x0"], rule["source"]["x1"]],
        }
    owned_x0 = min(float(segment["x0"]) for segment in segments) if segments else None
    owned_x1 = max(float(segment["x1"]) for segment in segments) if segments else None
    if (
        owned_x0 is not None
        and old_observed.get("x0") is not None
        and (
            float(old_observed["x0"]) < owned_x0 - 0.05
            or float(old_observed["x1"]) > owned_x1 + 0.05
        )
    ):
        return {
            "classification": "NEIGHBOUR_RULE_MERGE",
            "evidence": (
                "the old model measured a span wider than the rule's own run: the "
                "neighbouring underline it touches was measured as part of the rule"
            ),
            "old_measured_span": [
                float(old_observed["x0"]),
                float(old_observed["x1"]),
            ],
            "rule_own_span": [owned_x0, owned_x1],
        }
    return {
        "classification": "OBSOLETE_MEASUREMENT_MODEL",
        "evidence": (
            "the rule's own ink is inside the frozen tolerance in the very build the "
            "old inventory measured, so only the old measurement model disagreed: %s"
            % generated.get("measurement")
        ),
    }


def _old_disagreements(old_inventory: dict, measurements: list[dict]) -> list[dict]:
    """Every disagreement the old inventory reported, explained and re-measured."""

    pre = measurements[0]
    post = measurements[-1]
    explanations = []
    for entry in old_inventory.get("rules") or []:
        if entry.get("status") not in ("LOST", "OUT_OF_TOLERANCE"):
            continue
        explanation = _classify(entry, pre)
        explanations.append(
            {
                "old_status": entry.get("status"),
                "source_rule_id": entry.get("source_rule_id"),
                "old_measured": entry.get("observed") or {},
                "old_deviation_pt": entry.get("deviation_pt"),
                "old_gated_axis": entry.get("gated_axis"),
                "measured_in_the_build_the_old_inventory_measured": next(
                    (
                        rule["generated"]
                        for rule in pre["rules"]
                        if rule["source_rule_id"] == entry.get("source_rule_id")
                    ),
                    None,
                ),
                "post_reconciliation_measurement": next(
                    (
                        rule["generated"]
                        for rule in post["rules"]
                        if rule["source_rule_id"] == entry.get("source_rule_id")
                    ),
                    None,
                ),
                "resolved_in_post_build": next(
                    (
                        rule["generated"]["status"] == "MATCHED"
                        for rule in post["rules"]
                        if rule["source_rule_id"] == entry.get("source_rule_id")
                    ),
                    None,
                ),
                **explanation,
            }
        )
    for entry in old_inventory.get("invented_rules") or []:
        explanation = _classify(entry, pre)
        explanations.append(
            {
                "old_status": "INVENTED",
                "source_rule_id": None,
                "old_measured": entry,
                "old_deviation_pt": None,
                "old_gated_axis": None,
                "measured_in_the_build_the_old_inventory_measured": None,
                "post_reconciliation_measurement": None,
                "resolved_in_post_build": True,
                **explanation,
            }
        )
    return explanations


def build_diagnostic(
    source_pdf: Path,
    builds: list[tuple[str, Path]],
    old_inventory_path: Path | None,
) -> dict:
    inventory = _inventory_module()
    measurements = [
        _measure_build(label, build_dir, source_pdf, inventory)
        for label, build_dir in builds
    ]
    disagreements = []
    if old_inventory_path is not None and Path(old_inventory_path).exists():
        old_inventory = json.loads(Path(old_inventory_path).read_text(encoding="utf-8"))
        disagreements = _old_disagreements(old_inventory, measurements)
    counts: dict[str, int] = {}
    for entry in disagreements:
        counts[entry["classification"]] = counts.get(entry["classification"], 0) + 1
    return {
        "schema": SCHEMA,
        "source_pdf": str(source_pdf),
        "source_page": P3_SOURCE_PAGE,
        "tolerance_pt": TOLERANCE_PT,
        "frozen_contract": FROZEN_CONTRACT,
        "contract_authority": {
            "may_be_rebaselined": False,
            "measurement_implementation": (
                "source rule endpoint seeded contiguous painted run, read from the "
                "page's own drawn segments"
            ),
        },
        "measurements": measurements,
        "old_inventory": (
            None if old_inventory_path is None else str(old_inventory_path)
        ),
        "old_inventory_disagreements": disagreements,
        "old_disagreement_classification_counts": counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pdf", required=True)
    parser.add_argument(
        "--build",
        action="append",
        required=True,
        help="LABEL=BUILD_DIR; repeat for the before and after builds",
    )
    parser.add_argument("--old-inventory", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    builds = []
    for item in args.build:
        label, _, path = item.partition("=")
        builds.append((label, Path(path)))

    result = build_diagnostic(
        Path(args.source_pdf),
        builds,
        Path(args.old_inventory) if args.old_inventory else None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for measurement in result["measurements"]:
        accounting = measurement["accounting"]
        print(
            "%s: matched=%d lost=%d invented=%d out_of_tolerance=%d invariants=%d"
            % (
                measurement["label"],
                accounting["matched"],
                accounting["lost"],
                accounting["invented"],
                accounting["out_of_tolerance"],
                len(accounting["invariants"]),
            )
        )
    print(
        "old disagreement classification: %s"
        % json.dumps(result["old_disagreement_classification_counts"], ensure_ascii=False)
    )
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
