# tender-basic V1 MVP Scope

状态：范围已锁定（Scope Locked）；当前实现已落地，发布门禁另见 [PROJECT_GOVERNANCE.md](PROJECT_GOVERNANCE.md)
项目定位：可封装为 WorkBuddy Skill 的轻量级招投标文件处理工具  
本文件用途：维护 V1 的范围基线、数据契约、验收标准和 V2 变更边界；不把历史规划当成当前目录结构。

## 1. V1 目标

V1 只完成以下闭环：

> 招标文件解析 → 项目基本信息抽取 → 可追溯事实 → Excel 复核表 → 基础投标文件

工具一次处理一个招标文件，所有事实型下游输出均由同一份规范化 `project_facts` 数据生成；
DOCX 的源结构和格式由已校验的 SourceFormat 证据提供，复核证据包是独立的来源检索结果，
复核表的复核行由来源条款动态生成，不扩张 ProjectFacts 字段或自动合规结论。固定优先级为：
**Source Format First → Style System Second → Automation Third**。

## 2. 输入与输出契约

### 2.1 输入

支持以下本地文件：

1. 文本型 PDF：使用 PyMuPDF 提取文本和页码来源。
2. DOCX：使用 python-docx 提取正文段落和标准表格内容及其来源位置。

不在 V1 支持范围内：扫描件内容识别、OCR、图片/截图中的文字、复杂嵌入对象中的文字、多个文件自动合并。

### 2.2 成功路径输出

每次 `PARSED` 运行生成以下四项核心交付：

1. `project_facts.json`：规范化项目事实及全部来源证据。
2. `投标项目复核表.xlsx`：面向人工复核的事实清单、状态、来源和待办项。
3. `基础投标文件.docx`：只包含已抽取事实、关键要求和待填写占位内容的基础文档。
4. `qa_report.json`：解析、抽取、事实完整性和输出校验结果。

同一次运行还会生成规范化文档、事实复核、格式生成和复核证据/动态复核项等技术产物；
完整的 14 文件清单及其分层见 [PROJECT_GOVERNANCE.md](PROJECT_GOVERNANCE.md)。Round 5.1
的源编号、导航、样式和可编辑性 QA 只属于验收/调试证据，不改变这 14 个正常运行产物。

### 2.3 阻断路径

若 PDF 无法获得可靠文本，必须返回 `OCR_REQUIRED`：

- `qa_report.json` 记录 `OCR_REQUIRED` 及检测依据。
- 不得调用 OCR。
- 不得凭空生成项目事实、Excel 或投标文件。
- 不把扫描件的图片内容当作已抽取事实。

## 3. 事实模型与不变量

### 3.1 最小事实范围

V1 的 ProjectFacts 字段目录固定为 23 个；稳定契约以 `tender_basic.models.FieldName`、`ProjectFields`、`rules/output_fields.yaml` 和 `schemas/project_facts.schema.json` 共同校验：

- `project_name`、`project_number`、`tender_number`、`lot_name`、`lot_number`。
- `purchaser`、`tender_agency`、`project_location`、`procurement_scope`。
- `budget`、`max_price`、`duration`、`quality_target`。
- `bid_deadline`、`bid_open_time`、`bid_open_location`、`bid_validity`。
- `bid_bond_amount`、`bid_bond_form`、`consortium_allowed`、`procurement_method`。
- `submission_method`、`electronic_platform`。

字段未在文件中出现时，保留字段状态 `NOT_FOUND`，不填入推测值。资格条件、澄清截止、联系人等宽泛条款可由 64 项复核证据包检索，但不因此扩张 ProjectFacts 字段目录。

### 3.2 每条事实的最低结构

每条事实至少包含：

- 稳定字段名。
- 抽取值或空值。
- 状态：`RESOLVED`、`NEEDS_REVIEW` 或 `NOT_FOUND`。
- 一个或多个来源证据；证据包含原文摘录和定位信息。

来源定位按输入类型保存：

- PDF：页码，必要时附文本块或行定位。
- DOCX：段落序号、表格序号和单元格位置，必要时附标题/章节上下文。

已确认的非空事实必须能在输入文本中找到对应证据摘录。`NOT_FOUND` 是字段状态，不得被伪造为事实。

### 3.3 冲突与歧义

