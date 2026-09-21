# WorkBuddy 语义复核

Python 先生成 `facts_review_packet.json`。本文件描述人工候选复核路径：WorkBuddy 只针对其中的 `NEEDS_REVIEW` 字段作独立判断，不重新解释整份招标文件。

V1 允许两种操作：

- `SELECT_CANDIDATE`：选择已有候选的零基 `candidate_index`。
- `KEEP_UNRESOLVED`：保留 `NEEDS_REVIEW`。

禁止输出自由文本事实值。选择后由 `scripts/apply_resolution.py` 校验字段状态、候选索引和候选来源，生成 `project_facts.reviewed.json` 与 `resolution_audit.json`。随后只重新运行 XLSX、DOCX 和 QA，不重新解析原始文档。

如果两个候选都合理且无法仅凭证据安全判断，应要求用户确认，而不是猜测。原始 `project_facts.json` 保持不变。

该人工复核只改变 ProjectFacts 中已有 `NEEDS_REVIEW` 字段的受限状态；它不处理 64 项复核证据包中的条款，不把证据检索结果转换为自动合规结论。应用结果后必须在同一独立输出目录重新生成 XLSX、DOCX 和 QA，并以新的 `metadata.json` 和 `qa_report.json` 作为结果依据。

如果确定性候选发现遗漏了原文中的字段，可使用 `fact_gap_packet.json` 提交 source-backed `SemanticCandidateProposal`；该路径必须提供精确 locator、匹配原文证据和值类型，并由 Python 验证后重新解析，不能直接写入自由文本事实。

## 与 DOCX 格式的边界

WorkBuddy 的复核动作只影响受约束的 ProjectFacts 候选处理。DOCX 的结构、源标题层级、
可见编号、标点、空格、版式和表格来自已校验的 SourceFormat 证据；64 项
ReviewEvidence 只用于可追溯证据展示。SourceFormat、ReviewEvidence、fixture 文本和
WorkBuddy 自身都不能提供第二套事实填充值，只有 ProjectFacts 可以填入事实。
