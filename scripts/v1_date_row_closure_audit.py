#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Round-4 closure audit for the date rows: full audit + date-rule endpoints.

READ-ONLY over the build; writes only the two artefacts named by ``--out-json``
/ ``--out-md``.

This is the *acceptance* instrument for the date work, and it differs from
``scripts/v1_date_row_round4_diagnostic.py`` (the diagnostic that first
described the defects) in three ways that the closure demanded:

1. **A measured centring inset is not a synthetic indent.**  ``w:jc=center``
   stays the alignment, and the row's centre axis is corrected to the source
   row's own measured centre with a source-derived asymmetric inset
   (``SOURCE_CENTER_ALIGNMENT_FRAME``).  The older verdict counted any non-zero
   ``w:left`` on a centred row as an "unexpected indent", which would now flag
   the correction itself.  Here the expected inset is recomputed from the
   source's measured centroid offset and compared to the emitted one.

2. **A gap's mechanism is read from the delivered ``.docx``.**  Whether the row
   reproduces a source interval is a property of the emitted run chain (one
   space with stated tracking, a figure-space count, an absolute tab, or
   nothing), and that is what is classified here - so a row that renders a
   plausible width by *counting glyphs* is visible as such instead of passing on
   its rendered gap alone.

3. **Date-rule endpoints are graded per rule.**  Every source rule that belongs
   to a date row is paired with a generated underline span one-to-one, so a
   single merged underline cannot satisfy several source rules, and a generated
   underline with no source counterpart is reported as invented.

Pass requires, per row: native alignment matching the source class, a legitimate
indent, every measurable source interval reproduced within the frozen 2.0 pt
geometry tolerance (``tender_basic/geometry_rule_qa.py:33``), every token anchor
within it, and no figure-space geometry run.  The rule-endpoint gate requires
matched == source rule count with lost == invented == 0 and every endpoint
residual within 2.0 pt.
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

import v1_date_row_round4_diagnostic as diagnostic  # noqa: E402
import v1_date_segment_chain_ledger as ledger  # noqa: E402

from docx import Document  # noqa: E402

TOLERANCE_PT = diagnostic.TYPOGRAPHY_TOLERANCE_PT  # 2.0, frozen
INVENTED_MATERIAL_PT = 2.0
#: A centring inset the source proves: the row's measured centroid offset is
#: doubled, and below half a point the source proves no asymmetry at all.
CENTER_INSET_EPSILON_PT = 0.5
CENTER_INSET_TOLERANCE_PT = 0.5
#: Generated underline rules are searched in this window below the row's top.
RULE_BAND_TOP_PT = -1.0
RULE_BAND_BOTTOM_PT = 24.0
#: How far left of the year a date row's leading rule may start.
LEADING_RULE_REACH_PT = 130.0

IMPLIED_JC = {
    "SOURCE_ALIGNED_CENTER": "center",
    "SOURCE_ALIGNED_LEFT": "left",
    "SOURCE_ALIGNED_RIGHT": "right",
    "SOURCE_ANCHORED_FORM_ROW": "left",
}


def r2(value):
    if value is None:
        return None
    return round(float(value) + 0.0, 2)


def r3(value):
    if value is None:
        return None
    return round(float(value) + 0.0, 3)


def generated_rules(pdf_path: Path, cache: dict):
    """All horizontal rules of one generated page, memoised."""

    def load(page_index):
        if page_index not in cache:
            document = pymupdf.open(str(pdf_path))
            page = document[page_index - 1]
            cache[page_index] = diagnostic.horizontal_rules(page)
            document.close()
        return cache[page_index]

    return load


def merge_rules(rules, y_tolerance=1.0, gap_tolerance=0.5):
    """Union co-linear rules on one visual line into maximal spans.

    A source rule is a single underline, but a renderer is free to paint it as
    several rectangles: a tracked space run whose underline is one logical line
    comes back from the PDF as the run's full span *and* a shorter rectangle
    inside it.  Counting those separately would report every emitted rule as
    both matched and invented.  Merging on a tiny gap tolerance keeps genuinely
    separate rules apart - the source's own three rules sit 11.5 pt apart.
    """

    ordered = sorted(rules, key=lambda rule: (round(rule["y"], 1), rule["x0"]))
    merged = []
    for rule in ordered:
        if merged:
            last = merged[-1]
            if (
                abs(float(rule["y"]) - float(last["y"])) <= y_tolerance
                and float(rule["x0"]) <= float(last["x1"]) + gap_tolerance
            ):
                last["x1"] = max(float(last["x1"]), float(rule["x1"]))
                last["x0"] = min(float(last["x0"]), float(rule["x0"]))
                last["width_pt"] = last["x1"] - last["x0"]
                last["merged_from"] = last.get("merged_from", 1) + 1
                continue
        merged.append(dict(rule))
    return merged


