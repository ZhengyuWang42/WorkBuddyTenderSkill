# V1 项目状态（CURRENT TRUTH）

本文件是 WBTenderSkill / `tender-basic` V1 的**现行状态权威文档**。
它只记录当前真实状态；冻结决策见 [V1_DECISIONS.md](V1_DECISIONS.md)。

阅读顺序与优先级：

1. **CURRENT TRUTH** — 本文件第 1–5 节，只写当前可验证的事实。
2. **FROZEN DECISIONS** — [V1_DECISIONS.md](V1_DECISIONS.md)，已冻结、不得因新门禁变绿而放宽的契约。
3. **HISTORICAL / SUPERSEDED** — 本文件第 6 节历史缺陷表 + 各历史报告自身；历史报告中的局部 `PASS` 不改变现行契约。
4. **KNOWN DEVIATIONS** — 本文件第 7 节。
5. **OPEN TASKS** — 本文件第 8 节。

事实来源优先级（事实冲突时按此裁决）：
**① 当前生成产物 / manifest → ② 当前状态 JSON / 验收报告 → ③ 当前生产代码与测试 → ④ 已冻结的项目决策 → ⑤ 历史报告 → ⑥ 对话记录**。
本文件中每一个 hash、测试计数、指针与门禁结论都来自仓库内产物；不采用对话中的截断值。
若历史状态文件声称的状态与当前产物不一致，本文件显式标注 **SUPERSEDED / STALE**，不做静默调和。

---

## 0. 恢复指南（RECOVERY MAP）—— 新 agent 从这里开始

本文件是**自足**的：只读本文件 + [V1_DECISIONS.md](V1_DECISIONS.md) +
`acceptance/reports/v1_generalization/` 下的现行报告，即可恢复项目，无需任何对话记录。

| # | 主题 | 本章节 | 权威产物 |
| --- | --- | --- | --- |
| 1 | **产品定义**（输入 / 输出 / V1 排除项） | §2 | `tender_basic/`、`README.md` |
| 2 | **核心权威模型**（SourceFormat / ProjectFacts / ReviewEvidence 边界） | §3 | `V1_DECISIONS.md` §1 |
| 3 | **三个标准案例**（CASE001/002/003 的特性与存在理由） | §4 | `acceptance/private/`（不入库）、各 case 的 `*_current_build.json` |
| 4 | **冻结的 CASE001 P3 契约**（R1–R8、2.0 pt、REFLOW_AWARE_V1、已复核段落偏差） | §5.4 / §5.6.4、`V1_DECISIONS.md` §2–§3 | `case001_p3_semantic_registry_gate_final.json` |
| 5 | **Word 原生约束**（可编辑、无图形/文本框/覆盖层、无下划线画线 hack、无危险 OOXML） | `V1_DECISIONS.md` §5 | `tender_basic/word_safe_*.py` |
| 6 | **LibreOffice 启动契约**（冻结启动器、短 profile、bootstrap.ini 归属） | §7.2 / §7.3、`V1_DECISIONS.md` §7 | `scripts/render_case57.py` |
| 7 | **Windows pytest 环境问题**（根因与规避；不得误判为产品失败） | §7.4 | `scripts/dev/pytest_fscompat.py`、`scripts/run_full_tests_windows.py` |
| 8 | **缺陷与解决总账**（按类别归并，含症状/根因/通用解法/状态/证据） | **§5.7** | 各 `case001_*` 报告 |
| 9 | **当前 closure8 状态**（哈希、10/10、9/9、P9 残差、P3 8/8、硬换行、三案例、全量测试） | §5.6 | `case001_manual_word_review_final_status.json` |
| 10 | **当前人工状态**（Word / XLSX 人工复核、候选与提交标志） | §1.2 | 同上 |
| 11 | **当前进展**（Word 自动化、复核工作簿、发布就绪度） | **§12.1** | — |
| 12 | **下一步任务**（有序） | **§12.2** | — |

> 三条最容易被误读的结论，先行声明：
> **① 机器全绿 ≠ 可以提交**（`READY_FOR_SUBMISSION` 恒为 `false`，见 §1.2）。
> **② CASE001 Word 人工复核尚未确认**（`NOT_YET_CONFIRMED`，不是"通过"，也不是"被阻塞"）。
> **③ 复核工作簿是"复核视图"，不是第二个事实库**（见 `V1_DECISIONS.md` §13）。

---

## 1. 基线与当前状态（CURRENT TRUTH）

### 1.1 仓库基线

| 项 | 值 |
| --- | --- |
| 基线提交（baseline checkpoint commit） | `8de9e1f343a6643e11ea5c6c8e1df015dda123a5` |
| 分支 | `main` |
| 基线性质 | **pre-manual-review automated candidate checkpoint**（人工复核前的自动化候选检查点） |
| 该检查点之后的第 4 轮人工保真修复 | 见 §5.6（`v1_manual_fidelity_round4_date_rhythm_closure8`） |
| 下一步检查点 | **PRE_XLSX_CHECKPOINT = PASS**（第 4 轮 closure8 归档；见 §12.1）——**不是**发布、**不是** tag、**不是** production candidate |
| 检查点提交（PRE_XLSX_CHECKPOINT） | commit `fef72d9281042357e8f0f6d8d44e000aedda60aa`（`checkpoint: archive round4 closure8 before review workbook phase`），分支 `main`；远端 `refs/heads/main` 与该 SHA **一致**（已推送）；`git tag -l` 为空；未创建 release |
| 本轮代码改动范围 | 生产侧：`tender_basic/word_safe_source_builder.py`（日期前导/内部区间、固有间距、单元格逐源行段落）、`tender_basic/intrinsic_spacer.py`（新建）、`tender_basic/source_vertical_rhythm.py`（测得自然行比值 + 半点截断）、日期行/单元格节奏相关辅助；仪表侧：`scripts/v1_date_row_closure_audit.py`、`scripts/v1_date_segment_chain_ledger.py`、`scripts/v1_intrinsic_spacer_multisegment_probe.py`、`scripts/v1_table_cell_line_rhythm_audit.py` 等；测试侧：`tests/test_round4_vii_leading_blank_and_cell_rhythm.py`（28 项）。**`ProjectFacts` 语义未改动。** |

### 1.2 全局状态标志

| 标志 | 值 | 依据 |
| --- | --- | --- |
| `V1_AUTOMATED_CANDIDATE` | true | `acceptance/reports/v1_generalization/v1_automated_candidate_gate.json` |
| `MANUAL_WORD_REVIEW_REQUIRED` | true | `case001_manual_word_review_final_status.json::manual_word_review_required` |
| `V1_PRODUCTION_CANDIDATE` | **false** | `case001_manual_word_review_final_status.json::v1_production_candidate`；三个 case 的人工复核均未确认 |
| `READY_FOR_SUBMISSION` | **false** | 同上（`ready_for_submission = false`）；**任何自动化结论都不得置为 true**（D8） |
| `CASE001_MANUAL_WORD_REVIEW` | **NOT_YET_CONFIRMED** | `case001_manual_word_review_final_status.json::case001_manual_word_review`。含义：第 4 轮人工复核曾判 `FAIL` 并给出 A/B/C 三项发现，这些发现已在本轮**自动化关闭**（`AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`），但**人工尚未重新确认**——既不算通过，也不算被阻塞。**不得**因机器门禁全绿而驳回人工结论 |
| `CASE002_MANUAL_WORD_REVIEW` | **NOT_YET_CONFIRMED** | 无人工复核记录 |
| `CASE003_MANUAL_WORD_REVIEW` | **NOT_YET_CONFIRMED** | 无人工复核记录 |
| `CASE001_XLSX_MANUAL_REVIEW` | **NOT_YET_CONFIRMED** | 复核工作簿尚未开始人工 Excel 复核（Phase B 交付物） |
| `POINTER_CHECK` | **PASS** | `v1_three_case_regression_final.json`（`THREE_CASE_GENERALIZATION = PASS`，`failed_checks = []`） |
| `HARD_BREAK_FIDELITY` | **PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION** | `case001_typography_final.json::measurements.hard_break_fidelity` |
| `CASE001_FINAL_UNEXPECTED_HARDBREAK_CLOSURE` | **PASS** | `case001_p6_unexpected_hardbreak_diagnostic.json`（`verdict = P6_SOURCE_ROW_CONTINUITY_CLOSED`）+ `case001_typography_final.json` |
| `P6_SOURCE_ROW_CONTINUITY` / `P6_UNEXPECTED_W_BR` | **CLOSED** | 同上 |
| `RESPONSE_LETTER_COMPOSITE_SLOT` / `SOURCE_TABLE_CELL_ALIGNMENT` | **CLOSED** | `case001_manual_review_followup_acceptance_final.json::checks` |
| `P3_SEMANTIC_POLICY` / `P3_SEMANTIC_INTENT` / `P3_HORIZONTAL` | **8/8** / **8/8** / **8/8** | `case001_p3_semantic_registry_gate_final.json`（`failed_checks = []`） |
| `P3_SEMANTIC_EXECUTION_BINDING` | **8/8** | 同上（组合槽位按原子校验；历史红结论见 5.4 与 `case001_composite_execution_binding_diagnostic*.json`） |
| `COMPOSITE_EXECUTION_BINDING` | **CLOSED** | `case001_composite_execution_binding_diagnostic.json`（`unaccounted_atoms = 0`、`invented_atoms = 0`、`fact_value_mismatches = 0`、`duplicate_executions = 0`） |
| `P3_RULE_ACCOUNTING` | **matched 8 / lost 0 / invented 0 / out_of_tolerance 0** | 同上 |
| `documented_structural_deviation_count` | **1** | `case001_typography_final.json` |
| `unexplained_structural_split_count` | **0** | 同上 |
| `builder_forced_break_count` | **0** | 同上 |
| `unexpected_w_br_count` / `unexpected_w_cr_count` | **0** / **0** | 同上（整篇文档 `generated_w_br = 0`、`generated_w_cr = 0`） |

> **历史（HISTORICAL / SUPERSEDED build）**：第 4 轮桌面 Word 人工复核**已经发生**，其复核对象是
> `acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final`，并针对**该历史 build**
> 判定 `CASE001_MANUAL_WORD_REVIEW = FAIL`，给出源格式阻断项（§5.5 的 OPEN 项 A / B / C）。
> 这个 `FAIL` 是历史事实，**不得删除或改写**。
>
> **当前（CURRENT，closure8 候选）**：A / B / C 已由自动化关闭
> （`AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`，见 §5.6），但人工尚未在 closure8 上重新确认，
> 因此当前状态**唯一**为 `CASE001_MANUAL_WORD_REVIEW = NOT_YET_CONFIRMED`（§1.2 表中的当前值）：
> 既不算通过，也不算被阻塞。**不得**因机器门禁全绿而驳回历史人工结论，也**不得**把历史 `FAIL`
> 当作当前 build 的状态。术语见 [V1_DECISIONS.md](V1_DECISIONS.md) 第 9 节。

> `READY_FOR_SUBMISSION` **不是**编译器/流水线的全局状态。任何自动化结论都不得把它置为 true；
> 只有逐项目的商务 / 法务 / 报价 / 签字盖章复核完成后，才可能就该具体项目讨论提交就绪。

### 1.3 概念状态

| 维度 | 状态 |
| --- | --- |
| V1 自动化架构 | **advanced / largely closed** —— 三案例自动化验收全部 PASS，冻结契约未被削弱 |
| CASE001 自动化回归 | **PASS**（`THREE_CASE_GENERALIZATION = PASS`，`failed_checks = []`，`POINTER_CHECK = PASS`） |
| CASE001 硬换行保真 | **CLOSED**：整篇文档 0 个 `w:br`、0 个 `w:cr`；`unexpected_w_br_count = 0`；唯一的换行差异是第 7.1 节记录的**一个已复核段落边界** |
| CASE001 结构偏差策略 | **已协调**：`HARD_BREAK_FIDELITY = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`，偏差已文档化、计数并公开；本轮**未**把新关闭的缺陷记成第二个偏差 |
| CASE001 人工 Word 复核 | **NOT_YET_CONFIRMED** |
| CASE002 / CASE003 人工 Word 复核 | **NOT YET COMPLETED** |

第 5.4 节记录过的「`BLOCKED` 与 all PASS 并存」的状态模型矛盾**已经消除**：缺陷 B 不再被表示为
`BLOCKED`，而是表示为**已评审接受的结构性偏差**（`deviation_state = REVIEWED_ACCEPTED`，
`container_fidelity = SOURCE_CONTAINER_MISMATCH`），并且仍然留有一条未完成的人工复核项。

---

## 2. V1 产品范围与非目标

### 2.1 产品定位

