from __future__ import annotations

from pathlib import Path

import pymupdf
from docx import Document

from tender_basic.models import FieldName, PdfLocator, SourceType
from tender_basic.round48_qa import (
    build_fact_slot_coverage,
    build_glyph_semantics_qa,
    build_rendered_page_qa,
)
from tender_basic.source_fill_policy import slot_field_allowed
from tender_basic.source_font_policy import normalize_pdf_font_name
from tender_basic.source_format import (
    SourceCell, SourceFillSlot, SourceFormatTemplate, SourcePage, SourcePageElement,
    SourceRow, SourceRun, SourceTable, build_table_typography_profile,
    reconstruct_technical_runs,
)
from tender_basic.word_safe_source_builder import WordSafeSourceDocumentBuilder

from test_review_builder import make_project_facts
from test_source_format_fidelity import _resolved


def _cell(row: int, column: int, text: str, font: str, size: float, *, bold: bool = False) -> SourceCell:
    from tender_basic.models import PdfTableLocator
    bbox = (column * 100.0, row * 30.0, column * 100.0 + 90.0, row * 30.0 + 25.0)
    return SourceCell(
        row_index=row, column_index=column, bbox=bbox, text=text,
        runs=[SourceRun(text=text, bbox=bbox, font_name=font, font_size=size, bold=bold)],
        locator=PdfTableLocator(page=1, table_index=0, row_index=row, column_index=column),
    )


def _table(cells: list[SourceCell]) -> SourceTable:
    rows = []
    for row_index in sorted({cell.row_index for cell in cells}):
        rows.append(SourceRow(row_index=row_index, cells=[cell for cell in cells if cell.row_index == row_index]))
    return SourceTable(page=1, table_index=0, bbox=(0, 0, 200, len(rows) * 30), rows=rows,
                       columns=2, column_widths=[100, 100])


def test_pdf_subset_font_normalization() -> None:
    assert normalize_pdf_font_name("ABCDEE+SimSun")[0] == "宋体"
    assert normalize_pdf_font_name("QWERTY+FangSong_GB2312")[0] == "仿宋"
    assert normalize_pdf_font_name("SimHei")[0] == "黑体"
    assert normalize_pdf_font_name("KaiTi")[0] == "楷体"


def test_same_role_table_font_variant_is_not_flattened() -> None:
    cells = [_cell(0, 0, "名称", "SimSun", 10.5)]
    cells += [_cell(i, 0, text, "FangSong", 12) for i, text in enumerate(("甲", "乙", "丙"), 1)]
    cells.append(_cell(4, 0, "水泵", "SimSun", 10.5))
    profile = build_table_typography_profile(_table(cells))
    pump = profile.rows[4].cells[0]
    assert pump.runs[0].font_name == "SimSun"
    assert pump.runs[0].font_size == 10.5
    assert any(item["resolution"] == "PRESERVED_LOCAL_SOURCE_VARIATION" for item in profile.style_outliers)


def test_legitimate_table_font_variation_is_preserved() -> None:
    cells = [_cell(0, 0, "名称", "SimSun", 10.5)]
    cells += [_cell(i, 0, text, "FangSong", 12) for i, text in enumerate(("甲", "乙", "丙"), 1)]
    cells.append(_cell(4, 0, "强调", "SimHei", 16, bold=True))
    profile = build_table_typography_profile(_table(cells))
    assert profile.rows[4].cells[0].runs[0].font_name == "SimHei"
    assert any(item["resolution"] == "PRESERVED_LOCAL_SOURCE_VARIATION" for item in profile.style_outliers)


def _technical_runs(unit: str) -> list[SourceRun]:
    exponent = "²" if "²" in unit else "³"
    base, suffix = unit.split(exponent)
    return [
        SourceRun(text=exponent, bbox=(30, 8, 35, 22), font_name="Calibri", font_size=12),
        SourceRun(text=base, bbox=(0, 10, 30, 20), font_name="FangSong", font_size=12),
        SourceRun(text=suffix, bbox=(35, 10, 55, 20), font_name="FangSong", font_size=12),
    ]


