"""Round-3 final status: aggregate the review-workbook round-3 evidence.

Reads the round-3 build/gate/content-quality/visual-QA reports and the persisted
full-suite evidence, then writes:

    acceptance/reports/v1_generalization/review_workbook_round3_final_status.json
    acceptance/reports/v1_generalization/review_workbook_round3_final_status.md

Exit code 0 only when every machine gate is PASS and every human confirmation is
still absent (no checkbox may be ticked by this tool).
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
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook3",
    "case_002": "v1_round4_closure8_review_workbook3",
    "case_003": "v1_round4_closure8_review_workbook3",
}

#: round-2 visual-QA baselines (bounded-clipping warnings), for comparison only
VISUAL_BASELINE = {"case_001": 10, "case_002": 17, "case_003": 26}


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
    match = re.search(
        r"PASSED=(\d+)\s+SKIPPED=(\d+)\s+FAILED=(\d+)\s+ERRORS=(\d+)", text
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
    parser.add_argument("--out", type=Path, default=REPORTS / "review_workbook_round3_final_status.json")
    parser.add_argument("--md", type=Path, default=REPORTS / "review_workbook_round3_final_status.md")
    args = parser.parse_args(argv)

    cases: dict[str, dict] = {}
    blockers: list[str] = []
    for case, build_id in CASES.items():
        build = _load(REPORTS / f"{case}_review_workbook_build_round3.json")
        gate = _load(REPORTS / f"{case}_review_workbook_gate_round3.json")
        quality = _load(REPORTS / f"review_workbook_round3_content_quality_{case}.json")
        visual = _load(REPORTS / f"{case}_review_workbook_visual_qa_round3.json")

        gate_result = str(gate.get("result", ""))
        quality_result = quality.get("result", "")
        fixtures = f"{quality.get('fixtures_passed', 0)}/{quality.get('fixtures_total', 0)}"
        warranty = (quality.get("warranty_retention_fixture") or {}).get("result", "")
        audit = (quality.get("human_style_audit") or {}).get("result", "")
        conflicts = (quality.get("conflicts") or {}).get("false_conflict_count")
        counters = quality.get("counters") or {}
        identity = build.get("artifact_identity") or {}
        visual_checks = visual.get("checks") or {}
        visual_warnings = (visual_checks.get("clipping_bounded") or {}).get("total")
        dashboard_ok = (visual_checks.get("no_clipped_dashboard_text") or {}).get("result")

        for label, ok in (
            ("gate", gate_result == "PASS"),
            ("content_quality", quality_result == "PASS"),
            ("fixtures", fixtures == "14/14"),
            ("warranty_retention", warranty == "PASS"),
            ("manual_audit", audit.startswith("20/20")),
            ("false_conflicts_zero", conflicts == 0),
            ("word_byte_identical", bool(identity) and all(e.get("byte_identical") for e in identity.values())),
            ("visual_no_clipped_dashboard_text", dashboard_ok == "PASS"),
        ):
            if not ok:
                blockers.append(f"{case}:{label}")

        cases[case] = {
            "build_dir": build.get("build_dir"),
            "workbook": build.get("workbook"),
            "workbook_sha256": build.get("workbook_sha256"),
            "workbook_bytes": build.get("workbook_bytes"),
            "requirement_rows": ((build.get("views") or {}).get("requirement_rows")),
            "word_render_repeated": build.get("word_render_repeated"),
            "word_artifacts_byte_identical": {
                name: entry.get("byte_identical") for name, entry in identity.items()
            },
            "gate_result": gate_result,
            "gate_checks_passed": gate.get("checks_passed"),
            "gate_checks_total": gate.get("checks_total"),
            "content_quality_result": quality_result,
            "source_atoms": counters.get("source_atom_count"),
            "review_concerns": counters.get("review_concern_count"),
            "review_points": counters.get("review_point_count"),
            "ownership_mismatch": {
                key: counters.get(key)
                for key in (
                    "source_concern_mismatch",
                    "numeric_concern_mismatch",
                    "material_concern_mismatch",
                    "consequence_concern_mismatch",
                    "evidence_concern_mismatch",
                    "authority_scope_mismatch",
                    "foreign_role_numeric",
                )
            },
            "fixtures": fixtures,
            "warranty_retention_fixture": warranty,
            "manual_style_audit": audit,
            "before_after_examples": len(quality.get("examples") or []),
            "false_conflict_count": conflicts,
            "true_conflict_count": (quality.get("conflicts") or {}).get("true_conflict_count"),
            "visual_qa": {
                "result": visual.get("result"),
                "bounded_clipping_warnings": visual_warnings,
                "round2_baseline_warnings": VISUAL_BASELINE.get(case),
                "no_clipped_dashboard_text": dashboard_ok,
            },
        }

    suite = _suite_counts(REPORTS / "review_workbook_round3_full_test_suite.txt")
    if suite:
        if suite["failed"] or suite["errors"]:
            blockers.append("full_suite:failed_or_errors")
    else:
        blockers.append("full_suite:evidence_missing")

    payload = {
        "schema": "v1_review_workbook_round3_final_status/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round": "review_workbook_round3",
        "commit_subject": "feat: enforce review-concern ownership in tender workbook",
        "pipeline": "SourceRequirementAtom -> ReviewConcern -> ReviewPoint -> workbook views",
        "invariant": "PROVENANCE IS NECESSARY BUT NOT SUFFICIENT (source-backed AND same concern)",
        "result": "PASS" if not blockers else "FAIL",
        "blockers": blockers,
        "cases": cases,
        "warranty_retention_semantics": {
            "case_001": {
                "PROJECT_WARRANTY": "24个月（项目/产品质保期）",
                "RETENTION_MONEY_RATIO": "5%（质保金/尾款比例）",
                "RETENTION_RELEASE_PERIOD": "12个月（质保金释放/付款期）",
                "same_keyword_same_concept": False,
                "reported_as_source_conflict": False,
            }
        },
        "gates": {
            "REVIEWPOINT_EVIDENCE_CONCERN_COHERENCE": "PASS" if not blockers else "FAIL",
            "ACTIONABILITY": "PASS" if not blockers else "FAIL",
            "CASE001_WARRANTY_RETENTION_FALSE_CONFLICT": "PASS"
            if cases.get("case_001", {}).get("warranty_retention_fixture") == "PASS"
            else "FAIL",
            "FALSE_CONFLICT_COUNT": cases.get("case_001", {}).get("false_conflict_count"),
            "CASE00{1,2,3}_REVIEW_WORKBOOK_GATE": {
                case: data["gate_result"] for case, data in cases.items()
            },
        },
        "full_test_suite": suite,
        "human_confirmations": {
            "CASE001_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "CASE002_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "CASE003_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
            "human_checkboxes_ticked": 0,
        },
        "flags": {
            "V1_PRODUCTION_CANDIDATE": False,
            "READY_FOR_SUBMISSION": False,
        },
        "release": {"tag_created": False, "release_created": False},
        "private_reference_workbooks": {
            "tracked": False,
            "usage": "STYLE_ONLY",
            "contents_copied": False,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Review workbook round 3 — final status",
        "",
        f"- result: **{payload['result']}**" + (f" ({'; '.join(blockers)})" if blockers else ""),
        f"- pipeline: `{payload['pipeline']}`",
        f"- invariant: {payload['invariant']}",
        f"- planned commit subject: `{payload['commit_subject']}`",
        "",
        "## Per-case machine gates",
        "",
        "| case | gate | quality | fixtures | warranty/retention | audit | examples | false conflicts | visual QA | Word |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case, data in cases.items():
        visual = data["visual_qa"]
        lines.append(
            f"| {case} | {data['gate_result']} {data['gate_checks_passed']}/{data['gate_checks_total']} "
            f"| {data['content_quality_result']} | {data['fixtures']} | {data['warranty_retention_fixture']} "
            f"| {data['manual_style_audit']} | {data['before_after_examples']} | {data['false_conflict_count']} "
            f"| {visual['result']} ({visual['bounded_clipping_warnings']} bounded WARNs vs round-2 "
            f"{visual['round2_baseline_warnings']}) | byte-identical: "
            f"{all(data['word_artifacts_byte_identical'].values())} |"
        )
    lines += [
        "",
        "## Ownership counters",
        "",
        "| case | atoms | concerns | points | mismatch buckets |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case, data in cases.items():
        mismatches = ", ".join(f"{key}={value}" for key, value in data["ownership_mismatch"].items())
        lines.append(
            f"| {case} | {data['source_atoms']} | {data['review_concerns']} | {data['review_points']} | {mismatches} |"
        )
    lines += [
        "",
        "## Warranty / retention semantics (CASE001)",
        "",
        "| concept | value | meaning |",
        "| --- | --- | --- |",
    ]
    for concept, value in payload["warranty_retention_semantics"]["case_001"].items():
        lines.append(f"| {concept} | {value} | — |")
    lines += [
        "",
        "- same keyword ≠ same concept; the pair is never reported as a source conflict.",
        f"- FALSE_CONFLICT_COUNT = {payload['gates']['FALSE_CONFLICT_COUNT']}",
        "",
        "## Full test suite",
        "",
        f"- collected {suite.get('collected')} · passed {suite.get('passed')} · skipped {suite.get('skipped')} "
        f"· failed {suite.get('failed')} · errors {suite.get('errors')}",
        "- evidence: `review_workbook_round3_full_test_suite.txt` / `.xml`",
        "",
        "## Human confirmations",
        "",
    ]
    for key, value in payload["human_confirmations"].items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## Flags",
        "",
        f"- V1_PRODUCTION_CANDIDATE = {payload['flags']['V1_PRODUCTION_CANDIDATE']}",
        f"- READY_FOR_SUBMISSION = {payload['flags']['READY_FOR_SUBMISSION']}",
        f"- tag/release created: {payload['release']['tag_created']}/{payload['release']['release_created']}",
        f"- private reference workbooks: tracked={payload['private_reference_workbooks']['tracked']} "
        f"({payload['private_reference_workbooks']['usage']})",
        "",
    ]
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text("\n".join(lines), encoding="utf-8")

    print(
        f"ROUND3_FINAL_STATUS {payload['result']}"
        + (f" blockers={blockers}" if blockers else "")
        + f" suite={suite.get('passed')}passed/{suite.get('failed')}failed/{suite.get('errors')}errors"
    )
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
