# Round 11 structural-heading audit — case_001

- build: `v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook11`
- workbook: `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook11/投标项目复核表.xlsx`
- sha256: `ea07803616dff09f84efb932a55a7a0da7332dbe5fc70ffa71690dd63100914c`
- verdict: **PASS**
- checks: 24/24
- fixtures: 51/51

## Checks

| check | result | detail |
| --- | --- | --- |
| no negated operative clause loses its negation | PASS | 4 negated clause(s) checked, 0 polarity loss(es) |
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
| every delivered locator equals the production formatter's own output | PASS | 50 locator(s) recomputed from the canonical evidence unit and compared with the saved workbook, 0 mismatch(es), 1 clipped section(s) |
| the locator comparison accepts only exact formatter output | PASS | 4 negative control(s) + 1 positive control, accepted deviations=[] |
| a clipped locator section still identifies its own source unit | PASS | 1 clipped section(s) checked |
| no pure contract risk is delivered as a bid compliance or rejection item | PASS | 7 contract-risk row(s) checked, 0 still presented as a bid blocker |
| no response-stage requirement is demoted into the contract-risk stage | PASS | 39 response row(s) checked, 0 demoted |
| blank non-quotation forms are not listed under the quotation section | PASS | 4 presentation section(s) checked, 0 problem(s) |
| no canonical evidence unit carries body prose as its section | PASS | 50 unit(s) compared with the source's own container, 0 body-prose heading(s) |
| every canonical evidence unit names the source container that owns it | PASS | 50 unit(s) compared with the source's own container, 0 foreign container(s) |
| no delivered cell repeats a phrase the extraction emitted twice | PASS | 50 row(s) checked, 0 duplicated fragment(s) |
| a clipped evidence summary never ends inside a source identifier | PASS | 50 evidence summary(ies) checked, 0 mid-token truncation(s) |
| a multi-source row states each source role explicitly | PASS | 10 multi-source row(s) checked, 0 ambiguous anchor(s) |

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
| DR037_MULTI_SOURCE_ROLES | PASS | DR037 names both of its sources instead of citing a hidden page |
| DR038 | PASS | the legacy 一票否决 does not contradict the row's own 否决依据 |
| DR048_SOURCE_HEADING | PASS | DR048_SOURCE_HEADING cites the article that owns the clause |
| DR052_SOURCE_HEADING | PASS | DR052_SOURCE_HEADING cites the article that owns the clause |
| DUPLICATED_EXTRACTION_TEXT | PASS | the delivered workbook states each wrapped phrase once |
| E38_STANDARDS_NOT_CUT_MID_TOKEN | PASS | E38 the standards evidence is not clipped inside a standard identifier |
| E47_AUTHORIZATION_HEADING | PASS | E47 the authorization row cites the clause that carries the requirement |
| E57_CONTRACT_TERMINATION_HEADING | PASS | E57 the termination row uses the article heading, not its own body prose |
| FORM_P53_PRESENTATION | PASS | the similar-project-history form is presented in its own non-quotation section |
| LOCATOR_D34_BID_VALIDITY | PASS | LOCATOR_D34_BID_VALIDITY: the delivered locator equals the production formatter output |
| LOCATOR_D40_RETENTION_RELEASE | PASS | LOCATOR_D40_RETENTION_RELEASE: the delivered locator equals the production formatter output |
| LOCATOR_D43_RETENTION_RATIO | PASS | LOCATOR_D43_RETENTION_RATIO: the delivered locator equals the production formatter output |
| LOCATOR_D57_SUBMISSION_DEADLINE | PASS | LOCATOR_D57_SUBMISSION_DEADLINE: the delivered locator equals the production formatter output |
| LOCATOR_DR002_DELIVERY_PERIOD | PASS | LOCATOR_DR002_DELIVERY_PERIOD: the delivered locator equals the production formatter output |
| LOCATOR_DR047_AUTHORIZATION | PASS | LOCATOR_DR047_AUTHORIZATION: the delivered locator equals the production formatter output |
| RESPONSE_BANK_ACCEPTANCE_SCORING | PASS | RESPONSE_BANK_ACCEPTANCE_SCORING (SCORING_BANK_ACCEPTANCE) stays a response-stage item |
| RESPONSE_BID_BOND | PASS | RESPONSE_BID_BOND (BID_BOND_EVIDENCE) stays a response-stage item |
| RESPONSE_BID_VALIDITY | PASS | RESPONSE_BID_VALIDITY (BID_VALIDITY) stays a response-stage item |
| RESPONSE_DELIVERY_LOCATION | PASS | RESPONSE_DELIVERY_LOCATION (DELIVERY_LOCATION) stays a response-stage item |
| RESPONSE_DELIVERY_PERIOD | PASS | RESPONSE_DELIVERY_PERIOD (DELIVERY_PERIOD) stays a response-stage item |
| RESPONSE_PAYMENT_CONDITION_SCORING | PASS | RESPONSE_PAYMENT_CONDITION_SCORING (SCORING_PAYMENT_CONDITION) stays a response-stage item |
| RESPONSE_PRICE_CEILING | PASS | RESPONSE_PRICE_CEILING (PRICE_CEILING) stays a response-stage item |
| RESPONSE_PRICE_INCLUDED_COST | PASS | RESPONSE_PRICE_INCLUDED_COST (PRICE_INCLUDED_COST_SCOPE) stays a response-stage item |
| RESPONSE_PRICE_SCORING | PASS | RESPONSE_PRICE_SCORING (SCORING_PRICE_FORMULA) stays a response-stage item |
| RESPONSE_PRICE_TAX_BASIS | PASS | RESPONSE_PRICE_TAX_BASIS (PRICE_TAX_BASIS) stays a response-stage item |
| RESPONSE_PRICING_COMPLETENESS | PASS | RESPONSE_PRICING_COMPLETENESS (PRICING_COMPLETENESS) stays a response-stage item |
| RESPONSE_PROJECT_WARRANTY | PASS | RESPONSE_PROJECT_WARRANTY (PROJECT_WARRANTY) stays a response-stage item |
| RESPONSE_QUALITY_TARGET | PASS | RESPONSE_QUALITY_TARGET (QUALITY_TARGET) stays a response-stage item |
| RISK_DR025_CONTRACT_RISK | PASS | RISK_DR025_CONTRACT_RISK (CONTRACT_RISK) is delivered as a pre-bid contract risk notice |
| RISK_DR037_PERFORMANCE_BOND | PASS | RISK_DR037_PERFORMANCE_BOND (PERFORMANCE_BOND) is delivered as a pre-bid contract risk notice |
| RISK_DR044_CONTRACT_PAYMENT | PASS | RISK_DR044_CONTRACT_PAYMENT (CONTRACT_PAYMENT) is delivered as a pre-bid contract risk notice |
| RISK_DR045_RETENTION_RELEASE | PASS | RISK_DR045_RETENTION_RELEASE (RETENTION_RELEASE_PERIOD) is delivered as a pre-bid contract risk notice |
| RISK_DR048_DELIVERY_ACCEPTANCE | PASS | RISK_DR048_DELIVERY_ACCEPTANCE (DELIVERY_ACCEPTANCE_COMPLETION) is delivered as a pre-bid contract risk notice |
| RISK_DR049_TERMINATION_REFUND | PASS | RISK_DR049_TERMINATION_REFUND (CONTRACT_TERMINATION_REFUND) is delivered as a pre-bid contract risk notice |
| RISK_DR051_RETENTION_RATIO | PASS | RISK_DR051_RETENTION_RATIO (RETENTION_MONEY_RATIO) is delivered as a pre-bid contract risk notice |
| SCORING_BANK_ACCEPTANCE | PASS | SCORING_BANK_ACCEPTANCE: each source tier keeps its own ratio/condition, score and check |
| SCORING_PAYMENT_CONDITION | PASS | SCORING_PAYMENT_CONDITION: each source tier keeps its own ratio/condition, score and check |
