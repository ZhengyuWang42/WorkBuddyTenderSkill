"""Applicable-source resolution: project-specific source over a generic template.

A tender document states many requirements *conditionally* and defers the actual
project decision to a project-specific schedule / front table / appendix::

    1.11.1 供应商须知前附表规定组织踏勘现场的，采购人按……组织供应商踏勘项目现场。

The schedule then decides the project::

    *1.11.1 | 踏勘现场 | 不组织

Rendering the generic clause is wrong: it makes the bidder prepare for an event
that will not happen, and it makes a procedural clause look like an unconditional
duty.  This module resolves the generic clause to the *project-specific* source
record that actually governs, and keeps the generic clause as history.

Design constraints (round 7):

* nothing here is case-specific: the schedule table, the reference wording and
  the clause numbers are discovered from the document itself;
* generic clauses are never deleted -- they are marked ``superseded_for_display``
  and stay in the atom stream for coverage, provenance and audit;
* a resolution always records *why* it was made (``resolution_basis`` plus the
  structural hierarchy evidence), so the decision is auditable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------- #
# vocabulary
# --------------------------------------------------------------------------- #

RELATION_OVERRIDES = "OVERRIDES"
RELATION_SPECIALIZES = "SPECIALIZES"
RELATION_RESOLVES_REFERENCE = "RESOLVES_REFERENCE"
RELATION_COMPLEMENTS = "COMPLEMENTS"
RELATION_NONE = "NO_RELATION"

RELATIONSHIPS = (
    RELATION_OVERRIDES,
    RELATION_SPECIALIZES,
    RELATION_RESOLVES_REFERENCE,
    RELATION_COMPLEMENTS,
    RELATION_NONE,
)

#: a schedule-style label cell: an optional emphasis marker plus a clause number
CLAUSE_LABEL_RE = re.compile(r"^\**\s*(\d+(?:\.\d+)+|\d+)\s*$")
#: wording that names a project-specific schedule / schedule-like table
SCHEDULE_NAME_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z]{0,10}(?:前附表|附表)")
#: a reference from a generic clause to that schedule
SCHEDULE_REFERENCE_RE = re.compile(
    r"(?:见|详见|参见|按|按照|依据)?[\u4e00-\u9fa5A-Za-z]{0,10}(?:前附表|附表)"
)
#: the *name* of a schedule, anchored at the schedule word and read leftwards
SCHEDULE_TITLE_TOKEN_RE = re.compile(
    r"(?:供应商须知前附表|投标人须知前附表|招标人须知前附表|评审办法前附表|"
    r"评标办法前附表|采购需求前附表|前附表|附表)"
)
#: conditional construction: "……规定……的，……" (the schedule switches the duty on/off)
CONDITIONAL_REFERENCE_RE = re.compile(
    r"(?:前附表|附表)[^。；;]{0,24}?(?:规定|约定|要求)[^。；;]{0,40}?(?:的|者)[，,、]"
)
#: a decisive negative project decision: the event/permission does not happen
DECISIVE_NEGATION_RE = re.compile(
    r"^(?:不|否|无|未|不予|无须|无需|不再)"
    r"(?:召开|组织|进行|安排|允许|接受|需要|设置|举行|开展|提交|适用)"
)
#: a value that is itself only a pointer to another source location
POINTER_VALUE_RE = re.compile(r"^(?:见|详见|参见|按|按照|依据)")

#: A schedule's "编列内容" is a project decision.  A cell far longer than a
#: decision is a requirement body that belongs where it is, not a resolution of
#: this clause; the *corroboration* gate below is what rejects scrambled cells.
MAX_DECISION_LENGTH = 240
#: Interleaved PDF cell text ("硬件 交 目 采 项 部分质保3 年") is extraction noise:
#: several single-character tokens between real words.  Such a row must never
#: become a project's governing value.
_INTERLEAVE_MIN_TOKENS = 2
_TOKEN_RE = re.compile(r"[\u4e00-\u9fa5]{2,}")
#: wording that only introduces the reference, never the requirement's subject
_REFERENCE_NOISE = ("前附表", "供应商须知", "投标人须知", "评审办法", "评标办法", "详见", "参见", "本项目")

#: what a resolved project value means for the bidder
OUTCOME_EVENT_NOT_HELD = "EVENT_NOT_HELD"
OUTCOME_NOT_PERMITTED = "NOT_PERMITTED"
OUTCOME_CONCRETE_VALUE = "CONCRETE_VALUE"
OUTCOME_POINTER = "POINTER"

#: clause number inside an atom's own text (used when the structure id is empty)
_ATOM_CLAUSE_RE = re.compile(r"^\**\s*(\d+(?:\.\d+)+)")


def _flatten(text: object) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or ""))


def _clean_cell(text: object) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or "")).strip()


# --------------------------------------------------------------------------- #
# schedule discovery
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ScheduleRow:
    """One project-specific schedule / front-table row ("编列内容")."""

    row_id: str
    clause: str
    marker: str
    item: str
    value: str
    page: int | None
    table_index: int
    row_index: int
    heading: str
    structure_id: str = ""

    @property
    def text(self) -> str:
        parts = [f"{self.marker}{self.clause}" if self.marker else self.clause]
        if self.item:
            parts.append(self.item)
        if self.value:
            parts.append(self.value)
        return " ".join(part for part in parts if part)

    @property
    def locator(self) -> str:
        parts = []
        if self.page:
            parts.append(f"第{self.page}页")
        if self.heading:
            parts.append(self.heading)
        parts.append(f"第{self.clause}条")
        parts.append("（pdf_table_cell）")
        return " / ".join(parts)

    @property
    def outcome(self) -> str:
        if DECISIVE_NEGATION_RE.search(_flatten(self.value)):
            if re.search(r"(允许|接受)", _flatten(self.value)):
                return OUTCOME_NOT_PERMITTED
            return OUTCOME_EVENT_NOT_HELD
        if POINTER_VALUE_RE.search(_flatten(self.value)):
            return OUTCOME_POINTER
        return OUTCOME_CONCRETE_VALUE

    def as_dict(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "clause": self.clause,
            "marker": self.marker,
            "item": self.item,
            "value": self.value,
            "page": self.page,
            "table_index": self.table_index,
            "row_index": self.row_index,
            "heading": self.heading,
            "outcome": self.outcome,
            "text": self.text,
        }


def _table_caption(document: Any, page: int | None, bbox: tuple[float, ...] | None) -> str:
    """The nearest schedule-naming heading above a table on the same page.

    A front table is named where it is introduced ("供应商须知前附表"), not inside
    the table itself, so the caption is read from the page's own text blocks.
    """

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
    best = ""
    for block in getattr(page_model, "blocks", ()) or ():
        text = _clean_cell(getattr(block, "text", ""))
        if not text:
            continue
        if not SCHEDULE_NAME_RE.fullmatch(text) and not SCHEDULE_NAME_RE.search(text):
            continue
        block_box = getattr(block, "bbox", None)
        if top is not None and block_box and block_box[1] > top:
            continue  # the caption must precede the table
        if len(text) <= 24 and len(text) > len(best):
            best = text
    if best:
        return best
    # fall back to the running heading of the page
    for block in getattr(page_model, "blocks", ()) or ():
        text = _clean_cell(getattr(block, "text", ""))
        if SCHEDULE_NAME_RE.fullmatch(text):
            return text
    return ""


def discover_schedule_rows(document: Any) -> list[ScheduleRow]:
    """Every labelled project-value row of every schedule-like table.

    Structural test (no wording test): a table whose first column is a clause
    number and whose remaining cells hold the project's own item/value pair.
    """

    rows: list[ScheduleRow] = []
    counter = 0
    for table in getattr(document, "tables", ()) or ():
        table_rows = list(getattr(table, "rows", ()) or ())
        labelled = 0
        for row in table_rows:
            cells = sorted(getattr(row, "cells", ()) or (), key=lambda cell: cell.column_index)
            if not cells:
                continue
            label = _clean_cell(cells[0].text)
            if label and CLAUSE_LABEL_RE.match(label):
                labelled += 1
        if labelled < 2:
            continue
        page = getattr(table, "page", None)
        bbox = getattr(table, "bbox", None)
        heading = _table_caption(document, page, bbox)
        for row in table_rows:
            cells = sorted(getattr(row, "cells", ()) or (), key=lambda cell: cell.column_index)
            if not cells:
                continue
            label = _clean_cell(cells[0].text)
            match = CLAUSE_LABEL_RE.match(label) if label else None
            if not match:
                continue
            marker = "*" if label.lstrip().startswith("*") else ""
            item = _clean_cell(cells[1].text) if len(cells) > 1 else ""
            value = _clean_cell("；".join(cell.text for cell in cells[2:])) if len(cells) > 2 else ""
            if not value:
                continue
            counter += 1
            rows.append(
                ScheduleRow(
                    row_id=f"SCH{counter:04d}",
                    clause=match.group(1),
                    marker=marker,
                    item=item,
                    value=value,
                    page=page,
                    table_index=int(getattr(table, "table_index", 0)),
                    row_index=int(getattr(row, "row_index", 0)),
                    heading=heading,
                    structure_id=f"{'*' if marker else ''}{match.group(1)}",
                )
            )
    return rows


# --------------------------------------------------------------------------- #
# resolution
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ApplicableSourceResolution:
    """One generic source clause resolved to its project-specific source."""

    generic_atom_id: str
    specific_row_id: str
    specific_atom_id: str
    relationship: str
    applicable_atom_ids: tuple[str, ...]
    superseded_for_display_atom_ids: tuple[str, ...]
    resolution_basis: str
    source_hierarchy_evidence: dict[str, Any] = field(default_factory=dict)
    generic_text: str = ""
    specific_text: str = ""
    applicable_page: int | None = None
    applicable_heading: str = ""
    applicable_clause: str = ""
    applicable_locator: str = ""
    outcome: str = OUTCOME_CONCRETE_VALUE
    reference_name: str = ""
    clause: str = ""

    @property
    def specific_value_text(self) -> str:
        """The schedule's own item/value wording, without the clause label."""

        text = str(self.specific_text or "")
        clause_token = str(self.applicable_clause or "")
        if clause_token and text.startswith(clause_token):
            text = text[len(clause_token) :].strip()
        return text

    def as_dict(self) -> dict[str, Any]:
        return {
            "generic_atom_id": self.generic_atom_id,
            "specific_row_id": self.specific_row_id,
            "specific_atom_id": self.specific_atom_id,
            "relationship": self.relationship,
            "applicable_atom_ids": list(self.applicable_atom_ids),
            "superseded_for_display_atom_ids": list(self.superseded_for_display_atom_ids),
            "resolution_basis": self.resolution_basis,
            "source_hierarchy_evidence": self.source_hierarchy_evidence,
            "generic_text": self.generic_text,
            "specific_text": self.specific_text,
            "applicable_page": self.applicable_page,
            "applicable_heading": self.applicable_heading,
            "applicable_clause": self.applicable_clause,
            "applicable_locator": self.applicable_locator,
            "outcome": self.outcome,
            "reference_name": self.reference_name,
            "clause": self.clause,
        }


