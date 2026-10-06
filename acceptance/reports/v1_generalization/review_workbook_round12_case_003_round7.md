# Round 7 review workbook audit — case_003

- build: `v1_round4_closure9_review_workbook12_final`
- workbook: `acceptance/workspace/case_003/v1_round4_closure9_review_workbook12_final/投标项目复核表.xlsx`
- sha256: `1f0ca082bca96d745d29cd0cbeed72fb3c340567a23247f4d829f3f3ea061080`
- verdict: **PASS**
- delivered rows audited: 106

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
| ROUND6_MARKER_OCCURRENCE_COUNT | 6 |
| SOURCE_UNREADABLE_REFERENCE_COUNT | 0 |
| VALUE_INVARIANT_FAILURE_COUNT | 0 |

## Checks

| check | result | detail |
| --- | --- | --- |
| every generic schedule reference resolves to the project value | PASS | 106 resolved, 0 unresolved, 0 source-unreadable |
| no delivered row displays a superseded generic clause | PASS | 0 row(s) still display the generic template |
| no scoring / post-award / contract / procedural consequence is shown as 否决性 | PASS | 0 false rejection classification(s) across 6 vetoed row(s) |
| displayed requirement, page, section, clause and excerpt describe one unit | PASS | 106 row(s) checked, 0 mismatch(es) |
| no rendered source fragment is incomplete | PASS | 0 incomplete fragment(s) of 106 row(s) |
| no rendered numeric text is duplicated or corrupted | PASS | 0 corrupted numeric fragment(s) |
| different platform roles are not collapsed into one conflict | PASS | 0 false platform conflict(s); roles=2 |
| round-5/round-6 fact invariants still hold | PASS | 1 invariant(s) checked, 0 failure(s) |
| the banked round-6 marker accounting still holds | PASS | round-6 accounting verdict=PASS (failed=none) |
| Word artifacts are byte-identical (not re-rendered) | PASS | 3 artifact(s) compared against the accepted source build |

## Fixtures

| fixture | result | detail |
| --- | --- | --- |
| APPLICABLE_SOURCE_1.10.1 | PASS | 1.10.1 resolves to OVERRIDES/CONCRETE_VALUE and 2 row(s) display it |
| APPLICABLE_SOURCE_1.10.1_TEMPLATE_HIDDEN | PASS | the superseded generic clause is not displayed |
| APPLICABLE_SOURCE_GENERIC_KEPT | PASS | 5 generic clause(s) kept in the atom stream for coverage/audit |
| PLATFORM_ROLE_DISTINCT | PASS | 2 platform role(s) distinguished: 交易系统：操作视频、黑龙江省公共资源交易平台；公告发布平台：本次招标公告同时在中国招标投标公共服务平台 |
| PLATFORM_ROLE_NOT_A_CONFLICT | PASS | the platform field is not reported as a value conflict |
| REJECTION_SCOPE_SCORING_NOT_VETO | PASS | 2 scoring row(s) audited; none is a rejection |
| REJECTION_SCOPE_STAGE_NAMED | PASS | 31 non-vetoed mandatory row(s) name their own basis |
