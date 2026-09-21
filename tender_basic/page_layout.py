"""Small PDF-geometry layout layer. No facts, package XML or review logic.

Offsets always refer to the unmodified source container, so layout joining
cannot accidentally redirect a validated fill slot to a different substring.
"""
from dataclasses import dataclass, field
from enum import Enum
from statistics import median
import re


ITEM = re.compile(r'^\s*(?:附[表件录][一二三四五六七八九十\d]+|[一二三四五六七八九十]+[、．.]|\d+[、.)）]|[（(]\d+[)）]|[①-⑳])')
FORM_LABELS = ('法定代表人或其委托代理人','法定代表人或委托代理人','供应商名称','投标人名称',
    '法定代表人','委托代理人','授权代表','投标单位','供应商','投标人','单位性质','成立时间','经营期限',
    '邮政编码','开户银行','地址','网址','电话','传真','账号','姓名','性别','年龄','职务','日期','电传',
    '身份证号码','项目编号','投标单位全称','法定代表人或授权代表','法定代表人或授权委托人',
    '法定代表人（单位负责人）或其委托代理人')
FORM_ANCHOR = re.compile('(?:'+'|'.join(r'\s*'.join(re.escape(c) for c in label) for label in FORM_LABELS)+r')(?:\s*[（(][^()（）\r\n]{0,15}[）)])?\s*[：:]')
FORM = re.compile(r'^\s*'+FORM_ANCHOR.pattern)
TERMINAL = re.compile(r'[。！？；：?!][）)"”]*\s*$')


@dataclass(frozen=True)
class LayoutContainer:
    container_x0: float
    container_x1: float

    @property
    def container_width(self):
        return self.container_x1-self.container_x0


class EditableBlankKind(str, Enum):
    FORM_BLANK = 'FORM_BLANK'
    INLINE_BLANK = 'INLINE_BLANK'
    DATE_BLANK = 'DATE_BLANK'
    SOURCE_EMPTY = 'SOURCE_EMPTY'
    FIXED_VALUE = 'FIXED_VALUE'


class EditableBlankRenderStyle(str, Enum):
    BOTTOM_RULE = 'BOTTOM_RULE'
    UNDERLINED_INLINE = 'UNDERLINED_INLINE'
    PLAIN_EMPTY = 'PLAIN_EMPTY'


class BlankRepresentationKind(str, Enum):
    LITERAL_UNDERSCORES = "LITERAL_UNDERSCORES"
    UNDERLINED_WHITESPACE = "UNDERLINED_WHITESPACE"
    TAB_LEADER = "TAB_LEADER"
    SOURCE_WHITESPACE_GAP = "SOURCE_WHITESPACE_GAP"
    VECTOR_LINE = "VECTOR_LINE"
    MIXED = "MIXED"


class SourceLineSpacingMode(str, Enum):
    SINGLE = "SINGLE"
    ONE_POINT_FIVE = "ONE_POINT_FIVE"
    DOUBLE = "DOUBLE"
    MULTIPLE = "MULTIPLE"
    EXACT = "EXACT"


@dataclass(frozen=True)
class SourceLineSpacingProfile:
    """Semantic Word spacing inferred from PDF geometry, never silently exact."""
    mode: SourceLineSpacingMode
    multiple: float | None = None
    exact_pt: float | None = None
    source_locator: object | None = None
    source_evidence: str = ""
    confidence: float = 0.0
    reason: str = ""

    @property
    def word_value(self):
        return {SourceLineSpacingMode.SINGLE: 1.0, SourceLineSpacingMode.ONE_POINT_FIVE: 1.5, SourceLineSpacingMode.DOUBLE: 2.0}.get(self.mode, float(self.multiple or 1.0))


#: Word-safe auto line-spacing multiples.  ``w:lineRule="auto"`` geometry is
#: quoted as a fraction of the font's own natural line height, so a source PDF
#: baseline pitch is reproduced in points - not by copying the raw
#: ``pitch / font_size`` ratio, which over-inflates every line.
WORD_AUTO_LINE_MULTIPLES = (1.0, 1.15, 1.2, 1.25, 1.5, 2.0)

#: A source baseline pitch within this many points of plain single spacing is
#: an ordinary single-spaced paragraph, not a stretched one.
SINGLE_LINE_PITCH_TOLERANCE_PT = 1.0


def infer_semantic_line_spacing(font_size_pt, baseline_pitch_pt=0.0, *, source_locator=None):
    """Choose a Word-native auto-line-spacing multiple for PDF content.

    ``word_value`` stays a Word auto multiple (never ``exact``): the *rendered*
    line pitch of auto spacing is ``multiple`` x the font's own natural line
    height, whose ratio to the font size is unknown.  The source pitch is
    therefore matched *relatively*: a safe multiple ``M`` renders at
    ``M * L * font_size`` and single spacing renders at ``L * font_size``, so
    the multiple that renders the source pitch is
    ``M * (ratio - L) / (M - L)`` for the candidate bracket ``L < ratio <= M``.
    Choosing the candidate whose bracketed multiple renders closest to the
    source pitch reproduces the source line geometry without hard-coding any
    font metric and without ever falling back to an exact line height.
    """

    font_size = max(1.0, float(font_size_pt or 10.5))
    pitch = max(0.0, float(baseline_pitch_pt or 0.0))
    if pitch <= 0.0:
        return SourceLineSpacingProfile(
            mode=SourceLineSpacingMode.SINGLE,
            multiple=1.0,
            source_locator=source_locator,
            source_evidence=f"font_size={font_size:.3f};baseline_pitch=0.000",
            confidence=0.75,
            reason="single-line PDF paragraph",
        )
    ratio = pitch / font_size
    if abs(pitch - font_size) <= SINGLE_LINE_PITCH_TOLERANCE_PT or ratio <= 1.0:
        return SourceLineSpacingProfile(
            mode=SourceLineSpacingMode.SINGLE,
            multiple=1.0,
            source_locator=source_locator,
            source_evidence=(
                f"font_size={font_size:.3f};baseline_pitch={pitch:.3f};"
                f"ratio={ratio:.3f}"
            ),
            confidence=0.7,
            reason="source baseline pitch is plain single spacing",
        )
    best = None
    for candidate in WORD_AUTO_LINE_MULTIPLES[1:]:
        reference = max(
            (value for value in WORD_AUTO_LINE_MULTIPLES if value < candidate),
            default=1.0,
        )
        if ratio > candidate:
            multiple = candidate
        else:
            multiple = candidate * ((ratio - reference) / (candidate - reference))
        multiple = min(max(multiple, 1.0), WORD_AUTO_LINE_MULTIPLES[-1])
        # The rendered pitch is proportional to ``multiple * candidate``; the
        # candidate whose product lands nearest the source ratio wins.
        error = abs(multiple * candidate - ratio)
        if best is None or error < best[0] or (
            error == best[0] and multiple > best[1]
        ):
            best = (error, multiple, candidate, reference)
    _, multiple, candidate, reference = best
    mode = {
        1.0: SourceLineSpacingMode.SINGLE,
        1.5: SourceLineSpacingMode.ONE_POINT_FIVE,
        2.0: SourceLineSpacingMode.DOUBLE,
    }.get(multiple, SourceLineSpacingMode.MULTIPLE)
    return SourceLineSpacingProfile(
        mode=mode,
        multiple=multiple,
        source_locator=source_locator,
        source_evidence=(
            f"font_size={font_size:.3f};baseline_pitch={pitch:.3f};"
            f"ratio={ratio:.3f};bracket=({reference},{candidate}];multiple={multiple:.3f}"
        ),
        confidence=0.7,
        reason="source pitch matched by the rendered geometry of a Word auto multiple",
    )


class ParagraphLayoutRole(str, Enum):
    """Semantic roles that can be serialized as Word paragraphs."""

    FLOW_BODY = 'FLOW_BODY'
    LIST_ITEM = 'LIST_ITEM'
    HEADING = 'HEADING'
    COVER_TITLE = 'COVER_TITLE'
    ADDRESSEE = 'ADDRESSEE'
    FORM_LINE = 'FORM_LINE'
    DATE_LINE = 'DATE_LINE'
    SIGNATURE_LINE = 'SIGNATURE_LINE'
    CONTACT_LINE = 'CONTACT_LINE'


class AlignmentRole(str, Enum):
    CENTERED_TITLE = 'CENTERED_TITLE'
    CENTERED_SUBTITLE = 'CENTERED_SUBTITLE'
    CENTERED_FORM_LINE = 'CENTERED_FORM_LINE'
    LEFT_BODY = 'LEFT_BODY'
    LEFT_FORM_LINE = 'LEFT_FORM_LINE'
    JUSTIFIED_BODY = 'JUSTIFIED_BODY'
    LIST_ITEM = 'LIST_ITEM'


@dataclass(frozen=True)
class CenteredFormLine:
    label: str
    slot: str | None
    total_source_width: float
    slot_width: float
    source_line_center_x: float
    source_container_center_x: float


@dataclass(frozen=True)
class ParagraphTabStop:
    """One source-backed tab anchor within a physical paragraph line.

    ``position_pt`` is measured from the paragraph's left edge, matching the
    public python-docx tab-stop API.  ``source_x`` is retained for QA and is
    never used as a page-positioning shortcut.
    """

    position_pt: float
    source_x: float
    leader: str = 'NONE'
    alignment: str = 'left'
    purpose: str = 'anchor'


@dataclass
class ParagraphLayout:
    """Word-native paragraph layout contract for one logical source item."""

    role: ParagraphLayoutRole | str
    container_x0: float
    container_x1: float
    source_x0: float
    source_y0: float
    alignment: str
    left_indent_pt: float = 0.0
    right_indent_pt: float = 0.0
    first_line_indent_pt: float = 0.0
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0
    line_spacing: float = 0.0
    tab_stops: list[ParagraphTabStop] = field(default_factory=list)
    runs: list = field(default_factory=list)
    source_locator: object | None = None
    source_page: int | None = None


@dataclass(frozen=True)
class EditableBlank:
    """One source-backed editable span and its Word-safe rendering contract."""

    kind: EditableBlankKind
    source_x0: float
    source_x1: float
    width_pt: float
    semantic_slot: str | None
    render_style: EditableBlankRenderStyle
    source_locator: object | None
    representation_kind: BlankRepresentationKind = BlankRepresentationKind.SOURCE_WHITESPACE_GAP
    raw_placeholder: str = ""


@dataclass
class FormRowGeometry:
    """Geometry and blank semantics for one physical form row."""

    item: 'LogicalParagraph'
    parts: list[str]
    row_type: str
    blanks: list[EditableBlank] = field(default_factory=list)
    label_x: float = 0.0
    value_x: float = 0.0
    annotation_x: float = 0.0
    centered_form_line: CenteredFormLine | None = None


@dataclass
class FormBlock:
    """A local multi-row form grid; unrelated page content is never included."""

    source_page: int
    bbox: tuple[float, float, float, float]
    container_x0: float
    container_x1: float
    label_x: float
    value_x: float
    annotation_x: float
    row_geometries: list[FormRowGeometry] = field(default_factory=list)


@dataclass
class ListLayoutGroup:
    number_x: float
    text_x: float
    container_right: float
    line_spacing: float
    space_before: float = 0
    space_after: float = 0
    level: int = 0
    group_id: int = 0


def join_visual_lines(text):
    """No layout tabs; Chinese wrapping adds no artificial word separator."""
    return text.replace('\t', ' ').replace('\r', '').replace('\n', '')


def visible_box(line):
    boxes=[s.bbox for s in line.spans if s.text.strip() and
        s.bbox[0]>=line.bbox[0]-1 and s.bbox[1]>=line.bbox[1]-1 and
        s.bbox[2]<=line.bbox[2]+1 and s.bbox[3]<=line.bbox[3]+1]
    return (min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)) if boxes else line.bbox


@dataclass
class LogicalParagraph:
    source: object
    source_start: int
    source_end: int
    bbox: tuple
    source_lines: list
    logical_text: str
    alignment_hint: str
    left_indent_pt: float
    first_line_indent_pt: float
    line_pitch_pt: float
    font_size_pt: float
    kind: str = 'LogicalParagraph'
    flow: bool = True
    container: LayoutContainer | None = None
    fragments: list = field(default_factory=list)
    list_level: int = 0
    list_group_id: int = 0
    alignment_role: AlignmentRole = AlignmentRole.LEFT_BODY

    @property
    def text_bbox(self):
        return self.bbox

    @property
    def paragraph_container_bbox(self):
        return (self.container.container_x0,self.bbox[1],self.container.container_x1,self.bbox[3])


@dataclass
class SourcePageLayout:
    source_page: int
    page_width_pt: float
    page_height_pt: float
    content_box: tuple
    classification: str
    elements: list = field(default_factory=list)
    horizontal_rules: list = field(default_factory=list)
    list_groups: list = field(default_factory=list)
    form_blocks: list[FormBlock] = field(default_factory=list)


def logical_paragraphs(source):
    lines = source.lines
    size = median([r.font_size for r in source.runs if r.font_size > 0] or [10.5])
    # Missing/mismatching geometry is not permission to invent paragraph joins.
    if not lines or ''.join(''.join(l.text.split()) for l in lines) != ''.join(source.text.split()):
        return [LogicalParagraph(source, 0, len(source.text), source.bbox, lines,
            source.text, source.alignment, source.bbox[0], source.first_line_indent,
            size * 1.15, size, flow=False)]
    # Empty PDF lines are geometric separation, not printable Word rows.
    # Align non-whitespace characters back to authoritative container offsets.
    positions = [i for i,c in enumerate(source.text) if not c.isspace()]
    entries, consumed = [], 0
    for line in lines:
        length=len(''.join(line.text.split()))
        if not length:
            continue
        start=positions[consumed]
        consumed += length
        end=positions[consumed] if consumed < len(positions) else len(source.text)
        entries.append((line,start,end))
    # First collect physical baselines. PDF often splits 地址 into 地 / 址：
    # spans; classifying those fragments separately loses the form boundary.
    rows = []
    for entry in entries:
        if not rows or abs(entry[0].bbox[1]-rows[-1][0][0].bbox[1])>2.5:
            rows.append([])
        rows[-1].append(entry)
    groups, group = [], []
    for row in rows:
        line,start,end = row[0][0],row[0][1],row[-1][2]
        row_text=join_visual_lines(source.text[start:end])
        if group:
            prev = group[-1][0]
            vertical = line.bbox[1] - prev.bbox[1]
            previous_size = median([s.font_size for s in prev.spans if s.font_size] or [size])
            current_size = median([s.font_size for s in line.spans if s.font_size] or [size])
            previous_text=join_visual_lines(source.text[group[0][1]:group[-1][2]])
            semantic = bool(ITEM.match(row_text) or FORM.match(row_text)
                or FORM.match(previous_text) or TERMINAL.search(previous_text)
                or re.fullmatch(r'[_\s]*年[_\s]*月[_\s]*日',row_text))
            boundary = vertical > size * 2.5 or abs(previous_size-current_size) > 1.5
            # A same-baseline fragment is an inline field, not a new paragraph.
            if vertical > 2.5 and (semantic or boundary):
                groups.append(group)
                group = []
        group.extend(row)
    if group:
        groups.append(group)
    result = []
    for group in groups:
        glines = [v[0] for v in group]
        glyph_boxes=[visible_box(l) for l in glines]
        bbox = (min(b[0] for b in glyph_boxes),min(b[1] for b in glyph_boxes),
                max(b[2] for b in glyph_boxes),max(b[3] for b in glyph_boxes))
        pitches = [b.bbox[1]-a.bbox[1] for a,b in zip(glines, glines[1:])
                   if 2.5 < b.bbox[1]-a.bbox[1] < size*2.5]
        start, end = group[0][1], group[-1][2]
        size=median([s.font_size for l in glines for s in l.spans if s.text.strip() and s.font_size>0] or [size])
        indent = max(0, visible_box(glines[0])[0]-bbox[0])
        text = join_visual_lines(source.text[start:end])
        kind = 'FormRow' if FORM.match(text) else 'LogicalParagraph'
        result.append(LogicalParagraph(source, start, end, bbox, glines, text,
            source.alignment, bbox[0], indent, max(size*1.05, median(pitches) if pitches else size*1.15), size, kind))
    return result