**Tender Document Compiler（招标文件编译器）**，并保持设计顺序：

> **Source Format First → Style System Second → Automation Third**

生成文档必须同时是：**native Word、可编辑、由源格式驱动、事实安全（fact-safe）、可复核（reviewable）**。

### 2.2 V1 支持的输入

| 输入 | 行为 |
| --- | --- |
| 文本型 PDF | 支持 |
| DOCX | 支持 |
| 扫描件 / 纯图片 PDF | **V1 无 OCR**；返回 `OCR_REQUIRED`，停止下游交付，**不得凭空编造抽取文本** |

### 2.3 V1 核心输出

一次成功解析的运行写入 4 项核心交付（同批，不得跨运行拼接）：

- `project_facts.json`
- `投标项目复核表.xlsx`
- `基础投标文件.docx`
- `qa_report.json`

其余 10 个技术证据产物（规范化文档、事实复核包、语义候选、生成报告、源格式 QA、复核证据包、复核证据 QA、metadata 等）分层与新鲜度约束见 [PROJECT_GOVERNANCE.md](../PROJECT_GOVERNANCE.md) 第 3 节。

### 2.4 V1 明确排除

FastAPI、React、数据库、向量数据库、RAG、外部 LLM 调用、OCR。

### 2.5 定位补充

`基础投标文件.docx` 是**基础骨架**，不是可直接提交的完整标书。投标人名称、报价、签章、银行账户、项目经理、企业资质等自有信息保持占位符。

---

## 3. 数据 / 语义权威模型

三个权威数据域 + 一个基础设施基线（运行时细节见 [PROJECT_GOVERNANCE.md](../PROJECT_GOVERNANCE.md) 第 2.1 节）：

| 域 | 拥有的内容 | 不拥有的内容 |
| --- | --- | --- |
| `ProjectFacts` | 唯一的事实值权威（当前固定 23 个字段） | 结构、版式、编号 |
| `SourceFormat` / 已校验源格式证据 | 文档结构、可见编号、版式、源表格槽位、源视觉格式（字体/字号/字重/对齐/缩进/间距） | 事实值 |
| `ReviewEvidence` | 证据检索结果与证据 locator | 事实值、合规结论 |
| 外部 Word fixture | Word 可编辑性与样式基础设施 | 投标格式、源编号、事实、视觉格式 |

硬规则：

- **`ProjectFacts` 是事实值的 SSOT。** 缺失事实**永不发明**。
- 事实冲突 → `NEEDS_REVIEW`；事实缺失 → `NOT_FOUND`。
- **语义补全必须带 source evidence locator**；没有可靠证据就保持 `NOT_FOUND`。
- 未知的投标人专属字段保持未填写。
- **纯展示性源标记不得成为事实。**
  范例：CASE001 的 `lot_name` 即使源表格以 `/` 表示「不适用」并把它作为源格式标记输出，仍然保持 `NOT_FOUND`，
  `/` 永远是 `SOURCE_FORM_NOT_APPLICABLE_MARKER`，不生成事实、也不生成事实候选。
- 系统**全局不得**声称 `READY_FOR_SUBMISSION = true`（见 1.2）。

---

## 4. 冻结的三案例回归覆盖

本节只记录**回归覆盖**，不是事实转储。逐案例的未定稿字段以各自 `project_facts.json` 为准。

### CASE001 — 引江济淮郸城县配套工程水源置换城乡供水工程项目部一体化泵站采购项目

| 项 | 值（来自 `acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_followup/project_facts.json`） |
| --- | --- |
| project_name | 河南省水利第二工程局集团有限公司引江济淮郸城县配套工程水源置换城乡供水工程项目部一体化泵站采购项目 |
| project_number | `YSEJJXXB202607-18` |
| purchaser | 河南省水利第二工程局集团有限公司 |
| duration | `30日历天` |
| project_location（交货地点） | 周口市郸城县石槽泵站 |
| quality_target | 符合国家及行业有关标准、规范和询比文件要求 |
| bid_validity | `90日历天` |
| bid_bond_amount | `20000` |
| max_price | `3100000` |
| consortium_allowed | `false`（无联合体） |
| lot_name | **`NOT_FOUND`** |
| 字段汇总 | 23 总：RESOLVED 16 / NEEDS_REVIEW 1 / NOT_FOUND 6 |

> 质保期「24 个月」是源文件事实，但**不属于**当前 23 字段 `ProjectFacts` 的字段集合；
> 不要把它写成 ProjectFacts 字段。
> 关注点：P3（生成页 3 / 源页 42）响应函组合槽位、R3/R4 冻结几何、R6 语义绑定、P21 组合下划线与首行缩进。

### CASE002 — 营收系统整合和硬件系统升级项目

覆盖要点：

- 预算 / 最高限价（ceiling）与多个限值并存；
- 软件与硬件质保期差异；
- 不允许联合体 / 不允许分包；
- 星号（★）强制条款；
- **跨页长报价明细表**。

**强制架构回归：**该跨源页长报价表必须保持为**一个逻辑可编辑 Word 表格**（不得被拆成多个表或合成版式表格）。
未定稿字段：`procurement_scope = NEEDS_REVIEW`；`budget`/`lot_name`/`lot_number`/`submission_method = NOT_FOUND`。

### CASE003 — 肇源县城市供水管网漏损治理项目三标段

覆盖要点：

- 有实际意义的标段（lot/section）语义；
- `lot_name = "三标段"` 具源证据（`lot_cover_title`，源页 1，block_index 7）；
- **不得继承 CASE001 的 `lot_name = NOT_FOUND` 行为**。

未定稿字段：`budget`/`lot_number`/`procurement_method`/`project_number`/`submission_method`/`tender_number = NOT_FOUND`；
`bid_deadline`/`bid_open_time`/`consortium_allowed`/`duration`/`electronic_platform`/`quality_target = NEEDS_REVIEW`。

---

## 5. 当前指针与前次验收状态

### 5.1 当前被接受的 build 指针（CURRENT）

依据：三份指针 JSON 的**磁盘内容**（`acceptance/reports/v1_generalization/case_00X_current_build.json`，
schema `v09_current_build_pointer/1`），不是历史叙述。

| 指针文件 | 指向 build id | 生成 DOCX sha256 | 生成 PDF sha256 |
| --- | --- | --- | --- |
| `case_001_current_build.json` | `v1_manual_fidelity_round4_date_rhythm_closure8` | `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230` | `3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927` |
| `case_002_current_build.json` | `v1_round4_closure8` | `1e694c00bc341cfc3f87220fdb00cef13dea4b27f946f60c17efa0752b16589d` | `851549be46a538769d5c39df51fc5649c9601949d34e979840dd6368e7b78455` |
| `case_003_current_build.json` | `v1_round4_closure8` | `74946ddcdfa52781e4be1fec6e771e4658157867dcc98c5352b943a42b945a54` | `c9e0de0f9954f4118e03e6f7210d8a4b0951da411a13e5198db9df3a329a011e` |

三份指针的 DOCX/PDF 均指向各自 closure8 build 的 `基础投标文件.docx` / `基础投标文件.pdf`；
`POINTER_CHECK = PASS`（`v1_three_case_regression_final.json`，`failed_checks = []`）。
CASE001 的当前验收对象与哈希见 §5.6。

#### 5.1.1 历史指针值（HISTORICAL / SUPERSEDED）

以下是**已被 closure8 取代**的旧指针值，仅作历史记录，**不得**当作当前状态：

| 指针文件 | 旧指向 build id | 旧 DOCX sha256 |
| --- | --- | --- |
| `case_001_current_build.json`（历史） | `v1_manual_fidelity_round3_word_review_final` | `16dc0ae275cb43799a76df5770b43fb7dc76b9d93b374e07621792419f95a191` |
| `case_002_current_build.json`（历史） | `v1_manual_fidelity_round3_word_review_final` | `5206b4103338f4319c0510d3edaeed15e9628164db7161ca2b83e66989f08012` |
| `case_003_current_build.json`（历史） | `v1_followup3` | `e013b1f24f8a05ee9dd5d6b88518306aec2c1ebb9694d127e65150d9cf3e2365` |

历史 CASE001 PDF = `ad2692ef9e0baa47a60ff17662cb3259d8a7b3ac47cde55e2fbc8fde1860a174`（301445 B，22 页）；
历史 CASE002 PDF = `8608b9fb52d1fba5d3afc0efdc5a9d64460d8ced4b37064b35f2a7957f90104f`（504585 B，32 页）。

**CASE003 历史上为何没有迁移（已记录的判断，历史条目）：** 当时的共用发射器修复会重建 CASE003，
但重建产物的 `generation_report.json`（`1248666a…`）、`project_facts.json`、
`normalized_document.json`、`source_format_qa.json` 与被接受产物**逐字节相同**；差异仅存在于
DOCX 的 ZIP 时间戳字段（同一大小 56872 B、14 个 part 载荷全同）与 PDF 中一个重新子集化的
字体（该 PDF 本身在本机不可复现：对**同一个** DOCX 重渲染会得到第三个哈希）。
因此按「不为时间戳而迁移」的纪律，CASE003 指针当时保持不动，三案例回归即以该产物自身的验收证据评分。
重建产物自身的验收报告保留为 `case003_acceptance_final.json` 以备查。**该判断已被 closure8 轮次取代**：
CASE003 现在的指针目标是 `v1_round4_closure8`（见上表）。

### 5.2 最新人工复核候选 build（HISTORICAL / SUPERSEDED）

> **当前的人工复核候选是 §5.6 的 closure8 build**；本节描述的
> `v1_manual_fidelity_round3_word_review_final` 是**当时**的候选，现为历史。

build id：**`v1_manual_fidelity_round3_word_review_final`**（历史）

来源：`acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final/build_manifest.json`

| 项 | 完整值（历史） |
| --- | --- |
| manifest status | `FRESH_BUILD` |
| 源 PDF sha256 | `8e2bfb00e1a0c595db16d179477d9a09769ab82e45f63d476c3c8c459d46aa27`（61 页） |
| 生成 DOCX sha256 | `16dc0ae275cb43799a76df5770b43fb7dc76b9d93b374e07621792419f95a191`（45533 B） |
| 生成 PDF sha256 | `ad2692ef9e0baa47a60ff17662cb3259d8a7b3ac47cde55e2fbc8fde1860a174`（301445 B，22 页） |
| generation_report sha256 | `97584ab13b820378669f4fee90d94ef918637c35c4cd86a8fc3c28e172e4e761` |
| pipeline returncode | 0 |
| 渲染 | `C:\Program Files\LibreOffice\program\soffice.com`，冻结启动器，returncode 0 |
| 被取代的候选 | `v1_manual_fidelity_round3_word_review_followup`（DOCX `28648aad…924a1` / 45550 B，PDF `8013ce99…41a68` / 301457 B，22 页），**未被覆盖**，其状态/清单已归档为 `*_superseded_by_unexpected_hardbreak_closure` |

### 5.3 指针是否已迁移？（CURRENT）

**是，三案例指针均已迁移至各自的 closure8 build**（当前值见 §5.1；依据三份指针 JSON 的磁盘内容）：

- `pointer_repointed = true`（CASE001、CASE002、CASE003）
- `case_001_current_build.json` → `v1_manual_fidelity_round4_date_rhythm_closure8`
  （DOCX `8dedddb7…`，PDF `3fe5b5b9…`）
- `case_002_current_build.json` → `v1_round4_closure8`（DOCX `1e694c00…`，PDF `851549be…`）
- `case_003_current_build.json` → `v1_round4_closure8`（DOCX `74946ddc…`，PDF `c9e0de0f…`）
- 历史指针副本按轮次归档为 `case_00X_current_build_superseded_by_*.json`
  （`unexpected_hardbreak_closure`、`policy_reconciliation`、`round4_date_rhythm_closure8`；
  CASE001/CASE002 各三份，CASE003 两份 —— 原文件内容逐字节保留，未删除）
- 依据：`v1_three_case_regression_final.json` = `THREE_CASE_GENERALIZATION = PASS`，
  `failed_checks = []`，`POINTER_CHECK = PASS`
  （`pointers_resolve_to_the_acceptance_build`、`pointers_exist_for_every_case`、
  `build_directories_distinct`、`source_documents_distinct`、`generated_documents_distinct` 全为 true）。
  该回归对每个案例都用**其自身指针所指产物**的验收报告评分，因此指针/验收不一致无法被掩盖。

### 5.4 历史 build（`v1_manual_fidelity_round3_word_review_final`）的门禁结果（HISTORICAL）

> 本节是**历史** build 的门禁记录（第 4 轮续作之前）。**当前** closure8 build 的门禁见 §5.6.4，
> 复核工作簿第 3 轮的机器状态见 §12.1 / §12.3。

