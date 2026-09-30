"""Round 9: final delivered-content closure for the review workbook.

The round-8 successor was examined by hand and failed on five further content
classes:

* a scoring standard whose tiers are delivered as simultaneous obligations
  (D23) and whose payment-condition row is an extraction fragment (D38);
* a row whose source is the pre-bid-meeting decision but whose action is the
  question/clarification deadline (D56);
* an action that cites a page/clause the row does not quote (D57);
* corrupted source joins ("营业执照，准 供应商名称", "资格要求 格要求", D16/D22);
* a scoring rule the bidder is told to restate in its response (D50);
* a blank experience form still listed under the blank *quotation* form section
  (page 53), and retention rows citing a foreign evidence heading (D40/D43).

Every check here reads the **saved and reopened successor workbook**; the
fixtures are asserted against the source document's own text, never against the
classifier that produced the row.

Usage::

    .venv/Scripts/python.exe scripts/v1_review_workbook_round9_report.py --three-case
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from tender_basic.evidence_unit import (  # noqa: E402
    build_evidence_units,
    expected_locator_for_unit,
    format_locator_section_for_display,
    locators_match_exactly,
)
from v1_review_workbook_round8_report import (  # noqa: E402
    LEGACY_SHEET_TITLE,
    MANDATORY_SHEET_TITLE,
    REPORTS,
    Round8Report,
    _legacy_block,
)

SCHEMA = "v1_review_workbook_round9/1"
GENERALIZATION_SCHEMA = "v1_review_workbook_round9_generalization/1"
GATE_SCHEMA = "v1_review_workbook_round9_gate_integrity/1"

#: round-9 successor build per case.
#:
#: The ``...9r2`` revision is the round-9 successor: running the round-4 rendered
#: component ownership gate and the round-7 successor pointer against the first
#: round-9 workbook showed that the round-9 scoring wording named concepts the
#: row's own source never states ("得分"/"评分") and declared numeric components the
#: cell never displayed.  The product was corrected and the successor re-derived;
#: the first round-9 build stays frozen on disk, never overwritten.
BUILDS: dict[str, str] = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook9r2",
    "case_002": "v1_round4_closure9_review_workbook9r2",
    "case_003": "v1_round4_closure9_review_workbook9r2",
}

#: The scoring tiers the *source* prints, per case and row: (ratio detail, score).
#: They are read from the tender document itself (page 26 of CASE001's 评审办法
#: 前附表), so the fixture cannot agree with the renderer by construction.
SOURCE_TIERS: dict[str, dict[str, tuple[tuple[str, str], ...]]] = {
    "case_001": {
        "SCORING_BANK_ACCEPTANCE": (
            ("100%接受银行承兑", "4分"),
            ("50%接受银行承兑", "2分"),
            ("50%以下接受银行承兑", "1分"),
        ),
        "SCORING_PAYMENT_CONDITION": (
            ("免预付款", "12分"),
            ("预付款比例小于等于15%", "8分"),
            ("预付款比例大于15%", "4分"),
        ),
    }
}

#: A review action must cite the row's own page/clause; these are the actions a
#: round-9 fixture checks against the row's own evidence unit.
_ANCHOR_RE = re.compile(r"依据第(\d+)页(?:第([\d.]+)条)?逐条比对响应文件对应章节")

#: Checks that demand the bidder restate an evaluation rule in its response.
_BIDDER_DECLARATION_RE = re.compile(r"核对响应文件已载明")
#: Values that are evaluation-rule parameters (never a bidder declaration).
_RULE_VALUE_RE = re.compile(r"(本项最高|基本分)")

#: Corrupted joins the human named (D16/D22).
_CORRUPT_JOIN_RES = (
    re.compile(r"执照\s+执照"),
    re.compile(r"供应商名称\s+供应商名称"),
    re.compile(r"响应文件格式\s+响应文件格式"),
    re.compile(r"格要求\s+格要求"),
    re.compile(r"[，,]\s*准\s"),
)

#: The named locator fixtures, each with the content the finding is *about*.
#:
#: A finding is bound to a concern, but a case's own concern contract may state
#: the same source concept inside a sibling concern (CASE002 prints the retention
#: ratio in the clause that also states the release period, so it is delivered as
#: ``RETENTION_RELEASE_PERIOD`` and never as a separate ratio row).  The probe is
#: what keeps the fixture honest in that case: the finding is then asserted against
#: the delivered row that actually carries the content, and if the case's *source*
#: states the concept while no delivered row carries it, the fixture FAILS.  A
#: fixture therefore never disappears and is never accepted on a weaker match.
LOCATOR_FIXTURES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("LOCATOR_D34_BID_VALIDITY", "BID_VALIDITY", (r"有效期",)),
    ("LOCATOR_D40_RETENTION_RELEASE", "RETENTION_RELEASE_PERIOD", (r"质保金|质量保证金",)),
    (
        "LOCATOR_D43_RETENTION_RATIO",
        "RETENTION_MONEY_RATIO",
        (r"质保金|质量保证金", r"\d+\s*[%％]"),
    ),
    ("LOCATOR_D57_SUBMISSION_DEADLINE", "SUBMISSION_DEADLINE", (r"截止",)),
    ("LOCATOR_DR002_DELIVERY_PERIOD", "DELIVERY_PERIOD", (r"工期|供货期|交货期",)),
    ("LOCATOR_DR047_AUTHORIZATION", "AUTHORIZATION", (r"授权",)),
)


class Round9Report(Round8Report):
    """Round-8 audits plus the round-9 delivered-content closure."""

    def __init__(self, case: str, *, case_dir: Path | None = None) -> None:
        super().__init__(case, case_dir=case_dir, build_name=BUILDS[case])
        # the round-9 audit reads the round-9 plan (the round-8 base is bound to
        # the round-8 successor for its own frozen evidence)
        self.items = list(self.r4.items)
        self.background = list(self.r4.background)
        self.by_item = {
            str(item.item_id): item for item in [*self.items, *self.background]
        }

    # -- delivered text ---------------------------------------------------- #

    def fixture_rows(self) -> list[dict[str, Any]]:
        """One row per delivered item, with the legacy cell's blocks recovered.

        The legacy template prints "复核要点：…\\n通过标准：…\\n不满足后果：…" in one
        cell, so each block is read by its own label; the round-8 reader looked
        for "核验标准" and therefore lost the legacy pass criteria.
        """

        reviewer = self.reviewer_rows()
        legacy = self.legacy_rows()
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in [*reviewer, *legacy]:
            item_id = str(row.get("item_id") or "")
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            chosen = self._row_for([*reviewer, *legacy], item_id)
            if chosen is None:
                continue
            merged = dict(chosen)
            if str(chosen.get("sheet")) == LEGACY_SHEET_TITLE:
                template = next(
                    (
                        candidate
                        for candidate in legacy
                        if str(candidate.get("item_id")) == item_id
                    ),
                    None,
                )
                cell = str(template.get("cell_text") or "") if template else ""
                merged["action"] = merged.get("action") or _legacy_block(cell, "复核要点")
                merged["criteria"] = (
                    str(merged.get("criteria") or "")
                    or _legacy_block(cell, "通过标准")
                    or _legacy_block(cell, "核验标准")
                )
                merged["consequence"] = _legacy_block(cell, "不满足后果")
            out.append(merged)
        return out

    def _by_concern(self) -> dict[str, Mapping[str, Any]]:
        out: dict[str, Mapping[str, Any]] = {}
        for row in self.fixture_rows():
            item = row.get("item")
            concern_id = str(getattr(item, "concern_id", "") or "")
            if concern_id and concern_id not in out:
                out[concern_id] = row
        return out

    # -- source facts ----------------------------------------------------- #

    def _source_spans(self) -> list[str]:
        """Every source unit's text, read from the successor's own document."""

        if getattr(self, "_source_spans_cache", None) is None:
            from tender_basic.dynamic_requirements import build_requirement_index

            index = build_requirement_index(self.document)
            self._source_spans_cache = [str(unit.text) for unit in index.units]
        return self._source_spans_cache

    def source_contains(self, *needles: str) -> bool:
        haystack = re.sub(r"[\s\u3000]+", "", " ".join(self._source_spans()))
        return all(re.sub(r"[\s\u3000]+", "", needle) in haystack for needle in needles)

    def _sheet_rows(self, title: str) -> list[dict[str, Any]]:
        return self._rows(title)

    # -- round-9 checks --------------------------------------------------- #

    def check_scoring_tiers(self) -> None:
        """Every scoring tier keeps its own source condition and score."""

        problems: list[dict[str, Any]] = []
        checked = 0
        for row in self.fixture_rows():
            item_id = str(row.get("item_id") or "")
            requirement = str(row.get("requirement") or "")
            action = str(row.get("action") or "") + " " + str(row.get("criteria") or "")
            tiers = _tiers_in(requirement)
            if len(tiers) < 2:
                continue
            checked += 1
            for condition, score in tiers:
                if condition and score and f"{condition} 得 {score}" not in action:
                    problems.append(
                        {
                            "item_id": item_id,
                            "missing_tier": f"{condition} 得 {score}",
                        }
                    )
            # no pass criterion may require two mutually exclusive tiers at once
            criteria = str(row.get("criteria") or "")
            declarations = [
                line for line in criteria.split("。") if "且响应文件一致" in line
            ]
            if len(declarations) > 1 and any(
                "接受银行承兑" in line or "预付款" in line for line in declarations
            ):
                problems.append(
                    {
                        "item_id": item_id,
                        "reason": "pass criteria require more than one tier",
                        "criteria": criteria[:200],
                    }
                )
        self.counts["SCORING_TIER_PROBLEM_COUNT"] = len(problems)
        self.check(
            "every scoring tier keeps its own source condition and score",
            not problems,
            f"{checked} tiered scoring row(s) checked, {len(problems)} problem(s)",
            {"problems": problems[:6]},
        )

    def check_action_anchor(self) -> None:
        """A delivered action may only cite the row's own page and clause."""

        problems: list[dict[str, Any]] = []
        checked = 0
        for row in self.fixture_rows():
            action = str(row.get("action") or "")
            matches = _ANCHOR_RE.findall(action)
            if not matches:
                continue
            checked += 1
            locator = str(row.get("locator") or "")
            own_page = re.search(r"第(\d+)页", locator)
            own_clause = re.search(r"第([\d.]+)条", locator)
            for page, clause in matches:
                if own_page and page != own_page.group(1):
                    problems.append(
                        {
                            "item_id": row.get("item_id"),
                            "action_cites_page": page,
                            "own_page": own_page.group(1),
                        }
                    )
                elif clause and own_clause and clause != own_clause.group(1):
                    problems.append(
                        {
                            "item_id": row.get("item_id"),
                            "action_cites_clause": clause,
                            "own_clause": own_clause.group(1),
                        }
                    )
        self.counts["ACTION_ANCHOR_MISMATCH_COUNT"] = len(problems)
        self.check(
            "no delivered action cites a page or clause the row does not quote",
            not problems,
            f"{checked} anchored action(s) checked, {len(problems)} mismatch(es)",
            {"problems": problems[:6]},
        )

    def _canonical_units(self) -> dict[str, Any]:
        """Every evidence unit of the successor's own document, by unit id.

        Rebuilt here from the *delivered* document, so the audit's expected locator
        is the production formatter applied to a canonical ``EvidenceUnit``, never
        to a string an earlier run happened to record.
        """

        if getattr(self, "_canonical_units_cache", None) is None:
            self._canonical_units_cache = {
                unit.unit_id: unit for unit in build_evidence_units(self.document)
            }
        return self._canonical_units_cache

    def check_locator_coherence(self) -> None:
        """The delivered locator must equal the production formatter's output.

        For every delivered row this check

        1. rebuilds the row's PRIMARY evidence unit from the successor's own
           document (the canonical ``EvidenceUnit``),
        2. runs the production formatter (``expected_locator_for_unit``) over that
           unit and the exact span production handed it, and
        3. reads the delivered locator from the SAVED workbook cell and requires
           *exact* equality -- of the whole locator and of every printed field.

        The comparison is ``locators_match_exactly`` (equality): no prefix,
        substring or fuzzy variant is accepted.  A differing section is a product
        defect or a measurement correction, never something to tolerate.
        """

        problems: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        units = self._canonical_units()
        for row in self.fixture_rows():
            item = row.get("item")
            if item is None:
                continue
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
            recorded_section = str(primary.get("section") or "")
            unit = units.get(str(primary.get("unit_id") or ""))
            # the locator text as DELIVERED: read from the reopened workbook cell,
            # never from the plan's own locator string
            delivered = _delivered_locator(str(row.get("locator") or ""))
            page, section, clause, kind = _split_locator(delivered)
            record: dict[str, Any] = {
                "item_id": str(item.item_id),
                "concern_id": str(getattr(item, "concern_id", "") or ""),
                "cell": row.get("cell"),
                "sheet": row.get("sheet"),
                "canonical_unit_id": str(primary.get("unit_id") or ""),
                "canonical_section": recorded_section,
                "canonical_clause": str(primary.get("clause") or ""),
                "canonical_page": primary.get("page"),
                "unit_span": str(primary.get("unit_span") or "")[:120],
                "atom_clause": str(primary.get("atom_clause") or ""),
                "section_source": str(primary.get("section_source") or ""),
                "clip_limit": primary.get("section_clip_limit"),
                "actual_locator": delivered,
                "actual_visible_section": section,
                "actual_page": page,
                "actual_clause": clause,
                "actual_kind": kind,
                "source": "SAVED_XLSX",
            }
            if unit is None:
                record.update(
                    {
                        "expected_locator": "",
                        "expected_visible_section": "",
                        "expected_page": "",
                        "expected_clause": "",
                        "expected_kind": "",
                        "result": "FAIL",
                        "failure": "canonical evidence unit absent from the delivered document",
                        "classification": "STALE_BUILD",
                    }
                )
                records.append(record)
                problems.append(
                    {
                        "item_id": record["item_id"],
                        "unit_id": record["canonical_unit_id"],
                        "reason": record["failure"],
                        "classification": "STALE_BUILD",
                    }
                )
                continue
            # production keys the unit by the atom's own leading clause when the
            # atom states one: rebuild that same effective unit before running the
            # formatter, otherwise a body block anchored by "15.4.1 保修责任 …"
            # would be read as having no clause at all
            atom_clause = str(primary.get("atom_clause") or "")
            if atom_clause and atom_clause != unit.clause_number:
                unit = replace(unit, clause_number=atom_clause)
            expected_locator, expected_section, expected_clause, source, clip = (
                expected_locator_for_unit(
                    unit,
                    str(primary.get("unit_span") or ""),
                    fallback_page=primary.get("page"),
                    fallback_section=recorded_section,
                    fallback_clause=record["canonical_clause"],
                )
            )
            expected_section = format_locator_section_for_display(expected_section)
            expected_page_number = unit.page or primary.get("page")
            # ``_split_locator`` returns the page as the digits the locator printed,
            # so the expected side is compared in the same shape
            expected_page = str(expected_page_number) if expected_page_number else ""
            expected_kind = str(getattr(unit, "kind", "") or "")
            fields = {
                "locator": locators_match_exactly(expected_locator, delivered),
                "page": locators_match_exactly(expected_page, page),
                "section": locators_match_exactly(expected_section, section),
                "clause": locators_match_exactly(expected_clause, clause),
                "kind": locators_match_exactly(expected_kind, kind),
            }
            record.update(
                {
                    "expected_locator": expected_locator,
                    "expected_visible_section": expected_section,
                    "expected_page": expected_page,
                    "expected_clause": expected_clause,
                    "expected_kind": expected_kind,
                    "expected_section_source": source,
                    "expected_clip_limit": clip,
                    # the plan's own recorded section must be the formatter's output
                    # too, otherwise the *measurement* is stale rather than the build
                    "recorded_section_matches_formatter": locators_match_exactly(
                        expected_section,
                        format_locator_section_for_display(recorded_section),
                    ),
                    "field_matches": fields,
                    "result": "PASS" if all(fields.values()) else "FAIL",
                }
            )
            records.append(record)
            if record["result"] == "PASS":
                continue
            problems.append(
                {
                    "item_id": record["item_id"],
                    "cell": record["cell"],
                    "expected_locator": expected_locator[:120],
                    "actual_locator": delivered[:120],
                    "expected_visible_section": expected_section[:80],
                    "actual_visible_section": section[:80],
                    "field_matches": fields,
                    "recorded_section_matches_formatter": record[
                        "recorded_section_matches_formatter"
                    ],
                    "classification": (
                        "PRODUCT_DEFECT"
                        if not fields["section"]
                        else "PRODUCT_DEFECT_PAGE_CLAUSE_KIND"
                    ),
                }
            )
        self.locator_records = records
        self.counts["LOCATOR_COHERENCE_PROBLEM_COUNT"] = len(problems)
        self.counts["LOCATOR_ROWS_CHECKED"] = len(records)
        clipped = [record for record in records if record["clip_limit"]]
        self.counts["LOCATOR_CLIPPED_SECTION_COUNT"] = len(clipped)
        self.check(
            "every delivered locator equals the production formatter's own output",
            not problems,
            f"{len(records)} locator(s) recomputed from the canonical evidence unit and "
            f"compared with the saved workbook, {len(problems)} mismatch(es), "
            f"{len(clipped)} clipped section(s)",
            {"problems": problems[:6], "clipped": clipped[:6]},
        )

    def check_locator_matcher(self) -> None:
        """The comparison itself is exact: no prefix or fuzzy locator is accepted.

        ``locators_match_exactly`` is the only matcher the audit uses.  These
        controls assert that a prefix, a substring, a ``startswith`` variant and a
        fuzzy/overlapping variant of the expected locator are rejected, so
        "prefix/fuzzy matching = 0" is *measured* rather than asserted in prose.
        """

        expected = "第10页 / 供应商须知前附表 / 第3.3.1条 / （pdf_table_cell）"
        controls = {
            "prefix_of_section_accepted": locators_match_exactly(
                expected, "第10页 / 供应商须知前附表"
            ),
            "substring_accepted": locators_match_exactly("供应商须知前附表", expected),
            "startswith_accepted": locators_match_exactly(expected, expected[:20]),
            "fuzzy_variant_accepted": locators_match_exactly(
                expected, expected.replace("第10页", "第1页")
            ),
            "exact_rejected": not locators_match_exactly(expected, expected),
        }
        accepted = sorted(key for key, value in controls.items() if value)
        self.counts["LOCATOR_PREFIX_OR_FUZZY_ACCEPTANCE_COUNT"] = len(accepted)
        self.check(
            "the locator comparison accepts only exact formatter output",
            not accepted,
            f"4 negative control(s) + 1 positive control, accepted deviations={accepted}",
            {"controls": controls, "matcher": "tender_basic.evidence_unit.locators_match_exactly"},
        )

    def check_locator_identity(self) -> None:
        """A clipped section must still identify its own source unit.

        Production clips a section only where its own derivation says so
        (``opening_handle`` 48 characters, ``numbered_item`` 40).  The clip and its
        limit are recorded per row, and a clipped section may not be shorter than
        the source's identifying words.
        """

        problems: list[dict[str, Any]] = []
        for record in getattr(self, "locator_records", []):
            limit = record.get("clip_limit")
            if not limit:
                continue
            visible = str(record["expected_visible_section"])
            if len(visible) < 8 or visible != str(record["actual_visible_section"]):
                problems.append(
                    {
                        "item_id": record["item_id"],
                        "clip_limit": limit,
                        "visible": visible[:60],
                    }
                )
        self.counts["LOCATOR_CLIP_IDENTITY_PROBLEM_COUNT"] = len(problems)
        self.check(
            "a clipped locator section still identifies its own source unit",
            not problems,
            f"{self.counts.get('LOCATOR_CLIPPED_SECTION_COUNT', 0)} clipped section(s) checked",
            {"problems": problems[:6]},
        )

    def _raw_rows(self, title: str) -> list[tuple[str, ...]]:
        """The sheet's rows as raw column tuples (the 04 sheet has a title row)."""

        from openpyxl import load_workbook

        workbook = load_workbook(self.workbook, data_only=True, read_only=True)
        try:
            sheet = workbook[title]
            return [
                tuple("" if value is None else str(value) for value in row)
                for row in sheet.iter_rows(values_only=True)
            ]
        finally:
            workbook.close()

    def _form_sections(self) -> list[tuple[str, list[str]]]:
        """``(section label, form classes)`` read from the delivered 04 sheet."""

        sections: list[tuple[str, list[str]]] = []
        for values in self._raw_rows("04_报价与限价"):
            first = (values[0] if values else "").strip()
            if re.match(r"^[一二三四五六七八九十]+、", first):
                sections.append((first, []))
                continue
            if not sections or len(values) < 5:
                continue
            if first == "源页码":
                continue  # the table's own header row
            form_class = str(values[4]).strip()
            if form_class and "表单类型" not in form_class:
                sections[-1][1].append(form_class)
        return sections

    def check_form_section_grouping(self) -> None:
        """A blank quote form and a blank experience form may not share a section."""

        sections = self._form_sections()
        problems: list[dict[str, Any]] = []
        for label, classes in sections:
            # the quotation *section* is the one that presents quotation forms;
            # "非报价表单" names the other section and must not be read as one
            if "空白报价表单" not in label:
                continue
            for form_class in classes:
                if "空白报价表单" not in form_class:
                    problems.append({"section": label, "form_class": form_class[:60]})
        self.counts["FORM_SECTION_GROUPING_PROBLEM_COUNT"] = len(problems)
        self.check(
            "blank non-quotation forms are not listed under the quotation section",
            not problems,
            f"{len(sections)} presentation section(s) checked, {len(problems)} problem(s)",
            {
                "problems": problems[:6],
                "sections": {label: len(classes) for label, classes in sections},
            },
        )

    # -- fixtures --------------------------------------------------------- #

    def audit_fixtures(
        self, rows: Sequence[Mapping[str, Any]], price_result: Mapping[str, Any]
    ) -> None:
        """Every finding, bound to its concern rather than to a row id.

        Concern ids are stable; row ids are the address the human review cites and
        are frozen, so a fixture keyed by concern cannot drift when a new row is
        appended.
        """

        # locator fidelity is a cross-case invariant, so it is asserted for every
        # case before the case-specific fixtures
        self._locator_fixtures(
            {record["item_id"]: record for record in getattr(self, "locator_records", [])}
        )
        if self.case != "case_001":
            return
        by_concern = self._by_concern()
        tiers = SOURCE_TIERS[self.case]

        def text_of(concern_id: str, field: str) -> str:
            row = by_concern.get(concern_id) or {}
            return re.sub(r"\s+", "", str(row.get(field) or ""))

        def row_of(concern_id: str) -> Mapping[str, Any]:
            return by_concern.get(concern_id) or {}

        def evidence(concern_id: str, *, fields: str = "requirement") -> str:
            row = row_of(concern_id)
            return (
                f"concern={concern_id} row={row.get('item_id')} sheet={row.get('sheet')} "
                f"cell={row.get('cell')} | requirement={str(row.get('requirement'))[:130]} "
                f"| {fields}={str(row.get(fields.split(',')[0]))[:90]}"
            )

        # -- banked fixes -------------------------------------------------- #
        requirement = text_of("BID_BOND_EVIDENCE", "requirement")
        self.fixture(
            "D14",
            all(token in requirement for token in ("不按", "3.4.1", "否决")),
            "D14 the bid-bond rejection keeps its negated condition",
            evidence("BID_BOND_EVIDENCE"),
        )
        requirement = text_of("PERFORMANCE_BOND", "requirement")
        self.fixture(
            "D37",
            all(token in requirement for token in ("不能按", "7.3.1", "放弃成交")),
            "D37 the performance-bond forfeiture keeps its negated condition",
            evidence("PERFORMANCE_BOND"),
        )
        self.fixture(
            "D39",
            "＿＿" in text_of("CONTRACT_PAYMENT", "requirement"),
            "D39 the contract's blank grace period stays a blank",
            evidence("CONTRACT_PAYMENT"),
        )
        standards = text_of("TECHNICAL_STANDARD_COMPLIANCE", "requirement")
        self.fixture(
            "D45",
            "（11）" in standards and "…" not in standards,
            "D45 the technical-standard list is not visibly truncated",
            evidence("TECHNICAL_STANDARD_COMPLIANCE"),
        )
        test_report = text_of("TECHNICAL_TEST_REPORT", "requirement")
        self.fixture(
            "D46",
            "第三方检测" in test_report and "第四条" not in test_report,
            "D46 the starred test duty does not absorb the next heading",
            evidence("TECHNICAL_TEST_REPORT"),
        )
        mandatory = {
            str(row.get("requirement_id")): row
            for row in self._rows(MANDATORY_SHEET_TITLE)
        }
        for key, concern_id in (
            ("DR013", "GENERAL_BIDDER_OBLIGATION"),
            ("DR038", "AUTHORIZATION"),
        ):
            row = row_of(concern_id)
            item_id = str(row.get("item_id") or "")
            reviewer = mandatory.get(item_id)
            if not item_id or reviewer is None:
                self.fixture(key, False, f"{concern_id} is not delivered on both sheets")
                continue
            risk = str(row.get("risk") or "")
            veto = str(reviewer.get("否决性") or "").strip()
            self.fixture(
                key,
                not (risk == "一票否决" and veto != "是"),
                "the legacy 一票否决 does not contradict the row's own 否决依据",
                f"row={item_id} risk_cell={row.get('risk_cell')} risk={risk!r} "
                f"否决性={veto!r} 强制性类型={reviewer.get('强制性类型')!r}",
            )
        # D34: the validity row's locator names its own clause.
        validity = row_of("BID_VALIDITY")
        self.fixture(
            "D34",
            "3.3.1" in str(validity.get("locator") or "")
            and "1.12 分包" not in str(validity.get("locator") or ""),
            "D34 the validity row's locator names its own clause",
            f"row={validity.get('item_id')} cell={validity.get('cell')} "
            f"locator={str(validity.get('locator'))[:90]}",
        )
        # D16 / D22: no corrupted source join is delivered.
        for key, concern_id in (
            ("D16", "QUALIFICATION_LICENSE"),
            ("D22", "FILE_FORMAT"),
        ):
            delivered = text_of(concern_id, "requirement")
            corrupt = [
                pattern.pattern
                for pattern in _CORRUPT_JOIN_RES
                if pattern.search(delivered)
            ]
            self.fixture(
                key,
                not corrupt,
                f"{key} the delivered requirement carries no corrupted source join",
                f"corrupt={corrupt} | " + evidence(concern_id),
            )

        # -- round-9 findings ---------------------------------------------- #
        # D23 / D38: every source tier is delivered with its own condition and
        # score, as an alternative rather than a simultaneous obligation.
        for concern_id, source_tiers in tiers.items():
            row = row_of(concern_id)
            requirement = text_of(concern_id, "requirement").replace("的得", "得")
            action = text_of(concern_id, "action")
            criteria = text_of(concern_id, "criteria")
            # every tier keeps its own condition and its own score, in both the
            # delivered requirement and the reviewer's per-tier check
            missing = [
                condition
                for condition, score in source_tiers
                if condition not in requirement or f"得{score}" not in requirement
            ]
            unchecked = [
                condition
                for condition, score in source_tiers
                if not any(
                    re.sub(r"\s+", "", line.lstrip("①②③④⑤⑥⑦⑧⑨(10)0123456789. ")).startswith(
                        "逐档核对"
                    )
                    and condition in re.sub(r"\s+", "", line)
                    and f"得{score}" in re.sub(r"\s+", "", line)
                    for line in str(row.get("action") or "").splitlines()
                )
            ]
            exclusive = "不得要求同时满足全部分档" in criteria
            simultaneous = sum(
                1
                for line in criteria.split("。")
                if "且响应文件一致" in line and "接受银行承兑" in line
            ) > 1
            self.fixture(
                concern_id,
                not missing and not unchecked and exclusive and not simultaneous,
                f"{concern_id}: each source tier keeps its own ratio/condition, score and check",
                f"row={row.get('item_id')} cell={row.get('cell')} missing={missing} "
                f"unchecked={unchecked} exclusive={exclusive} simultaneous={simultaneous} "
                f"| requirement={requirement[:150]}",
            )

        # D56: the pre-bid decision and the question/clarification deadline are
        # two rows, each coherent with its own source.
        pre_bid = row_of("PRE_BID_MEETING")
        query = row_of("QUERY_DEADLINE")
        pre_action = str(pre_bid.get("action") or "")
        pre_requirement = str(pre_bid.get("requirement") or "")
        pre_criteria = str(pre_bid.get("criteria") or "")
        ok = bool(pre_bid) and bool(query)
        ok = ok and pre_bid.get("cell") != query.get("cell")
        ok = ok and "采购预备会" in pre_requirement and "不召开" in pre_requirement
        ok = ok and "采购预备会" in pre_action and "不召开" in pre_action
        ok = ok and "提问" not in pre_action and "澄清" not in pre_action
        ok = ok and "提问" not in pre_criteria and "澄清" not in pre_criteria
        ok = ok and "提出问题的时间" in str(query.get("requirement") or "")
        self.fixture(
            "D56",
            ok,
            "D56 the pre-bid-meeting decision and the question/clarification deadline are separate concerns",
            f"pre_bid={pre_bid.get('cell')} action={pre_action[:110]} "
            f"| query={query.get('cell')} requirement={str(query.get('requirement'))[:80]}",
        )

        # D57: an action may only cite the row's own page and clause.
        anchor_problems = []
        for row in rows:
            action = str(row.get("action") or "")
            locator = str(row.get("locator") or "")
            own_page = re.search(r"第(\d+)页", locator)
            own_clause = re.search(r"第([\d.]+)条", locator)
            for page, clause in _ANCHOR_RE.findall(action):
                if own_page and page != own_page.group(1):
                    anchor_problems.append((row.get("item_id"), page, own_page.group(1)))
                elif clause and own_clause and clause != own_clause.group(1):
                    anchor_problems.append((row.get("item_id"), clause, own_clause.group(1)))
        self.fixture(
            "D57",
            not anchor_problems,
            "D57 no delivered action cites a page or clause its own row does not quote",
            f"problems={anchor_problems[:4]} | submission_action="
            f"{str(row_of('SUBMISSION_DEADLINE').get('action'))[:120]}",
        )

        # D50: the base score and the ceiling stay distinct, and the bidder is not
        # asked to restate the evaluation rule.
        formula = row_of("SCORING_PRICE_FORMULA")
        formula_action = text_of("SCORING_PRICE_FORMULA", "action")
        formula_criteria = text_of("SCORING_PRICE_FORMULA", "criteria")
        demands_rule = any(
            _RULE_VALUE_RE.search(line)
            for line in str(formula.get("action") or "").splitlines()
            if _BIDDER_DECLARATION_RE.search(line)
        )
        self.fixture(
            "D50",
            not demands_rule
            and "基本分30" in formula_action
            and "本项最高40" in formula_action
            # the award parameter is verified by the reviewer with the row's own
            # wording, never demanded from the bidder as a restatement of the rule
            and "按上述要求的数值逐项核对响应报价" in formula_action
            and "核对该响应报价" in formula_criteria,
            "D50 the base score and the ceiling stay distinct; the rule is verified, not restated",
            f"row={formula.get('item_id')} cell={formula.get('cell')} "
            f"demands_rule={demands_rule} | action={formula_action[:150]}",
        )

        # D40 / D43: the retention rows cite their own contract clause.
        for key, concern_id in (
            ("D40", "RETENTION_RELEASE_PERIOD"),
            ("D43", "RETENTION_MONEY_RATIO"),
        ):
            row = row_of(concern_id)
            locator = str(row.get("locator") or "")
            self.fixture(
                key,
                "第2.3条" in locator and "其他资料" not in locator,
                f"{key} the retention row cites the contract clause that states it (2.3 付款方式)",
                f"row={row.get('item_id')} cell={row.get('cell')} locator={locator[:90]}",
            )

        # Page-53 form: presented in its own non-quotation section.
        sections = self._form_sections()
        history_sections = [
            label
            for label, classes in sections
            if any("空白报价表单" not in form_class for form_class in classes)
        ]
        quotation_sections = [
            label
            for label, classes in sections
            if classes and all("空白报价表单" in form_class for form_class in classes)
        ]
        self.fixture(
            "FORM_P53_PRESENTATION",
            bool(history_sections)
            and all("类似项目" not in label for label in quotation_sections),
            "the similar-project-history form is presented in its own non-quotation section",
            "sections="
            + json.dumps({label: classes for label, classes in sections}, ensure_ascii=False),
        )

        # Locator fidelity, named per finding: every one of these rows must show a
        # section that is exactly the production formatter's output for its own
        # PRIMARY evidence unit, read from the saved workbook (see
        # ``audit_locator_fixtures``, which runs for every case).
        records = {record["item_id"]: record for record in getattr(self, "locator_records", [])}
        self._locator_fixtures(records)

    def _row_probe_text(self, row: Mapping[str, Any]) -> str:
        return re.sub(
            r"[\s\u3000]+",
            "",
            f"{row.get('requirement') or ''} {row.get('excerpt') or ''}",
        )

    def _source_probe_text(self) -> str:
        if getattr(self, "_source_probe_cache", None) is None:
            self._source_probe_cache = re.sub(
                r"[\s\u3000]+", "", " ".join(self._source_spans())
            )
        return self._source_probe_cache

    def _locator_fixture_rows(
        self, concern_id: str, probes: Sequence[str]
    ) -> tuple[list[Mapping[str, Any]], str]:
        """``(rows, resolution)`` for one named locator fixture.

        The finding is bound to its concern, but a case's own contract may deliver
        the same source concept inside a sibling concern (CASE002 states the
        retention ratio in the clause that also states the release period).  The
        resolution therefore falls back to the *content* the finding is about, and
        reports the fallback it used: ``concern`` / ``content`` /
        ``source_present_undelivered`` / ``source_absent``.
        """

        rows = self.fixture_rows()
        keyed = [
            row
            for row in rows
            if str(getattr(row.get("item"), "concern_id", "") or "") == concern_id
        ]
        if keyed:
            return keyed, "concern"
        matched = [
            row
            for row in rows
            if all(
                re.search(pattern, self._row_probe_text(row)) for pattern in probes
            )
        ]
        if matched:
            return matched, "content"
        haystack = self._source_probe_text()
        if all(re.search(pattern, haystack) for pattern in probes):
            return [], "source_present_undelivered"
        return [], "source_absent"

    def _locator_fixtures(self, records: Mapping[str, Mapping[str, Any]]) -> None:
        """Locator fidelity fixtures, asserted for every case.

        A fixture is re-anchored to the delivered row that carries the probed
        content when the case's contract merges the concept into a sibling concern;
        if the case's source states the content while no delivered row carries it,
        the fixture fails.  So the finding is never dropped and never accepted on a
        weaker match.
        """

        fixture_records: dict[str, dict[str, Any]] = {}
        for key, concern_id, probes in LOCATOR_FIXTURES:
            rows, resolution = self._locator_fixture_rows(concern_id, probes)
            item_ids = [str(row.get("item_id") or "") for row in rows]
            here = [records.get(item_id) for item_id in item_ids]
            if resolution == "source_absent":
                self.fixture(
                    key,
                    True,
                    f"{key}: not applicable — this case's source states no such content",
                    f"concern={concern_id} probes={list(probes)} resolution={resolution}",
                )
                fixture_records[key] = {
                    "fixture": key,
                    "concern_id": concern_id,
                    "probes": list(probes),
                    "resolution": resolution,
                    "item_ids": [],
                    "records": [],
                    "result": "NOT_APPLICABLE",
                }
                continue
            ok = (
                bool(here)
                and all(record is not None for record in here)
                and all(record.get("result") == "PASS" for record in here)
            )
            self.fixture(
                key,
                ok,
                f"{key}: the delivered locator equals the production formatter output",
                json.dumps(
                    {
                        "concern_id": concern_id,
                        "resolution": resolution,
                        "item_ids": item_ids,
                        "records": here,
                    },
                    ensure_ascii=False,
                )[:400],
            )
            fixture_records[key] = {
                "fixture": key,
                "concern_id": concern_id,
                "probes": list(probes),
                "resolution": resolution,
                "item_ids": item_ids,
                "records": here,
                "result": "PASS" if ok else "FAIL",
            }
        self.locator_fixture_records_map = fixture_records
        # CASE003's bid-bond row historically inherited the *previous* clause's
        # sentence as its section; the row must now carry its own unit's section.
        if self.case == "case_003":
            item_id = self._item_for_concern("BID_BOND_EVIDENCE") or ""
            record = records.get(item_id)
            self.fixture(
                "LOCATOR_CASE003_BID_BOND",
                bool(record)
                and record.get("result") == "PASS"
                and not re.search(r"[，。；;]", str(record.get("actual_visible_section") or "")),
                "the CASE003 bid-bond locator no longer inherits another clause's sentence",
                json.dumps(record, ensure_ascii=False)[:600] if record else "BID_BOND_EVIDENCE not delivered",
            )

    def _item_for_concern(self, concern_id: str) -> str | None:
        for item in self.items:
            if item.concern_id == concern_id:
                return item.item_id
        return None

    def _price_result(self) -> Mapping[str, Any]:
        from tender_basic.review_workbook_views import _price_table_rows

        return _price_table_rows(self.document)

    # -- report ----------------------------------------------------------- #

    def audit(self) -> dict[str, Any]:
        data = super().audit()
        self.check_action_anchor()
        self.check_locator_coherence()
        self.check_locator_matcher()
        self.check_locator_identity()
        self.check_form_section_grouping()
        self.audit_fixtures(self.fixture_rows(), self._price_result())
        failed = [check.name for check in self.checks if not check.ok]
        failed_fixtures = [
            key for key, value in self.fixtures.items() if value["status"] != "PASS"
        ]
        fixture_records = getattr(self, "locator_fixture_records_map", {})
        data.update(
            {
                "schema": SCHEMA,
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
                "locator_records": getattr(self, "locator_records", []),
                "locator_fixtures": fixture_records,
                "locator_fixture_summary": {
                    "total": len(fixture_records),
                    "resolved_by": sorted(
                        {entry["resolution"] for entry in fixture_records.values()}
                    ),
                    "failed": [
                        key
                        for key, entry in fixture_records.items()
                        if entry["result"] == "FAIL"
                    ],
                },
            }
        )
        return data