def classify_page(page):
    text = ''.join(''.join(p.text.split()) for p in page.paragraphs)
    if not page.tables and re.fullmatch(r'第[一二三四五六七八九十\d]+[章部分]+.*文件格式', text):
        return 'CHAPTER_DIVIDER'
    if not page.tables and len(text) < 450 and any(t in text for t in ('投标文件','响应文件','报价文件')) and '目录' not in text:
        return 'COVER_PAGE'
    if page.tables:
        return 'MIXED_PAGE' if page.paragraphs else 'TABLE_PAGE'
    return 'FLOW_TEXT_PAGE'


def build_page_layout(page):
    boxes = [e.bbox for e in page.elements]
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
           max(b[2] for b in boxes), max(b[3] for b in boxes)) if boxes else (0,0,page.width,page.height)
    result = SourcePageLayout(page.page, page.width, page.height, box, classify_page(page))
    for item in page.elements:
        if item.type == 'table':
            result.elements.append(page.tables[item.index])
        else:
            paragraphs = logical_paragraphs(page.paragraphs[item.index])
            for paragraph in paragraphs:
                text=paragraph.logical_text.strip()
                numeric_list=bool(re.match(r'^(?:附[表件录][一二三四五六七八九十\d]+|\d+[、.)）]|[（(]\d+[)）]|[①-⑳])',text))
                sentence=bool(re.match(r'^(?:我|本[单位公司人]|兹|愿意|以人民币|参加|依据|按照|根据)',text)
                    or re.search(r'研究|决定|应当|不得|必须|收到',text))
                title=(not numeric_list and not sentence and len(text)<65 and not re.search(r'[，。；：？！]',text)
                    and (re.match(r'^[一二三四五六七八九十]+、',text)
                         or re.search(r'(?:文件|函|证明|委托书|承诺书|附录|目录|表|附表|方案|格式自拟）|资格|要求|资料|保证金|凭证)$',text)
                         or (paragraph.source.alignment=='center' and bool(re.fullmatch(r'[（(][^()（）]{1,33}[）)]',text)))
                         or re.match(r'^[（(][一二三四五六七八九十]+[）)]\D{1,15}$',text)
                         or result.classification in ('COVER_PAGE','CHAPTER_DIVIDER')))
                paragraph.kind=('FormRow' if FORM.match(text) or re.fullmatch(r'[_\s]*年[_\s]*月[_\s]*日',text)
                    else 'Heading' if title else 'List' if ITEM.match(text) else 'LogicalParagraph')
                source_line_center=(paragraph.bbox[0]+paragraph.bbox[2])/2.0
                source_container_center=page.width/2.0
                centered_geometry=abs(source_line_center-source_container_center) <= max(8.0,page.width*.02)
                if paragraph.kind == 'FormRow':
                    paragraph.alignment_role=(AlignmentRole.CENTERED_FORM_LINE
                        if centered_geometry and len(text) <= 24 else AlignmentRole.LEFT_FORM_LINE)
                elif paragraph.kind == 'List':
                    paragraph.alignment_role=AlignmentRole.LIST_ITEM
                elif paragraph.kind == 'Heading' and centered_geometry:
                    paragraph.alignment_role=(AlignmentRole.CENTERED_TITLE
                        if paragraph.font_size_pt >= 18 else AlignmentRole.CENTERED_SUBTITLE)
                elif paragraph.source.alignment == 'justify':
                    paragraph.alignment_role=AlignmentRole.JUSTIFIED_BODY
                else:
                    paragraph.alignment_role=AlignmentRole.LEFT_BODY
                if paragraph.kind in ('FormRow', 'List', 'Caption'):
                    # Form labels, addressees and list markers are anchored
                    # left; their source glyphs must not turn into a Word
                    # justification request.  A narrative paragraph may
                    # retain the explicit geometry-backed ``justify`` hint.
                    paragraph.alignment_hint='left'
                elif paragraph.kind != 'Heading':
                    paragraph.alignment_hint=(
                        'justify' if paragraph.source.alignment == 'justify' else 'left'
                    )
                if re.fullmatch(r'单位[：:].{1,8}',text): paragraph.kind='Caption'
                # Explicit right-side signature/label and unit-caption regions
                # are separate containers, not narrow body-text columns.
                container_left=(18.0 if paragraph.alignment_role == AlignmentRole.CENTERED_FORM_LINE
                    else paragraph.bbox[0] if paragraph.kind in ('FormRow','Caption') else box[0])
                # Ordinary flowing text owns the page content band.  A short
                # final glyph does not become a right-indent surrogate. Local
                # form/caption rows retain their source-region right edge.
                container_right=(page.width-18.0 if paragraph.alignment_role == AlignmentRole.CENTERED_FORM_LINE
                    else box[2] if paragraph.kind in ('FormRow','Caption') else page.width-18.0)
                paragraph.container=LayoutContainer(container_left,container_right)
                paragraph.fragments=[(paragraph.source,paragraph.source_start,paragraph.source_end)]
            result.elements.extend(paragraphs)
    # Estimate page-local pitch rather than treating font size as line spacing.
    # Some forms use ~10pt text on a 25pt baseline grid.
    pitches=[]
    for a,b in zip(result.elements,result.elements[1:]):
        if isinstance(a,LogicalParagraph) and isinstance(b,LogicalParagraph) and a.kind in ('LogicalParagraph','List') and b.kind in ('LogicalParagraph','List'):
            delta=b.bbox[1]-a.bbox[3]+a.font_size_pt
            if a.font_size_pt*.75<delta<a.font_size_pt*3.3: pitches.append(delta)
    if len(pitches)>=2:
        pitch=median(pitches)
        for p in result.elements:
            if isinstance(p,LogicalParagraph) and p.kind in ('LogicalParagraph','List') and len({round(l.bbox[1],1) for l in p.source_lines})==1:
                p.line_pitch_pt=max(p.font_size_pt*1.05,pitch)
    # Join strongly compatible adjacent blocks BEFORE the renderer sees them.
    merged=[]
    for paragraph in result.elements:
        if merged and can_continue(merged[-1],paragraph):
            previous=merged[-1]
            last_y=max(l.bbox[1] for l in previous.source_lines)
            pitch=paragraph.bbox[1]-last_y
            previous.fragments.extend(paragraph.fragments)
            previous.source_lines.extend(paragraph.source_lines)
            previous.logical_text=join_text(previous.logical_text,paragraph.logical_text)
            previous.bbox=(min(previous.bbox[0],paragraph.bbox[0]),previous.bbox[1],
                max(previous.bbox[2],paragraph.bbox[2]),paragraph.bbox[3])
            previous.left_indent_pt=previous.bbox[0]
            previous.first_line_indent_pt=visible_box(previous.source_lines[0])[0]-previous.bbox[0]
            previous.line_pitch_pt=max(previous.font_size_pt*1.05,pitch)
        else:
            merged.append(paragraph)
    result.elements=merged
    result.horizontal_rules = [line for line in page.lines if line.orientation == 'horizontal']
    # Sibling list items share one source geometry.  In these PDFs the
    # extracted continuation line is sometimes left of the first line: that
    # is the marker column, not the body column.  Normalize the two anchors
    # before handing them to Word so the hanging value is negative.
    siblings=[]
    sibling_level=None
    def finish_list():
        nonlocal sibling_level
        if not siblings:
            return
        number, text_x = _list_group_anchors(siblings)
        pitch = median(
            p.line_pitch_pt for p in siblings if len(p.source_lines) > 1
        ) if any(len(p.source_lines) > 1 for p in siblings) else median(
            p.line_pitch_pt for p in siblings
        )
        group_id=len(result.list_groups)
        group=ListLayoutGroup(number, text_x, box[2], pitch, level=sibling_level or 0, group_id=group_id)
        result.list_groups.append(group)
        for p in siblings:
            p.left_indent_pt=text_x
            p.first_line_indent_pt=number-text_x
            p.line_pitch_pt=pitch
            p.list_level=sibling_level or 0
            p.list_group_id=group_id
        siblings.clear()
        sibling_level=None
    for p in result.elements:
        if isinstance(p,LogicalParagraph) and p.kind=='List':
            level=_list_level(p.logical_text)
            if siblings and level != sibling_level:
                finish_list()
            sibling_level=level
            siblings.append(p)
        else:
            finish_list()
    finish_list()

    # Related form rows are one local grid.  Keeping the grouping here means
    # the Word builder never has to guess whether two independently emitted
    # one-row tables belong together.
    grouped=[]
    index=0
    while index < len(result.elements):
        item=result.elements[index]
        if not (isinstance(item,LogicalParagraph) and item.kind=='FormRow'):
            grouped.append(item)
            index += 1
            continue
        rows=[item]
        index += 1
        while index < len(result.elements):
            candidate=result.elements[index]
            if not (isinstance(candidate,LogicalParagraph) and candidate.kind=='FormRow'):
                break
            previous=rows[-1]
            gap=candidate.bbox[1]-previous.bbox[3]
            if gap > max(36.0, previous.font_size_pt*3.5) or abs(candidate.bbox[0]-previous.bbox[0]) > 18.0:
                break
            rows.append(candidate)
            index += 1
        form_block=_form_block_from_rows(rows, result.horizontal_rules, box)
        result.form_blocks.append(form_block)
        grouped.append(form_block)
    result.elements=grouped
    return result


def _list_level(text):
    match=re.match(r'^\s*(?:[（(][一二三四五六七八九十\d]+[)）]|[（(]\d+[)）])', text)
    return 1 if match else 0


def _marker_text(text):
    match=re.match(r'^\s*(?:附[表件录][一二三四五六七八九十\d]+|[一二三四五六七八九十]+[、．.]|\d+[、.)）]|[（(][一二三四五六七八九十\d]+[)）]|[①-⑳])', text)
    return match.group(0).strip() if match else ''


def _marker_advance(text, font_size):
    marker=_marker_text(text)
    if not marker:
        return max(10.0, font_size)
    # CJK punctuation and full-width markers occupy one em; Latin digits and
    # ASCII punctuation occupy approximately half an em in the source font.
    advance=sum(font_size if ord(char) > 127 else font_size*.55 for char in marker)
    return max(font_size*1.15, advance)


def _list_group_anchors(siblings):
    first_x=[visible_box(p.source_lines[0])[0] if p.source_lines else p.bbox[0] for p in siblings]
    continuation_x=[
        visible_box(line)[0]
        for p in siblings
        for line in p.source_lines[1:]
        if line.bbox[1] > p.bbox[1]+2.5
    ]
    first=median(first_x)
    if continuation_x:
        continuation=median(continuation_x)
        if continuation < first-2.0:
            # Source first lines begin at the body anchor while wrapped lines
            # expose the marker-column anchor.
            return continuation, first
        if abs(continuation-first) <= 2.0:
            # Some extracted lists place continuation lines on the same
            # source x as the marker.  Reserve the marker advance explicitly
            # so wrapped text cannot collapse onto the number column.
            return first, first+median(_marker_advance(p.logical_text,p.font_size_pt) for p in siblings)
        return first, continuation
    return first, first+median(_marker_advance(p.logical_text,p.font_size_pt) for p in siblings)


def _form_label(text):
    match=re.match(r'^\s*([^：:\r\n]{1,40})[：:]', text)
    return match.group(1).strip() if match else ''


def _source_char_advance(char, font_size):
    return font_size if ord(char) > 127 else font_size * .55


def _explicit_blank_geometry(item, match, occurrence):
    """Map an underscore sequence back into its source text run bbox.

    PDF extraction often keeps ``label:____`` in one span.  Using that span's
    right edge as the label edge makes the blank start after the whole row.
    Character advances preserve the source run's actual label/blank split and
    scale the estimate to the run bbox when the PDF font metrics differ.
    """
    candidates=[]
    for run in item.source.runs:
        for run_match in re.finditer(r'[_＿]{2,}', run.text or ''):
            candidates.append((run, run_match))
    if occurrence >= len(candidates):
        return None
    run, run_match = candidates[occurrence]
    font_size=float(run.font_size or item.font_size_pt or 10.5)
    raw_total=sum(_source_char_advance(char, font_size) for char in (run.text or ''))
    bbox_width=max(0.0, float(run.bbox[2])-float(run.bbox[0]))
    scale=bbox_width/raw_total if raw_total > 0 and bbox_width > 0 else 1.0
    prefix=(run.text or '')[:run_match.start()]
    blank=(run.text or '')[run_match.start():run_match.end()]
    x0=float(run.bbox[0])+sum(_source_char_advance(char, font_size) for char in prefix)*scale
    x1=x0+sum(_source_char_advance(char, font_size) for char in blank)*scale
    return x0, max(x0+1.0, x1)


def _form_row_type(parts, text):
    compact_text=re.sub(r'\s+','',text)
    if re.search(r'年.*月.*日',compact_text):
        return 'DATE_ROW'
    labels=sum(1 for part in parts if re.search(r'[：:]\s*$',part))
    if labels > 1:
        return 'MULTI_INLINE_FIELDS'
    if parts and parts[-1].strip(' \t\r\n'):
        return 'LABEL_BLANK_ANNOTATION'
    return 'LABEL_BLANK'


