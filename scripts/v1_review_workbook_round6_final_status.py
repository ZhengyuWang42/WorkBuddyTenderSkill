"""Round-6 final status: source-visible criticality is semantic data.

Aggregates the three per-case criticality audits, the visual QA renders, the
untouched-artifact proofs (word artifacts, workbook4/workbook5) and the persisted
full-suite record into

* ``acceptance/reports/v1_generalization/review_workbook_round6_final_status.json``
* ``acceptance/reports/v1_generalization/review_workbook_round6_final_status.md``

Usage::

    python -X utf8 scripts/v1_review_workbook_round6_final_status.py \
        --suite-txt acceptance/reports/v1_generalization/review_workbook_round6_full_test_suite.txt \
        --suite-xml acceptance/reports/v1_generalization/review_workbook_round6_full_test_suite.xml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "acceptance/reports/v1_generalization"
WORKSPACE = ROOT / "acceptance/workspace"

CASES = {
    "case_001": {
        "build": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook6",
        "workbook5": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook5",
        "workbook4": "v1_manual_fidelity_round4_date_rhythm_closure8",
        "audit": "review_workbook_round6_criticality_audit_case_001.json",
        "visual": "case_001_review_workbook_visual_qa_round6.json",
    },
    "case_002": {
        "build": "v1_round4_closure8_review_workbook6",
        "workbook5": "v1_round4_closure8_review_workbook5",
        "workbook4": "v1_round4_closure8",
        "audit": "review_workbook_round6_criticality_audit_case_002.json",
        "visual": "case_002_review_workbook_visual_qa_round6.json",
    },
    "case_003": {
        "build": "v1_round4_closure8_review_workbook6",
        "workbook5": "v1_round4_closure8_review_workbook5",
        "workbook4": "v1_round4_closure8",
        "audit": "review_workbook_round6_criticality_audit_case_003.json",
        "visual": "case_003_review_workbook_visual_qa_round6.json",
    },
}

WORKBOOK5_SHA = {
    "case_001": "2ab34c7547926bb56a8bfc4fb39a226d0f2bbc672ccd10edf1df73b5987046af",
    "case_002": "a38d00b76bb35febb77be030d8352ee80f48d810f378caea17fd6fe5eaccb859",
    "case_003": "85aa576207077d8730e9c78ad7ca373bc8be6fe3dad091b5ef6ab0015c7bb4de",
}

#: The clauses the human named as still blank in the round-5 workbook.
CASE001_STAR_FIXTURES = (
    "DR001",
    "DR002",
    "DR003",
    "DR004",
    "DR012",
    "DR017",
    "DR018",
    "DR019",
    "DR020",
    "DR030",
    "DR047",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def suite_counts(txt: Path | None, xml: Path | None) -> dict:
    record: dict = {
        "suite_txt": str(txt) if txt else "",
        "suite_xml": str(xml) if xml else "",
        "tests": None,
        "passed": None,
        "failed": None,
        "errors": None,
        "skipped": None,
        "result": "NOT_RUN",
    }
    if xml and xml.is_file():
        root = ElementTree.parse(xml).getroot()
        suites = [root] if root.tag == "testsuite" else list(root)
        totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
        for suite in suites:
            for key in ("tests", "failures", "errors", "skipped"):
                totals[key] += int(float(suite.get(key, 0) or 0))
            totals["time"] += float(suite.get("time", 0) or 0)
        record.update(
            tests=totals["tests"],
            passed=totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"],
            failed=totals["failures"],
            errors=totals["errors"],
            skipped=totals["skipped"],
            duration_seconds=round(totals["time"], 1),
        )
    if txt and txt.is_file():
        body = txt.read_text(encoding="utf-8", errors="replace")
        match = re.search(
            r"PASSED=(\d+)\s+SKIPPED=(\d+)\s+FAILED=(\d+)\s+ERRORS=(\d+)\s+EXIT=(\d+)", body
        )
        if match:
            passed, skipped, failed, errors, exit_code = (int(value) for value in match.groups())
            record.update(
                passed=passed,
                skipped=skipped,
                failed=failed,
                errors=errors,
                exit_code=exit_code,
                tests=passed + skipped + failed + errors,
            )
    if record["failed"] == 0 and record["errors"] == 0 and record["tests"]:
        record["result"] = "PASS"
    elif record["tests"]:
        record["result"] = "FAIL"
    return record


def word_artifacts(build: Path) -> dict:
    manifest = load(build / "build_manifest.json")
    identity = manifest.get("artifact_identity", {}) or {}
    return {
        "count": len(identity),
        "all_byte_identical": bool(identity)
        and all(entry.get("byte_identical") for entry in identity.values()),
        "artifacts": {
            name: {
                "byte_identical": entry.get("byte_identical"),
                "sha256": entry.get("sha256") or entry.get("after_sha256") or "",
            }
            for name, entry in identity.items()
        },
    }


def prior_workbooks(round5_closed: datetime) -> dict:
    """Every pre-round-6 review workbook must still predate the round-5 close."""

    entries: dict[str, dict] = {}
    for case in CASES:
        for path in sorted((WORKSPACE / case).glob("*review_workbook[1-5]/投标项目复核表.xlsx")):
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            entries[f"{case}/{path.parent.name}"] = {
                "path": str(path),
                "mtime": mtime.isoformat(),
                "untouched": mtime < round5_closed,
            }
    return entries


def build_status(args: argparse.Namespace) -> dict:
    suite = suite_counts(args.suite_txt, args.suite_xml)
    round5_status = load(REPORTS / "review_workbook_round5_final_status.json")
    try:
        round5_closed = datetime.fromisoformat(round5_status.get("generated_at", ""))
    except ValueError:
        round5_closed = datetime.now(timezone.utc)
    priors = prior_workbooks(round5_closed)
    cases: dict[str, dict] = {}
    for case, spec in CASES.items():
        build = WORKSPACE / case / spec["build"]
        audit = load(REPORTS / spec["audit"])
        visual = load(REPORTS / spec["visual"])
        workbook6 = build / "投标项目复核表.xlsx"
        workbook5 = WORKSPACE / case / spec["workbook5"] / "投标项目复核表.xlsx"
        workbook4 = WORKSPACE / case / spec["workbook4"] / "投标项目复核表.xlsx"
        workbook4_manifest = load(WORKSPACE / case / spec["workbook4"] / "build_manifest.json")
        counts = audit.get("counts", {})
        model = audit.get("criticality_model", {})
        marked_rules = [rule for rule in model.get("substantive_rules", []) if rule.get("markers")]
        cases[case] = {
            "build": spec["build"],
            "audit": str(REPORTS / spec["audit"]),
            "verdict": audit.get("verdict", "NOT_RUN"),
            "failed_checks": audit.get("failed_checks", []),
            "failed_fixtures": audit.get("fixture_summary", {}).get("failed", []),
            "fixture_summary": audit.get("fixture_summary", {}),
            "workbook_sha256": sha256(workbook6) if workbook6.is_file() else "",
            "row_count": audit.get("concern_contract", {}).get("review_row_count"),
            "marker_vocabulary": model.get("marker_vocabulary", []),
            "marker_rule_count": len(marked_rules),
            "governing_clauses": sorted(
                {rule.get("governing_clause") for rule in marked_rules if rule.get("governing_clause")}
            ),
            "marker_semantics": sorted({rule.get("semantics") for rule in marked_rules}),
            "counts": counts,
            "concern_contract": audit.get("concern_contract_verdict", "NOT_RUN"),
            "concern_contract_detail": audit.get("concern_contract", {}),
            "visual_qa": visual.get("result", "NOT_RUN"),
            "visual_qa_checks": {
                name: value.get("result", "NOT_RUN")
                for name, value in (visual.get("checks") or {}).items()
            },
            "visual_qa_failed_checks": visual.get("failed_checks", []),
            "word_artifacts": word_artifacts(build),
            "workbook5_sha256": sha256(workbook5) if workbook5.is_file() else "",
            "workbook5_expected_sha256": WORKBOOK5_SHA[case],
            "workbook5_untouched": bool(workbook5.is_file())
            and sha256(workbook5) == WORKBOOK5_SHA[case],
            "workbook4_sha256": sha256(workbook4) if workbook4.is_file() else "",
            "workbook4_manifest_sha256": workbook4_manifest.get("workbook_sha256", ""),
            "workbook4_untouched": bool(workbook4.is_file())
            and sha256(workbook4) == workbook4_manifest.get("workbook_sha256", "-"),
        }

    marker_lost = sum(case["counts"].get("marker_lost_count", 0) for case in cases.values())
    false_positive = sum(
        case["counts"].get("marker_false_positive_count", 0) for case in cases.values()
    )
    uncovered = sum(
        case["counts"].get(
            "source_substantive_requirement_without_review_coverage_count", 0
        )
        for case in cases.values()
    )
    fixtures = {
        key: value
        for key, value in load(REPORTS / CASES["case_001"]["audit"]).get("fixtures", {}).items()
    }
    star_fixtures = {
        fixture: fixtures.get(f"row:{fixture}", {}).get("status", "MISSING")
        for fixture in CASE001_STAR_FIXTURES
    }
    substantive_rows = sum(
        case["counts"].get("substantive_requirement_row_count", 0) for case in cases.values()
    )
    rejection_rows = sum(
        case["counts"].get("rejection_consequence_row_count", 0) for case in cases.values()
    )
    marked_rows = sum(
        case["counts"].get("source_marked_row_count", 0) for case in cases.values()
    )

    vocabulary_distinct = len({tuple(case["marker_vocabulary"]) for case in cases.values()}) >= 2
    flags: dict[str, object] = {
        "REVIEW_WORKBOOK_ROUND6": (
            "PASS"
            if all(case["verdict"] == "PASS" and case["visual_qa"] == "PASS" for case in cases.values())
            else "FAIL"
        ),
        "SOURCE_MARKER_FIDELITY": "PASS" if marker_lost == 0 and false_positive == 0 else "FAIL",
        "marker_lost_count": marker_lost,
        "marker_false_positive_count": false_positive,
        "SUBSTANTIVE_REQUIREMENT_CLASSIFICATION": (
            "PASS"
            if all(
                any(
                    check["ok"]
                    for check in load(REPORTS / CASES[case]["audit"])["checks"]
                    if check["check"].startswith("the tender's own substantive-requirement rule")
                )
                for case in cases
            )
            else "FAIL"
        ),
        "REJECTION_CONSEQUENCE_CLASSIFICATION": (
            "PASS"
            if all(
                any(
                    check["ok"]
                    for check in load(REPORTS / CASES[case]["audit"])["checks"]
                    if check["check"].startswith("every rejection claim traces")
                )
                for case in cases
            )
            else "FAIL"
        ),
        "source_substantive_requirement_without_review_coverage_count": uncovered,
        "CONCERN_CONTRACT": (
            "PASS" if all(case["concern_contract"] == "PASS" for case in cases.values()) else "FAIL"
        ),
        "CASE001": cases["case_001"]["verdict"],
        "CASE002": cases["case_002"]["verdict"],
        "CASE003": cases["case_003"]["verdict"],
        "THREE_CASE_GENERALIZATION": (
            "PASS"
            if vocabulary_distinct and all(case["verdict"] == "PASS" for case in cases.values())
            else "FAIL"
        ),
        "WORD_ARTIFACTS_UNCHANGED": (
            "PASS"
            if all(case["word_artifacts"]["all_byte_identical"] for case in cases.values())
            else "FAIL"
        ),
        "WORKBOOK5_UNTOUCHED": (
            "PASS" if all(case["workbook5_untouched"] for case in cases.values()) else "FAIL"
        ),
        "WORKBOOK4_UNTOUCHED": (
            "PASS"
            if priors and all(entry["untouched"] for entry in priors.values())
            else "FAIL"
        ),
        "FULL_SUITE": suite["result"],
        "CASE001_XLSX_MANUAL_REVIEW": "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW",
        "CASE002_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "CASE003_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "HUMAN_REVIEW_BOXES_TICKED": 0,
        "V1_PRODUCTION_CANDIDATE": False,
        "READY_FOR_SUBMISSION": False,
    }
    blockers = [
        f"{case}:{name}" for case, entry in cases.items() for name in entry["failed_checks"]
    ] + [
        f"{case}:fixture:{name}"
        for case, entry in cases.items()
        for name in entry["failed_fixtures"]
    ] + ([f"fixture:{name}" for name, status in star_fixtures.items() if status != "PASS"])
    if flags["SOURCE_MARKER_FIDELITY"] != "PASS":
        blockers.append("SOURCE_MARKER_FIDELITY")
    if flags["FULL_SUITE"] != "PASS":
        blockers.append("FULL_SUITE")
    if flags["WORKBOOK5_UNTOUCHED"] != "PASS":
        blockers.append("WORKBOOK5_UNTOUCHED")
    if flags["WORD_ARTIFACTS_UNCHANGED"] != "PASS":
        blockers.append("WORD_ARTIFACTS_UNCHANGED")

    head = ""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()
    except OSError:  # pragma: no cover - git missing
        head = ""

    return {
        "schema": "v1_review_workbook_round6_final_status/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round": "review_workbook_round6",
        "commit_subject": "feat: preserve substantive requirement markers in review workbook",
        "pipeline": (
            "SOURCE MARKER -> TENDER-SPECIFIC SUBSTANTIVE REQUIREMENT RULE -> "
            "CONSEQUENCE RULE -> REVIEW CRITICALITY"
        ),
        "invariant": "SOURCE-VISIBLE CRITICALITY IS SEMANTIC DATA",
        "dimensions": [
            "源标记条款数（带★）",
            "实质性要求数（源依据）",
            "明示或可证明否决项数",
        ],
        "result": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "flags": flags,
        "totals": {
            "source_marked_row_count": marked_rows,
            "substantive_requirement_row_count": substantive_rows,
            "rejection_consequence_row_count": rejection_rows,
        },
        "case001_star_fixtures": star_fixtures,
        "prior_workbooks": priors,
        "cases": cases,
        "full_test_suite": suite,
        "git_head": head,
        "human_review": {
            "records": [
                str(path)
                for path in (
                    REPORTS / "case001_review_workbook_round4_human_review.json",
                    REPORTS / "case001_review_workbook_round4_human_review_CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED.json",
                )
                if path.is_file()
            ],
            "human_verdict": "FAIL",
            "fail_reason": "SOURCE_MARKER_CRITICALITY_FIDELITY",
            "must_not_be_rewritten": True,
            "automation_may_not_mark_pass": True,
            "CASE001_XLSX_MANUAL_REVIEW": "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW",
            "CASE002_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "CASE003_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "human_checkboxes_ticked": 0,
        },
        "release": {
            "V1_PRODUCTION_CANDIDATE": False,
            "READY_FOR_SUBMISSION": False,
            "tagged": False,
            "released": False,
        },
    }


def render_markdown(status: dict) -> str:
    flags = status["flags"]
    lines = [
        "# Review workbook round 6 — source-visible criticality is semantic data",
        "",
        f"- invariant: **{status['invariant']}**",
        f"- chain: `{status['pipeline']}`",
        f"- result: **{status['result']}**",
        f"- blockers: {status['blockers'] or 'none'}",
        f"- git head: `{status['git_head']}`",
        "",
        "## Flags",
        "",
        "| flag | value |",
        "| --- | --- |",
    ]
    lines += [f"| `{key}` | `{value}` |" for key, value in flags.items()]
    lines += ["", "## Cases", "", "| case | marker vocabulary | semantics | marked rows | substantive | rejection | CC | audit | visual |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for case, entry in status["cases"].items():
        counts = entry["counts"]
        lines.append(
            f"| `{case}` | {'/'.join(entry['marker_vocabulary']) or '-'} | "
            f"{'/'.join(entry['marker_semantics']) or '-'} | "
            f"{counts.get('source_marked_row_count', 0)} | "
            f"{counts.get('substantive_requirement_row_count', 0)} | "
            f"{counts.get('rejection_consequence_row_count', 0)} | "
            f"{entry['concern_contract']} | {entry['verdict']} | {entry['visual_qa']} |"
        )
    lines += ["", "## Case-001 star fixtures", "", "| row | status |", "| --- | --- |"]
    lines += [f"| `{key}` | {value} |" for key, value in status["case001_star_fixtures"].items()]
    lines += [
        "",
        "## Full suite",
        "",
        f"- tests: {status['full_test_suite'].get('tests')}",
        f"- passed: {status['full_test_suite'].get('passed')}",
        f"- failed: {status['full_test_suite'].get('failed')}",
        f"- errors: {status['full_test_suite'].get('errors')}",
        f"- skipped: {status['full_test_suite'].get('skipped')}",
        f"- evidence: `{status['full_test_suite'].get('suite_txt')}`",
        "",
        "## Human review",
        "",
        f"- verdict: **{status['human_review']['human_verdict']}** ({status['human_review']['fail_reason']})",
        f"- CASE001 workbook: `{status['human_review']['CASE001_XLSX_MANUAL_REVIEW']}`",
        "- the automation may not rewrite this record or mark the workbook PASS",
        "",
        "## Release",
        "",
        f"- V1_PRODUCTION_CANDIDATE: `{status['release']['V1_PRODUCTION_CANDIDATE']}`",
        f"- READY_FOR_SUBMISSION: `{status['release']['READY_FOR_SUBMISSION']}`",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite-txt",
        type=Path,
        default=REPORTS / "review_workbook_round6_full_test_suite.txt",
    )
    parser.add_argument(
        "--suite-xml",
        type=Path,
        default=REPORTS / "review_workbook_round6_full_test_suite.xml",
    )
    args = parser.parse_args(argv)
    status = build_status(args)
    json_path = REPORTS / "review_workbook_round6_final_status.json"
    md_path = REPORTS / "review_workbook_round6_final_status.md"
    json_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(status), encoding="utf-8")
    print(f"REVIEW_WORKBOOK_ROUND6={status['flags']['REVIEW_WORKBOOK_ROUND6']}")
    for key, value in status["flags"].items():
        print(f"  {key}={value}")
    print(f"blockers: {status['blockers'] or 'none'}")
    print(f"-> {json_path.name}, {md_path.name}")
    return 0 if status["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
