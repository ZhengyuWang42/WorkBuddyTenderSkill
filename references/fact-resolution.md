# Fact Resolution Principles

本阶段由 `tender_basic/fact_resolver.py` 实现，接收带证据的候选事实并按字段独立生成 `RESOLVED`、`NEEDS_REVIEW` 或 `NOT_FOUND`。以下原则是当前 resolver 的不变量，而不是未来规划。

1. 所有 `RESOLVED` fact 必须来自至少一个 `CandidateFact`。
2. 不允许凭空补字段；没有可信候选时使用 `NOT_FOUND`。
3. 多来源给出相同值时，可以作为相互印证并提高最终置信度的输入。
4. 明显冲突、语义歧义或置信度不足必须标记 `NEEDS_REVIEW`。
5. `source_priority.yaml` 只能提供来源优先级提示，不能掩盖真实冲突，也不能无条件覆盖低优先级证据。
6. 原始 `evidence_text` 和结构化 `locator` 必须保留在候选事实中。
7. `NOT_FOUND` 比猜测一个值更正确。

## 字段独立性

`project_number`、`tender_number` 和 `lot_number` 是三个独立字段。模型或 resolver 不得仅凭标签相似、值格式相似或文件上下文相近而合并它们。

## 与格式和复核证据的边界

Resolver 只决定 ProjectFacts 的事实值和字段状态。SourceFormatTemplate/源格式证据
可以决定这些事实在 DOCX 中的结构和呈现位置，但不能提供替代事实值；ReviewEvidence
只保留条款证据和人工复核状态，不生成 ProjectFacts 或自动合规结论。
