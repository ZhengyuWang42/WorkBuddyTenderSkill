# CASE001 date-row round-4 diagnostic (document-wide)

Source `D:/PyCharmProjects/WBTenderSkill/acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf` (`8e2bfb00e1a0…`) → build `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm`.

**Totals**

- source date rows **12** (build scope 40–61: **10**); generated date paragraphs **10**
- alignment matched **10**, reviewed exceptions **2**, alignment mismatch **0**; collapsed rows **0**; lost source gaps **17**; invented gaps **0**; unexpected date indents **1**; ambiguous **0**
- alignment classes: SOURCE_ALIGNED_CENTER=4, SOURCE_ALIGNED_LEFT=1, SOURCE_ALIGNED_RIGHT=1, SOURCE_ANCHORED_FORM_ROW=6
- tolerance: gaps within **2.0 pt** (`MANDATORY_TOLERANCE_PT`, `tender_basic/geometry_rule_qa.py:33` == `docs/V1_DECISIONS.md` §2.1); centring `max(8.0, page_width*0.02)` = **11.91 pt** (`tender_basic/page_layout.py:463`); natural inter-glyph gap **0.00 pt** (measured)
- prior 10-row measurement table: reproduced exactly (max |delta| 0.00 pt)

**Root causes**

- NO_GAP_MECHANISM — 7/10 paired rows emit bare `年月日` (no w:tabs, no tab chars, no spaces): rendered gaps 0.00/0.00 pt vs source 12.00–21.96 pt (docx ¶45,50,76,86,91,114,136).
- NATIVE_CENTER_BUT_NO_SPACING — src p40/47/53/60 are centred natively (docx ¶6,86,114,136 w:jc=center, w:left=0) yet still drop the 40.34 pt intra-row gaps.
- POSITION_BY_INDENT_ONLY — 4 anchored rows (docx ¶45,50,76,91) reproduce source x with w:left only and lose every internal gap.
- TAB_STOPS_EXIST_BUT_MISMATCH — docx ¶57,64 carry w:tabs/underlined leader tabs but 4 of 6 material gap positions miss the 2.0 pt tolerance.
- GENERATION_REPORT_NOT_AUTHORITATIVE — generation_report.json records tab_stops=[] for docx ¶57,64 although the emitted docx contains 4/4 w:tabs.
- BUILD_SCOPE_ONLY — src p30,31 are genuine date rows (same `____年____月____日` rules) with no counterpart: the build only covers source pages 40–61.

## Rows

| src page | y | source alignment class | extent centre / offset | gen ¶ | gen jc | gen w:left | gen gaps 年→月/月→日 | source gaps 年→月/月→日 | preserved | collapsed | note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 404.34 | ALIGNED_RIGHT | 449.40 / +151.75 | — | — | — | — / — | 36.00 / 42.00 | n/a | n/a | source-only (no build counterpart) |
| 31 | 362.70 | ANCHORED_FORM_ROW | 337.80 / +40.15 | — | — | — | — / — | 24.00 / 24.00 | n/a | n/a | source-only (no build counterpart) |
| 40 | 635.41 | ALIGNED_CENTER | 309.11 / +11.46 | 6 | center | 0 tw | 34.50 / 40.25 | 40.34 / 45.98 | no | no | gaps lost: before_year,year_month,month_day |
| 42 | 586.14 | ANCHORED_FORM_ROW | 247.80 / -49.85 | 45 | left | 2940 tw | 12.00 / 12.00 | 12.00 / 12.00 | yes | no | all gaps within tolerance |
| 43 | 659.34 | ANCHORED_FORM_ROW | 462.60 / +164.95 | 50 | left | 7166 tw | 12.00 / 12.00 | 15.60 / 15.36 | no | no | gaps lost: year_month,month_day |
| 44 | 216.90 | ANCHORED_FORM_ROW | 212.87 / -84.78 | 57 | left | 24 tw | 24.00 / 48.00 | 30.00 / 48.00 | no | no | gaps lost: year_month |
| 44 | 450.66 | ALIGNED_LEFT | 134.82 / -162.83 | 64 | left | 578 tw | 5.55 / 45.00 | 34.32 / 28.80 | no | no | gaps lost: before_year,year_month,month_day; unexpected w:left |
| 45 | 466.14 | ANCHORED_FORM_ROW | 387.72 / +90.07 | 76 | left | 5738 tw | 12.00 / 12.00 | 12.00 / 12.00 | yes | no | all gaps within tolerance |
| 47 | 519.66 | ALIGNED_CENTER | 309.36 / +11.71 | 86 | center | 0 tw | 18.00 / 18.00 | 21.96 / 21.96 | no | no | gaps lost: year_month,month_day |
| 48 | 688.98 | ANCHORED_FORM_ROW | 393.84 / +96.19 | 91 | left | 5662 tw | 18.00 / 18.00 | 21.96 / 21.96 | no | no | gaps lost: year_month,month_day |
| 53 | 576.18 | ALIGNED_CENTER | 309.36 / +11.71 | 114 | center | 0 tw | 18.00 / 18.00 | 21.96 / 21.96 | no | no | gaps lost: year_month,month_day |
| 60 | 428.10 | ALIGNED_CENTER | 309.36 / +11.71 | 136 | center | 0 tw | 18.00 / 18.00 | 21.96 / 21.96 | no | no | gaps lost: year_month,month_day |

