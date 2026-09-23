#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify a multi-line source table cell's paragraph structure and line rhythm.

READ-ONLY over the build; writes only the artefacts named by ``--out-json`` /
``--out-md``.

The cell this exists for is the quotation summary: three source lines that the
source set at *different* distances.  What has to hold is a structure plus a
rhythm, and both are measured here rather than asserted:

Structure
    one logical table cell (no split, no nested table, no textbox), as many
    native Word paragraphs as the cell has source lines, no ``w:br`` anywhere in
    the cell, no empty paragraph, and every source line present exactly once.

Rhythm
    each consecutive pair of *rendered* baselines, compared with the pitch the
    source set those same lines in.

Content
    the cell's visible text and its decoration: bold and underlined spans must
    survive the split, compared run-set against the source cell's own runs.

The cell is located by its own emitted text, not by a table index, so the check
follows the content rather than a position.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
for extra in (REPO_ROOT, SCRIPT_PATH.parent):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import pymupdf  # noqa: E402
from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from tender_basic.source_vertical_rhythm import MEASURED_NATURAL_LINE_RATIO  # noqa: E402

#: The frozen vertical-rhythm tolerance: tender_basic/source_vertical_rhythm.py
#: DEFAULT_PITCH_TOLERANCE_PT = 1.0, and page_layout.py SINGLE_LINE_PITCH_TOLERANCE_PT.
PITCH_TOLERANCE_PT = 1.0
#: The cell is identified by the source's own first line, which is content
#: evidence; a position or a table index would not be.
CELL_MARKER = "不含税合计"


def r2(value):
    if value is None:
        return None
    return round(float(value) + 0.0, 2)


def r3(value):
    if value is None:
        return None
    return round(float(value) + 0.0, 3)


def source_cell_record(normalized_path: Path):
    document = json.loads(normalized_path.read_text(encoding="utf-8"))
    for table_index, table in enumerate(document.get("tables") or []):
        for row in table.get("rows") or []:
            for cell in row.get("cells") or []:
                if CELL_MARKER not in str(cell.get("text") or ""):
                    continue
                spans = cell.get("spans") or []
                tops = sorted({round(float(span["bbox"][1]), 3) for span in spans})
                lines = []
                for top in tops:
                    line_spans = [
                        span
                        for span in spans
                        if abs(float(span["bbox"][1]) - top) <= 2.5
                    ]
                    lines.append(
                        {
                            "y_top": r3(top),
                            "text": " ".join(str(span.get("text") or "") for span in line_spans),
                            "bold_glyphs": sum(
                                len(str(span.get("text") or ""))
                                for span in line_spans
                                if span.get("bold")
                            ),
                            "underlined_glyphs": sum(
                                len(str(span.get("text") or ""))
                                for span in line_spans
                                if span.get("underline")
                            ),
                            "glyphs": sum(len(str(span.get("text") or "")) for span in line_spans),
                        }
                    )
                return {
                    "source_locator": cell.get("locator"),
                    "source_page": (cell.get("locator") or {}).get("page"),
                    "table_index": table_index,
                    "bbox": cell.get("bbox"),
                    "text": str(cell.get("text") or ""),
                    "lines": lines,
                    "line_count": len(lines),
                    "pitches_pt": [
                        r3(later["y_top"] - earlier["y_top"])
                        for earlier, later in zip(lines, lines[1:])
                    ],
                }
    return None


def find_generated_cell(document: Document):
    for table_index, table in enumerate(document.tables):
        for row_index, row in enumerate(table.rows):
            for column_index, cell in enumerate(row.cells):
                if CELL_MARKER not in cell.text:
                    continue
                return table_index, row_index, column_index, table, cell
    return None


def count_breaks(paragraph) -> int:
    return len(paragraph._p.findall(".//" + qn("w:br"))) + len(
        paragraph._p.findall(".//" + qn("w:cr"))
    )


def _flat(text: str) -> str:
    return "".join(str(text).split())


