#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Persist the *emitted* date-row construction chain of one build.

READ-ONLY over the build; writes only the two artefacts named by ``--out-json``
/ ``--out-md``.

Why this exists
---------------
The date rows are reproduced as a sequence of runs whose widths are stated
individually, so "is the row right?" is not answerable from the row's *text*:
``年`` + one space + ``月`` says nothing about the space's width.  This ledger
opens the delivered ``.docx`` and records, for every build-scope date row, the
ordered runs the build actually emitted - their codepoints, fonts, size,
underline state, ``w:spacing`` and tab state - and classifies each one:

``TOKEN``
    one of the row's printed date labels.
``INTRINSIC_SPACER``
    one ``U+0020`` whose rendered width is stated in ``w:spacing``.
``LEGACY_FIGURE_SPACE``
    a run of ``U+2007`` used to *count* a width.  The count is quantised by the
    glyph's advance, so this is not a geometry authority; it is recorded
    because it is the mechanism the intrinsic representation replaced.
``TAB``
    a ``w:tab`` used to position a span absolutely.
``OTHER``
    anything else (label text, an untracked space).

Each row is then decomposed into the three source intervals that carry geometry
- the leading interval before the first token, year→month, and month→day - with
the source's own measured width for each and the mechanism the row emits for it.
That pairing is what makes a construct-width error locatable: an interval whose
emitted mechanism is a figure-space count cannot be reproducing the source's
measured width, and an interval with no emitted mechanism has lost its width
outright.

Source geometry comes from ``scripts/v1_date_row_round4_diagnostic.py`` (the
frozen read-only audit) rather than from a second parser, so the two artefacts
cannot disagree about what the source drew.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_PATH.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PATH.parent))

import v1_date_row_round4_diagnostic as diagnostic  # noqa: E402

from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from tender_basic.intrinsic_spacer import (  # noqa: E402
    calibration_for,
    intrinsic_spacer_widths,
)

DATE_TOKENS = diagnostic.DATE_TOKENS
TAB = diagnostic.TAB
FIGURE_SPACE = "\u2007"
NATURAL_SPACE = "\u0020"

TOKEN = "TOKEN"
INTRINSIC_SPACER = "INTRINSIC_SPACER"
LEGACY_FIGURE_SPACE = "LEGACY_FIGURE_SPACE"
TAB_MECHANISM = "TAB"
OTHER = "OTHER"


def r2(value):
    if value is None:
        return None
    return round(float(value) + 0.0, 2)


def r3(value):
    if value is None:
        return None
    return round(float(value) + 0.0, 3)


def _attr(element, name):
    if element is None:
        return None
    value = element.get(qn("w:" + name))
    return int(value) if value is not None else None


def paragraph_chain(paragraph):
    """The paragraph's paragraph-properties plus its ordered run chain."""

    p_pr = paragraph._p.find(qn("w:pPr"))
    jc = None
    indents = {}
    tabs = []
    if p_pr is not None:
        jc_el = p_pr.find(qn("w:jc"))
        if jc_el is not None:
            jc = jc_el.get(qn("w:val"))
        ind_el = p_pr.find(qn("w:ind"))
        for name in ("left", "right", "firstLine", "hanging"):
            raw = _attr(ind_el, name)
            indents[name] = raw
        tabs_el = p_pr.find(qn("w:tabs"))
        if tabs_el is not None:
            for tab in tabs_el.findall(qn("w:tab")):
                pos = tab.get(qn("w:pos"))
                tabs.append(
                    {
                        "pos_twips": int(pos) if pos is not None else None,
                        "val": tab.get(qn("w:val")),
                        "leader": tab.get(qn("w:leader")),
                    }
                )

    runs = []
    for index, run in enumerate(paragraph.runs):
        r_pr = run._r.find(qn("w:rPr"))
        spacing = None
        size_half_points = None
        fonts = {}
        tab_char = None
        if r_pr is not None:
            spacing_el = r_pr.find(qn("w:spacing"))
            if spacing_el is not None:
                spacing = spacing_el.get(qn("w:val"))
            size_el = r_pr.find(qn("w:sz"))
            if size_el is not None:
                size_half_points = int(size_el.get(qn("w:val")))
            fonts_el = r_pr.find(qn("w:rFonts"))
            if fonts_el is not None:
                for key, value in fonts_el.attrib.items():
                    fonts[key.split("}")[-1]] = value
            if r_pr.find(qn("w:tab")) is not None:
                tab_char = True
        text = run.text
        size_pt = (size_half_points / 2.0) if size_half_points else None
        runs.append(
            {
                "run_index": index,
                "text": text,
                "text_repr": repr(text),
                "length": len(text),
                "codepoints": [hex(ord(ch)) for ch in text],
                "font_family": fonts.get("ascii") or fonts.get("hAnsi"),
                "east_asian_font": fonts.get("eastAsia"),
                "font_size_pt": size_pt,
                "underline": run.underline,
                "w_spacing_twips": int(spacing) if spacing is not None else None,
                "w_spacing_pt": (int(spacing) / 20.0) if spacing is not None else None,
                "tab_state": "TAB_CHAR" if (tab_char or text == TAB) else None,
                "class": classify_run(text, spacing),
            }
        )
    return {"jc": jc, "indents": indents, "tabs": tabs}, runs


