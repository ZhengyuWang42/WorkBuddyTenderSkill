"""Evidence units: the semantic source unit an atom is displayed from.

A rendered review row shows a requirement, a page, a section heading, a clause
number and an excerpt.  Those five things must describe **one** source unit.  The
old pipeline printed the *extraction group's* page/section for whatever clause
the row quoted, so a supply-period row could cite "2.1 供应商须具有独立承担民事
责任的能力…" and a technical note could cite "2、乙方送到甲方现场后…".

This module builds the document's own evidence units (a page block, or one row of
a page table) with the heading that actually governs them, matches each source
atom to the unit that *literally contains* its text, and returns the locator,
clause number, heading, page and text span of that unit.  The locator is
therefore derived from the atom's own unit, never from a broader extraction
group.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Sequence

KIND_BLOCK = "pdf_block"
KIND_TABLE_CELL = "pdf_table_cell"

#: a clause heading / numbered section title: "1.10 采购预备会", "3.4.1 响应保证金"
#: (a bare list number such as "5、最高限价" is an item, never a heading)
CLAUSE_HEADING_RE = re.compile(r"^\**\s*(\d+(?:\.\d+)+)\s*[.．]?\s+?(\S.{0,40})$")
#: a Chinese-numbered section title: "三、获取询比文件"
CN_SECTION_RE = re.compile(r"^[一二三四五六七八九十]+[、.]\s*\S")
#: a chapter title: "第二章 供应商须知"
CHAPTER_RE = re.compile(r"^第[\u4e00-\u9fa5]{1,3}章")
#: a front-table / schedule title
SCHEDULE_TITLE_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z]{0,10}(?:前附表|附表)")
#: a numbered list item inside one extracted block: "5、最高限价：…"
NUMBERED_ITEM_RE = re.compile(r"(?:(?<=^)|(?<=[\s\u3000。；;]))(\d{1,2})[、.]")
#: an atom's own leading clause number
_ATOM_CLAUSE_RE = re.compile(r"^\**\s*(\d+(?:\.\d+)+)")
#: a clause number on its own (a schedule label or a structure id)
CLAUSE_LABEL_RE = re.compile(r"^\**\s*(\d+(?:\.\d+)+|\d+)\s*$")


def _flatten(text: object) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or ""))


def _clean(text: object) -> str:
    return re.sub(r"[\s\u3000]+", " ", str(text or "")).strip()


@dataclass(frozen=True)
class EvidenceUnit:
    """One source semantic unit: a page block or one table row."""

    unit_id: str
    kind: str
    page: int | None
    source_structure_id: str
    clause_number: str
    heading: str
    table_row_id: str
    text_span: str
    block_index: int | None = None
    table_index: int | None = None
    row_index: int | None = None
    order: int = 0
    #: the row's own label ("3.5.1 自招标人组织…" / a table row's first cell)
    row_label: str = ""

    @property
    def semantic_heading(self) -> str:
        """The heading a reviewer can use to find this unit in the source.

        A table row's clause number may be empty while its label carries the
        requirement ("第三条验收方法及技术要求" for a contract table); the
        locator then names the row's own label instead of a bare page.  A label
        that only opens a sentence ("作为质保金，质保期") is not a handle, so the
        row's own clause or its first cells are preferred.
        """

        if self.clause_number:
            return ""
        label = re.sub(r"\s+", " ", str(self.row_label or "")).strip()
        if not label:
            return ""
        if label.endswith(("，", ",", "：", ":")) or len(_flatten(label)) < 6:
            return ""
        if len(label) > 48:
            label = label[:48]
        return label

    @property
    def locator(self) -> str:
        parts: list[str] = []
        if self.page:
            parts.append(f"第{self.page}页")
        heading = self.heading or self.semantic_heading
        if heading:
            parts.append(heading)
        if self.clause_number:
            parts.append(f"第{self.clause_number}条")
        parts.append(f"（{self.kind}）")
        return " / ".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "kind": self.kind,
            "page": self.page,
            "source_structure_id": self.source_structure_id,
            "clause_number": self.clause_number,
            "heading": self.heading,
            "table_row_id": self.table_row_id,
            "text_span": self.text_span,
            "locator": self.locator,
        }


@dataclass
class AtomEvidence:
    """The evidence unit an atom is displayed from, plus its own span in it."""

    atom_id: str
    unit: EvidenceUnit
    span: str
    matched: bool = True

    @property
    def locator(self) -> str:
        return self.unit.locator

    def as_dict(self) -> dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "unit": self.unit.as_dict(),
            "span": self.span,
            "matched": self.matched,
        }


def _is_heading(text: str) -> bool:
    flat = _clean(text)
    if not flat or len(flat) > 40:
        return False
    if re.search(r"[，。；;！？!?]", flat):
        # A heading is a title, never a sentence: the extraction frequently emits
        # the truncated *body* of the previous clause as its own block, and
        # carrying it as the heading made every following row cite that sentence
        # as its section (round-9 fixture: CASE003's bid-bond row cited
        # "3.4.1招标人在投标人须知前附表中要求投标人提交投标保证金的，").
        return False
    if _schedule_row_block(text):
        # A front-table row ("*1.12 | 分包 | 不允许") is a *project value*, not a
        # section title: letting it become a heading makes every following row of
        # the same table cite "分包 不允许" as its section (round-8 fixture D34).
        return False
    if CHAPTER_RE.match(flat):
        return True
    if CN_SECTION_RE.match(flat):
        return True
    if SCHEDULE_TITLE_RE.fullmatch(flat):
        return True
    if _article_heading(flat):
        # A contract *article* title ("第五条 交（提）货地点、方式及费用") is a real
        # structural container: the clauses below it belong to it.  It has no
        # numeric clause number of its own, so it was previously invisible to the
        # block loop and the clauses under it inherited a *later* article's title
        # (round-11 fixtures DR048/DR052 cited 第六条 for clauses under 第五条).
        return True
    match = CLAUSE_HEADING_RE.match(flat)
    if match:
        body = match.group(2)
        # "1.10 采购预备会" is a heading; "12" or "1.10.1 供应商须知前附表规定…" is not
        if not re.search(r"[\u4e00-\u9fa5]{2,}", body):
            return False
        return len(match.group(1).split(".")) <= 2 and not body.endswith("。")
    return False


def _heading_titles(heading: str, clause: str) -> bool:
    """Does the carried heading belong to the same structural family as ``clause``?

    A heading that names clause 3.1 does not title a unit whose own clause is 5.2;
    the unit belongs to another section, and the heading must not travel with it
    (round-9 fixtures D40/D43's class, extended to all rows).
    """

    head_clause = _clause_of(str(heading or ""))
    own_clause = str(clause or "")
    if not head_clause or not own_clause:
        # A contract *article* ("第五条 交（提）货地点、方式及费用") carries no numeric
        # clause of its own, so there is nothing to compare; its scope is decided
        # by the article order in the block loop (a later article replaces it).
        return True
    return (
        own_clause == head_clause
        or own_clause.startswith(f"{head_clause}.")
        or head_clause.startswith(f"{own_clause}.")
    )


def _schedule_row_block(text: str) -> bool:
    """Is this block one row of a schedule-style front table?

    The front table is frequently extracted as *blocks* rather than table cells,
    one block per row, with the row's own fields on separate lines::

        *3.3.1
        询比有效期
        提交响应文件截止之日起90 日历天

    The first token is a bare clause label and at least two further tokens carry
    the project's own item/value.  Such a block is a row of the schedule, so it is
    never a section heading for the rows that follow it.
    """

    tokens = [token for token in re.split(r"[\s\u3000]+", str(text or "")) if token]
    if len(tokens) < 3:
        return False
    return bool(CLAUSE_LABEL_RE.match(tokens[0]))


def _clause_of(text: str) -> str:
    match = _ATOM_CLAUSE_RE.match(_clean(text).lstrip("*"))
    return match.group(1) if match else ""


def _block_kind(block: Any) -> str:
    locator = getattr(block, "locator", None)
    kind = str(getattr(locator, "locator_type", "") or "")
    return kind or KIND_BLOCK


def _page_running_heading(page: Any) -> str:
    """The first section-like heading on a page (used when none carries over)."""

    for block in getattr(page, "blocks", ()) or ():
        if _block_kind(block) != KIND_BLOCK:
            continue
        text = _clean(getattr(block, "text", ""))
        if text and _is_heading(text):
            return text
    return ""


def _major_section(text: str) -> bool:
    """A chapter/part title that governs everything after it."""

    flat = _clean(text)
    return bool(re.match(r"^第[\u4e00-\u9fa5]{1,3}[章部分]\s*\S", flat)) and len(flat) <= 30


def _carries_forward(heading: str) -> bool:
    """Does this heading still govern the next page?

    A major section keeps governing until the next major section starts, and a
    clause heading does too: a clause that continues onto the next page ("4.2.4
    供应商应确保…" whose head block sits on page 19) belongs to the heading that
    opened it.  A numbered list item ("2、乙方送到甲方现场后，…") is not a
    heading and ends with its own page, and neither does a front-table row (whose
    value is a project decision, not a section title).
    """

    if _schedule_row_block(heading):
        return False
    flat = _clean(heading)
    if re.match(r"^第[\u4e00-\u9fa5]{1,3}[章部分]", flat):
        return True
    if CN_SECTION_RE.match(flat):
        return True
    if SCHEDULE_TITLE_RE.fullmatch(flat):
        return True
    if _article_heading(flat):
        # a contract article governs the clauses printed under it, including the
        # ones that continue onto the following page
        return True
    match = CLAUSE_HEADING_RE.match(flat)
    if match:
        body = match.group(2)
        # a clause *title* ("4.2 响应文件的递交"), not a sentence
        return "，" not in body and "。" not in body and len(match.group(1)) <= 6
    return False


#: A gap inside one visual line, wider than this, is the source's own *blank*:
#: the contract template prints a rule/gap where a value ("__ 日的支付宽限期")
#: has to be written in.  Collapsing it to a space turns a fillable blank into a
#: sentence that merely reads oddly ("…从最后一笔款项应付之日起给甲方 的支付宽限期"),
#: so the blank is preserved as an explicit placeholder.
INLINE_BLANK_GAP_PT = 24.0
#: The placeholder an intrinsic source blank is rendered as.
INLINE_BLANK_PLACEHOLDER = "＿＿＿＿"


def _line_gap_spans(block: Any) -> list[int]:
    """Character offsets in ``block.text`` where the source printed a blank.

    The line/span geometry of the block is read directly, so the placeholder
    marks the *source's* own gap and never an invented value.  A wide horizontal
    gap either appears between two spans of one line or makes the extractor split
    the line in two at the same vertical position; both shapes are the same
    source blank.
    """

    lines = list(getattr(block, "lines", ()) or ())
    if not lines:
        return []
    text = str(getattr(block, "text", "") or "")
    if not text:
        return []
    offsets: list[int] = []
    cursor = 0
    for index, line in enumerate(lines):
        raw = str(getattr(line, "text", "") or "")
        if not raw:
            continue
        spans = list(getattr(line, "spans", ()) or ())
        gaps: list[float] = []
        for previous, following in zip(spans, spans[1:]):
            gaps.append(float(following.bbox[0]) - float(previous.bbox[2]))
        # the extractor's own line break is sometimes the blank: the next line
        # starts where this one ended but far to the right of it
        if index + 1 < len(lines):
            following_line = lines[index + 1]
            same_row = abs(float(following_line.bbox[1]) - float(line.bbox[1])) <= 2.0
            if same_row:
                gaps.append(float(following_line.bbox[0]) - float(line.bbox[2]))
        found = text.find(raw, cursor)
        if found < 0:
            continue
        cursor = found + len(raw)
        for gap in gaps:
            if gap >= INLINE_BLANK_GAP_PT:
                offsets.append(cursor)
                break
    return offsets


def _text_with_inline_blanks(block: Any) -> str:
    """The block's text with its own intrinsic blank gaps marked."""

    text = _clean(getattr(block, "text", ""))
    offsets = _line_gap_spans(block)
    if not text or not offsets:
        return text
    out = text
    for offset in sorted(set(offsets), reverse=True):
        if 0 < offset < len(out):
            out = f"{out[:offset]} {INLINE_BLANK_PLACEHOLDER} {out[offset:]}"
    return _clean(out)


def build_evidence_units(document: Any) -> list[EvidenceUnit]:
    """Every evidence unit of the document, in reading order."""

    units: list[EvidenceUnit] = []
    carried_heading = ""
    carried_page: int | None = None
    for page in getattr(document, "pages", ()) or ():
        page_number = getattr(page, "page_number", None)
        # a major section heading carries onto the following pages: a table on
        # page 34 belongs to the section that opened on page 33 ("第三条验收方法
        # 及技术要求").  It stops at the page after the one that holds a *new*
        # heading, so a body block on page 18 cannot title a clause on page 20.
        if carried_page is not None and page_number is not None:
            if int(page_number) - int(carried_page) > 1:
                carried_heading = ""
        heading = carried_heading
        heading_clause = _clause_of(heading) if heading else ""
        for block in getattr(page, "blocks", ()) or ():
            text = _clean(getattr(block, "text", ""))
            if not text:
                continue
            if _block_kind(block) != KIND_BLOCK:
                # a table cell is covered by its row unit; it is never a heading
                continue
            block_index = int(getattr(block, "block_index", 0))
            if _is_heading(text):
                heading = text
                heading_clause = _clause_of(text)
                if _carries_forward(text):
                    carried_heading = text
                    carried_page = page_number
            elif _major_section(text):
                carried_heading = text
                carried_page = page_number
            clause = _clause_of(text) or heading_clause
            units.append(
                EvidenceUnit(
                    unit_id=f"EU-P{page_number}-B{block_index}",
                    kind=KIND_BLOCK,
                    page=page_number,
                    source_structure_id=f"block:{block_index}",
                    clause_number=clause,
                    # A carried heading titles this unit only while the unit stays in
                    # the same clause family.  A block that states its own clause
                    # ("5.2 设备单价中含…") under a heading of an unrelated clause
                    # ("3.1 供应商提供设备应遵照…") is not in that section, and
                    # showing the foreign heading sends the reviewer to another
                    # chapter (round-9 fixtures D40/D43's class, extended to all
                    # rows).
                    heading=heading if _heading_titles(heading, clause) else "",
                    table_row_id="",
                    text_span=_text_with_inline_blanks(block),
                    block_index=block_index,
                    order=len(units),
                )
            )
    captions = _document_captions(document)
    for table in getattr(document, "tables", ()) or ():
        page_number = getattr(table, "page", None)
        # A table's heading is the heading that governs *its own position*: the
        # carried heading of the block loop has already reached the end of the
        # document by the time the tables are visited, so it must never title a
        # table (round-9 fixture D40/D43: a page-33 contract table was titled
        # "十五、其他资料", a section of the response-format chapter).
        caption = captions.get(page_number, "") or _page_heading_for_table(
            document, page_number, getattr(table, "bbox", None)
        )
        previous_clause = ""
        previous_span = ""
        for row in getattr(table, "rows", ()) or ():
            cells = sorted(getattr(row, "cells", ()) or (), key=lambda cell: cell.column_index)
            texts = [_clean(cell.text) for cell in cells if _clean(cell.text)]
            if not texts:
                continue
            label = texts[0]
            clause = _clause_of(label)
            span = " ".join(texts)
            if not clause and previous_clause and _continues_sentence(previous_span, span):
                # the row is the tail of the previous row's sentence (a clause
                # split across table rows): it belongs to the same clause, which
                # is what makes its locator coherent ("第2.3条", not a bare page).
                clause = previous_clause
            elif clause:
                previous_clause = clause
            previous_span = span
            # a row whose label is not a clause number still needs a locator: its
            # own label is the tightest handle the source offers
            units.append(
                EvidenceUnit(
                    unit_id=(
                        f"EU-P{page_number}-T{getattr(table, 'table_index', 0)}"
                        f"-R{getattr(row, 'row_index', 0)}"
                    ),
                    kind=KIND_TABLE_CELL,
                    page=page_number,
                    source_structure_id=(
                        f"table:{getattr(table, 'table_index', 0)}:"
                        f"row:{getattr(row, 'row_index', 0)}"
                    ),
                    clause_number=clause,
                    heading=caption,
                    table_row_id=f"T{getattr(table, 'table_index', 0)}R{getattr(row, 'row_index', 0)}",
                    text_span=span,
                    table_index=int(getattr(table, "table_index", 0)),
                    row_index=int(getattr(row, "row_index", 0)),
                    order=len(units),
                    row_label="" if clause else label,
                )
            )
    return units


def _continues_sentence(previous: str, current: str) -> bool:
    """Does ``current`` continue the sentence ``previous`` left unfinished?"""

    before = _clean(previous).rstrip()
    after = _clean(current).lstrip()
    if not before or not after:
        return False
    # a finished sentence is not continued, and a new clause label starts a new one
    if before.endswith(("。", "！", "？", "；", ";", ":")):
        return False
    if _clause_of(after) or re.match(r"^[（(]?\d", after):
        return False
    return True


def _document_captions(document: Any) -> dict[int | None, str]:
    """The schedule caption that governs each page's tables.

    A front table is introduced once ("供应商须知前附表") and then continues over
    several pages, so the caption carries forward -- but only until a new major
    part of the document starts ("第三章 合同条款"), which is *not* a schedule.
    """

    titled: list[tuple[int, str]] = []
    resets: list[int] = []
    for page in getattr(document, "pages", ()) or ():
        page_number = int(getattr(page, "page_number", 0) or 0)
        for block in getattr(page, "blocks", ()) or ():
            if _block_kind(block) != KIND_BLOCK:
                continue
            text = _clean(getattr(block, "text", ""))
            if not text:
                continue
            if SCHEDULE_TITLE_RE.fullmatch(text):
                titled.append((page_number, text))
            elif CHAPTER_RE.match(text) or CN_SECTION_RE.match(text):
                resets.append(page_number)
    captions: dict[int | None, str] = {}
    for page in getattr(document, "pages", ()) or ():
        page_number = int(getattr(page, "page_number", 0) or 0)
        current = ""
        scheduled_here = False
        for titled_page, text in titled:
            if titled_page <= page_number:
                if titled_page == page_number:
                    scheduled_here = True
                current = text
            else:
                break
        # a chapter that opens after the schedule ends the schedule's reach
        for reset_page in resets:
            if reset_page > (titled[-1][0] if titled else 0) and page_number >= reset_page:
                current = ""
        if scheduled_here:
            current = next(text for titled_page, text in titled if titled_page == page_number)
        captions[page_number] = current
    return captions


def _page_heading_for_table(
    document: Any, page: int | None, bbox: tuple[float, ...] | None
) -> str:
    """The running heading of the page at the table's position (caption fallback)."""
    if page is None:
        return ""
    page_model = None
    for candidate in getattr(document, "pages", ()) or ():
        if getattr(candidate, "page_number", None) == page:
            page_model = candidate
            break
    if page_model is None:
        return ""
    top = bbox[1] if bbox else None
    heading = ""
    for block in getattr(page_model, "blocks", ()) or ():
        if _block_kind(block) != KIND_BLOCK:
            continue
        text = _clean(getattr(block, "text", ""))
        if not text:
            continue
        block_box = getattr(block, "bbox", None)
        # Only blocks *above* the table may title it.  The scan must not break on
        # the first out-of-order block: a page footer (the printed page number)
        # sits at the bottom and used to end the scan before the real heading was
        # reached, leaving the table with no heading at all (round-9 D40/D43).
        if top is not None and block_box and block_box[1] > top:
            continue
        if _is_heading(text):
            heading = text
        elif CHAPTER_RE.match(text) or CN_SECTION_RE.match(text) or _article_heading(text):
            heading = text
    return heading


#: A contract *article* title ("第二条 合同价款及结算").  It is a section for the
#: table caption fallback: the contract's own clauses are numbered below it, and a
#: table holding clause 2.3 belongs to article 2 (round-9 D40/D43).
_ARTICLE_HEADING_RE = re.compile(r"^第[一二三四五六七八九十百]+条\s*\S")


def _article_heading(text: str) -> bool:
    flat = _clean(text)
    return bool(_ARTICLE_HEADING_RE.match(flat)) and len(flat) <= 30


@dataclass
class EvidenceUnitIndex:
    """Atom -> evidence-unit resolution over the whole document."""

    units: tuple[EvidenceUnit, ...] = ()
    #: atom id -> its evidence unit
    by_atom: dict[str, AtomEvidence] = field(default_factory=dict)
    #: atoms that could not be located in any unit
    unmatched_atom_ids: tuple[str, ...] = ()
    #: atom id -> text handed in for matching (used by the audit)
    atom_text: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(cls, document: Any, atoms: Sequence[Any]) -> "EvidenceUnitIndex":
        units = tuple(build_evidence_units(document))
        by_atom: dict[str, AtomEvidence] = {}
        unmatched: list[str] = []
        atom_text: dict[str, str] = {}
        for atom in atoms:
            atom_id = str(getattr(atom, "atom_id", ""))
            text = str(getattr(atom, "source_text", "") or "")
            atom_text[atom_id] = text
            evidence = locate_atom(atom, units)
            if evidence is None:
                unmatched.append(atom_id)
            else:
                by_atom[atom_id] = evidence
        # A derived *facet* atom ("SRA0234.r", ".c", ".a", ".s", ".t") is cut out
        # of its base atom's clause, so it belongs to the base atom's unit even
        # when its own text is a sub-slice that spans two units (round-9 fixture
        # D43).  The facet keeps its own span; only the unit is shared.
        for atom in atoms:
            atom_id = str(getattr(atom, "atom_id", ""))
            base, _, suffix = atom_id.rpartition(".")
            if not base or f".{suffix}" not in DERIVED_FACET_SUFFIXES:
                continue
            base_evidence = by_atom.get(base)
            evidence = by_atom.get(atom_id)
            if base_evidence is None:
                continue
            if evidence is None:
                by_atom[atom_id] = base_evidence
                unmatched = [value for value in unmatched if value != atom_id]
            else:
                by_atom[atom_id] = replace(evidence, unit=base_evidence.unit)
        return cls(
            units=units,
            by_atom=by_atom,
            unmatched_atom_ids=tuple(unmatched),
            atom_text=atom_text,
        )

    def for_atom(self, atom: Any) -> AtomEvidence | None:
        return self.by_atom.get(str(getattr(atom, "atom_id", "")))

    def unit_of(self, atom: Any) -> EvidenceUnit | None:
        evidence = self.for_atom(atom)
        return evidence.unit if evidence else None

    def summary(self) -> dict[str, Any]:
        kinds: dict[str, int] = {}
        for unit in self.units:
            kinds[unit.kind] = kinds.get(unit.kind, 0) + 1
        return {
            "unit_count": len(self.units),
            "unit_kinds": kinds,
            "atoms_located": len(self.by_atom),
            "atoms_unmatched": len(self.unmatched_atom_ids),
            "unmatched_sample": list(self.unmatched_atom_ids[:8]),
        }


def _match_score(atom_flat: str, unit_flat: str) -> int:
    """How much of the atom's text this unit carries.

    Sources are extracted with wrapped lines, so an atom's text frequently covers
    two blocks: containment *either way* counts, and a shared long prefix plus
    suffix counts as a partial (wrapped-line) match.  A leading stray bracket
    ("） （若为代理商…") is extraction noise, not a different unit.
    """

    if not atom_flat or not unit_flat:
        return 0
    for candidate in (atom_flat, atom_flat.lstrip("）)】」")):
        if candidate and (candidate in unit_flat or unit_flat in candidate):
            return min(len(candidate), len(unit_flat))
    if atom_flat[:1] in "）)】」" and len(atom_flat) > 1:
        # the atom opens with the tail of the previous unit: match on its body
        body = atom_flat[1:]
        if body in unit_flat or unit_flat in body:
            return min(len(body), len(unit_flat))
    prefix = 0
    for left, right in zip(atom_flat, unit_flat):
        if left != right:
            break
        prefix += 1
    suffix = 0
    for left, right in zip(reversed(atom_flat), reversed(unit_flat)):
        if left != right:
            break
        suffix += 1
    return prefix + suffix


#: a unit must carry at least this much of the atom to be its unit
MIN_UNIT_MATCH = 10

#: Suffixes of atoms that are *facets* cut out of a base atom's clause.  A facet
#: resolves to the base atom's evidence unit so its page/section/clause stay
#: coherent with the clause it quotes.
DERIVED_FACET_SUFFIXES = frozenset({".r", ".c", ".a", ".s", ".t"})


def _candidate_units(
    atom: Any, units: Sequence[EvidenceUnit], text: str | None = None
) -> list[tuple[int, EvidenceUnit]]:
    atom_flat = _flatten(text if text is not None else getattr(atom, "source_text", ""))
    if not atom_flat:
        return []
    threshold = min(MIN_UNIT_MATCH, max(4, len(atom_flat)))
    page = getattr(atom, "source_page", None)
    scored: list[tuple[int, EvidenceUnit]] = []
    for unit in units:
        unit_flat = _flatten(unit.text_span)
        if not unit_flat:
            continue
        score = _match_score(atom_flat, unit_flat)
        if score < threshold:
            # a wrapped sentence: the unit may hold only its head or its tail.  A
            # unit that carries one end of the sentence is scored by how much of
            # the atom it actually shares, never by the floor: otherwise a
            # 2-character page-number block ties with a real clause block.
            head = atom_flat[:threshold]
            tail = atom_flat[-threshold:]
            shared = 0
            if head in unit_flat:
                shared = max(shared, len(head))
            if tail in unit_flat:
                shared = max(shared, len(tail))
            if not shared:
                continue
            score = min(shared, threshold) - 1
        if page and unit.page and unit.page != page:
            score -= 2
        scored.append((score, unit))
    # a clause that repeats its own heading on the next page (a list continued
    # across a page break) must be anchored where it *starts*: the first unit
    # that carries the atom's opening text, at the earliest page
    opening = atom_flat[: min(16, len(atom_flat))]
    starters = [
        (score, unit)
        for score, unit in scored
        if opening and opening in _flatten(unit.text_span)
        and _clause_of(str(getattr(atom, "source_text", "")))
        and _clause_of(str(getattr(atom, "source_text", "")))
        == (unit.clause_number or _clause_of(str(getattr(atom, "source_text", ""))))
    ]
    if starters:
        best = max(score for score, _unit in starters)
        pool = [unit for score, unit in starters if score >= best - 2]
        # A front-table page emits the same row twice: as a page block and as the
        # table's own row.  The table row is the unit the reviewer can be sent to
        # (it carries the schedule caption and the row's clause), so it wins over
        # its block copy (round-9 fixture: the pre-bid row cited "（pdf_block）"
        # while every sibling schedule row cited "（pdf_table_cell）").
        tables = [unit for unit in pool if unit.kind == KIND_TABLE_CELL]
        if tables:
            pool = tables
        earliest = min((unit.page or 0, unit.order) for unit in pool)
        for unit in pool:
            if (unit.page or 0, unit.order) == earliest:
                return [(best, unit)]
    return scored


def _anchor_and_span(
    atom_flat: str, scored: Sequence[tuple[int, EvidenceUnit]]
) -> tuple[EvidenceUnit, str]:
    """The unit the atom *starts* in, plus the span the atom covers.

    An extracted atom often concatenates consecutive blocks (wrapped lines).  The
    locator must still be the unit where the atom begins -- taking the *last* or
    the *widest* block would print a neighbouring section heading (round-7
    fixtures G and H).
    """

    best = max(score for score, _unit in scored)
    covered = [
        unit
        for score, unit in scored
        if _flatten(unit.text_span) in atom_flat and len(_flatten(unit.text_span)) >= 4
    ]
    if covered:
        covered.sort(key=lambda unit: (-len(_flatten(unit.text_span)), unit.kind != KIND_TABLE_CELL, unit.order))
        anchor = covered[0]
        parts: list[str] = []
        joined = ""
        for unit in sorted(covered, key=lambda unit: unit.order):
            text = unit.text_span.strip()
            flat = _flatten(text)
            if not text or flat in joined:
                continue
            parts.append(text)
            joined += flat
        span = " ".join(parts) if parts else anchor.text_span
        anchor, span = _prefer_table_unit(atom_flat, anchor, span, scored)
        return anchor, span
    top = [unit for score, unit in scored if score == best]
    top.sort(key=lambda unit: (unit.order, unit.kind != KIND_TABLE_CELL))
    return _prefer_table_unit(atom_flat, top[0], top[0].text_span, scored)


def _prefer_table_unit(
    atom_flat: str,
    anchor: EvidenceUnit,
    span: str,
    scored: Sequence[tuple[int, EvidenceUnit]],
) -> tuple[EvidenceUnit, str]:
    """A table row is a tighter evidence unit than the page block that copies it.

    On a front-table page the extractor emits both the table row (with the
    schedule caption and the row's own clause) and a page block holding the same
    cell text under whatever heading ran before it; the row is the unit the
    reviewer can actually be sent to (round-7 fixture for the bond form).
    """

    if anchor.kind == KIND_TABLE_CELL or not atom_flat:
        return anchor, span
    candidates = [
        unit
        for _score, unit in scored
        if unit.kind == KIND_TABLE_CELL and atom_flat in _flatten(unit.text_span)
    ]
    if not candidates:
        return anchor, span
    candidates.sort(key=lambda unit: (len(_flatten(unit.text_span)), unit.order))
    return candidates[0], span


def locate_atom(atom: Any, units: Sequence[EvidenceUnit]) -> AtomEvidence | None:
    atom_flat = _flatten(getattr(atom, "source_text", ""))
    scored = _candidate_units(atom, units)
    if not scored:
        # A derived *facet* atom ("剩余 5%作为质保金") is cut out of a clause and
        # may span two source units, so its own text locates nothing.  The clause
        # it was cut from is handed to the atom as ``source_origin_text``: the
        # facet belongs to the unit that carries that clause, and using it keeps
        # the row's page/section/clause coherent (round-9 fixture D43).
        origin = _flatten(getattr(atom, "source_origin_text", ""))
        if origin and origin != atom_flat:
            scored = _candidate_units(atom, units, origin)
        if not scored:
            return None
    unit, span = _anchor_and_span(atom_flat or _flatten(getattr(atom, "source_origin_text", "")), scored)
    clause = _clause_of(str(getattr(atom, "source_text", ""))) or unit.clause_number
    if clause and clause != unit.clause_number:
        unit = EvidenceUnit(
            unit_id=unit.unit_id,
            kind=unit.kind,
            page=unit.page,
            source_structure_id=unit.source_structure_id,
            clause_number=clause,
            heading=unit.heading,
            table_row_id=unit.table_row_id,
            text_span=unit.text_span,
            block_index=unit.block_index,
            table_index=unit.table_index,
            row_index=unit.row_index,
            order=unit.order,
        )
    return AtomEvidence(
        atom_id=str(getattr(atom, "atom_id", "")),
        unit=unit,
        span=_clean(span) or _clean(unit.text_span),
    )


#: A locator prints a clause *number*; a Chinese item label is not one.
CLAUSE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*$")


def printable_clause_label(clause: str) -> str:
    """The clause as a locator may print it.

    The extraction keys some blocks by a Chinese item label ("五、质量要求",
    "（4）"); printing those as ``第（4）条`` invents a clause number the source does
    not carry.  A locator therefore prints a clause only when it is one.
    """

    flat = str(clause or "").strip()
    return flat if CLAUSE_NUMBER_RE.match(flat) else ""


def locator_for_atom(
    atom: Any,
    index: EvidenceUnitIndex,
    *,
    fallback_page: int | None = None,
    fallback_section: str = "",
    fallback_clause: str = "",
    fallback_kind: str = "",
) -> tuple[str, int | None, str, str]:
    """``(locator, page, section, clause)`` for an atom.

    The locator comes from the atom's own evidence unit.  When the atom has no
    unit at all the caller's fallback is used unchanged (an unlocatable atom is
    never silently given a *different* unit's locator).
    """

    evidence = index.for_atom(atom)
    if evidence is not None:
        unit = evidence.unit
        # ONE derivation decides the visible section (see
        # ``locator_section_for_unit``): the locator, the audit and the delivered
        # cell all read the same value.
        locator, section, clause, _source, _clip = expected_locator_for_unit(
            unit,
            evidence.span,
            fallback_page=fallback_page,
            fallback_section=fallback_section,
            fallback_clause=fallback_clause,
            fallback_kind=fallback_kind,
        )
        return locator, unit.page or fallback_page, section, clause
    locator = _locator_text(fallback_page, fallback_section, fallback_clause, fallback_kind)
    return locator, fallback_page, fallback_section, fallback_clause


def atom_clause_number(atom: Any) -> str:
    """The clause number an atom is keyed by (structure id first, then its text)."""

    structure = str(getattr(atom, "source_structure_id", "") or "").replace("*", "").strip()
    if _ATOM_CLAUSE_RE.match(structure) and CLAUSE_LABEL_RE.match(structure):
        return structure
    return _clause_of(str(getattr(atom, "source_text", "") or ""))


def _opening_handle(span: str) -> str:
    """The first substantial sentence of a unit, used when it has no heading."""

    text = re.sub(r"\s+", " ", str(span or "")).strip()
    if not text:
        return ""
    for piece in re.split(r"[。；;]", text):
        head = piece.strip()
        if len(_flatten(head)) >= 6:
            return head[:48]
    return ""


def _numbered_item_label(span: str) -> str:
    match = re.match(r"^\s*(\d{1,2})[、.]\s*(.{0,40})", _clean(span))
    if not match:
        return ""
    label = re.split(r"[。；;]", match.group(2))[0].strip()
    if len(label) < 3:
        return ""
    return f"{match.group(1)}、{label}"


def format_locator_section_for_display(section: str) -> str:
    """The section exactly as the delivered locator prints it.

    This is the one deterministic formatter between a unit's canonical section and
    the ``证据定位`` text in the workbook: ``_locator_text`` prints the value this
    function returns, so an audit must compare the visible section against *this*
    output rather than against the raw heading it was derived from, and never
    against a prefix, substring or fuzzy variant of it.
    """

    return str(section or "").strip()


def locator_section_for_unit(
    unit: Any, span: str, fallback_section: str = ""
) -> tuple[str, str, int | None]:
    """The visible locator section, where it came from, and its clip limit.

    ``(visible_section, source, clip_limit)``: ``source`` names the derivation
    (``unit.heading`` / ``unit.semantic_heading`` / ``atom.section`` /
    ``numbered_item`` / ``opening_handle``) and ``clip_limit`` is the production
    limit when a derivation clipped the source text, so a clipped locator is
    explicit and auditable instead of silently accepted.
    """

    heading = str(getattr(unit, "heading", "") or "")
    semantic = str(getattr(unit, "semantic_heading", "") or "")
    clause = str(getattr(unit, "clause_number", "") or "")
    if heading or semantic:
        value = heading or semantic
        return (
            format_locator_section_for_display(value),
            "unit.heading" if heading else "unit.semantic_heading",
            None,
        )
    if not clause:
        item = _numbered_item_label(span)
        if item:
            return format_locator_section_for_display(item), "numbered_item", 40
        return (
            format_locator_section_for_display(_opening_handle(span)),
            "opening_handle",
            48,
        )
    return format_locator_section_for_display(fallback_section), "atom.section", None


def expected_locator_for_unit(
    unit: Any,
    span: str,
    *,
    fallback_page: int | None = None,
    fallback_section: str = "",
    fallback_clause: str = "",
    fallback_kind: str = "",
) -> tuple[str, str, str, str, int | None]:
    """The production locator for a **canonical** evidence unit.

    ``(locator, section, clause, section_source, clip_limit)``, computed by the
    same derivation the delivered cell is rendered from (``locator_section_for_unit``
    -> ``printable_clause_label`` -> ``_locator_text``).  This is the only place a
    locator is put together, so the acceptance audit's *expected* value is the
    production formatter's own output for the unit, never a second implementation
    and never a prefix or fuzzy variant of it (round-9 gate).
    """

    section, source, clip = locator_section_for_unit(unit, span, fallback_section)
    clause = printable_clause_label(getattr(unit, "clause_number", "") or fallback_clause)
    if source in ("numbered_item", "opening_handle"):
        clause = ""
    kind = str(getattr(unit, "kind", "") or fallback_kind)
    page = getattr(unit, "page", None) or fallback_page
    return _locator_text(page, section, clause, kind), section, clause, source, clip


def locators_match_exactly(expected: str, actual: str) -> bool:
    """Whether a visible locator equals the formatter's output **exactly**.

    The round-9 gate invariant is

        canonical EvidenceUnit
        -> deterministic production locator formatter
        -> expected visible locator
        -> SAVED/REOPENED XLSX
        -> EXACT equality

    so the comparison is equality and nothing else: a delivered section that is a
    prefix (``startswith``), a substring (``in``) or an arbitrary prefix-overlap of
    the expected value is a *different* locator and is rejected.  The audit imports
    this function instead of writing its own comparison, so no second, weaker
    matcher can appear beside it.
    """

    return str(expected or "") == str(actual or "")


def _locator_text(
    page: int | None, section: str, clause: str, kind: str
) -> str:
    parts: list[str] = []
    if page:
        parts.append(f"第{page}页")
    if section:
        parts.append(format_locator_section_for_display(section))
    if clause:
        parts.append(f"第{clause}条")
    if kind:
        parts.append(f"（{kind}）")
    return " / ".join(parts)


def split_numbered_items(text: str) -> list[str]:
    """Cut one extracted block into its numbered items ("5、…", "6、…")."""

    raw = _clean(text)
    if not raw:
        return []
    marks = [match.start() for match in NUMBERED_ITEM_RE.finditer(raw)]
    if len(marks) <= 1:
        return [raw]
    pieces: list[str] = []
    for index, start in enumerate(marks):
        end = marks[index + 1] if index + 1 < len(marks) else len(raw)
        piece = raw[start:end].strip(" ；;，,。")
        if piece:
            pieces.append(piece)
    return pieces


def normalize_numeric_fragment(text: str, owned_values: Sequence[str] = ()) -> str:
    """Repair duplicated / placeholder-corrupted numeric text for display.

    The PDF extraction splits and repeats cells, producing text such as
    "剩余 %，剩余 5%%，剩余 5%作为质保金".  The rendered fragment must carry the
    real project value exactly once: repeated characters are collapsed, a bare
    placeholder ("剩余 %") that sits next to a real value is dropped, and a
    segment that merely repeats the head of a longer one is dropped with it.
    The engine never invents a number -- it only removes duplicates and
    placeholders, and the row's own owned value is never altered.
    """

    raw = _clean(text)
    if not raw:
        return ""
    raw = re.sub(r"\s+([。；;，,、！？!?])", r"\1", raw)
    raw = re.sub(r"([（(])\s+", r"\1", raw)
    fixed = re.sub(r"(%|％)\1+", r"\1", raw)
    segments = [
        piece.strip(" ，,；;、")
        for piece in re.split(r"[，,；;]", fixed)
        if piece.strip(" ，,；;、")
    ]
    if not segments:
        return fixed
    has_real_value = any(re.search(r"\d", segment) for segment in segments)
    kept: list[str] = []
    for segment in segments:
        flat = _flatten(segment)
        if has_real_value and not re.search(r"\d", segment) and re.search(r"[%％]", segment):
            continue  # a bare placeholder beside a real value
        if any(flat and flat in _flatten(other) and flat != _flatten(other) for other in kept):
            continue  # this segment is only the head of one already kept
        if flat in {_flatten(item) for item in kept}:
            continue
        kept = [item for item in kept if _flatten(item) not in flat]
        kept.append(segment)
    return "，".join(kept) if kept else fixed


_TERMINAL = "。；;！？!?"
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。；;！？!?])")


