# CASE001 Round 3 — Source typography and cell inline structure

> **Build superseded by the P3 contract reconciliation.** The defect fixes
> described in this report are carried, unchanged, into
> `acceptance/workspace/case_001/v1_manual_fidelity_round3_p3reconciled`
> (DOCX sha256 `0ac9f7bc1da34f1d32f5fe4aa444d2a1317a72a99589134972b8a49134fd39ab`,
> 7/7 typography families still green). The build named below is the
> pre-reconciliation build, measured there as the "before" side of the frozen P3
> endpoint diagnostic. See `case001_round3_p3_contract_reconciliation.md` and
> `case001_round3_p3_contract_reconciliation_status.json`.

**Build:** `acceptance/workspace/case_001/v1_manual_fidelity_round3_source_typography`
**DOCX sha256:** `3658bfcb6a4c9eae3d93398c6352113ba4db15f11fee2e899014df31d2643ec2` (22 rendered pages)
**Source:** `acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf` (61 pages)
**Round-2 baseline (unchanged, still banked):** `acceptance/workspace/case_001/v1_manual_fidelity_round2_p21fix`
**Nothing was committed or pushed.**

## 1. Status block

| Status | Result |
| --- | --- |
| `CASE001_SOURCE_TYPOGRAPHY_ROUND3_AUTOMATION` | PASS |
| `PARAGRAPH_ALIGNMENT` | CLOSED |
| `HARD_BREAK_FIDELITY` | CLOSED |
| `TABLE_CELL_LINE_STRUCTURE` | CLOSED |
| `SOURCE_BOLD_FIDELITY` | CLOSED |
| `SOURCE_UNDERLINE_FIDELITY` | CLOSED |
| `FIXED_BLANK_FIDELITY` | CLOSED |
| `CASE001_AUTOMATED_REGRESSION` | PASS |
| `CASE002_REGRESSION` | PASS |
| `CASE003_REGRESSION` | PASS |
| `THREE_CASE_GENERALIZATION` | PASS |
| `MANUAL_WORD_REVIEW_REQUIRED` | true |
| `V1_PRODUCTION_CANDIDATE` | false |
| `READY_FOR_SUBMISSION` | false |

## 2. The eight reported defects

| # | Defect | Evidence | State |
| --- | --- | --- | --- |
| 1 | builder-created hard break after `询比文件的全部内容，愿意` | `hard_break_fidelity` 75 checked / 0 failed; the response letter is one Word paragraph carrying no `w:br` and no builder paragraph split (baseline: 1 split element, page 42) | CLOSED |
| 2 | source body paragraph alignment JUSTIFY instead of LEFT | `paragraph_alignment` 73 checked / 0 failed, 4 justified paragraphs delivered — exactly the elements whose source rows fill the measure; baseline: 3 failures with 0 justified deliveries | CLOSED |
| 3 | response-appendix cell must keep `响应报价（元）` / `（不含税）` as its own internal lines | `table_cell_line_structure` 51 cells checked / 0 failed (baseline: 11) | CLOSED |
| 4 | source underline under the 90-day value in that table | `source_underline_fidelity` 6 checked / 0 failed; the delivered `90 日历天` value run is underlined | CLOSED |
| 5 | authorization-form `委托期限` fixed blank span incomplete | `fixed_blank_fidelity` 34 registered blank rules checked / 0 failed | CLOSED |
| 6 | quotation-table summary region: three source lines, source bold, blank underline spans, a break before `其中：税率：`, native Word cells | `table_cell_line_structure` (same family) + `source_bold_fidelity` + `fixed_blank_fidelity`; the cell is a native `w:tc` whose paragraph carries two `w:br` | CLOSED |
| 7 | reputation-page parenthetical note bold | `source_bold_fidelity` 29 checked / 0 failed | CLOSED |
| 8 | `供应商认为应附的其他材料` bold | `source_bold_fidelity` (same family) | CLOSED |

The gate is discriminating, not vacuous: run against the banked Round-2 build it reports
`FAIL` with `HARD_BREAK_FIDELITY` 1, `PARAGRAPH_ALIGNMENT` 3, `TABLE_CELL_LINE_STRUCTURE` 11,
`SOURCE_BOLD_FIDELITY` 29 (`case001_source_typography_round3_baseline.json`).

