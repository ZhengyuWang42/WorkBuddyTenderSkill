# Generic Word source fidelity gate

- build = `acceptance/workspace/case_002/v1_word_source_fidelity_arch3`
- **GENERIC_WORD_SOURCE_FIDELITY = PASS**

| component | status | detail |
| --- | --- | --- |
| PAGE_FRAME_FIDELITY | PASS | frames=18 declared_sizes=18 undeclared_rendered_sizes=0 |
| PARAGRAPH_CONTAINER_FIDELITY | PASS | docx_paragraphs=134 logical_records=114 empty_paragraphs=17 |
| SOURCE_VISUAL_ROW_CONTRACT | NOT_APPLICABLE | the build records no source visual-row contract evidence |
| SOURCE_TEXT_COMPLETENESS | PASS | missing=0 expected=451 delivered=451 |
| SOURCE_TEXT_EXACT_ONCE_OWNERSHIP | PASS | zero_owner=0 multiple_owner=0 duplicate=0 |
| SOURCE_SLOT_OWNERSHIP | PASS | slots_detected=11 filled=6 values_keeping_underline=0 underlined_runs=2 |
| ROW_CURSOR_OWNERSHIP | PASS | cursor_recomputed_from_paragraph_width_count=0 |
| NO_DEFAULT_TAB_FALLTHROUGH | PASS | default_tab_fallthrough_risk_count=0 tabs_without_explicit_stop_count=0 |
| NO_DOUBLE_HORIZONTAL_OWNERSHIP | PASS | consecutive_blank_double_ownership_count=0 |
| DATE_SLOT_FIDELITY | PASS | date rows=5 max_underline_blanks_in_one_row=3 |
| TYPOGRAPHY_CONTRACT | NOT_APPLICABLE | the build records no source font inventory to compare the DOCX against |
| VERTICAL_RHYTHM_CONTRACT | PASS | rhythm_blocks=14 blocks_with_measured_pitch=8 dominant_line_pitch_pt=23.4 |
| TEXT_COMPLETENESS | PASS | source_scope_atoms=451 delivered=451 missing=0 duplicate=0 |
| RENDERER_DIVERGENCE_CLASSIFICATION | WARN_PROVEN_FONT_SUBSTITUTION | HEADLESS_FONT_SUBSTITUTION_ONLY: the rendered advance is 0.40% wider than the source row, inside the documented font-metric band of 5%, and the host d |
| SOURCE_PAGE_SPLIT | PASS | source_pages=174 generated_pages=32 blank_pages=0 |
| LOGICAL_TABLE_IDENTITY | PASS | docx_tables=9 logical_tables=9 orphan_continuations=0 false_merges=0 |
| UNSAFE_OOXML_PROHIBITION | PASS | {"textbox_count": 0, "drawing_count": 0, "pict_count": 0, "object_count": 0} |
