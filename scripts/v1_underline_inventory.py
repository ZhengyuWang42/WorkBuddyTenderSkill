"""Stage C: full underline inventory for one generated delivery.

The inventory answers one question about the response-letter page: *for every
underline the source PDF drew on that page, is there exactly one emitted
underline in the generated PDF, at the source's own geometry?*

It is deliberately measured from the two PDFs - the source render and the
generated render - rather than from the emitter's own bookkeeping, so it can
detect a rule the emitter believes it wrote but that never reached the page, and
a painted rule no source rule explains.

Authority for the comparison is the rule's own recorded geometry intent, which is
part of the frozen horizontal contract:

``EXACT_SOURCE_SPAN``
    both the start and the end of the painted rule are gated against the source.

``ANCHOR_START_ONLY``
    only the start is gated.  The rule's own placeholder was replaced by a
    resolved value, and the value's own extent - which may wrap across several
    generated lines - is what the underline must cover, so the source's end x is
    not a valid target.  A wrapped continuation is claimed by the rule whose
    anchor it continues, starting as it does at the paragraph's line origin.

Nothing in the comparison is keyed to a case name, a page number, a rule id or a
literal value: the measured party is the source PDF, and the page under audit is
derived from the build's own record of which source page carried the form lines
that needed independent horizontal geometry.

Usage::

    python scripts/v1_underline_inventory.py \\
        --build acceptance/workspace/case_001/v1_manual_fidelity_round2 \\
        --source-pdf acceptance/private/<source>.pdf \\
        --out acceptance/reports/v1_generalization/case001_underline_inventory.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymupdf  # noqa: E402

from tender_basic.geometry_rule_qa import in_body, page_rules  # noqa: E402

SCHEMA = "v1_underline_inventory/1"

#: The frozen horizontal tolerance.  It is not relaxed here: a rule that does not
#: land inside it is reported as out of tolerance, not rounded into agreement.
TOLERANCE_PT = 2.0

#: A wrapped continuation must follow its anchor within this many line pitches to
#: be claimed as the same logical underline rather than a separate rule.
MAX_CONTINUATION_LINE_PITCHES = 2.5

GATED_BOTH = "START_AND_END"
GATED_START_ONLY = "START_ONLY"

#: Greatest gap between two painted segments on one line that still belong to the
#: same wrapped value: a resolved value the source wrapped is underlined across
#: the word space that broke it, and the break shows up as a gap of a few points.
SAME_LINE_CONTINUATION_GAP_PT = 6.0

#: Shortest painted segment that can be a rule rather than a table border hair.
MIN_PAINTED_WIDTH_PT = 2.0
#: A drawn segment counts as part of a rule when its midpoint falls inside the
#: rule's own window - the frozen source span widened by the tolerance.  A
#: neighbouring glyph's underline overlaps a blank's underline by a few tenths of
#: a point, so the window decides which ink belongs to which rule, and the rule's
#: painted span is the union of the segments inside its own window.
WINDOW_SEGMENT_MAX_HEIGHT_PT = 2.4


def _load(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _raw_segments(page) -> list[dict]:
    """Every horizontal painted segment on the page, unmerged.

    ``geometry_rule_qa`` merges neighbouring underlines into one logical rule,
    which answers "is this line underlined" but not "how wide is this blank": the
    delivered blank's own underline and the next glyph's underline touch, and the
    merged span is wider than the rule the source drew.  The measurement therefore
    reads the page's own drawn segments and lets each source rule's window claim
    the segments that are its ink.
    """

    segments: list[dict] = []
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                start, end = item[1], item[2]
                if abs(float(start.y) - float(end.y)) > 0.6:
                    continue
                x0 = min(float(start.x), float(end.x))
                x1 = max(float(start.x), float(end.x))
                y = (float(start.y) + float(end.y)) / 2.0
            elif item[0] == "re":
                rect = item[1]
                if float(rect.height) > WINDOW_SEGMENT_MAX_HEIGHT_PT:
                    continue
                x0, x1, y = float(rect.x0), float(rect.x1), float(rect.y0)
            else:
                continue
            if x1 - x0 < MIN_PAINTED_WIDTH_PT:
                continue
            segments.append({"x0": x0, "x1": x1, "y": y, "width": x1 - x0})
    segments.sort(key=lambda item: (item["y"], item["x0"]))
    return segments


def _merge_contiguous(segments: list[dict]) -> list[dict]:
    """Join segments that touch on one line into the span they paint together.

    The join only ever moves forward: a segment that starts left of the run it
    would join is a different rule's ink on a line a fraction of a point away, not
    the continuation of this run.
    """

    merged: list[dict] = []
    for segment in sorted(segments, key=lambda item: (item["y"], item["x0"])):
        if merged:
            last = merged[-1]
            if (
                abs(last["y1"] - segment["y"]) <= 0.8
                and last["x1"] - 0.05 <= segment["x0"] <= last["x1"] + 0.6
            ):
                last["x1"] = max(last["x1"], segment["x1"])
                last["width"] = last["x1"] - last["x0"]
                last["y"] = min(last["y"], segment["y"])
                continue
        merged.append(
            {
                "x0": segment["x0"],
                "x1": segment["x1"],
                "y": segment["y"],
                "y1": segment["y"],
                "width": segment["width"],
            }
        )
    return merged


def _generated_page_text_lines(page) -> list[float]:
    """Top edges of the page's text lines, in drawing order."""

    tops: list[float] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            if "".join(span.get("text", "") for span in line.get("spans", [])).strip():
                tops.append(round(float(line["bbox"][1]), 2))
    return sorted(tops)


