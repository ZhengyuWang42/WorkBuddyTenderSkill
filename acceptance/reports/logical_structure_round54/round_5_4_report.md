# Round 5.4 — Logical Source Structure, Source Alignment, Fact Slot Coverage

**FINAL_STATUS: `ROUND_5_4_AWAITING_WORD_MANUAL_CONFIRMATION`**

Hard gate failures: 0

## Measured results per case

| case | mid-word splits | alignment mismatches | PDF fragments | logical tables | merged | orphans | false merges | prose mismatches | unfilled resolved slots | wrong-type fills | render | bundle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case_001 | 0 | 0 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | OK | PASS |
| case_002 | 0 | 0 | 22 | 10 | 12 | 0 | 0 | 0 | 0 | 0 | OK | PASS |
| case_003 | 0 | 0 | 16 | 16 | 0 | 0 | 0 | 0 | 0 | 0 | OK | PASS |

## case001 cover logical paragraph

- paragraphs total: 139
- mid-word hard splits: 0
- cover title paragraphs: 3
  - `河南省水利第二工程局集团有限公司引江济淮郸城县配套工程水源置换城乡供水工程项目部一体化泵站采购项目`
  - `我方已充分研究了河南省水利第二工程局集团有限公司引江济淮郸城县配套工程水源置换城乡供水工程项目部一体化泵站采购项目YSEJJXXB202607-18询比文件的全部内容，愿意以人民币（大写）（不含税），（小写）           元的响应报价，供货期        ，按合同约定实施并完成本项目规定的所有工作内容，供货质量达到        。`
  - `在河南省水利第二工程局集团有限公司引江济淮郸城县配套工程水源置换城乡供水工程项目部一体化泵站采购项目询比活动中，我公司保证做到：`

## case001 appendix alignment (per audited field)

| label | source | generated | source x0..x1 | left pad | right pad | line spread L/C/R | reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 响应范围 | center | center | 309.72..405.72 | 128.32 | 118.85 | 0.0/0.0/0.0 | balanced side padding (128.32 vs 118.85 pt) |
| 供货期 | center | center | 312.72..402.72 | 131.32 | 121.85 | 0.0/0.0/0.0 | balanced side padding (131.32 vs 121.85 pt) |
| 交货地点 | center | center | 297.72..417.72 | 116.32 | 106.85 | 0.0/0.0/0.0 | balanced side padding (116.32 vs 106.85 pt) |
| 供货质量 | center | center | 225.72..489.72 | 44.32 | 34.85 | 0.0/0.0/0.0 | balanced side padding (44.32 vs 34.85 pt) |
| 质保期 | center | center | 248.16..467.16 | 66.76 | 57.41 | 0.0/0.0/0.0 | balanced side padding (66.76 vs 57.41 pt) |
| 询比有效期 | center | center | 264.72..450.72 | 83.32 | 73.85 | 0.0/0.0/0.0 | balanced side padding (83.32 vs 73.85 pt) |
| 权利义务 | center | center | 243.72..471.72 | 62.32 | 52.85 | 0.0/0.0/0.0 | balanced side padding (62.32 vs 52.85 pt) |
| 采购需求 | center | center | 261.72..453.72 | 80.32 | 70.85 | 0.0/0.0/0.0 | balanced side padding (80.32 vs 70.85 pt) |

## case002 quotation table continuation

- PDF table fragments: 22
- logical tables: 10
- logical rows: 63
- continuation fragments detected/merged: 12/12
- orphan continuation fragments: 0
- false continuation merges: 0
- source characters preserved (multiset): True (9546 -> 9546)
- long prose cells measured: 44
- long prose alignment mismatches: 0
- emitted Word tables: 10 (logical: 10)
- continuation cell texts found in the emitted Word tables: 38/38
- fill slots on continuation fragments: 0

## case003 fact slot coverage

- compatible slots: 8
- resolved-compatible slots: 7
- filled slots: 7
- unfilled resolved slots: 0
- wrong fact type fills: 0
- unresolved slots preserved: 1

| slot | type | hint | disposition | replacement |
| --- | --- | --- | --- | --- |
| slot-68-0 | PROJECT_NAME_SLOT | 项目名称 | FILLED | 肇源县城市供水管网漏损治理项目 |
| slot-70-2 | PURCHASER_SLOT | 招标人名称 | FILLED | 肇源县城市管理综合执法局 |
| slot-70-3 | PROJECT_NAME_SLOT | 项目名称 | FILLED | 肇源县城市供水管网漏损治理项目 |
| slot-70-4 | DURATION_SLOT | 工期 | UNRESOLVED_FACT_PRESERVED | None |
| slot-71-8 | PROJECT_NAME_SLOT | 项目名称 | FILLED | 肇源县城市供水管网漏损治理项目 |
| slot-73-12 | PROJECT_AND_LOT_SLOT | 项目名称（标段名称） | FILLED | （肇源县城市供水管网漏损治理项目（标段名称）） |
| slot-94-16 | PROJECT_NAME_SLOT | 项目名称  | FILLED | 肇源县城市供水管网漏损治理项目 |
| slot-96-17 | PURCHASER_SLOT | 招标人名称 | FILLED | 肇源县城市管理综合执法局 |

## Manual delivery bundle

### case_001 — PASS

| deliverable | bytes | sha256 == production |
| --- | --- | --- |
| project_facts.json | 41962 | True |
| 投标项目复核表.xlsx | 18842 | True |
| 基础投标文件.docx | 45254 | True |
| qa_report.json | 37348 | True |

### case_002 — PASS

| deliverable | bytes | sha256 == production |
| --- | --- | --- |
| project_facts.json | 37727 | True |
| 投标项目复核表.xlsx | 19875 | True |
| 基础投标文件.docx | 60938 | True |
| qa_report.json | 61631 | True |

### case_003 — PASS

| deliverable | bytes | sha256 == production |
| --- | --- | --- |
| project_facts.json | 42907 | True |
| 投标项目复核表.xlsx | 20218 | True |
| 基础投标文件.docx | 56329 | True |
| qa_report.json | 45531 | True |

## Source vs generated visual QA

| evidence | measurement |
| --- | --- |
| case001 title text equals the source logical paragraph | True |
| case001 title Word paragraphs holding that text | 1 |
| case001 appendix max abs value-cell x0 error (pt) | 7.67 |
| case002 quotation seam inside one editable cell | True |
| case003 resolved project name present | True |
| case003 resolved purchaser present | True |
| case003 unresolved lot placeholder preserved | True |

Rendered comparisons: `audit/img/c1_cover_*.png`, `audit/img/c1_appendix_*.png`, `audit/img/c2_quotation_seam_*.png`; full generated renders under `<case>/render/基础投标文件.pdf`.

## Word package integrity

| case | result | unsafe OOXML | reopen |
| --- | --- | --- | --- |
| case_001 | PASS | 0 | None |
| case_002 | PASS | 0 | None |
| case_003 | PASS | 0 | None |

## Round 5.3 regression references

| case | artifacts | facts fields | list anchor (old) |
| --- | --- | --- | --- |
| case_001 | 14 | 23 | (3, 94.8) |
| case_002 | 14 | 23 | (3, 94.92) |
| case_003 | 14 | 23 | (4, 75.85) |

### Superseded Round 5.3 gates

Round 5.3 asserted generated_table_count == source_table_count and synthetic_layout_tables == 0. Round 5.4 section 22 explicitly requires that pdf_table_fragments == logical_table_count and source page-table count == Word table count are NOT required, because one logical table may span pages. Those two Round 5.3 invariants are therefore intentionally superseded, not silently dropped.
