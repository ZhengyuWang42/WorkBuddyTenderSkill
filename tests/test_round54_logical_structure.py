"""Round 5.4 regression tests: logical source structure and fact slot coverage.

These tests are generic.  They deliberately use small synthetic sources rather
than case-specific page numbers or values, so the production logic cannot
depend on one tender document.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tender_basic.document_models import PdfTableCell, PdfTableLocator
from tender_basic.models import PdfLocator
from tender_basic.logical_structure import (
    build_logical_source_tables,
    build_logical_tables,
    split_fragments,
)
from tender_basic.source_format import (
    SourceCell,
    SourceRow,
    SourceTable,
    SourceRun,
    _classify_cell_alignment,
    _slot_contract,
    cell_alignment_evidence,
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _cell(box, text, row_index=0, column_index=0):
    return PdfTableCell(
        row_index=row_index,
        column_index=column_index,
        bbox=box,
        text=text,
        locator=PdfTableLocator(page=1, table_index=0, row_index=row_index, column_index=column_index),
    )


def _run(text, box):
    return SourceRun(text=text, bbox=box, font_name="SimSun", font_size=10.5)


def _source_cell(column_index, text, box):
    return SourceCell(
        row_index=0,
        column_index=column_index,
        bbox=box,
        text=text,
        runs=[_run(text, box)] if text.strip() else [],
        locator=PdfTableLocator(page=1, table_index=0, row_index=0, column_index=column_index),
    )


def _fragment(page, rows, *, columns=2, widths=(100.0, 200.0), top=90.0, bottom=500.0, index=0):
    """Build one PDF table fragment on ``page``."""
    source_rows = []
    for row_index, values in enumerate(rows):
        cells = [
            _source_cell(
                column,
                values[column] if column < len(values) else "",
                (100.0 + sum(widths[:column]), top, 100.0 + sum(widths[: column + 1]), bottom),
            )
            for column in range(columns)
        ]
        source_rows.append(SourceRow(row_index=row_index, cells=cells, height=30.0))
    table = SourceTable(
        page=page,
        table_index=index,
        bbox=(100.0, top, 100.0 + sum(widths), bottom),
        rows=source_rows,
        columns=columns,
        column_widths=list(widths),
        row_heights=[30.0] * len(rows),
    )
    return (page, 595.3, table)


# --------------------------------------------------------------------------
# source cell alignment model
# --------------------------------------------------------------------------


def test_single_line_flush_left_is_left_aligned():
    box = (100.0, 10.0, 400.0, 40.0)
    evidence = cell_alignment_evidence(_cell(box, "x"), [_run("x", (102.0, 20.0, 140.0, 30.0))])
    assert evidence.alignment == "left"


def test_single_line_flush_right_is_right_aligned():
    box = (100.0, 10.0, 400.0, 40.0)
    evidence = cell_alignment_evidence(_cell(box, "x"), [_run("x", (360.0, 20.0, 398.0, 30.0))])
    assert evidence.alignment == "right"


def test_centered_line_in_wide_cell_is_centered():
    box = (100.0, 10.0, 400.0, 40.0)
    evidence = cell_alignment_evidence(_cell(box, "x"), [_run("x", (230.0, 20.0, 270.0, 30.0))])
    assert evidence.alignment == "center"


def test_multi_line_left_axis_wins_over_stable_center():
    """A stable center axis alone must not force CENTER when lines share a left edge."""
    box = (100.0, 10.0, 400.0, 100.0)
    runs = [
        _run("a" * 30, (102.0, 20.0, 300.0, 32.0)),
        _run("b" * 8, (102.0, 40.0, 150.0, 52.0)),
        _run("c" * 16, (102.0, 60.0, 210.0, 72.0)),
    ]
    evidence = cell_alignment_evidence(_cell(box, "x"), runs)
    assert evidence.alignment == "left"
    assert evidence.left_spread == pytest.approx(0.0)
    # The center axis is genuinely unstable here, which is why LEFT wins.
    assert evidence.center_spread > evidence.left_spread


def test_justify_requires_body_lines_at_both_edges_and_shorter_last_line():
    box = (100.0, 10.0, 400.0, 100.0)
    runs = [
        _run("a" * 40, (102.0, 20.0, 398.0, 32.0)),
        _run("b" * 40, (102.0, 40.0, 398.0, 52.0)),
        _run("c" * 5, (102.0, 60.0, 140.0, 72.0)),
    ]
    evidence = cell_alignment_evidence(_cell(box, "x"), runs)
    assert evidence.alignment == "justify"
    assert evidence.fill_ratio >= 0.6


def test_unsupported_asymmetric_padding_reports_unknown_not_a_guess():
    """Insufficient evidence must be reported, never resolved to a role default."""
    box = (100.0, 10.0, 400.0, 40.0)
    evidence = cell_alignment_evidence(_cell(box, "x"), [_run("x", (150.0, 20.0, 200.0, 30.0))])
    assert evidence.alignment == "unknown"
    # The frozen render contract has no neutral value, so it degrades to left
    # while QA still sees the uncertainty.
    from tender_basic.source_format import _alignment_label

    assert _alignment_label(evidence) == "left"


def test_same_semantic_role_yields_different_alignment_from_geometry_only():
    box = (100.0, 10.0, 400.0, 40.0)
    left = cell_alignment_evidence(_cell(box, "value"), [_run("value", (102.0, 20.0, 160.0, 30.0))])
    right = cell_alignment_evidence(_cell(box, "value"), [_run("value", (350.0, 20.0, 398.0, 30.0))])
    assert left.alignment == "left"
    assert right.alignment == "right"


# --------------------------------------------------------------------------
# logical table continuation
# --------------------------------------------------------------------------


def _quotation_fragments():
    """Two adjacent pages of one logical table, split mid-sentence."""
    page_one = _fragment(
        10,
        [
            ["序号", "功能要求"],
            ["1", "配电模块至少包含 2 路 UPS 输"],
        ],
        top=90.0,
        bottom=500.0,
    )
    page_two = _fragment(
        11,
        [
            ["", "出支路；UPS 类型：单进单出"],
            ["2", "服务器配置说明"],
        ],
        top=90.0,
        bottom=500.0,
    )
    return [page_one, page_two]


def test_true_continuation_merges_into_one_logical_table():
    tables, report = build_logical_tables(_quotation_fragments())
    assert len(tables) == 1
    assert report.logical_table_count == 1
    assert report.continuation_fragments_merged == 1
    assert report.orphan_continuation_fragments == 0
    assert report.false_continuation_merges == 0


def test_continuation_text_order_is_preserved():
    tables, _report = build_logical_tables(_quotation_fragments())
    logical = tables[0].rows[1]
    fragments = [f.raw_text for f in logical.cells[1].fragments]
    joined = "".join(fragments)
    assert joined.startswith("配电模块至少包含 2 路 UPS 输")
    assert "输出支路" in joined.replace(" ", "")
    assert joined.index("输") < joined.index("出支路")


def test_resumed_item_index_merges_into_one_logical_table():
    """A table cut between two complete rows is still one logical table.

    Each row is a complete item and no cell text continues across the seam, so
    the item index column is the source evidence that the two PDF fragments are
    one table.  Both fragments are cut by the page boundary and share one grid.
    """
    page_one = _fragment(
        10,
        [["序号", "内容"], ["1", "第一项完整内容。"]],
        top=90.0,
        bottom=500.0,
    )
    page_two = _fragment(
        11,
        [["2", "第二项独立内容。"]],
        top=90.0,
        bottom=500.0,
    )
    tables, report = build_logical_tables([page_one, page_two])
    assert len(tables) == 1
    assert report.continuation_fragments_merged == 1
    assert report.false_continuation_merges == 0
    rows = tables[0].rows
    assert [row.identity for row in rows] == [("序号",), ("1",), ("2",)]


def test_broken_item_index_is_not_merged():
    """An index that does not continue proves these are two different tables."""
    page_one = _fragment(
        10,
        [["序号", "内容"], ["1", "第一项完整内容。"]],
        top=90.0,
        bottom=500.0,
    )
    page_two = _fragment(
        11,
        [["7", "另一张表的第七项。"]],
        top=90.0,
        bottom=500.0,
    )
    tables, report = build_logical_tables([page_one, page_two])
    assert len(tables) == 2
    assert report.continuation_fragments_merged == 0
    assert report.false_continuation_merges == 0


def test_repeated_header_row_starts_a_new_table():
    """A page that opens with its own column header restarts the table."""
    page_one = _fragment(
        10,
        [["序号", "内容"], ["1", "第一项完整内容。"]],
        top=90.0,
        bottom=500.0,
    )
    page_two = _fragment(
        11,
        [["序号", "内容"], ["2", "第二项独立内容。"]],
        top=90.0,
        bottom=500.0,
    )
    tables, report = build_logical_tables([page_one, page_two])
    assert len(tables) == 2
    assert report.continuation_fragments_merged == 0


def test_matching_geometry_alone_does_not_merge():
    """Same grid and same page band, but the previous fragment ended a sentence."""
    page_one = _fragment(
        10,
        [["序号", "内容"], ["1", "这一项已经写完。"]],
        top=90.0,
        bottom=500.0,
    )
    page_two = _fragment(
        11,
        [["", "完全无关的另一句"]],
        top=90.0,
        bottom=500.0,
    )
    tables, _report = build_logical_tables([page_one, page_two])
    assert len(tables) == 2


def test_non_adjacent_pages_are_never_merged():
    fragments = [
        _fragment(10, [["序号", "内容"], ["1", "未完成的句子没有结束"]], index=0),
        _fragment(13, [["", "出支路；继续"]], index=1),
    ]
    tables, report = build_logical_tables(fragments)
    assert len(tables) == 2
    assert report.continuation_fragments_merged == 0


def test_incompatible_grid_is_never_merged():
    page_one = _fragment(
        10,
        [["序号", "内容"], ["1", "未完成的句子没有结束"]],
        columns=2,
        widths=(100.0, 200.0),
    )
    # A different outer extent means a different physical table.
    page_two = (11, 595.3, SourceTable(
        page=11,
        table_index=1,
        bbox=(300.0, 90.0, 700.0, 500.0),
        rows=[SourceRow(row_index=0, cells=[
            _source_cell(0, "", (300.0, 90.0, 400.0, 500.0)),
            _source_cell(1, "出支路；继续", (400.0, 90.0, 700.0, 500.0)),
        ])],
        columns=2,
        column_widths=[100.0, 300.0],
    ))
    tables, report = build_logical_tables([page_one, page_two])
    assert len(tables) == 2
    assert report.continuation_fragments_merged == 0


def test_split_fragments_reports_every_decision():
    _groups, decisions = split_fragments(_quotation_fragments())
    assert len(decisions) == 1
    decision = decisions[0]
    assert set(decision) >= {"previous_page", "page", "merge", "reasons"}
    assert decision["merge"] is True
    assert decision["reasons"]


def test_reconstruction_preserves_every_source_character():
    """Merging reorders text but must never add or drop a character."""
    from collections import Counter

    fragments = [
        _fragment(
            10,
            [["序号", "功能要求"], ["1", "配电模块至少包含 2 路 UPS 输"], ["2", "第二项内容结束。"]],
            top=90.0,
            bottom=500.0,
        ),
        _fragment(
            11,
            [["", "出支路；UPS 类型：单进单出"], ["3", "第三项内容结束。"]],
            top=90.0,
            bottom=500.0,
        ),
    ]
    tables, _report = build_logical_tables(fragments)
    source = "".join(c.text for _p, _h, t in fragments for r in t.rows for c in r.cells)
    rebuilt = "".join(
        "".join(f.raw_text for f in cell.fragments)
        for t in tables for r in t.rows for cell in r.cells
    )
    assert Counter(source) == Counter(rebuilt)


def test_continuation_row_with_numbered_subitem_still_merges():
    """A page seam between numbered sub-items is one logical cell."""
    fragments = [
        _fragment(10, [["序号", "功能要求"], ["1", "技术要求如下："]], top=90.0, bottom=500.0),
        _fragment(11, [["", "2、第二项要求"]], top=90.0, bottom=500.0),
    ]
    tables, report = build_logical_tables(fragments)
    assert report.continuation_fragments_merged == 1
    assert len(tables) == 1


# --------------------------------------------------------------------------
# production plan: the editable Word table is the logical table
# --------------------------------------------------------------------------


def test_plan_emits_one_word_table_and_folds_the_continuation():
    fragments = [
        _fragment(10, [["序号", "功能要求"], ["1", "配电模块至少包含 2 路 UPS 输"]],
                  top=90.0, bottom=500.0),
        _fragment(11, [["", "出支路；UPS 类型：单进单出"]], top=90.0, bottom=500.0),
    ]
    plan = build_logical_source_tables(fragments)
    assert len(plan.source_tables) == 1
    assert plan.table_for(10, 0) is not None
    # The continuation page is not a Word table of its own.
    assert plan.table_for(11, 0) is None
    assert plan.continuation_map == {(11, 0): (10, 0)}
    merged = plan.source_tables[0]
    assert merged.columns == 2
    assert len(merged.rows) == 2
    joined = "".join(c.text for r in merged.rows for c in r.cells)
    assert "UPS输出支路；UPS类型：单进单出" in joined.replace(" ", "")
    source = "".join(c.text for _p, _h, t in fragments for r in t.rows for c in r.cells)
    assert Counter(source) == Counter(joined)


def test_a_folded_fragment_never_owns_its_own_section():
    """A continuation page renders inside the head fragment's section.

    The folded fragment's rows already render in the head table, so a section of
    its own would be an empty section - a page Word fills with nothing.
    """

    fragments = [
        _fragment(10, [["序号", "功能要求"], ["1", "配电模块至少包含 2 路 UPS 输"]],
                  top=90.0, bottom=500.0),
        _fragment(11, [["", "出支路；UPS 类型：单进单出"]], top=90.0, bottom=500.0),
        _fragment(12, [["序号", "功能要求"], ["2", "独立的一段新表"]], top=90.0, bottom=500.0),
    ]
    plan = build_logical_source_tables(fragments)
    assert plan.continuation_map == {(11, 0): (10, 0)}
    # The head page owns its section; the folded page does not; a page whose
    # fragment is a table head of its own does again.
    assert plan.head_page_for(10, 0) is None
    assert plan.head_page_for(11, 0) == 10
    assert plan.head_page_for(12, 0) is None
    assert plan.logical_tables[0].subsumed_by_head is True
    assert plan.logical_tables[1].subsumed_by_head is False


def test_coarser_continuation_grid_maps_onto_the_head_columns():
    """A later fragment that drops a column keeps the head table's grid."""
    head = _fragment(20, [["序号", "名称", "要求"], ["1", "甲", "甲乙丙丁戊己庚辛壬癸子丑"]],
                     columns=3, widths=(60.0, 100.0, 100.0), top=90.0, bottom=500.0)
    tail = _fragment(21, [["", "甲乙丙丁戊己庚辛壬癸子丑寅卯"]],
                     columns=2, widths=(60.0, 200.0), top=90.0, bottom=500.0, index=1)
    plan = build_logical_source_tables([head, tail])
    assert len(plan.source_tables) == 1
    merged = plan.source_tables[0]
    assert merged.columns == 3
    # The coarser fragment's second column is folded into the head's own
    # continuation column rather than becoming a new column or a new row.
    assert len(merged.rows) == 2
    source = "".join(c.text for _p, _h, t in (head, tail) for r in t.rows for c in r.cells)
    assert Counter(source) == Counter("".join(c.text for r in merged.rows for c in r.cells))


