"""Round 5.8: P42-R7 SOURCE_RULE_COMPOSITION regressions.

One logical source rule is emitted as three ordered physical segments whose
rule-bearing union is exactly the source rule extent.  All geometry is measured
from a fresh render of the generated DOCX, never from requested tab positions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_under_test import BUILD  # noqa: E402

GENERATED_PAGE = 3

RULE_X0, RULE_X1 = 352.80, 388.80
R7_SEGMENTS = [(352.80, 364.80), (364.80, 376.80), (376.80, 388.80)]
TOLERANCE_PT = 2.0

pytestmark = pytest.mark.skipif(not BUILD.available, reason=BUILD.skip_reason())


def _report() -> dict:
    return BUILD.report()


def _pdf() -> Path:
    return BUILD.pdf


def _composition(rule_id: str) -> dict:
    for record in _report().get("source_rule_compositions") or []:
        if record["source_rule_id"] == rule_id:
            return record
    raise AssertionError("no SOURCE_RULE_COMPOSITION for %s" % rule_id)


def _chars():
    page = pymupdf.open(_pdf())[GENERATED_PAGE - 1]
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    if char["c"].strip():
                        out.append(
                            {
                                "c": char["c"],
                                "x0": round(char["bbox"][0], 2),
                                "y": round(char["bbox"][1], 2),
                            }
                        )
    return out


def _find_all(needle: str):
    charlist = _chars()
    seq = [c["c"] for c in charlist]
    target = list(needle)
    hits = []
    for i in range(len(seq) - len(target) + 1):
        if seq[i : i + len(target)] == target:
            hits.append({"x0": charlist[i]["x0"], "y": charlist[i]["y"]})
    return hits


def _painted_rules():
    page = pymupdf.open(_pdf())[GENERATED_PAGE - 1]
    rules = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.height <= 2.4 and rect.width >= 2.0:
            rules.append(
                (
                    round(rect.x0, 2),
                    round(rect.x1, 2),
                    round((rect.y0 + rect.y1) / 2, 2),
                )
            )
    return rules


def _r7_segments():
    """The three painted segments on the R7 line, in order.

    The R7 line is the painted line carrying a segment at the rule's own x0;
    selecting by x-range alone would catch a different rule.
    """

    by_line = {}
    for rule in _painted_rules():
        by_line.setdefault(rule[2], []).append(rule)
    for _y, items in sorted(by_line.items()):
        if any(abs(item[0] - RULE_X0) <= TOLERANCE_PT for item in items):
            return sorted(items, key=lambda item: item[0])
    return []


def _document_xml() -> str:
    import zipfile

    with zipfile.ZipFile(BUILD.docx) as package:
        return package.read("word/document.xml").decode("utf-8")


# --- representation -------------------------------------------------------


def test_p42_r7_uses_source_rule_composition():
    record = _composition("P42-R7")
    assert record["representation_type"] == "SOURCE_RULE_COMPOSITION"
    assert record["geometry_policy"] == "EXACT_SOURCE_SPAN"


def test_composition_has_exactly_three_ordered_segments():
    record = _composition("P42-R7")
    assert record["segment_count"] == 3
    assert len(record["segments"]) == 3
    assert [segment["source_x0"] for segment in record["segments"]] == [
        352.80, 364.80, 376.80
    ]
    assert [segment["source_x1"] for segment in record["segments"]] == [
        364.80, 376.80, 388.80
    ]


def test_segment_types_are_empty_text_empty():
    record = _composition("P42-R7")
    assert [segment["segment_type"] for segment in record["segments"]] == [
        "EMPTY_RULE_SEGMENT",
        "TEXT_RULE_SEGMENT",
        "EMPTY_RULE_SEGMENT",
    ]


def test_segment_union_equals_source_rule_interval():
    record = _composition("P42-R7")
    segments = record["segments"]
    assert segments[0]["source_x0"] == RULE_X0
    assert segments[-1]["source_x1"] == RULE_X1
    for left, right in zip(segments, segments[1:]):
        assert left["source_x1"] == right["source_x0"]
    union = {}
    for segment in segments:
        union[segment["source_x0"]] = union.get(segment["source_x0"], 0) + 1
    assert min(segment["source_x0"] for segment in segments) == RULE_X0
    assert max(segment["source_x1"] for segment in segments) == RULE_X1


def test_middle_segment_text_is_exactly_90():
    record = _composition("P42-R7")
    middle = record["segments"][1]
    assert middle["source_text"] == "90"
    assert middle["generated_text"] == "90"
    assert middle["source_x0"] == 364.80
    assert middle["source_x1"] == 376.80


def test_visible_90_occurs_exactly_once_in_the_slot():
    hits = _find_all("90")
    assert len(hits) == 1, hits
    assert abs(hits[0]["x0"] - 364.80) <= TOLERANCE_PT


# --- the old path must be gone -------------------------------------------


def test_old_r7_run_underline_path_is_inactive():
    """R7's own characters are consumed, so no run carries them."""

    report = _report()
    for record in report.get("blank_representation_records") or []:
        assert not (
            record.get("source_x0") == RULE_X0 and record.get("source_x1") == RULE_X1
        ), "R7 is still emitted through the blank/underline path"
    composition = _composition("P42-R7")
    for segment in composition["segments"]:
        assert segment["emission_mechanism"] in (
            "SOURCE_POSITIONED_UNDERLINED_TAB",
            "SOURCE_UNDERLINED_VALUE_RUN",
        )


