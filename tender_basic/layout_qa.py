"""Measured render QA; missing renders never produce a layout PASS."""
import json
import re
from statistics import median
from zipfile import ZipFile
from lxml import etree

NS = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def docx_layout_counts(path):
    with ZipFile(path) as archive:
        root = etree.fromstring(archive.read('word/document.xml'))
    paragraphs = root.findall('.//w:p', NS)
    breaks = root.xpath('.//w:br[not(@w:type="page")]', namespaces=NS)
    # A tab is a safe intra-line anchor only when the paragraph declares a
    # custom tab stop.  This diagnostic therefore distinguishes form tabs
    # from legacy tabs used as page-positioning hacks.
    tab_hacks = 0
    for paragraph in paragraphs:
        tabs = paragraph.xpath('./w:pPr/w:tabs/w:tab', namespaces=NS)
        text_tabs = paragraph.xpath('.//w:r/w:tab', namespaces=NS)
        if text_tabs and not tabs:
            tab_hacks += 1
    return {'word_logical_paragraphs':len(paragraphs), 'word_manual_breaks':len(breaks),
        'word_page_breaks':len(root.xpath('.//w:br[@w:type="page"]', namespaces=NS)),
        'word_section_page_boundaries':max(0,len(root.findall('.//w:sectPr',NS))-1),
        'layout_tab_count':len(root.findall('.//w:tab', NS)),
        'layout_tab_hack':tab_hacks}


def compact(text):
    return re.sub(r'\s+', '', text)


def text_anchors(page):
    result = {}
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            spans = line.get('spans', [])
            text = compact(''.join(s['text'] for s in spans))
            if 3 <= len(text) <= 60:
                result.setdefault(text, []).append({'bbox':line['bbox'],
                    'font_size':median([s['size'] for s in spans] or [0])})
    return result


