"""Round-2 content-quality report for the tender review workbook.

The report compares the delivered review text of the accepted round with the
re-synthesized review points of this round, applies the CASE001 known-bad
fixtures from the round-2 brief, and writes both the machine-readable report and
its markdown companion.  It never edits a build.

Usage::

    .venv\\Scripts\\python.exe -X utf8 scripts\\v1_review_workbook_round2_report.py \\
        --build acceptance/workspace/case_001/<round2 build> \\
        --before acceptance/workspace/case_001/<round1 build> \\
        --case case_001 \\
        --out acceptance/reports/v1_generalization/review_workbook_round2_content_quality.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from openpyxl import load_workbook  # noqa: E402

from tender_basic.document_models import NormalizedDocument  # noqa: E402
from tender_basic.dynamic_review import (  # noqa: E402
    build_dynamic_review_plan,
    dynamic_review_qa,
    order_review_items,
)
from tender_basic.models import ProjectFacts  # noqa: E402
from tender_basic.review_point import (  # noqa: E402
    NEVER_USABLE_ROLES,
    ROLES_BY_TYPE,
    _claim_text,
    render_review_cell,
    scan_review_point,
    scan_review_points,
)

DELIVERED_SHEET = "投标项目复核表"
CHECKLIST_START_ROW = 9

#: Boilerplate the round-2 brief requires to disappear.
GENERIC_PHRASES = (
    "按上述招标文件条款逐项核对响应文件对应内容，确认完全响应。",
    "响应内容与上述招标文件条款一致。",
    "具体指标：",
    "须核对的具体值：",
)

SECTION_RE = re.compile(r"(招标文件要求|复核动作|核验标准|复核要点|通过标准|不满足后果|评分提示|准备材料)[：:]")
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

#: CASE001 tokens that must never reappear in a synthesized review line.
SIGNATURE_BAD_TOKENS = ("48小时", "69152076")
SUBMISSION_BAD_TOKENS = ("具体指标：0元", "0元")
FEE_BAD_TOKEN = "300元"
MEMBER_TOKENS = ("2人", "3人")
CONTRACT_BAD_TOKEN = "单位负责人为同一人"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_case(build: Path):
    document = NormalizedDocument.model_validate_json(
        (build / "normalized_document.json").read_text(encoding="utf-8")
    )
    facts = ProjectFacts.model_validate_json(
        (build / "project_facts.json").read_text(encoding="utf-8")
    )
    plan = build_dynamic_review_plan(document, facts)
    qa = dynamic_review_qa(plan, document, facts)
    return document, facts, plan, qa


def delivered_rows(build: Path) -> list[tuple[str, str, str]]:
    """(item_id, type/topic key, review text) for the delivered sheet's rows.

    The row key is the sheet's own ``类型：{type}/{topic}`` marker, so a report
    can pair two rounds by *concern* rather than by row position.
    """

    workbook = load_workbook(build / "投标项目复核表.xlsx", data_only=False)
    try:
        sheet = workbook[DELIVERED_SHEET]
        rows: list[tuple[str, str, str]] = []
        for row in range(CHECKLIST_START_ROW, sheet.max_row + 1):
            text = sheet.cell(row=row, column=4).value
            if text in (None, ""):
                break
            marker = str(sheet.cell(row=row, column=13).value or "")
            item_id = str(sheet.cell(row=row, column=1).value or "")
            rows.append((item_id, marker, str(text)))
        return rows
    finally:
        workbook.close()


def delivered_cells(build: Path) -> list[str]:
    """The delivered sheet's review-text column, rows in delivered order."""

    return [text for _, _, text in delivered_rows(build)]


def split_sections(cell: str) -> dict[str, str]:
    """Split a delivered review cell into its labelled sections."""

    matches = list(SECTION_RE.finditer(cell))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cell)
        sections[match.group(1)] = cell[match.end():end].strip()
    return sections


def synthesized_part(cell: str, after: bool) -> str:
    """The part of a delivered cell that the engine synthesized (not source quotes)."""

    sections = split_sections(cell)
    if after:
        keys = ("复核要点", "通过标准", "评分提示", "准备材料", "不满足后果")
    else:
        keys = ("复核动作", "核验标准")
    return "\n".join(sections.get(key, "") for key in keys)


