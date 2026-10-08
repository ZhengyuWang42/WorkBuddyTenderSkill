# V1 人工 Word 复核清单 (human manual review checklist)

本清单由自动化证据生成，**尚未完成**。自动化结论为 `V1_AUTOMATED_CANDIDATE`；`MANUAL_WORD_REVIEW_REQUIRED = true`、`READY_FOR_SUBMISSION = false` 在人工复核签字前保持不变。

权威状态与冻结契约见 [`docs/V1_PROJECT_STATE.md`](../../../docs/V1_PROJECT_STATE.md) 与 [`docs/V1_DECISIONS.md`](../../../docs/V1_DECISIONS.md)。

**注：第 1 节列出的构建目录属于历史轮次**（自动化结论仍然有效，但 build 目录不是当前被接受/最新候选）。
**当前 CASE001 复核对象见第 1.6 节。**

> 本清单中的任何复选框**都不得**由自动化勾选。所有 `[ ]` 保持未勾选状态，直到人工在桌面 Microsoft Word 中实际确认。

## 0.5 人工复核第 4 轮结论（ROUND-4 HUMAN FINDINGS，HISTORICAL / SUPERSEDED）

> **历史（HISTORICAL / SUPERSEDED build）**：本节记录**当时**的复核对象
> `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8`
> （DOCX `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230`，
> PDF `3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927`）。
> 该 build 已被后继构建取代，**当前**复核对象见第 1.6 节。
> 下表 A/B/C 三项发现均已**自动化关闭**，等待人工在**当前** build 上重新复核。
> **`CASE001_MANUAL_WORD_REVIEW = NOT_YET_CONFIRMED`**。

**发现所在的历史复核对象**：`acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final`
（DOCX `16dc0ae275cb43799a76df5770b43fb7dc76b9d93b374e07621792419f95a191`，
PDF `ad2692ef9e0baa47a60ff17662cb3259d8a7b3ac47cde55e2fbc8fde1860a174`）。

**当时结论：`CASE001_MANUAL_WORD_REVIEW = FAIL`（人工复核未通过）。**

| 编号 | OPEN 发现 | 人工观察 | 状态 |
| --- | --- | --- | --- |
| A | 源日期行的**段落对齐语义**未被忠实保留 | 封面日期段用 `w:jc = left` + `w:left ≈ 4248 twips (≈7.49 cm)` 模仿居中；`法定代表人身份证明` 日期段带非零左缩进 `≈578 twips (1.02 cm)` | AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW |
| B | 日期行 `年`/`月`/`日` 之间的**源间隙 / 可编辑空白结构被压平** | 若干签署日期行渲染为 `年月日`，源为 `年    月    日` 或 `____年____月____日`；人工点名 `商务和技术偏差表`、`分项报价表`、`反商业贿赂承诺书` | AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW |
| C | `五、分项报价表` 内三行摘要的**源行距**与源不一致 | 段落属性为 `w:spacing line=240 lineRule=auto`，故**不是**「行距 1.5」；缺陷是视觉基线节奏 | AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW |

> **第 4 轮续作 VII（ROUND 4 CONTINUATION VII）的机器证据**，复核对象
> `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8`
> （DOCX `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230`，
> PDF `3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927`）：
>
> * **A**：`DATE_ROW_ALIGNMENT_FIDELITY = PASS`，`alignment_mismatch = 0`，`unexpected_indents = 0`，
>   居中行仍为 `w:jc = center`（`SOURCE_ALIGNED_CENTER`），偏移由
>   `L − R = 2 × delta` 的**实测**轴移表达，`ambiguous = 0`。
> * **B**：`date_figure_space_geometry_runs = 0`（figure space 不再参与任何日期几何）、
>   `collapsed = 0`、`lost_gaps = 0`、`invented_gaps = 0`、`date_tab_runs = 0`，
>   段宽由**固有间距**（一个空格 + 实测 `w:spacing`）表达，`rows_within_2pt = 10/10`，
>   最大间隙残差 **0.23 pt**、最大 token 锚点残差 **0.51 pt**；
>   规则端点 `matched = 9 / lost = 0 / invented = 0`。
> * **C**：`TABLE_CELL_LINE_PITCH_FIDELITY = PASS`；三行摘要现在是**一个逻辑单元格内的三个原生段落**
>   （`w:br = 0`、空段落 0），源 `23.40 / 19.44 pt` 渲染为 `23.40 / 19.45 pt`（容差 1.0 pt）。
>
> 证据：`case001_date_row_round4_closure8.json` / `.md`、
> `case001_date_rule_endpoint_round4_closure8.json`、
> `case001_table_cell_line_rhythm_closure8.json` / `.md`。
> **这些行只表示「自动化已关闭」，不表示人工已确认；下列复选框一律保持未勾选。**

> 这些维度此前**没有任何门禁测量过**，因此「机器门禁全绿」不构成反驳。
> 修复完成后转为 AUTOMATION-CLOSED，但**下列复选框一律保持未勾选**，人工复核须重新进行。

## 0.6 第 3 轮复核关注点归属（ROUND-3 REVIEW-CONCERN OWNERSHIP）

> 本节由第 3 轮人工加入；若用 `scripts/v1_manual_review_checklist.py` 重新生成，需要重新追加。

第 3 轮的对象是**机器侧语义**，不改变人工复核义务：工作簿每个渲染组件（招标文件要求、
数字、准备材料、不满足后果、评分提示、证据）现在同时满足「源文件可回溯」与「由同一个
`ReviewConcern` 拥有」。机器证据：`review_workbook_round3_final_status_reconciled.json`（PASS；其被取代的
`review_workbook_round3_final_status.json` 保留未改，见第 5 节）、
`review_workbook_round3_content_quality_case_00{1,2,3}.json`、`case_00{1,2,3}_review_workbook_gate_round3.json`、
`case_00{1,2,3}_review_workbook_visual_qa_round3.json`。

- CASE001 `项目质保期 24 个月` / `剩余 5% 作为质保金` / `质保期 12 个月…无息付清余款` 分别是
  `PROJECT_WARRANTY`、`RETENTION_MONEY_RATIO`、`RETENTION_RELEASE_PERIOD` 三个关注点，
  **不再被当作同一"质保"概念的冲突**；人工复核时请按三个独立问题分别核对。
- 非投标人面向的内部程序/定义条款若仍出现在工作簿中，会带
  `〔采购人内部程序/定义条款，仅备查，无需投标响应〕` 标记，人工无需响应。
- `CASE00{1,2,3}_XLSX_MANUAL_REVIEW` 仍为 `NOT_YET_CONFIRMED`；本节**不勾选**任何复选框，
  人工 Excel 复核（第 0.5 节之后的任务 B）仍待人工执行。

## 0.7 第 4 轮渲染层出处闭环（Round4 / ROUND-4 RENDERED-COMPONENT PROVENANCE）

> 本节由第 4 轮人工加入；若用 `scripts/v1_manual_review_checklist.py` 重新生成，需要重新追加。

人工复核第 3 轮工作簿（`..._review_workbook3`）判 **FAIL**，原因
`RENDERED_COMPONENT_CONCERN_OWNERSHIP`：**语义归属存在于模型对象，但渲染出来的 Excel 单元格
文本仍可能沿用过期/过宽来源组或旧主题模板的措辞**。第 4 轮把不变量推进到渲染层：

> **SEMANTIC OWNERSHIP MUST SURVIVE RENDERING**——每一个渲染进 XLSX 的实质短语，
> 都必须有"关注点自有"的出处。

**当前 Excel 复核对象（CURRENT = Round4）**：

| 项目 | 值 |
| --- | --- |
| CASE001 | `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook4/投标项目复核表.xlsx` |
| CASE002 | `acceptance/workspace/case_002/v1_round4_closure8_review_workbook4/投标项目复核表.xlsx` |
| CASE003 | `acceptance/workspace/case_003/v1_round4_closure8_review_workbook4/投标项目复核表.xlsx` |
| 机器状态 | `review_workbook_round4_final_status.json`（CASE001 25/25、CASE002 23/23、CASE003 23/23；八类 `RENDERED_*_CONCERN_MISMATCH = 0`；A–S 19/19；最终单元格审计全格一致） |
| XLSX SHA256 | CASE001 `be084b7aeefd24cd1a81cd3452b92a63389ca256a7fd785d4eed1dc85db52c3c`（70271 B）<br>CASE002 `ea6c4f2d9bc8473c3f2d8bed5bf53bd3e74a0f2a9086adeaad3ed79d22359ea9`（76801 B）<br>CASE003 `3bb048a45ebb3a445f6171c97cf39ec47fd61e7aeb3942e8f6f73be50d160735`（81382 B） |
| 全套测试 | 770 collected / 769 passed / 1 skipped / 0 failed / 0 errors（`review_workbook_round4_full_test_suite.{txt,xml}`） |

**历史复核对象（HISTORICAL = Round3，人工判 FAIL，未删除、未改写）**：
`acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook3`、
`acceptance/workspace/case_002/v1_round4_closure8_review_workbook3`、
`acceptance/workspace/case_003/v1_round4_closure8_review_workbook3`
（SHA256 见 `review_workbook_round3_final_status_reconciled.json`；`review_workbook_round3_full_test_suite` = 716 collected / 715 passed）。

