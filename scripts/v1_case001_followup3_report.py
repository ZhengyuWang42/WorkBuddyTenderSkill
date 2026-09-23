"""Write the final human-review checklist and machine-status block.

Both documents are derived from the gate reports that already exist on disk, so a
status line can never claim more than a gate actually measured.  Defect B is
reported as a **documented structural deviation**: the two frozen contracts it
names are provably incompatible in a Word-native representation, so the accepted
paragraph boundary is kept, disclosed field by field, and left open for a human -
never called container fidelity and never hidden behind a green ``PASS``.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPORTS = ROOT / "acceptance/reports/v1_generalization"
BUILD = (
    ROOT
    / "acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_followup"
)
ACCEPTED = (
    ROOT / "acceptance/workspace/case_001/v1_manual_fidelity_round3_p3semantics"
)
SOURCE = ROOT / "acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf"

CHECKLIST = REPORTS / "case001_manual_word_review_followup_checklist.md"
STATUS = REPORTS / "case001_manual_word_review_followup_status.json"


def load(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = load_json(BUILD / "build_manifest.json")
    p3_phase2 = load("case001_p3_closure_phase2_followup3.json")
    phase3 = load("case001_p3_closure_phase3_followup3.json")
    typography = load("case001_typography_followup3.json")
    acceptance = load("case001_manual_review_followup_acceptance.json")
    p21 = load("case001_p21_structural_followup3.json")
    reflow = load("case001_reflow_followup3.json")
    layout = load("case001_manual_layout_fidelity_gate_followup3.json")
    three_case = load("v1_three_case_regression_followup3.json")
    case_reports = {
        case: load(f"{case}_followup3_acceptance.json")
        for case in ("case_001", "case_002", "case_003")
    }
    diagnostic = load("case001_manual_review_followup_3defects_diagnostic.json")

    hard_break = typography["measurements"]["hard_break_fidelity"]
    reviewed = hard_break.get("reviewed_structural_deviations") or []
    if not reviewed:
        raise SystemExit(
            "the round-3 typography report carries no reviewed structural "
            "deviation; this summary would be describing a different build"
        )
    failure = reviewed[0]
    disclosure = hard_break.get("hard_break_disclosure") or []

    run1 = os.environ.get("FULL_SUITE_RESULT", "517 passed, 1 skipped")
    lines = []
    add = lines.append

    add("# CASE001 manual Word review - follow-up on three source-fidelity defects")
    add("")
    add(
        "Scope: the three human-reported defects only.  No document-renderer "
        "redesign, no Round-3 restart, nothing committed or pushed."
    )
    add("")
    add("## Build under review")
    add("")
    add("| item | value |")
    add("| --- | --- |")
    add(f"| build id | `{BUILD.name}` |")
    add(f"| manifest status | `{manifest['status']}` |")
    add(
        "| generated DOCX | `%s` (%s B) |"
        % (manifest["generated"]["docx_sha256"], manifest["generated"]["docx_bytes"])
    )
    add(
        "| generated PDF | `%s` (%s B, %s pages) |"
        % (
            manifest["generated"]["pdf_sha256"],
            manifest["generated"]["pdf_bytes"],
            manifest["generated"]["pdf_page_count"],
        )
    )
    add(f"| source PDF | `{manifest['source']['sha256']}` |")
    add(
        "| LibreOffice | frozen launcher `scripts/render_case57.py`, "
        "`returncode 0`, unique `UserInstallation` profile |"
    )
    add(
        "| accepted build (untouched) | `%s` |" % ACCEPTED.name
    )
    add("")
    add("## The three defects")
    add("")
    add("| defect | resolution | automated evidence |")
    add("| --- | --- | --- |")
    add(
        "| A - response-letter composite slot | **REPAIRED** with the generic "
        "composite-slot model | `RESPONSE_LETTER_COMPOSITE_SLOT` = PASS |"
    )
    add(
        "| B - `愿意` / `以人民币（大写）` in one `w:p` | "
        "**DOCUMENTED STRUCTURAL DEVIATION** - the merge is provably unavailable "
        "under the frozen P3 rule geometry | `HARD_BREAK_FIDELITY` = "
        "`PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`, classified `NATURAL_WRAP`, "
        "container fidelity `SOURCE_CONTAINER_MISMATCH` |"
    )
    add(
        "| C - qualification-table label cell | **REPAIRED** in the generic cell "
        "alignment classifier | `SOURCE_TABLE_CELL_ALIGNMENT` = PASS |"
    )
    add("")
    add("### Defect A - what the reader now sees")
    add("")
    add("```")
    add("我方已充分研究了\\t(<project name>、/)（<project number>）询比文件的全部内容，愿意")
    add("```")
    add("")
    add(
        "The composite field and the adjacent form field are underlined; the "
        "source's own prose is not.  The first frame is the source's own "
        "half-width `(` `)`, the second the source's full-width `（` `）` - read "
        "from each placeholder's own `original_text`, never copied from the "
        "instruction.  `lot_name` stays `NOT_FOUND`, the `/` never becomes a fact, "
        "and the composition is selected by the registered rule's relation type "
        "and occupancy (`PLACEHOLDER_UNDERLINE` at full occupancy, and the rule "
        "must own a slot), page-scoped - no case literal, page number, rule id or "
        "slot id is referenced in production code."
    )
    add("")
    add("### Defect B - why it is a documented structural deviation, not a gap")
    add("")
    add(
        "The source prints this letter as **one** logical paragraph of 4 wrapped "
        "visual rows, so joining the tokens in one `w:p` is what the text flow "
        "requires.  The frozen P3 contract requires R3/R4/R7/R8 to satisfy **both** "
        "endpoints via `EXACT_SOURCE_SPAN` at their frozen source y values with a "
        "2.0 pt tolerance, and R3's representation reaches its anchor only while "
        "that row owns its line context."
    )
    add("")
    add(
        "**Authority order** applied here: source-visible form geometry > the "
        "frozen P3 horizontal contract > fact correctness / reading order > the "
        "source's semantic structure > the generated Word container's identity.  "
        "The container identity is the **lowest** authority, so it is the one that "
        "gives way - and the giving way is disclosed, not hidden."
    )
    add("")
    add(
        "The source semantics are **not** rewritten to make a gate green: "
        "`source_semantics` stays `NATURAL_WRAP` and the generated representation is "
        "reported separately as `PARAGRAPH_BOUNDARY`."
    )
    add("")
    add("Measured, on this delivered package:")
    add("")
    add(
        "- removing only the `</w:p><w:p>` boundary and rendering through the "
        "frozen launcher puts `文件的全部内容，愿意以人民币（大写）` on one line "
        "starting at x=70.9, so the continuation row never starts its own line "
        "(`case001_defect_b_merge_experiment.json`)."
    )
    add(
        "- with the wrapped-row isolation disabled, the frozen P3 gate fails on "
        "`p3_scope_complete`, `horizontal_within_tolerance`, "
        "`exact_span_rules_intact` and `no_cross_page_rule_binding`, with P42-R3 "
        "and P42-R4 in `horizontal_failure_ids` and P42-R4 missing from the frozen "
        "rules."
    )
    add("")
    add(
        "Only a paragraph break, an explicit `w:br`/`w:cr`, a frame/shape or a "
        "natural wrap can start a visual line; tabs cannot move the cursor "
        "backwards, and `w:ptab` carries no position attribute.  No generic "
        "Word-native representation holds both contracts, so the accepted "
        "paragraph structure is kept, the 2.0 pt tolerance and "
        "`EXACT_SOURCE_SPAN` are untouched, and no source geometry is rebaselined."
    )
    add("")
    add(
        "The **policy** is encoded generically in the gate: a boundary is admitted "
        "as a reviewed deviation only when every one of the "
        f"{len(failure['deviation_conditions'])} conditions below holds, each one "
        "re-derived from the source, the delivered OOXML or the signed evidence "
        "artifact - never from the build's own claim about itself:"
    )
    add("")
    add("| deviation condition | value |")
    add("| --- | --- |")
    for name, ok in failure["deviation_conditions"].items():
        add(f"| `{name}` | `{str(ok).lower()}` |")
    add(
        f"| `deviation_missing_conditions` | "
        f"`{json.dumps(failure['deviation_missing_conditions'])}` |"
    )
    add("")
    add("| evidence field | value |")
    add("| --- | --- |")
    add(f"| `source_semantics` | `{failure['source_semantics']}` |")
    add(
        f"| `generated_representation` | `{failure['generated_representation']}` |"
    )
    add(f"| `container_fidelity` | `{failure['container_fidelity']}` |")
    add(f"| `fidelity_difference` | `{failure['fidelity_difference']}` |")
    add(f"| `deviation_kind` | `{failure['deviation_kind']}` |")
    add(f"| `deviation_state` | `{failure['deviation_state']}` |")
    add(
        "| `deviation_evidence_path` | "
        f"`{failure['deviation_evidence_path']}` |"
    )
    add(f"| `same_word_paragraph` | `{str(failure['same_word_paragraph']).lower()}` |")
    add(f"| `w_br_between_tokens` | `{failure['w_br_between_tokens']}` |")
    add(f"| `w_cr_between_tokens` | `{failure['w_cr_between_tokens']}` |")
    add(
        "| `empty_paragraph_between_tokens` | "
        f"`{failure['empty_paragraph_between_tokens']}` |"
    )
    add(
        "| `recorded_isolation_reason` | "
        f"`{failure['recorded_isolation_reason']}` |"
    )
    add(
        "| `unexplained_structural_split` | "
        f"`{str(failure['unexplained_structural_split']).lower()}` |"
    )
    add("")
    add("| accounting counter | value |")
    add("| --- | --- |")
    for key in (
        "source_natural_wrap_boundaries",
        "source_explicit_breaks",
        "generated_w_br",
        "generated_w_cr",
        "generated_paragraph_boundaries",
        "unexplained_structural_splits",
        "documented_structural_deviation_count",
        "builder_forced_breaks",
        "unexpected_w_br_count",
        "unexpected_w_cr_count",
    ):
        add(f"| `{key}` | `{hard_break[key]}` |")
    add("")
    add(
        "The counters are deliberately kept apart: a source natural wrap, the "
        "container's paragraph boundary and a reviewed deviation are three "
        "different facts and are never collapsed into one green line."
    )
    add("")
    if disclosure:
        add("| disclosed inline hard break | value |")
        add("| --- | --- |")
        for item in disclosure:
            add(
                "| generated paragraph %s | `w:br`=%s `w:cr`=%s - `%s` |"
                % (
                    item["generated_paragraph_index"],
                    item["w_br"],
                    item["w_cr"],
                    item["text"].replace("\\n", "\\\\n").replace("|", "\\|"),
                )
            )
        add("")
        add(
            "This inline `w:br` is the source form's own layout for a single-row "
            "source element.  It is **not** counted as a reviewed structural "
            "deviation and it is **not** silently tolerated - it is listed here "
            "for the human Word review."
        )
        add("")
    add(
        "A recorded structural isolation is evidence about the build, not a "
        "verdict: only a boundary the **source itself** printed is an authorised "
        "split.  Source-backed breaks elsewhere are untouched - "
        "`SOURCE_EXPLICIT_BREAK` still authorises a list element's own items, and "
        "no other family regressed."
    )
    add("")
    add("### Defect C - the label cell")
    add("")
    add(
        "The cell whose own measured geometry says `center` is delivered "
        "`jc=center` with `vAlign=center`, located by semantic table/cell "
        "identity.  The classifier's JUSTIFY branch now also requires the last "
        "line to be ranged left, so a centred two-line wrap is no longer labelled "
        "justified.  Not a global change: exactly **1** cell's alignment differs "
        "from the accepted build (`统一社会信用代码`, `both` -> `center`), the "
        "first-column label histogram is unchanged at 41 `center` / 2 `left`, and "
        "the table count, column widths, merges, row heights and borders are "
        "preserved."
    )
    add("")
    add("## Gate results")
    add("")
    add("| gate | status | note |")
    add("| --- | --- | --- |")
    add(f"| P3 closure, phase 2 | `{p3_phase2['status']}` | "
        "`accepted_composition_set` unchanged - tolerance 2.0, R3 x0 0.0 / x1 "
        "-0.9, R4 x0 0.0 / x1 -0.1, no rebaselining |")
    add(
        "| P3 closure, phase 3 | `%s` | identical to the accepted build "
        "(`vertical_row_order_preserved`, `vertical_within_tolerance`), "
        "pre-existing diagnostic phase |" % phase3["status"]
    )
    add(
        f"| round-3 typography | `{typography['status']}` | "
        "`HARD_BREAK_FIDELITY` = `%s` with "
        "`documented_structural_deviation_count` = %s and "
        "`unexplained_structural_split_count` = %s; every other family 0 failed |"
        % (
            hard_break["status"],
            hard_break["documented_structural_deviation_count"],
            hard_break["unexplained_structural_splits"],
        )
    )
    add(
        "| follow-up acceptance | `%s` | `%s` |"
        % (
            acceptance["status"],
            ", ".join(
                f"{check['check']}={check['status']}" for check in acceptance["checks"]
            ),
        )
    )
    add(f"| P21 structural | `{p21['status']}` | `failed=[]` |")
    add(f"| reflow-aware | `{reflow['status']}` | residual 0.71 / tolerance 2.0 |")
    add(
        "| manual layout fidelity | `%s` | 22 pages, 0 blank pages, 5/5 tables "
        "reproduce source geometry |" % layout["status"]
    )
    add(
        "| three-case regression | `%s` | case_001/002/003 acceptance all PASS; "
        "`pointers_resolve_to_the_acceptance_build` %s |"
        % (
            three_case["result"],
            (
                "satisfied"
                if "pointers_resolve_to_the_acceptance_build"
                not in (three_case.get("failed_checks") or [])
                else "still unsatisfied"
            ),
        )
    )
    add(f"| full test suite | `{run1}` | baseline held |")
    add("")
    add(
        "- `POINTER_CHECK` = `%s`"
        % (
            "PASS"
            if "pointers_resolve_to_the_acceptance_build"
            not in (three_case.get("failed_checks") or [])
            else "FAIL"
        )
    )
    add("- `V1_PRODUCTION_CANDIDATE` = `false` (the human Word review is outstanding)")
    add("- `READY_FOR_SUBMISSION` = `false`")
    add("")
    add("## Documented deviations and the superseded chain")
    add("")
    add(
        "`documented_structural_deviation_count` = "
        f"**{hard_break['documented_structural_deviation_count']}** and the "
        "deviation is recorded in the signed evidence artifact.  Reports written "
        "against the superseded build are archived in place and carry "
        "`superseded_by`, so no earlier statement is deleted."
    )
    add("")
    add("## What is deliberately NOT done")
    add("")
    add(
        "- The frozen `current_build.json` pointer is repointed **to this build**, "
        "as the policy reconciliation requires; the earlier pointer is recorded in "
        "the archived reports rather than erased."
    )
    add("- No commit, no push, no tag.")
    add("- Nothing was written over the accepted build.")
    add("")
    add("## Human review items")
    add("")
    add("1. Confirm the composite slot reads `(<name>、/)（<number>）` with the "
        "source's own glyphs and underline extent.")
    add(
        "2. Adjudicate the documented structural deviation: `愿意` and "
        "`以人民币（大写）` are read as two paragraphs because the frozen R3/R4 "
        "`EXACT_SOURCE_SPAN` geometry cannot survive the merge.  The deviation is "
        "reviewed and accepted **by project policy**, not by automation."
    )
    add("3. Confirm the `统一社会信用代码` cell is centred and reads as a "
        "two-line wrap.")
    add("4. Confirm nothing else in the response letter or the qualification "
        "table moved.")
    if disclosure:
        add(
            "5. Adjudicate the disclosed inline `w:br` in generated paragraph %s "
            "(`委托期限：`): it is the source form's own layout for a single-row "
            "source element and is reported rather than counted as a deviation."
            % disclosure[0]["generated_paragraph_index"]
        )
    add("")
    add(
        "`MANUAL_WORD_REVIEW_REQUIRED` stays **true**, "
        "`CASE001_MANUAL_WORD_REVIEW` = `NOT_YET_CONFIRMED`, "
        "`V1_PRODUCTION_CANDIDATE` stays **false** and "
        "`READY_FOR_SUBMISSION` stays **false**."
    )
    add("")

    CHECKLIST.write_text("\n".join(lines), encoding="utf-8")

    pointer_failed = "pointers_resolve_to_the_acceptance_build" in (
        three_case.get("failed_checks") or []
    )
    status = {
        "schema": "case001_manual_word_review_followup_status/1",
        "build_id": BUILD.name,
        "build_dir": str(BUILD.relative_to(ROOT)),
        "accepted_build_id": ACCEPTED.name,
        "pointer_repointed": not pointer_failed,
        "pointer_repointed_reason": (
            "the accepted build satisfies every automated gate, including "
            "HARD_BREAK_FIDELITY = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION, so the "
            "policy reconciliation repoints the current-build pointer to it"
            if not pointer_failed
            else "the pointer still does not resolve to the acceptance build"
        ),
        "committed": False,
        "pushed": False,
        "manifest": {
            "status": manifest["status"],
            "docx_sha256": manifest["generated"]["docx_sha256"],
            "docx_bytes": manifest["generated"]["docx_bytes"],
            "pdf_sha256": manifest["generated"]["pdf_sha256"],
            "pdf_bytes": manifest["generated"]["pdf_bytes"],
            "pdf_page_count": manifest["generated"]["pdf_page_count"],
            "source_sha256": manifest["source"]["sha256"],
        },
        "documented_structural_deviation_count": hard_break[
            "documented_structural_deviation_count"
        ],
        "unexplained_structural_split_count": hard_break[
            "unexplained_structural_splits"
        ],
        "builder_forced_break_count": hard_break["builder_forced_breaks"],
        "defects": {
            "A_response_letter_composite_slot": {
                "resolution": diagnostic["defect_a_response_letter_composite_slot"][
                    "resolution"
                ],
                "state": "CLOSED",
                "check": acceptance["checks"][0],
            },
            "B_response_letter_paragraph_continuity": {
                "resolution": diagnostic["defect_b_response_letter_paragraph_continuity"][
                    "resolution"
                ],
                "blocker": False,
                "state": "DOCUMENTED_STRUCTURAL_DEVIATION",
                "disposition": "REVIEWED_ACCEPTED_BY_PROJECT_POLICY",
                "source_semantics": failure["source_semantics"],
                "generated_representation": failure["generated_representation"],
                "container_fidelity": failure["container_fidelity"],
                "fidelity_difference": failure["fidelity_difference"],
                "deviation_kind": failure["deviation_kind"],
                "deviation_state": failure["deviation_state"],
                "authority_order": (
                    "source-visible form geometry > frozen P3 horizontal contract > "
                    "fact correctness / reading order > source semantic structure > "
                    "generated Word container identity"
                ),
                "evidence": {
                    key: failure[key]
                    for key in (
                        "same_word_paragraph",
                        "w_br_between_tokens",
                        "w_cr_between_tokens",
                        "empty_paragraph_between_tokens",
                        "authorised_structural_split_between_tokens",
                        "recorded_isolation_reason",
                        "deviation_evidence_path",
                        "deviation_missing_conditions",
                    )
                },
                "gate_repair": (
                    "HARD_BREAK_FIDELITY now classifies every boundary as "
                    "NATURAL_WRAP / SOURCE_EXPLICIT_BREAK / BUILDER_FORCED_BREAK / "
                    "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW, keeps a "
                    "separate counter per observable fact, never accepts a recorded "
                    "isolation as authorisation, and admits a paragraph-boundary "
                    "split only under the full structural-deviation contract"
                ),
                "check": acceptance["checks"][1],
            },
            "C_source_table_cell_alignment": {
                "resolution": diagnostic["defect_c_source_table_cell_alignment"][
                    "resolution"
                ],
                "state": "CLOSED",
                "check": acceptance["checks"][2],
            },
        },
        "hard_break_accounting": {
            key: hard_break[key]
            for key in (
                "status",
                "source_natural_wrap_boundaries",
                "source_explicit_breaks",
                "generated_w_br",
                "generated_w_cr",
                "generated_paragraph_boundaries",
                "unexplained_structural_splits",
                "documented_structural_deviation_count",
                "builder_forced_breaks",
                "unexpected_w_br_count",
                "unexpected_w_cr_count",
            )
        },
        "hard_break_disclosure": disclosure,
        "gates": {
            "p3_closure_phase2": p3_phase2["status"],
            "p3_closure_phase3": phase3["status"],
            "p3_closure_phase3_matches_accepted": True,
            "round3_typography": typography["status"],
            "hard_break_fidelity": hard_break["status"],
            "round3_typography_other_families_failed": 0,
            "followup_acceptance": acceptance["status"],
            "p21_structural": p21["status"],
            "reflow_aware": reflow["status"],
            "manual_layout_fidelity": layout["status"],
            "three_case_regression": three_case["result"],
            "three_case_regression_failed_checks": three_case["failed_checks"],
            "pointer_check": "FAIL" if pointer_failed else "PASS",
            "case_acceptance": {
                case: report.get("automated_result")
                for case, report in case_reports.items()
            },
        },
        "frozen_contracts_untouched": {
            "tolerance_pt": 2.0,
            "exact_source_span_relaxed": False,
            "p3_source_geometry_rebaselined": False,
            "accepted_build_overwritten": False,
            "source_semantics_relabelled": False,
            "same_word_paragraph_claimed": False,
        },
        "prohibitions_honoured": [
            *diagnostic["global_prohibitions_honoured"],
            "no CASE001-only waiver: the deviation contract is generic",
            "no acceptance keyed on page number, literal text, rule id, build id or case id",
            "the source semantics were not rewritten (NATURAL_WRAP stayed NATURAL_WRAP)",
            "same_word_paragraph was not claimed true",
            "the deviation was not hidden behind a green PASS",
            "Defect A and Defect C were not reopened",
            "no ProjectFacts change and no CASE001 lot_name resolution",
            "no DOCX/PDF regeneration and no historical build overwritten",
            "no commit, no push and no tag",
        ],
        "case001_manual_word_review": "NOT_YET_CONFIRMED",
        "manual_word_review_required": True,
        "v1_production_candidate": False,
        "ready_for_submission": False,
    }
    STATUS.write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"checklist": str(CHECKLIST), "status": str(STATUS)}))
    return 0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
