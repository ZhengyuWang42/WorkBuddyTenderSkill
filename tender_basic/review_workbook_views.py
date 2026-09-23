"""Review views for ``投标项目复核表.xlsx``.

The workbook is the **human review surface** of the compiler, not an export
dump: a reviewer must be able to see what was extracted, where it came from,
what is still open, and what a human has to decide - without reading JSON.

Authority model (see ``docs/V1_DECISIONS.md``):

* ``ProjectFacts`` owns the factual values and their status,
* the normalized source / ``SourceFormat`` owns structure, requirements and
  visible form semantics,
* ``ReviewEvidence`` owns evidence locators,
* the QA reports own automated check results.

This module therefore only **projects** those authorities into sheets.  It never
resolves a fact, never promotes a status, and never invents a value:

* a ``NOT_FOUND`` fact is shown as ``NOT_FOUND`` and its value cell stays empty,
* a ``NEEDS_REVIEW`` fact keeps its competing candidates visible,
* a source presentation marker (``/`` and the like) is not a fact value,
* the manual columns are inputs *to a human*, and are never read back into a
  machine column or into ``ProjectFacts``.

Sheets are appended to the workbook the template built; the existing
``投标项目复核表`` sheet stays exactly where it is because published consumers
read it (and read ``sheetnames[0]``).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Sequence

from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# --------------------------------------------------------------------------- #
# vocabulary
# --------------------------------------------------------------------------- #

MANUAL_OPTIONS = ("未复核", "通过", "有疑问", "需修改", "不适用")
DEFAULT_MANUAL = MANUAL_OPTIONS[0]
MANUAL_CONCLUSION = "人工复核结论"
MANUAL_VALUE = "人工复核值"
MANUAL_NOTE = "人工备注"

FACT_STATUSES = ("RESOLVED", "NEEDS_REVIEW", "NOT_FOUND")

#: The 23 V1 fact fields, in schema order, with their human labels and the
#: review category a reviewer expects to find them under.  This is the fact
#: *schema* (fixed by the contract), not case data.
FACT_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("project_name", "项目名称", "项目标识"),
    ("project_number", "项目编号", "项目标识"),
    ("tender_number", "招标编号", "项目标识"),
    ("lot_name", "标段/包件名称", "项目标识"),
    ("lot_number", "标段/包件编号", "项目标识"),
    ("purchaser", "采购人", "招标主体"),
    ("tender_agency", "招标代理机构", "招标主体"),
    ("project_location", "项目地点", "招标主体"),
    ("procurement_scope", "采购范围", "采购内容"),
    ("budget", "预算金额", "报价与限价"),
    ("max_price", "最高限价", "报价与限价"),
    ("duration", "工期/供货期", "履约要求"),
    ("quality_target", "质量目标", "履约要求"),
    ("bid_deadline", "投标截止时间", "投标安排"),
    ("bid_open_time", "开标时间", "投标安排"),
    ("bid_open_location", "开标地点", "投标安排"),
    ("bid_bond_amount", "投标保证金金额", "保证金"),
    ("bid_bond_form", "投标保证金形式", "保证金"),
    ("consortium_allowed", "联合体", "投标规则"),
    ("procurement_method", "采购方式", "投标规则"),
    ("bid_validity", "投标有效期", "投标规则"),
    ("submission_method", "递交方式", "投标安排"),
    ("electronic_platform", "电子交易平台", "投标安排"),
)

#: Requirement types whose rows are commercial/contract clauses rather than
#: eligibility gates.  Taken from the source-derived requirement vocabulary.
CLAUSE_TYPES = (
    "PRICING",
    "BOND",
    "FINANCIAL",
    "DURATION",
    "QUALITY",
    "WARRANTY",
    "VALIDITY",
    "CONTRACT",
    "CONSORTIUM",
    "SUBCONTRACT",
    "LOCATION",
    "PAYMENT",
)

#: Requirement types that can veto a bid or gate eligibility.
MANDATORY_TYPES = ("REJECTION", "QUALIFICATION", "MANDATORY", "PROOF", "FORM")
MANDATORY_RISK_LEVELS = ("一票否决", "高")

SHEET_TITLES = (
    "00_复核总览",
    "01_项目事实",
    "02_关键条款",
    "03_资格否决与强制项",
    "04_报价与限价",
    "05_文件结构与签章",
    "06_冲突与缺失",
    "07_证据索引",
)

BANNER = "仅供投标文件编制与人工复核 —— 人工复核完成前，本工作簿不构成可提交状态"

#: A wrapped row may grow to this many points; QA reports any residual need.
MAX_ROW_HEIGHT = 150.0

# --------------------------------------------------------------------------- #
# styles
# --------------------------------------------------------------------------- #

THIN = Side(style="thin", color="B0B0B0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

TITLE_FONT = Font(bold=True, size=14, color="1F3864")
SECTION_FONT = Font(bold=True, size=11, color="1F3864")
MACHINE_HEADER_FILL = PatternFill("solid", fgColor="1F3864")
MACHINE_HEADER_FONT = Font(bold=True, color="FFFFFF")
MANUAL_HEADER_FILL = PatternFill("solid", fgColor="7F6000")
MANUAL_HEADER_FONT = Font(bold=True, color="FFFFFF")
MANUAL_FILL = PatternFill("solid", fgColor="FFF2CC")
MACHINE_FILL = PatternFill("solid", fgColor="F2F2F2")
BANNER_FILL = PatternFill("solid", fgColor="FCE4D6")
STATUS_FILLS = {
    "RESOLVED": PatternFill("solid", fgColor="E2EFDA"),
    "NEEDS_REVIEW": PatternFill("solid", fgColor="FFE699"),
    "NOT_FOUND": PatternFill("solid", fgColor="D9D9D9"),
}
MANDATORY_FONT = Font(bold=True, color="C00000")
WRAP = Alignment(wrap_text=True, vertical="top")
WRAP_CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")
TOP_LEFT = Alignment(vertical="top", horizontal="left")
TOP_RIGHT = Alignment(vertical="top", horizontal="right")


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clip(value: object, limit: int = 400) -> str:
    text = re.sub(r"\s*\n\s*", "\n", _text(value))
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _sheet_ref(title: str, column: str, first: int = 2, last: int = 999) -> str:
    """A quoted absolute reference to a column of a data sheet."""

    return f"'{title}'!${column}${first}:${column}${last}"


def _display_units(text: str) -> float:
    """Display width of ``text`` in Excel width units (CJK glyphs count twice)."""

    return sum(
        2.0 if unicodedata.east_asian_width(character) in ("W", "F") else 1.0
        for character in text
    )


def _row_height(values: Sequence[object], widths: Sequence[float] | None, minimum: float) -> float:
    """A row height that shows the wrapped text it has to hold.

    Word-wrapped workbook text is clipped by an explicit row height, so every
    row gets the height its content needs, bounded by ``MAX_ROW_HEIGHT``.  The
    bound is deliberate: the delivered sheet must stay printable, and a residual
    that still needs more lines is reported by the workbook QA instead of being
    hidden.
    """

    lines = 1.0
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value:
            continue
        width = 8.43
        if widths is not None and index < len(widths):
            width = widths[index] or 8.43
        per_line = max(6.0, width * 0.95)
        needed = 0.0
        for segment in value.split("\n"):
            needed += max(1.0, math.ceil(_display_units(segment) / per_line))
        lines = max(lines, needed)
    return min(MAX_ROW_HEIGHT, max(minimum, lines * 14.5))


class _Table:
    """Writes one header row plus data rows with a consistent workpaper style."""

    def __init__(
        self,
        worksheet,
        row: int,
        headers: Sequence[str],
        *,
        widths: Sequence[float] | None = None,
        manual_from: int | None = None,
    ) -> None:
        self.ws = worksheet
        self.header_row = row
        self.headers = list(headers)
        self.widths = list(widths) if widths is not None else None
        self.manual_from = manual_from
        for index, header in enumerate(self.headers, start=1):
            cell = worksheet.cell(row=row, column=index, value=header)
            manual = manual_from is not None and index >= manual_from
            cell.fill = MANUAL_HEADER_FILL if manual else MACHINE_HEADER_FILL
            cell.font = MANUAL_HEADER_FONT if manual else MACHINE_HEADER_FONT
            cell.alignment = WRAP_CENTER
            cell.border = BOX
            if widths is not None and index <= len(widths):
                worksheet.column_dimensions[get_column_letter(index)].width = widths[index - 1]
        self.row = row + 1
        self.first_data_row = row + 1

    def add(self, *values, height: float | None = None, number_formats: dict | None = None):
        for index, value in enumerate(values, start=1):
            cell = self.ws.cell(row=self.row, column=index, value=value)
            cell.border = BOX
            cell.alignment = WRAP
            if self.manual_from is not None and index >= self.manual_from:
                cell.fill = MANUAL_FILL
            if number_formats and index in number_formats:
                cell.number_format = number_formats[index]
        self.ws.row_dimensions[self.row].height = _row_height(
            values, self.widths, height or 18.0
        )
        self.row += 1
        return self.row - 1

    @property
    def last_data_row(self) -> int:
        return self.row - 1

    def finish(self, *, freeze: str | None = None, autofilter: bool = True) -> None:
        last_column = get_column_letter(len(self.headers))
        if autofilter and self.last_data_row >= self.first_data_row:
            self.ws.auto_filter.ref = (
                f"A{self.header_row}:{last_column}{max(self.last_data_row, self.first_data_row)}"
            )
        if freeze:
            self.ws.freeze_panes = freeze


def _manual_validation(worksheet, column: str, first: int, last: int) -> None:
    """Attach the review-conclusion dropdown and the pending-state format."""

    validation = DataValidation(
        type="list",
        formula1='"' + ",".join(MANUAL_OPTIONS) + '"',
        allow_blank=False,
        showDropDown=False,
        errorTitle="复核结论",
        error="请从下拉列表中选择复核结论。",
        promptTitle="人工复核",
        prompt="未复核 / 通过 / 有疑问 / 需修改 / 不适用",
        showErrorMessage=True,
        showInputMessage=True,
    )
    validation.errorStyle = "stop"
    worksheet.add_data_validation(validation)
    reference = f"{column}{first}:{column}{last}"
    validation.add(reference)
    worksheet.conditional_formatting.add(
        reference,
        CellIsRule(
            operator="equal",
            formula=['"未复核"'],
            fill=PatternFill("solid", fgColor="FFF2CC"),
            font=Font(color="7F6000"),
        ),
    )
    worksheet.conditional_formatting.add(
        reference,
        CellIsRule(
            operator="equal",
            formula=['"通过"'],
            fill=PatternFill("solid", fgColor="C6EFCE"),
            font=Font(color="006100"),
        ),
    )
    for outcome in ("有疑问", "需修改"):
        worksheet.conditional_formatting.add(
            reference,
            CellIsRule(
                operator="equal",
                formula=[f'"{outcome}"'],
                fill=PatternFill("solid", fgColor="FFC7CE"),
                font=Font(color="9C0006"),
            ),
        )


def _machine_status_format(worksheet, column: str, first: int, last: int) -> None:
    reference = f"{column}{first}:{column}{last}"
    for status, fill in STATUS_FILLS.items():
        worksheet.conditional_formatting.add(
            reference,
            CellIsRule(operator="equal", formula=[f'"{status}"'], fill=fill),
        )
    worksheet.conditional_formatting.add(
        reference,
        CellIsRule(
            operator="equal",
            formula=['"一票否决"'],
            fill=PatternFill("solid", fgColor="FFC7CE"),
            font=MANDATORY_FONT,
        ),
    )
    worksheet.conditional_formatting.add(
        reference,
        CellIsRule(
            operator="equal",
            formula=['"★"'],
            fill=PatternFill("solid", fgColor="FFC7CE"),
            font=MANDATORY_FONT,
        ),
    )


def _setup_page(worksheet, *, fit_width: int = 1, landscape: bool = True) -> None:
    worksheet.page_setup.orientation = "landscape" if landscape else "portrait"
    worksheet.page_setup.fitToWidth = fit_width
    worksheet.page_setup.fitToHeight = 0
    if worksheet.sheet_properties.pageSetUpPr is None:
        from openpyxl.worksheet.properties import PageSetupProperties

        worksheet.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    else:
        worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.print_title_rows = "1:1"


# --------------------------------------------------------------------------- #
# projections
# --------------------------------------------------------------------------- #


def _locator_text(locator: object) -> str:
    if locator is None:
        return ""
    if isinstance(locator, str):
        return locator
    if isinstance(locator, dict):
        data = locator
    else:
        data = locator.model_dump(mode="json")
    if "page" in data:
        return f"第{data['page']}页"
    if data.get("locator_type") == "docx_paragraph":
        return f"DOCX第{data['paragraph_index']}段"
    if data.get("locator_type") == "docx_table_cell":
        return f"DOCX表{data['table_index']}行{data['row_index']}列{data['cell_index']}"
    return "源文档"


def _locator_page(locator: object) -> object:
    if locator is None:
        return None
    data = locator if isinstance(locator, dict) else locator.model_dump(mode="json")
    return data.get("page")


def _locator_kind(locator: object) -> str:
    if locator is None:
        return ""
    data = locator if isinstance(locator, dict) else locator.model_dump(mode="json")
    return str(data.get("locator_type") or "")


def _status_of(field_record: dict) -> str:
    return str(field_record.get("status") or "NOT_FOUND")


def _field_rows(project_facts) -> list[dict]:
    """One projection row per fact field, straight from ``ProjectFacts``."""

    fields = project_facts.fields.model_dump(mode="json")
    rows = []
    for key, label, category in FACT_FIELDS:
        record = fields.get(key) or {}
        candidates = record.get("candidates") or []
        best = candidates[0] if candidates else {}
        rows.append(
            {
                "category": category,
                "key": key,
                "label": label,
                "value": record.get("resolved_value"),
                "status": _status_of(record),
                "page": _locator_page(best.get("locator")),
                "section": best.get("section") or "",
                "locator": _locator_text(best.get("locator")),
                "locator_kind": _locator_kind(best.get("locator")),
                "excerpt": _clip(best.get("evidence_text"), 300),
                "method": best.get("method") or "",
                "confidence": record.get("confidence"),
                "reason": record.get("resolution_reason") or "",
                "candidate_count": len(candidates),
                "alternative_values": [
                    _clip(item.get("normalized_value") or item.get("value"), 120)
                    for item in candidates[1:3]
                ],
            }
        )
    return rows


def _requirement_rows(dynamic_plan) -> list[dict]:
    rows = []
    for item in getattr(dynamic_plan, "items", ()) or ():
        rows.append(
            {
                "id": item.item_id,
                "module": item.module,
                "submodule": item.submodule,
                "topic": item.topic,
                "type": item.requirement_type,
                "risk": item.risk_level,
                "requirement": item.source_requirement,
                "action": item.verification_action,
                "criteria": item.pass_criteria,
                "consequence": item.consequence_if_failed,
                "locator": item.source_locator,
                "page": item.source_page,
                "section": item.source_section,
                "evidence": _clip(item.source_evidence, 300),
                "requirement_ids": list(item.source_requirement_ids),
                "fact": item.related_project_fact,
                "fact_value": item.related_fact_value,
                "status": item.status,
                "applicable": item.applicable,
                "values": list(item.values),
            }
        )
    return rows


def _is_mandatory(row: dict) -> bool:
    return row["type"] in MANDATORY_TYPES or row["risk"] in MANDATORY_RISK_LEVELS


def _is_clause(row: dict) -> bool:
    return row["type"] in CLAUSE_TYPES


_PRICE_HEADER_TOKENS = {
    "index": ("序号",),
    "name": ("内容", "名称", "项目", "设备", "货物", "品目", "标的"),
    "spec": ("规格", "型号", "参数", "技术"),
    "unit": ("单位",),
    "quantity": ("数量",),
    "unit_price": ("单价",),
    "amount": ("小计", "合价", "金额", "分项限价", "限价"),
}


def _row_values(row: object) -> list[str]:
    """Cell texts of one table row, for dict or model shaped rows alike."""

    if isinstance(row, dict):
        cells = row.get("cells")
    else:
        cells = getattr(row, "cells", row)
    values: list[str] = []
    for cell in cells or ():
        if isinstance(cell, dict):
            values.append(_text(cell.get("text")))
        else:
            values.append(_text(getattr(cell, "text", "")))
    return values


def _norm(value: object) -> str:
    """Whitespace-insensitive form: source headers wrap inside a single cell."""

    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", _text(value)))


def _looks_like_index(value: object) -> bool:
    """A first cell that reads as a bare row index (``1``, ``12``, ``三``)."""

    normalized = _norm(value)
    if not normalized or len(normalized) > 4:
        return False
    return bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?|[一二三四五六七八九十]+", normalized))


def _header_index(rows: Sequence[Sequence[str]]) -> int | None:
    """The row that names an index, an item and a price column."""

    for index, values in enumerate(rows[:3]):
        if not values:
            continue
        joined = _norm(" ".join(values))
        has_index = any(token in joined for token in _PRICE_HEADER_TOKENS["index"])
        has_name = any(token in joined for token in _PRICE_HEADER_TOKENS["name"])
        has_price = any(
            token in joined
            for token in _PRICE_HEADER_TOKENS["unit_price"] + _PRICE_HEADER_TOKENS["amount"]
        )
        if has_index and has_name and has_price:
            return index
    return None


def _columns_of(header: Sequence[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for key, tokens in _PRICE_HEADER_TOKENS.items():
        for position, value in enumerate(header):
            if any(token in _norm(value) for token in tokens):
                columns.setdefault(key, position)
                break
    return columns


def _price_table_rows(document) -> dict:
    """Source tables that are itemized price / limit tables.

    The detector is structural: a header row that names an index column, an item
    column and a price column.  Nothing is matched on a case-specific table,
    page or literal, and no price is computed - every number shown is the
    source's own cell text.

    Two source shapes have to survive generalization:

    * a table that continues on the next page without repeating its header is
      read with the previous header of the same shape, so a 32-line limit list
      split over two pages stays 32 reviewable lines;
    * a table whose rows are still empty is a *blank quotation form* the bidder
      must fill.  It is reported as a form, with its column names, instead of
      being silently dropped or invented into item rows.
    """

    items: list[dict] = []
    blank_forms: list[dict] = []
    carried: tuple | None = None
    for table in getattr(document, "tables", ()) or ():
        raw_rows = [_row_values(row) for row in (getattr(table, "rows", ()) or ())]
        rows = [values for values in raw_rows if any(_norm(value) for value in values)]
        if not rows:
            continue
        page = getattr(table, "page", None)
        table_index = getattr(table, "table_index", None)
        header_index = _header_index(rows)
        columns: dict[str, int]
        if header_index is not None:
            header = rows[header_index]
            columns = _columns_of(header)
            carried = (page, max(len(values) for values in rows), columns, header)
            data_rows = rows[header_index + 1 :]
        elif carried is not None:
            previous_page, width, previous_columns, header = carried
            here = max(len(values) for values in rows)
            if (
                previous_page is not None
                and page is not None
                and 0 <= page - previous_page <= 1
                and abs(here - width) <= 1
                and _looks_like_index(rows[0][0] if rows[0] else "")
            ):
                columns = previous_columns
                data_rows = rows
            else:
                continue
        else:
            continue

        named: list[dict] = []
        for values in data_rows:
            def take(key: str, values=values) -> str:
                position = columns.get(key)
                if position is None or position >= len(values):
                    return ""
                return values[position]

            name = take("name")
            index_text = take("index")
            unit_price = take("unit_price")
            amount = take("amount")
            if not _norm(name) and not (_norm(unit_price) or _norm(amount)):
                continue
            named.append(
                {
                    "page": page,
                    "table_index": table_index,
                    "index": index_text,
                    "name": name,
                    "spec": take("spec"),
                    "unit": take("unit"),
                    "quantity": take("quantity"),
                    "unit_price": unit_price,
                    "amount": amount,
                }
            )
        if not named:
            blank_forms.append(
                {
                    "page": page,
                    "table_index": table_index,
                    "columns": " | ".join(_text(value) for value in header if _norm(value)),
                    "capacity": len(data_rows),
                }
            )
            continue
        filled = any(_norm(item["unit_price"]) or _norm(item["amount"]) for item in named)
        for item in named:
            item["kind"] = (
                "源分项限价表（源文件已填写）" if filled else "源分项报价表（待供应商填写）"
            )
        items.extend(named)
    return {"items": items, "blank_forms": blank_forms}


_STRUCTURE_MARKERS = {
    "签字要求": ("签字", "签署", "法定代表人", "授权代表", "签名"),
    "盖章要求": ("盖章", "公章", "印章", "签章", "电子签章", "骑缝章"),
    "日期要求": ("日期", "年月日", "年 月 日", "填写日期"),
    "附件要求": ("附件", "附后", "复印件", "证明材料", "扫描件", "截图"),
}


def _structure_rows(format_template) -> list[dict]:
    """Source response-format structure, one row per source heading."""

    if format_template is None or not getattr(format_template, "elements", None):
        return []
    rows = []
    headings = [
        element
        for element in format_template.elements
        if element.type == "heading" and _text(element.text)
    ]
    for position, heading in enumerate(headings, start=1):
        # the section's own text is the heading plus everything until the next heading
        start = format_template.elements.index(heading)
        section = []
        for element in format_template.elements[start + 1 :]:
            if element.type == "heading" and _text(element.text):
                break
            if _text(element.text):
                section.append(_text(element.text))
        body = "\n".join(section)
        markers = {
            label: "是" if any(token in body for token in tokens) else ""
            for label, tokens in _STRUCTURE_MARKERS.items()
        }
        rows.append(
            {
                "index": position,
                "heading_level": heading.heading_level,
                "title": _clip(heading.text, 200),
                "locator": _locator_text(heading.locator),
                "page": _locator_page(heading.locator),
                "body_chars": len(body),
                **markers,
            }
        )
    return rows


def _evidence_key(item: dict) -> tuple:
    locator = item.get("locator") or {}
    if not isinstance(locator, dict):
        locator = locator.model_dump(mode="json")
    return (
        locator.get("page"),
        _text(item.get("section")),
        _text(locator.get("locator_type")),
        locator.get("block_index") or locator.get("row_index") or locator.get("paragraph_index"),
        _text(item.get("evidence_text"))[:80],
    )


def _evidence_rows(review_evidence: Iterable, fact_rows: Sequence[dict], requirement_rows: Sequence[dict]) -> list[dict]:
    """Deduplicated evidence index with the items that rely on each locator."""

    grouped: "OrderedDict[tuple, dict]" = OrderedDict()
    for index, item in enumerate(review_evidence or (), start=1):
        data = item if isinstance(item, dict) else item.model_dump(mode="json")
        key = _evidence_key(data)
        entry = grouped.get(key)
        if entry is None:
            locator = data.get("locator") or {}
            if not isinstance(locator, dict):
                locator = locator.model_dump(mode="json")
            entry = {
                "page": locator.get("page"),
                "section": _text(data.get("section")),
                "locator_type": _text(locator.get("locator_type")),
                "locator": _locator_text(locator),
                "excerpt": _clip(data.get("evidence_text"), 300),
                "intents": [],
                "review_items": [],
                "used_by_facts": [],
                "used_by_requirements": [],
            }
            grouped[key] = entry
        entry["review_items"].append(_text(data.get("review_item_id")))
        entry["intents"].append(_clip(data.get("review_intent"), 80))

    entries = list(grouped.values())
    for position, entry in enumerate(entries, start=1):
        entry["evidence_id"] = f"EV{position:03d}"
        page = entry["page"]
        excerpt = _text(entry["excerpt"])[:60]
        for fact in fact_rows:
            if fact["page"] == page and excerpt and excerpt[:30] in _text(fact["excerpt"]):
                entry["used_by_facts"].append(fact["key"])
        for requirement in requirement_rows:
            if requirement["page"] == page and (
                excerpt[:24] and excerpt[:24] in _text(requirement["evidence"])
            ):
                entry["used_by_requirements"].append(requirement["id"])
    return entries


def _exception_rows(fact_rows: Sequence[dict], requirement_rows: Sequence[dict]) -> list[dict]:
    """Only the rows a reviewer still has to act on."""

    rows = []
    for fact in fact_rows:
        if fact["status"] == "RESOLVED":
            if fact["locator"]:
                continue
            rows.append(
                {
                    "type": "证据缺失",
                    "key": fact["key"],
                    "description": f"{fact['label']} 已判定 RESOLVED，但没有证据定位",
                    "candidates": "",
                    "evidence": "",
                    "reason": "ProjectFacts 判定为已解析，但候选证据没有源定位",
                    "action": "人工在源文件中确认该值的依据并补记位置",
                }
            )
            continue
        detail = "；".join(fact["alternative_values"]) or fact["reason"]
        rows.append(
            {
                "type": "事实未定" if fact["status"] == "NEEDS_REVIEW" else "事实缺失",
                "key": fact["key"],
                "description": f"{fact['label']}：{fact['status']}",
                "candidates": detail,
                "evidence": fact["excerpt"],
                "reason": fact["reason"]
                or (
                    "存在多个可信候选，须人工裁决"
                    if fact["status"] == "NEEDS_REVIEW"
                    else "源文件未给出可靠值，自动化不得发明"
                ),
                "action": f"在源文件 {fact['locator'] or '相应章节'} 处人工确认后填写复核值",
            }
        )
    for requirement in requirement_rows:
        if requirement["applicable"] and not requirement["evidence"]:
            rows.append(
                {
                    "type": "强制项证据缺失",
                    "key": requirement["id"],
                    "description": f"{requirement['module']}／{requirement['topic']}",
                    "candidates": "",
                    "evidence": "",
                    "reason": "该强制项没有可定位的源证据",
                    "action": "人工在源文件中定位该要求并补记证据",
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# sheets
# --------------------------------------------------------------------------- #


def _build_overview(workbook, *, project_facts, build_meta, counts: dict) -> None:
    title = SHEET_TITLES[0]
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    ws["A1"] = "投标项目复核总览"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:F1")

    facts = project_facts.fields.model_dump(mode="json")
    digest = build_meta.get("project_facts_sha256") or ""
    source_digest = build_meta.get("source_pdf_sha256") or ""

    def value_of(key: str) -> str:
        record = facts.get(key) or {}
        value = record.get("resolved_value")
        status = _status_of(record)
        if value in (None, ""):
            return status
        return _clip(value, 120)

    block = [
        ("项目名称", value_of("project_name"), "项目编号", value_of("project_number")),
        ("招标编号", value_of("tender_number"), "采购人", value_of("purchaser")),
        ("标段/包件名称", value_of("lot_name"), "标段/包件编号", value_of("lot_number")),
        (
            "生成时间",
            build_meta.get("generated_at") or "",
            "case / build id",
            build_meta.get("build_id") or "",
        ),
        (
            "ProjectFacts 摘要",
            f"共 {counts['facts_total']} 项；RESOLVED {counts['resolved']}；"
            f"NEEDS_REVIEW {counts['needs_review']}；NOT_FOUND {counts['not_found']}",
            "source digest",
            f"sha256 {source_digest[:16]}…" if source_digest else "未记录",
        ),
        (
            "ProjectFacts digest",
            f"sha256 {digest[:16]}…" if digest else "未记录",
            "工作簿",
            str(build_meta.get("workbook_name") or "投标项目复核表.xlsx"),
        ),
    ]
    row = 3
    for left_label, left_value, right_label, right_value in block:
        ws.cell(row=row, column=1, value=left_label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=left_value).alignment = WRAP
        ws.cell(row=row, column=4, value=right_label).font = Font(bold=True)
        ws.cell(row=row, column=5, value=right_value).alignment = WRAP
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
        ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=6)
        ws.row_dimensions[row].height = _row_height(
            [left_label, left_value, "", right_label, right_value],
            (22, 48, 18, 22, 44, 18),
            20.0,
        )
        row += 1

    row += 1
    ws.cell(row=row, column=1, value=BANNER).fill = BANNER_FILL
    ws.cell(row=row, column=1).font = Font(bold=True, color="833C00")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    row += 2

    def section(label: str) -> int:
        nonlocal row
        ws.cell(row=row, column=1, value=label).font = SECTION_FONT
        ws.cell(row=row, column=2, value="公式统计").font = Font(italic=True, color="808080")
        row += 1
        return row

    row = section("机器事实状态（公式引用 01_项目事实）")
    fact_sheet = SHEET_TITLES[1]
    machine = [
        ("RESOLVED", f'=COUNTIF({_sheet_ref(fact_sheet, "E")},"RESOLVED")'),
        ("NEEDS_REVIEW", f'=COUNTIF({_sheet_ref(fact_sheet, "E")},"NEEDS_REVIEW")'),
        ("NOT_FOUND", f'=COUNTIF({_sheet_ref(fact_sheet, "E")},"NOT_FOUND")'),
        ("事实条目合计", f'=COUNTA({_sheet_ref(fact_sheet, "B")})'),
    ]
    for label, formula in machine:
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=formula)
        row += 1
    row += 1

    row = section("复核域行数（公式引用各复核视图）")
    domain_specs = [
        ("关键条款", SHEET_TITLES[2], "B"),
        ("资格否决与强制项", SHEET_TITLES[3], "B"),
        ("★/一票否决强制项", SHEET_TITLES[3], "H"),
        ("报价/限价行", SHEET_TITLES[4], "C"),
        ("文件结构与签章", SHEET_TITLES[5], "C"),
        ("冲突与缺失", SHEET_TITLES[6], "B"),
        ("证据条目", SHEET_TITLES[7], "A"),
    ]
    for label, sheet, column in domain_specs:
        if column == "H":
            formula = f'=COUNTIF({_sheet_ref(sheet, "H")},"★")'
        else:
            formula = f'=COUNTA({_sheet_ref(sheet, column)})'
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=formula)
        row += 1
    row += 1

    row = section("人工复核（公式引用人工结论列）")
    manual_columns = [
        (SHEET_TITLES[1], "M"),
        (SHEET_TITLES[2], "M"),
        (SHEET_TITLES[3], "O"),
        (SHEET_TITLES[4], "I"),
        (SHEET_TITLES[4], "L"),
        (SHEET_TITLES[5], "M"),
        (SHEET_TITLES[6], "H"),
    ]
    for label, outcome in (
        ("未复核", DEFAULT_MANUAL),
        ("已通过", "通过"),
        ("有疑问", "有疑问"),
        ("需修改", "需修改"),
        ("不适用", "不适用"),
    ):
        formula = "=" + "+".join(
            f'COUNTIF({_sheet_ref(sheet, column)},"{outcome}")' for sheet, column in manual_columns
        )
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=formula)
        row += 1
    total_formula = "=" + "+".join(
        f'COUNTA({_sheet_ref(sheet, column)})' for sheet, column in manual_columns
    )
    total_row = row
    ws.cell(row=row, column=1, value="人工复核条目合计")
    ws.cell(row=row, column=2, value=total_formula)
    row += 1
    pending_row = row
    ws.cell(row=row, column=1, value="剩余待复核（未复核）")
    ws.cell(
        row=row,
        column=2,
        value="=" + "+".join(
            f'COUNTIF({_sheet_ref(sheet, column)},"{DEFAULT_MANUAL}")'
            for sheet, column in manual_columns
        ),
    )
    row += 2

    row = section("当前状态")
    states = [
        ("AUTOMATED_CHECKS", "PASS（见 build 的 qa_report.json 与门禁报告）"),
        (
            "MANUAL_REVIEW",
            f'=IF(B{total_row}=0,"未开始",IF(B{pending_row}=0,"已完成","进行中"))',
        ),
        ("提交就绪判定", "否（由人工批准流程决定，自动化永不推断）"),
        ("生产候选版本", "否"),
    ]
    for label, value in states:
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row, column=2, value=value)
        row += 1

    for column, width in zip("ABCDEF", (22, 26, 18, 22, 26, 18)):
        ws.column_dimensions[column].width = width
    ws.freeze_panes = "A3"
    _setup_page(ws, landscape=False)


def _build_facts(workbook, project_facts) -> dict:
    title = SHEET_TITLES[1]
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    headers = [
        "分类",
        "fact_key",
        "复核项",
        "机器抽取值",
        "事实状态",
        "源文件页码",
        "源章节/表格",
        "证据定位",
        "证据摘要",
        "来源类型",
        "置信度",
        "候选数",
        MANUAL_CONCLUSION,
        MANUAL_VALUE,
        MANUAL_NOTE,
    ]
    table = _Table(
        ws,
        1,
        headers,
        widths=(12, 20, 16, 34, 13, 10, 18, 16, 46, 16, 8, 8, 12, 20, 22),
        manual_from=13,
    )
    rows = _field_rows(project_facts)
    for fact in rows:
        value = fact["value"]
        if value in (None, "") or fact["status"] == "NOT_FOUND":
            value_text = "NOT_FOUND" if fact["status"] == "NOT_FOUND" else ""
        else:
            value_text = _clip(value, 200)
        table.add(
            fact["category"],
            fact["key"],
            fact["label"],
            value_text,
            fact["status"],
            fact["page"] if fact["page"] is not None else "",
            fact["section"],
            fact["locator"],
            fact["excerpt"],
            f"{fact['method']} / {fact['locator_kind']}".strip(" /"),
            fact["confidence"] if fact["confidence"] is not None else "",
            fact["candidate_count"],
            DEFAULT_MANUAL,
            "",
            "",
            height=30,
        )
    table.finish(freeze="D2")
    _manual_validation(ws, "M", table.first_data_row, table.last_data_row)
    _manual_validation(ws, "N", table.first_data_row, table.last_data_row)
    _machine_status_format(ws, "E", table.first_data_row, table.last_data_row)
    _setup_page(ws)
    return {"rows": len(rows)}


def _build_clauses(workbook, requirement_rows: Sequence[dict]) -> dict:
    title = SHEET_TITLES[2]
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    headers = [
        "类别",
        "requirement_id",
        "条款",
        "抽取结果",
        "复核动作",
        "核验标准",
        "是否强制",
        "风险级别",
        "源页码",
        "源章节",
        "证据定位",
        "证据摘要",
        "人工复核结论",
        "人工备注",
    ]
    table = _Table(
        ws,
        1,
        headers,
        widths=(18, 12, 20, 44, 34, 30, 9, 10, 8, 16, 20, 40, 13, 20),
        manual_from=13,
    )
    rows = [row for row in requirement_rows if _is_clause(row)]
    for row in rows:
        table.add(
            row["module"],
            row["id"],
            row["topic"],
            _clip(row["requirement"], 400),
            _clip(row["action"], 300),
            _clip(row["criteria"], 240),
            "是" if _is_mandatory(row) else "",
            row["risk"],
            row["page"] if row["page"] is not None else "",
            row["section"],
            row["locator"],
            row["evidence"],
            DEFAULT_MANUAL,
            "",
            height=42,
        )
    table.finish(freeze="C2")
    _manual_validation(ws, "M", table.first_data_row, table.last_data_row)
    _machine_status_format(ws, "H", table.first_data_row, table.last_data_row)
    _setup_page(ws)
    return {"rows": len(rows)}


def _build_mandatory(workbook, requirement_rows: Sequence[dict]) -> dict:
    title = SHEET_TITLES[3]
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    headers = [
        "序号",
        "requirement_id",
        "类别",
        "子类",
        "要求正文",
        "复核动作",
        "核验标准",
        "★",
        "否决性",
        "强制性类型",
        "证据页码",
        "证据定位",
        "证据摘要",
        "机器识别状态",
        "人工满足情况",
        "人工证据/材料",
        "人工备注",
    ]
    table = _Table(
        ws,
        1,
        headers,
        widths=(6, 13, 18, 12, 46, 30, 26, 6, 9, 15, 9, 20, 36, 12, 13, 20, 20),
        manual_from=15,
    )
    rows = [row for row in requirement_rows if _is_mandatory(row)]
    for position, row in enumerate(rows, start=1):
        veto = "是" if (row["type"] == "REJECTION" or row["risk"] == "一票否决") else ""
        table.add(
            position,
            row["id"],
            row["module"],
            row["submodule"],
            _clip(row["requirement"], 500),
            _clip(row["action"], 260),
            _clip(row["criteria"], 220),
            "★" if veto else "",
            veto,
            row["type"],
            row["page"] if row["page"] is not None else "",
            row["locator"],
            row["evidence"],
            row["status"],
            DEFAULT_MANUAL,
            "",
            "",
            height=44,
        )
    table.finish(freeze="E2")
    _manual_validation(ws, "O", table.first_data_row, table.last_data_row)
    _manual_validation(ws, "P", table.first_data_row, table.last_data_row)
    _machine_status_format(ws, "H", table.first_data_row, table.last_data_row)
    _machine_status_format(ws, "I", table.first_data_row, table.last_data_row)
    _setup_page(ws)
    return {"rows": len(rows)}


def _number(value: str):
    """A price/number cell keeps the source's number, or stays text as typed."""

    text = _text(value).replace(",", "").replace("，", "")
    if not text:
        return ""
    match = re.fullmatch(r"-?\d+(?:\.\d+)?", text)
    if match:
        number = float(text)
        return int(number) if number.is_integer() and "." not in text else number
    return value


