# Round 5.2 — Word package integrity and source-owned visual fidelity

Final status: `ROUND_5_2_BLOCKED`.

## Package integrity

All three fresh production-path DOCX packages pass ZIP/XML, relationship target, content-type target, style, numbering, header/footer, note dependency, schema-order, unsafe-OOXML, and python-docx reopen checks. `footnotePr`, `endnotePr`, `footnotes.xml`, and `endnotes.xml` are absent. Normal Word COM open passed for all three files without OpenAndRepair; user-owned desktop visual acceptance is not claimed.

## Required list geometry

- case001 P3: source 94.80 pt, generated 94.90 pt, error +0.10 pt — PASS.
- case002 P3: source 94.92 pt, generated 95.00 pt, error +0.08 pt — PASS.
- case003 P4 outer: source 75.85 pt, generated 75.95 pt, error +0.10 pt — PASS.
- case003 P4 nested: source 90.88 pt, generated 90.95 pt, error +0.07 pt — PASS.

## Required typography and glyphs

- case001 P1 project-number row: source reference center 297.65 pt; generated 297.75 pt; error +0.10 pt — PASS. The filled value is not underlined.
- case002 P1 `投标文件`: source FangSong_GB2312 36.00 pt; generated FangSong 36.00 pt — PASS (mapped equivalent family).
- case002 project-number lines: source 14.05 pt; generated 14.00 pt — PASS.
- case001 P4: source/generated FangSong 12.00 pt — PASS.
- case002 P4: source FangSong_GB2312 12.00 pt; generated FangSong 12.00 pt — PASS.
- case001 P9 `智慧泵房箱体`: source/generated FangSong 12.00 pt — PASS.
- case001 P9 `水泵`: source SimSun 10.45 pt; generated SimSun 10.00 pt — PASS at 0.45 pt error.
- `800m³/h` and `300m³/h` use ordered semantic superscript runs; `不含税合价` is present and `不今税合价` is absent — PASS.

## Table visual geometry

- case001 P4 outer edges: source 65.21/524.69 pt; generated 65.15/524.85 pt — PASS.
- case002 P4 outer edges: source 56.56/539.89 pt; generated 56.45/540.05 pt — PASS.
- case002 P7 outer edges: source 54.11/542.34 pt; generated 54.05/542.45 pt — PASS.
- case003 P5 outer edges: source 54.83/539.96 pt; generated 54.95/540.65 pt — PASS (+0.12/+0.69 pt).

## Form geometry hard failures

Actual source and LibreOffice-rendered drawing segments were measured. The following pages retain shifted or incorrectly extended editable blanks and therefore fail the 2.0 pt audited-blank threshold:

- case001 P5 identity form.
- case002 P3 contact form.
- case003 P6 identity form.
- case003 P7 authorization form.

## Other regression evidence

Source numbering and navigation QA pass for all cases: prefix, punctuation, spacing, sequence dependency, false heading, TOC heading, body-list heading, and ambiguous promotion counts are zero. Synthetic layout tables and mid-sentence paragraph breaks are zero. The 23-field fact contract, 64 review-item contract, and normal 14-artifact pipeline contract remain unchanged. Case002 confirmed watermark/stamp strings do not leak into editable text. Quotation pages 8, 15, and 25 have source/generated comparison images and remain editable tables.

## Diagnostics and validation

- Page counts: case001 22/22, case002 31/31, case003 33/33. Diagnostic only.
- LibreOffice rendering: PASS for all three files. Not Microsoft Word visual proof.
- Microsoft Word normal COM open: PASS for all three files; no repair path used.
- Full pytest: 227 passed, 1 skipped (228 collected).
- `scripts/check_env.py`: PASS.
- `scripts/export_schema.py`: PASS.
- `git diff --check`: PASS (line-ending warnings only).

The automated package defect is fixed, but mandatory rendered form-blank geometry still fails. Under the fail-fast rule the only permitted final status is `ROUND_5_2_BLOCKED`.
