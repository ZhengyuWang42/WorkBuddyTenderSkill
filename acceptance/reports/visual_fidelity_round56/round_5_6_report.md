# Round 5.6 Source Visual Fidelity Report

Automated status: **AUTOMATED_VISUAL_PRECHECK_FAILED**

> This is an automated visual pre-check measured on rendered source and
> generated pages. It is not a visual acceptance. Final visual acceptance
> belongs to the human Microsoft Word inspection.

## Round 5.5 manual baseline

`ROUND_5_5_MANUAL_VISUAL_ACCEPTANCE = FAILED` (human Word inspection).

## case_001

- render: OK
- generated pages: 22
- automated visual pre-check: FAILED
  - lost_source_blank_count = 54
  - invented_blank_count = 26
  - section_margin_mismatch_count = 6
  - usable_text_width_mismatch_count = 6
  - quotation_total_blank_loss_count = 8
  - quotation_signature_blank_loss_count = 4
- blanks: lost=54 invented=26 kind_mismatch=0
- geometry: left_delta_median=0.0 right_delta_median=None
- typography mismatches: 0
- quotation blank loss: total=8 signature=4

## case_002

- render: OK
- generated pages: 43
- automated visual pre-check: FAILED
  - lost_source_blank_count = 38
  - invented_blank_count = 19
  - section_margin_mismatch_count = 17
  - usable_text_width_mismatch_count = 17
- blanks: lost=38 invented=19 kind_mismatch=0
- geometry: left_delta_median=6.43 right_delta_median=None
- typography mismatches: 0
- quotation blank loss: total=0 signature=0

## case_003

- render: OK
- generated pages: 35
- automated visual pre-check: FAILED
  - lost_source_blank_count = 61
  - invented_blank_count = 12
  - section_margin_mismatch_count = 14
  - usable_text_width_mismatch_count = 14
- blanks: lost=61 invented=12 kind_mismatch=0
- geometry: left_delta_median=0.0 right_delta_median=None
- typography mismatches: 0
- quotation blank loss: total=0 signature=0

## Tests and validation

- targeted_round56_tests: PASS - tests/test_round56_source_visual_fidelity.py (14 tests, includes 3 production-run regressions)
- regression_subset: PASS - tests/test_round46_form_layout.py, tests/test_round47_paragraph_native.py, tests/test_source_format_fidelity.py, tests/test_word_safe_builder.py (69 tests total in the run, rc 0)
- intentional_contract_change: tests/test_round46_form_layout.py::test_visible_pdf_rule_becomes_word_bottom_rule_and_plain_empty_stays_plain now asserts a continuous underlined Word run (Round 5.6 blank representation) instead of an underscore tab leader
- git_diff_check: rc 0 (CRLF warnings only)
- python_docx_reopen: PASS for all three produced DOCX files
- docx_package_integrity: PASS - ZIP CRC integrity, required parts present, no unsafe OOXML (txbxContent/v:shape) parts
- xlsx_reopen: PASS for all three produced workbooks
- libreoffice_render: PASS - rendered with -env:UserInstallation under isolated per-case profiles
- visual_acceptance: NOT AUTOMATED - final visual acceptance belongs to the human Microsoft Word inspection