def _rule_candidates(item, rules):
    return sorted(
        [
            rule for rule in rules
            if rule.orientation == 'horizontal'
            and 8.0 <= rule.bbox[2]-rule.bbox[0] <= 320.0
            and abs(rule.bbox[1]-item.bbox[3]) <= 6.0
            and rule.bbox[2] >= item.bbox[0]-4.0
            and rule.bbox[0] <= item.bbox[2]+80.0
        ],
        key=lambda rule: (rule.bbox[0], rule.bbox[2]),
    )


def _blank_indices(parts, text):
    if not parts:
        return []
    if re.search(r'年.*月.*日', re.sub(r'\s+','',text)) and len(parts) >= 6:
        return [1,3,5] if parts[0].strip().endswith(('：',':')) else [0,2,4]
    return [index for index, part in enumerate(parts) if not part.strip(' _＿\t\r\n') and index % 2 == 1]


def editable_blanks_for_form(item, rules, parts=None):
    """Classify one form row without creating a placeholder string."""
    parts=form_parts(item.logical_text) if parts is None else parts
    if not parts:
        return []
    blank_indexes=_blank_indices(parts,item.logical_text)
    if not blank_indexes:
        return []
    rules_found=_rule_candidates(item,rules)
    text_runs=[run for run in item.source.runs if run.text]
    label_end=item.bbox[0]
    if text_runs:
        first=text_runs[0]
        label_end=first.bbox[2] if first.text.strip() else label_end
    annotation_x=None
    for run in text_runs[1:]:
        if run.text.strip().startswith(('（','(')):
            annotation_x=run.bbox[0]
            break
    blanks=[]
    underscore_matches=list(re.finditer(r'[_＿]{2,}',item.logical_text))
    underscore_widths=[]
    for match in underscore_matches:
        underscore_widths.append(max(item.font_size_pt, len(match.group(0))*item.font_size_pt*.5))
    project_geometry=_form_label(item.logical_text) in {'项目编号','招标人项目编号','采购人项目编号','采购项目编号'}
    for position,index in enumerate(blank_indexes):
        rule=rules_found[position] if position < len(rules_found) else None
        explicit_width=underscore_widths[position] if position < len(underscore_widths) else None
        raw_placeholder = parts[index] if index < len(parts) else ""
        long_extracted_gap = (
            len(raw_placeholder) >= 4
            and not raw_placeholder.strip()
        )
        baseline_rule_placeholder = (
            rule is not None
            and bool(re.search(r"[：:]\s*$", item.logical_text))
            and abs(float(rule.bbox[1]) - float(item.bbox[3])) <= 2.5
        )
        if rule is not None and (long_extracted_gap or baseline_rule_placeholder):
            # A measured source rule is a vector line.  It is a safe editable
            # equivalent, but it must never be reported or rendered as literal
            # underscore text that the source does not contain.
            x0,x1=rule.bbox[0],rule.bbox[2]
            kind=EditableBlankKind.DATE_BLANK if _form_row_type(parts,item.logical_text)=="DATE_ROW" else EditableBlankKind.FORM_BLANK
            style=EditableBlankRenderStyle.BOTTOM_RULE
            representation=BlankRepresentationKind.VECTOR_LINE
        elif long_extracted_gap:
            # Only a visual whitespace gap exists in the source: keep the
            # editable slot but do not invent underscore/underline glyphs.
            x0=label_end+4.0
            width=max(item.font_size_pt*2.0, len(raw_placeholder)*item.font_size_pt*.5)
            x1=x0+width
            raw_placeholder=""
            kind=EditableBlankKind.DATE_BLANK if _form_row_type(parts,item.logical_text)=="DATE_ROW" else EditableBlankKind.FORM_BLANK
            style=EditableBlankRenderStyle.PLAIN_EMPTY
            representation=BlankRepresentationKind.SOURCE_WHITESPACE_GAP
        elif explicit_width is not None:
            geometry=_explicit_blank_geometry(item, underscore_matches[position], position)
            if geometry is not None:
                x0,x1=geometry
            else:
                x0=label_end+4.0 if position == 0 else label_end+4.0+position*explicit_width
                x1=x0+explicit_width
            kind=EditableBlankKind.DATE_BLANK if _form_row_type(parts,item.logical_text)=='DATE_ROW' else EditableBlankKind.FORM_BLANK
            style=EditableBlankRenderStyle.PLAIN_EMPTY
            representation=BlankRepresentationKind.LITERAL_UNDERSCORES
        elif rule is not None:
            x0,x1=rule.bbox[0],rule.bbox[2]
            kind=EditableBlankKind.DATE_BLANK if _form_row_type(parts,item.logical_text)=='DATE_ROW' else EditableBlankKind.FORM_BLANK
            style=EditableBlankRenderStyle.BOTTOM_RULE
            representation=BlankRepresentationKind.VECTOR_LINE
        elif project_geometry and position == 0:
            # The source row is ``项目编号：<whitespace>``: a labelled field
            # with no drawn rule and no underscore run.  It stays an editable
            # blank, but its kind is the page-local one - plain whitespace.
            # Inventing a tab leader here painted an underline the source never
            # draws and left a stray underlined figure-space after the value.
            x0=label_end+5.0
            x1=min(item.container.container_x1 if item.container else item.bbox[2]+150.0, x0+120.0)
            kind=EditableBlankKind.FORM_BLANK
            style=EditableBlankRenderStyle.PLAIN_EMPTY
            representation=BlankRepresentationKind.SOURCE_WHITESPACE_GAP
        else:
            x0=label_end+4.0
            x1=annotation_x-4.0 if annotation_x and annotation_x > x0 else x0+max(32.0,item.font_size_pt*4.0)
            kind=EditableBlankKind.DATE_BLANK if _form_row_type(parts,item.logical_text)=='DATE_ROW' else EditableBlankKind.SOURCE_EMPTY
            style=EditableBlankRenderStyle.PLAIN_EMPTY
            representation=BlankRepresentationKind.SOURCE_WHITESPACE_GAP
        blanks.append(EditableBlank(
            kind=kind,
            source_x0=x0,
            source_x1=max(x0+1.0,x1),
            width_pt=max(1.0,x1-x0),
            semantic_slot=_form_label(item.logical_text) or None,
            render_style=style,
            source_locator=item.source.locator,
            representation_kind=representation,
            raw_placeholder=raw_placeholder,
        ))
    return blanks


def _form_block_from_rows(rows, rules, box):
    geometries=[]
    for item in rows:
        parts=form_parts(item.logical_text) or [item.logical_text]
        blanks=editable_blanks_for_form(item,rules,parts)
        label_x=item.bbox[0]
        value_x=median([blank.source_x0 for blank in blanks]) if blanks else item.bbox[2]
        annotation_x=next(
            (run.bbox[0] for run in item.source.runs[1:] if run.text.strip().startswith(('（','('))),
            max([item.bbox[2]]+[blank.source_x1 for blank in blanks] or [item.bbox[2]]),
        )
        centered = None
        if item.alignment_role == AlignmentRole.CENTERED_FORM_LINE:
            slot_width=sum(blank.width_pt for blank in blanks)
            fixed_right=max([item.bbox[2]]+[blank.source_x1 for blank in blanks])
            centered=CenteredFormLine(
                label=parts[0] if parts else item.logical_text,
                slot=blanks[0].semantic_slot if blanks else None,
                total_source_width=max(1.0,fixed_right-item.bbox[0]),
                slot_width=max(1.0,slot_width),
                source_line_center_x=(item.bbox[0]+item.bbox[2])/2.0,
                source_container_center_x=(item.container.container_x0+item.container.container_x1)/2.0 if item.container else 0.0,
            )
        geometries.append(FormRowGeometry(item,parts,_form_row_type(parts,item.logical_text),blanks,label_x,value_x,annotation_x,centered))
    x0=min(g.label_x for g in geometries)
    x1=max([g.item.bbox[2] for g in geometries]+[blank.source_x1 for g in geometries for blank in g.blanks]+[g.annotation_x for g in geometries])
    label_x=median(g.label_x for g in geometries)
    value_candidates=[g.value_x for g in geometries if g.value_x > label_x]
    annotation_candidates=[g.annotation_x for g in geometries if g.annotation_x > label_x]
    value_x=median(value_candidates) if value_candidates else label_x
    annotation_x=median(annotation_candidates) if annotation_candidates else value_x
    centered_rows=[g for g in geometries if g.centered_form_line is not None]
    return FormBlock(
        source_page=rows[0].source.page,
        bbox=(x0,min(row.bbox[1] for row in rows),x1,max(row.bbox[3] for row in rows)),
        container_x0=(rows[0].container.container_x0 if len(centered_rows)==len(geometries) and rows[0].container else x0),
        container_x1=(rows[0].container.container_x1 if len(centered_rows)==len(geometries) and rows[0].container else x1),
        label_x=label_x,
        value_x=value_x,
        annotation_x=annotation_x,
        row_geometries=geometries,
    )


def join_text(left,right):
    # A Latin word boundary needs a separator, CJK visual wrapping does not.
    separator=' ' if left and right and left[-1].isascii() and left[-1].isalnum() and right[0].isascii() and right[0].isalnum() else ''
    return left+separator+right


def can_continue(left,right):
    if not isinstance(left,LogicalParagraph) or not isinstance(right,LogicalParagraph): return False
    if not left.flow or not right.flow or not left.source_lines or not right.source_lines: return False
    if TERMINAL.search(left.logical_text) and not (left.kind=='List' and left.logical_text.rstrip().endswith(('；',':','：'))): return False
    size=max(left.font_size_pt,right.font_size_pt)
    pitch=right.bbox[1]-max(l.bbox[1] for l in left.source_lines)
    if not size*.75<=pitch<=max(size*2.5,left.line_pitch_pt*1.25) or abs(left.font_size_pt-right.font_size_pt)>1.5: return False
    lf={r.font_name for r in left.source.runs if r.text.strip()}
    rf={r.font_name for r in right.source.runs if r.text.strip()}
    if lf and rf and not lf.intersection(rf): return False
    # A centered block cannot be joined by comparing left glyph edges: centered
    # lines share a center axis while their left edges move with line length.
    # A PDF visual wrap inside one centered title therefore must be judged on
    # the center axis, otherwise every wrapped title line becomes its own Word
    # paragraph and can split a word across two paragraphs.
    if left.alignment_hint=='center' and right.alignment_hint=='center':
        if left.kind not in ('LogicalParagraph','List','Heading') or right.kind not in ('LogicalParagraph','Heading'): return False
        left_center=(left.bbox[0]+left.bbox[2])/2.0
        right_center=(right.bbox[0]+right.bbox[2])/2.0
        if abs(right_center-left_center)>size*1.5: return False
        if left.kind!=right.kind: return False
        return _center_continuation_evidence(left,right,size)
    if left.kind not in ('LogicalParagraph','List') or right.kind!='LogicalParagraph': return False
    if abs(right.bbox[0]-left.bbox[0])>size*3: return False
    # Independent short labels are not unfinished prose. Require useful line
    # extent or sentence/list context, never similar right glyph coordinates.
    return (left.kind=='List' or len(left.logical_text)>25 or
            (left.container is not None and left.bbox[2]-left.bbox[0]>=left.container.container_width*.7) or
            bool(re.search(r'[，、（(]',left.logical_text)))


_SENTENCE_END=re.compile(r'[。！？；：!?;:]\s*$')
_CLAUSE_END=re.compile(r'[，、,]\s*$')
_MARKER_START=re.compile(r'^\s*(?:附[表件录][一二三四五六七八九十\d]+|[一二三四五六七八九十]+[、．.]|\d+[、.)）]|[（(]\d+[)）]|[①-⑳])')
_FORM_START=re.compile(r'^\s*[^：:\r\n]{1,40}[：:]')


def _center_continuation_evidence(left,right,size):
    """Decide whether two centered blocks are one wrapped logical block.

    Evidence is deliberately conservative: an unfinished line plus a genuine
    visual wrap. Two independent short centered labels are not joined.
    """
    left_text=left.logical_text.rstrip()
    right_text=right.logical_text.lstrip()
    if not left_text or not right_text: return False
    # A completed sentence or an explicit list/form marker starts a new block.
    if _SENTENCE_END.search(left_text): return False
    if _MARKER_START.match(right_text) or _FORM_START.match(right_text): return False
    container_right=left.container.container_x1 if left.container is not None else None
    if container_right is None: return False
    user_width=max(1.0,float(container_right)-(left.container.container_x0 if left.container is not None else 0.0))
    # The previous line must nearly fill the source column: that is the visible
    # wrap signal. A clause break alone is not enough to justify a merge.
    line_width=float(left.source_lines[-1].bbox[2])-float(left.source_lines[-1].bbox[0])
    if line_width < user_width*.85: return False
    # Require a same-script continuation so unrelated neighbours never merge.
    left_tail=left_text[-1]
    right_head=right_text[0]
    if left_tail.isascii() != right_head.isascii(): return False
    return True


def bounded_scale(requested):
    if not .94 <= requested <= 1.03:
        raise ValueError('PAGE_LAYOUT_NEEDS_REVIEW: scale outside 0.94–1.03')
    return requested


def read_pdf_geometry(path, source_pages):
    """Read only specified source pages; direct spans retain baseline/origin.

    This layout-only snapshot does not modify NormalizedDocument or facts.
    Graphic paths are evidence, not automatically rendered artwork.
    """
    import pymupdf
    result = []
    with pymupdf.open(path) as pdf:
        for number in source_pages:
            page = pdf[number-1]
            result.append({'source_page':number, 'page_width_pt':page.rect.width,
                'page_height_pt':page.rect.height,
                'text_blocks':[b for b in page.get_text('dict')['blocks'] if b.get('type') == 0],
                'graphic_paths':[{'rect':tuple(d['rect']), 'width':d.get('width'),
                    'items':[(v[0], *[tuple(x) if hasattr(x, 'x') or hasattr(x, 'x0') else x for x in v[1:]]) for v in d['items']]}
                    for d in page.get_drawings()]})
    return result


