"""Review-point synthesis for the tender review workbook.

Round 2 of the review-workbook workstream replaces raw requirement concatenation
with *synthesized human review points*.  A review point answers four separate
questions, and the four answers are kept semantically distinct:

``requirement_summary``
    What the tender actually requires (source text, condensed -- never invented).
``review_checks``
    What the reviewer must inspect in the response document / supporting
    material.  One actionable check per entry.
``pass_criteria``
    The observable condition that means the check passes.
``failure_consequence``
    What happens when it fails -- only ever quoted from a source clause that
    states a consequence.

Design rules enforced here (see ``docs/V1_DECISIONS.md`` D41-D47):

* A number may appear in a review point only when its *semantic role* is proven
  by the clause it came from and that role is compatible with the row's
  requirement type.  Contact numbers, tender-document fees and unrelated
  quantities therefore never reach a check or a pass criterion.
* Source clauses that the bidder cannot act on (purchaser-internal evaluation
  procedure, discipline rules) are not review rows -- unless they are high risk
  or mandatory, in which case they are kept and flagged ``NEEDS_REVIEW``.
* A failure consequence is only attached when its sentence belongs to the row's
  own requirement topic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .dynamic_requirements import VALUE_TYPES, SourceRequirementUnit
from .models import ContractModel

# ---------------------------------------------------------------------------
# vocabularies
# ---------------------------------------------------------------------------

ACTIONABLE = "ACTIONABLE"
INTERNAL_PROCEDURE = "INTERNAL_PROCEDURE"

READY = "READY"
NEEDS_REVIEW = "NEEDS_REVIEW"

#: numeric semantic roles
ROLE_BOND_AMOUNT = "BOND_AMOUNT"
ROLE_VALIDITY_DAYS = "VALIDITY_DAYS"
ROLE_DURATION_DAYS = "DURATION_DAYS"
ROLE_WARRANTY_MONTHS = "WARRANTY_MONTHS"
ROLE_PRICE = "PRICE"
ROLE_SCORE = "SCORE"
ROLE_PAYMENT_RATIO = "PAYMENT_RATIO"
ROLE_PERSON_COUNT = "PERSON_COUNT"
ROLE_QUANTITY = "QUANTITY"
ROLE_RESPONSE_DAYS = "RESPONSE_DAYS"
ROLE_CONTACT = "CONTACT_INFO"
ROLE_TENDER_FEE = "TENDER_FEE"
ROLE_OTHER = "OTHER"

#: which roles may appear inside a row of a given requirement type
ROLES_BY_TYPE: dict[str, frozenset[str]] = {
    "PRICING": frozenset({ROLE_PRICE, ROLE_PAYMENT_RATIO}),
    "BOND": frozenset({ROLE_BOND_AMOUNT}),
    "VALIDITY": frozenset({ROLE_VALIDITY_DAYS}),
    "DURATION": frozenset({ROLE_DURATION_DAYS}),
    "WARRANTY": frozenset({ROLE_WARRANTY_MONTHS}),
    "QUALITY": frozenset({ROLE_WARRANTY_MONTHS}),
    "EVALUATION": frozenset({ROLE_SCORE, ROLE_PAYMENT_RATIO, ROLE_PRICE}),
    "CONTRACT": frozenset({ROLE_PAYMENT_RATIO, ROLE_PRICE, ROLE_WARRANTY_MONTHS}),
    "TECHNICAL": frozenset({ROLE_QUANTITY, ROLE_RESPONSE_DAYS}),
    "PERSONNEL": frozenset({ROLE_PERSON_COUNT}),
    "FINANCIAL": frozenset({ROLE_PRICE}),
    "WARRANTY": frozenset({ROLE_WARRANTY_MONTHS, ROLE_RESPONSE_DAYS}),
    "QUALITY": frozenset({ROLE_WARRANTY_MONTHS, ROLE_RESPONSE_DAYS}),
}

#: roles that are never a bidder review value, whatever the row type
NEVER_USABLE_ROLES = frozenset({ROLE_CONTACT, ROLE_TENDER_FEE, ROLE_OTHER})

_MONEY_RE = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:万元|元)")
_RATIO_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_SCORE_RE = re.compile(r"\d+(?:\.\d+)?\s*分")
_DURATION_RE = re.compile(r"\d+\s*(?:个)?(?:日历天|自然日|日|天|个月|月|年)")
_COUNT_RE = re.compile(r"\d+\s*(?:名|人|台|套|个|件|批|辆|次|项|份)")
_ALL_NUMBER_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:万元|元|%|分|名|人|台|套|个|件|批|辆|次|项|份|"
    r"个?日历天|自然日|日|天|个月|月|年|小时|分钟)?"
)

_BOND_CTX = ("保证金", "投标担保", "响应担保")
_VALIDITY_CTX = ("有效期", "投标有效")
_DURATION_CTX = ("工期", "交货期", "供货期", "服务期", "履约期", "完工", "交付期", "完成时间")
_WARRANTY_CTX = ("质保", "保修", "质量保证期", "免费维护", "运维期", "缺陷责任期")
_PRICE_CTX = ("报价", "限价", "预算", "最高限价", "控制价", "总价", "单价", "合价", "金额", "费用", "暂列金额", "暂估价")
_SCORE_CTX = ("得分", "评分", "分值", "加分", "扣分", "满分", "基础分")
_PAYMENT_CTX = (
    "付款", "支付", "预付", "进度款", "质保金", "结算", "款项",
    "价款", "涨幅", "风险范围", "价格调整", "调价",
)
_PERSON_CTX = ("人员", "成员", "评审小组", "评标委员会", "项目负责人", "项目经理", "专家", "员工", "社保")
_CONTACT_CTX = ("电话", "传真", "手机", "联系", "邮编", "邮箱", "邮箱", "地址", "网址", "平台", "http")
_FEE_CTX = ("标书", "招标文件费", "文件费", "工本费", "平台服务费", "服务费", "下载费", "资料费", "报名费")

#: purchaser-internal procedure with no bidder obligation
_INTERNAL_SUBJECT = re.compile(
    r"(评审小组|评标委员会|磋商小组|询比小组|采购小组|评审委员会|评委|专家)"
)
_INTERNAL_THEME = re.compile(
    r"(人数|成员|组成|回避|纪律|监督|廉洁|收受|擅离职守|抽取|名单|保密|分工|职责)"
)
_INTERNAL_PATTERNS = (
    re.compile(r"(评审小组|评标委员会|磋商小组|询比小组|采购小组).{0,12}(人数|成员|组成|专家|名单|组长)"),
    re.compile(r"(评审|评标|谈判|询比).{0,6}(纪律|回避|内部|保密|监督|廉洁)"),
    re.compile(r"(专家|评委).{0,6}(回避|抽取|库)"),
    re.compile(r"采购人.{0,6}(内部|纪检|审计)"),
    re.compile(r"(评审|评标)场地|开标室安排|内部监督"),
)

#: patterns that put an obligation on the bidder (as opposed to merely naming it)
_BIDDER_OBLIGATION_PATTERNS = (
    re.compile(r"(供应商|投标人|响应人|承包人|申请人)[^。；]{0,6}(须|应|需|必须|不得|应当)"),
    re.compile(
        r"(应|须|需|必须)[^。；]{0,8}(提交|递交|上传|加盖|签字|盖章|报价|提供|承诺|响应)"
    ),
    re.compile(r"响应文件[^。；]{0,6}(应|须|需|包含|包括)"),
)

_CONSEQUENCE_MARKERS: tuple[tuple[str, str], ...] = (
    ("否决投标", "响应被否决"),
    ("否决其投标", "响应被否决"),
    ("将被否决", "响应被否决"),
    ("予以否决", "响应被否决"),
    ("投标被否决", "响应被否决"),
    ("响应被否决", "响应被否决"),
    ("否决其响应", "响应被否决"),
    ("废标", "投标无效"),
    ("作废标处理", "投标无效"),
    ("无效投标", "投标无效"),
    ("投标无效", "投标无效"),
    ("响应无效", "投标无效"),
    ("响应文件无效", "投标无效"),
    ("按无效标处理", "投标无效"),
    ("不予受理", "不予受理"),
    ("不予评审", "不予评审"),
    ("无法评审", "无法评审"),
    ("不得分", "不得分"),
    ("扣分", "扣分"),
    ("取消投标资格", "取消投标资格"),
    ("取消中标资格", "取消中标资格"),
    ("需要澄清", "需要澄清"),
    ("拒收", "拒收"),
)

#: topic level review checks (seed).  Keyed by the source topic vocabulary.
_TOPIC_CHECKS: dict[str, tuple[str, ...]] = {
    "报价超过最高限价": ("逐项核对投标报价表中的总价及分项报价，与限价逐条比对",),
    "未按要求签字盖章": ("逐页核对招标文件指定位置的签字、盖章、电子签章是否齐全", "核对签署人与授权委托书上的被授权人是否一致"),
    "联合体不符合要求": ("确认响应文件中是否出现联合体协议或联合体承诺", "如不接受联合体，确认投标人主体为单一供应商"),
    "违法分包转包挂靠": ("确认响应文件中无违法分包、转包、挂靠的承诺或安排", "核对分包范围（如允许）是否在招标文件限定范围内"),
    "投标有效期不足": ("核对响应函中承诺的投标有效期是否达到招标文件要求", "确认有效期覆盖评审、定标与签约周期"),
    "保证金不符合要求": ("核对缴纳凭证的付款主体、收款账户与到账时间", "核对保证金金额与形式是否符合招标文件"),
    "资格条件不符合": ("逐条核对营业执照、许可证书与资格证明材料", "确认所有证书有效期覆盖投标截止日"),
    "未实质性响应": ("逐条比对实质性要求与响应文件对应条款，统计正负偏离", "确认无负偏离、无缺漏项"),
    "投标文件不完整或格式不符": ("按招标文件目录逐项清点响应文件组成", "确认无缺页、漏表、漏附件，格式与固定格式一致"),
    "关键信息不一致或异常一致": ("全文核对项目名称、编号、投标人名称、报价、工期等关键字段的一致性", "排查与其他投标人文件雷同、制作信息异常一致的风险"),
    "解密失败或未按时递交": ("在招标文件规定时间内完成上传与解密操作", "提前验证CA介质、客户端与网络环境并准备备用方案"),
    "报价异常或选择性报价": ("核对报价表是否只有一个有效总报价", "确认不存在选择性报价或被禁止的报价表达"),
    "其他否决情形": ("逐条核对招标文件列明的否决/无效情形是否出现", "留存逐条核对记录"),
    "禁止性情形与失信排除": ("在招标文件指定平台查询并留存查询结果截图", "确认不存在失信被执行人、严重违法失信等禁止性记录"),
    "串通投标或弄虚作假": ("核验业绩、证书、人员材料的真实性", "排查与其他投标人文件、联系信息、制作信息雷同等情形"),
    "定性评审与定标": ("按定性评审/定标程序准备评审材料并逐项对应评审要素", "确认定标所需材料齐全、可核查"),
    "评分标准与分值构成": ("将评分因素拆解为得分条件、证明材料、响应文件页码与预估得分", "确认每一项评分因素都有对应响应内容"),
    "业绩评分": ("核对业绩的时间、金额、规模与项目类型是否符合评分口径", "确认业绩证明链（合同、验收、发票）完整"),
    "人员评分": ("核对拟投入人员的证书、职称与劳动关系", "确认人员配置与评分要求一致"),
    "价格评分与基准价": ("核对价格评分公式、基准价规则与异常低价风险", "确认报价处于可评审区间"),
    "技术评分": ("核对技术方案的响应深度与证明材料", "确认每个评分点都有对应章节与页码"),
    "最高限价与控制价": ("在报价表中逐项核对总价与分项报价是否超过限价", "核对暂估价、暂列金额是否按给定金额计入"),
    "分项限价与暂列金额": ("按分项限价表逐项核对分项报价是否超过对应限价", "核对暂估价、暂列金额是否按给定金额计取且未自行调整"),
    "报价组成与费用范围": ("核对报价口径、单价、数量与合价", "确认无漏项、无重复计取"),
    "保证金金额": ("核对响应文件中的保证金金额与缴纳凭证金额一致",),
    "保证金形式": ("核对保证金缴纳形式是否属于招标文件允许的形式", "核对凭证类型与所选形式一致"),
    "保证金递交与凭证": ("核对付款主体、收款账户信息与到账时间", "确认凭证按规定位置随响应文件提交"),
    "投标保证金": ("核对保证金金额、形式、到账时间与凭证", "确认付款主体为投标人基本账户（如要求）"),
    "投标有效期": ("核对响应函承诺的有效期天数与起算点", "确认有效期覆盖评审与定标周期"),
    "签字盖章要求": ("按招标文件签章要求逐页核对签字人、盖章种类与位置", "确认授权链条完整、印章清晰"),
    "CA与电子签章": ("验证CA介质/数字证书在有效期内且为投标人本单位证书", "核对电子签章位置与签章后文件的可验证性"),
    "加密上传与解密": ("按平台要求完成加密、上传与解密演练", "确认文件格式、大小与上传区域符合要求"),
    "联合体": ("确认响应文件中的联合体安排与招标文件要求一致", "如允许联合体，核对联合体协议内容完整并明确牵头人"),
    "分包与转包": ("确认响应文件无违规分包、转包安排", "如允许分包，核对分包范围符合招标文件限制"),
    "营业执照与独立法人": ("核对营业执照主体名称、统一社会信用代码与经营范围", "确认具备独立承担民事责任的能力，扫描件清晰并按要求盖章"),
    "资质等级与许可": ("核对许可证书的类别、等级、有效期与发证机关", "确认证书类别、等级与发证机关达到规定条件"),
    "信用与失信查询": ("在招标文件指定平台查询并留存查询截图", "确认查询结果无禁止性记录且截图在有效期内取得"),
    "特定资格条件": ("逐条核对特定资格条件对应的证明材料", "确认材料齐全、有效、与投标人主体一致"),
    "项目负责人资格": ("核对拟派项目负责人的注册证书与执业资格", "确认其在岗情况与社保关系符合要求"),
    "安全与管理人员": ("核对安全管理人员的证书类别、有效期与配备数量", "确认配备数量达到规定要求"),
    "人员社保与劳动关系": ("核对社保缴纳证明的月份区间与缴费单位", "确认缴费单位名称与投标人名称一致"),
    "人员配置要求": ("按招标文件人员配置表逐岗核对人员与证书", "确认无空缺岗位、无重复挂靠"),
    "类似项目业绩": ("核对类似业绩的时间、金额与规模是否满足要求", "确认业绩证明链完整、可核验"),
    "财务与审计报告": ("按招标文件指定年度/期间提供财务材料", "核对主体名称、数据口径与盖章"),
    "纳税与社保凭证": ("按指定月份/周期提供缴纳证明", "核对缴费主体与所属期间"),
    "财务承诺函": ("按招标文件格式出具财务能力承诺", "核对承诺内容与招标文件要求一致"),
    "★条款与强制参数": ("逐条列示★/强制条款的响应值", "确认无空白、无模糊表述，并附证明材料"),
    "技术参数与配置": ("按技术参数表逐项填写响应值", "确认响应值与报价表、技术资料一致"),
    "接口与集成": ("核对接口、协议与平台对接的技术方案", "确认方案可实施并附承诺"),
    "数据迁移与上线": ("核对数据迁移范围与迁移方案", "核对上线切换与回退预案"),
    "安装调试与验收": ("核对安装、调试、检测与验收标准", "确认验收节点与招标文件要求一致"),
    "培训与售后服务": ("核对培训安排与售后服务响应时间承诺", "确认备件、服务网点等承诺可量化、可履约"),
    "售后服务与运维": ("核对售后服务响应时间、服务方式与运维人员配置承诺", "确认服务网点、备件供应等承诺可履约"),
    "技术方案与实施组织": ("核对技术方案、进度计划与人员机具配置", "核对质量保证措施与应急预案"),
    "质量要求": ("核对质量承诺与招标文件质量目标/验收标准是否一致", "确认质量责任与违约责任已落入合同条款"),
    "工期与供货期": ("核对响应函与进度计划中的工期/供货期", "确认覆盖全部交付节点与验收节点"),
    "交付与实施地点": ("核对交付/实施地点、批次与服务范围", "确认与招标文件要求一致"),
    "质保与保修": ("核对质保期承诺与质保范围", "确认响应方式、费用承担与招标文件一致"),
    "合同条款与付款": ("核对合同条款响应、付款方式与结算依据", "确认无采购人不能接受的附加条件或偏差"),
    "证明材料要求": ("按招标文件要求准备证明材料", "确认清晰、完整、可核验并按要求盖章"),
    "投标文件格式": ("按招标文件格式要求编排、装订并编制目录与页码", "确认使用规定的固定格式"),
    "投标文件组成": ("按招标文件组成清单逐项清点响应文件章节与附表", "确认无遗漏、无多余内容冲突"),
    "递交方式与截止时间": ("核对递交方式、递交地点/平台与截止时间", "确认预留足够提前量并完成签到/解密准备"),
    "封装与密封": ("核对正副本份数与密封方式", "核对骑缝章与标注信息符合要求"),
    "费用与付款": ("核对相关费用口径与付款安排是否已按招标文件响应",),
    "评审计分": ("将评审得分要素拆解为得分条件与证明材料", "确认响应文件中有对应章节支撑"),
    "文件组成与格式": ("按招标文件清单核对响应文件组成与格式",),
    "程序性要求": ("按招标文件程序性要求逐项准备并核对响应文件",),
    "其他要求": ("按招标文件要求逐项核对响应文件的对应内容",),
    "一般要求": ("按招标文件要求逐项核对响应文件的对应内容",),
}

_PASS_BY_TYPE: dict[str, str] = {
    "PRICING": "报价总价与各分项均不超过规定限价，且与报价表、一览表金额一致。",
    "BOND": "保证金金额、形式、到账时间与凭证全部达到规定要求。",
    "VALIDITY": "投标有效期承诺不低于规定天数，覆盖评审与定标全过程。",
    "SIGNATURE": "所有指定位置签字/盖章齐全有效，授权链条一致。",
    "ELECTRONIC": "CA介质有效、文件加密上传成功、可按时解密。",
    "REJECTION": "不存在该条列明的否决/无效情形。",
    "QUALIFICATION": "资格材料齐全有效，主体信息一致。",
    "PERSONNEL": "拟投入人员的证书与劳动关系达到规定要求且相互一致。",
    "PERFORMANCE": "业绩数量、规模与时间达到规定口径。",
    "FINANCIAL": "财务材料按指定期间提供，主体名称与投标人一致。",
    "CREDIT": "指定平台查询结果无禁止性记录，并留存查询结果。",
    "CONSORTIUM": "联合体安排与规定完全一致。",
    "SUBCONTRACT": "无违规分包、转包、挂靠情形。",
    "DURATION": "工期/供货期承诺达到规定期限，且覆盖全部交付节点。",
    "LOCATION": "交付/实施地点与服务范围与规定一致。",
    "QUALITY": "质量承诺达到规定质量目标与验收标准。",
    "WARRANTY": "质保期与质保范围不低于规定期限。",
    "TECHNICAL": "技术要求逐条响应，证明材料可核验，无负偏离。",
    "EVALUATION": "每个评分因素都有对应响应内容与证明材料，预估得分可追溯。",
    "PROOF": "证明材料齐全、清晰并与响应内容对应。",
    "FORM": "响应文件格式、组成与编排符合规定。",
    "SUBMISSION": "在规定时间前按要求完成递交/上传与解密。",
    "PACKAGING": "封装、密封、份数与标注符合规定。",
    "CONTRACT": "合同条款、付款与履约承诺与规定一致。",
    "OTHER": "响应文件对应内容与该条款一致。",
}

#: material hints: source keyword -> preparation material suggestion
_PREPARATION_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("营业执照",), "营业执照副本扫描件（加盖公章）"),
    (("许可证", "资质"), "资质/许可证书扫描件"),
    (("财务", "审计报告"), "经审计的财务报告或财务状况承诺书"),
    (("社保", "社会保险"), "社保缴纳证明"),
    (("纳税", "完税"), "纳税证明"),
    (("业绩", "合同"), "类似项目合同及验收证明"),
    (("查询截图", "信用中国", "失信"), "指定平台查询结果截图"),
    (("保函", "保证金"), "保证金缴纳凭证或银行保函"),
    (("保证金", "基本账户", "基本户"), "基本账户开户证明"),
    (("技术参数", "★"), "技术参数响应对照表"),
    (("检测报告",), "检测报告"),
    (("承诺函", "承诺书"), "承诺函（按招标文件格式）"),
    (("授权", "委托"), "法定代表人授权委托书"),
    (("报价", "限价"), "投标报价表/开标一览表"),
    (("进度计划", "工期"), "进度计划或供货计划表"),
    (("培训",), "培训方案"),
    (("样品",), "样品或样册"),
)

_GENERIC_PHRASES = (
    "符合招标文件要求",
    "满足招标文件要求",
    "按招标文件要求执行",
    "按上述招标文件条款",
    "确认完全响应",
    "金额、形式、时间符合招标文件要求",
)


def grounding_terms() -> tuple[str, ...]:
    """Concept vocabulary that may only appear when the source supports it."""

    from .dynamic_requirements import TOPIC_LEXICON

    try:  # lazily imported to avoid a cycle: dynamic_review imports this module
        from .dynamic_review import CONCEPT_TERMS
    except Exception:  # pragma: no cover - defensive
        CONCEPT_TERMS = ()
    return tuple(TOPIC_LEXICON) + tuple(CONCEPT_TERMS)


def line_is_grounded(text: str, backing: str) -> bool:
    """True when every guarded concept in ``text`` also occurs in ``backing``."""

    lowered = backing.lower()
    for term in grounding_terms():
        low = term.lower()
        if low in text.lower() and low not in lowered:
            return False
    return True


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


class NumericEvidence(ContractModel):
    """One number found in the row's own clauses, with its proven role."""

    value: str
    role: str
    usable: bool
    unit_id: str
    source_page: int | None = None
    context: str = ""


