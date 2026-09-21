# WorkBuddy 招投标 Skill 项目治理约束

状态：当前生效

本文件是仓库的现行项目管理约束，适用于源代码、规则、Schema、WorkBuddy 封装、运行产物和验收报告。范围基线见 [MVP_SCOPE.md](MVP_SCOPE.md)，运行时行为见 [SKILL.md](SKILL.md)；治理决策记录位于开发仓库的 `.agents/notes/implemented/process/`，发布包不依赖这些记录。

## 1. 第一性原理

本项目真正要交付的是“可追溯的招标文件事实和人工复核基础”，不是一份未经确认即可提交的完整标书。主要失效模式只有四类：

1. 把输入文件没有说过的内容当成事实；
2. 把相似标签、不同所有者或不同金额含义合并；
3. 用旧运行产物、人工改过的派生文件或未验证的模板冒充当前结果；
4. 把结构检查通过误报成桌面 Word 可打开、视觉可接受或可以投标。

因此所有实现和文档必须同时守住以下闭环：

> 输入证据 → 规范化定位 → CandidateFact → ProjectFacts → 派生产物 → 技术 QA → 人工门禁 → 发布决定

任何一环没有证据或没有通过，都只能报告其真实的中间状态。

## 2. 事实与规则的唯一来源

- `normalized_document.json` 只保存输入 PDF/DOCX 的文本、结构、顺序和定位，不决定字段含义。
- `ProjectFacts` 是 XLSX、DOCX、QA 以及复核包的唯一事实来源。生成器不得重新读取原始文件并自行补值。
- 每个非空 `RESOLVED` 字段必须能回溯到至少一个 CandidateFact、原文摘录和 locator；没有可靠证据就使用 `NOT_FOUND`。
- 人工 `NEEDS_REVIEW` 只能在已有候选之间复核，不得自由创建事实；可选语义候选路径允许从 `NEEDS_REVIEW` 或 `NOT_FOUND` 提交 source-backed 候选，但必须通过精确 locator、原文证据和值类型的 Python 校验后才能重新解析。`project_number`、`tender_number`、`lot_number`、`budget` 和 `max_price` 永远保持语义独立。
- 当前 `ProjectFacts` 固定为 23 个字段；复核模板的 64 项是条款证据检索/人工复核清单，不是 64 个事实字段，也不产生自动合规结论。
- `rules/*.yaml` 和 `schemas/*.json` 是机器契约；修改字段、状态、定位、输出结构或规则语义时，必须同步参考文档和测试。

### 2.1 三个权威数据域与一个基础设施基线

必须把数据的“事实含义”“来源格式”和“复核证据”分开管理：

- **ProjectFacts** 是事实值的唯一权威。所有 `project_name`、编号、金额、时间、主体和其他 23 个字段的填充值只能来自同一次运行的已校验 `ProjectFacts`。渲染器、SourceFormat、ReviewEvidence、fixture、模型或生成的 Word 结构都不得创建替代事实值。
- **SourceFormatTemplate / 已校验的源格式证据** 是源文件自有结构和格式的权威。它可以来自 `normalized_document`、源 PDF/DOCX 几何、表格、标题和“投标文件格式/响应文件格式”章节，负责结构、层级、可见编号、标点、编号后空格、字体、字号、字重、对齐、段落间距、缩进、表格、空白栏、分页和源文件固定文字；它不是事实来源。
- **ReviewEvidence** 是可追溯复核证据的权威。它由 `normalized_document` 和 `rules/review_items.yaml` 产生，只承载证据片段、定位和复核状态；它不是 ProjectFacts，不是自由文本事实来源，也不把 `FOUND`、`MULTIPLE_FOUND`、`NOT_APPLICABLE_CANDIDATE`、`NEEDS_REVIEW` 或 `NOT_FOUND` 变成合规结论。
- **外部 Word fixture**（当前为 `danyang-v1.1-numbering-sanity-fixture-v5.docx`）只是 Word 可编辑性和样式基础设施基线，可提供 Named Styles、继承、Heading 1–9、outline/TOC 语义、正文/表格样式、自动编号机械能力以及 keep-with-next/keep-lines 等基础；它不是投标格式、源编号、事实或视觉格式权威。不可随包分发时必须记录为外部、未版本化且不可复现的输入。

跨域发生冲突时按以下固定顺序处理：

