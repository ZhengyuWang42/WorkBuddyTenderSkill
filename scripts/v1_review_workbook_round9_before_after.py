"""Round-9 delivered-content before/after for the review workbook (CASE001).

The round-8 workbook was reviewed by hand and failed five further delivered-content
classes; round 9 closes them in the delivered cells.  This script writes the
reviewer-readable, re-computable comparison between the **frozen round-8
successor** and the **round-9 successor**:

* both identities, pinned by the on-disk ``投标项目复核表.xlsx`` sha256;
* every row's delivered requirement / action / locator on both sides, with the
  columns that actually changed;
* the locator-specific before/after records the round-9 locator gate produced
  (canonical unit -> production formatter -> expected locator -> saved cell), so
  a human can re-derive why a locator moved.

The round-8 before/after evidence (round 7 -> round 8) is left untouched.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_round9_before_after.py --case case_001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import v1_review_workbook_round8_before_after as r8  # noqa: E402
from v1_review_workbook_round9_report import (  # noqa: E402
    BUILDS as ROUND9_BUILDS,
    REPORTS,
    Round9Report,
)

#: captured before ``_bind_round9`` swaps the module global: the round-8 plan
#: order is what the frozen workbook's delivered rows are addressed by
_ROUND8_REPORT = r8.Round8Report

SCHEMA = "v1_review_workbook_round9_before_after/1"

#: the round-8 successor each round-9 workbook was derived from
FROZEN = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook8",
    "case_002": "v1_round4_closure8_review_workbook8",
    "case_003": "v1_round4_closure8_review_workbook8",
}

#: the round-9 findings, keyed by the concern the finding is bound to
ROUND9_FINDINGS: tuple[tuple[str, str, str], ...] = (
    ("D23", "SCORING_BANK_ACCEPTANCE", "银行承兑分档：每档保留自己的条件与分值，且为择一"),
    ("D38", "SCORING_PAYMENT_CONDITION", "付款条件分档：每档保留自己的条件与分值"),
    ("D50", "SCORING_PRICE_FORMULA", "基本分 30 与本项最高 40 区分；评分规则为核验而非要求投标人重述"),
    ("D56", "PRE_BID_MEETING", "采购预备会决定与提问/澄清截止分离为两个关切"),
    ("D57", "SUBMISSION_DEADLINE", "复核动作只引用本行自己的页码/条款"),
    ("D16", "QUALIFICATION_LICENSE", "营业执照源文拼接损坏已清理"),
    ("D22", "FILE_FORMAT", "响应文件格式源文拼接损坏已清理"),
    ("D40", "RETENTION_RELEASE_PERIOD", "质保期释放行引用本合同条款（不引用外来标题）"),
    ("D43", "RETENTION_MONEY_RATIO", "质保金比例行引用本合同条款（不引用外来标题）"),
    ("D34", "BID_VALIDITY", "有效期行的定位指向本行自己的条款"),
)


def _bind_round9() -> None:
    """Point the round-8 comparison machinery at the round-9 objects."""

    r8.Round8Report = Round9Report
    r8.BUILDS = dict(ROUND9_BUILDS)
    r8.FROZEN = dict(FROZEN)


def _cell(value: object, limit: int = 90) -> str:
    text = " ".join(str(value or "").split())
    text = text.replace("|", "\\|")
    return text[:limit] + ("…" if len(text) > limit else "")


def build_case(case: str) -> dict[str, Any]:
    _bind_round9()
    data = r8.build(case)
    report = Round9Report(case)
    # the locator records are recomputed here so the before/after artifact carries
    # the same expectation the gate asserts (no separate measurement)
    audit = report.audit()
    # round 9 adds a delivered row (the pre-bid decision and the query/clarification
    # deadline become two rows), so the frozen build's *row index* no longer lines
    # up after the insertion point.  Re-read the frozen side **by item id** through
    # the round-8 plan order; a row round 8 did not deliver is marked NEW.
    frozen_report = _ROUND8_REPORT(case)
    frozen_ids = [str(item.item_id) for item in frozen_report.items]
    frozen = r8._load_build(
        r8.ROOT / "acceptance/workspace" / case / FROZEN[case]
    )
    changed = 0
    for record in data["rows"]:
        item_id = str(record["item_id"])
        if item_id in frozen_ids:
            position = frozen_ids.index(item_id)
            record["before"] = r8._legacy_view(frozen["legacy"].get(9 + position))
            record["frozen_cell"] = f"{r8.LEGACY}!D{9 + position}"
        else:
            record["before"] = r8._legacy_view(None)
            record["frozen_cell"] = ""
            record["delivered_in_frozen"] = False
        record["changed"] = sorted(
            field
            for field in ("risk", "requirement", "action", "criteria", "consequence", "locator")
            if str(record["before"].get(field) or "") != str(record["after"].get(field) or "")
        )
        if record["changed"]:
            changed += 1
    data.update(
        {
            "schema": SCHEMA,
            "frozen_delivered_row_count": len(frozen_ids),
            "alignment": "by_item_id",
            "changed_row_count": changed,
            "unchanged_row_count": len(data["rows"]) - changed,
            "locator_records": audit.get("locator_records", []),
            "locator_fixtures": audit.get("locator_fixtures", {}),
            "counts": audit.get("counts", {}),
        }
    )
    return data


def markdown(data: Mapping[str, Any]) -> str:
    rows: Sequence[Mapping[str, Any]] = data["rows"]
    records = {str(record["item_id"]): record for record in data["locator_records"]}
    by_concern = {str(record["concern_id"]): record for record in rows}
    lines = [
        f"# Round 9 delivered-content before/after — {data['case']}",
        "",
        "人工第 8 轮复核按送达文本保真判 **FAIL**；第 9 轮在交付单元格中关闭这些类别。"
        "本文件是逐行、可复算的对照：冻结构建 = 第 8 轮后继，目标构建 = 第 9 轮后继；"
        "所有文本都取自**已保存并重新打开**的 XLSX。",
        "",
        f"- 冻结构建：`{data['frozen_build']}`（`投标项目复核表.xlsx` sha256 "
        f"`{data['frozen_workbook_sha256']}`）",
        f"- 第 9 轮后继构建：`{data['successor_build']}`（sha256 "
        f"`{data['successor_workbook_sha256']}`）",
        f"- 交付行：{len(rows)} 行；变化 {data['changed_row_count']} 行，未变化 "
        f"{data['unchanged_row_count']} 行",
        f"- 对齐方式：按 `item_id`（第 8 轮交付 {data.get('frozen_delivered_row_count')} 行；"
        f"第 9 轮 {len(rows)} 行 —— 第 9 轮把「采购预备会决定」与「提问/澄清截止」拆成两行，"
        f"因此**不按行号**对齐）",
        "",
        "## 1. 第 9 轮点名的行",
        "",
        "| 发现 | 关切 | 行 | 地址 | 定位（第 8 轮 → 第 9 轮） | 要求正文（第 8 轮 → 第 9 轮） | 变化 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, concern_id, finding in ROUND9_FINDINGS:
        record = by_concern.get(concern_id)
        if record is None:
            lines.append(f"| {key} | {concern_id} | — | — | 本案例未交付该关切 | — | — |")
            continue
        lines.append(
            f"| {key} | {concern_id} | `{record['item_id']}` | `{record['delivered_cell']}` | "
            f"{_cell(record['before']['locator'], 60)} → {_cell(record['after']['locator'], 60)} | "
            f"{_cell(record['before']['requirement'], 70)} → {_cell(record['after']['requirement'], 70)} | "
            f"{'、'.join(record['changed']) or '—'}（{finding}） |"
        )

    lines += [
        "",
        "## 2. 定位门禁（canonical EvidenceUnit → production formatter → 已保存单元格）",
        "",
        "| 行 | 关切 | 规范单元 | 规范 section / clause | formatter 期望定位 | 已保存 XLSX 定位 | 结果 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item_id in sorted(records):
        record = records[item_id]
        lines.append(
            f"| `{item_id}` | {record.get('concern_id')} | `{record.get('canonical_unit_id')}` | "
            f"{_cell(record.get('canonical_section'), 40)} / {_cell(record.get('canonical_clause'), 12)} | "
            f"{_cell(record.get('expected_locator'), 70)} | {_cell(record.get('actual_locator'), 70)} | "
            f"{record.get('result')} |"
        )

    lines += [
        "",
        "## 3. 全部交付行的送达文本对照",
        "",
        "| 行 | 关切 | 地址 | 源定位（第 8 → 9 轮） | 要求正文（第 8 轮） | 要求正文（第 9 轮） | 变化 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in rows:
        lines.append(
            f"| `{record['item_id']}` | {record['concern_id']} | `{record['delivered_cell']}` | "
            f"{_cell(record['source_locator'], 50)} | "
            f"{_cell(record['before']['requirement'], 70)} | "
            f"{_cell(record['after']['requirement'], 70)} | "
            f"{'、'.join(record['changed']) or '—'} |"
        )

    lines += ["", "## 4. 视图行差异（04/05/06）", "", "| 视图 | 第 8 轮行数 | 第 9 轮行数 | 差异行 |", "| --- | --- | --- | --- |"]
    for title, entry in (data.get("price_sheet") or {}).items():
        lines.append(
            f"| {title} | {entry['rows_before']} | {entry['rows_after']} | "
            f"{len(entry['differing_rows'])} |"
        )
    lines += [
        "",
        "> 说明：本对照只陈述**已保存单元格**的差异；定位一栏的期望值由 "
        "`tender_basic.evidence_unit.expected_locator_for_unit` 从**重建的规范证据单元**现算，"
        "与交付值做**精确相等**比较（无前缀/模糊匹配）。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=None)
    args = parser.parse_args(argv)
    cases = args.case or ["case_001"]
    for case in cases:
        data = build_case(case)
        REPORTS.mkdir(parents=True, exist_ok=True)
        stem = f"review_workbook_round9_{case}_before_after"
        (REPORTS / f"{stem}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (REPORTS / f"{stem}.md").write_text(markdown(data), encoding="utf-8")
        print(
            f"{case}: {data['changed_row_count']}/{len(data['rows'])} row(s) changed "
            f"-> {stem}.{{json,md}}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
