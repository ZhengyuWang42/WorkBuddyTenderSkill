# Document Normalization

`NormalizedDocument` is the source-preserving intermediate representation for one PDF or DOCX file. It records text, structure, order, and stable locators. It does not decide which text is a `ProjectFacts` field and does not call a model.

## PDF

- `page_number` is always 1-based; the first PDF page is `1`.
- `block_index` is the zero-based index from the page's extracted block order.
- Each block keeps `text`, `bbox`, `block_type`, and a `PdfLocator` containing `page` and `block_index`.
- PDF pages and blocks are also exposed as ordered `elements`.

## DOCX

- Top-level body paragraphs use a zero-based `paragraph_index`.
- Tables use a zero-based `table_index`; cells use zero-based `row_index` and `cell_index`.
- DOCX locators never contain a page number.
- `elements` follows the DOCX body XML order, so a paragraph/table/paragraph sequence remains a paragraph/table/paragraph sequence.
- A cell's multiple paragraphs remain separated by normalized `\n` characters.
- DOCX `page_count` is `0` because python-docx does not provide a stable logical page layout.
- For `UNSUPPORTED_FORMAT`, `source_type` is `null` because the input cannot be assigned to either supported type.

## Lines view

`document.lines.txt` emits one locator-prefixed record per source item:

```text
[PDF:P:1:B:0] 文本
[DOCX:P:0] 段落
[DOCX:T:0:R:0:C:1] 单元格
```

Embedded newlines inside one item are represented as the literal `\n` sequence in the lines view. The original normalized newlines remain in `normalized_document.json`.

## OCR_REQUIRED

No OCR is attempted. A PDF is marked `OCR_REQUIRED` when it has no usable extracted text, has very little total text, or—when it has multiple pages—most pages do not reach the minimum text threshold or the average extracted text is too small. The warning is:

```text
PDF appears image-based or has insufficient extractable text.
```

The partially extracted pages are still saved for inspection, but the CLI exits non-zero.

## Exit codes

```text
0 PARSED
2 UNSUPPORTED_FORMAT
3 PARSE_ERROR
4 OCR_REQUIRED
```
