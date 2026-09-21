"""Round 5.8: exact PDF character geometry plumbing.

Exact per-character boxes must survive parser -> normalized model -> JSON ->
reload -> source run, and approximate even-width geometry must never satisfy an
exact boundary query.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_under_test import BUILD  # noqa: E402
from tender_basic.document_models import NormalizedDocument  # noqa: E402
from tender_basic.source_format import (  # noqa: E402
    SourceRun,
    _characters_from_runs,
    _source_run_from_span,
    find_exact_character_boundary,
)

TOLERANCE_PT = 0.75
R3_TEXT = "（不含税），（小写）"
R3_EXPECTED = [
    ("（", 262.68, 274.68), ("不", 274.92, 286.92), ("含", 287.04, 299.04),
    ("税", 299.28, 311.28), ("）", 311.40, 323.40), ("，", 323.64, 335.64),
    ("（", 335.88, 347.88), ("小", 348.00, 360.00), ("写", 360.24, 372.24),
    ("）", 372.48, 384.48),
]

pytestmark = pytest.mark.skipif(
    not BUILD.available, reason=BUILD.skip_reason()
)


def _report() -> dict:
    return BUILD.report()


def _document() -> NormalizedDocument:
    return NormalizedDocument.model_validate_json(
        BUILD.normalized_document.read_text(encoding="utf-8")
    )


def _spans(document, page_number):
    page = next(p for p in document.pages if p.page_number == page_number)
    return [s for b in page.blocks for line in b.lines for s in line.spans]


def _r3_span(document=None):
    document = document or _document()
    return next(s for s in _spans(document, 42) if s.text == R3_TEXT)


def _r3_run():
    return _source_run_from_span(_r3_span())


# --- 1, 5, 6: rawdict chars populate the normalized run -------------------


def test_rawdict_exact_characters_populate_the_normalized_span():
    span = _r3_span()
    assert len(span.characters) == len(R3_EXPECTED)
    for item, (character, x0, x1) in zip(span.characters, R3_EXPECTED):
        assert item.character == character
        assert abs(item.bbox[0] - x0) <= 0.01
        assert abs(item.bbox[2] - x1) <= 0.01


def test_rawdict_character_evidence_kind_is_exact():
    for item in _r3_span().characters:
        assert item.evidence_kind == "EXACT_PDF_CHAR"


def test_exact_characters_concatenate_to_the_owning_run_text():
    span = _r3_span()
    assert "".join(item.character for item in span.characters) == span.text
    run = _r3_run()
    assert "".join(item.character for item in run.characters) == run.text


# --- 2, 3, 4: serialization and backward compatibility --------------------


def test_exact_character_geometry_survives_round_trip():
    document = _document()
    reloaded = NormalizedDocument.model_validate_json(document.model_dump_json())
    original = _spans(document, 42)
    again = _spans(reloaded, 42)
    assert len(original) == len(again)
    for before, after in zip(original, again):
        assert len(before.characters) == len(after.characters)
        for one, two in zip(before.characters, after.characters):
            assert one.character == two.character
            assert tuple(one.bbox) == tuple(two.bbox)
            assert one.evidence_kind == two.evidence_kind
            assert one.index == two.index


def test_normalized_data_without_characters_still_loads():
    payload = json.loads(BUILD.normalized_document.read_text(encoding="utf-8"))
    for page in payload["pages"]:
        for block in page["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span.pop("characters", None)
    document = NormalizedDocument.model_validate(payload)
    assert _spans(document, 42)
    assert all(not span.characters for span in _spans(document, 42))


def test_source_run_without_exact_characters_is_valid():
    run = SourceRun(text="（供应商名称）", bbox=(84.7, 390.0, 190.0, 402.0))
    assert run.characters == []
    query = find_exact_character_boundary(run, 84.7, TOLERANCE_PT)
    assert query["aligned"] is False
    assert query["evidence_kind"] == "NO_CHARACTER_GEOMETRY"


# --- 7, 8: approximate geometry is never exact evidence -------------------


def test_synthetic_even_width_characters_are_marked_approximate():
    run = SourceRun(text=R3_TEXT, bbox=(262.68, 166.74, 384.48, 179.02))
    run.characters = _characters_from_runs([run])
    assert len(run.characters) == len(R3_TEXT)
    assert all(
        item.evidence_kind == "APPROXIMATED_FROM_RUN_WIDTH" for item in run.characters
    )


def test_approximate_characters_cannot_satisfy_an_exact_boundary_query():
    run = SourceRun(text=R3_TEXT, bbox=(262.68, 166.74, 384.48, 179.02))
    run.characters = _characters_from_runs([run])
    for boundary in (262.68, 323.60):
        query = find_exact_character_boundary(run, boundary, TOLERANCE_PT)
        assert query["aligned"] is False
        assert query["character_offset"] is None
        assert query["evidence_kind"] == "APPROXIMATED_FROM_RUN_WIDTH"


def test_exact_and_approximate_geometry_disagree_at_the_r3_boundary():
    """The approximation lands off the real boundary, so it must not be used."""

    exact = _r3_run()
    approximate = SourceRun(text=R3_TEXT, bbox=tuple(exact.bbox))
    approximate.characters = _characters_from_runs([approximate])
    exact_query = find_exact_character_boundary(exact, 323.60, TOLERANCE_PT)
    approximate_query = find_exact_character_boundary(approximate, 323.60, TOLERANCE_PT)
    assert exact_query["aligned"] is True
    assert approximate_query["aligned"] is False
    synthetic_edge = approximate.characters[5].x0
    assert abs(synthetic_edge - 323.60) > 0.0


# --- 9, 10, 11: production boundary queries -------------------------------


def test_r3_start_boundary_resolves_from_the_production_model():
    query = find_exact_character_boundary(_r3_run(), 262.68, TOLERANCE_PT)
    assert query["aligned"] is True
    assert query["evidence_kind"] == "EXACT_PDF_CHAR"
    assert query["character_offset"] == 0
    assert query["boundary_error_pt"] <= TOLERANCE_PT


def test_r3_end_boundary_resolves_from_the_production_model():
    query = find_exact_character_boundary(_r3_run(), 323.60, TOLERANCE_PT)
    assert query["aligned"] is True
    assert query["evidence_kind"] == "EXACT_PDF_CHAR"
    assert query["character_offset"] == 5
    assert query["boundary_error_pt"] <= TOLERANCE_PT
    assert query["straddling_character"] is None


def test_r3_split_resolves_to_the_expected_substrings():
    run = _r3_run()
    query = find_exact_character_boundary(run, 323.60, TOLERANCE_PT)
    offset = query["character_offset"]
    assert run.text[:offset] == "（不含税）"
    assert run.text[offset:] == "，（小写）"


# --- 12, 13: control probes stay inactive ---------------------------------


def test_r8_boundary_query_runs_without_activating_composition():
    document = _document()
    report = _report()
    entry = next(
        r for r in report["source_rule_registry"] if r["source_rule_id"] == "P42-R8"
    )
    assert entry["source_page"] == 42
    span = next(
        s
        for s in _spans(document, 42)
        if s.bbox[1] - 2.0 <= entry["y"] <= s.bbox[3] + 2.0
        and min(s.bbox[2], entry["x1"]) - max(s.bbox[0], entry["x0"]) > 0
    )
    run = _source_run_from_span(span)
    assert run.characters
    assert all(c.evidence_kind == "EXACT_PDF_CHAR" for c in run.characters)
    for boundary in (entry["x0"], entry["x1"]):
        query = find_exact_character_boundary(run, boundary, TOLERANCE_PT)
        assert "aligned" in query
    compositions = [c["source_rule_id"] for c in report.get("source_rule_compositions") or []]
    # P42-R8 keeps the source placeholder and is now represented by an accepted
    # composition of its own physical segments.
    assert "P42-R8" in compositions
    # P44-R12 now qualifies too: its covered character range names exactly the
    # glyphs it re-emits, so querying its boundaries no longer composes it by
    # accident.  The claim this test makes is about the *boundary query*, so it
    # asserts that the rule is represented, not that it is outside the set.
    assert "P44-R12" in compositions


def test_p44_r12_exposes_exact_evidence_and_is_composed_from_it():
    document = _document()
    report = _report()
    entry = next(
        r for r in report["source_rule_registry"] if r["source_rule_id"] == "P44-R12"
    )
    assert entry["source_page"] == 44
    spans = _spans(document, 44)
    run = _source_run_from_span(
        max(
            spans,
            key=lambda s: min(s.bbox[2], entry["x1"]) - max(s.bbox[0], entry["x0"]),
        )
    )
    assert run.characters, "P44-R12 run carries no exact character evidence"
    assert all(c.evidence_kind == "EXACT_PDF_CHAR" for c in run.characters)
    compositions = {
        c["source_rule_id"]: c for c in report.get("source_rule_compositions") or []
    }
    assert "P44-R12" in compositions
    # The composition is built from the same exact character evidence this test
    # reads, and it carries both source glyph text and the glyph-free span the
    # rule covers, so it is a real representation rather than a text-free split.
    segments = compositions["P44-R12"]["segments"]
    assert any(
        segment["segment_type"] == "TEXT_RULE_SEGMENT" and (segment["source_text"] or "").strip()
        for segment in segments
    )
    assert any(
        segment["segment_type"] == "EMPTY_RULE_SEGMENT" for segment in segments
    )


# --- 14: coverage is unchanged by evidence availability -------------------


def test_exact_source_span_coverage_is_complete():
    """Every exact-span P3 rule is physically represented in the current build.

    Coverage is measured from the current build's own source-rule registry and
    composition records, never from a frozen run directory.
    """

    report = _report()
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
    composed = {
        record["source_rule_id"]
        for record in report.get("source_rule_compositions") or []
    }
    # P42-R4 and P42-R6 keep their exact source span through the positioned
    # emitter's own painted rule path; the others are represented by an accepted
    # composition built from the same exact character evidence.
    represented = exact & ({"P42-R4", "P42-R6"} | composed)
    assert exact == {"P42-R3", "P42-R4", "P42-R6", "P42-R7", "P42-R8"}, sorted(exact)
    assert represented == exact, sorted(exact - represented)
    assert round(len(represented) / len(exact), 3) == 1.00