机器证据：`review_workbook_round4_final_status.json`、`case00{1,2,3}_review_workbook_round4.{json,md}`、
`review_workbook_round4_rendered_component_provenance_case_00{1,2,3}.json`、
`case_00{1,2,3}_review_workbook_round4_gate.json`（第 3 轮 40 项门禁在**第 4 轮工作簿**上各 40/40 PASS）、
`case_00{1,2,3}_review_workbook_visual_qa_round4.json`、`review_workbook_round4_full_test_suite.{txt,xml}`。

第 4 轮修复的人工可见缺陷（复核时请重点确认）：

- 资质/信用行不再出现 `资质证书` / `专业类别` / `资质等级`；签章行不再出现 CA 上传 / 澄清 /
  授权委托书；否决行不再出现"推荐成交候选人 1–3 名"或凭空的无效后果。
- 每个数字都能在其**所属关注点**的来源与角色里找到：工期行不出现"14 个/3 个"、安装行不出现
  联系人、评分行按 95%/5% 付款条件、40 分价格公式、最高 1 分**分行**呈现（不再合并成一行）。
- CASE001：`PROJECT_WARRANTY = 24个月`、`RETENTION_MONEY_RATIO = 5%`、
  `RETENTION_RELEASE_PERIOD = 12个月` 三行并存且措辞各自独立——12 个月**不**被写成项目质保期，
  5% **不**被写成评分/付款比例。
- 机器列（E 证据定位、M 类型/关联事实）只承载本关注点的证据与**允许的**关联事实键。

人工复核义务不变：第 3 轮人工 `FAIL` **保留**在
`case001_review_workbook_round4_human_review.json`，自动化只能关闭为
`CASE001_XLSX_MANUAL_REVIEW = AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`，
**不勾选任何人工结论**（`已通过 = 0`；`V1_PRODUCTION_CANDIDATE = false`、`READY_FOR_SUBMISSION = false`，
无 tag、无 release）。

## 0. 自动化结论 (automated result)

| 项目 | 值 |
| --- | --- |
| 三案例泛化 | THREE_CASE_GENERALIZATION = PASS |
| 指针一致性 | POINTER_CHECK = PASS（`v1_three_case_regression_final.json`，`failed_checks = []`） |
| CASE001 硬换行保真 | `HARD_BREAK_FIDELITY = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`；`generated_w_br = 0`、`generated_w_cr = 0`、`unexpected_w_br_count = 0`、`unexpected_w_cr_count = 0` |
| 自动化候选状态 | V1_AUTOMATED_CANDIDATE |
| 自动化阻塞项 | 无 |
| 不同源文件数 | 3 |

自动化已通过的门禁：字词安全扫描、ZIP 完整性、OOXML 可解析、无文本框/浮动对象/嵌入位图、无合成版式表格、无表格单元丢失/重复/虚构、无阻断性重叠、源文本无缺失、渲染 PDF 可重新打开且无空白页、每条 RESOLVED 事实保留来源证据、复核证据硬门禁通过。

## 1. 逐案例交付物 (deliverables to open)

> **历史轮次记录（HISTORICAL）**：本节的构建目录与结果属于本清单首次生成时的轮次。
> 自动化结论仍然有效；但 CASE001 的**当前**复核对象是 §5.6 / 第 0.6 节所述的 closure8 build
> （`v1_manual_fidelity_round4_date_rhythm_closure8`），**不是**历史候选
> `v1_manual_fidelity_round3_word_review_final`。
> 本节的 `[ ]` 仍然保持未勾选——它们没有被任何后续轮次完成或作废。

### CASE001 - 引江济淮郸城配套项目一体化泵站询比文件

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_001\v1_manual_fidelity_round2_p21fix`
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

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_002\v1_round2_p21fix`
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

- 构建目录: `D:\PyCharmProjects\WBTenderSkill\acceptance\workspace\case_003\v1_round2_p21fix`
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

## 1.5 结构性修复的人工确认点 (structural fixes to confirm in Word)

本节的每一项都由 `v1_p21_structural` 的测量结果派生，自动化已验证；请在 Word 中对同一处做目视确认。

### 组合槽位下划线 (composite slot underline)

- 源页 60，交付页 21，Word 段落索引 132
- 该槽位交付的值: `河南省水利第二工程局集团有限公司引江济淮郸城县配套工程水源置换城乡供水工程项目部一体化泵站采购项目、/`
- 人工复核点: 上列值中的**每一个组成部分**（事实值、源模板分隔符 `、`、源表格「不适用」标记 `/`）都必须位于**同一条连续下划线**之上。
- [ ] 该值在 Word 中整段带下划线（含末尾的标记符号），无中断
- [ ] 紧邻其前与紧随其后的正文（`在`）**没有**下划线
- [ ] `/` 是源表格的「不适用」标记，**不是**被填写的字段值（该字段状态为 lot_name=NOT_FOUND，保持未定稿）
- [ ] 该槽位只由 1 条源规则记账（`P60-R1`），无重复、无新增规则

### 源段落缩进 (source paragraph indents)

- 下列段落按**自身源文本行**逐段判定；同一页的不同列表项可以不同，不要按列表样式整体推断。

- [ ] 段落 130：无特殊首行缩进 - 由容器居中/锚定值定位，不适用通用缩进契约
- [ ] 段落 131：无特殊首行缩进 - Word 左缩进 1.30 pt + 首行 0.00 pt（源首行 x=72.12）
- [ ] 段落 132：首行缩进 - Word 左缩进 1.20 pt + 首行 27.60 pt（源首行 x=99.60）
- [ ] 段落 133：首行缩进 - Word 左缩进 1.20 pt + 首行 27.85 pt（源首行 x=99.84）
- [ ] 段落 134：首行缩进 - Word 左缩进 1.20 pt + 首行 27.85 pt（源首行 x=99.84）
- [ ] 段落 135：首行缩进 - Word 左缩进 1.20 pt + 首行 27.70 pt（源首行 x=99.72）

- [ ] 确认上述段落**没有**被整体左缩进：首行缩进只影响第一行，换行后的续行应回到正文左边界。

## 1.6 当前 CASE001 复核对象 (current CASE001 build under review)

**这是当前应打开复核的 build，并且它就是 `case_001_current_build.json` 的指针目标**
（哈希取自指针 JSON 与 `build_manifest.json`，二者一致）。

| 项 | 值 |
| --- | --- |
| build id | `v1_word_source_fidelity_arch3` |
| build dir | `acceptance/workspace/case_001/v1_word_source_fidelity_arch3` |
| manifest | `build_manifest.json`（`FRESH_BUILD`，pipeline rc 0，render rc 0） |
| DOCX | `6098bf6041ee31933ad75a451e1171c176fd67ccdda33bc13d695645ba585480`（45699 B） |
| PDF | `742a92a675d20c096fc1aab9f11585a798590afd6bc391f50f231e79e4d2e422`（308312 B，23 页） |
| 源 PDF | `8e2bfb00e1a0c595db16d179477d9a09769ab82e45f63d476c3c8c459d46aa27`（61 页） |
| generation_report | `638934270d45a62253e2985719b17ee2ba23dbeae78569cc2c4162de86f7a277` |
| 指针目标 | `acceptance/reports/v1_generalization/case_001_current_build.json` → `v1_word_source_fidelity_arch3`（`POINTER_CHECK = PASS`） |
| 自动化状态 | `HARD_BREAK_FIDELITY = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`，`documented_structural_deviation_count = 1`，`unexplained_structural_split_count = 0`，`unexpected_w_br_count = 0`，`unexpected_w_cr_count = 0`；`PARAGRAPH_FLOW_FIRST` 审计 `PARAGRAPH_POSITIONING_TAB_COUNT = 0`、`CENTER_ALIGNMENT_HACK_COUNT = 0`、`RIGHT_ALIGNMENT_HACK_COUNT = 0`、`FIRST_LINE_TAB_HACK_COUNT = 0`，`unreachable_positioned_blank_count = 0` |
| 人工状态 | `CASE001_MANUAL_WORD_REVIEW = NOT_YET_CONFIRMED`（本清单**全部未勾选**） |
| 上一候选（已被取代，**未删除**） | `v1_word_source_fidelity_arch2`，其前身为 `v1_manual_fidelity_round4_date_rhythm_closure8`（见 §1.6.2 HISTORICAL 块） |

生成文档 22 页，生成页 = 源页序 − 39。

> **本轮变化摘要（复核时请注意）：** 与上一候选相比，DOCX 的变化来自第 4 轮续作 VII 的两项关闭
> （前导日期空白几何、单元格内源行节奏），以及 `委托期限：` 表单行意外硬换行的修复
> （见第 1.6.1 节）。整篇文档 `generated_w_br = 0`、`generated_w_cr = 0`。
> 第 7.1 节那**一个**已复核段落边界**完全未动**（见下）。

### 1.6.2 历史复核对象（HISTORICAL / SUPERSEDED）

以下 build 是**当时**的当前复核对象，已被后继构建取代，**不得**当作当前状态；
其历史人工结论也一并保留：