def _rules(page) -> list[dict]:
    return [rule for rule in page_rules(page, include_underlines=True) if in_body(page, rule)]


def _response_letter_source_page(report: dict) -> int:
    """The source page the build itself recorded as carrying isolated form lines.

    The response letter's fill rules are the ones whose source visual line needed
    an independent horizontal geometry, so the build records exactly that page -
    once as the form-line paragraphs those rules own, and, where the element is
    one flowing paragraph instead, as the assembly gaps of the rows the flow
    places.  Both records name the same page, so either is read.  A build with
    no such record falls back to the source page carrying the most underlines.
    """

    for key in (
        "source_form_line_paragraphs",
        "structural_isolation_rows",
        "source_visual_line_assembly_gaps",
    ):
        pages = [
            int(entry["source_page"])
            for entry in report.get(key, [])
            if entry.get("source_page") is not None
        ]
        if pages:
            return max(set(pages), key=pages.count)
    return 0


def _source_rules_for_page(source_doc, page_number: int) -> list[dict]:
    page = source_doc[page_number - 1]
    return sorted(_rules(page), key=lambda item: (float(item["y"]), float(item["x0"])))


def _registry_intent(report: dict, page_number: int) -> list[dict]:
    return [
        entry
        for entry in report.get("source_rule_registry", [])
        if int(entry.get("source_page", -1)) == int(page_number)
    ]


def _intent_for(rule: dict, registry: list[dict]) -> dict | None:
    for entry in registry:
        if (
            abs(float(entry["x0"]) - float(rule["x0"])) <= TOLERANCE_PT
            and abs(float(entry["x1"]) - float(rule["x1"])) <= TOLERANCE_PT
        ):
            return entry
    return None


def _gated_axis(intent: dict | None) -> str:
    if intent is None:
        return GATED_BOTH
    if str(intent.get("geometry_intent", "")) == "ANCHOR_START_ONLY":
        return GATED_START_ONLY
    return GATED_BOTH


def _find_generated_page(generated_doc, source_rules: list[dict]) -> int:
    """The generated page that carries this source page's rules.

    The mapping is measured, not assumed: the generated page whose painted
    underline starts agree with the most source rules is the page that renders
    them.  No page index is hard-coded anywhere.
    """

    best_index, best_score = 0, -1
    for index in range(generated_doc.page_count):
        painted = _merge_contiguous(_raw_segments(generated_doc[index]))
        score = sum(
            1
            for source in source_rules
            if any(
                abs(float(item["x0"]) - float(source["x0"])) <= TOLERANCE_PT
                for item in painted
            )
        )
        if score > best_score:
            best_index, best_score = index, score
    return best_index


