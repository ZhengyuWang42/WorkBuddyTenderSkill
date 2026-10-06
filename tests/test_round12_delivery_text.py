"""Round-12: the SAVED workbook's delivery text, not the internal model.

Rounds 9-11 proved the model (exact locator equality, bid/contract-risk separation,
structural-heading fidelity).  Human review of workbook11 found the *delivered
cells* still disagreeing with those rules:

* pure contract-risk rows asked the bidder to "逐条比对响应文件对应章节";
* DR037's front-table value was indistinguishable from the general post-award
  clause, and an unrelated response-bond clause could be presented as its source;
* ``投标项目复核表!E38`` was cut inside a standard identifier ("GB50015-2") because
  the main sheet used a raw ``[:110]`` slice instead of the shared semantic clipper.

These tests read the saved/reopened XLSX through ``openpyxl`` and the delivery-text
invariants in :mod:`tender_basic.delivery_text`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tender_basic.delivery_text import (  # noqa: E402
    GENERAL_ROLE_LABEL,
    PROJECT_ROLE_LABEL,
    TWO_ROLE_ANNOUNCEMENT,
    check_contract_risk_delivery,
    check_evidence_summary_clipping,
    check_multi_source_role_display,
    mid_token_truncation,
    pre_bid_language,
    response_file_language,
    source_role_labels,
)
from tender_basic.document_models import NormalizedDocument  # noqa: E402
from tender_basic.dynamic_review import (  # noqa: E402
    build_dynamic_review_plan,
    order_review_items,
)
from tender_basic.models import ProjectFacts  # noqa: E402
from tender_basic.review_builder import CHECKLIST_START_ROW  # noqa: E402
from tender_basic.review_workbook_views import _clip  # noqa: E402
from v1_review_workbook_round12_report import BUILDS  # noqa: E402

CASE = ROOT / "acceptance/workspace/case_001"
BUILD = CASE / BUILDS["case_001"]

#: sheets whose evidence-summary cells are displayed to the reviewer, and the
#: column each one prints the summary in (mirrors the round-12 report)
EVIDENCE_COLUMNS = {
    "投标项目复核表": ("E", 9),
    "02_关键条款": ("L", 2),
    "03_资格否决与强制项": ("M", 2),
    "07_证据索引": ("D", 2),
}

pytestmark = pytest.mark.skipif(
    not (BUILD / "project_facts.json").is_file(),
    reason="round-12 CASE001 successor build is not present",
)

_ITEMS: dict[str, list] = {}


def _items(case: str) -> list:
    """The case's delivered rows, in the order the delivered sheet lists them.

    ``_build_dynamic_review_rows`` writes ``order_review_items(plan.items)``, so a
    sheet coordinate can only be mapped back to an item through that same ordering.
    The plan is expensive, so it is built once per case.
    """

    if case not in _ITEMS:
        build = ROOT / "acceptance/workspace" / case / BUILDS[case]
        document = NormalizedDocument.model_validate(
            json.loads((build / "normalized_document.json").read_text(encoding="utf-8"))
        )
        facts = ProjectFacts.model_validate(
            json.loads((build / "project_facts.json").read_text(encoding="utf-8"))
        )
        plan = build_dynamic_review_plan(document, facts)
        _ITEMS[case] = list(order_review_items(plan.items))
    return _ITEMS[case]


def _workbook(case: str):
    # not read-only: the tests address individual cells, and ReadOnlyWorksheet has
    # no ``cell()`` accessor
    return load_workbook(
        ROOT / "acceptance/workspace" / case / BUILDS[case] / "投标项目复核表.xlsx",
        data_only=True,
    )


def _legacy_text(sheet, index: int) -> str:
    return str(sheet.cell(row=CHECKLIST_START_ROW + index, column=4).value or "")


# --------------------------------------------------------------------------- #
# the invariants themselves
# --------------------------------------------------------------------------- #


def test_response_file_language_is_found_only_where_the_response_must_answer() -> None:
    assert response_file_language("③ 依据第6页逐条比对响应文件对应章节")
    assert response_file_language("核对响应文件已载明：最高限价为 3100000 元")
    assert not response_file_language("⑥ 查阅合同/项目专用条款原文：其中第11页第7.3条 供应商须知前附表")
    assert pre_bid_language("⑥ 查阅合同/项目专用条款原文：其中第11页第7.3条 供应商须知前附表")


def test_a_two_role_claim_must_deliver_both_roles() -> None:
    cell = (
        "⑥ 查阅合同/项目专用条款原文：其中第11页第7.3条 供应商须知前附表（项目专用值）；"
        "第21页 7.3 履约担保（通用/中标后条款）"
    )
    assert check_multi_source_role_display([{"item_id": "DR037", "text": cell}])[
        "multi_source_role_display_ambiguity_count"
    ] == 0
    # a half-declared pair is ambiguous
    half = "⑥ 查阅合同/项目专用条款原文：其中第11页第7.3条 供应商须知前附表（项目专用值）"
    ambiguous = check_multi_source_role_display([{"item_id": "DR037", "text": half}])
    assert ambiguous["multi_source_row_checked"] == 1
    assert ambiguous["multi_source_role_display_ambiguity_count"] == 1
    # a row that never claims two roles is out of scope
    assert check_multi_source_role_display(
        [{"item_id": "DR001", "text": "③ 依据第5页逐条比对响应文件对应章节"}]
    )["multi_source_row_checked"] == 0


def test_source_role_labels_read_the_page_and_clause_of_each_role() -> None:
    labels = source_role_labels(
        f"{TWO_ROLE_ANNOUNCEMENT}：其中第11页第7.3条 供应商须知前附表（{PROJECT_ROLE_LABEL}）；"
        f"第21页 7.3 履约担保（{GENERAL_ROLE_LABEL}）"
    )
    assert "第11页" in labels[PROJECT_ROLE_LABEL]
    assert "7.3" in labels[PROJECT_ROLE_LABEL]
    assert "第21页" in labels[GENERAL_ROLE_LABEL]
    assert "7.3履约担保" in labels[GENERAL_ROLE_LABEL].replace(" ", "")


def test_a_clip_inside_a_material_token_is_reported() -> None:
    assert mid_token_truncation("（3）《建筑给水排水设计规范》GB50015-2…") == "GB50015-2"
    assert mid_token_truncation("标准规范：GB50015-2019…") == ""
    assert mid_token_truncation("依据第3.4.2…") == "3.4.2"
    # a complete sentence may of course end with a number
    assert mid_token_truncation("最高限价为 3100000 元") == ""


def test_only_a_truncated_cell_can_be_mid_token() -> None:
    result = check_evidence_summary_clipping(
        [
            {"sheet": "02_关键条款", "cell": "L2", "text": "《室外给水设计规范》GB50013-2…"},
            # no clip mark: a cell that simply ends with a complete identifier is
            # never reported, whatever it ends with
            {"sheet": "02_关键条款", "cell": "L3", "text": "《室外给水设计规范》GB50013-2018"},
        ]
    )
    assert result["evidence_summary_cell_checked"] == 2
    assert result["mid_token_evidence_truncation_count"] == 1
    assert result["problems"][0]["cell"] == "L2"


# --------------------------------------------------------------------------- #
# the saved workbook: defect 1 -- pure contract risks stay internal
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("case", sorted(BUILDS))
def test_saved_contract_risk_rows_carry_no_response_file_language(case: str) -> None:
    items = _items(case)
    workbook = _workbook(case)
    try:
        sheet = workbook["投标项目复核表"]
        rows = [
            {
                "item_id": item.item_id,
                "sheet": "投标项目复核表",
                "cell": f"D{CHECKLIST_START_ROW + index}",
                "review_stage": item.review_stage,
                "text": _legacy_text(sheet, index),
            }
            for index, item in enumerate(items)
        ]
    finally:
        workbook.close()
    result = check_contract_risk_delivery(rows)
    assert result["contract_risk_row_checked"] > 0, case
    assert result["pure_contract_risk_response_file_language_count"] == 0, (
        case,
        result["contaminated"],
    )


def test_saved_contract_risk_rows_keep_their_pre_bid_wording() -> None:
    items = _items("case_001")
    workbook = _workbook("case_001")
    try:
        sheet = workbook["投标项目复核表"]
        texts = [
            _legacy_text(sheet, index)
            for index, item in enumerate(items)
            if item.review_stage == "CONTRACT_RISK_NOTICE"
        ]
    finally:
        workbook.close()
    assert texts
    assert all(pre_bid_language(text) for text in texts), texts


# --------------------------------------------------------------------------- #
# the saved workbook: defect 2 -- DR037's two sources
# --------------------------------------------------------------------------- #


def test_dr037_saved_cell_distinguishes_project_value_from_general_clause() -> None:
    items = _items("case_001")
    index = next(
        index for index, item in enumerate(items) if item.concern_id == "PERFORMANCE_BOND"
    )
    workbook = _workbook("case_001")
    try:
        text = _legacy_text(workbook["投标项目复核表"], index)
    finally:
        workbook.close()
    labels = source_role_labels(text)
    assert PROJECT_ROLE_LABEL in labels, text
    assert GENERAL_ROLE_LABEL in labels, text
    project = labels[PROJECT_ROLE_LABEL]
    general = labels[GENERAL_ROLE_LABEL]
    assert "第11页" in project and "7.3" in project, text
    assert "第21页" in general and "7.3履约担保" in general.replace(" ", ""), text
    # the response-bond clause belongs to a different concern and never appears here
    assert "响应保证金" not in text, text
    assert "第18页" not in text, text


# --------------------------------------------------------------------------- #
# the saved workbook: defect 3 -- one semantic clipper for every summary
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("case", sorted(BUILDS))
def test_main_sheet_evidence_uses_the_shared_semantic_clipper(case: str) -> None:
    items = _items(case)
    workbook = _workbook(case)
    try:
        sheet = workbook["投标项目复核表"]
        for index, item in enumerate(items):
            expected = (
                f"{item.source_locator} {_clip(item.source_evidence, 110)}"
                f"（源条款 {len(item.source_requirement_ids)} 条："
                f"{item.source_requirement_ids[0]}）"
            )
            actual = str(
                sheet.cell(row=CHECKLIST_START_ROW + index, column=5).value or ""
            )
            assert actual == expected, (case, item.item_id, actual, expected)
    finally:
        workbook.close()


@pytest.mark.parametrize("case", sorted(BUILDS))
def test_no_saved_evidence_summary_ends_inside_a_material_token(case: str) -> None:
    from openpyxl.utils import column_index_from_string

    workbook = _workbook(case)
    cells: list[dict[str, str]] = []
    try:
        for title, (column, first_row) in EVIDENCE_COLUMNS.items():
            if title not in workbook.sheetnames:
                continue
            sheet = workbook[title]
            index = column_index_from_string(column) - 1
            for position, row in enumerate(
                sheet.iter_rows(min_row=first_row, values_only=True), start=first_row
            ):
                if index >= len(row):
                    continue
                value = str(row[index] or "")
                if value.strip():
                    cells.append(
                        {"sheet": title, "cell": f"{column}{position}", "text": value}
                    )
    finally:
        workbook.close()
    result = check_evidence_summary_clipping(cells)
    assert result["evidence_summary_cell_checked"] > 0, case
    assert result["mid_token_evidence_truncation_count"] == 0, (case, result["problems"])
