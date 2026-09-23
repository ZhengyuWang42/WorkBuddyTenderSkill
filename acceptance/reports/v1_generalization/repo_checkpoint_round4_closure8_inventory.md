# Round-4 closure8 repository checkpoint inventory

Generated read-only from `git diff --name-status`, `git ls-files --others
--exclude-standard` and `git diff --cached --name-status` at
`HEAD = 8de9e1f343a6643e11ea5c6c8e1df015dda123a5`.

* paths Git can see: **267** (tracked-modified **35**, untracked **232**, staged **0**)
* staged for this checkpoint: **267**
* intentionally kept out of Git: **0**

## Classification summary

| classification | paths | staged |
| --- | --- | --- |
| `TRACK_ACCEPTANCE_EVIDENCE` | 202 | yes |
| `TRACK_CANONICAL_DOC` | 2 | yes |
| `TRACK_GATE_OR_SCRIPT` | 29 | yes |
| `TRACK_POINTER_OR_MANIFEST` | 3 | yes |
| `TRACK_PRODUCT` | 16 | yes |
| `TRACK_TEST` | 15 | yes |

No path classified `OBSOLETE_DUPLICATE`: superseded gate reports and
superseded pointers are *historical evidence* (`*_superseded_by_*`), which
the project keeps and links to its successor rather than deleting.

## Local artifact classes deliberately excluded (present on disk, ignored by Git)

| class | files | bytes |
| --- | --- | --- |
| `LOCAL_BUILD_ARTIFACT  acceptance/workspace/` | 27427 | 4274659841 |
| `PRIVATE_SOURCE  acceptance/private/` | 3 | 4046694 |
| `LOCAL_TEST_TEMP  tmp/` | 15201 | 515897025 |
| `LOCAL_TEST_TEMP  _r2tmp/` | 0 | 0 |

These trees are left untouched on disk: the round-by-round build history and
the private source corpus are the acceptance record, and the checkpoint does
not delete or rewrite them.

## Per-path classification

