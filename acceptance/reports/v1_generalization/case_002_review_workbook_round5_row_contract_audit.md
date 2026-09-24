# Review workbook round 5 — case_002

- build: `v1_round4_closure8_review_workbook5`
- workbook: `acceptance\workspace\case_002\v1_round4_closure8_review_workbook5\投标项目复核表.xlsx` (sha256 `a38d00b76bb35feb…`)
- contracts: 78 (human_round5_fixtures_A_T round5.1)
- delivered rows audited: 45 (failed 0)
- fixtures: 0/20 pass / 0 fail / 20 not applicable

## Checks

| check | result | detail |
| --- | --- | --- |
| concern_contracts_are_independent | PASS | 78 contracts authored by hand (source=human_round5_fixtures_A_T, version=round5.1); none derived from a generated ReviewPoint |
| every_delivered_concern_has_a_contract | PASS | 45 delivered concerns covered |
| all_case001_final_rows_concern_contract | PASS | 45/45 delivered CASE001 rows agree with their independent concern contract |
| delivered_rows_read_from_final_cells | PASS | 45/45 rows audited from the frozen sheet cells |
| needs_review_rows_excluded_from_delivery | PASS | background items=3; filtered=1; needs_review=4 |
| numeric_roles_are_canonical | PASS | 5 numeric roles in use are canonical business roles |
| payment_ratio_95_is_not_retention | PASS | RETENTION_MONEY_RATIO never carries 95% |
| five_money_roles_stay_distinct | PASS | CASE001 value invariants are scoped to CASE001; case_002 checked for role separation only |
| scoring_points_are_scoring_only | PASS | CASE001-scoped invariant |
| bank_acceptance_ratio_separate | PASS | CASE001-scoped invariant |
| sheet_views_are_semantically_coherent | PASS | 02_关键条款 and 03_资格否决与强制项: 53 view rows validated against their concern contracts |
| conflict_sheet_has_no_false_platform_conflicts | PASS | 5 conflict rows audited against the ProjectFacts SSOT |
| word_artifacts_unchanged | PASS | 3 carried-over artifacts are byte-identical to their source build |
| review_workbook5_written | PASS | 投标项目复核表.xlsx sha256=a38d00b76bb3 (75916 bytes) |
| rendered_row_provenance_persisted | PASS | 45 rendered rows carry their exact cell address |

## Fixtures A–T

| fixture | result | expectation | evidence |
| --- | --- | --- | --- |
| A | NOT_APPLICABLE | quality requirement displays no delivery location | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| B | NOT_APPLICABLE | bid validity shows direct 90-day evidence and no blacklist text | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| C | NOT_APPLICABLE | funding clause is its own concern and does not leak into price rows | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| D | NOT_APPLICABLE | contract payment carries no agency-fee clause; the fee is complete or NEEDS_REVIEW | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| E | NOT_APPLICABLE | contract payment evidence is not a contract-effectivity clause | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| F | NOT_APPLICABLE | performance bond displays and cites only 履约保证金 | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| G | NOT_APPLICABLE | price-completeness row asserts no unestablished 无漏项/无重复项 claim | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| H | NOT_APPLICABLE | unit-price cost scope and delivery completion are separate concerns | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| I | NOT_APPLICABLE | technical standards / third-party proof / acceptance are separate concerns | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| J | NOT_APPLICABLE | 95% is never displayed as a retention ratio | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| K | NOT_APPLICABLE | retention row shows 5% 质保金 and the warranty row shows 24 months | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| L | NOT_APPLICABLE | bank-acceptance ratio is scored in its own row | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| M | NOT_APPLICABLE | each scoring row carries its own factor's points | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| N | NOT_APPLICABLE | generic evaluation row invents no points value | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| O | NOT_APPLICABLE | technical scoring row uses real scoring-table content, not a cross-reference | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| P | NOT_APPLICABLE | general bidder obligation rows do not merge procurement scope with evaluation procedure | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| Q | NOT_APPLICABLE | authorization row is backed by authorization evidence | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| R | NOT_APPLICABLE | submission row carries no collusion/delivery-pattern text | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| S | NOT_APPLICABLE | platform roles are split and produce no false platform conflicts | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |
| T | NOT_APPLICABLE | agency fee renders completely or moves to NEEDS_REVIEW (no fragment row) | CASE001 hand-authored fixture; this report is case_002 (the row audit and the cross-case role separation checks still apply) |

## Delivered-row contract audit

