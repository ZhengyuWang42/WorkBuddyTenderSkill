"""Round-5 three-case generalization report and §SUCCESS flag board.

The round-5 review workbook is only credible if the *independent* concern
contracts generalize: the CASE001 fixtures A..T are hand-authored, so the same
contracts must also audit CASE002 and CASE003 delivered rows without new rules.

This report reads the three round-5 reports (and the three round-4 provenance
gates run against the round-5 workbooks), recomputes every contamination
counter from the FINAL workbook cell text, and writes the §SUCCESS board.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from openpyxl import load_workbook  # noqa: E402

SCHEMA = "v1_review_workbook_round5_generalization/1"

CASE001_TOKENS = {
    "location": ("泵站", "交货地点", "郸城", "周口"),
    "credit": ("黑名单", "失信", "被执行人", "信用中国", "严重违法"),
    "agency": ("代理服务费", "成交服务费", "招标代理服务费", "采购代理服务费", "中标服务费"),
    "effectivity": ("签字盖章后生效", "合同生效", "签字日期不一致"),
    "completeness": ("无漏项", "无重复项", "重复项", "已包含一切费用", "已包含要求的一切费用"),
    "acceptance": ("验收单", "交付完成", "视为交付"),
    "cost_scope": ("单价中含", "单价含", "设备价款包含", "费用均由乙方承担"),
    "response_bond": ("响应保证金", "投标保证金"),
}

#: Section prefixes of the 04_报价与限价 view.
PRICE_SECTIONS = ("一、", "二、", "三、", "四、")


def _norm(text: object) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or ""))


@dataclass
class CaseArtifacts:
    case: str
    build: Path
    round5: dict[str, Any]
    round4: dict[str, Any] | None
    workbook: Path
    cells: dict[str, dict[str, str]] = field(default_factory=dict)
    price_sections: dict[str, int] = field(default_factory=dict)
    roles: dict[str, list[str]] = field(default_factory=dict)

    def texts(self) -> list[str]:
        return [entry["d"] for entry in self.cells.values()]

    def rows_for(self, *concern_ids: str) -> list[dict[str, str]]:
        wanted = set(concern_ids)
        return [
            entry
            for entry in self.cells.values()
            if entry.get("concern_id") in wanted
        ]

    def hits(self, token_group: str, *concern_ids: str, scope: str = "de") -> list[dict[str, str]]:
        """Rows of ``concern_ids`` whose displayed text carries a foreign token.

        ``scope`` selects which final cells are scanned: ``"d"`` is the row's own
        displayed requirement plus its review guidance, ``"de"`` additionally
        scans the evidence locator.  Cross-concern *contamination* is judged on
        the row's own text; the shared source clause may legitimately be cited by
        two split concerns (a unit-price cost scope and its acceptance milestone
        live in one clause), so the evidence cell is not part of that test.
        """

        tokens = CASE001_TOKENS[token_group]
        out: list[dict[str, str]] = []
        for entry in self.rows_for(*concern_ids):
            blob = entry["d"] if scope == "d" else entry["d"] + entry["e"] + entry["m"]
            found = [token for token in tokens if token in blob]
            if found:
                out.append({"cell": entry["cell"], "tokens": found})
        return out


def load_case(case: str, workdir: Path, build: Path, round4_path: Path | None = None) -> CaseArtifacts:
    """Load one case: round-5 report, round-4 gate result and final cell text."""

    report_path = workdir / f"r5_{case}.json"
    artifacts = CaseArtifacts(
        case=case,
        build=build,
        round5=json.loads(report_path.read_text(encoding="utf-8")),
        round4=json.loads(round4_path.read_text(encoding="utf-8"))
        if round4_path and round4_path.exists()
        else None,
        workbook=build / "投标项目复核表.xlsx",
    )
    by_item = {row["item_id"]: row for row in artifacts.round5.get("rows", [])}
    for row in artifacts.round5.get("rows", []):
        artifacts.cells[row["item_id"]] = {
            "concern_id": str(row["concern_id"]),
            "cell": row["cell"],
            "d": str(row["displayed_source_requirement"]),
            "e": str(row["displayed_evidence"]),
            "m": str(row["displayed_note"]),
        }
    workbook = load_workbook(artifacts.workbook, data_only=True)
    if "04_报价与限价" in workbook.sheetnames:
        sheet = workbook["04_报价与限价"]
        current = None
        for values in sheet.iter_rows(values_only=True):
            first = str(values[0]) if values and values[0] is not None else ""
            if first.startswith(PRICE_SECTIONS):
                current = first[:2]
                artifacts.price_sections[current] = 0
                continue
            if current and values and any(value not in (None, "") for value in values):
                artifacts.price_sections[current] += 1
    # numeric roles as the plan declares them (independent of the rendered text)
    for entry in artifacts.round5.get("rows", []):
        for item in entry.get("numeric_role_values", []):
            artifacts.roles.setdefault(str(item.get("role", "")), []).append(str(item.get("value", "")))
        for role in entry.get("numeric_roles", []):
            artifacts.roles.setdefault(role, [])
    return artifacts


def _flags(cases: dict[str, CaseArtifacts], full_suite: tuple[int, int] | None) -> dict[str, Any]:
    c1 = cases["case_001"]
    c2 = cases["case_002"]
    c3 = cases["case_003"]

    def check_ok(report: dict[str, Any], name: str) -> bool:
        return any(entry["check"] == name and entry["ok"] for entry in report.get("checks", []))

    quality = c1.hits("location", "QUALITY_TARGET")
    validity = c1.hits("credit", "BID_VALIDITY")
    payment = c1.hits("agency", "CONTRACT_PAYMENT") + c1.hits("effectivity", "CONTRACT_PAYMENT")
    performance = c1.hits("response_bond", "PERFORMANCE_BOND")
    completeness = c1.hits("completeness", "PRICING_COMPLETENESS", "PRICE_COMPLETENESS", scope="d")
    price_acceptance = c1.hits("acceptance", "PRICE_INCLUDED_COST_SCOPE", scope="d") + c1.hits(
        "cost_scope", "DELIVERY_ACCEPTANCE_COMPLETION", scope="d"
    )
    technical_acceptance = c1.hits("cost_scope", "TECHNICAL_STANDARD_COMPLIANCE", scope="d") + c1.hits(
        "acceptance", "TECHNICAL_STANDARD_COMPLIANCE", scope="d"
    )
    retention_95 = [
        entry["cell"]
        for entry in c1.cells.values()
        if re.search(r"质保金比例\s*为?\s*95\s*%", _norm(entry["d"]))
    ]

    roles = c1.roles
    def has(role: str, value: str) -> bool:
        return value in ",".join(roles.get(role, []))

    fixtures = c1.round5.get("fixtures", {})
    fixtures_pass = [key for key, value in fixtures.items() if value["status"] == "PASS"]
    fixtures_fail = [key for key, value in fixtures.items() if value["status"] == "FAIL"]
    audit_total = c1.round5.get("delivered_row_audit_count", 0)
    audit_failed = c1.round5.get("delivered_row_audit_failed_count", 0)

    case_reports = {case: cases[case].round5 for case in cases}
    r4_verdicts = {
        case: (cases[case].round4 or {}).get("verdict", "NOT_RUN") for case in cases
    }

    flags: dict[str, Any] = {
        "REVIEW_WORKBOOK_ROUND5": "PASS"
        if all(not [c for c in report["checks"] if not c["ok"]] for report in case_reports.values())
        and all(report["fixtures_failed"] == 0 for report in case_reports.values())
        else "FAIL",
        "ALL_CASE001_FINAL_ROWS_CONCERN_CONTRACT": "PASS"
        if check_ok(c1.round5, "all_case001_final_rows_concern_contract")
        else "FAIL",
        "QUALITY_LOCATION_CONTAMINATION": len(quality),
        "VALIDITY_BLACKLIST_CONTAMINATION": len(validity),
        "CONTRACT_PAYMENT_FOREIGN_CLAUSE": len(payment),
        "PERFORMANCE_BOND_RESPONSE_BOND_EVIDENCE": len(performance),
        "UNSUPPORTED_PRICE_COMPLETENESS_ASSERTIONS": len(completeness),
        "PRICE_ACCEPTANCE_MIXED_CONCERNS": len(price_acceptance),
        "TECHNICAL_ACCEPTANCE_MIXED_CONCERNS": len(technical_acceptance),
        "PAYMENT_RATIO_95_AS_RETENTION": bool(retention_95),
        "RETENTION_RATIO": "5%" if has("RETENTION_MONEY_RATIO", "5%") else "MISSING",
        "RETENTION_RELEASE": "12 months" if has("RETENTION_RELEASE_MONTHS", "12个月") else "MISSING",
        "PROJECT_WARRANTY": "24 months" if has("PROJECT_WARRANTY_MONTHS", "24个月") else "MISSING",
        "BANK_ACCEPTANCE_RATIO_SEPARATE": bool(roles.get("BANK_ACCEPTANCE_RATIO"))
        and bool(roles.get("PAYMENT_RATIO")),
        "FALSE_PLATFORM_CONFLICTS": sum(
            int(report.get("qa", {}).get("false_platform_conflict_count", 0) or 0)
            for report in case_reports.values()
        ),
        "CASE001_FIXTURES_A_TO_T": f"{len(fixtures_pass)}/{len(fixtures)} PASS",
        "CASE001_FINAL_WORKBOOK_AUDIT": (
            "ALL/ALL coherent" if audit_failed == 0 and audit_total else f"{audit_total - audit_failed}/{audit_total}"
        ),
        "CASE001": "PASS" if not fixtures_fail and not audit_failed else "FAIL",
        "CASE002": "PASS" if check_ok(c2.round5, "all_case001_final_rows_concern_contract") else "FAIL",
        "CASE003": "PASS" if check_ok(c3.round5, "all_case001_final_rows_concern_contract") else "FAIL",
        "THREE_CASE_GENERALIZATION": "PASS"
        if all(r4_verdicts[case] == "PASS" for case in cases)
        and all(
            cases[case].round5["delivered_row_audit_failed_count"] == 0 for case in cases
        )
        else "FAIL",
        "WORD_ARTIFACTS_UNCHANGED": "PASS"
        if all(check_ok(cases[case].round5, "word_artifacts_unchanged") for case in cases)
        else "FAIL",
        "FULL_SUITE": "PASS" if (full_suite is not None and full_suite[1] == 0 and full_suite[0] > 0) else "NOT_RUN",
        "V1_PRODUCTION_CANDIDATE": False,
        "READY_FOR_SUBMISSION": False,
    }
    flags["_evidence"] = {
        "case_round5_checks": {
            case: f"{len([c for c in report['checks'] if c['ok']])}/{len(report['checks'])}"
            for case, report in case_reports.items()
        },
        "case_row_audit": {
            case: f"{cases[case].round5['delivered_row_audit_count'] - cases[case].round5['delivered_row_audit_failed_count']}"
            f"/{cases[case].round5['delivered_row_audit_count']}"
            for case in cases
        },
        "case_round4_verdict": r4_verdicts,
        "quality_location_rows": quality,
        "validity_blacklist_rows": validity,
        "contract_payment_foreign_rows": payment,
        "performance_bond_rows": performance,
        "price_completeness_rows": completeness,
        "price_acceptance_rows": price_acceptance,
        "technical_acceptance_rows": technical_acceptance,
        "retention_95_rows": retention_95,
        "numeric_roles": roles,
        "fixtures_failed": fixtures_fail,
        "full_suite": full_suite,
        "price_sections": {case: cases[case].price_sections for case in cases},
        "workbook_sha256": {
            case: cases[case].round5.get("workbook_sha256", "") for case in cases
        },
    }
    return flags


def read_full_suite(path: Path | None, xml: Path | None) -> tuple[int, int] | None:
    if xml is not None and xml.exists():
        text = xml.read_text(encoding="utf-8", errors="replace")
        root = re.search(r"<testsuite\s[^>]*>", text)
        if root:
            def _attr(name: str) -> int | None:
                found = re.search(rf'{name}="(\d+)"', root.group(0))
                return int(found.group(1)) if found else None

            tests, errors, failures = _attr("tests"), _attr("errors"), _attr("failures")
            if None not in (tests, errors, failures):
                return (tests, errors + failures)
    if path is not None and path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"(\d+) passed", text)
        failed = re.search(r"(\d+) failed", text)
        errors = re.search(r"(\d+) error", text)
        if match:
            return (
                int(match.group(1)),
                (int(failed.group(1)) if failed else 0) + (int(errors.group(1)) if errors else 0),
            )
    return None


def render_markdown(flags: dict[str, Any], cases: dict[str, CaseArtifacts]) -> str:
    evidence = flags.pop("_evidence", {})
    lines = [
        "# Round 5 — independent concern contracts (three-case generalization)",
        "",
        "> PROVENANCE CONSISTENCY IS NOT SEMANTIC VALIDATION.",
        "",
        "| flag | value |",
        "| --- | --- |",
    ]
    for key, value in flags.items():
        lines.append(f"| `{key}` | {value} |")
    lines += ["", "## Evidence", "", "```json", json.dumps(evidence, ensure_ascii=False, indent=1), "```"]
    lines += ["", "## Cases", "", "| case | build | rows audited | checks | fixtures |", "| --- | --- | --- | --- | --- |"]
    for case, artifacts in cases.items():
        report = artifacts.round5
        lines.append(
            f"| {case} | `{artifacts.build.name}` | {report['delivered_row_audit_count']} | "
            f"{evidence['case_round5_checks'][case]} | {report['fixtures_passed']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, help="directory holding r5_<case>.json / r4_on_w5_<case>.json")
    parser.add_argument("--case001", required=True)
    parser.add_argument("--case002", required=True)
    parser.add_argument("--case003", required=True)
    parser.add_argument("--round4-case001", default="")
    parser.add_argument("--round4-case002", default="")
    parser.add_argument("--round4-case003", default="")
    parser.add_argument("--full-suite", default="")
    parser.add_argument("--full-suite-xml", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--md", default="")
    args = parser.parse_args(argv)

    workdir = Path(args.workdir)
    cases = {
        "case_001": load_case(
            "case_001", workdir, Path(args.case001),
            Path(args.round4_case001) if args.round4_case001 else None,
        ),
        "case_002": load_case(
            "case_002", workdir, Path(args.case002),
            Path(args.round4_case002) if args.round4_case002 else None,
        ),
        "case_003": load_case(
            "case_003", workdir, Path(args.case003),
            Path(args.round4_case003) if args.round4_case003 else None,
        ),
    }
    suite = read_full_suite(
        Path(args.full_suite) if args.full_suite else None,
        Path(args.full_suite_xml) if args.full_suite_xml else None,
    )
    flags = _flags(cases, suite)
    payload = {
        "schema": SCHEMA,
        "flags": {key: value for key, value in flags.items() if not key.startswith("_")},
        "evidence": flags.get("_evidence", {}),
        "cases": {
            case: {
                "build": str(artifacts.build),
                "workbook": str(artifacts.workbook),
                "round5_checks": artifacts.round5["checks"],
                "fixtures": artifacts.round5["fixtures"],
                "round4_verdict": (artifacts.round4 or {}).get("verdict", "NOT_RUN"),
            }
            for case, artifacts in cases.items()
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.md:
        Path(args.md).write_text(render_markdown(dict(flags), cases), encoding="utf-8")
    failed = [
        key
        for key, value in payload["flags"].items()
        if value in {"FAIL", "MISSING", "NOT_RUN"}
        or (isinstance(value, int) and not isinstance(value, bool) and value and key.isupper())
    ]
    print(json.dumps({"flags": payload["flags"], "failed": failed, "out": str(out)}, ensure_ascii=False, indent=1))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
