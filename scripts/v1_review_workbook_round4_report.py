"""Round-4 rendered-component provenance report and rendered-output gate.

Round 3 proved concern ownership inside the model objects.  Round 4 makes the
*rendered workbook* the contract: every material phrase that reaches an XLSX
cell must be produced by a concern-owned ``RenderedReviewComponent``.

This script therefore

* rebuilds the review plan from the build's accepted ``normalized_document``
  and ``project_facts`` (no Word re-render happens here),
* reads the FINAL cell values of the built workbook,
* maps every rendered component to the exact cell that displays it,
* re-checks the rendered text of every cell (delivered sheet, clause view,
  mandatory view) against the component that must have produced it,
* evaluates the human fixtures A..S against the frozen cell text,
* runs the 30-cell CASE001 final-cell audit and persists the sampled addresses
  with their displayed text, and
* records the retained numeric invariants (project warranty, retention money
  ratio, retention release period) and the platform-role separation.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_round4_report.py \
        --build acceptance/workspace/case_001/<round4 build> --case case_001 \
        --before acceptance/workspace/case_001/<round3 build> \
        --out acceptance/reports/v1_generalization/case001_review_workbook_round4.json \
        --md acceptance/reports/v1_generalization/case001_review_workbook_round4.md \
        --provenance acceptance/reports/v1_generalization/\
review_workbook_round4_rendered_component_provenance_case_001.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from openpyxl import load_workbook  # noqa: E402

from tender_basic.document_models import NormalizedDocument  # noqa: E402
from tender_basic.dynamic_review import (  # noqa: E402
    build_dynamic_review_plan,
    dynamic_review_qa,
    order_review_items,
)
from tender_basic.models import ProjectFacts  # noqa: E402
from tender_basic.review_concern import concern_spec  # noqa: E402
from tender_basic.review_rendering import (  # noqa: E402
    COMPONENT_KINDS,
    EVIDENCE_SUMMARY,
    FAILURE_CONSEQUENCE,
    LINKED_FACT,
    NUMERIC_STATEMENT,
    PASS_CRITERION,
    PREPARATION_MATERIAL,
    REVIEW_CHECK,
    SCORING_GUIDANCE,
    SOURCE_REQUIREMENT,
    foreign_terms,
    mismatch_counts,
    normalize,
    numeric_tokens,
    provenance_map,
)

DELIVERED_SHEET = "投标项目复核表"
CLAUSE_SHEET = "02_关键条款"
MANDATORY_SHEET = "03_资格否决与强制项"
FACT_SHEET = "01_项目事实"
CONFLICT_SHEET = "06_冲突与缺失"
PRICE_SHEET = "04_报价与限价"

LEGACY_FIRST_ROW = 9
LEGACY_TEXT_COLUMN = 4  # D
LEGACY_EVIDENCE_COLUMN = 5  # E
LEGACY_NOTE_COLUMN = 13  # M

#: Blocks the delivered cell renders and the component kind behind each.
CELL_BLOCK_ORDER = (
    (SOURCE_REQUIREMENT, "招标文件要求："),
    (REVIEW_CHECK, "复核要点：\n"),
    (PASS_CRITERION, "通过标准：\n"),
    (FAILURE_CONSEQUENCE, "不满足后果："),
    (PREPARATION_MATERIAL, "准备材料："),
    (SCORING_GUIDANCE, "评分提示："),
)

#: Component kinds that must be visible in a final cell somewhere.
RENDERED_KINDS = (
    SOURCE_REQUIREMENT,
    REVIEW_CHECK,
    PASS_CRITERION,
    FAILURE_CONSEQUENCE,
    PREPARATION_MATERIAL,
    SCORING_GUIDANCE,
    NUMERIC_STATEMENT,
    EVIDENCE_SUMMARY,
    LINKED_FACT,
)

#: Wording that may never be rendered (round-4 retention/scoring separation).
FORBIDDEN_RENDERED = {
    "项目质保期不低于12个月": "12-month retention release presented as the project warranty",
    "质保期不低于12个月": "12-month retention release presented as the project warranty",
    "质保期不低于 12个月": "12-month retention release presented as the project warranty",
    "付款比例为5%": "5% retention money presented as a payment/scoring ratio",
    "付款/计分比例为5%": "5% retention money presented as a payment/scoring ratio",
    "计分比例为5%": "5% retention money presented as a scoring ratio",
    "付款/计分比例为 5%": "5% retention money presented as a payment/scoring ratio",
}

RETENTION_WARRANTY_PHRASES = (
    "项目质保期不低于12个月",
    "质保期不低于12个月",
    "质保期不低于 12个月",
)

#: 12-month-release wording that must never be presented as the project warranty.
WARRANTY_MONTHS = "24个月"
RETENTION_RATIO = "5%"
RETENTION_RELEASE = "12个月"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cell_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


@dataclass
class FinalRow:
    """One delivered-sheet row with its final displayed cell text."""

    item_id: str
    concern_id: str
    row: int
    d_address: str
    d_text: str
    e_address: str
    e_text: str
    m_address: str
    m_text: str


@dataclass
class FinalCells:
    """Read-only view of the FINAL workbook values."""

    path: Path
    sheets: dict[str, list[list[str]]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "FinalCells":
        workbook = load_workbook(path, data_only=True, read_only=True)
        try:
            sheets: dict[str, list[list[str]]] = {}
            for name in workbook.sheetnames:
                worksheet = workbook[name]
                rows: list[list[str]] = []
                for row in worksheet.iter_rows(values_only=True):
                    rows.append([cell_text(value) for value in row])
                sheets[name] = rows
            return cls(path=path, sheets=sheets)
        finally:
            workbook.close()

    def value(self, sheet: str, row: int, column: int) -> str:
        rows = self.sheets.get(sheet) or []
        if row - 1 >= len(rows):
            return ""
        values = rows[row - 1]
        return values[column - 1] if column - 1 < len(values) else ""

    def address(self, sheet: str, row: int, column: int) -> str:
        return f"{sheet}!{_column_letter(column)}{row}"

    def legacy_rows(self) -> list[FinalRow]:
        rows: list[FinalRow] = []
        sheet = self.sheets.get(DELIVERED_SHEET) or []
        for index, values in enumerate(sheet[LEGACY_FIRST_ROW - 1 :], start=LEGACY_FIRST_ROW):
            d_text = values[LEGACY_TEXT_COLUMN - 1] if len(values) >= LEGACY_TEXT_COLUMN else ""
            if not d_text:
                continue
            m_text = values[LEGACY_NOTE_COLUMN - 1] if len(values) >= LEGACY_NOTE_COLUMN else ""
            e_text = (
                values[LEGACY_EVIDENCE_COLUMN - 1] if len(values) >= LEGACY_EVIDENCE_COLUMN else ""
            )
            type_match = re.search(r"类型：\s*([^/；\s]+)\s*/\s*([^；]*)", m_text)
            rows.append(
                FinalRow(
                    item_id="",
                    concern_id="",
                    row=index,
                    d_address=f"{DELIVERED_SHEET}!D{index}",
                    d_text=d_text,
                    e_address=f"{DELIVERED_SHEET}!E{index}",
                    e_text=e_text,
                    m_address=f"{DELIVERED_SHEET}!M{index}",
                    m_text=m_text,
                )
            )
        return rows

    def sheet_rows(self, sheet: str) -> list[list[str]]:
        return self.sheets.get(sheet) or []

    def all_cells(self, sheets: Iterable[str]) -> Iterable[tuple[str, str]]:
        for sheet in sheets:
            for index, values in enumerate(self.sheet_rows(sheet), start=1):
                for column, value in enumerate(values, start=1):
                    if value:
                        yield self.address(sheet, index, column), value


def _column_letter(column: int) -> str:
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _flat(text: object) -> str:
    return normalize(text)


def _contains(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return _flat(needle) in _flat(haystack)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.name,
            "ok": bool(self.ok),
            "detail": self.detail,
            "evidence": self.evidence,
        }


class Round4Report:
    def __init__(
        self,
        build: Path,
        case: str,
        before: Path | None = None,
        audit_limit: int = 30,
    ) -> None:
        self.build = build
        self.case = case
        self.before = before
        self.audit_limit = audit_limit
        self.facts = ProjectFacts.model_validate_json(
            (build / "project_facts.json").read_text(encoding="utf-8")
        )
        self.document = NormalizedDocument.model_validate_json(
            (build / "normalized_document.json").read_text(encoding="utf-8")
        )
        self.plan = build_dynamic_review_plan(self.document, self.facts)
        self.qa = dynamic_review_qa(self.plan, self.document, self.facts)
        self.workbook_path = build / "投标项目复核表.xlsx"
        self.cells = FinalCells.load(self.workbook_path)
        self.items = list(order_review_items(self.plan.items))
        self.background = list(self.plan.background_items)
        self.checks: list[Check] = []
        self.rows_by_item: dict[str, FinalRow] = {}
        self._bind_rows()

    # -- binding --------------------------------------------------------- #

    def _bind_rows(self) -> None:
        """Bind plan items to delivered-sheet rows by their rendered cell text."""

        sheet_rows = [row for row in self.cells.legacy_rows() if row.d_text]
        unmatched = list(sheet_rows)
        for item in self.items:
            target = _flat(item.cell_text)
            match = next((row for row in unmatched if _flat(row.d_text) == target), None)
            if match is None:
                # tolerate whitespace-only drift
                match = next(
                    (row for row in unmatched if _flat(row.d_text)[:120] == target[:120]), None
                )
            if match is None:
                continue
            unmatched.remove(match)
            match.item_id = item.item_id
            match.concern_id = item.concern_id
            self.rows_by_item[item.item_id] = match

    # -- helpers --------------------------------------------------------- #

    def check(self, name: str, ok: bool, detail: str, evidence: dict | None = None) -> None:
        self.checks.append(Check(name=name, ok=bool(ok), detail=detail, evidence=evidence or {}))

    def _item_texts(self, item) -> list[str]:
        return [str(component["rendered_text"]) for component in item.rendered_components]

    def _find(self, *concern_ids: str):
        """First delivered item of any of ``concern_ids`` (round-5 renames)."""

        wanted = set(concern_ids)
        return next((item for item in self.items if item.concern_id in wanted), None)

    def _component_texts(self, item, kind: str) -> list[str]:
        return [
            str(component["rendered_text"])
            for component in item.rendered_components
            if component["component_kind"] == kind
        ]

    def _mismatch_counts(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for item in list(self.items) + list(self.background):
            counts = mismatch_counts(
                [
                    _component_from_dict(payload)
                    for payload in item.rendered_components
                ]
            )
            for key, value in counts.items():
                totals[key] = totals.get(key, 0) + int(value)
        totals.setdefault("rendered_component_concern_mismatch_total", 0)
        return totals

    # -- rendered-output gate -------------------------------------------- #

    def check_structure(self) -> None:
        missing = [item.item_id for item in self.items if item.item_id not in self.rows_by_item]
        self.check(
            "delivered_rows_bound_to_plan_items",
            not missing,
            f"{len(self.rows_by_item)}/{len(self.items)} delivered review rows bound to plan items",
            {"unbound_item_ids": missing[:10]},
        )

        mismatched_cells: list[dict[str, str]] = []
        for item in self.items:
            row = self.rows_by_item.get(item.item_id)
            if row is None:
                continue
            if _flat(row.d_text) != _flat(item.cell_text):
                mismatched_cells.append(
                    {"item_id": item.item_id, "cell": row.d_address, "reason": "cell_text_drift"}
                )
        self.check(
            "rendered_cell_equals_component_projection",
            not mismatched_cells,
            f"{len(self.items) - len(mismatched_cells)}/{len(self.items)} delivered D cells are "
            "the exact projection of their verified components",
            {"mismatched": mismatched_cells[:10]},
        )

    def check_component_ownership(self) -> None:
        counts = self._mismatch_counts()
        unverified: list[dict[str, str]] = []
        for item in list(self.items) + list(self.background):
            for component in item.rendered_components:
                if not component["ownership_verified"]:
                    unverified.append(
                        {
                            "item_id": item.item_id,
                            "concern_id": item.concern_id,
                            "component_kind": str(component["component_kind"]),
                            "foreign_terms": ",".join(component["foreign_terms"]),
                            "rendered_text": str(component["rendered_text"])[:120],
                        }
                    )
        self.check(
            "rendered_component_ownership_verified",
            not unverified,
            f"{self.qa['rendered_component_count']} rendered components verified concern-owned",
            {"unverified_count": len(unverified), "unverified": unverified[:10]},
        )
        self.check(
            "rendered_component_concern_mismatch_total_zero",
            int(counts["rendered_component_concern_mismatch_total"]) == 0,
            "total rendered-component concern mismatch is 0",
            {"counts": counts},
        )
        for kind in COMPONENT_KINDS:
            key = f"rendered_{kind.lower()}_concern_mismatch"
            self.check(
                key,
                int(counts.get(key, 0)) == 0,
                f"{kind} mismatch count is 0",
                {"count": int(counts.get(key, 0))},
            )

    def check_rendered_cells_owned(self) -> None:
        """Every rendered component must be visible in a final cell."""

        searchable = [
            (address, text)
            for address, text in self.cells.all_cells(
                [DELIVERED_SHEET, CLAUSE_SHEET, MANDATORY_SHEET, PRICE_SHEET, CONFLICT_SHEET]
            )
        ]
        hidden: list[dict[str, str]] = []
        cell_index: dict[str, str] = {}
        checked = 0
        for item in self.items:
            for component in item.rendered_components:
                kind = str(component["component_kind"])
                if kind not in RENDERED_KINDS:
                    continue
                checked += 1
                text = str(component["rendered_text"])
                if kind == LINKED_FACT:
                    keys = [str(key) for key in component["linked_fact_keys"]]
                    found = next(
                        (
                            address
                            for address, value in searchable
                            if "关联事实" in _flat(value)
                            and all(_flat(key) in _flat(value) for key in keys)
                        ),
                        "",
                    )
                    if found:
                        cell_index[str(component["component_id"])] = found
                    if not found:
                        hidden.append(
                            {
                                "item_id": item.item_id,
                                "component_kind": kind,
                                "rendered_text": text[:120],
                            }
                        )
                    continue
                probe = _flat(text)
                if kind in (REVIEW_CHECK, PASS_CRITERION, NUMERIC_STATEMENT):
                    # rendered through a check/criterion line, possibly with a
                    # bullet mark or a leading instruction
                    probe = re.sub(r"^核对响应文件已载明：", "", probe)
                probe = probe[:60]
                found = next((address for address, value in searchable if probe in _flat(value)), "")
                if not found:
                    hidden.append(
                        {
                            "item_id": item.item_id,
                            "component_kind": kind,
                            "rendered_text": text[:120],
                        }
                    )
                else:
                    cell_index[str(component["component_id"])] = found
        self.check(
            "every_rendered_component_present_in_final_cell",
            not hidden,
            f"{checked} rendered components of {len(self.items)} bidder-facing rows are displayed "
            "by a final workbook cell",
            {"not_rendered": hidden[:10], "checked": checked},
        )
        self._cell_index = cell_index

    def check_view_cells_consistent(self) -> None:
        """Clause/mandatory view cells must repeat the plan's rendered text."""

        clause_rows = self.cells.sheet_rows(CLAUSE_SHEET)
        mandatory_rows = self.cells.sheet_rows(MANDATORY_SHEET)
        stale: list[dict[str, str]] = []

        def text_at(rows: Sequence[Sequence[str]], row: int, column: int) -> str:
            if row - 1 >= len(rows):
                return ""
            values = rows[row - 1]
            return values[column - 1] if column - 1 < len(values) else ""

        for index, item in enumerate([i for i in self.items], start=2):
            if index - 1 >= len(clause_rows):
                break
            requirement = text_at(clause_rows, index, 2)
            if requirement != item.item_id:
                continue
            for column, expected_list in (
                (4, [item.source_requirement]),
                (5, [line for line in item.verification_action.split("\n")]),
                (6, [line for line in item.pass_criteria.split("\n")]),
                (12, [str(item.source_evidence)[:300]]),
            ):
                displayed = text_at(clause_rows, index, column)
                for expected in expected_list:
                    line = expected.strip("；; ")
                    if not line:
                        continue
                    if _flat(line)[:40] and _flat(line)[:40] not in _flat(displayed) and _flat(displayed):
                        # display joins bullets; require each line to be present
                        stripped = re.sub(r"^[①②③④⑤⑥⑦⑧⑨·\s]+", "", line)
                        if stripped and _flat(stripped)[:30] not in _flat(displayed):
                            stale.append(
                                {
                                    "sheet": CLAUSE_SHEET,
                                    "item_id": item.item_id,
                                    "cell": self.cells.address(CLAUSE_SHEET, index, column),
                                    "expected": line[:60],
                                    "displayed": displayed[:60],
                                }
                            )
        for index, item in enumerate([i for i in self.items], start=2):
            if index - 1 >= len(mandatory_rows):
                break
            requirement = text_at(mandatory_rows, index, 2)
            if requirement != item.item_id:
                continue
            for column, expected in (
                (5, item.source_requirement),
                (7, item.pass_criteria),
                (13, str(item.source_evidence)[:300]),
            ):
                displayed = text_at(mandatory_rows, index, column)
                stripped = re.sub(r"^[①②③④⑤⑥⑦⑧⑨·\s]+", "", expected.strip())
                if stripped and _flat(stripped)[:30] and _flat(stripped)[:30] not in _flat(displayed):
                    stale.append(
                        {
                            "sheet": MANDATORY_SHEET,
                            "item_id": item.item_id,
                            "cell": self.cells.address(MANDATORY_SHEET, index, column),
                            "expected": stripped[:60],
                            "displayed": displayed[:60],
                        }
                    )
        self.check(
            "view_cells_repeat_rendered_components",
            not stale,
            "clause/mandatory view cells repeat the concern-owned rendered text",
            {"stale_cells": stale[:10], "stale_count": len(stale)},
        )

    def check_foreign_text_absent(self) -> None:
        """No cell may carry wording that a different concern owns."""

        searchable = list(
            self.cells.all_cells([DELIVERED_SHEET, CLAUSE_SHEET, MANDATORY_SHEET])
        )
        family_terms = {
            "RETENTION_RELEASE_PERIOD": ("质保金释放", "无息付清余款"),
            "PROJECT_WARRANTY": ("项目质保期",),
        }
        hits: list[dict[str, str]] = []
        for address, text in searchable:
            for phrase, reason in FORBIDDEN_RENDERED.items():
                if _flat(phrase) in _flat(text):
                    hits.append({"cell": address, "phrase": phrase, "reason": reason})
        self.check(
            "forbidden_retention_wording_absent",
            not hits,
            "no cell presents the 12-month release period as the project warranty or the "
            "5% retention money as a payment/scoring ratio",
            {"hits": hits[:10]},
        )
        self._family_terms = family_terms

    def check_numeric_invariants(self) -> None:
        by_concern: dict[str, list[str]] = {}
        for item in self.items:
            by_concern.setdefault(item.concern_id, []).append(item.item_id)
        rows = {item.item_id: item for item in self.items}
        evidence: dict[str, Any] = {}

        def row_text(concern_id: str) -> str:
            return " ".join(
                self.rows_by_item[item_id].d_text
                for item_id in by_concern.get(concern_id, [])
                if item_id in self.rows_by_item
            )

        warranty_items = [rows[i] for i in by_concern.get("PROJECT_WARRANTY", []) if i in rows]
        ratio_items = [
            rows[i] for i in by_concern.get("RETENTION_MONEY_RATIO", []) if i in rows
        ]
        release_items = [
            rows[i] for i in by_concern.get("RETENTION_RELEASE_PERIOD", []) if i in rows
        ]
        warranty_text = row_text("PROJECT_WARRANTY")
        ratio_text = row_text("RETENTION_MONEY_RATIO")
        release_text = row_text("RETENTION_RELEASE_PERIOD")
        evidence = {
            "case": self.case,
            "project_warranty_rows": [item.item_id for item in warranty_items],
            "project_warranty_text": warranty_text[:200],
            "retention_money_rows": [item.item_id for item in ratio_items],
            "retention_money_text": ratio_text[:200],
            "retention_release_rows": [item.item_id for item in release_items],
            "retention_release_text": release_text[:200],
            "rendered_roles": {
                concern: sorted(
                    {
                        str(component["generation_rule"]).split(":")[-1]
                        for item_id in by_concern.get(concern, [])
                        for component in rows[item_id].rendered_components
                        if str(component["generation_rule"]).startswith("CONCERN_OWNED_NUMERIC")
                    }
                )
                for concern in ("PROJECT_WARRANTY", "RETENTION_MONEY_RATIO", "RETENTION_RELEASE_PERIOD")
            },
        }
        self._numeric_evidence = evidence

        if self.case == "case_001":
            self.check(
                "project_warranty_is_24_months",
                bool(warranty_items)
                and _contains(warranty_text, WARRANTY_MONTHS)
                and not any(
                    _contains(warranty_text, phrase) for phrase in RETENTION_WARRANTY_PHRASES
                ),
                f"project warranty renders as {WARRANTY_MONTHS}",
                evidence,
            )
            self.check(
                "retention_money_ratio_is_5_percent",
                bool(ratio_items) and _contains(ratio_text, RETENTION_RATIO),
                f"retention money ratio renders as {RETENTION_RATIO}",
                evidence,
            )
            self.check(
                "retention_release_period_is_12_months",
                bool(release_items) and _contains(release_text, RETENTION_RELEASE),
                f"retention release period renders as {RETENTION_RELEASE}",
                evidence,
            )
        else:
            # The values are case-specific; the *separation* is the invariant:
            # no row may render a numeric role that belongs to a different
            # retention/warranty concern.
            cross_role: list[dict[str, str]] = []
            # Round 5 renamed the warranty/retention roles; the map uses the
            # canonical names and accepts the legacy spelling of each role so the
            # check still audits the *separation*, not a role-string spelling.
            owners = {
                "PROJECT_WARRANTY": {"WARRANTY_MONTHS", "PROJECT_WARRANTY_MONTHS"},
                "RETENTION_MONEY_RATIO": {"RETENTION_MONEY_RATIO"},
                "RETENTION_RELEASE_PERIOD": {
                    "RETENTION_RELEASE_PERIOD",
                    "RETENTION_RELEASE_MONTHS",
                },
            }
            for concern_id, allowed in owners.items():
                for item_id in by_concern.get(concern_id, []):
                    for component in rows[item_id].rendered_components:
                        rule = str(component["generation_rule"])
                        if not rule.startswith("CONCERN_OWNED_NUMERIC:"):
                            continue
                        role = rule.split(":")[-1]
                        if role not in allowed:
                            cross_role.append(
                                {
                                    "item_id": item_id,
                                    "concern_id": concern_id,
                                    "foreign_role": role,
                                }
                            )
            self.check(
                "retention_roles_rendered_from_own_concerns",
                not cross_role,
                "retention/warranty rows render only their own numeric role",
                {**evidence, "cross_role": cross_role[:10]},
            )

        if warranty_items and (ratio_items or release_items):
            self.check(
                "retention_and_warranty_rows_are_distinct",
                not (
                    ({item.item_id for item in ratio_items} | {item.item_id for item in release_items})
                    & {item.item_id for item in warranty_items}
                ),
                "retention money/release and project warranty render in distinct rows",
                {
                    "ratio": [item.item_id for item in ratio_items],
                    "release": [item.item_id for item in release_items],
                    "warranty": [item.item_id for item in warranty_items],
                },
            )

        # every numeric token rendered in a delivered cell must be an owned value
        owned_by_item = {
            item.item_id: {
                _flat(value) for component in item.rendered_components
                for value in numeric_tokens(str(component["rendered_text"]))
            }
            for item in self.items
        }
        stray: list[dict[str, str]] = []
        for item in self.items:
            row = self.rows_by_item.get(item.item_id)
            if row is None:
                continue
            for token in numeric_tokens(row.d_text):
                if token not in owned_by_item[item.item_id]:
                    stray.append({"item_id": item.item_id, "cell": row.d_address, "token": token})
        self.check(
            "final_cell_numeric_ownership",
            not stray,
            "every numeric token displayed in a delivered cell is an owned value",
            {"stray": stray[:10]},
        )

    def check_linked_facts(self) -> None:
        stale: list[dict[str, str]] = []
        rows = {item.item_id: item for item in self.items}
        for item in self.items:
            row = self.rows_by_item.get(item.item_id)
            if row is None:
                continue
            allowed = set(concern_spec(item.concern_id).fact_fields)
            for match in re.finditer(r"关联事实：\s*([^\s；;]+)", row.m_text):
                for key in re.split(r"[、,，]", match.group(1)):
                    key = key.strip()
                    if not key:
                        continue
                    if key not in allowed:
                        stale.append(
                            {"item_id": item.item_id, "cell": row.m_address, "fact_key": key}
                        )
            for component in item.rendered_components:
                if component["component_kind"] != LINKED_FACT:
                    continue
                for key in component["linked_fact_keys"]:
                    if key not in allowed:
                        stale.append(
                            {
                                "item_id": item.item_id,
                                "cell": row.m_address,
                                "fact_key": str(key),
                            }
                        )
        self.check(
            "stale_linked_facts_absent",
            not stale,
            "every rendered linked fact is allowed for its concern",
            {"stale": stale[:10]},
        )

    def _concern_backings(self) -> dict[str, str]:
        """Concern id -> every text the concern owns.

        Mirrors ``ComponentOwnership.backing_text``: owned atoms (with the clause
        they were cut from), the concern's own materials and its owned fact
        values.  A rendered cell may not name a domain concept outside this set.
        """

        if getattr(self, "_backing_cache", None) is not None:
            return self._backing_cache
        from tender_basic.dynamic_requirements import build_requirement_index
        from tender_basic.review_concern import atomize_units, build_concerns, concern_spec

        index = build_requirement_index(self.document)
        units_by_id = {unit.requirement_id: unit for unit in index.units}
        atoms = atomize_units(index.units)
        backings: dict[str, str] = {}
        for concern in build_concerns(atoms):
            parts: list[str] = []
            for atom in getattr(concern, "atoms", ()):
                parts.append(str(atom.source_text))
                origin = getattr(atom, "source_origin_text", "")
                if origin:
                    parts.append(str(origin))
                unit = units_by_id.get(str(atom.source_clause_id))
                if unit is not None:
                    parts.append(str(unit.text))
                    parts.append(str(getattr(unit, "section", "") or ""))
            parts.extend(str(name) for name in concern.owned_materials())
            spec = concern_spec(concern.concern_id)
            for field in getattr(spec, "fact_fields", ()) or ():
                value = self._fact_text(field)
                if value:
                    parts.append(value)
                    parts.append(field)
            backings[concern.concern_id] = " ".join(parts)
        self._backing_cache = backings
        return backings

    def _fact_text(self, field: str) -> str:
        if getattr(self, "_fact_text_cache", None) is None:
            cache: dict[str, str] = {}
            payload = self.facts.model_dump()
            for key, entry in (payload.get("facts") or {}).items():
                if isinstance(entry, dict):
                    label = entry.get("label") or ""
                    value = entry.get("value")
                    cache[str(key)] = f"{label} {value if value is not None else ''}".strip()
            self._fact_text_cache = cache
        return self._fact_text_cache.get(field, "")

    def check_final_cell_text_owned(self) -> None:
        """The FINAL cell text itself must not name a concept the concern lacks.

        This is the rendered-output form of the round-4 rule: it reads the sheet,
        not the model, so stale group text cannot hide behind a verified object.
        """

        backings = self._concern_backings()
        leaks: list[dict[str, Any]] = []
        for item in self.items:
            row = self.rows_by_item.get(item.item_id)
            if row is None:
                continue
            backing = backings.get(item.concern_id, "")
            # the block labels are review meta language; drop them before asking
            # whether the displayed content names a foreign concept
            displayed = re.sub(
                r"(?m)^(招标文件要求|复核要点|通过标准|不满足后果|准备材料|评分提示|数值指标|关联事实)：",
                "",
                row.d_text,
            )
            foreign = foreign_terms(displayed, backing)
            if foreign:
                leaks.append(
                    {
                        "item_id": item.item_id,
                        "concern_id": item.concern_id,
                        "cell": row.d_address,
                        "foreign_terms": foreign,
                        "displayed_text": row.d_text[:200],
                    }
                )
        self.check(
            "final_cell_text_owned_by_concern",
            not leaks,
            f"{len(self.items) - len(leaks)}/{len(self.items)} delivered cells name only concepts "
            "their concern owns",
            {"leaks": leaks[:10], "leak_count": len(leaks)},
        )

    def check_platform_roles(self) -> None:
        """Platform roles stay separate semantic roles (fixture S)."""

        fact_rows = self.cells.sheet_rows(FACT_SHEET)
        role_rows: dict[str, dict[str, str]] = {}
        for index, values in enumerate(fact_rows[1:], start=2):
            key = values[1] if len(values) > 1 else ""
            if not key:
                continue
            role_rows[key] = {
                "cell": self.cells.address(FACT_SHEET, index, 4),
                "value": values[3] if len(values) > 3 else "",
                "status": values[4] if len(values) > 4 else "",
                "candidates": values[11] if len(values) > 11 else "",
            }
        platform_keys = [
            key
            for key in role_rows
            if "platform" in key or "entry" in key or "site" in key or "announcement" in key
        ]
        conflict_rows = self.cells.sheet_rows(CONFLICT_SHEET)
        conflicts = [
            {
                "cell": self.cells.address(CONFLICT_SHEET, index, 4),
                "text": values[3] if len(values) > 3 else "",
                "key": values[1] if len(values) > 1 else "",
            }
            for index, values in enumerate(conflict_rows[1:], start=2)
            if (values[1] if len(values) > 1 else "")
        ]
        merged = [
            conflict
            for conflict in conflicts
            if len(
                [
                    key
                    for key in platform_keys
                    if key and key in conflict["key"]
                ]
            )
            > 1
        ]
        evidence = {
            "platform_fact_keys": platform_keys,
            "platform_rows": {key: role_rows[key] for key in platform_keys},
            "conflict_rows": conflicts[:10],
        }
        self.check(
            "platform_role_distinction",
            bool(platform_keys) and not merged,
            f"{len(platform_keys)} platform-related facts stay separate semantic roles",
            evidence,
        )
        self._platform_evidence = evidence

    # -- fixtures A..S ---------------------------------------------------- #

    def _row(self, item_id: str) -> FinalRow | None:
        return self.rows_by_item.get(item_id)

    def _text(self, item_id: str) -> str:
        row = self._row(item_id)
        return row.d_text if row else ""

    def _by_concern(self, concern_id: str) -> list[Any]:
        return [item for item in self.items if item.concern_id == concern_id]

    def evaluate_fixtures(self) -> dict[str, dict[str, Any]]:
        workbook_text = " ".join(
            text
            for _address, text in self.cells.all_cells(
                [DELIVERED_SHEET, CLAUSE_SHEET, MANDATORY_SHEET]
            )
        )
        fixtures: dict[str, dict[str, Any]] = {}
        case_001 = self.case == "case_001"

        def record(
            key: str,
            expectation: str,
            ok: bool | None,
            evidence: str,
            anchors: Sequence[str] = (),
        ) -> None:
            if not anchors:
                anchors = tuple(
                    item.item_id
                    for item in self.items
                    if item.item_id in {"DR005", "DR007", "DR019", "DR025", "DR034", "DR036", "DR043"}
                )
            if not case_001:
                fixtures[key] = {
                    "expectation": expectation,
                    "status": "NOT_APPLICABLE",
                    "evidence": "human fixture is anchored to the CASE001 review workbook",
                }
                return
            fixtures[key] = {
                "expectation": expectation,
                "status": "PASS" if ok else "FAIL",
                "evidence": evidence,
            }

        # A -- a licence-sourced row may not invent 资质证书/专业类别/等级.
        row = self._row("DR005")
        text = row.d_text if row else ""
        record(
            "A",
            "营业执照 row renders only its own licence requirement",
            bool(row)
            and _contains(text, "营业执照")
            and not any(term in text for term in ("资质证书", "专业类别", "资质等级")),
            text[:160],
        )

        # B -- signature row must not carry CA upload/clarification/authorisation.
        row = self._row("DR007")
        text = row.d_text if row else ""
        record(
            "B",
            "signature row renders only the signature/seal requirement",
            bool(row)
            and _contains(text, "签字盖章要求")
            and not any(
                term in text
                for term in ("可编辑的Word", "澄清", "授权委托书", "身份证扫描件", "上传经")
            ),
            text[:160],
        )

        # C -- credit/exclusion content must not be a relationship-restriction row.
        credit_items = [
            item
            for item in self.items
            if item.concern_id in {"QUALIFICATION_CREDIT"} or "信用" in item.topic
        ]
        relationship_rows = [
            item
            for item in self.items
            if item.concern_id == "QUALIFICATION_RELATIONSHIP_RESTRICTION"
        ]
        credit_ok = bool(credit_items)
        for item in relationship_rows:
            relationship_text = self._text(item.item_id)
            if "失信" in relationship_text or "中国执行信息公开网" in relationship_text:
                credit_ok = False
        record(
            "C",
            "credit/exclusion content renders under a credit concern",
            credit_ok,
            "; ".join(item.item_id for item in credit_items) or "no credit concern rendered",
        )

        # D -- anti-bribery row is typed by its own concern.
        item = next(
            (i for i in self.items if i.concern_id == "QUALIFICATION_ANTI_BRIBERY"), None
        )
        row = self._row(item.item_id) if item else None
        record(
            "D",
            "anti-bribery commitment row is typed by its commitment concern",
            bool(item)
            and bool(row)
            and "SIGNATURE" not in (item.requirement_type or "")
            and "行贿" in (row.d_text if row else ""),
            f"{item.item_id if item else '-'} type={item.requirement_type if item else '-'} "
            f"row={(row.m_text if row else '')[:60]}",
        )

        # E -- platform registration row must not carry candidate counts or a
        #      foreign 无效 consequence.
        platform_items = [
            item
            for item in self.items
            if item.concern_id in {"ELECTRONIC_UPLOAD", "PLATFORM_REGISTRATION"}
        ]
        platform_ok = bool(platform_items)
        for item in platform_items:
            text = self._text(item.item_id)
            if "推荐的成交候选人" in text or "成交人数" in text:
                platform_ok = False
            if "无效" in text and "机器码" in text and "机器码" not in text.split("不满足后果")[0]:
                platform_ok = False
        record(
            "E",
            "platform registration row keeps its own content and consequence",
            platform_ok,
            "; ".join(item.item_id for item in platform_items) or "no platform row",
        )

        # F -- question/clarification deadline is its own row.
        query_items = [item for item in self.items if item.concern_id == "QUERY_DEADLINE"]
        submission_rows = [
            item
            for item in self.items
            if item.concern_id in {"SUBMISSION_DEADLINE", "SUBMISSION_PLATFORM"}
        ]
        submission_ok = bool(query_items)
        for item in submission_rows:
            if "提出问题" in self._text(item.item_id) or "澄清" in self._text(item.item_id):
                submission_ok = False
        record(
            "F",
            "clarification/question deadline renders as its own concern",
            submission_ok,
            "; ".join(item.item_id for item in query_items) or "no query-deadline row",
        )

        # G -- the installation/acceptance row carries installation content only.
        # Round 5 split this concern: the standards list moved to
        # TECHNICAL_STANDARD_COMPLIANCE and the delivery milestone to
        # DELIVERY_ACCEPTANCE_COMPLETION, so the round-5 check is that the
        # installation content is delivered by *one* of the three concerns and
        # that whichever row carries it shows no foreign text.
        item = self._find(
            "INSTALLATION_ACCEPTANCE",
            "TECHNICAL_INSTALLATION",
            "DELIVERY_ACCEPTANCE_COMPLETION",
            "TECHNICAL_STANDARD_COMPLIANCE",
        )
        row = self._row(item.item_id) if item else None
        text = row.d_text if row else ""
        forbidden_g = ("@", "联系电话", "传真", "14 个", "14个", "3 个工作日", "（12 分）")
        record(
            "G",
            "installation/acceptance content renders in its own row (round-5 split concerns) "
            "with no foreign text",
            bool(item)
            and bool(row)
            and not any(term in text for term in forbidden_g)
            and not numeric_tokens(text) - {
                _flat(value)
                for component in item.rendered_components
                for value in numeric_tokens(str(component["rendered_text"]))
            },
            f"{item.concern_id if item else ''}: {text[:160]}",
        )

        # H -- the response-bond amount row cites the direct amount clause.
        item = next((i for i in self.items if i.concern_id == "BID_BOND_AMOUNT"), None)
        row = self._row(item.item_id) if item else None
        record(
            "H",
            "response-bond amount row cites the direct amount clause",
            bool(item)
            and bool(row)
            and "响应保证金" in (row.e_text if row else "")
            and "履约保证金" not in (row.e_text if row else ""),
            (row.e_text if row else "")[:160],
        )

        # I -- the agency fee is its own *concern*; the contract payment row
        # excludes it.  Round 5 fixture T routes a fragmentary fee clause to
        # NEEDS_REVIEW, so an absent delivery row is the correct outcome when the
        # source only contains a fragment.
        fee_items = [item for item in self.items if item.concern_id == "AGENCY_SERVICE_FEE"]
        fee_needs_review = any(
            "代理服务费" in topic for topic in getattr(self.plan, "needs_review_topics", ())
        )
        payment_ok = bool(fee_items) or fee_needs_review
        for item in self.items:
            if item.concern_id != "CONTRACT_PAYMENT":
                continue
            text = self._text(item.item_id)
            if "代理服务费" in text or "收费标准" in text:
                payment_ok = False
        record(
            "I",
            "agency-service fee is its own concern (or NEEDS_REVIEW when the source is a fragment) "
            "and never renders inside contract payment",
            payment_ok,
            "; ".join(item.item_id for item in fee_items)
            or ("agency fee is NEEDS_REVIEW (fragment source)" if fee_needs_review else "no agency-fee row"),
        )

        # J -- "reject all responses" is a purchaser procedure, not a bidder veto.
        buyer_side = " ".join(
            str(item.source_requirement) for item in list(self.items) + list(self.background)
        )
        procedure_items = [
            item for item in self.background if item.concern_id == "PURCHASER_PROCEDURE"
        ]
        rendered_reject_all = [
            item.item_id
            for item in self.items
            if "否决所有" in self._text(item.item_id)
        ]
        record(
            "J",
            "reject-all-responses stays an internal procedure item",
            bool(procedure_items) and not rendered_reject_all,
            f"procedure_items={[i.item_id for i in procedure_items]} rendered_in_rows="
            f"{rendered_reject_all}",
        )

        # K -- a funding-source clause must not invent project-identity checks.
        # Round 5 moves the funding clause to its own PROJECT_FUNDING_SOURCE
        # concern, so "no PROJECT_BASIC_INFO row" is a pass: the check is that no
        # row invents project-identity checks out of a funding clause.
        basic_items = [
            i for i in self.items if i.concern_id in {"PROJECT_BASIC_INFO", "PROJECT_FUNDING_SOURCE"}
        ]
        funding = next((i for i in basic_items if i.concern_id == "PROJECT_FUNDING_SOURCE"), None)
        funding_text = self._text(funding.item_id) if funding else ""
        record(
            "K",
            "project-basic-info row does not invent project name/number/lot checks",
            not any(term in funding_text for term in ("项目名称", "项目编号", "标段")),
            funding_text[:160] or "no PROJECT_FUNDING_SOURCE row",
        )

        # L -- the chapter-6 format reference invents no binding/page-number rules.
        item = next((i for i in self.items if i.concern_id == "FILE_FORMAT"), None)
        text = self._text(item.item_id) if item else ""
        record(
            "L",
            "file-format row invents no binding/catalogue/page-number requirement",
            bool(item) and not any(term in text for term in ("装订", "目录", "页码")),
            text[:160],
        )

        # M -- composition row carries no clarification/committee text.
        composition = [
            item
            for item in self.items
            if item.concern_id in {"FILE_COMPOSITION", "FILE_FORMAT"}
            and item.item_id != (item.item_id)
        ]
        composition_items = [
            item for item in self.items if item.concern_id in {"FILE_COMPOSITION", "FILE_FORMAT"}
        ]
        composition_ok = bool(composition_items)
        for item in composition_items:
            text = self._text(item.item_id)
            if any(term in text for term in ("澄清", "评审小组成员", "专家")):
                composition_ok = False
        record(
            "M",
            "file composition row keeps clarification/committee text out",
            composition_ok,
            "; ".join(f"{i.item_id}:{i.concern_id}" for i in composition_items),
        )

        # N -- price completeness keeps price-scope evidence, and a 否决 claim is
        # allowed only when the plan carries the source consequence behind it.
        # Round 6 renders the source-visible criticality note into the cell, so a
        # row may say 否决 only with ``rejection_basis_atom_ids`` to show for it;
        # the generator's risk table no longer decides this.
        item = self._find("PRICING_COMPLETENESS", "PRICE_COMPLETENESS")
        row = self._row(item.item_id) if item else None
        text = row.d_text if row else ""
        veto_claimed = "否决" in text
        source_backed_veto = bool(
            getattr(item, "rejection_consequence", False)
            and getattr(item, "rejection_basis_atom_ids", ())
        )
        record(
            "N",
            "price-completeness row uses price-scope evidence and only a source-backed veto",
            bool(item)
            and bool(row)
            and "报价" in (row.e_text if row else "")
            and (not veto_claimed or source_backed_veto)
            and ("评审小组" not in text or "报价" in text),
            text[:160],
        )

        # O -- scoring is split across its own concerns (95%/5% payment
        # condition, the highest 1 point and the 40-point price formula must not
        # be flattened into one combined scoring row).
        scoring_concerns = sorted(
            {
                item.concern_id
                for item in self.items
                if item.concern_id.startswith("SCORING_")
                or item.concern_id == "EVALUATION_SCORING"
            }
        )
        payment_items = [
            item for item in self.items if item.concern_id == "SCORING_PAYMENT_CONDITION"
        ]
        payment_text = " ".join(self._text(item.item_id) for item in payment_items)
        price_items = [item for item in self.items if item.concern_id == "SCORING_PRICE_FORMULA"]
        price_text = " ".join(self._text(item.item_id) for item in price_items)
        cap_text = " ".join(
            self._text(item.item_id)
            for item in self.items
            if item.concern_id == "EVALUATION_SCORING"
        )
        o_ok = (
            len(scoring_concerns) >= 2
            and bool(payment_items)
            and "95%" in payment_text
            and re.search(r"(12|8)\s*分", payment_text) is not None
            and bool(price_items)
            and "40" in price_text
            and "1" in cap_text
        )
        record(
            "O",
            "scoring is split into separate scoring concerns "
            "(payment condition, highest score, price formula)",
            o_ok,
            f"concerns={scoring_concerns} payment={[i.item_id for i in payment_items]} "
            f"price={[i.item_id for i in price_items]}",
        )

        # P -- technical parameter row does not cite contract/material-list proof.
        item = next(
            (i for i in self.items if i.concern_id == "TECHNICAL_PARAMETER"), None
        )
        row = self._row(item.item_id) if item else None
        record(
            "P",
            "technical-parameter row does not borrow contract/material-list proof",
            bool(item)
            and bool(row)
            and "材料清单" not in (row.e_text if row else "")
            and "第一条设备采购清单" not in (row.e_text if row else ""),
            (row.e_text if row else "")[:160],
        )

        # Q -- 12 months renders only as the retention release period.
        release_items = [
            item for item in self.items if item.concern_id == "RETENTION_RELEASE_PERIOD"
        ]
        warranty_items = [item for item in self.items if item.concern_id == "PROJECT_WARRANTY"]
        q_ok = bool(release_items) and bool(warranty_items)
        for item in warranty_items:
            if any(phrase in self._text(item.item_id) for phrase in RETENTION_WARRANTY_PHRASES):
                q_ok = False
        record(
            "Q",
            "12-month release renders only as the retention release period",
            q_ok,
            f"release={[i.item_id for i in release_items]} warranty={[i.item_id for i in warranty_items]}",
        )

        # R -- 5% renders only as the retention money ratio.
        ratio_items = [
            item for item in self.items if item.concern_id == "RETENTION_MONEY_RATIO"
        ]
        payment_ratio_wording = re.compile(
            r"(付款|支付|计分|得分)\s*比例[^。；\n]{0,8}5\s*%|5\s*%[^。；\n]{0,4}(付款|支付|计分)\s*比例"
        )
        r_ok = bool(ratio_items)
        for item in self.items:
            text = self._text(item.item_id)
            if payment_ratio_wording.search(_flat(text)):
                r_ok = False
        r_ok = r_ok and all(
            ("质保金" in self._text(item.item_id))
            or ("质量保证金" in self._text(item.item_id))
            for item in ratio_items
        )
        record(
            "R",
            "5% renders only as the retention money ratio",
            r_ok,
            "; ".join(
                f"{item.item_id}:{self._text(item.item_id)[:60]}" for item in ratio_items
            )
            or "no retention money row",
        )

        # S -- platform roles stay separate; no merged candidate conflict.
        evidence = getattr(self, "_platform_evidence", {})
        platform_keys = evidence.get("platform_fact_keys") or []
        conflicts = evidence.get("conflict_rows") or []
        merged = [
            conflict
            for conflict in conflicts
            if sum(1 for key in platform_keys if key and key in str(conflict.get("key", ""))) > 1
        ]
        record(
            "S",
            "transaction/announcement/entry platform roles stay separate",
            bool(platform_keys) and not merged,
            f"platform_keys={platform_keys} conflicts={[c['cell'] for c in conflicts]}",
        )

        self._workbook_text = workbook_text
        return fixtures

    # -- 30-cell final-cell audit ---------------------------------------- #

    def final_cell_audit(self) -> dict[str, Any]:
        """Audit sampled FINAL cells for ownership coherence."""

        owned_by_item = {
            item.item_id: [_flat(text) for text in self._item_texts(item)] for item in self.items
        }
        allowed_numbers = {
            item.item_id: {
                _flat(value)
                for component in item.rendered_components
                for value in numeric_tokens(str(component["rendered_text"]))
            }
            for item in self.items
        }
        covered: list[dict[str, Any]] = []
        for item in self.items:
            row = self.rows_by_item.get(item.item_id)
            if row is None:
                continue
            owned_texts = owned_by_item[item.item_id]
            evidence_texts = [
                _flat(str(component["rendered_text"]))
                for component in item.rendered_components
                if str(component["component_kind"]) == EVIDENCE_SUMMARY
            ]
            expected_note = f"类型：{item.requirement_type}/{item.submodule or item.topic}"
            for address, text in (
                (row.d_address, row.d_text),
                (row.e_address, row.e_text),
                (row.m_address, row.m_text),
            ):
                if not text:
                    continue
                unowned: list[str] = []
                if address == row.d_address:
                    # the delivered cell is a projection of the components:
                    # every block line must be produced by one of them
                    for line in text.split("\n"):
                        stripped = re.sub(r"^[①②③④⑤⑥⑦⑧⑨·\s]+", "", line).strip()
                        stripped = re.sub(
                            r"^(招标文件要求|复核要点|通过标准|不满足后果|准备材料|评分提示)：",
                            "",
                            stripped,
                        )
                        if not stripped:
                            continue
                        flat = _flat(stripped)
                        if any(flat[:30] in owned or owned[:30] in flat for owned in owned_texts):
                            continue
                        unowned.append(stripped[:80])
                elif address == row.e_address:
                    # machine evidence cell: locator + the decisive clause text
                    if not any(
                        evidence and (evidence[:40] in _flat(text)) for evidence in evidence_texts
                    ):
                        unowned.append(text[:80])
                else:
                    # machine type note: concern type/topic and linked facts
                    if not _flat(expected_note)[:20] in _flat(text):
                        unowned.append(text[:80])
                stray_numbers = (
                    sorted(
                        token
                        for token in numeric_tokens(text)
                        if token not in allowed_numbers[item.item_id]
                    )
                    if address != row.e_address
                    else []
                )
                covered.append(
                    {
                        "item_id": item.item_id,
                        "concern_id": item.concern_id,
                        "cell": address,
                        "displayed_text": text[:300],
                        "unowned_lines": unowned,
                        "stray_numbers": stray_numbers,
                        "coherent": not unowned and not stray_numbers,
                    }
                )
        coherent = [entry for entry in covered if entry["coherent"]]
        total = len(covered)
        sample = coherent[: self.audit_limit]
        result = {
            "audited_cell_count": total,
            "coherent_cell_count": len(coherent),
            "incoherent_cell_count": total - len(coherent),
            "sample_count": len(sample),
            "sample": sample,
            "incoherent": [entry for entry in covered if not entry["coherent"]][:10],
        }
        self.check(
            "case_final_cell_audit",
            total - len(coherent) == 0 and len(sample) >= min(self.audit_limit, total),
            f"{len(coherent)}/{total} final cells coherent; {len(sample)} sampled with addresses "
            "and displayed text",
            {
                "audited_cell_count": total,
                "coherent_cell_count": len(coherent),
                "sample_addresses": [entry["cell"] for entry in sample[:10]],
            },
        )
        return result

    # -- report ----------------------------------------------------------- #

    def provenance(self) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for item in self.items:
            row = self.rows_by_item.get(item.item_id)
            addresses = {}
            if row is not None:
                addresses = {
                    SOURCE_REQUIREMENT: row.d_address,
                    REVIEW_CHECK: row.d_address,
                    PASS_CRITERION: row.d_address,
                    PREPARATION_MATERIAL: row.d_address,
                    FAILURE_CONSEQUENCE: row.d_address,
                    SCORING_GUIDANCE: row.d_address,
                    NUMERIC_STATEMENT: row.d_address,
                    EVIDENCE_SUMMARY: row.e_address,
                    LINKED_FACT: row.m_address,
                }
            components = [
                _component_from_dict(payload)
                for payload in item.rendered_components
            ]
            for entry in provenance_map(components, cell_addresses=addresses):
                entry["topic"] = item.topic
                entry["requirement_type"] = item.requirement_type
                entries.append(entry)
        return {
            "schema": "v1_review_workbook_round4_rendered_component_provenance/1",
            "case": self.case,
            "build_id": self.build.name,
            "workbook": str(self.workbook_path),
            "workbook_sha256": sha256(self.workbook_path),
            "cell_kinds": {
                SOURCE_REQUIREMENT: "delivered D",
                REVIEW_CHECK: "delivered D",
                PASS_CRITERION: "delivered D",
                PREPARATION_MATERIAL: "delivered D",
                FAILURE_CONSEQUENCE: "delivered D",
                SCORING_GUIDANCE: "delivered D",
                NUMERIC_STATEMENT: "delivered D",
                EVIDENCE_SUMMARY: "delivered E",
                LINKED_FACT: "delivered M",
            },
            "component_count": len(entries),
            "cell_count": len({str(entry["cell"]) for entry in entries}),
            "unverified_count": sum(1 for entry in entries if not entry["ownership_verified"]),
            "entries": entries,
        }

    def run(self) -> dict[str, Any]:
        self.check_structure()
        self.check_component_ownership()
        self.check_rendered_cells_owned()
        self.check_view_cells_consistent()
        self.check_foreign_text_absent()
        self.check_final_cell_text_owned()
        self.check_numeric_invariants()
        self.check_linked_facts()
        self.check_platform_roles()
        fixtures = self.evaluate_fixtures()
        audit = self.final_cell_audit()

        failed = [check for check in self.checks if not check.ok]
        failed_fixtures = [key for key, value in fixtures.items() if value["status"] == "FAIL"]
        not_applicable = [key for key, value in fixtures.items() if value["status"] == "NOT_APPLICABLE"]
        verdict = "PASS" if not failed and not failed_fixtures else "FAIL"

        before_summary = self._before_summary()
        return {
            "schema": "v1_review_workbook_round4_report/1",
            "case": self.case,
            "build_id": self.build.name,
            "workbook": str(self.workbook_path),
            "workbook_sha256": sha256(self.workbook_path),
            "word_artifacts_unchanged": before_summary.get("word_artifacts_unchanged"),
            "review_row_count": len(self.items),
            "background_item_count": len(self.background),
            "filtered_non_actionable_count": self.plan.filtered_non_actionable_count,
            "rendered_component_count": self.qa["rendered_component_count"],
            "rendered_component_unverified_count": self.qa[
                "rendered_component_unverified_count"
            ],
            "rendered_component_concern_mismatch_total": self.qa[
                "rendered_component_concern_mismatch_total"
            ],
            "rendered_mismatch_counts": self._mismatch_counts(),
            "check_count": len(self.checks),
            "passed_count": len(self.checks) - len(failed),
            "failed_count": len(failed),
            "checks": [check.as_dict() for check in self.checks],
            "failed_checks": [check.name for check in failed],
            "fixtures": fixtures,
            "fixture_summary": {
                "total": len(fixtures),
                "passed": len(fixtures) - len(failed_fixtures) - len(not_applicable),
                "evaluated": len(fixtures) - len(not_applicable),
                "failed": failed_fixtures,
                "not_applicable": not_applicable,
                "labels": {key: value["expectation"] for key, value in fixtures.items()},
            },
            "final_cell_audit": audit,
            "platform_role_evidence": getattr(self, "_platform_evidence", {}),
            "numeric_evidence": getattr(self, "_numeric_evidence", {}),
            "invariant": "SEMANTIC OWNERSHIP MUST SURVIVE RENDERING",
            "verdict": verdict,
        }

    def _before_summary(self) -> dict[str, Any]:
        unchanged: bool | None = None
        if self.before is not None:
            unchanged = True
            for name in ("基础投标文件.docx", "基础投标文件.pdf", "generation_report.json"):
                origin = self.before / name
                target = self.build / name
                if not origin.is_file() or not target.is_file():
                    unchanged = None
                    break
                if sha256(origin) != sha256(target):
                    unchanged = False
                    break
        return {"word_artifacts_unchanged": unchanged}


