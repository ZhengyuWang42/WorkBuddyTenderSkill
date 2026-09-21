# Round 4.2 Word OOXML forensic report

## ROOT_CAUSE

The Round 4.1 package was not failing because of one `w:tblpPr` position. A
static forensic comparison of the old generated package found several
independent WordprocessingML construction defects in `word/document.xml`:

- `w:pPr`, `w:rPr`, `w:tcPr`, and related property children were emitted in
  an order that did not follow the WordprocessingML schema;
- `w:br` was emitted directly under `w:p` instead of inside `w:r`;
- table border and cell-margin children were emitted with `w:start`/`w:end`,
  which are not the safe Transitional WordprocessingML children expected by
  desktop Word for these properties;
- the old floating-table `w:tblpPr` placement was also unsafe.

The Open XML SDK probe on old Round 4.1 files reported, before the final
repair, unexpected `w:color`, `w:spacing`, `w:start`, `w:tcBorders`, direct
`w:br`, and related schema errors. The project forensic scanner counted
1,605 / 3,870 / 8,061 schema/paragraph errors for case 001 / 002 / 003.

The current Round 4.2 documents have zero errors in the project forensic
scanner. The Open XML SDK 2.8.1 probe reports only its known `tblLook`
attribute-declaration warnings (6 per source table); the same warning shape
is present in ordinary `python-docx` packages and is not a dangling
relationship, malformed XML, or invalid table construction.

## AFFECTED_PART

The affected package part was primarily `word/document.xml`, including
nested `w:pPr`, `w:rPr`, `w:tblPr`, `w:trPr`, and `w:tcPr` nodes. Package
relationships, headers, footers, media, and content types were inspected as
well; the failing old package did not show a separate dangling relationship
root cause.

## INVALID_XML_OR_RELATIONSHIP

The old package was a readable ZIP and its XML parts parsed, but contained
schema-invalid WordprocessingML structure. The current packages have:

- ZIP integrity: PASS;
- XML parsing: PASS;
- required package parts/content types: PASS;
- relationship IDs/targets: PASS;
- duplicate drawing/bookmark/relationship IDs: none found;
- project forensic schema-order and structure errors: 0.

The scanner intentionally retains table-width warnings where PDF geometry
and the DOCX table grid are not exactly expressible; these are reported as
warnings, not silently treated as Word corruption.

## WHY_LIBREOFFICE_ACCEPTED_IT

LibreOffice is tolerant of recoverable WordprocessingML ordering and tree
errors and can normalize them while importing/rendering. Its successful
render therefore did not prove that the package was acceptable to desktop
Word.

## WHY_WORD_REJECTED_IT

Desktop Word validates the package more strictly at open time. The combined
property-order violations, direct paragraph break nodes, and unsafe border /
margin children were sufficient for Word to reject the old package even
though LibreOffice rendered it.

## GENERIC_FIX

The production source-format builder now:

1. inserts property children through explicit schema-order tables;
2. keeps every line break inside a `w:r`;
3. uses Word-safe Transitional `left`/`right` border and margin children;
4. emits safe editable tables and preserves merge/grid topology where it is
   reliably available;
5. runs the deep package scanner before delivery;
6. never opens/resaves the production package through LibreOffice as a repair
   step.

The repair-diff utility is available at
`scripts/compare_word_repair.py`, but no user-supplied Word “Open and Repair”
package was available in this round, so no fabricated repair diff was used.
The deterministic minimizer produced four diagnostic variants under
`acceptance/reports/diagnostics/round42/case_001/`; they are for targeted
manual diagnosis only and are not delivery files.

## MANUAL_ACCEPTANCE

`scripts/validate_word_open.ps1` performs a normal `Word.Application` open
only and does not count `OpenAndRepair` as a pass. In this automated session
Word COM activation returned `0x80070520` (“A specified logon session does
not exist”), so the generated Round 4.2 files still require the user's
manual desktop Word open confirmation.
