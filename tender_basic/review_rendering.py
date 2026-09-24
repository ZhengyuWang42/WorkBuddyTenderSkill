"""Round 4: rendered-component provenance.

Round 3 gave every *semantic object* a concern owner (``SourceRequirementAtom``
-> ``ReviewConcern`` -> ``ReviewPoint``).  That was necessary but not sufficient:
the final rendered Excel cell could still carry text produced by a stale/broad
group field or by an old topic/template path, because nothing checked the text
that actually reaches the workbook.

This module closes that gap.  Every material phrase that is rendered into the
workbook is represented as a :class:`RenderedReviewComponent` that records the
concern-owned inputs it came from (atoms, numbers, materials, evidence, linked
facts) and the rule that generated it.  ``verify_component`` then decides whether
the *rendered text* is fully owned by the concern; :func:`provenance_map` turns a
row's components into the per-cell map persisted as round-4 evidence.

The invariant is deliberately stated as an equality of two sets:

    terms(rendered_text) - meta_language  <=  terms(owned_inputs)

so a phrase the concern's own source never established is a mismatch, no matter
which upstream field happened to carry it.  No case id, page number or corpus
literal is used: the lexicon is domain vocabulary and the backing is whatever the
concern owns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "v1_rendered_review_component/1"

# --------------------------------------------------------------------------- #
# component kinds
# --------------------------------------------------------------------------- #

SOURCE_REQUIREMENT = "SOURCE_REQUIREMENT"
REVIEW_CHECK = "REVIEW_CHECK"
PASS_CRITERION = "PASS_CRITERION"
PREPARATION_MATERIAL = "PREPARATION_MATERIAL"
FAILURE_CONSEQUENCE = "FAILURE_CONSEQUENCE"
SCORING_GUIDANCE = "SCORING_GUIDANCE"
NUMERIC_STATEMENT = "NUMERIC_STATEMENT"
EVIDENCE_SUMMARY = "EVIDENCE_SUMMARY"
LINKED_FACT = "LINKED_FACT"
#: Round 6: the source-visible criticality note.  It is *not* source wording --
#: it is rendered from the source marker and the document's own substantive /
#: consequence clauses, so it is verified against those atoms rather than
#: against the concern's own requirement text.
CRITICALITY_NOTE = "CRITICALITY_NOTE"

COMPONENT_KINDS: tuple[str, ...] = (
    SOURCE_REQUIREMENT,
    REVIEW_CHECK,
    PASS_CRITERION,
    PREPARATION_MATERIAL,
    FAILURE_CONSEQUENCE,
    SCORING_GUIDANCE,
    NUMERIC_STATEMENT,
    EVIDENCE_SUMMARY,
    LINKED_FACT,
    CRITICALITY_NOTE,
)

#: Component kinds whose rendered text is prose and therefore term-guarded.
PROSE_KINDS: tuple[str, ...] = (
    SOURCE_REQUIREMENT,
    REVIEW_CHECK,
    PASS_CRITERION,
    FAILURE_CONSEQUENCE,
    SCORING_GUIDANCE,
    EVIDENCE_SUMMARY,
    NUMERIC_STATEMENT,
)

# --------------------------------------------------------------------------- #
# vocabulary
# --------------------------------------------------------------------------- #

#: Meta language: words a reviewer instruction may use without the source
#: having to establish them.  They describe the *review act*, not a tender
#: requirement, so they are subtracted before the ownership comparison.
META_TERMS: tuple[str, ...] = (
    "核对",
    "核验",
    "确认",
    "比对",
    "逐条",
    "逐项",
    "逐页",
    "逐处",
    "依据",
    "对照",
    "响应文件",
    "投标文件",
    "招标文件",
    "询比文件",
    "采购文件",
    "供应商",
    "投标人",
    "响应人",
    "采购人",
    "评审小组",
    "评审委员会",
    "对应",
    "一致",
    "齐全",
    "完整",
    "清晰",
    "有效",
    "有效期内",
    "内容",
    "条款",
    "要求",
    "位置",
    "章节",
    "页码位置",
    "证明材料位置",
    "对应章节",
    "备查",
    "记录",
    "留存",
    "附",
    "提供",
    "提交",
    "载明",
    "满足",
    "符合",
    "不触发",
    "不存在",
    "无缺项",
    "无遗漏",
    "无重复",
    "无负偏离",
    "有依据",
    "可核验",
    "说明",
    "签章",
    "签字",
    "盖章",
    "落款",
    "日期",
    "名称",
    "金额",
    "数量",
    "期限",
    "范围",
    "形式",
    "方式",
    "地点",
    "时间",
    "条件",
    "标准",
    "口径",
    "材料",
    "资料",
    "原件",
    "复印件",
    "扫描件",
    "电子版",
    "正本",
    "副本",
    "分项",
    "合计",
    "总价",
    "单价",
    "报价表",
    "一览表",
    "偏差表",
    "封面",
    "正文",
    "附件",
    "格式",
    # review-cell block labels (review meta language, never source content)
    "招标文件要求",
    "复核要点",
    "通过标准",
    "不满足后果",
    "准备材料",
    "评分提示",
    "数值指标",
    "关联事实",
    "证据摘要",
    # round-6 criticality note (rendered from the source marker + the document's
    # own substantive/consequence clauses, so it is a review label, not a claim)
    "源标记",
    "实质性要求",
    "不满足可能导致否决",
)

#: Domain vocabulary.  A rendered phrase may name one of these concepts only
#: when the concern's own source owns the concept.  This is what stops a row
#: from inheriting 资质证书/专业类别/等级, 装订/目录/页码, 控股管理关系,
#: 履约保证金, 推荐成交候选人, 否决所有响应 and similar foreign content.
DOMAIN_TERMS: tuple[str, ...] = (
    # qualification / credit
    "营业执照",
    "统一社会信用代码",
    "经营范围",
    "独立法人",
    "独立承担民事责任",
    "资质证书",
    "资质等级",
    "专业类别",
    "等级",
    "许可证书",
    "许可证",
    "信用中国",
    "失信被执行人",
    "严重违法失信",
    "重大税收违法",
    "信用记录",
    "行贿",
    "不良履约记录",
    "重大违法记录",
    "单位负责人",
    "控股",
    "管理关系",
    "关联关系",
    "联合体",
    "分包",
    "转包",
    "业绩",
    "类似项目",
    "审计报告",
    "财务报表",
    "财务能力",
    "社保",
    "社会保险",
    "纳税",
    "完税",
    "建造师",
    "注册证书",
    "职称",
    "项目负责人",
    # bond / fee
    "投标保证金",
    "响应保证金",
    "履约保证金",
    "保证金",
    "保函",
    "银行转账",
    "基本账户",
    "账户",
    "凭证",
    "到账",
    "代理服务费",
    "招标代理服务费",
    "平台服务费",
    "标书费",
    "工本费",
    # price
    "最高限价",
    "控制价",
    "预算",
    "分项限价",
    "暂列金额",
    "暂估价",
    "税率",
    "税金",
    "含税",
    "不含税",
    "人民币",
    "大写",
    "小写",
    # signature / electronic
    "CA",
    "电子签章",
    "电子印章",
    "数字证书",
    "加密",
    "解密",
    "上传",
    "制作工具",
    "机器码",
    # procedure / format
    "装订",
    "目录",
    "页码",
    "编排",
    "密封",
    "封装",
    "份数",
    "异议函",
    "质疑",
    "投诉",
    "澄清",
    "修改",
    "延长",
    "推荐成交候选人",
    "成交候选人",
    "否决所有响应",
    "评审小组成员",
    "专家",
    "抽取",
    "监督",
    "资金来源",
    "项目名称",
    "项目编号",
    "标段",
    # delivery / quality / warranty
    "工期",
    "供货期",
    "交付",
    "实施地点",
    "交货地点",
    "质保金",
    "质量保证金",
    "尾款",
    "余款",
    "质保期",
    "保修",
    "质量目标",
    "验收",
    "安装",
    "调试",
    "检测",
    "培训",
    "售后服务",
    "响应时间",
    "备件",
    "供货方案",
    "应急保障",
    "质量保证体系",
    "垫资",
    "银行承兑",
    "技术参数",
    "负偏离",
    "检测报告",
    "材料清单",
    "合同协议书",
    "业绩合同",
    "评分",
    "分值",
    "得分",
    "基准价",
    "价格分",
    "报价得分",
)

#: Terms that must never appear in a retention/contract-payment row as a
#: warranty claim (round-4 fixtures Q/R).
RETENTION_WARRANTY_PHRASES: tuple[str, ...] = (
    "质保期不低于12个月",
    "质保期不低于 12个月",
    "质保期不低于12 个月",
    "项目质保期不低于12个月",
    "项目质保期不低于 12个月",
    "质保期 12个月",
    "质保期12个月",
)

#: Forbidden framings for the retention ratio (round-4 fixture R).
RETENTION_RATIO_FORBIDDEN: tuple[str, ...] = (
    "付款/计分比例为 5%",
    "付款/计分比例为5%",
    "付款比例为 5%",
    "计分比例为 5%",
    "计分比例为5%",
)

_NUMERIC_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:"
    r"个工作日|个日历天|工作日|日历天|自然日|个月|小时|分钟|万元|%|％|元|分|个|台|人|名|月|年|日|天|周|套|件|批|辆|次|项|份"
    r")"
)
_BARE_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalize(text: object) -> str:
    """Whitespace- and punctuation-insensitive comparison form."""

    return re.sub(r"[\s\u3000]+", "", str(text or ""))


def numeric_tokens(text: object) -> set[str]:
    """Numeric tokens *with a unit*, normalised for comparison.

    A bare number in a review instruction is a page/clause reference
    ("依据第5页第2.1条"), not a source value, so it is not treated as a
    numeric claim.
    """

    return {normalize(match.group(0)) for match in _NUMERIC_RE.finditer(str(text or ""))}


def bare_numbers(text: object) -> set[str]:
    return {normalize(match.group(0)) for match in _BARE_NUMBER_RE.finditer(str(text or ""))}


def domain_terms(text: object) -> set[str]:
    """Domain concepts named by ``text``."""

    haystack = normalize(text)
    return {term for term in DOMAIN_TERMS if normalize(term) in haystack}


def content_terms(text: object) -> set[str]:
    """Domain concepts that are *not* review meta language."""

    return {term for term in domain_terms(text) if term not in META_TERMS}


def foreign_terms(rendered_text: object, backing_text: object) -> list[str]:
    """Concepts named in the rendered text but absent from its owned backing."""

    backing = normalize(backing_text)
    return sorted(term for term in content_terms(rendered_text) if normalize(term) not in backing)


# --------------------------------------------------------------------------- #
# component model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RenderedReviewComponent:
    """One material phrase rendered into the workbook, with its provenance."""

    component_id: str
    review_point_id: str
    concern_id: str
    component_kind: str
    rendered_text: str
    source_atom_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    linked_fact_keys: tuple[str, ...] = ()
    numeric_evidence_ids: tuple[str, ...] = ()
    generation_rule: str = ""
    ownership_verified: bool = False
    foreign_terms: tuple[str, ...] = ()
    cell_address: str = ""
    block: str = ""
    item_index: int = 0
    sentence_index: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "review_point_id": self.review_point_id,
            "concern_id": self.concern_id,
            "component_kind": self.component_kind,
            "rendered_text": self.rendered_text,
            "source_atom_ids": list(self.source_atom_ids),
            "evidence_ids": list(self.evidence_ids),
            "linked_fact_keys": list(self.linked_fact_keys),
            "numeric_evidence_ids": list(self.numeric_evidence_ids),
            "generation_rule": self.generation_rule,
            "ownership_verified": self.ownership_verified,
            "foreign_terms": list(self.foreign_terms),
            "cell_address": self.cell_address,
            "block": self.block,
            "item_index": self.item_index,
            "sentence_index": self.sentence_index,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RenderedReviewComponent":
        return cls(
            component_id=str(payload.get("component_id", "")),
            review_point_id=str(payload.get("review_point_id", "")),
            concern_id=str(payload.get("concern_id", "")),
            component_kind=str(payload.get("component_kind", "")),
            rendered_text=str(payload.get("rendered_text", "")),
            source_atom_ids=tuple(payload.get("source_atom_ids", ()) or ()),
            evidence_ids=tuple(payload.get("evidence_ids", ()) or ()),
            linked_fact_keys=tuple(payload.get("linked_fact_keys", ()) or ()),
            numeric_evidence_ids=tuple(payload.get("numeric_evidence_ids", ()) or ()),
            generation_rule=str(payload.get("generation_rule", "")),
            ownership_verified=bool(payload.get("ownership_verified", False)),
            foreign_terms=tuple(payload.get("foreign_terms", ()) or ()),
            cell_address=str(payload.get("cell_address", "")),
            block=str(payload.get("block", "")),
            item_index=int(payload.get("item_index", 0) or 0),
            sentence_index=int(payload.get("sentence_index", 0) or 0),
        )


@dataclass
class ComponentOwnership:
    """The concern-owned inputs a rendered phrase is allowed to come from."""

    concern_id: str
    atom_ids: tuple[str, ...] = ()
    atom_text: str = ""
    #: Text of the clauses this concern owns.  An atom is a *facet* of its
    #: clause; the clause itself is concern-owned, so its text may back a
    #: rendered phrase (a derived atom keeps the clause as its origin).
    clause_text: str = ""
    numeric_values: tuple[str, ...] = ()
    materials: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    allowed_fact_keys: frozenset[str] = frozenset()
    fact_values: Mapping[str, str] = field(default_factory=dict)
    concession_text: str = ""

    @property
    def backing_text(self) -> str:
        parts = [self.atom_text, self.clause_text, self.concession_text, " ".join(self.materials)]
        parts.extend(self.fact_values.values())
        return " ".join(part for part in parts if part)


def verify_component(component: RenderedReviewComponent, ownership: ComponentOwnership) -> RenderedReviewComponent:
    """Return the component with ``ownership_verified``/``foreign_terms`` set.

    Ownership is decided per kind, so an unverifiable phrase is reported rather
    than silently rendered:

    * prose kinds must not name a domain concept the concern's own atoms (or its
      owned facts) never mention;
    * numbers must be owned values of the concern;
    * materials must be owned materials;
    * a linked fact must be a fact the concern is allowed to link.
    """

    kind = component.component_kind
    foreign: list[str] = []
    if kind == CRITICALITY_NOTE:
        # the note is produced from source atoms (the marker row, the governing
        # substantive clause, the consequence clause); it may not be rendered
        # without that basis, and it may only use the criticality vocabulary.
        missing = [] if component.source_atom_ids else ["criticality_basis_atom_ids"]
        foreign = missing
        ok = not missing
    elif kind == LINKED_FACT:
        foreign = [key for key in component.linked_fact_keys if key not in ownership.allowed_fact_keys]
        ok = not foreign
    elif kind == PREPARATION_MATERIAL:
        # A rendered material must be one the concern owns (equal up to
        # whitespace, or an owned material named inside the rendered phrase);
        # an extracted head noun ("凭证") is not a mismatch by itself.
        owned = [normalize(material) for material in ownership.materials]
        rendered_flat = normalize(component.rendered_text)
        missing = [
            material
            for material in ownership_terms(component.rendered_text)
            if not any(normalize(material) in item or item in rendered_flat for item in owned)
        ]
        foreign = missing
        ok = not missing
    elif kind == NUMERIC_STATEMENT:
        owned_values = {normalize(value) for value in ownership.numeric_values}
        tokens = numeric_tokens(component.rendered_text)
        missing = sorted(token for token in tokens if token not in owned_values)
        foreign = missing
        ok = not missing
    else:
        foreign = foreign_terms(component.rendered_text, ownership.backing_text)
        ok = not foreign
        if ok and kind in (REVIEW_CHECK, PASS_CRITERION):
            owned_values = {normalize(value) for value in ownership.numeric_values}
            extra = sorted(token for token in numeric_tokens(component.rendered_text) if token not in owned_values)
            if extra:
                foreign = extra
                ok = False

    return RenderedReviewComponent(
        component_id=component.component_id,
        review_point_id=component.review_point_id,
        concern_id=component.concern_id,
        component_kind=component.component_kind,
        rendered_text=component.rendered_text,
        source_atom_ids=component.source_atom_ids,
        evidence_ids=component.evidence_ids,
        linked_fact_keys=component.linked_fact_keys,
        numeric_evidence_ids=component.numeric_evidence_ids,
        generation_rule=component.generation_rule,
        ownership_verified=ok,
        foreign_terms=tuple(foreign),
        cell_address=component.cell_address,
        block=component.block,
        item_index=component.item_index,
        sentence_index=component.sentence_index,
    )


def ownership_terms(text: object) -> list[str]:
    """Material names a rendered phrase claims (best-effort, generic)."""

    haystack = normalize(text)
    return [term for term in DOMAIN_TERMS if normalize(term) in haystack and term.endswith(("证书", "报告", "证明", "凭证", "执照", "清单", "承诺", "函", "复印件", "扫描件", "件"))]


def components_of(item: Any) -> list[RenderedReviewComponent]:
    return list(getattr(item, "components", ()) or ())


def component_mismatches(
    components: Iterable[RenderedReviewComponent],
) -> dict[str, list[dict[str, str]]]:
    """Mismatch buckets keyed by component kind (all must be empty)."""

    buckets: dict[str, list[dict[str, str]]] = {kind: [] for kind in COMPONENT_KINDS}
    for component in components:
        if component.ownership_verified:
            continue
        buckets.setdefault(component.component_kind, []).append(
            {
                "component_id": component.component_id,
                "review_point_id": component.review_point_id,
                "concern_id": component.concern_id,
                "rendered_text": component.rendered_text[:160],
                "foreign_terms": ",".join(component.foreign_terms),
            }
        )
    return buckets


def mismatch_counts(components: Iterable[RenderedReviewComponent]) -> dict[str, int]:
    buckets = component_mismatches(components)
    counts = {f"rendered_{kind.lower()}_concern_mismatch": len(rows) for kind, rows in buckets.items()}
    counts["rendered_component_concern_mismatch_total"] = sum(counts.values())
    return counts


def provenance_map(
    components: Sequence[RenderedReviewComponent],
    *,
    cell_addresses: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Per-cell provenance rows for the round-4 evidence report."""

    addresses = dict(cell_addresses or {})
    rows: list[dict[str, Any]] = []
    for component in components:
        rows.append(
            {
                "cell": addresses.get(component.component_kind, component.cell_address),
                "block": component.block or component.component_kind,
                "sentence_index": component.sentence_index,
                "item_index": component.item_index,
                "review_point_id": component.review_point_id,
                "concern_id": component.concern_id,
                "component_kind": component.component_kind,
                "rendered_text": component.rendered_text,
                "source_atom_ids": list(component.source_atom_ids),
                "numeric_evidence_ids": list(component.numeric_evidence_ids),
                "material_ids": [component.component_id] if component.component_kind == PREPARATION_MATERIAL else [],
                "evidence_ids": list(component.evidence_ids),
                "linked_fact_keys": list(component.linked_fact_keys),
                "generation_rule": component.generation_rule,
                "ownership_verified": component.ownership_verified,
                "foreign_terms": list(component.foreign_terms),
            }
        )
    return rows


__all__ = [
    "COMPONENT_KINDS",
    "ComponentOwnership",
    "CRITICALITY_NOTE",
    "DOMAIN_TERMS",
    "FAILURE_CONSEQUENCE",
    "EVIDENCE_SUMMARY",
    "LINKED_FACT",
    "META_TERMS",
    "NUMERIC_STATEMENT",
    "PASS_CRITERION",
    "PREPARATION_MATERIAL",
    "RenderedReviewComponent",
    "REVIEW_CHECK",
    "RETENTION_RATIO_FORBIDDEN",
    "RETENTION_WARRANTY_PHRASES",
    "SCHEMA",
    "SCORING_GUIDANCE",
    "SOURCE_REQUIREMENT",
    "component_mismatches",
    "components_of",
    "content_terms",
    "domain_terms",
    "foreign_terms",
    "mismatch_counts",
    "normalize",
    "numeric_tokens",
    "provenance_map",
    "verify_component",
]
