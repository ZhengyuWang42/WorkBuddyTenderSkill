# case_002 Real-case Root Cause

## 证据范围

本报告只比较 `acceptance/workspace/case_002/run_2` 的 `project_facts.json`、对应 normalized document，以及用户提供的人工复核/填充 DOCX。没有读取或建立 Gold。人工 DOCX 用于核对字段和表单结构，不产生代码硬编码。

## 逐字段比较

| 字段 | run_2 结果 | 人工复核/源文档可确认内容 | 分类 | 根因 |
|---|---|---|---|---|
| project_name | NEEDS_REVIEW；明确名称与“见投标人须知前附表”、格式表格空占位冲突 | 招标文件封面/格式表给出“营收系统整合和硬件系统升级项目” | SHOULD_HAVE_RESOLVED | 没有对明确项目名称标签、表格值和多行标题做确定性归并；空占位候选未过滤 |
| project_number | NEEDS_REVIEW；同时捕获招标人项目编号和招标代理项目编号，但都竞争同一字段 | 人工 DOCX 明确分别保留招标人项目编号和招标代理项目编号 | SHOULD_HAVE_RESOLVED | 编号 ownership 未实现；缺少 owner-side 与 agent-side label family，导致两个事实冲突后没有分别落位 |
| tender_number | NOT_FOUND | 人工 DOCX/源文档明确给出招标代理项目编号 | SHOULD_HAVE_RESOLVED | 代理项目编号没有映射到 tender_number；resolver 只尝试 project_number |
| purchaser | NEEDS_REVIEW；实体名称与章节引用/错位单字候选冲突 | 源文档明确招标人为西安市自来水有限公司 | SHOULD_HAVE_RESOLVED | “招标人”与“采购人”族虽部分支持，但没有过滤表格排版拆出的“名”，也没有提高完整机构名候选权重 |
| tender_agency | NEEDS_REVIEW；同一代理机构实体出现两次，同时有章节引用/错位“名” | 源文档明确招标代理机构名称 | SHOULD_HAVE_RESOLVED | 代理机构 alias 和多次同值合并不足；表格换行噪声未清洗 |
| project_location | NEEDS_REVIEW；“西安市内”和系统建设地点机构名称并列 | 源文档项目地点明确为西安市内 | SHOULD_HAVE_RESOLVED | 没有覆盖“项目地点/实施地点/建设地点”语义族，也没有按字段标签优先于正文地点语义 |
| procurement_scope | NEEDS_REVIEW；招标范围长值被截断，另有“见投标人须知前附表/功能要求”噪声 | 源文档给出系统整合和硬件升级的招标范围 | SHOULD_HAVE_RESOLVED | 缺少 labeled multiline value；未对长值续行，普通“建设内容/功能要求”被当成同字段候选 |
| budget | NOT_FOUND | 未发现独立预算金额 | REASONABLE_NOT_FOUND | 没有把最高投标限价错误复制为预算，事实隔离正确 |
| max_price | RESOLVED = 人民币 7507785.65 元及分项限价说明 | 源文档明确最高投标限价 | CORRECT_RESOLVED | 明确金额候选、类型和标签均成立；应保持与 budget 独立 |
| duration | NOT_FOUND | 人工复核表给出实施周期为合同签订后 18 个月内完成并投入试运行 | SHOULD_HAVE_RESOLVED | 没有覆盖“实施周期” alias；表格中的字段被保留为 table text，未进入字段候选 |
| quality_target | NEEDS_REVIEW；明确质量标准与验收条款大量候选冲突 | 源文档明确质量标准为符合国家现行相关规定及验收规范的合格标准 | SHOULD_HAVE_RESOLVED | 没有覆盖“质量标准”语义族；验收细节与总质量标准没有分层，候选质量排序不足 |
| bid_deadline | RESOLVED = 2026-04-14 09:30 | 源文档同一递交截止时间 | CORRECT_RESOLVED | 具体 datetime 候选且来源明确 |
| bid_open_time | RESOLVED = 2026-04-14 09:30 | 源文档同一开标时间 | CORRECT_RESOLVED | 具体 datetime 候选且多处一致 |
| bid_open_location | NEEDS_REVIEW；两个地点文本是同一平台但一个被截断 | 源文档明确开标地点为西安市综改试验区国企招标集采交易平台（招采通平台） | SHOULD_HAVE_RESOLVED | PDF block 截断/括号清洗未归一，未按同一标签和前缀合并 |
| bid_bond_amount | RESOLVED = “投标保证金的形式：本项目接受所有符合国家相关规定形式的保证金” | 源文档只明确保证金形式，未给出可靠金额 | WRONG_RESOLVED | amount validator 缺失；labeled next-line 把“保证金”后的完整下一行无条件当金额 |
| bid_bond_form | NOT_FOUND | 源文档明确接受符合国家相关规定形式的保证金 | SHOULD_HAVE_RESOLVED | 形式候选错误归入 amount 后没有回流到 bid_bond_form；字段类型/语义路由缺失 |
| consortium_allowed | RESOLVED = False；多处“不接受联合体投标”一致 | 源文档多处明确不接受联合体 | CORRECT_RESOLVED | 多处结构化证据一致 |
| procurement_method | NEEDS_REVIEW；正文明确“招标方式为公开招标” | 源文档给出公开招标 | SHOULD_HAVE_RESOLVED | 公开招标只作为 keyword_window，缺少明确“招标方式”标签候选和稳定枚举校验 |

## Root Cause 归纳

1. **金额字段污染是 Release Critical**：`bid_bond_amount` 没有 money parser，导致“形式”整句进入 amount；需要金额候选白名单和形式字段回流。
2. **编号 ownership 缺失**：`招标人项目编号` 与 `招标代理项目编号` 同时被当成 project_number，tender_number 因此 NOT_FOUND。
3. **表格没有成为结构化输入**：实施周期等关键字段在人工 DOCX 表格中明确，但当前 PDF 表格 flatten 后只作为普通段落，无法稳定提取字段或重建 source-format 表格。
4. **通用 alias 不完整**：实施周期、质量标准、项目地点/系统建设地点、招标范围等没有进入语义族，造成应召回字段 NOT_FOUND/NEEDS_REVIEW。
5. **长值和排版噪声处理不足**：表格换行的“名”、地点括号截断、长范围 block 截断，均缺少结构化续接和同值归并。
