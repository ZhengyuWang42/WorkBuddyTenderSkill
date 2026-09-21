# V1 Output Generation

XLSX 和 DOCX builder 只接受已经通过 Pydantic 校验的 `ProjectFacts` 作为事实值输入，
不读取原始 PDF、DOCX 或 `normalized_document.json` 来重新抽取事实。DOCX 还可以消费
`SourceFormatTemplate`/已校验的源格式证据来决定结构和格式，并可消费 `ReviewEvidence`
来展示复核证据；这两者都不是事实值来源。23 个字段的定义以模型、输出规则和 JSON
Schema 为准；复核条款不是第二套字段或事实来源。

## XLSX

`build_review_xlsx.py` 复制 `templates/投标项目复核表模板.xlsx`，在允许的顶部字段写值，
主 Sheet 保持为 `投标项目复核表`。模板的标题块、列名、`复核模块` 列、风险等级、
初审/二次/三次复核、备注以及末尾评审意见区域都保留。

复核表的实质行由 `tender_basic/dynamic_review.py` 从招标文件来源条款动态生成：

- 行数由源文件决定（`DR###` 复核项数目），不再是固定 64 行；
- `build_review_workbook(..., dynamic_plan=...)` 用动态行替换第 9 行到签章块之间的检查区间，
  并把签章块移动到最后一个复核项之后；不传 `dynamic_plan` 时保留历史固定行行为；
- 每个动态行写入来源要求、核验动作、通过标准、否决后果、来源依据（页码/条款/原文片段/源条款 ID）
  以及关联 ProjectFacts 值，初审结论/二次复核列为人工填写状态；
- `review_evidence_qa.json` 的 `dynamic_review` 内嵌动态项、来源要求索引摘要和硬性门禁值；
- `rules/review_items.yaml` 只作为主题分类与召回辅助，不决定最终行数。

最终用户工作簿不再要求旧的技术型 `项目复核表`、`字段证据`、`解析异常` 三 Sheet。
`project_facts.json` 和 `facts_review_packet.json` 是事实与证据的技术交付物，避免
破坏用户模板布局。复核行只承载来源证据和人工复核入口，不自动产生合规结论。

## DOCX

`build_bid_docx.py` 生成 A4 基础文件。若 `format_extractor.py` 在原招标文件中找到
确定性的 `投标文件格式`/`响应文件格式` 章节，则按该章节的标题、固定文字、表单和
表格顺序生成骨架；找不到或无法可靠确定边界时，才使用现有 generic skeleton
fallback。文档元数据记录 `format_source=SOURCE_DOCUMENT` 或
`format_source=GENERIC_FALLBACK`。

它不生成技术方案、商务承诺或完整标书内容。

### 编号所有权

- 源文件自有标题和正文列表默认使用 `SOURCE_LITERAL`：可见前缀、标点、编号后空格和源
  文件的序号间隔原样保留；Heading/Body List Named Styles 负责导航、缩进和样式编辑，
  源段落不依赖 `numPr`。
- “格式自拟”等系统新增内容才可使用独立的 `GENERATED_AUTO` Word 编号族。自动编号可以
  学习源格式约定，但不得重编号或覆盖任何源文件自有段落。

## 状态展示

- `RESOLVED` 使用 `resolved_value`。
- `NEEDS_REVIEW` 在 XLSX 使用 `【待核对】`，在 DOCX 使用 `【待人工确认】`。
- `NOT_FOUND` 在 XLSX 使用 `【待补充】`，在 DOCX 使用 `【待补充】`。

两个 builder 都保留 `project_number` 与 `tender_number` 的独立字段，不从其他字段
复制或推断值。输出文件生成后会立即重新打开验证。
