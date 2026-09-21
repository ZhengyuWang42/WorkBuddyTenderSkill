"""V1 PHASE D: compact human manual-review checklist.

Derives the manual review checklist from the accepted cases' own evidence - the
facts that are not resolved, the source slots the automation left blank, the
delivery warnings and the package properties no automated check can confirm - and
writes it as a short Markdown document.  The checklist is deliberately *not*
marked complete: manual Word review remains required and can only be signed off by
a human.

Usage::

    .venv/Scripts/python.exe scripts/v1_manual_review_checklist.py \
        --out acceptance/reports/v1_generalization/v1_manual_review_checklist.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CASE_LABELS = {
    "case_001": "CASE001 - 引江济淮郸城配套项目一体化泵站询比文件",
    "case_002": "CASE002 - 营收系统整合和硬件系统升级项目招标文件",
    "case_003": "CASE003 - 肇源县城市供水管网漏损治理项目三标段",
}

STATUS_LABELS = {
    "NEEDS_REVIEW": "需人工确认 (NEEDS_REVIEW)",
    "NOT_FOUND": "原文未找到 (NOT_FOUND)",
    "OCR_REQUIRED": "需 OCR (OCR_REQUIRED)",
}


def resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def facts_by_status(build_dir: Path, status: str) -> list[tuple[str, str]]:
    path = build_dir / "project_facts.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for name, field in sorted((payload.get("fields") or {}).items()):
        if str(field.get("status")) != status:
            continue
        rows.append((name, str(field.get("reason") or field.get("evidence_note") or "")[:120]))
    return rows


def delivery_warnings(build_dir: Path) -> list[str]:
    path = build_dir / "qa_report.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        "%s: %s" % (item.get("id"), item.get("message"))
        for item in (payload.get("warnings") or [])
        if str(item.get("status")) not in ("PASS", "SKIPPED")
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regression", type=Path,
                        default=ROOT / "acceptance/reports/v1_generalization/three_case_regression.json")
    parser.add_argument("--gate", type=Path,
                        default=ROOT / "acceptance/reports/v1_generalization/v1_automated_candidate_gate.json")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    regression = json.loads(resolve(args.regression).read_text(encoding="utf-8"))
    gate = json.loads(resolve(args.gate).read_text(encoding="utf-8"))

    lines: list[str] = []
    lines.append("# V1 人工 Word 复核清单 (human manual review checklist)")
    lines.append("")
    lines.append(
        "本清单由自动化证据生成，**尚未完成**。自动化结论为 `%s`；"
        "`MANUAL_WORD_REVIEW_REQUIRED = true`、`READY_FOR_SUBMISSION = false` "
        "在人工复核签字前保持不变。" % gate.get("status")
    )
    lines.append("")
    lines.append("## 0. 自动化结论 (automated result)")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append("| 三案例泛化 | %s |" % regression.get("status"))
    lines.append("| 自动化候选状态 | %s |" % gate.get("status"))
    lines.append("| 自动化阻塞项 | %s |" % (gate.get("automated_candidate_blockers") or "无"))
    lines.append("| 不同源文件数 | %s |" % regression.get("distinct_source_count"))
    lines.append("")
    lines.append(
        "自动化已通过的门禁：字词安全扫描、ZIP 完整性、OOXML 可解析、"
        "无文本框/浮动对象/嵌入位图、无合成版式表格、无表格单元丢失/重复/虚构、"
        "无阻断性重叠、源文本无缺失、渲染 PDF 可重新打开且无空白页、"
        "每条 RESOLVED 事实保留来源证据、复核证据硬门禁通过。"
    )
    lines.append("")
    lines.append("## 1. 逐案例交付物 (deliverables to open)")
    lines.append("")
    for case in regression.get("cases") or ():
        build_dir = resolve(case.get("build_dir") or "")
        lines.append("### %s" % CASE_LABELS.get(case.get("case"), case.get("case")))
        lines.append("")
        lines.append("- 构建目录: `%s`" % build_dir)
        lines.append("- 结果: `%s`" % case.get("case_result"))
        lines.append("- 逐项门禁: %d 项，失败 %d 项"
                     % (len(case.get("checks") or []), len(case.get("failed_checks") or [])))
        lines.append("")
        lines.append("- [ ] 在 Word 中打开 `基础投标文件.docx`，确认可正常打开、无修复提示")
        lines.append("- [ ] 确认页面、页眉页脚、章节顺序与原文一致")
        lines.append("- [ ] 确认表格为可编辑 Word 表格，跨页长表为单一逻辑表格")
        lines.append("- [ ] 确认占位符/下划线/空格位置可供人工填写")
        lines.append("- [ ] 在 Excel 中打开 `投标项目复核表.xlsx`，确认行与原文要求对应")
        lines.append("- [ ] 复核 `project_facts.json` 中以下未定稿字段")
        for status in ("NEEDS_REVIEW", "NOT_FOUND", "OCR_REQUIRED"):
            rows = facts_by_status(build_dir, status)
            if not rows:
                continue
            lines.append("")
            lines.append("  - %s:" % STATUS_LABELS.get(status, status))
            for name, reason in rows:
                lines.append("    - `%s`%s" % (name, (" - " + reason) if reason else ""))
        warnings = delivery_warnings(build_dir)
        if warnings:
            lines.append("")
            lines.append("  - 交付 QA 警告:")
            for warning in warnings:
                lines.append("    - %s" % warning)
        lines.append("")

    lines.append("## 2. 案例特有复核点 (case-specific review points)")
    lines.append("")
    lines.append(
        "- [ ] **CASE001**: 第 42 页响应函的 `达到` 前空位未填入质量目标"
        "（该行没有自己的字段标签，按行作用域规则保留为固定空位），"
        "请确认该空位应由人工填写。"
    )
    lines.append(
        "- [ ] **CASE002**: 询问报价明细长表跨源页合并为一个逻辑 Word 表格，"
        "Word 原生分页与源 PDF 页数不必相等，请确认分页位置可接受。"
    )
    lines.append(
        "- [ ] **CASE003**: 三标段标段语义（lot）与 12 个留空槽位，"
        "请确认标段信息与人工填写位置正确。"
    )
    lines.append("")
    lines.append("## 3. 签字 (sign-off)")
    lines.append("")
    lines.append("- [ ] 复核人：____________  日期：____________")
    lines.append("- [ ] 结论：可提交 / 需修改")
    lines.append("")
    lines.append(
        "> 只有人工完成本清单后，才可以把 `READY_FOR_SUBMISSION` 置为 true。"
        "自动化检查不会、也不可以自行升级该标志。"
    )
    lines.append("")

    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"written": str(out), "lines": len(lines)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
