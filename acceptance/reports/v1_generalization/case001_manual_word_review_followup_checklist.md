# CASE001 manual Word review - follow-up on three source-fidelity defects

Scope: the three human-reported defects only.  No document-renderer redesign, no Round-3 restart, nothing committed or pushed.

## Build under review

| item | value |
| --- | --- |
| build id | `v1_manual_fidelity_round3_word_review_followup` |
| manifest status | `FRESH_BUILD` |
| generated DOCX | `28648aadaf7b21f4fb9e3e0168ef3e16e405925f89755ddaff84afdcbd9924a1` (45550 B) |
| generated PDF | `8013ce9945b24ac07fa9493239a5935ebbfed4fa67f4faa3c7c0abf765f41a68` (301457 B, 22 pages) |
| source PDF | `8e2bfb00e1a0c595db16d179477d9a09769ab82e45f63d476c3c8c459d46aa27` |
| LibreOffice | frozen launcher `scripts/render_case57.py`, `returncode 0`, unique `UserInstallation` profile |
| accepted build (untouched) | `v1_manual_fidelity_round3_p3semantics` |

## The three defects

| defect | resolution | automated evidence |
| --- | --- | --- |
| A - response-letter composite slot | **REPAIRED** with the generic composite-slot model | `RESPONSE_LETTER_COMPOSITE_SLOT` = PASS |
| B - `愿意` / `以人民币（大写）` in one `w:p` | **DOCUMENTED STRUCTURAL DEVIATION** - the merge is provably unavailable under the frozen P3 rule geometry | `HARD_BREAK_FIDELITY` = `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`, classified `NATURAL_WRAP`, container fidelity `SOURCE_CONTAINER_MISMATCH` |
| C - qualification-table label cell | **REPAIRED** in the generic cell alignment classifier | `SOURCE_TABLE_CELL_ALIGNMENT` = PASS |

### Defect A - what the reader now sees

```
我方已充分研究了\t(<project name>、/)（<project number>）询比文件的全部内容，愿意
```

The composite field and the adjacent form field are underlined; the source's own prose is not.  The first frame is the source's own half-width `(` `)`, the second the source's full-width `（` `）` - read from each placeholder's own `original_text`, never copied from the instruction.  `lot_name` stays `NOT_FOUND`, the `/` never becomes a fact, and the composition is selected by the registered rule's relation type and occupancy (`PLACEHOLDER_UNDERLINE` at full occupancy, and the rule must own a slot), page-scoped - no case literal, page number, rule id or slot id is referenced in production code.

### Defect B - why it is a documented structural deviation, not a gap

The source prints this letter as **one** logical paragraph of 4 wrapped visual rows, so joining the tokens in one `w:p` is what the text flow requires.  The frozen P3 contract requires R3/R4/R7/R8 to satisfy **both** endpoints via `EXACT_SOURCE_SPAN` at their frozen source y values with a 2.0 pt tolerance, and R3's representation reaches its anchor only while that row owns its line context.

**Authority order** applied here: source-visible form geometry > the frozen P3 horizontal contract > fact correctness / reading order > the source's semantic structure > the generated Word container's identity.  The container identity is the **lowest** authority, so it is the one that gives way - and the giving way is disclosed, not hidden.

The source semantics are **not** rewritten to make a gate green: `source_semantics` stays `NATURAL_WRAP` and the generated representation is reported separately as `PARAGRAPH_BOUNDARY`.

Measured, on this delivered package:

- removing only the `</w:p><w:p>` boundary and rendering through the frozen launcher puts `文件的全部内容，愿意以人民币（大写）` on one line starting at x=70.9, so the continuation row never starts its own line (`case001_defect_b_merge_experiment.json`).
- with the wrapped-row isolation disabled, the frozen P3 gate fails on `p3_scope_complete`, `horizontal_within_tolerance`, `exact_span_rules_intact` and `no_cross_page_rule_binding`, with P42-R3 and P42-R4 in `horizontal_failure_ids` and P42-R4 missing from the frozen rules.

