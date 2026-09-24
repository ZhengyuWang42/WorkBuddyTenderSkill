# Round-4 rendered-component provenance — case_001

* build: `v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook4`
* workbook: `acceptance\workspace\case_001\v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook4\投标项目复核表.xlsx` (sha256 `be084b7aeefd24cd…`)
* invariant: **SEMANTIC OWNERSHIP MUST SURVIVE RENDERING**
* review rows: 46 (+3 non-bidder-facing background items)
* rendered components: 357 (0 unverified)
* rendered concern mismatches: 0
* **ROUND4 VERDICT: PASS** (25/25 checks, 19/19 fixtures)

## Rendered-component mismatch buckets

| bucket | count |
| --- | --- |
| rendered_component_concern_mismatch_total | 0 |
| rendered_evidence_summary_concern_mismatch | 0 |
| rendered_failure_consequence_concern_mismatch | 0 |
| rendered_linked_fact_concern_mismatch | 0 |
| rendered_numeric_statement_concern_mismatch | 0 |
| rendered_pass_criterion_concern_mismatch | 0 |
| rendered_preparation_material_concern_mismatch | 0 |
| rendered_review_check_concern_mismatch | 0 |
| rendered_scoring_guidance_concern_mismatch | 0 |
| rendered_source_requirement_concern_mismatch | 0 |

## Rendered-output gate

| check | ok | detail |
| --- | --- | --- |
| delivered_rows_bound_to_plan_items | PASS | 46/46 delivered review rows bound to plan items |
| rendered_cell_equals_component_projection | PASS | 46/46 delivered D cells are the exact projection of their verified components |
| rendered_component_ownership_verified | PASS | 357 rendered components verified concern-owned |
| rendered_component_concern_mismatch_total_zero | PASS | total rendered-component concern mismatch is 0 |
| rendered_source_requirement_concern_mismatch | PASS | SOURCE_REQUIREMENT mismatch count is 0 |
| rendered_review_check_concern_mismatch | PASS | REVIEW_CHECK mismatch count is 0 |
| rendered_pass_criterion_concern_mismatch | PASS | PASS_CRITERION mismatch count is 0 |
| rendered_preparation_material_concern_mismatch | PASS | PREPARATION_MATERIAL mismatch count is 0 |
| rendered_failure_consequence_concern_mismatch | PASS | FAILURE_CONSEQUENCE mismatch count is 0 |
| rendered_scoring_guidance_concern_mismatch | PASS | SCORING_GUIDANCE mismatch count is 0 |
| rendered_numeric_statement_concern_mismatch | PASS | NUMERIC_STATEMENT mismatch count is 0 |
| rendered_evidence_summary_concern_mismatch | PASS | EVIDENCE_SUMMARY mismatch count is 0 |
| rendered_linked_fact_concern_mismatch | PASS | LINKED_FACT mismatch count is 0 |
| every_rendered_component_present_in_final_cell | PASS | 338 rendered components of 46 bidder-facing rows are displayed by a final workbook cell |
| view_cells_repeat_rendered_components | PASS | clause/mandatory view cells repeat the concern-owned rendered text |
| forbidden_retention_wording_absent | PASS | no cell presents the 12-month release period as the project warranty or the 5% retention money as a payment/scoring ratio |
| final_cell_text_owned_by_concern | PASS | 46/46 delivered cells name only concepts their concern owns |
| project_warranty_is_24_months | PASS | project warranty renders as 24个月 |
| retention_money_ratio_is_5_percent | PASS | retention money ratio renders as 5% |
| retention_release_period_is_12_months | PASS | retention release period renders as 12个月 |
| retention_and_warranty_rows_are_distinct | PASS | retention money/release and project warranty render in distinct rows |
| final_cell_numeric_ownership | PASS | every numeric token displayed in a delivered cell is an owned value |
| stale_linked_facts_absent | PASS | every rendered linked fact is allowed for its concern |
| platform_role_distinction | PASS | 1 platform-related facts stay separate semantic roles |
| case_final_cell_audit | PASS | 138/138 final cells coherent; 30 sampled with addresses and displayed text |

