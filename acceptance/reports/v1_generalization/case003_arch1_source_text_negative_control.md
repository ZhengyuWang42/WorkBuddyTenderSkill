# Source text completeness

- build = `acceptance/workspace/case_003/v1_word_source_fidelity_arch1`
- measurement mode = RECOMPUTED_LEDGER
- authority = SAVED_REOPENED_DOCX
- **SOURCE_TEXT_COMPLETENESS = FAIL**

| counter | value |
| --- | --- |
| MISSING_ATOM_COUNT | 1 |
| DUPLICATED_ATOM_COUNT | 0 |
| source_text_atoms_with_zero_owner_count | 1 |
| source_text_atoms_with_multiple_owner_count | 0 |

- expected atoms = 503
- delivered atoms = 502
- out-of-order atoms = 38 (diagnostic)

## Missing atoms

- `P70-PARA5` page 70 (paragraph_text)
  - text: `期为   年   月   日；按合同约定实施和完成承包工程，修补工程中的任何缺陷，工程质量：    标准。 `
  - last present stage: STAGE_5_IN_MEMORY_DOCX
  - first missing stage: STAGE_5_IN_MEMORY_DOCX
  - neighbours: P70-PARA4 / P70-PARA6

out-of-order atoms are reported separately and are not a completeness failure: the delivered DOCX legitimately interleaves editable tables between source text, and the historical passing builds show the same count as the failing ones

