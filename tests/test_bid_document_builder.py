from __future__ import annotations

from docx import Document
import pytest

from tender_basic.bid_document_builder import build_bid_document
from tender_basic.output_helpers import load_output_fields

from test_review_builder import make_project_facts


def _document_text(document: Document) -> str:
    paragraph_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    table_text = "\n".join(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    return f"{paragraph_text}\n{table_text}"


def test_bid_document_is_readable_and_contains_basic_information_table(tmp_path) -> None:
    output = tmp_path / "基础投标文件.docx"
    build_bid_document(make_project_facts(), output)

    document = Document(output)
    assert output.stat().st_size > 0
    assert document.paragraphs
    assert document.tables
    info_tables = [table for table in document.tables if len(table.rows) == 21]
    assert len(info_tables) == 1
    info_text = "\n".join(cell.text for row in info_tables[0].rows for cell in row.cells)
    for field in load_output_fields():
        assert field.label in info_text


def test_bid_document_preserves_status_placeholders_and_separate_numbers(tmp_path) -> None:
    output = tmp_path / "bid.docx"
    build_bid_document(make_project_facts(), output)
    text = _document_text(Document(output))

    assert "项目编号" in text and "PRJ-123" in text
    assert "招标编号" in text and "BID-456" in text
    assert "PRJ-123" != "BID-456"
    assert "地点A" not in text
    assert "地点B" not in text
    assert "【待人工确认】" in text
    assert "【待补充】" in text
    assert "投标人：________________" in text
    assert "投标人：采购人甲" not in text


def test_bid_document_contains_only_the_basic_skeleton_sections(tmp_path) -> None:
    output = tmp_path / "bid.docx"
    build_bid_document(make_project_facts(), output)
    text = _document_text(Document(output))

    for heading in (
        "投 标 文 件",
        "项目基本信息",
        "一、投标函",
        "二、资格审查文件",
        "三、商务响应文件",
        "四、技术响应文件",
        "五、报价文件",
        "六、其他材料",
        "签字盖章复核提示",
    ):
        assert heading in text
    assert "【提示：本目录为基础工作骨架" in text
    assert "确保中标" not in text
    assert "完全满足全部要求" not in text


def test_bid_builder_requires_project_facts_ssot(tmp_path) -> None:
    with pytest.raises(TypeError):
        build_bid_document(tmp_path / "not-project-facts.json", tmp_path / "bid.docx")
