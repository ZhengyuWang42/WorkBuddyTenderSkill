"""Final-delivery text invariants read from the SAVED workbook cells.

The internal objects can be correct while the *delivered* text still says the
wrong thing, so these checks take the actual cell strings a reviewer reads:

* a pure **contract-risk** row must carry internal pre-bid risk language and must
  not ask for response-file comparison / declaration;
* a **two-source** row must make both source roles understandable;
* an **evidence summary** must never be clipped inside a material source token
  (standard identifier, clause number, money, percentage, date, URL, marker).

They deliberately take plain strings, so they can run against ``openpyxl`` cell
values with no access to the plan that produced them.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

#: Response-file wording that only makes sense when the *response* must answer the
#: clause.  A pure post-award contract risk is reviewed before bidding instead.
RESPONSE_FILE_PHRASES: tuple[str, ...] = (
    "逐条比对响应文件",
    "核对响应文件已载明",
    "响应文件接受",
    "与响应文件一致",
    "响应文件中提供",
    "响应文件载明",
    "投标文件接受",
    "响应文件中被接受",
)

#: The internal pre-bid wording a contract risk may use.
PRE_BID_PHRASES: tuple[str, ...] = (
    "查阅合同",
    "项目专用条款原文",
    "已知悉",
    "内部决策",
)

#: Material tokens that must never be cut in half by an evidence-summary clip.
#: Each pattern matches a token that ends at the very end of the displayed text.
_STANDARD_ID_RE = re.compile(r"[A-Za-z]{1,6}\s*/?\s*T?\s*\d[\d.\-/]*$")

#: A standard / code identifier is *complete* when it ends with its edition year
#: (``GB50015-2019``, ``GBJ 54-83``).  ``GB50015-2`` is the truncated shape the
#: human review found on 投标项目复核表!E38.
_COMPLETE_STANDARD_ID_RE = re.compile(r"-\d{2}$|-\d{4}$")

_OPEN_TOKEN_RES: tuple[re.Pattern[str], ...] = (
    # a standard / code identifier: "GB50015-2019", "CJJ140-2018", "CJ/T 415-2013"
    _STANDARD_ID_RE,
    # a clause number: "3.4.2", "第3.4条"
    re.compile(r"\d+(?:\.\d+)+$"),
    # a monetary value: "3100000 元", "￥12.5万"
    re.compile(r"[¥￥]?\s*\d[\d,]*(?:\.\d+)?\s*(?:万元|元|万)?$"),
    # a percentage: "95%"
    re.compile(r"\d+(?:\.\d+)?\s*[%％]$"),
    # a date: "2026-07-28", "2026 年 7 月"
    re.compile(r"\d{4}\s*[-/年]\s*\d{0,2}\s*(?:[-/月]\s*\d{0,2}\s*日?)?$"),
    # a URL
    re.compile(r"(?:https?://|www\.)\S*$"),
)

#: A source marker token the row displays.
_MARKER_RE = re.compile(r"[★☆*＊]\s*$")


def _flat(text: object) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or ""))


def response_file_language(text: object) -> list[str]:
    """Response-file phrases present in a delivered cell."""

    flat = _flat(text)
    return [phrase for phrase in RESPONSE_FILE_PHRASES if _flat(phrase) in flat]


def pre_bid_language(text: object) -> list[str]:
    """The internal pre-bid phrases present in a delivered cell."""

    flat = _flat(text)
    return [phrase for phrase in PRE_BID_PHRASES if _flat(phrase) in flat]


def check_contract_risk_delivery(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Saved-cell check: contract-risk rows stay internal risk review.

    ``rows`` entries are ``{"item_id", "sheet", "cell", "review_stage", "text"}``
    where ``text`` is the concatenation of the *displayed* requirement, review
    actions and pass criterion.
    """

    contaminated: list[dict[str, Any]] = []
    checked = 0
    for row in rows:
        if str(row.get("review_stage") or "") != "CONTRACT_RISK_NOTICE":
            continue
        checked += 1
        found = response_file_language(row.get("text"))
        if found:
            contaminated.append(
                {
                    "item_id": row.get("item_id"),
                    "sheet": row.get("sheet"),
                    "cell": row.get("cell"),
                    "phrases": found,
                    "text": str(row.get("text") or "")[:200],
                }
            )
    return {
        "contract_risk_row_checked": checked,
        "pure_contract_risk_response_file_language_count": len(contaminated),
        "contaminated": contaminated[:12],
    }


#: The pre-bid wording that *claims* a two-source composition.
TWO_ROLE_ANNOUNCEMENT = "查阅合同/项目专用条款原文"

#: The source roles such a claim must deliver.
PROJECT_ROLE_LABEL = "项目专用值"
GENERAL_ROLE_LABEL = "通用/中标后条款"

