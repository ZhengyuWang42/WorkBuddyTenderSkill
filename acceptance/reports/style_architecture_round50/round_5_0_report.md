# Round 5.0 Fixture Based Word Style Architecture

## CURRENT_STYLE_ARCHITECTURE_FAILURE

Round 4.9 output used Normal paragraphs with direct formatting and literal visible numbering. The recorded per-case counts are in `current_style_architecture_failure` in the JSON report.

## FIXTURE_STYLE_BASELINE

Structural baseline: external fixture `danyang-v1.1-numbering-sanity-fixture-v5.docx` (not versioned in this repository; the original run used a local path, so rerun requires the same fixture or a recorded fingerprint). Heading 1–9, basedOn inheritance, outline levels, keepNext/keepLines, fixture multilevel numbering, body first-line/center/right styles, and Table Text are retained. Visual values are replaced by source-PDF evidence.

## STYLE_MAPPING_ARCHITECTURE

Each case has a `style_profile.json` and `style_map.json`. Source spans are clustered by semantic role, font family, size, weight, alignment, indentation, and line rhythm; named Word styles receive the dominant values.

## NUMBERING_ARCHITECTURE

Structural headings use the fixture multilevel family. Body list paragraphs use a separate per-tender family and do not carry outline levels or TOC participation. Prefixes are removed from recognized structural and body-list paragraph text.

## CASE_001_STYLE_MAP

| Semantic Role | Word Style | Numbering Family | Source Font | Source Size | Alignment | Line Spacing | Indent (L/R/First/Hang) | Page Break Before |
|---|---|---|---|---:|---|---:|---|---|
| Chapter Title | Tender Chapter Title | — | 仿宋 | 21.95 | center | 25.24 | 0.0/0.0/0.0/0.0 | False |
| Heading 1 | Heading 1 | Fixture Heading Multilevel | 仿宋 | 14.05 | center | 16.16 | 0.0/0.0/0.0/0.0 | False |
| Heading 2 | Heading 2 | Fixture Heading Multilevel | 仿宋 | 12.0 | center | 13.8 | 0.0/0.0/0.0/0.0 | False |
| Heading 3 | Heading 3 | Fixture Heading Multilevel | 仿宋 | 14.05 | center | 16.16 | 0.0/0.0/0.0/0.0 | False |
| Body | Tender Body | — | 仿宋 | 12.0 | left | 23.92 | 0.0/0.0/0.0/0.0 | False |
| Body First Line | Tender Body First Line | — | 仿宋 | 12.0 | left | 23.34 | 0.0/0.0/24.6/0.0 | False |
| Body List 1 | Tender Body List 1 | Tender Body List | 仿宋 | 12.0 | left | 19.92 | 76.8/0.0/-24.0/24.0 | False |
| Body List 2 | Tender Body List 2 | Tender Body List | 仿宋 | 12.0 | left | 19.92 | 0.0/0.0/-24.0/0.0 | False |
| Table Text | Table Text | — | 宋体 | 10.5 | left | 23.92 | 0.0/0.0/0.0/0.0 | False |
| Table Header | Tender Table Header | — | 宋体 | 10.5 | center | 23.92 | 0.0/0.0/0.0/0.0 | False |
| Table Value | Tender Table Value | — | 宋体 | 10.5 | left | 23.92 | 0.0/0.0/0.0/0.0 | False |
| Signature Block | Tender Signature Block | — | 仿宋 | 12.0 | left | 13.8 | 0.0/0.0/0.0/0.0 | False |

Profile evidence and full JSON: `acceptance/workspace/case_001/run_5_0_style_architecture/style_map.json` and `style_profile.json`.

## HEADING_STYLE_QA

case_001: PASS; heading_count=23, headings_with_correct_style=23, fake_heading_count=0, literal_heading_number_count=0.

## BODY_STYLE_QA

case_001: body_count=21, body_using_body_style=21; paragraphs_with_named_style=362/362.

## BODY_LIST_QA

case_001: body_list_count=14, body_list_using_real_numbering=14, literal_prefix_count=0; insertion QA=PASS.

## TABLE_STYLE_QA

case_001: table_style_coverage=1.0; table_paragraph_count=222.

## OUTLINE_TREE_QA

case_001: outline_headings=23, body_list_headings=0, result=PASS; TOC and body-list entries are excluded.