class ReviewPoint(ContractModel):
    """The single semantic object rendered into the legacy sheet and 02/03."""

    requirement_type: str
    topic: str
    actionability: str = ACTIONABLE
    status: str = READY
    requirement_summary: str
    review_checks: list[str]
    pass_criteria: list[str]
    failure_consequence: str = ""
    preparation_materials: list[str] = []
    scoring_guidance: str = ""
    linked_fact_keys: list[str] = []
    evidence_ids: list[str] = []
    numeric_evidence: list[NumericEvidence] = []
    consequence_evidence_id: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# numeric provenance
# ---------------------------------------------------------------------------


def _window(text: str, start: int, end: int, radius: int) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def _role_for(text: str, value: str, start: int, end: int) -> str:
    near = _window(text, start, end, 12)
    wide = _window(text, start, end, 30)
    has_money = "元" in value or "万元" in value
    if any(term in near for term in _CONTACT_CTX):
        return ROLE_CONTACT
    if not has_money and re.fullmatch(r"\d{7,}", value) and not any(
        term in near for term in _CONTACT_CTX
    ):
        # a long bare digit run is a contact/reference, never a requirement value
        return ROLE_CONTACT
    if any(term in near for term in _FEE_CTX):
        return ROLE_TENDER_FEE
    if has_money:
        if any(term in wide for term in _BOND_CTX):
            return ROLE_BOND_AMOUNT
        if any(term in wide for term in _PRICE_CTX):
            return ROLE_PRICE
        if any(term in wide for term in _FEE_CTX):
            return ROLE_TENDER_FEE
        return ROLE_OTHER
    if "%" in value:
        if any(term in wide for term in _PAYMENT_CTX):
            return ROLE_PAYMENT_RATIO
        if any(term in wide for term in _SCORE_CTX):
            return ROLE_SCORE
        return ROLE_OTHER
    if "分" in value and any(term in wide for term in _SCORE_CTX):
        return ROLE_SCORE
    if re.search(r"(日历天|自然日|日|天|个月|月|年|小时|分钟)", value):
        if any(term in wide for term in _WARRANTY_CTX):
            if re.search(r"小时|分钟|日|天", value) and not re.search(r"个月|月|年", value):
                return ROLE_RESPONSE_DAYS
            return ROLE_WARRANTY_MONTHS
        if any(term in wide for term in _VALIDITY_CTX):
            return ROLE_VALIDITY_DAYS
        if any(term in wide for term in _DURATION_CTX):
            return ROLE_DURATION_DAYS
        return ROLE_OTHER
    if re.search(r"(名|位)", value) or re.fullmatch(r"\d+\s*人", value):
        return ROLE_PERSON_COUNT
    if re.search(r"(台|套|个|件|批|辆|次|项|份|人)", value):
        if re.search(r"(台|套|个|件|批|辆|次|项|份)", value):
            return ROLE_QUANTITY
        return ROLE_PERSON_COUNT
    return ROLE_OTHER