def form_parts(text):
    """Return physical form components without manufacturing placeholders."""
    # A source date row may carry trailing whitespace from PDF span geometry.
    # Anchoring the date patterns on the stripped text keeps the row a real
    # labeled date row instead of degrading it into an unparsed line.
    date_text = text.rstrip()
    date = re.fullmatch(r'([_＿\s]*)年([_＿\s]*)月([_＿\s]*)日', date_text)
    if date:
        return [date[1], '年', date[2], '月', date[3], '日']
    labeled_date = re.fullmatch(
        r'(?P<label>[^：:\r\n]{1,40}[：:])\s*'
        r'(?P<year>[_＿\s]*)年(?P<month>[_＿\s]*)月(?P<day>[_＿\s]*)日',
        date_text,
    )
    if labeled_date:
        return [
            labeled_date.group('label'), labeled_date.group('year'), '年',
            labeled_date.group('month'), '月', labeled_date.group('day'), '日',
        ]
    if not FORM.match(text):
        return None
    # Adjacent annotated labels without any explicit blank marker are usually
    # several physical rows that were concatenated upstream, not one
    # multi-field row.  Keep them out of the inline-row parser; geometry-aware
    # FormBlock grouping will still recover each real row independently.
    if (re.search(r'[）)]\s*[^：:\r\n]{1,20}[：:]', text)
            and not re.search(r'[_＿]', text)):
        return None
    match = re.fullmatch(r'([^：:\r\n]{1,40}[：:])([_\s]*)([（(][^：:\r\n]*[）)])?', text)
    if match:
        return [match[1], match[2], match[3] or '']

    # Same-baseline fields such as ``姓名：____ 性别：____ 年龄：____`` are
    # one physical row. Accept only empty/underscore values or one trailing
    # annotation, so fixed business text is never reclassified as a blank.
    parts=[]
    cursor=0
    while cursor < len(text):
        label=re.match(r'\s*([^：:\r\n]{1,20}[：:])', text[cursor:])
        if label is None:
            return None
        parts.append(label.group(1))
        cursor += label.end()
        blank=re.match(r'[_＿\s]*', text[cursor:])
        value=blank.group(0) if blank else ''
        parts.append(value)
        cursor += len(value)
        annotation=re.match(r'\s*([（(][^：:\r\n]*[）)])', text[cursor:])
        if annotation:
            parts.append(annotation.group(1))
            cursor += annotation.end()
        if cursor >= len(text):
            return parts
        trailing=re.match(r'\s*([。；.!！?？])\s*$', text[cursor:])
        if trailing:
            parts.append(trailing.group(1))
            return parts
        if not re.match(r'\s*[^：:\r\n]{1,20}[：:]', text[cursor:]):
            return None
    return parts or None


def underline_for_form(item, rules):
    """Associate a vector blank only with a nearby explicit field label.

    Table rules have already been separated by SourceFormatTemplate. Long
    graphic rules, unrelated lines and existing underscores are not duplicated.
    """
    date=bool(re.fullmatch(r'[_＿\s]*年[_＿\s]*月[_＿\s]*日',item.logical_text))
    if not (FORM.match(item.logical_text) or date) or re.search(r'[_＿]', item.logical_text):
        return None
    candidates = [r for r in rules if r.orientation=='horizontal'
        and 20 <= r.bbox[2]-r.bbox[0] <= 300
        and abs(r.bbox[1]-item.bbox[3]) <= 5
        and item.bbox[0]-(100 if date else 3)<=r.bbox[0]<=item.bbox[2]+30]
    return min(candidates,key=lambda r:abs(r.bbox[0]-item.bbox[2])) if candidates else None


INLINE_BLANK_PREFIX='\ue000BLANK:'
INLINE_BLANK_SUFFIX='\ue001'


def inline_blank_token(width_pt, source_x0=None, source_x1=None):
    """Marker for a source gap that must be emitted at its measured span.

    The token carries the rule's own ``x0``/``x1`` so the renderer can position
    the blank with explicit tab stops instead of inferring a span from the text
    cursor or from a repeated figure-space count.
    """

    x0 = 0.0 if source_x0 is None else float(source_x0)
    x1 = x0 + max(1.0, float(width_pt)) if source_x1 is None else float(source_x1)
    return (
        f'{INLINE_BLANK_PREFIX}w={max(1.0,float(width_pt)):.2f}'
        f';x0={x0:.2f};x1={x1:.2f}{INLINE_BLANK_SUFFIX}'
    )


def parse_inline_blank_token(payload):
    """The ``(width, x0, x1)`` carried by an inline blank token."""

    fields = {}
    for chunk in str(payload).split(';'):
        if '=' not in chunk:
            continue
        key, _, value = chunk.partition('=')
        try:
            fields[key.strip()] = float(value)
        except ValueError:
            continue
    if 'w' not in fields:
        return None
    width = fields['w']
    x0 = fields.get('x0', 0.0)
    x1 = fields.get('x1', x0 + width)
    return width, x0, x1


#: A rule whose extent is this clear of source text is a fill gap, not an
#: underline.  A rule whose extent is this occupied by source text is an
#: underline of that text and must never become a separate blank tab.
RULE_TEXT_OCCUPANCY_UNDERLINE = 0.60
RULE_TEXT_OCCUPANCY_GAP = 0.20


def _span_baseline(span):
    origin = getattr(span, "origin", None)
    if origin:
        try:
            return float(origin[1])
        except (TypeError, IndexError):
            pass
    return float(span.bbox[3])


def rule_text_occupancy(rule, spans, *, baseline_tolerance=4.0):
    """Fraction of a rule's horizontal extent that visible source text occupies.

    The rule is drawn at the source underline depth, so it lies *inside* the
    owner span's box rather than below it.  What decides whether it is a text
    underline or a fill gap is therefore not vertical distance but whether
    glyphs actually sit along the rule's extent.  Only spans sharing the rule's
    own line contribute.
    """

    rule_x0, rule_x1 = float(rule.bbox[0]), float(rule.bbox[2])
    rule_y = (float(rule.bbox[1]) + float(rule.bbox[3])) / 2.0
    width = max(0.01, rule_x1 - rule_x0)
    usable = [s for s in spans if str(getattr(s, "text", "") or "").strip()]
    if not usable:
        return 0.0
    owner_baseline = min((_span_baseline(s) for s in usable), key=lambda b: abs(rule_y - b))
    line_spans = [s for s in usable if abs(_span_baseline(s) - owner_baseline) <= baseline_tolerance]
    merged = []
    for span in sorted(line_spans, key=lambda s: float(s.bbox[0])):
        left, right = float(span.bbox[0]), float(span.bbox[2])
        if right <= rule_x0 + 0.5 or left >= rule_x1 - 0.5:
            continue
        if merged and left <= merged[-1][1] + 0.5:
            merged[-1][1] = max(merged[-1][1], right)
        else:
            merged.append([left, right])
    covered = sum(max(0.0, min(right, rule_x1) - max(left, rule_x0)) for left, right in merged)
    return covered / width


def classify_rule_relation(rule, spans, *, resolved_values=()):
    """Classify a horizontal rule against the source text it belongs to.

    Returns one of ``GAP_FILL_RULE`` (extent clear of text, so a fillable blank),
    ``TEXT_UNDERLINE`` / ``PLACEHOLDER_UNDERLINE`` / ``VALUE_UNDERLINE`` (extent
    occupied by source text, so the owning run keeps the underline), or
    ``FORM_LAYOUT_RULE`` (mixed extent, owner resolved by line geometry only).
    """

    occupancy = rule_text_occupancy(rule, spans)
    rule_x0, rule_x1 = float(rule.bbox[0]), float(rule.bbox[2])
    rule_y = (float(rule.bbox[1]) + float(rule.bbox[3])) / 2.0
    usable = [s for s in spans if str(getattr(s, "text", "") or "").strip()]
    prefixes = [
        s for s in usable
        if float(s.bbox[2]) <= rule_x0 + 1.5 and abs(float(s.bbox[1]) - rule_y) <= 16.0
    ]
    suffixes = [
        s for s in usable
        if float(s.bbox[0]) >= rule_x1 - 1.5 and abs(float(s.bbox[1]) - rule_y) <= 16.0
    ]
    owner = next(
        (
            s for s in usable
            if float(s.bbox[0]) <= rule_x0 + 1.5 and float(s.bbox[2]) >= rule_x1 - 1.5
        ),
        None,
    )
    prefix = max(prefixes, key=lambda s: float(s.bbox[2])) if prefixes else None
    suffix = min(suffixes, key=lambda s: float(s.bbox[0])) if suffixes else None
    if occupancy < RULE_TEXT_OCCUPANCY_GAP:
        relation = "GAP_FILL_RULE"
    elif occupancy >= RULE_TEXT_OCCUPANCY_UNDERLINE:
        owner_text = str(getattr(owner, "text", "") or "")
        resolved = any(value and value in owner_text for value in resolved_values)
        if resolved:
            relation = "VALUE_UNDERLINE"
        elif "（" in owner_text or "(" in owner_text:
            relation = "PLACEHOLDER_UNDERLINE"
        else:
            relation = "TEXT_UNDERLINE"
    else:
        relation = "FORM_LAYOUT_RULE"
    return {
        "relation_type": relation,
        "text_occupancy": round(occupancy, 3),
        "prefix_text": str(getattr(prefix, "text", "") or "") or None,
        "prefix_x1": round(float(prefix.bbox[2]), 2) if prefix else None,
        "suffix_text": str(getattr(suffix, "text", "") or "") or None,
        "suffix_x0": round(float(suffix.bbox[0]), 2) if suffix else None,
        "owner_text": str(getattr(owner, "text", "") or "") or None,
    }


@dataclass
class ParagraphCoordinateFrame:
    """Every x-coordinate involved in placing a source-positioned rule.

    The distinction that matters is between the *section* text margin, which is
    the origin Word measures ``w:tab/@w:pos`` from, and the *effective line
    origin*, which is where the rendered text actually starts once indents are
    applied.  Conflating the two silently shifted every positioned rule.
    """

    page_left_x: float
    section_left_margin: float
    paragraph_left_indent: float
    paragraph_first_line_indent: float
    paragraph_hanging_indent: float
    source_target_x0: float
    source_target_x1: float

    @property
    def tab_stop_reference_origin_x(self) -> float:
        """The x that ``w:tab/@w:pos`` is measured from.

        ``WORD_TAB_REFERENCE_MODEL`` from the controlled probes: the ruler a
        paragraph's tab stops are laid out on is the *section text margin*.  A
        paragraph's own left indent moves where its text starts but not where the
        ruler begins: a controlled probe that requests the same stop under
        ``left_indent = 0``, ``+21`` and ``-21`` paints it at the same absolute x,
        while the text itself starts at the indented origin.
        """

        return float(self.section_left_margin)

    @property
    def effective_line_origin_x(self) -> float:
        """Where the first line of this paragraph actually starts."""

        return (
            float(self.section_left_margin)
            + float(self.paragraph_left_indent)
            + float(self.paragraph_first_line_indent)
        )

    @property
    def current_line_origin_x(self) -> float:
        """Where a line after a form-layout break actually starts.

        A break ends the first line, so the first-line indent no longer applies;
        the left indent still does.
        """

        return float(self.section_left_margin) + float(self.paragraph_left_indent)

    def target_tab_start(self) -> float:
        return float(self.source_target_x0) - self.tab_stop_reference_origin_x

    def target_tab_end(self) -> float:
        return float(self.source_target_x1) - self.tab_stop_reference_origin_x

    def as_dict(self) -> dict:
        return {
            "page_left_x": round(self.page_left_x, 2),
            "section_left_margin": round(self.section_left_margin, 2),
            "paragraph_left_indent": round(self.paragraph_left_indent, 2),
            "paragraph_first_line_indent": round(self.paragraph_first_line_indent, 2),
            "paragraph_hanging_indent": round(self.paragraph_hanging_indent, 2),
            "effective_line_origin_x": round(self.effective_line_origin_x, 2),
            "current_line_origin_x": round(self.current_line_origin_x, 2),
            "tab_stop_reference_origin_x": round(self.tab_stop_reference_origin_x, 2),
            "source_target_x0": round(self.source_target_x0, 2),
            "source_target_x1": round(self.source_target_x1, 2),
            "target_tab_start": round(self.target_tab_start(), 2),
            "target_tab_end": round(self.target_tab_end(), 2),
        }


def paragraph_coordinate_frame(paragraph, source_x0, source_x1, *, page_left_x=0.0):
    """Build the coordinate frame for a rule placed inside ``paragraph``."""

    def _points(value):
        return float(getattr(value, "pt", 0.0) or 0.0)

    try:
        paragraph_format = paragraph.paragraph_format
        left_indent = _points(paragraph_format.left_indent)
        first_line = _points(paragraph_format.first_line_indent)
        section = paragraph.part.document.sections[-1]
        section_margin = _points(section.left_margin)
    except Exception:
        paragraph_format, left_indent, first_line, section_margin = None, 0.0, 0.0, 0.0
    hanging = abs(first_line) if first_line < 0.0 else 0.0
    return ParagraphCoordinateFrame(
        page_left_x=float(page_left_x),
        section_left_margin=section_margin,
        paragraph_left_indent=left_indent,
        paragraph_first_line_indent=first_line if first_line > 0.0 else 0.0,
        paragraph_hanging_indent=hanging,
        source_target_x0=float(source_x0),
        source_target_x1=float(source_x1),
    )


def underline_owner_runs(rules, runs, *, resolved_values=()):
    """The runs that a classified underline rule attaches to.

    A rule classified as a text/placeholder/value underline belongs to one
    owning span - the run whose own glyphs it was drawn beneath - not to every
    run it happens to touch.  Returning the run objects (not a geometric band)
    is what keeps a Word underline from spilling onto neighbouring text, since
    a delivered run's underline is all-or-nothing.
    """

    owners = []
    for rule in rules:
        if getattr(rule, "orientation", None) != "horizontal":
            continue
        relation = classify_rule_relation(rule, runs, resolved_values=resolved_values)
        if relation["relation_type"] not in (
            "TEXT_UNDERLINE",
            "PLACEHOLDER_UNDERLINE",
            "VALUE_UNDERLINE",
        ):
            continue
        rule_x0, rule_x1 = float(rule.bbox[0]), float(rule.bbox[2])
        rule_y = (float(rule.bbox[1]) + float(rule.bbox[3])) / 2.0
        best = None
        best_score = None
        for run in runs:
            if not str(getattr(run, "text", "") or "").strip():
                continue
            if not (
                float(run.bbox[1]) - 1.0 <= rule_y <= float(run.bbox[3]) + 1.0
            ):
                continue
            overlap = min(float(run.bbox[2]), rule_x1) - max(float(run.bbox[0]), rule_x0)
            if overlap <= 0.0:
                continue
            # Prefer the run whose extent actually contains the rule.
            contains = (
                float(run.bbox[0]) <= rule_x0 + 1.5
                and float(run.bbox[2]) >= rule_x1 - 1.5
            )
            score = (0 if contains else 1, -overlap)
            if best_score is None or score < best_score:
                best_score = score
                best = run
        if best is not None:
            owners.append((best, relation))
    return owners


