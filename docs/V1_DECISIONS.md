# V1 决策与冻结契约（FROZEN DECISIONS）

本文件记录 WBTenderSkill / `tender-basic` V1 **已冻结的架构与验收契约**。
这些契约**不因为实现变化而放宽**；任何改动都必须走显式的范围/契约变更，而不是让新门禁变绿。

现行状态、开放偏差与开放任务见 [V1_PROJECT_STATE.md](V1_PROJECT_STATE.md)。

范围与治理基线见 [PROJECT_GOVERNANCE.md](../PROJECT_GOVERNANCE.md) 与 [MVP_SCOPE.md](../MVP_SCOPE.md)。
本文件是它们的**验收契约层补充**，不重复它们已经写明的治理条款。

---

## 1. 数据 / 语义权威契约

> **`ProjectFacts` 是事实值的 SSOT。**
> `SourceFormat` 拥有结构、可见编号、版式、源表格槽位与源视觉格式。
> `ReviewEvidence` 拥有证据检索与证据 locator。

| # | 契约 | 说明 |
| --- | --- | --- |
| D1 | 事实值只来自同一次运行的已校验 `ProjectFacts` | 渲染器、SourceFormat、ReviewEvidence、fixture、模型、生成的 Word 结构都不得创建替代事实值 |
| D2 | **缺失事实永不发明** | 没有可靠证据即 `NOT_FOUND`；`NEEDS_REVIEW` 只能在已有候选之间复核，或提交经精确 locator + 原文证据 + 值类型校验的 source-backed 候选 |
| D3 | 事实冲突 = `NEEDS_REVIEW`；事实缺失 = `NOT_FOUND` | 两个状态不可互换 |
| D4 | 语义补全必须带 **source evidence locator** | 无 locator 的补值一律拒绝 |
| D5 | 未知的投标人专属字段保持未填写 | 投标人名称、报价、签章、银行账户、项目经理、企业资质等保持占位符 |
| D6 | **纯展示性源标记不得成为事实** | 源表格的「不适用」标记（如 `/`）是 `SOURCE_FORM_NOT_APPLICABLE_MARKER`，既不生成事实也不生成事实候选 |
| D7 | CASE001 实例（冻结） | `lot_name` **保持 `NOT_FOUND`**，即使 `/` 作为源格式「不适用」标记被输出；`project_name = 事实值`，`project_number = 事实值`，`/` = 展示性标记，`、` = 源模板字面量 |
| D8 | **系统全局不得声称 `READY_FOR_SUBMISSION = true`** | 无最终项目级商务/法务/报价/签字盖章批准，任何自动化结论都不得置为 true |
| D9 | 事实字段集合固定为 23 个 | 复核模板的 64 项是条款证据检索/人工复核清单，不是 64 个事实字段，也不产生自动合规结论 |
| D10 | `project_number` / `tender_number` / `lot_number` / `budget` / `max_price` 永久语义独立 | 不得因标签相似而合并 |

---

## 2. P3 水平 / 源规则契约（HORIZONTAL / SOURCE-RULE）

### 2.1 冻结的八条 CASE001 P3 源规则

来源页：源 PDF 第 42 页；交付页：生成页 3。
冻结证据：`acceptance/reports/v1_generalization/case001_round3_p3semantic_reconciliation_status.json::frozen_contract.rules`

| 规则 | 变换策略（transformation_policy） | 几何意图（geometry_intent） | 源 x0 | 源 x1 | 源 y |
| --- | --- | --- | --- | --- | --- |
| R1（P42-R1） | `PLACEHOLDER_REPLACED_BY_VALUE` | `ANCHOR_START_ONLY` | 94.8 | 194.6 | 138.35 |
| R2（P42-R2） | `PLACEHOLDER_REPLACED_BY_VALUE` | `ANCHOR_START_ONLY` | 198.1 | 375.7 | 158.4 |
| R3（P42-R3） | `FIXED_EMPTY_SLOT` | `EXACT_SOURCE_SPAN` | 169.65 | 323.6 | 178.4 |
| R4（P42-R4） | `FIXED_EMPTY_SLOT` | `EXACT_SOURCE_SPAN` | 384.6 | 459.0 | 178.4 |
| R5（P42-R5） | `RESOLVED_VALUE_IN_FIXED_SLOT` | `ANCHOR_START_ONLY` | 131.85 | 181.4 | 198.35 |
| R6（P42-R6） | `RESOLVED_VALUE_IN_FIXED_SLOT` | `ANCHOR_START_ONLY` | 95.25 | 151.05 | 218.4 |
| R7（P42-R7） | `SOURCE_VALUE_UNDERLINE` | `EXACT_SOURCE_SPAN` | 352.8 | 388.8 | 318.35 |
| R8（P42-R8） | `PRESERVE_SOURCE_PLACEHOLDER` | `EXACT_SOURCE_SPAN` | 112.8 | 208.8 | 418.4 |

单位：pt。`tolerance_pt = 2.0`。

### 2.2 契约条款

| # | 契约 |
| --- | --- |
| P1 | 容差固定 **2.0 pt**。**不得放宽**（`tolerance_is_not_relaxed` 必须为 true）。 |
| P2 | **R3 / R4 / R7 / R8 两端点均为权威。** 必须同时满足 `source_x0` 与 `source_x1`。**不得退化为单端点接受。** |
| P3 | R1 / R2 / R5 / R6 为 `ANCHOR_START_ONLY`：只锚定起点，终点不设门禁。R6 的终点**不**门禁（历史测量到 1.65 pt 视差）。 |
| P4 | **不得重基线化源几何**（`p3_source_geometry_rebaselined` 必须为 false）。被接受的 composition set 必须不变（`accepted_composition_set_unchanged`）。 |
| P5 | 规则记账必须完整：`matched=8, lost=0, invented=0, out_of_tolerance=0`。 |
| P6 | **不得跨页绑定规则**（`no_cross_page_rule_binding`）。 |
| P7 | 每条规则**只有一个**执行 owner、**一个** `SourceFillApplication`，不得重复执行。 |
| P8 | 值来自 `ProjectFacts` 的规则必须记录 `value_from_project_facts = true` 与 `invented_value = false`。 |
| P9 | P3 水平门禁（phase 2）当前状态：**PASS**，`failed_checks = []`。 |

### 2.3 冲突时的裁决顺序

P3 几何契约与「同一 `w:p` 自然流」冲突时，**P3 几何契约优先**。
理由与证明见 [V1_PROJECT_STATE.md](V1_PROJECT_STATE.md) 第 7.1 节；
结论是 `DOCUMENTED_STRUCTURAL_DEVIATION`，而不是放宽任一契约。

---

## 3. 重排感知的垂直权威契约（REFLOW-AWARE VERTICAL AUTHORITY）

| # | 契约 |
| --- | --- |
| V1 | 长解析值**可以合法地**增加 Word 行。因此垂直验收权威是 **`REFLOW_AWARE_V1`**。 |
| V2 | 即使「强制重排」被独立证明，**旧的绝对源 y 相位门禁仍可能报红**；这是**预期**结果，不是缺陷。 |
| V3 | **禁止**用以下手段「修好」旧门禁：缩小字号、裁剪、重叠、（放宽容差）、重基线化源几何。 |
| V4 | 垂直门禁必须做行预算记账：`source_row_count` + `mandatory_extra_row_count = mandatory_minimum_row_count`，`generated_row_count` 必须等于该最小值，`unexplained_extra_row_count = 0`，`unexplained_blank_row_count = 0`。 |
| V5 | 生成的垂直行顺序必须保持（`generated_row_order_is_preserved`）。 |
| V6 | 残差必须在**未放宽的** 2.0 pt 容差内。当前实测 `maximum_residual_y_error_pt = 0.71`（原始 y 误差 65.79 pt 被重排记账解释）。 |
| V7 | 区域账本必须与基线一致（`region_ledger_matches_the_baseline`）。 |

---

## 4. 页面框架契约（PAGE FRAME）

| # | 契约 |
| --- | --- |
| F1 | **不得**为每一页独立地从该页稀疏的内容极值推导页边距。 |
| F2 | 页面框架必须由**跨页重复的源锚点**推导。CASE001 的框架为 `PORTRAIT_595x842_1`：left **70.8 pt**、right **70.9 pt**、top body frame **73.86 pt**、可用文本宽 **453.6 pt**。 |
| F3 | 框架锚点必须是重复文本边缘（左锚点支持 ≥ 2 页，CASE001 实际左锚点支持 12 页 `[41,42,44,45,46,47,49,50,51,52,53,61]`，右锚点支持 10 页）。 |
| F4 | 门禁阈值：框架边距 spread 容差 **0.5 pt**；居中标题容差 **2.0 pt**；表格宽度容差 **1.0 pt**；框架锚点最小支持 **2 页**。 |
| F5 | 源表格必须按**自身源宽度**绘制，**绝不**被 clamp 到 section 文本列。 |
| F6 | 历史效果：该决定修复了稀疏页面之间不一致的页边距。CASE001 现为 22/22 页边距 spread = 0.0 pt，居中标题最大中心误差 1.12 pt，5/5 表格复现源几何（最大宽度差 0.0 pt）。 |

