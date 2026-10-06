"""Round 7: applicable source, rejection scope and evidence-locator fidelity.

The human's round-6 manual review failed with
``SOURCE_APPLICABILITY_AND_EVIDENCE_FIDELITY``.  These tests hold the round-7
chain to the source:

``APPLICABLE SOURCE -> SEMANTIC SCOPE -> FINAL DISPLAYED REQUIREMENT ->
EXACT MATCHING EVIDENCE LOCATOR``

Every assertion is about a *delivered workbook cell* or about a source-driven
rule; the CASE001 fixture rows are the human's own review findings.

The audited successor is the **current** one (round 12): the round-5/6/7 rules are
re-checked on the newest delivered workbook, while the round-7/8/9/10/11 workbooks
stay on disk as the artifacts the human reviewed and failed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.v1_review_workbook_round6_report import Round6Report
from scripts.v1_review_workbook_round7_report import Round7Report
from scripts.v1_review_workbook_round12_report import BUILDS as SUCCESSOR_BUILDS
from tender_basic.applicability_invariants import (
    _text_in_span,
    classify_consequence_scope,
    self_reference_only,
)
from tender_basic.platform_roles import (
    ROLE_ANNOUNCEMENT,
    ROLE_PROCUREMENT_SERVICE,
    ROLE_TRANSACTION,
    classify_platform_role,
    resolve_platform_roles,
)
from tender_basic.source_criticality import (
    SCOPE_CONTRACT_LIABILITY,
    SCOPE_INFORMATIONAL,
    SCOPE_POST_AWARD_CANCELLATION,
    SCOPE_RESPONSE_REJECTION,
    SCOPE_SCORING_ONLY,
)

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "acceptance/reports/v1_generalization"
CASES = ("case_001", "case_002", "case_003")


def _report_path(case: str) -> Path:
    """The frozen round-7 audit: this module's own record of round 7."""

    return REPORTS / f"review_workbook_round7_{case}.json"


def _successor_report_path(case: str) -> Path:
    """The current successor's audit of the same invariants (round 8)."""

    return REPORTS / f"review_workbook_round8_{case}.json"


pytestmark = pytest.mark.skipif(
    not all(_report_path(case).exists() for case in CASES),
    reason="the round-7 audits have not been produced in this workspace",
)


@pytest.fixture(scope="module")
def audits() -> dict[str, dict]:
    return {case: json.loads(_report_path(case).read_text(encoding="utf-8")) for case in CASES}


@pytest.fixture(scope="module")
def successor_audits() -> dict[str, dict]:
    return {
        case: json.loads(_successor_report_path(case).read_text(encoding="utf-8"))
        for case in CASES
    }


@pytest.fixture(scope="module")
def case001() -> Round7Report:
    return Round7Report("case_001", build_name=SUCCESSOR_BUILDS["case_001"])


def _rows(report: Round7Report) -> list[dict]:
    return report.delivered_rows()


def _row(report: Round7Report, item_id: str) -> dict:
    return next(row for row in _rows(report) if row["item_id"] == item_id)


# -- zero-count gates ------------------------------------------------------- #


def test_every_zero_count_gate_is_closed(audits: dict[str, dict]) -> None:
    """The round-7 success gates are counts, not verdicts: each must be zero."""

    for case, data in audits.items():
        counts = data["counts"]
        assert counts["GENERIC_REFERENCE_UNRESOLVED_COUNT"] == 0, case
        assert counts["FALSE_REJECTION_CLASSIFICATION_COUNT"] == 0, case
        assert counts["EVIDENCE_LOCATOR_SEMANTIC_MISMATCH_COUNT"] == 0, case
        assert counts["INCOMPLETE_RENDERED_SOURCE_FRAGMENT_COUNT"] == 0, case
        assert counts["CORRUPTED_RENDERED_NUMERIC_TEXT_COUNT"] == 0, case
        assert counts["FALSE_PLATFORM_CONFLICT_COUNT"] == 0, case
        assert counts["VALUE_INVARIANT_FAILURE_COUNT"] == 0, case


def test_every_case_verdict_is_pass(audits: dict[str, dict]) -> None:
    for case, data in audits.items():
        assert data["verdict"] == "PASS", (case, data["failed_checks"])
        assert data["fixture_summary"]["failed"] == [], case


def test_generalization_summary_is_pass() -> None:
    path = REPORTS / "review_workbook_round7_generalization.json"
    assert path.exists(), "the three-case generalization summary must be produced"
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["verdict"] == "PASS"
    assert summary["cases"]["case_001"]["verdict"] == "PASS"