def compare_layout(source_pdf, generated_pdf, template, docx, previous_docx=None):
    import pymupdf
    counts = docx_layout_counts(docx)
    prior = docx_layout_counts(previous_docx) if previous_docx else None
    anchors, table_errors, warnings = [], [], []
    source_lines = 0
    with pymupdf.open(source_pdf) as source, pymupdf.open(generated_pdf) as generated:
        page_count = len(generated)
        if page_count != len(template.source_pages):
            warnings.append('PAGE_LAYOUT_NEEDS_REVIEW: source/generated page count differs; page-paired metrics may include pagination drift')
        for index, model_page in enumerate(template.source_pages):
            if index >= len(generated):
                break
            src, dest = source[model_page.page-1], generated[index]
            chrome_indices={getattr(c.locator,'block_index',None) for c in template.chrome_items if c.page==model_page.page}
            for block in src.get_text('dict')['blocks']:
                if block.get('number') in chrome_indices:
                    continue
                for line in block.get('lines',[]):
                    if not ''.join(s['text'] for s in line['spans']).strip():
                        continue
                    cy=(line['bbox'][1]+line['bbox'][3])/2
                    if any(e.bbox[1]-1<=cy<=e.bbox[3]+1 for e in model_page.elements):
                        source_lines+=1
            sa, da = text_anchors(src), text_anchors(dest)
            chrome = {compact(c.text) for c in template.chrome_items if c.page == model_page.page}
            for text in sa.keys() & da.keys():
                if text in chrome or len(sa[text]) != 1 or len(da[text]) != 1:
                    continue
                a,b = sa[text][0],da[text][0]
                major = (len(text)<=35 and not any(c in text for c in '，。；：') and
                    any(t in text for t in ('文件格式','投标函','响应函','开标一览表','授权委托书','偏差表','偏离表','报价表','投标文件','响应文件')))
                anchors.append({'source_page':model_page.page, 'generated_page':index+1,
                    'text':text, 'major':major, 'source_bbox':a['bbox'], 'generated_bbox':b['bbox'],
                    'x_position_error_pt':abs(a['bbox'][0]-b['bbox'][0]),
                    'y_position_error_pt':abs(a['bbox'][1]-b['bbox'][1]),
                    'x_center_error_pt':abs((a['bbox'][0]+a['bbox'][2]-b['bbox'][0]-b['bbox'][2])/2),
                    'font_size_error_pt':abs(a['font_size']-b['font_size'])})
            detected = list(dest.find_tables().tables) if model_page.tables else []
            for table in model_page.tables:
                candidates = [t for t in detected if t.col_count == table.columns]
                if not candidates:
                    warnings.append(f'TABLE_GEOMETRY_UNMATCHED: source page {model_page.page}, table {table.table_index}')
                    continue
                target = min(candidates, key=lambda t:abs(t.bbox[1]-table.bbox[1]))
                detected.remove(target)
                xs = sorted({round(cell[0],1) for cell in target.cells if cell} | {round(cell[2],1) for cell in target.cells if cell})
                widths = [b-a for a,b in zip(xs,xs[1:])]
                ratio_error = None
                if len(widths) == len(table.column_widths) and sum(table.column_widths)>0:
                    ratio_error = max(abs(w/sum(widths)-s/sum(table.column_widths))/(s/sum(table.column_widths)) for w,s in zip(widths,table.column_widths) if s>0)
                table_errors.append({'source_page':model_page.page, 'table_index':table.table_index,
                    'table_bbox_width_error_pt':abs((target.bbox[2]-target.bbox[0])-(table.bbox[2]-table.bbox[0])),
                    'table_column_ratio_error':ratio_error})
        wrap_lines = sum(sum(sum(bool(''.join(s['text'] for s in l['spans']).strip()) for l in b.get('lines',[])) for b in p.get_text('dict')['blocks']) for p in generated)
    major = [a for a in anchors if a['major']]
    y = median([a['y_position_error_pt'] for a in major]) if major else None
    x = median([a['x_center_error_pt'] for a in major]) if major else None
    size = median([a['font_size_error_pt'] for a in major]) if major else None
    if y is None or y>12 or x>10 or size>2:
        warnings.append('PAGE_LAYOUT_NEEDS_REVIEW: major anchor geometry outside target or insufficient anchors')
    if any(t['table_column_ratio_error'] is None or t['table_column_ratio_error']>.1 for t in table_errors):
        warnings.append('TABLE_LAYOUT_NEEDS_REVIEW: unmeasured or >10% column proportion error')
    return {**counts, 'source_pages':len(template.source_pages), 'generated_pages':page_count,
        'pdf_visual_lines':source_lines, 'generated_pdf_visual_lines':wrap_lines,
        'source_visual_lines':source_lines, 'generated_visual_lines':wrap_lines,
        'line_wrap_delta':wrap_lines-source_lines,
        'wrap_line_count_delta':wrap_lines-source_lines, 'wrap_line_count_note':'Nonempty rendered text lines including table cells; source chrome excluded. Aggregate, not paragraph identity.',
        'manual_break_reduction':prior['word_manual_breaks']-counts['word_manual_breaks'] if prior else None,
        'major_anchor_y_error_pt':y, 'major_title_x_center_error_pt':x, 'major_anchor_font_size_error_pt':size,
        'anchors':anchors, 'tables':table_errors, 'layout_warnings':warnings,
        'result':'NEEDS_REVIEW' if warnings or counts['layout_tab_hack'] else 'PASS'}


def write_comparison_pairs(source_pdf, generated_pdf, template, output_dir):
    """PDF-native comparison, no raster editing or OCR. References retain chrome."""
    import pymupdf
    from pathlib import Path
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    pages = template.source_pages
    from .page_layout import classify_page
    divider=classify_page(pages[0])=='CHAPTER_DIVIDER'
    choices = {'cover':1 if divider else 0, 'first_form':min(3 if divider else 2,len(pages)-1)}
    if divider: choices['chapter_divider']=0
    text_pages = [i for i,p in enumerate(pages) if sum(len(t.text) for t in p.paragraphs)>500]
    table_pages = [i for i,p in enumerate(pages) if p.tables]
    if text_pages: choices['body']=text_pages[0]
    if table_pages:
        choices['table']=table_pages[0]
        choices['complex_table']=max(table_pages,key=lambda i:sum(len(t.rows)*t.columns for t in pages[i].tables))
    with pymupdf.open(source_pdf) as source, pymupdf.open(generated_pdf) as generated:
        for label,index in choices.items():
            if index>=len(generated): continue
            sp,gp = source[pages[index].page-1],generated[index]
            with pymupdf.open() as pair:
                width,height=max(sp.rect.width,gp.rect.width),max(sp.rect.height,gp.rect.height)
                p=pair.new_page(width=width*2+30,height=height+35)
                p.insert_text((10,18),f'SOURCE page {pages[index].page} | GENERATED page {index+1}')
                p.show_pdf_page(pymupdf.Rect(0,30,width,height+30),source,pages[index].page-1)
                p.show_pdf_page(pymupdf.Rect(width+30,30,width*2+30,height+30),generated,index)
                p.get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(output/f'{label}.png')
