# Review workbook round 6 (closed) — reconciled final status

- invariant: **SOURCE MARKER FIDELITY MUST BE CLOSED FROM THE SOURCE-DISCOVERY UNIVERSE, NOT FROM ALREADY-ATTRIBUTED ATOMS**
- universe invariant: `DISCOVERED_MARKERS = ATTRIBUTED_MARKERS + EXPLICITLY_ACCOUNTED_NON_DELIVERED_MARKERS`
- supersedes: `acceptance/reports/v1_generalization/review_workbook_round6_final_status.json` (recorded result `PASS`, now **INVALIDATED**)
- supersession reason: `COUNT_FORMULA_AND_MARKER_ATTRIBUTION_AUDIT_DEFECT`
- current closure result: **PASS**
- result: **PASS**
- blockers: none
- git head: `39ba8f6adb8333bc576ed6a414b3a04b10dc1fad`

## Defects closed

| id | name | status | evidence |
| --- | --- | --- | --- |
| D1 | `DASHBOARD_SUBSTANTIVE_COUNT_FORMULA_BROKEN` | FIXED | the substantive counter is one wildcard COUNTIF over the multi-valued 强制性类型 column and equals the independent recount in all three cases (31 / 1 / 4) |
| D2 | `SOURCE_MARKER_ATTRIBUTION_AUDIT_BLIND_SPOT` | FIXED | the audit starts from every de-duplicated discovered occurrence; mid-text markers (MK0017 / MK0018) are attributed, and CASE002 DR028 shows the ★ it owns |

## Flags

| flag | value |
| --- | --- |
| `ROUND6_DASHBOARD_COUNT_CONSISTENCY` | `PASS` |
| `ROUND6_MARKER_ATTRIBUTION_COMPLETENESS` | `PASS` |
| `ROUND6_MARKER_OCCURRENCE_RESOLUTION` | `PASS` |
| `ROUND6_SOURCE_MARKER_FIDELITY` | `PASS` |
| `ROUND6_FINAL_STATUS_RECONCILED` | `PASS` |
| `ROUND6_CRITICALITY_THREE_CASE_GENERALIZATION` | `PASS` |
| `ROUND6_CRITICALITY_CASE001` | `PASS` |
| `ROUND6_CRITICALITY_CASE002` | `PASS` |
| `ROUND6_CRITICALITY_CASE003` | `PASS` |
| `CASE001_DASHBOARD_SUBSTANTIVE_REQUIREMENTS` | `31` |
| `CASE002_DASHBOARD_SUBSTANTIVE_REQUIREMENTS` | `1` |
| `CASE003_DASHBOARD_SUBSTANTIVE_REQUIREMENTS` | `4` |
| `CASE002_DR028_SOURCE_MARKER_VISIBLE` | `PASS` |
| `SOURCE_MARKER_AGGREGATE_AUDIT` | `PASS` |
| `VISUAL_QA` | `PASS` |
| `WORD_ARTIFACTS_UNCHANGED` | `PASS` |
| `INITIAL_ROUND6_ARTIFACTS_PRESERVED` | `PASS` |
| `WORKBOOK5_UNTOUCHED` | `PASS` |
| `WORKBOOK4_UNTOUCHED` | `PASS` |
| `FULL_SUITE` | `PASS` |
| `CASE001_XLSX_MANUAL_REVIEW` | `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW` |
| `CASE002_XLSX_MANUAL_REVIEW` | `NOT_YET_CONFIRMED` |
| `CASE003_XLSX_MANUAL_REVIEW` | `NOT_YET_CONFIRMED` |
| `HUMAN_REVIEW_BOXES_TICKED` | `0` |
| `V1_PRODUCTION_CANDIDATE` | `False` |
| `READY_FOR_SUBMISSION` | `False` |

## Cases

