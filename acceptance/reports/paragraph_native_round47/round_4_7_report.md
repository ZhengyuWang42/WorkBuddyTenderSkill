# Round 4.7 paragraph-native acceptance report

## PARAGRAPH_NATIVE_ARCHITECTURE

Only geometry-classified genuine source tables are emitted as DOCX tables. FormBlock remains a semantic grouping object; ordinary form, signature, contact, date, heading, addressee, list, and flow content is emitted as Word-native paragraphs. Paragraph indentation controls block position, paragraph spacing controls vertical placement, and tab stops are used only for same-line fill/annotation anchors.

| Case | Source real tables | Generated real tables | Synthetic layout tables | Form paragraphs |
|---|---:|---:|---:|---:|
| case_001 | 5 | 5 | 0 | 41 |
| case_002 | 22 | 22 | 0 | 33 |
| case_003 | 16 | 16 | 0 | 30 |

## BLANK_MODEL_RESULT

EditableBlank is the single source-backed blank abstraction. Visible source rules use Word leaders or underlined figure-space runs; source-empty fields remain plain and no NBSP-only placeholders are emitted.

| Case | Detected | Visible rule | Plain empty | NBSP-only | Invisible required | Width error max / median (pt) |
|---|---:|---:|---:|---:|---:|---:|
| case_001 | 68 | 32 | 32 | 0 | 0 | 0.0 / 0.0 |
| case_002 | 65 | 42 | 9 | 0 | 0 | 0.0 / 0.0 |
| case_003 | 54 | 28 | 21 | 0 | 0 | 0.0 / 0.0 |

## CASE_001

- `real_tables`: 5 source / 5 generated; `synthetic_tables`: 0.
- `cover_form_element_types`: {'项目编号': 'w:p', '供应商': 'w:p', '法定代表人或其委托代理人': 'w:p', '日期': 'w:p'}.
- `project_number_blank`: PASS.
- `response_form_blanks`: PASS; `page5_form_alignment`: PASS.
- `list_indent_result`: PASS.
- `x/y layout errors`: {'x_max_pt': 0.020002746582036934, 'y_max_pt': 0.0, 'form_row_alignment_max_pt': 0.02000122070313637}.
- `visual_result`: PASS; rendered pages [1, 3, 5, 6].

## CASE_002

- `real_tables`: 22 source / 22 generated; `synthetic_tables`: 0.
- `contact_form_element_types`: {'投标单位全称': 'w:p', '地址': 'w:p', '开户银行': 'w:p', '账号': 'w:p', '电话': 'w:p', '传真': 'w:p', '授权代表': 'w:p'}.
- `blank_result`: PASS; `list_indent_result`: PASS.
- `artifact_filter_result`: PASS; geometry metrics: {'isolated_artifact_candidates': 6, 'artifact_spans_removed': 74, 'table_spans_rejected_by_geometry': 6, 'suspicious_short_cell_text': 0, 'short_source_candidates_reviewed': 5, 'short_source_candidates_leaked_to_generated_cells': 0, 'short_source_candidate_coordinates': [{'page': 150, 'row': 6, 'column': 3}, {'page': 150, 'row': 7, 'column': 3}, {'page': 152, 'row': 0, 'column': 1}, {'page': 159, 'row': 0, 'column': 1}, {'page': 160, 'row': 0, 'column': 1}]}.
- `x/y layout errors`: {'x_max_pt': 0.020013427734397737, 'y_max_pt': 0.0, 'form_row_alignment_max_pt': 0.02000732421873863}.
- `visual_result`: PASS; rendered pages [1, 3, 5, 6, 7, 8, 15] including the complex table page.

## CASE_003

- `real_tables`: 16 source / 16 generated; `synthetic_tables`: 0.
- `signature_form_element_types`: {'投标人': 'w:p', '法定代表人或其委托代理人': 'w:p', '地址': 'w:p', '电话': 'w:p', '日期': 'w:p'}.
- `blank_result`: PASS; `list_indent_result`: PASS.
- `form_alignment_result`: PASS; `x/y layout errors`: {'x_max_pt': 0.025000762939455967, 'y_max_pt': 0.0, 'form_row_alignment_max_pt': 0.025000762939455967}.
- `visual_result`: PASS; rendered pages [2, 5, 6, 7].

## ALIGNMENT_DISTRIBUTION

| Case | Left | Center | Justify | Right |
|---|---:|---:|---:|---:|
| case_001 | 91 | 28 | 0 | 0 |
| case_002 | 97 | 17 | 0 | 0 |
| case_003 | 143 | 19 | 0 | 0 |

## TAB_STOP_USAGE

| Case | Paragraphs with tabs | Leader tabs | Anchor tabs | Date underlined runs | Terminal fallback runs |
|---|---:|---:|---:|---:|---:|
| case_001 | 23 | 22 | 3 | 9 | 5 |
| case_002 | 19 | 24 | 0 | 15 | 14 |
| case_003 | 13 | 16 | 5 | 11 | 8 |

## WORD_SAFE_REGRESSION

| Case | python-docx reopen | Word-safe scan | LibreOffice render | Unsafe OOXML | Facts/review unchanged | Prior DOCX loaded |
|---|---|---|---|---:|---|---|
| case_001 | PASS | PASS | PASS | 0 | PASS | False |
| case_002 | PASS | PASS | PASS | 0 | PASS | False |
| case_003 | PASS | PASS | PASS | 0 | PASS | False |

## PAGE_COUNTS

| Case | Source | Generated |
|---|---:|---:|
| case_001 | 22 | 22 |
| case_002 | 31 | 31 |
| case_003 | 33 | 33 |

## TABLE_COUNTS

The table counts above are genuine source-table counts; synthetic layout table count is zero for every case.

## TESTS

Full suite: `203 passed, 1 skipped, 0 failed, 0 errors` (204 collected). JUnit evidence: `acceptance/reports/paragraph_native_round47/full_suite.xml`.

Synthetic coverage includes paragraph indentation, paragraph spacing, centered title, left addressee, geometry-backed justification, hanging and nested lists, native form leaders, annotations, date rows, multi-field rows, inline blanks, real-table preservation, and non-table form exclusion.

## RUN_4_7_OUTPUTS

- `acceptance/workspace/case_001/run_4_7_paragraph_native/基础投标文件.docx`
- `acceptance/workspace/case_002/run_4_7_paragraph_native/基础投标文件.docx`
- `acceptance/workspace/case_003/run_4_7_paragraph_native/基础投标文件.docx`
- `acceptance/manual_word_test_round47/01_case_001.docx`
- `acceptance/manual_word_test_round47/02_case_002.docx`
- `acceptance/manual_word_test_round47/03_case_003.docx`

Rendered PNGs and source/generated comparison pairs are under `acceptance/reports/paragraph_native_round47/{case}/render` and `.../comparisons`.

## GIT_STATUS

Working tree remains uncommitted and unreleased. Existing user changes and Round 4.6 outputs were preserved; no commit was created.

## BLOCKERS

Manual Microsoft Word desktop confirmation remains pending. LibreOffice native rendering, python-docx reopen, and Word-safe scan passed.

ROUND_4_7_AWAITING_MANUAL_CONFIRMATION