def _is_reference_number(text: str, start: int, end: int, value: str) -> bool:
    """True for page/clause references such as ``第 9 页`` or ``3.4.1 项``.

    A locator is not a requirement value: it must never be counted, rendered or
    reported as a numeric finding.
    """

    if start > 0 and text[start - 1] == "第":
        return True
    if value[-1:] in {"页", "条", "款", "章", "项", "节"} and start > 0 and text[start - 1] == "第":
        return True
    if re.match(r"^\d+(?:\.\d+){1,}", value):
        return True
    tail = text[end : end + 1]
    if tail in {"页", "条", "款", "章", "节"}:
        return True
    return False


def extract_numeric_evidence(units: Sequence[SourceRequirementUnit]) -> list[NumericEvidence]:
    """Collect the numbers of the row's own clauses together with their roles."""

    found: list[NumericEvidence] = []
    seen: set[tuple[str, str]] = set()
    for unit in units:
        text = unit.text
        for match in _ALL_NUMBER_RE.finditer(text):
            raw = match.group(0).strip()
            if not raw or not re.search(r"\d", raw):
                continue
            value = re.sub(r"\s+", "", raw)
            if _is_reference_number(text, match.start(), match.end(), value):
                continue
            role = _role_for(text, value, match.start(), match.end())
            key = (value, role)
            if key in seen:
                continue
            seen.add(key)
            context = re.sub(r"\s+", " ", _window(text, match.start(), match.end(), 14)).strip()
            found.append(
                NumericEvidence(
                    value=value,
                    role=role,
                    usable=False,
                    unit_id=unit.requirement_id,
                    source_page=unit.page,
                    context=context,
                )
            )
    return found


