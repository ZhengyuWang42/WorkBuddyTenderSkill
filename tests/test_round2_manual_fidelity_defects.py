"""Round-2 manual-fidelity regressions: the five defect classes.

Each test pins one defect class from the CASE001 manual Word review to the rule
that closes it, using only source-derived inputs - never a case, page, rule or
value literal in the production path:

* :mod:`test_round2_manual_fidelity_defects` defect 1 - underline ownership;
* defect 2 - forward-reachable positioned atoms never open a paragraph;
* defect 3 - a row's origin is its label, its fields are reached from there;
* defect 4 - the vertical rhythm is shared, not re-derived per row;
* defect 5 - a composite slot's presentation is provenance-tagged.

The complementary end-to-end evidence lives in the Stage C underline inventory
and the Stage H 10-check gate, which measure the artifacts themselves.
"""

from __future__ import annotations

from tender_basic.source_fill_policy import (
    COMPONENT_FACT_VALUE,
    COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER,
    COMPONENT_SOURCE_TEMPLATE_LITERAL,
    SOURCE_FORM_NOT_APPLICABLE_MARKER,
    composite_placeholder_ends_its_source_line,
    recorded_slot_presentation,
    reset_recorded_slot_presentations,
    slot_replacement,
)
from tender_basic.source_vertical_rhythm import (
    DEFAULT_PITCH_TOLERANCE_PT,
    SourceVerticalRhythm,
    dominant_line_pitch,
    rhythm_metrics,
)
from tender_basic.vertical_reflow_qa import ContentAtom, wrap_atoms

from test_review_builder import make_project_facts


# --------------------------------------------------------------------------- #
# Defect 2: forward-reachable positioned atoms stay in the row's paragraph
# --------------------------------------------------------------------------- #


def _atom(rule_id, x0, x1, advance, *, anchored=True):
    return ContentAtom(
        atom_kind="POSITIONED_BLANK",
        text="",
        source_x0=float(x0),
        source_x1=float(x1),
        advance_pt=float(advance),
        rule_id=rule_id,
        anchored=anchored,
        anchor_x=float(x0),
        geometry_source="SOURCE_RULE",
    )


def test_forward_reachable_anchor_stays_on_the_current_line():
    """An anchor ahead of the cursor is tabbed to, so it opens no new line."""

    atoms = [
        ContentAtom(
            atom_kind="PRESERVED_TEXT",
            text="成立时间：",
            source_x0=72.0,
            source_x1=130.0,
            advance_pt=58.0,
            rule_id=None,
            anchored=False,
            anchor_x=None,
            geometry_source="SOURCE_TEXT",
        ),
        _atom("R-x", 131.85, 179.85, 48.0),
    ]
    layout = wrap_atoms(atoms, first_line_start=72.0, line_start=70.8, right_limit=460.8)
    assert layout.line_count == 1
    assert layout.forced_new_line_rule_ids == []
    assert [item["placement"] for item in layout.placements] == [
        "FLOW",
        "FORWARD_TAB",
    ]


def test_backward_anchor_is_isolated_onto_its_own_line():
    """An anchor behind the cursor is geometrically unreachable on this line."""

    atoms = [
        ContentAtom(
            atom_kind="PRESERVED_TEXT",
            text="x" * 40,
            source_x0=72.0,
            source_x1=300.0,
            advance_pt=228.0,
            rule_id=None,
            anchored=False,
            anchor_x=None,
            geometry_source="SOURCE_TEXT",
        ),
        _atom("R-behind", 131.85, 179.85, 48.0),
    ]
    layout = wrap_atoms(atoms, first_line_start=72.0, line_start=70.8, right_limit=460.8)
    assert layout.line_count == 2
    assert layout.forced_new_line_rule_ids == ["R-behind"]
    assert layout.placements[-1]["reason"] == "backward_anchor_cannot_be_tabbed_to"