def restore_inline_rule_blanks(text, runs, rules, slots, *, spans=None, resolved_values=()):
    """Restore source vector rules as blanks, using each rule's own relation.

    A rule is one of two things, and they are emitted differently:

    * a **fill gap** whose extent is clear of source text - emitted as a blank
      whose Word geometry is positioned from the rule's own ``x0``/``x1``;
    * a **text/placeholder/value underline** whose extent is occupied by source
      text - *not* a separate blank at all, so it must not receive a token here.
      The owning run keeps the source underline instead.

    A rule may bridge a gap between two spans on *any* visual line of the
    paragraph, not only the last one, so the whole mapped run sequence is
    searched.  Each rule is consumed at most once.
    """

    positions=[i for i,c in enumerate(text) if not c.isspace()]
    compact=''.join(text[i] for i in positions)
    mapped=[]
    cursor=0
    for run in runs:
        key=''.join(run.text.split())
        if not key: continue
        at=compact.find(key,cursor)
        if at>=0:
            mapped.append((run,positions[at],positions[at+len(key)-1]+1))
            cursor=at+len(key)

    span_evidence = list(spans) if spans else [run for run, _, _ in mapped]
    inserts=[]
    consumed=set()
    for rule in rules:
        if rule.orientation != 'horizontal':
            continue
        if id(rule) in consumed:
            continue
        relation = classify_rule_relation(rule, span_evidence, resolved_values=resolved_values)
        if relation["relation_type"] != "GAP_FILL_RULE":
            continue
        rule_x0, rule_x1 = float(rule.bbox[0]), float(rule.bbox[2])
        rule_y = (float(rule.bbox[1]) + float(rule.bbox[3])) / 2.0
        for (left, _, end), (right, start, _) in zip(mapped, mapped[1:]):
            size = left.font_size or 10.5
            if abs(left.bbox[1] - right.bbox[1]) > 3:
                continue
            if text[end:start].strip():
                continue
            if any(s.text_start is not None and s.text_start <= end <= s.text_end for s in slots):
                continue
            if not (
                left.bbox[2] - 1.5 <= rule_x0 <= right.bbox[0] + 1.5
                and left.bbox[2] - 1.5 <= rule_x1 <= right.bbox[0] + 1.5
            ):
                continue
            if abs(rule_y - left.bbox[3]) > max(6.0, size * 1.2):
                continue
            consumed.add(id(rule))
            inserts.append((end, inline_blank_token(rule_x1 - rule_x0, rule_x0, rule_x1)))
            break

    for at,blank in reversed(inserts): text=text[:at]+blank+text[at:]
    def shifted(offset):
        return None if offset is None else offset+sum(len(blank) for at,blank in inserts if at<=offset)
    remapped=[s.model_copy(update={'text_start':shifted(s.text_start),'text_end':shifted(s.text_end)}) for s in slots]
    return text,remapped,len(inserts)


INLINE_COMPOSITION_PREFIX = '\ue002COMPOSE:'
INLINE_COMPOSITION_SUFFIX = '\ue003'


def composition_segments(rule, spans, *, baseline_tolerance=4.0):
    """Ordered EMPTY/TEXT segments for a rule that spans whitespace and text.

    A rule whose extent is partly occupied by source glyphs is neither a pure
    fill gap nor a pure text underline: it is a composition.  The segments are
    derived from the source glyph boxes themselves, so the physical width
    authority stays the source rule extent.

    Returns ``None`` when a rule boundary would cut through a glyph, because
    that cannot be represented by safe inline Word constructs.
    """

    rule_x0, rule_x1 = float(rule.bbox[0]), float(rule.bbox[2])
    rule_y = (float(rule.bbox[1]) + float(rule.bbox[3])) / 2.0
    owners = []
    for span in spans:
        if not getattr(span, "text", "").strip():
            continue
        size = float(getattr(span, "font_size", None) or 10.5)
        if not (float(span.bbox[1]) - baseline_tolerance <= rule_y
                <= float(span.bbox[3]) + max(6.0, size * 1.2)):
            continue
        owners.append(span)
    owners.sort(key=lambda span: float(span.bbox[0]))
    inside, straddling = [], []
    for span in owners:
        x0, x1 = float(span.bbox[0]), float(span.bbox[2])
        if x1 <= rule_x0 + 0.05 or x0 >= rule_x1 - 0.05:
            continue
        if x0 < rule_x0 - 0.05 or x1 > rule_x1 + 0.05:
            straddling.append(span)
        else:
            inside.append(span)
    if straddling or not inside:
        return None
    segments = []
    cursor = rule_x0
    for span in inside:
        x0, x1 = float(span.bbox[0]), float(span.bbox[2])
        if x0 - cursor > 0.5:
            segments.append(
                {"segment_type": "EMPTY_RULE_SEGMENT", "source_x0": round(cursor, 2),
                 "source_x1": round(x0, 2), "source_text": None}
            )
        segments.append(
            {"segment_type": "TEXT_RULE_SEGMENT", "source_x0": round(x0, 2),
             "source_x1": round(x1, 2), "source_text": span.text}
        )
        cursor = x1
    if rule_x1 - cursor > 0.5:
        segments.append(
            {"segment_type": "EMPTY_RULE_SEGMENT", "source_x0": round(cursor, 2),
             "source_x1": round(rule_x1, 2), "source_text": None}
        )
    if len(segments) < 2:
        return None
    return segments


def inline_rule_composition_token(source_rule_id, segments):

    parts = [str(source_rule_id)]
    for segment in segments:
        kind = "E" if segment["segment_type"] == "EMPTY_RULE_SEGMENT" else "T"
        if segment.get("needs_anchor"):
            # Marked when the rule starts beyond the preceding text, so the
            # emitter reaches the anchor with a tab instead of assuming the
            # cursor is already on it.
            kind = "A" + kind
        parts.append(
            "%s,%.2f,%.2f,%s"
            % (
                kind,
                float(segment["source_x0"]),
                float(segment["source_x1"]),
                "" if segment["source_text"] is None else str(segment["source_text"]),
            )
        )
    return INLINE_COMPOSITION_PREFIX + "|".join(parts) + INLINE_COMPOSITION_SUFFIX


def parse_inline_rule_composition_token(payload):
    """Decode a composition token into ``(source_rule_id, segments)``."""

    parts = str(payload).split("|")
    if len(parts) < 2:
        return None
    identity = parts[0].split("~")
    source_rule_id = identity[0] or None
    relation_type = identity[1] if len(identity) > 1 else None
    occupancy = None
    if len(identity) > 2:
        try:
            occupancy = float(identity[2])
        except ValueError:
            occupancy = None
    segments = []
    for index, part in enumerate(parts[1:], start=1):
        fields = part.split(",")
        if len(fields) < 3:
            return None
        kind, x0, x1 = fields[0], float(fields[1]), float(fields[2])
        text = ",".join(fields[3:]) if len(fields) > 3 else ""
        needs_anchor = kind.startswith("A")
        if needs_anchor:
            kind = kind[1:] or "E"
        segments.append(
            {
                "composition_segment_id": "%s-S%d"
                % (source_rule_id or "COMPOSITION", index),
                "segment_type": (
                    "EMPTY_RULE_SEGMENT" if kind == "E" else "TEXT_RULE_SEGMENT"
                ),
                "source_x0": x0,
                "source_x1": x1,
                "source_text": text or None,
                "source_rule_id": source_rule_id,
                "needs_anchor": needs_anchor,
            }
        )
    return source_rule_id, segments, {
        "source_relation_type": relation_type,
        "text_occupancy": occupancy,
        "composition_eligibility_evidence": "GLYPH_OCCUPANCY_PATTERN_AND_ALIGNED_BOUNDARIES",
    }


# ---------------------------------------------------------------------------
# Source visual line emission assembly
# ---------------------------------------------------------------------------
#
# A source visual line is one *physical printed row* of the source page.  The
# PDF frequently extracts such a row as several lines (glyphs, the digit run a
# rule carries, a trailing glyph group), and one reconstructed source paragraph
# can own several rows.  Everything on one physical row is positioned against
# that row's own origin, so the row - not the extraction line and not the
# semantic element - is the unit the renderer has to assemble before it emits
# anything.  The structures below are renderer scheduling state: they order and
# group existing representations, they never classify a rule or bind a fact.

#: Two extracted source lines are the same physical printed row when their tops
#: agree this closely.
SOURCE_VISUAL_ROW_TOLERANCE = 2.5

#: Emission atom kinds.  A ``POSITIONED_BLANK`` is a source gap rule emitted at
#: its own ``x0``/``x1``; a ``RULE_COMPOSITION`` is a rule that spans whitespace
#: and its own source glyphs; everything else is preserved source text.
ATOM_POSITIONED_BLANK = "POSITIONED_BLANK"
ATOM_RULE_COMPOSITION = "RULE_COMPOSITION"
ATOM_PRESERVED_TEXT = "PRESERVED_TEXT"

SOURCE_VISUAL_LINE_EMISSION_SCHEMA = "source_visual_line_emission_plan/1"

_ATOM_TOKEN_PATTERN = re.compile(
    "("
    + re.escape(INLINE_BLANK_PREFIX) + ".*?" + re.escape(INLINE_BLANK_SUFFIX)
    + "|"
    + re.escape(INLINE_COMPOSITION_PREFIX) + ".*?" + re.escape(INLINE_COMPOSITION_SUFFIX)
    + ")"
)


def source_visual_rows(source_lines, *, tolerance=SOURCE_VISUAL_ROW_TOLERANCE):
    """Group parsed source lines into physical visual rows, in source order.

    The grouping is pure source geometry - the extracted lines' own top edges -
    so it never depends on a page number, a rule id or literal text.
    """

    rows: list = []
    for line in source_lines or ():
        if not rows or abs(float(line.bbox[1]) - float(rows[-1][0].bbox[1])) > tolerance:
            rows.append([])
        rows[-1].append(line)
    return rows


@dataclass
class SourceVisualLineAtom:
    """One emission atom of a source visual line, retained with provenance."""

    atom_kind: str
    source_x0: float
    source_x1: float | None = None
    source_text: str = ""
    source_rule_id: str | None = None
    representation_kind: str | None = None
    geometry_source: str = "SOURCE_RULE_SPAN"

    def as_dict(self) -> dict:
        return {
            "atom_kind": self.atom_kind,
            "source_x0": round(float(self.source_x0), 2),
            "source_x1": (
                None if self.source_x1 is None else round(float(self.source_x1), 2)
            ),
            "source_text": self.source_text,
            "source_rule_id": self.source_rule_id,
            "representation_kind": self.representation_kind,
            "geometry_source": self.geometry_source,
        }


@dataclass
class SourceVisualLineEmissionPlan:
    """What one source physical row must emit, and in which order.

    Answers a single question: *which representations belong to one Word
    paragraph because the source places them on one physical visual line?*  The
    plan owns no semantics - it schedules representations the semantic compiler
    has already produced, in increasing source-x order, so a later atom can
    never make an earlier positioned atom unreachable.
    """

    source_page: int
    source_line_identity: str
    source_row_index: int
    source_y0: float
    source_y1: float
    container_x0: float
    container_x1: float
    owning_element_kind: str = "LogicalParagraph"
    atoms: list = field(default_factory=list)
    #: True when the row is not the element's first row and carries a positioned
    #: atom: continuous flow cannot guarantee this row's own origin, so the row
    #: is assembled inside its own paragraph context before it is emitted.
    needs_own_line_context: bool = False
    #: Whether the owning element actually has the source-form-line paragraph
    #: machinery activated.  Without it the row keeps the accepted inline
    #: emission, and the gap is recorded instead of silently assumed away.
    line_context_available: bool = False
    owns_line_context: bool = False
    generated_paragraph_index: int | None = None
    source_locator: object | None = None

    @property
    def positioned_atoms(self):
        return [
            atom for atom in self.atoms if atom.atom_kind != ATOM_PRESERVED_TEXT
        ]

    @property
    def source_rule_ids(self):
        return [
            atom.source_rule_id
            for atom in self.atoms
            if atom.source_rule_id
        ]

    def as_dict(self) -> dict:
        return {
            "schema": SOURCE_VISUAL_LINE_EMISSION_SCHEMA,
            "source_page": self.source_page,
            "source_line_identity": self.source_line_identity,
            "source_row_index": self.source_row_index,
            "source_y0": round(float(self.source_y0), 2),
            "source_y1": round(float(self.source_y1), 2),
            "container_x0": round(float(self.container_x0), 2),
            "container_x1": round(float(self.container_x1), 2),
            "owning_element_kind": self.owning_element_kind,
            "atom_count": len(self.atoms),
            "atoms": [atom.as_dict() for atom in self.atoms],
            "atom_order_is_source_x": self.atom_order_is_source_x(),
            "needs_own_line_context": self.needs_own_line_context,
            "line_context_available": self.line_context_available,
            "owns_line_context": self.owns_line_context,
            "generated_paragraph_index": self.generated_paragraph_index,
        }

    def atom_order_is_source_x(self) -> bool:
        xs = [float(atom.source_x0) for atom in self.atoms]
        return all(later >= earlier - 1e-6 for earlier, later in zip(xs, xs[1:]))