| 项 | 历史值 |
| --- | --- |
| build id | `v1_word_source_fidelity_arch2`（其后继为当前 `v1_word_source_fidelity_arch3`） |
| build dir | `acceptance/workspace/case_001/v1_word_source_fidelity_arch2` |
| DOCX | `fbca580b6f2f663dd01fbf8d869aa44d91cd87eb8c5c43a84b82025b6ca241d2` |
| 更早的 build id | `v1_manual_fidelity_round4_date_rhythm_closure8` |
| 更早的 build dir | `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8` |
| 更早的 DOCX | `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230`（45700 B） |
| 更早的 PDF | `3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927`（308449 B，22 页） |
| build id | `v1_manual_fidelity_round3_word_review_final` |
| build dir | `acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final` |
| DOCX | `16dc0ae275cb43799a76df5770b43fb7dc76b9d93b374e07621792419f95a191`（45533 B） |
| PDF | `ad2692ef9e0baa47a60ff17662cb3259d8a7b3ac47cde55e2fbc8fde1860a174`（301445 B，22 页） |
| generation_report | `97584ab13b820378669f4fee90d94ef918637c35c4cd86a8fc3c28e172e4e761` |
| 历史人工结论 | **`CASE001_MANUAL_WORD_REVIEW = FAIL`**（第 4 轮桌面 Word 人工复核针对**该** build 作出，并给出 §0.5 的 A / B / C 三项发现）——历史事实，**不得删除或改写** |
| 当时的后续候选 | `v1_manual_fidelity_round3_word_review_followup`（其 `w:br` 已关闭）；状态与清单归档为 `*_superseded_by_unexpected_hardbreak_closure.{json,md}` |
| 取代它的当前对象 | `v1_manual_fidelity_round4_date_rhythm_closure8`（见上表）；A / B / C 已 `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`，因此当前人工状态回到 `NOT_YET_CONFIRMED` |
| 历史指针副本 | `case_001_current_build_superseded_by_{unexpected_hardbreak_closure,policy_reconciliation,round4_date_rhythm_closure8}.json`（原文件逐字节保留） |

#### 1.6.1 本轮关闭的缺陷：`委托期限：` 表单行意外换行（P6）

| 项 | 值 |
| --- | --- |
| 源证据 | 源第 45 页：标签 `委托期限：`（x 94.80–154.80）、规则 `P45-R6`（x 154.80–232.80）、后缀 `。`（x 232.80–244.80）在**同一**视觉行 |
| 修复前 | 交付为**两行**（`委托期限：` 一行，`             。` 另一行），夹一条源文不存在的 `w:br` |
| 修复后 | 交付为**一行**：`委托期限：             。`；规则 x0/x1 误差 `0.0` / `0.0` pt |
| 根因 | `FORM_BLANK_REPRESENTATION_FORCED_BREAK`——判据用了「本行是否已有文字」（`paragraph_so_far.strip("\t")`），量的是段落而不是源表行；该处几何子句为假（`overshoot_pt = 0.0`） |
| 解决 | 判据改为空白自身的源起点 `blank_starts_behind_cursor = blank_x0 + 1.0 < reach`（通用，无字面量） |
| 是否记为偏差 | **否**。它是缺陷，不是 `DOCUMENTED_STRUCTURAL_DEVIATION`；偏差计数仍为 **1** |
| 诊断 | `acceptance/reports/v1_generalization/case001_p6_unexpected_hardbreak_diagnostic.json`（`verdict = P6_SOURCE_ROW_CONTINUITY_CLOSED`） |

### CASE001 逐项检查（全部未勾选）

- [ ] P3 组合槽位显示源正确内容：`project_name` + 源分隔符 + `/` + `project_number`
- [ ] P3 组合槽位下划线正确
- [ ] 「询比文件的全部内容」**没有**被误加下划线
- [ ] R6 `quality_target` 在交付的响应函中**可见**
- [ ] 「愿意」→「以人民币（大写）」之间**没有**可见空白行、也**没有**额外段落间距
      （即使当前 Word 实现使用了一个已记录的结构性段落边界）
- [ ] 该边界**没有**使用 `w:br` / `w:cr`
- [ ] R3/R4 源表单几何保持正确
- [ ] P4 响应报价单元格的**内部行结构**保持源兼容（生成页 4 / 源页 43）
- [ ] P4 的 90 日天下划线保持正确
- [ ] P5 成立时间的来源（origin）保持正确（生成页 5 / 源页 44）
- [ ] P6 `委托期限：` 这一源表行在 Word 中仍在**同一行**（标签 + 空白 + 句号）
- [ ] P6 `委托期限：` 该行的空白下划线**完整**，且**没有**多出源文中不存在的一行
- [ ] P6 `委托期限：` 该处**没有**任何硬换行（`w:br` / `w:cr`）
- [ ] P9 汇总表保持正确的多行 / 粗体 / 下划线（生成页 9 / 源页 48）
- [ ] P12 注记保持粗体（生成页 12 / 源页 51）
- [ ] 资格审查表中的「统一社会信用代码」单元格**水平居中且垂直居中**
- [ ] P21 组合下划线保持正确（生成页 21 / 源页 60）
- [ ] P21 引言段与「一/二/三」各段保持首行缩进语义
- [ ] P22 源粗体标题保持粗体（生成页 22 / 源页 61）
- [ ] 确认本轮修复没有让**任何其他**位置出现新的换行（整篇 `generated_w_br = 0`）

### 结构性偏差的人工裁决点（缺陷 B）

偏差的自动化结论（`case001_typography_final.json::measurements.hard_break_fidelity`）：