def test_unit_tokens_keep_x_order_for_m2_m3_m3h_m3s() -> None:
    for unit in ("m²", "m³", "m³/h", "m³/s"):
        text, runs, _chars, raised = reconstruct_technical_runs(_technical_runs(unit))
        expected = unit.translate(str.maketrans({"²": "2", "³": "3"}))
        assert text == expected
        assert "".join(run.text for run in runs) == expected
        assert runs[1].text in {"2", "3"}
        assert raised and raised[0].role == "SUPERSCRIPT"
        assert runs[1].font_name == "FangSong"


def test_true_word_superscript_and_no_orphan(tmp_path: Path) -> None:
    text, runs, chars, raised = reconstruct_technical_runs(_technical_runs("800m³/h"))
    cell = _cell(0, 0, text, "FangSong", 12).model_copy(update={"runs": runs, "characters": chars, "raised_glyphs": raised})
    table = _table([cell])
    page = SourcePage(page=1, width=595, height=842, tables=[table],
                      elements=[SourcePageElement(type="table", index=0, bbox=table.bbox)])
    template = SourceFormatTemplate(source_type=SourceType.PDF, source_pages=[page])
    path, _ = WordSafeSourceDocumentBuilder(make_project_facts(), template).build(tmp_path / "unit.docx")
    qa = build_glyph_semantics_qa(path)
    assert qa["orphan_raised_glyph_count"] == 0
    assert qa["unit_token_semantic_error_count"] == 0
    assert qa["result"] == "PASS"


def _slot(slot_id: str, field: FieldName, slot_type: str) -> SourceFillSlot:
    return SourceFillSlot(
        slot_id=slot_id, semantic_hint=field.value, slot_type=slot_type,
        source_page=1, source_locator=PdfLocator(page=1, block_index=int(slot_id[-1])),
        container_type="paragraph", original_text="____", text_start=0, text_end=4,
        allowed_fact_fields=[field], match_kind="underline",
    )


def test_resolved_fact_fills_all_compatible_slots_and_wrong_type_rejected() -> None:
    facts = _resolved(make_project_facts(), FieldName.PROJECT_NAME, "项目甲")
    slots = [_slot("slot-1", FieldName.PROJECT_NAME, "PROJECT_NAME_SLOT"),
             _slot("slot-2", FieldName.PROJECT_NAME, "PROJECT_NAME_SLOT")]
    template = SourceFormatTemplate(source_type=SourceType.PDF, fill_slots=slots)
    report = {"filled_slots": [{"slot_id": "slot-1", "field": ["project_name"]},
                                {"slot_id": "slot-2", "field": ["project_name"]}]}
    qa = build_fact_slot_coverage(template, facts, report)
    item = next(item for item in qa["facts"] if item["field"] == "project_name")
    assert item["compatible_slots_filled"] == 2
    wrong = _slot("slot-3", FieldName.PROJECT_NUMBER, "PROJECT_NAME_SLOT")
    assert not slot_field_allowed(wrong, FieldName.PROJECT_NUMBER)
    assert not slot_field_allowed(slots[0], FieldName.PROJECT_NUMBER)


def test_fixed_source_value_is_not_a_fill_slot() -> None:
    fixed = _cell(1, 1, "固定项目名", "FangSong", 12)
    assert fixed.text == "固定项目名"


def test_actual_rendered_page_count_can_differ_from_section_count(tmp_path: Path) -> None:
    docx = tmp_path / "one-section.docx"
    Document().save(docx)
    pdf = pymupdf.open()
    pdf.new_page(); pdf.new_page()
    pdf_path = tmp_path / "two-pages.pdf"
    pdf.save(pdf_path); pdf.close()
    qa = build_rendered_page_qa(1, docx, pdf_path)
    assert qa["source_section_count"] == 1
    assert qa["actual_rendered_pages"] == 2
    assert qa["generated_page_count"] != qa["source_section_count"]