def classify_run(text: str, spacing) -> str:
    if text == "":
        return OTHER
    if text in DATE_TOKENS:
        return TOKEN
    if all(ch in (FIGURE_SPACE, TAB, NATURAL_SPACE) for ch in text):
        if FIGURE_SPACE in text:
            return LEGACY_FIGURE_SPACE
        if text == TAB or TAB in text:
            return TAB_MECHANISM
        if text == NATURAL_SPACE and spacing is not None:
            return INTRINSIC_SPACER
    return OTHER


def run_model_width(run, fallback_size_pt):
    """The width this run is modelled to render, in points.

    Only meaningful for the spacer classes; a token's own advance is not what
    this ledger is auditing and is reported as ``None``.
    """

    cls = run["class"]
    size = run["font_size_pt"] or fallback_size_pt
    if cls == INTRINSIC_SPACER:
        twips = run["w_spacing_twips"]
        return calibration_for(run["font_family"]).base_advance_pt(size) + (
            twips / 20.0
        )
    if cls == LEGACY_FIGURE_SPACE:
        return run["length"] * calibration_for(run["font_family"]).base_advance_pt(size)
    return None


def interval_mechanisms(runs):
    """Slice the run chain into (leading, year→month, month→day) mechanisms.

    The token runs are the boundaries.  Everything between two adjacent tokens is
    the mechanism of that interval; everything before the first token is the
    leading interval's mechanism.
    """

    token_positions = [
        index for index, run in enumerate(runs) if run["class"] == TOKEN
    ]
    result = {"leading": [], "year_month": [], "month_day": []}
    if not token_positions:
        return result
    result["leading"] = runs[: token_positions[0]]
    if len(token_positions) >= 2:
        result["year_month"] = runs[token_positions[0] + 1 : token_positions[1]]
    if len(token_positions) >= 3:
        result["month_day"] = runs[token_positions[1] + 1 : token_positions[2]]
    return result


def describe_mechanism(runs, fallback_size_pt):
    """A compact, mechanical description of one interval's emitted runs."""

    described = []
    total = 0.0
    unknown = False
    for run in runs:
        width = run_model_width(run, fallback_size_pt)
        described.append(
            {
                "run_index": run["run_index"],
                "class": run["class"],
                "length": run["length"],
                "underline": run["underline"],
                "w_spacing_twips": run["w_spacing_twips"],
                "modelled_width_pt": r3(width),
            }
        )
        if width is not None:
            total += width
        else:
            unknown = True
    classes = sorted({entry["class"] for entry in described})
    return {
        "runs": described,
        "classes": classes,
        "emitted_modelled_width_pt": r3(total) if described else 0.0,
        "width_is_complete": bool(described) and not unknown,
    }


