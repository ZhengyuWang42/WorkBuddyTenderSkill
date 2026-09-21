# Delivery QA V1

Delivery QA reloads the final `project_facts.json`, XLSX, and DOCX from disk.
It does not trust builder return values and does not reopen the source tender
document. It validates the current run's artifacts only; it is not a substitute for
desktop Microsoft Word or business-owner review.

## Checks

- Pydantic validation of `ProjectFacts`.
- Artifact existence, non-zero size, and reopenability.
- Supplied-template XLSX main Sheet `投标项目复核表`, top-field placement, merged cells,
  64-item checklist, footer, and reopenability.
- DOCX project-information table and 23-field coverage.
- ProjectFacts-based value and status comparison for XLSX and DOCX.
- Protection of `NEEDS_REVIEW`, `NOT_FOUND`, project/tender numbers, budget/max-price
  pairs, and the distinction between `procurement_method` and submission method.
- DOCX `format_source` metadata and source-format heading order when supplied.
- Source-first numbering QA: source-visible prefixes, punctuation, spacing and source gaps remain
  unchanged; source Heading/Body List styles have no automatic numbering dependency.
- Outline QA: real Heading styles participate in navigation, while body lists, TOC entries and
  ambiguous numbered fragments do not become headings.
- Generated-auto QA: any system-generated numbering family is isolated from source-literal
  content and uses real Word numbering only where generated content is allowed.
- Candidate evidence integrity from `project_facts.json`, not from user-facing template
  sheets.
- Manual bidder placeholders and absence of a submission-ready status.

## Overall status

- `PASS`: technical checks pass and no field needs review or supplementation.
- `PASS_WITH_REVIEW`: technical checks pass, but `NEEDS_REVIEW` or `NOT_FOUND`
  remains in ProjectFacts.
- `FAIL`: an artifact, structure, value, status, or consistency check fails.

The QA CLI returns `0` for `PASS` and `PASS_WITH_REVIEW`, `2` for `FAIL`, and
`3` for a CLI/program error. The pipeline maps these results to
`READY_FOR_REVIEW`, `REVIEW_REQUIRED`, or `DELIVERY_FAILED`.

通过此 QA 只表示同批技术产物满足自动化一致性检查，不表示 `READY_FOR_SUBMISSION`。
桌面 Word 正常打开、代表性页面和人工事实/业务复核仍由项目治理约束作为发布门禁。
源编号 QA 的 `PASS` 只表示磁盘内容与源证据一致；它不替代桌面 Word 中对编号显示、
导航树、样式面板、可编辑性和视觉保真度的人工确认。

## Pipeline boundary

`run_pipeline.py` calls the existing normalization, extraction, resolution, and
builders directly, then runs disk-artifact QA. It stops at `OCR_REQUIRED` and
does not call an LLM, OCR engine, or semantic arbitration layer.
