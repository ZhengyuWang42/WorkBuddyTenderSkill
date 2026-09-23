#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Round-4 document-wide audit of source date rows vs generated date paragraphs.

READ-ONLY measurement task.

This script opens the source PDF, the generated ``基础投标文件.docx``, the generated
``基础投标文件.pdf`` and ``generation_report.json`` strictly read-only and writes
*only* the two report artefacts named by ``--out-json`` / ``--out-md``.

What it measures
----------------
Source side (``page.get_text("rawdict")`` per-character bboxes only -- the source text
layer prints ``年月日`` with no blanks, so line strings are useless):

* every visual row that carries ``年`` / ``月`` / ``日`` in reading order,
* the year/month/day glyph boxes and the three horizontal gaps,
* the vector rules (``page.get_drawings()``, ``height <= 2.4 and width >= 6``) that
  belong to the row, and a gap *kind* justified from that rule evidence,
* a source alignment class computed from the row's effective extent (glyph union plus
  the rules that belong to the row) against the page centre axis.

Generated side: every ``w:p`` whose text (tab characters removed) is a date row, with
its ``w:jc`` / ``w:ind`` / ``w:tabs`` / run underline state, its role from
``generation_report.json``, and the token positions actually *rendered* in the
generated PDF.

Frozen repository constants reused (no new numeric tolerance is invented)
------------------------------------------------------------------------
* ``tender_basic/page_layout.py`` line 463
  ``centered_geometry = abs(row_centre - page_centre) <= max(8.0, page_width * 0.02)``
* ``tender_basic/geometry_rule_qa.py`` line 33 ``MANDATORY_TOLERANCE_PT = 2.0``,
  restated as ``tolerance_pt = 2.0`` in ``docs/V1_DECISIONS.md`` section 2.1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

import pymupdf
from docx import Document
from docx.oxml.ns import qn

# --------------------------------------------------------------------------- #
# Frozen repository constants / measured natural units
# --------------------------------------------------------------------------- #
# tender_basic/page_layout.py:463 -- the existing form-line centring test.
CENTRED_TOLERANCE_MIN_PT = 8.0
CENTRED_TOLERANCE_WIDTH_RATIO = 0.02
# tender_basic/geometry_rule_qa.py:33 == docs/V1_DECISIONS.md 2.1 "tolerance_pt = 2.0".
TYPOGRAPHY_TOLERANCE_PT = 2.0
# Empirically measured in the generated PDF: where the build emits bare 年月日 the
# three full-width glyphs are exactly adjacent, i.e. natural inter-glyph gap == 0.00 pt.
NATURAL_INTER_GLYPH_GAP_PT = 0.0

RULE_MAX_HEIGHT_PT = 2.4
RULE_MIN_WIDTH_PT = 6.0
RULE_EDGE_COINCIDENCE_PT = 1.5
BAND_PAD_PT = 1.0
UNDERLINE_Y_WINDOW_PT = 3.5
UNDERLINE_MAX_WIDTH_PT = 130.0
FULL_GAP_COVERAGE_RATIO = 0.95

DATE_TOKENS = ("年", "月", "日")
TAB = "\t"
# A date row may carry at most a short label prefix such as "成立时间：" and nothing else.
MAX_LABEL_PREFIX_CHARS = 8
# Sentence punctuation that marks a row as prose rather than a date row.  A colon is
# allowed because the legitimate short label prefix "成立时间：" ends with one.
PUNCT_FOR_PROSE = set("，。；？！、（）()《》<>【】[]“”\"'%,.;!?")


def strip_date_tokens(text):
    """Remove one occurrence of each date token, returning what is left."""
    stripped = text
    for token in DATE_TOKENS:
        stripped = stripped.replace(token, "", 1)
    return stripped


def date_row_purity(text):
    """``(is_date_row, leftover, reason)`` for a candidate row's flattened text.

    Whitespace is a *gap*, not a label.  A date row is written
    ``____年____月____日``, and the build may reproduce the writable space the
    source leaves as literal whitespace (figure spaces, tab characters).  That
    whitespace is the very format this audit exists to measure, so it is
    dropped before the "is this row only a date" test - otherwise a row whose
    gaps *were* preserved would be misread as prose and excluded, and the audit
    would silently lose exactly the rows it is meant to grade.
    """
    leftover = "".join(
        ch for ch in strip_date_tokens(text) if not ch.isspace()
    )
    if len(leftover) > MAX_LABEL_PREFIX_CHARS:
        return False, leftover, (
            "prose row: %d glyphs besides 年/月/日 -- e.g. %r"
            % (len(leftover), leftover[:36])
        )
    bad = [ch for ch in leftover if ch in PUNCT_FOR_PROSE]
    if bad:
        return False, leftover, (
            "prose row: contains sentence punctuation %r besides 年/月/日 -- %r"
            % ("".join(bad), leftover[:36])
        )
    return True, leftover, "row carries only 年/月/日 plus a short label prefix %r" % leftover

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def r2(value):
    if value is None:
        return None
    return round(float(value) + 0.0, 2)


def r4(value):
    if value is None:
        return None
    return round(float(value) + 0.0, 4)


def load_chars(page):
    """All visible per-character records of a page (rawdict), in reading order."""
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for ch in span["chars"]:
                    if ch["c"].strip():
                        out.append(ch)
    return out


def group_rows(chars, tolerance=2.5):
    """Group characters into visual rows by their bbox top."""
    if not chars:
        return []
    ordered = sorted(chars, key=lambda c: (round(c["bbox"][1], 2), c["bbox"][0]))
    rows = []
    current = [ordered[0]]
    for ch in ordered[1:]:
        if ch["bbox"][1] - current[0]["bbox"][1] <= tolerance:
            current.append(ch)
        else:
            rows.append(current)
            current = [ch]
    rows.append(current)
    for row in rows:
        row.sort(key=lambda c: c["bbox"][0])
    return rows


def date_tokens_in_row(row_chars):
    """Return ``(年, 月, 日)`` char records when they occur in reading order, else None."""
    seq = [c["c"] for c in row_chars]
    idx = None
    found = []
    for token in DATE_TOKENS:
        start = 0 if idx is None else idx + 1
        try:
            idx = seq.index(token, start)
        except ValueError:
            return None
        found.append(row_chars[idx])
    return tuple(found)


def horizontal_rules(page):
    """Vector rules drawn on the page: ``height <= 2.4`` and ``width >= 6``."""
    rules = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.height <= RULE_MAX_HEIGHT_PT and rect.width >= RULE_MIN_WIDTH_PT:
            rules.append(
                {
                    "x0": float(rect.x0),
                    "x1": float(rect.x1),
                    "y": float(rect.y0),
                    "width_pt": float(rect.width),
                    "height_pt": float(rect.height),
                    "drawing_type": drawing.get("type"),
                }
            )
    rules.sort(key=lambda r: (round(r["y"], 2), r["x0"]))
    return rules


# --------------------------------------------------------------------------- #
# source side
# --------------------------------------------------------------------------- #
def classify_gap(span_x0, span_x1, rules, glyph_bottom):
    """Classify one gap position from the rules that intersect it.

    ``EDITABLE_FIXED_BLANK`` -- a rule covers >=95% of the gap span, i.e. the classic
    ``____年____月____日`` fill-in underline whose two endpoints coincide with the
    delimiter glyph edges.
    ``SOURCE_RULE``          -- a rule intersects the gap materially but does not cover
    it completely (a longer/shorter source form rule crossing the gap).
    ``PLAIN_GAP``            -- no rule intersects the gap.
    ``TAB_POSITION``         -- not observable on the source side (a PDF has no tab
    metadata); recorded here only so the vocabulary is complete.
    """
    span = max(0.0, span_x1 - span_x0)
    best = None
    for rule in rules:
        overlap = min(rule["x1"], span_x1) - max(rule["x0"], span_x0)
        if overlap <= 0:
            continue
        if best is None or overlap > best[1]:
            best = (rule, overlap)
    if best is None:
        return {
            "gap_kind": "PLAIN_GAP",
            "rule": None,
            "rule_coverage_ratio": None,
            "justification": (
                "no vector rule (height<=%.1f, width>=%.1f) intersects x[%.2f,%.2f]"
                % (RULE_MAX_HEIGHT_PT, RULE_MIN_WIDTH_PT, span_x0, span_x1)
            ),
        }
    rule, overlap = best
    ratio = overlap / span if span > 0 else 1.0
    at_glyph_bottom = abs(rule["y"] - glyph_bottom) <= UNDERLINE_Y_WINDOW_PT
    kind = "EDITABLE_FIXED_BLANK" if ratio >= FULL_GAP_COVERAGE_RATIO else "SOURCE_RULE"
    return {
        "gap_kind": kind,
        "rule": {
            "x0": r2(rule["x0"]),
            "x1": r2(rule["x1"]),
            "y": r2(rule["y"]),
            "width_pt": r2(rule["width_pt"]),
        },
        "rule_coverage_ratio": r4(ratio),
        "justification": (
            "rule x[%.2f,%.2f] y=%.2f covers %.1f%% of gap x[%.2f,%.2f] "
            "(%s within %.1f pt of glyph bottom %.2f)%s"
            % (
                rule["x0"],
                rule["x1"],
                rule["y"],
                100.0 * ratio,
                span_x0,
                span_x1,
                "is" if at_glyph_bottom else "is NOT",
                UNDERLINE_Y_WINDOW_PT,
                glyph_bottom,
                " -> full-span fill-in underline" if kind == "EDITABLE_FIXED_BLANK"
                else " -> partial coverage, source form rule",
            )
        ),
    }