def test_measured_forward_reachability_outranks_the_width_estimate():
    """The emitter's own measurement wins over the wrap model's rounding.

    This is the clause whose label ends exactly at its anchor: the estimate puts
    the cursor a fraction past the anchor and would demand a whole extra generated
    line.  The emission measured the tab reaching the anchor, so the plan must
    follow the measurement - otherwise the region claims a row the page cannot
    hold and every row below it is displaced by one pitch.
    """

    atoms = [
        ContentAtom(
            atom_kind="PRESERVED_TEXT",
            text="label",
            source_x0=94.8,
            source_x1=353.0,
            advance_pt=258.2,
            rule_id=None,
            anchored=False,
            anchor_x=None,
            geometry_source="SOURCE_TEXT",
        ),
        _atom("R-boundary", 352.8, 388.8, 36.0),
    ]
    estimate_only = wrap_atoms(
        atoms, first_line_start=94.8, line_start=94.8, right_limit=460.8
    )
    assert estimate_only.forced_new_line_rule_ids == ["R-boundary"]
    measured = wrap_atoms(
        atoms,
        first_line_start=94.8,
        line_start=94.8,
        right_limit=460.8,
        forward_reachable_rule_ids=["R-boundary"],
    )
    assert measured.forced_new_line_rule_ids == []
    assert measured.line_count == 1
    placement = measured.placements[-1]
    assert placement["placement"] == "FORWARD_TAB"
    assert placement["reason"] == "emission_recorded_forward_reachable"
    #: The cursor never moves backwards, so a later atom cannot be mis-positioned.
    assert placement["starts_at_pt"] == 352.8


# --------------------------------------------------------------------------- #
# Defect 4: the vertical rhythm is shared, never re-derived per row
# --------------------------------------------------------------------------- #


def test_repeated_source_gaps_share_one_spacing_value():
    """Nine distinct row gaps collapse to the source's own spacing levels."""

    rows = [17.52, 17.52, 17.52, 17.4, 17.4, 17.66, 23.4, 23.4, 23.28]
    rhythm = SourceVerticalRhythm(rows, pitch_sample=rows)
    snapped = {round(rhythm.snap(gap), 2) for gap in rows}
    assert len(snapped) < len(set(rows))
    assert rhythm.class_count <= len(set(rows))


def test_snapping_never_advances_the_page_less_far_than_the_source():
    """A shared value is its class's largest member, so sharing never compresses.

    Rounding a gap down to its class's *smallest* member tightens a region until a
    source row is dropped, which is a vertical contract violation rather than a
    cosmetic difference.
    """

    rows = [17.4, 17.52, 17.66]
    rhythm = SourceVerticalRhythm(rows, pitch_sample=rows)
    for gap in rows:
        assert rhythm.snap(gap) >= gap - 1e-6
    assert rhythm.snap(17.4) == rhythm.snap(17.52) == rhythm.snap(17.66)


def test_a_fixed_anchor_stops_spacing_classes_from_chaining():
    """Near-misses cannot walk one class across the whole gap population."""

    spread = [10.0, 10.9, 11.8, 12.7, 13.6, 14.5, 15.4]
    rhythm = SourceVerticalRhythm(spread, pitch_sample=spread)
    assert rhythm.class_count > 1
    assert max(rhythm.distinct_values) - min(rhythm.distinct_values) < (
        max(spread) - min(spread)
    )


def test_sub_line_gaps_collapse_to_zero_with_evidence():
    """A gap worth a fraction of a line is an artefact, not a block boundary."""

    pitch = 18.0
    gaps = [pitch, pitch, pitch, pitch, 0.12, 0.28, 1.65]
    rhythm = SourceVerticalRhythm(gaps, pitch_sample=gaps)
    assert dominant_line_pitch(gaps) == pitch
    for artefact in (0.12, 0.28, 1.65):
        assert rhythm.snap(artefact) == 0.0
    assert sorted(rhythm.collapsed_sub_line_gaps) == [0.12, 0.28, 1.65]
    assert rhythm.as_dict()["collapsed_sub_line_gap_count"] == 3


