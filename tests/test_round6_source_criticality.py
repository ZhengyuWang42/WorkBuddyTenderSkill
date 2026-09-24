"""Round 6: source-visible criticality is semantic data.

The round-5 review workbook lost the source's own emphasis markers (``*`` /
``★``) and conflated three different source questions into one column.  These
tests hold the round-6 chain to the source:

``SOURCE MARKER -> TENDER-SPECIFIC SUBSTANTIVE REQUIREMENT RULE ->
CONSEQUENCE RULE -> REVIEW CRITICALITY``

Nothing here asserts case-specific wording as *production* behaviour: the
case-specific expectations are the human's own review fixtures, and every other
assertion is about the source-driven rule.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from openpyxl import load_workbook

from scripts.v1_review_workbook_round4_report import Round4Report
from tender_basic.dynamic_requirements import build_requirement_index, split_source_clauses
from tender_basic.review_concern import atomize_units
from tender_basic.source_criticality import (
    BASIS_EXPLICIT_WORDING,
    BASIS_LEGAL_RULE,
    BASIS_REFERENCE_PROPAGATION,
    BASIS_SOURCE_MARKER,
    CRITICALITY_MANDATORY,
    CRITICALITY_ORDINARY,
    CRITICALITY_SUBSTANTIVE,
    CRITICALITY_SUBSTANTIVE_REJECTION,
    MANDATORY_TYPE_PROOF,
    MANDATORY_TYPE_STARRED,
    REJECTION_DERIVED,
    REJECTION_EXPLICIT,
    SEMANTICS_PROOF,
    SEMANTICS_SCORING,
    SEMANTICS_SUBSTANTIVE,
    SEMANTICS_UNESTABLISHED,
    VISIBLE_MARKER,
    build_criticality_index,
    discover_marker_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
CASE_001 = ROOT / "acceptance/workspace/case_001"
BUILD6 = CASE_001 / "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook6"
WORKBOOK = BUILD6 / "投标项目复核表.xlsx"
AUDIT = {
    case: ROOT / f"acceptance/reports/v1_generalization/review_workbook_round6_criticality_audit_{case}.json"
    for case in ("case_001", "case_002", "case_003")
}
MANDATORY_SHEET = "03_资格否决与强制项"
DELIVERED_SHEET = "投标项目复核表"

pytestmark = pytest.mark.skipif(
    not WORKBOOK.exists(),
    reason="the round-6 review workbook has not been built in this workspace",
)


@pytest.fixture(scope="module")
def report() -> Round4Report:
    return Round4Report(BUILD6, "case_001")


@pytest.fixture(scope="module")
def index(report: Round4Report):
    return report.plan.criticality


@pytest.fixture(scope="module")
def atoms(report: Round4Report):
    return atomize_units(list(report.plan.index.units))


def _mandatory_rows() -> list[dict]:
    workbook = load_workbook(WORKBOOK, data_only=True, read_only=True)
    try:
        sheet = workbook[MANDATORY_SHEET]
        headers = [str(cell.value or "").strip() for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
        rows = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not any(value not in (None, "") for value in row):
                continue
            rows.append({headers[i]: row[i] for i in range(min(len(headers), len(row)))})
        return rows
    finally:
        workbook.close()


# -- raw marker preservation ------------------------------------------------ #


def test_leading_source_marker_survives_clause_splitting():
    """``*1.4.5 供货期 …`` must not lose its ``*`` on the way to a clause."""

    chunks = split_source_clauses("*1.4.5 供货期 签订合同后 30 日历天。")
    assert chunks, "a marked clause must produce a clause chunk"
    assert any(chunk.startswith("*") for chunk in chunks)
    assert any("供货期" in chunk for chunk in chunks)


def test_marker_vocabulary_is_discovered_from_the_document(index):
    """``*`` in CASE001, ``★`` in CASE002, ``*`` in CASE003 -- discovered, not assumed."""

    case_001 = json.loads(AUDIT["case_001"].read_text(encoding="utf-8"))
    case_002 = json.loads(AUDIT["case_002"].read_text(encoding="utf-8"))
    assert case_001["criticality_model"]["marker_vocabulary"] == ["*"]
    assert case_002["criticality_model"]["marker_vocabulary"] == ["★"]
    assert {record.raw_marker for record in index.markers} == {"*"}


def test_every_source_marker_is_accounted_for(report: Round4Report):
    """No marker is lost: each one reaches an atom, a row or a kept background clause."""

    for case, path in AUDIT.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["counts"]["marker_lost_count"] == 0, case
        unaccounted = [
            record
            for record in data["marker_records"]
            if record["status"] not in {"DELIVERED_REVIEW_ROW", "NON_BIDDER_ACTIONABLE_ROW"}
        ]
        assert unaccounted == [], case


def test_marker_is_not_invented_where_the_source_has_none(report: Round4Report):
    """Every starred row is backed by a marker atom; no row is starred by opinion."""

    starred = {
        str(row.get("requirement_id"))
        for row in _mandatory_rows()
        if str(row.get("★") or "").strip() == "★"
    }
    assert starred
    items = {item.item_id: item for item in report.items}
    for item_id in starred:
        assert items[item_id].marker_present, item_id
        assert items[item_id].raw_source_markers, item_id


def test_normalised_visible_marker_is_star():
    """The reviewer-facing normalisation is ``★``; the raw character is kept."""

    assert VISIBLE_MARKER == "★"
    rows = [row for row in _mandatory_rows() if str(row.get("★") or "").strip()]
    assert rows
    assert all(str(row["★"]).strip() == "★" for row in rows)
    raw = [str(row.get("源标记") or "") for row in rows]
    assert all("原始标记" in value for value in raw)
    assert all("★" not in value.split("（")[0] or "*" not in value for value in raw)


# -- the three dimensions are independent ----------------------------------- #


def test_marker_substantive_and_rejection_are_separate_dimensions(report: Round4Report):
    marked = [item for item in report.items if item.marker_present]
    substantive = [item for item in report.items if item.substantive_requirement]
    rejection = [item for item in report.items if item.rejection_consequence]
    assert marked and substantive and rejection
    # a marked requirement is not automatically substantive, and vice versa
    assert all(
        item.rejection_consequence and item.rejection_basis_atom_ids
        for item in rejection
    )
    assert all(item.substantive_basis_atom_ids for item in substantive)


def test_star_and_veto_columns_are_not_aliases():
    starred = {
        str(row.get("requirement_id"))
        for row in _mandatory_rows()
        if str(row.get("★") or "").strip() == "★"
    }
    vetoed = {
        str(row.get("requirement_id"))
        for row in _mandatory_rows()
        if str(row.get("否决性") or "").strip() == "是"
    }
    assert starred and vetoed
    assert starred != vetoed


def test_reference_children_are_substantive_without_being_starred(report: Round4Report):
    """Propagation must not duplicate the parent's ★ on the child rows."""

    propagated = [
        item
        for item in report.items
        if item.substantive_basis_kind == BASIS_REFERENCE_PROPAGATION
    ]
    assert propagated
    for item in propagated:
        assert not item.marker_present, item.item_id
        assert MANDATORY_TYPE_STARRED not in item.mandatory_types, item.item_id
        assert item.reference_target, item.item_id


