"""Round 5.5 dynamic review items.

The review workbook is no longer a fixed 1..64 checklist.  ``rules/review_items.yaml``
stays in the project as a taxonomy/recall aid, but the substantive rows of
``投标项目复核表.xlsx`` are projected from the real source requirements indexed by
:mod:`tender_basic.dynamic_requirements`.

Pipeline::

    source document
      -> SourceRequirementUnit[]        (deterministic, evidence-backed)
      -> DynamicReviewItem[]            (grouped by requirement type + topic)
      -> 投标项目复核表.xlsx main sheet

Every review row answers: what does THIS tender require, what must be checked,
what counts as compliant, what happens on failure (only when the source says
so), and where the requirement comes from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from pydantic import Field

from .document_models import NormalizedDocument
from .evidence_unit import (  # noqa: E402
    EvidenceUnitIndex,
    NEW_ELEMENT_RE,
    _clause_of,
    _up_to_sentence_end,
    atom_clause_number,
    complete_fragment_backwards,
    dedupe_segments,
    extend_fragment,
    finish_from_unit,
    locator_for_atom,
    locator_section_for_unit,
    normalize_numeric_fragment,
    sentence_window,
    split_numbered_items,
    strip_leading_overlap,
)
from .source_applicability import (  # noqa: E402
    action_for_resolution,
    apply_applicable_resolutions,
    discover_schedule_rows,
    resolve_applicable_sources,
    resolution_for_concern,
    resolution_is_project_decision,
    risk_is_informational,
)
from .dynamic_requirements import (
    MODULE_EVALUATION,
    MODULE_EVALUATION_QUALITATIVE,
    MODULE_ORDER,
    RISK_BY_TYPE,
    TOPIC_LEXICON,
    VALUE_TYPES,
    RequirementIndex,
    SourceRequirementUnit,
    build_requirement_index,
    compact_text,
    extract_values,
    topic_patterns,
)
from .models import ContractModel, FactStatus, FieldName, ProjectFacts
from .concern_contract import contract_for as concern_contract_for  # noqa: E402
from .concern_contract import owned_text, validate_point  # noqa: E402
from .output_helpers import value_text
from .review_concern import actionable_concerns, atomize_units, build_concerns, concern_spec
from .review_point import (
    CONCERN_CHECKS,
    CONCERN_PASS_CRITERIA,
    ReviewPoint,
    _dedupe_repeated_phrases,
    _scoring_enumeration,
    render_checks,
    render_review_cell,
    scoring_enumeration_span,
    synthesize_concern_point,
    synthesize_review_point,
    value_sentence,
)
from .review_rendering import (
    CRITICALITY_NOTE,
    EVIDENCE_SUMMARY,
    FAILURE_CONSEQUENCE,
    LINKED_FACT,
    NUMERIC_STATEMENT,
    PASS_CRITERION,
    PREPARATION_MATERIAL,
    REVIEW_CHECK,
    SCORING_GUIDANCE,
    SOURCE_REQUIREMENT,
    ComponentOwnership,
    RenderedReviewComponent,
    mismatch_counts,
    numeric_tokens,
    verify_component,
)
from .semantic_roles import ROLE_TIER_SCORE
from .source_criticality import (
    BASIS_REFERENCE_PROPAGATION,
    BASIS_SOURCE_MARKER,
    CRITICALITY_ORDINARY,
    REJECTION_EXPLICIT,
    SEMANTICS_PROOF,
    SEMANTICS_SCORING,
    SEMANTICS_UNESTABLISHED,
    VISIBLE_MARKER,
    CriticalityIndex,
    SourceRequirementCriticality,
    build_criticality_index,
)

_STATUS_PENDING = "待核对"
_MONEY_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:万元|元)")
_DURATION_RE = re.compile(r"\d+\s*(?:个)?(?:日历天|自然日|日|天|个月|月|年)")
_SCORE_RE = re.compile(r"\d+(?:\.\d+)?\s*分")

#: Field mapping used to inject resolved ProjectFacts values into a review row.
FACT_FOR_TYPE: dict[str, tuple[str, ...]] = {
    "PRICING": ("max_price", "budget"),
    "BOND": ("bid_bond_amount", "bid_bond_form"),
    "VALIDITY": ("bid_validity",),
    "DURATION": ("duration",),
    "LOCATION": ("project_location",),
    "QUALITY": ("quality_target",),
    "CONSORTIUM": ("consortium_allowed",),
    "WARRANTY": ("quality_target",),
}

FACT_LABELS: dict[str, str] = {
    "max_price": "最高限价",
    "budget": "预算金额",
    "bid_bond_amount": "投标保证金金额",
    "bid_bond_form": "投标保证金形式",
    "bid_validity": "投标有效期",
    "duration": "工期/供货期",
    "project_location": "交付地点",
    "quality_target": "质量要求",
    "consortium_allowed": "联合体",
    "purchaser": "招标人/采购人",
}

#: Concrete verification actions per topic.  Each entry receives the source
#: topic text and the concrete values found in the backing clauses, so the row
#: never falls back to generic wording when the tender states the requirement.
#: The templates deliberately avoid naming materials the source may not
#: require; a concept guard strips any term the backing clauses do not contain.
_ACTION_BY_TOPIC: dict[str, str] = {
    "报价超过最高限价": "逐项核对投标报价表中的总价与分项报价，与上述限价逐条比对，确认无任何一项超出。",
    "未按要求签字盖章": "逐页核对招标文件指定位置的签字、盖章、电子签章是否齐全，并确认签署人与授权委托书一致。",
    "联合体不符合要求": "确认是否递交联合体协议；若招标文件不接受联合体，确认响应文件中无联合体成员、联合体协议或联合体承诺。",
    "违法分包转包挂靠": "确认响应文件中无违法分包、转包、挂靠承诺或安排，并与承诺函内容一致。",
    "投标有效期不足": "核对响应函中承诺的有效期是否达到上述天数，且覆盖至评审、定标完成。",
    "保证金不符合要求": "核对缴纳凭证、付款主体、账户信息与到账时间，确认与上述金额、形式和截止时间一致。",
    "资格条件不符合": "逐条核对营业执照、许可证书、资格证明材料是否满足上述资格条件，并确认有效期。",
    "未实质性响应": "逐条比对招标文件实质性要求与响应文件对应条款，统计正负偏离，确认无负偏离、无缺漏。",
    "投标文件不完整或格式不符": "按招标文件目录逐项清点响应文件组成，确认无缺页、漏表、漏附件，格式与固定格式一致。",
    "关键信息不一致或异常一致": "全文核对项目名称、编号、投标人名称、报价、工期等关键字段的一致性，并排查制作机器识别信息异常一致的风险。",
    "解密失败或未按时递交": "在规定时间内完成上传、签到与解密，提前验证CA介质、客户端与网络环境。",
    "报价异常或选择性报价": "核对报价表是否只有一个有效总报价，无被招标文件禁止的报价形式。",
    "其他否决情形": "按上述条款逐条核对是否存在否决/无效情形，并留存核对记录。",
    "禁止性情形与失信排除": "按规定平台查询并留存查询结果，确认不存在上述禁止性情形。",
    "串通投标或弄虚作假": "核验业绩、证书、人员材料的真实性，排查与其他投标人文件、联系信息、制作信息雷同等情形。",
    "定性评审与定标": "按招标文件定性评审/定标程序准备评审材料，逐项对应评审要素，确保定标所需材料齐全。",
    "评分标准与分值构成": "将评分/评审因素拆解为“得分条件-证明材料-响应文件页码-预估得分”，逐项落实证明材料来源。",
    "业绩评分": "核对业绩时间、金额、项目类型与证明链是否符合评分口径。",
    "人员评分": "核对拟投入人员的证书、职称与劳动关系，并确认与评分要求一致。",
    "价格评分与基准价": "核对价格评分公式、基准价规则与异常低价风险，确认报价处于可评审区间。",
    "技术评分": "核对技术方案的响应深度与证明材料，确保评分点均有对应章节和页码。",
    "最高限价与控制价": "在报价表中逐项核对总价及分项报价，确认均不超过上述限价，并核对暂估价、暂列金额是否按给定金额计入。",
    "分项限价与暂列金额": "按工程量清单/分项限价表逐项核对分项报价，确认暂估价、暂列金额按给定金额计取。",
    "报价组成与费用范围": "核对报价表口径、单价、数量、合价与费用范围，确认无漏项、无重复计取。",
    "保证金金额": "核对响应文件中的保证金金额与上述金额一致，并与缴纳凭证金额对应。",
    "保证金形式": "核对保证金缴纳形式是否属于上述允许形式，凭证类型与形式一致。",
    "保证金递交与凭证": "核对付款主体、账户信息、到账时间与凭证归档位置，确认在规定时间前到账。",
    "投标保证金": "核对保证金金额、形式、到账时间与凭证，确认满足上述全部要求。",
    "投标有效期": "核对响应函承诺的有效期天数与起算点，并确认覆盖评审与定标周期。",
    "签字盖章要求": "按招标文件签章要求逐页核对签字人、盖章种类与位置，确认授权链条完整。",
    "CA与电子签章": "验证CA介质/数字证书有效性、签章位置与签章后的文件可验证性，确认使用本单位证书。",
    "加密上传与解密": "按平台要求完成加密、上传与解密演练，确认文件格式、大小与上传区域符合要求。",
    "联合体": "确认响应文件中的联合体安排与上述要求一致，联合体协议（如允许）内容完整。",
    "分包与转包": "确认响应文件无违规分包、转包安排，分包范围（如允许）符合上述限制。",
    "营业执照与独立法人": "核对营业执照主体名称、统一社会信用代码、经营范围与独立法人资格，扫描件清晰并按要求盖章。",
    "资质等级与许可": "核对许可证书的类别、等级、有效期与发证机关，确认满足上述要求。",
    "信用与失信查询": "在指定平台查询并留存查询结果，确认无上述禁止性记录。",
    "特定资格条件": "逐条核对特定资格条件对应的证明材料是否齐全有效。",
    "项目负责人资格": "核对拟派项目负责人的注册证书、执业资格与在岗情况，确认符合上述要求。",
    "安全与管理人员": "核对安全管理人员的证书类别、有效期与配备数量，确认满足上述要求。",
    "人员社保与劳动关系": "核对社保缴纳证明的月份区间、缴费单位与投标人名称的一致性。",
    "人员配置要求": "按招标文件人员配置表逐岗核对人员、证书与证明材料。",
    "类似项目业绩": "核对类似业绩的时间、金额、规模与证明链，确认满足上述数量与口径。",
    "财务与审计报告": "按上述年度/期间提供对应的财务材料，核对主体名称、数据口径与盖章。",
    "纳税与社保凭证": "按指定月份/周期提供对应的缴纳证明，核对缴费主体与期间。",
    "财务承诺函": "按招标文件格式出具财务能力承诺，核对承诺内容与上述要求一致。",
    "★条款与强制参数": "逐条列示★/强制条款的响应值，确认无空白、无模糊表述，并附证明材料。",
    "技术参数与配置": "按技术参数表逐项填写响应值，确认与报价表、技术资料一致。",
    "接口与集成": "核对接口、协议、平台对接要求的技术方案与承诺，确认可实施。",
    "数据迁移与上线": "核对数据迁移范围、迁移方案、上线切换与回退预案，确认满足上述要求。",
    "安装调试与验收": "核对安装、调试、检测、验收标准与节点，确认与招标文件验收要求一致。",
    "培训与售后服务": "核对培训安排与售后服务响应时间、备件、服务网点承诺，确认可量化、可履约。",
    "技术方案与实施组织": "核对技术方案、进度计划、人员机具配置、质量保证与应急措施的完整性。",
    "质量要求": "核对质量承诺与招标文件质量目标/验收标准一致，并落入合同履约条款。",
    "工期与供货期": "核对响应函与进度计划中的工期/供货期是否满足上述天数，并覆盖全部交付节点。",
    "交付与实施地点": "核对交付/实施地点、批次与服务范围与上述要求一致。",
    "质保与保修": "核对质保期承诺是否不低于上述要求，并确认质保范围、响应方式与费用承担。",
    "合同条款与付款": "核对合同条款响应、付款方式、结算依据与违约责任，确认无采购人不能接受的附加条件。",
    "证明材料要求": "按上述要求准备证明材料，确认清晰、完整、可核验。",
    "投标文件格式": "按招标文件格式要求编排、装订、编制目录与页码，确认符合规定。",
    "投标文件组成": "按招标文件组成清单逐项清点响应文件章节与附表，确认无遗漏。",
    "递交方式与截止时间": "核对递交方式、递交地点/平台、截止时间要求，预留足够提前量。",
    "封装与密封": "核对正副本份数、密封方式、骑缝章与标注信息，确认符合上述要求。",
    "一般要求": "按上述招标文件条款逐项核对响应文件对应内容，确认完全响应。",
}

#: Terms that may only appear in a review row when the backing source clauses
#: contain them.  The guard keeps the row free of concepts the tender never
#: asked for (see Round 5.5 section H).
CONCEPT_TERMS: tuple[str, ...] = (
    "数据库",
    "中间件",
    "国产化",
    "操作系统",
    "培训",
    "软件",
    "云平台",
    "虚拟化",
    "信创",
    "审计报告",
    "财务报表",
    "社保",
    "社会保险",
    "技术参数",
    "检测报告",
    "银行转账",
    "基本账户",
    "基本户",
    "保函",
    "机器码",
    "CA",
    "电子印章",
    "中标通知",
    "发票",
    "★",
    "纳税",
    "完税",
    "资质",
    "许可证",
    "建造师",
)

_PASS_BY_TYPE: dict[str, str] = {
    "PRICING": "报价总价与各分项均不超过规定限价，且与报价表、一览表金额一致。",
    "BOND": "保证金金额、形式、到账时间与凭证全部符合上述要求。",
    "VALIDITY": "投标有效期承诺不低于规定天数，覆盖评审与定标全过程。",
    "SIGNATURE": "所有指定位置签字/盖章齐全有效，授权链条一致。",
    "ELECTRONIC": "CA介质有效、文件加密上传成功、可按时解密。",
    "REJECTION": "不存在上述任何否决/无效情形，逐条核对记录齐备。",
    "QUALIFICATION": "资格材料齐全有效，主体信息一致，满足全部资格条件。",
    "PERSONNEL": "拟投入人员的证书与劳动关系满足要求且相互一致。",
    "PERFORMANCE": "业绩数量、规模、时间与证明链满足招标文件口径。",
    "FINANCIAL": "财务材料按指定期间提供，主体名称与投标人一致。",
    "CREDIT": "指定平台查询结果无禁止性记录，并留存查询结果。",
    "CONSORTIUM": "联合体安排与招标文件要求完全一致。",
    "SUBCONTRACT": "无违规分包、转包、挂靠情形。",
    "DURATION": "工期/供货期承诺满足招标文件要求。",
    "LOCATION": "交付/实施地点与服务范围满足招标文件要求。",
    "QUALITY": "质量承诺满足招标文件质量目标与验收标准。",
    "WARRANTY": "质保期与质保范围不低于招标文件要求。",
    "TECHNICAL": "技术要求逐条响应，证明材料可核验，无负偏离。",
    "EVALUATION": "评分/评审因素逐条有对应响应内容与证明材料，预估得分可追溯。",
    "PROOF": "证明材料齐全、清晰并与响应内容对应。",
    "FORM": "响应文件格式、组成与编排符合招标文件规定。",
    "SUBMISSION": "在规定时间前按要求完成递交/上传与解密。",
    "PACKAGING": "封装、密封、份数与标注符合招标文件要求。",
    "CONTRACT": "合同条款、付款与履约承诺符合招标文件要求。",
    "OTHER": "响应内容与上述招标文件条款一致。",
}

_NEUTRAL_ACTION = "按上述招标文件条款逐项核对响应文件对应内容，确认完全响应。"
_NEUTRAL_PASS = "响应内容与上述招标文件条款一致。"


def _guard_concepts(text: str, backing: str) -> str:
    """Reject wording that names a concept this tender never asks for.

    Surgical removal left dangling connectors such as "提前验证、客户端与网络
    环境。", so an action or pass criterion that would name an unrequested concept
    is rejected outright and the caller falls back to neutral, concept-free
    wording instead.
    """

    lowered = backing.lower()
    for term in CONCEPT_TERMS:
        if term.lower() in text.lower() and term.lower() not in lowered:
            return ""
    return text.strip()

_CONSEQUENCE_PATTERNS = (
    "否决投标",
    "否决其投标",
    "将被否决",
    "予以否决",
    "投标被否决",
    "废标",
    "作废标处理",
    "无效投标",
    "投标无效",
    "响应无效",
    "响应文件无效",
    "按无效标处理",
    "不予评审",
    "取消投标资格",
    "取消中标资格",
    "不得参加",
)

_GENERIC_PHRASES = (
    "符合招标文件要求",
    "满足招标文件要求",
    "不得超过预算或最高限价",
    "按招标文件要求执行",
    "金额、形式、时间符合招标文件要求",
)


def _fact_value(project_facts: ProjectFacts | None, field: str) -> str:
    if project_facts is None:
        return ""
    fact = getattr(project_facts.fields, field, None)
    if fact is None or fact.status != FactStatus.RESOLVED:
        return ""
    return value_text(fact.resolved_value)


def _fact_locator(project_facts: ProjectFacts | None, field: str) -> str:
    if project_facts is None:
        return ""
    fact = getattr(project_facts.fields, field, None)
    if fact is None or fact.status != FactStatus.RESOLVED or not fact.candidates:
        return ""
    candidate = max(fact.candidates, key=lambda item: item.confidence)
    page = getattr(candidate.locator, "page", None)
    return f"第{page}页" if page else ""


class DynamicReviewItem(ContractModel):
    """One project-specific review row of the delivered workbook."""

    item_id: str = Field(pattern=r"^DR\d{3}$")
    module: str
    submodule: str = ""
    risk_level: str
    requirement_type: str
    topic: str
    source_requirement: str
    verification_action: str
    pass_criteria: str
    consequence_if_failed: str = ""
    source_locator: str
    source_page: int | None = None
    source_section: str = ""
    source_evidence: str
    source_requirement_ids: list[str] = Field(default_factory=list)
    related_project_fact: str = ""
    related_fact_value: str = ""
    applicable: bool = True
    confidence: float = 0.0
    status: str = _STATUS_PENDING
    values: list[str] = Field(default_factory=list)
    notes: str = ""
    cell_text: str = ""
    review_point: "ReviewPoint | None" = None
    # round 3: the human review concern that owns every rendered component
    concern_id: str = ""
    concern_label: str = ""
    # round 4: every material phrase rendered from this row, with the concern-owned
    # inputs it came from (see tender_basic.review_rendering)
    rendered_components: list[dict[str, Any]] = Field(default_factory=list)
    # round 6: source-visible criticality, derived from the source markers, the
    # document's own substantive-requirement definition and its consequence rules
    raw_source_markers: list[str] = Field(default_factory=list)
    marker_present: bool = False
    marker_semantics: str = ""
    substantive_requirement: bool = False
    substantive_basis_kind: str = ""
    substantive_basis_atom_ids: list[str] = Field(default_factory=list)
    rejection_consequence: bool = False
    rejection_kind: str = ""
    rejection_basis_atom_ids: list[str] = Field(default_factory=list)
    criticality_level: str = ""
    criticality_reason: str = ""
    mandatory_types: list[str] = Field(default_factory=list)
    reference_parent_atom_id: str = ""
    reference_target: str = ""
    #: Round 7: every source semantic unit the displayed requirement is composed
    #: from, explicitly linked.  A broad concern (contract risk) legitimately
    #: quotes several clauses, and the reviewer must be able to reach each of
    #: them; the row's primary locator is the first entry.
    evidence_units: list[dict[str, Any]] = Field(default_factory=list)
    #: Round 8: the row is a source-resolved project decision ("采购预备会 不召开",
    #: "分包 不允许").  It sorts last, which is what keeps a *displayed* risk
    #: correction from renumbering the rows the human's findings are addressed
    #: by.  It is not a risk claim: see ``risk_is_informational``.
    project_decision: bool = False


@dataclass(frozen=True)
class DynamicReviewPlan:
    items: tuple[DynamicReviewItem, ...]
    index: RequirementIndex
    source_requirement_count: int
    dropped_duplicate_count: int
    filtered_non_actionable_count: int = 0
    filtered_non_actionable_topics: tuple[str, ...] = ()
    #: Non-bidder-facing clauses kept for coverage/traceability.  They are never
    #: rendered as ordinary delivery rows (round-4 fixture: an internal-procedure
    #: row must not appear as a normal row, let alone a HIGH-risk one).
    background_items: tuple[DynamicReviewItem, ...] = ()
    #: Concerns whose owned source text is an extraction fragment (round-5
    #: fixture T: "意见》的通知中规定的收费标准的 70%向成交供应商").  They keep
    #: their evidence but are moved to NEEDS_REVIEW instead of being rendered as
    #: a fragment row the bidder cannot act on.
    needs_review_topics: tuple[str, ...] = ()
    #: Source clauses escalated to NEEDS_REVIEW (fixture T).  They are not
    #: rendered as rows but they are *not* dropped either: their coverage is
    #: reported here so a fragmentary clause cannot silently disappear.
    needs_review_clause_ids: tuple[str, ...] = ()
    #: Round 6: the document's own criticality model (source markers, governing
    #: substantive clause, consequence rules and the references between them).
    #: It is the source authority the rendered rows are audited against.
    criticality: CriticalityIndex | None = None

    def rows(self) -> list[DynamicReviewItem]:
        return list(self.items)

    def by_module(self) -> dict[str, list[DynamicReviewItem]]:
        grouped: dict[str, list[DynamicReviewItem]] = {}
        for item in self.items:
            grouped.setdefault(item.module, []).append(item)
        return grouped

    def module_counts(self) -> dict[str, int]:
        """JSON-safe module histogram (``by_module`` returns the items)."""

        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.module] = counts.get(item.module, 0) + 1
        return counts


def _unit_priority(item_topic: str):
    """Rank clause candidates: topic-central, concrete, authoritative, brief."""

    patterns = topic_patterns(item_topic)

    def key(unit: SourceRequirementUnit) -> tuple[int, int, int, int, int]:
        lowered = unit.text.lower()
        topic_hits = sum(1 for pattern in patterns if pattern.lower() in lowered)
        section = unit.section or ""
        authoritative = any(
            marker in section
            for marker in ("前附表", "评审", "评标", "须知", "公告", "资格", "合同", "需求", "技术")
        )
        # Prefer quotable clauses: a URL-heavy or very long sentence is poor
        # evidence for a review row even when it is topic-central.
        url_penalty = -lowered.count("http")
        return (
            topic_hits,
            url_penalty,
            1 if unit.values else 0,
            1 if authoritative else 0,
            -len(unit.text),
        )

    return key


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，,；;、 ") + "…"


def _compose_source_requirement(units: Sequence[SourceRequirementUnit], item_topic: str) -> str:
    ordered = sorted(units, key=_unit_priority(item_topic), reverse=True)
    excerpts: list[str] = []
    for unit in ordered:
        excerpt = _truncate(unit.text, 150)
        if any(excerpt[:24] == existing[:24] for existing in excerpts):
            continue
        excerpts.append(excerpt)
        if len(excerpts) == 3:
            break
    text = "；".join(excerpts)
    if len(ordered) > len(excerpts):
        text += f"（另见{len(ordered) - len(excerpts)}处同类条款）"
    return text


def _consequence(units: Sequence[SourceRequirementUnit], item_topic: str) -> str:
    for unit in sorted(units, key=_unit_priority(item_topic), reverse=True):
        for marker in _CONSEQUENCE_PATTERNS:
            position = unit.text.find(marker)
            if position < 0:
                continue
            start = max(0, position - 40)
            end = min(len(unit.text), position + len(marker) + 12)
            snippet = unit.text[start:end].strip("，,；;、 ")
            return snippet
    return ""


def _concrete_values(units: Sequence[SourceRequirementUnit]) -> list[str]:
    values: list[str] = []
    for unit in units:
        for value in unit.values:
            if value not in values:
                values.append(value)
    return values


def _compose_action(item_topic: str, values: Sequence[str], fact_text: str) -> str:
    action = _ACTION_BY_TOPIC.get(item_topic) or _ACTION_BY_TOPIC["一般要求"]
    if fact_text:
        return f"{action}（项目事实：{fact_text}）"
    if values:
        return f"{action}（须核对的具体值：{'、'.join(values[:6])}）"
    return action


def _compose_pass_criteria(requirement_type: str, values: Sequence[str], fact_text: str) -> str:
    base = _PASS_BY_TYPE.get(requirement_type, _PASS_BY_TYPE["OTHER"])
    if fact_text:
        return f"{base} 项目事实基准：{fact_text}。"
    if values:
        return f"{base} 具体指标：{'、'.join(values[:6])}。"
    return base


def _compose_cell_text(
    source_requirement: str,
    verification_action: str,
    pass_criteria: str,
    consequence: str,
) -> str:
    parts = [
        f"招标文件要求：{source_requirement}",
        f"复核动作：{verification_action}",
        f"核验标准：{pass_criteria}",
    ]
    if consequence:
        parts.append(f"不满足后果：{consequence}")
    return "\n".join(parts)


#: Unclassified clauses still have to land in a business module that matches
#: what they actually talk about.
_OTHER_MODULE_BY_TOPIC: dict[str, str] = {
    "费用与付款": "四、报价与合同商务",
    "合同责任": "四、报价与合同商务",
    "评审计分": "六、评分项复核",
    "文件组成与格式": "三、投标文件组成与格式",
    "程序性要求": "八、递交与开标准备",
    "其他要求": "三、投标文件组成与格式",
}


def _module_for(
    units: Sequence[SourceRequirementUnit],
    requirement_type: str,
    item_topic: str,
) -> str:
    module = units[0].module
    if requirement_type == "OTHER":
        module = _OTHER_MODULE_BY_TOPIC.get(item_topic, module)
    if module == MODULE_EVALUATION:
        text = " ".join(unit.text for unit in units)
        if any(marker in text for marker in ("定性评审", "评定分离", "定标")):
            return MODULE_EVALUATION_QUALITATIVE
    return module


def build_dynamic_review_plan(
    document: NormalizedDocument,
    project_facts: ProjectFacts | None = None,
    index: RequirementIndex | None = None,
) -> DynamicReviewPlan:
    """Project the source requirement index into project-specific review rows."""

    source_index = index if index is not None else build_requirement_index(document)
    # Round 3: atomize the source once, resolve each atom to the human review
    # concern it belongs to, and synthesize one row per concern.  A concern --
    # not the old (requirement_type, topic) bucket -- owns the rendered
    # requirement, numbers, materials, consequence and evidence.
    atoms = atomize_units(source_index.units)
    # Round 7: resolve the generic clauses that a project-specific schedule /
    # front table actually decides ("见供应商须知前附表" -> the schedule's own
    # value).  The generic clause is kept but marked superseded for display.
    schedule_rows = discover_schedule_rows(document)
    applicable_resolutions, atoms = apply_applicable_resolutions(
        atoms, resolve_applicable_sources(atoms, schedule_rows, document)
    )
    #: every source atom of the plan, so a row can reach the project-specific
    #: source it resolves to even when a sibling concern owns the generic clause
    stream_atoms = list(atoms)
    # Round 6: the source's own criticality semantics (raw emphasis markers, the
    # governing substantive-requirement clause, the consequence rules and the
    # explicit references those clauses use).  Derived from the document, never
    # from the generated rows.
    criticality = build_criticality_index(document, atoms)
    # Round 7: the evidence unit each atom is displayed from (page / heading /
    # clause / span), so the printed locator cannot describe another section.
    evidence_units = EvidenceUnitIndex.build(document, atoms)
    concerns = build_concerns(atoms)
    kept, filtered = actionable_concerns(concerns)
    # a new concern takes the next ids; the concerns already delivered keep theirs
    kept = _stable_concern_order(kept)
    units_by_id = {unit.requirement_id: unit for unit in source_index.units}

    items: list[DynamicReviewItem] = []
    background_items: list[DynamicReviewItem] = []
    needs_review_topics: list[str] = []
    needs_review_clause_ids: list[str] = []
    filtered_topics: list[str] = [
        f"{concern.label}（{concern.topic}）" for concern in filtered
    ]
    counter = 0
    for concern in kept:
        needs_review = ""
        reason_fn = getattr(concern, "needs_review", None)
        if callable(reason_fn):
            needs_review = str(reason_fn() or "")
        if needs_review:
            # Round 5 fixture T: fragments go to NEEDS_REVIEW, never to a row.
            needs_review_topics.append(f"{concern.label}（{concern.topic}）：{needs_review}")
            needs_review_clause_ids.extend(
                cid for cid in concern.clause_ids if cid in units_by_id
            )
            continue
        units = [units_by_id[cid] for cid in concern.clause_ids if cid in units_by_id]
        if not units:
            filtered_topics.append(f"{concern.label}（{concern.topic}）")
            continue
        spec = concern_spec(concern.concern_id)
        # Round 4: the row's presentation slot and its facts come from the
        # concern, not from whichever clause happened to be first (an
        # anti-bribery qualification concern must not be presented as a
        # signature row, and a retention clause must not link the quality target).
        requirement_type = spec.review_type or units[0].requirement_type
        topic = spec.review_topic or units[0].topic
        # a concern may declare the module it is *presented* in (the pre-bid
        # meeting decision belongs to the submission stage even though the clause
        # quoting it sits in the supplier-instructions chapter)
        module = str(getattr(spec, "review_module", "") or "") or _module_for(
            units, requirement_type, topic
        )
        fact_fields = tuple(field for field in FACT_FOR_TYPE.get(requirement_type, ()) if field in spec.fact_fields)
        fact_hints: dict[str, str] = {}
        related_field = ""
        related_value = ""
        for field in fact_fields:
            resolved = _fact_value(project_facts, field)
            if not resolved:
                continue
            locator = _fact_locator(project_facts, field)
            label = FACT_LABELS.get(field, field)
            fact_hints[field] = f"{label} {resolved}" + (f"（{locator}）" if locator else "")
            if not related_field:
                related_field = field
                related_value = resolved
        point = synthesize_concern_point(
            concern,
            fact_hints=fact_hints,
            linked_fields=tuple(field for field in fact_fields if field in fact_hints),
            requirement_type=requirement_type,
            topic=topic,
            requirement_override=_scoring_enumeration_of(concern, evidence_units),
        )
        if point is None:
            # Non-actionable or source-less concern: not a bidder review row.
            filtered_topics.append(f"{concern.label}（{topic}）")
            continue
        owned_numbers = list(concern.owned_numbers())
        owned_values = {value.value for value in owned_numbers}
        source_requirement = point.requirement_summary
        # Round 4: the row's numbers are the concern's *owned* numbers, rendered
        # with a role-appropriate sentence.  The old broad extractor could put a
        # neighbouring clause's quantity, contact or score into this row.
        values = [value.value for value in owned_numbers]
        verification_action = render_checks(point)
        operational_lead = ""
        pass_criteria = " ".join(point.pass_criteria)
        consequence = point.failure_consequence
        resolution = resolution_for_concern(
            concern, applicable_resolutions, point.requirement_summary
        )
        display_atoms: list[Any] = []
        if resolution is not None:
            # the resolution's own source atom is the row's evidence, even when the
            # concern reaches it through a generic clause it shares with another
            # concern: the displayed requirement comes from that atom, so the page,
            # section, clause and excerpt must come from it too
            specific = next(
                (
                    atom
                    for atom in getattr(concern, "atoms", ())
                    if str(getattr(atom, "atom_id", "")) == resolution.specific_atom_id
                ),
                None,
            )
            if specific is None:
                # the applicable atom may belong to a sibling concern that shares
                # the generic clause: it is still the row's own source
                specific = next(
                    (
                        atom
                        for atom in stream_atoms
                        if str(getattr(atom, "atom_id", "")) == resolution.specific_atom_id
                    ),
                    None,
                )
            primary_atom, primary = _primary_source(
                concern,
                units_by_id,
                units,
                spec.decisive_pattern,
                owned_values,
                point.requirement_summary,
                preferred_atom=specific,
            )
        else:
            primary_atom, primary = _primary_source(
                concern,
                units_by_id,
                units,
                spec.decisive_pattern,
                owned_values,
                point.requirement_summary,
            )
        locator, page, section, clause = locator_for_atom(
            primary_atom,
            evidence_units,
            fallback_page=getattr(primary, "page", None),
            fallback_section=str(getattr(primary, "section", "") or ""),
            fallback_clause=str(getattr(primary, "clause", "") or ""),
            fallback_kind=str(getattr(primary, "source_kind", "") or ""),
        )
        counter += 1
        item_id = f"DR{counter:03d}"
        if resolution is not None and resolution.specific_text:
            display_atoms = _display_atoms(concern, resolution, "", primary_atom)
            primary_atom, primary, _realigned = _realign_primary(
                primary_atom,
                primary,
                "",
                display_atoms,
                units_by_id,
                units,
            )
            locator, page, section, clause = locator_for_atom(
                primary_atom,
                evidence_units,
                fallback_page=getattr(primary, "page", None),
                fallback_section=str(getattr(primary, "section", "") or ""),
                fallback_clause=str(getattr(primary, "clause", "") or ""),
                fallback_kind=str(getattr(primary, "source_kind", "") or ""),
            )
        evidence_text = _evidence_excerpt(concern, primary_atom, evidence_units)
        # Round 9: the completion pass runs on every row, not only on rows without
        # an applicable source.  A schedule row's cell is split across a page
        # ("1.10.2 供应商提出问题的时间 提交响应文件截止时间 2 日前在“河南国企阳光招"
        # ends on page 9, the rest is on page 10), so a resolved row used to
        # deliver a requirement cut mid-parenthesis (round-9 fixture D56).
        repaired_summary = _complete_source_text(concern, point.requirement_summary, evidence_units)
        if resolution is not None and resolution.specific_text:
            source_requirement = normalize_numeric_fragment(
                _applicable_requirement(
                    repaired_summary,
                    resolution,
                    value_override=_complete_quote(
                        str(getattr(resolution, "specific_value_text", "") or ""),
                        evidence_text,
                    ),
                )
            )
        else:
            source_requirement = normalize_numeric_fragment(
                _displayed_requirement(concern, repaired_summary)
            )
        # Round 8: the extraction repeats a word it wrapped on ("…具备有效的营业
        # 执照 执照，准 供应商名称 供应商名称 与营业执照一致"), which delivers
        # duplicated wording.  The delivered requirement is therefore reduced to
        # the source's own single reading before it is rendered.
        source_requirement = dedupe_segments(
            _dedupe_repeated_phrases(source_requirement)
        )
        # Round 7 (§20): the row's evidence must be an atom the displayed
        # requirement actually comes from.  A concern can reach a clause through a
        # sibling concern's generic atom, which would otherwise print one clause's
        # text while citing another's page.  Re-point the row at the clause whose
        # own text the requirement quotes.
        display_atoms = _display_atoms(concern, resolution, source_requirement, primary_atom)
        primary_atom, primary, realigned = _realign_primary(
            primary_atom,
            primary,
            source_requirement,
            _facet_atoms(concern),
            units_by_id,
            units,
            str(getattr(concern, "concern_id", "") or ""),
        )
        if realigned:
            locator, page, section, clause = locator_for_atom(
                primary_atom,
                evidence_units,
                fallback_page=getattr(primary, "page", None),
                fallback_section=str(getattr(primary, "section", "") or ""),
                fallback_clause=str(getattr(primary, "clause", "") or ""),
                fallback_kind=str(getattr(primary, "source_kind", "") or ""),
            )
            evidence_text = _evidence_excerpt(concern, primary_atom, evidence_units)
        # Round 9: the anchor a delivered row cites must be the row's *own*
        # evidence unit.  The concern's atom list may reach a sibling clause
        # ("2.2.2 评审基准价" for a pricing-formula row whose own clause is
        # "2.2.4"), and the check text then sent the reviewer to a page/clause the
        # row does not quote (round-9 fixture D57).
        _retarget_anchor_checks(point, page, section, clause)
        verification_action = render_checks(point)
        if resolution is not None:
            operational = action_for_resolution(resolution, concern.label or topic)
            if operational:
                merged_action = _operational_action(verification_action, operational)
                if merged_action != verification_action:
                    # the operational action is *new* text for this row, so the
                    # cell renderer has to own it as a review check of its own
                    operational_lead = operational
                verification_action = merged_action
        display_atoms = _display_atoms(
            concern, resolution, source_requirement, primary_atom
        )
        row_criticality = criticality.for_atoms(
            list(getattr(concern, "atoms", ())), scope_atoms=display_atoms
        )
        components = _render_components(
            item_id=item_id,
            concern=concern,
            point=point,
            spec=spec,
            owned_numbers=owned_numbers,
            primary_atom=primary_atom,
            primary=primary,
            units=units,
            fact_hints=fact_hints,
            evidence_text=evidence_text,
            criticality=row_criticality,
            displayed_requirement=source_requirement,
            operational_action=operational_lead,
            # The ownership backing must be the same text the round-7 completion rule
            # already lets this row quote: the concern's atoms, the source units they
            # are displayed from, and the unit that continues each of them (a
            # contract sentence split across two blocks).  Otherwise a completion the
            # repair guard allows is rejected by the component check -- one row, two
            # different notions of what it owns.
            evidence_unit_text=_concern_evidence_backing(concern, evidence_units),
        )
        item = DynamicReviewItem(
            item_id=item_id,
            module=module,
            submodule=concern.label or topic,
            risk_level=_risk_level_for(
                requirement_type,
                row_criticality,
                informational=bool(
                    resolution is not None and risk_is_informational(resolution)
                ),
            ),
            requirement_type=requirement_type,
            topic=topic,
            source_requirement=source_requirement,
            verification_action=verification_action,
            pass_criteria=pass_criteria,
            consequence_if_failed=consequence,
            source_locator=locator,
            source_page=page,
            source_section=section,
            source_evidence=evidence_text,
            source_requirement_ids=[
                unit.requirement_id for unit in units
            ]
            + [merged for unit in units for merged in unit.merged_ids],
            related_project_fact=related_field,
            related_fact_value=related_value,
            confidence=round(
                sum(unit.mandatory or unit.high_risk for unit in units) / max(len(units), 1),
                3,
            ),
            values=values[:12],
            notes=point.notes,
            cell_text=cell_from_components(components),
            review_point=point,
            concern_id=point.concern_id,
            concern_label=point.concern_label,
            rendered_components=[component.as_dict() for component in components],
            raw_source_markers=(
                [row_criticality.raw_source_marker] if row_criticality.marker_present else []
            ),
            marker_present=bool(row_criticality.marker_present),
            marker_semantics=row_criticality.marker_semantics,
            substantive_requirement=bool(row_criticality.substantive_requirement),
            substantive_basis_kind=row_criticality.substantive_basis_kind,
            substantive_basis_atom_ids=list(row_criticality.substantive_basis_atom_ids),
            rejection_consequence=bool(row_criticality.rejection_consequence),
            rejection_kind=row_criticality.rejection_kind,
            rejection_basis_atom_ids=list(row_criticality.rejection_basis_atom_ids),
            criticality_level=row_criticality.criticality_level,
            criticality_reason=row_criticality.criticality_reason,
            mandatory_types=list(row_criticality.mandatory_types),
            reference_parent_atom_id=row_criticality.reference_parent_atom_id,
            reference_target=row_criticality.reference_target,
            evidence_units=_linked_evidence_units(
                source_requirement,
                primary_atom,
                evidence_units,
                display_atoms,
                locator=locator,
                page=page,
                section=section,
                clause=clause,
                excerpt=evidence_text,
            ),
            project_decision=bool(
                resolution is not None and resolution_is_project_decision(resolution)
            ),
        )
        if spec.bidder_facing:
            items.append(item)
        else:
            # Kept for coverage/traceability, never rendered as a delivery row.
            background_items.append(item)
    return DynamicReviewPlan(
        items=tuple(items),
        index=source_index,
        source_requirement_count=len(source_index.units),
        dropped_duplicate_count=source_index.merged_duplicates,
        filtered_non_actionable_count=len(filtered_topics),
        filtered_non_actionable_topics=tuple(filtered_topics),
        background_items=tuple(background_items),
        needs_review_topics=tuple(needs_review_topics),
        needs_review_clause_ids=tuple(dict.fromkeys(needs_review_clause_ids)),
        criticality=criticality,
    )


def _flatten(text: Any) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or ""))


def _facet_atoms(concern: Any) -> list[Any]:
    """The owned atoms that carry the concern's own facet (never empty)."""

    facet = list(getattr(concern, "facet_atoms", lambda: [])() or [])
    return facet or list(getattr(concern, "atoms", ()))


