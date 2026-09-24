# Round-4 rendered-component provenance — case_002

* build: `v1_round4_closure8_review_workbook4`
* workbook: `acceptance\workspace\case_002\v1_round4_closure8_review_workbook4\投标项目复核表.xlsx` (sha256 `ea6c4f2d9bc8473c…`)
* invariant: **SEMANTIC OWNERSHIP MUST SURVIVE RENDERING**
* review rows: 46 (+3 non-bidder-facing background items)
* rendered components: 352 (0 unverified)
* rendered concern mismatches: 0
* **ROUND4 VERDICT: PASS** (23/23 checks, 0/19 fixtures)

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
| rendered_component_ownership_verified | PASS | 352 rendered components verified concern-owned |
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
| every_rendered_component_present_in_final_cell | PASS | 333 rendered components of 46 bidder-facing rows are displayed by a final workbook cell |
| view_cells_repeat_rendered_components | PASS | clause/mandatory view cells repeat the concern-owned rendered text |
| forbidden_retention_wording_absent | PASS | no cell presents the 12-month release period as the project warranty or the 5% retention money as a payment/scoring ratio |
| final_cell_text_owned_by_concern | PASS | 46/46 delivered cells name only concepts their concern owns |
| retention_roles_rendered_from_own_concerns | PASS | retention/warranty rows render only their own numeric role |
| retention_and_warranty_rows_are_distinct | PASS | retention money/release and project warranty render in distinct rows |
| final_cell_numeric_ownership | PASS | every numeric token displayed in a delivered cell is an owned value |
| stale_linked_facts_absent | PASS | every rendered linked fact is allowed for its concern |
| platform_role_distinction | PASS | 1 platform-related facts stay separate semantic roles |
| case_final_cell_audit | PASS | 138/138 final cells coherent; 30 sampled with addresses and displayed text |

## Human fixtures A–S (frozen workbook cells)

| fixture | expectation | status | evidence |
| --- | --- | --- | --- |
| A | 营业执照 row renders only its own licence requirement | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| B | signature row renders only the signature/seal requirement | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| C | credit/exclusion content renders under a credit concern | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| D | anti-bribery commitment row is typed by its commitment concern | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| E | platform registration row keeps its own content and consequence | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| F | clarification/question deadline renders as its own concern | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| G | installation/acceptance row renders only installation content | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| H | response-bond amount row cites the direct amount clause | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| I | agency-service fee renders as its own concern | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| J | reject-all-responses stays an internal procedure item | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| K | project-basic-info row does not invent project name/number/lot checks | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| L | file-format row invents no binding/catalogue/page-number requirement | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| M | file composition row keeps clarification/committee text out | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| N | price-completeness row uses price-scope evidence without an unsupported veto | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| O | scoring is split into separate scoring concerns (payment condition, highest score, price formula) | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| P | technical-parameter row does not borrow contract/material-list proof | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| Q | 12-month release renders only as the retention release period | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| R | 5% renders only as the retention money ratio | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |
| S | transaction/announcement/entry platform roles stay separate | NOT_APPLICABLE | human fixture is anchored to the CASE001 review workbook |

## Final-cell audit (138/138 coherent)