def sentence_window(unit_text: str, needle: str) -> str:
    """The whole sentence(s) of ``unit_text`` that carry ``needle``.

    A displayed fragment must not begin or end mid-sentence: the extraction cuts
    atoms at line boundaries, and a half sentence ("…承诺从最后一笔款项应付之日
    起给甲方") is not a reviewable source fragment.
    """

    unit = _clean(unit_text)
    target = _flatten(needle)
    if not unit:
        return ""
    if not target:
        return unit
    sentences = [piece.strip() for piece in _SENTENCE_SPLIT_RE.split(unit) if piece.strip()]
    if not sentences:
        return ""
    kept: list[str] = []
    for sentence in sentences:
        flat = _flatten(sentence)
        if target in flat or flat in target:
            kept.append(sentence)
    if kept:
        return " ".join(kept).strip()
    return ""


#: a unit that opens a new source element rather than continuing a sentence
NEW_ELEMENT_RE = re.compile(r"^(?:第[\u4e00-\u9fa5]{1,4}[条款节章]|\d{1,2}(?:\.\d+)*[、.．]|[（(]\d{1,2}[）)]|[一二三四五六七八九十]+、)")


def _raw_prefix_for_flat(text: str, flat_length: int) -> str:
    """The raw prefix of ``text`` whose whitespace-free form has that length."""

    if flat_length <= 0:
        return text
    count = 0
    for index, character in enumerate(text):
        if not character.isspace():
            count += 1
        if count >= flat_length:
            return text[index + 1 :]
    return ""


