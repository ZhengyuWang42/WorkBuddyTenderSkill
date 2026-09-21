"""Round 5.8: compact lossless serialization of exact character geometry.

Compact JSON must not change any evidence: the field set and values are
identical, only the pretty-print indentation is gone.
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
from tender_basic.document_models import (  # noqa: E402
    NormalizedDocument,
    PdfCharacterGeometry,
    PdfTextSpan,
)
from tender_basic.source_format import (  # noqa: E402
    SourceRun,
    _characters_from_runs,
    _source_run_from_span,
    find_exact_character_boundary,
)

TOLERANCE_PT = 0.75
R3_TEXT = "（不含税），（小写）"
BASELINE_MB = 11.29

pytestmark = pytest.mark.skipif(
    not BUILD.available, reason=BUILD.skip_reason()
)


def _report() -> dict:
    return BUILD.report()


def _raw() -> dict:
    return json.loads(BUILD.normalized_document.read_text(encoding="utf-8"))


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


def _r8_run():
    report = _report()
    entry = next(
        r for r in report["source_rule_registry"] if r["source_rule_id"] == "P42-R8"
    )
    document = _document()
    span = next(
        s
        for s in _spans(document, 42)
        if s.bbox[1] - 2.0 <= entry["y"] <= s.bbox[3] + 2.0
        and min(s.bbox[2], entry["x1"]) - max(s.bbox[0], entry["x0"]) > 0
    )
    return _source_run_from_span(span), entry


# --- 1, 7: compact serialization round-trips ------------------------------


def test_compact_serialization_round_trips_exact_characters():
    document = _document()
    compact = json.dumps(document.model_dump(mode="json"), ensure_ascii=False)
    reloaded = NormalizedDocument.model_validate_json(compact)
    assert reloaded.model_dump(mode="json") == document.model_dump(mode="json")
    assert len(_spans(reloaded, 42)) == len(_spans(document, 42))


def test_bbox_values_are_stable_through_round_trip():
    document = _document()
    reloaded = NormalizedDocument.model_validate_json(
        json.dumps(document.model_dump(mode="json"), ensure_ascii=False)
    )
    for before, after in zip(_spans(document, 42), _spans(reloaded, 42)):
        for one, two in zip(before.characters, after.characters):
            assert tuple(one.bbox) == tuple(two.bbox)
            assert one.index == two.index
            assert one.character == two.character
            assert one.evidence_kind == two.evidence_kind


def test_persisted_artifact_is_compact_and_not_indented():
    text = BUILD.normalized_document.read_text(encoding="utf-8")
    assert "\n  " not in text[:200000], "artifact is still pretty-printed"
    line_count = text.count("\n")
    mib = len(text.encode("utf-8")) / 1048576
    assert line_count < 50, "artifact looks indented (%d lines)" % line_count
    assert mib <= 20.0, "artifact exceeds the 20 MiB target: %.2f MiB" % mib


def test_persisted_artifact_retains_union_discriminators():
    """exclude_defaults strips elements' `type` tag and breaks reload."""

    payload = _raw()
    assert payload["elements"], "no elements to check"
    missing = [i for i, item in enumerate(payload["elements"]) if "type" not in item]
    assert missing == [], "elements missing their union tag: %s" % missing[:5]
    NormalizedDocument.model_validate(payload)


# --- 2, 5, 6: default omission and origin ---------------------------------


def test_omitted_default_evidence_kind_reloads_as_exact():
    item = PdfCharacterGeometry(character="（", bbox=(262.68, 166.74, 274.68, 179.02))
    payload = json.loads(item.model_dump_json())
    payload.pop("evidence_kind")
    reloaded = PdfCharacterGeometry.model_validate(payload)
    assert reloaded.evidence_kind == "EXACT_PDF_CHAR"


def test_non_null_origin_survives_serialization():
    payload = _raw()
    origins = [
        c["origin"]
        for page in payload["pages"]
        for b in page.get("blocks", [])
        for line in b.get("lines", [])
        for span in line.get("spans", [])
        for c in span.get("characters", [])
        if c.get("origin")
    ]
    assert origins, "no non-null origins persisted"
    reloaded = _document()
    kept = [
        c.origin
        for page in reloaded.pages
        for b in page.blocks
        for line in b.lines
        for span in line.spans
        for c in span.characters
        if c.origin is not None
    ]
    assert len(kept) == len(origins)


