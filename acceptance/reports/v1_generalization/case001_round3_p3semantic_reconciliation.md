# CASE001 — FINAL P3 SEMANTIC-REGISTRY RECONCILIATION (Round 3, reconciliation 2)

Scope: make the production rule registry carry the **frozen authoritative P3 semantics**
for every one of the eight frozen rules, without restarting Round 3, without redesigning
rendering, and without touching the frozen table itself. The inconsistency under repair
was that the accepted build's registry reported `P42-R6` as
`FIXED_EMPTY_SLOT` / `EXACT_SOURCE_SPAN` while the frozen contract says
`RESOLVED_VALUE_IN_FIXED_SLOT` / `ANCHOR_START_ONLY`.

All evidence below is machine-generated from delivered artifacts.
`MANUAL_WORD_REVIEW_REQUIRED` stays **true**; this is automation evidence only.

* repository: `D:\PyCharmProjects\WBTenderSkill`
* baseline commit: `8de9e1f343a6643e11ea5c6c8e1df015dda123a5` (unchanged; nothing committed, nothing pushed)
* source: `acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf`
  (sha256 `8e2bfb00e1a0c595db16d179477d9a09769ab82e45f63d476c3c8c459d46aa27`, 61 pages)
* pre-reconciliation build (the build that exhibited the inconsistency):
  `acceptance/workspace/case_001/v1_manual_fidelity_round3_p3reconciled`
* reconciled build under test:
  `acceptance/workspace/case_001/v1_manual_fidelity_round3_p3semantics`

---

## 1. Stage A — where the semantics convert (no assumption)

`acceptance/reports/v1_generalization/case001_p3_r6_semantic_registry_diagnostic.json`
traces `P42-R6` through nine stages and records the value each stage carries. It was run
against **both** builds: the post-fix stages are recomputed in-process through production
code, and the pre-fix stages are read from the artifacts the pre-reconciliation build
actually wrote (the recomputation cannot reproduce the pre-fix plan, because the code is
already repaired — the diagnostic says so explicitly).

| # | stage | pre-reconciliation value | reconciled value |
|---|-------|--------------------------|------------------|
| 1 | source rule detection (source page 42) | rule at x 95.25–151.05, y 218.40 (glyph-free physical rule) | identical |
| 2 | glyph occupancy | no source text on the rule | identical |
| 3 | own visual line label | preceding text on the rule's own row = `达到` → no fact field binds | `达到` → own-line channel still names no field |
| 4 | structural neighbourhood | row-scoped channels only; the label `供货质量` ends the **wrapped row above** (row band 75, y 186.78), which no channel offered | the wrapped-row channel offers `供货质量` → `quality_target` |
| 5 | `SourceFormPlan` compile | `FIXED_EMPTY_SLOT`, no field | `RESOLVED_VALUE_IN_FIXED_SLOT` + `quality_target` |
| 6 | serialized normalized artifact + reload | geometry only, no P3 semantics (unchanged either way) | identical |
| 7 | execution ownership / application / value run | 0 owners, 0 applications, 0 value runs — the resolved fact was **absent from the delivered letter** (`达到\t。`) | 1 `SOURCE_FORM_LINE_OWNER`, 1 `SourceFillApplication` `VALUE_IN_FIXED_SLOT`, 1 value run anchored at x 95.25 |
| 8 | production registry | `FIXED_EMPTY_SLOT` / `EXACT_SOURCE_SPAN` | `RESOLVED_VALUE_IN_FIXED_SLOT` / `ANCHOR_START_ONLY` |
| 9 | QA + gates | both gates read the registry, so both reported the wrong semantics as *matching* (the painted ink 94.80–151.00 satisfied the fixed-empty reading within 0.45/0.05 pt) | closure gate measures the value run (start error 0.10 pt), inventory gates the start only |

**Root cause (evidence, not assumption):** the source letter wraps its sentence *after* the
label `供货质量`, so the slot that label belongs to sits at the end of the **next** source
visual row (`达到____。`). The field compiler had no channel for a label that ends the row
above: the own-line channel saw only `达到`, and the structural channels are row-scoped by
the accepted contract. The plan therefore fell back to `FIXED_EMPTY_SLOT` with no field, and
the registry — which faithfully mirrors the plan and derives `geometry_intent` from the
policy — reported `FIXED_EMPTY_SLOT` / `EXACT_SOURCE_SPAN`.