def _atom_clause(atom: Any) -> str:
    """The clause number an atom is keyed by (structure id first, then its text)."""

    structure = str(getattr(atom, "source_structure_id", "") or "").strip().lstrip("*")
    structure = structure.replace("*", "")
    if CLAUSE_LABEL_RE.match(structure):
        return structure
    text = str(getattr(atom, "source_text", "") or "")
    match = _ATOM_CLAUSE_RE.match(text.strip())
    return match.group(1) if match else ""


def _reference_names(text: str) -> list[str]:
    """Every schedule name this text refers to (longest first).

    Only the schedule's *own* name counts ("供应商须知前附表"), never the words a
    clause happens to put in front of it ("供应商应按供应商须知前附表").
    """

    names: list[str] = []
    for match in SCHEDULE_TITLE_TOKEN_RE.finditer(str(text or "")):
        name = match.group(0)
        if name not in names:
            names.append(name)
    return sorted(names, key=len, reverse=True)


def _is_conditional_reference(text: str) -> bool:
    return bool(CONDITIONAL_REFERENCE_RE.search(text))


def _is_interleaved(text: str) -> bool:
    """True when PDF cell extraction scrambled another column into this cell.

    A front-table cell holds the project's own words.  When extraction merged a
    neighbouring column into the cell, the cell's text no longer reads as one
    statement: a *stray* character from another column lands at the cell's edge
    (``技术要求 台详见招标文件第五章内容平`` -- the ``台``/``平`` of another
    row) or the same character both opens and closes the cell.
    """

    body = _clean_cell(text)
    if not body:
        return False
    compact = re.sub(r"\s+", "", body)
    if len(compact) >= 12 and compact[-1] in compact[:8] and compact[-1] not in "。；;%的）)":
        return True
    return False