def pair_rules(source_rules, generated_candidates):
    """One-to-one greedy pairing by combined endpoint distance.

    Returns ``(pairs, lost, invented)`` where a source rule that could not be
    paired is *lost* and a generated rule nobody claimed is *invented*.  The
    one-to-one constraint is the point: an underline that spans two source
    rules is one generated span, so the second source rule is reported lost
    rather than being counted as reproduced.
    """

    remaining = list(generated_candidates)
    pairs = []
    lost = []
    for rule in source_rules:
        best = None
        for index, candidate in enumerate(remaining):
            dx0 = abs(float(candidate["x0"]) - float(rule["x0"]))
            dx1 = abs(float(candidate["x1"]) - float(rule["x1"]))
            if dx0 > TOLERANCE_PT or dx1 > TOLERANCE_PT:
                continue
            score = dx0 + dx1
            if best is None or score < best[0]:
                best = (score, index, dx0, dx1, candidate)
        if best is None:
            lost.append(rule)
            continue
        _score, index, dx0, dx1, candidate = best
        remaining.pop(index)
        pairs.append(
            {
                "source_x0": r2(rule["x0"]),
                "source_x1": r2(rule["x1"]),
                "source_y": r2(rule["y"]),
                "generated_x0": r2(candidate["x0"]),
                "generated_x1": r2(candidate["x1"]),
                "generated_y": r2(candidate["y"]),
                "x0_residual_pt": r3(float(candidate["x0"]) - float(rule["x0"])),
                "x1_residual_pt": r3(float(candidate["x1"]) - float(rule["x1"])),
                "is_leading_rule": bool(float(rule["x1"]) <= float(rule["x1"])),
            }
        )
    invented = [
        {
            "generated_x0": r2(candidate["x0"]),
            "generated_x1": r2(candidate["x1"]),
            "generated_y": r2(candidate["y"]),
            "width_pt": r2(candidate["width_pt"]),
        }
        for candidate in remaining
    ]
    return pairs, lost, invented