def usable_numbers(requirement_type: str, evidence: Sequence[NumericEvidence]) -> list[NumericEvidence]:
    """Numbers whose role is compatible with the row's requirement type."""

    allowed = ROLES_BY_TYPE.get(requirement_type, frozenset())
    usable: list[NumericEvidence] = []
    for item in evidence:
        if item.role in NEVER_USABLE_ROLES or item.role not in allowed:
            continue
        if item.value in {existing.value for existing in usable}:
            continue
        usable.append(item)
    return usable


# ---------------------------------------------------------------------------
# actionability
# ---------------------------------------------------------------------------


def is_internal_procedure(unit: SourceRequirementUnit) -> bool:
    """True when the clause describes purchaser-internal procedure only."""

    text = unit.text
    subject = bool(_INTERNAL_SUBJECT.search(text))
    theme = bool(_INTERNAL_THEME.search(text))
    matched = (subject and theme) or any(pattern.search(text) for pattern in _INTERNAL_PATTERNS)
    if not matched:
        return False
    return not any(pattern.search(text) for pattern in _BIDDER_OBLIGATION_PATTERNS)


def classify_group(units: Sequence[SourceRequirementUnit]) -> str:
    internal = [unit for unit in units if is_internal_procedure(unit)]
    if internal and len(internal) == len(units):
        return INTERNAL_PROCEDURE
    if len(internal) > len(units) / 2:
        return INTERNAL_PROCEDURE
    return ACTIONABLE


