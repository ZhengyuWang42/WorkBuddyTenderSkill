# Review workbook round 5 — case_001

- build: `v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook5`
- workbook: `acceptance\workspace\case_001\v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook5\投标项目复核表.xlsx` (sha256 `2ab34c7547926bb5…`)
- contracts: 78 (human_round5_fixtures_A_T round5.1)
- delivered rows audited: 49 (failed 0)
- fixtures: 20/20 pass / 0 fail / 0 not applicable

## Checks

| check | result | detail |
| --- | --- | --- |
| concern_contracts_are_independent | PASS | 78 contracts authored by hand (source=human_round5_fixtures_A_T, version=round5.1); none derived from a generated ReviewPoint |
| every_delivered_concern_has_a_contract | PASS | 49 delivered concerns covered |
| all_case001_final_rows_concern_contract | PASS | 49/49 delivered CASE001 rows agree with their independent concern contract |
| delivered_rows_read_from_final_cells | PASS | 49/49 rows audited from the frozen sheet cells |
| needs_review_rows_excluded_from_delivery | PASS | background items=3; filtered=2; needs_review=2 |
| numeric_roles_are_canonical | PASS | 9 numeric roles in use are canonical business roles |
| payment_ratio_95_is_not_retention | PASS | RETENTION_MONEY_RATIO never carries 95% |
| five_money_roles_stay_distinct | PASS | project warranty 24 months / retention 5% / release 12 months / payment 95% / bank acceptance 100% are separate roles |
| payment_ratio_95_is_not_retention | PASS | RETENTION_MONEY_RATIO never carries 95% |
| scoring_points_are_scoring_only | PASS | SCORE_POINTS values: ['12分', '1分', '2分', '30分', '40分', '4分', '8分'] |
| bank_acceptance_ratio_separate | PASS | bank-acceptance ratio and payment ratio are distinct roles |
| sheet_views_are_semantically_coherent | PASS | 02_关键条款 and 03_资格否决与强制项 audited from final cell text |
| conflict_sheet_has_no_false_platform_conflicts | PASS | 8 conflict rows audited |
| word_artifacts_unchanged | PASS | 3 carried-over artifacts are byte-identical to their source build |
| review_workbook5_written | PASS | 投标项目复核表.xlsx sha256=2ab34c754792 (71049 bytes) |
| rendered_row_provenance_persisted | PASS | 49 rendered rows carry their exact cell address |

## Fixtures A–T

| fixture | result | expectation | evidence |
| --- | --- | --- | --- |
| A | PASS | quality requirement displays no delivery location | D=招标文件要求：1.4.7 质量要求 符合国家及行业有关标准、规范和询比文件要求；准 质量要求 质量要求 符合第二章“供应商须知”第 1.4.7 款规定
复核要点：
① 确认响应文件承诺达标
② 按本条要求逐条核对响应文件的对应内容
③ 依据 E=第9页 / 供应商须知前附表 / 第1.4.7条 / （pdf_tab |
| B | PASS | bid validity shows direct 90-day evidence and no blacklist text | D=招标文件要求：3.3.1 询比有效期 提交响应文件截止之日起 90 日历天；询比有效期 提交响应文件截止之日起 90 日历天
复核要点：
① 核对投标函中的投标有效期
② 确认覆盖评审与定标全过程
③ 依据第12页逐条比对响应文件对应章节
 E=第10页 / 第3.3.1条 / （pdf_table_cell） 3 |