# --------------------------------------------------------------------------
# nested composite placeholder contract
# --------------------------------------------------------------------------


def test_nested_composite_placeholder_names_project_and_lot():
    slot_type, allowed = _slot_contract("项目名称（标段名称）")
    assert slot_type == "PROJECT_AND_LOT_SLOT"
    assert {field.value for field in allowed} == {"project_name", "lot_name"}


def test_plain_project_name_hint_is_a_single_field_slot():
    slot_type, allowed = _slot_contract("项目名称")
    assert slot_type == "PROJECT_NAME_SLOT"
    assert [field.value for field in allowed] == ["project_name"]


def test_unknown_hint_grants_no_field():
    """An unrecognised placeholder must not be fillable by anything."""
    slot_type, allowed = _slot_contract("签字日期")
    assert slot_type == "UNKNOWN_SLOT"
    assert allowed == []


def _candidate(value, evidence, field="project_name"):
    """Build a candidate exactly as production does: normalized_value is set."""
    from tender_basic.fact_normalizer import normalize_field_value
    from tender_basic.models import CandidateFact

    return CandidateFact(
        value=value,
        normalized_value=normalize_field_value(field, value),
        confidence=0.95,
        method="label_value_same_line",
        source_file="x.pdf",
        source_type="PDF",
        locator=PdfLocator(page=1, block_index=0),
        evidence_text=evidence,
    )


