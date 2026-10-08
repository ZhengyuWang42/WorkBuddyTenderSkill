# Generic Word source fidelity gate

- build = `acceptance/workspace/case_003/v1_word_source_fidelity_arch2`
- **GENERIC_WORD_SOURCE_FIDELITY = PASS**

| component | status | detail |
| --- | --- | --- |
| PAGE_FRAME_FIDELITY | PASS | frames=33 declared_sizes=33 undeclared_rendered_sizes=0 |
| PARAGRAPH_CONTAINER_FIDELITY | PASS | docx_paragraphs=196 logical_records=162 empty_paragraphs=32 |
| SOURCE_VISUAL_ROW_CONTRACT | NOT_APPLICABLE | the build records no source visual-row contract evidence |
| SOURCE_TEXT_COMPLETENESS | PASS | missing=0 expected=503 delivered=503 |
| SOURCE_TEXT_EXACT_ONCE_OWNERSHIP | PASS | zero_owner=0 multiple_owner=0 duplicate=0 |
| SOURCE_SLOT_OWNERSHIP | PASS | slots_detected=19 filled=7 values_keeping_underline=0 underlined_runs=24 |
| ROW_CURSOR_OWNERSHIP | PASS | cursor_recomputed_from_paragraph_width_count=0 |
| NO_DEFAULT_TAB_FALLTHROUGH | PASS | default_tab_fallthrough_risk_count=0 tabs_without_explicit_stop_count=0 |
| NO_DOUBLE_HORIZONTAL_OWNERSHIP | PASS | consecutive_blank_double_ownership_count=0 |
| DATE_SLOT_FIDELITY | PASS | date rows=14 max_underline_blanks_in_one_row=3 |
| TYPOGRAPHY_CONTRACT | NOT_APPLICABLE | the build records no source font inventory to compare the DOCX against |
| VERTICAL_RHYTHM_CONTRACT | PASS | rhythm_blocks=18 blocks_with_measured_pitch=3 dominant_line_pitch_pt=12.07 |
| TEXT_COMPLETENESS | PASS | source_scope_atoms=503 delivered=503 missing=0 duplicate=0 |
| RENDERER_DIVERGENCE_CLASSIFICATION | WARN_PROVEN_FONT_SUBSTITUTION | HEADLESS_FONT_SUBSTITUTION_ONLY: no measurable horizontal divergence: the widest matched rendered row fits inside the source row's own extent (430.50  |
| SOURCE_PAGE_SPLIT | PASS | source_pages=203 generated_pages=33 blank_pages=0 |
| LOGICAL_TABLE_IDENTITY | PASS | docx_tables=16 logical_tables=16 orphan_continuations=0 false_merges=0 |
| UNSAFE_OOXML_PROHIBITION | PASS | {"textbox_count": 0, "drawing_count": 0, "pict_count": 0, "object_count": 0} |
