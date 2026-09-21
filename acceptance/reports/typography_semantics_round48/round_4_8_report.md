# Round 4.8 typography semantics acceptance report

## TYPOGRAPHY_ROOT_CAUSE

Round 4.7 emitted each extracted PDF span directly. PDF subset and fallback font identities were treated as intentional styles, so two `水泵` cells retained an isolated 宋体 10 pt extraction while same-role name cells used 仿宋 12 pt. Table cell spans were also sorted by y before x, which moved the overlapping raised `³` span before `800m` and `300m`. Fill QA counted insertions rather than auditing every typed compatible slot, and page QA could fall back to structural/model counts.

Round 4.8 normalizes PDF subset names, clusters table typography by column and semantic role, preserves legitimate header/numeric/unit variation, groups technical glyphs into overlapping baseline bands ordered by x, emits raised digits through Word superscript properties, types every tender fact slot, audits every resolved fact occurrence, and measures page count only from the LibreOffice-rendered PDF.

## CASE_001

- name_column_styles_before: `智慧泵房箱体` 仿宋 12 pt; both `水泵` cells 宋体 10 pt; `水质检测系统` 仿宋 12 pt.
- name_column_styles_after: all four named cells are 仿宋 12 pt.
- m3h_semantic_result: `800m³/h` and `300m³/h` render in x-order with the `3` stored as a true Word superscript run inheriting 仿宋 12 pt. All glyph semantic error counts are zero.
- suspicious_source_text_result: the PDF ToUnicode map returns `今`, while the rendered glyph at page 48 `[407.64,117.54,418.09,127.99]` is `含`. The geometry-backed repair produces `不含税合价`; disagreement and mapping-warning counts are each 1.
- fact_fill_coverage: 6 compatible resolved-fact slots detected, 6 filled, 0 unfilled, 0 semantic mismatches, 0 wrong-type fills. The cover project number is filled. The response sentence receives the project name from the project-name/lot slot and `YSEJJXXB202607-18` from the separate project-number slot.
- actual_rendered_pages: 22.
- visual_result: PASS on the full 22-page contact sheet and pages 1, 3, 5, and 9 at high resolution.

## CASE_002

- fact_fill_coverage: 6 compatible resolved-fact slots detected, 6 filled, 0 unfilled, 0 semantic mismatches, 0 wrong-type fills. The 投标函 sentence now reads `我单位收到贵公司营收系统整合和硬件系统升级项目招标文件` without a duplicated `项目` suffix.
- actual_rendered_pages: 31.
- source_section_count: 31.
- typography_result: PASS; matched-anchor font-family, size, and baseline mismatch counts are zero.
- visual_result: PASS on the full 31-page contact sheet and cover, 投标函, 开标一览表, first quotation, and continuation quotation pages.
- renderer note: the same local LibreOffice executable also renders the Round 4.7 DOCX as 31 pages, whereas the separately uploaded Round 4.7 artifact was reported as 32. Round 4.8 records the measured PDF length and does not infer equality from the 31 sections.

## CASE_003

- fact_fill_coverage: 0 compatible slots belong to resolved facts; 0 unfilled resolved-fact slots, 0 semantic mismatches, 0 wrong-type fills. Four project-name slots and two purchaser slots remain source placeholders because those facts are `NEEDS_REVIEW`. The resolved agency has no compatible placeholder in the source-format range.
- actual_rendered_pages: 33.
- typography_result: PASS; matched-anchor font-family, size, and baseline mismatch counts are zero.
- visual_result: PASS on the full 33-page contact sheet and cover, 投标函, 法定代表人身份证明, a data table, and 投标承诺书.

## TABLE_STYLE_QA

Case001/002/003 table style outliers: 3/8/2. All isolated same-role anomalies supported by clustering were normalized; legitimate numeric, unit, or emphasis variations were preserved. Same-role unexplained discontinuities: 0 for every case.

## GLYPH_SEMANTICS_QA

For every case: orphan raised glyphs 0; superscript order errors 0; subscript order errors 0; unit-token semantic errors 0; foreign-font superscripts 0. Case001 assertions reject `³800m/h` and `³300m/h` and confirm semantic `800m³/h` and `300m³/h`.

## FACT_SLOT_COVERAGE

Case001: 6/6 compatible resolved-fact slots filled. Case002: 6/6. Case003: 0/0 because its visible project-name and purchaser placeholders correspond to unresolved facts. All cases have semantic-slot mismatch count 0 and wrong-fact-type fill count 0.

## TRUE_PAGE_COUNT_QA

`generated_page_count` is now the PyMuPDF page length of the LibreOffice-rendered PDF. Results are case001 22, case002 31, case003 33. Source-format pages and section counts are reported separately.

## WORD_SAFE_REGRESSION

All three DOCX files reopen with python-docx, render with LibreOffice, contain zero synthetic layout tables, zero unsafe OOXML findings, and zero mid-sentence paragraph breaks. Real source tables remain native tables and forms remain paragraph-native.

## TESTS

Full suite: 211 passed, 1 skipped in 18.40 seconds. New regressions cover subset-font aliases, same-role normalization, legitimate variation, outlier detection, `m²`, `m³`, `m³/h`, `m³/s`, superscript x-order, true Word superscript, orphan detection, all-compatible fact fills, wrong-type rejection, project-name/number separation, fixed source preservation, and rendered-page count independent of section count.

## FILES_CHANGED

Round 4.8 implementation adds `tender_basic/round48_qa.py`, `scripts/run_round48_typography_semantics.py`, and `tests/test_round48_typography_semantics.py`; it updates source font normalization, source-format models and reconstruction, strict fill policy, Word-safe run emission, and the Word-safe public-API whitelist for `w:vertAlign`. Round 4.7 artifacts were not overwritten.

## RUN_4_8_OUTPUTS

- `acceptance/workspace/case_001/run_4_8_typography_semantics`
- `acceptance/workspace/case_002/run_4_8_typography_semantics`
- `acceptance/workspace/case_003/run_4_8_typography_semantics`
- `acceptance/manual_word_test_round48/01_case_001.docx`
- `acceptance/manual_word_test_round48/02_case_002.docx`
- `acceptance/manual_word_test_round48/03_case_003.docx`

Each case workspace contains `typography_qa.json`, `glyph_semantics_qa.json`, `fact_slot_coverage.json`, and `rendered_page_qa.json`.

## GIT_STATUS

The working tree remains intentionally dirty with the cumulative uncommitted Round 4.x work and the new Round 4.8 files. No commit or release was performed.

## BLOCKERS

No implementation or automated-QA blocker remains. Desktop Word/manual cross-render confirmation is still required; case002 should be rechecked in the same environment that previously produced 32 pages.

ROUND_4_8_AWAITING_MANUAL_CONFIRMATION