def test_composite_replacement_preserves_unresolved_component():
    from tender_basic.models import FieldName
    from tender_basic.source_fill_policy import slot_replacement
    from tender_basic.fact_resolver import resolve_field, load_field_aliases

    class _Slot:
        slot_type = "PROJECT_AND_LOT_SLOT"
        semantic_hint = "项目名称（标段名称）"
        original_text = "（项目名称（标段名称））"
        allowed_fact_fields = [FieldName.PROJECT_NAME, FieldName.LOT_NAME]
        suffix_text = ""

    class _Facts:
        class fields:
            project_name = resolve_field(
                "project_name",
                [_candidate("测试项目名称", "项目名称：测试项目名称")],
                [],
                load_field_aliases(),
            )
            lot_name = resolve_field("lot_name", [], [], load_field_aliases())

    result = slot_replacement(_Slot(), _Facts())
    assert result is not None
    text, method = result
    # The resolved half is filled...
    assert "测试项目名称" in text
    # ...and the unresolved half keeps its original source placeholder.
    assert "标段名称" in text
    assert method == "source_slot_partial"


def test_composite_replacement_fills_both_when_both_resolve():
    from tender_basic.models import FieldName
    from tender_basic.source_fill_policy import slot_replacement
    from tender_basic.fact_resolver import resolve_field, load_field_aliases

    class _Slot:
        slot_type = "PROJECT_AND_LOT_SLOT"
        semantic_hint = "项目名称（标段名称）"
        original_text = "（项目名称（标段名称））"
        allowed_fact_fields = [FieldName.PROJECT_NAME, FieldName.LOT_NAME]
        suffix_text = ""

    class _Facts:
        class fields:
            project_name = resolve_field(
                "project_name", [_candidate("测试项目", "项目名称：测试项目")], [], load_field_aliases()
            )
            lot_name = resolve_field(
                "lot_name",
                [_candidate("一标段", "标段名称：一标段", field="lot_name")],
                [],
                load_field_aliases(),
            )

    text, method = slot_replacement(_Slot(), _Facts())
    assert "测试项目" in text and "一标段" in text
    assert method == "source_slot"


