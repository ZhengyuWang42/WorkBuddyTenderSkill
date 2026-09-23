"""Atomic semantic-execution validation for emitted source-form slot values.

A composite source form slot prints more than one semantic component: the
source's own template punctuation, one or more resolved ProjectFacts values, and
- where a named component of the form has no fact behind it - the source form's
own not-applicable marker.  The value Word receives is therefore *not* expected
to equal any single ProjectFacts field, and a validator that compares the whole
emitted surface with one fact value rejects correct output.

This module validates such a value at the level it is actually composed on: the
atomic provenance the emitter already records at the write event
(``slot_value_presentations``), whose component vocabulary is defined once, in
:mod:`tender_basic.source_fill_policy`:

``FACT_VALUE``
    A ProjectFacts value.  The field must exist in the schema, the fact must be
    resolved, and the emitted text must equal the authoritative resolved value
    exactly.  Nothing is normalised here: any destination formatting is a
    rendering concern and is already applied before the atom is recorded.
``SOURCE_TEMPLATE_LITERAL``
    One visible character (or run of characters) of the source's own form text -
    the source's brackets and separators, which the form prints around its
    components.  It never resolves to a fact and never creates one.
``SOURCE_FORM_NOT_APPLICABLE_MARKER``
    The source form's own marker for a named component that is structurally
    absent.  It is presentation: it may sit over a fact that is *not* resolved,
    it can never cover a resolved fact, and it can never turn an unresolved fact
    into a resolved one.

The validator is a strict superset of whole-value equality, never a bypass: a
surface only passes when it is either (a) described atom by atom by a recorded
presentation that reconstructs it exactly and whose every atom is individually
accountable, or (b) exactly equal to one authoritative ProjectFacts value of a
field the application declared.  Anything else fails with the same notes the
whole-value check produced.

Decoration is kept deliberately separate from value provenance.  A source slot's
underline is inherited by every component that occupies the slot; it is evidence
of *where the source drew its rule*, not of what a component means.  A literal
and a marker may both be underlined and still be a literal and a marker - so the
decoration record is checked for consistency with the atoms, and is never
allowed to reclassify one.
"""

from __future__ import annotations

from typing import Any, Iterable

from tender_basic.source_fill_policy import (
    COMPONENT_FACT_VALUE,
    COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER,
    COMPONENT_SOURCE_TEMPLATE_LITERAL,
    SOURCE_FORM_NOT_APPLICABLE_MARKER,
)

SCHEMA = "composite_semantic_binding/1"

#: The provenance classes a component may carry.
COMPONENT_KINDS = (
    COMPONENT_FACT_VALUE,
    COMPONENT_SOURCE_TEMPLATE_LITERAL,
    COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER,
)

#: The evidence classes the emitter may name for a component.  A component whose
#: ``source`` is not one of these is not accountable.
APPROVED_COMPONENT_SOURCES = frozenset(
    {
        "ProjectFacts",
        "SOURCE_PLACEHOLDER_TEXT",
        "SOURCE_SLOT_HINT",
        "SOURCE_FORM_STRUCTURE",
    }
)

#: A surface decomposed into exactly one FACT_VALUE needs no presentation record;
#: it is the ordinary non-composite case.
SINGLE_FACT_NOTE = "SINGLE_FACT_VALUE_STRICT_EQUALITY"


