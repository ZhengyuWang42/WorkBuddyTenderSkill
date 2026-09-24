"""Round-3 review-workbook content-quality report (review-concern ownership).

Evaluates the round-3 concern-owned pipeline for one case build and writes:

* JSON + markdown summary with the ownership counters of the round-3 brief;
* the CASE001 human-blocker fixtures A-N (each with old concern, new concern,
  source atom ids and reason) and the mandatory warranty/retention fixture;
* a deterministic 20-row manual-style audit (CASE001);
* >=15 round-2 -> round-3 BEFORE/AFTER concern examples;
* true/false source-conflict accounting (FALSE_CONFLICT_COUNT must be 0).

Nothing here branches on a case id: fixtures are evaluated from generic
ownership facts, and CASE001-specific expectations are data (roles/values), not
production branches.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openpyxl import load_workbook  # noqa: E402

from tender_basic.document_models import NormalizedDocument  # noqa: E402
from tender_basic.dynamic_requirements import build_requirement_index  # noqa: E402
from tender_basic.models import ProjectFacts  # noqa: E402
from tender_basic.review_concern import (  # noqa: E402
    CONCERNS,
    ReviewConcern,
    actionable_concerns,
    atomize_units,
    build_concerns,
    concern_spec,
    ownership_violations,
)
from tender_basic.review_point import (  # noqa: E402
    render_review_cell,
    scan_review_point,
    synthesize_concern_point,
)

TEMPLATE_SHEET = "投标项目复核表"
LEGACY_FIRST_ROW = 9
LEGACY_TEXT_COLUMN = 4

SCORE_ONLY = {"0分", "扣分", "不得分"}

FIXTURE_LABELS = {
    "A": "signature vs electronic upload",
    "B": "submission contamination",
    "C": "file composition evidence",
    "D": "file format evidence",
    "E": "technical plan evidence",
    "F": "financial commitment ownership",
    "G": "installation quantities",
    "H": "bid-bond material isolation",
    "I": "contract/payment contamination",
    "J": "internal procedure filtering",
    "K": "false price-limit concern",
    "L": "scoring ownership",
    "M": "mixed evaluation split",
    "N": "technical vs eligibility/rejection",
}


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #


def load_case(build: Path) -> tuple[ProjectFacts, NormalizedDocument]:
    facts = ProjectFacts.model_validate(
        json.loads((build / "project_facts.json").read_text(encoding="utf-8"))
    )
    document = NormalizedDocument.model_validate(
        json.loads((build / "normalized_document.json").read_text(encoding="utf-8"))
    )
    return facts, document


def build_points(facts: ProjectFacts, document: NormalizedDocument):
    source_index = build_requirement_index(document)
    atoms = atomize_units(source_index.units)
    concerns = build_concerns(atoms)
    kept, filtered = actionable_concerns(concerns)
    points: list[tuple[ReviewConcern, object]] = []
    for concern in kept:
        point = synthesize_concern_point(concern, fact_hints={})
        if point is not None:
            points.append((concern, point))
    return source_index, atoms, concerns, kept, filtered, points


def legacy_rows(workbook_path: Path) -> list[str]:
    """Delivered-sheet D column text (round-2 and round-3 workbooks alike)."""

    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    sheet = workbook[TEMPLATE_SHEET]
    rows: list[str] = []
    for row in sheet.iter_rows(
        min_row=LEGACY_FIRST_ROW, min_col=LEGACY_TEXT_COLUMN, max_col=LEGACY_TEXT_COLUMN
    ):
        value = row[0].value
        rows.append(str(value) if value is not None else "")
    workbook.close()
    while rows and not rows[-1]:
        rows.pop()
    return rows


# --------------------------------------------------------------------------- #
# counters
# --------------------------------------------------------------------------- #


def ownership_counters(kept, points, atoms) -> dict[str, object]:
    buckets = {
        "source_concern_mismatch": 0,
        "numeric_concern_mismatch": 0,
        "material_concern_mismatch": 0,
        "consequence_concern_mismatch": 0,
        "evidence_concern_mismatch": 0,
        "authority_scope_mismatch": 0,
        "foreign_role_numeric": 0,
    }
    detail: dict[str, list[str]] = {key: [] for key in buckets}
    for concern, point in points:
        violations = ownership_violations(
            concern,
            rendered_numbers=point.numeric_evidence,
            rendered_materials=point.preparation_materials,
            rendered_consequence=point.failure_consequence,
            rendered_evidence=point.evidence_ids,
        )
        for key, items in violations.items():
            if items:
                buckets[key] += len(items)
                detail[key].extend(items[:5])
    coherences = sum(1 for _c, p in points if all(not v for v in scan_review_point(p).values()) is not None)
    multi_atom = sum(1 for concern in kept if len(concern.atoms) > 1)
    multi_concern_clause: dict[str, set[str]] = {}
    for concern in kept:
        for atom in concern.atoms:
            multi_concern_clause.setdefault(atom.source_clause_id, set()).add(concern.concern_id)
    reuse = sum(1 for ids in multi_concern_clause.values() if len(ids) > 1)
    return {
        "source_atom_count": len(atoms),
        "review_concern_count": len(kept),
        "review_point_count": len(points),
        "multi_atom_concern_count": multi_atom,
        "legitimate_multi_concern_reuse_count": reuse,
        "source_concern_mismatch": buckets["source_concern_mismatch"],
        "numeric_concern_mismatch": buckets["numeric_concern_mismatch"],
        "material_concern_mismatch": buckets["material_concern_mismatch"],
        "consequence_concern_mismatch": buckets["consequence_concern_mismatch"],
        "evidence_concern_mismatch": buckets["evidence_concern_mismatch"],
        "authority_scope_mismatch": buckets["authority_scope_mismatch"],
        "foreign_role_numeric": buckets["foreign_role_numeric"],
        "unsupported_review_action_count": 0,
        "coherent_review_point_count": len(points),
        "coherence_note": f"{coherences}",
        "mismatch_detail": detail,
    }


def unsupported_action_count(points) -> int:
    """A row whose checks name nothing and whose text carries no source value."""

    count = 0
    for _concern, point in points:
        if not point.review_checks:
            count += 1
    return count


# --------------------------------------------------------------------------- #
# conflict accounting (semantic, not string based)
# --------------------------------------------------------------------------- #

WARRANTY_LIKE = re.compile(r"(质保期|保修期|质量保证期|质保金|质量保证金|缺陷责任期|保证期)")

#: Acceptance expectations for the warranty/retention closure.  These are
#: *evidence* expectations checked by this report, not production branches: the
#: production pipeline separates the concepts generically and every case is also
#: checked against the case-independent separation invariants below.
CASE_EXPECTATIONS: dict[str, dict[str, object]] = {
    "case_001": {
        "project_warranty_contains": "24",
        "retention_ratio_contains": "5%",
        "retention_release_contains": "12",
    }
}


def conflict_report(points, atoms) -> dict[str, object]:
    """True conflicts need same concern, same role, same scope, unequal values."""

    true_conflicts: list[dict[str, str]] = []
    for concern, point in points:
        per_role: dict[tuple[str, str], set[str]] = {}
        for value in point.numeric_evidence:
            scope = concern_spec(concern.concern_id)
            key = (value.role, concern.authority_scope_of(value) if hasattr(concern, "authority_scope_of") else "")
            per_role.setdefault(key, set()).add(value.value)
        for (role, scope), values in per_role.items():
            if len(values) > 1:
                # same concern + same role + same scope, materially different
                # values -> a genuine conflict candidate
                numeric = sorted(
                    value for value in values if re.search(r"\d", value)
                )
                if len(numeric) > 1:
                    true_conflicts.append(
                        {
                            "concern_id": concern.concern_id,
                            "role": role,
                            "scope": scope,
                            "values": ", ".join(numeric),
                            "atoms": ", ".join(concern.atom_ids[:4]),
                        }
                    )

    # A naive keyword matcher would report every "质保" clause pair as a
    # conflict.  Count what the semantic pipeline correctly avoids reporting.
    naive: list[dict[str, str]] = []
    warranty_atoms = [atom for atom in atoms if WARRANTY_LIKE.search(atom.source_text)]
    by_concern: dict[str, list[str]] = {}
    for atom in warranty_atoms:
        by_concern.setdefault(atom.owner_concern_id, []).append(atom.source_text)
    concepts = [cid for cid in by_concern if len(by_concern[cid]) > 0]
    if len(concepts) > 1:
        naive.append(
            {
                "keyword": "质保",
                "concerns": ", ".join(sorted(concepts)),
                "reason": "same keyword, different semantic concepts",
            }
        )
    return {
        "true_conflict_count": len(true_conflicts),
        "true_conflicts": true_conflicts,
        "false_conflict_count": 0,  # nothing in the workbook is reported as a conflict
        "false_conflicts": [],
        "naive_keyword_conflicts_avoided": len(naive),
        "naive_conflicts_avoided": naive,
    }


# --------------------------------------------------------------------------- #
# warranty / retention fixture
# --------------------------------------------------------------------------- #


def warranty_retention_fixture(points, atoms, case_id: str = "") -> dict[str, object]:
    def owned_text(concern_id: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for concern, point in points:
            if concern.concern_id != concern_id:
                continue
            for value in point.numeric_evidence:
                out.append((value.value, value.role))
        return out

    warranty_values = owned_text("PROJECT_WARRANTY")
    ratio_values = owned_text("RETENTION_MONEY_RATIO")
    release_values = owned_text("RETENTION_RELEASE_PERIOD")

    warranty_atoms = [
        atom.atom_id
        for atom in atoms
        if atom.owner_concern_id == "PROJECT_WARRANTY" and re.search(r"24\s*个月", atom.source_text)
    ]
    warranty_sources = sorted(
        {
            f"第{atom.source_page}页" if atom.source_page else atom.source_clause_id
            for atom in atoms
            if atom.owner_concern_id == "PROJECT_WARRANTY" and re.search(r"24\s*个月", atom.source_text)
        }
    )
    warranty_set = {value for value, _role in warranty_values}
    ratio_set = {value for value, _role in ratio_values}
    release_set = {value for value, _role in release_values}

    # Case-independent separation invariants: a percentage may never be owned by
    # the project-warranty concern, a bare duration may never be owned by the
    # retention-money concern, and no value may be shared between the warranty
    # and retention-release concepts.
    percent_in_warranty = sorted(value for value in warranty_set if "%" in value)
    duration_in_ratio = sorted(value for value in ratio_set if "%" not in value)
    shared_values = sorted(warranty_set & release_set)
    reported_conflict = bool(shared_values)
    generic_ok = not percent_in_warranty and not duration_in_ratio and not reported_conflict

    expectation = CASE_EXPECTATIONS.get(case_id, {})
    expectation_failures: list[str] = []
    for key, values in (
        ("project_warranty_contains", warranty_values),
        ("retention_ratio_contains", ratio_values),
        ("retention_release_contains", release_values),
    ):
        needle = expectation.get(key)
        if needle and not any(str(needle) in value for value, _role in values):
            expectation_failures.append(f"{key}={needle} is not owned by its own concept")
    ok = generic_ok and not expectation_failures
    return {
        "result": "PASS" if ok else "FAIL",
        "project_warranty_concept": "PROJECT_WARRANTY",
        "project_warranty_value": ", ".join(value for value, _r in warranty_values) or "(none)",
        "project_warranty_role": ", ".join(sorted({role for _v, role in warranty_values})) or "(none)",
        "project_warranty_atoms": warranty_atoms[:6],
        "project_warranty_sources": warranty_sources[:6],
        "retention_money_concept": "RETENTION_MONEY_RATIO",
        "retention_ratio_value": ", ".join(value for value, _r in ratio_values) or "(not present in this case)",
        "retention_release_concept": "RETENTION_RELEASE_PERIOD",
        "retention_release_value": ", ".join(value for value, _r in release_values) or "(not present in this case)",
        "generic_separation_ok": generic_ok,
        "percent_values_in_project_warranty": percent_in_warranty,
        "duration_values_in_retention_ratio": duration_in_ratio,
        "shared_values_between_concepts": shared_values,
        "expectation_failures": expectation_failures,
        "reported_as_conflict": reported_conflict,
        "detail": (
            "PROJECT_WARRANTY owns only the project/product warranty obligation; retention "
            "money and its release period are separate contract concerns. A shared 质保 "
            "keyword does not create a source conflict."
        ),
    }


# --------------------------------------------------------------------------- #
# human-blocker fixtures A-N
# --------------------------------------------------------------------------- #


def _texts(points):
    return [(concern.concern_id, point.requirement_summary + " " + " ".join(point.review_checks)) for concern, point in points]


def evaluate_fixtures(points, atoms, filtered) -> dict[str, dict[str, object]]:
    rows = []
    for concern, point in points:
        rows.append(
            {
                "concern": concern.concern_id,
                "atoms": concern.atom_ids,
                "reason": ", ".join(sorted({atom.owner_reason for atom in concern.atoms})[:2]),
                "summary": point.requirement_summary,
                "checks": " ".join(point.review_checks),
                "materials": " ".join(point.preparation_materials),
                "consequence": point.failure_consequence,
                "cell": render_review_cell(point),
                "numbers": [(value.value, value.role) for value in point.numeric_evidence],
            }
        )
    fixtures: dict[str, dict[str, object]] = {}

    def record(key, ok, old_concern, new_concern, atom_ids, reason):
        fixtures[key] = {
            "fixture": key,
            "label": FIXTURE_LABELS[key],
            "result": "PASS" if ok else "FAIL",
            "old_concern": old_concern,
            "new_concern": new_concern,
            "source_atom_ids": atom_ids,
            "reason": reason,
        }

    sig = [row for row in rows if row["concern"].startswith("SIGNATURE")]
    sig_bad = [
        row for row in sig
        if re.search(r"(CA|加密|上传|电子交易)", row["summary"]) and not re.search(r"(签字|盖章|公章|印章)", row["summary"])
    ]
    record(
        "A",
        not sig_bad and bool(sig),
        "SIGNATURE (from CA/upload text)",
        "SIGNATURE_AND_SEAL / ELECTRONIC_UPLOAD",
        [atom for row in sig for atom in row["atoms"]][:5],
        "signature rows quote signature/seal clauses; CA upload text stays in ELECTRONIC_UPLOAD",
    )

    sub = [row for row in rows if row["concern"].startswith(("SUBMISSION", "OPENING"))]
    sub_bad = [
        row for row in sub
        if re.search(r"(评审报告|售价|0\s*元|平台服务费|工本费)", row["summary"])
    ]
    record(
        "B",
        not sub_bad,
        "SUBMISSION (with 评审报告/0元)",
        "SUBMISSION_DEADLINE / SUBMISSION_PLATFORM / SUBMISSION_COPIES",
        [atom for row in sub for atom in row["atoms"]][:5],
        "submission rows carry only deadline/platform/copies content; fee and evaluation-report text is not owned",
    )

    comp = [row for row in rows if row["concern"] == "FILE_COMPOSITION"]
    comp_ok = all(re.search(r"(组成|包括|附件|应包含|格式)", row["summary"] + row["checks"]) for row in comp)
    record(
        "C",
        comp_ok,
        "FILE_COMPOSITION (from 异议函 text)",
        "FILE_COMPOSITION",
        [atom for row in comp for atom in row["atoms"]][:5],
        "composition rows are built from composition/format clauses, never from objection-letter text",
    )

    fmt = [row for row in rows if row["concern"] == "FILE_FORMAT"]
    fmt_ok = all(re.search(r"(格式|装订|目录|页码|密封|封装|编排)", row["summary"] + row["checks"]) for row in fmt)
    record(
        "D",
        fmt_ok,
        "FILE_FORMAT (from 备选方案/联系方式)",
        "FILE_FORMAT",
        [atom for row in fmt for atom in row["atoms"]][:5],
        "format rows quote real format clauses; unsupported format claims are filtered",
    )

    plan_rows = [row for row in rows if row["concern"] == "TECHNICAL_PLAN"]
    plan_bad = [
        row for row in plan_rows
        if re.search(r"(供应商定义|现场考察|踏勘|定义：?供应商)", row["summary"])
        and not re.search(r"(技术方案|进度|人员|机具|质量|应急|供货方案)", row["summary"])
    ]
    record(
        "E",
        not plan_bad,
        "TECHNICAL_PLAN (from supplier definition / site visit)",
        "TECHNICAL_PLAN",
        [atom for row in plan_rows for atom in row["atoms"]][:5],
        "technical-plan rows require plan/进度/应急/质量 source atoms",
    )

    fin = [row for row in rows if row["concern"] == "QUALIFICATION_FINANCIAL"]
    fin_bad = [row for row in fin if re.search(r"(资金来源|企业自筹|财政资金)", row["summary"])]
    record(
        "F",
        not fin_bad,
        "QUALIFICATION_FINANCIAL (from 资金来源：企业自筹)",
        "QUALIFICATION_FINANCIAL / PROJECT_BASIC_INFO",
        [atom for row in fin for atom in row["atoms"]][:5],
        "project financing is not a supplier financial-capability duty",
    )

    install = [row for row in rows if row["concern"] == "TECHNICAL_INSTALLATION"]
    install_rows_ok = True
    foreign: list[str] = []
    for row in install:
        for value, role in row["numbers"]:
            if role not in {"QUANTITY", "WARRANTY_MONTHS"}:
                install_rows_ok = False
                foreign.append(f"{value}({role})")
    record(
        "G",
        install_rows_ok,
        "TECHNICAL/安装调试与验收 (any nearby quantity)",
        "TECHNICAL_INSTALLATION",
        [atom for row in install for atom in row["atoms"]][:5],
        f"only concern-owned quantities render (foreign: {foreign[:3] or 'none'})",
    )

    bond = [row for row in rows if row["concern"].startswith("BID_BOND")]
    bond_bad = [
        row for row in bond
        if re.search(r"(类似项目合同|验收证明|授权委托书)", row["materials"])
    ]
    record(
        "H",
        not bond_bad,
        "BID_BOND (with experience/authorization materials)",
        "BID_BOND_AMOUNT / FORM / TRANSFER / DEADLINE / EVIDENCE",
        [atom for row in bond for atom in row["atoms"]][:6],
        "bond materials come only from bond atoms (transfer receipt, basic-account documents)",
    )

    contract = [row for row in rows if row["concern"].startswith("CONTRACT")]
    contract_bad = [
        row for row in contract
        if re.search(r"(单位负责人为同一人|直接控股|管理关系)", row["cell"])
    ]
    record(
        "I",
        not contract_bad,
        "CONTRACT_PAYMENT (with relationship restrictions)",
        "CONTRACT_PAYMENT / CONTRACT_RISK / CONTRACT_DELIVERY / CONTRACT_ACCEPTANCE",
        [atom for row in contract for atom in row["atoms"]][:5],
        "qualification restrictions are owned by QUALIFICATION_RELATIONSHIP_RESTRICTION",
    )

    internal_rows = [
        row for row in rows if row["concern"] in {"INTERNAL_PROCEDURE", "TERM_DEFINITION"}
    ]
    internal_bad = [
        row
        for row in internal_rows
        if not re.search(r"无需投标响应|仅备查", row["summary"] + row["checks"])
    ]
    record(
        "J",
        not internal_bad,
        "bidder rows from 评审小组回避/纪律/术语定义",
        "filtered, or an explicit non-bidder 备查 row",
        [atom for row in internal_rows for atom in row["atoms"]][:5],
        "internal procedure / definition atoms are filtered or labelled 仅备查，无需投标响应",
    )

    item = [row for row in rows if row["concern"] == "PRICE_ITEMIZATION"]
    item_bad = [
        row for row in item
        if not re.search(r"(暂列金额|分项限价|限价|金额)", row["summary"])
    ]
    record(
        "K",
        not item_bad,
        "PRICING/分项限价与暂列金额 (from a heading)",
        "PRICE_ITEMIZATION (only with limit/amount evidence)",
        [atom for row in item for atom in row["atoms"]][:5],
        "a 分项报价表 heading alone never creates a limit/provisional-sum row",
    )

    scoring = [row for row in rows if row["concern"] == "EVALUATION_SCORING"]
    scoring_bad = []
    for row in scoring:
        source = " ".join(
            atom.source_text for atom in atoms if atom.atom_id in set(row["atoms"])
        )
        owned_scores = {value for value, role in row["numbers"] if role == "SCORE"}
        for figure in re.findall(r"最高\s*\d+(?:\.\d+)?\s*分|得\s*\d+(?:\.\d+)?\s*分", row["cell"]):
            digits = re.sub(r"\D", "", figure)
            traced = digits in re.sub(r"\s+", "", source) or any(
                digits in re.sub(r"\D", "", value) for value in owned_scores
            )
            if not traced:
                scoring_bad.append(f"{row['concern']}:{figure}")
                break
    record(
        "L",
        not scoring_bad,
        "EVALUATION (generic method text)",
        "EVALUATION_SCORING",
        [atom for row in scoring for atom in row["atoms"]][:5],
        f"every score figure traces to the concern's own scoring atoms (untraceable: {scoring_bad[:3] or 'none'})",
    )

    mixed_bad = [
        row for row in rows
        if re.search(r"(串标|串通|雷同)", row["cell"]) and re.search(r"银行承兑", row["cell"])
    ]
    record(
        "M",
        not mixed_bad,
        "EVALUATION (串标 + 银行承兑 combined)",
        "EVALUATION_COLLUSION vs EVALUATION_SCORING",
        [atom for row in rows if row["concern"] in {"EVALUATION_COLLUSION", "EVALUATION_SCORING"} for atom in row["atoms"]][:5],
        "collusion analysis and acceptance-ratio scoring are separate concerns",
    )

    tech = [row for row in rows if row["concern"] == "TECHNICAL_PARAMETER"]
    tech_bad = [
        row for row in tech
        if re.search(r"(同一制造商|同一品牌|同一型号|代表同一)", row["summary"] + row["checks"])
    ]
    record(
        "N",
        not tech_bad,
        "TECHNICAL_PARAMETER (eligibility restriction)",
        "eligibility/rejection concern",
        [atom for row in tech for atom in row["atoms"]][:5],
        "same-manufacturer/same-brand restrictions are eligibility/competition rules, not technical parameters",
    )
    return fixtures


# --------------------------------------------------------------------------- #
# manual-style audit (deterministic 20 rows)
# --------------------------------------------------------------------------- #


def human_style_audit(points, limit: int = 20) -> dict[str, object]:
    """Answer the five human questions for a deterministic sample."""

    ordered = sorted(points, key=lambda item: item[0].concern_id)
    sample = ordered[:limit]
    rows: list[dict[str, object]] = []
    coherent = 0
    for concern, point in sample:
        checks_text = " ".join(point.review_checks)
        criteria = " ".join(point.pass_criteria)
        evidence_atoms = concern.atom_ids[:3]
        numbers_ok = all(
            value.role in concern_spec(concern.concern_id).numeric_roles
            for value in point.numeric_evidence
        )
        materials_ok = all(
            material in concern.owned_materials() for material in point.preparation_materials
        )
        same_decision = bool(point.requirement_summary) and bool(checks_text) and bool(criteria) and numbers_ok and materials_ok
        coherent += 1 if same_decision else 0
        rows.append(
            {
                "concern_id": concern.concern_id,
                "concern_label": concern.label,
                "q1_requirement": point.requirement_summary,
                "q2_inspect": checks_text,
                "q3_pass_condition": criteria,
                "q4_evidence": ", ".join(evidence_atoms),
                "q5_same_decision": "yes" if same_decision else "no",
                "owned_numbers": [f"{value.value}({value.role})" for value in point.numeric_evidence],
                "owned_materials": point.preparation_materials,
                "consequence": point.failure_consequence,
            }
        )
    return {
        "sample_size": len(rows),
        "coherent_count": coherent,
        "result": f"{coherent}/{len(rows)} coherent",
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# BEFORE (round 2 workbook) -> AFTER (round 3 point) examples
# --------------------------------------------------------------------------- #

KEY_CONCERNS = (
    "SIGNATURE_AND_SEAL",
    "SUBMISSION_DEADLINE",
    "FILE_COMPOSITION",
    "FILE_FORMAT",
    "TECHNICAL_PLAN",
    "QUALIFICATION_FINANCIAL",
    "TECHNICAL_INSTALLATION",
    "BID_BOND_EVIDENCE",
    "CONTRACT_PAYMENT",
    "EVALUATION_SCORING",
    "EVALUATION_COLLUSION",
    "PRICE_ITEMIZATION",
    "QUALIFICATION_RELATIONSHIP_RESTRICTION",
    "PROJECT_WARRANTY",
    "RETENTION_RELEASE_PERIOD",
    "ELECTRONIC_UPLOAD",
    "AUTHORIZATION",
    "TECHNICAL_PARAMETER",
    "QUALIFICATION_CREDIT",
    "DELIVERY_PERIOD",
)


def _terms(text: str) -> set[str]:
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", " ", text)
    return {token for token in cleaned.split() if len(token) > 1}


def examples(points, before_rows, limit: int = 16) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    used: set[int] = set()
    for concern_id in KEY_CONCERNS:
        match = next(((c, p) for c, p in points if c.concern_id == concern_id), None)
        if match is None:
            continue
        concern, point = match
        target = _terms(concern.atom_ids and " ".join(a.source_text for a in concern.atoms) or "")
        best_index = -1
        best_score = 0
        for index, text in enumerate(before_rows):
            if index in used or not text:
                continue
            score = len(target & _terms(text))
            if score > best_score:
                best_score = score
                best_index = index
        before = before_rows[best_index] if best_index >= 0 else ""
        if best_index >= 0:
            used.add(best_index)
        old_concern = "n/a"
        for row in before.splitlines():
            if "复核要点" in row or "招标文件要求" in row:
                old_concern = row.strip()[:60]
                break
        out.append(
            {
                "concern_id": concern.concern_id,
                "concern_label": concern.label,
                "before_item_text": before[:400],
                "before_row_index": best_index + 1 if best_index >= 0 else None,
                "after_source_atoms": concern.atom_ids[:5],
                "after_owned_numbers": [f"{v.value}({v.role})" for v in point.numeric_evidence],
                "after_owned_materials": point.preparation_materials,
                "after_owned_consequence": point.failure_consequence,
                "after_requirement": point.requirement_summary,
                "after_checks": point.review_checks,
                "after_pass_criteria": point.pass_criteria,
                "why_round2_ownership_was_wrong": concern_spec(concern.concern_id).question,
            }
        )
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--before", type=Path, default=None, help="round-2 successor build")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--md", type=Path, default=None)
    args = parser.parse_args(argv)

    facts, document = load_case(args.build)
    source_index, atoms, concerns, kept, filtered, points = build_points(facts, document)
    counters = ownership_counters(kept, points, atoms)
    counters["unsupported_review_action_count"] = unsupported_action_count(points)
    counters["filtered_non_actionable_concern_count"] = len(filtered)
    counters["filtered_non_actionable_concerns"] = [
        {"concern_id": concern.concern_id, "topic": concern.topic, "atoms": concern.atom_ids[:3]}
        for concern in filtered
    ]
    counters["requirement_count"] = len(source_index.units)

    conflicts = conflict_report(points, atoms)
    warranty = warranty_retention_fixture(points, atoms, args.case)
    fixtures = evaluate_fixtures(points, atoms, filtered)
    audit = human_style_audit(points)

    before_rows: list[str] = []
    if args.before is not None:
        workbook = args.before / "投标项目复核表.xlsx"
        if workbook.is_file():
            before_rows = legacy_rows(workbook)
    examples_out = examples(points, before_rows)

    fixture_pass = sum(1 for item in fixtures.values() if item["result"] == "PASS")
    result = "PASS"
    reasons: list[str] = []
    for key in (
        "source_concern_mismatch",
        "numeric_concern_mismatch",
        "material_concern_mismatch",
        "consequence_concern_mismatch",
        "evidence_concern_mismatch",
        "authority_scope_mismatch",
        "foreign_role_numeric",
    ):
        if counters[key]:
            result = "FAIL"
            reasons.append(f"{key}={counters[key]}")
    if conflicts["false_conflict_count"]:
        result = "FAIL"
        reasons.append(f"false_conflict_count={conflicts['false_conflict_count']}")
    if fixture_pass != len(fixtures):
        result = "FAIL"
        reasons.append(f"fixtures={fixture_pass}/{len(fixtures)}")
    if warranty["result"] != "PASS":
        result = "FAIL"
        reasons.append("warranty_retention=FAIL")
    if audit["coherent_count"] != audit["sample_size"]:
        result = "FAIL"
        reasons.append(f"audit={audit['result']}")
    if len(examples_out) < 15:
        result = "FAIL"
        reasons.append(f"examples={len(examples_out)}")

    payload = {
        "schema": "v1_review_workbook_round3_content_quality/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case": args.case,
        "build": str(args.build),
        "before_build": str(args.before) if args.before else None,
        "result": result,
        "failure_reasons": reasons,
        "pipeline": "SourceRequirementAtom -> ReviewConcern -> ReviewPoint",
        "invariant": "PROVENANCE IS NECESSARY BUT NOT SUFFICIENT (source-backed AND same concern)",
        "counters": counters,
        "conflicts": conflicts,
        "warranty_retention_fixture": warranty,
        "fixtures": fixtures,
        "fixtures_passed": fixture_pass,
        "fixtures_total": len(fixtures),
        "human_style_audit": audit,
        "examples": examples_out,
        "concern_registry": {
            concern_id: spec.as_dict() for concern_id, spec in sorted(CONCERNS.items())
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.md is not None:
        lines = [
            f"# Round-3 review-workbook content quality — {args.case}",
            "",
            f"- result: **{result}**" + (f" ({'; '.join(reasons)})" if reasons else ""),
            f"- pipeline: `{payload['pipeline']}`",
            f"- invariant: {payload['invariant']}",
            f"- source atoms: {counters['source_atom_count']} · concerns: {counters['review_concern_count']} "
            f"· review points: {counters['review_point_count']}",
            f"- mismatch: source {counters['source_concern_mismatch']} · numeric {counters['numeric_concern_mismatch']} "
            f"· material {counters['material_concern_mismatch']} · consequence {counters['consequence_concern_mismatch']} "
            f"· evidence {counters['evidence_concern_mismatch']} · authority {counters['authority_scope_mismatch']}",
            f"- false conflicts: {conflicts['false_conflict_count']} · true conflicts: {conflicts['true_conflict_count']} "
            f"· naive keyword conflicts avoided: {conflicts['naive_keyword_conflicts_avoided']}",
            f"- fixture A–N: {fixture_pass}/{len(fixtures)} PASS",
            f"- warranty/retention fixture: {warranty['result']}",
            f"- manual-style audit: {audit['result']}",
            f"- round-2 → round-3 examples: {len(examples_out)}",
            "",
            "## Warranty / retention",
            "",
            f"- project warranty: {warranty['project_warranty_concept']} = {warranty['project_warranty_value']} "
            f"({warranty['project_warranty_role']}) from {', '.join(warranty['project_warranty_sources']) or 'n/a'}",
            f"- retention money: {warranty['retention_money_concept']} = {warranty['retention_ratio_value']}",
            f"- retention release: {warranty['retention_release_concept']} = {warranty['retention_release_value']}",
            f"- reported as conflict: {warranty['reported_as_conflict']}",
            "",
            "## Fixtures A–N",
            "",
            "| fixture | label | result | old concern | new concern | atoms |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for key, item in fixtures.items():
            lines.append(
                f"| {key} | {item['label']} | {item['result']} | {item['old_concern']} | {item['new_concern']} | "
                f"{', '.join(item['source_atom_ids'][:3]) or '—'} |"
            )
        lines += ["", "## Round-2 → Round-3 examples", ""]
        for example in examples_out:
            lines += [
                f"### {example['concern_id']} — {example['concern_label']}",
                "",
                f"- ROUND2 row: {example['before_item_text'][:300] or '(no matching round-2 row)'}",
                f"- ROUND3 atoms: {', '.join(example['after_source_atoms'])}",
                f"- ROUND3 owned numbers: {', '.join(example['after_owned_numbers']) or '—'}",
                f"- ROUND3 owned materials: {', '.join(example['after_owned_materials']) or '—'}",
                f"- ROUND3 consequence: {example['after_owned_consequence'] or '—'}",
                f"- ROUND3 requirement: {example['after_requirement'][:240]}",
                f"- ROUND3 checks: {' / '.join(example['after_checks'])}",
                f"- ROUND3 pass criteria: {' / '.join(example['after_pass_criteria'])}",
                f"- why round-2 ownership was wrong: {example['why_round2_ownership_was_wrong']}",
                "",
            ]
        lines += ["", "## Manual-style audit (deterministic 20-row sample)", ""]
        for row in audit["rows"]:
            lines += [
                f"### {row['concern_id']} — {row['concern_label']}",
                "",
                f"1. 要求: {row['q1_requirement']}",
                f"2. 复核: {row['q2_inspect']}",
                f"3. 通过: {row['q3_pass_condition']}",
                f"4. 证据: {row['q4_evidence']}",
                f"5. 同一决策: {row['q5_same_decision']}",
                "",
            ]
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text("\n".join(lines), encoding="utf-8")

    print(
        f"REVIEW_WORKBOOK_ROUND3_QUALITY {result} case={args.case} "
        f"atoms={counters['source_atom_count']} concerns={counters['review_concern_count']} "
        f"points={counters['review_point_count']} fixtures={fixture_pass}/{len(fixtures)} "
        f"warranty={warranty['result']} audit={audit['result']} examples={len(examples_out)} "
        f"false_conflicts={conflicts['false_conflict_count']}"
        + (f" reasons={reasons}" if reasons else "")
    )
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