## Human fixtures A–S (frozen workbook cells)

| fixture | expectation | status | evidence |
| --- | --- | --- | --- |
| A | 营业执照 row renders only its own licence requirement | PASS | 招标文件要求：2.1 供应商须具有独立承担民事责任的能力，为法人或其他组织，具备有效的营业 执照；准 供应商名称 供应商名称 与营业执照一致 复核要点： ① 核对该条要求对应的营业执照 ② 按本条要求逐条核对响应文件的对应内容 ③ 依据第5页第2.1条逐条比对响应文件对应章节 通过标准： · 已按本条要求提供营业执照， |
| B | signature row renders only the signature/seal requirement | PASS | 招标文件要求：3.7.3 签字盖章要求 1．所有要求供应商加盖公章的地方都应用供应商单 位的 CA 印章；签字或盖章的具体要求见供应商须知前附表 复核要点： ① 按招标文件签章要求逐处核对签字人与印章 ② 确认授权链条完整、印章清晰 ③ 依据第19页逐条比对响应文件对应章节 通过标准： · 所有指定位置的签字、盖章齐全 |
| C | credit/exclusion content renders under a credit concern | PASS | DR008 |
| D | anti-bribery commitment row is typed by its commitment concern | PASS | DR011 type=QUALIFICATION row=类型：QUALIFICATION/资格·无行贿与履约记录 |
| E | platform registration row keeps its own content and consequence | PASS | DR015 |
| F | clarification/question deadline renders as its own concern | PASS | DR016 |
| G | installation/acceptance row renders only installation content | PASS | 招标文件要求：3.1 供应商提供设备应遵照国家和部颁发的下列标准、规程和规范： （1）《二次供水工程技术规程》CJJ140-2018 （2）《室外给水设计规范》GB50013-2018 （3）《建筑给水排水设计规范》GB50015-2…；*流量计等相关计量仪器需提供第三方检测实验报告 第四条 复核要点： ① 确认验收节 |
| H | response-bond amount row cites the direct amount clause | PASS | 第10页 / 第3.4.1条 / （pdf_table_cell） 3.4.1 响应保证金 响应保证金的金额：人民币贰万元整。（源条款 7 条：SR0033） |
| I | agency-service fee renders as its own concern | PASS | DR026 |
| J | reject-all-responses stays an internal procedure item | PASS | procedure_items=['DR023'] rendered_in_rows=[] |
| K | project-basic-info row does not invent project name/number/lot checks | PASS | 招标文件要求：1.4.3 本项目的资金来源：见供应商须知前附表 复核要点： ① 核对项目基本信息 ② 确认与招标文件一致 ③ 依据第14页第1.4.3条逐条比对响应文件对应章节 通过标准： · 本条要求的内容在响应文件中可核验，且与要求一致。 |
| L | file-format row invents no binding/catalogue/page-number requirement | PASS | 招标文件要求：3.5 资格审查资料 按第六章“响应文件格式”中的要求提供相关资料，并符合询比公告中供应商的资 格要求；准 响应文件格式 响应文件格式 符合第六章“响应文件格式”中的要求 复核要点： ① 确认符合响应文件格式规定 ② 按本条要求逐条核对响应文件的对应内容 ③ 依据第17页第(6)条逐条比对响应文件对应章节 |
| M | file composition row keeps clarification/committee text out | PASS | DR036:FILE_FORMAT |
| N | price-completeness row uses price-scope evidence without an unsupported veto | PASS | 招标文件要求：3.2.1 供应商应在响应文件中按要求填写报价；3.2.4 评审小组发现供应商的报价明显低于其他响应报价，使得其响应报价可能低 于其成本的，应当要求该供应商作出书面说明并提供相应的证明材料 复核要点： ① 核对报价组成 ② 确认无漏项、重复项与未包含费用 ③ 依据第28页逐条比对响应文件对应章节 通过标准 |
| O | scoring is split into separate scoring concerns (payment condition, highest score, price formula) | PASS | concerns=['EVALUATION_SCORING', 'SCORING_PAYMENT_CONDITION', 'SCORING_PRICE_FORMULA', 'SCORING_TECHNICAL'] payment=['DR044'] price=['DR043'] |
| P | technical-parameter row does not borrow contract/material-list proof | PASS | 第34页 / 第三条验收方法及技术要求 / 第3.1条 / （pdf_block） 3.1 供应商提供设备应遵照国家和部颁发的下列标准、规程和规范： （1）《二次供水工程技术规程》CJJ140-2018 （2）《室外给水设计规范》GB50013-2018 （3）《建筑给水排水设计规范》GB50015-2（源条款 3 条 |
| Q | 12-month release renders only as the retention release period | PASS | release=['DR046'] warranty=['DR004'] |
| R | 5% renders only as the retention money ratio | PASS | DR049:招标文件要求：剩余 %，剩余 5%%，剩余 5%作为质保金 复核要点： ① 确认响应文件接受该比例 ② 按上述要求的数值 |
| S | transaction/announcement/entry platform roles stay separate | PASS | platform_keys=['electronic_platform'] conflicts=['06_冲突与缺失!D2', '06_冲突与缺失!D3', '06_冲突与缺失!D4', '06_冲突与缺失!D5', '06_冲突与缺失!D6', '06_冲突与缺失!D7', '06_冲突与缺失!D8'] |