def group_is_filterable(units: Sequence[SourceRequirementUnit], actionability: str) -> bool:
    """A group may only be dropped when nothing forces coverage.

    Two classes are dropped: purchaser-internal procedure, and clauses that only
    state a document/platform fee (a purchaser cost item with no bidder
    obligation).  High-risk and mandatory units always keep their row.
    """

    if any(unit.high_risk or unit.mandatory for unit in units):
        return False
    if actionability == INTERNAL_PROCEDURE:
        return True
    return bool(units) and all(_is_fee_clause(unit.text) for unit in units)


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------


def _clean(text: str) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    value = re.sub(r"^[；;、,，。\.]+", "", value)
    return value.strip()


def _sentence_containing(text: str, position: int) -> str:
    start = 0
    for mark in ("。", "；", ";", "\n"):
        found = text.rfind(mark, 0, position)
        if found > start:
            start = found + 1
    end = len(text)
    for mark in ("。", "；", ";", "\n"):
        found = text.find(mark, position)
        if found != -1:
            end = min(end, found + 1)
    return _clean(text[start:end])


def _truncate(text: str, limit: int) -> str:
    value = _clean(text)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip("，,；;、 ") + "…"


def _topic_terms(topic: str) -> list[str]:
    terms: list[str] = []
    for chunk in re.split(r"[与和及]", topic):
        chunk = chunk.strip()
        if len(chunk) >= 2:
            terms.append(chunk)
    return terms


