# CASE001 Round 3 — P3 contract reconciliation

**Objective:** keep the Round-3 typography and cell fixes, and give the frozen P3
horizontal contract its geometry back.

**Build (new, same build for every measurement below):**
`acceptance/workspace/case_001/v1_manual_fidelity_round3_p3reconciled`
**DOCX sha256:** `0ac9f7bc1da34f1d32f5fe4aa444d2a1317a72a99589134972b8a49134fd39ab`
**PDF sha256:** `2d282ec4c77269b90c4d69a8b0c0fae8ca937d736941eb175709d30b3cbe29b5`
(22 rendered pages, 0 blank pages, LibreOffice returncode 0, pipeline returncode 0)

**Superseded build (measured here, not deleted):**
`acceptance/workspace/case_001/v1_manual_fidelity_round3_source_typography`
(DOCX sha256 `3658bfcb…`) — Round 3's typography fixes, measured before this
reconciliation.

**Source:** `acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf`
(61 pages, sha256 `8e2bfb00…`). **Round-2 baseline (still banked, unchanged):**
`acceptance/workspace/case_001/v1_manual_fidelity_round2_p21fix`.
**Nothing was committed or pushed.**

## 1. Status block

| Status | Result |
| --- | --- |
| `CASE001_ROUND3_P3_RECONCILIATION` | PASS |
| `ROUND3_TYPOGRAPHY` | PASS (7/7 families, 0 failed) |
| `P3_SEMANTICS` | 8/8 |
| `P3_HORIZONTAL` | 8/8 |
| `P3_RULE_ACCOUNTING` | matched 8 / lost 0 / invented 0 / out_of_tolerance 0 / invariants [] |
| `REFLOW_AWARE_V1` | PASS (15 plans, max residual 0.70–0.71 pt ≤ 2.0) |
| `CASE001_AUTOMATED_REGRESSION` | PASS |
| `CASE002_REGRESSION` | PASS |
| `CASE003_REGRESSION` | PASS |
| `THREE_CASE_GENERALIZATION` | PASS |
| `MANUAL_WORD_REVIEW_REQUIRED` | true |
| `V1_PRODUCTION_CANDIDATE` | false |
| `READY_FOR_SUBMISSION` | false |

## 2. The contract that was never allowed to move

Frozen, unchanged, not re-baselined anywhere in this round:

| Rule | Transformation policy | Geometry intent | Source span (pt) | Tolerance |
| --- | --- | --- | --- | --- |
| `P42-R1` | `PLACEHOLDER_REPLACED_BY_VALUE` | `ANCHOR_START_ONLY` | 94.80 – 194.60 | 2.0 pt |
| `P42-R2` | `PLACEHOLDER_REPLACED_BY_VALUE` | `ANCHOR_START_ONLY` | 198.10 – 375.70 | 2.0 pt |
| `P42-R3` | `FIXED_EMPTY_SLOT` | `EXACT_SOURCE_SPAN` | 169.65 – 323.60 | 2.0 pt |
| `P42-R4` | `FIXED_EMPTY_SLOT` | `EXACT_SOURCE_SPAN` | 384.60 – 459.00 | 2.0 pt |
| `P42-R5` | `RESOLVED_VALUE_IN_FIXED_SLOT` | `ANCHOR_START_ONLY` | 131.85 – 181.40 | 2.0 pt |
| `P42-R6` | `RESOLVED_VALUE_IN_FIXED_SLOT` | `ANCHOR_START_ONLY` | 95.25 – 151.05 | 2.0 pt |
| `P42-R7` | `SOURCE_VALUE_UNDERLINE` | `EXACT_SOURCE_SPAN` | 352.80 – 388.80 | 2.0 pt |
| `P42-R8` | `PRESERVE_SOURCE_PLACEHOLDER` | `EXACT_SOURCE_SPAN` | 112.80 – 208.80 | 2.0 pt |

