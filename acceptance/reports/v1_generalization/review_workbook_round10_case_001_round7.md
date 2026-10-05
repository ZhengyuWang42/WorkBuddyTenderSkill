# Round 7 review workbook audit — case_001

- build: `v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook10`
- workbook: `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook10/投标项目复核表.xlsx`
- sha256: `f0f2d94e0bde5640e57d637e44d6f3b2988c63a6904666c1393b247efaaa33a4`
- verdict: **PASS**
- delivered rows audited: 109

## Zero-count gates

| gate | value |
| --- | --- |
| CORRUPTED_RENDERED_NUMERIC_TEXT_COUNT | 0 |
| EVIDENCE_LOCATOR_SEMANTIC_MISMATCH_COUNT | 0 |
| FALSE_PLATFORM_CONFLICT_COUNT | 0 |
| FALSE_REJECTION_CLASSIFICATION_COUNT | 0 |
| GENERIC_REFERENCE_UNRESOLVED_COUNT | 0 |
| INCOMPLETE_RENDERED_SOURCE_FRAGMENT_COUNT | 0 |
| ROUND6_CONCERN_CONTRACT_FAILURES | 0 |
| ROUND6_MARKER_LOST_COUNT | 0 |
| ROUND6_MARKER_OCCURRENCE_COUNT | 18 |
| SOURCE_UNREADABLE_REFERENCE_COUNT | 0 |
| VALUE_INVARIANT_FAILURE_COUNT | 0 |

## Checks

| check | result | detail |
| --- | --- | --- |
| every generic schedule reference resolves to the project value | PASS | 109 resolved, 0 unresolved, 0 source-unreadable |
| no delivered row displays a superseded generic clause | PASS | 0 row(s) still display the generic template |
| no scoring / post-award / contract / procedural consequence is shown as 否决性 | PASS | 0 false rejection classification(s) across 25 vetoed row(s) |
| displayed requirement, page, section, clause and excerpt describe one unit | PASS | 109 row(s) checked, 0 mismatch(es) |
| no rendered source fragment is incomplete | PASS | 0 incomplete fragment(s) of 109 row(s) |
| no rendered numeric text is duplicated or corrupted | PASS | 0 corrupted numeric fragment(s) |
| different platform roles are not collapsed into one conflict | PASS | 0 false platform conflict(s); roles=3 |
| round-5/round-6 fact invariants still hold | PASS | 4 invariant(s) checked, 0 failure(s) |
| the banked round-6 marker accounting still holds | PASS | round-6 accounting verdict=PASS (failed=none) |
| Word artifacts are byte-identical (not re-rendered) | PASS | 3 artifact(s) compared against the accepted source build |

## Fixtures

| fixture | result | detail |
| --- | --- | --- |
| APPLICABLE_SOURCE_1.10.1 | PASS | 1.10.1 resolves to OVERRIDES/EVENT_NOT_HELD and 1 row(s) display it |
| APPLICABLE_SOURCE_1.10.1_TEMPLATE_HIDDEN | PASS | the superseded generic clause is not displayed |
| APPLICABLE_SOURCE_1.11.1 | PASS | 1.11.1 resolves to OVERRIDES/EVENT_NOT_HELD and 1 row(s) display it |
| APPLICABLE_SOURCE_1.11.1_TEMPLATE_HIDDEN | PASS | the superseded generic clause is not displayed |
| APPLICABLE_SOURCE_1.12 | PASS | 1.12 resolves to RESOLVES_REFERENCE/NOT_PERMITTED and 3 row(s) display it |
| APPLICABLE_SOURCE_1.12_TEMPLATE_HIDDEN | PASS | the superseded generic clause is not displayed |
| APPLICABLE_SOURCE_GENERIC_KEPT | PASS | 15 generic clause(s) kept in the atom stream for coverage/audit |
| EVIDENCE_LOCATOR_DR002 | PASS | the delivery period is located at its own supply-period source |
| EVIDENCE_LOCATOR_DR019 | PASS | the bond form is located at its own bond-form clause |
| EVIDENCE_LOCATOR_DR047 | PASS | the third-party test is located at its own test-report clause |
| FRAGMENT_DR044 | PASS | the contract-payment sentence is complete |
| FRAGMENT_DR051 | PASS | the retention ratio is 5%, not a duplicated placeholder |
| PLATFORM_ROLE_DISTINCT | PASS | 3 platform role(s) distinguished: 采购服务平台：河南国企阳光招采服务平台；交易系统：e招投标交易平台；公告发布平台：中国招标投标公共服务平台 |
| PLATFORM_ROLE_NOT_A_CONFLICT | PASS | the platform field is not reported as a value conflict |
| REJECTION_SCOPE_SCORING_NOT_VETO | PASS | 4 scoring row(s) audited; none is a rejection |
| REJECTION_SCOPE_STAGE_NAMED | PASS | 11 non-vetoed mandatory row(s) name their own basis |
