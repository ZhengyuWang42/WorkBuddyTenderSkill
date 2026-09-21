"""Round 5.7 geometry + source-rule matching QA.

This module is the *measurement* layer for the Round 5.7 corrective round.  It
never edits production output: it rasterises/parses the authoritative rendered
source tender pages and the rendered generated Word pages, reduces both to

* **rules** - visible horizontal ink segments (drawn vector rules and Word
  underline runs) with ``x0``/``x1``/``y``/``width``/``kind`` and the semantic
  source context they sit in, and
* **table geometry** - the outer box, column boundaries and row boundaries of a
  table object,

and then matches source rules to generated rules one-to-one.

The matcher is deliberately strict: a mandatory source rule is only *matched*
when a generated rule sits within ``MANDATORY_TOLERANCE_PT`` on the page, the
horizontal geometry and the semantic context.  Tolerance is never widened to
make a gate green; a proven renderer-wide systematic offset must be passed in
explicitly through ``normalization`` and is then documented in the report.
"""

from __future__ import annotations

import re
from pathlib import Path
from statistics import median

import pymupdf

ROOT = Path(__file__).resolve().parents[1]

#: Round 5.7 mandatory geometry tolerance, in points.
MANDATORY_TOLERANCE_PT = 2.0

#: Portion of the page height treated as the running header/footer band.
CHROME_BAND = 0.075

#: A drawn segment counts as a horizontal rule when it is this thin.
MAX_RULE_HEIGHT_PT = 2.4

#: Minimum visible length of a horizontal rule.
MIN_RULE_WIDTH_PT = 6.0

#: Two collinear segments closer than this are one painted rule (Word paints a
#: table border as several segments; the source draws it as one).
MERGE_GAP_PT = 4.0

#: Vertical neighbourhood used when matching a source rule to a generated rule.
Y_NEIGHBOURHOOD_PT = 2.0

#: Blank/rule kinds modelled by the round.
VECTOR_RULE = "VECTOR_RULE"
UNDERLINED_WHITESPACE = "UNDERLINED_WHITESPACE"
LITERAL_UNDERSCORE = "LITERAL_UNDERSCORE"
TAB_LEADER = "TAB_LEADER"
VALUE_WITH_UNDERLINE = "VALUE_WITH_UNDERLINE"
SOURCE_PLACEHOLDER_WITH_UNDERLINE = "SOURCE_PLACEHOLDER_WITH_UNDERLINE"

#: Kinds whose rendered appearance is a solid line, so a source rule and a
#: generated underline are the same visible affordance.
SAME_VISUAL_RULE = {
    VECTOR_RULE,
    UNDERLINED_WHITESPACE,
    VALUE_WITH_UNDERLINE,
    SOURCE_PLACEHOLDER_WITH_UNDERLINE,
}

#: Hard invariants every ``match_blank_rules`` report must satisfy.  A report
#: that breaks one of these must never be emitted as a gate result.
MATCH_INVARIANTS = (
    "source == matched + lost",
    "generated == matched + invented",
    "each rule appears exactly once",
)


def write_json(path: Path, payload) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def compact(text: str) -> str:
    return "".join(ch for ch in (text or "") if not ch.isspace())


def page_spans(page: pymupdf.Page) -> list[dict]:
    found: list[dict] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if not span.get("text", "").strip():
                    continue
                found.append(
                    {
                        "text": span["text"],
                        "compact": compact(span["text"]),
                        "size": round(float(span.get("size", 0.0)), 2),
                        "font": span.get("font", ""),
                        "bbox": [round(float(v), 2) for v in span.get("bbox", (0, 0, 0, 0))],
                    }
                )
    return found


def raw_segments(page: pymupdf.Page) -> list[dict]:
    """Every thin horizontal drawn segment on the page."""

    segments: list[dict] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        width = float(rect.width)
        height = float(rect.height)
        if height > MAX_RULE_HEIGHT_PT or width < MIN_RULE_WIDTH_PT:
            continue
        segments.append(
            {
                "x0": round(float(rect.x0), 2),
                "x1": round(float(rect.x1), 2),
                "y": round(float((rect.y0 + rect.y1) / 2.0), 2),
                "width": round(width, 2),
            }
        )
    return segments


def merge_segments(segments: list[dict]) -> list[dict]:
    """Fold collinear touching segments into one painted rule."""

    merged: list[dict] = []
    for segment in sorted(segments, key=lambda item: (item["y"], item["x0"])):
        target = None
        for candidate in merged:
            if abs(candidate["y"] - segment["y"]) > Y_NEIGHBOURHOOD_PT:
                continue
            if segment["x0"] - candidate["x1"] > MERGE_GAP_PT:
                continue
            if candidate["x0"] - segment["x1"] > MERGE_GAP_PT:
                continue
            target = candidate
            break
        if target is None:
            merged.append(dict(segment))
            continue
        target["x0"] = round(min(target["x0"], segment["x0"]), 2)
        target["x1"] = round(max(target["x1"], segment["x1"]), 2)
        target["width"] = round(target["x1"] - target["x0"], 2)
        target["parts"] = target.get("parts", 1) + 1
    return sorted(merged, key=lambda item: (item["y"], item["x0"]))


