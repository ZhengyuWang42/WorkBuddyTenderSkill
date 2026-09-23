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
                           set_east_asian_font, set_run_character_spacing,
                           set_run_fonts, set_table_cell_margins,
                           set_table_indent, set_table_width)
from .source_fill_policy import (
    COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER,
    recorded_slot_presentation,
    reset_recorded_slot_presentations,
    slot_replacement,
)
from .source_fill_patterns import (
    EVIDENCE_DIRECT,
    EVIDENCE_INVENTED,
    UNDERLINED_BLANK_KINDS,
)
from .source_font_policy import font_name
from .source_vertical_rhythm import dominant_line_pitch
from .intrinsic_spacer import (
    apply_spacing,
    intrinsic_spacer_widths,
    spacer_floor_pt,
)
from .source_vertical_rhythm import (
    SourceVerticalRhythm,
    auto_line_multiple_for_pitch,
    block_rhythm,
    rhythm_metrics,
    source_line_pitch,
)
#: Smallest table width ever emitted, so a pathological source table still has a
#: usable grid.
MIN_TABLE_WIDTH_PT = 36.0

#: The minimum blank margin kept between a table's right edge and the physical
#: page edge.  A table wider than the section text column is reproduced as the
#: source drew it; only the page itself bounds it.
MIN_TABLE_RIGHT_GUARD_PT = 18.0
from .logical_structure import LogicalTablePlan, build_logical_source_tables
from .page_layout import (
    INLINE_BLANK_PREFIX,
INLINE_COMPOSITION_PREFIX,
INLINE_COMPOSITION_SUFFIX,
parse_inline_rule_composition_token,
    INLINE_BLANK_SUFFIX,
    parse_inline_blank_token,
    single_visual_row_join,
    source_visual_rows,
    EditableBlank,
    EditableBlankKind,
    EditableBlankRenderStyle,
    BlankRepresentationKind,
    VALUE_REPLACING_POLICIES,
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

#: A FIGURE SPACE carries the font's own digit advance, which is half an em in
#: the source fonts this emitter reads.  An inline blank's width is the source
#: rule's own width, so the emitter paints whole figure spaces and rides the
#: remainder on the run's character spacing rather than rounding the rule away.
FIGURE_SPACE_ADVANCE_RATIO = 0.5

#: The widest per-character correction the emitter will ask a run for.  Beyond
#: it the width is better approximated by one fewer glyph, and a larger spacing
#: would show as visibly loose text instead of a rule.
MAX_INLINE_BLANK_SPACING_PT = 0.75

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


def add_safe_run(paragraph, text, source=None, underline=None, spacing_pt=None):
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
    if spacing_pt:
        set_run_spacing(run, spacing_pt)
    for index, line in enumerate(text.split('\n')):
        if index:
            run.add_break(WD_BREAK.LINE)
        run.add_text(line)
    return run


def set_run_spacing(run, spacing_pt):
    """Expand a run's own character advance by ``spacing_pt`` per character.

    A run's glyph count is a coarse stand-in for a source rule's width: whole
    figure spaces cannot land on an arbitrary span.  The remainder rides the run's
    character spacing, so what the page paints is the source's width rather than
    the nearest whole number of glyphs.  The element authoring itself lives in
    the reviewed compatibility module, which is the only place allowed to write
    run properties directly.
    """

    set_run_character_spacing(run, spacing_pt)


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

    #: Below this a gap is not material and is not emitted as its own segment;
    #: the source does not separate date labels by fractions of a point.
    MIN_MATERIAL_SEGMENT_PT = 0.5

    @staticmethod
    def _date_row_extent_x0(row) -> float:
        """Where the source *row* begins, which may precede its first label.

        ``label_x`` is where the source starts printing the row's text.  A date
        row's leading fill-in rule can start further left, and that rule is part
        of the row: for a signature date the source begins the row at the frame
        edge and reaches the year through the blank.  Taking the labels as the
        row's start would drop that blank and then have to recover the distance
        some other way - which is how the same displacement ended up owned twice.
        """

        xs = [float(row.label_x)]
        for blank in row.blanks:
            try:
                xs.append(float(blank.source_x0))
            except (AttributeError, TypeError, ValueError):
                continue
        return min(xs)

    @staticmethod
    def _date_row_extent_x1(row) -> float:
        """The source row's effective right edge, rules included."""

        xs = [float(row.item.bbox[2])]
        for blank in row.blanks:
            try:
                xs.append(float(blank.source_x1))
            except (AttributeError, TypeError, ValueError):
                continue
        return max(xs)

    def _source_center_frame_insets(self, row, page_content_x0, page_content_x1) -> dict:
        """Indents that put a CENTER row's centre axis where the source put it.

        ``w:jc=center`` centres content between the paragraph's indents, so the
        axis it centres on is the *frame* centre.  A source row classified
        ``SOURCE_ALIGNED_CENTER`` may still sit slightly off that centre - the
        cover's row spans 214.20-404.02, centroid 309.11, against a frame centre
        of 297.60, i.e. 11.51 pt right of centre.  That offset is inside the
        alignment classification tolerance, so the row *is* centred, but it is
        not centred on the frame.

        The fix is not to abandon centring and indent the glyphs from the left:
        ``w:jc=center`` stays, and the axis is moved by making the paragraph's
        remaining width asymmetric.  With left inset ``L`` and right inset ``R``
        the axis lands at ``frame_centre + (L - R) / 2``, so the required
        asymmetry is ``L - R = 2 * delta``.  Every number here is measured
        source geometry, and this is only consultable by a row already
        classified CENTER.
        """

        frame_x0 = float(page_content_x0)
        frame_x1 = float(page_content_x1)
        row_x0 = self._date_row_extent_x0(row)
        row_x1 = self._date_row_extent_x1(row)
        frame_center = (frame_x0 + frame_x1) / 2.0
        row_center = (row_x0 + row_x1) / 2.0
        delta = row_center - frame_center
        # Below half a point there is no asymmetry to express: the row is
        # centred on the frame and an inset would be invented precision.
        if abs(delta) < 0.5:
            left = right = 0.0
        elif delta > 0:
            left, right = 2.0 * delta, 0.0
        else:
            left, right = 0.0, 2.0 * abs(delta)
        return {
            "kind": "SOURCE_CENTER_ALIGNMENT_FRAME",
            "source_frame_x0": round(frame_x0, 2),
            "source_frame_x1": round(frame_x1, 2),
            "source_frame_center": round(frame_center, 2),
            "source_row_extent_x0": round(row_x0, 2),
            "source_row_extent_x1": round(row_x1, 2),
            "source_row_center": round(row_center, 2),
            "center_axis_delta": round(delta, 2),
            "left_inset_pt": round(left, 2),
            "right_inset_pt": round(right, 2),
        }

    def _date_gap_decomposition(self, gap_x0, gap_x1, covered_spans) -> list:
        """Split a token-to-token gap into intrinsic ``(width_pt, underlined)``.

        A gap between two date labels is not all-or-nothing.  The source may
        underline part of it and leave the rest as open space, so
        ``SOURCE_RULE_WIDTH != TOKEN_GAP_WIDTH``: treating the whole gap as an
        underlined blank would stretch the rule, and treating the whole gap as
        plain would lose the rule.  The decomposition keeps both - every
        uncovered prefix, inter-rule span and suffix stays a non-underlined
        segment of its own width - and the emitted widths always reconstruct
        ``gap_x1 - gap_x0`` exactly, which is checked before anything renders.
        """

        segments: list = []
        cursor = float(gap_x0)
        for raw_start, raw_end in sorted(
            (max(float(s), float(gap_x0)), min(float(e), float(gap_x1)))
            for s, e in covered_spans
        ):
            if raw_end <= raw_start + 1e-6:
                continue
            if raw_start - cursor > self.MIN_MATERIAL_SEGMENT_PT:
                segments.append((raw_start - cursor, False))
            segments.append((raw_end - raw_start, True))
            cursor = max(cursor, raw_end)
        if float(gap_x1) - cursor > self.MIN_MATERIAL_SEGMENT_PT:
            segments.append((float(gap_x1) - cursor, False))
        emitted = sum(width for width, _ in segments)
        self.builder.tab_stop_usage['date_gap_decompositions'] = (
            self.builder.tab_stop_usage.get('date_gap_decompositions', 0) + 1
        )
        self.date_gap_decomposition_log = getattr(
            self, 'date_gap_decomposition_log', None
        )
        if self.date_gap_decomposition_log is None:
            self.date_gap_decomposition_log = []
        self.date_gap_decomposition_log.append(
            {
                "gap_x0": round(float(gap_x0), 2),
                "gap_x1": round(float(gap_x1), 2),
                "source_gap_pt": round(float(gap_x1) - float(gap_x0), 2),
                "segments": [
                    {"width_pt": round(w, 2), "underlined": u} for w, u in segments
                ],
                "emitted_total_pt": round(emitted, 2),
                "reconstructs_source_gap": bool(
                    abs(emitted - (float(gap_x1) - float(gap_x0))) <= 0.05
                ),
            }
        )
        return segments

    def _record_date_segment_conflict(self, record: dict) -> None:
        """Record one date geometry segment this mechanism could not match.

        A conflict is evidence, not a failure to hide: the caller has already
        chosen the smaller of two errors, and this list is what lets the audit
        tell a construct whose emitted segments sum to the source interval from
        one that only appears to.
        """

        recorded = getattr(self, 'date_segment_floor_conflicts', None)
        if recorded is None:
            recorded = []
            self.date_segment_floor_conflicts = recorded
        recorded.append(record)

    def _intrinsic_spacer(self, paragraph, width_pt, source, *, underlined: bool):
        """One space run whose measured rendered width is ``width_pt``.

        The width belongs to the run, so a centred paragraph can centre it -
        which an absolute tab stop cannot do.  The spacer is the run's own
        native Word underline when a source rule covers this span, and an
        ordinary unmarked run otherwise; underscore glyphs are never used.

        Returns the width the run will actually render, which for a target
        below the mechanism's floor is the floor itself rather than the target.
        The caller compares the two so a construct that had to be inflated is
        recorded instead of silently reported as exact.
        """

        family, size = self._spacer_source_metrics(source, 10.5)
        twips, rendered = intrinsic_spacer_widths(width_pt, family, size)
        run = self.builder._add_run(paragraph, ' ', source, underline=bool(underlined))
        apply_spacing(run, twips)
        self.builder.tab_stop_usage['intrinsic_spacer_runs'] = (
            self.builder.tab_stop_usage.get('intrinsic_spacer_runs', 0) + 1
        )
        return rendered

    def _figure_space_count(self, width_pt, source, fallback_size) -> int:
        """How many figure spaces render a source gap of ``width_pt``.

        The count is derived from the *measured* advance of one figure space in
        this run's own font, not from a ratio assumed for the font: an assumed
        advance under-fills a wide source blank, and a centred row whose blanks
        are short is then centred around a construct narrower than the source
        drew - which moves every one of its tokens off the source x even though
        the alignment itself is right.
        """

        size = max(6.0, float(getattr(source, 'font_size', fallback_size) or 10.5))
        advance = 0.0
        try:
            advance = float(self.builder._form_text_width('\u2007', size) or 0.0)
        except Exception:
            advance = 0.0
        if advance <= 0.1:
            advance = size * .55
        return max(1, int(round(max(0.0, float(width_pt)) / advance)))

    @staticmethod
    def _date_token_boxes(row) -> list:
        """The source's own measured boxes for a date row's printed tokens.

        A date row is written ``____年____月____日``.  The PDF extractor returns
        the three labels as three *separate* visual lines, because the source
        leaves a writable gap between them that is wider than the intra-line
        fragment threshold - so the row item's own ``source_lines`` carry each
        label's real span.  That geometry is the only evidence for how wide the
        gap between two labels is: the source's text layer holds no space
        characters there, so comparing the row as *text* cannot tell
        ``年月日`` from ``年    月    日`` at all.

        Returns one ``(x0, x1)`` pair per printed token, in row order, or an
        empty list when the row's geometry does not pair one visual line with
        each printed token.
        """

        lines = list(getattr(getattr(row, "item", None), "source_lines", ()) or ())
        boxes = []
        for line in lines:
            bbox = getattr(line, "bbox", None)
            if not bbox or not str(getattr(line, "text", "") or "").strip():
                return []
            boxes.append((float(bbox[0]), float(bbox[2])))
        return boxes

    @staticmethod
    def _spacer_source_metrics(source, fallback_size):
        """``(family, size_pt)`` the intrinsic spacer calibration is read with.

        One place, so the emitted run's own font metrics and the calibration
        lookup can never drift apart.
        """

        family = getattr(source, 'font_name', None) or getattr(source, 'name', None)
        size = max(6.0, float(getattr(source, 'font_size', fallback_size) or 10.5))
        return family, size

    def _source_date_gap(self, row, part_index, blank=None):
        """The measured source interval one date-row blank stands for.

        ``part_index`` addresses a blank part.  The tokens are the non-blank
        parts, so for an *interior* blank the gap sits between token ``n - 1``
        and token ``n`` where ``n`` is how many tokens precede it.

        THE LEADING INTERVAL IS GEOMETRY TOO.  ``part_index`` is 0 for the
        first blank of a date row that carries no label, and that blank is not
        an absence: ``____年`` begins the row with a fill-in space the source
        drew, 69.00 pt wide on the cover.  Treating it as "no preceding token,
        therefore no gap" left the row's own first segment unowned, and the
        fallback that picked it up counted figure-space glyphs - which is why
        the cover's construct came out shorter than the source drew it and
        ``w:jc=center`` then centred every token around the wrong width.

        The leading interval runs from where the blank itself starts to where
        the first token starts, which is the same construction as an interior
        gap with the blank's own measured start standing in for the previous
        token's end.  For a *labelled* row the label is a part of its own and is
        counted as a token, so its blank is an interior gap reached from the
        label's right edge.

        Returns ``(gap_pt, next_token_x0)`` or ``None``.
        """

        boxes = self._date_token_boxes(row)
        parts = list(getattr(row, "parts", ()) or ())
        tokens = [candidate for candidate in parts if str(candidate).strip()]
        if not boxes or len(tokens) != len(boxes):
            return None
        preceding = sum(
            1 for candidate in parts[:part_index] if str(candidate).strip()
        )
        if preceding == 0:
            leading_x0 = self._leading_date_interval_x0(row, blank)
            if leading_x0 is None:
                return None
            gap = boxes[0][0] - leading_x0
            if gap <= 0.0:
                return None
            return gap, boxes[0][0]
        previous_token, next_token = preceding - 1, preceding
        if previous_token < 0 or next_token >= len(boxes):
            return None
        gap = boxes[next_token][0] - boxes[previous_token][1]
        if gap <= 0.0:
            return None
        return gap, boxes[next_token][0]

    def _leading_date_interval_x0(self, row, blank):
        """Where a date row's leading fill-in interval starts, or ``None``.

        The blank's own measured start is the authority when it has one: a
        labelled row reaches its first blank from the label, and the row's
        paragraph origin is already the row extent.  Falling back to the row
        extent keeps the interval defined for a row whose blank carries no
        usable span, and the caller still drops it when the interval is empty.
        """

        if blank is not None:
            try:
                return float(blank.source_x0)
            except (AttributeError, TypeError, ValueError):
                return self._date_row_extent_x0(row)
        return self._date_row_extent_x0(row)

    def _positioned_rule_blank(
        self,
        paragraph,
        blank,
        source,
        *,
        page_content_x0,
        page_content_x1,
        cursor_x,
    ):
        """Paint one source-drawn row blank at its own measured span.

        FORM-ROW ORIGIN vs FIELD ANCHOR.  A row's *origin* is a property of the
        row's own source text: ``供应商名称：`` starts where the source starts
        it, and so does ``成立时间：``.  A field *anchor* is where the blank
        after that text begins.  They are different concepts, and the paragraph
        may only carry the first: moving the paragraph's left indent onto the
        anchor drags the row's label right by the whole anchor offset.

        The field is therefore reached from the row's own origin with
        source-derived tab stops.  ``w:tab/@w:pos`` is measured from the section
        text margin, which is the same origin the source ``x0``/``x1`` are
        expressed in, so the two stops of one span put the painted rule exactly
        where the source draws it.  An anchor tab is emitted only when the
        cursor measured so far is still behind the span start; the leader tab
        then carries the cursor to the span end under an underline.

        Returns the row's new cursor estimate.
        """

        blank_x0 = float(blank.source_x0)
        blank_x1 = min(float(blank.source_x1), float(page_content_x1))
        if blank_x1 <= blank_x0:
            blank_x1 = blank_x0 + 1.0
        # ONE OWNER PER DISPLACEMENT.  A row's leading blank is often the very
        # span the paragraph's own origin already stands at: the row begins
        # where that blank begins, so that displacement has been spent before
        # the first run is emitted.  Emitting the blank's tabs on top of that
        # origin charges the same source distance twice - the paragraph carries
        # the row to the blank and the anchor tab carries it again - which put
        # the year label 40.63 pt past where the source prints it.  When the
        # cursor already stands at or past the blank's end, the blank has been
        # reached and owns nothing further.
        if float(cursor_x) + 0.5 >= blank_x1:
            self.builder._register_blank(
                blank,
                rendered_width=blank_x1 - blank_x0,
                visible=blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY,
            )
            return max(float(cursor_x), blank_x1)
        size = max(6.0, float(getattr(source, "font_size", 0) or 10.5))
        anchor_position = self.builder._source_tab_position(blank_x0, page_content_x0)
        leader_position = self.builder._source_tab_position(blank_x1, page_content_x0)
        tab_stops = paragraph.paragraph_format.tab_stops
        anchored = float(cursor_x) + 1.0 < blank_x0
        if anchored:
            tab_stops.add_tab_stop(
                Pt(anchor_position), WD_TAB_ALIGNMENT.LEFT, WD_TAB_LEADER.SPACES
            )
            self.builder._add_run(paragraph, "\t", source)
            self._count_anchor_tab()
        tab_stops.add_tab_stop(
            Pt(leader_position), WD_TAB_ALIGNMENT.LEFT, WD_TAB_LEADER.SPACES
        )
        self.builder._add_run(paragraph, "\t", source, underline=True)
        self.builder.tab_stop_usage["positioned_leader_tabs"] = (
            self.builder.tab_stop_usage.get("positioned_leader_tabs", 0) + 1
        )
        self.builder._register_blank(
            blank,
            rendered_width=blank_x1 - blank_x0,
            visible=blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY,
        )
        self.builder.positioned_blank_records.append(
            {
                #: The emission's own identity.  A positioned blank's source
                #: evidence is a *span*: some come from a registered numbered
                #: rule and carry its id, others are source vector lines that
                #: were never registered.  The span identity is what makes every
                #: emission distinguishable - and therefore what makes a
                #: duplicate emission detectable - whether or not a rule id
                #: exists for it.
                "emission_id": "POSITIONED_BLANK|p%s|%.2f-%.2f"
                % (
                    getattr(getattr(blank, "source_locator", None), "page", None),
                    blank_x0,
                    blank_x1,
                ),
                "semantic_slot": blank.semantic_slot,
                "source_rule_id": getattr(blank, "source_rule_id", None),
                "source_page": getattr(
                    getattr(blank, "source_locator", None), "page", None
                ),
                "source_x0": round(blank_x0, 2),
                "source_x1": round(blank_x1, 2),
                "source_span_pt": round(blank_x1 - blank_x0, 2),
                "representation_kind": str(
                    getattr(
                        getattr(blank, "representation_kind", None), "value",
                        getattr(blank, "representation_kind", ""),
                    )
                ),
                "emission_mechanism": "SOURCE_POSITIONED_UNDERLINED_TAB",
                "paragraph_origin_pt": round(float(page_content_x0), 2),
                "anchor_tab_position_pt": round(anchor_position, 2) if anchored else None,
                "leader_tab_position_pt": round(leader_position, 2),
                "row_origin_preserved": True,
            }
        )
        return blank_x1

    def _count_anchor_tab(self):
        """One anchor tab was used to reach a source field's own start."""

        self.builder.tab_stop_usage["anchor_tabs"] = (
            self.builder.tab_stop_usage.get("anchor_tabs", 0) + 1
        )
        self.builder.tab_stop_usage["positioned_anchor_tabs"] = (
            self.builder.tab_stop_usage.get("positioned_anchor_tabs", 0) + 1
        )

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

    def _row_right_indent(self, row, page_content_x1):
        """Negative right indent for a row that overhangs the section frame.

        The indent is the row's own source right edge against the section frame,
        so it only exists when the source itself places content beyond the frame.
        A row that ends inside the frame keeps a zero indent.
        """

        if page_content_x1 is None:
            return 0.0
        right = max(
            [float(row.item.bbox[2]), float(row.annotation_x)]
            + [float(blank.source_x1) for blank in row.blanks]
        )
        return round(min(0.0, float(page_content_x1) - right), 2)

    def _render_row(self, doc, row, block, *, page_content_x0, page_content_x1, scale, space_before):
        source = self._source_run(row)
        p = doc.add_paragraph(style='Normal')
        role = self._role(row)
        blanks_for_anchor = row.blanks
        date_row = row.row_type == 'DATE_ROW'
        # FORM-ROW ORIGIN.  A row's paragraph origin is the row's own source text
        # origin - where the source starts printing the row - and never the
        # anchor of the first field drawn on it.  A labelled date row such as
        # ``成立时间：___年___月___日`` starts its label at the same source x as
        # its sibling rows; its three blanks merely begin later.  Deriving the
        # paragraph indent from the first blank instead moved the whole row right
        # by the anchor offset (P44-R4 x0 131.85 - 70.80 = 61.05 pt).  The field
        # is reached from this origin with source-derived tab stops, so both the
        # label and the blanks keep their source geometry.
        label_x = float(row.label_x)
        pf = p.paragraph_format
        centered = row.item.alignment_role == AlignmentRole.CENTERED_FORM_LINE
        # PARAGRAPH SEMANTIC ALIGNMENT, NOT A POSITIONAL INDENT.  A centred form
        # row states its alignment natively and must carry no indent at all: the
        # source centres the row, so ``w:jc`` is the representation and a large
        # ``w:left`` chosen to *look* centred is not.  A row the source anchors
        # inside a signature block is a different fact - it keeps its own
        # measured source origin as an independently source-backed body-frame
        # indent, which is the same x the source drew it at.
        row_origin_x = self._date_row_extent_x0(row) if date_row else label_x
        # ONE OWNER PER DISPLACEMENT.  The paragraph origin owns *where the row
        # begins*; every displacement after that - including a leading fill-in
        # blank the source draws before the first label - is owned by the
        # intrinsic segments that follow.  Charging both put the signature date's
        # year 40.63 pt past its source x.  A centred row states its alignment
        # natively and carries no indent, so its row origin must come from the
        # segment sequence instead.
        if centered:
            # SOURCE_CENTER_ALIGNMENT_FRAME.  Native centring stays; the axis it
            # centres on is corrected to the source row's own measured centre.
            frame = self._source_center_frame_insets(row, page_content_x0, page_content_x1)
            pf.left_indent = Pt(frame["left_inset_pt"])
            center_frame_inset = frame
            log = getattr(self, 'center_alignment_frames', None)
            if log is None:
                log = []
                self.center_alignment_frames = log
            log.append(frame)
        else:
            pf.left_indent = Pt(max(0.0, row_origin_x - page_content_x0))
            center_frame_inset = None
        # A row whose own source extent leaves the stable section frame keeps its
        # source right edge through a negative right indent.  The frame is a
        # section-level bound, not a per-row content box: a signature row that the
        # source draws out to x1=533.40 inside a 524.40 frame is reproduced, not
        # narrowed into a wrap.
        pf.right_indent = Pt(
            self._row_right_indent(row, page_content_x1)
            + (center_frame_inset["right_inset_pt"] if center_frame_inset else 0.0)
        )
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
        # The row's own emitted cursor, in the same absolute source x space the
        # blanks are expressed in.  A blank whose start the source already
        # reached needs no anchor tab; one still ahead of it does.
        cursor_x = row_origin_x
        for part_index, part in enumerate(row.parts):
            if self._is_blank(row, part_index, part):
                blank = self._blank_for(row, blank_cursor)
                blank_cursor += 1
                purpose = 'date' if role == ParagraphLayoutRole.DATE_LINE else (
                    'multi_field' if row.row_type == 'MULTI_INLINE_FIELDS' else 'blank'
                )
                date_replacement = self.builder._row_replacement(row, part_index, slots) if role == ParagraphLayoutRole.DATE_LINE else None
                if (
                    role == ParagraphLayoutRole.DATE_LINE
                    and self._is_solid_rule_blank(blank)
                    and blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY
                    and date_replacement is None
                    # CANDIDATE A REJECTED: an absolute source-positioned tab
                    # stop measures from the margin, but a CENTER paragraph
                    # chooses its own line start from the content width, so the
                    # leader painted from the centred start to the stop and
                    # over-ran the source gap (+212.36 pt on the cover).  A
                    # centred row may not position its interior absolutely.
                    and row.centered_form_line is None
                    # The intrinsic decomposition owns a date gap's *width*, so
                    # it must be reached first.  This tab branch runs earlier and
                    # would claim the blank, painting only the source rule's span
                    # and letting the paragraph origin carry the rest - which is
                    # how the partially-covered signature gaps lost their
                    # uncovered 5-6 pt residual.  This branch stays only as the
                    # fallback for a date rule whose geometry does not pair.
                    and self._source_date_gap(row, part_index, blank) is None
                ):
                    # The source draws this date field as a measured rule.  Its
                    # physical span is the authority, so it is painted from its
                    # own source anchor with tab stops measured from the section
                    # text margin - the row's label keeps its own origin.
                    cursor_x = self._positioned_rule_blank(
                        p,
                        blank,
                        source,
                        page_content_x0=page_content_x0,
                        page_content_x1=page_content_x1,
                        cursor_x=cursor_x,
                    )
                    previous_anchor = max(previous_anchor, cursor_x)
                    continue
                if (
                    role == ParagraphLayoutRole.DATE_LINE
                    and date_replacement is None
                ):
                    # A SOURCE GAP IS FORMAT, NOT ABSENT TEXT.  The source prints
                    # the date labels apart and leaves the space between them for
                    # the date to be written into.  Nothing is drawn under that
                    # space, so the blank is plain whitespace - and plain
                    # whitespace used to emit nothing at all, collapsing
                    # ``年    月    日`` into ``年月日``.  Emit the *measured*
                    # source gap as a plain, un-underlined run of figure spaces:
                    # the row keeps its source rhythm and stays editable, and no
                    # glyph or underline the source does not draw is invented.
                    date_gap = self._source_date_gap(row, part_index, blank)
                    if date_gap is not None:
                        gap_pt, next_token_x0 = date_gap
                        # INTRINSIC SOURCE-MEASURED SEGMENTS.  The gap's width and
                        # the part of it a source rule covers both come from the
                        # source's own coordinates; the run's rendered width is
                        # then stated in tracking, so it survives w:jc=center.
                        # Absolute tabs cannot do this (they are measured from
                        # the margin, which a centred line does not start at),
                        # and a figure-space count reproduces the width only if
                        # the spacer's advance divides it.
                        #
                        # ONLY A SOURCE-DRAWN RULE MAY BE UNDERLINED.  A date
                        # blank's span is where the *document* may be written,
                        # and for most of these rows the parser derives it from
                        # a fill pattern rather than from a drawn line: on source
                        # pages 42, 43, 45, 47, 48, 53 and 60 the 年月日 band
                        # contains no vector rule at all, yet the registered span
                        # overlaps the gap and used to be emitted as an
                        # underlined segment.  That painted a rule the source
                        # never drew, over a width the source never drew it at,
                        # and left a sub-space plain prefix in front of it.  The
                        # blank's span is taken as the rule only when the blank
                        # *is* a solid rule blank; otherwise the whole gap is
                        # open space and the decomposition emits it plain.
                        covered = []
                        if self._is_solid_rule_blank(blank):
                            try:
                                covered.append(
                                    (float(blank.source_x0), float(blank.source_x1))
                                )
                            except (AttributeError, TypeError, ValueError):
                                pass
                        segments = self._date_gap_decomposition(
                            next_token_x0 - gap_pt, next_token_x0, covered
                        )
                        family, size = self._spacer_source_metrics(
                            source, row.item.font_size_pt
                        )
                        floor_pt = spacer_floor_pt(family, size)
                        for width, underlined in segments:
                            # REPRESENTATION FLOOR.  One space plus tracking
                            # cannot render narrower than the space's own
                            # advance, so a segment below that floor cannot be
                            # drawn by this mechanism at all.  Emitting a
                            # physical U+0020 for it would add the whole advance
                            # to the construct: on a CENTER row that widens the
                            # row by ~6 pt and shifts every token half of it,
                            # which is exactly the uniform translation seen on
                            # the cover.  Empty geometry owns nothing, so it
                            # emits nothing, and the conflict is recorded rather
                            # than silently clamped or silently dropped.
                            if width <= self.MIN_MATERIAL_SEGMENT_PT:
                                self.builder.tab_stop_usage[
                                    'intrinsic_segments_below_floor'
                                ] = self.builder.tab_stop_usage.get(
                                    'intrinsic_segments_below_floor', 0
                                ) + 1
                                self._record_date_segment_conflict(
                                    {
                                        "target_width_pt": round(width, 3),
                                        "underlined": bool(underlined),
                                        "floor_pt": round(floor_pt, 3),
                                        "mechanism_floor_pt": round(floor_pt, 3),
                                        "reason": (
                                            "narrower than the date row's own "
                                            "materiality floor; not representable as "
                                            "a segment of its own, no spacer emitted"
                                        ),
                                    }
                                )
                                continue
                            self.builder._register_blank(
                                blank, rendered_width=width, visible=True
                            )
                            rendered = self._intrinsic_spacer(
                                p, width, source, underlined=underlined
                            )
                            # HONEST ARITHMETIC.  A target between the materiality
                            # floor and the spacer's own floor is emitted at the
                            # spacer's floor: the segment is real source geometry
                            # and dropping it would move everything after it, so
                            # the inflation is the smaller error - but it is
                            # recorded, because a construct whose emitted segments
                            # do not sum to the source interval must not be
                            # reported as exact.
                            if rendered - width > 0.05:
                                self.builder.tab_stop_usage[
                                    'intrinsic_segment_inflations'
                                ] = self.builder.tab_stop_usage.get(
                                    'intrinsic_segment_inflations', 0
                                ) + 1
                                self._record_date_segment_conflict(
                                    {
                                        "target_width_pt": round(width, 3),
                                        "rendered_width_pt": round(rendered, 3),
                                        "inflation_pt": round(rendered - width, 3),
                                        "underlined": bool(underlined),
                                        "floor_pt": round(floor_pt, 3),
                                        "mechanism_floor_pt": round(floor_pt, 3),
                                        "reason": (
                                            "target below one untracked space; the run "
                                            "renders at the space advance"
                                        ),
                                    }
                                )
                        previous_anchor = max(previous_anchor, next_token_x0)
                        cursor_x = max(cursor_x, next_token_x0)
                        continue
                if role == ParagraphLayoutRole.DATE_LINE and blank.render_style != EditableBlankRenderStyle.PLAIN_EMPTY and date_replacement is None:
                    # LEGACY DATE FIGURE-SPACE PATH.  Reached only when a date
                    # blank has no measurable source interval (the token boxes and
                    # the row's parts do not pair), so the width has to be
                    # approximated by counting figure-space glyphs.  It must not
                    # fire for a row whose geometry *was* measured: the count is
                    # quantised by the glyph's advance, so the row's construct
                    # comes out at a multiple of it and a centred row then centres
                    # every token around the wrong width.  The audit asserts zero
                    # of these runs inside date rows; this counter is how a
                    # regression becomes visible.
                    self.builder.tab_stop_usage['date_legacy_figure_space_runs'] = (
                        self.builder.tab_stop_usage.get('date_legacy_figure_space_runs', 0)
                        + 1
                    )
                    display_x1 = min(float(blank.source_x1), float(page_content_x1))
                    display_width = max(1.0, display_x1 - float(blank.source_x0))
                    self.builder._register_blank(blank, rendered_width=display_width, visible=True)
                    count = max(2, self._figure_space_count(display_width, source, row.item.font_size_pt))
                    self.builder._add_run(p, '\u2007' * count, source, underline=True)
                    self.builder.tab_stop_usage['date_underlined_runs'] = self.builder.tab_stop_usage.get('date_underlined_runs', 0) + 1
                    previous_anchor = max(previous_anchor, display_x1)
                    cursor_x = max(cursor_x, display_x1)
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
                    cursor_x = max(cursor_x, blank.source_x1)
                if not filled and blank.render_style == EditableBlankRenderStyle.PLAIN_EMPTY:
                    previous_anchor = max(previous_anchor, blank.source_x1)
                    cursor_x = max(cursor_x, blank.source_x1)
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
            cursor_x = max(
                cursor_x,
                cursor_x + self.builder._form_text_width(
                    part, getattr(source, 'font_size', row.item.font_size_pt)
                ),
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
        tops = [float(row.item.bbox[1]) for row in block.row_geometries]
        # SHARED VERTICAL RHYTHM.  A block's rows are its own text block, so they
        # advance by the source's measured row pitch; a true block boundary is a
        # gap large enough, against that pitch, to be a boundary rather than a
        # continuation.  Only the boundary keeps its own source gap.  The rhythm
        # record travels with the emission as evidence.
        self.builder._record_block_rhythm(block, tops)
        for index, row in enumerate(block.row_geometries):
            if index == 0:
                gap = max(0.0, float(initial_space_before))
            else:
                gap = self.builder._rhythm.snap(
                    max(0.0, row.item.bbox[1] - previous_bottom) * scale
                )
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


def plan_table_width(preferred, *, table_left, usable, page_width,
                     min_width=MIN_TABLE_WIDTH_PT,
                     right_guard=MIN_TABLE_RIGHT_GUARD_PT):
    """Resolve the width a Word table receives for one source table.

    The source table's own width is the authority.  The section frame bounds the
    *text column*, not a table: a source table wider than the frame - many tender
    tables start left of the body and end right of it - keeps its measured width
    and overhangs the frame exactly as the source does.  The only real limit is
    the physical page, so the clamp is taken against the page edge with a minimum
    right margin, never against the section's usable text width, which silently
    compressed every grid column.

    Returns ``(target_total_pt, available_pt, clamped_to_page)``.
    """

    preferred = max(1.0, float(preferred))
    if page_width and page_width > 0:
        available = max(float(min_width),
                        float(page_width) - float(table_left) - float(right_guard))
    else:
        available = max(float(min_width), float(usable))
    return min(preferred, available), available, bool(preferred > available + 0.01)


def _twips_value(element, attribute, qn):  # pragma: no cover - helper for reports
    value = element.get(qn(attribute)) if element is not None else None
    return None if value is None else int(value)


def _twips_value(element, attribute, qn):  # pragma: no cover - helper for reports
    value = element.get(qn(attribute)) if element is not None else None
    return None if value is None else int(value)


def flow_cursor_blank_representation(in_table_cell, source_visual_row_count) -> bool:
    """Whether an unreachable source blank is painted inline at the flow cursor.

    A paragraph reconstructed from several source rows wraps by Word's own
    rules, so a rule's row-local ``x`` is not reachable by any tab stop and
    starting the rule's own form line would put a hard break inside flowing
    prose the source never broke.  Such a blank keeps the source's *width* and
    is painted where the cursor stands.  A single-row source form line reaches
    its rule with an anchor tab, and a table cell has its own line structure, so
    neither takes this representation.
    """

    if in_table_cell:
        return False
    return int(source_visual_row_count or 1) > 1


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
        #: Stage E table geometry evidence: every emitted table records its source
        #: geometry and the geometry Word actually received, so a table-width
        #: clamp can never be silent.
        self.table_geometry_records = []
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
        #: Mid-row blanks on a source line the delivered paragraph has already
        #: flowed past.  Their absolute x cannot be reached, so they are emitted
        #: inline at the flow cursor with the source's own width instead of being
        #: dropped: the paragraph flows (no invented line break) and the source
        #: blank the reviewer reads is still on the page.
        self.flow_inline_blank_count = 0
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
        #: Character ranges, in the fragment text currently being emitted, whose
        #: source decoration is inherited by a replacement value.  Set by the
        #: logical-content emitter for exactly one emission call at a time.
        self._inherited_value_decoration_ranges = ()
        #: Declared paragraph coordinate frames, one per positioned rule.
        self._positioned_coordinate_frames = []
        self._positioned_paragraph = None
        self._positioned_paragraph_start = 0
        #: SHARED VERTICAL RHYTHM.  One document-wide sampling of the source's
        #: own row gaps, so a repeated form row is spaced by the source's
        #: rhythm instead of by its own absolute y offset.
        #: A new delivery starts with no recorded slot presentations, so one
        #: build can never inherit another build's emission provenance.
        reset_recorded_slot_presentations()
        self._source_gap_population: tuple = ()
        self._source_gap_rows: tuple = ()
        self._rhythm = None
        self.vertical_rhythm_blocks = []
        self.vertical_rhythm_rows = []
        self.vertical_rhythm_expansions = []
        self.vertical_rhythm_source_spacings = []
        self.vertical_rhythm_line_pitch_sample = ()
        # The rhythm is sampled once per build, *after* the source page frames
        # are known, so the sampler and the emitter cannot disagree about where a
        # page's first element starts or how the cursor advances.
        self._prepare_source_vertical_rhythm()
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

    def _add_run(self, paragraph, text, source=None, underline=None, spacing_pt=None):
        """Hook for the style-first builder; the Round 4.9 path is unchanged."""

        return add_safe_run(paragraph, text, source, underline, spacing_pt=spacing_pt)

    def _source_extent_for_text_range(self, runs, text, start, end):
        """Source x extent of ``text[start:end]``, measured inside its runs.

        A source placeholder and the fixed prose around it can share one source
        run, so the run box alone cannot say which characters a rule was drawn
        beneath.  Each run's own box is therefore interpolated character by
        character in reading order, which is the finest granularity a Word run
        underline can honour (a delivered run is underlined all-or-nothing).
        """

        positions = [i for i, character in enumerate(text) if not character.isspace()]
        if not positions:
            return None
        compact = "".join(text[i] for i in positions)
        compact_start = sum(1 for i in positions if i < start)
        compact_end = sum(1 for i in positions if i < end)
        if compact_end <= compact_start:
            return None
        x0 = x1 = None
        cursor = 0
        for run in runs:
            key = "".join(str(getattr(run, "text", "") or "").split())
            if not key:
                continue
            at = compact.find(key, cursor)
            if at < 0:
                continue
            cursor = at + len(key)
            run_start, run_end = at, at + len(key)
            if run_end <= compact_start or compact_end <= run_start:
                continue
            box = getattr(run, "bbox", None)
            if not box:
                continue
            width = float(box[2]) - float(box[0])
            first = max(0, compact_start - run_start)
            last = min(len(key), compact_end - run_start)
            left = float(box[0]) + width * (first / len(key))
            right = float(box[0]) + width * (last / len(key))
            x0 = left if x0 is None else min(x0, left)
            x1 = right if x1 is None else max(x1, right)
        return None if x0 is None else (x0, x1)

    def _slot_source_decoration_underline(self, slot, runs=None, text=None) -> bool:
        """Whether the source decorates this semantic slot with an underline.

        The compiled rule registry already binds each physical rule to the
        authoritative slot it decorates, so the source's own slot decoration is
        read from that provenance first.  A rule bound to a slot whose placeholder
        a resolved value replaces is a line the source drew on that slot whatever
        occupancy label the rule was given: a line that carries a blank, the
        placeholder and more blank is *classified* a form-layout rule because most
        of its extent is not glyphs, which is a statement about the rule's
        coverage and not about whether the rule is a line.  Where the binding has
        not been enriched yet, the decision falls back to source geometry: the
        placeholder's own extent, interpolated inside its source runs, against
        the rule's span on the same visual line.  A replacement value inheriting
        this decoration is preservation of source slot decoration, not an
        invented underline, and it is independent of any literal page or text.
        """

        slot_id = getattr(slot, "slot_id", None)
        geometry = getattr(slot, "geometry", None)
        page = getattr(slot, "source_page", None)
        start = getattr(slot, "text_start", None)
        end = getattr(slot, "text_end", None)
        extent = None
        if runs is not None and text is not None and start is not None and end is not None:
            extent = self._source_extent_for_text_range(runs, text, start, end)
        if extent is None and geometry:
            extent = (float(geometry[0]), float(geometry[2]))
        bindings = getattr(self, "_rule_slot_binding", None) or {}
        policies = getattr(self, "_rule_transformation_policy", None) or {}
        for entry in getattr(self, "source_rule_registry", None) or []:
            rule_id = entry.get("source_rule_id")
            binding = bindings.get(rule_id) or {}
            if (
                slot_id is not None
                and binding.get("slot_id") == slot_id
                and binding.get("resolved_fact_fields")
                and policies.get(rule_id) in VALUE_REPLACING_POLICIES
            ):
                return True
            if "UNDERLINE" not in str(entry.get("relation_type", "")):
                continue
            if page is None or extent is None or entry.get("source_page") != page:
                continue
            span = max(1.0, extent[1] - extent[0])
            overlap = min(float(entry.get("x1", 0.0)), extent[1]) - max(
                float(entry.get("x0", 0.0)), extent[0]
            )
            if overlap <= 0.5 * span:
                continue
            rule_y = float(entry.get("y", 0.0))
            if geometry:
                y0, y1 = float(geometry[1]), float(geometry[3])
                if rule_y < y0 - 2.0 or rule_y > y1 + 12.0:
                    continue
            return True
        return False

    def _slot_inherits_source_decoration(self, slot, runs=None, text=None) -> bool:
        """Whether this slot's replacement value inherits a source decoration.

        Two independent, evidence-backed routes: a rule the emitter established
        as decorating a placeholder overlapping this slot on the same visual
        line, and the rule bound to the slot itself.
        """

        start = getattr(slot, "text_start", None)
        end = getattr(slot, "text_end", None)
        if start is not None and end is not None:
            for range_start, range_end in (
                getattr(self, "_inherited_value_decoration_ranges", ()) or ()
            ):
                if range_start <= start and end <= range_end:
                    return True
        return self._slot_source_decoration_underline(slot, runs, text)

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

    def _apply_source_paragraph_indent(self, paragraph_format, item, page_content_x0) -> dict:
        """Write a paragraph's source-derived left and first-line indents.

        One implementation, used by both builders, so a paragraph cannot be
        indented by one architecture and wrapped by another.  ``w:ind/@w:left``
        is the body boundary the source returns this paragraph's *wrapped* rows
        to and ``w:ind/@w:firstLine`` is the signed offset of its first row from
        that boundary - positive for a first-line indent, negative for a hanging
        indent, zero when the source gives the first row no special position.
        A centred line has no body boundary to relate its first row to, so it
        carries no indent at all.
        """

        centred = str(getattr(item, "alignment_hint", "") or "") == "center"
        if centred:
            paragraph_format.left_indent = Pt(0)
            paragraph_format.first_line_indent = Pt(0)
            return {
                "left_indent_pt": 0.0,
                "first_line_indent_pt": 0.0,
                "basis": "CENTERED_LINE",
            }
        left = max(
            0.0,
            float(getattr(item, "left_indent_pt", 0.0) or 0.0) - float(page_content_x0),
        )
        first_line = float(getattr(item, "first_line_indent_pt", 0.0) or 0.0)
        paragraph_format.left_indent = Pt(left)
        paragraph_format.first_line_indent = Pt(first_line)
        indent = getattr(item, "source_indent", None)
        return {
            "left_indent_pt": round(left, 4),
            "first_line_indent_pt": round(first_line, 4),
            "basis": (
                "SOURCE_INDENT_CLASSIFICATION"
                if indent is not None
                else "MODEL_LEFT_AND_FIRST_LINE"
            ),
        }

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

    def _flowed_cursor_advance(self, text, font_size, measure_pt):
        """Advance left on the line the flow cursor stands on.

        A paragraph the emitter wrote from several source rows is wrapped by
        Word, so the text already written does not all sit on one line: the
        cursor is at the end of the *last* line the flow produced.  The line
        breaking is the same greedy one Word applies - fill the line, break,
        continue - so replaying it with the emitter's own advance model answers
        where on the line the next blank starts.

        A tab is a cursor move, not advance width: it carries the cursor to the
        next line-relative tab interval, which is what the emitter's own tab
        stops are measured from.
        """

        size = max(1.0, float(font_size or 0.0))
        measure = max(1.0, float(measure_pt or 0.0))
        advance = 0.0
        for char in str(text or ""):
            if char == "\t":
                advance = (int(advance // 36.0) + 1) * 36.0
                continue
            width = self._form_advance_width(char, size)
            if advance + width > measure and advance > 0.0:
                advance = 0.0
            advance += width
        return advance

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

    def _start_source_form_line_paragraph(self, paragraph, source, span=None,
                                          *, isolation_reason=None):
        """Begin a SOURCE_FORM_LINE_PARAGRAPH for the next source form line.

        A source visual form line that carries its own rule needs its own Word
        paragraph coordinate context: a line break does not create one, so the
        next line would inherit this paragraph's tab stops and indents.  This
        opens a fresh paragraph through the normal python-docx API instead.

        ``isolation_reason`` names *why* the context is required, so an isolated
        row is never indistinguishable from an unnecessary split.  The default
        reason is the resolved-reflow one: a positioned atom whose anchor the
        cursor has already passed, which no forward tab can reach.
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
            "isolation_reason": (
                isolation_reason
                or "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"
            ),
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
            # The pointer marks where the line the cursor is *on* begins, so it
            # starts after the paragraph's last explicit break.  Text already
            # emitted into this paragraph - the label a form rule follows - has
            # moved the cursor and must count: reading the pointer as the current
            # text length would measure a zero advance and emit an anchor tab for
            # a rule the cursor is already standing on, which is what makes Word
            # skip that stop and paint the blank's leader somewhere else.
            self._positioned_paragraph = paragraph
            self._positioned_paragraph_start = paragraph_so_far.rfind("\n") + 1
        paragraph_so_far = paragraph_so_far[self._positioned_paragraph_start:]
        current_line = paragraph_so_far.rsplit("\n", 1)[-1]
        emitted = self._form_advance_width(current_line.replace("\t", ""), size)
        # The declared paragraph coordinate frame: the ruler a paragraph's tab
        # stops are laid out on follows the section text margin, while the text of
        # a first line also carries its first-line indent.  For deciding whether
        # the cursor has already passed the rule, the origin of the line the
        # cursor is *on* is what matters - the first line carries the first-line
        # indent, a line opened by an explicit break does not - so the two frames
        # are read through one helper that both this path and the anchor
        # decisions share, and a form-layout break re-reads it after clearing the
        # first-line indent.
        frame = paragraph_coordinate_frame(paragraph, blank_x0, blank_x1)
        margin = self._cursor_line_origin(paragraph, frame)
        row_owns_line_context = bool(
            getattr(self, "_row_owns_line_context", False)
        )
        if (
            "\n" not in paragraph_so_far
            and not row_owns_line_context
            and int(getattr(self, "_current_source_visual_row_count", 1) or 1) > 1
        ):
            # The element is one Word paragraph built from several source rows, so
            # the cursor is not at the end of everything written into it: Word
            # wrapped the text, and what is left on the line the cursor stands on
            # is the flow's own position.  Measuring the whole text would report a
            # cursor past the page and force every blank of the element - including
            # the ones the flow has not reached yet - onto a cursor-only
            # representation the source's own rule start never asked for.
            emitted = self._flowed_cursor_advance(
                current_line,
                size,
                max(1.0, float(page_content_x1) - margin),
            )
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
        # paragraph's own origin, where the stops are measured from - and a fresh
        # line is only ever *needed* when the cursor has already moved past the
        # blank's own source start.  A cursor that has not yet reached the rule
        # can still be carried onto it by the rule's own tab stop, which is the
        # ordinary representation every other positioned blank in the document
        # already uses.
        #
        # Breaking on "the line already carries text" instead measured the
        # paragraph rather than the source row: a source form row that draws its
        # label, its fill rule and its trailing suffix on ONE visual row has text
        # on the line well before the rule is reached, so breaking there moved the
        # rule and the suffix onto a second line the source never drew.  The row
        # is the authority, so the emitter starts the blank's own form line only
        # when the row cannot reach it.  This is the narrow
        # SOURCE_FORM_LAYOUT_LINE remedy, limited to lines that carry a real
        # fillable field, and it uses only a Word line break.
        form_line_break = False
        reach = margin + emitted
        managed = id(paragraph) in getattr(self, "_form_line_managed_paragraphs", set())
        # A table cell's lines are the source's own: the cell is a fixed-width box
        # the source wrapped, and the breaks inside it are the cell's line
        # structure, not the paragraph's.  Starting a blank's own form line there
        # would add a line the source never drew - one per positioned blank - so a
        # cell paragraph keeps its own lines and reaches each blank with its own
        # source-derived tab.
        in_table_cell = bool(getattr(self, "_cell_paragraph_depth", 0))
        # The cursor only moves forward, so a forward tab reaches every blank
        # whose own source start is still at or ahead of it; the one geometric
        # situation no tab can repair is a rule that starts behind the cursor.
        blank_starts_behind_cursor = blank_x0 + 1.0 < reach
        if not managed and not in_table_cell and blank_starts_behind_cursor:
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
                        "the source form row's own fill rule starts behind the "
                        "cursor this paragraph has already reached, so a forward "
                        "tab cannot carry the blank and the rule opens its own "
                        "source form line"
                    ),
                }
            )
            emitted = 0.0
            reach = margin
        if blank_x0 + 1.0 < reach:
            # The rule lies on a source row the delivered paragraph has already
            # flowed past.  A paragraph reconstructed from several source rows
            # wraps by Word's own rules, so the row-local x of a rule inside it
            # is not reachable by any tab stop - and starting the rule's own
            # form line would put a hard break inside flowing prose the source
            # never broke.  The blank's *width* is what the delivery owns, so a
            # mid-row blank of a flowing source line is emitted inline at the
            # cursor through the representation an inline blank already uses.
            if flow_cursor_blank_representation(
                in_table_cell,
                getattr(self, "_current_source_visual_row_count", 1),
            ) and not row_owns_line_context:
                width = blank_x1 - blank_x0
                # The blank's width is the source rule's own width, and the flow
                # owns where the cursor stands: an inline run of figure spaces -
                # corrected by the run's own character spacing - carries that width
                # with it.  A leader tab would instead measure from wherever Word
                # actually broke the line to an absolute stop, which the flowed
                # cursor estimate cannot place exactly.
                self._inline_blank_run(
                    paragraph,
                    width,
                    source,
                    semantic_slot=blank.semantic_slot,
                    source_locator=blank.source_locator,
                    page_content_x0=page_content_x0,
                    page_content_x1=page_content_x1,
                )
                self.flow_inline_blank_count += 1
                self.positioned_blank_records.append(
                    {
                        "emission_id": "SOURCE_INLINE_BLANK_AT_FLOW_CURSOR|p%s|%.2f-%.2f"
                        % (source_rule_page, blank_x0, blank_x1),
                        "semantic_slot": blank.semantic_slot,
                        "source_rule_id": source_rule_id,
                        "source_page": source_rule_page,
                        "source_x0": round(blank_x0, 2),
                        "source_x1": round(blank_x1, 2),
                        "source_span_pt": round(width, 2),
                        "paragraph_origin_pt": round(margin, 2),
                        "form_layout_line_break": False,
                        "cursor_origin_pt": round(margin, 2),
                        "emitted_advance_pt": round(emitted, 2),
                        "reach_pt": round(reach, 2),
                        "representation_kind": (
                            blank.representation_kind.value
                            if hasattr(blank.representation_kind, "value")
                            else str(blank.representation_kind)
                        ),
                        "emission_mechanism": "SOURCE_INLINE_BLANK_AT_FLOW_CURSOR",
                        "reason": (
                            "the source row wrapped inside the delivered "
                            "paragraph, so the rule's own x is unreachable; the "
                            "blank keeps the source's width at the flow cursor"
                        ),
                    }
                )
                return blank_x1
            self.positioned_blank_records.append(
                {
                    "emission_id": "POSITIONED_BLANK_UNREACHABLE|p%s|%.2f-%.2f"
                    % (
                        getattr(
                            getattr(blank, "source_locator", None), "page", None
                        ),
                        blank_x0,
                        blank_x1,
                    ),
                    "semantic_slot": blank.semantic_slot,
                    "source_rule_id": getattr(blank, "source_rule_id", None),
                    "source_x0": round(blank_x0, 2),
                    "source_x1": round(blank_x1, 2),
                    "source_span_pt": round(blank_x1 - blank_x0, 2),
                    "emission_mechanism": "SOURCE_POSITIONED_UNREACHABLE",
                    "reach_pt": round(reach, 2),
                    "overshoot_pt": round(reach - blank_x0, 2),
                    "reason": "source rule lies left of the emitted flow position",
                    "source_page": source_rule_page,
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
                "emission_id": "POSITIONED_BLANK|p%s|%.2f-%.2f"
                % (source_rule_page, blank_x0, blank_x1),
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
                #: The flow position the anchor decision was made from.  A blank
                #: whose rule starts at or behind it needs no anchor tab, and
                #: emitting one there is what makes Word skip the stop and paint
                #: the leader somewhere else, so the evidence is recorded.
                "cursor_origin_pt": round(margin, 2),
                "emitted_advance_pt": round(emitted, 2),
                "cursor_text_tail": str(
                    paragraph_so_far.rsplit("\n", 1)[-1].replace("\t", "")
                )[-40:],
                "reach_pt": round(reach, 2),
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
        #: A FIGURE SPACE carries the font's own digit advance, half an em in the
        #: source fonts this emitter reads, so a whole number of them can only
        #: approximate an arbitrary rule span.  The run's character spacing carries
        #: the remainder, so what the page paints is the source's width rather than
        #: the nearest count of a glyph whose advance the emitter cannot read.
        advance=max(1.0, size*FIGURE_SPACE_ADVANCE_RATIO)
        count=max(2, int(round(float(width_pt)/advance)))
        spacing=(float(width_pt)-count*advance)/count
        if abs(spacing) > MAX_INLINE_BLANK_SPACING_PT:
            count=max(2, int(float(width_pt)//advance))
            spacing=(float(width_pt)-count*advance)/count
        # FIGURE SPACE is a Word-visible underlined glyph, unlike a trailing
        # ordinary-space run, and is deliberately not an NBSP placeholder.
        self._add_run(
            paragraph,
            '\u2007'*count,
            source,
            underline=True,
            spacing_pt=spacing,
        )
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
                                 evidence=None, source=None):
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

    def _render_inline_tokens(self, paragraph, text, runs, slots, *, flow=False,
                              source_rows=None):
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
                paragraph, text, composition, runs, slots, flow=flow,
                source_rows=source_rows,
            )
        if blank is None:
            return False
        return self._render_blank_atom(
            paragraph, text, blank, runs, slots, flow=flow, source_rows=source_rows
        )

    def _render_composition_atom(
        self, paragraph, text, composition, runs, slots, *, flow=False,
        source_rows=None,
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
            self.text(paragraph, before, runs, before_slots, flow=flow,
                      source_rows=source_rows)
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
            # an empty rule segment paints from its own source anchor.  A new
            # paragraph context is opened for it ONLY when the anchor is already
            # behind the emission cursor, because a tab can never move backwards.
            #
            # FORWARD_REACHABLE_SAME_ROW: when the anchor is still at or ahead of
            # the cursor, continuous flow reaches it with the atom's own
            # source-derived anchor tab, so the row stays the one Word paragraph
            # the source drew.  Opening a paragraph there splits one source visual
            # line into two for no geometric reason - exactly the clause
            # ``4、本项目询比有效期为提交响应文件截止之日起90日历天…`` defect, whose
            # fixed leading text ends precisely at its own rule anchor.
            #
            # STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW: a genuinely
            # backwards anchor keeps a paragraph of its own, because the resolved
            # reflow carried the cursor past the source anchor and the source
            # geometry could not otherwise be preserved.
            #
            # A row the assembler already gave a paragraph context keeps it: it is
            # the same one context.
            promoted = False
            if (
                getattr(self, "_source_form_line_mode", False)
                and getattr(self, "_form_line_paragraph_factory", None) is not None
                and segments
                and segments[0]["segment_type"] == "EMPTY_RULE_SEGMENT"
                and not getattr(self, "_form_line_composition_split", False)
                and paragraph is not getattr(self, "_row_context_paragraph", None)
                and self._isolated_row_is_its_own_source_line()
                and self._anchor_behind(
                    paragraph,
                    segments[0]["source_x0"],
                    segments[-1]["source_x1"],
                    max(6.0, float(getattr(source, "font_size", 0) or 10.5)),
                )
            ):
                paragraph = self._start_source_form_line_paragraph(
                    paragraph, source,
                    span=(segments[0]["source_x0"], segments[-1]["source_x1"]),
                    isolation_reason="STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW",
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
                segments[0]["reachability"] = (
                    "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"
                    if promoted
                    else "FORWARD_REACHABLE_SAME_ROW"
                )
            self._render_rule_composition(
                paragraph, source_rule_id, segments, evidence, source
            )
        if after:
            self.text(composed_paragraph, after, runs, after_slots, flow=flow,
                      source_rows=source_rows)
        return True

    def _render_blank_atom(self, paragraph, text, match, runs, slots, *, flow=False,
                           source_rows=None):
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
            self.text(paragraph,before,runs,before_slots,flow=flow,
                      source_rows=source_rows)
        source=next((run for run in runs if run.text.strip()),None)
        parsed = parse_inline_blank_token(match.group(1))
        width, span_x0, span_x1 = parsed if parsed else (1.0, 0.0, 1.0)
        # SOURCE_FORM_LINE_PARAGRAPH: a source visual form line that owns its own
        # rule gets an independent Word paragraph, so it cannot inherit the
        # previous form line's tab stops or indents.  Only the dedicated
        # form-line path does this; everything else keeps one flowing paragraph.
        # A row the assembler already opened a paragraph for keeps that context.
        #
        # FORWARD_REACHABLE_SAME_ROW: the same generic rule as a composed rule
        # applies - a blank whose own anchor is still at or ahead of the cursor is
        # reached with its own source-derived tab inside the current paragraph, so
        # it does not open a second paragraph for one source visual line.
        # STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW: a backwards anchor
        # keeps a paragraph of its own, because a tab cannot move left.
        if getattr(self, "_source_form_line_mode", False) and getattr(
            self, "_form_line_paragraph_factory", None
        ) is not None:
            if (
                paragraph is not getattr(self, "_row_context_paragraph", None)
                and self._form_line_has_content
                and self._isolated_row_is_its_own_source_line()
                and not self._same_split_line(span_x0, span_x1)
                and not self._same_source_line_rule(span_x0, span_x1)
                and self._anchor_behind(
                    paragraph, span_x0, span_x1,
                    max(6.0, float(getattr(source, "font_size", 0) or 10.5)),
                )
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
                after,runs,after_slots,flow=flow,source_rows=source_rows,
            )
        return True

    def _isolated_row_is_its_own_source_line(self) -> bool:
        """Whether the row being emitted is the whole source paragraph.

        ``STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW`` buys exact geometry
        for a row by giving it a Word paragraph of its own, which is only honest
        when the source drew that row as a line of its own.  A row that is merely
        one of a flowing paragraph's wrapped rows is not a line break in the
        source, so promoting it would turn the source's own wrapping into hard
        paragraph breaks the reader can see - and it would strand the rest of the
        paragraph in fragments that can never reflow as one text.  A backwards
        anchor inside such a paragraph is delivered by flow instead: the row stays
        in its paragraph, and the rule's own segments decide what can still be
        reached.
        """

        return int(getattr(self, "_current_source_visual_row_count", 1) or 1) <= 1

    def _cursor_estimate(self, paragraph, source_x0, source_x1, size):
        """``(current_line_origin_x, emitted_advance_pt)`` for one paragraph.

        The estimate is the same source-derived one the positioned blank path
        uses: the modelled advance width of the text already emitted on this
        paragraph's line, measured from the paragraph's own tab-stop reference
        origin.  Both the anchor-ahead and the anchor-behind decision read this
        one estimate, so the two can never disagree about where the cursor is.
        """

        frame = paragraph_coordinate_frame(
            paragraph, float(source_x0), float(source_x1)
        )
        emitted = self._form_advance_width(
            str(paragraph.text or "").rsplit("\n", 1)[-1].replace("\t", ""),
            max(6.0, float(size or 10.5)),
        )
        return self._cursor_line_origin(paragraph, frame), float(emitted)

    def _cursor_line_origin(self, paragraph, frame) -> float:
        """Where the line the cursor is on actually starts.

        The paragraph's *first* line carries its first-line offset; a line the
        emitter opened with an explicit break does not.  The coordinate frame
        declares both, and reading the wrong one mis-estimates the cursor by the
        whole first-line offset - which is exactly the width that decides whether
        an anchor is still ahead of it.
        """

        if "\n" in str(paragraph.text or ""):
            return float(frame.current_line_origin_x)
        return float(frame.effective_line_origin_x)

    def _anchor_ahead(self, paragraph, source_x0, source_x1, size):
        """Whether a positioned rule's start is still ahead of the cursor.

        A rule whose anchor is already behind the cursor is left to the paragraph
        context instead, so no backwards tab is ever emitted.
        """

        try:
            origin, emitted = self._cursor_estimate(
                paragraph, source_x0, source_x1, size
            )
        except Exception:  # pragma: no cover - defensive geometry boundary
            return False
        return float(source_x0) > origin + emitted + 1.0

    def _anchor_behind(self, paragraph, source_x0, source_x1, size) -> bool:
        """Whether a positioned rule's start is already behind the cursor.

        This is the ONLY condition that authorises a positioned atom to open its
        own Word paragraph context.  Continuous forward flow can reach an anchor
        that is still at or ahead of the cursor with the atom's own source-derived
        tab, so isolating that atom would split one source visual line across two
        paragraphs for no geometric reason.  A genuinely backwards anchor cannot
        be reached by a tab - the cursor only moves forward - so that row keeps a
        paragraph context of its own, classified
        ``STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW``.
        """

        if not hasattr(self, "_cursor_estimate"):
            return False
        try:
            origin, emitted = self._cursor_estimate(
                paragraph, source_x0, source_x1, size
            )
        except Exception:  # pragma: no cover - defensive geometry boundary
            return False
        return float(source_x0) < origin + emitted - 1.0

    def is_forward_reachable(self, paragraph, source_x0, source_x1, size) -> bool:
        """Public predicate: a positioned atom that needs no own paragraph."""

        return not self._anchor_behind(paragraph, source_x0, source_x1, size)

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

    def _apply_source_value_anchor(self, paragraph, slot, rule, value, *, runs=None, text=None):
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
            "underline_semantics": (
                "SOURCE_PLACEHOLDER_DECORATION_INHERITED_BY_VALUE"
                if self._slot_inherits_source_decoration(slot, runs, text)
                else "VALUE_SUPPLIES_CONTENT_ONLY"
            ),
            "source_placeholder_underlined": self._slot_inherits_source_decoration(
                slot, runs, text
            ),
            "resolved_value_underlined": self._slot_inherits_source_decoration(
                slot, runs, text
            ),
            "source_local_pattern": (
                "source field rule under its own placeholder text; the delivered "
                "value replaces that placeholder at the field's start anchor and "
                "follows natural glyph width"
            ),
            "evidence_reason": (
                "the source rule extent is occupied by the placeholder glyphs, so the rule "
                "decorates the semantic slot; the value that replaces the placeholder inherits "
                "that decoration, and the fixed prose around it keeps only its own decoration"
                if self._slot_inherits_source_decoration(slot, runs, text)
                else (
                    "the source rule extent is occupied by the placeholder glyphs, so "
                    "the rule belongs to the placeholder text; the frozen fill pattern "
                    "makes the delivered value supply content only, so no underline is "
                    "invented for it and none is required to satisfy this geometry"
                )
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

    @staticmethod
    def _flow_segment_text(segment, flow, source_rows=None):
        """The delivered text of one run-sized source segment.

        ``flow`` joins the extraction's own line separators, because a source page
        may draw one visual row as several text objects and the newline between
        them is a property of the extraction rather than a line the source drew.
        A container that hands over its own source rows - a table cell whose text
        spans several of them - keeps the separators *between* rows, so the cell's
        internal line structure survives into Word as the line breaks the source
        drew instead of collapsing into one wrapped line.
        """

        if not flow:
            return segment
        if source_rows:
            joined, _removed = single_visual_row_join(segment, source_rows)
            return joined
        return join_visual_lines(segment)

    def _source_form_field_slot_ids(self, runs, text, slots) -> frozenset:
        """Slot ids the source's own rule decorates as a whole placeholder field.

        Base contract: an emitter without a source rule registry claims no such
        slot, so every placeholder keeps the accepted plain substitution.  The
        style-first builder, which owns the registry, resolves the claim from the
        source's own measured rule geometry.
        """

        return frozenset()

    def text(self, paragraph, text, runs, slots, *, flow=False, source_rows=None):
        if self._render_inline_tokens(paragraph,text,runs,slots,flow=flow,
                                      source_rows=source_rows):
            return
        source_form_fields = self._source_form_field_slot_ids(runs, text, slots)
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
            replacement = slot_replacement(
                slot,
                self.facts,
                source_form_field=str(getattr(slot, "slot_id", "")) in source_form_fields,
            )
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
                    self._add_run(paragraph, self._flow_segment_text(segment, flow, source_rows), styles[start])
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
            inherits_slot_decoration = self._slot_inherits_source_decoration(
                slot, runs, text
            )
            keep_underline = bool(slot.destination_style.underline) or bool(
                getattr(fill_pattern, "value_is_underlined", False)
            ) or inherits_slot_decoration
            self.fill_pattern_usage['filled_slots'] += 1
            if fill_pattern is not None:
                self.fill_pattern_usage['pattern_matched'] += 1
            self.fill_pattern_usage[
                'value_kept_source_underline' if keep_underline else 'value_plain_whitespace'
            ] += 1
            if inherits_slot_decoration:
                # The source decorates the placeholder itself, so the delivered
                # value inherits that decoration while the fixed prose around it
                # keeps only its own source decoration.
                self.fill_pattern_usage['value_inherited_source_slot_underline'] = (
                    self.fill_pattern_usage.get('value_inherited_source_slot_underline', 0) + 1
                )
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
        # The source table's left edge is where the indent below places it.
        table_left = float(source.bbox[0])
        page_width = float(
            getattr(getattr(doc.sections[-1], "page_width", None), "pt", 0.0) or 0.0
        )
        target_total, available, clamped_to_page = plan_table_width(
            preferred,
            table_left=table_left,
            usable=float(usable),
            page_width=page_width,
        )
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
        self.table_geometry_records.append({
            "source_page": int(getattr(source, "page", 0) or 0),
            "table_index": int(getattr(source, "table_index", 0) or 0),
            "rows": int(rows),
            "columns": int(cols),
            "source_x0": round(float(source.bbox[0]), 2),
            "source_x1": round(float(source.bbox[2]), 2),
            "source_height_pt": round(
                float(source.bbox[3]) - float(source.bbox[1]), 2),
            "section_left_margin": round(left_margin, 2),
            "table_indent_pt": round(float(source.bbox[0]) - left_margin, 2),
            "source_width_pt": round(preferred, 2),
            "rendered_width_pt": round(target_total, 2),
            "rendered_x1_pt": round(table_left + target_total, 2),
            "page_available_width_pt": round(available, 2),
            "clamped_to_page": bool(clamped_to_page),
            "width_matches_source": bool(not clamped_to_page),
            "source_column_widths": [round(float(w), 2) for w in widths],
            "rendered_column_widths": [round(float(w), 2) for w in column_pt],
            "source_row_heights_pt": [round(float(h), 2) for h in source.row_heights],
        })
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
                sizes = [r.font_size for r in source_cell.runs if r.font_size > 0]
                table_size = max(sizes or [10.5])
                # THE CELL'S OWN RHYTHM, MEASURED.  A cell that drew several
                # source lines states its own baseline pitch, and the Word line
                # spacing must reproduce that pitch.  Passing a ratio chosen for
                # the cell instead (``table_size * 1.05``) is not a measurement:
                # it lands inside the single-spacing tolerance by construction,
                # so every multi-line cell was silently delivered single-spaced
                # however far apart the source set its lines.
                table_pitch = self._cell_source_line_pitch(
                    self._cell_source_rows(source_cell)
                )
                single_spacing = infer_semantic_line_spacing(
                    table_size,
                    table_pitch if table_pitch > 0.0 else table_size * 1.05,
                    source_locator=source_cell.locator,
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
                cell_text, cell_slots, cell_runs = self._cell_source_text(
                    source_cell, slots
                )
                # ONE PARAGRAPH PER SOURCE LINE.  A cell that drew several lines
                # is several source lines, not one paragraph with forced breaks:
                # one ``w:line`` over a break-separated run can only reproduce a
                # single pitch, so a cell whose lines were set at two different
                # distances was delivered uniformly spaced and every interval
                # after the first was wrong - the delivered summary cell rendered
                # 17.60/17.60 for source pitches of 23.40 and 19.44 pt.  Native
                # paragraphs let each line carry its own measured pitch, keep the
                # cell one editable container of ordinary text, and need no
                # ``w:br`` at all.
                line_groups = self._cell_line_groups(source_cell, cell_text, cell_slots)
                if line_groups:
                    self.builder_note_cell_split(len(line_groups))
                    for index, (text, runs, line_slots, pitch) in enumerate(line_groups):
                        paragraph = p if index == 0 else cell.add_paragraph()
                        spacing = auto_line_multiple_for_pitch(table_size, pitch)
                        self._configure_cell_paragraph(
                            paragraph,
                            single_spacing if spacing is None else spacing,
                            p.alignment,
                        )
                        self._emit_cell_paragraph(paragraph, text, runs, line_slots)
                else:
                    self._configure_cell_paragraph(p, single_spacing, p.alignment)
                    self._emit_cell_paragraph(p, cell_text, cell_runs, cell_slots)

    def builder_note_cell_split(self, line_count: int) -> None:
        """Record that a table cell was emitted as its own source lines."""

        owner = getattr(self, 'builder', None) or self
        usage = getattr(owner, 'tab_stop_usage', None)
        if usage is None:
            usage = {}
            try:
                owner.tab_stop_usage = usage
            except (AttributeError, TypeError):
                return
        usage['multi_line_cell_paragraph_splits'] = (
            usage.get('multi_line_cell_paragraph_splits', 0) + 1
        )
        usage['multi_line_cell_paragraph_count'] = (
            usage.get('multi_line_cell_paragraph_count', 0) + line_count
        )

    @staticmethod
    def _configure_cell_paragraph(paragraph, spacing, alignment) -> None:
        paragraph_format = paragraph.paragraph_format
        paragraph_format.space_after = Pt(0)
        paragraph_format.space_before = Pt(0)
        paragraph_format.first_line_indent = Pt(0)
        paragraph_format.left_indent = paragraph_format.right_indent = Pt(0)
        paragraph_format.line_spacing = spacing
        paragraph.alignment = alignment

    def _emit_cell_paragraph(self, paragraph, text, runs, slots) -> None:
        self._cell_paragraph_depth = getattr(self, "_cell_paragraph_depth", 0) + 1
        try:
            self.text(paragraph, text, runs, slots, flow=True, source_rows=runs)
        finally:
            self._cell_paragraph_depth = max(
                0, getattr(self, "_cell_paragraph_depth", 1) - 1
            )

    def _cell_line_groups(self, source_cell, cell_text, cell_slots):
        """``[(text, runs, slots, pitch_to_next_line)]`` for a multi-line cell.

        The split is taken only when the source proves it: the cell's own runs
        must group into exactly as many visual rows as the cell text has line
        separators, each run must appear in its own row's text in order, and no
        fill slot may straddle a boundary.  Anything else returns ``None`` and the
        cell keeps its single-paragraph emission, because guessing which side of a
        boundary a piece of text belongs to would move source text between lines.
        """

        runs = [
            run
            for run in getattr(source_cell, "runs", ()) or ()
            if getattr(run, "bbox", None)
        ]
        text = str(cell_text or "")
        if len(runs) < 2 or '\n' not in text:
            return None
        ordered = sorted(runs, key=lambda run: (float(run.bbox[1]), float(run.bbox[0])))
        groups = source_visual_rows(ordered)
        segments = text.split('\n')
        if len(groups) != len(segments):
            return None
        if any(not segment.strip() for segment in segments):
            return None
        offsets = []
        cursor = 0
        for segment in segments:
            offsets.append((cursor, cursor + len(segment)))
            cursor += len(segment) + 1
        line_runs = []
        for group, segment in zip(groups, segments):
            placed = []
            probe = 0
            for run in group:
                run_text = str(getattr(run, "text", "") or "")
                at = segment.find(run_text, probe) if run_text else -1
                if at < 0:
                    return None
                probe = at + len(run_text)
                placed.append(run)
            line_runs.append(placed)
        line_slots = [[] for _ in segments]
        for slot in cell_slots or ():
            start, end = slot.text_start, slot.text_end
            if start is None or end is None:
                continue
            for index, (line_start, line_end) in enumerate(offsets):
                if line_start <= start and end <= line_end:
                    line_slots[index].append(
                        slot.model_copy(
                            update={
                                'text_start': start - line_start,
                                'text_end': end - line_start,
                            }
                        )
                    )
                    break
                if start < line_end < end:
                    # A slot that spans a line boundary cannot be placed on one
                    # side of it without inventing a second slot.
                    return None
            else:
                return None
        tops = [min(float(run.bbox[1]) for run in group) for group in groups]
        return [
            (
                segments[index],
                line_runs[index],
                line_slots[index],
                (tops[index + 1] - tops[index]) if index + 1 < len(tops) else 0.0,
            )
            for index in range(len(segments))
        ]

    def _cell_source_text(self, source_cell, slots):
        """The text, slot offsets and runs a table cell is emitted from.

        A subclass may restore the rules the source drew *inside* the cell: the
        text gains the blanks those rules leave, and the runs may be split so the
        glyphs an underline covers carry it.  The base delivery emits the cell's
        own text and runs unchanged.
        """

        return source_cell.text, slots, source_cell.runs

    @staticmethod
    def _cell_source_rows(source_cell):
        """A table cell's own source visual lines, from its runs' geometry.

        A cell whose source drew several lines carries them as one newline-joined
        text; the cell's runs carry the line each piece was drawn on, so the
        separators that are row boundaries can be told from the separators a
        source page draws *inside* one row.  ``None`` when the cell is one row.
        """

        runs = [run for run in getattr(source_cell, "runs", ()) or () if getattr(run, "bbox", None)]
        if len(runs) < 2:
            return None
        runs = sorted(runs, key=lambda item: (float(item.bbox[1]), float(item.bbox[0])))
        rows = source_visual_rows(runs)
        return runs if len(rows) > 1 else None

    @staticmethod
    def _cell_source_line_pitch(source_rows):
        """The baseline pitch a source cell set its own lines in, measured.

        The pitch is the source's *dominant* gap, not its mean: a cell whose
        first line carries extra leading before it has one wide boundary gap
        and one rhythm gap, and the rhythm is what the line spacing must
        reproduce.  ``0.0`` when the cell drew a single line, which leaves the
        caller's single-line default in place.
        """

        if not source_rows:
            return 0.0
        rows = source_visual_rows(source_rows)
        tops = [
            min(float(getattr(run, "bbox", (0.0, 0.0, 0.0, 0.0))[1]) for run in group)
            for group in rows
        ]
        gaps = [later - earlier for earlier, later in zip(tops, tops[1:]) if later - earlier > 0.5]
        return dominant_line_pitch(gaps, default=0.0)

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

    def form_block(self, doc, block, *, page_content_x0=18.0, page_content_x1=None, scale=1.0, initial_space_before=0.0):
        """Render a FormBlock as paragraph-native Word form lines.

        The FormBlock is a semantic source grouping only.  Real PDF tables
        continue through :meth:`table`; ordinary form rows never call
        ``Document.add_table``.
        """
        if page_content_x1 is None:
            # The right body-frame edge is the page width minus the *right*
            # margin.  Deriving it as ``page_width - left_margin`` silently
            # assumed a symmetric section, which stopped being true once the
            # stable source page frame separated the two margins.
            section = doc.sections[-1]
            page_content_x1 = float(section.page_width.pt) - float(section.right_margin.pt)
        rendered = self.form_renderer.render_block(
            doc,
            block,
            page_content_x0=page_content_x0,
            page_content_x1=float(page_content_x1),
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

    def _record_block_rhythm(self, block, tops) -> None:
        """One source block's shared vertical rhythm, with its own evidence."""

        first_row = block.row_geometries[0] if block.row_geometries else None
        source_page = (
            getattr(getattr(first_row.item.source, "locator", None), "page", None)
            if first_row is not None
            else None
        )
        record = block_rhythm(
            tops,
            source_page=source_page,
            block_id="FORM_BLOCK_%s_%d" % (source_page, len(self.vertical_rhythm_blocks)),
            rhythm=self._rhythm,
        )
        self.vertical_rhythm_blocks.append(record)
        boundary_positions = {
            int(row_index) + 1 for row_index in record.block_gap_indices
        }
        for position, row in enumerate(block.row_geometries):
            self.vertical_rhythm_rows.append(
                {
                    "source_page": getattr(
                        getattr(row.item.source, "locator", None), "page", None
                    ),
                    "block_id": record.block_id,
                    "source_y": round(float(row.item.bbox[1]), 2),
                    "row_type": row.row_type,
                    "block_line_pitch_pt": round(float(record.line_pitch_pt), 2),
                    "is_block_boundary": position in boundary_positions,
                    "space_before_source_gap_pt": (
                        round(float(record.gaps[position - 1]), 2)
                        if 0 < position <= len(record.gaps)
                        else None
                    ),
                    "space_before_shared_pt": (
                        round(float(record.snapped_gaps[position - 1]), 2)
                        if 0 < position <= len(record.snapped_gaps)
                        else None
                    ),
                }
            )

    def _slot_value_presentation_report(self) -> dict:
        """Every composed slot value, component by component, with provenance.

        A composed value is never a single opaque string in the report: the
        resolved fact, the source's own separator and the source form's
        not-applicable marker each stay separately readable, so the marker can
        never be mistaken for a fact and no fact count is affected by it.
        """

        records = [
            {
                "slot_id": record.get("slot_id"),
                "source_page": record.get("source_page"),
                "generated_paragraph_index": record.get("generated_paragraph_index"),
                "value": record.get("value"),
                "method": record.get("method"),
                **record.get("value_presentation", {}),
            }
            for record in self.filled
            if record.get("value_presentation")
        ]
        marker_components = [
            component
            for record in records
            for component in record.get("components", ())
            if component.get("kind") == COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER
        ]
        return {
            "composed_slot_value_count": len(records),
            "records": records,
            "source_form_not_applicable_marker_count": len(marker_components),
            "source_form_not_applicable_markers": marker_components,
            "marker_is_a_fact": False,
            "marker_creates_a_fact_candidate": False,
            "note": (
                "the not-applicable marker is source form structure, not a value: "
                "the field it stands for keeps its own ProjectFacts status"
            ),
        }

    def _source_vertical_rhythm_report(self) -> dict:
        """The emitted vertical rhythm, with the source evidence behind it.

        The two emitted populations are reported separately and never mixed:

        ``repeated_form_row_*``
            The ``space_before`` of a form row that follows another row of the
            same source block.  These are the rows the shared rhythm governs, so
            ``distinct_row_spacing_values_before`` is what the superseded
            per-row absolute-y architecture would have written (one value per
            row) and ``..._after`` is what the shared rhythm actually wrote.

        ``layout_boundary_spacings``
            The ``space_before``/``space_after`` of a real source block
            boundary, which is authorised to keep its own measured gap.

        ``unexplained_custom_row_spacing_count_after`` is the number of repeated
        rows still carrying a spacing that no source-repeated level explains:
        zero means every repeated form row is spaced by a level the source itself
        repeats.
        """

        row_spacings = [
            round(float(row["space_before_shared_pt"]), 2)
            for row in self.vertical_rhythm_rows
            if row.get("space_before_shared_pt") is not None
        ]
        boundary_spacings = [
            round(float(record["shared_rhythm_pt"]), 2)
            for record in self.vertical_rhythm_expansions
        ]
        classes = [item.as_dict() for item in self._rhythm.classes]
        model = rhythm_metrics(
            before_values=self.vertical_rhythm_source_spacings,
            after_values=row_spacings,
            block_records=self.vertical_rhythm_blocks,
            heading_level_rows=self.vertical_rhythm_expansions,
            boundary_values=boundary_spacings,
            spacing_classes=classes,
        )
        unexplained = self._unexplained_row_spacing_rows(row_spacings, classes)
        model["unexplained_custom_row_spacing_count_after"] = len(unexplained)
        model["unexplained_custom_row_spacing_rows"] = unexplained
        model["unexplained_custom_row_spacing_evidence"] = (
            "a repeated form row whose written space_before is a one-off AND is "
            "not a spacing level at least two of the source's own measured row "
            "gaps share; zero means every one-off is source-evidenced"
        )
        return {
            **self._rhythm.as_dict(),
            "metrics": model,
            "source_spacing_population": [
                round(float(value), 2) for value in self.vertical_rhythm_source_spacings
            ],
            "source_spacing_levels": self._rhythm.distinct_values,
            "line_pitch_sample": [
                round(float(value), 2) for value in self.vertical_rhythm_line_pitch_sample
            ],
            "repeated_form_row_spacings": row_spacings,
            "layout_boundary_spacings": boundary_spacings,
            "blocks": [record.as_dict() for record in self.vertical_rhythm_blocks],
            "rows": self.vertical_rhythm_rows,
            "page_boundaries": self.vertical_rhythm_expansions,
            "model_note": (
                "consecutive rows of one source block share the source's own "
                "measured line pitch; only a gap large enough against that pitch "
                "to be a real block boundary keeps its own source gap"
            ),
        }

    def _source_row_gap_rows(self) -> list:
        """The per-row source gaps: the legacy architecture's value population."""

        return [round(float(gap), 2) for gap in self._source_gap_rows]

    def _unexplained_row_spacing_rows(self, row_spacings, classes) -> list:
        """Repeated rows whose written spacing no source-repeated level explains.

        A row is explained when its written ``space_before`` is a spacing level at
        least two of the source's own measured row gaps share - the row belongs
        to a rhythm the source itself repeats.  A row that is not is an arbitrary
        per-row compensation and is reported by its own coordinates.
        """

        shared = {
            round(float(item.get("value_pt")), 2)
            for item in classes
            if int(item.get("member_count", 0)) >= 2
        }
        counts: dict[float, int] = {}
        for value in row_spacings:
            counts[round(float(value), 2)] = counts.get(round(float(value), 2), 0) + 1
        unexplained = []
        for row in self.vertical_rhythm_rows:
            value = row.get("space_before_shared_pt")
            if value is None:
                continue
            value = round(float(value), 2)
            if counts.get(value, 0) > 1 or value in shared:
                continue
            unexplained.append(
                {
                    "source_page": row.get("source_page"),
                    "block_id": row.get("block_id"),
                    "row_type": row.get("row_type"),
                    "source_y": row.get("source_y"),
                    "space_before_shared_pt": value,
                    "source_gap_pt": row.get("space_before_source_gap_pt"),
                }
            )
        return unexplained

    def _prepare_source_vertical_rhythm(self) -> None:
        """Sample the source's own vertical rhythm once, before emission.

        The sampled population is *exactly* the gap population the emitter will
        produce: the same page top, the same per-element cursor advance rule and
        the same per-page scale.  That is what makes a paragraph's ``space_before``
        a lookup into a shared model rather than a re-derivation, and it is what
        lets a sub-line artefact be recognised as an artefact instead of being
        measured into a boundary of its own.
        """

        gaps: list[float] = []
        row_gaps: list[float] = []
        line_pitch_sample: list[float] = []
        for page, layout in zip(self.template.source_pages, self.layouts):
            scale = self.page_scales.get(page.page, 1.0)
            cursor_y = self._rhythm_page_top(page, layout)
            for item in layout.elements:
                gaps.append(
                    round(max(0.0, float(item.bbox[1]) - cursor_y) * scale, 3)
                )
                if isinstance(item, FormBlock):
                    tops = [float(row.item.bbox[1]) for row in item.row_geometries]
                    block_row_gaps = [
                        round((later - earlier) * scale, 3)
                        for earlier, later in zip(tops, tops[1:])
                        if later - earlier > 0.0
                    ]
                    gaps.extend(block_row_gaps)
                    row_gaps.extend(block_row_gaps)
                elif isinstance(item, LogicalParagraph) and item.line_pitch_pt:
                    # A paragraph's own measured line pitch is a line-like sample
                    # of the same rhythm a form row advances by.
                    line_pitch_sample.append(round(float(item.line_pitch_pt) * scale, 3))
                cursor_y = self._source_element_cursor(item, cursor_y, scale)
        self._source_gap_population = tuple(sorted(set(gaps)))
        # The superseded architecture wrote one ``space_before`` per repeated form
        # row, taken from that row's own absolute y offset, so the honest "before"
        # population is the *raw* per-row gap list - duplicates and all.  Page
        # element boundaries are a separate population and are reported as such.
        self._source_gap_rows = tuple(row_gaps)
        self.vertical_rhythm_source_spacings = [
            round(float(gap), 2) for gap in self._source_gap_rows
        ]
        self.vertical_rhythm_line_pitch_sample = tuple(
            sorted(set(row_gaps + line_pitch_sample))
        )
        self._rhythm = SourceVerticalRhythm(
            gaps, pitch_sample=list(row_gaps) + line_pitch_sample
        )

    def _rhythm_page_top(self, page, layout) -> float:
        """The y the page's first element is measured from.

        The emitter starts a page at its source section frame's own body top, so
        the sampler uses the same value; a caller with no frame falls back to the
        page's content top.
        """

        frames = getattr(self, "section_frames", None) or {}
        frame = frames.get(page.page) if hasattr(frames, "get") else None
        if frame is not None:
            return float(frame.top_body_frame)
        return float(layout.content_box[1])

    def _source_element_cursor(self, item, cursor_y, scale) -> float:
        """Where the emission cursor stands after ``item``.

        A logical paragraph advances the cursor by its own modelled visual line
        count, because a source element's bounding box bottom is not the end of
        its rendered lines.  Everything else advances to the furthest content
        already emitted: a form block's rows can end above its declared extent,
        and letting the cursor move backwards there would silently shrink the next
        real source boundary into a clamp.
        """

        if isinstance(item, LogicalParagraph):
            visual_rows = len({round(line.bbox[1], 0) for line in item.source_lines}) or 1
            return float(item.bbox[1]) + visual_rows * float(item.line_pitch_pt) * scale
        return max(float(cursor_y), float(item.bbox[3]))

    def _build_source_vertical_rhythm(self) -> SourceVerticalRhythm:
        self._prepare_source_vertical_rhythm()
        return self._rhythm

    def _page_vertical_space(self, source_gap, *, page, position):
        """The shared rhythm spacing for a page-level source gap.

        A page's element boundary is the same concept as a block boundary: when
        the source itself shows a gap, that gap is a block boundary and keeps its
        own evidence; the recorded value is the shared rhythm spacing it belongs
        to, so repeated boundaries across the delivery share one value.
        """

        value = self._rhythm.snap(max(0.0, float(source_gap)))
        self.vertical_rhythm_expansions.append(
            {
                "source_page": page,
                "position": position,
                "source_gap_pt": round(max(0.0, float(source_gap)), 2),
                "shared_rhythm_pt": round(value, 2),
                "evidence": "SOURCE_ELEMENT_BOUNDARY_GAP",
            }
        )
        return value

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
            for position, item in enumerate(layout.elements):
                # SHARED VERTICAL RHYTHM.  The page's element boundary gap is
                # snapped to the source's own shared spacing, and the cursor is
                # the bottom of the furthest content already emitted.  Letting it
                # move backwards - which a form block whose rows end above its
                # own declared extent used to do - silently shrank the next real
                # source boundary into a clamp.
                gap = self._page_vertical_space(
                    max(0, item.bbox[1] - cursor_y) * scale,
                    page=page.page,
                    position=position,
                )
                if isinstance(item, FormBlock):
                    last_paragraph = self.form_block(
                        doc,
                        item,
                        page_content_x0=page_content_x0,
                        scale=scale,
                        initial_space_before=gap,
                    )
                    cursor_y = max(cursor_y, item.bbox[3])
                elif not isinstance(item, LogicalParagraph):
                    source = item
                    if last_paragraph is not None:
                        last_paragraph.paragraph_format.space_after = Pt(gap)
                    if (source.page, source.table_index) in self.logical_plan.continuation_map:
                        # This fragment is a continuation of the logical table
                        # already emitted at the page seam; its content lives in
                        # that table, so it must not become its own table.
                        cursor_y = max(cursor_y, source.bbox[3])
                        last_paragraph = None
                        continue
                    self.table(
                        doc,
                        self.logical_plan.table_for(source.page, source.table_index) or source,
                        usable,
                        page_content_x0=page_content_x0,
                    )
                    cursor_y = max(cursor_y, source.bbox[3])
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
                    # The paragraph's classified source indent, through the same
                    # implementation the style-first builder uses.  A centred
                    # block deliberately has no positioning indent; ordinary
                    # left-aligned text uses the body boundary the source returns
                    # its wrapped rows to, with the source's own first-line offset.
                    self._apply_source_paragraph_indent(pf, item, page_content_x0)
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
                    # A paragraph's first line carries its own first-line offset,
                    # so the delivered line that starts at the source's first row
                    # is ``left_indent + first_line_indent``.  Measuring only the
                    # left indent reports a first-line indent as a horizontal
                    # error exactly as wide as itself.
                    generated_x = page_content_x0 + (
                        float(pf.left_indent.pt or 0.0)
                        + float(pf.first_line_indent.pt or 0.0)
                    )
                    source_first_row_x = (
                        float(item.source_lines[0].bbox[0])
                        if item.source_lines
                        else float(item.bbox[0])
                    )
                    self.paragraph_x_errors.append(
                        abs(generated_x - source_first_row_x)
                        if item.alignment_hint != 'center' else 0.0
                    )
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
                        'source_indent':(item.source_indent.as_dict()
                            if getattr(item,'source_indent',None) is not None else None),
                        'layout_role':role.value,
                        'container_x0':paragraph_layout.container_x0,
                        'container_x1':paragraph_layout.container_x1,
                        'source_x':source_anchor,
                        'generated_left_indent':paragraph_layout.left_indent_pt,
                        'source_y':item.bbox[1],
                        'space_before':paragraph_layout.space_before_pt,
                        'tab_stops':[],
                        'x_error_pt':self.paragraph_x_errors[-1],
                        'source_first_row_x':round(source_first_row_x,4),
                        'generated_first_line_x':round(generated_x,4),
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
                  'source_vertical_rhythm': self._source_vertical_rhythm_report(),
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
                  'flow_inline_blank_count': self.flow_inline_blank_count,
                  'fill_slots_detected': len(self.template.fill_slots), 'fill_slots_filled': len(self.filled),
                  'fill_slots_left_blank': len(self.template.fill_slots)-len(self.filled), 'filled_slots': self.filled,
                  'slot_value_presentations': self._slot_value_presentation_report(),
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
                  'table_geometry_records': self.table_geometry_records,
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