def build_ledger(build_dir: Path, source_pdf: Path):
    docx_path = build_dir / "基础投标文件.docx"
    args = argparse.Namespace(
        source_pdf=str(source_pdf),
        build_dir=str(build_dir),
        out_json="",
        out_md="",
    )
    audit = diagnostic.build_report(args)

    document = Document(docx_path)
    paragraphs = list(document.paragraphs)
    chains = {}
    for index, paragraph in enumerate(paragraphs):
        props, runs = paragraph_chain(paragraph)
        chains[index] = {"paragraph_properties": props, "runs": runs}

    rows = []
    figure_space_rows = 0
    for row in audit["rows"]:
        generated = row.get("generated") or {}
        paragraph_index = generated.get("generated_paragraph_index")
        entry = {
            "source_page": row["source_page"],
            "source_y_top": row["source_y_top"],
            "source_row_raw_text": row["source_row_raw_text"],
            "source_alignment_class": row["alignment_class"],
            "source_row_extent_x0": row["source_row_extent_x0"],
            "source_row_extent_x1": row["source_row_extent_x1"],
            "source_rules_in_band": row["source_rules_in_band"],
            "source_rules_in_band_count": row["source_rules_in_band_count"],
            "generated_paragraph_index": paragraph_index,
            "in_build_scope": paragraph_index is not None,
            "source_gap_before_year_pt": row["source_gap_before_year_pt"],
            "source_gap_year_month_pt": row["source_gap_year_month_pt"],
            "source_gap_month_day_pt": row["source_gap_month_day_pt"],
        }
        if paragraph_index is None:
            entry["note"] = (
                "genuine source date row outside the build's source_page range; "
                "no generated counterpart exists and none is expected"
            )
            rows.append(entry)
            continue

        chain = chains[paragraph_index]
        runs = chain["runs"]
        fallback_size = 12.0
        for run in runs:
            if run["font_size_pt"]:
                fallback_size = run["font_size_pt"]
                break

        intervals = interval_mechanisms(runs)
        source_intervals = {
            "leading": row["source_gap_before_year_pt"],
            "year_month": row["source_gap_year_month_pt"],
            "month_day": row["source_gap_month_day_pt"],
        }
        mechanisms = {}
        for name in ("leading", "year_month", "month_day"):
            described = describe_mechanism(intervals[name], fallback_size)
            described["source_width_pt"] = source_intervals[name]
            if described["source_width_pt"] is not None:
                described["residual_pt"] = r3(
                    described["emitted_modelled_width_pt"]
                    - described["source_width_pt"]
                )
            else:
                described["residual_pt"] = None
            mechanisms[name] = described

        figure_runs = [run for run in runs if run["class"] == LEGACY_FIGURE_SPACE]
        if figure_runs:
            figure_space_rows += 1

        entry.update(
            {
                "generated_paragraph_properties": chain["paragraph_properties"],
                "generated_runs": runs,
                "generated_run_count": len(runs),
                "generated_token_run_count": sum(
                    1 for run in runs if run["class"] == TOKEN
                ),
                "generated_spacer_run_count": sum(
                    1 for run in runs if run["class"] == INTRINSIC_SPACER
                ),
                "generated_figure_space_run_count": len(figure_runs),
                "generated_figure_space_glyph_count": sum(
                    run["length"] for run in figure_runs
                ),
                "generated_tab_run_count": sum(
                    1 for run in runs if run["class"] == TAB_MECHANISM
                ),
                "generated_zero_width_spacer_count": sum(
                    1
                    for run in runs
                    if run["class"] == INTRINSIC_SPACER
                    and isinstance(run["w_spacing_twips"], int)
                    and run["w_spacing_twips"] <= 0
                ),
                "generated_physical_space_run_count": sum(
                    1
                    for run in runs
                    if run["class"] in (INTRINSIC_SPACER, LEGACY_FIGURE_SPACE)
                ),
                "intervals": mechanisms,
                "source_intervals_pt": source_intervals,
            }
        )

        # Construct accounting: what the row's emitted runs are modelled to
        # measure, against what the source's own extent measures.  The extent is
        # the source glyph union including the rules that belong to the row, so
        # it is exactly leading interval + tokens + the two interior intervals.
        token_widths = []
        for token in diagnostic.DATE_TOKENS:
            key = {
                "年": "source_year_x",
                "月": "source_month_x",
                "日": "source_day_x",
            }[token]
            span = row.get(key)
            if span:
                token_widths.append(float(span[1]) - float(span[0]))
        modelled_total = 0.0
        unmodelled = []
        without_mechanism = []
        for name in ("leading", "year_month", "month_day"):
            mechanism = mechanisms[name]
            source_width = source_intervals[name]
            if not mechanism["runs"]:
                if source_width is not None:
                    without_mechanism.append(name)
                continue
            if mechanism["width_is_complete"]:
                modelled_total += mechanism["emitted_modelled_width_pt"]
            else:
                # A mechanism whose runs carry no modelled width (an absolute
                # tab positioned at the source anchor, say) still spans its
                # source interval; it is counted at the source width and named,
                # so the completeness check does not silently pass.
                unmodelled.append(name)
                if source_width is not None:
                    modelled_total += float(source_width)
        source_extent = float(row["source_row_extent_x1"]) - float(
            row["source_row_extent_x0"]
        )
        emitted_construct = modelled_total + sum(token_widths)
        entry["construct_accounting"] = {
            "source_effective_row_width_pt": r2(source_extent),
            "sum_source_token_widths_pt": r2(sum(token_widths)),
            "sum_source_interval_widths_pt": r2(
                sum(value for value in source_intervals.values() if value is not None)
            ),
            "sum_emitted_interval_widths_pt": r2(modelled_total),
            "intervals_via_unmodelled_mechanism": unmodelled,
            "intervals_with_source_width_but_no_mechanism": without_mechanism,
            "target_intrinsic_segment_count": sum(
                1
                for name in ("leading", "year_month", "month_day")
                for run in mechanisms[name]["runs"]
                if run["class"] == INTRINSIC_SPACER
            ),
            "emitted_construct_width_pt": r2(emitted_construct),
            "construct_minus_extent_pt": r3(emitted_construct - source_extent),
            "reconstructs_source_row": bool(
                abs(emitted_construct - source_extent) <= 0.25
                and not without_mechanism
            ),
            "method": (
                "the row's emitted intervals are the modelled rendered widths of "
                "the run chain in the delivered .docx (source widths are used for "
                "an interval whose mechanism is an absolute tab); the source "
                "extent is its glyph union incl. the rules that belong to the row"
            ),
        }
        rows.append(entry)

    cover = next(
        (entry for entry in rows if entry.get("source_page") == 40), None
    )
    cover_leading = None
    if cover is not None:
        leading_runs = [
            run
            for run in cover["generated_runs"]
            if run["run_index"] < _first_token_index(cover["generated_runs"])
        ]
        cover_leading = {
            "runs": leading_runs,
            "mechanism": (
                leading_runs[0]["class"] if leading_runs else "NO_RUN_BEFORE_FIRST_TOKEN"
            ),
            "basis": (
                "the runs the delivered .docx emits before the row's first date "
                "token, i.e. the mechanism that owns the leading source interval"
            ),
        }

    return {
        "schema": "case001_date_segment_chain_ledger/1",
        "generated_by": "scripts/v1_date_segment_chain_ledger.py",
        "build": str(build_dir).replace("\\", "/"),
        "build_hashes": audit["build_hashes"],
        "source_pdf": audit["source_pdf"],
        "source_pdf_sha256": audit["source_pdf_sha256"],
        "rows": rows,
        "summary": {
            "source_date_rows_document_wide": len(rows),
            "rows_in_build_scope": sum(1 for entry in rows if entry["in_build_scope"]),
            "rows_with_figure_space_geometry": figure_space_rows,
            "date_figure_space_run_count": sum(
                entry.get("generated_figure_space_run_count", 0) for entry in rows
            ),
            "date_figure_space_glyph_count": sum(
                entry.get("generated_figure_space_glyph_count", 0) for entry in rows
            ),
            "date_intrinsic_spacer_run_count": sum(
                entry.get("generated_spacer_run_count", 0) for entry in rows
            ),
            "date_tab_run_count": sum(
                entry.get("generated_tab_run_count", 0) for entry in rows
            ),
            "rows_reconstructing_source_width": sum(
                1
                for entry in rows
                if entry.get("construct_accounting", {}).get("reconstructs_source_row")
            ),
        },
        "cover_leading_interval": cover_leading,
        "disclosures": [
            "READ-ONLY over the build: the delivered .docx is opened for reading; "
            "only the report artefacts are written.",
            "The interval decomposition is derived from the run chain alone: the "
            "token runs are the boundaries and everything between two adjacent "
            "tokens belongs to that interval. A mechanism list may therefore "
            "contain a run the source did not intend for geometry (for example a "
            "label), which is reported as OTHER rather than being silently "
            "reclassified.",
            "Modelled widths use tender_basic/intrinsic_spacer.py, the same "
            "calibration the builder emits from, so a systematic calibration "
            "error would show up as a uniform residual rather than as a "
            "reconstruction failure. The reconstruction check is therefore an "
            "*arithmetic* check on the chain, not an independent measurement of "
            "the page.",
            "The interval-level reconstruction required before render is enforced "
            "by the builder itself (date_gap_decomposition_log.reconstructs_source_gap); "
            "the row-level construct check in this ledger is computed from the "
            "emitted chain and the source's measured extent.",
        ],
    }


