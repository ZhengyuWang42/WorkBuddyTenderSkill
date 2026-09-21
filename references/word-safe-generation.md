# Word-safe source generation

Production source rendering starts with python-docx `Document()` in
`word_safe_source_builder.py`. The older `source_docx_builder.py` is diagnostic
only: desktop Word rejected its output. Do not import it into a production
renderer and do not reuse its package parts.

The renderer uses Normal paragraphs, public run formatting and breaks,
Section APIs, `add_table`, proportional widths, minimum row heights,
`Table Grid` borders and rectangular `cell.merge`. Repeated PDF cells are
merged only when their identical text and bbox establish one physical cell.
Distinct text and subordinate fill slots force rectangular degradation.

## Source-first format and numbering

The source tender is the authority for source-owned structure and visible
formatting. `ProjectFacts` is the only authority for fact-valued fill content;
`SourceFormatTemplate` and validated source evidence provide structure, visible
numbering, punctuation, spacing, typography, tables, blanks and layout;
`ReviewEvidence` is limited to traceable review-evidence presentation. The
external style fixture is Word editability/style infrastructure only.

Source-owned headings and body lists use literal source prefixes with Named
Styles and outline semantics, but no automatic-numbering dependency. Preserve
the source prefix, punctuation, spaces and gaps. Only newly generated,
self-designed sections may use an isolated `GENERATED_AUTO` numbering family,
whose visible convention is learned from the tender source.

The only private operations are centralized in `word_safe_xml.py`: setting
East Asian font attributes and dropping the default template's unused
bibliography/customXml relationship. No relationship is created manually.
The ZIP scanner cannot infer authorship of a relationship from its bytes;
source-level API tests enforce that separate boundary.

Run `scripts/build_word_safe_canary.py` before real cases. Use
`scripts/scan_word_safe_docx.py FILE` for package and forbidden-construct
checks. `scripts/build_minimal_word_test.py` produces the isolated
`tmp/99_hello.docx` environment control; it is intentionally excluded from
the four-file manual acceptance folder unless the canary also fails Word.

`scripts/run_pipeline.py` regenerates `基础投标文件.docx` together with the same
run's ProjectFacts, review workbook and QA evidence; the per-round rebuild
scripts used during development are not part of the repository. The explicit
rebuild option only accepts an already-generated Word-safe directory and its
matching metadata.

Automated package checks, python-docx reopen and LibreOffice rendering are
required but do not prove Microsoft Word acceptance. Until a user confirms
all required manual targets open without repair/error prompts, the final status
is `WORD_SAFE_REBUILD_AWAITING_MANUAL_CONFIRMATION`.

For the current source-numbering acceptance lane, the equivalent status is
`ROUND_5_1_AWAITING_MANUAL_NUMBERING_CONFIRMATION` until desktop Word confirms
opening, navigation, style editing, literal numbering and visual fidelity.

If canary passes Word but a real file fails, disable supported feature classes
(merges, borders, minimum heights, paragraph spacing, page mapping, pictures)
to isolate the difference. Do not resume arbitrary XML patching.
