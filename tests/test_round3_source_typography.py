"""Round 3's source-typography mechanics, per defect family.

Each test here pins one mechanism a reported defect needed, at the level the
mechanism actually decides:

* the source's own alignment is what a paragraph's ``w:jc`` carries,
* a source blank the paragraph's own flow has passed is still painted, at the
  source's width,
* a cell keeps the source's own internal lines,
* the source's synthetic bold is read from how the glyph was drawn.

They are deliberately narrow: a full build is the acceptance evidence, and an
end-to-end test would only restate it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tender_basic.source_paragraph_alignment import (  # noqa: E402
    CLASSIFICATION_JUSTIFIED,
    CLASSIFICATION_LEFT,
    classify_source_paragraph_alignment,
)
from tender_basic.word_safe_source_builder import (  # noqa: E402
    flow_cursor_blank_representation,
)
from v1_source_typography_round3_gate import (  # noqa: E402
    _hard_break_fidelity,
    _is_subsequence,
    _literal_text,
    _split_pieces,
    _structural_deviation_evidence,
    _table_cell_line_structure,
    match_flow_placed_rule,
)


class _Character:
    """A character box as the alignment check reads it."""

    def __init__(self, x0: float, width: float = 12.0) -> None:
        self.bbox = (x0, 0.0, x0 + width, 12.0)


class _Span:
    def __init__(self, text: str, size: float, advance: float) -> None:
        self.text = text
        self.font_size = size
        self.characters = [
            _Character(index * advance) for index in range(len(text))
        ]


class _Line:
    def __init__(self, spans) -> None:
        self.spans = list(spans)


def _rows(first: str, second: str, *, advance: float):
    return [
        [_Line([_Span(first, 12.0, advance)])],
        [_Line([_Span(second, 12.0, advance)])],
    ]


# --------------------------------------------------------------------------- #
# D2 - the source's own alignment
# --------------------------------------------------------------------------- #


def test_source_rows_that_fill_the_measure_are_justified():
    """A row stretched past its natural advance is the source justifying it."""

    alignment = classify_source_paragraph_alignment(
        _rows("一二三四五六七八", "九十甲乙丙丁戊己", advance=13.0)
    )
    assert alignment.classification == CLASSIFICATION_JUSTIFIED
    assert alignment.justified is True
    assert alignment.alignment_hint == "justify"


def test_source_rows_at_their_natural_advance_are_left_aligned():
    """A row laid out at its own glyph advance was never stretched."""

    alignment = classify_source_paragraph_alignment(
        _rows("一二三四五六七八", "九十甲乙丙丁戊己", advance=12.0)
    )
    assert alignment.classification == CLASSIFICATION_LEFT
    assert alignment.justified is False
    assert alignment.alignment_hint == "left"


def test_a_single_row_carries_no_alignment_evidence():
    """One row looks the same either way, so it asks for nothing."""

    alignment = classify_source_paragraph_alignment(
        _rows("一二三四五六七八", "九十甲乙丙丁戊己", advance=13.0)[:1]
    )
    assert alignment.row_count == 1
    assert alignment.justified is False


# --------------------------------------------------------------------------- #
# D5 - the blank the paragraph's own flow has already passed
# --------------------------------------------------------------------------- #


def test_a_flowing_prose_paragraph_paints_its_blank_at_the_cursor():
    """A multi-row paragraph wraps by Word's rules, so the blank goes inline."""

    assert flow_cursor_blank_representation(False, 3) is True


def test_a_single_row_form_line_keeps_its_positioned_blank():
    """A one-row form line reaches its own rule with an anchor tab."""

    assert flow_cursor_blank_representation(False, 1) is False


def test_a_table_cell_keeps_its_own_line_structure():
    """A cell's lines are the source's, so its blanks are never lifted out."""

    assert flow_cursor_blank_representation(True, 4) is False


# --------------------------------------------------------------------------- #
# D3/D6 - the cell's own lines
# --------------------------------------------------------------------------- #


def _cell(rows, *, page=43):
    return {
        "source_page": page,
        "text": "\n".join(rows),
        "compact": "".join(rows),
        "row_count": len(rows),
        "row_texts": list(rows),
    }


