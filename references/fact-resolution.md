# Fact Resolution Principles

本阶段只记录未来 resolver 应遵守的原则，不实现 resolver。

1. 所有 `RESOLVED` fact 必须来自至少一个 `CandidateFact`。
2. 不允许凭空补字段；没有可信候选时使用 `NOT_FOUND`。
3. 多来源给出相同值时，可以作为相互印证并提高最终置信度的输入。
4. 明显冲突、语义歧义或置信度不足必须标记 `NEEDS_REVIEW`。
5. `source_priority.yaml` 只能提供来源优先级提示，不能掩盖真实冲突，也不能无条件覆盖低优先级证据。
6. 原始 `evidence_text` 和结构化 `locator` 必须保留在候选事实中。
7. `NOT_FOUND` 比猜测一个值更正确。

## 字段独立性

`project_number`、`tender_number` 和 `lot_number` 是三个独立字段。模型或未来 resolver 不得仅凭标签相似、值格式相似或文件上下文相近而合并它们。