def plan_source_visual_line(
    text,
    *,
    source_page: int,
    source_row_index: int,
    source_lines,
    owning_element_kind: str = "LogicalParagraph",
    rule_spans=None,
    source_locator=None,
) -> SourceVisualLineEmissionPlan:
    """Assemble one source visual line's emission atoms in source-x order.

    ``text`` is the row's already-restored source text: the token stream the
    existing representation restorers produced, in which every positioned rule
    is carried by its own inline token.  The atoms are therefore read off in the
    order the source itself places them, and the plan reports whether that order
    is monotonic in source x.
    """

    lines = list(source_lines or ())
    if lines:
        y0 = min(float(line.bbox[1]) for line in lines)
        y1 = max(float(line.bbox[3]) for line in lines)
        x0 = min(float(line.bbox[0]) for line in lines)
        x1 = max(float(line.bbox[2]) for line in lines)
    else:
        y0 = y1 = x0 = x1 = 0.0
    atoms: list = []
    cursor = 0
    payload = str(text or "")
    for match in _ATOM_TOKEN_PATTERN.finditer(payload):
        if match.start() > cursor:
            literal = payload[cursor:match.start()]
            if literal.strip():
                atoms.append(
                    SourceVisualLineAtom(
                        atom_kind=ATOM_PRESERVED_TEXT,
                        source_x0=(
                            float(atoms[-1].source_x1)
                            if atoms and atoms[-1].source_x1 is not None
                            else x0
                        ),
                        source_x1=None,
                        source_text=literal,
                        representation_kind="SOURCE_PRESERVED_TEXT",
                        geometry_source=(
                            "SOURCE_PREDECESSOR_RULE_END"
                            if atoms and atoms[-1].source_x1 is not None
                            else "SOURCE_ROW_ORIGIN"
                        ),
                    )
                )
        token = match.group(1)
        if token.startswith(INLINE_BLANK_PREFIX):
            parsed = parse_inline_blank_token(
                token[len(INLINE_BLANK_PREFIX):-len(INLINE_BLANK_SUFFIX)]
            )
            if parsed is not None:
                _width, blank_x0, blank_x1 = parsed
                atoms.append(
                    SourceVisualLineAtom(
                        atom_kind=ATOM_POSITIONED_BLANK,
                        source_x0=float(blank_x0),
                        source_x1=float(blank_x1),
                        representation_kind="SOURCE_POSITIONED_UNDERLINED_TAB",
                        source_rule_id=_rule_id_for_span(
                            rule_spans, float(blank_x0), float(blank_x1)
                        ),
                    )
                )
        else:
            parsed = parse_inline_rule_composition_token(
                token[len(INLINE_COMPOSITION_PREFIX):-len(INLINE_COMPOSITION_SUFFIX)]
            )
            if parsed is not None:
                source_rule_id, segments, _evidence = parsed
                if segments:
                    atoms.append(
                        SourceVisualLineAtom(
                            atom_kind=ATOM_RULE_COMPOSITION,
                            source_x0=float(segments[0]["source_x0"]),
                            source_x1=float(segments[-1]["source_x1"]),
                            source_text="".join(
                                segment["source_text"] or ""
                                for segment in segments
                                if segment["segment_type"] == "TEXT_RULE_SEGMENT"
                            ),
                            source_rule_id=source_rule_id,
                            representation_kind="SOURCE_RULE_COMPOSITION",
                        )
                    )
        cursor = match.end()
    if cursor < len(payload):
        literal = payload[cursor:]
        if literal.strip():
            atoms.append(
                SourceVisualLineAtom(
                    atom_kind=ATOM_PRESERVED_TEXT,
                    source_x0=(
                        float(atoms[-1].source_x1)
                        if atoms and atoms[-1].source_x1 is not None
                        else x0
                    ),
                    source_x1=None,
                    source_text=literal,
                    representation_kind="SOURCE_PRESERVED_TEXT",
                    geometry_source=(
                        "SOURCE_PREDECESSOR_RULE_END"
                        if atoms and atoms[-1].source_x1 is not None
                        else "SOURCE_ROW_ORIGIN"
                    ),
                )
            )
    positioned = [
        atom for atom in atoms if atom.atom_kind != ATOM_PRESERVED_TEXT
    ]
    return SourceVisualLineEmissionPlan(
        source_page=int(source_page),
        source_line_identity="S%d-L%d" % (int(source_page), int(source_row_index) + 1),
        source_row_index=int(source_row_index),
        source_y0=y0,
        source_y1=y1,
        container_x0=x0,
        container_x1=x1,
        owning_element_kind=str(owning_element_kind),
        atoms=atoms,
        needs_own_line_context=bool(positioned) and int(source_row_index) > 0,
        source_locator=source_locator,
    )


def _rule_id_for_span(rule_spans, x0, x1, *, tolerance=1.0):
    """The registered source rule whose span this blank token was cut from."""

    for entry in rule_spans or ():
        try:
            span_x0, span_x1, rule_id = entry
        except (TypeError, ValueError):
            continue
        if (
            abs(float(span_x0) - float(x0)) <= tolerance
            and abs(float(span_x1) - float(x1)) <= tolerance
        ):
            return rule_id
    return None


def character_composition_segments(rule, mapped, *, tolerance=0.75, self_offsets=None,
                                  container_text=None):
    """Ordered composition segments for a rule, from EXACT_PDF_CHAR evidence.

    ``mapped`` is a sequence of ``(run, logical_start, logical_end)``.  The
    rule's boundaries must each coincide with a real character boundary
    recorded in the source; geometry that was approximated from a run width is
    never admissible.  ``self_offsets`` maps ``id(run)`` to the index the run's
    own first character holds in the container text, which is the coordinate
    space the returned offsets and the renderer's ``mapped`` offsets share.
    Returns ``(segments, start_offset, end_offset, needs_anchor)``, or ``None``
    when the rule is not an evidence-backed composition.
    """

    rule_x0, rule_x1 = float(rule.bbox[0]), float(rule.bbox[2])
    rule_y = (float(rule.bbox[1]) + float(rule.bbox[3])) / 2.0
    self_offsets = self_offsets or {}
    atoms = []
    for run, logical_start, _logical_end in mapped:
        characters = [
            item for item in getattr(run, "characters", ())
            if item.evidence_kind == "EXACT_PDF_CHAR" and item.character.strip()
        ]
        if not characters:
            continue
        size = float(getattr(run, "font_size", 0.0) or 10.5)
        if not (float(run.bbox[1]) - 4.0 <= rule_y
                <= float(run.bbox[3]) + max(6.0, size * 1.2)):
            continue
        # ``CharacterGeometry.index`` is the record's position in the *span's own*
        # character stream, which is not always the run's text index: a whitespace
        # or soft-hyphen record may be present in one stream and not the other.
        # Pairing the two by that index can therefore drop a real source
        # character out of the split.  The record is instead paired with the run's
        # own text character at the same ordinal position, and that character's
        # index *in the container text* is the offset - the same coordinate the
        # renderer's ``mapped`` range is expressed in.  Both ends then describe
        # the same characters, so the covered range names exactly what the
        # segments re-emit.
        #
        # ``logical_start``/``self_offsets`` give the container index of the run's
        # first *visible* character, so the offset advances over the visible
        # characters only: the source's own spaces inside the run consume no text
        # position
        # and must not shift the character the offset names.
        first_visible = next(
            (index for index, character in enumerate(run.text) if not character.isspace()),
            None,
        )
        if first_visible is None:
            continue
        run_start = self_offsets.get(id(run), logical_start)
        run_atom_offsets = {}
        seen_characters = 0
        for index, character in enumerate(run.text):
            if character.isspace():
                continue
            run_atom_offsets[seen_characters] = run_start + index - first_visible
            seen_characters += 1
        visible = [item for item in characters]
        visible_offsets = list(run_atom_offsets.values())
        if len(visible) != len(visible_offsets):
            # The character records and the run text disagree on how many visible
            # characters there are, so no character-to-offset pairing is provable
            # and a split would drop source text.  Fail closed: the rule is not
            # an evidence-backed composition and keeps the accepted whole-run
            # representation.
            return None
        for item, offset in zip(visible, visible_offsets):
            atoms.append({
                "x0": float(item.x0),
                "x1": float(item.x1),
                "character": item.character,
                "offset": offset,
            })
    if not atoms:
        return None
    atoms.sort(key=lambda atom: (atom["x0"], atom["offset"]))

    # The covered character range is the run of glyphs the rule's measured extent
    # actually covers.  The rule's own origin is where it starts, so the first
    # glyph that begins inside the rule opens the range, and the range then grows
    # through the glyphs that still fit inside it.  Both ends are expressed in the
    # container text's own coordinates, so the covered range names exactly the
    # characters the segments re-emit instead of a differently-numbered run.
    anchor = next(
        (
            index for index, atom in enumerate(atoms)
            if atom["x0"] >= rule_x0 - tolerance and atom["x0"] <= rule_x1 + tolerance
        ),
        None,
    )
    if anchor is None:
        return None
    start_position = atoms[anchor]["offset"]
    end_position = start_position
    for atom in atoms:
        if (atom["x0"] < rule_x0 - tolerance
                or atom["x1"] > rule_x1 + tolerance
                or (atom["x0"] + atom["x1"]) / 2.0 > rule_x1):
            continue
        if atom["offset"] < start_position:
            # A glyph the rule covers but that precedes its own first covered
            # glyph cannot be part of a contiguous range without also taking
            # everything between them, so it is not covered.
            continue
        end_position = max(end_position, atom["offset"] + 1)
    if end_position <= start_position:
        return None

    inside = [
        atom for atom in atoms
        if atom["x0"] >= rule_x0 - tolerance
        and atom["x1"] <= rule_x1 + tolerance
        and start_position <= atom["offset"] < end_position
    ]
    if not inside:
        return None

    segments = []
    cursor = rule_x0
    for atom in inside:
        if atom["x0"] - cursor > tolerance:
            segments.append({
                "segment_type": "EMPTY_RULE_SEGMENT",
                "source_x0": round(cursor, 2),
                "source_x1": round(atom["x0"], 2),
                "source_text": None,
            })
        if (segments
                and segments[-1]["segment_type"] == "TEXT_RULE_SEGMENT"
                and abs(segments[-1]["source_x1"] - atom["x0"]) <= tolerance):
            segments[-1]["source_x1"] = round(atom["x1"], 2)
            segments[-1]["source_text"] += atom["character"]
        else:
            segments.append({
                "segment_type": "TEXT_RULE_SEGMENT",
                "source_x0": round(atom["x0"], 2),
                "source_x1": round(atom["x1"], 2),
                "source_text": atom["character"],
            })
        cursor = atom["x1"]
    if rule_x1 - cursor > tolerance:
        segments.append({
            "segment_type": "EMPTY_RULE_SEGMENT",
            "source_x0": round(cursor, 2),
            "source_x1": round(rule_x1, 2),
            "source_text": None,
        })
    if not any(s["segment_type"] == "TEXT_RULE_SEGMENT" for s in segments):
        return None
    # Snap the outer edges onto the rule extent where the boundary is aligned,
    # so the declared composition is the physical rule being represented.
    if abs(segments[0]["source_x0"] - rule_x0) <= tolerance:
        segments[0]["source_x0"] = round(rule_x0, 2)
    if abs(segments[-1]["source_x1"] - rule_x1) <= tolerance:
        segments[-1]["source_x1"] = round(rule_x1, 2)

    # A rule that covers one whole run exactly is an ordinary run underline,
    # already handled by the accepted path; it is not a composition.
    covered = [
        (run, start, end) for run, start, end in mapped
        if start < end_position and start_position < end
    ]
    if len(covered) == 1 and not any(
        segment["segment_type"] == "EMPTY_RULE_SEGMENT" for segment in segments
    ):
        _run, run_start, run_end = covered[0]
        if start_position <= run_start and end_position >= run_end:
            return None

    preceding = [atom for atom in atoms if atom["offset"] < start_position]
    needs_anchor = True
    if preceding:
        last = max(preceding, key=lambda atom: atom["offset"])
        needs_anchor = (rule_x0 - last["x1"]) > 1.0
    return segments, start_position, end_position, needs_anchor


#: Production geometry intent for a source rule.  Derived from source-local
#: evidence only, never from a page number, a rule id or a literal string.
GEOMETRY_INTENT_EXACT_SOURCE_SPAN = "EXACT_SOURCE_SPAN"
GEOMETRY_INTENT_ANCHOR_START_ONLY = "ANCHOR_START_ONLY"
GEOMETRY_INTENT_NO_EXACT_SPAN_INTENT = "NO_EXACT_SPAN_INTENT"

#: Transformation policy of one source rule: what happens to the source text the
#: rule covers.
TRANSFORMATION_FIXED_EMPTY_SLOT = "FIXED_EMPTY_SLOT"
TRANSFORMATION_RESOLVED_VALUE_IN_FIXED_SLOT = "RESOLVED_VALUE_IN_FIXED_SLOT"
TRANSFORMATION_PLACEHOLDER_REPLACED_BY_VALUE = "PLACEHOLDER_REPLACED_BY_VALUE"
TRANSFORMATION_SOURCE_VALUE_UNDERLINE = "SOURCE_VALUE_UNDERLINE"
TRANSFORMATION_PRESERVE_SOURCE_PLACEHOLDER = "PRESERVE_SOURCE_PLACEHOLDER"
TRANSFORMATION_UNRESOLVED = "UNRESOLVED"

#: Authoritative policy -> intent mapping.  A rule whose text a resolved value
#: replaces, or which receives a resolved value in a fixed slot, is anchored at
#: its start only: the placeholder's original x1 stops being authoritative once
#: it is replaced.  Every other policy keeps the rule's own physical extent.
_TRANSFORMATION_GEOMETRY_INTENT = {
    TRANSFORMATION_FIXED_EMPTY_SLOT: GEOMETRY_INTENT_EXACT_SOURCE_SPAN,
    TRANSFORMATION_SOURCE_VALUE_UNDERLINE: GEOMETRY_INTENT_EXACT_SOURCE_SPAN,
    TRANSFORMATION_PRESERVE_SOURCE_PLACEHOLDER: GEOMETRY_INTENT_EXACT_SOURCE_SPAN,
    TRANSFORMATION_PLACEHOLDER_REPLACED_BY_VALUE: GEOMETRY_INTENT_ANCHOR_START_ONLY,
    TRANSFORMATION_RESOLVED_VALUE_IN_FIXED_SLOT: GEOMETRY_INTENT_ANCHOR_START_ONLY,
}


def source_rule_geometry_intent(transformation_policy):
    """Geometry intent of one source rule, from its transformation policy.

    Fails closed: a policy that production could not establish from reliable
    evidence has no exact-span intent, so it can never authorise a composition.
    """

    return _TRANSFORMATION_GEOMETRY_INTENT.get(
        transformation_policy, GEOMETRY_INTENT_NO_EXACT_SPAN_INTENT
    )


def _fact_field_key(name) -> str:
    """Canonical key of a fact field name, whether a member or a plain string."""

    return str(getattr(name, "value", name)).strip().upper()


def _rule_source_glyphs(rule, spans):
    """Source text inside the rule's own extent, from the PDF spans.

    Returns ``(text, has_interior_gap)``.  This is source evidence, so the
    transformation policy never depends on a representation having been built:
    the dependency runs source evidence -> policy -> intent -> representation.
    """

    if not spans:
        return "", False
    rule_x0, rule_x1 = float(rule.bbox[0]), float(rule.bbox[2])
    rule_y0, rule_y1 = float(rule.bbox[1]), float(rule.bbox[3])
    inside = []
    for span in spans:
        try:
            x0, y0, x1, y1 = (float(value) for value in span.bbox)
        except (TypeError, ValueError):
            continue
        # A source form underline is drawn *below* the text it underlines, and a
        # physical rule is a zero-height line, so ownership is decided by the
        # glyph's own measured line band widened downward by its own line height
        # - not by a rectangle intersection that a zero-height rule can never
        # satisfy, and not by an arbitrary tolerance.
        band = max(y1 - y0, 0.0)
        if rule_y1 < y0 - 2.0 or rule_y0 > y1 + 0.75 * band + 2.0:
            continue
        if x1 <= rule_x0 + 0.5 or x0 >= rule_x1 - 0.5:
            continue
        inside.append((max(x0, rule_x0), min(x1, rule_x1), str(getattr(span, "text", ""))))
    if not inside:
        return "", False
    inside.sort(key=lambda item: item[0])
    text = "".join(item[2] for item in inside).strip()
    has_gap = (inside[0][0] - rule_x0 > 1.0) or (rule_x1 - inside[-1][1] > 1.0)
    return text, has_gap