来源：`acceptance/reports/v1_generalization/case001_manual_word_review_final_status.json`

| 门禁 | 结果 | 说明 |
| --- | --- | --- |
| P3 closure, phase 2 | `PASS` | tolerance `2.0` 未变，无重基线化；`horizontal_failure_ids = []`、`missing_frozen_rule_ids = []`、`cross_page_rule_ids = []`，9 项检查全 true |
| P3 closure, phase 3 | `FAIL` | 与被接受 build 完全相同的 `vertical_row_order_preserved`、`vertical_within_tolerance`，属既有诊断阶段（权威归 `REFLOW_AWARE_V1`） |
| P3 semantic registry | `PASS` | `failed_checks = []`。policy 8/8、intent 8/8、**execution binding 8/8**、horizontal 8/8、matched 8 / lost 0 / invented 0 / out_of_tolerance 0 |
| round-3 typography | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` | 仅 `HARD_BREAK_FIDELITY` 带偏差；其余族 0 失败 |
| `HARD_BREAK_FIDELITY` | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` | `documented_structural_deviation_count = 1`，`unexplained_structural_splits = 0`，`builder_forced_breaks = 0` |
| follow-up acceptance | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION` | 组合槽位 = PASS；段落连续性 = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION；单元格对齐 = PASS |
| P21 structural | `PASS` | classified 77，composite_slots 2，`failed = []` |
| reflow-aware | `PASS` | `maximum_residual_y_error_pt = 0.71`，tolerance 保持 `2.0` |
| manual layout fidelity | `PASS` | 22 页、0 空白页 |
| ownership closure | `PASS` | 本轮针对该 build 重跑 |
| underline inventory | `PASS` | source 8 / matched 8 / lost 0 / invented 0 / out_of_tolerance 0 |
| 案例验收 | `PASS` | CASE001/002/003 均为 `AUTOMATED_RESULT = PASS` |
| three-case regression | `PASS` | `THREE_CASE_GENERALIZATION = PASS`，`failed_checks = []`（`POINTER_CHECK = PASS`） |
| 全量测试套件 | 见 `acceptance/reports/v1_generalization/case001_full_test_suite_final.txt` | **585 collected → 584 passed, 1 skipped, 0 failed, 0 errors，exit 0**（基线 547 + P6 聚焦 16 + 原子绑定 21 = 584 通过；585 = 584 + 1 skipped） |

**已闭合的门禁/证据不一致（`semantic_execution_binding`）：**

> **症状**：`scripts/v1_p3_semantic_registry_gate.py` 的 `semantic_execution_binding` 检查
> 把「实际发出的整条值」与 `ProjectFacts` 的单个原始值逐字比较。P42-R2 发出的组合槽位
> `(河南省水利第二工程局集团有限公司引江济淮郸城县配套工程水源置换城乡供水工程项目部一体化泵站采购项目、/)`
> 在事实值外还带有**源表自身的标点**与源表的「不适用」标记，因此按逐字比较在构造上
> 不可能等于 `project_name` 的原始值，检查必然为红。
>
> **根因**：**门禁在整条字符串层面比较，而该值是在原子层面合成的**——不是 ProjectFacts 缺陷，
> 也不是交付产物缺陷。应用记录 `SFA2` 的 `resolved_values` 是
> `["(…、/)", "YSEJJXXB202607-18"]`，前者的原子分解为
> `SOURCE_TEMPLATE_LITERAL "("` + `FACT_VALUE project_name` +
> `SOURCE_TEMPLATE_LITERAL "、"` + `SOURCE_FORM_NOT_APPLICABLE_MARKER "/"`（`field = lot_name`）+
> `SOURCE_TEMPLATE_LITERAL ")"`；后者是相邻源槽 `slot-42-4` 的 `project_number`，
> 交付为 `（YSEJJXXB202607-18）`。该原子模型**早已存在**于
> `tender_basic/source_fill_policy.py`（`SlotValuePresentation` +
> `COMPONENT_FACT_VALUE` / `COMPONENT_SOURCE_TEMPLATE_LITERAL` /
> `COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER`），并在写入事件处记录进
> `generation_report.json::slot_value_presentations`。
>
> **处置**：修复门禁，不动渲染。新增 `tender_basic/composite_semantic_binding.py`，
> 按原子校验组合槽位（每个 `FACT_VALUE` 必须等于 ProjectFacts 权威值；每个
> `SOURCE_TEMPLATE_LITERAL` 必须声明受认可的源证据类别；每个
> `SOURCE_FORM_NOT_APPLICABLE_MARKER` 不得覆盖已解析事实、不得把 `NOT_FOUND` 变成
> `RESOLVED`；原子拼接必须逐字重放交付表面）。**普通单事实槽位仍保持严格逐字相等**
> ——P42-R1 / R5 / R6 在该报告中的校验模式即为
> `SINGLE_FACT_STRICT_EQUALITY`，组合槽位为 `ATOMIC_PROVENANCE`。
>
> **历史红结论保留、未改写**：修复前的门禁结论存于
> `case001_composite_execution_binding_diagnostic_before_repair.json`
> （`gate_status_before = FAIL`，`binding_failure_ids = ['P42-R2']`），
> `case001_composite_execution_binding_diagnostic.json` 同时记录修复前后两个状态，并用
> `before_repair_fragment_still_present = false` **机器校验**旧判据已从门禁中消失。
>
> **未变**：源契约、`ProjectFacts`、渲染内容、2.0 pt 容差、R3/R4 契约、已复核的
> P3 结构偏差，全部未变；DOCX/PDF 未重新生成。P3 契约钉住的四项（policy 8/8、
> intent 8/8、horizontal 8/8、matched 8 / lost 0 / invented 0 / out_of_tolerance 0）
> 在该 build 上继续成立。
>
> **一般原则**：**过时的测量实现不会使底层的 `ProjectFacts` 契约过时**；组合源槽位只能
> 在原子层面被证明，不能用整条字符串证明。

### 5.5 人工 Word 复核第 4 轮 —— OPEN 发现（ROUND-4 HUMAN FINDINGS）

**状态来源**：桌面 Microsoft Word 人工复核，对象为 `v1_manual_fidelity_round3_word_review_final`
（DOCX `16dc0ae2…f95a191` / PDF `ad2692ef…860a174`）。**结论：不通过**。

> 这些结论是**权威人工证据**。此前机器门禁全绿，是因为**这些维度此前没有被任何门禁测量过**
> （对齐语义 vs 位置缩进、日期行内部源间隙、表格单元格多行基线节奏）。**机器通过不构成反驳。**

| 编号 | OPEN 发现 | 人工观察 | 机器状态 |
| --- | --- | --- | --- |
| **A** | **源日期行的段落对齐语义未被忠实保留** | 生成文档用**段落缩进**去模仿源定位。封面日期段 `w:jc = left` + `w:left ≈ 4248 twips (≈7.49 cm)`，而源日期行是**居中**的；`法定代表人身份证明` 的日期段也带非零左缩进（`≈578 twips / 1.02 cm`） | 此前**无**门禁测量「源对齐类别 vs 生成 `w:jc`」；P3 只覆盖第 42 页规则几何 |
| **B** | **日期行 `年`/`月`/`日` 之间的源间隙与可编辑空白结构被压平** | 若干日期行被渲染成 `年月日`，而源可见形态为 `年    月    日` 或 `____年____月____日`。人工点名的例子包括 `商务和技术偏差表`、`分项报价表`、`反商业贿赂承诺书` 的签署日期行 | 此前**无**门禁测量日期行内部间隙；文本相等门禁对 `年月日` 与 `年    月    日` **同等通过**，属测量盲区 |
| **C** | **`五、分项报价表` 内三行摘要的源行距与源不一致** | 三行摘要视觉行距与源不同。注意：生成的 OOXML 是**一个段落 + 两条源支持的显式换行**，段属性为 `w:spacing line=240 lineRule=auto`——因此缺陷**不是**「行距被设成 1.5」 | 此前门禁只测文本/粗体/下划线/行边界，**不测基线节奏**（baseline rhythm） |

**统一状态**：A / B / C 在修复前均为 **OPEN**。

**第 4 轮自动化结果（`v1_manual_fidelity_round4_date_rhythm`，指针**未**迁移）：**

> 该 build 已生成并通过构建/渲染（`rc = 0`、LibreOffice `rc = 0`、22 页、0 空白页），
> 但**未通过**日期行/行距验收，因此**不是**被接受的 build，指针仍指向
> `v1_manual_fidelity_round3_word_review_final`。
> DOCX `ba9a937a…b23f76` / PDF `74e8d54f…a9cb547` / report `413dc5b3…f00068f`。
>
> | 发现 | 测得的第 4 轮结果 | 状态 |
> | --- | --- | --- |
> | **A** | 封面日期行已由 `w:jc = left` + `w:left = 4248 twips` 改为 **`w:jc = center` + `w:left = 0`**，行内容为其**完整构成**（前导空白 + `年`/`月`/`日` + 内部间隙）。全部 10 个日期段的 `w:left` 要么为 0（居中行），要么等于其**自身测得的源原点**偏移（锚定行）。审计 `alignment_mismatch = 0`、`synthetic_left_indent_for_centering` 不再命中封面行 | **AUTOMATION-CLOSED**（分类与机制）；居中行仍因下方 B 的间隙宽度误差而整体左移约 8.5 pt，未达几何容差 |
> | **B** | 7 个原本渲染为裸 `年月日` 的日期段现在都带源间隙（`collapsed_date_rows` 7 → **0**）。但间隙宽度由 figure space 合成，实测残差 **−3.96 ~ −5.84 pt**，超出 2.0 pt 规则几何容差；`法定代表人身份证明` 签署日期行另有**先存**缺陷（前导 `\t\t` 过冲，`年` 落在 140.35 而源为 99.72，偏差 +40.63 pt，**不是**本轮引入） | **仍 OPEN** |
> | **C** | 根因为表格单元格行距取自**臆造的**比值 `table_size * 1.05`（必然落入单倍行距容差），而非测得节奏。改为测得的主导源间距后 `w:line` 240 → **300**，渲染行距 14.10 → **17.60 pt**（源 23.40 / 19.44）。残差 2→3 为 **1.84 pt**、1→2 为 **5.80 pt**，均超出仓库既有的 1.0 pt 行距容差（`source_vertical_rhythm.DEFAULT_PITCH_TOLERANCE_PT`） | **仍 OPEN**（已定位并部分修复，未达容差） |
>
> 机器证据：`case001_date_row_round4_diagnostic.json` / `.md`（**修复前**，对象为 round-3 build）、
> `case001_date_row_round4_final.json` / `.md`（**修复后**，对象为 round-4 build）、
> `case001_quotation_summary_line_pitch_round4.json`。
> 人工复选框**全部保持未勾选**；`CASE001_MANUAL_WORD_REVIEW` 在新 build 上回到 `NOT_YET_CONFIRMED`。

**曾被记录的状态模型矛盾（已消除）：**

> 历史：`case001_manual_word_review_followup_status.json` 曾把缺陷 B 记为 `BLOCKED` /
> `blocker = true`，而 `case001_manual_review_followup_acceptance.json` 的
> `RESPONSE_LETTER_PARAGRAPH_CONTINUITY` 记 `PASS`——两者语义冲突。
> **现已统一**为单一状态：缺陷 B 是
> `DOCUMENTED_STRUCTURAL_DEVIATION` / `deviation_state = REVIEWED_ACCEPTED`
> （`container_fidelity = SOURCE_CONTAINER_MISMATCH`，`fidelity_difference = CONTAINER_IDENTITY`），
> 由项目政策接受，且留有一条未完成的人工复核项。缺陷 A / 缺陷 C 记为 `CLOSED`。
> 没有 `CASE001` 专属豁免、没有任何门禁被削弱、没有把 `NATURAL_WRAP` 改写为显式换行、
> 没有断言 `same_word_paragraph = true`、偏差没有被隐藏。

**该偏差的公开记账（`case001_typography_final.json::measurements.hard_break_fidelity`）：**

| 计数器 | 值 |
| --- | --- |
| `source_natural_wrap_boundaries` | 1 |
| `source_explicit_breaks` | 0 |
| `generated_w_br` | 0 |
| `generated_w_cr` | 0 |
| `generated_paragraph_boundaries` | 1 |
| `unexplained_structural_splits` | 0 |
| `documented_structural_deviation_count` | 1 |
| `builder_forced_breaks` | 0 |
| `unexpected_w_br_count` | 0 |
| `unexpected_w_cr_count` | 0 |

即：整篇文档**没有任何** `w:br` 或 `w:cr`。偏差仍然是那**一个**段落边界——它是被单独记账的
`generated_paragraph_boundaries`，不是硬换行，两者在此表中是**不同的计数器**。
（上一候选 build 的同一张表里 `generated_w_br = 1`、`unexpected_w_br_count = 1`，
对应的是 `委托期限：` 表单行里的意外换行，已在本轮关闭，见第 6 节。）

偏差证据（可独立复算、带摘要钉住）：
`acceptance/evidence/structural_deviations/response_letter_natural_wrap_boundary.json`
（schema `structural_deviation_evidence/1`，由 `scripts/v1_structural_deviation_evidence.py` 生成）。

---

## 5.6 第 4 轮续作 VII（ROUND 4 CONTINUATION VII）—— 关闭状态与验收对象

**当前验收对象（本文件余下章节的「当前 build」均指这里）**：
`acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8`

| 产物 | SHA256 |
| --- | --- |
| DOCX | `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230` |
| PDF | `3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927` |
| generation_report | `1274c205a9e151976d09c3598b1feffd169fa579878c7f105126994717608ace` |

管道 rc 0、LibreOffice 渲染 rc 0、22 页。CASE001/CASE002/CASE003 三条指针均已指向各自的
新验收 build（CASE002 `v1_round4_closure8`、CASE003 `v1_round4_closure8`），
`POINTER_CHECK = PASS`。`v09_internal_preview/current_build.json` **未改动**。

### 5.6.1 本轮关闭的两项（§5.5 尾部的 scoped items）

| 项 | 缺陷 | 关闭依据 |
| --- | --- | --- |
| A | 前导日期空白逃出固有几何分解（封面 `____年` 的 69.00 pt 由 figure space 字形数合成） | 见 D20/D21：前导区间按空白自身实测起点构造；封面段现为 `w:spacing=1265` twips 的固有间距（渲染 69.00 pt），`date_figure_space_geometry_runs = 0` |
| B | 多段固有间距标定**不可测**（`MEASURED_SPACE_ADVANCE_EM` 曾为 0.535 em） | 见 D21/D22：改测为 **0.500 em**，并用标记夹逼探针 1/2/3 段实测（`case001_intrinsic_spacer_multisegment_calibration_v2.json`，全部残差 0.0），condensed tracking 实测**不被渲染器应用** |

### 5.6.2 日期行验收（`case001_date_row_round4_closure8.json`）

`DATE_AUDIT = PASS`；源 12 行、构建范围内 10 行、生成 10 行、`rows_within_2pt = 10/10`；
`alignment_mismatch = 0`、`collapsed = 0`、`lost_gaps = 0`、`invented_gaps = 0`、
`unexpected_indents = 0`、`ambiguous = 0`、`rows_with_figure_space_geometry = 0`；
`date_intrinsic_spacer_runs = 27`、`date_tab_runs = 0`、
最大间隙残差 **0.23 pt**、最大 token 锚点残差 **0.51 pt**。
规则端点（`case001_date_rule_endpoint_round4_closure8.json`）：`matched = 9 / lost = 0 / invented = 0`，
max x0 残差 **0.55 pt**、max x1 残差 **0.30 pt**。

`CENTER` 轴模型未改：居中行仍是 `w:jc = center`，轴移由 `L − R = 2 × delta` 表达，
`SOURCE_ALIGNED_CENTER` / `SOURCE_ANCHORED_FORM_ROW` 语义与分类阈值均未动。

### 5.6.3 分项报价表三行摘要（`case001_table_cell_line_rhythm_closure8.json`）

`TABLE_CELL_LINE_PITCH_FIDELITY = PASS`：一个逻辑单元格内的**三个原生段落**，
`w:br = 0`、空段落 0、无文本框/图形；源基线 pitch `23.40 / 19.44 pt` → 渲染 `23.40 / 19.45 pt`
（容差 1.0 pt）。源行文本、加粗与下划线全部保留。同一机制在文档内共拆 13 个单元格 / 27 个段落，
文档级 `w:br` 由 22 降到 8。

### 5.6.4 门禁与测试

| 门禁 | 结果 |
| --- | --- |
| P3 phase 2 / phase 3 | `PASS` / `FAIL`（phase 3 的 FAIL 是**既有**状态，非本轮回归；见 §7） |
| P3 语义注册表 | `PASS`（`semantic_policy 8/8`、`semantic_intent 8/8`、`p3_horizontal 8/8`、`matched 8 / lost 0 / invented 0 / out_of_tolerance 0`、`tolerance 2.0 pt` 未重基线化） |
| `HARD_BREAK_FIDELITY` | `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`，`documented_structural_deviation_count = 1`，`unexpected_w_br_count = 0`、`unexpected_w_cr_count = 0` |
| `REFLOW_AWARE_V1` / P3 垂直重排门禁 | `PASS` / `PASS` |
| 版式 / 表格几何 / 下划线清单 / 人工版式保真 | `PASS` |
| 所有权闭环 / 源行装配 / P21 结构 | `PASS` |
| CASE001 / CASE002 / CASE003 验收 | `PASS` / `PASS` / `PASS` |
| 三案例泛化 | `THREE_CASE_GENERALIZATION = PASS`（`failed_checks = []`） |
| 全量测试 | **638 passed, 1 skipped, 0 failed, 0 errors**（639 collected，exit 0），见 `review_workbook_full_test_suite.txt` / `.xml`（复核工作簿轮次） |

新增定向测试 `tests/test_round4_vii_leading_blank_and_cell_rhythm.py`（28 项）钉住前导区间构造、
固有间距标定、`CENTER` 公式不变、半点截断、逐行 pitch 换算、「同一行距无法同时满足两个源 pitch」
的不可行性，以及 P3 已复核偏差证据未被改写。

**本轮未关闭、也未新建任何人工阻塞项**：`MANUAL_WORD_REVIEW_REQUIRED = true`，
CASE001/CASE002/CASE003 的人工 Word 复核仍为 `NOT_YET_CONFIRMED`，
`V1_PRODUCTION_CANDIDATE = false`、`READY_FOR_SUBMISSION = false`。

> **环境注记（§7.4 的同类问题）**：本机 `Path.mkdir(mode=0o700)`（pytest 临时目录工厂使用的 mode）
> 会创建出**创建者自己也无法枚举**的目录（`PermissionError [WinError 5]`），导致所有 `tmp_path`
> 测试报错。全量测试因此通过 `PYTEST_PLUGINS` 从仓库外加载
> `acceptance/workspace/_scratch_round4_vii/pytest_fscompat.py` 把该 mode 还原为默认值。
> 这是**测试基础设施**的规避，未修改任何产品代码与测试文件。

---

## 5.7 缺陷与解决总账（PROBLEM / RESOLUTION LEDGER，按类别归并）

本节把 §6（历史缺陷）与 §7（已知偏差）合并成一张**按类别**的总账：每一行给出
**症状 → 根因 → 通用解法 → 状态 → 证据**。所有解法都是**通用**的：不含页码、段号、
`年月日` 字面量、规则 id、build id 或 case id 特例。

| # | 类别 | 症状 | 根因 | 通用解法 | 状态 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 页面框架 page frame | 页边距/内容框逐页漂移，渲染与源视觉不一致 | 「每页自己算页边距」 | 唯一源派生框架：整篇一个内容框，页面只引用它；禁止逐页重算（F1） | **CLOSED** | `tender_basic/source_page_frame.py`、`case001_page_frame_audit_final.json` |
| 2 | P3 语义绑定 P3 semantic bindings | 8 条冻结 P3 规则的**语义**未被验证，只有几何通过 | 注册表只校验了水平几何，未校验「规则语义=执行语义」 | 四条独立语义校验（policy / intent / horizontal / scope）8/8，且必须证明**执行绑定** | **PASS** | `case001_p3_semantic_registry_gate_final.json`（`semantic_policy 8/8`、`semantic_intent 8/8`、`p3_horizontal 8/8`、`semantic_execution_binding PASS`） |
| 3 | 组合源表单槽位 composite source-form slot | 组合读法 `(…、/)` 与单个事实值不相等，门禁判红 | 门禁把**整条组合字符串**当成一个事实值比较 | 组合槽位按**原子论元**校验（`ATOMIC_PROVENANCE`），普通槽位仍严格单值相等；`/` 是源展示标记，不是事实 | **CLOSED** | `tender_basic/composite_semantic_binding.py`、`case001_composite_execution_binding_diagnostic.json` |
| 4 | R3/R4 几何 R3/R4 geometry | 源规则 R3/R4 端点漂移 | 同一水平位移被两处重复表达（缩进 + tab + 间隙） | 冻结 `EXACT_SOURCE_SPAN`，容差 **2.0 pt 不放宽**；**一个位移只有一个拥有者** | **CLOSED**（phase 2 = PASS） | `case001_p3_closure_phase2_final.json` |
| 5 | P21 组合 P21 composite | P21 结构表单元格内容/合并与源不符 | 结构门禁未覆盖 P21 的组合单元格 | 结构与合并不变量由独立门禁测量，逐单元格对比源签名 | **CLOSED** | `case001_p21_structural_final.json` |
| 6 | P21 缩进 P21 indentation | P21 单元格出现源不存在的左缩进 | 把**位置缩进**当成**源语义对齐** | 分离「源对齐语义」（`SOURCE_ALIGNED_*` / `SOURCE_ANCHORED_FORM_ROW`）与「位置缩进」；无证据不得生成缩进 | **CLOSED** | `tender_basic/source_paragraph_alignment.py`、`source_paragraph_indent.py` |
| 7 | 表格排印 table typography | 表格内字号/加粗/下划线/行结构与源不一致 | 表格单元格沿用默认样式而非源视觉格式 | 源排印门禁逐族校验（硬换行、段落对齐、单元格行结构、加粗、下划线、固定空白） | **PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION**（见第 17/18 行） | `case001_typography_final.json` |
| 8 | 资格单元格对齐 qualification cell alignment | 表格首列被全局居中，源并非居中 | 「全局居中表格首列」这类便捷规则 | 逐单元格**实测**对齐（稳定中轴 / 两侧留白），禁止全局居中或全局归零（T6/T7） | **CLOSED** | `case001_table_geometry_final.json` |
| 9 | P6 硬换行 P6 hard break | `委托期限：` 表单行被强制换行，生成多出一个视觉行 | 判据量的是「**本行是否已有文字**」，而不是**空白自身的源起点** | 判据改为 `blank_x0 + 1.0 < reach`（空白仍在光标之前才开新行）；不含任何语料字面量 | **CLOSED** | `case001_p6_unexpected_hardbreak_diagnostic.json` |
| 10 | 语义注册表原子溯源 semantic registry atomic provenance | 注册表变红 | **测量实现**把组合值当单值比较（同第 3 行），或把历史红结论当成产物缺陷 | 原子校验必须对**全部规则、全部案例**通用；测量缺陷修测量，历史红结论归档不改写；不得放宽门禁 | **PASS** | §5.4、`case001_p3_semantic_registry_gate_final.json` |
| 11 | 日期行对齐 date-row alignment | 封面日期段用 `w:jc=left` + 约 7.49 cm 左缩进「模仿」居中；证明书日期段有多余左缩进 | 对齐语义被位置缩进替代 | 居中行恢复 `w:jc=center`；轴移由**实测**轴差表达，不再用缩进伪造 | **CLOSED** | `case001_date_row_round4_closure8.json`（`alignment_mismatch 0`、`unexpected_indents 0`） |
| 12 | 日期 token 间隙几何 date token gap geometry | `年 月 日` 之间的源间隙被压平成 `年月日`，或由 figure space **合成** | 用字形个数当几何 authority；无前置 token 时前导空白无人拥有 | 间隙宽度由**固有间距**表达（一个 `U+0020` + 实测 `w:spacing`），前导区间按空白自身源起点构造；`date_figure_space_geometry_runs = 0` | **CLOSED** | 同上（`collapsed 0`、`lost_gaps 0`、`invented_gaps 0`、`rows_within_2pt 10/10`、最大残差 0.23 pt） |
| 13 | 固有间距模型 intrinsic spacer model | 合成间隙残差 −3.96 ~ −5.84 pt，超 2.0 pt 容差 | 基础前进量取 `0.535 em`（未实测），且未测字符跟踪响应 | 实测标定：`base_space_advance_em = 0.500`、`TRACKING_RESPONSE_RATIO = 1.0`、负跟踪不取整；用标记夹逼探针在 1/2/3 段与多字号上验证（残差 0.0） | **CLOSED** | `tender_basic/intrinsic_spacer.py`、`case001_intrinsic_spacer_multisegment_calibration_v2.json` |
| 14 | CENTER 对齐框架 CENTER alignment frame | 居中行相对源稳定偏移约 0.12 pt | 生成帧中心与 Word 有效中心轴不是同一个值 | **实测**模型：raw centre 297.650 pt、effective 297.766 pt、`L − R = 2 × delta`、inset 响应 0.4996；低于 0.5 pt 不位移 | **CONFIRMED / 冻结** | `case001_center_axis_calibration*.json` |
| 15 | 部分源规则分解 partial source-rule decomposition | 源日期行只画了部分线（有段落无规则），无法整段对齐 | 把「整行」当成一条规则 | 拆成**有规则的段**（按端点对齐）+ **残余纯间隙**（按测得宽度），不拉伸、不虚构规则 | **CLOSED** | `case001_date_row_round4_closure8.json`、`case001_date_rule_endpoint_round4_closure8.json` |
| 16 | 日期规则端点 date rule endpoints | 规则端点出现 9 条「虚构」规则 | 渲染器把每条下划线画成**两个叠放矩形**（整段 + 短内段），门禁按矩形一对一配对 | 配对前先**并合同线共线**的规则段（间隙 ≤ 0.5 pt），再一对一配对 | **CLOSED** | 同上（`matched 9 / lost 0 / invented 0`，max x0 0.55 pt、max x1 0.30 pt） |
| 17 | P9 多行单元格节奏 P9 multiline cell rhythm | 分项报价表三行摘要源节奏 `23.40 / 19.44 pt`，生成被压成同一行距（≈17.60 / 17.60） | 一个 `w:line` 只能复现一个节奏，却把三行塞进一个带 `w:br` 的段落 | **一个源行一个原生段落**，每段行距由该行**实测** pitch 换算；换算基于**实际交付字号**（`w:sz` 半点截断） | **CLOSED** | `case001_table_cell_line_rhythm_closure8.json`（渲染 23.40 / 19.45，`w:br 0`、空段落 0） |
| 18 | 过时门禁测量的协调 outdated gate measurement reconciliation | 表示法改为原生段落后，`TABLE_CELL_LINE_STRUCTURE` 判红 9 个单元格 | 判据只数 `w:br`，而 Word 表达「单元格内换行」有**两种原生写法**（段内 `w:br` 与段落边界） | **先区分「测量实现过时」与「源契约过时」**：源契约未变（一个可编辑单元格、逐行保真、2.0 pt），故修**测量实现**——数「原生行分隔数 = 源行数 − 1」并要求逐行文本相等，合并/丢失/乱序仍红；**不得弃检、不得放宽** | **CLOSED** | `scripts/v1_source_typography_round3_gate.py::_table_cell_line_structure`、`tests/test_round3_source_typography.py`（含「同一处边界被写成两种分隔即判红」的回归） |

**未列入本表的既知偏差**（不是缺陷，见 §7）：LibreOffice 与 Word 的页面顶端间距差异（§7.2）、
字体度量固有漂移（§7.3）、Windows 目录 ACL 环境问题（§7.4）。

---

## 6. 历史缺陷与解决（HISTORICAL / SUPERSEDED）

按时间顺序，仅为避免重复发现同一问题。每行都已在当前被接受 build 或最新跟进 build 上关闭。

| # | 缺陷 | 症状 | 根因 | 解决 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 1 | 页面框架 / 页边距漂移 | 不同 Word 页面的页边距肉眼可见不一致 | 每页 section 边距由**该页自身**内容极值推导，稀疏页命中大幅 clamp | 由**跨页重复锚点**推导稳定源页面框架 `PORTRAIT_595x842_1`（left 70.8 / right 70.9 / top body 73.86 pt，可用文本宽 453.6 pt，左锚点支持 12 页、右锚点支持 10 页） | CLOSED；22/22 页边距 spread = 0.0 pt |
| 2 | 源行装配 / 同行规则 | 同一视觉源行上的表单字段被输出成不同结构，光标顺序错误 | 缺少源行感知的发射模型 | 源行感知发射：同一视觉行分组、按 source-x 排序、单调光标、不回退 tab | CLOSED；`case001_source_line_assembly*.json` = PASS |
| 3 | 长解析值 / 垂直重排 | `project_name` 需要比源占位符更多的 Word 行 | 绝对源 y 契约无法表达合法的强制重排 | `REFLOW_AWARE_V1` 把**强制重排**与**未解释的垂直漂移**分离 | CLOSED；residual 0.71 / tolerance 2.0 |
| 4 | P21 组合下划线 | `project_name` + 源分隔符 + `/` 未一致继承源槽位下划线 | 槽位装饰继承被陈旧 registry 字段否决 | 下划线继承由**绑定/源槽位**授权；`project_name` + `、` + `/` 占同一组合源槽位；`lot_name` 保持 `NOT_FOUND` | CLOSED；`v1_p21_structural` = PASS |
| 5 | P21 首行缩进 | 段落缩进被表示成整段左缩进 | 正文左边界与首行偏移未分离 | 分离**正文左边界**与**首行偏移**；除非源证据证明悬挂，否则不用悬挂缩进 | CLOSED |
| 6 | Round-3 排版 / 单元格结构 | 人工 Word 复核发现：对齐错误、不当强制换行、表格单元格内部行结构被压平、粗体缺失、下划线丢失、固定空白 span 不完整 | 段落对齐、run 级粗体/下划线、单元格内部源行结构未由源驱动 | 源驱动段落对齐 + 源 run 粗体/下划线传播 + 单元格内部源行结构 + 固定空白/值规则保留 + 文档级排版记账 | CLOSED（基线门禁曾 FAIL 于 `PARAGRAPH_ALIGNMENT`/`TABLE_CELL_LINE_STRUCTURE`/`SOURCE_BOLD_FIDELITY`） |
| 7 | P3 R3/R4 几何回归 | Round-3 的「一段化」流程改动使 R3/R4 固定槽位漂移 | 包裹行（wrapped row）的结构隔离被抑制 | 仅在**该行自身的规则同时欠两个端点**处恢复隔离；R3/R4 冻结几何在 2.0 pt 契约不变的前提下恢复 | CLOSED；phase 2 = PASS |
| 8 | R6 语义 registry / 字段绑定 | R6 被登记为固定空槽，`quality_target` 实际未出现在交付的响应函中 | 字段标签在上一行视觉换行，行作用域绑定看不到它 | 引入通用「上一行标签证据」兜底通道（有界、保守）；R6 现为 `RESOLVED_VALUE_IN_FIXED_SLOT` / `ANCHOR_START_ONLY`、`quality_target`、1 owner、1 `SourceFillApplication` | CLOSED |
| 9 | 表格单元格对齐 | 人工复核指出资格审查表 `统一社会信用代码` 单元格应居中 | 对称 padding 分类器把两行居中折行误判为 JUSTIFY | 源驱动单元格对齐分类；JUSTIFY 分支现在额外要求**最后一行左对齐** | CLOSED；相对被接受 build 只改 1 个单元格（`统一社会信用代码` `both` → `center`）；**不做全局居中** |
| 10 | 表单行意外硬换行（`委托期限：`） | 源第 45 页把标签 `委托期限：`、下划线规则 `P45-R6` 与后缀 `。` 画在**同一视觉行**；交付的 Word/PDF 把它变成**两行** | 空白发射器用「本行是否已有文字」（`paragraph_so_far.strip("\t")`）作为是否另起一行表单行的判据——它量的是**段落**，不是**源表行**。该行的几何子句为假（空白恰好被光标触及，`overshoot_pt = 0.0`），只有文字子句为真，于是发出一条源文不存在的 `w:br` | 判据改为**空白自身的源起点**：`blank_starts_behind_cursor = blank_x0 + 1.0 < reach`，只有光标确实已经越过规则起点时才另起源表单行；`tender_basic/word_safe_source_builder.py::_render_positioned_blank`。通用、无语料/页号/规则号/case 字面量 | CLOSED；`CASE001_FINAL_UNEXPECTED_HARDBREAK_CLOSURE = PASS`；该源行交付为**一行**，规则 x0/x1 误差 0.0 / 0.0 pt（未重基线化），整篇文档 `generated_w_br` 1→0、`unexpected_w_br_count` 1→0；同一源行未被记为偏差 |
| 11 | P3 语义执行绑定误红（组合槽位） | `semantic_execution_binding` 对 P42-R2 报 `EMITTED_VALUE_NOT_FROM_PROJECT_FACTS`，而源表、`ProjectFacts` 与交付产物三者一致 | **门禁在整条字符串层面比较**：它把应用记录的每个值压平成一个「整条字符串」列表，只取第一条与 `ProjectFacts` 的单个原始值逐字比较。组合源槽位的表面由「源模板标点 + 事实值 + 源表『不适用』标记」合成，在构造上不可能等于单个事实值；应用记录本身也是有损视图（`YSEJJXXB202607-18` vs 交付的 `（YSEJJXXB202607-18）`） | 组合槽位改为**按原子校验**：新增 `tender_basic/composite_semantic_binding.py`，逐元校验 `FACT_VALUE`（必须等于 `ProjectFacts` 权威值）/ `SOURCE_TEMPLATE_LITERAL`（必须声明受认可的源证据类别；诊断另与**源 PDF 该规则跨度内实际印出的字符**比对）/ `SOURCE_FORM_NOT_APPLICABLE_MARKER`（不得覆盖已解析事实、不得把 `NOT_FOUND` 提升为 `RESOLVED`），并要求原子拼接**逐字重放**交付表面、无未归类元、无重复执行。**普通单事实槽位仍走严格逐字相等**——是严格超集，不是旁路。通用、无规则号/页号/case/字面量特例 | CLOSED；`P3_SEMANTIC_EXECUTION_BINDING = 8/8`、`failed_checks = []`；修复前红结论保留在 `case001_composite_execution_binding_diagnostic_before_repair.json` 未被改写；渲染器 / `ProjectFacts` / DOCX / PDF 均未改动 |

---

## 7. 已知偏差（KNOWN DEVIATIONS）

### 7.1 缺陷 B —— 响应函「愿意」/「以人民币（大写）」段落边界（当前唯一开口偏差）

**这是当前最重要的架构偏差。该偏差仍然存在**，并且**保持显式、可审计**：
它已被**完全协调进门禁 / 状态 / 指针**（见本节末），门禁表现为
`HARD_BREAK_FIDELITY = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`（**不是**普通 `PASS`）；
但**人工 Word 确认仍然未完成**（`CASE001_MANUAL_WORD_REVIEW = NOT_YET_CONFIRMED`）。

| 维度 | 值 |
| --- | --- |
| 源语义（source_semantics） | `NATURAL_WRAP`——源文件打印**一个**逻辑段落的 4 个折行视觉行，源**从未**在 token 之间断行 |
| 生成表示（generated_representation） | `PARAGRAPH_BOUNDARY` |
| `same_word_paragraph` | `false` |
| `w:br` 数量 | `0` |
| `w:cr` 数量 | `0` |
| 空段落数量 | `0` |
| 可见额外间距 | `0` / 与源等价（不得出现可见空白行或额外段间距） |
| 偏差分类 | **`DOCUMENTED_STRUCTURAL_DEVIATION`** |
| 偏差原因 | **`STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY`** |
| 门禁表现 | `HARD_BREAK_FIDELITY = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`；该边界同时给出 `source_semantics = NATURAL_WRAP`、`generated_representation = PARAGRAPH_BOUNDARY`、`container_fidelity = SOURCE_CONTAINER_MISMATCH`、`fidelity_difference = CONTAINER_IDENTITY`、`deviation_state = REVIEWED_ACCEPTED`，`unexplained_structural_split = false`；`recorded_isolation_reason = STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW`（build 记录通道的既有名称，门禁接受它作为「已接受的结构隔离原因」，而证据文件声明真正原因是冻结几何） |

**冲突证明（可复现证据）：**

- 合并实验（`acceptance/reports/v1_generalization/case001_defect_b_merge_experiment.json`）：
  只移除两个 `w:p` 之间的边界，经冻结启动器渲染后，
  `文件的全部内容，愿意以人民币（大写）` 落在同一行且从 `x=70.9` 起排，续行不再独占一行，
  `continuation_starts_its_own_line = false`，因此 R3 的源锚点 `x=169.65` **不可达**。
- 反向实验（禁用包裹行隔离）：冻结 P3 门禁在 `p3_scope_complete`、`horizontal_within_tolerance`、
  `exact_span_rules_intact`、`no_cross_page_rule_binding` 上失败，`P42-R3`、`P42-R4` 进入 `horizontal_failure_ids`。
- 结论：允许使用的原生 Word 构件**无法同时**提供「同一 `w:p` 自然流」与「所需的回退/固定源位置」。

**已做出的决策（本轮已实施）：**

- **保留 R3/R4 `EXACT_SOURCE_SPAN`**；
- **不放宽 tolerance**（保持 2.0 pt）；
- **不把源断行说成显式换行**（`source_semantics` 保持 `NATURAL_WRAP`）；
- 接受生成的 Word 段落边界为 `DOCUMENTED_STRUCTURAL_DEVIATION`，原因 `STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY`。

权威顺序（偏差成立的依据）：

> ① 源可见形体几何 ② 冻结 P3 水平契约 ③ 事实正确性 / 阅读顺序
> ④ 源语义结构 ⑤ 生成的 Word 容器身份

容器身份权威**最低**，因此让步的是它——而让步被**公开**，没有被隐藏。

该偏差**保持显式且可审计**：`case001_typography_final.json`、
`case001_manual_review_followup_acceptance_final.json`、
`case001_manual_word_review_final_status.json`、
`case001_manual_word_review_final_checklist.md` 与证据文件
`acceptance/evidence/structural_deviations/response_letter_natural_wrap_boundary.json`
五处一致陈述同一状态。**决策已完全协调进门禁 / 状态 / 指针。**

> **本轮对该偏差的处理（重要）：** 本轮关闭的表单行意外硬换行**不是**第二个偏差，也**没有**
> 被记成偏差。它是一条源文不存在的 `w:br`，属于**缺陷**，已按通用规则修复并
> `unexpected_w_br_count = 0`。修复后 `documented_structural_deviation_count` 仍为 **1**，
> `generated_paragraph_boundaries` 仍为 **1**，偏差的 17 个条件仍全部为真。
> 换言之：偏差没有被移除、没有被隐藏、没有被改写成「完美保真」，也没有被用来掩护新的缺陷。

偏差证据契约（通用，非 CASE001 专属）的 17 个条件定义见
[V1_DECISIONS.md](V1_DECISIONS.md) 第 6.1 节。

### 7.2 LibreOffice 页面顶端间距的渲染器差异（需在桌面 Word 确认）

- LibreOffice 只在 `docDefaults` 段落间距被清零（before=0/after=0）后才尊重页顶 space-before；
- Microsoft Word 通过 `w:suppressSpBfAfterPgBrk w:val=false` + compatibility mode 14 到达同一页顶；
- 因此**生成文档的页顶间距必须在桌面 Word 中确认**（见人工复核清单）。
  来源：`case001_manual_layout_closure_audit.json::renderer_dependent_verification_note`。

### 7.3 字体度量差异（非可避免漂移）

Word 行高是**最小值**，两个渲染器对 CJK 回退字体的度量不同；每个实测行高差都在 `max(2.0 pt, 行高 25%)` 之内，分类为 `FONT_METRIC_ONLY`。
来源：同上 `font_metric_note`。

### 7.4 Windows pytest 环境问题（环境问题，不是产品失败）

| 项 | 值 |
| --- | --- |
| 不可访问目录 | `D:\PyCharmProjects\WBTenderSkill\tmp\pytest-of-WPG`（以及仓库根的 `pytest-of-WPG/`、`_r2tmp/`） |
| 症状 | pytest `tmp_path` fixture 建立阶段 `PermissionError` / `WinError 5` |
| 曾观察到的结果 | `370 passed, 1 skipped, 147 setup errors`；本轮定位前的复现为 `E.....`（每个用到 `tmp_path` 的测试都在 setup 报错） |
| 性质 | **环境 / setup 错误，不是产品断言失败**；退出码非零不代表代码红 |
| 干净全量运行（全新可写 basetemp） | `517 passed, 1 skipped, 0 failed, 0 errors` |
| 后续全量运行（跟进 build） | `519 passed, 1 skipped, 0 failed, 0 errors`（仓库存档：`case001_full_test_suite_followup3.txt`） |
| 偏差策略协调后 | `547 passed, 1 skipped, 0 failed, 0 errors` |
| 第 4 轮 closure8 | **`614 passed, 1 skipped, 0 failed, 0 errors`**（615 collected，exit 0），见 `case001_full_test_suite_round4_closure8.txt` / `.xml`（本文件 §5.6.4）。相对上一轮的 612 增加了 2 项：`tests/test_round3_source_typography.py` 的单元格行分隔夹具改为**显式拼写**并新增「同一处边界被写成两种分隔即判红」的回归（见 §5.7 第 18 行） |
| 复核工作簿轮次 | **`638 passed, 1 skipped, 0 failed, 0 errors`**（639 collected，exit 0），见 `review_workbook_full_test_suite.txt` / `.xml`。相对 closure8 的 614 增加 24 项：`tests/test_round62_review_workbook.py`（复核视图契约：事实/状态/定位投影、`NOT_FOUND` 显式显示、人工列与机器列隔离、公式只做汇总、★ 只标否决项、价格行照抄源表、空白报价表单如实呈现、证据索引去重、人工填写不回写机器列、998 行压力、视图表头契约） |

**根因（本轮查清，不是「ACL 玄学」）**：pytest 的临时目录工厂用
`pathlib.Path.mkdir(mode=0o700)` 创建 `tmp_path`，而在本 Windows 主机上，用该 mode 创建出来的目录
**创建者自己也无法枚举**：随后 pytest 对它的 `os.scandir`（第一次发放 `tmp_path` 时，以及会话结束时的
`cleanup_dead_symlinks`）抛 `PermissionError [WinError 5]`。因此故障点是**目录模式**，不是磁盘、不是权限继承、
也不是产品代码。**不得**把它误判为产品测试失败，也**不得**修改产品代码去适配主机 ACL。

**两条受支持的测试路径：**

1. **普通环境**：`pytest -q --basetemp <全新可写目录>`，无需任何插件。
2. **受影响的 Windows 主机**：显式加载仓库内的可选兼容插件（**不自动加载**）：

```powershell
# 等价于普通环境的两步，只是多了一个"仅本次运行"的兼容插件
$env:PYTHONPATH = "$PWD\scripts\dev"
$env:PYTEST_PLUGINS = 'pytest_fscompat'
.venv\Scripts\python.exe -X utf8 -m pytest -q -p no:cacheprovider `
    --basetemp "acceptance\workspace\pytest_fullsuite_$(New-Guid)" --junitxml <scratch>\suite.xml
```

