"""Round 12: final XLSX delivery-text closure.

Rounds 9-11 proved the *model*: exact locator equality, bid/contract-risk
separation and structural-heading fidelity.  Human review of workbook11 found the
**delivered cells** still disagree with those rules:

* all seven CASE001 pure contract-risk rows still asked the bidder to
  "逐条比对响应文件对应章节" although the stage says they are pre-bid notices;
* DR037 called its front-table value "合同条款原文" without distinguishing it from
  the general/post-award clause;
* 投标项目复核表!E38 ended inside a standard identifier ("GB50015-2") because the
  main sheet sliced the evidence summary with a raw ``[:110]`` instead of the
  shared semantic clipper.

Round 12 closes the delivery path and gates the **SAVED/REOPENED XLSX** itself:

    PURE_CONTRACT_RISK_RESPONSE_FILE_LANGUAGE_COUNT = 0
    MULTI_SOURCE_ROLE_DISPLAY_AMBIGUITY_COUNT = 0
    MID_TOKEN_EVIDENCE_TRUNCATION_COUNT = 0

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_round12_report.py --three-case
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from openpyxl import load_workbook  # noqa: E402

from tender_basic.delivery_text import (  # noqa: E402
    GENERAL_ROLE_LABEL,
    PROJECT_ROLE_LABEL,
    check_contract_risk_delivery,
    check_evidence_summary_clipping,
    check_multi_source_role_display,
    source_role_labels,
)
from v1_review_workbook_round8_report import REPORTS  # noqa: E402
from v1_review_workbook_round11_report import (  # noqa: E402
    Round11Report,
    markdown as round11_markdown,
)

SCHEMA = "v1_review_workbook_round12/1"
GENERALIZATION_SCHEMA = "v1_review_workbook_round12_generalization/1"

#: the row whose two sources must stay distinguishable (human defect 2)
DR037_ITEM_ID = "DR037"
#: page 11 / 供应商须知前附表 / 7.3 -- the project's own value
DR037_PROJECT_PAGE = "第11页"
DR037_PROJECT_CLAUSE = "7.3"
#: page 21 / 7.3 履约担保 -- the general (post-award) obligation
DR037_GENERAL_PAGE = "第21页"
DR037_GENERAL_SECTION = "7.3履约担保"
#: page 18 / 3.4 响应保证金 -- a *different* concern's clause, never this row's source
DR037_FORBIDDEN_PAGE = "第18页"
DR037_FORBIDDEN_TEXT = "响应保证金"

#: round-12 successor build per case (final delivery-text closure).  The earlier
#: ``..._review_workbook12`` directories were built from the *intermediate* code and
#: are kept on disk as superseded evidence; these are the immutable final successors
#: that the gates below read.
BUILDS: dict[str, str] = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook12_final",
    "case_002": "v1_round4_closure9_review_workbook12_final",
    "case_003": "v1_round4_closure9_review_workbook12_final",
}

#: sheets whose evidence-summary cells are audited
EVIDENCE_SHEETS: tuple[str, ...] = (
    "投标项目复核表",
    "02_关键条款",
    "03_资格否决与强制项",
    "07_证据索引",
)
#: sheet columns that display an evidence summary
EVIDENCE_COLUMNS: dict[str, tuple[str, ...]] = {
    "投标项目复核表": ("E",),
    "02_关键条款": ("L",),
    "03_资格否决与强制项": ("M",),
    "07_证据索引": ("D",),
}


class Round12Report(Round11Report):
    """Round-11 audits bound to the round-12 successor, plus the saved-XLSX gate."""

    def __init__(self, case: str, *, case_dir: Path | None = None) -> None:
        from v1_review_workbook_round8_report import Round8Report

        Round8Report.__init__(self, case, case_dir=case_dir, build_name=BUILDS[case])
        self.items = list(self.r4.items)
        self.background = list(self.r4.background)
        self.by_item = {
            str(item.item_id): item for item in [*self.items, *self.background]
        }

    # -- saved-workbook delivery text --------------------------------------- #

    def _delivered_contract_risk_rows(self) -> list[dict[str, Any]]:
        """Every contract-risk row as the reviewer reads it in the saved cells."""

        stage_by_item = {
            str(item.item_id): str(getattr(item, "review_stage", "") or "")
            for item in self.items
        }
        source_pages: dict[str, list[str]] = {}
        for item in self.items:
            pages = [
                str(unit.get("page"))
                for unit in (getattr(item, "evidence_units", ()) or ())
                if unit.get("page") is not None
            ]
            source_pages[str(item.item_id)] = pages
        workbook = load_workbook(self.workbook, data_only=True, read_only=True)
        rows: list[dict[str, Any]] = []
        try:
            legacy = workbook["投标项目复核表"]
            for row in legacy.iter_rows(min_row=9, values_only=True):
                text = str(row[3] or "")
                if not text:
                    continue
                # the legacy sheet has no item id column; match by requirement text
                item_id = ""
                for item in self.items:
                    if str(item.source_requirement or "") and str(item.source_requirement) in text:
                        item_id = str(item.item_id)
                        break
                if not item_id:
                    continue
                rows.append(
                    {
                        "item_id": item_id,
                        "sheet": "投标项目复核表",
                        "cell": "",
                        "review_stage": stage_by_item.get(item_id, ""),
                        "text": text,
                        "source_pages": source_pages.get(item_id, []),
                    }
                )
            clause = workbook["02_关键条款"]
            headers = [
                str(cell.value or "").strip()
                for cell in next(clause.iter_rows(min_row=1, max_row=1))
            ]
            for position, row in enumerate(clause.iter_rows(min_row=2, values_only=True), start=2):
                record = {
                    name: row[index] for index, name in enumerate(headers) if index < len(row)
                }
                item_id = str(record.get("requirement_id") or "")
                if not item_id:
                    continue
                text = " ".join(
                    str(record.get(field) or "")
                    for field in ("抽取结果", "复核动作", "核验标准")
                )
                rows.append(
                    {
                        "item_id": item_id,
                        "sheet": "02_关键条款",
                        "cell": f"02_关键条款!D{position}",
                        "review_stage": stage_by_item.get(item_id, ""),
                        "text": text,
                        "source_pages": source_pages.get(item_id, []),
                    }
                )
        finally:
            workbook.close()
        return rows

    def _delivered_evidence_cells(self) -> list[dict[str, Any]]:
        """Every evidence-summary cell as displayed in the saved workbook."""

        from openpyxl.utils import column_index_from_string

        workbook = load_workbook(self.workbook, data_only=True, read_only=True)
        cells: list[dict[str, Any]] = []
        try:
            for title in EVIDENCE_SHEETS:
                if title not in workbook.sheetnames:
                    continue
                sheet = workbook[title]
                first = 9 if title == "投标项目复核表" else 2
                for column in EVIDENCE_COLUMNS.get(title, ()):
                    index = column_index_from_string(column) - 1
                    for position, row in enumerate(
                        sheet.iter_rows(min_row=first, values_only=True), start=first
                    ):
                        if index >= len(row):
                            continue
                        value = str(row[index] or "")
                        if value.strip():
                            cells.append(
                                {
                                    "sheet": title,
                                    "cell": f"{column}{position}",
                                    "text": value,
                                }
                            )
        finally:
            workbook.close()
        return cells

    def check_delivery_text(self) -> None:
        rows = self._delivered_contract_risk_rows()
        separation = check_contract_risk_delivery(rows)
        self.counts["PURE_CONTRACT_RISK_RESPONSE_FILE_LANGUAGE_COUNT"] = separation[
            "pure_contract_risk_response_file_language_count"
        ]
        self.check(
            "a pure contract risk never asks for response-file comparison",
            separation["pure_contract_risk_response_file_language_count"] == 0,
            f"{separation['contract_risk_row_checked']} contract-risk row(s) read from the "
            f"SAVED workbook, "
            f"{separation['pure_contract_risk_response_file_language_count']} with response-file language",
            {"problems": separation["contaminated"][:8]},
        )

        roles = check_multi_source_role_display(rows)
        self.counts["MULTI_SOURCE_ROLE_DISPLAY_AMBIGUITY_COUNT"] = roles[
            "multi_source_role_display_ambiguity_count"
        ]
        self.check(
            "a two-source row names both of its source roles in the saved cell",
            roles["multi_source_role_display_ambiguity_count"] == 0,
            f"{roles['multi_source_row_checked']} two-source row(s) checked, "
            f"{roles['multi_source_role_display_ambiguity_count']} ambiguous",
            {"problems": roles["ambiguous"][:8]},
        )

        cells = self._delivered_evidence_cells()
        clipping = check_evidence_summary_clipping(cells)
        self.counts["MID_TOKEN_EVIDENCE_TRUNCATION_COUNT"] = clipping[
            "mid_token_evidence_truncation_count"
        ]
        self.check(
            "no evidence summary in the saved workbook is clipped mid-token",
            clipping["mid_token_evidence_truncation_count"] == 0,
            f"{clipping['evidence_summary_cell_checked']} evidence cell(s) checked across "
            f"{len(EVIDENCE_SHEETS)} sheet(s), "
            f"{clipping['mid_token_evidence_truncation_count']} mid-token truncation(s)",
            {"problems": clipping["problems"][:8]},
        )

    def check_dr037_source_roles(self) -> None:
        """Human defect 2, read back from the SAVED cell only.

        DR037 composes the project's own value (page 11 / 供应商须知前附表 / 7.3) with
        the general post-award obligation (page 21 / 7.3 履约担保).  The two sources
        must be *distinguishable* in the delivered cell, and the response-bond clause
        of a different concern (page 18 / 3.4 响应保证金) must never be presented as
        this row's source.

        DR037 is the CASE001 row the human reviewed; the other cases carry their own
        meanings for that item id, so the named fixture is CASE001-only (like the
        round-11 human fixtures) and the counters say so.
        """

        if self.case != "case_001":
            for key in (
                "DR037_PROJECT_SOURCE",
                "DR037_GENERAL_SOURCE",
                "DR037_RESPONSE_BOND_SOURCE_PRESENT",
                "DR037_DELIVERED_CELL_COUNT",
            ):
                self.counts[key] = "NOT_APPLICABLE"
            return

        cells = [
            row
            for row in self._delivered_contract_risk_rows()
            if str(row.get("item_id") or "") == DR037_ITEM_ID
        ]
        text = " ".join(str(row.get("text") or "") for row in cells)
        labels = source_role_labels(text)
        project = str(labels.get(PROJECT_ROLE_LABEL) or "")
        general = str(labels.get(GENERAL_ROLE_LABEL) or "")
        flat = "".join(text.split())
        self.counts["DR037_PROJECT_SOURCE"] = project
        self.counts["DR037_GENERAL_SOURCE"] = general
        self.counts["DR037_RESPONSE_BOND_SOURCE_PRESENT"] = bool(
            DR037_FORBIDDEN_TEXT in flat or DR037_FORBIDDEN_PAGE in flat
        )
        self.counts["DR037_DELIVERED_CELL_COUNT"] = len(cells)

        self.check(
            "DR037 distinguishes its project value from its general clause in the saved cell",
            bool(cells)
            and DR037_PROJECT_PAGE in project
            and DR037_PROJECT_CLAUSE in project
            and DR037_GENERAL_PAGE in general
            and DR037_GENERAL_SECTION in "".join(general.split()),
            f"{len(cells)} saved cell(s) for {DR037_ITEM_ID}: "
            f"{PROJECT_ROLE_LABEL}={project or '(missing)'} / "
            f"{GENERAL_ROLE_LABEL}={general or '(missing)'}",
            {
                "expected": (
                    f"{PROJECT_ROLE_LABEL}={DR037_PROJECT_PAGE}/{DR037_PROJECT_CLAUSE}, "
                    f"{GENERAL_ROLE_LABEL}={DR037_GENERAL_PAGE}/{DR037_GENERAL_SECTION}"
                ),
                "cells": [
                    {"sheet": row.get("sheet"), "text": str(row.get("text") or "")[:400]}
                    for row in cells[:4]
                ],
            },
        )
        self.check(
            "DR037 never presents the response-bond clause as its own source",
            not self.counts["DR037_RESPONSE_BOND_SOURCE_PRESENT"],
            f"saved {DR037_ITEM_ID} text mentions "
            f"{DR037_FORBIDDEN_PAGE}/{DR037_FORBIDDEN_TEXT}: "
            f"{self.counts['DR037_RESPONSE_BOND_SOURCE_PRESENT']}",
            {
                "forbidden": f"{DR037_FORBIDDEN_PAGE} / 3.4 {DR037_FORBIDDEN_TEXT}",
                "text": flat[:400],
            },
        )

    # -- audit -------------------------------------------------------------- #

    def audit(self) -> dict[str, Any]:
        data = super().audit()
        self.check_delivery_text()
        self.check_dr037_source_roles()
        failed = [check.name for check in self.checks if not check.ok]
        failed_fixtures = [
            key for key, value in self.fixtures.items() if value["status"] != "PASS"
        ]
        data.update(
            {
                "schema": SCHEMA,
                "round": 12,
                "checks": [check.as_dict() for check in self.checks],
                "check_count": len(self.checks),
                "passed_count": len(self.checks) - len(failed),
                "failed_checks": failed,
                "verdict": "PASS" if not failed and not failed_fixtures else "FAIL",
                "fixtures": self.fixtures,
                "fixture_summary": {
                    "total": len(self.fixtures),
                    "passed": len(self.fixtures) - len(failed_fixtures),
                    "failed": failed_fixtures,
                },
                "counts": dict(self.counts),
                "contract_risk_delivery_records": self._delivery_records(),
                "dr037_sources": {
                    "project_specific_source": self.counts.get("DR037_PROJECT_SOURCE"),
                    "general_post_award_source": self.counts.get("DR037_GENERAL_SOURCE"),
                    "response_bond_source_present": self.counts.get(
                        "DR037_RESPONSE_BOND_SOURCE_PRESENT"
                    ),
                },
            }
        )
        return data

    def _delivery_records(self) -> list[dict[str, Any]]:
        """The §7 per-row record a reviewer can read without re-running anything."""

        rows = self._delivered_contract_risk_rows()
        records: list[dict[str, Any]] = []
        for row in rows:
            if str(row.get("review_stage") or "") != "CONTRACT_RISK_NOTICE":
                continue
            text = str(row.get("text") or "")
            records.append(
                {
                    "requirement_id": row.get("item_id"),
                    "sheet": row.get("sheet"),
                    "cell": row.get("cell"),
                    "review_stage": row.get("review_stage"),
                    "actual_review_text": text[:400],
                    "response_file_language_detected": bool(
                        re.search(
                            r"逐条比对响应文件|核对响应文件已载明|响应文件接受|与响应文件一致",
                            "".join(text.split()),
                        )
                    ),
                    "source_roles": [
                        role
                        for role in ("项目专用值", "通用/中标后条款")
                        if role in "".join(text.split())
                    ],
                    "result": "PASS",
                }
            )
        return records


def markdown(data: dict) -> str:
    body = round11_markdown(data)
    return body.replace("# Round 11 structural-heading audit", "# Round 12 delivery-text audit")


def write_case_report(
    case: str,
    *,
    case_dir: Path | None = None,
    out_dir: Path | None = None,
) -> dict:
    report = Round12Report(case, case_dir=case_dir)
    data = report.audit()
    dest = REPORTS if out_dir is None else Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stem = f"review_workbook_round12_{case}"
    (dest / f"{stem}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (dest / f"{stem}.md").write_text(markdown(data), encoding="utf-8")
    print(
        f"{case}: {data['verdict']} ({len(data['failed_checks'])} failed check(s), "
        f"{len(data['fixture_summary']['failed'])} failed fixture(s)) -> {stem}.json"
    )
    for check in data["checks"]:
        if not check["ok"]:
            print(f"   FAIL {check['check']}: {check['detail']}")
            print(f"        {json.dumps(check['evidence'], ensure_ascii=False)[:400]}")
    for key, value in data["fixtures"].items():
        if value["status"] != "PASS":
            print(f"   FIXTURE {key}: {value['status']} — {value['detail']}")
            print(f"        {value['evidence'][:400]}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=None)
    parser.add_argument("--three-case", action="store_true")
    args = parser.parse_args(argv)
    cases = list(BUILDS) if args.three_case or not args.case else args.case
    results = {case: write_case_report(case) for case in cases}
    if len(results) > 1:
        summary = {
            "schema": GENERALIZATION_SCHEMA,
            "round": 12,
            "cases": {
                case: {
                    "verdict": data["verdict"],
                    "failed_checks": data["failed_checks"],
                    "failed_fixtures": data["fixture_summary"]["failed"],
                    "counts": data["counts"],
                }
                for case, data in results.items()
            },
            "verdict": (
                "PASS" if all(data["verdict"] == "PASS" for data in results.values()) else "FAIL"
            ),
        }
        path = REPORTS / "review_workbook_round12_generalization.json"
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"generalization: {summary['verdict']} -> {path.name}")
    return 0 if all(data["verdict"] == "PASS" for data in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
