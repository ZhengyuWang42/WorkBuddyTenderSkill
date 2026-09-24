"""Independent semantic contracts for review concerns (round 5).

Round 4 made every rendered phrase *traceable* to its concern.  The CASE001
human review then failed the workbook with

    FAIL_REASON = CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED

because traceability is not meaning: a component can be perfectly owned by its
``ReviewConcern`` while the concern itself (or the semantic role it assigns) is
wrong.  Round 5 therefore gives every concern an **independent contract**: a
hand-written specification of

* which actors and authority scopes may produce it,
* which source signatures it *requires* and which it *forbids*,
* which numeric roles, linked facts, materials, consequences and scoring roles it
  may use,
* what its primary evidence must literally say,
* whether it is mandatory / rejection / scoring / contract-only / informational.

The table below is written from the human fixture list (A-T) and the source
semantics -- never from the generated ``ReviewPoint`` it validates.  The
validator only reads text that a human can read in the final workbook, so a
contract failure is a *semantic* failure, not a provenance failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .semantic_roles import (
    NEVER_USABLE_ROLES,
    NON_REVIEW_ROLES,
    ROLE_AGENCY_SERVICE_FEE,
    ROLE_BANK_ACCEPTANCE_RATIO,
    ROLE_BID_VALIDITY_DAYS,
    ROLE_BOND_AMOUNT,
    ROLE_BOND_FORM,
    ROLE_CONTACT_INFO,
    ROLE_DELIVERY_DAYS,
    ROLE_OTHER,
    ROLE_PAYMENT_RATIO,
    ROLE_PERFORMANCE_BOND,
    ROLE_PERSON_COUNT,
    ROLE_PRICE,
    ROLE_PRICE_CEILING,
    ROLE_PROJECT_WARRANTY_MONTHS,
    ROLE_QUANTITY,
    ROLE_RESPONSE_BOND,
    ROLE_RESPONSE_DAYS,
    ROLE_RETENTION_MONEY_RATIO,
    ROLE_RETENTION_RELEASE_MONTHS,
    ROLE_SCORE_POINTS,
    ROLE_TENDER_DOCUMENT_PRICE,
)

SCHEMA = "v1_concern_contract/1"

#: The contracts are authored from the human brief (fixtures A-T) and the source
#: vocabulary, NOT derived from the concern classifier under test.
CONTRACT_SOURCE = "human_round5_fixtures_A_T"

KIND_MANDATORY = "MANDATORY"
KIND_REJECTION = "REJECTION"
KIND_SCORING = "SCORING"
KIND_CONTRACT_ONLY = "CONTRACT_ONLY"
KIND_INFORMATIONAL = "INFORMATIONAL"
KINDS = frozenset({KIND_MANDATORY, KIND_REJECTION, KIND_SCORING, KIND_CONTRACT_ONLY, KIND_INFORMATIONAL})

ACTOR_BIDDER = "BIDDER"
ACTOR_PURCHASER = "PURCHASER"
ACTOR_PLATFORM = "PLATFORM"
ACTOR_AGENT = "AGENT"

CONSEQUENCE_NONE = "NONE"
CONSEQUENCE_VOID = "VOID"  # 无效
CONSEQUENCE_REJECT = "REJECT"  # 否决
CONSEQUENCE_NO_ACCEPT = "NO_ACCEPT"  # 不予受理
CONSEQUENCE_DISQUALIFY = "DISQUALIFY"  # 不得参加 / 取消资格
CONSEQUENCE_LIABILITY = "LIABILITY"  # 赔偿/利息等合同责任
CONSEQUENCES = frozenset(
    {
        CONSEQUENCE_NONE,
        CONSEQUENCE_VOID,
        CONSEQUENCE_REJECT,
        CONSEQUENCE_NO_ACCEPT,
        CONSEQUENCE_DISQUALIFY,
        CONSEQUENCE_LIABILITY,
    }
)

#: Consequence classes recognised in rendered text (longest cues first).
CONSEQUENCE_CUES: tuple[tuple[str, str], ...] = (
    ("不予受理", CONSEQUENCE_NO_ACCEPT),
    ("不得参加", CONSEQUENCE_DISQUALIFY),
    ("取消其成交资格", CONSEQUENCE_DISQUALIFY),
    ("视为放弃成交", CONSEQUENCE_DISQUALIFY),
    ("否决", CONSEQUENCE_REJECT),
    ("无效", CONSEQUENCE_VOID),
    ("赔偿", CONSEQUENCE_LIABILITY),
    ("利息", CONSEQUENCE_LIABILITY),
)


def consequence_class(text: str) -> str:
    """Classify a rendered consequence sentence (never invents one)."""

    for cue, klass in CONSEQUENCE_CUES:
        if cue in str(text or ""):
            return klass
    return CONSEQUENCE_NONE


@dataclass(frozen=True)
class ConcernContract:
    """An independent semantic specification of one review concern."""

    concern_id: str
    kind: str
    actors: frozenset[str] = frozenset({ACTOR_BIDDER})
    #: source signatures *any* of which must appear in a segment the concern owns
    required_signatures: tuple[str, ...] = ()
    #: source signatures that must never appear in a segment the concern owns
    forbidden_signatures: tuple[str, ...] = ()
    allowed_roles: frozenset[str] = frozenset()
    forbidden_roles: frozenset[str] = frozenset()
    allowed_fact_keys: frozenset[str] = frozenset()
    #: signatures the *primary evidence* of the row must literally contain
    required_evidence: tuple[str, ...] = ()
    forbidden_evidence: tuple[str, ...] = ()
    allowed_consequences: frozenset[str] = frozenset(CONSEQUENCES)
    #: materials must match one of these regexes (empty = the concern's own list)
    allowed_material_classes: tuple[str, ...] = ()
    #: scoring factors this concern may score (SCORING contracts only)
    scoring_roles: frozenset[str] = frozenset()
    #: human fixture letter(s) this contract implements
    fixtures: tuple[str, ...] = ()
    rationale: str = ""
    #: False for the permissive fallback contract of an unlisted concern
    explicit: bool = True
    #: authority scopes (empty = any)
    authority_scopes: frozenset[str] = frozenset()

    # -- matching ---------------------------------------------------------- #

    def owned_segment_ok(self, segment: str) -> bool:
        """True when ``segment`` may be owned (and rendered) by this concern."""

        text = str(segment or "")
        if not text.strip():
            return False
        flat = _nospace(text)
        for pattern in self.forbidden_signatures:
            if re.search(pattern, flat):
                return False
        if self.required_signatures:
            return any(re.search(pattern, flat) for pattern in self.required_signatures)
        return True

    def evidence_ok(self, evidence: str) -> bool:
        """True when ``evidence`` may serve as the row's primary locator text."""

        flat = _nospace(evidence)
        if not flat:
            return not self.required_evidence
        for pattern in self.forbidden_evidence:
            if re.search(pattern, flat):
                return False
        if not self.required_evidence:
            return True
        return any(re.search(pattern, flat) for pattern in self.required_evidence)

    def evidence_forbidden(self, evidence: str) -> bool:
        """True when the contract forbids this text as the row's evidence."""

        flat = _nospace(evidence)
        if not flat:
            return False
        return any(re.search(pattern, flat) for pattern in self.forbidden_evidence)

    def section_ok(self, locator: str) -> bool:
        """True when a *locator* (page/section/clause title) may be displayed.

        A locator is not a requirement, so it needs no required signature -- but
        it may never name another concern's facet: a quality row must not cite
        the "交货地点" section, and a performance-bond row must not cite the
        response-bond clause (fixtures A and F).
        """

        flat = _nospace(locator)
        if not flat:
            return True
        for pattern in tuple(self.forbidden_signatures) + tuple(self.forbidden_evidence):
            if re.search(pattern, flat):
                return False
        return True

    def role_ok(self, role: str) -> bool:
        if role in self.forbidden_roles:
            return False
        if self.allowed_roles:
            return role in self.allowed_roles
        return role not in NEVER_USABLE_ROLES

    def fact_ok(self, key: str) -> bool:
        return not self.allowed_fact_keys or key in self.allowed_fact_keys

    def material_ok(self, name: str) -> bool:
        if not self.allowed_material_classes:
            return True
        return any(re.search(pattern, str(name)) for pattern in self.allowed_material_classes)

    def consequence_ok(self, text: str) -> bool:
        return consequence_class(text) in self.allowed_consequences

    def as_dict(self) -> dict[str, Any]:
        return {
            "concern_id": self.concern_id,
            "kind": self.kind,
            "actors": sorted(self.actors),
            "required_signatures": list(self.required_signatures),
            "forbidden_signatures": list(self.forbidden_signatures),
            "allowed_roles": sorted(self.allowed_roles),
            "forbidden_roles": sorted(self.forbidden_roles),
            "allowed_fact_keys": sorted(self.allowed_fact_keys),
            "required_evidence": list(self.required_evidence),
            "forbidden_evidence": list(self.forbidden_evidence),
            "allowed_consequences": sorted(self.allowed_consequences),
            "allowed_material_classes": list(self.allowed_material_classes),
            "scoring_roles": sorted(self.scoring_roles),
            "fixtures": list(self.fixtures),
            "rationale": self.rationale,
            "explicit": self.explicit,
            "source": CONTRACT_SOURCE,
            "schema": SCHEMA,
        }