def context_for(spans: list[dict], rule: dict, *, radius: float = 6.0) -> str:
    """Semantic context of a rule: the visible text on its own source line."""

    pieces = []
    for span in spans:
        x0, y0, x1, y1 = span["bbox"]
        if y0 - radius <= rule["y"] <= y1 + radius and span["compact"]:
            pieces.append(span["compact"])
    return "|".join(pieces)[:120]


def classify(rule: dict, spans: list[dict]) -> str:
    """Rule kind from source-local span evidence, not from the semantic role."""

    for span in spans:
        x0, y0, x1, y1 = span["bbox"]
        if not (y0 - 3.0 <= rule["y"] <= y1 + 3.0):
            continue
        if x0 >= rule["x1"] or x1 <= rule["x0"]:
            continue
        body = span["compact"]
        if body and set(body) <= {"_", "＿"}:
            return LITERAL_UNDERSCORE
        if "\u2007" in span["text"] or "\u00a0" in span["text"]:
            return UNDERLINED_WHITESPACE
        if span["text"].strip():
            return VALUE_WITH_UNDERLINE
    return VECTOR_RULE


def underline_spans(page: pymupdf.Page) -> list[dict]:
    """Underlined figure-space runs, measured from the render."""

    found: list[dict] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if "\u2007" not in text and "\u00a0" not in text:
                    continue
                count = text.count("\u2007") + text.count("\u00a0")
                if count < 2:
                    continue
                bbox = [round(float(v), 2) for v in span.get("bbox", (0, 0, 0, 0))]
                found.append(
                    {
                        "x0": bbox[0],
                        "x1": bbox[2],
                        "y": round(bbox[3] - 1.0, 2),
                        "width": round(bbox[2] - bbox[0], 2),
                        "kind": UNDERLINED_WHITESPACE,
                        "figure_spaces": count,
                    }
                )
    return found


def drawn_rules(page: pymupdf.Page, spans: list[dict]) -> list[dict]:
    rules = []
    for rule in merge_segments(raw_segments(page)):
        entry = dict(rule)
        entry.setdefault("parts", 1)
        entry["kind"] = classify(entry, spans)
        entry["context"] = context_for(spans, rule)
        rules.append(entry)
    return rules


def page_rules(page: pymupdf.Page, *, include_underlines: bool) -> list[dict]:
    spans = page_spans(page)
    rules = drawn_rules(page, spans)
    if include_underlines:
        for span in underline_spans(page):
            entry = dict(span)
            entry["parts"] = 1
            entry["context"] = context_for(spans, entry)
            rules.append(entry)
    for rule in rules:
        rule.setdefault("semantic_context", rule.get("context", ""))
    return sorted(rules, key=lambda item: (item["y"], item["x0"]))


def in_body(page: pymupdf.Page, rule: dict) -> bool:
    height = float(page.rect.height)
    return height * CHROME_BAND <= rule["y"] <= height * (1.0 - CHROME_BAND)


def table_grid(page: pymupdf.Page, *, min_rows: int = 3, coverage: float = 120.0) -> dict | None:
    """Outer box, column boundaries and row boundaries of a page table grid.

    A grid is recognised from the page's own drawn rules: several baselines must
    carry a horizontal run of at least ``coverage`` points.  The widest baseline
    run is the table's horizontal extent; every baseline in that band is a row
    boundary and every vertical line inside the box is a column boundary.
    """

    horizontals = merge_segments(raw_segments(page))
    verticals: list[float] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        if rect.width <= MAX_RULE_HEIGHT_PT and rect.height >= 20.0:
            verticals.append(round(float(rect.x0), 2))

    wide = [rule for rule in horizontals if rule["width"] >= coverage]
    if len(wide) < min_rows:
        return None
    x0 = min(rule["x0"] for rule in wide)
    x1 = max(rule["x1"] for rule in wide)
    y0 = min(rule["y"] for rule in wide)
    y1 = max(rule["y"] for rule in wide)
    if x1 - x0 < coverage or y1 - y0 < 20.0:
        return None
    # A page can carry more than one table; keep only the rules that overlap
    # the dominant horizontal extent.
    rows = sorted({rule["y"] for rule in wide if rule["x0"] <= x0 + 2.0})
    columns = sorted(
        value for value in verticals if x0 - 3.0 <= value <= x1 + 3.0
    )
    return {
        "x0": round(x0, 2),
        "x1": round(x1, 2),
        "width": round(x1 - x0, 2),
        "center": round((x0 + x1) / 2.0, 2),
        "top": round(y0, 2),
        "bottom": round(y1, 2),
        "row_boundaries": rows,
        "column_boundaries": columns,
        "column_widths": [
            round(columns[index + 1] - columns[index], 2)
            for index in range(len(columns) - 1)
        ],
        "rule_count": len(wide),
    }