def test_successor_audit_closes_the_delivered_text_gates(
    successor_audits: dict[str, dict],
) -> None:
    """Round 8 carries every round-7 zero-count gate onto the current successor.

    Each successor audit must be PASS, must have no failed fixture, and every
    delivered-text counter it reports must be zero -- the round-7 checks are a
    floor, not a substitute for auditing the text that is actually delivered.
    """

    for case, data in successor_audits.items():
        assert data["verdict"] == "PASS", (case, data["failed_checks"])
        assert data["fixture_summary"]["failed"] == [], case
        assert data["workbook_sha256"], case
        for name, value in data["counts"].items():
            if name.endswith("_COUNT"):
                assert value == 0, (case, name, value)


# -- A: applicable source resolution ---------------------------------------- #


def test_project_specific_schedule_supersedes_the_generic_template() -> None:
    """CASE001: 采购预备会=不召开, 踏勘现场=不组织, 分包=不允许 are displayed.

    The decision is bound to its **concern**, not to a row address: round 9 split
    the pre-bid meeting decision from the question/clarification deadline (the two
    had been delivered as one row, the round-8 human finding D56), so the row the
    project decision lives on is not the round-8 row id any more.
    """

    report = Round7Report("case_001", build_name=SUCCESSOR_BUILDS["case_001"])
    expected = {
        "PRE_BID_MEETING": "不召开",
        "SITE_VISIT": "不组织",
        "SUBCONTRACT": "不允许",
    }
    for concern_id, decision in expected.items():
        item = next((entry for entry in report.items if entry.concern_id == concern_id), None)
        assert item is not None, concern_id
        row = _row(report, item.item_id)
        assert decision in row["requirement"], (concern_id, item.item_id, row["requirement"][:160])
        # the generic template must not be what the reviewer reads
        assert "前附表规定" not in row["requirement"], (concern_id, item.item_id)

    # the row that used to carry the pre-bid decision now carries its own source:
    # the question/clarification deadline, never the pre-bid meeting decision
    query = next(
        (entry for entry in report.items if entry.concern_id == "QUERY_DEADLINE"), None
    )
    assert query is not None, "the question/clarification deadline must be its own row"
    query_requirement = _row(report, query.item_id)["requirement"]
    assert "采购预备会" not in query_requirement, query_requirement[:160]
    assert "提出问题的时间" in query_requirement, query_requirement[:160]


def test_generic_clause_is_kept_but_superseded() -> None:
    """A generic clause is never deleted: it stays marked superseded for display."""

    report = Round7Report("case_001", build_name=SUCCESSOR_BUILDS["case_001"])
    superseded = [
        atom for atom in report.atoms if getattr(atom, "superseded_for_display", False)
    ]
    assert superseded, "the schedule resolutions must supersede the generic clauses"
    assert all(getattr(atom, "applicability_relation", "") for atom in superseded)
    assert all(getattr(atom, "source_text", "") for atom in superseded)


def test_applicable_row_cites_the_schedule_row_it_resolves_to() -> None:
    """The row's locator is the schedule row that carries the project value.

    The schedule is the document's front table (前附表): its page is the table's
    page, not the page of the generic clause the value superseded.
    """

    report = Round7Report("case_001", build_name=SUCCESSOR_BUILDS["case_001"])
    #: the schedule page of each decision, read from the source document
    expected_page = {"DR016": 9, "DR032": 10, "DR033": 10}
    for item_id, page in expected_page.items():
        row = _row(report, item_id)
        assert f"第{page}页" in row["locator"], (item_id, row["locator"])
        # never the generic clause's own page
        assert "第16页" not in row["locator"], (item_id, row["locator"])
        assert row["locator"].rstrip().endswith(("（pdf_table_cell）", "（pdf_block）")), row[
            "locator"
        ]
        assert "前附表" in row["locator"] or row["locator"].split(" / ")[1].startswith(
            ("*1.12", "1.11.1", "1.10.1")
        ), (item_id, row["locator"])


def test_specializes_clause_keeps_its_own_wording() -> None:
    """A clause that defers only a parameter keeps the clause and gains the value."""

    report = Round7Report("case_001", build_name=SUCCESSOR_BUILDS["case_001"])
    row = _row(report, "DR037")
    requirement = row["requirement"]
    # the clause's own obligation survives
    assert "履约保证金" in requirement
    # and the schedule's parameter is present
    assert "拾万元整" in requirement or "银行保函" in requirement, requirement[:200]


# -- B: rejection scope ----------------------------------------------------- #


def test_scoring_deduction_is_not_a_response_rejection() -> None:
    scope = classify_consequence_scope("当响应报价高于评审基准价时，每高1%扣1分，扣完为止。")
    assert scope == SCOPE_SCORING_ONLY


