from __future__ import annotations

from pathlib import Path

import pymupdf

from tender_basic.document_parser import parse_document
from tender_basic.dynamic_requirements import (
    MODULE_ORDER,
    build_requirement_index,
    detect_clause,
    detect_markers,
    extract_values,
    source_contains,
    split_source_clauses,
)
from tender_basic.dynamic_requirements import _topic_for, _type_for

FIXTURE_TEXT = (
    "第三章 投标人须知\n"
    "3.1 投标人资格要求\n"
    "3.1.1 投标人必须是在中华人民共和国境内注册的独立法人，具备有效的营业执照。\n"
    "3.1.2 投标人不得被列入失信被执行人名单，须提供信用中国查询截图。\n"
    "4.1 最高投标限价：人民币310万元（不含税），投标报价超过最高投标限价的，其投标无效。\n"
    "4.3 投标报价应为完成本项目全部工作内容的总价，采用固定总价方式。\n"
    "4.2 投标保证金金额：人民币20000元；形式：银行转账；须在投标截止时间前到账。\n"
    "5.1 投标有效期为投标截止之日起90日历天。\n"
    "6.1 供货期为合同签订后30日历天。\n"
    "7.1 投标人须在2026年7月28日10时00分前完成上传，逾期上传的投标文件不予受理。\n"
    "8.1 投标文件的签字盖章须齐全，未按要求签字盖章的投标文件将被否决。\n"
    "9.1 评标办法采用综合评分法，技术分40分，价格分60分，商务分5分。\n"
    "10.1 投标人不得存在下列情形之一：（1）与采购人存在利害关系；（2）为本项目提供过整体设计。\n"
)


def _make_pdf(tmp_path: Path, text: str = FIXTURE_TEXT) -> Path:
    path = tmp_path / "dynamic-requirements.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page(width=620, height=800)
    page.insert_text((50, 70), text, fontsize=10, fontname="china-s")
    pdf.save(path)
    pdf.close()
    return path


def test_requirement_index_ids_modules_and_risk(tmp_path: Path) -> None:
    document = parse_document(_make_pdf(tmp_path))
    index = build_requirement_index(document)

    assert index.units, "the index must not be empty for a document with mandatory clauses"
    assert index.scanned_fragments > 0
    for position, unit in enumerate(index.units, start=1):
        assert unit.requirement_id == f"SR{position:04d}"
        assert unit.topic
        assert unit.module in MODULE_ORDER
        assert unit.text.strip()
        assert unit.evidence_text.strip()
        assert unit.page is None or unit.page >= 1

    types = index.by_type()
    assert types.get("PRICING"), "投标报价总价条款 must become a pricing requirement"
    assert types.get("BOND"), "保证金条款 must become a bond requirement"
    assert types.get("QUALIFICATION"), "资格条款 must become a qualification requirement"
    assert types.get("REJECTION"), "否决/无效条款 must become a rejection requirement"

    limits = [unit for unit in index.units if "最高投标限价" in unit.text]
    assert limits
    # A limit stated together with "其投标无效" is fatal, so it must be a
    # rejection requirement even though it also carries a price value.
    assert all(unit.requirement_type == "REJECTION" for unit in limits)
    assert all(unit.high_risk for unit in limits)


def test_rejection_clauses_outrank_their_topic(tmp_path: Path) -> None:
    document = parse_document(_make_pdf(tmp_path))
    index = build_requirement_index(document)
    rejections = [unit for unit in index.units if unit.requirement_type == "REJECTION"]
    texts = " ".join(unit.text for unit in rejections)

    assert "投标无效" in texts or "否决" in texts or "不予受理" in texts
    assert all(unit.module == "一、废标红线" for unit in rejections)


def test_dates_scores_and_counts_are_not_values() -> None:
    assert extract_values("投标人须在2026年7月28日10时00分前完成上传。") == []
    assert "1.12分" not in extract_values("1.12 分包：本项目不允许分包。")
    scores = extract_values("评标办法采用综合评分法，技术分40分，价格分60分。")
    assert scores == ["40分", "60分"]
    values = extract_values("最高投标限价：人民币310万元（不含税）。")
    assert any("310" in value for value in values)


def test_inline_enumeration_is_split_into_clauses() -> None:
    parts = split_source_clauses(
        "投标人不得存在下列情形之一：（1）与采购人存在利害关系；（2）为本项目提供过整体设计。"
    )
    assert len(parts) >= 2
    assert any("利害关系" in part for part in parts)
    assert any("整体设计" in part for part in parts)


def test_topic_and_type_classification_is_source_driven() -> None:
    assert _type_for("投标报价超过最高投标限价的，其投标无效。", ["无效"], ["必须"], []) == "REJECTION"
    assert _type_for("最高投标限价：人民币310万元。", [], [], ["310万元"]) == "PRICING"
    assert _type_for("投标保证金金额：人民币20000元。", [], ["须"], ["20000元"]) == "BOND"
    assert _topic_for("PRICING", "最高投标限价：人民币310万元。") == "最高限价与控制价"
    assert _topic_for("REJECTION", "投标人不符合资格条件的，其投标无效。") == "资格条件不符合"
    assert _topic_for("REJECTION", "投标报价超过最高投标限价的，其投标无效。") == "报价超过最高限价"
    assert _topic_for("OTHER", "本合同的争议解决方式为仲裁。") == "合同责任"


def test_clause_and_marker_detection() -> None:
    assert detect_clause("3.1.2 投标人不得被列入失信被执行人名单") == "3.1.2"
    strong, mandatory = detect_markers("投标人必须提供营业执照，否则投标无效。")
    assert strong
    assert mandatory


def test_duplicate_clauses_are_merged_once(tmp_path: Path) -> None:
    repeated = FIXTURE_TEXT + "\n" + "4.1 最高投标限价：人民币310万元（不含税），投标报价超过最高投标限价的，其投标无效。"
    document = parse_document(_make_pdf(tmp_path, repeated))
    index = build_requirement_index(document)

    limits = [unit for unit in index.units if "最高投标限价：人民币310万元" in unit.text]
    assert len(limits) == 1
    assert index.merged_duplicates >= 1


def test_source_contains_matches_grouped_text(tmp_path: Path) -> None:
    document = parse_document(_make_pdf(tmp_path))
    assert source_contains(document, "营业执照")
    assert source_contains(document, "最高投标限价")
    assert not source_contains(document, "数据库")
    assert not source_contains(document, "国产化")
