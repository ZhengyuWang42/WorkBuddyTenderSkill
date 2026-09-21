"""SourceFormatTemplate -> public python-docx API -> fresh Word package.

There is deliberately no import of the diagnostic high-fidelity emitter.
PDF absolute positioning, artwork and complex merge geometry are degraded.
"""
import json
import re
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.section import WD_SECTION
from docx.shared import Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from .word_safe_xml import (clean_bootstrap, get_run_fonts, set_cell_bottom_border,
                           set_east_asian_font, set_run_fonts, set_table_cell_margins,
                           set_table_indent, set_table_width)
from .source_fill_policy import slot_replacement
from .source_fill_patterns import (
    EVIDENCE_DIRECT,
    EVIDENCE_INVENTED,
    UNDERLINED_BLANK_KINDS,
)
from .source_font_policy import font_name
from .logical_structure import LogicalTablePlan, build_logical_source_tables
from .page_layout import (
    INLINE_BLANK_PREFIX,
INLINE_COMPOSITION_PREFIX,
INLINE_COMPOSITION_SUFFIX,
parse_inline_rule_composition_token,
    INLINE_BLANK_SUFFIX,
    parse_inline_blank_token,
    EditableBlank,
    EditableBlankKind,
    EditableBlankRenderStyle,
    BlankRepresentationKind,
    infer_semantic_line_spacing,
    FormBlock,
    FormRowGeometry,
    LogicalParagraph,
    ParagraphLayout,
    ParagraphLayoutRole,
    ParagraphTabStop,
    AlignmentRole,
    build_page_layout,
    bounded_scale,
    form_parts,
    join_visual_lines,
    paragraph_coordinate_frame,
    restore_inline_rule_blanks,
)

ALIGN = {
    'left': WD_ALIGN_PARAGRAPH.LEFT,
    'center': WD_ALIGN_PARAGRAPH.CENTER,
    'right': WD_ALIGN_PARAGRAPH.RIGHT,
    'justify': WD_ALIGN_PARAGRAPH.JUSTIFY,
}

#: The two inline positioned-atom token shapes, compiled once.  Both are matched
#: against the same restored source line so the emitter can dispatch on whichever
#: the source places first.
_INLINE_BLANK_PATTERN = re.compile(
    re.escape(INLINE_BLANK_PREFIX) + r'(.*?)' + re.escape(INLINE_BLANK_SUFFIX)
)
_INLINE_COMPOSITION_PATTERN = re.compile(
    re.escape(INLINE_COMPOSITION_PREFIX) + r'(.*?)'
    + re.escape(INLINE_COMPOSITION_SUFFIX)
)


def new_word_safe_document():
    doc = Document()
    clean_bootstrap(doc)
    cp = doc.core_properties
    cp.title, cp.subject, cp.author = '基础投标文件', '招标文件格式继承', 'WorkBuddyTenderSkill'
    cp.comments = cp.last_modified_by = cp.keywords = ''
    style = doc.styles['Normal']
    set_east_asian_font(style, '宋体')
    style.font.size = Pt(10.5)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_after = Pt(0)
    return doc


def add_safe_run(paragraph, text, source=None, underline=None):
    run = paragraph.add_run()
    source_name = getattr(source, 'east_asia_font', None) or getattr(source, 'font_name', '') or '宋体'
    name, _ = font_name(source_name)
    latin = getattr(source, 'latin_font', None) or name
    set_run_fonts(run, name, latin)
    run.font.size = Pt(max(1, min(1638, getattr(source, 'font_size', 0) or 10.5)))
    run.bold = bool(getattr(source, 'bold', False))
    run.italic = bool(getattr(source, 'italic', False))
    run.underline = bool(getattr(source, 'underline', False)) if underline is None else underline
    run.font.color.rgb = RGBColor(0, 0, 0)
    baseline_role = getattr(source, 'baseline_role', 'NORMAL')
    run.font.superscript = baseline_role == 'SUPERSCRIPT'
    run.font.subscript = baseline_role == 'SUBSCRIPT'
    for index, line in enumerate(text.split('\n')):
        if index:
            run.add_break(WD_BREAK.LINE)
        run.add_text(line)
    return run


def _key(locator):
    return json.dumps(locator.model_dump(mode='json'), sort_keys=True)


def _paragraph_text(source):
    """Legacy callable: only join when the direct line stream is complete."""
    lines = source.lines
    if not lines or '\n'.join(l.text for l in lines) != source.text:
        return source.text
    return join_visual_lines(source.text)


class ParagraphFormRenderer:
    """Render a semantic ``FormBlock`` as ordinary Word paragraphs.

    ``FormBlock`` remains useful as a source-geometry grouping, but it is not
    a Word container. A paragraph indent establishes the shared left column;
    tab stops are used only for anchors on the same physical source line.
    """

    _SIGNATURE_LABELS = ('投标人', '供应商', '法定代表人', '委托代理人', '授权代表', '签字', '盖章')
    _CONTACT_LABELS = ('投标单位全称', '单位性质', '地址', '网址', '电话', '传真', '邮政编码',
                       '开户银行', '账号', '授权代表', '供应商名称', '经营期限')

    def __init__(self, builder):
        self.builder = builder

    @staticmethod
    def _source_run(row):
        return next((run for run in row.item.source.runs if run.text.strip()), None)

    @staticmethod
    def _blank_for(row, blank_cursor):
        if blank_cursor < len(row.blanks):
            return row.blanks[blank_cursor]
        return EditableBlank(
            kind=EditableBlankKind.SOURCE_EMPTY,
            source_x0=0.0,
            source_x1=1.0,
            width_pt=1.0,
            semantic_slot=None,
            render_style=EditableBlankRenderStyle.PLAIN_EMPTY,
            source_locator=row.item.source.locator,
        )

    @staticmethod
    def _is_blank(row, index, part):
        if row.row_type == 'DATE_ROW':
            labeled = bool(row.parts and row.parts[0].strip().endswith(('：', ':')))
            return index in ([1, 3, 5] if labeled else [0, 2, 4])
        return index % 2 == 1 and not part.strip(' _＿\t\r\n')

    @classmethod
    def _role(cls, row):
        compact = re.sub(r'\s+', '', row.item.logical_text)
        if row.row_type == 'DATE_ROW' or re.search(r'年.*月.*日', compact):
            return ParagraphLayoutRole.DATE_LINE
        if any(label in compact for label in cls._SIGNATURE_LABELS):
            return ParagraphLayoutRole.SIGNATURE_LINE
        if any(label in compact for label in cls._CONTACT_LABELS):
            return ParagraphLayoutRole.CONTACT_LINE
        return ParagraphLayoutRole.FORM_LINE

    @staticmethod
    def _compact(value):
        return re.sub(r'\s+', '', value or '')

    def _part_anchor(self, row, part, previous_x):
        """Find a source x anchor for a following label or annotation."""
        if part.strip().startswith(('（', '(')):
            return max(previous_x + 1.0, float(row.annotation_x))
        compact = self._compact(part)
        if compact:
            spans = [span for line in row.item.source_lines for span in line.spans if span.text.strip()]
            for span in spans:
                if compact in self._compact(span.text):
                    return max(previous_x + 1.0, float(span.bbox[0]))
        return max(previous_x + 6.0, float(row.item.bbox[0]) +
                   self.builder._form_text_width(part, row.item.font_size_pt))

    @staticmethod
    def _tab_position(source_x, label_x, *, page_content_x0=18.0):
        """Convert a source x coordinate into an OOXML tab-stop position.

        ``w:tab/@w:pos`` is measured from the page text margin, not from the
        paragraph indent.  ``source_x`` and ``label_x`` are absolute page
        coordinates while ``page_content_x0`` is that left margin, so all
        stops are measured from the same origin the renderer uses.  Measuring
        from ``label_x`` instead shifted every stop right by the paragraph
        indent and could push a leader past the cursor so that no leader was
        painted at all.
        """
        return max(1.0, float(source_x) - float(page_content_x0))

    def _add_tab(self, paragraph, source, *, source_x, label_x, leader='NONE', purpose='anchor', page_content_x0=18.0):
        position = self._tab_position(source_x, label_x, page_content_x0=page_content_x0)
        paragraph.paragraph_format.tab_stops.add_tab_stop(
            Pt(position), WD_TAB_ALIGNMENT.LEFT,
            WD_TAB_LEADER.LINES if leader == 'LINES' else WD_TAB_LEADER.SPACES,
        )
        self.builder._add_run(paragraph, '\t', source)
        self.builder.tab_stop_usage['anchor_tabs' if leader != 'LINES' else 'leader_tabs'] += 1
        if leader == 'LINES':
            self.builder.tab_stop_usage['form_tab_leader_count'] = self.builder.tab_stop_usage.get('form_tab_leader_count', 0) + 1
        if purpose == 'annotation':
            self.builder.tab_stop_usage['annotation_tabs'] += 1
        if purpose == 'date':
            self.builder.tab_stop_usage['date_tabs'] += 1
        if purpose == 'multi_field':
            self.builder.tab_stop_usage['multi_field_tabs'] += 1
        return ParagraphTabStop(
            position_pt=position,
            source_x=float(source_x),
            leader=leader,
            alignment='left',
            purpose=purpose,
        )

    def _record_fill(self, slot, value, method, run, paragraph):
        self.builder._record_fill(slot, value, method, run, paragraph)

    def _render_figure_blank(self, paragraph, blank, source, *, content_right):
        """Render a visible blank when punctuation follows the field.

        A terminal/near-terminal tab leader is not painted consistently by
        all Word-compatible renderers when the next character is punctuation.
        Figure spaces keep that field on the same physical line without
        introducing a second paragraph or an underscore placeholder.
        """
        display_x1=min(float(blank.source_x1), float(content_right))
        display_width=max(1.0, display_x1-float(blank.source_x0))
        self.builder._register_blank(blank, rendered_width=display_width, visible=True)
        size=max(6.0, float(getattr(source, 'font_size', 10.5) or 10.5))
        count=max(2, int(round(display_width/(size*.55))))
        self.builder._add_run(paragraph, '\u2007'*count, source, underline=True)
        return True

    #: Round 5.6 blank kinds that the source draws as a solid line.  Word
    #: renders an underlined run as one continuous rule, so this is the
    #: compatible representation; an underscore tab leader paints separate
    #: underscore glyphs and is a *different* blank mechanism.
    SOLID_RULE_KINDS = (
        'VECTOR_LINE',
        'UNDERLINED_WHITESPACE',
        'MIXED',
    )

    def _is_solid_rule_blank(self, blank) -> bool:
        kind = getattr(blank, "representation_kind", None)
        return str(getattr(kind, "value", kind)) in self.SOLID_RULE_KINDS

    def _render_solid_rule_blank(self, paragraph, blank, source, *, width, content_right):
        """Render a source drawn rule as one continuous underlined run."""

        display_x1 = min(float(blank.source_x1), float(content_right))
        display_width = max(1.0, min(float(width), display_x1 - float(blank.source_x0)))
        self.builder._register_blank(blank, rendered_width=display_width, visible=True)
        size = max(6.0, float(getattr(source, "font_size", 10.5) or 10.5))
        count = max(2, int(round(display_width / (size * .55))))
        self.builder._add_run(paragraph, '\u2007' * count, source, underline=True)
        self.builder.tab_stop_usage['solid_rule_blanks'] = (
            self.builder.tab_stop_usage.get('solid_rule_blanks', 0) + 1
        )
        return display_width

    def _render_blank(self, paragraph, row, blank, source, slots, part_index, *, label_x, purpose, content_right, page_content_x0=18.0):
        replacement = self.builder._row_replacement(row, part_index, slots)
        if replacement is not None:
            slot, (value, method) = replacement
            destination = slot.destination_style
            # Round 5.6 SOURCE_FILL_PATTERN: the fact value supplies content
            # only.  When the source field is a visible blank (a drawn rule, an
            # underlined whitespace region), the filled value keeps that line;
            # knowing the value must never delete the source's own affordance.
            pattern = self.builder._fill_pattern_for(slot, blank)
            self.builder._record_blank_kind_authority(blank, pattern)
            keep_underline = bool(getattr(destination, "underline", False)) or bool(
                getattr(pattern, "value_is_underlined", False)
            ) or self._is_solid_rule_blank(blank)
            self.builder.fill_pattern_usage['filled_slots'] += 1
            if pattern is not None:
                self.builder.fill_pattern_usage['pattern_matched'] += 1
            if keep_underline:
                self.builder.fill_pattern_usage['value_kept_source_underline'] += 1
            else:
                self.builder.fill_pattern_usage['value_plain_whitespace'] += 1
            value_run=self.builder._add_run(paragraph, value, destination,
                                   underline=keep_underline)
            # A centred form slot is only completed to its source width when the
            # source itself draws a rule there.  Filling the remainder of a slot
            # whose page-local evidence is plain whitespace would paint an
            # underline the source never draws - the invented trailing rule that
            # appeared after the project number.
            source_rule_blank = (
                blank.render_style == EditableBlankRenderStyle.BOTTOM_RULE
                or self._is_solid_rule_blank(blank)
                or bool(getattr(pattern, "value_is_underlined", False))
            )
            if row.centered_form_line is not None and source_rule_blank:
                remaining=max(0.0, row.centered_form_line.slot_width-
                              self.builder._form_text_width(value, destination.font_size))
                if remaining > destination.font_size * .25:
                    count=max(1,int(round(remaining/(destination.font_size*.55))))
                    self.builder._add_run(paragraph,'\u2007'*count,destination,underline=True)
            self._record_fill(slot, value, method, value_run, paragraph)
            self.builder._register_blank(
                blank,
                rendered_width=(blank.width_pt if row.centered_form_line is not None else
                    max(blank.width_pt, self.builder._form_text_width(value, destination.font_size))),
                visible=True,
            )
            return None, True
        if blank.representation_kind == BlankRepresentationKind.LITERAL_UNDERSCORES:
            placeholder = blank.raw_placeholder
            self.builder._register_blank(
                blank, rendered_width=blank.width_pt, visible=bool(placeholder)
            )
            if placeholder:
                self.builder._add_run(paragraph, placeholder, source, underline=False)
            return None, False
        visible = blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY
        self.builder._record_blank_kind_authority(blank, None)
        display_x1 = min(float(blank.source_x1), float(content_right))
        display_width = max(1.0, display_x1 - float(blank.source_x0))
        self.builder._register_blank(
            blank,
            rendered_width=display_width if visible else blank.width_pt,
            visible=visible,
        )
        if not visible:
            return None, False
        if row.centered_form_line is not None:
            count=max(2,int(round(row.centered_form_line.slot_width/
                                  (max(6.0,row.item.font_size_pt)*.55))))
            self.builder._add_run(paragraph,'\u2007'*count,source,underline=True)
            return None, False
        return self._add_tab(
            paragraph,
            source,
            source_x=display_x1,
            label_x=label_x,
            leader='LINES',
            purpose=purpose,
            page_content_x0=page_content_x0,
        ), False

    def _render_row(self, doc, row, block, *, page_content_x0, page_content_x1, scale, space_before):
        source = self._source_run(row)
        p = doc.add_paragraph(style='Normal')
        role = self._role(row)
        blanks_for_anchor = row.blanks
        date_row = row.row_type == 'DATE_ROW'
        # Date/signature rows may occupy a right-side source region inside a
        # broader contact block. Their first rule is the reliable paragraph
        # anchor, including the labeled ``日期：`` form.
        label_x = float(min((blank.source_x0 for blank in blanks_for_anchor), default=block.label_x)) if date_row else float(block.label_x)
        pf = p.paragraph_format
        centered = row.item.alignment_role == AlignmentRole.CENTERED_FORM_LINE
        pf.left_indent = Pt(0 if centered else max(0.0, label_x - page_content_x0))
        pf.right_indent = Pt(0)
        pf.first_line_indent = Pt(0)
        pf.space_before = Pt(max(0.0, space_before))
        pf.space_after = Pt(0)
        spacing = infer_semantic_line_spacing(
            row.item.font_size_pt, row.item.line_pitch_pt * scale,
            source_locator=row.item.source.locator,
        )
        pf.line_spacing = spacing.word_value
        pf.widow_control = False
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.LEFT
        slots = self.builder._item_slots(row.item)
        tab_specs = []
        blank_cursor = 0
        previous_anchor = label_x
        for part_index, part in enumerate(row.parts):
            if self._is_blank(row, part_index, part):
                blank = self._blank_for(row, blank_cursor)
                blank_cursor += 1
                purpose = 'date' if role == ParagraphLayoutRole.DATE_LINE else (
                    'multi_field' if row.row_type == 'MULTI_INLINE_FIELDS' else 'blank'
                )
                date_replacement = self.builder._row_replacement(row, part_index, slots) if role == ParagraphLayoutRole.DATE_LINE else None
                if role == ParagraphLayoutRole.DATE_LINE and blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY and date_replacement is None:
                    display_x1 = min(float(blank.source_x1), float(page_content_x1))
                    display_width = max(1.0, display_x1 - float(blank.source_x0))
                    self.builder._register_blank(blank, rendered_width=display_width, visible=True)
                    size = max(6.0, float(getattr(source, 'font_size', row.item.font_size_pt) or 10.5))
                    count = max(2, int(round(display_width / (size * .55))))
                    self.builder._add_run(p, '\u2007' * count, source, underline=True)
                    self.builder.tab_stop_usage['date_underlined_runs'] = self.builder.tab_stop_usage.get('date_underlined_runs', 0) + 1
                    previous_anchor = max(previous_anchor, display_x1)
                    continue
                next_part = next((candidate for candidate in row.parts[part_index + 1:] if candidate.strip()), '')
                if (
                    row.centered_form_line is None
                    and self._is_solid_rule_blank(blank)
                    and blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY
                    and self.builder._row_replacement(row, part_index, slots) is None
                ):
                    # The source draws this field as a solid rule: emit one
                    # continuous underlined run instead of an underscore tab
                    # leader, so the delivered blank looks like the source
                    # blank and stays an editable Word run.
                    self._render_solid_rule_blank(
                        p, blank, source,
                        width=min(float(blank.source_x1), float(page_content_x1)) - float(blank.source_x0),
                        content_right=page_content_x1,
                    )
                    previous_anchor = max(previous_anchor, min(float(blank.source_x1), float(page_content_x1)))
                    continue
                if (
                    row.row_type == 'MULTI_INLINE_FIELDS'
                    and not any(candidate.strip() for candidate in row.parts[part_index + 1:])
                    and blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY
                    and self.builder._row_replacement(row, part_index, slots) is None
                ):
                    self._render_figure_blank(
                        p, blank, source, content_right=page_content_x1
                    )
                    previous_anchor=max(previous_anchor, blank.source_x1)
                    continue
                spec, filled = self._render_blank(
                    p, row, blank, source, slots, part_index,
                    label_x=label_x, purpose=purpose, content_right=page_content_x1,
                    page_content_x0=page_content_x0,
                )
                if spec is not None:
                    tab_specs.append(spec)
                    previous_anchor = max(previous_anchor, spec.source_x)
                    # LibreOffice and some Word builds do not paint a leader
                    # for a trailing tab.  A small source-width run of
                    # underlined figure spaces is the Word-native fallback;
                    # it contains no underscore or NBSP placeholder.
                    # A terminal leader already paints through the requested
                    # stop.  Do not append the visual fallback when that stop
                    # is at the page content edge: the fallback would begin
                    # after the leader and wrap onto a second line (notably
                    # for clipped right-side contact rules in case_002).
                    if (not any(next_part.strip() for next_part in row.parts[part_index + 1:])
                            and min(float(blank.source_x1), float(page_content_x1)) < float(page_content_x1) - 1.0):
                        size = max(6.0, float(getattr(source, 'font_size', row.item.font_size_pt) or 10.5))
                        display_width = max(1.0, min(float(blank.source_x1), float(page_content_x1)) - float(blank.source_x0))
                        count = max(2, int(round(display_width / (size * .55))))
                        self.builder._add_run(p, '\u2007' * count, source, underline=True)
                        self.builder.tab_stop_usage['terminal_rule_fallback'] = self.builder.tab_stop_usage.get('terminal_rule_fallback', 0) + 1
                elif filled:
                    previous_anchor = max(previous_anchor, blank.source_x1)
                if not filled and blank.render_style == EditableBlankRenderStyle.PLAIN_EMPTY:
                    previous_anchor = max(previous_anchor, blank.source_x1)
                continue
            if not part:
                continue
            target = self._part_anchor(row, part, previous_anchor)
            is_annotation = part.strip().startswith(('（', '('))
            is_following_label = bool(re.search(r'[：:]\s*$', part.strip()))
            if p.text and (is_annotation or is_following_label) and target > previous_anchor + 1:
                spec = self._add_tab(
                    p, source, source_x=target, label_x=label_x,
                    leader='NONE', purpose='annotation' if is_annotation else 'multi_field',
                    page_content_x0=page_content_x0,
                )
                tab_specs.append(spec)
                previous_anchor = target
            # Every nonblank source fragment belongs in the paragraph. The
            # tab branch above only adds an anchor before an annotation or
            # following label; it must not suppress the fragment itself when
            # this is the first run on the line.
            self.builder._add_run(p, part, source)
            previous_anchor = max(
                previous_anchor,
                target + self.builder._form_text_width(part, getattr(source, 'font_size', row.item.font_size_pt)),
            )
        if '\t' in p.text:
            self.builder.tab_stop_usage['paragraphs_with_tabs'] += 1
        self.builder.paragraph_form_count += 1
        layout = ParagraphLayout(
            role=role,
            container_x0=float(block.container_x0),
            container_x1=float(block.container_x1),
            # Date/signature rows can occupy a right-side local region inside
            # a broader FormBlock.  The paragraph's actual source anchor is
            # the first editable/date rule used above, not the block row's
            # broad text bbox origin.
            source_x0=float(label_x),
            source_y0=float(row.item.bbox[1]),
                alignment='center' if centered else 'left',
            left_indent_pt=float(pf.left_indent.pt or 0.0),
            right_indent_pt=float(pf.right_indent.pt or 0.0),
            first_line_indent_pt=float(pf.first_line_indent.pt or 0.0),
            space_before_pt=float(pf.space_before.pt or 0.0),
            space_after_pt=float(pf.space_after.pt or 0.0),
            line_spacing=float(pf.line_spacing or 1.0),
            tab_stops=tab_specs,
            runs=list(p.runs),
            source_locator=row.item.source.locator,
            source_page=row.item.source.page,
        )
        return p, layout

    def render_block(self, doc, block, *, page_content_x0, page_content_x1, scale, initial_space_before):
        paragraphs = []
        previous_bottom = None
        for index, row in enumerate(block.row_geometries):
            gap = initial_space_before if index == 0 else max(0.0, row.item.bbox[1] - previous_bottom) * scale
            paragraph, layout = self._render_row(
                doc, row, block,
                page_content_x0=page_content_x0,
                page_content_x1=page_content_x1,
                scale=scale,
                space_before=gap,
            )
            paragraphs.append((paragraph, layout, row))
            previous_bottom = row.item.bbox[3]
        return paragraphs


