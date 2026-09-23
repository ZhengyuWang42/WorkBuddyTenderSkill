"""Round-4 continuation VII focused tests.

Three repairs are pinned here, each at the mechanism rather than at one page:

* the *leading* blank of a date row is intrinsic geometry - it has a measured
  source interval even though no label precedes it, and that interval is what
  owns its width (never a figure-space glyph count);
* the intrinsic spacer's measured calibration (one space advances half an em,
  tracking responds one-for-one, condensed tracking is not applied by the
  renderer) is what a source width is converted with, so an emitted chain
  reconstructs the source row;
* a table cell that the source drew as several lines is emitted as one native
  paragraph per line, each with its own measured pitch - which is the only
  representation in which two *different* source pitches can both be delivered.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx import Document
from docx.oxml.ns import qn

from tender_basic import intrinsic_spacer as spacer
from tender_basic.geometry_rule_qa import MANDATORY_TOLERANCE_PT
from tender_basic.source_vertical_rhythm import (
    MEASURED_NATURAL_LINE_RATIO,
    auto_line_multiple_for_pitch,
    dominant_line_pitch,
    emitted_font_size_pt,
)
from tender_basic.word_safe_source_builder import (
    ParagraphFormRenderer,
    WordSafeSourceDocumentBuilder,
)

ROOT = Path(__file__).resolve().parents[1]

#: The frozen vertical-rhythm tolerance (source_vertical_rhythm.py).
PITCH_TOLERANCE_PT = 1.0

#: The frozen horizontal/geometry tolerance (geometry_rule_qa.py).
GEOMETRY_TOLERANCE_PT = 2.0


class _Box:
    """A source span or blank with the only attribute the model reads."""

    def __init__(self, x0: float, x1: float, y0: float = 0.0, y1: float = 10.0):
        self.source_x0 = x0
        self.source_x1 = x1
        self.bbox = (x0, y0, x1, y1)


class _Item:
    def __init__(self, x1: float):
        self.bbox = (0.0, 0.0, x1, 10.0)


class _Row:
    def __init__(self, label_x, parts, blanks, item_x1):
        self.label_x = label_x
        self.parts = parts
        self.blanks = blanks
        self.item = _Item(item_x1)


class _Run:
    def __init__(self, text: str, x0: float, y0: float, x1: float = 0.0):
        self.text = text
        self.bbox = (x0, y0, x1 or x0 + 10.0, y0 + 10.0)
        self.font_size = 10.45
        self.font_name = "FangSong"
        self.bold = False
        self.underline = False


class _Slot:
    """A fill slot with the two offsets and the copy hook the split uses."""

    def __init__(self, start: int, end: int):
        self.text_start = start
        self.text_end = end
        self.updated = None

    def model_copy(self, update=None):
        clone = _Slot(self.text_start, self.text_end)
        clone.updated = dict(update or {})
        if update:
            clone.text_start = update.get("text_start", clone.text_start)
            clone.text_end = update.get("text_end", clone.text_end)
        return clone


def _builder():
    """Uninitialised builders: every method under test is self-contained."""

    return ParagraphFormRenderer.__new__(ParagraphFormRenderer)


def _cell_builder():
    return WordSafeSourceDocumentBuilder.__new__(WordSafeSourceDocumentBuilder)


# --------------------------------------------------------------------------
# The intrinsic spacer's measured calibration
# --------------------------------------------------------------------------


def test_measured_space_advance_is_one_half_em() -> None:
    assert spacer.MEASURED_SPACE_ADVANCE_EM == 0.5
    assert spacer.MIN_INTRINSIC_WIDTH_FACTOR == pytest.approx(0.5)


def test_measured_tracking_responds_one_for_one_and_never_condenses() -> None:
    assert spacer.TRACKING_RESPONSE_RATIO == 1.0
    assert spacer.NEGATIVE_TRACKING_ROUNDS is False
    calibration = spacer.calibration_for("FangSong")
    # A target below one space is reported at the floor, never squeezed.
    assert calibration.tracking_pt(3.0, 12.0) == 0.0
    assert calibration.representable(3.0, 12.0) is False


def test_intrinsic_spacer_renders_the_target_width_at_both_date_sizes() -> None:
    for size, target in ((12.0, 6.00), (12.0, 21.96), (12.0, 40.30), (11.5, 69.00)):
        twips, rendered = spacer.intrinsic_spacer_widths(target, "FangSong", size)
        assert isinstance(twips, int)
        assert rendered == pytest.approx(target, abs=0.05)


def test_intrinsic_spacer_floor_is_the_base_space_advance() -> None:
    assert spacer.spacer_floor_pt("FangSong", 12.0) == pytest.approx(6.0)
    assert spacer.spacer_floor_pt("仿宋", 11.5) == pytest.approx(5.75)


def test_a_chain_of_intrinsic_spacers_reconstructs_its_source_width() -> None:
    target = 12.00 + 21.96 + 45.98
    rendered = sum(
        spacer.intrinsic_spacer_widths(part, "FangSong", 12.0)[1]
        for part in (12.00, 21.96, 45.98)
    )
    assert abs(rendered - target) <= 0.5


def test_calibration_is_keyed_by_family_and_falls_back_measurably() -> None:
    for family in ("FangSong", "仿宋"):
        calibration = spacer.calibration_for(family)
        assert calibration.space_advance_em == spacer.MEASURED_SPACE_ADVANCE_EM
        assert calibration.tracking_response_ratio == spacer.TRACKING_RESPONSE_RATIO
        assert calibration is not spacer.DEFAULT_CALIBRATION
    fallback = spacer.calibration_for("NoSuchFamily")
    assert fallback is spacer.DEFAULT_CALIBRATION
    assert fallback.space_advance_em == spacer.MEASURED_SPACE_ADVANCE_EM


def test_drift_in_a_target_width_changes_the_emitted_tracking() -> None:
    exact, _ = spacer.intrinsic_spacer_widths(21.96, "FangSong", 12.0)
    drifted, _ = spacer.intrinsic_spacer_widths(22.96, "FangSong", 12.0)
    assert exact != drifted
    assert drifted - exact == pytest.approx(20, abs=1)


def test_apply_spacing_places_one_schema_ordered_w_spacing() -> None:
    document = Document()
    run = document.add_paragraph().add_run(" ")
    run.font.size = 12.0
    run.underline = True
    spacer.apply_spacing(run, 319)
    rpr = run._r.find(qn("w:rPr"))
    spacings = rpr.findall(qn("w:spacing"))
    assert len(spacings) == 1
    assert spacings[0].get(qn("w:val")) == "319"
    # ``w:spacing`` precedes the elements the schema puts after it, so Word is
    # entitled to accept the part.
    order = [child.tag.split("}")[-1] for child in rpr]
    assert order.index("spacing") < order.index("u")
    assert order.index("spacing") < order.index("sz")
    # The spacer is one ordinary space whose width is intrinsic to the run.
    assert run.text == " "


# --------------------------------------------------------------------------
# The leading date interval is geometry
# --------------------------------------------------------------------------


def test_leading_blank_interval_is_measured_from_the_blank_itself() -> None:
    builder = _builder()
    # ``_date_token_boxes`` returns one ``(x0, x1)`` pair per printed token.
    builder._date_token_boxes = lambda row: [(283.20, 296.70)]
    row = _Row(283.20, ["", "年"], [_Box(214.20, 283.20)], 404.02)
    gap, next_x0 = builder._source_date_gap(row, 0, row.blanks[0])
    assert gap == pytest.approx(69.00)
    assert next_x0 == pytest.approx(283.20)


def test_leading_interval_falls_back_to_the_row_extent_without_a_blank_span() -> None:
    builder = _builder()
    builder._date_token_boxes = lambda row: [(100.0, 110.0)]
    row = _Row(100.0, ["", "年"], [type("B", (), {"source_x0": None})()], 200.0)
    # The row extent starts where the first token starts, so the interval is
    # empty and is dropped rather than emitted as a zero-width spacer.
    assert builder._source_date_gap(row, 0, row.blanks[0]) is None


def test_a_labelled_row_reaches_its_first_blank_from_the_label() -> None:
    builder = _builder()
    boxes = [
        (200.00, 260.00),
        (300.00, 313.50),
        (340.00, 353.50),
        (380.00, 393.50),
    ]
    builder._date_token_boxes = lambda row: boxes
    row = _Row(
        200.00,
        ["签署日期：", "", "年", "", "月", "", "日"],
        [_Box(260.0, 300.0), _Box(313.5, 340.0), _Box(353.5, 380.0)],
        393.50,
    )
    gap, next_x0 = builder._source_date_gap(row, 1, row.blanks[0])
    assert gap == pytest.approx(40.00)
    assert next_x0 == pytest.approx(300.00)


def test_leading_date_interval_x0_prefers_the_blank_own_start() -> None:
    builder = _builder()
    row = _Row(283.20, ["", "年"], [_Box(214.20, 283.20)], 404.02)
    assert builder._leading_date_interval_x0(row, row.blanks[0]) == pytest.approx(214.20)
    # Without a blank span the interval still has a defined start: the row's own
    # extent, which is the label when no blank reaches further left.
    assert builder._leading_date_interval_x0(row, None) == pytest.approx(214.20)
    bare = _Row(283.20, ["", "年"], [type("B", (), {"source_x0": None})()], 404.02)
    assert builder._leading_date_interval_x0(bare, None) == pytest.approx(283.20)


def test_sub_materiality_segments_are_not_emitted() -> None:
    assert ParagraphFormRenderer.MIN_MATERIAL_SEGMENT_PT == 0.5
    # A zero-width segment is below the floor, so no spacer run is created for
    # it: zero-width geometry never becomes a physical space.
    assert 0.0 < ParagraphFormRenderer.MIN_MATERIAL_SEGMENT_PT


# --------------------------------------------------------------------------
# CENTER alignment: unchanged
# --------------------------------------------------------------------------


def _insets(row_x0: float, row_x1: float) -> dict:
    builder = _builder()
    row = _Row(row_x0, ["年", "月", "日"], [_Box(row_x0, row_x0)], row_x1)
    for x in (row_x0, row_x1):
        row.blanks.append(_Box(x, x))
    return builder._source_center_frame_insets(row, 92.25, 503.05)


def test_center_axis_formula_is_unchanged_for_a_right_of_center_row() -> None:
    insets = _insets(214.20, 404.02)
    delta = insets["center_axis_delta"]
    assert delta > 0.5
    assert insets["left_inset_pt"] - insets["right_inset_pt"] == pytest.approx(
        2.0 * delta, abs=0.01
    )
    assert insets["right_inset_pt"] == 0.0
    assert insets["kind"] == "SOURCE_CENTER_ALIGNMENT_FRAME"


def test_center_axis_formula_is_unchanged_for_a_left_of_center_row() -> None:
    insets = _insets(120.00, 300.00)
    assert insets["center_axis_delta"] < -0.5
    assert insets["left_inset_pt"] == 0.0
    assert insets["right_inset_pt"] == pytest.approx(
        -2.0 * insets["center_axis_delta"], abs=0.01
    )


def test_center_axis_below_half_a_point_stays_symmetric() -> None:
    insets = _insets(200.00, 395.00)
    assert abs(insets["center_axis_delta"]) < 0.5
    assert insets["left_inset_pt"] == 0.0
    assert insets["right_inset_pt"] == 0.0


def test_date_row_geometry_tolerance_is_still_two_points() -> None:
    assert MANDATORY_TOLERANCE_PT == 2.0
    assert GEOMETRY_TOLERANCE_PT == MANDATORY_TOLERANCE_PT


# --------------------------------------------------------------------------
# A table cell's own multi-line rhythm
# --------------------------------------------------------------------------


def test_emitted_font_size_is_a_truncated_half_point_count() -> None:
    assert emitted_font_size_pt(10.45) == 10.0
    assert emitted_font_size_pt(10.75) == 10.5
    assert emitted_font_size_pt(11.25) == 11.0
    assert emitted_font_size_pt(11.5) == 11.5
    assert emitted_font_size_pt(0.0) == 0.0


def test_measured_natural_line_ratio_is_an_em_ratio() -> None:
    assert 1.0 < MEASURED_NATURAL_LINE_RATIO < 2.0
    assert MEASURED_NATURAL_LINE_RATIO * 10.0 == pytest.approx(14.076, abs=0.01)


def test_auto_line_multiple_reproduces_each_measured_pitch() -> None:
    for pitch in (23.40, 19.44, 40.30):
        multiple = auto_line_multiple_for_pitch(10.45, pitch)
        rendered = multiple * MEASURED_NATURAL_LINE_RATIO * emitted_font_size_pt(10.45)
        assert multiple is not None
        assert rendered == pytest.approx(pitch, abs=PITCH_TOLERANCE_PT)


def test_no_single_line_spacing_can_deliver_two_different_source_pitches() -> None:
    """Uniform rhythm cannot pass: the defect this representation removes."""

    first, second = 23.40, 19.44
    assert abs(first - second) > 2.0 * PITCH_TOLERANCE_PT
    single = MEASURED_NATURAL_LINE_RATIO * emitted_font_size_pt(10.45)
    shared = [
        units / 240.0
        for units in range(240, 720)
        if abs(units / 240.0 * single - first) <= PITCH_TOLERANCE_PT
        and abs(units / 240.0 * single - second) <= PITCH_TOLERANCE_PT
    ]
    assert shared == []


def test_auto_line_multiple_never_compresses_below_single_spacing() -> None:
    assert auto_line_multiple_for_pitch(10.5, 5.0) == 1.0
    assert auto_line_multiple_for_pitch(10.5, 0.0) is None
    assert auto_line_multiple_for_pitch(10.5, None) is None


def test_dominant_line_pitch_is_the_mode_not_the_mean() -> None:
    assert dominant_line_pitch([23.4, 19.44, 23.4, 23.4]) == 23.4
    assert dominant_line_pitch([]) == 0.0


def test_cell_splits_into_one_group_per_source_line_with_its_own_pitch() -> None:
    builder = _cell_builder()
    cell = type(
        "C",
        (),
        {
            "runs": [
                _Run("不含税合计（即响应报价）：", 118.80, 561.79),
                _Run("（大写），", 350.64, 561.79),
                _Run("元（小写）", 456.00, 561.79),
                _Run("其中：税率：", 118.80, 585.19),
                _Run("总计（含税金额）：", 118.80, 604.63),
            ],
            "text": "a\nb\nc",
        },
    )()
    text = "不含税合计（即响应报价）： （大写）， 元（小写）\n其中：税率：\n总计（含税金额）："
    groups = builder._cell_line_groups(cell, text, [])
    assert groups is not None
    assert len(groups) == 3
    pitches = [group[3] for group in groups]
    assert pitches[0] == pytest.approx(23.40, abs=0.01)
    assert pitches[1] == pytest.approx(19.44, abs=0.01)
    # The last line has no next line, so it states no pitch and keeps the
    # semantic single-line default rather than inventing one.
    assert pitches[2] == 0.0


def test_cell_split_refuses_when_the_text_and_runs_disagree() -> None:
    builder = _cell_builder()
    cell = type(
        "C",
        (),
        {"runs": [_Run("A", 0.0, 0.0), _Run("B", 0.0, 20.0)], "text": "A\nB"},
    )()
    assert builder._cell_line_groups(cell, "A\nB", []) is not None
    # Two separators but runs on three rows is not a line-by-line cell.
    assert builder._cell_line_groups(cell, "A\nB\nC", []) is None
    # An empty source line is never emitted as an empty paragraph.
    assert builder._cell_line_groups(cell, "A\n\nB", []) is None


def test_cell_split_refuses_a_slot_that_straddles_a_line_boundary() -> None:
    builder = _cell_builder()
    cell = type(
        "C",
        (),
        {
            "runs": [
                _Run("abcdef", 0.0, 0.0),
                _Run("ghij", 0.0, 20.0),
            ],
            "text": "abcdef\nghij",
        },
    )()
    inside = builder._cell_line_groups(cell, "abcdef\nghij", [_Slot(0, 6)])
    assert inside is not None
    assert inside[0][2][0].text_start == 0
    assert builder._cell_line_groups(cell, "abcdef\nghij", [_Slot(4, 8)]) is None


def test_a_split_cell_paragraph_keeps_the_cell_own_spacing_model() -> None:
    document = Document()
    table = document.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    paragraph = cell.paragraphs[0]
    WordSafeSourceDocumentBuilder._configure_cell_paragraph(paragraph, 1.6625, None)
    spacing = paragraph._p.get_or_add_pPr().find(qn("w:spacing"))
    assert spacing is not None
    assert spacing.get(qn("w:lineRule")) == "auto"
    assert spacing.get(qn("w:line")) == "399"
    assert paragraph.paragraph_format.space_before.pt == 0
    assert paragraph.paragraph_format.space_after.pt == 0


def test_the_p3_reviewed_structural_deviation_is_unchanged() -> None:
    evidence = json.loads(
        (
            ROOT
            / "acceptance/evidence/structural_deviations/"
            "response_letter_natural_wrap_boundary.json"
        ).read_text(encoding="utf-8")
    )
    contract = evidence["predecessor_geometry_contract"]
    assert contract["contract_sha256"] == (
        "15052e12b32985826f7b78f06223af7fa46496e47c9690aebeb1fa373c0d385f"
    )
    assert contract["tolerance_pt"] == "2.0"
    assert contract["tolerance_weakened"] is False
    assert contract["rebaselined"] is False
    experiment = evidence["same_word_paragraph_experiment"]
    assert experiment["outcome"] == "SAME_WORD_PARAGRAPH_UNAVAILABLE"
    assert experiment["w_br_in_experiment"] == 0
    assert experiment["w_cr_in_experiment"] == 0
