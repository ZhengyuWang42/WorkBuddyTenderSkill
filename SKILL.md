---
name: tender-basic
description: 从招标文件中提取项目基本事实，生成投标项目复核表、基础投标文件并执行交付 QA。
version: 1.0.0
---

# tender-basic

## 用途

本 Skill 用于“招投标基础解析与复核”。它处理一个文本型 PDF 或 DOCX，运行本地确定性流水线，生成可追溯的 ProjectFacts、复核表、基础投标文件和交付 QA。

项目范围、产物分层和发布门禁以 [PROJECT_GOVERNANCE.md](PROJECT_GOVERNANCE.md) 为准；
本 Skill 的目标是提供可审阅的事实基础，不是生成可以直接提交的完整标书。

以下请求应触发本 Skill：

- 解析这份招标文件
- 提取项目名称、项目编号等信息
- 生成投标项目复核表
- 生成基础投标文件
- 检查招标文件基本信息
- 整理投标前项目关键信息

纯知识问答（例如“什么是招标编号”）不触发文件流水线。

## 工作流

1. 确认一个主输入文件。支持 `.pdf` 和 `.docx`。多个文件无法判断主文件时，先请用户指定，不随机选择。
2. 为本次运行使用独立输出目录；不要把旧运行的派生产物拼入新结果。在 Skill 目录运行：

   ```powershell
   python scripts/run_pipeline.py "<input-file>" --output "<workspace-output>"
   ```

3. 读取流水线状态、`qa_report.json` 和 `metadata.json`，只报告实际状态和同一次运行的产物路径。
4. 对 `OCR_REQUIRED`、`UNSUPPORTED_FORMAT` 或 `PARSE_ERROR` 停止事实和文件交付；对 `DELIVERY_FAILED` 说明失败阶段和原因，不声称成功。
5. 对 `READY_FOR_REVIEW` 交付技术上完整的审阅包；对 `REVIEW_REQUIRED` 处理 `facts_review_packet.json` 的人工候选复核，或对 `fact_gap_packet.json` 提交经原文证据约束的候选建议，然后重新生成派生产物。
6. 无论自动化 QA 是否通过，都不得将结果描述为 `READY_FOR_SUBMISSION`；桌面 Word 正常打开、代表性页面和人工业务复核仍是发布前门禁。

## 语义复核边界

WorkBuddy 有两条受约束的语义处理路径：

- `facts_review_packet.json`：只处理 Python 标记为 `NEEDS_REVIEW` 的 ProjectFacts 字段，每个字段只能 `SELECT_CANDIDATE` 选择已有零基 `candidate_index`，或 `KEEP_UNRESOLVED`。
- `fact_gap_packet.json`：可针对 `NEEDS_REVIEW` 或 `NOT_FOUND` 提交 source-backed `SemanticCandidateProposal`；必须提供规范化文档中的精确 locator、匹配的原文证据和值类型，Python 验证通过后才转为 Candidate 并重新解析。

人工复核选择使用 `scripts/apply_resolution.py` 生成 reviewed ProjectFacts 和独立审计文件，再重新生成 XLSX、DOCX 并运行 QA。模型不得自由创建项目事实、自由填写无证据新值或改写证据。

复核模板的 64 项条款 evidence packet 是来源证据检索结果，不是 ProjectFacts 字段，也不自动产生合规结论。
`review_evidence_qa.json` 中的 `dynamic_review` 记录本轮动态复核项、来源要求索引和硬性门禁结果；该字段才是复核表实际行内容的来源说明。

Python 负责文档解析、候选发现、归一化、冲突检测、XLSX、DOCX 和 QA。Skill 不重新实现这些确定性逻辑，也不调用外部 LLM SDK。

基础投标文件优先使用原招标文件中确定性识别的“投标文件格式/响应文件格式”章节；
只有没有可用 source format 时才使用 generic fallback。复核表复制
`templates/投标项目复核表模板.xlsx`，ProjectFacts 仍是唯一事实来源。