def _build_pricing(workbook, *, project_facts, document, build_meta) -> dict:
    title = SHEET_TITLES[4]
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    ws["A1"] = "报价与限价复核"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:J1")

    facts = {row["key"]: row for row in _field_rows(project_facts)}
    row = 3
    ws.cell(row=row, column=1, value="一、限价与预算（ProjectFacts，二者语义独立）").font = SECTION_FONT
    row += 1
    limit_headers = [
        "项目",
        "fact_key",
        "值",
        "事实状态",
        "源页码",
        "证据定位",
        "证据摘要",
        "限价类型（源）",
        MANUAL_CONCLUSION,
        MANUAL_NOTE,
    ]
    limit_table = _Table(
        ws,
        row,
        limit_headers,
        widths=(18, 14, 18, 12, 8, 18, 40, 26, 13, 20),
        manual_from=9,
    )
    limit_keys = ("budget", "max_price", "bid_bond_amount")
    for key in limit_keys:
        fact = facts.get(key) or {}
        value = fact.get("value")
        source_type = ""
        if key == "budget":
            source_type = "预算金额（不得与最高限价合并）"
        elif key == "max_price":
            source_type = "最高限价/控制价"
        elif key == "bid_bond_amount":
            source_type = "投标保证金"
        limit_table.add(
            fact.get("label", key),
            key,
            _number(value) if value not in (None, "") else ("NOT_FOUND" if fact.get("status") == "NOT_FOUND" else ""),
            fact.get("status", ""),
            fact.get("page") if fact.get("page") is not None else "",
            fact.get("locator", ""),
            fact.get("excerpt", ""),
            source_type,
            DEFAULT_MANUAL,
            "",
            height=30,
            number_formats={3: "#,##0.00"},
        )
    _manual_validation(ws, "I", limit_table.first_data_row, limit_table.last_data_row)
    _machine_status_format(ws, "D", limit_table.first_data_row, limit_table.last_data_row)
    row = limit_table.row + 1

    ws.cell(row=row, column=1, value="二、源分项价格／限价表（逐行来自源表格）").font = SECTION_FONT
    row += 1
    price_result = _price_table_rows(document)
    price_rows = price_result["items"]
    blank_forms = price_result["blank_forms"]
    price_headers = [
        "源页码",
        "源表序号",
        "序号",
        "项目/内容",
        "规格",
        "单位",
        "数量",
        "单价（元）",
        "小计/限价（元）",
        "源表类型",
        "源证据",
        MANUAL_CONCLUSION,
        MANUAL_NOTE,
    ]
    price_table = _Table(
        ws,
        row,
        price_headers,
        widths=(8, 10, 6, 30, 20, 6, 8, 14, 16, 26, 24, 13, 20),
        manual_from=12,
    )
    for item in price_rows:
        price_table.add(
            item["page"] if item["page"] is not None else "",
            item["table_index"] if item["table_index"] is not None else "",
            _number(item["index"]),
            _clip(item["name"], 200),
            _clip(item["spec"], 120),
            item["unit"],
            _number(item["quantity"]),
            _number(item["unit_price"]),
            _number(item["amount"]),
            item.get("kind", ""),
            f"源表 第{item['page']}页/{item['table_index']}",
            DEFAULT_MANUAL,
            "",
            height=26,
            number_formats={7: "#,##0.###", 8: "#,##0.00", 9: "#,##0.00"},
        )
    if not price_rows:
        price_table.add(
            "",
            "",
            "（本案例源文件没有分项价格表）",
            *([""] * (len(price_headers) - 3)),
        )
    _manual_validation(ws, "L", price_table.first_data_row, price_table.last_data_row)
    price_table.finish(freeze="D2", autofilter=False)
    row = price_table.row + 1

    if blank_forms:
        ws.cell(
            row=row,
            column=1,
            value="三、源空白报价表单（源文件要求填写、当前空白，需供应商报价）",
        ).font = SECTION_FONT
        row += 1
        form_headers = ["源页码", "源表序号", "源表列名", "空白行数", "说明", MANUAL_CONCLUSION, MANUAL_NOTE]
        form_table = _Table(
            ws,
            row,
            form_headers,
            widths=(8, 10, 60, 9, 34, 13, 20),
            manual_from=6,
        )
        for form in blank_forms:
            form_table.add(
                form["page"] if form["page"] is not None else "",
                form["table_index"] if form["table_index"] is not None else "",
                _clip(form["columns"], 300),
                form["capacity"],
                "源文件给出空白报价表，无任何单价/合价数据；工作簿不填写、不推测",
                DEFAULT_MANUAL,
                "",
                height=26,
            )
        _manual_validation(ws, "F", form_table.first_data_row, form_table.last_data_row)
        row = form_table.row + 1

    ws.cell(row=row, column=1, value=(
        "说明：单价、小计、限价均为源文件自身的单元格内容，工作簿不计算、不换算、不合并任何价格；"
        "预算与最高限价保持相互独立的两行。"
    )).font = Font(italic=True, color="808080")
    _setup_page(ws)
    return {
        "limits": len(limit_keys),
        "items": len(price_rows),
        "blank_forms": len(blank_forms),
    }