class WordSafeSourceDocumentBuilder:
    def __init__(self, facts, template, *, page_scales=None):
        self.facts, self.template = facts, template
        self.filled = []
        self.warnings = ['FORMAT_DEGRADED_FOR_WORD_COMPATIBILITY: geometry mapped to safe paragraph spacing and paragraph-native form lines; no absolute positioning',
                         'FORMAT_DEGRADED_FOR_WORD_COMPATIBILITY: vector artwork, glyph offsets and micro-kerning omitted; row heights are minimums']
        self.expected = []
        self.layouts = [build_page_layout(page) for page in template.source_pages]
        self.page_scales = {page: bounded_scale(scale) for page, scale in (page_scales or {}).items()}
        self.font_substitutions = []
        self.table_style_outliers = [outlier for page in template.source_pages for table in page.tables
                                     for outlier in table.style_outliers]
        self.semantic_slot_corrections = []
        self.paragraph_form_count = 0
        self.form_block_count = 0
        self.paragraph_layouts = []
        self.tab_stop_usage = {'paragraphs_with_tabs': 0, 'leader_tabs': 0, 'anchor_tabs': 0,
                               'form_tab_leader_count': 0, 'date_tabs': 0,
                               'date_underlined_runs': 0, 'terminal_rule_fallback': 0,
                               'annotation_tabs': 0, 'multi_field_tabs': 0,
                               'solid_rule_blanks': 0}
        #: Round 5.6 SOURCE_FILL_PATTERN usage: how often a filled value kept
        #: the source's own visible blank instead of replacing its mechanism.
        self.fill_pattern_usage = {'filled_slots': 0, 'pattern_matched': 0,
                                   'value_kept_source_underline': 0,
                                   'value_plain_whitespace': 0,
                                   'local_evidence_direct': 0,
                                   'local_evidence_derived': 0,
                                   'generic_role_override': 0}
        #: Round 5.7 page-local blank authority: every blank whose Word
        #: affordance was decided by a semantic-role default instead of the
        #: source's own page-local representation.  Must stay empty.
        self.generic_role_overrode_source_blank_kind = []
        self.blank_kind_authority = []
        #: Round 5.8 source-positioned blank emission records: every blank placed
        #: by explicit source tab stops rather than a repeated-space count.
        self.positioned_blank_records = []
        #: Source rules the linear paragraph flow cannot reach (drawn left of the
        #: text already emitted).  Reported, never silently mis-painted.
        self.unreachable_positioned_blank_count = 0
        self.paragraph_x_errors = []
        self.paragraph_y_errors = []
        self.form_renderer = ParagraphFormRenderer(self)
        self.vector_blanks_recovered = 0
        #: Round 5.8 rule-relation state: the current page's classified rule
        #: relations, the underline-rule extents applied to owning runs, and the
        #: paragraph currently being emitted at a source-positioned blank.
        self._page_rule_relations = []
        self._underline_rule_spans = []
        self._underlined_source_run_ids = set()
        self._active_source_page = None
        #: Round 5.8 narrow SOURCE_FORM_LAYOUT_LINE uses, each with its locator
        #: and reason, so the remedy can never be applied silently.
        self.positioned_form_layout_breaks = []
        #: Every classified source rule in the document, with a stable id, so a
        #: generated rule's provenance resolves document-wide rather than only
        #: inside the page QA happens to look at.
        self.source_rule_registry = []
        #: SOURCE_FORM_LINE_PARAGRAPH state: when the inline-token path is in
        #: form-line mode, each source visual form line that owns a rule opens a
        #: new Word paragraph through ``_form_line_paragraph_factory``.
        self._source_form_line_mode = False
        self._form_line_paragraph_factory = None
        self._form_line_has_content = False
        self._form_line_previous = None
        self._form_line_managed_paragraphs = set()
        #: The source visual rows already isolated by a form-line paragraph, so
        #: a second rule on the same row stays in that row's paragraph context.
        self._form_line_source_rows = set()
        #: The paragraph a source visual line was assembled into *before* its own
        #: text was emitted.  A row that already owns its Word paragraph context
        #: never opens a second one, and the atomic positioners keep using the
        #: paragraph the row was assembled in.
        self._row_context_paragraph = None
        #: The paragraph the current element's next text must be emitted into.
        #: A promoted form-line paragraph belongs to the element's remaining
        #: flow, so the source's own reading order survives the promotion.
        self._current_emission_paragraph = None
        #: SourceVisualLineEmissionPlan records, one per source visual line the
        #: renderer assembled, in emission order.
        self.source_visual_line_emission_plans = []
        #: Source visual rows that carry a positioned atom in a later row but
        #: whose element has no source-form-line paragraph activated, so the row
        #: keeps the accepted inline emission.
        self.source_visual_line_assembly_gaps = []
        #: SOURCE_FORM_LINE_PARAGRAPH records, one per created form-line
        #: paragraph, with the source form line metadata the gate requires.
        self.source_form_line_paragraphs = []
        #: SOURCE_ANCHORED_VALUE_RUN records: the resolved value itself is the
        #: representation, positioned at its source rule's start anchor.
        self.source_anchored_value_runs = []
        #: The subset of the above emitted by an eligible SOURCE_FORM_LINE owner
        #: executing a planned RESOLVED_VALUE_IN_FIXED_SLOT, with the execution
        #: owner and SourceFillApplication each one produced.
        self.source_form_line_value_runs = []
        #: Renderer execution ownership: one record per source form field the
        #: renderer established an active representation for.
        self.source_form_execution_owners = []
        #: Raw value writes performed by an owning representation, in emission
        #: order, used to collapse a composite write into one logical record.
        self.filled_value_writes = []
        self.logical_application_merges = []
        #: Generated paragraph index -> the anchored rule whose representation
        #: owns that paragraph, so a second composite slot write folds into the
        #: one logical application instead of becoming a second field record.
        self._anchored_paragraph_rules = {}
        #: SOURCE_RULE_COMPOSITION records: one logical source rule emitted as
        #: ordered empty and text segments whose union is the rule extent.
        self.source_rule_compositions = []
        self._active_source_run = None
        #: Source visual line id per classified rule, so an anchored value can
        #: name the source form line it belongs to.
        self._rule_source_visual_line = {}
        self._anchored_rule_applied = set()
        #: Declared paragraph coordinate frames, one per positioned rule.
        self._positioned_coordinate_frames = []
        self._positioned_paragraph = None
        self._positioned_paragraph_start = 0
        self.logical_records = []
        self.blank_records = []
        self.inline_blank_count = 0
        self.plain_empty_blank_count = 0
        self.visible_rule_blank_count = 0
        self.blank_width_errors = []
        for page in template.source_pages:
            runs = [r for p in page.paragraphs for r in p.runs] + [r for t in page.tables for row in t.rows for c in row.cells for r in c.runs]
            for run in runs:
                mapped, changed = font_name(run.font_name)
                if changed and (run.font_name, mapped) not in self.font_substitutions:
                    self.font_substitutions.append((run.font_name, mapped))

    def _add_run(self, paragraph, text, source=None, underline=None):
        """Hook for the style-first builder; the Round 4.9 path is unchanged."""

        return add_safe_run(paragraph, text, source, underline)

    def _record_fill(self, slot, value, method, run, paragraph):
        profile=slot.destination_style
        east_asia_font, latin_font = get_run_fonts(run)
        paragraph_alignment={
            WD_ALIGN_PARAGRAPH.CENTER: 'center', WD_ALIGN_PARAGRAPH.RIGHT: 'right',
            WD_ALIGN_PARAGRAPH.JUSTIFY: 'justify', WD_ALIGN_PARAGRAPH.LEFT: 'left',
        }.get(paragraph.alignment, 'left')
        self.filled.append({
            'slot_id': slot.slot_id,
            'value': value,
            'method': method,
            'field': [allowed_field.value for allowed_field in slot.allowed_fact_fields],
            'source_locator': slot.source_locator.model_dump(mode='json'),
            'source_page': slot.source_page,
            'slot_role': 'TABLE_VALUE' if slot.container_type == 'table_cell' else 'FORM_VALUE',
            'destination_expected_style': profile.model_dump(mode='json'),
            'generated_value_style': {
                'east_asia_font': east_asia_font,
                'latin_font': latin_font,
                'font_size': run.font.size.pt if run.font.size is not None else None,
                'bold': bool(run.bold),
                'italic': bool(run.italic),
                'underline': bool(run.underline),
                'color': str(run.font.color.rgb) if run.font.color.rgb is not None else None,
                'font_weight_role': 'bold' if run.bold else profile.font_weight_role,
                'paragraph_alignment': paragraph_alignment,
            },
        })

    def _record_blank_kind_authority(self, blank, pattern):
        """Page-local blank authority: source evidence outranks role defaults.

        A blank whose page-local representation is *not* a visible rule may
        only be rendered as one when the source itself says so.  When the
        chosen fill pattern comes from the semantic-role index instead, the
        generic role has overridden the source, which is a Round 5.7 gate.
        """

        representation = (
            blank.representation_kind.value
            if hasattr(blank.representation_kind, "value")
            else str(blank.representation_kind)
        )
        evidence = (
            getattr(pattern, "evidence_kind", EVIDENCE_INVENTED)
            if pattern is not None
            else (EVIDENCE_DIRECT if representation in {"VECTOR_LINE", "LITERAL_UNDERSCORES"}
                  else EVIDENCE_INVENTED)
        )
        blank_kind = (
            getattr(pattern, "blank_kind", None) if pattern is not None else None
        )
        role_override = (
            evidence == EVIDENCE_INVENTED
            and blank_kind in UNDERLINED_BLANK_KINDS
            and getattr(pattern, "value_is_underlined", False)
        )
        record = {
            'semantic_slot': blank.semantic_slot,
            'representation_kind': representation,
            'evidence_kind': evidence,
            'role_blank_kind': blank_kind,
            'role_override': role_override,
        }
        if record not in self.blank_kind_authority:
            self.blank_kind_authority.append(record)
        if evidence == EVIDENCE_DIRECT:
            self.fill_pattern_usage['local_evidence_direct'] += 1
        elif evidence == EVIDENCE_INVENTED:
            pass
        else:
            self.fill_pattern_usage['local_evidence_derived'] += 1
        if role_override:
            self.fill_pattern_usage['generic_role_override'] += 1
            entry = {
                'semantic_slot': blank.semantic_slot,
                'representation_kind': representation,
                'role_blank_kind': blank_kind,
                'source_page': getattr(
                    getattr(blank, 'source_locator', None), 'page', None
                ),
            }
            if entry not in self.generic_role_overrode_source_blank_kind:
                self.generic_role_overrode_source_blank_kind.append(entry)

    def _register_blank(self, blank, *, rendered_width=None, visible=None):
        width=float(blank.width_pt)
        actual=width if rendered_width is None else float(rendered_width)
        self.blank_records.append({
            'kind': blank.kind.value if hasattr(blank.kind,'value') else str(blank.kind),
            'source_x0': blank.source_x0,
            'source_x1': blank.source_x1,
            'width_pt': width,
            'semantic_slot': blank.semantic_slot,
            'render_style': blank.render_style.value if hasattr(blank.render_style,'value') else str(blank.render_style),
            'source_locator': blank.source_locator.model_dump(mode='json') if hasattr(blank.source_locator,'model_dump') else None,
            'representation_kind': blank.representation_kind.value if hasattr(blank.representation_kind,'value') else str(blank.representation_kind),
            'raw_placeholder': blank.raw_placeholder,
            'rendered_width_pt': actual,
            'visible': bool(visible if visible is not None else blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY),
        })
        self.blank_width_errors.append(abs(actual-width))
        if blank.render_style == EditableBlankRenderStyle.BOTTOM_RULE:
            self.visible_rule_blank_count += 1
        if blank.render_style == EditableBlankRenderStyle.PLAIN_EMPTY:
            self.plain_empty_blank_count += 1

    #: Word's ``w:tab/@w:pos`` and a paragraph's tab stops are measured from the
    #: page text margin, which is the same origin the renderer uses.
    def _source_tab_position(self, source_x, reference_origin):
        """A source x converted to the offset Word measures tab stops in.

        The reference origin is supplied by the caller from the declared
        :class:`ParagraphCoordinateFrame`.  ``WORD_TAB_REFERENCE_MODEL`` measures
        tab stops from the section text margin; a paragraph's own indent moves
        where its text starts without moving the ruler, so it is deliberately not
        folded in.  The origin must be the section margin the *paragraph* renders
        under - the same value the section geometry gave the emitter - because a
        frame that reads a different section's margin silently offsets every
        positioned rule.
        """

        return max(1.0, float(source_x) - float(reference_origin))

    def _paragraph_left_indent(self, paragraph) -> float:
        """The paragraph's own left indent, the shift Word applies to tab stops."""

        try:
            value = paragraph.paragraph_format.left_indent
        except Exception:
            return 0.0
        return float(getattr(value, "pt", 0.0) or 0.0)

    def _form_advance_width(self, text, font_size):
        """Estimated advance width of ``text``, for deciding tab anchors.

        This is only used to decide *whether* a source-positioned tab anchor is
        needed; the blank's own physical span always comes from the source
        ``x0``/``x1`` tab stops, never from a repeated-space count.
        """

        total = 0.0
        for char in str(text or ""):
            if "\u2007" in char or char == "\u00a0":
                total += font_size * 0.5
            elif ord(char) > 0x2E80:
                total += font_size
            elif char == " ":
                total += font_size * 0.25
            else:
                total += font_size * 0.5
        return total

    def _rule_line_y(self, x0, x1):
        """Source y of the registered rule at this exact source extent."""

        for entry in getattr(self, "source_rule_registry", []):
            if abs(entry["x0"] - float(x0)) <= 1.0 and abs(entry["x1"] - float(x1)) <= 1.0:
                return entry["y"]
        return None

    def _same_split_line(self, x0, x1):
        """Whether this rule sits on the line a composition already isolated."""

        line_y = getattr(self, "_form_line_split_line_y", None)
        if line_y is None:
            return False
        rule_y = self._rule_line_y(x0, x1)
        return rule_y is not None and abs(float(rule_y) - float(line_y)) <= 2.0

    def _register_form_line_source_row(self, rule_y):
        """Mark a source visual row as isolated by a form-line paragraph."""

        if rule_y is None:
            return
        rows = getattr(self, "_form_line_source_rows", None)
        if rows is None:
            rows = set()
            self._form_line_source_rows = rows
        rows.add(round(float(rule_y), 1))

    def _same_source_line_rule(self, x0, x1):
        """Whether this rule shares a source visual line with the isolated one.

        A source visual line can carry more than one fill rule.  The line is a
        single physical row, so every rule on it belongs to the one paragraph
        context the first of them opened; promoting a later one would place it
        below its own source row.  The evidence is the source rules' own y
        geometry - never a page, rule id or literal text.
        """

        rule_y = self._rule_line_y(x0, x1)
        if rule_y is None:
            return False
        rows = getattr(self, "_form_line_source_rows", set())
        return any(abs(float(row) - float(rule_y)) <= 2.0 for row in rows)

    def _start_source_form_line_paragraph(self, paragraph, source, span=None):
        """Begin a SOURCE_FORM_LINE_PARAGRAPH for the next source form line.

        A source visual form line that carries its own rule needs its own Word
        paragraph coordinate context: a line break does not create one, so the
        next line would inherit this paragraph's tab stops and indents.  This
        opens a fresh paragraph through the normal python-docx API instead.
        """

        factory = getattr(self, "_form_line_paragraph_factory", None)
        if factory is None:
            return paragraph
        span_x0 = float(span[0]) if span else None
        span_x1 = float(span[1]) if span else None
        source_rule_id = None
        if span_x0 is not None:
            for entry in getattr(self, "source_rule_registry", []):
                if (
                    abs(entry["x0"] - span_x0) <= 1.0
                    and abs(entry["x1"] - span_x1) <= 1.0
                ):
                    source_rule_id = entry["source_rule_id"]
                    break
        record = {
            "source_page": self._active_source_page,
            "source_rule_id": source_rule_id,
            "source_rule_ids": [source_rule_id] if source_rule_id else [],
            "source_rule_x0": span_x0,
            "source_rule_x1": span_x1,
            "previous_paragraph_index": getattr(self, "_form_line_previous", None),
            "reason": (
                "source visual form line owns a fill rule that needs independent "
                "horizontal geometry"
            ),
        }
        previous_paragraph = paragraph
        paragraph = factory(previous_paragraph, record)
        self.tab_stop_usage["source_form_line_paragraph_count"] = (
            self.tab_stop_usage.get("source_form_line_paragraph_count", 0) + 1
        )
        self._form_line_previous = record.get("generated_paragraph_index")
        self._positioned_paragraph = None
        self._positioned_paragraph_start = 0
        # A form-line paragraph is now the element's live emission context: the
        # source text that follows this row belongs after it, not back in the
        # paragraph the row was lifted out of.
        self._current_emission_paragraph = paragraph
        return paragraph

    def _render_positioned_blank(
        self,
        paragraph,
        blank,
        source,
        *,
        page_content_x0,
        page_content_x1,
        suffix_start_x=None,
    ):
        """Emit a fillable blank at its measured source span.

        The source rule's own ``x0``/``x1`` become explicit Word tab stops.  An
        anchor tab (a ``spaces`` leader, which paints nothing) carries the cursor
        to the source blank start, and a second tab - carrying an underline run
        property over a ``spaces`` leader - paints a solid rule that starts at
        ``x0`` and ends at ``x1``.  A trailing ``underscore``/``dots`` leader is
        deliberately avoided: it paints its own glyphs and would be read back as
        invented literal underscores.  The physical span is therefore controlled
        by source geometry, never by a repeated figure-space count.
        """

        blank_x0 = float(blank.source_x0)
        blank_x1 = min(float(blank.source_x1), float(page_content_x1))
        if blank_x1 <= blank_x0:
            blank_x1 = blank_x0 + 1.0
        size = max(6.0, float(getattr(source, "font_size", 0) or 10.5))
        # Only the text emitted on the *current visual line* competes for the
        # blank's position: a paragraph is reconstructed from several source
        # lines joined by line breaks, and text on an earlier line has already
        # moved the cursor down, not right.  Tab characters are cursor moves,
        # not advance width, so they are excluded from the estimate.
        paragraph_so_far = str(paragraph.text or "")
        if paragraph is not getattr(self, "_positioned_paragraph", None):
            self._positioned_paragraph = paragraph
            self._positioned_paragraph_start = len(paragraph_so_far)
        paragraph_so_far = paragraph_so_far[self._positioned_paragraph_start:]
        emitted = self._form_advance_width(
            paragraph_so_far.rsplit("\n", 1)[-1].replace("\t", ""), size
        )
        # The declared paragraph coordinate frame: the ruler a paragraph's tab
        # stops are laid out on follows the paragraph's own left indent, while the
        # text of a first line also carries its first-line indent.  For deciding
        # whether the cursor has already passed the rule, only the *current* line
        # origin matters, and a form-layout break clears the first-line indent.
        frame = paragraph_coordinate_frame(paragraph, blank_x0, blank_x1)
        margin = frame.current_line_origin_x
        tab_origin = frame.tab_stop_reference_origin_x
        # Resolve this blank's source rule identity by exact span, so the record
        # carries provenance instead of only geometry.
        source_rule_id = None
        source_rule_page = None
        matched_rule_entry = None
        for entry in getattr(self, "source_rule_registry", []):
            if (
                abs(entry["x0"] - blank_x0) <= 1.0
                and abs(entry["x1"] - blank_x1) <= 1.0
            ):
                matched_rule_entry = entry
                break
        if matched_rule_entry is not None:
            source_rule_id = matched_rule_entry["source_rule_id"]
            source_rule_page = matched_rule_entry.get("source_page")
        if source_rule_page is None and source_rule_id:
            # The frozen id model is ``P<source page>-R<index>``, so the owning
            # source page is recoverable from the id itself.
            page_match = re.match(r"^P(\d+)-R\d+$", str(source_rule_id))
            if page_match:
                source_rule_page = int(page_match.group(1))
        if source_rule_page is None:
            source_rule_page = self._active_source_page
        self._positioned_coordinate_frames.append(frame.as_dict())
        tab_stops = paragraph.paragraph_format.tab_stops
        # OWNER-DRIVEN FIXED-SLOT EXECUTION.  The renderer has just established
        # this blank's own active representation, so it is the execution owner
        # for the source form field the pre-render plan bound to this rule.  The
        # plan supplies the semantic value; the owner decides whether there is a
        # place to execute it.  Nothing here iterates document-wide plans, so a
        # plan with no active owner (a rule whose representation this renderer
        # never established) stays execution-inactive.
        owned_value = self._owner_driven_fixed_slot_value(
            paragraph, rule_entry=matched_rule_entry, source=source
        )
        if owned_value is not None:
            return owned_value

        # A positioned blank consumes its tab stops on whatever line the cursor
        # currently occupies, and the two stops advance the cursor in sequence.
        # That is only correct when the blank starts a fresh line at this
        # paragraph's own origin, where the stops are measured from.  The
        # emitter therefore always starts the blank's own form line: this is the
        # narrow SOURCE_FORM_LAYOUT_LINE remedy, limited to lines that carry a
        # real fillable field, and it uses only a Word line break.
        form_line_break = False
        reach = margin + emitted
        managed = id(paragraph) in getattr(self, "_form_line_managed_paragraphs", set())
        if not managed and (paragraph_so_far.strip("\t") or blank_x0 + 1.0 < reach):
            self._add_run(paragraph, "", source).add_break()
            self._positioned_paragraph_start = len(str(paragraph.text or ""))
            form_line_break = True
            self.tab_stop_usage["form_layout_break_count"] = (
                self.tab_stop_usage.get("form_layout_break_count", 0) + 1
            )
            self.positioned_form_layout_breaks.append(
                {
                    "source_page": getattr(
                        getattr(blank, "source_locator", None), "page", None
                    ),
                    "source_x0": round(blank_x0, 2),
                    "source_x1": round(blank_x1, 2),
                    "previous_reach_pt": round(reach, 2),
                    "overshoot_pt": round(reach - blank_x0, 2),
                    "reason": (
                        "source form line splits one visual row around a fill "
                        "rule; Word reflow carried the cursor past the rule"
                        if blank_x0 + 1.0 < reach
                        else "fill rule starts its own source form line"
                    ),
                }
            )
            emitted = 0.0
            reach = margin
        if blank_x0 + 1.0 < reach:
            self.positioned_blank_records.append(
                {
                    "semantic_slot": blank.semantic_slot,
                    "source_x0": round(blank_x0, 2),
                    "source_x1": round(blank_x1, 2),
                    "source_span_pt": round(blank_x1 - blank_x0, 2),
                    "emission_mechanism": "SOURCE_POSITIONED_UNREACHABLE",
                    "reach_pt": round(reach, 2),
                    "overshoot_pt": round(reach - blank_x0, 2),
                    "reason": "source rule lies left of the emitted flow position",
                    "source_page": getattr(
                        getattr(blank, "source_locator", None), "page", None
                    ),
                }
            )
            self.unreachable_positioned_blank_count += 1
            self._register_blank(blank, rendered_width=0.0, visible=False)
            return blank_x0

        anchored_start = blank_x0 > reach + 1.0
        paragraph_indent = self._paragraph_left_indent(paragraph)
        if anchored_start:
            anchor_stop = self._source_tab_position(blank_x0, tab_origin)
            tab_stops.add_tab_stop(
                Pt(anchor_stop),
                WD_TAB_ALIGNMENT.LEFT,
                WD_TAB_LEADER.SPACES,
            )
            self._add_run(paragraph, "\t", source)
            self.tab_stop_usage["positioned_anchor_tabs"] = (
                self.tab_stop_usage.get("positioned_anchor_tabs", 0) + 1
            )
        leader_position = self._source_tab_position(blank_x1, tab_origin)
        tab_stops.add_tab_stop(
            Pt(leader_position), WD_TAB_ALIGNMENT.LEFT, WD_TAB_LEADER.SPACES
        )
        self._add_run(paragraph, "\t", source, underline=True)
        self.tab_stop_usage["positioned_leader_tabs"] = (
            self.tab_stop_usage.get("positioned_leader_tabs", 0) + 1
        )
        if suffix_start_x is not None:
            stop = self._source_tab_position(suffix_start_x, tab_origin)
            if stop > leader_position + 0.5:
                tab_stops.add_tab_stop(Pt(stop), WD_TAB_ALIGNMENT.LEFT, WD_TAB_LEADER.SPACES)
                self._add_run(paragraph, "\t", source)
                self.tab_stop_usage["positioned_suffix_tabs"] = (
                    self.tab_stop_usage.get("positioned_suffix_tabs", 0) + 1
                )
        self._register_blank(
            blank,
            rendered_width=blank_x1 - blank_x0,
            visible=blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY,
        )
        self.positioned_blank_records.append(
            {
                "semantic_slot": blank.semantic_slot,
                "source_rule_id": source_rule_id,
                "source_page": source_rule_page,
                "source_x0": round(blank_x0, 2),
                "source_x1": round(blank_x1, 2),
                "source_span_pt": round(blank_x1 - blank_x0, 2),
                "paragraph_origin_pt": round(margin, 2),
                "section_left_margin_pt": round(
                    float(
                        paragraph.part.document.sections[-1].left_margin.pt
                    ),
                    2,
                ),
                "document_section_left_margins_pt": [
                    round(float(s.left_margin.pt), 2)
                    for s in paragraph.part.document.sections
                ],
                "paragraph_indent_pt": round(paragraph_indent, 2),
                "form_layout_line_break": form_line_break,
                "anchor_tab_position_pt": (
                    round(anchor_stop, 2) if anchored_start else None
                ),
                "leader_tab_position_pt": round(leader_position, 2),
                "representation_kind": (
                    blank.representation_kind.value
                    if hasattr(blank.representation_kind, "value")
                    else str(blank.representation_kind)
                ),
                "emission_mechanism": "SOURCE_POSITIONED_UNDERLINED_TAB",
                "anchor_tab": bool(anchored_start),
                "suffix_tab": suffix_start_x is not None,
            }
        )
        return blank_x1

    def _compiled_field_plan_records(self) -> list:
        """The compiled per-rule SourceFormPlan as serializable evidence records.

        Each compiled plan key is matched back to the registry entry it came from
        through the same plan-resolution contract rendering uses, so the QA
        artifact names the exact ``source_rule_id`` the plan was compiled for.
        """

        from tender_basic.source_form_execution import resolve_field_plan

        plans = getattr(self, "_rule_field_plans", None) or {}
        records = []
        for entry in self.source_rule_registry:
            plan = resolve_field_plan(
                plans,
                page=entry.get("source_page"),
                x0=entry.get("x0"),
                x1=entry.get("x1"),
                y=entry.get("y"),
            )
            if plan is None:
                continue
            records.append(
                {
                    "source_rule_id": entry["source_rule_id"],
                    "source_page": entry.get("source_page"),
                    "source_x0": entry.get("x0"),
                    "source_x1": entry.get("x1"),
                    "source_y": entry.get("y"),
                    "transformation_policy": (
                        plan[0] if isinstance(plan, tuple) and plan else None
                    ),
                    "planned_fact_fields": [
                        str(getattr(field, "value", field))
                        for field in (
                            plan[1] if isinstance(plan, tuple) and len(plan) > 1 else ()
                        )
                    ],
                }
            )
        records.sort(
            key=lambda record: (
                record["source_page"] or 0,
                record["source_y"] or 0.0,
                record["source_x0"] or 0.0,
            )
        )
        return records

    def _owner_driven_fixed_slot_value(self, paragraph, *, rule_entry, source):
        """Emit a resolved planned value from the owner of this form line.

        The renderer owns an active representation for this rule (it is
        emitting the rule's own form line right now), and the compiled plan may
        require a resolved value in that fixed slot.  When both hold, the value
        replaces the empty rule as the visual representation:

        * it starts at the rule's own source ``x0``;
        * it is followed by its natural glyph width, never forced to the source
          ``x1``, never padded with an invented underline and never stretched;
        * the application is recorded at this emission event.

        Returns the emitted end x when the owner executed the plan, else
        ``None`` so the caller keeps the accepted empty-slot path.  No plan is
        iterated: execution exists only because an owner was established.
        """

        from tender_basic.source_form_execution import (
            OWNER_KIND_SOURCE_FORM_LINE,
            plan_policy,
            register_source_form_execution_owner,
            record_source_fill_application,
            resolve_field_plan_for_rule,
            resolve_planned_value_execution,
        )
        if rule_entry is None:
            return None
        rule = dict(rule_entry)
        plan = resolve_field_plan_for_rule(rule, getattr(self, "_rule_field_plans", None))
        if plan is None or plan_policy(plan) != "RESOLVED_VALUE_IN_FIXED_SLOT":
            # The renderer owns a form line here, but the compiled plan does not
            # ask for a resolved value in this slot, so no execution owner is
            # established and the accepted empty-slot path is kept.
            return None
        # Execution ownership is renderer-derived: the SOURCE_FORM_LINE owner
        # exists only when this blank's paragraph is one the renderer itself
        # opened for a source visual form line (SOURCE_FORM_LINE_PARAGRAPH).  A
        # rule whose blank is painted inside an ordinary flowing paragraph has no
        # active value representation, so it stays execution-inactive.
        if not getattr(self, "_source_form_line_mode", False):
            return None
        if id(paragraph) not in getattr(self, "_form_line_managed_paragraphs", set()):
            return None
        document = paragraph.part.document
        paragraph_index = len(document.paragraphs) - 1
        register_source_form_execution_owner(
            self,
            rule=rule,
            owner_kind=OWNER_KIND_SOURCE_FORM_LINE,
            representation_type="SOURCE_FORM_LINE_PARAGRAPH",
            accepts_value_insertion=True,
            paragraph_index=paragraph_index,
            emitter_identity="SOURCE_FORM_LINE_OWNER:SOURCE_ANCHORED_VALUE_RUN",
            transformation_policy=(plan[0] if isinstance(plan, tuple) and plan else None),
            registration_reason=(
                "renderer created the source form line that owns this fill rule"
            ),
        )
        decision = resolve_planned_value_execution(self, rule, plan)
        if not decision["execute"]:
            return None
        owner = decision["owner"]
        values = decision["values"]
        fact_fields = decision["fact_fields"]
        value = values[0]
        geometry = owner.source_geometry or (
            float(rule.get("x0", 0.0)),
            float(rule.get("x1", 0.0)),
            float(rule.get("y", 0.0)),
        )
        anchor_x = float(geometry[0])
        section = paragraph.part.document.sections[-1]
        page_content_x0 = float(section.left_margin.pt or 18.0)
        page_content_x1 = float(section.page_width.pt) - float(section.right_margin.pt or 18.0)
        frame = paragraph_coordinate_frame(paragraph, anchor_x, anchor_x + 1.0)
        tab_origin = frame.tab_stop_reference_origin_x
        origin = frame.current_line_origin_x
        mechanism = "ALREADY_AT_ANCHOR"
        tab_position = None
        if anchor_x < origin - 1.0:
            formatting = paragraph.paragraph_format
            formatting.left_indent = Pt(
                float(formatting.left_indent.pt or 0.0) + (origin - anchor_x)
            )
            formatting.first_line_indent = Pt(0.0)
            origin = anchor_x
            mechanism = "LINE_ORIGIN_MOVED_TO_SOURCE_ANCHOR"
        elif anchor_x > origin + 1.0:
            tab_position = self._source_tab_position(anchor_x, tab_origin)
            paragraph.paragraph_format.tab_stops.add_tab_stop(
                Pt(tab_position), WD_TAB_ALIGNMENT.LEFT, WD_TAB_LEADER.SPACES
            )
            self._add_run(paragraph, "\t", source)
            mechanism = "SOURCE_POSITIONED_ANCHOR_TAB"
        run_index = len(paragraph.runs)
        self._add_run(paragraph, value, source, underline=True)
        applications = getattr(self, "source_fill_applications", None) or []
        record_source_fill_application(
            self,
            rule=rule,
            fact_fields=fact_fields,
            values=[value],
            application_kind="VALUE_IN_FIXED_SLOT",
            representation_type="SOURCE_ANCHORED_VALUE_RUN",
            generated_paragraph_index=paragraph_index,
            generated_run_index=run_index,
            source_slot_id=owner.source_slot_id,
            owner_kind=owner.owner_kind,
        )
        self.tab_stop_usage["owner_driven_value_emissions"] = (
            self.tab_stop_usage.get("owner_driven_value_emissions", 0) + 1
        )
        record = {
            "source_rule_id": rule.get("source_rule_id"),
            "source_page": rule.get("source_page"),
            "source_x0": round(anchor_x, 2),
            "source_x1": round(float(geometry[1]), 2),
            "source_form_field_id": owner.source_form_field_id,
            "owner_kind": owner.owner_kind,
            "representation_type": "SOURCE_ANCHORED_VALUE_RUN",
            "application_kind": "VALUE_IN_FIXED_SLOT",
            "fact_fields": list(fact_fields),
            "resolved_values": list(values),
            "generated_paragraph_index": paragraph_index,
            "generated_run_index": run_index,
            "anchor_x": round(anchor_x, 2),
            "anchor_mechanism": mechanism,
            "anchor_tab_position_pt": tab_position,
            "underline_semantics": "RESOLVED_VALUE_UNDERLINED_AT_NATURAL_WIDTH",
            "geometry_intent": "ANCHOR_START_ONLY",
            "geometry_note": (
                "value starts at the source slot anchor and follows its own "
                "natural glyph width; the source x1 is retained as provenance "
                "only and never forces the value's right edge"
            ),
            "application_id": applications[-1].application_id
            if applications
            else None,
        }
        self.source_anchored_value_runs.append(record)
        self.source_form_line_value_runs.append(record)
        return anchor_x

    def _planned_resolved_fields(self) -> list:
        """The planned resolved fields an active execution owner undertook.

        Only fields the renderer actually owns are planned: a document-wide
        semantic plan the renderer never established an active representation
        for has no execution owner and therefore no planned application, so it
        can never be reported as a missing execution.
        """

        from tender_basic.source_form_execution import (
            execution_owners,
            resolved_fact_values,
        )

        values = resolved_fact_values(self)
        planned = []
        for owner in execution_owners(self):
            if not owner.eligible_for_value_emission:
                continue
            fact_fields = [
                key
                for key in (owner.planned_fact_fields or ())
                if key and key in values
            ]
            if not fact_fields:
                # An owner that carries no resolved planned fact executes
                # nothing, so it is planned with empty coverage.
                fact_fields = []
            planned.append(
                {
                    "field_id": owner.source_form_field_id,
                    "fact_fields": fact_fields,
                    "values": [values[key] for key in fact_fields],
                    "declared_fact_fields": list(owner.planned_fact_fields or ()),
                    "owner_kind": owner.owner_kind,
                    "representation_type": owner.representation_type,
                }
            )
        return planned

    def _extend_anchored_application(
        self, paragraph_index, anchor_rule, fact_fields, matched_values
    ):
        """Fold a second composite slot write into the anchored application.

        One logical write event can cover two source facts: the anchored
        representation owns the paragraph, and the adjacent source slot writes
        the other half of the same composite placeholder.  The application keeps
        its identity and gains the second fact/value pair, so its coverage is the
        real composite rather than a projected single field.
        """

        from tender_basic.source_form_execution import (
            execution_owners,
            record_source_fill_application,
            stable_field_id,
        )

        field_id = stable_field_id(
            source_page=anchor_rule.get("source_page"),
            source_rule_ids=[anchor_rule["source_rule_id"]]
            if anchor_rule.get("source_rule_id")
            else (),
            geometry=(
                float(anchor_rule.get("x0", 0.0)),
                float(anchor_rule.get("x1", 0.0)),
                float(anchor_rule.get("y", 0.0)),
            ),
        )
        owner = next(
            (
                item
                for item in execution_owners(self)
                if item.source_form_field_id == field_id
            ),
            None,
        )
        applications = getattr(self, "source_fill_applications", None) or []
        existing = next(
            (
                application
                for application in applications
                if application.generated_paragraph_index == paragraph_index
                and application.source_form_field_id == field_id
            ),
            None,
        )
        if existing is None:
            return record_source_fill_application(
                self,
                rule=anchor_rule,
                fact_fields=fact_fields,
                values=matched_values,
                application_kind="PLACEHOLDER_REPLACEMENT",
                representation_type="SOURCE_ANCHORED_VALUE_RUN",
                generated_paragraph_index=paragraph_index,
                source_slot_id=getattr(owner, "source_slot_id", None),
                owner_kind=getattr(owner, "owner_kind", None),
            )
        facts = list(existing.fact_fields)
        values = list(existing.resolved_values)
        for key, value in zip(fact_fields, matched_values):
            if key in facts:
                continue
            facts.append(key)
            values.append(value)
        existing.fact_fields = tuple(facts)
        existing.resolved_values = tuple(values)
        if owner is not None:
            merged = list(owner.planned_fact_fields or ())
            for key in facts:
                if key not in merged:
                    merged.append(key)
            owner.planned_fact_fields = tuple(merged)
        return existing

    def _record_legacy_slot_write(self, paragraph, slot, value, *, generated_run_index=None):
        """Record the write an actively owning legacy source fill slot performs.

        The slot is the active representation for this source form field, so the
        renderer registers it as the execution owner and records the application
        at the real write event.  Which facts the write actually carries is
        decided by the emitted characters against the slot's own canonical fact
        bridge, so a composite placeholder records both of its facts and a
        non-resolved component is never counted as written.
        """

        from tender_basic.source_form_execution import (
            OWNER_KIND_LEGACY_SLOT,
            canonical_fact_fields_for_slot,
            execution_owners,
            facts_actually_written,
            record_source_fill_application,
            register_source_form_execution_owner,
            resolved_fact_values,
        )

        candidates = canonical_fact_fields_for_slot(slot)
        values = resolved_fact_values(self)
        available = [type("F", (), {"name": key, "resolved_value": values[key]}) for key in candidates if key in values]
        fact_fields, matched_values = facts_actually_written(value, available)
        if not fact_fields:
            return None
        paragraph_index = len(paragraph.part.document.paragraphs) - 1
        # A composite source placeholder can be filled by two adjacent slots in
        # one paragraph.  The anchored representation that already owns this
        # paragraph is the logical write event, so this slot's fact/value pair is
        # folded into that one application instead of becoming a second, separate
        # field record.
        anchor_rule = self._anchored_paragraph_rules.get(paragraph_index)
        if anchor_rule is not None:
            return self._extend_anchored_application(
                paragraph_index, anchor_rule, fact_fields, matched_values
            )
        # A value write the anchored representation already owns is not a second
        # write event: the anchored run established the active representation and
        # recorded the application at its own emission, so the same value is
        # never written into the provenance twice.
        if any(
            set(owner.planned_fact_fields) & set(candidates)
            for owner in execution_owners(self)
            if owner.eligible_for_value_emission
        ):
            return None
        rule = {
            "source_rule_id": getattr(slot, "source_rule_id", None),
            "source_page": getattr(slot, "source_page", None),
            "x0": 0.0,
            "x1": 0.0,
            "y": 0.0,
        }
        geometry = getattr(slot, "geometry", None)
        if geometry and len(geometry) == 4:
            rule.update(
                {
                    "x0": float(geometry[0]),
                    "x1": float(geometry[2]),
                    "y": float(geometry[1]),
                }
            )
        register_source_form_execution_owner(
            self,
            rule=rule,
            owner_kind=OWNER_KIND_LEGACY_SLOT,
            representation_type="SOURCE_FILL_SLOT",
            accepts_value_insertion=True,
            source_slot_id=getattr(slot, "slot_id", None),
            paragraph_index=paragraph_index,
            emitter_identity="LEGACY_SLOT_OWNER:SOURCE_FILL_SLOT",
            planned_fact_fields=fact_fields,
            registration_reason=(
                "legacy source fill slot actively owns this value write"
            ),
        )
        application = record_source_fill_application(
            self,
            rule=rule,
            fact_fields=fact_fields,
            values=matched_values,
            application_kind="PLACEHOLDER_REPLACEMENT",
            representation_type="SOURCE_FILL_SLOT",
            generated_paragraph_index=paragraph_index,
            generated_run_index=generated_run_index,
            source_slot_id=getattr(slot, "slot_id", None),
            owner_kind=OWNER_KIND_LEGACY_SLOT,
        )
        self.filled_value_writes.append(
            {
                "application_id": application.application_id,
                "paragraph_index": paragraph_index,
                "slot_id": getattr(slot, "slot_id", None),
                "slot_type": getattr(slot, "slot_type", None),
                "fact_fields": list(fact_fields),
                "values": list(matched_values),
            }
        )
        return application

    def _merge_adjacent_logical_applications(self):
        """One logical application per adjacent composite write.

        A source composite placeholder filled by two adjacent slots is a single
        logical write event, so its applications are one record covering both
        fact/value pairs instead of two records that each look like a complete
        standalone field.  Merging is by adjacency in the emitted paragraph and
        by the fact sets being disjoint, never by scanning the final text.
        """

        applications = getattr(self, "source_fill_applications", None)
        writes = getattr(self, "filled_value_writes", None)
        if not applications or not writes:
            return
        merged = []
        index = 0
        while index < len(writes):
            head = writes[index]
            group = [head]
            cursor = index + 1
            while cursor < len(writes):
                nxt = writes[cursor]
                if nxt.get("paragraph_index") != head.get("paragraph_index"):
                    break
                head_facts = {item for entry in group for item in entry["fact_fields"]}
                if head_facts & set(nxt["fact_fields"]):
                    break
                group.append(nxt)
                cursor += 1
            if len(group) > 1:
                ids = [entry["application_id"] for entry in group]
                primary = next(
                    (app for app in applications if app.application_id == ids[0]),
                    None,
                )
                if primary is not None:
                    facts: list[str] = []
                    values: list[str] = []
                    for entry in group:
                        for key, value in zip(entry["fact_fields"], entry["values"]):
                            if key in facts:
                                continue
                            facts.append(key)
                            values.append(value)
                    primary.fact_fields = tuple(facts)
                    primary.resolved_values = tuple(values)
                    primary.source_slot_id = primary.source_slot_id or group[0].get(
                        "slot_id"
                    )
                    merged.append(
                        {
                            "logical_application_id": primary.application_id,
                            "child_application_ids": ids,
                            "paragraph_index": head.get("paragraph_index"),
                            "fact_fields": list(facts),
                            "values": list(values),
                            "reason": (
                                "adjacent source composite slots filled in one "
                                "paragraph are one logical write event"
                            ),
                        }
                    )
                    for entry in group[1:]:
                        record = next(
                            (
                                app
                                for app in applications
                                if app.application_id == entry["application_id"]
                            ),
                            None,
                        )
                        if record is not None:
                            applications.remove(record)
            index = cursor if cursor > index else index + 1
        self.logical_application_merges = merged

    def _inline_blank_run(
        self,
        paragraph,
        width_pt,
        source=None,
        *,
        semantic_slot=None,
        source_locator=None,
        source_span=None,
        page_content_x0=18.0,
        page_content_x1=None,
        suffix_start_x=None,
    ):
        if source_span is not None:
            blank = EditableBlank(
                kind=EditableBlankKind.INLINE_BLANK,
                source_x0=float(source_span[0]),
                source_x1=float(source_span[1]),
                width_pt=max(1.0, float(source_span[1]) - float(source_span[0])),
                semantic_slot=semantic_slot,
                render_style=EditableBlankRenderStyle.UNDERLINED_INLINE,
                source_locator=source_locator,
            )
            self._render_positioned_blank(
                paragraph,
                blank,
                source,
                page_content_x0=page_content_x0,
                page_content_x1=(
                    float(page_content_x1) if page_content_x1 is not None else float(source_span[1]) + 1.0
                ),
                suffix_start_x=suffix_start_x,
            )
            self.inline_blank_count += 1
            return
        size=max(6.0, float(getattr(source,'font_size',0) or 10.5))
        count=max(2, int(round(float(width_pt)/(size*.55))))
        # FIGURE SPACE is a Word-visible underlined glyph, unlike a trailing
        # ordinary-space run, and is deliberately not an NBSP placeholder.
        self._add_run(paragraph, '\u2007'*count, source, underline=True)
        blank=EditableBlank(
            kind=EditableBlankKind.INLINE_BLANK,
            source_x0=0.0,
            source_x1=float(width_pt),
            width_pt=float(width_pt),
            semantic_slot=semantic_slot,
            render_style=EditableBlankRenderStyle.UNDERLINED_INLINE,
            source_locator=source_locator,
        )
        self._register_blank(blank, rendered_width=float(width_pt), visible=True)
        self.inline_blank_count += 1

    def _render_rule_composition(self, paragraph, source_rule_id, segments,
                                 evidence=None):
        """Emit one SOURCE_RULE_COMPOSITION: empty segments plus its own text.

        The rule-bearing union is the source rule extent.  Empty segments use
        the proven source-positioned underlined tab, so the physical width
        authority is the source ``x0``/``x1`` and never a glyph count.
        """

        section = paragraph.part.document.sections[-1]
        page_content_x0 = float(section.left_margin.pt or 18.0)
        page_content_x1 = float(section.page_width.pt) - float(section.right_margin.pt or 18.0)
        frame = paragraph_coordinate_frame(
            paragraph, segments[0]["source_x0"], segments[-1]["source_x1"]
        )
        tab_origin = frame.tab_stop_reference_origin_x
        stops = paragraph.paragraph_format.tab_stops
        emitted = []
        first = True
        for segment in segments:
            x0, x1 = float(segment["source_x0"]), float(segment["source_x1"])
            anchor = self._source_tab_position(x0, tab_origin)
            leader = self._source_tab_position(x1, tab_origin)
            if anchor > page_content_x1 - page_content_x0:
                continue
            stops.add_tab_stop(Pt(anchor), WD_TAB_ALIGNMENT.LEFT, WD_TAB_LEADER.SPACES)
            if first and segment.get("needs_anchor"):
                # Reach the anchor without painting a leader behind it.
                self._add_run(paragraph, "\t", None)
            first = False
            if segment["segment_type"] == "EMPTY_RULE_SEGMENT":
                stops.add_tab_stop(Pt(leader), WD_TAB_ALIGNMENT.LEFT, WD_TAB_LEADER.SPACES)
                self._add_run(paragraph, "\t", None, underline=True)
                emitted.append(
                    {
                        "composition_segment_id": segment["composition_segment_id"],
                        "segment_type": "EMPTY_RULE_SEGMENT",
                        "source_x0": round(x0, 2),
                        "source_x1": round(x1, 2),
                        "source_text": None,
                        "generated_text": "",
                        "emission_mechanism": "SOURCE_POSITIONED_UNDERLINED_TAB",
                        "source_rule_id": source_rule_id,
                        "anchor_tab_position_pt": round(anchor, 2),
                        "leader_tab_position_pt": round(leader, 2),
                    }
                )
            else:
                self._add_run(paragraph, segment["source_text"] or "", None, underline=True)
                # Execution provenance for a plan-driven resolved fixed-slot
                # value, recorded at this emission event: the plan said the field
                # is populated and this is the run that actually carries it.
                from tender_basic.source_form_execution import (
                    record_source_fill_application,
                    resolve_field_plan as _resolve_plan,
                )

                _entry = next(
                    (
                        item
                        for item in getattr(self, "source_rule_registry", [])
                        if item.get("source_rule_id") == source_rule_id
                    ),
                    None,
                )
                _plan = (
                    _resolve_plan(
                        getattr(self, "_rule_field_plans", None),
                        page=_entry.get("source_page"),
                        x0=_entry.get("x0", 0.0),
                        x1=_entry.get("x1", 0.0),
                        y=_entry.get("y", 0.0),
                    )
                    if _entry
                    else None
                )
                if (
                    isinstance(_plan, tuple)
                    and _plan
                    and _plan[0] == "RESOLVED_VALUE_IN_FIXED_SLOT"
                ):
                    record_source_fill_application(
                        self,
                        rule=_entry,
                        fact_fields=[
                            str(getattr(item, "name", item))
                            for item in (_plan[1] or ())
                        ],
                        values=[segment["source_text"] or ""],
                        application_kind="VALUE_IN_FIXED_SLOT",
                        representation_type="SOURCE_RULE_COMPOSITION",
                        generated_paragraph_index=(
                            len(paragraph.part.document.paragraphs) - 1
                        ),
                    )
                emitted.append(
                    {
                        "composition_segment_id": segment["composition_segment_id"],
                        "segment_type": "TEXT_RULE_SEGMENT",
                        "source_x0": round(x0, 2),
                        "source_x1": round(x1, 2),
                        "source_text": segment["source_text"],
                        "generated_text": segment["source_text"] or "",
                        "emission_mechanism": "SOURCE_UNDERLINED_VALUE_RUN",
                        "source_rule_id": source_rule_id,
                        "anchor_tab_position_pt": round(anchor, 2),
                        "leader_tab_position_pt": round(leader, 2),
                    }
                )
        record = {
            "source_rule_id": source_rule_id,
            "source_visual_line_id": self._rule_source_visual_line.get(source_rule_id),
            "geometry_policy": "EXACT_SOURCE_SPAN",
            "representation_type": "SOURCE_RULE_COMPOSITION",
            "logical_rule_emission_count": 1,
            "segments": emitted,
            "segment_count": len(emitted),
            "composition_segment_emission_count": len(emitted),
            "paragraph_index": len(paragraph.part.document.paragraphs) - 1,
            "paragraph_coordinate_frame": frame.as_dict(),
            **(evidence or {}),
        }
        self.source_rule_compositions.append(record)
        return record

    def _render_inline_tokens(self, paragraph, text, runs, slots, *, flow=False):
        """Emit the inline representations of one source visual line.

        SOURCE-LINE ORDER: the representation the source places *first* is
        emitted first.  Every positioned atom of a source visual line is cut
        into this text at its own source position, so dispatching on the earliest
        token is what keeps the generated row monotonic in source x.  Handling a
        later-x atom first would emit it into a paragraph context an earlier
        positioned atom can no longer reach, which is exactly the row-parity
        defect this ordering removes.
        """

        blank = _INLINE_BLANK_PATTERN.search(text)
        composition = _INLINE_COMPOSITION_PATTERN.search(text)
        if composition is not None and (
            blank is None or composition.start() < blank.start()
        ):
            return self._render_composition_atom(
                paragraph, text, composition, runs, slots, flow=flow
            )
        if blank is None:
            return False
        return self._render_blank_atom(
            paragraph, text, blank, runs, slots, flow=flow
        )

    def _render_composition_atom(
        self, paragraph, text, composition, runs, slots, *, flow=False
    ):
        before = text[:composition.start()]
        after = text[composition.end():]
        before_slots, after_slots = [], []
        for slot in slots:
            if slot.text_start is None or slot.text_end is None:
                continue
            if slot.text_end <= composition.start():
                before_slots.append(slot)
            elif slot.text_start >= composition.end():
                after_slots.append(slot.model_copy(update={
                    'text_start': slot.text_start - composition.end(),
                    'text_end': slot.text_end - composition.end(),
                }))
        if before:
            self.text(paragraph, before, runs, before_slots, flow=flow)
        parsed = parse_inline_rule_composition_token(composition.group(1))
        source = next((run for run in runs if run.text.strip()), None)
        # SOURCE_RULE_COMPOSITION owns the paragraph its token lands in: a form
        # line promoted for this rule is that paragraph, and its trailing source
        # text belongs in the composition's own paragraph rather than wherever
        # the element's emission cursor happened to point before the rule was
        # rendered.  Sending the tail elsewhere splits one source visual line
        # across two paragraphs and re-orders it against the composition.
        composed_paragraph = paragraph
        if parsed is not None:
            source_rule_id, segments, evidence = parsed
            # SOURCE_FORM_LINE_PARAGRAPH: a composed rule whose first segment is
            # an empty rule segment must paint from its own source anchor.
            # Continuous text flow may already have carried the cursor past that
            # anchor and a tab cannot move backwards, so the composed line is
            # given its own paragraph coordinate context and is then positioned
            # absolutely from the rule's own anchor.  A row the assembler already
            # gave a paragraph context keeps it: it is the same one context.
            promoted = False
            if (
                getattr(self, "_source_form_line_mode", False)
                and getattr(self, "_form_line_paragraph_factory", None) is not None
                and segments
                and segments[0]["segment_type"] == "EMPTY_RULE_SEGMENT"
                and not getattr(self, "_form_line_composition_split", False)
                and paragraph is not getattr(self, "_row_context_paragraph", None)
            ):
                paragraph = self._start_source_form_line_paragraph(
                    paragraph, source,
                    span=(segments[0]["source_x0"], segments[-1]["source_x1"]),
                )
                self._form_line_managed_paragraphs.add(id(paragraph))
                self._form_line_has_content = True
                self._form_line_composition_split = True
                # Other rules on this same source visual line belong to
                # the line this composition just isolated, so they stay in it
                # instead of opening yet another paragraph.
                self._form_line_split_line_y = self._rule_line_y(
                    segments[0]["source_x0"], segments[-1]["source_x1"]
                )
                self._register_form_line_source_row(self._form_line_split_line_y)
                promoted = True
            composed_paragraph = paragraph
            if segments and segments[0]["segment_type"] == "EMPTY_RULE_SEGMENT":
                # The rule's own start is authoritative whichever paragraph the
                # rule lands in, so the anchor is reached with a tab whenever the
                # cursor may still be behind it.  A backwards anchor is never
                # emitted: the estimate below is a conservative lower bound on
                # the cursor, and a rule whose anchor is already behind it is
                # handled by the paragraph context instead.
                segments[0]["needs_anchor"] = promoted or self._anchor_ahead(
                    paragraph,
                    segments[0]["source_x0"],
                    segments[-1]["source_x1"],
                    max(6.0, float(getattr(source, "font_size", 0) or 10.5)),
                )
            self._render_rule_composition(
                paragraph, source_rule_id, segments, evidence
            )
        if after:
            self.text(composed_paragraph, after, runs, after_slots, flow=flow)
        return True

    def _render_blank_atom(self, paragraph, text, match, runs, slots, *, flow=False):
        before,after=text[:match.start()],text[match.end():]
        before_slots=[]
        after_slots=[]
        for slot in slots:
            start,end=slot.text_start,slot.text_end
            if start is None or end is None:
                continue
            if end <= match.start():
                before_slots.append(slot)
            elif start >= match.end():
                after_slots.append(slot.model_copy(update={'text_start':start-match.end(),'text_end':end-match.end()}))
        if before:
            self.text(paragraph,before,runs,before_slots,flow=flow)
        source=next((run for run in runs if run.text.strip()),None)
        parsed = parse_inline_blank_token(match.group(1))
        width, span_x0, span_x1 = parsed if parsed else (1.0, 0.0, 1.0)
        # SOURCE_FORM_LINE_PARAGRAPH: a source visual form line that owns its own
        # rule gets an independent Word paragraph, so it cannot inherit the
        # previous form line's tab stops or indents.  Only the dedicated
        # form-line path does this; everything else keeps one flowing paragraph.
        # A row the assembler already opened a paragraph for keeps that context.
        if getattr(self, "_source_form_line_mode", False) and getattr(
            self, "_form_line_paragraph_factory", None
        ) is not None:
            if (
                paragraph is not getattr(self, "_row_context_paragraph", None)
                and self._form_line_has_content
                and not self._same_split_line(span_x0, span_x1)
                and not self._same_source_line_rule(span_x0, span_x1)
            ):
                paragraph = self._start_source_form_line_paragraph(
                    paragraph, source, span=(span_x0, span_x1)
                )
                self._register_form_line_source_row(
                    self._rule_line_y(span_x0, span_x1)
                )
            else:
                self._form_line_has_content = True
                self._form_line_previous = getattr(self, "_form_line_previous", None)
            self._form_line_managed_paragraphs.add(id(paragraph))
        # The blank's own source span is authoritative: it becomes the Word tab
        # stops, so the painted rule lands exactly where the source draws it.
        section = paragraph.part.document.sections[-1]
        page_content_x0 = float(section.left_margin.pt or 18.0)
        page_content_x1 = float(section.page_width.pt) - float(section.right_margin.pt or 18.0)
        self._inline_blank_run(
            paragraph,
            width,
            source,
            source_span=(span_x0, span_x1),
            page_content_x0=page_content_x0,
            page_content_x1=page_content_x1,
        )
        if after:
            self.text(
                self._current_emission_paragraph or paragraph,
                after,runs,after_slots,flow=flow,
            )
        return True

    def _anchor_ahead(self, paragraph, source_x0, source_x1, size):
        """Whether a positioned rule's start is still ahead of the cursor.

        The estimate is the same source-derived one the positioned blank path
        uses: the modelled advance width of the text already emitted on this
        paragraph's line, measured from the paragraph's own tab-stop reference
        origin.  It only ever authorises an *anchor* tab, and a rule whose anchor
        is already behind the cursor is left to the paragraph context instead, so
        no backwards tab is ever emitted.
        """

        try:
            frame = paragraph_coordinate_frame(
                paragraph, float(source_x0), float(source_x1)
            )
            emitted = self._form_advance_width(
                str(paragraph.text or "").rsplit("\n", 1)[-1].replace("\t", ""),
                max(6.0, float(size or 10.5)),
            )
        except Exception:  # pragma: no cover - defensive geometry boundary
            return False
        return float(source_x0) > frame.current_line_origin_x + emitted + 1.0

    def _anchored_value_rule(self, slot, runs):
        """The source rule whose field a resolved value replaces.

        Evidence: the source drew a field rule under its own placeholder text.
        The rule that belongs to this fragment's own source visual line is that
        field, and its start is the anchor.  A line carrying more than one
        underline rule is ambiguous and is left alone.  Nothing here is keyed to
        a page, rule id or literal text.
        """

        bands = [
            (float(run.bbox[1]), float(run.bbox[3]))
            for run in runs
            if getattr(run, "text", "").strip() and getattr(run, "bbox", None)
        ]
        if not bands:
            return None
        band_y0 = min(band[0] for band in bands)
        band_y1 = max(band[1] for band in bands)
        candidates = [
            entry
            for entry in getattr(self, "source_rule_registry", [])
            if entry.get("source_page") == self._active_source_page
            and "UNDERLINE" in str(entry.get("relation_type", ""))
            and band_y0 - 1.5 <= entry["y"] <= band_y1 + 2.5
        ]
        return candidates[0] if len(candidates) == 1 else None

    def _apply_source_value_anchor(self, paragraph, slot, rule, value):
        """Place the resolved value at its source anchor and record provenance.

        The value itself is the representation, so its measured bbox start is
        what gets gated.  Only the established coordinate model is used: the
        paragraph line origin, or a positioned tab measured from the section
        text margin.  No repeated spaces, no textbox, no fixed-width blank.
        """

        section = paragraph.part.document.sections[-1]
        page_content_x0 = float(section.left_margin.pt or 18.0)
        formatting = paragraph.paragraph_format
        left_indent = float(formatting.left_indent.pt or 0.0)
        first_line = float(formatting.first_line_indent.pt or 0.0)
        hanging = min(0.0, first_line)
        origin = page_content_x0 + left_indent + first_line
        tab_origin = page_content_x0 + left_indent + hanging
        anchor_x = float(rule["x0"])
        mechanism = "ALREADY_AT_ANCHOR"
        tab_position = None
        if anchor_x < origin - 1.0:
            # The source field starts left of the placeholder's own text, so the
            # line origin moves to the field anchor.  A tab cannot move left.
            formatting.left_indent = Pt(max(0.0, anchor_x - page_content_x0))
            formatting.first_line_indent = Pt(0)
            mechanism = "LINE_ORIGIN_MOVED_TO_SOURCE_ANCHOR"
        elif anchor_x > origin + 1.0:
            tab_position = self._source_tab_position(anchor_x, tab_origin)
            formatting.tab_stops.add_tab_stop(
                Pt(tab_position), WD_TAB_ALIGNMENT.LEFT, WD_TAB_LEADER.SPACES
            )
            self._add_run(paragraph, "\t", slot.destination_style)
            mechanism = "SOURCE_POSITIONED_ANCHOR_TAB"
        document = paragraph.part.document
        record = {
            "source_rule_id": rule["source_rule_id"],
            "source_visual_line_id": self._rule_source_visual_line.get(
                rule["source_rule_id"]
            ),
            "fact_fields": list(slot.fact_fields)
            if getattr(slot, "fact_fields", None)
            else [slot.slot_type],
            "resolved_values": [value],
            "generated_text": value,
            "source_anchor_x": round(anchor_x, 2),
            "generated_value_start_x": None,
            "generated_value_end_x": None,
            "paragraph_index": len(document.paragraphs) - 1,
            "underline_semantics": "VALUE_SUPPLIES_CONTENT_ONLY",
            "source_placeholder_underlined": True,
            "resolved_value_underlined": False,
            "source_local_pattern": (
                "source field rule under its own placeholder text; the delivered "
                "value replaces that placeholder at the field's start anchor and "
                "follows natural glyph width"
            ),
            "evidence_reason": (
                "the source rule extent is occupied by the placeholder glyphs, so "
                "the rule belongs to the placeholder text; the frozen fill pattern "
                "makes the delivered value supply content only, so no underline is "
                "invented for it and none is required to satisfy this geometry"
            ),
            "anchor_x": round(anchor_x, 2),
            "anchor_mechanism": mechanism,
            "anchor_tab_position_pt": tab_position,
            "paragraph_left_indent_pt": round(
                float(formatting.left_indent.pt or 0.0), 2
            ),
            "paragraph_first_line_indent_pt": round(
                float(formatting.first_line_indent.pt or 0.0), 2
            ),
            "paragraph_coordinate_frame": paragraph_coordinate_frame(
                paragraph, anchor_x, anchor_x + 1.0
            ).as_dict(),
        }
        self.source_anchored_value_runs.append(record)
        # This paragraph's logical write event is owned by this anchored rule, so
        # an adjacent composite slot write that lands in the same paragraph folds
        # into the same application instead of becoming a second field record.
        self._anchored_paragraph_rules.setdefault(record.get("paragraph_index"), rule)
        # Execution provenance: recorded at the emission event itself, strictly
        # downstream of the pre-render plan.  It never drives what is rendered.
        # The anchored run is the active representation, so the renderer is the
        # execution owner of this source form field and the legacy slot identity
        # is bridged to canonical ProjectFacts fact names.
        from tender_basic.source_form_execution import (
            OWNER_KIND_ANCHORED_VALUE,
            canonical_fact_fields_for_slot,
            record_source_fill_application,
            register_source_form_execution_owner,
        )

        canonical_facts = canonical_fact_fields_for_slot(slot)
        register_source_form_execution_owner(
            self,
            rule=rule,
            owner_kind=OWNER_KIND_ANCHORED_VALUE,
            representation_type="SOURCE_ANCHORED_VALUE_RUN",
            accepts_value_insertion=True,
            source_slot_id=getattr(slot, "slot_id", None),
            paragraph_index=record["paragraph_index"],
            emitter_identity="ANCHORED_VALUE_OWNER:SOURCE_ANCHORED_VALUE_RUN",
            planned_fact_fields=canonical_facts,
            registration_reason=(
                "anchored renderer established the value run at the source anchor"
            ),
        )
        record_source_fill_application(
            self,
            rule=rule,
            fact_fields=canonical_facts,
            values=[value],
            application_kind="PLACEHOLDER_REPLACEMENT",
            representation_type="SOURCE_ANCHORED_VALUE_RUN",
            generated_paragraph_index=record["paragraph_index"],
            source_slot_id=getattr(slot, "slot_id", None),
            owner_kind=OWNER_KIND_ANCHORED_VALUE,
        )
        return record

    def text(self, paragraph, text, runs, slots, *, flow=False):
        if self._render_inline_tokens(paragraph,text,runs,slots,flow=flow):
            return
        # Match spans against the authoritative source text; retain every
        # character, including gaps/newlines not represented by PDF spans.
        visible_runs=[r for r in runs if r.text.strip()]
        styles = [visible_runs[0] if visible_runs else None] * len(text)
        cursor = 0
        for run in runs:
            at = text.find(run.text, cursor) if run.text else -1
            if at >= 0:
                styles[at:at+len(run.text)] = [run] * len(run.text)
                cursor = at + len(run.text)
        # Normalization can collapse PDF spacing. Match visible characters
        # back to span styling without rewriting any fact/container text.
        positions=[i for i,c in enumerate(text) if not c.isspace()]
        compact_text=''.join(text[i] for i in positions)
        cursor=0
        for run in visible_runs:
            key=''.join(run.text.split())
            at=compact_text.find(key,cursor)
            if at>=0:
                for i in positions[at:at+len(key)]: styles[i]=run
                cursor=at+len(key)
        replacements = []
        for slot in slots:
            replacement = slot_replacement(slot, self.facts)
            if replacement is None:
                continue
            start, end = slot.text_start, slot.text_end
            if slot.match_kind == 'table_blank' and not text.strip():
                start, end = 0, len(text)
            if start is None or end is None or not 0 <= start <= end <= len(text):
                continue
            if text[start:end] != slot.original_text and slot.match_kind != 'table_blank':
                # Slot offsets must refer to the same source container.
                continue
            if slot.slot_type == 'PROJECT_AND_LOT_SLOT':
                suffix = text[end:]
                token = re.match(r'([A-Za-z0-9][A-Za-z0-9._-]{3,})(?=(?:询比|招标|采购)文件)', suffix)
                incompatible = []
                for field_name in ('project_number', 'tender_number'):
                    fact = getattr(self.facts.fields, field_name)
                    if getattr(fact, 'status', None).value == 'RESOLVED' and fact.resolved_value is not None:
                        incompatible.append(str(fact.resolved_value))
                if token and token.group(1) in incompatible:
                    end += len(token.group(1))
                    self.semantic_slot_corrections.append({
                        'slot_id': slot.slot_id,
                        'removed_incompatible_value': token.group(1),
                        'reason': 'identifier in PROJECT_AND_LOT_SLOT',
                    })
            replacements.append((start, end, replacement, slot))
        unresolved = [
            slot for slot in slots
            if slot.match_kind == 'underline'
            and slot_replacement(slot,self.facts) is None
            and slot.text_start is not None and slot.text_end is not None
        ]
        cursor, emitted = 0, ''
        def original(start, end):
            pending=[slot for slot in unresolved if start <= slot.text_start < slot.text_end <= end]
            position=start
            for slot in pending:
                if slot.text_start > position:
                    emit_source(position,slot.text_start)
                geometry=slot.geometry or (0.0,0.0,float(len(slot.original_text))*10.5,0.0)
                self._inline_blank_run(
                    paragraph,
                    max(1.0,geometry[2]-geometry[0]),
                    styles[slot.text_start] if slot.text_start < len(styles) else None,
                    semantic_slot=slot.slot_id,
                    source_locator=slot.source_locator,
                )
                position=slot.text_end
            if position < end:
                emit_source(position,end)
        def emit_source(start,end):
            while start < end:
                stop = start + 1
                while stop < end and styles[stop] is styles[start]:
                    stop += 1
                segment = text[start:stop]
                if segment:
                    self._add_run(paragraph, join_visual_lines(segment) if flow else segment, styles[start])
                start = stop
        for start, end, (value, method), slot in sorted(replacements, key=lambda x: x[:2]):
            if start < cursor:
                continue
            original(cursor, start)
            # Round 5.6 SOURCE_FILL_PATTERN: the value supplies content only.
            # The source's own field presentation decides whether the filled
            # value keeps a visible line, and whether the source placeholder
            # (for example the bracketed project/lot pair) survives the fill.
            fill_pattern = self._fill_pattern_for(slot)
            keep_underline = bool(slot.destination_style.underline) or bool(
                getattr(fill_pattern, "value_is_underlined", False)
            )
            self.fill_pattern_usage['filled_slots'] += 1
            if fill_pattern is not None:
                self.fill_pattern_usage['pattern_matched'] += 1
            self.fill_pattern_usage[
                'value_kept_source_underline' if keep_underline else 'value_plain_whitespace'
            ] += 1
            # SOURCE_ANCHORED_VALUE_RUN: a placeholder replaced by a resolved
            # value is positioned at its source field anchor, so the delivered
            # value itself is the representation that gets measured.
            anchor_rule = self._anchored_value_rule(slot, runs)
            if anchor_rule is not None and anchor_rule["source_rule_id"] not in getattr(
                self, "_anchored_rule_applied", set()
            ):
                self._anchored_rule_applied.add(anchor_rule["source_rule_id"])
                self._apply_source_value_anchor(paragraph, slot, anchor_rule, value)
            value_run=self._add_run(paragraph, value, slot.destination_style, keep_underline)
            self._record_legacy_slot_write(
                paragraph, slot, value, generated_run_index=len(paragraph.runs) - 1
            )
            emitted += text[cursor:start] + value
            cursor = end
            self._record_fill(slot, value, method, value_run, paragraph)
        original(cursor, len(text))
        expected = emitted + text[cursor:]
        self.expected.append(join_visual_lines(expected) if flow else expected)

    def table(self, doc, source, usable, *, page_content_x0=None):
        rows, cols = len(source.rows), source.columns
        if rows < 1 or cols < 1:
            raise ValueError('Source table must have rows and columns')
        table = doc.add_table(rows, cols)
        table.style = 'Table Grid'
        table.autofit = False
        # A left-aligned Word table is positioned by its own ``w:tblInd``
        # measured from the section text margin to the table's leading edge.
        # The source table's outer geometry - not the page's text extents - is
        # the authority: a source table that starts left of the source text
        # body gets a negative indent, and the table object is never shifted
        # sideways to make it fit.
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        if page_content_x0 is None:
            page_content_x0 = float(getattr(doc.sections[-1], "left_margin").pt or 18.0)
        left_margin = float(page_content_x0)
        preferred = max(1.0, float(source.bbox[2]) - float(source.bbox[0]))
        # A zero default cell margin makes the source table edge the measured
        # edge: with the table cell margin left at Word's built-in 108 dxa the
        # painted outer border lands 5.7 pt left of where the table is placed,
        # which is exactly the systematic offset that made every table object
        # look shifted.  Zeroing it removes the offset instead of compensating
        # for it with a guessed indent.
        column_margin_pt = 0.0
        set_table_cell_margins(table, left_pt=column_margin_pt, right_pt=column_margin_pt)
        target_total = min(preferred, max(36.0, float(usable) - 0.0))
        # ``w:tblInd`` is measured from the section text margin to the leading
        # edge of the table.  The source table's own left edge is the anchor.
        set_table_width(table, target_total)
        set_table_indent(table, float(source.bbox[0]) - left_margin)
        widths = source.column_widths
        if len(widths) != cols or any(w <= 0 for w in widths):
            widths = [1] * cols
        weight = float(sum(widths))
        # Keep the source column proportions exactly: every grid column keeps
        # its source share of the table's preferred width.
        column_pt = [target_total * float(width) / weight for width in widths]
        for c, width in enumerate(column_pt):
            value = Pt(width)
            table.columns[c].width = value
            for row in table.rows:
                row.cells[c].width = value
        occupied = set()
        merges = []
        cell_map = {(c.row_index, c.column_index): c for r in source.rows for c in r.cells}
        for r0, r1, c0, c1 in source.merged_cells:
            region = {(r, c) for r in range(r0, r1+1) for c in range(c0, c1+1)}
            anchor = cell_map.get((r0,c0))
            subordinate_slots = any(s.container_type == 'table_cell' and s.source_page == source.page
                and s.table_index == source.table_index and (s.row_index,s.column_index) in region - {(r0,c0)}
                for s in self.template.fill_slots)
            def duplicate_or_empty(key):
                cell = cell_map.get(key)
                return cell is None or not cell.text.strip() or (
                    anchor is not None and anchor.bbox is not None and
                    cell.bbox == anchor.bbox and cell.text == anchor.text)
            # Repeated PDF cell rectangles are one physical merged cell.
            # Distinct text or differing rectangles are never silently dropped.
            if (not (0 <= r0 <= r1 < rows and 0 <= c0 <= c1 < cols) or region & occupied or subordinate_slots or
                not all(duplicate_or_empty(k) for k in region - {(r0,c0)})):
                self.warnings.append(f'TABLE_MERGE_DEGRADED_FOR_WORD_COMPATIBILITY: page={source.page}, table={source.table_index}, region={(r0,r1,c0,c1)}')
                continue
            table.cell(r0, c0).merge(table.cell(r1, c1))
            occupied |= region
            merges.append(region - {(r0,c0)})
        skipped = set().union(*merges) if merges else set()
        for row in source.rows:
            if row.height > 0:
                table.rows[row.row_index].height = Pt(row.height)
                table.rows[row.row_index].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
            for source_cell in row.cells:
                if (source_cell.row_index, source_cell.column_index) in skipped:
                    continue
                cell = table.cell(source_cell.row_index, source_cell.column_index)
                cell.vertical_alignment = {'top': WD_CELL_VERTICAL_ALIGNMENT.TOP, 'bottom': WD_CELL_VERTICAL_ALIGNMENT.BOTTOM}.get(source_cell.vertical_alignment, WD_CELL_VERTICAL_ALIGNMENT.CENTER)
                p = cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.first_line_indent = Pt(0)
                p.paragraph_format.left_indent = p.paragraph_format.right_indent = Pt(0)
                sizes = [r.font_size for r in source_cell.runs if r.font_size > 0]
                table_size = max(sizes or [10.5])
                p.paragraph_format.line_spacing = infer_semantic_line_spacing(
                    table_size, table_size * 1.05, source_locator=source_cell.locator,
                ).word_value
                p.alignment = ALIGN[getattr(source_cell, "horizontal_alignment", "left")]
                slots = [s for s in self.template.fill_slots if _key(s.source_locator) == _key(source_cell.locator)]
                if slots:
                    p.alignment = ALIGN[slots[0].destination_style.paragraph_alignment]
                if not source_cell.text.strip() and slots and source_cell.bbox:
                    slot=slots[0]
                    blank=EditableBlank(
                        kind=EditableBlankKind.FORM_BLANK,
                        source_x0=source_cell.bbox[0],source_x1=source_cell.bbox[2],
                        width_pt=max(1.0,source_cell.bbox[2]-source_cell.bbox[0]),
                        semantic_slot=slot.semantic_hint,
                        render_style=EditableBlankRenderStyle.BOTTOM_RULE,
                        source_locator=source_cell.locator,
                    )
                    self._register_blank(blank,rendered_width=source_cell.bbox[2]-source_cell.bbox[0],visible=True)
                    set_cell_bottom_border(cell)
                self.text(p, source_cell.text, source_cell.runs, slots, flow=True)

    def _item_slots(self, item):
        slots=[
            slot for slot in self.template.fill_slots
            if _key(slot.source_locator) == _key(item.source.locator)
            and slot.text_start is not None and slot.text_end is not None
            and item.source_start <= slot.text_start <= slot.text_end <= item.source_end
        ]
        return [slot.model_copy(update={
            'text_start':slot.text_start-item.source_start,
            'text_end':slot.text_end-item.source_start,
        }) for slot in slots]

    def _fill_pattern_for(self, slot, blank=None):
        """Return the Round 5.6 source fill pattern governing ``slot``.

        The production style builder publishes ``fill_pattern_index`` inferred
        from the source rows; this lookup keeps the emitted value inside the
        source's own presentation (kept parentheses, kept underline, kept
        placeholder) instead of letting the value dictate the shape.
        """

        index = getattr(self, "fill_pattern_index", None) or {}
        if not index:
            return None
        if blank is not None:
            label = str(getattr(blank, "semantic_slot", "") or "")
            if label and label in index:
                return index[label]
        for attribute in ("semantic_hint", "slot_id", "slot_type"):
            key = str(getattr(slot, attribute, "") or "")
            if not key:
                continue
            if key in index:
                return index[key]
            stripped = key.replace("_SLOT", "").lower()
            if stripped in index:
                return index[stripped]
        hint = str(getattr(slot, "semantic_hint", "") or "")
        for key, pattern in index.items():
            if key and hint and (key in hint or hint in key or hint in pattern.prefix_text):
                return pattern
        return None

    def _row_replacement(self, row, index, slots):
        if not slots:
            return None
        label=row.item.logical_text.split('：',1)[0].split(':',1)[0].strip()
        for slot in slots:
            replacement=slot_replacement(slot,self.facts)
            if replacement is None:
                continue
            if slot.match_kind == 'table_blank' or slot.semantic_hint in label or label in slot.semantic_hint:
                return slot,replacement
        return None

    @staticmethod
    def _form_text_width(text, font_size):
        compact=''.join((text or '').split())
        return sum(font_size if ord(char) > 127 else font_size * .55 for char in compact)

    def form_block(self, doc, block, *, page_content_x0=18.0, scale=1.0, initial_space_before=0.0):
        """Render a FormBlock as paragraph-native Word form lines.

        The FormBlock is a semantic source grouping only.  Real PDF tables
        continue through :meth:`table`; ordinary form rows never call
        ``Document.add_table``.
        """
        rendered = self.form_renderer.render_block(
            doc,
            block,
            page_content_x0=page_content_x0,
            page_content_x1=float(doc.sections[-1].page_width.pt - page_content_x0),
            scale=scale,
            initial_space_before=initial_space_before,
        )
        first_paragraph_index = len(doc.paragraphs) - len(rendered)
        form_block_index = self.form_block_count
        for row_index, (paragraph, layout, row) in enumerate(rendered):
            # ``rendered`` is emitted in document order; this public
            # collection index remains stable after package serialization.
            paragraph_index = first_paragraph_index + row_index
            self.paragraph_layouts.append(layout)
            self.paragraph_x_errors.append(0.0 if layout.alignment == 'center' else
                                           abs((page_content_x0 + layout.left_indent_pt) - layout.source_x0))
            self.paragraph_y_errors.append(0.0)
            tab_records = [
                {
                    'position_pt': stop.position_pt,
                    'source_x': stop.source_x,
                    'leader': stop.leader,
                    'alignment': stop.alignment,
                    'purpose': stop.purpose,
                }
                for stop in layout.tab_stops
            ]
            self.logical_records.append({
                'kind': 'FormRow',
                'row_type': row.row_type,
                'role': layout.role.value if hasattr(layout.role, 'value') else str(layout.role),
                'source_page': row.item.source.page,
                'paragraph_index': paragraph_index,
                'text': paragraph.text,
                'source_text': row.item.logical_text,
                'source_baselines': sorted({round(line.bbox[1], 1) for line in row.item.source_lines}),
                'source_lines': len(row.item.source_lines),
                'form_block_index': form_block_index,
                'table_index': None,
                'label_x': block.label_x,
                'value_x': block.value_x,
                'annotation_x': block.annotation_x,
                'source_label_x': row.label_x,
                'source_value_x': row.value_x,
                'source_annotation_x': row.annotation_x,
                'alignment': layout.alignment,
                'alignment_role': row.item.alignment_role.value,
                'source_line_center_x': row.centered_form_line.source_line_center_x if row.centered_form_line else None,
                'source_container_center_x': row.centered_form_line.source_container_center_x if row.centered_form_line else None,
                'total_source_width': row.centered_form_line.total_source_width if row.centered_form_line else None,
                'slot_width': row.centered_form_line.slot_width if row.centered_form_line else None,
                'container_bbox': [block.container_x0, row.item.bbox[1], block.container_x1, row.item.bbox[3]],
                'layout_role': layout.role.value if hasattr(layout.role, 'value') else str(layout.role),
                'source_x': layout.source_x0,
                'generated_left_indent': layout.left_indent_pt,
                'source_y': row.item.bbox[1],
                'space_before': layout.space_before_pt,
                'tab_stops': tab_records,
                'x_error_pt': 0.0 if layout.alignment == 'center' else abs((page_content_x0 + layout.left_indent_pt) - layout.source_x0),
                'y_error_pt': 0.0,
            })
        self.form_block_count += 1
        return rendered[-1][0] if rendered else None

    def _build_logical_plan(self) -> LogicalTablePlan:
        """Reconstruct the document's logical tables from its PDF fragments.

        The plan is derived from the same source model the emitter consumes, so
        no case-specific table count, page number or column layout is assumed.
        """
        fragments = [
            (page.page, page.height, table)
            for page in self.template.source_pages
            for table in page.tables
        ]
        return build_logical_source_tables(fragments)

    def build(self, output, generation_report_path=None):
        if not self.template.source_pages:
            raise ValueError('Source format has no pages')
        doc = new_word_safe_document()
        # One Word table per *logical* table: a PDF page fragment is not a table
        # boundary.  Fragments that continue a cell across a page seam are folded
        # into the logical table they belong to instead of being emitted as
        # separate tables.
        self.logical_plan = self._build_logical_plan()
        previous = None
        for page, layout in zip(self.template.source_pages, self.layouts):
            section = doc.sections[-1]
            if previous is not None:
                section = doc.add_section(WD_SECTION.NEW_PAGE)
            previous = (page.width, page.height)
            section.page_width, section.page_height = Pt(page.width), Pt(page.height)
            # Word suppresses space-before at the top after a page break.
            # A public page-local Section margin retains the source top band.
            top = max(18, min(layout.content_box[1], page.height-72))
            section.top_margin = Pt(top)
            section.bottom_margin = Pt(18)
            section.left_margin = section.right_margin = Pt(18)
            page_content_x0 = float(section.left_margin.pt or 18.0)
            usable = page.width - 36
            scale = self.page_scales.get(page.page, 1.0)
            cursor_y = top
            last_paragraph = None
            for item in layout.elements:
                gap = max(0, item.bbox[1] - cursor_y) * scale
                if isinstance(item, FormBlock):
                    last_paragraph = self.form_block(
                        doc,
                        item,
                        page_content_x0=page_content_x0,
                        scale=scale,
                        initial_space_before=gap,
                    )
                    cursor_y=item.bbox[3]
                elif not isinstance(item, LogicalParagraph):
                    source = item
                    if last_paragraph is not None:
                        last_paragraph.paragraph_format.space_after = Pt(gap)
                    if (source.page, source.table_index) in self.logical_plan.continuation_map:
                        # This fragment is a continuation of the logical table
                        # already emitted at the page seam; its content lives in
                        # that table, so it must not become its own table.
                        cursor_y = source.bbox[3]
                        last_paragraph = None
                        continue
                    self.table(
                        doc,
                        self.logical_plan.table_for(source.page, source.table_index) or source,
                        usable,
                        page_content_x0=page_content_x0,
                    )
                    cursor_y = source.bbox[3]
                    last_paragraph = None
                else:
                    source = item.source
                    local_slots = self._item_slots(item)
                    raw_text = source.text[item.source_start:item.source_end]
                    p = doc.add_paragraph(style='Normal')
                    p.alignment = ALIGN[item.alignment_hint]
                    pf = p.paragraph_format
                    pf.space_before = Pt(gap)
                    pf.space_after = Pt(0)
                    pf.first_line_indent = Pt(0 if item.alignment_hint == 'center' else item.first_line_indent_pt)
                    # A paragraph's indent establishes its block position.  A
                    # centered block deliberately has no positioning indent;
                    # ordinary left-aligned text uses the page content edge
                    # and therefore keeps a zero right indent.
                    pf.left_indent = Pt(0 if item.alignment_hint == 'center' else max(0, item.left_indent_pt-page_content_x0))
                    pf.right_indent = Pt(0)
                    pf.line_spacing = infer_semantic_line_spacing(
                        item.font_size_pt, item.line_pitch_pt * scale,
                        source_locator=item.source.locator,
                    ).word_value
                    pf.widow_control = False
                    item_slots = [s for fragment, _start, _end in item.fragments for s in self.template.fill_slots
                                  if _key(s.source_locator) == _key(fragment.locator)]
                    has_project_and_lot_slot = any(s.slot_type == 'PROJECT_AND_LOT_SLOT' for s in item_slots)
                    for fragment_index,(fragment,start,end) in enumerate(item.fragments):
                        raw=fragment.text[start:end]
                        fragment_slots=[s.model_copy(update={'text_start':s.text_start-start,'text_end':s.text_end-start})
                            for s in self.template.fill_slots if _key(s.source_locator)==_key(fragment.locator)
                            and s.text_start is not None and s.text_end is not None and start<=s.text_start<=s.text_end<=end]
                        raw,fragment_slots,restored=restore_inline_rule_blanks(raw,fragment.runs,layout.horizontal_rules,fragment_slots)
                        self.vector_blanks_recovered+=restored
                        if fragment_index and has_project_and_lot_slot:
                            for field_name in ('project_number', 'tender_number'):
                                fact = getattr(self.facts.fields, field_name)
                                if fact.status.value != 'RESOLVED' or fact.resolved_value is None:
                                    continue
                                incompatible = str(fact.resolved_value)
                                if raw.startswith(incompatible) and re.match(r'(?:询比|招标|采购)文件', raw[len(incompatible):]):
                                    raw = raw[len(incompatible):]
                                    self.semantic_slot_corrections.append({
                                        'slot_id': next(s.slot_id for s in item_slots if s.slot_type == 'PROJECT_AND_LOT_SLOT'),
                                        'removed_incompatible_value': incompatible,
                                        'reason': 'identifier in PROJECT_AND_LOT_SLOT across PDF fragments',
                                    })
                                    break
                        if fragment_index and p.text and raw and p.text[-1].isascii() and p.text[-1].isalnum() and raw[0].isascii() and raw[0].isalnum():
                            self._add_run(p,' ',fragment.runs[0] if fragment.runs else None)
                        self.text(p,raw,fragment.runs,fragment_slots,flow=item.flow)
                    if item.kind == 'List':
                        role = ParagraphLayoutRole.LIST_ITEM
                    elif item.kind == 'Heading':
                        role = ParagraphLayoutRole.COVER_TITLE if layout.classification in ('COVER_PAGE', 'CHAPTER_DIVIDER') else ParagraphLayoutRole.HEADING
                    elif item.kind == 'Caption' or len(item.logical_text) <= 40 and item.logical_text.strip().startswith(('致', '收件人')):
                        role = ParagraphLayoutRole.ADDRESSEE
                    else:
                        role = ParagraphLayoutRole.FLOW_BODY
                    source_anchor = item.left_indent_pt if item.kind == 'List' else item.bbox[0]
                    paragraph_layout = ParagraphLayout(
                        role=role,
                        container_x0=float(item.container.container_x0 if item.container else page_content_x0),
                        container_x1=float(item.container.container_x1 if item.container else page.width-page_content_x0),
                        source_x0=float(source_anchor),
                        source_y0=float(item.bbox[1]),
                        alignment=item.alignment_hint,
                        left_indent_pt=float(pf.left_indent.pt or 0.0),
                        right_indent_pt=float(pf.right_indent.pt or 0.0),
                        first_line_indent_pt=float(pf.first_line_indent.pt or 0.0),
                        space_before_pt=float(pf.space_before.pt or 0.0),
                        space_after_pt=float(pf.space_after.pt or 0.0),
                        line_spacing=float(pf.line_spacing or 1.0),
                        tab_stops=[],
                        runs=list(p.runs),
                        source_locator=item.source.locator,
                        source_page=page.page,
                    )
                    self.paragraph_layouts.append(paragraph_layout)
                    generated_x = page_content_x0 + (pf.left_indent.pt or 0.0)
                    self.paragraph_x_errors.append(abs(generated_x - source_anchor) if item.alignment_hint != 'center' else 0.0)
                    self.paragraph_y_errors.append(0.0)
                    self.logical_records.append({'kind':item.kind,'role':role.value,
                        'source_page':page.page,
                        'paragraph_index':len(doc.paragraphs)-1,'text':p.text,'source_text':item.logical_text,
                        'text_bbox':item.text_bbox,'container_bbox':item.paragraph_container_bbox,
                        'source_lines':len(item.source_lines),'fragment_count':len(item.fragments),
                        'source_baselines':sorted({round(l.bbox[1],1) for l in item.source_lines}),
                        'alignment':item.alignment_hint,
                        'alignment_role':item.alignment_role.value,
                        'list_level':item.list_level,
                        'list_number_start_x':item.left_indent_pt+item.first_line_indent_pt if item.kind=='List' else None,
                        'list_text_start_x':item.left_indent_pt if item.kind=='List' else None,
                        'list_container_right':item.container.container_x1 if item.kind=='List' and item.container else None,
                        'list_source_line_xs':[line.bbox[0] for line in item.source_lines] if item.kind=='List' else [],
                        'list_group_key':(
                            page.page,item.list_level,item.list_group_id,
                            round(item.left_indent_pt,1),
                            round(item.first_line_indent_pt,1),
                        ) if item.kind=='List' else None,
                        'left_indent_pt':p.paragraph_format.left_indent.pt or 0.0,
                        'first_line_indent_pt':p.paragraph_format.first_line_indent.pt or 0.0,
                        'layout_role':role.value,
                        'container_x0':paragraph_layout.container_x0,
                        'container_x1':paragraph_layout.container_x1,
                        'source_x':source_anchor,
                        'generated_left_indent':paragraph_layout.left_indent_pt,
                        'source_y':item.bbox[1],
                        'space_before':paragraph_layout.space_before_pt,
                        'tab_stops':[],
                        'x_error_pt':self.paragraph_x_errors[-1],
                        'y_error_pt':0.0})
                    visual_rows = len({round(l.bbox[1], 0) for l in item.source_lines}) or 1
                    cursor_y = item.bbox[1] + visual_rows * item.line_pitch_pt * scale
                    last_paragraph = p
        doc.core_properties.keywords = 'format_source=SOURCE_DOCUMENT;compatibility_mode=WORD_SAFE'
        doc.core_properties.subject = '招标文件格式继承;format_source=SOURCE_DOCUMENT'
        # The emitted table count is the number of *logical* tables, which is the
        # number of PDF page fragments minus the fragments folded into the
        # logical table open at their page seam.  A PDF page boundary is not a
        # Word table boundary, so fragment count is deliberately not asserted.
        if len(doc.tables) != len(self.logical_plan.source_tables):
            raise ValueError('Logical source table count changed before serialization')
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(path)
        from .word_safe_scan import scan_word_safe_docx
        scan = scan_word_safe_docx(path)
        if scan['result'] != 'PASS':
            raise ValueError(f'Word-safe package validation failed: {scan}')
        all_document_text=''.join(paragraph.text for paragraph in doc.paragraphs)
        all_document_text+=''.join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
        nbsp_only=sum(
            1 for text in [all_document_text]
            if '\u00a0' in text and text.replace('\u00a0', '').strip() == ''
        )
        blank_errors=sorted(self.blank_width_errors)
        from tender_basic.source_form_execution import (
            execution_owner_metrics,
            plan_application_metrics,
        )

        # A composite source placeholder filled by adjacent slots is one logical
        # write event, so its applications collapse into one record before the
        # report is serialized and before any plan/application comparison runs.
        self._merge_adjacent_logical_applications()
        owner_metrics = execution_owner_metrics(self)
        application_metrics = plan_application_metrics(
            planned=self._planned_resolved_fields(),
            applications=getattr(self, 'source_fill_applications', []),
        )
        report = {'architecture': 'WordSafeSourceDocumentBuilder', 'compatibility_mode': 'WORD_SAFE',
                  'format_source': 'SOURCE_DOCUMENT', 'source_heading': self.template.source_heading,
                  'source_page_count': len(self.template.source_pages), 'source_table_count': self.template.source_table_count,
                  'source_real_tables': self.template.source_table_count,
                  'pdf_table_fragment_count': len(self.logical_plan.head_keys) + len(self.logical_plan.continuation_map),
                  'logical_table_count': len(self.logical_plan.source_tables),
                  'logical_tables': [
                      {'table_id': logical.table_id,
                       'head_page': self.logical_plan.head_keys[index][0],
                       'head_table_index': self.logical_plan.head_keys[index][1],
                       'source_pages': logical.source_pages,
                       'fragment_count': len(logical.fragments),
                       'logical_rows': len(logical.rows),
                       'continuation_cells': len(logical.continuation_evidence)}
                      for index, logical in enumerate(self.logical_plan.logical_tables)
                  ],
                  'continuation_fragments_merged': self.logical_plan.report.continuation_fragments_merged,
                  'orphan_continuation_fragments': self.logical_plan.report.orphan_continuation_fragments,
                  'false_continuation_merges': self.logical_plan.report.false_continuation_merges,
                  'logical_table_decisions': self.logical_plan.report.decisions,
                  'generated_table_count': len(doc.tables), 'generated_textbox_count': 0,
                  'generated_real_tables': len(doc.tables),
                  'synthetic_layout_tables': 0,
                  'form_layout_table_count': 0,
                  'form_block_count': self.form_block_count,
                  'paragraph_form_count': self.paragraph_form_count,
                  'vector_blanks_recovered': self.vector_blanks_recovered,
                  'editable_blanks': self.blank_records,
                  'detected_editable_blanks': len(self.blank_records),
                  'visible_rule_blanks': self.visible_rule_blank_count,
                  'plain_empty_blanks': self.plain_empty_blank_count,
                  'nbsp_only_placeholder_count': nbsp_only,
                  'invisible_required_blank_count': 0,
                  'blank_width_error_max': max(blank_errors,default=0.0),
                  'blank_width_error_median': blank_errors[len(blank_errors)//2] if blank_errors else 0.0,
                  'inline_blank_count': self.inline_blank_count,
                  'paragraph_layout_count': len(self.paragraph_layouts),
                  'paragraph_layout_records': self.logical_records,
                  'paragraph_x_error_max': max(self.paragraph_x_errors, default=0.0),
                  'paragraph_x_error_median': sorted(self.paragraph_x_errors)[len(self.paragraph_x_errors)//2] if self.paragraph_x_errors else 0.0,
                  'paragraph_y_error_max': max(self.paragraph_y_errors, default=0.0),
                  'paragraph_y_error_median': sorted(self.paragraph_y_errors)[len(self.paragraph_y_errors)//2] if self.paragraph_y_errors else 0.0,
                  'tab_stop_usage': self.tab_stop_usage,
                  'source_form_execution_owners': [
                      item.as_dict() if hasattr(item, 'as_dict') else item
                      for item in getattr(self, 'source_form_execution_owners', [])
                  ],
                  'source_form_execution_owner_count': len(
                      getattr(self, 'source_form_execution_owners', [])
                  ),
                  'source_form_execution_owner_metrics': owner_metrics,
                  'eligible_value_owner_count': owner_metrics['eligible_value_owner_count'],
                  'multiple_eligible_owner_conflicts': owner_metrics[
                      'multiple_eligible_owner_conflicts'
                  ],
                  'source_form_line_value_runs': self.source_form_line_value_runs,
                  'source_form_line_value_run_count': len(self.source_form_line_value_runs),
                  'plan_application_metrics': application_metrics,
                  'planned_resolved_application_count': application_metrics[
                      'planned_resolved_application_count'
                  ],
                  'actual_resolved_application_count': application_metrics[
                      'actual_resolved_application_count'
                  ],
                  'logical_application_record_count': application_metrics[
                      'logical_application_record_count'
                  ],
                  'missing_planned_application_count': application_metrics[
                      'missing_planned_application_count'
                  ],
                  'unexpected_application_count': application_metrics[
                      'unexpected_application_count'
                  ],
                  'application_fact_mismatch_count': application_metrics[
                      'application_fact_mismatch_count'
                  ],
                  'application_value_mismatch_count': application_metrics[
                      'application_value_mismatch_count'
                  ],
                  'application_field_mismatch_count': application_metrics[
                      'application_field_mismatch_count'
                  ],
                  'planned_resolved_fact_count': application_metrics[
                      'planned_resolved_fact_count'
                  ],
                  'actual_covered_resolved_fact_count': application_metrics[
                      'actual_covered_resolved_fact_count'
                  ],
                  'logical_application_merges': self.logical_application_merges,
                  'owner_driven_value_emission_count': self.tab_stop_usage.get(
                      'owner_driven_value_emissions', 0
                  ),
                  'source_fill_applications': [
                      item.as_dict() if hasattr(item, 'as_dict') else item
                      for item in getattr(self, 'source_fill_applications', [])
                  ],
                  'source_fill_application_count': len(
                      getattr(self, 'source_fill_applications', [])
                  ),
                  'positioned_blank_records': self.positioned_blank_records,
                  'positioned_blank_count': len(self.positioned_blank_records),
                  'unreachable_positioned_blank_count': self.unreachable_positioned_blank_count,
                  'fill_slots_detected': len(self.template.fill_slots), 'fill_slots_filled': len(self.filled),
                  'fill_slots_left_blank': len(self.template.fill_slots)-len(self.filled), 'filled_slots': self.filled,
                  'table_style_outliers': self.table_style_outliers,
                  'table_style_outlier_count': len(self.table_style_outliers),
                  'same_role_style_discontinuities': sum(
                      1 for item in self.table_style_outliers
                      if item.get('resolution') == 'PRESERVED_UNEXPLAINED_VARIATION'
                  ),
                  'semantic_slot_corrections': self.semantic_slot_corrections,
                  'raised_glyph_count': sum(len(cell.raised_glyphs) for page in self.template.source_pages
                                            for table in page.tables for row in table.rows for cell in row.cells),
                  'layout_mode': 'GEOMETRY_AWARE',
                  'logical_paragraph_records':self.logical_records,
                  'page_layouts': [{'source_page':p.source_page, 'classification':p.classification, 'content_box':p.content_box} for p in self.layouts],
                  'artifact_filter_report': self.template.artifact_filter_report,
                  'page_scales': self.page_scales,
                  'layout_warnings': self.warnings, 'font_substitutions': self.font_substitutions, 'font_repairs': [],
                  'word_open_status': 'PENDING_MANUAL_CONFIRMATION', 'word_safe_scan': scan,
                  'logical_table_provenance': self._logical_table_provenance(
                      doc, self.logical_plan
                  )}
        if generation_report_path:
            Path(generation_report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return path, report

    def _logical_table_provenance(self, doc, plan):
        """Per-logical-table provenance and cell accounting for this build.

        Each logical table is paired with the Word table that actually carries
        its rows - identified by document-order traversal of ``w:body``, never by
        emission intent - and its source cell texts are compared with the emitted
        ones, so lost, duplicated and invented cells are accounted for.
        """

        from .logical_table_provenance import provenance_for_plan, source_rows_for_plan

        return provenance_for_plan(
            doc,
            plan,
            source_rows=source_rows_for_plan(plan),
            fill_applications=getattr(self, "source_fill_applications", ()),
        )


def build_source_format_docx(project_facts, template, output_path, *, generation_report_path=None):
    return WordSafeSourceDocumentBuilder(project_facts, template).build(output_path, generation_report_path)
