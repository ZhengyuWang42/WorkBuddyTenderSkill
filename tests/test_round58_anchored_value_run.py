"""Round 5.8 / V0.9: SOURCE_ANCHORED_VALUE_RUN regressions.

A placeholder replaced by a resolved value is positioned at its source field
anchor, and the delivered value itself is the gated representation.  V0.9 adds
owner-driven value emission for the accepted fixed form line (P42-R5), which uses
the same anchored representation.  P42-R6 is the blank one visual row below it
and stays a fixed empty slot, because its own row carries no field label.  Every
measurement here comes from the current build's fresh render, never from a
requested tab position.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_under_test import BUILD  # noqa: E402

GENERATED_PAGE = 3

R1_ANCHOR = 94.80
R2_ANCHOR = 198.10
R5_ANCHOR = 131.85
R6_ANCHOR = 95.25
R6_SPAN = (95.25, 151.05)
R4_SPAN = (384.60, 458.90)
PURCHASER = "河南省水利第二工程局集团有限公司"
PROJECT_NAME = (
    "河南省水利第二工程局集团有限公司引江济淮郸城县配套工程"
    "水源置换城乡供水工程项目部一体化泵站采购项目"
)
PROJECT_NUMBER = "YSEJJXXB202607-18"
DURATION = "30日历天"
QUALITY_TARGET = "符合国家及行业有关标准、规范和询比文件要求"

pytestmark = pytest.mark.skipif(not BUILD.available, reason=BUILD.skip_reason())


def _report() -> dict:
    return BUILD.report()


def _anchored(rule_id: str) -> dict:
    for record in _report().get("source_anchored_value_runs") or []:
        if record["source_rule_id"] == rule_id:
            return record
    raise AssertionError("no anchored value run for %s" % rule_id)


def _chars():
    page = pymupdf.open(BUILD.pdf)[GENERATED_PAGE - 1]
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    out.append(
                        {
                            "c": char["c"],
                            "x0": round(char["bbox"][0], 2),
                            "x1": round(char["bbox"][2], 2),
                            "y": round(char["bbox"][1], 2),
                        }
                    )
    return out


def _find_all(needle: str):
    """Every painted occurrence of ``needle``, ignoring layout whitespace.

    A resolved value can be split across spans when a proportional font wraps
    it, so matches are found over the non-whitespace character sequence and the
    recorded span is the sequence of the matched glyphs themselves.
    """

    charlist = [char for char in _chars() if char["c"].strip()]
    seq = [c["c"] for c in charlist]
    target = list(needle)
    hits = []
    for i in range(len(seq) - len(target) + 1):
        if seq[i : i + len(target)] == target:
            window = charlist[i : i + len(target)]
            hits.append(
                {"x0": window[0]["x0"], "x1": window[-1]["x1"], "y": window[0]["y"]}
            )
    return hits


def test_r1_uses_source_anchored_value_run():
    record = _anchored("P42-R1")
    assert record["generated_text"] == PURCHASER
    assert record["source_anchor_x"] == R1_ANCHOR
    assert record["anchor_mechanism"] in (
        "LINE_ORIGIN_MOVED_TO_SOURCE_ANCHOR",
        "SOURCE_POSITIONED_ANCHOR_TAB",
        "ALREADY_AT_ANCHOR",
    )


def test_r2_uses_source_anchored_value_run():
    """The R2 field is one logical slot filled by two adjacent source slots."""

    record = _anchored("P42-R2")
    assert record["source_anchor_x"] == R2_ANCHOR
    assert record["generated_text"] == PROJECT_NAME
    assert record["fact_fields"] == ["PROJECT_AND_LOT_SLOT"]


def test_placeholder_is_replaced_not_duplicated():
    """The source placeholder must not survive next to the delivered value."""

    assert _find_all("采购人名称") == []
    assert _find_all("项目名称、标段") == []
    assert len(_find_all(PURCHASER)) >= 1


def test_actual_fact_text_retains_source_rule_id():
    record = _anchored("P42-R1")
    assert record["source_rule_id"] == "P42-R1"
    assert record["resolved_values"] == [PURCHASER]
    assert _anchored("P42-R2")["source_rule_id"] == "P42-R2"


def test_r1_r2_anchor_uses_measured_bbox_not_a_nearby_rule():
    """The value's own rendered bbox start is the representation."""

    hits = _find_all(PURCHASER)
    assert hits, "purchaser not rendered"
    assert abs(hits[0]["x0"] - R1_ANCHOR) <= 2.0, hits[0]

    name_hits = [hit for hit in _find_all(PROJECT_NAME) if hit["x0"] <= 260.0]
    assert name_hits, "project_name not rendered on its anchored line"
    assert abs(name_hits[0]["x0"] - R2_ANCHOR) <= 2.0, name_hits[0]

    # The recorded value start is left for the fresh render to fill in.
    assert _anchored("P42-R1")["source_anchor_x"] == R1_ANCHOR