---

## 5. Word 原生结构契约（WORD NATIVE STRUCTURE）

### 5.1 禁止使用

- textbox
- floating shape / 浮动对象
- overlay（叠放覆盖）
- 用于段落定位的合成版式表格（synthetic layout tables）
- 用下划线**字形**（underscore glyphs）当表单横线
- 不安全的 OOXML

### 5.2 必须使用

- 原生段落（paragraphs）
- 原生 run
- tab / 源定位锚点 tab
- 原生表格结构（table structure）
- Word 兼容的 spacing / indent / alignment
- 真实 Named Styles / Heading outline（导航与编辑性）

### 5.3 条款

| # | 契约 |
| --- | --- |
| W1 | DOCX 从全新 `python-docx Document()` 开始；旧定位 OOXML 渲染器仅供诊断。 |
| W2 | 源文件自有标题与列表保留**可见编号**、标点、编号后空格与序号间隔，不写 `numPr`（`SOURCE_LITERAL`）。 |
| W3 | 只有「格式自拟」等系统新增内容可使用隔离的 `GENERATED_AUTO` 自动编号族。 |
| W4 | 空槽位的下划线装饰由**绑定/源槽位**授权，不由陈旧的 registry 字段授权。 |
| W5 | 表单元格必须保持**单元格内部源行结构**（不得被压平成单行）。 |
| W6 | 源 run 的粗体 / 下划线必须传播；正文 prose 不得被误加下划线。 |
| W7 | 固定空白 span 必须完整（`fixed_blank_fidelity`）。 |
| W8 | 文档必须通过 word-safe 静态扫描、ZIP 完整性、OOXML 可解析、python-docx 重开、无文本框/浮动对象/嵌入位图、无合成版式表格。 |
| W9 | **静态检查与 LibreOffice 渲染不能替代桌面 Microsoft Word 正常打开确认。** |

---

## 6. 自然折行 vs 显式换行契约（NATURAL WRAP VS EXPLICIT BREAK）

| # | 契约 |
| --- | --- |
| B1 | **PDF 的视觉行边界不自动等于 Word 硬换行。** |
| B2 | 每个被检查的边界必须被分类为四类之一：`NATURAL_WRAP` / `SOURCE_EXPLICIT_BREAK` / `STRUCTURAL_ISOLATION_REQUIRED_BY_REFLOW` / `BUILDER_FORCED_BREAK`。 |
| B3 | **不得**仅因为 PDF 产生了另一个视觉行就创建 `<w:br/>`。 |
| B4 | 只有**源自己打印的**边界才是授权拆分：`SOURCE_EXPLICIT_BREAK`（源的列表项 / 源自有行）。 |
| B5 | **构建记录中的结构隔离是「关于该 build 的证据」，不是裁决**（`authorised_structural_split_between_tokens = false`）。 |
| B6 | `STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW` 必须被记录，但**不得自行授权**该拆分。 |
| B7 | 对于源为 `NATURAL_WRAP` 的边界：`same_word_paragraph`、`w_br_between_tokens`、`w_cr_between_tokens`、`empty_paragraph_between_tokens` 必须真实上报；**不得伪造 `same_word_paragraph = true`**。 |
| B8 | 当源为 `NATURAL_WRAP` 而生成结构为段落边界、且该偏差被复核接受时，必须记为 `DOCUMENTED_STRUCTURAL_DEVIATION`，原因是 `STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY`，并使可见额外间距为 0（等同源）。 |
| B9 | 「源断行是显式换行」这一重新标注（re-label）被**禁止**。 |
| B10 | 已复核的结构性偏差**永远不是** container fidelity：`container_fidelity = SOURCE_CONTAINER_MISMATCH` 必须显式给出，族状态为 `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`（**不是** `PASS`）。 |
| B11 | 门禁必须为**每类可观察事实各留一个计数器**，不得合并：`source_natural_wrap_boundaries` / `source_explicit_breaks` / `generated_w_br` / `generated_w_cr` / `generated_paragraph_boundaries` / `unexplained_structural_splits` / `documented_structural_deviation_count` / `builder_forced_breaks`。 |
| B12 | 任何 `w:br`/`w:cr` 若超出源自身行模型所能解释的数量，必须在 `hard_break_disclosure` 中逐条公开（含段落索引与文本），**不得静默容忍**。 |
| B13 | **表单行的换行判据必须是该空白自身的源几何，不是「本行是否已有文字」。** 当源证据证明标签、可编辑空白/规则、后缀属于**同一个源表行**时，Word 原生表示必须保持在**一个段落**内，用该规则自身的源推导 tab 到达，除非另有一条**被单独证明的更高权威约束**使其不可能。 |
| B14 | 唯一被承认的这类更高权威约束是**空白起点已经落在光标之后**（`blank_x0 + 1.0 < reach`）：光标只前进不后退，任何 tab 停靠点都无法把光标带回，因此该规则才另起一行源表单行。此判断必须记入 `positioned_form_layout_breaks`，含 `source_x0` / `source_x1` / `previous_reach_pt` / `overshoot_pt`，使「越界」是**可复算的几何事实**而不是推测。 |
| B15 | 由本条规则产生的 `w:br` 是**缺陷**（`BUILDER_FORCED_BREAK`），**不得**被记成 `DOCUMENTED_STRUCTURAL_DEVIATION`。`documented_structural_deviation_count` 只统计真正无法用 Word 原生构件表达、且经复核接受的边界。 |
| B16 | 该判据**不得**包含任何语料字面量、页号、段落序号、规则编号或 case 标识；同一实现必须对全部案例成立。残留的表单行换行必须逐条自证 `previous_reach_pt − source_x0 > 0`。 |
| B17 | **组合源槽位的语义执行校验必须在原子层面进行，不得在整条字符串层面进行。** 当源表把一个槽位写成「自身模板标点 + 一个或多个事实值 + （某具名分量为空时）源表自身的不适用标记」时，交付表面**按构造不期望**等于任何单个 `ProjectFacts` 字段；把整条表面与单个事实值逐字比较，是**无效的**语义执行测试。原子类别沿用仓库既有词汇：`FACT_VALUE` / `SOURCE_TEMPLATE_LITERAL` / `SOURCE_FORM_NOT_APPLICABLE_MARKER`（`tender_basic/source_fill_policy.py`）。 |
| B18 | 每个原子必须**独立可追责**：`FACT_VALUE` 的字段须存在于 `ProjectFacts` schema、其值须**逐字等于**权威解析值；`SOURCE_TEMPLATE_LITERAL` 须由源证据支持（源占位符文本 / 槽位提示 / 源 PDF 该规则跨度内实际印出的字符），且**不得**被解读为事实值；`SOURCE_FORM_NOT_APPLICABLE_MARKER` 须有呈现来源、**不得**覆盖已解析事实、**不得**把 `NOT_FOUND` 变成 `RESOLVED`、**不得**新建候选事实或改写 `ProjectFacts`。全部原子按序拼接必须**逐字重放**交付表面；未归类元、未追责文本、重复执行、越权事实字段一律硬失败。 |
| B19 | **组合感知门禁必须是原判据的严格超集，不是旁路。** 只含单个 `FACT_VALUE` 的普通槽位继续适用原有严格逐字相等契约（`SINGLE_FACT_STRICT_EQUALITY`）；组合槽位走 `ATOMIC_PROVENANCE`。两条路径都不得为任何规则号、页号、case 或字面量开例外。 |
| B20 | **槽位装饰（源下划线）是呈现归属，不是取值归属。** 源模板字面量与「不适用」标记可以继承源槽位的下划线，但仍分别是字面量与标记；装饰记录只能与原子类别**一致**，不得重新分类任何原子，也不得借装饰把源标点变成事实值。 |
| B21 | **过时的测量实现不会使底层的 `ProjectFacts` 契约过时。** 当门禁结论与源表、`ProjectFacts`、交付产物三者一致的证据冲突时，首先怀疑测量实现；修复门禁时**不得**改写历史红结论（以 `superseded_by` / `*_before_repair` 归档保留），**不得**改动渲染器、`ProjectFacts`、源标点或已交付的 DOCX/PDF。 |

### 6.1 结构性偏差证据契约（17 个条件）