def _page_texts(document: Any, page: int | None) -> list[str]:
    """The flattened reading-order text of every block on a page."""

    if page is None:
        return []
    for candidate in getattr(document, "pages", ()) or ():
        if getattr(candidate, "page_number", None) != page:
            continue
        out: list[str] = []
        for block in getattr(candidate, "blocks", ()) or ():
            text = _clean_cell(getattr(block, "text", ""))
            if text:
                out.append(_flatten(text))
        return out
    return []


def _row_is_corroborated(row: ScheduleRow, document: Any) -> bool:
    """Is the row's value text the source actually reads in order?

    A front-table cell can be extracted with a neighbouring column merged into
    it, which shows up at the cell's *tail* ("…A座2401室平易", "…第五章内容平")
    or as a stray character at its head ("台详见招标文件第五章内容…").  The
    project value must be text the page reads in reading order: the value's own
    tail must appear in the page's blocks, in order.
    """

    if document is None:
        return True
    value = _flatten(row.value)
    if not value:
        return False
    texts = _page_texts(document, row.page)
    if not texts:
        return True
    reading_order = "".join(texts)
    if value in reading_order:
        return True
    # a wrapped cell is read as consecutive blocks: the value's head and tail
    # must both be present in reading order
    tail = value[-10:] if len(value) > 10 else value
    head = value[:10] if len(value) > 10 else value
    return bool(tail) and tail in reading_order and bool(head) and head in reading_order


