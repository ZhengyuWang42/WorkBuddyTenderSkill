"""Render the review workbook and check what a real spreadsheet shows.

Two independent renders of the same file:

1. **PDF** - proves the workbook opens, every sheet has a printable page, and no
   ``#REF!``/``#VALUE!``/``####`` marker stands where a value should be.
2. **recalculated XLSX** - LibreOffice is asked to convert the workbook to XLSX.
   Because the delivered file stores *formulas without cached results*, the
   converted copy carries the values a spreadsheet actually computes.  The
   dashboard counts in that copy are then compared with the counts recomputed
   here from the sheets themselves.

The launcher is the frozen one from ``scripts/render_case57.py``: ``soffice.com``
with an argv list, ``shell=False``, ``CREATE_NO_WINDOW`` and a fresh
``UserInstallation`` profile per render.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_visual_qa.py \
        --build acceptance/workspace/case_001/<build> --case case_001 \
        --out acceptance/reports/v1_generalization/case001_review_workbook_visual_qa.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from openpyxl import load_workbook  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from render_case57 import new_profile, run_soffice, soffice_argv  # noqa: E402
from tender_basic.review_workbook_views import SHEET_TITLES  # noqa: E402

DELIVERED_SHEET = "投标项目复核表"
ERROR_MARKERS = ("#REF!", "#VALUE!", "#NAME?", "#DIV/0!", "#N/A", "#NULL!", "#NUM!", "Err:")

MANUAL_COLUMNS = [
    ("01_项目事实", "M"),
    ("02_关键条款", "M"),
    ("03_资格否决与强制项", "O"),
    ("04_报价与限价", "I"),
    ("04_报价与限价", "L"),
    ("05_文件结构与签章", "M"),
    ("06_冲突与缺失", "H"),
]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _display_units(text: str) -> float:
    """Display width in Excel width units: a CJK glyph is about two units."""

    return sum(
        2.0 if unicodedata.east_asian_width(character) in ("W", "F") else 1.0
        for character in text
    )


def _convert(source: Path, outdir: Path, convert_to: str) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    profile_dir, profile_uri = new_profile(outdir)
    suffix = {"pdf": ".pdf", "xlsx": ".xlsx"}[convert_to.split(":")[0]]
    target = outdir / (source.stem + suffix)
    if target.exists():
        target.unlink()
    argv = soffice_argv(source.resolve(), outdir.resolve(), profile_uri, convert_to=convert_to)
    result = run_soffice(argv, timeout=900)
    if result.returncode != 0 or not target.is_file():
        raise RuntimeError(
            f"LibreOffice conversion failed (rc={result.returncode}): "
            f"{result.stderr.decode('utf-8', 'replace')[:400]}"
        )
    shutil.rmtree(profile_dir, ignore_errors=True)
    return target


def _estimated_clipping(worksheet) -> list[dict]:
    """Cells whose wrapped text needs more lines than the row can show."""

    merged_width: dict[str, float] = {}
    for merged in worksheet.merged_cells.ranges:
        total = 0.0
        for column in range(merged.min_col, merged.max_col + 1):
            letter = get_column_letter(column)
            total += worksheet.column_dimensions[letter].width or 8.43
        merged_width[f"{get_column_letter(merged.min_col)}{merged.min_row}"] = total

    risky = []
    for row in worksheet.iter_rows():
        for cell in row:
            if not isinstance(cell.value, str) or cell.value.startswith("="):
                continue
            column_letter = cell.column_letter
            width = merged_width.get(
                cell.coordinate, worksheet.column_dimensions[column_letter].width or 8.43
            )
            alignment = cell.alignment
            if not alignment or not alignment.wrap_text:
                continue
            characters_per_line = max(4.0, width * 1.0)
            lines = 0
            for segment in str(cell.value).split("\n"):
                lines += max(1, math.ceil(_display_units(segment) / characters_per_line))
            height = worksheet.row_dimensions[cell.row].height
            available = (height / 14.5) if height else 1.0
            if lines > available + 0.4:
                risky.append(
                    {
                        "sheet": worksheet.title,
                        "cell": cell.coordinate,
                        "lines_needed": lines,
                        "lines_available": round(available, 1),
                    }
                )
    return risky


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--out")
    parser.add_argument("--render-dir", help="directory for the rendered files")
    parser.add_argument("--skip-render", action="store_true", help="reuse an existing render")
    args = parser.parse_args()

    build = Path(args.build)
    if not build.is_absolute():
        build = REPO / build
    workbook_path = build / "投标项目复核表.xlsx"
    render_dir = Path(args.render_dir) if args.render_dir else build / "_render_qa"
    if not render_dir.is_absolute():
        render_dir = REPO / render_dir

    workbook = load_workbook(workbook_path, data_only=False)

    # recompute the counts the dashboard claims, from the sheets themselves
    expected = {}
    for label, outcome in (
        ("未复核", "未复核"),
        ("已通过", "通过"),
        ("有疑问", "有疑问"),
        ("需修改", "需修改"),
        ("不适用", "不适用"),
    ):
        expected[label] = sum(
            1
            for sheet, column in MANUAL_COLUMNS
            for row in workbook[sheet].iter_rows(min_row=2, values_only=True)
            if len(row) >= ord(column) - ord("A") + 1
            and _text(row[ord(column) - ord("A")]) == outcome
        )
    expected["人工复核条目合计"] = sum(
        1
        for sheet, column in MANUAL_COLUMNS
        for row in workbook[sheet].iter_rows(min_row=2, values_only=True)
        if len(row) >= ord(column) - ord("A") + 1 and _text(row[ord(column) - ord("A")])
    )
    expected["剩余待复核（未复核）"] = expected["未复核"]

    report: dict = {
        "schema": "v1_review_workbook_visual_qa/1",
        "case": args.case,
        "build": build.name,
        "workbook": str(workbook_path),
        "render_dir": str(render_dir),
        "sheets": list(workbook.sheetnames),
        "manual_expected": expected,
        "clipping_risks": {
            sheet: _estimated_clipping(workbook[sheet])
            for sheet in workbook.sheetnames
            if sheet != DELIVERED_SHEET
        },
        "checks": {},
    }

    pdf_path = render_dir / (workbook_path.stem + ".pdf")
    xlsx_path = render_dir / (workbook_path.stem + ".xlsx")
    if not args.skip_render:
        for stale in (pdf_path, xlsx_path):
            if stale.exists():
                stale.unlink()
        pdf_path = _convert(workbook_path, render_dir, "pdf")
        xlsx_path = _convert(workbook_path, render_dir, "xlsx")
    report["rendered_pdf"] = str(pdf_path)
    report["rendered_xlsx"] = str(xlsx_path)

    # 1. the PDF renders and shows no spreadsheet error marker
    try:
        import fitz  # PyMuPDF

        with fitz.open(pdf_path) as document:
            page_count = document.page_count
            text = "\n".join(page.get_text() for page in document)
    except Exception as error:  # pragma: no cover - renderer specific
        page_count = None
        text = ""
        report["pdf_read_error"] = str(error)
    markers = [marker for marker in ERROR_MARKERS if marker in text]
    report["checks"]["pdf_renders"] = {
        "result": "PASS" if page_count else "FAIL",
        "pages": page_count,
        "error_markers": markers,
    }
    report["checks"]["no_error_markers_in_render"] = {
        "result": "PASS" if not markers else "FAIL",
        "markers": markers,
    }
    # Each view is identified in the render by the labels it prints, not by its
    # sheet tab name (a printable page does not carry the tab name).
    view_markers = {
        SHEET_TITLES[0]: ["投标项目复核总览", "提交就绪判定"],
        SHEET_TITLES[1]: ["fact_key", "机器抽取值", "人工复核结论"],
        SHEET_TITLES[2]: ["requirement_id", "核验标准"],
        SHEET_TITLES[3]: ["否决性", "强制性类型", "人工满足情况"],
        SHEET_TITLES[4]: ["报价与限价复核", "限价类型（源）"],
        SHEET_TITLES[5]: ["盖章要求", "生成文档是否存在"],
        SHEET_TITLES[6]: ["建议人工动作", "候选值/冲突"],
        SHEET_TITLES[7]: ["evidence_id", "复核意图"],
    }
    rendered_views = {
        title: [marker for marker in markers if marker in text]
        for title, markers in view_markers.items()
    }
    missing_views = [title for title, found in rendered_views.items() if not found]
    report["rendered_views"] = rendered_views
    report["checks"]["all_views_render"] = {
        "result": "PASS" if not missing_views else "FAIL",
        "missing": missing_views,
        "markers_found": {title: len(found) for title, found in rendered_views.items()},
    }

    # 2. the recalculated copy proves the dashboard formulas evaluate
    values = load_workbook(xlsx_path, data_only=True)
    dashboard = values[SHEET_TITLES[0]]
    observed = {}
    for row in dashboard.iter_rows(values_only=True):
        label = _text(row[0]) if row else ""
        if label in expected:
            observed[label] = row[1]
    mismatches = {
        label: {"expected": expected[label], "rendered": observed.get(label)}
        for label in expected
        if observed.get(label) != expected[label]
    }
    report["manual_observed"] = observed
    report["checks"]["dashboard_formulas_evaluate"] = {
        "result": "PASS" if not mismatches else "FAIL",
        "compared": len(expected),
        "mismatches": mismatches,
    }
    # Round-6 closure: the *criticality* counters are checked the same way -- from
    # the LibreOffice-recalculated copy, never from a stale cached value and never
    # from the formula text alone.
    criticality_expected = {}
    mandatory_sheet = workbook[SHEET_TITLES[3]]
    mandatory_headers = [
        _text(cell.value) for cell in next(mandatory_sheet.iter_rows(min_row=1, max_row=1))
    ]
    criticality_columns = ("★", "否决性", "强制性类型", "否决依据")
    criticality_values = {name: [] for name in criticality_columns}
    if all(name in mandatory_headers for name in criticality_columns):
        for row in mandatory_sheet.iter_rows(min_row=2, values_only=True):
            for name in criticality_columns:
                index = mandatory_headers.index(name)
                criticality_values[name].append(
                    _text(row[index]) if len(row) > index else ""
                )
    criticality_expected = {
        "带源标记的复核条目数（★）": sum(
            1 for value in criticality_values["★"] if value == "★"
        ),
        "实质性要求条目数（源依据）": sum(
            1
            for value in criticality_values["强制性类型"]
            if value.startswith("SUBSTANTIVE")
        ),
        "明示或可证明否决项数": sum(
            1 for value in criticality_values["否决性"] if value == "是"
        ),
        "其中：明示否决（源文明确示后果）": sum(
            1 for value in criticality_values["否决依据"] if value.startswith("EXPLICIT")
        ),
        "其中：推导否决（源文实质性要求规则）": sum(
            1 for value in criticality_values["否决依据"] if value.startswith("DERIVED")
        ),
    }
    criticality_observed = {}
    for row in dashboard.iter_rows(values_only=True):
        label = _text(row[0]) if row else ""
        if label in criticality_expected:
            criticality_observed[label] = row[1]
    criticality_mismatches = {
        label: {"expected": criticality_expected[label], "recalculated": criticality_observed.get(label)}
        for label in criticality_expected
        if criticality_observed.get(label) != criticality_expected[label]
    }
    report["criticality_expected"] = criticality_expected
    report["criticality_observed"] = criticality_observed
    report["checks"]["criticality_counters_evaluate"] = {
        "result": (
            "PASS"
            if not criticality_mismatches and len(criticality_observed) == len(criticality_expected)
            else "FAIL"
        ),
        "compared": len(criticality_expected),
        "mismatches": criticality_mismatches,
    }
    # the source-marker label must never read as a count of source occurrences
    criticality_labels = [
        _text(row[0]) for row in dashboard.iter_rows(values_only=True) if row and _text(row[0])
    ]
    misreadable = [
        label
        for label in criticality_labels
        if "源标记条款数" in label
        or "源标记出现次数" in label
        or ("源文件标记" in label and "出现次数" in label)
    ]
    report["checks"]["source_marker_label_is_row_count"] = {
        "result": "PASS" if not misreadable else "FAIL",
        "misreadable": misreadable,
    }
    formula_errors = []
    computed = load_workbook(xlsx_path, data_only=True)
    for worksheet in computed.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                value = _text(cell.value)
                if any(marker in value for marker in ERROR_MARKERS):
                    formula_errors.append(f"{worksheet.title}!{cell.coordinate}={value}")
    report["checks"]["recalculated_workbook_has_no_errors"] = {
        "result": "PASS" if not formula_errors else "FAIL",
        "cells": formula_errors[:12],
    }
    values.close()
    computed.close()

    clipping = {
        sheet: risks
        for sheet, risks in report["clipping_risks"].items()
        if risks
    }
    dashboard_risks = [risk for risk in clipping.get(SHEET_TITLES[0], [])]
    report["checks"]["no_clipped_dashboard_text"] = {
        "result": "PASS" if not dashboard_risks else "FAIL",
        "cells": dashboard_risks[:8],
    }
    report["clipping_total"] = sum(len(risks) for risks in clipping.values())
    report["checks"]["clipping_bounded"] = {
        "result": "PASS" if report["clipping_total"] == 0 else "WARN",
        "total": report["clipping_total"],
        "worst": sorted(
            (
                {"sheet": risk["sheet"], "cell": risk["cell"],
                 "needed": risk["lines_needed"], "available": risk["lines_available"]}
                for risks in clipping.values()
                for risk in risks
            ),
            key=lambda item: item["needed"] - item["available"],
            reverse=True,
        )[:10],
    }
    workbook.close()

    failed = [name for name, check in report["checks"].items() if check["result"] == "FAIL"]
    report["result"] = "PASS" if not failed else "FAIL"
    report["failed_checks"] = failed
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"REVIEW_WORKBOOK_VISUAL_QA {report['result']}")
    for name, check in report["checks"].items():
        print(f"  {check['result']:4} {name}: {json.dumps(check, ensure_ascii=False)[:220]}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
