# V1 Output Generation

XLSX 和 DOCX builder 只接受已经通过 Pydantic 校验的 `ProjectFacts`，不读取原始
PDF、DOCX 或 `normalized_document.json`，也不重新执行事实抽取。

## XLSX

`build_review_xlsx.py` 生成三个固定 Sheet：

1. `项目复核表`：20 个字段、状态、置信度、来源位置和人工填写栏。
2. `字段证据`：每个 `CandidateFact` 一行，保留原始证据和 locator。
3. `解析异常`：只列 `NEEDS_REVIEW` 和 `NOT_FOUND`。

## DOCX

`build_bid_docx.py` 生成 A4 基础工作骨架，包括封面、项目基本信息表、投标函、
资格审查文件、商务响应文件、技术响应文件、报价文件、其他材料和签字盖章提示。
它不生成技术方案、商务承诺或完整标书内容。

## 状态展示

- `RESOLVED` 使用 `resolved_value`。
- `NEEDS_REVIEW` 在 XLSX 使用冲突提示，在 DOCX 使用 `【待人工确认】`。
- `NOT_FOUND` 在 XLSX 使用 `【未找到】`，在 DOCX 使用 `【待补充】`。

两个 builder 都保留 `project_number` 与 `tender_number` 的独立字段，不从其他字段
复制或推断值。输出文件生成后会立即重新打开验证。
