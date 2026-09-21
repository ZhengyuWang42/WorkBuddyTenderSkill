# Round 4.3 Word-safe rebuild

## Architectural reset

Every production source DOCX now starts from a clean python-docx Document().
No old DOCX was loaded, repaired, resaved or used as a template. The old custom
OOXML emitter is diagnostic only. Public APIs create paragraphs, inline tables,
rectangular merges, widths, minimum row heights, run breaks and sections.
Private operations are centralized in word_safe_xml.py; it creates no arbitrary
elements or relationships. It sets East Asian font attributes and removes the
default template's unused bibliography/customXml relationship.

## Actual gates

| Case | Source pages | Rendered pages | Editable tables | Filled slots | Static/reopen/render |
|---|---:|---:|---:|---:|---|
| case_001 | 22 | 22 | 5 | 2 | PASS |
| case_002 | 31 | 33 | 22 | 5 | PASS |
| case_003 | 33 | 33 | 16 | 0 | PASS |

All four manual targets pass ZIP integrity, XML parsing, relationship forensics,
python-docx reopen and the Word-safe whitelist. Forbidden elements and
relationships are empty; unsafe table positions, paragraph-level breaks, styles
and sections are zero. Relationship authorship cannot be inferred from ZIP
bytes; production source API tests enforce no manual relationship creation.
Canary has three pages, including Chinese text, formatting, horizontal/vertical
merges, widths, minimum heights and mixed-page sections. LibreOffice renders it.

## Content and fidelity

Only RESOLVED facts with matching candidate values, evidence and valid types fill
source slots. Unknown/company fields remain unchanged. Fixed text is retained.
Identical PDF cell rectangles with identical text are rendered once using a
safe rectangular merge; distinct content causes degradation instead.
An existing chrome bug removed a real cover title merely because it matched
watermark text. Exclusion now uses the exact geometry-verified block locator;
timestamp matching retains the original whitespace before classification.
Synthetic tests cover both, with no project-specific conditions.

Intentional degradation: absolute positions become flow, exact source indents
become margin-relative bounds, line spacing is single, borders use Table Grid,
row heights are minimums, vector artwork/underlines are omitted, and page breaks
can add table continuations. Source font names are retained but installed-font
availability is not certified. The case_002 quotation table produces two short
continuation pages. These are not blank pages or clipped content.

Visual QA: all-page contact sheets plus full-size representative pages were
inspected against source PDF pages. This does not certify pixel-level fidelity.
Source reference/output images and PDFs are under reports/debug/round43, outside
the delivery directories. No OCR, RAG, external LLM or Gold was used.

## Frozen review and facts

For every case, project_facts.json, the XLSX and all copied review evidence
artifacts are byte-identical to run_4_2. No review rule/ranking code was changed.
Baseline and all previous run directories were not written by this workflow.

## Manual Word acceptance

acceptance/manual_word_test contains only 00_word_safe_canary.docx,
01_case_001.docx, 02_case_002.docx and 03_case_003.docx. These are the exact
scanned output bytes. The minimal environment control is tmp/99_hello.docx;
only add it to manual tests if the canary also fails.

Microsoft Word desktop normal-open remains UNCONFIRMED. COM was not retried.
All four files must open without error, repair or recovered-content prompts.
No commit or release was performed.

FINAL_STATUS: WORD_SAFE_REBUILD_AWAITING_MANUAL_CONFIRMATION