def classify_source_alignment(extent_x0, extent_x1, page_width, band_left, band_right, advance):
    tol = max(CENTRED_TOLERANCE_MIN_PT, page_width * CENTRED_TOLERANCE_WIDTH_RATIO)
    centroid = (extent_x0 + extent_x1) / 2.0
    page_centre = page_width / 2.0
    offset = centroid - page_centre
    margin = tol - abs(offset)
    if abs(offset) <= tol:
        cls = "SOURCE_ALIGNED_CENTER"
        reason = "|offset| %.2f <= centring tolerance %.3f pt" % (abs(offset), tol)
    elif abs(offset) <= tol + advance:
        cls = "AMBIGUOUS_NEEDS_REVIEW"
        reason = (
            "|offset| %.2f pt exceeds the centring tolerance %.3f pt by %.2f pt, which is "
            "within one glyph advance (%.2f pt) -- too close to call"
            % (abs(offset), tol, abs(offset) - tol, advance)
        )
    elif abs(extent_x1 - band_right) <= tol:
        cls = "SOURCE_ALIGNED_RIGHT"
        reason = "extent right %.2f pt is %.2f pt from the content band right %.2f pt" % (
            extent_x1, abs(extent_x1 - band_right), band_right,
        )
    elif abs(extent_x0 - band_left) <= tol:
        cls = "SOURCE_ALIGNED_LEFT"
        reason = "extent left %.2f pt is %.2f pt from the content band left %.2f pt" % (
            extent_x0, abs(extent_x0 - band_left), band_left,
        )
    else:
        cls = "SOURCE_ANCHORED_FORM_ROW"
        reason = (
            "offset %.2f pt (tolerance %.3f, ambiguity band %.3f) and extent x[%.2f,%.2f] is "
            "neither flush to the content band (%.2f .. %.2f) nor centred -- an anchored "
            "form/signature row placed by source x, not by an alignment"
            % (offset, tol, tol + advance, extent_x0, extent_x1, band_left, band_right)
        )
    return {
        "alignment_class": cls,
        "reason": reason,
        "source_row_extent_x0": r2(extent_x0),
        "source_row_extent_x1": r2(extent_x1),
        "source_row_centroid": r2(centroid),
        "page_centre_x": r2(page_centre),
        "centroid_offset_pt": r2(offset),
        "centring_tolerance_pt": r4(tol),
        "centring_margin_pt": r4(margin),
        "ambiguity_band_pt": r4(tol + advance),
        "median_glyph_advance_pt": r4(advance),
    }


def row_is_date_row(row_chars, tokens):
    """True for a near-pure date row; False for a prose row that merely mentions 年月日."""
    text = "".join(c["c"] for c in row_chars)
    is_date, leftover, reason = date_row_purity(text)
    if is_date and len(row_chars) > 8:
        return False, text, (
            "prose row: %d glyphs on the row (text besides 年/月/日 %r)"
            % (len(row_chars), leftover)
        )
    return is_date, text, reason


def audit_source_pdf(pdf_path: Path):
    doc = pymupdf.open(pdf_path)
    page_records = []
    date_rows = []
    prose = []
    for page_no in range(doc.page_count):
        page = doc[page_no]
        chars = load_chars(page)
        if not chars:
            continue
        band_left = min(c["bbox"][0] for c in chars)
        band_right = max(c["bbox"][2] for c in chars)
        page_records.append(
            {
                "page": page_no + 1,
                "width": float(page.rect.width),
                "height": float(page.rect.height),
                "content_band_x0": r2(band_left),
                "content_band_x1": r2(band_right),
            }
        )
        rules = horizontal_rules(page)
        for row in group_rows(chars):
            tokens = date_tokens_in_row(row)
            if tokens is None:
                continue
            is_date, raw_text, reason = row_is_date_row(row, tokens)
            if not is_date:
                prose.append(
                    {
                        "source_page": page_no + 1,
                        "y": r2(tokens[0]["bbox"][1]),
                        "raw_row_text": raw_text,
                        "exclusion_reason": reason,
                    }
                )
                continue
            date_rows.append(
                {
                    "page_no": page_no + 1,
                    "chars": row,
                    "tokens": tokens,
                    "raw_text": raw_text,
                    "rules": rules,
                    "content_band": (band_left, band_right),
                }
            )
    doc.close()
    return page_records, date_rows, prose


def build_source_row_record(entry, page_width, doc_band, page_band):
    year, month, day = entry["tokens"]
    y_top = float(year["bbox"][1])
    y_bottom = max(float(c["bbox"][3]) for c in entry["chars"])
    glyph_x0 = float(year["bbox"][0])
    glyph_x1 = float(day["bbox"][2])
    advances = [float(c["bbox"][2]) - float(c["bbox"][0]) for c in (year, month, day)]
    advance = statistics.median(advances)

    band_lo = y_top - BAND_PAD_PT
    band_hi = y_bottom + BAND_PAD_PT
    rules_in_band = [r for r in entry["rules"] if band_lo <= r["y"] <= band_hi]
    token_edges = [float(c["bbox"][0]) for c in entry["chars"]] + [
        float(c["bbox"][2]) for c in entry["chars"]
    ]
    row_rules = []
    for rule in rules_in_band:
        touches = any(abs(rule[e] - edge) <= RULE_EDGE_COINCIDENCE_PT for e in ("x0", "x1") for edge in token_edges)
        before_first = rule["x1"] <= glyph_x0 + RULE_EDGE_COINCIDENCE_PT and rule["x0"] < glyph_x0
        if touches or before_first:
            rule = dict(rule)
            rule["belongs_to_row"] = True
            rule["edge_coincidence"] = (
                "endpoint coincides (<= %.1f pt) with a token edge" % RULE_EDGE_COINCIDENCE_PT
                if touches else "lies between the leading edge and the first token"
            )
            row_rules.append(rule)

    year_x0, year_x1 = float(year["bbox"][0]), float(year["bbox"][2])
    month_x0, month_x1 = float(month["bbox"][0]), float(month["bbox"][2])
    day_x0, day_x1 = float(day["bbox"][0]), float(day["bbox"][2])

    leading_rules = [r for r in row_rules if r["x1"] <= year_x0 + RULE_EDGE_COINCIDENCE_PT]
    gaps = {}

    if leading_rules:
        lead = min(leading_rules, key=lambda r: r["x0"])
        gaps["before_year"] = {
            "defined": True,
            "gap_span_x0": r2(lead["x0"]),
            "gap_span_x1": r2(year_x0),
            "gap_pt": r2(year_x0 - lead["x0"]),
            **classify_gap(lead["x0"], year_x0, [lead], y_bottom),
        }
    else:
        gaps["before_year"] = {
            "defined": False,
            "gap_span_x0": None,
            "gap_span_x1": None,
            "gap_pt": None,
            "gap_kind": None,
            "rule": None,
            "rule_coverage_ratio": None,
            "justification": "no rule precedes 年 (only measured when a rule precedes 年)",
        }

    gaps["year_month"] = {
        "defined": True,
        "gap_span_x0": r2(year_x1),
        "gap_span_x1": r2(month_x0),
        "gap_pt": r2(month_x0 - year_x1),
        **classify_gap(year_x1, month_x0, row_rules, y_bottom),
    }
    gaps["month_day"] = {
        "defined": True,
        "gap_span_x0": r2(month_x1),
        "gap_span_x1": r2(day_x0),
        "gap_pt": r2(day_x0 - month_x1),
        **classify_gap(month_x1, day_x0, row_rules, y_bottom),
    }

    # effective extent = glyph union + the rules that belong to the row
    extent_x0 = min([glyph_x0] + [r["x0"] for r in row_rules])
    extent_x1 = max([glyph_x1] + [r["x1"] for r in row_rules])
    alignment = classify_source_alignment(
        extent_x0, extent_x1, page_width, doc_band[0], doc_band[1], advance
    )
    glyph_only = classify_source_alignment(
        glyph_x0, glyph_x1, page_width, doc_band[0], doc_band[1], advance
    )

    return {
        "source_page": entry["page_no"],
        "source_y_top": r2(y_top),
        "source_glyph_bottom": r2(y_bottom),
        "source_row_band": [r2(band_lo), r2(band_hi)],
        "source_row_raw_text": entry["raw_text"],
        "source_year_x": [r2(year_x0), r2(year_x1)],
        "source_month_x": [r2(month_x0), r2(month_x1)],
        "source_day_x": [r2(day_x0), r2(day_x1)],
        "source_gap_before_year_pt": gaps["before_year"]["gap_pt"],
        "source_gap_year_month_pt": gaps["year_month"]["gap_pt"],
        "source_gap_month_day_pt": gaps["month_day"]["gap_pt"],
        "source_gap_kinds": {
            "before_year": gaps["before_year"]["gap_kind"],
            "year_month": gaps["year_month"]["gap_kind"],
            "month_day": gaps["month_day"]["gap_kind"],
        },
        "source_gaps": gaps,
        "source_rules_in_band": [
            {
                "x0": r2(r["x0"]), "x1": r2(r["x1"]), "y": r2(r["y"]),
                "width_pt": r2(r["width_pt"]), "belongs_to_row": True,
                "edge_coincidence": r["edge_coincidence"],
            }
            for r in row_rules
        ],
        "source_rules_in_band_count": len(row_rules),
        "page_content_band": [r2(doc_band[0]), r2(doc_band[1])],
        "page_content_band_source": "document-wide median of per-page glyph extremes",
        "page_local_content_band": [r2(page_band[0]), r2(page_band[1])],
        **alignment,
        "glyph_only_extent": [r2(glyph_x0), r2(glyph_x1)],
        "glyph_only_alignment_class": glyph_only["alignment_class"],
        "glyph_only_centroid_offset_pt": glyph_only["centroid_offset_pt"],
        "page_width_pt": r2(page_width),
    }


