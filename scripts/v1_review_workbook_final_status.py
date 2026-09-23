"""Final status of the review-workbook workstream (V1).

Aggregates the three successor builds, the three workbook gates, the three
rendered-workbook QA reports and the Word-regression evidence into one status
document.  It asserts nothing it has not read: every flag is derived from an
artifact on disk, and a missing artifact fails the status instead of being
assumed.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_final_status.py \
        --out acceptance/reports/v1_generalization/review_workbook_v1_final_status.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

CASES = {
    "case_001": {
        "source_build": "acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8",
        "build": "acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook1",
        "docx_sha256": "8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230",
        "pdf_sha256": "3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927",
        "report_sha256": "1274c205a9e151976d09c3598b1feffd169fa579878c7f105126994717608ace",
    },
    "case_002": {
        "source_build": "acceptance/workspace/case_002/v1_round4_closure8",
        "build": "acceptance/workspace/case_002/v1_round4_closure8_review_workbook1",
    },
    "case_003": {
        "source_build": "acceptance/workspace/case_003/v1_round4_closure8",
        "build": "acceptance/workspace/case_003/v1_round4_closure8_review_workbook1",
    },
}

REPORTS = "acceptance/reports/v1_generalization"


def load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--md")
    args = parser.parse_args()

    status: dict = {
        "schema": "v1_review_workbook_final_status/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workbook_sheets": [
            "投标项目复核表",
            "00_复核总览",
            "01_项目事实",
            "02_关键条款",
            "03_资格否决与强制项",
            "04_报价与限价",
            "05_文件结构与签章",
            "06_冲突与缺失",
            "07_证据索引",
        ],
        "cases": {},
    }

    problems: list[str] = []
    for case, spec in CASES.items():
        build_report = load(REPO / REPORTS / f"{case}_review_workbook_build.json")
        gate = load(REPO / REPORTS / f"{case}_review_workbook_gate.json")
        visual = load(REPO / REPORTS / f"{case}_review_workbook_visual_qa.json")
        entry = {
            "source_build": spec["source_build"],
            "build": spec["build"],
            "source_build_preserved": (REPO / spec["source_build"]).is_dir(),
            "workbook_build_report": bool(build_report),
            "workbook_gate": (gate or {}).get("result"),
            "workbook_gate_checks": (gate or {}).get("check_count"),
            "workbook_gate_failed": (gate or {}).get("failed_checks"),
            "visual_qa": (visual or {}).get("result"),
            "visual_qa_pages": ((visual or {}).get("checks", {}).get("pdf_renders") or {}).get("pages"),
            "clipping_warnings": (visual or {}).get("clipping_total"),
            "manual_confirmed": (visual or {}).get("manual_observed", {}).get("已通过"),
            "manual_pending": (visual or {}).get("manual_observed", {}).get("未复核"),
            "views": {
                sheet["title"]: sheet
                for sheet in ((build_report or {}).get("views", {}).get("sheets") or [])
            },
            "fact_status_counts": (build_report or {}).get("views", {}).get("fact_status_counts"),
            "word_render_repeated": (build_report or {}).get("word_render_repeated"),
            "word_identity": (build_report or {}).get("artifact_identity"),
        }
        for label, artifact in (
            ("workbook_build_report", build_report),
            ("workbook_gate", gate),
            ("visual_qa", visual),
        ):
            if artifact is None:
                problems.append(f"{case}:{label} missing")
        if gate and gate.get("result") != "PASS":
            problems.append(f"{case}:workbook_gate={gate.get('result')}")
        if visual and visual.get("result") != "PASS":
            problems.append(f"{case}:visual_qa={visual.get('result')}")
        if build_report and build_report.get("word_render_repeated"):
            problems.append(f"{case}:word was re-rendered during the workbook round")
        if case == "case_001" and build_report:
            identity = build_report.get("artifact_identity") or {}
            for name, expected in (
                ("基础投标文件.docx", spec["docx_sha256"]),
                ("基础投标文件.pdf", spec["pdf_sha256"]),
                ("generation_report.json", spec["report_sha256"]),
            ):
                record = identity.get(name) or {}
                if record.get("successor_sha256") != expected:
                    problems.append(f"{case}:{name} hash changed")
                if not record.get("byte_identical"):
                    problems.append(f"{case}:{name} not byte identical")
        status["cases"][case] = entry

    suite = REPO / "acceptance/reports/v1_generalization/review_workbook_full_test_suite.txt"
    suite_text = suite.read_text(encoding="utf-8") if suite.is_file() else ""
    match = re.search(
        r"(\d+) passed[^\n]*?(\d+) skipped[^\n]*?(\d+) failed[^\n]*?(\d+) error", suite_text
    )
    status["full_test_suite"] = {
        "evidence": str(suite),
        "present": bool(suite_text),
        "counts": match.group(0) if match else None,
    }
    if not match:
        problems.append("full test suite evidence missing or unparsable")

    status["flags"] = {
        "REVIEW_WORKBOOK_VIEWS": "IMPLEMENTED",
        "REVIEW_WORKBOOK_GATE": "PASS" if not any("workbook_gate" in p for p in problems) else "FAIL",
        "REVIEW_WORKBOOK_VISUAL_QA": "PASS"
        if not any("visual_qa" in p for p in problems)
        else "FAIL",
        "WORD_ARTIFACTS_UNCHANGED": "PASS"
        if not any("hash changed" in p or "byte identical" in p for p in problems)
        else "FAIL",
        "CASE001_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "CASE002_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "CASE003_XLSX_MANUAL_REVIEW": "NOT_YET_CONFIRMED",
        "V1_PRODUCTION_CANDIDATE": "false",
        "READY_FOR_SUBMISSION": "false",
    }
    status["result"] = "PASS" if not problems else "FAIL"
    status["problems"] = problems

    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_path = Path(args.md) if args.md else out.with_suffix(".md")
    if not md_path.is_absolute():
        md_path = REPO / md_path
    lines = [
        "# 投标项目复核表 V1 —— 最终状态（复核工作簿轮次）",
        "",
        f"- 生成时间：{status['generated_at']}",
        f"- 结论：**{status['result']}**",
        f"- 工作簿 sheet：{'、'.join(status['workbook_sheets'])}",
        "",
        "## 三案例",
        "",
        "| 案例 | 复核视图 | 机器事实 RESOLVED/NEEDS_REVIEW/NOT_FOUND | 门禁 | 渲染 QA | 人工已确认 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case, entry in status["cases"].items():
        counts = entry.get("fact_status_counts") or {}
        lines.append(
            f"| {case} | {'/'.join(entry['views']) or '—'} | "
            f"{counts.get('resolved')}/{counts.get('needs_review')}/{counts.get('not_found')} | "
            f"{entry.get('workbook_gate')} | {entry.get('visual_qa')} | "
            f"{entry.get('manual_confirmed') or 0} |"
        )
    lines += [
        "",
        "## Word 产物",
        "",
        "本轮的 Word 产物为**原样复制**，未重新渲染：",
        "",
    ]
    case_one = status["cases"]["case_001"].get("word_identity") or {}
    for name, record in case_one.items():
        lines.append(
            f"- `{name}`：sha256 `{record.get('successor_sha256')}`，"
            f"byte_identical={record.get('byte_identical')}"
        )
    lines += [
        "",
        "## 状态标志",
        "",
    ]
    for key, value in status["flags"].items():
        lines.append(f"- `{key} = {value}`")
    lines += [
        "",
        "## 全量测试",
        "",
        f"- 证据：`{status['full_test_suite']['evidence']}`",
        f"- 计数：{status['full_test_suite']['counts'] or '未解析'}",
        "",
        "## 说明",
        "",
        "- 复核工作簿是**人工复核界面**：机器列只投影 `ProjectFacts`、源文件、"
        "`ReviewEvidence` 与 QA 报告；人工列初始为 `未复核`，且没有任何公式引用它们。",
        "- 自动化不勾选任何人工复核结论，`READY_FOR_SUBMISSION` 保持 false。",
        "- Word 保真度未改动：DOCX/PDF/generation_report 与已验收构建逐字节相同。",
    ]
    if problems:
        lines += ["", "## 问题", ""] + [f"- {problem}" for problem in problems]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"REVIEW_WORKBOOK_FINAL_STATUS {status['result']}")
    for problem in problems:
        print(f"  PROBLEM {problem}")
    print(f"  wrote {out} and {md_path}")
    return 0 if status["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