- 同一字段存在不能确定为同一含义的多个值时，保留全部相关证据并标记 `NEEDS_REVIEW`。
- WorkBuddy 模型可以提出语义候选、同义字段映射和歧义说明，但不得无证据补值或静默选择冲突值。
- Python 负责确定性校验、格式规范化、证据引用校验、冲突标记和输出；不负责臆测语义。

## 4. V1 非目标

以下内容明确不进入 V1；64 项复核证据包只用于来源检索和人工复核准备，不等同于完整审标或自动评分：

- Web 前端、FastAPI 服务、数据库、PostgreSQL、Redis、向量数据库。
- RAG、企业知识库、文档检索系统、用户体系和权限体系。
- 完整长篇标书 AI 写作、自动编造技术方案、自动编造商务承诺。
- OCR 引擎、扫描件文字识别、图像理解流水线。
- Docker 部署、云端任务队列、分布式执行、可插拔基础设施抽象。
- 多租户、历史项目管理、在线协作、Excel 回填后反向更新事实。
- 不属于当前字段目录的复杂行业规则和自动投标决策。
- 复制 AGPL 或其他公开项目源码；公开项目仅可用于研究架构思想。

## 5. 当前目录结构与职责

以下为当前实现的目录与职责基线。该项目已经包含运行代码、规则、模板、验收资产和脚本；新增目录或替换入口必须先更新本文件与项目治理约束，不得把历史规划目录当作发布内容。

```text
tender-basic/
├── MVP_SCOPE.md
├── pyproject.toml
├── README.md                   # 使用说明与当前能力边界
├── SKILL.md                   # WorkBuddy Skill 调用契约
├── PROJECT_GOVERNANCE.md      # 项目级治理、状态机与发布门禁
├── rules/                      # 字段别名、输出标签、复核条款和规则
├── schemas/                   # ProjectFacts 与 resolution JSON Schema
├── templates/                 # 复核表模板及其说明
├── tender_basic/              # 解析、事实、输出和 QA 的可复用实现
├── scripts/                   # 流水线、解析、构建、QA、打包入口
├── tests/                     # 离线单元测试和回归测试
└── acceptance/                # 验收样例、报告和人工 Word 门禁资产
```

目录树为治理索引而非完整文件清单；`acceptance/` 与 `.agents/notes/` 属于项目验证和决策记录，不是运行时事实来源。当前 V1 不设置 `api/`、`web/`、`db/`、`rag/`、`repositories/`、`adapters/`、`services/` 等没有消费者的层级。

## 6. 模块职责

### `SKILL.md`

- 定义 WorkBuddy 的输入、输出、调用顺序、失败状态和人工门禁。
- 约束模型只在已有 Candidate 中进行语义复核，不创建无证据事实。

### `tender_basic/models.py`

- 使用 Pydantic 定义文档来源、证据、字段事实、ProjectFacts、复核请求和 QA 数据。
- 固定 23 个字段、字段状态和证据最小结构，作为 JSON、XLSX、DOCX 与 QA 的数据契约。

### `tender_basic/document_parser.py` 与 `document_models.py`

- 根据扩展名解析文本型 PDF 或 DOCX，并保留页码、段落、表格和单元格定位。
- 对 PDF 执行确定性的文本可用性检测；扫描或无可靠文本时返回 `OCR_REQUIRED`，不执行 OCR。
- 输出 `normalized_document.json` 和 `document.lines.txt`，供后续事实与证据检索使用。

### `tender_basic/fact_extractor.py`、`fact_normalizer.py`、`fact_resolver.py` 与 `resolution.py`

- 从规范化文档发现候选，校验证据引用，规范化日期、金额和枚举文本。
- 安全合并候选；无法确定时保留 `NEEDS_REVIEW`，字段缺失时生成 `NOT_FOUND`。
- 生成唯一的 `project_facts.json`；`apply_resolution.py` 只允许选择已有候选或保持未解决。
- `semantic_candidates.py` 只接受带规范化文档精确 locator、匹配证据和值类型的 source-backed 候选，随后交回 Python resolver。

### `tender_basic/review_evidence.py`、`dynamic_requirements.py`、`dynamic_review.py` 与 `review_builder.py`

- 按 `rules/review_items.yaml` 生成复核证据包（召回辅助）；`dynamic_requirements.py` 从句级来源片段建立
  有序来源要求索引，`dynamic_review.py` 据此生成复核项 `DR###`。
- 用户复核工作簿的复核行由这些来源要求动态生成：行数由招标文件决定，`rules/review_items.yaml` 不决定行数；
  模板的标题块、模块列、结论列与签章块保留。