def build_audit(build_dir: Path, source_pdf: Path):
    docx_path = build_dir / "基础投标文件.docx"
    pdf_path = build_dir / "基础投标文件.pdf"
    args = argparse.Namespace(
        source_pdf=str(source_pdf), build_dir=str(build_dir), out_json="", out_md=""
    )
    audit = diagnostic.build_report(args)

    document = Document(docx_path)
    chains = {}
    for index, paragraph in enumerate(document.paragraphs):
        chains[index] = ledger.paragraph_chain(paragraph)

    rule_cache: dict = {}
    rules_for_page = generated_rules(pdf_path, rule_cache)

    rows = []
    counters = {
        "alignment_mismatch": 0,
        "collapsed": 0,
        "lost_gaps": 0,
        "invented_gaps": 0,
        "unexpected_indents": 0,
        "ambiguous": 0,
        "figure_space_rows": 0,
    }
    rows_within = 0
    all_pairs = []
    all_lost = []
    all_invented = []
    source_rule_total = 0
    max_gap_residual = 0.0
    max_anchor_residual = 0.0
    max_rule_x0 = 0.0
    max_rule_x1 = 0.0

    for row in audit["rows"]:
        generated = row.get("generated") or {}
        paragraph_index = generated.get("generated_paragraph_index")
        if paragraph_index is None:
            rows.append(
                {
                    "source_page": row["source_page"],
                    "source_y_top": row["source_y_top"],
                    "in_build_scope": False,
                    "verdict": "OUTSIDE_BUILD_SCOPE",
                    "note": (
                        "genuine source date row outside the build's source_page "
                        "range; no generated counterpart exists and none is expected"
                    ),
                }
            )
            continue

        props, runs = chains[paragraph_index]
        entry = {
            "source_page": row["source_page"],
            "source_y_top": row["source_y_top"],
            "source_alignment_class": row["alignment_class"],
            "in_build_scope": True,
            "generated_paragraph_index": paragraph_index,
            "generated_jc": props["jc"],
            "generated_left_twips": props["indents"].get("left"),
            "generated_left_pt": r2((props["indents"].get("left") or 0) / 20.0),
            "generated_run_count": len(runs),
            "generated_figure_space_run_count": sum(
                1 for run in runs if run["class"] == ledger.LEGACY_FIGURE_SPACE
            ),
            "generated_intrinsic_spacer_run_count": sum(
                1 for run in runs if run["class"] == ledger.INTRINSIC_SPACER
            ),
            "generated_tab_run_count": sum(
                1 for run in runs if run["class"] == ledger.TAB_MECHANISM
            ),
            "generated_zero_tracking_spacer_count": sum(
                1
                for run in runs
                if run["class"] == ledger.INTRINSIC_SPACER
                and isinstance(run["w_spacing_twips"], int)
                and run["w_spacing_twips"] <= 0
            ),
            "generated_runs": runs,
        }
        if entry["generated_figure_space_run_count"]:
            counters["figure_space_rows"] += 1

        notes = []
        implied = IMPLIED_JC.get(row["alignment_class"])
        align_ok = implied is not None and props["jc"] == implied
        entry["alignment_class_matches"] = align_ok
        if implied is None:
            counters["ambiguous"] += 1
            entry["alignment_ambiguous"] = True
        elif not align_ok:
            counters["alignment_mismatch"] += 1
            notes.append(
                "source class %s implies w:jc=%s, generated w:jc=%s"
                % (row["alignment_class"], implied, props["jc"])
            )

        # A centring inset the source measured is legitimate; anything else on a
        # centred row is a synthetic position surrogate.
        delta = float(row.get("centroid_offset_pt") or 0.0)
        expected_inset = 2.0 * delta if abs(delta) >= CENTER_INSET_EPSILON_PT else 0.0
        entry["centring"] = {
            "source_centroid_offset_pt": r2(delta),
            "expected_center_inset_pt": r2(expected_inset),
            "emitted_left_inset_pt": entry["generated_left_pt"],
        }
        if row["alignment_class"] == "SOURCE_ALIGNED_CENTER":
            emitted = float(props["indents"].get("left") or 0) / 20.0
            legit = abs(emitted - expected_inset) <= CENTER_INSET_TOLERANCE_PT
            entry["centring"]["inset_is_source_measured"] = legit
            if not legit:
                counters["unexpected_indents"] += 1
                notes.append(
                    "centred row carries w:left=%.2f pt, not the source-measured "
                    "centre-axis inset %.2f pt" % (emitted, expected_inset)
                )

        # Interval fidelity, from the source's measured intervals.
        intervals = ledger.interval_mechanisms(runs)
        source_intervals = {
            "leading": row["source_gap_before_year_pt"],
            "year_month": row["source_gap_year_month_pt"],
            "month_day": row["source_gap_month_day_pt"],
        }
        generated_gaps = {
            "leading": generated.get("generated_gap_before_year_pt"),
            "year_month": generated.get("generated_gap_year_month_pt"),
            "month_day": generated.get("generated_gap_month_day_pt"),
        }
        interval_records = {}
        row_ok = align_ok and entry["centring"].get("inset_is_source_measured", True)
        for name in ("leading", "year_month", "month_day"):
            source_width = source_intervals[name]
            rendered = generated_gaps[name]
            classes = sorted({run["class"] for run in intervals[name]})
            record = {
                "source_width_pt": source_width,
                "generated_width_pt": rendered,
                "residual_pt": (
                    r3(rendered - source_width)
                    if rendered is not None and source_width is not None
                    else None
                ),
                "mechanism_classes": classes,
                "material_in_source": bool(
                    source_width is not None
                    and source_width > INVENTED_MATERIAL_PT
                ),
            }
            if record["material_in_source"]:
                if rendered is None:
                    # The leading interval of a row with nothing printed to its
                    # left cannot be measured as a glyph gap; it is graded
                    # through its rule endpoint or through the year anchor.
                    record["verdict"] = "NOT_MEASURABLE_AS_GLYPH_GAP"
                else:
                    error = abs(record["residual_pt"])
                    max_gap_residual = max(max_gap_residual, error)
                    if error > TOLERANCE_PT:
                        counters["lost_gaps"] += 1
                        row_ok = False
                        record["verdict"] = "LOST"
                    else:
                        record["verdict"] = "PRESERVED"
            elif rendered is not None and rendered > INVENTED_MATERIAL_PT:
                counters["invented_gaps"] += 1
                row_ok = False
                record["verdict"] = "INVENTED"
            else:
                record["verdict"] = "NOT_APPLICABLE"
            interval_records[name] = record

        # Collapse: every material source interval rendered as adjacent glyphs.
        material = [
            name
            for name in ("year_month", "month_day")
            if interval_records[name]["material_in_source"]
        ]
        if material and all(
            (generated_gaps[name] or 0.0) <= 1.0 for name in material
        ):
            counters["collapsed"] += 1
            entry["collapsed"] = True
            row_ok = False
        else:
            entry["collapsed"] = False

        # Token anchors.
        source_tokens = {
            "年": row["source_year_x"],
            "月": row["source_month_x"],
            "日": row["source_day_x"],
        }
        token_anchors = {}
        for token, span in source_tokens.items():
            generated_span = (generated.get("generated_token_x") or {}).get(token)
            if not span or not generated_span:
                token_anchors[token] = {"residual_pt": None}
                continue
            residual = float(generated_span[0]) - float(span[0])
            max_anchor_residual = max(max_anchor_residual, abs(residual))
            token_anchors[token] = {
                "source_x0": r2(span[0]),
                "generated_x0": r2(generated_span[0]),
                "residual_pt": r3(residual),
            }
            if abs(residual) > TOLERANCE_PT:
                row_ok = False
        entry["token_anchors"] = token_anchors

        # Rule endpoints for this row's own rules.
        page = generated.get("generated_pdf_page")
        y_top = generated.get("generated_pdf_y_top")
        source_rules = row.get("source_rules_in_band") or []
        source_rule_total += len(source_rules)
        if page and y_top is not None and source_rules:
            year_x0 = float(row["source_year_x"][0])
            day_x1 = float(row["source_day_x"][1])
            candidates = merge_rules(
                [
                    rule
                    for rule in rules_for_page(int(page))
                    if y_top + RULE_BAND_TOP_PT
                    <= rule["y"]
                    <= y_top + RULE_BAND_BOTTOM_PT
                    and rule["x0"] >= year_x0 - LEADING_RULE_REACH_PT
                    and rule["x1"] <= day_x1 + TOLERANCE_PT
                ]
            )
            pairs, lost, invented = pair_rules(source_rules, candidates)
            for pair in pairs:
                pair["source_page"] = row["source_page"]
                pair["generated_paragraph_index"] = paragraph_index
                pair["is_leading_rule"] = bool(
                    float(pair["source_x1"]) <= float(row["source_year_x"][0]) + 1.5
                )
                max_rule_x0 = max(max_rule_x0, abs(pair["x0_residual_pt"]))
                max_rule_x1 = max(max_rule_x1, abs(pair["x1_residual_pt"]))
            for rule in lost:
                all_lost.append(
                    {
                        "source_page": row["source_page"],
                        "generated_paragraph_index": paragraph_index,
                        "source_x0": r2(rule["x0"]),
                        "source_x1": r2(rule["x1"]),
                    }
                )
            for rule in invented:
                rule["source_page"] = row["source_page"]
                rule["generated_paragraph_index"] = paragraph_index
                all_invented.append(rule)
            all_pairs.extend(pairs)
            entry["rule_pairs"] = pairs
            entry["rule_lost"] = len(lost)
            entry["rule_invented"] = len(invented)
            entry["leading_rule_width_residual_pt"] = next(
                (
                    r3(
                        (pair["generated_x1"] - pair["generated_x0"])
                        - (pair["source_x1"] - pair["source_x0"])
                    )
                    for pair in pairs
                    if pair["is_leading_rule"]
                ),
                None,
            )
        else:
            entry["rule_pairs"] = []
            entry["rule_lost"] = 0
            entry["rule_invented"] = 0
            entry["leading_rule_width_residual_pt"] = None

        entry["intervals"] = interval_records
        entry["notes"] = notes
        entry["within_tolerance"] = bool(row_ok)
        if row_ok:
            rows_within += 1
        entry["verdict"] = "PASS" if row_ok else "FAIL"
        rows.append(entry)

    in_scope = [entry for entry in rows if entry["in_build_scope"]]
    accounting = {
        "source_date_rows_document_wide": len(rows),
        "source_date_rows_build_scope": len(in_scope),
        "generated_date_rows": len(in_scope),
        "rows_within_2pt": rows_within,
        "rows_within_2pt_label": "%d/%d" % (rows_within, len(in_scope)),
        "alignment_mismatch": counters["alignment_mismatch"],
        "collapsed": counters["collapsed"],
        "lost_gaps": counters["lost_gaps"],
        "invented_gaps": counters["invented_gaps"],
        "unexpected_indents": counters["unexpected_indents"],
        "ambiguous": counters["ambiguous"],
        "rows_with_figure_space_geometry": counters["figure_space_rows"],
        "date_figure_space_geometry_runs": sum(
            entry.get("generated_figure_space_run_count", 0) for entry in in_scope
        ),
        "date_intrinsic_spacer_runs": sum(
            entry.get("generated_intrinsic_spacer_run_count", 0) for entry in in_scope
        ),
        "date_tab_runs": sum(
            entry.get("generated_tab_run_count", 0) for entry in in_scope
        ),
        #: Spacers emitted with zero tracking because their target was below one
        #: space's advance.  A *zero-width* geometry segment never reaches here:
        #: it is below the materiality floor and emits no run at all.
        "date_zero_tracking_spacer_runs": sum(
            entry.get("generated_zero_tracking_spacer_count", 0) for entry in in_scope
        ),        "max_date_gap_residual_pt": r3(max_gap_residual),
        "max_date_token_anchor_residual_pt": r3(max_anchor_residual),
    }
    endpoints = {
        "source_rule_count": source_rule_total,
        "matched": len(all_pairs),
        "lost": len(all_lost),
        "invented": len(all_invented),
        "max_x0_residual_pt": r3(max_rule_x0),
        "max_x1_residual_pt": r3(max_rule_x1),
        "leading_rule_pairs": sum(1 for pair in all_pairs if pair["is_leading_rule"]),
        "lost_rules": all_lost,
        "invented_rules": all_invented,
        "pairs": all_pairs,
    }

    date_pass = (
        accounting["source_date_rows_document_wide"] == 12
        and accounting["source_date_rows_build_scope"] == 10
        and accounting["generated_date_rows"] == 10
        and accounting["rows_within_2pt"] == 10
        and accounting["alignment_mismatch"] == 0
        and accounting["collapsed"] == 0
        and accounting["lost_gaps"] == 0
        and accounting["invented_gaps"] == 0
        and accounting["unexpected_indents"] == 0
        and accounting["ambiguous"] == 0
        and accounting["date_figure_space_geometry_runs"] == 0
        and accounting["max_date_gap_residual_pt"] <= TOLERANCE_PT
        and accounting["max_date_token_anchor_residual_pt"] <= TOLERANCE_PT
    )
    endpoint_pass = (
        endpoints["matched"] == endpoints["source_rule_count"]
        and endpoints["lost"] == 0
        and endpoints["invented"] == 0
        and endpoints["max_x0_residual_pt"] <= TOLERANCE_PT
        and endpoints["max_x1_residual_pt"] <= TOLERANCE_PT
    )

    return {
        "schema": "case001_date_row_closure/1",
        "generated_by": "scripts/v1_date_row_closure_audit.py",
        "build": str(build_dir).replace("\\", "/"),
        "build_hashes": audit["build_hashes"],
        "source_pdf": audit["source_pdf"],
        "source_pdf_sha256": audit["source_pdf_sha256"],
        "tolerance_pt": TOLERANCE_PT,
        "tolerance_provenance": (
            "tender_basic/geometry_rule_qa.py:33 MANDATORY_TOLERANCE_PT = 2.0, "
            "restated in docs/V1_DECISIONS.md section 2.1 as frozen"
        ),
        "rows": rows,
        "accounting": accounting,
        "rule_endpoints": endpoints,
        "DATE_ROW_ALIGNMENT_FIDELITY": "PASS" if accounting["alignment_mismatch"] == 0 else "FAIL",
        "DATE_ROW_GAP_FIDELITY": "PASS" if accounting["lost_gaps"] == 0 and accounting["invented_gaps"] == 0 else "FAIL",
        "DATE_ROW_TOKEN_ANCHOR_FIDELITY": "PASS" if accounting["max_date_token_anchor_residual_pt"] <= TOLERANCE_PT else "FAIL",
        "DATE_FIGURE_SPACE_GEOMETRY_RUNS": accounting["date_figure_space_geometry_runs"],
        "DATE_RULE_ENDPOINT_FIDELITY": "PASS" if endpoint_pass else "FAIL",
        "DATE_AUDIT": "PASS" if date_pass else "FAIL",
        "indent_policy": (
            "A centred row's w:left is legitimate exactly when it equals twice the "
            "source row's measured centroid offset (0 below 0.5 pt, where the "
            "source proves no asymmetry); that is SOURCE_CENTER_ALIGNMENT_FRAME, "
            "the native-alignment contract plus a measured axis correction, not a "
            "position surrogate. Non-centred rows state w:jc=left/right and their "
            "indent is the source-anchored body indent; their position fidelity is "
            "graded by the token anchors."
        ),
        "disclosures": [
            "READ-ONLY over the build; only the report artefacts are written.",
            "Generated underline spans are read from the build PDF's vector "
            "drawings with the same rule filter the source audit uses "
            "(height <= 2.4 pt, width >= 6 pt), inside a +/- window around the "
            "row's rendered top; a rule of another row that shares the window "
            "would be reported as invented rather than silently matched.",
            "Rule pairing is one-to-one and greedy on combined endpoint distance: "
            "a single merged generated underline cannot satisfy two source rules, "
            "and the second source rule is reported lost.",
            "The leading interval of a row with nothing printed to its left is not "
            "measurable as a glyph gap; it is graded through its own rule "
            "endpoint pair and through the year anchor.",
            "A generated underline is only claimed as a match within 2.0 pt in "
            "both endpoints, the frozen geometry tolerance; no new tolerance is "
            "introduced.",
        ],
    }