Source-rule evidence per row is in the JSON (`rows[].source_gaps[].gap_kind` / `justification`, `rows[].source_rules_in_band`).

## Excluded prose occurrences

| side | location | y | row text | reason |
|---|---|---|---|---|
| source | page 4 | 136.87 | `七、近年（2022年1月1日以来）类似项目情况表............` | prose row: 96 glyphs besides 年/月/日 |
| source | page 6 | 264.90 | `2.5供应商须自行承诺，近三年（2023年1月1日）以来企业、法定代表人` | prose row: 37 glyphs besides 年/月/日 |
| source | page 6 | 381.90 | `1.时间：2026年7月22日至2026年7月27日17时00分。` | prose row: 30 glyphs besides 年/月/日 |
| source | page 7 | 124.50 | `1.截止时间：2026年7月28日15时00分（北京时间）。` | prose row: 27 glyphs besides 年/月/日 |
| source | page 7 | 288.30 | `1.时间：2026年7月28日15时00分（北京时间）。` | prose row: 25 glyphs besides 年/月/日 |
| source | page 10 | 359.94 | `2.2.2提交响应文件截止时间2026年7月28日15时00分(北京时间` | prose row: 34 glyphs besides 年/月/日 |
| source | page 12 | 219.78 | `供应商自2023年1月1日以来，具有类似一体化泵` | prose row: 21 glyphs besides 年/月/日 |
| source | page 25 | 670.98 | `2.2.4(3)企业实供应商自2023年1月1日以来，具有一体化泵站的供` | prose row: 39 glyphs besides 年/月/日 |
| source | page 30 | 310.74 | `请将上述问题的澄清于年月日时前通过河南国企阳光招采服务` | prose row: 24 glyphs besides 年/月/日 |
| source | page 41 | 299.02 | `七、近年（2023年1月1日以来）类似项目情况表` | prose row: 21 glyphs besides 年/月/日 |
| source | page 52 | 108.90 | `供应商须自行承诺，近三年（2023年1月1日）以来企业、法定代表人无行贿` | prose row: 33 glyphs besides 年/月/日 |
| source | page 53 | 80.62 | `七、近年（2023年1月1日以来）类似项目情况表` | prose row: 21 glyphs besides 年/月/日 |
| docx | ¶15 | — | `七、近年（2023 年 1 月 1 日以来）类似项目情况表` | prose row: 21 glyphs besides 年/月/日 |
| docx | ¶108 | — | `供应商须自行承诺，近三年（2023 年 1 月 1 日）以来企业、法定代` | prose row: 85 glyphs besides 年/月/日 |
| docx | ¶110 | — | `七、近年（2023 年 1 月 1 日以来）类似项目情况表` | prose row: 21 glyphs besides 年/月/日 |

## Disclosures