#: ``<where>（项目专用值）`` -- the page/clause a declared role is attached to.
_ROLE_LABEL_RE = re.compile(
    r"(?P<where>[^；;。\n]{0,60}?)\s*[（(]\s*(?P<role>"
    + PROJECT_ROLE_LABEL
    + "|"
    + GENERAL_ROLE_LABEL
    + r")\s*[）)]"
)


def source_role_labels(text: object) -> dict[str, str]:
    """The page/clause each *declared* source role is attached to.

    A cell that claims two sources must say **which** source is the project value
    and which is the general/post-award clause; this reads those two attachments
    back out of the delivered text so a gate can assert them by page and clause.
    """

    labels: dict[str, str] = {}
    for match in _ROLE_LABEL_RE.finditer(str(text or "")):
        role = match.group("role")
        # keep only the source reference itself: the wording that introduced it
        # ("查阅合同/项目专用条款原文：其中", "并依据") is not part of the locator
        where = re.split(r"其中|：|依据", _flat(match.group("where")))[-1][-32:]
        if where and role not in labels:
            labels[role] = where
    return labels


def check_multi_source_role_display(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Saved-cell check: a claim of two source roles delivers both of them.

    Only a row that *declares* the pre-bid two-source composition
    ("查阅合同/项目专用条款原文") is in scope.  Round-11's separate
    ``MULTI_SOURCE_EVIDENCE_ROLE_AMBIGUITY_COUNT`` already requires every page a
    response row cites beyond its own to be introduced as an explicit second
    source; this round-12 check closes the other half: once a row says it composes
    a project value with a general clause, the delivered cell has to name *both*
    roles -- a half-declared pair (or a bare "合同条款原文") is what made DR037's
    front-table value indistinguishable from the post-award obligation.

    ``rows`` entries are ``{"item_id", "sheet", "cell", "text", "source_pages"}``.
    """

    ambiguous: list[dict[str, Any]] = []
    checked = 0
    for row in rows:
        text = _flat(row.get("text"))
        if TWO_ROLE_ANNOUNCEMENT not in text:
            continue
        checked += 1
        labels = source_role_labels(row.get("text"))
        has_project = PROJECT_ROLE_LABEL in labels
        has_general = GENERAL_ROLE_LABEL in labels
        if not (has_project and has_general):
            ambiguous.append(
                {
                    "item_id": row.get("item_id"),
                    "sheet": row.get("sheet"),
                    "cell": row.get("cell"),
                    "source_pages": list(row.get("source_pages") or ()),
                    "has_project_role": has_project,
                    "has_general_role": has_general,
                    "roles": labels,
                    "text": str(row.get("text") or "")[:200],
                }
            )
    return {
        "multi_source_row_checked": checked,
        "multi_source_role_display_ambiguity_count": len(ambiguous),
        "ambiguous": ambiguous[:12],
    }


def mid_token_truncation(text: object) -> str:
    """The material token a clipped cell ends inside, or "" when it is clean.

    Only a cell that is actually truncated (it ends with the explicit clip mark)
    can be mid-token: a complete sentence may of course end with a number.
    """

    value = str(text or "").rstrip()
    if not value.endswith("…"):
        return ""
    head = value[:-1].rstrip()
    if not head:
        return ""
    tail = head[-24:]
    for pattern in _OPEN_TOKEN_RES:
        match = pattern.search(tail)
        if not match or not match.group(0).strip():
            continue
        token = match.group(0).strip()
        if pattern is _STANDARD_ID_RE and _COMPLETE_STANDARD_ID_RE.search(token):
            # the cell ends after a *complete* identifier: the clip is clean
            return ""
        return token
    if _MARKER_RE.search(tail):
        return _MARKER_RE.search(tail).group(0).strip()
    return ""


def check_evidence_summary_clipping(
    cells: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Saved-cell check: no evidence summary is clipped inside a material token.

    ``cells`` entries are ``{"sheet", "cell", "text"}``.
    """

    problems: list[dict[str, Any]] = []
    checked = 0
    for cell in cells:
        text = str(cell.get("text") or "")
        if not text.strip():
            continue
        checked += 1
        token = mid_token_truncation(text)
        if token:
            problems.append(
                {
                    "sheet": cell.get("sheet"),
                    "cell": cell.get("cell"),
                    "token": token,
                    "text": text[-90:],
                }
            )
    return {
        "evidence_summary_cell_checked": checked,
        "mid_token_evidence_truncation_count": len(problems),
        "problems": problems[:12],
    }


__all__ = [
    "RESPONSE_FILE_PHRASES",
    "PRE_BID_PHRASES",
    "TWO_ROLE_ANNOUNCEMENT",
    "PROJECT_ROLE_LABEL",
    "GENERAL_ROLE_LABEL",
    "response_file_language",
    "pre_bid_language",
    "source_role_labels",
    "check_contract_risk_delivery",
    "check_multi_source_role_display",
    "mid_token_truncation",
    "check_evidence_summary_clipping",
]