def _delivered_cell(paragraphs, breaks=0, *, spelling="paragraph"):
    """A delivered cell in one of Word's two native spellings of a line break.

    Word expresses a line inside a cell either as a paragraph boundary
    (``spelling="paragraph"``, one paragraph per source line, no ``w:br``) or as
    a ``w:br`` inside one paragraph (``spelling="break"``, one paragraph that
    carries every source line).  Both are ordinary editable text in the same
    single cell; a real delivery uses one of them for a given boundary, never
    both.  The gate joins the cell's paragraphs with ``"\\n"``, so the two
    spellings arrive as the same row list and are told apart by their separator
    count, which is what these fixtures now model.
    """

    if spelling == "break":
        joined = "\n".join(paragraphs)
        return {
            "text": joined,
            "compact": "".join(paragraphs),
            "breaks": breaks,
            "paragraphs": [{"text": joined}],
            "style": "Table Text",
        }
    return {
        "text": "\n".join(paragraphs),
        "compact": "".join(paragraphs),
        "breaks": breaks,
        "paragraphs": [{"text": paragraph} for paragraph in paragraphs],
        "style": "Table Text",
    }


def test_a_cell_that_keeps_the_source_lines_passes():
    counts = _table_cell_line_structure(
        [_cell(["响应报价(元）", "（不含税）"])],
        [_delivered_cell(["响应报价(元）", "（不含税）"])],
    )
    assert counts == (1, [])


def test_the_same_cell_delivered_with_line_breaks_also_passes():
    counts = _table_cell_line_structure(
        [_cell(["响应报价(元）", "（不含税）"])],
        [_delivered_cell(["响应报价(元）", "（不含税）"], breaks=1, spelling="break")],
    )
    assert counts == (1, [])


def test_a_cell_that_spells_one_boundary_twice_is_refused():
    """Two native separators for one source boundary is not source fidelity.

    A boundary spelled both as a ``w:br`` and as a paragraph boundary would put
    a blank line between the source's own lines.  Counting only one spelling
    would let that through, so the check counts every native separator the cell
    carries.
    """

    doubled = _delivered_cell(["响应报价(元）", "（不含税）"], breaks=1)
    checked, failures = _table_cell_line_structure(
        [_cell(["响应报价(元）", "（不含税）"])], [doubled]
    )
    assert checked == 1
    assert len(failures) == 1
    assert failures[0]["delivered_breaks"] == 1
    assert failures[0]["delivered_paragraph_boundaries"] == 1
    assert failures[0]["delivered_line_separators"] == 2
    assert failures[0]["expected_line_separators"] == 1


def test_a_cell_that_merges_the_source_lines_fails():
    checked, failures = _table_cell_line_structure(
        [_cell(["响应报价(元）", "（不含税）"])],
        [_delivered_cell(["响应报价(元）（不含税）"], breaks=0)],
    )
    assert checked == 1
    assert len(failures) == 1
    assert failures[0]["expected_breaks"] == 1
    assert failures[0]["delivered_breaks"] == 0


def test_a_three_line_summary_cell_needs_two_breaks():
    rows = ["不含税合计（即响应报价）：", "其中：税率：", "总计（含税金额）："]
    counts = _table_cell_line_structure(
        [_cell(rows)], [_delivered_cell(rows, breaks=2, spelling="break")]
    )
    assert counts == (1, [])


# --------------------------------------------------------------------------- #
# D1 - one source element is one delivered paragraph
# --------------------------------------------------------------------------- #


def _element(text, rows=3, page=42, kind="LogicalParagraph"):
    return {
        "source_page": page,
        "text": text,
        "compact": "".join(text.split()),
        "row_count": rows,
        "kind": kind,
    }


def _paragraph(
    text, index=0, breaks=0, style=None, space_before_pt=0.0, space_after_pt=0.0
):
    return {
        "text": text,
        "compact": "".join(text.split()),
        "breaks": breaks,
        "index": index,
        "style": style,
        "space_before_pt": space_before_pt,
        "space_after_pt": space_after_pt,
        "runs": [{"text": text, "bold": False, "underline": None}],
    }


def test_an_element_delivered_as_one_paragraph_passes():
    letter = "我方已充分研究了询比文件的全部内容，愿意以人民币（大写）元的响应报价。"
    counts, failures = _hard_break_fidelity(
        [_element(letter)], [_paragraph(letter)], ()
    )
    assert counts["checked"] == 1
    assert failures == []


