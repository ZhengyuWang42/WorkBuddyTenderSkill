"""Review stage: when a source obligation must actually be answered.

The human product decision this module banks:

    报价/商务响应 = 投标响应项
    合同条款     = 投标前风险识别项

A *pure* post-award contract condition (a payment grace period, a retention
release term, a post-award performance-bond duty, a termination/refund liability)
must not decide whether the bid is compliant, responsive or rejectable, and must
not be scored.  It exists so the bid team knows the commercial risk **before**
submitting.

Two rules follow, and both are enforced in code:

* **The source chapter does not determine the stage.**  A cost clause inside the
  contract chapter still belongs to the bidder's quotation and therefore stays a
  bid-response item; a payment condition used directly as an evaluation factor
  stays a scoring item.
* **A stage is not an architecture.**  It is one derived attribute of the concern
  that already owns the row -- it adds no second provenance chain, no second
  locator and no second concern graph.

The stage is derived from *effect and stage* (who must act, when, and whether the
document evaluates/reacts to the response), never from a chapter name and never
from a case id.
"""

from __future__ import annotations

import re
from typing import Any

#: The bidder must address or satisfy it in the response; it may affect
#: compliance, evaluation or bid validity.
BID_RESPONSE = "BID_RESPONSE"
#: The bidder's selected response affects scoring; still a bid-response item.
SCORING_RESPONSE = "SCORING_RESPONSE"
#: A post-award / contract-performance condition the bid team must know before
#: deciding to bid.  It does not by itself determine responsiveness, rejection or
#: score.
CONTRACT_RISK_NOTICE = "CONTRACT_RISK_NOTICE"
#: Context only.
INFORMATIONAL = "INFORMATIONAL"

REVIEW_STAGES: tuple[str, ...] = (
    BID_RESPONSE,
    SCORING_RESPONSE,
    CONTRACT_RISK_NOTICE,
    INFORMATIONAL,
)

#: The stage's own visible classification in the delivered workbook.  It is a
#: *stage* label, never a rejection vocabulary: a contract-risk row shows
#: ``风险提示`` and no 否决/实质性 wording.
STAGE_LABELS: dict[str, str] = {
    BID_RESPONSE: "响应项",
    SCORING_RESPONSE: "评分响应项",
    CONTRACT_RISK_NOTICE: "风险提示",
    INFORMATIONAL: "参考信息",
}

#: The stage a concern's own contract kind maps to, when the kind is decisive.
#: A pure contract clause is a pre-bid risk notice *unless* the concern carries
#: its own response-stage evidence (see :func:`review_stage_for`).
_CONTRACT_KINDS: frozenset[str] = frozenset({"CONTRACT_ONLY"})

#: Source wording that puts the obligation on the **response** side even though
#: the clause sits in the contract chapter: the response itself must state, accept
#: or contain it.  It is *source evidence*, not a chapter rule.
RESPONSE_STAGE_SIGNATURES: tuple[str, ...] = (
    r"响应文件(?:中)?(?:应|须|需|必须|应当)?(?:载明|明确|包含|列入|附|提交)",
    r"(?:应|须|需|必须|应当)在响应文件中",
    r"投标文件(?:中)?(?:应|须|需|必须|应当)?(?:载明|明确|包含|列入|附|提交)",
    r"报价(?:应|须|需|必须|应当)?(?:包含|包括|含)",
)

#: Source wording that marks the obligation as **post-award**: it binds after the
#: contract is signed / after award, so it cannot decide responsiveness.
POST_AWARD_SIGNATURES: tuple[str, ...] = (
    r"签订合同(?:前|后|时)",
    r"合同(?:签订|生效|履行|执行)(?:前|后|时|期间|期内)",
    r"(?:中标|成交)(?:后|人)",
    r"履约(?:期间|期内|过程中)",
    r"缺陷责任期",
    r"质保期满",
    r"保修期",
    r"验收(?:合格|完成)后",
    r"结算(?:时|后)",
    r"付款(?:时|后)",
)

_RESPONSE_RE = tuple(re.compile(pattern) for pattern in RESPONSE_STAGE_SIGNATURES)
_POST_AWARD_RE = tuple(re.compile(pattern) for pattern in POST_AWARD_SIGNATURES)