一个「源为自然折行、容器为段落边界」的边界，只有在**全部** 17 个条件成立时才可被接受为
`REVIEWED_ACCEPTED`；任一条件缺失即保持 `unexplained_structural_split`（并导致族 FAIL）：

| # | 条件 | 读自 |
| --- | --- | --- |
| 1 | `source_evidence_proves_one_logical_paragraph` | 源模型（kind / row_count） |
| 2 | `source_boundary_classification_is_natural_wrap` | 源分类 |
| 3 | `generated_structure_is_a_native_paragraph_boundary` | 交付 OOXML |
| 4 | `generated_boundary_has_no_w_br_no_w_cr_no_empty_paragraph` | 交付 OOXML |
| 5 | `generated_boundary_spacing_is_zero_or_source_equivalent` | 交付 OOXML |
| 6 | `no_visible_blank_row_is_introduced` | 交付 OOXML |
| 7 | `reading_order_is_unchanged` | 源↔交付字符顺序 |
| 8 | `text_content_is_unchanged` | 源↔交付字符顺序 |
| 9 | `split_occurs_at_a_source_visual_row_transition` | 源行模型 + 渲染实验 |
| 10 | `same_w_p_rendering_experimentally_tested` | 证据文件（实测） |
| 11 | `experiment_fails_an_independently_frozen_source_geometry_contract` | 冻结 P3 门禁结论 |
| 12 | `the_violated_geometry_contract_predates_the_deviation` | 前驱报告 + 摘要 |
| 13 | `no_permitted_native_inline_construct_satisfies_both` | 证据文件（构件穷举） |
| 14 | `preserving_geometry_requires_no_tolerance_weakening` | 契约 `tolerance_pt = 2.0` |
| 15 | `no_source_geometry_rebaseline_is_performed` | 契约 `rebaselined = false` |
| 16 | `deviation_is_surfaced_explicitly` | 证据 + 构建记录原因 |
| 17 | `a_human_review_item_remains_open` | 证据文件 |

### 6.2 证据文件的受理条件（不得由构建自证）

- 证据必须放在声明过的证据根（`acceptance/evidence/structural_deviations/`），
  schema 前缀为 `structural_deviation_evidence/`；缺失即**不可能**被接受。
- 证据必须声明 `source.break_semantics`、`deviation.kind`、`deviation.state`、
  `generated.representation`、`generated.same_word_paragraph = false`、
  `same_word_paragraph_experiment.outcome = SAME_WORD_PARAGRAPH_UNAVAILABLE`、
  实测失败的几何规则清单，以及**未被重基线化**的前驱契约。
- 前驱契约以 `contract_sha256`（对其规则做规范化摘要）钉住；摘要不匹配即拒收
  （`PREDECESSOR_CONTRACT_DIGEST_MISMATCH`）。
- 接受必须声明其权威来源：`review.state = ACCEPTED_BY_PROJECT_POLICY`、
  `review.authority = PROJECT_POLICY`、`review.accepted_by_automation = false`，
  并记录 `reviewed_by` / `reviewed_at`。**自动化不得自行接受偏差。**
- **禁止** `CASE001` 专属豁免；**禁止**把接受条件绑定到页码、字面文本、规则 id、build id 或 case id；
  生产逻辑与门禁逻辑必须**通用**（测试可用具体夹具）。

### 6.3 权威顺序（何时允许容器身份让步）

> ① 源可见形体几何 ② 冻结 P3 水平契约 ③ 事实正确性 / 阅读顺序
> ④ 源语义结构 ⑤ 生成的 Word 容器身份

容器身份权威**最低**，因此当①②与⑤不可兼得时，让步的是⑤——但让步必须被**公开**（B10/B11/B12），
且**不得**通过削弱 tolerance、重基线化几何或重标注源语义来「变绿」。

---

## 7. LibreOffice 启动契约（基础设施契约 / INFRASTRUCTURE）

### 7.1 已知可用版本

| 项 | 值 |
| --- | --- |
| LibreOffice | **26.2.3.2**（`70e089b17412e4cb7773e41413306b17a2328c34`） |
| 主机命令验证 | `C:\Program Files\LibreOffice\program\soffice.com --version` → `LibreOffice 26.2.3.2 ...`，**exit code 0** |
| 冻结启动器 | `scripts/render_case57.py` |
| 金丝雀证据 | `acceptance/reports/v1_generalization/libreoffice_frozen_launcher_canary.json`（`verdict = PASS`，returncode 0） |

### 7.2 启动器契约条款

| # | 契约 |
| --- | --- |
| L1 | 可执行文件为 `soffice.com`（不是 `soffice.exe`）。 |
| L2 | 参数以 **argv 列表**传递（`argv_is_list = true`），**不经过 shell**（`shell = False`）。 |
| L3 | `capture_output = True`；创建标志 `CREATE_NO_WINDOW`。 |
| L4 | 输入路径与输出目录必须是**绝对路径**（`input_path_absolute`、`output_directory_absolute`）。 |
| L5 | 每轮使用**项目控制的唯一 profile**：`_lo_profile_<uuid>`（`profile_name_has_uuid`、`profile_is_project_controlled`）。 |
| L6 | profile 以 `-env:UserInstallation=file:///<绝对路径>` **有效 file URI** 形式提供。 |
| L7 | **不得**改动 `C:\Program Files\LibreOffice\program\bootstrap.ini`：金丝雀记录的 `bootstrap_ini_sha256_before = 9bc1ffa0360adacad9666d1b9d5be2b09e3f9ff1eb851a05f168393819cbabe0` 与 `_after` 相同，`bootstrap_ini_unchanged = true`。 |
| L8 | **禁止** `HOME` hack、**禁止** `USERPROFILE` hack、**禁止**复用全局/共享 profile。金丝雀记录 `environment_overrides = {}`、`environment_unchanged = true`，运行前后 `URE_BOOTSTRAP` / `UNO_PATH` / `SAL_CONFIGFILE` / `HOME` 均为 null。 |
| L9 | 项目**只应复用这一个**已冻结的启动器，不得同时维护多个独立的 LibreOffice 启动实现。 |

### 7.3 已查明的事实（不得重新发现）

- **LibreOffice 安装本身是健康的**（见 7.1 主机命令 exit 0）。
- 曾出现的 GUI「bootstrap.ini corrupted」症状 **不是**安装损坏；
  后续调查把它归因于**无头启动器 / profile 路径长度敏感性**。
- 项目代码**不得**编辑 `bootstrap.ini`。

### 7.4 复现命令（主机上手工验证用）

```powershell
& "C:\Program Files\LibreOffice\program\soffice.com" --version   # 期望 exit 0 且输出 26.2.3.2
```

---

## 8. 排版与单元格对齐契约

| # | 契约 |
| --- | --- |
| T1 | 段落对齐必须**源驱动**（不得全局套用一个对齐）。 |
| T2 | 首行缩进与正文左边界必须**分离**：首行偏移只影响第一行，续行回到正文左边界。 |
| T3 | **无源证据即不得使用悬挂缩进。** |
| T4 | 同类列表的不同列表项可以有不同的首行缩进；必须逐项按其自身源文本行判定，不得按列表样式整体推断。 |
| T5 | 表格单元格的**水平 / 垂直对齐必须源驱动分类**。 |
| T6 | **不得全局居中首列标签**，也不得全局居中任何单元格类别。 |
| T7 | 源居中单元格的两行折行**不得**被分类为 JUSTIFY；JUSTIFY 分支额外要求**最后一行左对齐**。 |
| T8 | 相对被接受 build 的结构性改动必须最小且可审计（范例：`统一社会信用代码` 单元格 `both` → `center`，changed_cells = 1）。 |
| T9 | 表格数量、列宽、合并、行高、边框必须保持。 |

---

## 9. 状态术语表（GLOSSARY）

后续所有报告必须使用以下措辞，不得混用：

