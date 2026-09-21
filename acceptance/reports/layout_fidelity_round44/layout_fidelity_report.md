# Round 4.4 engineering validation report

Status: ROUND_4_4_AWAITING_MANUAL_LAYOUT_CONFIRMATION. Not a release approval.

## Layout root cause

Round 4.3 converted PDF visual lines to hard breaks/tabs, used universal spacing and fixed margins, and misclassified symmetric prose as centered. Blank PDF spans also distorted cover geometry and font selection. Word suppresses paragraph space-before after page breaks, so page-local Section margins now preserve top bands.

## Implementation

SourcePageLayout captures source geometry, logical paragraph boundaries, original offsets and page classification. PDF spans and vector rules are read directly. The renderer still starts with Document() and uses only the accepted Word-safe APIs; the XML whitelist is unchanged. No facts, review rules, workbook logic, requirements or packaging were changed.

Logical paragraphs join wrapped Chinese lines, preserve numbered boundaries and infer first-line indentation and line pitch. Page-local sections preserve source page boundaries. Tables remain editable and page-local, with source-derived widths and minimum row heights. Signature/date rows use borderless tables. Vector-backed inline blanks are restored conservatively; underscores are an intentional fallback where underlined spaces disappear.

## Environment and tests

See environment.json for the recorded system-Python/LibreOffice fingerprint. check_env.py and export_schema.py passed before generation. TEMP and TMP were project-local. The skill renderer lacked pdf2image; the explicitly authorized local LibreOffice fallback produced PDFs, and existing PyMuPDF produced PNGs. No dependency was added.

Full regression: 174 passed, 1 skipped in 26.79s. The skip is the optional desktop Word COM test. See pytest.xml. All three production files passed the unchanged Word-safe scan, ZIP/XML checks and python-docx reopen. All frozen facts/review artifacts are byte-identical to Round 4.3.

## Measured results

| Case | Source/generated pages | Major Y median pt | Title X center median pt | Manual breaks before/after | Table width max pt | Column ratio max |
|---|---|---|---|---|---|---|
| case_001 | 22/22 | 0.852 | 0.216 | 30/0 | 0.310 | 0.300% |
| case_002 | 31/31 | 1.314 | 0.444 | 401/0 | 0.290 | 0.271% |
| case_003 | 33/33 | 0.646 | 5.805 | 31/0 | 0.337 | 0.362% |

All three have 0 layout tabs and 0 repeated-tab hacks. Source editable tables matched: 5/5, 22/22, 16/16. Additional tables are borderless form rows, not replacement tender tables. No text scaling was needed (1.00); configured scaling is bounded to 0.94–1.03. A general automatic overflow-calibration loop remains a limitation; these three real outputs fit without it.

The major-anchor set is short, uniquely matched titles/form headings, not every body clause containing the words “bid document”. Every matched anchor, including outliers, is retained in JSON. All-anchor maximum Y errors are 44.891, 65.198 and 15.822 pt; title medians must not be interpreted as full-page fidelity. Aggregate rendered-line deltas include table cells, filled values and editable blanks and are not semantic paragraph-equality scores.

## Visual review and remaining limitations

All 86 generated pages were reviewed in contact-sheet overview; representative cover, form and table comparisons were inspected in detail. This is not a claim of pixel-perfect replication or desktop Word layout approval. Publishing headers/watermarks/page numbers are excluded from the metrics where the source model identifies them.

### case_001

- FORM_BLANK_WIDTH_APPROXIMATED: signature/date underlines remain shorter than source vectors
- FONT_AND_WRAP_DIFFERENCE: cover title weight/wrapping and table-cell paragraph alignment differ

### case_002

- FORM_BLANK_WIDTH_APPROXIMATED: signature/date rows use safe underscore blanks
- TABLE_CHROME_FRAGMENT_NEEDS_REVIEW: deviation-table blank cells retain small platform-watermark fragments from the source model

### case_003

- FORM_POSITION_APPROXIMATED: some signature/date rows are centered rather than source-left positioned
- TABLE_HEADING_WRAP_DIFFERENCE: some appendix headings wrap, shifting the following table vertically

Font family mapping is centralized; metadata available from PDF is retained. PDF synthetic weight/glyph metrics are not fully reproduced. Some short blank widths, cell alignment and non-major paragraph positions differ. These are explicit visual-review warnings, not silently accepted exact matches.

## Outputs and scope

Each case has a fresh run_4_4_layout directory. The manual package acceptance/manual_word_test_round44 contains exactly 01_case_001.docx, 02_case_002.docx and 03_case_003.docx. PDFs, PNGs, geometry snapshots and QA are under this report directory. No prior run was overwritten, no Gold was read/created, no commit or release was performed.

Round 4.3 desktop Word normal-open remains unconfirmed. Round 4.4 desktop Word/layout confirmation remains a manual gate.
