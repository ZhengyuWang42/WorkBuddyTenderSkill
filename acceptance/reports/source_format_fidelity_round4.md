# REAL CASE ROUND 4 — Source Format Fidelity

## WHY_RUN3_WAS_NOT_FORMAT_FAITHFUL

run_3 had recovered source section ordering and editable tables, but the DOCX
was still reconstructed from normalized text with generic paragraph geometry.
That lost the source PDF's direct span typography, baseline grouping, blank-line
placement, underline rules, page composition, and multi-line table-cell layout.
It therefore looked like a new Word document containing similar wording rather
than an editable rendering of the tender's own response-form template.

## SOURCE_FORMAT_ARCHITECTURE

Round 4 adds a geometry-aware `SourceFormatTemplate` built from the source PDF
pages, direct PDF spans, vector rules, page dimensions, editable tables, and
explicit source fill slots. The DOCX builder places source paragraphs and
tables at source-page coordinates, emits direct run formatting, uses fixed
table grids/row heights/merges, and creates section breaks when page geometry
changes. `SOURCE_DOCUMENT` starts at the detected source heading and does not
add a generic cover or generic ProjectFacts page.

Source format sections found:

| Case | Heading | Source locator | Pages | Tables |
|---|---|---:|---:|---:|
| case_001 | 第六章响应文件格式 | PDF page 40 | 22 | 5 |
| case_002 | 第六章投标文件格式 | PDF page 144 | 31 | 22 |
| case_003 | 第八章 投标文件格式 | PDF page 67 | 33 | 16 |

## PDF_FORMAT_EXTRACTION

Direct PyMuPDF span metadata is retained: source font name, repaired font
name when PDF encoding is malformed, size, bold/italic flags, color, bbox,
line bbox, source order, page size, and simple horizontal/vertical rules.
Table extraction retains cell text, row/column coordinates, relative widths,
row heights, and merge topology. Source QA reports zero missing or reordered
source text records for all three cases.

Repeated page markers, repeated watermark text, timestamps, and repeated
top/bottom text are excluded only by deterministic text/geometry repetition.
The counts are recorded in QA rather than hidden.

## TABLE_RECONSTRUCTION

All detected source tables remain editable DOCX tables. Final structural QA:

| Case | Source/generated pages | Source/generated tables | Merge topology | Geometry | Source/generated rules |
|---|---:|---:|---|---:|---:|
| case_001 | 22/22 | 5/5 | match | 1.0 | 47/47 |
| case_002 | 31/31 | 22/22 | match | 1.0 | 63/63 |
| case_003 | 33/33 | 16/16 | match | 1.0 | 54/54 |

Table cells retain source line breaks reconstructed from span baselines. Fixed
source values remain source content; they are not replaced merely because a
same-named ProjectFacts field exists.

## FILL_SLOT_MODEL

`SourceFillSlot` records slot id, semantic hint, source page/locator, container,
original text, prefix/suffix, source run formatting, geometry, match kind, and
allowed ProjectFacts fields. V1 recognizes underline, whitespace,
parenthetical, table-cell, and date/signature slots.

Final detected/filled counts:

| Case | Detected | Filled | Left blank |
|---|---:|---:|---:|
| case_001 | 12 | 2 | 10 |
| case_002 | 10 | 5 | 5 |
| case_003 | 17 | 0 | 17 |

The case_002 watermark contamination path and case_003 fixed-value/right-side
remark false slot were both blocked by regression tests. Multi-line table-cell
spans and the case_003 date rule are now preserved.

## FACT_FILL_POLICY

Only `ProjectFacts` values with `RESOLVED` status, valid field type, and a
confident source slot mapping can be inserted. `NEEDS_REVIEW` and `NOT_FOUND`
leave the source slot unchanged/blank. Bidder/company fields remain manual:
bidder name, representatives, bank account, contact, bid price, model/brand,
project manager, and enterprise qualifications are never invented.

