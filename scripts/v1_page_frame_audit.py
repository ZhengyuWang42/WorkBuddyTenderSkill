"""CASE001 page-frame diagnostic and per-page source-vs-generated audit.

Stage A proves *why* the generated Word sections carry different margins; the
same tool is the Stage G per-page visual review.  Everything it writes is
machine-readable, and every measured value is read back from real artifacts:

* the generated DOCX section properties (``w:pgSz`` / ``w:pgMar``),
* the rendered PDF (text geometry per generated page),
* the recorded ``section_geometry`` provenance of the build being audited,
* the source model rebuilt from the build's own ``normalized_document.json``.

Usage::

    .venv/Scripts/python.exe scripts/v1_page_frame_audit.py \
        --build acceptance/workspace/case_001/v1_phaseC_final2 \
        --out acceptance/reports/v1_generalization/case001_page_frame_audit_prefix.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.bid_document_builder import SOURCE_GLYPH_REPAIRS  # noqa: E402
from tender_basic.document_models import NormalizedDocument  # noqa: E402
from tender_basic.format_extractor import extract_bid_format  # noqa: E402
from tender_basic.page_layout import build_page_layout  # noqa: E402
from tender_basic.source_format import (  # noqa: E402
    apply_source_glyph_repairs,
    build_source_format_model,
)
from tender_basic.source_page_frame import (  # noqa: E402
    MIN_FRAME_MARGIN_PT,
    derive_source_section_page_frames,
    page_frame_evidence,
)
from tender_basic.source_page_geometry import (  # noqa: E402
    MAX_MARGIN_RATIO,
    section_geometry,
)

SCHEMA = "v1_case001_page_frame_audit/1"

#: A centred heading whose rendered centre differs from its source centre by more
#: than this is a page-frame defect, not a typographic rounding difference.
CENTER_ERROR_TOLERANCE_PT = 2.0

#: A source visual row count may differ from the rendered line count by this much
#: before it is reported as an unexpected wrap.
WRAP_TOLERANCE_ROWS = 0


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _round(value, digits: int = 2):
    return None if value is None else round(float(value), digits)


def load_source_model(build: Path):
    normalized = build / "normalized_document.json"
    document = NormalizedDocument.model_validate(
        json.loads(normalized.read_text(encoding="utf-8"))
    )
    model = build_source_format_model(document, extract_bid_format(document))
    model, _qa = apply_source_glyph_repairs(model, SOURCE_GLYPH_REPAIRS)
    return model


def docx_sections(docx_path: Path) -> list[dict]:
    from docx import Document

    document = Document(str(docx_path))
    out = []
    for index, section in enumerate(document.sections):
        width = float(section.page_width.pt)
        height = float(section.page_height.pt)
        out.append({
            "section_index": index,
            "page_width": _round(width),
            "page_height": _round(height),
            "orientation": "PORTRAIT" if height >= width else "LANDSCAPE",
            "start_type": str(section.start_type),
            "left_margin": _round(section.left_margin.pt),
            "right_margin": _round(section.right_margin.pt),
            "top_margin": _round(section.top_margin.pt),
            "bottom_margin": _round(section.bottom_margin.pt),
            "usable_text_width": _round(width - float(section.left_margin.pt)
                                        - float(section.right_margin.pt)),
        })
    return out


def _normalize_text(value: str) -> str:
    """Comparison form: no whitespace/figure space, no blank-fill characters."""

    text = (value or "")
    for char in ("\u2007", "\u00a0", "\u3000", "\t", "\r", "\n", " ", "_", "＿"):
        text = text.replace(char, "")
    return (text.replace("（", "(").replace("）", ")")
                .replace("，", ",").replace("。", ".").replace("：", ":"))


def measure_source_row_integrity(source_elements, generated_lines) -> dict:
    """Every source *one-row* element must stay on one rendered line.

    This is the structural form of the manual-review defect class: a source row
    that is one physical row in the source PDF - a form line, a signature row or
    a heading - must not need two rendered lines.  The check is anchored on the
    row's own leading and trailing source glyphs, so it never depends on a page
    number, a literal heading, a rule id or a resolved fact value.
    """

    checked = 0
    failures = []
    unmeasured = []
    for element in source_elements:
        if element["visual_rows"] != 1:
            continue
        target = _normalize_text(element["text"])
        if len(target) < 8:
            continue
        leading, trailing = target[:2], target[-4:]
        checked += 1
        if any(leading in _normalize_text(line["text"])
               and trailing in _normalize_text(line["text"])
               for line in generated_lines):
            continue
        leading_lines = [line for line in generated_lines
                         if leading in _normalize_text(line["text"])]
        trailing_lines = [line for line in generated_lines
                          if trailing in _normalize_text(line["text"])]
        if not leading_lines or not trailing_lines:
            # A source placeholder whose bracketed slot the build filled (a
            # resolved fact value replaces the placeholder text) is not evidence
            # of a wrap, so it is reported as unmeasured rather than as a split.
            unmeasured.append({
                "source_element_kind": element["kind"],
                "source_text": element["text"][:80],
                "leading_marker": leading,
                "leading_found": bool(leading_lines),
                "trailing_marker": trailing,
                "trailing_found": bool(trailing_lines),
                "reason": (
                    "TRACE_TEXT_REPLACED_OR_ABSENT"
                    if not leading_lines and not trailing_lines
                    else "TRACE_MARKER_REPLACED_OR_ABSENT"
                ),
            })
            continue
        failures.append({
            "source_element_kind": element["kind"],
            "source_text": element["text"][:80],
            "source_bbox": element["bbox"],
            "leading_marker": leading,
            "trailing_marker": trailing,
            "leading_line_y": leading_lines[0]["y0"],
            "trailing_line_y": trailing_lines[0]["y0"],
            "rows_needed": 2,
        })
    return {
        "checked_single_row_elements": checked,
        "split_single_row_elements": failures,
        "unmeasured_single_row_elements": unmeasured,
    }


def _source_element_rows(source_page, layout) -> list[dict]:
    from tender_basic.page_layout import FormBlock

    rows = []
    for element in layout.elements or ():
        if isinstance(element, FormBlock):
            for row in element.row_geometries:
                rows.append({
                    "kind": "FormRow",
                    "text": str(row.item.logical_text or ""),
                    "visual_rows": len({
                        round(float(line.bbox[1]), 1)
                        for line in (row.item.source_lines or ())}) or 1,
                    "bbox": [_round(v) for v in row.item.bbox],
                })
            continue
        text = str(getattr(element, "logical_text", "") or "")
        if not text:
            text = "".join(
                span.text
                for line in (getattr(element, "source_lines", None) or ())
                for span in getattr(line, "spans", [])
            )
        visual_rows = len({round(float(line.bbox[1]), 1)
                           for line in (getattr(element, "source_lines", None) or ())})
        rows.append({
            "kind": type(element).__name__,
            "text": text,
            "visual_rows": visual_rows,
            "bbox": [_round(v) for v in element.bbox],
        })
    return rows


def _group_rendered_rows(lines: list[dict], *, tolerance: float = 2.5) -> list[dict]:
    """Group extracted line objects into rendered visual rows.

    A renderer may draw one physical row as several line objects - a tab-advanced
    form line is exactly that - so the row, not the extraction object, is the unit
    a source row is compared against.
    """

    rows: list[dict] = []
    for line in sorted(lines, key=lambda item: (item["y0"], item["x0"])):
        if rows and abs(float(line["y0"]) - float(rows[-1]["y0"])) <= tolerance:
            row = rows[-1]
            row["segments"].append(line)
            row["y0"] = min(row["y0"], line["y0"])
            row["y1"] = max(row["y1"], line["y1"])
            row["x0"] = min(row["x0"], line["x0"])
            row["x1"] = max(row["x1"], line["x1"])
            continue
        rows.append({
            "x0": line["x0"], "y0": line["y0"], "x1": line["x1"], "y1": line["y1"],
            "segments": [line],
        })
    for row in rows:
        row["segments"].sort(key=lambda item: item["x0"])
        row["text"] = "".join(segment["text"] for segment in row["segments"])
        row["segment_count"] = len(row["segments"])
    return rows


def pdf_page_lines(pdf_path: Path) -> list[dict]:
    import pymupdf

    document = pymupdf.open(str(pdf_path))
    pages = []
    for index, page in enumerate(document):
        page_dict = page.get_text("dict")
        lines = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                lines.append({
                    "x0": _round(min(s["bbox"][0] for s in spans)),
                    "y0": _round(min(s["bbox"][1] for s in spans)),
                    "x1": _round(max(s["bbox"][2] for s in spans)),
                    "y1": _round(max(s["bbox"][3] for s in spans)),
                    "text": "".join(s["text"] for s in spans),
                })
        lines.sort(key=lambda row: (row["y0"], row["x0"]))
        rows = _group_rendered_rows(lines)
        pages.append({
            "pdf_page": index + 1,
            "line_count": len(lines),
            "visual_row_count": len(rows),
            "visible_x0": _round(min((l["x0"] for l in lines), default=None)),
            "visible_x1": _round(max((l["x1"] for l in lines), default=None)),
            "first_content_y": _round(min((l["y0"] for l in lines), default=None)),
            "last_content_y": _round(max((l["y1"] for l in lines), default=None)),
            "is_blank": not lines,
            "lines": lines,
            "rows": rows,
        })
    return pages


def _docx_paragraphs_by_section(docx_path: Path) -> list[dict]:
    """Body paragraphs grouped by the section they belong to, in document order."""

    from docx import Document
    from docx.oxml.ns import qn

    document = Document(str(docx_path))
    body = document.element.body
    groups: list[list[dict]] = [[]]
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            sect = child.find(qn("w:pPr") + "/" + qn("w:sectPr"))
            text = "".join(node.text or "" for node in child.iter(qn("w:t")))
            jc = child.find(qn("w:pPr") + "/" + qn("w:jc"))
            groups[-1].append({
                "text": text,
                "alignment": (jc.get(qn("w:val")) if jc is not None else None),
            })
            if sect is not None:
                groups.append([])
        elif child.tag == qn("w:tbl"):
            pass
    return groups


def _source_first_element(source_page, layout) -> dict:
    element = layout.elements[0] if layout.elements else None
    if element is None:
        return {"kind": None, "bbox": None, "centered": False, "visual_rows": 0,
                "text": ""}
    kind = type(element).__name__
    hint = str(getattr(element, "alignment_hint", "") or "")
    role = str(getattr(getattr(element, "alignment_role", ""), "value",
                       getattr(element, "alignment_role", "")) or "")
    rows = len({round(float(line.bbox[1]), 1)
                for line in (getattr(element, "source_lines", None) or ())})
    return {
        "kind": kind,
        "bbox": [_round(v) for v in element.bbox],
        "centered": hint == "center" or "CENTER" in role.upper(),
        "visual_rows": rows,
        "text": str(getattr(element, "logical_text", "") or "")[:80],
    }


def audit(build: Path, *, rebuild_frames: bool = True) -> dict:
    docx_path = build / "基础投标文件.docx"
    report_path = build / "generation_report.json"
    pdf_path = build / "基础投标文件.pdf"
    for path in (docx_path, report_path):
        if not path.exists():
            raise SystemExit(f"missing build artifact: {path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    model = load_source_model(build)
    source_pages = list(model.source_pages)
    layouts = [build_page_layout(page) for page in source_pages]
    frames = derive_source_section_page_frames(source_pages, layouts)
    recorded = {int(row["page"]): row for row in report.get("section_geometry") or []}

    sections = docx_sections(docx_path)
    rendered = pdf_page_lines(pdf_path) if pdf_path.exists() else []
    paragraphs_by_section = _docx_paragraphs_by_section(docx_path)

    pages = []
    extrema_driven = []
    for index, (page, layout) in enumerate(zip(source_pages, layouts)):
        frame = frames[page.page]
        evidence = page_frame_evidence(page, layout)
        section = sections[index] if index < len(sections) else None
        page_render = rendered[index] if index < len(rendered) else None
        provenance = recorded.get(page.page, {})
        first = _source_first_element(page, layout)

        # Does the *recorded* margin of this build come from this page's own
        # content x extrema?  Recompute the old derivation explicitly and
        # compare; that is the root-cause proof, not an inference.
        legacy = section_geometry(layout, page)
        clamp = round(float(page.width) * MAX_MARGIN_RATIO, 2)
        from_extrema = bool(
            provenance
            and abs(float(provenance.get("left_margin", -1)) - legacy.left_margin) <= 0.02
            and abs(float(provenance.get("right_margin", -1)) - legacy.right_margin) <= 0.02
        )
        if from_extrema:
            extrema_driven.append(page.page)

        generated_first_line = None
        if page_render and page_render["lines"]:
            generated_first_line = page_render["lines"][0]
        source_center = None
        if first["centered"] and first["bbox"]:
            source_center = (first["bbox"][0] + first["bbox"][2]) / 2.0
        generated_center = None
        if generated_first_line is not None:
            generated_center = (generated_first_line["x0"] + generated_first_line["x1"]) / 2.0
        center_error = None
        if source_center is not None and generated_center is not None:
            center_error = round(generated_center - source_center, 2)

        source_rows = first["visual_rows"] or 0
        integrity = measure_source_row_integrity(
            _source_element_rows(page, layout),
            page_render["rows"] if page_render else [],
        )
        splits = integrity["split_single_row_elements"]
        first_split = next(
            (row for row in splits
             if first and row["leading_marker"] in _normalize_text(first["text"])),
            None,
        )
        heading_wrapped = None
        if source_rows and first_split is not None:
            heading_wrapped = True

        pages.append({
            "generated_page": index + 1,
            "generated_section_index": index,
            "source_page": int(page.page),
            "frame_id": frame.frame_id,
            "section": section,
            "recorded_section_geometry": provenance,
            "frame_conformance": {
                "left_margin_delta": None if section is None else _round(
                    float(section["left_margin"]) - frame.left_margin),
                "right_margin_delta": None if section is None else _round(
                    float(section["right_margin"]) - frame.right_margin),
                "top_margin_delta": None if section is None else _round(
                    float(section["top_margin"]) - frame.top_body_frame),
                "conforms": None if section is None else bool(
                    abs(float(section["left_margin"]) - frame.left_margin) <= 0.02
                    and abs(float(section["right_margin"]) - frame.right_margin) <= 0.02
                ),
            },
            "source": {
                "page_width": evidence["page_width"],
                "page_height": evidence["page_height"],
                "visible_x0": evidence["visible_x0"],
                "visible_x1": evidence["visible_x1"],
                "first_content_y": evidence["first_content_y"],
                "element_count": evidence["element_count"],
                "widest_element_type": evidence["widest_element_type"],
                "sparse_title_only": evidence["title_only"],
                "spans_body_frame": evidence["spans_body_frame"],
                "first_element": first,
            },
            "generated": {
                "visible_x0": None if page_render is None else page_render["visible_x0"],
                "visible_x1": None if page_render is None else page_render["visible_x1"],
                "first_content_y": None if page_render is None else page_render["first_content_y"],
                "last_content_y": None if page_render is None else page_render["last_content_y"],
                "line_count": None if page_render is None else page_render["line_count"],
                "visual_row_count": (
                    None if page_render is None else page_render["visual_row_count"]),
                "is_blank": None if page_render is None else page_render["is_blank"],
            },
            "heading": {
                "source_center_x": _round(source_center),
                "generated_center_x": _round(generated_center),
                "center_error_pt": center_error,
                "center_error_within_tolerance": (
                    None if center_error is None
                    else abs(center_error) <= CENTER_ERROR_TOLERANCE_PT
                ),
                "source_visual_rows": source_rows,
                "source_one_line_heading_wrapped": heading_wrapped,
            },
            "source_row_integrity": integrity,
            "root_cause": {
                "legacy_per_page_margin": {
                    "left_margin": legacy.left_margin,
                    "right_margin": legacy.right_margin,
                    "top_margin": legacy.top_margin,
                    "body_x0": legacy.body_x0,
                    "body_x1": legacy.body_x1,
                },
                "legacy_margin_clamp_pt": clamp,
                "recorded_margin_reproduced_by_content_extrema": from_extrema,
                "margin_came_from_page_content_extrema": from_extrema,
                "expected_stable_frame": {
                    "frame_id": frame.frame_id,
                    "left_margin": frame.left_margin,
                    "right_margin": frame.right_margin,
                    "top_body_frame": frame.top_body_frame,
                },
            },
        })

    frame_rows = {}
    for page, frame in frames.items():
        frame_rows.setdefault(frame.frame_id, {"frame": frame.as_dict(), "pages": []})
        frame_rows[frame.frame_id]["pages"].append(int(page))

    margin_spreads = {}
    for frame_id, payload in frame_rows.items():
        frame_pages = [row for row in pages if row["frame_id"] == frame_id and row["section"]]
        margin_spreads[frame_id] = {
            "left_margin_spread_pt": _round(
                max(r["section"]["left_margin"] for r in frame_pages)
                - min(r["section"]["left_margin"] for r in frame_pages)),
            "right_margin_spread_pt": _round(
                max(r["section"]["right_margin"] for r in frame_pages)
                - min(r["section"]["right_margin"] for r in frame_pages)),
            "top_margin_spread_pt": _round(
                max(r["section"]["top_margin"] for r in frame_pages)
                - min(r["section"]["top_margin"] for r in frame_pages)),
            "page_count": len(frame_pages),
        }

    centered = [row for row in pages if row["heading"]["center_error_pt"] is not None]
    split_rows = [
        {"generated_page": row["generated_page"], **element}
        for row in pages
        for element in row["source_row_integrity"]["split_single_row_elements"]
    ]
    blanks = [row["generated_page"] for row in pages
              if row["generated"]["is_blank"] is True]

    payload = {
        "schema": SCHEMA,
        "build": {
            "build_id": build.name,
            "build_dir": str(build),
            "docx": str(docx_path),
            "docx_sha256": sha256(docx_path),
            "generation_report": str(report_path),
            "pdf": str(pdf_path) if pdf_path.exists() else None,
            "pdf_sha256": sha256(pdf_path) if pdf_path.exists() else None,
            "pdf_page_count": len(rendered),
            "source_page_count": len(source_pages),
            "section_count": len(sections),
        },
        "frame_derivation": {
            "frames": {fid: row["frame"] for fid, row in frame_rows.items()},
            "pages_by_frame": {fid: row["pages"] for fid, row in frame_rows.items()},
            "margin_spread": margin_spreads,
        },
        "root_cause": {
            "proven": bool(extrema_driven),
            "mechanism": (
                "section margins were derived per page from that page's own "
                "source content x extrema (min body x0 / max body x1, tables "
                "included) and clamped to MAX_MARGIN_RATIO of the page width"
            ),
            "clamp_ratio": MAX_MARGIN_RATIO,
            "clamp_value_pt": _round(float(source_pages[0].width) * MAX_MARGIN_RATIO)
            if source_pages else None,
            "pages_whose_recorded_margin_is_content_extrema_driven": extrema_driven,
            "pages_audited": len(pages),
            "consequence": (
                "a sparse title-only page acquires the clamp margin on both "
                "sides (its content is centred on the page, so the narrowed "
                "column shifts every centred heading left by half the margin "
                "difference) and a table wider than the body contracts the text "
                "column; headings the source keeps on one line then wrap"
            ),
        },
        "pages": pages,
        "summary": {
            "sections": len(sections),
            "generated_pages": len(rendered),
            "blank_pages": blanks,
            "pages_using_the_stable_frame": sum(
                1 for row in pages if row["frame_conformance"]["conforms"]),
            "centered_heading_pages": len(centered),
            "centered_heading_pages_outside_tolerance": [
                row["generated_page"] for row in centered
                if not row["heading"]["center_error_within_tolerance"]
            ],
            "max_center_error_pt": _round(
                max((abs(row["heading"]["center_error_pt"]) for row in centered), default=0.0)),
            "source_one_line_headings_wrapped": [
                row["generated_page"] for row in pages
                if row["heading"]["source_one_line_heading_wrapped"]],
            "single_row_elements_checked": sum(
                row["source_row_integrity"]["checked_single_row_elements"] for row in pages),
            "pages_with_a_split_source_row": sorted(
                {row["generated_page"] for row in pages
                 if row["source_row_integrity"]["split_single_row_elements"]}),
            "split_source_rows": split_rows,
            "unmeasured_source_rows": [
                {"generated_page": row["generated_page"], **element}
                for row in pages
                for element in row["source_row_integrity"]["unmeasured_single_row_elements"]
            ],
        },
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    payload = audit(args.build.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    if not args.quiet:
        print(json.dumps({
            "schema": payload["schema"],
            "build_id": payload["build"]["build_id"],
            "section_count": payload["build"]["section_count"],
            "pdf_page_count": payload["build"]["pdf_page_count"],
            "frame_derivation": payload["frame_derivation"]["margin_spread"],
            "root_cause_proven": payload["root_cause"]["proven"],
            "extrema_driven_pages": payload["root_cause"][
                "pages_whose_recorded_margin_is_content_extrema_driven"],
            "summary": payload["summary"],
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