#: the source's own emphasis characters (round 6 vocabulary, discovered per case)
_SOURCE_MARKER_RE = re.compile(r"^\s*[\*★☆▲△●]")


def source_marked(atom: Any) -> bool:
    """Does the atom's own source text visibly carry an emphasis marker?"""

    return bool(_SOURCE_MARKER_RE.match(str(getattr(atom, "source_text", "") or "")))


def _scoring_enumeration_of(concern: Any, evidence_units: EvidenceUnitIndex) -> str:
    """The complete scoring enumeration of a concern's own evidence units.

    A scoring standard that awards points per alternative is extracted as several
    fragments ("分） 1、100%接受银行承兑的得 4 分；" / "2、50%…得 2 分；" /
    "50%以下…得 1 分。"), while the *unit* they were read from still carries the
    whole standard.  The delivered requirement and its tiers must come from that
    complete enumeration (round-9 fixtures D23/D38), so the unit texts of the
    concern's own atoms are searched for the reading with the most tiers.
    """

    texts: list[str] = []
    for atom in list(getattr(concern, "atoms", ())):
        evidence = evidence_units.for_atom(atom)
        if evidence is None:
            continue
        texts.append(str(evidence.unit.text_span or ""))
    complete = _scoring_enumeration(texts)
    if not complete:
        return ""
    return scoring_enumeration_span(complete)


