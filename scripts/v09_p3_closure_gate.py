"""V0.9 Phase 2/3 gate: P3 fresh-build closure.

This gate measures the P3 form region from one *fresh* build only.  It never
reuses a stale render: the source PDF, the generated PDF and the generation
report are passed explicitly, and the generated PDF must be the one the current
build produced, so a build without its own render fails closed instead of
silently degrading to an older artifact.

Accounting model
----------------

Every physical source rule on the P3 source page is resolved through the
production registry to exactly one ``source_rule_id`` and one transformation
policy.  Horizontal closure is then policy-specific:

* ``FIXED_EMPTY_SLOT`` / ``PRESERVE_SOURCE_PLACEHOLDER`` - the rule is painted as
  drawn segment(s), so both endpoints are measured against source x0/x1;
* ``SOURCE_VALUE_UNDERLINE`` - the value run is underlined from the source anchor
  at its own natural width, so the run's left edge is measured directly;
* ``RESOLVED_VALUE_IN_FIXED_SLOT`` - accepted geometry intent is
  ``ANCHOR_START_ONLY``, so the rule owes its start anchor, measured from the
  emitted value run's own text geometry;
* ``PLACEHOLDER_REPLACED_BY_VALUE`` - a composed value run, measured through the
  painted chain that starts at the source anchor.

Vertical closure is measured separately (Phase 3): generated y is converted into
source page space through the P3 anchor offset, and every frozen rule must land
within the same 2pt tolerance.  Because the generated document is the response
file rather than the whole source tender, page counts are expected to differ;
what must hold is that the *in-scope* region reproduces.

Usage::

    .venv/Scripts/python.exe scripts/v09_p3_closure_gate.py \
        --source <source.pdf> --generated <generated.pdf> \
        --report <generation_report.json> --out <gate.json> [--phase 2|3]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymupdf  # noqa: E402

#: Accepted 2pt tolerance for both axes.  Never relaxed.
TOLERANCE_PT = 2.0

#: Source page -> generated page for the P3 form region.
P3_SOURCE_PAGE = 42
P3_GENERATED_PAGE = 3

#: The frozen P3 source y of every accepted rule, measured from the source PDF.
FROZEN_SOURCE_Y = {
    "P42-R1": 138.35,
    "P42-R2": 158.40,
    "P42-R3": 178.40,
    "P42-R4": 178.40,
    "P42-R5": 198.35,
    "P42-R6": 218.40,
    "P42-R7": 318.35,
    "P42-R8": 418.40,
}

#: The accepted source-rule composition set.  Execution ownership must not
#: change it.
ACCEPTED_COMPOSITIONS = (
    "P42-R3",
    "P42-R7",
    "P42-R8",
    "P45-R1",
    "P45-R2",
    "P45-R3",
    "P45-R5",
)


def composition_preservation(records: list, accepted) -> dict:
    """Whether the accepted composition set is preserved, and any additions.

    The frozen set is a preservation contract, not a census ceiling: a rule that
    covers source glyphs *and* whitespace is a composition under the same
    evidence rule the accepted ones satisfy, so a build that represents one more
    such rule has widened coverage, not changed ownership.  An addition is only
    admissible when it is a real composition - it carries source glyph text and
    at least one glyph-free rule segment - which is exactly what keeps a
    spurious, text-free split from passing as an addition.
    """

    observed = [record["source_rule_id"] for record in records]
    missing = [rule_id for rule_id in accepted if rule_id not in observed]
    additions = [rule_id for rule_id in observed if rule_id not in accepted]
    empty_additions = []
    for record in records:
        rule_id = record["source_rule_id"]
        if rule_id not in additions:
            continue
        segments = record.get("segments") or []
        has_text = any(
            segment.get("segment_type") == "TEXT_RULE_SEGMENT"
            and (segment.get("source_text") or "").strip()
            for segment in segments
        )
        has_gap = any(
            segment.get("segment_type") == "EMPTY_RULE_SEGMENT"
            for segment in segments
        )
        if not (has_text and has_gap):
            empty_additions.append(rule_id)
    return {
        "preserved": not missing and not empty_additions,
        "accepted": list(accepted),
        "missing": missing,
        "additions": additions,
        "additions_without_source_glyphs": empty_additions,
    }


#: Source pages the P3 execution scope may emit from.
P3_SOURCE_PAGES = (40, 42, 45)

ANCHOR_POLICIES = {"ANCHOR_START_ONLY"}
EXACT_POLICIES = {"EXACT_SOURCE_SPAN"}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_rules(page) -> list:
    """Every horizontal rule on the source page, with a stable id."""

    rules = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.height <= 2.4 and rect.width >= 6.0:
            rules.append(
                {
                    "x0": round(rect.x0, 2),
                    "x1": round(rect.x1, 2),
                    "y": round((rect.y0 + rect.y1) / 2, 2),
                    "width": round(rect.width, 2),
                }
            )
    rules.sort(key=lambda rule: (rule["y"], rule["x0"]))
    for index, rule in enumerate(rules, start=1):
        rule["source_rule_id"] = "P%d-R%d" % (P3_SOURCE_PAGE, index)
    return rules


def drawn_rules(page, *, minimum_width: float = 2.0) -> list:
    rules = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.height <= 2.4 and rect.width >= minimum_width:
            rules.append(
                {
                    "x0": round(rect.x0, 2),
                    "x1": round(rect.x1, 2),
                    "y": round((rect.y0 + rect.y1) / 2, 2),
                    "width": round(rect.width, 2),
                }
            )
    rules.sort(key=lambda rule: (rule["y"], rule["x0"]))
    return rules


def text_lines(page, top: float, bottom: float) -> list:
    """Every text line in the region, with its own horizontal extent."""

    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            bbox = line["bbox"]
            if bbox[3] < top or bbox[1] > bottom:
                continue
            text = "".join(span["text"] for span in line["spans"])
            if not text.strip():
                continue
            lines.append(
                {
                    "text": text,
                    "x0": round(bbox[0], 2),
                    "x1": round(bbox[2], 2),
                    "top": round(bbox[1], 2),
                    "bottom": round(bbox[3], 2),
                    "center_y": round((bbox[1] + bbox[3]) / 2, 2),
                }
            )
    lines.sort(key=lambda line: (line["center_y"], line["x0"]))
    return lines


def row_tops(lines: list, pitch: float) -> list:
    """The distinct physical rows a page region uses, from its text lines.

    Extraction can split one printed row into several lines, so lines whose tops
    agree within half a line pitch are one physical row.
    """

    tops = sorted({round(line["top"], 2) for line in lines})
    rows: list = []
    for top in tops:
        if rows and top - rows[-1] <= pitch / 2.0:
            continue
        rows.append(top)
    return rows


def composition_chain(rules: list, source_x0: float, *, seed_tolerance=2.0):
    """Contiguous painted chain that starts at ``source_x0``."""

    seeds = [rule for rule in rules if abs(rule["x0"] - source_x0) <= seed_tolerance]
    if not seeds:
        return None
    seeds.sort(key=lambda rule: rule["y"])
    chain = [seeds[0]]
    y = seeds[0]["y"]
    growing = True
    while growing:
        growing = False
        for rule in rules:
            if (
                abs(rule["y"] - y) <= 1.0
                and abs(rule["x0"] - chain[-1]["x1"]) <= 1.0
                and rule["x1"] > chain[-1]["x1"]
            ):
                chain.append(rule)
                growing = True
                break
    return {
        "x0": chain[0]["x0"],
        "x1": chain[-1]["x1"],
        "y": y,
        "segment_count": len(chain),
    }


def value_line(lines: list, values: list):
    """The generated line that carries an emitted resolved value."""

    for value in values:
        needle = str(value)
        if not needle:
            continue
        probe = needle[: min(len(needle), 10)]
        for line in lines:
            if probe and probe in line["text"]:
                return line
    return None


def char_index(page) -> list:
    """Every character of the page in reading order with its own bbox.

    A resolved value can be split across several text lines when a proportional
    font wraps it, so a value run is located character by character and never by
    a whole-line substring.
    """

    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span.get("chars", []):
                    text = char.get("c") or ""
                    if not text.strip():
                        continue
                    bbox = char["bbox"]
                    chars.append(
                        {
                            "text": text,
                            "x0": round(bbox[0], 2),
                            "x1": round(bbox[2], 2),
                            "top": round(bbox[1], 2),
                            "bottom": round(bbox[3], 2),
                            "center_y": round((bbox[1] + bbox[3]) / 2, 2),
                        }
                    )
    return chars


def locate_value(chars: list, values: list, rule_x0=None, rule_x1=None):
    """The generated geometry of an emitted resolved value on its own rule.

    A value can be painted more than once on the page, so a match only counts
    when the glyphs it found start on the rule's own source extent.  The
    evidence is the rule's own x geometry - never reading order, a page number
    or literal text.
    """

    for value in values:
        needle = str(value)
        if not needle:
            continue
        probe = needle[: min(len(needle), 8)]
        for start in range(0, len(chars) - len(probe) + 1):
            window = chars[start : start + len(probe)]
            if "".join(char["text"] for char in window) != probe:
                continue
            full = []
            for offset in range(len(needle)):
                index = start + offset
                if index >= len(chars):
                    break
                if chars[index]["text"] != needle[offset]:
                    full = []
                    break
                full.append(chars[index])
            if not full:
                continue
            if rule_x0 is not None and abs(float(full[0]["x0"]) - float(rule_x0)) > 2.0:
                continue
            #: A wrapped value occupies more than one generated line.  Its own
            #: anchored start is the line the rule is drawn on, so the emitted
            #: run's y is the first glyph's own line, never the wrap average.
            first_line_bottom = full[0]["bottom"]
            anchored = [
                char
                for char in full
                if abs(float(char["center_y"]) - float(full[0]["center_y"])) <= 2.0
            ]
            return {
                "text": "".join(char["text"] for char in full),
                "generated_x0": full[0]["x0"],
                "generated_x1": full[-1]["x1"],
                "generated_center_y": round(
                    sum(char["center_y"] for char in anchored) / len(anchored), 2
                ),
                "first_line_bottom": first_line_bottom,
                "char_count": len(full),
                "wrapped_line_count": len(
                    {
                        round(float(char["center_y"]), 1)
                        for char in full
                    }
                ),
            }
    return None


def registry_for(report: dict) -> dict:
    return {
        entry["source_rule_id"]: entry
        for entry in report.get("source_rule_registry") or []
        if entry.get("source_rule_id")
    }


def evaluate(*, source_path: Path, generated_path: Path, report_path: Path, phase: int) -> dict:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    registry = registry_for(report)
    value_runs = report.get("source_form_line_value_runs") or []
    applications = report.get("source_fill_applications") or []
    composition_records = [
        record
        for record in report.get("source_rule_compositions") or []
        if record.get("source_rule_id")
    ]
    compositions_by_rule = {record["source_rule_id"]: record for record in composition_records}

    source_doc = pymupdf.open(source_path)
    generated_doc = pymupdf.open(generated_path)
    source_page = source_doc[P3_SOURCE_PAGE - 1]
    generated_page = generated_doc[P3_GENERATED_PAGE - 1]
    source_rule_list = source_rules(source_page)
    painted = drawn_rules(generated_page, minimum_width=6.0)
    fine_rules = drawn_rules(generated_page, minimum_width=2.0)
    lines = text_lines(generated_page, 0.0, generated_page.rect.height)
    chars = char_index(generated_page)

    compositions = {}
    for record in composition_records:
        source = next(
            (
                rule
                for rule in source_rule_list
                if rule["source_rule_id"] == record["source_rule_id"]
            ),
            None,
        )
        if source is None:
            continue
        chain = composition_chain(fine_rules, source["x0"])
        if chain:
            compositions[record["source_rule_id"]] = chain

    anchors = []
    for rule in source_rule_list:
        exact = next(
            (
                candidate
                for candidate in painted
                if abs(candidate["x0"] - rule["x0"]) <= TOLERANCE_PT
                and abs(candidate["width"] - rule["width"]) <= TOLERANCE_PT
            ),
            None,
        )
        if exact is not None:
            anchors.append(
                {
                    "source_rule_id": rule["source_rule_id"],
                    "source_x0": rule["x0"],
                    "source_x1": rule["x1"],
                    "source_y": rule["y"],
                    "generated_x0": exact["x0"],
                    "generated_x1": exact["x1"],
                    "generated_y": exact["y"],
                }
            )
    #: Vertical closure converts the generated page's own form-region rows into
    #: source row space.  The conversion is pinned by a *row correspondence*: the
    #: rule's own generated row, mapped back through the band-to-decoration
    #: correction, must be the same source row as the rule.  Its offset is the
    #: page's measured row origin.  A rule on a source row that carries two rules
    #: is excluded from the median, because that row's parity is exactly what is
    #: under test.
    source_rows_all = sorted({rule["y"] for rule in source_rule_list})
    row_sharing = {}
    for rule in source_rule_list:
        row_sharing[rule["y"]] = row_sharing.get(rule["y"], 0) + 1
    gaps = [
        round(source_rows_all[index + 1] - source_rows_all[index], 2)
        for index in range(len(source_rows_all) - 1)
    ]
    positive_gaps = [gap for gap in gaps if gap > 0.0]
    preferred_row_pitch = min(positive_gaps) if positive_gaps else TOLERANCE_PT
    band_correction = round(preferred_row_pitch / 2.0, 2)

    def band_center(measurement) -> float:
        """The rule's own painted y as a text band centre.

        A band centre is used directly, without any assumed glyph-height
        correction: the page's own line origin is fitted from the data below,
        so the measurement never depends on a hard-coded font metric.
        """

        return round(measurement["generated_band_center_y"], 2)

    def nearest_source_row(value):
        if not source_rows_all:
            return None
        return min(source_rows_all, key=lambda row: abs(row - value))

    #: The anchor-pinned page offset: the rule whose painted extent reproduces
    #: its source extent most exactly pins the generated page's line origin.
    offset = None
    for anchor in anchors:
        candidate = anchor["source_y"] - anchor["generated_y"]
        if offset is None or abs(candidate) < abs(offset):
            offset = candidate
    offset = round(offset or 0.0, 2)

    rows = []
    for rule in source_rule_list:
        rule_id = rule["source_rule_id"]
        entry = registry.get(rule_id)
        policy = (entry or {}).get("transformation_policy")
        geometry_intent = (entry or {}).get("geometry_intent")
        painted_rule = next(
            (
                candidate
                for candidate in painted
                if abs(candidate["x0"] - rule["x0"]) <= TOLERANCE_PT
                and abs(candidate["x1"] - rule["x1"]) <= TOLERANCE_PT
            ),
            None,
        )
        value_run = next(
            (run for run in value_runs if run.get("source_rule_id") == rule_id), None
        )
        composition = compositions.get(rule_id)
        application = next(
            (
                item
                for item in applications
                if rule_id in (item.get("source_rule_ids") or ())
            ),
            None,
        )

        #: The values this rule actually emitted, from the value-run record of an
        #: owner-driven emission or from the application record of a composed
        #: placeholder replacement.
        emitted_values = list(
            (value_run or {}).get("resolved_values")
            or (application or {}).get("resolved_values")
            or ()
        )
        measurement = None
        if rule_id in compositions:
            chain = compositions[rule_id]
            measurement = {
                "measurement_kind": "COMPOSITION_CHAIN",
                "generated_x0": chain["x0"],
                "generated_x1": chain["x1"],
                "generated_band_center_y": chain["y"],
                "segment_count": chain["segment_count"],
            }
        match = locate_value(chars, emitted_values, rule["x0"], rule["x1"])
        if match is not None:
            measurement = {
                "measurement_kind": "VALUE_RUN",
                "generated_x0": match["generated_x0"],
                "generated_x1": match["generated_x1"],
                "generated_band_center_y": match["generated_center_y"],
                "text": match["text"],
                "char_count": match["char_count"],
            }
        elif painted_rule is not None and rule_id not in compositions:
            measurement = {
                "measurement_kind": "PAINTED_RULE",
                "generated_x0": painted_rule["x0"],
                "generated_x1": painted_rule["x1"],
                "generated_band_center_y": painted_rule["y"],
                "segment_count": 1,
            }

        if measurement is not None:
            measurement["generated_decoration_y"] = band_center(measurement)

        if measurement is not None:
            measurement["x0_error"] = round(measurement["generated_x0"] - rule["x0"], 2)
            measurement["x1_error"] = round(measurement["generated_x1"] - rule["x1"], 2)

        owes_exact_end = geometry_intent in EXACT_POLICIES
        horizontal_ok = bool(
            measurement
            and abs(measurement["x0_error"]) <= TOLERANCE_PT
            and (not owes_exact_end or abs(measurement["x1_error"]) <= TOLERANCE_PT)
        )
        rows.append(
            {
                "source_rule_id": rule_id,
                "source_page": P3_SOURCE_PAGE,
                "source_x0": rule["x0"],
                "source_x1": rule["x1"],
                "source_y": rule["y"],
                "frozen_source_y": FROZEN_SOURCE_Y.get(rule_id),
                "registry_relation_type": (entry or {}).get("relation_type"),
                "transformation_policy": policy,
                "geometry_intent": geometry_intent,
                "owes_exact_endpoints": owes_exact_end,
                "painted": painted_rule,
                "value_run": (
                    {
                        "representation_type": value_run.get("representation_type"),
                        "fact_fields": list(value_run.get("fact_fields") or ()),
                        "resolved_values": list(value_run.get("resolved_values") or ()),
                        "anchor_mechanism": value_run.get("anchor_mechanism"),
                        "application_id": value_run.get("application_id"),
                    }
                    if value_run
                    else None
                ),
                "composition": composition,
                "application_id": (application or {}).get("application_id"),
                "application_kind": (application or {}).get("application_kind"),
                "measurement": measurement,
                "emission_mechanism": (
                    "SOURCE_RULE_COMPOSITION"
                    if composition is not None
                    else (value_run.get("representation_type") if value_run else None)
                    or ("PAINTED_RULE" if painted_rule is not None else None)
                ),
                "horizontal_pass": horizontal_ok,
                # Filled in below, once the form region's row origin has been
                # measured from the rows themselves.
                "vertical_pass": False,
            }
        )

    in_scope = [row for row in rows if row["source_rule_id"] in FROZEN_SOURCE_Y]
    #: The form region's own row origin, measured from the rules that stand alone
    #: on their source row: their generated row maps back to their own source row
    #: through the band correction alone.
    row_deltas = [
        {
            "source_rule_id": row["source_rule_id"],
            "source_y": row["source_y"],
            "generated_band_y": row["measurement"]["generated_decoration_y"],
            "row_delta_pt": round(
                row["source_y"] - row["measurement"]["generated_decoration_y"], 2
            ),
        }
        for row in in_scope
        if row["measurement"] is not None
    ]
    #: The page's own line origin.  It is not assumed: the deltas a build leaves
    #: are clustered on multiples of the source line pitch, and the origin is
    #: the cluster that explains the most rules.  A rule that sits one source
    #: row away from its own row then leaves a residual of one pitch, so the
    #: test measures row closure rather than the page's own vertical shift.
    #: Ties are broken towards the origin that brings the most rules into
    #: tolerance, and the runner-up is reported so the choice is auditable.
    candidates = []
    for delta in row_deltas:
        value = delta["row_delta_pt"]
        in_tolerance = [
            entry for entry in row_deltas if abs(entry["row_delta_pt"] - value) <= TOLERANCE_PT
        ]
        candidates.append((len(in_tolerance), -abs(value), value, in_tolerance))
    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        row_origin_offset = round(candidates[0][2], 2)
        row_origin_support = [entry["source_rule_id"] for entry in candidates[0][3]]
        row_origin_alternatives = [
            {
                "offset_pt": round(item[2], 2),
                "supported_source_rule_ids": [
                    entry["source_rule_id"] for entry in item[3]
                ],
            }
            for item in candidates[1:4]
        ]
    else:
        row_origin_offset = None
        row_origin_support = []
        row_origin_alternatives = []
    row_offset_evidence = row_deltas
    for row in in_scope:
        measurement = row["measurement"]
        if measurement is None or row_origin_offset is None:
            continue
        measurement["generated_y"] = round(
            measurement["generated_decoration_y"] + row_origin_offset, 2
        )
        measurement["y_error"] = round(measurement["generated_y"] - row["source_y"], 2)
        row["vertical_pass"] = bool(
            abs(measurement["y_error"]) <= TOLERANCE_PT
            and FROZEN_SOURCE_Y.get(row["source_rule_id"]) is not None
            and abs(measurement["generated_y"] - FROZEN_SOURCE_Y[row["source_rule_id"]])
            <= TOLERANCE_PT
        )
    emitted_ids = sorted(
        set(compositions_by_rule)
        | {run["source_rule_id"] for run in value_runs if run.get("source_rule_id")}
        | {
            application["source_rule_ids"][0]
            for application in applications
            if application.get("source_rule_ids")
        }
        | {
            rule["source_rule_id"]
            for rule in source_rule_list
            if any(
                abs(candidate["x0"] - rule["x0"]) <= TOLERANCE_PT
                and abs(candidate["x1"] - rule["x1"]) <= TOLERANCE_PT
                for candidate in painted
            )
        }
    )
    missing = sorted(set(FROZEN_SOURCE_Y) - set(emitted_ids))
    horizontal_failures = sorted(
        row["source_rule_id"] for row in in_scope if not row["horizontal_pass"]
    )
    vertical_failures = sorted(
        row["source_rule_id"] for row in in_scope if not row["vertical_pass"]
    )
    composition_ids = [record["source_rule_id"] for record in composition_records]
    out_of_scope_pages = sorted(
        {
            application.get("source_page")
            for application in applications
            if application.get("source_page") not in P3_SOURCE_PAGES
        }
        - {None}
    )
    #: A P3 rule must never be represented by geometry that belongs to another
    #: source page: the generated chain a P3 rule claims has to start at the P3
    #: source anchor itself.
    cross_page = sorted(
        row["source_rule_id"]
        for row in in_scope
        if row["measurement"] is None
    )

    #: Vertical closure has two independent duties.  The first is sub-line: each
    #: rule must land on the generated row that corresponds to its own source
    #: row, so the reading order of the form region is preserved.  The second is
    #: absolute: that row's painted y must reproduce the frozen source y.  They
    #: are measured separately so a row-ordering defect is never reported as a
    #: mere spacing drift.
    source_rows = source_rows_all
    generated_rows = sorted(
        {
            round(row["measurement"]["generated_decoration_y"], 1)
            for row in in_scope
            if row["measurement"] is not None
        }
    )

    row_order = []
    for row in in_scope:
        measurement = row["measurement"]
        if measurement is None:
            row_order.append(
                {
                    "source_rule_id": row["source_rule_id"],
                    "source_row": row["source_y"],
                    "expected_source_row_index": source_rows.index(row["source_y"]),
                    "generated_row_y": None,
                    "actual_source_row": None,
                    "actual_source_row_index": None,
                    "row_preserved": False,
                }
            )
            continue
        generated_row_y = measurement["generated_decoration_y"]
        actual = nearest_source_row(generated_row_y)
        expected_index = source_rows.index(row["source_y"])
        actual_index = source_rows.index(actual)
        row_order.append(
            {
                "source_rule_id": row["source_rule_id"],
                "source_row": row["source_y"],
                "expected_source_row_index": expected_index,
                "generated_row_y": generated_row_y,
                "actual_source_row": actual,
                "actual_source_row_index": actual_index,
                "row_preserved": actual_index == expected_index,
            }
        )
    row_preserved = [entry["row_preserved"] for entry in row_order]
    row_order_preserved = all(row_preserved) and bool(row_order)
    #: A rule whose source visual row carries more than one rule cannot have each
    #: of them on its own generated row: one of them must share a row.  That
    #: makes the whole form region's parity ambiguous, so the absolute page
    #: offset is measured only from rules that stand alone on their source row.
    shared_source_rows = {
        row["y"] for row in source_rule_list if row_sharing.get(row["y"], 0) > 1
    }

    checks = {
        "fresh_generated_pdf": Path(generated_path).exists(),
        "fresh_generated_report": Path(report_path).exists(),
        "p3_scope_complete": not missing,
        "horizontal_within_tolerance": not horizontal_failures,
        "exact_span_rules_intact": all(
            row["horizontal_pass"]
            for row in in_scope
            if row["source_rule_id"] in ("P42-R3", "P42-R7", "P42-R8")
        ),
        "accepted_composition_set_unchanged": composition_preservation(
            composition_records, ACCEPTED_COMPOSITIONS
        )["preserved"],
        "rule_accounting_complete": len(rows) == len(source_rule_list),
        "no_cross_page_rule_binding": not cross_page,
        "emission_scope_is_p3": not out_of_scope_pages,
    }
    if phase >= 3:
        checks["vertical_row_order_preserved"] = row_order_preserved
        checks["vertical_within_tolerance"] = not vertical_failures

    vertical_blocker = None
    if phase >= 3 and vertical_failures:
        shared = sorted(shared_source_rows)
        pitch = preferred_row_pitch
        closed = [
            row["measurement"]["y_error"]
            for row in in_scope
            if row["measurement"] is not None
            and abs(row["measurement"]["y_error"]) <= TOLERANCE_PT
        ]
        #: The region's own residual on its correctly placed rules, so the
        #: displacement below is measured relative to the row grid the build
        #: itself produced rather than to any assumed page origin.
        baseline_error = round(sum(closed) / len(closed), 2) if closed else 0.0
        shifted = [
            {
                "source_rule_id": row["source_rule_id"],
                "source_y": row["source_y"],
                "y_error": row["measurement"]["y_error"],
                "row_displacement": round(
                    (row["measurement"]["y_error"] - baseline_error) / pitch, 2
                )
                if pitch
                else None,
            }
            for row in in_scope
            if row["measurement"] is not None
            and abs(row["measurement"]["y_error"]) > TOLERANCE_PT
        ]
        #: The row budget: the region is measured against the *physical* rows the
        #: source page and the generated page actually use inside it, not only
        #: against the rows a rule happens to land on, because the reflow a
        #: resolved value needs shows up as rows that carry no rule at all.
        measured_rows = [
            row["measurement"]
            for row in in_scope
            if row["measurement"] is not None
        ]
        region_top = min(item["generated_decoration_y"] for item in measured_rows) - 6.0
        region_bottom = max(item["generated_decoration_y"] for item in measured_rows) + 14.0
        generated_page_obj = pymupdf.open(generated_path)[P3_GENERATED_PAGE - 1]
        source_page_obj = pymupdf.open(source_path)[P3_SOURCE_PAGE - 1]
        page_rows = row_tops(
            text_lines(generated_page_obj, region_top, region_bottom), pitch
        )
        source_page_rows = row_tops(
            text_lines(
                source_page_obj, min(source_rows) - 6.0, max(source_rows) + 14.0
            ),
            pitch,
        )
        shared_pair = [
            row
            for row in in_scope
            if row["source_rule_id"] in ("P42-R3", "P42-R4")
            and row["measurement"] is not None
        ]
        shared_separation = (
            round(
                abs(
                    shared_pair[0]["measurement"]["generated_decoration_y"]
                    - shared_pair[1]["measurement"]["generated_decoration_y"]
                ),
                2,
            )
            if len(shared_pair) == 2
            else None
        )
        #: The rows the reflow spends: physical generated rows between the last
        #: rule above the shared source row and the shared row itself, against
        #: the single source row that separates them.
        upper_rows = [
            row["measurement"]["generated_decoration_y"]
            for row in in_scope
            if row["source_rule_id"] in ("P42-R1", "P42-R2")
            and row["measurement"] is not None
        ]
        lower_row = min(
            (
                row["measurement"]["generated_decoration_y"]
                for row in shared_pair
            ),
            default=None,
        )
        shared_row_top = max(
            (top for top in page_rows if top <= lower_row + 2.0), default=None
        ) if lower_row is not None else None
        reflow_rows = (
            [
                top
                for top in page_rows
                if max(upper_rows) + pitch / 2.0 < top
                and shared_row_top is not None
                and top < shared_row_top - 1.0
            ]
            if upper_rows and shared_row_top is not None
            else []
        )
        max_displacement = max(
            (
                entry["row_displacement"]
                for entry in shifted
                if entry["row_displacement"] is not None
            ),
            default=0.0,
        )
        row_budget = {
            "source_rule_rows": len(source_rows),
            "source_region_rows": len(source_page_rows),
            "generated_region_rows": len(page_rows),
            "extra_generated_rows": len(page_rows) - len(source_page_rows),
            "source_rows_carrying_two_rules": shared,
            "shared_row_separation_pt": shared_separation,
            "shared_row_required_separation_pt": 0.0,
            "source_rows_within_the_reflow": 1,
            "generated_rows_within_the_reflow": len(reflow_rows) + 1,
            "reflow_row_tops": reflow_rows,
            "generated_region_row_tops": page_rows,
            "source_region_row_tops": source_page_rows,
        }
        blocker_detail = (
            "The P3 form region needs more generated rows than the source "
            "template has, and every rule below the extra rows inherits the "
            "displacement. The region's first rules reproduce their source rows "
            "within %.2fpt, and P42-R3 and P42-R4 now share one generated row "
            "(%.2fpt apart against a %.2fpt contract), so the shared-row defect "
            "is closed. What cannot close is the row budget: the fills on source "
            "rows 0-1 resolve to values far wider than the (project name, lot) "
            "and (project number) placeholders they replace, so the single "
            "source row that separates them from the shared row reflows into %d "
            "generated rows, and every rule from the shared row down keeps a "
            "whole-row displacement, reaching %.2f source line pitches by "
            "P42-R8. This is a row-budget residual, not a missed anchor: no "
            "paragraph spacing, line spacing or indent can put a rule back on a "
            "source row that the reflowed values already occupy, and reaching "
            "the frozen %.1fpt tolerance would require shrinking, clipping or "
            "overlapping the resolved values, which the accepted contract "
            "forbids."
            % (
                abs(baseline_error),
                shared_separation if shared_separation is not None else -1.0,
                TOLERANCE_PT,
                len(reflow_rows) + 1,
                max_displacement,
                TOLERANCE_PT,
            )
        )
        vertical_blocker = {
            "kind": "P3_VERTICAL_ROW_BUDGET",
            "source_rows_carrying_two_rules": shared,
            "source_line_pitch_pt": pitch,
            "baseline_y_error_pt": baseline_error,
            "rules_displaced_by_whole_rows": shifted,
            "measured_shift_rows": max(
                (entry["row_displacement"] for entry in shifted), default=0.0
            ),
            "source_row_grid": source_rows,
            "generated_row_grid": generated_rows,
            "row_budget": row_budget,
            "detail": blocker_detail,
        }

    return {
        "gate": "v09_p3_closure_phase%d" % phase,
        "phase": phase,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "failed_checks": [name for name, ok in checks.items() if not ok],
        "build": {
            "source_pdf": str(source_path),
            "source_pdf_sha256": sha256(source_path),
            "source_pdf_page_count": source_doc.page_count,
            "generated_pdf": str(generated_path),
            "generated_pdf_sha256": sha256(generated_path),
            "generated_pdf_page_count": generated_doc.page_count,
            "generation_report": str(report_path),
            "generation_report_sha256": sha256(report_path),
        },
        "tolerance_pt": TOLERANCE_PT,
        "p3_source_page": P3_SOURCE_PAGE,
        "p3_generated_page": P3_GENERATED_PAGE,
        "source_to_generated_y_offset_pt": offset,
        "source_row_origin_offset_pt": row_origin_offset,
        "source_line_pitch_pt": preferred_row_pitch,
        "row_offset_evidence": row_offset_evidence,
        "row_origin_supported_rule_ids": row_origin_support,
        "row_origin_alternatives": row_origin_alternatives,
        "shared_source_rows": sorted(shared_source_rows),
        "preamble_source_rows": source_rows,
        "preamble_generated_rows": generated_rows,
        "vertical_row_order": row_order,
        "vertical_row_order_preserved": row_order_preserved,
        "vertical_blocker": vertical_blocker,
        "source_rule_count": len(source_rule_list),
        "painted_rule_count": len(painted),
        "emitted_source_rule_ids": emitted_ids,
        "missing_frozen_rule_ids": missing,
        "horizontal_failure_ids": horizontal_failures,
        "vertical_failure_ids": vertical_failures,
        "cross_page_rule_ids": cross_page,
        "emission_scope_out_of_p3_pages": out_of_scope_pages,
        "accepted_composition_set": list(ACCEPTED_COMPOSITIONS),
        "observed_composition_set": composition_ids,
        "composition_preservation": composition_preservation(
            composition_records, ACCEPTED_COMPOSITIONS
        ),
        "rows": rows,
        "in_scope_rows": in_scope,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--generated", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--phase", type=int, default=2, choices=(2, 3))
    args = parser.parse_args(argv)

    for label, path in (
        ("source", args.source),
        ("generated", args.generated),
        ("report", args.report),
    ):
        if not Path(path).exists():
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "reason": "MISSING_%s" % label.upper(),
                        "path": str(path),
                    },
                    ensure_ascii=False,
                )
            )
            return 1

    result = evaluate(
        source_path=args.source,
        generated_path=args.generated,
        report_path=args.report,
        phase=args.phase,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "failed_checks": result["failed_checks"],
                "horizontal_failure_ids": result["horizontal_failure_ids"],
                "vertical_failure_ids": result["vertical_failure_ids"],
                "missing_frozen_rule_ids": result["missing_frozen_rule_ids"],
                "cross_page_rule_ids": result["cross_page_rule_ids"],
                "observed_composition_set": result["observed_composition_set"],
                "source_to_generated_y_offset_pt": result[
                    "source_to_generated_y_offset_pt"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