> **SOURCE FORMAT FIRST → STYLE SYSTEM SECOND → AUTOMATION THIRD**

对源文件自有内容，保留源结构和可见编号，把源层级映射到真实 Named Styles/outline，把源字体和版式配置到目标样式；对“格式自拟”或系统新增内容，才可使用独立的 Word 自动编号。样式系统可以提供导航和全局编辑能力，但不得替换源文件已有的编号文字。

## 3. 产物分层与新鲜度

一次已解析的完整流水线运行会写入 14 个文件。四项核心交付和其余技术证据必须分开理解：

| 层级 | 文件 | 约束 |
| --- | --- | --- |
| 核心交付 | `project_facts.json`、`投标项目复核表.xlsx`、`基础投标文件.docx`、`qa_report.json` | 同一次运行生成；不得用不同运行目录拼接 |
| 来源与事实证据 | `normalized_document.json`、`document.lines.txt`、`facts_review_packet.json`、`fact_gap_packet.json`、`semantic_candidate_results.json` | 用于追溯和复核；不是第二套事实来源 |
| 生成与复核 QA | `generation_report.json`、`source_format_qa.json`、`review_evidence_packet.json`、`review_evidence_qa.json`、`metadata.json` | 解释格式、证据检索和磁盘产物是否一致 |

流水线会在运行前清理已知的下游文件；输出目录不得被人工混入旧文件后再宣称结果完整。需要人工复核时，使用 `scripts/apply_resolution.py` 生成 reviewed ProjectFacts 和审计文件，再重新生成 XLSX、DOCX 和 QA；若使用 `fact_gap_packet.json`，只能通过 `--semantic-proposals` 走 source-backed 校验，并保留同批 `semantic_candidate_results.json`。不得直接编辑派生文件来“修正”事实。

Round 5.1 的 `source_numbering_qa.json`、`outline_tree.json`、`style_architecture_qa.json`、`editability_qa.json` 等是验收/调试证据，不加入用户运行时的 14 文件契约；它们必须写入新的验收轮次目录，不能覆盖历史轮次。

## 4. 状态机与报告用语

状态含义不可互换：

| 层级 | 状态 | 含义和后续动作 |
| --- | --- | --- |
| 文档解析 | `PARSED` | 可进入事实抽取；`OCR_REQUIRED`、`UNSUPPORTED_FORMAT`、`PARSE_ERROR` 均停止下游交付 |
| 字段事实 | `RESOLVED` | 已有证据支持的确定值；`NEEDS_REVIEW` 只能选择已有候选或保持未解决；`NOT_FOUND` 默认不补值，source-backed 候选须先经 Python 校验 |
| 技术 QA | `PASS` | 技术检查通过且无事实缺失/冲突。 |
| 技术 QA | `PASS_WITH_REVIEW` | 技术检查通过但仍有事实待核对/待补充。 |
| 技术 QA | `FAIL` | 产物或一致性检查失败。 |
| 流水线 | `READY_FOR_REVIEW` | QA 为 `PASS` 的可审阅包，不等于可提交投标。 |
| 流水线 | `REVIEW_REQUIRED` | QA 为 `PASS_WITH_REVIEW`，必须先处理人工复核项。 |
| 流水线 | `DELIVERY_FAILED` | 确定性失败或程序异常。 |

`PASS`、`READY_FOR_REVIEW` 和任何验收报告中的局部 `PASS` 都不得改写成 `READY_FOR_SUBMISSION`。当前系统不产生提交就绪状态。

## 5. WorkBuddy 语义复核边界

WorkBuddy 的语义处理分为两条受限路径：

- 人工复核消费 `facts_review_packet.json` 中的 `NEEDS_REVIEW` 字段，只能输出 `SELECT_CANDIDATE`（选择已有零基 `candidate_index`）或 `KEEP_UNRESOLVED`。
- 可选候选补充消费 `fact_gap_packet.json` 中的 `NEEDS_REVIEW`/`NOT_FOUND` 缺口，只能提交包含规范化文档精确 locator、匹配原文证据和值类型的 `SemanticCandidateProposal`；Python 验证后转为 Candidate 并重新解析。

模型不得输出自由文本事实值，不得重读整份文件后静默仲裁。64 项复核表的 evidence packet 只提供原文依据和候选片段；`FOUND`、`MULTIPLE_FOUND` 或 `NOT_APPLICABLE_CANDIDATE` 不是自动通过结论，最终判断仍由人工负责。