def _first_token_index(runs):
    for run in runs:
        if run["class"] == TOKEN:
            return run["run_index"]
    return len(runs)


def render_markdown(report):
    lines = [
        "# CASE001 date segment chain ledger",
        "",
        "Build: `%s`" % report["build"],
        "",
        "DOCX SHA256: `%s`" % report["build_hashes"]["docx_sha256"],
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append("* `%s` = %s" % (key, value))
    lines.append("")
    cover = report.get("cover_leading_interval")
    if cover:
        lines.append("## Cover leading interval (source page 40)")
        lines.append("")
        lines.append("* mechanism = `%s`" % cover["mechanism"])
        lines.append("* %s" % cover["basis"])
        lines.append("")
        lines.append("| run | class | len | codepoints | underline | w:spacing |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for run in cover["runs"]:
            lines.append(
                "| %d | `%s` | %d | %s | %s | %s |"
                % (
                    run["run_index"],
                    run["class"],
                    run["length"],
                    " ".join(run["codepoints"][:6]),
                    run["underline"],
                    run["w_spacing_twips"],
                )
            )
        lines.append("")
    lines.append("## Rows")
    lines.append("")
    lines.append(
        "| src p | y | class | ¶ | jc | left | tokens | spacers | fig-space | tabs | "
        "src lead/ym/md | emitted lead/ym/md |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for entry in report["rows"]:
        if not entry["in_build_scope"]:
            lines.append(
                "| %s | %s | `%s` | - | - | - | - | - | - | - | %s | - |"
                % (
                    entry["source_page"],
                    entry["source_y_top"],
                    entry["source_alignment_class"],
                    " / ".join(
                        str(entry.get(key))
                        for key in (
                            "source_gap_before_year_pt",
                            "source_gap_year_month_pt",
                            "source_gap_month_day_pt",
                        )
                    ),
                )
            )
            continue
        props = entry["generated_paragraph_properties"]
        intervals = entry["intervals"]
        lines.append(
            "| %s | %s | `%s` | %s | %s | %s | %d | %d | %d | %d | %s | %s |"
            % (
                entry["source_page"],
                entry["source_y_top"],
                entry["source_alignment_class"],
                entry["generated_paragraph_index"],
                props["jc"],
                props["indents"].get("left"),
                entry["generated_token_run_count"],
                entry["generated_spacer_run_count"],
                entry["generated_figure_space_run_count"],
                entry["generated_tab_run_count"],
                " / ".join(
                    str(entry["source_intervals_pt"][key]) for key in
                    ("leading", "year_month", "month_day")
                ),
                " / ".join(
                    str(intervals[key]["emitted_modelled_width_pt"]) for key in
                    ("leading", "year_month", "month_day")
                ),
            )
        )
    lines.append("")
    lines.append("## Disclosures")
    lines.append("")
    for item in report["disclosures"]:
        lines.append("* %s" % item)
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-dir", required=True)
    parser.add_argument(
        "--source-pdf",
        default=str(
            REPO_ROOT
            / "acceptance"
            / "private"
            / "7.28引江济淮郸城配套项目一体化泵站询比文件.pdf"
        ),
    )
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", default="")
    args = parser.parse_args(argv)

    report = build_ledger(Path(args.build_dir), Path(args.source_pdf))
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        with open(out_md, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_markdown(report))

    summary = report["summary"]
    print("build                          : %s" % report["build"])
    print("docx sha256                    : %s" % report["build_hashes"]["docx_sha256"])
    for key, value in summary.items():
        print("%-30s : %s" % (key, value))
    cover = report.get("cover_leading_interval")
    if cover:
        print("cover leading mechanism        : %s" % cover["mechanism"])
        for run in cover["runs"]:
            print(
                "   run%-3d %-20s len=%-3d u=%-6s sp=%s"
                % (run["run_index"], run["class"], run["length"], run["underline"],
                   run["w_spacing_twips"])
            )
    print("wrote                          : %s" % out_json)
    if args.out_md:
        print("wrote                          : %s" % args.out_md)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
