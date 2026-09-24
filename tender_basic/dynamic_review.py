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
from .output_helpers import value_text
from .review_concern import actionable_concerns, atomize_units, build_concerns, concern_spec
from .review_point import (
    CONCERN_CHECKS,
    CONCERN_PASS_CRITERIA,
    ReviewPoint,
    render_checks,
    render_review_cell,
    synthesize_concern_point,
    synthesize_review_point,
    value_sentence,
)
from .review_rendering import (
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
    verify_component,
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
    concerns = build_concerns(atoms)
    kept, filtered = actionable_concerns(concerns)
    units_by_id = {unit.requirement_id: unit for unit in source_index.units}

    items: list[DynamicReviewItem] = []
    background_items: list[DynamicReviewItem] = []
    filtered_topics: list[str] = [
        f"{concern.label}（{concern.topic}）" for concern in filtered
    ]
    counter = 0
    for concern in kept:
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
        module = _module_for(units, requirement_type, topic)
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
        pass_criteria = " ".join(point.pass_criteria)
        consequence = point.failure_consequence
        primary_atom, primary = _primary_source(
            concern, units_by_id, units, spec.decisive_pattern, owned_values, point.requirement_summary
        )
        locator_parts = []
        if primary.page:
            locator_parts.append(f"第{primary.page}页")
        if primary.section:
            locator_parts.append(primary.section)
        if primary.clause:
            locator_parts.append(f"第{primary.clause}条")
        locator_parts.append(
            f"（{primary.source_kind}）"
        )
        counter += 1
        item_id = f"DR{counter:03d}"
        evidence_text = str(getattr(primary_atom, "source_origin_text", "") or primary_atom.source_text)
        if not _shared_grounding(evidence_text, units):
            # a derived atom keeps its clause as the rendered evidence, so the
            # evidence stays literally present in the source
            evidence_text = str(getattr(primary, "text", "") or evidence_text)
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
        )
        item = DynamicReviewItem(
            item_id=item_id,
            module=module,
            submodule=concern.label or topic,
            risk_level=RISK_BY_TYPE.get(requirement_type, "中"),
            requirement_type=requirement_type,
            topic=topic,
            source_requirement=source_requirement,
            verification_action=verification_action,
            pass_criteria=pass_criteria,
            consequence_if_failed=consequence,
            source_locator=" / ".join(locator_parts),
            source_page=primary.page,
            source_section=primary.section,
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
    )


def _primary_source(
    concern: Any,
    units_by_id: dict[str, Any],
    units: Sequence[Any],
    decisive_pattern: str,
    owned_values: set[str],
    requirement_summary: str = "",
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
) -> list[RenderedReviewComponent]:
    """Build and verify the rendered components of one review row."""

    concern_id = point.concern_id
    atoms = list(getattr(concern, "atoms", ()))
    materials = list(getattr(concern, "owned_materials", lambda: [])())
    ownership = ComponentOwnership(
        concern_id=concern_id,
        atom_ids=tuple(str(atom.atom_id) for atom in atoms),
        atom_text=" ".join(
            f"{atom.source_text} {getattr(atom, 'source_origin_text', '') or ''}" for atom in atoms
        ),
        clause_text=" ".join(str(unit.text) for unit in units),
        numeric_values=tuple(str(value.value) for value in owned_numbers),
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

    add(SOURCE_REQUIREMENT, point.requirement_summary, rule="CONCERN_SUMMARY_OWNED_ATOMS")
    templates = set(CONCERN_CHECKS.get(concern_id, ()))
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
    for value in owned_numbers[:4]:
        # only the numbers the row actually renders (its checks/criteria carry the
        # first four) become rendered components; further owned values stay data
        add(
            NUMERIC_STATEMENT,
            value_sentence(value.role, value.value, numeric_backing),
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


def order_review_items(items: Sequence[DynamicReviewItem]) -> list[DynamicReviewItem]:
    """Sort rows by business module, then risk, then source order."""

    risk_order = {"一票否决": 0, "高": 1, "中": 2}
    module_rank = {module: index for index, module in enumerate(MODULE_ORDER)}

    def key(item: DynamicReviewItem) -> tuple[int, int, str]:
        return (
            module_rank.get(item.module, len(MODULE_ORDER)),
            risk_order.get(item.risk_level, 3),
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

    compact = re.sub(r"\s+", "", evidence)
    if len(compact) < 6:
        return False
    for unit in units:
        haystack = re.sub(r"\s+", "", unit.text)
        for start in range(0, max(len(compact) - 11, 1), 6):
            window = compact[start : start + 12]
            if len(window) >= 8 and window in haystack:
                return True
        if compact[:12] in haystack:
            return True
    return False


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
    for item in plan.items:
        units = [units_by_id[rid] for rid in item.source_requirement_ids if rid in units_by_id]
        backing = " ".join(unit.text for unit in units)
        if not item.source_evidence.strip() or not backing.strip():
            empty_evidence.append(item.item_id)
        if item.source_page is None or item.source_page < 1 or not units:
            invalid_locator.append(item.item_id)
        elif not _shared_grounding(item.source_evidence, units):
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
