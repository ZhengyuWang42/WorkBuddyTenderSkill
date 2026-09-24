# Round-6 marker closure -- case_003

- build: `v1_round4_closure8_review_workbook6_marker_closure`
- verdict: **PASS**
- raw marker discovery records: 6
- de-duplicated source marker occurrences: 6
- duplicate extractor records collapsed: 0
- round-6 text-deduplicated evidence records: 6
- marker-carrying source atoms: 6
- ★ review rows: 4
- substantive review rows (source basis): 4
- unattributed occurrences: 0
- unresolved occurrences: 0
- direct-marker visibility failures: 0
- reference-parent coverage failures: 0
- actionable substantive uncovered: 0

## dispositions

- DIRECT_DELIVERED: 6

## occurrence ledger

| occurrence | marker | page | locator | disposition | rows |
| --- | --- | --- | --- | --- | --- |
| MO0001 (MK0001) | * | 58 | 第58页 / 块22 | DIRECT_DELIVERED | DR023 |
| MO0002 (MK0002) | * | 58 | 第58页 / 块23 | DIRECT_DELIVERED | DR023 |
| MO0003 (MK0003) | * | 58 | 第58页 / 块25 | DIRECT_DELIVERED | DR017 |
| MO0004 (MK0004) | * | 59 | 第59页 / 块10 | DIRECT_DELIVERED | DR043 |
| MO0005 (MK0005) | * | 59 | 第59页 / 块14 | DIRECT_DELIVERED | DR044 |
| MO0006 (MK0006) | * | 59 | 第59页 / 块23 | DIRECT_DELIVERED | DR023 |

## dashboard counters

| counter | formula | expected | recalculated | independent | ok |
| --- | --- | --- | --- | --- | --- |
| 带源标记的复核条目数（★） | `=COUNTIF('03_资格否决与强制项'!$H$2:$H$999,"★")` | 4 | 4 | 4 | yes |
| 实质性要求条目数（源依据） | `=COUNTIF('03_资格否决与强制项'!$J$2:$J$999,"SUBSTANTIVE*")` | 4 | 4 | 4 | yes |
| 明示或可证明否决项数 | `=COUNTIF('03_资格否决与强制项'!$I$2:$I$999,"是")` | 10 | 10 | 10 | yes |
| 其中：明示否决（源文明确示后果） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"EXPLICIT*")` | 10 | 10 | 10 | yes |
| 其中：推导否决（源文实质性要求规则） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"DERIVED*")` | 0 | 0 | 0 | yes |