def test_does_not_fill_when_nothing_resolves():
    from tender_basic.models import FieldName
    from tender_basic.source_fill_policy import slot_replacement
    from tender_basic.fact_resolver import resolve_field, load_field_aliases

    class _Slot:
        slot_type = "PROJECT_AND_LOT_SLOT"
        semantic_hint = "项目名称（标段名称）"
        original_text = "（项目名称（标段名称））"
        allowed_fact_fields = [FieldName.PROJECT_NAME, FieldName.LOT_NAME]
        suffix_text = ""

    class _Facts:
        class fields:
            project_name = resolve_field("project_name", [], [], load_field_aliases())
            lot_name = resolve_field("lot_name", [], [], load_field_aliases())

    assert slot_replacement(_Slot(), _Facts()) is None


# --------------------------------------------------------------------------
# wrong fact type safety
# --------------------------------------------------------------------------


def test_cross_type_fills_are_rejected():
    from tender_basic.models import FieldName
    from tender_basic.source_fill_policy import slot_field_allowed

    class _Slot:
        slot_type = "PROJECT_NUMBER_SLOT"
        semantic_hint = "项目编号"
        original_text = "（项目编号）"
        allowed_fact_fields = [FieldName.PROJECT_NUMBER]

    assert slot_field_allowed(_Slot(), FieldName.PROJECT_NUMBER) is True
    # A tender number is not a project number, even though both are identifiers.
    assert slot_field_allowed(_Slot(), FieldName.TENDER_NUMBER) is False
    assert slot_field_allowed(_Slot(), FieldName.PROJECT_NAME) is False

    class _PurchaserSlot:
        slot_type = "PURCHASER_SLOT"
        semantic_hint = "招标人名称"
        original_text = "（招标人名称）"
        allowed_fact_fields = [FieldName.PURCHASER]

    # An agency is not the purchaser.
    assert slot_field_allowed(_PurchaserSlot(), FieldName.TENDER_AGENCY) is False
    assert slot_field_allowed(_PurchaserSlot(), FieldName.PURCHASER) is True