## EDITABILITY_QA

case_001: PASS; checks=PASS for Heading 1, Tender Body, and Table Text.

## DIRECT_FORMATTING_QA

case_001: direct_format_override_count=23, illegal_direct_format_override_count=0.

## SOURCE_VISUAL_QA

case_001: PASS; generated_pages=22, synthetic_layout_tables=0, manual_visual_confirmation=PENDING.

## WORD_SAFE_REGRESSION

case_001: PASS; facts/review artifacts remain byte-identical to Round 4.9.

## CASE_002_STYLE_MAP

| Semantic Role | Word Style | Numbering Family | Source Font | Source Size | Alignment | Line Spacing | Indent (L/R/First/Hang) | Page Break Before |
|---|---|---|---|---:|---|---:|---|---|
| Chapter Title | Tender Chapter Title | — | 仿宋 | 12.0 | left | 23.4 | 0.0/0.0/0.0/0.0 | False |
| Heading 1 | Heading 1 | Fixture Heading Multilevel | 仿宋 | 15.95 | center | 18.34 | 0.0/0.0/0.0/0.0 | False |
| Heading 2 | Heading 2 | Fixture Heading Multilevel | 仿宋 | 15.95 | center | 18.34 | 0.0/0.0/0.0/0.0 | False |
| Heading 3 | Heading 3 | Fixture Heading Multilevel | 仿宋 | 15.95 | center | 18.34 | 0.0/0.0/0.0/0.0 | False |
| Body | Tender Body | — | 仿宋 | 12.0 | left | 23.4 | 0.0/0.0/0.0/0.0 | False |
| Body First Line | Tender Body First Line | — | 仿宋 | 12.0 | left | 23.4 | 0.0/0.0/24.0/0.0 | False |
| Body List 1 | Tender Body List 1 | Tender Body List | 仿宋 | 12.0 | left | 23.4 | 85.8/0.0/-18.6/18.6 | False |
| Body List 2 | Tender Body List 2 | Tender Body List | 仿宋 | 12.0 | left | 23.4 | 0.0/0.0/-18.6/0.0 | False |
| Table Text | Table Text | — | 宋体 | 10.5 | left | 23.4 | 0.0/0.0/0.0/0.0 | False |
| Table Header | Tender Table Header | — | 宋体 | 10.5 | center | 23.4 | 0.0/0.0/0.0/0.0 | False |
| Table Value | Tender Table Value | — | 宋体 | 10.5 | left | 23.4 | 0.0/0.0/0.0/0.0 | False |
| Signature Block | Tender Signature Block | — | 仿宋 | 12.0 | left | 13.8 | 0.0/0.0/0.0/0.0 | False |

Profile evidence and full JSON: `acceptance/workspace/case_002/run_5_0_style_architecture/style_map.json` and `style_profile.json`.

## HEADING_STYLE_QA

case_002: PASS; heading_count=14, headings_with_correct_style=14, fake_heading_count=0, literal_heading_number_count=0.

## BODY_STYLE_QA

case_002: body_count=20, body_using_body_style=20; paragraphs_with_named_style=637/637.

## BODY_LIST_QA

case_002: body_list_count=33, body_list_using_real_numbering=33, literal_prefix_count=0; insertion QA=PASS.

## TABLE_STYLE_QA

case_002: table_style_coverage=1.0; table_paragraph_count=493.

## OUTLINE_TREE_QA

case_002: outline_headings=14, body_list_headings=0, result=PASS; TOC and body-list entries are excluded.

## EDITABILITY_QA

case_002: PASS; checks=PASS for Heading 1, Tender Body, and Table Text.

## DIRECT_FORMATTING_QA

case_002: direct_format_override_count=41, illegal_direct_format_override_count=0.

## SOURCE_VISUAL_QA

case_002: PASS; generated_pages=31, synthetic_layout_tables=0, manual_visual_confirmation=PENDING.

## WORD_SAFE_REGRESSION

case_002: PASS; facts/review artifacts remain byte-identical to Round 4.9.

## CASE_003_STYLE_MAP