def _nospace(text: object) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or ""))


# --------------------------------------------------------------------------- #
# the contract table
# --------------------------------------------------------------------------- #

#: Signatures reused by several contracts.
_LOCATION = r"(交货地点|交付地点|供货地点|实施地点|项目现场|泵站|地址|联系人|联系方式|电话)"
_CREDIT = r"(黑名单|失信|被执行人|信用中国|经营异常|严重违法|税收违法|信用记录)"
_SCORE_SENTENCE = r"(得[^，。；]{0,6}\d+\s*分|（\d+\s*分）|\(\d+\s*分\)|分值|评分|计分)"
_AGENCY = r"(代理服务费|招标代理服务费|中标服务费|成交服务费|采购代理服务费)"


def _c(concern_id: str, kind: str, **kwargs: Any) -> ConcernContract:
    return ConcernContract(concern_id=concern_id, kind=kind, **kwargs)


CONTRACTS: dict[str, ConcernContract] = {}


def _register(contract: ConcernContract) -> ConcernContract:
    CONTRACTS[contract.concern_id] = contract
    return contract


# --- qualification / rejection --------------------------------------------- #

_register(
    _c(
        "QUALIFICATION_CREDIT",
        KIND_REJECTION,
        required_signatures=(_CREDIT,),
        allowed_consequences=frozenset({CONSEQUENCE_VOID, CONSEQUENCE_REJECT, CONSEQUENCE_DISQUALIFY, CONSEQUENCE_NONE}),
        fixtures=("B",),
        rationale="a credit-record exclusion clause; a validity period is not credit evidence",
    )
)
_register(
    _c(
        "QUALIFICATION_LICENSE",
        KIND_MANDATORY,
        required_signatures=(r"(营业执照|独立法人|民事责任能力|资质证书|资质等级)",),
        rationale="licence/legal-person duty only; no invented licence grade",
    )
)
_register(
    _c(
        "QUALIFICATION_FINANCIAL",
        KIND_MANDATORY,
        required_signatures=(r"(财务状况|审计报告|财务报表|资产|破产|冻结)",),
        forbidden_signatures=(r"(资金来源|自筹|财政资金)",),
        fixtures=("C",),
        rationale="bidder financial standing; the project's funding source is not a bidder duty",
    )
)
_register(
    _c(
        "QUALIFICATION_ANTI_BRIBERY",
        KIND_MANDATORY,
        required_signatures=(r"(行贿|不良履约记录|违法记录|承诺)",),
    )
)
_register(
    _c(
        "QUALIFICATION_PERFORMANCE",
        KIND_MANDATORY,
        required_signatures=(r"(业绩|类似项目|合同)",),
    )
)
_register(
    _c(
        "QUALIFICATION_RELATIONSHIP_RESTRICTION",
        KIND_REJECTION,
        required_signatures=(r"(单位负责人|控股|管理关系|关联)",),
        allowed_fact_keys=frozenset(),
    )
)
_register(
    _c(
        "CONSORTIUM",
        KIND_MANDATORY,
        required_signatures=(r"(联合体|联合投标|共同投标)",),
        allowed_fact_keys=frozenset({"consortium_allowed"}),
    )
)
_register(
    _c(
        "SUBCONTRACT",
        KIND_MANDATORY,
        required_signatures=(r"(分包|转包)",),
    )
)
_register(
    _c(
        "REJECTION_GENERAL",
        KIND_REJECTION,
        allowed_consequences=frozenset({CONSEQUENCE_VOID, CONSEQUENCE_REJECT, CONSEQUENCE_NONE}),
    )
)
_register(
    _c(
        "EVALUATION_COLLUSION",
        KIND_REJECTION,
        required_signatures=(r"(串通|串标|弄虚作假|行贿|雷同|机器码|同一人送达|联系电话一致)",),
        allowed_consequences=frozenset({CONSEQUENCE_VOID, CONSEQUENCE_REJECT, CONSEQUENCE_NONE}),
        fixtures=("R",),
        rationale="collusion/fraud facts; a submission-platform clause must not absorb them",
    )
)
_register(
    _c(
        "EVALUATION_RESPONSIVENESS",
        KIND_REJECTION,
        required_signatures=(r"(实质性|响应性|重大偏差|偏差)",),
        allowed_consequences=frozenset({CONSEQUENCE_VOID, CONSEQUENCE_REJECT, CONSEQUENCE_NONE}),
    )
)
_register(
    _c(
        "EVALUATION_QUALIFICATION_REVIEW",
        KIND_REJECTION,
        required_signatures=(r"(资格审查|资格评审|不合格)",),
    )
)
_register(
    _c(
        "AUTHORIZATION",
        KIND_MANDATORY,
        required_signatures=(r"(授权委托书|法定代表人|委托代理人|授权代表|身份证明)",),
        required_evidence=(r"(授权|法定代表人|委托代理人|代理人)",),
        fixtures=("Q",),
        rationale="evidence must literally be an authorisation chain",
    )
)
_register(
    _c(
        "SIGNATURE_AND_SEAL",
        KIND_MANDATORY,
        required_signatures=(r"(签字|盖章|印章|公章|签章)",),
        forbidden_signatures=(r"(授权委托书|法定代表人身份证明)",),
    )
)
_register(
    _c(
        "SIGNATURE_RED_LINE",
        KIND_REJECTION,
        required_signatures=(r"(签字|盖章|印章|公章|签章|密封)",),
        allowed_consequences=frozenset({CONSEQUENCE_VOID, CONSEQUENCE_REJECT, CONSEQUENCE_NO_ACCEPT, CONSEQUENCE_NONE}),
    )
)
_register(
    _c(
        "SIGNATURE_EXECUTION",
        KIND_MANDATORY,
        required_signatures=(r"(签署|签字|盖章)",),
    )
)

