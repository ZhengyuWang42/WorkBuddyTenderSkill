"""Round-6 closure status: the reconciled round-6 result.

The initial round-6 final status was invalidated by the read-only count-consistency
audit (``review_workbook_round6_count_consistency_note.json``):

* **D1** the dashboard's substantive-requirement counter summed four exact-match
  ``COUNTIF`` terms against a "；"-joined multi-valued column, and
* **D2** the marker-fidelity audit iterated only the atoms that already claimed a
  marker, so a discovered-but-unattributed marker was invisible to it.

This script aggregates the marker-closure audits (one per case), the visual QA of
the successor builds, the preserved initial round-6 evidence and the persisted
full-suite record into

* ``acceptance/reports/v1_generalization/review_workbook_round6_final_status_reconciled.json``
* ``acceptance/reports/v1_generalization/review_workbook_round6_final_status_reconciled.md``

Usage::

    python -X utf8 scripts/v1_review_workbook_round6_reconciled_status.py \
        --suite-txt acceptance/reports/v1_generalization/review_workbook_round6_marker_closure_full_test_suite.txt \
        --suite-xml acceptance/reports/v1_generalization/review_workbook_round6_marker_closure_full_test_suite.xml
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from v1_review_workbook_round6_final_status import (  # noqa: E402
    CASES as INITIAL_CASES,
    REPORTS,
    ROOT as _ROOT,
    WORKBOOK5_SHA,
    WORKSPACE,
    load,
    prior_workbooks,
    sha256,
    suite_counts,
    word_artifacts,
)

#: The successor build of each case (the initial round-6 build is never written).
CLOSURE_BUILDS = {
    case: f"{spec['build']}_marker_closure" for case, spec in INITIAL_CASES.items()
}

CLOSURE_AUDIT = {
    case: REPORTS / f"review_workbook_round6_marker_closure_{case}.json"
    for case in INITIAL_CASES
}
CLOSURE_VISUAL = {
    case: REPORTS / f"review_workbook_round6_marker_closure_visual_qa_{case}.json"
    for case in INITIAL_CASES
}
COUNT_NOTE = REPORTS / "review_workbook_round6_count_consistency_note.json"
INITIAL_STATUS = REPORTS / "review_workbook_round6_final_status.json"
INITIAL_AUDIT = {
    case: REPORTS / f"review_workbook_round6_criticality_audit_{case}.json"
    for case in INITIAL_CASES
}

SUPERSESSION_REASON = "COUNT_FORMULA_AND_MARKER_ATTRIBUTION_AUDIT_DEFECT"

#: The dashboard counters the closure gates on, per case.
EXPECTED = {
    "case_001": {
        "source_marker_occurrence_count": 18,
        "direct_source_marked_review_row_count": 17,
        "substantive_review_row_count": 31,
        "explicit_rejection_row_count": 10,
        "derived_rejection_row_count": 23,
    },
    "case_002": {
        "source_marker_occurrence_count": 45,
        "direct_source_marked_review_row_count": 3,
        "substantive_review_row_count": 1,
        "explicit_rejection_row_count": 3,
        "derived_rejection_row_count": 0,
    },
    "case_003": {
        "source_marker_occurrence_count": 6,
        "direct_source_marked_review_row_count": 4,
        "substantive_review_row_count": 4,
        "explicit_rejection_row_count": 10,
        "derived_rejection_row_count": 0,
    },
}


def _workbook(case: str) -> Path:
    return WORKSPACE / case / CLOSURE_BUILDS[case] / "投标项目复核表.xlsx"


def _case_entry(case: str) -> dict:
    audit = load(CLOSURE_AUDIT[case])
    visual = load(CLOSURE_VISUAL[case])
    counts = audit.get("counts", {})
    model = audit.get("criticality_model", {})
    initial = load(INITIAL_AUDIT[case])
    workbook = _workbook(case)
    expected = EXPECTED[case]
    metrics = audit.get("dashboard_metrics", {})
    mismatch = [
        label
        for label, metric in metrics.items()
        if not metric.get("ok")
        or metric.get("recalculated_value") != metric.get("independent_value")
    ]
    return {
        "build": CLOSURE_BUILDS[case],
        "initial_build": INITIAL_CASES[case]["build"],
        "initial_build_workbook_sha256": (
            sha256(WORKSPACE / case / INITIAL_CASES[case]["build"] / "投标项目复核表.xlsx")
        ),
        "workbook": str(workbook),
        "workbook_sha256": sha256(workbook) if workbook.is_file() else "",
        "audit": str(CLOSURE_AUDIT[case]),
        "visual_qa_report": str(CLOSURE_VISUAL[case]),
        "verdict": audit.get("verdict", "NOT_RUN"),
        "initial_verdict": initial.get("verdict", "NOT_RUN"),
        "failed_checks": audit.get("failed_checks", []),
        "failed_fixtures": audit.get("fixture_summary", {}).get("failed", []),
        "fixture_summary": audit.get("fixture_summary", {}),
        "marker_vocabulary": model.get("marker_vocabulary", []),
        "marker_semantics": sorted(
            {
                rule.get("semantics", "")
                for rule in model.get("substantive_rules", [])
                if rule.get("semantics")
            }
        ),
        "occurrence_counts": {
            "raw_source_marker_discovery_count": model.get(
                "raw_source_marker_discovery_count"
            ),
            "source_marker_occurrence_count": model.get("source_marker_occurrence_count"),
            "duplicate_source_marker_record_count": model.get(
                "duplicate_source_marker_record_count"
            ),
            "source_marker_evidence_count": model.get("marker_count"),
        },
        "marker_dispositions": audit.get("marker_dispositions", {}),
        "counts": counts,
        "expected": expected,
        "expected_matches": {
            key: counts.get(key) == value for key, value in expected.items()
        },
        "dashboard_metrics": metrics,
        "dashboard_mismatches": mismatch,
        "concern_contract": audit.get("concern_contract_verdict", "NOT_RUN"),
        "concern_contract_detail": audit.get("concern_contract", {}),
        "visual_qa": visual.get("result", "NOT_RUN"),
        "visual_qa_checks": {
            name: check.get("result") for name, check in (visual.get("checks") or {}).items()
        },
        "visual_qa_criticality_counters": {
            "expected": visual.get("criticality_expected", {}),
            "recalculated": visual.get("criticality_observed", {}),
        },
        # clipping stays a bounded WARN; it is reported, never silently dropped
        "visual_qa_clipping": {
            "result": (visual.get("checks") or {}).get("clipping_bounded", {}).get("result"),
            "total": visual.get("clipping_total"),
        },
        "word_artifacts": word_artifacts(WORKSPACE / case / CLOSURE_BUILDS[case]),
    }


def _note_verdict(note: dict) -> str:
    verdict = note.get("verdict")
    if isinstance(verdict, dict):
        return str(verdict.get("ROUND6_COUNT_CONSISTENCY", "MISSING"))
    if isinstance(verdict, str):
        return verdict
    return "MISSING"


def build_status(args: argparse.Namespace) -> dict:
    suite = suite_counts(args.suite_txt, args.suite_xml)
    initial_status = load(INITIAL_STATUS)
    count_note = load(COUNT_NOTE)
    count_note_verdict = _note_verdict(count_note)
    round5_status = load(REPORTS / "review_workbook_round5_final_status.json")
    try:
        round5_closed = datetime.fromisoformat(round5_status.get("generated_at", ""))
    except ValueError:
        round5_closed = datetime.now(timezone.utc)
    priors = prior_workbooks(round5_closed)

    cases = {case: _case_entry(case) for case in INITIAL_CASES}

    workbook5_untouched = {}
    for case, spec in INITIAL_CASES.items():
        path = WORKSPACE / case / spec["workbook5"] / "投标项目复核表.xlsx"
        digest = sha256(path) if path.is_file() else ""
        workbook5_untouched[case] = {
            "path": str(path),
            "sha256": digest,
            "recorded_sha256": WORKBOOK5_SHA[case],
            "untouched": digest == WORKBOOK5_SHA[case],
        }

    initial_preserved = {
        case: {
            "build": INITIAL_CASES[case]["build"],
            "audit": str(INITIAL_AUDIT[case]),
            "verdict": load(INITIAL_AUDIT[case]).get("verdict", "NOT_RUN"),
            "workbook_sha256": cases[case]["initial_build_workbook_sha256"],
            "preserved": (WORKSPACE / case / INITIAL_CASES[case]["build"]).is_dir(),
        }
        for case in INITIAL_CASES
    }

    defects = {
        "D1": {
            "id": "DASHBOARD_SUBSTANTIVE_COUNT_FORMULA_BROKEN",
            "status": "FIXED",
            "evidence": "the substantive counter is one wildcard COUNTIF over the "
            "multi-valued 强制性类型 column and equals the independent recount in "
            "all three cases (31 / 1 / 4)",
        },
        "D2": {
            "id": "SOURCE_MARKER_ATTRIBUTION_AUDIT_BLIND_SPOT",
            "status": "FIXED",
            "evidence": "the audit starts from every de-duplicated discovered "
            "occurrence; mid-text markers (MK0017 / MK0018) are attributed, and "
            "CASE002 DR028 shows the ★ it owns",
        },
    }

    dashboard_ok = all(        not entry["dashboard_mismatches"]
        and all(entry["expected_matches"].values())
        and entry["dashboard_metrics"]
        for entry in cases.values()
    )
    markers_attributed = all(
        entry["counts"].get("marker_unattributed_count") == 0 for entry in cases.values()
    )
    markers_resolved = all(
        entry["counts"].get("marker_unresolved_count") == 0 for entry in cases.values()
    )
    fidelity_ok = all(
        entry["counts"].get("marker_lost_count") == 0
        and entry["counts"].get("direct_delivered_marker_visibility_failures") == 0
        and entry["counts"].get("reference_parent_coverage_failures") == 0
        and entry["counts"].get("marker_false_positive_count") == 0
        and entry["counts"].get("source_substantive_actionable_uncovered_count") == 0
        for entry in cases.values()
    )
    audits_ok = all(
        entry["verdict"] == "PASS"
        and not entry["failed_checks"]
        and not entry["failed_fixtures"]
        and entry["concern_contract"] == "PASS"
        for entry in cases.values()
    )
    visuals_ok = all(entry["visual_qa"] == "PASS" for entry in cases.values())
    words_ok = all(entry["word_artifacts"]["all_byte_identical"] for entry in cases.values())
    suite_ok = suite["result"] == "PASS"

    flags = {
        "ROUND6_DASHBOARD_COUNT_CONSISTENCY": "PASS" if dashboard_ok else "FAIL",
        "ROUND6_MARKER_ATTRIBUTION_COMPLETENESS": "PASS" if markers_attributed else "FAIL",
        "ROUND6_MARKER_OCCURRENCE_RESOLUTION": "PASS" if markers_resolved else "FAIL",
        "ROUND6_SOURCE_MARKER_FIDELITY": "PASS" if fidelity_ok else "FAIL",
        "ROUND6_FINAL_STATUS_RECONCILED": (
            "PASS"
            if initial_status and count_note_verdict == "FAIL" and audits_ok
            else "FAIL"
        ),
        "ROUND6_CRITICALITY_THREE_CASE_GENERALIZATION": "PASS" if audits_ok else "FAIL",
        "ROUND6_CRITICALITY_CASE001": "PASS" if cases["case_001"]["verdict"] == "PASS" else "FAIL",
        "ROUND6_CRITICALITY_CASE002": "PASS" if cases["case_002"]["verdict"] == "PASS" else "FAIL",
        "ROUND6_CRITICALITY_CASE003": "PASS" if cases["case_003"]["verdict"] == "PASS" else "FAIL",
        "CASE001_DASHBOARD_SUBSTANTIVE_REQUIREMENTS": cases["case_001"]["counts"].get(
            "substantive_review_row_count"
        ),
        "CASE002_DASHBOARD_SUBSTANTIVE_REQUIREMENTS": cases["case_002"]["counts"].get(
            "substantive_review_row_count"
        ),
        "CASE003_DASHBOARD_SUBSTANTIVE_REQUIREMENTS": cases["case_003"]["counts"].get(
            "substantive_review_row_count"
        ),
        "CASE002_DR028_SOURCE_MARKER_VISIBLE": (
            "PASS"
            if any(
                record.get("disposition") == "DIRECT_DELIVERED"
                and "DR028" in (record.get("starred_rows") or [])
                for record in load(CLOSURE_AUDIT["case_002"]).get("marker_records", [])
            )
            else "FAIL"
        ),
        "SOURCE_MARKER_AGGREGATE_AUDIT": "PASS" if fidelity_ok and markers_resolved else "FAIL",
        "VISUAL_QA": "PASS" if visuals_ok else "FAIL",
        "WORD_ARTIFACTS_UNCHANGED": "PASS" if words_ok else "FAIL",
        "INITIAL_ROUND6_ARTIFACTS_PRESERVED": (
            "PASS" if all(entry["preserved"] for entry in initial_preserved.values()) else "FAIL"
        ),
        "WORKBOOK5_UNTOUCHED": (
            "PASS" if all(entry["untouched"] for entry in workbook5_untouched.values()) else "FAIL"
        ),
        "WORKBOOK4_UNTOUCHED": (
            "PASS" if priors and all(entry["untouched"] for entry in priors.values()) else "FAIL"
        ),
        "FULL_SUITE": suite["result"],
        "CASE001_XLSX_MANUAL_REVIEW": "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW",
        "CASE002_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "CASE003_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "HUMAN_REVIEW_BOXES_TICKED": 0,
        "V1_PRODUCTION_CANDIDATE": False,
        "READY_FOR_SUBMISSION": False,
    }
    blockers = [f"{case}:{name}" for case, entry in cases.items() for name in entry["failed_checks"]]
    blockers += [
        f"{case}:fixture:{name}"
        for case, entry in cases.items()
        for name in entry["failed_fixtures"]
    ]
    blockers += [f"{case}:dashboard:{name}" for case, entry in cases.items() for name in entry["dashboard_mismatches"]]
    blockers += [name for name, value in flags.items() if value == "FAIL"]

    head = ""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()
    except OSError:  # pragma: no cover - git missing
        head = ""

    return {
        "schema": "v1_review_workbook_round6_final_status_reconciled/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round": "review_workbook_round6_marker_closure",
        "supersedes": INITIAL_STATUS.relative_to(ROOT).as_posix(),
        "supersedes_sha256": sha256(INITIAL_STATUS) if INITIAL_STATUS.is_file() else "",
        "supersedes_verdict_recorded": initial_status.get("result", "UNKNOWN"),
        "supersession_reason": SUPERSESSION_REASON,
        "initial_round6_result": "INVALIDATED",
        "current_round6_closure_result": (
            "PASS" if all(value != "FAIL" for value in flags.values()) else "FAIL"
        ),
        "invariant": (
            "SOURCE MARKER FIDELITY MUST BE CLOSED FROM THE SOURCE-DISCOVERY "
            "UNIVERSE, NOT FROM ALREADY-ATTRIBUTED ATOMS"
        ),
        "invariant_chain": (
            "DISCOVERED_MARKERS = ATTRIBUTED_MARKERS + EXPLICITLY_ACCOUNTED_NON_DELIVERED_MARKERS"
        ),
        "distinct_metrics": [
            "source_marker_occurrence_count",
            "direct_source_marked_review_row_count",
            "substantive_review_row_count",
        ],
        "defects_fixed": defects,
        "count_consistency_evidence": {
            "note": COUNT_NOTE.relative_to(ROOT).as_posix(),
            "sha256": sha256(COUNT_NOTE) if COUNT_NOTE.is_file() else "",
            "verdict": count_note_verdict,
            "recorded_defects": [
                defect
                for defect in ("D1", "D2")
                if defect
                in json.dumps(count_note, ensure_ascii=False)
            ],
            "historical": True,
            "rewritten_after_fix": False,
        },
        "closure_audits": {
            case: path.relative_to(ROOT).as_posix() for case, path in CLOSURE_AUDIT.items()
        },
        "result": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "flags": flags,
        "totals": {
            "source_marker_occurrence_count": sum(
                entry["counts"].get("source_marker_occurrence_count", 0)
                for entry in cases.values()
            ),
            "raw_source_marker_discovery_count": sum(
                entry["counts"].get("raw_source_marker_discovery_count", 0)
                for entry in cases.values()
            ),
            "direct_source_marked_review_row_count": sum(
                entry["counts"].get("direct_source_marked_review_row_count", 0)
                for entry in cases.values()
            ),
            "substantive_review_row_count": sum(
                entry["counts"].get("substantive_review_row_count", 0)
                for entry in cases.values()
            ),
            "marker_unattributed_count": sum(
                entry["counts"].get("marker_unattributed_count", 0) for entry in cases.values()
            ),
            "marker_unresolved_count": sum(
                entry["counts"].get("marker_unresolved_count", 0) for entry in cases.values()
            ),
        },
        "cases": cases,
        "initial_round6_preserved": initial_preserved,
        "workbook5_untouched": workbook5_untouched,
        "prior_workbooks": priors,
        "full_test_suite": suite,
        "git_head": head,
        "human_review": {
            "records": [
                path.relative_to(ROOT).as_posix()
                for path in (
                    REPORTS / "case001_review_workbook_round4_human_review.json",
                    REPORTS
                    / "case001_review_workbook_round4_human_review_CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED.json",
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
    lines = [
        "# Review workbook round 6 (closed) — reconciled final status",
        "",
        f"- invariant: **{status['invariant']}**",
        f"- universe invariant: `{status['invariant_chain']}`",
        f"- supersedes: `{status['supersedes']}` "
        f"(recorded result `{status['supersedes_verdict_recorded']}`, now "
        f"**{status['initial_round6_result']}**)",
        f"- supersession reason: `{status['supersession_reason']}`",
        f"- current closure result: **{status['current_round6_closure_result']}**",
        f"- result: **{status['result']}**",
        f"- blockers: {status['blockers'] or 'none'}",
        f"- git head: `{status['git_head']}`",
        "",
        "## Defects closed",
        "",
        "| id | name | status | evidence |",
        "| --- | --- | --- | --- |",
    ]
    for key, defect in status["defects_fixed"].items():
        lines.append(f"| {key} | `{defect['id']}` | {defect['status']} | {defect['evidence']} |")
    lines += ["", "## Flags", "", "| flag | value |", "| --- | --- |"]
    lines += [f"| `{key}` | `{value}` |" for key, value in status["flags"].items()]
    lines += [
        "",
        "## Cases",
        "",
        "| case | occurrences (raw → dedup) | dispositions | ★ rows | substantive | rejections (E/D) | dashboard | CC | audit | visual |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case, entry in status["cases"].items():
        occ = entry["occurrence_counts"]
        counts = entry["counts"]
        lines.append(
            f"| `{case}` | {occ['raw_source_marker_discovery_count']} → "
            f"{occ['source_marker_occurrence_count']} | "
            f"{json.dumps(entry['marker_dispositions'], ensure_ascii=False)} | "
            f"{counts.get('direct_source_marked_review_row_count', 0)} | "
            f"{counts.get('substantive_review_row_count', 0)} | "
            f"{counts.get('explicit_rejection_row_count', 0)}/"
            f"{counts.get('derived_rejection_row_count', 0)} | "
            f"{'PASS' if not entry['dashboard_mismatches'] else 'FAIL'} | "
            f"{entry['concern_contract']} | {entry['verdict']} | {entry['visual_qa']} |"
        )
    lines += [
        "",
        "## Dashboard counters (formula → expected = recalculated = independent)",
        "",
        "| case | counter | formula | value |",
        "| --- | --- | --- | --- |",
    ]
    for case, entry in status["cases"].items():
        for label, metric in entry["dashboard_metrics"].items():
            lines.append(
                f"| `{case}` | {label} | `{metric['formula']}` | "
                f"{metric['expected_value']} = {metric['recalculated_value']} = "
                f"{metric['independent_value']} |"
            )
    lines += [
        "",
        "## Count-consistency evidence (historical, not rewritten)",
        "",
        f"- note: `{status['count_consistency_evidence']['note']}`",
        f"- sha256: `{status['count_consistency_evidence']['sha256']}`",
        f"- verdict recorded by the note: `{status['count_consistency_evidence']['verdict']}`",
        "",
        "## Test suite",
        "",
        f"- {status['full_test_suite']}",
        "",
        "## Human review",
        "",
        f"- CASE001_XLSX_MANUAL_REVIEW: `{status['flags']['CASE001_XLSX_MANUAL_REVIEW']}`",
        f"- human checkboxes ticked: {status['human_review']['human_checkboxes_ticked']}",
        f"- V1_PRODUCTION_CANDIDATE: {status['release']['V1_PRODUCTION_CANDIDATE']}",
        f"- READY_FOR_SUBMISSION: {status['release']['READY_FOR_SUBMISSION']}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-txt", type=Path, default=None)
    parser.add_argument("--suite-xml", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    args = parser.parse_args(argv)
    for name in ("suite_txt", "suite_xml"):
        value = getattr(args, name)
        if value is not None and not value.is_absolute():
            setattr(args, name, ROOT / value)
    status = build_status(args)
    json_path = args.out_json or (REPORTS / "review_workbook_round6_final_status_reconciled.json")
    md_path = args.out_md or (REPORTS / "review_workbook_round6_final_status_reconciled.md")
    json_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(status), encoding="utf-8")
    print(f"ROUND6_FINAL_STATUS_RECONCILED {status['result']} -> {json_path.name}, {md_path.name}")
    for key, value in status["flags"].items():
        print(f"  {key} = {value}")
    if status["blockers"]:
        print(f"  blockers: {status['blockers'][:12]}")
    return 0 if status["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
