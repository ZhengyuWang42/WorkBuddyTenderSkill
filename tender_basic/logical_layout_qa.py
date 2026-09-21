"""Structural QA for serialized logical paragraphs, forms, and list geometry."""

from collections import defaultdict
from zipfile import ZipFile

from docx import Document

from .layout_qa import docx_layout_counts
from .page_layout import FORM_ANCHOR, ITEM, TERMINAL
from .source_fill_policy import slot_field_allowed


W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W = {'w': W_NS}


def _docx_xml_counts(path):
    from lxml import etree

    with ZipFile(path) as archive:
        root=etree.fromstring(archive.read('word/document.xml'))
    underlined_text=[]
    for run in root.xpath('.//w:r',namespaces=W):
        underline=run.find('w:rPr/w:u',namespaces=W)
        if underline is not None and underline.get(f'{{{W_NS}}}val','single') != 'none':
            underlined_text.append(''.join(run.xpath('.//w:t/text()',namespaces=W)))
    nbsp_only=len([
        text for text in root.xpath('.//w:t/text()',namespaces=W)
        if text and '\u00a0' in text and text.replace('\u00a0', '').strip() == ''
    ])
    leader_stops=root.xpath('.//w:pPr/w:tabs/w:tab[@w:leader and @w:leader!="space"]',namespaces=W)
    return {
        'bottom_border_count':len(root.xpath('.//w:tcBorders/w:bottom',namespaces=W)),
        'underlined_run_count':len(underlined_text),
        'underlined_text':underlined_text,
        'leader_tab_stop_count':len(leader_stops),
        'nbsp_only_placeholder_count':nbsp_only,
    }


def _variance(values):
    values=[float(value) for value in values if value is not None]
    return max(values)-min(values) if values else 0.0