| 术语 | 含义 |
| --- | --- |
| `PASS` | 机器契约已满足 |
| `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` | 全部机器契约已满足**并且**至少存在一条已复核接受的结构性偏差；**不是** `PASS`，因为容器身份未被满足 |
| `FAIL` | 机器契约未满足 |
| `BLOCKED` | 验证因外部/技术阻塞无法继续（**不**用于产品缺陷或未完成的工作） |
| `DOCUMENTED_STRUCTURAL_DEVIATION` | 源语义与生成的容器结构**有意**不同，因为更高权威的冻结源契约无法以其他方式保留 |
| `REVIEWED_ACCEPTED` | 该偏差已按项目政策复核接受（`review.state = ACCEPTED_BY_PROJECT_POLICY`），且仍留有一条未完成的人工复核项 |
| `SOURCE_CONTAINER_MISMATCH` | 生成容器的身份与源语义不一致；**不得**被表述为 `SOURCE_CONTAINER_MATCH` |
| `NOT_YET_CONFIRMED` | 尚未发生的人工确认（既未通过，也未被阻塞） |
| `MANUAL_WORD_REVIEW_REQUIRED` | 机器门禁不足；仍需要桌面 Word 人工检查 |
| `FORM_BLANK_REPRESENTATION_FORCED_BREAK` | 空白发射器的换行根因分类：几何子句为假而「本行已有文字」子句为真，于是发出一条源文不存在的 `w:br`。**是缺陷**，不是偏差。 |
| `P6_SOURCE_ROW_CONTINUITY_CLOSED` | 该缺陷已关闭：同一源表行交付为同一 Word 段落，规则几何不变，`unexpected_w_br_count = 0` |
| `CASE001_FINAL_UNEXPECTED_HARDBREAK_CLOSURE` | 本轮（意外硬换行关闭轮）的总结论标志 |
| `COMPOSITE_EXECUTION_BINDING` | 组合源槽位的语义执行绑定已闭合：整条表面在**原子层面**被证明，不是与单个事实值逐字比较 |
| `ATOMIC_PROVENANCE` | 语义执行校验模式：该表面由记录在案的原子（`FACT_VALUE` / `SOURCE_TEMPLATE_LITERAL` / `SOURCE_FORM_NOT_APPLICABLE_MARKER`）逐元证明 |
| `SINGLE_FACT_STRICT_EQUALITY` | 语义执行校验模式：普通槽位，发出的表面必须**逐字等于**所声明事实的权威值（原契约，未放宽） |
| `FACT_VALUE` / `SOURCE_TEMPLATE_LITERAL` / `SOURCE_FORM_NOT_APPLICABLE_MARKER` | 组合槽位可见成分的原子类别（定义于 `tender_basic/source_fill_policy.py`）。标记**永不**是事实，也**永不**创建事实候选 |
| `V1_PRODUCTION_CANDIDATE` | 全部预期的自动化与人工 V1 验收在全部规范案例上完成 |
| `READY_FOR_SUBMISSION` | **不是**全局编译器状态；只有逐项目的最终商务/法务/商务条件/签字批准才可能允许 |

补充约束：

- 任何局部的 `PASS` 都**不得**改写成 `READY_FOR_SUBMISSION`。
- `PASS` 表示「该检查项通过」，不表示「可提交」。
- `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` **永不**等价于 `PASS`，也**永不**表示 container fidelity 成立。
- `BLOCKED` **只**用于外部/技术阻塞；产品缺陷、未完成工作、不确定性**不是** `BLOCKED`。
- 若某处同时存在「BLOCKED」与「all checks PASS」，这是**状态模型缺陷**，必须消除，不能并存。
- 若某处同时存在 `DOCUMENTED_STRUCTURAL_DEVIATION` 与「无偏差 / container fidelity 成立」，
  同样是状态模型缺陷，必须消除。
- `unexpected_w_br_count` / `unexpected_w_cr_count` 为 0 **不等于**「无结构偏差」：偏差由
  `documented_structural_deviation_count` 与 `generated_paragraph_boundaries` 记账，硬换行由
  `generated_w_br` / `generated_w_cr` 记账，**两组计数器不得互相替代或互相掩饰**。
- 一个已关闭的**缺陷**（如本轮的表单行意外换行）**不得**被登记为
  `DOCUMENTED_STRUCTURAL_DEVIATION`；偏差记的是「Word 原生构件无法表达」，不是「实现写错了」。
- 一个已关闭的**门禁测量缺陷**（如组合槽位的整条字符串比较）同样**不得**被登记为
  `DOCUMENTED_STRUCTURAL_DEVIATION`：`documented_structural_deviation_count` 保持 **1**，
  且历史红结论必须归档保留、不得改写为「一直通过」。

---

## 10. 文档层级与变更纪律

本仓库文档职责划分：

| 文件 | 职责 |
| --- | --- |
| `docs/V1_PROJECT_STATE.md` | **现行状态**（CURRENT TRUTH）、已知偏差、开放任务、过时状态标注 |
| `docs/V1_DECISIONS.md`（本文件） | **冻结决策 / 验收契约**、术语表、变更纪律 |
| `acceptance/reports/v1_generalization/v1_manual_review_checklist.md` | **人工 Word 复核清单**（唯一的 canonical checklist） |
| `PROJECT_GOVERNANCE.md` | 项目治理约束（范围、状态机、门禁、产物分层） |
| `MVP_SCOPE.md` | MVP 输入/字段/非目标基线 |
| `README.md` | 使用与安装入口 |
| `.agents/notes/implemented/<class>/` | 决策笔记（改动行为/契约/流程时必须同步更新） |

变更纪律（同时适用于代码、报告与文档）：

1. 不得覆盖已接受的历史 build；每个新的人工保真 build 获得新的 build id。
2. 保留 manifest 与 hash；不得用截断 hash 记账。
3. 被取代的状态文件必须**显式链接到后继状态**。
4. 不得静默改写历史验收报告。
5. 不得为了让新门禁变绿而重基线化冻结几何。
6. 不得因为实现改变而削弱测试。
7. 必须区分「**测量实现过时**」与「**源契约过时**」——只有后者才需要契约变更流程。
8. 人工阻塞项存在期间不得 commit / push，除非做出明确的 checkpoint 决策。
9. 默认保留用户未提交改动；不执行 `git reset`、不覆盖验收目录、不提交、不推送、不 tag。

---

## 11. 不得重新发现的结论（快速索引）

| 别再重新讨论 | 结论 | 位置 |
| --- | --- | --- |
| 「把两个段落合并成一个 `w:p` 就解决缺陷 B 了」 | 已实验证明：合并使 R3/R4 源位置不可达，违反冻结的 `EXACT_SOURCE_SPAN` | 状态文档 §7.1 |
| 「放宽 R3/R4 容差」 | 禁止（P1/P2） | 本文件 §2.2 |
| 「R3/R4 只校验一端」 | 禁止（P2） | 本文件 §2.2 |
| 「把源的自然折行标注成显式换行」 | 禁止（B9） | 本文件 §6 |
| 「把已复核的结构性偏差写成 PASS」 | 禁止（B10）：族状态为 `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`，`container_fidelity = SOURCE_CONTAINER_MISMATCH` | 本文件 §6 / §6.3 |
| 「构建自己记录了隔离，所以该拆分被授权」 | 禁止（B5/B6）：构建记录是**关于该 build 的证据**，不是裁决 | 本文件 §6 |
| 「把偏差的接受条件写成 CASE001 专属」 | 禁止（§6.2）：证据与条件必须通用，不得绑定页码/字面/规则 id/build id/case id | 本文件 §6.2 |
| 「自动化可以直接接受偏差」 | 禁止（§6.2）：必须 `review.state = ACCEPTED_BY_PROJECT_POLICY`、`accepted_by_automation = false` | 本文件 §6.2 |
| 「让每页自己算页边距」 | 禁止（F1） | 本文件 §4 |
| 「LibreOffice 安装坏了，改 bootstrap.ini」 | 安装健康；症状是无头启动器/profile 路径长度敏感性；不得改 bootstrap.ini | 本文件 §7.3 |
| 「全局居中表格首列」 | 禁止（T6/T7） | 本文件 §8 |
| 「把 CASE001 的 `lot_name` 解析出来」 | `lot_name` 保持 `NOT_FOUND`（D6/D7） | 本文件 §1 |
| 「`V1_AUTOMATED_CANDIDATE` 说明可以提交了」 | 不能；`READY_FOR_SUBMISSION` 恒为 false（D8） | 本文件 §9 |
| 「CASE001 人工 Word 复核已通过」 | 尚未确认（`CASE001_MANUAL_WORD_REVIEW = NOT_YET_CONFIRMED`）；既未通过，也未被阻塞 | 状态文档 §1.2 |
| 「改产品代码绕过 `pytest-of-WPG` 的 ACL 问题」 | 禁止；用全新可写 basetemp | 状态文档 §7.4 |
| 「表单行里出现 `w:br`，把它记成第二个已复核偏差就过去了」 | 禁止（B15）：那是 `BUILDER_FORCED_BREAK` 缺陷；偏差只记「Word 原生构件无法表达」 | 本文件 §6 / 状态文档 §6 第 10 行 |
| 「判据用『本行是否已有文字』就能决定要不要换行」 | 禁止（B13/B14）：那量的是**段落**不是**源表行**；判据必须是空白自身的源起点 `blank_x0 + 1.0 < reach` | 本文件 §6 |
| 「表单行换行判据里带上『委托期限』或 P45-R6 之类的特例」 | 禁止（B16）：不得含语料字面量 / 页号 / 段号 / 规则号 / case 标识 | 本文件 §6 |
| 「`semantic_execution_binding` 红了就把门禁放宽」 | 禁止（B19/B21）：不得放宽、不得设例外。正确处置是判定**测量实现**是否有误——组合槽位只能在**原子层面**被证明；历史红结论归档保留，不改写 | 状态文档 §5.4 / 本文件 §6 B17–B21 |
| 「组合槽位对不上单个事实值，就把它记成新的已复核偏差」 | 禁止（B17）：这是**门禁测量缺陷**，不是交付产物偏差；`documented_structural_deviation_count` 保持 1 | 本文件 §6 B17 / 状态文档 §7.1 |
| 「为组合槽位在门禁里写 `P42-R2` / 页号 / 组合字面量的特例」 | 禁止（B19）：原子校验必须通用，对全部规则与全部案例成立 | 本文件 §6 B19 |
| 「CASE003 重建后哈希变了，所以必须迁移指针」 | ~~不必~~ **已被第 4 轮续作 VII 取代**：当时成立的前提是产物逐字节相同；本轮把多行单元格改为「每个源行一个原生段落」后，CASE002/CASE003 的 DOCX / PDF / generation_report 哈希**确实全部改变**（CASE003 `w:br` 20 → 1，段落 1555 → 1574），因此两条指针**已迁移**到各自的新 build。判据不变：只有产物真正改变才迁移指针 | 状态文档 §5.6 |

