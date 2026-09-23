# CASE001 最终人工 Word 复核清单 (final human Word review checklist)

本清单由 `scripts/v1_case001_final_status.py` 依据 `_final` 门禁报告生成；所有数字都来自仓库内产物。**全部复选框保持未勾选**——人工复核尚未发生。

## 1. 复核对象 (build under review)

| 项 | 值 |
| --- | --- |
| build id | `v1_manual_fidelity_round4_date_rhythm_closure8` |
| build dir | `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8` |
| manifest | `build_manifest.json`（`FRESH_BUILD`，pipeline rc 0，render rc 0） |
| DOCX | `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230`（45700 B） |
| PDF | `3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927`（308449 B，22 页） |
| 源 PDF | `8e2bfb00e1a0c595db16d179477d9a09769ab82e45f63d476c3c8c459d46aa27` |
| 被取代的候选 | `v1_manual_fidelity_round3_word_review_followup`（见 `supersedes` 归档） |

## 2. 自动化结论 (automated result)

| 门禁 | 结果 |
| --- | --- |
| `p3_closure_phase2` | `PASS` |
| `p3_closure_phase3` | `FAIL` |
| `p3_semantic_registry` | `PASS` |
| `round3_typography` | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` |
| `followup_acceptance` | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` |
| `p21_structural` | `PASS` |
| `reflow_aware` | `PASS` |
| `manual_layout_fidelity` | `PASS` |
| `ownership_closure` | `PASS` |
| `underline_inventory` | `PASS` |
| `case_acceptance` | `PASS` |
| `three_case_regression` | `PASS` |
| `three_case_regression_failed_checks` | `[]` |
| `pointer_check` | `PASS` |
| `source_line_assembly` | `PASS` |
| `full_suite` | `614 passed, 1 skipped, 0 failed, 0 errors` |
| `round4_leading_date_blank_intrinsic` | `PASS` |
| `round4_date_row_alignment_fidelity` | `PASS` |
| `round4_date_row_gap_fidelity` | `PASS` |
| `round4_date_row_token_anchor_fidelity` | `PASS` |
| `round4_date_rule_endpoint_fidelity` | `PASS` |
| `round4_table_cell_line_pitch_fidelity` | `PASS` |

> `p3_semantic_registry` 的 `semantic_execution_binding` 已**闭合**（`PASS`，8 条规则全部 `binding_ok`）。历史上该检查曾为红，原因是它把「整条发出的值」与`ProjectFacts` 的单个原始值逐字比较——组合槽位（源模板字面量 + 事实值 + 源表「不适用」标记）在构造上永远无法等于单个事实值。该红结论作为历史证据保留在 `case001_composite_execution_binding_diagnostic_before_repair.json`，**没有被改写**。现在的门禁按原子校验（`FACT_VALUE` / `SOURCE_TEMPLATE_LITERAL` / `SOURCE_FORM_NOT_APPLICABLE_MARKER`），普通单事实槽位仍保持严格逐字相等。源契约、`ProjectFacts`、渲染内容均未改变。P3 契约钉住的四项不变：policy 8/8、intent 8/8、horizontal 8/8、matched 8 / lost 0 / invented 0 / out_of_tolerance 0。

> `p3_closure_phase3` 为红是既有诊断阶段（`FAIL`），其绝对垂直门禁在本轮前后同样为红，权威归 `REFLOW_AWARE_V1`（见 `docs/V1_PROJECT_STATE.md` 第 7 节）。

## 3. 文档级硬换行账目 (document-wide hard-break accounting)

| 计数 | 值 |
| --- | --- |
| `generated_w_br` | `0` |
| `generated_w_cr` | `0` |
| `generated_paragraph_boundaries` | `1` |
| `source_natural_wrap_boundaries` | `1` |
| `source_explicit_breaks` | `0` |
| `unexplained_structural_splits` | `0` |
| `builder_forced_breaks` | `0` |
| `unexpected_w_br_count` | `0` |
| `unexpected_w_cr_count` | `0` |
| `documented_structural_deviation_count` | `1` |

