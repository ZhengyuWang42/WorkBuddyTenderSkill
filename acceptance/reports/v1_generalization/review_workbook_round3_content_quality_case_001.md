# Round-3 review-workbook content quality — case_001

- result: **PASS**
- pipeline: `SourceRequirementAtom -> ReviewConcern -> ReviewPoint`
- invariant: PROVENANCE IS NECESSARY BUT NOT SUFFICIENT (source-backed AND same concern)
- source atoms: 309 · concerns: 44 · review points: 43
- mismatch: source 0 · numeric 0 · material 0 · consequence 0 · evidence 0 · authority 0
- false conflicts: 0 · true conflicts: 3 · naive keyword conflicts avoided: 1
- fixture A–N: 14/14 PASS
- warranty/retention fixture: PASS
- manual-style audit: 20/20 coherent
- round-2 → round-3 examples: 16

## Warranty / retention

- project warranty: PROJECT_WARRANTY = 24个月 (WARRANTY_MONTHS) from 第39页, 第43页, 第5页, 第9页
- retention money: RETENTION_MONEY_RATIO = 5%
- retention release: RETENTION_RELEASE_PERIOD = 12个月
- reported as conflict: False

## Fixtures A–N

| fixture | label | result | old concern | new concern | atoms |
| --- | --- | --- | --- | --- | --- |
| A | signature vs electronic upload | PASS | SIGNATURE (from CA/upload text) | SIGNATURE_AND_SEAL / ELECTRONIC_UPLOAD | SRA0007, SRA0013, SRA0021 |
| B | submission contamination | PASS | SUBMISSION (with 评审报告/0元) | SUBMISSION_DEADLINE / SUBMISSION_PLATFORM / SUBMISSION_COPIES | SRA0018, SRA0027, SRA0029 |
| C | file composition evidence | PASS | FILE_COMPOSITION (from 异议函 text) | FILE_COMPOSITION | SRA0081, SRA0127, SRA0128 |
| D | file format evidence | PASS | FILE_FORMAT (from 备选方案/联系方式) | FILE_FORMAT | SRA0080, SRA0088, SRA0103 |
| E | technical plan evidence | PASS | TECHNICAL_PLAN (from supplier definition / site visit) | TECHNICAL_PLAN | — |
| F | financial commitment ownership | PASS | QUALIFICATION_FINANCIAL (from 资金来源：企业自筹) | QUALIFICATION_FINANCIAL / PROJECT_BASIC_INFO | SRA0006, SRA0162, SRA0291 |
| G | installation quantities | PASS | TECHNICAL/安装调试与验收 (any nearby quantity) | TECHNICAL_INSTALLATION | SRA0023, SRA0184, SRA0186 |
| H | bid-bond material isolation | PASS | BID_BOND (with experience/authorization materials) | BID_BOND_AMOUNT / FORM / TRANSFER / DEADLINE / EVIDENCE | SRA0032, SRA0034, SRA0098 |
| I | contract/payment contamination | PASS | CONTRACT_PAYMENT (with relationship restrictions) | CONTRACT_PAYMENT / CONTRACT_RISK / CONTRACT_DELIVERY / CONTRACT_ACCEPTANCE | SRA0049.1, SRA0049.2, SRA0134 |
| J | internal procedure filtering | PASS | bidder rows from 评审小组回避/纪律/术语定义 | filtered, or an explicit non-bidder 备查 row | SRA0038, SRA0145, SRA0228 |
| K | false price-limit concern | PASS | PRICING/分项限价与暂列金额 (from a heading) | PRICE_ITEMIZATION (only with limit/amount evidence) | — |
| L | scoring ownership | PASS | EVALUATION (generic method text) | EVALUATION_SCORING | SRA0050, SRA0129, SRA0143 |
| M | mixed evaluation split | PASS | EVALUATION (串标 + 银行承兑 combined) | EVALUATION_COLLUSION vs EVALUATION_SCORING | SRA0050, SRA0129, SRA0143 |
| N | technical vs eligibility/rejection | PASS | TECHNICAL_PARAMETER (eligibility restriction) | eligibility/rejection concern | SRA0179, SRA0240, SRA0264 |

## Round-2 → Round-3 examples

### SIGNATURE_AND_SEAL — 签章要求