def test_lot_name_not_found_generates_no_fake_text():
    """lot_name is NOT_FOUND, so no lot text may be invented."""

    record = _anchored("P42-R2")
    assert record["generated_text"] == PROJECT_NAME
    assert "None" not in record["generated_text"]
    assert "NOT_FOUND" not in record["generated_text"]
    # The composite on the rendered line is project_name then project_number.
    assert _find_all(PROJECT_NAME + PROJECT_NUMBER)


def test_no_invented_separator_between_name_and_number():
    """Source placeholders are adjacent, so the composite is adjacent."""

    composite = _find_all(PROJECT_NAME + PROJECT_NUMBER)
    assert composite, "project_name and project_number are not adjacent"
    for invented in (" - ", " / ", "编号：", "（项目编号："):
        assert not _find_all(PROJECT_NAME + invented + PROJECT_NUMBER)


def test_no_trailing_blank_underline_after_project_number():
    """No fixed-width blank may follow the delivered number."""

    page = pymupdf.open(BUILD.pdf)[GENERATED_PAGE - 1]
    number_hits = _find_all(PROJECT_NUMBER)
    assert number_hits
    number_y = number_hits[0]["y"]
    trailing = [
        drawing["rect"]
        for drawing in page.get_drawings()
        if drawing["rect"].height <= 2.4
        and abs((drawing["rect"].y0 + drawing["rect"].y1) / 2 - number_y) <= 3.0
        and drawing["rect"].x0 >= 340.0
    ]
    assert trailing == []


def test_r5_and_r6_emit_their_resolved_values_at_their_anchors():
    """An accepted fixed form line delivers a value at its own source anchor.

    ``P42-R5`` is the accepted owner-driven value emission.  ``P42-R6`` is the
    blank one visual row below it: that row carries no field label of its own
    (only the ``达到`` before the blank and the ``。`` after it), so no executed
    value is authoritative for it and the rule stays a fixed empty slot.  Its
    geometry is still the source's own span, which is asserted here directly.
    """

    report = _report()
    run = next(
        record
        for record in report.get("source_form_line_value_runs") or []
        if record["source_rule_id"] == "P42-R5"
    )
    assert run["resolved_values"] == [DURATION]
    assert run["application_kind"] == "VALUE_IN_FIXED_SLOT"
    assert abs(run["anchor_x"] - R5_ANCHOR) <= 2.0
    hits = _find_all(DURATION)
    assert hits, "no painted value run for P42-R5"
    assert abs(hits[0]["x0"] - R5_ANCHOR) <= 2.0, hits[0]

    entry = next(
        record
        for record in report["source_rule_registry"]
        if record["source_rule_id"] == "P42-R6"
    )
    assert entry["transformation_policy"] == "FIXED_EMPTY_SLOT"
    assert entry["geometry_intent"] == "EXACT_SOURCE_SPAN"
    assert entry["x0"] == R6_ANCHOR
    assert not [
        record
        for record in report.get("source_form_line_value_runs") or []
        if record["source_rule_id"] == "P42-R6"
    ]
    assert not _find_all(QUALITY_TARGET)