# --- provenance and accounting -------------------------------------------


def test_one_logical_rule_owns_the_three_segments():
    record = _composition("P42-R7")
    assert record["logical_rule_emission_count"] == 1
    assert record["composition_segment_emission_count"] == 3
    occurrences = [
        item["source_rule_id"]
        for item in _report().get("source_rule_compositions") or []
        if item["source_rule_id"] == "P42-R7"
    ]
    assert occurrences == ["P42-R7"], "R7 composed more than once"


def test_all_segments_retain_the_source_rule_id():
    for segment in _composition("P42-R7")["segments"]:
        assert segment["source_rule_id"] == "P42-R7"


def test_each_segment_has_a_unique_composition_segment_id():
    ids = [segment["composition_segment_id"] for segment in _composition("P42-R7")["segments"]]
    assert len(ids) == len(set(ids)) == 3
    assert all("P42-R7" in segment_id for segment_id in ids)


def test_duplicate_logical_rule_emission_count_is_zero():
    ids = [
        record["source_rule_id"]
        for record in _report().get("source_rule_compositions") or []
    ]
    assert len(ids) == len(set(ids))


def test_empty_segments_use_source_positioned_geometry():
    """Physical width comes from the source span, not a glyph count."""

    record = _composition("P42-R7")
    for segment in record["segments"]:
        assert segment["emission_mechanism"] in (
            "SOURCE_POSITIONED_UNDERLINED_TAB",
            "SOURCE_UNDERLINED_VALUE_RUN",
        )
        if segment["segment_type"] == "EMPTY_RULE_SEGMENT":
            assert segment["source_text"] is None
            assert segment["generated_text"] == ""
            assert segment["anchor_tab_position_pt"] is not None
            assert segment["leader_tab_position_pt"] is not None
    # Physical width must come from the source span, so R7's own paragraph may
    # not use repeated figure spaces as a width authority.
    from docx import Document

    index = _composition("P42-R7")["paragraph_index"]
    paragraph = Document(str(BUILD.docx)).paragraphs[index]
    assert "\u2007" not in paragraph._p.xml


# --- fresh rendered geometry ---------------------------------------------


def test_r7_overall_painted_union_matches_source():
    segments = _r7_segments()
    assert len(segments) == 3, segments
    assert abs(segments[0][0] - RULE_X0) <= TOLERANCE_PT
    assert abs(segments[-1][1] - RULE_X1) <= TOLERANCE_PT


def test_r7_segment_gaps_and_overlaps_are_negligible():
    segments = _r7_segments()
    assert len(segments) == 3, segments
    for (x0, x1, _), (nx0, nx1, _) in zip(segments, segments[1:]):
        gap = nx0 - x1
        assert gap <= TOLERANCE_PT, "gap between segments is %s" % gap
        assert gap >= -TOLERANCE_PT, "segments overlap by %s" % -gap


def test_r7_segment_geometry_matches_the_frozen_contract():
    painted = [(seg[0], seg[1]) for seg in _r7_segments()]
    assert len(painted) == 3
    for (got_x0, got_x1), (want_x0, want_x1) in zip(painted, R7_SEGMENTS):
        assert abs(got_x0 - want_x0) <= TOLERANCE_PT
        assert abs(got_x1 - want_x1) <= TOLERANCE_PT


# --- frozen regressions ---------------------------------------------------


def test_r1_and_r2_anchors_remain_within_tolerance():
    assert abs(_report()["source_anchored_value_runs"][0]["source_anchor_x"] - 94.80) <= TOLERANCE_PT
    hits = [hit for hit in _find_all("河南省水利第二工程局集团有限公司") if abs(hit["y"] - 137.83) <= 6.0]
    assert hits and abs(hits[0]["x0"] - 94.80) <= TOLERANCE_PT
    assert abs(_report()["source_anchored_value_runs"][1]["source_anchor_x"] - 198.10) <= TOLERANCE_PT


