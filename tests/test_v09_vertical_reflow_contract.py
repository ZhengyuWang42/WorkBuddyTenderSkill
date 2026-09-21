"""V0.9: REFLOW_AWARE_V1 vertical contract regressions.

The frozen Phase-3 gate compared each rule's generated y against its source y
with a flat 2.0pt tolerance.  That test cannot separate a renderer defect from
reflow the source's own content forces.  These tests pin the reflow-aware
contract that replaces it:

* the minimum generated line count of a source visual row is computed from the
  row's *own measured content*, never from the generated row count;
* mandatory expansion is allowed only when it is independently justified, and
  only for rows at or below the point that needs it;
* a backward anchor may be isolated onto its own line only when all six
  structural conditions are measured true;
* the residual tolerance stays at 2.0pt, and the raw source-y difference stays
  visible in the report;
* the frozen horizontal, semantic, ownership and assembly architecture is
  unchanged.
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

from tender_basic.vertical_reflow_qa import (  # noqa: E402
    ATOM_ANCHOR_RULE,
    ATOM_PRESERVED_TEXT,
    CONTRACT_VERSION,
    MEASURE_EPSILON_PT,
    REASON_CONTENT_REFLOW,
    REASON_FITS,
    REASON_STRUCTURAL_ISOLATION,
    TOLERANCE_PT,
    ContentAtom,
    account_region_rows,
    detect_blank_row_gaps,
    evaluate_isolation,
    mandatory_extra_lines,
    reflow_axis,
    wrap_atoms,
)
from tender_basic.vertical_reflow_region import (  # noqa: E402
    build_region_reflow_plan,
)

REPORTS = ROOT / "acceptance" / "reports" / "v09_internal_preview"
P3_GATE = REPORTS / "p3_final_round58_gate.json"
PHASE2_GATE = REPORTS / "p3_phase2_gate.json"
OWNERSHIP_GATE = REPORTS / "phase1_execution_ownership_closure.json"
ASSEMBLY_GATE = REPORTS / "source_line_assembly_gate.json"
FINAL_REPORT = REPORTS / "v09_final_preview_report.json"

REGION_LEFT = 70.80
RIGHT_LIMIT = 523.92
FIRST_LINE_START = 96.84
USABLE_NARROW = RIGHT_LIMIT - FIRST_LINE_START
USABLE_WIDE = RIGHT_LIMIT - REGION_LEFT
SOUND_PITCH = 21.21

P3_REGION_RULE_IDS = tuple("P42-R%d" % index for index in range(1, 9))


def _flow(advance: float) -> list[ContentAtom]:
    return [
        ContentAtom(
            atom_kind=ATOM_PRESERVED_TEXT,
            text="x",
            source_x0=REGION_LEFT,
            source_x1=REGION_LEFT + advance,
            advance_pt=advance,
        )
    ]


def _wrap(atoms: list[ContentAtom]):
    return wrap_atoms(
        atoms,
        first_line_start=FIRST_LINE_START,
        line_start=REGION_LEFT,
        right_limit=RIGHT_LIMIT,
    )


def _gate() -> dict:
    return json.loads(P3_GATE.read_text(encoding="utf-8"))


def _side_gate(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1-3: the minimum line count comes from measured content, not from the render
# --------------------------------------------------------------------------- #


def test_fitting_source_line_earns_no_reflow_budget() -> None:
    """A row whose measured content fits one generated line forces nothing."""

    layout = _wrap(_flow(USABLE_NARROW - 1.0))
    assert layout.line_count == 1
    assert mandatory_extra_lines(layout.line_count, 1) == 0


def test_two_required_lines_earn_exactly_one_extra_line() -> None:
    """Content needing two lines forces exactly one mandatory extra line."""

    layout = _wrap(_flow(USABLE_NARROW + 1.0))
    assert layout.line_count == 2
    assert mandatory_extra_lines(layout.line_count, 1) == 1


def test_three_required_lines_earn_exactly_two_extra_lines() -> None:
    """The 940pt-class row: two wrapped lines force two mandatory extra lines."""

    narrow, wide = USABLE_NARROW, USABLE_WIDE
    #: 1.5x the narrow capacity overflows into a second line, and the remaining
    #: payload needs the wide capacity twice over.
    layout = _wrap(_flow(narrow + wide + 1.0))
    assert layout.line_count == 3
    assert mandatory_extra_lines(layout.line_count, 1) == 2


def test_wide_continuation_capacity_is_measured_separately() -> None:
    """Continuation lines use the region's left edge, not the first-line indent."""

    assert USABLE_WIDE > USABLE_NARROW
    layout = _wrap(_flow(USABLE_NARROW + 1.0))
    assert layout.line_count == 2
    assert layout.line_ends[0] <= RIGHT_LIMIT