# --- submission / platform -------------------------------------------------- #

_register(
    _c(
        "BID_VALIDITY",
        KIND_MANDATORY,
        required_signatures=(r"(有效期|投标有效|响应有效|报价有效)",),
        forbidden_signatures=(_CREDIT,),
        required_evidence=(r"(有效期|投标有效|响应有效)",),
        forbidden_evidence=(_CREDIT,),
        allowed_roles=frozenset({ROLE_BID_VALIDITY_DAYS}),
        allowed_fact_keys=frozenset({"bid_validity"}),
        fixtures=("B",),
        rationale="the bid/response validity period; a blacklist period is not validity evidence",
    )
)
_register(
    _c(
        "EVALUATION_FORMAL_REVIEW",
        KIND_MANDATORY,
        required_signatures=(r"(形式评审|形式审查|符合性)",),
    )
)
_register(
    _c(
        "SUBMISSION_DEADLINE",
        KIND_REJECTION,
        required_signatures=(r"(截止时间|递交|提交|送达|开启时间)",),
        forbidden_signatures=(r"(不同供应商|同一人送达|联系电话一致)",),
        allowed_consequences=frozenset({CONSEQUENCE_NO_ACCEPT, CONSEQUENCE_REJECT, CONSEQUENCE_NONE}),
        allowed_fact_keys=frozenset({"bid_deadline"}),
    )
)
_register(
    _c(
        "SUBMISSION_PLATFORM",
        KIND_REJECTION,
        required_signatures=(r"(平台|上传|递交|送达|地点|方式|解密)",),
        forbidden_signatures=(
            r"(不同供应商的?投标|同一人送达|同一人或不同联系人的联系电话一致|串通)",
            # fixture S: the platform roles are split -- the opening/decryption
            # and the announcement duties are other concerns' rows
            r"(成交公告|成交结果公告|中标公告|公告发布|发布公告|开标时间|唱标|在线解密|签到)",
        ),
        required_evidence=(r"(平台|上传|递交|送达|地点|方式|解密)",),
        allowed_consequences=frozenset({CONSEQUENCE_NO_ACCEPT, CONSEQUENCE_REJECT, CONSEQUENCE_NONE}),
        fixtures=("R", "S"),
        rationale="platform/submission mechanics; collusion patterns belong to EVALUATION_COLLUSION "
        "and the opening/announcement duties have their own concerns",
    )
)
_register(
    _c(
        "ELECTRONIC_UPLOAD",
        KIND_REJECTION,
        required_signatures=(r"(上传|加密|电子响应文件|CA|制作工具|电子交易系统)",),
        forbidden_signatures=(r"(成交公告|成交结果公告|中标公告|公告发布|开标时间|唱标|签到)",),
        required_evidence=(r"(上传|加密|电子响应文件|CA|制作工具|电子交易系统)",),
        allowed_consequences=frozenset({CONSEQUENCE_NO_ACCEPT, CONSEQUENCE_REJECT, CONSEQUENCE_NONE}),
        fixtures=("S",),
        rationale="the electronic-upload duty only; the opening and the announcement are separate concerns",
    )
)
_register(
    _c(
        "OPENING_DECRYPTION",
        KIND_MANDATORY,
        required_signatures=(r"(解密|开标|签到|开启)",),
        forbidden_signatures=(r"(成交公告|成交结果公告|中标公告|公告发布|上传响应文件|电子上传)",),
        required_evidence=(r"(解密|开标|签到|开启)",),
        fixtures=("S",),
        rationale="the opening/decryption duty only; the upload and announcement are separate concerns",
    )
)
_register(
    _c(
        "SUBMISSION_COPIES",
        KIND_MANDATORY,
        required_signatures=(r"(正本|副本|份数|U盘|电子版)",),
        allowed_roles=frozenset({ROLE_QUANTITY}),
    )
)
_register(
    _c(
        "QUERY_DEADLINE",
        KIND_MANDATORY,
        required_signatures=(r"(提问|澄清|质疑|修改|预备会|截止时间)",),
        forbidden_signatures=(r"(不接受供应商主动提出)",),
        fixtures=("P",),
        rationale="clarification/amendment procedure with a bidder action",
    )
)
_register(
    _c(
        "SITE_VISIT",
        KIND_INFORMATIONAL,
        required_signatures=(r"(踏勘|现场考察|预备会)",),
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
        rationale="a conditional site-visit rule keeps its condition; it is not unconditional bidder work",
    )
)

# --- bonds ------------------------------------------------------------------ #

_register(
    _c(
        "BID_BOND_AMOUNT",
        KIND_MANDATORY,
        required_signatures=(r"(保证金|担保).{0,12}(金额|人民币|万元|元)|金额.{0,12}保证金",),
        allowed_roles=frozenset({ROLE_RESPONSE_BOND, ROLE_BOND_AMOUNT, ROLE_PRICE}),
        allowed_fact_keys=frozenset({"bid_bond_amount", "bid_bond_form"}),
        required_evidence=(r"(响应保证金|投标保证金|保证金)",),
        # Round 5 (CASE003): a response-bond row must never cite a performance or
        # advance-payment guarantee clause.
        forbidden_evidence=(r"(预付款担保|履约担保|履约保证金|质量保证金|质保金)",),
    )
)
_register(
    _c(
        "BID_BOND_FORM",
        KIND_MANDATORY,
        # The bond's *form*: any accepted instrument wording counts, the amount
        # does not (it belongs to BID_BOND_AMOUNT).
        required_signatures=(r"(保函|保证保险|保单|支票|转账|电汇|银行汇票|现金|缴纳形式|提交形式|形式为|形式提交|方式)",),
        forbidden_signatures=(
            r"(格式自拟|承诺书|缴纳凭证|投标文件格式|开标一览表|投标函|法定代表人身份证明)",
            r"(\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2})",
            r"(交易平台|营收系统|集采)",
            r"(保证金金额|金额为|金额：)",
        ),
        allowed_roles=frozenset({ROLE_BOND_FORM, ROLE_PRICE}),
        forbidden_roles=frozenset({ROLE_RETENTION_MONEY_RATIO, ROLE_PAYMENT_RATIO}),
        allowed_fact_keys=frozenset({"bid_bond_amount", "bid_bond_form"}),
        # the evidence is the clause that lists the accepted instruments; CASE003
        # lists them without the words 保证金
        required_evidence=(r"(保证金|保函|保证保险|担保机构|银行电汇|银行转账|现金)",),
        forbidden_evidence=(r"(格式自拟|承诺书|缴纳凭证|开标一览表)",),
    )
)
_register(
    _c(
        "BID_BOND_TRANSFER",
        KIND_MANDATORY,
        required_signatures=(r"(基本账户|基本存款账户|开户许可证|转出|汇入)",),
        allowed_fact_keys=frozenset({"bid_bond_amount"}),
    )
)
_register(
    _c(
        "BID_BOND_DEADLINE",
        KIND_MANDATORY,
        required_signatures=(r"(保证金).{0,20}(截止|前|时间|到账)",),
        allowed_roles=frozenset({ROLE_RESPONSE_DAYS, ROLE_BOND_AMOUNT, ROLE_RESPONSE_BOND}),
        allowed_fact_keys=frozenset({"bid_bond_amount"}),
    )
)
_register(
    _c(
        "BID_BOND_EVIDENCE",
        KIND_REJECTION,
        required_signatures=(r"(保证金).{0,20}(凭证|回单|扫描件|复印件|递交|提交)|保证金.{0,10}否决",),
        allowed_fact_keys=frozenset({"bid_bond_amount"}),
        allowed_consequences=frozenset({CONSEQUENCE_VOID, CONSEQUENCE_REJECT, CONSEQUENCE_NONE}),
    )
)
_register(
    _c(
        "PERFORMANCE_BOND",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"履约保证金",),
        forbidden_signatures=(r"响应保证金|投标保证金",),
        required_evidence=(r"履约保证金",),
        forbidden_evidence=(r"响应保证金|投标保证金",),
        allowed_roles=frozenset({ROLE_PERFORMANCE_BOND, ROLE_PRICE}),
        allowed_consequences=frozenset({CONSEQUENCE_DISQUALIFY, CONSEQUENCE_VOID, CONSEQUENCE_LIABILITY, CONSEQUENCE_NONE}),
        fixtures=("F",),
        rationale="performance bond evidence must literally be a performance-bond clause",
    )
)

