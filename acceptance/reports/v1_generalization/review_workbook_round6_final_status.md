# Review workbook round 6 — source-visible criticality is semantic data

- invariant: **SOURCE-VISIBLE CRITICALITY IS SEMANTIC DATA**
- chain: `SOURCE MARKER -> TENDER-SPECIFIC SUBSTANTIVE REQUIREMENT RULE -> CONSEQUENCE RULE -> REVIEW CRITICALITY`
- result: **PASS**
- blockers: none
- git head: `c11c8ffd213d16111c1aecae82222f81df59c5aa`

## Flags

| flag | value |
| --- | --- |
| `REVIEW_WORKBOOK_ROUND6` | `PASS` |
| `SOURCE_MARKER_FIDELITY` | `PASS` |
| `marker_lost_count` | `0` |
| `marker_false_positive_count` | `0` |
| `SUBSTANTIVE_REQUIREMENT_CLASSIFICATION` | `PASS` |
| `REJECTION_CONSEQUENCE_CLASSIFICATION` | `PASS` |
| `source_substantive_requirement_without_review_coverage_count` | `0` |
| `CONCERN_CONTRACT` | `PASS` |
| `CASE001` | `PASS` |
| `CASE002` | `PASS` |
| `CASE003` | `PASS` |
| `THREE_CASE_GENERALIZATION` | `PASS` |
| `WORD_ARTIFACTS_UNCHANGED` | `PASS` |
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

| case | marker vocabulary | semantics | marked rows | substantive | rejection | CC | audit | visual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `case_001` | * | SUBSTANTIVE_REQUIREMENT | 17 | 31 | 33 | PASS | PASS | PASS |
| `case_002` | ★ | MANDATORY_PROOF | 1 | 1 | 3 | PASS | PASS | PASS |
| `case_003` | * | SUBSTANTIVE_REQUIREMENT | 4 | 4 | 10 | PASS | PASS | PASS |

## Case-001 star fixtures

| row | status |
| --- | --- |
| `DR001` | PASS |
| `DR002` | PASS |
| `DR003` | PASS |
| `DR004` | PASS |
| `DR012` | PASS |
| `DR017` | PASS |
| `DR018` | PASS |
| `DR019` | PASS |
| `DR020` | PASS |
| `DR030` | PASS |
| `DR047` | PASS |

## Full suite

- tests: 831
- passed: 830
- failed: 0
- errors: 0
- skipped: 1
- evidence: `D:\PyCharmProjects\WBTenderSkill\acceptance\reports\v1_generalization\review_workbook_round6_full_test_suite.txt`

## Human review

- verdict: **FAIL** (SOURCE_MARKER_CRITICALITY_FIDELITY)
- CASE001 workbook: `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`
- the automation may not rewrite this record or mark the workbook PASS

## Release

- V1_PRODUCTION_CANDIDATE: `False`
- READY_FOR_SUBMISSION: `False`
