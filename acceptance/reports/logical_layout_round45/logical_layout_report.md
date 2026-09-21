# Round 4.5 logical layout engineering report

## LOGICAL_LAYOUT_ROOT_CAUSE

Round 4.4 joined lines only inside individual PDF blocks; mixed-page right indents used glyph x1. Its bbox-center heuristic also promoted incomplete list sentences to headings. Split form-label spans hid baseline boundaries. Zero manual breaks was therefore insufficient evidence of correct paragraphs.

## Correction

LayoutContainer separates available width from visible glyph bounds. Baseline rows are assembled before role classification; compatible adjacent blocks become one LogicalParagraph with preserved source fragments and slot offsets. ListLayoutGroup stabilizes indentation. Form rows use left-aligned safe tables and a leading spacer; labels/annotations retain minimum widths. Only the blank column gives way. No OOXML whitelist, package, relationship or source-table construction change.

## Slot semantic check

The source response letter contains adjacent `(项目名称、标段)` and `（项目编号）` placeholders. The identifier was inserted into the latter explicit number slot, not the name slot. The former is left unchanged; no replacement was invented. A separate semantic guard rejects number fields in name/lot slots.

## Real render results

| Case | Source / generated pages | Source / editable tables | Logical paragraphs | Joined block boundaries | Structural QA |
|---|---:|---:|---:|---:|---|
| case_001 | 22 / 22 | 5 / 44 | 80 | 21 | PASS |
| case_002 | 31 / 31 | 22 / 49 | 87 | 21 | PASS |
| case_003 | 33 / 33 | 16 / 44 | 134 | 37 | PASS |

Counts are explicitly scoped: logical paragraphs above are source body/heading paragraphs; editable tables include source tables and borderless form layout tables. The full XML paragraph count also includes cell and section-carrier paragraphs. Geometry measurements are supplementary, not visual acceptance.

## Tests

Tests: {'name': 'pytest', 'errors': '0', 'failures': '0', 'skipped': '1', 'tests': '187', 'time': '28.886', 'timestamp': '2026-09-14T16:00:08.521620+08:00', 'hostname': 'LAPTOP-SM89OMIU'}; check_env.py and export_schema.py succeeded. Full suite uses project-local TEMP/TMP and basetemp.

## Regression and limits

All five frozen fact/review artifacts are byte-identical to Round 4.4 for each case. Historical runs were not regenerated. python-docx reopen and unchanged Word-safe scanner pass. LibreOffice actually rendered all three documents. Word desktop normal-open confirmation belongs to the user; previous Round 4.4 acceptance is not claimed as a new manual test.

Remaining fidelity differences: source synthetic bold is not fully reproduced; date/underline widths are approximate; some inline source underlines and cell text alignment remain less faithful than the PDF. Source-table rendering is intentionally frozen. Visible editable underscores are used where LibreOffice suppresses trailing-space underlines. A structural PASS does not certify pixel fidelity or enterprise data correctness.

## Outputs

Three run_4_5_logical_layout directories and acceptance/manual_word_test_round45 contain the regenerated documents. Source/render PNG pairs and full-page renders are under this report directory. No Gold was read or created; no commit or release.

ROUND_4_5_AWAITING_MANUAL_LAYOUT_CONFIRMATION