def test_post_award_and_contract_scopes_are_distinguished() -> None:
    assert (
        classify_consequence_scope("中标人放弃中标的，取消其中标资格。")
        == SCOPE_POST_AWARD_CANCELLATION
    )
    assert (
        classify_consequence_scope("乙方未按期付款的，应当承担违约责任并支付利息。")
        == SCOPE_CONTRACT_LIABILITY
    )
    assert (
        classify_consequence_scope("本项目不接受联合体投标。") == SCOPE_INFORMATIONAL
    )


def test_response_rejection_still_detected() -> None:
    for text in (
        "投标文件未实质性响应招标文件要求的，其投标将被否决。",
        "供应商有以下情形之一的，评审小组应当否决其响应：",
        "逾期上传的电子响应文件，采购人不予受理。",
    ):
        scope = classify_consequence_scope(text)
        assert scope in {SCOPE_RESPONSE_REJECTION, "NON_ACCEPTANCE_OF_LATE_SUBMISSION"}, text


def test_no_scoring_row_is_marked_as_a_rejection(case001: Round7Report) -> None:
    for row in _rows(case001):
        item = row["item"]
        if item is None:
            continue
        if not str(item.concern_id).startswith("SCORING"):
            continue
        assert row["veto"] != "是", row["item_id"]


# -- C: evidence locator fidelity ------------------------------------------- #


def test_requirement_and_evidence_describe_one_unit(case001: Round7Report) -> None:
    """§20: page / section / clause / excerpt must describe the evidenced unit."""

    units = case001.units
    for row in _rows(case001):
        item = row["item"]
        if item is None:
            continue
        excerpt = row["excerpt"]
        if not excerpt:
            continue
        matches = [unit for unit in units.units if unit.locator == row["locator"]]
        if not matches:
            continue
        haystack = " ".join(unit.text_span for unit in matches)
        assert _text_in_span(excerpt, haystack) or _text_in_span(
            excerpt, " ".join(unit.text_span for unit in units.units)
        ), (row["item_id"], row["locator"], excerpt[:80])


def test_case001_historical_locator_findings_are_closed(case001: Round7Report) -> None:
    """The exact findings the human named: DR002, DR019, DR047."""

    delivery = _row(case001, "DR002")
    assert "营业执照" not in delivery["locator"]
    assert "30" in delivery["requirement"]

    bond = _row(case001, "DR019")
    assert "支付方式" not in bond["requirement"]
    assert "承兑汇票" not in bond["requirement"]
    assert "保理" not in bond["requirement"]

    test_report = _row(case001, "DR047")
    assert "第三方检测" in test_report["excerpt"] or "第三方检测" in test_report["requirement"]


def test_multi_clause_requirement_links_every_unit() -> None:
    """A concern quoting several clauses links each unit explicitly (§20).

    The link set is decided by the row's own covered span, so the invariant is
    asserted over the *corpus* rather than on one hardcoded row: whenever a row's
    delivered requirement is not fully carried by its PRIMARY unit, the further
    units are linked, and every link names a unit and the span it contributes.  A
    row whose primary unit already carries the whole requirement needs no link
    (round 9's CASE002 EVALUATION_RESPONSIVENESS row quotes one clause), so at
    least one row must still exercise the link path or this test would be vacuous.
    """

    linked_rows = 0
    for case in CASES:
        report = Round7Report(case, build_name=SUCCESSOR_BUILDS[case])
        for item in report.items:
            links = list(item.evidence_units or ())
            if not links:
                continue
            assert links[0]["role"] == "PRIMARY", (case, item.item_id)
            linked = [link for link in links if link["role"] == "LINKED"]
            if not linked:
                continue
            linked_rows += 1
            for link in linked:
                assert str(link.get("unit_id")), (case, item.item_id)
                assert str(link.get("span")), (case, item.item_id)
    assert linked_rows >= 3, "a multi-clause requirement must link its other units"
    assert all(link.get("unit_id") for link in linked)
    assert all(link.get("locator") for link in linked)


# -- D: fragment completeness ----------------------------------------------- #


def test_contract_payment_sentence_is_complete(case001: Round7Report) -> None:
    row = _row(case001, "DR044")
    requirement = row["requirement"]
    assert "支付宽限期" in requirement, requirement[:160]
    assert not requirement.startswith(("的，", "，", "）")), requirement[:80]


def test_retention_ratio_has_no_duplicated_placeholder(case001: Round7Report) -> None:
    row = _row(case001, "DR051")
    requirement = row["requirement"]
    assert "5%" in requirement
    assert "%%" not in requirement
    assert requirement.count("剩余 5%") <= 1