| C | PASS | funding clause is its own concern and does not leak into price rows | D=招标文件要求：1.4.3 本项目的资金来源：见供应商须知前附表
复核要点：
① 核对项目资金来源条款
② 确认已知悉资金来源与落实情况
③ 依据第14页第1.4.3条逐条比对响应文件对应章节
通过标准：
· 项目资金来源与资金落实情况已在响 |
| D | PASS | contract payment carries no agency-fee clause; the fee is complete or NEEDS_REVIEW | payment_rows=['DR044'] fee_rows=[] |
| E | PASS | contract payment evidence is not a contract-effectivity clause | 招标文件要求：如果甲方未按期向乙方支付货款的，乙方予以理解并承诺从最后一笔款项应付之日 起给甲方
复核要点：
① 核对合同付款条款响应
② 核对付款方式、结算依据与付款条件
③ 依据第33页逐条比对响应文件对应章节
通过标准：
· 付款方式、结算依据与付款条件在响应文件中被接受。第33页 / 第三条验收方法及技术要求  |
| F | PASS | performance bond displays and cites only 履约保证金 | 招标文件要求：7.3.1 在签订合同前，成交供应商应按供应商须知前附表规定的形式、金额和询比 文件第四章“合同条款及格式”规定的或者事先经过采购人书面认可的履约保证金形式 向采购人提交履约保证金；7.3.1 项要求提交履约保证金的，视为放弃成交
复核要点：
① 核对履约保证金的形式、金额与提交时点
② 确认在规定时间前 |
| G | PASS | price-completeness row asserts no unestablished 无漏项/无重复项 claim | 招标文件要求：3.2.1 供应商应在响应文件中按要求填写报价；所有报价及有关费用均以人民币元 为单位,供应商认为应计取的费用，均应列入响应报价，运费、税费等亦包括在报价中， 如因疏漏而未报或故意不报，采购人均按供应商已计取这些费用对待
复核要点：
① 核对报价组成与费用范围
② 确认费用范围与承担方与源文件一致
③ 依 |
| H | PASS | unit-price cost scope and delivery completion are separate concerns | cost=招标文件要求：5.2 设备单价中含运输费、装卸费、安装费、损耗和税金等费用
复核要点：
① 核对单价/报价包含的费用项
② 确认费用范围与承担方与源文件一致
③ 依据第34页第5.2条逐条比对响应文件 completion=招标文件要求：设备安装调试完 毕，甲方负责人在验收单上签字或加盖项目部印章，视为交付完 |
| I | PASS | technical standards / third-party proof / acceptance are separate concerns | standards=招标文件要求：3.1 供应商提供设备应遵照国家和部颁发的下列标准、规程和规范： （1）《二次供水工程技术规程》CJJ140-2018 （2）《室外给水设计规范》GB50013-20 report=招标文件要求：*流量计等相关计量仪器需提供第三方检测实验报告 第四条
复核要点：
① 核对需第三方检测/ |
| J | PASS | 95% is never displayed as a retention ratio | no 质保金比例为 95% phrasing |
| K | PASS | retention row shows 5% 质保金 and the warranty row shows 24 months | retention=质保金比例为 5% warranty=质保期不低于 24个月 |
| L | PASS | bank-acceptance ratio is scored in its own row | bank=接受银行承兑汇票比例为 100% 本项最高 4分 接受银行承兑汇票比例为 50% 本项最高 2分 |
| M | PASS | each scoring row carries its own factor's points | payment=比例为 95% 质保金比例为 5% 本项最高 12分 比例为 15% bank=接受银行承兑汇票比例为 100% 本项最高 4分 接受银行承兑汇票比例为 50% 本项最高 2分 |
| N | PASS | generic evaluation row invents no points value | no points value in EVALUATION_SCORING rows |
| O | PASS | technical scoring row uses real scoring-table content, not a cross-reference | 招标文件要求：2.2.4(2）目规定的评审因素和分值对技术标计算出得分B
复核要点：
① 核对技术方案的得分条件与证明材料
② 确认技术标章节可定位
③ 依据第27页第(2）条逐条比对响应文件对应章节
通过标准：
· 本条要求的内容在响应文件中可核验，且与要求一致。
评分提示：2.2.4(2）目规定的评审因素和分值对技 |
| P | PASS | general bidder obligation rows do not merge procurement scope with evaluation procedure | 1 obligation rows coherent |
| Q | PASS | authorization row is backed by authorization evidence | 招标文件要求：由授权代表签字的，应当附法定代表人授权书；由供应商的法定代表人（单位负责人）签字或加盖电子印章的，应附法 定代表人（单位负责人）身份证明，由代理人签字或加盖电子印章的，应附由法定代表 人（单位负责人）签署的授权委托书
复核要点：
① 核对授权委托书
② 确认授权代表与签署人一致且在有效期内
③ 依据第29 |
| R | PASS | submission row carries no collusion/delivery-pattern text | 招标文件要求：加密电子响应文件逾期上传或者未上传或未送达指定地点，采购 人不予受理
复核要点：
① 核对递交方式与地点/平台
② 确认按指定方式递交
③ 依据第20页逐条比对响应文件对应章节
通过标准：
· 递交方式、地点/平台符合招标文件要求。
不满足后果：不予受理第20页 / 4.2.4 供应商应确保电子响应文件在 |
| S | PASS | platform roles are split and produce no false platform conflicts | platform_concerns=['ELECTRONIC_UPLOAD', 'SUBMISSION_PLATFORM'] false_conflicts=0 |
| T | PASS | agency fee renders completely or moves to NEEDS_REVIEW (no fragment row) | agency fee is NEEDS_REVIEW (fragment source) |

## Delivered-row contract audit

| item | concern | cell | contract | violations |
| --- | --- | --- | --- | --- |
| DR008 | QUALIFICATION_CREDIT | 投标项目复核表!D9 | PASS |  |
| DR015 | ELECTRONIC_UPLOAD | 投标项目复核表!D10 | PASS |  |
| DR027 | EVALUATION_COLLUSION | 投标项目复核表!D11 | PASS |  |
| DR028 | EVALUATION_RESPONSIVENESS | 投标项目复核表!D12 | PASS |  |
| DR029 | REJECTION_GENERAL | 投标项目复核表!D13 | PASS |  |
| DR036 | BID_BOND_EVIDENCE | 投标项目复核表!D14 | PASS |  |
| DR039 | SUBMISSION_PLATFORM | 投标项目复核表!D15 | PASS |  |
| DR005 | QUALIFICATION_LICENSE | 投标项目复核表!D16 | PASS |  |
| DR006 | QUALIFICATION_FINANCIAL | 投标项目复核表!D17 | PASS |  |
| DR012 | CONSORTIUM | 投标项目复核表!D18 | PASS |  |
| DR031 | PROJECT_FUNDING_SOURCE | 投标项目复核表!D19 | PASS |  |
| DR033 | SUBCONTRACT | 投标项目复核表!D20 | PASS |  |
| DR009 | TECHNICAL_PROOF | 投标项目复核表!D21 | PASS |  |
| DR034 | FILE_FORMAT | 投标项目复核表!D22 | PASS |  |
| DR041 | SCORING_BANK_ACCEPTANCE | 投标项目复核表!D23 | PASS |  |
| DR001 | PRICE_CEILING | 投标项目复核表!D24 | PASS |  |
| DR010 | QUALIFICATION_RELATIONSHIP_RESTRICTION | 投标项目复核表!D25 | PASS |  |
| DR018 | BID_BOND_AMOUNT | 投标项目复核表!D26 | PASS |  |
| DR019 | BID_BOND_FORM | 投标项目复核表!D27 | PASS |  |
| DR020 | BID_BOND_TRANSFER | 投标项目复核表!D28 | PASS |  |
| DR024 | PRICE_TAX_BASIS | 投标项目复核表!D29 | PASS |  |
| DR035 | PRICING_COMPLETENESS | 投标项目复核表!D30 | PASS |  |
| DR052 | PRICE_INCLUDED_COST_SCOPE | 投标项目复核表!D31 | PASS |  |
| DR002 | DELIVERY_PERIOD | 投标项目复核表!D32 | PASS |  |
| DR003 | QUALITY_TARGET | 投标项目复核表!D33 | PASS |  |
| DR017 | BID_VALIDITY | 投标项目复核表!D34 | PASS |  |
| DR030 | DELIVERY_LOCATION | 投标项目复核表!D35 | PASS |  |
| DR025 | CONTRACT_RISK | 投标项目复核表!D36 | PASS |  |
| DR037 | PERFORMANCE_BOND | 投标项目复核表!D37 | PASS |  |
| DR042 | SCORING_PAYMENT_CONDITION | 投标项目复核表!D38 | PASS |  |
| DR044 | CONTRACT_PAYMENT | 投标项目复核表!D39 | PASS |  |
| DR045 | RETENTION_RELEASE_PERIOD | 投标项目复核表!D40 | PASS |  |
| DR048 | DELIVERY_ACCEPTANCE_COMPLETION | 投标项目复核表!D41 | PASS |  |
| DR049 | CONTRACT_TERMINATION_REFUND | 投标项目复核表!D42 | PASS |  |
| DR051 | RETENTION_MONEY_RATIO | 投标项目复核表!D43 | PASS |  |
| DR004 | PROJECT_WARRANTY | 投标项目复核表!D44 | PASS |  |
| DR032 | SITE_VISIT | 投标项目复核表!D45 | PASS |  |
| DR046 | TECHNICAL_STANDARD_COMPLIANCE | 投标项目复核表!D46 | PASS |  |
| DR047 | TECHNICAL_TEST_REPORT | 投标项目复核表!D47 | PASS |  |
| DR050 | TECHNICAL_PARAMETER | 投标项目复核表!D48 | PASS |  |
| DR026 | EVALUATION_SCORING | 投标项目复核表!D49 | PASS |  |
| DR040 | SCORING_PRICE_FORMULA | 投标项目复核表!D50 | PASS |  |
| DR043 | SCORING_TECHNICAL | 投标项目复核表!D51 | PASS |  |
| DR007 | SIGNATURE_AND_SEAL | 投标项目复核表!D52 | PASS |  |
| DR013 | GENERAL_BIDDER_OBLIGATION | 投标项目复核表!D53 | PASS |  |
| DR016 | QUERY_DEADLINE | 投标项目复核表!D54 | PASS |  |
| DR038 | AUTHORIZATION | 投标项目复核表!D55 | PASS |  |
| DR011 | QUALIFICATION_ANTI_BRIBERY | 投标项目复核表!D56 | PASS |  |
| DR014 | SUBMISSION_DEADLINE | 投标项目复核表!D57 | PASS |  |