| case | occurrences (raw → dedup) | dispositions | ★ rows | substantive | rejections (E/D) | dashboard | CC | audit | visual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `case_001` | 18 → 18 | {"DIRECT_DELIVERED": 15, "REFERENCE_PARENT": 2, "BACKGROUND_NON_ACTIONABLE": 1} | 17 | 31 | 10/23 | PASS | PASS | PASS | PASS |
| `case_002` | 45 → 45 | {"BACKGROUND_NON_ACTIONABLE": 21, "DIRECT_DELIVERED": 24} | 3 | 1 | 3/0 | PASS | PASS | PASS | PASS |
| `case_003` | 6 → 6 | {"DIRECT_DELIVERED": 6} | 4 | 4 | 10/0 | PASS | PASS | PASS | PASS |

## Dashboard counters (formula → expected = recalculated = independent)

| case | counter | formula | value |
| --- | --- | --- | --- |
| `case_001` | 带源标记的复核条目数（★） | `=COUNTIF('03_资格否决与强制项'!$H$2:$H$999,"★")` | 17 = 17 = 17 |
| `case_001` | 实质性要求条目数（源依据） | `=COUNTIF('03_资格否决与强制项'!$J$2:$J$999,"SUBSTANTIVE*")` | 31 = 31 = 31 |
| `case_001` | 明示或可证明否决项数 | `=COUNTIF('03_资格否决与强制项'!$I$2:$I$999,"是")` | 33 = 33 = 33 |
| `case_001` | 其中：明示否决（源文明确示后果） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"EXPLICIT*")` | 10 = 10 = 10 |
| `case_001` | 其中：推导否决（源文实质性要求规则） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"DERIVED*")` | 23 = 23 = 23 |
| `case_002` | 带源标记的复核条目数（★） | `=COUNTIF('03_资格否决与强制项'!$H$2:$H$999,"★")` | 3 = 3 = 3 |
| `case_002` | 实质性要求条目数（源依据） | `=COUNTIF('03_资格否决与强制项'!$J$2:$J$999,"SUBSTANTIVE*")` | 1 = 1 = 1 |
| `case_002` | 明示或可证明否决项数 | `=COUNTIF('03_资格否决与强制项'!$I$2:$I$999,"是")` | 3 = 3 = 3 |
| `case_002` | 其中：明示否决（源文明确示后果） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"EXPLICIT*")` | 3 = 3 = 3 |
| `case_002` | 其中：推导否决（源文实质性要求规则） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"DERIVED*")` | 0 = 0 = 0 |
| `case_003` | 带源标记的复核条目数（★） | `=COUNTIF('03_资格否决与强制项'!$H$2:$H$999,"★")` | 4 = 4 = 4 |
| `case_003` | 实质性要求条目数（源依据） | `=COUNTIF('03_资格否决与强制项'!$J$2:$J$999,"SUBSTANTIVE*")` | 4 = 4 = 4 |
| `case_003` | 明示或可证明否决项数 | `=COUNTIF('03_资格否决与强制项'!$I$2:$I$999,"是")` | 10 = 10 = 10 |
| `case_003` | 其中：明示否决（源文明确示后果） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"EXPLICIT*")` | 10 = 10 = 10 |
| `case_003` | 其中：推导否决（源文实质性要求规则） | `=COUNTIF('03_资格否决与强制项'!$T$2:$T$999,"DERIVED*")` | 0 = 0 = 0 |

## Count-consistency evidence (historical, not rewritten)

- note: `acceptance/reports/v1_generalization/review_workbook_round6_count_consistency_note.json`
- sha256: `44f677c665c6452cdad9667786e9d48bb22f4cd0ddde97d3edd69b757665bfdb`
- verdict recorded by the note: `FAIL`

## Test suite

- {'suite_txt': 'D:\\PyCharmProjects\\WBTenderSkill\\acceptance\\reports\\v1_generalization\\review_workbook_round6_marker_closure_full_test_suite.txt', 'suite_xml': 'D:\\PyCharmProjects\\WBTenderSkill\\acceptance\\reports\\v1_generalization\\review_workbook_round6_marker_closure_full_test_suite.xml', 'tests': 865, 'passed': 864, 'failed': 0, 'errors': 0, 'skipped': 1, 'result': 'PASS', 'duration_seconds': 70.7}

## Human review

- CASE001_XLSX_MANUAL_REVIEW: `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`
- human checkboxes ticked: 0
- V1_PRODUCTION_CANDIDATE: False
- READY_FOR_SUBMISSION: False