def _facet_answers_concern(text: str, row: ScheduleRow) -> bool:
    """Does the schedule row state the *same* subject the generic clause names?

    A schedule's row for one clause number is not automatically the project
    decision of the generic clause that cites it: CASE002's row for 1.3.5 states
    the implementation period while the generic clause asks about the warranty.
    The row's own item name must carry the clause's subject.
    """

    subject = _flatten(text)
    for noise in _REFERENCE_NOISE:
        subject = subject.replace(_flatten(noise), "")
    subject = re.sub(r"^\**\s*\d+(\.\d+)*", "", subject)
    subject = re.sub(r"[\s\u3000。；;，,、：:（）()的]+", "", subject)
    item = _flatten(row.item) or _flatten(row.value)
    if not subject or not item:
        return True
    if subject[:2] and subject[:2] in item:
        return True
    if item and item in subject:
        # the schedule's item name answers the clause ("采购预备会" in 1.10.1)
        return True
    # the row answers the clause when the two share a real content token
    tokens = [token for token in _TOKEN_RE.findall(subject) if len(token) >= 2]
    return any(token and token in item for token in tokens)


def _row_is_usable(row: ScheduleRow) -> bool:
    """Can this schedule row stand in for the generic clause on a review row?"""

    value = _flatten(row.value)
    if not value or row.outcome == OUTCOME_POINTER:
        return False
    if len(value) > MAX_DECISION_LENGTH:
        return False
    return not _is_interleaved(row.text)


def _value_is_usable(resolution: ApplicableSourceResolution) -> bool:
    """Whether a resolved project value may replace the generic clause."""

    value = _flatten(resolution.specific_value_text)
    if not value:
        return False
    if resolution.outcome == OUTCOME_POINTER:
        return False
    if len(value) > MAX_DECISION_LENGTH:
        # a long cell is a requirement body, not a project decision
        return False
    if _is_interleaved(resolution.specific_text):
        return False
    return True


def _is_specializing_reference(text: str) -> bool:
    """Does the clause state its own duty and defer a parameter to the schedule?

    A clause with its own obligation ("成交供应商应按供应商须知前附表规定的形式、
    金额…提交履约保证金", "签字或盖章的具体要求见供应商须知前附表") is completed
    by the project value rather than replaced by it.  A clause with no obligation
    of its own is a pure pointer (``RESOLVES_REFERENCE``) or a conditional
    (``OVERRIDES``).
    """

    flat = _flatten(text)
    if not SCHEDULE_REFERENCE_RE.search(flat):
        return False
    return bool(re.search(r"(应|须|应当|必须|不得|需)", flat))


def _reference_only_text(text: str) -> bool:
    """True when the clause adds no content besides pointing at the schedule."""

    stripped = SCHEDULE_REFERENCE_RE.sub("", str(text or ""))
    stripped = re.sub(r"[\s\u3000。；;，,、：:（）()的]+", "", stripped)
    stripped = re.sub(r"^\**\s*\d+(\.\d+)*", "", stripped)
    # "是否允许分包" style question stems are content-free
    stripped = re.sub(r"^(是否|能否)", "", stripped)
    return len(stripped) <= 12


def _heading_matches(reference: str, heading: str) -> bool:
    if not reference or not heading:
        # an unnamed "前附表" reference is satisfied by any schedule caption
        return bool(reference) != bool(heading) or True
    if reference in heading or heading in reference:
        return True
    return _flatten(reference)[-3:] == _flatten(heading)[-3:]


