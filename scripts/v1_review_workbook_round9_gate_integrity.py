"""ROUND9_GATE_INTEGRITY: the first execution gate of the round-9 closure.

Round 9's locator work must not be able to weaken its own acceptance rule.  This
gate runs the round-9 delivered-content audit for every case and requires, from
the SAVED workbooks only:

* ``locator comparison = EXACT_FORMATTER_OUTPUT`` -- the expected value is the
  production formatter's own output for the row's **canonical EvidenceUnit**
  (rebuilt from the delivered document) and the comparison is equality;
* ``prefix/fuzzy matching = 0`` -- measured by negative controls over the single
  comparer, not asserted in prose;
* ``actual saved XLSX locator semantic mismatches = 0``;
* every named locator fixture PASSes (or is *not applicable* because the case's
  source states no such content at all -- a fixture never silently disappears
  when the source does state it).

The gate also records, per named fixture, the stable item id, the canonical
evidence unit, its section and clause, the expected formatter output, the locator
read back from the saved workbook, the page/section/clause/kind of both sides and
the PASS/FAIL verdict, so a human can re-derive the result without re-running the
audit.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_round9_gate_integrity.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from v1_review_workbook_round8_report import REPORTS, _sha256  # noqa: E402
from v1_review_workbook_round9_report import (  # noqa: E402
    BUILDS,
    GENERALIZATION_SCHEMA,
    GATE_SCHEMA,
    LOCATOR_FIXTURES,
    write_case_report,
)

#: The fixtures a case is expected to carry beyond the cross-case list.
CASE_FIXTURES: dict[str, tuple[str, ...]] = {
    "case_003": ("LOCATOR_CASE003_BID_BOND",),
}

#: A fixture result that satisfies the gate.
ACCEPTED_FIXTURE_RESULTS = ("PASS", "NOT_APPLICABLE")


def _named_fixture_rows(
    case: str, data: dict[str, Any]
) -> list[dict[str, Any]]:
    """One reviewer-readable row per named locator fixture of ``case``."""

    fixtures = data.get("locator_fixtures") or {}
    rows: list[dict[str, Any]] = []
    keys = [key for key, _concern, _probes in LOCATOR_FIXTURES]
    keys += list(CASE_FIXTURES.get(case, ()))
    for key in keys:
        entry = fixtures.get(key)
        if entry is None:
            # the CASE003 bond fixture is written straight into ``fixtures``
            fixture = (data.get("fixtures") or {}).get(key) or {}
            rows.append(
                {
                    "case": case,
                    "fixture": key,
                    "result": "FAIL" if fixture.get("status") != "PASS" else "PASS",
                    "resolution": "case_fixture",
                    "record": None,
                    "detail": fixture.get("detail") or "",
                }
            )
            continue
        records = entry.get("records") or []
        rows.append(
            {
                "case": case,
                "fixture": key,
                "concern_id": entry.get("concern_id"),
                "probes": entry.get("probes"),
                "resolution": entry.get("resolution"),
                "item_ids": entry.get("item_ids"),
                "records": records,
                "result": entry.get("result"),
            }
        )
    return rows


def _case_gate(case: str, data: dict[str, Any]) -> dict[str, Any]:
    counts = data.get("counts") or {}
    records = data.get("locator_records") or []
    named = _named_fixture_rows(case, data)
    failures: list[str] = []
    if data.get("verdict") != "PASS":
        failures.append("case_verdict")
    if counts.get("LOCATOR_COHERENCE_PROBLEM_COUNT"):
        failures.append("locator_semantic_mismatch")
    if counts.get("LOCATOR_PREFIX_OR_FUZZY_ACCEPTANCE_COUNT"):
        failures.append("prefix_or_fuzzy_acceptance")
    if counts.get("LOCATOR_CLIP_IDENTITY_PROBLEM_COUNT"):
        failures.append("clipped_locator_identity")
    for record in records:
        if record.get("result") != "PASS":
            failures.append(f"record:{record.get('item_id')}")
    for row in named:
        if row.get("result") not in ACCEPTED_FIXTURE_RESULTS:
            failures.append(f"fixture:{row['fixture']}")
    return {
        "build_id": data.get("build_id"),
        "workbook": data.get("workbook"),
        "workbook_sha256": data.get("workbook_sha256"),
        "verdict": data.get("verdict"),
        "failed_checks": data.get("failed_checks"),
        "failed_fixtures": (data.get("fixture_summary") or {}).get("failed"),
        "locator_rows_checked": counts.get("LOCATOR_ROWS_CHECKED"),
        "locator_semantic_mismatches": counts.get("LOCATOR_COHERENCE_PROBLEM_COUNT"),
        "prefix_or_fuzzy_acceptances": counts.get(
            "LOCATOR_PREFIX_OR_FUZZY_ACCEPTANCE_COUNT"
        ),
        "clipped_sections": counts.get("LOCATOR_CLIPPED_SECTION_COUNT"),
        "clip_identity_problems": counts.get("LOCATOR_CLIP_IDENTITY_PROBLEM_COUNT"),
        "named_fixtures": named,
        "gate_failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=None)
    parser.add_argument("--three-case", action="store_true")
    parser.add_argument(
        "--round10",
        action="store_true",
        help="re-verify the same locator contract on the round-10 successors",
    )
    parser.add_argument(
        "--round11",
        action="store_true",
        help="re-verify the same locator contract on the round-11 successors",
    )
    parser.add_argument(
        "--round12",
        action="store_true",
        help="re-verify the same locator contract on the round-12 successors",
    )
    parser.add_argument("--out", help="report path (default: the round's own gate file)")
    args = parser.parse_args(argv)
    cases = list(BUILDS) if args.three_case or not args.case else args.case

    if args.round12:
        # The locator contract is stage-, structure- and delivery-text-independent,
        # so the same exact-formatter gate must still hold on the round-12
        # successors -- the ones whose *delivered cells* round 12 changed.  Every
        # artifact is written under the round-12 stem, so no round-9/10/11 evidence
        # file is rewritten.
        import v1_review_workbook_round9_report as round9

        from v1_review_workbook_round12_report import BUILDS as ROUND12_BUILDS
        from v1_review_workbook_round12_report import write_case_report as write12

        round9.BUILDS = dict(ROUND12_BUILDS)
        _case_report_writer = write12
        # its own file: the round-12 delivery-text generalization (written by the
        # round-12 report) is a different conclusion and must survive alongside
        _generalization_stem = "review_workbook_round12_locator_generalization.json"
        _gate_label = "ROUND12_LOCATOR_GATE"
    elif args.round11:
        # The locator contract is stage- and structure-independent, so the same
        # exact-formatter gate must hold on the round-11 successors.  Every
        # artifact is written under the round-11 stem, so no round-9/10 evidence
        # file is rewritten.
        import v1_review_workbook_round9_report as round9

        from v1_review_workbook_round11_report import BUILDS as ROUND11_BUILDS
        from v1_review_workbook_round11_report import write_case_report as write11

        round9.BUILDS = dict(ROUND11_BUILDS)
        _case_report_writer = write11
        _generalization_stem = "review_workbook_round11_generalization.json"
        _gate_label = "ROUND11_LOCATOR_GATE"
    elif args.round10:
        # The locator contract is stage-independent, so the same gate must hold on
        # the round-10 successors.  Rebind the round-9 report's BUILDS for this run
        # only, and write every artifact under the round-10 stem, so no round-9
        # evidence file is rewritten.
        import v1_review_workbook_round9_report as round9

        from v1_review_workbook_round10_report import BUILDS as ROUND10_BUILDS

        round9.BUILDS = dict(ROUND10_BUILDS)

        def _write_round10_case_report(case: str) -> dict[str, Any]:
            from v1_review_workbook_round10_report import write_case_report as write10

            return write10(case)

        _case_report_writer = _write_round10_case_report
        _generalization_stem = "review_workbook_round10_generalization.json"
        _gate_label = "ROUND10_LOCATOR_GATE"
    else:
        _case_report_writer = write_case_report
        _generalization_stem = "review_workbook_round9_generalization.json"
        _gate_label = "ROUND9_GATE_INTEGRITY"

    results: dict[str, dict[str, Any]] = {}
    for case in cases:
        results[case] = _case_report_writer(case)

    case_gates = {case: _case_gate(case, data) for case, data in results.items()}
    named_rows = [row for case in cases for row in case_gates[case]["named_fixtures"]]
    failed_cases = [case for case, gate in case_gates.items() if gate["gate_failures"]]
    semantic_mismatches = sum(
        int(gate["locator_semantic_mismatches"] or 0) for gate in case_gates.values()
    )
    fuzzy_acceptances = sum(
        int(gate["prefix_or_fuzzy_acceptances"] or 0) for gate in case_gates.values()
    )
    verdict = "PASS" if not failed_cases and not semantic_mismatches else "FAIL"

    report = {
        "schema": GATE_SCHEMA,
        "round": 9,
        "locator_comparison": "EXACT_FORMATTER_OUTPUT",
        "matcher": "tender_basic.evidence_unit.locators_match_exactly",
        "expected_source": (
            "canonical EvidenceUnit rebuilt from the delivered document -> "
            "tender_basic.evidence_unit.expected_locator_for_unit -> "
            "compared with the locator parsed from the SAVED/REOPENED XLSX cell"
        ),
        "actual_source": "SAVED_XLSX",
        "prefix_or_fuzzy_comparison_count": fuzzy_acceptances,
        "actual_saved_xlsx_locator_semantic_mismatch_count": semantic_mismatches,
        "named_fixture_count": len(named_rows),
        "named_fixtures": named_rows,
        "cases": case_gates,
        "workbook_identity": {
            case: {
                "path": results[case].get("workbook"),
                "sha256": results[case].get("workbook_sha256"),
            }
            for case in cases
        },
        "failed_cases": failed_cases,
        "verdict": verdict,
    }
    # the verified XLSX identity is also pinned from disk, never from the audit's
    # own string, so the gate names an artifact that exists right now
    for case in cases:
        path = ROOT / str(results[case].get("workbook") or "")
        if path.is_file():
            report["workbook_identity"][case]["sha256_on_disk"] = _sha256(path)
            report["workbook_identity"][case]["sha256_matches"] = (
                _sha256(path) == results[case].get("workbook_sha256")
            )
        else:
            report["workbook_identity"][case]["sha256_matches"] = False
            verdict = report["verdict"] = "FAIL"
    if any(
        not entry.get("sha256_matches") for entry in report["workbook_identity"].values()
    ):
        failed_cases = report["failed_cases"] = sorted(
            set(failed_cases) | {"workbook_identity"}
        )

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / (args.out or "round9_gate_integrity.json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    generalization = {
        "schema": GENERALIZATION_SCHEMA,
        "cases": {
            case: {
                "verdict": data["verdict"],
                "failed_checks": data["failed_checks"],
                "failed_fixtures": data["fixture_summary"]["failed"],
                "counts": data["counts"],
            }
            for case, data in results.items()
        },
        "verdict": (
            "PASS" if all(data["verdict"] == "PASS" for data in results.values()) else "FAIL"
        ),
    }
    (REPORTS / _generalization_stem).write_text(
        json.dumps(generalization, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"{_gate_label} = {report['verdict']}")
    print(f"locator comparison = {report['locator_comparison']}")
    print(f"prefix/fuzzy matching = {report['prefix_or_fuzzy_comparison_count']}")
    print(
        "actual saved XLSX locator semantic mismatches = "
        f"{report['actual_saved_xlsx_locator_semantic_mismatch_count']}"
    )
    for case, gate in case_gates.items():
        print(
            f"  {case}: rows={gate['locator_rows_checked']} "
            f"fixtures={len(gate['named_fixtures'])} failures={gate['gate_failures']}"
        )
    for row in named_rows:
        if row.get("result") not in ACCEPTED_FIXTURE_RESULTS:
            print(f"  FIXTURE FAIL {row['case']}/{row['fixture']}: {json.dumps(row, ensure_ascii=False)[:400]}")
    print(f"gate: {path.relative_to(ROOT).as_posix()}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
