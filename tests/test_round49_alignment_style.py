from __future__ import annotations

from docx import Document

from tender_basic.models import FieldName, PdfLocator, PdfTableLocator, SourceType
from tender_basic.page_layout import AlignmentRole, build_page_layout
from tender_basic.round49_qa import build_filled_slot_style_audit
from tender_basic.source_format import (
    DestinationStyleProfile, SourceCell, SourceFillSlot, SourceFormatTemplate,
    SourcePage, SourcePageElement, SourceRow, SourceRun, SourceTable,
    _destination_style_for_slot, build_table_typography_profile,
)
from tender_basic.word_safe_source_builder import WordSafeSourceDocumentBuilder

from test_review_builder import make_project_facts
from test_round46_form_layout import _paragraph, _template
from test_source_format_fidelity import _resolved


def test_centered_form_alignment_is_source_geometry_semantic() -> None:
    paragraph = _paragraph("项目编号：____", bbox=(245.0, 100.0, 350.0, 114.0))
    layout = build_page_layout(_template([paragraph]).source_pages[0])
    row = layout.form_blocks[0].row_geometries[0]
    assert row.item.alignment_role == AlignmentRole.CENTERED_FORM_LINE
    assert row.centered_form_line is not None
    assert abs(row.centered_form_line.source_line_center_x - 297.5) < .01


def test_centered_form_fill_uses_center_and_zero_indents_with_fixed_slot(tmp_path) -> None:
    paragraph = _paragraph("项目编号：____", bbox=(245.0, 100.0, 350.0, 114.0))
    slot = SourceFillSlot(
        slot_id="center", semantic_hint="项目编号", slot_type="PROJECT_NUMBER_SLOT",
        source_page=1, source_locator=paragraph.locator, container_type="paragraph",
        original_text="____", text_start=5, text_end=9, font_name="FangSong", font_size=12,
        underline=True, geometry=(305, 100, 350, 114), allowed_fact_fields=[FieldName.PROJECT_NUMBER],
        match_kind="underline", destination_style=DestinationStyleProfile(
            east_asia_font="仿宋", latin_font="Times New Roman", font_size=12,
            underline=True, paragraph_alignment="center", anchor_source="DESTINATION_PLACEHOLDER_RUN",
        ),
    )
    template = _template([paragraph]).model_copy(update={"fill_slots": [slot]})
    facts = _resolved(make_project_facts(), FieldName.PROJECT_NUMBER, "ABC-2026-001")
    path, report = WordSafeSourceDocumentBuilder(facts, template).build(tmp_path / "center.docx")
    p = Document(path).paragraphs[0]
    assert p.alignment == 1
    assert (p.paragraph_format.left_indent.pt or 0) == 0
    assert (p.paragraph_format.right_indent.pt or 0) == 0
    assert (p.paragraph_format.first_line_indent.pt or 0) == 0
    assert "\t" not in p.text
    assert report["logical_paragraph_records"][0]["alignment_role"] == "CENTERED_FORM_LINE"


def test_empty_table_value_resolves_style_from_paired_label() -> None:
    label = SourceCell(
        row_index=0, column_index=0, bbox=(0, 0, 100, 30), text="项目名称、标段",
        runs=[SourceRun(text="项目名称、标段", bbox=(5, 5, 85, 20), font_name="FangSong", font_size=12)],
        locator=PdfTableLocator(page=1, table_index=0, row_index=0, column_index=0),
    )
    value = SourceCell(
        row_index=0, column_index=1, bbox=(100, 0, 300, 30), text="", runs=[],
        locator=PdfTableLocator(page=1, table_index=0, row_index=0, column_index=1),
    )
    table = build_table_typography_profile(SourceTable(
        page=1, table_index=0, bbox=(0, 0, 300, 30), rows=[SourceRow(row_index=0, cells=[label, value])],
        columns=2, column_widths=[100, 200],
    ))
    page = SourcePage(page=1, width=595, height=842, tables=[table],
                      elements=[SourcePageElement(type="table", index=0, bbox=table.bbox)])
    slot = SourceFillSlot(
        slot_id="table", semantic_hint="项目名称、标段", slot_type="PROJECT_NAME_SLOT",
        source_page=1, source_locator=value.locator, container_type="table_cell", original_text="",
        allowed_fact_fields=[FieldName.PROJECT_NAME], match_kind="table_blank",
        table_index=0, row_index=0, column_index=1,
    )
    profile = _destination_style_for_slot(slot, [page])
    assert profile.east_asia_font == "仿宋"
    assert profile.font_size == 12
    assert profile.anchor_source == "SAME_ROW_SEMANTIC_PEER"


def test_same_fact_uses_independent_destination_styles(tmp_path) -> None:
    left = _paragraph("（项目名称）", bbox=(72, 80, 150, 94))
    right = _paragraph("（项目名称）", block=1, bbox=(72, 120, 150, 134))
    slots = []
    for index, (paragraph, font, size) in enumerate(((left, "仿宋", 12), (right, "宋体", 10.5))):
        slots.append(SourceFillSlot(
            slot_id=f"slot-{index}", semantic_hint="项目名称", slot_type="PROJECT_NAME_SLOT",
            source_page=1, source_locator=paragraph.locator, container_type="paragraph",
            original_text="（项目名称）", text_start=0, text_end=6,
            allowed_fact_fields=[FieldName.PROJECT_NAME], match_kind="parenthetical",
            destination_style=DestinationStyleProfile(
                east_asia_font=font, latin_font="Times New Roman", font_size=size,
                paragraph_alignment="left", anchor_source="DESTINATION_PLACEHOLDER_RUN",
            ),
        ))
    facts = _resolved(make_project_facts(), FieldName.PROJECT_NAME, "示例项目")
    template = _template([left, right]).model_copy(update={"fill_slots": slots})
    _path, report = WordSafeSourceDocumentBuilder(facts, template).build(tmp_path / "independent.docx")
    assert [item["value"] for item in report["filled_slots"]] == ["示例项目", "示例项目"]
    assert [item["generated_value_style"]["east_asia_font"] for item in report["filled_slots"]] == ["仿宋", "宋体"]
    audit = build_filled_slot_style_audit(report)
    assert audit["result"] == "PASS"
    assert audit["filled_slot_font_family_mismatch"] == 0