## 3. What the implementation does (generic, no reported string is hard-coded)

* **Source paragraph alignment** (`tender_basic/source_paragraph_alignment.py`, new): a source
  element is classified from its own rows — a row that fills the measure (advance ratio) is
  justified, a row at its natural advance is left, a single row carries no evidence — and the
  classification drives `w:jc`, instead of one global alignment.
* **One flowing paragraph per logical element** (`word_style_source_builder.py`): the source's
  own physical rows are the assembly unit for *content*, never a Word paragraph of their own, so
  no builder break is inserted inside flowing prose; a row that is not a source line is recorded
  in `source_visual_line_assembly_gaps` with the reason it stays in the paragraph.
* **Cell inline structure** (`word_style_source_builder.py`): a delivered table cell keeps the
  source cell's own internal lines — its rows become lines inside one paragraph — and the
  intentional break structure is preserved rather than collapsed.
* **Synthetic bold / underline fidelity** (`source_format.py`, `page_layout.py`,
  `document_parser.py`): bold and underlined source spans are read from the source runs (and the
  source's synthetic-bold strokes), and the delivered run carries the same formatting.
* **Fixed blank span** (`word_safe_source_builder.py`): a registered blank rule is emitted as a
  delivered blank over the same source span, and the render is re-measured.
* **Inline blank width** (`word_safe_source_builder.py`, `word_safe_xml.py`): a blank the flow
  has carried past its source `x0` is emitted at the flow cursor as whole figure spaces plus the
  run's own character spacing, so the painted width tracks the source rule's width instead of the
  nearest glyph count. The character-spacing element is authored only in the reviewed compatibility
  module (`set_run_character_spacing`), schema-ordered inside `w:rPr`.
* **Flow-cursor reach** (`word_safe_source_builder.py`): for a paragraph built from several source
  rows, the cursor's position is the end of the *last line the flow produced* (greedy wrap at the
  measure), not the advance of everything written so far — reading the whole advance reported a
  cursor past the page and forced every blank of such an element onto a cursor-only representation.

## 4. CASE001 regression

| Gate | Report | Result |
| --- | --- | --- |
| Acceptance | `case_001_round3_acceptance.json` | PASS (`AUTOMATED_RESULT PASS`) |
| Reflow-aware V1 | `case001_reflow_aware_round3.json` | PASS — 15 plans, max residual 0.70 pt ≤ 2.0 pt, all 15 rows accounted, order preserved |
| P21 structural | `case001_p21_structural_gate.json` | PASS — 77 classified, 1 composite slot, 0 failed |
| P21 follow-up | `case001_p21_followup_status.json` | PASS — `COMPOSITE_SLOT_UNDERLINE` / `INTRO_FIRST_LINE_INDENT` / `NUMBERED_PARAGRAPH_INDENT` all CLOSED |
| Underline inventory | `case001_underline_inventory_round3.json` | FAIL — see §6 (Round-2 row model, superseded by the new family) |
| Full test suite | — | 505 passed, 1 skipped, 0 failed |

The stable frame, the P3 execution ownership, `REFLOW_AWARE_V1`, the Round-2 vertical rhythm and
the P21 composite/first-line-indent semantics were not redesigned.

## 5. New gate family: flow-placed rule endpoints

`FLOW_PLACED_RULE_ENDPOINTS` (4 checked / 0 failed) states what the delivery still owes for a rule
that stands on a *wrapped row of one Word paragraph*: the flow owns where the rule starts, so only
one of the source rule's two endpoints can be held — and it must land within 2.0 pt. Both endpoint
deviations are recorded for every rule, not only the passing one. A rule the source's own text
covers is that text's decoration and moves with the text (`source_underline_fidelity` owns it);
two such rules (`P45-R4`, `P45-R5`, both `text_occupancy` 1.0) are excluded by name with that
reason.

## 6. Disclosures (open, measured, not hidden)