def _claimed_span(segments: list[dict], source: dict) -> dict | None:
    """The ink a source rule owns: the segments inside the rule's own window.

    A rule's window is its frozen source span widened by the tolerance.  A
    segment belongs to the rule when its midpoint falls inside that window - which
    is how a blank's underline is told apart from the next glyph's underline that
    touches it - and the rule's painted span is the union of its own segments, so
    a rule the emitter painted as several segments (a composed rule's empty
    segments, a leader plus its end) measures as the one span the source drew.
    """

    x0 = float(source["x0"]) - TOLERANCE_PT
    x1 = float(source["x1"]) + TOLERANCE_PT
    owned = [
        segment
        for segment in segments
        if x0 <= (float(segment["x0"]) + float(segment["x1"])) / 2.0 <= x1
    ]
    if not owned:
        return None
    return {
        "x0": min(float(segment["x0"]) for segment in owned),
        "x1": max(float(segment["x1"]) for segment in owned),
        "y": min(float(segment["y"]) for segment in owned),
        "segments": [
            {
                "x0": round(float(segment["x0"]), 2),
                "x1": round(float(segment["x1"]), 2),
                "y": round(float(segment["y"]), 2),
            }
            for segment in owned
        ],
    }


def _nearest_span(segments: list[dict], source: dict) -> dict | None:
    """The painted span closest to a rule that owns no ink in its own window.

    A rule whose window holds nothing is reported with the nearest ink and both
    endpoint deviations, so a lost rule is diagnosable instead of an empty record.
    """

    best = None
    for segment in segments:
        start = abs(float(segment["x0"]) - float(source["x0"]))
        end = abs(float(segment["x1"]) - float(source["x1"]))
        deviation = min(start, end)
        if best is None or deviation < best["deviation"]:
            best = {
                "x0": float(segment["x0"]),
                "x1": float(segment["x1"]),
                "y": float(segment["y"]),
                "segments": [
                    {
                        "x0": round(float(segment["x0"]), 2),
                        "x1": round(float(segment["x1"]), 2),
                        "y": round(float(segment["y"]), 2),
                    }
                ],
                "deviation": deviation,
            }
    return best


def _line_origins(page) -> list[float]:
    lefts: list[float] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            if text.strip():
                lefts.append(round(float(line["bbox"][0]), 2))
    return sorted(set(lefts))