def _is_fee_clause(text: str) -> bool:
    """True when the clause only states a document/platform fee.

    Such a clause is a purchaser cost item, not a bidder obligation, so it never
    becomes the summary or a value of an unrelated review row.
    """

    if "保证金" in text:
        return False
    return any(term in text for term in _FEE_CTX)


def _summarize_requirement(
    units: Sequence[SourceRequirementUnit],
    limit: int = 180,
    must_include: Sequence[str] = (),
) -> str:
    """Condense the row's clauses into the operative statement.

    Clauses that only restate boilerplate ("符合招标文件要求") are pushed to the
    back so a row with concrete content is summarized by the concrete content.
    When the row carries concrete values, the summary keeps at least one of them
    verbatim: the summary is a source quote, so this stays evidence, not claim.
    """

    def rank(unit: SourceRequirementUnit) -> tuple[int, int, int, int]:
        generic = any(phrase in unit.text for phrase in _GENERIC_PHRASES)
        fee = _is_fee_clause(unit.text)
        return (
            0 if generic else 1,
            0 if fee else 1,
            int(bool(unit.mandatory or unit.high_risk)),
            len(unit.values),
        )

    ordered = sorted(units, key=rank, reverse=True)
    concrete = [
        unit
        for unit in ordered
        if not any(phrase in unit.text for phrase in _GENERIC_PHRASES)
        and not _is_fee_clause(unit.text)
    ]
    candidates = concrete or ordered
    if must_include and not any(
        any(value in unit.text for value in must_include) for unit in candidates[:1]
    ):
        carriers = [unit for unit in candidates if any(value in unit.text for value in must_include)]
        if carriers:
            candidates = carriers[:1] + [unit for unit in candidates if unit not in carriers]
    excerpts: list[str] = []
    for unit in candidates:
        excerpt = _truncate(unit.text, 110)
        if not excerpt:
            continue
        if any(excerpt[:18] == existing[:18] for existing in excerpts):
            continue
        excerpts.append(excerpt)
        if len(excerpts) == 2:
            break
    summary = "；".join(excerpts)
    if not summary:
        summary = _truncate(ordered[0].text, limit)
    return _truncate(summary, limit)


def _anchor(units: Sequence[SourceRequirementUnit]) -> str:
    """A short source reference for the row: page and clause only.

    The section title often carries its own numbering ("5、最高限价"), which must
    not leak into the check text as if it were a requirement value.
    """

    primary = sorted(units, key=lambda unit: (unit.mandatory, unit.high_risk), reverse=True)[0]
    parts: list[str] = []
    if primary.page:
        parts.append(f"第{primary.page}页")
    if primary.clause:
        parts.append(f"第{primary.clause}条")
    if not parts and primary.section and not re.search(r"\d", primary.section):
        parts.append(primary.section[:12])
    return "".join(parts)


def _value_sentence(role: str, value: str) -> str:
    if role == ROLE_BOND_AMOUNT:
        return f"保证金金额为 {value}"
    if role == ROLE_VALIDITY_DAYS:
        return f"投标有效期不少于 {value}"
    if role == ROLE_DURATION_DAYS:
        return f"工期/供货期满足 {value}"
    if role == ROLE_WARRANTY_MONTHS:
        return f"质保期不低于 {value}"
    if role == ROLE_RESPONSE_DAYS:
        return f"服务响应时间不超过 {value}"
    if role == ROLE_PRICE:
        return f"金额/限价为 {value}"
    if role == ROLE_SCORE:
        return f"该评分因素最高 {value}"
    if role == ROLE_PAYMENT_RATIO:
        return f"付款/计分比例为 {value}"
    if role == ROLE_PERSON_COUNT:
        return f"人员配备数量为 {value}"
    if role == ROLE_QUANTITY:
        return f"数量要求为 {value}"
    return f"指标为 {value}"


# ---------------------------------------------------------------------------
# synthesis
# ---------------------------------------------------------------------------


def _failure_consequence(
    units: Sequence[SourceRequirementUnit], topic: str
) -> tuple[str, str]:
    """Return (consequence text, source unit id).  Never invents a consequence."""

    for unit in sorted(units, key=lambda unit: (unit.mandatory, unit.high_risk), reverse=True):
        for marker, label in _CONSEQUENCE_MARKERS:
            position = unit.text.find(marker)
            if position < 0:
                continue
            sentence = _sentence_containing(unit.text, position)
            if len(sentence) < 6:
                sentence = label
            return _truncate(sentence, 120), unit.requirement_id
    return "", ""