def test_an_element_split_across_paragraphs_fails():
    letter = "我方已充分研究了询比文件的全部内容，愿意以人民币（大写）元的响应报价。"
    head = "我方已充分研究了询比文件的全部内容，愿意"
    tail = "以人民币（大写）元的响应报价。"
    counts, failures = _hard_break_fidelity(
        [_element(letter)],
        [_paragraph(head, index=0), _paragraph(tail, index=1)],
        (),
        {},
        [],
    )
    assert counts["checked"] == 1
    assert [failure["kind"] for failure in failures] == [
        "SOURCE_ELEMENT_SPLIT_ACROSS_PARAGRAPHS"
    ]
    assert failures[0]["delivered_paragraphs"] == 2


def test_a_recorded_isolation_does_not_authorise_a_natural_wrap_split():
    """A recorded isolation is evidence about the build, not a verdict.

    The build may state that the resolved value's reflow forced a row onto its
    own paragraph, and that statement is still not a licence: the source printed
    this letter as one logical paragraph of wrapped visual rows, so a delivered
    paragraph boundary inside it is an invented break.  The gate reports the
    classification and every reader-visible fact instead of passing it.
    """

    letter = "我方已充分研究了询比文件的全部内容，愿意以人民币（大写）元的响应报价。"
    head = "我方已充分研究了询比文件的全部内容，愿意"
    tail = "以人民币（大写）元的响应报价。"
    counts, failures = _hard_break_fidelity(
        [_element(letter, rows=3)],
        [_paragraph(head, index=0), _paragraph(tail, index=1)],
        (),
        {
            1: {
                "reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW",
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
            }
        },
        [],
    )
    assert counts["authorized_splits"] == 0
    assert counts["split_classifications"] == {"NATURAL_WRAP": 1}
    assert [failure["kind"] for failure in failures] == [
        "SOURCE_ELEMENT_SPLIT_ACROSS_PARAGRAPHS"
    ]
    failure = failures[0]
    assert failure["classification"] == "NATURAL_WRAP"
    assert failure["source_semantics"] == "NATURAL_WRAP"
    assert failure["generated_representation"] == "PARAGRAPH_BOUNDARY"
    assert failure["container_fidelity"] == "SOURCE_CONTAINER_MISMATCH"
    assert failure["deviation_state"] == "NONE"
    assert failure["unexplained_structural_split"] is True
    assert failure["same_word_paragraph"] is False
    assert failure["w_br_between_tokens"] == 0
    assert failure["w_cr_between_tokens"] == 0
    assert failure["empty_paragraph_between_tokens"] == 0
    assert failure["authorised_structural_split_between_tokens"] is False
    assert failure["recorded_isolation_reason"] == (
        "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"
    )
    # The source semantics may never be rewritten just to make a gate green.
    assert failure["classification"] != "SOURCE_EXPLICIT_BREAK"


def test_a_source_list_its_own_items_split_is_authorised():
    """The source's own structure still authorises a split: a list element's
    items are separate source rows, so the boundary is the source's own.
    """

    items = "第一条的要求第二条的要求"
    counts, failures = _hard_break_fidelity(
        [_element(items, rows=2, kind="List")],
        [_paragraph("第一条的要求", index=0), _paragraph("第二条的要求", index=1)],
        (),
        {1: {"reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"}},
    )
    assert failures == []
    assert counts["authorized_splits"] == 1
    assert counts["split_classifications"] == {"SOURCE_EXPLICIT_BREAK": 1}


def test_a_single_source_row_split_is_a_builder_forced_break():
    """An element the source printed as one visual row has no internal boundary
    at all, so a delivered boundary there is the builder's own.
    """

    line = "我方已充分研究了询比文件的全部内容，愿意以人民币（大写）元"
    head = "我方已充分研究了询比文件的全部内容，"
    tail = "愿意以人民币（大写）元"
    counts, failures = _hard_break_fidelity(
        [_element(line, rows=1)],
        [_paragraph(head, index=0), _paragraph(tail, index=1)],
        (),
        {1: {"reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"}},
        [],
    )
    assert counts["split_classifications"] == {"BUILDER_FORCED_BREAK": 1}
    assert [failure["classification"] for failure in failures] == [
        "BUILDER_FORCED_BREAK"
    ]