## Final-cell audit (138/138 coherent)

| cell | item | concern | displayed text (first 160) |
| --- | --- | --- | --- |
| 投标项目复核表!D9 | DR008 | QUALIFICATION_CREDIT | 招标文件要求：2.3 供应商被列入“中国执行信息公开网（https://zxgk.court.gov.cn/shixin） 一全国法院失信被执行人名单信息公布与查询平台-失信被执行人”的；（三）信誉要求 1、供应商的“中国执行信息公开网（http://zxgk.court.gov.cn/shixin）一全国法院 失信被 |
| 投标项目复核表!E9 | DR008 | QUALIFICATION_CREDIT | 第6页 / 2.1 供应商须具有独立承担民事责任的能力，为法人或其他组织，具备有效的营业 / 第2.3条 / （pdf_block） 2.3 供应商被列入“中国执行信息公开网（https://zxgk.court.gov.cn/shixin） 一全国法院失信被执行人名单信息公布与查询平台-失信被执行人”的、“中国政府采 |
| 投标项目复核表!M9 | DR008 | QUALIFICATION_CREDIT | 类型：REJECTION/资格·信用记录 |
| 投标项目复核表!D10 | DR015 | ELECTRONIC_UPLOAD | 招标文件要求：供应商须使用电子交易系统提供的投标文件制作工具进行电子响应文件的制作，并在提 交响应文件截止时间前通过“河南国企阳光招采服务平台”上传经CA 密钥签章和加密 的电子响应文件（.EJYTF 格式）； 复核要点： ① 核对电子文件加密与上传记录 ② 确认上传成功且文件完整 ③ 依据第7页逐条比对响应文件对应章 |
| 投标项目复核表!E10 | DR015 | ELECTRONIC_UPLOAD | 第7页 / 1、采购人信息 / （pdf_block） 供应商须使用电子交易系统提供的投标文件制作工具进行电子响应文件的制作，并在提 交响应文件截止时间前通过“河南国企阳光招采服务平台”上传经CA 密钥签章和加密 的电子响应文件（.EJYTF 格式），加密电子响应文件逾期上传（源条款 10 条：SR0019） |
| 投标项目复核表!M10 | DR015 | ELECTRONIC_UPLOAD | 类型：REJECTION/电子上传与加密 |
| 投标项目复核表!D11 | DR029 | EVALUATION_COLLUSION | 招标文件要求：9.2 对供应商的纪律要求 供应商不得相互串通响应或与采购人串通响应，不得向采购人或者评审小组成员行 贿谋取成交，不得以他人名义响应或者以其他方式弄虚作假骗取成交；投标人投标文件制作机器码一致视为串通投标行为 复核要点： ① 核对不存在串标、弄虚作假的证据 ② 确认响应文件无雷同与异常一致 ③ 依据第22 |
| 投标项目复核表!E11 | DR029 | EVALUATION_COLLUSION | 第22页 / 9.2 对供应商的纪律要求 / 第9.2条 / （pdf_block） 9.2 对供应商的纪律要求 供应商不得相互串通响应或与采购人串通响应，不得向采购人或者评审小组成员行 贿谋取成交，不得以他人名义响应或者以其他方式弄虚作假骗取成交；（源条款 5 条：SR0052） |
| 投标项目复核表!M11 | DR029 | EVALUATION_COLLUSION | 类型：REJECTION/评审·串标与弄虚作假 |
| 投标项目复核表!D12 | DR030 | EVALUATION_RESPONSIVENESS | 招标文件要求：10.8 实质性要求和条件 本表格中带“*”条款；其中，响应函附录在满足询比文件实质性要求的基础上， 可以提出比询比文件要求更有利于采购人的承诺 复核要点： ① 核对实质性响应要求 ② 确认无重大偏差 ③ 依据第28页第3.1.2条逐条比对响应文件对应章节 通过标准： · 实质性响应要求全部满足，无重大偏 |
| 投标项目复核表!E12 | DR030 | EVALUATION_RESPONSIVENESS | 第13页 / 第10.8条 / （pdf_table_cell） 10.8 实质性要求和条件 本表格中带“*”条款；（源条款 9 条：SR0054） |
| 投标项目复核表!M12 | DR030 | EVALUATION_RESPONSIVENESS | 类型：REJECTION/评审·响应性审查 |
| 投标项目复核表!D13 | DR031 | REJECTION_GENERAL | 招标文件要求：“不允许”、“否决”、“无效”等文字规定的条款；“响应文件无效”条款 复核要点： ① 核对该否决情形对应的响应内容 ② 确认不触发该情形 ③ 依据第13页逐条比对响应文件对应章节 通过标准： · 不存在该情形，或已在响应文件中作出符合要求的响应。 不满足后果：无效 |
| 投标项目复核表!E13 | DR031 | REJECTION_GENERAL | 第13页 / （pdf_table_cell） “不允许”、“否决”、“无效”等文字规定的条款；（源条款 5 条：SR0055） |
| 投标项目复核表!M13 | DR031 | REJECTION_GENERAL | 类型：REJECTION/其他否决情形 |
| 投标项目复核表!D14 | DR038 | BID_BOND_EVIDENCE | 招标文件要求：3.4.1项要求提交响应保证金的，评审小组将否决其响应 复核要点： ① 按本条要求逐条核对响应文件的对应内容 ② 依据第18页第3.4.1条逐条比对响应文件对应章节 通过标准： · 本条要求的内容在响应文件中可核验，且与要求一致。 不满足后果：否决 |
| 投标项目复核表!E14 | DR038 | BID_BOND_EVIDENCE | 第18页 / 第六章“响应文件格式”规定的响应保证金格式递交响应保证金，并作为其响应文件的 / 第3.4.1条 / （pdf_block） 3.4.1项要求提交响应保证金的，评审小组将否决其响应。（源条款 1 条：SR0098） |
| 投标项目复核表!M14 | DR038 | BID_BOND_EVIDENCE | 类型：REJECTION/保证金凭证 |
| 投标项目复核表!D15 | DR041 | SUBMISSION_PLATFORM | 招标文件要求：加密电子响应文件逾期上传或者未上传或未送达指定地点，采购 人不予受理；④不同供应商的投标(响应)文件由同一人送达或者分发，或者不同供应商联系人为 同一人或不同联系人的联系电话一致的 复核要点： ① 核对递交方式与地点/平台 ② 确认按指定方式递交 ③ 依据第20页逐条比对响应文件对应章节 通过标准： ·  |
| 投标项目复核表!E15 | DR041 | SUBMISSION_PLATFORM | 第20页 / 4.2.4 供应商应确保电子响应文件在询比文件规定的提交响应文件截止时间前成 / （pdf_block） 加密电子响应文件逾期上传或者未上传或未送达指定地点，采购 人不予受理。（源条款 2 条：SR0120） |
| 投标项目复核表!M15 | DR041 | SUBMISSION_PLATFORM | 类型：REJECTION/递交地点与平台 |
| 投标项目复核表!D16 | DR005 | QUALIFICATION_LICENSE | 招标文件要求：2.1 供应商须具有独立承担民事责任的能力，为法人或其他组织，具备有效的营业 执照；准 供应商名称 供应商名称 与营业执照一致 复核要点： ① 核对该条要求对应的营业执照 ② 按本条要求逐条核对响应文件的对应内容 ③ 依据第5页第2.1条逐条比对响应文件对应章节 通过标准： · 已按本条要求提供营业执照， |
| 投标项目复核表!E16 | DR005 | QUALIFICATION_LICENSE | 第5页 / 二、供应商资格要求 / 第2.1条 / （pdf_block） 2.1 供应商须具有独立承担民事责任的能力，为法人或其他组织，具备有效的营业 执照。（源条款 3 条：SR0005） |
| 投标项目复核表!M16 | DR005 | QUALIFICATION_LICENSE | 类型：QUALIFICATION/资格·营业执照与资质 |
| 投标项目复核表!D17 | DR006 | QUALIFICATION_FINANCIAL | 招标文件要求：2.2 供应商近三年（2023、2024、2025年）财务状况良好（成立时间不足的以成立 之日为准），没有处于财务被接管、冻结、破产状态；（二）财务状况承诺书 供应商近三年（2023、2024、2025年）财务状况良好（成立时间不足的以成立之日 为准），没有处于财务被接管、冻结、破产状态 复核要点： ①  |
| 投标项目复核表!E17 | DR006 | QUALIFICATION_FINANCIAL | 第5页 / 2.1 供应商须具有独立承担民事责任的能力，为法人或其他组织，具备有效的营业 / 第2.2条 / （pdf_block） 2.2 供应商近三年（2023、2024、2025年）财务状况良好（成立时间不足的以成立 之日为准），没有处于财务被接管、冻结、破产状态；（源条款 3 条：SR0006） |
| 投标项目复核表!M17 | DR006 | QUALIFICATION_FINANCIAL | 类型：FINANCIAL/资格·财务能力 |
| 投标项目复核表!D18 | DR012 | CONSORTIUM | 招标文件要求：1.5.2 是否接受联合体响应：不接受 复核要点： ① 核对投标主体形式 ② 确认与联合体规定一致 ③ 依据第6页第2.6条逐条比对响应文件对应章节 通过标准： · 响应文件的投标主体形式与招标文件关于联合体的规定一致。 |
| 投标项目复核表!E18 | DR012 | CONSORTIUM | 第15页 / 1.6 费用承担 / 第1.5.2条 / （pdf_block） 1.5.2 是否接受联合体响应：不接受。（源条款 2 条：SR0015） |
| 投标项目复核表!M18 | DR012 | CONSORTIUM | 类型：CONSORTIUM/联合体；关联事实：consortium_allowed |

