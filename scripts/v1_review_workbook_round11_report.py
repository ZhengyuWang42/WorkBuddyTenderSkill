"""Round 11: canonical EvidenceUnit structural-heading fidelity.

The exact-formatter gate (round 9) proves only that the delivered locator equals
the formatter's output for the canonical ``EvidenceUnit``.  It cannot prove that
the unit itself is the source unit that *owns* the requirement.  Human review of
workbook10 found three such upstream defects:

* the authorization row cited ``3.3 响应文件的澄清和补正`` although 81% of its
  text is clause ``3.7.3`` of the supplier-instructions chapter;
* the contract-termination row promoted a body sentence
  ("合同解除或乙方应当退换的……") into its section field;
* clauses under **第五条** cited **第六条** because a contract *article* title was
  never recognised as a structural heading.

Round 11 closes the upstream chain:

    SOURCE_ATOM -> actual PDF structural container -> canonical EvidenceUnit
                -> formatter -> saved XLSX

and it also closes two delivered-text defects found in the same review: duplicated
extraction wording in the evidence summary ("资格要求 格要求") and a standards
identifier cut in half ("GB50015-2").

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_round11_report.py --three-case
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

from tender_basic.evidence_unit import build_evidence_units  # noqa: E402
from tender_basic.structural_heading import (  # noqa: E402
    check_structural_heading_fidelity,
    container_is_structural,
)
from v1_review_workbook_round8_report import REPORTS  # noqa: E402
from v1_review_workbook_round9_report import (  # noqa: E402
    Round9Report,
    markdown as round9_markdown,
)

SCHEMA = "v1_review_workbook_round11/1"
GENERALIZATION_SCHEMA = "v1_review_workbook_round11_generalization/1"

#: round-11 successor build per case (structural-heading closure)
BUILDS: dict[str, str] = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook11",
    "case_002": "v1_round4_closure9_review_workbook11",
    "case_003": "v1_round4_closure9_review_workbook11",
}

#: Wording the extraction emitted twice because it wrapped mid-word.
#:
#: The defect is a repeat with **no separator** ("…的资 格要求 格要求", "…营业 执照 执照"):
#: the extractor printed the tail of the wrapped token twice.  A repeat separated by
#: a space is the source's own label-then-value layout ("*3.4.1 响应保证金 响应保证金的
#: 金额：…", "履约保证金 履约保证金的金额：…") and is *not* an artifact, so it is not
#: counted.
_DUPLICATED_SOURCE_RES = (
    re.compile(r"([\u4e00-\u9fa5]{2,8})\1(?![\u4e00-\u9fa5])"),
)

#: A source identifier that must never be cut in half (a standard, a URL).
_OPEN_TOKEN_RE = re.compile(r"[A-Za-z]{1,6}\s*/?\s*T?\s*\d[\d.\-/]*$|[A-Za-z]+://\S*$|\d[\d.\-/]{3,}$")


class Round11Report(Round9Report):
    """The round-9 audits bound to the round-11 successor, plus the structural gate."""

    def __init__(self, case: str, *, case_dir: Path | None = None) -> None:
        from v1_review_workbook_round8_report import Round8Report

        Round8Report.__init__(self, case, case_dir=case_dir, build_name=BUILDS[case])
        self.items = list(self.r4.items)
        self.background = list(self.r4.background)
        self.by_item = {
            str(item.item_id): item for item in [*self.items, *self.background]
        }

    # -- structural source fidelity ---------------------------------------- #

    def audit(self) -> dict[str, Any]:
        """Round-9 audits plus the round-11 structural-heading closure."""

        data = super().audit()
        self.check_structural_heading()
        self.check_duplicated_source_wording()
        self.check_evidence_summary_truncation()
        self.check_multi_source_roles()
        failed = [check.name for check in self.checks if not check.ok]
        failed_fixtures = [
            key for key, value in self.fixtures.items() if value["status"] != "PASS"
        ]
        data.update(
            {
                "schema": SCHEMA,
                "round": 11,
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
            }
        )
        return data

    def _unit_records(self) -> list[dict[str, Any]]:
        """One record per delivered row: its canonical unit and source position."""

        units = {unit.unit_id: unit for unit in build_evidence_units(self.document)}
        records: list[dict[str, Any]] = []
        for item in self.items:
            primary = next(
                (
                    unit
                    for unit in (getattr(item, "evidence_units", ()) or ())
                    if str(unit.get("role")) == "PRIMARY"
                ),
                None,
            )
            if primary is None:
                continue
            unit = units.get(str(primary.get("unit_id") or ""))
            if unit is None:
                continue
            records.append(
                {
                    "item_id": str(item.item_id),
                    "concern_id": str(item.concern_id or ""),
                    "page": unit.page,
                    "block_index": unit.block_index,
                    "row_index": unit.row_index,
                    "unit_id": unit.unit_id,
                    "unit_heading": str(unit.heading or unit.semantic_heading or ""),
                    "unit_clause": str(unit.clause_number or ""),
                    "requirement": str(item.source_requirement or ""),
                    "locator": str(item.source_locator or ""),
                }
            )
        return records

    def check_structural_heading(self) -> None:
        """The canonical unit's heading must be the source's own container."""

        records = self._unit_records()
        result = check_structural_heading_fidelity(self.document, records)
        self.counts["BODY_PROSE_HEADING_COUNT"] = result["body_prose_heading_count"]
        self.counts["FOREIGN_STRUCTURAL_HEADING_COUNT"] = result["foreign_heading_count"]
        self.check(
            "no canonical evidence unit carries body prose as its section",
            result["body_prose_heading_count"] == 0,
            f"{result['checked']} unit(s) compared with the source's own container, "
            f"{result['body_prose_heading_count']} body-prose heading(s)",
            {"problems": result["heading_not_structural"][:8]},
        )
        # a *foreign* container is reported as its own measurement: it is what the
        # round-11 human fixtures found (clauses under 第五条 citing 第六条)
        self.check(
            "every canonical evidence unit names the source container that owns it",
            result["foreign_heading_count"] == 0,
            f"{result['checked']} unit(s) compared with the source's own container, "
            f"{result['foreign_heading_count']} foreign container(s)",
            {"problems": result["heading_foreign"][:8]},
        )

    def check_duplicated_source_wording(self) -> None:
        """No delivered requirement or evidence summary repeats a wrapped word."""

        problems: list[dict[str, Any]] = []
        for row in self.fixture_rows():
            for field in ("requirement", "excerpt"):
                text = str(row.get(field) or "")
                for pattern in _DUPLICATED_SOURCE_RES:
                    match = pattern.search(text)
                    if match:
                        problems.append(
                            {
                                "item_id": row.get("item_id"),
                                "field": field,
                                "phrase": match.group(0)[:40],
                            }
                        )
                        break
        self.counts["DUPLICATED_SOURCE_FRAGMENT_COUNT"] = len(problems)
        self.check(
            "no delivered cell repeats a phrase the extraction emitted twice",
            not problems,
            f"{len(self.fixture_rows())} row(s) checked, {len(problems)} duplicated fragment(s)",
            {"problems": problems[:8]},
        )

    def check_evidence_summary_truncation(self) -> None:
        """An evidence summary may not end inside a source identifier."""

        problems: list[dict[str, Any]] = []
        for row in self.fixture_rows():
            excerpt = str(row.get("excerpt") or "").strip()
            if not excerpt.endswith("…"):
                continue  # not truncated at all
            head = excerpt[:-1].rstrip()
            tail = head[-24:]
            if _OPEN_TOKEN_RE.search(tail):
                problems.append(
                    {
                        "item_id": row.get("item_id"),
                        "tail": tail,
                    }
                )
        self.counts["MID_TOKEN_EVIDENCE_TRUNCATION_COUNT"] = len(problems)
        self.check(
            "a clipped evidence summary never ends inside a source identifier",
            not problems,
            f"{len(self.fixture_rows())} evidence summary(ies) checked, "
            f"{len(problems)} mid-token truncation(s)",
            {"problems": problems[:8]},
        )

    def check_multi_source_roles(self) -> None:
        """A two-source row names both sources; an anchor never cites a hidden page."""

        problems: list[dict[str, Any]] = []
        checked = 0
        for item in self.items:
            units = list(getattr(item, "evidence_units", ()) or ())
            linked = [unit for unit in units if str(unit.get("role")) == "LINKED"]
            if not linked:
                continue
            checked += 1
            locator = str(item.source_locator or "")
            own = re.search(r"第(\d+)页", locator)
            own_page = own.group(1) if own else ""
            action = str(item.verification_action or "")
            # every page the action cites that is not the row's own evidence page
            # must be introduced as an explicit second source
            for page in re.findall(r"依据第(\d+)页", action):
                if own_page and page == own_page:
                    continue
                if f"依据第{page}页核对另一来源条款" in action:
                    continue
                problems.append(
                    {
                        "item_id": item.item_id,
                        "action_page": page,
                        "own_page": own_page,
                        "locator": locator[:80],
                    }
                )
        self.counts["MULTI_SOURCE_EVIDENCE_ROLE_AMBIGUITY_COUNT"] = len(problems)
        self.check(
            "a multi-source row states each source role explicitly",
            not problems,
            f"{checked} multi-source row(s) checked, {len(problems)} ambiguous anchor(s)",
            {"problems": problems[:8]},
        )

    # -- human fixtures ----------------------------------------------------- #

    def audit_fixtures(self, rows, price_result) -> None:
        super().audit_fixtures(rows, price_result)
        if self.case != "case_001":
            return
        because = {str(row.get("item_id")): row for row in rows if row.get("item_id")}

        def fixture_row(concern_id: str):
            for row in rows:
                item = row.get("item")
                if item is not None and str(getattr(item, "concern_id", "")) == concern_id:
                    return row
            return None

        # fixture 1: the authorization row cites the clause that carries its text
        authorization = fixture_row("AUTHORIZATION")
        locator = str((authorization or {}).get("locator") or "")
        self.fixture(
            "E47_AUTHORIZATION_HEADING",
            bool(authorization)
            and "3.7" in locator
            and "响应文件的编制" in locator
            and "澄清和补正" not in locator,
            "E47 the authorization row cites the clause that carries the requirement",
            f"row={(authorization or {}).get('item_id')} locator={locator[:120]}",
        )

        # fixture 2: no contract-risk row promotes body prose into its section
        termination = fixture_row("CONTRACT_TERMINATION_REFUND")
        term_locator = str((termination or {}).get("locator") or "")
        self.fixture(
            "E57_CONTRACT_TERMINATION_HEADING",
            bool(termination)
            and "第七条" in term_locator
            and "合同解除或乙方应当退换" not in term_locator,
            "E57 the termination row uses the article heading, not its own body prose",
            f"row={(termination or {}).get('item_id')} locator={term_locator[:120]}",
        )

        # fixtures 3 / 4: the delivered cells carry no duplicated or cut source text
        duplicated = []
        truncated = []
        for row in rows:
            for field in ("requirement", "excerpt"):
                text = str(row.get(field) or "")
                for pattern in _DUPLICATED_SOURCE_RES:
                    match = pattern.search(text)
                    if match:
                        duplicated.append((row.get("item_id"), field, match.group(0)[:24]))
                        break
            excerpt = str(row.get("excerpt") or "").strip()
            if excerpt.endswith("…"):
                tail = excerpt[:-1].rstrip()[-24:]
                if _OPEN_TOKEN_RE.search(tail):
                    truncated.append((row.get("item_id"), tail))
        self.fixture(
            "DUPLICATED_EXTRACTION_TEXT",
            not duplicated,
            "the delivered workbook states each wrapped phrase once",
            f"problems={duplicated[:5]}",
        )
        self.fixture(
            "E38_STANDARDS_NOT_CUT_MID_TOKEN",
            not truncated,
            "E38 the standards evidence is not clipped inside a standard identifier",
            f"problems={truncated[:5]}",
        )

        # fixture 5: the performance-bond row explains its second source
        bond = fixture_row("PERFORMANCE_BOND")
        bond_action = str((bond or {}).get("action") or "")
        bond_locator = str((bond or {}).get("locator") or "")
        own = re.search(r"第(\d+)页", bond_locator)
        own_page = own.group(1) if own else ""
        other_pages = [
            page
            for page in re.findall(r"依据第(\d+)页", bond_action)
            if page != own_page
        ]
        # every page the action cites other than the row's own evidence page must
        # be introduced as an explicit *second source*, not left unexplained
        unexplained = [
            page
            for page in other_pages
            if f"依据第{page}页核对另一来源条款" not in bond_action
        ]
        self.fixture(
            "DR037_MULTI_SOURCE_ROLES",
            bool(bond) and bool(other_pages) and not unexplained,
            "DR037 names both of its sources instead of citing a hidden page",
            f"row={(bond or {}).get('item_id')} locator={bond_locator[:80]} "
            f"own_page={own_page} other_pages={other_pages} "
            f"unexplained={unexplained} action={bond_action[:200]}",
        )

        # fixture 6: the two clauses under 第五条 keep that article
        for key, concern_id in (
            ("DR048_SOURCE_HEADING", "DELIVERY_ACCEPTANCE_COMPLETION"),
            ("DR052_SOURCE_HEADING", "PRICE_INCLUDED_COST_SCOPE"),
        ):
            row = fixture_row(concern_id)
            locator = str((row or {}).get("locator") or "")
            self.fixture(
                key,
                bool(row) and "第五条" in locator and "第六条" not in locator,
                f"{key} cites the article that owns the clause",
                f"row={(row or {}).get('item_id')} concern={concern_id} locator={locator[:120]}",
            )


def markdown(data: dict) -> str:
    body = round9_markdown(data)
    return body.replace("# Round 9 delivered-content audit", "# Round 11 structural-heading audit")


def write_case_report(case: str, *, case_dir: Path | None = None) -> dict:
    report = Round11Report(case, case_dir=case_dir)
    data = report.audit()
    data["schema"] = SCHEMA
    data["round"] = 11
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = f"review_workbook_round11_{case}"
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
            "round": 11,
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
        path = REPORTS / "review_workbook_round11_generalization.json"
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"generalization: {summary['verdict']} -> {path.name}")
    return 0 if all(data["verdict"] == "PASS" for data in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
