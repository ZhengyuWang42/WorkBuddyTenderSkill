# Round 9 delivered-content audit — case_002

- build: `v1_round4_closure9_review_workbook9r2`
- workbook: `acceptance/workspace/case_002/v1_round4_closure9_review_workbook9r2/投标项目复核表.xlsx`
- sha256: `d836f8dd38a96f4638858596528599840fc4f171db76ff778865936ec85a6d23`
- verdict: **PASS**
- checks: 17/17
- fixtures: 6/6

## Checks

| check | result | detail |
| --- | --- | --- |
| no negated operative clause loses its negation | PASS | 0 negated clause(s) checked, 0 polarity loss(es) |
| scoring tiers are conditional alternatives and base/ceiling stay distinct | PASS | 0 tier row(s), 0 base-score row(s), 0 problem(s) |
| a source blank is delivered as a blank | PASS | 0 row(s) carry an explicit blank, 0 problem(s) |
| no enumeration is truncated and no clause is rendered twice | PASS | 0 fragment problem(s) |
| no requirement absorbed the next source heading | PASS | 0 absorbed heading(s) |
| no locator names a heading that governs a different clause | PASS | 0 locator(s) checked, 0 foreign heading(s) |
| no delivered requirement repeats a source phrase | PASS | 0 duplicated phrase(s) |
| the legacy 风险级别 agrees with the reviewer sheet's 否决依据 | PASS | 38 row(s) compared, 0 contradiction(s) |
| blank source forms are classified by heading and column schema | PASS | 0 blank form(s) checked, 0 misclassified |
| the criticality vocabulary matches the checks | PASS | risk / criticality vocabularies are the ones the engine emits |
| the banked round-6 marker accounting still holds | PASS | round-6 accounting verdict=PASS (failed=none) |
| Word artifacts are byte-identical (not re-rendered) | PASS | 3 artifact(s) compared against the accepted source build |
| no delivered action cites a page or clause the row does not quote | PASS | 45 anchored action(s) checked, 0 mismatch(es) |
| every delivered locator equals the production formatter's own output | PASS | 45 locator(s) recomputed from the canonical evidence unit and compared with the saved workbook, 0 mismatch(es), 4 clipped section(s) |
| the locator comparison accepts only exact formatter output | PASS | 4 negative control(s) + 1 positive control, accepted deviations=[] |
| a clipped locator section still identifies its own source unit | PASS | 4 clipped section(s) checked |
| blank non-quotation forms are not listed under the quotation section | PASS | 2 presentation section(s) checked, 0 problem(s) |

## Fixtures

| fixture | result | detail |
| --- | --- | --- |
| LOCATOR_D34_BID_VALIDITY | PASS | LOCATOR_D34_BID_VALIDITY: the delivered locator equals the production formatter output |
| LOCATOR_D40_RETENTION_RELEASE | PASS | LOCATOR_D40_RETENTION_RELEASE: the delivered locator equals the production formatter output |
| LOCATOR_D43_RETENTION_RATIO | PASS | LOCATOR_D43_RETENTION_RATIO: the delivered locator equals the production formatter output |
| LOCATOR_D57_SUBMISSION_DEADLINE | PASS | LOCATOR_D57_SUBMISSION_DEADLINE: the delivered locator equals the production formatter output |
| LOCATOR_DR002_DELIVERY_PERIOD | PASS | LOCATOR_DR002_DELIVERY_PERIOD: the delivered locator equals the production formatter output |
| LOCATOR_DR047_AUTHORIZATION | PASS | LOCATOR_DR047_AUTHORIZATION: the delivered locator equals the production formatter output |