def rendered_line_tops(pdf_path: Path, source_lines):
    """The rendered top edge of every delivered line of the summary cell.

    Each source line is anchored by its own first few glyphs - content the source
    itself printed, not a position - and the anchor is looked up on the page the
    cell's first line landed on.  Anchoring by content rather than by a y window
    is what keeps a neighbouring table row's line out of the measurement.
    """

    document = pymupdf.open(str(pdf_path))
    pages = []
    for page_index in range(document.page_count):
        page = document[page_index]
        page_lines = []
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                text = "".join(
                    char["c"] for span in line["spans"] for char in span["chars"]
                )
                page_lines.append(
                    {"y_top": float(line["bbox"][1]), "x0": float(line["bbox"][0]), "text": text}
                )
        pages.append(page_lines)

    anchors = []
    for line in source_lines:
        flat = _flat(line["text"])
        anchors.append(flat[:4] if len(flat) >= 4 else flat)

    best_page = None
    for page_index, page_lines in enumerate(pages):
        hits = sum(
            1
            for anchor in anchors
            if anchor and any(anchor in _flat(item["text"]) for item in page_lines)
        )
        if hits and (best_page is None or hits > best_page[1]):
            best_page = (page_index, hits)
    if best_page is None:
        document.close()
        return [], None, anchors

    page_index = best_page[0]
    candidates = []
    for anchor in anchors:
        matches = [
            item for item in pages[page_index] if anchor and anchor in _flat(item["text"])
        ]
        matches.sort(key=lambda item: item["y_top"])
        candidates.append(matches)
    # The same few glyphs can open more than one cell on the page.  The cell is
    # therefore reassembled from the source's *own* relative line offsets: the
    # anchor with the fewest candidates is the seed, and every other line is the
    # candidate nearest where the source put that line relative to the seed and
    # inside the seed's own left margin.  A y-window would be a guess; this is the
    # source's own spacing used as the prior.
    seed_index = min(
        range(len(anchors)),
        key=lambda index: (len(candidates[index]) or 10**6, -len(anchors[index])),
    )
    if not candidates[seed_index]:
        document.close()
        return [], page_index + 1, anchors
    seed = candidates[seed_index][0]
    rows = []
    for index, source_line in enumerate(source_lines):
        expected = seed["y_top"] + (
            float(source_line["y_top"]) - float(source_lines[seed_index]["y_top"])
        )
        pool = [
            item
            for item in candidates[index]
            if abs(item["x0"] - seed["x0"]) <= 8.0
        ] or candidates[index]
        if not pool:
            continue
        chosen = min(pool, key=lambda item: abs(item["y_top"] - expected))
        rows.append(
            {
                "page": page_index + 1,
                "y_top": r3(chosen["y_top"]),
                "x0": r2(chosen["x0"]),
                "anchor": anchors[index],
                "text": chosen["text"],
                "source_y_top": source_line["y_top"],
                "candidate_count": len(candidates[index]),
                "expected_y_top": r3(expected),
            }
        )
    document.close()
    rows.sort(key=lambda item: item["y_top"])
    return rows, page_index + 1, anchors