def resolve_applicable_sources(
    atoms: Sequence[Any],
    schedule_rows: Sequence[ScheduleRow],
    document: Any = None,
) -> list[ApplicableSourceResolution]:
    """Resolve every generic atom that a project-specific schedule decides.

    A candidate must (a) refer to a schedule, (b) be keyed by a clause number the
    schedule also carries, (c) state the same subject the clause asks about, and
    (d) be text the source actually reads in order (a cell that extraction merged
    with a neighbouring column is not a project decision).
    """

    by_clause: dict[str, list[ScheduleRow]] = {}
    for row in schedule_rows:
        by_clause.setdefault(row.clause, []).append(row)
    resolutions: list[ApplicableSourceResolution] = []
    for atom in atoms:
        text = str(getattr(atom, "source_text", "") or "")
        if not text or not SCHEDULE_REFERENCE_RE.search(text):
            continue
        relation = ""
        if _reference_only_text(text):
            relation = RELATION_RESOLVES_REFERENCE
        elif _is_conditional_reference(text):
            relation = RELATION_OVERRIDES
        elif _is_specializing_reference(text):
            # the clause states its own obligation and defers one of its
            # parameters to the schedule ("按前附表规定的形式、金额…提交履约
            # 保证金"): the project value completes the clause instead of
            # replacing it
            relation = RELATION_SPECIALIZES
        else:
            continue
        clause = _atom_clause(atom)
        if not clause:
            continue
        candidates = [
            row
            for row in by_clause.get(clause, ())
            if _heading_matches(
                _reference_names(text)[0] if _reference_names(text) else "", row.heading
            )
        ]
        if not candidates and "." in clause:
            # the schedule may key the decision at the parent section ("7.3
            # 履约保证金" decides 7.3.1): the reference still resolves
            parent = clause.rsplit(".", 1)[0]
            candidates = [
                row
                for row in by_clause.get(parent, ())
                if _heading_matches(
                    _reference_names(text)[0] if _reference_names(text) else "", row.heading
                )
            ]
        if not candidates:
            continue
        # the schedule row wins over a table that only repeats the pointer
        candidates.sort(
            key=lambda row: (
                row.outcome == OUTCOME_POINTER,
                not _row_is_usable(row),
                len(_flatten(row.value)),
                row.page or 0,
                row.row_index,
            )
        )
        usable = [
            row
            for row in candidates
            if _row_is_usable(row) and _row_is_corroborated(row, document)
        ]
        if not usable:
            # the schedule states no usable project decision for this clause: the
            # generic clause stays the displayed requirement (never a noisy row)
            continue
        specific = usable[0]
        if not _facet_answers_concern(text, specific):
            # the schedule row's own item must answer the generic clause's
            # question (1.3.5 质保期 answers 质保期; 1.3.2 实施周期 does not)
            continue
        if relation == RELATION_RESOLVES_REFERENCE and specific.outcome == OUTCOME_POINTER:
            # the schedule only points further on: the value is still unresolved
            relation = RELATION_RESOLVES_REFERENCE
        resolutions.append(
            ApplicableSourceResolution(
                generic_atom_id=str(getattr(atom, "atom_id", "")),
                specific_row_id=specific.row_id,
                specific_atom_id="",
                relationship=relation,
                applicable_atom_ids=(),
                superseded_for_display_atom_ids=(
                    (str(getattr(atom, "atom_id", "")),)
                    if relation != RELATION_SPECIALIZES
                    else ()
                ),
                resolution_basis=(
                    "the generic clause defers the project decision to the schedule "
                    f"({specific.heading or '前附表'}) and the schedule carries clause "
                    f"{clause}"
                ),
                source_hierarchy_evidence={
                    "specific_source": {
                        "kind": "schedule_row",
                        "table_index": specific.table_index,
                        "row_index": specific.row_index,
                        "page": specific.page,
                        "heading": specific.heading,
                        "clause": specific.clause,
                        "item": specific.item,
                        "value": specific.value,
                    },
                    "generic_source": {
                        "kind": "bidder_instructions_clause",
                        "atom_id": str(getattr(atom, "atom_id", "")),
                        "page": getattr(atom, "source_page", None),
                        "clause": clause,
                    },
                    "conditional_reference": _is_conditional_reference(text),
                },
                generic_text=text,
                specific_text=specific.text,
                applicable_page=specific.page,
                applicable_heading=specific.heading,
                applicable_clause=specific.clause,
                applicable_locator=specific.locator,
                outcome=specific.outcome,
                reference_name=_reference_names(text)[0] if _reference_names(text) else "",
                clause=clause,
            )
        )
    return resolutions


def schedule_atom_id(resolution: ApplicableSourceResolution) -> str:
    return f"SCH-{resolution.specific_row_id}"


def _existing_schedule_atom(atoms: Sequence[Any], resolution: ApplicableSourceResolution):
    """The atom the extractor already produced for this schedule row, if any."""

    value = _flatten(resolution.specific_value_text)
    clause = resolution.applicable_clause
    for atom in atoms:
        structure = str(getattr(atom, "source_structure_id", "") or "").replace("*", "")
        text = _flatten(getattr(atom, "source_text", ""))
        if structure != clause:
            continue
        if value and value not in text:
            continue
        page = getattr(atom, "source_page", None)
        if resolution.applicable_page and page and page != resolution.applicable_page:
            continue
        return atom
    return None