**The registry was not the original source of the error.** Not the cause: the registry, the
serialized normalized artifact (geometry only), the execution owner (which correctly declined
to own an unplanned value), and the QA/gate representation (both read the registry).
The divergence is introduced one stage earlier, in field binding.

## 2. Stage B — the generic fix

`tender_basic/page_layout.py` gains one **last-resort evidence channel** in
`source_rule_structural_context`, offered after the own-line and nearer structural channels
fail to bind:

* `_wrap_continuation_row_text(unified, owner)` — leaf text of the nearest visual row band
  above the rule's own band, returned only when that row exists, sits at most
  `_WRAP_CONTINUATION_MAX_BANDS = 12` bands (≈30 pt) above, and does **not** end with a
  sentence ender (`。！？；;!?`) or a label terminator (`：:`);
* `evidence["wrap_continuation_row_text"]` + a `wrap_continuation_row` candidate appended
  **last** (weakest channel);
* `compile_source_form_field_plans` consults that candidate only when the row's compact text
  ends with the compact hint (`_wrap_bound_label`).

Unchanged contracts: the single-distinct-field rule, the resolved-fact requirement, the
row-scoped ownership of every nearer channel. A wrap can therefore supply a **label**, never
a value. Generic by construction and by measurement:

* no `P42-R6` (or page/case/value) literal anywhere in `tender_basic/`;
* blast radius over the whole case_001 build: 24 compiled plans vs 24 recorded plans,
  **exactly 1 plan changed** (R6); case_002: 51/51, 0 changed; case_003 unchanged;
* R3/R4 stay `FIXED_EMPTY_SLOT` / `EXACT_SOURCE_SPAN`, R7/R8 stay exact-span, R1/R2 unchanged.

8 focused tests were added to `tests/test_round59_source_evidence_generalization.py`
(`_wrapped_row_plan` helper + 8 cases: label ends the wrapped row → offered; row ends its own
sentence → not carried; label terminator → not carried; far row (12 bands) → not carried;
wrapped label binds a resolved value; wrapped label for an unresolved field stays a fixed
empty slot; and the two negative binding cases).

## 3. Stage C — R6 is now executed from ProjectFacts

From the reconciled build's `generation_report.json`:

| rule | registry policy / intent | owner kind | application | emitted value | from ProjectFacts |
|------|--------------------------|------------|-------------|---------------|-------------------|
| P42-R5 (`duration`) | `RESOLVED_VALUE_IN_FIXED_SLOT` / `ANCHOR_START_ONLY` | `SOURCE_FORM_LINE_OWNER` (1) | `SFA3` `VALUE_IN_FIXED_SLOT` (1) | `30日历天` | yes |
| P42-R6 (`quality_target`) | `RESOLVED_VALUE_IN_FIXED_SLOT` / `ANCHOR_START_ONLY` | `SOURCE_FORM_LINE_OWNER` (1) | `SFA4` `VALUE_IN_FIXED_SLOT` (1) | `符合国家及行业有关标准、规范和询比文件要求` | yes |

Exactly one owner and exactly one application per rule → no duplicate execution across plan
iterations. The value equals `project_facts.json`'s resolved `quality_target`
(`符合国家及行业有关标准、规范和询比文件要求`); nothing was invented. R5 is used only as a
generic sibling: it satisfies the same class of contract through the same owner path.

## 4. Stage D — the rebuilt artifact

A rebuild was required because the registry policy feeds the emitted representation (the
registry is not the source of the error, but the plan it mirrors is what the renderer
executes). Fresh build
`acceptance/workspace/case_001/v1_manual_fidelity_round3_p3semantics`:

* DOCX `0ebfbda52bbc889b432bcff3ea67d26c7f0f1c5beac59c3e521e59294ae3da2b` (45 542 bytes)
* PDF `1b988e2a84ac78f5524c7d9bda4187caaf4606eb559d4721d92095b67d56f0ea`, 22 pages, 0 blank pages
* `generation_report.json` sha256 `7c193cdff8c571461f53c600f7aa55c36807d0c499701180b8f59089463fccc5`
* pipeline rc 0, LibreOffice render rc 0, facts 16 RESOLVED / 6 NOT_FOUND / 1 NEEDS_REVIEW