- SCOPE: this audit is document-wide over all 61 source pages and finds 12 source date rows. The prior 10-row table (and the '13 年月日 occurrences / 10 date rows' statement) covered only source pages 40-61, the build's source_page range; the two extra rows are source pages 30 (y=404.34) and 31 (y=362.70), which have no generated counterpart. Both counts are reported (accounting.source_date_rows and accounting.source_date_rows_in_build_scope).
- PRIOR TABLE REPRODUCED: all 10 rows of the supplied 10-row table were re-measured independently; maximum absolute delta across every token x0/x1 and both gaps is 0.0000 pt (declared exact when <= 0.05 pt), so the table was NOT contradicted and was used as given. Details: prior_measurement_reproduction.
- CONTRADICTED GIVEN FACT: 'Pages 42,43,44,45,47,48,53,60 have no rules in their date-row band' is true for 42,43,45,47,48,53,60 but FALSE for page 44: the row at y=216.90 has 3 underline rules at y=228.60 and the row at y=450.66 has 3 at y=462.35, all inside the glyph band (glyph bottoms 229.18 and 462.94).
- CONTRADICTED GIVEN FACT (minor): 'two pages carry an extra 年月日 occurrence inside ordinary prose' -- within the build scope (pages 40-61) there are actually three such prose rows (source pages 41, 52, 53), giving the '13 occurrences / 10 date rows' pair; document-wide there are 12 prose rows against 12 date rows.
- CENTRING SENSITIVITY: source page 40 (y=635.41) is classified SOURCE_ALIGNED_CENTER with centroid offset 11.46 pt against a centring tolerance of 11.906 pt (margin 0.45 pt); this depends on including the leading rule x[214.20,283.20]@y=646.80, x[294.70,335.00]@y=646.80, x[346.40,392.50]@y=646.80 in the effective extent, as instructed. With the glyph-only extent x[283.20,404.02] the offset is 45.96 pt and the class becomes SOURCE_ANCHORED_FORM_ROW. Both values are recorded per row (centroid_offset_pt / glyph_only_centroid_offset_pt). || source page 44 (y=450.66) is classified SOURCE_ALIGNED_LEFT with centroid offset -162.83 pt against a centring tolerance of 11.906 pt (margin -150.92 pt); this depends on including the leading rule x[70.80,99.70]@y=462.35, x[111.35,140.25]@y=462.35, x[157.80,181.05]@y=462.35 in the effective extent, as instructed. With the glyph-only extent x[99.72,198.84] the offset is -148.37 pt and the class becomes SOURCE_ANCHORED_FORM_ROW. Both values are recorded per row (centroid_offset_pt / glyph_only_centroid_offset_pt).
- MARGINAL CENTRING: 4 row(s) classified SOURCE_ALIGNED_CENTER sit within 0.5 pt of the centring tolerance edge: source page 40 x[214.20,404.02] offset 11.46 pt vs tolerance 11.906 pt (margin 0.45 pt); source page 47 x[269.40,349.32] offset 11.71 pt vs tolerance 11.906 pt (margin 0.20 pt); source page 53 x[269.40,349.32] offset 11.71 pt vs tolerance 11.906 pt (margin 0.20 pt); source page 60 x[269.40,349.32] offset 11.71 pt vs tolerance 11.906 pt (margin 0.20 pt). No row fell strictly outside the tolerance, so AMBIGUOUS_NEEDS_REVIEW was returned 0 times.
- CONTENT BAND: the page text-frame is approximated as the document-wide median of per-page glyph extremes (left 70.80 pt, right 524.58 pt) rather than being re-derived from cross-page repeated anchors as tender_basic/source_page_frame.py does. The approximation is noisy -- e.g. source page 31 has a glyph reaching x1=530.40, beyond the frozen frame right edge 524.4 pt recorded in docs/V1_DECISIONS.md F2.
- TAB_POSITION gap kind is not observable on the source side: a PDF carries no tab metadata, so source gap kinds can only be SOURCE_RULE / EDITABLE_FIXED_BLANK / PLAIN_GAP. TAB_POSITION is used on the generated side only.
- SOLID UNDERLINE EXTENT: run.underline is reported as the python-docx tri-state (True/None); w:u/@w:val detail (single vs none) is not resolved beyond that.
- PAIRING: source row <-> generated paragraph pairing uses generation_report.json paragraph_layout_records[paragraph_index].source_page + source_baselines[0] (role == DATE_LINE) for all 10 pairs; the generated PDF row is attached by document order, which is safe because both sequences are monotone over generated pages 1,3,4,5,5,6,8,9,14,21. pairing_token_x_delta_pt is recorded per row as the residual check (max |delta| = 40.63 pt on source page 40, where the row is also shifted by a synthetic indent).
- GAP-BEFORE-YEAR on the generated side is only defined when a tab character precedes 年 or a non-date glyph precedes it on the rendered row; the basis used is recorded in generated_gap_before_year_basis.
- WORD RENDERING: rendered token positions come from the build PDF's text layer. Word's own tab-stop arithmetic was not executed or re-derived, so a tab stop that exists in w:tabs but does not move the glyph is reported as a measured mismatch without a cause.
- NO WRITES: every input was opened read-only; only the two report paths were written.
