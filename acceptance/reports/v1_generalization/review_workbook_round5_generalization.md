# Round 5 — independent concern contracts (three-case generalization)

> PROVENANCE CONSISTENCY IS NOT SEMANTIC VALIDATION.

| flag | value |
| --- | --- |
| `REVIEW_WORKBOOK_ROUND5` | PASS |
| `ALL_CASE001_FINAL_ROWS_CONCERN_CONTRACT` | PASS |
| `QUALITY_LOCATION_CONTAMINATION` | 0 |
| `VALIDITY_BLACKLIST_CONTAMINATION` | 0 |
| `CONTRACT_PAYMENT_FOREIGN_CLAUSE` | 0 |
| `PERFORMANCE_BOND_RESPONSE_BOND_EVIDENCE` | 0 |
| `UNSUPPORTED_PRICE_COMPLETENESS_ASSERTIONS` | 0 |
| `PRICE_ACCEPTANCE_MIXED_CONCERNS` | 0 |
| `TECHNICAL_ACCEPTANCE_MIXED_CONCERNS` | 0 |
| `PAYMENT_RATIO_95_AS_RETENTION` | False |
| `RETENTION_RATIO` | 5% |
| `RETENTION_RELEASE` | 12 months |
| `PROJECT_WARRANTY` | 24 months |
| `BANK_ACCEPTANCE_RATIO_SEPARATE` | True |
| `FALSE_PLATFORM_CONFLICTS` | 0 |
| `CASE001_FIXTURES_A_TO_T` | 20/20 PASS |
| `CASE001_FINAL_WORKBOOK_AUDIT` | ALL/ALL coherent |
| `CASE001` | PASS |
| `CASE002` | PASS |
| `CASE003` | PASS |
| `THREE_CASE_GENERALIZATION` | PASS |
| `WORD_ARTIFACTS_UNCHANGED` | PASS |
| `FULL_SUITE` | PASS |
| `V1_PRODUCTION_CANDIDATE` | False |
| `READY_FOR_SUBMISSION` | False |

## Evidence

```json
{
 "case_round5_checks": {
  "case_001": "16/16",
  "case_002": "15/15",
  "case_003": "15/15"
 },
 "case_row_audit": {
  "case_001": "49/49",
  "case_002": "45/45",
  "case_003": "48/48"
 },
 "case_round4_verdict": {
  "case_001": "PASS",
  "case_002": "PASS",
  "case_003": "PASS"
 },
 "quality_location_rows": [],
 "validity_blacklist_rows": [],
 "contract_payment_foreign_rows": [],
 "performance_bond_rows": [],
 "price_completeness_rows": [],
 "price_acceptance_rows": [],
 "technical_acceptance_rows": [],
 "retention_95_rows": [],
 "numeric_roles": {
  "BANK_ACCEPTANCE_RATIO": [
   "100%",
   "50%"
  ],
  "SCORE_POINTS": [
   "4分",
   "2分",
   "1分",
   "12分",
   "8分",
   "40分",
   "30分"
  ],
  "PRICE_CEILING": [
   "3100000元"
  ],
  "DELIVERY_DAYS": [
   "30日历天",
   "30天"
  ],
  "BID_VALIDITY_DAYS": [
   "90日历天"
  ],
  "PAYMENT_RATIO": [
   "95%",
   "15%"
  ],
  "RETENTION_MONEY_RATIO": [
   "5%",
   "5%"
  ],
  "RETENTION_RELEASE_MONTHS": [
   "12个月"
  ],
  "PROJECT_WARRANTY_MONTHS": [
   "24个月"
  ]
 },
 "fixtures_failed": [],
 "full_suite": [
  806,
  0
 ],
 "price_sections": {
  "case_001": {
   "一、": 4,
   "二、": 10,
   "三、": 4
  },
  "case_002": {
   "一、": 4,
   "二、": 38
  },
  "case_003": {
   "一、": 4,
   "二、": 2,
   "三、": 6
  }
 },
 "workbook_sha256": {
  "case_001": "2ab34c7547926bb56a8bfc4fb39a226d0f2bbc672ccd10edf1df73b5987046af",
  "case_002": "a38d00b76bb35febb77be030d8352ee80f48d810f378caea17fd6fe5eaccb859",
  "case_003": "85aa576207077d8730e9c78ad7ca373bc8be6fe3dad091b5ef6ab0015c7bb4de"
 }
}
```

## Cases

| case | build | rows audited | checks | fixtures |
| --- | --- | --- | --- | --- |
| case_001 | `v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook5` | 49 | 16/16 | 20/20 |
| case_002 | `v1_round4_closure8_review_workbook5` | 45 | 15/15 | 0/20 |
| case_003 | `v1_round4_closure8_review_workbook5` | 48 | 15/15 | 0/20 |