def _rule_source_glyphs_from_boxes(rule_x0, rule_x1, rule_y0, rule_y1, boxes):
    """Source text a physical rule covers, from boxes carrying real geometry.

    One generic rule/glyph ownership rule: a physical rule is a zero-height line
    drawn below the text it underlines, so ownership is decided by the glyph's
    own measured line band widened downward by its own line height, never by a
    rectangle intersection and never by a per-rule tolerance constant.
    """

    inside = []
    for box in boxes:
        bbox = getattr(box, "bbox", None)
        if not bbox:
            continue
        try:
            x0, y0, x1, y1 = (float(value) for value in bbox)
        except (TypeError, ValueError):
            continue
        band = max(y1 - y0, 0.0)
        if rule_y1 < y0 - 2.0 or rule_y0 > y1 + 0.75 * band + 2.0:
            continue
        if x1 <= rule_x0 + 0.5 or x0 >= rule_x1 - 0.5:
            continue
        inside.append((max(x0, rule_x0), min(x1, rule_x1), str(getattr(box, "text", ""))))
    if not inside:
        return "", False
    inside.sort(key=lambda item: item[0])
    text = "".join(item[2] for item in inside).strip()
    has_gap = (inside[0][0] - rule_x0 > 1.0) or (rule_x1 - inside[-1][1] > 1.0)
    return text, has_gap


def compile_source_rule_glyph_evidence(source_pages):
    """Compile rule -> covered source text for the whole document, once.

    This is the pre-render semantic boundary for source glyph evidence: it runs
    over the parsed source pages rather than over whichever rendering fragment
    happens to be active, so a rule's transformation evidence no longer depends
    on fragment-local state.  Returns a mapping keyed by
    ``(source_page, x0, x1, y)`` rounded to a tenth of a point.
    """

    evidence = {}
    for page in source_pages or ():
        boxes = []
        for paragraph in getattr(page, "paragraphs", None) or ():
            for run in getattr(paragraph, "runs", None) or ():
                if str(getattr(run, "text", "")).strip():
                    boxes.append(run)
        for rule in getattr(page, "lines", None) or ():
            if str(getattr(rule, "orientation", "horizontal")) != "horizontal":
                continue
            try:
                x0, y0, x1, y1 = (float(value) for value in rule.bbox)
            except (TypeError, ValueError):
                continue
            if x1 - x0 <= 1.0:
                continue
            text, has_gap = _rule_source_glyphs_from_boxes(x0, x1, y0, y1, boxes)
            evidence[
                (int(getattr(page, "page", 0)), round(x0, 1), round(x1, 1), round(y0, 1))
            ] = (text, has_gap)
    return evidence


_SOURCE_VISUAL_CHILD_ATTRS = ("paragraphs", "tables", "rows", "cells", "runs", "lines", "spans")
_SOURCE_OWNERSHIP_ATTRS = {"tables": "table", "rows": "row", "cells": "cell"}


def iter_source_text_boxes(container, *, depth=0, ownership=(), path=()):
    """Every source text object with geometry, carrying its container path.

    Yields ``(obj, ownership, path, is_leaf)``.  ``ownership`` is a tuple of
    ``(kind, index)`` pairs naming the table/row/cell that contains the object,
    so structural relationships are never recovered later by matching text.
    Containers are yielded as well as leaves, because a paragraph or cell can
    carry the label text that its individual runs do not.
    """

    if container is None or depth > 6:
        return
    if isinstance(container, (str, bytes, int, float, bool)):
        return
    children = []
    for name in _SOURCE_VISUAL_CHILD_ATTRS:
        value = getattr(container, name, None)
        if not isinstance(value, (list, tuple)):
            continue
        kind = _SOURCE_OWNERSHIP_ATTRS.get(name)
        for index, child in enumerate(value):
            if kind is None:
                children.append((child, ownership, path))
            else:
                children.append(
                    (
                        child,
                        tuple(ownership) + ((kind, index),),
                        tuple(path) + ("%s:%d" % (kind, index),),
                    )
                )
    text = getattr(container, "text", None)
    if (
        isinstance(text, str)
        and text.strip()
        and getattr(container, "bbox", None) is not None
    ):
        yield container, tuple(ownership), tuple(path), not children
    for child, child_ownership, child_path in children:
        yield from iter_source_text_boxes(
            child, depth=depth + 1, ownership=child_ownership, path=child_path
        )


def compile_source_visual_text_boxes(source_page):
    """Normalized, deduplicated source text boxes with structural ownership.

    The same visible text can arrive through more than one parsed view, so exact
    duplicates - same geometry, same visible text - collapse into one box, and
    the collapsed box keeps the strongest structural ownership available.
    Returns ``(boxes, report)`` with boxes ordered by vertical band then x.
    """

    raw = 0
    order = []
    seen = {}
    for obj, ownership, path, is_leaf in iter_source_text_boxes(source_page):
        bbox = getattr(obj, "bbox", None)
        try:
            x0, y0, x1, y1 = (float(value) for value in bbox)
        except (TypeError, ValueError):
            continue
        text = str(getattr(obj, "text", "") or "")
        if not text.strip():
            continue
        raw += 1
        key = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1), text)
        box = {
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "text": text,
            "kind": type(obj).__name__,
            "ownership": tuple(ownership),
            "container_path": ".".join(path),
            "is_leaf": bool(is_leaf),
        }
        existing = seen.get(key)
        if existing is None:
            seen[key] = box
            order.append(key)
        else:
            if len(box["ownership"]) > len(existing["ownership"]):
                existing["ownership"] = box["ownership"]
                existing["container_path"] = box["container_path"]
            existing["is_leaf"] = existing["is_leaf"] or box["is_leaf"]
    boxes = [seen[key] for key in order]
    boxes.sort(key=lambda item: (round(item["y0"], 1), item["x0"]))
    report = {
        "source_visual_boxes_raw_count": raw,
        "source_visual_boxes_count": len(boxes),
        "source_visual_boxes_removed_count": raw - len(boxes),
    }
    return boxes, report


def _visual_row_band(box, *, tolerance=2.5):
    """The source visual row a unified text box belongs to.

    A row is a set of boxes sharing one physical baseline, quantized with the
    same tolerance the source row grouping uses, so two boxes compare equal
    exactly when the source itself places them on one visual line.  This is
    geometry, never text or document order.
    """

    return round(float(box["y0"]) / float(tolerance))


def source_rule_structural_context(page, rule_x0, rule_y0, rule_x1, rule_y1):
    """Structural neighbourhood of a physical rule, most specific first.

    Returns ``(selected, evidence)`` where evidence records the owning
    container text and the same-cell / same-row / adjacent-row texts, each
    ordered deterministically and bounded to the rule's own structural family.
    """

    unified, _report = compile_source_visual_text_boxes(page)
    mid_x = (rule_x0 + rule_x1) / 2.0
    mid_y = (rule_y0 + rule_y1) / 2.0
    owners = []
    for box in unified:
        if box["x0"] - 1.0 <= mid_x <= box["x1"] + 1.0 and box["y0"] - 1.0 <= mid_y <= box["y1"] + 1.0:
            owners.append(box)
    owners.sort(key=lambda box: (box["x1"] - box["x0"]) * max(box["y1"] - box["y0"], 0.0))
    evidence = {
        "owning_container_text": "",
        "owning_container_kind": "",
        "same_cell_texts": [],
        "same_row_texts": [],
        "adjacent_row_texts": [],
        "preceding_container_texts": [],
    }
    candidates = []
    if owners:
        owner = owners[0]
        evidence["owning_container_text"] = owner["text"]
        evidence["owning_container_kind"] = owner["kind"]
        evidence["container_path"] = owner["container_path"]
        candidates.append(("owning_container", owner["text"]))
        own = owner["ownership"]
        if not owner["is_leaf"]:
            # A form label can be the tail of the container that shares the
            # field's own visual row - the source sentence is continuous across
            # the field.  Exactly one preceding container is offered, never an
            # arbitrary page-wide search, and only when the field's owner is
            # itself a structural container.
            #
            # Adjacency is decided by the *source visual row*, never by document
            # order: a paragraph block holds several visual rows, so the box that
            # simply precedes the owner in the unified order is frequently the
            # label of a completely different clause one or more lines above (an
            # upstream document heading, for example).  Binding a fact from such a
            # row would print a value the field's own label never asked for, so a
            # preceding container is only evidence when it shares the rule's row.
            own_band = _visual_row_band(owner)
            position = unified.index(owner)
            for back in (1, 2):
                if position - back < 0:
                    break
                previous = unified[position - back]
                if _visual_row_band(previous) != own_band:
                    continue
                evidence["preceding_container_texts"].append(previous["text"])
                candidates.append(("preceding_container", previous["text"]))
        if own:
            for box in unified:
                if box is owner or not box["ownership"]:
                    continue
                other = box["ownership"]
                if other == own:
                    evidence["same_cell_texts"].append(box["text"])
                    candidates.append(("same_cell", box["text"]))
                elif other[:-1] == own[:-1]:
                    evidence["same_row_texts"].append(box["text"])
                    candidates.append(("same_row", box["text"]))
                elif (
                    len(own) >= 2
                    and len(other) >= 2
                    and own[-2][0] == "row"
                    and other[-2][0] == "row"
                    and other[: len(own) - 2] == own[: len(own) - 2]
                    and abs(other[-2][1] - own[-2][1]) == 1
                ):
                    evidence["adjacent_row_texts"].append(box["text"])
                    candidates.append(("adjacent_row", box["text"]))
    return candidates, evidence


def source_rule_line_context(page, rule_x0, rule_y0, rule_y1):
    """Ordered source runs on a physical rule's own visual line.

    Returns ``(boxes, preceding_text)`` where boxes are ``(x0, x1, text)``
    ordered by x, and ``preceding_text`` is the source text sitting before the
    rule on that same line - the deterministic hint evidence for a form field.
    """

    unified, _report = compile_source_visual_text_boxes(page)
    boxes = []
    for box in unified:
        if not box["is_leaf"]:
            continue
        y0, y1 = box["y0"], box["y1"]
        band = max(y1 - y0, 0.0)
        # The accepted zero-height ownership rule: a physical rule is a line
        # drawn below its own text, so the glyph's measured band governs.
        if rule_y1 < y0 - 2.0 or rule_y0 > y1 + 0.75 * band + 2.0:
            continue
        boxes.append((box["x0"], box["x1"], box["text"]))
    boxes.sort(key=lambda item: item[0])
    preceding = "".join(text for x0, x1, text in boxes if x1 <= rule_x0 + 0.5)
    return boxes, preceding.strip()


def _field_hint_candidates(text):
    """Deterministic hint candidates from the source text before a rule."""

    tail = (text or "").strip()
    if not tail:
        return ()
    window = tail[-24:]
    candidates = [window, tail]
    for separator in ("：", ":", "（", "(", "，", ",", "、", "；", ";", " ", "\u3000"):
        if separator in window:
            candidates.append(window.partition(separator)[0])
            candidates.append(window.rsplit(separator, 1)[-1])
    # A label can follow upstream text on the same source line, so trailing
    # substrings are offered too, longest first.
    for length in range(min(len(window), 10), 1, -1):
        candidates.append(window[-length:])
    ordered = []
    for candidate in candidates:
        candidate = candidate.strip().strip("，,、；;")
        if candidate and candidate not in ordered:
            ordered.append(candidate)
    return tuple(ordered)


def _single_distinct_field(fields):
    """The one fact field a set of hint-derived candidates names, or ``[]``.

    A rule can offer the same field through several hint candidates, so the
    candidates are deduplicated by field identity; a neighbourhood that names
    more than one distinct field is ambiguous and binds nothing.
    """

    ordered: list = []
    seen: set[str] = set()
    for field in fields:
        key = str(getattr(field, "value", field))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(field)
    return ordered if len(ordered) == 1 else []


def compile_source_form_field_plans(*, source_pages, glyph_evidence, resolved_fact_fields,
                                    slot_contract):
    """Bind glyph-free physical rules to source form fields, once, pre-render.

    A glyph-free rule carries no intrinsic semantics: it is interpreted through
    the source form field it belongs to.  The label on the rule's own source
    visual line is fed into the repository's existing deterministic hint
    contract, and the resulting fact fields are checked against real
    ProjectFacts status.  A planned insertion requires a compatible resolved
    fact; otherwise the field stays a fixed empty source slot.  No rule identity
    or page number is special-cased, and no value is invented.

    Returns a mapping keyed like the compiled glyph evidence, holding
    ``(transformation_policy, planned_fact_fields)``.
    """

    plans = {}
    resolved = {
        str(getattr(name, "value", name)).strip().upper()
        for name in (resolved_fact_fields or ())
    }
    for page in source_pages or ():
        page_number = int(getattr(page, "page", 0))
        for rule in getattr(page, "lines", None) or ():
            if str(getattr(rule, "orientation", "horizontal")) != "horizontal":
                continue
            try:
                x0, y0, x1, y1 = (float(value) for value in rule.bbox)
            except (TypeError, ValueError):
                continue
            if x1 - x0 <= 1.0:
                continue
            key = (page_number, round(x0, 1), round(x1, 1), round(y0, 1))
            compiled = (glyph_evidence or {}).get(key)
            if compiled is None or compiled[0]:
                # Only glyph-free rules need field binding; a rule that covers
                # source text already has stronger, direct evidence.
                continue
            _boxes, preceding = source_rule_line_context(page, x0, y0, y1)
            fields = []
            line_fields: list = []
            for hint in _field_hint_candidates(preceding):
                _slot_type, allowed = slot_contract(hint)
                if allowed:
                    line_fields.extend(allowed)
            if line_fields:
                # The source label on the rule's own visual line is the primary
                # evidence channel: a fact field can only be bound when that
                # channel names exactly one field, so an ambiguous own-line
                # neighbourhood never authorises a value.
                fields = _single_distinct_field(line_fields)
            else:
                # The label may live in the rule's own structural container - a
                # paragraph or a table cell - rather than on the rule's exact
                # visual line.  The container-aware neighbourhood is searched in
                # its own bounded, deterministic proximity order (owning
                # container, same cell, same row, then the structural adjacent
                # row) and the FIRST container that names exactly one fact field
                # binds the rule: a nearer label wins over a farther one, and a
                # container that names several fields is ambiguous and skipped
                # rather than merged into a false conflict.
                structural, _evidence = source_rule_structural_context(page, x0, y0, x1, y1)
                for _source_kind, text in structural:
                    candidate_fields: list = []
                    for hint in _field_hint_candidates(text):
                        _slot_type, allowed = slot_contract(hint)
                        if allowed:
                            candidate_fields.extend(allowed)
                    bound = _single_distinct_field(candidate_fields)
                    if bound:
                        fields = bound
                        break
            # A fact field is identified by its name or its value depending on
            # how the resolved-fact evidence was collected, so both forms are
            # compared rather than assuming one representation.
            resolved_here = tuple(
                field
                for field in fields
                if {
                    str(getattr(field, "value", field)).strip().upper(),
                    str(getattr(field, "name", field)).strip().upper(),
                }
                & resolved
            )
            if resolved_here:
                plans[key] = (
                    TRANSFORMATION_RESOLVED_VALUE_IN_FIXED_SLOT,
                    resolved_here,
                )
            else:
                plans[key] = (TRANSFORMATION_FIXED_EMPTY_SLOT, tuple(fields))
    return plans