或直接用包装脚本（它会自建全新 basetemp、加载插件、从 JUnit XML 读取计数并落盘证据）：

```powershell
pwsh -NoProfile -File scripts\run_full_tests_windows.ps1
```

- 兼容插件 `scripts/dev/pytest_fscompat.py`：**测试基础设施**，只在显式加载且主机受影响时才生效；
  它把 `Path.mkdir(0o700)` 还原为默认 mode，并在 `pytest_unconfigure` 还原原函数。
  它**不改变任何断言、任何测试体、任何产品模块**，也不被产品代码 import。
- 在 DSH 文件沙箱内运行时，也可用 `scripts/run_pytest_sandbox.py`（同类改写）。
- **不得**为了绕过陈旧的 `pytest-of-WPG` ACL 问题修改产品代码；**不得**把仓库级 ACL 修复当作日常开发步骤；
  **不得**去"修复"那个不可访问的目录树。
- pytest 自己的最终计数行在 PowerShell 捕获下不可靠，因此**计数以 JUnit XML 为准**（包装脚本已内建）。
- 仓库根的 `pytest-of-WPG/`、`_r2tmp/` 已在 `.gitignore` 中按根锚定忽略，git 的
  `warning: could not open directory 'pytest-of-WPG/'` 因此不再出现。