def test_null_origin_may_be_omitted_safely():
    item = PdfCharacterGeometry(character="x", bbox=(1.0, 2.0, 3.0, 4.0), origin=None)
    payload = json.loads(item.model_dump_json())
    payload.pop("origin", None)
    reloaded = PdfCharacterGeometry.model_validate(payload)
    assert reloaded.origin is None
    assert reloaded.character == "x"
    assert tuple(reloaded.bbox) == (1.0, 2.0, 3.0, 4.0)


# --- 3, 4: approximate evidence -------------------------------------------


def test_approximate_evidence_kind_is_serialized_and_preserved():
    run = SourceRun(text=R3_TEXT, bbox=(262.68, 166.74, 384.48, 179.02))
    run.characters = _characters_from_runs([run])
    payload = json.loads(run.model_dump_json())
    kinds = {c["evidence_kind"] for c in payload["characters"]}
    assert kinds == {"APPROXIMATED_FROM_RUN_WIDTH"}
    reloaded = SourceRun.model_validate(payload)
    assert all(
        c.evidence_kind == "APPROXIMATED_FROM_RUN_WIDTH" for c in reloaded.characters
    )


def test_approximate_characters_survive_but_are_still_rejected():
    run = SourceRun(text=R3_TEXT, bbox=(262.68, 166.74, 384.48, 179.02))
    run.characters = _characters_from_runs([run])
    reloaded = SourceRun.model_validate_json(run.model_dump_json())
    for boundary in (262.68, 323.60):
        query = find_exact_character_boundary(reloaded, boundary, TOLERANCE_PT)
        assert query["aligned"] is False
        assert query["evidence_kind"] == "APPROXIMATED_FROM_RUN_WIDTH"


# --- 8, 9: boundary evidence unchanged ------------------------------------


def test_r3_boundary_result_unchanged_after_storage_change():
    run = _source_run_from_span(_r3_span())
    start = find_exact_character_boundary(run, 262.68, TOLERANCE_PT)
    end = find_exact_character_boundary(run, 323.60, TOLERANCE_PT)
    assert start["aligned"] and start["character_offset"] == 0
    assert start["evidence_kind"] == "EXACT_PDF_CHAR"
    assert end["aligned"] and end["character_offset"] == 5
    assert end["evidence_kind"] == "EXACT_PDF_CHAR"
    assert end["boundary_x_pt"] == 323.64
    assert end["boundary_error_pt"] == 0.04
    assert end["straddling_character"] is None
    assert run.text[:5] == "（不含税）"
    assert run.text[5:] == "，（小写）"


def test_r8_boundary_result_unchanged_after_storage_change():
    run, entry = _r8_run()
    for boundary in (entry["x0"], entry["x1"]):
        query = find_exact_character_boundary(run, boundary, TOLERANCE_PT)
        assert query["aligned"] is True
        assert query["evidence_kind"] == "EXACT_PDF_CHAR"
    report = _report()
    # P42-R8 preserves the source placeholder and is represented by its own
    # accepted composition in the current build.
    assert "P42-R8" in [
        c["source_rule_id"] for c in report.get("source_rule_compositions") or []
    ]


# --- 10, 11: backward compatibility --------------------------------------


def test_old_normalized_data_without_characters_still_loads():
    payload = _raw()
    for page in payload["pages"]:
        for block in page["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span.pop("characters", None)
    document = NormalizedDocument.model_validate(payload)
    assert all(not span.characters for span in _spans(document, 42))


def test_docx_source_without_characters_remains_valid():
    span = PdfTextSpan(text="供应商名称", bbox=(84.7, 390.0, 160.0, 402.0))
    assert span.characters == []
    run = _source_run_from_span(span)
    assert run.characters == []
    assert find_exact_character_boundary(run, 84.7, TOLERANCE_PT)["aligned"] is False


# --- 12: coverage unchanged ----------------------------------------------


def test_exact_source_span_coverage_is_complete():
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
    represented = exact & ({"P42-R4", "P42-R6"} | composed)
    assert represented == exact
    assert round(len(represented) / len(exact), 3) == 1.00