def stage_label(stage: str) -> str:
    """The visible label for a stage (never a rejection vocabulary)."""

    return STAGE_LABELS.get(str(stage or ""), "")


def is_contract_risk(stage: str) -> bool:
    return str(stage or "") == CONTRACT_RISK_NOTICE


def _flat(text: object) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or ""))


def source_is_post_award(text: object) -> bool:
    """Does the source wording bind the obligation only after award?"""

    flat = _flat(text)
    if not flat:
        return False
    return any(pattern.search(flat) for pattern in _POST_AWARD_RE)


def source_requires_response(text: object) -> bool:
    """Does the source explicitly require the **response** to carry it?

    This is the independent evidence that keeps a contract-chapter clause on the
    response side: a contract clause that tells the bidder what its response must
    state is a bid-response requirement, not a mere risk notice.
    """

    flat = _flat(text)
    if not flat:
        return False
    return any(pattern.search(flat) for pattern in _RESPONSE_RE)


def review_stage_for(
    concern: Any,
    *,
    concern_id: str = "",
    contract_kind: str = "",
    source_text: str = "",
    evidence_text: str = "",
) -> str:
    """The review stage of one concern / row.

    ``(concern_id, contract_kind, source_text, evidence_text)`` are all that is
    needed, and each is generic:

    * a **scoring** concern is :data:`SCORING_RESPONSE` (its selected response is
      scored), whatever contract vocabulary it shares;
    * a concern the source makes binding *on the response* -- explicit response
      wording, or an independent response-stage consequence such as rejection --
      is :data:`BID_RESPONSE`;
    * a **pure contract** concern (``CONTRACT_ONLY``) whose obligation applies
      after award and whose source asks nothing of the response is
      :data:`CONTRACT_RISK_NOTICE`;
    * an informational concern is :data:`INFORMATIONAL`.

    The chapter a clause was printed in is never consulted.
    """

    cid = str(concern_id or getattr(concern, "concern_id", "") or "")
    kind = str(contract_kind or "")
    if cid.startswith("SCORING_") or kind == "SCORING":
        return SCORING_RESPONSE
    evidence = " ".join(
        [str(source_text or ""), str(evidence_text or "")]
    )
    has_consequence = _concern_has_response_consequence(concern)
    if kind == "CONTRACT_ONLY":
        if source_requires_response(evidence) or has_consequence:
            # independent source evidence keeps it on the response side
            return BID_RESPONSE
        return CONTRACT_RISK_NOTICE
    if kind == "INFORMATIONAL":
        return INFORMATIONAL
    # MANDATORY / REJECTION / SCORING and every fallback contract: the bidder
    # must answer it in the response.
    return BID_RESPONSE


def _concern_has_response_consequence(concern: Any) -> bool:
    """Does the concern carry its own response-stage rejection evidence?

    A consequence the *document* attaches to the response (否决 / 无效 / 不予受理)
    is response-stage evidence; a post-award liability (赔偿 / 利息) is not.
    Consequences are owned per atom (``owned_consequence`` returns the first one
    the contract lets the concern display), so the atom list is the right place to
    ask.
    """

    if concern is None:
        return False
    markers: list[str] = []
    owned = getattr(concern, "owned_consequence", None)
    if callable(owned):
        try:
            text, _atom = owned()
        except (TypeError, ValueError):
            text = ""
        if text:
            markers.append(str(text))
    for atom in getattr(concern, "atoms", ()) or ():
        marker = str(getattr(atom, "explicit_consequence", "") or "")
        if marker:
            markers.append(marker)
    if not markers:
        return False
    flat = _flat(" ".join(markers))
    return any(_flat(cue) in flat for cue in _RESPONSE_CONSEQUENCES)


_RESPONSE_CONSEQUENCES: tuple[str, ...] = (
    "否决投标",
    "否决其投标",
    "将被否决",
    "予以否决",
    "投标无效",
    "响应无效",
    "响应文件无效",
    "不予受理",
    "取消资格",
    "取消其成交资格",
    "不得参加",
)


__all__ = [
    "BID_RESPONSE",
    "SCORING_RESPONSE",
    "CONTRACT_RISK_NOTICE",
    "INFORMATIONAL",
    "REVIEW_STAGES",
    "STAGE_LABELS",
    "stage_label",
    "is_contract_risk",
    "source_is_post_award",
    "source_requires_response",
    "review_stage_for",
]