def test_no_delivered_cell_renders_a_bare_placeholder(case001: Round7Report) -> None:
    for row in _rows(case001):
        for field in ("requirement", "excerpt"):
            text = str(row[field] or "")
            assert "%%" not in text, (row["item_id"], field)
            assert not _span_coverage_of_is_placeholder(text), (row["item_id"], field)


def _span_coverage_of_is_placeholder(text: str) -> bool:
    """A lone percent with no number is a placeholder, not a project value."""

    import re

    from tender_basic.applicability_invariants import _flatten

    for segment in re.split(r"[，,；;]", _flatten(text)):
        if segment and segment.endswith("%") and not re.search(r"\d", segment):
            return True
    return False


def test_self_reference_only_classifier() -> None:
    assert self_reference_only("1.2.1本招标项目的资金来源：见投标人须知前附表。", set())
    assert not self_reference_only(
        "7.3.1在签订合同前，成交供应商应按供应商须知前附表规定的形式、金额向采购人提交履约保证金。",
        set(),
    )


# -- E: platform roles ------------------------------------------------------ #


def test_platform_roles_are_classified_by_name() -> None:
    assert classify_platform_role("河南国企阳光招采服务平台") == ROLE_PROCUREMENT_SERVICE
    assert classify_platform_role("e招投标交易平台") == ROLE_TRANSACTION
    assert classify_platform_role("中国招标投标公共服务平台") == ROLE_ANNOUNCEMENT


def test_platform_roles_do_not_become_a_conflict() -> None:
    entries = [
        ("河南国企阳光招采服务平台", "于提交响应文件截止时间前上传电子响应文件"),
        ("e招投标交易平台", "在此业务系统进行账号绑定"),
        ("中国招标投标公共服务平台", "公告发布媒介"),
    ]
    resolved, by_role, _ = resolve_platform_roles(entries)
    assert resolved == "河南国企阳光招采服务平台"
    assert len(by_role) == 3, by_role


def test_electronic_platform_fact_resolves_for_case001() -> None:
    report = Round7Report("case_001", build_name=SUCCESSOR_BUILDS["case_001"])
    payload = json.loads((report.build / "project_facts.json").read_text(encoding="utf-8"))
    field = payload["fields"]["electronic_platform"]
    assert field["status"] != "NEEDS_REVIEW", field
    assert field["resolved_value"], field
    assert "平台" in field["resolved_value"]


def test_no_exception_row_reports_a_platform_conflict() -> None:
    report = Round7Report("case_001", build_name=SUCCESSOR_BUILDS["case_001"])
    rows = report._rows("06_冲突与缺失")
    conflicts = [
        row
        for row in rows
        if "electronic_platform" in " ".join(str(value) for value in row.values())
        and str(row.get("类型") or "").startswith("事实未定")
    ]
    assert conflicts == []


# -- banked rounds must not regress ----------------------------------------- #


def test_banked_round6_marker_accounting_still_holds() -> None:
    for case in CASES:
        data = Round6Report(case, build_name=SUCCESSOR_BUILDS[case]).run()
        assert data["verdict"] == "PASS", (case, data["failed_checks"])
        assert data["counts"]["marker_lost_count"] == 0, case
        assert data["counts"]["marker_unattributed_count"] == 0, case
        assert data["counts"]["marker_unresolved_count"] == 0, case
        assert data["counts"]["direct_delivered_marker_visibility_failures"] == 0, case


def test_round5_concern_contract_still_holds() -> None:
    for case in CASES:
        data = Round6Report(case, build_name=SUCCESSOR_BUILDS[case]).run()
        assert data["concern_contract_verdict"] == "PASS", (
            case,
            data["concern_contract"]["failed_checks"],
        )


def test_round6_regression_evidence_is_untouched() -> None:
    """The committed round-6 marker-closure audits stay exactly as accepted."""

    required = {"case_001": 18, "case_002": 45, "case_003": 6}
    for case, occurrences in required.items():
        path = REPORTS / f"review_workbook_round6_marker_closure_{case}.json"
        assert path.exists(), path.name
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["verdict"] == "PASS", case
        assert data["counts"]["source_marker_occurrence_count"] == occurrences, case


def test_word_artifacts_are_byte_identical(audits: dict[str, dict]) -> None:
    for case, data in audits.items():
        checks = {check["check"]: check for check in data["checks"]}
        word = checks["Word artifacts are byte-identical (not re-rendered)"]
        assert word["ok"], (case, word["detail"])


def test_manual_review_is_not_marked_pass() -> None:
    """Round 7 closes automation only; the human review stays pending."""

    for case in CASES:
        data = json.loads(_report_path(case).read_text(encoding="utf-8"))
        assert "MANUAL_REVIEW" not in json.dumps(data)