---

## 12. 第 4 轮续作 VII 冻结决策（ROUND 4 CONTINUATION VII）

### D20 日期行的**前导**空白是固有几何，不是「没有前一个 token」

`____年` 之前没有标签，但那段空白是源画出来的（封面 69.00 pt）。把「无前置 token」当成「无间隙」，会让该行第一段无人拥有，回退路径只好去数 figure space 字形——形态几何就成了 authority，且行宽构造短于源，`w:jc=center` 于是绕错误的宽度居中。

* 前导区间 = 从空白自身的实测起点（无 span 时退化为行 extent）到第一个 token 的起点；
* 带标签的行里，标签本身是一个 part、也是一个 token，其后的空白仍是**内部**区间，从标签右缘量起；
* 一个水平位移**只有一个拥有者**：绝不出现「段落缩进 + tab + 固有间距」三者叠加表达同一段位移。

### D21 日期段的宽度由**固有间距**表达，figure space 不参与几何

`U+2007` 的个数是渲染结果，不是几何 authority。段宽改由「一个 `U+0020` 文本 + 原生 `w:spacing`（twips，字符跟踪）」表达，宽度因此**内在于 run**，可以在 `w:jc=center` 下存活（绝对 tab 不能，候选 A 已否决）。

### D22 单元格的源行 = 原生段落，一源行一段，各带**自己测得的**行距

源在同一个单元格里画了多行时，那不是「一个带强制换行的段落」：一个 `w:line` 只能复现一个节奏，源按 23.40 / 19.44 pt 两个不同距离排的行必然被压成同一行距（旧表示渲染 17.60 / 17.60）。

* 每源行一个原生段落；`w:br = 0`；无空段落；仍是**一个**可编辑单元格；
* 每段的行距由该行到下一行的**实测** pitch 换算，不共享一个比值；
* 换算用 `MEASURED_NATURAL_LINE_RATIO`（`w:lineRule="auto"` 的 240 分之一单位）并基于**实际交付的字号**——`w:sz` 是半点数且 python-docx **截断**，源 10.45 pt 交付为 10.0 pt，用源字号换算会系统性偏宽。

### D23 门禁的「行分隔」判据必须覆盖 Word 的两种原生写法

`TABLE_CELL_LINE_STRUCTURE` 原先只数 `w:br`。Word 表达「单元格内的换行」有两种**同样原生**的写法：段内 `w:br`，以及单元格内的段落边界。判据改为「单元格携带的原生行分隔数 = 源行数 − 1，且逐行文本与源逐行相等」——合并、丢失、乱序仍然红。这是**测量实现过时**（§10 第 7 条）的修正，不是放宽：源契约（一个单元格、逐行保真）没有变，容差没有变，也没有任何特例。

---

## 13. 格式语义与几何权威补充决策（D24–D31）

> 本节补齐第 4 轮人工保真期间定型、但此前只散落在状态文档与门禁实现里的契约。
> 它们同样是**冻结**的：不得因为实现改变而放宽。

### D24 源语义对齐 ≠ 位置缩进

«一行在源里是不是居中的» 是**语义**，必须由源可测证据判定（稳定中轴 → `SOURCE_ALIGNED_CENTER`；
两侧留白均衡 → 同义；源锚定表单行 → `SOURCE_ANCHORED_FORM_ROW`；无证据 → 不判定）。**位置缩进**只是
表达手段，只能在源本身就带缩进时有值。

* 禁止用「左对齐 + 大左缩进」伪造居中，也禁止反向把源缩进当噪声清零；
* 不得全局居中或全局归零（T6/T7）；
* 无法归类时必须留 `ambiguous`，不得猜。

### D25 日期里的视觉间隙是**格式语义**，不是文本

`年    月    日` 之间的空白是**排版格式**（可编辑、宽度可测），不是"多打了几个空格"。
因此：

* 不得用空格/glyph 个数表达几何；
* 不得把间隙压平（`collapsed`）；
* 不得把源没有的间隙"发明"出来（`invented_gaps`）；
* 间隙的**宽度**必须可测量、可复算，并与源在同一容差内（日期几何 2.0 pt）。

### D26 固有间距标定契约（INTRINSIC SPACER）

日期/表单段的宽度由**固有间距**表达：一个 `U+0020` 文本 run + 原生 `w:spacing`（字符跟踪，twips）。
宽度因此**内在于 run**，可以在 `w:jc=center` 下存活（绝对 tab 在居中段落里不能，候选 A 已否决）。

已冻结的实测常数（`tender_basic/intrinsic_spacer.py`）：

| 常数 | 值 | 含义 |
| --- | --- | --- |
| `MEASURED_SPACE_ADVANCE_EM` | `0.500` | 空格前进量（em）；此前误用 0.535 em |
| `TRACKING_RESPONSE_RATIO` | `1.0` | 跟踪 1:1 反映到渲染宽度 |
| `NEGATIVE_TRACKING_ROUNDS` | `False` | 负跟踪不做取整（实测渲染器不应用 condensed tracking） |
| `rendered = base_advance + max(0, tracking)` | — | 唯一的宽度公式 |
| `MIN_INTRINSIC_WIDTH_FACTOR` | 见实现 | 低于可表示下限时不得宣称"已表达" |

标定必须用**标记夹逼**在 1/2/3 段与多字号上验证，而不是单点外推。**figure space 的个数永远不是
几何 authority**（D21）。

### D27 `SOURCE_CENTER_ALIGNMENT_FRAME`（居中轴冻结）

生成帧的几何中心与 Word 的**有效**居中轴不是同一个值。冻结模型：

* raw frame centre `297.650 pt`；effective Word centre axis `297.766 pt`；`delta = +0.116 pt`；
* inset 响应 `0.4996`；
* 位移公式 **`L − R = 2 × delta`**（`delta > 0` 调 `L`，`delta < 0` 调 `R`，两者都不动当 `|delta| < 0.5 pt`）；
* 分类阈值：`max(8.0 pt, 页面宽度 × 2%)`（当前 = 11.906 pt）。

不得重新"发现"这套行为，也不得改成全局居中。

### D28 单一水平拥有者（ONE OWNER PER DISPLACEMENT）

同一段水平位移**只能有一个表达者**。禁止「段落缩进 + tab + 固有间距」三者同时表达同一段位移。
出现两处表达时，正确处置是判定哪一处是源的 owner 并删除另一处，不是把两处都留下再"补偿"。

### D29 部分源规则 + 残余纯间隙分解

源在一条视觉行上可能只画了**部分**规则线（有段落、无规则）。此时不得：

* 把整行当成一条规则拉伸（stretch）；也不得
* 虚构源不存在的规则。

正确分解：**有规则的段**按端点对齐（端点残差 ≤ 容差），**残余**按测得的纯间隙宽度表达。
这类行的合法性由"代表行"程序判定（`LEGAL_REPRESENTATIVE_DATE_ROW`）。

> 端点配对前必须**并合同线共线的规则矩形**：渲染器把一条下划线画成两个叠放矩形
> （整段 + 短内段），逐矩形一对一配对会得出"虚构规则"的假红。

### D30 渲染几何才是验收证据

验收测量对象是**渲染后的 PDF 几何**（pymupdf 读出的字形与线条位置）。OOXML 属性（`w:jc`、`w:ind`、
`w:spacing`）只是**表示**，不是结论：