- 复核条款是宽召回和来源证据入口，不是 ProjectFacts 字段目录，也不自动给出合规结论。

### `tender_basic/bid_document_builder.py`、`source_format.py` 与 `word_safe_source_builder.py`

- 从 ProjectFacts 生成 XLSX 和基础 DOCX；原文存在可确定格式章节时优先提取其结构。
- 生成器只从 ProjectFacts 取得事实填充值，从 SourceFormatTemplate/已校验源格式证据取得结构和格式；ReviewEvidence 仅可用于复核证据展示。
- 生产 DOCX 使用 Word-safe 新建文档路径；未知事实、需复核事实和投标人信息使用明确占位符。
- 不生成完整技术方案、商务承诺或可直接提交的标书，不读取原文自行补值。

### `tender_basic/style_architecture.py` 与 `word_style_source_builder.py`

- 保留 Round 5.0 的 Named Style、继承和 outline 架构，同时把源文件自有标题/正文列表的可见编号作为 `SOURCE_LITERAL` 文本保留。
- 源 Heading/Body List 样式不依赖 `numPr`；真实 Heading 样式提供 Word 导航，正文列表样式提供 hanging indent。系统新增内容才使用隔离的 `GENERATED_AUTO` 编号族。
- 标题分类必须结合字体、几何、语义、目录、邻接结构和章节上下文；编号前缀单独不足以把段落升格为标题，歧义项保持 `HEADING_CLASSIFICATION_NEEDS_REVIEW`。

### `tender_basic/delivery_qa.py`、`source_format_qa.py` 与 `word_safe_scan.py`

- 从磁盘重新加载最终产物，校验 ProjectFacts、模板结构、字段状态、证据和输出一致性。
- 生成 `qa_report.json`、`source_format_qa.json` 及 Word-safe 扫描结果；自动 QA 不能替代桌面 Word 人工门禁。

### `scripts/run_pipeline.py`、`scripts/apply_resolution.py` 与打包脚本

- `run_pipeline.py` 串联解析、事实处理、证据复核、格式生成和磁盘 QA，写入同批 14 项产物。
- `apply_resolution.py` 应用受限的 Candidate 选择后重新生成派生产物；`package_skill.py` 和 `validate_package.py` 负责发布包。

### `rules/`、`schemas/`、`templates/` 与 `tests/`

- `rules/` 保存字段别名、输出标签、复核条款、来源优先级和校验规则；`schemas/` 保存机器可校验契约。
- `templates/` 保存正式复核表模板，不作为第二套事实来源；`tests/` 使用离线 fixtures 覆盖解析、事实、输出、QA 和回归。

## 7. 端到端数据流

```text
WorkBuddy 输入文件路径
        │
        ▼
参数与文件校验
        │
        ▼
文本提取
  ├─ 文本型 PDF → PyMuPDF → 页面文本 + 页码证据
  ├─ DOCX      → python-docx → 段落/表格文本 + 结构证据
  └─ 扫描/无可靠文本 → OCR_REQUIRED → qa_report.json → 停止
        │
        ▼
确定性候选发现与归一化
  输出：候选字段 + 原文摘录 + 来源定位 + 归一化比较值
  约束：候选必须引用输入文本，不得创造事实

可选 WorkBuddy 语义处理：`facts_review_packet.json` 仅处理已有 `NEEDS_REVIEW` 候选；
`fact_gap_packet.json` 可提交 `NEEDS_REVIEW`/`NOT_FOUND` 的 source-backed 候选，但必须经 Python 校验后再重新解析。
        │
        ▼
Pydantic 校验与事实整理
  ├─ 证据引用校验
  ├─ 日期/金额等确定性规范化
  ├─ 缺失字段 → NOT_FOUND
  └─ 冲突/无法判断 → NEEDS_REVIEW
        │
        ▼
唯一 project_facts 数据源
        │
        ├─ project_facts.json
        ├─ 投标项目复核表.xlsx
        ├─ 基础投标文件.docx
        └─ qa_report.json


DOCX 源格式分支
  ├─ SourceFormatTemplate / 已校验源格式证据 → 结构、层级、编号、版式和表格
  ├─ ProjectFacts → 唯一事实值填充
  ├─ ReviewEvidence → 仅复核证据展示
  └─ “格式自拟”等系统新增内容 → 可使用独立 GENERATED_AUTO 编号

同一次运行还必须保留规范化文档、事实复核包、候选结果、格式 QA、64 项证据包、元数据等技术产物；产物新鲜度和状态解释遵循 [PROJECT_GOVERNANCE.md](PROJECT_GOVERNANCE.md)。
```