## 6. 文档生成和发布门禁

- 有可靠的“投标文件格式/响应文件格式”章节时，DOCX 以源文件格式模型为首选；没有可靠章节才使用 generic fallback。格式结构不能成为第二套事实来源。
- DOCX 生成器可以同时消费 `ProjectFacts`（仅事实内容）、`SourceFormatTemplate`/已校验源格式证据（结构与格式）和 `ReviewEvidence`（仅复核/证据展示）；只有 `ProjectFacts` 可以提供事实值填充。
- 源拥有的标题和正文列表默认使用 `SOURCE_LITERAL`：保留可见编号、标点、编号后空格和源文件中的序号间隔，不写入 `numPr`，并用真实 Heading/正文 Named Styles 提供导航、缩进和编辑能力。源编号不得因删除、误分类或插入另一段而自动重排；其 `SourceNumberToken` 需保留 `raw_prefix`、`normalized_level_hint`、`numbering_family`、`separator_after_prefix`、`source_locator`、`confidence` 和 `ownership`。
- 系统新增的“格式自拟”章节或说明内容可以使用独立的 `GENERATED_AUTO` Word 编号族；该编号族应从本次源格式证据学习约定，且不得参与源文字的编号序列。
- DOCX 生产渲染从全新的 `python-docx Document()` 开始；旧 OOXML 生成器只用于诊断。`word-safe` 静态扫描、python-docx 重开和 LibreOffice 渲染是必要检查，但不能替代桌面 Microsoft Word 正常打开。
- 最终发布前，所有目标 DOCX 必须在桌面 Word 中正常打开，无修复/恢复内容提示，并完成代表性页面、导航、可编辑性和编号插入检查。未完成时保持 `PENDING`/`AWAITING_MANUAL_CONFIRMATION`，不得发布。
- 投标人名称、报价、签章、银行账户、项目经理、企业资质等自有信息保持占位符；不自动报价、签字、盖章或提交投标。

## 7. 范围、变更和验收报告

- V1 范围已锁定。新增输入类型、字段、输出文件名、状态、事实来源边界、外部服务或基础设施，必须先形成 V2/范围变更并更新 Schema、测试和文档。
- 只要修改行为、跨文件契约、流程/工具链、测试策略或落盘格式，就必须在同一批改动中更新 `.agents/notes/implemented/<class>/` 下的决策笔记；纯排版、错别字和无歧义机械修复可免。
- 每个验收轮次必须使用新的 `acceptance/workspace/<case>/run_<id>/`，不得覆盖旧轮次。报告必须区分：测试结果、证据路径、已知限制、人工门禁、是否提交/发布。
- 涉及源格式或编号时，验收报告还必须分别记录可见编号前缀、标点、空格、序列依赖、Heading/TOC 导航、歧义标题防误升格、Named Style 编辑性和独立生成编号族；局部 `PASS` 不能掩盖桌面 Word 人工门禁。
- 验收报告是历史证据，不自动改变现行契约；报告中的局部 `PASS` 只能说明对应检查项通过。新报告应使用仓库相对路径；外部 fixture 若不可提交，必须记录来源、指纹或“不可复现”状态。历史报告中的绝对运行路径只作为当次环境记录，不得据此声称当前可复现。
- 默认保留用户现有未提交改动；除非用户明确要求，不执行 `git reset`、覆盖既有验收目录、提交、推送或发布。
- `dist/` 下的 ZIP 是可再生派生产物；字段、运行模块、规则、模板或治理文档变化后，旧包必须重新构建并通过 `validate_package.py`，不得把旧包当作当前发布包。

## 8. 合并前检查

在具备项目依赖的 Python 环境中，至少运行并记录：

```powershell
python scripts/check_env.py
python -m pytest -q --basetemp "tmp/pytest-<run-id>"
python scripts/export_schema.py
python scripts/package_skill.py --output "dist/tender-basic-1.0.0.zip"
python scripts/validate_package.py "dist/tender-basic-1.0.0.zip"
```

如果运行环境不支持桌面 Word，应明确记录自动化门禁通过、Word 人工门禁未执行，而不是降低门槛。外部 GitHub 版本可用于补充参考，但远程不可访问时，仓库本身必须仍能作为完整、可审计的依据。
