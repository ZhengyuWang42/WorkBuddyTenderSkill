from __future__ import annotations

from pathlib import Path

import pymupdf

from tender_basic.document_parser import parse_document
from tender_basic.fact_extractor import extract_candidates
from tender_basic.fact_normalizer import normalize_candidates
from tender_basic.fact_resolver import resolve_project_facts

LOT_FIXTURE = (
    "肇源县城市供水管网漏损治理项目\n"
    "招标文件\n"
    "三标段\n"
    "第二章 投标人须知\n"
    "2.3 标段划分：3个标段（不允许兼投兼中）。\n"
    "2.7 合同估算价：三标段1252.299431万元。\n"
    "3.1 三标段投标人资格要求：投标人必须具有独立法人资格。\n"
    "3.4 投标保证金的金额：三标段12.00万元（人民币）。\n"
    "5.1 投标人应按照本项目同一标段的要求分别递交投标文件。\n"
)

PLAIN_FIXTURE = (
    "某单位设备采购项目\n"
    "第二章 投标人须知\n"
    "2.3 标段划分：本项目不划分标段。\n"
    "3.1 投标人资格要求：投标人必须具有独立法人资格。\n"
    "5.1 投标人应按照招标文件要求递交投标文件。\n"
)


def _make_pdf(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    pdf = pymupdf.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_text((40, 60), text, fontsize=10, fontname="china-s")
    pdf.save(path)
    pdf.close()
    return path


def _facts(tmp_path: Path, name: str, text: str):
    document = parse_document(_make_pdf(tmp_path, name, text))
    candidates = extract_candidates(document)
    return resolve_project_facts(document, normalize_candidates(candidates))


def test_lot_name_resolves_from_lot_scoped_values(tmp_path: Path) -> None:
    facts = _facts(tmp_path, "lot.pdf", LOT_FIXTURE)
    lot = facts.fields.lot_name

    assert lot.status.value == "RESOLVED"
    assert lot.resolved_value == "三标段"
    assert lot.candidates
    assert any("标段" in (candidate.evidence_text or "") for candidate in lot.candidates)
    assert any(
        "合同估算价" in (candidate.evidence_text or "")
        or "投标人资格要求" in (candidate.evidence_text or "")
        or "投标保证金的金额" in (candidate.evidence_text or "")
        for candidate in lot.candidates
    )


def test_generic_same_lot_mentions_are_not_candidates(tmp_path: Path) -> None:
    facts = _facts(tmp_path, "lot.pdf", LOT_FIXTURE)
    lot = facts.fields.lot_name

    for candidate in lot.candidates:
        assert "同一标段" not in (candidate.evidence_text or "")
        assert "每个标段" not in (candidate.evidence_text or "")
        assert candidate.value in {"三标段"}


def test_plain_tender_has_no_lot_name(tmp_path: Path) -> None:
    facts = _facts(tmp_path, "plain.pdf", PLAIN_FIXTURE)
    lot = facts.fields.lot_name

    assert lot.status.value == "NOT_FOUND"
    assert lot.resolved_value is None