def test_a_split_with_an_invented_hard_break_inside_it_still_fails():
    letter = "我方已充分研究了询比文件的全部内容，愿意以人民币（大写）元的响应报价。"
    head = "我方已充分研究了询比文件的全部内容，愿意"
    tail = "以人民币（大写）元的响应报价。"
    _, failures = _hard_break_fidelity(
        [_element(letter)],
        [_paragraph(head, index=0), _paragraph(tail, index=1, breaks=1)],
        (),
        {1: {"reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"}},
        [],
    )
    assert [failure["kind"] for failure in failures] == [
        "BUILDER_HARD_BREAK_INSIDE_ELEMENT"
    ]


def test_a_split_that_leaves_a_visible_gap_fails():
    letter = "我方已充分研究了询比文件的全部内容，愿意以人民币（大写）元的响应报价。"
    head = "我方已充分研究了询比文件的全部内容，愿意"
    tail = "以人民币（大写）元的响应报价。"
    _, failures = _hard_break_fidelity(
        [_element(letter)],
        [
            _paragraph(head, index=0),
            _paragraph("", index=1),
            _paragraph(tail, index=2),
        ],
        (),
        {2: {"reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"}},
        [],
    )
    assert [failure["kind"] for failure in failures] == [
        "SPLIT_INTRODUCES_VISIBLE_GAP"
    ]


def test_a_split_that_carries_paragraph_spacing_fails():
    letter = "我方已充分研究了询比文件的全部内容，愿意以人民币（大写）元的响应报价。"
    head = "我方已充分研究了询比文件的全部内容，愿意"
    tail = "以人民币（大写）元的响应报价。"
    _, failures = _hard_break_fidelity(
        [_element(letter)],
        [
            _paragraph(head, index=0),
            _paragraph(tail, index=1, space_before_pt=6.0),
        ],
        (),
        {1: {"reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"}},
        [],
    )
    assert [failure["kind"] for failure in failures] == [
        "SPLIT_INTRODUCES_PARAGRAPH_SPACING"
    ]


def test_a_value_the_source_never_printed_is_not_part_of_its_line():
    """A filled slot's characters come from the facts, not from the source."""

    source = "我方已充分研究了询比文件的全部内容"
    delivered = "我方已充分研究了某项目部一体化泵站采购项目询比文件的全部内容"
    value = "某项目部一体化泵站采购项目"
    assert _literal_text("".join(delivered.split()), (value,)) == "".join(
        source.split()
    )


def test_split_pieces_reads_the_runs_characters_in_order():
    key = "我方已充分研究了询比文件的全部内容"
    assert _is_subsequence("我方已充分研究", key) is True
    assert _is_subsequence("研究充分我方", key) is False
    delivered = [
        _paragraph("我方已充分研究了"),
        _paragraph("询比文件的全部内容"),
    ]
    pieces = _split_pieces(key, delivered, ())
    assert len(pieces) == 2
    assert sum(len(piece["literal"]) for piece in pieces) == len(key)


def test_a_repeated_paragraph_is_not_a_split():
    """A paragraph that repeats the element's words is not the element split."""

    key = "本项目询比有效期"
    delivered = [_paragraph("本项目询比有效期"), _paragraph("其他内容")]
    pieces = _split_pieces(key, delivered, ())
    assert len(pieces) == 1


def test_a_flow_placed_rule_keeps_its_anchored_endpoint():
    """Only one endpoint can be held once the flow owns the rule's start."""

    painted = [{"x0": 238.8, "x1": 323.9, "y": 209.8}]
    best = match_flow_placed_rule((169.65, 323.6), painted)
    assert best["anchored_endpoint"] == "END"
    assert best["anchored_deviation_pt"] == pytest.approx(0.3)
    assert best["start_deviation_pt"] == pytest.approx(69.15)


def test_a_flow_placed_rule_prefers_the_endpoint_it_can_hold():
    """A rule the flow moved is matched by whichever endpoint still lands."""

    painted = [{"x0": 385.6, "x1": 463.0, "y": 209.5}]
    best = match_flow_placed_rule((384.6, 459.0), painted)
    assert best["anchored_endpoint"] == "START"
    assert best["anchored_deviation_pt"] == pytest.approx(1.0)


