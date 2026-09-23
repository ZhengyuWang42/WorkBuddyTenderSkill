"""Deterministic tests for the V1 manual-Word-review layout fidelity gate.

The gate's whole purpose is to fail the class of defect the CASE001 manual
review found, so the tests drive it from synthetic measurements: a good document
must pass, and *each individual* way a page can drag the section frame or force a
wrap must fail the specific check that owns it.  Nothing here reads a build.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from v1_manual_layout_fidelity_gate import (  # noqa: E402
    CENTER_ERROR_TOLERANCE_PT,
    FRAME_SPREAD_TOLERANCE_PT,
    TABLE_WIDTH_TOLERANCE_PT,
    build_report,
    frame_checks,
    table_checks,
)

FRAME_ID = "PORTRAIT_595x842_1"


def _frame_audit() -> dict:
    """A good CASE001-shaped audit: one frame, 22 conforming pages."""

    return {
        "schema": "v1_case001_page_frame_audit/1",
        "build": {
            "build_id": "synthetic",
            "build_dir": "synthetic",
            "docx": "synthetic.docx",
            "docx_sha256": "0" * 64,
            "pdf": "synthetic.pdf",
            "pdf_sha256": "1" * 64,
            "pdf_page_count": 3,
            "source_page_count": 3,
            "section_count": 3,
        },
        "frame_derivation": {
            "frames": {
                FRAME_ID: {
                    "frame_id": FRAME_ID,
                    "left_margin": 70.8,
                    "right_margin": 70.9,
                    "top_body_frame": 73.86,
                    "usable_text_width": 453.6,
                    "confidence": 0.545,
                    "left_anchor": {"x": 70.8, "kind": "text_left", "support": 12},
                    "right_anchor": {"x": 524.4, "kind": "text_right", "support": 10},
                    "centered_symmetry": None,
                }
            },
            "pages_by_frame": {FRAME_ID: [40, 41, 42]},
            "margin_spread": {
                FRAME_ID: {
                    "left_margin_spread_pt": 0.0,
                    "right_margin_spread_pt": 0.0,
                    "top_margin_spread_pt": 0.0,
                    "page_count": 3,
                }
            },
        },
        "pages": [
            {
                "generated_page": index + 1,
                "source_page": 40 + index,
                "frame_conformance": {"conforms": True},
                "source": {"sparse_title_only": False},
            }
            for index in range(3)
        ],
        "summary": {
            "sections": 3,
            "generated_pages": 3,
            "blank_pages": [],
            "pages_using_the_stable_frame": 3,
            "centered_heading_pages": 3,
            "centered_heading_pages_outside_tolerance": [],
            "max_center_error_pt": 0.42,
            "source_one_line_headings_wrapped": [],
            "single_row_elements_checked": 12,
            "pages_with_a_split_source_row": [],
            "split_source_rows": 0,
            "unmeasured_source_rows": [],
        },
    }


def _table_audit() -> dict:
    return {
        "schema": "v1_table_geometry_audit/1",
        "build_id": "synthetic",
        "table_count": 1,
        "records": [],
        "summary": {
            "tables": 1,
            "source_reproduced": 1,
            "font_metric_only": 0,
            "avoidable_drift": [],
            "clamped_tables": [],
            "max_abs_width_delta_pt": 0.0,
            "max_abs_x1_delta_pt": 0.0,
            "rendered_pages_with_table_box": 1,
        },
    }


def _status(report: dict) -> tuple[str, list[str]]:
    return report["status"], report["failed_checks"]


def test_a_conforming_document_passes_every_check() -> None:
    report = build_report(_frame_audit(), table_audit=_table_audit(), label="case_001")
    assert _status(report) == ("PASS", [])
    assert report["manual_review_required"] is True
    assert report["readiness"]["READY_FOR_SUBMISSION"] is False


def test_a_sparse_page_that_moves_the_frame_fails_the_spread_check() -> None:
    audit = _frame_audit()
    # A title-only page whose own extents became the section margin.
    audit["frame_derivation"]["margin_spread"][FRAME_ID]["left_margin_spread_pt"] = 113.25
    audit["frame_derivation"]["margin_spread"][FRAME_ID]["right_margin_spread_pt"] = 125.05
    audit["pages"][1]["frame_conformance"] = {
        "conforms": False,
        "left_margin_delta": -53.9,
    }
    status, failed = _status(build_report(audit))
    assert status == "FAIL"
    assert "section_frame_margin_spread_zero" in failed
    assert "every_page_conforms_to_its_section_frame" in failed


@pytest.mark.parametrize(
    "left,right",
    [
        ({"kind": "table_left", "support": 12}, {"kind": "table_right", "support": 10}),
        ({"kind": "text_left", "support": 1}, {"kind": "text_right", "support": 1}),
        ({"kind": "text_left", "support": 12}, {"kind": "rule_right", "support": 4}),
    ],
)
def test_a_frame_not_backed_by_a_repeated_text_edge_fails(left, right) -> None:
    audit = _frame_audit()
    frame = audit["frame_derivation"]["frames"][FRAME_ID]
    frame["left_anchor"] = {"x": 65.33, **left}
    frame["right_anchor"] = {"x": 541.77, **right}
    status, failed = _status(build_report(audit))
    assert status == "FAIL"
    assert "frame_anchor_is_a_repeated_text_edge" in failed


def test_a_frame_from_centring_symmetry_is_accepted() -> None:
    audit = _frame_audit()
    frame = audit["frame_derivation"]["frames"][FRAME_ID]
    frame["left_anchor"] = {"x": 245.0, "kind": "text_left", "support": 1}
    frame["right_anchor"] = {"x": 350.3, "kind": "text_right", "support": 1}
    frame["centered_symmetry"] = {"page_center_x": 297.65, "frame_center_x": 297.6}
    assert _status(build_report(audit)) == ("PASS", [])


def test_a_drifting_centered_heading_fails() -> None:
    audit = _frame_audit()
    audit["summary"]["centered_heading_pages_outside_tolerance"] = [2]
    audit["summary"]["max_center_error_pt"] = 53.88
    status, failed = _status(build_report(audit))
    assert status == "FAIL"
    assert "centered_headings_sit_on_the_page_centre" in failed
    # The same audit with only sub-point drift still fails the tolerance check.
    audit["summary"]["centered_heading_pages_outside_tolerance"] = []
    audit["summary"]["max_center_error_pt"] = CENTER_ERROR_TOLERANCE_PT + 0.01
    assert "centered_headings_sit_on_the_page_centre" in _status(build_report(audit))[1]


def test_a_wrapped_source_one_line_heading_fails() -> None:
    audit = _frame_audit()
    audit["summary"]["source_one_line_headings_wrapped"] = [
        {"generated_page": 15, "source_text": "八、响应货物技术性能指标的详细描述及技术支持资料"}
    ]
    status, failed = _status(build_report(audit))
    assert status == "FAIL"
    assert "source_one_line_headings_stay_one_line" in failed


def test_a_source_row_split_across_two_generated_lines_fails() -> None:
    audit = _frame_audit()
    audit["summary"]["pages_with_a_split_source_row"] = [5]
    audit["summary"]["split_source_rows"] = 1
    status, failed = _status(build_report(audit))
    assert status == "FAIL"
    assert "no_source_row_is_split_across_generated_lines" in failed


def test_an_unmeasured_source_row_is_reported_not_failed() -> None:
    audit = _frame_audit()
    audit["summary"]["unmeasured_source_rows"] = [
        {"generated_page": 3, "reason": "TRACE_TEXT_REPLACED_OR_ABSENT"}
    ]
    assert _status(build_report(audit)) == ("PASS", [])


def test_a_blank_page_fails() -> None:
    audit = _frame_audit()
    audit["summary"]["blank_pages"] = [17]
    status, failed = _status(build_report(audit))
    assert status == "FAIL"
    assert "no_unexpected_blank_page" in failed


def test_a_page_on_a_private_frame_fails_the_grouping_check() -> None:
    audit = _frame_audit()
    audit["frame_derivation"]["pages_by_frame"][FRAME_ID] = [40, 41]
    status, failed = _status(build_report(audit))
    assert status == "FAIL"
    assert "section_count_matches_page_count" in failed


def test_a_table_clamped_to_the_text_column_fails() -> None:
    audit = _frame_audit()
    tables = _table_audit()
    tables["summary"]["clamped_tables"] = [
        {"source_page": 48, "source_width_pt": 476.44, "rendered_width_pt": 453.6}
    ]
    tables["summary"]["max_abs_width_delta_pt"] = 22.84
    status, failed = _status(build_report(audit, table_audit=tables))
    assert status == "FAIL"
    assert "table_width_keeps_the_source_geometry" in failed


def test_table_check_tolerates_border_stroke_only() -> None:
    checks = table_checks(_table_audit())
    assert checks[0]["ok"] is True
    tables = _table_audit()
    tables["summary"]["max_abs_x1_delta_pt"] = TABLE_WIDTH_TOLERANCE_PT
    assert table_checks(tables)[0]["ok"] is True
    tables["summary"]["max_abs_x1_delta_pt"] = TABLE_WIDTH_TOLERANCE_PT + 0.2
    assert table_checks(tables)[0]["ok"] is False


def test_frame_checks_do_not_mutate_the_audit() -> None:
    audit = _frame_audit()
    snapshot = copy.deepcopy(audit)
    frame_checks(audit)
    assert audit == snapshot


def test_frame_spread_tolerance_is_strict() -> None:
    audit = _frame_audit()
    audit["frame_derivation"]["margin_spread"][FRAME_ID]["left_margin_spread_pt"] = (
        FRAME_SPREAD_TOLERANCE_PT
    )
    assert _status(build_report(audit)) == ("PASS", [])
    audit["frame_derivation"]["margin_spread"][FRAME_ID]["left_margin_spread_pt"] = (
        FRAME_SPREAD_TOLERANCE_PT + 0.01
    )
    assert "section_frame_margin_spread_zero" in _status(build_report(audit))[1]
