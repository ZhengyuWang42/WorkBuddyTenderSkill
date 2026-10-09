# Intermediate XLSX regression — root cause and release-gate status

HEAD `e3f6416` · scope: why committed PASS reports for the round9/10/11 intermediate
successors contradict current isolated FAIL results.

## Verdict

**`TRANSITIVE_INPUT_OR_CONTRACT_DRIFT`.** The frozen successor workbooks are re-audited
against today's **inherited delivered-item registry**, which has grown since those PASS
reports were written. The documented contract scopes rounds 9/10/11 as
`HISTORICAL / SUPERSEDED` and round 12 as the current authority, so the intermediate
failures are **archival**, not mandatory current release gates. No waiver is invented and
no historical report is rewritten.

## One root cause, two failing checks

Both failing checks come from a single condition — an item whose `_row(item)` is `None`
has no bound row, so it is counted unbound *and* contributes an empty cell address:

| check | file:line | rule |
| --- | --- | --- |
| `delivered_rows_read_from_final_cells` | `scripts/v1_review_workbook_round5_report.py:299-305` | PASS iff no item has `_row(item) is None`; detail `30/50 rows audited` |
| `rendered_row_provenance_persisted` | `scripts/v1_review_workbook_round5_report.py:953-958` | PASS iff every item resolves to a non-empty cell address |

## Row-level matrix

| artifact | expected | audited | unbound | named unbound | distinct cells | class |
| --- | --- | --- | --- | --- | --- | --- |
| round10 case_001 | 50 | 30 | 20 | DR028, DR029, DR039, DR012, DR034, DR001, DR018, DR019, DR024, DR035 (validator records only the first 10) | 31 | PROVENANCE_NOT_FOUND / SOURCE_MAPPING_MISMATCH |
| round11 case_001 | 50 | 49 | 1 | DR051 | 50 | PROVENANCE_NOT_FOUND / SOURCE_MAPPING_MISMATCH |
| **round12 case_001 (current final)** | 50 | **50** | **0** | — | 50 | **PASS** |

Cause distribution: `unbound_item_no_matching_row = 20`, and **zero**
`CELL_NOT_FOUND`, `CELL_VALUE_MISMATCH`, `EXTERNAL_FIXTURE_MISMATCH`,
`ROW_FILTERED_BY_CONTRACT` or `OTHER_WITH_EVIDENCE`. The gate persists only the first ten
unbound ids, so the remaining ten of round10's twenty are not named by the artifact; the
count is exact.

## Transitive dependency manifest

| role | path | identity |
| --- | --- | --- |
| INPUT_BYTES | `..._review_workbook10/投标项目复核表.xlsx` | `F0F2D94E0BDE5640…EFAAA33A4` — **identical to the hash inside the committed PASS report** |
| INPUT_BYTES | `..._review_workbook11/投标项目复核表.xlsx` | `EA07803616DFF09F…63100914C` — identical to the committed record |
| INPUT_BYTES | `..._review_workbook12_final/投标项目复核表.xlsx` ×3 | `034DEDBC…E1764`, `AC39ED76…2C7B87`, `1F0CA082…A061080` — current final objects |
| **GENERATED_OR_CACHED_STATE** | `self.items = list(self.r4.items)` — `round5_report.py:152` | **the drifted input**: the audited item registry is *inherited*, not read from the workbook |
| VALIDATOR_CODE | `scripts/v1_review_workbook_round5_report.py` | unmodified in this worktree |
| FIXTURE_CONTRACT | `round8_regressions.run_case → Round5/6/7Report` | only change this session is the optional `out_dir` parameter |
| RUNTIME_ENVIRONMENT | `.venv` python 3.14, same cwd | not a candidate — the current round-12 artifact passes this same code |

Workbook-byte drift is therefore **eliminated**; the drift is in the item registry the
checks consume.

## HEAD baseline

`NOT_RUN` — a separate disposable `e3f6416` checkout was not executed within budget. This
report therefore does **not** claim `BASELINE_REPRODUCED_FAILURE`; the classification
rests on input identity plus the documented artifact scopes.

## Committed PASS vs current FAIL

A committed PASS is historical evidence produced when the inherited item registry matched
the successor workbook it audited. Today's registry contains items the byte-frozen
successors have no rows for (round10: ~20, round11: `DR051`), so the same check reports
them unbound. Round 12's current final workbook has a row for every item and passes. The
historical PASS reports are neither rewritten nor relabelled.

## Documented scope (the decisive citations)

- `docs/V1_PROJECT_STATE.md:1064` — **第 12 轮（当前）**: current machine state is
  `review_workbook_round12_generalization.json` + `review_workbook_round12_case_00{1,2,3}.json`,
  locator contract `case00{1,2,3}_review_workbook12_gate.json` (43/43).
- `:1074` — **第 11 轮（HISTORICAL / SUPERSEDED）**, its successor builds byte-preserved.
- `:1078` — **第 10 轮（HISTORICAL / SUPERSEDED）**.
- `:1085` — **第 9 轮（HISTORICAL / SUPERSEDED）**.

```
ROUND9_INTERMEDIATE_MANDATORY  = false
ROUND10_INTERMEDIATE_MANDATORY = false
ROUND11_INTERMEDIATE_MANDATORY = false
```

## Current final acceptance (unchanged)

| gate | command | result |
| --- | --- | --- |
| locator | `v1_review_workbook_round9_gate_integrity.py --round12 --three-case --out-dir <iso>` | **PASS**, `EXACT_FORMATTER_OUTPUT`, 0 fuzzy, 0 semantic mismatches; 50/45/49 rows, 0 failures; `sha256_matches = true` ×3 |
| banked regressions | `v1_review_workbook_round12_regressions.py --three-case --out-dir <iso>` | **PASS**, all three cases r5/r6/r7 PASS, `ROUND5_FIXTURE_F = PASS` |

## Output isolation and historical integrity

Round9 8/8, Round10 12, Round11 13, Round12 13 reports written inside their isolated
directories; **zero** historical report bytes changed. arch3 and arch4 DOCX intact;
CASE001 HUMAN_PASS workbook untouched.

## Release-gate verdict

`MANDATORY_CONDITIONS_MET_WITH_ARCHIVAL_INTERMEDIATE_DISCREPANCY` — the current final
acceptance passes for all three cases, the intermediate failures are explained and
recorded as archival evidence, and no HUMAN_PASS or renamed PASS is claimed.
