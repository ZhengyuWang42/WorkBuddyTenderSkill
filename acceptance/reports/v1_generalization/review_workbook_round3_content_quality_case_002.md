# Round-3 review-workbook content quality — case_002

- result: **PASS**
- pipeline: `SourceRequirementAtom -> ReviewConcern -> ReviewPoint`
- invariant: PROVENANCE IS NECESSARY BUT NOT SUFFICIENT (source-backed AND same concern)
- source atoms: 690 · concerns: 44 · review points: 44
- mismatch: source 0 · numeric 0 · material 0 · consequence 0 · evidence 0 · authority 0
- false conflicts: 0 · true conflicts: 3 · naive keyword conflicts avoided: 1
- fixture A–N: 14/14 PASS
- warranty/retention fixture: PASS
- manual-style audit: 20/20 coherent
- round-2 → round-3 examples: 16

## Warranty / retention

- project warranty: PROJECT_WARRANTY = 3年, 2年 (WARRANTY_MONTHS) from n/a
- retention money: RETENTION_MONEY_RATIO = (not present in this case)
- retention release: RETENTION_RELEASE_PERIOD = (not present in this case)
- reported as conflict: False

## Fixtures A–N

| fixture | label | result | old concern | new concern | atoms |
| --- | --- | --- | --- | --- | --- |
| A | signature vs electronic upload | PASS | SIGNATURE (from CA/upload text) | SIGNATURE_AND_SEAL / ELECTRONIC_UPLOAD | SRA0003, SRA0007, SRA0024 |
| B | submission contamination | PASS | SUBMISSION (with 评审报告/0元) | SUBMISSION_DEADLINE / SUBMISSION_PLATFORM / SUBMISSION_COPIES | SRA0010, SRA0030.1, SRA0031 |
| C | file composition evidence | PASS | FILE_COMPOSITION (from 异议函 text) | FILE_COMPOSITION | SRA0264 |
| D | file format evidence | PASS | FILE_FORMAT (from 备选方案/联系方式) | FILE_FORMAT | — |
| E | technical plan evidence | PASS | TECHNICAL_PLAN (from supplier definition / site visit) | TECHNICAL_PLAN | SRA0012, SRA0018, SRA0077 |
| F | financial commitment ownership | PASS | QUALIFICATION_FINANCIAL (from 资金来源：企业自筹) | QUALIFICATION_FINANCIAL / PROJECT_BASIC_INFO | SRA0083, SRA0338, SRA0491 |
| G | installation quantities | PASS | TECHNICAL/安装调试与验收 (any nearby quantity) | TECHNICAL_INSTALLATION | SRA0019, SRA0021, SRA0201 |
| H | bid-bond material isolation | PASS | BID_BOND (with experience/authorization materials) | BID_BOND_AMOUNT / FORM / TRANSFER / DEADLINE / EVIDENCE | SRA0040, SRA0041, SRA0047 |
| I | contract/payment contamination | PASS | CONTRACT_PAYMENT (with relationship restrictions) | CONTRACT_PAYMENT / CONTRACT_RISK / CONTRACT_DELIVERY / CONTRACT_ACCEPTANCE | SRA0074, SRA0315, SRA0316 |
| J | internal procedure filtering | PASS | bidder rows from 评审小组回避/纪律/术语定义 | filtered, or an explicit non-bidder 备查 row | SRA0160, SRA0173, SRA0175 |
| K | false price-limit concern | PASS | PRICING/分项限价与暂列金额 (from a heading) | PRICE_ITEMIZATION (only with limit/amount evidence) | — |
| L | scoring ownership | PASS | EVALUATION (generic method text) | EVALUATION_SCORING | SRA0057, SRA0151, SRA0152 |
| M | mixed evaluation split | PASS | EVALUATION (串标 + 银行承兑 combined) | EVALUATION_COLLUSION vs EVALUATION_SCORING | SRA0057, SRA0151, SRA0152 |
| N | technical vs eligibility/rejection | PASS | TECHNICAL_PARAMETER (eligibility restriction) | eligibility/rejection concern | SRA0038, SRA0197, SRA0213 |

## Round-2 → Round-3 examples

### SIGNATURE_AND_SEAL — 签章要求

- ROUND2 row: 招标文件要求：3.2 法定代表人授权书（附法定代表人、被授权人身份证复印件）及被授权 人身份证复印件（法定代表人直接参加投标，须提供法定代表人身份证明及身份 证复印件）；；被授权人身份证复印件（法定代表人直接参加投标，须提供法定代表
复核要点：
① 按招标文件签章要求逐页核对签字人、盖章种类与位置
② 确认授权链条完整、印章清晰
③ 依据第4页第3.2条逐条比对响应文件对应章节
通过标准：
· 所有指定位置签字/盖章齐全有效，授权链条一致。
准备材料：营业执照副本扫描件（加盖公章）、社保缴纳证明、类似项目合同及验收证明、指定平台查询结果截图
- ROUND3 atoms: SRA0003, SRA0007, SRA0024, SRA0025, SRA0036
- ROUND3 owned numbers: —
- ROUND3 owned materials: 法定代表人授权委托书, 身份证扫描件, 纳税与社保缴纳凭证, 技术证明材料
- ROUND3 consequence: 无效
- ROUND3 requirement: 3.2 法定代表人授权书（附法定代表人、被授权人身份证复印件）及被授权 人身份证复印件（法定代表人直接参加投标，须提供法定代表人身份证明及身份 证复印件）；；4.2 获取方式：1、凡有意参加的投标人，请于文件获取时间截止时间前通 过招采通平台进行确认并将单位介绍信（或授权委托书）及经办人（或被授权人） 身份证复印件并加盖公章发送至陕西瑞通工程造价咨询有限公…
- ROUND3 checks: 按招标文件签章要求逐处核对签字人与印章 / 确认授权链条完整、印章清晰 / 依据第4页第3.2条逐条比对响应文件对应章节
- ROUND3 pass criteria: 所有指定位置的签字、盖章齐全且形式合规。
- why round-2 ownership was wrong: 哪些位置必须签字/盖章，形式是否合规？

