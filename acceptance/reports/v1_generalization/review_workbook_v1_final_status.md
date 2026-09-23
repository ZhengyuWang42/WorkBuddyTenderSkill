# 投标项目复核表 V1 —— 最终状态（复核工作簿轮次）

- 生成时间：2026-09-23T09:29:40.491888+00:00
- 结论：**PASS**
- 工作簿 sheet：投标项目复核表、00_复核总览、01_项目事实、02_关键条款、03_资格否决与强制项、04_报价与限价、05_文件结构与签章、06_冲突与缺失、07_证据索引

## 三案例

| 案例 | 复核视图 | 机器事实 RESOLVED/NEEDS_REVIEW/NOT_FOUND | 门禁 | 渲染 QA | 人工已确认 |
| --- | --- | --- | --- | --- | --- |
| case_001 | 00_复核总览/01_项目事实/02_关键条款/03_资格否决与强制项/04_报价与限价/05_文件结构与签章/06_冲突与缺失/07_证据索引 | 16/1/6 | PASS | PASS | 0 |
| case_002 | 00_复核总览/01_项目事实/02_关键条款/03_资格否决与强制项/04_报价与限价/05_文件结构与签章/06_冲突与缺失/07_证据索引 | 18/1/4 | PASS | PASS | 0 |
| case_003 | 00_复核总览/01_项目事实/02_关键条款/03_资格否决与强制项/04_报价与限价/05_文件结构与签章/06_冲突与缺失/07_证据索引 | 11/6/6 | PASS | PASS | 0 |

## Word 产物

本轮的 Word 产物为**原样复制**，未重新渲染：

- `基础投标文件.docx`：sha256 `8dedddb7682e193cf6544feae286cdbbf1ba3be876355eba20c7a8f4cd294230`，byte_identical=True
- `基础投标文件.pdf`：sha256 `3fe5b5b9118b57cb24742f02062284ba0c3038bcacae1dbf11211bdb23261927`，byte_identical=True
- `generation_report.json`：sha256 `1274c205a9e151976d09c3598b1feffd169fa579878c7f105126994717608ace`，byte_identical=True

## 状态标志

- `REVIEW_WORKBOOK_VIEWS = IMPLEMENTED`
- `REVIEW_WORKBOOK_GATE = PASS`
- `REVIEW_WORKBOOK_VISUAL_QA = PASS`
- `WORD_ARTIFACTS_UNCHANGED = PASS`
- `CASE001_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`
- `CASE002_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`
- `CASE003_XLSX_MANUAL_REVIEW = NOT_YET_CONFIRMED`
- `V1_PRODUCTION_CANDIDATE = false`
- `READY_FOR_SUBMISSION = false`

## 全量测试

- 证据：`D:\PyCharmProjects\WBTenderSkill\acceptance\reports\v1_generalization\review_workbook_full_test_suite.txt`
- 计数：638 passed, 1 skipped, 0 failed, 0 error

## 说明

- 复核工作簿是**人工复核界面**：机器列只投影 `ProjectFacts`、源文件、`ReviewEvidence` 与 QA 报告；人工列初始为 `未复核`，且没有任何公式引用它们。
- 自动化不勾选任何人工复核结论，`READY_FOR_SUBMISSION` 保持 false。
- Word 保真度未改动：DOCX/PDF/generation_report 与已验收构建逐字节相同。