| 项 | 值 |
| --- | --- |
| 族状态 | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`（**不是** `PASS`） |
| `source_semantics` | `NATURAL_WRAP`（**未**被改写为显式换行） |
| `generated_representation` | `PARAGRAPH_BOUNDARY` |
| `container_fidelity` | `SOURCE_CONTAINER_MISMATCH` |
| `fidelity_difference` | `CONTAINER_IDENTITY` |
| `deviation_kind` | `STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY` |
| `deviation_state` | `REVIEWED_ACCEPTED`（项目政策接受，**非**自动化接受） |
| `same_word_paragraph` | `false`（**未**伪造） |
| `w_br` / `w_cr` / 空段落 / 可见额外间距 | `0` / `0` / `0` / `0` |
| `documented_structural_deviation_count` | `1`（**只有**这一个；本轮关闭的 P6 缺陷**未**被登记为偏差） |
| `unexplained_structural_split_count` | `0` |
| `builder_forced_break_count` | `0` |
| `unexpected_w_br_count` / `unexpected_w_cr_count` | `0` / `0` |
| 证据文件 | `acceptance/evidence/structural_deviations/response_letter_natural_wrap_boundary.json` |
| 上一候选曾需裁决的内联硬换行 | **已关闭，不再需要裁决**：`委托期限：` 表单行的 `w:br` 已被修复（见第 1.6.1 节） |

- [ ] 确认缺陷 B 的裁决：**接受该段落边界为已复核的结构性偏差**
      （`deviation_state = REVIEWED_ACCEPTED`、`container_fidelity = SOURCE_CONTAINER_MISMATCH`），
      **或者**明确要求放宽 R3/R4 的 `EXACT_SOURCE_SPAN` 契约。
      ——**两者不能同时成立。**
- [ ] 确认该偏差在阅读体验上等同于源（无可见空白行、无额外间距、阅读顺序与文字内容一致）
- [ ] 确认**没有**把 `委托期限：` 表单行当成第二个结构性偏差（它已被修复，不是偏差）

### 渲染器差异的人工确认点

- [ ] 确认生成文档的**页顶间距**在桌面 Word 中与预期一致
      （LibreOffice 与 Word 到达页顶的机制不同，见 `docs/V1_PROJECT_STATE.md` §7.2）

## 2. 案例特有复核点 (case-specific review points)

- [ ] ~~**CASE001**: 第 42 页响应函的 `达到` 前空位未填入质量目标（该行没有自己的字段标签，按行作用域规则保留为固定空位），请确认该空位应由人工填写。~~
      **SUPERSEDED（已过时）**：R6 现在由语义 registry 绑定到 `quality_target`，
      其值 `符合国家及行业有关标准、规范和询比文件要求` **已出现在**交付的响应函中
      （1 owner、1 `SourceFillApplication`，`value_from_project_facts = true`）。
      请改为按第 1.6 节确认「R6 `quality_target` 在交付的响应函中可见」。保留此行仅为记录历史状态。
- [ ] **CASE002**: 询问报价明细长表跨源页合并为一个逻辑 Word 表格，Word 原生分页与源 PDF 页数不必相等，请确认分页位置可接受。
- [ ] **CASE003**: 三标段标段语义（lot）与 12 个留空槽位，请确认标段信息与人工填写位置正确。

## 2.5 CASE002 / CASE003 人工复核状态 (not yet completed)

以下两案例的人工 Word 复核**尚未开始**。在开始之前不得声称任何人工结论。

### CASE002 — 营收系统整合和硬件系统升级项目

当前指针目标（`case_002_current_build.json`）：`acceptance/workspace/case_002/v1_word_source_fidelity_arch3`
DOCX sha256 = `8772eb2a7df1034403188b56269efe6ac90727f41deac995b91cb853f3bf7acf`（61152 B）
PDF sha256 = `b4f0ec41d9632826e8ce5f12acd2841cd20ac0cd875a53ffa5f88dae98b09c8d`（552765 B，32 页）
源 PDF sha256 = `2803076ab4e334bfa710a63d3dfe008893a48474db120b16118fe392cb818449`（174 页）
generation_report sha256 = `266cdf3dd5799e84ee01119e69c0f48078f79ad0aec50032e74bdce09c3a48c7`

> **历史（HISTORICAL / SUPERSEDED）**：旧当前指针曾是
> `v1_word_source_fidelity_arch2`，更早为 `v1_round4_closure8`
> （DOCX `1e694c00…5989d`），再早为 `v1_manual_fidelity_round3_word_review_final`（DOCX `5206b410…f08012`）。
> 历史指针副本保留为 `case_002_current_build_superseded_by_*.json`。以下关于该轮修复的描述
> 属那些历史 build 的记录。

> 本轮共用修复重建了 CASE002，并把 4 条表单行 `w:br` 中的 **2** 条关闭（`系`、
> `我公司参加贵单位组织的` 两行）；保留的 **2** 条（`3、我方拟委派的项目负责人为`、
> `7、我方的投标文件有效期为`）都带发射器自己的几何越界证据（19.1 pt / 19.95 pt），
> 即光标确实已越过规则起点，属**必须**另起一行。重建后两案例验收仍为 `PASS`。
> 证据：`case002_p6_unexpected_hardbreak_row_measure.json`。

- [ ] **强制**：询问报价明细的**跨页长表**在 Word 中仍是**一个逻辑可编辑表格**
- [ ] 确认 Word 原生分页位置可接受（Word 分页数与源 PDF 页数**不必**相等）
- [ ] 确认预算 / 最高限价（ceiling）与多个限值在文档中语义未混用
- [ ] 确认软件与硬件质保期的差异被正确保留
- [ ] 确认不允许联合体 / 不允许分包被正确表达
- [ ] 确认星号（★）强制条款未被遗漏或改变
- [ ] 复核 `project_facts.json` 中 `procurement_scope = NEEDS_REVIEW` 及 `budget`/`lot_name`/`lot_number`/`submission_method = NOT_FOUND`
- [ ] 确认本轮关闭的 2 条表单行（`系`、`我公司参加贵单位组织的`）在 Word 中确实各占**一行**
- [ ] 确认保留的 2 条（`3、我方拟委派的项目负责人为`、`7、我方的投标文件有效期为`）的换行与源表单版式一致
- [ ] 结论：可接受 / 需修改

### CASE003 — 肇源县城市供水管网漏损治理项目三标段

当前指针目标（`case_003_current_build.json`）：`acceptance/workspace/case_003/v1_word_source_fidelity_arch3`
DOCX sha256 = `df754d89e6c28013a1ae53c8cddf368036c86adf5edd752c91d1ad27fa1da950`（56960 B）
PDF sha256 = `e8c1825002fc157c8e147483744efc5237291f64a86ced898b7cdce29540d417`（897769 B，33 页）
源 PDF sha256 = `aa9e4e6936269fc506fc27c921b4e14a655426414e73393b23a4e22348a0384a`（203 页）
generation_report sha256 = `6df50d39ceaaacd246f362598413154ccff1a00b9384fcea40b94a8fbe134255`

> **历史（HISTORICAL / SUPERSEDED）：CASE003 的旧当前指针是 `v1_followup3`
> （DOCX `e013b1f2…cf3e2365`），其后为 `v1_round4_closure8`（DOCX `74946ddc…45a54`），
> 再后为 `v1_word_source_fidelity_arch2`。**
> 历史理由（**已 SUPERSEDED，仅作历史证据**）：当时共用修复也重建了 CASE003，
> 但重建产物的 `generation_report.json`（`1248666a…`）、`project_facts.json`、
> `normalized_document.json`、`source_format_qa.json` 与被接受产物**逐字节相同**，该案例有 **0**
> 条表单行换行，修复对它是 **no-op**。因此当时指针**不迁移**（不为 ZIP 时间戳而 churn），
> 三案例回归以该产物自身的验收证据评分。重建产物自身的验收报告保留为 `case003_acceptance_final.json`。
> 历史指针副本保留为 `case_003_current_build_superseded_by_{policy_reconciliation,round4_date_rhythm_closure8}.json`。

- [ ] **强制**：标段（lot/section）语义有意义——`lot_name = 三标段` 具源证据，且**未**继承 CASE001 的 `lot_name = NOT_FOUND` 行为
- [ ] 确认 12 个留空槽位与标段信息的人工填写位置正确
- [ ] 复核 `project_facts.json` 中 `bid_deadline`/`bid_open_time`/`consortium_allowed`/`duration`/`electronic_platform`/`quality_target = NEEDS_REVIEW`，以及 `budget`/`lot_number`/`procurement_method`/`project_number`/`submission_method`/`tender_number = NOT_FOUND`
- [ ] 结论：可接受 / 需修改

## 3. 签字 (sign-off)

- [ ] 复核人：____________  日期：____________
- [ ] 结论：可接受（该案例的人工 Word 复核通过） / 需修改

> 只有人工完成本清单后，才可能就该**具体项目**讨论提交就绪。
> `READY_FOR_SUBMISSION` **不是**编译器/流水线的全局状态；任何自动化检查都不会、也不可以把它置为 true。
> 签署本清单**不等于**提交就绪——最终提交仍需逐项目的商务复核、法务复核、报价复核与签字/盖章复核。
>
> 签署本清单也**不**构成 `V1_PRODUCTION_CANDIDATE = true`：该状态要求**三个规范案例**的自动化与人工验收全部完成。
> 术语定义见 [`docs/V1_DECISIONS.md`](../../../docs/V1_DECISIONS.md) 第 9 节。

## 4. 人工 Excel 复核（投标项目复核表.xlsx）

**当前复核对象（CURRENT = Round12）**：第 12 轮后继构建（最终 XLSX 送达文本收口），
Word 产物与 closure9 逐字节相同（`word_render_repeated=false`）。路径与 sha256 取自本轮构建清单。

| 案例 | 工作簿（当前复核对象） | 行数 | XLSX sha256 |
| --- | --- | --- | --- |
| CASE001 | `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook12_final/投标项目复核表.xlsx` | 50 | `034dedbc3cee3e88dfb36db830e030de2e6bdc61b5728d6dae3db7b3651e1764` |
| CASE002 | `acceptance/workspace/case_002/v1_round4_closure9_review_workbook12_final/投标项目复核表.xlsx` | 45 | `ac39ed7628fb7136624467f72a2593c59c49e88257f6b34eebe63f3e4b2c7b87` |
| CASE003 | `acceptance/workspace/case_003/v1_round4_closure9_review_workbook12_final/投标项目复核表.xlsx` | 49 | `1f0ca082bca96d745d29cd0cbeed72fb3c340567a23247f4d829f3f3ea061080` |

> 更早的中间构建 `..._review_workbook12`（第 12 轮代码修复之前的运行，CASE001 sha256
> `68cb48a31c4ba98201151c4d428040f67c152107b33a972689a9b607df937210`）作为缺陷证据
> **逐字节保留、未被覆盖**（其构建报告改名为
> `case_00{1,2,3}_review_workbook_build12_superseded.json`）；
> 门禁与人工复核只认 `..._review_workbook12_final`。

**CASE001 人工 Excel 复核状态：`HUMAN_PASS`（CURRENT；已授权归档）** ——
人工已对**该确切构建**的 `投标项目复核表.xlsx` 判 PASS，机器前置条件 Round12 = PASS。
归档记录见 `case001_review_workbook_round12_human_review.json` / `.md`，当前复核点见 §4.6。
**CASE002 / CASE003 的人工 Excel 复核仍未确认**（`NOT_YET_CONFIRMED`），见 §4.7（CASE002 准备）
与 §2.5。

### 4.6 第 12 轮 CASE001 XLSX 人工复核结论（CURRENT = HUMAN_PASS，已授权归档）

**CURRENT CASE001 XLSX HUMAN REVIEW: PASS**

| 项 | 值 |
| --- | --- |
| Build | `v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook12_final` |
| Artifact | `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure9_review_workbook12_final/投标项目复核表.xlsx` |
| SHA256 | `034DEDBC3CEE3E88DFB36DB830E030DE2E6BDC61B5728D6DAE3DB7B3651E1764` |
| Round12 machine prerequisite | **PASS** |
| 归档记录 | `case001_review_workbook_round12_human_review.json` / `.md` |

人工确认的子结论：`BID_RESPONSE_CONTRACT_RISK_SEPARATION = HUMAN_PASS`、
`CANONICAL_EVIDENCE_UNIT_HEADING_FIDELITY = HUMAN_PASS`、
`FINAL_XLSX_DELIVERY_TEXT_FIDELITY = HUMAN_PASS`。

已知**非阻塞**观察（人工判定不阻塞本次 PASS）：`30日历天` / `30天` 之类的重复复核措辞可能仍然存在；
部分送达语言仍偏机器/模板化。

**作用范围（不得泛化）**：本 PASS 只适用于 `case_001` 的**该确切构建**与**该确切 SHA256**；
后续重新生成的任何工作簿都必须**独立**人工复核。历史人工 FAIL 记录**未改写**。
本 PASS **不**构成 CASE002/CASE003 的 XLSX 复核结论、**不**构成 Word 人工复核结论、
**不**构成 `V1_PRODUCTION_CANDIDATE` 或 `READY_FOR_SUBMISSION`，
也**不**构成商务/法务/报价/签字/盖章审批。

人工复核点（已由**人**勾选）：

- [x] 纯合同风险行（`九、合同风险提示（投标前识别）`，CASE001 共 7 行）的复核要点**没有**
      「逐条比对响应文件对应章节 / 核对响应文件已载明 / 确认响应文件接受 / 与响应文件一致」等响应侧措辞，
      只有投标前内部风险决策步骤
- [x] DR037（履约保证金，合同风险行）的复核要点同时给出**两个来源角色**：
      `其中第11页第7.3条 供应商须知前附表（项目专用值）；第21页 7.3 履约担保（通用/中标后条款）`
- [x] DR037 行**不出现** `第18页 / 3.4 响应保证金`（那是**另一个**关切「投标保证金」的条款，不是履约保证金的来源）
- [x] `投标项目复核表!E38`（设备标准、规程和规范）的证据摘要**没有**在标准号中间截断
      （不再出现 `GB50015-2`），完整值仍可在 `要求正文` 列看到 `GB50015-2019`
- [x] 主表 E 列证据摘要与 `02_关键条款` / `03_资格否决与强制项` / `07_证据索引` 使用同一裁剪口径（同一 `…` 截断标记语义）
- [x] 第 10 / 11 轮人工确认点（合同风险分离、结构标题保真）在**第 12 轮构建上**同样成立
- [x] 人工结论列**由人**勾选（本次即由人给出 `HUMAN_PASS`）；自动化永不勾选，也永不把 `CASE001_XLSX_MANUAL_REVIEW` 置为 PASS

机器闭环证据（**已通过，不代替人工复核**）：

- 第 12 轮三案例审计 PASS：`review_workbook_round12_case_00{1,2,3}.json` / `.md`
  （`0 failed check` / `0 failed fixture`）、泛化 `review_workbook_round12_generalization.json` = PASS
- 送达文本读数（取自**已保存 XLSX**）：`PURE_CONTRACT_RISK_RESPONSE_FILE_LANGUAGE_COUNT = 0`、
  `MID_TOKEN_EVIDENCE_TRUNCATION_COUNT = 0`、`MULTI_SOURCE_ROLE_DISPLAY_AMBIGUITY_COUNT = 0`；
  CASE001 `DR037_PROJECT_SOURCE = 第11页第7.3条 供应商须知前附表`、
  `DR037_GENERAL_SOURCE = 第21页 7.3 履约担保`、`DR037_RESPONSE_BOND_SOURCE_PRESENT = false`
- 工作簿门禁 `case00{1,2,3}_review_workbook12_gate.json` = **PASS（43/43）**
- 定位门禁 `round12_locator_gate.json` = **PASS**（144 行精确比较，0 语义不一致，0 前缀/模糊）
  与 `review_workbook_round12_locator_generalization.json` = PASS
- 第 5 / 6 / 7 轮门禁在**第 12 轮构建上**复跑通过：`review_workbook_round12_banked_regressions.json`
  （`ROUND5_FIXTURE_F = PASS`：履约保证金行只显示/引用 `履约保证金`）
- 渲染 QA PASS：`case00{1,2,3}_review_workbook12_visual_qa.json`
- 全套测试 PASS：`review_workbook_round12_full_test_suite.{txt,xml}`
  （977 collected / 976 passed / 0 failed / 0 errors / 1 skipped）
- 文档—产物一致性 PASS：`v1_docs_state_consistency.json`
- Word 产物逐字节未变（`word_render_repeated = false`）

### 4.7 CASE002 第 12 轮 XLSX 人工复核准备（CURRENT，全部未勾选）

**本节目的是准备复核对象，不是复核结论。** CASE002 **尚未**人工复核：
`CASE002_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`。

| 项 | 值 |
| --- | --- |
| case | `case_002` |
| review build | `v1_round4_closure9_review_workbook12_final` |
| build dir | `acceptance/workspace/case_002/v1_round4_closure9_review_workbook12_final` |
| XLSX path | `acceptance/workspace/case_002/v1_round4_closure9_review_workbook12_final/投标项目复核表.xlsx` |
| XLSX SHA256 | `ac39ed7628fb7136624467f72a2593c59c49e88257f6b34eebe63f3e4b2c7b87` |
| 文件大小 | 75490 B |
| sheet 数 | 8（`投标项目复核表` + `00_复核总览` … `07_证据索引`，不含交付表本身时视图为 7） |
| 交付动态行数 | 45（`delivered_row_count`；`04_报价与限价` items 36 / limits 3 / blank_forms 0） |
| machine status | `ROUND12 = PASS`（三案例审计 PASS、工作簿门禁 43/43、定位门禁 45 行精确比较、第 5–7 轮复跑 PASS） |
| visual QA | `case002_review_workbook12_visual_qa.json` = PASS（`failed_checks = []`） |
| human status | `NOT_YET_CONFIRMED` |
| superseded candidates | 中间构建 `..._review_workbook12`（修复前代码）与 workbook11 及更早构建均为 **HISTORICAL / SUPERSEDED**，构建报告见 `case_002_review_workbook_build12_superseded.json` |

逐表复核范围（A–I，全部未勾选）：

- [ ] A. 交付表 `投标项目复核表`（45 行动态行 + 模板/签章区）
- [ ] B. `00_复核总览`（仪表盘计数：投标响应复核项 / 合同风险提示项 / 事实状态）
- [ ] C. `01_项目事实`（23 项事实的状态与来源证据）
- [ ] D. `02_关键条款`
- [ ] E. `03_资格否决与强制项`
- [ ] F. `04_报价与限价`（分项报价 36 项 + 限价 3 项）
- [ ] G. `05_文件结构与签章`
- [ ] H. `06_冲突与缺失`
- [ ] I. `07_证据索引`

CASE002 需要重点确认的点（全部未勾选）：

- [ ] 1. `budget = NOT_FOUND`（源文未找到可信预算）。**不得**凭空写成 `8,000,000`
- [ ] 2. `max_price = 7507785.65` 且状态为 `RESOLVED`（第 13 页 / 投标人须知前附表 / 11.3 最高投标限价）。
      预算与最高限价**必须分开**呈现
- [ ] 3. 分项报价/限价行均有源证据支撑；以**当前机器证据**的准确行数为准
      （`04_报价与限价`：items 36 / limits 3），不要沿用对话里的旧数字
- [ ] 4. ★ 标记语义：源文 `★` **不自动**等于否决。CASE002 的源文标记含义可能是
      「必备证明材料（MANDATORY_PROOF）」而非否决；人工需分别检查**源标记 / 是否强制 / 否决后果**三个维度
- [ ] 5. 跨页的价格/限价表在逻辑上连贯（限价 → 分项限价 → 无效投标后果）
- [ ] 6. **无 CASE001 专属数据泄漏**（CASE001 的人名/页号/条款/金额不得出现在 CASE002）
- [ ] 7. 合同风险 / 投标响应分离在 CASE002 中依然可理解
- [ ] 8. 证据定位与标题（页码 / 章节 / 条款）可读且与源文一致
- [ ] 9. 证据摘要**无实质性中截断**、无重复片段
- [ ] 10. 人工结论保持空白 / `NOT_YET_CONFIRMED`，直到人工真正打开 CASE002 工作簿复核完毕

> **CASE002_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED**
> `REVIEW_OBJECT = acceptance/workspace/case_002/v1_round4_closure9_review_workbook12_final/投标项目复核表.xlsx`
> `SHA256 = ac39ed7628fb7136624467f72a2593c59c49e88257f6b34eebe63f3e4b2c7b87`
> `MACHINE_STATUS = PASS`（Round12 三案例审计 / 工作簿门禁 43/43 / 定位门禁 45 行 / 渲染 QA PASS）
> `HUMAN_STATUS = NOT_YET_CONFIRMED`
> `NEXT_ACTION = 用桌面 Microsoft Excel 打开上面这个确切 XLSX，按本节 A–I 与 1–10 项逐条复核`
>
> 该文件**尚未**被人工复核；本节的任何复选框都不得由自动化勾选。

### 4.5 第 11 轮（canonical EvidenceUnit 结构标题保真）人工复核点（全部未勾选，HISTORICAL）

本轮不变量：**canonical EvidenceUnit 必须坐落在拥有它的源结构容器中**。
精确定位门禁只证明 `XLSX == formatter(unit)`，不证明该 unit 就是正确的源单元；
标题必须来自真实章/节/条容器，正文句子永不作为标题。

- [ ] E47 授权行的定位指向 `3.7 响应文件的编制`（81% 文本属 3.7.3），不再是 `3.3 澄清和补正`
- [ ] E57 合同解除行的 section 为 `第七条 其他约定`，不再把正文句子当标题
- [ ] DR048 / DR052（第五条下的 5.2）定位为 `第五条 交（提）货地点、方式及费用`，不再误引第六条
- [ ] DR037 显式声明第二来源（`依据第N页核对另一来源条款`），无「依据第18页」而证据为第11页的无解释引用
- [ ] 交付单元格无重复拼接（`资格要求 格要求`、`营业 执照 执照`），且源文自身「标签 值」布局未被误折叠
- [ ] 证据摘要截断不在源标识符中间（如 `GB50015-2`），且截断已用 `…` 显式标注
- [ ] 第 10 轮合同风险分离保持不变（合同风险行仍在 `九、`，`是否强制` 空白，`风险级别 = 风险提示`）
- [ ] 人工结论列**由人**勾选；自动化永不勾选，也永不把 `CASE001_XLSX_MANUAL_REVIEW` 置为 PASS

机器闭环证据（**已通过，不代替人工复核**）：

- 第 11 轮三案例审计 PASS：`review_workbook_round11_case_00{1,2,3}.json` / `.md`
  （`0 failed check` / `0 failed fixture`）、泛化 `review_workbook_round11_generalization.json` = PASS
- 工作簿门禁 `case00{1,2,3}_review_workbook11_gate.json` = **PASS（43/43）**
- 定位门禁 `round11_locator_gate.json` = **PASS**（144 行精确比较，0 语义不一致，0 前缀/模糊）
- 结构门禁计数：`BODY_PROSE_HEADING_COUNT = 0`、`FOREIGN_STRUCTURAL_HEADING_COUNT = 0`、
  `DUPLICATED_SOURCE_FRAGMENT_COUNT = 0`、`MID_TOKEN_EVIDENCE_TRUNCATION_COUNT = 0`、
  `MULTI_SOURCE_EVIDENCE_ROLE_AMBIGUITY_COUNT = 0`
- 第 5 / 6 / 7 轮门禁在**第 11 轮构建上**复跑通过：`review_workbook_round11_banked_regressions.json`
- 渲染 QA PASS：`case00{1,2,3}_review_workbook11_visual_qa.json`
- Word 产物逐字节未变（`word_render_repeated = false`）

### 4.4 第 10 轮（投标响应 vs 合同风险）人工复核点（HISTORICAL，全部未勾选）

本轮产品决策：**报价/商务响应 = 投标响应项；合同条款 = 投标前风险识别项**。
纯中标后合同条款**不得**影响投标符合性、否决或评分；它只用于投标前警示投标团队。
**源文章节不决定复核阶段**（合同章里的报价/成本条款仍是投标响应项）。

- [ ] 主表第 02 表类别已拆分为 `四、报价与商务响应` 与 `九、合同风险提示（投标前识别）`
- [ ] 合同风险行 `是否强制` 为空白、`风险级别 = 风险提示`（不出现 `一票否决`）
- [ ] 合同风险行**不在** `03_资格否决与强制项` 中，且无 `否决性 = 是` / `SUBSTANTIVE_*`
- [ ] 合同风险单元格块标签为 `合同风险提示：`，复核要点为投标前内部风险决策步骤
- [ ] 合同风险行没有「核对响应文件已载明…」「确认响应文件接受该比例」「与响应文件一致」等响应侧措辞
- [ ] `PROJECT_WARRANTY = 24 个月` 仍作为投标/技术响应项；`质保金 12 个月` / `5%` 为合同风险，二者未合并
- [ ] 履约保证金（中标后/签订合同前提交）显示为合同风险，**未**显示为投标否决
- [ ] 投标保证金（响应保证金）、最高限价、报价完整性、税率口径、报价费用范围、
      银行承兑评分、付款条件评分、价格评分、供货期、交货地点、质量要求、投标有效期
      **仍**为投标响应/评分项
- [ ] 仪表盘分别显示「投标响应复核项」与「合同风险提示项」，且合同风险数不进入否决/实质性/阻断计数
- [ ] 人工结论列**由人**勾选；自动化永不勾选，也永不把 `CASE001_XLSX_MANUAL_REVIEW` 置为 PASS

机器闭环证据（**已通过，不代替人工复核**）：

- 第 10 轮三案例审计 PASS：`review_workbook_round10_case_00{1,2,3}.json` / `.md`
  （`0 failed check` / `0 failed fixture`）、泛化 `review_workbook_round10_generalization.json` = PASS
- 工作簿门禁 `case00{1,2,3}_review_workbook10_gate.json` = **PASS（43/43）**
  （含 `review_stage.contract_risk_is_not_a_bid_blocker`）
- 定位门禁 `round10_locator_gate.json` = **PASS**（144 行精确比较，0 语义不一致，0 前缀/模糊匹配）
- 第 5 / 6 / 7 轮门禁在**第 10 轮构建上**复跑通过：`review_workbook_round10_banked_regressions.json`
- Word 产物逐字节未变（`word_render_repeated = false`）

### 4.3 第 9 轮（送达内容语义 + 定位精确格式化）人工复核点（HISTORICAL，全部未勾选）

本轮修复规则：分档只在**其中一档**成立；项目决定与提问/澄清截止是两个关切；复核动作只引用
**本行自己的**页码/条款；源文拼接与外来标题必须清理；基本分与最高分是两件事；
质保金/质保期行必须引用**本合同条款**；证据定位必须等于**本行规范证据单元经唯一生产格式化函数**
的输出，并与已保存 XLSX **精确相等**（禁止前缀/包含/模糊匹配）。

- [ ] 银行承兑分档（D23）与付款条件分档（D38）各自保留条件与分值，且只要求满足其中一档
- [ ] 报价公式（D50）：基本分 30 与本项最高 40 是两件事；评分规则为**核验**而非要求投标人重述
- [ ] 采购预备会（D56）与提问/澄清截止是两个独立关切，各自的动作只讲自己的事
- [ ] 提交截止行（D57）的动作只引用本行自己的页码/条款
- [ ] 营业执照（D16）与响应文件格式（D22）没有重复/损坏的源文拼接
- [ ] 质保期释放（D40）与质保金比例（D43）行引用**本合同条款**，不出现外来章节标题
- [ ] 有效期行（D34）的定位指向本行自己的前附表条款
- [ ] 证据定位等于 `expected_locator_for_unit` 的输出（精确比较，无前缀/模糊匹配）
- [ ] 人工结论列**由人**勾选；自动化永不勾选，也永不把 `CASE001_XLSX_MANUAL_REVIEW` 置为 PASS

机器闭环证据（**已通过，不代替人工复核**）：

- 定位门禁 `round9_gate_integrity.json` = **PASS**（`ROUND9_GATE_INTEGRITY = PASS`；
  `locator comparison = EXACT_FORMATTER_OUTPUT`；`prefix/fuzzy matching = 0`；
  `actual saved XLSX locator semantic mismatches = 0`；三案例 50/45/49 = 144 行逐行比较）
- 第 9 轮三案例审计 PASS：`review_workbook_round9_case_00{1,2,3}.json` / `.md`
  （`0 failed check` / `0 failed fixture`）、泛化 `review_workbook_round9_generalization.json` = PASS
- 第 9 轮送达文本前后对照：`review_workbook_round9_case_001_before_after.json` / `.md`
  （第 8→9 轮逐行、按地址比较，含定位门禁表）
- 第 5 / 6 / 7 轮门禁在**第 9 轮构建上**复跑通过：`review_workbook_round9_banked_regressions.json`
- 复核工作簿门禁 `case00{1,2,3}_review_workbook9_gate.json` = PASS（42/42）
- Word 产物逐字节未变（`word_render_repeated = false`）

### 4.1 第 7 轮人工 Excel 复核结论（保留，不得改写）

**人工结论：`CASE001_XLSX_MANUAL_REVIEW = FAIL`（人工复核未通过）。**
复核对象：`acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook7/投标项目复核表.xlsx`
（sha256 `d2381158cc390f6ca871b452252638d3f6aff1470b366b463965ac4cb56f9717`，71394 B）。

失败范围（`fail_scope`）：`FINAL_RENDERED_TEXT_FIDELITY`、`SCORING_TIER_SEMANTICS`、
`CROSS_SHEET_RISK_CONSISTENCY`、`SOURCE_FORM_CLASSIFICATION`。人工点名 13 项，
逐项地址与修复前后对照见 `review_workbook_round8_case_001_before_after.md`：

| 人工发现 | 行 | 地址 | 人工观察 |
| --- | --- | --- | --- |
| D14 | `DR036` | `投标项目复核表!D14` | 投标保证金否决条款的否定条件被交叉引用截断 |
| D37 | `DR037` | `投标项目复核表!D37` | 履约保证金没收条款的否定条件被交叉引用截断 |
| D23 | `DR041` | `投标项目复核表!D23` | 银行承兑 100%/50% 两档被写成须同时满足 |
| D50 | `DR040` | `投标项目复核表!D50` | 报价公式的基本分 30 被写成第二个最高分 |
| D39 | `DR044` | `投标项目复核表!D39` | 合同付款宽限期的源空白被渲染成不完整句子 |
| D45 | `DR046` | `投标项目复核表!D45` | 技术标准清单在第 3 项后可见截断 |
| D46 | `DR047` | `投标项目复核表!D46` | 带星号第三方检测要求吸收了下一章标题「第四条」 |
| D16 | `DR005` | `投标项目复核表!D16` | 营业执照要求重复渲染 |
| D56 | `DR016` | `投标项目复核表!D56` | 「不召开采购预备会」的动作写成另一个问题的动作 |
| D34 | `DR017` | `投标项目复核表!D34` | 询比有效期行的定位指向了分包章节标题 |
| DR013 | `DR013` | `投标项目复核表!D53` | 旧表 一票否决 与 03 表空白否决依据矛盾 |
| DR038 | `DR038` | `投标项目复核表!D54` | 旧表 一票否决 与 03 表空白否决依据矛盾 |
| 04 表 | — | `04_报价与限价` | 第 53 页类似项目情况表被误分类为空白报价表单 |

必需不变量：`FINAL DELIVERED TEXT MUST CARRY THE SOURCE'S OWN MEANING`。