### SUBMISSION_DEADLINE — 递交截止时间

- ROUND2 row: 招标文件要求：1.9 分包 本项目不允许分包。；2026-03-23 16:58:05 二十、分包 本合同不接受分包。
复核要点：
① 确认响应文件无违规分包、转包安排
② 如允许分包，核对分包范围符合招标文件限制
③ 依据第17页第1.9条逐条比对响应文件对应章节
通过标准：
· 无违规分包、转包、挂靠情形。
准备材料：类似项目合同及验收证明
- ROUND3 atoms: SRA0010, SRA0030.1, SRA0031, SRA0032, SRA0033
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: 拒收
- ROUND3 requirement: 5.1 递交截止时间：2026 年04 月14 日09 时30 分；提问截止时间 投标人应仔细阅读和检查招标文件的全部内容。
- ROUND3 checks: 核对递交截止时间 / 确认完成递交的时间与凭证 / 依据第9页逐条比对响应文件对应章节
- ROUND3 pass criteria: 在规定的截止时间前完成递交。
- why round-2 ownership was wrong: 是否在规定截止时间前完成递交？

### FILE_COMPOSITION — 响应文件组成

- ROUND2 row: 招标文件要求：1.22 投标文件未按规定的格式填写，或主要内容不全，或关键字迹模糊、 营收系统整合和硬件系统升级项目 无法辨认造成无法满足评标需要的；
复核要点：
① 按招标文件清单核对响应文件组成与格式
② 依据第34页第1.22条逐条比对响应文件对应章节
通过标准：
· 响应文件对应内容与该条款一致。
- ROUND3 atoms: SRA0264
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 1.22 投标文件未按规定的格式填写，或主要内容不全，或关键字迹模糊、 营收系统整合和硬件系统升级项目 无法辨认造成无法满足评标需要的；
- ROUND3 checks: 按招标文件要求的组成部分逐项清点 / 确认无缺项、无多余替代件 / 依据第34页第1.22条逐条比对响应文件对应章节
- ROUND3 pass criteria: 响应文件组成齐全，与招标文件要求的组成部分一致。
- why round-2 ownership was wrong: 响应文件应由哪些部分组成、是否齐全？

### TECHNICAL_PLAN — 技术方案与实施组织

- ROUND2 row: 招标文件要求：话：029-81871890-8019 电子邮件：rtzbgs@126.com 第二章投标人须知 投标人须知前附表；1.1.2 招标人：见投标人须知前附表。
复核要点：
① 按招标文件格式要求编排、装订并编制目录与页码
② 确认使用规定的固定格式
③ 依据第7页逐条比对响应文件对应章节
通过标准：
· 响应文件格式、组成与编排符合规定。
准备材料：法定代表人授权委托书
- ROUND3 atoms: SRA0012, SRA0018, SRA0077, SRA0085, SRA0204
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 7.1 本次招标公告在招采通平台（http://zct.xacin.com.cn/）、陕西采购 与招标网（http://www.sntba.com/）同时发布，因轻信其他组织、个人或媒体 提供的信息而造成损失的，招标人…；供货地点 实施周期：合同签订后的 18 个月之内完成全部系统的开发并投入试
- ROUND3 checks: 核对技术方案与进度计划 / 核对人员机具配置、质量措施与应急预案 / 依据第52页逐条比对响应文件对应章节
- ROUND3 pass criteria: 技术方案、进度计划、人员机具、质量与应急措施完整可实施。
- why round-2 ownership was wrong: 技术方案/进度/人员机具/质量/应急是否完整可实施？

### QUALIFICATION_FINANCIAL — 资格·财务能力

- ROUND2 row: 招标文件要求：1.2.1 本招标项目的资金来源：见投标人须知前附表。；1.2.3 本招标项目的预算金额及资金落实情况：见投标人须知前附表。
复核要点：
① 按招标文件格式出具财务能力承诺
② 核对承诺内容与招标文件要求一致
③ 依据第16页第1.2.1条逐条比对响应文件对应章节
通过标准：
· 财务材料按指定期间提供，主体名称与投标人一致。
准备材料：经审计的财务报告或财务状况承诺书
- ROUND3 atoms: SRA0083, SRA0338, SRA0491, SRA0566
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 1.2.3 本招标项目的预算金额及资金落实情况：见投标人须知前附表。；可根据财务要求，提供定制化接口开 发。
- ROUND3 checks: 核对财务审计报告或财务承诺 / 确认数据与出具主体符合要求 / 依据第16页第1.2.3条逐条比对响应文件对应章节
- ROUND3 pass criteria: 财务能力材料按要求提供且数据可核验。
- why round-2 ownership was wrong: 财务能力承诺或审计报告是否按要求提供？