Source-format text is not used to bypass ProjectFacts. Semantic candidate
augmentation remains evidence-bound: a proposal must name an allowed field,
point to a real normalized locator, quote matching evidence, use a direct or
deterministically normalized value, and pass the Python field validator before
resolver input.

## PDF_CHROME_POLICY

Repeated chrome exclusions are reported as layout warnings:

- case_001: 49 repeated items
- case_002: 118 repeated items
- case_003: 42 repeated items

case_002 also reports sizeable non-text PDF artwork on the source pages. It is
not silently treated as editable bid content; each occurrence is recorded as a
visual-review warning. Ordinary bid tables and thin source rules are not
classified as artwork gaps.

## VISUAL_QA

Each final DOCX was converted with LibreOffice in an isolated profile and
compared with source-format renders using PyMuPDF. Final reports:

- `acceptance/reports/debug/round4/finalcheck3/case_001/visual_qa.json` — 22/22 pages, no visual-QA warnings
- `acceptance/reports/debug/round4/finalcheck3/case_002/visual_qa.json` — 31/31 pages, no visual-QA warnings
- `acceptance/reports/debug/round4/finalcheck3/case_003/visual_qa.json` — 33/33 pages, no visual-QA warnings

Representative cover, response/bid letter, appendix/opening schedule,
authorization, deviation, quotation/detail, construction-organization, and
project-organization pages were rendered and manually inspected. The raster
metric is diagnostic and fill-slot masked; it is not treated as pixel identity.

## CASE_001_RESULT

`SOURCE_DOCUMENT`; source heading page 40; 22 pages and 5 editable tables;
2 constrained slots filled. Source fixed appendix content and signature rules
remain in the source layout. Delivery QA is `PASS_WITH_REVIEW` only because
ProjectFacts still contains review/supplement fields.

## CASE_002_RESULT

`SOURCE_DOCUMENT`; source heading page 144; 31 pages and 22 editable tables;
5 constrained slots filled. The opening schedule, bid letter, authorization,
deviation, and quotation/detail tables remain real tables. The watermark text
contamination and multi-line cell flattening regressions are fixed. Delivery
QA is `PASS_WITH_REVIEW` only because ProjectFacts still contains review/
supplement fields; non-text artwork warnings remain explicit in source QA.

## CASE_003_RESULT

`SOURCE_DOCUMENT`; source heading page 67; 33 pages and 16 editable tables;
no source slots were filled because the detected source blanks did not have a
confident RESOLVED ProjectFacts mapping. The fixed `90 日历天` source content
remains once in the table, and the signature date rule is retained. Delivery QA
is `PASS_WITH_REVIEW` only because ProjectFacts still contains review/supplement
fields.

## FACT_REGRESSION_STATUS

Final run_4 ProjectFacts counts are unchanged from run_3:

- case_001: 16 RESOLVED / 1 NEEDS_REVIEW / 6 NOT_FOUND
- case_002: 18 RESOLVED / 1 NEEDS_REVIEW / 4 NOT_FOUND
- case_003: 8 RESOLVED / 8 NEEDS_REVIEW / 7 NOT_FOUND

The run_3 deadline/open-time corrections, amount/form separation, unresolved
cross-reference behavior, owner/agency number ownership, common aliases,
multiline recovery, and source-format locator recovery remain intact.

## REMAINING_LIMITATIONS

1. PDF chrome cleanup is intentionally conservative and is visible in QA
   warnings. case_002 sizeable non-text artwork is recorded but not rebuilt as
   editable artwork; if a specific seal/scan mark is later confirmed as
   mandatory form content, it needs a scoped artwork-preservation extension.
2. PDF-to-DOCX typography and line wrapping are substantially source-derived,
   but Word/LibreOffice font metrics cannot guarantee pixel identity.
3. Unresolved facts remain human-review states; Round 4 does not broaden into
   full tender review or enterprise-profile completion.

Overall engineering result: `PASS_WITH_REVIEW` for the three delivery QA
reports, with source-format architecture and editable table reconstruction in
place.