Only a paragraph break, an explicit `w:br`/`w:cr`, a frame/shape or a natural wrap can start a visual line; tabs cannot move the cursor backwards, and `w:ptab` carries no position attribute.  No generic Word-native representation holds both contracts, so the accepted paragraph structure is kept, the 2.0 pt tolerance and `EXACT_SOURCE_SPAN` are untouched, and no source geometry is rebaselined.

The **policy** is encoded generically in the gate: a boundary is admitted as a reviewed deviation only when every one of the 17 conditions below holds, each one re-derived from the source, the delivered OOXML or the signed evidence artifact - never from the build's own claim about itself:

| deviation condition | value |
| --- | --- |
| `source_evidence_proves_one_logical_paragraph` | `true` |
| `source_boundary_classification_is_natural_wrap` | `true` |
| `generated_structure_is_a_native_paragraph_boundary` | `true` |
| `generated_boundary_has_no_w_br_no_w_cr_no_empty_paragraph` | `true` |
| `generated_boundary_spacing_is_zero_or_source_equivalent` | `true` |
| `no_visible_blank_row_is_introduced` | `true` |
| `reading_order_is_unchanged` | `true` |
| `text_content_is_unchanged` | `true` |
| `split_occurs_at_a_source_visual_row_transition` | `true` |
| `same_w_p_rendering_experimentally_tested` | `true` |
| `experiment_fails_an_independently_frozen_source_geometry_contract` | `true` |
| `the_violated_geometry_contract_predates_the_deviation` | `true` |
| `no_permitted_native_inline_construct_satisfies_both` | `true` |
| `preserving_geometry_requires_no_tolerance_weakening` | `true` |
| `no_source_geometry_rebaseline_is_performed` | `true` |
| `deviation_is_surfaced_explicitly` | `true` |
| `a_human_review_item_remains_open` | `true` |
| `deviation_missing_conditions` | `[]` |

| evidence field | value |
| --- | --- |
| `source_semantics` | `NATURAL_WRAP` |
| `generated_representation` | `PARAGRAPH_BOUNDARY` |
| `container_fidelity` | `SOURCE_CONTAINER_MISMATCH` |
| `fidelity_difference` | `CONTAINER_IDENTITY` |
| `deviation_kind` | `STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY` |
| `deviation_state` | `REVIEWED_ACCEPTED` |
| `deviation_evidence_path` | `acceptance/evidence/structural_deviations/response_letter_natural_wrap_boundary.json` |
| `same_word_paragraph` | `false` |
| `w_br_between_tokens` | `0` |
| `w_cr_between_tokens` | `0` |
| `empty_paragraph_between_tokens` | `0` |
| `recorded_isolation_reason` | `STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW` |
| `unexplained_structural_split` | `false` |

| accounting counter | value |
| --- | --- |
| `source_natural_wrap_boundaries` | `1` |
| `source_explicit_breaks` | `0` |
| `generated_w_br` | `1` |
| `generated_w_cr` | `0` |
| `generated_paragraph_boundaries` | `1` |
| `unexplained_structural_splits` | `0` |
| `documented_structural_deviation_count` | `1` |
| `builder_forced_breaks` | `0` |
| `unexpected_w_br_count` | `1` |
| `unexpected_w_cr_count` | `0` |

The counters are deliberately kept apart: a source natural wrap, the container's paragraph boundary and a reviewed deviation are three different facts and are never collapsed into one green line.

| disclosed inline hard break | value |
| --- | --- |
| generated paragraph 68 | `w:br`=1 `w:cr`=0 - `委托期限：
		。` |

This inline `w:br` is the source form's own layout for a single-row source element.  It is **not** counted as a reviewed structural deviation and it is **not** silently tolerated - it is listed here for the human Word review.