def before_metrics(cells: list[str], items: list) -> dict:
    rows_with_numbers = 0
    contaminated = 0
    generic = 0
    for cell, item in zip(cells, items):
        text = synthesized_part(cell, after=False)
        if not text.strip():
            text = cell
        if NUMBER_RE.search(text):
            rows_with_numbers += 1
            allowed = ROLES_BY_TYPE.get(item.requirement_type, frozenset())
            plan_numbers = {value for value in item.values}
            stray = [
                number
                for number in NUMBER_RE.findall(text)
                if number not in plan_numbers and allowed == frozenset()
            ]
            if stray:
                contaminated += 1
        if any(phrase in cell for phrase in GENERIC_PHRASES):
            generic += 1
    return {
        "rows": len(cells),
        "rows_with_numbers_in_synthesized_text": rows_with_numbers,
        "numeric_contamination_rows": contaminated,
        "generic_boilerplate_rows": generic,
    }


def after_metrics(plan) -> dict:
    points = [item.review_point for item in plan.items if item.review_point]
    scan = scan_review_points(points).as_dict()
    rows_with_numbers = 0
    for point in points:
        if NUMBER_RE.search(_claim_text(point)):
            rows_with_numbers += 1
    scan["rows_with_numbers_in_synthesized_text"] = rows_with_numbers
    scan["filtered_non_actionable_count"] = plan.filtered_non_actionable_count
    scan["filtered_non_actionable_topics"] = list(plan.filtered_non_actionable_topics)
    return scan