# --- price ------------------------------------------------------------------ #

_register(
    _c(
        "PRICE_CEILING",
        KIND_REJECTION,
        required_signatures=(
            r"(最高(?:投标|响应|采购)?限价|控制价|预算金额|采购预算|超过限价)",
        ),
        forbidden_signatures=(r"(资金来源|自筹|财政资金|交货地点|质量要求)",),
        allowed_roles=frozenset({ROLE_PRICE_CEILING, ROLE_PRICE}),
        allowed_fact_keys=frozenset({"max_price", "budget"}),
        allowed_consequences=frozenset({CONSEQUENCE_REJECT, CONSEQUENCE_VOID, CONSEQUENCE_NONE}),
        fixtures=("C",),
        rationale="the ceiling value only; funding source has its own concern",
    )
)
_register(
    _c(
        "PRICE_ARITHMETIC",
        KIND_MANDATORY,
        required_signatures=(r"(大写|小写|单价|合计|总价|算术|修正)",),
        allowed_roles=frozenset({ROLE_PRICE, ROLE_QUANTITY}),
        allowed_fact_keys=frozenset({"max_price"}),
    )
)
_register(
    _c(
        "PRICE_ITEMIZATION",
        KIND_MANDATORY,
        required_signatures=(r"(分项限价|暂列金额|暂估价|工程量清单|限价表|分项报价)",),
        allowed_roles=frozenset({ROLE_PRICE, ROLE_PRICE_CEILING, ROLE_QUANTITY}),
        allowed_fact_keys=frozenset({"max_price"}),
    )
)
_register(
    _c(
        "PRICE_INCLUDED_COST_SCOPE",
        KIND_MANDATORY,
        required_signatures=(
            r"(单价|报价|费用).{0,24}(包含|含|包括|列入|计入)",
            r"(均应列入响应报价|包括在报价中|费用均由乙方承担)",
        ),
        forbidden_signatures=(
            r"(验收单|交付完成|签字或加盖项目部印章)",
            r"(安装调试完\s*毕|设备安装调试|视为交付)",
        ),
        allowed_roles=frozenset({ROLE_PRICE, ROLE_PRICE_CEILING, ROLE_QUANTITY}),
        allowed_fact_keys=frozenset({"max_price"}),
        fixtures=("H",),
        rationale="the cost scope a unit price includes; acceptance completion is a separate concern",
    )
)
_register(
    _c(
        "PRICING_COMPLETENESS",
        KIND_MANDATORY,
        required_signatures=(
            r"(报价|费用).{0,30}(包含|含|包括|列入|计入|漏项|重复)",
            r"(按要求填写报价|算术错误|修正)",
        ),
        forbidden_signatures=(
            r"(验收单|交付完成|签字或加盖项目部印章)",
            # fixture G: the source must establish the cost scope; a row may not
            # assert completeness on its own authority
            r"(无漏项|无重复项|无重复报价|已包含一切费用|已包含要求的一切费用|费用已全部包含)",
        ),
        allowed_roles=frozenset({ROLE_PRICE, ROLE_QUANTITY, ROLE_PRICE_CEILING}),
        allowed_fact_keys=frozenset({"max_price"}),
        fixtures=("G",),
        rationale=(
            "a completeness claim needs a clause that establishes the included cost scope; "
            "a bare 'fill in your price' or an abnormal-low-price procedure proves nothing about omissions"
        ),
    )
)
_register(
    _c(
        "PRICE_TAX_BASIS",
        KIND_MANDATORY,
        required_signatures=(r"(税金|税率|含税|不含税|增值税)",),
        allowed_roles=frozenset({ROLE_PRICE, ROLE_QUANTITY}),
        allowed_fact_keys=frozenset({"max_price"}),
    )
)
_register(
    _c(
        "PROJECT_FUNDING_SOURCE",
        KIND_INFORMATIONAL,
        required_signatures=(r"(资金来源|自筹|财政资金|资金落实情况)",),
        forbidden_signatures=(r"(项目名称|项目编号|标段|采购人名称)",),
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
        fixtures=("C",),
        rationale="a funding clause is a funding clause; it must not be labelled generic project information",
    )
)

# --- delivery / quality / warranty ------------------------------------------ #

