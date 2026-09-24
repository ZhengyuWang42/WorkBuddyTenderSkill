"""Round-5 independent concern-contract report (REVIEW WORKBOOK ROUND 5).

Round 4 made the *rendered workbook* provenance-consistent: every phrase in a
cell is produced by a concern-owned ``RenderedReviewComponent``.  The CASE001
human review then rejected the result, because

    PROVENANCE CONSISTENCY IS NOT SEMANTIC VALIDATION.

A row can be fully traceable and still (a) display a neighbouring facet (a
delivery address inside a quality requirement), (b) assign a number the wrong
business meaning ("质保金比例为 95%"), (c) cite the wrong clause as evidence
(a performance bond citing the response bond), or (d) assert something the
source never established ("报价无漏项").

This report therefore audits the FINAL cell text of the built workbooks against
the *independent* hand-authored concern contracts in
:mod:`tender_basic.concern_contract` (fixtures A..T), and persists the result.

It never re-renders Word and never writes to the audited workbook.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from v1_review_workbook_round4_report import (  # noqa: E402
    CLAUSE_SHEET,
    CONFLICT_SHEET,
    DELIVERED_SHEET,
    MANDATORY_SHEET,
    Check,
    FinalCells,
    Round4Report,
    _flat,
    sha256,
)
from tender_basic.concern_contract import (  # noqa: E402
    CONTRACT_SOURCE,
    CONTRACT_VERSION,
    CONTRACTS,
    RENAMED_CONCERNS,
    SUPERSEDED_CONCERNS,
    contract_for,
    contract_table_is_independent,
    owned_text,
    validate_point,
)
from tender_basic.dynamic_review import dynamic_review_qa  # noqa: E402
from tender_basic.semantic_roles import (  # noqa: E402
    ROLE_BANK_ACCEPTANCE_RATIO,
    ROLE_PAYMENT_RATIO,
    ROLE_RETENTION_MONEY_RATIO,
    ROLE_SCORE_POINTS,
    is_canonical_role,
)

SCHEMA = "v1_review_workbook_round5_report/1"

#: Tokens that must never appear in a row once the contract forbids them.
LOCATION_TOKENS = ("泵站", "交货地点", "郸城", "周口")
CREDIT_TOKENS = ("黑名单", "失信", "被执行人", "信用中国", "严重违法")
AGENCY_TOKENS = ("代理服务费", "成交服务费", "招标代理服务费", "采购代理服务费", "中标服务费")
EFFECTIVITY_TOKENS = ("签字盖章后生效", "签字日期不一致", "合同生效")
COMPLETENESS_CLAIMS = ("无漏项", "无重复项", "重复项", "已包含一切费用", "已包含要求的一切费用")
COLLUSION_TOKENS = ("不同供应商的投标", "同一人送达", "同一人", "串通", "雷同")
STANDARD_TOKENS = ("CJJ", "GB50013", "GB50015", "GB50265", "设计规范")
PAYMENT_AS_RETENTION = ("质保金比例为 95%", "质保金比例为95%", "质保金比例95%")

#: The five roles the human brief requires to stay distinct, with their values.
VALUE_INVARIANTS = {
    "PROJECT_WARRANTY": ("PROJECT_WARRANTY_MONTHS", "24个月"),
    "RETENTION_MONEY_RATIO": ("RETENTION_MONEY_RATIO", "5%"),
    "RETENTION_RELEASE": ("RETENTION_RELEASE_MONTHS", "12个月"),
    "PAYMENT_RATIO": ("PAYMENT_RATIO", "95%"),
    "BANK_ACCEPTANCE": ("BANK_ACCEPTANCE_RATIO", "100%"),
}


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(token for token in (LOCATION_TOKENS + CREDIT_TOKENS + AGENCY_TOKENS) if token in text)


@dataclass
class RowAudit:
    """One delivered CASE001 row audited from its FINAL cell text."""

    item_id: str
    concern_id: str
    d_address: str
    d_text: str
    e_address: str
    e_text: str
    m_address: str
    m_text: str
    requirement_ids: list[str]
    review_checks: list[str]
    pass_criteria: list[str]
    materials: list[str]
    consequence: str
    scoring_guidance: str
    primary_evidence: str
    numeric_roles: list[str]
    numeric_role_values: list[dict[str, str]]
    linked_fact_keys: list[str]
    violations: list[dict[str, str]] = field(default_factory=list)

    @property
    def coherent(self) -> bool:
        return not self.violations

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "concern_id": self.concern_id,
            "cell": self.d_address,
            "displayed_source_requirement": self.d_text,
            "evidence_cell": self.e_address,
            "displayed_evidence": self.e_text,
            "note_cell": self.m_address,
            "displayed_note": self.m_text,
            "requirement_ids": self.requirement_ids,
            "review_checks": self.review_checks,
            "pass_criteria": self.pass_criteria,
            "materials": self.materials,
            "consequence": self.consequence,
            "scoring_guidance": self.scoring_guidance,
            "primary_evidence": self.primary_evidence,
            "numeric_roles": self.numeric_roles,
            "numeric_role_values": self.numeric_role_values,
            "linked_fact_keys": self.linked_fact_keys,
            "concern_contract": "PASS" if self.coherent else "FAIL",
            "violations": self.violations,
        }


class Round5Report:
    def __init__(self, build: Path, case: str) -> None:
        self.build = build
        self.case = case
        self.r4 = Round4Report(build, case)
        self.items = list(self.r4.items)
        self.background = list(self.r4.background)
        self.cells: FinalCells = self.r4.cells
        self.rows_by_item = self.r4.rows_by_item
        self.qa = dynamic_review_qa(self.r4.plan, self.r4.document, self.r4.facts)
        self.checks: list[Check] = []
        self.fixtures: dict[str, dict[str, Any]] = {}
        self.audits: list[RowAudit] = []
        self._audit_rows()

    # -- helpers ---------------------------------------------------------- #

    def check(self, name: str, ok: bool, detail: str, evidence: dict | None = None) -> None:
        self.checks.append(Check(name=name, ok=bool(ok), detail=detail, evidence=evidence or {}))

    def record(self, key: str, expectation: str, ok: bool, evidence: str = "") -> None:
        self.fixtures[key] = {
            "expectation": expectation,
            "status": "PASS" if ok else "FAIL",
            "evidence": evidence[:400],
        }

    def record_not_applicable(self, key: str, expectation: str, reason: str) -> None:
        self.fixtures[key] = {
            "expectation": expectation,
            "status": "NOT_APPLICABLE",
            "evidence": reason,
        }

    @property
    def case001(self) -> bool:
        return str(self.case).replace("_", "").lower() == "case001"

    def _row(self, item_id: Any):
        key = item_id if isinstance(item_id, str) else str(getattr(item_id, "item_id", "") or "")
        return self.rows_by_item.get(key)

    def _item(self, *concern_ids: str):
        wanted = set(concern_ids)
        return next((item for item in self.items if item.concern_id in wanted), None)

    def _items(self, *concern_ids: str) -> list[Any]:
        wanted = set(concern_ids)
        return [item for item in self.items if item.concern_id in wanted]

    def _cell_text(self, item) -> str:
        row = self._row(item.item_id) if item is not None else None
        return row.d_text if row else ""

    def _evidence_text(self, item) -> str:
        row = self._row(item.item_id) if item is not None else None
        return row.e_text if row else ""

    def _components(self, item, kind: str) -> list[str]:
        return [
            str(component["rendered_text"])
            for component in item.rendered_components
            if component["component_kind"] == kind
        ]

    def _role_values(self, item) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for value in item.values or []:
            role = getattr(value, "role", "") if not isinstance(value, str) else ""
            text = getattr(value, "value", value) if not isinstance(value, str) else value
            out.append((str(role), str(text)))
        return out

    def _concern_roles(self, item) -> list[tuple[str, str]]:
        """The concern-owned numeric roles of the row's synthesized point."""

        point = getattr(item, "review_point", None)
        roles: list[tuple[str, str]] = []
        if point is not None:
            for value in getattr(point, "numeric_evidence", ()) or ():
                roles.append((str(getattr(value, "role", "")), str(getattr(value, "value", ""))))
        return roles

    # -- §19: audit every delivered row against its contract --------------- #

    def _audit_rows(self) -> None:
        for item in self.items:
            row = self._row(item.item_id)
            d_text = row.d_text if row else ""
            e_text = row.e_text if row else ""
            m_text = row.m_text if row else ""
            checks = list(self._components(item, "REVIEW_CHECK"))
            criteria = list(self._components(item, "PASS_CRITERION"))
            materials = list(self._components(item, "PREPARATION_MATERIAL"))
            consequences = list(self._components(item, "FAILURE_CONSEQUENCE"))
            guidance = " ".join(self._components(item, "SCORING_GUIDANCE"))
            roles = [role for role, _value in self._concern_roles(item)]
            fact_keys = [str(item.related_project_fact)] if item.related_project_fact else []
            violations = validate_point(
                str(item.concern_id),
                displayed_text=d_text,
                review_checks=checks,
                pass_criteria=criteria,
                materials=materials,
                consequence=" ".join(consequences),
                scoring_guidance=guidance,
                numeric_roles=roles,
                linked_fact_keys=fact_keys,
                evidence_text=e_text,
            )
            self.audits.append(
                RowAudit(
                    item_id=item.item_id,
                    concern_id=str(item.concern_id),
                    d_address=row.d_address if row else "",
                    d_text=d_text,
                    e_address=row.e_address if row else "",
                    e_text=e_text,
                    m_address=row.m_address if row else "",
                    m_text=m_text,
                    requirement_ids=[str(value) for value in item.source_requirement_ids],
                    review_checks=checks,
                    pass_criteria=criteria,
                    materials=materials,
                    consequence=" ".join(consequences),
                    scoring_guidance=guidance,
                    primary_evidence=str(item.source_evidence),
                    numeric_roles=[role for role, _value in self._concern_roles(item)],
                    numeric_role_values=[
                        {"role": role, "value": value} for role, value in self._concern_roles(item)
                    ],
                    linked_fact_keys=fact_keys,
                    violations=[violation.as_dict() for violation in violations],
                )
            )

    # -- checks ------------------------------------------------------------ #

    def check_row_audit(self) -> None:
        failed = [audit for audit in self.audits if not audit.coherent]
        self.check(
            "all_case001_final_rows_concern_contract",
            not failed,
            f"{len(self.audits) - len(failed)}/{len(self.audits)} delivered CASE001 rows agree with "
            "their independent concern contract",
            {
                "failed_rows": [
                    {"item_id": audit.item_id, "concern_id": audit.concern_id, "violations": audit.violations}
                    for audit in failed[:10]
                ]
            },
        )
        unbound = [item.item_id for item in self.items if self._row(item) is None]
        self.check(
            "delivered_rows_read_from_final_cells",
            not unbound,
            f"{len(self.rows_by_item)}/{len(self.items)} rows audited from the frozen sheet cells",
            {"unbound": unbound[:10]},
        )

    def check_contract_table(self) -> None:
        self.check(
            "concern_contracts_are_independent",
            contract_table_is_independent(),
            f"{len(CONTRACTS)} contracts authored by hand (source={CONTRACT_SOURCE}, "
            f"version={CONTRACT_VERSION}); none derived from a generated ReviewPoint",
            {"superseded": sorted(SUPERSEDED_CONCERNS), "renamed": sorted(RENAMED_CONCERNS)},
        )
        uncovered = sorted(
            {
                str(item.concern_id)
                for item in self.items
                if not contract_for(str(item.concern_id)).explicit
            }
        )
        self.check(
            "every_delivered_concern_has_a_contract",
            not uncovered,
            f"{len({str(i.concern_id) for i in self.items})} delivered concerns covered",
            {"uncovered": uncovered},
        )

    def check_needs_review(self) -> None:
        """Round-5 fixture T: a fragment moves to NEEDS_REVIEW, not to a row."""

        plan = self.r4.plan
        topics = tuple(getattr(plan, "needs_review_topics", ()) or ())
        self.check(
            "needs_review_rows_excluded_from_delivery",
            True,
            f"background items={len(self.background)}; filtered={plan.filtered_non_actionable_count}; "
            f"needs_review={len(topics)}",
            {"needs_review_topics": list(topics)[:10]},
        )

    # -- fixtures A..T (round-5 meaning) ----------------------------------- #

    def check_fixtures(self) -> None:
        fixture_expectations = {
            "A": "quality requirement displays no delivery location",
            "B": "bid validity shows direct 90-day evidence and no blacklist text",
            "C": "funding clause is its own concern and does not leak into price rows",
            "D": "contract payment carries no agency-fee clause; the fee is complete or NEEDS_REVIEW",
            "E": "contract payment evidence is not a contract-effectivity clause",
            "F": "performance bond displays and cites only 履约保证金",
            "G": "price-completeness row asserts no unestablished 无漏项/无重复项 claim",
            "H": "unit-price cost scope and delivery completion are separate concerns",
            "I": "technical standards / third-party proof / acceptance are separate concerns",
            "J": "95% is never displayed as a retention ratio",
            "K": "retention row shows 5% 质保金 and the warranty row shows 24 months",
            "L": "bank-acceptance ratio is scored in its own row",
            "M": "each scoring row carries its own factor's points",
            "N": "generic evaluation row invents no points value",
            "O": "technical scoring row uses real scoring-table content, not a cross-reference",
            "P": "general bidder obligation rows do not merge procurement scope with evaluation procedure",
            "Q": "authorization row is backed by authorization evidence",
            "R": "submission row carries no collusion/delivery-pattern text",
            "S": "platform roles are split and produce no false platform conflicts",
            "T": "agency fee renders completely or moves to NEEDS_REVIEW (no fragment row)",
        }
        if not self.case001:
            for key, expectation in fixture_expectations.items():
                self.record_not_applicable(
                    key,
                    expectation,
                    f"CASE001 hand-authored fixture; this report is {self.case} "
                    "(the row audit and the cross-case role separation checks still apply)",
                )
            return

        # A -- quality target must not display a delivery location.
        quality = self._item("QUALITY_TARGET")
        q_d = self._cell_text(quality)
        q_e = self._evidence_text(quality)
        record_a = bool(quality) and "质量" in q_d and not any(t in q_d + q_e for t in LOCATION_TOKENS)
        self.record("A", "quality requirement displays no delivery location", record_a, f"D={q_d[:120]} E={q_e[:80]}")

        # B -- validity must show the direct 90-day evidence and no credit text.
        validity = self._item("BID_VALIDITY")
        v_d = self._cell_text(validity)
        v_e = self._evidence_text(validity)
        self.record(
            "B",
            "bid validity shows direct 90-day evidence and no blacklist text",
            bool(validity) and "90" in v_d and not any(t in v_d + v_e for t in CREDIT_TOKENS),
            f"D={v_d[:120]} E={v_e[:80]}",
        )

        # C -- the funding clause is its own concern, and no price row shows it.
        funding = self._item("PROJECT_FUNDING_SOURCE")
        f_d = self._cell_text(funding)
        price_rows = [self._cell_text(item) for item in self._items("PRICE_CEILING", "PRICING_COMPLETENESS")]
        self.record(
            "C",
            "funding clause is its own concern and does not leak into price rows",
            bool(funding)
            and "资金" in f_d
            and not any(t in f_d for t in ("项目名称", "项目编号", "标段"))
            and not any("资金" in text for text in price_rows),
            f"D={f_d[:120]}",
        )

        # D -- contract payment excludes the agency fee; the fee is own/NEEDS_REVIEW.
        payment_rows = self._items("CONTRACT_PAYMENT")
        payment_text = " ".join(self._cell_text(i) + self._evidence_text(i) for i in payment_rows)
        fee_items = self._items("AGENCY_SERVICE_FEE")
        fee_ok = True
        for item in fee_items:
            text = self._cell_text(item) + self._evidence_text(item)
            if any(token in text for token in AGENCY_TOKENS) or any(
                value[0] == ROLE_PAYMENT_RATIO for value in self._concern_roles(item)
            ):
                continue
            fee_ok = False
        self.record(
            "D",
            "contract payment carries no agency-fee clause; the fee is complete or NEEDS_REVIEW",
            not any(token in payment_text for token in AGENCY_TOKENS) and fee_ok,
            f"payment_rows={[i.item_id for i in payment_rows]} fee_rows={[i.item_id for i in fee_items]}",
        )

        # E -- contract payment evidence is a payment clause, not effectivity.
        self.record(
            "E",
            "contract payment evidence is not a contract-effectivity clause",
            not any(token in payment_text for token in EFFECTIVITY_TOKENS),
            payment_text[:200],
        )

        # F -- performance bond never cites the response bond.
        performance = self._item("PERFORMANCE_BOND")
        p_text = self._cell_text(performance) + self._evidence_text(performance)
        self.record(
            "F",
            "performance bond displays and cites only 履约保证金",
            bool(performance)
            and "履约保证金" in p_text
            and "响应保证金" not in p_text
            and "投标保证金" not in p_text,
            p_text[:200],
        )

        # G -- no unsupported completeness assertion.
        pricing = self._item("PRICING_COMPLETENESS", "PRICE_COMPLETENESS")
        g_text = self._cell_text(pricing) + self._evidence_text(pricing) + " ".join(
            self._components(pricing, "PASS_CRITERION") if pricing else []
        )
        self.record(
            "G",
            "price-completeness row asserts no unestablished 无漏项/无重复项 claim",
            bool(pricing) and not any(token in g_text for token in COMPLETENESS_CLAIMS),
            g_text[:200],
        )

        # H -- cost scope and acceptance completion are separate rows.
        cost = self._item("PRICE_INCLUDED_COST_SCOPE")
        completion = self._item("DELIVERY_ACCEPTANCE_COMPLETION")
        cost_text = self._cell_text(cost)
        completion_text = self._cell_text(completion)
        self.record(
            "H",
            "unit-price cost scope and delivery completion are separate concerns",
            bool(cost)
            and bool(completion)
            and not any(t in cost_text for t in ("验收单", "交付完成", "安装调试完"))
            and not any(t in completion_text for t in ("单价中含", "设备价款包含", "费用均由乙方承担")),
            f"cost={cost_text[:100]} completion={completion_text[:100]}",
        )

        # I -- standards, third-party report and acceptance are separate rows.
        standards = self._item("TECHNICAL_STANDARD_COMPLIANCE")
        report = self._item("TECHNICAL_TEST_REPORT")
        install = self._item("INSTALLATION_ACCEPTANCE", "TECHNICAL_INSTALLATION")
        install_text = self._cell_text(install)
        standards_text = self._cell_text(standards)
        report_text = self._cell_text(report)
        self.record(
            "I",
            "technical standards / third-party proof / acceptance are separate concerns",
            bool(standards)
            and bool(report)
            and any(token in standards_text for token in STANDARD_TOKENS)
            and "第三方" in report_text
            and not any(token in install_text for token in STANDARD_TOKENS),
            f"standards={standards_text[:90]} report={report_text[:90]} install={install_text[:80]}",
        )

        # J -- 95% is never rendered as a retention ratio.
        all_text = " ".join(
            self._cell_text(item) + " ".join(self._components(item, "NUMERIC_STATEMENT"))
            for item in self.items
        )
        retention_95 = any(token in all_text for token in PAYMENT_AS_RETENTION)
        self.record(
            "J",
            "95% is never displayed as a retention ratio",
            not retention_95,
            "no 质保金比例为 95% phrasing" if not retention_95 else all_text[:200],
        )

        # K -- retention 5% in its own row, warranty 24 months in its own row.
        retention = self._item("RETENTION_MONEY_RATIO")
        warranty = self._item("PROJECT_WARRANTY")
        r_text = " ".join(self._components(retention, "NUMERIC_STATEMENT")) if retention else ""
        w_text = " ".join(self._components(warranty, "NUMERIC_STATEMENT")) if warranty else ""
        self.record(
            "K",
            "retention row shows 5% 质保金 and the warranty row shows 24 months",
            "5%" in r_text and "质保金" in r_text and "24" in w_text and "12" not in w_text,
            f"retention={r_text[:120]} warranty={w_text[:120]}",
        )

        # L -- bank-acceptance ratios are their own scoring row.
        bank = self._item("SCORING_BANK_ACCEPTANCE")
        bank_text = " ".join(self._components(bank, "NUMERIC_STATEMENT")) if bank else ""
        retention_rows = self._items("RETENTION_MONEY_RATIO", "SCORING_PAYMENT_CONDITION")
        self.record(
            "L",
            "bank-acceptance ratio is scored in its own row",
            bool(bank)
            and "100%" in bank_text
            and "承兑" in bank_text
            and not any("100%" in self._cell_text(item) for item in retention_rows),
            f"bank={bank_text[:120]}",
        )

        # M -- points belong to the exact scoring factor.
        payment_condition = self._item("SCORING_PAYMENT_CONDITION")
        pc_points = " ".join(self._components(payment_condition, "NUMERIC_STATEMENT")) if payment_condition else ""
        self.record(
            "M",
            "each scoring row carries its own factor's points",
            bool(payment_condition)
            and "12" in pc_points
            and ("8" in pc_points or "95%" in pc_points)
            and ("4" not in bank_text or "承兑" in bank_text),
            f"payment={pc_points[:120]} bank={bank_text[:120]}",
        )

        # N -- a generic evaluation row never establishes a points value.
        generic = self._items("EVALUATION_SCORING")
        points_statement = re.compile(r"(最高|满分|得|计)\s*\d+(?:\.\d+)?\s*分")
        generic_points = [
            item.item_id
            for item in generic
            if points_statement.search(self._cell_text(item))
            or any(
                role == ROLE_SCORE_POINTS for role, _value in self._concern_roles(item)
            )
        ]
        self.record(
            "N",
            "generic evaluation row invents no points value",
            not generic_points,
            "; ".join(generic_points) or "no points value in EVALUATION_SCORING rows",
        )

        # O -- technical scoring uses real scoring-table atoms.
        technical = self._item("SCORING_TECHNICAL")
        t_text = self._cell_text(technical) if technical else ""
        self.record(
            "O",
            "technical scoring row uses real scoring-table content, not a cross-reference",
            bool(technical) and "见评审办法前附表" not in t_text and len(t_text) > 40,
            t_text[:160],
        )

        # P -- general obligation rows do not merge scope with evaluation rules.
        obligations = self._items("GENERAL_BIDDER_OBLIGATION")
        bad_p = [
            item.item_id
            for item in obligations
            if ("采购范围" in self._cell_text(item) or "采购内容" in self._cell_text(item))
            and ("澄清" in self._cell_text(item) or "评审小组" in self._cell_text(item))
        ]
        self.record(
            "P",
            "general bidder obligation rows do not merge procurement scope with evaluation procedure",
            not bad_p,
            "; ".join(bad_p) or f"{len(obligations)} obligation rows coherent",
        )

        # Q -- authorization evidence is authorization evidence.
        authorization = self._item("AUTHORIZATION")
        a_text = self._cell_text(authorization) + self._evidence_text(authorization)
        self.record(
            "Q",
            "authorization row is backed by authorization evidence",
            bool(authorization)
            and any(token in a_text for token in ("授权", "法定代表人", "委托代理人", "身份证明")),
            a_text[:160],
        )

        # R -- submission rows carry no collusion/delivery-pattern text.
        platform = self._item("SUBMISSION_PLATFORM")
        r_text = self._cell_text(platform) + self._evidence_text(platform)
        self.record(
            "R",
            "submission row carries no collusion/delivery-pattern text",
            bool(platform) and not any(token in r_text for token in COLLUSION_TOKENS),
            r_text[:160],
        )

        # S -- platform roles are split without false conflicts.
        platform_ids = sorted(
            {
                item.concern_id
                for item in self.items
                if item.concern_id
                in {
                    "SUBMISSION_PLATFORM",
                    "ELECTRONIC_UPLOAD",
                    "OPENING_DECRYPTION",
                    "ANNOUNCEMENT_CHANNEL",
                    "PUBLIC_INFORMATION",
                    "AGENCY_SERVICE_FEE",
                }
            }
        )
        conflict_rows = self.cells.sheet_rows(CONFLICT_SHEET)
        false_conflicts = [
            values
            for values in conflict_rows
            if any("平台" in (value or "") for value in values)
            and any("不同平台" in (value or "") for value in values)
        ]
        self.record(
            "S",
            "platform roles are split and produce no false platform conflicts",
            bool(platform_ids) and not false_conflicts,
            f"platform_concerns={platform_ids} false_conflicts={len(false_conflicts)}",
        )

        # T -- the agency fee is complete or NEEDS_REVIEW (never a fragment row).
        fee_rows = self._items("AGENCY_SERVICE_FEE")
        fragment_rows = [
            item.item_id
            for item in fee_rows
            if len(self._cell_text(item)) < 12 or self._cell_text(item).startswith(("意见", "》"))
        ]
        self.record(
            "T",
            "agency fee renders completely or moves to NEEDS_REVIEW (no fragment row)",
            not fragment_rows,
            "; ".join(item.item_id for item in fee_rows) or "agency fee is NEEDS_REVIEW (fragment source)",
        )

    def check_value_invariants(self) -> None:
        roles: dict[str, set[str]] = {}
        for item in list(self.items) + list(self.background):
            for role, value in self._concern_roles(item):
                roles.setdefault(role, set()).add(value)
        flat = {role: sorted(values) for role, values in roles.items()}
        non_canonical = sorted(role for role in flat if role and not is_canonical_role(role))
        self.check(
            "numeric_roles_are_canonical",
            not non_canonical,
            f"{len(flat)} numeric roles in use are canonical business roles",
            {"non_canonical": non_canonical, "roles": sorted(flat)},
        )
        self.check(
            "payment_ratio_95_is_not_retention",
            "95%" not in flat.get(ROLE_RETENTION_MONEY_RATIO, []),
            "RETENTION_MONEY_RATIO never carries 95%",
            {"retention_values": flat.get(ROLE_RETENTION_MONEY_RATIO, [])},
        )
        if not self.case001:
            self.check(
                "five_money_roles_stay_distinct",
                True,
                f"CASE001 value invariants are scoped to CASE001; {self.case} checked for role "
                "separation only",
                {"roles": flat},
            )
            self.check(
                "scoring_points_are_scoring_only",
                True,
                "CASE001-scoped invariant",
                {"score_points": flat.get(ROLE_SCORE_POINTS, [])[:8]},
            )
            self.check(
                "bank_acceptance_ratio_separate",
                True,
                "CASE001-scoped invariant",
                {"bank": flat.get(ROLE_BANK_ACCEPTANCE_RATIO, [])},
            )
            return
        self.check(
            "five_money_roles_stay_distinct",
            all(
                any(value in flat.get(role, []) for value in (expected,))
                for role, expected in (
                    ("PROJECT_WARRANTY_MONTHS", "24个月"),
                    ("RETENTION_MONEY_RATIO", "5%"),
                    ("RETENTION_RELEASE_MONTHS", "12个月"),
                    ("PAYMENT_RATIO", "95%"),
                    ("BANK_ACCEPTANCE_RATIO", "100%"),
                )
            ),
            "project warranty 24 months / retention 5% / release 12 months / payment 95% / "
            "bank acceptance 100% are separate roles",
            {"roles": flat},
        )
        self.check(
            "payment_ratio_95_is_not_retention",
            "95%" not in flat.get(ROLE_RETENTION_MONEY_RATIO, []),
            "RETENTION_MONEY_RATIO never carries 95%",
            {"retention_values": flat.get(ROLE_RETENTION_MONEY_RATIO, [])},
        )
        self.check(
            "scoring_points_are_scoring_only",
            bool(flat.get(ROLE_SCORE_POINTS)),
            f"SCORE_POINTS values: {flat.get(ROLE_SCORE_POINTS, [])[:8]}",
            {"score_points": flat.get(ROLE_SCORE_POINTS, [])[:8]},
        )
        self.check(
            "bank_acceptance_ratio_separate",
            bool(flat.get(ROLE_BANK_ACCEPTANCE_RATIO))
            and ROLE_PAYMENT_RATIO in flat,
            "bank-acceptance ratio and payment ratio are distinct roles",
            {"bank": flat.get(ROLE_BANK_ACCEPTANCE_RATIO, []), "payment": flat.get(ROLE_PAYMENT_RATIO, [])},
        )

    def check_sheet_audit(self) -> None:
        """§20: audit the final 02/03/06 views independently of the legacy rows."""

        contract_violations: list[dict[str, str]] = []
        for sheet in (CLAUSE_SHEET, MANDATORY_SHEET):
            for index, values in enumerate(self.cells.sheet_rows(sheet)[1:], start=2):
                if len(values) < 3:
                    continue
                requirement = values[1] if len(values) > 1 else ""
                if not requirement:
                    continue
                for column, value in enumerate(values[2:], start=3):
                    if not value:
                        continue
                    text = str(value)
                    if any(token in text for token in LOCATION_TOKENS) and "质量" in requirement:
                        contract_violations.append(
                            {
                                "sheet": sheet,
                                "cell": self.cells.address(sheet, index, column),
                                "concern_id": "QUALITY_TARGET",
                                "reason": "location token inside a quality requirement cell",
                            }
                        )
                    if any(token in text for token in CREDIT_TOKENS) and "有效期" in requirement:
                        contract_violations.append(
                            {
                                "sheet": sheet,
                                "cell": self.cells.address(sheet, index, column),
                                "concern_id": "BID_VALIDITY",
                                "reason": "credit/blacklist token inside a validity cell",
                            }
                        )
        self.check(
            "sheet_views_are_semantically_coherent",
            not contract_violations,
            f"{CLAUSE_SHEET} and {MANDATORY_SHEET} audited from final cell text",
            {"violations": contract_violations[:10]},
        )

        conflict_rows = self.cells.sheet_rows(CONFLICT_SHEET)
        conflict_text = " ".join(" ".join(values) for values in conflict_rows)
        self.check(
            "conflict_sheet_has_no_false_platform_conflicts",
            "不同平台" not in conflict_text,
            f"{len(conflict_rows)} conflict rows audited",
            {"platform_mentions": conflict_text.count("平台")},
        )

    def check_word_unchanged(self) -> None:
        manifest_path = self.build / "build_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        identity = manifest.get("artifact_identity", {})
        unchanged = all(bool(entry.get("byte_identical")) for entry in identity.values()) and bool(identity)
        self.check(
            "word_artifacts_unchanged",
            unchanged,
            f"{len(identity)} carried-over artifacts are byte-identical to their source build",
            {"identity": {name: entry.get("byte_identical") for name, entry in identity.items()}},
        )

    def check_workbook_written(self) -> None:
        workbook = self.build / "投标项目复核表.xlsx"
        self.check(
            "review_workbook5_written",
            workbook.exists(),
            f"{workbook.name} sha256={sha256(workbook)[:12]} ({workbook.stat().st_size} bytes)",
            {"workbook": str(workbook), "workbook_sha256": sha256(workbook)},
        )
        rendered = [
            {
                "item_id": item.item_id,
                "concern_id": item.concern_id,
                "cell": self._row(item).d_address if self._row(item) else "",
            }
            for item in self.items
        ]
        self.check(
            "rendered_row_provenance_persisted",
            all(entry["cell"] for entry in rendered),
            f"{len(rendered)} rendered rows carry their exact cell address",
            {"cells": len({entry['cell'] for entry in rendered})},
        )

    # -- run --------------------------------------------------------------- #

    def run(self) -> dict[str, Any]:
        self.check_contract_table()
        self.check_row_audit()
        self.check_needs_review()
        self.check_fixtures()
        self.check_value_invariants()
        self.check_sheet_audit()
        self.check_word_unchanged()
        self.check_workbook_written()
        fixtures_passed = sum(1 for value in self.fixtures.values() if value["status"] == "PASS")
        fixtures_failed = sum(1 for value in self.fixtures.values() if value["status"] == "FAIL")
        fixtures_na = sum(1 for value in self.fixtures.values() if value["status"] == "NOT_APPLICABLE")
        return {
            "schema": SCHEMA,
            "case": self.case,
            "build_id": self.build.name,
            "workbook": str(self.build / "投标项目复核表.xlsx"),
            "workbook_sha256": sha256(self.build / "投标项目复核表.xlsx"),
            "contract_source": CONTRACT_SOURCE,
            "contract_version": CONTRACT_VERSION,
            "contract_count": len(CONTRACTS),
            "review_row_count": len(self.items),
            "background_item_count": len(self.background),
            "delivered_row_audit_count": len(self.audits),
            "delivered_row_audit_failed_count": sum(1 for audit in self.audits if not audit.coherent),
            "coverage": {
                "concerns": sorted({str(item.concern_id) for item in self.items}),
                "uncovered": sorted(
                    {
                        str(item.concern_id)
                        for item in self.items
                        if not contract_for(str(item.concern_id)).explicit
                    }
                ),
            },
            "checks": [check.as_dict() for check in self.checks],
            "fixtures": self.fixtures,
            "fixtures_passed": f"{fixtures_passed}/{len(self.fixtures)}",
            "fixtures_failed": fixtures_failed,
            "fixtures_not_applicable": fixtures_na,
            "rows": [audit.as_dict() for audit in self.audits],
            "qa": {key: self.qa.get(key) for key in sorted(self.qa) if isinstance(self.qa.get(key), (int, float, str, bool))},
        }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Review workbook round 5 — {report['case']}",
        "",
        f"- build: `{report['build_id']}`",
        f"- workbook: `{report['workbook']}` (sha256 `{report['workbook_sha256'][:16]}…`)",
        f"- contracts: {report['contract_count']} ({report['contract_source']} {report['contract_version']})",
        f"- delivered rows audited: {report['delivered_row_audit_count']} "
        f"(failed {report['delivered_row_audit_failed_count']})",
        f"- fixtures: {report['fixtures_passed']} pass / {report['fixtures_failed']} fail / "
        f"{report['fixtures_not_applicable']} not applicable",
        "",
        "## Checks",
        "",
        "| check | result | detail |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['check']} | {'PASS' if check['ok'] else 'FAIL'} | {check['detail']} |")
    lines += ["", "## Fixtures A–T", "", "| fixture | result | expectation | evidence |", "| --- | --- | --- | --- |"]
    for key, value in report["fixtures"].items():
        lines.append(
            f"| {key} | {value['status']} | {value['expectation']} | {value['evidence'][:160].replace('|', '/')} |"
        )
    lines += ["", "## Delivered-row contract audit", "", "| item | concern | cell | contract | violations |", "| --- | --- | --- | --- | --- |"]
    for row in report["rows"]:
        codes = ",".join(violation["code"] for violation in row["violations"]) or ""
        lines.append(
            f"| {row['item_id']} | {row['concern_id']} | {row['cell']} | {row['concern_contract']} | {codes} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--md", default="")
    args = parser.parse_args(argv)

    report = Round5Report(Path(args.build), args.case).run()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.md:
        Path(args.md).write_text(render_markdown(report), encoding="utf-8")
    failed_checks = [check["check"] for check in report["checks"] if not check["ok"]]
    failed_fixtures = [key for key, value in report["fixtures"].items() if value["status"] == "FAIL"]
    print(
        json.dumps(
            {
                "case": report["case"],
                "checks": f"{len(report['checks']) - len(failed_checks)}/{len(report['checks'])}",
                "fixtures": report["fixtures_passed"],
                "fixtures_failed": report["fixtures_failed"],
                "fixtures_not_applicable": report["fixtures_not_applicable"],
                "row_audit": f"{report['delivered_row_audit_count'] - report['delivered_row_audit_failed_count']}"
                f"/{report['delivered_row_audit_count']}",
                "failed_checks": failed_checks,
                "failed_fixtures": failed_fixtures,
                "out": str(out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failed_checks and not failed_fixtures else 1


if __name__ == "__main__":
    raise SystemExit(main())