def test_rhythm_metrics_separate_rows_from_block_boundaries():
    """Only the row population is the architectural target."""

    metrics = rhythm_metrics(
        before_values=[17.52, 17.4, 17.66, 23.4, 23.28],
        after_values=[17.52, 17.52, 23.4, 23.4],
        boundary_values=[205.95],
        block_records=[],
        spacing_classes=[
            {"value_pt": 17.52, "member_count": 3},
            {"value_pt": 23.4, "member_count": 2},
        ],
    )
    assert metrics["distinct_normal_row_space_before_before"] == 5
    assert metrics["distinct_normal_row_space_before_after"] < 5
    assert metrics["unexplained_custom_row_spacing_count_after"] == 0
    assert metrics["layout_boundary_spacing_count"] == 1


# --------------------------------------------------------------------------- #
# Defect 5: the composite slot's presentation is provenance-tagged
# --------------------------------------------------------------------------- #


def _line_level_slot(
    *,
    semantic_hint="项目名称、标段",
    original_text="（项目名称、标段）",
    suffix_text="\r\n询比活动中，我公司保证做到：",
    slot_id="synthetic-composite",
):
    from tender_basic.models import FieldName, PdfLocator
    from tender_basic.source_format import SourceFillSlot

    return SourceFillSlot(
        slot_id=slot_id,
        semantic_hint=semantic_hint,
        slot_type="PROJECT_AND_LOT_SLOT",
        source_page=1,
        source_locator=PdfLocator(page=1, block_index=0),
        container_type="paragraph",
        original_text=original_text,
        suffix_text=suffix_text,
        match_kind="parenthetical",
        allowed_fact_fields=[FieldName.PROJECT_NAME, FieldName.LOT_NAME],
    )


def test_line_level_composite_slot_marks_the_absent_component():
    """A placeholder that ends its own source line composes with the marker."""

    reset_recorded_slot_presentations()
    slot = _line_level_slot()
    value, method = slot_replacement(slot, make_project_facts())
    assert value == "测试工程" + "、" + SOURCE_FORM_NOT_APPLICABLE_MARKER
    assert method == "source_slot_composite_presentation"
    presentation = recorded_slot_presentation(slot)
    assert presentation is not None
    assert [item["kind"] for item in presentation["components"]] == [
        COMPONENT_FACT_VALUE,
        COMPONENT_SOURCE_TEMPLATE_LITERAL,
        COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER,
    ]
    assert presentation["fact_components"] == ["project_name"]
    # The marker names the field whose source component has no fact behind it,
    # but it is never itself a fact and it never changes that field's status.
    assert presentation["marker_components"] == ["lot_name"]


def test_composite_marker_does_not_create_or_resolve_a_fact():
    """``lot_name`` keeps its own status; the marker is presentation only."""

    reset_recorded_slot_presentations()
    facts = make_project_facts()
    before = facts.fields.lot_name.model_copy(deep=True) if hasattr(
        facts.fields.lot_name, "model_copy"
    ) else facts.fields.lot_name
    slot = _line_level_slot()
    slot_replacement(slot, facts)
    after = facts.fields.lot_name
    assert after.status.value == "NOT_FOUND"
    assert after.resolved_value is None
    assert after.candidates == []
    assert after.status == before.status
    assert after.candidates == before.candidates


def test_inline_composite_slot_is_left_alone():
    """A placeholder mid-line keeps the accepted plain join.

    The marker states "this source form has no such component", which is only
    true of a form line that gives the component its own line.  An inline
    placeholder is part of a running sentence, where a marker would read as
    content the source never wrote.
    """

    reset_recorded_slot_presentations()
    slot = _line_level_slot(
        original_text="(项目名称、标段)",
        suffix_text="（项目编号）询比文件的全部内容，愿意",
    )
    assert composite_placeholder_ends_its_source_line(slot) is False
    value, _ = slot_replacement(slot, make_project_facts())
    assert SOURCE_FORM_NOT_APPLICABLE_MARKER not in value
    assert recorded_slot_presentation(slot) is None


def test_composite_presentation_is_not_recorded_for_a_plain_slot():
    """A slot that is not the composite one records no presentation."""

    reset_recorded_slot_presentations()
    slot = _line_level_slot(
        semantic_hint="供应商名称",
        original_text="（供应商名称）",
        slot_id="synthetic-plain",
    )
    slot.slot_type = "UNKNOWN_SLOT"
    slot_replacement(slot, make_project_facts())
    assert recorded_slot_presentation(slot) is None
