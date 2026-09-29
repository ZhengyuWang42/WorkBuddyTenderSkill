# Round 8 delivered-text audit — case_003

- build: `v1_round4_closure8_review_workbook8`
- workbook: `acceptance/workspace/case_003/v1_round4_closure8_review_workbook8/投标项目复核表.xlsx`
- sha256: `0911b930fe14ed0d5d0a3ac988a1335588bab22f96b84f089aeff667bf193e2d`
- verdict: **PASS**
- delivered rows audited: 48

## Zero-count gates

| gate | value |
| --- | --- |
| ABSORBED_HEADING_COUNT | 0 |
| BLANK_PLACEHOLDER_PROBLEM_COUNT | 0 |
| CONDITIONAL_SCORING_PROBLEM_COUNT | 0 |
| CROSS_SHEET_RISK_MISMATCH_COUNT | 0 |
| DUPLICATED_WORDING_COUNT | 0 |
| FOREIGN_LOCATOR_HEADING_COUNT | 0 |
| FORM_CLASSIFICATION_PROBLEM_COUNT | 0 |
| FRAGMENT_PROBLEM_COUNT | 0 |
| POLARITY_LOSS_COUNT | 0 |

## Checks

| check | result | detail |
| --- | --- | --- |
| no negated operative clause loses its negation | PASS | 5 negated clause(s) checked, 0 polarity loss(es) |
| scoring tiers are conditional alternatives and base/ceiling stay distinct | PASS | 0 tier row(s), 0 base-score row(s), 0 problem(s) |
| a source blank is delivered as a blank | PASS | 0 row(s) carry an explicit blank, 0 problem(s) |
| no enumeration is truncated and no clause is rendered twice | PASS | 0 fragment problem(s) |
| no requirement absorbed the next source heading | PASS | 0 absorbed heading(s) |
| no locator names a heading that governs a different clause | PASS | 0 locator(s) checked, 0 foreign heading(s) |
| no delivered requirement repeats a source phrase | PASS | 0 duplicated phrase(s) |
| the legacy 风险级别 agrees with the reviewer sheet's 否决依据 | PASS | 37 row(s) compared, 0 contradiction(s) |
| blank source forms are classified by heading and column schema | PASS | 4 blank form(s) checked, 0 misclassified |
| the criticality vocabulary matches the checks | PASS | risk / criticality vocabularies are the ones the engine emits |
| the banked round-6 marker accounting still holds | PASS | round-6 accounting verdict=PASS (failed=none) |
| Word artifacts are byte-identical (not re-rendered) | PASS | 3 artifact(s) compared against the accepted source build |

## Fixtures

| fixture | result | detail |
| --- | --- | --- |
