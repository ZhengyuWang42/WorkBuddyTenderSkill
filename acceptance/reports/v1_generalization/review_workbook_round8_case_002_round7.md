# Round 7 review workbook audit — case_002

- build: `v1_round4_closure8_review_workbook8`
- workbook: `acceptance/workspace/case_002/v1_round4_closure8_review_workbook8/投标项目复核表.xlsx`
- sha256: `af70029182a76e309013f902aa62c7978a23b09587fba4fc444c8e2f45da06aa`
- verdict: **PASS**
- delivered rows audited: 99

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
| ROUND6_MARKER_OCCURRENCE_COUNT | 45 |
| SOURCE_UNREADABLE_REFERENCE_COUNT | 4 |
| VALUE_INVARIANT_FAILURE_COUNT | 0 |

## Checks

| check | result | detail |
| --- | --- | --- |
| every generic schedule reference resolves to the project value | PASS | 95 resolved, 0 unresolved, 4 source-unreadable |
| no delivered row displays a superseded generic clause | PASS | 0 row(s) still display the generic template |
| no scoring / post-award / contract / procedural consequence is shown as 否决性 | PASS | 0 false rejection classification(s) across 1 vetoed row(s) |
| displayed requirement, page, section, clause and excerpt describe one unit | PASS | 99 row(s) checked, 0 mismatch(es) |
| no rendered source fragment is incomplete | PASS | 0 incomplete fragment(s) of 99 row(s) |
| no rendered numeric text is duplicated or corrupted | PASS | 0 corrupted numeric fragment(s) |
| different platform roles are not collapsed into one conflict | PASS | 0 false platform conflict(s); roles=1 |
| round-5/round-6 fact invariants still hold | PASS | 1 invariant(s) checked, 0 failure(s) |
| the banked round-6 marker accounting still holds | PASS | round-6 accounting verdict=PASS (failed=none) |
| Word artifacts are byte-identical (not re-rendered) | PASS | 3 artifact(s) compared against the accepted source build |

## Fixtures

| fixture | result | detail |
| --- | --- | --- |
| APPLICABLE_SOURCE_GENERIC_KEPT | PASS | 3 generic clause(s) kept in the atom stream for coverage/audit |
| PLATFORM_ROLE_DISTINCT | PASS | 1 platform role(s) distinguished: 交易系统：西安市综改试验区国企招标集采交易平台 |
| PLATFORM_ROLE_NOT_A_CONFLICT | PASS | the platform field is not reported as a value conflict |
| REJECTION_SCOPE_SCORING_NOT_VETO | PASS | 3 scoring row(s) audited; none is a rejection |
| REJECTION_SCOPE_STAGE_NAMED | PASS | 37 non-vetoed mandatory row(s) name their own basis |