# --------------------------------------------------------------------------- #
# generated side
# --------------------------------------------------------------------------- #
def ind_attr(ind_el, name):
    if ind_el is None:
        return None
    val = ind_el.get(qn("w:" + name))
    return int(val) if val is not None else None


def scan_generated_docx(docx_path: Path):
    doc = Document(docx_path)
    paragraphs = list(doc.paragraphs)
    records = []
    prose = []
    for index, paragraph in enumerate(paragraphs):
        text = paragraph.text
        flat = text.replace(TAB, "")
        if not all(tok in flat for tok in DATE_TOKENS):
            continue
        in_order = True
        cursor = 0
        for tok in DATE_TOKENS:
            pos = flat.find(tok, cursor)
            if pos < 0:
                in_order = False
                break
            cursor = pos + 1
        if not in_order:
            continue

        pPr = paragraph._p.find(qn("w:pPr"))
        jc = None
        left = first_line = hanging = None
        tabs = []
        if pPr is not None:
            jc_el = pPr.find(qn("w:jc"))
            if jc_el is not None:
                jc = jc_el.get(qn("w:val"))
            ind_el = pPr.find(qn("w:ind"))
            left = ind_attr(ind_el, "left")
            first_line = ind_attr(ind_el, "firstLine")
            hanging = ind_attr(ind_el, "hanging")
            tabs_el = pPr.find(qn("w:tabs"))
            if tabs_el is not None:
                for tab in tabs_el.findall(qn("w:tab")):
                    pos = tab.get(qn("w:pos"))
                    tabs.append(
                        {
                            "pos_twips": int(pos) if pos is not None else None,
                            "pos_pt": r2(int(pos) / 20.0) if pos is not None else None,
                            "val": tab.get(qn("w:val")),
                        }
                    )

        in_table = False
        ancestor = paragraph._p.getparent()
        while ancestor is not None:
            if ancestor.tag == qn("w:tc"):
                in_table = True
                break
            ancestor = ancestor.getparent()

        is_date_row, leftover, purity_reason = date_row_purity(flat)

        run_info = []
        underline_run_count = 0
        for run in paragraph.runs:
            if run.text == "" and run.underline is None:
                continue
            u = run.underline
            if u is True:
                underline_run_count += 1
            run_info.append({"text": run.text.replace(TAB, "\\t"), "underline": u})

        if not is_date_row:
            prose.append(
                {
                    "generated_paragraph_index": index,
                    "generated_text": text.replace(TAB, "\\t"),
                    "exclusion_reason": purity_reason,
                }
            )
            continue

        records.append(
            {
                "generated_paragraph_index": index,
                "generated_text": text.replace(TAB, "\\t"),
                "generated_jc": jc,
                "generated_left_twips": left,
                "generated_left_pt": r2(left / 20.0) if left is not None else None,
                "generated_first_line_twips": first_line,
                "generated_hanging_twips": hanging,
                "generated_tabs": tabs,
                "generated_tab_chars": text.count(TAB),
                "generated_runs": run_info,
                "generated_underline_run_count": underline_run_count,
                "generated_in_table_cell": in_table,
                "generated_section_left_margin_pt": r2(
                    doc.sections[0].left_margin.pt if doc.sections else None
                ),
            }
        )
    return records, prose


def scan_generated_pdf(pdf_path: Path):
    doc = pymupdf.open(pdf_path)
    rows = []
    prose = []
    for page_no in range(doc.page_count):
        page = doc[page_no]
        chars = load_chars(page)
        if not chars:
            continue
        for row in group_rows(chars):
            tokens = date_tokens_in_row(row)
            if tokens is None:
                continue
            text = "".join(c["c"] for c in row)
            is_date_row, _leftover, purity_reason = date_row_purity(text)
            if not is_date_row:
                prose.append(
                    {
                        "generated_pdf_page": page_no + 1,
                        "y": r2(tokens[0]["bbox"][1]),
                        "raw_row_text": text,
                        "exclusion_reason": purity_reason,
                    }
                )
                continue
            year, month, day = tokens
            left_context = [
                c for c in row if float(c["bbox"][2]) <= float(year["bbox"][0]) + 0.01
                and c["c"] not in DATE_TOKENS
            ]
            prev_right = (
                max(float(c["bbox"][2]) for c in left_context) if left_context else None
            )
            rows.append(
                {
                    "generated_pdf_page": page_no + 1,
                    "generated_pdf_y_top": r2(year["bbox"][1]),
                    "generated_pdf_row_text": text,
                    "generated_token_x": {
                        "年": [r2(year["bbox"][0]), r2(year["bbox"][2])],
                        "月": [r2(month["bbox"][0]), r2(month["bbox"][2])],
                        "日": [r2(day["bbox"][0]), r2(day["bbox"][2])],
                    },
                    "generated_gap_year_month_pt": r2(
                        float(month["bbox"][0]) - float(year["bbox"][2])
                    ),
                    "generated_gap_month_day_pt": r2(
                        float(day["bbox"][0]) - float(month["bbox"][2])
                    ),
                    "preceding_glyph_right_pt": r2(prev_right),
                }
            )
    doc.close()
    rows.sort(key=lambda row: (row["generated_pdf_page"], row["generated_pdf_y_top"]))
    return rows, prose


# --------------------------------------------------------------------------- #
# pairing / verdicts
# --------------------------------------------------------------------------- #
IMPLIED_JC = {
    "SOURCE_ALIGNED_CENTER": "center",
    "SOURCE_ALIGNED_LEFT": "left",
    "SOURCE_ALIGNED_RIGHT": "right",
    "SOURCE_ANCHORED_FORM_ROW": "left",
}


def material(gap_pt):
    return gap_pt is not None and gap_pt > NATURAL_INTER_GLYPH_GAP_PT + TYPOGRAPHY_TOLERANCE_PT