def _build_structure(workbook, *, format_template, workbook_path) -> dict:
    title = SHEET_TITLES[5]
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    headers = [
        "序号",
        "源结构层级",
        "文件/章节/表单",
        "是否要求",
        "签字要求",
        "盖章要求",
        "日期要求",
        "附件要求",
        "源页码",
        "证据定位",
        "机器状态",
        "生成文档是否存在",
        MANUAL_CONCLUSION,
        MANUAL_NOTE,
    ]
    table = _Table(
        ws,
        1,
        headers,
        widths=(6, 10, 34, 9, 10, 10, 10, 12, 8, 18, 16, 16, 13, 20),
        manual_from=13,
    )
    rows = _structure_rows(format_template)
    document_path = Path(workbook_path).with_name("基础投标文件.docx")
    generated = "是" if document_path.is_file() else "构建中"
    for row in rows:
        table.add(
            row["index"],
            row["heading_level"] or "",
            row["title"],
            "是",
            row["签字要求"],
            row["盖章要求"],
            row["日期要求"],
            row["附件要求"],
            row["page"] if row["page"] is not None else "",
            row["locator"],
            "源结构已解析",
            generated,
            DEFAULT_MANUAL,
            "",
            height=30,
        )
    if not rows:
        table.add("", "", "（源文件未解析出可用的响应文件格式章节）", *([""] * (len(headers) - 3)))
    table.finish(freeze="C2")
    _manual_validation(ws, "M", table.first_data_row, table.last_data_row)
    _setup_page(ws)
    return {"rows": len(rows)}


