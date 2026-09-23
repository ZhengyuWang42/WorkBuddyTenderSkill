"""The P21 structural gate's own contract.

The gate is the thing that decides whether two structural defects are closed, so
it needs its own tests: the composite slot must be found from presentation
provenance alone, the four underline states must stay distinguishable, and the
delivered artifact must satisfy the gate end to end.  A gate that cannot tell an
underline that never reached the page from one that arrived without a rule to own
it would report the very defect it exists to catch as a pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from v1_manual_review_p21_diagnostic import _underline_state  # noqa: E402
from v1_p21_structural_gate import _composite_records  # noqa: E402
from v1_p21_followup_status import passed, status_of  # noqa: E402
from v1_manual_review_checklist import structural_review_points  # noqa: E402

BUILD = ROOT / "acceptance/workspace/case_001/v1_manual_fidelity_round2_p21fix"
SOURCE_PDF = ROOT / "acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf"


def _record(**overrides) -> dict:
    record = {
        "slot_id": "slot-x",
        "value": "某公司采购项目、/",
        "components": [
            {"kind": "FACT_VALUE", "text": "某公司采购项目", "field": "project_name"},
            {"kind": "SOURCE_TEMPLATE_LITERAL", "text": "、", "field": None},
            {"kind": "SOURCE_FORM_NOT_APPLICABLE_MARKER", "text": "/", "field": "lot_name"},
        ],
    }
    record.update(overrides)
    return record


def test_a_composite_slot_is_found_from_its_component_provenance():
    """A marker beside a resolved value is the composite, whatever it is called."""

    found = _composite_records({"slot_value_presentations": {"records": [_record()]}})
    assert len(found) == 1
    # Renaming the slot, the fact and every literal keeps the composite composite:
    # nothing in the identification is keyed to a case, a page or a value.
    renamed = _composite_records(
        {
            "slot_value_presentations": {
                "records": [
                    _record(
                        slot_id="slot-other",
                        value="乙供应商报价表、/",
                        components=[
                            {"kind": "FACT_VALUE", "text": "乙供应商报价表", "field": "supplier_name"},
                            {"kind": "SOURCE_TEMPLATE_LITERAL", "text": "、", "field": None},
                            {
                                "kind": "SOURCE_FORM_NOT_APPLICABLE_MARKER",
                                "text": "/",
                                "field": "package_name",
                            },
                        ],
                    )
                ]
            }
        }
    )
    assert len(renamed) == 1


def test_a_value_without_the_source_marker_is_not_a_composite_slot():
    """A plain resolved value leaves the marker question alone."""

    found = _composite_records(
        {
            "slot_value_presentations": {
                "records": [
                    _record(
                        components=[
                            {"kind": "FACT_VALUE", "text": "某公司", "field": "project_name"}
                        ]
                    )
                ]
            }
        }
    )
    assert found == []


def test_a_marker_without_a_resolved_value_is_not_a_composite_slot():
    """The marker alone is a preserved placeholder, not a composite delivery."""

    found = _composite_records(
        {
            "slot_value_presentations": {
                "records": [
                    _record(
                        components=[
                            {
                                "kind": "SOURCE_FORM_NOT_APPLICABLE_MARKER",
                                "text": "/",
                                "field": "lot_name",
                            }
                        ]
                    )
                ]
            }
        }
    )
    assert found == []


def test_the_four_underline_states_are_distinguishable():
    """Inherited, dropped and unauthorised are three different findings."""

    assert _underline_state(True, True) == "SLOT_DECORATION_INHERITED"
    assert _underline_state(True, False) == "SLOT_DECORATION_DROPPED"
    assert _underline_state(False, True) == "RUN_UNDERLINE_WITHOUT_SLOT_AUTHORITY"
    assert _underline_state(False, False) == "NO_SLOT_DECORATION_INTENT"
    assert len(
        {
            _underline_state(True, True),
            _underline_state(True, False),
            _underline_state(False, True),
            _underline_state(False, False),
        }
    ) == 4


@pytest.mark.skipif(
    not BUILD.exists() or not SOURCE_PDF.exists(),
    reason="the follow-up build and its source are not present",
)
def test_the_delivered_build_satisfies_the_structural_gate():
    """The gate passes on the artifact it was written for, defect by defect."""

    from v1_p21_structural_gate import evaluate

    report = evaluate(BUILD, SOURCE_PDF)
    assert report["status"] == "PASS", report["failed_checks"]
    measurements = report["measurements"]

    # DEFECT A: one composite slot, its rule accounted exactly once, its value
    # underlined on the page, and no underline leaking onto the prose.
    assert len(measurements["composite_slots"]) == 1
    slot = measurements["composite_slots"][0]
    assert slot["source_slot_underline_inherited"] is True
    assert slot["carrier_run_underline"] is True
    assert slot["marker_occurrences"] == {"/": 1}
    assert slot["marker_field_status"] == {"lot_name": "NOT_FOUND"}
    assert [rule["source_rule_id"] for rule in slot["bound_rules"]] == ["P60-R1"]
    assert slot["bound_rules"][0]["geometry_intent"] == "ANCHOR_START_ONLY"
    assert all(
        run["underline"] is False
        for run in slot["slot_neighbour_runs"]
        if run["text"].strip()
    )
    assert slot["rendered_rules_under_value"], "no rule reached the page"
    assert all(item["rule"] is not None for item in slot["rendered_rules_under_value"])

    # DEFECT B: the source's first-line indent, not a whole-paragraph left indent.
    assert measurements["classification_histogram"] == {
        "NO_SPECIAL_FIRST_LINE_INDENT": 57,
        "FIRST_LINE_INDENT": 20,
    }
    assert measurements["exempt_paragraph_reasons"] == [
        "CENTRED_LINE_POSITIONED_FROM_THE_CONTAINER_CENTRE",
        "PARAGRAPH_ORIGIN_MOVED_BY_AN_ANCHORED_SOURCE_VALUE",
    ]


@pytest.mark.skipif(
    not BUILD.exists() or not SOURCE_PDF.exists(),
    reason="the follow-up build and its source are not present",
)
def test_the_audited_page_carries_a_first_line_indent_per_paragraph():
    """Each numbered paragraph on the page is classified on its own rows."""

    from v1_p21_structural_gate import evaluate

    report = evaluate(BUILD, SOURCE_PDF)
    rows = {
        row["paragraph_index"]: row
        for row in report["measurements"]["audited_source_page_paragraphs"]
    }
    # The introduction and the three numbered paragraphs are separate paragraphs
    # with their own classifications; none of them inherits another's geometry.
    indices = sorted(
        index for index in rows if rows[index]["kind"] in ("LogicalParagraph", "List")
    )
    assert len(indices) >= 4, indices
    for index in indices:
        row = rows[index]
        assert row["classification"] in (
            "FIRST_LINE_INDENT",
            "HANGING_INDENT",
            "NO_SPECIAL_FIRST_LINE_INDENT",
        ), row
        if row.get("exempt_reason"):
            continue
        # The delivered first line sits on the source's own first row, and the
        # body boundary it returns to is a boundary the source's rows use.
        assert row["generated_first_line_x"] == pytest.approx(
            row["source_first_row_x"], abs=2.0
        )
        assert row["word_left_pt"] == pytest.approx(row["expected_left_pt"], abs=0.5)
        assert row["word_first_line_pt"] == pytest.approx(
            row["expected_first_line_pt"], abs=0.5
        )
    first_line = [index for index in indices if rows[index]["classification"] == "FIRST_LINE_INDENT"]
    assert first_line, "the page's first-line indents were not classified"
    for index in first_line:
        assert rows[index]["word_first_line_pt"] > 0


def test_a_gate_verdict_is_read_as_the_token_the_gate_uses():
    """Gates spell a pass differently; the status report must read all of them."""

    assert passed({"status": "PASS"}) is True
    assert passed({"status": "FAIL"}) is False
    assert passed({"status": "THREE_CASE_GENERALIZATION = PASS"}) is True
    assert passed({"result": "PASS"}) is True
    assert passed({"automated_result": "PASS"}) is True
    assert passed({"status": "V1_AUTOMATED_CANDIDATE", "failed_checks": []}) is True
    assert passed({"status": "V1_BLOCKED_PACKAGE_SAFETY", "failed_checks": ["x"]}) is False
    assert passed({}) is False
    assert status_of({"automated_result": "PASS"}) == "PASS"


def test_the_checklist_restates_the_gate_measurements_as_review_steps():
    """Every automated structural claim becomes one thing to look at in Word."""

    section = structural_review_points(
        {
            "gate": "v1_p21_structural",
            "measurements": {
                "composite_slots": [
                    {
                        "source_page": 60,
                        "generated_page": 21,
                        "generated_paragraph_index": 132,
                        "value": "某公司采购项目、/",
                        "marker_texts": ["/"],
                        "marker_occurrences": {"/": 1},
                        "separator_occurrences": {"、": 1},
                        "marker_field_status": {"lot_name": "NOT_FOUND"},
                        "bound_rules": [{"source_rule_id": "P60-R1"}],
                        "slot_neighbour_runs": [
                            {"text": "在", "underline": False},
                            {"text": "", "underline": False},
                        ],
                    }
                ],
                "audited_source_page_paragraphs": [
                    {
                        "paragraph_index": 132,
                        "classification": "FIRST_LINE_INDENT",
                        "word_left_pt": 1.2,
                        "word_first_line_pt": 27.6,
                        "source_first_row_x": 99.6,
                    },
                    {
                        "paragraph_index": 130,
                        "classification": "NO_SPECIAL_FIRST_LINE_INDENT",
                        "exempt_reason": "CENTRED_LINE_POSITIONED_FROM_THE_CONTAINER_CENTRE",
                    },
                ],
            },
        }
    )
    text = "\n".join(section)
    assert "1.5" in text
    # The marker is named as a marker and the field it belongs to stays open.
    assert "`/`" in text and "lot_name=NOT_FOUND" in text
    assert "`、`" in text, "the source separator was not described as its own component"
    assert "`在`" in text, "the neighbouring prose was not named"
    assert "段落 132" in text and "首行缩进" in text
    assert "不适用通用缩进契约" in text, "the centred exemption was not explained"
    # No case name, page number or value is invented by the checklist itself.
    assert "P60-R1" in text


def test_the_checklist_says_nothing_when_the_gate_measured_nothing():
    """An empty gate report produces no section rather than an empty claim."""

    assert structural_review_points({"measurements": {}}) == []
    assert structural_review_points({}) == []