| path | git state | classification | stage | reason |
| --- | --- | --- | --- | --- |
| `acceptance/evidence/structural_deviations/response_letter_natural_wrap_boundary.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | structural-deviation evidence contract |
| `acceptance/reports/v09_internal_preview/case001_v09_internal_preview_gate.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v09_internal_preview/current_build.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v09_internal_preview/ownership_closure_gate.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v09_internal_preview/ownership_closure_gate_v1_manual_layout_closure.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v09_internal_preview/p3_phase2_gate.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v09_internal_preview/p3_reflow_vertical_gate.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v09_internal_preview/source_line_assembly_gate.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v09_internal_preview/v09_full_test_suite.xml` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_acceptance.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_acceptance_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_acceptance_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_composite_execution_binding_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_composite_execution_binding_diagnostic_before_repair.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_intrinsic_spacing_calibration.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_row_round4_closure6.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_row_round4_closure6.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_row_round4_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_row_round4_closure8.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_row_round4_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_row_round4_diagnostic.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_row_round4_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_row_round4_final.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_rule_endpoint_round4_closure6.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_rule_endpoint_round4_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_segment_chain_ledger_closure5.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_date_segment_chain_ledger_closure5.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_defect_b_merge_experiment.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_full_test_suite_final.txt` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_full_test_suite_followup3.txt` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_full_test_suite_round4_closure8.txt` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_full_test_suite_round4_closure8.xml` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_intrinsic_spacer_multisegment_calibration.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_intrinsic_spacer_multisegment_calibration_v2.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_fidelity_round2_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_fidelity_round2_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_fidelity_round2_gate.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_fidelity_round2_progress.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_fidelity_round2_review_checklist.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_layout_closure_audit.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_layout_fidelity.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate_prefix.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_review_followup_3defects_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_review_followup_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_review_followup_acceptance_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_review_followup_acceptance_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_review_p21_followup_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_word_review_final_checklist.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_word_review_final_status.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_word_review_followup_checklist.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_word_review_followup_checklist_superseded_by_round4_date_rhythm_closure8.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_word_review_followup_checklist_superseded_by_unexpected_hardbreak_closure.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_word_review_followup_status.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_word_review_followup_status_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_manual_word_review_followup_status_superseded_by_unexpected_hardbreak_closure.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_ownership_closure.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_ownership_closure_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_ownership_closure_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_ownership_closure_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_ownership_closure_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p21_followup_status.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p21_structural_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p21_structural_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p21_structural_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p21_structural_gate.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p21_structural_gate_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p21_structural_gate_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_phase2.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_phase2_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_phase2_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_phase2_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_phase2_followup3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_phase3_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_phase3_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_phase3_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_probe22.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_probe23.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_round2.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_round3_recon_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_closure_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_r6_semantic_registry_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_reflow_vertical_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_reflow_vertical_round2.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_reflow_vertical_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_reflow_vertical_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_semantic_registry_gate.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_semantic_registry_gate_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p3_semantic_registry_gate_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p6_before_build_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_p6_unexpected_hardbreak_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_frame4.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_postfix.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_prefix.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_round2.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_frame_audit_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_page_table_audit.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_preview_gate.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_quotation_summary_line_pitch_round4.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_reflow_aware_round3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_reflow_aware_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_reflow_aware_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_reflow_aware_v1.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_reflow_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_reflow_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_reflow_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_round2_probe_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_round3_p3_contract_reconciliation.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_round3_p3_contract_reconciliation_diagnostic.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_round3_p3_contract_reconciliation_status.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_round3_p3semantic_reconciliation.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_round3_p3semantic_reconciliation_status.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_round3_typography_probe23.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_line_assembly.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_line_assembly_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_line_assembly_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_line_assembly_round4_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_typography_round3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_typography_round3_baseline.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_typography_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_typography_round3_probe10.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_typography_round3_report.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_source_typography_round3_status.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_cell_line_rhythm_closure7.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_cell_line_rhythm_closure7.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_cell_line_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_cell_line_rhythm_closure8.md` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_geometry.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_geometry_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_geometry_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_geometry_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_geometry_frame5.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_table_geometry_round2.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_typography_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_typography_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_typography_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_typography_followup3_superseded_by_policy_reconciliation.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_probe17.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_probe18.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_probe22.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_probe23.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_probe23_repaired.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_round2.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_round3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_round3_prep3reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_underline_inventory_round3_repaired.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case001_word_center_axis_calibration.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case002_acceptance.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case002_acceptance_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case002_acceptance_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case002_p6_unexpected_hardbreak_row_measure.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case003_acceptance.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case003_acceptance_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_001_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_001_current_build.json` | tracked-modified | `TRACK_POINTER_OR_MANIFEST` | yes | per-case current-build pointer the gates and the three-case regression read |
| `acceptance/reports/v1_generalization/case_001_current_build_superseded_by_policy_reconciliation.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_001_current_build_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_001_current_build_superseded_by_unexpected_hardbreak_closure.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_001_followup3_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_001_round3_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_001_round3_p3semantics_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_002_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_002_current_build.json` | tracked-modified | `TRACK_POINTER_OR_MANIFEST` | yes | per-case current-build pointer the gates and the three-case regression read |
| `acceptance/reports/v1_generalization/case_002_current_build_superseded_by_policy_reconciliation.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_002_current_build_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_002_current_build_superseded_by_unexpected_hardbreak_closure.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_002_followup3_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_002_layout_closure_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_002_round3_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_002_round3_p3semantics_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_003_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_003_current_build.json` | tracked-modified | `TRACK_POINTER_OR_MANIFEST` | yes | per-case current-build pointer the gates and the three-case regression read |
| `acceptance/reports/v1_generalization/case_003_current_build_superseded_by_policy_reconciliation.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_003_current_build_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_003_followup3_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_003_followup3_acceptance_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_003_layout_closure_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_003_round3_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/case_003_round3_p3semantics_acceptance.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/libreoffice_frozen_launcher_canary.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/three_case_generalization.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/three_case_regression.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/three_case_regression_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/v1_automated_candidate_gate.json` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/v1_automated_candidate_gate_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/v1_automated_candidate_gate_round3_reconciled.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/v1_manual_review_checklist.md` | tracked-modified | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/v1_three_case_regression_final.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/v1_three_case_regression_final_superseded_by_round4_date_rhythm_closure8.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/v1_three_case_regression_followup3.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `acceptance/reports/v1_generalization/v1_three_case_regression_round3_p3semantics.json` | untracked | `TRACK_ACCEPTANCE_EVIDENCE` | yes | machine evidence and gate reports for the accepted rounds |
| `docs/V1_DECISIONS.md` | untracked | `TRACK_CANONICAL_DOC` | yes | canonical documentation |
| `docs/V1_PROJECT_STATE.md` | untracked | `TRACK_CANONICAL_DOC` | yes | canonical documentation |
| `scripts/v09_source_line_assembly_gate.py` | tracked-modified | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_case001_final_status.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_case001_followup3_diagnostic.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_case001_followup3_report.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_case001_followup_acceptance.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_case_acceptance.py` | tracked-modified | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_center_axis_and_chain_calibration.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_composite_execution_binding_diagnostic.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_date_intrinsic_spacing_calibration.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_date_row_closure_audit.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_date_row_round4_diagnostic.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_date_segment_chain_ledger.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_intrinsic_spacer_multisegment_probe.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_manual_layout_fidelity_gate.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_manual_review_checklist.py` | tracked-modified | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_manual_review_p21_diagnostic.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_p21_followup_status.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_p21_structural_gate.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_p3_r6_semantic_registry_diagnostic.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_p3_semantic_registry_gate.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_p6_form_line_diagnostic.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_page_frame_audit.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_page_table_geometry_audit.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_reflow_aware_regression.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_round3_p3_reconciliation_diagnostic.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_source_typography_round3_gate.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_structural_deviation_evidence.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_table_cell_line_rhythm_audit.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `scripts/v1_underline_inventory.py` | untracked | `TRACK_GATE_OR_SCRIPT` | yes | gate, audit or diagnostic instrument |
| `tender_basic/composite_semantic_binding.py` | untracked | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/document_parser.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/intrinsic_spacer.py` | untracked | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/page_layout.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/source_fill_policy.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/source_format.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/source_format_qa.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/source_page_frame.py` | untracked | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/source_paragraph_alignment.py` | untracked | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/source_paragraph_indent.py` | untracked | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/source_vertical_rhythm.py` | untracked | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/vertical_reflow_qa.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/vertical_reflow_region.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/word_safe_source_builder.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/word_safe_xml.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tender_basic/word_style_source_builder.py` | tracked-modified | `TRACK_PRODUCT` | yes | production source of the compiler |
| `tests/test_logical_layout.py` | tracked-modified | `TRACK_TEST` | yes | automated test |
| `tests/test_round2_manual_fidelity_defects.py` | untracked | `TRACK_TEST` | yes | automated test |
| `tests/test_round3_source_typography.py` | untracked | `TRACK_TEST` | yes | automated test |
| `tests/test_round46_form_layout.py` | tracked-modified | `TRACK_TEST` | yes | automated test |
| `tests/test_round47_paragraph_native.py` | tracked-modified | `TRACK_TEST` | yes | automated test |
| `tests/test_round4_vii_leading_blank_and_cell_rhythm.py` | untracked | `TRACK_TEST` | yes | automated test |
| `tests/test_round56_source_visual_fidelity.py` | tracked-modified | `TRACK_TEST` | yes | automated test |
| `tests/test_round58_anchored_value_run.py` | tracked-modified | `TRACK_TEST` | yes | automated test |
| `tests/test_round58_form_line_paragraph.py` | tracked-modified | `TRACK_TEST` | yes | automated test |
| `tests/test_round59_source_evidence_generalization.py` | tracked-modified | `TRACK_TEST` | yes | automated test |
| `tests/test_round60_form_line_hard_break.py` | untracked | `TRACK_TEST` | yes | automated test |
| `tests/test_round61_atomic_execution_binding.py` | untracked | `TRACK_TEST` | yes | automated test |
| `tests/test_v1_manual_layout_fidelity_gate.py` | untracked | `TRACK_TEST` | yes | automated test |
| `tests/test_v1_p21_manual_review_followup.py` | untracked | `TRACK_TEST` | yes | automated test |
| `tests/test_v1_p21_structural_gate.py` | untracked | `TRACK_TEST` | yes | automated test |