def _concrete_values(units: Sequence[SourceRequirementUnit]) -> list[str]:
    values: list[str] = []
    for unit in units:
        for value in unit.values:
            if value not in values:
                values.append(value)
    return values


def _preparation_materials(units: Sequence[SourceRequirementUnit], limit: int = 4) -> list[str]:
    backing = " ".join(unit.text for unit in units)
    materials: list[str] = []
    for keywords, material in _PREPARATION_HINTS:
        if any(keyword in backing for keyword in keywords) and material not in materials:
            materials.append(material)
        if len(materials) == limit:
            break
    return materials


def _scoring_guidance(requirement_type: str, units: Sequence[SourceRequirementUnit]) -> str:
    if requirement_type != "EVALUATION" and not any(
        keyword in unit.text for unit in units for keyword in ("评分", "得分", "分值")
    ):
        return ""
    scores = [
        evidence
        for evidence in extract_numeric_evidence(units)
        if evidence.role == ROLE_SCORE
    ]
    parts = ["按“得分条件—证明材料—响应文件位置—预估得分”逐项落实。"]
    if scores:
        parts.append("分值线索：" + "、".join(dict.fromkeys(item.value for item in scores[:4])) + "。")
    return "".join(parts)


def synthesize_review_point(
    *,
    units: Sequence[SourceRequirementUnit],
    requirement_type: str,
    topic: str,
    fact_hints: Mapping[str, str],
    linked_fields: Sequence[str] = (),
) -> ReviewPoint | None:
    """Synthesize one review point.  ``None`` means "not an actionable row"."""

    if not units:
        return None
    actionability = classify_group(units)
    if group_is_filterable(units, actionability):
        return None

    evidence = extract_numeric_evidence(units)
    usable = usable_numbers(requirement_type, evidence)
    for item in evidence:
        item.usable = item in usable

    backing = " ".join(unit.text for unit in units)
    checks: list[str] = []
    checks.extend(_TOPIC_CHECKS.get(topic, _TOPIC_CHECKS["一般要求"]))
    anchor = _anchor(units)
    if anchor:
        checks.append(f"依据{anchor}逐条比对响应文件对应章节")

    for item in usable[:3]:
        if item.role in {ROLE_QUANTITY, ROLE_PERSON_COUNT}:
            continue
        sentence = _value_sentence(item.role, item.value)
        if any(sentence in check for check in checks):
            continue
        checks.append(f"核对响应文件已载明：{sentence}")

    facts_used: list[str] = []
    for field in linked_fields:
        hint = fact_hints.get(field, "")
        if not hint:
            continue
        facts_used.append(hint)
        checks.append(f"与项目事实核对：{hint}")

    pass_criteria: list[str] = [_PASS_BY_TYPE.get(requirement_type, _PASS_BY_TYPE["OTHER"])]
    for item in usable[:2]:
        pass_criteria.append(f"{_value_sentence(item.role, item.value)}，且响应文件一致。")

    # A synthesized line may only name concepts the row's own clauses contain.
    checks = [check for check in checks if line_is_grounded(check, backing)]
    pass_criteria = [line for line in pass_criteria if line_is_grounded(line, backing)]
    preparation = [
        material for material in _preparation_materials(units) if line_is_grounded(material, backing)
    ]

    consequence, consequence_unit = _failure_consequence(units, topic)

    point = ReviewPoint(
        requirement_type=requirement_type,
        topic=topic,
        actionability=actionability,
        status=READY if actionability == ACTIONABLE else NEEDS_REVIEW,
        requirement_summary=_summarize_requirement(
            units,
            must_include=(
                [value for value in _concrete_values(units)]
                if requirement_type in VALUE_TYPES
                else []
            ),
        ),
        review_checks=list(dict.fromkeys(check for check in checks if check)),
        pass_criteria=list(dict.fromkeys(criterion for criterion in pass_criteria if criterion)),
        failure_consequence=consequence,
        preparation_materials=preparation,
        scoring_guidance=_scoring_guidance(requirement_type, units),
        linked_fact_keys=list(linked_fields),
        evidence_ids=[unit.requirement_id for unit in units][:60],
        numeric_evidence=evidence,
        consequence_evidence_id=consequence_unit,
    )
    if actionability == INTERNAL_PROCEDURE:
        point.notes = "该条款主要描述采购人内部评审程序；因涉及高风险或强制要求而保留，需人工判断是否存在投标人义务。"
    return point


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def render_checks(point: ReviewPoint) -> str:
    marks = "①②③④⑤⑥⑦⑧⑨"
    lines = []
    for index, check in enumerate(point.review_checks):
        mark = marks[index] if index < len(marks) else f"({index + 1})"
        lines.append(f"{mark} {check}")
    return "\n".join(lines)


def render_pass_criteria(point: ReviewPoint) -> str:
    return "\n".join(f"· {criterion}" for criterion in point.pass_criteria)


def render_review_cell(point: ReviewPoint) -> str:
    """Render the legacy D-column review text (only material blocks)."""

    blocks = [f"招标文件要求：{point.requirement_summary}"]
    if point.review_checks:
        blocks.append("复核要点：\n" + render_checks(point))
    if point.pass_criteria:
        blocks.append("通过标准：\n" + render_pass_criteria(point))
    if point.failure_consequence:
        blocks.append(f"不满足后果：{point.failure_consequence}")
    if point.preparation_materials:
        blocks.append("准备材料：" + "、".join(point.preparation_materials))
    if point.scoring_guidance:
        blocks.append(f"评分提示：{point.scoring_guidance}")
    return "\n".join(block for block in blocks if block.strip())


