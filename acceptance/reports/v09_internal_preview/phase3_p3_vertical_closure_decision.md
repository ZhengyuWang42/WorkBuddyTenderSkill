# V0.9 Phase 3 — P3 vertical closure under the reflow-aware contract

**Status:** closed. `V0.9_INTERNAL_PREVIEW`.
**Build under test:** `acceptance/workspace/case_001/v09_build_5`
(DOCX `729529e42264ddb12385f52795217711755d97f909a5ebb4ed8dd1878a92152e`, PDF
`f60da77614f18472be6c2e2da2f5b95e7377b5923bdddb0f43c492995735beb1`, 22 pages)
**Vertical contract:** `REFLOW_AWARE_V1`
**Tolerance:** 2.0pt (unchanged, never relaxed)
**Gates:** `p3_phase2_gate.json` (PASS), `source_line_assembly_gate.json` (PASS),
`ownership_closure_gate_build5.json` (PASS), `p3_reflow_vertical_gate.json` (PASS),
`p3_final_round58_gate.json` (PASS), `case001_v09_internal_preview_gate.json`
(PASS 20/20)

## What changed and what did not

**No production rendering code was changed.** The previous decision recorded a
row-budget residual that the frozen *absolute* Phase-3 gate could not accept. The
evidence gathered since then shows the residual is not a renderer defect at all:
it is reflow the source's own content forces, plus a renderer line-pitch artifact
of the same 1.25 line-spacing spec. The repair therefore belongs in the QA
measurement, not in the emitted document.

New code, all of it measurement-only:

| file | role |
|---|---|
| `tender_basic/vertical_reflow_qa.py` | contract model: atoms, wrapping, isolation proof, plans, grid helpers |
| `tender_basic/vertical_reflow_region.py` | PDF/report-driven region assembly and line-count derivation |
| `scripts/v09_p3_reflow_vertical_gate.py` | canonical Phase-3 gate |
| `tests/test_v09_vertical_reflow_contract.py` | 20 focused regressions |

Nothing in `tender_basic/`'s rendering path imports either new module. The
generation report for build_5 is **byte-identical** to build_4's
(`73a510a11aae88b3127b533c99f8e3693bcd8cd1f35f1963807a57857fa7b2db`), and every
OOXML part of the two DOCX files is byte-identical, so the pass is provably
inert with respect to production output.

## The contract

For every logical source visual row of the P3 region the gate computes, from
measured source geometry and measured resolved-value widths:

