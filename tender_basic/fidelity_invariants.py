"""Round-8 invariants: delivered-text fidelity, conditional scoring, cross-sheet risk.

The human's round-7 manual review examined the actual CASE001 workbook and failed
it: the delivered *text* was still wrong in ways a provenance check cannot see.
These are audit checks, not production decisions.  They read the delivered
workbook cells (and the source document behind them) and report whether the
round-8 promises hold:

* **polarity** -- an operative clause keeps its negative wording ("供应商不按本章
  第3.4.1项要求提交响应保证金的…"), so a rejection clause cannot read as its own
  opposite;
* **conditional scoring** -- a scoring factor's tiers are alternatives, a factor's
  maximum is not a formula's base score, and the bidder is never asked to claim
  every tier at once;
* **blank placeholders** -- a source blank stays a blank;
* **complete fragments** -- a rendered enumeration is not cut in half, and no
  duplicated wording or foreign heading survives;
* **cross-sheet risk** -- the delivered 风险级别 column is consistent with the
  source marker, the substantive basis and the rejection basis the same workbook
  prints in its own reviewer sheets;
* **form classification** -- a blank source form is classified by its own heading
  and column schema.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .applicability_invariants import _flatten
from .semantic_roles import ROLE_BASE_SCORE, ROLE_MAX_SCORE, ROLE_TIER_SCORE
from .source_criticality import (
    BASIS_KINDS,
    CRITICALITY_MANDATORY,
    CRITICALITY_ORDINARY,
    CRITICALITY_SUBSTANTIVE,
    CRITICALITY_SUBSTANTIVE_REJECTION,
    MANDATORY_TYPE_UNCLASSIFIED,
)

# --------------------------------------------------------------------------- #
# 1. polarity / operative wording
# --------------------------------------------------------------------------- #

#: A clause that opens with a *negative condition*: the requirement is the
#: negation of a duty, so the negative wording is what makes it mean anything.
_NEGATION_TOKENS: tuple[str, ...] = (
    "不按",
    "不能按",
    "未按",
    "不符合",
    "未提交",
    "未提供",
    "未在",
    "逾期",
    "超过",
    "不满足",
    "未满足",
    "拒绝",
    "不予受理",
)
_NEGATED_CONDITION_RE = re.compile("|".join(_NEGATION_TOKENS))
#: A cross-reference the extractor used to split on ("本章第3.4.1项").
_CROSS_REFERENCE_RE = re.compile(r"第\s*\d+(?:\.\d+)+\s*[项条款]")


def check_polarity(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A negated operative clause must still carry its negation.

    A condition that names another clause ("供应商不按本章第3.4.1项要求提交响应
    保证金的，评审小组将否决其响应") states its duty through a *negative* verb
    plus a cross-reference.  If the split drops the head, the delivered text
    reads as the opposite requirement -- which is worse than an omission.

    The test is therefore: when a row's source states a negation, and the row's
    delivered requirement quotes a cross-reference, the *negation itself* must
    survive in the delivered text.  An ordinary clause that merely contains a
    "不得" elsewhere is not affected, because the pairing with the row's own
    cross-reference is what makes the negation load-bearing.
    """

    problems: list[dict[str, Any]] = []
    checked = 0
    seen: set[tuple[str, str]] = set()
    for row in rows:
        item_id = str(row.get("item_id") or "")
        sheet = str(row.get("sheet") or "")
        if (item_id, sheet) in seen:
            continue
        seen.add((item_id, sheet))
        requirement = str(row.get("requirement") or "").strip()
        item = row.get("item")
        if not requirement or item is None:
            continue
        if not _CROSS_REFERENCE_RE.search(requirement):
            continue
        point = getattr(item, "review_point", None)
        source_text = str(getattr(point, "owned_backing", "") or "") if point else ""
        if not source_text:
            continue
        source_hit = _NEGATED_CONDITION_RE.search(source_text)
        if not source_hit:
            continue
        checked += 1
        if not any(token in _flatten(requirement) for token in _NEGATION_TOKENS):
            problems.append(
                {
                    "item_id": item_id,
                    "sheet": sheet,
                    "reason": "a negated operative clause lost its negation",
                    "requirement": requirement[:160],
                    "source_negation": source_hit.group(0),
                }
            )
    return {
        "checked": checked,
        "polarity_loss_count": len(problems),
        "polarity_losses": problems,
    }


# --------------------------------------------------------------------------- #
# 2. conditional scoring
# --------------------------------------------------------------------------- #

