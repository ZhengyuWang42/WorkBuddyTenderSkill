from __future__ import annotations

from tender_basic.document_models import (
    DocumentParagraph,
    DocumentStatus,
    NormalizedDocument,
    ParagraphElement,
)
from tender_basic.fact_extractor import extract_candidates
from tender_basic.fact_normalizer import (
    is_resolved_value_type_valid,
    is_value_type_valid,
    normalize_candidates,
)
from tender_basic.fact_resolver import resolve_project_facts
from tender_basic.models import (
    DocxParagraphLocator,
    FieldName,
    FactStatus,
    SemanticCandidateProposal,
    SourceType,
)
from tender_basic.semantic_candidates import (
    apply_semantic_candidate_proposals,
    build_fact_gap_packet,
)


def _document(texts: list[str]) -> NormalizedDocument:
    elements = [
        ParagraphElement(
            paragraph=DocumentParagraph(
                paragraph_index=index,
                text=text,
                locator=DocxParagraphLocator(paragraph_index=index),
            )
        )
        for index, text in enumerate(texts)
    ]
    return NormalizedDocument(
        source_file="synthetic.docx",
        source_type=SourceType.DOCX,
        status=DocumentStatus.PARSED,
        page_count=0,
        text_length=sum(len(text) for text in texts),
        elements=elements,
    )


def _resolve(document: NormalizedDocument):
    return resolve_project_facts(
        document,
        normalize_candidates(extract_candidates(document)),
    )


def test_guarantee_form_sentence_never_contaminates_amount() -> None:
    facts = _resolve(
        _document(["投标保证金的形式：本项目接受所有符合国家相关规定形式的保证金"])
    )

    assert facts.fields.bid_bond_amount.status is FactStatus.NOT_FOUND
    assert facts.fields.bid_bond_amount.resolved_value is None
    assert facts.fields.bid_bond_form.status is FactStatus.RESOLVED
    assert "形式" in str(facts.fields.bid_bond_form.resolved_value)


def test_canonical_money_and_boolean_values_remain_type_valid() -> None:
    assert is_resolved_value_type_valid(FieldName.MAX_PRICE, "3100000") is True
    assert is_resolved_value_type_valid(FieldName.BID_BOND_AMOUNT, "50000") is True
    assert is_resolved_value_type_valid(FieldName.CONSORTIUM_ALLOWED, False) is True
    assert is_value_type_valid(FieldName.MAX_PRICE, "3100000") is False
    assert is_value_type_valid(
        FieldName.BID_BOND_AMOUNT,
        "投标保证金的形式为银行转账",
    ) is False


def test_reference_time_requires_review_without_a_resolved_deadline() -> None:
    facts = _resolve(_document(["开标时间：同投标截止时间"]))

    assert facts.fields.bid_open_time.status is FactStatus.NEEDS_REVIEW
    assert facts.fields.bid_open_time.resolved_value is None


def test_reference_time_can_only_be_derived_from_a_concrete_deadline() -> None:
    facts = _resolve(
        _document(
            [
                "投标截止时间：2026年7月28日15:00",
                "开标时间：同投标截止时间",
            ]
        )
    )

    assert facts.fields.bid_open_time.status is FactStatus.RESOLVED
    assert facts.fields.bid_open_time.resolved_value == "2026-07-28 15:00"
    assert any(
        candidate.method == "derived_cross_reference"
        for candidate in facts.fields.bid_open_time.candidates
    )


def test_owner_and_agent_number_aliases_keep_ownership_independent() -> None:
    facts = _resolve(
        _document(
            [
                "招标人项目编号：OWNER-001",
                "招标代理项目编号：AGENT-888",
            ]
        )
    )

    assert facts.fields.project_number.resolved_value == "OWNER-001"
    assert facts.fields.tender_number.resolved_value == "AGENT-888"