* `minimum_required_generated_line_count` — how many generated lines the row's
  *own* participating content needs, wrapped into the measured usable widths
  (`first_line_width` for the first line, the region's left edge for the rest).
  It is never read from the generated row count, so the computation is
  non-circular.
* `mandatory_extra_line_count` and `mandatory_extra_height_pt` — the extra lines
  the row itself forces, and their height at the applicable generated pitch.
* `expansion_reason` — `FITS_ONE_GENERATED_LINE`, `MANDATORY_CONTENT_REFLOW`, or
  `MANDATORY_STRUCTURAL_ISOLATION`.
* `cumulative_mandatory_reflow_before_row_pt`, `line_pitch_expansion_before_row_pt`
  and `region_origin_offset_pt` — the three mandatory expansions that separate a
  source row from its generated row.
* `reflow_adjusted_target_y`, `actual_generated_y`, `raw_y_error`, `residual_y_error`.

Measured region facts (source page 42 vs generated page 3):

```
source logical rows                15
generated region rows              18
mandatory minimum generated rows   18      (source rows + independently justified extras)
unexplained extra rows              0
unexplained blank row gaps          0
region origin offset               11.05 pt
source line pitch                  19.9971 pt
applicable generated line pitch    21.2088 pt   (same 1.25 line-spacing spec, renderer font metrics)
line pitch expansion                1.2117 pt per row
maximum raw y error                91.64 pt
maximum residual y error            0.62 pt   (tolerance 2.0 pt, never relaxed)
```

The three mandatory extra lines are independently justified and nothing else:

* **`RF42-R02` (+2 lines, `MANDATORY_CONTENT_REFLOW`).** The row's participating
  content measures 96.00 (preserved) + 588.00 + 102.00 (the two `P42-R2` resolved
  values) + 144.86 (preserved) = **930.86pt** against a two-line capacity of
  427.08 + 453.12 = **880.20pt**. Two lines cannot hold it, so three are required.
  This independently reproduces the 940.0 / 454.8 arithmetic recorded in the
  previous decision.
* **`RF42-R10` (+1 line, `MANDATORY_STRUCTURAL_ISOLATION`).** `P42-R7`'s source
  text reaches x = 352.80, exactly its own anchor, so a forward Word tab cannot
  reach the anchor on the same line. All six structural conditions are measured,
  not assumed (see below).

## R7 structural isolation, measured

```
rule_representation_begins_at_source_anchor          true   (generated drawn rule x0 = 352.80, error 0.00)
preceding_source_content_present                     true
preceding_content_reaches_or_passes_anchor           true   (cursor 352.80 >= anchor 352.80)
reordering_would_break_source_reading_order          true
word_tab_cannot_move_backward                        true
no_same_line_representation_preserves_horizontal_contract  true (next forward stop 388.80 -> error 36.00pt)
structural_isolation_proven                          true
isolation_expansion_height_pt                       21.21
```

No other row in the region claims a structural-isolation budget; the gate refuses
the budget whenever the six conditions are not all true.

## Raw source fidelity stays visible

The reflow-aware verdict replaces only the frozen *absolute* test. The frozen
test's own verdicts are retained verbatim beside it:

* `frozen_absolute_vertical_row_order_preserved` — `false`
* `frozen_absolute_vertical_failure_ids` — the eight rules that fail the flat test
* `frozen_absolute_maximum_y_error_pt` — `91.64`
* `raw_vertical_row_table` — per-rule source y, generated y and raw error
* per-row `raw_y_error` on every one of the 15 rows

`raw_vertical_source_fidelity_difference_present` is `true` and
`manual_word_review_required` is `true`: the generated region does **not** sit on
the source's absolute y grid, and a human reviewer must see that.

## Why normalising the line pitch was still not the answer on its own

The generated pitch exceeds the source pitch by 1.2117pt because the same
`w:line="300" w:lineRule="auto"` (1.25 multiple) resolves through different font
metrics in the source producer and in LibreOffice. That difference is real and is
carried explicitly as `line_pitch_expansion_before_row_pt`; it is *not* hidden by
changing the document's line spacing, which would invalidate the frozen Phase 1/2
evidence and still would not account for the +3 mandatory rows on its own.

## Non-regression

* Horizontal: 8/8 rules matched, `horizontal_failure_ids: []`, dx = 0.00 on x0 and
  x1; `p3_phase2_gate.json` PASS.
* Semantics: 8/8 transformation policies and geometry intents unchanged; accepted
  composition set exactly the frozen seven.
* Execution ownership: `ownership_closure_gate_build5.json` PASS on all 8 checks;
  `P40-R1` / `P45-R6` establish no owner and emit no value (all four counters 0).
* Source-line assembly: PASS, `failed_checks: []`.
* Safety: `generated_textbox_count: 0`, no positioned form-layout breaks, no
  synthetic layout tables, unsafe OOXML scan clean, text-clipping / duplication /
  blocking-overlap counters 0, `lot_name_invented: false`.
* Fresh build determinism: `generation_report.json` byte-identical between build_4
  and build_5; all 15 OOXML parts of the DOCX byte-identical; all 22 PDF pages
  geometrically identical (text, line boxes and drawn rules).
* CASE001 internal-preview precheck: PASS 20/20.
* Test suite: **411 collected, 410 passed, 1 skipped, 0 failures, 0 errors**
  (390 passed / 1 skipped before this round + 20 new reflow-contract tests).

## Status

```
vertical_contract_version                        = REFLOW_AWARE_V1
unexplained_vertical_expansion_count             = 0
mandatory_reflow_fully_explains_vertical_difference = true
vertical_residual_within_2pt                     = true
raw_vertical_source_fidelity_difference_present  = true
INTERNAL_PREVIEW                                 = true
READY_FOR_INTERNAL_TRIAL                         = true
MANUAL_WORD_REVIEW_REQUIRED                      = true
READY_FOR_SUBMISSION                             = false
```