def strip_leading_overlap(current: str, addition: str, *, min_overlap: int = 4) -> str:
    """Drop the part of ``addition`` that already ends ``current``.

    Consecutive extraction units repeat a few characters where the line wrapped
    ("…从最后一笔款项应付之日 起给甲方" + "起给甲方 的支付宽限期…"); appending
    both would duplicate the fragment.
    """

    left = _flatten(current)
    right = _flatten(addition)
    if not left or not right:
        return addition
    if right in left:
        return ""
    best = 0
    limit = min(len(left), len(right))
    for size in range(limit, min_overlap - 1, -1):
        if left[-size:] == right[:size]:
            best = size
            break
    if not best:
        return addition
    return _raw_prefix_for_flat(addition, best)


def finish_from_unit(fragment: str, unit_text: str, *, min_overlap: int = 6) -> str:
    """Finish a cut fragment from the tail of the atom's *own* unit.

    The extraction frequently keeps the head of a sentence in one block and its
    continuation (a URL, a bracketed clause) in the next block of the same unit;
    the rest of that unit is the correct completion.
    """

    text = _clean(fragment)
    unit = _clean(unit_text)
    if not text or not unit:
        return text
    if text.endswith(tuple(_TERMINAL)):
        return text
    left = _flatten(text)
    right = _flatten(unit)
    best = 0
    for size in range(min(len(left), 80), min_overlap - 1, -1):
        if left[-size:] in right:
            best = size
            break
    if not best:
        return text
    remainder = _raw_prefix_for_flat(unit, right.index(left[-best:]) + best)
    remainder = _up_to_sentence_end(remainder, text)
    if not remainder or _flatten(remainder) in left:
        return text
    return f"{text}{remainder}".strip()


