# Round 5.3 — semantic line spacing, literal text fidelity, blank representation and form/alignment fidelity

Final status: `ROUND_5_3_AWAITING_WORD_MANUAL_CONFIRMATION`.

This report is generated from the real production-pipeline outputs in
`acceptance/workspace/<case>/run_5_3_text_spacing_fidelity` and LibreOffice renders of those exact files.
Page counts and internal metadata are diagnostics only and never decide acceptance.

## A. Semantic line spacing

| case | ordinary body | body list | table text | form text | TOC | exact exceptions |
| --- | --- | --- | --- | --- | --- | --- |
| case_001 | 0 | 0 | 0 | 0 | 0 | 0 |
| case_002 | 0 | 0 | 0 | 0 | 0 | 0 |
| case_003 | 0 | 0 | 0 | 0 | 0 | 0 |

All PDF-derived content uses `lineRule="auto"` with Word-native multipliers (single / 1.15 / 1.2 / 1.25 / 1.5 / double). No `w:lineRule="exact"` node exists anywhere in `word/document.xml`, `word/styles.xml` or `word/stylesWithEffects.xml`.

## B. Literal source text and space fidelity

| case | source `_` | generated `_` | lost | added | mandatory samples missing | result |
| --- | --- | --- | --- | --- | --- | --- |
| case_001 | 0 | 0 | 0 | 0 | 0 | PASS |
| case_002 | 246 | 246 | 0 | 0 | 0 | PASS |
| case_003 | 0 | 0 | 0 | 0 | 0 | PASS |

Source-visible internal spaces are preserved; shown by measured examples:

- `case_001`
  - `20\d\d\s+年\s+\d+\s+月\s+\d+\s+日` — source [] / generated ['2023 年 1 月 1 日']
  - `合同签订后\s*\d+\s*天` — source ['合同签订后30 天'] / generated ['合同签订后 30 天']
  - `截止之日起\s*\d+\s*日历天` — source ['截止之日起\n90\n日历天', '截止之日起90 日历天'] / generated ['截止之日起 90 日历天', '截止之日起90日历天']
  - `近\s*\d+\s*年` — source [] / generated []
- `case_002`
  - `20\d\d\s+年\s+\d+\s+月\s+\d+\s+日` — source [] / generated []
  - `合同签订后\s*\d+\s*天` — source [] / generated []
  - `截止之日起\s*\d+\s*日历天` — source [] / generated []
  - `近\s*\d+\s*年` — source [] / generated []
- `case_003`
  - `20\d\d\s+年\s+\d+\s+月\s+\d+\s+日` — source [] / generated []
  - `合同签订后\s*\d+\s*天` — source [] / generated []
  - `截止之日起\s*\d+\s*日历天` — source [] / generated []
  - `近\s*\d+\s*年` — source [] / generated ['近3年']

Every audited source segment that is not literally present in the DOCX is accounted for:

| case | non-verbatim segments | unexplained | disposition |
| --- | --- | --- | --- |
| case_001 | 10 | 0 | `{"DOCUMENTED_TOUNICODE_GLYPH_REPAIR": 1, "INTENDED_TRUE_SEMANTIC_SUPERSCRIPT": 2, "PROJECT_FACTS_SLOT_REPLACEMENT": 2, "RUNNING_CHROME_EXCLUDED": 5}` |
| case_002 | 25 | 0 | `{"PAGE_NUMBER_EXCLUDED": 8, "PROJECT_FACTS_SLOT_REPLACEMENT": 1, "RUNNING_CHROME_EXCLUDED": 16}` |
| case_003 | 0 | 0 | `{}` |

Allowed dispositions: running header/footer chrome, source page numbers, ProjectFacts slot replacement, the documented ToUnicode glyph repair (`不今税合` → `不含税合价`), and the intended true semantic superscript for m³/h. `UNEXPLAINED` would be a failure.

## C. Blank representation fidelity

### case_001

- representation kinds: `{"TAB_LEADER": 1, "VECTOR_LINE": 31, "SOURCE_WHITESPACE_GAP": 37}`
- invented literal-underscore forms: 0 (PASS)

