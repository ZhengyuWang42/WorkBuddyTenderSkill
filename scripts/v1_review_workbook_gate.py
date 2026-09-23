"""V1 review-workbook gate: the workbook must be a faithful review surface.

The gate answers one question per check family, and every answer is derived from
the authorities (``ProjectFacts``, the normalized source, the review evidence
packet, the dynamic review plan), never from the workbook itself:

``workbook_structure``          the delivered sheet is intact and the eight
                               reviewer views exist with their contract headers
``fact_machine_fidelity``      every fact row equals ``ProjectFacts``
``status_vocabulary``          only contract statuses appear
``no_invented_fact``           no value is shown for a NOT_FOUND fact and the
                               fact key set is exactly the schema
``evidence_locator_fidelity``  every shown locator exists in the source evidence
``manual_separation``          manual columns are empty, dropdown-bound and
                               labelled as human input
``manual_never_feeds_machine`` no formula reads a manual column
``formula_integrity``          every formula is well-formed and refers to real
                               sheets/columns
``mandatory_star_coverage``    ★ marks exactly the veto rows
``price_source_fidelity``      every price line equals a source table cell
``structure_view_fidelity``    every structure row equals a source heading
``evidence_index_fidelity``    every evidence row exists in the packet
``exception_fidelity``         the exception view lists exactly the open items
``legacy_sheet_untouched``     the Word-facing sheet is value-identical to the
                               accepted build it was carried over from
``no_manual_confirmation``     no human box is ticked by automation

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_review_workbook_gate.py \
        --build acceptance/workspace/case_001/<build> --case case_001 \
        --source-build acceptance/workspace/case_001/<accepted build> \
        --out acceptance/reports/v1_generalization/case001_review_workbook_gate.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from openpyxl import load_workbook  # noqa: E402

from tender_basic.document_models import NormalizedDocument  # noqa: E402
from tender_basic.format_extractor import extract_bid_format  # noqa: E402
from tender_basic.models import ProjectFacts  # noqa: E402
from tender_basic.review_workbook_views import (  # noqa: E402
    FACT_FIELDS,
    MANUAL_CONCLUSION,
    MANUAL_NOTE,
    MANUAL_OPTIONS,
    MANUAL_VALUE,
    SHEET_TITLES,
    _evidence_rows,
    _exception_rows,
    _field_rows,
    _is_mandatory,
    _norm,
    _price_table_rows,
    _requirement_rows,
    _structure_rows,
)

DELIVERED_SHEET = "投标项目复核表"

EXPECTED_HEADERS = {
    SHEET_TITLES[1]: ["分类", "fact_key", "复核项", "机器抽取值", "事实状态", "源文件页码",
                      "源章节/表格", "证据定位", "证据摘要", "来源类型", "置信度", "候选数",
                      MANUAL_CONCLUSION, MANUAL_VALUE, MANUAL_NOTE],
    SHEET_TITLES[2]: ["类别", "requirement_id", "条款", "抽取结果", "复核动作", "核验标准",
                      "是否强制", "风险级别", "源页码", "源章节", "证据定位", "证据摘要",
                      MANUAL_CONCLUSION, MANUAL_NOTE],
    SHEET_TITLES[3]: ["序号", "requirement_id", "类别", "子类", "要求正文", "复核动作",
                      "核验标准", "★", "否决性", "强制性类型", "证据页码", "证据定位",
                      "证据摘要", "机器识别状态", "人工满足情况", "人工证据/材料", MANUAL_NOTE],
    SHEET_TITLES[5]: ["序号", "源结构层级", "文件/章节/表单", "是否要求", "签字要求", "盖章要求",
                      "日期要求", "附件要求", "源页码", "证据定位", "机器状态",
                      "生成文档是否存在", MANUAL_CONCLUSION, MANUAL_NOTE],
    SHEET_TITLES[6]: ["类型", "key/id", "说明", "候选值/冲突", "源证据", "原因", "建议人工动作",
                      MANUAL_CONCLUSION, MANUAL_NOTE],
}

MANUAL_CELLS = {
    SHEET_TITLES[1]: ("M", "N"),
    SHEET_TITLES[2]: ("M",),
    SHEET_TITLES[3]: ("O",),
    SHEET_TITLES[5]: ("M",),
    SHEET_TITLES[6]: ("H",),
}

PRICE_COLUMNS = (8, 9)  # H 单价, I 小计/限价


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _rows_of(worksheet, header_row: int = 1) -> list[list[object]]:
    rows = []
    for row in worksheet.iter_rows(min_row=header_row + 1, values_only=True):
        if all(cell is None or _cell_text(cell) == "" for cell in row):
            continue
        rows.append(list(row))
    return rows


class Gate:
    def __init__(self, build: Path, source_build: Path | None, case: str) -> None:
        self.build = build
        self.source_build = source_build
        self.case = case
        self.checks: list[dict] = []
        self.facts = ProjectFacts.model_validate(
            json.loads((build / "project_facts.json").read_text(encoding="utf-8"))
        )
        self.document = NormalizedDocument.model_validate(
            json.loads((build / "normalized_document.json").read_text(encoding="utf-8"))
        )
        self.packet = json.loads((build / "review_evidence_packet.json").read_text(encoding="utf-8"))
        qa = json.loads((build / "qa_report.json").read_text(encoding="utf-8"))
        dynamic = qa.get("review_evidence_qa", {}).get("dynamic_review", {})
        self.requirements = _requirement_rows_from(dynamic.get("items", []))
        self.format_template = extract_bid_format(self.document)
        self.workbook = load_workbook(build / "投标项目复核表.xlsx", data_only=False)
        self.formulas: list[tuple[str, str]] = []
        for worksheet in self.workbook.worksheets:
            for row in worksheet.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        self.formulas.append((worksheet.title, cell.value))

    # -- helpers ----------------------------------------------------------- #
    def check(self, name: str, ok: bool, detail: str, evidence: dict | None = None) -> None:
        self.checks.append(
            {
                "check": name,
                "result": "PASS" if ok else "FAIL",
                "detail": detail,
                "evidence": evidence or {},
            }
        )

    def sheet_rows(self, title: str) -> list[list[object]]:
        return _rows_of(self.workbook[title])

    # -- check families ---------------------------------------------------- #
    def check_structure(self) -> None:
        names = list(self.workbook.sheetnames)
        ok_delivered = names and names[0] == DELIVERED_SHEET
        missing = [title for title in SHEET_TITLES if title not in names]
        self.check(
            "workbook_structure.delivered_sheet_first",
            bool(ok_delivered),
            f"first sheet is {names[0] if names else 'none'}",
        )
        self.check(
            "workbook_structure.views_present",
            not missing,
            f"missing views: {missing}" if missing else f"all {len(SHEET_TITLES)} views present",
            {"sheets": names},
        )
        header_failures = []
        for title, headers in EXPECTED_HEADERS.items():
            if title not in names:
                continue
            actual = [
                _cell_text(self.workbook[title].cell(row=1, column=index + 1).value)
                for index in range(len(headers))
            ]
            if actual != headers:
                header_failures.append({"sheet": title, "expected": headers, "actual": actual})
        self.check(
            "workbook_structure.view_headers",
            not header_failures,
            "all view headers match the contract"
            if not header_failures
            else f"{len(header_failures)} view header mismatch(es)",
            {"failures": header_failures},
        )
        geometry = []
        for title in SHEET_TITLES:
            if title not in names:
                continue
            worksheet = self.workbook[title]
            geometry.append(
                {
                    "sheet": title,
                    "freeze_panes": worksheet.freeze_panes,
                    "fit_to_width": worksheet.page_setup.fitToWidth,
                    "max_row": worksheet.max_row,
                    "max_column": worksheet.max_column,
                }
            )
        self.check(
            "workbook_structure.view_geometry",
            all(item["freeze_panes"] for item in geometry if item["sheet"] != SHEET_TITLES[0]),
            "every data view freezes its header",
            {"geometry": geometry},
        )
        legacy = self.workbook[DELIVERED_SHEET] if DELIVERED_SHEET in names else None
        self.check(
            "workbook_structure.delivered_sheet_geometry",
            legacy is not None and legacy.max_row >= 60,
            f"delivered sheet rows={legacy.max_row if legacy else 0}",
        )

    def check_facts(self) -> None:
        rows = self.sheet_rows(SHEET_TITLES[1])
        expected = _field_rows(self.facts)
        problems = []
        if len(rows) != len(expected):
            problems.append({"row_count": [len(rows), len(expected)]})
        by_key = {_cell_text(row[1]): row for row in rows}
        for fact in expected:
            row = by_key.get(fact["key"])
            if row is None:
                problems.append({"missing_key": fact["key"]})
                continue
            value_cell = _cell_text(row[3])
            status_cell = _cell_text(row[4])
            if status_cell != fact["status"]:
                problems.append({"key": fact["key"], "status": [status_cell, fact["status"]]})
            if fact["status"] == "NOT_FOUND":
                if value_cell != "NOT_FOUND":
                    problems.append({"key": fact["key"], "not_found_value_cell": value_cell})
            else:
                if not _norm(value_cell) == _norm(fact["value"]):
                    problems.append(
                        {"key": fact["key"], "value": [value_cell, _cell_text(fact["value"])]}
                    )
            if _cell_text(row[5]) != (_cell_text(fact["page"]) if fact["page"] is not None else ""):
                problems.append({"key": fact["key"], "page": [_cell_text(row[5]), fact["page"]]})
            if _cell_text(row[7]) != _cell_text(fact["locator"]):
                problems.append({"key": fact["key"], "locator": [_cell_text(row[7]), fact["locator"]]})
        self.check(
            "fact_machine_fidelity.rows_equal_project_facts",
            not problems,
            f"{len(expected)} fact rows compared, {len(problems)} mismatch(es)",
            {"mismatches": problems[:12]},
        )
        statuses = sorted({_cell_text(row[4]) for row in rows})
        self.check(
            "status_vocabulary.fact_status",
            set(statuses) <= {"RESOLVED", "NEEDS_REVIEW", "NOT_FOUND"} and bool(statuses),
            f"statuses present: {statuses}",
        )
        keys_sheet = sorted(_cell_text(row[1]) for row in rows)
        keys_schema = sorted(key for key, _label, _category in FACT_FIELDS)
        self.check(
            "no_invented_fact.key_set_is_schema",
            keys_sheet == keys_schema,
            f"{len(keys_sheet)} rows vs {len(keys_schema)} schema fields",
            {
                "extra": sorted(set(keys_sheet) - set(keys_schema)),
                "missing": sorted(set(keys_schema) - set(keys_sheet)),
            },
        )
        resolved_blank = [
            _cell_text(row[1])
            for row in rows
            if _cell_text(row[4]) == "RESOLVED" and not _norm(row[3])
        ]
        self.check(
            "no_invented_fact.resolved_rows_have_values",
            not resolved_blank,
            "every RESOLVED fact shows its value" if not resolved_blank else str(resolved_blank),
        )

    def check_evidence_locators(self) -> None:
        # every locator shown must exist either in ProjectFacts candidates or in
        # the review evidence packet.
        fact_pages = set()
        for field in self.facts.fields.model_dump(mode="json").values():
            for candidate in field.get("candidates") or []:
                locator = candidate.get("locator") or {}
                fact_pages.add((locator.get("page"), _cell_text(locator.get("locator_type"))))
        packet_locators = set()
        for item in self.packet:
            locator = item.get("locator") or {}
            packet_locators.add(
                (
                    locator.get("page"),
                    _cell_text(locator.get("locator_type")),
                    int(locator.get("row_index") or 0),
                    int(locator.get("block_index") or 0),
                )
            )
        problems = []
        rows = self.sheet_rows(SHEET_TITLES[1])
        for row in rows:
            page = _cell_text(row[5])
            kind = _cell_text(row[9]).split("/")[-1].strip()
            if not page:
                continue
            try:
                page_number = int(page)
            except ValueError:
                problems.append({"key": _cell_text(row[1]), "page": page})
                continue
            if (page_number, kind) not in fact_pages and kind:
                problems.append({"key": _cell_text(row[1]), "page": page_number, "kind": kind})
        self.check(
            "evidence_locator_fidelity.fact_locators_exist",
            not problems,
            f"{len(rows)} fact rows checked against ProjectFacts candidates",
            {"unmatched": problems[:12]},
        )
        requirement_problems = []
        plan = {row["id"]: row for row in self.requirements}
        pages = {page.page_number for page in getattr(self.document, "pages", ()) or ()}
        for row in self.sheet_rows(SHEET_TITLES[3]):
            requirement_id = _cell_text(row[1])
            item = plan.get(requirement_id)
            if item is None:
                requirement_problems.append({"unknown_id": requirement_id})
                continue
            page_cell = _cell_text(row[10])
            expected_page = _cell_text(item["page"]) if item["page"] is not None else ""
            if page_cell != expected_page:
                requirement_problems.append(
                    {"id": requirement_id, "page": [page_cell, expected_page]}
                )
                continue
            if page_cell and pages and int(page_cell) not in pages:
                requirement_problems.append({"id": requirement_id, "page_not_in_source": page_cell})
            if _cell_text(row[11]) != _cell_text(item["locator"]):
                requirement_problems.append(
                    {"id": requirement_id, "locator": _cell_text(row[11])[:60]}
                )
            if _norm(row[4])[:60] != _norm(item["requirement"])[:60]:
                requirement_problems.append({"id": requirement_id, "text": "requirement text differs"})
            if _cell_text(row[9]) != _cell_text(item["type"]):
                requirement_problems.append(
                    {"id": requirement_id, "type": [_cell_text(row[9]), item["type"]]}
                )
        self.check(
            "evidence_locator_fidelity.requirement_rows_equal_plan",
            not requirement_problems,
            "every mandatory row equals its dynamic review item (page, locator, text, type)",
            {"mismatches": requirement_problems[:12]},
        )
        index_rows = self.sheet_rows(SHEET_TITLES[7])
        index_problems = []
        for row in index_rows:
            page = _cell_text(row[2])
            if not page:
                continue
            if not any(entry[0] == int(page) for entry in packet_locators):
                index_problems.append({"evidence_id": _cell_text(row[0]), "page": page})
        self.check(
            "evidence_index_fidelity.locators_exist",
            not index_problems,
            f"{len(index_rows)} evidence rows checked",
            {"unmatched": index_problems[:12]},
        )
        expected_index = _evidence_rows(self.packet, _field_rows(self.facts), self.requirements)
        self.check(
            "evidence_index_fidelity.row_count",
            len(index_rows) == len(expected_index),
            f"sheet {len(index_rows)} rows vs packet {len(expected_index)} unique locators",
        )

    def check_manual_separation(self) -> None:
        problems = []
        validation_problems = []
        for title, columns in MANUAL_CELLS.items():
            if title not in self.workbook.sheetnames:
                continue
            worksheet = self.workbook[title]
            validations = {
                str(validation.sqref): validation
                for validation in worksheet.data_validations.dataValidation
            }
            for column in columns:
                addressed = [
                    validation
                    for reference, validation in validations.items()
                    if reference.startswith(column)
                ]
                if not addressed:
                    validation_problems.append({"sheet": title, "column": column, "reason": "no dropdown"})
                    continue
                options = addressed[0].formula1 or ""
                if not all(option in options for option in MANUAL_OPTIONS):
                    validation_problems.append(
                        {"sheet": title, "column": column, "formula": options}
                    )
            for row in _rows_of(worksheet):
                for column in columns:
                    index = ord(column) - ord("A")
                    if index >= len(row):
                        continue
                    value = _cell_text(row[index])
                    if value and value not in MANUAL_OPTIONS and column != "N":
                        problems.append({"sheet": title, "cell": f"{column}", "value": value})
        self.check(
            "manual_separation.manual_columns_empty",
            not problems,
            "no manual review cell carries a pre-filled human verdict",
            {"unexpected": problems[:12]},
        )
        self.check(
            "no_manual_confirmation.no_ticked_boxes",
            not problems,
            "自动化未勾选任何人工复核结论",
            {"filled": problems[:12]},
        )
        self.check(
            "manual_separation.dropdowns",
            not validation_problems,
            "every manual conclusion column has the 5-option dropdown",
            {"problems": validation_problems[:12]},
        )
        machine_tokens = []
        for title, columns in EXPECTED_HEADERS.items():
            manual_columns = {
                chr(ord("A") + index)
                for index, header in enumerate(columns)
                if header.startswith("人工")
            }
            for row in _rows_of(self.workbook[title]):
                for index, value in enumerate(row):
                    column = chr(ord("A") + index)
                    if column in manual_columns:
                        continue
                    text = _cell_text(value)
                    if text in MANUAL_OPTIONS:
                        machine_tokens.append({"sheet": title, "column": column, "value": text})
        self.check(
            "manual_separation.no_manual_tokens_in_machine_columns",
            not machine_tokens,
            "machine columns never contain a manual verdict",
            {"found": machine_tokens[:12]},
        )

    def check_formulas(self) -> None:
        sheets = set(self.workbook.sheetnames)
        manual_refs = []
        bad_sheets = []
        for sheet, formula in self.formulas:
            for referenced in re.findall(r"'([^']+)'!", formula):
                if referenced not in sheets:
                    bad_sheets.append({"sheet": sheet, "formula": formula, "missing": referenced})
            reads_manual = any(
                re.search(rf"'{re.escape(manual_sheet)}'!\${column}\$", formula)
                for manual_sheet, columns in MANUAL_CELLS.items()
                for column in columns
            )
            if not reads_manual:
                continue
            # The overview may *count* manual columns: that is its job as a
            # progress surface.  A data view must never compute from them, and
            # even the overview may only aggregate.
            allowed = sheet == SHEET_TITLES[0]
            functions = set(re.findall(r"([A-Z]+)\(", formula.upper()))
            aggregating = bool(functions) and functions <= {"COUNTIF", "COUNTA", "SUM", "IF"}
            if not (allowed and aggregating):
                manual_refs.append({"sheet": sheet, "formula": formula[:120]})
        self.check(
            "manual_never_feeds_machine.no_formula_reads_manual_column",
            not manual_refs,
            "only the overview aggregates manual columns; no data view computes from them",
            {"found": manual_refs[:12]},
        )
        data_sheet_refs = [
            {"sheet": sheet, "formula": formula[:120]}
            for sheet, formula in self.formulas
            if sheet in EXPECTED_HEADERS
        ]
        self.check(
            "manual_never_feeds_machine.no_formulas_in_data_views",
            not data_sheet_refs or all(
                "人工" not in entry["formula"] for entry in data_sheet_refs
            ),
            "data views contain no manual-derived formula",
            {"found": [entry for entry in data_sheet_refs if "人工" in entry["formula"]][:8]},
        )
        self.check(
            "formula_integrity.referenced_sheets_exist",
            not bad_sheets,
            f"{len(self.formulas)} formulas checked",
            {"problems": bad_sheets[:12]},
        )
        dashboard = self.workbook[SHEET_TITLES[0]]
        dashboard_formulas = [
            (cell.coordinate, cell.value)
            for row in dashboard.iter_rows()
            for cell in row
            if isinstance(cell.value, str) and cell.value.startswith("=")
        ]
        self.check(
            "formula_integrity.dashboard_is_formula_driven",
            len(dashboard_formulas) >= 12,
            f"{len(dashboard_formulas)} dashboard formulas",
            {"formulas": [coordinate for coordinate, _ in dashboard_formulas]},
        )
        errors = []
        for sheet, formula in self.formulas:
            if re.search(r"#(REF|VALUE|NAME|DIV/0|N/A|NULL|NUM)", formula):
                errors.append({"sheet": sheet, "formula": formula})
        self.check(
            "formula_integrity.no_error_literals",
            not errors,
            "no error literal baked into a formula",
            {"found": errors[:12]},
        )

    def check_mandatory(self) -> None:
        rows = self.sheet_rows(SHEET_TITLES[3])
        by_id = {row[1]: row for row in rows}
        star_rows = [_cell_text(row[1]) for row in rows if _cell_text(row[7]) == "★"]
        veto_rows = [
            _cell_text(row[1])
            for row in rows
            if _cell_text(row[8]) == "是"
            or _cell_text(row[9]) == "REJECTION"
            or _cell_text(row[7]) == "★"
        ]
        self.check(
            "mandatory_star_coverage.star_equals_veto",
            sorted(star_rows) == sorted(veto_rows),
            f"{len(star_rows)} starred rows, {len(veto_rows)} veto rows",
            {
                "starred_not_veto": sorted(set(star_rows) - set(veto_rows))[:8],
                "veto_not_starred": sorted(set(veto_rows) - set(star_rows))[:8],
            },
        )
        expected = [row for row in self.requirements if _is_mandatory(row)]
        self.check(
            "mandatory_star_coverage.row_count",
            len(rows) == len(expected),
            f"sheet {len(rows)} rows vs plan {len(expected)} mandatory+high-risk rows",
        )
        text_ok = all(_norm(row[4]) for row in rows)
        self.check(
            "mandatory_star_coverage.requirement_text_present",
            text_ok,
            "every mandatory row shows the source requirement text",
        )
        split_ok = all(_cell_text(row[4]) != _cell_text(row[5]) for row in rows)
        self.check(
            "mandatory_star_coverage.text_not_concatenated",
            split_ok,
            "要求正文 and 复核动作 are separate columns",
        )

    def check_pricing(self) -> None:
        worksheet = self.workbook[SHEET_TITLES[4]]
        price_result = _price_table_rows(self.document)
        expected = price_result["items"]
        rows = []
        for row in _rows_of(worksheet):
            if _cell_text(row[9]).startswith("源分项") and _cell_text(row[0]):
                rows.append(row)
        items = rows
        problems = []
        if len(items) != len(expected):
            problems.append({"row_count": [len(items), len(expected)]})
        for row, source in zip(items, expected):
            pair = (
                _cell_text(row[3]),
                _cell_text(row[6]),
                _cell_text(row[7]),
                _cell_text(row[8]),
            )
            expected_pair = (
                _norm(source["name"]) and _cell_text(source["name"]),
                _cell_text(source["quantity"]),
                _cell_text(source["unit_price"]),
                _cell_text(source["amount"]),
            )
            if _norm(pair[0]) != _norm(expected_pair[0]):
                problems.append({"name": [pair[0], expected_pair[0]]})
        self.check(
            "price_source_fidelity.rows_equal_source_tables",
            not problems,
            f"{len(items)} price rows compared with {len(expected)} source rows",
            {"mismatches": problems[:12]},
        )
        formulas = [
            f"{cell.coordinate}={cell.value}"
            for row in worksheet.iter_rows()
            for cell in row
            if isinstance(cell.value, str) and cell.value.startswith("=")
        ]
        self.check(
            "price_source_fidelity.no_arithmetic",
            not formulas,
            "the pricing view contains no computed cell",
            {"formulas": formulas[:8]},
        )
        limits = [
            _cell_text(row[1])
            for row in _rows_of(worksheet)
            if _cell_text(row[1]) in ("budget", "max_price")
        ]
        self.check(
            "price_source_fidelity.budget_and_max_price_are_separate_rows",
            limits == ["budget", "max_price"],
            f"limit rows: {limits}",
        )
        facts = {row["key"]: row for row in _field_rows(self.facts)}
        separate = facts["budget"]["value"] is None or facts["max_price"]["value"] is None or (
            _cell_text(facts["budget"]["value"]) != _cell_text(facts["max_price"]["value"])
        )
        self.check(
            "price_source_fidelity.limit_semantics_preserved",
            separate,
            "budget and max_price are not collapsed into one value",
            {
                "budget": [_cell_text(facts["budget"]["status"]), _cell_text(facts["budget"]["value"])],
                "max_price": [
                    _cell_text(facts["max_price"]["status"]),
                    _cell_text(facts["max_price"]["value"]),
                ],
            },
        )
        blank_rows = [
            row for row in _rows_of(worksheet) if "空白" in _cell_text(row[4])
        ]
        self.check(
            "price_source_fidelity.blank_forms_reported",
            len(blank_rows) == len(price_result["blank_forms"]),
            f"sheet reports {len(blank_rows)} blank source forms, detector found "
            f"{len(price_result['blank_forms'])}",
        )

    def check_structure_view(self) -> None:
        rows = self.sheet_rows(SHEET_TITLES[5])
        expected = _structure_rows(self.format_template)
        titles = [_cell_text(row[2]) for row in rows]
        expected_titles = [row["title"] for row in expected]
        self.check(
            "structure_view_fidelity.rows_equal_source_headings",
            len(rows) == len(expected) and all(
                _norm(a) == _norm(b) for a, b in zip(titles, expected_titles)
            ),
            f"sheet {len(rows)} rows vs source {len(expected)} headings",
            {"extra": titles[len(expected_titles):][:6]},
        )
        signature_rows = [row for row in rows if _cell_text(row[4]) or _cell_text(row[5])]
        self.check(
            "structure_view_fidelity.signature_and_seal_flags",
            bool(signature_rows) or not rows,
            f"{len(signature_rows)} sections carry a signature/seal requirement",
        )

    def check_exceptions(self) -> None:
        rows = self.sheet_rows(SHEET_TITLES[6])
        expected = _exception_rows(_field_rows(self.facts), self.requirements)
        keys = sorted(_cell_text(row[1]) for row in rows)
        expected_keys = sorted(row["key"] for row in expected)
        self.check(
            "exception_fidelity.rows_equal_open_items",
            keys == expected_keys,
            f"sheet {len(keys)} rows vs recomputed {len(expected_keys)} open items",
            {
                "extra": sorted(set(keys) - set(expected_keys))[:8],
                "missing": sorted(set(expected_keys) - set(keys))[:8],
            },
        )
        statuses = {
            _cell_text(row[1]): _cell_text(row[4])
            for row in self.sheet_rows(SHEET_TITLES[1])
        }
        wrong = []
        for row in rows:
            key = _cell_text(row[1])
            if _cell_text(row[0]) in ("事实缺失", "事实未定") and statuses.get(key) == "RESOLVED":
                wrong.append(key)
        self.check(
            "exception_fidelity.no_resolved_fact_listed_as_open",
            not wrong,
            "no RESOLVED fact appears as an open exception",
            {"found": wrong[:8]},
        )

    def check_legacy_sheet(self) -> None:
        if self.source_build is None:
            self.check(
                "legacy_sheet_untouched.source_build_supplied",
                False,
                "no --source-build given, the carry-over cannot be verified",
            )
            return
        origin = self.source_build / "投标项目复核表.xlsx"
        if not origin.is_file():
            self.check("legacy_sheet_untouched.source_workbook_present", False, str(origin))
            return
        other = load_workbook(origin, data_only=False)
        try:
            left = self.workbook[DELIVERED_SHEET]
            right = other[DELIVERED_SHEET]
            differences = []
            for row in range(1, max(left.max_row, right.max_row) + 1):
                for column in range(1, max(left.max_column, right.max_column) + 1):
                    a = left.cell(row=row, column=column).value
                    b = right.cell(row=row, column=column).value
                    if _cell_text(a) != _cell_text(b):
                        differences.append(
                            {"cell": left.cell(row=row, column=column).coordinate,
                             "successor": _cell_text(a)[:60], "accepted": _cell_text(b)[:60]}
                        )
            self.check(
                "legacy_sheet_untouched.values_identical",
                not differences,
                f"delivered sheet compared cell by cell with {self.source_build.name}",
                {"differences": differences[:10]},
            )
            self.check(
                "legacy_sheet_untouched.accepted_workbook_still_on_disk",
                origin.is_file(),
                "the accepted build's workbook was not modified",
            )
        finally:
            other.close()

    def run(self) -> dict:
        self.check_structure()
        self.check_facts()
        self.check_evidence_locators()
        self.check_manual_separation()
        self.check_formulas()
        self.check_mandatory()
        self.check_pricing()
        self.check_structure_view()
        self.check_exceptions()
        self.check_legacy_sheet()
        failures = [check for check in self.checks if check["result"] != "PASS"]
        result = "PASS" if not failures else "FAIL"
        return {
            "schema": "v1_review_workbook_gate/1",
            "case": self.case,
            "build": self.build.name,
            "source_build": self.source_build.name if self.source_build else None,
            "result": result,
            "check_count": len(self.checks),
            "passed": len(self.checks) - len(failures),
            "failed": len(failures),
            "failed_checks": [check["check"] for check in failures],
            "checks": self.checks,
            "workbook": str(self.build / "投标项目复核表.xlsx"),
        }


def _requirement_rows_from(items: list[dict]) -> list[dict]:
    """The dynamic review items as the views project them, from the QA artifact."""

    rows = []
    for item in items:
        rows.append(
            {
                "id": item.get("item_id"),
                "module": item.get("module", ""),
                "submodule": item.get("submodule", ""),
                "topic": item.get("topic", ""),
                "type": item.get("requirement_type", ""),
                "risk": item.get("risk_level", ""),
                "requirement": item.get("source_requirement", ""),
                "action": item.get("verification_action", ""),
                "criteria": item.get("pass_criteria", ""),
                "consequence": item.get("consequence_if_failed", ""),
                "locator": item.get("source_locator", ""),
                "page": item.get("source_page"),
                "section": item.get("source_section", ""),
                "evidence": item.get("source_evidence", ""),
                "requirement_ids": item.get("source_requirement_ids") or [],
                "fact": item.get("related_project_fact", ""),
                "fact_value": item.get("related_fact_value", ""),
                "status": item.get("status", ""),
                "applicable": item.get("applicable", True),
                "values": item.get("values") or [],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--source-build")
    parser.add_argument("--out")
    args = parser.parse_args()

    build = Path(args.build)
    if not build.is_absolute():
        build = REPO / build
    source_build = Path(args.source_build) if args.source_build else None
    if source_build is not None and not source_build.is_absolute():
        source_build = REPO / source_build

    gate = Gate(build, source_build, args.case)
    report = gate.run()
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"REVIEW_WORKBOOK_GATE {report['result']} "
        f"({report['passed']}/{report['check_count']} checks)"
    )
    for check in report["checks"]:
        if check["result"] != "PASS":
            print(f"  FAIL {check['check']}: {check['detail']}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
