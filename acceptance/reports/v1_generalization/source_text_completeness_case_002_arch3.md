# Source text completeness

- build = `acceptance/workspace/case_002/v1_word_source_fidelity_arch3`
- measurement mode = SAVED_BUILD_QA
- authority = SAVED_REOPENED_DOCX
- **SOURCE_TEXT_COMPLETENESS = PASS**

| counter | value |
| --- | --- |
| MISSING_ATOM_COUNT | 0 |
| DUPLICATED_ATOM_COUNT | 0 |
| source_text_atoms_with_zero_owner_count | 0 |
| source_text_atoms_with_multiple_owner_count | 0 |

- expected atoms = 451
- delivered atoms = 451
- out-of-order atoms = 25 (diagnostic)

out-of-order atoms are reported separately and are not a completeness failure: the delivered DOCX legitimately interleaves editable tables between source text, and the historical passing builds show the same count as the failing ones