def _delivered_locator(text: str) -> str:
    """The locator exactly as the workbook cell prints it.

    The legacy sheet writes the locator and then the evidence excerpt into the same
    cell, so the locator ends at the source-unit kind marker.
    """

    raw = str(text or "").strip()
    match = re.search(r"（pdf_[a-z_]+）", raw)
    if match:
        return raw[: match.end()].strip()
    return raw


def _split_locator(locator: str) -> tuple[str, str, str, str]:
    """``(page, section, clause, kind)`` exactly as ``_locator_text`` joined them.

    The section is whatever sits between the page part and the clause/kind parts,
    so a section that itself contains " / " survives unchanged (round-9 fixture:
    CASE003's authorization row printed a section containing "/单位电子签章" and a
    naive split read half of it).
    """

    text = str(locator or "").strip()
    kind = ""
    match = re.search(r"（(pdf_[a-z_]+)）\s*$", text)
    if match:
        kind = match.group(1)
        text = text[: match.start()].rstrip(" /")
    clause = ""
    # the clause field is printed as "第{clause}条", so it is the final " / " slot
    # (a section may itself contain " / ", and a section may open with 第…条)
    if " / " in text:
        head, _separator, tail = text.rpartition(" / ")
        match = re.fullmatch(r"第(.+?)条", tail.strip())
        if match:
            clause = match.group(1).strip()
            text = head
    page = ""
    match = re.match(r"^第(\d+)页", text)
    if match:
        page = match.group(1)
        text = text[match.end() :]
        if text.startswith(" / "):
            text = text[3:]
    return page, text.strip(), clause, kind


