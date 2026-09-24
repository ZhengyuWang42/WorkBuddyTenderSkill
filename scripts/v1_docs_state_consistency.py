"""Read-only consistency gate for the V1 current-state documentation.

The durable docs are only useful if they cannot silently drift away from the
artifacts they describe.  This gate cross-checks the *current-state* statements
in

* ``docs/V1_PROJECT_STATE.md``
* ``docs/V1_DECISIONS.md``
* ``acceptance/reports/v1_generalization/v1_manual_review_checklist.md``

against the artifacts those statements are about:

* the CASE001 manual-review status JSON and the build it names,
* the three per-case current-build pointers,
* the three-case regression report,
* the JUnit XML record of the latest full-suite run.

It never writes to the artifacts and never changes a verdict: it reports where
the documentation and the machine state disagree, so a stale claim is caught
rather than trusted.  No page numbers, corpus literals, rule ids or case-specific
exceptions are used; every check is derived from the artifacts.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_docs_state_consistency.py \
        --out acceptance/reports/v1_generalization/v1_docs_state_consistency.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GENERALIZATION = Path("acceptance/reports/v1_generalization")
STATUS_NAME = "case001_manual_word_review_final_status.json"
THREE_CASE_NAME = "v1_three_case_regression_final.json"
CHECKLIST_NAME = "v1_manual_review_checklist.md"
FULL_SUITE_XML = "case001_full_test_suite_round4_closure8.xml"

#: Round-3 review-workbook current-truth evidence.
ROUND3_FINAL_STATUS = "review_workbook_round3_final_status_reconciled.json"
ROUND3_FINAL_STATUS_SUPERSEDED = "review_workbook_round3_final_status.json"
ROUND3_SUITE_XML = "review_workbook_round3_full_test_suite.xml"
ROUND3_GATE = "{case}_review_workbook_gate_round3.json"
ROUND3_QUALITY = "review_workbook_round3_content_quality_{case}.json"
ROUND3_VISUAL = "{case}_review_workbook_visual_qa_round3.json"
ARCHIVED_POINTER_GLOB = "case_*_current_build_superseded_by_*.json"
ROUND3_BUILD_ID = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook3",
    "case_002": "v1_round4_closure8_review_workbook3",
    "case_003": "v1_round4_closure8_review_workbook3",
}

#: Round-4 review-workbook current-truth evidence.  Round 4 supersedes round 3 as
#: the *current* review object (the human reviewed round 3, failed it, and round 4
#: closes the rendered-component provenance defect); the round-3 artifacts above
#: stay frozen and keep being verified as history.
ROUND4_FINAL_STATUS = "review_workbook_round4_final_status.json"
ROUND4_REPORT = "{case}_review_workbook_round4.json"
ROUND4_GATE = "{case}_review_workbook_round4_gate.json"
ROUND4_VISUAL = "{case}_review_workbook_visual_qa_round4.json"
ROUND4_PROVENANCE = "review_workbook_round4_rendered_component_provenance_{case}.json"
ROUND4_SUITE_XML = "review_workbook_round4_full_test_suite.xml"
ROUND4_BUILD_ID = {
    "case_001": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook4",
    "case_002": "v1_round4_closure8_review_workbook4",
    "case_003": "v1_round4_closure8_review_workbook4",
}
ROUND4_INVARIANT = "SEMANTIC OWNERSHIP MUST SURVIVE RENDERING"
ROUND4_MISMATCH_BUCKETS = (
    "rendered_source_requirement_concern_mismatch",
    "rendered_review_check_concern_mismatch",
    "rendered_pass_criterion_concern_mismatch",
    "rendered_failure_consequence_concern_mismatch",
    "rendered_preparation_material_concern_mismatch",
    "rendered_scoring_guidance_concern_mismatch",
    "rendered_numeric_statement_concern_mismatch",
    "rendered_evidence_summary_concern_mismatch",
)

#: Lines of look-back allowed when deciding whether a superseded build id is
#: introduced by a history marker rather than presented as current.
HISTORY_LOOKBACK = 10

#: A deviation may not be described as both uncoordinated and coordinated.
UNCOORDINATED_PATTERNS = (r"尚未[^\n。]{0,24}协调", r"未(?:完全)?协调进")
COORDINATED_PATTERNS = (r"已完全协调进", r"已(?:完全)?协调进门禁")

#: A heading that claims to describe the *current* review object.  Superseded
#: build ids may not appear under such a heading unless the mention itself sits
#: under a history-marked sub-heading.
CURRENT_SECTION_RE = re.compile(
    r"(当前|current)[^\n]{0,24}(复核对象|build under review)", re.IGNORECASE
)

#: A line that asserts a current pointer target.  Such a line may not name a
#: superseded build id without a history marker, whatever section it sits in.
CURRENT_TARGET_RE = re.compile(r"当前[^\n]{0,16}指针目标|指针目标|当前指针")

#: Wording that marks a statement as history rather than current state.
HISTORY_MARKERS = ("历史", "HISTORICAL", "SUPERSEDED", "基线", "baseline", "被取代")

CASES = ("case_001", "case_002", "case_003")

#: Statements that must never appear in a current-state document.
FORBIDDEN_CLAIMS = (
    "READY_FOR_SUBMISSION = true",
    "READY_FOR_SUBMISSION=true",
    "V1_PRODUCTION_CANDIDATE = true",
    "V1_PRODUCTION_CANDIDATE=true",
)

#: A line that *forbids* a claim is not the claim.  D8 exists precisely to say
#: "never assert READY_FOR_SUBMISSION = true", so the prohibition wording is
#: expected and allowed; only an assertion is a defect.
PROHIBITION_MARKERS = ("不得", "禁止", "永不", "绝", "never", "not allowed")


def asserts_claim(text: str) -> list[str]:
    """Forbidden claims that are *asserted* somewhere in ``text``."""

    found = []
    for line in text.splitlines():
        if any(marker in line for marker in PROHIBITION_MARKERS):
            continue
        stripped = re.sub(r"`[^`]*`", "", line)
        for claim in FORBIDDEN_CLAIMS:
            if claim in line and claim in stripped:
                found.append(f"{claim} :: {line.strip()[:120]}")
    return found


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Gate:
    """Collects named checks so the report says what was and was not verified."""

    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.problems: list[str] = []

    def check(self, name: str, ok: bool, **evidence) -> bool:
        entry = {"check": name, "status": "PASS" if ok else "FAIL"}
        entry.update(evidence)
        self.checks.append(entry)
        if not ok:
            self.problems.append(name)
        return ok


def check_build(gate: Gate, status: dict) -> dict:
    build_id = status.get("build_id")
    build_dir = REPO / str(status.get("build_dir", ""))
    manifest_path = build_dir / "build_manifest.json"
    gate.check(
        "documented_build_id_resolves",
        bool(build_id) and manifest_path.is_file(),
        build_id=build_id,
        build_dir=status.get("build_dir"),
    )
    if not manifest_path.is_file():
        return {}
    manifest = load(manifest_path)
    generated = manifest["generated"]
    docx = Path(generated["docx"])
    pdf = Path(generated["pdf"])
    docx_actual = sha256(docx) if docx.is_file() else ""
    pdf_actual = sha256(pdf) if pdf.is_file() else ""
    documented = status.get("manifest", {})
    gate.check(
        "documented_docx_hash_is_the_build_hash",
        docx_actual == generated["docx_sha256"] == documented.get("docx_sha256"),
        recomputed=docx_actual,
        manifest=generated["docx_sha256"],
        documented=documented.get("docx_sha256"),
    )
    gate.check(
        "documented_pdf_hash_is_the_build_hash",
        pdf_actual == generated["pdf_sha256"] == documented.get("pdf_sha256"),
        recomputed=pdf_actual,
        manifest=generated["pdf_sha256"],
        documented=documented.get("pdf_sha256"),
    )
    return {
        "build_id": build_id,
        "docx_sha256": docx_actual,
        "pdf_sha256": pdf_actual,
    }


def check_flags(gate: Gate, status: dict) -> dict:
    flags = {
        "manual_word_review_required": status.get("manual_word_review_required"),
        "case001_manual_word_review": status.get("case001_manual_word_review"),
        "v1_production_candidate": status.get("v1_production_candidate"),
        "ready_for_submission": status.get("ready_for_submission"),
    }
    gate.check(
        "manual_review_still_required",
        flags["manual_word_review_required"] is True,
        **{"manual_word_review_required": flags["manual_word_review_required"]},
    )
    gate.check(
        "case001_manual_word_review_not_confirmed",
        str(flags["case001_manual_word_review"]).upper() == "NOT_YET_CONFIRMED",
        case001_manual_word_review=flags["case001_manual_word_review"],
    )
    gate.check(
        "not_a_production_candidate",
        flags["v1_production_candidate"] is False,
        v1_production_candidate=flags["v1_production_candidate"],
    )
    gate.check(
        "never_ready_for_submission",
        flags["ready_for_submission"] is False,
        ready_for_submission=flags["ready_for_submission"],
    )
    return flags


def check_full_suite(gate: Gate, status: dict) -> dict:
    xml_path = REPO / GENERALIZATION / FULL_SUITE_XML
    recorded = str((status.get("gates") or {}).get("full_suite") or "")
    if not xml_path.is_file():
        gate.check("full_suite_evidence_exists", False, path=str(xml_path))
        return {}
    import xml.etree.ElementTree as ET

    root = ET.parse(xml_path).getroot()
    suite = next(root.iter("testsuite"))
    counts = {
        "tests": int(suite.get("tests")),
        "failures": int(suite.get("failures")),
        "errors": int(suite.get("errors")),
        "skipped": int(suite.get("skipped")),
    }
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    gate.check(
        "full_suite_is_green",
        counts["failures"] == 0 and counts["errors"] == 0,
        **counts,
    )
    pattern = re.compile(
        rf"{counts['passed']} passed,\s*{counts['skipped']} skipped,\s*"
        rf"{counts['failures']} failed,\s*{counts['errors']} errors"
    )
    gate.check(
        "documented_full_suite_count_matches_the_run",
        bool(pattern.search(recorded)),
        documented=recorded,
        evidence_counts=counts,
    )
    return counts


def check_pointers(gate: Gate) -> dict:
    pointers = {}
    regression_path = REPO / GENERALIZATION / THREE_CASE_NAME
    regression = load(regression_path) if regression_path.is_file() else {}
    gate.check(
        "three_case_regression_present_and_pass",
        str(regression.get("result") or regression.get("status") or "").startswith("PASS")
        or regression.get("result") == "PASS",
        result=regression.get("result") or regression.get("status"),
    )
    for case in CASES:
        pointer_path = REPO / GENERALIZATION / f"{case}_current_build.json"
        if not pointer_path.is_file():
            gate.check(f"{case}_pointer_exists", False, path=str(pointer_path))
            continue
        pointer = load(pointer_path)
        build_dir = Path(pointer["build_dir"])
        docx = Path(pointer["generated_docx"])
        pdf = Path(pointer["generated_pdf"])
        docx_ok = docx.is_file() and sha256(docx) == pointer["generated_docx_sha256"]
        pdf_ok = pdf.is_file() and sha256(pdf) == pointer["generated_pdf_sha256"]
        gate.check(
            f"{case}_pointer_hashes_match_its_build",
            docx_ok and pdf_ok,
            build_id=pointer.get("build_id"),
            build_dir_exists=build_dir.is_dir(),
            docx_ok=docx_ok,
            pdf_ok=pdf_ok,
        )
        pointers[case] = {
            "build_id": pointer.get("build_id"),
            "docx_sha256": pointer.get("generated_docx_sha256"),
            "pdf_sha256": pointer.get("generated_pdf_sha256"),
        }
    return pointers


def check_docs(gate: Gate, state_text: str, decisions_text: str, checklist_text: str) -> dict:
    state = REPO / "docs/V1_PROJECT_STATE.md"
    decisions = REPO / "docs/V1_DECISIONS.md"
    gate.check(
        "current_state_docs_exist",
        state.is_file() and decisions.is_file(),
        state=str(state),
        decisions=str(decisions),
    )
    asserted = asserts_claim(state_text) + asserts_claim(decisions_text)
    gate.check(
        "forbidden_readiness_claims_absent",
        not asserted,
        forbidden=list(FORBIDDEN_CLAIMS),
        asserted=asserted,
        note="a line that forbids the claim is not the claim",
    )
    gate.check(
        "state_doc_marks_manual_review_not_confirmed",
        "NOT_YET_CONFIRMED" in state_text,
    )
    gate.check(
        "state_doc_marks_not_ready_for_submission",
        "READY_FOR_SUBMISSION" in state_text and "false" in state_text.lower(),
    )
    gate.check(
        "state_doc_has_the_recovery_map",
        "RECOVERY MAP" in state_text,
    )
    checkboxes = len(re.findall(r"^\s*[-*]\s*\[[xX]\]", checklist_text, flags=re.MULTILINE))
    gate.check(
        "human_review_boxes_unticked",
        checkboxes == 0,
        ticked_boxes=checkboxes,
    )
    return {
        "checked_human_boxes": checkboxes,
        "state_doc_bytes": len(state_text.encode("utf-8")),
        "decisions_doc_bytes": len(decisions_text.encode("utf-8")),
    }


def check_round4_docs(
    gate: Gate, state_text: str, decisions_text: str, checklist_text: str
) -> dict:
    """Round-4 current truth: the rendered workbook must agree with the docs.

    Round 4 supersedes round 3 as the current review object.  The machine state is
    authoritative; the docs are checked *against* it, never the other way round.
    The round-3 object stays frozen and documented as history.
    """

    general = REPO / GENERALIZATION
    final_path = general / ROUND4_FINAL_STATUS
    if not final_path.is_file():
        gate.check("round4_final_status_exists", False, path=str(final_path))
        return {}
    final = load(final_path)
    gate.check(
        "round4_final_status_is_pass",
        str(final.get("result")) == "PASS" and not final.get("blockers"),
        result=final.get("result"),
        blockers=final.get("blockers"),
    )

    cases: dict[str, dict] = {}
    for case in CASES:
        entry: dict[str, object] = {}
        report_path = general / ROUND4_REPORT.format(case=case)
        if report_path.is_file():
            report = load(report_path)
            counts = report.get("rendered_mismatch_counts") or {}
            audit = report.get("final_cell_audit") or {}
            entry["report"] = {
                "verdict": report.get("verdict"),
                "checks": f"{report.get('passed_count')}/{report.get('check_count')}",
                "mismatch_total": report.get("rendered_component_concern_mismatch_total"),
                "unverified": report.get("rendered_component_unverified_count"),
                "audit": f"{audit.get('coherent_cell_count')}/{audit.get('audited_cell_count')}",
            }
            gate.check(
                f"{case}_round4_report_pass",
                report.get("verdict") == "PASS"
                and report.get("failed_checks") == []
                and report.get("rendered_component_concern_mismatch_total") == 0
                and report.get("rendered_component_unverified_count") == 0
                and all(counts.get(bucket) == 0 for bucket in ROUND4_MISMATCH_BUCKETS)
                and int(audit.get("incoherent_cell_count", 1)) == 0,
                **entry["report"],
            )
        else:
            gate.check(f"{case}_round4_report_pass", False, path=str(report_path))

        provenance_path = general / ROUND4_PROVENANCE.format(case=case)
        if provenance_path.is_file():
            provenance = load(provenance_path)
            entry["provenance"] = {
                "components": provenance.get("component_count"),
                "unverified": provenance.get("unverified_count"),
                "cells": provenance.get("cell_count"),
            }
            gate.check(
                f"{case}_round4_provenance_complete",
                bool(provenance.get("component_count"))
                and provenance.get("unverified_count") == 0
                and bool(provenance.get("cells"))
                and bool(provenance.get("workbook_sha256")),
                **entry["provenance"],
            )
        else:
            gate.check(f"{case}_round4_provenance_complete", False, path=str(provenance_path))

        gate_path = general / ROUND4_GATE.format(case=case)
        if gate_path.is_file():
            structure = load(gate_path)
            entry["gate"] = {
                "result": structure.get("result"),
                "passed": structure.get("passed"),
                "check_count": structure.get("check_count"),
            }
            gate.check(
                f"{case}_round4_structure_gate_40_of_40",
                structure.get("result") == "PASS"
                and structure.get("passed") == structure.get("check_count") == 40,
                **entry["gate"],
            )
        else:
            gate.check(f"{case}_round4_structure_gate_40_of_40", False, path=str(gate_path))

        visual_path = general / ROUND4_VISUAL.format(case=case)
        if visual_path.is_file():
            visual = load(visual_path)
            checks = visual.get("checks") or {}
            entry["visual_qa"] = {
                "result": visual.get("result"),
                "bounded_clipping_warnings": (checks.get("clipping_bounded") or {}).get("total"),
                "no_clipped_dashboard_text": (checks.get("no_clipped_dashboard_text") or {}).get("result"),
            }
            gate.check(
                f"{case}_round4_visual_qa_pass",
                visual.get("result") == "PASS"
                and entry["visual_qa"]["no_clipped_dashboard_text"] == "PASS",
                **entry["visual_qa"],
            )
        else:
            gate.check(f"{case}_round4_visual_qa_pass", False, path=str(visual_path))
        cases[case] = entry

    suite_path = general / ROUND4_SUITE_XML
    suite_counts: dict[str, object] = {}
    if suite_path.is_file():
        import xml.etree.ElementTree as ET

        suite = next(ET.parse(suite_path).getroot().iter("testsuite"))
        suite_counts = {
            "collected": int(suite.get("tests", "0")),
            "failures": int(suite.get("failures", "0")),
            "errors": int(suite.get("errors", "0")),
            "skipped": int(suite.get("skipped", "0")),
        }
        suite_counts["passed"] = (
            suite_counts["collected"]
            - suite_counts["failures"]
            - suite_counts["errors"]
            - suite_counts["skipped"]
        )
        gate.check(
            "round4_full_suite_is_green",
            suite_counts["failures"] == 0 and suite_counts["errors"] == 0,
            **suite_counts,
        )
    else:
        gate.check("round4_full_suite_is_green", False, path=str(suite_path))

    # --- documentation agreement ------------------------------------------- #
    gate.check(
        "state_doc_names_the_round4_pipeline",
        "Round4" in state_text
        and ROUND4_INVARIANT in state_text
        and "RenderedReviewComponent" in state_text
        and "review_rendering.py" in state_text
        and "当前轮次" in state_text,
    )
    missing_paths = [
        build_id
        for build_id in ROUND4_BUILD_ID.values()
        if build_id not in state_text or build_id not in checklist_text
    ]
    gate.check("docs_name_the_current_round4_builds", not missing_paths, missing=missing_paths)

    hashes = {
        case: (data.get("workbook_sha256") or "")
        for case, data in (final.get("cases") or {}).items()
    }
    missing_hashes = [
        case
        for case, digest in hashes.items()
        if not digest or digest not in state_text or digest not in checklist_text
    ]
    gate.check("docs_name_the_current_round4_xlsx_hashes", not missing_hashes, missing=missing_hashes)

    gate.check(
        "docs_record_the_round4_suite_counts",
        bool(suite_counts)
        and f"{suite_counts.get('collected')} collected" in state_text
        and f"{suite_counts.get('passed')} passed" in state_text,
        state_has_counts=(
            f"{suite_counts.get('collected')} collected" in state_text
            and f"{suite_counts.get('passed')} passed" in state_text
        ),
        counts=suite_counts,
    )
    gate.check(
        "state_doc_marks_xlsx_review_state",
        "CASE001_XLSX_MANUAL_REVIEW = AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW" in state_text
        and all(
            f"CASE00{index}_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED" in state_text
            for index in (2, 3)
        ),
        note="round 4 may only close the human FAIL as pending-review, never tick a box",
    )
    human_path = general / "case001_review_workbook_round4_human_review.json"
    human = load(human_path) if human_path.is_file() else {}
    gate.check(
        "human_fail_is_preserved_not_rewritten",
        str(human.get("human_verdict", "")).upper() == "FAIL"
        and human.get("fail_reason") == "RENDERED_COMPONENT_CONCERN_OWNERSHIP"
        and human.get("must_not_be_rewritten") is True,
        record=str(human_path),
        human_verdict=human.get("human_verdict"),
        fail_reason=human.get("fail_reason"),
    )
    gate.check(
        "decisions_record_the_rendering_invariant",
        ROUND4_INVARIANT in decisions_text
        and "RenderedReviewComponent" in decisions_text
        and "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW" in decisions_text,
    )
    gate.check(
        "checklist_current_excel_object_is_round4",
        "Round4" in checklist_text
        and all(build_id in checklist_text for build_id in ROUND4_BUILD_ID.values()),
        note="the checklist must point the human at the round-4 workbooks",
    )

    return {"result": "PASS" if not gate.problems else "FAIL", "cases": cases, "suite": suite_counts}


def check_round3_docs(gate: Gate, state_text: str, decisions_text: str, checklist_text: str) -> dict:
    """Round-3 history: the round-3 artifacts stay frozen and documented.

    The round-3 machine state is authoritative; the docs are checked *against* it,
    never the other way round.  A previous round may still be described, but only
    where the sentence is marked as history.
    """

    general = REPO / GENERALIZATION
    final_path = general / ROUND3_FINAL_STATUS
    if not final_path.is_file():
        gate.check("round3_final_status_exists", False, path=str(final_path))
        return {}
    final = load(final_path)
    gate.check(
        "round3_final_status_is_pass",
        str(final.get("result")) == "PASS" and not final.get("blockers"),
        result=final.get("result"),
        blockers=final.get("blockers"),
    )

    cases: dict[str, dict] = {}
    for case in CASES:
        entry: dict[str, object] = {}
        gate_path = general / ROUND3_GATE.format(case=case)
        if gate_path.is_file():
            report = load(gate_path)
            entry["gate"] = {
                "result": report.get("result"),
                "passed": report.get("passed"),
                "check_count": report.get("check_count"),
                "failed": report.get("failed"),
            }
            gate.check(
                f"{case}_round3_structure_gate_40_of_40",
                report.get("result") == "PASS"
                and report.get("passed") == report.get("check_count") == 40
                and report.get("failed") == 0,
                **entry["gate"],
            )
        else:
            gate.check(f"{case}_round3_structure_gate_40_of_40", False, path=str(gate_path))

        quality_path = general / ROUND3_QUALITY.format(case=case)
        if quality_path.is_file():
            quality = load(quality_path)
            counters = quality.get("counters") or {}
            audit = quality.get("human_style_audit") or {}
            conflicts = quality.get("conflicts") or {}
            entry["quality"] = {
                "result": quality.get("result"),
                "fixtures": f"{quality.get('fixtures_passed')}/{quality.get('fixtures_total')}",
                "audit": audit.get("result"),
                "false_conflict_count": conflicts.get("false_conflict_count"),
            }
            gate.check(
                f"{case}_round3_content_quality_pass",
                quality.get("result") == "PASS"
                and quality.get("fixtures_passed") == quality.get("fixtures_total") == 14
                and (quality.get("fixtures_total") or 0) == 14
                and audit.get("coherent_count") == audit.get("sample_size") == 20
                and conflicts.get("false_conflict_count") == 0,
                **entry["quality"],
            )
            gate.check(
                f"{case}_round3_ownership_buckets_empty",
                all(
                    counters.get(key) == 0
                    for key in (
                        "source_concern_mismatch",
                        "numeric_concern_mismatch",
                        "material_concern_mismatch",
                        "consequence_concern_mismatch",
                        "evidence_concern_mismatch",
                        "authority_scope_mismatch",
                        "foreign_role_numeric",
                    )
                ),
                counters={
                    key: counters.get(key)
                    for key in (
                        "source_concern_mismatch",
                        "numeric_concern_mismatch",
                        "material_concern_mismatch",
                        "consequence_concern_mismatch",
                        "evidence_concern_mismatch",
                        "authority_scope_mismatch",
                        "foreign_role_numeric",
                    )
                },
            )
        else:
            gate.check(f"{case}_round3_content_quality_pass", False, path=str(quality_path))

        visual_path = general / ROUND3_VISUAL.format(case=case)
        if visual_path.is_file():
            visual = load(visual_path)
            checks = visual.get("checks") or {}
            entry["visual_qa"] = {
                "result": visual.get("result"),
                "bounded_clipping_warnings": (checks.get("clipping_bounded") or {}).get("total"),
                "no_clipped_dashboard_text": (checks.get("no_clipped_dashboard_text") or {}).get("result"),
            }
            gate.check(
                f"{case}_round3_visual_qa_pass",
                visual.get("result") == "PASS"
                and entry["visual_qa"]["no_clipped_dashboard_text"] == "PASS",
                **entry["visual_qa"],
            )
        else:
            gate.check(f"{case}_round3_visual_qa_pass", False, path=str(visual_path))
        cases[case] = entry

    suite_path = general / ROUND3_SUITE_XML
    suite_counts: dict[str, object] = {}
    if suite_path.is_file():
        import xml.etree.ElementTree as ET

        suite = next(ET.parse(suite_path).getroot().iter("testsuite"))
        suite_counts = {
            "collected": int(suite.get("tests", "0")),
            "failures": int(suite.get("failures", "0")),
            "errors": int(suite.get("errors", "0")),
            "skipped": int(suite.get("skipped", "0")),
        }
        suite_counts["passed"] = (
            suite_counts["collected"] - suite_counts["failures"] - suite_counts["errors"] - suite_counts["skipped"]
        )
        gate.check(
            "round3_full_suite_is_green",
            suite_counts["failures"] == 0 and suite_counts["errors"] == 0 and suite_counts["passed"] == 715,
            **suite_counts,
        )
    else:
        gate.check("round3_full_suite_is_green", False, path=str(suite_path))

    # --- documentation agreement ------------------------------------------- #
    gate.check(
        "state_doc_names_the_round3_pipeline",
        "Round3" in state_text
        and "SourceRequirementAtom" in state_text
        and "ReviewConcern" in state_text
        and "review_concern.py" in state_text
        and "当前轮次" in state_text,
    )
    missing_paths = [
        build_id
        for build_id in ROUND3_BUILD_ID.values()
        if build_id not in state_text and build_id not in checklist_text
    ]
    gate.check(
        "docs_name_the_round3_builds_as_history",
        not missing_paths,
        missing=missing_paths,
        note="round 3 is history; its build ids must still be recorded somewhere in the docs",
    )

    hashes = {
        case: (data.get("workbook_sha256") or "")
        for case, data in (load(final_path).get("cases") or {}).items()
    }
    missing_hashes = [
        case
        for case, digest in hashes.items()
        if not digest or (digest not in state_text and digest not in checklist_text)
    ]
    gate.check("docs_record_the_round3_xlsx_hashes_as_history", not missing_hashes, missing=missing_hashes)

    gate.check(
        "docs_record_the_round3_suite_counts",
        ("716 collected" in state_text or "716 collected" in decisions_text)
        and ("715 passed" in state_text or "715 passed" in decisions_text),
        state_has_counts=("716 collected" in state_text and "715 passed" in state_text),
        decisions_has_counts=("716 collected" in decisions_text and "715 passed" in decisions_text),
    )
    gate.check(
        "state_doc_marks_the_round3_xlsx_review_as_superseded",
        "review_workbook3" in state_text
        and "review_workbook4" in state_text
        and "AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW" in state_text,
    )
    gate.check(
        "state_doc_keeps_history_marked_as_history",
        "历史（HISTORICAL / SUPERSEDED build）" in state_text
        and "历史指针值（HISTORICAL / SUPERSEDED）" in state_text,
    )

    stale: list[str] = []
    for line in state_text.splitlines():
        if ("第 2 轮" not in line and "Round2" not in line) or "当前" not in line:
            continue
        if any(marker in line for marker in HISTORY_MARKERS):
            continue
        stale.append(line.strip()[:140])
    gate.check(
        "no_previous_round_claimed_as_current",
        not stale,
        stale_lines=stale,
        note="a sentence about a previous round may stay only where it is marked as history",
    )

    current_marker = "当前 Excel 复核对象（CURRENT = Round4）"
    history_marker = "历史复核对象（HISTORICAL"
    current_at = checklist_text.find(current_marker)
    history_at = checklist_text.find(history_marker, current_at) if current_at >= 0 else -1
    legacy_at = checklist_text.find("review_workbook1")
    gate.check(
        "checklist_current_excel_object_is_round4",
        current_at >= 0
        and history_at > current_at
        and (legacy_at < 0 or legacy_at > history_at)
        and all(build_id in checklist_text for build_id in ROUND4_BUILD_ID.values()),
        current_marker_at=current_at,
        history_marker_at=history_at,
        first_round1_reference_at=legacy_at,
        note="the current Excel review object is Round4; round-1/2/3 references sit behind history markers",
    )
    gate.check(
        "checklist_has_the_round3_manual_checks",
        all(
            phrase in checklist_text
            for phrase in (
                "每一行 displayed source requirement 与 ReviewConcern 是同一事项",
                "项目质保期 24个月作为 `PROJECT_WARRANTY` 单独核对",
                "5% 质保金比例作为 `RETENTION_MONEY_RATIO` 单独核对",
                "合同付款语境的 12个月作为 `RETENTION_RELEASE_PERIOD` 单独核对",
                "24个月 / 12个月没有被错误报告成同一质保事实冲突",
                "随机抽查至少 20 条 ReviewPoint",
            )
        ),
    )
    gate.check(
        "decisions_record_private_reference_workbooks_as_style_only",
        "acceptance/private/reference_review_workbooks/" in decisions_text
        and "STYLE_ONLY" in decisions_text
        and "HUMAN_WORKFLOW_REFERENCE_ONLY" in decisions_text
        and ("永不提交" in decisions_text or "忽略" in decisions_text),
    )

    # --- current vs historical reconciliation ------------------------------- #
    def _history_context(lines: list[str], index: int) -> bool:
        """Whether the line is explicitly marked (or headed) as history."""

        marked = lambda text: any(marker in text for marker in HISTORY_MARKERS)  # noqa: E731
        if marked(lines[index]):
            return True
        for previous in range(max(0, index - 2), index):
            if marked(lines[previous]):
                return True
        for above in range(index, -1, -1):
            if lines[above].lstrip().startswith("#"):
                return marked(lines[above])
        return False

    def _current_section_spans(lines: list[str]) -> list[tuple[int, int]]:
        """Spans of sections whose heading claims to describe the *current* object."""

        spans: list[tuple[int, int]] = []
        for index, line in enumerate(lines):
            stripped = line.lstrip()
            if not stripped.startswith("#") or not CURRENT_SECTION_RE.search(stripped):
                continue
            level = len(stripped) - len(stripped.lstrip("#"))
            end = len(lines)
            for below in range(index + 1, len(lines)):
                other = lines[below].lstrip()
                if other.startswith("#") and (len(other) - len(other.lstrip("#"))) <= level:
                    end = below
                    break
            spans.append((index, end))
        return spans

    pointers: dict[str, dict] = {}
    for case in CASES:
        pointer_path = general / f"{case}_current_build.json"
        if not pointer_path.is_file():
            continue
        pointer = load(pointer_path)
        pointers[case] = {
            "build_id": pointer.get("build_id"),
            "build_dir": Path(str(pointer.get("build_dir") or "")).name,
            "docx_sha256": pointer.get("generated_docx_sha256"),
            "pdf_sha256": pointer.get("generated_pdf_sha256"),
        }
    current_ids = {str(entry["build_id"]) for entry in pointers.values()}
    superseded_ids: set[str] = set()
    pointer_history: dict[str, list[dict]] = {}
    for archived_path in sorted(general.glob(ARCHIVED_POINTER_GLOB)):
        record = load(archived_path)
        archived_id = record.get("build_id")
        case = archived_path.name.split("_current_build_superseded_by_")[0]
        if archived_id and archived_id not in current_ids:
            superseded_ids.add(str(archived_id))
        pointer_history.setdefault(case, []).append(
            {
                "build_id": archived_id,
                "docx_sha256": record.get("generated_docx_sha256"),
            }
        )

    # A/B/C: the checklist must resolve each case to its live pointer target, and
    # must not present that case's archived build as the current object.
    checklist_lines = checklist_text.splitlines()
    for case, entry in pointers.items():
        stale_assertions = [
            f"{index + 1}: {line.strip()[:110]}"
            for index, line in enumerate(checklist_lines)
            if not _history_context(checklist_lines, index)
            and any(
                archived.get("docx_sha256") and archived["docx_sha256"] in line
                for archived in pointer_history.get(case, [])
            )
        ]
        gate.check(
            f"checklist_current_word_object_matches_{case}_pointer",
            bool(entry["build_id"])
            and entry["build_dir"] in checklist_text
            and entry["docx_sha256"] in checklist_text
            and not stale_assertions,
            pointer_build=entry["build_id"],
            pointer_dir=entry["build_dir"],
            docx_hash_present=entry["docx_sha256"] in checklist_text,
            archived_build_presented_as_current=stale_assertions,
        )

    mislabelled: list[str] = []
    for label, text in (("state", state_text), ("checklist", checklist_text)):
        lines = text.splitlines()
        current_object_lines: set[int] = set()
        for start, end in _current_section_spans(lines):
            current_object_lines.update(range(start, end))
        for index, line in enumerate(lines):
            if not any(superseded in line for superseded in superseded_ids):
                continue
            asserted_current = index in current_object_lines or CURRENT_TARGET_RE.search(line)
            if not asserted_current or _history_context(lines, index):
                continue
            mislabelled.append(f"{label}:{index + 1}: {line.strip()[:120]}")
    gate.check(
        "superseded_build_ids_are_not_current",
        not mislabelled,
        superseded_ids=sorted(superseded_ids),
        mislabelled=mislabelled,
        note="a line that describes the CURRENT review object or pointer target must not "
        "name a superseded build id unless the mention is marked as history",
    )

    # E: a deviation may not be both uncoordinated and coordinated.
    uncoordinated = [
        match.group(0)
        for pattern in UNCOORDINATED_PATTERNS
        for match in re.finditer(pattern, state_text)
    ]
    coordinated = [
        match.group(0)
        for pattern in COORDINATED_PATTERNS
        for match in re.finditer(pattern, state_text)
    ]
    gate.check(
        "deviation_coordination_is_not_self_contradictory",
        not (uncoordinated and coordinated),
        uncoordinated=uncoordinated,
        coordinated=coordinated,
    )

    # F: the current round-3 final status must expose real gate counts, and the
    #    artifact it supersedes must be preserved byte-for-byte.
    recorded_cases = final.get("cases") or {}
    gate.check(
        "current_final_status_covers_every_case",
        all(case in recorded_cases for case in CASES),
        recorded=sorted(recorded_cases),
    )
    for case, data in recorded_cases.items():
        passed = data.get("gate_checks_passed")
        total = data.get("gate_checks_total")
        gate.check(
            f"{case}_current_final_status_exposes_gate_counts",
            isinstance(passed, int) and isinstance(total, int) and passed == total == 40,
            gate_checks_passed=passed,
            gate_checks_total=total,
        )
    superseded_path = general / ROUND3_FINAL_STATUS_SUPERSEDED
    gate.check(
        "current_final_status_records_its_supersession",
        final.get("supersedes") == ROUND3_FINAL_STATUS_SUPERSEDED
        and isinstance(final.get("supersession_reason"), str)
        and bool(final.get("supersession_reason"))
        and superseded_path.is_file()
        and final.get("superseded_artifact_sha256") == sha256(superseded_path),
        supersedes=final.get("supersedes"),
        supersession_reason=final.get("supersession_reason"),
        recorded_sha256=final.get("superseded_artifact_sha256"),
        actual_sha256=sha256(superseded_path) if superseded_path.is_file() else None,
    )

    # G: the checklist's round-3 workbooks must be the final-status authority.
    for case, data in (final.get("cases") or {}).items():
        build_id = Path(str(data.get("build_dir") or "")).name
        digest = data.get("workbook_sha256")
        gate.check(
            f"{case}_round3_workbook_in_checklist_matches_final_status",
            bool(build_id) and build_id in checklist_text and bool(digest) and digest in checklist_text,
            build_id=build_id,
            workbook_sha256=digest,
        )

    return {"cases": cases, "full_suite": suite_counts, "workbook_sha256": hashes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(GENERALIZATION / "v1_docs_state_consistency.json"),
        help="report path (relative paths resolve against the repository root)",
    )
    args = parser.parse_args()

    status_path = REPO / GENERALIZATION / STATUS_NAME
    gate = Gate()
    if not status_path.is_file():
        print(f"missing current-state status: {status_path}", file=sys.stderr)
        return 2
    status = load(status_path)

    build = check_build(gate, status)
    flags = check_flags(gate, status)
    counts = check_full_suite(gate, status)
    pointers = check_pointers(gate)
    state_text = (REPO / "docs/V1_PROJECT_STATE.md").read_text(encoding="utf-8")
    decisions_text = (REPO / "docs/V1_DECISIONS.md").read_text(encoding="utf-8")
    checklist_text = (REPO / GENERALIZATION / CHECKLIST_NAME).read_text(encoding="utf-8")
    docs = check_docs(
        gate,
        state_text,
        decisions_text,
        checklist_text,
    )
    round3 = check_round3_docs(gate, state_text, decisions_text, checklist_text)

    report = {
        "schema": "v1_docs_state_consistency/1",
        "status": "PASS" if not gate.problems else "FAIL",
        "documented_build": build,
        "flags": flags,
        "full_suite": counts,
        "round3": round3,
        "pointers": pointers,
        "docs": docs,
        "checks": gate.checks,
        "failed_checks": gate.problems,
        "note": (
            "read-only: the gate compares the durable docs with the artifacts they "
            "describe and never changes a verdict or an artifact"
        ),
    }
    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out), "status": report["status"], "failed": gate.problems}, ensure_ascii=False))
    return 0 if not gate.problems else 1


if __name__ == "__main__":
    sys.exit(main())
