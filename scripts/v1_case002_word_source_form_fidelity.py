"""CASE002 Word source-form fidelity gate with component-level verdicts.

This gate judges the delivered CASE002 Word artifact through the explicit
three-layer authority contract in :mod:`tender_basic.word_render_authority`:

* the SOURCE PDF's own glyph boxes, rule extents and row geometry,
* the DELIVERED DOCX's intended typography and geometry,
* a HEADLESS LibreOffice render as *diagnostic* evidence.

The authorization form is not a boolean "page 149 is fine": it is reported as
separate component results (source model, DOCX geometry, DOCX typography, source
slot fidelity, text completeness, headless render) plus a renderer divergence
class, and the overall verdict follows the authority contract - a proven
substitution-only divergence is a warning, an unclassifiable one is a failure.

Every mandatory measurement is required: if an input cannot be measured the gate
reports FAIL for that item rather than passing it silently.

Usage::

    python scripts/v1_case002_word_source_form_fidelity.py \
        --build acceptance/workspace/case_002/v1_word_source_fidelity_arch1 \
        --json acceptance/reports/v1_generalization/case002_word_source_form_fidelity.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pymupdf
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.word_render_authority import (  # noqa: E402
    DOCX_TYPOGRAPHY_AUTHORITY,
    HEADLESS_RENDERER_ROLE,
    HOST_FONT_ABSENT,
    HOST_FONT_INSTALLED,
    HOST_FONT_UNKNOWN,
    SOURCE_GEOMETRY_AUTHORITY,
    SourceFidelityProofs,
    SourceRowMeasurement,
    SourceTypographyEvidence,
    WORD_DESKTOP_ROLE,
    classify_renderer_divergence,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DEFAULT_SOURCE = ROOT / "acceptance/private/营收系统整合和硬件系统升级项目招标文件.pdf"
WINDOWS_FONTS = Path("C:/Windows/Fonts")
#: The source row of the authorization opening paragraph whose composed width the
#: headless render may overrun by a proven substitute-font advance difference.
AUTHORIZATION_TARGET_ROW_Y = 169.14
#: The portrait frame's right text boundary, used to derive a row's own capacity.
PORTRAIT_TEXT_RIGHT_PT = 511.44


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_rows(page, y_from: float, y_to: float) -> list[dict]:
    rows = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"])
            if not text.strip():
                continue
            y0 = float(line["bbox"][1])
            if not (y_from <= y0 <= y_to):
                continue
            rows.append(
                {
                    "y": round(y0, 2),
                    "x0": round(float(line["bbox"][0]), 2),
                    "x1": round(float(line["bbox"][2]), 2),
                    "text": text.strip(),
                    "chars": len(text.strip()),
                    "fonts": sorted({span["font"] for span in line["spans"]}),
                    "sizes": sorted(
                        {round(float(span["size"]), 2) for span in line["spans"]}
                    ),
                }
            )
    return sorted(rows, key=lambda row: (row["y"], row["x0"]))


def find_page(pdf, *needles: str) -> int | None:
    for number in range(1, pdf.page_count + 1):
        text = "".join(pdf[number - 1].get_text().split())
        if all(needle in text for needle in needles):
            return number
    return None


def font_state(family: str | None) -> str:
    """Whether the host provides ``family`` (names only; no font files are read)."""

    if not family:
        return HOST_FONT_UNKNOWN
    try:
        candidates = [path.stem.lower() for path in WINDOWS_FONTS.glob("*")]
    except OSError:
        return HOST_FONT_UNKNOWN
    if not candidates:
        return HOST_FONT_UNKNOWN
    key = "".join(str(family).split()).lower()
    for candidate in candidates:
        if key and (key in candidate or candidate in key):
            return HOST_FONT_INSTALLED
    return HOST_FONT_ABSENT


def paragraph_fonts(document: Document, needle: str) -> dict | None:
    for paragraph in document.paragraphs:
        if needle not in paragraph.text:
            continue
        style_ea = None
        if paragraph.style is not None:
            style_rpr = paragraph.style.element.find(f"{W}rPr")
            if style_rpr is not None:
                style_fonts = style_rpr.find(f"{W}rFonts")
                if style_fonts is not None:
                    style_ea = style_fonts.get(f"{W}eastAsia")
        for run in paragraph.runs:
            if not run.text.strip():
                continue
            rpr = run._element.find(f"{W}rPr")
            if rpr is None:
                continue
            fonts = rpr.find(f"{W}rFonts")
            spacing = rpr.find(f"{W}spacing")
            return {
                "east_asia": (fonts.get(f"{W}eastAsia") if fonts is not None else None)
                or style_ea,
                "ascii": fonts.get(f"{W}ascii") if fonts is not None else None,
                "hansi": fonts.get(f"{W}hAnsi") if fonts is not None else None,
                "cs": fonts.get(f"{W}cs") if fonts is not None else None,
                "size_pt": run.font.size.pt if run.font.size else None,
                "spacing_twips": (
                    int(spacing.get(f"{W}val")) if spacing is not None else None
                ),
            }
    return None


def runs_of(document: Document, needle: str) -> list[dict]:
    for paragraph in document.paragraphs:
        if needle in paragraph.text:
            return [
                {"text": run.text, "underline": run.underline}
                for run in paragraph.runs
                if run.text
            ]
    return []


def check(passed: bool | None, detail: str) -> dict:
    return {
        "result": "FAIL" if passed is None else ("PASS" if passed else "FAIL"),
        "detail": detail,
    }


def build_report(build: Path) -> dict:
    build = build.resolve()
    docx_path = build / "基础投标文件.docx"
    pdf_path = build / "基础投标文件.pdf"
    report_path = build / "generation_report.json"
    document = Document(docx_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    results: dict[str, dict] = {}

    with pymupdf.open(DEFAULT_SOURCE) as source, pymupdf.open(pdf_path) as rendered:
        source_page_number = find_page(source, "四、授权委托书", "注册于")
        rendered_page_number = find_page(rendered, "四、授权委托书", "注册于")

        source_rows = (
            text_rows(source[source_page_number - 1], 100.0, 200.0)
            if source_page_number
            else []
        )
        rendered_rows = (
            text_rows(rendered[rendered_page_number - 1], 60.0, 260.0)
            if rendered_page_number
            else []
        )
        source_row = next(
            (row for row in source_rows if abs(row["y"] - AUTHORIZATION_TARGET_ROW_Y) < 0.5),
            None,
        )
        rendered_row = (
            max(rendered_rows, key=lambda row: row["x1"] - row["x0"])
            if rendered_rows
            else None
        )
        results["AUTHORIZATION_SOURCE_MODEL_FIDELITY"] = check(
            bool(source_row) and bool(rendered_rows),
            f"source rows measured={len(source_rows)} rendered rows={len(rendered_rows)}",
        )

        # The first source row of the paragraph and the first rendered row of it
        # must share the source's own origin.
        first_source = next((row for row in source_rows if row["y"] < 130), None)
        first_render = next((row for row in rendered_rows if row["y"] > 120), None)
        geometry_ok = None
        if first_source and first_render:
            geometry_ok = abs(first_render["x0"] - first_source["x0"]) <= 2.0
        results["AUTHORIZATION_DOCX_GEOMETRY_FIDELITY"] = check(
            geometry_ok,
            "first row origin source="
            f"{first_source['x0'] if first_source else None} rendered="
            f"{first_render['x0'] if first_render else None}",
        )

        fonts = paragraph_fonts(document, "注册于")
        rendered_fonts = sorted({name for row in rendered_rows for name in row["fonts"]})
        source_fonts = sorted({name for row in source_rows for name in row["fonts"]})
        host_state = font_state(fonts["east_asia"] if fonts else None)
        typography = SourceTypographyEvidence(
            source_family=source_fonts[0] if source_fonts else None,
            source_size_pt=(
                source_row["sizes"][0] if source_row and source_row["sizes"] else None
            ),
            docx_east_asia=(fonts or {}).get("east_asia"),
            docx_ascii=(fonts or {}).get("ascii"),
            docx_hansi=(fonts or {}).get("hansi"),
            docx_cs=(fonts or {}).get("cs"),
            docx_size_pt=(fonts or {}).get("size_pt"),
            docx_character_spacing_twips=(fonts or {}).get("spacing_twips"),
            host_font_state=host_state,
            headless_family=rendered_fonts[0] if rendered_fonts else None,
            headless_size_pt=(
                rendered_row["sizes"][0]
                if rendered_row and rendered_row["sizes"]
                else None
            ),
        )
        results["AUTHORIZATION_DOCX_TYPOGRAPHY_FIDELITY"] = check(
            typography.docx_matches_source if typography.evidence_complete else None,
            f"source={typography.source_family!r}@{typography.source_size_pt} "
            f"docx={typography.docx_requested_family!r}@{typography.docx_size_pt} "
            f"host={host_state} headless={typography.headless_family!r}",
        )

        row = SourceRowMeasurement(
            row_id="AUTHORIZATION_OPENING",
            source_char_count=source_row["chars"] if source_row else None,
            source_used_width_pt=(
                (source_row["x1"] - source_row["x0"]) if source_row else None
            ),
            source_available_width_pt=(
                (PORTRAIT_TEXT_RIGHT_PT - source_row["x0"]) if source_row else None
            ),
            headless_char_count=rendered_row["chars"] if rendered_row else None,
            headless_used_width_pt=(
                (rendered_row["x1"] - rendered_row["x0"]) if rendered_row else None
            ),
        )
        breaks = report.get("positioned_form_layout_breaks") or []
        cursor = report.get("source_form_row_cursor") or {}
        ownership_ok = all(
            int(cursor.get(key) or 0) == 0
            for key in (
                "default_tab_fallthrough_risk_count",
                "tabs_without_explicit_stop_count",
                "consecutive_blank_double_ownership_count",
                "cursor_recomputed_from_paragraph_width_count",
            )
        )

    # ---- text completeness and source slots ---------------------------------- #
    docx_text = "".join(paragraph.text for paragraph in document.paragraphs)
    docx_text += "".join(
        cell.text
        for table in document.tables
        for table_row in table.rows
        for cell in table_row.cells
    )
    key_phrases = ["授权委托书", "工商行政管理局名称", "投标人全称", "全权代表姓名"]
    missing = [phrase for phrase in key_phrases if phrase not in docx_text]
    results["AUTHORIZATION_TEXT_COMPLETENESS"] = check(
        not missing, f"missing={missing}" if missing else "all key phrases present"
    )
    results["AUTHORIZATION_SOURCE_SLOT_FIDELITY"] = check(
        "授权委托书" in docx_text,
        f"tables={len(document.tables)} authorization wording present",
    )

    proofs = SourceFidelityProofs(
        docx_geometry_matches_source=geometry_ok,
        row_ownership_correct=ownership_ok and not breaks,
        text_complete_and_ordered=not missing,
        source_slots_preserved="授权委托书" in docx_text,
        no_true_geometry_defect=not breaks,
    )
    classification = classify_renderer_divergence(
        typography=typography, row=row, proofs=proofs
    )
    results["AUTHORIZATION_HEADLESS_RENDER_FIDELITY"] = {
        "result": (
            "WARN_PROVEN_FONT_SUBSTITUTION"
            if classification.is_substitution_only
            else ("PASS" if not classification.blocking else "FAIL")
        ),
        "detail": classification.reasons[0] if classification.reasons else "",
    }
    results["AUTHORIZATION_RENDERER_DIVERGENCE_CLASS"] = {
        "result": classification.divergence_class,
        "detail": json.dumps(classification.evidence, ensure_ascii=False)[:400],
    }
    required_components = (
        "AUTHORIZATION_SOURCE_MODEL_FIDELITY",
        "AUTHORIZATION_DOCX_GEOMETRY_FIDELITY",
        "AUTHORIZATION_DOCX_TYPOGRAPHY_FIDELITY",
        "AUTHORIZATION_TEXT_COMPLETENESS",
        "AUTHORIZATION_SOURCE_SLOT_FIDELITY",
    )
    components_ok = all(
        results[key]["result"] == "PASS" for key in required_components
    ) and not classification.blocking
    results["AUTHORIZATION_FORM_FIDELITY"] = check(
        components_ok,
        f"components_ok={components_ok} divergence={classification.divergence_class}",
    )

    # ---- opening table -------------------------------------------------------- #
    opening_tables = [
        table
        for table in document.tables
        if "实施周期" in "".join(cell.text for row_ in table.rows for cell in row_.cells)
    ]
    opening = opening_tables[0] if opening_tables else None
    opening_text = (
        "".join(cell.text for row_ in opening.rows for cell in row_.cells)
        if opening is not None
        else ""
    )
    opening_compact = opening_text.replace(" ", "")
    opening_ok = (
        len(opening_tables) == 1
        and "18个月" in opening_compact
        and "西安市内" in opening_text
    )
    results["OPENING_TABLE_FORM_SLOT_FIDELITY"] = check(
        opening_ok,
        f"tables_with_实施周期={len(opening_tables)} "
        f"18个月={'18个月' in opening_compact} "
        f"西安市内={'西安市内' in opening_text}",
    )

    # ---- banked invariants ---------------------------------------------------- #
    # The whole response letter - its contact block *and* its own date row - must
    # stay on one generated page, not merely appear somewhere once.
    with pymupdf.open(pdf_path) as rendered:
        letter_pages = []
        for number in range(1, rendered.page_count + 1):
            text = "".join(rendered[number - 1].get_text().split())
            if "投标单位全称" in text:
                letter_pages.append(number)
                if "日期" not in text:
                    letter_pages.append(f"page {number} lacks the letter date row")
    letter_ok = len(letter_pages) == 1
    results["LETTER_SINGLE_PAGE_FIDELITY"] = check(
        letter_ok, f"pages carrying 投标单位全称 and its date row={letter_pages}"
    )

    cover_slots = 0
    for paragraph in document.paragraphs:
        text = paragraph.text
        if "年" in text and "月" in text and "日" in text:
            blanks = [run for run in paragraph.runs if run.underline and not run.text.strip()]
            cover_slots = max(cover_slots, len(blanks))
    results["COVER_DATE_THREE_SLOT_FIDELITY"] = check(
        cover_slots >= 3, f"underline blank runs in a 年月日 row={cover_slots}"
    )

    name_runs = runs_of(document, "收到贵公司")
    name_ok = any(run["underline"] for run in name_runs if run["text"].strip())
    results["PROJECT_NAME_SOURCE_SLOT"] = check(
        name_ok, f"underlined value run present={name_ok}"
    )

    upper = [
        run
        for paragraph in document.paragraphs
        if "大写" in paragraph.text
        for run in paragraph.runs
        if run.underline
    ]
    lower = [
        run
        for paragraph in document.paragraphs
        if "小写" in paragraph.text
        for run in paragraph.runs
        if run.underline
    ]
    results["BID_TOTAL_UPPERCASE_SLOT"] = check(bool(upper), f"underlined runs={len(upper)}")
    results["BID_TOTAL_LOWERCASE_SLOT"] = check(bool(lower), f"underlined runs={len(lower)}")

    manager_ok = any(
        "项目负责人" in paragraph.text and "。" in paragraph.text
        for paragraph in document.paragraphs
    )
    results["PROJECT_MANAGER_SAME_ROW_SLOT"] = check(
        manager_ok, f"paragraphs with 项目负责人 and 。={manager_ok}"
    )

    invariants = {
        "default_tab_fallthrough_risk_count": int(
            cursor.get("default_tab_fallthrough_risk_count") or 0
        ),
        "tabs_without_explicit_stop_count": int(
            cursor.get("tabs_without_explicit_stop_count") or 0
        ),
        "consecutive_blank_double_ownership_count": int(
            cursor.get("consecutive_blank_double_ownership_count") or 0
        ),
        "cursor_recomputed_from_paragraph_width_count": int(
            cursor.get("cursor_recomputed_from_paragraph_width_count") or 0
        ),
        "positioned_form_layout_break_count": len(breaks),
    }
    invariants_ok = all(value == 0 for value in invariants.values())

    biggest = max(
        document.tables,
        key=lambda table: len(table.rows) * max(1, len(table.columns)),
        default=None,
    )
    table_ok = biggest is not None and len(biggest.rows) >= 20
    results["CASE002_CROSS_PAGE_QUOTATION_TABLE"] = check(
        table_ok,
        f"largest table rows={len(biggest.rows) if biggest is not None else None} "
        f"cols={len(biggest.columns) if biggest is not None else None}",
    )

    overall = (
        components_ok
        and opening_ok
        and letter_ok
        and cover_slots >= 3
        and name_ok
        and bool(upper)
        and bool(lower)
        and manager_ok
        and invariants_ok
        and table_ok
    )
    return {
        "schema": "v1_case002_word_source_form_fidelity/2",
        "build": (
            str(build.relative_to(ROOT)).replace("\\", "/")
            if build.is_relative_to(ROOT)
            else str(build)
        ),
        "authorities": {
            "SOURCE_GEOMETRY_AUTHORITY": SOURCE_GEOMETRY_AUTHORITY,
            "DOCX_TYPOGRAPHY_AUTHORITY": DOCX_TYPOGRAPHY_AUTHORITY,
            "HEADLESS_RENDERER_ROLE": HEADLESS_RENDERER_ROLE,
            "WORD_DESKTOP_ROLE": WORD_DESKTOP_ROLE,
        },
        "components": results,
        "renderer_divergence": classification.as_dict(),
        "generic_invariants": invariants,
        "artifacts": {
            "docx_sha256": sha256(docx_path),
            "pdf_sha256": sha256(pdf_path),
            "generation_report_sha256": sha256(report_path),
        },
        "CASE002_WORD_SOURCE_FORM_FIDELITY": "PASS" if overall else "FAIL",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    report = build_report(args.build)
    for name, entry in report["components"].items():
        print(f"{name} = {entry['result']}  ({entry['detail'][:120]})")
    print("generic_invariants =", json.dumps(report["generic_invariants"]))
    print(
        "CASE002_WORD_SOURCE_FORM_FIDELITY =",
        report["CASE002_WORD_SOURCE_FORM_FIDELITY"],
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", args.json)
    return 0 if report["CASE002_WORD_SOURCE_FORM_FIDELITY"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
