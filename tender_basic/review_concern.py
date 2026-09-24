"""Review-concern ownership layer (REVIEW WORKBOOK ROUND 3).

Round-2 gave every rendered component *provenance*: a real source clause, a real
number, a real locator.  Human review then found rows where all of that was true
yet the components did **not** belong to the same human review concern.

This module adds the missing layer:

    SourceRequirementAtom -> ReviewConcern -> concern-owned components -> ReviewPoint

Frozen round-3 rule: **provenance is necessary but not sufficient**.  A component
may be rendered only when it is source-backed *and* its ``owner_concern_id``
equals the concern being rendered (or when an explicit, evidence-linked
multi-concern reuse exists with a distinct human purpose).

Nothing here branches on a case id: classification is driven by generic source
vocabulary, actors, modalities and authority scopes only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from tender_basic.dynamic_requirements import SourceRequirementUnit
from tender_basic.review_point import (
    NumericEvidence,
    extract_numeric_evidence,
    is_internal_procedure,
    line_is_grounded,
)

# --------------------------------------------------------------------------- #
# vocabularies
# --------------------------------------------------------------------------- #

ACTOR_BIDDER = "BIDDER"
ACTOR_PURCHASER = "PURCHASER"
ACTOR_AGENT = "AGENT"
ACTOR_EVALUATION_COMMITTEE = "EVALUATION_COMMITTEE"
ACTOR_OTHER = "OTHER"
ACTORS = (
    ACTOR_BIDDER,
    ACTOR_PURCHASER,
    ACTOR_AGENT,
    ACTOR_EVALUATION_COMMITTEE,
    ACTOR_OTHER,
)

MODALITY_MUST = "MUST"
MODALITY_MUST_NOT = "MUST_NOT"
MODALITY_MAY = "MAY"
MODALITY_INFORMATIONAL = "INFORMATIONAL"
MODALITIES = (MODALITY_MUST, MODALITY_MUST_NOT, MODALITY_MAY, MODALITY_INFORMATIONAL)

SCOPE_TENDER_NOTICE = "TENDER_NOTICE"
SCOPE_BIDDER_INSTRUCTIONS = "BIDDER_INSTRUCTIONS"
SCOPE_BIDDER_INSTRUCTIONS_SCHEDULE = "BIDDER_INSTRUCTIONS_SCHEDULE"
SCOPE_EVALUATION_METHOD = "EVALUATION_METHOD"
SCOPE_CONTRACT_TEMPLATE = "CONTRACT_TEMPLATE"
SCOPE_PROCUREMENT_REQUIREMENTS = "PROCUREMENT_REQUIREMENTS"
SCOPE_RESPONSE_FORMAT = "RESPONSE_FORMAT"
AUTHORITY_SCOPES = (
    SCOPE_TENDER_NOTICE,
    SCOPE_BIDDER_INSTRUCTIONS,
    SCOPE_BIDDER_INSTRUCTIONS_SCHEDULE,
    SCOPE_EVALUATION_METHOD,
    SCOPE_CONTRACT_TEMPLATE,
    SCOPE_PROCUREMENT_REQUIREMENTS,
    SCOPE_RESPONSE_FORMAT,
)

#: Concerns that are never a bidder checklist row on their own.
INTERNAL_CONCERNS = frozenset({"INTERNAL_PROCEDURE"})


# --------------------------------------------------------------------------- #
# concern registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ConcernSpec:
    """One practical human decision/action."""

    concern_id: str
    label: str
    question: str
    #: numeric roles this concern may own (round-2 role vocabulary)
    numeric_roles: frozenset[str] = frozenset()
    #: True when the concern is a bidder-facing work item by construction
    bidder_facing: bool = True
    #: True for concerns whose components may legitimately come from another
    #: concern's clause when the source relationship is explicit
    allows_reuse: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "concern_id": self.concern_id,
            "label": self.label,
            "question": self.question,
            "numeric_roles": sorted(self.numeric_roles),
            "bidder_facing": self.bidder_facing,
        }


def _spec(
    concern_id: str,
    label: str,
    question: str,
    roles: Iterable[str] = (),
    *,
    bidder_facing: bool = True,
    allows_reuse: bool = False,
) -> ConcernSpec:
    return ConcernSpec(
        concern_id=concern_id,
        label=label,
        question=question,
        numeric_roles=frozenset(roles),
        bidder_facing=bidder_facing,
        allows_reuse=allows_reuse,
    )


CONCERNS: dict[str, ConcernSpec] = {
    spec.concern_id: spec
    for spec in (
        _spec("PROJECT_BASIC_INFO", "项目基本信息", "本项目的基本信息是否与招标文件一致？", ()),
        _spec("BID_VALIDITY", "投标有效期", "投标有效期是否满足并覆盖评审定标全过程？", ("VALIDITY_DAYS",)),
        _spec("AFTER_SALES_SERVICE", "售后服务与运维", "售后服务与运维承诺是否满足要求？", ("RESPONSE_DAYS",)),
        _spec(
            "TECHNICAL_INSTALLATION",
            "安装调试与验收",
            "安装、调试、检测与验收标准是否满足要求？",
            ("QUANTITY", "WARRANTY_MONTHS"),
        ),
        _spec(
            "SIGNATURE_RED_LINE",
            "签章否决红线",
            "签章/签字缺陷是否会导致否决？",
        ),
        _spec("REJECTION_GENERAL", "其他否决情形", "还有哪些情形会导致投标被否决？"),
        _spec(
            "GENERAL_BIDDER_OBLIGATION",
            "一般投标人义务",
            "该条款对投标人提出了什么具体义务？",
        ),
        # qualification
        _spec("QUALIFICATION_LICENSE", "资格·营业执照与资质", "营业执照/资质证书是否有效并按要求提供？", ()),
        _spec("QUALIFICATION_FINANCIAL", "资格·财务能力", "财务能力承诺或审计报告是否按要求提供？", ()),
        _spec("QUALIFICATION_CREDIT", "资格·信用记录", "信用记录查询结果是否满足要求？", ()),
        _spec("QUALIFICATION_ANTI_BRIBERY", "资格·无行贿与履约记录", "无行贿/无不良履约记录承诺是否按要求提交？", ()),
        _spec("QUALIFICATION_PERFORMANCE", "资格·类似业绩", "类似项目业绩是否满足数量与时间范围要求？", ("PERSON_COUNT",)),
        _spec(
            "QUALIFICATION_RELATIONSHIP_RESTRICTION",
            "资格·关联关系限制",
            "是否存在单位负责人同一人或控股、管理关系等禁止情形？",
        ),
        _spec("CONSORTIUM", "联合体", "是否允许联合体投标，响应是否与之一致？"),
        _spec("SUBCONTRACT", "分包与转包", "是否存在违规分包、转包情形？"),
        # submission / electronic
        _spec("SUBMISSION_DEADLINE", "递交截止时间", "是否在规定截止时间前完成递交？", ("RESPONSE_DAYS",)),
        _spec("SUBMISSION_PLATFORM", "递交地点与平台", "递交方式、地点/平台是否符合要求？"),
        _spec(
            "SUBMISSION_COPIES",
            "文件份数与电子版",
            "正副本份数与电子版要求是否满足？",
            ("QUANTITY",),
        ),
        _spec("ELECTRONIC_UPLOAD", "电子上传与加密", "电子文件是否按规定加密/上传成功？"),
        _spec("OPENING_DECRYPTION", "开标与解密", "是否按时完成签到与解密？", ("RESPONSE_DAYS",)),
        # signature
        _spec("SIGNATURE_AND_SEAL", "签章要求", "哪些位置必须签字/盖章，形式是否合规？"),
        _spec("SIGNATURE_EXECUTION", "签章执行核对", "逐页/逐处签章是否执行到位？"),
        _spec("AUTHORIZATION", "授权委托", "授权代表签署的授权链条是否完整？"),
        # bid bond
        _spec("BID_BOND_AMOUNT", "保证金金额", "保证金金额是否与招标文件一致？", ("BOND_AMOUNT",)),
        _spec("BID_BOND_FORM", "保证金形式", "保证金形式是否符合规定？"),
        _spec("BID_BOND_TRANSFER", "保证金转出账户", "是否从规定账户转出？"),
        _spec("BID_BOND_DEADLINE", "保证金到账时间", "保证金是否在截止前到账？", ("RESPONSE_DAYS",)),
        _spec("BID_BOND_EVIDENCE", "保证金凭证", "保证金凭证是否放入响应文件？"),
        # price
        _spec("PRICE_CEILING", "报价与最高限价", "报价是否不超过最高限价？", ("PRICE",)),
        _spec("PRICE_ARITHMETIC", "报价算术与大小写", "大小写、单价×数量、分项合计是否一致？", ("PRICE",)),
        _spec("PRICE_COMPLETENESS", "报价完整性", "是否存在漏项、重复项或未包含费用？", ("PRICE", "QUANTITY")),
        _spec("PRICE_TAX_BASIS", "报价税务口径", "税率与含税口径是否一致？", ("SCORE",)),
        _spec("PRICE_ITEMIZATION", "分项报价与暂列金额", "分项限价/暂列金额是否与源表一致？", ("PRICE", "QUANTITY")),
        # delivery / quality / warranty
        _spec("DELIVERY_PERIOD", "工期与供货期", "工期/供货期是否满足并覆盖交付节点？", ("DURATION_DAYS",)),
        _spec("DELIVERY_LOCATION", "交付地点", "交付地点与实施范围是否符合要求？"),
        _spec("SITE_VISIT", "现场踏勘", "是否按须知规定参加/安排了现场踏勘，记录是否留档？"),
        _spec(
            "TERM_DEFINITION",
            "术语与主体定义",
            "（仅词汇定义，非投标人义务）",
            bidder_facing=False,
        ),
        _spec("QUALITY_TARGET", "质量目标", "质量/验收标准是否达标？"),
        _spec("PROJECT_WARRANTY", "项目/产品质保", "项目/产品质保期与范围是否满足要求？", ("WARRANTY_MONTHS",)),
        _spec("RETENTION_MONEY_RATIO", "质保金比例", "质保金/尾款比例是否与合同条款一致？", ("PAYMENT_RATIO",)),
        _spec(
            "RETENTION_RELEASE_PERIOD",
            "质保金释放期限",
            "质保金/尾款返还或释放期限及条件是否清楚？",
            ("WARRANTY_MONTHS", "DURATION_DAYS"),
        ),
        # file
        _spec("FILE_COMPOSITION", "响应文件组成", "响应文件应由哪些部分组成、是否齐全？"),
        _spec("FILE_FORMAT", "响应文件格式", "格式、装订、目录与页码是否按要求？"),
        # technical
        _spec("TECHNICAL_PARAMETER", "技术参数与配置", "技术参数是否逐条响应、有无负偏离？", ("QUANTITY",)),
        _spec("TECHNICAL_PROOF", "技术证明材料", "证明材料是否齐全、可核验？"),
        _spec(
            "TECHNICAL_PLAN",
            "技术方案与实施组织",
            "技术方案/进度/人员机具/质量/应急是否完整可实施？",
        ),
        # evaluation
        _spec("EVALUATION_FORMAL_REVIEW", "评审·形式审查", "形式审查要点是否满足？"),
        _spec("EVALUATION_QUALIFICATION_REVIEW", "评审·资格审查", "资格审查要点是否满足？"),
        _spec("EVALUATION_RESPONSIVENESS", "评审·响应性审查", "实质性响应要求是否全部满足？"),
        _spec(
            "EVALUATION_SCORING",
            "评分标准与分值构成",
            "每个评分因素如何得分、需要什么证明？",
            ("SCORE", "PERSON_COUNT", "QUANTITY", "PAYMENT_RATIO", "PRICE"),
            allows_reuse=True,
        ),
        _spec("EVALUATION_COLLUSION", "评审·串标与弄虚作假", "是否存在串标、弄虚作假情形？"),
        # contract
        _spec(
            "CONTRACT_PAYMENT",
            "合同付款与结算",
            "付款方式、结算依据与付款条件是否可接受？",
            ("PAYMENT_RATIO", "PRICE"),
        ),
        _spec("CONTRACT_RISK", "合同风险与违约责任", "是否存在采购人不能接受的附加条件或风险？"),
        _spec("CONTRACT_DELIVERY", "合同交付义务", "合同交付义务与招标要求是否一致？", ("DURATION_DAYS",)),
        _spec("CONTRACT_ACCEPTANCE", "合同验收", "验收标准与程序是否可执行？"),
        # conflict
        _spec("SOURCE_REQUIREMENT_CONFLICT", "条款冲突", "不同来源条款是否真正互相冲突？", allows_reuse=True),
        # internal (never an ordinary bidder row)
        _spec(
            "INTERNAL_PROCEDURE",
            "采购方内部程序",
            "采购方/评审委员会内部程序事项",
            bidder_facing=False,
        ),
        # fallback
        _spec("UNCLASSIFIED", "未归类", "待人工归类", bidder_facing=False),
        _spec(
            "UNSUPPORTED_FORMAT_CLAIM",
            "无源依据的格式主张",
            "该格式/组成主张在源文件中是否有真实依据？",
            bidder_facing=False,
        ),
    )
}


def concern_spec(concern_id: str) -> ConcernSpec:
    return CONCERNS.get(concern_id, CONCERNS["UNCLASSIFIED"])


def concern_label(concern_id: str) -> str:
    return concern_spec(concern_id).label


# --------------------------------------------------------------------------- #
# SourceRequirementAtom
# --------------------------------------------------------------------------- #


@dataclass
class SourceRequirementAtom:
    """One source requirement sentence-group, with actor/scope/numeric metadata."""

    atom_id: str
    source_clause_id: str
    source_text: str
    source_page: int | None = None
    source_section: str = ""
    source_locator: str = ""
    source_structure_id: str = ""
    actor: str = ACTOR_OTHER
    object: str = ""
    action: str = ""
    topic: str = ""
    requirement_kind: str = ""
    modality: str = MODALITY_INFORMATIONAL
    applicability_scope: str = ""
    authority_scope: str = SCOPE_BIDDER_INSTRUCTIONS
    requirement_type: str = ""
    numeric_values: list[NumericEvidence] = field(default_factory=list)
    required_materials: list[str] = field(default_factory=list)
    linked_fact_keys: list[str] = field(default_factory=list)
    explicit_consequence: str = ""
    explicit_score_rule: str = ""
    source_parent_id: str = ""
    owner_concern_id: str = ""
    owner_reason: str = ""
    mandatory: bool = False
    high_risk: bool = False
    internal: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "source_clause_id": self.source_clause_id,
            "source_page": self.source_page,
            "source_section": self.source_section,
            "source_locator": self.source_locator,
            "source_structure_id": self.source_structure_id,
            "source_text": self.source_text,
            "actor": self.actor,
            "object": self.object,
            "action": self.action,
            "topic": self.topic,
            "requirement_kind": self.requirement_kind,
            "modality": self.modality,
            "applicability_scope": self.applicability_scope,
            "authority_scope": self.authority_scope,
            "requirement_type": self.requirement_type,
            "numeric_values": [value.as_dict() for value in self.numeric_values],
            "required_materials": list(self.required_materials),
            "linked_fact_keys": list(self.linked_fact_keys),
            "explicit_consequence": self.explicit_consequence,
            "explicit_score_rule": self.explicit_score_rule,
            "source_parent_id": self.source_parent_id,
            "owner_concern_id": self.owner_concern_id,
            "owner_reason": self.owner_reason,
            "mandatory": self.mandatory,
            "high_risk": self.high_risk,
            "internal": self.internal,
        }


# --------------------------------------------------------------------------- #
# actor / modality / authority scope
# --------------------------------------------------------------------------- #

_INTERNAL_SUBJECT = re.compile(
    r"(评审小组|评标委员会|磋商小组|询比小组|采购小组|评审委员会|评委|评审专家|专家|采购人|招标人|采购单位|代理机构|采购代理机构)"
)
_BIDDER_SUBJECT = re.compile(r"(供应商|投标人|响应人|承包人|申请人|报价人|投标单位)")

_AGENT_SUBJECT = re.compile(r"(代理机构|采购代理|招标代理)")

_MODALITY_MUST = re.compile(r"(应当|须|必须|应|需|不得|禁止|不允许|不接受|拒绝)")
_MODALITY_MAY = re.compile(r"(可以|可自行|允许|可选择)")
_MUST_NOT = re.compile(r"(不得|禁止|不允许|不接受|拒绝|严禁)")

_ACTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("提交", re.compile(r"(提交|递交|上传|报送|送达|提供)")),
    ("签署", re.compile(r"(签字|签署|盖章|加盖|签章)")),
    ("报价", re.compile(r"(报价|价格|费用|金额)")),
    ("评审", re.compile(r"(评审|评标|审查|打分|计分|得分)")),
    ("履行", re.compile(r"(履行|执行|完成|交付|供货|安装|调试)")),
    ("承诺", re.compile(r"(承诺|保证|声明)")),
    ("支付", re.compile(r"(付款|支付|结算|返还|付清)")),
)

_CONSEQUENCE_RE = re.compile(
    r"(否决|废标|无效(?:投标|响应|报价)?|不予受理|不予评审|不得参加|取消(?:投标|成交|中标)?资格|扣分|不得分|0分|拒绝接收|拒收)"
)
_SCORE_RE = re.compile(r"(最高得?\s*\d+(?:\.\d+)?\s*分|得\s*\d+(?:\.\d+)?\s*分|\d+(?:\.\d+)?\s*分\s*[）)]|分值|评分标准|计分)")

#: authority-scope cues, strongest first
_SCOPE_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        SCOPE_CONTRACT_TEMPLATE,
        (
            "合同条款",
            "合同格式",
            "合同书",
            "合同模板",
            "协议书",
            "合同附件",
            "第四章",
            "甲乙双方",
            "甲方",
            "乙方",
            "发包人",
            "承包人",
            "违约责任",
        ),
    ),
    (
        SCOPE_RESPONSE_FORMAT,
        ("响应文件格式", "投标文件格式", "第六章", "格式要求", "格式见", "封面格式", "格式附件"),
    ),
    (
        SCOPE_BIDDER_INSTRUCTIONS_SCHEDULE,
        ("前附表", "投标人须知前附表", "供应商须知前附表"),
    ),
    (
        SCOPE_EVALUATION_METHOD,
        ("评审办法", "评标办法", "评分标准", "评分办法", "评审因素", "评标方法", "第五章", "评标细则"),
    ),
    (
        SCOPE_BIDDER_INSTRUCTIONS,
        ("投标人须知", "供应商须知", "投标须知", "响应人须知", "第二章", "总则"),
    ),
    (
        SCOPE_PROCUREMENT_REQUIREMENTS,
        ("采购需求", "技术要求", "规格参数", "第三章", "工程量清单", "供货要求"),
    ),
    (SCOPE_TENDER_NOTICE, ("招标公告", "采购公告", "磋商公告", "询比公告")),
)


def classify_actor(text: str) -> tuple[str, str]:
    """Return ``(actor, reason)`` for a source sentence-group."""

    bidder = bool(_BIDDER_SUBJECT.search(text))
    internal_subject = _INTERNAL_SUBJECT.search(text)
    if bidder:
        return ACTOR_BIDDER, "bidder subject"
    if internal_subject:
        subject = internal_subject.group(1)
        if _AGENT_SUBJECT.search(subject):
            return ACTOR_AGENT, "agent subject"
        if subject in {"评审小组", "评标委员会", "磋商小组", "询比小组", "采购小组", "评审委员会", "评委", "评审专家", "专家"}:
            return ACTOR_EVALUATION_COMMITTEE, "evaluation-committee subject"
        return ACTOR_PURCHASER, "purchaser subject"
    return ACTOR_OTHER, "no explicit subject"


def classify_modality(text: str) -> str:
    if _MUST_NOT.search(text):
        return MODALITY_MUST_NOT
    if _MODALITY_MUST.search(text):
        return MODALITY_MUST
    if _MODALITY_MAY.search(text):
        return MODALITY_MAY
    return MODALITY_INFORMATIONAL


def classify_action(text: str) -> str:
    for action, pattern in _ACTION_PATTERNS:
        if pattern.search(text):
            return action
    return ""


def classify_authority_scope(*, section: str, clause: str, text: str) -> str:
    haystack = f"{section} {clause}"
    for scope, cues in _SCOPE_CUES:
        if any(cue in haystack for cue in cues):
            return scope
    for scope, cues in _SCOPE_CUES:
        if any(cue in text for cue in cues):
            return scope
    return SCOPE_BIDDER_INSTRUCTIONS


# --------------------------------------------------------------------------- #
# concern classification
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Rule:
    concern_id: str
    any_of: tuple[str, ...]
    all_of: tuple[str, ...] = ()
    none_of: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    actor: str = ""
    reason: str = ""

    def matches(self, atom: SourceRequirementAtom) -> bool:
        text = atom.source_text
        if self.actor and atom.actor != self.actor:
            return False
        if self.scopes and atom.authority_scope not in self.scopes:
            return False
        if self.any_of and not any(term in text for term in self.any_of):
            return False
        if self.all_of and not all(term in text for term in self.all_of):
            return False
        if self.none_of and any(term in text for term in self.none_of):
            return False
        return True


#: Ordered classification rules.  The first match wins.  Rules are generic: they
#: use source vocabulary, authority scope and actor only — never a case id.
_CONCERN_RULES: tuple[_Rule, ...] = (
    # ---- internal purchaser / committee procedure -------------------------- #
    _Rule(
        "INTERNAL_PROCEDURE",
        any_of=("评审小组", "评标委员会", "磋商小组", "询比小组", "评审委员会", "评委", "评审专家", "采购人", "招标人"),
        all_of=(),
        reason="internal-procedure subject",
        actor="",
    ),
    # ---- retention vs project warranty (same keyword, different concept) --- #
    _Rule(
        "RETENTION_MONEY_RATIO",
        any_of=("质保金", "质量保证金", "尾款", "余款", "保留金"),
        all_of=(),
        scopes=(SCOPE_CONTRACT_TEMPLATE,),
        reason="retention-money wording inside the contract-payment scope",
    ),
    _Rule(
        "RETENTION_RELEASE_PERIOD",
        any_of=("质保金", "质量保证金", "尾款", "余款", "保留金", "缺陷责任期"),
        all_of=(),
        scopes=(SCOPE_CONTRACT_TEMPLATE,),
        reason="retention/payment-release wording inside the contract-payment scope",
    ),
    _Rule(
        "PROJECT_WARRANTY",
        any_of=("质保期", "保修期", "质保范围", "质保服务", "免费质保", "质量保证期"),
        none_of=("质保金", "质量保证金", "保留金"),
        reason="project/product warranty obligation",
    ),
    # ---- bid bond ---------------------------------------------------------- #
    _Rule(
        "BID_BOND_AMOUNT",
        any_of=("投标保证金", "响应保证金", "保证金"),
        all_of=("元",),
        reason="bond amount",
    ),
    _Rule(
        "BID_BOND_TRANSFER",
        any_of=("基本账户", "基本存款账户", "开户许可证", "从投标人", "转出"),
        all_of=("保证金",),
        reason="bond source account",
    ),
    _Rule(
        "BID_BOND_FORM",
        any_of=("电汇", "转账", "银行保函", "保函", "保险", "形式"),
        all_of=("保证金",),
        reason="bond form",
    ),
    _Rule(
        "BID_BOND_DEADLINE",
        any_of=("截止时间前", "到账", "前到账"),
        all_of=("保证金",),
        reason="bond deadline",
    ),
    _Rule(
        "BID_BOND_EVIDENCE",
        any_of=("凭证", "回单", "扫描件"),
        all_of=("保证金",),
        reason="bond proof",
    ),
    _Rule("BID_BOND_EVIDENCE", any_of=("保证金",), reason="bond clause (unspecified aspect)"),
    # ---- electronic / submission ------------------------------------------ #
    _Rule(
        "ELECTRONIC_UPLOAD",
        any_of=("CA", "ca锁", "加密", "电子投标", "电子响应", "电子交易平台"),
        reason="electronic upload/encryption",
    ),
    _Rule(
        "OPENING_DECRYPTION",
        any_of=("解密", "签到"),
        reason="opening/decryption",
    ),
    _Rule(
        "SUBMISSION_PLATFORM",
        any_of=("递交地点", "递交方式", "送达地点", "上传平台", "开标地点", "递交至"),
        reason="submission place/method",
    ),
    _Rule(
        "SUBMISSION_COPIES",
        any_of=("正本", "副本", "份数", "U盘", "电子版"),
        reason="copies / electronic copy",
    ),
    _Rule(
        "SUBMISSION_DEADLINE",
        any_of=("投标截止时间", "递交截止时间", "响应截止时间", "截止时间", "逾期"),
        reason="submission deadline",
    ),
    # ---- signature --------------------------------------------------------- #
    _Rule(
        "AUTHORIZATION",
        any_of=("授权委托", "授权书", "授权代表", "法定代表人授权", "授权代理人"),
        reason="authorization chain",
    ),
    _Rule(
        "SIGNATURE_AND_SEAL",
        any_of=("签字", "盖章", "公章", "签章", "法定代表人"),
        reason="signature/seal requirement",
    ),
    # ---- qualification ----------------------------------------------------- #
    _Rule(
        "QUALIFICATION_RELATIONSHIP_RESTRICTION",
        any_of=("单位负责人为同一人", "控股", "管理关系", "同一人", "关联企业"),
        reason="relationship restriction",
    ),
    _Rule(
        "QUALIFICATION_LICENSE",
        any_of=("营业执照", "资质证书", "资质等级", "许可证", "三证合一"),
        reason="licence/qualification document",
    ),
    _Rule(
        "QUALIFICATION_FINANCIAL",
        any_of=("财务状况", "财务审计", "财务报表", "财务承诺", "资产负债", "银行资信"),
        reason="bidder financial capability",
    ),
    _Rule(
        "QUALIFICATION_CREDIT",
        any_of=("信用中国", "失信被执行人", "重大税收违法", "政府采购严重违法", "信用记录", "信用查询"),
        reason="credit record",
    ),
    _Rule(
        "QUALIFICATION_ANTI_BRIBERY",
        any_of=("行贿", "不良履约", "无重大违法", "犯罪记录"),
        reason="anti-bribery / no-bad-record commitment",
    ),
    _Rule(
        "QUALIFICATION_PERFORMANCE",
        any_of=("类似业绩", "类似项目业绩", "业绩证明", "供货业绩", "合同业绩"),
        reason="comparable performance record",
    ),
    _Rule("CONSORTIUM", any_of=("联合体",), reason="consortium rule"),
    _Rule("SUBCONTRACT", any_of=("分包", "转包"), reason="subcontracting rule"),
    # ---- price ------------------------------------------------------------- #
    _Rule(
        "PRICE_ITEMIZATION",
        any_of=("分项报价", "暂列金额", "分项限价", "已标价工程量清单", "分项表"),
        reason="itemised pricing / provisional sum",
    ),
    _Rule(
        "PRICE_CEILING",
        any_of=("最高限价", "最高投标限价", "预算金额", "采购预算", "超过限价"),
        reason="price ceiling",
    ),
    _Rule(
        "PRICE_TAX_BASIS",
        any_of=("税率", "含税", "不含税", "增值税"),
        reason="tax basis",
    ),
    _Rule(
        "PRICE_ARITHMETIC",
        any_of=("大写", "小写", "单价", "合计", "总价", "算术"),
        reason="price arithmetic / case consistency",
    ),
    _Rule(
        "PRICE_COMPLETENESS",
        any_of=("漏项", "重复项", "未包含", "一切费用", "费用包含"),
        reason="price completeness",
    ),
    _Rule("PRICE_COMPLETENESS", any_of=("报价", "价格"), reason="pricing clause (general)"),
    # ---- delivery / quality ------------------------------------------------ #
    _Rule(
        "DELIVERY_PERIOD",
        any_of=("供货期", "交货期", "工期", "服务期", "交付期"),
        reason="delivery period",
    ),
    _Rule(
        "DELIVERY_LOCATION",
        any_of=("交货地点", "交付地点", "实施地点", "服务地点", "供货地点"),
        reason="delivery location",
    ),
    _Rule(
        "QUALITY_TARGET",
        any_of=("质量标准", "合格标准", "验收标准", "质量要求", "质量目标"),
        reason="quality target",
    ),
    # ---- file -------------------------------------------------------------- #
    _Rule(
        "FILE_COMPOSITION",
        any_of=("响应文件组成", "投标文件组成", "文件组成", "组成内容", "包括下列", "应包含"),
        reason="response-file composition",
    ),
    _Rule(
        "FILE_FORMAT",
        any_of=("装订", "目录", "页码", "格式要求", "编排", "字体", "密封", "封装"),
        reason="response-file format",
    ),
    # ---- technical --------------------------------------------------------- #
    _Rule(
        "TECHNICAL_PARAMETER",
        any_of=("技术参数", "规格参数", "技术规格", "配置要求", "偏离"),
        reason="technical parameter",
    ),
    _Rule(
        "TECHNICAL_PROOF",
        any_of=("检测报告", "证明材料", "检验报告", "型式试验", "认证证书"),
        reason="technical proof",
    ),
    _Rule(
        "TECHNICAL_PLAN",
        any_of=("技术方案", "实施方案", "进度计划", "应急预案", "质量保证措施", "供货方案", "售后服务方案"),
        reason="technical plan",
    ),
    # ---- evaluation -------------------------------------------------------- #
    _Rule(
        "EVALUATION_COLLUSION",
        any_of=("串标", "串通", "雷同", "恶意串通", "弄虚作假"),
        reason="collusion / fraud",
    ),
    _Rule(
        "EVALUATION_SCORING",
        any_of=("评分标准", "评分因素", "评审因素", "得分", "计分", "分值"),
        reason="scoring item",
    ),
    _Rule(
        "EVALUATION_FORMAL_REVIEW",
        any_of=("形式审查", "形式评审", "符合性审查"),
        reason="formal review",
    ),
    _Rule(
        "EVALUATION_QUALIFICATION_REVIEW",
        any_of=("资格审查", "资格评审", "资格审核"),
        reason="qualification review",
    ),
    _Rule(
        "EVALUATION_RESPONSIVENESS",
        any_of=("实质性响应", "实质性要求", "响应性审查"),
        reason="responsiveness review",
    ),
    # ---- contract ---------------------------------------------------------- #
    _Rule(
        "CONTRACT_PAYMENT",
        any_of=("付款", "支付", "结算", "付款方式", "价款"),
        scopes=(SCOPE_CONTRACT_TEMPLATE,),
        reason="contract payment terms",
    ),
    _Rule(
        "CONTRACT_ACCEPTANCE",
        any_of=("验收", "竣工验收"),
        scopes=(SCOPE_CONTRACT_TEMPLATE,),
        reason="contract acceptance",
    ),
    _Rule(
        "CONTRACT_DELIVERY",
        any_of=("交付", "供货", "工期", "交货"),
        scopes=(SCOPE_CONTRACT_TEMPLATE,),
        reason="contract delivery obligation",
    ),
    _Rule(
        "CONTRACT_RISK",
        any_of=("违约", "赔偿", "索赔", "不可抗力", "争议", "仲裁", "诉讼", "保证金不予退还"),
        scopes=(SCOPE_CONTRACT_TEMPLATE,),
        reason="contract risk / liability",
    ),
)


#: Topic priors.  The round-2 requirement index already separates
#: ``requirement_type``/``topic``; that separation is the strongest available
#: signal for *which human concern* a clause belongs to.  Text cues are used
#: only to select the sub-concern inside a topic family.
_TOPIC_CONCERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^投标保证金$|^保证金金额$"), "BID_BOND_AMOUNT"),
    (re.compile(r"^保证金形式$"), "BID_BOND_FORM"),
    (re.compile(r"^保证金递交与凭证$"), "BID_BOND_EVIDENCE"),
    (re.compile(r"^联合体$"), "CONSORTIUM"),
    (re.compile(r"^分包与转包$"), "SUBCONTRACT"),
    (re.compile(r"^合同条款与付款$"), "CONTRACT_PAYMENT"),
    (re.compile(r"^工期与供货期$"), "DELIVERY_PERIOD"),
    (re.compile(r"^加密上传与解密$"), "ELECTRONIC_UPLOAD"),
    (re.compile(r"^CA与电子签章$"), "ELECTRONIC_UPLOAD"),
    (re.compile(r"^评分标准与分值构成$|^价格评分与基准价$|^评审计分$"), "EVALUATION_SCORING"),
    (re.compile(r"^财务与审计报告$|^财务承诺函$"), "QUALIFICATION_FINANCIAL"),
    (re.compile(r"^投标文件格式$"), "FILE_FORMAT"),
    (re.compile(r"^投标文件组成$"), "FILE_COMPOSITION"),
    (re.compile(r"^交付与实施地点$"), "DELIVERY_LOCATION"),
    (re.compile(r"^费用与付款$"), "PRICE_COMPLETENESS"),
    (re.compile(r"^报价组成与费用范围$"), "PRICE_COMPLETENESS"),
    (re.compile(r"^最高限价与控制价$"), "PRICE_CEILING"),
    (re.compile(r"^分项限价与暂列金额$"), "PRICE_ITEMIZATION"),
    (re.compile(r"^证明材料要求$"), "TECHNICAL_PROOF"),
    (re.compile(r"^营业执照与独立法人$"), "QUALIFICATION_LICENSE"),
    (re.compile(r"^信用与失信查询$"), "QUALIFICATION_CREDIT"),
    (re.compile(r"^质量要求$"), "QUALITY_TARGET"),
    (re.compile(r"^签字盖章要求$"), "SIGNATURE_AND_SEAL"),
    (re.compile(r"^未按要求签字盖章$"), "SIGNATURE_RED_LINE"),
    (re.compile(r"^串通投标或弄虚作假$"), "EVALUATION_COLLUSION"),
    (re.compile(r"^未实质性响应$"), "EVALUATION_RESPONSIVENESS"),
    (re.compile(r"^保证金不符合要求$"), "BID_BOND_EVIDENCE"),
    (re.compile(r"^解密失败或未按时递交$"), "SUBMISSION_DEADLINE"),
    (re.compile(r"^报价超过最高限价$|^报价异常或选择性报价$"), "PRICE_CEILING"),
    (re.compile(r"^禁止性情形与失信排除$"), "QUALIFICATION_RELATIONSHIP_RESTRICTION"),
    (re.compile(r"^其他否决情形$"), "REJECTION_GENERAL"),
    (re.compile(r"^递交方式与截止时间$"), "SUBMISSION_DEADLINE"),
    (re.compile(r"^安装调试与验收$"), "TECHNICAL_INSTALLATION"),
    (re.compile(r"^技术参数与配置$|^接口与集成$"), "TECHNICAL_PARAMETER"),
    (re.compile(r"^技术方案与实施组织$"), "TECHNICAL_PLAN"),
    (re.compile(r"^售后服务与运维$"), "AFTER_SALES_SERVICE"),
    (re.compile(r"^投标有效期$"), "BID_VALIDITY"),
    (re.compile(r"^质保与保修$"), "PROJECT_WARRANTY"),
    (re.compile(r"^文件组成与格式$"), "FILE_COMPOSITION"),
    (re.compile(r"^程序性要求$"), "INTERNAL_PROCEDURE"),
    (re.compile(r"^其他要求$"), "GENERAL_BIDDER_OBLIGATION"),
)

_RETENTION_TEXT = re.compile(r"(质保金|质量保证金|保留金|尾款|余款)")
_RETENTION_RELEASE_TEXT = re.compile(r"(返还|退还|释放|付清|无息支付|期满后)")
_SUBMISSION_CUES = re.compile(r"(递交|提交|送达|上传|截止|拒收|逾期)")
_PRICE_CEILING_CUES = re.compile(r"(最高限价|控制价|预算金额|采购预算|超过限价)")
_COLLUSION_CUES = re.compile(r"(串标|串通|雷同|恶意串通|弄虚作假|行贿)")
_FORMAT_CUES = re.compile(r"(装订|目录|页码|编排|字体|密封|封装|格式)")
_COMPOSITION_CUES = re.compile(r"(组成|包括|应包含|应当包含|附件)")
_ITEMIZATION_CUES = re.compile(r"(暂列金额|分项限价|已标价工程量清单|限价表)")

#: High-signal text overrides.  A topic prior picks the family, but a clause
#: that plainly belongs to another family must not be dragged into it (round-3
#: fixtures A/C/H class: qualification text inside a signature/format topic).
#: Clauses whose legal identity is unambiguous: they are resolved before the
#: topic prior so a contract/payment or technical heading can never own a
#: relationship restriction, a same-manufacturer rejection ground, a site-visit
#: arrangement or a pure definitional clause (fixtures E/I/N class).
_DECISIVE_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"(单位负责人为同一人|直接控股|管理关系|同一人或者存在)"),
        "QUALIFICATION_RELATIONSHIP_RESTRICTION",
        "relationship/affiliation restriction",
    ),
    (
        re.compile(r"(同一制造商|同一品牌|同一型号|代理同一个制造商)"),
        "REJECTION_GENERAL",
        "same-manufacturer/brand/model rejection ground",
    ),
    (
        re.compile(r"(踏勘现场|现场考察|组织踏勘)"),
        "SITE_VISIT",
        "site visit / site survey arrangement",
    ),
    (
        re.compile(r"(供应商[:：]\s*响应采购人邀请|术语定义|^定义[:：]|定义[:：]\s*供应商)"),
        "TERM_DEFINITION",
        "definitional clause, not a bidder duty",
    ),
)

#: Every sign of an electronic submission object.
_ELECTRONIC_DOMINANT = re.compile(r"(电子交易系统|制作工具|上传|加密|\.EJYTF|电子响应文件|电子投标文件)")
#: Every sign of a real signature/seal duty (CA 电子签章 deliberately excluded).
_SIGNATURE_DOMINANT = re.compile(r"(加盖公章|签字|盖章|印章|公章|签署|法定代表人签字)")

_TEXT_OVERRIDES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"(行贿|不良履约记录|重大违法记录)"), "QUALIFICATION_ANTI_BRIBERY", "anti-bribery wording"),
    (re.compile(r"(信用中国|失信被执行人|重大税收违法|信用记录)"), "QUALIFICATION_CREDIT", "credit-record wording"),
    (re.compile(r"(营业执照|资质证书|资质等级|独立法人)"), "QUALIFICATION_LICENSE", "licence wording"),
    (re.compile(r"(财务审计|审计报告|财务状况|财务承诺)"), "QUALIFICATION_FINANCIAL", "financial wording"),
    (re.compile(r"(类似业绩|类似项目业绩|业绩证明)"), "QUALIFICATION_PERFORMANCE", "performance wording"),
    (re.compile(r"(单位负责人为同一人|直接控股|管理关系)"), "QUALIFICATION_RELATIONSHIP_RESTRICTION", "relationship wording"),
    (re.compile(r"联合体"), "CONSORTIUM", "consortium wording"),
    (re.compile(r"(分包|转包)"), "SUBCONTRACT", "subcontract wording"),
)

#: Bases that a text override may replace (families whose topic prior is a
#: presentation category rather than a semantic owner).
_OVERRIDABLE_BASES = frozenset(
    {
        "SIGNATURE_AND_SEAL",
        "SIGNATURE_EXECUTION",
        "FILE_FORMAT",
        "FILE_COMPOSITION",
        "EVALUATION_SCORING",
        "QUALITY_TARGET",
        "TECHNICAL_PARAMETER",
        "TECHNICAL_PROOF",
        "TECHNICAL_PLAN",
        "GENERAL_BIDDER_OBLIGATION",
        "REJECTION_GENERAL",
        "PROJECT_BASIC_INFO",
    }
)

#: Consequences that only a scoring concern may own.
_SCORE_ONLY_CONSEQUENCES = frozenset({"0分", "扣分", "不得分"})

_FEE_FRAGMENT = re.compile(r"(?:\d+[、.)]?\s*)?[^。；\n]*(?:售价|工本费|平台服务费|标书费|文件费)[^。；\n]*[。；]?")


_ANAPHORIC = re.compile(r"(此项|该事项|本项|上述|本项目|该条款|本条)")

#: Concerns strong enough to be inherited by an anaphoric sibling atom inside
#: the same source clause (``此项``/``本项`` refers to the same requirement).
_STRONG_CONCERNS = frozenset(
    {
        "QUALIFICATION_ANTI_BRIBERY",
        "QUALIFICATION_CREDIT",
        "QUALIFICATION_LICENSE",
        "QUALIFICATION_FINANCIAL",
        "QUALIFICATION_PERFORMANCE",
        "QUALIFICATION_RELATIONSHIP_RESTRICTION",
        "CONSORTIUM",
        "SUBCONTRACT",
    }
)


def _topic_concern(atom: SourceRequirementAtom) -> str:
    for pattern, concern_id in _TOPIC_CONCERNS:
        if pattern.search(atom.topic or ""):
            return concern_id
    return ""


def _text_override(atom: SourceRequirementAtom, base: str) -> tuple[str, str] | None:
    if base not in _OVERRIDABLE_BASES:
        return None
    for pattern, concern_id, reason in _TEXT_OVERRIDES:
        if pattern.search(atom.source_text) and concern_id != base:
            return concern_id, reason
    return None


def strip_fee_fragments(text: str) -> str:
    """Remove tender-file fee sentences (never a bidder review requirement)."""

    return _clean_fragment(_FEE_FRAGMENT.sub("", text))


def _clean_fragment(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ；;。")


def _sub_split(atom: SourceRequirementAtom, base: str) -> tuple[str, str]:
    """Refine the topic family into the exact human concern."""

    text = atom.source_text
    scope = atom.authority_scope

    # A clause about the e-bidding platform's production/upload/encryption flow is
    # an electronic submission requirement even when the source also says
    # "CA密钥签章": the electronic object, not the signature duty, is what the
    # human has to check there.
    if base.startswith("SIGNATURE") and _ELECTRONIC_DOMINANT.search(text) and not _SIGNATURE_DOMINANT.search(text):
        return "ELECTRONIC_UPLOAD", "electronic signing/upload wording dominates the signature keyword"

    # A scoring rule about a payment ratio is a scoring item, not a retention
    # clause; an explicit score cue therefore wins over retention wording.
    if re.search(r"(得\s*\d+(?:\.\d+)?\s*分|分值|最高得?\s*\d+(?:\.\d+)?\s*分)", text):
        if _COLLUSION_CUES.search(text):
            return "EVALUATION_COLLUSION", "collusion/fraud wording inside a scoring clause"
        return "EVALUATION_SCORING", "scoring clause"

    # retention wording always wins over the warranty topic: same keyword,
    # different concept (frozen round-3 rule).
    if _RETENTION_TEXT.search(text):
        if _RETENTION_RELEASE_TEXT.search(text) or re.search(r"\d+\s*个月", text):
            return "RETENTION_RELEASE_PERIOD", "retention/payment-release wording"
        return "RETENTION_MONEY_RATIO", "retention-money wording"

    # a real warranty obligation outranks an incidental hosting topic
    if re.search(r"(质保期|保修期|质量保证期|质保范围)", text):
        return "PROJECT_WARRANTY", "project/product warranty obligation"

    if base == "PROJECT_WARRANTY":
        return base, "project/product warranty obligation"

    if base == "CONTRACT_PAYMENT":
        if re.search(r"(违约|赔偿|索赔|争议|仲裁|诉讼|不可抗力)", text):
            return "CONTRACT_RISK", "contract liability/risk wording"
        if re.search(r"(验收|竣工验收)", text):
            return "CONTRACT_ACCEPTANCE", "contract acceptance wording"
        if re.search(r"(质保|保修)", text):
            return "PROJECT_WARRANTY", "warranty obligation inside the contract clause"
        return base, "contract payment terms"

    if base.startswith("BID_BOND"):
        if re.search(r"(基本账户|基本存款账户|开户许可证|转出)", text):
            return "BID_BOND_TRANSFER", "bond source account"
        if re.search(r"(到账|截止时间前)", text):
            return "BID_BOND_DEADLINE", "bond deadline"
        if re.search(r"(保函|电汇|转账|保险|形式)", text):
            return "BID_BOND_FORM", "bond form"
        if re.search(r"(凭证|回单|扫描件|复印件)", text):
            return "BID_BOND_EVIDENCE", "bond proof"
        if re.search(r"\d[\d,\.]*\s*(元|万元)", text):
            return "BID_BOND_AMOUNT", "bond amount"
        return base, "bond clause"

    if base == "SUBMISSION_DEADLINE":
        if re.search(r"(地点|方式|平台|送达|递交至)", text):
            return "SUBMISSION_PLATFORM", "submission place/method"
        if re.search(r"(正本|副本|份数|U盘|电子版)", text):
            return "SUBMISSION_COPIES", "copies/electronic copy"
        if re.search(r"(解密|签到)", text):
            return "OPENING_DECRYPTION", "opening/decryption"
        if _SUBMISSION_CUES.search(text):
            return "SUBMISSION_DEADLINE", "submission deadline"
        return "GENERAL_BIDDER_OBLIGATION", "no submission-specific content"

    if base == "ELECTRONIC_UPLOAD":
        if re.search(r"(解密|签到)", text):
            return "OPENING_DECRYPTION", "opening/decryption"
        if re.search(r"(上传|加密|CA|ca锁|电子)", text):
            return "ELECTRONIC_UPLOAD", "electronic upload/encryption"
        return "GENERAL_BIDDER_OBLIGATION", "no electronic-upload content"

    if base == "EVALUATION_SCORING":
        if _COLLUSION_CUES.search(text):
            return "EVALUATION_COLLUSION", "collusion/fraud wording inside the evaluation topic"
        if re.search(r"(得\s*\d+(?:\.\d+)?\s*分|分值|最高得?\s*\d+(?:\.\d+)?\s*分)", text):
            return "EVALUATION_SCORING", "scoring item"
        return "EVALUATION_SCORING", "evaluation-method clause"

    if base == "FILE_FORMAT":
        if _FORMAT_CUES.search(text):
            return "FILE_FORMAT", "response-file format requirement"
        if _COMPOSITION_CUES.search(text):
            return "FILE_COMPOSITION", "response-file composition requirement"
        return "UNSUPPORTED_FORMAT_CLAIM", "format topic without format source content"

    if base == "FILE_COMPOSITION":
        if re.search(r"异议", text):
            return "UNSUPPORTED_FORMAT_CLAIM", "objection-letter text is not file composition"
        if _COMPOSITION_CUES.search(text) or _FORMAT_CUES.search(text):
            return "FILE_COMPOSITION", "response-file composition requirement"
        return "GENERAL_BIDDER_OBLIGATION", "composition topic without composition content"

    if base == "PRICE_ITEMIZATION":
        if _ITEMIZATION_CUES.search(text):
            return "PRICE_ITEMIZATION", "itemised limit / provisional sum"
        return "PRICE_COMPLETENESS", "no itemised-limit source content"

    if base == "PRICE_CEILING" and not _PRICE_CEILING_CUES.search(text):
        return "PRICE_COMPLETENESS", "price topic without a ceiling value"

    if base == "PRICE_COMPLETENESS":
        if re.search(r"(税金|税率|含税|不含税)", text):
            return "PRICE_TAX_BASIS", "tax basis wording"
        if re.search(r"(大写|小写|单价|合计|总价)", text):
            return "PRICE_ARITHMETIC", "price arithmetic wording"
        return base, "price completeness wording"

    if base == "QUALIFICATION_FINANCIAL" and re.search(r"(资金来源|自筹|财政资金|资金来源为)", text):
        return "PROJECT_BASIC_INFO", "project financing is not a bidder financial duty"

    if base == "TECHNICAL_PROOF" and not scope:
        return base, "technical proof"

    return base, "topic prior"


def classify_concern(atom: SourceRequirementAtom) -> tuple[str, str]:
    """Resolve the atom's human review concern (``concern_id``, reason).

    Order: atom-level internality -> topic prior (+ sub-split) -> text cues.
    Never keyed on a case id.
    """

    text = atom.source_text
    if atom.internal and not _BIDDER_SUBJECT.search(text) and _INTERNAL_SUBJECT.search(text):
        return "INTERNAL_PROCEDURE", "internal procedure with no bidder-facing element"

    for pattern, concern_id, reason in _DECISIVE_RULES:
        if pattern.search(text):
            return concern_id, f"decisive: {reason}"

    base = _topic_concern(atom)
    if base:
        if base == "INTERNAL_PROCEDURE" and _BIDDER_SUBJECT.search(text):
            base = "GENERAL_BIDDER_OBLIGATION"
        override = _text_override(atom, base)
        if override is not None:
            return override
        return _sub_split(atom, base)

    # no topic prior: fall back to ordered text rules.  Inside the contract
    # template the contract concerns are consulted first, so a liability clause
    # is never re-labelled as a warranty requirement.
    if atom.authority_scope == SCOPE_CONTRACT_TEMPLATE:
        for rule in _CONCERN_RULES:
            if rule.concern_id in {"INTERNAL_PROCEDURE", "PROJECT_WARRANTY"}:
                continue
            if rule.scopes and rule.matches(atom):
                return rule.concern_id, f"contract scope: {rule.reason or rule.concern_id}"
    for rule in _CONCERN_RULES:
        if rule.concern_id == "INTERNAL_PROCEDURE":
            continue
        if rule.matches(atom):
            return rule.concern_id, rule.reason or f"rule {rule.concern_id}"

    if atom.actor == ACTOR_EVALUATION_COMMITTEE:
        return "INTERNAL_PROCEDURE", "evaluation-committee clause"
    if atom.authority_scope == SCOPE_CONTRACT_TEMPLATE:
        return "CONTRACT_RISK", "unclassified contract-template clause"
    if atom.actor == ACTOR_BIDDER:
        return "GENERAL_BIDDER_OBLIGATION", "bidder-facing clause without a finer concern"
    return "UNCLASSIFIED", "no bidder-facing concern recognised"


class _UnitLike:
    """Adaptor so round-2 helpers can be reused on an atom."""

    def __init__(self, atom: SourceRequirementAtom) -> None:
        self.text = atom.source_text
        self.topic = atom.topic
        self.requirement_type = atom.requirement_type
        self.requirement_id = atom.source_clause_id or atom.atom_id
        self.page = atom.source_page
        self.clause = atom.source_structure_id
        self.section = atom.source_section
        self.high_risk = atom.high_risk
        self.mandatory = atom.mandatory


def _unit_like(atom: SourceRequirementAtom) -> _UnitLike:
    return _UnitLike(atom)


# --------------------------------------------------------------------------- #
# atomization
# --------------------------------------------------------------------------- #

_SPLIT_RE = re.compile(r"(?<=[。；;])")
_MAX_ATOM_CHARS = 400
_MATERIAL_HINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("营业执照", re.compile(r"营业执照")),
    ("资质证书", re.compile(r"资质证书|资质等级")),
    ("财务审计报告", re.compile(r"财务审计|审计报告")),
    ("财务承诺函", re.compile(r"财务承诺")),
    ("信用查询截图", re.compile(r"信用中国|信用查询|失信被执行人")),
    ("无行贿犯罪记录承诺", re.compile(r"无行贿|行贿犯罪")),
    ("类似项目业绩证明", re.compile(r"类似业绩|类似项目业绩|业绩证明")),
    ("纳税与社保缴纳凭证", re.compile(r"纳税|税收|社保|社会保险")),
    ("法定代表人授权委托书", re.compile(r"授权委托书|授权书")),
    ("身份证扫描件", re.compile(r"身份证")),
    ("响应保证金转账凭证", re.compile(r"保证金[^。]{0,12}(凭证|回单)|(凭证|回单)[^。]{0,12}保证金")),
    ("基本账户开户许可证或基本存款账户信息", re.compile(r"基本账户|基本存款账户|开户许可证")),
    ("技术证明材料", re.compile(r"检测报告|检验报告|型式试验|认证证书|证明材料")),
    ("报价表", re.compile(r"报价表|开标一览表|分项报价")),
)


def split_source_text(text: str, atom_id_prefix: str = "") -> list[str]:
    """Split a source block into atom-sized sentences.

    Splitting is deliberately conservative: a sentence is kept whole unless it
    exceeds ``_MAX_ATOM_CHARS``, so semantic meaning is never destroyed just to
    obtain smaller atoms.
    """

    stripped = (text or "").strip()
    if not stripped:
        return []
    parts = [part.strip() for part in _SPLIT_RE.split(stripped) if part.strip()]
    atoms: list[str] = []
    for part in parts:
        if len(part) <= _MAX_ATOM_CHARS:
            atoms.append(part)
            continue
        # only split an over-long sentence at secondary separators
        chunks = [chunk.strip() for chunk in re.split(r"(?<=[，,])", part) if chunk.strip()]
        buffer = ""
        for chunk in chunks:
            if buffer and len(buffer) + len(chunk) > _MAX_ATOM_CHARS:
                atoms.append(buffer)
                buffer = chunk
            else:
                buffer = f"{buffer}{chunk}"
        if buffer:
            atoms.append(buffer)
    return atoms


def _materials_in(text: str) -> list[str]:
    return [name for name, pattern in _MATERIAL_HINTS if pattern.search(text)]


#: A retention clause frequently states two different facts in one sentence: the
#: money withheld (a ratio) and when it is released (a period).  Same keyword,
#: different concepts -- the ratio belongs to RETENTION_MONEY_RATIO and the
#: period to RETENTION_RELEASE_PERIOD.
_RETENTION_RATIO_RE = re.compile(
    r"\d+(?:\.\d+)?\s*%[^，,。；;]{0,12}(?:质保金|质量保证金|保证金|尾款|余款)"
    r"|(?:质保金|质量保证金|保证金|尾款|余款)[^，,。；;]{0,12}\d+(?:\.\d+)?\s*%"
)
_RETENTION_PERIOD_RE = re.compile(
    r"(?:质保期|保修期|质量保证期|缺陷责任期|保证期)\s*[:：]?\s*\d+(?:\.\d+)?\s*(?:个月|月|年|天|日)"
)


def _retention_ratio_atoms(atom: SourceRequirementAtom) -> list[SourceRequirementAtom]:
    """Derive the money facet of a combined retention clause as its own atom."""

    if atom.owner_concern_id != "RETENTION_RELEASE_PERIOD":
        return []
    text = atom.source_text
    ratio = _RETENTION_RATIO_RE.search(text)
    if ratio is None or not _RETENTION_PERIOD_RE.search(text):
        return []
    fragment = ratio.group(0).strip()
    if not fragment or fragment == text.strip():
        return []
    return [
        replace(
            atom,
            atom_id=f"{atom.atom_id}.r",
            source_text=fragment,
            owner_concern_id="RETENTION_MONEY_RATIO",
            owner_reason="decisive: retention-money ratio facet of a combined retention clause",
        )
    ]


def atomize_unit(unit: SourceRequirementUnit, *, index: int = 0) -> list[SourceRequirementAtom]:
    """Turn one round-2 unit into one or more atoms (1:1 whenever possible)."""

    sentences = split_source_text(unit.text) or [unit.text]
    atoms: list[SourceRequirementAtom] = []
    for offset, sentence in enumerate(sentences):
        atom_id = f"SRA{index + 1:04d}" if len(sentences) == 1 else f"SRA{index + 1:04d}.{offset + 1}"
        actor, _ = classify_actor(sentence)
        scope = classify_authority_scope(section=unit.section, clause=unit.clause, text=sentence)
        atom = SourceRequirementAtom(
            atom_id=atom_id,
            source_clause_id=unit.requirement_id,
            source_text=sentence,
            source_page=unit.page,
            source_section=unit.section,
            source_locator=unit.locator,
            source_structure_id=unit.clause,
            actor=actor,
            object=unit.topic,
            action=classify_action(sentence),
            topic=unit.topic,
            requirement_kind=unit.requirement_type,
            modality=classify_modality(sentence),
            applicability_scope=unit.topic,
            authority_scope=scope,
            requirement_type=unit.requirement_type,
            required_materials=_materials_in(sentence),
            explicit_consequence=(_CONSEQUENCE_RE.search(sentence).group(0) if _CONSEQUENCE_RE.search(sentence) else ""),
            explicit_score_rule=(_SCORE_RE.search(sentence).group(0) if _SCORE_RE.search(sentence) else ""),
            source_parent_id=unit.requirement_id,
            mandatory=unit.mandatory,
            high_risk=unit.high_risk,
            internal=is_internal_procedure(unit),
        )
        concern_id, reason = classify_concern(atom)
        atom.owner_concern_id = concern_id
        atom.owner_reason = reason
        atoms.append(atom)
        atoms.extend(_retention_ratio_atoms(atom))
    return atoms


def atomize_units(units: Sequence[SourceRequirementUnit]) -> list[SourceRequirementAtom]:
    atoms: list[SourceRequirementAtom] = []
    for index, unit in enumerate(units):
        atoms.extend(atomize_unit(unit, index=index))
    _apply_clause_context(atoms)
    atoms.extend(_retention_clause_atoms(atoms))
    return atoms


def _retention_clause_atoms(atoms: Sequence[SourceRequirementAtom]) -> list[SourceRequirementAtom]:
    """Ensure a clause that withholds money *and* fixes a period owns both facets.

    Sentence splitting can leave the ratio and the 质保金 wording in different
    atoms, so the money facet is derived once per clause when the clause as a
    whole is a retention clause (period + 质保金/尾款 wording + a ratio).
    """

    by_clause: dict[str, list[SourceRequirementAtom]] = {}
    for atom in atoms:
        # group by section, not by clause: the source often splits "剩余 5%" and
        # "作为质保金，质保期 12 个月" into two units of the same section.
        by_clause.setdefault(atom.source_section or atom.source_clause_id, []).append(atom)

    derived: list[SourceRequirementAtom] = []
    for group in by_clause.values():
        if any(atom.owner_concern_id == "RETENTION_MONEY_RATIO" for atom in group):
            continue
        joined = "".join(atom.source_text for atom in group)
        if not _RETENTION_PERIOD_RE.search(joined):
            continue
        if not re.search(r"质保金|质量保证金|尾款|余款", joined):
            continue
        ratio = re.search(r"\d+(?:\.\d+)?\s*%", joined)
        if ratio is None:
            continue
        start, end = ratio.span()
        fragment = joined[max(0, start - 10) : min(len(joined), end + 12)].strip()
        if not fragment:
            continue
        template = next(
            (atom for atom in group if atom.owner_concern_id == "RETENTION_RELEASE_PERIOD"),
            group[0],
        )
        derived.append(
            replace(
                template,
                atom_id=f"{template.atom_id}.r",
                source_text=fragment,
                owner_concern_id="RETENTION_MONEY_RATIO",
                owner_reason="decisive: retention-money ratio facet (clause level)",
                required_materials=[],
                explicit_consequence="",
                explicit_score_rule="",
            )
        )
    return derived


def _apply_clause_context(atoms: Sequence[SourceRequirementAtom]) -> None:
    """Let an anaphoric atom (``此项``/``本项``) adopt its clause's strong concern.

    Only siblings **inside the same source clause** are consulted, and only for
    concerns that are semantically strong (qualification/consortium/etc.).  This
    is not keyword inheritance from a neighbouring paragraph: the pronoun refers
    to the same requirement.
    """

    by_clause: dict[str, list[SourceRequirementAtom]] = {}
    for atom in atoms:
        by_clause.setdefault(atom.source_clause_id, []).append(atom)
    for siblings in by_clause.values():
        strong = {
            atom.owner_concern_id
            for atom in siblings
            if atom.owner_concern_id in _STRONG_CONCERNS
        }
        if len(strong) != 1:
            continue
        target = next(iter(strong))
        for atom in siblings:
            if atom.owner_concern_id == target:
                continue
            if not _ANAPHORIC.search(atom.source_text):
                continue
            atom.owner_concern_id = target
            atom.owner_reason = f"anaphoric reference to clause concern {target}"


# --------------------------------------------------------------------------- #
# ReviewConcern
# --------------------------------------------------------------------------- #


@dataclass
class ReviewConcern:
    """One human decision/action plus the components it owns."""

    concern_id: str
    label: str
    question: str
    atoms: list[SourceRequirementAtom] = field(default_factory=list)
    topic: str = ""
    multi_concern_reuse: bool = False

    @property
    def atom_ids(self) -> list[str]:
        return [atom.atom_id for atom in self.atoms]

    @property
    def clause_ids(self) -> list[str]:
        return sorted({atom.source_clause_id for atom in self.atoms})

    @property
    def is_bidder_facing(self) -> bool:
        return concern_spec(self.concern_id).bidder_facing

    def owned_numbers(self) -> list[NumericEvidence]:
        roles = concern_spec(self.concern_id).numeric_roles
        owned: list[NumericEvidence] = []
        seen: set[tuple[str, str]] = set()
        for atom in self.atoms:
            for value in extract_numeric_evidence([_unit_like(atom)]):
                # ownership is decided by the semantic role, not by the round-2
                # usability gate (which is keyed on the old requirement_type)
                if value.role not in roles:
                    continue
                key = (value.value, value.role)
                if key in seen:
                    continue
                seen.add(key)
                owned.append(value)
        return owned

    def owned_materials(self) -> list[str]:
        materials: list[str] = []
        for atom in self.atoms:
            for name in atom.required_materials:
                if name not in materials:
                    materials.append(name)
        return materials

    def owned_consequence(self) -> tuple[str, str]:
        for atom in self.atoms:
            marker = atom.explicit_consequence
            if not marker:
                continue
            if marker in _SCORE_ONLY_CONSEQUENCES and self.concern_id != "EVALUATION_SCORING":
                continue  # a score loss is not this concern's failure consequence
            return marker, atom.atom_id
        return "", ""

    def owned_score_rule(self) -> tuple[str, str]:
        for atom in self.atoms:
            if atom.explicit_score_rule:
                return atom.source_text, atom.atom_id
        return "", ""

    def as_dict(self) -> dict[str, Any]:
        consequence, consequence_atom = self.owned_consequence()
        score_text, score_atom = self.owned_score_rule()
        return {
            "concern_id": self.concern_id,
            "label": self.label,
            "question": self.question,
            "topic": self.topic,
            "atom_count": len(self.atoms),
            "atom_ids": self.atom_ids,
            "clause_ids": self.clause_ids,
            "owned_numbers": [value.as_dict() for value in self.owned_numbers()],
            "owned_materials": self.owned_materials(),
            "owned_consequence": consequence,
            "owned_consequence_atom": consequence_atom,
            "owned_score_rule": score_text,
            "owned_score_atom": score_atom,
            "multi_concern_reuse": self.multi_concern_reuse,
            "bidder_facing": self.is_bidder_facing,
        }


def build_concerns(atoms: Sequence[SourceRequirementAtom]) -> list[ReviewConcern]:
    """Group atoms by the concern they own (one concern per human question)."""

    by_id: dict[str, ReviewConcern] = {}
    for atom in atoms:
        concern = by_id.get(atom.owner_concern_id)
        if concern is None:
            spec = concern_spec(atom.owner_concern_id)
            concern = ReviewConcern(
                concern_id=atom.owner_concern_id,
                label=spec.label,
                question=spec.question,
                topic=atom.topic,
            )
            by_id[atom.owner_concern_id] = concern
        concern.atoms.append(atom)
    return list(by_id.values())


def actionable_concerns(concerns: Sequence[ReviewConcern]) -> tuple[list[ReviewConcern], list[ReviewConcern]]:
    """Split concerns into (bidder-facing, filtered) without deleting evidence.

    A concern that is not bidder-facing (purchaser-internal procedure, pure
    definition) never becomes an *ordinary* bidder row: either it is filtered
    out, or -- when a mandatory/high-risk clause would otherwise lose coverage --
    it is kept and synthesized as an explicitly non-bidder "备查" row.
    """

    kept: list[ReviewConcern] = []
    filtered: list[ReviewConcern] = []
    for concern in concerns:
        if concern.is_bidder_facing:
            kept.append(concern)
            continue
        if any(atom.mandatory or atom.high_risk for atom in concern.atoms):
            kept.append(concern)  # coverage never lost to the actionability filter
            continue
        filtered.append(concern)
    return kept, filtered


# --------------------------------------------------------------------------- #
# ownership gate
# --------------------------------------------------------------------------- #


def component_owned(component_concern_id: str, concern_id: str, *, reuse_ok: bool = False) -> bool:
    if component_concern_id == concern_id:
        return True
    if reuse_ok and concern_spec(concern_id).allows_reuse:
        return True
    return False


def ownership_violations(
    concern: ReviewConcern,
    *,
    rendered_numbers: Sequence[NumericEvidence] | None = None,
    rendered_materials: Sequence[str] | None = None,
    rendered_consequence: str | None = None,
    rendered_evidence: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    """Component-vs-concern mismatch buckets for one concern.

    A component passes only when it is source-backed **and** owned by the same
    concern.  ``rendered_*`` are the values a ReviewPoint would actually show;
    when omitted they default to the concern's own owned components (the
    greenfield case).  Every bucket must be empty for an accepted row.
    """

    spec = concern_spec(concern.concern_id)
    reuse_ok = spec.allows_reuse
    violations: dict[str, list[str]] = {
        "source_concern_mismatch": [],
        "numeric_concern_mismatch": [],
        "material_concern_mismatch": [],
        "consequence_concern_mismatch": [],
        "evidence_concern_mismatch": [],
        "authority_scope_mismatch": [],
        "foreign_role_numeric": [],
    }
    if not concern.atoms:
        violations["evidence_concern_mismatch"].append(f"{concern.concern_id}:{concern.topic}:no owned source atom")

    owned_numbers: dict[tuple[str, str], str] = {}
    for value in concern.owned_numbers():
        owned_numbers[(value.value, value.role)] = value.unit_id

    for atom in concern.atoms:
        if not component_owned(atom.owner_concern_id, concern.concern_id, reuse_ok=reuse_ok):
            violations["source_concern_mismatch"].append(f"{atom.atom_id}({atom.owner_concern_id})")
        if atom.authority_scope not in AUTHORITY_SCOPES:
            violations["authority_scope_mismatch"].append(f"{atom.atom_id}({atom.authority_scope})")
        for value in extract_numeric_evidence([_unit_like(atom)]):
            if not value.usable or value.role in {"", "OTHER"}:
                continue
            if value.role not in spec.numeric_roles and not reuse_ok:
                # a role-typed value that this concern does not own: it must
                # never be rendered here (round-3 fixture G class).
                violations["foreign_role_numeric"].append(f"{atom.atom_id}:{value.value}({value.role})")

    rendered_numbers = list(concern.owned_numbers()) if rendered_numbers is None else list(rendered_numbers)
    for value in rendered_numbers:
        if (value.value, value.role) not in owned_numbers:
            violations["numeric_concern_mismatch"].append(f"unowned:{value.value}({value.role})")
        elif value.role not in spec.numeric_roles and not reuse_ok:
            violations["numeric_concern_mismatch"].append(f"role:{value.value}({value.role})")

    rendered_materials = list(concern.owned_materials()) if rendered_materials is None else list(rendered_materials)
    owned_materials = set(concern.owned_materials())
    for name in rendered_materials:
        if name not in owned_materials:
            violations["material_concern_mismatch"].append(f"unowned:{name}")

    owned_consequence, consequence_atom = concern.owned_consequence()
    if rendered_consequence is None:
        rendered_consequence = owned_consequence
    if rendered_consequence and rendered_consequence != owned_consequence:
        violations["consequence_concern_mismatch"].append(
            f"unowned:{rendered_consequence[:30]}(owned={consequence_atom or 'none'})"
        )

    if rendered_evidence is not None:
        owned_evidence = set(concern.clause_ids)
        for evidence_id in rendered_evidence:
            if evidence_id not in owned_evidence:
                violations["evidence_concern_mismatch"].append(f"unowned:{evidence_id}")
    return violations


def coherence_ok(concern: ReviewConcern, **rendered: object) -> bool:
    """True when every recorded provenance independently carries its concern."""

    return all(not items for items in ownership_violations(concern, **rendered).values())


def grounded_atom(atom: SourceRequirementAtom, lines: Sequence[str]) -> bool:
    """Every rendered line must be grounded in the concern's own atoms."""

    terms = {term for line in lines for term in line.split()}
    return line_is_grounded(atom.source_text, terms) if terms else True
