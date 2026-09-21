# Word OOXML integrity Round 4.1

## ROOT_CAUSE

The Round 4 source-format builder appended `w:tblpPr` after the existing
`w:tblW`, `w:tblLayout`, and `w:tblLook` children of each `w:tblPr`.  The
generated package was ZIP-valid and every XML part parsed, but the table
property sequence was not schema ordered.  This was present in all three
Round 4 generated DOCX files.

## AFFECTED_PART

`word/document.xml`, in every floating source-format table's `w:tblPr`.

Observed legacy order:

```text
tblW, tblLayout, tblLook, tblpPr
```

Round 4.1 order:

```text
tblpPr, tblW, tblLayout, tblLook
```

The affected table counts were case_001: 5, case_002: 22, and case_003: 16.

## INVALID_XML_OR_RELATIONSHIP

The XML was well formed and the package relationships were not dangling.  The
read-only scanner found no ZIP CRC failure, missing relationship target,
duplicate relationship ID, duplicate `wp:docPr` ID, or orphan bookmark.  It
did find the invalid `w:tblPr` property order in the legacy packages:

| package | scanner result | schema-order records |
| --- | --- | ---: |
| case_001 Round 4 | FAIL | 10 |
| case_002 Round 4 | FAIL | 44 |
| case_003 Round 4 | FAIL | 32 |
| all three Round 4.1 | PASS | 0 |

The two records per table in the legacy count are the `tblpPr`-before-`tblW`
and `tblpPr`-before-`tblLook` checks.

## WHY_LIBREOFFICE_ACCEPTED_IT

LibreOffice accepted the package and rendered the tables because its import
filter is tolerant of this property-order defect and can normalize the table
properties while importing.  A successful LibreOffice conversion therefore
did not prove that the original OOXML was acceptable to Word.

## WHY_WORD_REJECTED_IT

Desktop Word validates the OOXML property sequence more strictly during the
normal open path.  The legacy package's out-of-order `w:tblpPr` was enough to
produce the reported Word open/repair error even though the ZIP and XML syntax
were valid.

The required Word COM gate was also run.  In this managed automation session
Word could not be activated and returned `0x80070520` (the logon session does
not exist), so this environment cannot independently report a normal-open
PASS.  That is recorded as an acceptance blocker rather than treated as a
document PASS.

## GENERIC_FIX

Create `w:tblpPr` before the first existing `w:tblPr` property instead of
appending it.  Keep the property values source-derived and retain the table as
an editable DOCX table.  The fix is in
`tender_basic/source_docx_builder.py`; the independent package scanner is in
`tender_basic/word_ooxml.py`, and the Windows normal-open helper is
`scripts/validate_word_open.ps1`.