def test_duration_quality_aliases_and_procurement_submission_separation() -> None:
    duration = _resolve(_document(["供货期：30天"]))
    quality = _resolve(_document(["供货质量：满足国家标准"]))
    procurement = _resolve(_document(["采购方式：公开招标"]))

    assert duration.fields.duration.resolved_value == "30日历天"
    assert quality.fields.quality_target.resolved_value == "满足国家标准"
    assert procurement.fields.procurement_method.resolved_value == "公开招标"
    assert procurement.fields.submission_method.status is FactStatus.NOT_FOUND


def test_labeled_multiline_value_keeps_a_split_project_title_bounded() -> None:
    document = _document(["项目名称：\n华东\n供水工程", "项目编号：PRJ-001"])
    candidates = extract_candidates(document)[FieldName.PROJECT_NAME.value]

    assert any(
        candidate.method == "labeled_multiline_value"
        and candidate.value == "华东供水工程"
        for candidate in candidates
    )


def test_standalone_title_candidate_is_limited_to_obvious_title_context() -> None:
    document = _document(["第六章 投标文件格式", "测试供水工程项目"])
    # The helper creates plain paragraphs, so give the title the same source
    # context that a normalized DOCX/PDF title receives by using a heading
    # style in a second, explicit normalized document.
    document.elements[0].paragraph.style_name = "Heading 1"
    candidates = extract_candidates(document)[FieldName.PROJECT_NAME.value]

    assert any(
        candidate.method == "standalone_title_candidate"
        and candidate.value == "测试供水工程项目"
        for candidate in candidates
    )


def test_semantic_proposal_is_evidence_bound_and_re_resolved_by_python() -> None:
    document = _document(
        [
            "本项目采购范围：测试系统采购",
            "开标时间：详见投标人须知",
            "投标保证金的形式：仅限银行转账",
        ]
    )
    baseline = _resolve(document)
    packet = build_fact_gap_packet(baseline)

    valid = SemanticCandidateProposal(
        field=FieldName.PROCUREMENT_SCOPE,
        value="测试系统采购",
        source_locator=DocxParagraphLocator(paragraph_index=0),
        evidence_text="本项目采购范围：测试系统采购",
        reason="The exact labeled source sentence is present.",
    )
    invalid_locator = {
        "field": "project_name",
        "value": "自由生成项目",
        "source_locator": {"locator_type": "docx_paragraph", "paragraph_index": 99},
        "evidence_text": "自由生成项目",
        "reason": "No source locator exists.",
    }
    invalid_evidence = {
        "field": "project_name",
        "value": "采购范围",
        "source_locator": {"locator_type": "docx_paragraph", "paragraph_index": 0},
        "evidence_text": "模型补写的证据",
        "reason": "Evidence is not in the located source.",
    }
    invalid_type = {
        "field": "bid_bond_amount",
        "value": "保证金的形式为银行转账",
        "source_locator": {"locator_type": "docx_paragraph", "paragraph_index": 2},
        "evidence_text": "投标保证金的形式：仅限银行转账",
        "reason": "A form sentence cannot become an amount.",
    }
    invalid_field = {
        "field": "bidder_company",
        "value": "虚构公司",
        "source_locator": {"locator_type": "docx_paragraph", "paragraph_index": 0},
        "evidence_text": "本项目采购范围：测试系统采购",
        "reason": "Field is outside the contract.",
    }

    reviewed, audit = apply_semantic_candidate_proposals(
        document,
        baseline,
        [valid, invalid_locator, invalid_evidence, invalid_type, invalid_field],
    )

    assert packet["allowed_fields"]
    assert len(audit["accepted"]) == 1
    assert len(audit["rejected"]) == 4
    assert audit["model_can_only_propose"] is True
    assert reviewed.fields.procurement_scope.status is FactStatus.RESOLVED
    assert reviewed.fields.procurement_scope.resolved_value == "测试系统采购"
    assert reviewed.fields.bid_bond_amount.status is FactStatus.NOT_FOUND
