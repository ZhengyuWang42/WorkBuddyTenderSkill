---
name: tender-basic
description: 从招标文件中提取项目基本事实，生成投标项目复核表、基础投标文件并执行交付 QA。
version: 1.0.0
---

# tender-basic

## 用途

本 Skill 用于“招投标基础解析与复核”。它处理一个文本型 PDF 或 DOCX，运行本地确定性流水线，生成可追溯的 ProjectFacts、复核表、基础投标文件和交付 QA。

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
2. 在 Skill 目录运行：

   ```powershell
   python scripts/run_pipeline.py "<input-file>" --output "<workspace-output>"
   ```

3. 读取流水线状态和 `qa_report.json`，只向用户报告实际状态和产物路径。
4. 对 `OCR_REQUIRED` 明确说明 V1 未启用 OCR，并停止后续交付。对 `DELIVERY_FAILED` 说明失败检查，不声称成功。
5. 对 `READY_FOR_REVIEW` 交付审核结果。对 `REVIEW_REQUIRED` 只读取 `facts_review_packet.json` 处理冲突字段。

## 语义复核边界

WorkBuddy 只处理 Python 标记为 `NEEDS_REVIEW` 的字段。每个字段只能返回：

- `SELECT_CANDIDATE`：选择已有的零基 `candidate_index`。
- `KEEP_UNRESOLVED`：保留未解决状态。

选择后使用 `scripts/apply_resolution.py` 生成 reviewed ProjectFacts 和独立审计文件，再重新生成 XLSX、DOCX 并运行 QA。模型不得自由创建项目事实、自由填写新值或改写证据。

Python 负责文档解析、候选发现、归一化、冲突检测、XLSX、DOCX 和 QA。Skill 不重新实现这些确定性逻辑，也不调用外部 LLM SDK。

## V1 输出与边界

成功路径输出：

- `project_facts.json`
- `投标项目复核表.xlsx`
- `基础投标文件.docx`
- `qa_report.json`

当前能力是 Project Facts、人工复核工作簿、基础投标文件骨架和 QA，不是完整标书生成器。V1 不实现 OCR、正式企业模板映射、完整审标、评分项分析、数据库、Web 或 RAG。

必须遵守：

- 不编造招标文件中不存在的项目事实。
- `NEEDS_REVIEW` 只能选择 Candidate，不能自由生成值。
- 无法确定时要求用户确认或保持未解决。
- `NOT_FOUND` 保持缺失。
- 不自动报价、不自动签字、不自动盖章、不自动提交投标。
- QA FAIL 时不得声明成功。
