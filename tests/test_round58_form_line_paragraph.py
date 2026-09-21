"""Round 5.8 / V0.9: SOURCE_FORM_LINE_PARAGRAPH regressions.

P42-R5 and P42-R6 are separate source visual form lines that must not share a
Word paragraph coordinate context.  V0.9 makes them value-bearing: each owns a
``SOURCE_FORM_LINE_PARAGRAPH`` execution owner and emits its resolved value as a
``SOURCE_ANCHORED_VALUE_RUN`` starting at its own source anchor.  These tests pin
that structural result together with the actual painted geometry, and they read
the *current* build rather than a frozen run directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_under_test import BUILD  # noqa: E402

GENERATED_PAGE = 3

R5 = (131.85, 181.40)
R6 = (95.25, 151.05)
R4 = (384.60, 459.00)

pytestmark = pytest.mark.skipif(not BUILD.available, reason=BUILD.skip_reason())


def _report() -> dict:
    return BUILD.report()


def _form_line(rule_id: str) -> dict:
    for record in _report().get("source_form_line_paragraphs") or []:
        if record.get("source_rule_id") == rule_id:
            return record
    raise AssertionError("no form-line paragraph for %s" % rule_id)


def _value_run(rule_id: str) -> dict:
    for record in _report().get("source_form_line_value_runs") or []:
        if record.get("source_rule_id") == rule_id:
            return record
    raise AssertionError("no owner-driven value run for %s" % rule_id)


def _blank(rule_id: str) -> dict:
    for record in _report().get("positioned_blank_records") or []:
        if record.get("source_rule_id") == rule_id:
            return record
    raise AssertionError("no emission record for %s" % rule_id)


def _rendered_rules():
    import pymupdf

    page = pymupdf.open(BUILD.pdf)[GENERATED_PAGE - 1]
    rules = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.height <= 2.4 and rect.width >= 6.0:
            rules.append(
                (round(rect.x0, 2), round(rect.x1, 2), round((rect.y0 + rect.y1) / 2, 2))
            )
    return sorted(rules, key=lambda item: (item[2], item[0]))


def _value_span(rule_id: str):
    """The painted character span of the value this rule emitted."""

    import pymupdf

    record = _value_run(rule_id)
    values = list(record.get("resolved_values") or ())
    page = pymupdf.open(BUILD.pdf)[GENERATED_PAGE - 1]
    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span.get("chars", []):
                    if char.get("c", "").strip():
                        chars.append((char["c"], char["bbox"]))
    for value in values:
        probe = str(value)
        if not probe:
            continue
        for start in range(0, len(chars) - len(probe) + 1):
            if "".join(item[0] for item in chars[start : start + len(probe)]) == probe:
                window = chars[start : start + len(probe)]
                return (
                    round(window[0][1][0], 2),
                    round(window[-1][1][2], 2),
                    round((window[0][1][1] + window[0][1][3]) / 2, 2),
                )
    return None


def _painted(rule_id: str):
    record = _blank(rule_id)
    width = record["leader_tab_position_pt"] - record["anchor_tab_position_pt"]
    for x0, x1, y in _rendered_rules():
        if abs((x1 - x0) - width) <= 1.5:
            return x0, x1, y
    return None


def test_source_form_line_paragraphs_created():
    """Every source form line that needs its own geometry gets a paragraph.

    ``P44-R12`` is the additional one: its covered character range now names
    exactly the glyphs it re-emits, so it is a real composition and needs its own
    line context exactly like the accepted P3 rules.
    """

    report = _report()
    assert report.get("source_form_line_paragraph_count") == 5
    records = report.get("source_form_line_paragraphs") or []
    ids = [record["source_rule_id"] for record in records]
    assert ids == ["P42-R3", "P42-R5", "P42-R6", "P42-R7", "P44-R12"], ids


def test_r5_and_r6_are_different_paragraphs():
    """The two form lines must not share a paragraph index."""

    r5 = _form_line("P42-R5")["generated_paragraph_index"]
    r6 = _form_line("P42-R6")["generated_paragraph_index"]
    assert r5 is not None and r6 is not None
    assert r5 != r6, "R5 and R6 share paragraph %s" % r5


def test_no_run_break_separates_r5_and_r6():
    """The old run.add_break() form-line path must not execute for these lines."""

    report = _report()
    assert report.get("form_layout_break_count") == 0
    assert (
        _form_line("P42-R5")["generated_paragraph_index"]
        != _form_line("P42-R6")["generated_paragraph_index"]
    )


def test_r5_paragraph_owns_p42_r5_only():
    assert _form_line("P42-R5")["source_rule_ids"] == ["P42-R5"]


def test_r6_paragraph_owns_p42_r6_only():
    assert _form_line("P42-R6")["source_rule_ids"] == ["P42-R6"]


def test_first_line_indent_of_r5_cannot_affect_r6():
    """Both form-line paragraphs declare their own zero first-line indent."""

    for rule_id in ("P42-R5", "P42-R6"):
        formatting = _form_line(rule_id)["paragraph_format"]
        assert formatting["first_line_indent_pt"] == 0.0
        assert formatting["space_before_pt"] == 0.0
        assert formatting["space_after_pt"] == 0.0
        assert formatting["left_indent_pt"] == 0.0
        assert formatting["right_indent_pt"] == 0.0


def test_r5_and_r6_are_owner_driven_value_emissions():
    """The accepted form line carries its resolved value through an owner.

    ``P42-R6`` is the blank one visual row below ``P42-R5``.  Its own row carries
    no field label, so no execution owner exists for it and it stays a fixed
    empty slot - the paragraph and its own geometry are still created, which is
    what the form-line architecture owes it.
    """

    owners = {
        owner["source_form_field_id"]: owner
        for owner in _report().get("source_form_execution_owners") or []
    }
    run = _value_run("P42-R5")
    owner = owners[run["source_form_field_id"]]
    assert owner["owner_kind"] == "SOURCE_FORM_LINE_OWNER"
    assert owner["representation_type"] == "SOURCE_FORM_LINE_PARAGRAPH"
    assert owner["eligible_for_value_emission"] is True
    assert run["application_kind"] == "VALUE_IN_FIXED_SLOT"
    assert run["representation_type"] == "SOURCE_ANCHORED_VALUE_RUN"
    assert run["geometry_intent"] == "ANCHOR_START_ONLY"
    assert run["fact_fields"], "P42-R5"
    assert run["resolved_values"], "P42-R5"

    assert not [
        record
        for record in _report().get("source_form_line_value_runs") or []
        if record["source_rule_id"] == "P42-R6"
    ]
    assert _form_line("P42-R6")["source_rule_ids"] == ["P42-R6"]
    assert _blank("P42-R6")


def test_r5_and_r6_paint_at_their_source_anchors():
    """Actual painted geometry, not requested tab coordinates."""

    painted = _value_span("P42-R5")
    assert painted is not None, "no painted value run for P42-R5"
    assert abs(painted[0] - R5[0]) <= 2.0, (painted, R5)
    # P42-R6 owns no value, so nothing of its resolved field is painted; its own
    # source span is painted as the rule itself.
    blank = _blank("P42-R6")
    assert abs(blank["source_x0"] - R6[0]) <= 2.0, blank
    assert abs(blank["source_x1"] - R6[1]) <= 2.0, blank


def test_r5_and_r6_values_use_their_own_natural_width():
    """ANCHOR_START_ONLY keeps the source x1 as provenance only."""

    run = _value_run("P42-R5")
    assert run["geometry_intent"] == "ANCHOR_START_ONLY"
    assert run["underline_semantics"] == "RESOLVED_VALUE_UNDERLINED_AT_NATURAL_WIDTH"
    assert "never forces" in run["geometry_note"]
    # The blank keeps its source span exactly, because it carries no value whose
    # natural width could differ from the source x1.
    entry = next(
        record
        for record in _report()["source_rule_registry"]
        if record["source_rule_id"] == "P42-R6"
    )
    assert entry["geometry_intent"] == "EXACT_SOURCE_SPAN"
    assert (entry["x0"], entry["x1"]) == R6


def test_r5_and_r6_representations_are_distinct():
    r5 = _value_span("P42-R5")
    assert r5 is not None
    r6 = _blank("P42-R6")
    assert r6["source_x0"] != r5[0] or r6["source_x1"] != r5[1]


def test_p42_r4_stays_on_the_proven_path():
    """The frozen P42-R4 contract must not regress."""

    painted = _painted("P42-R4")
    assert painted is not None
    assert abs(painted[0] - R4[0]) <= 2.0
    assert abs(painted[1] - R4[1]) <= 2.0


def test_p42_r4_establishes_no_execution_owner():
    """An accepted empty slot keeps the empty path and owns no value."""

    owners = _report().get("source_form_execution_owners") or []
    assert not any(
        "P42-R4" in (owner.get("source_rule_ids") or ()) for owner in owners
    )


def test_p45_r6_remains_valid_out_of_scope_provenance():
    """A legitimate emission from another page is not an orphan."""

    registry = {
        entry["source_rule_id"]: entry
        for entry in _report().get("source_rule_registry") or []
    }
    assert "P45-R6" in registry
    assert registry["P45-R6"]["source_page"] == 45
    record = _blank("P45-R6")
    assert record["source_page"] == 45
    assert abs(record["source_x0"] - 154.80) <= 1.0
    assert abs(record["source_x1"] - 232.80) <= 1.0


def test_p45_r6_establishes_no_execution_owner():
    """P45-R6 stays execution-inactive under the plan-driven channel."""

    owners = _report().get("source_form_execution_owners") or []
    assert not any(
        "P45-R6" in (owner.get("source_rule_ids") or ()) for owner in owners
    )


def test_duplicate_source_rule_id_emission_count_is_zero():
    ids = [
        record.get("source_rule_id")
        for record in _report().get("positioned_blank_records") or []
    ]
    assert len(ids) == len(set(ids)), ids
    assert all(ids), "an emission record lost its source_rule_id"
