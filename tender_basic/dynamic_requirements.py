"""Round 5.5 source-requirement index.

This module turns the tender document into first-class, evidence-backed
requirement records.  It is deliberately deterministic: every record keeps the
exact source locator and the source clause text it was derived from, and no
requirement is ever invented from a template or a case name.

The index is the recall side of the dynamic review architecture.  Review rows
are projected from it by :mod:`tender_basic.dynamic_review`; the QA in the same
module re-scans the source independently and fails when a high-risk mandatory
requirement is not covered by at least one generated review item.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from pydantic import Field

from .document_models import NormalizedDocument
from .document_parser import normalize_text
from .models import ContractModel, Locator
from .review_evidence import iter_source_fragments
from .source_criticality import MARKER_CLASS

# --------------------------------------------------------------------------
# taxonomy
# --------------------------------------------------------------------------

RequirementType = Literal[
    "REJECTION",
    "QUALIFICATION",
    "PERSONNEL",
    "PERFORMANCE",
    "FINANCIAL",
    "CREDIT",
    "CONSORTIUM",
    "SUBCONTRACT",
    "PRICING",
    "BOND",
    "VALIDITY",
    "SIGNATURE",
    "ELECTRONIC",
    "DURATION",
    "LOCATION",
    "QUALITY",
    "WARRANTY",
    "TECHNICAL",
    "EVALUATION",
    "PROOF",
    "FORM",
    "SUBMISSION",
    "PACKAGING",
    "CONTRACT",
    "OTHER",
]

MODULE_REJECTION = "一、废标红线"
MODULE_QUALIFICATION = "二、资格审查"
MODULE_DOCUMENT = "三、投标文件组成与格式"
MODULE_COMMERCIAL = "四、报价与合同商务"
MODULE_TECHNICAL = "五、技术响应"
MODULE_EVALUATION = "六、评分项复核"
MODULE_EVALUATION_QUALITATIVE = "六、定性评审与定标材料"
MODULE_SIGNATURE = "七、签章与电子标"
MODULE_SUBMISSION = "八、递交与开标准备"

MODULE_ORDER: tuple[str, ...] = (
    MODULE_REJECTION,
    MODULE_QUALIFICATION,
    MODULE_DOCUMENT,
    MODULE_COMMERCIAL,
    MODULE_TECHNICAL,
    MODULE_EVALUATION,
    MODULE_EVALUATION_QUALITATIVE,
    MODULE_SIGNATURE,
    MODULE_SUBMISSION,
)

TYPE_MODULE: dict[str, str] = {
    "REJECTION": MODULE_REJECTION,
    "QUALIFICATION": MODULE_QUALIFICATION,
    "PERSONNEL": MODULE_QUALIFICATION,
    "PERFORMANCE": MODULE_QUALIFICATION,
    "FINANCIAL": MODULE_QUALIFICATION,
    "CREDIT": MODULE_QUALIFICATION,
    "CONSORTIUM": MODULE_QUALIFICATION,
    "SUBCONTRACT": MODULE_QUALIFICATION,
    "PRICING": MODULE_COMMERCIAL,
    "BOND": MODULE_COMMERCIAL,
    "VALIDITY": MODULE_COMMERCIAL,
    "DURATION": MODULE_COMMERCIAL,
    "LOCATION": MODULE_COMMERCIAL,
    "QUALITY": MODULE_COMMERCIAL,
    "WARRANTY": MODULE_COMMERCIAL,
    "CONTRACT": MODULE_COMMERCIAL,
    "TECHNICAL": MODULE_TECHNICAL,
    "EVALUATION": MODULE_EVALUATION,
    "PROOF": MODULE_DOCUMENT,
    "FORM": MODULE_DOCUMENT,
    "SIGNATURE": MODULE_SIGNATURE,
    "ELECTRONIC": MODULE_SIGNATURE,
    "SUBMISSION": MODULE_SUBMISSION,
    "PACKAGING": MODULE_SUBMISSION,
    "OTHER": MODULE_DOCUMENT,
}

#: Requirement families whose failure the source treats as fatal.
STRONG_MARKERS: tuple[str, ...] = (
    "否决投标",
    "否决其投标",
    "将被否决",
    "予以否决",
    "投标被否决",
    "否决",
    "废标",
    "作废标处理",
    "无效投标",
    "投标无效",
    "响应无效",
    "响应文件无效",
    "无效响应",
    "作无效处理",
    "按无效标处理",
    "不予评审",
    "不予受理",
    "实质性要求",
    "实质性响应",
    "未实质响应",
    "重大偏差",
    "串通投标",
    "围标",
    "弄虚作假",
    "虚假材料",
    "提供虚假",
    "伪造",
    "取消投标资格",
    "取消中标资格",
)

#: Ordinary mandatory wording.  ``应``/``须`` are intentionally not included on
#: their own because they appear in descriptive prose as well.
MANDATORY_MARKERS: tuple[str, ...] = (
    "必须",
    "应当",
    "不得",
    "不允许",
    "不接受",
    "禁止",
    "严禁",
    "须提供",
    "须提交",
    "须加盖",
    "须为",
    "不低于",
    "不超过",
    "不少于",
    "不得低于",
    "不得高于",
    "应提供",
    "应提交",
    "应满足",
    "应符合",
    "应加盖",
    "应包含",
    "需提供",
    "需提交",
    "均须",
    "均需",
    "务必",
    "一票否决",
)

VALUE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("money", r"(?<![\d.第])\d[\d,]*(?:\.\d+)?\s*(?:万元|元)"),
    ("percent", r"(?<![\d.])\d+(?:\.\d+)?\s*%"),
    ("duration", r"(?<![\d.第])\d+\s*(?:个)?(?:日历天|自然日|天|个月|月|年|小时)(?!\s*[月日])"),
    ("count", r"(?<![\d.第])\d+\s*(?:份|台|套|人|名|册|倍)"),
    ("score", r"(?<![\d.第])\d+(?:\.\d+)?\s*分(?!值)"),
)

#: Date/time masks are removed before value extraction so that a deadline such
#: as "2026 年 7 月 28 日 09 时 00 分" does not masquerade as a project value.
_DATE_TIME_MASKS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?"),
    re.compile(r"\d{1,2}\s*月\s*\d{1,2}\s*日"),
    re.compile(r"\d{1,2}\s*[:：]\s*\d{2}"),
    re.compile(r"\d{1,2}\s*时\s*\d{1,2}\s*分?"),
)

#: Clauses that exclude a bidder from participating even though they do not use
#: the words 否决/废标/无效.  They are still fatal conditions for the bidder.
EXCLUSION_PATTERNS: tuple[str, ...] = (
    "不得存在下列情形",
    "不得存在下列",
    "存在下列情形之一",
    "不得参加本项目",
    "不得参加同一",
    "禁止其参与本项目",
    "被责令停产停业",
    "吊销许可证",
    "吊销执照",
    "失信被执行人",
    "严重违法失信",
    "政府采购严重违法",
    "经营异常名录",
    "重大税收违法",
    "处于被禁止参加",
    "取消其投标资格",
)

#: Ordered topic rules.  The first match wins inside its requirement type, and
#: the first type rule that matches decides the requirement type.
TOPIC_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # -- rejection / invalidation conditions ------------------------------
    ("REJECTION", "串通投标或弄虚作假", ("串通投标", "串标", "围标", "弄虚作假", "虚假材料", "提供虚假", "伪造")),
    ("REJECTION", "禁止性情形与失信排除", EXCLUSION_PATTERNS),
    ("REJECTION", "报价超过最高限价", ("超过最高限价", "超过招标控制价", "超过投标最高限价", "报价超过", "超出最高限价", "高于最高限价", "超过控制价")),
    ("REJECTION", "未按要求签字盖章", ("未按要求签字", "未签字", "未盖章", "未加盖", "签字盖章", "签章")),
    ("REJECTION", "联合体不符合要求", ("联合体",)),
    ("REJECTION", "违法分包转包挂靠", ("违法分包", "转包", "挂靠")),
    ("REJECTION", "投标有效期不足", ("有效期",)),
    ("REJECTION", "保证金不符合要求", ("保证金", "保函", "担保")),
    ("REJECTION", "资格条件不符合", ("资格", "资质", "许可")),
    ("REJECTION", "未实质性响应", ("实质性要求", "实质性响应", "未实质响应", "重大偏差", "负偏离", "未响应招标文件", "不响应")),
    ("REJECTION", "投标文件不完整或格式不符", ("不完整", "缺项", "未按规定格式", "格式不符", "内容不全", "未按要求编制", "不齐全")),
    ("REJECTION", "关键信息不一致或异常一致", ("机器码", "雷同", "相同ip", "ip地址", "mac地址", "cpu序列号", "硬盘序列号", "联系电话一致", "联系人一致", "关键信息不一致", "前后矛盾")),
    ("REJECTION", "解密失败或未按时递交", ("解密", "逾期上传", "逾期送达", "未按时上传", "未按时递交", "迟到", "不予受理")),
    ("REJECTION", "报价异常或选择性报价", ("低于成本", "选择性报价", "赠送", "零元", "0元", "不平衡报价", "两个报价", "多个报价", "不接受修正价格")),
    ("REJECTION", "其他否决情形", ()),
    # -- evaluation / tender determination --------------------------------
    ("EVALUATION", "定性评审与定标", ("定性评审", "评定分离", "票决", "择优", "定标委员会")),
    ("EVALUATION", "评分标准与分值构成", ("评分标准", "评标办法", "评审办法", "综合评分", "分值", "得分", "打分", "扣分", "评分因素", "评审因素", "权重", "技术标", "商务标", "价格分", "评分")),
    ("EVALUATION", "业绩评分", ("业绩得分", "业绩评分", "类似业绩", "业绩加分")),
    ("EVALUATION", "人员评分", ("人员得分", "项目负责人得分", "项目经理得分", "人员配置得分")),
    ("EVALUATION", "价格评分与基准价", ("价格分", "评标基准价", "基准价", "报价得分", "低价")),
    ("EVALUATION", "技术评分", ("技术分", "技术方案得分", "方案评分", "技术评审")),
    # -- pricing -----------------------------------------------------------
    ("PRICING", "最高限价与控制价", ("最高限价", "最高投标限价", "招标控制价", "最高控制价", "控制价", "最高报价")),
    ("PRICING", "分项限价与暂列金额", ("暂列金额", "暂估价", "暂列金", "分项限价", "分部分项", "工程量清单", "分项报价表")),
    ("PRICING", "报价组成与费用范围", ("报价", "价格", "单价", "总价", "费率", "税金", "税率", "计价", "报价表", "开标一览表", "含税", "不含税")),
    # -- bond / validity ---------------------------------------------------
    ("BOND", "保证金金额", ("保证金的金额", "保证金金额", "担保金额", "保证金数额", "保证金为", "保证金：", "保证金:", "保证金人民币", "响应保证金：")),
    ("BOND", "保证金形式", ("保证金的形式", "保证金形式", "缴纳方式", "提交形式", "银行转账", "支票", "电汇", "现金", "基本账户转出", "保函")),
    ("BOND", "保证金递交与凭证", ("保证金到账", "保证金缴纳", "提交响应保证金", "提交投标保证金", "保证金递交", "到账时间", "基本账户", "开户证明", "保证金退还", "保证金不予退还")),
    ("BOND", "投标保证金", ("保证金", "担保")),
    ("VALIDITY", "投标有效期", ("有效期",)),
    # -- signature / electronic -------------------------------------------
    ("SIGNATURE", "签字盖章要求", ("签字", "盖章", "签章", "公章", "法定代表人", "授权代表", "签署", "手签", "私章")),
    ("ELECTRONIC", "CA与电子签章", ("ca", "数字证书", "电子签章", "电子签名", "电子印章", "ukey", "u盾")),
    ("ELECTRONIC", "加密上传与解密", ("加密", "上传", "解密", "电子投标", "电子响应", "交易平台", "投标客户端", "制作工具")),
    # -- consortium / subcontract ----------------------------------------
    ("CONSORTIUM", "联合体", ("联合体",)),
    ("SUBCONTRACT", "分包与转包", ("分包", "转包", "挂靠")),
    # -- qualification ----------------------------------------------------
    ("QUALIFICATION", "营业执照与独立法人", ("营业执照", "独立法人", "独立承担民事责任", "法人资格", "事业单位")),
    ("QUALIFICATION", "资质等级与许可", ("资质", "资质等级", "许可证", "安全生产许可", "许可证书", "资质证书", "等级证书")),
    ("QUALIFICATION", "信用与失信查询", ("信用中国", "失信", "被执行人", "经营异常", "严重违法", "信用记录", "黑名单", "信用信息")),
    ("QUALIFICATION", "特定资格条件", ("特定资格", "资格条件", "资格要求", "准入", "备案", "登记")),
    ("PERSONNEL", "项目负责人资格", ("项目负责人", "项目经理", "建造师", "总监理", "技术负责人")),
    ("PERSONNEL", "安全与管理人员", ("安全员", "安全生产考核", "b证", "b类", "c证", "五大员", "施工员", "质量员", "特种作业")),
    ("PERSONNEL", "人员社保与劳动关系", ("社保", "社会保险", "养老保险", "劳动合同", "聘用", "在职")),
    ("PERSONNEL", "人员配置要求", ("人员配置", "人员要求", "人员配备", "项目班子", "团队配置", "职称", "岗位证书")),
    ("PERFORMANCE", "类似项目业绩", ("业绩", "类似项目", "同类项目", "类似工程", "合同业绩", "类似业绩", "同类业绩", "业绩证明")),
    ("FINANCIAL", "财务与审计报告", ("审计报告", "财务报表", "财务报告", "资产负债", "财务状况", "净资产")),
    ("FINANCIAL", "纳税与社保凭证", ("纳税", "税收", "完税", "社保", "社会保险", "缴纳证明", "依法缴纳")),
    ("FINANCIAL", "财务承诺函", ("财务", "垫资", "融资", "资金")),
    # -- technical --------------------------------------------------------
    ("TECHNICAL", "★条款与强制参数", ("★", "▲", "强制", "关键技术", "实质性技术")),
    ("TECHNICAL", "技术参数与配置", ("技术参数", "技术规格", "规格", "参数", "配置", "性能", "型号", "品牌")),
    ("TECHNICAL", "接口与集成", ("接口", "集成", "对接", "协议", "兼容", "数据库", "中间件", "国产化", "操作系统")),
    ("TECHNICAL", "数据迁移与上线", ("数据迁移", "迁移", "上线", "切换", "割接", "试运行")),
    ("TECHNICAL", "安装调试与验收", ("安装", "调试", "验收", "检测", "试验", "联调")),
    ("TECHNICAL", "培训与售后服务", ("培训",)),
    ("TECHNICAL", "售后服务与运维", ("售后", "运维", "响应时间", "服务网点", "备件", "质保期服务")),
    ("TECHNICAL", "技术方案与实施组织", ("技术方案", "实施", "进度", "组织", "应急", "安全措施", "质量保证")),
    # -- quality / duration / location / warranty / contract -------------
    ("QUALITY", "质量要求", ("质量要求", "质量标准", "质量目标", "合格", "优良", "工程质量", "验收标准", "供货质量")),
    ("DURATION", "工期与供货期", ("工期", "供货期", "服务期", "交货期", "交付期", "实施周期", "履约期限", "服务期限", "项目周期")),
    ("LOCATION", "交付与实施地点", ("交货地点", "供货地点", "交付地点", "实施地点", "服务地点", "项目地点", "建设地点", "项目所在地")),
    ("WARRANTY", "质保与保修", ("质保", "保修", "免费维修", "维护期", "缺陷责任期")),
    ("CONTRACT", "合同条款与付款", ("合同", "付款", "支付", "结算", "违约", "履约", "索赔", "验收", "费用承担", "赔偿责任", "争议", "仲裁", "诉讼", "终止合同", "解除合同")),
    # -- document / proof / form -----------------------------------------
    ("PROOF", "证明材料要求", ("证明材料", "证明文件", "检测报告", "复印件", "扫描件", "原件", "加盖公章", "官网截图", "彩页", "授权函", "承诺函")),
    ("FORM", "投标文件格式", ("投标文件格式", "响应文件格式", "格式要求", "格式规定", "按格式", "封面", "目录", "装订", "分册", "附表")),
    ("FORM", "投标文件组成", ("投标文件组成", "响应文件组成", "投标文件包括", "响应文件包括", "组成内容", "文件构成", "应当包括")),
    ("SUBMISSION", "递交方式与截止时间", ("递交", "提交", "送达", "递交方式", "递交地点", "截止时间", "上传", "密封", "递交介质")),
    ("PACKAGING", "封装与密封", ("密封", "正本", "副本", "封装", "u盘", "光盘", "骑缝")),
)

#: Types that always deserve a review row when a matching source clause exists,
#: even without mandatory wording (they carry concrete project values).
VALUE_TYPES: frozenset[str] = frozenset(
    {
        "PRICING",
        "BOND",
        "VALIDITY",
        "DURATION",
        "LOCATION",
        "QUALITY",
        "WARRANTY",
        "EVALUATION",
        "REJECTION",
    }
)

RISK_BY_TYPE: dict[str, str] = {
    "REJECTION": "一票否决",
    "QUALIFICATION": "高",
    "PERSONNEL": "高",
    "PERFORMANCE": "高",
    "FINANCIAL": "高",
    "CREDIT": "高",
    "CONSORTIUM": "高",
    "SUBCONTRACT": "高",
    "PRICING": "一票否决",
    "BOND": "一票否决",
    "VALIDITY": "高",
    "SIGNATURE": "一票否决",
    "ELECTRONIC": "一票否决",
    "DURATION": "高",
    "LOCATION": "高",
    "QUALITY": "高",
    "WARRANTY": "高",
    "TECHNICAL": "高",
    "EVALUATION": "中",
    "PROOF": "高",
    "FORM": "高",
    "SUBMISSION": "一票否决",
    "PACKAGING": "高",
    "CONTRACT": "中",
    "OTHER": "中",
}

_CLAUSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(A\d+(?:\.\d+)*)\b"),
    re.compile(r"第\s*(\d+(?:\.\d+)*)\s*条"),
    re.compile(r"^(\d+(?:\.\d+){1,4})\s*"),
    re.compile(r"^([一二三四五六七八九十百]{1,3}[、.．])"),
    re.compile(r"^([（(]\s*\d{1,3}\s*[）)])"),
)

_HEADING_ONLY = re.compile(
    r"^(?:第[一二三四五六七八九十百千万零〇0-9]+[章节篇部分]|[一二三四五六七八九十百千万]{1,3}[、.．)]"
    r"|\d+(?:\.\d+)*[、.．)])?[^。；;：:]{0,26}$"
)

_NAVIGATION_MARKERS = ("目录", "....", "……", "页码")

#: Page furniture and running heads are structure, not requirements.
_RUNNING_HEAD_TAILS = ("询比文件", "招标文件", "采购文件", "投标文件", "响应文件", "竞争性磋商文件")
_PAGE_FOOTER_RE = re.compile(r"^(?:第\s*\d+\s*页(?:\s*[,，]?\s*共\s*\d+\s*页)?|\d{1,3})$")

#: A pass/fail criterion row of an evaluation table states a requirement even
#: without 必须/应当 wording: the bidder must satisfy it to pass the review.
_CRITERIA_MARKERS: tuple[str, ...] = (
    "评审标准",
    "评审因素",
    "评标标准",
    "审查标准",
    "评审办法前附表",
    "资格审查标准",
    "具备有效的",
    "与营业执照一致",
    "符合第二章",
    "符合询比文件",
    "符合招标文件",
)

#: Verbs that turn a topic mention into something the bidder must do.
_INSTRUCTION_VERBS: tuple[str, ...] = (
    "提供",
    "提交",
    "加盖",
    "上传",
    "编制",
    "填写",
    "附",
    "采用",
    "递交",
    "缴纳",
    "出具",
    "承诺",
    "响应",
    "符合",
    "满足",
    "具备",
    "不得",
    "必须",
    "应当",
    "应按",
    "须",
    "查询",
    "签字",
    "盖章",
)

_TOPIC_PATTERN_INDEX: tuple[str, ...] = tuple(
    sorted(
        {pattern for _type, _topic, patterns in TOPIC_RULES for pattern in patterns},
        key=len,
        reverse=True,
    )
)


def _is_running_head(text: str) -> bool:
    stripped = compact_text(text)
    if len(stripped) > 140:
        return False
    if "。" in stripped[-24:]:
        return False
    return stripped.endswith(_RUNNING_HEAD_TAILS)


def _is_page_furniture(text: str) -> bool:
    return bool(_PAGE_FOOTER_RE.match(compact_text(text)))


def _has_criteria_marker(text: str) -> bool:
    return any(marker in text for marker in _CRITERIA_MARKERS)


def _matches_topic(text: str) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in _TOPIC_PATTERN_INDEX)


def _has_instruction_verb(text: str) -> bool:
    return any(verb in text for verb in _INSTRUCTION_VERBS)


#: Terms that must never appear in a review row unless the source itself
#: contains them.  This is the project-irrelevance lexicon.
TOPIC_LEXICON: tuple[str, ...] = (
    "数据库",
    "中间件",
    "国产化",
    "操作系统",
    "培训",
    "软件",
    "云平台",
    "虚拟化",
    "信创",
)


def compact_text(value: object) -> str:
    """Normalise whitespace without dropping source characters."""

    return re.sub(r"\s+", " ", normalize_text(value).replace("\n", " ")).strip()


#: A "…分" token is only a score when the clause actually talks about scoring;
#: otherwise "1.12 分包" would be read as the value "1.12分".
_SCORE_CONTEXT: tuple[str, ...] = (
    "得分",
    "评分",
    "分值",
    "扣分",
    "加分",
    "技术分",
    "商务分",
    "价格分",
    "评审分",
    "总分",
)


def extract_values(text: str) -> list[str]:
    masked = text
    for mask in _DATE_TIME_MASKS:
        masked = mask.sub(" ", masked)
    values: list[str] = []
    for kind, pattern in VALUE_PATTERNS:
        for match in re.finditer(pattern, masked):
            if kind == "score" and not any(marker in text for marker in _SCORE_CONTEXT):
                continue
            token = re.sub(r"\s+", "", match.group(0))
            if token not in values:
                values.append(token)
    return values


_CLAUSE_BREAK = re.compile(r"[。；;\n]")
_INLINE_CLAUSE = re.compile(
    r"(?=(?:A\d{1,2}\.\d{1,2})|(?<![\d.])\d{1,2}(?:\.\d{1,2}){1,3}\s*[\u4e00-\u9fff（(])"
)
#: Round 6: source-visible emphasis markers are format semantics, not noise.
#: The vocabulary lives in :mod:`tender_basic.source_criticality` so the review
#: side and the requirement index can never disagree about what a marker is.
_LEADING_MARKER = re.compile(rf"^\s*([{MARKER_CLASS}])\s*")
_MARKER_ONLY = re.compile(rf"^[{MARKER_CLASS}]$")
_TRAILING_MARKER = re.compile(rf"([{MARKER_CLASS}])\s*$")
#: Markers that carry the tender's own clause emphasis.  Only these may keep a
#: clause in the index that the ordinary predicate would drop: a leading list
#: bullet is not a tender-specific emphasis marker, and a trailing ``*`` is
#: usually a redaction/footnote artefact.
_RESCUE_MARKERS = ("*", "★")
_RESCUE_CLAUSE = re.compile(r"^\s*[*★]\s*(?:\d+(?:\.\d+)*|[\u4e00-\u9fff])")

#: Subjects that only bind the purchaser/evaluator.  A clause that binds them
#: and never the bidder is procedural context, not a bidder review requirement.
_PURCHASER_SUBJECTS: tuple[str, ...] = (
    "采购人",
    "招标人",
    "评审小组",
    "询比小组",
    "评标委员会",
    "评审委员会",
    "代理机构",
    "监督部门",
    "评委",
)
_BIDDER_SUBJECTS: tuple[str, ...] = (
    "供应商",
    "投标人",
    "响应人",
    "申请人",
    "承包人",
    "成交供应商",
    "中标人",
)


def split_source_clauses(text: str) -> list[str]:
    """Split one source fragment into clause-level requirement statements.

    The locator stays the fragment's exact PDF locator; only the unit of
    requirement classification becomes a clause instead of a whole block.  This
    is what keeps topics, values, and evidence from mixing across unrelated
    clauses of one large PDF block or table cell.

    Round 6: a source-visible emphasis marker (``*`` / ``★`` …) is *source
    format semantics* and must survive the split.  The clause splitter is a
    zero-width lookahead, so a marker written in front of a clause number used
    to end up in the discarded empty first piece (``*1.4.5 供货期`` became
    ``1.4.5 供货期``); a marker between two clauses used to stick to the *end*
    of the previous clause.  Both cases are repaired here, so every downstream
    step (atomization, concern grouping, review rows) still sees the marker with
    the requirement it marks.
    """

    leading_marker = ""
    marker_match = _LEADING_MARKER.match(text)
    if marker_match:
        leading_marker = marker_match.group(1)
        text = text[marker_match.end() :]
    pieces: list[str] = []
    start = 0
    for match in _CLAUSE_BREAK.finditer(text):
        piece = text[start : match.end()]
        start = match.end()
        if piece.strip():
            pieces.append(piece.strip())
    tail = text[start:].strip()
    if tail:
        pieces.append(tail)

    expanded: list[str] = []
    for piece in pieces:
        for chunk in _INLINE_CLAUSE.split(piece):
            chunk = chunk.strip()
            if chunk:
                expanded.append(chunk)

    merged: list[str] = []
    for chunk in expanded:
        if merged and len(compact_text(chunk)) < 10:
            merged[-1] = f"{merged[-1]} {chunk}"
        else:
            merged.append(chunk)
    merged = _reattach_source_markers(merged)
    if leading_marker:
        if merged:
            if not merged[0].lstrip().startswith(leading_marker):
                merged[0] = f"{leading_marker}{merged[0]}"
        else:
            merged = [leading_marker]
    return [chunk for chunk in merged if compact_text(chunk)]


def _reattach_source_markers(chunks: list[str]) -> list[str]:
    """Keep a marker with the clause it marks, never with the previous one.

    A marker emitted as its own piece (the clause splitter breaks *before* a
    marker) or left dangling at the end of a piece belongs to the requirement
    that follows it -- never to the clause before it and never dropped.
    """

    out: list[str] = []
    pending = ""
    for chunk in chunks:
        text = f"{pending} {chunk}".strip() if pending else chunk
        pending = ""
        stripped = text.strip()
        if not stripped:
            continue
        if _MARKER_ONLY.match(stripped):
            pending = stripped
            continue
        trailing = _TRAILING_MARKER.search(stripped)
        if trailing and _compact_len(stripped) > len(trailing.group(1)) + 1:
            head = stripped[: trailing.start()].rstrip()
            pending = trailing.group(1)
            if head:
                out.append(head)
            continue
        out.append(text)
    if pending:
        out.append(pending)
    return out


def _compact_len(value: str) -> int:
    return len(compact_text(value))


def _binds_only_purchaser(text: str) -> bool:
    if not any(subject in text for subject in _PURCHASER_SUBJECTS):
        return False
    return not any(subject in text for subject in _BIDDER_SUBJECTS)


@dataclass
class _AssembledFragment:
    locator: Locator
    page: int | None
    section: str
    text: str
    order: tuple[int, int, int]
    source_kind: str


_SENTENCE_TERMINATORS = "。；;！!?"
_CLAUSE_CONTINUATIONS = "：:，,、"


def _ends_sentence(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped[-1] in _SENTENCE_TERMINATORS


def _assemble_source_fragments(fragments: Iterable[object]) -> list[_AssembledFragment]:
    """Join source fragments that are one sentence split by PDF layout.

    A condition list such as "……存在下列情形之一的：" / "（1）……" / "（2）……" is
    frequently emitted as separate PDF blocks.  Splitting those fragments in
    isolation loses the sentence's governing verb, so the clause never looks
    mandatory.  Assembly is limited to adjacent blocks on the same page; table
    cells stay self-contained.
    """

    assembled: list[_AssembledFragment] = []
    for fragment in fragments:
        if _is_running_head(fragment.text) or _is_page_furniture(fragment.text):
            continue
        current = _AssembledFragment(
            locator=fragment.locator,
            page=fragment.page,
            section=fragment.section,
            text=fragment.text,
            order=fragment.order,
            source_kind=fragment.source_kind,
        )
        if assembled:
            previous = assembled[-1]
            same_kind = previous.source_kind == fragment.source_kind
            same_page = previous.page == fragment.page and fragment.page is not None
            next_page = (
                previous.page is not None
                and fragment.page is not None
                and fragment.page == previous.page + 1
                and previous.source_kind == "pdf_block"
                and fragment.source_kind == "pdf_block"
            )
            if previous.source_kind == "pdf_block":
                adjacency = abs(int(fragment.order[1]) - int(previous.order[1])) <= 25
            else:
                adjacency = (
                    int(previous.order[1]) == int(fragment.order[1])
                    and int(fragment.order[2]) - int(previous.order[2])
                    in (1, 1000, 1001)
                )
            continuable = (
                same_kind
                and (same_page or next_page)
                and adjacency
                and len(previous.text) < 600
                and (
                    not _ends_sentence(previous.text)
                    or previous.text.rstrip()[-1] in _CLAUSE_CONTINUATIONS
                )
            )
            if continuable:
                previous.text = f"{previous.text} {fragment.text}"
                previous.order = fragment.order
                previous.page = fragment.page
                previous.locator = fragment.locator
                continue
        assembled.append(current)
    return assembled


#: A clause that introduces an enumeration hands its requirement force down to
#: the items that follow it.
_GOVERNING_MARKERS = ("下列", "如下", "以下", "情形之一的", "条件之一的")


def _is_governing_clause(text: str) -> bool:
    stripped = text.rstrip()
    if stripped.endswith(("：", ":")):
        return True
    return any(marker in stripped for marker in _GOVERNING_MARKERS)



def detect_clause(text: str) -> str:
    # Round 6: a leading emphasis marker is source format, not part of the
    # clause number, so "*1.4.5 供货期 …" still detects clause 1.4.5.
    marker = _LEADING_MARKER.match(text)
    if marker:
        text = text[marker.end() :]
    for pattern in _CLAUSE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


def detect_markers(text: str) -> tuple[list[str], list[str]]:
    lowered = text.lower()
    strong = [marker for marker in STRONG_MARKERS if marker.lower() in lowered]
    mandatory = [marker for marker in MANDATORY_MARKERS if marker in text]
    return strong, mandatory


def _is_heading_like(text: str) -> bool:
    if any(marker in text for marker in _NAVIGATION_MARKERS):
        return True
    if len(text) > 60:
        return False
    if text.endswith(("。", "；", ";", "！")):
        return False
    return bool(_HEADING_ONLY.match(text))


_OTHER_BUCKETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("费用与付款", ("费用", "承担", "价款", "付款", "支付", "结算", "税", "发票")),
    ("合同责任", ("合同", "责任", "违约", "赔偿", "争议", "仲裁", "诉讼", "解除", "终止")),
    ("评审计分", ("分", "得分", "评分", "技术标", "商务标")),
    ("文件组成与格式", ("应当包括", "组成", "包括", "目录", "装订", "分册", "附表", "格式", "编制")),
    ("程序性要求", ("公告", "澄清", "修改", "撤回", "程序", "平台", "方式", "时间", "地点", "监督")),
)


def _other_topic(text: str) -> str:
    for topic, patterns in _OTHER_BUCKETS:
        if any(pattern in text for pattern in patterns):
            return topic
    return "其他要求"


def _topic_for(requirement_type: str, text: str) -> str:
    lowered = text.lower()
    for rule_type, topic, patterns in TOPIC_RULES:
        if rule_type != requirement_type:
            continue
        for pattern in patterns:
            if pattern.lower() in lowered:
                return topic
    if requirement_type == "REJECTION":
        return "其他否决情形"
    if requirement_type == "OTHER":
        return _other_topic(text)
    return "一般要求"


def topic_patterns(topic: str) -> tuple[str, ...]:
    for _type, name, patterns in TOPIC_RULES:
        if name == topic:
            return patterns
    return ()


def _type_for(text: str, strong: list[str], mandatory: list[str], values: list[str]) -> str:
    lowered = text.lower()
    if strong:
        return "REJECTION"
    for pattern in EXCLUSION_PATTERNS:
        if pattern in text:
            return "REJECTION"
    for rule_type, _topic, patterns in TOPIC_RULES:
        if rule_type == "REJECTION":
            continue
        for pattern in patterns:
            if pattern.lower() in lowered:
                return rule_type
    if values and mandatory:
        return "OTHER"
    return "OTHER"


class SourceRequirementUnit(ContractModel):
    """One source clause / cell that states something the bid must satisfy."""

    requirement_id: str = Field(pattern=r"^SR\d{4}$")
    requirement_type: str
    topic: str
    risk_level: str
    module: str
    mandatory: bool = False
    high_risk: bool = False
    markers: list[str] = Field(default_factory=list)
    clause: str = ""
    page: int | None = None
    section: str = ""
    text: str
    evidence_text: str
    locator: Locator
    source_kind: str = "pdf_block"
    order: list[int] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    merged_ids: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class RequirementIndex:
    units: tuple[SourceRequirementUnit, ...]
    scanned_fragments: int
    dropped_navigation: int
    dropped_heading: int
    dropped_short: int
    merged_duplicates: int
    dropped_procedural: int = 0

    @property
    def high_risk_units(self) -> tuple[SourceRequirementUnit, ...]:
        return tuple(unit for unit in self.units if unit.high_risk)

    def by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for unit in self.units:
            counts[unit.requirement_type] = counts.get(unit.requirement_type, 0) + 1
        return counts


def _dedupe(units: list[SourceRequirementUnit]) -> tuple[list[SourceRequirementUnit], int]:
    """Collapse repeated clauses while keeping the earlier locator authoritative."""

    seen: dict[tuple[str, str], SourceRequirementUnit] = {}
    order: list[SourceRequirementUnit] = []
    merged = 0
    for unit in units:
        key = (unit.requirement_type, re.sub(r"\s+", "", unit.text))
        if key in seen:
            owner = seen[key]
            owner.merged_ids.append(unit.requirement_id)
            merged += 1
            continue
        seen[key] = unit
        order.append(unit)
    return order, merged


def build_requirement_index(document: NormalizedDocument) -> RequirementIndex:
    """Scan the real source document and index its reviewable requirements."""

    units: list[SourceRequirementUnit] = []
    rescued: list[tuple[Any, str, int]] = []
    indexed_clauses: set[str] = set()
    scanned = 0
    dropped_navigation = 0
    dropped_heading = 0
    dropped_short = 0
    dropped_procedural = 0
    counter = 0
    for fragment in _assemble_source_fragments(iter_source_fragments(document)):
        scanned += 1
        block = compact_text(fragment.text)
        if not block:
            dropped_short += 1
            continue
        if any(marker in block for marker in _NAVIGATION_MARKERS):
            dropped_navigation += 1
            continue
        _governing_clause = ""
        for sentence_index, clause_text in enumerate(split_source_clauses(fragment.text)):
            text = compact_text(clause_text)
            if not text:
                continue
            if any(marker in text for marker in _NAVIGATION_MARKERS):
                dropped_navigation += 1
                continue
            strong, mandatory = detect_markers(text)
            values = extract_values(text)
            criteria = _has_criteria_marker(text)
            governing = _governing_clause
            if governing and not strong and not mandatory and not values:
                text = f"{governing} {text}"
                strong, mandatory = detect_markers(text)
                values = extract_values(text)
                criteria = criteria or _has_criteria_marker(text)
            if _is_governing_clause(compact_text(clause_text)):
                _governing_clause = compact_text(clause_text)[:160]
            elif strong and _ends_sentence(compact_text(clause_text)):
                _governing_clause = ""
            if criteria:
                mandatory = [*mandatory, "评审标准"]
            # Round 6: a clause the *source* marks with an emphasis marker is a
            # requirement the tender itself singled out.  Keeping it as a unit is
            # not a rejection claim and not a substantive claim -- dropping it is
            # what used to make the marker disappear before criticality was even
            # considered.
            source_marked = bool(_RESCUE_CLAUSE.match(clause_text))
            if source_marked and not (
                strong
                or mandatory
                or values
                or (_matches_topic(text) and _has_instruction_verb(text))
            ):
                # Kept for review, but appended *after* the ordinary units so no
                # existing requirement id (and therefore no existing review row)
                # changes: round-5 row identities stay stable.  A clause that is
                # already indexed is not rescued again, so a marked table row
                # cannot duplicate the requirement it restates.
                if len(text) >= 6:
                    rescued.append((fragment, text, sentence_index))
                continue
            if not (
                strong
                or mandatory
                or values
                or (_matches_topic(text) and _has_instruction_verb(text))
            ):
                dropped_heading += 1
                continue
            if len(text) < 6:
                dropped_short += 1
                continue
            if (
                not strong
                and not values
                and not criteria
                and _is_heading_like(text)
            ):
                dropped_heading += 1
                continue
            requirement_type = _type_for(text, strong, mandatory, values)
            if (
                requirement_type == "OTHER"
                and not strong
                and not criteria
                and _binds_only_purchaser(text)
            ):
                dropped_procedural += 1
                continue
            counter += 1
            topic = _topic_for(requirement_type, text)
            evidence = text if len(text) <= 400 else text[:397].rstrip() + "..."
            units.append(
                SourceRequirementUnit(
                    requirement_id=f"SR{counter:04d}",
                    requirement_type=requirement_type,
                    topic=topic,
                    risk_level=RISK_BY_TYPE.get(requirement_type, "中"),
                    module=TYPE_MODULE.get(requirement_type, MODULE_DOCUMENT),
                    mandatory=bool(mandatory),
                    high_risk=bool(strong),
                    markers=[*strong, *mandatory][:12],
                    clause=detect_clause(text),
                    page=fragment.page,
                    section=compact_text(fragment.section)[:80],
                    text=text if len(text) <= 600 else text[:597].rstrip() + "...",
                    evidence_text=evidence,
                    locator=fragment.locator,
                    source_kind=fragment.source_kind,
                    order=[*fragment.order, sentence_index],
                    values=values[:12],
                )
            )
            clause_id = detect_clause(text)
            if clause_id:
                indexed_clauses.add(clause_id)
    # source-marked clauses that the ordinary predicate would drop are appended
    # after the ordinary units (see `rescued` above).  A clause that the index
    # already carries is not appended again, so a marked table row cannot
    # duplicate the requirement it restates.
    rescued = [
        candidate
        for candidate in rescued
        if not (detect_clause(candidate[1]) and detect_clause(candidate[1]) in indexed_clauses)
    ]
    for fragment, text, sentence_index in rescued:
        counter += 1
        strong, mandatory = detect_markers(text)
        values = extract_values(text)
        criteria = _has_criteria_marker(text)
        requirement_type = _type_for(text, strong, mandatory, values)
        topic = _topic_for(requirement_type, text)
        evidence = text if len(text) <= 400 else text[:397].rstrip() + "..."
        units.append(
            SourceRequirementUnit(
                requirement_id=f"SR{counter:04d}",
                requirement_type=requirement_type,
                topic=topic,
                risk_level=RISK_BY_TYPE.get(requirement_type, "中"),
                module=TYPE_MODULE.get(requirement_type, MODULE_DOCUMENT),
                mandatory=bool(mandatory),
                high_risk=bool(strong),
                markers=[*strong, *mandatory][:12],
                clause=detect_clause(text),
                page=fragment.page,
                section=compact_text(fragment.section)[:80],
                text=text if len(text) <= 600 else text[:597].rstrip() + "...",
                evidence_text=evidence,
                locator=fragment.locator,
                source_kind=fragment.source_kind,
                order=[*fragment.order, sentence_index],
                values=values[:12],
            )
        )
    deduped, merged = _dedupe(units)
    return RequirementIndex(
        units=tuple(deduped),
        scanned_fragments=scanned,
        dropped_navigation=dropped_navigation,
        dropped_heading=dropped_heading,
        dropped_short=dropped_short,
        dropped_procedural=dropped_procedural,
        merged_duplicates=merged,
    )


def source_contains(document: NormalizedDocument, term: str) -> bool:
    """Evidence check used by the project-irrelevance QA."""

    lowered = term.lower()
    for fragment in iter_source_fragments(document):
        if lowered in compact_text(fragment.text).lower():
            return True
    return False


__all__ = [
    "MANDATORY_MARKERS",
    "MODULE_COMMERCIAL",
    "MODULE_DOCUMENT",
    "MODULE_EVALUATION",
    "MODULE_EVALUATION_QUALITATIVE",
    "MODULE_ORDER",
    "MODULE_QUALIFICATION",
    "MODULE_REJECTION",
    "MODULE_SIGNATURE",
    "MODULE_SUBMISSION",
    "MODULE_TECHNICAL",
    "RequirementIndex",
    "RequirementType",
    "RISK_BY_TYPE",
    "STRONG_MARKERS",
    "SourceRequirementUnit",
    "TOPIC_LEXICON",
    "TOPIC_RULES",
    "TYPE_MODULE",
    "VALUE_TYPES",
    "build_requirement_index",
    "compact_text",
    "detect_clause",
    "detect_markers",
    "extract_values",
    "source_contains",
    "split_source_clauses",
]