### 4.2 第 8 轮（送达文本保真）人工复核点（HISTORICAL，全部未勾选）

本轮修复规则：保留极性词与完整有效子句；分档是**条件式备选**（不得要求同时满足）；
源空白保持空白；按业务含义而非字面出处校验；跨表风险语义一致
（源标记 / 实质性状态 / 响应阶段否决 / 逾期不予受理 四者相互独立）；
按源标题与列结构判定表单类型。

- [ ] 第 7 轮点名的 13 项发现确已修复（逐项对照 `review_workbook_round8_case_001_before_after.md`）
- [ ] 否定条件与后果动词同时出现在同一句内（D14「不按…3.4.1…否决」、D37「不能按…7.3.1…放弃成交」）
- [ ] 100%/50% 银行承兑只要求满足**其中一档**；基本分 30 与最高分 40 是两件事
- [ ] 源空白（如合同付款宽限期 `＿＿＿＿`）在交付文本中仍是空白，且句子完整
- [ ] 技术标准清单没有被可见截断；带星号要求没有吸收下一章标题
- [ ] 要求正文没有重复渲染的短语
- [ ] 项目决定（不召开 / 不组织 / 不允许）的运行性动作出现在该行自己的「复核要点」里
- [ ] 旧表 `风险级别` 与 03 表 `否决性` 双向一致（`一票否决` ⟺ `否决性 = 是`）
- [ ] 询比有效期行的证据定位指向本行自身的前附表行，不是分包章节标题
- [ ] 类似项目情况表按源标题/列结构分类为**业绩/资格表单**，不是空白报价表单
- [ ] 人工结论列**由人**勾选；自动化永不勾选，也永不把 `CASE001_XLSX_MANUAL_REVIEW` 置为 PASS

