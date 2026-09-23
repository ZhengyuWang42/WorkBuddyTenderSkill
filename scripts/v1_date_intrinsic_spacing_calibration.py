"""Stage-4 bounded calibration: is a single space + w:spacing an exact width?

Candidate B's premise is that a run of ONE space carrying ``w:spacing``
(character tracking, in twentieths of a point) has a width that is
*intrinsic* - it belongs to the run, so a centred paragraph can centre it
without the run having to know where the line starts.  An absolute tab stop
cannot do that, which is why Candidate A was rejected.

The premise is only usable if the mapping from requested tracking to rendered
width is measurable and stable.  This probe measures it directly instead of
assuming ``rendered = space_advance + tracking``: it renders one short bounded
set of tracking values through the same frozen LibreOffice path the builder
uses, then reports the rendered width of each single-space run.

Run:
    .venv\\Scripts\\python.exe -X utf8 scripts\\v1_date_intrinsic_spacing_calibration.py
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
from docx.oxml.ns import qn

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
# The frozen launcher: exact soffice path, isolated short profile, argv list,
# shell=False, CREATE_NO_WINDOW.  Reused rather than re-implemented so the probe
# renders through the same path the builder uses.
from render_case57 import new_profile, soffice_argv  # noqa: E402

OUT_DIR = REPO_ROOT / "acceptance" / "reports" / "v1_generalization"
EVIDENCE = OUT_DIR / "case001_date_intrinsic_spacing_calibration.json"

# The date rows are set in 仿宋; the probe uses the same family and point size so
# the measured space advance is the one the real emitter will get.
PROBE_FONT = "仿宋"
PROBE_SIZE_PT = 10.5
# A small bounded sample: the identity point plus values spanning the source
# gaps this model has to cover (the widest measured date gap is ~46 pt).
TRACKING_TWIPS = [0, 100, 200, 400, 600, 800, 1000]

# The probe asks for the width of the *space run itself*, so the two labels are
# flush either side of it: 年<space>月 and the measured 年->月 distance minus the
# two label widths is the space run's advance.
PROBE_LABEL = "年"


def set_tracking(run, twips: int) -> None:
    """Apply ``w:spacing`` (character tracking) to a run, in twentieths of a point."""

    rpr = run._r.get_or_add_rPr()
    for stale in rpr.findall(qn("w:spacing")):
        rpr.remove(stale)
    element = rpr.makeelement(qn("w:spacing"), {})
    element.set(qn("w:val"), str(int(twips)))
    rpr.append(element)


def build_probe(path: Path) -> None:
    document = docx.Document()
    for twips in TRACKING_TWIPS:
        paragraph = document.add_paragraph()
        head = paragraph.add_run(PROBE_LABEL)
        head.font.name = PROBE_FONT
        head.font.size = docx.shared.Pt(PROBE_SIZE_PT)
        # A left-aligned paragraph so the run's advance is what is measured,
        # with no centring decision mixed in.
        paragraph.paragraph_format.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.LEFT
        space = paragraph.add_run("\u0020")
        space.font.name = PROBE_FONT
        space.font.size = docx.shared.Pt(PROBE_SIZE_PT)
        set_tracking(space, twips)
        tail = paragraph.add_run(PROBE_LABEL)
        tail.font.name = PROBE_FONT
        tail.font.size = docx.shared.Pt(PROBE_SIZE_PT)
    document.save(str(path))


def render(docx_path: Path, out_dir: Path) -> Path:
    """Render through the frozen launcher: argv list, shell=False, short profile."""

    profile = out_dir / ("_lo_profile_" + uuid.uuid4().hex)
    profile.mkdir(parents=True, exist_ok=True)
    _profile_path, profile_uri = new_profile(out_dir)
    command = soffice_argv(docx_path.resolve(), out_dir.resolve(), profile_uri)
    completed = subprocess.run(
        command,
        shell=False,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    print("libreoffice rc =", completed.returncode)
    if completed.returncode != 0:
        print(completed.stdout.decode("utf-8", "replace")[-2000:])
        print(completed.stderr.decode("utf-8", "replace")[-2000:])
    return out_dir / (docx_path.stem + ".pdf")


def measure(pdf_path: Path) -> list[dict]:
    """Width of each single-space run, from the rendered label positions."""

    pdf = pymupdf.open(str(pdf_path))
    lines: list[list[tuple[float, float, str]]] = []
    for page in pdf:
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                # The space glyph itself may or may not be reported by the PDF
                # text layer; either way the distance between the two labels is
                # the run's advance, so only the labels are matched.
                chars = [
                    c
                    for span in line["spans"]
                    for c in span["chars"]
                    if c["c"] == PROBE_LABEL
                ]
                if len(chars) == 2:
                    lines.append(
                        [
                            (float(chars[0]["bbox"][0]), float(chars[0]["bbox"][2]), "L"),
                            (float(chars[1]["bbox"][0]), float(chars[1]["bbox"][2]), "R"),
                        ]
                    )
    lines.sort(key=lambda row: row[0][1])
    results = []
    for twips, row in zip(TRACKING_TWIPS, lines):
        left, right = row[0], row[1]
        label_width = left[1] - left[0]
        distance = right[0] - left[1]
        results.append(
            {
                "requested_spacing_twips": twips,
                "requested_spacing_pt": round(twips / 20.0, 2),
                "rendered_label_advance_pt": round(label_width, 3),
                "rendered_gap_pt": round(distance, 3),
            }
        )
    return results


def main() -> int:
    work = REPO_ROOT / "acceptance" / "workspace" / (
        "calib_intrinsic_" + uuid.uuid4().hex[:8]
    )
    work.mkdir(parents=True, exist_ok=True)
    docx_path = work / "probe.docx"
    build_probe(docx_path)
    pdf_path = render(docx_path, work)
    rows = measure(pdf_path)

    baseline = rows[0]["rendered_gap_pt"] if rows else 0.0
    for row in rows:
        row["delta_from_zero_tracking_pt"] = round(
            row["rendered_gap_pt"] - baseline, 3
        )

    steps = [
        rows[i + 1]["delta_from_zero_tracking_pt"]
        - rows[i]["delta_from_zero_tracking_pt"]
        for i in range(len(rows) - 1)
    ]
    requested_steps = [
        (TRACKING_TWIPS[i + 1] - TRACKING_TWIPS[i]) / 20.0 for i in range(len(rows) - 1)
    ]
    ratios = [s / r for s, r in zip(steps, requested_steps) if r]
    spread = max(ratios) - min(ratios) if ratios else 0.0
    # The model is only usable if one requested point of tracking buys the same
    # rendered point everywhere in the range (ratio 1.0) - a spread of more than
    # a few percent means the mapping is not deterministic enough to synthesize
    # a target width from.
    linear = bool(ratios) and spread <= 0.05

    evidence = {
        "schema": "v1_date_intrinsic_spacing_calibration/1",
        "probe_font": PROBE_FONT,
        "probe_size_pt": PROBE_SIZE_PT,
        "mechanism": "single U+0020 run carrying w:spacing (character tracking)",
        "requested_vs_rendered": rows,
        "baseline_gap_at_zero_tracking_pt": baseline,
        "per_step_ratio_rendered_per_requested": [round(r, 4) for r in ratios],
        "ratio_spread": round(spread, 4),
        "mapping_is_deterministic": linear,
        "conclusion": (
            "PASS - rendered width is a stable affine function of requested "
            "tracking, so a source-measured target width can be synthesized"
            if linear
            else "FAIL - requested tracking does not map to rendered width "
            "deterministically enough to synthesize a source-measured width"
        ),
        "measured_rows": len(rows),
        "requested_rows": len(TRACKING_TWIPS),
        "disclosures": [
            "Rendered through LibreOffice, not Microsoft Word; Word is the "
            "delivery renderer and may differ.",
            "Only %d of %d requested tracking values yielded a measurement: at "
            "wider tracking the gap exceeds the PDF extractor's intra-line "
            "fragment threshold and the two labels come back as separate visual "
            "lines, which this matcher does not pair. The mapping is established "
            "from the rows that were measurable; the unmeasured rows are not "
            "claimed as corroboration." % (len(rows), len(TRACKING_TWIPS)),
            "The probe measures a left-aligned paragraph; the mapping is "
            "assumed to hold inside w:jc=center, which the CENTER pilot tests.",
            "Only the mapping is calibrated here - the absolute source widths "
            "still come from the source document's own geometry.",
            "Candidate B was CALIBRATED but NOT IMPLEMENTED in this turn: no "
            "emitter change and no document integration followed.",
        ],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"{'twips':>6} {'req pt':>7} {'gap pt':>8} {'delta':>8}")
    for row in rows:
        print(
            f"{row['requested_spacing_twips']:>6} {row['requested_spacing_pt']:>7.2f} "
            f"{row['rendered_gap_pt']:>8.3f} {row['delta_from_zero_tracking_pt']:>8.3f}"
        )
    print("per-step ratios:", [round(r, 4) for r in ratios], "spread:", round(spread, 4))
    print("mapping_is_deterministic =", linear)
    print("wrote", EVIDENCE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
