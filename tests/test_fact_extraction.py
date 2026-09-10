from __future__ import annotations

from pathlib import Path

from tender_basic.document_models import (
    DocumentBlock,
    DocumentCell,
    DocumentPage,
    DocumentParagraph,
    DocumentRow,
    DocumentStatus,
    DocumentTable,
    NormalizedDocument,
    ParagraphElement,
    PdfBlockElement,
    TableElement,
)
from tender_basic.fact_extractor import extract_candidates
from tender_basic.fact_normalizer import normalize_candidates
from tender_basic.fact_resolver import resolve_project_facts
from tender_basic.models import (
    DocxParagraphLocator,
    DocxTableLocator,
    FieldName,
    PdfLocator,
    SourceType,
)


def _paragraph(index: int, text: str, style_name: str | None = None) -> ParagraphElement:
    return ParagraphElement(
        paragraph=DocumentParagraph(
            paragraph_index=index,
            text=text,
            style_name=style_name,
            locator=DocxParagraphLocator(paragraph_index=index),
        )
    )


def _table(table_index: int, rows: list[list[str]]) -> TableElement:
    return TableElement(
        table=DocumentTable(
            table_index=table_index,
            rows=[
                DocumentRow(
                    row_index=row_index,
                    cells=[
                        DocumentCell(
                            cell_index=cell_index,
                            text=text,
                            locator=DocxTableLocator(
                                table_index=table_index,
                                row_index=row_index,
                                cell_index=cell_index,
                            ),
                        )
                        for cell_index, text in enumerate(row)
                    ],
                )
                for row_index, row in enumerate(rows)
            ],
        )
    )


def _document(*elements: object) -> NormalizedDocument:
    return NormalizedDocument(
        source_file="sample.docx",
        source_type=SourceType.DOCX,
        status=DocumentStatus.PARSED,
        page_count=0,
        text_length=1,
        elements=list(elements),
    )


def _pdf_document(*blocks: str) -> NormalizedDocument:
    normalized_blocks = [
        DocumentBlock(
            block_index=index,
            text=text,
            bbox=(0.0, 0.0, 100.0, 20.0),
            locator=PdfLocator(page=1, block_index=index),
        )
        for index, text in enumerate(blocks)
    ]
    return NormalizedDocument(
        source_file="sample.pdf",
        source_type=SourceType.PDF,
        status=DocumentStatus.PARSED,
        page_count=1,
        text_length=sum(len(block.text) for block in normalized_blocks),
        pages=[DocumentPage(page_number=1, blocks=normalized_blocks)],
        elements=[PdfBlockElement(page_number=1, block=block) for block in normalized_blocks],
    )


def _facts(document: NormalizedDocument):
    raw = extract_candidates(document)
    return resolve_project_facts(document, normalize_candidates(raw))


def test_same_line_candidate_resolves_project_name() -> None:
    facts = _facts(_document(_paragraph(0, "项目名称：智慧城市平台项目")))
    fact = facts.fields.project_name

    assert fact.status.value == "RESOLVED"
    assert fact.resolved_value == "智慧城市平台项目"
    assert fact.candidates[0].method == "label_value_same_line"
    assert fact.candidates[0].evidence_text == "项目名称：智慧城市平台项目"


def test_pdf_candidate_uses_one_based_page_locator() -> None:
    facts = _facts(_pdf_document("项目名称：PDF测试项目"))
    candidate = facts.fields.project_name.candidates[0]

    assert facts.fields.project_name.resolved_value == "PDF测试项目"
    assert candidate.source_type == SourceType.PDF
    assert candidate.locator.model_dump(mode="json") == {
        "locator_type": "pdf_block",
        "page": 1,
        "block_index": 0,
    }


def test_table_candidates_keep_field_identity_and_value_locator() -> None:
    document = _document(
        _table(
            0,
            [
                ["项目名称", "测试工程"],
                ["项目编号", "PRJ-001"],
                ["招标编号", "BID-002"],
            ],
        )
    )
    facts = _facts(document)

    assert facts.fields.project_name.resolved_value == "测试工程"
    assert facts.fields.project_number.resolved_value == "PRJ-001"
    assert facts.fields.tender_number.resolved_value == "BID-002"
    assert facts.fields.project_number.candidates[0].method == "table_label_exact"
    assert facts.fields.project_number.candidates[0].locator.model_dump(mode="json") == {
        "locator_type": "docx_table_cell",
        "table_index": 0,
        "row_index": 1,
        "cell_index": 1,
    }