def render_markdown(report):
    accounting = report["accounting"]
    endpoints = report["rule_endpoints"]
    lines = [
        "# CASE001 date-row closure audit",
        "",
        "Build: `%s`" % report["build"],
        "",
        "DOCX SHA256: `%s`" % report["build_hashes"]["docx_sha256"],
        "",
        "## Status",
        "",
        "| gate | value |",
        "| --- | --- |",
        "| DATE_AUDIT | `%s` |" % report["DATE_AUDIT"],
        "| DATE_ROW_ALIGNMENT_FIDELITY | `%s` |" % report["DATE_ROW_ALIGNMENT_FIDELITY"],
        "| DATE_ROW_GAP_FIDELITY | `%s` |" % report["DATE_ROW_GAP_FIDELITY"],
        "| DATE_ROW_TOKEN_ANCHOR_FIDELITY | `%s` |" % report["DATE_ROW_TOKEN_ANCHOR_FIDELITY"],
        "| DATE_RULE_ENDPOINT_FIDELITY | `%s` |" % report["DATE_RULE_ENDPOINT_FIDELITY"],
        "| DATE_FIGURE_SPACE_GEOMETRY_RUNS | `%s` |" % report["DATE_FIGURE_SPACE_GEOMETRY_RUNS"],
        "",
        "## Accounting",
        "",
    ]
    for key, value in accounting.items():
        lines.append("* `%s` = %s" % (key, value))
    lines.append("")
    lines.append("## Date-rule endpoints")
    lines.append("")
    for key, value in endpoints.items():
        if key in ("pairs", "lost_rules", "invented_rules"):
            continue
        lines.append("* `%s` = %s" % (key, value))
    lines.append("")
    lines.append("## Rows")
    lines.append("")
    lines.append(
        "| src p | y | class | ¶ | jc | left pt | intervals (src → gen) | "
        "anchors Δ年/Δ月/Δ日 | rules m/l/i | verdict |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for entry in report["rows"]:
        if not entry["in_build_scope"]:
            lines.append(
                "| %s | %s | `%s` | - | - | - | outside build scope | - | - | `%s` |"
                % (
                    entry["source_page"],
                    entry["source_y_top"],
                    entry.get("source_alignment_class", "-"),
                    entry["verdict"],
                )
            )
            continue
        intervals = entry["intervals"]
        anchors = entry["token_anchors"]
        lines.append(
            "| %s | %s | `%s` | %s | %s | %s | %s | %s | %s/%s/%s | `%s` |"
            % (
                entry["source_page"],
                entry["source_y_top"],
                entry["source_alignment_class"],
                entry["generated_paragraph_index"],
                entry["generated_jc"],
                entry["generated_left_pt"],
                " · ".join(
                    "%s %s→%s" % (
                        name,
                        intervals[name]["source_width_pt"],
                        intervals[name]["generated_width_pt"],
                    )
                    for name in ("leading", "year_month", "month_day")
                ),
                "/".join(
                    str(anchors[token]["residual_pt"]) for token in ("年", "月", "日")
                ),
                len(entry.get("rule_pairs") or []),
                entry.get("rule_lost"),
                entry.get("rule_invented"),
                entry["verdict"],
            )
        )
    lines.append("")
    lines.append("## Disclosures")
    lines.append("")
    lines.append("* Indent policy: %s" % report["indent_policy"])
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
    parser.add_argument(
        "--out-endpoints",
        default="",
        help="also write the date-rule endpoint gate as its own artefact",
    )
    args = parser.parse_args(argv)

    report = build_audit(Path(args.build_dir), Path(args.source_pdf))
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

    if args.out_endpoints:
        out_endpoints = Path(args.out_endpoints)
        out_endpoints.parent.mkdir(parents=True, exist_ok=True)
        with open(out_endpoints, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "schema": "case001_date_rule_endpoint/1",
                    "generated_by": "scripts/v1_date_row_closure_audit.py",
                    "build": report["build"],
                    "build_hashes": report["build_hashes"],
                    "tolerance_pt": TOLERANCE_PT,
                    "DATE_RULE_ENDPOINT_FIDELITY": report[
                        "DATE_RULE_ENDPOINT_FIDELITY"
                    ],
                    "rule_endpoints": report["rule_endpoints"],
                    "disclosures": report["disclosures"],
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")

    print("build        : %s" % report["build"])
    print("DATE_AUDIT   : %s" % report["DATE_AUDIT"])
    for key, value in report["accounting"].items():
        print("  %-38s : %s" % (key, value))
    print("DATE_RULE_ENDPOINT_FIDELITY : %s" % report["DATE_RULE_ENDPOINT_FIDELITY"])
    for key in ("source_rule_count", "matched", "lost", "invented",
                "max_x0_residual_pt", "max_x1_residual_pt", "leading_rule_pairs"):
        print("  %-38s : %s" % (key, report["rule_endpoints"][key]))
    print("per-row verdicts:")
    for entry in report["rows"]:
        if not entry["in_build_scope"]:
            print("  p%-3s %-58s %s" % (entry["source_page"], "outside build scope", entry["verdict"]))
            continue
        print(
            "  p%-3s ¶%-4s %-24s %-5s gaps %s/%s/%s anchors %s/%s/%s figspace=%s"
            % (
                entry["source_page"],
                entry["generated_paragraph_index"],
                entry["source_alignment_class"],
                entry["verdict"],
                entry["intervals"]["leading"]["residual_pt"],
                entry["intervals"]["year_month"]["residual_pt"],
                entry["intervals"]["month_day"]["residual_pt"],
                entry["token_anchors"]["年"]["residual_pt"],
                entry["token_anchors"]["月"]["residual_pt"],
                entry["token_anchors"]["日"]["residual_pt"],
                entry["generated_figure_space_run_count"],
            )
        )
        for note in entry["notes"]:
            print("        note: %s" % note)
    print("wrote        : %s" % out_json)
    if args.out_md:
        print("wrote        : %s" % args.out_md)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
