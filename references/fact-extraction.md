# Fact Extraction V1

事实抽取只消费 `normalized_document.json`，不重新打开原始 PDF 或 DOCX。
它先按字段别名生成带 locator 和 evidence 的 `CandidateFact`，再进行比较所需的
归一化，最后逐字段生成现有 `ProjectFacts` Contract。

## Candidate methods

当前只支持四种确定性发现方法：

1. `table_label_exact`：表格标签精确匹配，取同一行右侧最近的非空单元格。
2. `label_value_same_line`：标签与冒号和值在同一段落或 PDF block。
3. `label_value_next_line`：标签单独占一条记录时，只查看紧邻下一条文本记录。
4. `keyword_window`：正文中“字段为/是/指/包括值”的小窗口，以及联合体明确
   否定短语。

每个候选保留原始 `value`、`evidence_text`、`locator`、来源类型和方法。

## Confidence and normalization

基础 confidence 只是稳定的排序信号，不是概率：表格 0.98、同行 0.95、下一条
文本记录 0.85、关键词窗口 0.70。文本、金额、日期时间、工期、布尔值和编号只
做确定性比较归一化；候选原文不被覆盖。金额使用 Decimal 计算，工期不把月份
换算成天，编号不删除连字符、斜杠或括号。

## Resolution

每个字段独立处理：没有可信候选是 `NOT_FOUND`；只有一个候选或多个归一化后相同
的候选是 `RESOLVED`；多个不同归一化值是 `NEEDS_REVIEW`。所有最终结果保留完整
候选列表。`source_priority.yaml` 只用于排序和轻微 confidence 调整，不能覆盖
真实冲突。

单候选还必须通过确定性门槛：表格候选至少 0.95、同行候选至少 0.90、下一条文本
候选至少 0.85，且下一条文本的值不能本身像另一个字段标签。单独的
`keyword_window` 永不自动解决；只有它与不同 locator 的高质量候选归一化后一致时，
才可按多来源一致规则解决。

## Review packet

`facts_review_packet.json` 只包含 `NEEDS_REVIEW` 字段及其候选证据，不复制完整的
normalized document，也不执行人工或 WorkBuddy 仲裁。

事实抽取只为 ProjectFacts 建立事实候选。它不决定 DOCX 的源结构、版式或可见编号；
这些由 SourceFormatTemplate/已校验源格式证据负责。64 项 ReviewEvidence 也不属于
事实抽取结果，不会因证据检索状态而自动产生合规结论。

## CLI exit codes

`extract_facts.py` 返回 `0` 表示已生成两个输出文件，即使其中有
`NEEDS_REVIEW` 或 `NOT_FOUND`。输入 JSON 无效、状态不可抽取或 Contract 校验失败
返回 `3`；输入状态为 `OCR_REQUIRED` 返回 `4`，且不会生成空的 ProjectFacts。
