# Round 9 delivered-content audit — case_001

- build: `v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook9r2`
- workbook: `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook9r2/投标项目复核表.xlsx`
- sha256: `e97c7072471fdf2d81d232dee03ab0acfe75139facd082fe545e5772078217f2`
- verdict: **PASS**
- checks: 17/17
- fixtures: 24/24

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
| the legacy 风险级别 agrees with the reviewer sheet's 否决依据 | PASS | 36 row(s) compared, 0 contradiction(s) |
| blank source forms are classified by heading and column schema | PASS | 2 blank form(s) checked, 0 misclassified |
| the criticality vocabulary matches the checks | PASS | risk / criticality vocabularies are the ones the engine emits |
| the banked round-6 marker accounting still holds | PASS | round-6 accounting verdict=PASS (failed=none) |
| Word artifacts are byte-identical (not re-rendered) | PASS | 3 artifact(s) compared against the accepted source build |
| no delivered action cites a page or clause the row does not quote | PASS | 50 anchored action(s) checked, 0 mismatch(es) |
| every delivered locator equals the production formatter's own output | PASS | 50 locator(s) recomputed from the canonical evidence unit and compared with the saved workbook, 0 mismatch(es), 2 clipped section(s) |
| the locator comparison accepts only exact formatter output | PASS | 4 negative control(s) + 1 positive control, accepted deviations=[] |
| a clipped locator section still identifies its own source unit | PASS | 2 clipped section(s) checked |
| blank non-quotation forms are not listed under the quotation section | PASS | 4 presentation section(s) checked, 0 problem(s) |

## Fixtures

| fixture | result | detail |
| --- | --- | --- |
| D14 | PASS | D14 the bid-bond rejection keeps its negated condition |
| D16 | PASS | D16 the delivered requirement carries no corrupted source join |
| D22 | PASS | D22 the delivered requirement carries no corrupted source join |
| D34 | PASS | D34 the validity row's locator names its own clause |
| D37 | PASS | D37 the performance-bond forfeiture keeps its negated condition |
| D39 | PASS | D39 the contract's blank grace period stays a blank |
| D40 | PASS | D40 the retention row cites the contract clause that states it (2.3 付款方式) |
| D43 | PASS | D43 the retention row cites the contract clause that states it (2.3 付款方式) |
| D45 | PASS | D45 the technical-standard list is not visibly truncated |
| D46 | PASS | D46 the starred test duty does not absorb the next heading |
| D50 | PASS | D50 the base score and the ceiling stay distinct; the rule is verified, not restated |
| D56 | PASS | D56 the pre-bid-meeting decision and the question/clarification deadline are separate concerns |
| D57 | PASS | D57 no delivered action cites a page or clause its own row does not quote |
| DR013 | PASS | the legacy 一票否决 does not contradict the row's own 否决依据 |
| DR038 | PASS | the legacy 一票否决 does not contradict the row's own 否决依据 |
| FORM_P53_PRESENTATION | PASS | the similar-project-history form is presented in its own non-quotation section |
| LOCATOR_D34_BID_VALIDITY | PASS | LOCATOR_D34_BID_VALIDITY: the delivered locator equals the production formatter output |
| LOCATOR_D40_RETENTION_RELEASE | PASS | LOCATOR_D40_RETENTION_RELEASE: the delivered locator equals the production formatter output |
| LOCATOR_D43_RETENTION_RATIO | PASS | LOCATOR_D43_RETENTION_RATIO: the delivered locator equals the production formatter output |
| LOCATOR_D57_SUBMISSION_DEADLINE | PASS | LOCATOR_D57_SUBMISSION_DEADLINE: the delivered locator equals the production formatter output |
| LOCATOR_DR002_DELIVERY_PERIOD | PASS | LOCATOR_DR002_DELIVERY_PERIOD: the delivered locator equals the production formatter output |
| LOCATOR_DR047_AUTHORIZATION | PASS | LOCATOR_DR047_AUTHORIZATION: the delivered locator equals the production formatter output |
| SCORING_BANK_ACCEPTANCE | PASS | SCORING_BANK_ACCEPTANCE: each source tier keeps its own ratio/condition, score and check |
| SCORING_PAYMENT_CONDITION | PASS | SCORING_PAYMENT_CONDITION: each source tier keeps its own ratio/condition, score and check |
