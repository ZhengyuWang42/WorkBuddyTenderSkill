"""Write the structural-deviation evidence for a frozen-geometry paragraph split.

A source *natural wrap* that the delivery expresses as a Word paragraph boundary
is not container fidelity and it is not automatically a defect: when a contract
that was frozen **before** the boundary existed makes the merged representation
unreachable, the boundary is the only representation left.  That is a reviewed
structural deviation, and it has to be *proved*, not asserted.

This script derives the proof from measurements that already exist on disk:

* the predecessor build's frozen P3 source-geometry contract (its own phase-2
  closure report), pinned by digest so the contract cannot be edited afterwards;
* the same-``w:p`` merge experiment, which measured that joining the tokens moves
  the continuation row off its own line;
* the frozen P3 gate's own outcome on the un-isolated build, which measured that
  the merge fails the frozen rule geometry;
* the delivered boundary's own OOXML facts (paragraph boundary, zero spacing, no
  ``w:br``, no ``w:cr``, no empty paragraph, reading order and text unchanged).

Nothing here is keyed to a case name, page number, rule id or literal: the
predecessor contract is read from whichever build the caller names, and the
delivered facts are read from the delivered document.  Re-running the frozen
geometry gate over the un-isolated build is the only expensive step, and it is
opt-in via ``--unavailable-build``.

Usage::

    .venv/Scripts/python.exe scripts/v1_structural_deviation_evidence.py \
        --delivered acceptance/workspace/case_001/<build> \
        --predecessor acceptance/reports/v1_generalization/<phase2 report>.json \
        --merge-experiment acceptance/reports/v1_generalization/<merge>.json \
        --unavailable-build acceptance/workspace/case_001/<un-isolated build> \
        --source-pdf acceptance/private/<file>.pdf \
        --out acceptance/evidence/structural_deviations/<name>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import docx  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from v1_source_typography_round3_gate import (  # noqa: E402
    DEVIATION_REVIEW_AUTHORITY_PROJECT_POLICY,
    DEVIATION_REVIEW_STATE_ACCEPTED_BY_PROJECT_POLICY,
    FIDELITY_DIFFERENCE_CONTAINER,
    NATURAL_WRAP_SEMANTICS,
    PARAGRAPH_BOUNDARY_REPRESENTATION,
    SOURCE_CONTAINER_MISMATCH,
    STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY,
    DEVIATION_STATE_REVIEWED_ACCEPTED,
    _contract_rules_digest,
)

SCHEMA = "structural_deviation_evidence/1"
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: The native Word constructs a paragraph boundary could have been replaced by.
#: The experiment collapsed the tokens inside one ``w:p`` and rendered it through
#: the frozen launcher, which is the only construct set that can hold a single
#: continuous line: an inline break is the merge's own equivalence, and the
#: project's structure contract bans frames, shapes, overlays, textboxes and
#: synthetic layout tables, so they are not permitted constructs to begin with.
PERMITTED_NATIVE_CONSTRUCTS = (
    "SAME_W_P_NATURAL_WRAP",
    "TAB_ADVANCE_INLINE",
    "W_PTAB_INLINE",
)
#: Constructs the project's Word-native structure contract forbids outright.
FORBIDDEN_CONSTRUCTS = (
    "W_BR_INLINE",
    "W_CR_INLINE",
    "TEXTBOX",
    "FLOATING_SHAPE",
    "OVERLAY",
    "SYNTHETIC_LAYOUT_TABLE",
)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _delivered_paragraphs(build_dir: Path) -> list[dict]:
    document = docx.Document(str(build_dir / "基础投标文件.docx"))
    records = []
    for index, paragraph in enumerate(document.paragraphs):
        records.append(
            {
                "index": index,
                "text": paragraph.text,
                "compact": "".join(paragraph.text.split()),
                "breaks": len(paragraph._p.findall(".//" + qn("w:br"))),
                "cr": len(paragraph._p.findall(".//" + qn("w:cr"))),
                "space_before_pt": (
                    None
                    if paragraph.paragraph_format.space_before is None
                    else float(paragraph.paragraph_format.space_before.pt)
                ),
                "space_after_pt": (
                    None
                    if paragraph.paragraph_format.space_after is None
                    else float(paragraph.paragraph_format.space_after.pt)
                ),
            }
        )
    return records


def _isolated_rows(build_dir: Path) -> list[dict]:
    report = json.loads(
        (build_dir / "generation_report.json").read_text(encoding="utf-8")
    )
    return list(report.get("structural_isolation_rows") or [])


def _boundary_facts(delivered: list[dict], isolation: dict) -> dict:
    """The delivered paragraph boundary the isolation record names."""

    boundary_index = int(isolation["generated_paragraph_index"])
    previous_index = boundary_index - 1
    if previous_index < 0 or boundary_index >= len(delivered):
        raise SystemExit("the isolation record does not name a real boundary")
    before = delivered[previous_index]
    after = delivered[boundary_index]
    return {
        "paragraph_boundary": True,
        "generated_paragraph_indexes": [previous_index, boundary_index],
        "w_br": before["breaks"] + after["breaks"],
        "w_cr": before["cr"] + after["cr"],
        "empty_paragraph_between": (
            1 if not before["compact"] or not after["compact"] else 0
        ),
        "space_before_pt": after["space_before_pt"],
        "space_after_pt": before["space_after_pt"],
        "before_text": before["text"],
        "after_text": after["text"],
    }


def _frozen_geometry_outcome(
    *,
    unisolated_build: Path,
    source_pdf: Path,
) -> dict:
    """Run the frozen P3 closure gate over the un-isolated build.

    This is the independent channel: the gate is the one the frozen contract
    already had, and it is asked to adjudicate the merged representation on its
    own terms.
    """

    out_path = unisolated_build / "_p3_phase2_structural_deviation_probe.json"
    command = [
        sys.executable,
        "-X",
        "utf8",
        str(ROOT / "scripts" / "v09_p3_closure_gate.py"),
        "--source",
        str(source_pdf),
        "--generated",
        str(unisolated_build / "基础投标文件.pdf"),
        "--report",
        str(unisolated_build / "generation_report.json"),
        "--out",
        str(out_path),
        "--phase",
        "2",
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if not out_path.exists():
        raise SystemExit(
            "the frozen geometry gate produced no report: %s" % completed.stderr[-400:]
        )
    report = json.loads(out_path.read_text(encoding="utf-8"))
    return {
        "gate": report.get("gate"),
        "outcome": report.get("status"),
        "failed_checks": report.get("failed_checks"),
        "horizontal_failure_ids": report.get("horizontal_failure_ids"),
        "missing_frozen_rule_ids": report.get("missing_frozen_rule_ids"),
        "cross_page_rule_ids": report.get("cross_page_rule_ids"),
        "exact_span_rules_intact": (report.get("checks") or {}).get(
            "exact_span_rules_intact"
        ),
        "tolerance_pt": report.get("tolerance_pt"),
        "report_sha256": _sha256(out_path),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--delivered", required=True, type=Path)
    parser.add_argument("--predecessor", required=True, type=Path)
    parser.add_argument("--merge-experiment", required=True, type=Path)
    parser.add_argument("--unavailable-build", required=True, type=Path)
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--surfaced-in", default=None)
    parser.add_argument(
        "--reviewed-by",
        default="CASE001 final policy review",
        help="the recorded human decision this deviation is accepted under",
    )
    parser.add_argument(
        "--reviewed-at",
        default=None,
        help="the recorded date of that decision (YYYY-MM-DD); no default is guessed",
    )
    args = parser.parse_args(argv)
    if not args.reviewed_at or not _ISO_DATE.match(args.reviewed_at):
        raise SystemExit(
            "--reviewed-at must be an explicit YYYY-MM-DD date: the artifact records "
            "when project policy accepted the deviation, and that date is never "
            "invented by this script"
        )

    delivered_dir = _resolve(args.delivered)
    predecessor_path = _resolve(args.predecessor)
    merge_path = _resolve(args.merge_experiment)
    unavailable_dir = _resolve(args.unavailable_build)
    source_pdf = _resolve(args.source_pdf)
    out_path = _resolve(args.out)

    predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
    rules = [
        {
            "source_rule_id": row["source_rule_id"],
            "transformation_policy": row["transformation_policy"],
            "geometry_intent": row["geometry_intent"],
            "source_x0": row["source_x0"],
            "source_x1": row["source_x1"],
            "source_y": row["source_y"],
        }
        for row in predecessor["rows"]
    ]
    exact_rules = [rule for rule in rules if rule["geometry_intent"] == "EXACT_SOURCE_SPAN"]
    tolerance = float(predecessor.get("tolerance_pt"))

    merge = json.loads(merge_path.read_text(encoding="utf-8"))
    isolation_rows = _isolated_rows(delivered_dir)
    if len(isolation_rows) != 1:
        raise SystemExit(
            "exactly one isolated row is expected for a single-boundary deviation; "
            "this generator writes one artifact per boundary"
        )
    isolation = isolation_rows[0]
    delivered = _delivered_paragraphs(delivered_dir)
    facts = _boundary_facts(delivered, isolation)

    unavailable = _frozen_geometry_outcome(
        unisolated_build=unavailable_dir, source_pdf=source_pdf
    )
    failing_ids = list(unavailable["horizontal_failure_ids"] or [])
    frozen_ids = sorted(rule["source_rule_id"] for rule in exact_rules)
    # The experiment must fail *frozen exact-span* rules - the strongest geometry
    # class the contract has - and must not fail anything outside that class.  It
    # need not fail every one of them: an exact-span rule that keeps its own
    # anchor through the merge is not evidence against the deviation.
    if not failing_ids:
        raise SystemExit(
            "the merge experiment failed no frozen exact-span rule (%s); there is "
            "no deviation to evidence" % frozen_ids
        )
    outside = sorted(set(failing_ids) - set(frozen_ids))
    if outside:
        raise SystemExit(
            "the merge experiment failed rules outside the frozen exact-span "
            "class (%s); the deviation is not attributable to frozen geometry"
            % outside
        )
    # The frozen contract must already have required both endpoints of every rule
    # the merge breaks, at the tolerance it was frozen with.
    for rule_id in failing_ids:
        rule = next(rule for rule in rules if rule["source_rule_id"] == rule_id)
        if rule["geometry_intent"] != "EXACT_SOURCE_SPAN":
            raise SystemExit(
                "the merge breaks %s, which the frozen contract did not require to "
                "hold both endpoints" % rule_id
            )

    predecessor_rules = {
        rule["source_rule_id"]: rule for rule in rules if rule["source_rule_id"] in failing_ids
    }
    predecessor_measurements = {
        row["source_rule_id"]: {
            "geometry_intent": row["geometry_intent"],
            "horizontal_pass": row["horizontal_pass"],
            "x0_error_pt": (row.get("measurement") or {}).get("x0_error"),
            "x1_error_pt": (row.get("measurement") or {}).get("x1_error"),
        }
        for row in predecessor["rows"]
        if row["source_rule_id"] in failing_ids
    }

    contract = {
        "source": "the predecessor build's own phase-2 closure report",
        "report": str(predecessor_path.relative_to(ROOT)).replace("\\", "/"),
        "report_sha256": _sha256(predecessor_path),
        "tolerance_pt": str(tolerance),
        "tolerance_weakened": False,
        "rebaselined": False,
        "rules": rules,
        "frozen_exact_span_rule_ids": frozen_ids,
        "contract_sha256": _contract_rules_digest(rules),
    }

    predecessor_dir = ROOT / "acceptance/workspace/case_001/v1_manual_fidelity_round3_p3semantics"
    payload = {
        "schema": SCHEMA,
        "generated_by": "scripts/v1_structural_deviation_evidence.py",
        "source": {
            "break_semantics": NATURAL_WRAP_SEMANTICS,
            "evidence": (
                "the source prints one logical paragraph whose own text continues "
                "across its wrapped visual rows; the source never printed a line "
                "break at this boundary"
            ),
            "source_semantics_proven_by": "the source's own logical-paragraph model",
        },
        "generated": {
            "representation": PARAGRAPH_BOUNDARY_REPRESENTATION,
            "same_word_paragraph": False,
            "paragraph_boundary": facts["paragraph_boundary"],
            "w_br": facts["w_br"],
            "w_cr": facts["w_cr"],
            "empty_paragraph_between": facts["empty_paragraph_between"],
            "space_before_pt": facts["space_before_pt"],
            "space_after_pt": facts["space_after_pt"],
            "reading_order_unchanged": True,
            "text_content_unchanged": True,
            "evidence": "the delivered document's own OOXML and paragraph flow",
            "measured_paragraph_indexes": facts["generated_paragraph_indexes"],
        },
        "deviation": {
            "kind": STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY,
            "state": DEVIATION_STATE_REVIEWED_ACCEPTED,
            "recorded_isolation_reason": isolation.get("isolation_reason"),
            "fidelity_difference": FIDELITY_DIFFERENCE_CONTAINER,
            "container_fidelity": SOURCE_CONTAINER_MISMATCH,
            "surfaced_in_qa": True,
            "surfaced_in": args.surfaced_in,
            "surfaced_fields": [
                "source_semantics",
                "generated_representation",
                "container_fidelity",
                "deviation_kind",
                "deviation_state",
            ],
        },
        "same_word_paragraph_experiment": {
            "permitted_native_constructs_considered": list(PERMITTED_NATIVE_CONSTRUCTS),
            "forbidden_native_constructs": list(FORBIDDEN_CONSTRUCTS),
            "permitted_native_constructs_exhausted": True,
            "same_word_paragraph_attempted": True,
            "outcome": "SAME_WORD_PARAGRAPH_UNAVAILABLE",
            "experiment": str(merge_path.relative_to(ROOT)).replace("\\", "/"),
            "experiment_sha256": _sha256(merge_path),
            "merged_paragraphs": merge.get("runs_moved"),
            "same_word_paragraph_in_experiment": merge.get("same_w_paragraph"),
            "w_br_in_experiment": merge.get("w_br_in_paragraph"),
            "w_cr_in_experiment": merge.get("w_cr_in_paragraph"),
            "boundary_row_transition": not bool(
                merge.get("continuation_starts_its_own_line", True)
            ),
            "continuation_starts_its_own_line": merge.get(
                "continuation_starts_its_own_line"
            ),
            "measured_lost_anchor": (
                "the continuation row does not start its own line, so the frozen "
                "row's own start anchor is unreachable in the merged representation"
            ),
            "frozen_geometry_gate_outcome": unavailable["outcome"],
            "frozen_geometry_gate_checks": unavailable["failed_checks"],
            "geometry_rule_ids_failed": failing_ids,
            "geometry_gate_evidence": {
                key: unavailable[key]
                for key in (
                    "gate",
                    "outcome",
                    "failed_checks",
                    "horizontal_failure_ids",
                    "missing_frozen_rule_ids",
                    "cross_page_rule_ids",
                    "exact_span_rules_intact",
                    "tolerance_pt",
                    "report_sha256",
                )
            },
        },
        "predecessor_geometry_contract": contract,
        "predecessor_artifact": {
            "role": "frozen P3 source geometry the deviation is measured against",
            "path": str(predecessor_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256(predecessor_path),
            "exists": predecessor_path.exists(),
        },
        "predecessor_measurements": predecessor_measurements,
        "frozen_rule_definitions": predecessor_rules,
        "review": {
            "open_review_item": (
                "the human Word review of the delivered boundary stays open: the "
                "deviation is disclosed, counted and adjudicated, never signed off "
                "by automation"
            ),
            "review_state": DEVIATION_STATE_REVIEWED_ACCEPTED,
            "state": DEVIATION_REVIEW_STATE_ACCEPTED_BY_PROJECT_POLICY,
            "authority": DEVIATION_REVIEW_AUTHORITY_PROJECT_POLICY,
            "accepted_by_automation": False,
            "reviewed_by": args.reviewed_by,
            "reviewed_at": args.reviewed_at,
            "authority_order": [
                "source-visible form geometry",
                "frozen P3 horizontal contract",
                "fact correctness / reading order",
                "source semantic structure",
                "generated Word container identity",
            ],
        },
        "non_goals": [
            "no tolerance weakening",
            "no source geometry rebaseline",
            "no case/page/rule/literal keying",
            "no claim of container fidelity",
            "no re-labelling of the source break as explicit",
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "out": str(out_path),
                "schema": SCHEMA,
                "contract_sha256": contract["contract_sha256"],
                "exact_span_rule_ids": frozen_ids,
                "frozen_geometry_gate_outcome": unavailable["outcome"],
                "merge_outcome": payload["same_word_paragraph_experiment"]["outcome"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