def test_marker_is_never_a_rejection_shortcut(index):
    """No rule maps a marker straight to a rejection consequence."""

    marker_rules = [rule for rule in index.substantive_rules if rule.markers]
    assert marker_rules
    assert all(rule.kind == BASIS_SOURCE_MARKER for rule in marker_rules)
    for rule in marker_rules:
        assert rule.governing_clause or rule.semantics != SEMANTICS_UNESTABLISHED
        # the rule itself carries no consequence wording
        assert not re.search(r"否决|废标|无效", rule.governing_text or "") or rule.kind == BASIS_SOURCE_MARKER


def test_substantive_basis_kinds_are_source_backed(report: Round4Report):
    allowed = {
        BASIS_SOURCE_MARKER,
        BASIS_EXPLICIT_WORDING,
        BASIS_LEGAL_RULE,
        BASIS_REFERENCE_PROPAGATION,
    }
    for item in report.items:
        if item.substantive_requirement:
            assert item.substantive_basis_kind in allowed, item.item_id
            assert item.substantive_basis_atom_ids, item.item_id


# -- marker semantics ------------------------------------------------------- #


def test_marker_meaning_comes_from_the_document():
    """CASE002's ★ means "supply the proof", not "substantive requirement"."""

    case_002 = json.loads(AUDIT["case_002"].read_text(encoding="utf-8"))
    rules = [rule for rule in case_002["criticality_model"]["substantive_rules"] if rule["markers"]]
    assert rules
    assert all(rule["semantics"] == SEMANTICS_PROOF for rule in rules)
    marked_rows = [row for row in case_002["row_audit"] if row["marker_present"]]
    assert marked_rows
    for row in marked_rows:
        assert row["marker_semantics"] == SEMANTICS_PROOF
        assert row["substantive_requirement"] is False
        assert row["rejection_consequence"] is False
        assert row["mandatory_types"] == [MANDATORY_TYPE_PROOF]
        assert str(row["cell"]["★"]).strip() == "★"
        assert str(row["cell"]["否决性"] or "").strip() in {"", "否"}


def test_case_001_marker_means_substantive(index):
    rule = next(rule for rule in index.substantive_rules if rule.markers)
    assert rule.semantics == SEMANTICS_SUBSTANTIVE
    assert rule.governing_clause
    assert "实质性要求" in rule.governing_text