def apply_applicable_resolutions(
    atoms: Sequence[Any],
    resolutions: Sequence[ApplicableSourceResolution],
) -> tuple[list[ApplicableSourceResolution], list[Any]]:
    """Apply the resolutions to the atom stream (additive, never destructive).

    Returns the applied resolutions (with their ``specific_atom_id`` filled in)
    and the new atom stream.  The generic clause keeps its text and stays in the
    stream: it is only marked ``superseded_for_display`` so coverage, provenance
    and the marker audit still see it.
    """

    from dataclasses import replace

    from .review_concern import SourceRequirementAtom  # local: avoids an import cycle

    stream = list(atoms)
    applied: list[ApplicableSourceResolution] = []
    for resolution in resolutions:
        if resolution.outcome == OUTCOME_POINTER:
            # the schedule only points on (a reference chain): the reference
            # propagation owns that case, and there is no project value to show
            continue
        if resolution.relationship == RELATION_SPECIALIZES and not resolution.applicable_atom_ids:
            # the clause keeps its own wording and gains the project's parameter:
            # the generic clause stays displayed, and the schedule value joins it
            generic = next(
                (
                    atom
                    for atom in stream
                    if str(getattr(atom, "atom_id", "")) == resolution.generic_atom_id
                ),
                None,
            )
            if generic is None:
                continue
            specific = _existing_schedule_atom(stream, resolution)
            if specific is None:
                spec_id = f"APL{resolution.specific_row_id[-4:]}"
                specific = next(
                    (atom for atom in stream if str(getattr(atom, "atom_id", "")) == spec_id),
                    None,
                )
            if specific is None:
                # the schedule row never became an atom (its clause keys a parent
                # section, as "7.3 履约保证金" decides 7.3.1): create the
                # project-value atom so the clause can display its parameter
                specific = _schedule_atom(resolution, generic)
                stream.append(specific)
            generic.applicability_relation = resolution.relationship
            specific.applicability_relation = resolution.relationship
            specific.applicable_of_atom_id = str(getattr(generic, "atom_id", ""))
            applied.append(
                replace(
                    resolution,
                    specific_atom_id=str(getattr(specific, "atom_id", "")),
                    applicable_atom_ids=(str(getattr(specific, "atom_id", "")),),
                )
            )
            continue
        generic = next(
            (
                atom
                for atom in stream
                if str(getattr(atom, "atom_id", "")) == resolution.generic_atom_id
            ),
            None,
        )
        if generic is None:
            continue
        specific = _existing_schedule_atom(stream, resolution)
        if specific is None:
            specific = _schedule_atom(resolution, generic)
            stream.append(specific)
        generic.superseded_for_display = True
        generic.applicability_relation = resolution.relationship
        specific.applicability_relation = resolution.relationship
        specific.applicable_of_atom_id = str(getattr(generic, "atom_id", ""))
        applied.append(
            replace(
                resolution,
                specific_atom_id=str(getattr(specific, "atom_id", "")),
                applicable_atom_ids=(str(getattr(specific, "atom_id", "")),),
            )
        )
    return applied, stream


def _schedule_atom(resolution: ApplicableSourceResolution, generic: Any) -> Any:
    """The project-value atom a resolution contributes to the stream.

    It inherits the generic clause's facet metadata (actor, object, topic,
    requirement type, authority) so the concern that owns the clause keeps owning
    the project's own value, and it carries the schedule row's own page, heading,
    clause and locator so the row can cite the value's real source.
    """

    from .review_concern import SourceRequirementAtom  # local: avoids an import cycle

    return SourceRequirementAtom(
        atom_id=f"APL{resolution.specific_row_id[-4:]}",
        source_clause_id=str(getattr(generic, "source_clause_id", "")),
        source_text=resolution.specific_text,
        source_page=resolution.applicable_page,
        source_section=resolution.applicable_heading,
        source_locator=resolution.applicable_locator,
        source_structure_id=resolution.applicable_clause or resolution.clause,
        actor=str(getattr(generic, "actor", "")),
        object=str(getattr(generic, "object", "")),
        action=str(getattr(generic, "action", "")),
        topic=str(getattr(generic, "topic", "")),
        requirement_kind=str(getattr(generic, "requirement_kind", "")),
        modality=str(getattr(generic, "modality", "")),
        authority_scope=str(getattr(generic, "authority_scope", "")),
        requirement_type=str(getattr(generic, "requirement_type", "")),
        source_parent_id=str(getattr(generic, "atom_id", "")),
        owner_concern_id=str(getattr(generic, "owner_concern_id", "")),
        owner_reason=str(getattr(generic, "owner_reason", "")),
        mandatory=bool(getattr(generic, "mandatory", False)),
        high_risk=bool(getattr(generic, "high_risk", False)),
        internal=bool(getattr(generic, "internal", False)),
    )


def _concern_atom_ids(concern: Any) -> set[str]:
    ids = getattr(concern, "atom_ids", None)
    if callable(ids):
        ids = ids()
    if ids is None:
        ids = [str(getattr(atom, "atom_id", "")) for atom in getattr(concern, "atoms", ())]
    return {str(atom_id) for atom_id in ids}


