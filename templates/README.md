# Templates

`投标项目复核表模板.xlsx` 是 V1 正式复核表模板。生成器复制该文件并只填充约定的
23 个 ProjectFacts 字段和保守的复核占位值，保留主 Sheet、合并单元格、列宽、行高、
边框、下拉和 64 项复核清单。

64 项清单是来源证据和人工复核入口，不是 ProjectFacts 的额外字段，也不自动判定资格、
商务、技术或其他合规结论。模板中的空白或待复核状态不得被解释为已满足要求。

基础投标文件 DOCX 不以通用章节作为首选：当原招标文件存在明确格式章节时，使用
`format_extractor.py` 提取的 source format 结构；所有招标事实仍必须来自
`ProjectFacts`。任何格式模板都不得成为第二套事实来源。

对 DOCX，固定优先级为 **Source Format First → Style System Second → Automation Third**。
源文件自有标题和正文列表的编号、标点、编号后空格及序号间隔必须作为字面内容保留；
Named Styles/outline 只提供导航、缩进和全局编辑能力，不能替换源编号。系统新增的
“格式自拟”等内容如需编号，应使用与源格式隔离的 `GENERATED_AUTO` 样式/编号族。