def table_geometry_qa(source_page: pymupdf.Page, generated_page: pymupdf.Page) -> dict:
    source = table_grid(source_page)
    generated = table_grid(generated_page)
    if source is None or generated is None:
        return {
            "status": "TABLE_NOT_FOUND",
            "source": source,
            "generated": generated,
            "source_page": source_page.number + 1,
            "generated_page": generated_page.number + 1,
        }
    source_rows = source["row_boundaries"]
    generated_rows = generated["row_boundaries"]
    drift = [
        round(generated_rows[index] - source_rows[index], 2)
        for index in range(min(len(source_rows), len(generated_rows)))
    ]
    drift_from_top = [
        round(
            (generated_rows[index] - generated["top"]) - (source_rows[index] - source["top"]),
            2,
        )
        for index in range(min(len(source_rows), len(generated_rows)))
    ]
    source_columns = source["column_boundaries"]
    generated_columns = generated["column_boundaries"]
    column_drift = [
        round(generated_columns[index] - source_columns[index], 2)
        for index in range(min(len(source_columns), len(generated_columns)))
    ]
    return {
        "status": "COMPARED",
        "source_page": source_page.number + 1,
        "generated_page": generated_page.number + 1,
        "source": source,
        "generated": generated,
        "table_outer_x0_error": round(generated["x0"] - source["x0"], 2),
        "table_outer_x1_error": round(generated["x1"] - source["x1"], 2),
        "table_center_error": round(generated["center"] - source["center"], 2),
        "table_width_error": round(generated["width"] - source["width"], 2),
        "table_top_y_error": round(generated["top"] - source["top"], 2),
        "table_bottom_y_error": round(generated["bottom"] - source["bottom"], 2),
        "row_boundary_drift": drift,
        "cumulative_row_height_drift": round(
            (generated["bottom"] - generated["top"]) - (source["bottom"] - source["top"]), 2
        ),
        "row_boundary_drift_from_table_top": drift_from_top,
        "column_boundary_drift": column_drift,
    }


def mandatory_rule_kinds(page: pymupdf.Page) -> set[str]:
    """Kinds that must be reproduced one-to-one on a form/letter page."""

    kinds = {VECTOR_RULE, UNDERLINED_WHITESPACE, LITERAL_UNDERSCORE}
    return kinds


def _distance(source_rule: dict, generated_rule: dict, normalization: dict) -> float | None:
    dx = normalization.get("dx", 0.0)
    dy = normalization.get("dy", 0.0)
    y_error = abs((generated_rule["y"] - dy) - source_rule["y"])
    x0_error = abs((generated_rule["x0"] - dx) - source_rule["x0"])
    x1_error = abs((generated_rule["x1"] - dx) - source_rule["x1"])
    if (
        y_error > MANDATORY_TOLERANCE_PT
        or x0_error > MANDATORY_TOLERANCE_PT
        or x1_error > MANDATORY_TOLERANCE_PT
    ):
        return None
    return y_error + x0_error + x1_error


#: A rule wider than this is a table row separator or a full-width form line,
#: not a standalone fillable blank.
WIDE_RULE_WIDTH_PT = 340.0

#: A generated rule and a source rule below this vertical distance are candidates
#: for the same physical blank; they still have to satisfy the geometry test.
BLANK_CANDIDATE_Y_PT = 12.0

#: Horizontal slack for the same physical blank: a rule may be re-laid-out a few
#: points sideways inside its own source line before it is a different blank.
BLANK_CANDIDATE_X_PT = 30.0

#: Overlap fraction of the source rule a generated rule must cover to be the
#: same physical blank.
BLANK_OVERLAP_RATIO = 0.6


def is_form_rule(rule: dict) -> bool:
    """A standalone fillable/rule blank, not a table row separator."""

    return rule["width"] < WIDE_RULE_WIDTH_PT


#: A table's own bottom border can be narrower than its widest row separator
#: (a merged last row); a rule this close below the table band still belongs to
#: the table.
TABLE_TAIL_PT = 45.0


