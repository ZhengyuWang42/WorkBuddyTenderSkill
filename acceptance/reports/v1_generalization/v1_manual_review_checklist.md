# V1 人工 Word 复核清单 (human manual review checklist)

本清单由自动化证据生成，**尚未完成**。自动化结论为 `V1_AUTOMATED_CANDIDATE`；`MANUAL_WORD_REVIEW_REQUIRED = true`、`READY_FOR_SUBMISSION = false` 在人工复核签字前保持不变。

权威状态与冻结契约见 [`docs/V1_PROJECT_STATE.md`](../../../docs/V1_PROJECT_STATE.md) 与 [`docs/V1_DECISIONS.md`](../../../docs/V1_DECISIONS.md)。

**注：第 1 节列出的构建目录属于历史轮次**（自动化结论仍然有效，但 build 目录不是当前被接受/最新候选）。
**当前 CASE001 复核对象见第 1.6 节。**

> 本清单中的任何复选框**都不得**由自动化勾选。所有 `[ ]` 保持未勾选状态，直到人工在桌面 Microsoft Word 中实际确认。

## 0.5 人工复核第 4 轮结论（ROUND-4 HUMAN FINDINGS）

> **当前复核对象（CURRENT）**：`acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8`
> （DOCX `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230`，
> PDF `3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927`）。
> 下表 A/B/C 三项发现均已**自动化关闭**，等待人工在这一 build 上重新复核。
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
> 自动化结论仍然有效；但 CASE001 的**当前**复核对象是第 1.6 节的 `v1_manual_fidelity_round3_word_review_final`。
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

**这是当前应打开复核的 build，并且它已经是 `case_001_current_build.json` 的指针目标。**

| 项 | 值 |
| --- | --- |
| build id | `v1_manual_fidelity_round3_word_review_final` |
| build dir | `acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final` |
| manifest | `build_manifest.json`（`FRESH_BUILD`，pipeline rc 0，render rc 0） |
| DOCX | `16dc0ae275cb43799a76df5770b43fb7dc76b9d93b374e07621792419f95a191`（45533 B） |
| PDF | `ad2692ef9e0baa47a60ff17662cb3259d8a7b3ac47cde55e2fbc8fde1860a174`（301445 B，22 页） |
| 源 PDF | `8e2bfb00e1a0c595db16d179477d9a09769ab82e45f63d476c3c8c459d46aa27`（61 页） |
| 指针目标 | `acceptance/reports/v1_generalization/case_001_current_build.json` → `v1_manual_fidelity_round3_word_review_final`（`POINTER_CHECK = PASS`） |
| 自动化状态 | `HARD_BREAK_FIDELITY = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`，`documented_structural_deviation_count = 1`，`unexplained_structural_split_count = 0`，`unexpected_w_br_count = 0`，`unexpected_w_cr_count = 0` |
| 人工状态 | `CASE001_MANUAL_WORD_REVIEW = NOT_YET_CONFIRMED`（本清单**全部未勾选**） |
| 上一候选（已被取代，**未删除**） | `v1_manual_fidelity_round3_word_review_followup`（其 `w:br` 已在本轮关闭）；状态与清单归档为 `*_superseded_by_unexpected_hardbreak_closure.{json,md}` |

生成文档 22 页，生成页 = 源页序 − 39。

> **本轮变化摘要（复核时请注意）：** 与上一候选相比，DOCX 只有**两处**内容差异会产生像素变化——
> 即本文件第 1.6.1 节的 `委托期限：` 源表单行：它此前被交付成**两行**（标签一行、规则+句号一行），
> 现在交付成**一行**。除此之外整篇文档 `generated_w_br = 0`、`generated_w_cr = 0`。
> 第 7.1 节那**一个**已复核段落边界**完全未动**。

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

当前指针目标（`case_002_current_build.json`）：`acceptance/workspace/case_002/v1_manual_fidelity_round3_word_review_final`
DOCX sha256 = `5206b4103338f4319c0510d3edaeed15e9628164db7161ca2b83e66989f08012`

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

当前指针目标（`case_003_current_build.json`）：`acceptance/workspace/case_003/v1_followup3`
DOCX sha256 = `e013b1f24f8a05ee9dd5d6b88518306aec2c1ebb9694d127e65150d9cf3e2365`

> 本轮共用修复也重建了 CASE003，但重建产物的 `generation_report.json`（`1248666a…`）、
> `project_facts.json`、`normalized_document.json`、`source_format_qa.json` 与被接受产物
> **逐字节相同**，该案例有 **0** 条表单行换行，修复对它是 **no-op**。因此指针**不迁移**
> （不为 ZIP 时间戳而 churn），三案例回归以该产物自身的验收证据评分。
> 重建产物自身的验收报告保留为 `case003_acceptance_final.json`。

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

复核对象（后继构建，Word 产物与 closure8 逐字节相同）：

| 案例 | 工作簿 |
| --- | --- |
| CASE001 | `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook1/投标项目复核表.xlsx` |
| CASE002 | `acceptance/workspace/case_002/v1_round4_closure8_review_workbook1/投标项目复核表.xlsx` |
| CASE003 | `acceptance/workspace/case_003/v1_round4_closure8_review_workbook1/投标项目复核表.xlsx` |

机器闭环证据（**已通过，不代替人工复核**）：

- 工作簿门禁 37/37 PASS（`v1_review_workbook_gate.py`，三案例各自的 `*_review_workbook_gate.json`）
- 渲染 QA PASS（`v1_review_workbook_visual_qa.py`：LibreOffice PDF + 重算副本核对总览公式）
- Word 产物未重新渲染：DOCX `8dedddb7…`、PDF `3fe5b5b9…`、报告 `1274c205…` 与已验收构建逐字节相同
- 状态：`CASE001_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、`CASE002_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、`CASE003_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`

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

### 第 2 轮（复核要点合成）新增复核点（全部未勾选）

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
> `review_workbook_round2_full_test_suite.txt` / `.xml`。
> 自动化结论：`CASE001_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、
> `CASE002_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、`CASE003_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、
> `V1_PRODUCTION_CANDIDATE = false`、`READY_FOR_SUBMISSION = false`。以上复选框全部保持未勾选。