#: The review check that names the page/clause the reviewer compares against.
_ANCHOR_CHECK_RE = re.compile(r"^依据.+?逐条比对响应文件对应章节$")


def _anchor_text(page: int | None, section: str, clause: str) -> str:
    """The row's own reference, in the form the check text uses."""

    if page and clause:
        return f"第{page}页第{clause}条"
    if page:
        return f"第{page}页"
    if section and not re.search(r"\d", section):
        return section[:12]
    return ""


def _retarget_anchor_checks(
    point: ReviewPoint, page: int | None, section: str, clause: str
) -> None:
    """Re-point every delivered anchor check at the row's own evidence unit."""

    target = _anchor_text(page, section, clause)
    if not target:
        return
    pattern = re.compile(r"^依据.+?逐条比对响应文件对应章节$")
    checks = list(point.review_checks)
    updated = [
        f"依据{target}逐条比对响应文件对应章节" if pattern.match(str(check)) else check
        for check in checks
    ]
    if updated != checks:
        point.review_checks = updated


def _display_atoms(
    concern: Any,
    resolution: Any = None,
    summary: str = "",
    primary_atom: Any = None,
) -> list[Any]:
    """The atoms this row actually displays, and therefore the atoms whose
    source criticality it may show.

    A concern groups every atom that answers one human question, including atoms
    that are only *related* to it; a marker or a rejection consequence carried by
    such a neighbour must not appear on this row (round-7 fixtures A/B/E).  The
    set is the atoms whose source text the row's displayed requirement literally
    quotes, plus the row's primary atom and the project-specific source that
    resolves the clause.
    """

    atoms = list(getattr(concern, "atoms", ()))
    if not atoms:
        return []
    if resolution is not None:
        specific = next(
            (
                atom
                for atom in atoms
                if str(getattr(atom, "atom_id", "")) == str(
                    getattr(resolution, "specific_atom_id", "") or ""
                )
            ),
            None,
        )
        if specific is not None:
            return [specific]
    quoted = [
        atom
        for atom in atoms
        if not getattr(atom, "superseded_for_display", False)
        and _grounded_in(str(summary or ""), [str(getattr(atom, "source_text", "") or "")])
    ]
    if primary_atom is not None and primary_atom not in quoted:
        quoted.append(primary_atom)
    # the same requirement clause may be stated twice (body clause + front-table
    # row): a marker on either copy belongs to the displayed requirement
    clauses = {
        atom_clause_number(atom) for atom in quoted if atom_clause_number(atom)
    }
    for atom in atoms:
        if atom in quoted or getattr(atom, "superseded_for_display", False):
            continue
        if atom_clause_number(atom) and atom_clause_number(atom) in clauses:
            quoted.append(atom)
        elif getattr(atom, "applicable_of_atom_id", ""):
            quoted.append(atom)
    # A directly source-marked clause of this concern is part of what the row
    # displays even when the summary quotes a sibling clause of the same
    # requirement (round-7: the electronic-upload row shows 3.7.4's ★ while its
    # wording comes from 4.2.4).
    facet_ids = {str(getattr(atom, "atom_id", "")) for atom in _facet_atoms(concern)}
    for atom in atoms:
        if atom in quoted or getattr(atom, "superseded_for_display", False):
            continue
        if str(getattr(atom, "atom_id", "")) in facet_ids and source_marked(atom):
            quoted.append(atom)
    if quoted:
        return quoted
    facet = list(getattr(concern, "facet_atoms", lambda: [])() or [])
    pool = facet or atoms
    visible = [atom for atom in pool if not getattr(atom, "superseded_for_display", False)]
    return visible or pool