def build_inventory(
    build_dir: Path,
    source_pdf: Path,
    *,
    label: str = "",
) -> dict:
    report = _load(build_dir / "generation_report.json")
    manifest = _load(build_dir / "build_manifest.json")
    source_doc = pymupdf.open(str(source_pdf))
    generated_path = Path(manifest["generated"]["pdf"])
    if not generated_path.is_absolute():
        generated_path = (ROOT / generated_path).resolve()
    generated_doc = pymupdf.open(str(generated_path))

    page_number = _response_letter_source_page(report)
    source_rules = _source_rules_for_page(source_doc, page_number)
    registry = _registry_intent(report, page_number)
    generated_index = _find_generated_page(generated_doc, source_rules)
    generated_page = generated_doc[generated_index]
    painted = _merge_contiguous(
        [
            segment
            for segment in _raw_segments(generated_page)
            if in_body(generated_page, segment)
        ]
    )
    kinds = page_rules(generated_page, include_underlines=True)
    text_tops = _generated_page_text_lines(generated_page)
    line_origins = _line_origins(generated_page)

    def _kind_for(span) -> Any:
        midpoint = (float(span["x0"]) + float(span["x1"])) / 2.0
        for rule in kinds:
            if float(rule["x0"]) <= midpoint <= float(rule["x1"]):
                return rule.get("kind") or rule.get("semantic_context")
        return None

    claims: dict[int, list[int]] = {index: [] for index in range(len(source_rules))}
    records: list[dict] = []

    for index, source in enumerate(source_rules):
        intent = _intent_for(source, registry)
        axis = _gated_axis(intent)
        entry = {
            "source_rule_id": (intent or {}).get("source_rule_id"),
            "source_page": page_number,
            "relation_type": (intent or {}).get("relation_type"),
            "transformation_policy": (intent or {}).get("transformation_policy"),
            "geometry_intent": (intent or {}).get("geometry_intent"),
            "gated_axis": axis,
            "source_x0": round(float(source["x0"]), 2),
            "source_x1": round(float(source["x1"]), 2),
            "source_y": round(float(source["y"]), 2),
        }
        # A rule owns the ink that starts where the source rule starts, or ends
        # where it ends - the two endpoints the frozen contract names.  From that
        # seed the rule's own run grows through segments that touch it: a composed
        # rule is painted as several abutting segments and is one rule.  A segment
        # that *overlaps* the run is this rule's ink only when it re-draws the run
        # and extends it inside the rule's own source window - a page renderer may
        # split one underlined run into overlapping pieces - while a neighbouring
        # glyph's underline that reaches past the window still belongs to that other
        # rule, not to this one.  A rule with no seed is reported against the
        # nearest painted span, so a lost rule is diagnosable instead of an empty
        # record.
        window_x1 = float(source["x1"]) + TOLERANCE_PT
        seeds = [
            position
            for position, item in enumerate(painted)
            if abs(float(item["x0"]) - float(source["x0"])) <= TOLERANCE_PT
            or abs(float(item["x1"]) - float(source["x1"])) <= TOLERANCE_PT
        ]
        candidates = []
        for seed in seeds:
            run = [seed]
            cursor = painted[seed]
            for position in range(seed + 1, len(painted)):
                item = painted[position]
                if abs(float(item["y"]) - float(cursor["y"])) > 0.8:
                    break
                if float(item["x0"]) < float(cursor["x1"]) - 0.05:
                    # Overlapping ink: a re-drawn piece of this run when it extends
                    # the run and stays inside the rule's own source window.
                    if (
                        float(item["x1"]) <= float(cursor["x1"]) + 0.05
                        or float(item["x1"]) > window_x1
                    ):
                        break
                    run.append(position)
                    cursor = item
                    continue
                if float(item["x0"]) > float(cursor["x1"]) + 0.6:
                    break
                run.append(position)
                cursor = item
            span = {
                "x0": min(float(painted[position]["x0"]) for position in run),
                "x1": max(float(painted[position]["x1"]) for position in run),
                "y": min(float(painted[position]["y"]) for position in run),
                "positions": run,
            }
            start_error = abs(float(span["x0"]) - float(source["x0"]))
            end_error = abs(float(span["x1"]) - float(source["x1"]))
            span["start_error"] = start_error
            span["end_error"] = end_error
            span["deviation"] = (
                start_error if axis == GATED_START_ONLY else max(start_error, end_error)
            )
            # Prefer the candidate that satisfies the gated tolerance and sits on
            # the source rule's own line: a rule and a same-width rule further
            # down the page can both satisfy a start anchor, and only the source's
            # own reading order tells them apart.
            span["within_tolerance"] = span["deviation"] <= TOLERANCE_PT
            span["line_distance"] = abs(float(span["y"]) - float(source["y"]))
            candidates.append(span)
        if not candidates:
            nearest = _nearest_span(painted, source)
            entry.update(
                status="LOST",
                matched=False,
                observed=(
                    {}
                    if nearest is None
                    else {
                        "x0": round(float(nearest["x0"]), 2),
                        "x1": round(float(nearest["x1"]), 2),
                        "y": round(float(nearest["y"]), 2),
                        "kind": _kind_for(nearest),
                    }
                ),
                deviation_pt=(
                    None if nearest is None else round(float(nearest["deviation"]), 2)
                ),
                measurement="NO_PAINTED_ENDPOINT_MATCHES_SOURCE_ENDPOINT",
                reason=(
                    "no painted rule starts or ends where this source rule does, "
                    "within %.1f pt" % TOLERANCE_PT
                ),
            )
            records.append(entry)
            continue
        best = min(
            candidates,
            key=lambda span: (
                0 if span["within_tolerance"] else 1,
                span["line_distance"] if span["within_tolerance"] else span["deviation"],
                span["deviation"],
            ),
        )
        owned = best["positions"]
        claims[index].extend(owned)
        observed = {"x0": best["x0"], "x1": best["x1"], "y": best["y"]}
        start_error = best["start_error"]
        end_error = best["end_error"]
        deviation = best["deviation"]
        entry.update(
            observed={
                "x0": round(float(observed["x0"]), 2),
                "x1": round(float(observed["x1"]), 2),
                "y": round(float(observed["y"]), 2),
                "kind": _kind_for(observed),
            },
            start_error_pt=round(start_error, 2),
            end_error_pt=round(end_error, 2),
            deviation_pt=round(deviation, 2),
            end_axis_gated=axis == GATED_BOTH,
            measurement="ENDPOINT_SEEDED_CONTIGUOUS_RUN",
            painted_segments=[
                {
                    "x0": round(float(painted[position]["x0"]), 2),
                    "x1": round(float(painted[position]["x1"]), 2),
                    "y": round(float(painted[position]["y"]), 2),
                }
                for position in owned
            ],
        )
        # CLAIM A WRAPPED CONTINUATION.  A resolved value longer than the source
        # placeholder wraps, and its underline continues at the next line's own
        # origin.  Such a fragment is the same logical rule, and it is claimed
        # only when it starts at a text line's origin and follows the anchor
        # within a couple of line pitches - never merely because it is nearby.
        pitch = 0.0
        if len(text_tops) >= 2:
            deltas = [
                b - a for a, b in zip(text_tops, text_tops[1:]) if b - a > 0.05
            ]
            pitch = sorted(deltas)[len(deltas) // 2] if deltas else 0.0
        continuation_limit = pitch * MAX_CONTINUATION_LINE_PITCHES if pitch else 0.0
        continuations = []
        for other_position, other in enumerate(painted):
            if other_position in claims[index]:
                continue
            if other_position in {p for group in claims.values() for p in group}:
                continue
            if float(other["y"]) <= float(observed["y"]):
                continue
            if continuation_limit and float(other["y"]) - float(observed["y"]) > continuation_limit:
                continue
            same_line_continuation = any(
                abs(float(other["y"]) - float(claimed["y"])) <= 0.8
                and -0.05
                <= float(other["x0"]) - float(claimed["x1"])
                <= SAME_LINE_CONTINUATION_GAP_PT
                for claimed in (
                    painted[position] for position in claims[index]
                )
            )
            if not same_line_continuation and not any(
                abs(float(other["x0"]) - float(origin)) <= TOLERANCE_PT
                for origin in line_origins
            ):
                continue
            claims[index].append(other_position)
            continuations.append(
                {
                    "x0": round(float(other["x0"]), 2),
                    "x1": round(float(other["x1"]), 2),
                    "y": round(float(other["y"]), 2),
                    "evidence": (
                        "WRAPPED_UNDERLINE_CONTINUES_ON_SAME_LINE"
                        if same_line_continuation
                        else "WRAPPED_UNDERLINE_CONTINUES_AT_LINE_ORIGIN"
                    ),
                }
            )
        if continuations:
            entry["wrap_continuations"] = continuations
        if deviation <= TOLERANCE_PT:
            entry.update(status="MATCHED", matched=True, reason="")
        else:
            entry.update(
                status="OUT_OF_TOLERANCE",
                matched=False,
                reason=(
                    "painted rule deviates %.2f pt from the gated source geometry "
                    "(tolerance %.1f pt)" % (deviation, TOLERANCE_PT)
                ),
            )
        records.append(entry)

    claimed_positions = {position for group in claims.values() for position in group}
    claimed_runs = [painted[position] for position in sorted(claimed_positions)]
    unclaimed: list[dict] = []
    fragments: list[dict] = []
    for position, item in enumerate(painted):
        if position in claimed_positions:
            continue
        record = {
            "x0": round(float(item["x0"]), 2),
            "x1": round(float(item["x1"]), 2),
            "y": round(float(item["y"]), 2),
            "kind": _kind_for(item),
        }
        # A leftover segment that touches or overlaps an already-measured rule on
        # the same line is not a rule of its own: the renderer drew one underline
        # as several segments, and the next glyph's underline touches the blank's.
        # It is disclosed as a fragment, never counted as an invented rule, and it
        # never widens the rule the source drew.
        if any(
            abs(float(item["y"]) - float(run["y"])) <= 0.8
            and not (
                float(item["x1"]) < float(run["x0"]) - 0.05
                or float(item["x0"]) > float(run["x1"]) + 0.05
            )
            for run in claimed_runs
        ):
            fragments.append(
                {
                    **record,
                    "reason": "fragment of an already measured rule's own underline",
                }
            )
            continue
        unclaimed.append(record)
    invented = [
        {**record, "reason": "painted underline no source rule on this page explains"}
        for record in unclaimed
    ]

    matched = sum(1 for entry in records if entry["status"] == "MATCHED")
    lost = sum(1 for entry in records if entry["status"] == "LOST")
    out_of_tolerance = sum(
        1 for entry in records if entry["status"] == "OUT_OF_TOLERANCE"
    )
    result = {
        "schema": SCHEMA,
        "label": label or build_dir.name,
        "build_dir": str(build_dir),
        "source_pdf": str(source_pdf),
        "generated_pdf": str(generated_path),
        "tolerance_pt": TOLERANCE_PT,
        "contract": {
            "source_span_authority": "FROZEN_P3_SOURCE_GEOMETRY",
            "exact_span_policy": "BOTH_ENDPOINTS_WITHIN_TOLERANCE",
            "anchor_policy": "START_ENDPOINT_WITHIN_TOLERANCE",
            "tolerance_pt": TOLERANCE_PT,
            "measurement_model": "UNMERGED_DRAWN_SEGMENTS_UNITED_PER_SOURCE_WINDOW",
        },
        "response_letter_source_page": page_number,
        "response_letter_generated_page": generated_index + 1,
        "page_mapping_basis": "MEASURED_BY_RULE_START_AGREEMENT",
        "source_underline_count": len(source_rules),
        "painted_underline_count": len(painted),
        "matched": matched,
        "lost": lost,
        "invented": len(invented),
        "out_of_tolerance": out_of_tolerance,
        "rules": records,
        "invented_rules": invented,
        "unclaimed_fragments": fragments,
        "status": (
            "PASS"
            if lost == 0 and out_of_tolerance == 0 and not invented
            else "FAIL"
        ),
    }
    generated_doc.close()
    source_doc.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--source-pdf", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--expect-source-rules",
        type=int,
        default=0,
        help="when set, the source underline count must equal this number",
    )
    args = parser.parse_args(argv)

    inventory = build_inventory(
        Path(args.build).resolve(), Path(args.source_pdf).resolve(), label=args.label
    )
    if args.expect_source_rules and inventory["source_underline_count"] != args.expect_source_rules:
        inventory["status"] = "FAIL"
        inventory["expectation_error"] = (
            "source underline count %d != expected %d"
            % (inventory["source_underline_count"], args.expect_source_rules)
        )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(
        "underline inventory: source=%d matched=%d lost=%d invented=%d "
        "out_of_tolerance=%d status=%s (source page %s -> generated page %s)"
        % (
            inventory["source_underline_count"],
            inventory["matched"],
            inventory["lost"],
            inventory["invented"],
            inventory["out_of_tolerance"],
            inventory["status"],
            inventory["response_letter_source_page"],
            inventory["response_letter_generated_page"],
        )
    )
    return 0 if inventory["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