* 门禁不得只读 OOXML 属性就宣称保真；
* 也不得反过来只信渲染而忽略 OOXML 语义（两者都要，且必须能对上）；
* 因此"固有间距 1265 twips"必须与"渲染 69.00 pt"同时成立，才叫表达成功。

### D31 全机器通过 ≠ 可以提交（重申 D8）

三案例机器门禁全绿、全量测试 0 失败，**都不**使 `READY_FOR_SUBMISSION` 变为 true。
人工 Word 复核、人工 Excel 复核、以及商务/法务/报价/签字盖章批准都在自动化之外；
自动化只能报告"机器已闭环、等待人工确认"。

## 14. 复核工作簿决策（D32–D40，REVIEW WORKBOOK）

复核工作簿轮次只改 `投标项目复核表.xlsx`：它是**人工复核界面**，不是 Word
渲染管线的输入，也不改变任何事实语义。

### D32 工作簿是复核视图，不是第二事实库

`投标项目复核表.xlsx` 的机器列只做投影：事实值/状态来自 `ProjectFacts`，结构与
价格单元格来自规范化源文件，定位来自 `ReviewEvidence`，检查结论来自 QA 报告。
工作簿不解析、不推断、不换算、不合并任何事实，也不写回 `ProjectFacts`。

### D33 人工列与机器列物理分离

每个复核视图都有显式的机器列区与人工列区；人工列标题以「人工」开头，初始值一律为
`未复核`，并绑定五选项下拉（未复核/通过/有疑问/需修改/不适用），机器列不得出现这些
人工结论词。人工结论列**不得**被任何公式引用（仅 `00_复核总览` 允许对其做 COUNTIF /
COUNTA 汇总，用于显示复核进度）。

### D34 `NOT_FOUND` 必须在工作簿中显式显示

`NOT_FOUND` 事实的机器抽取值单元格显示字面量 `NOT_FOUND`，且不显示候选值、不显示
证据摘要；`NEEDS_REVIEW` 事实保留候选值，并在 `06_冲突与缺失` 中作为待人工裁决项
列出。工作簿中的 `/` 仍是 `SOURCE_FORM_NOT_APPLICABLE_MARKER`，不是事实值。

### D35 预算与最高限价是两个独立概念

`04_报价与限价` 中 `budget` 与 `max_price` 各自成行，绝不合并、不相减、不互为默认。
源文件只给出其一（或没有给出）时，另一行按其真实状态显示。

### D36 价格行逐行照抄源表格，不计算

`04_报价与限价` 的单价/小计/数量一律来自源表格单元格文本；该视图内**没有公式**。
表格识别是结构性的（表头同时含序号列、名称列与价格列），跨页续表沿用上一页表头
（CASE002 的 32 行分项限价正因此完整保留）；源文件只有空白报价表单时，报告为
「源空白报价表单（待供应商填写）」而不是编造行或静默丢弃。

### D37 ★ 只标记否决项

`03_资格否决与强制项` 收录强制项、否决项与高风险条款；`★` 与「否决性＝是」只用于
`REJECTION` 或 `一票否决` 行，两者集合必须相等。

### D38 要求正文、复核动作、核验标准分列

工作簿不得再把三段文本拼成一个单元格：`03` 视图把它们放在三列，便于逐项核对与
按列筛选。

### D39 后继构建：Word 产物原样复制，不重新渲染

工作簿轮次不重跑 Word。`scripts/v1_build_review_workbook.py` 从已验收构建复制
DOCX/PDF/generation_report（逐字节相同），只重建工作簿与工作簿报告，并在
后继 `build_manifest.json` 中记录 `status=REVIEW_WORKBOOK_SUCCESSOR`、
`word_render_repeated=false` 与三者的来源/后继哈希。指针 `*_current_build.json`
只描述 Word 构建，因此**不迁移**：它继续指向 closure8。

### D40 机器列对齐由门禁证明，不靠人工看

`scripts/v1_review_workbook_gate.py` 的 37 项检查把工作簿与权威对象逐行比对
（事实行、状态词表、定位、强制项、价格行、结构行、证据索引、冲突项），并证明
人工列未被引用；`scripts/v1_review_workbook_visual_qa.py` 用 LibreOffice 渲染 PDF
并把工作簿转成"重算副本"，用重算值核对总览公式。两者均须 PASS；渲染中剩余的
换行截断以 `clipping_bounded = WARN` 如实报告，不隐藏、不豁免。

## 15. 复核要点合成决策（D41–D49，REVIEW POINT SYNTHESIS）

### D41 复核行是"合成的人工复核要点"，不是原始要求拼接（长期规则）

**长期规则：复核工作簿的每一行都是合成出来的人工复核要点，不是原始要求的拼接。**
一轮生成不得把源条款文本＋模板句子直接拼进单元格；每一行必须回答：招标文件要求
什么（SOURCE REQUIREMENT）、复核人检查什么（REVIEW POINT）、什么样的可观察状态算
通过（PASS CRITERIA）、不满足会有什么后果（FAILURE CONSEQUENCE / RISK，且只在源条款
写明时才写）、评审如何计分（SCORING，且只在源条款写明时才写）、复核前要准备什么
（PREPARATION）。这四类语义在数据模型与渲染中保持独立字段，不得互相覆盖。
引擎为 `tender_basic/review_point.py`，唯一语义对象为 `ReviewPoint`。

### D42 数字必须有语义归属，否则不得进入复核文本

每个数字按上下文赋予一个语义角色（保证金金额/有效期天数/工期天数/质保月数/服务
响应天数/价格/分值/付款比例/人数/数量），只有与该行 `requirement_type` 兼容的角色
才允许出现在复核要点与通过标准中；联系电话、标书费/平台服务费与其他无归属数字
（`NEVER_USABLE_ROLES`）永不进入复核文本。数字只在其**所属源条款文本**中出现才算有
出处，页号/条款号（`第 N 页`、`9.2` 等定位符）不是要求值，既不计数也不渲染。

### D43 非行动项被过滤，但不得削弱覆盖

采购方内部程序（评审小组人数/组成/回避/纪律等，且该组无任何投标人义务、无强制项、
无高风险）不构成投标复核要点，按组过滤并记录被过滤主题与数量；纯费用条款（如
平台服务费）同理。任何强制项或高风险条款所在的行永不因可行动性过滤而消失。

### D44 后果不得编造

`failure_consequence` 只在源条款出现明确后果标记（否决投标/废标/无效投标/不予受理/
不予评审/不得分/扣分/取消投标资格/需要澄清/拒收）时生成，并记录来源条款 id
（`consequence_evidence_id`）；没有标记就没有后果文本，也不用"可能影响评审"之类的
占位句填充。

### D45 样板文字被消除，不是被改写

"按上述招标文件条款逐项核对响应文件对应内容，确认完全响应。"之类模板句必须从合成
行中消失：要求摘要优先选取**具体**条款（含具体值、非样板句）作为引文；引文是源条款
原文，可包含模板措辞，但合成行不得包含模板句。

### D46 交付表与结构化视图共享同一语义对象

`投标项目复核表` 的 D 列（招标文件要求/复核要点/通过标准/…）与 `02_关键条款`、
`03_资格否决与强制项` 的正文、复核动作、核验标准必须由**同一个** `ReviewPoint`
渲染而来；门禁逐行比对 D 列与 `render_review_cell(review_point)`，不允许两处各写一套。

### D47 第 2 轮可刷新交付表动态行，模板与人工列不动

`augment_review_workbook(..., refresh_legacy_rows=True)` 只重算交付表的动态复核行
（模板表头、合并、列宽、签章块、人工列与下拉保持原样）；门禁以
`--legacy-text-refresh` 分区比对：表头逐格相同、动态区行数等于本轮计划行数、
动态区之后（含签章块）在去掉行位移后逐格相同、D 列等于 `render_review_cell`。

### D48 两份历史手填工作簿仅作写作与复核流程参考

仓库内 `acceptance/manual_delivery_round54|55|56/case_00{1,2,3}/投标项目复核表.xlsx`
是人工填写风格的参考样本，**只作风格与复核流程参考**，不是 CASE001/002/003 的事实
来源，也不得覆盖当前模板；其人工结论词（如"已核对"）、责任人姓名与状态值一律不得
复制进生成的工作簿。

### D49 第 2 轮证据与冻结事实