### TECHNICAL_INSTALLATION — 安装调试与验收

- ROUND2 row: 招标文件要求：3、投标保证金缴纳凭证如下： 保证金交纳凭证 西安市综改试验区国企招标集采交易平台 营收系统整合和硬件系统升级项目 2026-03-23 16:58:05 九、技术方案 技术方案应包含但不限于以下内容，格式自拟： 1）…；投标保证金缴纳账户：按照“西安市综改试验区国企招标集采交易
复核要点：
① 核对付款主体、收款账户信息与到账时间
② 确认凭证按规定位置随响应文件提交
③ 依据第173页逐条比对响应文件对应章节
④ 与项目事实核对：投标保证金金额 50000（第10页）
⑤ 与项目事实核对：投标保证金形式 本项目接受所有符合国家相关规定形式的保证金（第10页）
通过标准：
· 
- ROUND3 atoms: SRA0019, SRA0021, SRA0201, SRA0202, SRA0203
- ROUND3 owned numbers: —
- ROUND3 owned materials: 技术证明材料
- ROUND3 consequence: —
- ROUND3 requirement: 运行，其中：开发周期 6 个月，各现场系统安装、接驳及调试完成时；1.3.3 质量要求 符合国家现行相关规定及验收规范的合格标准。
- ROUND3 checks: 核对安装、调试与验收标准 / 确认验收节点与招标文件一致 / 依据第49页逐条比对响应文件对应章节
- ROUND3 pass criteria: 安装、调试、检测与验收节点在响应文件中逐项落实。
- why round-2 ownership was wrong: 安装、调试、检测与验收标准是否满足要求？

### BID_BOND_EVIDENCE — 保证金凭证

- ROUND2 row: 招标文件要求：八、工期要求及系统建设地点 1.合同签订后新整合营收系统完成之前必须保证现状营业收费系统可靠运 行，合同签订后的18 个月之内完成全部系统的开发并投入试运行。；3.4.1 合同签订后新整合营收系统完成之前必须保证现状营业收费系统可 2026-03-23 16:58:05 靠运行，合同签订后的18 个月之内完成全部系统的开发并投入试运行。
复核要点：
① 核对数据迁移范围与迁移方案
② 核对上线切换与回退预案
③ 依据第51页第八、条逐条比对响应文件对应章节
通过标准：
· 技术要求逐条响应，证明材料可核验，无负偏离。
· 数量要求为 6个，且响应文件一致。
· 数量要求为 18个
- ROUND3 atoms: SRA0043, SRA0051, SRA0109, SRA0111, SRA0122
- ROUND3 owned numbers: —
- ROUND3 owned materials: 响应保证金转账凭证
- ROUND3 consequence: —
- ROUND3 requirement: 投标保证金缴纳账户：按照“西安市综改试验区国企招标集采交易；注意事项：投标保证金缴纳成功后，在投标文件编制时附缴存凭证。
- ROUND3 checks: 核对保证金凭证 / 确认凭证已放入响应文件对应位置 / 依据第173页逐条比对响应文件对应章节
- ROUND3 pass criteria: 保证金凭证放入响应文件，可核验。
- why round-2 ownership was wrong: 保证金凭证是否放入响应文件？

### CONTRACT_PAYMENT — 合同付款与结算

- ROUND2 row: 招标文件要求：拟派团队成员（项目经 理除外）应包含： （3）系统集成项目管理工程师中级及以上证书；；2026-03-23 16:58:05 9.当合同期满之后，乙方须提供全面的技术支持，若不需要乙方维护则不收 取系统维护费用，若需要乙方对系统进行二次开发，甲乙双方根据开发工作量拟 定补充协议。
复核要点：
① 核对接口、协议与平台对接的技术方案
② 确认方案可实施并附承诺
③ 依据第29页逐条比对响应文件对应章节
通过标准：
· 技术要求逐条响应，证明材料可核验，无负偏离。
· 数量要求为 8个，且响应文件一致。
准备材料：类似项目合同及验收证明、法定代表人授权委托书
- ROUND3 atoms: SRA0164, SRA0274, SRA0276, SRA0277, SRA0282
- ROUND3 owned numbers: 97%(PAYMENT_RATIO)
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: （3）项目试运行期满后，由乙方委托第三方评估机构并支付相关评估费用， 进行项目评估，第三方评估机构出具评估合格报告后,并经甲方组织竣工验收合 格后，支付至结算价款的97%；；7.8.1 招标人和中标单位应当在中标通知书发出之日起30 日内，根据招标 文件和中标单位的投标文件订立书面合同。
- ROUND3 checks: 核对合同付款条款响应 / 核对付款方式、结算依据与付款条件 / 依据第25页第7.8.1条逐条比对响应文件对应章节 / 核对响应文件已载明：付款/计分比例为 97%
- ROUND3 pass criteria: 付款方式、结算依据与付款条件在响应文件中被接受。 / 付款/计分比例为 97%，且响应文件一致。
- why round-2 ownership was wrong: 付款方式、结算依据与付款条件是否可接受？