| item | concern | cell | contract | violations |
| --- | --- | --- | --- | --- |
| DR029 | REJECTION_GENERAL | 投标项目复核表!D9 | PASS |  |
| DR032 | EVALUATION_RESPONSIVENESS | 投标项目复核表!D10 | PASS |  |
| DR038 | EVALUATION_COLLUSION | 投标项目复核表!D11 | PASS |  |
| DR002 | QUALIFICATION_LICENSE | 投标项目复核表!D12 | PASS |  |
| DR004 | QUALIFICATION_CREDIT | 投标项目复核表!D13 | PASS |  |
| DR006 | CONSORTIUM | 投标项目复核表!D14 | PASS |  |
| DR027 | PROJECT_FUNDING_SOURCE | 投标项目复核表!D15 | PASS |  |
| DR031 | SUBCONTRACT | 投标项目复核表!D16 | PASS |  |
| DR034 | EVALUATION_QUALIFICATION_REVIEW | 投标项目复核表!D17 | PASS |  |
| DR039 | TECHNICAL_PROOF | 投标项目复核表!D18 | PASS |  |
| DR042 | QUALIFICATION_PERFORMANCE | 投标项目复核表!D19 | PASS |  |
| DR005 | QUALIFICATION_RELATIONSHIP_RESTRICTION | 投标项目复核表!D20 | PASS |  |
| DR001 | GENERAL_BIDDER_OBLIGATION | 投标项目复核表!D21 | PASS |  |
| DR019 | BID_BOND_FORM | 投标项目复核表!D22 | PASS |  |
| DR020 | BID_BOND_AMOUNT | 投标项目复核表!D23 | PASS |  |
| DR021 | BID_BOND_EVIDENCE | 投标项目复核表!D24 | PASS |  |
| DR022 | BID_BOND_TRANSFER | 投标项目复核表!D25 | PASS |  |
| DR025 | PRICE_CEILING | 投标项目复核表!D26 | PASS |  |
| DR033 | PRICE_TAX_BASIS | 投标项目复核表!D27 | PASS |  |
| DR044 | PRICE_ARITHMETIC | 投标项目复核表!D28 | PASS |  |
| DR013 | PROJECT_WARRANTY | 投标项目复核表!D29 | PASS |  |
| DR018 | BID_VALIDITY | 投标项目复核表!D30 | PASS |  |
| DR028 | QUALITY_TARGET | 投标项目复核表!D31 | PASS |  |
| DR024 | PERFORMANCE_BOND | 投标项目复核表!D32 | PASS |  |
| DR026 | CONTRACT_RISK | 投标项目复核表!D33 | PASS |  |
| DR045 | RETENTION_RELEASE_PERIOD | 投标项目复核表!D34 | PASS |  |
| DR007 | AFTER_SALES_SERVICE | 投标项目复核表!D35 | PASS |  |
| DR010 | TECHNICAL_PLAN | 投标项目复核表!D36 | PASS |  |
| DR011 | INSTALLATION_ACCEPTANCE | 投标项目复核表!D37 | PASS |  |
| DR017 | TECHNICAL_PARAMETER | 投标项目复核表!D38 | PASS |  |
| DR043 | CONTRACT_PAYMENT | 投标项目复核表!D39 | PASS |  |
| DR046 | DELIVERY_PERIOD | 投标项目复核表!D40 | PASS |  |
| DR048 | TECHNICAL_TEST_REPORT | 投标项目复核表!D41 | PASS |  |
| DR041 | SCORING_EMERGENCY_PLAN | 投标项目复核表!D42 | PASS |  |
| DR023 | EVALUATION_SCORING | 投标项目复核表!D43 | PASS |  |
| DR040 | SCORING_PRICE_FORMULA | 投标项目复核表!D44 | PASS |  |
| DR047 | SCORING_QUALITY_SYSTEM | 投标项目复核表!D45 | PASS |  |
| DR003 | AUTHORIZATION | 投标项目复核表!D46 | PASS |  |
| DR008 | ELECTRONIC_UPLOAD | 投标项目复核表!D47 | PASS |  |
| DR014 | SIGNATURE_AND_SEAL | 投标项目复核表!D48 | PASS |  |
| DR035 | OPENING_DECRYPTION | 投标项目复核表!D49 | PASS |  |
| DR030 | QUALIFICATION_ANTI_BRIBERY | 投标项目复核表!D50 | PASS |  |
| DR009 | SUBMISSION_DEADLINE | 投标项目复核表!D51 | PASS |  |
| DR015 | QUERY_DEADLINE | 投标项目复核表!D52 | PASS |  |
| DR016 | SUBMISSION_PLATFORM | 投标项目复核表!D53 | PASS |  |