def validate_presentation_atoms(
    *,
    surface: str,
    presentation: dict[str, Any],
    fact_fields: dict[str, Any],
    allowed_fact_fields: Iterable[str] = (),
    marker_literal: str = SOURCE_FORM_NOT_APPLICABLE_MARKER,
) -> dict[str, Any]:
    """Validate one atomically composed slot value.

    ``surface`` is the string the emitter actually delivered for this slot;
    ``presentation`` is the recorded composition of it; ``fact_fields`` is the
    ProjectFacts schema as delivered (``project_facts.json`` ``fields``);
    ``allowed_fact_fields`` is the set of fields the frozen contract and the
    application permit this rule to emit.
    """

    notes: list[str] = []
    atoms: list[dict[str, Any]] = []
    accounting = {
        "atom_count": 0,
        "unaccounted_atoms": 0,
        "invented_atoms": 0,
        "fact_value_mismatches": 0,
        "unidentified_component_sources": 0,
        "markers_over_a_resolved_fact": 0,
        "facts_outside_the_permitted_field_set": 0,
        "fields_used_as_both_value_and_non_value": 0,
        "duplicate_fact_executions": 0,
        "decoration_reclassifies_an_atom": 0,
        "reconstruction": None,
        "reconstruction_equals_surface": False,
    }

    recorded_value = str(presentation.get("value") or "")
    if recorded_value != surface:
        notes.append("PRESENTATION_DOES_NOT_DESCRIBE_THE_EMITTED_SURFACE")
        return {"ok": False, "notes": notes, "atoms": atoms, "accounting": accounting}

    components = list(presentation.get("components") or ())
    if not components:
        notes.append("COMPOSITE_SURFACE_WITHOUT_ANY_PROVENANCE_COMPONENT")
        return {"ok": False, "notes": notes, "atoms": atoms, "accounting": accounting}

    permitted = {str(field).lower() for field in allowed_fact_fields or ()}
    cursor = 0
    fact_value_fields: set[str] = set()
    non_value_fields: set[str] = set()

    for ordinal, component in enumerate(components):
        kind = component.get("kind")
        text = component.get("text")
        field = component.get("field")
        declared_source = component.get("source")
        row: dict[str, Any] = {
            "ordinal": ordinal,
            "provenance_class": kind,
            "field": field,
            "emitted_text": text,
            "declared_source": declared_source,
        }

        if kind not in COMPONENT_KINDS:
            notes.append(
                "UNCLASSIFIED_PROVENANCE_COMPONENT:%s" % (kind,)
            )
            accounting["invented_atoms"] += 1
            row["accounted"] = False
            atoms.append(row)
            continue
        if not isinstance(text, str) or not text:
            notes.append("PROVENANCE_COMPONENT_WITHOUT_TEXT:%s" % (ordinal,))
            accounting["invented_atoms"] += 1
            row["accounted"] = False
            atoms.append(row)
            continue
        if declared_source not in APPROVED_COMPONENT_SOURCES:
            notes.append(
                "PROVENANCE_COMPONENT_WITHOUT_SOURCE_EVIDENCE:%s" % (ordinal,)
            )
            accounting["unidentified_component_sources"] += 1

        # The atom must occupy the position the composition claims for it, in
        # order: this is what makes "concatenating the atoms reproduces the
        # delivered surface" a real check rather than a restatement.
        start = surface.find(text, cursor)
        row["surface_offset"] = start
        if start < 0:
            notes.append("UNACCOUNTED_EMITTED_TEXT:%s" % (ordinal,))
            accounting["unaccounted_atoms"] += 1
            row["accounted"] = False
        else:
            cursor = start + len(text)
            row["accounted"] = True

        if kind == COMPONENT_FACT_VALUE:
            field_name = str(field).lower() if field is not None else ""
            payload = fact_fields.get(field_name) or {}
            authoritative = payload.get("resolved_value")
            row["project_facts_status"] = payload.get("status")
            row["project_facts_resolved_value"] = authoritative
            row["fact_matches_project_facts"] = (
                bool(field_name)
                and payload.get("status") == "RESOLVED"
                and authoritative is not None
                and str(authoritative) == text
            )
            if field_name not in fact_fields:
                notes.append("FACT_VALUE_FIELD_NOT_IN_PROJECT_FACTS_SCHEMA:%s" % (field,))
            if not row["fact_matches_project_facts"]:
                notes.append("EMITTED_VALUE_NOT_FROM_PROJECT_FACTS:%s" % (field,))
                accounting["fact_value_mismatches"] += 1
            if permitted and field_name not in permitted:
                notes.append(
                    "FACT_VALUE_FIELD_OUTSIDE_THE_PERMITTED_FIELD_SET:%s" % (field,)
                )
                accounting["facts_outside_the_permitted_field_set"] += 1
            fact_value_fields.add(field_name)
        elif kind == COMPONENT_SOURCE_TEMPLATE_LITERAL:
            row["is_a_fact"] = False
            if field is not None:
                notes.append("SOURCE_TEMPLATE_LITERAL_CARRYING_A_FIELD:%s" % (field,))
                accounting["fields_used_as_both_value_and_non_value"] += 1
        else:  # SOURCE_FORM_NOT_APPLICABLE_MARKER
            field_name = str(field).lower() if field is not None else ""
            payload = fact_fields.get(field_name) or {}
            row["marker_fact_status"] = payload.get("status")
            row["is_a_fact"] = False
            row["marker_does_not_cover_a_resolved_fact"] = (
                payload.get("status") != "RESOLVED"
            )
            if text != marker_literal:
                notes.append("NOT_APPLICABLE_MARKER_IS_NOT_THE_SOURCE_FORMS_MARKER")
            if payload.get("status") == "RESOLVED":
                notes.append(
                    "SOURCE_FORM_NOT_APPLICABLE_MARKER_OVER_A_RESOLVED_FACT:%s"
                    % (field,)
                )
                accounting["markers_over_a_resolved_fact"] += 1
            if field_name not in fact_fields:
                notes.append(
                    "NOT_APPLICABLE_MARKER_NAMES_A_FIELD_NOT_IN_PROJECT_FACTS:%s"
                    % (field,)
                )
            non_value_fields.add(field_name)
        atoms.append(row)

    accounting["atom_count"] = len(atoms)
    reconstruction = "".join(str(component.get("text") or "") for component in components)
    accounting["reconstruction"] = reconstruction
    accounting["reconstruction_equals_surface"] = reconstruction == surface
    if reconstruction != surface:
        notes.append("ATOMIC_RECONSTRUCTION_DOES_NOT_EQUAL_THE_DELIVERED_SURFACE")
    if cursor != len(surface):
        notes.append("EMITTED_TEXT_LEFT_UNACCOUNTED")
        accounting["unaccounted_atoms"] += 1

    overlapping = fact_value_fields & non_value_fields
    if overlapping:
        notes.append(
            "FIELD_USED_AS_BOTH_A_VALUE_AND_A_NON_VALUE:%s"
            % (",".join(sorted(overlapping)),)
        )
        accounting["fields_used_as_both_value_and_non_value"] += len(overlapping)

    # One fact, one execution.  The same field resolving twice inside one
    # composed value means the plan executed more than once, whatever the two
    # copies happen to say.
    seen_fact_atoms: dict[str, int] = {}
    for row in atoms:
        if row["provenance_class"] != COMPONENT_FACT_VALUE:
            continue
        field_name = str(row.get("field")).lower()
        seen_fact_atoms[field_name] = seen_fact_atoms.get(field_name, 0) + 1
    duplicated = sorted(
        field for field, count in seen_fact_atoms.items() if count > 1
    )
    if duplicated:
        notes.append("DUPLICATE_FACT_EXECUTION:%s" % (",".join(duplicated),))
        accounting["duplicate_fact_executions"] += len(duplicated)

    # Decoration is presentation, never provenance: when the source slot's
    # underline is inherited, the components it decorates must be exactly the
    # atoms, in the same classes.  A decoration record that added or reclassified
    # a component would be claiming a value the source never printed.
    if presentation.get("source_slot_underline_inherited"):
        underline_kinds = list(presentation.get("underline_components") or ())
        component_kinds = [str(component.get("kind")) for component in components]
        row_kinds = [row["provenance_class"] for row in atoms]
        if underline_kinds and underline_kinds not in (component_kinds, row_kinds):
            notes.append("SLOT_DECORATION_RECLASSIFIES_AN_ATOM")
            accounting["decoration_reclassifies_an_atom"] += 1
        declared_facts = [str(item).lower() for item in presentation.get("fact_components") or ()]
        declared_markers = [
            str(item).lower() for item in presentation.get("marker_components") or ()
        ]
        if declared_facts and declared_facts != sorted(fact_value_fields):
            notes.append("RECORDED_FACT_COMPONENTS_DISAGREE_WITH_THE_ATOMS")
            accounting["decoration_reclassifies_an_atom"] += 1
        if declared_markers and declared_markers != sorted(
            field for field in non_value_fields if field
        ):
            notes.append("RECORDED_MARKER_COMPONENTS_DISAGREE_WITH_THE_ATOMS")
            accounting["decoration_reclassifies_an_atom"] += 1

    return {
        "ok": not notes,
        "notes": notes,
        "atoms": atoms,
        "accounting": accounting,
        "fact_value_fields": sorted(fact_value_fields),
        "marker_fields": sorted(field for field in non_value_fields if field),
    }


def validate_single_fact_surface(
    *,
    surface: str,
    declared_fact_fields: Iterable[str],
    fact_fields: dict[str, Any],
) -> dict[str, Any]:
    """The ordinary case: one emitted surface that must equal one fact value.

    Unchanged in meaning from the whole-value check it replaces - the surface
    must be exactly the authoritative resolved value of a field the application
    declared, and that field must be resolved in ProjectFacts.
    """

    declared = [str(field).lower() for field in declared_fact_fields or ()]
    matches = [
        field
        for field in declared
        if (fact_fields.get(field) or {}).get("status") == "RESOLVED"
        and str((fact_fields.get(field) or {}).get("resolved_value")) == surface
    ]
    return {
        "ok": bool(matches),
        "notes": [] if matches else ["EMITTED_VALUE_NOT_FROM_PROJECT_FACTS"],
        "matched_fields": matches,
    }
