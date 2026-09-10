# Delivery QA V1

Delivery QA reloads the final `project_facts.json`, XLSX, and DOCX from disk.
It does not trust builder return values and does not reopen the source tender
document.

## Checks

- Pydantic validation of `ProjectFacts`.
- Artifact existence, non-zero size, and reopenability.
- Fixed XLSX sheets and 20-field coverage.
- DOCX project-information table and 20-field coverage.
- Field-level value and status comparison for XLSX and DOCX.
- Candidate evidence row counts and exception-sheet completeness.
- Protection of `NEEDS_REVIEW`, `NOT_FOUND`, project/tender numbers, and
  budget/max-price pairs.
- Manual bidder placeholders and absence of a submission-ready status.

## Overall status

- `PASS`: technical checks pass and no field needs review or supplementation.
- `PASS_WITH_REVIEW`: technical checks pass, but `NEEDS_REVIEW` or `NOT_FOUND`
  remains in ProjectFacts.
- `FAIL`: an artifact, structure, value, status, or consistency check fails.

The QA CLI returns `0` for `PASS` and `PASS_WITH_REVIEW`, `2` for `FAIL`, and
`3` for a CLI/program error. The pipeline maps these results to
`READY_FOR_REVIEW`, `REVIEW_REQUIRED`, or `DELIVERY_FAILED`.

## Pipeline boundary

`run_pipeline.py` calls the existing normalization, extraction, resolution, and
builders directly, then runs disk-artifact QA. It stops at `OCR_REQUIRED` and
does not call an LLM, OCR engine, or semantic arbitration layer.