def test_four_column_table_checks_every_label_cell() -> None:
    facts = _facts(
        _document(_table(0, [["项目名称", "测试工程", "项目编号", "PRJ-001"]]))
    )

    assert facts.fields.project_name.resolved_value == "测试工程"
    assert facts.fields.project_number.resolved_value == "PRJ-001"


def test_same_line_method_and_money_normalization() -> None:
    document = _document(_paragraph(0, "最高限价：1,000,000元"))
    raw = extract_candidates(document)
    normalized = normalize_candidates(raw)

    assert raw[FieldName.MAX_PRICE.value][0].method == "label_value_same_line"
    assert normalized[FieldName.MAX_PRICE.value][0].normalized_value == "1000000"


def test_same_line_accepts_fullwidth_spacing_around_colon() -> None:
    facts = _facts(_document(_paragraph(0, "项目名称　：　全角空格项目")))

    assert facts.fields.project_name.resolved_value == "全角空格项目"


def test_next_line_candidate_does_not_cross_a_new_field_label() -> None:
    resolved = _facts(
        _document(
            _paragraph(0, "质量目标"),
            _paragraph(1, "合格"),
            _paragraph(2, "项目编号"),
            _paragraph(3, "PRJ-001"),
        )
    )

    assert resolved.fields.quality_target.resolved_value == "合格"
    assert resolved.fields.quality_target.candidates[0].method == "label_value_next_line"
    assert resolved.fields.project_name.status.value == "NOT_FOUND"


def test_next_line_does_not_use_a_new_label_with_an_inline_value() -> None:
    facts = _facts(
        _document(
            _paragraph(0, "项目名称"),
            _paragraph(1, "项目编号：PRJ-001"),
        )
    )

    assert facts.fields.project_name.status.value == "NOT_FOUND"
    assert facts.fields.project_number.resolved_value == "PRJ-001"


def test_keyword_window_finds_body_sentence() -> None:
    facts = _facts(
        _document(_paragraph(0, "本项目项目名称为“测试平台”，项目编号为 ABC-001。"))
    )

    assert facts.fields.project_name.status.value == "NEEDS_REVIEW"
    assert facts.fields.project_name.resolved_value is None
    assert facts.fields.project_number.status.value == "NEEDS_REVIEW"
    assert all(
        candidate.method == "keyword_window"
        for candidate in facts.fields.project_name.candidates
    )


def test_equal_sources_are_retained_and_resolved() -> None:
    facts = _facts(
        _document(
            _paragraph(0, "项目名称：测试工程"),
            _paragraph(1, "投标人须知前附表", "标题 1"),
            _table(0, [["项目名称", "测试工程"]]),
        )
    )
    fact = facts.fields.project_name

    assert fact.status.value == "RESOLVED"
    assert len(fact.candidates) >= 2
    assert all(candidate.evidence_text for candidate in fact.candidates)


def test_project_and_tender_numbers_remain_independent() -> None:
    facts = _facts(
        _document(
            _paragraph(0, "采购项目编号：PRJ-2026-001"),
            _paragraph(1, "招标编号：BID-2026-888"),
        )
    )

    assert facts.fields.project_number.resolved_value == "PRJ-2026-001"
    assert facts.fields.tender_number.resolved_value == "BID-2026-888"


def test_negative_consortium_phrase_normalizes_to_false() -> None:
    document = _document(_paragraph(0, "不接受联合体投标"))
    normalized = normalize_candidates(extract_candidates(document))

    consortium = normalized[FieldName.CONSORTIUM_ALLOWED.value]
    assert consortium
    assert consortium[0].normalized_value is False

    facts = resolve_project_facts(document, normalized)
    assert facts.fields.consortium_allowed.status.value == "NEEDS_REVIEW"
    assert facts.fields.consortium_allowed.resolved_value is None


def test_candidate_evidence_and_locator_are_present_for_resolved_fields() -> None:
    facts = _facts(_document(_paragraph(7, "项目名称：可追溯项目")))
    candidate = facts.fields.project_name.candidates[0]

    assert candidate.evidence_text
    assert candidate.locator.model_dump(mode="json") == {
        "locator_type": "docx_paragraph",
        "paragraph_index": 7,
    }