# --------------------------------------------------------------------------
# junk candidate hygiene
# --------------------------------------------------------------------------


def test_blank_glyph_run_is_not_a_fact_value():
    from tender_basic.fact_extractor import _is_non_value_reference

    private_use = "\ue5e5" * 15
    assert _is_non_value_reference("project_name", private_use) is True


def test_bracketed_instruction_is_not_a_purchaser_value():
    from tender_basic.fact_extractor import _is_non_value_reference

    assert _is_non_value_reference("purchaser", "盖单位章") is False  # bare text
    assert _is_non_value_reference("project_name", "（盖单位章）") is True


def test_bare_role_noun_is_not_an_entity_name():
    from tender_basic.fact_extractor import _is_non_value_reference

    assert _is_non_value_reference("project_name", "承包单位") is True
    assert _is_non_value_reference("purchaser", "招标人") is True
    # A real name that merely contains a role word is still a value.
    assert _is_non_value_reference("purchaser", "肇源县城市管理综合执法局") is False


def test_bare_measurement_unit_is_not_a_value():
    from tender_basic.fact_extractor import _is_non_value_reference

    assert _is_non_value_reference("duration", "日历天") is True
    assert _is_non_value_reference("duration", "554日历天") is False


def test_label_header_block_evidence_is_rejected():
    from tender_basic.fact_extractor import _evidence_is_label_header_block, load_field_aliases

    aliases = load_field_aliases()
    header = "项目名称\n工程名称"
    assert _evidence_is_label_header_block(header, aliases, "project_name") is True
    # A genuine label/value pair is never treated as a header row.
    assert _evidence_is_label_header_block("质量目标\n合格", aliases, "quality_target") is False
