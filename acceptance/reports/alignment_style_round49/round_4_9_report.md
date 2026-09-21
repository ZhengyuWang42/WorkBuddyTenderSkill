# Round 4.9 Alignment Semantics and Destination Style Inheritance

## ALIGNMENT_ROOT_CAUSE

Round 4.8 classified the project-number block as a form row, then forced every form row through a left-aligned paragraph renderer. The source x-position was reproduced with a 244.8 pt left indent, which substituted positioning for semantic alignment. Round 4.9 classifies short standalone source lines from source geometry and semantic role, emits `CENTERED_FORM_LINE` with native centered paragraph alignment, zero indents, and a fixed-width paragraph-native slot.

## CASE001_PROJECT_NUMBER

- source_alignment: `CENTERED_FORM_LINE`
- generated_alignment: `CENTER`
- source_line_center_x: 292.9195 pt
- source_center_x: 297.6500 pt
- generated_center_x: 297.7360 pt
- center_error: 0.0860 pt
- left_indent: 0.0 pt
- right_indent: 0.0 pt
- first_line_indent: 0.0 pt
- fixed total source width: 185.2391 pt
- fixed slot width: 120.0 pt
- result: PASS

## CASE001_TABLE_PROJECT_NAME

- label_font: 仿宋
- label_size: 12.0 pt
- label_weight: regular
- value_font: 仿宋
- value_size: 12.0 pt
- value_weight: regular
- destination anchor: same-row semantic peer
- style_match: PASS

## COVER_TYPOGRAPHY

- chapter: source `FangSong`, normalized 仿宋, 21.95 pt, flags 4, regular, bbox height 22.4548 pt; rendered 仿宋 class at 21.5 pt, regular
- project_title: source `SimSun`, normalized 宋体, 21.95 pt, flags 4, regular, bbox height 21.95 pt; rendered 宋体 class at 21.5 pt, regular
- document_title: source `FangSong`, normalized 仿宋, 27.95 pt, flags 4, regular, bbox height 28.5929 pt; rendered 仿宋 class at 27.5 pt, regular
- project-number label: source `FangSong`, normalized 仿宋, 12.0 pt, flags 4, regular, bbox height 12.2760 pt; rendered at 12.0 pt, regular

The source PDF spans do not mark these cover roles bold. Round 4.9 therefore preserves regular weight instead of guessing from screenshot appearance.

## FILLED_SLOT_STYLE_AUDIT

- total: 12
- case001: 6
- case002: 6
- case003: 0 because no corresponding facts are resolved
- font_mismatches: 0
- size_mismatches: 0
- weight_mismatches: 0
- alignment_mismatches: 0
- result: PASS

Every fill record reports field, source page, slot role, value, destination expected font and size, actual font and size, weight, alignment, and destination anchor in each case's `filled_slot_style_audit.json`.

## WORKBUDDY_DOCX_SKILL

- available_or_not: NOT_AVAILABLE
- what_was_learned: No local WorkBuddy `office/docx` or `office/pdf` skill was available, so no external implementation practice was extracted.

## PDF2DOCX_BENCHMARK

- available_or_not: NOT_AVAILABLE
- comparison_result: NOT_RUN; `pdf2docx` was not present and Round 4.9 did not install it or change the production runtime.

## WORD_SAFE_REGRESSION

- python-docx reopen: PASS for all three documents
- LibreOffice render: PASS for all three documents
- synthetic layout tables: 0 for all cases
- unsafe OOXML: 0 for all cases
- mid-sentence paragraph breaks: 0 for all cases
- case001 `800m³/h` and `300m³/h` true Word superscript semantics: PASS
- fact-slot semantic typing and fill coverage: PASS
- review-evidence artifacts: byte-identical to Round 4.8

## TRUE_PAGE_COUNT

- case001: source-format pages 22; source sections 22; actual rendered pages 22
- case002: source-format pages 31; source sections 31; actual rendered pages 31
- case003: source-format pages 33; source sections 33; actual rendered pages 33

Counts come from generated DOCX to LibreOffice PDF to PyMuPDF page count. The local LibreOffice 26.2.3 environment renders case002 as 31 pages; a different desktop/upload renderer may paginate differently and remains part of manual acceptance.

## TESTS

- 215 passed
- 1 skipped
- 0 failed
- full suite total: 216

## FILES_CHANGED

- `tender_basic/source_format.py`
- `tender_basic/page_layout.py`
- `tender_basic/word_safe_source_builder.py`
- `tender_basic/word_safe_xml.py`
- `tender_basic/round49_qa.py`
- `scripts/run_round49_alignment_style.py`
- `tests/test_round49_alignment_style.py`
- Round 4.9 workspace, report, render-QA, and manual-test artifacts

## RUN_4_9_OUTPUTS

- `acceptance/workspace/case_001/run_4_9_alignment_style`
- `acceptance/workspace/case_002/run_4_9_alignment_style`
- `acceptance/workspace/case_003/run_4_9_alignment_style`
- `acceptance/manual_word_test_round49/01_case_001.docx`
- `acceptance/manual_word_test_round49/02_case_002.docx`
- `acceptance/manual_word_test_round49/03_case_003.docx`
- `acceptance/reports/alignment_style_round49/benchmark_layout_comparison.md`

## GIT_STATUS

Working tree remains intentionally uncommitted. No commit or release was performed. Round 4.8 and earlier uncommitted changes remain present. No GOLD path was read or created.

## BLOCKERS

No automated blocker remains. Desktop Word normal-open and visual acceptance are pending user confirmation. Cross-renderer pagination variance for case002 should be checked during that manual pass.

Final status: `ROUND_4_9_AWAITING_MANUAL_CONFIRMATION`