def _applicable_requirement(summary: str, resolution: Any, value_override: str = "") -> str:
    """The displayed requirement: the project-specific value that now governs.

    Round 7: the schedule's own value *replaces* the generic template for
    display.  The generic clause is not part of the displayed requirement -- it
    is kept in the atom stream and in the resolution record for coverage,
    provenance and audit, and a marker or consequence that belonged to it is
    resolved through ``source_hierarchy_evidence``.  Repeating it inside the
    requirement cell would put a superseded clause back in front of the reviewer
    (and re-introduce its foreign facet text: "1.5.1 供应商资格能力和条件" inside
    the warranty row).

    ``value_override`` is the source's own complete wording of the value (a front
    table cell is split across a page, so the extracted value is frequently cut
    mid-sentence: "…同时将问题的电子版（附加", round-9 fixture D56).
    """

    specific = str(getattr(resolution, "specific_text", "") or "").strip()
    generic = str(summary or "").strip()
    if not specific:
        return generic
    value = value_override or str(getattr(resolution, "specific_value_text", "") or "").strip()
    if str(getattr(resolution, "relationship", "")) == "SPECIALIZES":
        # the clause states its own obligation and the schedule supplies one of
        # its parameters ("按供应商须知前附表规定的形式、金额…提交履约保证金"):
        # the project value joins the clause instead of replacing it
        if not value or _flatten(value) in _flatten(generic):
            return generic or value or specific
        return f"{generic}；项目专用值：{value}" if generic else value
    return specific


def _complete_quote(value: str, source_text: str) -> str:
    """The source's own complete wording of a quoted value.

    A front-table cell that continues on the next page is extracted in two
    pieces, so the schedule row's value can stop mid-sentence.  The row's own
    evidence carries the whole cell, and that wording is what may be displayed.
    """

    flat_value = _flatten(value)
    if not flat_value or not source_text:
        return value
    for sentence in re.split(r"(?<=[。；;！？!?])", str(source_text)):
        if flat_value in _flatten(sentence):
            complete = re.sub(r"[\s\u3000]+", " ", sentence).strip()
            if len(_flatten(complete)) >= len(flat_value):
                return complete
    return value


def _operational_action(checks: str, operational: str) -> str:
    """Put the project-value action first, keeping the owned checks after it."""

    lines = [line.strip() for line in str(checks or "").splitlines() if line.strip()]
    if not lines:
        return operational
    if operational in lines:
        return checks
    if operational.startswith(lines[0].lstrip("①②③④⑤⑥⑦⑧⑨ ")):
        return checks
    remainder = [_reletter(line, index) for index, line in enumerate(lines, start=2)]
    return "\n".join([f"① {operational}", *remainder])


_CHECK_MARKS = "①②③④⑤⑥⑦⑧⑨"


def _reletter(line: str, index: int) -> str:
    body = line.lstrip(_CHECK_MARKS + " ")
    if index <= len(_CHECK_MARKS):
        return f"{_CHECK_MARKS[index - 1]} {body}"
    return f"{index}. {body}"


def _evidence_excerpt(
    concern: Any,
    primary_atom: Any,
    evidence_units: EvidenceUnitIndex,
    fallback_text: str = "",
) -> str:
    """The row's source excerpt: the concern's own part of its primary atom.

    Round 7: the excerpt is trimmed to the code items / sentences the concern
    actually owns (an adjacent "资金来源：企业自筹" sentence is another concern's
    item, and must not sit inside this row's evidence), it is taken from the
    atom's own evidence unit so page, section and excerpt agree, it is aligned to
    sentence boundaries inside that unit, it is completed forwards/backwards when
    the extraction cut the sentence, and duplicated / placeholder numeric text is
    repaired.
    """

    concern_id = str(getattr(concern, "concern_id", "") or "")
    atom_text = str(
        getattr(primary_atom, "source_origin_text", "") or getattr(primary_atom, "source_text", "")
    )
    evidence = evidence_units.for_atom(primary_atom)
    span = evidence.span if evidence is not None else ""
    owned = owned_text(concern_id, atom_text)
    excerpt = owned or atom_text or str(fallback_text or "")
    if not excerpt:
        return ""
    if evidence is not None:
        window = sentence_window(evidence.unit.text_span, excerpt)
        # a unit window may only *grow* the excerpt: the atom's own head is never
        # replaced by a neighbouring unit's sentence
        if window and _flatten(excerpt) in _flatten(window):
            excerpt = window
        if not excerpt.rstrip().endswith(tuple("。；;！？!?")):
            excerpt = finish_from_unit(excerpt, evidence.unit.text_span)
        if not excerpt.rstrip().endswith(tuple("。；;！？!?")):
            excerpt = extend_fragment(excerpt, evidence.unit, evidence_units.units)
        if not excerpt.rstrip().endswith(tuple("。；;！？!?")):
            # the sentence continued into the *next* block, but the atom's own
            # text already covered part of that block: finish from its remainder
            excerpt = _finish_from_following(excerpt, evidence, evidence_units.units)
        # Round 7 (excerpt scope): the excerpt may complete the concern's own
        # sentence but must not grow into the next source unit's requirement
        base_text = owned or atom_text
        backing = _concern_evidence_backing(concern, evidence_units)
        if not _extension_stays_in_sentence(base_text, excerpt) or not _repair_stays_owned(
            base_text, excerpt, backing
        ):
            excerpt = base_text
        excerpt = _trim_to_facet(concern_id, excerpt, base=owned or atom_text)
        # the concern's own contract decides where its text stops: completing a
        # cut sentence must not import the *next* requirement of the clause
        # ("…损耗和税金等费用，设备安装调试完毕，…视为交付完成。").  A completion
        # that the contract keeps is a real continuation and is kept.
        trimmed = owned_text(concern_id, excerpt)
        if trimmed and len(_flatten(trimmed)) >= len(_flatten(owned or atom_text)):
            excerpt = trimmed
        elif _continuation_ok(atom_text, excerpt, concern_id):
            excerpt = trimmed or excerpt
        else:
            excerpt = owned or atom_text
        if len(split_numbered_items(excerpt)) > 1:
            # a multi-item block: keep only the items this concern owns, so an
            # adjacent item of another concern cannot sit in this row's evidence
            trimmed = owned_text(concern_id, excerpt)
            if trimmed:
                excerpt = trimmed
    excerpt = dedupe_segments(normalize_numeric_fragment(excerpt))
    excerpt = _trim_stray_leading_bracket(excerpt)
    if not excerpt:
        excerpt = str(atom_text or "")
    if not _grounded_in(excerpt, [atom_text, span]) and span:
        excerpt = normalize_numeric_fragment(span)
    # Round 7 (§20): the excerpt and the row's locator must describe one source
    # semantic unit.  A concern that owns a broad span of the document (a
    # contract-risk concern) can otherwise print a sentence while citing another
    # clause's row, so the excerpt is kept on the atom it actually came from.
    return _shorten(_clean_excerpt(_align_excerpt_to_atom(excerpt, atom_text)), 300)


def _align_excerpt_to_atom(excerpt: str, atom_text: str) -> str:
    """Keep the excerpt on the atom it came from.

    A broad concern (contract risk) owns clauses across the whole document; its
    rendered excerpt must still be a sentence its own evidence atom carries,
    otherwise the row's page and locator describe a different clause than the
    text the reviewer reads.
    """

    text = str(excerpt or "").strip()
    atom = _flatten(atom_text)
    if not text or not atom:
        return text
    if _grounded_in(text, [atom_text]):
        return text
    sentences = [piece for piece in re.split(r"(?<=[。；;])", text) if piece.strip()]
    if len(sentences) <= 1:
        return text
    for index, sentence in enumerate(sentences):
        if _grounded_in(sentence, [atom_text]):
            return "".join(sentences[index:]).strip()
    return text


def _displayed_requirement(concern: Any, summary: str) -> str:
    """The row's displayed requirement, trimmed to this concern's own facet.

    One source sentence frequently states two different requirements ("5.2 设备
    单价中含运输费…，设备安装调试完毕后，甲方负责人在验收单上签字…视为交付
    完成。").  The concern's contract decides where its requirement stops; the
    trimmed text is only used when it still carries the concern's own content, so
    a row never silently loses its requirement and never displays its neighbour's.
    """

    text = str(summary or "").strip()
    if not text:
        return text
    concern_id = str(getattr(concern, "concern_id", "") or "")
    owned = owned_text(concern_id, text)
    if not owned:
        return text
    if _flatten(owned) == _flatten(text):
        return text
    # keep the trim only when the concern's own requirement survives intact
    if _grounded_in(owned, [text]) and len(_flatten(owned)) >= 12:
        return owned
    return text


def _realign_primary(
    primary_atom: Any,
    primary: Any,
    requirement: str,
    display_atoms: Sequence[Any],
    units_by_id: Mapping[str, Any],
    units: Sequence[Any],
    concern_id: str = "",
) -> tuple[Any, Any, bool]:
    """Re-point a row's evidence at the clause its displayed requirement quotes.

    A concern can reach a project-specific source through a *sibling* concern's
    generic atom, which would print one clause's text while citing another's page,
    section and clause.  The row's evidence is therefore re-pointed at the owned
    atom whose own text the requirement carries -- but only when that atom's
    evidence *satisfies the concern's own contract*.  Re-pointing a row at a clause
    its contract forbids (a bid-bond row at an advance-payment guarantee) would
    trade a locator defect for a semantic one, so the renderer keeps its own clause
    in that case and the concern-grouping defect is reported instead.
    """

    from .concern_contract import contract_for

    text = str(requirement or "").strip()
    if not text or primary_atom is None:
        return primary_atom, primary, False
    atom_text = str(
        getattr(primary_atom, "source_origin_text", "") or getattr(primary_atom, "source_text", "")
    )
    if _grounded_in(text, [atom_text]):
        return primary_atom, primary, False
    spec = contract_for(str(concern_id or "")) if concern_id else None
    for atom in display_atoms:
        candidate_text = str(
            getattr(atom, "source_origin_text", "") or getattr(atom, "source_text", "")
        )
        if not candidate_text or not _grounded_in(text, [candidate_text]):
            continue
        if spec is not None:
            flat = _flatten(candidate_text)
            if spec.forbidden_evidence and any(
                re.search(pattern, flat) for pattern in spec.forbidden_evidence
            ):
                continue
            if spec.required_evidence and not any(
                re.search(pattern, flat) for pattern in spec.required_evidence
            ):
                continue
        unit = units_by_id.get(str(getattr(atom, "source_clause_id", "")))
        return atom, unit if unit is not None else primary, True
    return primary_atom, primary, False


def _span_coverage(text: str, spans: Sequence[str]) -> float:
    """What fraction of ``text`` is literally carried by ``spans``?

    A requirement may legitimately be stitched from a clause's own sentences, but
    when most of it comes from *another* clause the row's locator no longer
    describes what the reviewer reads.  Coverage is measured over overlapping
    windows so a single shared phrase cannot pass the check.
    """

    flat = _flatten(text)
    if not flat:
        return 1.0
    haystack = " ".join(_flatten(span) for span in spans if span)
    if not haystack:
        return 0.0
    windows = [flat[start : start + 12] for start in range(0, max(len(flat) - 11, 1), 6)]
    if not windows:
        return 1.0 if flat in haystack else 0.0
    hits = sum(1 for window in windows if len(window) >= 8 and window in haystack)
    return hits / len(windows)


def _exclude_foreign_requirement(
    requirement: str,
    concern: Any,
    primary_atom: Any,
    units_index: Any = None,
    evidence: Any = None,
) -> str:
    """Drop a displayed requirement the concern's own contract calls foreign.

    A concern's contract names the evidence it may not own ("预付款担保" is not a
    bid-bond-amount clause).  When the synthesized requirement is *itself* that
    foreign clause, the row must display the clause its own locator names instead;
    the foreign clause is not discarded -- it keeps its atom, its own row and its
    provenance.
    """

    text = str(requirement or "").strip()
    if not text or primary_atom is None:
        return text
    concern_id = str(getattr(concern, "concern_id", "") or "")
    if not concern_id:
        return text
    from .concern_contract import contract_for

    spec = contract_for(concern_id)
    flat = _flatten(text)
    if not spec.forbidden_evidence or not any(
        re.search(pattern, flat) for pattern in spec.forbidden_evidence
    ):
        return text
    # the whole requirement is the foreign clause: rebuild it from the atom the
    # row's own locator and excerpt describe
    atom_text = str(
        getattr(primary_atom, "source_origin_text", "") or getattr(primary_atom, "source_text", "")
    )
    unit_text = ""
    if evidence is not None:
        unit_text = str(getattr(getattr(evidence, "unit", None), "text_span", "") or "")
    for candidate in (owned_text(concern_id, atom_text), unit_text, atom_text):
        candidate = str(candidate or "").strip()
        if not candidate:
            continue
        flat_candidate = _flatten(candidate)
        if any(re.search(pattern, flat_candidate) for pattern in spec.forbidden_evidence):
            continue
        window = sentence_window(unit_text, candidate) if unit_text else ""
        if window and _grounded_in(window, [unit_text]):
            return window
        return candidate
    return text