# --------------------------------------------------------------------------- #
# 4 & 12: an unjustified row - including a blank one - never earns budget
# --------------------------------------------------------------------------- #


def test_generated_extra_row_without_justification_is_unexplained() -> None:
    """One generated row more than the mandatory minimum is a failure."""

    accounting = account_region_rows(
        source_row_count=14,
        group_minimum_lines=[3],
        group_row_counts=[1],
        generated_row_count=17,
    )
    assert accounting["mandatory_extra_row_count"] == 2
    assert accounting["mandatory_minimum_row_count"] == 16
    assert accounting["unexplained_extra_row_count"] == 1
    assert accounting["rows_accounted"] is False

    justified = account_region_rows(
        source_row_count=14,
        group_minimum_lines=[3],
        group_row_counts=[1],
        generated_row_count=16,
    )
    assert justified["unexplained_extra_row_count"] == 0
    assert justified["rows_accounted"] is True


def test_blank_row_never_receives_reflow_budget() -> None:
    """An accidental blank paragraph is detected and never justified."""

    rows = [
        {"top": 100.0, "text": "a", "lines": [{"bottom": 112.0}]},
        {"top": 142.0, "text": "b", "lines": [{"bottom": 154.0}]},
    ]
    gaps = detect_blank_row_gaps(rows, SOUND_PITCH, 1.6)
    assert gaps, "a gap of 42pt against a 21.21pt pitch must be visible"
    accounting = account_region_rows(
        source_row_count=2,
        group_minimum_lines=[1, 1],
        group_row_counts=[1, 1],
        generated_row_count=2,
        unexplained_blank_row_count=len(gaps),
    )
    assert accounting["rows_accounted"] is False


# --------------------------------------------------------------------------- #
# 5 & 6: expansion propagates downstream, one target per source row
# --------------------------------------------------------------------------- #


def test_cumulative_reflow_moves_only_rows_below_it() -> None:
    """A later group's extra lines cannot move a row above it."""

    axis = reflow_axis([[1], [3, 3], [1]])
    #: Group 2's first row needs three lines on its own, so the second row of
    #: that group starts two lines lower; the row above the group does not move.
    assert axis["extra_lines_attributed_to_row"] == [0, 2, 0, 0]
    assert axis["cumulative_extra_lines_before_row"] == [0, 0, 2, 1]
    assert axis["extra_lines_after_region"] == 1

    downstream = reflow_axis([[1], [1], [1], [1]])
    assert downstream["extra_lines_attributed_to_row"] == [0, 0, 0, 0]
    assert downstream["cumulative_extra_lines_before_row"] == [0, 0, 0, 0]
    assert downstream["extra_lines_after_region"] == 0


def test_each_source_logical_row_receives_one_adjusted_target() -> None:
    """Every row has exactly one reflow-adjusted target, and it is unique."""

    gate = _gate()
    rows = gate["vertical_reflow"]["rows"]
    assert rows
    assert len({row["source_visual_line_id"] for row in rows}) == len(rows)
    for row in rows:
        expected = round(
            row["source_y"]
            + row["region_origin_offset_pt"]
            + row["line_pitch_expansion_before_row_pt"]
            + row["cumulative_mandatory_reflow_before_row_pt"],
            2,
        )
        assert abs(row["reflow_adjusted_target_y"] - expected) <= 0.01
        assert row["residual_y_error"] == pytest.approx(
            row["actual_generated_y"] - row["reflow_adjusted_target_y"], abs=0.01
        )