def check_fixtures(plan, case: str) -> list[dict]:
    """The brief's known-bad fixtures, evaluated on this round's plan."""

    items = order_review_items(plan.items)
    results: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        results.append({"fixture": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    signature = [item for item in items if item.requirement_type == "SIGNATURE"]
    signature_hits = [
        (item.item_id, token)
        for item in signature
        for token in SIGNATURE_BAD_TOKENS
        if token in synthesized_part(item.cell_text, after=True)
    ]
    add(
        "A_signature_duration_and_phone",
        not signature_hits,
        f"{len(signature)} SIGNATURE rows; hits={signature_hits[:4]}",
    )

    submission = [item for item in items if item.requirement_type == "SUBMISSION"]
    submission_hits = [
        (item.item_id, token)
        for item in submission
        for token in SUBMISSION_BAD_TOKENS
        if token in synthesized_part(item.cell_text, after=True)
    ]
    add(
        "B_submission_fee_as_value",
        not submission_hits,
        f"{len(submission)} SUBMISSION rows; hits={submission_hits[:4]}",
    )

    fee_rows = [
        item.item_id
        for item in items
        if FEE_BAD_TOKEN in synthesized_part(item.cell_text, after=True)
        or "平台服务费" in synthesized_part(item.cell_text, after=True)
    ]
    fee_only_after_sales = []
    for item in items:
        if "售后" not in item.topic:
            continue
        units = [
            unit
            for unit in plan.index.units
            if unit.requirement_id in set(item.source_requirement_ids)
        ]
        if units and all("服务费" in unit.text for unit in units):
            fee_only_after_sales.append(f"{item.item_id}:{item.requirement_type}/{item.topic}")
    add(
        "C_platform_fee_not_a_review_value",
        not fee_rows and not fee_only_after_sales,
        f"fee-value rows={fee_rows[:4]}; fee-only after-sales rows={fee_only_after_sales[:4]}",
    )

    member_rows = []
    for item in items:
        point = item.review_point
        quoted = synthesized_part(item.cell_text, after=True)
        if re.search(r"(评审小组|评标委员会|磋商小组|评委|专家库)[^。；\n]{0,12}\d+\s*[人名]", quoted):
            member_rows.append(item.item_id)
            continue
        for evidence in point.numeric_evidence:
            if not evidence.usable or evidence.role != "PERSON_COUNT":
                continue
            owner = next(
                (
                    unit
                    for unit in plan.index.units
                    if unit.requirement_id == evidence.unit_id
                ),
                None,
            )
            if owner is not None and re.search(
                r"(评审小组|评标委员会|磋商小组|评委|专家库)", owner.text
            ):
                member_rows.append(item.item_id)
                break
    add(
        "D_evaluation_member_count",
        not member_rows,
        f"rows quoting purchaser-side member counts as values={sorted(set(member_rows))[:4]}",
    )

    mixed = []
    for item in items:
        point = item.review_point
        roles = sorted({evidence.role for evidence in point.numeric_evidence if evidence.usable})
        if len(roles) > 2:
            mixed.append({"item": item.item_id, "roles": roles})
    add(
        "E_unrelated_numeric_mix",
        not mixed,
        f"rows whose values span more than two semantic roles={mixed[:3]}",
    )

    contract_hits = [
        item.item_id
        for item in items
        if item.requirement_type == "CONTRACT"
        and CONTRACT_BAD_TOKEN in (item.review_point.failure_consequence or "")
    ]
    contract_hits += [
        item.item_id
        for item in items
        if item.requirement_type == "CONTRACT"
        and CONTRACT_BAD_TOKEN in item.review_point.failure_consequence
        and CONTRACT_BAD_TOKEN not in item.review_point.requirement_summary
    ]
    add(
        "F_contract_unrelated_consequence",
        not contract_hits,
        f"CONTRACT rows with an unrelated consequence={sorted(set(contract_hits))[:4]}",
    )

    fabricated = []
    unit_text = {unit.requirement_id: unit.text for unit in plan.index.units}
    for item in items:
        point = item.review_point
        row_ids = set(item.source_requirement_ids)
        for evidence in point.numeric_evidence:
            if not evidence.usable:
                continue
            owner_text = unit_text.get(evidence.unit_id, "")
            if evidence.unit_id not in row_ids or evidence.value not in owner_text.replace(" ", ""):
                fabricated.append(
                    {"item": item.item_id, "value": evidence.value, "unit": evidence.unit_id}
                )
    add(
        "G_values_owned_by_the_row",
        not fabricated,
        f"values shown without an owning clause in the row={fabricated[:4]}",
    )
    return results


def numeric_semantics(plan) -> dict:
    """How many values of each semantic role survive into a row, per type."""

    roles: dict[str, int] = {}
    unusable = 0
    for item in plan.items:
        point = item.review_point
        for evidence in point.numeric_evidence:
            roles[evidence.role] = roles.get(evidence.role, 0) + 1
            if not evidence.usable:
                unusable += 1
    return {
        "roles_seen": dict(sorted(roles.items())),
        "usable_values": sum(1 for item in plan.items for e in item.review_point.numeric_evidence if e.usable),
        "blocked_values": unusable,
        "never_usable_roles": sorted(NEVER_USABLE_ROLES),
    }


def examples(plan, before_rows: list[tuple[str, str, str]], limit: int = 8) -> list[dict]:
    """Deterministic BEFORE/AFTER pairs, paired by review concern.

    Rows are paired by the delivered ``类型：{type}/{topic}`` marker, never by
    position: a round may add or drop a row, and a positional pairing would
    silently compare two different concerns.
    """

    items = order_review_items(plan.items)
    before_by_key = {marker: text for _, marker, text in before_rows}
    before_id_by_key = {marker: item_id for item_id, marker, _ in before_rows}
    priority = {
        "SIGNATURE": 0,
        "SUBMISSION": 1,
        "TECHNICAL": 2,
        "CONTRACT": 3,
        "EVALUATION": 4,
        "OTHER": 5,
    }
    ranked = sorted(
        items,
        key=lambda item: (
            priority.get(item.requirement_type, 9),
            item.item_id,
        ),
    )
    chosen: list[dict] = []
    for item in ranked:
        key = f"类型：{item.requirement_type}/{item.submodule or item.topic}"
        before = before_by_key.get(key, "")
        after = render_review_cell(item.review_point) if item.review_point else ""
        if not before or before == after:
            continue
        chosen.append(
            {
                "item_id": item.item_id,
                "before_item_id": before_id_by_key.get(key, ""),
                "paired_by": key,
                "requirement_type": item.requirement_type,
                "topic": item.topic,
                "before": before,
                "after": after,
                "before_synthesized": synthesized_part(before, after=False),
                "after_synthesized": synthesized_part(after, after=True),
            }
        )
        if len(chosen) >= limit:
            break
    return chosen


def case_invariants(case: str, plan, facts) -> list[dict]:
    """Case-specific expectations carried over from the acceptance rounds."""

    checks: list[dict] = []
    fields = facts.fields.model_dump(mode="json")

    def field(name: str) -> tuple[object, str]:
        entry = fields.get(name) or {}
        return entry.get("resolved_value"), str(entry.get("status") or "")

    if case == "case_002":
        value, status = field("max_price")
        checks.append(
            {
                "check": "case_002.max_price_is_7507785_65",
                "result": "PASS"
                if status == "RESOLVED" and str(value) == "7507785.65"
                else "FAIL",
                "detail": f"max_price={value!r} status={status}",
            }
        )
        value, status = field("budget")
        checks.append(
            {
                "check": "case_002.budget_stays_not_found",
                "result": "PASS" if status == "NOT_FOUND" else "FAIL",
                "detail": f"budget status={status}",
            }
        )
    if case == "case_003":
        value, status = field("lot_name")
        checks.append(
            {
                "check": "case_003.lot_name_resolved",
                "result": "PASS"
                if status == "RESOLVED" and "三标段" in str(value)
                else "FAIL",
                "detail": f"lot_name={value!r} status={status}",
            }
        )
        leaked = [
            item.item_id
            for item in plan.items
            if "69152076" in item.cell_text or "河南国企阳光招采" in item.cell_text
        ]
        checks.append(
            {
                "check": "case_003.no_case_001_leakage",
                "result": "PASS" if not leaked else "FAIL",
                "detail": f"rows carrying CASE001 material={leaked[:4]}",
            }
        )
    return checks


def to_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Review workbook round 2 — human review-point synthesis content quality")
    lines.append("")
    lines.append(f"- generated: {report['generated_at']}")
    lines.append(f"- case: {report['case']}")
    lines.append(f"- result: {report['result']}")
    lines.append(f"- review-point rows: {report['after']['rows']}")
    lines.append(
        f"- filtered non-actionable clauses: {report['after']['non_actionable_rows']} "
        f"(topics: {report['after'].get('filtered_non_actionable_topics')})"
    )
    lines.append("")
    lines.append("## Counters")
    lines.append("")
    lines.append("| counter | before (round 1) | after (round 2) |")
    lines.append("| --- | --- | --- |")
    for key in (
        "rows",
        "generic_boilerplate_rows",
        "numeric_contamination_rows",
        "semantic_contamination_rows",
        "unsupported_consequence_rows",
        "source_backed_consequence_rows",
        "rows_with_numbers_in_synthesized_text",
    ):
        before = report["before"].get(key, "-")
        after = report["after"].get(key, "-")
        lines.append(f"| {key} | {before} | {after} |")
    lines.append("")
    lines.append("## CASE001 known-bad fixtures")
    lines.append("")
    lines.append("| fixture | result | detail |")
    lines.append("| --- | --- | --- |")
    for entry in report["fixtures"]:
        lines.append(f"| {entry['fixture']} | {entry['result']} | {entry['detail']} |")
    lines.append("")
    if report.get("case_checks"):
        lines.append("## Case invariants")
        lines.append("")
        lines.append("| check | result | detail |")
        lines.append("| --- | --- | --- |")
        for entry in report["case_checks"]:
            lines.append(f"| {entry['check']} | {entry['result']} | {entry['detail']} |")
        lines.append("")
    lines.append("## BEFORE → AFTER examples")
    lines.append("")
    for example in report["examples"]:
        lines.append(
            f"### {example['item_id']} — {example['requirement_type']}/{example['topic']}"
        )
        lines.append("")
        lines.append("BEFORE (synthesized part)")
        lines.append("")
        lines.append("```text")
        lines.append(example["before_synthesized"][:600] or example["before"][:600])
        lines.append("```")
        lines.append("")
        lines.append("AFTER (synthesized part)")
        lines.append("")
        lines.append("```text")
        lines.append(example["after_synthesized"][:600])
        lines.append("```")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--before", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--out")
    parser.add_argument("--md")
    parser.add_argument("--audit-out")
    args = parser.parse_args()

    build = Path(args.build)
    if not build.is_absolute():
        build = REPO / build
    before_build = Path(args.before)
    if not before_build.is_absolute():
        before_build = REPO / before_build

    document, facts, plan, qa = load_case(build)
    before_document, before_facts, before_plan, before_qa = load_case(before_build)

    before_cells = delivered_cells(before_build)
    before_rows = delivered_rows(before_build)
    after_cells = delivered_cells(build)
    before_items = order_review_items(before_plan.items)

    after = after_metrics(plan)
    after["rows"] = len(plan.items)
    after["delivered_rows"] = len(after_cells)
    before = before_metrics(before_cells, before_items)
    before["delivered_rows"] = len(before_cells)

    fixtures = check_fixtures(plan, args.case)
    case_checks = case_invariants(args.case, plan, facts) + case_invariants(
        args.case, before_plan, before_facts
    )
    semantic_match = [
        {"row": index + CHECKLIST_START_ROW,
         "item": item.item_id,
         "matches": render_review_cell(item.review_point) == after_cells[index]
         if index < len(after_cells)
         else False}
        for index, item in enumerate(order_review_items(plan.items))
    ]
    mismatched = [row for row in semantic_match if not row["matches"]]

    report = {
        "schema": "v1_review_workbook_round2_content_quality/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case": args.case,
        "build": str(build.relative_to(REPO)) if build.is_relative_to(REPO) else str(build),
        "before_build": str(before_build.relative_to(REPO))
        if before_build.is_relative_to(REPO)
        else str(before_build),
        "workbook_sha256": sha256(build / "投标项目复核表.xlsx"),
        "before_workbook_sha256": sha256(before_build / "投标项目复核表.xlsx"),
        "after": after,
        "before": before,
        "numeric_semantics": numeric_semantics(plan),
        "fixtures": fixtures,
        "case_checks": case_checks,
        "delivered_sheet_matches_review_points": {
            "rows_compared": len(semantic_match),
            "mismatches": mismatched[:5],
            "result": "PASS" if not mismatched else "FAIL",
        },
        "dynamic_review_qa": {
            "result": qa["result"],
            "hard_gate_values": qa.get("hard_gate_values", {}),
        },
        "before_dynamic_review_qa_result": before_qa["result"],
        "examples": examples(plan, before_rows),
        "review_points": [
            {
                "item_id": item.item_id,
                "requirement_type": item.requirement_type,
                "topic": item.topic,
                "actionability": item.review_point.actionability,
                "status": item.review_point.status,
                "checks": len(item.review_point.review_checks),
                "pass_criteria": len(item.review_point.pass_criteria),
                "source_backed_consequence": bool(item.review_point.consequence_evidence_id),
                "consequence": item.review_point.failure_consequence,
                "evidence_ids": item.review_point.evidence_ids[:4],
                "values": [e.value for e in item.review_point.numeric_evidence if e.usable],
            }
            for item in order_review_items(plan.items)
        ],
    }
    hard_gates = {
        key: value
        for key, value in report["dynamic_review_qa"]["hard_gate_values"].items()
        if value and key != "dynamic_review_item_count"
    }
    fixture_failures = [entry["fixture"] for entry in fixtures if entry["result"] != "PASS"]
    report["result"] = (
        "PASS"
        if not hard_gates
        and not fixture_failures
        and report["delivered_sheet_matches_review_points"]["result"] == "PASS"
        and after["generic_boilerplate_rows"] == 0
        and after["numeric_contamination_rows"] == 0
        and all(entry["result"] == "PASS" for entry in case_checks)
        else "FAIL"
    )
    report["blocking"] = {
        "hard_gates": hard_gates,
        "fixture_failures": fixture_failures,
        "sheet_mismatches": len(mismatched),
        "case_checks": [entry["check"] for entry in case_checks if entry["result"] != "PASS"],
    }

    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.md:
        md = Path(args.md)
        if not md.is_absolute():
            md = REPO / md
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(to_markdown(report), encoding="utf-8")
    if args.audit_out:
        audit = Path(args.audit_out)
        if not audit.is_absolute():
            audit = REPO / audit
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text(
            json.dumps(
                {
                    "schema": "v1_review_workbook_current_state_audit/1",
                    "generated_at": report["generated_at"],
                    "case": args.case,
                    "note": (
                        "audit of the round-2 review-workbook state: this file did not exist "
                        "before round 2 and is created here from the delivered artifacts"
                    ),
                    "review_point_plan": {
                        "rows": len(plan.items),
                        "filtered_non_actionable": plan.filtered_non_actionable_count,
                        "filtered_topics": list(plan.filtered_non_actionable_topics),
                    },
                    "delivered_sheet": {
                        "rows": len(after_cells),
                        "matches_review_points": report[
                            "delivered_sheet_matches_review_points"
                        ]["result"],
                    },
                    "structured_views": {
                        "02_关键条款": len(
                            [item for item in plan.items if item.requirement_type in {"REJECTION", "QUALIFICATION", "PRICING", "BOND", "VALIDITY", "DURATION", "CONTRACT"}]
                        ),
                        "03_资格否决与强制项": len(plan.mandatory_items)
                        if hasattr(plan, "mandatory_items")
                        else None,
                    },
                    "workbook_sha256": report["workbook_sha256"],
                    "result": report["result"],
                    "manual_review": "NOT_YET_CONFIRMED",
                    "ready_for_submission": False,
                    "v1_production_candidate": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        f"REVIEW_WORKBOOK_ROUND2_QUALITY {report['result']} case={args.case} "
        f"rows={after['rows']} filtered={after['non_actionable_rows']} "
        f"generic={after['generic_boilerplate_rows']} numeric={after['numeric_contamination_rows']}"
    )
    for entry in fixtures:
        if entry["result"] != "PASS":
            print(f"  FIXTURE FAIL {entry['fixture']}: {entry['detail']}")
    for entry in case_checks:
        if entry["result"] != "PASS":
            print(f"  CASE FAIL {entry['check']}: {entry['detail']}")
    for key, value in hard_gates.items():
        print(f"  GATE FAIL {key}={value}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
