#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Measure the intrinsic spacer by *chains*, with marker brackets and a control.

The spacer model is ``rendered = base_space_advance + tracking``.  Fitting it
from the document's own date rows cannot work: every row mixes a base advance
with a tracking value, and two rows with different segment counts then give two
equations in the same two unknowns only if the segment count is known exactly -
which is the thing under test.  The previous fit did exactly that and produced
``5.618 / 10.5`` (0.535 em), which then rendered each segment 0.42 pt wide and
made a four-segment row accumulate 1.67 pt of token drift.

This probe measures the model directly:

* Every measured row is bracketed by two unique text markers, ``A<nn>`` and
  ``B<nn>``, and the chain is ``B.x0 - A.x1``.
* The markers are located by *character*, not by PDF text fragment, so a row the
  extractor splits into several fragments measures exactly like one it returns
  whole.  This is what defeated the earlier chain probe.
* A zero-spacer control row ``A00 -> B00`` is measured in every size group, and
  each chain is reported as ``chain(n) - chain(control)``.  The markers' own
  advances and the glyph bearings behind them therefore cancel exactly instead
  of being folded into the answer.

The same ``tender_basic.intrinsic_spacer`` calibration the builder emits from is
used to *predict* each chain, and ``apply_spacing`` writes the ``w:spacing`` so
the probe's runs are byte-identical to the document's.  That keeps the probe a
validation of production rather than a parallel implementation:

* 1, 2 and 3 segment chains of production-tuned targets;
* one mixed-width chain;
* one sub-base target, to test whether a width below the space advance is
  reachable at all;
* a pair of rows differing only by ``w:spacing = -4`` versus ``0``, which tests
  whether the renderer applies condensed tracking;
* a zero-tracking row per size, which measures the base advance directly;
* a 200-twip row, which measures the tracking response ratio directly.

Run:
    .venv\\Scripts\\python.exe -X utf8 scripts\\v1_intrinsic_spacer_multisegment_probe.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import docx
import pymupdf
from docx.shared import Pt

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from render_case57 import new_profile, soffice_argv  # noqa: E402

from tender_basic.intrinsic_spacer import (  # noqa: E402
    apply_spacing,
    calibration_for,
    intrinsic_spacer_widths,
)

OUT_DIR = REPO_ROOT / "acceptance" / "reports" / "v1_generalization"
EVIDENCE = OUT_DIR / "case001_intrinsic_spacer_multisegment_calibration_v2.json"

FONT = "仿宋"
PAGE_W_PT, PAGE_H_PT = 595.3, 841.9
MARGIN_X_PT = 70.80
#: Chain residual tolerance demanded by the calibration task.
CHAIN_TOLERANCE_PT = 0.5
#: Targets taken from the delivered date rows, so the probe measures the widths
#: production actually asks for rather than round numbers.
PROBE_TARGETS = (12.00, 21.96, 45.98, 40.30, 69.00)
#: Below one space at 12 pt (6.00 pt): is it reachable?
SUB_BASE_TARGET_PT = 5.79
#: Tracking used for the response-ratio row: 200 twips = 10.00 pt.
RESPONSE_TWIPS = 200
#: Tracking used for the condensed-spacing experiment.
NEGATIVE_TWIPS = -4


def spec_rows():
    """``(key, size_pt, label, [(kind, value)])`` for every probe row."""

    return [
        # group 12.0 pt - the delivered date rows' dominant size
        (0, 12.0, "control (no spacer)", []),
        (1, 12.0, "1 segment, production target 21.96", [("target", 21.96)]),
        (2, 12.0, "2 segments, 12.00 + 21.96",
         [("target", 12.00), ("target", 21.96)]),
        (3, 12.0, "3 segments, 12.00 + 21.96 + 45.98",
         [("target", 12.00), ("target", 21.96), ("target", 45.98)]),
        (4, 12.0, "mixed 28.90 + 5.79 (one below the floor)",
         [("target", 28.90), ("target", SUB_BASE_TARGET_PT)]),
        (6, 12.0, "base advance (w:spacing = 0)", [("twips", 0)]),
        (7, 12.0, "tracking response (w:spacing = 200 twips)", [("twips", RESPONSE_TWIPS)]),
        # pair differing only in the sign of the tracking
        (5, 12.0, "condensed tracking (w:spacing = -4 twips)",
         [("twips", NEGATIVE_TWIPS)]),
        (8, 12.0, "zero tracking, raw (control for the condensed pair)", [("twips", 0)]),
        # group 11.5 pt - the cover date row's size
        (10, 11.5, "control (no spacer)", []),
        (11, 11.5, "1 segment, cover target 40.30", [("target", 40.30)]),
        (12, 11.5, "2 segments, 40.30 + 45.96",
         [("target", 40.30), ("target", 45.96)]),
        (13, 11.5, "3 segments, 40.30 + 45.96 + 69.00",
         [("target", 40.30), ("target", 45.96), ("target", 69.00)]),
        (16, 11.5, "base advance (w:spacing = 0)", [("twips", 0)]),
    ]


