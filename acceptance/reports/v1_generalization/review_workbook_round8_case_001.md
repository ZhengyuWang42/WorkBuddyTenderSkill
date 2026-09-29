# Round 8 delivered-text audit — case_001

- build: `v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook8`
- workbook: `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook8/投标项目复核表.xlsx`
- sha256: `130c7638e14b96e7d4e2af79c0f6dffaf88c2d83ae9f5f8d5626ee43a2df5c8d`
- verdict: **PASS**
- delivered rows audited: 49

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
| no negated operative clause loses its negation | PASS | 6 negated clause(s) checked, 0 polarity loss(es) |
| scoring tiers are conditional alternatives and base/ceiling stay distinct | PASS | 2 tier row(s), 1 base-score row(s), 0 problem(s) |
| a source blank is delivered as a blank | PASS | 2 row(s) carry an explicit blank, 0 problem(s) |
| no enumeration is truncated and no clause is rendered twice | PASS | 0 fragment problem(s) |
| no requirement absorbed the next source heading | PASS | 0 absorbed heading(s) |
| no locator names a heading that governs a different clause | PASS | 0 locator(s) checked, 0 foreign heading(s) |
| no delivered requirement repeats a source phrase | PASS | 0 duplicated phrase(s) |
| the legacy 风险级别 agrees with the reviewer sheet's 否决依据 | PASS | 35 row(s) compared, 0 contradiction(s) |
| blank source forms are classified by heading and column schema | PASS | 2 blank form(s) checked, 0 misclassified |
| the criticality vocabulary matches the checks | PASS | risk / criticality vocabularies are the ones the engine emits |
| the banked round-6 marker accounting still holds | PASS | round-6 accounting verdict=PASS (failed=none) |
| Word artifacts are byte-identical (not re-rendered) | PASS | 3 artifact(s) compared against the accepted source build |

## Fixtures

| fixture | result | detail |
| --- | --- | --- |
| D14 | PASS | the bid-bond rejection keeps its negated condition |
| D16 | PASS | the licence wording is not duplicated |
| D23 | PASS | bank-acceptance tiers are conditional alternatives |
| D34 | PASS | the validity row's locator names its own clause |
| D37 | PASS | the performance-bond forfeiture keeps its negated condition |
| D39 | PASS | the contract's blank grace period stays a blank |
| D45 | PASS | the technical-standard list is not visibly truncated |
| D46 | PASS | the starred test duty does not absorb the next heading |
| D50 | PASS | the formula's base score is not a second maximum |
| D56 | PASS | the no-pre-bid-meeting row's action names its own decision |
| DR013 | PASS | the legacy 一票否决 does not contradict the row's own 否决依据 |
| DR038 | PASS | the legacy 一票否决 does not contradict the row's own 否决依据 |
| FORM_P53 | PASS | the similar-project-history form is not classified as a blank quotation form |