1. **Underline inventory on source page 42** — `5 matched / 1 lost / 2 out of tolerance / 2 invented`.
   The inventory models the Round-2 structure (one Word paragraph per source row), where every
   rule's source `x0` is reachable by a tab stop. Defect 1 removed that structure by review mandate,
   so the letter's wrapped rows are placed by flow and their rules can no longer start at their
   source `x0`. Measured on the final build: `P42-R1/R2/R5/R7/R8` exact (≤ 0.1 pt); `P42-R3`
   anchored at its source **end** (0.3 pt, start 69.15 pt into the flow); `P42-R4` start exact
   (1.0 pt) with the painted run stretched ~3 pt by the justified line it sits on; `P42-R6` start
   0.35 pt with the run's own width exact (55.80 pt) — the inventory's 5.35 pt reading merges the
   neighbouring 6 pt underline. The "invented" pair is `P42-R3`'s own leader (counted separately
   because its start moved) and the delivered `（小写）` value underline. This is disclosed as a
   Round-3 structural consequence, not presented as a pass; the new family above gates the endpoint
   the representation actually owns and reports both deviations.
2. **Contents entries are not bold** in the delivery although their source spans are synthetically
   bold: 30 entries are excluded from `source_bold_fidelity` under the builder's own contents styles
   (`Tender TOC`). Disclosed, non-gating.
3. **Reflow region ledger** — the accepted difference
   (`region_ledger_matches_the_baseline`) is the letter's region moving from per-source-row
   paragraphs to one flow region; accepted explicitly with the reason recorded in the report.
4. **`P42-R4` painted width** carries the justified line's own glyph stretch (~4%), which no
   glyph-run representation can avoid while the source's line is justified.
5. Automation evidence only: `MANUAL_WORD_REVIEW_REQUIRED` stays **true**,
   `V1_PRODUCTION_CANDIDATE` **false**, `READY_FOR_SUBMISSION` **false**.

## 7. Three-case generalization

`three_case_regression.json` = PASS, `V1_AUTOMATED_CANDIDATE` = PASS (0 failed checks), over freshly
rebuilt and re-accepted case_002 (`v1_round3_source_typography`, 32 pages) and case_003
(`v1_round3_source_typography`, 33 pages) with the case_001 build above; all three pointers were
repointed through `v1_point_build.py` so every recorded hash addresses the measured artifact.

## 8. Reconciliation addendum (Round 3, after this report was written)

This report's defect fixes stand. Two of its disclosures were consequences of a **real** geometry
regression, and both the regression and the measurement model behind the second were repaired
afterwards — see `case001_round3_p3_contract_reconciliation.md` for the full evidence.

1. **§6.1 and §6.4 are corrected.** The invariant gate reported `5 matched / 1 lost /
   2 out of tolerance / 2 invented` against the frozen contract. That was not only an obsolete
   measurement model: `P42-R3` really was painted 69.15 pt from its source start and `P42-R4`'s own
   run really ended 4.00 pt past its source end (`385.60 – 463.00` against `384.60 – 459.00`),
   because the row was placed by flow and by a justified line. Both are now exact
   (`169.65 – 322.70`, `384.60 – 458.90`) on the reconciled build, whose accounting is
   `matched 8 / lost 0 / invented 0 / out_of_tolerance 0`.
2. **The second "invented" entry is not the delivered `（小写）` value underline.** The page's own
   drawn segments contain no `324.20 – 524.31` segment at all: the entry was the same underline line
   the inventory already measured for `P42-R3`/`P42-R4`, counted twice. Classification:
   `DOUBLE_ACCOUNTING` (as is `P42-R3`'s own leader, the first invented entry), `NEIGHBOUR_RULE_MERGE`
   for the `P42-R6` 5.35 pt reading, and `ACTUAL_RENDER_REGRESSION` for `P42-R3`/`P42-R4`.
3. **§5's family is now diagnostic metadata only.** `FLOW_PLACED_RULE_ENDPOINTS` no longer contributes
   a failure: a weaker second endpoint model must not stand in for the frozen contract. It stays in
   `measurements` as disclosure (1 flow-placed rule: `P42-R5`, anchor error 0.00 pt).
4. **The letter's rows are isolated again where the frozen geometry needs it** (paragraphs 29 and 30,
   `STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW`, zero before/after spacing, no `<w:br/>`,
   uniform line pitch), which is also why the reflow ledger difference is accepted on the reconciled
   build.