def test_a_segment_of_the_wrong_width_cannot_claim_the_rule():
    """A short underline on the same line is not the source rule."""

    painted = [{"x0": 150.4, "x1": 156.4, "y": 251.7}]
    assert match_flow_placed_rule((95.25, 151.05), painted) is None


def test_no_painted_rule_leaves_the_flow_placed_rule_unanswered():
    assert match_flow_placed_rule((95.25, 151.05), []) is None


# --------------------------------------------------------------------------- #
# D2 - a reviewed structural deviation is disclosed, never called fidelity
# --------------------------------------------------------------------------- #
#
# The deviation is a *generic* contract: nothing below - or in production code -
# keys acceptance on a case name, a page number, a rule id, a build id or a
# literal.  The fixtures use the repository's own recorded decision because the
# point of these tests is that the *artifact* decides, not the check.


def _signed_deviation_artifact(**overrides):
    """An admissible deviation artifact, straight from the repository's evidence.

    A test that wants to prove "this passes only because the signed artifact says
    so" reads the shipped artifact rather than a hand-written stand-in.  Overrides
    mutate a copy, so a missing condition can be asserted without editing disk.
    """

    artifacts = _structural_deviation_evidence()
    assert artifacts, "the repository must ship its signed deviation evidence"
    artifact = json.loads(json.dumps(artifacts[0]))
    for key, value in overrides.items():
        cursor = artifact
        *parents, leaf = key.split(".")
        for parent in parents:
            cursor = cursor[parent]
        cursor[leaf] = value
    return artifact


def test_the_shipped_evidence_artifact_is_self_consistent():
    """The artifact's own claim is re-derived, never trusted."""

    artifact = _signed_deviation_artifact()
    assert artifact["schema"].startswith("structural_deviation_evidence/")
    assert artifact["source"]["break_semantics"] == "NATURAL_WRAP"
    assert artifact["generated"]["representation"] == "PARAGRAPH_BOUNDARY"
    assert artifact["generated"]["same_word_paragraph"] is False
    assert artifact["deviation"]["state"] == "REVIEWED_ACCEPTED"
    assert artifact["review"]["state"] == "ACCEPTED_BY_PROJECT_POLICY"
    assert artifact["review"]["authority"] == "PROJECT_POLICY"
    assert artifact["review"]["accepted_by_automation"] is False
    assert artifact["review"]["open_review_item"]
    assert artifact["review"]["reviewed_by"] and artifact["review"]["reviewed_at"]
    assert artifact["predecessor_geometry_contract"]["tolerance_pt"] == "2.0"
    assert artifact["predecessor_geometry_contract"]["rebaselined"] is False
    assert artifact["predecessor_geometry_contract"]["tolerance_weakened"] is False
    assert artifact["same_word_paragraph_experiment"]["outcome"] == (
        "SAME_WORD_PARAGRAPH_UNAVAILABLE"
    )
    assert artifact["same_word_paragraph_experiment"]["geometry_rule_ids_failed"]
    assert artifact["same_word_paragraph_experiment"][
        "frozen_geometry_gate_outcome"
    ] == "FAIL"
    assert artifact["same_word_paragraph_experiment"][
        "permitted_native_constructs_exhausted"
    ] is True


def _split_letter():
    letter = "我方已充分研究了询比文件的全部内容，愿意以人民币（大写）元的响应报价。"
    head = "我方已充分研究了询比文件的全部内容，愿意"
    tail = "以人民币（大写）元的响应报价。"
    return letter, head, tail


def _split_call(artifacts, **element_overrides):
    letter, head, tail = _split_letter()
    return _hard_break_fidelity(
        [_element(letter, rows=3, **element_overrides)],
        [_paragraph(head, index=0), _paragraph(tail, index=1)],
        (),
        {
            1: {
                "reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW",
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
            }
        },
        artifacts,
    )


