# Word render authority audit — CASE002

本报告把 Word 交付拆成三层独立权威，并用实测数据分类剩余分歧。

## 1. 权威契约（引用冻结决定，不新造策略）

- CURRENT_CONTRACT = DIAGNOSTIC / FINAL_AUTHORITY_FOR_WORD_DELIVERY / AUTHORITATIVE_FOR_SOURCE_AND_DOCX_FIDELITY
- LIBREOFFICE_ROLE = DIAGNOSTIC
- WORD_DESKTOP_ROLE = FINAL_AUTHORITY_FOR_WORD_DELIVERY
- SOURCE_GEOMETRY_ROLE = AUTHORITATIVE_FOR_SOURCE_AND_DOCX_FIDELITY

- `docs/V1_DECISIONS.md` **W9**：静态检查与 LibreOffice 渲染不能替代桌面 Microsoft Word 正常打开确认。
- `docs/V1_PROJECT_STATE.md` **§7 既知偏差（不是缺陷）**：字体度量固有漂移（§7.3）
- `docs/V1_PROJECT_STATE.md` **§7.3**：Word 行高是最小值，两个渲染器对 CJK 回退字体的度量不同；每个实测行高差都在 max(2.0 pt, 行高 25%) 之内，分类为 FONT_METRIC_ONLY。

## 2. 三层实测

| 层 | 字体 | 字号 | 目标行每字符宽 | 行宽 |
| --- | --- | --- | --- | --- |
| SOURCE PDF | FangSong_GB2312（子集） | 12.0 pt | 11.843 pt | 426.36 pt |
| DELIVERED DOCX | 仿宋 (FangSong) | 12.0 pt | —（请求，不渲染） | — |
| HEADLESS PDF | FangSong（LibreOffice 解析） | 12.0 pt | 12.000 pt | 420.00 pt |

- 宿主机是否安装 仿宋：**否（发生替换）**
- 字宽比 headless/source = 1.0132（宽 1.32%）

## 3. 分歧预测与观测（§15）

- source_used_width = 426.36 pt，source_available_width = 426.36 pt，source_fill_ratio = 1.0000
- docx_requested_font = 仿宋 12.0 pt（与源同族同号）
- predicted_headless_width = 36 × 12.000 = 432.00 pt
- predicted_overflow = 5.64 pt（不足一个全角字）
- observed_overflow = 6.36 pt（最后一个字 `全` 换行）
- prediction_residual = 0.72 pt

结论：

**AUTHORIZATION_RENDERER_DIVERGENCE_CLASS = HEADLESS_FONT_SUBSTITUTION_ONLY**

预测可解释观测，且源/文档几何、槽位归属、行内游标不变量、文本完整性全部为真；
因此这一分歧是渲染器字体替换的固有度量漂移，而不是交付文档的排版或几何缺陷。
该结论沿用 `docs/V1_PROJECT_STATE.md` §7.3 已冻结的 `FONT_METRIC_ONLY` 判断，
只是从行高轴扩展到水平步进轴；最终 Word 交付权威仍是桌面 Microsoft Word 人工复核（W9）。

## 4. 组件结论

- AUTHORIZATION_SOURCE_MODEL_FIDELITY = PASS
- AUTHORIZATION_DOCX_GEOMETRY_FIDELITY = PASS
- AUTHORIZATION_DOCX_TYPOGRAPHY_FIDELITY = PASS
- AUTHORIZATION_HEADLESS_RENDER_FIDELITY = WARN_PROVEN_FONT_SUBSTITUTION
- AUTHORIZATION_RENDERER_DIVERGENCE_CLASS = HEADLESS_FONT_SUBSTITUTION_ONLY
- AUTHORIZATION_TEXT_COMPLETENESS = PASS
- AUTHORIZATION_SOURCE_SLOT_FIDELITY = PASS
- AUTHORIZATION_WORD_RENDER_FIDELITY = PENDING_HUMAN_DESKTOP_WORD_REVIEW

## 5. 垂直节奏权威

- SOURCE_VERTICAL_RHYTHM_METRIC = Word line-spacing model (source-backed multiple)
- SOURCE_VALUE = source row pitch 23.4 pt inferred from the source's own baselines
- DOCX_VALUE = w:spacing/@w:line = 1.5 (lineRule auto) via infer_semantic_line_spacing
- HEADLESS_RENDER_VALUE = 25.35 pt rendered baseline delta
- TOLERANCE = max(2.0 pt, 行高 25%) per docs/V1_PROJECT_STATE.md §7.3
- AUTHORITY = source-backed line-spacing model; rendered delta is FONT_METRIC_ONLY
- FORM_ROW_LINE_PITCH_FIDELITY = PASS
- note = the DOCX carries the source-derived spacing model; the rendered baseline difference is the same CJK fallback-font metric drift the frozen §7.3 decision already classifies as a non-defect