def test_r4_r5_r6_geometry_unchanged():
    """The frozen positioned emitter and form-line paragraphs must not regress."""

    report = _report()
    # A form-line paragraph is only opened for a row whose positioned atom cannot
    # be reached forward from that row's own paragraph origin.  R3/R4 share one
    # form line and R5 and P42-R6 have their own; a row whose anchor IS reachable
    # forward keeps the owning element's paragraph, so it contributes no record
    # here.  The frozen geometry of the emitters is what must not regress, and it
    # is asserted directly below rather than through a record count.
    assert report["source_form_line_paragraph_count"] == 3
    isolated = [
        record["source_rule_ids"]
        for record in report["source_form_line_paragraphs"]
    ]
    assert isolated == [["P42-R3", "P42-R4"], ["P42-R5"], ["P42-R6"]], isolated
    assert report["form_layout_break_count"] == 0
    page = pymupdf.open(BUILD.pdf)[GENERATED_PAGE - 1]
    rules = sorted(
        (
            (round(d["rect"].x0, 2), round(d["rect"].x1, 2))
            for d in page.get_drawings()
            if d["rect"].height <= 2.4 and d["rect"].width >= 6.0
        ),
        key=lambda item: item[0],
    )
    assert any(
        abs(x0 - R4_SPAN[0]) <= 2.0 and abs(x1 - R4_SPAN[1]) <= 2.0
        for x0, x1 in rules
    )
    # P42-R5 owes only its start anchor, expressed as an underlined value run
    # rather than a drawn rule.
    hits = _find_all(DURATION)
    assert hits and abs(hits[0]["x0"] - R5_ANCHOR) <= 2.0, "P42-R5"
    # P42-R6 stays a fixed empty slot and is painted as a rule across its own
    # source span, so the source x1 is honoured exactly for it.
    assert any(
        abs(x0 - R6_ANCHOR) <= 2.0 and abs(x1 - R6_SPAN[1]) <= 2.0
        for x0, x1 in rules
    ), rules


def test_r5_r6_values_are_underlined():
    """A resolved value in a fixed slot keeps the source underline semantics."""

    report = _report()
    runs = {
        record["source_rule_id"]: record
        for record in report.get("source_form_line_value_runs") or []
    }
    record = runs["P42-R5"]
    assert record["underline_semantics"] == "RESOLVED_VALUE_UNDERLINED_AT_NATURAL_WIDTH"
    assert record["geometry_intent"] == "ANCHOR_START_ONLY"
    assert record["representation_type"] == "SOURCE_ANCHORED_VALUE_RUN"
    assert "never forces" in record["geometry_note"]
    # P42-R6 keeps the source's own span instead: with no value to underline it
    # is painted as the source rule itself.
    entry = next(
        record
        for record in report["source_rule_registry"]
        if record["source_rule_id"] == "P42-R6"
    )
    assert entry["geometry_intent"] == "EXACT_SOURCE_SPAN"
    assert entry["x1"] == R6_SPAN[1]
    # The value run's right edge is its own natural glyph extent, never the
    # source x1, so the delivered value is what actually carries the underline.
    hits = _find_all(DURATION)
    assert hits, "P42-R5"
    assert hits[0]["x1"] > hits[0]["x0"]
    # P42-R6 delivers no value, so its own resolved field text is painted
    # nowhere in the document.
    assert not _find_all(QUALITY_TARGET)


def test_p45_r6_remains_valid_out_of_scope_provenance():
    registry = {
        entry["source_rule_id"]: entry
        for entry in _report().get("source_rule_registry") or []
    }
    assert "P45-R6" in registry
    assert registry["P45-R6"]["source_page"] == 45
    owners = _report().get("source_form_execution_owners") or []
    assert not any(
        "P45-R6" in (owner.get("source_rule_ids") or ()) for owner in owners
    )