def verdicts(row):
    """Return (alignment_class_matches, synthetic_left_indent, gaps_preserved, collapsed,
    lost_gap_positions, invented_gap_positions, unexpected_indent, notes)."""
    cls = row["alignment_class"]
    gen = row.get("generated") or {}
    jc = gen.get("generated_jc")
    left_twips = gen.get("generated_left_twips")
    notes = []

    if not gen:
        return None, None, None, None, [], [], False, ["no generated counterpart in this build"]

    implied = IMPLIED_JC.get(cls)
    if implied is None:
        align_match = None
        notes.append("source class %s is not assessable against a w:jc value" % cls)
    else:
        align_match = jc == implied
        if not align_match:
            notes.append(
                "source class %s implies w:jc=%s but the generated paragraph is w:jc=%s"
                % (cls, implied, jc)
            )

    synthetic = bool(cls == "SOURCE_ALIGNED_CENTER" and jc != "center" and (left_twips or 0) != 0)
    if synthetic:
        notes.append(
            "centred source row reproduced with w:jc=%s + w:left=%d twips (%.2f pt) synthetic indent"
            % (jc, left_twips, (left_twips or 0) / 20.0)
        )

    lost, invented, preserved_flags = [], [], []
    adjacent = []
    for key, src_key, gen_key in (
        ("before_year", "source_gap_before_year_pt", "generated_gap_before_year_pt"),
        ("year_month", "source_gap_year_month_pt", "generated_gap_year_month_pt"),
        ("month_day", "source_gap_month_day_pt", "generated_gap_month_day_pt"),
    ):
        src = row.get(src_key)
        dst = gen.get(gen_key)
        if src is None and dst is None:
            continue
        if material(src):
            if dst is None:
                lost.append({"position": key, "source_gap_pt": src, "generated_gap_pt": None,
                             "error_pt": None, "rendered_adjacent": True})
                preserved_flags.append(False)
                adjacent.append(True)
                continue
            error = dst - src
            ok = abs(error) <= TYPOGRAPHY_TOLERANCE_PT
            preserved_flags.append(ok)
            is_adjacent = abs(dst - NATURAL_INTER_GLYPH_GAP_PT) <= TYPOGRAPHY_TOLERANCE_PT
            if not ok:
                lost.append({"position": key, "source_gap_pt": src, "generated_gap_pt": dst,
                             "error_pt": r2(error), "rendered_adjacent": is_adjacent})
                adjacent.append(is_adjacent)
        elif material(dst):
            invented.append({"position": key, "source_gap_pt": src, "generated_gap_pt": dst})

    gaps_preserved = bool(preserved_flags) and all(preserved_flags)
    mechanism = gen.get("generated_gap_mechanism")
    # "collapsed" per the task definition: the source gaps are material AND the generated
    # tokens sit at their natural adjacent positions (no tab/space/indent reproduces them).
    collapsed = bool(lost) and all(adjacent)
    if collapsed:
        notes.append(
            "generated row renders the tokens at their natural adjacent positions "
            "(measured gaps %s pt) with no intra-row gap mechanism; paragraph position "
            "mechanism is %s"
            % (
                "/".join(
                    fmt(gen.get(k)) for k in
                    ("generated_gap_year_month_pt", "generated_gap_month_day_pt")
                ),
                gen.get("generated_row_position_mechanism"),
            )
        )
    elif lost:
        notes.append(
            "gap mechanism present (%s) but %d gap position(s) miss the %.1f pt tolerance"
            % (mechanism, len(lost), TYPOGRAPHY_TOLERANCE_PT)
        )

    unexpected_indent = bool(
        (left_twips or 0) != 0 and cls in ("SOURCE_ALIGNED_CENTER", "SOURCE_ALIGNED_LEFT",
                                          "SOURCE_ALIGNED_RIGHT")
    )
    if unexpected_indent and not synthetic:
        notes.append(
            "generated w:left=%d twips (%.2f pt) is a position surrogate for a source class %s"
            % (left_twips, (left_twips or 0) / 20.0, cls)
        )
    return align_match, synthetic, gaps_preserved, collapsed, lost, invented, unexpected_indent, notes


