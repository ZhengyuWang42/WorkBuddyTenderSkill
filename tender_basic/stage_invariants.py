"""Review-stage separation invariants (bid response vs contract risk).

The human product decision this module gates:

    报价/商务响应 = 投标响应项
    合同条款     = 投标前风险识别项

A pure post-award contract condition must not affect bid compliance, rejection
or scoring.  These checks read the **delivered** rows and the concern's own
saved stage, so a contract risk can never quietly become a bid blocker, and a
genuine response requirement can never be quietly demoted.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .review_stage import (
    BID_RESPONSE,
    CONTRACT_RISK_NOTICE,
    INFORMATIONAL,
    SCORING_RESPONSE,
)

#: Wording that only makes sense for a response-file obligation.  A pure
#: contract risk may not carry it: the source asked the bidder for no such
#: declaration, so the wording would invent one.
RESPONSE_FILE_CUES: tuple[str, ...] = (
    "核对响应文件已载明",
    "确认响应文件接受",
    "响应文件中被接受",
    "与响应文件一致",
    "响应文件一致",
    "在响应文件中明确",
    "响应文件接受该比例",
)


def _text(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(field) or "")
        for field in ("requirement", "action", "criteria", "consequence", "locator")
    )


def contract_risk_contamination(row: Mapping[str, Any]) -> dict[str, Any]:
    """Everything about ``row`` that wrongly presents it as bid-response.

    ``row`` is one delivered item with its ``stage`` (from ``review_stage``) and
    its delivered text / risk label / mandatory flags.
    """

    stage = str(row.get("stage") or "")
    findings: list[str] = []
    if stage != CONTRACT_RISK_NOTICE:
        return {"row": row.get("item_id"), "stage": stage, "findings": findings}
    risk = str(row.get("risk") or "")
    if risk in ("一票否决",):
        findings.append("risk_claims_rejection")
    if str(row.get("veto") or "").strip() == "是":
        findings.append("veto_column_is_yes")
    if row.get("rejection"):
        findings.append("rejection_consequence")
    if row.get("substantive"):
        findings.append("substantive_requirement")
    mandatory = [str(value) for value in (row.get("mandatory_types") or ())]
    if any(
        value.startswith("SUBSTANTIVE") or value == "REJECTION"
        for value in mandatory
    ):
        findings.append("substantive_or_rejection_type")
    text = _text(row)
    flat = "".join(text.split())
    for cue in RESPONSE_FILE_CUES:
        if "".join(cue.split()) in flat:
            findings.append(f"response_file_wording:{cue}")
    if "不满足导致否决" in flat or "投标响应不满足" in flat:
        findings.append("rejection_presentation")
    return {"row": row.get("item_id"), "stage": stage, "findings": findings}


def check_stage_separation(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count every pure contract risk that still reads as a bid blocker."""

    contaminated: list[dict[str, Any]] = []
    checked = 0
    per_stage: dict[str, int] = {}
    for row in rows:
        stage = str(row.get("stage") or "")
        if stage:
            per_stage[stage] = per_stage.get(stage, 0) + 1
        if stage != CONTRACT_RISK_NOTICE:
            continue
        checked += 1
        finding = contract_risk_contamination(row)
        if finding["findings"]:
            contaminated.append(finding)
    return {
        "contract_risk_row_checked": checked,
        "contract_risk_as_bid_blocker_count": len(contaminated),
        "contract_risk_as_bid_blockers": contaminated[:12],
        "per_stage": per_stage,
    }


def check_response_side_not_demoted(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """No concern that must be answered in the response may be a risk notice."""

    demoted: list[dict[str, Any]] = []
    checked = 0
    for row in rows:
        expected = str(row.get("expected_stage") or "")
        if expected not in (BID_RESPONSE, SCORING_RESPONSE):
            continue
        checked += 1
        stage = str(row.get("stage") or "")
        if stage != expected:
            demoted.append(
                {
                    "item_id": row.get("item_id"),
                    "concern_id": row.get("concern_id"),
                    "expected_stage": expected,
                    "stage": stage,
                }
            )
    return {
        "response_row_checked": checked,
        "response_row_demoted_count": len(demoted),
        "response_row_demoted": demoted[:12],
    }


__all__ = [
    "RESPONSE_FILE_CUES",
    "contract_risk_contamination",
    "check_stage_separation",
    "check_response_side_not_demoted",
]