def resolution_for_concern(
    concern: Any,
    resolutions: Sequence[ApplicableSourceResolution],
    summary: str = "",
):
    """The resolution that governs a concern (through its own atoms).

    A concern may own several schedule clauses (a delivery-location concern owns
    both 建设地点 and 交货地点).  The resolution that governs the row is the one
    the row's own source text refers to -- otherwise the row would display a
    neighbouring clause's value and lose that clause's source marker.
    """

    owned = _concern_atom_ids(concern)
    facet_ids = {
        str(getattr(atom, "atom_id", ""))
        for atom in (getattr(concern, "facet_atoms", list)() or [])
    }
    # the concern's own question, used when it owns no clearly-matching atom
    facet_text = _flatten(getattr(concern, "label", "") or "")
    candidates = [
        resolution
        for resolution in resolutions
        if resolution.generic_atom_id in owned
        or any(atom_id in owned for atom_id in resolution.applicable_atom_ids)
    ]
    if not candidates:
        return None
    # The resolution must answer *this* concern's question.  A concern may own a
    # neighbouring clause's atom -- and the resolved value may already belong to
    # another concern that asked first -- so the concern's own contract decides.
    facet_candidates = [
        resolution
        for resolution in candidates
        if _resolution_answers_concern(concern, resolution)
    ]
    if facet_candidates:
        candidates = facet_candidates
    elif facet_text:
        return None
    # the resolved value must belong to this concern (or to no concern yet): a
    # value another concern already displays is that concern's requirement
    mine = [
        resolution
        for resolution in candidates
        if resolution.specific_atom_id in owned
    ]
    if len(candidates) > 1 and mine:
        candidates = mine
    if len(candidates) == 1:
        return candidates[0]
    atoms = list(getattr(concern, "atoms", ()))
    by_id = {str(getattr(atom, "atom_id", "")): atom for atom in atoms}
    probe = _flatten(summary)
    if not probe:
        probe = "".join(
            _flatten(getattr(atom, "source_text", "")) for atom in getattr(concern, "facet_atoms", list)()
        )
    facet = _flatten(getattr(concern, "label", "") or "")

    def facet_score(resolution: ApplicableSourceResolution) -> tuple[int, int, int]:
        """How well this resolution answers the concern's own question."""

        applicable = by_id.get(resolution.specific_atom_id) or by_id.get(
            resolution.generic_atom_id
        )
        # 1. the row's own text cites this clause ("…符合第二章…第 1.4.6 款规定")
        clause_hit = 1 if resolution.clause and resolution.clause in probe else 0
        # 2. the schedule row's item name answers the concern's question
        item = _flatten(getattr(applicable, "source_section", "") or "")
        item_hit = 1 if facet and item and (facet in item or item in facet) else 0
        # 3. a directly source-marked applicable clause outranks an unmarked one
        marked = 1 if _atom_marked(applicable) else 0
        return (clause_hit, item_hit, marked)

    candidates.sort(key=facet_score, reverse=True)
    return candidates[0]


def _resolution_answers_concern(concern: Any, resolution: ApplicableSourceResolution) -> bool:
    """Does this project value answer the concern's own question?

    The concern's hand-authored contract names the vocabulary its requirement must
    carry ("技术方案|实施方案|…").  The project value, or the clause it replaces,
    must carry it -- otherwise the resolution belongs to another concern that
    happens to share the clause.
    """

    from .concern_contract import contract_for

    spec = contract_for(str(getattr(concern, "concern_id", "") or ""))
    if not spec.required_signatures:
        return True
    probe = _flatten(
        f"{getattr(resolution, 'specific_text', '')}"
        f"{getattr(resolution, 'generic_text', '')}"
    )
    if not probe:
        return True
    # a value the concern's own contract forbids belongs to a *different* concern
    # ("金额：…" is the bond amount, not the bond form)
    if spec.forbidden_signatures:
        value = _flatten(str(getattr(resolution, "specific_value_text", "") or ""))
        if value and any(re.search(pattern, value) for pattern in spec.forbidden_signatures):
            return False
    return any(re.search(pattern, probe) for pattern in spec.required_signatures)


def _resolution_subject_overlap(facet: str, resolution: ApplicableSourceResolution) -> int:
    """How many of the concern's own tokens the schedule row's item shares."""

    if not facet:
        return 0
    tokens = [
        token
        for token in _TOKEN_RE.findall(str(getattr(resolution, "specific_text", "")))
        if len(token) >= 2
    ]
    return sum(1 for token in tokens if token in facet)


def _resolution_subject_match(facet: str, resolution: ApplicableSourceResolution) -> bool:
    """Does the schedule row's item answer the concern's own question?

    The concern is named by the human question it asks ("技术方案与实施组织"),
    and the schedule row by the project's own item name ("实施周期及供货地点").
    At least one real content token must be shared for the row to be this
    concern's own requirement.
    """

    if not facet:
        return True
    return _resolution_subject_overlap(facet, resolution) > 0


def _atom_marked(atom: Any) -> bool:
    """Does the atom's own text carry a source emphasis marker?"""

    return bool(re.match(r"^\s*[\*★☆]", str(getattr(atom, "source_text", "") or "")))


