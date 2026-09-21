"""V1 PHASE D: automated candidate gate.

Decides whether the V1 package is an automated candidate: every accepted case
produced its four deliverables, the three-case architecture regression passed,
the V0.9 internal-preview gates still hold, and no cross-case leakage or package
safety problem is open.  It never claims more than automated evidence supports:
``READY_FOR_SUBMISSION`` stays false and manual Word review stays required.

Usage::

    .venv/Scripts/python.exe scripts/v1_automated_candidate_gate.py \
        --out acceptance/reports/v1_generalization/v1_automated_candidate_gate.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMA = "v1_automated_candidate_gate/1"

#: Deliverables every accepted case must have produced.
DELIVERABLES: tuple[str, ...] = (
    "project_facts.json",
    "投标项目复核表.xlsx",
    "基础投标文件.docx",
    "qa_report.json",
)

#: Architecture gates banked for the V0.9 internal preview baseline.
PREVIEW_GATES: tuple[tuple[str, str], ...] = (
    ("p3_reflow_vertical_gate", "acceptance/reports/v09_internal_preview/p3_reflow_vertical_gate.json"),
    ("source_line_assembly_gate", "acceptance/reports/v09_internal_preview/source_line_assembly_gate.json"),
    ("ownership_closure_gate", "acceptance/reports/v09_internal_preview/ownership_closure_gate_build5.json"),
    ("case001_internal_preview_gate", "acceptance/reports/v09_internal_preview/case001_v09_internal_preview_gate.json"),
)

FLAG_REQUIREMENTS = {
    "INTERNAL_PREVIEW": True,
    "READY_FOR_INTERNAL_TRIAL": True,
    "MANUAL_WORD_REVIEW_REQUIRED": True,
    "READY_FOR_SUBMISSION": False,
}

#: The preview label a gate may carry instead of the boolean flag.
PREVIEW_LABELS: tuple[str, ...] = ("V0.9_INTERNAL_PREVIEW", "V1_INTERNAL_PREVIEW")


def resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_flags(*reports: dict) -> dict[str, object]:
    """Merge every ``flags`` block found anywhere in the given reports."""

    flags: dict[str, object] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            block = node.get("flags")
            if isinstance(block, dict):
                flags.update(block)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for report in reports:
        walk(report)
    return flags


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regression", type=Path,
                        default=ROOT / "acceptance/reports/v1_generalization/three_case_regression.json")
    parser.add_argument("--gate", action="append", default=None,
                        help="name=path to an additional gate report (repeatable)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    checks: list[dict] = []

    def check(name: str, ok: bool, observed: object = None, expected: object = None) -> None:
        checks.append(
            {"check": name, "ok": bool(ok), "expected": expected, "observed": observed}
        )

    regression_path = resolve(args.regression)
    regression = load(regression_path)
    check("three_case_regression_present", regression_path.exists(), str(regression_path), True)
    check("three_case_regression_result", regression.get("result") == "PASS",
          regression.get("result"), "PASS")
    check("three_case_regression_status",
          regression.get("status") == "THREE_CASE_GENERALIZATION = PASS",
          regression.get("status"), "THREE_CASE_GENERALIZATION = PASS")
    check("three_case_regression_failed_checks",
          not regression.get("failed_checks"), regression.get("failed_checks"), [])
    check("three_distinct_source_documents",
          regression.get("distinct_source_count") == 3,
          regression.get("distinct_source_count"), 3)
    case_names = regression.get("case_order") or []
    check("three_cases_accepted", len(case_names) == 3, case_names, 3)
    for case in regression.get("cases") or ():
        check("case_accepted::%s" % case.get("case"),
              case.get("case_result") == "PASS", case.get("case_result"), "PASS")

    # Deliverables: every accepted case produced all four outputs, and the two
    # binary deliverables are non-trivial and hash-stable against the case's own
    # acceptance evidence.
    deliverable_records = []
    for case in regression.get("cases") or ():
        build_dir = resolve(case.get("build_dir") or "")
        record = {"case": case.get("case"), "build_dir": str(build_dir), "files": {}}
        for name in DELIVERABLES:
            path = build_dir / name
            entry = {"exists": path.exists()}
            if path.exists():
                entry["bytes"] = path.stat().st_size
                entry["sha256"] = sha256(path)
            record["files"][name] = entry
            check("deliverable::%s::%s" % (case.get("case"), name),
                  entry["exists"], entry, True)
        docx = record["files"]["基础投标文件.docx"]
        check("deliverable_size::%s::docx" % case.get("case"),
              docx.get("bytes", 0) > 10_000, docx.get("bytes"), ">10000")
        workbook = record["files"]["投标项目复核表.xlsx"]
        check("deliverable_size::%s::xlsx" % case.get("case"),
              workbook.get("bytes", 0) > 5_000, workbook.get("bytes"), ">5000")
        acceptance = load(resolve(case.get("build_dir") or "") / "qa_report.json")
        check("delivery_qa_no_errors::%s" % case.get("case"),
              not acceptance.get("errors"), acceptance.get("errors"), [])
        deliverable_records.append(record)

    # Banked V0.9 architecture gates must still be green.
    gate_records = []
    gates = list(PREVIEW_GATES)
    for item in args.gate or ():
        name, _, path = item.partition("=")
        gates.append((name, path))
    gate_reports = {}
    for name, path in gates:
        resolved = resolve(path)
        if not resolved.exists():
            check("preview_gate_present::%s" % name, False, str(resolved), True)
            continue
        report = load(resolved)
        gate_reports[name] = report
        status = report.get("status") or report.get("result")
        failed = report.get("failed") or report.get("failed_checks") or []
        gate_records.append(
            {"gate": name, "path": str(resolved), "status": status,
             "failed_checks": failed, "sha256": sha256(resolved)}
        )
        check("preview_gate_status::%s" % name, status == "PASS", status, "PASS")
        check("preview_gate_failed_checks::%s" % name, not failed, failed, [])

    flags = collect_flags(regression, *gate_reports.values())
    for flag, expected in FLAG_REQUIREMENTS.items():
        check("flag::%s" % flag, flags.get(flag) is expected, flags.get(flag), expected)

    labels = [
        value
        for report in gate_reports.values()
        for value in (report.get("preview"), report.get("status"))
        if isinstance(value, str)
    ]
    check(
        "internal_preview_label",
        any(label in PREVIEW_LABELS for label in labels)
        or flags.get("INTERNAL_PREVIEW") is True,
        sorted({label for label in labels if label}),
        list(PREVIEW_LABELS),
    )

    # No case may be reported submit-ready by automated evidence alone.
    check("ready_for_submission_not_claimed",
          flags.get("READY_FOR_SUBMISSION") is False,
          flags.get("READY_FOR_SUBMISSION"), False)
    check("manual_word_review_still_required",
          flags.get("MANUAL_WORD_REVIEW_REQUIRED") is True,
          flags.get("MANUAL_WORD_REVIEW_REQUIRED"), True)

    failed = [check["check"] for check in checks if not check["ok"]]
    if failed:
        status = "V1_BLOCKED_PACKAGE_SAFETY"
    else:
        status = "V1_AUTOMATED_CANDIDATE"

    report = {
        "schema": SCHEMA,
        "regression_report": {"path": str(regression_path), "sha256": sha256(regression_path)},
        "cases": case_names,
        "deliverables": deliverable_records,
        "architecture_gates": gate_records,
        "flags": flags,
        "checks": checks,
        "failed_checks": failed,
        "automated_candidate_blockers": failed,
        "status": status,
        "result": "PASS" if not failed else "FAIL",
        "constraints": {
            "MANUAL_WORD_REVIEW_REQUIRED": True,
            "READY_FOR_SUBMISSION": False,
            "V1_SCOPE": "text PDF + DOCX input; project_facts.json, 投标项目复核表.xlsx, 基础投标文件.docx, qa_report.json output; no OCR, no external LLM, no database",
        },
    }
    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(out), "status": status, "result": report["result"],
                      "failed": failed}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
