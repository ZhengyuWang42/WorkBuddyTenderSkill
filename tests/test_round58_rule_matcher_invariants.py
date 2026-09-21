"""Round 5.8 rule-matcher accounting invariants.

The Round 5.7 gate emitted ``source_rule_count = 8`` with
``matched_rule_count = 1`` and ``lost_source_rule_count = 8``, which cannot be a
one-to-one partition.  These tests pin the accounting down: a report whose counts
do not close must be impossible to emit, and a geometrically displaced match must
be reported as *displaced*, never as both matched and lost.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tender_basic.geometry_rule_qa import (  # noqa: E402
    MATCH_INVARIANTS,
    rule_accounting_failures,
)


def _rule(x0: float, x1: float, y: float, kind: str = "VECTOR_RULE", context: str = "") -> dict:
    return {
        "x0": x0,
        "x1": x1,
        "y": y,
        "width": round(x1 - x0, 2),
        "kind": kind,
        "context": context,
        "semantic_context": context,
        "parts": 1,
    }


def _match(source: list[dict], generated: list[dict]) -> dict:
    from tender_basic.geometry_rule_qa import match_blank_rules

    return match_blank_rules(source, generated)


def test_accounting_closes_for_a_perfect_match():
    source = [_rule(100, 200, 300), _rule(100, 200, 320)]
    generated = [_rule(100, 200, 300), _rule(100, 200, 320)]
    report = _match(source, generated)

    assert report["normalized_source_rule_count"] == 2
    assert report["normalized_generated_rule_count"] == 2
    assert report["matched_rule_count"] == 2
    assert report["lost_source_rule_count"] == 0
    assert report["invented_rule_count"] == 0
    assert report["matched_out_of_tolerance_count"] == 0
    assert rule_accounting_failures(report) == []


def test_source_equals_matched_plus_lost():
    source = [_rule(100, 200, 300), _rule(100, 200, 320), _rule(100, 200, 340)]
    generated = [_rule(100, 200, 300), _rule(100, 200, 340)]
    report = _match(source, generated)

    assert (
        report["normalized_source_rule_count"]
        == report["matched_rule_count"] + report["lost_source_rule_count"]
    )
    assert report["lost_source_rule_count"] == 1
    assert rule_accounting_failures(report) == []


def test_generated_equals_matched_plus_invented():
    source = [_rule(100, 200, 300)]
    generated = [_rule(100, 200, 300), _rule(100, 200, 320), _rule(400, 500, 300)]
    report = _match(source, generated)

    assert (
        report["normalized_generated_rule_count"]
        == report["matched_rule_count"] + report["invented_rule_count"]
    )
    assert report["invented_rule_count"] == 2
    assert rule_accounting_failures(report) == []


def test_displaced_match_is_not_counted_as_both_matched_and_lost():
    """The Round 5.7 inconsistency: 8 source, 1 matched, 8 lost."""

    source = [_rule(94.80, 194.60, 138.35), _rule(95.25, 151.05, 218.40)]
    # Same physical blank (overlapping span, same neighbourhood) but 5 pt out.
    generated = [_rule(95.25, 151.05, 223.40)]
    report = _match(source, generated)

    assert report["matched_rule_count"] == 1
    assert report["matched_out_of_tolerance_count"] == 1
    assert report["lost_source_rule_count"] == 1
    assert report["invented_rule_count"] == 0
    assert report["normalized_source_rule_count"] == (
        report["matched_rule_count"] + report["lost_source_rule_count"]
    )
    assert report["normalized_generated_rule_count"] == (
        report["matched_rule_count"] + report["invented_rule_count"]
    )
    assert report["displaced"][0]["mandatory_geometry_ok"] is False
    assert rule_accounting_failures(report) == []


def test_one_generated_rule_cannot_match_two_source_rules():
    source = [_rule(100, 200, 300), _rule(100, 200, 300.5)]
    generated = [_rule(100, 200, 300)]
    report = _match(source, generated)

    assert report["matched_rule_count"] == 1
    assert report["lost_source_rule_count"] == 1
    assert len(report["pairs"]) == 1
    assert rule_accounting_failures(report) == []


def test_raw_counts_record_the_folded_inventory():
    source = [_rule(100, 200, 300)]
    generated = [_rule(100, 200, 300), _rule(200, 300, 300)]
    report = _match(source, generated)

    assert report["raw_source_rule_count"] == 1
    assert report["raw_generated_rule_count"] == 2
    assert report["normalized_source_rule_count"] == 1
    assert report["normalized_generated_rule_count"] == 2
    assert rule_accounting_failures(report) == []


def test_every_source_and_generated_rule_appears_exactly_once():
    source = [_rule(100, 200, 300), _rule(300, 400, 500), _rule(120, 180, 700)]
    generated = [_rule(100, 200, 300), _rule(305, 405, 505), _rule(700, 800, 900)]
    report = _match(source, generated)

    seen_source = [
        (pair["source"]["x0"], pair["source"]["x1"], pair["source"]["y"])
        for pair in report["pairs"]
    ] + [(rule["x0"], rule["x1"], rule["y"]) for rule in report["lost"]]
    seen_generated = [
        (pair["generated"]["x0"], pair["generated"]["x1"], pair["generated"]["y"])
        for pair in report["pairs"]
    ] + [(rule["x0"], rule["x1"], rule["y"]) for rule in report["invented"]]

    assert sorted(seen_source) == sorted(
        (rule["x0"], rule["x1"], rule["y"]) for rule in source
    )
    assert sorted(seen_generated) == sorted(
        (rule["x0"], rule["x1"], rule["y"]) for rule in generated
    )
    assert rule_accounting_failures(report) == []


def test_accounting_checker_rejects_an_inconsistent_report():
    broken = {
        "normalized_source_rule_count": 8,
        "normalized_generated_rule_count": 3,
        "matched_rule_count": 1,
        "lost_source_rule_count": 8,
        "invented_rule_count": 2,
        "pairs": [{}],
        "lost": [{}] * 8,
        "invented": [{}] * 2,
    }
    failures = rule_accounting_failures(broken)

    assert failures, "an inconsistent report must be rejected"
    assert any("lost" in failure for failure in failures)


def test_mandatory_invariants_are_declared():
    assert "source == matched + lost" in MATCH_INVARIANTS
    assert "generated == matched + invented" in MATCH_INVARIANTS
    assert "each rule appears exactly once" in MATCH_INVARIANTS
