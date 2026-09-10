# WorkBuddy 语义复核

Python 先生成 `facts_review_packet.json`。WorkBuddy 只针对其中的 `NEEDS_REVIEW` 字段作独立判断，不重新解释整份招标文件。

V1 允许两种操作：

- `SELECT_CANDIDATE`：选择已有候选的零基 `candidate_index`。
- `KEEP_UNRESOLVED`：保留 `NEEDS_REVIEW`。

禁止输出自由文本事实值。选择后由 `scripts/apply_resolution.py` 校验字段状态、候选索引和候选来源，生成 `project_facts.reviewed.json` 与 `resolution_audit.json`。随后只重新运行 XLSX、DOCX 和 QA，不重新解析原始文档。

如果两个候选都合理且无法仅凭证据安全判断，应要求用户确认，而不是猜测。原始 `project_facts.json` 保持不变。
