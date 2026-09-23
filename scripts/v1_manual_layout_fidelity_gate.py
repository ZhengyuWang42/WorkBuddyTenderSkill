"""V1 PHASE D/E gate: manual Word-review layout fidelity.

This gate exists because the CASE001 manual review found a class of defect no
existing automated gate could see: every page of the generated document was
individually plausible, yet the *pages disagreed with each other*.  Each source
page had become its own Word section, and the section margins were re-derived
per page from that one page's own content extrema, so an ordinary text page, a
sparse title-only page, a page whose table overhangs the body and a page of form
rows all produced different margins, and every centred heading on a
narrower-margin page drifted away from the page centre.

The lesson is general, so the gate is general: a source-format document that
reproduces one source document must present *one* section frame for one page
format, and no single page's content may move it.  Nothing here is specific to
CASE001 - the gate never mentions a page number, a margin value or a case id; it
reads measurements that were themselves derived from the source PDF and the
independently rendered generated PDF, and it applies thresholds.

Checks
------
``section_frame_margin_spread_zero``
    Every page-size group resolves to one frame and every measured margin spread
    inside it is within ``FRAME_SPREAD_TOLERANCE_PT``.  This is the check that
    would have failed the pre-fix CASE001 build by more than 100 pt.
``every_page_conforms_to_its_section_frame``
    Each page's Word section carries exactly the frame's margins.
``section_count_matches_page_count``
    Every generated page belongs to exactly one frame group, so no page was left
    on a private frame the group check never measured.
``frame_anchor_is_a_repeated_text_edge``
    The frame is backed by a repeated *text* body edge (or by centring symmetry),
    never by a single page's content extent and never by a table that overhangs
    the body.  This is the check that keeps a wide table from contracting the
    frame.
``centered_headings_sit_on_the_page_centre``
    No centred source heading is more than ``CENTER_ERROR_TOLERANCE_PT`` from the
    page centre.
``source_one_line_headings_stay_one_line``
    A source heading that occupies one source line is not wrapped in the
    generated document.
``no_source_row_is_split_across_generated_lines``
    A source element whose lines all lie in one visual row is emitted as one
    generated row, so an assembled form line cannot spill onto a second line.
``no_unexpected_blank_page``
    No generated page is blank.
``table_geometry_preserved`` (when a table-geometry audit is supplied)
    No table is clamped to a narrower width than its source, no avoidable
    geometry drift remains, and the rendered table box matches the source box.

Usage::

    .venv/Scripts/python.exe scripts/v1_manual_layout_fidelity_gate.py \
        --frame-audit acceptance/reports/v1_generalization/case001_page_frame_audit.json \
        --table-audit acceptance/reports/v1_generalization/case001_table_geometry.json \
        --label case_001 \
        --out acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "v1_manual_layout_fidelity/1"

# A stable frame means the same margin on every page of one page format.  The
# tolerance is not zero because Word stores twips (1/20 pt) and a frame may be
# re-derived with sub-twip rounding; it is far below the tens of points a
# per-page derivation moved.
FRAME_SPREAD_TOLERANCE_PT = 0.5
CENTER_ERROR_TOLERANCE_PT = 2.0
TABLE_WIDTH_TOLERANCE_PT = 1.0

MIN_FRAME_ANCHOR_SUPPORT = 2


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _check(name: str, ok: bool, observed: Any, *, note: str = "") -> dict[str, Any]:
    return {"check": name, "ok": bool(ok), "observed": observed, "note": note}


def frame_checks(audit: dict[str, Any]) -> list[dict[str, Any]]:
    derivation = audit.get("frame_derivation") or {}
    frames = derivation.get("frames") or {}
    spreads = derivation.get("margin_spread") or {}
    pages = audit.get("pages") or []
    summary = audit.get("summary") or {}

    spread_failures = {
        frame_id: spread
        for frame_id, spread in spreads.items()
        if max(
            abs(float(spread.get("left_margin_spread_pt") or 0.0)),
            abs(float(spread.get("right_margin_spread_pt") or 0.0)),
            abs(float(spread.get("top_margin_spread_pt") or 0.0)),
        ) > FRAME_SPREAD_TOLERANCE_PT
    }
    non_conforming = [
        page.get("generated_page")
        for page in pages
        if not (page.get("frame_conformance") or {}).get("conforms")
    ]
    grouped_pages = sum(len(pages) for pages in (derivation.get("pages_by_frame") or {}).values())

    weak_anchors: list[Any] = []
    for frame_id, frame in frames.items():
        symmetric = frame.get("centered_symmetry")
        left = frame.get("left_anchor") or {}
        right = frame.get("right_anchor") or {}
        text_backed = (
            str(left.get("kind", "")).startswith("text_")
            and str(right.get("kind", "")).startswith("text_")
        )
        if symmetric:
            continue
        if not text_backed or min(
            int(left.get("support") or 0), int(right.get("support") or 0)
        ) < MIN_FRAME_ANCHOR_SUPPORT:
            weak_anchors.append(
                {
                    "frame_id": frame_id,
                    "left_anchor": left,
                    "right_anchor": right,
                    "centered_symmetry": symmetric,
                }
            )

    outside = summary.get("centered_heading_pages_outside_tolerance") or []
    max_center_error = summary.get("max_center_error_pt")
    center_ok = not outside and (
        max_center_error is None or abs(float(max_center_error)) <= CENTER_ERROR_TOLERANCE_PT
    )

    return [
        _check(
            "section_frame_margin_spread_zero",
            not spread_failures,
            {"spreads": spreads, "outside_tolerance": spread_failures},
            note=f"tolerance {FRAME_SPREAD_TOLERANCE_PT} pt",
        ),
        _check(
            "every_page_conforms_to_its_section_frame",
            not non_conforming,
            {"pages_not_conforming": non_conforming, "page_count": len(pages)},
        ),
        _check(
            "section_count_matches_page_count",
            grouped_pages == len(pages) and len(pages) > 0,
            {
                "pages_grouped_into_a_frame": grouped_pages,
                "measured_pages": len(pages),
                "pages_by_frame": {
                    frame_id: len(frame_pages)
                    for frame_id, frame_pages in (derivation.get("pages_by_frame") or {}).items()
                },
                "sections": summary.get("sections"),
                "generated_pages": summary.get("generated_pages"),
            },
        ),
        _check(
            "frame_anchor_is_a_repeated_text_edge",
            not weak_anchors,
            {"frames_without_a_repeated_text_edge": weak_anchors},
            note=(
                "a frame must be a repeated text body edge, or the centring "
                f"symmetry of the body; minimum support {MIN_FRAME_ANCHOR_SUPPORT} pages"
            ),
        ),
        _check(
            "centered_headings_sit_on_the_page_centre",
            center_ok,
            {
                "centered_heading_pages": summary.get("centered_heading_pages"),
                "outside_tolerance": outside,
                "max_center_error_pt": max_center_error,
            },
            note=f"tolerance {CENTER_ERROR_TOLERANCE_PT} pt",
        ),
        _check(
            "source_one_line_headings_stay_one_line",
            not (summary.get("source_one_line_headings_wrapped") or []),
            {"wrapped": summary.get("source_one_line_headings_wrapped") or []},
        ),
        _check(
            "no_source_row_is_split_across_generated_lines",
            not (summary.get("pages_with_a_split_source_row") or [])
            and int(summary.get("split_source_rows") or 0) == 0,
            {
                "pages_with_a_split_source_row": summary.get(
                    "pages_with_a_split_source_row"
                )
                or [],
                "split_source_rows": summary.get("split_source_rows"),
                "single_row_elements_checked": summary.get("single_row_elements_checked"),
                "unmeasured_source_rows": summary.get("unmeasured_source_rows") or [],
            },
            note=(
                "an unmeasured source row is a row whose trace markers were "
                "replaced by a resolved value; it is reported, not failed"
            ),
        ),
        _check(
            "no_unexpected_blank_page",
            not (summary.get("blank_pages") or []),
            {"blank_pages": summary.get("blank_pages") or []},
        ),
    ]


def table_checks(audit: dict[str, Any]) -> list[dict[str, Any]]:
    summary = audit.get("summary") or {}
    avoidable = summary.get("avoidable_drift") or []
    clamped = summary.get("clamped_tables") or []
    width_delta = abs(float(summary.get("max_abs_width_delta_pt") or 0.0))
    x1_delta = abs(float(summary.get("max_abs_x1_delta_pt") or 0.0))
    return [
        _check(
            "table_width_keeps_the_source_geometry",
            not avoidable
            and not clamped
            and width_delta <= TABLE_WIDTH_TOLERANCE_PT
            and x1_delta <= TABLE_WIDTH_TOLERANCE_PT,
            {
                "tables": summary.get("tables"),
                "source_reproduced": summary.get("source_reproduced"),
                "font_metric_only": summary.get("font_metric_only"),
                "avoidable_drift": avoidable,
                "clamped_tables": clamped,
                "max_abs_width_delta_pt": summary.get("max_abs_width_delta_pt"),
                "max_abs_x1_delta_pt": summary.get("max_abs_x1_delta_pt"),
                "rendered_pages_with_table_box": summary.get("rendered_pages_with_table_box"),
            },
            note=(
                f"tolerance {TABLE_WIDTH_TOLERANCE_PT} pt; every source table must "
                "be painted at its own source width, never clamped to the section "
                "text column"
            ),
        )
    ]


def underline_checks(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """The Stage C underline inventory, as one gate check.

    Every underline the source drew on the response-letter page must have exactly
    one emitted counterpart at the source's own geometry.  The check is stated as
    the four counts the inventory produces, so a lost, invented or mis-measured
    underline fails the gate by name rather than by a derived score.
    """

    expected = int(inventory.get("source_underline_count", 0))
    matched = int(inventory.get("matched", 0))
    lost = int(inventory.get("lost", 0))
    invented = int(inventory.get("invented", 0))
    out_of_tolerance = int(inventory.get("out_of_tolerance", 0))
    ok = (
        expected > 0
        and matched == expected
        and lost == 0
        and invented == 0
        and out_of_tolerance == 0
    )
    return [
        _check(
            "source_underline_inventory_is_complete",
            ok,
            {
                "source_underline_count": expected,
                "matched": matched,
                "lost": lost,
                "invented": invented,
                "out_of_tolerance": out_of_tolerance,
                "tolerance_pt": inventory.get("tolerance_pt"),
                "response_letter_source_page": inventory.get(
                    "response_letter_source_page"
                ),
                "response_letter_generated_page": inventory.get(
                    "response_letter_generated_page"
                ),
                "page_mapping_basis": inventory.get("page_mapping_basis"),
                "lost_rules": [
                    rule.get("source_rule_id")
                    for rule in inventory.get("rules", [])
                    if rule.get("status") == "LOST"
                ],
                "offending_rules": [
                    {
                        "source_rule_id": rule.get("source_rule_id"),
                        "status": rule.get("status"),
                        "deviation_pt": rule.get("deviation_pt"),
                        "gated_axis": rule.get("gated_axis"),
                    }
                    for rule in inventory.get("rules", [])
                    if rule.get("status") == "OUT_OF_TOLERANCE"
                ],
                "invented_rules": inventory.get("invented_rules", []),
            },
            note=(
                "every source underline on the response-letter page is accounted "
                "for exactly once, at the source's own geometry, inside the frozen "
                "horizontal tolerance, which is never relaxed to make a rule agree"
            ),
        )
    ]


def build_report(
    frame_audit: dict[str, Any],
    *,
    table_audit: dict[str, Any] | None = None,
    underline_inventory: dict[str, Any] | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    checks = frame_checks(frame_audit)
    if table_audit is not None:
        checks.extend(table_checks(table_audit))
    if underline_inventory is not None:
        checks.extend(underline_checks(underline_inventory))
    failed = [check["check"] for check in checks if not check["ok"]]
    build = frame_audit.get("build") or {}
    return {
        "schema": SCHEMA,
        "gate": "v1_manual_word_review_layout_fidelity",
        "label": label,
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "failed_checks": failed,
        "thresholds": {
            "frame_spread_tolerance_pt": FRAME_SPREAD_TOLERANCE_PT,
            "center_error_tolerance_pt": CENTER_ERROR_TOLERANCE_PT,
            "table_width_tolerance_pt": TABLE_WIDTH_TOLERANCE_PT,
            "min_frame_anchor_support": MIN_FRAME_ANCHOR_SUPPORT,
            "underline_tolerance_pt": (underline_inventory or {}).get("tolerance_pt"),
        },
        "build": {
            "build_id": build.get("build_id"),
            "build_dir": build.get("build_dir"),
            "docx": build.get("docx"),
            "docx_sha256": build.get("docx_sha256"),
            "pdf": build.get("pdf"),
            "pdf_sha256": build.get("pdf_sha256"),
            "generated_pages": build.get("pdf_page_count"),
            "source_pages": build.get("source_page_count"),
            "section_count": build.get("section_count"),
        },
        "source_audits": {
            "frame": frame_audit.get("schema"),
            "table": (table_audit or {}).get("schema"),
            "underline_inventory": (underline_inventory or {}).get("schema"),
        },
        "manual_review_required": True,
        "readiness": {
            "READY_FOR_SUBMISSION": False,
            "note": (
                "This gate proves the automated layout contract only. Manual Word "
                "review remains required and cannot be completed by automation."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "V1 manual-Word-review layout fidelity gate. Applies the stable "
            "section-frame, no-forced-wrap, table-geometry and underline-inventory "
            "contract to the measurements an independent page-frame / "
            "table-geometry audit and the Stage C underline inventory derived from "
            "the source PDF and the rendered generated PDF. It contains no "
            "case-specific page number, margin or threshold."
        )
    )
    parser.add_argument("--frame-audit", required=True)
    parser.add_argument("--table-audit", default=None)
    parser.add_argument("--underline-inventory", default=None)
    parser.add_argument("--label", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    frame_audit = _load(args.frame_audit)
    table_audit = _load(args.table_audit) if args.table_audit else None
    underline_inventory = (
        _load(args.underline_inventory) if args.underline_inventory else None
    )
    report = build_report(
        frame_audit,
        table_audit=table_audit,
        underline_inventory=underline_inventory,
        label=args.label,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "failed_checks": report["failed_checks"],
                "checks": [check["check"] for check in report["checks"]],
                "out": str(out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
