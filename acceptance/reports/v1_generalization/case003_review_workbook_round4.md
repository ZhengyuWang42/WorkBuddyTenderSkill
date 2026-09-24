# Round-4 rendered-component provenance — case_003

* build: `v1_round4_closure8_review_workbook4`
* workbook: `acceptance\workspace\case_003\v1_round4_closure8_review_workbook4\投标项目复核表.xlsx` (sha256 `3bb048a45ebb3a44…`)
* invariant: **SEMANTIC OWNERSHIP MUST SURVIVE RENDERING**
* review rows: 49 (+4 non-bidder-facing background items)
* rendered components: 378 (0 unverified)
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
| delivered_rows_bound_to_plan_items | PASS | 49/49 delivered review rows bound to plan items |
| rendered_cell_equals_component_projection | PASS | 49/49 delivered D cells are the exact projection of their verified components |
| rendered_component_ownership_verified | PASS | 378 rendered components verified concern-owned |
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
| every_rendered_component_present_in_final_cell | PASS | 351 rendered components of 49 bidder-facing rows are displayed by a final workbook cell |
| view_cells_repeat_rendered_components | PASS | clause/mandatory view cells repeat the concern-owned rendered text |
| forbidden_retention_wording_absent | PASS | no cell presents the 12-month release period as the project warranty or the 5% retention money as a payment/scoring ratio |
| final_cell_text_owned_by_concern | PASS | 49/49 delivered cells name only concepts their concern owns |
| retention_roles_rendered_from_own_concerns | PASS | retention/warranty rows render only their own numeric role |
| retention_and_warranty_rows_are_distinct | PASS | retention money/release and project warranty render in distinct rows |
| final_cell_numeric_ownership | PASS | every numeric token displayed in a delivered cell is an owned value |
| stale_linked_facts_absent | PASS | every rendered linked fact is allowed for its concern |
| platform_role_distinction | PASS | 1 platform-related facts stay separate semantic roles |
| case_final_cell_audit | PASS | 147/147 final cells coherent; 30 sampled with addresses and displayed text |

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

## Final-cell audit (147/147 coherent)

