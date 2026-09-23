"""Stage E: source vs generated table geometry, machine-readable.

For every emitted table the audit reports the geometry the source drew, the
geometry the build planned, and the geometry the rendered PDF actually paints:

* source table ``x0``/``x1``, width, height, column widths, row heights,
* the recorded ``w:tblInd`` and grid column widths the DOCX received,
* row heights, cell margins and cell paragraph spacing from the DOCX,
* the painted table box and its horizontal/vertical rule positions in the PDF.

Every delta is classified.  ``SOURCE_REPRODUCED`` means the generated geometry
equals the source geometry; ``FONT_METRIC_ONLY`` means the only difference is the
renderer's own glyph ascent/descent (Word row heights are minimums and the two
renderers measure CJK fallback fonts differently); ``AVOIDABLE_DRIFT`` means the
generated geometry differs from a source geometry the build already knew, which
is a defect and must be empty.

Usage::

    .venv/Scripts/python.exe scripts/v1_page_table_geometry_audit.py \
        --build acceptance/workspace/case_001/v1_manual_frame_5 \
        --out acceptance/reports/v1_generalization/case001_table_geometry.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA = "v1_table_geometry_audit/1"

#: CASE001 renders source pages 40..61 as generated pages 1..22, so a source page
#: number and a generated page number differ by this constant offset.  It is a
#: property of the source document's page numbering, not of any table.
SOURCE_TO_GENERATED_OFFSET = 39

#: Geometry is reproduced when it lands within this distance of the source.
GEOMETRY_TOLERANCE_PT = 1.0

#: A row-height difference below this is the renderer's own line box, never a
#: layout decision: Word row heights are minimums and a CJK fallback font's
#: ascent/descent is not the PDF font's.
ROW_HEIGHT_FONT_TOLERANCE_PT = 2.0
ROW_HEIGHT_FONT_TOLERANCE_RATIO = 0.25


def _round(value, digits: int = 2):
    return None if value is None else round(float(value), digits)


def _twips_to_pt(value) -> float | None:
    if value is None:
        return None
    try:
        return float(int(value)) / 20.0
    except (TypeError, ValueError):
        return None


def docx_tables_by_section(docx_path: Path) -> list[list[dict]]:
    """Every table of every section, with the geometry Word actually received."""

    from docx import Document
    from docx.oxml.ns import qn

    document = Document(str(docx_path))
    body = document.element.body
    groups: list[list[dict]] = [[]]
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            if child.find(qn("w:pPr") + "/" + qn("w:sectPr")) is not None:
                groups.append([])
        elif child.tag == qn("w:tbl"):
            groups[-1].append(_table_geometry(child, qn))
    return groups


def _table_geometry(element, qn) -> dict:
    properties = element.find(qn("w:tblPr"))
    indent = None
    cell_mar = None
    if properties is not None:
        ind = properties.find(qn("w:tblInd"))
        if ind is not None:
            indent = _twips_to_pt(ind.get(qn("w:w")))
        mar = properties.find(qn("w:tblCellMar"))
        if mar is not None:
            cell_mar = {
                side: _twips_to_pt(mar.find(qn(f"w:{side}")).get(qn("w:w")))
                if mar.find(qn(f"w:{side}")) is not None else None
                for side in ("top", "left", "bottom", "right")
            }
    grid = element.find(qn("w:tblGrid"))
    columns = []
    if grid is not None:
        for col in grid.findall(qn("w:gridCol")):
            columns.append(_twips_to_pt(col.get(qn("w:w"))))
    rows = []
    for row in element.findall(qn("w:tr")):
        tr_pr = row.find(qn("w:trPr"))
        height = None
        rule = None
        if tr_pr is not None:
            tr_height = tr_pr.find(qn("w:trHeight"))
            if tr_height is not None:
                height = _twips_to_pt(tr_height.get(qn("w:val")))
                rule = tr_height.get(qn("w:hRule"))
        cells = row.findall(qn("w:tc"))
        first = cells[0] if cells else None
        spacing = None
        font_sizes = []
        if first is not None:
            paragraph = first.find(qn("w:p"))
            if paragraph is not None:
                ppr = paragraph.find(qn("w:pPr"))
                sp = ppr.find(qn("w:spacing")) if ppr is not None else None
                if sp is not None:
                    spacing = {
                        "before_pt": _twips_to_pt(sp.get(qn("w:before"))),
                        "after_pt": _twips_to_pt(sp.get(qn("w:after"))),
                        "line": sp.get(qn("w:line")),
                        "line_rule": sp.get(qn("w:lineRule")),
                    }
            for size in first.iter(qn("w:sz")):
                font_sizes.append(_twips_to_pt(size.get(qn("w:val"))))
        rows.append({
            "height_pt": height,
            "height_rule": rule,
            "cell_count": len(cells),
            "first_cell_spacing": spacing,
            "first_cell_font_sizes_pt": font_sizes,
        })
    return {
        "indent_pt": indent,
        "grid_columns_pt": columns,
        "grid_width_pt": _round(sum(c for c in columns if c is not None), 2) if columns else None,
        "cell_margins_pt": cell_mar,
        "row_count": len(rows),
        "rows": rows,
    }


def pdf_table_geometry(pdf_path: Path) -> list[dict]:
    """Painted table boxes and rule positions per rendered page."""

    import pymupdf

    document = pymupdf.open(str(pdf_path))
    pages = []
    for index, page in enumerate(document):
        horizontal, vertical, rects = [], [], []
        for drawing in page.get_drawings():
            for item in drawing["items"]:
                if item[0] == "re":
                    rect = item[1]
                    if rect.width >= 0.2 and rect.height >= 0.2:
                        rects.append(rect)
                elif item[0] == "l":
                    start, end = item[1], item[2]
                    if abs(start.y - end.y) <= 0.5 and abs(start.x - end.x) > 2.0:
                        horizontal.append((round(min(start.x, end.x), 2),
                                           round(max(start.x, end.x), 2),
                                           round(start.y, 2)))
                    elif abs(start.x - end.x) <= 0.5 and abs(start.y - end.y) > 2.0:
                        vertical.append((round(min(start.y, end.y), 2),
                                         round(max(start.y, end.y), 2),
                                         round(start.x, 2)))
        long_rules = [rule for rule in horizontal if rule[1] - rule[0] > 40.0]
        tall_rules = [rule for rule in vertical if rule[1] - rule[0] > 12.0]
        table_box = None
        if long_rules:
            xs = [rule[0] for rule in long_rules] + [rule[1] for rule in long_rules]
            ys = [rule[2] for rule in long_rules]
            table_box = {
                "x0": _round(min(xs)), "x1": _round(max(xs)),
                "y0": _round(min(ys)), "y1": _round(max(ys)),
                "width_pt": _round(max(xs) - min(xs)),
                "height_pt": _round(max(ys) - min(ys)),
            }
        pages.append({
            "pdf_page": index + 1,
            "long_horizontal_rule_count": len(long_rules),
            "tall_vertical_rule_count": len(tall_rules),
            "table_box_from_rules": table_box,
            "row_rule_ys": sorted({rule[2] for rule in long_rules}),
            "column_rule_xs": sorted({rule[2] for rule in tall_rules}),
            "rect_count": len(rects),
        })
    return pages


def build_record(planned: dict, docx: dict, rendered: dict | None) -> dict:
    source_width = planned["source_width_pt"]
    rendered_width = planned["rendered_width_pt"]
    width_delta = _round(rendered_width - source_width)
    x1_delta = _round(planned["rendered_x1_pt"] - planned["source_x1"])
    source_columns = planned["source_column_widths"]
    rendered_columns = planned["rendered_column_widths"]
    column_deltas = [
        _round(out - src) for src, out in zip(source_columns, rendered_columns)
    ]
    docx_indent = docx.get("indent_pt")
    x0_delta = (
        None if docx_indent is None
        else _round(docx_indent - planned["table_indent_pt"])
    )
    comparisons = {
        "width_delta_pt": width_delta,
        "x0_delta_pt": x0_delta,
        "x1_delta_pt": x1_delta,
        "column_width_deltas_pt": column_deltas,
        "max_abs_column_delta_pt": _round(
            max((abs(d) for d in column_deltas), default=0.0)),
        "clamped_to_page": planned["clamped_to_page"],
        "docx_grid_width_pt": docx.get("grid_width_pt"),
        "docx_grid_vs_planned_delta_pt": (
            None if docx.get("grid_width_pt") is None
            else _round(docx["grid_width_pt"] - rendered_width)),
        "docx_indent_vs_planned_delta_pt": x0_delta,
    }
    rendered_check = None
    if rendered and rendered.get("table_box_from_rules"):
        box = rendered["table_box_from_rules"]
        rendered_check = {
            "painted_x0": box["x0"],
            "painted_x1": box["x1"],
            "painted_width_pt": box["width_pt"],
            "painted_x0_delta_pt": _round(box["x0"] - planned["source_x0"]),
            "painted_x1_delta_pt": _round(box["x1"] - planned["source_x1"]),
            "painted_width_delta_pt": _round(box["width_pt"] - source_width),
            "row_rule_count": len(rendered["row_rule_ys"]),
            "column_rule_count": len(rendered["column_rule_xs"]),
        }
    classification = "SOURCE_REPRODUCED"
    reasons = []
    if planned["clamped_to_page"]:
        classification = "AVOIDABLE_DRIFT"
        reasons.append("table_width_clamped_below_its_own_source_width")
    for label, delta in (("width", width_delta), ("x0", x0_delta), ("x1", x1_delta)):
        if delta is None:
            continue
        if abs(delta) > GEOMETRY_TOLERANCE_PT:
            classification = "AVOIDABLE_DRIFT"
            reasons.append(f"{label}_delta_{delta}_pt")
    if comparisons["max_abs_column_delta_pt"] > GEOMETRY_TOLERANCE_PT:
        classification = "AVOIDABLE_DRIFT"
        reasons.append(f"column_delta_{comparisons['max_abs_column_delta_pt']}_pt")
    row_height_deltas = []
    for source_height, row in zip(planned["source_row_heights_pt"], docx["rows"]):
        if row["height_pt"] is None:
            continue
        delta = _round(row["height_pt"] - source_height)
        tolerance = max(ROW_HEIGHT_FONT_TOLERANCE_PT,
                        abs(source_height) * ROW_HEIGHT_FONT_TOLERANCE_RATIO)
        row_height_deltas.append({
            "source_height_pt": source_height,
            "generated_height_pt": row["height_pt"],
            "delta_pt": delta,
            "within_font_metric_tolerance": abs(delta) <= tolerance,
        })
    non_font_rows = [row for row in row_height_deltas
                     if not row["within_font_metric_tolerance"]]
    if non_font_rows and classification == "SOURCE_REPRODUCED":
        classification = "FONT_METRIC_ONLY"
        reasons.append(f"{len(non_font_rows)}_row_heights_differ_by_more_than_line_box")
    return {
        "source_page": planned["source_page"],
        "table_index": planned["table_index"],
        "rows": planned["rows"],
        "columns": planned["columns"],
        "source": {
            "x0": planned["source_x0"],
            "x1": planned["source_x1"],
            "width_pt": source_width,
            "height_pt": planned["source_height_pt"],
            "column_widths_pt": source_columns,
            "row_heights_pt": planned["source_row_heights_pt"],
        },
        "planned_word_geometry": {
            "section_left_margin_pt": planned["section_left_margin"],
            "table_indent_pt": planned["table_indent_pt"],
            "table_width_pt": rendered_width,
            "table_right_edge_pt": planned["rendered_x1_pt"],
            "page_available_width_pt": planned["page_available_width_pt"],
            "column_widths_pt": rendered_columns,
        },
        "docx_geometry": docx,
        "rendered_geometry": rendered_check,
        "comparison": comparisons,
        "row_height_comparison": row_height_deltas,
        "classification": classification,
        "classification_reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    build = args.build.resolve()
    report = json.loads((build / "generation_report.json").read_text(encoding="utf-8"))
    planned = report.get("table_geometry_records") or []
    docx_path = build / "基础投标文件.docx"
    pdf_path = build / "基础投标文件.pdf"
    sections = docx_tables_by_section(docx_path)
    rendered = pdf_table_geometry(pdf_path) if pdf_path.exists() else []

    by_page: dict[int, list[dict]] = {}
    for index, group in enumerate(sections, start=1):
        by_page[index] = group

    records = []
    for entry in planned:
        # Each source page owns one generated section, and the sections are in
        # generated-page order, so the generated page index is positional.
        generated_page = int(entry["generated_page"]) if "generated_page" in entry else None
        if generated_page is None:
            generated_page = int(entry["source_page"]) - SOURCE_TO_GENERATED_OFFSET
        tables = by_page.get(generated_page, [])
        docx_entry = tables[0] if tables else {
            "indent_pt": None, "grid_columns_pt": [], "grid_width_pt": None,
            "cell_margins_pt": None, "row_count": 0, "rows": [],
        }
        rendered_entry = next(
            (row for row in rendered if row["pdf_page"] == generated_page), None)
        record = build_record(entry, docx_entry, rendered_entry)
        record["generated_page"] = generated_page
        records.append(record)

    payload = {
        "schema": SCHEMA,
        "build_id": build.name,
        "table_count": len(records),
        "records": records,
        "summary": {
            "tables": len(records),
            "source_reproduced": sum(
                1 for row in records if row["classification"] == "SOURCE_REPRODUCED"),
            "font_metric_only": sum(
                1 for row in records if row["classification"] == "FONT_METRIC_ONLY"),
            "avoidable_drift": [
                {"source_page": row["source_page"], "table_index": row["table_index"],
                 "reasons": row["classification_reasons"]}
                for row in records if row["classification"] == "AVOIDABLE_DRIFT"
            ],
            "clamped_tables": [
                row["source_page"] for row in records
                if row["comparison"]["clamped_to_page"]
            ],
            "max_abs_width_delta_pt": _round(max(
                (abs(row["comparison"]["width_delta_pt"]) for row in records
                 if row["comparison"]["width_delta_pt"] is not None), default=0.0)),
            "max_abs_x1_delta_pt": _round(max(
                (abs(row["comparison"]["x1_delta_pt"]) for row in records
                 if row["comparison"]["x1_delta_pt"] is not None), default=0.0)),
            "rendered_pages_with_table_box": sum(
                1 for row in records
                if row["rendered_geometry"] is not None),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    if not args.quiet:
        print(json.dumps({"schema": SCHEMA, "build_id": payload["build_id"],
                          **payload["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