三案例第 2 轮后继构建的门禁 40/40 PASS；内容质量报告 7/7 已知坏例 PASS、8 组
BEFORE→AFTER；已知坏例（48小时/69152076、0元、平台服务费300元、评审小组成员人数、
混行数字、CONTRACT 无关后果、无归属值）全部由通用规则关闭，未使用案例专用分支。
渲染 QA 的 `clipping_bounded` WARN 为 CASE001 10（第 1 轮 8，结构化视图 E/F 列多出 2
格）、CASE002 17（18）、CASE003 26（26）；该 WARN 不是失败项，也不构成提交就绪。

### D50 复核关注点归属：PROVENANCE IS NECESSARY BUT NOT SUFFICIENT

第 3 轮引入 `SourceRequirementAtom -> ReviewConcern -> ReviewPoint` 归属链。来源可追溯
不再足以让一个数字、材料或后果出现在某一行：每个渲染组件必须**同时**是源文件可回溯的、
**且**由同一个 `ReviewConcern` 拥有。引擎新增 `tender_basic/review_concern.py`
（原子化、关注点分类注册表、归属违规检查器），`ReviewPoint` 增加 `concern_id` /
`concern_label` / `concern_question` / `owned_atom_ids` / `owned_clause_ids`，
`dynamic_review.build_dynamic_review_plan` 改为按关注点合成行（一个关注点 = 一行 = 一个人工问题）。

### D51 源条款按语义切分，而非按标点切分

源文件常把同一段商务条款拆到不同 unit（例如 `剩余 5%` 与 `作为质保金，质保期 12 个月，
质保期满后无息付清余款`）。因此保留金条款的**金额面**在**节（section）级**派生一个额外原子：
当同一节同时出现保留期、质保金/尾款/余款措辞与百分比时，从原文中截取**逐字片段**生成
`RETENTION_MONEY_RATIO` 原子。派生原子不含新增数字、不引入案例分支。

### D52 同一中文关键词不等于同一语义概念

CASE001 的 `项目质保期 24 个月`（PROJECT_WARRANTY，WARRANTY_MONTHS）、
`剩余 5% 作为质保金`（RETENTION_MONEY_RATIO，PAYMENT_RATIO）、
`质保期 12 个月…质保期满后无息付清余款`（RETENTION_RELEASE_PERIOD，WARRANTY_MONTHS）
是三个不同关注点，**不得**被报告为源文件冲突。`FALSE_CONFLICT_COUNT = 0`；
冲突判定要求"同一关注点 + 同一角色 + 同一权限范围 + 值不等"，朴素关键词匹配会报出的
假冲突由该规则显式计数为 `naive_keyword_conflicts_avoided`，不进入工作簿。

### D53 可执行性：内部程序与定义条款不作为投标人义务行

非投标人面向的关注点（`INTERNAL_PROCEDURE`、`TERM_DEFINITION`）默认被过滤；仅当其中
含强制/高风险条款（否则丢失覆盖）时保留，且该行必须以
`〔采购人内部程序/定义条款，仅备查，无需投标响应〕` 标记，并配"无需投标人响应"的复核要点，
使人工不会误把它当成需要响应的废标项。

### D54 第 3 轮证据与冻结事实

三案例第 3 轮后继构建门禁 40/40 PASS、内容质量报告 PASS（14/14 A–N 已知坏例、
20/20 人工风格审计、≥15 组 BEFORE→AFTER、`FALSE_CONFLICT_COUNT = 0`）、结构渲染 QA PASS
（`clipping_bounded` WARN 为 CASE001 8（第 2 轮 10）、CASE002 10（17）、CASE003 26（26），
均不劣于基线）。全套测试 716 收集 / 715 passed / 1 skipped / **0 failed / 0 errors**。
Word 产物在各后继目录中逐字节一致（`word_render_repeated=false`）。CASE002 `budget` 仍为
NOT_FOUND、`max_price 7507785.65` 仍 RESOLVED，分项报价行 36 = 源文件 36 行；CASE003
`lot_name 三标段` 仍 RESOLVED。人工确认状态保持未勾选：`CASE00{1,2,3}_XLSX_MANUAL_REVIEW`
均为 `NOT_YET_CONFIRMED`，`V1_PRODUCTION_CANDIDATE=false`、`READY_FOR_SUBMISSION=false`，
未创建任何 tag 或 release。

### D55 参考工作簿的两个类别：仓库历史手填件与用户私有参考件

D48 记录的是**类别 A**（仓库内历史手填工作簿）的定位，其含义不改写。为避免两类参考件
被混为一谈，补充记录**类别 B**：

| 类别 | 位置 | 是否纳入版本控制 | 允许用途 |
| --- | --- | --- | --- |
| **A. 仓库历史手填工作簿** | `acceptance/manual_delivery_round54|55|56/case_00{1,2,3}/投标项目复核表.xlsx`（D48） | 是（历史可见） | `STYLE_ONLY` + `HUMAN_WORKFLOW_REFERENCE_ONLY` |
| **B. 用户私有参考工作簿** | `acceptance/private/reference_review_workbooks/` | **否 —— 被 `.gitignore` 忽略，永不提交** | `STYLE_ONLY` + `HUMAN_WORKFLOW_REFERENCE_ONLY` |

两类参考件的共同约束：

- **既不是** `ProjectFacts` 权威，**也不是** `ReviewEvidence` 权威，**更不是**当前案例的事实证据；
  只能用于写作风格与人工复核流程参考。
- 不得复制其事实、数值、结论状态（如"已核对"）、责任人姓名或任何状态值进入生成的工作簿、
  `ProjectFacts` 或验收产物。
- 类别 B 位于 `acceptance/private/`，被 `.gitignore` 覆盖：**必须保持 ignore / untracked**，
  不得提交、不得引用其内容作为证据，只能引用"存在且仅作风格参考"这一事实。
- 生成的工作簿只以当前案例的源文件与 `ProjectFacts` 为依据；参考件的存在不改变任何门禁结论。

### D56 渲染层归属：SEMANTIC OWNERSHIP MUST SURVIVE RENDERING

第 3 轮把归属放进模型对象，**不足**：人工复核第 3 轮工作簿时判 `FAIL`
（`FAIL_REASON = RENDERED_COMPONENT_CONCERN_OWNERSHIP`）——模型里每行都有归属，但**渲染出来的
Excel 单元格文本**仍可能沿用过期/过宽来源组或旧主题模板的措辞。第 4 轮因此把不变量提升到渲染层：

> **每一个渲染进 XLSX 的实质短语，都必须有"关注点自有"的出处。**

落地机制（通用规则，无案例分支）：

- `tender_basic/review_rendering.py` 新增 `RenderedReviewComponent`：九类组件
  （SOURCE_REQUIREMENT / REVIEW_CHECK / PASS_CRITERION / FAILURE_CONSEQUENCE /
  PREPARATION_MATERIAL / SCORING_GUIDANCE / NUMERIC_STATEMENT / EVIDENCE_SUMMARY /
  LINKED_FACT），每个组件携带 `concern_id`、来源原子 id、数值/材料/证据 id 与
  `ownership_verified`。
- 交付表 D 列文本不再由模板拼接，而是由**已校验组件投影**生成
  （`dynamic_review.cell_from_components`）；`review_rendering.verify_component` 逐类校验，
  `foreign_terms` 判定"渲染文本点名了关注点不具备的概念"。
- 句级仲裁：同一句若被更长的决定性模式命中，则归属该处（旧组/宽泛主题不能"顺带"渲染该句）；
  数值措辞用源文件自己的术语（`_source_term` / `value_sentence`），避免质保金↔尾款、
  供货期↔交货期等外来同义词。
- 输出门禁读取**最终** xlsx 单元格（不是模型对象）复核：`scripts/v1_review_workbook_round4_report.py`
  校验 `rendered_cell_equals_component_projection`、八类 `RENDERED_*_CONCERN_MISMATCH = 0`、
  `final_cell_text_owned_by_concern`、`every_rendered_component_present_in_final_cell`、
  `stale_linked_facts_absent`、以及 30 格最终单元格审计（记录地址与显示文本）；
  出处映射持久化为 `review_workbook_round4_rendered_component_provenance_case_00{1,2,3}.json`。

人工复核结论**不得**由自动化改写：第 3 轮人工 `FAIL` 保留在
`case001_review_workbook_round4_human_review.json` 中，自动化只能把状态推进到
`CASE001_XLSX_MANUAL_REVIEW = AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`，不勾选任何人工框。

### D57 第 4 轮证据与冻结事实