- ROUND2 row: 招标文件要求：如 果出现上述情况，改动之处应加盖单位公章并由供应商的法定代表人或其授权的代理人 签字确认。；异议函应当包括下列内容： 异议函及授权委托书应按照规定签字并加盖公 章。
复核要点：
① 按招标文件签章要求逐页核对签字人、盖章种类与位置
② 确认授权链条完整、印章清晰
③ 依据第19页逐条比对响应文件对应章节
通过标准：
· 所有指定位置签字/盖章齐全有效，授权链条一致。
准备材料：类似项目合同及验收证明、法定代表人授权委托书
- ROUND3 atoms: SRA0007, SRA0013, SRA0021, SRA0028, SRA0036
- ROUND3 owned numbers: —
- ROUND3 owned materials: 法定代表人授权委托书, 身份证扫描件
- ROUND3 consequence: 无效
- ROUND3 requirement: 盖企业公章的扫描件和可编辑的Word 电子版）上传。；3.7.3 签字盖章要求 1．所有要求供应商加盖公章的地方都应用供应商单 位的 CA 印章。
- ROUND3 checks: 按招标文件签章要求逐处核对签字人与印章 / 确认授权链条完整、印章清晰 / 依据第19页逐条比对响应文件对应章节
- ROUND3 pass criteria: 所有指定位置的签字、盖章齐全且形式合规。
- why round-2 ownership was wrong: 哪些位置必须签字/盖章，形式是否合规？

### SUBMISSION_DEADLINE — 递交截止时间

- ROUND2 row: 招标文件要求：3.4.2 评审小组完成评审后，应当向采购人提交书面评审报告。；4.询比文件售价：0元 四、响应文件提交 1.截止时间：2026 年7 月28 日15 时00 分（北京时间）。
复核要点：
① 核对递交方式、递交地点/平台与截止时间
② 确认预留足够提前量并完成签到/解密准备
③ 依据第29页第3.4.2条逐条比对响应文件对应章节
通过标准：
· 在规定时间前按要求完成递交/上传与解密。
- ROUND3 atoms: SRA0018, SRA0027, SRA0029, SRA0030, SRA0037
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 1.10.2 供应商提出问题的时间 提交响应文件截止时间 2 日前在“河南国企阳光招
- ROUND3 checks: 核对递交截止时间 / 确认完成递交的时间与凭证 / 依据第29页第3.4.2条逐条比对响应文件对应章节
- ROUND3 pass criteria: 在规定的截止时间前完成递交。
- why round-2 ownership was wrong: 是否在规定截止时间前完成递交？

### FILE_COMPOSITION — 响应文件组成