### EVALUATION_SCORING — 评分标准与分值构成

- ROUND2 row: 招标文件要求：6.3.1 评标委员会按照第三章“评标办法”规定的方法、评审因素、标准和 程序对投标文件进行评审。；第三章“评标办法”没有规定的方法、评审因素和标 准，不作为评标依据。
复核要点：
① 将评分因素拆解为得分条件、证明材料、响应文件页码与预估得分
② 确认每一项评分因素都有对应响应内容
③ 依据第23页第6.3.1条逐条比对响应文件对应章节
④ 核对响应文件已载明：该评分因素最高 100分
⑤ 核对响应文件已载明：该评分因素最高 1分
通过标准：
· 每个评分因素都有对应响应内容与证明材料，预估得分可追溯。
· 该评分因素最高 100分，且响应文件一致。
· 该评分因素最高 1分，
- ROUND3 atoms: SRA0057, SRA0151, SRA0152, SRA0159, SRA0181
- ROUND3 owned numbers: 3名(PERSON_COUNT), 100分(SCORE), 1分(SCORE)
- ROUND3 owned materials: —
- ROUND3 consequence: 不得分
- ROUND3 requirement: 的人数 按最终得分由高到低的顺序选取前 3 名为中标候选人。；6.3.1 评标委员会按照第三章“评标办法”规定的方法、评审因素、标准和 程序对投标文件进行评审。
- ROUND3 checks: 将评分因素拆解为得分条件、证明材料与页码 / 确认每项都有对应响应内容 / 依据第23页第6.3.1条逐条比对响应文件对应章节 / 核对响应文件已载明：人员配备数量为 3名 / 核对响应文件已载明：该评分因素最高 100分 / 核对响应文件已载明：该评分因素最高 1分
- ROUND3 pass criteria: 每个评分因素都有对应响应内容与证明材料。 / 人员配备数量为 3名，且响应文件一致。 / 该评分因素最高 100分，且响应文件一致。 / 该评分因素最高 1分，且响应文件一致。
- why round-2 ownership was wrong: 每个评分因素如何得分、需要什么证明？

### EVALUATION_COLLUSION — 评审·串标与弄虚作假

- ROUND2 row: 招标文件要求：7.5.2 若排名第一的中标候选人放弃中标、因不可抗力不能履行合同、不按 照招标文件要求提交履约保证金、或招标人对中标候选人组织核验时发现存在弄 虚作假围标串标等违法情形，不符合中标条件的，其投标保证金不予退还，招标…；7.5.3 重点核查的异常投标情形： （一）法律法规规定视为串通投标的情形；
复核要点：
① 核验业绩、证书、人员材料的真实性
② 排查与其他投标人文件、联系信息、制作信息雷同等情形
③ 依据第25页第9.2条逐条比对响应文件对应章节
通过标准：
· 不存在该条列明的否决/无效情形。
准备材料：资质/许可证书扫描件、经审计的财务报告或财务状况承诺书、类似项目合同及
- ROUND3 atoms: SRA0161, SRA0162, SRA0171, SRA0236, SRA0256
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 7.5.3 重点核查的异常投标情形： （一）法律法规规定视为串通投标的情形；；（四）通过受让、租借、挂靠资质投标，伪造、变造资质、资格证书或者其 他许可证件，提供虚假业绩、奖项、项目负责人等材料。
- ROUND3 checks: 核对不存在串标、弄虚作假的证据 / 确认响应文件无雷同与异常一致 / 依据第25页第9.2条逐条比对响应文件对应章节
- ROUND3 pass criteria: 不存在串标、弄虚作假情形。
- why round-2 ownership was wrong: 是否存在串标、弄虚作假情形？

### QUALIFICATION_RELATIONSHIP_RESTRICTION — 资格·关联关系限制

- ROUND2 row: 招标文件要求：投标人的澄清、说明或者 2026-03-23 16:58:05 更正不得超出投标文件的范围或者改变投标文件的实质性内容。；投标人不得以任何方式干扰、影响评标工作。
复核要点：
① 按招标文件程序性要求逐项准备并核对响应文件
② 依据第23页逐条比对响应文件对应章节
通过标准：
· 响应文件对应内容与该条款一致。
- ROUND3 atoms: SRA0005, SRA0091, SRA0642
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 1.4.3 投标人不得存在下列情形之一： （1）与招标人存在利害关系且可能影响招标公正性；；(提供网站查 询截图并加盖公章) 西安市综改试验区国企招标集采交易平台 营收系统整合和硬件系统升级项目 2026-03-23 16:58:05 4、投标单位负责人为同一人或者存在直接控股、管理关系的不同投标人，不得 同…
- ROUND3 checks: 核对不存在关联关系禁止情形 / 确认声明或证明材料齐全 / 依据第5页第3.5条逐条比对响应文件对应章节
- ROUND3 pass criteria: 不存在单位负责人同一人或控股、管理关系等禁止情形。
- why round-2 ownership was wrong: 是否存在单位负责人同一人或控股、管理关系等禁止情形？

