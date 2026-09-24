"""Round-6 closure: source-marker fidelity is closed from the discovery universe.

The initial round-6 result was invalidated by two proven defects:

* the dashboard's substantive-requirement counter summed four exact-match
  ``COUNTIF`` terms against a column that stores "；"-joined multi-values, and
* the marker-fidelity audit iterated only the atoms that already claimed a
  marker, so a marker that was discovered but attributed to no atom was
  invisible to it.

These tests hold the closure to the source: every *discovered* marker occurrence
must end in a disposition, the dashboard counters must equal an independent
recount, and the counted row/occurrence metrics stay three separate numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from scripts.v1_review_workbook_round6_report import Round6Report
from tender_basic.source_criticality import (
    COVERAGE_KIND_DIRECT_DELIVERED,
    COVERAGE_KIND_REFERENCE_PARENT,
    COVERAGE_KIND_UNRESOLVED,
    MIN_OCCURRENCE_FRAGMENT,
    OCCURRENCE_IDENTITY_MIN,
    _same_marked_identity,
    discover_marker_occurrences,
    duplicate_marker_record_count,
    raw_marker_discovery_count,
)

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "acceptance/reports/v1_generalization"
CASES = ("case_001", "case_002", "case_003")
BUILDS = {
    "case_001": (
        ROOT
        / "acceptance/workspace/case_001"
        / "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook6_marker_closure"
    ),
    "case_002": (
        ROOT / "acceptance/workspace/case_002" / "v1_round4_closure8_review_workbook6_marker_closure"
    ),
    "case_003": (
        ROOT / "acceptance/workspace/case_003" / "v1_round4_closure8_review_workbook6_marker_closure"
    ),
}
INITIAL_BUILDS = {
    "case_001": (
        ROOT
        / "acceptance/workspace/case_001"
        / "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook6"
    ),
    "case_002": ROOT / "acceptance/workspace/case_002" / "v1_round4_closure8_review_workbook6",
    "case_003": ROOT / "acceptance/workspace/case_003" / "v1_round4_closure8_review_workbook6",
}
MANDATORY_SHEET = "03_资格否决与强制项"

pytestmark = pytest.mark.skipif(
    not all((REPORTS / f"review_workbook_round6_marker_closure_{case}.json").exists() for case in CASES),
    reason="the round-6 marker-closure audits have not been produced in this workspace",
)


def closure(case: str) -> dict:
    return json.loads(
        (REPORTS / f"review_workbook_round6_marker_closure_{case}.json").read_text(
            encoding="utf-8"
        )
    )


def ledger(case: str) -> list[dict]:
    return closure(case)["marker_records"]


def mandatory_rows(case: str) -> dict[str, dict]:
    workbook = load_workbook(BUILDS[case] / "投标项目复核表.xlsx", data_only=True, read_only=True)
    try:
        sheet = workbook[MANDATORY_SHEET]
        headers = [
            str(cell.value or "").strip() for cell in next(sheet.iter_rows(min_row=1, max_row=1))
        ]
        rows = {}
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not any(value not in (None, "") for value in row):
                continue
            record = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
            rows[str(record.get("requirement_id"))] = record
        return rows
    finally:
        workbook.close()


def stub_document(blocks: dict[int, list[str]], tables: list | None = None) -> SimpleNamespace:
    pages = [
        SimpleNamespace(
            page_number=number,
            blocks=[
                SimpleNamespace(text=text, block_index=position, locator=None)
                for position, text in enumerate(texts)
            ],
        )
        for number, texts in sorted(blocks.items())
    ]
    return SimpleNamespace(pages=pages, tables=tables or [])


# -- 1..5 occurrence discovery and de-duplication ---------------------------- #


@pytest.mark.parametrize(
    ("case", "occurrences", "raw"),
    (("case_001", 18, 18), ("case_002", 45, 45), ("case_003", 6, 6)),
)
def test_discovered_occurrence_universe_is_complete_and_deduplicated(
    case: str, occurrences: int, raw: int
) -> None:
    """The universe is discovered from the source, not from already-marked atoms."""

    data = closure(case)
    assert data["criticality_model"]["source_marker_occurrence_count"] == occurrences
    assert data["criticality_model"]["raw_source_marker_discovery_count"] == raw
    assert (
        data["criticality_model"]["duplicate_source_marker_record_count"] == raw - occurrences
    )
    assert len(data["marker_records"]) == occurrences


def test_same_visual_marker_records_collapse_but_pages_stay_separate() -> None:
    """Extractor duplicates collapse; the same marker on another page does not."""

    line = "★提供原厂授权证明。"
    document = stub_document({5: [f"{line}\n{line}"], 6: [line]})
    occurrences = discover_marker_occurrences(document, {})
    assert len(occurrences) == 2, "one occurrence per printed marker, not per extractor record"
    assert raw_marker_discovery_count(occurrences) == 3
    assert duplicate_marker_record_count(occurrences) == 1
    assert sorted(occurrence.page for occurrence in occurrences) == [5, 6]
    collapsed = [occurrence for occurrence in occurrences if occurrence.extractor_record_count > 1]
    assert len(collapsed) == 1 and collapsed[0].page == 5


def test_wrapped_repeat_of_the_same_statement_shares_its_atoms() -> None:
    """A clause the extractor wraps differently on another page is the same statement."""

    from tender_basic.source_criticality import MarkerOccurrence

    def occurrence(body: str, page: int) -> MarkerOccurrence:
        return MarkerOccurrence(
            occurrence_id=f"MO{page:04d}",
            evidence_id=f"MK{page:04d}",
            raw_marker="★",
            normalized_marker="★",
            clause="",
            label="",
            page=page,
            locator=f"第{page}页",
            source_text=f"★{body}",
            source_kind="INLINE_TEXT",
            scope="BODY_TEXT",
            dedup_key=f"k{page}",
            text_key=f"t{page}",
        )

    wrapped = occurrence("提供产品计算机软件著作权证书和网络关键设", 67)
    complete = occurrence("提供产品计算机软件著作权证书和网络关键设备、网络安全专用产品", 95)
    assert _same_marked_identity(wrapped, complete)
    unrelated = occurrence("提供产品详细功能描述文字和CMA、CNAS 标志国家认可", 68)
    assert not _same_marked_identity(wrapped, unrelated)
    assert OCCURRENCE_IDENTITY_MIN > MIN_OCCURRENCE_FRAGMENT


@pytest.mark.parametrize("case", CASES)
def test_every_discovered_occurrence_has_one_disposition(case: str) -> None:
    """No occurrence may be silently missing from the ledger."""

    data = closure(case)
    records = data["marker_records"]
    ids = [record["occurrence_id"] for record in records]
    assert len(ids) == len(set(ids))
    assert len(ids) == data["criticality_model"]["source_marker_occurrence_count"]
    assert all(record["disposition"] for record in records)
    assert all(record["disposition_reason"] for record in records)
    counted = sum(data["marker_dispositions"].values())
    assert counted == len(records)


@pytest.mark.parametrize("case", CASES)
def test_discovered_equals_attributed_plus_accounted(case: str) -> None:
    """DISCOVERED = ATTRIBUTED + EXPLICITLY ACCOUNTED NON-DELIVERED, no remainder."""

    data = closure(case)
    counts = data["counts"]
    assert counts["marker_unresolved_count"] == 0
    assert counts["marker_unattributed_count"] == 0
    assert counts["marker_lost_count"] == 0
    attributed = sum(
        value
        for key, value in data["marker_dispositions"].items()
        if key in {COVERAGE_KIND_DIRECT_DELIVERED, COVERAGE_KIND_REFERENCE_PARENT}
    )
    background = data["marker_dispositions"].get("BACKGROUND_NON_ACTIONABLE", 0)
    assert attributed + background == counts["source_marker_occurrence_count"]
    assert COVERAGE_KIND_UNRESOLVED not in data["marker_dispositions"]


# -- 6..13 attribution semantics --------------------------------------------- #


def test_mid_text_markers_are_attributed_to_their_atom() -> None:
    """MK0017 / MK0018 are mid-block markers; the initial audit could not see them."""

    records = {
        record["marker_evidence_id"]: record
        for record in ledger("case_001")
    }
    for evidence_id, atom_id, expected_row in (
        ("MK0017", "SRA0263", "DR015"),
        ("MK0018", "SRA0264", "DR047"),
    ):
        record = records[evidence_id]
        assert record["source_atom_ids"], f"{evidence_id} must be attributed to an atom"
        assert atom_id in record["source_atom_ids"]
        assert record["disposition"] == COVERAGE_KIND_DIRECT_DELIVERED
        assert expected_row in record["starred_rows"]


def test_mid_text_attribution_route_is_recorded() -> None:
    routes = {
        route
        for record in ledger("case_002")
        for route in record["attribution_routes"]
    }
    assert "MARKER_IN_ATOM" in routes
    assert "CONTINUATION" in routes
    assert any("MARKER_IN_ATOM" in record["attribution_routes"] for record in ledger("case_001"))


def test_one_atom_may_carry_several_occurrences() -> None:
    by_atom: dict[str, list[str]] = {}
    for record in ledger("case_002"):
        for atom_id in record["source_atom_ids"]:
            by_atom.setdefault(atom_id, []).append(record["occurrence_id"])
    repeated = {atom: ids for atom, ids in by_atom.items() if len(ids) > 1}
    assert repeated, "a source atom must be able to carry several marker occurrences"
    assert max(len(ids) for ids in repeated.values()) >= 3


def test_one_occurrence_may_reach_several_review_rows() -> None:
    multi = [
        record
        for record in ledger("case_001")
        if len(record["starred_rows"]) > 1
    ]
    assert multi, "a marked clause can deliver several review rows"
    rows = {row for record in multi for row in record["starred_rows"]}
    assert {"DR018", "DR019", "DR020"} <= rows


def test_reference_parent_occurrences_are_not_direct_delivered_markers() -> None:
    parents = [
        record
        for record in ledger("case_001")
        if record["disposition"] == COVERAGE_KIND_REFERENCE_PARENT
    ]
    assert len(parents) == 2
    assert all(record["reference_parent"] for record in parents)
    assert all(not record["starred_rows"] for record in parents)


def test_attributed_occurrences_always_have_an_owner() -> None:
    for case in CASES:
        for record in ledger(case):
            if record["source_atom_ids"]:
                assert record["owner_items"], (
                    f"{case} {record['occurrence_id']} is attributed to an atom no review "
                    "point owns"
                )
            else:
                assert record["disposition"] in {
                    "BACKGROUND_NON_ACTIONABLE",
                    COVERAGE_KIND_REFERENCE_PARENT,
                }


def test_direct_marker_visibility_failures_are_zero() -> None:
    for case in CASES:
        data = closure(case)
        assert data["counts"]["direct_delivered_marker_visibility_failures"] == 0, case
        assert data["counts"]["reference_parent_coverage_failures"] == 0, case
        assert data["counts"]["marker_false_positive_count"] == 0, case


def test_marker_carrying_rows_keep_their_source_marker_column() -> None:
    rows = mandatory_rows("case_001")
    for record in ledger("case_001"):
        for row_id in record["starred_rows"]:
            row = rows[row_id]
            assert str(row["★"]).strip() == "★"
            assert str(row["源标记"] or "").strip(), f"{row_id} must print its source marker"


# -- 14..15 CASE002 DR028 closure -------------------------------------------- #


def test_case002_dr028_source_marker_is_visible_and_is_not_a_rejection() -> None:
    row = mandatory_rows("case_002")["DR028"]
    assert str(row["★"]).strip() == "★", "DR028 must show the ★ it owns"
    assert str(row["源标记"] or "").strip() == "原始标记：★（MANDATORY_PROOF）"
    assert str(row["强制性类型"] or "").strip() == "MANDATORY"
    assert str(row["否决性"] or "").strip() in ("", "None")
    assert not str(row["否决依据"] or "").strip() or str(row["否决依据"]).strip() == "None"
    assert str(row["实质性依据"] or "").strip() in ("", "None")


def test_case002_dr028_owns_the_delivered_occurrences() -> None:
    owned = [
        record
        for record in ledger("case_002")
        if "DR028" in record["delivered_owner_items"]
    ]
    assert len(owned) >= 6
    assert all(record["disposition"] == COVERAGE_KIND_DIRECT_DELIVERED for record in owned)
    assert all("DR028" in record["starred_rows"] for record in owned)


# -- 16..19 dashboard counters ----------------------------------------------- #


def test_substantive_dashboard_formula_matches_multi_valued_cells() -> None:
    metrics = closure("case_001")["dashboard_metrics"]
    formula = metrics["实质性要求条目数（源依据）"]["formula"]
    assert formula.count("COUNTIF") == 1, "one wildcard count, not a sum of exact matches"
    assert formula.endswith('"SUBSTANTIVE*")')


@pytest.mark.parametrize(
    ("case", "substantive", "marked_rows"),
    (("case_001", 31, 17), ("case_002", 1, 3), ("case_003", 4, 4)),
)
def test_dashboard_counters_equal_the_independent_recount(
    case: str, substantive: int, marked_rows: int
) -> None:
    data = closure(case)
    metrics = data["dashboard_metrics"]
    for label, metric in metrics.items():
        assert metric["ok"], f"{case} {label} does not reconcile"
        assert metric["recalculated_value"] == metric["independent_value"]
    assert metrics["实质性要求条目数（源依据）"]["recalculated_value"] == substantive
    assert metrics["带源标记的复核条目数（★）"]["recalculated_value"] == marked_rows
    assert data["counts"]["substantive_review_row_count"] == substantive
    assert data["counts"]["direct_source_marked_review_row_count"] == marked_rows


def test_source_marker_dashboard_label_is_a_row_count() -> None:
    for case in CASES:
        metrics = closure(case)["dashboard_metrics"]
        assert "带源标记的复核条目数（★）" in metrics
        assert not [label for label in metrics if "源标记条款数" in label]
        assert not [label for label in metrics if "源标记出现次数" in label]


def test_dashboard_gate_can_fail_on_the_historical_defect() -> None:
    """The gate must reject the formula shape and the token that hid D1."""

    values = ["SUBSTANTIVE_STARRED；REJECTION", "SUBSTANTIVE_VIA_REFERENCE；REJECTION", "MANDATORY"]
    broken = (
        '=COUNTIF(X,"SUBSTANTIVE_STARRED")+COUNTIF(X,"SUBSTANTIVE_EXPLICIT_WORDING")'
        '+COUNTIF(X,"SUBSTANTIVE_VIA_REFERENCE*")+COUNTIF(X,"SUBSTANTIVE_BY_LAW*")'
    )
    assert Round6Report._countif_evaluate(broken, values, "SUBSTANTIVE*") == -1
    assert Round6Report._countif_evaluate('=COUNTIF(X,"SUBSTANTIVE_")', values, "SUBSTANTIVE_") == 0
    assert Round6Report._countif_evaluate('=COUNTIF(X,"SUBSTANTIVE*")', values, "SUBSTANTIVE*") == 2


# -- 20..22 case invariants, coverage and preserved evidence ------------------ #


def test_case001_criticality_decomposition_is_unchanged() -> None:
    data = closure("case_001")
    counts = data["counts"]
    assert counts["substantive_review_row_count"] == 31
    kinds = {record["basis_kind"] for record in data["coverage_records"]}
    assert {"SOURCE_MARKER", "EXPLICIT_WORDING", "REFERENCE_PROPAGATION"} <= kinds
    assert counts["explicit_rejection_row_count"] == 10
    assert counts["derived_rejection_row_count"] == 23


def test_case003_marker_accounting_does_not_regress() -> None:
    data = closure("case_003")
    counts = data["counts"]
    assert counts["source_marker_occurrence_count"] == 6
    assert counts["marker_carrying_source_atom_count"] == 6
    assert counts["direct_source_marked_review_row_count"] == 4
    assert counts["substantive_review_row_count"] == 4
    assert counts["explicit_rejection_row_count"] == 10
    assert counts["derived_rejection_row_count"] == 0
    assert data["marker_dispositions"] == {COVERAGE_KIND_DIRECT_DELIVERED: 6}


@pytest.mark.parametrize("case", CASES)
def test_actionable_substantive_coverage_is_complete(case: str) -> None:
    data = closure(case)
    assert data["counts"]["source_substantive_actionable_uncovered_count"] == 0
    assert data["counts"]["source_substantive_requirement_without_review_coverage_count"] == 0
    assert data["coverage_records"], "coverage must be recomputed over the whole universe"


def test_initial_round6_builds_are_preserved_as_failed_evidence() -> None:
    for case in CASES:
        assert (INITIAL_BUILDS[case] / "投标项目复核表.xlsx").exists(), case
        assert (BUILDS[case] / "投标项目复核表.xlsx").exists(), case


def test_successor_workbooks_keep_the_word_artifacts_byte_identical() -> None:
    for case in CASES:
        manifest = json.loads(
            (BUILDS[case] / "build_manifest.json").read_text(encoding="utf-8")
        )
        identity = manifest["artifact_identity"]
        assert identity, case
        assert manifest["status"] == "REVIEW_WORKBOOK_SUCCESSOR", case
        assert "no Word rendering is repeated" in manifest["successor_reason"], case
        for name, entry in identity.items():
            assert entry["byte_identical"] is True, f"{case} {name}"
            assert entry["source_build_sha256"] == entry["successor_sha256"], f"{case} {name}"