#: A scoring sentence that awards points *per alternative* ("1、…的得4 分；2、…").
_TIER_SENTENCE_RE = re.compile(r"[（(]?\s*\d{1,2}\s*[、.．)）]")
#: Imperative wording that would make a tier a simultaneous obligation.
_SIMULTANEOUS_DEMAND_RE = re.compile(
    r"(均需|均应|同时满足|全部满足|每一项都|各档均|所有分档|每一档都)"
)
#: The delivered cell's own sentences.
_SENTENCE_SPLIT_RE = re.compile(r"[；;。\n]")


def check_conditional_scoring(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Scoring tiers must be alternatives, and base/ceiling must stay distinct.

    The human fixture: "1、100%接受银行承兑的得 4 分，2、50%接受银行承兑的得2 分"
    was delivered with a check per tier ("核对响应文件已载明：…") *and* one per
    score ("本项最高 4分", "本项最高 2分"), so the workbook told the bidder to
    claim every mutually exclusive tier at once.
    """

    problems: list[dict[str, Any]] = []
    tier_rows = 0
    base_rows = 0
    for row in rows:
        item = row.get("item")
        if item is None:
            continue
        concern_id = str(getattr(item, "concern_id", "") or "")
        if not (concern_id.startswith("SCORING_") or concern_id == "EVALUATION_SCORING"):
            continue
        point = getattr(item, "review_point", None)
        numbers = list(getattr(point, "numeric_evidence", ()) or ()) if point else []
        roles = {str(getattr(number, "role", "")) for number in numbers}
        text = " ".join(
            str(row.get(field) or "")
            for field in ("requirement", "action", "criteria")
        )
        if ROLE_TIER_SCORE in roles:
            tier_rows += 1
            if _SIMULTANEOUS_DEMAND_RE.search(text):
                problems.append(
                    {
                        "item_id": row.get("item_id"),
                        "reason": "scoring tiers are required simultaneously",
                        "text": text[:160],
                    }
                )
            # a tier must never be presented as the factor's ceiling
            if re.search(r"本项最高\s*\d+\s*分[^\n]{0,40}本项最高\s*\d+\s*分", text):
                problems.append(
                    {
                        "item_id": row.get("item_id"),
                        "reason": "two tiers are both presented as the maximum",
                        "text": text[:160],
                    }
                )
        if ROLE_BASE_SCORE in roles:
            base_rows += 1
            if not re.search(r"(基本分|基础分|基准分)", text):
                problems.append(
                    {
                        "item_id": row.get("item_id"),
                        "reason": "the formula's base score is not named as a base score",
                        "text": text[:160],
                    }
                )
        if ROLE_MAX_SCORE in roles:
            # a factor has exactly one ceiling
            ceilings = re.findall(r"本项最高\s*(\d+(?:\.\d+)?)\s*分", text)
            if len(set(ceilings)) > 1 and ROLE_TIER_SCORE not in roles:
                problems.append(
                    {
                        "item_id": row.get("item_id"),
                        "reason": "the factor shows more than one maximum",
                        "text": text[:160],
                    }
                )
    return {
        "tier_rows": tier_rows,
        "base_score_rows": base_rows,
        "conditional_scoring_problem_count": len(problems),
        "conditional_scoring_problems": problems,
    }


# --------------------------------------------------------------------------- #
# 3. blank placeholders / fragment completeness
# --------------------------------------------------------------------------- #

#: The explicit placeholder the renderer writes for a source blank.
BLANK_PLACEHOLDER = "＿＿"


def check_blank_placeholders(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A source blank must be delivered as a blank, never silently rewritten.

    The contract template prints a rule where the grace period has to be filled
    in ("…从最后一笔款项应付之日起给甲方 ______ 的支付宽限期").  Delivering the
    sentence without the blank makes an incomplete factual statement look like a
    complete requirement.
    """

    problems: list[dict[str, Any]] = []
    checked = 0
    for row in rows:
        requirement = str(row.get("requirement") or "")
        if BLANK_PLACEHOLDER not in requirement:
            continue
        checked += 1
        # the placeholder must sit where the source's own gap is: it may not
        # appear at the start (which would turn a label into a value)
        if requirement.lstrip().startswith(BLANK_PLACEHOLDER):
            problems.append(
                {
                    "item_id": row.get("item_id"),
                    "reason": "blank placeholder opens the requirement",
                    "text": requirement[:160],
                }
            )
    return {
        "blank_marked_rows": checked,
        "blank_placeholder_problem_count": len(problems),
        "blank_placeholder_problems": problems,
    }


#: An open enumeration in a delivered requirement: a "…" right after a list.
_TRUNCATED_ENUMERATION_RE = re.compile(
    r"(?:[（(]\s*\d{1,2}\s*[)）]|\d{1,2}\s*[、.．])[^；;。]*…"
)


def check_complete_fragments(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A rendered enumeration is whole, and no clause is rendered twice."""

    problems: list[dict[str, Any]] = []
    for row in rows:
        requirement = str(row.get("requirement") or "")
        if not requirement:
            continue
        if _TRUNCATED_ENUMERATION_RE.search(requirement):
            problems.append(
                {
                    "item_id": row.get("item_id"),
                    "reason": "an enumerated requirement is visibly truncated",
                    "text": requirement[:160],
                }
            )
        # one clause rendered twice in the same requirement is an extraction
        # artifact, not a source statement
        segments = [
            _flatten(piece)
            for piece in re.split(r"[；;]", requirement)
            if len(_flatten(piece)) >= 24
        ]
        seen: set[str] = set()
        for segment in segments:
            if segment in seen:
                problems.append(
                    {
                        "item_id": row.get("item_id"),
                        "reason": "the same clause is rendered twice",
                        "text": requirement[:160],
                    }
                )
                break
            seen.add(segment)
    return {
        "fragment_problem_count": len(problems),
        "fragment_problems": problems,
    }


# --------------------------------------------------------------------------- #
# 4. foreign heading / duplicated wording in the locator
# --------------------------------------------------------------------------- #

#: A source element that is a project *decision* row, not a section heading.
_DECISION_ROW_RE = re.compile(r"^[*★]?\s*\d+(?:\.\d+)+\s*$")
#: Clause labels that appear in a locator's heading slot.
_LOCATOR_CLAUSE_RE = re.compile(r"第([\d.]+)条")


def check_locator_headings(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The heading a locator names must govern the clause the row cites.

    "*3.3.1 询比有效期" was located as "第10页 / *1.12 分包 不允许 / 第3.3.1条":
    the heading belongs to a *different* front-table row, so the reviewer is sent
    to the wrong place in the schedule.

    The defect is specific: a **different front-table row's decision** used as the
    section of a clause.  The check therefore compares the *decision value* the
    heading carries ("分包 不允许") against the row's own requirement: a heading
    whose decision is not this row's requirement is another schedule row.
    """

    problems: list[dict[str, Any]] = []
    checked = 0
    seen: set[tuple[str, str]] = set()
    for row in rows:
        locator = str(row.get("locator") or "")
        if not locator or "（pdf_" not in locator:
            continue
        key = (str(row.get("item_id")), locator)
        if key in seen:
            continue
        seen.add(key)
        parts = [part.strip() for part in locator.split(" / ")]
        if len(parts) < 3:
            continue
        heading = _front_table_row_decision(parts[1])
        if heading is None:
            continue
        # a schedule row that *is* the row's own requirement is its own locator
        label, decision = heading
        requirement = _flatten(row.get("requirement") or "")
        if decision and decision in requirement:
            continue
        checked += 1
        problems.append(
            {
                "item_id": row.get("item_id"),
                "reason": "the locator's heading is another front-table row's decision",
                "heading": f"{label} {decision}",
                "locator": locator[:140],
            }
        )
    return {
        "locator_heading_checked": checked,
        "foreign_locator_heading_count": len(problems),
        "foreign_locator_headings": problems,
    }


#: A front-table row label is *short*: "*1.12 分包 不允许".  A document section
#: heading ("1.5 供应商资格能力和条件", "4.2 响应文件的递交") is a section title,
#: not a schedule decision, so it is not this defect.
_MAX_FRONT_TABLE_LABEL_CHARS = 24
#: A schedule decision states a *project fact*, not a section title: the value is
#: a short predicate the project decided (不允许 / 不组织 / 不接受 / 不召开 / a
#: date, a name, an amount).  Section titles end with a noun ("…的递交").
_SECTION_TITLE_TAIL_RE = re.compile(
    r"(递交|报价|有效期|保证金|组成|评审|办法|须知|要求|规定|条件|格式|合同|条款|标准|方式|地点|时间|内容|说明|程序|资料|材料|清单|表|函)$"
)


def _front_table_row_decision(heading: str) -> tuple[str, str] | None:
    """The (label, decision) of a *front-table row* heading, or None.

    A front table prints each decision as "<clause> <item> <value>" and nothing
    else, and the value is a project fact the schedule decided.  An ordinary
    section title is excluded by its shape, so no document-specific wording is
    needed.
    """

    text = re.sub(r"[\s\u3000]+", " ", str(heading or "")).strip()
    if not text or len(_flatten(text)) > _MAX_FRONT_TABLE_LABEL_CHARS:
        return None
    tokens = [token for token in text.split(" ") if token]
    if not 2 <= len(tokens) <= 3:
        return None
    if not re.fullmatch(r"[*★]?\d+(?:\.\d+)+", tokens[0]):
        return None
    item = tokens[1] if len(tokens) > 1 else ""
    decision = " ".join(tokens[2:])
    if decision:
        return tokens[0], decision
    # a two-token heading ("1.5 供应商资格能力和条件") is a section title, never a
    # schedule row: a schedule row always carries its own decision
    return None


#: A source chapter/article heading that was absorbed into a requirement.
_ABSORBED_HEADING_RE = re.compile(
    r"(?:^|\s)(第[一二三四五六七八九十\d]{1,3}[章条节])\s*$"
)


def check_absorbed_headings(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A requirement must not end with the next source element's heading."""

    problems: list[dict[str, Any]] = []
    for row in rows:
        requirement = str(row.get("requirement") or "")
        found = _ABSORBED_HEADING_RE.search(requirement)
        if found:
            problems.append(
                {
                    "item_id": row.get("item_id"),
                    "reason": "the row absorbed the next source heading",
                    "heading": found.group(1),
                    "text": requirement[:160],
                }
            )
    return {
        "absorbed_heading_count": len(problems),
        "absorbed_headings": problems,
    }


#: A short phrase the extraction repeated back-to-back ("营业 执照 执照").
_DUPLICATED_PHRASE_RE = re.compile(r"([\u4e00-\u9fa5]{2,8})(?:\s+\1)+")
#: A short fragment repeated in one rendered requirement.
_REPEATED_SHORT_RE = re.compile(r"([\u4e00-\u9fa5]{4,12})(?=[^\u4e00-\u9fa5]{0,3}\1)")


def check_duplicated_wording(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """No delivered requirement repeats a phrase the source states once."""

    problems: list[dict[str, Any]] = []
    for row in rows:
        requirement = str(row.get("requirement") or "")
        if not requirement:
            continue
        found = _DUPLICATED_PHRASE_RE.search(requirement)
        if found:
            problems.append(
                {
                    "item_id": row.get("item_id"),
                    "reason": "a source phrase is rendered twice",
                    "phrase": found.group(1),
                    "text": requirement[:160],
                }
            )
    return {
        "duplicated_wording_count": len(problems),
        "duplicated_wording": problems,
    }


# --------------------------------------------------------------------------- #
# 5. cross-sheet risk consistency
# --------------------------------------------------------------------------- #

#: The delivered risk vocabulary.
RISK_VETO = "一票否决"
RISK_LEVELS: tuple[str, ...] = (RISK_VETO, "高", "中", "低")
#: Criticality levels that *are* a rejection claim.
REJECTION_CRITICALITIES = frozenset(
    {CRITICALITY_SUBSTANTIVE_REJECTION}
)


def check_cross_sheet_risk(
    mandatory_rows: Sequence[Mapping[str, Any]],
    legacy_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The legacy sheet's 风险级别 must agree with the reviewer sheet's columns.

    Source marker, substantive status and rejection basis are *separate*
    dimensions, but they may not contradict each other: a row the reviewer sheet
    reports as having no 否决依据 must not be printed as 一票否决 on the delivered
    template.  (Round 7: DR013 and DR038 carried the legacy 一票否决 while their
    own 否决 basis was empty and the 03 sheet said the marker was unclassified.)
    """

    problems: list[dict[str, Any]] = []
    by_id = {
        str(row.get("requirement_id")): row
        for row in mandatory_rows
        if row.get("requirement_id")
    }
    checked = 0
    for row in legacy_rows:
        item_id = str(row.get("item_id") or "")
        risk = str(row.get("risk") or "")
        if not item_id:
            continue
        reviewer = by_id.get(item_id)
        if reviewer is None:
            continue
        checked += 1
        veto_basis = str(reviewer.get("否决性") or "").strip()
        if risk not in RISK_LEVELS:
            problems.append(
                {
                    "item_id": item_id,
                    "reason": "the delivered row has no 风险级别 from the delivered vocabulary",
                    "risk": risk or "(empty)",
                    "veto_basis": veto_basis or "(empty)",
                }
            )
            continue
        # the two sheets report the same dimension and must agree both ways: the
        # legacy template's 一票否决 *is* a rejection claim, so a row that makes
        # it must have a 否决依据, and a row the source gives a 否决依据 may not be
        # delivered as anything less (round-8 fixture DR033: 分包 不允许 carried a
        # derived 否决依据 while the template said 低).
        if (risk == RISK_VETO) != (veto_basis == "是"):
            problems.append(
                {
                    "item_id": item_id,
                    "reason": (
                        "the delivered template says 一票否决 but the row has no 否决依据"
                        if risk == RISK_VETO
                        else "the row has a 否决依据 but the delivered template does not say 一票否决"
                    ),
                    "risk": risk,
                    "veto_basis": veto_basis or "(empty)",
                }
            )
    return {
        "cross_sheet_risk_checked": checked,
        "cross_sheet_risk_mismatch_count": len(problems),
        "cross_sheet_risk_mismatches": problems,
    }


# --------------------------------------------------------------------------- #
# 6. source-form classification
# --------------------------------------------------------------------------- #

#: A blank form class that claims the form is a quotation table.
_QUOTATION_FORM_CLASS_RE = re.compile(r"空白报价表单")
#: Column tokens that only a *quotation* table has.
_QUOTATION_REQUIRED_TOKENS: tuple[tuple[str, ...], ...] = (
    ("单价",),
    ("合价", "小计", "合计", "金额", "总价", "限价"),
)
#: Tokens that identify a *history / qualification* form.
_HISTORY_TOKENS = ("项目名称", "采购人名称", "合同金额", "签订合同", "类似项目", "业绩")


def check_form_classification(blank_forms: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A blank form is a quotation form only when its schema prices an item.

    A similar-project-history table has a contract-amount column, so an amount
    column alone classifies nothing.  The row's class must come from the form's
    own heading and full column schema (round-8 fixture: page 53's
    "七、近年…类似项目情况表" was reported as a blank quotation form).
    """

    problems: list[dict[str, Any]] = []
    for form in blank_forms:
        form_class = str(form.get("form_class") or "")
        columns = str(form.get("columns") or "")
        heading = str(form.get("heading") or "")
        if not _QUOTATION_FORM_CLASS_RE.search(form_class):
            continue
        flat_columns = _flatten(columns)
        history = any(_flatten(token) in _flatten(heading + columns) for token in _HISTORY_TOKENS)
        priced = all(
            any(token in flat_columns for token in group)
            for group in _QUOTATION_REQUIRED_TOKENS
        )
        unit_or_quantity = "单位" in flat_columns or "数量" in flat_columns
        if history and not priced:
            problems.append(
                {
                    "page": form.get("page"),
                    "reason": "a history form is classified as a blank quotation form",
                    "heading": heading[:80],
                    "columns": columns[:120],
                }
            )
        elif not (priced and unit_or_quantity):
            problems.append(
                {
                    "page": form.get("page"),
                    "reason": "a blank form is called a quotation form without a pricing schema",
                    "heading": heading[:80],
                    "columns": columns[:120],
                }
            )
    return {
        "blank_form_checked": len(blank_forms),
        "form_classification_problem_count": len(problems),
        "form_classification_problems": problems,
    }


# --------------------------------------------------------------------------- #
# 7. the criticality vocabulary is the one the checks assume
# --------------------------------------------------------------------------- #


def criticality_vocabulary_ok() -> bool:
    """The risk check must be written against the vocabulary the engine emits."""

    levels = {
        CRITICALITY_ORDINARY,
        CRITICALITY_SUBSTANTIVE,
        CRITICALITY_SUBSTANTIVE_REJECTION,
        CRITICALITY_MANDATORY,
    }
    return (
        len(levels) == 4
        and all(isinstance(item, str) and item for item in BASIS_KINDS)
        and MANDATORY_TYPE_UNCLASSIFIED != ""
        and REJECTION_CRITICALITIES <= levels
    )


__all__ = [
    "BLANK_PLACEHOLDER",
    "RISK_LEVELS",
    "RISK_VETO",
    "check_absorbed_headings",
    "check_blank_placeholders",
    "check_complete_fragments",
    "check_conditional_scoring",
    "check_cross_sheet_risk",
    "check_duplicated_wording",
    "check_form_classification",
    "check_locator_headings",
    "check_polarity",
    "criticality_vocabulary_ok",
]