三案例第 4 轮后继构建报告 PASS（CASE001 25/25、CASE002 23/23、CASE003 23/23），
八类 `RENDERED_*_CONCERN_MISMATCH = 0`，A–S 人工坏例 19/19 PASS，CASE001 最终单元格审计
全格一致（CASE001 138/138、CASE002 138/138、CASE003 147/147 单元格一致，抽样 30 格记录地址与
显示文本），结构门禁复用第 3 轮 40 项在三案例第 4 轮工作簿上各 40/40 PASS，渲染 QA PASS
（`clipping_bounded` WARN 为 CASE001 8、CASE002 10、CASE003 25，均不劣于基线）。
Word 产物在各后继目录中逐字节一致（`word_render_repeated=false`，第 1–4 轮**从未**重新渲染 Word）。
CASE002 `budget` 仍为 NOT_FOUND、`max_price 7507785.65` 仍 RESOLVED，分项报价行 36 = 源文件 36 行；
CASE003 `lot_name 三标段` 仍 RESOLVED、分项报价 0 行 + 空白表单 4 项。CASE001 的
`PROJECT_WARRANTY = 24个月`、`RETENTION_MONEY_RATIO = 5%`、`RETENTION_RELEASE_PERIOD = 12个月`
在渲染文本中保持三个不同关注点：12 个月**不**被写成项目质保期、5% **不**被写成评分/付款比例，
`FALSE_CONFLICT_COUNT = 0`。人工确认状态：`CASE001_XLSX_MANUAL_REVIEW =
AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`（人工第 3 轮判 FAIL）、CASE002/003 仍为
`NOT_YET_CONFIRMED`，`V1_PRODUCTION_CANDIDATE=false`、`READY_FOR_SUBMISSION=false`，
未创建任何 tag 或 release。

### D58 语义校验：PROVENANCE CONSISTENCY IS NOT SEMANTIC VALIDATION

第 4 轮把不变量提升到渲染层（D56），机器门禁全绿（25/25、八类 mismatch 0、A–S 19/19），
但人工复核**第 4 轮工作簿**仍判 `FAIL`，`FAIL_REASON = CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED`：
一行文本可以**完全可溯源**却仍然是错的——质量要求里带着交货地点、把 95% 写成质保金比例、
履约保证金引用响应保证金条款、断言"报价无漏项"、付款行吸收代理服务费。
**出处一致（provenance-consistent）不等于语义正确（semantically-correct）**，且
**任何关注点都不得只用自己的生成元数据自证**。

第 5 轮因此引入**独立的关注点契约** `tender_basic/concern_contract.py`：

> **每一个关注点都有一份人工手写的语义契约；契约校验的是"渲染出来的那一行"，而不是生成它的对象。**

- `ConcernContract` 逐关注点声明：允许的行为主体（actors）、权威范围（authority scopes）、
  必需/禁止的**词法来源签名**（required/forbidden lexical-source signatures）、允许/禁止的
  **数值角色**、允许关联的**事实键**、允许的材料类别、允许的后果类别、评分角色、必需的证据属性、
  以及 kind（MANDATORY / REJECTION / SCORING / CONTRACT_ONLY / INFORMATIONAL）。
- **契约不得由被校验的 ReviewPoint 派生**：`CONTRACT_SOURCE = human_round5_fixtures_A_T`
  （来自人工坏例 A–T），`concern_contract.py` **不导入** `review_point` / `review_concern`，
  由 `contract_table_is_independent()` 与单元测试共同断言。
- `validate_point(...)` 校验**最终单元格文本**（要求正文、复核要点、通过标准、准备材料、不满足后果、
  评分提示、数值角色、关联事实、证据），违规码包括
  `CONTRACT_FORBIDDEN_SIGNATURE` / `CONTRACT_MISSING_REQUIRED_SIGNATURE` / `CONTRACT_FORBIDDEN_ROLE` /
  `CONTRACT_ROLE_NOT_ALLOWED` / `CONTRACT_FACT_NOT_ALLOWED` / `CONTRACT_CONSEQUENCE_NOT_ALLOWED` /
  `CONTRACT_MATERIAL_NOT_ALLOWED` / `CONTRACT_EVIDENCE_SIGNATURE_MISSING` / `CONTRACT_EVIDENCE_FORBIDDEN`。
- 分段读取：`segment_text` / `owned_segments` 只保留契约自有的**片段**
  （禁止签名优先于必需签名），所以一行不会"顺带"继承邻近关注点的措辞。
- 片段而非要求：`is_incomplete_fragment` 把抽取残片
  （如"意见》的通知中规定的收费标准的 70%向成交供应商"）路由到 **NEEDS_REVIEW**，
  既不出现在交付行里，也不被静默丢弃（`needs_review_topics` / `needs_review_clause_ids`）。
- 冻结视图同样受语义校验（**与旧表相等 ≠ 正确**）：`02_关键条款` 与
  `03_资格否决与强制项` 的**每一行**都从最终单元格读出，用其产出关注点的契约重新校验
  （CASE001 60 行、CASE002 53 行、CASE003 56 行，0 违规），且每一行都必须绑定到已交付关注点
  （视图不得凭空造行）；`06_冲突与缺失` 与 **ProjectFacts SSOT** 双向比对
  （SSOT 已 RESOLVED 的事实不得出现在冲突表、SSOT 未解决的事实不得在冲突表里缺失）。

### D59 五个角色必须分开（BANK the five roles）

第 5 轮把业务含义已知的数字固定到最小充分角色集，并禁止再用 `PERCENTAGE` / `PRICE` / `MONTHS` /
`QUANTITY` 之类的宽泛角色覆盖已知业务含义：

| 角色（canonical） | CASE001 值 | 语义 |
| --- | --- | --- |
| `PAYMENT_RATIO` | 95% | 付款比例 |
| `RETENTION_MONEY_RATIO` | 5% | 质保金（留存款）比例 |
| `RETENTION_RELEASE_MONTHS` | 12 个月 | 质保金释放期（**不是**项目质保期） |
| `PROJECT_WARRANTY_MONTHS` | 24 个月 | 项目/产品质保期 |
| `BANK_ACCEPTANCE_RATIO` | 100% / 50% | 接受银行承兑汇票比例（计分因素自有） |

同时拆分：`SCORE_POINTS`（"得 12 分"/"（12 分）"只属于该评分因素）、`BID_VALIDITY_DAYS`（90 日历天）、
`RESPONSE_BOND` / `PERFORMANCE_BOND` / `BOND_AMOUNT` / `BOND_FORM`。
历史角色名通过 `semantic_roles.canonical_role()` 单点翻译（`VALIDITY_DAYS`→`BID_VALIDITY_DAYS`、
`WARRANTY_MONTHS`→`PROJECT_WARRANTY_MONTHS`、`RETENTION_RELEASE_PERIOD`→`RETENTION_RELEASE_MONTHS`、
`SCORE`→`SCORE_POINTS`、`TENDER_FEE`→`TENDER_DOCUMENT_PRICE`、`CONTACT`→`CONTACT_INFO`…），
调用方可以保留历史词汇，**写出的角色永远是 canonical**。

### D60 第 5 轮证据与冻结事实

- 三案例第 5 轮工作簿 `..._review_workbook5`：CASE001 16/16 检查、A–T 坏例 **20/20 PASS**、
  **49/49** 交付行通过契约审计；CASE002 15/15（45/45 行）；CASE003 15/15（48/48 行）。
- 第 4 轮溯源门禁在**同一批第 5 轮工作簿**上复跑：CASE001 25/25、CASE002 23/23、CASE003 23/23，
  `rendered_mismatch_total = 0`，A–S 19/19。
- §SUCCESS 全绿：`QUALITY_LOCATION_CONTAMINATION = 0`、`VALIDITY_BLACKLIST_CONTAMINATION = 0`、
  `CONTRACT_PAYMENT_FOREIGN_CLAUSE = 0`、`PERFORMANCE_BOND_RESPONSE_BOND_EVIDENCE = 0`、
  `UNSUPPORTED_PRICE_COMPLETENESS_ASSERTIONS = 0`、`PRICE_ACCEPTANCE_MIXED_CONCERNS = 0`、
  `TECHNICAL_ACCEPTANCE_MIXED_CONCERNS = 0`、`PAYMENT_RATIO_95_AS_RETENTION = false`、
  `FALSE_PLATFORM_CONFLICTS = 0`、`CASE001_FINAL_WORKBOOK_AUDIT = ALL/ALL coherent`、
  `THREE_CASE_GENERALIZATION = PASS`、`WORD_ARTIFACTS_UNCHANGED = PASS`。
- 第 4 轮工作簿**未被覆盖**，Word **未被重新渲染**；人工第 4 轮 `FAIL`
  （`CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED`）保留在
  `case001_review_workbook_round4_human_review_CONCERN_CONTRACT_NOT_INDEPENDENTLY_VALIDATED.json`，
  自动化只能把状态推进到 `CASE001_XLSX_MANUAL_REVIEW = AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`。
- `V1_PRODUCTION_CANDIDATE = false`、`READY_FOR_SUBMISSION = false`，未创建 tag 或 release。