def _tiers_in(text: str) -> list[tuple[str, str]]:
    from tender_basic.review_point import scoring_tiers

    return scoring_tiers(text)


def _form_groups(groups: Sequence[Any]) -> dict[int, list[str]]:
    """``id(form) -> [section label]`` for the 04 sheet's presentation sections."""

    out: dict[int, list[str]] = {}
    for entry in groups:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            label, forms = entry
            for form in forms or ():
                out.setdefault(id(form), []).append(str(label))
    return out


def markdown(data: Mapping[str, Any]) -> str:
    lines = [
        f"# Round 9 delivered-content audit — {data['case']}",
        "",
        f"- build: `{data['build_id']}`",
        f"- workbook: `{data['workbook']}`",
        f"- sha256: `{data['workbook_sha256']}`",
        f"- verdict: **{data['verdict']}**",
        f"- checks: {data['passed_count']}/{data['check_count']}",
        f"- fixtures: {data['fixture_summary']['passed']}/{data['fixture_summary']['total']}",
        "",
        "## Checks",
        "",
        "| check | result | detail |",
        "| --- | --- | --- |",
    ]
    for check in data["checks"]:
        lines.append(
            f"| {check['check']} | {'PASS' if check['ok'] else 'FAIL'} | {check['detail']} |"
        )
    lines += ["", "## Fixtures", "", "| fixture | result | detail |", "| --- | --- | --- |"]
    for key in sorted(data["fixtures"]):
        fixture = data["fixtures"][key]
        lines.append(f"| {key} | {fixture['status']} | {fixture['detail']} |")
    return "\n".join(lines) + "\n"


def write_case_report(case: str, *, case_dir: Path | None = None) -> dict[str, Any]:
    report = Round9Report(case, case_dir=case_dir)
    data = report.audit()
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = f"review_workbook_round9_{case}"
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
        path = REPORTS / "review_workbook_round9_generalization.json"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"generalization: {summary['verdict']} -> {path.name}")
    return 0 if all(data["verdict"] == "PASS" for data in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