def resolution_subject(resolution: ApplicableSourceResolution) -> str:
    """The source's own name for what this project decision is about.

    The *schedule row's* own item ("采购预备会", "踏勘现场", "分包") names the
    decision; the review concern's label ("提问与澄清截止") is the reviewer's
    question and must never be spliced into the decision's wording.  Doing so
    produced actions such as "确认本项目提问与澄清截止采购预备会 不召开", which
    attaches one question's subject to another row's decision (round-8 fixture
    D56).
    """

    evidence = resolution.source_hierarchy_evidence or {}
    specific = evidence.get("specific_source") or {}
    item = _clean_cell(specific.get("item") or "")
    if not item:
        # the schedule row's own value is "<item> <decision>"; the item is its head
        value = _clean_cell(resolution.specific_value_text)
        clause = _clean_cell(resolution.applicable_clause)
        if clause and value.startswith(clause):
            value = value[len(clause) :].strip()
        item = value
    for decision in ("不召开", "不组织", "不允许", "不接受", "不进行", "不安排", "无需", "无须"):
        if item.endswith(decision):
            item = item[: -len(decision)].strip(" ：:，,；;　")
            break
    return item.strip(" ：:，,；;　")


def _cited_decision(resolution: ApplicableSourceResolution, decision: str) -> str:
    """The schedule row's own decision, cited once with its clause label.

    A front-table row is printed as "*1.12 分包 不允许": the row's own clause
    label (and its source marker) are already inside the value, so prefixing the
    applicable clause again produced the delivered sentence
    "确认本项目分包：1.12 *1.12分包不允许" -- the clause was named twice and the
    row's emphasis marker was spliced into an instruction (round-8 fixture
    DR033).  The clause is cited exactly once and the marker stays where it
    belongs, on the source row.
    """

    clause = _clean_cell(resolution.applicable_clause)
    body = _clean_cell(decision).lstrip("*★☆")
    if clause and body.startswith(clause):
        body = body[len(clause) :].lstrip("*★☆ 、.．:：")
    body = body.strip(" 、；;，,。")
    if clause and body:
        return f"{clause} {body}"
    return body or clause


def action_for_resolution(resolution: ApplicableSourceResolution, subject: str = "") -> str:
    """The operational review action the *project value* implies.

    The value drives the action: a project that does not hold the event is not a
    preparation duty, and a project that forbids subcontracting must be checked
    for the absence of a subcontract, not for a "conforming arrangement".

    The action names the *decision's own* subject.  ``subject`` is only a
    fallback for a resolution whose schedule row carries no item of its own.
    """

    decision = _clean_cell(resolution.specific_value_text)
    own_subject = resolution_subject(resolution)
    label = own_subject or (subject or "").strip()
    cited = _cited_decision(resolution, decision)
    if resolution.outcome == OUTCOME_EVENT_NOT_HELD:
        head = f"确认本项目{label}" if label else "确认本项目"
        return f"{head}：{cited}；不应在响应文件中作出与此矛盾的陈述。"
    if resolution.outcome == OUTCOME_NOT_PERMITTED:
        head = f"确认本项目{label}" if label else "确认本项目"
        return f"{head}：{cited}；响应文件中不得出现与之相矛盾的安排或陈述。"
    return ""


def resolution_is_project_decision(resolution: ApplicableSourceResolution) -> bool:
    """Is this row a project decision the schedule took for the bidder?

    The schedule row decides the project ("采购预备会 不召开", "踏勘现场 不组织",
    "分包 不允许").  Such a row sorts last, which is what keeps its *displayed*
    risk from renumbering the rows the human's findings are addressed by.  The
    flag is about the row's origin, never about its risk: the two decisions have
    opposite risk semantics (see :func:`risk_is_informational`).
    """

    return resolution.outcome in {OUTCOME_EVENT_NOT_HELD, OUTCOME_NOT_PERMITTED}


def risk_is_informational(resolution: ApplicableSourceResolution) -> bool:
    """Does this decision switch a bidder duty off, leaving no positive work?

    Only an event the project does not hold ("采购预备会 不召开", "踏勘现场 不
    组织") removes work: there is nothing to prepare and nothing to check, so the
    row is 低 risk.  An arrangement the project does *not permit* ("分包 不允许")
    is the opposite: it places an obligation on the bidder and carries the
    clause's own rejection consequence, so it may not be shown as 低 while the
    03 sheet records a 否决依据 for it (round-8 cross-sheet fixture DR033).
    """

    return resolution.outcome == OUTCOME_EVENT_NOT_HELD


__all__ = [
    "RELATIONSHIPS",
    "RELATION_OVERRIDES",
    "RELATION_SPECIALIZES",
    "RELATION_RESOLVES_REFERENCE",
    "RELATION_COMPLEMENTS",
    "RELATION_NONE",
    "OUTCOME_EVENT_NOT_HELD",
    "OUTCOME_NOT_PERMITTED",
    "OUTCOME_CONCRETE_VALUE",
    "OUTCOME_POINTER",
    "ScheduleRow",
    "ApplicableSourceResolution",
    "discover_schedule_rows",
    "resolve_applicable_sources",
    "apply_applicable_resolutions",
    "resolution_for_concern",
    "resolution_subject",
    "schedule_atom_id",
    "action_for_resolution",
    "resolution_is_project_decision",
    "risk_is_informational",
]