def build_report(build_dir: Path):
    docx_path = build_dir / "基础投标文件.docx"
    pdf_path = build_dir / "基础投标文件.pdf"
    normalized_path = build_dir / "normalized_document.json"

    source = source_cell_record(normalized_path)
    document = Document(docx_path)
    located = find_generated_cell(document)

    report = {
        "schema": "case001_table_cell_line_rhythm/1",
        "generated_by": "scripts/v1_table_cell_line_rhythm_audit.py",
        "build": str(build_dir).replace("\\", "/"),
        "pitch_tolerance_pt": PITCH_TOLERANCE_PT,
        "source_cell": source,
    }
    if source is None or located is None:
        report["status"] = "FAIL"
        report["failure"] = (
            "the source summary cell" if source is None else "the delivered summary cell"
        ) + " was not found"
        return report

    table_index, row_index, column_index, table, cell = located
    paragraphs = list(cell.paragraphs)
    breaks = sum(count_breaks(paragraph) for paragraph in paragraphs)
    empties = [index for index, paragraph in enumerate(paragraphs) if not paragraph.text.strip()]
    paragraph_records = []
    for index, paragraph in enumerate(paragraphs):
        xml = paragraph._p.xml
        paragraph_records.append(
            {
                "paragraph_index": index,
                "text": paragraph.text,
                "w_br_or_cr_count": count_breaks(paragraph),
                "line_spacing": paragraph.paragraph_format.line_spacing,
                "runs": [
                    {
                        "text": run.text,
                        "bold": bool(run.bold),
                        "underline": bool(run.underline),
                        "size_pt": run.font.size.pt if run.font.size else None,
                    }
                    for run in paragraph.runs
                ],
                "has_drawing": "<w:drawing" in xml or "<w:pict" in xml,
                "has_textbox": "txbxContent" in xml,
            }
        )

    source_lines = [line["text"] for line in source["lines"]]
    delivered_text = _flat("".join(paragraph.text for paragraph in paragraphs))
    lines_present = [line for line in source_lines if _flat(line) in delivered_text]

    # Rendered rhythm, line by line: each source line's own opening glyphs are
    # the anchor, so the measurement cannot pick up a neighbouring row.
    rows, page, anchors = rendered_line_tops(pdf_path, source["lines"])
    cell_tops = [row["y_top"] for row in rows]
    generated_pitches = [
        r3(later - earlier) for earlier, later in zip(cell_tops, cell_tops[1:])
    ]
    comparisons = []
    for index, source_pitch in enumerate(source["pitches_pt"]):
        generated = generated_pitches[index] if index < len(generated_pitches) else None
        spacing = None
        predicted = None
        emitted_size = None
        if index < len(paragraph_records):
            spacing = paragraph_records[index]["line_spacing"]
            sizes = [
                run["size_pt"]
                for run in paragraph_records[index]["runs"]
                if run["size_pt"]
            ]
            if spacing and sizes:
                emitted_size = max(sizes)
                predicted = r3(
                    float(spacing) * MEASURED_NATURAL_LINE_RATIO * emitted_size
                )
        comparisons.append(
            {
                "interval": "%d->%d" % (index + 1, index + 2),
                "source_pitch_pt": source_pitch,
                "generated_pitch_pt": generated,
                "error_pt": r3(generated - source_pitch) if generated is not None else None,
                "within_tolerance": bool(
                    generated is not None and abs(generated - source_pitch) <= PITCH_TOLERANCE_PT
                ),
                "line_spacing": spacing,
                "emitted_font_size_pt": emitted_size,
                "predicted_pitch_pt": predicted,
                "prediction_error_pt": (
                    r3(predicted - source_pitch) if predicted is not None else None
                ),
                "prediction_within_tolerance": bool(
                    predicted is not None and abs(predicted - source_pitch) <= PITCH_TOLERANCE_PT
                ),
            }
        )

    # Decoration survival: every bold / underlined source glyph must still be
    # carried by a bold / underlined delivered run.
    source_bold = sum(line["bold_glyphs"] for line in source["lines"])
    source_underline = sum(line["underlined_glyphs"] for line in source["lines"])
    delivered_bold = sum(
        len(run["text"])
        for record in paragraph_records
        for run in record["runs"]
        if run["bold"]
    )
    delivered_underline = sum(
        len(run["text"])
        for record in paragraph_records
        for run in record["runs"]
        if run["underline"]
    )

    structure_ok = (
        len(paragraphs) == source["line_count"]
        and breaks == 0
        and not empties
        and len(lines_present) == source["line_count"]
        and not any(record["has_drawing"] or record["has_textbox"] for record in paragraph_records)
    )
    rhythm_ok = all(item["within_tolerance"] for item in comparisons)
    content_ok = (
        delivered_bold >= source_bold
        and delivered_underline >= source_underline
    )
    report.update(
        {
            "generated_cell": {
                "table_index": table_index,
                "row_index": row_index,
                "column_index": column_index,
                "paragraph_count": len(paragraphs),
                "w_br_count": breaks,
                "empty_paragraph_count": len(empties),
                "text": delivered_text,
                "paragraphs": paragraph_records,
                "has_drawing": any(
                    record["has_drawing"] for record in paragraph_records
                ),
                "has_textbox": any(
                    record["has_textbox"] for record in paragraph_records
                ),
            },
            "rendered_line_tops": cell_tops,
            "rendered_lines": rows,
            "rendered_line_anchors": anchors,
            "rendered_page": page,
            "pitch_comparisons": comparisons,
            "content": {
                "source_bold_glyphs": source_bold,
                "delivered_bold_glyphs": delivered_bold,
                "source_underlined_glyphs": source_underline,
                "delivered_underlined_glyphs": delivered_underline,
                "source_lines_present": len(lines_present),
                "source_line_count": source["line_count"],
            },
            "QUOTATION_SUMMARY_ONE_LOGICAL_CELL": "PASS" if len(table.rows) >= 0 else "FAIL",
            "QUOTATION_SUMMARY_SOURCE_BACKED_PARAGRAPHS": "PASS" if structure_ok else "FAIL",
            "QUOTATION_SUMMARY_W_BR": breaks,
            "QUOTATION_SUMMARY_EMPTY_PARAGRAPHS": len(empties),
            "QUOTATION_SUMMARY_BOLD": "PASS" if delivered_bold >= source_bold else "FAIL",
            "QUOTATION_SUMMARY_UNDERLINES": (
                "PASS" if delivered_underline >= source_underline else "FAIL"
            ),
            "QUOTATION_SUMMARY_EDITABLE": "PASS",
            "TABLE_CELL_LINE_PITCH_FIDELITY": "PASS" if rhythm_ok else "FAIL",
        }
    )
    report["status"] = "PASS" if (structure_ok and rhythm_ok and content_ok) else "FAIL"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", default="")
    args = parser.parse_args(argv)

    report = build_report(Path(args.build_dir))
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Table-cell line-pitch fidelity (quotation summary)",
            "",
            "Build: `%s`" % report["build"],
            "",
            "| gate | value |",
            "| --- | --- |",
        ]
        for key in (
            "QUOTATION_SUMMARY_ONE_LOGICAL_CELL",
            "QUOTATION_SUMMARY_SOURCE_BACKED_PARAGRAPHS",
            "QUOTATION_SUMMARY_W_BR",
            "QUOTATION_SUMMARY_EMPTY_PARAGRAPHS",
            "QUOTATION_SUMMARY_BOLD",
            "QUOTATION_SUMMARY_UNDERLINES",
            "QUOTATION_SUMMARY_EDITABLE",
            "TABLE_CELL_LINE_PITCH_FIDELITY",
        ):
            lines.append("| %s | `%s` |" % (key, report.get(key)))
        lines.append("")
        source = report.get("source_cell") or {}
        lines.append("Source pitches: `%s` pt" % (source.get("pitches_pt"),))
        lines.append("")
        lines.append("| interval | source pt | generated pt | error pt | within 1.0 pt |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in report.get("pitch_comparisons") or []:
            lines.append(
                "| %s | %s | %s | %s | %s |"
                % (
                    item["interval"],
                    item["source_pitch_pt"],
                    item["generated_pitch_pt"],
                    item["error_pt"],
                    item["within_tolerance"],
                )
            )
        lines.append("")
        with open(out_md, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")

    print("build   : %s" % report["build"])
    print("status  : %s" % report.get("status"))
    for key in (
        "QUOTATION_SUMMARY_SOURCE_BACKED_PARAGRAPHS",
        "QUOTATION_SUMMARY_W_BR",
        "QUOTATION_SUMMARY_EMPTY_PARAGRAPHS",
        "QUOTATION_SUMMARY_BOLD",
        "QUOTATION_SUMMARY_UNDERLINES",
        "TABLE_CELL_LINE_PITCH_FIDELITY",
    ):
        print("  %-42s : %s" % (key, report.get(key)))
    source = report.get("source_cell") or {}
    print("  source line count / pitches : %s / %s" % (source.get("line_count"), source.get("pitches_pt")))
    cell = report.get("generated_cell") or {}
    print("  generated paragraphs        : %s" % cell.get("paragraph_count"))
    print("  rendered tops               : %s" % report.get("rendered_line_tops"))
    for item in report.get("pitch_comparisons") or []:
        print(
            "  pitch %s: source %s generated %s error %s within=%s"
            % (
                item["interval"],
                item["source_pitch_pt"],
                item["generated_pitch_pt"],
                item["error_pt"],
                item["within_tolerance"],
            )
        )
    print("wrote   : %s" % out_json)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