def test_a_wrap_the_container_cannot_merge_passes_with_a_reviewed_deviation():
    counts, failures = _split_call([_signed_deviation_artifact()])
    assert failures == []
    assert counts["reviewed_deviations"]
    assert counts["accounting"]["unexplained_structural_splits"] == 0
    assert counts["accounting"]["reviewed_structural_deviations"] == 1
    reviewed = counts["reviewed_deviations"][0]
    # The source semantics and the generated representation stay separate facts.
    assert reviewed["source_semantics"] == "NATURAL_WRAP"
    assert reviewed["generated_representation"] == "PARAGRAPH_BOUNDARY"
    assert reviewed["container_fidelity"] == "SOURCE_CONTAINER_MISMATCH"
    assert reviewed["fidelity_difference"] == "CONTAINER_IDENTITY"
    assert reviewed["deviation_kind"] == (
        "STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY"
    )
    assert reviewed["deviation_state"] == "REVIEWED_ACCEPTED"
    # It is a disclosed difference, never fidelity.
    assert reviewed["same_word_paragraph"] is False
    assert reviewed["container_fidelity"] != "SOURCE_CONTAINER_MATCH"
    assert counts["split_classifications"] == {"NATURAL_WRAP": 1}
    assert counts["authorized_splits"] == 0


@pytest.mark.parametrize(
    "override",
    [
        {"deviation.state": "NONE"},
        {"deviation.kind": "SOMETHING_ELSE"},
        {"source.break_semantics": "SOURCE_EXPLICIT_BREAK"},
        {"generated.representation": "SAME_PARAGRAPH"},
        {"generated.same_word_paragraph": True},
        {"review.state": "ACCEPTED_BY_AUTOMATION"},
        {"review.authority": "AUTOMATION"},
        {"review.accepted_by_automation": True},
        {"review.reviewed_by": ""},
        {"review.reviewed_at": ""},
        {"review.open_review_item": ""},
        {"same_word_paragraph_experiment.outcome": "AVAILABLE"},
        {"same_word_paragraph_experiment.geometry_rule_ids_failed": []},
        {"same_word_paragraph_experiment.frozen_geometry_gate_outcome": "PASS"},
        {
            "same_word_paragraph_experiment.permitted_native_constructs_exhausted": False
        },
        {"predecessor_geometry_contract.rebaselined": True},
        {"predecessor_geometry_contract.tolerance_pt": "3.0"},
        {"predecessor_geometry_contract.contract_sha256": "0" * 64},
        {"contract_rules_cleared": True},
    ],
)
def test_any_missing_deviation_condition_leaves_the_split_a_failure(override):
    artifact = _signed_deviation_artifact()
    if override.pop("contract_rules_cleared", False):
        artifact["predecessor_geometry_contract"]["rules"] = []
    else:
        for key, value in override.items():
            cursor = artifact
            *parents, leaf = key.split(".")
            for parent in parents:
                cursor = cursor[parent]
            cursor[leaf] = value
    counts, failures = _split_call([artifact])
    assert counts["reviewed_deviations"] == []
    assert counts["accounting"]["unexplained_structural_splits"] == 1
    assert [failure["kind"] for failure in failures] == [
        "SOURCE_ELEMENT_SPLIT_ACROSS_PARAGRAPHS"
    ]
    assert failures[0]["unexplained_structural_split"] is True
    assert failures[0]["reviewed_structural_deviation"] is False
    assert failures[0]["deviation_missing_conditions"]


def test_the_deviation_contract_is_not_keyed_to_a_case_page_or_rule():
    """The same boundary passes or fails purely on its evidence.

    The artifact carries a CASE001 rule id and a concrete page; if the check keyed
    on either, a boundary on another page or another rule could never be admitted.
    Rewriting both to different values must change nothing.
    """

    baseline_counts, _ = _split_call([_signed_deviation_artifact()])
    assert baseline_counts["reviewed_deviations"]

    other = _signed_deviation_artifact()
    other["same_word_paragraph_experiment"]["geometry_rule_ids_failed"] = ["R-OTHER-1"]
    other["predecessor_geometry_contract"]["rules"] = [
        {
            "source_rule_id": "R-OTHER-1",
            "transformation_policy": "OTHER_POLICY",
            "geometry_intent": "EXACT_SOURCE_SPAN",
            "source_x0": 1.0,
            "source_x1": 2.0,
            "source_y": 3.0,
        }
    ]
    from v1_source_typography_round3_gate import _contract_rules_digest

    other["predecessor_geometry_contract"]["contract_sha256"] = _contract_rules_digest(
        other["predecessor_geometry_contract"]["rules"]
    )
    counts, failures = _split_call([other])
    assert failures == []
    assert counts["reviewed_deviations"]
    assert counts["reviewed_deviations"][0]["deviation_kind"] == (
        "STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY"
    )