| cell | item | concern | displayed text (first 160) |
| --- | --- | --- | --- |
| 投标项目复核表!D9 | DR018 | REJECTION_GENERAL | 招标文件要求：3.1.2其他要求： （1）投标人拟投入项目管理机构人员要求：按照《黑龙江省房屋建筑和市政 基础设施工程施工现场管理人员配备管理办法》(黑建规〔2023〕2号)文件及招标 文件(项目管理机构人员配置表)规定；3.6.1除投标人须知前附表规定允许外，投标人不得递交备选投标方案，否则其投标将被 否决 复核要点 |
| 投标项目复核表!E9 | DR018 | REJECTION_GENERAL | 第8页 / 2.因原项目发包方原因导致工程长期停工、无法组织竣工验收，且该人员已按 / 第3.1.2条 / （pdf_block） 3.1.2其他要求： （1）投标人拟投入项目管理机构人员要求：按照《黑龙江省房屋建筑和市政 基础设施工程施工现场管理人员配备管理办法》(黑建规〔2023〕2号)文件及招标 文件(项目管理机 |
| 投标项目复核表!M9 | DR018 | REJECTION_GENERAL | 类型：REJECTION/其他否决情形 |
| 投标项目复核表!D10 | DR019 | EVALUATION_COLLUSION | 招标文件要求：9.2对投标人的纪律要求：投标人不得相互串通投标或者与招标人串通投标，不得向招标人 或者评标委员会成员行贿谋取中标，不得以他人名义投标或者以其他方式弄虚作假骗取中 标；（4）承诺函法律责任：投标人提供的承诺函应真实、准确，若存在虚假承诺 ，视为弄虚作假，依据《中华人民共和国招标投标法》相关规定追究责任，中 |
| 投标项目复核表!E10 | DR019 | EVALUATION_COLLUSION | 第38页 / 9.2对投标人的纪律要求：投标人不得相互串通投标或者与招标人串通投标，不得向招标人 / 第9.2条 / （pdf_block） 9.2对投标人的纪律要求：投标人不得相互串通投标或者与招标人串通投标，不得向招标人 或者评标委员会成员行贿谋取中标，不得以他人名义投标或者以其他方式弄虚作假骗取中 标；（源条款  |
| 投标项目复核表!M10 | DR019 | EVALUATION_COLLUSION | 类型：REJECTION/评审·串标与弄虚作假 |
| 投标项目复核表!D11 | DR028 | EVALUATION_RESPONSIVENESS | 招标文件要求：1.12.2投标文件应对招标文件的实质性要求和条件作出满足性或更有利于招标人的响 应，否则，视为投标文件存在重大偏差，投标人的投标将被否决；偏差包括重大偏差和细微 偏差 复核要点： ① 核对实质性响应要求 ② 确认无重大偏差 ③ 依据第49页逐条比对响应文件对应章节 通过标准： · 实质性响应要求全部满足 |
| 投标项目复核表!E11 | DR028 | EVALUATION_RESPONSIVENESS | 第29页 / 1.12.2投标文件应对招标文件的实质性要求和条件作出满足性或更有利于招标人的响 / 第1.12.2条 / （pdf_block） 1.12.2投标文件应对招标文件的实质性要求和条件作出满足性或更有利于招标人的响 应，否则，视为投标文件存在重大偏差，投标人的投标将被否决。（源条款 7 条：SR0125） |
| 投标项目复核表!M11 | DR028 | EVALUATION_RESPONSIVENESS | 类型：REJECTION/评审·响应性审查 |
| 投标项目复核表!D12 | DR044 | EVALUATION_QUALIFICATION_REVIEW | 招标文件要求：注：特别说明： 1、资格审查委员会及评标委员会依据招标文件规定对投标人资格、形式、响应性及否决投标情形进 行审查，进行独立评审 复核要点： ① 核对资格审查要点 ② 确认全部满足 ③ 依据第44页逐条比对响应文件对应章节 通过标准： · 资格审查要点在响应文件中全部满足。 不满足后果：否决 |
| 投标项目复核表!E12 | DR044 | EVALUATION_QUALIFICATION_REVIEW | 第44页 / 第一节评标办法 （定性评审法） 评标办法前附表 / （pdf_block） 注：特别说明： 1、资格审查委员会及评标委员会依据招标文件规定对投标人资格、形式、响应性及否决投标情形进 行审查，进行独立评审。（源条款 1 条：SR0392） |
| 投标项目复核表!M12 | DR044 | EVALUATION_QUALIFICATION_REVIEW | 类型：REJECTION/评审·资格审查 |
| 投标项目复核表!D13 | DR012 | QUALIFICATION_LICENSE | 招标文件要求：3.1.1投标人必须是在中华人民共和国境内注册的具有独立法人资格的法人 或其他组织并具备承担本招标项目的能力，条件如下：；3.1.1投标人必须是在中华人民共和国境内注册的具有独立法人资格的法人 或其他组织并具备承担本招标项目的能力，条件如下： 3.1.1.1投标人资质要求：具备有效的工商营业执照 复核要点 |
| 投标项目复核表!E13 | DR012 | QUALIFICATION_LICENSE | 第6页 / 2.12其他：/ / 第3.1.1条 / （pdf_block） 3.1.1投标人必须是在中华人民共和国境内注册的具有独立法人资格的法人 或其他组织并具备承担本招标项目的能力，条件如下： 3.1.1.1投标人资质要求：具备有效的工商营业执照，同时具备电子与智能化 工程专业承包二级及以上（源条款 14 条：S |
| 投标项目复核表!M13 | DR012 | QUALIFICATION_LICENSE | 类型：QUALIFICATION/资格·营业执照与资质 |
| 投标项目复核表!D14 | DR017 | CONSORTIUM | 招标文件要求：3.1.1.7本招标项目不接受联合体投标；1.1.7本招标项目不接受联合体投标 复核要点： ① 核对投标主体形式 ② 确认与联合体规定一致 ③ 依据第8页第3.1.1.7条逐条比对响应文件对应章节 通过标准： · 响应文件的投标主体形式与招标文件关于联合体的规定一致。 |
| 投标项目复核表!E14 | DR017 | CONSORTIUM | 第8页 / 2.因原项目发包方原因导致工程长期停工、无法组织竣工验收，且该人员已按 / 第3.1.1.7条 / （pdf_block） 3.1.1.7本招标项目不接受联合体投标。（源条款 14 条：SR0036） |
| 投标项目复核表!M14 | DR017 | CONSORTIUM | 类型：CONSORTIUM/联合体 |
| 投标项目复核表!D15 | DR020 | SUBCONTRACT | 招标文件要求：须提供对本工程无挂靠施 工声明承诺书；分包必须 复核要点： ① 核对分包安排 ② 确认无违规分包、转包 ③ 依据第9页第（5）条逐条比对响应文件对应章节 通过标准： · 不存在违规分包、转包情形，或已按允许范围说明。 |
| 投标项目复核表!E15 | DR020 | SUBCONTRACT | 第22页 / （pdf_table_cell） 须提供对本工程无挂靠施 工声明承诺书。（源条款 24 条：SR0047） |
| 投标项目复核表!M15 | DR020 | SUBCONTRACT | 类型：SUBCONTRACT/分包与转包 |
| 投标项目复核表!D16 | DR049 | CONTRACT_DELIVERY | 招标文件要求：承包人不提交上述文件的，项目经理无权履行职责，发包人 有权要求更换项目经理，由此增加的费用和（或）延误的工期由承包人承担 复核要点： ① 按本条要求逐条核对响应文件的对应内容 ② 依据第117页逐条比对响应文件对应章节 通过标准： · 本条要求的内容在响应文件中可核验，且与要求一致。 |
| 投标项目复核表!E16 | DR049 | CONTRACT_DELIVERY | 第117页 / 3.2项目经理 / （pdf_block） 承包人不提交上述文件的，项目经理无权履行职责，发包人 有权要求更换项目经理，由此增加的费用和（或）延误的工期由承包人承担。（源条款 1 条：SR0609） |
| 投标项目复核表!M16 | DR049 | CONTRACT_DELIVERY | 类型：PERSONNEL/合同交付义务 |
| 投标项目复核表!D17 | DR022 | QUALIFICATION_RELATIONSHIP_RESTRICTION | 招标文件要求：（7）单位负责人为同一人或者存在控股、管理关系的不同单位，不得参加同 一标段投标或者未划分标段的同一招标项目投标；（7）单位负责人为同一人或者存在控股、管理关系的不同单位，不得参加同一 复核要点： ① 确认声明或证明材料齐全 ② 按本条要求逐条核对响应文件的对应内容 ③ 依据第9页第（7）条逐条比对响应文 |
| 投标项目复核表!E17 | DR022 | QUALIFICATION_RELATIONSHIP_RESTRICTION | 第9页 / 4.招标文件的获取 / 第（7）条 / （pdf_block） （7）单位负责人为同一人或者存在控股、管理关系的不同单位，不得参加同 一标段投标或者未划分标段的同一招标项目投标。（源条款 5 条：SR0049） |
| 投标项目复核表!M17 | DR022 | QUALIFICATION_RELATIONSHIP_RESTRICTION | 类型：REJECTION/资格·关联关系限制 |
| 投标项目复核表!D18 | DR043 | QUERY_DEADLINE | 招标文件要求：1.10.1投标人须知前附表规定召开投标预备会的，招标人按照投标人须知前附表规定的时间 和形式召开投标预备会，澄清投标人提出的问题；1.10.2投标人应按照投标人须知前附表规定的时间和形式将提出的问题送达招标人， 以便招标人在会议期间澄清 复核要点： ① 核对提问/澄清的时间与提交方式 ② 确认澄清或修改 |
| 投标项目复核表!E18 | DR043 | QUERY_DEADLINE | 第28页 / 1.10投标预备会 / 第1.10.1条 / （pdf_block） 1.10.1投标人须知前附表规定召开投标预备会的，招标人按照投标人须知前附表规定的时间 和形式召开投标预备会，澄清投标人提出的问题。（源条款 10 条：SR0275） |
| 投标项目复核表!M18 | DR043 | QUERY_DEADLINE | 类型：SUBMISSION/提问与澄清截止 |

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
   "key": "project_number"
  },
  {
   "cell": "06_冲突与缺失!D3",
   "text": "No credible candidate found.",
   "key": "tender_number"
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
   "text": "554日历天；554日历天",
   "key": "duration"
  },
  {
   "cell": "06_冲突与缺失!D7",
   "text": "符合现行国家、行业及地方工程施工质量验收标准以及相关专业验收规范的合格标准；格标准",
   "key": "quality_target"
  },
  {
   "cell": "06_冲突与缺失!D8",
   "text": "同投标截止时间",
   "key": "bid_deadline"
  },
  {
   "cell": "06_冲突与缺失!D9",
   "text": "Candidate evidence exists but no candidate passed the field value-type validator.",
   "key": "bid_open_time"
  },
  {
   "cell": "06_冲突与缺失!D10",
   "text": "不接受；不接受",
   "key": "consortium_allowed"
  },
  {
   "cell": "06_冲突与缺失!D11",
   "text": "No credible candidate found.",
   "key": "procurement_method"
  }
 ]
}
```
