# Round-6 marker closure -- case_001

- build: `v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook6_marker_closure`
- verdict: **PASS**
- raw marker discovery records: 18
- de-duplicated source marker occurrences: 18
- duplicate extractor records collapsed: 0
- round-6 text-deduplicated evidence records: 18
- marker-carrying source atoms: 34
- ★ review rows: 17
- substantive review rows (source basis): 31
- unattributed occurrences: 0
- unresolved occurrences: 0
- direct-marker visibility failures: 0
- reference-parent coverage failures: 0
- actionable substantive uncovered: 0

## dispositions

- BACKGROUND_NON_ACTIONABLE: 1
- DIRECT_DELIVERED: 15
- REFERENCE_PARENT: 2

## occurrence ledger

| occurrence | marker | page | locator | disposition | rows |
| --- | --- | --- | --- | --- | --- |
| MO0001 (MK0001) | * | 10 | 第10页 / 表0 第3行 | DIRECT_DELIVERED | DR033 |
| MO0002 (MK0002) | * | 9 | 第9页 / 表0 第4行 | REFERENCE_PARENT | background: DR023 |
| MO0003 (MK0003) | * | 9 | 第9页 / 表0 第7行 | BACKGROUND_NON_ACTIONABLE | background: DR023 |
| MO0004 (MK0004) | * | 9 | 第9页 / 表0 第8行 | DIRECT_DELIVERED | DR002 |
| MO0005 (MK0005) | * | 9 | 第9页 / 表0 第9行 | DIRECT_DELIVERED | DR003, DR030 |
| MO0006 (MK0006) | * | 9 | 第9页 / 表0 第10行 | DIRECT_DELIVERED | DR003 |
| MO0007 (MK0007) | * | 9 | 第9页 / 表0 第11行 | DIRECT_DELIVERED | DR004 |
| MO0008 (MK0008) | * | 9 | 第9页 / 表0 第12行 | REFERENCE_PARENT | background: DR023 |
| MO0009 (MK0009) | * | 9 | 第9页 / 表0 第13行 | DIRECT_DELIVERED | DR012 |
| MO0010 (MK0010) | * | 12 | 第12页 / 表0 第2行 | DIRECT_DELIVERED | DR001, DR024 |
| MO0011 (MK0011) | * | 10 | 第10页 / 表0 第10行 | DIRECT_DELIVERED | DR017 |
| MO0012 (MK0012) | * | 10 | 第10页 / 表0 第11行 | DIRECT_DELIVERED | DR018, DR019, DR020, DR036 |
| MO0013 (MK0013) | * | 11 | 第11页 / 表0 第1行 | DIRECT_DELIVERED | DR007, DR015 |
| MO0014 (MK0014) | * | 11 | 第11页 / 表0 第2行 | DIRECT_DELIVERED | DR015 |
| MO0015 (MK0015) | * | 34 | 第34页 / 块10 | DIRECT_DELIVERED | DR047 |
| MO0016 (MK0016) | * | 39 | 第39页 / 块2 | DIRECT_DELIVERED | DR013 |
| MO0017 (MK0017) | * | 39 | 第39页 / 块4 | DIRECT_DELIVERED | DR015 |
| MO0018 (MK0018) | * | 39 | 第39页 / 块5 | DIRECT_DELIVERED | DR047 |

## dashboard counters

| counter | formula | expected | recalculated | independent | ok |
| --- | --- | --- | --- | --- | --- |
| 带源标记的复核条目数（★） | `=COUNTIF('03_资格否决与强制项'!$H$2:$H$999,"★")` | 17 | 17 | 17 | yes |
| 实质性要求条目数（源依据） | `=COUNTIF('03_资格否决与强制项'!$J$2:$J$999,"SUBSTANTIVE*")` | 31 | 31 | 31 | yes |
| 明示或可证明否决项数 | `=COUNTIF('03_资格否决与强制项'!$I$2:$I$999,"是")` | 33 | 33 | 33 | yes |
| 其中：明示否决（源文明确示后果） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"EXPLICIT*")` | 10 | 10 | 10 | yes |
| 其中：推导否决（源文实质性要求规则） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"DERIVED*")` | 23 | 23 | 23 | yes |
