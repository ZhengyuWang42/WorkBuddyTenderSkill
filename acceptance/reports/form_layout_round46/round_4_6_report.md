# Round 4.6 form-layout acceptance report

## BLANK_MODEL_RESULT

`EditableBlank` is the single source-backed blank abstraction. `FormBlock` groups only local related rows, while source-empty rows remain plain. Detected visible rules render as Word bottom borders; inline rules render as underlined figure spaces in the same logical paragraph; date rows retain three independent blanks.

| Case | Detected | Visible rule | Plain empty | NBSP-only | Invisible required | Width error max / median (pt) |
|---|---:|---:|---:|---:|---:|---:|
| case_001 | 68 | 28 | 32 | 0 | 0 | 0.0 / 0.0 |
| case_002 | 65 | 34 | 9 | 0 | 0 | 0.0 / 0.0 |
| case_003 | 54 | 24 | 21 | 0 | 0 | 0.0 / 0.0 |

All three cases satisfy `nbsp_only_placeholder_count = 0` and `invisible_required_blank_count = 0`.

## CASE_001

- `project_number_blank`: PASS; the source-page-40 项目编号 row has a real bottom rule in the generated FormBlock.
- `response_form_blanks`: PASS; source-page-42 plain rows remain plain, while ruled page-44/page-45 fields remain visible.
- `page5_form_alignment`: PASS; related page-44 rows share one FormBlock and zero measured column variance.
- `list_indent_result`: PASS; item 4 and item 6 use a negative first-line indent and continuation QA is 0.01 pt.
- `visual_result`: PASS; LibreOffice rendered the requested pages [1, 3, 5, 6, 8, 9] and comparison PNGs are present.

## CASE_002

- `blank_result`: PASS; visible signature/contact rules are present.
- `list_indent_result`: PASS; items 1–10 share a list group with true hanging indentation.
- `artifact_filter_result`: PASS; geometry rejected 5 source-derived short candidates, with 0 leaking to generated cells; 74 artifact assignments were removed overall.
- `visual_result`: PASS; LibreOffice rendered requested pages [1, 3, 5, 6, 7, 8], including the complex quotation continuation page.

## CASE_003

- `blank_result`: PASS; 投标人、法定代表人、地址 and 电话 source fields preserve their ruled/plain presentation.
- `list_indent_result`: PASS; main clauses and nested （1）–（4） groups have negative first-line indents; continuation QA is 0.025 pt.
- `form_alignment_result`: PASS; signature/date blocks retain shared-grid metrics.
- `visual_result`: PASS; LibreOffice rendered requested pages [2, 4, 6, 7, 10, 30].

## QA_METRICS

| Case | Hanging direction | Continuation x error (pt) | Sibling variance (pt) | Form label variance (pt) | Form value variance (pt) | Row alignment error (pt) | Source / generated visual lines | Wrap delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| case_001 | 0 | 0.01 | 0.0 | 0.0 | 0.0 | 0.0 | 332 / 305 | -27 |
| case_002 | 0 | 0.02 | 0.0 | 0.0 | 0.0 | 0.0 | 830 / 764 | -66 |
| case_003 | 0 | 0.025 | 0.0 | 0.0 | 0.0 | 0.0 | 453 / 478 | 25 |

Required structural gates for every case: `nbsp_only_placeholder_count=0`, `invisible_required_blank_count=0`, `list_hanging_direction_error=0`, `multi_label_form_row_count=0`, `layout_tab_hack=0`, `unsafe_ooxml=0`.

## WORD_SAFE_REGRESSION

| Case | python-docx reopen | Word-safe scan | Unsafe OOXML | LibreOffice render | Facts/review byte-identical | Prior DOCX loaded |
|---|---|---|---:|---|---|---|
| case_001 | PASS | PASS | 0 | PASS | PASS | False |
| case_002 | PASS | PASS | 0 | PASS | PASS | False |
| case_003 | PASS | PASS | 0 | PASS | PASS | False |

## PAGE_COUNTS

| Case | Source | Generated |
|---|---:|---:|
| case_001 | 22 | 22 |
| case_002 | 31 | 31 |
| case_003 | 33 | 33 |

## TABLE_COUNTS

| Case | Source tables | Generated tables | FormBlock tables |
|---|---:|---:|---:|
| case_001 | 5 | 26 | 21 |
| case_002 | 22 | 36 | 14 |
| case_003 | 16 | 34 | 18 |

## TESTS

Full suite: `195 passed, 1 skipped, 0 failed, 0 errors` (196 collected). JUnit evidence: `acceptance/reports/form_layout_round46/full_suite.xml`.

Synthetic Round 4.6 regressions cover visible-rule blanks, plain source-empty blanks, project-number fields, signature rows, date rows, inline blanks, true/nested hanging lists, shared FormBlocks, geometry-rejected artifacts, rotated watermark text, and preservation of valid short business cells.

## RUN_4_6_OUTPUTS

- `acceptance/workspace/case_001/run_4_6_form_layout/基础投标文件.docx`
- `acceptance/workspace/case_002/run_4_6_form_layout/基础投标文件.docx`
- `acceptance/workspace/case_003/run_4_6_form_layout/基础投标文件.docx`
- `acceptance/manual_word_test_round46/01_case_001.docx`
- `acceptance/manual_word_test_round46/02_case_002.docx`
- `acceptance/manual_word_test_round46/03_case_003.docx`

Representative full-page renders and source/generated comparison PNGs are under `acceptance/reports/form_layout_round46/{case}/render` and `.../comparisons`.

## GIT_STATUS

Working tree remains uncommitted and unreleased. Existing Round 4.5 and other user changes were preserved; no commit was created.

## BLOCKERS

Manual Microsoft Word desktop confirmation is pending. LibreOffice native rendering was used because the packaged renderer dependency `pdf2image` is unavailable; Word-safe scan and python-docx reopen passed.

ROUND_4_6_AWAITING_MANUAL_CONFIRMATION