机器闭环证据（**已通过，不代替人工复核**）：

- 第 8 轮三案例审计 PASS：`review_workbook_round8_case_00{1,2,3}.json` / `.md`
  （`0 failed check`；CASE001 另含 13/13 人工夹具）、泛化 `review_workbook_round8_generalization.json` = PASS
- 第 8 轮送达文本前后对照：`review_workbook_round8_case_001_before_after.json` / `.md`
  （49 行逐行、按地址比较；36 行变化，13 行未变化）
- 渲染 QA PASS：`case00{1,2,3}_review_workbook8_visual_qa.json`（`failed_checks = 0`；
  `clipping_bounded` 有界 WARN：CASE001 **9** / CASE002 **10** / CASE003 **27**，非失败）
- 第 5 / 6 / 7 轮门禁在**第 8 轮构建上**复跑通过：`review_workbook_round8_banked_regressions.json`
- 复核工作簿门禁 `case00{1,2,3}_review_workbook8_gate.json` = PASS（42/42，含修正后的
  ★/否决性分离、前附表证据定位与交付文本=计划投影三项）
- 三案例泛化回归 `three_case_regression.json` = PASS（`failed_checks = []`）
- 全套测试：`review_workbook_round8_full_test_suite.txt` / `.xml` =
  **893 collected / 0 failed / 0 errors / 1 skipped**
