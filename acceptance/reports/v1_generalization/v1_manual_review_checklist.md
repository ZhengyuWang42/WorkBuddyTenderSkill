# V1 人工 Word 复核清单 (human manual review checklist)

本清单由自动化证据生成，**尚未完成**。自动化结论为 `V1_AUTOMATED_CANDIDATE`；`MANUAL_WORD_REVIEW_REQUIRED = true`、`READY_FOR_SUBMISSION = false` 在人工复核签字前保持不变。

## 0. 自动化结论 (automated result)

| 项目 | 值 |
| --- | --- |
| 三案例泛化 | THREE_CASE_GENERALIZATION = PASS |
| 自动化候选状态 | V1_AUTOMATED_CANDIDATE |
| 自动化阻塞项 | 无 |
| 不同源文件数 | 3 |

自动化已通过的门禁：字词安全扫描、ZIP 完整性、OOXML 可解析、无文本框/浮动对象/嵌入位图、无合成版式表格、无表格单元丢失/重复/虚构、无阻断性重叠、源文本无缺失、渲染 PDF 可重新打开且无空白页、每条 RESOLVED 事实保留来源证据、复核证据硬门禁通过。

## 1. 逐案例交付物 (deliverables to open)

### CASE001 - 引江济淮郸城配套项目一体化泵站询比文件

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_001\v1_phaseC_final2`
- 结果: `PASS`
- 逐项门禁: 27 项，失败 0 项

- [ ] 在 Word 中打开 `基础投标文件.docx`，确认可正常打开、无修复提示
- [ ] 确认页面、页眉页脚、章节顺序与原文一致
- [ ] 确认表格为可编辑 Word 表格，跨页长表为单一逻辑表格
- [ ] 确认占位符/下划线/空格位置可供人工填写
- [ ] 在 Excel 中打开 `投标项目复核表.xlsx`，确认行与原文要求对应
- [ ] 复核 `project_facts.json` 中以下未定稿字段

  - 需人工确认 (NEEDS_REVIEW):
    - `electronic_platform`

  - 原文未找到 (NOT_FOUND):
    - `budget`
    - `lot_name`
    - `lot_number`
    - `procurement_method`
    - `submission_method`
    - `tender_number`

  - 交付 QA 警告:
    - business_review_state: ProjectFacts contains fields requiring human review or supplementation.

### CASE002 - 营收系统整合和硬件系统升级项目招标文件

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_002\v1_phaseC_final`
- 结果: `PASS`
- 逐项门禁: 27 项，失败 0 项

- [ ] 在 Word 中打开 `基础投标文件.docx`，确认可正常打开、无修复提示
- [ ] 确认页面、页眉页脚、章节顺序与原文一致
- [ ] 确认表格为可编辑 Word 表格，跨页长表为单一逻辑表格
- [ ] 确认占位符/下划线/空格位置可供人工填写
- [ ] 在 Excel 中打开 `投标项目复核表.xlsx`，确认行与原文要求对应
- [ ] 复核 `project_facts.json` 中以下未定稿字段

  - 需人工确认 (NEEDS_REVIEW):
    - `procurement_scope`

  - 原文未找到 (NOT_FOUND):
    - `budget`
    - `lot_name`
    - `lot_number`
    - `submission_method`

  - 交付 QA 警告:
    - business_review_state: ProjectFacts contains fields requiring human review or supplementation.

### CASE003 - 肇源县城市供水管网漏损治理项目三标段

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_003\v1_phaseC_final`
- 结果: `PASS`
- 逐项门禁: 27 项，失败 0 项

- [ ] 在 Word 中打开 `基础投标文件.docx`，确认可正常打开、无修复提示
- [ ] 确认页面、页眉页脚、章节顺序与原文一致
- [ ] 确认表格为可编辑 Word 表格，跨页长表为单一逻辑表格
- [ ] 确认占位符/下划线/空格位置可供人工填写
- [ ] 在 Excel 中打开 `投标项目复核表.xlsx`，确认行与原文要求对应
- [ ] 复核 `project_facts.json` 中以下未定稿字段

  - 需人工确认 (NEEDS_REVIEW):
    - `bid_deadline`
    - `bid_open_time`
    - `consortium_allowed`
    - `duration`
    - `electronic_platform`
    - `quality_target`

  - 原文未找到 (NOT_FOUND):
    - `budget`
    - `lot_number`
    - `procurement_method`
    - `project_number`
    - `submission_method`
    - `tender_number`

  - 交付 QA 警告:
    - business_review_state: ProjectFacts contains fields requiring human review or supplementation.

## 2. 案例特有复核点 (case-specific review points)

- [ ] **CASE001**: 第 42 页响应函的 `达到` 前空位未填入质量目标（该行没有自己的字段标签，按行作用域规则保留为固定空位），请确认该空位应由人工填写。
- [ ] **CASE002**: 询问报价明细长表跨源页合并为一个逻辑 Word 表格，Word 原生分页与源 PDF 页数不必相等，请确认分页位置可接受。
- [ ] **CASE003**: 三标段标段语义（lot）与 12 个留空槽位，请确认标段信息与人工填写位置正确。

## 3. 签字 (sign-off)

- [ ] 复核人：____________  日期：____________
- [ ] 结论：可提交 / 需修改

> 只有人工完成本清单后，才可以把 `READY_FOR_SUBMISSION` 置为 true。自动化检查不会、也不可以自行升级该标志。