- ROUND2 row: 招标文件要求：6.1.2 评审小组成员有下列情形之一的，应当回避： (1）供应商或供应商的主要负责人的近亲属；；9.3 对评审小组成员的纪律要求 评审小组成员不得收受他人的财物或者其他好处，不得向他人透露对响应文件的评 审和比较、成交候选供应商的推荐情况以及评审有关的其他情况。
复核要点：
① 按招标文件清单核对响应文件组成与格式
② 依据第20页第6.1.2条逐条比对响应文件对应章节
通过标准：
· 响应文件对应内容与该条款一致。
- ROUND3 atoms: SRA0081, SRA0127, SRA0128, SRA0142
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 如有疑问，应按照供应商须知前附表规定的时间前以书 面形式（包括信函、电报、传真等可以有形地表现所载内容的形式，下同），要求采购 人对询比文件予以澄清，否则由此引起的任何后果均由供应商自己承担，采购人和采购 代理机构不承…；评审小组成员人数以及技术、经济等方面专家的确定方式 见供应商须知前附表。
- ROUND3 checks: 按招标文件要求的组成部分逐项清点 / 确认无缺项、无多余替代件 / 依据第20页第6.1.2条逐条比对响应文件对应章节
- ROUND3 pass criteria: 响应文件组成齐全，与招标文件要求的组成部分一致。
- why round-2 ownership was wrong: 响应文件应由哪些部分组成、是否齐全？

### FILE_FORMAT — 响应文件格式

- ROUND2 row: 招标文件要求：异议函应当包括下列内容：（1）供应商的姓名或者；异议函应当包括下列内容：
复核要点：
① 按招标文件组成清单逐项清点响应文件章节与附表
② 确认无遗漏、无多余内容冲突
③ 依据第11页逐条比对响应文件对应章节
通过标准：
· 响应文件格式、组成与编排符合规定。
- ROUND3 atoms: SRA0080, SRA0088, SRA0103, SRA0105, SRA0159
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: (6) 响应文件格式。；3.1.1 详见第六章“响应文件格式”。
- ROUND3 checks: 核对格式、装订、目录与页码 / 确认符合响应文件格式规定 / 依据第17页第(6)条逐条比对响应文件对应章节
- ROUND3 pass criteria: 格式、装订、目录与页码符合招标文件要求。
- why round-2 ownership was wrong: 格式、装订、目录与页码是否按要求？

### QUALIFICATION_FINANCIAL — 资格·财务能力

- ROUND2 row: 招标文件要求：2.1.2 资格评审标准 资格评审标准 财务状况 财务状况 符合第二章“供应商须知”第 1.5.1 款规定；2.2 供应商近三年（2023、2024、2025年）财务状况良好（成立时间不足的以成立 之日为准），没有处于财务被接管、冻结、破产状态；
复核要点：
① 按招标文件指定年度/期间提供财务材料
② 核对主体名称、数据口径与盖章
③ 依据第24页第2.1.2条逐条比对响应文件对应章节
通过标准：
· 财务材料按指定期间提供，主体名称与投标人一致。
准备材料：经审计的财务报告或财务状况承诺书、承诺函（按招标文件格式）
- ROUND3 atoms: SRA0006, SRA0162, SRA0291, SRA0297
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 2.2 供应商近三年（2023、2024、2025年）财务状况良好（成立时间不足的以成立 之日为准），没有处于财务被接管、冻结、破产状态；；2.1.2 资格评审标准 资格评审标准 财务状况 财务状况 符合第二章“供应商须知”第 1.5.1 款规定
- ROUND3 checks: 核对财务审计报告或财务承诺 / 确认数据与出具主体符合要求 / 依据第24页第2.1.2条逐条比对响应文件对应章节
- ROUND3 pass criteria: 财务能力材料按要求提供且数据可核验。
- why round-2 ownership was wrong: 财务能力承诺或审计报告是否按要求提供？

### TECHNICAL_INSTALLATION — 安装调试与验收

- ROUND2 row: 招标文件要求：3.1 供应商提供设备应遵照国家和部颁发的下列标准、规程和规范： （1）《二次供水工程技术规程》CJJ140-2018 （2）《室外给水设计规范》GB50013-2018 （3）《建筑给水排水设计规范》GB50015-…；*流量计等相关计量仪器需提供第三方检测实验报告 第四条
复核要点：
① 核对安装、调试、检测与验收标准
② 确认验收节点与招标文件要求一致
③ 依据第34页第3.1条逐条比对响应文件对应章节
通过标准：
· 技术要求逐条响应，证明材料可核验，无负偏离。
· 数量要求为 24个，且响应文件一致。
· 数量要求为 14个，且响应文件一致。
- ROUND3 atoms: SRA0023, SRA0184, SRA0186, SRA0239, SRA0241
- ROUND3 owned numbers: 14个(QUANTITY), 3个(QUANTITY)
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 八、联系方式 1、采购人信息 名称：河南省水利第二工程局集团有限公司 地址：河南省郑州市经济技术开发区经北五路8 号 联系人：丁先生 联系方式：18703979494 2、采购代理机构信息 名称：河南科源水利建设工程检…；（12 分） 于等于 15%，并且接受设备安装完成验收合格后三个月内支付总货款
- ROUND3 checks: 核对安装、调试与验收标准 / 确认验收节点与招标文件一致 / 依据第34页第3.1条逐条比对响应文件对应章节 / 核对响应文件已载明：数量要求为 14个 / 核对响应文件已载明：数量要求为 3个
- ROUND3 pass criteria: 安装、调试、检测与验收节点在响应文件中逐项落实。 / 数量要求为 14个，且响应文件一致。 / 数量要求为 3个，且响应文件一致。
- why round-2 ownership was wrong: 安装、调试、检测与验收标准是否满足要求？

### BID_BOND_EVIDENCE — 保证金凭证

- ROUND2 row: 招标文件要求：3.4.1项要求提交响应保证金的，评审小组将否决其响应。
复核要点：
① 核对缴纳凭证的付款主体、收款账户与到账时间
② 核对保证金金额与形式是否符合招标文件
③ 依据第18页第3.4.1条逐条比对响应文件对应章节
通过标准：
· 不存在该条列明的否决/无效情形。
不满足后果：3.4.1项要求提交响应保证金的，评审小组将否决其响应。
- ROUND3 atoms: SRA0097
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: 否决
- ROUND3 requirement: 3.4.1项要求提交响应保证金的，评审小组将否决其响应。
- ROUND3 checks: 核对保证金凭证 / 确认凭证已放入响应文件对应位置 / 依据第18页第3.4.1条逐条比对响应文件对应章节
- ROUND3 pass criteria: 保证金凭证放入响应文件，可核验。
- why round-2 ownership was wrong: 保证金凭证是否放入响应文件？

### CONTRACT_PAYMENT — 合同付款与结算

- ROUND2 row: (no matching round-2 row)
- ROUND3 atoms: SRA0049.1, SRA0049.2, SRA0134, SRA0172, SRA0231
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 3、支付时间：领取《成交通知书》时缴纳。；缴纳账
- ROUND3 checks: 核对合同付款条款响应 / 核对付款方式、结算依据与付款条件 / 依据第22页第7.4.1条逐条比对响应文件对应章节
- ROUND3 pass criteria: 付款方式、结算依据与付款条件在响应文件中被接受。
- why round-2 ownership was wrong: 付款方式、结算依据与付款条件是否可接受？

### EVALUATION_SCORING — 评分标准与分值构成

- ROUND2 row: 招标文件要求：第三章“评审办法”没有规定的方法、评审因素和标准，不作为评审依据。；在评审活动中，评审 小组成员不得擅离职守，影响评审程序正常进行，不得使用第三章《评审办法》没有规 定的评审因素和标准进行评审。
复核要点：
① 将评分因素拆解为得分条件、证明材料、响应文件页码与预估得分
② 确认每一项评分因素都有对应响应内容
③ 依据第21页逐条比对响应文件对应章节
④ 核对响应文件已载明：该评分因素最高 1分
通过标准：
· 每个评分因素都有对应响应内容与证明材料，预估得分可追溯。
· 该评分因素最高 1分，且响应文件一致。
准备材料：法定代表人授权委托书、投标报价表/开标一览表
评分提示：按
- ROUND3 atoms: SRA0050, SRA0129, SRA0143, SRA0155, SRA0156
- ROUND3 owned numbers: 95%(PAYMENT_RATIO), 5%(PAYMENT_RATIO), 1分(SCORE)
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 款 95%（5%质保金质保期满无息支付）的得 12 分；；（12 分） 95%（5%质保金质保期满无息支付）的得 8 分；
- ROUND3 checks: 将评分因素拆解为得分条件、证明材料与页码 / 确认每项都有对应响应内容 / 依据第21页逐条比对响应文件对应章节 / 核对响应文件已载明：付款/计分比例为 95% / 核对响应文件已载明：付款/计分比例为 5% / 核对响应文件已载明：该评分因素最高 1分
- ROUND3 pass criteria: 每个评分因素都有对应响应内容与证明材料。 / 付款/计分比例为 95%，且响应文件一致。 / 付款/计分比例为 5%，且响应文件一致。 / 该评分因素最高 1分，且响应文件一致。
- why round-2 ownership was wrong: 每个评分因素如何得分、需要什么证明？

### EVALUATION_COLLUSION — 评审·串标与弄虚作假

- ROUND2 row: 招标文件要求：投标人投标文件制作机器码一致视为串通投标行为；9.2 对供应商的纪律要求 供应商不得相互串通响应或与采购人串通响应，不得向采购人或者评审小组成员行 贿谋取成交，不得以他人名义响应或者以其他方式弄虚作假骗取成交；
复核要点：
① 核验业绩、证书、人员材料的真实性
② 排查与其他投标人文件、联系信息、制作信息雷同等情形
③ 依据第22页第9.2条逐条比对响应文件对应章节
通过标准：
· 不存在该条列明的否决/无效情形。
- ROUND3 atoms: SRA0051, SRA0140, SRA0160, SRA0205
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 投标人投标文件制作机器码一致视为串通投标行为；9.2 对供应商的纪律要求 供应商不得相互串通响应或与采购人串通响应，不得向采购人或者评审小组成员行 贿谋取成交，不得以他人名义响应或者以其他方式弄虚作假骗取成交；
- ROUND3 checks: 核对不存在串标、弄虚作假的证据 / 确认响应文件无雷同与异常一致 / 依据第22页第9.2条逐条比对响应文件对应章节
- ROUND3 pass criteria: 不存在串标、弄虚作假情形。
- why round-2 ownership was wrong: 是否存在串标、弄虚作假情形？

### QUALIFICATION_RELATIONSHIP_RESTRICTION — 资格·关联关系限制

- ROUND2 row: 招标文件要求：2.3 供应商被列入“中国执行信息公开网（https://zxgk.court.gov.cn/shixin） 一全国法院失信被执行人名单信息公布与查询平台-失信被执行人”的、“中国政府采 购网（https://www.…；1.5.3 供应商不得存在下列情形之一： （1）与采购人存在利害关系且可能影响采购公正性；
复核要点：
① 在招标文件指定平台查询并留存查询结果截图
② 确认不存在失信被执行人、严重违法失信等禁止性记录
③ 依据第6页第2.3条逐条比对响应文件对应章节
通过标准：
· 不存在该条列明的否决/无效情形。
准备材料：指定平台查询结果截图
- ROUND3 atoms: SRA0008, SRA0011, SRA0072, SRA0292, SRA0293
- ROUND3 owned numbers: —
- ROUND3 owned materials: 信用查询截图
- ROUND3 consequence: 不得参加
- ROUND3 requirement: 2.3 供应商被列入“中国执行信息公开网（https://zxgk.court.gov.cn/shixin） 一全国法院失信被执行人名单信息公布与查询平台-失信被执行人”的、“中国政府采 购网（https://www.…；2.4 单位负责人为同一人或者存在直接控股、管理关系的不同供应商，不得参加同 一合同项下的采购活动。
- ROUND3 checks: 核对不存在关联关系禁止情形 / 确认声明或证明材料齐全 / 依据第6页第2.3条逐条比对响应文件对应章节
- ROUND3 pass criteria: 不存在单位负责人同一人或控股、管理关系等禁止情形。
- why round-2 ownership was wrong: 是否存在单位负责人同一人或控股、管理关系等禁止情形？

### PROJECT_WARRANTY — 项目/产品质保

- ROUND2 row: 招标文件要求：款 95%（5%质保金质保期满无息支付）的得 12 分； 2、预付款比例小；准 质保期 质保期 符合第二章“供应商须知”第 1.4.8 款规定
复核要点：
① 核对质保期承诺与质保范围
② 确认响应方式、费用承担与招标文件一致
③ 依据第24页逐条比对响应文件对应章节
④ 与项目事实核对：质量要求 符合国家及行业有关标准、规范和询比文件要求（第9页）
通过标准：
· 质保期与质保范围不低于规定期限。
准备材料：类似项目合同及验收证明
- ROUND3 atoms: SRA0004, SRA0026, SRA0069, SRA0169, SRA0183.2
- ROUND3 owned numbers: 24个月(WARRANTY_MONTHS)
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 1.4.8 质保期 24 个月（自工程完工验收合格之日起算）；准 质保期 质保期 符合第二章“供应商须知”第 1.4.8 款规定
- ROUND3 checks: 核对响应文件中的质保期与质保范围 / 确认起算点与覆盖范围符合要求 / 依据第24页逐条比对响应文件对应章节 / 核对响应文件已载明：质保期不低于 24个月
- ROUND3 pass criteria: 项目/产品质保期与质保范围符合招标文件要求。 / 质保期不低于 24个月，且响应文件一致。
- why round-2 ownership was wrong: 项目/产品质保期与范围是否满足要求？

### RETENTION_RELEASE_PERIOD — 质保金释放期限

- ROUND2 row: 招标文件要求：1.12 分包 是否允许分包：见供应商须知前附表。
复核要点：
① 确认响应文件无违规分包、转包安排
② 如允许分包，核对分包范围符合招标文件限制
③ 依据第16页第1.12条逐条比对响应文件对应章节
通过标准：
· 无违规分包、转包、挂靠情形。
- ROUND3 atoms: SRA0235
- ROUND3 owned numbers: 12个月(WARRANTY_MONTHS)
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 作为质保金，质保期 12 个月，质保期满后无息付清余款。
- ROUND3 checks: 核对质保金/尾款释放期限与条件 / 确认与合同条款一致 / 依据第33页逐条比对响应文件对应章节 / 核对响应文件已载明：质保期不低于 12个月
- ROUND3 pass criteria: 质保金/尾款释放期限与条件在响应文件中明确。 / 质保期不低于 12个月，且响应文件一致。
- why round-2 ownership was wrong: 质保金/尾款返还或释放期限及条件是否清楚？

### ELECTRONIC_UPLOAD — 电子上传与加密

- ROUND2 row: 招标文件要求：供应商须使用电子交易系统提供的投标文件制作工具进行电子响应文件的制作，并在提 交响应文件截止时间前通过“河南国企阳光招采服务平台”上传经CA 密钥签章和加密 的电子响应文件（.EJYTF 格式），加密电子响应文件逾期上…
复核要点：
① 逐页核对招标文件指定位置的签字、盖章、电子签章是否齐全
② 核对签署人与授权委托书上的被授权人是否一致
③ 依据第7页逐条比对响应文件对应章节
通过标准：
· 不存在该条列明的否决/无效情形。
不满足后果：供应商须使用电子交易系统提供的投标文件制作工具进行电子响应文件的制作，并在提 交响应文件截止时间前通过“河南国企阳光招采服务平台”上传经CA 
- ROUND3 atoms: SRA0019, SRA0108, SRA0112, SRA0117, SRA0118
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: 不予受理
- ROUND3 requirement: 供应商须使用电子交易系统提供的投标文件制作工具进行电子响应文件的制作，并在提 交响应文件截止时间前通过“河南国企阳光招采服务平台”上传经CA 密钥签章和加密 的电子响应文件（.EJYTF 格式），加密电子响应文件逾期上…；3.7.3 响应文件全部采用电子文档，除供应商须知前附表另有规定外，响应文件所 附证书证件均为原件扫描件，并采用单位和个人数字证书，按询…
- ROUND3 checks: 核对电子文件加密与上传记录 / 确认上传成功且文件完整 / 依据第7页逐条比对响应文件对应章节
- ROUND3 pass criteria: 电子文件按规定加密并上传成功。
- why round-2 ownership was wrong: 电子文件是否按规定加密/上传成功？

### TECHNICAL_PARAMETER — 技术参数与配置

- ROUND2 row: 招标文件要求：进出水口各预留1 米不锈钢管含配套法兰、螺栓，以便于泵站外部管网对接 *流量计等相关计量仪器需提供第三方校检证书 二、采购范围：包含但不限于供货、包装、运输、保险、装车、配合验收、安装、调试 以及质量保证等伴随服务。；注：提供合同协议书复印件、材料清单复印件（若合同协议书中已
复核要点：
① 核对接口、协议与平台对接的技术方案
② 确认方案可实施并附承诺
③ 依据第39页逐条比对响应文件对应章节
通过标准：
· 技术要求逐条响应，证明材料可核验，无负偏离。
准备材料：类似项目合同及验收证明
- ROUND3 atoms: SRA0179, SRA0240, SRA0264, SRA0266
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 注：提供合同协议书复印件、材料清单复印件（若合同协议书中已；3.1 供应商提供设备应遵照国家和部颁发的下列标准、规程和规范： （1）《二次供水工程技术规程》CJJ140-2018 （2）《室外给水设计规范》GB50013-2018 （3）《建筑给水排水设计规范》GB50015-…
- ROUND3 checks: 逐条核对技术参数响应 / 确认无负偏离并标注证明材料位置 / 依据第39页逐条比对响应文件对应章节
- ROUND3 pass criteria: 技术参数逐条响应，无负偏离。
- why round-2 ownership was wrong: 技术参数是否逐条响应、有无负偏离？

### QUALIFICATION_CREDIT — 资格·信用记录

- ROUND2 row: 招标文件要求：供应商需提供在“国家企业信用信息公示系统”网站 （https://www.gsxt.gov.cn/index.html）查询其企业信息、股东或投资人信息的截图。；3、供应商的“信用中国（https://www.creditchina.gov.cn/xinyongfuwu/?navPage=4） -严重失信主体名单”的查询截图。
复核要点：
① 在招标文件指定平台查询并留存查询截图
② 确认查询结果无禁止性记录且截图在有效期内取得
③ 依据第6页逐条比对响应文件对应章节
通过标准：
· 资格材料齐全有效，主体信息一致。
准备材料：指定平台查询结果截图
- ROUND3 atoms: SRA0012, SRA0294
- ROUND3 owned numbers: —
- ROUND3 owned materials: 信用查询截图
- ROUND3 consequence: —
- ROUND3 requirement: 供应商需提供在“国家企业信用信息公示系统”网站 （https://www.gsxt.gov.cn/index.html）查询其企业信息、股东或投资人信息的截图。；3、供应商的“信用中国（https://www.creditchina.gov.cn/xinyongfuwu/?navPage=4） -严重失信主体名单”的查询截图。
- ROUND3 checks: 核对信用查询截图 / 确认查询时间与查询结果满足要求 / 依据第6页逐条比对响应文件对应章节
- ROUND3 pass criteria: 信用记录查询结果满足招标文件要求。
- why round-2 ownership was wrong: 信用记录查询结果是否满足要求？


## Manual-style audit (deterministic 20-row sample)

### BID_BOND_AMOUNT — 保证金金额

1. 要求: 3.4.1 响应保证金 响应保证金的金额：人民币贰万元整。；响应保证金的递交截止时间：同提交响应文件截止
2. 复核: 核对响应文件中的保证金金额 确认凭证金额与招标文件一致 依据第24页逐条比对响应文件对应章节
3. 通过: 保证金金额与招标文件规定一致。
4. 证据: SRA0032, SRA0034, SRA0098
5. 同一决策: yes

### BID_BOND_EVIDENCE — 保证金凭证

1. 要求: 3.4.1项要求提交响应保证金的，评审小组将否决其响应。
2. 复核: 核对保证金凭证 确认凭证已放入响应文件对应位置 依据第18页第3.4.1条逐条比对响应文件对应章节
3. 通过: 保证金凭证放入响应文件，可核验。
4. 证据: SRA0097
5. 同一决策: yes

### BID_BOND_FORM — 保证金形式

1. 要求: 响应保证金的形式：银行转账方式。；3.4.1 供应商在递交响应文件的同时，应按供应商须知前附表规定的金额、形式和 第六章“响应文件格式”规定的响应保证金格式递交响应保证金，并作为其响应文件的 组成部分。
2. 复核: 核对保证金形式（电汇/转账/保函等） 确认形式符合招标文件规定 依据第10页逐条比对响应文件对应章节
3. 通过: 保证金形式符合规定，且来源合法。
4. 证据: SRA0033, SRA0095, SRA0132
5. 同一决策: yes

### BID_BOND_TRANSFER — 保证金转出账户

1. 要求: 响应保证金从供应商基本账户一次性汇入指定账 户。；境内供应商以现金或者支票形式提交的响应保证金，应当从其基本账户转出 并在响应文件中附上基本账户开户证明。
2. 复核: 核对保证金转出账户 确认从规定账户转出并留存凭证 依据第18页逐条比对响应文件对应章节
3. 通过: 保证金从规定的账户转出。
4. 证据: SRA0035, SRA0096
5. 同一决策: yes

### BID_VALIDITY — 投标有效期

1. 要求: 3.3.1 询比有效期 提交响应文件截止之日起 90 日历天；司黑名单有效期限内的供应商不得确定为中标人。
2. 复核: 核对投标函中的投标有效期 确认覆盖评审与定标全过程 依据第12页逐条比对响应文件对应章节 核对响应文件已载明：投标有效期不少于 90日历天
3. 通过: 投标有效期达到规定天数，且覆盖评审与定标全过程。 投标有效期不少于 90日历天，且响应文件一致。
4. 证据: SRA0031, SRA0047, SRA0093
5. 同一决策: yes

### CONSORTIUM — 联合体

1. 要求: 1.5.2 是否接受联合体响应：不接受。
2. 复核: 核对投标主体形式 确认与联合体规定一致 依据第6页第2.6条逐条比对响应文件对应章节
3. 通过: 响应文件的投标主体形式与招标文件关于联合体的规定一致。
4. 证据: SRA0015, SRA0071
5. 同一决策: yes

### CONTRACT_PAYMENT — 合同付款与结算

1. 要求: 3、支付时间：领取《成交通知书》时缴纳。；缴纳账
2. 复核: 核对合同付款条款响应 核对付款方式、结算依据与付款条件 依据第22页第7.4.1条逐条比对响应文件对应章节
3. 通过: 付款方式、结算依据与付款条件在响应文件中被接受。
4. 证据: SRA0049.1, SRA0049.2, SRA0134
5. 同一决策: yes

### CONTRACT_RISK — 合同风险与违约责任

1. 要求: 采购人 将依序确定排名第一的成交候选供应商为成交人，若第一成交候选供应商放弃成交、因 不可抗力不能履行合同、或者被查实存在影响成交结果的违法行为等情形，不符合成交 条件的，采购人可以按照评审小组提出的成交候选人名单排序…；成交人无正当理由拒签合同的，采购人取消其成交资格， 给采购人造成损失的，成交人还应当予以赔偿。
2. 复核: 核对违约、索赔与争议条款响应 确认无采购人不能接受的附加条件 依据第22页逐条比对响应文件对应章节
3. 通过: 不存在采购人不能接受的附加条件或未响应风险条款。
4. 证据: SRA0131, SRA0135, SRA0136
5. 同一决策: yes

### DELIVERY_LOCATION — 交付地点

1. 要求: 准 交货地点 交货地点 符合第二章“供应商须知”第 1.4.6 款规定
2. 复核: 核对交付地点与实施范围 确认与招标文件一致 依据第24页逐条比对响应文件对应章节
3. 通过: 交付地点与实施范围符合招标文件要求。
4. 证据: SRA0063, SRA0067, SRA0167
5. 同一决策: yes

### DELIVERY_PERIOD — 工期与供货期

1. 要求: 7、供货期：合同签订后30 日历天。；1.4.5 供货期 签订合同后 30 日历天。
2. 复核: 核对响应函与进度计划中的工期/供货期 确认覆盖全部交付与验收节点 依据第24页逐条比对响应文件对应章节 核对响应文件已载明：工期/供货期满足 30日历天 核对响应文件已载明：工期/供货期满足 30天
3. 通过: 工期/供货期达到规定期限，且覆盖全部交付节点。 工期/供货期满足 30日历天，且响应文件一致。 工期/供货期满足 30天，且响应文件一致。
4. 证据: SRA0002, SRA0024, SRA0066
5. 同一决策: yes

### ELECTRONIC_UPLOAD — 电子上传与加密

1. 要求: 供应商须使用电子交易系统提供的投标文件制作工具进行电子响应文件的制作，并在提 交响应文件截止时间前通过“河南国企阳光招采服务平台”上传经CA 密钥签章和加密 的电子响应文件（.EJYTF 格式），加密电子响应文件逾期上…；3.7.3 响应文件全部采用电子文档，除供应商须知前附表另有规定外，响应文件所 附证书证件均为原件扫描件，并采用单位和个人数字证书，按询…
2. 复核: 核对电子文件加密与上传记录 确认上传成功且文件完整 依据第7页逐条比对响应文件对应章节
3. 通过: 电子文件按规定加密并上传成功。
4. 证据: SRA0019, SRA0108, SRA0112
5. 同一决策: yes

### EVALUATION_COLLUSION — 评审·串标与弄虚作假

1. 要求: 投标人投标文件制作机器码一致视为串通投标行为；9.2 对供应商的纪律要求 供应商不得相互串通响应或与采购人串通响应，不得向采购人或者评审小组成员行 贿谋取成交，不得以他人名义响应或者以其他方式弄虚作假骗取成交；
2. 复核: 核对不存在串标、弄虚作假的证据 确认响应文件无雷同与异常一致 依据第22页第9.2条逐条比对响应文件对应章节
3. 通过: 不存在串标、弄虚作假情形。
4. 证据: SRA0051, SRA0140, SRA0160
5. 同一决策: yes

### EVALUATION_RESPONSIVENESS — 评审·响应性审查

1. 要求: 10.8 实质性要求和条件 本表格中带“*”条款；；其中，响应函附录在满足询比文件实质性要求的基础上， 可以提出比询比文件要求更有利于采购人的承诺。
2. 复核: 核对实质性响应要求 确认无重大偏差 依据第28页第(3)条逐条比对响应文件对应章节
3. 通过: 实质性响应要求全部满足，无重大偏差。
4. 证据: SRA0053, SRA0106, SRA0188
5. 同一决策: yes

### EVALUATION_SCORING — 评分标准与分值构成

1. 要求: 款 95%（5%质保金质保期满无息支付）的得 12 分；；（12 分） 95%（5%质保金质保期满无息支付）的得 8 分；
2. 复核: 将评分因素拆解为得分条件、证明材料与页码 确认每项都有对应响应内容 依据第21页逐条比对响应文件对应章节 核对响应文件已载明：付款/计分比例为 95% 核对响应文件已载明：付款/计分比例为 5% 核对响应文件已载明：该评分因素最高 1分
3. 通过: 每个评分因素都有对应响应内容与证明材料。 付款/计分比例为 95%，且响应文件一致。 付款/计分比例为 5%，且响应文件一致。 该评分因素最高 1分，且响应文件一致。
4. 证据: SRA0050, SRA0129, SRA0143
5. 同一决策: yes

### FILE_COMPOSITION — 响应文件组成

1. 要求: 如有疑问，应按照供应商须知前附表规定的时间前以书 面形式（包括信函、电报、传真等可以有形地表现所载内容的形式，下同），要求采购 人对询比文件予以澄清，否则由此引起的任何后果均由供应商自己承担，采购人和采购 代理机构不承…；评审小组成员人数以及技术、经济等方面专家的确定方式 见供应商须知前附表。
2. 复核: 按招标文件要求的组成部分逐项清点 确认无缺项、无多余替代件 依据第20页第6.1.2条逐条比对响应文件对应章节
3. 通过: 响应文件组成齐全，与招标文件要求的组成部分一致。
4. 证据: SRA0081, SRA0127, SRA0128
5. 同一决策: yes

### FILE_FORMAT — 响应文件格式

1. 要求: (6) 响应文件格式。；3.1.1 详见第六章“响应文件格式”。
2. 复核: 核对格式、装订、目录与页码 确认符合响应文件格式规定 依据第17页第(6)条逐条比对响应文件对应章节
3. 通过: 格式、装订、目录与页码符合招标文件要求。
4. 证据: SRA0080, SRA0088, SRA0103
5. 同一决策: yes

### GENERAL_BIDDER_OBLIGATION — 一般投标人义务

1. 要求: 完成注册后进行供应商登录，再点击【招采服务平台】-【招标采购】（页 面跳转）至“e招投标交易平台”，在此业务系统进行账号绑定后，首先需要供应商完 善诚信库信息，然后点击【采购业务】-【采购公告】，查询要参加的项目公告信…；成交人 否，推荐的成交候选人数：1-3 名
2. 复核: 核对该条款对应的响应内容 确认响应完整、可核验 依据第18页逐条比对响应文件对应章节
3. 通过: 响应文件对该条款作出可核验的对应响应。
4. 证据: SRA0016, SRA0039, SRA0048
5. 同一决策: yes

### INTERNAL_PROCEDURE — 采购方内部程序

1. 要求: 〔采购人内部程序/定义条款，仅备查，无需投标响应〕面的专家 2 人，共 3 人组成。；在评 审活动中，与评审活动有关的工作人员不得擅离职守，影响评审程序正常进行。
2. 复核: 确认该条属于采购人内部程序或术语定义，无需投标人响应 仅作背景备查，不作为废标/评分依据 依据第22页逐条比对响应文件对应章节
3. 通过: 该条款的响应内容在响应文件中可核验，且与要求一致。
4. 证据: SRA0038, SRA0145, SRA0228
5. 同一决策: yes

### OPENING_DECRYPTION — 开标与解密

1. 要求: 供应商登录“远程开标大厅”后，先进行签到，其后应一直 保持在线状态，保证能准时参加响应文件的解密、答疑澄清等活动。
2. 复核: 核对签到与解密时间 确认在规定时间内完成解密 依据第7页逐条比对响应文件对应章节
3. 通过: 在规定时间内完成签到与解密。
4. 证据: SRA0022
5. 同一决策: yes

### PRICE_ARITHMETIC — 报价算术与大小写

1. 要求: 等） 如因图纸、施工环境、业主要求变更导致实际采购内容发生变更，与表中差距较大的， 乙方表示理解，并同意按照表中单价与实际使用数量结算，不得以此作为调价和索赔依 据。
2. 复核: 核对大小写金额 核对单价×数量与分项合计、总价 依据第32页逐条比对响应文件对应章节
3. 通过: 大小写金额一致，单价×数量等于合计，分项合计与总价一致。
4. 证据: SRA0230
5. 同一决策: yes