def _linked_evidence_units(
    requirement: str,
    primary_atom: Any,
    units_index: EvidenceUnitIndex,
    display_atoms: Sequence[Any],
    *,
    locator: str,
    page: int | None,
    section: str,
    clause: str,
    excerpt: str,
) -> list[dict[str, Any]]:
    """Every source unit the displayed requirement is composed from (§20).

    A broad concern (contract risk) legitimately quotes several clauses: the row
    then carries an explicit, source-backed link for each one, so the reviewer can
    verify every sentence.  The primary unit comes first and is the one the row's
    page/section/clause/excerpt describe; further units are linked only when they
    actually add text the requirement needs.
    """

    primary_evidence = units_index.for_atom(primary_atom)
    # the delivered locator's section, where production derived it from, and the
    # clip limit that derivation applied -- recorded so an audit compares the
    # visible section against this exact value instead of a prefix of the heading
    section_source, section_clip_limit = "none", None
    if primary_evidence is not None:
        _visible, section_source, section_clip_limit = locator_section_for_unit(
            primary_evidence.unit, primary_evidence.span
        )
    out: list[dict[str, Any]] = [
        {
            "role": "PRIMARY",
            "atom_id": str(getattr(primary_atom, "atom_id", "") or ""),
            "unit_id": primary_evidence.unit.unit_id if primary_evidence is not None else "",
            # the exact span handover the locator derivation was given, recorded so
            # the round-9 acceptance audit can re-run the *production* formatter
            # over the canonical unit (rebuilt from the document) and compare its
            # own output with the saved cell -- the span is the only input the
            # formatter takes besides the unit itself
            "unit_span": primary_evidence.span if primary_evidence is not None else "",
            # ``locate_atom`` keys the unit by the *atom's* own leading clause when
            # the atom states one ("15.4.1 保修责任 …" anchored in a body block),
            # which is what decides whether the section falls back to the review
            # point's own section.  The override is recorded so the audit can
            # rebuild the same effective unit instead of guessing it.
            "atom_clause": _clause_of(str(getattr(primary_atom, "source_text", "") or "")),
            "page": page,
            "section": section,
            "section_source": section_source,
            "section_clip_limit": section_clip_limit,
            "clause": clause,
            "locator": locator,
            "span": excerpt,
        }
    ]
    text = str(requirement or "")
    if not text:
        return out
    covered = str(excerpt or "")
    seen = {str(getattr(primary_atom, "atom_id", "") or "")}
    # link the units that carry the parts of the requirement the primary does not
    while _span_coverage(text, [covered]) < 1.0:
        best: tuple[float, Any, Any] | None = None
        for atom in display_atoms:
            atom_id = str(getattr(atom, "atom_id", "") or "")
            if not atom_id or atom_id in seen:
                continue
            evidence = units_index.for_atom(atom)
            if evidence is None:
                continue
            gain = _span_coverage(text, [covered, evidence.unit.text_span]) - _span_coverage(
                text, [covered]
            )
            if gain <= 0:
                continue
            if best is None or gain > best[0]:
                best = (gain, atom, evidence)
        if best is None:
            break
        _gain, atom, evidence = best
        seen.add(str(getattr(atom, "atom_id", "") or ""))
        covered = f"{covered} {evidence.unit.text_span}"
        out.append(
            {
                "role": "LINKED",
                "atom_id": str(getattr(atom, "atom_id", "") or ""),
                "unit_id": evidence.unit.unit_id,
                "page": evidence.unit.page,
                "section": evidence.unit.heading or evidence.unit.semantic_heading,
                "clause": evidence.unit.clause_number,
                "locator": evidence.locator,
                "span": evidence.span,
            }
        )
    return out


def _confine_requirement_to_unit(
    requirement: str,
    atom: Any,
    evidence: Any,
    units_index: Any = None,
    concern_id: str = "",
) -> str:
    """Confine a displayed requirement to the unit its locator names (§20).

    A concern such as contract risk owns clauses across the whole document, and
    its synthesized summary can splice one clause's sentence together with a
    *different* clause's sentence.  The row then prints text its located
    page/section/clause does not carry, so the reviewer cannot verify what they
    read: the requirement is rebuilt from the atom that the row's locator and
    excerpt describe.

    Nothing is discarded silently: the other clauses remain in the atom stream, in
    the row's source requirement ids and in the concern's provenance.
    """

    text = str(requirement or "").strip()
    if not text or evidence is None or atom is None:
        return text
    unit = getattr(evidence, "unit", None)
    unit_text = str(getattr(unit, "text_span", "") or "")
    if not unit_text:
        return text
    if _span_coverage(text, [unit_text]) >= 0.6:
        return text
    # the requirement may legitimately continue into the neighbour block
    neighbours: list[str] = []
    if units_index is not None and unit is not None:
        for candidate in getattr(units_index, "units", ()) or ():
            if candidate.order in {unit.order - 1, unit.order + 1} and candidate.page == unit.page:
                neighbours.append(str(candidate.text_span))
    if neighbours and _span_coverage(text, [unit_text, *neighbours]) >= 0.6:
        return text
    # rebuild from the atom the locator names
    atom_text = str(
        getattr(atom, "source_origin_text", "") or getattr(atom, "source_text", "")
    )
    owned = owned_text(concern_id, atom_text) if concern_id else atom_text
    candidate = owned or atom_text
    if not candidate:
        return text
    window = sentence_window(unit_text, candidate)
    if window and _grounded_in(window, [unit_text]):
        return window
    if _grounded_in(candidate, [unit_text]):
        return candidate
    # the atom's own text is a wrapped sentence: use the unit's own sentence that
    # carries the row's excerpt
    excerpt = str(getattr(evidence, "span", "") or "")
    window = sentence_window(unit_text, excerpt)
    return window or text


def _align_requirement_to_evidence(
    requirement: str, excerpt: str, atoms: Sequence[Any]
) -> str:
    """Keep the displayed requirement on the clause its evidence came from.

    A concern that owns a broad span of the document renders the sentences of one
    clause while citing another; the requirement must then be the sentences of the
    evidenced clause, so page, section, clause, requirement and excerpt agree.
    """

    text = str(requirement or "").strip()
    evidence = str(excerpt or "").strip()
    if not text or not evidence:
        return text
    if _grounded_in(text, [evidence]) or _grounded_in(evidence, [text]):
        return text
    sentences = [piece for piece in re.split(r"(?<=[。；;])", text) if piece.strip()]
    if len(sentences) <= 1:
        return text
    kept = [sentence for sentence in sentences if _grounded_in(sentence, [evidence])]
    if kept and len("".join(kept)) >= 12:
        return "".join(kept).strip()
    return text

def _trim_to_facet(concern_id: str, excerpt: str, *, base: str) -> str:
    """Keep only the part of an extended excerpt that this concern owns.

    Completing a cut sentence can pull the *next* requirement of the same source
    clause into the row ("…损耗和税金等费用，设备安装调试完毕，…视为交付完成。").
    The clause genuinely carries both, but only the first is this concern's
    requirement: the extension stops where the concern's own contract says the
    text stops belonging to it.  The concern's original text is never trimmed
    away.
    """

    text = str(excerpt or "").strip()
    original = str(base or "").strip()
    if not text or not original:
        return text
    segments = [piece.strip() for piece in re.split(r"[。；;]", text) if piece.strip()]
    if len(segments) <= 1:
        return text
    kept: list[str] = []
    for index, segment in enumerate(segments):
        if index == 0:
            kept.append(segment)
            continue
        if _grounded_in(original, [segment]) or _grounded_in(segment, [original]):
            kept.append(segment)
            continue
        owned = owned_text(concern_id, segment)
        if owned and _flatten(owned) == _flatten(segment):
            kept.append(segment)
    if not kept:
        return text
    joined = "。".join(kept)
    if text.rstrip().endswith(tuple("。；;！？!?")):
        joined += "。"
    # never return less than the concern's own requirement
    if len(_flatten(joined)) < len(_flatten(original)):
        return text
    return joined


def _continuation_ok(original: str, completed: str, concern_id: str = "") -> bool:
    """Does the completed text stay inside the original requirement's facet?

    Completing a cut sentence is only correct while the added text continues the
    *same* requirement.  The owning concern's own contract is the judge: if the
    addition belongs to another concern (the acceptance-completion sentence of
    the same clause), the row keeps its own requirement instead.
    """

    before = str(original or "").strip()
    after = str(completed or "").strip()
    if not before or not after:
        return True
    before_flat = _flatten(before)
    after_flat = _flatten(after)
    if len(after_flat) <= len(before_flat):
        return True
    added = after_flat[len(before_flat) :]
    if not added:
        return True
    if concern_id:
        # the continuation must belong to this concern's own sentence.  The added
        # text starts where the atom stopped, so the concern's contract is asked
        # about the *overlap* it shares with the text already shown plus the
        # addition: a neighbouring requirement ("…设备安装调试完毕，甲方负责人
        # 在验收单上签字…视为交付完成。") is not this concern's continuation.
        joined = before_flat + added
        owned = owned_text(concern_id, joined)
        if not owned:
            return False
        if not _flatten(owned).startswith(before_flat):
            return False
        # the addition itself must be this concern's own text: a clause that only
        # contributes its *head* to this concern while the addition starts another
        # requirement is not a continuation
        if not _grounded_in(added, [owned]) and not _grounded_in(owned, [joined]):
            return False
    return not _FORBIDDEN_FACET_RE.search(added)


#: text that signals the addition belongs to another requirement of the clause
_FORBIDDEN_FACET_RE = re.compile(
    r"(验收单|交付完成|签字或加盖|视为交付|违约|赔偿|索赔|合同解除|退还甲方|签字盖章后生效)"
)


def _finish_from_following(excerpt: str, evidence: Any, units: Sequence[Any]) -> str:
    """Finish a cut sentence from the block that continues it.

    The extraction split one sentence across two blocks and the atom holds only
    the first ("…承诺从最后一笔款项应付之日" + "起给甲方 的支付宽限期，宽限期内
    不追究甲方的违约责任或要求利息。").  The continuation is appended up to the
    first sentence end; the remainder of that block's next sentence is not pulled
    in.
    """

    text = str(excerpt or "").strip()
    if not text:
        return text
    unit = evidence.unit
    following = [
        candidate
        for candidate in units
        if candidate.order > unit.order
        and (
            candidate.page is None
            or unit.page is None
            or int(candidate.page) <= int(unit.page) + 1
        )
    ]
    following.sort(key=lambda candidate: candidate.order)
    for candidate in following[:2]:
        addition = strip_leading_overlap(text, str(candidate.text_span))
        if not addition:
            continue
        if NEW_ELEMENT_RE.match(addition):
            break
        text = f"{text}{_up_to_sentence_end(addition, text)}".strip()
        if text.endswith(tuple("。；;！？!?")):
            break
    return text


def _trim_stray_leading_bracket(text: str) -> str:
    """Drop an extraction-stray closing bracket that opens a fragment.

    A wrapped line that ends a parenthetical leaves its closing bracket at the
    start of the next extracted fragment ("） （若为代理商，须提供生产商的相关
    证明材料"), which is not a reviewable requirement fragment.
    """

    value = str(text or "").strip()
    if not value:
        return value
    stripped = value.lstrip()
    if stripped[:1] in "）)】」" and len(stripped) > 1:
        stripped = stripped[1:].lstrip()
        if len(_flatten(stripped)) >= 6:
            return stripped
    return value


def _complete_source_text(
    concern: Any,
    summary: str,
    evidence_units: EvidenceUnitIndex,
) -> str:
    """Repair a displayed requirement whose quoted clause was cut in half.

    The requirement summary quotes source sentences; when the extraction cut a
    sentence at a line boundary the row would display half a rule.  Each summary
    segment that matches one of the concern's atoms is replaced by that atom's
    own, unit-aligned source text (never by invented content), and repeated
    segments are collapsed.

    Round 7: the repair may only *complete* the segment.  It must not pull a
    neighbouring concern's sentences into the row -- a requirement that suddenly
    names scoring terms ("得分", "评分", "成交候选人") on a responsiveness row is a
    foreign-facet leak, and the round-4 ownership rule forbids it.
    """

    text = str(summary or "").strip()
    if not text:
        return text
    concern_id = str(getattr(concern, "concern_id", "") or "")
    atoms = list(getattr(concern, "atoms", ()))
    backing = _concern_evidence_backing(concern, evidence_units)
    segments = [piece.strip() for piece in re.split(r"[；;]", text) if piece.strip()]
    repaired: list[str] = []
    for segment in segments:
        needle = _flatten(segment)
        match = None
        for atom in atoms:
            atom_flat = _flatten(getattr(atom, "source_text", ""))
            if not atom_flat or not needle:
                continue
            if needle in atom_flat or atom_flat in needle:
                match = atom
                break
        if match is None:
            repaired.append(segment)
            continue
        complete = _evidence_excerpt(concern, match, evidence_units, fallback_text=segment)
        if (
            complete
            and _flatten(complete).startswith(needle)
            and _repair_stays_owned(segment, complete, backing)
        ):
            repaired.append(complete)
        else:
            repaired.append(segment)
    return dedupe_segments("；".join(repaired))


def _concern_backing_text(concern: Any) -> str:
    """The text a concern may name: its owned atoms, materials and fact values."""

    parts: list[str] = []
    for atom in getattr(concern, "atoms", ()) or ():
        parts.append(str(getattr(atom, "source_text", "") or ""))
        origin = getattr(atom, "source_origin_text", "")
        if origin:
            parts.append(str(origin))
    materials = getattr(concern, "owned_materials", None)
    if callable(materials):
        parts.extend(str(name) for name in materials())
    return _flatten(" ".join(parts))


#: an addition that opens a *new* source element instead of continuing the
#: concern's own sentence: a clause / numbered label ("*3.4.1 响应保证金"), or a
#: project-value label ("供货期 合同签订后30 天", "1.12 分包 不允许")
_NEW_SOURCE_ELEMENT_HEAD_RE = re.compile(
    r"^[\s*]*(?:\d+(?:\.\d+)+|\d+[、.]|[（(]\d+[)）]|[①-⑳]|[一二三四五六七八九十]+[、.]"
    r"|[\u4e00-\u9fa5]{2,8}[ \u3000]+[^\s])"
)


def _extension_stays_in_sentence(original: str, extended: str) -> bool:
    """May ``extended`` keep the text it adds beyond the concern's own atom?

    Round 7 (excerpt scope): completing a cut sentence is legitimate
    ("…从最后一笔款项应付之日" + "的支付宽限期，…"), growing the excerpt into the
    *next* source unit's requirement is not ("*3.3.1 询比有效期…90 日历天" +
    "*3.4.1 响应保证金 的金额：…").  The addition is rejected when it opens a new
    source element: a clause number, a numbered item, or a project-value label.
    """

    before = _flatten(original)
    after = _flatten(extended)
    if not before or not after or after == before:
        return True
    index = extended.find(original)
    if index >= 0:
        added = extended[index + len(original) :]
    elif after.startswith(before):
        added = after[len(before) :]
    else:
        return True
    if not added.strip():
        return True
    return _NEW_SOURCE_ELEMENT_HEAD_RE.match(added) is None


def _concern_evidence_backing(concern: Any, evidence_units: EvidenceUnitIndex) -> str:
    """The text a concern may legitimately quote when completing a cut sentence.

    Round 7: the concern's own atoms plus the source units they are displayed
    from, and the unit that *continues* each of them.  A contract sentence is
    split across two blocks ("…从最后一笔款项应付之日" | "起给甲方 的支付宽限期，
    宽限期内不追究甲方的违约责任或要求利息。"), so the continuation is the
    concern's own text -- bounded to the immediately following unit, never a
    distant clause of the document.
    """

    parts = [_concern_backing_text(concern)]
    for atom in getattr(concern, "atoms", ()) or ():
        evidence = evidence_units.for_atom(atom)
        if evidence is None:
            continue
        parts.append(str(evidence.unit.text_span))
        following = [
            candidate
            for candidate in evidence_units.units
            if candidate.order > evidence.unit.order
            and (
                candidate.page is None
                or evidence.unit.page is None
                or int(candidate.page) <= int(evidence.unit.page) + 1
            )
        ]
        following.sort(key=lambda candidate: candidate.order)
        if following:
            parts.append(str(following[0].text_span))
    return _flatten(" ".join(parts))