---

## 8. 开放任务（OPEN TASKS，按顺序）

### NEXT 1 — 缺陷 B 的策略 / 门禁协调 ✅ 已完成

要求与结果：

| 要求 | 结果 |
| --- | --- |
| 源语义保持 `NATURAL_WRAP` | ✅ `source_semantics = NATURAL_WRAP` |
| 生成表示保持 `PARAGRAPH_BOUNDARY` | ✅ `generated_representation = PARAGRAPH_BOUNDARY` |
| 偏差 = `STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY` | ✅ `deviation_kind` |
| R3/R4 `EXACT_SOURCE_SPAN` 保持冻结（tolerance 2.0 pt 不放宽） | ✅ 未改；phase 2 = PASS |
| 门禁必须**区分**源语义 / 生成表示 / 已复核的结构性偏差 | ✅ 三个独立字段 + 8 个独立计数器 |
| **不得**伪造 `same_word_paragraph = true` | ✅ 保持 `false` |
| **不得**把源断行称作显式换行 | ✅ `source_explicit_breaks = 0` |

同时消除了第 5.4 节记录的状态模型矛盾。实现落在：

- `scripts/v1_source_typography_round3_gate.py`：通用偏差契约
  （17 条件 + 证据发现 + 8 项独立记账 + `hard_break_disclosure`）；