## Platform-role evidence

```json
{
 "platform_fact_keys": [
  "electronic_platform"
 ],
 "platform_rows": {
  "electronic_platform": {
   "cell": "01_项目事实!D24",
   "value": "",
   "status": "NEEDS_REVIEW",
   "candidates": "3"
  }
 },
 "conflict_rows": [
  {
   "cell": "06_冲突与缺失!D2",
   "text": "No credible candidate found.",
   "key": "tender_number"
  },
  {
   "cell": "06_冲突与缺失!D3",
   "text": "No credible candidate found.",
   "key": "lot_name"
  },
  {
   "cell": "06_冲突与缺失!D4",
   "text": "No credible candidate found.",
   "key": "lot_number"
  },
  {
   "cell": "06_冲突与缺失!D5",
   "text": "No credible candidate found.",
   "key": "budget"
  },
  {
   "cell": "06_冲突与缺失!D6",
   "text": "No credible candidate found.",
   "key": "procurement_method"
  },
  {
   "cell": "06_冲突与缺失!D7",
   "text": "No credible candidate found.",
   "key": "submission_method"
  },
  {
   "cell": "06_冲突与缺失!D8",
   "text": "e招投标交易平台；中国招标投标公共服务平台",
   "key": "electronic_platform"
  }
 ]
}
```