def test_semantics_vocabulary_is_source_derived():
    assert SEMANTICS_SUBSTANTIVE and SEMANTICS_PROOF and SEMANTICS_SCORING
    assert SEMANTICS_UNESTABLISHED not in {
        SEMANTICS_SUBSTANTIVE,
        SEMANTICS_PROOF,
        SEMANTICS_SCORING,
    }


# -- consequence rules ------------------------------------------------------ #


def test_rejection_consequences_trace_to_consequence_clauses(report: Round4Report):
    explicit = [item for item in report.items if item.rejection_kind == REJECTION_EXPLICIT]
    derived = [item for item in report.items if item.rejection_kind == REJECTION_DERIVED]
    assert explicit
    for item in [*explicit, *derived]:
        assert item.rejection_basis_atom_ids, item.item_id
    # derived rejections only ever attach to substantive requirements
    for item in derived:
        assert item.substantive_requirement, item.item_id


def test_no_invented_one_vote_veto(report: Round4Report):
    for item in report.items:
        assert "一票否决" not in (item.criticality_reason or "")
        assert "一票否决" not in (item.criticality_level or "")
    for row in _mandatory_rows():
        for column in ("强制性类型", "否决依据", "实质性依据"):
            assert "一票否决" not in str(row.get(column) or "")


# -- rendered workbook ------------------------------------------------------ #


def test_every_source_marked_row_shows_a_star(report: Round4Report):
    starred = {
        str(row.get("requirement_id"))
        for row in _mandatory_rows()
        if str(row.get("★") or "").strip() == "★"
    }
    missing = [
        item.item_id
        for item in report.items
        if item.marker_present and item.item_id not in starred
    ]
    assert missing == []


def test_mandatory_sheet_keeps_the_original_columns_and_appends_the_basis():
    rows = _mandatory_rows()
    headers = list(rows[0].keys())
    for column in ("★", "否决性", "强制性类型", "源标记", "实质性依据", "否决依据"):
        assert column in headers
    for row in rows:
        if str(row.get("★") or "").strip() == "★":
            assert str(row.get("源标记") or "").strip(), row.get("requirement_id")
        if "SUBSTANTIVE" in str(row.get("强制性类型") or ""):
            assert str(row.get("实质性依据") or "").strip(), row.get("requirement_id")
        if str(row.get("否决性") or "").strip() == "是":
            assert str(row.get("否决依据") or "").strip(), row.get("requirement_id")


def test_delivered_cell_prefix_is_visible_and_compiles_with_the_contract(report: Round4Report):
    """The prefix is part of the cell, and the round-5 contract parser skips it."""

    workbook = load_workbook(WORKBOOK, data_only=True, read_only=True)
    try:
        sheet = workbook[DELIVERED_SHEET]
        headers = [str(cell.value or "").strip() for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
        column = headers.index("复核要点") if "复核要点" in headers else 3
        texts = [
            str(row[column] or "")
            for row in sheet.iter_rows(min_row=10, values_only=True)
        ]
    finally:
        workbook.close()
    marked = [
        text for text in texts if text.startswith("【") and "实质性要求" in text.split("】")[0]
    ]
    assert marked, "marked rows must carry a visible criticality note"
    assert any("★实质性要求" in text.split("】")[0] for text in marked)


def test_dashboard_reports_three_separate_dimensions():
    workbook = load_workbook(WORKBOOK, data_only=False, read_only=True)
    try:
        sheet = workbook["00_复核总览"]
        labels = {
            str(row[0]): str(row[1])
            for row in sheet.iter_rows(values_only=True)
            if row and row[0] and row[1]
        }
    finally:
        workbook.close()
    assert "源标记条款数（带★）" in labels
    assert "实质性要求数（源依据）" in labels
    assert "明示或可证明否决项数" in labels
    assert not [label for label in labels if "★/一票否决" in label]
    assert labels["源标记条款数（带★）"].startswith("=")
    assert labels["实质性要求数（源依据）"].startswith("=")


# -- reviewer-facing audit -------------------------------------------------- #


def test_audit_records_the_full_chain_per_row():
    data = json.loads(AUDIT["case_001"].read_text(encoding="utf-8"))
    assert data["verdict"] == "PASS"
    assert data["counts"]["marker_lost_count"] == 0
    assert data["row_audit"]
    for row in data["row_audit"]:
        if not (row["marker_present"] or row["substantive_requirement"]):
            continue
        assert row["source_atom_ids"], row["item_id"]
        assert row["concern_id"], row["item_id"]
        assert row["criticality_level"] in {
            CRITICALITY_SUBSTANTIVE,
            CRITICALITY_SUBSTANTIVE_REJECTION,
            CRITICALITY_MANDATORY,
            CRITICALITY_ORDINARY,
        }
        assert "→" not in row["criticality_reason"]


def test_coverage_records_have_no_uncovered_substantive_requirement():
    data = json.loads(AUDIT["case_001"].read_text(encoding="utf-8"))
    uncovered = [row for row in data["coverage_records"] if row["coverage"] == "UNCOVERED"]
    assert uncovered == []