Content-level change against the pre-reconciliation build (whole-package diff of OOXML
parts) is **exactly one insertion**: `word/document.xml` only, and

```
供货质量达到\t。            →  供货质量达到\t符合国家及行业有关标准、规范和询比文件要求。
```

Rendering was **not** redesigned, and nothing was altered merely to move a hash:
the P3 geometry stays inside the existing frozen contracts (stage E), and the Round-3
typography families are unchanged (stage F). The one structural consequence is that the R6
row no longer needs its own isolated paragraph — the letter now carries **one fewer
paragraph boundary** (authorized splits 2 → 1, `isolated_paragraphs: [29]`).

## 5. Stage E — one P3 semantic-registry gate

`scripts/v1_p3_semantic_registry_gate.py` →
`acceptance/reports/v1_generalization/case001_p3_semantic_registry_gate.json` (**PASS**, no
failed checks). It embeds the frozen table as the contract under test and reads every other
input from a gate report produced on this build, so it can only disagree with artifacts.

| requirement | observed |
|---|---|
| `semantic_policy_match` | **8/8** |
| `semantic_intent_match` | **8/8** |
| `semantic_execution_binding` | PASS (R5/R6 owners + applications + values from ProjectFacts; no value for a non-value policy) |
| `p3_horizontal` | **8/8** (`horizontal_failure_ids: []`) |
| `p3_scope_complete` | 8 frozen rules emitted |
| `p3_rule_accounting` | matched **8**, lost **0**, invented **0**, out_of_tolerance **0**, invariants **[]** |
| `REFLOW_AWARE_V1` | PASS (residual 0.71 pt ≤ unrelaxed 2.0 pt; 0 unexplained extra rows; structural isolations 0) |
| execution ownership | PASS |
| source-line assembly | PASS |
| Round-3 typography | PASS |
| `gates_measured_the_same_build` | true |

Supporting measurements on this build:

* underline inventory — `source=8 matched=8 lost=0 invented=0 out_of_tolerance=0 PASS`;
  per rule: R1 94.90–286.90 (start 0.10), R2 198.20–523.50 (0.10), R3 169.65–322.70
  (0.00/0.90), R4 384.60–458.90 (0.00/0.10), **R5 131.85–183.05 (start 0.00, end 1.65)**,
  **R6 95.35–347.35 (start 0.10, end not gated — `ANCHOR_START_ONLY`)**, R7 352.80–388.80
  (0.00/0.00), R8 112.90–208.90 (0.10/0.10).
* frozen P3 closure gate, phase 2 (the committed P3 horizontal contract): PASS.

### Measurement repair made for honesty (no contract change)

* `scripts/v1_underline_inventory.py`: the endpoint-seeded run growth now absorbs an
  **overlapping continuation** that extends the run *inside the rule's own source window*
  (a renderer may split one underlined run into overlapping pieces). Tolerance, gated axes
  and width windows are unchanged; the guard that keeps a neighbouring glyph's underline
  reaching past the window out of the run is unchanged. This is what lets R5 report its true
  span 131.85–183.05 instead of the truncated 131.85–150.05.
* `scripts/v1_source_typography_round3_gate.py`: the diagnostic-only
  `flow_placed_rule_endpoints` family now excludes value-inserting policies and discloses
  them separately (`value_representation_rules`), because a resolved value is *anchored* at
  the source `x0` by its owner and is not a blank left to the flow. It previously matched a
  page-blind, y-blind painted rule for R6 and reported a blank that does not exist. The
  family is diagnostic-only and decides no gate either way.

## 6. Stage F — Round-3 typography preserved, regressions re-run

All Round-3 typography fixes are intact (gate PASS, no failed family):

| family | measured |
|---|---|
| hard-break fidelity | 75 checked, 0 failed, authorized splits 1, `isolated_paragraphs: [29]` |
| paragraph alignment | 73 checked, 0 failed, 5 justified delivered |
| table-cell line structure | 51 checked, 0 failed |
| source bold fidelity | 29 checked, 0 failed (30 contents entries excluded) |
| source underline fidelity | 6 checked, 0 failed |
| fixed blank fidelity | 33 checked, 0 failed |
| P21 composite underline + indents | PASS (77 classified, 1 composite slot, 0 failed) |
| page-frame audit | 22 pages, `pages_using_the_stable_frame 22`, 0 centered-heading outliers, 0 split source rows |