- Word 产物未重新渲染：DOCX / PDF / 报告与已验收 closure8 构建逐字节相同（三案例）
- 状态：`CASE001_XLSX_MANUAL_REVIEW = AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`（**人工尚未置为已确认**）、
  `CASE002_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、`CASE003_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`

> **历史复核对象（HISTORICAL，已被上表取代）**：第 1 轮后继构建
> `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook1/投标项目复核表.xlsx`
> （CASE002 `case_002/v1_round4_closure8_review_workbook1`、CASE003 `case_003/v1_round4_closure8_review_workbook1`），
> 当时门禁 37/37 PASS、渲染 QA PASS。第 2 / 3 / 4 / 5 / 6 轮后继构建
> （`..._review_workbook2` … `..._review_workbook6_marker_closure`）同样为历史。全部**未删除**。
> 第 7 轮后继构建（`..._review_workbook7`，CASE002/003 为 `v1_round4_closure8_review_workbook7`）
> 是**人工判 FAIL 的那一版**，作为失败证据保留，未删除、未改写。

### 第 7 轮（适用源解析 / 否决作用域 / 证据定位保真）人工复核点（HISTORICAL，全部未勾选）

本轮链条为 `APPLICABLE SOURCE → SEMANTIC SCOPE → FINAL DISPLAYED REQUIREMENT →
EXACT MATCHING EVIDENCE LOCATOR`。人工复核时请逐项确认：

- [ ] 个案化前附表/日程值（如 `1.10.1 采购预备会 不召开`、`1.11.1 踏勘现场 不组织`、
      `*1.12 分包 不允许`、`*1.4.5 供货期`、`*1.4.6 交货地点`、`7.3 履约保证金`）显示的是
      **前附表的值**，而不是"见供应商须知前附表"的通用正文
- [ ] 适用源的页码/条款号指向**前附表页**（CASE001 为第 9 / 10 / 11 页），不是通用正文页（第 16 页）
- [ ] `SPECIALIZES` 情形（`7.3.1 履约保证金`）父条款措辞保留，同时以"项目专用值："附加个案值
- [ ] 否决/实质性语义只出现在真正会被否决的行；仅影响得分、仅中标后取消、合同责任、
      逾期不予接受等**不得**显示为响应性否决
- [ ] 每行的显示要求、证据摘录、页码、章节、条款号指向**同一个**源语义单元
- [ ] 证据摘录不跨越相邻源单元的**另一个**要求（例如有效期行不应同时引用响应保证金行）
- [ ] 多条款要求（CASE002 `DR026`）显式链接全部证据单元（PRIMARY + LINKED），没有丢弃任一来源
- [ ] 同一平台的不同角色（采购服务平台 / 交易 / 上传 / 开标 / 公告）没有被折叠成一个事实
- [ ] 最终源片段完整且不重复（无 `%%`、无重复编号项、无半句话）
- [ ] 人工结论列**由人**勾选；自动化永不勾选，也永不把 `CASE001_XLSX_MANUAL_REVIEW` 置为 PASS

### 第 6 轮（标记收口）人工复核点（全部未勾选，HISTORICAL）

第 6 轮把源文标记账目闭合到"出现次数"层级（`MarkerOccurrence`、
`DISCOVERED = ATTRIBUTED + EXPLICITLY_ACCOUNTED_NON_DELIVERED`）。人工复核时请逐项确认：

- [ ] 仪表盘 `B27` 标签为**行数**语义（带源标记的复核条目数），不是标记出现次数
- [ ] 三个计数彼此独立且不得互相替代（出现次数 / 带标记行数 / 实质性行数）
- [ ] 每个源文标记出现都有归属或明确的非交付处置（无 `UNRESOLVED`）
- [ ] `★` 未被自动等同于否决
- [ ] 背景非行动项的处置理由成立，且没有掩盖已交付要求


### 第 3 轮（复核关注点归属）人工复核点（全部未勾选）

第 3 轮把每一行绑定到一个**人工复核关注点**：行的招标文件要求、复核要点、通过标准、准备材料、
不满足后果、评分提示必须同源**且**同关注点（`SourceRequirementAtom → ReviewConcern → ReviewPoint`）。
人工复核时请逐项确认：

- [ ] 每一行 displayed source requirement 与 ReviewConcern 是同一事项
- [ ] 复核要点 / 通过标准 / 准备材料 / 后果 / 评分提示均属于同一个关注点
- [ ] 不存在真实但属于其他关注点的数字串入当前行
- [ ] 不存在属于其他关注点的准备材料串入当前行
- [ ] 不存在属于其他关注点的否决后果串入当前行
- [ ] 采购人/评审小组内部程序没有被当成普通投标人响应任务
- [ ] 项目质保期 24个月作为 `PROJECT_WARRANTY` 单独核对
- [ ] 5% 质保金比例作为 `RETENTION_MONEY_RATIO` 单独核对
- [ ] 合同付款语境的 12个月作为 `RETENTION_RELEASE_PERIOD` 单独核对
- [ ] 24个月 / 12个月没有被错误报告成同一质保事实冲突
- [ ] 签章、电子上传、授权委托分别核对，不互相串项
- [ ] 投标保证金的金额/形式/账户/截止时间/凭证材料没有串入业绩或授权材料
- [ ] 文件组成来自真正的响应文件组成/格式源证据，不来自异议函或内部程序
- [ ] 评分项的分值、档位、证明材料属于同一评分因素
- [ ] `06_冲突与缺失` 只包含真实未决/冲突，不包含关键词造成的假冲突
- [ ] `clipping_bounded` WARN 中不存在影响人工阅读的关键文本截断
- [ ] 随机抽查至少 20 条 ReviewPoint：source requirement / human check / pass criteria / evidence 四者确属同一事项

### CASE001 复核步骤（人工填写，自动化永不勾选）

- [ ] 打开工作簿顶部原交付表 `投标项目复核表`，核对项目信息与清单行是否仍然正确
- [ ] `00_复核总览`：核对项目标识、事实摘要与三组公式统计是否与 `01`–`07` 视图一致
- [ ] `01_项目事实`：逐行核对 23 项事实；`NOT_FOUND` 行必须保持 `NOT_FOUND`，不得由人工凭空补值
- [ ] `01_项目事实`：`NEEDS_REVIEW`（`budget`）行的候选值与 `06_冲突与缺失` 的说明是否一致
- [ ] `02_关键条款`：核对报价/保证金/工期/质保/有效期等条款抽取结果与证据定位
- [ ] `03_资格否决与强制项`：逐条核对 ★ 与「否决性」行（要求正文 / 复核动作 / 核验标准分列）
- [ ] `04_报价与限价`：核对最高限价来源；分项报价表条目是否与源文件一致（空白表单须保持空白）
- [ ] `04_报价与限价`：确认"预算"与"最高限价"没有被合并成一个数
- [ ] `05_文件结构与签章`：核对签章/签字/日期/附件要求与源文件章节一致
- [ ] `06_冲突与缺失`：对每条未决项给出结论与依据
- [ ] `07_证据索引`：抽查定位是否指向真实源位置
- [ ] 结论：可接受 / 需修改
- [ ] 复核人：____________  日期：____________

> 复核纪律：`ProjectFacts` 是事实 SSOT。人工在工作簿里填写的复核值与结论**不会**写回
> `project_facts.json`；若人工发现事实错误，须走 `scripts/apply_resolution.py` 的受控流程
> （仅 `NEEDS_REVIEW` 可被人工裁决），并留下审计记录。

### 第 2 轮（复核要点合成）新增复核点（HISTORICAL，全部未勾选）

第 2 轮把每一行改写为**合成的人工复核要点**：招标文件要求 / 复核要点（①②③）/ 通过标准 /
不满足后果 / 准备材料 / 评分提示。人工复核时请额外确认：

- [ ] 每一行的「复核要点」是否与「招标文件要求」（源条款引文）指向同一件事
- [ ] 「通过标准」是否描述可观察状态（而不是重复要求原文）
- [ ] 「不满足后果」是否确有源条款依据（无依据的行应没有此块）
- [ ] 行内出现的数字是否属于该行：金额只出现在报价/保证金行，天数只出现在工期/有效期/
      质保/响应时间行；费用（标书费/平台服务费）与电话号码不得出现在复核要点中
- [ ] `02_关键条款` / `03_资格否决与强制项` 的正文、复核动作、核验标准是否与交付表 D 列同源
- [ ] 第 2 轮被过滤的非行动项（CASE001：1 条"售后服务与运维"平台服务费条款）是否确无投标
      人义务，过滤是否正确
- [ ] 渲染 QA 剩余的 `clipping_bounded` WARN（CASE001 10 / CASE002 17 / CASE003 26）中，
      `02_关键条款` 与 `03_资格否决与强制项` 的 E/F 列小幅截断是否影响阅读
- [ ] 结论：可接受 / 需修改
- [ ] 复核人：____________  日期：____________

> 证据：`review_workbook_round2_content_quality.json` / `.md`（含 8 组 BEFORE→AFTER 与
> 7 项已知坏例结果）、`case_00{1,2,3}_review_workbook_{build,gate,visual_qa}_round2.json`、
> `review_workbook_round2_full_test_suite.txt` / `.xml`（684 收集 / 683 passed / 1 skipped /
> 0 failed / 0 errors）、`tests/test_round63_review_point_synthesis.py`（45 项，含 19 种
> 复核类型覆盖测试）。
> 自动化结论：`CASE001_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、
> `CASE002_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、`CASE003_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、
> `V1_PRODUCTION_CANDIDATE = false`、`READY_FOR_SUBMISSION = false`。以上复选框全部保持未勾选。