| cell | item | concern | displayed text (first 160) |
| --- | --- | --- | --- |
| 投标项目复核表!D9 | DR031 | REJECTION_GENERAL | 招标文件要求：3.6.1 除投标人须知前附表规定允许外，投标人不得递交备选投标方案，否则 其投标将被否决；投标人拒不澄清确认的， 评标委员会应当否决其投标： （1）投标文件中的大写金额与小写金额不一致的，以大写金额为准 复核要点： ① 核对该否决情形对应的响应内容 ② 确认不触发该情形 ③ 依据第20页第3.6.1条逐 |
| 投标项目复核表!E9 | DR031 | REJECTION_GENERAL | 第20页 / 3.6 备选投标方案 / 第3.6.1条 / （pdf_block） 3.6.1 除投标人须知前附表规定允许外，投标人不得递交备选投标方案，否则 其投标将被否决。（源条款 10 条：SR0099） |
| 投标项目复核表!M9 | DR031 | REJECTION_GENERAL | 类型：REJECTION/其他否决情形 |
| 投标项目复核表!D10 | DR034 | EVALUATION_RESPONSIVENESS | 招标文件要求：1.5 投标文件未实质性响应招标文件要求的；1.21 其他经评委会确认的未能实质性响应招标文件要求的投标 复核要点： ① 核对实质性响应要求 ② 确认无重大偏差 ③ 依据第17页第1.10.1条逐条比对响应文件对应章节 通过标准： · 实质性响应要求全部满足，无重大偏差。 |
| 投标项目复核表!E10 | DR034 | EVALUATION_RESPONSIVENESS | 第33页 / 第二章“投标人须知”和本章正文部分所规定的否决投标条件的总结和补充，如 / 第1.5条 / （pdf_block） 1.5 投标文件未实质性响应招标文件要求的；（源条款 8 条：SR0103） |
| 投标项目复核表!M10 | DR034 | EVALUATION_RESPONSIVENESS | 类型：REJECTION/评审·响应性审查 |
| 投标项目复核表!D11 | DR040 | EVALUATION_COLLUSION | 招标文件要求：9.2 对投标人的纪律要求 投标人不得相互串通投标或者与招标人串通投标，不得向招标人或者评标委 员会成员行贿谋取中标，不得以他人名义投标或者以其他方式弄虚作假骗取中 标；7.5.3 重点核查的异常投标情形： （一）法律法规规定视为串通投标的情形 复核要点： ① 核对不存在串标、弄虚作假的证据 ② 确认响应 |
| 投标项目复核表!E11 | DR040 | EVALUATION_COLLUSION | 第25页 / 9.2 对投标人的纪律要求 / 第9.2条 / （pdf_block） 9.2 对投标人的纪律要求 投标人不得相互串通投标或者与招标人串通投标，不得向招标人或者评标委 员会成员行贿谋取中标，不得以他人名义投标或者以其他方式弄虚作假骗取中 标；（源条款 14 条：SR0168） |
| 投标项目复核表!M11 | DR040 | EVALUATION_COLLUSION | 类型：REJECTION/评审·串标与弄虚作假 |
| 投标项目复核表!D12 | DR002 | QUALIFICATION_LICENSE | 招标文件要求：3.1 投标人须在中华人民共和国境内登记注册，具有独立承担民事责任能力 的法人或其他组织，具有有效的营业执照或其他证明文件 复核要点： ① 核对该条要求对应的营业执照 ② 按本条要求逐条核对响应文件的对应内容 ③ 依据第4页第3.1条逐条比对响应文件对应章节 通过标准： · 已按本条要求提供营业执照，内容 |
| 投标项目复核表!E12 | DR002 | QUALIFICATION_LICENSE | 第4页 / 三、投标人资格要求 / 第3.1条 / （pdf_block） 3.1 投标人须在中华人民共和国境内登记注册，具有独立承担民事责任能力 的法人或其他组织，具有有效的营业执照或其他证明文件；（源条款 1 条：SR0002） |
| 投标项目复核表!M12 | DR002 | QUALIFICATION_LICENSE | 类型：QUALIFICATION/资格·营业执照与资质 |
| 投标项目复核表!D13 | DR004 | QUALIFICATION_CREDIT | 招标文件要求：3.4 投标人须未被列入“信用中国（https://www.creditchina.gov.cn/）” 严重失信主体名单；4、投标人须未被列入“信用中国（https://www.creditchina.gov. 复核要点： ① 核对信用查询截图 ② 确认查询时间与查询结果满足要求 ③ 依据第5页第3.4条 |
| 投标项目复核表!E13 | DR004 | QUALIFICATION_CREDIT | 第5页 / 3.2 法定代表人授权书（附法定代表人、被授权人身份证复印件）及被授权 / 第3.4条 / （pdf_block） 3.4 投标人须未被列入“信用中国（https://www.creditchina.gov.cn/）” 严重失信主体名单；（源条款 2 条：SR0004） |
| 投标项目复核表!M13 | DR004 | QUALIFICATION_CREDIT | 类型：QUALIFICATION/资格·信用记录 |
| 投标项目复核表!D14 | DR006 | CONSORTIUM | 招标文件要求：3.1.2 投标人须知前附表规定不接受联合体投标的，或投标人没有组成联合 2026-03-23 16:58:05 体的，投标文件不包括联合体协议书 复核要点： ① 核对投标主体形式 ② 确认与联合体规定一致 ③ 依据第5页第3.6条逐条比对响应文件对应章节 通过标准： · 响应文件的投标主体形式与招标文件 |
| 投标项目复核表!E14 | DR006 | CONSORTIUM | 第19页 / 3.1.2 投标人须知前附表规定不接受联合体投标的，或投标人没有组成联合 / 第3.1.2条 / （pdf_block） 3.1.2 投标人须知前附表规定不接受联合体投标的，或投标人没有组成联合 2026-03-23 16:58:05 体的，投标文件不包括联合体协议书。（源条款 5 条：SR0006） |
| 投标项目复核表!M14 | DR006 | CONSORTIUM | 类型：CONSORTIUM/联合体；关联事实：consortium_allowed |
| 投标项目复核表!D15 | DR028 | PROJECT_BASIC_INFO | 招标文件要求：1.2.1 本招标项目的资金来源：见投标人须知前附表 复核要点： ① 核对项目基本信息 ② 确认与招标文件一致 ③ 依据第16页第1.2.1条逐条比对响应文件对应章节 通过标准： · 本条要求的内容在响应文件中可核验，且与要求一致。 |
| 投标项目复核表!E15 | DR028 | PROJECT_BASIC_INFO | 第16页 / 1.2 招标项目的资金来源和落实情况 / 第1.2.1条 / （pdf_block） 1.2.1 本招标项目的资金来源：见投标人须知前附表。（源条款 1 条：SR0088） |
| 投标项目复核表!M15 | DR028 | PROJECT_BASIC_INFO | 类型：FINANCIAL/项目基本信息 |
| 投标项目复核表!D16 | DR029 | QUALIFICATION_FINANCIAL | 招标文件要求：可根据财务要求，提供定制化接口开 发 复核要点： ① 确认数据与出具主体符合要求 ② 按本条要求逐条核对响应文件的对应内容 ③ 依据第16页第1.2.3条逐条比对响应文件对应章节 通过标准： · 本条要求的内容在响应文件中可核验，且与要求一致。 |
| 投标项目复核表!E16 | DR029 | QUALIFICATION_FINANCIAL | 第87页 / 1.7 报表管理平台 / （pdf_block） 可根据财务要求，提供定制化接口开 发。（源条款 4 条：SR0090） |
| 投标项目复核表!M16 | DR029 | QUALIFICATION_FINANCIAL | 类型：FINANCIAL/资格·财务能力 |
| 投标项目复核表!D17 | DR033 | SUBCONTRACT | 招标文件要求：2026-03-23 16:58:05 二十、分包 本合同不接受分包；5.乙方不允许转包已中标的工程，未经甲方同意不得更换投标时所报的项目 经理或该项日经理未实质上组织管理该工程，若发生时经书面协调未纠正，甲方 可认定乙方违约而予以相应处罚直至解除合同 复核要点： ① 核对分包安排 ② 确认无违规分包、转 |
| 投标项目复核表!E17 | DR033 | SUBCONTRACT | 第45页 / 二十二、误期赔偿费 / （pdf_block） 2026-03-23 16:58:05 二十、分包 本合同不接受分包。（源条款 3 条：SR0102） |
| 投标项目复核表!M17 | DR033 | SUBCONTRACT | 类型：SUBCONTRACT/分包与转包 |
| 投标项目复核表!D18 | DR036 | EVALUATION_QUALIFICATION_REVIEW | 招标文件要求：3.5 资格审查资料 除投标人须知前附表另有规定外，投标人应按下列规定提供资格审查资料， 以证明其满足本章第 1.4.1 款规定的投标人资质条件 复核要点： ① 核对资格审查要点 ② 确认全部满足 ③ 依据第20页第3.5条逐条比对响应文件对应章节 通过标准： · 资格审查要点在响应文件中全部满足。 |
| 投标项目复核表!E18 | DR036 | EVALUATION_QUALIFICATION_REVIEW | 第20页 / 3.5 资格审查资料 / 第3.5条 / （pdf_block） 3.5 资格审查资料 除投标人须知前附表另有规定外，投标人应按下列规定提供资格审查资料， 以证明其满足本章第 1.4.1 款规定的投标人资质条件。（源条款 1 条：SR0133） |
| 投标项目复核表!M18 | DR036 | EVALUATION_QUALIFICATION_REVIEW | 类型：QUALIFICATION/评审·资格审查 |