Shared production logic changed (`page_layout.py`), so the other two cases were rebuilt and
re-accepted:

| case | build | DOCX | pages | acceptance |
|---|---|---|---|---|
| case_001 | `v1_manual_fidelity_round3_p3semantics` | `0ebfbda5…` | 22 | PASS |
| case_002 | `v1_round3_p3semantics` | `255980b8…` | 32 | PASS |
| case_003 | `v1_round3_p3semantics` | `a5bc3f0c…` | 33 | PASS |

case_002's and case_003's DOCX differ from their predecessors in **ZIP packaging metadata
only** (every OOXML part is byte-identical), so no rendering changed for them. Three-case
architecture regression **PASS**; automated candidate gate **PASS**
(`V1_AUTOMATED_CANDIDATE`). Case-001 pointer repointed; both other pointers repointed.

Full suite: `scripts/run_pytest_sandbox.py -q` → **0 failures** (229 collected, 1 skipped,
exit code 0), after the 8 new focused tests plus the 45 focused Round-3/Round-59 tests.

## 7. Disclosures (nothing hidden)

1. **Legacy absolute vertical phase stays red — before and after.** Both the phase-3
   closure gate and `v09_p3_reflow_vertical_gate.py` fail the *frozen absolute* vertical
   model (`no_absolute_positioning`), on the pre-reconciliation build as well as this one.
   This is the documented mandatory-reflow consequence, and `REFLOW_AWARE_V1` is the vertical
   authority — and it is PASS (residual 0.71 pt, 0 unexplained rows, structural isolations 0).
   The phase-3 *failure id list* changed (pre: R1, R2, R5, R7, R8; post: R3, R4, R5, R6, R7,
   R8) because R6 is now measured through its value run's text band instead of the painted
   blank's decoration y, which shifts the gate's origin-cluster election from −52.5 to −2.13.
   The gate's own origin election is unchanged code; both readings fail the same two checks.
   No geometry was rebaselined and no tolerance was weakened to hide this.
2. **The reflow-aware ledger change is accepted, not ignored**: R6's structural isolation is
   gone (structural isolation count 0), which is the strict improvement the frozen semantic
   contract implies. The acceptance reason is recorded in the report itself.
3. **Two gate-script measurements were repaired** (section 5). Neither changes a contract, a
   tolerance, or the accepted rendering; both make a report stop contradicting the artifact.
4. The previous round's status file already *asserted* the frozen table with R6 =
   `RESOLVED_VALUE_IN_FIXED_SLOT` / `ANCHOR_START_ONLY`, while the artifact carried
   `FIXED_EMPTY_SLOT` / `EXACT_SOURCE_SPAN`. That gap is what this round closes: the assertion
   is now true of the build.

## 8. Status

```
CASE001_P3_SEMANTIC_REGISTRY_RECONCILIATION = PASS
P3_SEMANTIC_POLICY   = 8/8
P3_SEMANTIC_INTENT   = 8/8
R6_POLICY            = RESOLVED_VALUE_IN_FIXED_SLOT
R6_INTENT            = ANCHOR_START_ONLY
P3_HORIZONTAL        = 8/8
P3_RULE_ACCOUNTING   = 8/8  (matched 8 / lost 0 / invented 0 / out_of_tolerance 0 / invariants [])
REFLOW_AWARE_V1      = PASS
ROUND3_TYPOGRAPHY    = PASS
CASE001_AUTOMATED_REGRESSION = PASS
CASE002_REGRESSION   = PASS
CASE003_REGRESSION   = PASS
MANUAL_WORD_REVIEW_REQUIRED  = true
V1_PRODUCTION_CANDIDATE      = false
READY_FOR_SUBMISSION         = false
```

Frozen semantic table: **unchanged**. No `P42-R6` special case in production. No geometry
rebaselined, no tolerance weakened, no ProjectFacts value modified, no Round-3 typography
architecture reopened. Nothing committed, nothing pushed.