- `scripts/v1_structural_deviation_evidence.py`：确定性证据生成器；
- `acceptance/evidence/structural_deviations/response_letter_natural_wrap_boundary.json`：签名证据；
- `scripts/v1_case001_followup_acceptance.py` /
  `scripts/v1_case001_followup3_report.py`：状态语义。

### NEXT 2 — 策略/状态/门禁自洽后 ✅ 已完成

1. ✅ 重跑聚焦验收（`case001_typography_followup3.json` =
   `PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`）；
2. ✅ 跑全量测试套件（`547 passed, 1 skipped, 0 failed, 0 errors`）；
3. ✅ 全部检查通过后，current-build 指针已解析到新的跟进 build（`POINTER_CHECK = PASS`）。

### NEXT 2b — CASE001 最终意外硬换行关闭（P6 表单行连续性） ✅ 已完成

| 要求 | 结果 |
| --- | --- |
| 先写只读诊断，再改生产代码 | ✅ `scripts/v1_p6_form_line_diagnostic.py` → `case001_p6_before_build_diagnostic.json`（缺陷所在 build，`UNEXPECTED_HARD_BREAK_IN_ONE_SOURCE_ROW`）与 `case001_p6_unexpected_hardbreak_diagnostic.json`（`verdict = P6_SOURCE_ROW_CONTINUITY_CLOSED`）；后者可用前者作 `--reference-diagnostic` 独立复算 |
| 根因由**发射器自己的记录**证明 | ✅ `FORM_BLANK_REPRESENTATION_FORCED_BREAK`：几何子句为假（`overshoot_pt = 0.0`）、文字子句为真（`paragraph_so_far.strip("\t")`） |
| 修复必须通用（无字面量 / 页号 / 段号 / 规则号 / case 号） | ✅ 判据改为空白自身的源起点 `blank_starts_behind_cursor` |
| 保留源规则几何，不得重基线化 | ✅ 该行规则 x0/x1 误差 0.0 / 0.0 pt；tolerance 仍 2.0 |
| 文档级硬换行审计 | ✅ `generated_w_br = 0`、`generated_w_cr = 0`、`unexpected_w_br_count = 0`、`unexpected_w_cr_count = 0`、`builder_forced_breaks = 0`、`unexplained_structural_splits = 0` |
| 不得把该缺陷记成第二个偏差 | ✅ `documented_structural_deviation_count = 1`（仍只有第 7.1 节那一个） |
| P3 冻结几何与策略回归 | ✅ phase 2 = PASS；policy 8/8、intent 8/8、horizontal 8/8、matched 8 / lost 0 / invented 0 / out_of_tolerance 0 |
| 不得覆盖已接受 build | ✅ `v1_manual_fidelity_round3_word_review_followup` 与 `v1_manual_fidelity_round3_p3semantics` 逐字节未动 |
| CASE002 / CASE003 共用代码回归 | ✅ 两案例 `AUTOMATED_RESULT = PASS`；CASE002 的 `w:br` 4→2，剩余 2 条均带 19.1 / 19.95 pt 几何越界证据；CASE003 的 `generation_report.json` 逐字节不变 |

实现与证据：`tender_basic/word_safe_source_builder.py::_render_positioned_blank`、
`scripts/v1_p6_form_line_diagnostic.py`、`scripts/v1_case001_final_status.py`、
`tests/test_round60_form_line_hard_break.py`、`case001_typography_final.json`、
`v1_three_case_regression_final.json`。

### NEXT 3 — CASE001 最终 Microsoft Word 人工复核

高风险页 / 区域（生成文档 22 页，生成页 = 源页序 − 39）：

| 生成页 | 源页 | 区域 |
| --- | --- | --- |
| 3 | 42 | 响应函（组合槽位、R3/R4/R6、段落边界） |
| 4 | 43 | 响应函附录（分项报价单元格内部结构、90 日历天下划线） |
| 5 / 6 | 44 / 45 | 身份证明 / 授权委托书（成立时间、委托期限空白 span） |
| 9 | 48 | 分项报价汇总表 |
| 12 | 51 | 信誉 / 查询截图说明（粗体注记） |
| 21 | 60 | 反商业贿赂承诺书（组合下划线、首行缩进） |
| 22 | 61 | 其他资料（源粗体标题） |