def _repair_stays_owned(segment: str, complete: str, backing: str) -> bool:
    """Does the repair add only text the concern already owns?

    The added text is what the segment did not carry; it must appear in the
    concern's own backing (its atoms, materials and linked fact values).
    """

    if not backing:
        return True
    before = _flatten(segment)
    after = _flatten(complete)
    if not after.startswith(before):
        return False
    added = after[len(before) :]
    if not added:
        return True
    # every 6-character window of the addition must be owned by the concern
    windows = [added[start : start + 6] for start in range(0, max(len(added) - 5, 1), 3)]
    if not windows:
        return True
    return all(window in backing for window in windows)


def _clean_excerpt(text: str) -> str:
    parts = split_numbered_items(text)
    if len(parts) > 1:
        # keep every numbered item: the caller has already restricted the text to
        # the items this concern owns
        return " ".join(parts)
    return str(text or "").strip()


def _primary_source(
    concern: Any,
    units_by_id: dict[str, Any],
    units: Sequence[Any],
    decisive_pattern: str,
    owned_values: set[str],
    requirement_summary: str = "",
    preferred_atom: Any = None,
) -> tuple[Any, Any]:
    """Pick the clause that actually carries this concern's facet.

    Ranking: the clause the rendered requirement was quoted from, then the
    concern's decisive facet, then an owned value, then owned
    materials/consequence, then source order.  The printed locator, page and
    evidence therefore belong to the same clause as the requirement text
    (round-4 fixture H: a response-bond row must not cite the performance-bond
    clause; fixture N: a price-completeness row must cite its own price clause).
    """

    atoms = list(getattr(concern, "atoms", ()))
    facet = list(concern.facet_atoms()) if hasattr(concern, "facet_atoms") else atoms
    # Round 5: the concern's independent contract decides which clause may serve
    # as the row's evidence.  A performance-bond row may never cite the
    # response-bond clause, and a validity row may never cite a credit-blacklist
    # clause (fixtures B and F).
    contract = None
    try:
        from .concern_contract import contract_for as _contract_for

        contract = _contract_for(str(getattr(concern, "concern_id", "") or ""))
    except Exception:  # pragma: no cover - import guard
        contract = None
    if contract is not None:
        eligible = [
            atom
            for atom in atoms
            if contract.evidence_ok(str(getattr(atom, "source_origin_text", "") or atom.source_text))
            or contract.owned_segment_ok(str(atom.source_text))
        ]
        # Round 5: a clause the contract explicitly forbids as evidence is never
        # cited, even when the concern owns no preferred clause at all (CASE003:
        # a bid-bond row cited an advance-payment-guarantee clause).
        banned = {
            id(atom)
            for atom in atoms
            if contract.evidence_forbidden(
                str(getattr(atom, "source_origin_text", "") or atom.source_text)
            )
        }
        if banned:
            atoms = [atom for atom in atoms if id(atom) not in banned]
            facet = [atom for atom in facet if id(atom) not in banned]
            eligible = [atom for atom in eligible if id(atom) not in banned]
        if eligible:
            facet = [atom for atom in facet if atom in eligible] or eligible
    pattern = None
    if decisive_pattern:
        try:
            pattern = re.compile(decisive_pattern)
        except re.error:  # pragma: no cover - registry typo guard
            pattern = None
    summary_key = re.sub(r"\s+", "", str(requirement_summary or ""))[:24]

    def rank(indexed: tuple[int, Any]) -> tuple[int, int]:
        index, atom = indexed
        score = 0
        flat_atom = re.sub(r"[\s\u3000]+", "", str(atom.source_text))
        if contract is not None:
            # The printed locator (page / section / clause) is displayed too: a
            # clause whose *section title* belongs to another concern must not
            # carry this row's evidence (fixture A: a quality row must not cite
            # the "交货地点" section).
            unit = units_by_id.get(getattr(atom, "source_clause_id", ""))
            section_text = f"{getattr(unit, 'section', '')}{getattr(unit, 'clause', '')}"
            if section_text.strip() and not contract.section_ok(section_text):
                score -= 120
            elif section_text.strip():
                score += 2
        if summary_key:
            first = True
            for sentence in re.split(r"[；;。]", str(requirement_summary or "")):
                probe = re.sub(r"[\s\u3000]+", "", sentence)[:24]
                if probe and probe in flat_atom:
                    # The clause the rendered requirement was quoted from is the
                    # row's evidence; the first quoted sentence is decisive.
                    score += 100 if first else 16
                    break
                if probe:
                    first = False
        if pattern is not None and pattern.search(flat_atom):
            score += 8
        if any(value and re.sub(r"[\s\u3000]+", "", value) in flat_atom for value in owned_values):
            score += 4
        if atom.required_materials:
            score += 2
        if atom.explicit_consequence:
            score += 1
        if atom.explicit_score_rule:
            score += 1
        if _OBLIGATION_CUE.search(atom.source_text):
            # an imperative clause is the requirement itself; a bare table cell
            # ("准 供应商名称 … 与营业执照一致") is only a cross-reference
            score += 3
        if re.search(r"\d+\.\d+(?:\.\d+)?", f"{atom.source_structure_id}{atom.source_text[:24]}"):
            score += 2
        return (score, -index)

    pool = facet or atoms
    if not pool:
        return (None, units[0])
    if preferred_atom is not None:
        # round 7: the applicable (project-specific) source is the row's evidence
        # whenever the row displays it, even when a sibling concern owns the
        # generic clause it resolves -- the value the reviewer reads is that atom's
        # text, so the page, section, clause and excerpt must be its own
        preferred = units_by_id.get(str(getattr(preferred_atom, "source_clause_id", "")))
        return (preferred_atom, preferred if preferred is not None else units[0])
    primary_atom = max(enumerate(pool), key=rank)[1]
    primary = units_by_id.get(primary_atom.source_clause_id)
    if primary is None:
        primary = units[0]
    return (primary_atom, primary)


#: The cell block each component kind is rendered into.
BLOCK_OF_KIND = {
    SOURCE_REQUIREMENT: "招标文件要求",
    REVIEW_CHECK: "复核要点",
    PASS_CRITERION: "通过标准",
    PREPARATION_MATERIAL: "准备材料",
    FAILURE_CONSEQUENCE: "不满足后果",
    SCORING_GUIDANCE: "评分提示",
    NUMERIC_STATEMENT: "数值指标",
    EVIDENCE_SUMMARY: "证据摘要",
    LINKED_FACT: "关联事实",
}


def _components_from_dicts(payloads: Sequence[Mapping[str, Any]]) -> list[RenderedReviewComponent]:
    return [RenderedReviewComponent.from_dict(payload) for payload in payloads]


_CELL_MARKS = "①②③④⑤⑥⑦⑧⑨"


def cell_from_components(components: Sequence[RenderedReviewComponent]) -> str:
    """Render the legacy review cell *from* the verified components.

    Round 4: the cell is a projection of the components, so a phrase cannot
    appear in the sheet unless a concern-owned component produced it.  The
    block labels and bullet marks match the historical cell layout.
    """

    def texts(kind: str) -> list[str]:
        return [c.rendered_text for c in components if c.component_kind == kind]

    blocks: list[str] = []
    notes = texts(CRITICALITY_NOTE)
    if notes:
        # the source-visible criticality leads the cell, so the reviewer cannot
        # miss a critical row even without reading the marker column
        blocks.append(notes[0])
    requirements = texts(SOURCE_REQUIREMENT)
    if requirements:
        blocks.append(f"招标文件要求：{requirements[0]}")
    checks = texts(REVIEW_CHECK)
    if checks:
        lines = []
        for index, check in enumerate(checks):
            mark = _CELL_MARKS[index] if index < len(_CELL_MARKS) else f"({index + 1})"
            lines.append(f"{mark} {check}")
        blocks.append("复核要点：\n" + "\n".join(lines))
    criteria = texts(PASS_CRITERION)
    if criteria:
        blocks.append("通过标准：\n" + "\n".join(f"· {criterion}" for criterion in criteria))
    consequences = texts(FAILURE_CONSEQUENCE)
    if consequences:
        blocks.append(f"不满足后果：{consequences[0]}")
    materials = texts(PREPARATION_MATERIAL)
    if materials:
        blocks.append("准备材料：" + "、".join(materials))
    guidance = texts(SCORING_GUIDANCE)
    if guidance:
        blocks.append(f"评分提示：{guidance[0]}")
    return "\n".join(block for block in blocks if block.strip())


