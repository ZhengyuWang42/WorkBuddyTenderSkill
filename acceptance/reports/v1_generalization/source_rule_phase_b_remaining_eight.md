# Phase B residual eight — decision matrix

Build: `acceptance/workspace/case_002/_phaseB_probe` (canonical pipeline, rc 0 / 0)

## Counters after the evidence-linkage fix

| counter | before Phase B | after Phase B core | after linkage fix |
| --- | --- | --- | --- |
| canonical physical rules | 51 | 51 | 51 |
| applicable fill rules | 51 | 51 | 51 |
| delivered | 42 | 44 | **48** |
| **visible** | 5 | 43 | **47** |
| missing | 7 | 5 | **3** |
| structurally-but-not-visible | 37 | 1 | **1** |
| evidence unavailable | 2 | 2 | **0** |
| duplicate delivery | 0 | 0 | 0 |
| wrong owner | 0 | 0 | 0 |
| unresolved classification | 0 | 0 | 0 |

`run_content_w_tab` 0 → 23, `literal_tab_chars` 23 → 0.

## Closed by the linkage fix (no emission change)

| rule | page | span | root cause | evidence | verdict |
| --- | --- | --- | --- | --- | --- |
| P149-R5 | 149 | 163.80→187.80 | MATCHER_FALSE_NEGATIVE | `source_form_line_paragraph` → paragraph 63; an underlined run paints exactly 24.00 pt | DELIVERED_VISIBLE_EDITABLE |
| P149-R6 | 149 | 453.35→489.35 | MATCHER_FALSE_NEGATIVE | same owner; second underlined run paints exactly 36.00 pt | DELIVERED_VISIBLE_EDITABLE |
| P144-R3 | 144 | 233.85→270.60 | EVIDENCE_LOOKUP_GAP | `editable_blank` BOTTOM_RULE/VECTOR_LINE, rendered 36.75 pt = source width | DELIVERED_VISIBLE_EDITABLE |
| P148-R8 | 148 | 321.10→358.65 | EVIDENCE_LOOKUP_GAP | `editable_blank` BOTTOM_RULE/VECTOR_LINE, rendered 37.55 pt = source width | DELIVERED_VISIBLE_EDITABLE |

The linkage fix has two parts, both generic and label-free:

1. **Owner index from the emitter's own records.** `source_form_line_paragraphs`,
   `source_visual_line_emission_plans` and `source_rule_compositions` name the rule ids
   they carry *and* the Word paragraph they built, so the owner is read exactly instead
   of being guessed from a label. A blank's `block_index` is a *source* block and is
   never used as a Word paragraph index.
2. **Coverage per rule span, not per paragraph.** Several rules share one delivered
   paragraph, so summing a paragraph's underlined advance and dividing by one rule's
   width reported 2.5 for the first rule and 0.48 for the second — neither is a
   measurement of either rule. The run whose own painted advance equals this rule's own
   source width is that rule's owner.

## Still open

| rule | page | span | root cause | state | resolution |
| --- | --- | --- | --- | --- | --- |
| P146-R1 | 146 | 196.90→304.90 | MATCHER_FALSE_NEGATIVE | delivered as the **underlined resolved project name** in paragraph 23 | add the `SOURCE_RULE_OWNED_BY_RESOLVED_VALUE` class and link it through the fill application's page/geometry; **do not emit a second underline** |
| P149-R1 | 149 | 85.05→139.05 | DELIVERY_MISSING | leading rule, no owner | extend the inline-element pathway to `LEADING_RULE_BEFORE_TEXT` |
| P170-R1 | 170 | 90.00→138.00 | DELIVERY_MISSING | leading rule, no owner | same leading-field support |
| P144-R2 | 144 | 280.05→392.00 | VISIBILITY_INSUFFICIENT | recorded 111.95 pt BOTTOM_RULE, measured 0.875 | determine real deficit vs measurement gap; the 0.90 threshold is **not** lowered |

`P146-R1` is the case §3 warns about: the DOCX *does* deliver the rule — paragraph 23 is
`'我单位收到贵公司' + [营收系统整合和硬件系统升级, underlined] + '项目招标文件…'` — so the fault is in
evidence linkage, not delivery. A width-equality match cannot find it because the value's
own painted advance (≈180 pt of 15 CJK glyphs) is its value width, not the rule's declared
108 pt, and `source_fill_applications` carry `source_rule_ids: []`.

No entry is `UNKNOWN`; implementation is not blocked on classification.