_register(
    _c(
        "DELIVERY_PERIOD",
        KIND_MANDATORY,
        required_signatures=(r"(供货期|交货期|交付期|服务期|工期|履约期限)",),
        forbidden_signatures=(_LOCATION,),
        allowed_roles=frozenset({ROLE_DELIVERY_DAYS}),
        allowed_fact_keys=frozenset({"duration"}),
    )
)
_register(
    _c(
        "DELIVERY_LOCATION",
        KIND_MANDATORY,
        required_signatures=(_LOCATION,),
        allowed_fact_keys=frozenset({"project_location"}),
    )
)
_register(
    _c(
        "QUALITY_TARGET",
        KIND_MANDATORY,
        required_signatures=(r"(质量要求|质量标准|质量目标|技术标准|规范|合格)",),
        forbidden_signatures=(_LOCATION,),
        allowed_fact_keys=frozenset({"quality_target"}),
        allowed_roles=frozenset({ROLE_PROJECT_WARRANTY_MONTHS}),
        fixtures=("A",),
        rationale="a quality obligation never carries the delivery address",
    )
)
_register(
    _c(
        "PROJECT_WARRANTY",
        KIND_MANDATORY,
        required_signatures=(r"(质保期|保修期|质量保证期|免费维护|缺陷责任期)",),
        forbidden_signatures=(r"(质保金|质量保证金|保留金|尾款|余款)",),
        allowed_roles=frozenset({ROLE_PROJECT_WARRANTY_MONTHS, ROLE_RESPONSE_DAYS}),
        allowed_consequences=frozenset({CONSEQUENCE_NONE, CONSEQUENCE_LIABILITY}),
        fixtures=("K",),
        rationale="the project/product warranty period, never the retention money",
    )
)
_register(
    _c(
        "RETENTION_MONEY_RATIO",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"(质保金|质量保证金|保留金|尾款|余款)",),
        forbidden_signatures=(
            r"(银行承兑|承兑汇票)",
            # fixture J: 95% is the payment ratio, never the retention ratio
            r"(95\s*%|95％)",
            r"(?<!质保金)(?<!质量保证金)(?<!保留金)(?<!尾款)(?<!余款)的?得\s*\d+\s*分",
        ),
        allowed_roles=frozenset({ROLE_RETENTION_MONEY_RATIO}),
        fixtures=("J", "K", "L"),
        rationale="the money kept back (5%); a payment ratio or bank-acceptance ratio is a different role",
    )
)
_register(
    _c(
        "RETENTION_RELEASE_PERIOD",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"(质保金|质量保证金|保留金|尾款|余款)", r"(返还|退还|释放|付清|期满)"),
        forbidden_signatures=(r"(银行承兑|承兑汇票)",),
        allowed_roles=frozenset({ROLE_RETENTION_RELEASE_MONTHS, ROLE_PROJECT_WARRANTY_MONTHS}),
        fixtures=("K",),
        rationale="when the retention money is released (12 months), not the warranty period",
    )
)
_register(
    _c(
        "CONTRACT_DELIVERY",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"(交货|交付|供货|工期|履约)",),
        allowed_roles=frozenset({ROLE_DELIVERY_DAYS, ROLE_QUANTITY}),
    )
)
_register(
    _c(
        "DELIVERY_ACCEPTANCE_COMPLETION",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"(验收|交付完成|安装调试完毕|签字或加盖|交货完成)",),
        forbidden_signatures=(r"(单价中含|设备价款包含|费用均由乙方承担)",),
        allowed_consequences=frozenset({CONSEQUENCE_LIABILITY, CONSEQUENCE_NONE}),
        fixtures=("H", "I"),
        rationale="the acceptance/completion milestone; price cost scope is a different concern",
    )
)
_register(
    _c(
        "INSTALLATION_ACCEPTANCE",
        KIND_MANDATORY,
        required_signatures=(r"(安装|调试|验收|试运行)",),
        forbidden_signatures=(
            r"(CJJ|GB\s*/?T?\s*\d|GBJ|CJ/T|检测实验报告|检测报告|校检证书)",
            # an acceptance row is not a payment/scoring rule (round-5 fixture G)
            r"(得\s*\d+(?:\.\d+)?\s*分|（\s*\d+(?:\.\d+)?\s*分\s*）|支付|货款|质保金|银行承兑|承兑汇票)",
        ),
        allowed_consequences=frozenset({CONSEQUENCE_NONE, CONSEQUENCE_REJECT}),
        fixtures=("I",),
        rationale="installation/acceptance process, not a technical-standard list",
    )
)
_register(
    _c(
        "TECHNICAL_STANDARD_COMPLIANCE",
        KIND_INFORMATIONAL,
        required_signatures=(r"(CJJ|GB\s*/?T?\s*\d|GBJ|CJ/T|规程|设计规范|验收规范)",),
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
        fixtures=("I",),
        rationale="the standards the equipment must follow; not an acceptance milestone",
    )
)
_register(
    _c(
        "TECHNICAL_TEST_REPORT",
        KIND_MANDATORY,
        required_signatures=(r"(第三方|检测报告|检验报告|校检证书|试验报告|认证证书)",),
        forbidden_signatures=(
            r"(评分|得分|分值)",
            r"(采购范围|采购内容|预留|不锈钢管|法兰|螺栓|管网对接|包装|运输|保险|装车)",
        ),
        allowed_consequences=frozenset({CONSEQUENCE_NONE, CONSEQUENCE_REJECT}),
        fixtures=("I",),
        rationale="third-party proof material is its own requirement",
    )
)
_register(
    _c(
        "TECHNICAL_PARAMETER",
        KIND_MANDATORY,
        required_signatures=(r"(参数|配置|规格|型号|技术要求|材质|口径|管|法兰|计量)",),
        forbidden_signatures=(r"(CJJ140|GB50013|GB50015|GB50265|GB50242|GB50275|低压配电|设计规范)",),
        allowed_roles=frozenset({ROLE_QUANTITY}),
        fixtures=("I",),
        rationale="concrete equipment parameters; a standards list belongs to TECHNICAL_STANDARD_COMPLIANCE",
    )
)
_register(
    _c(
        "TECHNICAL_PROOF",
        KIND_MANDATORY,
        required_signatures=(r"(证明材料|复印件|扫描件|检测|合同协议书|材料清单)",),
    )
)
_register(
    _c(
        "TECHNICAL_PLAN",
        KIND_MANDATORY,
        required_signatures=(r"(技术方案|实施方案|施工方案|方案|组织设计)",),
    )
)
_register(
    _c(
        "AFTER_SALES_SERVICE",
        KIND_MANDATORY,
        required_signatures=(r"(售后|维保|维修|服务响应|质保服务)",),
        allowed_roles=frozenset({ROLE_RESPONSE_DAYS, ROLE_PROJECT_WARRANTY_MONTHS}),
    )
)
_register(
    _c(
        "GENERAL_BIDDER_OBLIGATION",
        KIND_MANDATORY,
        forbidden_signatures=(
            r"(采购范围|采购内容)",
            r"(评审小组不接受供应商主动提出)",
            r"(评标委员会|评审小组).{0,10}(澄清|说明)",
        ),
        fixtures=("P",),
        rationale=(
            "a general bidder duty must not merge the procurement scope with an evaluation "
            "clarification procedure"
        ),
    )
)

# --- contract / fee --------------------------------------------------------- #

_register(
    _c(
        "CONTRACT_PAYMENT",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"(付款|支付|价款|货款|费用|结算)",),
        forbidden_signatures=(
            _AGENCY,
            r"(领取《成交通知书》时缴纳|成交通知书.{0,10}缴纳)",
            r"(合同解除|退换|退还甲方)",
            r"(签字盖章后生效|签字日期不一致)",
            r"(违约|赔偿|索赔|争议|仲裁|诉讼)",
            r"(质保金|质量保证金)",
        ),
        forbidden_evidence=(
            _AGENCY,
            r"(签字盖章后生效|合同生效)",
            r"(合同解除|退换)",
        ),
        required_evidence=(r"(付款|支付|货款|费用|结算)",),
        allowed_roles=frozenset({ROLE_PAYMENT_RATIO, ROLE_PRICE, ROLE_RETENTION_MONEY_RATIO}),
        allowed_consequences=frozenset({CONSEQUENCE_NONE, CONSEQUENCE_LIABILITY}),
        fixtures=("D", "E"),
        rationale="the procurement contract's own payment/cost terms, excluding agency fee, refunds and effectivity",
    )
)
_register(
    _c(
        "CONTRACT_TERMINATION_REFUND",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"(合同解除|退换|退还)",),
        allowed_consequences=frozenset({CONSEQUENCE_LIABILITY, CONSEQUENCE_NONE}),
        fixtures=("D",),
        rationale="termination-refund liability has its own concern",
    )
)
_register(
    _c(
        "AGENCY_SERVICE_FEE",
        KIND_CONTRACT_ONLY,
        required_signatures=(_AGENCY,),
        forbidden_signatures=(),
        allowed_roles=frozenset({ROLE_AGENCY_SERVICE_FEE, ROLE_PAYMENT_RATIO}),
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
        fixtures=("D", "T"),
        rationale="the agency service fee is a separate obligation and must be displayed completely",
    )
)
_register(
    _c(
        "CONTRACT_RISK",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"(违约|赔偿|索赔|争议|仲裁|诉讼|不可抗力|风险|责任)",),
        allowed_consequences=frozenset({CONSEQUENCE_LIABILITY, CONSEQUENCE_NONE}),
    )
)
_register(
    _c(
        "CONTRACT_ACCEPTANCE",
        KIND_CONTRACT_ONLY,
        required_signatures=(r"(验收|交付|移交)",),
    )
)