def extend_fragment(
    fragment: str,
    unit: EvidenceUnit,
    units: Sequence[EvidenceUnit],
    *,
    max_extra: int = 2,
) -> str:
    """Append the following unit(s) while the fragment stops mid-sentence.

    The appended text stops at the first sentence end: a cut sentence is
    completed, but the next sentence of the source is a different requirement and
    must not be pulled into this row's excerpt.
    """

    text = _clean(fragment)
    if not text:
        return text
    rest = [
        unit_
        for unit_ in units
        if unit_.order > unit.order
        and (unit_.page is None or unit.page is None or int(unit_.page) <= int(unit.page) + 1)
    ]
    rest.sort(key=lambda unit_: unit_.order)
    for next_unit in rest[:max_extra]:
        if text.endswith(tuple(_TERMINAL)):
            break
        addition = strip_leading_overlap(text, _clean(next_unit.text_span))
        if not addition:
            continue
        if NEW_ELEMENT_RE.match(addition):
            break  # a new clause / item is not the continuation of this sentence
        text = f"{text} {_up_to_sentence_end(addition, text)}".strip()
    return text


def _up_to_sentence_end(addition: str, current: str) -> str:
    """The part of ``addition`` that finishes ``current``'s sentence."""

    if current.endswith(tuple(_TERMINAL)):
        return ""
    for index, character in enumerate(addition):
        if character in _TERMINAL:
            return addition[: index + 1]
    return addition