def inspect_logical_layout(path, generation, template):
    doc=Document(path)
    records=generation.get('logical_paragraph_records',[])
    issues={key:[] for key in (
        'mid_sentence_paragraph_breaks','centered_body_paragraph_count',
        'extreme_body_right_indent_count','list_continuation_split_count',
        'multi_label_form_row_count','form_table_wrong_alignment_count',
        'slot_semantic_mismatch_count','paragraph_fragmentation_count',
        'form_paragraph_not_native_count',
    )}
    body=[record for record in records if 'paragraph_index' in record]
    for record in body:
        paragraph=doc.paragraphs[record['paragraph_index']]
        if paragraph.text != record['text']:
            issues['paragraph_fragmentation_count'].append(record['paragraph_index'])
        if record['kind'] in ('LogicalParagraph','List'):
            if paragraph.alignment == 1:
                issues['centered_body_paragraph_count'].append(paragraph.text)
            page_width=next(page.width for page in template.source_pages if page.page == record['source_page'])
            width=page_width-36-(paragraph.paragraph_format.left_indent.pt or 0)-(paragraph.paragraph_format.right_indent.pt or 0)
            container=record['container_bbox'][2]-record['container_bbox'][0]
            if width < .75*container:
                issues['extreme_body_right_indent_count'].append({'text':paragraph.text,'width':width,'container':container})

    # Examine original adjacency as well as actual text; a zero br count
    # cannot hide an incomplete sentence split into several paragraphs.
    for left,right in zip(records,records[1:]):
        if left['kind'] not in ('LogicalParagraph','List') or right['kind'] != 'LogicalParagraph':
            continue
        terminal=bool(TERMINAL.search(left.get('source_text','')))
        if left['kind']=='List' and left.get('source_text','').rstrip().endswith(('；','：',':')):
            terminal=False
        if left['source_page'] != right['source_page'] or terminal:
            continue
        if not left.get('source_baselines') or not right.get('source_baselines'):
            continue
        pitch=right['source_baselines'][0]-left['source_baselines'][-1]
        left_paragraph=doc.paragraphs[left['paragraph_index']]
        size=max([run.font.size.pt for run in left_paragraph.runs if run.font.size] or [12])
        if .75*size <= pitch <= 3.3*size and len(left['source_text']) > 25 and not ITEM.match(right['text']):
            issue={'before':left_paragraph.text[-60:],'after':doc.paragraphs[right['paragraph_index']].text[:60],
                   'page':left['source_page']}
            issues['mid_sentence_paragraph_breaks'].append(issue)
            if left['kind']=='List':
                issues['list_continuation_split_count'].append(issue)

    form_records=[record for record in records if record['kind']=='FormRow']
    form_by_block=defaultdict(list)
    for record in form_records:
        paragraph_index=record.get('paragraph_index')
        if record.get('table_index') is not None or paragraph_index is None or paragraph_index >= len(doc.paragraphs):
            issues['form_paragraph_not_native_count'].append(record.get('text'))
        form_by_block[record.get('form_block_index', record.get('table_index'))].append(record)
        if record.get('row_type') != 'MULTI_INLINE_FIELDS' and len(FORM_ANCHOR.findall(record['text'])) > 1 and len(record.get('source_baselines',[])) > 1:
            issues['multi_label_form_row_count'].append(record['text'])

    slots={slot.slot_id:slot for slot in template.fill_slots}
    for fill in generation.get('filled_slots',[]):
        slot=slots.get(fill['slot_id'])
        if slot is not None and not all(slot_field_allowed(slot,field) for field in slot.allowed_fact_fields):
            issues['slot_semantic_mismatch_count'].append(fill)

    xml_counts=_docx_xml_counts(path)
    blank_records=generation.get('editable_blanks',[]) or []
    required=[blank for blank in blank_records if blank.get('visible')]
    required_bottom=sum(blank.get('render_style')=='BOTTOM_RULE' for blank in required)
    required_inline=sum(blank.get('render_style')=='UNDERLINED_INLINE' for blank in required)
    # A source rule outside a real table is represented by a Word tab leader;
    # real table-cell rules remain schema-safe cell borders.
    rendered_figure_runs=sum('\u2007' in text for text in xml_counts['underlined_text'])
    rendered_bottom=xml_counts['bottom_border_count'] + xml_counts['leader_tab_stop_count'] + rendered_figure_runs
    rendered_inline=rendered_figure_runs
    invisible=max(0,required_bottom-rendered_bottom)+max(0,required_inline-rendered_inline)
    blank_errors=sorted(abs(float(blank.get('width_pt',0))-float(blank.get('rendered_width_pt',0))) for blank in blank_records)

    list_records=[record for record in records if record['kind']=='List' and 'paragraph_index' in record]
    hanging_errors=[]
    continuation_errors=[]
    sibling_groups=defaultdict(list)
    for record in list_records:
        paragraph=doc.paragraphs[record['paragraph_index']]
        left=paragraph.paragraph_format.left_indent.pt or 0.0
        first=paragraph.paragraph_format.first_line_indent.pt or 0.0
        # The list text anchor is the paragraph left edge; a true hanging
        # number always uses a negative first-line value.
        if first >= -0.5:
            hanging_errors.append({'text':paragraph.text,'first_line_indent_pt':first})
        actual_text=left+18.0
        expected_text=record.get('list_text_start_x')
        if expected_text is not None:
            continuation_errors.append(abs(actual_text-float(expected_text)))
        sibling_groups[tuple(record.get('list_group_key') or (record['source_page'],record.get('list_level',0)))].append(left)
    sibling_variances=[_variance(values) for values in sibling_groups.values() if len(values)>1]
    list_hanging_direction_error=len(hanging_errors)
    list_continuation_x_error=max(continuation_errors,default=0.0)
    list_sibling_indent_variance=max(sibling_variances,default=0.0)

    block_label_variances=[]
    block_value_variances=[]
    block_row_errors=[]
    for values in form_by_block.values():
        block_label_variances.append(_variance([record.get('label_x') for record in values]))
        block_value_variances.append(_variance([record.get('value_x') for record in values]))
        block_row_errors.append(max((float(record.get('x_error_pt', 0.0)) for record in values), default=0.0))

    counts={key:len(value) for key,value in issues.items()}
    source_visual_lines=sum(record.get('source_lines',len(record.get('source_baselines',[]))) for record in records)
    unsafe_scan=generation.get('word_safe_scan',{}) or {}
    unsafe_ooxml=int(bool(unsafe_scan.get('unsafe_ooxml',0)) or unsafe_scan.get('result') != 'PASS')
    mandatory={
        'nbsp_only_placeholder_count':xml_counts['nbsp_only_placeholder_count'],
        'invisible_required_blank_count':invisible,
        'list_hanging_direction_error':list_hanging_direction_error,
        'multi_label_form_row_count':counts['multi_label_form_row_count'],
        'form_paragraph_not_native_count':counts['form_paragraph_not_native_count'],
        'layout_tab_hack':docx_layout_counts(path)['layout_tab_hack'],
        'unsafe_ooxml':unsafe_ooxml,
    }
    result='NEEDS_REVIEW' if any(counts.values()) or any(value for value in mandatory.values()) else 'PASS'
    return {
        **docx_layout_counts(path),
        **counts,
        **mandatory,
        'logical_paragraph_count':len(body),
        'source_visual_line_count':source_visual_lines,
        'source_visual_lines':source_visual_lines,
        'generated_visual_lines':None,
        'line_wrap_delta':None,
        'detected_editable_blanks':len(blank_records),
        'visible_rule_blanks':sum(blank.get('render_style')=='BOTTOM_RULE' for blank in required),
        'plain_empty_blanks':sum(blank.get('render_style')=='PLAIN_EMPTY' for blank in blank_records),
        'blank_width_error_max':max(blank_errors,default=0.0),
        'blank_width_error_median':blank_errors[len(blank_errors)//2] if blank_errors else 0.0,
        'list_continuation_x_error_pt':list_continuation_x_error,
        'list_sibling_indent_variance_pt':list_sibling_indent_variance,
        'form_block_label_x_variance':max(block_label_variances,default=0.0),
        'form_block_value_x_variance':max(block_value_variances,default=0.0),
        'form_block_row_alignment_error':max(block_row_errors,default=0.0),
        'source_real_tables':generation.get('source_real_tables', generation.get('source_table_count', template.source_table_count)),
        'generated_real_tables':generation.get('generated_real_tables', generation.get('generated_table_count', len(doc.tables))),
        'synthetic_layout_tables':generation.get('synthetic_layout_tables', generation.get('form_layout_table_count', 0)),
        'paragraph_x_error_pt_max':max((float(record.get('x_error_pt', 0.0)) for record in records), default=0.0),
        'paragraph_y_error_pt_max':max((float(record.get('y_error_pt', 0.0)) for record in records), default=0.0),
        'tab_stop_usage':generation.get('tab_stop_usage', {}),
        'artifact_filter':generation.get('artifact_filter_report',{}),
        'issues':issues,
        'result':result,
    }