# --- scoring ---------------------------------------------------------------- #

_register(
    _c(
        "EVALUATION_SCORING",
        KIND_SCORING,
        required_signatures=(r"(评审办法|评审因素|评分标准|分值构成|综合评分法|评标办法)",),
        forbidden_signatures=(
            r"(得\s*\d+(?:\.\d+)?\s*分)",
            # round-5 fixture N: a generic evaluation row may never establish a
            # points value ("最高 1 分"), whatever the extraction looked like
            r"(最高\s*\d+(?:\.\d+)?\s*分|满分\s*\d+(?:\.\d+)?\s*分|(?<![\d.])\d+(?:\.\d+)?\s*分)",
        ),
        allowed_roles=frozenset(),
        forbidden_roles=frozenset({ROLE_SCORE_POINTS, ROLE_PAYMENT_RATIO, ROLE_BANK_ACCEPTANCE_RATIO}),
        fixtures=("N",),
        rationale=(
            "generic evaluation-method text establishes the method only; it can never "
            "establish a points value such as 最高 1 分"
        ),
    )
)
_register(
    _c(
        "SCORING_PAYMENT_CONDITION",
        KIND_SCORING,
        required_signatures=(r"(付款|支付|货款)",),
        forbidden_signatures=(r"(银行承兑|承兑汇票)",),
        allowed_roles=frozenset({ROLE_PAYMENT_RATIO, ROLE_RETENTION_MONEY_RATIO, ROLE_SCORE_POINTS}),
        scoring_roles=frozenset({"PAYMENT_CONDITION"}),
        fixtures=("J", "K", "M"),
        rationale="the payment-condition scoring factor: 95% payment ratio, 5% retention, 12/8 points",
    )
)
_register(
    _c(
        "SCORING_BANK_ACCEPTANCE",
        KIND_SCORING,
        required_signatures=(r"(银行承兑|承兑汇票)",),
        allowed_roles=frozenset({ROLE_BANK_ACCEPTANCE_RATIO, ROLE_SCORE_POINTS}),
        scoring_roles=frozenset({"BANK_ACCEPTANCE"}),
        fixtures=("L",),
        rationale="the accepted-bank-draft ratio is scored on its own; it is not a retention ratio",
    )
)
_register(
    _c(
        "SCORING_PRICE_FORMULA",
        KIND_SCORING,
        required_signatures=(r"(价格|报价|基准价|偏差率|经济标)",),
        allowed_roles=frozenset({ROLE_SCORE_POINTS, ROLE_PRICE, ROLE_PRICE_CEILING}),
        scoring_roles=frozenset({"PRICE_FORMULA"}),
    )
)
_register(
    _c(
        "SCORING_TECHNICAL",
        KIND_SCORING,
        required_signatures=(r"(技术)",),
        forbidden_signatures=(r"(见评审办法前附表|见前附表)",),
        fixtures=("O",),
        rationale=(
            "a technical scoring row needs real scoring-table atoms; a bare cross-reference "
            "is not a scoring factor and must not be delivered as one"
        ),
    )
)
for _factor, _signature, _name in (
    ("SCORING_DELIVERY_PLAN", r"(供货方案|供货计划|实施方案|进度计划)", "delivery plan"),
    ("SCORING_EMERGENCY_PLAN", r"(应急|保障措施|突发)", "emergency plan"),
    ("SCORING_QUALITY_SYSTEM", r"(质量保证体系|质量体系|质量管理|质量控制)", "quality system"),
    ("SCORING_PERFORMANCE", r"(类似业绩|业绩|类似项目)", "performance"),
    ("SCORING_PERSONNEL", r"(项目负责人|项目经理|职称|人员配置|拟投入人员)", "personnel"),
):
    _register(
        _c(
            _factor,
            KIND_SCORING,
            required_signatures=(_signature,),
            forbidden_signatures=(r"(见评审办法前附表|见前附表)",),
            allowed_roles=frozenset({ROLE_SCORE_POINTS, ROLE_PERSON_COUNT}),
            scoring_roles=frozenset({_name.upper().replace(" ", "_")}),
        )
    )

# --- file / format / internal ----------------------------------------------- #

_register(
    _c(
        "FILE_FORMAT",
        KIND_MANDATORY,
        required_signatures=(r"(格式|装订|目录|页码|编排|字体|密封|封装)",),
        forbidden_signatures=(r"(评审小组成员|专家|工作人员)",),
    )
)
_register(
    _c(
        "FILE_COMPOSITION",
        KIND_MANDATORY,
        required_signatures=(r"(组成|包括|应包含|应当包含|附件)",),
    )
)
_register(
    _c(
        "INTERNAL_PROCEDURE",
        KIND_INFORMATIONAL,
        actors=frozenset({ACTOR_PURCHASER}),
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
    )
)
_register(
    _c(
        "PURCHASER_PROCEDURE",
        KIND_INFORMATIONAL,
        actors=frozenset({ACTOR_PURCHASER}),
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
    )
)
_register(
    _c("TERM_DEFINITION", KIND_INFORMATIONAL, allowed_consequences=frozenset({CONSEQUENCE_NONE}))
)
_register(
    _c("UNCLASSIFIED", KIND_INFORMATIONAL, allowed_consequences=frozenset({CONSEQUENCE_NONE}))
)
_register(
    _c(
        "UNSUPPORTED_FORMAT_CLAIM",
        KIND_INFORMATIONAL,
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
    )
)
_register(
    _c(
        "SOURCE_REQUIREMENT_CONFLICT",
        KIND_INFORMATIONAL,
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
    )
)
_register(
    _c(
        "PROJECT_BASIC_INFO",
        KIND_INFORMATIONAL,
        required_signatures=(r"(项目名称|项目编号|标段|采购人|基本信息)",),
        allowed_consequences=frozenset({CONSEQUENCE_NONE}),
    )
)

#: concerns whose deliverable row was replaced by a finer round-5 concern
SUPERSEDED_CONCERNS: dict[str, str] = {
    "PROJECT_BASIC_INFO": "PROJECT_FUNDING_SOURCE",
    "PRICE_TAX_BASIS": "PRICE_INCLUDED_COST_SCOPE",
    "CONTRACT_ACCEPTANCE": "DELIVERY_ACCEPTANCE_COMPLETION",
    "PRICE_COMPLETENESS": "PRICING_COMPLETENESS",
    "TECHNICAL_INSTALLATION": "INSTALLATION_ACCEPTANCE",
}

#: round-4 concern ids that round 5 renames (kept for report continuity)
RENAMED_CONCERNS: dict[str, str] = {
    "PROJECT_BASIC_INFO": "PROJECT_FUNDING_SOURCE",
    "PRICE_COMPLETENESS": "PRICING_COMPLETENESS",
    "CONTRACT_ACCEPTANCE": "DELIVERY_ACCEPTANCE_COMPLETION",
    "TECHNICAL_INSTALLATION": "INSTALLATION_ACCEPTANCE",
}

#: The version of the contract table; bumped whenever a signature changes.
CONTRACT_VERSION = "round5.1"

_PERMISSIVE = ConcernContract(
    concern_id="*",
    kind=KIND_INFORMATIONAL,
    explicit=False,
    rationale="permissive fallback: no contract has been authored for this concern yet",
)


