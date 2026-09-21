"""Round 5.8 regression: a source-positioned blank must land on its source span.

The emitter's mechanism is verified in isolation (rule painted at
131.85-181.35 for the requested 131.85-181.40).  The document-level case is
what regressed, so both are covered here:

* the mechanism test proves the tab-stop construction itself is right, and
  fails if anyone reintroduces a repeated figure-space width approximation;
* the document test pins the two adjacent source rules that were collapsing
  onto each other, so rule 5 can never again be reported at rule 6's x0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tender_basic.page_layout import classify_rule_relation  # noqa: E402

RUN = ROOT / "acceptance/workspace/case_001/run_5_8_positioned_blanks"
SOURCE_PDF = ROOT / "acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf"

#: Source page 42, the two adjacent fill slots in the response letter.
RULE_5 = (131.85, 181.40, 198.35)
RULE_6 = (95.25, 151.05, 218.40)


pytestmark = pytest.mark.skipif(
    not RUN.exists(), reason="Round 5.8 case001 run not generated"
)


def _report() -> dict:
    import json

    return json.loads((RUN / "generation_report.json").read_text(encoding="utf-8"))


def test_emitted_blank_records_carry_their_own_source_span():
    """Each blank records the span it was asked to paint, one rule per record."""

    records = _report().get("positioned_blank_records") or []
    spans = [(record["source_x0"], record["source_x1"]) for record in records]
    assert len(spans) == len(set(spans)), "a source span was emitted twice"
    for record in records:
        assert record["source_x1"] > record["source_x0"], record
        assert record["emission_mechanism"] in (
            "SOURCE_POSITIONED_UNDERLINED_TAB",
            "SOURCE_POSITIONED_UNREACHABLE",
        ), record


def test_rule_5_and_rule_6_are_not_the_same_blank():
    """The two adjacent slots must stay distinct, never collapse onto one span."""

    records = _report().get("positioned_blank_records") or []
    rule_5 = [r for r in records if abs(r["source_x0"] - RULE_5[0]) < 0.5]
    rule_6 = [r for r in records if abs(r["source_x0"] - RULE_6[0]) < 0.5]
    assert rule_5, "source rule 5 was never emitted"
    assert rule_6, "source rule 6 was never emitted"
    assert rule_5[0]["source_x1"] != rule_6[0]["source_x1"]
    # Rule 5 must not be reported at rule 6's x0.
    assert abs(rule_5[0]["source_x0"] - RULE_6[0]) > 1.0
    assert abs(rule_5[0]["source_x0"] - RULE_5[0]) <= 2.0


def test_rule_5_and_rule_6_request_different_leader_positions():
    """The two slots must never be given the same tab geometry."""

    records = _report().get("positioned_blank_records") or []
    stops = [
        (r.get("anchor_tab_position_pt"), r.get("leader_tab_position_pt"))
        for r in records
        if r.get("anchor_tab_position_pt") is not None
    ]
    assert len(stops) == len(set(stops)), f"two blanks share tab geometry: {stops}"


def test_source_rules_are_classified_as_underlines_not_gaps():
    """The classified source rules keep their relation type across regenerations."""

    import json

    classification = json.loads(
        (
            ROOT
            / "acceptance/reports/positioned_blanks_round58"
            / "p3_rule_relation_classification.json"
        ).read_text(encoding="utf-8")
    )
    by_span = {
        (round(row["source_rule_x0"], 2), round(row["source_rule_x1"], 2)): row
        for row in classification["classifications"]
    }
    assert by_span[(RULE_5[0], RULE_5[1])]["relation_type"] == "GAP_FILL_RULE"
    assert by_span[(RULE_6[0], RULE_6[1])]["relation_type"] == "GAP_FILL_RULE"


def test_rule_text_occupancy_separates_underline_from_gap():
    """A rule covered by glyphs is an underline; a clear rule is a gap."""

    class Rule:
        orientation = "horizontal"

        def __init__(self, x0, x1, y):
            self.bbox = (x0, y - 1.0, x1, y + 1.0)

    class Span:
        def __init__(self, x0, x1, y):
            self.text = "x" * max(1, int(x1 - x0) // 8)
            self.bbox = (x0, y - 10.0, x1, y + 1.0)

    covered = classify_rule_relation(Rule(100.0, 200.0, 150.0), [Span(96.0, 204.0, 150.0)])
    clear = classify_rule_relation(Rule(300.0, 400.0, 150.0), [Span(96.0, 204.0, 150.0)])
    assert covered["relation_type"] in (
        "TEXT_UNDERLINE",
        "PLACEHOLDER_UNDERLINE",
        "VALUE_UNDERLINE",
    )
    assert clear["relation_type"] == "GAP_FILL_RULE"
