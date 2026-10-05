"""Round 10: bid response vs contract risk separation.

The human product decision this round delivers:

    报价/商务响应 = 投标响应项
    合同条款     = 投标前风险识别项

A pure post-award contract condition must not affect bid compliance, rejection or
scoring; it exists so the bid team knows the commercial risk before submitting.
Round 10 therefore adds one derived attribute -- the row's **review stage** -- and
delivers the two stages in separate modules with different vocabularies.

Nothing about the round-5..9 provenance / concern / evidence-unit / locator
architecture is reopened: the stage is derived from the concern that already owns
the row and is asserted against the SAVED workbook.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_round10_report.py --three-case
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from v1_review_workbook_round8_report import REPORTS  # noqa: E402
from v1_review_workbook_round9_report import (  # noqa: E402
    Round9Report,
    markdown as round9_markdown,
)

SCHEMA = "v1_review_workbook_round10/1"
GENERALIZATION_SCHEMA = "v1_review_workbook_round10_generalization/1"

#: round-10 successor build per case (the review-stage separation round)
BUILDS: dict[str, str] = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook10",
    "case_002": "v1_round4_closure9_review_workbook10",
    "case_003": "v1_round4_closure9_review_workbook10",
}


class Round10Report(Round9Report):
    """The round-9 audits, bound to the round-10 successor."""

    def __init__(self, case: str, *, case_dir: Path | None = None) -> None:
        # Bind the round-10 successor through the round-8 constructor (which owns
        # the build/case wiring) while keeping every round-9 check method: the
        # round-9 evidence and its BUILDS mapping are never touched.
        from v1_review_workbook_round8_report import Round8Report

        Round8Report.__init__(self, case, case_dir=case_dir, build_name=BUILDS[case])
        self.items = list(self.r4.items)
        self.background = list(self.r4.background)
        self.by_item = {
            str(item.item_id): item for item in [*self.items, *self.background]
        }


def markdown(data: dict) -> str:
    body = round9_markdown(data)
    return body.replace("# Round 9 delivered-content audit", "# Round 10 review-stage audit")


def write_case_report(case: str, *, case_dir: Path | None = None) -> dict:
    report = Round10Report(case, case_dir=case_dir)
    data = report.audit()
    data["schema"] = SCHEMA
    data["round"] = 10
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = f"review_workbook_round10_{case}"
    (REPORTS / f"{stem}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (REPORTS / f"{stem}.md").write_text(markdown(data), encoding="utf-8")
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


#: round-11 successor build per case (the evidence-unit structural-heading round)
BUILDS11: dict[str, str] = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook11",
    "case_002": "v1_round4_closure9_review_workbook11",
    "case_003": "v1_round4_closure9_review_workbook11",
}


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
            "round": 10,
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
        path = REPORTS / "review_workbook_round10_generalization.json"
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"generalization: {summary['verdict']} -> {path.name}")
    return 0 if all(data["verdict"] == "PASS" for data in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