### PROJECT_WARRANTY — 项目/产品质保

- ROUND2 row: 招标文件要求：2.质保期内乙方应为甲方提供免费维修服务，确保甲方每周7天每天24小时 随时可向乙方提出故障诊断、恢复请求，并在2小时内得到响应。；2、其他约定:中标后商定 三、质量保修责任 1、质保期内乙方应为甲方提供免费维修服务，确保甲方每周7 天每天24 小时随时可向乙方提出故障诊断、恢复请求，并在2 小时内得到响应。
复核要点：
① 核对质保期承诺与质保范围
② 确认响应方式、费用承担与招标文件一致
③ 依据第8页逐条比对响应文件对应章节
④ 核对响应文件已载明：质保期不低于 3年
⑤ 核对响应文件已载明：质保期不低于 2年
⑥ 核对响应文件已载明：服务响应时间不超过 7天
⑦ 与项目事
- ROUND3 atoms: SRA0022, SRA0029, SRA0088, SRA0098, SRA0275
- ROUND3 owned numbers: 3年(WARRANTY_MONTHS), 2年(WARRANTY_MONTHS)
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 部分质保 3 年，软件部分质保 2 年。；要求和条件 实施周期、供货地点、质保期、付款方式、结算原则不允许负偏离
- ROUND3 checks: 核对响应文件中的质保期与质保范围 / 确认起算点与覆盖范围符合要求 / 依据第9页逐条比对响应文件对应章节 / 核对响应文件已载明：质保期不低于 3年 / 核对响应文件已载明：质保期不低于 2年
- ROUND3 pass criteria: 项目/产品质保期与质保范围符合招标文件要求。 / 质保期不低于 3年，且响应文件一致。 / 质保期不低于 2年，且响应文件一致。
- why round-2 ownership was wrong: 项目/产品质保期与范围是否满足要求？

### RETENTION_RELEASE_PERIOD — 质保金释放期限

- ROUND2 row: 招标文件要求：投诉 西安市综改试验区国企招标集采交易平台 应当有明确的请求和必要的证明材料。；专用条款 一、合同文件 本合同所附下列文件是构成本合同不可分割的部分： （三）合同格式及条款 （四）招投标过程有关澄清、说明或者补正文件 （五）中标通知书 （六）本合同附件 西安市综改试验区国企招标集采交易平台 二、项…
复核要点：
① 按平台要求完成加密、上传与解密演练
② 确认文件格式、大小与上传区域符合要求
③ 依据第26页逐条比对响应文件对应章节
准备材料：类似项目合同及验收证明、法定代表人授权委托书、培训方案
- ROUND3 atoms: SRA0337, SRA0565
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: （4）结算价款的3%作为质保金，硬件部分质保期满后一次性(无息)予以支 付。；西安市综改试验区国企招标集采交易平台 （4）结算价款的3%作为质保金，硬件部分质保期满后一次性(无息)予以支 付。
- ROUND3 checks: 核对质保金/尾款释放期限与条件 / 确认与合同条款一致 / 依据第50页第（4）条逐条比对响应文件对应章节
- ROUND3 pass criteria: 质保金/尾款释放期限与条件在响应文件中明确。
- why round-2 ownership was wrong: 质保金/尾款返还或释放期限及条件是否清楚？

### ELECTRONIC_UPLOAD — 电子上传与加密