def source_rule_glyph_evidence(evidence, page, x0, x1, y):
    """Look one rule up in the compiled document-wide glyph evidence."""

    if not evidence:
        return None
    key = (int(page or 0), round(float(x0), 1), round(float(x1), 1), round(float(y), 1))
    found = evidence.get(key)
    if found is not None:
        return found
    # The registry and the vector pass can differ in the last decimal only.
    for candidate, value in evidence.items():
        if candidate[0] != key[0]:
            continue
        if abs(candidate[1] - key[1]) <= 0.2 and abs(candidate[2] - key[2]) <= 0.2:
            if abs(candidate[3] - key[3]) <= 1.0:
                return value
    return None


def bind_source_rule_to_fill_slot(rule, *, text_slots=(), geometry_slots=(),
                                  text_start=None, text_end=None,
                                  resolved_fact_fields=(), rule_page=None):
    """The authoritative source fill slot that owns or covers this rule.

    Template-level ``SourceFillSlot`` objects are the single source of truth for
    slot geometry, ``allowed_fact_fields`` and placeholder semantics; a fragment
    copy carries the same fields, so binding uses the fragment's own text range
    where the rule covers text and the template slot's own source geometry where
    it does not.  Nothing here is keyed to a page, a rule id or literal text.
    """

    rule_x0, rule_x1 = float(rule.bbox[0]), float(rule.bbox[2])
    rule_y = (float(rule.bbox[1]) + float(rule.bbox[3])) / 2.0
    # ``allowed_fact_fields`` holds FieldName members, whose ``str()`` is the
    # enum member path rather than the fact name, so the enum value is the key.
    resolved = {_fact_field_key(name) for name in resolved_fact_fields}

    def record(slot):
        allowed = [
            _fact_field_key(name)
            for name in (getattr(slot, "allowed_fact_fields", None) or ())
        ]
        return {
            "slot_id": getattr(slot, "slot_id", None),
            "slot_type": getattr(slot, "slot_type", None),
            "match_kind": getattr(slot, "match_kind", None),
            "geometry": tuple(float(value) for value in slot.geometry)
            if getattr(slot, "geometry", None)
            else None,
            "original_text": getattr(slot, "original_text", None),
            "allowed_fact_fields": allowed,
            "resolved_fact_fields": [name for name in allowed if name in resolved],
        }

    text_candidates = []
    for slot in text_slots:
        if (
            text_start is not None
            and text_end is not None
            and getattr(slot, "text_start", None) is not None
            and getattr(slot, "text_end", None) is not None
            and text_start < slot.text_end
            and slot.text_start < text_end
        ):
            text_candidates.append(record(slot))

    geometry_candidates = []
    for slot in geometry_slots:
        # Ownership is decided before geometry: a rule may only bind a slot cut
        # out of its own source page, so a remote form page can never claim a
        # slot merely because the x ranges happen to overlap.
        if rule_page is not None:
            slot_page = getattr(slot, "source_page", None)
            if slot_page is not None and int(slot_page) != int(rule_page):
                continue
        geometry = getattr(slot, "geometry", None)
        if not geometry:
            continue
        slot_x0, slot_y0, slot_x1, slot_y1 = (float(value) for value in geometry)
        if (
            min(slot_x1, rule_x1) - max(slot_x0, rule_x0) > 0.05
            and slot_y0 - 2.0 <= rule_y <= slot_y1 + 2.0
        ):
            geometry_candidates.append(record(slot))

    candidates = text_candidates or geometry_candidates
    if not candidates:
        return {"bound": False, "reason": "NO_AUTHORITATIVE_SLOT", "candidates": []}
    inserting = [entry for entry in candidates if entry["resolved_fact_fields"]]
    if len(candidates) > 1 and not inserting:
        # Several slots cover the rule and none of them inserts a resolved
        # value, so the evidence cannot say which transformation applies.
        return {
            "bound": False,
            "reason": "AMBIGUOUS_AUTHORITATIVE_SLOT",
            "candidates": candidates,
        }
    chosen = inserting[0] if inserting else candidates[0]
    return {
        "bound": True,
        "reason": "TEXT_BINDING" if text_candidates else "GEOMETRY_BINDING",
        "candidates": candidates,
        **chosen,
    }


def source_rule_transformation_policy(*, rule_text, has_glyphs, has_interior_gap,
                                      resolved_values=(), binding=None):
    """Transformation policy of one source rule, from production evidence.

    Derived from the source rule's own glyph relationship *and* the
    authoritative slot plus fact-resolution evidence.  Glyph occupancy alone is
    never the authority.
    """

    binding = binding or {}
    bound = bool(binding.get("bound"))
    inserts_value = bool(binding.get("resolved_fact_fields"))

    if has_glyphs:
        # A value the document already carries is preserved, underline included.
        if rule_text and any(rule_text in str(value) for value in resolved_values):
            return TRANSFORMATION_SOURCE_VALUE_UNDERLINE
        if bound and inserts_value:
            return TRANSFORMATION_PLACEHOLDER_REPLACED_BY_VALUE
        if has_interior_gap:
            return TRANSFORMATION_FIXED_EMPTY_SLOT
        if bound or binding.get("reason") == "NO_AUTHORITATIVE_SLOT":
            return TRANSFORMATION_PRESERVE_SOURCE_PLACEHOLDER
        return TRANSFORMATION_UNRESOLVED
    if bound and inserts_value:
        return TRANSFORMATION_RESOLVED_VALUE_IN_FIXED_SLOT
    if bound:
        return TRANSFORMATION_FIXED_EMPTY_SLOT
    return TRANSFORMATION_UNRESOLVED


def restore_inline_rule_compositions(text, runs, rules, slots, *, spans=None,
                                     resolved_values=(), rule_ids=None,
                                     owned_runs=None, policy_out=None,
                                     authoritative_slots=None,
                                     resolved_fact_fields=(), binding_out=None,
                                     rule_pages=None, rule_glyph_evidence=None,
                                     rule_field_plans=None, container_text=None):
    """Replace a composed rule's own visible characters with one token.

    The rule's text segments are the source's own glyphs, so they are consumed
    here and re-emitted by the composition emitter at their source positions.
    Every other character, including literal source spaces, is untouched.
    ``container_text`` is the text the covered ranges address; it defaults to the
    text being restored.
    """

    container = text if container_text is None else container_text
    if not spans:
        return text, slots, 0
    rule_ids = rule_ids or {}
    positions = [i for i, c in enumerate(text) if not c.isspace()]
    compact = ''.join(text[i] for i in positions)
    mapped = []
    self_offsets = {}
    cursor = 0
    seen: dict = {}
    for run in runs:
        key = ''.join(run.text.split())
        if not key:
            continue
        at = compact.find(key, cursor)
        if at >= 0:
            # ``at`` is an index into the compact visible-character string, so the
            # run's first and last visible characters hold those container text
            # indices.  ``positions`` is the text index of each visible character,
            # which is the coordinate the character evidence and the emitter's
            # slicing both use.
            mapped.append((run, positions[at], positions[at + len(key) - 1] + 1))
            cursor = at + len(key)
            self_offsets[id(run)] = positions[at]
            occurrence = seen.get(run.text, 0)
            seen[run.text] = occurrence + 1
    if not mapped:
        return text, slots, 0

    inserts = []
    consumed = set()
    binding_rank: dict = {}
    policy_rank: dict = {}
    for rule in rules:
        if rule.orientation != 'horizontal' or id(rule) in consumed:
            continue
        relation = classify_rule_relation(rule, spans, resolved_values=resolved_values)
        # Composition eligibility is a *geometry and evidence* decision: the
        # rule's boundaries must coincide with real recorded character
        # boundaries, and the rule must not already be an ordinary whole-run
        # underline.  The semantic relation label classifies ownership and is
        # deliberately not used to authorise a split.
        rule_id = rule_ids.get(id(rule))
        composition = character_composition_segments(
            rule, mapped, self_offsets=self_offsets, container_text=container_text
        )
        segments = composition[0] if composition else []
        # Production transformation policy, derived here from the rule's own
        # covered source text, the resolved values the document carries and the
        # fill-slot evidence.  Geometry intent follows from it by the
        # authoritative mapping, and an unestablished policy fails closed.
        # The compiled document-wide plan is the semantic boundary: a rule's
        # covered source text comes from the pre-render glyph compilation, not
        # from whichever fragment happens to be rendering right now.  The
        # fragment-local reads remain only as a fallback for rules the compiler
        # did not see.
        compiled = source_rule_glyph_evidence(
            rule_glyph_evidence,
            (rule_pages or {}).get(rule_id),
            float(rule.bbox[0]),
            float(rule.bbox[2]),
            float(rule.bbox[1]),
        )
        if compiled is not None:
            source_text, source_gap = compiled
        else:
            source_text, source_gap = _rule_source_glyphs(rule, runs or spans)
        # Glyph occupancy is source evidence in its own right: a rule can cover
        # text whose outer edges do not coincide with exact character
        # boundaries, so it never authorises a split but does establish that
        # source glyphs occupy the rule.
        has_glyphs = (
            bool(composition)
            or bool(source_text)
            or float(relation.get("text_occupancy") or 0.0) > 0.0
        )
        rule_text = source_text or "".join(
            segment["source_text"] or ""
            for segment in segments
            if segment["segment_type"] == "TEXT_RULE_SEGMENT"
        )
        has_interior_gap = source_gap or any(
            segment["segment_type"] == "EMPTY_RULE_SEGMENT" for segment in segments
        )
        binding = bind_source_rule_to_fill_slot(
            rule,
            text_slots=slots,
            geometry_slots=authoritative_slots if authoritative_slots is not None else slots,
            text_start=composition[1] if composition else None,
            text_end=composition[2] if composition else None,
            resolved_fact_fields=resolved_fact_fields,
            rule_page=(rule_pages or {}).get(rule_id),
        )
        # Field plan, compiled before rendering: a glyph-free physical rule
        # carries no intrinsic fact binding, so its semantic comes from the
        # source form field the compiler bound on the rule's own visual line.
        # Where a plan exists it is authoritative and rendering does not
        # re-derive it; a rule that already carries source glyphs keeps the
        # glyph evidence, which is strictly stronger.
        field_plan = source_rule_glyph_evidence(
            rule_field_plans,
            (rule_pages or {}).get(rule_id),
            float(rule.bbox[0]),
            float(rule.bbox[2]),
            float(rule.bbox[1]),
        )
        # The compiled evidence, not the fragment-local occupancy heuristic,
        # decides whether a rule covers source glyphs: a rule the compiler found
        # glyph-free takes its semantics from the compiled field plan.
        if field_plan is not None and not source_text:
            transformation_policy = field_plan[0]
        else:
            transformation_policy = source_rule_transformation_policy(
                rule_text=rule_text,
                has_glyphs=has_glyphs,
                has_interior_gap=has_interior_gap,
                resolved_values=resolved_values,
                binding=binding,
            )
        # The rule list is the whole page's, so an element that carries neither
        # the rule's glyphs nor its slot cannot establish anything about it.
        # Evidence is ranked, and a look that carries more of it wins, so an
        # established policy or binding is never downgraded by a later look at
        # an element that simply does not own the rule.
        evidence_rank = 0
        if binding.get("bound"):
            evidence_rank = 3 if binding.get("resolved_fact_fields") else 2
        elif source_gap or (source_text and composition):
            evidence_rank = 2
        elif has_glyphs:
            evidence_rank = 1
        if binding_out is not None and rule_id:
            if evidence_rank >= binding_rank.get(rule_id, -1):
                binding_out[rule_id] = binding
                binding_rank[rule_id] = evidence_rank
        if policy_out is not None and rule_id:
            if evidence_rank >= policy_rank.get(rule_id, -1):
                policy_out[rule_id] = transformation_policy
                policy_rank[rule_id] = evidence_rank
        if source_rule_geometry_intent(transformation_policy) != GEOMETRY_INTENT_EXACT_SOURCE_SPAN:
            continue
        if composition is None:
            continue
        segments, start, end, needs_anchor = composition
        # A resolved fact slot inside the rule's own text would be consumed by
        # the composition, so that rule is left to the normal slot path.  This
        # is what keeps value-replacing placeholders on their accepted path.
        if any(slot.text_start is not None and slot.text_end is not None
               and start < slot.text_end and slot.text_start < end
               for slot in slots):
            continue
        consumed.add(id(rule))
        segments[0]["needs_anchor"] = needs_anchor
        # The composition owns the underline semantics of every source run it
        # consumes: it re-establishes underline exactly on its own TEXT
        # segments, so the legacy whole-run underline must not paint the
        # prefix/suffix characters that the split left outside the rule.
        if owned_runs is not None:
            for owned_run, run_start, run_end in mapped:
                if run_start < end and start < run_end:
                    owned_runs.add(id(owned_run))
        inserts.append((
            start,
            end,
            inline_rule_composition_token(
                "%s~%s~%.3f"
                % (
                    rule_ids.get(id(rule)) or "COMPOSITION",
                    relation["relation_type"],
                    relation["text_occupancy"],
                ),
                segments,
            ),
        ))

    if not inserts:
        return text, slots, 0
    for start, end, token in reversed(inserts):
        text = text[:start] + token + text[end:]

    def shifted(offset):
        shift = 0
        for ins_start, ins_end, token in inserts:
            if ins_end <= offset:
                shift += len(token) - (ins_end - ins_start)
            elif ins_start < offset < ins_end:
                offset = ins_start + len(token)
        return offset + shift

    remapped = [
        slot.model_copy(update={
            'text_start': None if slot.text_start is None else shifted(slot.text_start),
            'text_end': None if slot.text_end is None else shifted(slot.text_end),
        })
        for slot in slots
    ]
    return text, remapped, len(inserts)
