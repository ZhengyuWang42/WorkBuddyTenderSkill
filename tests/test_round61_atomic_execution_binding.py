"""Atomic semantic-execution binding: composite slots, siblings and negatives.

The P3 semantic execution contract used to compare a slot's whole emitted surface
with one ProjectFacts value.  That is the right test for an ordinary slot, and
the wrong test for a composite source form slot - one the source itself writes as
template punctuation *plus* one or more facts *plus*, where a named component has
no fact behind it, the source form's own not-applicable marker.

These tests bank both halves of the replacement:

* the composite in the delivered CASE001 artifact validates atom by atom, and so
  does the already-existing P21 sibling composite, without creating a fact;
* an ordinary single-fact slot keeps the original strict equality contract;
* and every way a composite can be malformed still fails hard - a wrong fact, an
  unproven literal, a marker masquerading as a fact, a missing atom, a duplicated
  execution, an atom the source never printed, a reconstruction that does not
  reproduce the delivered text, and an unresolved fact promoted to a value
  because the source's marker happens to sit where it would.

The real builds are read when they are present in the workspace and skipped when
they are not, so the suite stays runnable on a clean checkout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tender_basic.composite_semantic_binding import (
    validate_presentation_atoms,
    validate_single_fact_surface,
)

ROOT = Path(__file__).resolve().parents[1]

CASE001_FINAL = (
    ROOT / "acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final"
)
P21_BUILD = ROOT / "acceptance/workspace/case_001/v1_manual_fidelity_round2_p21fix"

PROJECT_NAME = (
    "河南省水利第二工程局集团有限公司引江济淮郸城县配套工程水源置换城乡供水工程"
    "项目部一体化泵站采购项目"
)
PROJECT_NUMBER = "YSEJJXXB202607-18"

FACTS = {
    "project_name": {"status": "RESOLVED", "resolved_value": PROJECT_NAME},
    "lot_name": {"status": "NOT_FOUND", "resolved_value": None},
    "project_number": {"status": "RESOLVED", "resolved_value": PROJECT_NUMBER},
}


def _presentations(build: Path) -> list[dict]:
    report_path = build / "generation_report.json"
    if not report_path.exists():
        pytest.skip("build %s is not present in this workspace" % build.name)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return (report.get("slot_value_presentations") or {}).get("records") or []


def _by_slot(build: Path, slot_id: str) -> dict:
    for record in _presentations(build):
        if record.get("slot_id") == slot_id:
            return record
    pytest.skip("build %s records no presentation for %s" % (build.name, slot_id))


def _composite(value: str, components: list[dict], **extra) -> dict:
    return {
        "value": value,
        "method": "source_slot_composite_presentation",
        "components": components,
        "fact_components": [
            component["field"]
            for component in components
            if component["kind"] == "FACT_VALUE"
        ],
        "marker_components": [
            component["field"]
            for component in components
            if component["kind"] == "SOURCE_FORM_NOT_APPLICABLE_MARKER"
        ],
        **extra,
    }


def _fact(text: str, field: str = "project_name") -> dict:
    return {"kind": "FACT_VALUE", "field": field, "text": text, "source": "ProjectFacts"}


def _literal(text: str, source: str = "SOURCE_PLACEHOLDER_TEXT") -> dict:
    return {
        "kind": "SOURCE_TEMPLATE_LITERAL",
        "field": None,
        "text": text,
        "source": source,
    }


def _marker(field: str = "lot_name", text: str = "/") -> dict:
    return {
        "kind": "SOURCE_FORM_NOT_APPLICABLE_MARKER",
        "field": field,
        "text": text,
        "source": "SOURCE_FORM_STRUCTURE",
    }


# --------------------------------------------------------------------------- #
# The delivered composite, and its already-existing sibling
# --------------------------------------------------------------------------- #


def test_the_delivered_case001_composite_validates_atom_by_atom():
    record = _by_slot(CASE001_FINAL, "slot-42-3")
    outcome = validate_presentation_atoms(
        surface=record["value"],
        presentation=record,
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name", "project_number"],
    )
    assert outcome["ok"], outcome["notes"]
    assert outcome["accounting"]["reconstruction_equals_surface"] is True
    assert outcome["accounting"]["unaccounted_atoms"] == 0
    assert outcome["accounting"]["invented_atoms"] == 0
    assert outcome["accounting"]["fact_value_mismatches"] == 0
    assert outcome["accounting"]["duplicate_fact_executions"] == 0
    kinds = [row["provenance_class"] for row in outcome["atoms"]]
    assert kinds == [
        "SOURCE_TEMPLATE_LITERAL",
        "FACT_VALUE",
        "SOURCE_TEMPLATE_LITERAL",
        "SOURCE_FORM_NOT_APPLICABLE_MARKER",
        "SOURCE_TEMPLATE_LITERAL",
    ]
    assert outcome["fact_value_fields"] == ["project_name"]
    assert outcome["marker_fields"] == ["lot_name"]


def test_the_delivered_composite_is_not_equal_to_any_single_fact_value():
    """The whole reason the old contract rejected it - stated as a fact."""

    record = _by_slot(CASE001_FINAL, "slot-42-3")
    resolved = {
        str(payload.get("resolved_value"))
        for payload in FACTS.values()
        if payload.get("status") == "RESOLVED"
    }
    assert record["value"] not in resolved


def test_the_p21_sibling_composite_validates_without_creating_a_fact():
    record = _by_slot(P21_BUILD, "slot-60-14")
    outcome = validate_presentation_atoms(
        surface=record["value"],
        presentation=record,
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"], outcome["notes"]
    assert outcome["fact_value_fields"] == ["project_name"]
    assert outcome["marker_fields"] == ["lot_name"]
    # The marker is presentation: the fact it stands for keeps its own status
    # and is not turned into a value by the marker's presence.
    assert [row["marker_fact_status"] for row in outcome["atoms"] if row["field"] == "lot_name"] == [
        "NOT_FOUND"
    ]
    assert all(
        row.get("is_a_fact") is False
        for row in outcome["atoms"]
        if row["provenance_class"] == "SOURCE_FORM_NOT_APPLICABLE_MARKER"
    )


# --------------------------------------------------------------------------- #
# An ordinary slot keeps the original strict contract
# --------------------------------------------------------------------------- #


def test_an_ordinary_single_fact_slot_still_requires_exact_equality():
    ok = validate_single_fact_surface(
        surface=PROJECT_NAME,
        declared_fact_fields=["project_name", "lot_name"],
        fact_fields=FACTS,
    )
    assert ok["ok"] is True
    assert ok["matched_fields"] == ["project_name"]

    for drifted in (
        PROJECT_NAME + " ",
        " " + PROJECT_NAME,
        PROJECT_NAME[:-1],
        "（" + PROJECT_NAME + "）",
        PROJECT_NAME.replace("河南省", "河南省 "),
    ):
        rejected = validate_single_fact_surface(
            surface=drifted,
            declared_fact_fields=["project_name", "lot_name"],
            fact_fields=FACTS,
        )
        assert rejected["ok"] is False, drifted
        assert "EMITTED_VALUE_NOT_FROM_PROJECT_FACTS" in rejected["notes"]


def test_a_single_fact_slot_cannot_be_bound_to_a_fact_it_never_declared():
    outcome = validate_single_fact_surface(
        surface=PROJECT_NAME,
        declared_fact_fields=["lot_name"],
        fact_fields=FACTS,
    )
    assert outcome["ok"] is False


def test_a_non_composite_surface_that_is_not_a_fact_falls_back_and_fails():
    """No presentation record means no atom proof, so the strict test applies."""

    surface = PROJECT_NAME + "、/"
    assert validate_single_fact_surface(
        surface=surface,
        declared_fact_fields=["project_name", "lot_name"],
        fact_fields=FACTS,
    )["ok"] is False


# --------------------------------------------------------------------------- #
# Malformed composites must fail hard
# --------------------------------------------------------------------------- #


def _composite_surface() -> str:
    return "(" + PROJECT_NAME + "、/)"


def _valid_components() -> list[dict]:
    return [
        _literal("("),
        _fact(PROJECT_NAME),
        _literal("、", "SOURCE_SLOT_HINT"),
        _marker(),
        _literal(")"),
    ]


def test_the_known_good_composite_is_the_control_case():
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=_composite(_composite_surface(), _valid_components()),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"], outcome["notes"]


def test_negative_a_fact_value_that_differs_from_project_facts_fails():
    components = _valid_components()
    components[1] = _fact(PROJECT_NAME + "有限公司")
    surface = "(" + PROJECT_NAME + "有限公司、/)"
    outcome = validate_presentation_atoms(
        surface=surface,
        presentation=_composite(surface, components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert any(
        note.startswith("EMITTED_VALUE_NOT_FROM_PROJECT_FACTS") for note in outcome["notes"]
    )
    assert outcome["accounting"]["fact_value_mismatches"] == 1


def test_negative_a_literal_without_source_evidence_fails():
    components = _valid_components()
    components[0] = _literal("(", "MADE_UP_EVIDENCE")
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=_composite(_composite_surface(), components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert any(
        note.startswith("PROVENANCE_COMPONENT_WITHOUT_SOURCE_EVIDENCE")
        for note in outcome["notes"]
    )
    assert outcome["accounting"]["unidentified_component_sources"] == 1


def test_negative_a_presentation_marker_classified_as_a_fact_fails():
    components = _valid_components()
    # The marker is claimed to be the lot_name fact.  lot_name is NOT_FOUND, so
    # the claim cannot be honoured - a marker never promotes a fact to resolved.
    components[3] = _fact("/", "lot_name")
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=_composite(_composite_surface(), components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert any(
        note.startswith("EMITTED_VALUE_NOT_FROM_PROJECT_FACTS") for note in outcome["notes"]
    )
    assert outcome["accounting"]["fact_value_mismatches"] >= 1


def test_negative_an_unresolved_fact_cannot_be_promoted_by_a_marker():
    """The precise §FORM_NOT_APPLICABLE failure: "/" as a resolved lot_name."""

    facts = dict(FACTS)
    facts["lot_name"] = {"status": "NOT_FOUND", "resolved_value": "/"}
    components = _valid_components()
    components[3] = _fact("/", "lot_name")
    surface = "(" + PROJECT_NAME + "、/)"
    outcome = validate_presentation_atoms(
        surface=surface,
        presentation=_composite(surface, components),
        fact_fields=facts,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert outcome["accounting"]["fact_value_mismatches"] >= 1
    assert outcome["marker_fields"] == []
    # The marker never becomes the fact's value: the fact keeps its own status.
    assert facts["lot_name"]["status"] == "NOT_FOUND"


def test_negative_a_marker_over_a_resolved_fact_fails():
    components = _valid_components()
    components[3] = _marker("project_name")
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=_composite(_composite_surface(), components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert any(
        note.startswith("SOURCE_FORM_NOT_APPLICABLE_MARKER_OVER_A_RESOLVED_FACT")
        for note in outcome["notes"]
    )
    assert outcome["accounting"]["markers_over_a_resolved_fact"] == 1


def test_negative_a_missing_atom_provenance_fails():
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=_composite(_composite_surface(), []),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert "COMPOSITE_SURFACE_WITHOUT_ANY_PROVENANCE_COMPONENT" in outcome["notes"]


def test_negative_an_unclassified_component_fails():
    components = _valid_components()
    components.insert(0, {"kind": "PROBABLY_A_FACT", "field": None, "text": "(", "source": "ProjectFacts"})
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=_composite(_composite_surface(), components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert any(
        note.startswith("UNCLASSIFIED_PROVENANCE_COMPONENT") for note in outcome["notes"]
    )
    assert outcome["accounting"]["invented_atoms"] == 1


def test_negative_a_duplicated_fact_execution_fails():
    components = _valid_components()
    components.insert(2, _fact(PROJECT_NAME))
    surface = "(" + PROJECT_NAME + PROJECT_NAME + "、/)"
    outcome = validate_presentation_atoms(
        surface=surface,
        presentation=_composite(surface, components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert "DUPLICATE_FACT_EXECUTION:project_name" in outcome["notes"]
    assert outcome["accounting"]["duplicate_fact_executions"] == 1


def test_negative_an_extra_atom_the_source_never_printed_fails():
    components = _valid_components()
    components.append(_literal("附"))
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=_composite(_composite_surface(), components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert any(
        note.startswith("UNACCOUNTED_EMITTED_TEXT") or note.startswith("ATOMIC_RECONSTRUCTION")
        for note in outcome["notes"]
    )


def test_negative_a_reconstruction_that_does_not_reproduce_the_surface_fails():
    components = _valid_components()
    components[0] = _literal("（")
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=_composite(_composite_surface(), components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert "ATOMIC_RECONSTRUCTION_DOES_NOT_EQUAL_THE_DELIVERED_SURFACE" in outcome["notes"]


def test_negative_a_presentation_for_a_different_surface_fails():
    outcome = validate_presentation_atoms(
        surface="something else entirely",
        presentation=_composite(_composite_surface(), _valid_components()),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert "PRESENTATION_DOES_NOT_DESCRIBE_THE_EMITTED_SURFACE" in outcome["notes"]


def test_negative_a_fact_outside_the_permitted_field_set_fails():
    components = _valid_components()
    components[1] = _fact(PROJECT_NUMBER, "project_number")
    surface = "(" + PROJECT_NUMBER + "、/)"
    outcome = validate_presentation_atoms(
        surface=surface,
        presentation=_composite(surface, components),
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert any(
        note.startswith("FACT_VALUE_FIELD_OUTSIDE_THE_PERMITTED_FIELD_SET")
        for note in outcome["notes"]
    )
    assert outcome["accounting"]["facts_outside_the_permitted_field_set"] == 1


def test_decoration_never_reclassifies_an_atom():
    """A literal may inherit the slot underline and stay a literal."""

    components = _valid_components()
    presentation = _composite(
        _composite_surface(),
        components,
        source_slot_underline_inherited=True,
        underline_components=["FACT_VALUE"] * len(components),
    )
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=presentation,
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"] is False
    assert "SLOT_DECORATION_RECLASSIFIES_AN_ATOM" in outcome["notes"]


def test_a_literal_and_a_marker_may_be_underlined_and_stay_non_facts():
    components = _valid_components()
    presentation = _composite(
        _composite_surface(),
        components,
        source_slot_underline_inherited=True,
        underline_components=[component["kind"] for component in components],
    )
    outcome = validate_presentation_atoms(
        surface=_composite_surface(),
        presentation=presentation,
        fact_fields=FACTS,
        allowed_fact_fields=["project_name", "lot_name"],
    )
    assert outcome["ok"], outcome["notes"]
    assert outcome["fact_value_fields"] == ["project_name"]
    assert outcome["marker_fields"] == ["lot_name"]