Authority order used for every Word-flow conflict, unchanged:
1. source-visible form geometry, 2. the frozen P3 horizontal contract, 3. fact
completeness and reading order, 4. source visual-line semantics, 5. Word
paragraph continuity. A paragraph boundary is admissible when the frozen geometry
requires it; a builder-created `<w:br/>` never is.

The frozen closure gate `scripts/v09_p3_closure_gate.py` reports its own rows with
the **production** registry, which lists `P42-R6` as `FIXED_EMPTY_SLOT` /
`EXACT_SOURCE_SPAN` (identical in the Round-2 baseline and in every Round-3 build).
That difference from the contract listing above is disclosed in §8 and is not
hidden: the delivered `P42-R6` ink satisfies **both** readings (§3).

## 3. Stage A — same-build endpoint measurement

Written by `scripts/v1_round3_p3_reconciliation_diagnostic.py` (new) to
`acceptance/reports/v1_generalization/case001_round3_p3_contract_reconciliation_diagnostic.json`.
Both builds are measured inside one run, with the same measurement code, on the
same source page (42 → generated page 3):

| Rule | Endpoints owed | Source span | Pre-reconciliation painted | Pre error | Reconciled painted | Reconciled error |
| --- | --- | --- | --- | --- | --- | --- |
| `P42-R1` | start anchor | 94.80 – 194.60 | 94.90 – 286.90 | 0.10 | 94.90 – 286.90 | 0.10 |
| `P42-R2` | start anchor | 198.10 – 375.70 | 198.20 – 523.50 | 0.10 | 198.20 – 523.50 | 0.10 |
| `P42-R3` | both | 169.65 – 323.60 | 238.80 – 323.90 | **69.15** | 169.65 – 322.70 | **0.90** |
| `P42-R4` | both | 384.60 – 459.00 | 385.60 – 463.00 | **10.05** | 384.60 – 458.90 | **0.10** |
| `P42-R5` | start anchor | 131.85 – 181.40 | 131.85 – 182.25 | 0.00 | 131.85 – 182.25 | 0.00 |
| `P42-R6` | start anchor | 95.25 – 151.05 | 94.90 – 150.70 | 0.45 | 94.80 – 151.00 | 0.45 |
| `P42-R7` | both | 352.80 – 388.80 | 352.80 – 388.80 | 0.00 | 352.80 – 388.80 | 0.00 |
| `P42-R8` | both | 112.80 – 208.80 | 112.90 – 208.90 | 0.10 | 112.90 – 208.90 | 0.10 |

(For the pre-reconciliation build, `P42-R4` is measured on the rule's own run
`385.60 – 463.00`: its end was 4.00 pt beyond the source end because a justified
line stretched it, and the abutting neighbour underline that touched it added the
rest of the 10.05 pt the old inventory reported. Both facts are in the record.)

Per rule the diagnostic also records the representation the emitter used
(`SOURCE_RULE_COMPOSITION` with its segments, or `POSITIONED_BLANK` with
`emission_mechanism`, `anchor_tab`, `paragraph_origin_pt`, `reach_pt`,
`emitted_advance_pt`), the generated paragraph index, the delivered run identity
(text, underline, bold, alignment, hard-break count, spacing) and the measured
justification effect:

| Rule | Representation (reconciled) | Paragraph | Delivered line advance ratio | Rule geometry changed by justification |
| --- | --- | --- | --- | --- |
| `P42-R1` | positioned blank, anchored tab | 0 (element's own paragraph) | 1.000 | no |
| `P42-R2` | positioned blank, anchored tab | 0 | 1.000 | no |
| `P42-R3` | rule composition (empty rule segment, anchored) | 29 (isolated) | 1.000 | no |
| `P42-R4` | positioned underlined tab, anchor tab | 29 (isolated) | 1.000 | no |
| `P42-R5` | flow-placed resolved value | 0 | 1.000 | no |
| `P42-R6` | positioned underlined tab, anchor tab | 30 (isolated) | 1.000 | no |
| `P42-R7` | rule composition (forward-reachable) | 8 | 1.000 | no |
| `P42-R8` | rule composition | 11 | 1.000 | no |

**Reconciled accounting: matched 8, lost 0, invented 0, out_of_tolerance 0,
invariants `[]`.** The pre-reconciliation build measures matched 6,
out_of_tolerance 2 (`P42-R3`, `P42-R4`), invariants 2 (the same two rules).

## 4. Stage B — what each old disagreement actually was

The old inventory (`case001_underline_inventory_round3.json`, Round-2 measurement
model) reported `matched=5 lost=1 out_of_tolerance=2 invented=2`. Every one of
those five entries is explained against the build it measured:

| Old entry | Old measurement | Classification | Evidence |
| --- | --- | --- | --- |
| `P42-R3` `LOST` | no painted rule started at 169.65 | `ACTUAL_RENDER_REGRESSION` | the rule's own ink was 238.80 – 323.90, i.e. **69.15 pt** from the frozen source start; only the matcher's empty `observed` made it look merely "lost" |
| `P42-R4` `OUT_OF_TOLERANCE` (10.05) | 385.60 – 469.05 | `ACTUAL_RENDER_REGRESSION` | the rule's own run measured 385.60 – 463.00: its end was 4.00 pt past the source end on a justified line (the remaining 6.05 pt was the abutting neighbour's underline) |
| `P42-R6` `OUT_OF_TOLERANCE` (5.35) | 94.90 – 156.40 | `NEIGHBOUR_RULE_MERGE` | the rule's own run measured 94.90 – 150.70 (start 0.35, end 0.35, inside tolerance); the merged span included the next glyph's underline that touches it |
| invented `{238.80 – 323.90, y 209.8}` | "no source rule explains this ink" | `DOUBLE_ACCOUNTING` | the same ink is `P42-R3`'s own painted run, reported once as lost and again as invented |
| invented `{324.20 – 524.31, y 208.78}` | "no source rule explains this ink" | `DOUBLE_ACCOUNTING` | the span is the same underline line already measured for `P42-R3`/`P42-R4`; it is not drawn ink of its own (the page's raw segments contain no such segment) |

Classification counts: `ACTUAL_RENDER_REGRESSION` 2, `NEIGHBOUR_RULE_MERGE` 1,
`DOUBLE_ACCOUNTING` 2, `OTHER_PROVEN_CAUSE` 0.

So the old gate's failures were **not** all measurement debris: `P42-R3` and
`P42-R4` were real render regressions against the frozen contract. Two of the
four secondary findings (`R6` merge, the re-counted ink) were measurement-model
artefacts, and the measurement model was repaired anyway (§7).

## 5. Stage C — justification may not move a form rule

`P42-R4` no longer pays for justification: it is painted by a Word-native
positioned tab (anchor tab to the source `x0` 384.60, underlined leader tab to the
source `x1` 459.00), so the paragraph's justification cannot move either endpoint.
Measured after the fix: **384.60 – 458.90**, i.e. start 0.00 pt and end 0.10 pt
from the frozen span. `P42-R3` is painted by its own composed rule
(`169.65 – 322.70`: start 0.00, end 0.90).

No form rule is stretched, and no representation was invented to get there:
no underscore glyph filler, no shape, no textbox, no overlay — the delivered
document still has `generated_textbox_count 0`, `drawing_count 0`,
`blocking_overlap_count 0`, and the emitter's own record says which Word-native
primitive each rule used.

## 6. Stage D — paragraph boundaries the frozen geometry authorises

The reconciled build does **not** require the whole opening response letter to be
one Word paragraph. Two wrapped source rows whose own rules owe both exact
endpoints are assembled in their own paragraph context:

| Isolated paragraph | Rules | Reason recorded by the build | `space_before` | `space_after` | `<w:br/>` |
| --- | --- | --- | --- | --- | --- |
| 29 | `P42-R3`, `P42-R4` | `STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW` | 0.0 pt | 0.0 pt | 0 |
| 30 | `P42-R6` | `STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW` | 0.0 pt | 0.0 pt | 0 |

What the reader gets, measured on the rendered page:

* no builder-created hard line break: paragraphs 28/29/30 carry **0** `<w:br/>`
  elements, and no paragraph in the letter carries one;
* no spurious visible blank line: the letter's rendered line pitch is uniform
  (`21.10 / 20.73 / 21.47 / 21.92 pt` between consecutive rows; no doubled gap
  anywhere), because the isolated paragraphs have zero before/after spacing and
  carry the source-compatible line spacing;
* source reading order preserved: the boundaries fall where the source's own
  visual lines end (`…愿意` │ `以人民币（大写）…` │ `达到…。`), and
  `source_text_missing = 0`;
* typography/alignment correct: all three paragraphs keep the source's own
  justification (`JUSTIFY`), and every Round-3 typography family stays green (§7).

This is the Round-2 `STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW` mechanism,
narrowed to the rows that actually owe exact-span geometry: the row that carries
`P42-R5` — an `ANCHOR_START_ONLY` rule whose anchor flow keeps exactly — stays in
the element's paragraph and is placed by flow, exactly as before.

## 7. Stage E/F — the pipelines that must all stay green on this one build

| Gate | Script | Result |
| --- | --- | --- |
| Round-3 typography (7 families) | `scripts/v1_source_typography_round3_gate.py` | **PASS** — `hard_break_fidelity` 0/75 (1 authorised split), `paragraph_alignment` 0/73, `table_cell_line_structure` 0/51, `source_bold_fidelity` 0/29, `source_underline_fidelity` 0/6, `fixed_blank_fidelity` 0/34 |
| Frozen P3 closure (semantics + horizontal) | `scripts/v09_p3_closure_gate.py` | **PASS** — `failed_checks []`, `horizontal_failure_ids []`, `missing_frozen []`, `cross_page []`, composition preserved |
| P3 rule accounting (current gate) | `scripts/v1_underline_inventory.py` | **PASS** — matched 8 / lost 0 / invented 0 / out_of_tolerance 0 |
| Reflow-aware vertical authority | `scripts/v1_reflow_aware_regression.py` | **PASS** — 15 plans, max residual 0.71 pt ≤ 2.0 pt |
| P3 vertical (frozen absolute + reflow) | `scripts/v09_p3_reflow_vertical_gate.py` | reflow contract PASS (residual 0.71, 0 unexplained expansions); the legacy absolute phase stays red by design (§8) |
| Source-line assembly | `scripts/v09_source_line_assembly_gate.py` | **PASS** |
| Execution ownership | `scripts/v09_ownership_closure_gate.py` | **PASS** |
| P21 structural | `scripts/v1_p21_structural_gate.py` | **PASS** (77 classified, 1 composite slot, 0 failed) |
| Page frame | `scripts/v1_page_frame_audit.py` | **PASS** (22 pages, no per-page frame defect) |
| Case acceptance | `scripts/v1_case_acceptance.py` | **PASS** for case_001/002/003 |
| Three-case generalization | `scripts/v1_three_case_regression.py` | **PASS** |
| Automated candidate | `scripts/v1_automated_candidate_gate.py` | **PASS** |
| Test suite | `scripts/run_pytest_sandbox.py` | see §9 |

### How the measurement implementation changed, without touching the contract

`scripts/v1_underline_inventory.py` — same tolerance (2.0 pt), same frozen source
spans, same policies and geometry intents; only how a rule's painted ink is
*measured* is current:

* a rule's ink is read from the page's **own drawn segments**, not from
  `geometry_rule_qa`'s merged logical underline — merging is what reported a
  blank's underline together with the next glyph's underline;
* a rule owns the run **seeded at one of its own source endpoints** and grown
  through segments that touch it without overlapping: a composed rule's abutting
  segments are one rule, while a neighbouring glyph's underline that *overlaps*
  the run belongs to that neighbour;
* candidates are ranked `(inside tolerance, distance from the source line,
  deviation)`, so a same-width rule further down the page can no longer be
  mistaken for this one;
* a rule that owns no ink is reported against the **nearest** painted span with
  both endpoint errors, instead of an empty record;
* leftover ink is split into fragments of an already-measured rule's underline
  (disclosed, never counted as a rule) and genuinely unexplained rules (counted
  as invented).

`scripts/v1_source_typography_round3_gate.py`:

* `HARD_BREAK_FIDELITY` now measures the Stage-D contract instead of the
  paragraph count: a `<w:br/>` inside the element's prose, an empty paragraph
  between fragments, paragraph spacing on a fragment, or a split the build did
  not record as `STRUCTURAL_ISOLATION_…` are failures; a recorded isolation with
  zero spacing and no break is an authorised split and is reported as
  `authorized_splits`;
* fragment runs are matched in order (characters consumed from where the previous
  fragment stopped), so two paragraphs that repeat the same text cannot be read as
  one element split in two;
* `FLOW_PLACED_RULE_ENDPOINTS` is **diagnostic metadata only**: it no longer
  contributes a failure, because a second, weaker endpoint model must not stand in
  for the frozen contract. Its observation (1 flow-placed rule, `P42-R5`, anchor
  error 0.00 pt) is still published under `measurements`.

The production change is one row-scope decision, in
`tender_basic/word_style_source_builder.py`:
`_row_is_its_own_source_line(plan, element_row_count)` isolates a wrapped row when
one of the row's own registered rules owes both endpoints
(`source_rule_geometry_intent(policy) == EXACT_SOURCE_SPAN`, derived through the
same function that annotates the registry, so the decision and the delivered
registry cannot disagree), and leaves every other wrapped row in the element's
single paragraph. `tender_basic/word_safe_source_builder.py` honours that decision
when choosing the blank representation (`self._row_owns_line_context`): an isolated
row uses the source-positioned representation, a flow-placed row keeps the inline
one. Round-3 typography, cells, bold and blank behaviour are untouched.

## 8. Contract notes (disclosed, not silently reconciled)

1. **`P42-R6` policy listing.** The frozen contract listing in this round names
   `P42-R6` as `RESOLVED_VALUE_IN_FIXED_SLOT` / `ANCHOR_START_ONLY`; the production
   registry — identical in the Round-2 baseline and in all Round-3 builds — names
   it `FIXED_EMPTY_SLOT` / `EXACT_SOURCE_SPAN`, and the source has no resolved fact
   for that slot (the delivered blank is empty, exactly as the source drew it).
   Both readings are satisfied by the delivered ink: start 0.45 pt (≤ 2.0) and end
   0.05 pt (≤ 2.0), with the row isolated so the stricter reading also holds. The
   difference is recorded in the diagnostic as
   `contract_registry_notes`, and `invariants` is empty because nothing measured
   violates either reading.
2. **Legacy absolute vertical gate.** `v09_p3_reflow_vertical_gate.py` still
   reports the frozen *absolute* phase red (`P42-R1/R2/R5/R7/R8`, max raw y error
   50.37 pt, raw 65.79 pt on the audit page). That is the frozen consequence of
   mandatory reflow of the recorded long project name and values, and it is not
   normalised or re-baselined here: `REFLOW_AWARE_V1` is the vertical authority
   (residual 0.70–0.71 pt), and the reflow report itself states
   `mandatory_reflow_fully_explains_vertical_difference: true` with
   `unexplained_vertical_expansion_count: 0`. The exception covers vertical
   source-y reflow only — never a horizontal span.
3. **Vertical residual differences.** 0.70 pt in the dedicated reflow-aware
   regression and 0.71 pt in the gate are the two measurements of the same
   15-plan region taken by two scripts (row-origin versus region-origin); both are
   inside the frozen 2.0 pt tolerance.

## 9. Regression on the same build

* `case_001_round3_acceptance.json` — **PASS**: 22 pages, 0 blank pages, 3818
  extractable characters, LibreOffice returncode 0, `source_text_missing 0`,
  `blocking_overlap_count 0`, `duplicated_paragraph_count 0`, lost cells 0,
  duplicated cells 0, `generated_textbox_count 0`, `unsafe_generated_ooxml 0`,
  `resolved_without_evidence_fields []`, facts 16 `RESOLVED` / 6 `NOT_FOUND` /
  1 `NEEDS_REVIEW` (no fact invented or dropped).
* `case_002_round3_acceptance.json`, `case_003_round3_acceptance.json` — **PASS**
  on the rebuilt `v1_round3_p3reconciled` builds (32 and 33 pages), both pointers
  repointed to them.
* `three_case_regression_round3_reconciled.json` — **PASS**.
* `v1_automated_candidate_gate_round3_reconciled.json` — **PASS**
  (`V1_AUTOMATED_CANDIDATE`, `failed_checks []`), with
  `MANUAL_WORD_REVIEW_REQUIRED = true`, `V1_PRODUCTION_CANDIDATE = false`,
  `READY_FOR_SUBMISSION = false`.
* Full test suite: `python scripts/run_pytest_sandbox.py` — **505 passed,
  1 skipped, 0 failed**, including the new Round-3 contract tests
  (`tests/test_round3_source_typography.py`: 22 passed) that pin an authorised
  split as passing and an invented `<w:br/>`, a visible gap, an unspaced-authority
  split and paragraph spacing as failing.

## 10. Files

**Production:** `tender_basic/word_style_source_builder.py`
(`_row_is_its_own_source_line`, `_row_owes_exact_source_span`),
`tender_basic/word_safe_source_builder.py` (`_row_owns_line_context` honoured by
the positioned-blank path).

**Gates and evidence:** `scripts/v1_underline_inventory.py` (measurement model),
`scripts/v1_source_typography_round3_gate.py` (Stage-D hard-break contract,
`FLOW_PLACED_RULE_ENDPOINTS` demoted to diagnostics),
`scripts/v1_round3_p3_reconciliation_diagnostic.py` (new, Stage A/B),
`tests/test_round3_source_typography.py` (4 new contract tests).

**Reports:** `case001_round3_p3_contract_reconciliation_diagnostic.json`,
`case001_round3_p3_contract_reconciliation_status.json`,
`case001_round3_p3_contract_reconciliation.md` (this file),
`case001_p3_closure_round3_reconciled.json`,
`case001_underline_inventory_round3_reconciled.json`,
`case001_underline_inventory_round3_prep3reconciled.json`,
`case001_source_typography_round3.json` (PASS, 7/7),
`case001_source_typography_round3_baseline.json` (Round-2 baseline, FAIL 3
families — still discriminating), `case001_reflow_aware_round3_reconciled.json`,
`case001_p3_reflow_vertical_round3_reconciled.json`,
`case001_source_line_assembly_round3_reconciled.json`,
`case001_ownership_closure_round3_reconciled.json`,
`case001_p21_structural_gate_round3_reconciled.json`,
`case001_page_frame_audit_round3_reconciled.json`,
`case_001_round3_acceptance.json`, `case_002_round3_acceptance.json`,
`case_003_round3_acceptance.json`, `three_case_regression_round3_reconciled.json`,
`v1_automated_candidate_gate_round3_reconciled.json`.

## 11. What this round does not claim

Automation evidence only. The opening letter is still delivered as more than one
Word paragraph where the frozen geometry requires it (§6) — that is the authorised
trade in the authority order, and it is the one visible consequence a human
reviewer should look at first. `MANUAL_WORD_REVIEW_REQUIRED` stays **true**,
`V1_PRODUCTION_CANDIDATE` stays **false** and `READY_FOR_SUBMISSION` stays
**false**.