| form | source page | source vector rules | source literal `_` runs | generated kinds | invented slots |
| --- | --- | --- | --- | --- | --- |
| P5_IDENTITY | 44 | 16 | 0 | `{"VECTOR_LINE": 15}` | 0 |

### case_002

- representation kinds: `{"VECTOR_LINE": 33, "SOURCE_WHITESPACE_GAP": 25, "LITERAL_UNDERSCORES": 6}`
- invented literal-underscore forms: 0 (PASS)

| form | source page | source vector rules | source literal `_` runs | generated kinds | invented slots |
| --- | --- | --- | --- | --- | --- |
| P3_CONTACT | 146 | 8 | 6 | `{"SOURCE_WHITESPACE_GAP": 1, "LITERAL_UNDERSCORES": 6, "VECTOR_LINE": 3}` | 0 |
| P6_IDENTITY | 149 | 18 | 0 | `{"VECTOR_LINE": 7, "SOURCE_WHITESPACE_GAP": 1}` | 0 |
| P7_AUTHORIZATION | 150 | 0 | 0 | `{"SOURCE_WHITESPACE_GAP": 3}` | 0 |

### case_003

- representation kinds: `{"VECTOR_LINE": 22, "SOURCE_WHITESPACE_GAP": 23}`
- invented literal-underscore forms: 0 (PASS)

| form | source page | source vector rules | source literal `_` runs | generated kinds | invented slots |
| --- | --- | --- | --- | --- | --- |
| P6_IDENTITY | 72 | 17 | 0 | `{"VECTOR_LINE": 15}` | 0 |
| P7_AUTHORIZATION | 73 | 12 | 0 | `{"VECTOR_LINE": 5}` | 0 |

## D. Table cell alignment

- case_001: mandatory source alignment mismatches = 0 (PASS)
  - P4_APPENDIX: `{"column_0": {"alignment": "center", "axis_spread_pt": 12.0, "all_axis_spreads_pt": {"left": 42.0, "center": 12.0, "right": 30.0}}, "column_1": {"alignment": "left", "axis_spread_pt": 125.88, "all_axis_spreads_pt": {"left": 125.88, "center": 146.88, "right": 254.88}}}`
- case_002: mandatory source alignment mismatches = 0 (PASS)
  - P4_OPENING: `{"column_0": {"alignment": "left", "axis_spread_pt": 38.04, "all_axis_spreads_pt": {"left": 38.04, "center": 183.0, "right": 403.92}}, "column_1": {"alignment": "left", "axis_spread_pt": 12.88, "all_axis_spreads_pt": {"left": 12.88, "center": 69.6, "right": 139.2}}}`
- case_003: mandatory source alignment mismatches = 0 (PASS)
  - P5_APPENDIX: `{"column_0": {"alignment": "center", "axis_spread_pt": 1.14, "all_axis_spreads_pt": {"left": 6.75, "center": 1.14, "right": 9.03}}, "column_1": {"alignment": "center", "axis_spread_pt": 0.74, "all_axis_spreads_pt": {"left": 47.33, "center": 0.74, "right": 47.39}}, "column_2": {"alignment": "center", "axis_spread_pt": 1.71, "all_axis_spreads_pt": {"left": 66.08, "center": 1.71, "right": 67.0}}}`

## E. Round 5.2 regressions

### List geometry (mandatory anchors)

| case | source pt | Round 5.2 reference pt | generated pt | error pt | result |
| --- | --- | --- | --- | --- | --- |
| case_001 | 94.8 | 94.8 | 94.9 | 0.1 | PASS |
| case_002 | 94.92 | 94.92 | 95.0 | 0.08 | PASS |
| case_003 | 75.85 | 75.85 | 75.95 | 0.1 | PASS |
| case_003 nested `（1）` | 90.88 | 90.88 | 90.95 | 0.07 | PASS |

### Typography and glyphs

| anchor | measured | expected | result |
| --- | --- | --- | --- |
| case_001_P9_智慧泵房箱体 | FangSong 12.0 pt | FangSong / 仿宋 12.0 pt | PASS |
| case_001_P9_水泵 | SimSun 10.0 pt | SimSun / 宋体 10.45 pt | PASS |
| case_002_P1_投标文件 | FangSong 36.0 pt | 36.0 pt | PASS |
| m³/h semantic superscript | 2 superscript runs, 0 literal `³` | true semantic superscript | PASS |

