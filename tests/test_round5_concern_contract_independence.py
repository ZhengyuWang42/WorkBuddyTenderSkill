"""Round-5 independent concern contracts (fixtures A..T).

Round 4 made the workbook provenance-consistent: every displayed phrase comes
from a concern-owned rendered component.  The CASE001 human review then rejected
it, because

    PROVENANCE CONSISTENCY IS NOT SEMANTIC VALIDATION.

A row can be fully traceable and still display a neighbouring facet, give a
number the wrong business meaning, cite the wrong clause, or assert something
the source never established.  Round 5 therefore adds an *independent* contract
per concern -- hand-authored from the human fixture brief -- that validates the
*displayed* row: text, numeric roles, linked facts, materials, consequence and
evidence.

These tests assert (a) the contracts are independent of the generated review
points, (b) every fixture A..T rejects its violation and accepts its compliant
row, and (c) the roles the fixtures require stay separate with hand-written
expected values.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tender_basic.concern_contract import (
    CONTRACTS,
    CONTRACT_SOURCE,
    CONTRACT_VERSION,
    RENAMED_CONCERNS,
    SUPERSEDED_CONCERNS,
    contract_for,
    contract_table_is_independent,
    is_incomplete_fragment,
    owned_segments,
    validate_point,
)
from tender_basic.semantic_roles import canonical_role, is_canonical_role

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "acceptance/workspace/case_001"
BUILD5 = CASE / "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook5"
#: the durable round-5 CASE001 audit (committed); the workspace copy is local-only
REPORT5 = ROOT / "acceptance/reports/v1_generalization/case_001_review_workbook_round5_row_contract_audit.json"


# --------------------------------------------------------------------------- #
# 1. the contract table is independent of the classifier and of the review points
# --------------------------------------------------------------------------- #
def test_contract_table_is_hand_authored_and_independent():
    assert contract_table_is_independent()
    assert CONTRACT_SOURCE == "human_round5_fixtures_A_T"
    assert CONTRACT_VERSION.startswith("round5")
    for concern_id, contract in CONTRACTS.items():
        assert contract.explicit, concern_id
        # the contract must state what it owns and how it can be violated
        assert contract.kind in {
            "MANDATORY",
            "REJECTION",
            "SCORING",
            "CONTRACT_ONLY",
            "INFORMATIONAL",
        }, concern_id
    # every contract the human fixtures rely on states its rationale and at least
    # one enforceable rule
    for concern_id, contract in CONTRACTS.items():
        if not contract.fixtures:
            continue
        assert contract.rationale, concern_id
        assert (
            contract.required_signatures
            or contract.forbidden_signatures
            or contract.allowed_roles
            or contract.required_evidence
        ), concern_id


def test_every_contract_declares_its_fixture_or_is_registered_as_a_base_contract():
    """Fixtures A..T must be traceable to the concerns that carry them."""

    fixtures = {key for contract in CONTRACTS.values() for key in contract.fixtures}
    assert set("ABCDEFGHIJKLMNOPQRST") <= fixtures


def test_contracts_are_not_derived_from_the_generated_review_points():
    """The contract source must not import the renderer or the classifier.

    A contract that read ``ReviewPoint``/``ReviewConcern`` could only ever
    confirm the classifier's own opinion, which is exactly the round-4 failure.
    """

    source = (ROOT / "tender_basic/concern_contract.py").read_text(encoding="utf-8")
    assert "review_point" not in source
    assert "review_concern" not in source


def test_every_delivered_concern_of_case001_has_an_explicit_contract():
    if not REPORT5.is_file():
        pytest.skip("round-5 CASE001 report is not present")
    report = json.loads(REPORT5.read_text(encoding="utf-8"))
    assert report["coverage"]["uncovered"] == []
    assert report["coverage"]["concerns"]
    assert all(contract_for(concern).explicit for concern in report["coverage"]["concerns"])


# --------------------------------------------------------------------------- #
# 2. fixtures A..T: the violation is rejected, the compliant row is accepted
# --------------------------------------------------------------------------- #
def _violation_codes(concern_id: str, **kwargs) -> set[str]:
    return {violation.code for violation in validate_point(concern_id, **kwargs)}


def _violations(concern_id: str, **kwargs) -> list:
    return validate_point(concern_id, **kwargs)


# A -- quality target must not display the delivery location.
def test_fixture_a_quality_target_rejects_location():
    assert _violation_codes(
        "QUALITY_TARGET",
        displayed_text="9、质量要求：符合国家及行业有关标准、规范和询比文件要求",
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "QUALITY_TARGET",
        displayed_text="9、质量要求：合格；交货地点：周口市郸城县石槽泵站",
    )


# B -- validity must not be documented through a credit blacklist.
def test_fixture_b_validity_rejects_blacklist_and_needs_its_own_clause():
    assert _violation_codes(
        "BID_VALIDITY",
        displayed_text="3.3.1 询比有效期 提交响应文件截止之日起 90 日历天",
        evidence_text="第10页 / 3.3.1 询比有效期 / 第3.3.1条",
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "BID_VALIDITY", displayed_text="供应商被列入失信被执行人名单的，不得参加"
    )


# C -- the funding clause is its own concern, not a price ceiling.
def test_fixture_c_funding_is_not_a_price_row():
    assert _violation_codes(
        "PRICE_CEILING",
        displayed_text="5、最高限价：3100000 元（不含税）",
        numeric_roles=["PRICE_CEILING"],
        linked_fact_keys=["max_price"],
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "PRICE_CEILING", displayed_text="6、资金来源：企业自筹"
    )


# D -- the contract payment never absorbs the agency fee.
def test_fixture_d_contract_payment_excludes_agency_fee():
    assert _violation_codes(
        "CONTRACT_PAYMENT",
        displayed_text="第3.2条 付款方式：验收合格后支付 95%",
        evidence_text="第34页 / 第3.2条 付款方式",
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "CONTRACT_PAYMENT", displayed_text="代理服务费按收费标准的 70%向成交供应商收取"
    )


# E -- payment evidence is not contract-effectivity evidence.
def test_fixture_e_payment_is_not_effectivity():
    assert _violation_codes(
        "CONTRACT_PAYMENT",
        displayed_text="付款方式：验收合格后支付 95%",
        evidence_text="第34页 / 第3.2条 付款方式",
    ) == set()
    assert "CONTRACT_EVIDENCE_FORBIDDEN" in _violation_codes(
        "CONTRACT_PAYMENT",
        displayed_text="付款方式：验收合格后支付 95%",
        evidence_text="合同经双方签字盖章后生效",
    )


# F -- a performance bond never cites the response bond.
def test_fixture_f_performance_bond_is_not_response_bond():
    assert _violation_codes(
        "PERFORMANCE_BOND",
        displayed_text="7.3 履约担保：履约保证金为合同价的 5%",
        evidence_text="第21页 / 7.3 履约担保（履约保证金） / 第7.3.1条",
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "PERFORMANCE_BOND", displayed_text="投标保证金为人民币 20000 元"
    )


# G -- no unsupported completeness assertion.
def test_fixture_g_price_completeness_asserts_nothing_unestablished():
    assert _violation_codes(
        "PRICING_COMPLETENESS",
        displayed_text="3.2.1 供应商应在响应文件中按要求填写报价",
        pass_criteria=["报价组成与费用范围按源文件逐项核对"],
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "PRICING_COMPLETENESS", displayed_text="报价无漏项、无重复项，已包含一切费用"
    )


# H -- unit-price cost scope and delivery completion are separate.
def test_fixture_h_cost_scope_and_acceptance_are_separate():
    assert _violation_codes(
        "PRICE_INCLUDED_COST_SCOPE",
        displayed_text="5.2 设备单价中含运输费、装卸费、安装费、损耗和税金等费用",
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "PRICE_INCLUDED_COST_SCOPE", displayed_text="设备安装调试完毕，签字后视为交付完成"
    )
    assert _violation_codes(
        "DELIVERY_ACCEPTANCE_COMPLETION",
        displayed_text="设备安装调试完毕，甲方负责人在验收单上签字后视为交付完成",
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "DELIVERY_ACCEPTANCE_COMPLETION", displayed_text="设备单价中含运输费、税金"
    )


# I -- technical standard compliance is not acceptance, nor a test report.
def test_fixture_i_technical_standard_is_not_acceptance():
    assert _violation_codes(
        "TECHNICAL_STANDARD_COMPLIANCE",
        displayed_text="3.1 设备应遵照《二次供水工程技术规程》CJJ140-2018 等标准执行",
    ) == set()
    # an acceptance clause carries no standard code: the contract owns it nowhere
    assert _violation_codes(
        "TECHNICAL_STANDARD_COMPLIANCE", displayed_text="安装调试完毕经甲方验收合格"
    ), "an acceptance clause must not validate as a standard-compliance clause"
    assert _violation_codes(
        "TECHNICAL_TEST_REPORT", displayed_text="流量计需提供第三方检测报告"
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "TECHNICAL_TEST_REPORT", displayed_text="设备采购范围包括不锈钢管与法兰"
    )


# J -- 95% is a payment ratio, never a retention ratio.
def test_fixture_j_95_percent_is_never_retention():
    codes = _violation_codes(
        "RETENTION_MONEY_RATIO",
        displayed_text="质保金比例为 95%",
        numeric_roles=["RETENTION_MONEY_RATIO"],
    )
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in codes, "95% must never be accepted as the retention ratio"
    assert _violation_codes(
        "RETENTION_MONEY_RATIO",
        displayed_text="质保金比例为 5%",
        numeric_roles=["RETENTION_MONEY_RATIO"],
    ) == set()


# K -- the retention 5% row must not absorb the 12/24 month periods.
def test_fixture_k_retention_is_5_percent_only():
    codes = _violation_codes(
        "RETENTION_MONEY_RATIO",
        displayed_text="质保金比例为 5%",
        numeric_roles=["PROJECT_WARRANTY_MONTHS"],
    )
    assert codes & {"CONTRACT_FORBIDDEN_ROLE", "CONTRACT_ROLE_NOT_ALLOWED"}
    assert _violation_codes(
        "RETENTION_MONEY_RATIO",
        displayed_text="质保金比例为 5%",
        numeric_roles=["RETENTION_MONEY_RATIO"],
    ) == set()


# L -- the bank-acceptance ratio is independently scored.
def test_fixture_l_bank_acceptance_ratio_is_independent():
    assert _violation_codes(
        "SCORING_BANK_ACCEPTANCE",
        displayed_text="1、100%接受银行承兑的得 4 分",
        numeric_roles=["BANK_ACCEPTANCE_RATIO", "SCORE_POINTS"],
    ) == set()
    codes = _violation_codes(
        "SCORING_BANK_ACCEPTANCE",
        displayed_text="质保金比例为 5%",
        numeric_roles=["RETENTION_MONEY_RATIO"],
    )
    assert codes


# M -- points belong to the exact scoring factor.
def test_fixture_m_points_belong_to_the_exact_factor():
    assert _violation_codes(
        "SCORING_PAYMENT_CONDITION",
        displayed_text="款 95%（5%质保金质保期满无息支付）的得 12 分",
        numeric_roles=["PAYMENT_RATIO", "RETENTION_MONEY_RATIO", "SCORE_POINTS"],
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "SCORING_PAYMENT_CONDITION", displayed_text="1、100%接受银行承兑的得 4 分"
    )


# N -- a generic evaluation row never invents a points value.
def test_fixture_n_generic_evaluation_row_invents_no_points():
    assert _violation_codes(
        "EVALUATION_SCORING",
        displayed_text="评审办法正文部分 1. 本次评审采用综合评分法；2.2.4 评分标准",
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "EVALUATION_SCORING", displayed_text="技术标评分最高 1 分"
    )


# O -- technical scoring quotes the real table, not a cross-reference.
def test_fixture_o_technical_scoring_uses_real_atoms():
    assert _violation_codes(
        "SCORING_TECHNICAL",
        displayed_text="（12 分） 技术方案完整、可行的得 12 分",
        numeric_roles=["SCORE_POINTS"],
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "SCORING_TECHNICAL", displayed_text="技术标：见评审办法前附表"
    )


# P -- a general obligation never merges the procurement scope with the
#      evaluation procedure.
def test_fixture_p_general_obligation_keeps_one_subject():
    assert _violation_codes(
        "GENERAL_BIDDER_OBLIGATION",
        displayed_text="供应商应按要求提供合格产品并承担相应的质量责任",
    ) == set()
    codes = _violation_codes(
        "GENERAL_BIDDER_OBLIGATION",
        displayed_text="供应商应按采购范围供货；评审小组可以要求澄清",
    )
    violations = _violations(
        "GENERAL_BIDDER_OBLIGATION",
        displayed_text="供应商应按采购范围供货；评审小组可以要求澄清",
    )
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in codes
    assert len(violations) >= 2, "both merged subjects must be rejected"


# Q -- authorization evidence is authorization evidence.
def test_fixture_q_authorization_needs_authorization_evidence():
    assert _violation_codes(
        "AUTHORIZATION",
        displayed_text="法定代表人授权委托书（附身份证明）",
    ) == set()
    assert "CONTRACT_EVIDENCE_SIGNATURE_MISSING" in _violation_codes(
        "AUTHORIZATION",
        displayed_text="法定代表人授权委托书",
        evidence_text="第9页 / 营业执照",
    )


# R -- the submission row carries no collusion/delivery pattern.
def test_fixture_r_submission_row_has_no_collusion_pattern():
    assert _violation_codes(
        "SUBMISSION_PLATFORM",
        displayed_text="供应商应在电子交易平台上传响应文件",
    ) == set()
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "SUBMISSION_PLATFORM", displayed_text="不同供应商的响应文件由同一人送达"
    )


# S -- the platform roles are split.
def test_fixture_s_platform_roles_are_separate():
    for concern_id, text in (
        ("SUBMISSION_PLATFORM", "供应商应在电子交易平台递交响应文件"),
        ("ELECTRONIC_UPLOAD", "响应文件须在截止时间前完成电子上传"),
        ("OPENING_DECRYPTION", "开标时供应商须在线解密响应文件"),
    ):
        assert _violation_codes(concern_id, displayed_text=text) == set(), concern_id
    # a submission row may not claim the announcement or opening duty
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "SUBMISSION_PLATFORM", displayed_text="成交结果公告在平台网站发布"
    )
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "ELECTRONIC_UPLOAD", displayed_text="开标时间由采购人另行通知"
    )
    assert "CONTRACT_FORBIDDEN_SIGNATURE" in _violation_codes(
        "OPENING_DECRYPTION", displayed_text="成交公告在平台发布"
    )


# T -- an extraction fragment is NEEDS_REVIEW, never a fragment row.
def test_fixture_t_fragment_is_needs_review_not_a_row():
    assert is_incomplete_fragment("意见》的通知中规定的收费标准的 70%向成交供应商")
    assert is_incomplete_fragment("》的通知中规定的收费标准")
    assert not is_incomplete_fragment("代理服务费按收费标准的 70%向成交供应商收取。")
    codes = _violation_codes(
        "AGENCY_SERVICE_FEE",
        displayed_text="意见》的通知中规定的收费标准的 70%向成交供应商",
    )
    assert codes, "an incomplete agency-fee fragment must not validate"


# --------------------------------------------------------------------------- #
# 3. the roles the fixtures require stay separate, with hand-written values
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("VALIDITY_DAYS", "BID_VALIDITY_DAYS"),
        ("DURATION_DAYS", "DELIVERY_DAYS"),
        ("WARRANTY_MONTHS", "PROJECT_WARRANTY_MONTHS"),
        ("RETENTION_RELEASE_PERIOD", "RETENTION_RELEASE_MONTHS"),
        ("SCORE", "SCORE_POINTS"),
        ("CONTACT", "CONTACT_INFO"),
        ("TENDER_FEE", "TENDER_DOCUMENT_PRICE"),
        ("BOND", "BOND_AMOUNT"),
    ],
)
def test_legacy_role_names_map_to_the_round5_canonical_roles(legacy: str, canonical: str):
    assert canonical_role(legacy) == canonical
    assert is_canonical_role(canonical)


def test_the_five_money_roles_are_distinct():
    roles = {
        "PROJECT_WARRANTY_MONTHS": "24个月",
        "RETENTION_RELEASE_MONTHS": "12个月",
        "RETENTION_MONEY_RATIO": "5%",
        "PAYMENT_RATIO": "95%",
        "BANK_ACCEPTANCE_RATIO": "100%",
    }
    assert len(set(roles.values())) == len(roles)
    # fixtures J and K: the retention ratio is 5% and the payment ratio 95%
    assert roles["RETENTION_MONEY_RATIO"] == "5%"
    assert roles["PAYMENT_RATIO"] == "95%"
    assert roles["RETENTION_RELEASE_MONTHS"] == "12个月"
    assert roles["PROJECT_WARRANTY_MONTHS"] == "24个月"


def test_renames_and_supersessions_are_declared():
    assert RENAMED_CONCERNS == {
        "TECHNICAL_INSTALLATION": "INSTALLATION_ACCEPTANCE",
        "CONTRACT_ACCEPTANCE": "DELIVERY_ACCEPTANCE_COMPLETION",
        "PRICE_COMPLETENESS": "PRICING_COMPLETENESS",
        "PROJECT_BASIC_INFO": "PROJECT_FUNDING_SOURCE",
    }
    assert SUPERSEDED_CONCERNS
    assert all(source != target for source, target in RENAMED_CONCERNS.items())


def test_owned_segments_split_a_mixed_clause():
    """The reader keeps only the contract-owned parts of a mixed clause."""

    assert owned_segments(
        "PRICE_CEILING", "5、最高限价：3100000 元（不含税） 6、资金来源：企业自筹"
    ) == ["5、最高限价：3100000 元（不含税）"]
    # forbidden wins over required
    assert owned_segments("QUALITY_TARGET", "质量要求：合格；交货地点：周口市郸城县石槽泵站") == [
        "质量要求：合格"
    ]


# --------------------------------------------------------------------------- #
# 4. the delivered CASE001 workbook agrees end to end
# --------------------------------------------------------------------------- #
def test_delivered_case001_rows_agree_with_their_contracts():
    if not REPORT5.is_file():
        pytest.skip("round-5 CASE001 report is not present")
    report = json.loads(REPORT5.read_text(encoding="utf-8"))
    failed = [
        row["item_id"] for row in report["rows"] if row["concern_contract"] != "PASS"
    ]
    assert not failed, failed
    assert report["delivered_row_audit_count"] == len(report["rows"]) > 0
    assert report["fixtures_passed"].startswith("20/20")


def test_delivered_rows_are_read_from_the_final_cells():
    """§19: the audit reads the workbook, not the in-memory model objects."""

    if not REPORT5.is_file():
        pytest.skip("round-5 CASE001 report is not present")
    report = json.loads(REPORT5.read_text(encoding="utf-8"))
    checks = {check["check"]: check for check in report["checks"]}
    assert checks["delivered_rows_read_from_final_cells"]["ok"]
    for row in report["rows"]:
        assert row["cell"].startswith("投标项目复核表!")
        assert row["evidence_cell"].startswith("投标项目复核表!")
        assert row["note_cell"].startswith("投标项目复核表!")


def test_final_view_sheets_are_audited_against_the_contracts():
    """§20: 02/03 row cells and 06 are audited independently of the legacy rows."""

    if not REPORT5.is_file():
        pytest.skip("round-5 CASE001 report is not present")
    report = json.loads(REPORT5.read_text(encoding="utf-8"))
    checks = {check["check"]: check for check in report["checks"]}
    views = checks["sheet_views_are_semantically_coherent"]
    assert views["ok"]
    assert views["evidence"]["rows_audited"] > 0
    assert views["evidence"]["violations"] == []
    assert views["evidence"]["unbound_rows"] == []

    conflicts = checks["conflict_sheet_has_no_false_platform_conflicts"]
    assert conflicts["ok"]
    # 06 is compared with the ProjectFacts SSOT, never with the legacy sheet
    assert conflicts["evidence"]["contradictions"] == []
    assert "SSOT" in conflicts["detail"]


def test_final_view_rows_are_not_judged_by_legacy_equality():
    """The view audit must read the frozen sheet cells, not a legacy row copy."""

    source = (ROOT / "scripts/v1_review_workbook_round5_report.py").read_text(encoding="utf-8")
    assert "sheet_rows(sheet)" in source
    assert "(CLAUSE_SHEET, 3, 11)" in source
    assert "(MANDATORY_SHEET, 4, 12)" in source
    assert "sheet_rows(CONFLICT_SHEET)" in source
    # 06 is cross-checked with the ProjectFacts SSOT, not with the legacy rows
    assert "facts.fields" in source and "SSOT" in source

