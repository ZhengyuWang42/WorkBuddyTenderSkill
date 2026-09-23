# CASE001 date segment chain ledger

Build: `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure5`

DOCX SHA256: `1f98fcbd31d3fffaa466b993bba8652ac73cb339f49e0db72cfc692bd26955b0`

## Summary

* `source_date_rows_document_wide` = 12
* `rows_in_build_scope` = 10
* `rows_with_figure_space_geometry` = 1
* `date_figure_space_run_count` = 1
* `date_figure_space_glyph_count` = 11
* `date_intrinsic_spacer_run_count` = 35
* `date_tab_run_count` = 1
* `rows_reconstructing_source_width` = 0

## Cover leading interval (source page 40)

* mechanism = `LEGACY_FIGURE_SPACE`
* the runs the delivered .docx emits before the row's first date token, i.e. the mechanism that owns the leading source interval

| run | class | len | codepoints | underline | w:spacing |
| --- | --- | --- | --- | --- | --- |
| 0 | `LEGACY_FIGURE_SPACE` | 11 | 0x2007 0x2007 0x2007 0x2007 0x2007 0x2007 | True | None |

## Rows

| src p | y | class | ¶ | jc | left | tokens | spacers | fig-space | tabs | src lead/ym/md | emitted lead/ym/md |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 404.34 | `SOURCE_ALIGNED_RIGHT` | - | - | - | - | - | - | - | 36.0 / 36.0 / 42.0 | - |
| 31 | 362.7 | `SOURCE_ANCHORED_FORM_ROW` | - | - | - | - | - | - | - | 42.0 / 24.0 / 24.0 | - |
| 40 | 635.41 | `SOURCE_ALIGNED_CENTER` | 6 | center | 460 | 3 | 2 | 1 | 0 | 69.0 / 40.34 / 45.98 | 63.25 / 39.9 / 45.55 |
| 42 | 586.14 | `SOURCE_ANCHORED_FORM_ROW` | 45 | left | 2940 | 3 | 2 | 0 | 0 | None / 12.0 / 12.0 | 0.0 / 11.6 / 11.6 |
| 43 | 659.34 | `SOURCE_ANCHORED_FORM_ROW` | 50 | left | 7166 | 3 | 3 | 0 | 0 | None / 15.6 / 15.36 | 0.0 / 14.8 / 14.95 |
| 44 | 216.9 | `SOURCE_ANCHORED_FORM_ROW` | 57 | left | 24 | 3 | 5 | 0 | 0 | 48.03 / 30.0 / 48.0 | 47.55 / 29.15 / 47.15 |
| 44 | 450.66 | `SOURCE_ALIGNED_LEFT` | 64 | left | 0 | 3 | 4 | 0 | 1 | 28.92 / 34.32 / 28.8 | 0.0 / 33.45 / 27.95 |
| 45 | 466.14 | `SOURCE_ANCHORED_FORM_ROW` | 76 | left | 5738 | 3 | 3 | 0 | 0 | None / 12.0 / 12.0 | 0.0 / 11.2 / 11.6 |
| 47 | 519.66 | `SOURCE_ALIGNED_CENTER` | 86 | center | 470 | 3 | 4 | 0 | 0 | None / 21.96 / 21.96 | 0.0 / 21.15 / 21.1 |
| 48 | 688.98 | `SOURCE_ANCHORED_FORM_ROW` | 91 | left | 5662 | 3 | 4 | 0 | 0 | None / 21.96 / 21.96 | 0.0 / 21.15 / 21.1 |
| 53 | 576.18 | `SOURCE_ALIGNED_CENTER` | 114 | center | 470 | 3 | 4 | 0 | 0 | None / 21.96 / 21.96 | 0.0 / 21.15 / 21.1 |
| 60 | 428.1 | `SOURCE_ALIGNED_CENTER` | 136 | center | 470 | 3 | 4 | 0 | 0 | None / 21.96 / 21.96 | 0.0 / 21.15 / 21.1 |

## Disclosures

* READ-ONLY over the build: the delivered .docx is opened for reading; only the report artefacts are written.
* The interval decomposition is derived from the run chain alone: the token runs are the boundaries and everything between two adjacent tokens belongs to that interval. A mechanism list may therefore contain a run the source did not intend for geometry (for example a label), which is reported as OTHER rather than being silently reclassified.
* Modelled widths use tender_basic/intrinsic_spacer.py, the same calibration the builder emits from, so a systematic calibration error would show up as a uniform residual rather than as a reconstruction failure. The reconstruction check is therefore an *arithmetic* check on the chain, not an independent measurement of the page.
* The interval-level reconstruction required before render is enforced by the builder itself (date_gap_decomposition_log.reconstructs_source_gap); the row-level construct check in this ledger is computed from the emitted chain and the source's measured extent.