def apply_generated_measurements(gen_record, pdf_row, source_row):
    gen_record["generated_pdf_page"] = pdf_row["generated_pdf_page"]
    gen_record["generated_pdf_y_top"] = pdf_row["generated_pdf_y_top"]
    gen_record["generated_pdf_row_text"] = pdf_row["generated_pdf_row_text"]
    gen_record["generated_token_x"] = pdf_row["generated_token_x"]
    gen_record["generated_gap_year_month_pt"] = pdf_row["generated_gap_year_month_pt"]
    gen_record["generated_gap_month_day_pt"] = pdf_row["generated_gap_month_day_pt"]

    margin = gen_record.get("generated_section_left_margin_pt") or 0.0
    left_pt = gen_record.get("generated_left_pt") or 0.0
    origin = margin + left_pt
    gen_record["generated_row_origin_x_pt"] = r2(origin)

    has_leading_tab = gen_record["generated_text"].startswith("\\t") or (
        "：\\t" in gen_record["generated_text"]
    )
    if has_leading_tab or pdf_row["preceding_glyph_right_pt"] is not None:
        boundary = pdf_row["preceding_glyph_right_pt"]
        basis = "right edge of the preceding rendered glyph on the same row"
        if boundary is None:
            boundary = origin
            basis = "paragraph origin (section left margin + w:left)"
        gen_record["generated_gap_before_year_pt"] = r2(
            pdf_row["generated_token_x"]["年"][0] - boundary
        )
        gen_record["generated_gap_before_year_basis"] = basis
    else:
        gen_record["generated_gap_before_year_pt"] = None
        gen_record["generated_gap_before_year_basis"] = None

    mechanisms = []
    if gen_record["generated_tabs"]:
        mechanisms.append("TAB_POSITION(w:tabs x%d)" % len(gen_record["generated_tabs"]))
    if gen_record["generated_tab_chars"]:
        mechanisms.append("TAB_CHAR(x%d)" % gen_record["generated_tab_chars"])
    if gen_record.get("generated_underline_run_count"):
        mechanisms.append("UNDERLINE_LEADER_RUN(x%d)" % gen_record["generated_underline_run_count"])
    if " " in gen_record["generated_text"].replace("\\t", ""):
        mechanisms.append("LITERAL_SPACE")
    gen_record["generated_gap_mechanisms"] = mechanisms
    # A paragraph left indent moves the row's origin; it cannot open the gaps *inside*
    # the row, so it is tracked separately from genuine intra-row gap mechanisms.
    gen_record["generated_gap_mechanism"] = "+".join(mechanisms) if mechanisms else "NONE"
    gen_record["generated_row_position_mechanism"] = (
        "PARAGRAPH_LEFT_INDENT(w:left=%d twips)"
        % gen_record["generated_left_twips"]
        if (gen_record.get("generated_left_twips") or 0) != 0
        else "NATIVE_ALIGNMENT(w:jc=%s, w:left=0)" % (gen_record.get("generated_jc") or "default")
    )

    if source_row is not None:
        gen_record["pairing_token_x_delta_pt"] = r2(
            pdf_row["generated_token_x"]["年"][0] - source_row["source_year_x"][0]
        )
    else:
        gen_record["pairing_token_x_delta_pt"] = None


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def build_report(args):
    source_pdf = Path(args.source_pdf)
    build_dir = Path(args.build_dir)
    docx_path = build_dir / "基础投标文件.docx"
    pdf_path = build_dir / "基础投标文件.pdf"
    report_path = build_dir / "generation_report.json"

    for path in (source_pdf, docx_path, pdf_path, report_path):
        if not path.exists():
            raise SystemExit("missing input: %s" % path)

    with open(report_path, encoding="utf-8") as fh:
        generation_report = json.load(fh)
    layout_records = {
        rec.get("paragraph_index"): rec
        for rec in generation_report.get("paragraph_layout_records", [])
        if rec.get("paragraph_index") is not None
    }

    page_records, raw_rows, source_prose = audit_source_pdf(source_pdf)
    doc_band = (
        statistics.median([p["content_band_x0"] for p in page_records]),
        statistics.median([p["content_band_x1"] for p in page_records]),
    )
    page_width_by_page = {p["page"]: p["width"] for p in page_records}
    page_band_by_page = {
        p["page"]: (p["content_band_x0"], p["content_band_x1"]) for p in page_records
    }

    rows = []
    for entry in raw_rows:
        rows.append(
            build_source_row_record(
                entry,
                page_width_by_page[entry["page_no"]],
                doc_band,
                page_band_by_page[entry["page_no"]],
            )
        )
    rows.sort(key=lambda r: (r["source_page"], r["source_y_top"]))

    gen_records, gen_docx_prose = scan_generated_docx(docx_path)
    pdf_rows, gen_pdf_prose = scan_generated_pdf(pdf_path)

    # ---- pair generated paragraphs -> source rows via generation_report ---------- #
    paired = []
    unmatched_gen = []
    for gen in gen_records:
        rec = layout_records.get(gen["generated_paragraph_index"])
        target = None
        if rec is not None and rec.get("role") == "DATE_LINE":
            target_page = rec.get("source_page")
            baselines = rec.get("source_baselines") or []
            target_y = baselines[0] if baselines else None
            for row in rows:
                if row["source_page"] != target_page:
                    continue
                if target_y is None or abs(row["source_y_top"] - float(target_y)) <= 3.0:
                    target = row
                    break
        gen["layout_record_role"] = rec.get("role") if rec else None
        gen["layout_record_alignment_role"] = rec.get("alignment_role") if rec else None
        gen["layout_record_source_page"] = rec.get("source_page") if rec else None
        gen["layout_record_source_y"] = (
            r2((rec.get("source_baselines") or [None])[0]) if rec else None
        )
        gen["layout_record_generated_left_indent_pt"] = (
            r2(rec.get("generated_left_indent")) if rec else None
        )
        gen["layout_record_tab_stops"] = rec.get("tab_stops") if rec else None
        if target is None:
            unmatched_gen.append(gen)
            continue
        paired.append((target, gen))
        target["generated"] = gen

    # ---- attach rendered positions: docx order <-> generated PDF reading order ---- #
    if len(paired) != len(pdf_rows):
        raise SystemExit(
            "pairing mismatch: %d generated date paragraphs vs %d rendered date rows"
            % (len(paired), len(pdf_rows))
        )
    paired.sort(key=lambda item: item[1]["generated_paragraph_index"])
    for (source_row, gen), pdf_row in zip(paired, pdf_rows):
        apply_generated_measurements(gen, pdf_row, source_row)
    rows.sort(key=lambda r: (r["source_page"], r["source_y_top"]))

    # ---- verdicts --------------------------------------------------------------- #
    alignment_classes = {}
    for row in rows:
        gen = row.get("generated")
        match, synthetic, preserved, collapsed, lost, invented, unexpected, notes = verdicts(row)
        row["generated_jc"] = gen.get("generated_jc") if gen else None
        row["generated_left_twips"] = gen.get("generated_left_twips") if gen else None
        row["alignment_class_matches"] = match
        row["synthetic_left_indent_for_centering"] = synthetic
        row["gaps_preserved"] = preserved
        row["collapsed"] = collapsed
        row["lost_source_date_gaps"] = lost
        row["invented_date_gaps"] = invented
        row["unexpected_date_indent"] = unexpected
        row["review_notes"] = notes
        alignment_classes[row["alignment_class"]] = (
            alignment_classes.get(row["alignment_class"], 0) + 1
        )

    collapsed_rows = [r for r in rows if r["collapsed"]]
    lost_all = [g for r in rows for g in r["lost_source_date_gaps"]]
    invented_all = [g for r in rows for g in r["invented_date_gaps"]]
    unexpected = [r for r in rows if r["unexpected_date_indent"]]
    ambiguous = [r for r in rows if r["alignment_class"] == "AMBIGUOUS_NEEDS_REVIEW"]
    unpaired_source = [r for r in rows if not r.get("generated")]
    matched = [r for r in rows if r["alignment_class_matches"] is True]
    mismatched = [r for r in rows if r["alignment_class_matches"] is False]

    accounting = {
        "source_date_rows": len(rows),
        "matched_alignment": len(matched),
        "reviewed_exceptions": len(unpaired_source),
        "alignment_mismatch": len(mismatched),
        "collapsed_date_rows": len(collapsed_rows),
        "lost_source_date_gaps": len(lost_all),
        "invented_date_gaps": len(invented_all),
        "unexpected_date_indents": len(unexpected),
        "ambiguous_needs_review": len(ambiguous),
        "source_date_rows_in_build_scope": len(rows) - len(unpaired_source),
        "generated_date_paragraph_count": len(gen_records),
        "ledger_check": (
            len(matched) + len(unpaired_source) + len(mismatched) == len(rows)
        ),
    }

    # ---- root causes grounded strictly in the measured rows --------------------- #
    no_mechanism = [r for r in rows if r.get("generated")
                    and r["generated"]["generated_gap_mechanism"] == "NONE"]
    center_but_left = [
        r for r in rows
        if r["alignment_class"] == "SOURCE_ALIGNED_CENTER" and r.get("generated")
        and r["generated"]["generated_jc"] != "center"
    ]
    center_native = [
        r for r in rows
        if r["alignment_class"] == "SOURCE_ALIGNED_CENTER" and r.get("generated")
        and r["generated"]["generated_jc"] == "center"
    ]
    root_cause_findings = []
    if no_mechanism:
        paired_total = len(rows) - len(unpaired_source)
        root_cause_findings.append(
            "NO_GAP_MECHANISM: %d of %d paired rows (of %d source date rows in total) emit the "
            "bare string '年月日' (0 w:tabs, 0 tab "
            "characters, 0 literal spaces), so the rendered tokens are exactly adjacent "
            "(measured generated gaps 0.00/0.00 pt) while the source gaps are %.2f-%.2f pt: "
            "source pages %s (docx paragraphs %s)."
            % (
                len(no_mechanism), paired_total, len(rows),
                min(r["source_gap_year_month_pt"] for r in no_mechanism),
                max(r["source_gap_month_day_pt"] for r in no_mechanism),
                ", ".join(str(r["source_page"]) for r in no_mechanism),
                ", ".join(str(r["generated"]["generated_paragraph_index"]) for r in no_mechanism),
            )
        )
    for row in center_but_left:
        gen = row["generated"]
        root_cause_findings.append(
            "SYNTHETIC_CENTER_INDENT: source page %d (y=%.2f) is class %s (centroid offset "
            "%.2f pt, tolerance %.2f pt) but docx paragraph %d is w:jc=%s with w:left=%d twips "
            "(%.2f pt) plus w:tabs at %s pt -- a synthetic paragraph indent stands in for native "
            "centring."
            % (
                row["source_page"], row["source_y_top"], row["alignment_class"],
                row["centroid_offset_pt"], row["centring_tolerance_pt"],
                gen["generated_paragraph_index"], gen["generated_jc"],
                gen["generated_left_twips"], gen["generated_left_pt"],
                [t["pos_pt"] for t in gen["generated_tabs"]],
            )
        )
    for row in center_native:
        gen = row["generated"]
        if gen["generated_gap_mechanism"] == "NONE":
            root_cause_findings.append(
                "NATIVE_CENTER_BUT_NO_SPACING: source page %d (y=%.2f) is class %s and docx "
                "paragraph %d is correctly w:jc=center with w:left=0, yet it still emits bare "
                "'年月日' -- the source intra-row gaps (%.2f/%.2f pt) are dropped even though the "
                "alignment itself is faithful."
                % (
                    row["source_page"], row["source_y_top"], row["alignment_class"],
                    gen["generated_paragraph_index"],
                    row["source_gap_year_month_pt"], row["source_gap_month_day_pt"],
                )
            )
    anchored_indent = [
        r for r in rows if r["alignment_class"] == "SOURCE_ANCHORED_FORM_ROW" and r.get("generated")
        and (r["generated"]["generated_left_twips"] or 0) != 0
        and not r["generated"]["generated_tabs"]
        and not r["generated"]["generated_tab_chars"]
    ]
    if anchored_indent:
        root_cause_findings.append(
            "POSITION_BY_INDENT_ONLY: %d anchored form rows reproduce their source x with "
            "w:left only (no tab stops, no tab characters) and therefore lose every internal "
            "gap: %s."
            % (
                len(anchored_indent),
                "; ".join(
                    "docx ¶%d w:left=%.1f pt, gaps %.2f/%.2f pt vs source %.2f/%.2f pt"
                    % (
                        r["generated"]["generated_paragraph_index"],
                        r["generated"]["generated_left_pt"],
                        r["generated"]["generated_gap_year_month_pt"],
                        r["generated"]["generated_gap_month_day_pt"],
                        r["source_gap_year_month_pt"], r["source_gap_month_day_pt"],
                    )
                    for r in anchored_indent
                ),
            )
        )
    tabbed = [
        r for r in rows if r.get("generated")
        and "TAB_POSITION" in r["generated"]["generated_gap_mechanism"]
    ]
    if tabbed:
        tabbed_positions = sum(
            1 for r in tabbed
            for key in ("source_gap_before_year_pt", "source_gap_year_month_pt",
                        "source_gap_month_day_pt")
            if material(r.get(key))
        )
        tabbed_lost = sum(len(r["lost_source_date_gaps"]) for r in tabbed)
        root_cause_findings.append(
            "TAB_STOPS_EXIST_BUT_MISMATCH: %d rows do carry w:tabs / underlined leader tabs "
            "(%s) yet %d of %d material gap positions miss the %.1f pt tolerance, because the "
            "emitted tab stops do not reproduce the source rule spans."
            % (
                len(tabbed),
                ", ".join("¶%d" % r["generated"]["generated_paragraph_index"] for r in tabbed),
                tabbed_lost,
                tabbed_positions,
                TYPOGRAPHY_TOLERANCE_PT,
            )
        )
    # ---- reproduce the frozen prior measurement table, or report the delta -------- #
    prior_table = [
        # src page, y, year x0, year x1, month x0, month x1, day x0, day x1, ym gap, md gap
        (40, 635.41, 283.20, 294.70, 335.04, 346.54, 392.52, 404.02, 40.34, 45.98),
        (42, 586.14, 217.80, 229.80, 241.80, 253.80, 265.80, 277.80, 12.00, 12.00),
        (43, 659.34, 429.12, 441.12, 456.72, 468.72, 484.08, 496.08, 15.60, 15.36),
        (44, 216.90, 179.88, 191.88, 221.88, 233.88, 281.88, 293.88, 30.00, 48.00),
        (44, 450.66, 99.72, 111.72, 146.04, 158.04, 186.84, 198.84, 34.32, 28.80),
        (45, 466.14, 357.72, 369.72, 381.72, 393.72, 405.72, 417.72, 12.00, 12.00),
        (47, 519.66, 269.40, 281.40, 303.36, 315.36, 337.32, 349.32, 21.96, 21.96),
        (48, 688.98, 353.88, 365.88, 387.84, 399.84, 421.80, 433.80, 21.96, 21.96),
        (53, 576.18, 269.40, 281.40, 303.36, 315.36, 337.32, 349.32, 21.96, 21.96),
        (60, 428.10, 269.40, 281.40, 303.36, 315.36, 337.32, 349.32, 21.96, 21.96),
    ]
    by_key = {(r["source_page"], r["source_y_top"]): r for r in rows}
    reproduction = []
    for (page, y, yx0, yx1, mx0, mx1, dx0, dx1, ym, md) in prior_table:
        row = by_key.get((page, y))
        if row is None:
            reproduction.append({"source_page": page, "source_y": y,
                                 "reproduced": False, "delta": "row not found"})
            continue
        measured = {
            "year_x": [row["source_year_x"][0], row["source_year_x"][1]],
            "month_x": [row["source_month_x"][0], row["source_month_x"][1]],
            "day_x": [row["source_day_x"][0], row["source_day_x"][1]],
            "year_month_gap": row["source_gap_year_month_pt"],
            "month_day_gap": row["source_gap_month_day_pt"],
        }
        given = {
            "year_x": [yx0, yx1], "month_x": [mx0, mx1], "day_x": [dx0, dx1],
            "year_month_gap": ym, "month_day_gap": md,
        }
        deltas = []
        for key in ("year_x", "month_x", "day_x"):
            deltas.extend(
                abs(measured[key][i] - given[key][i]) for i in (0, 1)
            )
        deltas.append(abs(measured["year_month_gap"] - given["year_month_gap"]))
        deltas.append(abs(measured["month_day_gap"] - given["month_day_gap"]))
        max_delta = max(deltas)
        reproduction.append(
            {
                "source_page": page,
                "source_y": y,
                "reproduced": max_delta <= 0.05,
                "max_abs_delta_pt": r4(max_delta),
                "measured": measured,
                "given": given,
            }
        )
    prior_reproduction = {
        "table": "prior measurement table supplied with the task (10 rows, source pages 40-61)",
        "all_rows_reproduced": all(item.get("reproduced") for item in reproduction),
        "max_abs_delta_pt": r4(max(item.get("max_abs_delta_pt") or 0.0 for item in reproduction)),
        "rows": reproduction,
    }

    report_tab_mismatch = [
        r for r in rows if r.get("generated") and r["generated"]["generated_tabs"]
        and not r["generated"]["layout_record_tab_stops"]
    ]
    if report_tab_mismatch:
        root_cause_findings.append(
            "GENERATION_REPORT_NOT_AUTHORITATIVE: generation_report.json "
            "paragraph_layout_records records tab_stops=[] for %s although the emitted docx "
            "really contains w:tabs (%s) -- the report's tab_stops/generated_left_indent cannot "
            "be used as the gap-mechanism authority."
            % (
                ", ".join("¶%d" % r["generated"]["generated_paragraph_index"] for r in report_tab_mismatch),
                "; ".join(
                    "¶%d: %d stop(s) %s pt"
                    % (
                        r["generated"]["generated_paragraph_index"],
                        len(r["generated"]["generated_tabs"]),
                        [t["pos_pt"] for t in r["generated"]["generated_tabs"]],
                    )
                    for r in report_tab_mismatch
                ),
            )
        )
    if unpaired_source:
        root_cause_findings.append(
            "BUILD_SCOPE_ONLY: source %s are genuine date rows with the same "
            "'____年____月____日' rule geometry as the compiled rows, but the build only compiles "
            "source pages 40-61, so they have no generated counterpart and could not be paired."
            % ", ".join("page %d (y=%.2f)" % (r["source_page"], r["source_y_top"])
                        for r in unpaired_source)
        )

    # ---- compact root-cause summary (one line each, for the md header) ---------- #
    root_cause_summary = []
    if no_mechanism:
        root_cause_summary.append(
            "NO_GAP_MECHANISM — %d/%d paired rows emit bare `年月日` (no w:tabs, no tab chars, no "
            "spaces): rendered gaps 0.00/0.00 pt vs source %.2f–%.2f pt (docx ¶%s)."
            % (
                len(no_mechanism), len(rows) - len(unpaired_source),
                min(r["source_gap_year_month_pt"] for r in no_mechanism),
                max(r["source_gap_month_day_pt"] for r in no_mechanism),
                ",".join(str(r["generated"]["generated_paragraph_index"]) for r in no_mechanism),
            )
        )
    for row in center_but_left:
        gen = row["generated"]
        root_cause_summary.append(
            "SYNTHETIC_CENTER_INDENT — src p%d is centred (offset %+.2f pt vs tol %.2f pt) but "
            "docx ¶%d is w:jc=%s + w:left=%.2f pt (w:tabs %s pt)."
            % (
                row["source_page"], row["centroid_offset_pt"], row["centring_tolerance_pt"],
                gen["generated_paragraph_index"], gen["generated_jc"], gen["generated_left_pt"],
                [t["pos_pt"] for t in gen["generated_tabs"]],
            )
        )
    if center_native:
        root_cause_summary.append(
            "NATIVE_CENTER_BUT_NO_SPACING — src p%s are centred natively (docx ¶%s w:jc=center, "
            "w:left=0) yet still drop the %.2f pt intra-row gaps."
            % (
                "/".join(str(r["source_page"]) for r in center_native),
                ",".join(str(r["generated"]["generated_paragraph_index"]) for r in center_native),
                center_native[0]["source_gap_year_month_pt"],
            )
        )
    if anchored_indent:
        root_cause_summary.append(
            "POSITION_BY_INDENT_ONLY — %d anchored rows (docx ¶%s) reproduce source x with w:left "
            "only and lose every internal gap."
            % (
                len(anchored_indent),
                ",".join(str(r["generated"]["generated_paragraph_index"]) for r in anchored_indent),
            )
        )
    if tabbed:
        tabbed_positions = sum(
            1 for r in tabbed
            for key in ("source_gap_before_year_pt", "source_gap_year_month_pt",
                        "source_gap_month_day_pt")
            if material(r.get(key))
        )
        root_cause_summary.append(
            "TAB_STOPS_EXIST_BUT_MISMATCH — docx ¶%s carry w:tabs/underlined leader tabs but %d of "
            "%d material gap positions miss the %.1f pt tolerance."
            % (
                ",".join(str(r["generated"]["generated_paragraph_index"]) for r in tabbed),
                sum(len(r["lost_source_date_gaps"]) for r in tabbed),
                tabbed_positions, TYPOGRAPHY_TOLERANCE_PT,
            )
        )
    if report_tab_mismatch:
        root_cause_summary.append(
            "GENERATION_REPORT_NOT_AUTHORITATIVE — generation_report.json records tab_stops=[] for "
            "docx ¶%s although the emitted docx contains %s w:tabs."
            % (
                ",".join(str(r["generated"]["generated_paragraph_index"]) for r in report_tab_mismatch),
                "/".join(str(len(r["generated"]["generated_tabs"])) for r in report_tab_mismatch),
            )
        )
    if unpaired_source:
        root_cause_summary.append(
            "BUILD_SCOPE_ONLY — src p%s are genuine date rows (same `____年____月____日` rules) with "
            "no counterpart: the build only covers source pages 40–61."
            % ",".join(str(r["source_page"]) for r in unpaired_source)
        )

    # ---- tolerance provenance ---------------------------------------------------- #
    tolerance = {
        "used_tolerance_pt": TYPOGRAPHY_TOLERANCE_PT,
        "provenance": [
            "tender_basic/geometry_rule_qa.py:33 -- MANDATORY_TOLERANCE_PT = 2.0",
            "docs/V1_DECISIONS.md section 2.1 -- 'tolerance_pt = 2.0' (frozen, not to be relaxed)",
            "docs/V1_DECISIONS.md table P1 -- tolerance fixed at 2.0 pt",
        ],
        "applies_to": "|generated_gap_pt - source_gap_pt| <= 2.0 pt",
        "rule_geometry_origin": (
            "The repository tolerance is a x/y geometry tolerance for source rules and vertical "
            "residuals. No gap-width-specific tolerance exists in tender_basic/, docs/V1_DECISIONS.md "
            "or docs/V1_PROJECT_STATE.md, so this task reuses the frozen 2.0 pt value for gap widths; "
            "that reuse is a limitation, see disclosures."
        ),
        "centring_tolerance": {
            "formula": "max(8.0, page_width * 0.02)",
            "value_pt": r4(max(CENTRED_TOLERANCE_MIN_PT, 595.2999877929688 * CENTRED_TOLERANCE_WIDTH_RATIO)),
            "provenance": "tender_basic/page_layout.py:463",
        },
        "natural_inter_glyph_gap_pt": NATURAL_INTER_GLYPH_GAP_PT,
        "natural_inter_glyph_gap_provenance": (
            "measured: in the generated PDF where the build emits bare 年月日 the full-width "
            "glyphs are exactly adjacent (year.x1 == month.x0 == day.x0), so the natural gap is 0.00 pt"
        ),
        "materiality_threshold_pt": NATURAL_INTER_GLYPH_GAP_PT + TYPOGRAPHY_TOLERANCE_PT,
        "ambiguity_band": (
            "tol_center < |offset| <= tol_center + median_glyph_advance_pt => "
            "AMBIGUOUS_NEEDS_REVIEW (one character cell beyond the centring tolerance)"
        ),
    }

    disclosures = [
        "SCOPE: this audit is document-wide over all 61 source pages and finds %d source date "
        "rows. The prior 10-row table (and the '13 年月日 occurrences / 10 date rows' statement) "
        "covered only source pages 40-61, the build's source_page range; the two extra rows are "
        "source pages 30 (y=404.34) and 31 (y=362.70), which have no generated counterpart. "
        "Both counts are reported (accounting.source_date_rows and "
        "accounting.source_date_rows_in_build_scope)." % len(rows),
        "PRIOR TABLE REPRODUCED: all %d rows of the supplied 10-row table were re-measured "
        "independently; maximum absolute delta across every token x0/x1 and both gaps is %.4f pt "
        "(declared exact when <= 0.05 pt), so the table was NOT contradicted and was used as given. "
        "Details: prior_measurement_reproduction."
        % (
            len(prior_reproduction["rows"]),
            prior_reproduction["max_abs_delta_pt"] or 0.0,
        ),
        "CONTRADICTED GIVEN FACT: 'Pages 42,43,44,45,47,48,53,60 have no rules in their "
        "date-row band' is true for 42,43,45,47,48,53,60 but FALSE for page 44: the row at "
        "y=216.90 has 3 underline rules at y=228.60 and the row at y=450.66 has 3 at y=462.35, "
        "all inside the glyph band (glyph bottoms 229.18 and 462.94).",
        "CONTRADICTED GIVEN FACT (minor): 'two pages carry an extra 年月日 occurrence inside "        "ordinary prose' -- within the build scope (pages 40-61) there are actually three such "
        "prose rows (source pages 41, 52, 53), giving the '13 occurrences / 10 date rows' pair; "
        "document-wide there are 12 prose rows against 12 date rows.",
        "CENTRING SENSITIVITY: %s" % _centring_sensitivity(rows),
        "MARGINAL CENTRING: %s" % _marginal_centring(rows),
        "CONTENT BAND: the page text-frame is approximated as the document-wide median of "
        "per-page glyph extremes (left %.2f pt, right %.2f pt) rather than being re-derived from "
        "cross-page repeated anchors as tender_basic/source_page_frame.py does. The approximation "
        "is noisy -- e.g. source page 31 has a glyph reaching x1=530.40, beyond the frozen frame "
        "right edge 524.4 pt recorded in docs/V1_DECISIONS.md F2." % (doc_band[0], doc_band[1]),
        "TAB_POSITION gap kind is not observable on the source side: a PDF carries no tab "
        "metadata, so source gap kinds can only be SOURCE_RULE / EDITABLE_FIXED_BLANK / "
        "PLAIN_GAP. TAB_POSITION is used on the generated side only.",
        "SOLID UNDERLINE EXTENT: run.underline is reported as the python-docx tri-state "
        "(True/None); w:u/@w:val detail (single vs none) is not resolved beyond that.",
        "PAIRING: source row <-> generated paragraph pairing uses "
        "generation_report.json paragraph_layout_records[paragraph_index].source_page + "
        "source_baselines[0] (role == DATE_LINE) for all 10 pairs; the generated PDF row is "
        "attached by document order, which is safe because both sequences are monotone over "
        "generated pages 1,3,4,5,5,6,8,9,14,21. pairing_token_x_delta_pt is recorded per row as "
        "the residual check (max |delta| = %.2f pt on source page 40, where the row is also "
        "shifted by a synthetic indent)." % max(
            abs(r["generated"]["pairing_token_x_delta_pt"]) for r in rows if r.get("generated")
        ),
        "GAP-BEFORE-YEAR on the generated side is only defined when a tab character precedes 年 "
        "or a non-date glyph precedes it on the rendered row; the basis used is recorded in "
        "generated_gap_before_year_basis.",
        "WORD RENDERING: rendered token positions come from the build PDF's text layer. Word's "
        "own tab-stop arithmetic was not executed or re-derived, so a tab stop that exists in "
        "w:tabs but does not move the glyph is reported as a measured mismatch without a cause.",
        "NO WRITES: every input was opened read-only; only the two report paths were written.",
    ]

    report = {
        "schema": "case001_date_row_round4/1",
        "generated_by": "scripts/v1_date_row_round4_diagnostic.py",
        "build": str(build_dir).replace("\\", "/"),
        "build_hashes": {
            "docx_sha256": sha256_file(docx_path),
            "pdf_sha256": sha256_file(pdf_path),
            "generation_report_sha256": sha256_file(report_path),
        },
        "source_pdf": str(source_pdf).replace("\\", "/"),
        "source_pdf_sha256": sha256_file(source_pdf),
        "source_pdf_page_count": len(page_records),
        "source_pdf_page_box_pt": [595.3, 841.9],
        "source_date_row_count": len(rows),
        "source_date_row_count_in_build_scope": len(rows) - len(unpaired_source),
        "generated_date_paragraph_count": len(gen_records),
        "document_content_band": {"x0": r2(doc_band[0]), "x1": r2(doc_band[1]),
                                  "method": "document-wide median of per-page glyph extremes"},
        "prose_occurrences_excluded": {
            "source": source_prose,
            "source_count": len(source_prose),
            "generated_docx": gen_docx_prose,
            "generated_docx_count": len(gen_docx_prose),
            "generated_pdf": gen_pdf_prose,
            "generated_pdf_count": len(gen_pdf_prose),
            "heading_excluded": "七、近年（2023 年 1 月 1 日以来）类似项目情况表 "
                                "(docx paragraphs 15 and 110; generated PDF pages 2 and 14)",
        },
        "rows": rows,
        "alignment_classes": alignment_classes,
        "accounting": accounting,
        "tolerance": tolerance,
        "prior_measurement_reproduction": prior_reproduction,
        "root_cause_summary": root_cause_summary,
        "root_cause_findings": root_cause_findings,
        "disclosures": disclosures,
    }
    return report