- ROUND2 row: 招标文件要求：7.2.4 投标人使用“招采通电脑端软件”打开招标文件，并按照操作手册提 示进行投标文件的编制，CA 加密，在投标截止时间前通过招采通平台进行文件 上传递交，按系统提示完成开标流程。；3.7.4 投标人使用“招采通电脑端软件”打开招标文件，并按照操作手册提 示进行投标文件的编制，CA 加密，在投标截止时间前通过招采通平台进行文件 上传递交，按系统提示完成开…
复核要点：
① 验证CA介质/数字证书在有效期内且为投标人本单位证书
② 核对电子签章位置与签章后文件的可验证性
③ 依据第6页第7.2.4条逐条比对响应文件对应章节
通过标准：
· CA介质有效、文件加密上传成功、可按时解
- ROUND3 atoms: SRA0009, SRA0011, SRA0013, SRA0014, SRA0054
- ROUND3 owned numbers: —
- ROUND3 owned materials: —
- ROUND3 consequence: —
- ROUND3 requirement: 3、缴费成功后须将缴费凭证上传至“招采通平台”(以下简称平台， 2026-03-23 16:58:05 http://zct.xacin.com.cn)下载获取招标文件。；5.2 递交方法：电子版投标文件上传至西安市综改试验区国企招标集采交易 平台（招采通平台）(网址：http://zct.xacin.com.cn/) 六、开标时间及地点
- ROUND3 checks: 核对电子文件加密与上传记录 / 确认上传成功且文件完整 / 依据第5页逐条比对响应文件对应章节
- ROUND3 pass criteria: 电子文件按规定加密并上传成功。
- why round-2 ownership was wrong: 电子文件是否按规定加密/上传成功？

### TECHNICAL_PARAMETER — 技术参数与配置

- ROUND2 row: 招标文件要求：套 13% 浪潮、深 信服、华 为等，要 求投标产 品技术指 标不低于 以上品牌 要求；台 13% 浪潮、深 信服、华 为等，要 求投标产 品技术指 标不低于 以上品牌 要求
复核要点：
① 按技术参数表逐项填写响应值
② 确认响应值与报价表、技术资料一致
③ 依据第39页第三、条逐条比对响应文件对应章节
通过标准：
· 技术要求逐条响应，证明材料可核验，无负偏离。
准备材料：类似项目合同及验收证明、技术参数响应对照表、检测报告、样品或样册
- ROUND3 atoms: SRA0038, SRA0197, SRA0213, SRA0273, SRA0285
- ROUND3 owned numbers: 8个(QUANTITY)
- ROUND3 owned materials: 技术证明材料
- ROUND3 consequence: —
- ROUND3 requirement: 包括但不限于：需求分析、软件设计、开发、集成、有关设备和附件；（20 分） 1）由评标委员会对所提供产品的技术参数进行评审，投标人须根据招标文
- ROUND3 checks: 逐条核对技术参数响应 / 确认无负偏离并标注证明材料位置 / 依据第29页逐条比对响应文件对应章节 / 核对响应文件已载明：数量要求为 8个
- ROUND3 pass criteria: 技术参数逐条响应，无负偏离。 / 数量要求为 8个，且响应文件一致。
- why round-2 ownership was wrong: 技术参数是否逐条响应、有无负偏离？

### QUALIFICATION_CREDIT — 资格·信用记录

- ROUND2 row: 招标文件要求：3.4 投标人须未被列入“信用中国（https://www.creditchina.gov.cn/）” 严重失信主体名单；；4、投标人须未被列入“信用中国（https://www.creditchina.gov.
复核要点：
① 在招标文件指定平台查询并留存查询截图
② 确认查询结果无禁止性记录且截图在有效期内取得
③ 依据第5页第3.4条逐条比对响应文件对应章节
通过标准：
· 资格材料齐全有效，主体信息一致。
准备材料：指定平台查询结果截图
- ROUND3 atoms: SRA0004, SRA0026
- ROUND3 owned numbers: —
- ROUND3 owned materials: 信用查询截图
- ROUND3 consequence: —
- ROUND3 requirement: 3.4 投标人须未被列入“信用中国（https://www.creditchina.gov.cn/）” 严重失信主体名单；；4、投标人须未被列入“信用中国（https://www.creditchina.gov.
- ROUND3 checks: 核对信用查询截图 / 确认查询时间与查询结果满足要求 / 依据第5页第3.4条逐条比对响应文件对应章节
- ROUND3 pass criteria: 信用记录查询结果满足招标文件要求。
- why round-2 ownership was wrong: 信用记录查询结果是否满足要求？


## Manual-style audit (deterministic 20-row sample)

### AFTER_SALES_SERVICE — 售后服务与运维

1. 要求: 案不包含单不限于响应时间、应急保障措施、应急保障团队组成等方面，，
2. 复核: 核对售后服务响应时间与运维方案 确认承诺可执行 依据第29页逐条比对响应文件对应章节
3. 通过: 售后服务响应时间与运维方案在响应文件中有明确承诺。
4. 证据: SRA0008, SRA0208, SRA0215
5. 同一决策: yes

### BID_BOND_AMOUNT — 保证金金额

1. 要求: ¥投标保证金的金额：伍万整（50000.00 元）；的一部分，投标保证金有效期与投标文件有效期一致。
2. 复核: 核对响应文件中的保证金金额 确认凭证金额与招标文件一致 依据第20页逐条比对响应文件对应章节
3. 通过: 保证金金额与招标文件规定一致。
4. 证据: SRA0042, SRA0049.1, SRA0049.2
5. 同一决策: yes

### BID_BOND_DEADLINE — 保证金到账时间

1. 要求: 账户，招标人确认款项到账即视为履约担保提供完毕，同时，给中标
2. 复核: 核对保证金到账时间 确认早于递交截止时间 依据第11页逐条比对响应文件对应章节
3. 通过: 保证金在递交截止时间前到账。
4. 证据: SRA0060
5. 同一决策: yes

### BID_BOND_EVIDENCE — 保证金凭证

1. 要求: 投标保证金缴纳账户：按照“西安市综改试验区国企招标集采交易；注意事项：投标保证金缴纳成功后，在投标文件编制时附缴存凭证。
2. 复核: 核对保证金凭证 确认凭证已放入响应文件对应位置 依据第173页逐条比对响应文件对应章节
3. 通过: 保证金凭证放入响应文件，可核验。
4. 证据: SRA0043, SRA0051, SRA0109
5. 同一决策: yes

### BID_BOND_FORM — 保证金形式

1. 要求: 缴纳（包括但不限于现金转账、银行保函、工程担保公司出具的保函；2.采用纸质保函形式提交的投标保证金须将纸质保函原件在投标文
2. 复核: 核对保证金形式（电汇/转账/保函等） 确认形式符合招标文件规定 依据第10页第3.4.1条逐条比对响应文件对应章节
3. 通过: 保证金形式符合规定，且来源合法。
4. 证据: SRA0040, SRA0041, SRA0047
5. 同一决策: yes

### BID_BOND_TRANSFER — 保证金转出账户

1. 要求: 1.采用转账或银行电汇形式提交的投标保证金必须从其基本账户转；须附汇款凭证及基本账户证明材料复印件加盖投标人公章。
2. 复核: 核对保证金转出账户 确认从规定账户转出并留存凭证 依据第10页逐条比对响应文件对应章节
3. 通过: 保证金从规定的账户转出。
4. 证据: SRA0044, SRA0046, SRA0120
5. 同一决策: yes

### BID_VALIDITY — 投标有效期

1. 要求: 3.3.1 投标有效期 90 个日历天(从投标截止之日算起)；3.3.1 除投标人须知前附表另有规定外，投标有效期为90 个日历天。
2. 复核: 核对投标函中的投标有效期 确认覆盖评审与定标全过程 依据第20页逐条比对响应文件对应章节 核对响应文件已载明：投标有效期不少于 90个日历天 核对响应文件已载明：投标有效期不少于 90天
3. 通过: 投标有效期达到规定天数，且覆盖评审与定标全过程。 投标有效期不少于 90个日历天，且响应文件一致。 投标有效期不少于 90天，且响应文件一致。
4. 证据: SRA0039, SRA0117, SRA0118
5. 同一决策: yes

### CONSORTIUM — 联合体

1. 要求: 3.1.2 投标人须知前附表规定不接受联合体投标的，或投标人没有组成联合 2026-03-23 16:58:05 体的，投标文件不包括联合体协议书。；评审标准：提供非联合体投标承诺书。
2. 复核: 核对投标主体形式 确认与联合体规定一致 依据第5页第3.6条逐条比对响应文件对应章节
3. 通过: 响应文件的投标主体形式与招标文件关于联合体的规定一致。
4. 证据: SRA0006, SRA0028, SRA0090
5. 同一决策: yes

### CONTRACT_PAYMENT — 合同付款与结算

1. 要求: （3）项目试运行期满后，由乙方委托第三方评估机构并支付相关评估费用， 进行项目评估，第三方评估机构出具评估合格报告后,并经甲方组织竣工验收合 格后，支付至结算价款的97%；；7.8.1 招标人和中标单位应当在中标通知书发出之日起30 日内，根据招标 文件和中标单位的投标文件订立书面合同。
2. 复核: 核对合同付款条款响应 核对付款方式、结算依据与付款条件 依据第25页第7.8.1条逐条比对响应文件对应章节 核对响应文件已载明：付款/计分比例为 97%
3. 通过: 付款方式、结算依据与付款条件在响应文件中被接受。 付款/计分比例为 97%，且响应文件一致。
4. 证据: SRA0164, SRA0274, SRA0276
5. 同一决策: yes

### CONTRACT_RISK — 合同风险与违约责任

1. 要求: 的，投标人须承担全部赔偿责任。；二十二、误期赔偿费 除合同条款第二十四条规定的情况外，如果乙方没有按照合同规定的时间交 货和提供服务，甲方应在不影响合同项下的其他补救措施的情况下，从合同价中 扣除误期赔偿费，具体赔偿标准见合同专用条款。
2. 复核: 核对违约、索赔与争议条款响应 确认无采购人不能接受的附加条件 依据第52页逐条比对响应文件对应章节
3. 通过: 不存在采购人不能接受的附加条件或未响应风险条款。
4. 证据: SRA0074, SRA0315, SRA0316
5. 同一决策: yes

### DELIVERY_PERIOD — 工期与供货期

1. 要求: 八、工期要求及系统建设地点 1.合同签订后新整合营收系统完成之前必须保证现状营业收费系统可靠运 行，合同签订后的18 个月之内完成全部系统的开发并投入试运行。；（工期要求： 开发周期6 个月，各现场系统安装、接驳及调试完成时间6 个月，试运行时间6 个月）。
2. 复核: 核对响应函与进度计划中的工期/供货期 确认覆盖全部交付与验收节点 依据第51页第八、条逐条比对响应文件对应章节 核对响应文件已载明：工期/供货期满足 6个月
3. 通过: 工期/供货期达到规定期限，且覆盖全部交付节点。 工期/供货期满足 6个月，且响应文件一致。
4. 证据: SRA0343, SRA0344
5. 同一决策: yes

### ELECTRONIC_UPLOAD — 电子上传与加密

1. 要求: 3、缴费成功后须将缴费凭证上传至“招采通平台”(以下简称平台， 2026-03-23 16:58:05 http://zct.xacin.com.cn)下载获取招标文件。；5.2 递交方法：电子版投标文件上传至西安市综改试验区国企招标集采交易 平台（招采通平台）(网址：http://zct.xacin.com.cn/) 六、开标时间及地点
2. 复核: 核对电子文件加密与上传记录 确认上传成功且文件完整 依据第5页逐条比对响应文件对应章节
3. 通过: 电子文件按规定加密并上传成功。
4. 证据: SRA0009, SRA0011, SRA0013
5. 同一决策: yes

### EVALUATION_COLLUSION — 评审·串标与弄虚作假

1. 要求: 7.5.3 重点核查的异常投标情形： （一）法律法规规定视为串通投标的情形；；（四）通过受让、租借、挂靠资质投标，伪造、变造资质、资格证书或者其 他许可证件，提供虚假业绩、奖项、项目负责人等材料。
2. 复核: 核对不存在串标、弄虚作假的证据 确认响应文件无雷同与异常一致 依据第25页第9.2条逐条比对响应文件对应章节
3. 通过: 不存在串标、弄虚作假情形。
4. 证据: SRA0161, SRA0162, SRA0171
5. 同一决策: yes

### EVALUATION_QUALIFICATION_REVIEW — 评审·资格审查

1. 要求: 3.5 资格审查资料 除投标人须知前附表另有规定外，投标人应按下列规定提供资格审查资料， 以证明其满足本章第 1.4.1 款规定的投标人资质条件。
2. 复核: 核对资格审查要点 确认全部满足 依据第20页第3.5条逐条比对响应文件对应章节
3. 通过: 资格审查要点在响应文件中全部满足。
4. 证据: SRA0126
5. 同一决策: yes

### EVALUATION_RESPONSIVENESS — 评审·响应性审查

1. 要求: 1.10.1 投标文件应当对招标文件的实质性要求和条件作出满足性或更有利于 招标人的响应，否则，投标人的投标将被否决。；实质性要求和条件见投标人须知 前附表。
2. 复核: 核对实质性响应要求 确认无重大偏差 依据第17页第1.10.1条逐条比对响应文件对应章节
3. 通过: 实质性响应要求全部满足，无重大偏差。
4. 证据: SRA0096, SRA0097, SRA0235
5. 同一决策: yes

### EVALUATION_SCORING — 评分标准与分值构成

1. 要求: 的人数 按最终得分由高到低的顺序选取前 3 名为中标候选人。；6.3.1 评标委员会按照第三章“评标办法”规定的方法、评审因素、标准和 程序对投标文件进行评审。
2. 复核: 将评分因素拆解为得分条件、证明材料与页码 确认每项都有对应响应内容 依据第23页第6.3.1条逐条比对响应文件对应章节 核对响应文件已载明：人员配备数量为 3名 核对响应文件已载明：该评分因素最高 100分 核对响应文件已载明：该评分因素最高 1分
3. 通过: 每个评分因素都有对应响应内容与证明材料。 人员配备数量为 3名，且响应文件一致。 该评分因素最高 100分，且响应文件一致。 该评分因素最高 1分，且响应文件一致。
4. 证据: SRA0057, SRA0151, SRA0152
5. 同一决策: yes

### FILE_COMPOSITION — 响应文件组成

1. 要求: 1.22 投标文件未按规定的格式填写，或主要内容不全，或关键字迹模糊、 营收系统整合和硬件系统升级项目 无法辨认造成无法满足评标需要的；
2. 复核: 按招标文件要求的组成部分逐项清点 确认无缺项、无多余替代件 依据第34页第1.22条逐条比对响应文件对应章节
3. 通过: 响应文件组成齐全，与招标文件要求的组成部分一致。
4. 证据: SRA0264
5. 同一决策: yes

### GENERAL_BIDDER_OBLIGATION — 一般投标人义务

1. 要求: 金落实情况 800 万元；要求 1、投标人须在中华人民共和国境内登记注册，具有独立承担民事责
2. 复核: 核对该条款对应的响应内容 确认响应完整、可核验 依据第8页逐条比对响应文件对应章节
3. 通过: 响应文件对该条款作出可核验的对应响应。
4. 证据: SRA0001, SRA0016, SRA0017
5. 同一决策: yes

### INTERNAL_PROCEDURE — 采购方内部程序

1. 要求: 〔采购人内部程序/定义条款，仅备查，无需投标响应〕7.5.2 若排名第一的中标候选人放弃中标、因不可抗力不能履行合同、不按 照招标文件要求提交履约保证金、或招标人对中标候选人组织核验时发现存在弄 虚作假围标串标等违法情形，不符合中标条件的，其投标保证金不予退还，招标…；在评标活 动中，评标委员会成员应当客观、公正地履行职责，遵守职业道德，不得擅离职 守，影响评标程序正常进行，不得使用第三章“评标办法”没有…
2. 复核: 确认该条属于采购人内部程序或术语定义，无需投标人响应 仅作背景备查，不作为废标/评分依据 依据第26页逐条比对响应文件对应章节
3. 通过: 该条款的响应内容在响应文件中可核验，且与要求一致。
4. 证据: SRA0160, SRA0173, SRA0175
5. 同一决策: yes

### OPENING_DECRYPTION — 开标与解密

1. 要求: （3）文件解密：开标时，投标单位须使用电子招标投标文件加密时所用的 数字认证证书（CA 锁）自行解密电子招标投标文件。；1.18 因投标单位自身原因（如CA 锁与制作电子投标文件使用的CA 锁不一 致、或沿用旧版招标文件编制投标文件等情形），导致在规定时间内无法解密投 标文件的；
2. 复核: 核对签到与解密时间 确认在规定时间内完成解密 依据第22页第（3）条逐条比对响应文件对应章节
3. 通过: 在规定时间内完成签到与解密。
4. 证据: SRA0145, SRA0261
5. 同一决策: yes
