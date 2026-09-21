# tender-basic / WorkBuddy 招投标 Skill

`tender-basic` 是一个可封装为 WorkBuddy Skill 的轻量级招投标基础解析与复核工具。

项目范围、状态机、产物分层和发布门禁以 [项目治理约束](PROJECT_GOVERNANCE.md) 为准；
MVP 的输入/字段/非目标基线见 [MVP_SCOPE.md](MVP_SCOPE.md)。

DOCX 源格式生成默认使用 **WORD_SAFE**：全新 `Document()`、公开 python-docx
段落/表格/分节 API；旧定位 OOXML 渲染器仅供诊断。
参见 [Word-safe 生成约束](references/word-safe-generation.md)。桌面 Microsoft Word
手工正常打开确认仍是验收门槛，静态检查和 LibreOffice 渲染不能代替它。

DOCX 遵循 **Source Format First → Style System Second → Automation Third**：
`ProjectFacts` 只提供事实值，已校验的 `SourceFormatTemplate`/源格式证据提供结构与格式，
`ReviewEvidence` 只提供可追溯复核证据，外部 fixture 只提供 Word 样式/编辑性基础设施。
源文件自有标题和正文列表保留可见编号、标点、空格和序号间隔，使用 Named Styles/outline
实现导航但不依赖自动编号；“格式自拟”等系统新增内容才使用隔离的自动编号族。

## V1 支持

- 输入一个文本型 PDF 或 DOCX。
- 确定性解析、候选事实抽取、冲突暴露和 ProjectFacts 校验。
- 维护 23 个 ProjectFacts 字段；复核表的复核行由招标文件来源条款动态生成（`rules/review_items.yaml` 只作主题分类/召回辅助，不决定行数），不自动给出合规结论。
- 生成 `project_facts.json`、`投标项目复核表.xlsx`、`基础投标文件.docx` 和 `qa_report.json`。
- 基础投标文件优先沿用原招标文件的确定性格式章节；复核表复制
  `templates/投标项目复核表模板.xlsx`，保留用户复核布局。
- 这类格式章节只决定内容的 WHERE/HOW/STYLE，不提供事实值；事实填充仍只能来自同一次运行的 `ProjectFacts`。
- 对扫描 PDF 返回 `OCR_REQUIRED`，V1 不实现 OCR。

V1 不包含 OCR、Web、数据库、RAG、外部 LLM SDK、正式企业模板映射或完整标书生成。

## 安装依赖

需要 Python 3.11+：

```powershell
python -m pip install -r requirements.txt
```

## 本地运行

```powershell
python scripts/run_pipeline.py "<招标文件.pdf或docx>" --output "<输出目录>"
```

输入成功解析后，一次运行会写入 14 个同批产物：4 个核心交付物
（`project_facts.json`、`投标项目复核表.xlsx`、`基础投标文件.docx`、`qa_report.json`），
以及规范化文档、事实复核、格式生成和证据 QA 等技术产物。完整清单和混用旧运行结果的限制见
[项目治理约束](PROJECT_GOVERNANCE.md)。

## WorkBuddy 安装

将打包后的 Skill 解压到 WorkBuddy Skill 目录，例如 Windows：

```text
%USERPROFILE%\.workbuddy\skills\tender-basic
```

然后按 WorkBuddy 的方式重载或重启 Skill。本文不假设自动安装已经完成。

WorkBuddy 只负责调用流水线和处理已有候选之间的语义复核；不得自由创建事实值。
`基础投标文件.docx` 是基础骨架，不是可直接提交的完整标书。

## 安全原则

ProjectFacts 是 XLSX、DOCX 和 QA 的唯一事实来源。人工复核时 `NEEDS_REVIEW` 只能选择已有 Candidate；`NOT_FOUND` 默认不补值，只有经精确 locator、原文证据和值类型校验的 source-backed 语义候选才能重新解析。不自动报价、签字、盖章或提交投标。QA 失败时不得声称交付成功。