def test_r4_x0_and_x1_remain_within_tolerance():
    painted = [
        (x0, x1)
        for x0, x1, _y in _painted_rules()
        if abs(x0 - 384.60) <= TOLERANCE_PT
    ]
    assert painted, "P42-R4 rule missing"
    x0, x1 = painted[0]
    assert abs(x0 - 384.60) <= TOLERANCE_PT
    assert abs(x1 - 459.00) <= TOLERANCE_PT


def test_r5_and_r6_anchors_remain_within_tolerance():
    """Each form line keeps its own source anchor, whatever represents it.

    ``P42-R5`` expresses its anchor as a value run's painted text.  ``P42-R6``
    owns no value, so its anchor is the registry entry the positioned emitter
    paints from - the source x0 and x1 stay unchanged either way.
    """

    report = _report()
    run = next(
        record
        for record in report.get("source_form_line_value_runs") or []
        if record["source_rule_id"] == "P42-R5"
    )
    assert abs(run["source_x0"] - 131.85) <= TOLERANCE_PT
    assert abs(run["anchor_x"] - 131.85) <= TOLERANCE_PT
    entry = next(
        record
        for record in report["source_rule_registry"]
        if record["source_rule_id"] == "P42-R6"
    )
    assert abs(entry["x0"] - 95.25) <= TOLERANCE_PT
    assert abs(entry["x1"] - 151.05) <= TOLERANCE_PT
    assert entry["geometry_intent"] == "EXACT_SOURCE_SPAN"


def test_r5_and_r6_remain_separate_form_line_paragraphs():
    report = _report()
    records = {
        record["source_rule_id"]: record
        for record in report.get("source_form_line_paragraphs") or []
    }
    assert records["P42-R5"]["generated_paragraph_index"] != records["P42-R6"][
        "generated_paragraph_index"
    ]
    assert report["form_layout_break_count"] == 0


def test_p45_r6_remains_valid_out_of_scope_provenance():
    registry = {
        entry["source_rule_id"]: entry
        for entry in _report().get("source_rule_registry") or []
    }
    assert "P45-R6" in registry
    assert registry["P45-R6"]["source_page"] == 45


# --- QA aggregation: a composition is one represented logical rule ---------


def _composition_geometry(source_rule_id: str):
    """The painted chain a composition actually produced, measured from the PDF."""

    record = _composition(source_rule_id)
    source_x0 = record.get("source_x0")
    if source_x0 is None:
        source_x0 = RULE_X0 if source_rule_id == "P42-R7" else None
    rules = sorted(
        _painted_rules(), key=lambda item: (item[2], item[0])
    )
    seeds = [rule for rule in rules if abs(rule[0] - source_x0) <= TOLERANCE_PT]
    assert seeds, "no painted segment starts at the %s source anchor" % source_rule_id
    chain = [seeds[0]]
    y = seeds[0][2]
    growing = True
    while growing:
        growing = False
        for rule in rules:
            if (
                abs(rule[2] - y) <= 1.0
                and abs(rule[0] - chain[-1][1]) <= 1.0
                and rule[1] > chain[-1][1]
            ):
                chain.append(rule)
                growing = True
                break
    return {
        "x0": chain[0][0],
        "x1": chain[-1][1],
        "y": y,
        "painted_segment_count": len(chain),
    }


def test_composition_counts_as_one_represented_exact_span_rule():
    """QA must credit an accepted composition as a physical representation.

    Regression for the stale accounting that counted a composition's physical
    segments as several rules and reported the composed rules as lost.
    """

    report = _report()
    composed = {
        record["source_rule_id"]
        for record in report.get("source_rule_compositions") or []
    }
    assert "P42-R7" in composed, "composition not credited to its logical rule"
    registry = {
        entry["source_rule_id"]: entry
        for entry in report.get("source_rule_registry") or []
        if entry.get("source_page") == 42
    }
    exact = {
        rule_id
        for rule_id, entry in registry.items()
        if entry.get("geometry_intent") == "EXACT_SOURCE_SPAN"
    }
    represented = exact & ({"P42-R4", "P42-R6"} | composed)
    assert exact == {"P42-R3", "P42-R4", "P42-R6", "P42-R7", "P42-R8"}, sorted(exact)
    assert represented == exact, sorted(exact - represented)
    assert round(len(represented) / len(exact), 3) == 1.00


def test_composed_rule_keeps_its_exact_source_span():
    record = _composition("P42-R7")
    assert record["logical_rule_emission_count"] == 1
    assert record.get("composition_segment_emission_count", record.get("segment_count")) == 3
    assert record.get("segment_count") == 3
    painted = _composition_geometry("P42-R7")
    assert abs(painted["x0"] - RULE_X0) <= TOLERANCE_PT
    assert abs(painted["x1"] - RULE_X1) <= TOLERANCE_PT
    assert painted["painted_segment_count"] == 3