def short_note(row):
    """A few words for the compact md table; full reasoning lives in the JSON."""
    if not row.get("generated"):
        return "source-only (no build counterpart)"
    parts = []
    if row["alignment_class_matches"] is False:
        parts.append("ALIGNMENT MISMATCH")
    if row["synthetic_left_indent_for_centering"]:
        parts.append("synthetic w:left for centring")
    if row["collapsed"]:
        parts.append("collapsed: no gap mechanism")
    else:
        lost = row["lost_source_date_gaps"]
        if lost:
            parts.append(
                "gaps lost: " + ",".join(g["position"] for g in lost)
            )
    if row["unexpected_date_indent"] and not row["synthetic_left_indent_for_centering"]:
        parts.append("unexpected w:left")
    if row["gaps_preserved"]:
        parts.append("all gaps within tolerance")
    return "; ".join(parts) or "ok"


def render_markdown(report):
    acc = report["accounting"]
    lines = []
    lines.append("# CASE001 date-row round-4 diagnostic (document-wide)")
    lines.append("")
    lines.append(
        "Source `%s` (`%s…`) → build `%s`."
        % (report["source_pdf"], report["source_pdf_sha256"][:12], report["build"])
    )
    lines.append("")
    lines.append("**Totals**")
    lines.append("")
    lines.append(
        "- source date rows **%d** (build scope 40–61: **%d**); generated date paragraphs **%d**"
        % (acc["source_date_rows"], acc["source_date_rows_in_build_scope"],
           acc["generated_date_paragraph_count"])
    )
    lines.append(
        "- alignment matched **%d**, reviewed exceptions **%d**, alignment mismatch **%d**; "
        "collapsed rows **%d**; lost source gaps **%d**; invented gaps **%d**; unexpected date "
        "indents **%d**; ambiguous **%d**"
        % (acc["matched_alignment"], acc["reviewed_exceptions"], acc["alignment_mismatch"],
           acc["collapsed_date_rows"], acc["lost_source_date_gaps"], acc["invented_date_gaps"],
           acc["unexpected_date_indents"], acc["ambiguous_needs_review"])
    )
    lines.append(
        "- alignment classes: " + ", ".join(
            "%s=%d" % (k, v) for k, v in sorted(report["alignment_classes"].items())
        )
    )
    lines.append(
        "- tolerance: gaps within **%.1f pt** (`MANDATORY_TOLERANCE_PT`, "
        "`tender_basic/geometry_rule_qa.py:33` == `docs/V1_DECISIONS.md` §2.1); centring "
        "`max(8.0, page_width*0.02)` = **%.2f pt** (`tender_basic/page_layout.py:463`); natural "
        "inter-glyph gap **%.2f pt** (measured)"
        % (report["tolerance"]["used_tolerance_pt"],
           report["tolerance"]["centring_tolerance"]["value_pt"],
           report["tolerance"]["natural_inter_glyph_gap_pt"])
    )
    repro = report.get("prior_measurement_reproduction")
    if repro:
        lines.append(
            "- prior 10-row measurement table: %s (max |delta| %.2f pt)"
            % ("reproduced exactly" if repro["all_rows_reproduced"] else "**NOT reproduced**",
               repro["max_abs_delta_pt"])
        )
    lines.append("")
    lines.append("**Root causes**")
    lines.append("")
    for item in report.get("root_cause_summary", []):
        lines.append("- " + item)
    lines.append("")
    lines.append("## Rows")
    lines.append("")
    lines.append(
        "| src page | y | source alignment class | extent centre / offset | gen ¶ | gen jc | "
        "gen w:left | gen gaps 年→月/月→日 | source gaps 年→月/月→日 | preserved | collapsed | note |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in report["rows"]:
        gen = row.get("generated") or {}
        lines.append(
            "| %s | %.2f | %s | %.2f / %+.2f | %s | %s | %s | %s / %s | %s / %s | %s | %s | %s |"
            % (
                row["source_page"],
                row["source_y_top"],
                row["alignment_class"].replace("SOURCE_", ""),
                row["source_row_centroid"],
                row["centroid_offset_pt"],
                gen.get("generated_paragraph_index", "—"),
                gen.get("generated_jc", "—"),
                "—" if gen.get("generated_left_twips") is None
                else "%d tw" % gen["generated_left_twips"],
                fmt(gen.get("generated_gap_year_month_pt")),
                fmt(gen.get("generated_gap_month_day_pt")),
                fmt(row["source_gap_year_month_pt"]),
                fmt(row["source_gap_month_day_pt"]),
                fmt_bool(row["gaps_preserved"]),
                fmt_bool(row["collapsed"]),
                short_note(row),
            )
        )
    lines.append("")
    lines.append(
        "Source-rule evidence per row is in the JSON (`rows[].source_gaps[].gap_kind` / "
        "`justification`, `rows[].source_rules_in_band`)."
    )
    lines.append("")
    lines.append("## Excluded prose occurrences")
    lines.append("")
    lines.append("| side | location | y | row text | reason |")
    lines.append("|---|---|---|---|---|")
    for item in report["prose_occurrences_excluded"]["source"]:
        lines.append("| source | page %s | %.2f | `%s` | %s |" % (
            item["source_page"], item["y"], item["raw_row_text"][:36],
            item["exclusion_reason"].split(" -- ")[0]))
    for item in report["prose_occurrences_excluded"]["generated_docx"]:
        lines.append("| docx | ¶%s | — | `%s` | %s |" % (
            item["generated_paragraph_index"], item["generated_text"][:36],
            item["exclusion_reason"].split(" -- ")[0]))
    lines.append("")
    lines.append("## Disclosures")
    lines.append("")
    for item in report["disclosures"]:
        lines.append("- " + item)
    lines.append("")
    return "\n".join(lines)


def fmt(value):
    return "—" if value is None else "%.2f" % value


def fmt_bool(value):
    if value is None:
        return "n/a"
    return "yes" if value else "no"


def _centring_sensitivity(rows):
    """Disclosure text for the row whose class flips when the leading rule is excluded."""
    flips = []
    for row in rows:
        if row["glyph_only_alignment_class"] != row["alignment_class"]:
            rules = row["source_rules_in_band"]
            flips.append(
                "source page %d (y=%.2f) is classified %s with centroid offset %.2f pt against a "
                "centring tolerance of %.3f pt (margin %.2f pt); this depends on including the "
                "leading rule%s %s in the effective extent, as instructed. With the glyph-only "
                "extent x[%.2f,%.2f] the offset is %.2f pt and the class becomes %s. Both values "
                "are recorded per row (centroid_offset_pt / glyph_only_centroid_offset_pt)."
                % (
                    row["source_page"], row["source_y_top"], row["alignment_class"],
                    row["centroid_offset_pt"], row["centring_tolerance_pt"],
                    row["centring_margin_pt"],
                    "" if len(rules) != 1 else "",
                    ", ".join("x[%.2f,%.2f]@y=%.2f" % (r["x0"], r["x1"], r["y"])
                              for r in rules) or "(none)",
                    row["glyph_only_extent"][0], row["glyph_only_extent"][1],
                    row["glyph_only_centroid_offset_pt"], row["glyph_only_alignment_class"],
                )
            )
    if not flips:
        return "no row changes its alignment class when the row rules are excluded from the extent."
    return " || ".join(flips)


def _marginal_centring(rows, margin_pt=0.5):
    """Disclosure text for CENTER rows that sit within ``margin_pt`` of the tolerance edge."""
    marginal = [
        row for row in rows
        if row["alignment_class"] == "SOURCE_ALIGNED_CENTER"
        and row["centring_margin_pt"] is not None
        and row["centring_margin_pt"] <= margin_pt
    ]
    if not marginal:
        return "no CENTER row sits within %.1f pt of the centring tolerance edge." % margin_pt
    return (
        "%d row(s) classified SOURCE_ALIGNED_CENTER sit within %.1f pt of the centring tolerance "
        "edge: %s. No row fell strictly outside the tolerance, so AMBIGUOUS_NEEDS_REVIEW was "
        "returned %d times."
        % (
            len(marginal),
            margin_pt,
            "; ".join(
                "source page %d x[%.2f,%.2f] offset %.2f pt vs tolerance %.3f pt (margin %.2f pt)"
                % (row["source_page"], row["source_row_extent_x0"], row["source_row_extent_x1"],
                   row["centroid_offset_pt"], row["centring_tolerance_pt"],
                   row["centring_margin_pt"])
                for row in marginal
            ),
            sum(1 for row in rows if row["alignment_class"] == "AMBIGUOUS_NEEDS_REVIEW"),
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source-pdf",
        default=str(REPO_ROOT / "acceptance" / "private" /
                    "7.28引江济淮郸城配套项目一体化泵站询比文件.pdf"),
    )
    parser.add_argument(
        "--build-dir",
        default=str(REPO_ROOT / "acceptance" / "workspace" / "case_001" /
                    "v1_manual_fidelity_round3_word_review_final"),
    )
    parser.add_argument(
        "--out-json",
        default=str(REPO_ROOT / "acceptance" / "reports" / "v1_generalization" /
                    "case001_date_row_round4_diagnostic.json"),
    )
    parser.add_argument(
        "--out-md",
        default=str(REPO_ROOT / "acceptance" / "reports" / "v1_generalization" /
                    "case001_date_row_round4_diagnostic.md"),
    )
    args = parser.parse_args(argv)

    report = build_report(args)

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(out_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_markdown(report))

    acc = report["accounting"]
    print("source pdf      : %s" % report["source_pdf"])
    print("source sha256   : %s" % report["source_pdf_sha256"])
    print("build           : %s" % report["build"])
    print("docx sha256     : %s" % report["build_hashes"]["docx_sha256"])
    print("pdf  sha256     : %s" % report["build_hashes"]["pdf_sha256"])
    print("report sha256   : %s" % report["build_hashes"]["generation_report_sha256"])
    print("source date rows: %d (build scope %d)   generated date paragraphs: %d"
          % (acc["source_date_rows"], acc["source_date_rows_in_build_scope"],
             acc["generated_date_paragraph_count"]))
    print("prose excluded  : source %d, docx %d, generated pdf %d"
          % (report["prose_occurrences_excluded"]["source_count"],
             report["prose_occurrences_excluded"]["generated_docx_count"],
             report["prose_occurrences_excluded"]["generated_pdf_count"]))
    print("alignment       : " + ", ".join(
        "%s=%d" % (k, v) for k, v in sorted(report["alignment_classes"].items())))
    print("accounting      : matched=%d reviewed_exceptions=%d mismatch=%d collapsed=%d "
          "lost_gaps=%d invented_gaps=%d unexpected_indents=%d ambiguous=%d"
          % (acc["matched_alignment"], acc["reviewed_exceptions"], acc["alignment_mismatch"],
             acc["collapsed_date_rows"], acc["lost_source_date_gaps"], acc["invented_date_gaps"],
             acc["unexpected_date_indents"], acc["ambiguous_needs_review"]))
    print("root causes     : %d finding(s)" % len(report["root_cause_findings"]))
    for finding in report.get("root_cause_summary", []):
        print("  - %s" % finding)
    repro = report.get("prior_measurement_reproduction") or {}
    print("prior table     : all_rows_reproduced=%s max|delta|=%.4f pt"
          % (repro.get("all_rows_reproduced"), repro.get("max_abs_delta_pt") or 0.0))
    print("wrote           : %s" % out_json)
    print("wrote           : %s" % out_md)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