def test_expansion_reason_matches_the_measured_cause() -> None:
    """Row reasons are derived, not asserted."""

    rows = _gate()["vertical_reflow"]["rows"]
    for row in rows:
        if row["mandatory_extra_line_count"] == 0:
            assert row["expansion_reason"] == REASON_FITS
        elif row["forced_new_line_rule_ids"]:
            assert row["expansion_reason"] == REASON_STRUCTURAL_ISOLATION
        else:
            assert row["expansion_reason"] == REASON_CONTENT_REFLOW


# --------------------------------------------------------------------------- #
# 7-9: the raw difference stays visible and the tolerance is never relaxed
# --------------------------------------------------------------------------- #


def test_raw_source_y_difference_is_preserved_in_the_report() -> None:
    """Normalising the target must not hide the raw source-y difference."""

    gate = _gate()
    rows = gate["vertical_reflow"]["rows"]
    assert all(row["raw_y_error"] is not None for row in rows)
    for row in rows:
        assert row["raw_y_error"] == pytest.approx(
            row["actual_generated_y"] - row["source_y"], abs=0.01
        )
    assert gate["vertical_reflow"]["raw_vertical_source_fidelity_difference_present"]
    assert gate["vertical_reflow"]["maximum_raw_y_error_pt"] > TOLERANCE_PT
    assert gate["frozen_absolute_vertical_failure_ids"], (
        "the frozen absolute test must still record its own failures"
    )


def test_residual_tolerance_remains_two_points() -> None:
    """The reflow-aware gate reuses the frozen tolerance; it does not widen it."""

    assert TOLERANCE_PT == 2.0
    gate = _gate()
    assert gate["tolerance_pt"] == 2.0
    assert gate["vertical_reflow"]["tolerance_pt"] == 2.0
    assert gate["checks"]["vertical_tolerance_is_frozen"] is True
    for row in gate["vertical_reflow"]["rows"]:
        assert abs(row["residual_y_error"]) <= 2.0
        assert row["pass"] is True


def test_no_larger_global_vertical_tolerance_is_introduced() -> None:
    """No tolerance anywhere in the canonical report exceeds 2.0pt."""

    offenders: list[tuple[str, float]] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, "%s.%s" % (path, key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, "%s[%d]" % (path, index))
        elif isinstance(node, (int, float)) and "tolerance" in path.lower():
            if float(node) > 2.0:
                offenders.append((path, float(node)))

    walk(_gate(), "gate")
    assert offenders == []


# --------------------------------------------------------------------------- #
# 10-11: structural isolation must be proven, never assumed
# --------------------------------------------------------------------------- #


def test_backward_anchor_impossibility_authorises_isolation() -> None:
    """A tab cannot move backward, so an unreachable anchor is a real cause."""

    evidence = evaluate_isolation(
        rule_id="PX-R7",
        source_anchor_x=352.80,
        cursor_before_pt=352.80,
        anchor_start_preserved=True,
        preceding_content_present=True,
        reading_order_is_source_order=True,
        candidate_stops=[388.80, 400.80],
        expansion_height_pt=SOUND_PITCH,
    )
    assert evidence.proven is True
    assert all(evidence.conditions.values())
    assert evidence.next_forward_tab_stop_pt == 388.80
    assert evidence.same_line_error_pt > TOLERANCE_PT
    assert evidence.expansion_height_pt == pytest.approx(SOUND_PITCH, abs=0.01)