def document_table_boxes(path: Path) -> dict[int, list[tuple[float, float, float, float]]]:
    """Source table rectangles per page, straight from the document model.

    Using the document model's own table detection (rather than a geometric
    guess) is what keeps a table's row separators out of the fillable-blank
    inventory.
    """

    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    boxes: dict[int, list[tuple[float, float, float, float]]] = {}
    for table in payload.get("tables", []) or []:
        bbox = table.get("bbox")
        page = table.get("page")
        if not bbox or page is None or len(bbox) < 4:
            continue
        boxes.setdefault(int(page), []).append(
            (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        )
    return boxes


def table_region(page: pymupdf.Page) -> dict | None:
    """The page's table band, measured from the page's own drawn rules.

    The band is the vertical run of rules that share the table's horizontal
    extent: every drawn rule whose span sits inside the widest rule's extent
    and follows it within ``TABLE_TAIL_PT`` belongs to the table.  Separating
    the band is what makes form-blank matching possible - a table's own row
    separators are not fillable blanks and must not be compared as if they were.
    """

    horizontals = merge_segments(raw_segments(page))
    if not horizontals:
        return None
    widest = max(horizontals, key=lambda rule: rule["width"])
    if widest["width"] < 120.0:
        return None
    x0, x1 = widest["x0"], widest["x1"]
    band = [rule for rule in horizontals if rule["x0"] >= x0 - 3.0 and rule["x1"] <= x1 + 3.0]
    if len(band) < 3:
        return None
    band.sort(key=lambda rule: rule["y"])
    top = band[0]["y"]
    bottom = band[-1]["y"]
    tail_top = bottom - 3.0
    for rule in horizontals:
        if rule["y"] <= tail_top or rule["y"] > bottom + TABLE_TAIL_PT:
            continue
        if rule["x1"] < x0 + 8.0 or rule["x0"] > x1 - 8.0:
            continue
        bottom = max(bottom, rule["y"])
    return {
        "x0": round(x0, 2),
        "x1": round(x1, 2),
        "top": round(top, 2),
        "bottom": round(bottom, 2),
        "rule_count": len(band),
    }


def _inside_table(rule: dict, region: dict | None) -> bool:
    if region is None:
        return False
    return (
        region["top"] - 2.0 <= rule["y"] <= region["bottom"] + 2.0
        and rule["x0"] >= region["x0"] - 6.0
        and rule["x1"] <= region["x1"] + 6.0
    )


def normalise_render_rules(rules: list[dict]) -> list[dict]:
    """Collapse the renderer's own segmentation of one painted mark.

    A Word renderer can paint a single underlined region as several underline
    marks plus a drawn border segment at the same baseline and extent.  They are
    one visible rule, so they are folded into one before matching; this is a
    modelling correction of the renderer's segmentation, not a widened
    tolerance - geometry is still compared exactly afterwards.
    """

    ordered = sorted(rules, key=lambda rule: (rule["y"], rule["x0"]))
    grouped: list[dict] = []
    for rule in ordered:
        target = None
        for candidate in grouped:
            if abs(candidate["y"] - rule["y"]) > MERGE_GAP_PT:
                continue
            if (
                rule["x0"] <= candidate["x1"] + MERGE_GAP_PT
                and candidate["x0"] <= rule["x1"] + MERGE_GAP_PT
            ):
                target = candidate
                break
        if target is None:
            grouped.append(dict(rule, parts=int(rule.get("parts", 1))))
            continue
        target["x0"] = round(min(target["x0"], rule["x0"]), 2)
        target["x1"] = round(max(target["x1"], rule["x1"]), 2)
        target["width"] = round(target["x1"] - target["x0"], 2)
        target["parts"] = int(target.get("parts", 1)) + int(rule.get("parts", 1))
        if rule.get("kind") == VECTOR_RULE and target.get("kind") != VECTOR_RULE:
            target["kind"] = rule["kind"]
    return sorted(grouped, key=lambda rule: (rule["y"], rule["x0"]))


def form_rule_inventory(
    page: pymupdf.Page,
    *,
    underlines: bool,
    table_boxes: list[tuple[float, float, float, float]] | None = None,
) -> dict:
    """Fillable-blank rule inventory: every visible rule that is not a table's.

    The table regions come from the document model's own table detection (the
    PDF table detector for the source, the measured table grid for the
    generated render).  A table's row separators are not fillable blanks and
    must never be matched as if they were.
    """

    rules = normalise_render_rules(
        [
            rule
            for rule in page_rules(page, include_underlines=underlines)
            if not any(
                box[0] - 6.0 <= rule["x0"]
                and rule["x1"] <= box[2] + 6.0
                and box[1] - 2.0 <= rule["y"] <= box[3] + 2.0
                for box in (table_boxes or [])
            )
        ]
    )
    return {"rules": rules, "table_boxes": table_boxes or [], "rule_count": len(rules)}


def match_blank_rules(
    source_rules: list[dict],
    generated_rules: list[dict],
    *,
    raw_source_rules: list[dict] | None = None,
    raw_generated_rules: list[dict] | None = None,
    transformed_slots: list[dict] | None = None,
) -> dict:
    """One-to-one matching of *fillable* rule blanks.

    The returned inventory is a strict one-to-one partition, so an inconsistent
    report cannot be emitted:

    * ``normalized_source_rule_count == exact_matched_rule_count
      + transformed_matched_rule_count + lost_source_rule_count``
    * ``normalized_generated_rule_count == exact_matched_rule_count
      + transformed_matched_rule_count + invented_rule_count``
    * every source rule appears exactly once across
      ``pairs``/``transformed``/``lost``
    * every generated rule appears exactly once across
      ``pairs``/``transformed``/``invented``

    ``transformed_slots`` declares source slots whose representation is
    *expected* to change shape because a resolved value replaced a placeholder.
    For such a slot a generated rule that starts at the source slot start and
    stays within the slot band is a ``TRANSFORMED_MATCH`` instead of a
    lost+invented pair.  The exception is never inferred from a mismatch: it
    must be declared here with the slot's source rule span, its transformation
    policy and its geometry policy.

    A source rule and a generated rule that *are* the same physical blank but
    whose geometry is outside the mandatory tolerance are still a matched pair
    (the delivery did draw the blank); they are reported in ``displaced`` and
    ``matched_out_of_tolerance_count`` instead of being counted as both matched
    and lost.  The mandatory geometry gate is
    ``mandatory_geometry_ok`` on each pair.

    ``raw_source_rules``/``raw_generated_rules`` record the pre-folding
    inventories so a folded (MANY_TO_ONE) render is documented rather than
    silently absorbed.
    """

    normalized_source = [rule for rule in source_rules if is_form_rule(rule)]
    raw_source = list(raw_source_rules) if raw_source_rules is not None else list(source_rules)
    raw_generated = (
        list(raw_generated_rules) if raw_generated_rules is not None else list(generated_rules)
    )
    matched_source: set[int] = set()
    matched_generated: set[int] = set()
    pairs: list[dict] = []
    for generated_index, generated in enumerate(generated_rules):
        best = None
        for source_index, source in enumerate(normalized_source):
            if source_index in matched_source:
                continue
            dy = abs(generated["y"] - source["y"])
            if dy > BLANK_CANDIDATE_Y_PT:
                continue
            dx0 = abs(generated["x0"] - source["x0"])
            dx1 = abs(generated["x1"] - source["x1"])
            if dx0 > BLANK_CANDIDATE_X_PT and dx1 > BLANK_CANDIDATE_X_PT:
                overlap = min(generated["x1"], source["x1"]) - max(
                    generated["x0"], source["x0"]
                )
                if overlap <= 0 or overlap / max(1.0, source["width"]) < BLANK_OVERLAP_RATIO:
                    continue
            score = dy + min(dx0, dx1)
            if best is None or score < best[0]:
                best = (score, source_index)
        if best is None:
            continue
        source = normalized_source[best[1]]
        matched_source.add(best[1])
        matched_generated.add(generated_index)
        pairs.append(
            {
                "semantic_context": source.get("semantic_context") or source.get("context"),
                "source_page": source.get("source_page"),
                "source": source,
                "generated": generated,
                "source_kind": source["kind"],
                "generated_kind": generated["kind"],
                "source_x0": source["x0"],
                "generated_x0": generated["x0"],
                "x0_error": round(generated["x0"] - source["x0"], 2),
                "source_x1": source["x1"],
                "generated_x1": generated["x1"],
                "x1_error": round(generated["x1"] - source["x1"], 2),
                "source_y": source["y"],
                "generated_y": generated["y"],
                "y_error": round(generated["y"] - source["y"], 2),
                "mandatory_geometry_ok": (
                    abs(generated["y"] - source["y"]) <= MANDATORY_TOLERANCE_PT
                    and abs(generated["x0"] - source["x0"]) <= MANDATORY_TOLERANCE_PT
                    and abs(generated["x1"] - source["x1"]) <= MANDATORY_TOLERANCE_PT
                ),
                "kind_compatible": (
                    source["kind"] == generated["kind"]
                    or {source["kind"], generated["kind"]} <= SAME_VISUAL_RULE
                ),
                "match_type": "EXACT_MATCH",
            }
        )
    # ---- declared slot transformations ------------------------------------
    transformed: list[dict] = []
    for slot in transformed_slots or []:
        source_index = _declared_slot_source_index(normalized_source, matched_source, slot)
        if source_index is None:
            continue
        generated_index = _declared_slot_generated_index(
            generated_rules, matched_generated, slot
        )
        if generated_index is None:
            continue
        source_rule = normalized_source[source_index]
        generated_rule = generated_rules[generated_index]
        matched_source.add(source_index)
        matched_generated.add(generated_index)
        transformed.append(_transformed_record(source_rule, generated_rule, slot))
    # Exactly one entry per source rule and per generated rule: the partition is
    # a total function over both inventories, which is what makes the reported
    # counts close by construction.
    lost = [
        rule for index, rule in enumerate(normalized_source) if index not in matched_source
    ]
    invented = [
        rule for index, rule in enumerate(generated_rules) if index not in matched_generated
    ]
    displaced = [pair for pair in pairs if not pair["mandatory_geometry_ok"]]
    result = {
        "pairs": pairs,
        "transformed": transformed,
        "displaced": displaced,
        "lost": lost,
        "invented": invented,
        "kind_mismatch": [pair for pair in pairs if not pair["kind_compatible"]],
        "raw_source_rule_count": len(raw_source),
        "raw_generated_rule_count": len(raw_generated),
        "normalized_source_rule_count": len(normalized_source),
        "normalized_generated_rule_count": len(generated_rules),
        "source_rule_count": len(normalized_source),
        "generated_rule_count": len(generated_rules),
        "matched_rule_count": len(pairs) + len(transformed),
        "exact_matched_rule_count": len(pairs),
        "transformed_matched_rule_count": len(transformed),
        "lost_source_rule_count": len(lost),
        "invented_rule_count": len(invented),
        "displaced_rule_count": len(displaced),
        "matched_out_of_tolerance_count": len(displaced),
        "rule_kind_mismatch_count": sum(
            1 for pair in pairs if not pair["kind_compatible"]
        ),
        "rule_x0_error_max": round(max((abs(p["x0_error"]) for p in pairs), default=0.0), 2),
        "rule_x1_error_max": round(max((abs(p["x1_error"]) for p in pairs), default=0.0), 2),
        "rule_y_error_max": round(max((abs(p["y_error"]) for p in pairs), default=0.0), 2),
    }
    result["accounting_invariant_failures"] = rule_accounting_failures(result)
    return result


def _declared_slot_source_index(normalized_source, matched_source, slot) -> int | None:
    """The unmatched source rule that *is* the declared slot, by exact span."""

    for index, rule in enumerate(normalized_source):
        if index in matched_source:
            continue
        if (
            abs(float(rule["x0"]) - float(slot["source_x0"])) <= 1.0
            and abs(float(rule["x1"]) - float(slot["source_x1"])) <= 1.0
            and abs(float(rule["y"]) - float(slot["source_y"])) <= 1.0
        ):
            return index
    return None


def _declared_slot_generated_index(generated_rules, matched_generated, slot) -> int | None:
    """The unmatched generated rule that carries the declared slot's value.

    It must start at the source slot anchor within the declared anchor
    tolerance, and lie within the slot's own content band.  Nothing else is
    eligible, so an unrelated rule can never be absorbed as a transformation.
    """

    band = float(slot.get("y_band_pt", BLANK_CANDIDATE_Y_PT))
    tolerance = float(slot.get("anchor_tolerance_pt", MANDATORY_TOLERANCE_PT))
    source_x0 = float(slot["source_x0"])
    source_y = float(slot["source_y"])
    best_index = None
    best_score = None
    for index, rule in enumerate(generated_rules):
        if index in matched_generated:
            continue
        if abs(float(rule["x0"]) - source_x0) > tolerance:
            continue
        if abs(float(rule["y"]) - source_y) > band:
            continue
        score = abs(float(rule["y"]) - source_y) + abs(float(rule["x0"]) - source_x0)
        if best_score is None or score < best_score:
            best_score = score
            best_index = index
    return best_index


def _transformed_record(source_rule, generated_rule, slot) -> dict:
    """A declared placeholder-to-value transformation, fully accounted."""

    tolerance = float(slot.get("anchor_tolerance_pt", MANDATORY_TOLERANCE_PT))
    return {
        "semantic_context": source_rule.get("semantic_context") or source_rule.get("context"),
        "source_page": source_rule.get("source_page"),
        "source": source_rule,
        "generated": generated_rule,
        "source_kind": source_rule["kind"],
        "generated_kind": generated_rule["kind"],
        "source_x0": source_rule["x0"],
        "generated_x0": generated_rule["x0"],
        "x0_error": round(generated_rule["x0"] - source_rule["x0"], 2),
        "source_x1": source_rule["x1"],
        "generated_x1": generated_rule["x1"],
        "x1_error": round(generated_rule["x1"] - source_rule["x1"], 2),
        "source_y": source_rule["y"],
        "generated_y": generated_rule["y"],
        "y_error": round(generated_rule["y"] - source_rule["y"], 2),
        "transformation_policy": slot.get("transformation_policy"),
        "geometry_policy": slot.get("geometry_policy"),
        "fact_field": slot.get("fact_field"),
        "expected_value": slot.get("expected_value"),
        "anchor_ok": abs(generated_rule["x0"] - source_rule["x0"]) <= tolerance,
        "within_source_slot": (
            generated_rule["x1"] <= source_rule["x1"] + MANDATORY_TOLERANCE_PT
        ),
        "match_type": "TRANSFORMED_MATCH",
    }


def rule_accounting_failures(report: dict) -> list[str]:
    """Every way a rule-matching report's one-to-one accounting can be wrong."""

    failures: list[str] = []
    source = int(report.get("normalized_source_rule_count", report.get("source_rule_count", 0)))
    generated = int(
        report.get("normalized_generated_rule_count", report.get("generated_rule_count", 0))
    )
    matched = int(report.get("matched_rule_count", 0))
    exact = int(report.get("exact_matched_rule_count", matched))
    transformed = int(report.get("transformed_matched_rule_count", 0))
    lost = int(report.get("lost_source_rule_count", 0))
    invented = int(report.get("invented_rule_count", 0))
    if matched != exact + transformed:
        failures.append(
            f"matched({matched}) != exact({exact}) + transformed({transformed})"
        )
    if source != exact + transformed + lost:
        failures.append(
            f"normalized_source_rule_count({source}) != exact({exact})"
            f" + transformed({transformed}) + lost({lost})"
        )
    if generated != exact + transformed + invented:
        failures.append(
            f"normalized_generated_rule_count({generated}) != exact({exact})"
            f" + transformed({transformed}) + invented({invented})"
        )
    if len(report.get("lost", [])) != lost:
        failures.append("lost_source_rule_count does not equal len(lost)")
    if len(report.get("invented", [])) != invented:
        failures.append("invented_rule_count does not equal len(invented)")
    if len(report.get("pairs", [])) != exact:
        failures.append("exact_matched_rule_count does not equal len(pairs)")
    if len(report.get("transformed", [])) != transformed:
        failures.append("transformed_matched_rule_count does not equal len(transformed)")
    all_matches = list(report.get("pairs", [])) + list(report.get("transformed", []))
    pair_source_ids = [
        (
            pair.get("source", {}).get("kind"),
            pair.get("source", {}).get("x0"),
            pair.get("source", {}).get("x1"),
            pair.get("source", {}).get("y"),
        )
        for pair in all_matches
    ]
    if len(set(pair_source_ids)) != matched:
        failures.append("a source rule is matched more than once")
    pair_generated_ids = [
        (
            pair.get("generated", {}).get("kind"),
            pair.get("generated", {}).get("x0"),
            pair.get("generated", {}).get("x1"),
            pair.get("generated", {}).get("y"),
        )
        for pair in all_matches
    ]
    if len(set(pair_generated_ids)) != matched:
        failures.append("a generated rule is matched more than once")
    return failures


def match_rules(
    source_rules: list[dict],
    generated_rules: list[dict],
    *,
    normalization: dict | None = None,
) -> dict:
    """One-to-one source/generated rule matching.

    Match quality is (page/region, semantic context, vertical neighbourhood,
    horizontal geometry).  A mandatory source rule is matched only inside the
    round tolerance; nothing is matched by count.
    """

    normalization = normalization or {}
    matched_source: set[int] = set()
    matched_generated: set[int] = set()
    pairs: list[dict] = []
    for source_index, source_rule in enumerate(source_rules):
        best = None
        for generated_index, generated_rule in enumerate(generated_rules):
            if generated_index in matched_generated:
                continue
            score = _distance(source_rule, generated_rule, normalization)
            if score is None:
                continue
            if best is None or score < best[0]:
                best = (score, generated_index)
        if best is None:
            continue
        generated = generated_rules[best[1]]
        matched_source.add(source_index)
        matched_generated.add(best[1])
        same_context = bool(
            source_rule.get("context")
            and generated.get("context")
            and (
                source_rule["context"] == generated["context"]
                or source_rule["context"] in generated["context"]
                or generated["context"] in source_rule["context"]
            )
        )
        kind_compatible = (
            source_rule["kind"] == generated["kind"]
            or {source_rule["kind"], generated["kind"]} <= SAME_VISUAL_RULE
        )
        pairs.append(
            {
                "source": source_rule,
                "generated": generated,
                "y_error": round(generated["y"] - source_rule["y"], 2),
                "x0_error": round(generated["x0"] - source_rule["x0"], 2),
                "x1_error": round(generated["x1"] - source_rule["x1"], 2),
                "width_error": round(generated["width"] - source_rule["width"], 2),
                "context_match": same_context,
                "kind_compatible": kind_compatible,
            }
        )
    lost = [rule for index, rule in enumerate(source_rules) if index not in matched_source]
    invented = [
        rule for index, rule in enumerate(generated_rules) if index not in matched_generated
    ]
    kind_mismatch = [pair for pair in pairs if not pair["kind_compatible"]]
    return {
        "pairs": pairs,
        "lost": lost,
        "invented": invented,
        "kind_mismatch": kind_mismatch,
        "source_rule_count": len(source_rules),
        "generated_rule_count": len(generated_rules),
        "matched_rule_count": len(pairs),
        "lost_source_rule_count": len(lost),
        "invented_rule_count": len(invented),
        "rule_kind_mismatch_count": len(kind_mismatch),
        "rule_x0_error_max": round(max((abs(p["x0_error"]) for p in pairs), default=0.0), 2),
        "rule_x1_error_max": round(max((abs(p["x1_error"]) for p in pairs), default=0.0), 2),
        "rule_y_error_max": round(max((abs(p["y_error"]) for p in pairs), default=0.0), 2),
        "rule_width_error_median": round(
            median([abs(p["width_error"]) for p in pairs]), 2
        )
        if pairs
        else None,
    }


def region_rules(page: pymupdf.Page, box: tuple[float, float, float, float], *, underlines: bool) -> list[dict]:
    rules = page_rules(page, include_underlines=underlines)
    return [
        rule
        for rule in rules
        if box[0] <= rule["x0"] and rule["x1"] <= box[2] and box[1] <= rule["y"] <= box[3]
    ]


def anchor_box(page: pymupdf.Page, needle: str) -> list[float] | None:
    target = compact(needle)
    for span in page_spans(page):
        if target and target in span["compact"]:
            return span["bbox"]
    return None


def line_box(
    page: pymupdf.Page, needle: str, *, occurrence: int = 0, exact: bool = False
) -> list[float] | None:
    """Bounding box of the ``occurrence``-th source line whose text is/contains ``needle``.

    A logical source line can be split into several spans, so the *line* is the
    honest anchor: this measures the visible line the anchor text sits on.
    """

    target = compact(needle)
    if not target:
        return None
    seen = 0
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = compact("".join(span.get("text", "") for span in line.get("spans", [])))
            if not text:
                continue
            hit = text == target if exact else target in text
            if not hit:
                continue
            if seen == occurrence:
                return [
                    round(float(v), 2) for v in line.get("bbox", (0, 0, 0, 0))
                ]
            seen += 1
    return None


def span_bbox(page: pymupdf.Page, needle: str) -> list[float] | None:
    return anchor_box(page, needle)


def vertical_anchor_qa(
    source_page: pymupdf.Page,
    generated_page: pymupdf.Page,
    anchors: list[tuple],
) -> dict:
    """Measure mandatory vertical anchors.

    ``anchors`` items are ``(role, needle, occurrence, exact)``.  Both the
    source and the generated page are searched for the same source line, so a
    reported error is a real position error between the two renders.
    """

    rows = []
    for role, needle, occurrence, exact in anchors:
        source_box = line_box(source_page, needle, occurrence=occurrence, exact=exact)
        generated_box = line_box(generated_page, needle, occurrence=occurrence, exact=exact)
        row = {
            "role": role,
            "anchor": needle,
            "source_y": source_box[1] if source_box else None,
            "generated_y": generated_box[1] if generated_box else None,
            "source_x": source_box[0] if source_box else None,
            "generated_x": generated_box[0] if generated_box else None,
            "source_bbox": source_box,
            "generated_bbox": generated_box,
        }
        if source_box and generated_box:
            row["y_error"] = round(generated_box[1] - source_box[1], 2)
            row["x_error"] = round(generated_box[0] - source_box[0], 2)
        else:
            row["y_error"] = None
            row["x_error"] = None
            row["status"] = "ANCHOR_MISSING"
        rows.append(row)
    errors = [row["y_error"] for row in rows if row["y_error"] is not None]
    x_errors = [row["x_error"] for row in rows if row["x_error"] is not None]
    return {
        "page_source": source_page.number + 1,
        "page_generated": generated_page.number + 1,
        "anchor_count": len(rows),
        "y_error_max": round(max((abs(v) for v in errors), default=0.0), 2),
        "y_error_median": round(median([abs(v) for v in errors]), 2) if errors else None,
        "x_error_max": round(max((abs(v) for v in x_errors), default=0.0), 2),
        "anchors": rows,
    }


def docx_table_properties(docx: Path) -> list[dict]:
    """Declared table geometry straight from the generated Word package."""

    from docx import Document
    from docx.oxml.ns import qn

    document = Document(str(docx))
    records = []
    for index, table in enumerate(document.tables):
        tbl_pr = table._tbl.tblPr
        grid = [
            int(column.get(qn("w:w")))
            for column in table._tbl.tblGrid.findall(qn("w:gridCol"))
        ]

        def prop(name: str) -> dict:
            element = tbl_pr.find(qn(name))
            if element is None:
                return {}
            return {
                key.rsplit("}", 1)[-1]: value for key, value in element.attrib.items()
            }

        width = prop("w:tblW")
        indent = prop("w:tblInd")
        records.append(
            {
                "table_index": index,
                "tblW": width,
                "tblW_pt": round(int(width.get("w", 0)) / 20.0, 2) if width else None,
                "tblInd": indent,
                "tblInd_pt": round(int(indent.get("w", 0)) / 20.0, 2) if indent else None,
                "jc": prop("w:jc").get("val"),
                "tblLayout": prop("w:tblLayout").get("type"),
                "grid_dxa": grid,
                "grid_pt": [round(value / 20.0, 2) for value in grid],
                "grid_total_pt": round(sum(grid) / 20.0, 2),
                "row_count": len(table.rows),
                "column_count": len(table.columns),
            }
        )
    return records


__all__ = [
    "MANDATORY_TOLERANCE_PT",
    "MATCH_INVARIANTS",
    "anchor_box",
    "classify",
    "compact",
    "context_for",
    "docx_table_properties",
    "document_table_boxes",
    "drawn_rules",
    "form_rule_inventory",
    "in_body",
    "match_rules",
    "merge_segments",
    "page_rules",
    "page_spans",
    "raw_segments",
    "region_rules",
    "rule_accounting_failures",
    "table_geometry_qa",
    "table_grid",
    "underline_spans",
    "vertical_anchor_qa",
    "write_json",
]
