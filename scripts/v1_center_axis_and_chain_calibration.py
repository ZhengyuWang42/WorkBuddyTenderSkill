"""Re-derive the effective Word centre axis and the multi-segment spacer model.

Two calibration questions remain open, and neither can be answered from the
document's own rows without circularity:

1. ``w:jc=center`` centres content on *some* axis inside the paragraph frame.
   The round-4 alignment frame assumed that axis is the raw frame centroid
   (70.80 + 524.40) / 2 = 297.60, and the cover then rendered a uniform
   ~2.8 pt left of the source.  A centred construct of *measured* width answers
   this directly: its rendered centre IS the effective axis, with no
   assumption about fonts or about what the frame "should" be.

2. The intrinsic spacer is one space + ``w:spacing``.  With one spacer the
   rendered gap came out ~0.4 pt under target; with two it came out ~1.6 pt
   over.  A per-run affine model cannot produce both signs, so the behaviour of
   *chains* has to be measured rather than inferred from a single isolated
   space.  Each chain's total width is measured here for 1, 2 and 3 spacers.

Both probes use the document's own section geometry (A4, 70.80 pt margins, so
the text frame is the one the date rows are laid out in).

Run:
    .venv\\Scripts\\python.exe -X utf8 scripts\\v1_center_axis_and_chain_calibration.py
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import docx
import pymupdf
from docx.oxml.ns import qn
from docx.shared import Pt

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from render_case57 import new_profile, soffice_argv  # noqa: E402

from tender_basic.intrinsic_spacer import (  # noqa: E402
    TWIPS_PER_PT,
    calibration_for,
)

OUT_DIR = REPO_ROOT / "acceptance" / "reports" / "v1_generalization"
AXIS_EVIDENCE = OUT_DIR / "case001_word_center_axis_calibration.json"
CHAIN_EVIDENCE = OUT_DIR / "case001_intrinsic_spacer_multisegment_calibration.json"

#: The section the case-001 date rows are laid out in, in points.
PAGE_W_PT, PAGE_H_PT = 595.3, 841.9
MARGIN_X_PT = 70.80
FONT, SIZE_PT = "仿宋", 10.5
#: The source centre offset the round-4 frame was built from, for comparison.
COVER_DELTA_PT = 11.51
COVER_ROW_CENTER_PT = 309.11
#: Tracking requested per chain, in twips: 20 twips = 1 pt of target width.
CHAIN_TRACKING_TWIPS = [200, 400, 600]


def build(path: Path, indent_pt: float) -> None:
    document = docx.Document()
    section = document.sections[0]
    section.page_width = Pt(PAGE_W_PT)
    section.page_height = Pt(PAGE_H_PT)
    section.left_margin = Pt(MARGIN_X_PT)
    section.right_margin = Pt(PAGE_W_PT - (PAGE_W_PT - MARGIN_X_PT))
    # A centred single glyph of measurable width: its rendered centre is the
    # axis Word actually centres on.
    centred = document.add_paragraph()
    centred.paragraph_format.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
    centred.paragraph_format.left_indent = Pt(indent_pt)
    run = centred.add_run("年")
    run.font.name = FONT
    run.font.size = Pt(SIZE_PT)

    # Chains of 1, 2 and 3 identical tracked spacers, flush left, so the total
    # rendered width of the chain is directly measurable.
    for twips, count in zip(CHAIN_TRACKING_TWIPS, (1, 2, 3)):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.LEFT
        head = paragraph.add_run("年")
        head.font.name = FONT
        head.font.size = Pt(SIZE_PT)
        for _ in range(count):
            spacer = paragraph.add_run(" ")
            spacer.font.name = FONT
            spacer.font.size = Pt(SIZE_PT)
            rpr = spacer._r.get_or_add_rPr()
            element = rpr.makeelement(qn("w:spacing"), {})
            element.set(qn("w:val"), str(int(twips)))
            rpr.append(element)
        tail = paragraph.add_run("月")
        tail.font.name = FONT
        tail.font.size = Pt(SIZE_PT)
    document.save(str(path))


def render(docx_path: Path, out_dir: Path) -> None:
    _profile, uri = new_profile(out_dir)
    command = soffice_argv(docx_path.resolve(), out_dir.resolve(), uri)
    completed = __import__("subprocess").run(
        command, shell=False, capture_output=True,
        creationflags=getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0),
    )
    print("libreoffice rc =", completed.returncode)


def label_boxes(pdf_path: Path) -> list[list[tuple[float, float]]]:
    """``[(x0, x1)]`` per rendered line, one entry per printed label."""

    pdf = pymupdf.open(str(pdf_path))
    found: list[tuple[float, list[tuple[float, float]]]] = []
    for page in pdf:
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                boxes = [
                    (float(c["bbox"][0]), float(c["bbox"][2]))
                    for span in line["spans"]
                    for c in span["chars"]
                    if c["c"] in "年月"
                ]
                if boxes:
                    found.append((float(line["bbox"][1]), sorted(boxes)))
    # Document order, not left-to-right: the centred probe glyph is the first
    # paragraph, and the chains follow it.  Sorting by x would put a
    # left-aligned chain line first and read its margin glyph as the axis.
    found.sort(key=lambda item: item[0])
    return [boxes for _, boxes in found]


def main() -> int:
    calibration = calibration_for(FONT)
    base = calibration.base_advance_pt(SIZE_PT)

    axis_rows = []
    for indent in (0.0, 2.0 * COVER_DELTA_PT):
        work = REPO_ROOT / "acceptance" / "workspace" / f"calib_axis_{uuid.uuid4().hex[:8]}"
        work.mkdir(parents=True, exist_ok=True)
        docx_path = work / "axis.docx"
        build(docx_path, indent)
        render(docx_path, work)
        lines = label_boxes(work / "axis.pdf")
        glyph = lines[0][0]
        centre = (glyph[0] + glyph[1]) / 2.0
        axis_rows.append(
            {
                "paragraph_left_indent_pt": indent,
                "rendered_glyph_x0": round(glyph[0], 3),
                "rendered_glyph_x1": round(glyph[1], 3),
                "rendered_center_pt": round(centre, 3),
            }
        )
        chains = []
        for index, twips in enumerate(CHAIN_TRACKING_TWIPS):
            row = lines[1 + index]
            if len(row) < 2:
                chains.append({"tracking_twips": twips, "measurable": False})
                continue
            total = row[-1][0] - row[0][1]
            chains.append(
                {
                    "tracking_twips": twips,
                    "spacer_count": index + 1,
                    "requested_chain_pt": round(
                        (index + 1) * (base + twips / TWIPS_PER_PT), 3
                    ),
                    "rendered_chain_pt": round(total, 3),
                    "residual_pt": round(
                        total - (index + 1) * (base + twips / TWIPS_PER_PT), 3
                    ),
                }
            )

    raw_frame_center = MARGIN_X_PT + (PAGE_W_PT - 2 * MARGIN_X_PT) / 2.0
    effective_axis = axis_rows[0]["rendered_center_pt"]
    shift = effective_axis - raw_frame_center
    induced = axis_rows[1]["rendered_center_pt"] - effective_axis

    axis_evidence = {
        "schema": "v1_word_center_axis_calibration/1",
        "probe_font": FONT,
        "probe_size_pt": SIZE_PT,
        "section": {
            "page_width_pt": PAGE_W_PT,
            "page_height_pt": PAGE_H_PT,
            "left_margin_pt": MARGIN_X_PT,
            "right_margin_pt": MARGIN_X_PT,
            "text_frame_x0_pt": MARGIN_X_PT,
            "text_frame_x1_pt": PAGE_W_PT - MARGIN_X_PT,
        },
        "raw_frame_center_pt": round(raw_frame_center, 3),
        "effective_word_center_axis_pt": round(effective_axis, 3),
        "effective_minus_raw_pt": round(shift, 3),
        "measurements": axis_rows,
        "inset_response_ratio": round(induced / (2.0 * COVER_DELTA_PT), 4)
        if COVER_DELTA_PT
        else None,
        "cover_comparison": {
            "cover_derived_delta_pt": COVER_DELTA_PT,
            "cover_source_row_center_pt": COVER_ROW_CENTER_PT,
            "round4_assumed_raw_frame_center_pt": round(raw_frame_center, 3),
            "round4_emitted_left_inset_pt": round(2.0 * COVER_DELTA_PT, 3),
            "uniform_residual_observed_pt": -2.8,
        },
        "disclosures": [
            "Rendered through LibreOffice, not Microsoft Word.",
            "One probe glyph measures the axis; the section geometry is the "
            "document's own.",
        ],
    }

    measurable = [row for row in chains if row.get("measurable", True)]
    per_segment = [
        row["residual_pt"] / row["spacer_count"] for row in measurable
    ]
    chain_evidence = {
        "schema": "v1_intrinsic_spacer_multisegment_calibration/1",
        "font": FONT,
        "size_pt": SIZE_PT,
        "centralized_base_advance_pt": round(base, 4),
        "tracking_response_ratio": calibration.tracking_response_ratio,
        "chains": chains,
        "residual_per_segment_pt": [round(v, 3) for v in per_segment],
        "finding": (
            "residual grows with spacer count, so the per-run affine model "
            "cannot hold as-is"
            if len(per_segment) > 1 and max(per_segment) - min(per_segment) > 0.5
            else "per-run affine model holds across chain lengths"
        ),
        "disclosures": [
            "Rendered through LibreOffice, not Microsoft Word.",
            "Chains are emitted through the same space + w:spacing representation "
            "the builder uses.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AXIS_EVIDENCE.write_text(
        json.dumps(axis_evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    CHAIN_EVIDENCE.write_text(
        json.dumps(chain_evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"raw frame center            = {raw_frame_center:.3f} pt")
    print(f"effective Word center axis  = {effective_axis:.3f} pt")
    print(f"effective - raw             = {shift:+.3f} pt")
    print(f"axis response to inset      = {axis_evidence['inset_response_ratio']}")
    for row in measurable:
        print(
            f"  chain n={row['spacer_count']} requested={row['requested_chain_pt']:8.3f} "
            f"rendered={row['rendered_chain_pt']:8.3f} residual={row['residual_pt']:+7.3f}"
        )
    print("residual per segment:", chain_evidence["residual_per_segment_pt"])
    print("wrote", AXIS_EVIDENCE.name, "and", CHAIN_EVIDENCE.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