def _shorten(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


#: An imperative requirement clause (as opposed to a cross-reference table cell).
_OBLIGATION_CUE = re.compile(r"(应当|须|必须|不得|禁止|不允许|不接受|要求|应)")


def criticality_note_text(criticality: SourceRequirementCriticality) -> str:
    """The visible, source-backed criticality note of a review row.

    The wording carries the *source* marker (``★`` is the reviewer-facing
    normalisation of whatever emphasis character the source used) and only
    claims what the document's own statements support -- a rejection consequence
    needs a consequence clause, a starred proof list is not a starred
    substantive requirement, and ``一票否决`` is never written.
    """

    if not criticality.marker_present and not criticality.substantive_requirement:
        return ""
    star = VISIBLE_MARKER if criticality.marker_present else ""
    if not criticality.substantive_requirement:
        label = {
            SEMANTICS_PROOF: "必备证明材料",
            SEMANTICS_SCORING: "评分相关条款",
        }.get(criticality.marker_semantics, "源文标记条款")
        return f"【{star}{label}】"
    parts = [f"{star}实质性要求"]
    if criticality.rejection_consequence:
        parts.append("不满足可能导致否决")
    elif criticality.consequence_scopes:
        # round 7: the source states a consequence, but at another stage -- say
        # which one, so a scoring deduction is never read as a rejection
        scoped = {
            "SCORING_ONLY": "评分规则，非否决情形",
            "POST_AWARD_CANCELLATION": "中标后取消资格情形，非响应否决",
            "CONTRACT_LIABILITY": "合同违约责任，非响应否决",
            "NON_ACCEPTANCE_OF_LATE_SUBMISSION": "逾期提交不予受理情形",
            "INFORMATIONAL_PROCEDURAL": "程序性说明，非否决情形",
        }
        for scope in criticality.consequence_scopes:
            if scope in scoped and scoped[scope] not in parts:
                parts.append(scoped[scope])
    return "【" + "｜".join(parts) + "】"


def _render_components(
    *,
    item_id: str,
    concern: Any,
    point: ReviewPoint,
    spec: Any,
    owned_numbers: Sequence[Any],
    primary_atom: Any,
    primary: Any = None,
    units: Sequence[Any] = (),
    fact_hints: Mapping[str, str],
    evidence_text: str = "",
    criticality: SourceRequirementCriticality | None = None,
    displayed_requirement: str = "",
    operational_action: str = "",
    evidence_unit_text: str = "",
) -> list[RenderedReviewComponent]:
    """Build and verify the rendered components of one review row."""

    concern_id = point.concern_id
    atoms = list(getattr(concern, "atoms", ()))
    materials = list(getattr(concern, "owned_materials", lambda: [])())
    # The row's own delivered requirement is source-backed text (the
    # SOURCE_REQUIREMENT component is verified against this same ownership), so a
    # number it states is a value this row owns.  Round 9 renders one 逐档核对 check
    # per source tier; a tier whose score the round-5 segment split left out of
    # ``owned_numbers()`` would otherwise be an unowned claim inside a check the row
    # itself displays.
    requirement_numbers = numeric_tokens(displayed_requirement or point.requirement_summary)
    ownership = ComponentOwnership(
        concern_id=concern_id,
        atom_ids=tuple(str(atom.atom_id) for atom in atoms),
        atom_text=" ".join(
            f"{atom.source_text} {getattr(atom, 'source_origin_text', '') or ''}" for atom in atoms
        ),
        clause_text=" ".join(
            [str(unit.text) for unit in units]
            + ([evidence_unit_text] if evidence_unit_text else [])
        ),
        numeric_values=tuple(str(value.value) for value in owned_numbers)
        + tuple(sorted(requirement_numbers)),
        materials=tuple(str(name) for name in materials),
        evidence_ids=tuple(point.owned_clause_ids),
        allowed_fact_keys=frozenset(spec.fact_fields),
        fact_values={field: hint for field, hint in fact_hints.items()},
    )
    components: list[RenderedReviewComponent] = []
    counter = 0
    kind_counts: dict[str, int] = {}

    def add(
        kind: str,
        text: str,
        *,
        rule: str,
        evidence_ids: Sequence[str] = (),
        numeric_ids: Sequence[str] = (),
        fact_keys: Sequence[str] = (),
    ) -> None:
        nonlocal counter
        counter += 1
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        component = RenderedReviewComponent(
            component_id=f"{item_id}:{kind}:{counter:02d}",
            review_point_id=item_id,
            concern_id=concern_id,
            component_kind=kind,
            rendered_text=str(text),
            source_atom_ids=tuple(str(atom.atom_id) for atom in atoms),
            evidence_ids=tuple(str(value) for value in evidence_ids),
            linked_fact_keys=tuple(str(value) for value in fact_keys),
            numeric_evidence_ids=tuple(str(value) for value in numeric_ids),
            generation_rule=rule,
            block=BLOCK_OF_KIND.get(kind, kind),
            sentence_index=kind_counts[kind],
        )
        components.append(verify_component(component, ownership))

    add(
        SOURCE_REQUIREMENT,
        displayed_requirement or point.requirement_summary,
        rule="CONCERN_SUMMARY_OWNED_ATOMS",
    )
    if criticality is not None:
        note = criticality_note_text(criticality)
        if note:
            # Round 6: the note is rendered first so the reviewer sees the
            # source-visible criticality before the requirement itself.
            add(
                CRITICALITY_NOTE,
                note,
                rule=(
                    "SOURCE_MARKER_AND_GOVERNING_CLAUSE"
                    if criticality.marker_present
                    else "GOVERNING_SUBSTANTIVE_CLAUSE"
                ),
                evidence_ids=[
                    *criticality.substantive_basis_atom_ids,
                    *criticality.rejection_basis_atom_ids,
                ],
            )
    templates = set(CONCERN_CHECKS.get(concern_id, ()))
    if operational_action:
        # Round 8: the project value's own operational action is the *first*
        # review check.  It was previously written only onto the item's action
        # field, so the delivered cell (which is rendered from these components)
        # showed the concern's generic checks and lost the decision the row is
        # actually about (fixture D56: "采购预备会 不召开" was delivered with an
        # action about the clarification deadline).  Rendering it here keeps the
        # cell and the action field projecting the same owned text.
        add(
            REVIEW_CHECK,
            operational_action,
            rule="RESOLUTION_OPERATIONAL_ACTION",
        )
    for check in point.review_checks:
        add(
            REVIEW_CHECK,
            check,
            rule="CONCERN_CHECK_TEMPLATE" if check in templates else "CONCERN_CHECK_DERIVED_OWNED",
        )
    criteria_templates = {CONCERN_PASS_CRITERIA.get(concern_id, "")}
    for criterion in point.pass_criteria:
        add(
            PASS_CRITERION,
            criterion,
            rule="CONCERN_CRITERION_TEMPLATE" if criterion in criteria_templates else "CONCERN_CRITERION_DERIVED_OWNED",
        )
    for name in materials:
        add(PREPARATION_MATERIAL, str(name), rule="CONCERN_OWNED_MATERIAL")
    if point.failure_consequence:
        add(FAILURE_CONSEQUENCE, point.failure_consequence, rule="CONCERN_OWNED_CONSEQUENCE")
    if point.scoring_guidance:
        add(SCORING_GUIDANCE, point.scoring_guidance, rule="CONCERN_OWNED_SCORE_RULE")
    numeric_backing = str(getattr(point, "owned_backing", "") or "") or ownership.backing_text
    # The row's own delivered text (requirement, checks, criteria, guidance) is what
    # the cell will project: a numeric *claim* is a rendered component only while
    # that text actually states it.
    rendered_so_far = " ".join(_flatten(component.rendered_text) for component in components)
    for value in owned_numbers[:4]:
        # only the numbers the row actually renders (its checks/criteria carry the
        # first four) become rendered components; further owned values stay data
        if value.role == ROLE_TIER_SCORE:
            # a tier is not one value claim: the row renders one 逐档核对 check per
            # tier ("逐档核对：4分 对应的响应内容在响应文件中可核验"), so a second
            # "该档计 4分" statement would be a claim no delivered cell displays
            continue
        sentence = value_sentence(value.role, value.value, numeric_backing)
        if _flatten(sentence) not in rendered_so_far:
            # Round 9 stopped rendering an evaluation-rule parameter as a bidder
            # declaration on a scoring row (fixture D50: the rule is verified by the
            # reviewer, never restated by the bidder), so a claim the cell no longer
            # displays may not be declared as a component: the round-4 provenance
            # gate requires every component to be present in the final cell
            continue
        add(
            NUMERIC_STATEMENT,
            sentence,
            rule=f"CONCERN_OWNED_NUMERIC:{value.role}",
            numeric_ids=[str(getattr(value, "unit_id", "") or value.value)],
        )
    if primary_atom is not None:
        add(
            EVIDENCE_SUMMARY,
            _shorten(evidence_text or str(primary_atom.source_text), 300),
            rule="CONCERN_DECISIVE_ATOM",
            evidence_ids=[str(primary_atom.source_clause_id)],
        )
    for field in getattr(point, "linked_fact_keys", ()) or ():
        if field not in fact_hints:
            continue
        add(LINKED_FACT, f"关联事实：{field}", rule="CONCERN_ALLOWED_FACT", fact_keys=[field])
    return components


#: The risk a row shows in the delivered template's 风险级别 column.  It is
#: derived from the *source* criticality, never from the requirement-type table
#: alone: a row whose type ("ELECTRONIC", "SIGNATURE") has a default of 一票否决
#: but whose source states no rejection consequence must not be shown as a
#: rejection on one sheet while the substantive/否决 columns say otherwise
#: (round-8 fixtures DR013/DR038/DR039).
RISK_VETO = "一票否决"
RISK_HIGH = "高"
RISK_MEDIUM = "中"
RISK_LOW = "低"

#: Risk shown when the row's own requirement type implies a consequence even
#: where the source states none (a submission deadline that lapses).
RISK_BY_CRITICALITY: dict[str, str] = {
    "SUBSTANTIVE_REJECTION": RISK_VETO,
    "SUBSTANTIVE": RISK_HIGH,
    "MANDATORY": RISK_HIGH,
    "ORDINARY": RISK_MEDIUM,
}


#: The concern order the delivered row ids were allocated in.  A row id is part of
#: the address the human review cites, and the banked gates name rows by id, so a
#: *new* concern may never renumber an existing one: the concerns below keep the
#: ids they were delivered with, and any concern that is not listed takes the next
#: ids after them.  The list is concern vocabulary, not case data, and it only
#: ever appends -- another case's order is untouched.
DELIVERED_CONCERN_ORDER: tuple[str, ...] = (
    "PRICE_CEILING",
    "DELIVERY_PERIOD",
    "QUALITY_TARGET",
    "PROJECT_WARRANTY",
    "QUALIFICATION_LICENSE",
    "QUALIFICATION_FINANCIAL",
    "SIGNATURE_AND_SEAL",
    "QUALIFICATION_CREDIT",
    "TECHNICAL_PROOF",
    "QUALIFICATION_RELATIONSHIP_RESTRICTION",
    "QUALIFICATION_ANTI_BRIBERY",
    "CONSORTIUM",
    "GENERAL_BIDDER_OBLIGATION",
    "SUBMISSION_DEADLINE",
    "ELECTRONIC_UPLOAD",
    "QUERY_DEADLINE",
    "BID_VALIDITY",
    "BID_BOND_AMOUNT",
    "BID_BOND_FORM",
    "BID_BOND_TRANSFER",
    "INTERNAL_PROCEDURE",
    "PURCHASER_PROCEDURE",
    "UNSUPPORTED_FORMAT_CLAIM",
    "PRICE_TAX_BASIS",
    "CONTRACT_RISK",
    "EVALUATION_SCORING",
    "EVALUATION_COLLUSION",
    "EVALUATION_RESPONSIVENESS",
    "REJECTION_GENERAL",
    "DELIVERY_LOCATION",
    "PROJECT_FUNDING_SOURCE",
    "SITE_VISIT",
    "SUBCONTRACT",
    "FILE_FORMAT",
    "PRICING_COMPLETENESS",
    "BID_BOND_EVIDENCE",
    "PERFORMANCE_BOND",
    "AUTHORIZATION",
    "SUBMISSION_PLATFORM",
    "SCORING_PRICE_FORMULA",
    "SCORING_BANK_ACCEPTANCE",
    "SCORING_PAYMENT_CONDITION",
    "SCORING_TECHNICAL",
    "CONTRACT_PAYMENT",
    "RETENTION_RELEASE_PERIOD",
    "TECHNICAL_STANDARD_COMPLIANCE",
    "TECHNICAL_TEST_REPORT",
    "DELIVERY_ACCEPTANCE_COMPLETION",
    "CONTRACT_TERMINATION_REFUND",
    "TECHNICAL_PARAMETER",
    "RETENTION_MONEY_RATIO",
    "PRICE_INCLUDED_COST_SCOPE",
)


def _stable_concern_order(concerns: Sequence[Any]) -> list[Any]:
    """The concerns in id-allocation order: known ones first, new ones appended."""

    index = {concern_id: position for position, concern_id in enumerate(DELIVERED_CONCERN_ORDER)}
    known = [concern for concern in concerns if str(concern.concern_id) in index]
    fresh = [concern for concern in concerns if str(concern.concern_id) not in index]
    known.sort(key=lambda concern: index[str(concern.concern_id)])
    return [*known, *fresh]


def _risk_level_for(
    requirement_type: str,
    criticality: SourceRequirementCriticality | None,
    *,
    informational: bool = False,
) -> str:
    """The row's risk level, made consistent with its own source basis.

    Three independent dimensions must agree across the delivered sheets: the
    source marker (★), the substantive basis (实质性依据) and the rejection
    consequence (否决依据).  The 风险级别 column may therefore not claim 一票否决
    for a row whose source states no rejection consequence at all -- that is the
    "legacy 一票否决" contradiction the human review found.  A type default is
    still used where the source says nothing, but it can only *raise* the level
    to the type's own risk, never to 一票否决.
    """

    if informational:
        return RISK_LOW
    default = RISK_BY_TYPE.get(requirement_type, RISK_MEDIUM)
    if criticality is None:
        return default
    if criticality.rejection_consequence:
        return RISK_VETO
    level = RISK_BY_CRITICALITY.get(criticality.criticality_level, RISK_MEDIUM)
    if default == RISK_VETO:
        # the type is veto-class, but *this* row's source states no rejection
        # consequence: the strongest honest level is 高
        return RISK_HIGH if level == RISK_MEDIUM else level
    order = {RISK_LOW: 0, RISK_MEDIUM: 1, RISK_HIGH: 2, RISK_VETO: 3}
    return max([default, level], key=lambda value: order.get(value, 1))


#: The row's ordering vocabulary must know every level the risk function emits.
RISK_ORDER: dict[str, int] = {
    RISK_VETO: 0,
    RISK_HIGH: 1,
    RISK_MEDIUM: 2,
    RISK_LOW: 3,
}


#: The rank a row is *ordered* by.  This reproduces the historical order exactly:
#: a source-resolved project decision sorts last, and every other row sorts by
#: its requirement type's own risk -- never by the risk the row displays, so
#: correcting a displayed 风险级别 does not renumber the rows the human's
#: findings are addressed by.
def _ordering_rank(item: DynamicReviewItem) -> int:
    if getattr(item, "project_decision", False):
        return 3
    return RISK_ORDER.get(RISK_BY_TYPE.get(item.requirement_type, RISK_MEDIUM), 2)


def order_review_items(items: Sequence[DynamicReviewItem]) -> list[DynamicReviewItem]:
    """Sort rows by business module, then risk, then source order.

    The sort key is the row's *type* risk (see :func:`_ordering_rank`), so the
    displayed 风险级别 can be corrected for cross-sheet consistency without
    changing any row id: the human's findings are addressed by row address.
    """

    module_rank = {module: index for index, module in enumerate(MODULE_ORDER)}
    ranks = {item.item_id: _ordering_rank(item) for item in items}

    def key(item: DynamicReviewItem) -> tuple[int, int, str]:
        return (
            module_rank.get(item.module, len(MODULE_ORDER)),
            ranks.get(item.item_id, 2),
            item.item_id,
        )

    return sorted(items, key=key)


# --------------------------------------------------------------------------
# QA
# --------------------------------------------------------------------------


def _lexicon_hits(text: str) -> list[str]:
    return [term for term in TOPIC_LEXICON if term in text]


def _shared_grounding(evidence: str, units: Sequence[SourceRequirementUnit]) -> bool:
    """Require the item evidence to be literally present in its source units."""

    return _grounded_in(evidence, [str(getattr(unit, "text", "") or "") for unit in units])


def _applicable_source_texts(document: Any) -> list[str]:
    """The project-specific values a generic clause resolves to (front table rows)."""

    if document is None:
        return []
    return [str(getattr(row, "text", "") or "") for row in discover_schedule_rows(document)]


def _page_source_texts(document: Any) -> dict[int, list[str]]:
    """The document's own physical source text, by page.

    Round 7: the extraction index is not the source.  A contract sentence is
    routinely split across two *blocks* (``"…剩余5%"`` + ``"作为质保金，质保期12
    个月…"``), so the page's own reading order is offered as well: each unit, and
    every short run of adjacent units inside one clause.  The allowance stays
    page-bounded and clause-bounded, so a row cannot ground itself in a distant
    section.
    """

    if document is None:
        return {}
    from .evidence_unit import build_evidence_units

    by_page: dict[int, list[tuple[int, str, str]]] = {}
    for unit in build_evidence_units(document):
        page = getattr(unit, "page", None)
        if page is None:
            continue
        by_page.setdefault(int(page), []).append(
            (
                int(getattr(unit, "order", 0) or 0),
                str(getattr(unit, "clause_number", "") or ""),
                str(getattr(unit, "text_span", "") or ""),
            )
        )
    pages: dict[int, list[str]] = {}
    for page, entries in by_page.items():
        entries.sort()
        texts = [text for _, _, text in entries]
        pages[page] = list(texts)
        for start in range(len(entries)):
            clause = entries[start][1]
            run = [entries[start][2]]
            for order, next_clause, text in entries[start + 1 : start + 3]:
                if next_clause and clause and next_clause != clause:
                    break
                run.append(text)
                clause = clause or next_clause
            if len(run) > 1:
                pages[page].append(" ".join(run))
    return pages


def _shared_applicable_grounding(item: Any, sources: Sequence[str]) -> bool:
    """Is the row's evidence drawn from the applicable source it resolves to?

    The generic clause the concern was extracted from says ``"见供应商须知前附表"``;
    the row displays the front table's own value, so its evidence is grounded in
    that applicable source -- but only when the row's *requirement* quotes the same
    source (this is the applicable-source resolution, not a licence to quote any
    front-table row).
    """

    if not sources:
        return False
    evidence = str(getattr(item, "source_evidence", "") or "")
    requirement = str(getattr(item, "source_requirement", "") or "")
    if not evidence or not requirement:
        return False
    return any(
        _grounded_in(evidence, [source]) and _grounded_in(requirement, [source]) for source in sources
    )


def _physical_grounding(item: Any, page_sources: Mapping[int, Sequence[str]]) -> bool:
    """Are requirement and evidence both literally present on the row's own page?"""

    page = getattr(item, "source_page", None)
    if page is None:
        return False
    sources = page_sources.get(int(page))
    if not sources:
        return False
    evidence = str(getattr(item, "source_evidence", "") or "")
    requirement = str(getattr(item, "source_requirement", "") or "")
    if not evidence or not requirement:
        return False
    return _grounded_in(evidence, sources) and _grounded_in(requirement, sources)


def _grounded_in(evidence: str, sources: Sequence[str]) -> bool:
    """Is ``evidence`` literally present in any of ``sources``?"""

    compact = re.sub(r"\s+", "", evidence)
    if len(compact) < 6:
        return False
    for source in sources:
        haystack = re.sub(r"\s+", "", source or "")
        if not haystack:
            continue
        for start in range(0, max(len(compact) - 11, 1), 6):
            window = compact[start : start + 12]
            if len(window) >= 8 and window in haystack:
                return True
        if compact[:12] in haystack:
            return True
    return False


def _false_platform_conflict_count(plan: DynamicReviewPlan) -> int:
    """Rows that claim a conflict between two platform roles that are not in conflict.

    Round 5 fixture S: the transaction / upload / opening / announcement /
    public-information roles are *different aspects of the same platform*, so a
    row that reports "不同平台" for them is a false conflict.
    """

    platform_roles = {
        "SUBMISSION_PLATFORM",
        "ELECTRONIC_UPLOAD",
        "OPENING_DECRYPTION",
        "ANNOUNCEMENT_CHANNEL",
        "PUBLIC_INFORMATION",
    }
    count = 0
    for item in list(plan.items) + list(getattr(plan, "background_items", ()) or ()):
        text = str(getattr(item, "cell_text", "") or "")
        if "不同平台" not in text:
            continue
        if str(getattr(item, "concern_id", "") or "") in platform_roles or "平台" in text:
            count += 1
    return count


def dynamic_review_qa(
    plan: DynamicReviewPlan,
    document: NormalizedDocument | None = None,
    project_facts: ProjectFacts | None = None,
    workbook_rows: Sequence[Sequence[object]] | None = None,
) -> dict[str, object]:
    """Machine-readable QA for the dynamic review architecture.

    The reverse-coverage audit re-scans the source with an independent keyword
    pass instead of trusting the extraction output.
    """

    units_by_id = {unit.requirement_id: unit for unit in plan.index.units}
    covered_ids: set[str] = set()
    for item in plan.items:
        covered_ids.update(item.source_requirement_ids)
    # Background (non-bidder-facing) clauses are still covered: they are retained
    # for traceability but are not rendered as delivery rows.
    for item in getattr(plan, "background_items", ()) or ():
        covered_ids.update(item.source_requirement_ids)
    # Round 5: a clause escalated to NEEDS_REVIEW is covered by that escalation,
    # not silently dropped (fixture T).
    covered_ids.update(getattr(plan, "needs_review_clause_ids", ()) or ())

    high_risk_units = [
        unit for unit in plan.index.units if unit.high_risk
    ]
    uncovered_high_risk = [
        unit.requirement_id for unit in high_risk_units if unit.requirement_id not in covered_ids
    ]

    irrelevant: list[str] = []
    cross_topic: list[str] = []
    empty_evidence: list[str] = []
    invalid_locator: list[str] = []
    generic_text: list[str] = []
    # Round 7: the row's evidence is grounded in its extraction units, in the
    # applicable source its requirement resolves to, or in the document's own
    # physical text on the page it cites.
    applicable_sources = _applicable_source_texts(document)
    page_sources = _page_source_texts(document)
    for item in plan.items:
        units = [units_by_id[rid] for rid in item.source_requirement_ids if rid in units_by_id]
        backing = " ".join(unit.text for unit in units)
        if not item.source_evidence.strip() or not backing.strip():
            empty_evidence.append(item.item_id)
        if item.source_page is None or item.source_page < 1 or not units:
            invalid_locator.append(item.item_id)
        elif (
            not _shared_grounding(item.source_evidence, units)
            and not _shared_applicable_grounding(item, applicable_sources)
            and not _physical_grounding(item, page_sources)
        ):
            invalid_locator.append(item.item_id)
        for term in _lexicon_hits(item.cell_text):
            if term not in backing and term not in item.source_evidence:
                irrelevant.append(item.item_id)
                break
        # The row's stated requirement must be traceable to its own evidence.
        requirement_terms = _lexicon_hits(item.source_requirement)
        for term in requirement_terms:
            if term not in backing:
                cross_topic.append(item.item_id)
                break
        if any(phrase in item.source_requirement for phrase in _GENERIC_PHRASES):
            generic_text.append(item.item_id)
            continue
        if item.requirement_type in VALUE_TYPES:
            # Round 3: only a value the *concern* owns counts as a specific
            # source value for this row.  A value owned by another concern (a
            # tender fee, a contact number, another row's quantity) must not be
            # forced into this row's text.
            owned = {
                value.value
                for value in (item.review_point.numeric_evidence if item.review_point else [])
            }
            concrete = [value for unit in units for value in unit.values if value in owned]
            if concrete and not any(value in item.cell_text for value in concrete):
                if not item.related_fact_value or item.related_fact_value not in item.cell_text:
                    generic_text.append(item.item_id)

    duplicates: list[str] = []
    seen_keys: dict[str, str] = {}
    for item in plan.items:
        key = re.sub(r"\s+", "", item.source_requirement)[:80]
        if key in seen_keys:
            duplicates.append(item.item_id)
        else:
            seen_keys[key] = item.item_id

    module_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for item in plan.items:
        module_counts[item.module] = module_counts.get(item.module, 0) + 1
        risk_counts[item.risk_level] = risk_counts.get(item.risk_level, 0) + 1
        type_counts[item.requirement_type] = type_counts.get(item.requirement_type, 0) + 1

    unclassified_high_risk = [
        unit.requirement_id
        for unit in high_risk_units
        if unit.requirement_type == "OTHER"
    ]

    # Round 6: source-visible criticality counters.  A row may only show a
    # marker it can back with a source marker, and a rejection status may only
    # exist with a source consequence rule behind it.
    marker_rows = [item for item in plan.items if item.marker_present]
    substantive_rows = [item for item in plan.items if item.substantive_requirement]
    rejection_rows = [item for item in plan.items if item.rejection_consequence]
    explicit_rejection_rows = [
        item for item in rejection_rows if item.rejection_kind == REJECTION_EXPLICIT
    ]
    unbacked_marker_rows = [
        item.item_id
        for item in marker_rows
        if not item.substantive_basis_atom_ids
        and item.substantive_basis_kind != BASIS_SOURCE_MARKER
        and not item.raw_source_markers
    ]
    unbacked_rejection_rows = [
        item.item_id for item in rejection_rows if not item.rejection_basis_atom_ids
    ]
    unbacked_substantive_rows = [
        item.item_id
        for item in substantive_rows
        if not item.substantive_basis_atom_ids
        and item.substantive_basis_kind != BASIS_SOURCE_MARKER
        and item.substantive_basis_kind != BASIS_REFERENCE_PROPAGATION
    ]
    basis_kind_counts: dict[str, int] = {}
    for item in substantive_rows:
        kind = item.substantive_basis_kind or "UNKNOWN"
        basis_kind_counts[kind] = basis_kind_counts.get(kind, 0) + 1

    workbook_row_count = None
    workbook_rows_match = None
    workbook_mismatch_rows: list[int] = []
    if workbook_rows is not None:
        expected = [item.cell_text for item in order_review_items(plan.items)]
        written = [
            str(row[3]) if len(row) > 3 and row[3] is not None else ""
            for row in workbook_rows
        ]
        workbook_row_count = len(written)
        workbook_mismatch_rows = [
            index
            for index, (left, right) in enumerate(zip(expected, written), start=1)
            if left != right
        ]
        workbook_rows_match = (
            not workbook_mismatch_rows and len(expected) == len(written)
        )

    metrics: dict[str, object] = {
        "dynamic_review_item_count": len(plan.items),
        "background_review_item_count": len(getattr(plan, "background_items", ()) or ()),
        "review_items_by_module": module_counts,
        "review_items_by_risk": risk_counts,
        "review_items_by_type": type_counts,
        "rejection_review_item_count": type_counts.get("REJECTION", 0),
        "qualification_review_item_count": type_counts.get("QUALIFICATION", 0),
        "evaluation_review_item_count": type_counts.get("EVALUATION", 0),
        "pricing_review_item_count": type_counts.get("PRICING", 0),
        "technical_review_item_count": type_counts.get("TECHNICAL", 0),
        "bond_review_item_count": type_counts.get("BOND", 0),
        "source_fragment_count": plan.index.scanned_fragments,
        "source_requirement_count": plan.source_requirement_count,
        "source_mandatory_requirement_count": len(high_risk_units),
        "source_mandatory_requirement_without_review_item_count": len(uncovered_high_risk),
        "source_mandatory_requirement_without_review_item_ids": uncovered_high_risk[:20],
        "project_irrelevant_review_item_count": len(set(irrelevant)),
        "project_irrelevant_review_item_ids": sorted(set(irrelevant))[:20],
        "invalid_review_evidence_locator_count": len(set(invalid_locator)),
        "invalid_review_evidence_locator_ids": sorted(set(invalid_locator))[:20],
        "empty_review_evidence_count": len(set(empty_evidence)),
        "empty_review_evidence_ids": sorted(set(empty_evidence))[:20],
        "cross_topic_evidence_mismatch_count": len(set(cross_topic)),
        "cross_topic_evidence_mismatch_ids": sorted(set(cross_topic))[:20],
        # ---- round 6: source-visible criticality ------------------------- #
        "source_marker_review_item_count": len(marker_rows),
        "source_marker_review_item_ids": [item.item_id for item in marker_rows],
        "substantive_requirement_review_item_count": len(substantive_rows),
        "rejection_consequence_review_item_count": len(rejection_rows),
        "explicit_rejection_consequence_review_item_count": len(explicit_rejection_rows),
        "substantive_basis_kind_counts": basis_kind_counts,
        "unbacked_marker_review_item_count": len(set(unbacked_marker_rows)),
        "unbacked_rejection_review_item_count": len(set(unbacked_rejection_rows)),
        "unbacked_substantive_review_item_count": len(set(unbacked_substantive_rows)),
        "duplicate_review_item_count": len(duplicates),
        "duplicate_review_item_ids": duplicates[:20],
        "unclassified_dynamic_requirement_count": len(unclassified_high_risk),
        "unclassified_high_risk_requirement_ids": unclassified_high_risk[:20],
        "generic_text_when_specific_source_available_count": len(set(generic_text)),
        "generic_text_item_ids": sorted(set(generic_text))[:20],
        "dropped_duplicate_requirement_count": plan.dropped_duplicate_count,
        "dropped_navigation_fragment_count": plan.index.dropped_navigation,
        "dropped_heading_fragment_count": plan.index.dropped_heading,
        "workbook_row_count": workbook_row_count,
        "workbook_rows_match_dynamic_items": workbook_rows_match,
        "workbook_mismatch_rows": workbook_mismatch_rows[:20],
    }
    # Round 4: every rendered phrase must be owned by the row's concern.  The
    # counts are per component kind so a failure names the rendering path.
    rendered_counts = {f"rendered_{kind.lower()}_concern_mismatch": 0 for kind in (
        SOURCE_REQUIREMENT,
        REVIEW_CHECK,
        PASS_CRITERION,
        PREPARATION_MATERIAL,
        FAILURE_CONSEQUENCE,
        SCORING_GUIDANCE,
        NUMERIC_STATEMENT,
        EVIDENCE_SUMMARY,
        LINKED_FACT,
    )}
    rendered_counts["rendered_component_concern_mismatch_total"] = 0
    mismatch_ids: list[str] = []
    unverified_component_count = 0
    for item in list(plan.items) + list(getattr(plan, "background_items", ()) or ()):
        component_dicts = list(getattr(item, "rendered_components", ()) or ())
        unverified_component_count += sum(1 for row in component_dicts if not row.get("ownership_verified"))
        counts = mismatch_counts(_components_from_dicts(component_dicts))
        for key, value in counts.items():
            rendered_counts[key] = rendered_counts.get(key, 0) + value
        if any(not row.get("ownership_verified") for row in component_dicts):
            mismatch_ids.append(item.item_id)
    metrics.update(rendered_counts)
    metrics["rendered_component_concern_mismatch_item_ids"] = mismatch_ids[:20]
    metrics["rendered_component_count"] = sum(
        len(getattr(item, "rendered_components", ()) or ())
        for item in list(plan.items) + list(getattr(plan, "background_items", ()) or ())
    )
    metrics["rendered_component_unverified_count"] = unverified_component_count
    # Round 5: the independent concern contracts audit the *displayed* text of
    # every delivered row.  Provenance consistency (round 4) is not semantic
    # validation: a row can be fully traceable and still display a neighbouring
    # facet or assign a number the wrong business meaning.  These counters are
    # the semantic gate.
    contract_violation_counts: dict[str, int] = {}
    contract_violation_rows: list[str] = []
    uncovered_concern_ids: set[str] = set()
    for item in list(plan.items) + list(getattr(plan, "background_items", ()) or ()):
        concern_id = str(getattr(item, "concern_id", "") or "")
        spec = concern_contract_for(concern_id)
        if spec is None or not spec.explicit:
            uncovered_concern_ids.add(concern_id)
        point = getattr(item, "review_point", None)
        component_kinds: dict[str, list[str]] = {}
        for row in getattr(item, "rendered_components", ()) or ():
            component_kinds.setdefault(str(row.get("component_kind", "")), []).append(
                str(row.get("rendered_text", ""))
            )
        violations = validate_point(
            concern_id,
            displayed_text=str(getattr(item, "cell_text", "") or ""),
            review_checks=component_kinds.get(REVIEW_CHECK, []),
            pass_criteria=component_kinds.get(PASS_CRITERION, []),
            materials=component_kinds.get(PREPARATION_MATERIAL, []),
            consequence=" ".join(component_kinds.get(FAILURE_CONSEQUENCE, [])),
            scoring_guidance=" ".join(component_kinds.get(SCORING_GUIDANCE, [])),
            numeric_roles=[
                str(getattr(value, "role", ""))
                for value in (getattr(point, "numeric_evidence", ()) or ())
            ],
            linked_fact_keys=[
                str(getattr(item, "related_project_fact", "") or "")
            ]
            if getattr(item, "related_project_fact", None)
            else [],
            evidence_text=str(getattr(item, "source_evidence", "") or ""),
        )
        if violations:
            contract_violation_rows.append(str(getattr(item, "item_id", "")))
            for violation in violations:
                contract_violation_counts[violation.code] = (
                    contract_violation_counts.get(violation.code, 0) + 1
                )
    metrics["concern_contract_violation_count"] = sum(contract_violation_counts.values())
    metrics["concern_contract_violation_codes"] = dict(sorted(contract_violation_counts.items()))
    metrics["concern_contract_violation_item_ids"] = sorted(set(contract_violation_rows))[:20]
    metrics["contract_uncovered_concern_count"] = len(uncovered_concern_ids)
    metrics["contract_uncovered_concern_ids"] = sorted(uncovered_concern_ids)[:20]
    metrics["needs_review_topic_count"] = len(getattr(plan, "needs_review_topics", ()) or ())
    metrics["needs_review_topics"] = list(getattr(plan, "needs_review_topics", ()) or ())[:20]
    metrics["false_platform_conflict_count"] = _false_platform_conflict_count(plan)
    hard_gates = {
        "source_mandatory_requirement_without_review_item_count": metrics[
            "source_mandatory_requirement_without_review_item_count"
        ],
        "project_irrelevant_review_item_count": metrics["project_irrelevant_review_item_count"],
        "invalid_review_evidence_locator_count": metrics["invalid_review_evidence_locator_count"],
        "empty_review_evidence_count": metrics["empty_review_evidence_count"],
        "cross_topic_evidence_mismatch_count": metrics["cross_topic_evidence_mismatch_count"],
        "unclassified_dynamic_requirement_count": metrics["unclassified_dynamic_requirement_count"],
        "generic_text_when_specific_source_available_count": metrics[
            "generic_text_when_specific_source_available_count"
        ],
        "dynamic_review_item_count": metrics["dynamic_review_item_count"],
        "concern_contract_violation_count": metrics["concern_contract_violation_count"],
        "contract_uncovered_concern_count": metrics["contract_uncovered_concern_count"],
        "false_platform_conflict_count": metrics["false_platform_conflict_count"],
    }
    for key, value in rendered_counts.items():
        hard_gates[key] = value
    metrics["hard_gate_values"] = hard_gates
    metrics["hard_gate_failures"] = [
        name
        for name, value in hard_gates.items()
        if value not in (0, None) and name != "dynamic_review_item_count"
    ]
    if metrics["dynamic_review_item_count"] == 0:
        metrics["hard_gate_failures"].append("dynamic_review_item_count")
    metrics["result"] = (
        "PASS" if not metrics["hard_gate_failures"] else "FAIL"
    )
    return metrics


__all__ = [
    "CONCEPT_TERMS",
    "DynamicReviewItem",
    "DynamicReviewPlan",
    "FACT_FOR_TYPE",
    "build_dynamic_review_plan",
    "dynamic_review_qa",
    "order_review_items",
]