### Rendered source-vs-generated pages

Source and generated pagination differ, so each audited source page is paired with the rendered page that actually carries its content (matched by a distinctive source string, not by page number).

| case | source page | rendered page | match | comparison file |
| --- | --- | --- | --- | --- |
| case_001 | P1 | p1 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_001\comparisons\p01_source_vs_generated.png` |
| case_001 | P3 | p3 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_001\comparisons\p03_source_vs_generated.png` |
| case_001 | P4 | p4 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_001\comparisons\p04_source_vs_generated.png` |
| case_001 | P5 | p5 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_001\comparisons\p05_source_vs_generated.png` |
| case_001 | P9 | p9 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_001\comparisons\p09_source_vs_generated.png` |
| case_002 | P1 | p1 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_002\comparisons\p01_source_vs_generated.png` |
| case_002 | P3 | p3 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_002\comparisons\p03_source_vs_generated.png` |
| case_002 | P5 | p2 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_002\comparisons\p05_source_vs_generated.png` |
| case_002 | P6 | p6 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_002\comparisons\p06_source_vs_generated.png` |
| case_002 | P7 | p7 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_002\comparisons\p07_source_vs_generated.png` |
| case_002 | P8 | p9 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_002\comparisons\p08_source_vs_generated.png` |
| case_002 | P15 | p16 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_002\comparisons\p15_source_vs_generated.png` |
| case_002 | P25 | p25 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_002\comparisons\p25_source_vs_generated.png` |
| case_003 | P2 | p2 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_003\comparisons\p02_source_vs_generated.png` |
| case_003 | P4 | p4 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_003\comparisons\p04_source_vs_generated.png` |
| case_003 | P5 | p3 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_003\comparisons\p05_source_vs_generated.png` |
| case_003 | P6 | p6 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_003\comparisons\p06_source_vs_generated.png` |
| case_003 | P7 | p7 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_003\comparisons\p07_source_vs_generated.png` |
| case_003 | P10 | p10 | CONTENT_ANCHOR | `acceptance\reports\text_spacing_round53\case_003\comparisons\p10_source_vs_generated.png` |

### Frozen contracts

| contract | expected | observed | result |
| --- | --- | --- | --- |
| case_001 ProjectFacts fields | 23 | 23 | PASS |
| case_001 review items | 64 | 64 | PASS |
| case_001 runtime artifacts | 14 | 14 | PASS |
| case_002 ProjectFacts fields | 23 | 23 | PASS |
| case_002 review items | 64 | 64 | PASS |
| case_002 runtime artifacts | 14 | 14 | PASS |
| case_003 ProjectFacts fields | 23 | 23 | PASS |
| case_003 review items | 64 | 64 | PASS |
| case_003 runtime artifacts | 14 | 14 | PASS |

### Manual copies

| case | production sha256 | manual sha256 | byte identical |
| --- | --- | --- | --- |
| case_001 | `ca8b25ad3ac3ffdd` | `ca8b25ad3ac3ffdd` | True |
| case_002 | `67f6d80058ea7f80` | `67f6d80058ea7f80` | True |
| case_003 | `65d7f5b672d994f6` | `65d7f5b672d994f6` | True |

### Microsoft Word normal open

Status: `WORD_COM_ENVIRONMENT_BLOCKED`.

Word COM could not produce a reliable document acceptance signal in this environment (work-file creation and `Documents.Open` both failed, and an unrelated freshly generated minimal python-docx file behaved identically). A `pages=0 / paragraphs=0 / tables=0` probe result is an environment artifact and is **not** evidence about the generated content. No `OpenAndRepair` path was used. This is not a Round 5.3 hard failure; the normal desktop Word open gate is performed by the user on the three final DOCX files.

## Hard-gate failures

- none

Rendered comparisons and per-case QA JSON are in `acceptance/reports/text_spacing_round53/`.
Manual Word inspection remains a human gate and is not claimed by this report.