关键边界：模型只负责需要语义理解的候选抽取和歧义说明；Python 负责稳定的解析、校验、状态处理和文件生成。任何输出生成器都不直接读取原始文档并自行补充事实。

## 8. V1 验收标准

### 输入与解析

- [ ] 对文本型 PDF 能稳定提取正文，并为事实提供正确页码来源。
- [ ] 对 DOCX 能提取正文段落和标准表格，并保留段落/表格/单元格定位。
- [ ] 对扫描件 PDF 或无法获得可靠文本的 PDF 稳定返回 `OCR_REQUIRED`。
- [ ] 检测到 `OCR_REQUIRED` 时不调用 OCR，不生成无依据的下游事实。
- [ ] 不依赖网络、数据库、缓存服务或外部知识库即可运行。

### 事实与追溯

- [ ] 项目事实只来自输入招标文件，并符合 V1 字段目录。
- [ ] 每条已抽取非空事实都有原文摘录和来源定位。
- [ ] 找不到的字段标记 `NOT_FOUND`，不使用默认值或常识补全。
- [ ] 同字段冲突保留相关证据并标记 `NEEDS_REVIEW`，不静默猜测。
- [ ] `project_facts.json` 能通过 Pydantic 模型校验，并可作为三个核心下游输出的唯一事实输入。

### 输出文件

- [ ] `PARSED` 且生成成功时四个核心交付均生成，另有同批 14 项产物清单；JSON、XLSX、DOCX 可正常打开/解析。
- [ ] 复核证据包与 `rules/review_items.yaml` 对齐，记录来源和检索状态，不把未核实条款转为合规结论。
- [ ] 复核表的复核行由来源条款动态生成（行数随文件变化），每行记录来源依据、核验动作与通过标准，模块列与签章块保留。
- [ ] Excel 复核表展示事实值、状态、证据摘录、来源定位、缺失项和冲突项。
- [ ] 基础投标文件只填入已确认或明确标注需复核的招标事实；投标人自有信息使用占位符。
- [ ] 源文件自有标题和正文列表保留可见编号、标点、编号后空格及源文件序号间隔；样式/outline 与可见编号解耦，源段落不依赖自动编号。
- [ ] 自动生成内容的编号使用独立的 Generated 样式/编号族，能够学习源文件约定，但不改变任何 SOURCE_LITERAL 段落。
- [ ] 基础投标文件不生成完整技术方案、商务承诺或输入文件中不存在的事实。
- [ ] QA 报告记录输入类型、解析状态、事实统计、缺失/冲突项和输出校验结果。
- [ ] 任意输出生成失败时，QA 报告能明确指出失败阶段和原因，不返回“成功”状态。

### 可封装性与质量

- [ ] WorkBuddy Skill 只需传入一个文件路径和输出位置即可触发完整流程。
- [ ] Skill 能区分成功、`OCR_REQUIRED` 和确定性失败三类结果。
- [ ] 核心逻辑可由 pytest fixtures 离线测试，结果可重复。
- [ ] 代码依赖限定为 Python 3.11+、PyMuPDF、python-docx、openpyxl、pydantic、PyYAML 和 pytest。
- [ ] 不引入本范围未列出的服务、基础设施或大型抽象层。

### 发布门禁

- [ ] 自动 QA、静态 Word-safe 扫描、python-docx 重开和代表性渲染均通过。
- [ ] `source_numbering_qa.json`、`outline_tree.json`、`style_architecture_qa.json` 和编辑性 QA 通过；正文列表不进入导航，目录条目不成为真实 Heading，歧义编号片段不被仅凭前缀升格。
- [ ] 桌面 Microsoft Word 对人工验收样例均能正常打开，无修复提示、内容丢失或不可编辑异常。
- [ ] 代表性页面、标题层级、表格、编号、占位符和业务事实已由人工复核；未满足前不得称为可提交标书或正式发布包。

## 9. V1 结束条件

满足上一节的技术与人工门禁，才可将当前实现标记为 V1 发布完成；仅通过自动化测试只能标记为技术审阅包完成。任何新增需求必须先形成 V2 范围变更，不得直接混入 V1。

V1_SCOPE_LOCKED