def test_isolation_without_proof_earns_no_budget() -> None:
    """A reachable anchor, or unmeasured conditions, must not buy an extra line."""

    reachable = evaluate_isolation(
        rule_id="PX-R7",
        source_anchor_x=352.80,
        cursor_before_pt=300.00,
        anchor_start_preserved=True,
        preceding_content_present=True,
        reading_order_is_source_order=True,
        candidate_stops=[352.80, 388.80],
        expansion_height_pt=SOUND_PITCH,
    )
    assert reachable.proven is False
    assert reachable.expansion_height_pt == 0.0

    unmeasured = evaluate_isolation(
        rule_id="PX-R7",
        source_anchor_x=352.80,
        cursor_before_pt=352.80,
        anchor_start_preserved=False,
        preceding_content_present=True,
        reading_order_is_source_order=True,
        candidate_stops=[388.80],
        expansion_height_pt=SOUND_PITCH,
    )
    assert unmeasured.proven is False
    assert unmeasured.expansion_height_pt == 0.0


def test_region_forcings_are_all_proven() -> None:
    """Every forced new line in the live region carries a measured proof."""

    gate = _gate()
    reflow = gate["vertical_reflow"]
    forced = {
        rule_id
        for row in reflow["rows"]
        for rule_id in row["forced_new_line_rule_ids"]
    }
    proven = {
        record["source_rule_id"]
        for record in reflow["structural_isolations"]
        if record["structural_isolation_proven"]
    }
    assert forced == {"P42-R7"}
    assert forced <= proven
    assert reflow["rows"][0]["region_origin_offset_pt"] == pytest.approx(
        reflow["region_origin_offset_pt"], abs=0.01
    )


# --------------------------------------------------------------------------- #
# 13-16: frozen architecture non-regression
# --------------------------------------------------------------------------- #


def test_horizontal_contract_is_still_eight_of_eight() -> None:
    """All eight frozen rules are still matched inside tolerance."""

    gate = _gate()
    horizontal = gate["horizontal"]
    assert gate["checks"]["horizontal_within_tolerance"] is True
    assert horizontal["horizontal_failure_ids"] == gate["horizontal_failure_ids"] == []
    assert horizontal["matched"] == 8
    assert horizontal["lost"] == 0
    assert horizontal["out_of_tolerance"] == 0
    assert horizontal["coverage"]["ratio"] == 1.0
    assert _side_gate(PHASE2_GATE)["status"] == "PASS"


def test_p3_semantic_rows_are_still_eight_of_eight() -> None:
    """Every frozen rule keeps its accepted policy and geometry intent."""

    gate = _gate()
    semantics = gate["semantics"]
    assert len(semantics["transformation_policy_rows"]) == 8
    assert len(semantics["geometry_intent_rows"]) == 8
    assert semantics["accepted_composition_set_unchanged"] is True
    assert gate["horizontal"]["accepted_composition_set"] == gate["horizontal"][
        "observed_composition_set"
    ]


def test_execution_ownership_is_unchanged() -> None:
    """The Phase-1 ownership closure still holds and stays the only owner."""

    gate = _gate()
    ownership = gate["execution_ownership"]
    assert ownership["present"] is True
    assert ownership["status"] == "PASS"
    assert ownership["failed_checks"] == []
    assert all(ownership["checks"].values())
    side = _side_gate(OWNERSHIP_GATE)
    assert side["status"] == "PASS"
    assert side["failed_checks"] == []
    applications = gate["applications"]
    assert applications["planned_resolved_application_count"] == 4
    assert applications["actual_resolved_application_count"] == 4
    assert applications["missing_planned_application_count"] == 0
    assert applications["unexpected_application_count"] == 0
    conclusion = ownership["conclusion"]
    for rule_id in ("P40-R1", "P45-R6"):
        assert conclusion["%s_new_plan_driven_execution_owner" % rule_id] == 0
        assert conclusion["%s_new_plan_driven_value_emission" % rule_id] == 0


def test_source_line_assembly_is_unchanged() -> None:
    """The shared source-row composition architecture still measures clean."""

    gate = _gate()
    assembly = gate["source_line_assembly"]
    assert assembly["present"] is True
    assert assembly["status"] == "PASS"
    assert assembly["failed_checks"] == []
    side = _side_gate(ASSEMBLY_GATE)
    assert side["status"] == "PASS"
    assert side["failed_checks"] == []
    assert gate["checks"]["no_absolute_positioning"] is True
    assert gate["safety"]["generated_textbox_count"] == 0


