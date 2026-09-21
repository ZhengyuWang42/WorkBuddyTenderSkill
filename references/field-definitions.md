# V1 字段定义

本文件定义 ProjectFacts 的唯一 23 个核心字段。字段名是稳定契约；中文别名只用于候选抽取，不改变字段身份。字段数量与 `tender_basic.models.FieldName`、`ProjectFields`、`rules/output_fields.yaml` 和 `schemas/project_facts.schema.json` 必须保持一致。

| 字段 | 含义 |
| --- | --- |
| `project_name` | 招标或采购项目的正式名称。 |
| `project_number` | 项目/采购项目自身的编号或编码。它不是招标文件编号。 |
| `tender_number` | 招标活动或招标文件的编号。它不是项目编号。 |
| `lot_name` | 当前标段、包或分包的名称。 |
| `lot_number` | 当前标段、包或分包的编号。 |
| `purchaser` | 招标人、采购人或项目建设/采购主体。 |
| `tender_agency` | 负责招标或采购代理工作的机构。 |
| `project_location` | 项目实施、建设、服务或交付地点。 |
| `procurement_scope` | 招标范围、采购内容或项目工作范围的原文摘要。 |
| `budget` | 文件明确给出的预算金额或采购预算。 |
| `max_price` | 最高限价、最高投标限价或控制价。 |
| `duration` | 工期、服务期限、供货期或履约期限。 |
| `quality_target` | 质量标准、质量目标、验收标准或服务质量要求。 |
| `bid_deadline` | 投标文件递交或提交的截止时间。 |
| `bid_open_time` | 开标或开启投标文件的时间。 |
| `bid_open_location` | 开标地点、地址或开标场所。开标方式不在本字段中另造字段。 |
| `bid_bond_amount` | 投标保证金或投标担保的金额。 |
| `bid_bond_form` | 投标保证金/投标担保的形式或提交方式。 |
| `consortium_allowed` | 文件对联合体投标是否接受或允许的明确结论。 |
| `procurement_method` | 公开招标、邀请招标、竞争性磋商等采购/招标方式。 |
| `bid_validity` | 投标文件有效期或投标有效期。 |
| `submission_method` | 投标/响应文件的递交、提交或开启方式。 |
| `electronic_platform` | 文件指定的电子交易、采购或投标平台。 |

## 关键编号区别

`rules/review_items.yaml` 中的复核条款不是额外的 ProjectFacts 字段；它们用于主题分类、来源检索和召回辅助，
不决定最终复核表行数，也不改变本字段字典，也不自动生成资格、商务、技术或合规结论。
复核表的实质行由 `tender_basic/dynamic_requirements.py` 与 `tender_basic/dynamic_review.py` 从句级来源要求生成。

### `project_number`

项目、采购项目或工程项目本身的编号/编码。来源标签为“项目编号”时，默认只作为该字段的候选，不自动转为 `tender_number`。

### `tender_number`

招标活动、招标文件或招标公告对应的编号。来源标签为“招标编号”或“招标文件编号”时，作为该字段的候选。

### `lot_number`

标段、包、分包或标包的编号。它既不是项目编号，也不是招标编号。

同一文件同时出现这些编号时，三者必须分别保存；值相同也不能因此合并字段。

### `lot_name`

当前标段/包的名称（如“三标段”）。单标段项目通常不用“标段名称：”标签，而是通过
“合同估算价：三标段…万元”“3.1 三标段投标人资格要求”“投标保证金的金额：三标段…”
或封面独立标段标题说明所属标段；`fact_extractor` 只从这些来源证据中取值，绝不从文件名、
路径或案例标识推断。指向“同一标段/每个标段/各标段”等泛指表述不作为候选；
文件确实没有标段时保持 `NOT_FOUND`，不编造标段名。
