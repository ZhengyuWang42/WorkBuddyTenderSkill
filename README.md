# tender-basic

`tender-basic` 是一个可封装为 WorkBuddy Skill 的轻量级招投标基础解析与复核工具。

## V1 支持

- 输入一个文本型 PDF 或 DOCX。
- 确定性解析、候选事实抽取、冲突暴露和 ProjectFacts 校验。
- 生成 `project_facts.json`、`投标项目复核表.xlsx`、`基础投标文件.docx` 和 `qa_report.json`。
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

普通结果会写入七个主要产物：规范化文档 JSON、文本行视图、ProjectFacts、复核包、XLSX、DOCX 和 QA 报告。

## WorkBuddy 安装

将打包后的 Skill 解压到 WorkBuddy Skill 目录，例如 Windows：

```text
%USERPROFILE%\.workbuddy\skills\tender-basic
```

然后按 WorkBuddy 的方式重载或重启 Skill。本文不假设自动安装已经完成。

## 安全原则

ProjectFacts 是 XLSX、DOCX 和 QA 的唯一事实来源。`NEEDS_REVIEW` 只能选择已有 Candidate，`NOT_FOUND` 不补值；不自动报价、签字、盖章或提交投标。QA 失败时不得声称交付成功。