# ---------------------------------------------------------------------------
# quality scanning (used by the gate and the content-quality report)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityScan:
    rows: int
    actionable_rows: int
    non_actionable_rows: int
    generic_boilerplate_rows: int
    semantic_contamination_rows: int
    numeric_contamination_rows: int
    source_backed_consequence_rows: int
    unsupported_consequence_rows: int
    checks_without_observable_noun: int

    def as_dict(self) -> dict[str, int]:
        return {
            "rows": self.rows,
            "actionable_rows": self.actionable_rows,
            "non_actionable_rows": self.non_actionable_rows,
            "generic_boilerplate_rows": self.generic_boilerplate_rows,
            "semantic_contamination_rows": self.semantic_contamination_rows,
            "numeric_contamination_rows": self.numeric_contamination_rows,
            "source_backed_consequence_rows": self.source_backed_consequence_rows,
            "unsupported_consequence_rows": self.unsupported_consequence_rows,
            "checks_without_observable_noun": self.checks_without_observable_noun,
        }


_OBSERVABLE_TERMS = (
    "核对", "比对", "确认", "清点", "查询", "验证", "核验", "检查", "提交", "载明",
    "一致", "齐全", "有效", "覆盖", "留存", "对照", "逐条", "逐项", "提供", "准备",
    "出具", "编制", "完成", "拆解", "落实", "排查", "统计", "记录", "满足", "符合",
)


def _review_only_text(point: ReviewPoint) -> str:
    parts = list(point.review_checks) + list(point.pass_criteria)
    if point.preparation_materials:
        parts.extend(point.preparation_materials)
    if point.scoring_guidance:
        parts.append(point.scoring_guidance)
    return "\n".join(parts)


_LOCATOR_LINE_PREFIXES = ("依据第", "与项目事实核对")


def _claim_text(point: ReviewPoint) -> str:
    """Synthesized lines excluding locator references and fact pointers."""

    lines = _review_only_text(point).splitlines()
    return "\n".join(
        line for line in lines if not line.startswith(_LOCATOR_LINE_PREFIXES)
    )


def _numeric_tokens(text: str) -> set[str]:
    """Numbers actually present in a text, as whole tokens."""

    return {
        re.sub(r"\s+", "", match.group(0))
        for match in _ALL_NUMBER_RE.finditer(text)
        if re.search(r"\d", match.group(0))
    }


def scan_review_point(point: ReviewPoint) -> dict[str, bool]:
    """Per-row quality flags; the gate aggregates them into counters.

    A number quoted inside ``requirement_summary`` or ``failure_consequence`` is
    source evidence, not a synthesized claim, so only the synthesized lines
    (checks, pass criteria, preparation, scoring) are scanned for contamination.
    """

    generic = any(phrase in _review_only_text(point) for phrase in _GENERIC_PHRASES)
    allowed = ROLES_BY_TYPE.get(point.requirement_type, frozenset())
    present = _numeric_tokens(_claim_text(point))
    usable_values = {item.value for item in point.numeric_evidence if item.usable}
    contamination = sorted(
        {
            item.value
            for item in point.numeric_evidence
            if not item.usable and item.value in present and item.value not in usable_values
        }
    )
    semantic = sorted(
        {
            item.value
            for item in point.numeric_evidence
            if item.usable and item.role not in allowed
        }
    )
    checks_ok = all(
        any(term in check for term in _OBSERVABLE_TERMS) for check in point.review_checks
    )
    return {
        "generic": generic,
        "numeric_contamination": bool(contamination),
        "semantic_contamination": bool(semantic),
        "unsupported_consequence": bool(point.failure_consequence)
        and not _consequence_supported(point),
        "checks_without_observable_noun": bool(point.review_checks) and not checks_ok,
    }


def _consequence_supported(point: ReviewPoint) -> bool:
    """A consequence is supported only when its own source clause is recorded."""

    if not point.failure_consequence:
        return True
    return bool(point.consequence_evidence_id) and (
        not point.evidence_ids or point.consequence_evidence_id in point.evidence_ids
    )


def scan_review_points(points: Iterable[ReviewPoint]) -> QualityScan:
    rows = list(points)
    flags = [scan_review_point(point) for point in rows]
    return QualityScan(
        rows=len(rows),
        actionable_rows=sum(1 for point in rows if point.actionability == ACTIONABLE),
        non_actionable_rows=sum(1 for point in rows if point.actionability != ACTIONABLE),
        generic_boilerplate_rows=sum(1 for flag in flags if flag["generic"]),
        semantic_contamination_rows=sum(1 for flag in flags if flag["semantic_contamination"]),
        numeric_contamination_rows=sum(1 for flag in flags if flag["numeric_contamination"]),
        source_backed_consequence_rows=sum(1 for point in rows if point.failure_consequence),
        unsupported_consequence_rows=sum(1 for flag in flags if flag["unsupported_consequence"]),
        checks_without_observable_noun=sum(
            1 for flag in flags if flag["checks_without_observable_noun"]
        ),
    )


__all__ = [
    "ACTIONABLE",
    "INTERNAL_PROCEDURE",
    "NEEDS_REVIEW",
    "READY",
    "NumericEvidence",
    "QualityScan",
    "ReviewPoint",
    "ROLES_BY_TYPE",
    "classify_group",
    "extract_numeric_evidence",
    "group_is_filterable",
    "is_internal_procedure",
    "render_checks",
    "render_pass_criteria",
    "render_review_cell",
    "scan_review_point",
    "scan_review_points",
    "synthesize_review_point",
    "usable_numbers",
]
