# Round 5.5 动态复核项与最终来源保真审计报告

- run: `run_5_5_dynamic_review_final_audit`
- automated_checks: **PASS**
- final_status: **ROUND_5_5_AWAITING_WORD_MANUAL_CONFIRMATION**
- word_com_status: `WORD_COM_ENVIRONMENT_BLOCKED`

## 1. 动态复核项架构 (DYNAMIC_REVIEW_ARCHITECTURE)
源文件 → 源要求索引 (source requirement index) → ProjectFacts → 动态复核项 (dynamic review items) → 可编辑 Word 表 → 交付 QA → 人工 Word 确认。
`rules/review_items.yaml` 仍作为主题分类/召回辅助，但 **不决定最终行数**：行数由源文件条款数量决定。

- `case_001`: 源片段 467，源要求 297，动态复核项 47，工作簿行 47，模块 {'四、报价与合同商务': 14, '五、技术响应': 5, '二、资格审查': 6, '七、签章与电子标': 3, '一、废标红线': 9, '三、投标文件组成与格式': 5, '八、递交与开标准备': 2, '六、评分项复核': 3}
- `case_002`: 源片段 2199，源要求 649，动态复核项 49，工作簿行 49，模块 {'三、投标文件组成与格式': 4, '二、资格审查': 9, '七、签章与电子标': 3, '五、技术响应': 8, '八、递交与开标准备': 2, '四、报价与合同商务': 13, '六、评分项复核': 3, '一、废标红线': 7}
- `case_003`: 源片段 1610，源要求 1005，动态复核项 53，工作簿行 53，模块 {'六、定性评审与定标材料': 2, '三、投标文件组成与格式': 4, '一、废标红线': 7, '五、技术响应': 7, '六、评分项复核': 2, '八、递交与开标准备': 2, '四、报价与合同商务': 13, '二、资格审查': 13, '七、签章与电子标': 3}

## 2. CASE_001_REVIEW_RESULT
- 动态复核项: 47（工作簿行 47，游离行 0）
- 模块分布: {'四、报价与合同商务': 14, '五、技术响应': 5, '二、资格审查': 6, '七、签章与电子标': 3, '一、废标红线': 9, '三、投标文件组成与格式': 5, '八、递交与开标准备': 2, '六、评分项复核': 3}
- 硬性门禁: {'source_mandatory_requirement_without_review_item_count': 0, 'project_irrelevant_review_item_count': 0, 'invalid_review_evidence_locator_count': 0, 'empty_review_evidence_count': 0, 'cross_topic_evidence_mismatch_count': 0, 'unclassified_dynamic_requirement_count': 0, 'generic_text_when_specific_source_available_count': 0, 'dynamic_review_item_count': 47}
- 覆盖: {'requirement_count': 99, 'covered': 99, 'uncovered': []}
- 结果: **PASS**

## 3. CASE_002_REVIEW_RESULT
- 动态复核项: 49（工作簿行 49，游离行 0）
- 模块分布: {'三、投标文件组成与格式': 4, '二、资格审查': 9, '七、签章与电子标': 3, '五、技术响应': 8, '八、递交与开标准备': 2, '四、报价与合同商务': 13, '六、评分项复核': 3, '一、废标红线': 7}
- 硬性门禁: {'source_mandatory_requirement_without_review_item_count': 0, 'project_irrelevant_review_item_count': 0, 'invalid_review_evidence_locator_count': 0, 'empty_review_evidence_count': 0, 'cross_topic_evidence_mismatch_count': 0, 'unclassified_dynamic_requirement_count': 0, 'generic_text_when_specific_source_available_count': 0, 'dynamic_review_item_count': 49}
- 覆盖: {'requirement_count': 154, 'covered': 154, 'uncovered': []}
- 结果: **PASS**

## 4. CASE_003_REVIEW_RESULT
- 动态复核项: 53（工作簿行 53，游离行 0）
- 模块分布: {'六、定性评审与定标材料': 2, '三、投标文件组成与格式': 4, '一、废标红线': 7, '五、技术响应': 7, '六、评分项复核': 2, '八、递交与开标准备': 2, '四、报价与合同商务': 13, '二、资格审查': 13, '七、签章与电子标': 3}
- 硬性门禁: {'source_mandatory_requirement_without_review_item_count': 0, 'project_irrelevant_review_item_count': 0, 'invalid_review_evidence_locator_count': 0, 'empty_review_evidence_count': 0, 'cross_topic_evidence_mismatch_count': 0, 'unclassified_dynamic_requirement_count': 0, 'generic_text_when_specific_source_available_count': 0, 'dynamic_review_item_count': 53}
- 覆盖: {'requirement_count': 339, 'covered': 339, 'uncovered': []}
- 结果: **PASS**

## 6. CASE003_LOT_NAME_FIX
- `lot_name` = '三标段' (RESOLVED)
- 依据: [{"value": "三标段", "method": "lot_cover_title", "page": 1, "evidence": "三标段"}, {"value": "三标段", "method": "lot_value_context", "page": 5, "evidence": "2.7合同估算价:三标段1252.299431万元。"}, {"value": "三标段", "method": "lot_section_heading", "page": 6, "evidence": "3.1三标段投标人资格要求:"}]
- 结果: **PASS**