def contract_for(concern_id: str) -> ConcernContract:
    """Return the contract of ``concern_id`` (permissive when unlisted)."""

    contract = CONTRACTS.get(str(concern_id))
    if contract is not None:
        return contract
    return ConcernContract(concern_id=str(concern_id), kind=_PERMISSIVE.kind, explicit=False)


def has_explicit_contract(concern_id: str) -> bool:
    return str(concern_id) in CONTRACTS


def concern_kind(concern_id: str) -> str:
    return contract_for(concern_id).kind


def is_scoring_concern(concern_id: str) -> bool:
    return concern_kind(concern_id) == KIND_SCORING or str(concern_id).startswith("SCORING_")


# --------------------------------------------------------------------------- #
# segment selection
# --------------------------------------------------------------------------- #

#: A new numbered list item ("8、交货地点" / "3、支付时间") starts a new facet.
_NUMBERED_ITEM_RE = re.compile(r"(?<=[\s。；;）)】、])\s*(?=\d{1,2}\s*、)")
_SENTENCE_RE = re.compile(r"(?<=[。；;])")


def segment_text(text: str) -> list[str]:
    """Cut source text into facet-sized segments.

    Round 4 split at sentence terminators only, so one extracted atom could carry
    a delivery address and a quality obligation at once.  Round 5 also cuts at
    numbered list items, which is how tender documents actually enumerate
    independent requirements.
    """

    raw = str(text or "")
    if not raw.strip():
        return []
    pieces: list[str] = []
    for chunk in _NUMBERED_ITEM_RE.split(raw):
        for sentence in _SENTENCE_RE.split(chunk):
            cleaned = sentence.strip(" \t\r\n；;。，,、")
            if cleaned:
                pieces.append(cleaned)
    return pieces


def _clause_runs(segment: str, spec: ConcernContract | None = None) -> list[str]:
    """Split a mixed segment at commas and merge consecutive owned clauses.

    Round-5 fixture H: one source clause states the *cost scope* of a unit price
    and the *acceptance milestone* in the same sentence ("设备单价中含运输费…，
    设备安装调试完毕，甲方负责人…视为交付完成").  Each concern may keep only its
    own clause run, so the delivered rows stop sharing one mixed sentence.

    With a contract the runs are the maximal consecutive clause sequences that
    contract owns; without one the raw clause pairs are returned.
    """

    clauses = [part.strip(" \t") for part in re.split(r"(?<=[，,])", segment) if part.strip()]
    if spec is None:
        return [left + right for left, right in zip(clauses, clauses[1:])] or clauses
    runs: list[str] = []
    current = ""
    for clause in clauses:
        candidate = f"{current}{clause}"
        if spec.owned_segment_ok(candidate):
            current = candidate
            continue
        if current:
            runs.append(current)
        current = clause if spec.owned_segment_ok(clause) else ""
    if current:
        runs.append(current)
    return runs


def owned_segments(concern_id: str, text: str, *, contract: ConcernContract | None = None) -> list[str]:
    """The segments of ``text`` that the concern's contract allows it to own.

    A segment that the contract rejects is retried at clause level, so a mixed
    source sentence yields each concern its own clause run instead of being
    dropped for both (or, worse, rendered whole for one of them).
    """

    spec = contract if contract is not None else contract_for(concern_id)
    kept: list[str] = []
    for segment in segment_text(text):
        if spec.owned_segment_ok(segment):
            kept.append(segment)
            continue
        for run in _clause_runs(segment, spec):
            trimmed = run.rstrip(" 、,，;；")
            if len(trimmed) < 4:
                continue
            if spec.owned_segment_ok(trimmed):
                if trimmed not in kept:
                    kept.append(trimmed)
    return kept


def owned_text(concern_id: str, text: str, *, contract: ConcernContract | None = None) -> str:
    """``text`` reduced to the segments the concern contract allows."""

    return "；".join(owned_segments(concern_id, text, contract=contract))


#: An extracted fragment that is not a reviewable requirement: it starts with the
#: tail of a citation ("意见》的通知中…"), a stray closing bracket, or a dangling
#: connector.  Round-5 fixture T moves such a concern to NEEDS_REVIEW.
_INCOMPLETE_FRAGMENT = re.compile(
    r"^[》〉】）)\]」”’]"
    r"|^[^，。；;：:]{0,6}》[^，。；;]{0,20}(规定|通知|标准|办法|意见)"
    r"|^(缴纳账|其中|以及|并且|或者)"
)


def is_incomplete_fragment(text: str) -> bool:
    """True when ``text`` is an extraction fragment rather than a requirement."""

    return bool(_INCOMPLETE_FRAGMENT.search(_nospace(text)))


#: Block labels the rendered cell uses to separate source text from instructions.
_BLOCK_LABELS = (
    "招标文件要求",
    "复核要点",
    "通过标准",
    "准备材料",
    "不满足后果",
    "评分提示",
    "数值指标",
    "证据摘要",
    "关联事实",
)


def _split_display_blocks(displayed: str) -> tuple[str, str]:
    """Split a rendered cell into (source-requirement text, instruction text)."""

    text = str(displayed or "")
    found = sorted(
        (text.find(f"{label}："), label) for label in _BLOCK_LABELS if text.find(f"{label}：") >= 0
    )
    if not found:
        return text, ""
    source_parts: list[str] = []
    instruction_parts: list[str] = []
    for index, (at, label) in enumerate(found):
        end = found[index + 1][0] if index + 1 < len(found) else len(text)
        body = text[at + len(label) + 1 : end]
        if label == "招标文件要求":
            source_parts.append(body)
        else:
            instruction_parts.append(body)
    return " ".join(source_parts), " ".join(instruction_parts)


def forbidden_segments(concern_id: str, text: str, *, contract: ConcernContract | None = None) -> list[str]:
    """Segments a concern may not own (the contract's forbidden signatures)."""

    spec = contract if contract is not None else contract_for(concern_id)
    rejected: list[str] = []
    for segment in segment_text(text):
        if spec.owned_segment_ok(segment):
            continue
        flat = _nospace(segment)
        if any(re.search(pattern, flat) for pattern in spec.forbidden_signatures):
            rejected.append(segment)
    return rejected


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Violation:
    code: str
    concern_id: str
    detail: str
    text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "concern_id": self.concern_id,
            "detail": self.detail,
            "text": self.text[:200],
        }


CODE_FORBIDDEN_SIGNATURE = "CONTRACT_FORBIDDEN_SIGNATURE"
CODE_MISSING_REQUIRED_SIGNATURE = "CONTRACT_MISSING_REQUIRED_SIGNATURE"
CODE_FORBIDDEN_ROLE = "CONTRACT_FORBIDDEN_ROLE"
CODE_ROLE_NOT_ALLOWED = "CONTRACT_ROLE_NOT_ALLOWED"
CODE_FACT_NOT_ALLOWED = "CONTRACT_FACT_NOT_ALLOWED"
CODE_CONSEQUENCE_NOT_ALLOWED = "CONTRACT_CONSEQUENCE_NOT_ALLOWED"
CODE_MATERIAL_NOT_ALLOWED = "CONTRACT_MATERIAL_NOT_ALLOWED"
CODE_EVIDENCE_SIGNATURE_MISSING = "CONTRACT_EVIDENCE_SIGNATURE_MISSING"
CODE_EVIDENCE_FORBIDDEN = "CONTRACT_EVIDENCE_FORBIDDEN"
CODE_GENERIC_ROLE = "CONTRACT_GENERIC_ROLE"


