# Round 5.6 blockers

Status: `ROUND_5_6_BLOCKED`

## 1. Measurement-verification blocker (primary)

The Round 5.6 comparison harness (`scripts/run_round56_qa.py`) maps generated
page N to a source page and then compares drawn rules, blank geometry and
rendered glyph weight. Two defects in that harness prevent an automated PASS
verdict from being trustworthy:

- **Page alignment.** The tender body repeats the format-section cover text, so
  text-based source-page detection is ambiguous. The configured mapping
  (`source_start + N`, from the extracted format section) and the
  highest-similarity mapping disagree for case_002/case_003, which shifts every
  per-page comparison. Evidence: `round_5_6_report.json -> cases.*.source_offset`
  (`offset_conflict`).
- **Blank inventory asymmetry.** Source blanks are PDF *vector rules*; generated
  blanks are Word *underline runs*, visible in a render only as figure-space
  spans. Rules that are table row separators, and figure-space runs the emitter
  creates for unresolved-but-fillable source slots, land on one side only and are
  currently counted as `lost_source_blank_count` / `invented_blank_count`. This
  is the dominant contributor to the residual blank counts (case_001 54/26,
  case_002 38/19, case_003 61/12).

Until both are resolved, `blank_fidelity_qa.json` and the
`section_geometry_qa.json` per-page rows must be read as *inventory evidence*,
not as a pass/fail proof. Every other gate (typography roles, fill patterns,
quotation blanks, logical tables, package integrity, delivery bundles) is
render-independent or anchored, and passes.

## 2. Residual fidelity work not completed

- Generated fill regions that have no source rule on the same baseline
  (`invented_blank_count`): the emitter still creates underlined fill runs for
  some source slots whose source presentation is a plain whitespace gap.
- Source rules that the emitted tables do not reproduce as text blanks
  (`lost_source_blank_count`): quotation-table interior blanks and case_003 form
  grids.
- case_001 quotation totals/signature region rule matching
  (`quotation_total_blank_loss_count` 8, `quotation_signature_blank_loss_count` 4)
  is reported by a region heuristic that compares vector rules with underline
  runs; it needs the same alignment fix as (1).

## 3. Environment

- `WORD_COM_ENVIRONMENT_BLOCKED`: no Microsoft Word COM automation was attempted
  (no `OpenAndRepair`, no repair-save). Final visual acceptance stays with the
  human Word inspection.

## 4. What is verified

- Source-derived section geometry: margins/usable width are computed per source
  page from the source body bounds and no longer hard-code 18 pt
  (`tender_basic/source_page_geometry.py`).
- Source visual typography: role weights are measured from rendered glyphs and
  drive the Named Style weight, per role, without globally bolding headings
  (`tender_basic/source_visual_typography.py`, `style_architecture.py`).
- Source fill patterns: `tender_basic/source_fill_patterns.py` is inferred from
  the source rows and consumed by the production builder
  (`fill_pattern_usage` in `generation_report.json`).
- Blank representation: source drawn rules become one continuous underlined
  Word run instead of an underscore tab leader (`blank_representation_usage.solid_rule_blanks`).
- 14 tests in `tests/test_round56_source_visual_fidelity.py` plus the
  form-layout/paragraph-native/source-format/word-safe suites pass.