### NEXT 4 — 仅当 CASE001 人工复核真正通过

才可以考虑建立 manual-fidelity checkpoint commit。
**不自动 push、不自动 tag。**

### NEXT 5 — CASE002 / CASE003 桌面 Microsoft Word 人工复核

- CASE002 强制复核：**跨页长表仍是一个逻辑可编辑 Word 表格**；
- CASE003 强制复核：**有意义的标段（lot/section）语义**（`lot_name = 三标段`，不得继承 CASE001 的 `NOT_FOUND` 行为）。

### NEXT 6 — 三案例人工复核可接受之后

只有此时 V1 才可被视为 production candidate。
即便到那时：**`READY_FOR_SUBMISSION` 全局仍为 false**。
最终提交需要逐项目的商务复核、法务复核、报价复核、签字/盖章复核。

---

## 9. 仓库与变更纪律

- **不得覆盖已接受的历史 build。** 每个新的人工保真 build 都获得新的 build id。
- 保留 manifest 与 hash；不要用截断 hash 记账。
- 被取代的状态文件应**显式链接到后继状态**（示例：`case001_source_typography_round3_status.json::superseded_by`）。
- **不得静默改写旧验收报告**；历史报告是历史证据。
- **不得为了让新门禁变绿而重基线化冻结几何。**
- **不得因为实现改变而削弱测试**（先判断是「测量实现过时」还是「源契约过时」）。
- 人工阻塞项存在期间不得 commit / push，除非做出明确的 checkpoint 决策。
- 默认保留用户现有未提交改动；除非用户明确要求，不执行 `git reset`、不覆盖既有验收目录、不提交、不推送、不发布。

---

## 10. 已确认过时 / 被取代的状态（SUPERSEDED / STALE）

按来源优先级规则，下列历史状态与当前产物不一致，**显式标注为过时**，不做静默调和：

| 历史状态 | 声称 | 当前事实 | 处置 |
| --- | --- | --- | --- |
| `acceptance/reports/v1_generalization/v1_automated_candidate_gate.json` | `status = V1_AUTOMATED_CANDIDATE`，`result = PASS`，`failed_checks = []` | 其引用的回归报告是 `three_case_regression.json`（`THREE_CASE_GENERALIZATION = PASS`） | **SUPERSEDED**（后继：`v1_three_case_regression_followup3.json` = `PASS`） |
| `acceptance/reports/v1_generalization/three_case_regression.json` | `THREE_CASE_GENERALIZATION = PASS` | 仍然成立 | **PARTIALLY SUPERSEDED**，后继：`v1_three_case_regression_followup3.json` |
| `case001_source_typography_round3_status.json` | `HARD_BREAK_FIDELITY = CLOSED` | 该结论属于 pre-follow-up build（`v1_manual_fidelity_round3_p3reconciled`） | 该文件**自带** `superseded_by` 字段；当前状态以 `case001_typography_followup3.json` 为准（`PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION`） |
| `case001_typography_followup3_superseded_by_policy_reconciliation.json` | `round-3 typography = FAIL`（`HARD_BREAK_FIDELITY`） | 该报告写于偏差契约编码**之前** | **SUPERSEDED**，自带 `superseded_by` / `superseded_sha256`；后继：`case001_typography_followup3.json` |
| `case_00{1,2,3}_current_build_superseded_by_policy_reconciliation.json` | 旧的指针目标（`v1_manual_fidelity_round3_p3semantics` / `v1_round3_p3semantics`） | 指针现已解析到验收 build | **SUPERSEDED**，自带 `superseded_by`；后继：`case_00{1,2,3}_current_build.json` |
| `case001_manual_layout_closure_audit.json::full_test_suite` | `tests = 455` | 当前全量 = 547 passed / 1 skipped | **STALE 计数**（关账轮的记录），当前计数以当轮全量运行为准 |
| `acceptance/reports/v1_generalization/v1_manual_review_checklist.md` 第 1 节 | 指向 `v1_manual_fidelity_round2_p21fix` / `v1_round2_p21fix` 构建目录 | 当前指针目标为 `v1_manual_fidelity_round3_word_review_final` / `v1_manual_fidelity_round3_word_review_final`（case_003 仍为 `v1_followup3`） | 已在清单内标注为 **历史轮次**，并以第 1.6 节指向当前 build（见清单文件） |
| `case001_manual_word_review_followup_status.json` / `…_checklist.md` | 把 `v1_manual_fidelity_round3_word_review_followup` 记为「最新候选」，`generated_w_br = 1`、`unexpected_w_br_count = 1` | 该候选已被 `v1_manual_fidelity_round3_word_review_final` 取代，且其 `w:br` 已关闭（`generated_w_br = 0`） | **SUPERSEDED**：其证据未被改写，并**新增** `superseded_by` / `superseded_reason` / `superseded_build_id`（清单文件加同样的提示横幅）；标注**之前**的逐字节快照归档为 `*_superseded_by_unexpected_hardbreak_closure.{json,md}`；后继：`case001_manual_word_review_final_status.json` / `…_final_checklist.md` |
| `case001_typography_followup3.json` 等 `*_followup3.json` 门禁报告 | 衡量上一候选 build 的几何 | 当前权威是同一门禁的 `*_final.json` | **历史证据，未改写**；当前数值以 `*_final.json` 为准 |
| `case001_p3_semantic_registry_gate_final.json`（**修复前**的那一版，`status = FAIL`，`semantic_execution_binding = ['P42-R2']`） | 组合槽位 `P42-R2` 的语义执行绑定为红 | 该红结论是**测量实现缺陷**：门禁在整条字符串层面比较（见 §5.4、§6 第 11 行） | **SUPERSEDED**（同名文件被修复后的 `PASS` 版本取代）。修复前的红结论**未被改写**，逐字保留在 `case001_composite_execution_binding_diagnostic_before_repair.json`（`gate_status_before = FAIL`、`gate_binding_failure_ids = ['P42-R2']`）与 `case001_composite_execution_binding_diagnostic.json::gate_collapse.before_repair`（含旧判据原文，并以 `before_repair_fragment_still_present = false` 机器校验其已消失） |
| `v1_three_case_regression_final.json`（本轮一次**输入配对错误**产生的 `FAIL`） | `pointers_resolve_to_the_acceptance_build` 为红 | 该次运行把 CASE003 的验收报告配成了 `case003_acceptance_final.json`（对应 `v1_manual_fidelity_round3_word_review_final`），而 CASE003 的指针指向 `v1_followup3` | **操作者输入错误，非回归**。已用与指针匹配的 `case_003_followup3_acceptance.json` 重跑 → `THREE_CASE_GENERALIZATION = PASS`、`failed_checks = []`。**指针未被改动** |

> 历史报告**不**因为被标注而过时就被改写。本文件只负责说明「当前权威是谁」。

---

## 11. 当前状态来源产物清单

本文件所有数值的取证来源：

```
acceptance/reports/v1_generalization/case_001_current_build.json
acceptance/reports/v1_generalization/case_002_current_build.json
acceptance/reports/v1_generalization/case_003_current_build.json
acceptance/reports/v1_generalization/case001_manual_word_review_final_status.json
acceptance/reports/v1_generalization/case001_manual_word_review_final_checklist.md
acceptance/reports/v1_generalization/case001_p6_unexpected_hardbreak_diagnostic.json
acceptance/reports/v1_generalization/case001_p6_before_build_diagnostic.json
acceptance/reports/v1_generalization/case001_typography_final.json
acceptance/reports/v1_generalization/case001_p3_closure_phase2_final.json
acceptance/reports/v1_generalization/case001_p3_closure_phase3_final.json
acceptance/reports/v1_generalization/case001_p3_semantic_registry_gate_final.json
acceptance/reports/v1_generalization/case001_composite_execution_binding_diagnostic.json
acceptance/reports/v1_generalization/case001_composite_execution_binding_diagnostic_before_repair.json
acceptance/reports/v1_generalization/case001_reflow_final.json
acceptance/reports/v1_generalization/case001_p21_structural_final.json
acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate_final.json
acceptance/reports/v1_generalization/case001_manual_review_followup_acceptance_final.json
acceptance/reports/v1_generalization/case001_page_frame_audit_final.json
acceptance/reports/v1_generalization/case001_underline_inventory_final.json
acceptance/reports/v1_generalization/case001_ownership_closure_final.json
acceptance/reports/v1_generalization/v1_three_case_regression_final.json
acceptance/reports/v1_generalization/case00{1,2,3}_acceptance_final.json
acceptance/reports/v1_generalization/case002_p6_unexpected_hardbreak_row_measure.json
acceptance/reports/v1_generalization/case001_manual_word_review_followup_status.json
acceptance/reports/v1_generalization/case001_manual_review_followup_acceptance.json
acceptance/reports/v1_generalization/case001_manual_word_review_followup_checklist.md
acceptance/reports/v1_generalization/case001_manual_layout_closure_audit.json
acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate.json
acceptance/reports/v1_generalization/case001_manual_layout_fidelity_gate_followup3.json
acceptance/reports/v1_generalization/case001_p3_closure_phase2_followup3.json
acceptance/reports/v1_generalization/case001_p3_closure_phase3_followup3.json
acceptance/reports/v1_generalization/case001_reflow_followup3.json
acceptance/reports/v1_generalization/case001_p21_structural_gate.json
acceptance/reports/v1_generalization/case001_typography_followup3.json
acceptance/reports/v1_generalization/case001_defect_b_merge_experiment.json
acceptance/reports/v1_generalization/case001_manual_review_followup_3defects_diagnostic.json
acceptance/reports/v1_generalization/case001_page_frame_audit_followup3.json
acceptance/reports/v1_generalization/case001_round3_p3semantic_reconciliation_status.json
acceptance/reports/v1_generalization/case001_source_typography_round3_status.json
acceptance/reports/v1_generalization/case001_full_test_suite_followup3.txt
acceptance/reports/v1_generalization/case001_full_test_suite_final.txt
acceptance/reports/v1_generalization/libreoffice_frozen_launcher_canary.json
acceptance/reports/v1_generalization/three_case_regression.json
acceptance/reports/v1_generalization/v1_three_case_regression_followup3.json
acceptance/reports/v1_generalization/v1_automated_candidate_gate.json
acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final/build_manifest.json
acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_final/project_facts.json
acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_followup/build_manifest.json
acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_followup/project_facts.json
acceptance/workspace/case_002/v1_round3_p3semantics/project_facts.json
acceptance/workspace/case_003/v1_round3_p3semantics/project_facts.json
```

---

## 12. 当前进展与下一步（CURRENT PROGRESS / NEXT TASKS）

### 12.1 当前进展（本条是"我们现在在哪"的唯一权威回答）

| 工作流 | 状态 |
| --- | --- |
| **Word 自动化** | **machine-closed pending human review**：CASE001 closure8 的全部机器门禁通过（§5.6.4）；三项历史人工发现（A / B / C）已自动化关闭；**人工桌面 Word 复核尚未确认**（当前 `CASE001_MANUAL_WORD_REVIEW = NOT_YET_CONFIRMED`，历史 `FAIL` 见 §1.2） |
| **复核工作簿（投标项目复核表.xlsx）** | **machine-closed pending human review**：九个 sheet（原交付表 + 复核视图 00–07）已实现；**第 4 轮（当前机器状态）**把不变量推进到渲染层——**SEMANTIC OWNERSHIP MUST SURVIVE RENDERING**：交付单元格由 `RenderedReviewComponent` 投影生成（`cell_from_components`），每个渲染短语都必须有*关注点自有*的出处；三案例第 4 轮报告 **PASS**（CASE001 `25/25`、CASE002 `23/23`、CASE003 `23/23`）、八类 `RENDERED_*_CONCERN_MISMATCH = 0`、三案例门禁 **40/40 PASS（各自，复用第 3 轮门禁）**、渲染 QA **PASS**（`clipping_bounded` WARN：CASE001 **8** / CASE002 **10** / CASE003 **25**，均不劣于基线）、Word 产物逐字节未变；**人工 Excel 复核尚未确认**（第 3 轮人工复核结论为 **FAIL**，原因 `RENDERED_COMPONENT_CONCERN_OWNERSHIP`，第 4 轮已由自动化关闭并记为 `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`） |
| **人工 Excel 复核** | 未确认：第 3 轮工作簿经人工复核判 **FAIL**（`FAIL_REASON = RENDERED_COMPONENT_CONCERN_OWNERSHIP`，模型里有归属、渲染文本仍会继承过期/过宽来源组），第 4 轮已自动化关闭该缺陷，人工结论列**仍未勾选**（`已通过 = 0`；`CASE001_XLSX_MANUAL_REVIEW = AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`、`CASE002_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`、`CASE003_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`）；当前复核对象见 §12.3 与 `v1_manual_review_checklist.md` 第 4 节 |
| **全量测试（复核工作簿第 4 轮）** | 见 §12.3「Round4 全套测试」（`review_workbook_round4_full_test_suite.txt` / `.xml`，JUnit XML 计数） |
| **发布** | **not ready**：`V1_PRODUCTION_CANDIDATE = false`、`READY_FOR_SUBMISSION = false`、**无 tag、无 release** |
| **检查点** | `PRE_XLSX_CHECKPOINT = PASS`：commit `fef72d9281042357e8f0f6d8d44e000aedda60aa` 已推送至 `origin/main`（**不是**发布提交、**无 tag、无 release**）；第 3 轮复核工作簿检查点 = commit `49a514a`（`feat: enforce review-concern ownership in tender workbook`），已推送；工作簿轮次细节见 §12.3 |