## Platform-role evidence

```json
{
 "platform_fact_keys": [
  "electronic_platform"
 ],
 "platform_rows": {
  "electronic_platform": {
   "cell": "01_项目事实!D24",
   "value": "西安市综改试验区国企招标集采交易平台",
   "status": "RESOLVED",
   "candidates": "1"
  }
 },
 "conflict_rows": [
  {
   "cell": "06_冲突与缺失!D2",
   "text": "No credible candidate found.",
   "key": "lot_name"
  },
  {
   "cell": "06_冲突与缺失!D3",
   "text": "No credible candidate found.",
   "key": "lot_number"
  },
  {
   "cell": "06_冲突与缺失!D4",
   "text": "软件功能建设包含水表全生命周期管理系统(表务管理系统),IC卡表对接,缴费一体机功能开发,接入“i西安”APP,接入陕西省政务平台,营销App升级,报表管理平台(报表中心),网上营业厅；西安市自来水公司数据库逻辑分析(含机械表、一代卡、二代卡、三代卡)业务系统数据对原数据库数据表、业务逻辑全面分析,充分",
   "key": "procurement_scope"
  },
  {
   "cell": "06_冲突与缺失!D5",
   "text": "No credible candidate found.",
   "key": "budget"
  },
  {
   "cell": "06_冲突与缺失!D6",
   "text": "No credible candidate found.",
   "key": "submission_method"
  }
 ]
}
```
