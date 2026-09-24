"""Round-5 final status: independent concern contracts (semantic validation).

Aggregates the round-5 evidence into one durable status board:

* ``acceptance/reports/v1_generalization/review_workbook_round5_final_status.json``
* ``acceptance/reports/v1_generalization/review_workbook_round5_final_status.md``

Round 5 closes the defect the human found in round 4 by eye.  Round 4 proved that
every rendered phrase has concern-owned provenance; the human review of
``..._review_workbook4`` still returned FAIL with
``CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED``, because

    PROVENANCE CONSISTENCY IS NOT SEMANTIC VALIDATION.

Round 5 therefore validates the *displayed* row against an independent,
hand-authored :class:`~tender_basic.concern_contract.ConcernContract` per
concern, and audits every delivered CASE001 row from its final cell text.

Automation never ticks a human box: ``CASE001_XLSX_MANUAL_REVIEW`` can only ever
read ``AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW``,
``V1_PRODUCTION_CANDIDATE`` and ``READY_FOR_SUBMISSION`` stay false.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "acceptance/reports/v1_generalization"
WORKSPACE = ROOT / "acceptance/workspace/_r5"

CASES = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook5",
    "case_002": "v1_round4_closure8_review_workbook5",
    "case_003": "v1_round4_closure8_review_workbook5",
}

ROUND5_HUMAN_RECORD = (
    REPORTS / "case001_review_workbook_round4_human_review_CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED.json"
)
ROUND3_HUMAN_RECORD = REPORTS / "case001_review_workbook_round4_human_review.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _suite(path: Path | None, xml: Path | None) -> dict[str, Any]:
    if xml is not None and xml.is_file():
        text = xml.read_text(encoding="utf-8", errors="replace")
        root = re.search(r"<testsuite\s[^>]*>", text)

        def attr(name: str) -> int | None:
            if not root:
                return None
            match = re.search(rf'{name}="(\d+)"', root.group(0))
            return int(match.group(1)) if match else None

        tests, errors, failures = attr("tests"), attr("errors"), attr("failures")
        if None not in (tests, errors, failures):
            return {
                "report": str(path) if path else "",
                "xml": str(xml),
                "tests": tests,
                "failed": failures,
                "errors": errors,
                "skipped": attr("skipped") or 0,
                "result": "PASS" if errors + failures == 0 else "FAIL",
            }
    if path is not None and path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        passed = re.search(r"(\d+) passed", text)
        failed = re.search(r"(\d+) failed", text)
        errors = re.search(r"(\d+) error", text)
        return {
            "report": str(path),
            "xml": str(xml) if xml else "",
            "tests": int(passed.group(1)) if passed else 0,
            "failed": int(failed.group(1)) if failed else 0,
            "errors": int(errors.group(1)) if errors else 0,
            "result": "PASS" if not (failed or errors) and passed else "FAIL",
        }
    return {"report": str(path) if path else "", "result": "NOT_RUN"}


def build_status(workspace: Path, suite_path: Path | None, suite_xml: Path | None) -> dict[str, Any]:
    flags_source = _load(workspace / "r5_flags.json").get("flags", {})
    suite = _suite(suite_path, suite_xml)
    cases: dict[str, Any] = {}
    for case, build in CASES.items():
        report = _load(workspace / f"r5_{case}.json")
        gate = _load(workspace / ("r4_on_w5.json" if case == "case_001" else f"r4_on_w5_{case}.json"))
        cases[case] = {
            "build": build,
            "workbook_sha256": report.get("workbook_sha256", ""),
            "round5_checks": f"{len([c for c in report.get('checks', []) if c['ok']])}/{len(report.get('checks', []))}",
            "round5_failed_checks": [c["check"] for c in report.get("checks", []) if not c["ok"]],
            "fixtures": report.get("fixtures_passed", ""),
            "fixtures_failed": report.get("fixtures_failed", 0),
            "row_audit": (
                f"{report.get('delivered_row_audit_count', 0) - report.get('delivered_row_audit_failed_count', 0)}"
                f"/{report.get('delivered_row_audit_count', 0)}"
            ),
            "row_audit_failed": report.get("delivered_row_audit_failed_count", 0),
            "concern_contract_violations": report.get("qa", {}).get("concern_contract_violation_count", 0),
            "needs_review_rows": report.get("qa", {}).get("needs_review_topic_count", 0),
            "round4_gate_verdict": gate.get("verdict", "NOT_RUN"),
            "round4_gate_checks": gate.get("checks", ""),
            "round4_rendered_mismatch_total": gate.get("rendered_mismatch_total", None),
        }
    human_records = [record for record in (ROUND3_HUMAN_RECORD, ROUND5_HUMAN_RECORD) if record.is_file()]
    blockers = [
        f"{case}:{name}"
        for case, entry in cases.items()
        for name in entry["round5_failed_checks"]
    ] + [
        f"{case}:row_audit"
        for case, entry in cases.items()
        if entry["row_audit_failed"]
    ] + [
        f"{case}:round4_gate"
        for case, entry in cases.items()
        if entry["round4_gate_verdict"] != "PASS"
    ]
    flags: dict[str, Any] = {
        **flags_source,
        "FULL_SUITE": suite["result"],
        "CASE001_XLSX_MANUAL_REVIEW": "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW",
        "CASE002_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "CASE003_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "HUMAN_REVIEW_BOXES_TICKED": 0,
        "REVIEW_WORKBOOK_ROUND5": "PASS" if not blockers else "FAIL",
        "V1_PRODUCTION_CANDIDATE": False,
        "READY_FOR_SUBMISSION": False,
    }
    return {
        "schema": "v1_review_workbook_round5_final_status/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round": "review_workbook_round5",
        "commit_subject": "feat: add independent concern contracts to review workbook",
        "pipeline": (
            "SourceRequirementAtom -> ReviewConcern -> ReviewPoint -> RenderedReviewComponent"
            " -> ConcernContract (independent semantic validation) -> workbook views"
        ),
        "invariant": "PROVENANCE CONSISTENCY IS NOT SEMANTIC VALIDATION",
        "result": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "flags": flags,
        "cases": cases,
        "human_review": {
            "records": [str(path) for path in human_records],
            "human_verdict": "FAIL",
            "fail_reason": "CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED",
            "must_not_be_rewritten": True,
            "automation_may_not_mark_pass": True,
            "CASE001_XLSX_MANUAL_REVIEW": "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW",
            "CASE002_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "CASE003_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "human_checkboxes_ticked": 0,
        },
        "full_test_suite": suite,
        "release": {
            "V1_PRODUCTION_CANDIDATE": False,
            "READY_FOR_SUBMISSION": False,
            "tagged": False,
            "released": False,
        },
    }


def render_markdown(status: dict[str, Any]) -> str:
    lines = [
        "# Review workbook round 5 — independent concern contracts",
        "",
        f"- round: `{status['round']}`",
        f"- invariant: **{status['invariant']}**",
        f"- result: **{status['result']}**",
        f"- blockers: {status['blockers'] or 'none'}",
        f"- full suite: {status['full_test_suite'].get('tests', 0)} tests, "
        f"{status['full_test_suite'].get('failed', 0)} failed, "
        f"{status['full_test_suite'].get('errors', 0)} errors",
        "",
        "## Flags",
        "",
        "| flag | value |",
        "| --- | --- |",
    ]
    for key, value in status["flags"].items():
        lines.append(f"| `{key}` | {value} |")
    lines += [
        "",
        "## Cases",
        "",
        "| case | round-5 checks | fixtures | rows audited | round-4 gate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case, entry in status["cases"].items():
        lines.append(
            f"| {case} | {entry['round5_checks']} | {entry['fixtures']} | {entry['row_audit']} | "
            f"{entry['round4_gate_verdict']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--out", type=Path, default=REPORTS / "review_workbook_round5_final_status.json")
    parser.add_argument("--md", type=Path, default=REPORTS / "review_workbook_round5_final_status.md")
    parser.add_argument(
        "--full-suite", type=Path, default=REPORTS / "review_workbook_round5_full_test_suite.txt"
    )
    parser.add_argument(
        "--full-suite-xml", type=Path, default=REPORTS / "review_workbook_round5_full_test_suite.xml"
    )
    args = parser.parse_args(argv)

    status = build_status(args.workspace, args.full_suite, args.full_suite_xml)
    args.out.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    args.md.write_text(render_markdown(status), encoding="utf-8")
    print(
        json.dumps(
            {
                "result": status["result"],
                "blockers": status["blockers"],
                "flags": status["flags"],
                "out": str(args.out),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0 if status["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
