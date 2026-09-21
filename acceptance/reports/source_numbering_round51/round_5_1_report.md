# Round 5.1 Governance Alignment + Source-First Hybrid Numbering

## GOVERNANCE_ALIGNMENT

Source Format First → Style System Second → Automation Third. ProjectFacts owns fact-valued content; validated SourceFormat evidence owns source structure and visible numbering; ReviewEvidence owns traceable review evidence; the fixture supplies editable Word infrastructure only.

## NUMBERING_ARCHITECTURE_CORRECTION

Source-owned headings and body lists retain their literal prefix and use Named Styles without automatic numbering. GENERATED_AUTO styles have an independent real Word numbering family and are not used by the source reconstruction path.

## CASE_RESULTS

- case_001: SOURCE_LITERAL=52; GENERATED_AUTO=0; prefix/punctuation/spacing/sequence=True/True/True/True; false-heading=True; status=ROUND_5_1_AWAITING_MANUAL_NUMBERING_CONFIRMATION.
- case_002: SOURCE_LITERAL=53; GENERATED_AUTO=0; prefix/punctuation/spacing/sequence=True/True/True/True; false-heading=True; status=ROUND_5_1_AWAITING_MANUAL_NUMBERING_CONFIRMATION.
- case_003: SOURCE_LITERAL=88; GENERATED_AUTO=0; prefix/punctuation/spacing/sequence=True/True/True/True; false-heading=True; status=ROUND_5_1_AWAITING_MANUAL_NUMBERING_CONFIRMATION.


## AUTOMATED_REGRESSION

All three cases passed source prefix, punctuation, spacing, sequence-dependency, outline, style architecture, editability, Generated-auto isolation, Word-safe and rendered-page checks. See each case's JSON artifacts for the complete record.

## TESTS

Full pytest suite: PASS; returncode=0. The project-local Python executable and JUnit path are recorded in `full_suite_junit.xml` and the JSON report.

## REQUIRED_MANUAL_CHECKS

Inspect `acceptance/manual_word_test_round51/01_case_001.docx`, `02_case_002.docx`, and `03_case_003.docx` in desktop Microsoft Word. Confirm normal open, navigation tree, style editability, literal source numbering, spacing/punctuation, source gaps, and the case003 ambiguous table-heading area.

## LOCKED_SCOPE

ProjectFacts=23; review items=64; normal pipeline artifacts=14. Round 5.1 adds acceptance/debug QA only and does not expand the normal artifact contract.

## STATUS

ROUND_5_1_AWAITING_MANUAL_NUMBERING_CONFIRMATION

No commit, push, or release was created. Historical Round 5.0 outputs were not overwritten.