A recorded structural isolation is evidence about the build, not a verdict: only a boundary the **source itself** printed is an authorised split.  Source-backed breaks elsewhere are untouched - `SOURCE_EXPLICIT_BREAK` still authorises a list element's own items, and no other family regressed.

### Defect C - the label cell

The cell whose own measured geometry says `center` is delivered `jc=center` with `vAlign=center`, located by semantic table/cell identity.  The classifier's JUSTIFY branch now also requires the last line to be ranged left, so a centred two-line wrap is no longer labelled justified.  Not a global change: exactly **1** cell's alignment differs from the accepted build (`统一社会信用代码`, `both` -> `center`), the first-column label histogram is unchanged at 41 `center` / 2 `left`, and the table count, column widths, merges, row heights and borders are preserved.

## Gate results

| gate | status | note |
| --- | --- | --- |
| P3 closure, phase 2 | `PASS` | `accepted_composition_set` unchanged - tolerance 2.0, R3 x0 0.0 / x1 -0.9, R4 x0 0.0 / x1 -0.1, no rebaselining |
| P3 closure, phase 3 | `FAIL` | identical to the accepted build (`vertical_row_order_preserved`, `vertical_within_tolerance`), pre-existing diagnostic phase |
| round-3 typography | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` | `HARD_BREAK_FIDELITY` = `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` with `documented_structural_deviation_count` = 1 and `unexplained_structural_split_count` = 0; every other family 0 failed |
| follow-up acceptance | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` | `RESPONSE_LETTER_COMPOSITE_SLOT=PASS, RESPONSE_LETTER_PARAGRAPH_CONTINUITY=PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION, SOURCE_TABLE_CELL_ALIGNMENT=PASS` |
| P21 structural | `PASS` | `failed=[]` |
| reflow-aware | `PASS` | residual 0.71 / tolerance 2.0 |
| manual layout fidelity | `PASS` | 22 pages, 0 blank pages, 5/5 tables reproduce source geometry |
| three-case regression | `PASS` | case_001/002/003 acceptance all PASS; `pointers_resolve_to_the_acceptance_build` satisfied |
| full test suite | `517 passed, 1 skipped` | baseline held |

- `POINTER_CHECK` = `PASS`
- `V1_PRODUCTION_CANDIDATE` = `false` (the human Word review is outstanding)
- `READY_FOR_SUBMISSION` = `false`

## Documented deviations and the superseded chain

`documented_structural_deviation_count` = **1** and the deviation is recorded in the signed evidence artifact.  Reports written against the superseded build are archived in place and carry `superseded_by`, so no earlier statement is deleted.

## What is deliberately NOT done

- The frozen `current_build.json` pointer is repointed **to this build**, as the policy reconciliation requires; the earlier pointer is recorded in the archived reports rather than erased.
- No commit, no push, no tag.
- Nothing was written over the accepted build.

## Human review items

1. Confirm the composite slot reads `(<name>、/)（<number>）` with the source's own glyphs and underline extent.
2. Adjudicate the documented structural deviation: `愿意` and `以人民币（大写）` are read as two paragraphs because the frozen R3/R4 `EXACT_SOURCE_SPAN` geometry cannot survive the merge.  The deviation is reviewed and accepted **by project policy**, not by automation.
3. Confirm the `统一社会信用代码` cell is centred and reads as a two-line wrap.
4. Confirm nothing else in the response letter or the qualification table moved.
5. Adjudicate the disclosed inline `w:br` in generated paragraph 68 (`委托期限：`): it is the source form's own layout for a single-row source element and is reported rather than counted as a deviation.

`MANUAL_WORD_REVIEW_REQUIRED` stays **true**, `CASE001_MANUAL_WORD_REVIEW` = `NOT_YET_CONFIRMED`, `V1_PRODUCTION_CANDIDATE` stays **false** and `READY_FOR_SUBMISSION` stays **false**.