def marker(key: int, side: str) -> str:
    return "%s%02d" % (side, key)


def build(path: Path, rows) -> None:
    document = docx.Document()
    section = document.sections[0]
    section.page_width = Pt(PAGE_W_PT)
    section.page_height = Pt(PAGE_H_PT)
    section.left_margin = Pt(MARGIN_X_PT)
    section.right_margin = Pt(PAGE_W_PT - (PAGE_W_PT - MARGIN_X_PT))

    for key, size, _label, spacers in rows:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        head = paragraph.add_run(marker(key, "A"))
        head.font.name = FONT
        head.font.size = Pt(size)
        for kind, value in spacers:
            spacer = paragraph.add_run(" ")
            spacer.font.name = FONT
            spacer.font.size = Pt(size)
            if kind == "target":
                twips, _rendered = intrinsic_spacer_widths(value, FONT, size)
            else:
                twips = int(value)
            apply_spacing(spacer, twips)
        tail = paragraph.add_run(marker(key, "B"))
        tail.font.name = FONT
        tail.font.size = Pt(size)
    document.save(str(path))


def render(docx_path: Path, out_dir: Path) -> int:
    _profile, uri = new_profile(out_dir)
    command = soffice_argv(docx_path.resolve(), out_dir.resolve(), uri)
    completed = subprocess.run(
        command,
        shell=False,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    print("libreoffice rc =", completed.returncode)
    return completed.returncode


def page_chars(page):
    """Every character on the page, in reading order, spaces included."""

    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for char in span["chars"]:
                    chars.append(
                        {
                            "c": char["c"],
                            "bbox": [float(v) for v in char["bbox"]],
                            "size": float(span.get("size", 0.0)),
                            "font": span.get("font", ""),
                        }
                    )
    return chars


def group_rows(chars, tolerance=2.5):
    if not chars:
        return []
    ordered = sorted(chars, key=lambda c: (round(c["bbox"][1], 2), c["bbox"][0]))
    rows = []
    current = [ordered[0]]
    for char in ordered[1:]:
        if abs(char["bbox"][1] - current[0]["bbox"][1]) <= tolerance:
            current.append(char)
        else:
            rows.append(current)
            current = [char]
    rows.append(current)
    return rows


def measure_chains(pdf_path: Path, keys):
    """``{key: chain_pt}`` from ``B.x0 - A.x1``, located per character."""

    pdf = pymupdf.open(str(pdf_path))
    found = {}
    fonts = set()
    for page in pdf:
        for row in group_rows(page_chars(page)):
            ordered = sorted(row, key=lambda c: c["bbox"][0])
            text = "".join(c["c"] for c in ordered)
            for key in keys:
                left = marker(key, "A")
                right = marker(key, "B")
                i = text.find(left)
                j = text.find(right)
                if i < 0 or j < 0 or j <= i:
                    continue
                left_chars = ordered[i : i + len(left)]
                right_chars = ordered[j : j + len(right)]
                if len(left_chars) != len(left) or len(right_chars) != len(right):
                    continue
                for char in right_chars:
                    if char["font"]:
                        fonts.add(char["font"])
                found[key] = {
                    "marker_left": left,
                    "marker_right": right,
                    "row_text": text,
                    "left_marker_x1_pt": round(left_chars[-1]["bbox"][2], 3),
                    "right_marker_x0_pt": round(right_chars[0]["bbox"][0], 3),
                    "chain_pt": round(
                        right_chars[0]["bbox"][0] - left_chars[-1]["bbox"][2], 3
                    ),
                    "row_fragment_count": len(
                        [line for line in [text]]
                    ),
                    "font_used": right_chars[0]["font"],
                }
    pdf.close()
    return found, sorted(fonts)


def main() -> int:
    rows = spec_rows()
    keys = [row[0] for row in rows]
    work = REPO_ROOT / "acceptance" / "workspace" / (
        "intrinsic_spacer_probe_%s" % uuid.uuid4().hex[:8]
    )
    work.mkdir(parents=True, exist_ok=True)
    docx_path = work / "probe.docx"
    build(docx_path, rows)
    render(docx_path, work)
    pdf_path = work / "probe.pdf"
    measured, fonts = measure_chains(pdf_path, keys)
    print("probe rendered with fonts:", fonts)

    calibration = calibration_for(FONT)
    groups = {12.0: (0, 6), 11.5: (10, 16)}
    records = []
    failures = []
    for key, size, label, spacers in rows:
        control_key = groups[size][0] if size in groups else None
        measured_row = measured.get(key)
        control = measured.get(control_key) if control_key is not None else None
        predicted = 0.0
        detail = []
        for kind, value in spacers:
            if kind == "target":
                twips, rendered = intrinsic_spacer_widths(value, FONT, size)
                representable = calibration.representable(value, size)
                detail.append(
                    {
                        "kind": "target",
                        "target_width_pt": value,
                        "w_spacing_twips": twips,
                        "predicted_rendered_pt": round(rendered, 3),
                        "representable": representable,
                    }
                )
            else:
                rendered = calibration.base_advance_pt(size) + int(value) / 20.0
                detail.append(
                    {
                        "kind": "raw_twips",
                        "w_spacing_twips": int(value),
                        "predicted_rendered_pt": round(rendered, 3),
                        "representable": int(value) >= 0,
                    }
                )
            predicted += rendered
        chain_spacers = None
        residual = None
        if measured_row is not None and control is not None:
            chain_spacers = round(measured_row["chain_pt"] - control["chain_pt"], 3)
            residual = round(chain_spacers - predicted, 3)
        records.append(
            {
                "probe_key": key,
                "label": label,
                "font_size_pt": size,
                "font_family": FONT,
                "control_probe_key": control_key,
                "segments": detail,
                "segment_count": len(spacers),
                "predicted_chain_width_pt": round(predicted, 3),
                "measured_chain_pt": measured_row["chain_pt"] if measured_row else None,
                "measured_control_chain_pt": control["chain_pt"] if control else None,
                "rendered_chain_width_pt": chain_spacers,
                "residual_pt": residual,
                "residual_per_segment_pt": (
                    round(residual / len(spacers), 3)
                    if residual is not None and spacers
                    else None
                ),
                "pairing_evidence": measured_row,
            }
        )
        if spacers and residual is not None and abs(residual) > CHAIN_TOLERANCE_PT:
            failures.append(
                "probe %d (%s): chain residual %.3f pt exceeds %.1f pt"
                % (key, label, residual, CHAIN_TOLERANCE_PT)
            )

    def chain(key):
        row = measured.get(key)
        return row["chain_pt"] if row else None

    def spacers_of(key):
        control = groups[12.0][0] if key < 10 else groups[11.5][0]
        if chain(key) is None or chain(control) is None:
            return None
        return round(chain(key) - chain(control), 3)

    base_12 = spacers_of(6)
    base_11_5 = spacers_of(16)
    response = spacers_of(7)
    condensed = spacers_of(5)
    raw_zero = spacers_of(8)
    derived = {
        "base_advance_pt_at_12": base_12,
        "base_advance_pt_at_11_5": base_11_5,
        "base_space_advance_em_from_12": (
            round(base_12 / 12.0, 4) if base_12 is not None else None
        ),
        "base_space_advance_em_from_11_5": (
            round(base_11_5 / 11.5, 4) if base_11_5 is not None else None
        ),
        "stored_space_advance_em": calibration.space_advance_em,
        "tracking_response_ratio_measured": (
            round((response - base_12) / (RESPONSE_TWIPS / 20.0), 4)
            if response is not None and base_12 is not None
            else None
        ),
        "stored_tracking_response_ratio": calibration.tracking_response_ratio,
        "condensed_tracking_row_width_pt": condensed,
        "zero_tracking_row_width_pt": raw_zero,
        "condensed_tracking_applied": (
            None
            if condensed is None or raw_zero is None
            else bool(raw_zero - condensed > 0.05)
        ),
        "condensed_amount_measured_pt": (
            round(raw_zero - condensed, 3)
            if condensed is not None and raw_zero is not None
            else None
        ),
        "condensed_amount_requested_pt": round(abs(NEGATIVE_TWIPS) / 20.0, 3),
    }
    if derived["base_space_advance_em_from_12"] is not None:
        if abs(derived["base_space_advance_em_from_12"] - 0.5) > 0.005:
            failures.append(
                "measured base advance at 12 pt is %.4f em, not the stored %.4f"
                % (derived["base_space_advance_em_from_12"], 0.5)
            )
    if derived["base_space_advance_em_from_11_5"] is not None:
        if abs(derived["base_space_advance_em_from_11_5"] - 0.5) > 0.005:
            failures.append(
                "measured base advance at 11.5 pt is %.4f em, not the stored %.4f"
                % (derived["base_space_advance_em_from_11_5"], 0.5)
            )
    if derived["tracking_response_ratio_measured"] is not None:
        if abs(derived["tracking_response_ratio_measured"] - 1.0) > 0.02:
            failures.append(
                "measured tracking response is %.4f, not the stored %.4f"
                % (derived["tracking_response_ratio_measured"], 1.0)
            )

    status = "PASS" if not failures else "FAIL"
    report = {
        "schema": "case001_intrinsic_spacer_multisegment_calibration/2",
        "generated_by": "scripts/v1_intrinsic_spacer_multisegment_probe.py",
        "status": status,
        "chain_tolerance_pt": CHAIN_TOLERANCE_PT,
        "matcher_strategy": (
            "marker-bracketed rows, located per *character* rather than per PDF "
            "text fragment: the page's characters are grouped into rows by y, "
            "sorted by x, joined into a string, and each unique marker "
            "'A<nn>'/'B<nn>' is found inside that string so its own characters "
            "supply the left edge (last char x1) and the right edge (first char "
            "x0). A row the extractor fragments therefore measures exactly like "
            "one it returns whole. Each chain is reported against a zero-spacer "
            "control row in the same size group, so the markers' advances cancel."
        ),
        "probe_document": str(docx_path).replace("\\", "/"),
        "probe_pdf": str(pdf_path).replace("\\", "/"),
        "fonts_seen_in_render": fonts,
        "rows": records,
        "derived_constants": derived,
        "failures": failures,
        "disclosures": [
            "The probe renders through the same frozen LibreOffice launcher the "
            "build uses (scripts/render_case57.py), into a scratch workspace "
            "directory; no production artefact is touched.",
            "Predictions come from tender_basic/intrinsic_spacer.py, the same "
            "calibration the builder emits from, and w:spacing is written by the "
            "same apply_spacing helper, so a probe row is byte-identical to a "
            "document spacer run.",
            "The control row subtraction removes the markers' own advances; a "
            "residual is therefore a property of the spacer runs, not of the "
            "brackets.",
            "The condensed-tracking pair (probe 5 vs probe 8) requests -4 twips "
            "and 0 twips. It is a renderer-behaviour measurement only: the "
            "production calibration never emits a negative w:spacing.",
        ],
    }

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print()
    print("%-4s %-6s %-52s %10s %10s %9s" % ("key", "size", "label", "predicted", "rendered", "residual"))
    for record in records:
        print(
            "%-4s %-6s %-52s %10s %10s %9s"
            % (
                record["probe_key"],
                record["font_size_pt"],
                record["label"][:52],
                record["predicted_chain_width_pt"],
                record["rendered_chain_width_pt"],
                record["residual_pt"],
            )
        )
    print()
    for name, value in derived.items():
        print("  %-40s = %s" % (name, value))
    print()
    print("status:", status)
    for failure in failures:
        print("  FAIL:", failure)
    print("wrote:", EVIDENCE)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
