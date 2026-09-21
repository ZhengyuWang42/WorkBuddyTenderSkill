# Round 4.5 visual inspection

## Scope and acceptance meaning

All three DOCX files were rendered by local LibreOffice. Source/generated PDF pairs were inspected for the requested pages. Full-document contact sheets were also reviewed for pagination and gross overflow; they do not certify every glyph at full resolution. No Gold was used. Structural QA PASS is not a declaration of exact visual fidelity or desktop Word manual acceptance.

## case_001

Inspected generated pages 1, 3, 5, 6, 8 and 9 against their source PDF pages. Page 3's purchaser addressee is one rendered line. The response sentence and numbered continuations now flow as logical paragraphs. Page 5 labels remain ordered; page 6 supplier/representative labels no longer wrap into narrow cells. Signature rows are separate and left-anchored. Page 8 deviation table and page 9 quotation table remain editable.

Remaining differences: the cover's synthetic bold and title wrapping differ from the source. Several inline underlines are not fully reproduced, and dates/blank widths remain approximate. Quotation-cell typography and alignment are inherited from the frozen source-table renderer, not redesigned in this round.

## case_002

Inspected pages 1, 3, 5, 6 and 8; additionally inspected page 7's deviation table. Page 3's opening sentence and list items now remain logical paragraphs, including item 9 ending in 全部内容. Page 6's purchaser addressee is no longer artificially narrowed. The large quotation table remains page-local and editable.

Remaining differences: source bold and some form/date blanks are approximate. The pre-existing source-table extraction residue 平 台 / 交 易 目 remains in page 7's otherwise blank cells. This is an existing PDF chrome/table-content limitation, not a newly filled fact; it was not hidden by the logical-layout PASS or fixed by changing the frozen table strategy. Complex quotation-cell text spacing/alignment remains visibly different from the PDF. Manual layout acceptance is still required.

## case_003

Inspected pages 2, 4, 6, 7, 10 and 30, and reviewed the project-manager appointment page in the full-document overview. Bid-letter, authorization and commitment prose now use logical paragraphs rather than centered visual-line fragments. The chapter divider remains separate from the cover. Appendix catalog items on page 10 are separate rows, not concatenated into one sentence.

Four right-side signature rows required safe leftward adjustment to keep labels and annotations within the page: source pages 70 (20.57pt and 23.47pt), 71 (19.08pt), and 97 (12.77pt). These are explicitly recorded as FORM_ROW_X_DEGRADED_FOR_SAFE_WIDTH. The final page 4 render was rechecked: the signature annotation is visible, not clipped.

Remaining differences: some source blanks, date positioning and fixed table-cell alignment still differ. Page 6's multi-label physical row is retained as one row but its blank spacing is less faithful than the source. These limitations must be evaluated by the user in Word.

## Result

Logical structure corrections and automatic safety checks are complete. Visual results are improved but not certified as source-identical. Source and generated page counts match at 22/31/33. The final files are for manual layout confirmation, not release.

ROUND_4_5_AWAITING_MANUAL_LAYOUT_CONFIRMATION
