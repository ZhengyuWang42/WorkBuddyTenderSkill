# V1 人工 Word 复核清单 (human manual review checklist)

本清单由自动化证据生成，**尚未完成**。自动化结论为 `PASS`；`MANUAL_WORD_REVIEW_REQUIRED = true`、`READY_FOR_SUBMISSION = false` 在人工复核签字前保持不变。

## 0. 自动化结论 (automated result)

| 项目 | 值 |
| --- | --- |
| 三案例泛化 | THREE_CASE_GENERALIZATION = PASS |
| 自动化候选状态 | PASS |
| 自动化阻塞项 | 无 |
| 不同源文件数 | 3 |

自动化已通过的门禁：字词安全扫描、ZIP 完整性、OOXML 可解析、无文本框/浮动对象/嵌入位图、无合成版式表格、无表格单元丢失/重复/虚构、无阻断性重叠、源文本无缺失、渲染 PDF 可重新打开且无空白页、每条 RESOLVED 事实保留来源证据、复核证据硬门禁通过。

## 1. 逐案例交付物 (deliverables to open)

### CASE001 - 引江济淮郸城配套项目一体化泵站询比文件

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_001\v1_manual_fidelity_round2`
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

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_002\v1_round2_regression`
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

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_003\v1_round2_regression`
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

## 2.1 Round-2 人工复核点 (round-2 recheck pages)

第二轮修复把五类人工复核缺陷各自收敛到一条可测规则。以下三页请在 Word 中逐一打开确认；每一条都附上了自动化已测得的数值，人工只需判断这些数值是否符合原件的排版意图。

打开 `acceptance/workspace/case_001/v1_manual_fidelity_round2/基础投标文件.docx`：

### 第 3 页 —— 响应函（源 PDF 第 42 页）

- [ ] 第 4 条 `本项目询比有效期为提交响应文件截止之日起 90 日历天…` **应是一段**，不是两段：`90` 与前后下划线在同一行内，且该段没有段前/段后间距（已测得 `space_before = 0`、`space_after = 0`）。
- [ ] 该行的填充区与源件一致：3 段填充落在源件的 352.80–388.80 pt 区间内（冻结水平合同 ±2.0 pt，实测通过）。
- [ ] 该页共 8 条源件下划线，全部有且仅有一条对应输出（实测 `matched = 8 / lost = 0 / invented = 0 / out_of_tolerance = 0`）。
- [ ] 项目名称、标段、项目编号三个填入值不重叠、不截断；`达到` 前的空位仍为空白待人工填写。
- [ ] 该页仍是 22 页文档中的第 3 页，无空白页，下方来源行没有被上方换行挤走。

### 第 5 页 —— 法定代表人身份证明（源 PDF 第 44 页）

- [ ] `成立时间：` 行**从标签自身的位置起排**（段落左缩进 1.2 pt，即源件标签的 72.0 pt），不是从年份空位的位置起排。
- [ ] `成立时间：` 标签本身**不带下划线**，只有空位带下划线。
- [ ] 空位下划线的右端落在源件位置上（已测得 179.85 / 215.85 / 233.85 / 275.85 pt，冻结水平合同 ±2.0 pt）。
- [ ] 该段的段前/段后间距来自共享的源件竖向节奏，而不是按行补偿的任意数值。

### 第 21 页 —— 反商业贿赂承诺（源 PDF 第 60 页）

- [ ] `（项目名称、标段）` 行的填入值应显示为 `…一体化泵站采购项目、/`：项目名称 + 源件分隔符 + 斜杠标记。
- [ ] 斜杠 `/` 表示**源件表单要求的这个组成部分没有对应事实**，它不是一个被填入的事实值；`lot_name` 仍为 `NOT_FOUND`。
- [ ] 斜杠后应紧跟源件的 `询比活动中，我公司保证做到：`，与源件断行一致。
- [ ] 第 3 页响应函中**行内**出现的 `(项目名称、标段)`（后接 `（项目编号）`）**不应**出现斜杠——该处不是独立成行的表单字段。

> 以上三页的数值均由自动化门禁测得，并非人工估计：10 项结构门禁、Stage C 下划线清点、`REFLOW_AWARE_V1` 竖向合同、以及三案例泛化回归。人工只需确认这些数值符合原件意图。

## 3. 签字 (sign-off)

- [ ] 复核人：____________  日期：____________
- [ ] 结论：可提交 / 需修改

> 只有人工完成本清单后，才可以把 `READY_FOR_SUBMISSION` 置为 true。自动化检查不会、也不可以自行升级该标志。