# --------------------------------------------------------------------------- #
# Live-build contract checks
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not BUILD.available, reason=BUILD.skip_reason())
def test_live_region_plan_is_non_circular_and_fully_accounted() -> None:
    """The live plan derives its minimum from measured content and explains all rows."""

    import pymupdf

    source_doc = pymupdf.open(BUILD.source_pdf)
    generated_doc = pymupdf.open(BUILD.pdf)
    try:
        region = build_region_reflow_plan(
            source_doc=source_doc,
            generated_doc=generated_doc,
            report=BUILD.report(),
            source_page=42,
            generated_page=3,
            region_rule_ids=P3_REGION_RULE_IDS,
        )
    finally:
        source_doc.close()
        generated_doc.close()

    assert region["vertical_contract_version"] == CONTRACT_VERSION
    assert region["row_accounting"]["rows_accounted"] is True
    assert region["unexplained_extra_row_count"] == 0
    assert region["unexplained_blank_row_gaps"] == []
    assert region["generated_region_rows"] == region["mandatory_minimum_generated_rows"]
    assert region["generated_row_order_preserved"] is True
    assert region["all_rows_matched"] is True

    #: Non-circularity: each row's minimum follows from its own measured width.
    for row in region["_plans"]:
        assert row.minimum_required_generated_line_count >= 1
        assert row.available_width > 0
        assert row.first_line_width <= row.available_width + MEASURE_EPSILON_PT
        assert row.participating_content
        for atom in row.participating_content:
            assert atom["advance_pt"] >= -MEASURE_EPSILON_PT

    #: The contract is only sound when the raw difference it explains is real.
    assert region["raw_vertical_source_fidelity_difference_present"] is True
    assert region["mandatory_reflow_present"] is True
    assert region["maximum_residual_y_error_pt"] <= TOLERANCE_PT
    assert region["maximum_raw_y_error_pt"] > TOLERANCE_PT


def test_final_preview_report_repeats_the_gate_verdicts() -> None:
    """The handover report carries the gates' own verdicts, not a new one."""

    report = json.loads(FINAL_REPORT.read_text(encoding="utf-8"))
    assert report["vertical_contract_version"] == CONTRACT_VERSION
    assert report["status"] == "V0.9_INTERNAL_PREVIEW"
    assert report["failing_gates"] == []
    assert all(record["status"] == "PASS" for record in report["gates"].values())
    assert report["gates"]["phase3_canonical"]["sha256"] == _sha256(P3_GATE)

    flags = report["flags"]
    assert flags["INTERNAL_PREVIEW"] is True
    assert flags["READY_FOR_INTERNAL_TRIAL"] is True
    assert flags["MANUAL_WORD_REVIEW_REQUIRED"] is True
    assert flags["READY_FOR_SUBMISSION"] is False
    assert flags["raw_vertical_source_fidelity_difference_present"] is True
    assert flags["manual_word_review_required"] is True
    assert flags["ready_for_submission"] is False

    evidence = report["vertical_evidence"]
    assert evidence["unexplained_vertical_expansion_count"] == 0
    assert evidence["mandatory_reflow_fully_explains_vertical_difference"] is True
    assert evidence["vertical_residual_within_2pt"] is True
    assert evidence["raw_vertical_source_fidelity_difference_present"] is True
    assert evidence["maximum_raw_y_error_pt"] > TOLERANCE_PT

    contract = report["reflow_contract"]
    assert contract["tolerance_relaxed"] is False
    assert contract["required_line_count_source"] == "MEASURED_SOURCE_CONTENT_WIDTH"
    assert contract["required_line_count_derived_from_generated_rows"] is False
    assert contract["renderer_modules_modified"] == []

    suite = report["non_regression"]["test_suite"]
    assert suite["present"] is True
    assert suite["failures"] == 0
    assert suite["errors"] == 0
    assert suite["passed"] >= suite_baseline(report) + 20


def suite_baseline(report: dict) -> int:
    return int(report["non_regression"]["test_suite_baseline"]["reference_passed"])


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
