# case_001 Real-case Root Cause

## 证据范围

本报告只比较 `acceptance/workspace/case_001/run_2` 的 `project_facts.json`、对应 normalized document，以及用户提供的人工复核 DOCX。没有读取或建立 Gold。人工复核 DOCX 只作为事实核对和输出结构辅助证据，不作为代码中的特例。

## 逐字段比较

| 字段 | run_2 结果 | 人工复核/源文档可确认内容 | 分类 | 根因 |
|---|---|---|---|---|
| project_name | NEEDS_REVIEW；项目名称候选被截断且与“见供应商须知前附表”冲突 | 响应文件封面、公告和复核稿均给出完整项目名称 | SHOULD_HAVE_RESOLVED | 同一事实在公告、须知前附表、格式封面多处出现；当前 resolver 没有对明确项目标题和多行项目名加权，也缺少安全的多行值拼接 |
| project_number | NEEDS_REVIEW；多个位置给出同一编号，另有空白格式占位 | 格式封面和公告给出同一项目编号 | SHOULD_HAVE_RESOLVED | 空白“项目编号：”占位被当成候选，稀释了同值的明确候选；缺少编号候选质量和空值过滤 |
| tender_number | NOT_FOUND | 文档未提供独立“招标编号/代理项目编号”事实 | REASONABLE_NOT_FOUND | 没有将项目编号越权复制为招标编号，符合 ownership 原则 |
| purchaser | NEEDS_REVIEW；明确名称与“见供应商须知前附表/定义性正文”冲突 | 复核稿和格式正文给出采购人名称 | SHOULD_HAVE_RESOLVED | 没有优先选择带“名称：”的连续标签值；定义性正文被错误地与实体名称同权 |
| tender_agency | NEEDS_REVIEW；明确代理机构名称与章节引用、定义性正文冲突 | 源文档明确给出采购代理机构名称 | SHOULD_HAVE_RESOLVED | 同 purchaser；缺少机构实体值优先级和引用短语过滤 |
| project_location | NEEDS_REVIEW；“见供应商须知前附表”与“周口市郸城县”并列 | 复核稿/采购需求进一步明确交货地点为周口市郸城县石槽泵站 | SHOULD_HAVE_RESOLVED | 未覆盖“项目地点/交货地点/供货地点”语义族；没有合并标签后的连续行，也没有区分章节引用和实体地点 |
| procurement_scope | NEEDS_REVIEW；采购内容、采购需求引用和格式占位互相冲突 | 公告及复核稿明确为一体化泵站及其伴随服务 | SHOULD_HAVE_RESOLVED | 候选来自多个章节但没有进行同义归并；缺少对明确“采购内容/采购范围”标签和跨行值的优先级 |
| budget | NOT_FOUND | 未发现独立预算金额，只有最高限价 | REASONABLE_NOT_FOUND | 没有把最高限价错误复制为预算，符合两个金额事实独立的要求 |
| max_price | NEEDS_REVIEW；阿拉伯数字和大写金额语义相同但未归一 | 源文档明确最高限价为 3100000 元（不含税） | SHOULD_HAVE_RESOLVED | 金额规范化未把小写金额、大写金额和税务说明归并为同一候选 |
| duration | NEEDS_REVIEW；多个“供货期”候选包含 30 日历天，也包含章节引用/格式占位 | 复核稿和采购需求均明确供货期 30 日历天 | SHOULD_HAVE_RESOLVED | 未覆盖“供货期”到 duration 的语义族；引用短语与实际值未过滤，未做同值去重 |
| quality_target | NEEDS_REVIEW；明确质量要求与章节引用、截断长值冲突 | 复核稿和采购需求明确质量达到国家及行业标准、规范和询比文件要求 | SHOULD_HAVE_RESOLVED | 未覆盖“质量要求/质量标准/供货质量”语义族；PDF block 截断后没有安全续接 |
| bid_deadline | RESOLVED = “同提交响应文件截止” | 源文档明确响应文件截止日期时间 | WRONG_RESOLVED | 没有 reference phrase validator；保证金递交截止标签被当作投标截止时间直接取值 |
| bid_open_time | RESOLVED = “同提交响应文件截止时间” | 源文档明确开启日期时间 | WRONG_RESOLVED | 没有 reference phrase validator，也没有在存在明确开启时间时优先选择明确 datetime |
| bid_open_location | NOT_FOUND | 复核稿保留了电子交易平台和远程开标室/地址信息 | SHOULD_HAVE_RESOLVED | 未覆盖“开标地点/递交地点/响应文件递交地点”，且长地点跨 block 被截断 |
| bid_bond_amount | NOT_FOUND | 人工复核稿要求提交前人工确认，源文档未形成可靠金额 | REASONABLE_NOT_FOUND | 未将保证金形式短语伪造为金额；本字段当前缺少可靠数值证据 |
| bid_bond_form | NOT_FOUND | 源文档主要表达为按平台/文件要求或人工确认，未形成稳定可填的单一形式 | REASONABLE_NOT_FOUND | 没有把无法确定的保证金形式猜成电子/转账等具体形式 |
| consortium_allowed | NEEDS_REVIEW = “不接受” | 源文档明确“不接受联合体响应” | SHOULD_HAVE_RESOLVED | 只有 keyword_window 候选，没有把“联合体 + 不接受”作为确定性结构证据 |
| procurement_method | NOT_FOUND | 文件形态为询比文件，但未发现稳定的独立采购方式标签值 | REASONABLE_NOT_FOUND | 当前没有把文件标题或普通正文关键词直接当作采购方式，避免语义猜测 |

## Root Cause 归纳

1. **值类型约束缺失**：date/time reference phrase 没有拒绝，导致截止时间和开启时间出现错误 RESOLVED。
2. **标签语义族覆盖不足**：供货期、交货地点、质量要求、采购人/代理机构等明确字段没有统一 alias family。
3. **PDF block 结构损失**：长项目名、地点、质量值被拆断，现有 extractor 只取单 block；未提供 `labeled_multiline_value` 和安全停止边界。
4. **候选质量排序不足**：章节引用“见供应商须知前附表”、定义性解释、格式空白占位与真实实体值同权，造成大量 NEEDS_REVIEW。
5. **编号/金额事实应保持独立**：本 case 没有招标编号和预算，当前未误填，这部分属于需要保留的正确防护。
