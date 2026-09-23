# CASE001 date-row closure audit

Build: `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8`

DOCX SHA256: `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230`

## Status

| gate | value |
| --- | --- |
| DATE_AUDIT | `PASS` |
| DATE_ROW_ALIGNMENT_FIDELITY | `PASS` |
| DATE_ROW_GAP_FIDELITY | `PASS` |
| DATE_ROW_TOKEN_ANCHOR_FIDELITY | `PASS` |
| DATE_RULE_ENDPOINT_FIDELITY | `PASS` |
| DATE_FIGURE_SPACE_GEOMETRY_RUNS | `0` |

## Accounting

* `source_date_rows_document_wide` = 12
* `source_date_rows_build_scope` = 10
* `generated_date_rows` = 10
* `rows_within_2pt` = 10
* `rows_within_2pt_label` = 10/10
* `alignment_mismatch` = 0
* `collapsed` = 0
* `lost_gaps` = 0
* `invented_gaps` = 0
* `unexpected_indents` = 0
* `ambiguous` = 0
* `rows_with_figure_space_geometry` = 0
* `date_figure_space_geometry_runs` = 0
* `date_intrinsic_spacer_runs` = 27
* `date_tab_runs` = 0
* `date_zero_tracking_spacer_runs` = 2
* `max_date_gap_residual_pt` = 0.23
* `max_date_token_anchor_residual_pt` = 0.51

## Date-rule endpoints

* `source_rule_count` = 9
* `matched` = 9
* `lost` = 0
* `invented` = 0
* `max_x0_residual_pt` = 0.55
* `max_x1_residual_pt` = 0.3
* `leading_rule_pairs` = 3

## Rows

| src p | y | class | ¶ | jc | left pt | intervals (src → gen) | anchors Δ年/Δ月/Δ日 | rules m/l/i | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 404.34 | `-` | - | - | - | outside build scope | - | - | `OUTSIDE_BUILD_SCOPE` |
| 31 | 362.7 | `-` | - | - | - | outside build scope | - | - | `OUTSIDE_BUILD_SCOPE` |
| 40 | 635.41 | `SOURCE_ALIGNED_CENTER` | 6 | center | 23.0 | leading 69.0→None · year_month 40.34→40.3 · month_day 45.98→45.95 | 0.15/0.11/0.08 | 3/0/0 | `PASS` |
| 42 | 586.14 | `SOURCE_ANCHORED_FORM_ROW` | 45 | left | 147.0 | leading None→None · year_month 12.0→12.0 · month_day 12.0→12.0 | 0.1/0.1/0.1 | 0/0/0 | `PASS` |
| 43 | 659.34 | `SOURCE_ANCHORED_FORM_ROW` | 50 | left | 358.3 | leading None→None · year_month 15.6→15.6 · month_day 15.36→15.35 | 0.08/0.08/0.07 | 0/0/0 | `PASS` |
| 44 | 216.9 | `SOURCE_ANCHORED_FORM_ROW` | 57 | left | 1.2 | leading 48.03→47.95 · year_month 30.0→30.0 · month_day 48.0→48.0 | 0.17/0.17/0.17 | 3/0/0 | `PASS` |
| 44 | 450.66 | `SOURCE_ALIGNED_LEFT` | 64 | left | 0.0 | leading 28.92→None · year_month 34.32→34.55 · month_day 28.8→29.0 | 0.08/0.31/0.51 | 3/0/0 | `PASS` |
| 45 | 466.14 | `SOURCE_ANCHORED_FORM_ROW` | 76 | left | 286.9 | leading None→None · year_month 12.0→12.0 · month_day 12.0→12.0 | 0.08/0.08/0.08 | 0/0/0 | `PASS` |
| 47 | 519.66 | `SOURCE_ALIGNED_CENTER` | 86 | center | 23.5 | leading None→None · year_month 21.96→21.95 · month_day 21.96→21.95 | 0.1/0.09/0.08 | 0/0/0 | `PASS` |
| 48 | 688.98 | `SOURCE_ANCHORED_FORM_ROW` | 91 | left | 283.1 | leading None→None · year_month 21.96→21.95 · month_day 21.96→21.95 | 0.12/0.11/0.1 | 0/0/0 | `PASS` |
| 53 | 576.18 | `SOURCE_ALIGNED_CENTER` | 114 | center | 23.5 | leading None→None · year_month 21.96→21.95 · month_day 21.96→21.95 | 0.1/0.09/0.08 | 0/0/0 | `PASS` |
| 60 | 428.1 | `SOURCE_ALIGNED_CENTER` | 136 | center | 23.5 | leading None→None · year_month 21.96→21.95 · month_day 21.96→21.95 | 0.1/0.09/0.08 | 0/0/0 | `PASS` |

## Disclosures

* Indent policy: A centred row's w:left is legitimate exactly when it equals twice the source row's measured centroid offset (0 below 0.5 pt, where the source proves no asymmetry); that is SOURCE_CENTER_ALIGNMENT_FRAME, the native-alignment contract plus a measured axis correction, not a position surrogate. Non-centred rows state w:jc=left/right and their indent is the source-anchored body indent; their position fidelity is graded by the token anchors.
* READ-ONLY over the build; only the report artefacts are written.
* Generated underline spans are read from the build PDF's vector drawings with the same rule filter the source audit uses (height <= 2.4 pt, width >= 6 pt), inside a +/- window around the row's rendered top; a rule of another row that shares the window would be reported as invented rather than silently matched.
* Rule pairing is one-to-one and greedy on combined endpoint distance: a single merged generated underline cannot satisfy two source rules, and the second source rule is reported lost.
* The leading interval of a row with nothing printed to its left is not measurable as a glyph gap; it is graded through its own rule endpoint pair and through the year anchor.
* A generated underline is only claimed as a match within 2.0 pt in both endpoints, the frozen geometry tolerance; no new tolerance is introduced.