> 第 4 轮（当前）的机器状态以
> `acceptance/reports/v1_generalization/review_workbook_round4_final_status.json`
> 为准（`result = PASS`、`blockers = []`、三案例第 4 轮报告 PASS、门禁 `40/40`）；
> 第 3 轮的状态**只是历史**，不得再当作当前机器状态。
> 第 3 轮（历史）的机器状态以
> `acceptance/reports/v1_generalization/review_workbook_round3_final_status_reconciled.json`
> 为准（`result = PASS`、`blockers = []`、三案例门禁 `40/40`）；它**取代**首个产物
> `review_workbook_round3_final_status.json`，取代原因 `MEASUREMENT_AGGREGATOR_KEY_MISMATCH`
> （该首产物把门禁计数打印成 `None/None`，结论同为 `PASS`；被取代产物**逐字节保留、未改写**，
> SHA256 `d225dc141ada3c119c9b4e2ec02eaa0394eb6212a515e698fad35db5b33190a0`）。
> 第 2 轮的状态**只是历史**，不得再当作当前机器状态。

### 12.3 复核工作簿轮次（REVIEW WORKBOOK ROUND，已完成机器闭环）

**当前轮次 = 第 4 轮（Round4）**；第 1 / 第 2 / 第 3 轮行保留为历史，已明确标注。

| 项目 | 值 |
| --- | --- |
| **当前轮次** | **Round4**（渲染组件出处闭环：`RenderedReviewComponent` + 最终单元格审计） |
| **本轮不变量（当前）** | **SEMANTIC OWNERSHIP MUST SURVIVE RENDERING**——*每一个渲染进 XLSX 的实质短语，都必须有"关注点自有"的出处*；模型对象里有归属**不够**，交付单元格的文本本身必须可追溯到同关注点的来源原子/数值/材料/证据 |
| **语义管线（当前）** | `SourceRequirementAtom → ReviewConcern → ReviewPoint → RenderedReviewComponent → 工作簿视图` |
| **渲染组件模型** | `tender_basic/review_rendering.py`（`RenderedReviewComponent` 九类组件、`ComponentOwnership`、`verify_component`、`foreign_terms`、`provenance_map`） |
| **关注点引擎（当前）** | `tender_basic/review_concern.py`（原子化、`ReviewConcern` 注册表与分类、句级仲裁、归属违规检查器、可执行性过滤） |
| **复核要点引擎（当前）** | `tender_basic/review_point.py`（`synthesize_concern_point` / `synthesize_review_point` / `value_sentence` / `render_review_cell` / `scan_review_points`），由 `dynamic_review.build_dynamic_review_plan` 按关注点建行 |
| 工作簿构建器 | `tender_basic/review_workbook_views.py`（`build_review_views` / `augment_review_workbook(..., refresh_legacy_rows=)`），由 `review_builder.build_review_workbook` 调用 |
| 后继构建工具 | `scripts/v1_build_review_workbook.py`（复制 Word 产物，不重新渲染；`--refresh-legacy-rows` 重算交付表动态复核行；**目标目录已存在时拒绝覆盖**，重跑前须先删除） |
| 工作簿门禁 | `scripts/v1_review_workbook_gate.py`（第 1 轮 37 项；第 2/3/4 轮 `--legacy-text-refresh` **40 项**；第 4 轮三案例各 **40/40 PASS**） |
| 渲染 QA | `scripts/v1_review_workbook_visual_qa.py`（LibreOffice PDF + 重算副本） |
| **单元格投影** | `tender_basic/dynamic_review.py::cell_from_components`——交付表 D 列文本由已校验组件投影生成，不再由模板直接拼接 |
| **Round4 报告** | `scripts/v1_review_workbook_round4_report.py`（重新读取**最终** xlsx 单元格校验渲染输出、A–S 人工坏例、30 格最终单元格审计、出处映射）→ `case00{1,2,3}_review_workbook_round4.{json,md}` + `review_workbook_round4_rendered_component_provenance_case_00{1,2,3}.json` |
| **Round4 最终状态** | `scripts/v1_review_workbook_round4_final_status.py` → `review_workbook_round4_final_status.{json,md}` |
| **Round4 人工复核输入记录** | `acceptance/reports/v1_generalization/case001_review_workbook_round4_human_review.json`（人工 = `FAIL` / `RENDERED_COMPONENT_CONCERN_OWNERSHIP`，自动化**只能**关闭为 `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`） |
| **Round4 后继构建（当前复核对象）** | CASE001 `acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook4`（45 行，`投标项目复核表.xlsx` sha256 `be084b7aeefd24cd1a81cd3452b92a63389ca256a7fd785d4eed1dc85db52c3c`，70271 B）<br>CASE002 `acceptance/workspace/case_002/v1_round4_closure8_review_workbook4`（46 行，sha256 `ea6c4f2d9bc8473c3f2d8bed5bf53bd3e74a0f2a9086adeaad3ed79d22359ea9`，76801 B）<br>CASE003 `acceptance/workspace/case_003/v1_round4_closure8_review_workbook4`（49 行，sha256 `3bb048a45ebb3a445f6171c97cf39ec47fd61e7aeb3942e8f6f73be50d160735`，81382 B） |
| **Round4 测试模块** | `tests/test_round64_rendered_component_provenance.py`（A–S 人工坏例 + 渲染出处 / 旧组泄漏 / 过期关联事实 / 最终单元格证据归属 / 质保金措辞 / 评分拆分 / 平台角色区分） |
| **Round4 全套测试** | **770 collected / 769 passed / 1 skipped / 0 failed / 0 errors**（`review_workbook_round4_full_test_suite.txt` / `.xml`，JUnit XML 计数） |
| Round3（HISTORICAL） | 复核关注点归属：`scripts/v1_review_workbook_round3_report.py` → `review_workbook_round3_content_quality_case_00{1,2,3}.{json,md}`；后继构建 `..._review_workbook3`（CASE001 `v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook3`、CASE002/003 `v1_round4_closure8_review_workbook3`，XLSX SHA256 见 `review_workbook_round3_final_status_reconciled.json`）；三案例门禁 40/40；`review_workbook_round3_final_status_reconciled.json` = PASS；全套测试 716 collected / 715 passed / 1 skipped / 0 failed（`review_workbook_round3_full_test_suite.{txt,xml}`） |
| Round3 测试模块（HISTORICAL） | `tests/test_round64_review_concern_ownership.py`（32 项覆盖） |
| Round3 关键语义事实 | CASE001：`PROJECT_WARRANTY 24个月` / `RETENTION_MONEY_RATIO 5%` / `RETENTION_RELEASE_PERIOD 12个月` 为三个关注点，同一「质保」关键词**不构成**源冲突（`FALSE_CONFLICT_COUNT = 0`）；CASE002 `budget NOT_FOUND`、`max_price 7507785.65` RESOLVED、分项报价 36 行；CASE003 `lot_name 三标段` RESOLVED |
| Word 产物 | closure8 的 DOCX/PDF/generation_report **原样复制、逐字节相同**（`word_render_repeated=false`，第 1–4 轮均未重新渲染 Word） |
| 指针 | 不迁移：`*_current_build.json` 描述 **Word** 构建，三案例继续指向 closure8（§5.1）；工作簿后继构建是**复核视图**，不是新的 Word 指针目标 |
| 人工复核 | 第 3 轮人工判 `FAIL`（`RENDERED_COMPONENT_CONCERN_OWNERSHIP`）；第 4 轮自动化关闭为 `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`，**人工结论列仍未勾选**（`已通过 = 0`） |
| 第 2 轮（HISTORICAL） | 复核要点合成：`scripts/v1_review_workbook_round2_report.py` → `review_workbook_round2_content_quality.{json,md}`；后继构建 `..._review_workbook2`；门禁 40/40；全套测试 684 收集 / 683 passed / 1 skipped / 0 failed |
| 第 1 轮（HISTORICAL） | 复核视图首次落地：`review_workbook_v1_final_status.{json,md}`；后继构建 `..._review_workbook1`；门禁 37/37 |
| 历史轮次的复核行数 | 第 2 轮：CASE001 47 → 46（过滤 1 条非行动项：平台服务费条款归入"售后服务与运维"）；CASE002 49；CASE003 53（历史值，非当前） |

### 12.2 下一步任务（有序）

| 顺序 | 任务 | 完成判据 |
| --- | --- | --- |
| **A** | 改进 `投标项目复核表.xlsx`（复核视图：总览、事实、关键条款、强制/★项、报价与限价、文件结构与签章、冲突与缺失、证据索引） | ✅ 已完成：三案例工作簿门禁 37/37 PASS + 渲染 QA PASS（`REVIEW_WORKBOOK_THREE_CASE_GENERALIZATION = PASS`） |
| **A2** | 复核工作簿第 2 轮：把复核行改写为**人工复核要点合成**（要求/复核要点/通过标准/不满足后果/准备材料/评分提示），删除样板文字与无关数字 | ✅ 已完成：三案例门禁 40/40 PASS、内容质量报告 PASS（7/7 已知坏例、8 组 BEFORE→AFTER、19 种复核类型覆盖测试）、全套测试 684 收集 / 683 passed / 1 skipped / 0 failed |
| **A3** | 复核工作簿第 3 轮：**复核关注点归属**（`SourceRequirementAtom -> ReviewConcern -> ReviewPoint`），每个渲染组件必须同源且同关注点；修正质保期/质保金/释放期语义 | ✅ 已完成：三案例门禁 40/40 PASS、内容质量报告 PASS（14/14 A–N、20/20 审计、≥15 BEFORE→AFTER、`FALSE_CONFLICT_COUNT = 0`）、32 项归属测试、全套测试 716 收集 / 715 passed / 1 skipped / **0 failed / 0 errors**（`review_workbook_round3_final_status_reconciled.json` = PASS） |
| **A4** | 复核工作簿第 4 轮：**渲染组件出处闭环**——人工判第 3 轮 `FAIL`（`RENDERED_COMPONENT_CONCERN_OWNERSHIP`），交付单元格必须由已校验组件投影，且每个渲染短语都有同关注点出处（**SEMANTIC OWNERSHIP MUST SURVIVE RENDERING**） | ✅ 已完成（机器闭环）：三案例第 4 轮报告 PASS（25/25、23/23、23/23）、八类 `RENDERED_*_CONCERN_MISMATCH = 0`、A–S 人工坏例 19/19、CASE001 最终单元格审计全格一致、门禁 40/40、渲染 QA PASS、Word 产物逐字节未变、全套测试 0 failed / 0 errors；人工结论列仍为 `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW` |
| **B** | 人工 Excel 复核（打开工作簿逐表复核，勾选手工结论列） | `CASE001_XLSX_MANUAL_REVIEW` 由人工置为已确认（当前为 `AUTOMATION_CLOSED_PENDING_HUMAN_REVIEW`，第 3 轮人工判 `FAIL` / `RENDERED_COMPONENT_CONCERN_OWNERSHIP`，第 4 轮已自动化关闭） |
| **C** | 如人工 Excel 复核暴露源数据缺陷，回到 CASE001 桌面 Word 复核（否则无需重开） | CASE001 人工 Word 复核结论 |
| **D** | CASE002 / CASE003 桌面人工 Word 复核 | 两个 case 的人工结论 |
| **E** | 最终 release-candidate 检查点 | 三案例人工复核均完成后的独立决策 |
| **F** | 商务 / 法务 / 报价 / 签字盖章批准 | **在自动化之外**由人完成；自动化永不推断 `READY_FOR_SUBMISSION` |

> 关于任务 A 的纪律：工作簿是**复核视图**，不是第二个事实库。`ProjectFacts` 仍是事实 SSOT；
> 人工在 Excel 里填的值**不得**静默写回 `ProjectFacts`，而是作为"复核差异"呈现（`V1_DECISIONS.md` §14）。