## 5. Round3 最终状态产物：测量聚合修正与取代记录

第 3 轮最终状态的**首个**产物 `review_workbook_round3_final_status.json` / `.md` 存在一处
**测量/呈现缺陷**：聚合脚本读取了门禁报告里不存在的字段名（`checks_passed` / `checks_total`，
实际字段为 `passed` / `check_count`），因此三案例的门禁计数被打印成 `PASS None/None`，
JSON 里对应字段为 `null`。**该缺陷只影响计数呈现，不影响任何结论**——当时与现在的
`result` 均为 `PASS`，门禁本身一直是 40/40。

处理方式：**不覆盖历史产物**，而是生成继任产物并记录取代关系。

| 项 | 值 |
| --- | --- |
| 当前产物（CURRENT） | `review_workbook_round3_final_status_reconciled.json` / `.md` |
| `status` | `PASS` |
| `blockers` | `[]` |
| CASE001 / CASE002 / CASE003 门禁 | `40/40` / `40/40` / `40/40` |
| `supersedes` | `review_workbook_round3_final_status.json` |
| `supersession_reason` | `MEASUREMENT_AGGREGATOR_KEY_MISMATCH` |
| 被取代产物的 sha256 | `d225dc141ada3c119c9b4e2ec02eaa0394eb6212a515e698fad35db5b33190a0`（**逐字节保留，未改动**） |
| 修复 | `scripts/v1_review_workbook_round3_final_status.py` 改为读取 `passed` / `check_count`，并新增 `--supersedes` / `--supersession-reason` 记录取代关系 |

- [ ] 确认已按上表打开**当前**产物 `review_workbook_round3_final_status_reconciled.json`，
      而不是被取代的那个


---

## Word 源版式保真 — CASE002 人工复核对象（第 14 轮，**自动关闭待人工确认**）

自动化已闭环；下列复选框**全部未勾选**，必须由人工在桌面 Microsoft Word 中打开**确切**产物后填写。

| 项 | 值 |
| --- | --- |
| 构建 | `acceptance/workspace/case_002/v1_word_source_fidelity_arch3` |
| DOCX | `acceptance/workspace/case_002/v1_word_source_fidelity_arch3/基础投标文件.docx` |
| DOCX SHA256 | `8772eb2a7df1034403188b56269efe6ac90727f41deac995b91cb853f3bf7acf` |
| PDF SHA256 | `b4f0ec41d9632826e8ce5f12acd2841cd20ac0cd875a53ffa5f88dae98b09c8d` |
| generation_report SHA256 | `266cdf3dd5799e84ee01119e69c0f48078f79ad0aec50032e74bdce09c3a48c7` |
| 机器状态 | `CASE002_WORD_SOURCE_FORM_FIDELITY = PASS`；`GENERIC_WORD_SOURCE_FIDELITY = PASS`；`SOURCE_TEXT_COMPLETENESS = PASS`（missing/duplicate/zero_owner/multiple_owner = 0）；`THREE_CASE_GENERALIZATION = PASS` |
| 段落流架构 | `PARAGRAPH_FLOW_FIRST` 审计：`PARAGRAPH_POSITIONING_TAB_COUNT = 0`、`CENTER_ALIGNMENT_HACK_COUNT = 0`、`RIGHT_ALIGNMENT_HACK_COUNT = 0`、`FIRST_LINE_TAB_HACK_COUNT = 0`；`unreachable_positioned_blank_count = 0` |
| 人工状态 | `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`（**不是** `HUMAN_PASS`） |
| 历史构建（**不是**当前对象） | `v1_word_source_fidelity_arch2`（DOCX `8b0c8b01…591ad`）；`v1_round4_closure8`（DOCX `1e694c00…5989d`） |

- [ ] 在桌面 Microsoft Word 中打开上表**确切** DOCX（不是任何历史构建）
- [ ] 封面日期行为三个独立可填空白（年 / 月 / 日 前各一）
- [ ] 投标函（`一、投标函` 起至其 `日期：` 行）为**一个**页面
- [ ] 投标函正文左边界与源文一致（源 ≈ 70.92 pt）
- [ ] 项目名称以**带下划线的已解析值**落在源槽位内（源规则 196.90→304.90）
- [ ] 投标总价大写 / 小写槽位均为可编辑下划线空白
- [ ] 项目负责人行与有效期行均为**同一行**
- [ ] 开标一览表为**一个**逻辑可编辑表格；`实施周期 = 18个月`、`交货地点 = 西安市内`
- [ ] 授权委托书结构完整、无提前换行、无裁剪/重叠（无头渲染的字距差异见审计报告）
- [ ] 跨页报价明细仍为**一个**逻辑可编辑表格
- [ ] 未发现源文文字丢失（机器：missing/duplicate/zero_owner/multiple_owner = 0）

> 无头 LibreOffice 渲染与桌面 Word 的字距差异已按 `word_render_authority_audit.json` 归类为
> `HEADLESS_FONT_SUBSTITUTION_ONLY`（宿主机缺少 `仿宋`）；该分类**不**免除桌面 Word 复核。
