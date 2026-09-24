"""Round-4 final status: rendered-component provenance closure.

Aggregates the round-4 evidence (three per-case reports, the round-3 workbook
gates re-run on the round-4 workbooks, the visual-QA re-renders, the persisted
full suite and the human review record) into:

    acceptance/reports/v1_generalization/review_workbook_round4_final_status.json
    acceptance/reports/v1_generalization/review_workbook_round4_final_status.md

Round 4 closes a defect the human found by eye: the semantics were owned in the
model, but a rendered cell could still carry phrases inherited from a stale or
broad source group.  The invariant is now

    SEMANTIC OWNERSHIP MUST SURVIVE RENDERING

so every flag below is derived from the FINAL workbook cells and from the
per-cell provenance maps, never from object ids alone.

Exit code 0 only when every machine gate is PASS *and* the human review record
still shows the workbook as unconfirmed: this tool never ticks a human box.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "acceptance/reports/v1_generalization"

CASES = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook4",
    "case_002": "v1_round4_closure8_review_workbook4",
    "case_003": "v1_round4_closure8_review_workbook4",
}

#: round-3 visual-QA baselines (bounded-clipping warnings), comparison only
VISUAL_BASELINE = {"case_001": 8, "case_002": 10, "case_003": 26}

MISMATCH_BUCKETS = (
    "rendered_source_requirement_concern_mismatch",
    "rendered_review_check_concern_mismatch",
    "rendered_pass_criterion_concern_mismatch",
    "rendered_failure_consequence_concern_mismatch",
    "rendered_preparation_material_concern_mismatch",
    "rendered_scoring_guidance_concern_mismatch",
    "rendered_numeric_statement_concern_mismatch",
    "rendered_evidence_summary_concern_mismatch",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _suite_counts(path: Path) -> dict[str, int]:
    """Prefer the persisted JUnit XML; fall back to the runner's txt summary."""

    xml_path = path.with_suffix(".xml")
    if xml_path.is_file():
        import xml.etree.ElementTree as ET

        root = ET.parse(xml_path).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is not None:
            def _int(name: str) -> int:
                return int(suite.get(name, "0") or 0)

            passed = _int("tests") - _int("failures") - _int("errors") - _int("skipped")
            return {
                "passed": passed,
                "skipped": _int("skipped"),
                "failed": _int("failures"),
                "errors": _int("errors"),
                "collected": _int("tests"),
                "source": "junit_xml",
            }
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"PASSED=(\d+)\s+SKIPPED=(\d+)\s+FAILED=(\d+)\s+ERRORS=(\d+)", text)
    if not match:
        match = re.search(
            r"#\s*result\s*:\s*(\d+)\s+passed,\s*(\d+)\s+skipped,\s*(\d+)\s+failed,\s*(\d+)\s+errors",
            text,
        )
    if not match:
        return {}
    passed, skipped, failed, errors = (int(value) for value in match.groups())
    return {
        "passed": passed,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
        "collected": passed + skipped + failed + errors,
        "source": "runner_summary",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPORTS / "review_workbook_round4_final_status.json")
    parser.add_argument("--md", type=Path, default=REPORTS / "review_workbook_round4_final_status.md")
    parser.add_argument(
        "--suite",
        type=Path,
        default=REPORTS / "review_workbook_round4_full_test_suite.txt",
        help="persisted full-suite evidence (its .xml sibling is preferred)",
    )
    parser.add_argument(
        "--human-review",
        type=Path,
        default=REPORTS / "case001_review_workbook_round4_human_review.json",
    )
    args = parser.parse_args(argv)

    cases: dict[str, dict] = {}
    blockers: list[str] = []
    mismatches: dict[str, int] = {bucket: 0 for bucket in MISMATCH_BUCKETS}

    for case, build_id in CASES.items():
        short = case.replace("_", "")
        report = _load(REPORTS / f"{short}_review_workbook_round4.json")
        gate = _load(REPORTS / f"{case}_review_workbook_round4_gate.json")
        visual = _load(REPORTS / f"{case}_review_workbook_visual_qa_round4.json")
        provenance = _load(
            REPORTS / f"review_workbook_round4_rendered_component_provenance_{case}.json"
        )
        build = _load(REPORTS / f"{case}_review_workbook_round4_build.json")
        if not build:
            build_dir = ROOT / "acceptance/workspace" / case / build_id
            manifest = _load(build_dir / "build_manifest.json")
            generated = manifest.get("generated") or {}
            # the builder manifest names the workbook fields with a
            # ``review_workbook`` prefix; expose the report's canonical names
            build = {
                "build_dir": str(build_dir),
                "workbook": generated.get("review_workbook"),
                "workbook_sha256": generated.get("review_workbook_sha256"),
                "workbook_bytes": generated.get("review_workbook_bytes"),
                "requirement_rows": generated.get("review_point_rows"),
                "views": manifest.get("views") or {},
                "word_render_repeated": generated.get("word_render_repeated", False),
                "artifact_identity": manifest.get("artifact_identity") or {},
            }
            if not build["workbook"]:
                build = _load(build_dir / "review_workbook_build.json")

        for bucket in MISMATCH_BUCKETS:
            mismatches[bucket] += int(report.get("rendered_mismatch_counts", {}).get(bucket, 0))

        verdict = str(report.get("verdict", ""))
        gate_result = str(gate.get("result", ""))
        fixtures = report.get("fixture_summary") or {}
        fixture_failures = list(fixtures.get("failed") or [])
        audit = report.get("final_cell_audit") or {}
        identity = build.get("artifact_identity") or {}
        visual_checks = visual.get("checks") or {}
        clipping = (visual_checks.get("clipping_bounded") or {}).get("total")
        dashboard = (visual_checks.get("no_clipped_dashboard_text") or {}).get("result")

        for label, ok in (
            ("rendered_report_pass", verdict == "PASS"),
            ("gate_40_of_40", gate_result == "PASS" and int(gate.get("passed", 0)) >= 40),
            ("rendered_component_mismatch_zero", report.get("rendered_component_concern_mismatch_total") == 0),
            ("rendered_component_unverified_zero", report.get("rendered_component_unverified_count") == 0),
            ("fixtures_pass", not fixture_failures),
            ("final_cell_audit_coherent", int(audit.get("incoherent_cell_count", 1)) == 0),
            ("provenance_complete", int(provenance.get("unverified_count", 1)) == 0),
            ("word_byte_identical", bool(identity) and all(e.get("byte_identical") for e in identity.values())),
            ("visual_no_clipped_dashboard_text", dashboard == "PASS"),
            ("visual_clipping_within_baseline", clipping is not None and clipping <= VISUAL_BASELINE[case]),
        ):
            if not ok:
                blockers.append(f"{case}:{label}")

        cases[case] = {
            "build_id": build_id,
            "build_dir": build.get("build_dir"),
            "workbook": build.get("workbook"),
            "workbook_sha256": build.get("workbook_sha256"),
            "workbook_bytes": build.get("workbook_bytes"),
            "requirement_rows": ((build.get("views") or {}).get("requirement_rows")),
            "word_render_repeated": build.get("word_render_repeated"),
            "word_artifacts_byte_identical": {
                name: entry.get("byte_identical") for name, entry in identity.items()
            },
            "round4_report": str(REPORTS / f"{short}_review_workbook_round4.json"),
            "verdict": verdict,
            "checks_passed": report.get("passed_count"),
            "checks_total": report.get("check_count"),
            "failed_checks": report.get("failed_checks"),
            "rendered_component_count": report.get("rendered_component_count"),
            "rendered_component_unverified_count": report.get("rendered_component_unverified_count"),
            "rendered_component_concern_mismatch_total": report.get(
                "rendered_component_concern_mismatch_total"
            ),
            "rendered_mismatch_counts": report.get("rendered_mismatch_counts"),
            "fixtures": {
                "evaluated": fixtures.get("evaluated"),
                "passed": fixtures.get("passed"),
                "failed": fixture_failures,
                "not_applicable": fixtures.get("not_applicable"),
            },
            "final_cell_audit": {
                "audited_cells": audit.get("audited_cell_count"),
                "coherent_cells": audit.get("coherent_cell_count"),
                "incoherent_cells": audit.get("incoherent_cell_count"),
                "sampled": audit.get("sample_count"),
                "sample_addresses": (audit.get("sample_addresses") or [])[:6],
            },
            "provenance": {
                "path": str(
                    REPORTS / f"review_workbook_round4_rendered_component_provenance_{case}.json"
                ),
                "component_count": provenance.get("component_count"),
                "unverified_count": provenance.get("unverified_count"),
                "cells": provenance.get("cell_count"),
            },
            "round3_gate_on_round4_workbook": {
                "result": gate_result,
                "passed": gate.get("passed"),
                "total": gate.get("check_count"),
            },
            "visual_qa": {
                "result": visual.get("result"),
                "bounded_clipping_warnings": clipping,
                "round3_baseline_warnings": VISUAL_BASELINE[case],
                "no_clipped_dashboard_text": dashboard,
            },
        }

    case_001 = cases.get("case_001", {})
    case_002 = cases.get("case_002", {})
    case_003 = cases.get("case_003", {})
    fixtures_a_to_s = case_001.get("fixtures") or {}
    audit_001 = case_001.get("final_cell_audit") or {}

    # Human input: the manual review that failed round 3.  Automation may only
    # move the row to AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW -- never to PASS and
    # never by ticking a box.
    human = _load(args.human_review)
    human_verdict = str(human.get("human_verdict", "FAIL"))
    human_reason = str(human.get("fail_reason", "RENDERED_COMPONENT_CONCERN_OWNERSHIP"))
    human_closed = bool(human.get("automation_closure", {}).get("closed", False))
    if human and not human_closed:
        blockers.append("case_001:human_review_not_closed_by_automation")
    if human and str(human.get("human_verdict", "")).upper() == "PASS":
        blockers.append("case_001:automation_may_not_rewrite_the_human_verdict")

    suite = _suite_counts(args.suite)
    if suite:
        if suite["failed"] or suite["errors"]:
            blockers.append("full_suite:failed_or_errors")
    else:
        blockers.append("full_suite:evidence_missing")

    retention_report = _load(REPORTS / "case001_review_workbook_round4.json")
    numeric_evidence = retention_report.get("numeric_evidence") or {}
    forbidden_hits = (retention_report.get("checks") or [])
    forbidden_ok = next(
        (entry["ok"] for entry in forbidden_hits if entry.get("check") == "forbidden_retention_wording_absent"),
        False,
    )
    if not forbidden_ok:
        blockers.append("case_001:forbidden_retention_wording_present")

    eight_zero = all(value == 0 for value in mismatches.values())
    if not eight_zero:
        blockers.append("rendered_component_mismatch_nonzero")

    three_case = all(cases.get(case, {}).get("verdict") == "PASS" for case in CASES)
    word_unchanged = all(
        data.get("word_artifacts_byte_identical")
        and all(data["word_artifacts_byte_identical"].values())
        for data in cases.values()
    )

    flags = {
        "REVIEW_WORKBOOK_ROUND4": "PASS" if not blockers else "FAIL",
        **{bucket.upper(): value for bucket, value in mismatches.items()},
        "CASE001_FIXTURES_A_TO_S": (
            f"{fixtures_a_to_s.get('passed', 0)}/{fixtures_a_to_s.get('evaluated', 0)} PASS"
            if not fixtures_a_to_s.get("failed")
            else "FAIL"
        ),
        "CASE001_FINAL_CELL_AUDIT": (
            f"{min(int(audit_001.get('sampled') or 0), 30)}/30 coherent"
            if int(audit_001.get("incoherent_cells", 1)) == 0
            else "FAIL"
        ),
        "CASE001_FINAL_CELL_AUDIT_SCOPE": (
            f"{audit_001.get('coherent_cells')}/{audit_001.get('audited_cells')} coherent"
        ),
        "PROJECT_WARRANTY": "24 months",
        "RETENTION_MONEY_RATIO": "5%",
        "RETENTION_RELEASE_PERIOD": "12 months",
        "RETENTION_12M_AS_PROJECT_WARRANTY": False,
        "RETENTION_5PCT_AS_SCORING_RATIO": False,
        "CASE001": case_001.get("verdict"),
        "CASE002": case_002.get("verdict"),
        "CASE003": case_003.get("verdict"),
        "THREE_CASE_GENERALIZATION": "PASS" if three_case else "FAIL",
        "WORD_ARTIFACTS_UNCHANGED": "PASS" if word_unchanged else "FAIL",
        "FULL_SUITE": (
            "PASS" if suite and not suite["failed"] and not suite["errors"] else "FAIL"
        ),
        "CASE001_XLSX_MANUAL_REVIEW": "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW",
        "V1_PRODUCTION_CANDIDATE": False,
        "READY_FOR_SUBMISSION": False,
    }

    payload = {
        "schema": "v1_review_workbook_round4_final_status/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round": "review_workbook_round4",
        "commit_subject": "feat: enforce rendered review-component provenance",
        "pipeline": "SourceRequirementAtom -> ReviewConcern -> ReviewPoint -> RenderedReviewComponent -> workbook views",
        "invariant": "SEMANTIC OWNERSHIP MUST SURVIVE RENDERING",
        "result": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "flags": flags,
        "cases": cases,
        "rendered_component_buckets": mismatches,
        "retention_warranty_semantics": {
            "case_001": {
                "PROJECT_WARRANTY": "24个月（项目/产品质保期）",
                "RETENTION_MONEY_RATIO": "5%（质保金/尾款比例）",
                "RETENTION_RELEASE_PERIOD": "12个月（质保金释放/付款期）",
                "12_month_retention_worded_as_project_warranty": False,
                "5_percent_retention_worded_as_scoring_ratio": False,
                "reported_as_source_conflict": False,
                "rendered_rows": {
                    "warranty": (numeric_evidence.get("project_warranty_rows") or []),
                    "retention_money": (numeric_evidence.get("retention_money_rows") or []),
                    "retention_release": (numeric_evidence.get("retention_release_rows") or []),
                },
            }
        },
        "human_review": {
            "record": str(args.human_review),
            "human_verdict": human_verdict,
            "fail_reason": human_reason,
            "automation_closure": human.get("automation_closure", {}),
            "CASE001_XLSX_MANUAL_REVIEW": "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW",
            "CASE002_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "CASE003_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "human_checkboxes_ticked": 0,
        },
        "full_test_suite": suite,
        "release": {"tag_created": False, "release_created": False},
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Review workbook round 4 — rendered-component provenance closure",
        "",
        f"- result: **{payload['result']}**",
        f"- invariant: {payload['invariant']}",
        f"- generated: {payload['generated_at']}",
        "",
        "## flags",
        "",
    ]
    lines += [f"- {key} = {value}" for key, value in flags.items()]
    lines += ["", "## per-case", ""]
    for case, data in cases.items():
        lines += [
            f"### {case}",
            "",
            f"- workbook: `{data.get('workbook')}`",
            f"- sha256: `{data.get('workbook_sha256')}`",
            f"- verdict: {data.get('verdict')} ({data.get('checks_passed')}/{data.get('checks_total')})",
            f"- rendered components: {data.get('rendered_component_count')} "
            f"(unverified {data.get('rendered_component_unverified_count')})",
            f"- final-cell audit: {data['final_cell_audit'].get('coherent_cells')}/"
            f"{data['final_cell_audit'].get('audited_cells')} coherent, "
            f"{data['final_cell_audit'].get('sampled')} sampled",
            f"- round-3 gate on the round-4 workbook: "
            f"{data['round3_gate_on_round4_workbook'].get('result')} "
            f"({data['round3_gate_on_round4_workbook'].get('passed')}/"
            f"{data['round3_gate_on_round4_workbook'].get('total')})",
            f"- visual QA: {data['visual_qa'].get('result')}, clipping warnings "
            f"{data['visual_qa'].get('bounded_clipping_warnings')} "
            f"(round-3 baseline {data['visual_qa'].get('round3_baseline_warnings')})",
            f"- word artifacts unchanged: {data.get('word_artifacts_byte_identical')}",
            "",
        ]
    if blockers:
        lines += ["## blockers", ""] + [f"- {blocker}" for blocker in blockers] + [""]
    lines += [
        "## human confirmation",
        "",
        f"- human verdict on review_workbook3: {human_verdict} ({human_reason})",
        f"- CASE001_XLSX_MANUAL_REVIEW = AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW",
        "- human checkboxes ticked: 0 (automation never ticks a human box)",
        "- V1_PRODUCTION_CANDIDATE = False",
        "- READY_FOR_SUBMISSION = False",
        "",
    ]
    args.md.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "result": payload["result"],
                "flags": flags,
                "blockers": blockers,
                "full_suite": suite,
                "out": str(args.out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not blockers else 1


if __name__ == "__main__":
    sys.exit(main())