def _component_from_dict(payload: dict[str, Any]):
    from tender_basic.review_rendering import RenderedReviewComponent

    return RenderedReviewComponent.from_dict(payload)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Round-4 rendered-component provenance — {report['case']}",
        "",
        f"* build: `{report['build_id']}`",
        f"* workbook: `{report['workbook']}` (sha256 `{report['workbook_sha256'][:16]}…`)",
        f"* invariant: **{report['invariant']}**",
        f"* review rows: {report['review_row_count']} (+{report['background_item_count']} "
        "non-bidder-facing background items)",
        f"* rendered components: {report['rendered_component_count']} "
        f"({report['rendered_component_unverified_count']} unverified)",
        f"* rendered concern mismatches: {report['rendered_component_concern_mismatch_total']}",
        f"* **ROUND4 VERDICT: {report['verdict']}** "
        f"({report['passed_count']}/{report['check_count']} checks, "
        f"{report['fixture_summary']['passed']}/{report['fixture_summary']['total']} fixtures)",
        "",
        "## Rendered-component mismatch buckets",
        "",
        "| bucket | count |",
        "| --- | --- |",
    ]
    for key, value in sorted(report["rendered_mismatch_counts"].items()):
        lines.append(f"| {key} | {value} |")
    lines += ["", "## Rendered-output gate", "", "| check | ok | detail |", "| --- | --- | --- |"]
    for check in report["checks"]:
        lines.append(f"| {check['check']} | {'PASS' if check['ok'] else 'FAIL'} | {check['detail']} |")
    lines += [
        "",
        "## Human fixtures A–S (frozen workbook cells)",
        "",
        "| fixture | expectation | status | evidence |",
        "| --- | --- | --- | --- |",
    ]
    for key, value in report["fixtures"].items():
        evidence = str(value["evidence"]).replace("\n", " ")[:160]
        lines.append(f"| {key} | {value['expectation']} | {value['status']} | {evidence} |")
    audit = report["final_cell_audit"]
    lines += [
        "",
        f"## Final-cell audit ({audit['coherent_cell_count']}/{audit['audited_cell_count']} coherent)",
        "",
        "| cell | item | concern | displayed text (first 160) |",
        "| --- | --- | --- | --- |",
    ]
    for entry in audit["sample"]:
        displayed = entry["displayed_text"].replace("\n", " ")[:160]
        lines.append(
            f"| {entry['cell']} | {entry['item_id']} | {entry['concern_id']} | {displayed} |"
        )
    if audit["incoherent"]:
        lines += ["", "### Incoherent cells", ""]
        for entry in audit["incoherent"]:
            lines.append(f"* {entry['cell']} ({entry['item_id']}): {entry['unowned_lines']}")
    lines += ["", "## Platform-role evidence", "", "```json"]
    lines.append(json.dumps(report.get("platform_role_evidence", {}), ensure_ascii=False, indent=1)[:2000])
    lines += ["```", ""]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--before", type=Path, default=None)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--md", type=Path, default=None)
    parser.add_argument("--provenance", type=Path, default=None)
    parser.add_argument("--audit-limit", type=int, default=30)
    args = parser.parse_args(argv)

    report = Round4Report(
        build=args.build, case=args.case, before=args.before, audit_limit=args.audit_limit
    ).run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.md is not None:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(render_markdown(report), encoding="utf-8")
    if args.provenance is not None:
        provenance = Round4Report(
            build=args.build, case=args.case, before=args.before, audit_limit=args.audit_limit
        ).provenance()
        args.provenance.parent.mkdir(parents=True, exist_ok=True)
        args.provenance.write_text(
            json.dumps(provenance, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "case": args.case,
                "verdict": report["verdict"],
                "checks": f"{report['passed_count']}/{report['check_count']}",
                "fixtures": f"{report['fixture_summary']['passed']}/{report['fixture_summary']['total']}",
                "failed_checks": report["failed_checks"],
                "failed_fixtures": report["fixture_summary"]["failed"],
                "rendered_mismatch_total": report["rendered_component_concern_mismatch_total"],
                "audit": f"{report['final_cell_audit']['coherent_cell_count']}/"
                f"{report['final_cell_audit']['audited_cell_count']}",
                "out": str(args.out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