## 7. CASE_001_DOCX_SOURCE_AUDIT
- 源表单元格检查: 25，缺失 0
- 逻辑表: PDF 片段 5 → 逻辑表 5（折叠 0），孤立续页片段 0，误合并 0
- 文本无损: 逻辑模型 True，可编辑表 True，字符差 0
- 跨页缝单元格: 0，DOCX 缺失 0
- 逐字面空格保真: True，上标 run 2，SOURCE_LITERAL 编号 52，自动编号 0
- 硬性空白/几何: blank_width_error_max 0.0，paragraph_x_error_max 0.020002746582036934，合成布局表 0，段落 139，表 5
- 结果: **PASS**（视觉: PASS，渲染 OK，渲染页回溯源文件 22/22，行级 0.8487）

## 8. CASE_002_DOCX_SOURCE_AUDIT
- 源表单元格检查: 79，缺失 0
- 逻辑表: PDF 片段 22 → 逻辑表 10（折叠 12），孤立续页片段 0，误合并 0
- 文本无损: 逻辑模型 True，可编辑表 True，字符差 0
- 跨页缝单元格: 11，DOCX 缺失 0
- 逐字面空格保真: True，上标 run 0，SOURCE_LITERAL 编号 53，自动编号 0
- 硬性空白/几何: blank_width_error_max 0.0，paragraph_x_error_max 0.020013427734397737，合成布局表 0，段落 144，表 10
- 结果: **PASS**（视觉: PASS，渲染 OK，渲染页回溯源文件 31/31，行级 0.9737）
- 无可提取文本的渲染页（折叠逻辑表长行溢出，需人工目视确认）: [13, 14, 15, 16, 22, 23, 24, 25, 29, 30, 34, 35]

## 9. CASE_003_DOCX_SOURCE_AUDIT
- 源表单元格检查: 51，缺失 0
- 逻辑表: PDF 片段 16 → 逻辑表 16（折叠 0），孤立续页片段 0，误合并 0
- 文本无损: 逻辑模型 True，可编辑表 True，字符差 0
- 跨页缝单元格: 0，DOCX 缺失 0
- 逐字面空格保真: True，上标 run 0，SOURCE_LITERAL 编号 88，自动编号 0
- 硬性空白/几何: blank_width_error_max 0.0，paragraph_x_error_max 0.025000762939455967，合成布局表 0，段落 194，表 16
- 结果: **PASS**（视觉: PASS，渲染 OK，渲染页回溯源文件 34/34，行级 0.9342）
- 无可提取文本的渲染页（折叠逻辑表长行溢出，需人工目视确认）: [33]

## 11. SOURCE_REQUIREMENT_COVERAGE
- `case_001`: 源要求 297，必核 {'requirement_count': 99, 'covered': 99, 'uncovered': []}，高风险 {'requirement_count': 18, 'covered': 18, 'uncovered': []}
- `case_002`: 源要求 649，必核 {'requirement_count': 154, 'covered': 154, 'uncovered': []}，高风险 {'requirement_count': 35, 'covered': 35, 'uncovered': []}
- `case_003`: 源要求 1005，必核 {'requirement_count': 339, 'covered': 339, 'uncovered': []}，高风险 {'requirement_count': 53, 'covered': 53, 'uncovered': []}

## 12. PROJECT_IRRELEVANT_ITEM_QA
- `case_001`: 项目无关项 0，本项目源文件未出现的概念: ['培训', '数据库', '中间件', '国产化', '操作系统']
- `case_002`: 项目无关项 0，本项目源文件未出现的概念: []
- `case_003`: 项目无关项 0，本项目源文件未出现的概念: []

## 13. PROJECTFACTS_REGRESSION
- `case_001`: 字段数 23，未解析却带值 []
- `case_002`: 字段数 23，未解析却带值 []
- `case_003`: 字段数 23，未解析却带值 []

## 14. ROUND_5_3_5_4_REGRESSION
- 结果: **PASS**
- `case_001`: 版式差异 无，生成指标差异 无，事实漂移 {}
- `case_002`: 版式差异 无，生成指标差异 无，事实漂移 {}
- `case_003`: 版式差异 无，生成指标差异 无，事实漂移 {'lot_name': [None, '三标段']}

## 15. WORD_PACKAGE_INTEGRITY
- `case_001`: PASS（bytes 45254，reopen True）
- `case_002`: PASS（bytes 60938，reopen True）
- `case_003`: PASS（bytes 56322，reopen True）

## 16. MANUAL_DELIVERY_BUNDLE
- `case_001`: 4 个文件，结果 **PASS** (D:\PyCharmProjects\WBTenderSkill\acceptance\manual_delivery_round55\case_001)
- `case_002`: 4 个文件，结果 **PASS** (D:\PyCharmProjects\WBTenderSkill\acceptance\manual_delivery_round55\case_002)
- `case_003`: 4 个文件，结果 **PASS** (D:\PyCharmProjects\WBTenderSkill\acceptance\manual_delivery_round55\case_003)

## 20. OUTPUT_PATHS
- workspace: `acceptance/workspace/<case>/run_5_5_dynamic_review_final_audit`
- reports: `acceptance/reports/dynamic_review_round55`
- manual bundle: `acceptance/manual_delivery_round55`

## 21. FINAL_STATUS
- automated: **PASS**
- WORD_COM_ENVIRONMENT_BLOCKED: Word COM automation is unavailable in this environment and no OpenAndRepair or repair-save was attempted; the final Word visual acceptance belongs to the user.
- **ROUND_5_5_AWAITING_WORD_MANUAL_CONFIRMATION**