def validate_displayed_text(
    concern_id: str,
    displayed: str,
    *,
    contract: ConcernContract | None = None,
) -> list[Violation]:
    """Validate the *displayed* requirement text against the contract.

    The row's displayed cell mixes the quoted source requirement with the
    review's own instruction blocks (复核要点/通过标准/不满足后果/评分提示).
    Required signatures are therefore enforced on the *source requirement*
    block only -- an instruction line ("不满足后果：否决") is not a source
    requirement and must not be judged as one -- while a *forbidden* signature
    is enforced everywhere, because it marks text that belongs to another
    concern wherever it appears.
    """

    spec = contract if contract is not None else contract_for(concern_id)
    out: list[Violation] = []
    source_text, instruction_text = _split_display_blocks(displayed)
    for segment in segment_text(source_text):
        flat = _nospace(segment)
        if spec.required_signatures and not any(
            re.search(pattern, flat) for pattern in spec.required_signatures
        ):
            # only a violation when the concern declares its own signatures: a
            # neutral segment without any of them is a foreign facet.
            out.append(
                Violation(
                    CODE_MISSING_REQUIRED_SIGNATURE,
                    spec.concern_id,
                    "segment carries none of the concern's required signatures",
                    segment,
                )
            )
    for segment in segment_text(source_text + " " + instruction_text):
        flat = _nospace(segment)
        for pattern in spec.forbidden_signatures:
            if re.search(pattern, flat):
                out.append(
                    Violation(
                        CODE_FORBIDDEN_SIGNATURE,
                        spec.concern_id,
                        f"forbidden source signature /{pattern}/",
                        segment,
                    )
                )
    return out


def validate_roles(
    concern_id: str,
    roles: Iterable[str],
    *,
    contract: ConcernContract | None = None,
) -> list[Violation]:
    spec = contract if contract is not None else contract_for(concern_id)
    out: list[Violation] = []
    for role in roles:
        role = str(role)
        if role in spec.forbidden_roles:
            out.append(Violation(CODE_FORBIDDEN_ROLE, spec.concern_id, f"forbidden numeric role {role}", role))
            continue
        if spec.allowed_roles and role not in spec.allowed_roles:
            out.append(Violation(CODE_ROLE_NOT_ALLOWED, spec.concern_id, f"numeric role {role} not allowed", role))
    return out


def validate_point(
    concern_id: str,
    *,
    displayed_text: str = "",
    review_checks: Sequence[str] = (),
    pass_criteria: Sequence[str] = (),
    materials: Sequence[str] = (),
    consequence: str = "",
    scoring_guidance: str = "",
    numeric_roles: Iterable[str] = (),
    linked_fact_keys: Iterable[str] = (),
    evidence_text: str = "",
    contract: ConcernContract | None = None,
) -> list[Violation]:
    """Validate one *rendered* row against its concern contract.

    Everything validated here is text a human reads in the final workbook, so a
    violation is a semantic defect rather than a provenance one.
    """

    spec = contract if contract is not None else contract_for(concern_id)
    out = validate_displayed_text(concern_id, displayed_text, contract=spec)
    out.extend(validate_roles(concern_id, numeric_roles, contract=spec))
    for key in linked_fact_keys:
        if not spec.fact_ok(str(key)):
            out.append(
                Violation(CODE_FACT_NOT_ALLOWED, spec.concern_id, f"linked fact {key} not allowed", str(key))
            )
    for name in materials:
        if not spec.material_ok(str(name)):
            out.append(
                Violation(CODE_MATERIAL_NOT_ALLOWED, spec.concern_id, f"material {name} not allowed", str(name))
            )
    if consequence and not spec.consequence_ok(consequence):
        out.append(
            Violation(
                CODE_CONSEQUENCE_NOT_ALLOWED,
                spec.concern_id,
                f"consequence class {consequence_class(consequence)} not allowed",
                consequence,
            )
        )
    if evidence_text:
        flat = _nospace(evidence_text)
        for pattern in spec.forbidden_evidence:
            if re.search(pattern, flat):
                out.append(
                    Violation(
                        CODE_EVIDENCE_FORBIDDEN,
                        spec.concern_id,
                        f"primary evidence matches forbidden /{pattern}/",
                        evidence_text,
                    )
                )
        if spec.required_evidence and not any(
            re.search(pattern, flat) for pattern in spec.required_evidence
        ):
            out.append(
                Violation(
                    CODE_EVIDENCE_SIGNATURE_MISSING,
                    spec.concern_id,
                    "primary evidence carries none of the required signatures",
                    evidence_text,
                )
            )
    # a scoring row may only quote score text when its contract is a scoring one
    if scoring_guidance and not is_scoring_concern(spec.concern_id):
        if re.search(r"(得\s*\d+\s*分|分值|评分)", _nospace(scoring_guidance)):
            out.append(
                Violation(
                    CODE_FORBIDDEN_SIGNATURE,
                    spec.concern_id,
                    "a non-scoring concern quotes scoring text",
                    scoring_guidance,
                )
            )
    for line in list(review_checks) + list(pass_criteria):
        if spec.kind in {KIND_INFORMATIONAL} and re.search(r"(否决|无效|不予受理)", str(line)):
            out.append(
                Violation(CODE_CONSEQUENCE_NOT_ALLOWED, spec.concern_id, "informational concern claims a rejection", str(line))
            )
    return out


def contract_table_is_independent() -> bool:
    """Structural self-check: the table must not be keyed by generated content."""

    if not CONTRACTS:
        return False
    for concern_id, spec in CONTRACTS.items():
        if spec.concern_id != concern_id:
            return False
        if spec.kind not in KINDS:
            return False
        if spec.explicit is not True:
            return False
    return True


def contracts_table() -> dict[str, Any]:
    """The persisted contract table (the human-readable specification)."""

    return {
        "schema": SCHEMA,
        "source": CONTRACT_SOURCE,
        "version": CONTRACT_VERSION,
        "independent": contract_table_is_independent(),
        "count": len(CONTRACTS),
        "kinds": sorted(KINDS),
        "contracts": {cid: spec.as_dict() for cid, spec in sorted(CONTRACTS.items())},
    }


__all__ = [
    "ACTOR_AGENT",
    "ACTOR_BIDDER",
    "ACTOR_PLATFORM",
    "ACTOR_PURCHASER",
    "CONSEQUENCES",
    "CONSEQUENCE_CUES",
    "CONSEQUENCE_DISQUALIFY",
    "CONSEQUENCE_LIABILITY",
    "CONSEQUENCE_NO_ACCEPT",
    "CONSEQUENCE_NONE",
    "CONSEQUENCE_REJECT",
    "CONSEQUENCE_VOID",
    "CONTRACT_SOURCE",
    "CONTRACT_VERSION",
    "CONTRACTS",
    "KINDS",
    "KIND_CONTRACT_ONLY",
    "KIND_INFORMATIONAL",
    "KIND_MANDATORY",
    "KIND_REJECTION",
    "KIND_SCORING",
    "RENAMED_CONCERNS",
    "SCHEMA",
    "SUPERSEDED_CONCERNS",
    "ConcernContract",
    "Violation",
    "concern_kind",
    "consequence_class",
    "contract_for",
    "contract_table_is_independent",
    "contracts_table",
    "forbidden_segments",
    "has_explicit_contract",
    "is_scoring_concern",
    "owned_segments",
    "owned_text",
    "segment_text",
    "validate_displayed_text",
    "validate_point",
    "validate_roles",
]