def complete_fragment_backwards(
    fragment: str,
    unit: EvidenceUnit,
    units: Sequence[EvidenceUnit],
    *,
    max_extra: int = 2,
) -> str:
    """Prepend the previous unit(s) while the fragment starts mid-sentence."""

    text = _clean(fragment)
    if not text:
        return text
    previous = [
        unit_
        for unit_ in units
        if unit_.order < unit.order and unit_.page == unit.page
    ]
    previous.sort(key=lambda unit_: unit_.order, reverse=True)
    for previous_unit in previous[:max_extra]:
        head = _clean(previous_unit.text_span)
        if not head or _flatten(head) in _flatten(text):
            break
        if head.endswith(tuple(_TERMINAL)):
            break  # the previous unit closed its sentence: this one starts fresh
        if NEW_ELEMENT_RE.match(text) or SCHEDULE_TITLE_RE.fullmatch(head):
            break
        text = f"{head} {text}"
    return text


def dedupe_segments(text: str) -> str:
    """Drop segments that repeat (or are contained in) another segment.

    Two source atoms can carry the same sentence from adjacent extraction units
    ("…视为交付完成；甲方负责人在验收单上签字…视为交付完成"); the displayed
    requirement must state it once.  A segment may also *continue* the previous
    one with a few repeated characters ("…应付之日 起给甲方" + "起给甲方 的支付
    宽限期…"): the repeat is dropped and the two are joined.
    """

    raw = _clean(text)
    if not raw:
        return ""
    segments = [piece.strip() for piece in re.split(r"[；;]", raw) if piece.strip()]
    if len(segments) <= 1:
        return strip_leading_overlap("", raw) or raw
    kept: list[str] = []
    for segment in segments:
        flat = _flatten(segment)
        duplicate = False
        for index, existing in enumerate(kept):
            existing_flat = _flatten(existing)
            if flat == existing_flat or flat in existing_flat:
                duplicate = True
                break
            if existing_flat in flat:
                kept.pop(index)
                break
        if duplicate:
            continue
        if kept:
            addition = strip_leading_overlap(kept[-1], segment)
            if not addition:
                continue
            if addition != segment:
                kept[-1] = f"{kept[-1]} {addition}".strip()
                continue
        kept.append(segment)
    return "；".join(kept)


__all__ = [
    "KIND_BLOCK",
    "KIND_TABLE_CELL",
    "EvidenceUnit",
    "AtomEvidence",
    "EvidenceUnitIndex",
    "build_evidence_units",
    "locate_atom",
    "locator_for_atom",
    "expected_locator_for_unit",
    "locators_match_exactly",
    "format_locator_section_for_display",
    "locator_section_for_unit",
    "printable_clause_label",
    "atom_clause_number",
    "split_numbered_items",
    "sentence_window",
    "finish_from_unit",
    "extend_fragment",
    "complete_fragment_backwards",
    "strip_leading_overlap",
    "dedupe_segments",
    "normalize_numeric_fragment",
]