| Semantic Role | Word Style | Numbering Family | Source Font | Source Size | Alignment | Line Spacing | Indent (L/R/First/Hang) | Page Break Before |
|---|---|---|---|---:|---|---:|---|---|
| Chapter Title | Tender Chapter Title | — | 黑体 | 15.77 | center | 18.14 | 0.0/0.0/0.0/0.0 | False |
| Heading 1 | Heading 1 | Fixture Heading Multilevel | 黑体 | 14.27 | center | 16.42 | 0.0/0.0/0.0/0.0 | False |
| Heading 2 | Heading 2 | Fixture Heading Multilevel | 黑体 | 12.0 | left | 12.07 | 0.0/0.0/0.0/0.0 | False |
| Heading 3 | Heading 3 | Fixture Heading Multilevel | 黑体 | 14.27 | center | 16.42 | 0.0/0.0/0.0/0.0 | False |
| Body | Tender Body | — | 宋体 | 10.5 | left | 21.74 | 0.0/0.0/0.0/0.0 | False |
| Body First Line | Tender Body First Line | — | 宋体 | 10.5 | left | 21.75 | 0.0/0.0/21.02/0.0 | False |
| Body List 1 | Tender Body List 1 | Tender Body List | 宋体 | 10.5 | left | 22.84 | 66.86/0.0/-20.27/20.27 | False |
| Body List 2 | Tender Body List 2 | Tender Body List | 宋体 | 12.0 | left | 25.52 | 82.6/0.0/-21.77/21.77 | False |
| Table Text | Table Text | — | 宋体 | 10.5 | left | 21.74 | 0.0/0.0/0.0/0.0 | False |
| Table Header | Tender Table Header | — | 宋体 | 10.5 | center | 21.74 | 0.0/0.0/0.0/0.0 | False |
| Table Value | Tender Table Value | — | 宋体 | 10.5 | left | 21.74 | 0.0/0.0/0.0/0.0 | False |
| Signature Block | Tender Signature Block | — | 宋体 | 10.5 | left | 12.07 | 0.0/0.0/0.0/0.0 | False |

Profile evidence and full JSON: `acceptance/workspace/case_003/run_5_0_style_architecture/style_map.json` and `style_profile.json`.

## HEADING_STYLE_QA

case_003: PASS; heading_count=29, headings_with_correct_style=29, fake_heading_count=0, literal_heading_number_count=0.

## BODY_STYLE_QA

case_003: body_count=32, body_using_body_style=32; paragraphs_with_named_style=1553/1553.

## BODY_LIST_QA

case_003: body_list_count=37, body_list_using_real_numbering=37, literal_prefix_count=0; insertion QA=PASS.

## TABLE_STYLE_QA

case_003: table_style_coverage=1.0; table_paragraph_count=1359.

## OUTLINE_TREE_QA

case_003: outline_headings=29, body_list_headings=0, result=PASS; TOC and body-list entries are excluded.

## EDITABILITY_QA

case_003: PASS; checks=PASS for Heading 1, Tender Body, and Table Text.

## DIRECT_FORMATTING_QA

case_003: direct_format_override_count=29, illegal_direct_format_override_count=0.

## SOURCE_VISUAL_QA

case_003: PASS; generated_pages=33, synthetic_layout_tables=0, manual_visual_confirmation=PENDING.

## WORD_SAFE_REGRESSION

case_003: PASS; facts/review artifacts remain byte-identical to Round 4.9.

## TESTS

Full repository suite: PASS (216 tests, 0 failures, 0 errors, 1 skipped). JUnit evidence: `acceptance/reports/style_architecture_round50/full_suite_junit.xml`. Desktop Word normal-open and visual/navigation confirmation remain manual gates.

## RUN_5_0_OUTPUTS

- `acceptance/workspace/case_001/run_5_0_style_architecture`
- `acceptance/workspace/case_002/run_5_0_style_architecture`
- `acceptance/workspace/case_003/run_5_0_style_architecture`
- `acceptance/manual_word_test_round50/01_case_001.docx`
- `acceptance/manual_word_test_round50/02_case_002.docx`
- `acceptance/manual_word_test_round50/03_case_003.docx`

## GIT_STATUS

Working tree intentionally remains uncommitted. No release was created. No GOLD path was read or created.

## BLOCKERS

Desktop Word manual style editability, navigation, numbering insertion, and representative-page visual confirmation are pending.

Final status: `ROUND_5_0_AWAITING_MANUAL_STYLE_CONFIRMATION`