def test_the_deviation_is_not_keyed_to_this_page_or_element():
    """A different page and a different element's text are equally admissible."""

    other = _signed_deviation_artifact()
    letter, head, tail = _split_letter()
    counts, failures = _hard_break_fidelity(
        [_element(letter, rows=3, page=7)],
        [_paragraph(head, index=0), _paragraph(tail, index=1)],
        (),
        {
            1: {
                "reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW",
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
            }
        },
        [other],
    )
    assert failures == []
    assert counts["reviewed_deviations"][0]["source_page"] == 7


def test_the_source_semantics_are_never_relabelled_as_an_explicit_break():
    counts, failures = _split_call([_signed_deviation_artifact()])
    assert failures == []
    reviewed = counts["reviewed_deviations"][0]
    assert reviewed["classification"] == "NATURAL_WRAP"
    assert reviewed["source_semantics"] == "NATURAL_WRAP"
    assert counts["accounting"]["source_explicit_breaks"] == 0
    assert counts["split_classifications"] != {"SOURCE_EXPLICIT_BREAK": 1}


def test_the_deviation_counters_stay_separate():
    """One counter per observable fact; none of them is `PASS`."""

    counts, failures = _split_call([_signed_deviation_artifact()])
    assert failures == []
    accounting = counts["accounting"]
    assert accounting["source_natural_wrap_boundaries"] == 1
    assert accounting["generated_paragraph_boundaries"] == 1
    assert accounting["reviewed_structural_deviations"] == 1
    assert accounting["unexplained_structural_splits"] == 0
    assert accounting["builder_forced_breaks"] == 0
    assert accounting["source_explicit_breaks"] == 0


def test_an_unexplained_split_is_disclosed_rather_than_tolerated():
    """A `w:br` inside the boundary is reported even when the deviation is admitted."""

    letter, head, tail = _split_letter()
    counts, failures = _hard_break_fidelity(
        [_element(letter, rows=3)],
        [_paragraph(head, index=0), _paragraph(tail, index=1, breaks=1)],
        (),
        {1: {"reason": "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"}},
        [_signed_deviation_artifact()],
    )
    assert [failure["kind"] for failure in failures] == [
        "BUILDER_HARD_BREAK_INSIDE_ELEMENT"
    ]
    assert counts["reviewed_deviations"] == []
    assert counts["accounting"]["reviewed_structural_deviations"] == 0


def test_a_hard_break_the_source_rows_do_not_explain_is_disclosed():
    """`unexpected_w_br_count` and the disclosure list are both reader-visible.

    The source element has two rows, so one break is its own row separation; the
    second break produces a line the source's rows never accounted for, and it is
    counted and listed rather than tolerated.
    """

    letter = "第一条的要求第二条的要求"
    counts, failures = _hard_break_fidelity(
        [_element(letter, rows=2, kind="List")],
        [_paragraph(letter, index=0, breaks=2)],
        (),
        {},
        [],
    )
    assert failures == []
    assert counts["accounting"]["generated_w_br"] == 2
    assert counts["accounting"]["unexpected_w_br_count"] == 1
    assert [item["generated_paragraph_index"] for item in counts["hard_break_disclosure"]] == [0]


def test_a_hard_break_the_source_rows_do_expect_is_not_disclosed():
    """A list's own row separation is the source's break, not the builder's.

    A source element of ``n`` rows needs exactly ``n - 1`` breaks to be delivered
    as one paragraph, so those breaks are the source's own layout - and nothing is
    disclosed.
    """

    letter = "第一条的要求第二条的要求第三条的要求"
    counts, failures = _hard_break_fidelity(
        [_element(letter, rows=3, kind="List")],
        [_paragraph(letter, index=0, breaks=2)],
        (),
        {},
        [],
    )
    assert failures == []
    assert counts["accounting"]["generated_w_br"] == 2
    assert counts["accounting"]["unexpected_w_br_count"] == 0
    assert counts["hard_break_disclosure"] == []