## 4. 已复核的 P3 结构性偏差（仍然存在，未被隐藏）

| 项 | 值 |
| --- | --- |
| `count` | `1` |
| `state` | `DOCUMENTED_STRUCTURAL_DEVIATION` |
| `disposition` | `REVIEWED_ACCEPTED_BY_PROJECT_POLICY` |
| `source_semantics` | `NATURAL_WRAP` |
| `generated_representation` | `PARAGRAPH_BOUNDARY` |
| `container_fidelity` | `SOURCE_CONTAINER_MISMATCH` |
| `fidelity_difference` | `CONTAINER_IDENTITY` |
| `deviation_kind` | `STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY` |
| `deviation_state` | `REVIEWED_ACCEPTED` |
| `accepted_by_automation` | `False` |
| `same_word_paragraph` | `False` |
| `conditions_satisfied` | `17` |
| `conditions_total` | `17` |
| `evidence_path` | `acceptance/evidence/structural_deviations/response_letter_natural_wrap_boundary.json` |

## 5. 本轮关闭的缺陷：委托期限 form line 的意外 w:br

同一源表行的修复前后对比（源几何证据，非字面量）：

| 源行 | 源规则 | 源行数 | 修复前行数 | 修复后行数 | x0 误差 | x1 误差 |
| --- | --- | --- | --- | --- | --- | --- |
| `委托期限：` | `P45-R6` | 1 | 2 | 1 | 0.0 | 0.0 |

根因：`FORM_BLANK_REPRESENTATION_FORCED_BREAK`

## 6. 逐项检查（全部未勾选）

- [ ] 在 Word 中打开 DOCX，确认可正常打开、无修复提示
- [ ] 确认生成文档 22 页，无空白页
- [ ] 确认「委托期限：」这一源表行在 Word 中仍在**同一行**（标签 + 空白 + 句号）
- [ ] 确认该行的空白下划线完整，且**没有**多出源文中不存在的一行
- [ ] 确认「委托期限：」该处**没有**任何硬换行（`w:br` / `w:cr`）
- [ ] 确认 P3 组合槽位 `(项目名称、/)（项目编号）` 与源标点一致，且下划线正确
- [ ] 确认「询比文件的全部内容，愿意」**不在**槽位下划线内
- [ ] 确认 `quality_target` 在响应函中**可见**
- [ ] 确认响应函「愿意」→「以人民币（大写）」之间无可见空白行、无额外段距（虽然此处仍是一个已记录的结构性段落边界）
- [ ] 确认该 P3 边界**没有**使用 `w:br` / `w:cr` / 空段落
- [ ] 确认 R3/R4 源表单几何仍正确（生成页 3 / 源页 42）
- [ ] 确认 P4 响应报价单元格内部行结构与 90 日天下划线仍正确
- [ ] 确认 P5 成立时间来源仍正确
- [ ] 确认 P9 汇总表多行 / 粗体 / 源空白下划线仍正确
- [ ] 确认 P12 注记仍为粗体
- [ ] 确认资格审查表「统一社会信用代码」单元格水平与垂直居中
- [ ] 确认 P21 组合下划线仍正确、首行缩进语义仍正确
- [ ] 确认 P22 源粗体标题仍为粗体
- [ ] 确认页顶间距在桌面 Word 中与预期一致
- [ ] 结论：可接受 / 需修改

## 7. 签字 (sign-off)

- [ ] 复核人：____________  日期：____________
- [ ] 结论：可接受（该案例的人工 Word 复核通过） / 需修改

> `READY_FOR_SUBMISSION` 不是编译器/流水线的全局状态；任何自动化检查都不会也不可以把它置为 true。
> 签署本清单也**不**构成 `V1_PRODUCTION_CANDIDATE = true`。
> 术语见 [`docs/V1_DECISIONS.md`](../../../docs/V1_DECISIONS.md) 第 9 节。