def _build_exceptions(workbook, exception_rows: Sequence[dict]) -> dict:
    title = SHEET_TITLES[6]
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    headers = [
        "类型",
        "key/id",
        "说明",
        "候选值/冲突",
        "源证据",
        "原因",
        "建议人工动作",
        MANUAL_CONCLUSION,
        MANUAL_NOTE,
    ]
    table = _Table(
        ws,
        1,
        headers,
        widths=(14, 16, 40, 30, 40, 40, 40, 13, 20),
        manual_from=8,
    )
    for row in exception_rows:
        table.add(
            row["type"],
            row["key"],
            row["description"],
            row["candidates"],
            row["evidence"],
            row["reason"],
            row["action"],
            DEFAULT_MANUAL,
            "",
            height=40,
        )
    if not exception_rows:
        table.add("无", "", "没有未决的事实或强制项", "", "", "", "", DEFAULT_MANUAL, "")
    table.finish(freeze="C2")
    _manual_validation(ws, "H", table.first_data_row, table.last_data_row)
    _setup_page(ws)
    return {"rows": len(exception_rows)}


def _build_evidence_index(workbook, evidence_rows: Sequence[dict]) -> dict:
    title = SHEET_TITLES[7]
    if title in workbook.sheetnames:
        del workbook[title]
    ws = workbook.create_sheet(title)
    headers = [
        "evidence_id",
        "源文件",
        "源页码",
        "源章节",
        "定位类型",
        "定位",
        "摘要",
        "用于事实",
        "用于强制项",
        "复核意图",
    ]
    table = _Table(
        ws,
        1,
        headers,
        widths=(12, 28, 8, 20, 16, 18, 52, 22, 22, 30),
    )
    for row in evidence_rows:
        table.add(
            row["evidence_id"],
            row.get("source_file", ""),
            row["page"] if row["page"] is not None else "",
            row["section"],
            row["locator_type"],
            row["locator"],
            row["excerpt"],
            ", ".join(dict.fromkeys(row["used_by_facts"]))[:200],
            ", ".join(dict.fromkeys(row["used_by_requirements"]))[:200],
            " / ".join(dict.fromkeys(item for item in row["intents"] if item))[:200],
            height=32,
        )
    table.finish(freeze="C2")
    _setup_page(ws)
    return {"rows": len(evidence_rows)}


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def build_review_views(
    workbook,
    *,
    project_facts,
    dynamic_plan=None,
    normalized_document=None,
    format_template=None,
    review_evidence=(),
    build_meta: dict | None = None,
    workbook_path: str | Path | None = None,
) -> dict:
    """Append the review views to ``workbook`` and return their row counts.

    The caller saves the workbook; nothing here writes a file, and nothing here
    changes a machine value: every machine cell is a projection of an authority
    object, and every manual cell is an input for a human reviewer.
    """

    build_meta = dict(build_meta or {})
    if workbook_path is not None:
        build_meta.setdefault("workbook_name", Path(workbook_path).name)
    requirement_rows = _requirement_rows(dynamic_plan)
    fact_rows = _field_rows(project_facts)
    counts = {
        "facts_total": len(fact_rows),
        "resolved": sum(1 for row in fact_rows if row["status"] == "RESOLVED"),
        "needs_review": sum(1 for row in fact_rows if row["status"] == "NEEDS_REVIEW"),
        "not_found": sum(1 for row in fact_rows if row["status"] == "NOT_FOUND"),
    }
    evidence_rows = _evidence_rows(review_evidence, fact_rows, requirement_rows)
    source_file = _text(build_meta.get("source_file"))
    for row in evidence_rows:
        row["source_file"] = source_file
    exception_rows = _exception_rows(fact_rows, requirement_rows)

    summary = {
        "sheets": [],
        "fact_status_counts": counts,
    }
    _build_overview(
        workbook,
        project_facts=project_facts,
        build_meta=build_meta,
        counts=counts,
    )
    summary["sheets"].append({"title": SHEET_TITLES[0], "kind": "dashboard"})

    result = _build_facts(workbook, project_facts)
    summary["sheets"].append({"title": SHEET_TITLES[1], **result})
    result = _build_clauses(workbook, requirement_rows)
    summary["sheets"].append({"title": SHEET_TITLES[2], **result})
    result = _build_mandatory(workbook, requirement_rows)
    summary["sheets"].append({"title": SHEET_TITLES[3], **result})
    result = _build_pricing(
        workbook,
        project_facts=project_facts,
        document=normalized_document,
        build_meta=build_meta,
    )
    summary["sheets"].append({"title": SHEET_TITLES[4], **result})
    result = _build_structure(
        workbook, format_template=format_template, workbook_path=workbook_path or ""
    )
    summary["sheets"].append({"title": SHEET_TITLES[5], **result})
    result = _build_exceptions(workbook, exception_rows)
    summary["sheets"].append({"title": SHEET_TITLES[6], **result})
    result = _build_evidence_index(workbook, evidence_rows)
    summary["sheets"].append({"title": SHEET_TITLES[7], **result})

    summary["requirement_rows"] = len(requirement_rows)
    summary["mandatory_rows"] = sum(1 for row in requirement_rows if _is_mandatory(row))
    summary["clause_rows"] = sum(1 for row in requirement_rows if _is_clause(row))
    summary["evidence_rows"] = len(evidence_rows)
    summary["exception_rows"] = len(exception_rows)
    summary["manual_columns"] = [
        ("01_项目事实", "M"),
        ("02_关键条款", "M"),
        ("03_资格否决与强制项", "O"),
        ("04_报价与限价", "I"),
        ("04_报价与限价", "L"),
        ("05_文件结构与签章", "M"),
        ("06_冲突与缺失", "H"),
    ]
    return summary


def augment_review_workbook(
    path: str | Path,
    *,
    project_facts,
    dynamic_plan=None,
    normalized_document=None,
    format_template=None,
    review_evidence=(),
    build_meta: dict | None = None,
) -> dict:
    """Append the review views to an existing workbook file, in place.

    Used when the workbook is being regenerated over an *accepted* build: the
    delivered sheet keeps its exact values and layout, and only the reviewer
    views are added.  No machine value of the existing sheet is read, rewritten
    or re-derived.
    """

    from openpyxl import load_workbook

    workbook_path = Path(path)
    workbook = load_workbook(workbook_path, data_only=False, read_only=False)
    try:
        summary = build_review_views(
            workbook,
            project_facts=project_facts,
            dynamic_plan=dynamic_plan,
            normalized_document=normalized_document,
            format_template=format_template,
            review_evidence=review_evidence,
            build_meta=build_meta,
            workbook_path=workbook_path,
        )
        workbook.save(workbook_path)
    finally:
        workbook.close()
    return summary