## 动态复核项架构

复核表的实质行**由招标文件本身生成**，不是固定 64 行清单：

1. **Source Format First**：先确定源格式章节与页面几何。
2. **Source Requirements / Evidence**：`tender_basic/dynamic_requirements.py` 从句级来源片段
   建立有序要求索引（`SR####`），区分必核/高风险/一般要求并保留 locator、页码、条款号与原文。
3. **ProjectFacts**：23 个字段仍是唯一事实来源，只提供事实值与基准证据。
4. **Dynamic Review Items**：`tender_basic/dynamic_review.py` 按“要求类型 + 主题”归并同源条款，
   生成 `DR###` 复核项（来源要求、核验动作、通过标准、否决后果、来源依据、关联事实）。
   行动与通过标准不得出现源文件中不存在的概念（如数据库/中间件/国产化/培训）。
5. **Source-faithful editable DOCX**：复核行写回模板的标题块、模块列、结论列与签章块之间的检查区间，
   行数由来源决定；模板标题、列名、模块合并、签章块与人工字段保持不变。
6. **Delivery QA → Manual Word confirmation**：`qa_report.json` 校验模块列、签章块和动态行编号，
   `review_evidence_qa.json` 内嵌动态项与硬性门禁值；`rules/review_items.yaml` 只作为主题分类与召回辅助，
   不决定最终行数。

## DOCX 权威顺序与编号

DOCX 遵循 **Source Format First → Style System Second → Automation Third**：

- `ProjectFacts` 只提供事实值；`SourceFormatTemplate` 和已校验的源格式证据提供结构、层级、
  可见编号、标点、编号后空格、字体、版式、表格和固定文字；`ReviewEvidence` 只提供复核/
  证据展示；外部 Word fixture 只提供样式继承、导航和编辑性基础设施。
- 源文件自有标题、固定表单和正文列表默认是 `SOURCE_LITERAL`。保留源前缀、标点、空格和
  序号间隔，使用真实 Named Styles/outline 导航，但不为其写入自动编号，也不因分类错误而
  自动重排后续源编号。
- “格式自拟”、系统新增技术章节或说明可使用独立 `GENERATED_AUTO` 编号族；该编号族学习
  源格式约定但不参与或覆盖任何源文字编号。

SourceFormat、ReviewEvidence、fixture 文本和原始规范化文档都不得成为第二套事实来源；
只有 ProjectFacts 可以提供事实填充。

## V1 输出与边界

输入成功解析后，一次运行写入 14 个同批产物。四项核心交付是：

- `project_facts.json`
- `投标项目复核表.xlsx`
- `基础投标文件.docx`
- `qa_report.json`

其余同批技术产物为：

- `normalized_document.json`、`document.lines.txt`
- `facts_review_packet.json`、`fact_gap_packet.json`、`semantic_candidate_results.json`
- `generation_report.json`、`source_format_qa.json`
- `review_evidence_packet.json`、`review_evidence_qa.json`、`metadata.json`

当前能力是 Project Facts、人工复核工作簿、基础投标文件骨架和 QA，不是完整标书生成器。V1 不实现 OCR、正式企业模板映射、完整审标、评分项分析、数据库、Web 或 RAG。
复核表按来源条款动态生成（行数随文件变化），只做宽召回、来源证据和人工复核准备，不替代法律/商务/技术结论。

必须遵守：

- 不编造招标文件中不存在的项目事实。
- 人工 `NEEDS_REVIEW` 只能选择已有 Candidate，不能自由生成值；语义候选路径也必须经过原文 locator、证据和值类型校验。
- 无法确定时要求用户确认或保持未解决。
- `NOT_FOUND` 默认保持缺失；只有通过 `fact_gap_packet.json` 提交并经 Python 验证的 source-backed 候选，才可重新解析为事实。
- 不自动报价、不自动签字、不自动盖章、不自动提交投标。
- QA FAIL 时不得声明成功。
