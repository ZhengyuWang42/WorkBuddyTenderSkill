"""Round 6: source-visible criticality semantics.

Round 5 established that a *displayed* review row is validated by an
independent :mod:`tender_basic.concern_contract` spec, so a row can no longer
show text its concern does not own.  That gate is semantic, but it is not
enough: the delivered workbook could still drop the tender's own **criticality**
signals, because nothing modelled them.

The observable defect (CASE001 workbook5) was that a source-visible leading
``*`` on a 供应商须知前附表 clause number was lost during requirement
atomization, so the same tender produced ``★`` on ``*10.1 最高限价`` while
``*1.4.5 供货期`` / ``*1.4.7 质量要求`` / ``*1.5.2 是否接受联合体响应`` and the
starred technical line ``*流量计等相关计量仪器需提供第三方检测实验报告``
arrived with a blank marker column.

This module models the source semantics explicitly, in three *separate*
dimensions.  They are never collapsed into one flag, and none of them is
inferred from how important the model thinks a clause is:

``SOURCE_MARKER``
    the raw emphasis marker, preserved verbatim (``*`` stays ``*``, never
    rewritten as ``★``).  Owned by the source format.

``SUBSTANTIVE_REQUIREMENT``
    proven by a *governing clause* in the document itself (CASE001: clause
    10.8 lists starred clauses, clauses using 拒绝/不（予）接受/不得/不允许/
    否决/无效 wording, and applicable law), or inherited through an explicit
    source reference (``*1.5.1`` -> 询比公告"第二款 供应商资格要求").

``REJECTION_CONSEQUENCE``
    proven by a consequence rule (a rejection clause listing "不符合询比文件
    规定的其他实质性要求的" as a ground, or a clause-specific consequence such
    as "修正后的最终响应报价若超过最高限价，评审小组应当否决其响应").  A
    marker alone never implies rejection.

Everything is discovered from the document: no case id, page number, project
literal, or marker-to-rejection shortcut is used anywhere in this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "v1_source_criticality/1"

# --------------------------------------------------------------------------- #
# marker vocabulary (source format)
# --------------------------------------------------------------------------- #

MARKER_CHARS: tuple[str, ...] = ("*", "★", "▲", "◆", "●")
MARKER_CLASS = "".join(re.escape(char) for char in MARKER_CHARS)
#: The single indicator the *reviewer* sees; ``raw_source_marker`` keeps the
#: character the source actually used.
VISIBLE_MARKER = "★"

MARKER_SOURCE_TABLE_CELL = "TABLE_CELL"
MARKER_SOURCE_INLINE = "INLINE_TEXT"

# --------------------------------------------------------------------------- #
# substantive basis kinds / criticality levels / visible types
# --------------------------------------------------------------------------- #

BASIS_SOURCE_MARKER = "SOURCE_MARKER"
BASIS_EXPLICIT_WORDING = "EXPLICIT_WORDING"
BASIS_LEGAL_RULE = "LEGAL_RULE"
BASIS_REFERENCE_PROPAGATION = "REFERENCE_PROPAGATION"
BASIS_OTHER = "OTHER"

BASIS_KINDS: tuple[str, ...] = (
    BASIS_SOURCE_MARKER,
    BASIS_EXPLICIT_WORDING,
    BASIS_LEGAL_RULE,
    BASIS_REFERENCE_PROPAGATION,
    BASIS_OTHER,
)

CRITICALITY_ORDINARY = "ORDINARY"
CRITICALITY_SUBSTANTIVE = "SUBSTANTIVE"
CRITICALITY_SUBSTANTIVE_REJECTION = "SUBSTANTIVE_REJECTION"
#: Marked by the source, and the source says the marker means "supply the
#: proof" (or "scored") -- a review obligation without a substantive/rejection
#: claim.
CRITICALITY_MANDATORY = "MANDATORY"

MANDATORY_TYPE_STARRED = "SUBSTANTIVE_STARRED"
MANDATORY_TYPE_WORDING = "SUBSTANTIVE_EXPLICIT_WORDING"
MANDATORY_TYPE_REFERENCE = "SUBSTANTIVE_VIA_REFERENCE"
MANDATORY_TYPE_LEGAL = "SUBSTANTIVE_BY_LAW"
MANDATORY_TYPE_REJECTION = "REJECTION"
#: A marked requirement the source defines as "must be proven with materials"
#: rather than as a substantive/rejection requirement (CASE002's ★).
MANDATORY_TYPE_PROOF = "MANDATORY"
#: A marked requirement the source ties to scoring only.
MANDATORY_TYPE_SCORED = "SCORED_MARKER"
#: A marked clause whose meaning the source never states: the marker is still
#: visible data, but no substantive/rejection status may be inferred from it.
MANDATORY_TYPE_UNCLASSIFIED = "MARKER_UNCLASSIFIED"

#: What a document says its own emphasis marker *means*.  A marker is semantic
#: data only through one of these source statements, never by assumption.
SEMANTICS_SUBSTANTIVE = "SUBSTANTIVE_REQUIREMENT"
SEMANTICS_PROOF = "MANDATORY_PROOF"
SEMANTICS_SCORING = "SCORING_WEIGHT"
SEMANTICS_UNESTABLISHED = "UNESTABLISHED"

#: Resolution order when a document uses one marker with several statements.
SEMANTICS_PRIORITY: tuple[str, ...] = (
    SEMANTICS_SUBSTANTIVE,
    SEMANTICS_PROOF,
    SEMANTICS_SCORING,
)

#: Terms a document uses when it defines what its marker means.
SEMANTICS_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        SEMANTICS_SUBSTANTIVE,
        (
            "实质性要求",
            "实质性响应",
            "实质性条款",
            "实质性内容",
            "无效响应",
            "废标",
        ),
    ),
    (
        SEMANTICS_PROOF,
        (
            "提供证明材料",
            "提供证明",
            "提供相关证明",
            "提供材料",
            "加盖原厂",
            "授权证明",
            "须提供",
            "须附",
        ),
    ),
    (SEMANTICS_SCORING, ("得分", "扣分", "加分", "评分")),
)

REJECTION_EXPLICIT = "EXPLICIT"
REJECTION_DERIVED = "DERIVED"

REJECTION_TRIGGER_SUBSTANTIVE = "SUBSTANTIVE_REQUIREMENT"
REJECTION_TRIGGER_SPECIFIC_CLAUSE = "SPECIFIC_CLAUSE"
REJECTION_TRIGGER_GENERAL = "GENERAL_REJECTION"

COVERAGE_DELIVERED_ROW = "DELIVERED_REVIEW_ROW"
COVERAGE_REFERENCE_CHILD = "REFERENCE_PROPAGATION_CHILD"
COVERAGE_BACKGROUND_ROW = "NON_BIDDER_ACTIONABLE_ROW"
COVERAGE_REFERENCE_PARENT = "REFERENCE_PARENT_CLAUSE"
COVERAGE_UNCOVERED = "UNCOVERED"

# --------------------------------------------------------------------------- #
# marker / clause / rule patterns
# --------------------------------------------------------------------------- #

_CLAUSE_NUMBER = r"\d{1,2}(?:\.\d{1,2}){1,4}"

_MARKER_CELL_RE = re.compile(rf"^\s*([{MARKER_CLASS}])\s*({_CLAUSE_NUMBER})\s*$")
_PLAIN_CLAUSE_RE = re.compile(rf"^\s*({_CLAUSE_NUMBER})\s*$")
_LEADING_MARKER_RE = re.compile(rf"^\s*([{MARKER_CLASS}])\s*")
_LEADING_MARKER_CLAUSE_RE = re.compile(rf"^\s*([{MARKER_CLASS}])\s*({_CLAUSE_NUMBER})")
_INLINE_LINE_RE = re.compile(rf"^\s*([{MARKER_CLASS}])\s*(\S.*)$")

#: A consequence rule uses the document's own rejection wording.
REJECTION_CUES: tuple[str, ...] = (
    "否决",
    "无效",
    "不予接受",
    "不接受",
    "拒绝",
    "不予受理",
)
_REJECTION_CUE_RE = re.compile("|".join(re.escape(cue) for cue in REJECTION_CUES))

#: General "failure of a substantive requirement" ground.
_SUBSTANTIVE_FAIL_RE = re.compile(
    r"(不符合|不满足|未响应|未实质性响应|不响应|背离)[^。；;]{0,24}"
    r"(实质性要求|实质性内容|实质性响应|实质性条款)"
)
#: A rejection clause that introduces an enumeration of grounds.
_REJECTION_LIST_HEAD_RE = re.compile(
    r"(有以下情形之一|有下列情形之一|下列情形之一|以下情形之一)"
)
_LIST_ITEM_RE = re.compile(r"^\s*[（(]\s*\d{1,2}\s*[）)]")
#: "…不按本章第3.4.1项要求…" -- a clause-specific consequence.
_CLAUSE_REFERENCE_RE = re.compile(
    r"第\s*(" + _CLAUSE_NUMBER + r")\s*(?:项|款|目|条)"
)

#: A clause that *defines* which source requirements are substantive.
_GOVERNING_HEAD_RE = re.compile(
    r"(实质性要求|实质性响应|实质性内容|重大偏差|无效条款|否决条款|重要条款)"
)
_QUOTED_MARKER_CLAUSE_RE = re.compile(
    rf"(?:带|用|以|有)?\s*[\u201c\"']\s*([{MARKER_CLASS}])\s*[\u201d\"']\s*(?:条款|的条款)"
)
_QUOTED_TOKEN_RE = re.compile(r"[\u201c\"']([^\u201d\"']{1,10})[\u201d\"']")
_LEGAL_RULE_RE = re.compile(r"法律\s*[、，,]?\s*法规|法规\s*[、，,]?\s*规章")
_TABLE_SCOPE_RE = re.compile(r"(本表格|前附表|下表|本表)")

#: Reference propagation: "见询比公告“第二款 供应商资格要求”".
_REFERENCE_RE = re.compile(
    r"(?:见|详见|参见|依据|按照|按)\s*[^。；;，,]{0,24}?[\u201c\"']([^\u201d\"']{2,40})[\u201d\"']"
)
_REFERENCE_TAIL_RE = re.compile(
    r"(?:见|详见|参见)\s*((?:第[一二三四五六七八九十]+章|第[一二三四五六七八九十]+款|第[一二三四五六七八九十]+条)"
    r"[^。；;，,]{0,24})"
)
_NO_ACTIONABLE_DUTY_RE = re.compile(r"(本项目|本章|本章节|本项目采购|详见|见|按照)")


def _normalize(value: object) -> str:
    return re.sub(r"[\s\u3000]+", "", str(value or ""))


def _clause_token(clause: str) -> re.Pattern[str]:
    """A clause number that must not be a prefix/suffix of a longer number."""

    return re.compile(rf"(?<![\d.]){re.escape(clause)}(?![\d])")


# --------------------------------------------------------------------------- #
# evidence records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SourceMarkerEvidence:
    """One source-visible emphasis marker, with its exact source location."""

    evidence_id: str
    raw_marker: str
    normalized_marker: str
    clause: str
    label: str
    page: int | None
    locator: str
    source_text: str
    source_kind: str
    scope: str = ""

    @property
    def is_table_label(self) -> bool:
        return self.source_kind == MARKER_SOURCE_TABLE_CELL and bool(self.clause)

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "raw_marker": self.raw_marker,
            "normalized_marker": self.normalized_marker,
            "clause": self.clause,
            "label": self.label,
            "page": self.page,
            "locator": self.locator,
            "source_text": self.source_text,
            "source_kind": self.source_kind,
            "scope": self.scope,
        }


@dataclass(frozen=True)
class SubstantiveRule:
    """A governing clause that defines substantive requirements."""

    rule_id: str
    kind: str
    markers: tuple[str, ...]
    words: tuple[str, ...]
    scope: str
    governing_atom_id: str
    governing_clause: str
    governing_text: str
    page: int | None
    locator: str
    #: What the source says its marker means (round 6).
    semantics: str = SEMANTICS_UNESTABLISHED
    semantics_all: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "kind": self.kind,
            "markers": list(self.markers),
            "words": list(self.words),
            "scope": self.scope,
            "governing_atom_id": self.governing_atom_id,
            "governing_clause": self.governing_clause,
            "governing_text": self.governing_text,
            "page": self.page,
            "locator": self.locator,
            "semantics": self.semantics,
            "semantics_all": list(self.semantics_all),
        }


@dataclass(frozen=True)
class RejectionRule:
    """A clause that states the consequence of failing a requirement."""

    rule_id: str
    consequence: str
    trigger: str
    governing_atom_id: str
    governing_clause: str
    governing_text: str
    page: int | None
    locator: str
    target_clauses: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "consequence": self.consequence,
            "trigger": self.trigger,
            "governing_atom_id": self.governing_atom_id,
            "governing_clause": self.governing_clause,
            "governing_text": self.governing_text,
            "page": self.page,
            "locator": self.locator,
            "target_clauses": list(self.target_clauses),
        }


@dataclass(frozen=True)
class SourceRequirementCriticality:
    """The source-backed criticality of one requirement atom."""

    source_atom_id: str
    raw_source_marker: str = ""
    marker_present: bool = False
    marker_source_location: str = ""
    marker_source_text: str = ""
    marker_evidence_id: str = ""
    #: What the document says its own marker means (SEMANTICS_*).
    marker_semantics: str = SEMANTICS_UNESTABLISHED
    substantive_requirement: bool | None = None
    substantive_basis_kind: str = ""
    substantive_basis_atom_ids: tuple[str, ...] = ()
    substantive_basis_text: str = ""
    explicit_rejection_consequence: bool = False
    derived_rejection_consequence: bool = False
    rejection_basis_atom_ids: tuple[str, ...] = ()
    rejection_consequence_text: str = ""
    criticality_level: str = CRITICALITY_ORDINARY
    criticality_reason: str = ""
    reference_parent_atom_id: str = ""
    reference_target: str = ""
    governing_clause_atom_id: str = ""

    @property
    def rejection_consequence(self) -> bool:
        return self.explicit_rejection_consequence or self.derived_rejection_consequence

    @property
    def rejection_kind(self) -> str:
        if self.explicit_rejection_consequence:
            return REJECTION_EXPLICIT
        if self.derived_rejection_consequence:
            return REJECTION_DERIVED
        return ""

    @property
    def mandatory_types(self) -> list[str]:
        """Repository-native 强制性类型 values, strongest source-backed first."""

        out: list[str] = []
        if self.substantive_requirement:
            kind = self.substantive_basis_kind
            mapped = {
                BASIS_SOURCE_MARKER: MANDATORY_TYPE_STARRED,
                BASIS_EXPLICIT_WORDING: MANDATORY_TYPE_WORDING,
                BASIS_REFERENCE_PROPAGATION: MANDATORY_TYPE_REFERENCE,
                BASIS_LEGAL_RULE: MANDATORY_TYPE_LEGAL,
            }.get(kind, "")
            if mapped:
                out.append(mapped)
        elif self.marker_present:
            # ★ is visible, but the *type* has to say what the source says the
            # marker means -- a starred proof list is not a starred substantive
            # requirement.
            out.append(
                {
                    SEMANTICS_PROOF: MANDATORY_TYPE_PROOF,
                    SEMANTICS_SCORING: MANDATORY_TYPE_SCORED,
                }.get(self.marker_semantics, MANDATORY_TYPE_UNCLASSIFIED)
            )
        if self.rejection_consequence:
            out.append(MANDATORY_TYPE_REJECTION)
        return out

    @property
    def visible_marker(self) -> str:
        return VISIBLE_MARKER if self.marker_present else ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_atom_id": self.source_atom_id,
            "raw_source_marker": self.raw_source_marker,
            "marker_present": self.marker_present,
            "marker_source_location": self.marker_source_location,
            "marker_source_text": self.marker_source_text,
            "marker_evidence_id": self.marker_evidence_id,
            "marker_semantics": self.marker_semantics,
            "substantive_requirement": self.substantive_requirement,
            "substantive_basis_kind": self.substantive_basis_kind,
            "substantive_basis_atom_ids": list(self.substantive_basis_atom_ids),
            "substantive_basis_text": self.substantive_basis_text,
            "explicit_rejection_consequence": self.explicit_rejection_consequence,
            "derived_rejection_consequence": self.derived_rejection_consequence,
            "rejection_basis_atom_ids": list(self.rejection_basis_atom_ids),
            "rejection_consequence_text": self.rejection_consequence_text,
            "criticality_level": self.criticality_level,
            "criticality_reason": self.criticality_reason,
            "reference_parent_atom_id": self.reference_parent_atom_id,
            "reference_target": self.reference_target,
            "governing_clause_atom_id": self.governing_clause_atom_id,
            "mandatory_types": self.mandatory_types,
        }


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #


def _table_rows(document: Any) -> Iterable[tuple[int, int, list[Any]]]:
    for table in getattr(document, "tables", ()) or ():
        page = int(getattr(table, "page", 0) or 0)
        index = int(getattr(table, "table_index", 0) or 0)
        for row in getattr(table, "rows", ()) or ():
            yield page, index, list(getattr(row, "cells", ()) or ())


def _locator_text(locator: Any, page: int | None = None) -> str:
    """Reviewer-readable locator text for a marker's source position."""

    if isinstance(locator, str):
        if locator.startswith("locator_type"):
            block = re.search(r"block_index=(\d+)", locator)
            found = re.search(r"page=(\d+)", locator)
            number = found.group(1) if found else page
            if block and number:
                return f"第{number}页 / 块{block.group(1)}"
            if number:
                return f"第{number}页"
            return locator
        return locator
    if isinstance(locator, Mapping):
        data: Mapping[str, Any] = locator
    elif locator is not None and hasattr(locator, "model_dump"):
        data = locator.model_dump(mode="json")
    else:
        data = {}
    if data.get("page"):
        return f"第{data['page']}页"
    if page is not None:
        return f"第{page}页"
    return ""


def discover_clause_labels(
    document: Any,
) -> dict[str, dict[str, Any]]:
    """Index the document's clause-number table by clause number.

    The 条款号 column of a "前附表"-style table is the authoritative place a
    marker lives, so this index records the marker, the clause label and the
    row content for every labelled row -- marked or not.
    """

    labels: dict[str, dict[str, Any]] = {}
    last_clause: dict[tuple[int, int], str] = {}
    for page, table_index, cells in _table_rows(document):
        table_key = (page, table_index)
        texts = [str(getattr(cell, "text", "") or "").strip() for cell in cells]
        clause = ""
        marker = ""
        marker_column = -1
        for position, text in enumerate(texts):
            match = _MARKER_CELL_RE.match(text)
            if match:
                marker, clause, marker_column = match.group(1), match.group(2), position
                break
        if not clause and texts:
            plain = _PLAIN_CLAUSE_RE.match(texts[0])
            if plain:
                clause = plain.group(1)
        if not clause:
            # A row without a 条款号 continues the previous row's clause, so its
            # cells are extra content of that clause -- including its marker.
            previous = last_clause.get(table_key)
            contents = [
                text
                for text in texts
                if text and not _PLAIN_CLAUSE_RE.match(text) and not _MARKER_CELL_RE.match(text)
            ]
            if previous and contents and previous in labels:
                labels[previous]["rows"].append(
                    {"page": page, "content": " ".join(contents), "marker": "", "continuation": True}
                )
                labels[previous]["content_cells"].extend(contents)
            continue
        last_clause[table_key] = clause
        label = ""
        content = ""
        for position, text in enumerate(texts):
            if position == marker_column or _PLAIN_CLAUSE_RE.match(text) or _MARKER_CELL_RE.match(text):
                continue
            if not text:
                continue
            if not label:
                label = text
            else:
                content = f"{content} {text}".strip()
        locator = ""
        for cell in cells:
            raw_locator = getattr(cell, "locator", None)
            if raw_locator is not None:
                locator = str(
                    f"第{getattr(raw_locator, 'page', page)}页 / 表{table_index} 第"
                    f"{getattr(raw_locator, 'row_index', 0)}行"
                )
                break
        record = labels.setdefault(
            clause,
            {
                "clause": clause,
                "label": label,
                "valid": True,
                "marker": "",
                "rows": [],
                "content_cells": [],
            },
        )
        record.setdefault("content_cells", [])
        record["rows"].append({"page": page, "content": content, "marker": marker})
        record["content_cells"].extend(
            text
            for position, text in enumerate(texts)
            if text
            and position != marker_column
            and not _PLAIN_CLAUSE_RE.match(text)
            and not _MARKER_CELL_RE.match(text)
        )
        if label and not record["label"]:
            record["label"] = label
        if marker and not record["marker"]:
            record["marker"] = marker
            record["marker_locator"] = locator
            record["marker_source_text"] = " | ".join(text for text in texts if text)
            record["marker_page"] = page
    return labels


def discover_marker_evidence(
    document: Any,
    labels: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[SourceMarkerEvidence, ...]:
    """Every source-visible marker: table-cell clause labels and inline text."""

    label_index = dict(labels or discover_clause_labels(document))
    found: list[SourceMarkerEvidence] = []
    seen: set[tuple[str, str]] = set()
    counter = 0

    def add(
        raw: str,
        clause: str,
        label: str,
        page: int | None,
        locator: str,
        text: str,
        kind: str,
        scope: str,
    ) -> None:
        nonlocal counter
        key = (raw, clause) if clause else (raw, _normalize(text)[:48])
        if key in seen:
            return
        seen.add(key)
        counter += 1
        found.append(
            SourceMarkerEvidence(
                evidence_id=f"MK{counter:04d}",
                raw_marker=raw,
                normalized_marker=VISIBLE_MARKER,
                clause=clause,
                label=label,
                page=page,
                locator=locator,
                source_text=text[:400],
                source_kind=kind,
                scope=scope,
            )
        )

    # 1. clause-number table labels (the authoritative marker location)
    for clause, record in sorted(label_index.items()):
        marker = str(record.get("marker") or "")
        if not marker:
            continue
        add(
            marker,
            clause,
            str(record.get("label") or ""),
            record.get("marker_page"),
            str(record.get("marker_locator") or ""),
            str(record.get("marker_source_text") or ""),
            MARKER_SOURCE_TABLE_CELL,
            "TABLE_LABEL",
        )

    # 2. markers written inline in source text (body clauses, table cells)
    def scan(text: str, page: int | None, locator: str, kind: str) -> None:
        for line in str(text or "").split("\n"):
            match = _INLINE_LINE_RE.match(line)
            if not match:
                continue
            raw, body = match.group(1), match.group(2).strip()
            clause_match = _LEADING_MARKER_CLAUSE_RE.match(line)
            clause = clause_match.group(2) if clause_match else ""
            if clause and clause in label_index:
                # already recorded as a table label
                continue
            add(raw, clause, "", page, locator, f"{raw}{body}", kind, "BODY_TEXT")

    for page in getattr(document, "pages", ()) or ():
        number = int(getattr(page, "page_number", 0) or 0)
        for block in getattr(page, "blocks", ()) or ():
            locator_obj = getattr(block, "locator", None)
            locator = f"第{number}页 / 块{getattr(block, 'block_index', 0)}"
            if locator_obj is None:
                locator = f"第{number}页"
            scan(str(getattr(block, "text", "") or ""), number, locator, MARKER_SOURCE_INLINE)
    for page, table_index, cells in _table_rows(document):
        for cell in cells:
            text = str(getattr(cell, "text", "") or "")
            if not _INLINE_LINE_RE.match(text.strip()):
                continue
            locator_obj = getattr(cell, "locator", None)
            locator = f"第{page}页 / 表{table_index} 第{getattr(locator_obj, 'row_index', 0)}行"
            scan(text, page, locator, MARKER_SOURCE_TABLE_CELL)
    return tuple(found)


def _governing_windows(
    atoms: Sequence[Any],
    document: Any | None = None,
) -> list[tuple[str, int | None, str, str]]:
    """Text windows that may contain a governing substantive definition.

    A governing clause is frequently emitted as several PDF blocks or several
    clause fragments ("……实质性要求和条件" / "本表格中带“*”条款；" / "……等文字
    规定的条款；" / "法律、法规、规章的相关规定。"), so the window is the head
    plus its continuation until the next numbered clause.  Both the atom stream
    and the raw blocks are mined, because the fragment splitter may drop a pure
    enumeration piece from the requirement index.
    """

    windows: list[tuple[str, int | None, str, str]] = []
    # 1. document blocks (the authoritative full wording)
    for page in getattr(document, "pages", ()) or ():
        number = int(getattr(page, "page_number", 0) or 0)
        blocks = list(getattr(page, "blocks", ()) or ())
        for position, block in enumerate(blocks):
            text = str(getattr(block, "text", "") or "")
            if not _GOVERNING_HEAD_RE.search(text):
                continue
            joined = [text]
            for follow in blocks[position + 1 :]:
                follow_text = str(getattr(follow, "text", "") or "")
                if not follow_text.strip():
                    continue
                if re.match(rf"^\s*{_CLAUSE_NUMBER}\s", follow_text):
                    break
                joined.append(follow_text)
                if follow_text.rstrip().endswith("。"):
                    break
            windows.append(
                (
                    " ".join(joined),
                    number,
                    f"第{number}页 / 块{getattr(block, 'block_index', position)}",
                    "DOCUMENT_BLOCK",
                )
            )
    # 2. atom stream (locates the governing atom id for the chain)
    for position, atom in enumerate(atoms):
        text = str(getattr(atom, "source_text", "") or "")
        if not _GOVERNING_HEAD_RE.search(text):
            continue
        joined = [text]
        for follow in atoms[position + 1 :]:
            follow_text = str(getattr(follow, "source_text", "") or "")
            if not follow_text.strip():
                continue
            if re.match(rf"^[{MARKER_CLASS}]?\s*{_CLAUSE_NUMBER}\s", follow_text.strip()):
                break
            joined.append(follow_text)
            if follow_text.rstrip().endswith("。"):
                break
        windows.append(
            (
                " ".join(joined),
                getattr(atom, "source_page", None),
                str(getattr(atom, "source_locator", "") or ""),
                "ATOM_STREAM",
            )
        )
    return windows


def discover_marker_semantics(
    atoms: Sequence[Any],
    *,
    document: Any | None = None,
) -> dict[str, dict[str, Any]]:
    """What the document itself says its emphasis markers mean.

    A marker character is only semantic data when the source states its meaning
    ("本表格中带“*”条款" under 实质性要求和条件, "标注“★”的要求，须提供证明
    材料").  The statement may live anywhere in the document, so every block and
    every atom is scanned for a co-occurrence of the marker character and one of
    the semantics terms.
    """

    out: dict[str, dict[str, Any]] = {}
    windows = list(_governing_windows(atoms, document))
    for page in getattr(document, "pages", ()) or ():
        number = int(getattr(page, "page_number", 0) or 0)
        for block in getattr(page, "blocks", ()) or ():
            text = str(getattr(block, "text", "") or "").strip()
            if not text or not any(char in text for char in MARKER_CHARS):
                continue
            windows.append(
                (
                    text,
                    number,
                    f"第{number}页 / 块{getattr(block, 'block_index', 0)}",
                    "DOCUMENT_BLOCK",
                )
            )
    for atom in atoms:
        text = str(getattr(atom, "source_text", "") or "").strip()
        if not text or not any(char in text for char in MARKER_CHARS):
            continue
        windows.append(
            (
                text,
                getattr(atom, "source_page", None),
                _locator_text(
                    getattr(atom, "source_locator", None),
                    getattr(atom, "source_page", None),
                ),
                "ATOM_STREAM",
            )
        )
    for text, page, locator, _source in windows:
        flat = _normalize(text)
        for char in MARKER_CHARS:
            if char not in flat:
                continue
            found = [
                semantics
                for semantics, terms in SEMANTICS_TERMS
                if any(term in flat for term in terms)
            ]
            if not found:
                continue
            record = out.setdefault(
                char,
                {"markers": char, "semantics": (), "evidence": []},
            )
            record["semantics"] = tuple(
                dict.fromkeys((*record["semantics"], *found))
            )
            record["evidence"].append(
                {
                    "page": page,
                    "locator": locator,
                    "text": text[:400],
                    "semantics": list(found),
                }
            )
    for char, record in out.items():
        ordered = [
            semantics
            for semantics in SEMANTICS_PRIORITY
            if semantics in record["semantics"]
        ]
        record["semantics"] = tuple(ordered)
        record["primary"] = ordered[0] if ordered else SEMANTICS_UNESTABLISHED
    return out


def _primary_semantics(semantics: Sequence[str]) -> str:
    for candidate in SEMANTICS_PRIORITY:
        if candidate in semantics:
            return candidate
    return SEMANTICS_UNESTABLISHED


def discover_substantive_rules(
    atoms: Sequence[Any],
    *,
    document: Any | None = None,
) -> tuple[SubstantiveRule, ...]:
    """Governing clauses that *define* substantive requirements."""

    semantics_index = discover_marker_semantics(atoms, document=document)
    rules: list[SubstantiveRule] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    counter = 0
    for text, page, locator, _source in _governing_windows(atoms, document):
        head = _GOVERNING_HEAD_RE.search(text)
        if not head:
            continue
        markers = tuple(dict.fromkeys(_QUOTED_MARKER_CLAUSE_RE.findall(text)))
        quoted = [token.strip() for token in _QUOTED_TOKEN_RE.findall(text)]
        words = tuple(
            token
            for token in dict.fromkeys(quoted)
            if token and not any(char in token for char in MARKER_CHARS)
        )
        legal = bool(_LEGAL_RULE_RE.search(text))
        if not markers and len(words) < 2 and not legal:
            continue
        governing_atom_id = ""
        for atom in atoms:
            if _GOVERNING_HEAD_RE.search(str(getattr(atom, "source_text", "") or "")):
                governing_atom_id = str(getattr(atom, "atom_id", "") or "")
                break
        clause = ""
        for atom in atoms:
            if governing_atom_id and str(getattr(atom, "atom_id", "") or "") == governing_atom_id:
                clause = str(getattr(atom, "source_clause_id", "") or "")
                break
        scope = "TABLE" if _TABLE_SCOPE_RE.search(text) else "DOCUMENT"
        semantics = _primary_semantics(
            tuple(
                semantics
                for char in markers
                for semantics in semantics_index.get(char, {}).get("semantics", ())
            )
        )
        for kind, kind_markers, kind_words in (
            (BASIS_SOURCE_MARKER, markers, ()),
            (BASIS_EXPLICIT_WORDING, (), words),
            (BASIS_LEGAL_RULE, (), () if legal else ()),
        ):
            if kind == BASIS_SOURCE_MARKER and not kind_markers:
                continue
            if kind == BASIS_EXPLICIT_WORDING and not kind_words:
                continue
            if kind == BASIS_LEGAL_RULE and not legal:
                continue
            key = (kind, tuple(kind_markers) or tuple(kind_words))
            if key in seen:
                continue
            seen.add(key)
            counter += 1
            rules.append(
                SubstantiveRule(
                    rule_id=f"GR{counter:04d}",
                    kind=kind,
                    markers=kind_markers,
                    words=kind_words,
                    scope=scope,
                    governing_atom_id=governing_atom_id,
                    governing_clause=clause,
                    governing_text=text[:600],
                    page=page,
                    locator=locator,
                    semantics=(
                        semantics if kind == BASIS_SOURCE_MARKER else SEMANTICS_UNESTABLISHED
                    ),
                    semantics_all=tuple(
                        dict.fromkeys(
                            semantics
                            for char in kind_markers
                            for semantics in semantics_index.get(char, {}).get(
                                "semantics", ()
                            )
                        )
                    ),
                )
            )
    # A marker whose meaning the document states *outside* a governing heading
    # (CASE002: "标注“★”的要求，须提供证明材料") still gets its own rule, so the
    # marker is never interpreted without its source statement.
    for char, record in semantics_index.items():
        if not record["semantics"]:
            continue
        if any(char in rule.markers for rule in rules):
            continue
        evidence = record["evidence"][0]
        counter += 1
        rules.append(
            SubstantiveRule(
                rule_id=f"GR{counter:04d}",
                kind=BASIS_SOURCE_MARKER,
                markers=(char,),
                words=(),
                scope="DOCUMENT",
                governing_atom_id="",
                governing_clause="",
                governing_text=evidence["text"],
                page=evidence["page"],
                locator=evidence["locator"],
                semantics=record["primary"],
                semantics_all=tuple(record["semantics"]),
            )
        )
    return tuple(rules)


def discover_rejection_rules(
    atoms: Sequence[Any],
    *,
    labels: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[RejectionRule, ...]:
    """Consequence clauses: what the document says happens on non-compliance.

    Three source shapes are recognised, all of them read from the document:

    * a clause-specific consequence (``…不按本章第3.4.1项要求…否决其响应`` or a
      consequence whose text names a labelled clause such as 最高限价);
    * a rejection enumeration whose ground is "不符合…实质性要求" -- the ground
      is usually emitted as its own list item, so list items inherit the head
      clause's consequence;
    * a general rejection clause (recorded, never linked to a requirement).
    """

    label_index = dict(labels or {})
    rules: list[RejectionRule] = []
    counter = 0

    def consequence_of(text: str) -> str:
        match = _REJECTION_CUE_RE.search(text)
        return match.group(0) if match else ""

    def record(
        *,
        consequence: str,
        trigger: str,
        atom: Any,
        targets: Sequence[str] = (),
    ) -> None:
        nonlocal counter
        counter += 1
        rules.append(
            RejectionRule(
                rule_id=f"RJ{counter:04d}",
                consequence=consequence,
                trigger=trigger,
                governing_atom_id=str(getattr(atom, "atom_id", "") or ""),
                governing_clause=str(getattr(atom, "source_clause_id", "") or ""),
                governing_text=str(getattr(atom, "source_text", "") or "")[:400],
                page=getattr(atom, "source_page", None),
                locator=_locator_text(
                    getattr(atom, "source_locator", None),
                    getattr(atom, "source_page", None),
                ),
                target_clauses=tuple(dict.fromkeys(targets)),
            )
        )

    heads: list[int] = []
    for position, atom in enumerate(atoms):
        text = str(getattr(atom, "source_text", "") or "")
        cue = _REJECTION_CUE_RE.search(text)
        if not cue:
            continue
        if _REJECTION_LIST_HEAD_RE.search(text):
            heads.append(position)
            continue
        targets: list[str] = []
        for match in _CLAUSE_REFERENCE_RE.finditer(text):
            targets.append(match.group(1))
        flat = _normalize(text)
        for labelled, label_record in label_index.items():
            label = str(label_record.get("label") or "")
            if not label or len(_normalize(label)) < 2:
                continue
            if _normalize(label) in flat:
                targets.append(labelled)
        record(
            consequence=cue.group(0),
            trigger=(
                REJECTION_TRIGGER_SPECIFIC_CLAUSE
                if targets
                else REJECTION_TRIGGER_GENERAL
            ),
            atom=atom,
            targets=targets,
        )

    # list items of a rejection enumeration inherit their head's consequence
    for head_index in heads:
        head = atoms[head_index]
        head_text = str(getattr(head, "source_text", "") or "")
        consequence = consequence_of(head_text) or "否决"
        found_ground = False
        for position in range(head_index + 1, len(atoms)):
            text = str(getattr(atoms[position], "source_text", "") or "")
            if not _LIST_ITEM_RE.match(text.strip()):
                break
            if not _SUBSTANTIVE_FAIL_RE.search(text):
                continue
            record(
                consequence=consequence,
                trigger=REJECTION_TRIGGER_SUBSTANTIVE,
                atom=head,
            )
            found_ground = True
            break
        if not found_ground and _SUBSTANTIVE_FAIL_RE.search(head_text):
            record(
                consequence=consequence,
                trigger=REJECTION_TRIGGER_SUBSTANTIVE,
                atom=head,
            )
    return tuple(rules)


# --------------------------------------------------------------------------- #
# reference propagation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ReferenceLink:
    """A starred parent clause that hands its substantiveness to a section."""

    parent_atom_id: str
    parent_clause: str
    marker: str
    target: str
    target_atom_ids: tuple[str, ...]
    target_kind: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "parent_atom_id": self.parent_atom_id,
            "parent_clause": self.parent_clause,
            "marker": self.marker,
            "target": self.target,
            "target_atom_ids": list(self.target_atom_ids),
            "target_kind": self.target_kind,
        }


_SELF_TABLE_REFERENCE_RE = re.compile(r"(前附表|本表|上表|下表|本表格)")


def _sentence_containing(text: str, start: int, end: int) -> str:
    left = max((text.rfind(char, 0, start) for char in "。；;\n"), default=-1)
    right_candidates = [text.find(char, end) for char in "。；;\n"]
    right = min([value for value in right_candidates if value >= 0], default=len(text))
    return text[left + 1 : right]


def _is_primary_reference(text: str, match: re.Match[str]) -> bool:
    """True when the sentence *is* the reference, not an incidental pointer.

    ``*1.5.1 供应商资格能力和条件 见询比公告“第二款 供应商资格要求”`` and
    ``*1.4.1 采购内容 一体化泵站（详见询比文件“第五章 采购需求”）`` make the
    referenced section the requirement itself, so the reference carries the
    marker's substantiveness.  ``*3.4.1 …应按…第六章“响应文件格式”规定的响应
    保证金格式递交…`` merely points at where a format lives; propagating the
    whole referenced chapter there would be an invented claim, so it is not a
    primary reference.
    """

    sentence = _sentence_containing(text, match.start(), match.end())
    residual = sentence.replace(match.group(0), "")
    residual = re.sub(r"[\s\u3000（）()【】]", "", residual)
    return len(residual) <= 24


def _reference_targets(text: str) -> list[str]:
    targets: list[str] = []
    for match in _REFERENCE_RE.finditer(text):
        if _SELF_TABLE_REFERENCE_RE.search(match.group(0)):
            continue
        if not _is_primary_reference(text, match):
            continue
        targets.append(match.group(1).strip())
    for match in _REFERENCE_TAIL_RE.finditer(text):
        if _SELF_TABLE_REFERENCE_RE.search(match.group(0)):
            continue
        targets.append(match.group(1).strip())
    cleaned: list[str] = []
    for target in targets:
        value = _normalize(target)
        if len(value) < 2:
            continue
        cleaned.append(value)
    return list(dict.fromkeys(cleaned))


def _target_section_tokens(target: str) -> list[str]:
    """Candidate section names a reference may name (generic, no literals)."""

    tokens = [target]
    stripped = re.sub(r"^第[一二三四五六七八九十百]+[章条款]", "", target)
    stripped = re.sub(r"^[一二三四五六七八九十]+[、.．]", "", stripped)
    if stripped and stripped != target:
        tokens.append(stripped)
    return [token for token in dict.fromkeys(tokens) if len(token) >= 2]


def discover_chapters(document: Any) -> tuple[dict[str, Any], ...]:
    """Chapter-level source structure, so "第五章 采购需求" can be resolved."""

    chapters: list[dict[str, Any]] = []
    # A heading is a *short* block that is nothing but "第X章 <title>".  Body
    # sentences that merely start by naming a chapter (round-6 CASE001: "第六章
    # “响应文件格式”规定的响应保证金格式递交响应保证金，并作为其响应文件的…")
    # must not create a chapter, because the chapter is what scopes clause
    # numbers.
    pattern = re.compile(r"第\s*([一二三四五六七八九十百]+)\s*章\s*(.{0,26})")
    for page in getattr(document, "pages", ()) or ():
        number = int(getattr(page, "page_number", 0) or 0)
        for block in getattr(page, "blocks", ()) or ():
            text = str(getattr(block, "text", "") or "").strip()
            if not text:
                continue
            # a table of contents line is navigation, not the chapter body
            if "...." in text or "……" in text:
                continue
            condensed = re.sub(r"\s+", "", text)
            match = pattern.fullmatch(condensed)
            if not match:
                continue
            if any(char in match.group(2) for char in "，。；,;：:"):
                continue
            chapters.append(
                {
                    "number": match.group(1),
                    "title": _normalize(text)[:60],
                    "page": number,
                    "locator": f"第{number}页 / 块{getattr(block, 'block_index', 0)}",
                    "raw": text[:120],
                }
            )
    return tuple(chapters)


def _chapter_children(
    target: str,
    chapters: Sequence[Mapping[str, Any]],
    atoms: Sequence[Any],
    *,
    parent_atom_id: str,
) -> tuple[list[str], str]:
    """Atoms of the chapter a reference names, page-range based."""

    number_match = re.search(r"第\s*([一二三四五六七八九十百]+)\s*章", target)
    if not number_match:
        return [], ""
    wanted = number_match.group(1)
    matched: list[Mapping[str, Any]] = [
        chapter for chapter in chapters if chapter.get("number") == wanted
    ]
    if not matched:
        return [], ""
    chapter = matched[0]
    ordered = sorted(chapters, key=lambda item: int(item.get("page") or 0))
    later = [
        item
        for item in ordered
        if int(item.get("page") or 0) > int(chapter.get("page") or 0)
    ]
    end_page = int(later[0].get("page") or 0) if later else 10**6
    children: list[str] = []
    for atom in atoms:
        atom_id = str(getattr(atom, "atom_id", "") or "")
        if atom_id == parent_atom_id:
            continue
        page = getattr(atom, "source_page", None)
        if page is None:
            continue
        if int(chapter.get("page") or 0) <= int(page) < end_page:
            children.append(atom_id)
    return children, str(chapter.get("locator") or "")


_SECTION_HEADING_RE = re.compile(
    r"^\s*(?:[一二三四五六七八九十百]+[、.．]|第[一二三四五六七八九十百]+[章款节])"
)


def _section_range_children(
    hit_id: str,
    atoms: Sequence[Any],
) -> list[str]:
    """Atoms of the section a reference resolved to, up to the next heading.

    The requirement index stores a section name on the first clause of a
    section only, so a name match alone would propagate to a single atom.  The
    section therefore extends forward while the source keeps producing clauses
    of the same section, and stops at the next 中文-numbered heading.
    """

    position = next(
        (
            index
            for index, atom in enumerate(atoms)
            if str(getattr(atom, "atom_id", "") or "") == hit_id
        ),
        -1,
    )
    if position < 0:
        return []
    children: list[str] = []
    for atom in atoms[position + 1 :]:
        text = str(getattr(atom, "source_text", "") or "").strip()
        if _SECTION_HEADING_RE.match(text) or re.match(r"^\s*第\s*\d+\s*章", text):
            break
        children.append(str(getattr(atom, "atom_id", "") or ""))
    return children


def discover_reference_links(
    atoms: Sequence[Any],
    *,
    marker_by_atom: Mapping[str, str],
    markers: Sequence[SourceMarkerEvidence] = (),
    labels: Mapping[str, Mapping[str, Any]] | None = None,
    chapters: Sequence[Mapping[str, Any]] = (),
) -> tuple[ReferenceLink, ...]:
    """Propagate a starred parent's criticality to the section it references.

    The parent may be an atom (its own text carries the reference) or a marked
    table row whose *content* carries it (``*1.5.1 … 见询比公告“第二款 供应商
    资格要求”``), because the requirement index may drop a pure cross-reference
    cell.  The chain that is persisted is always
    ``child atom -> referenced section -> starred parent``.
    """

    marker_by_clause: dict[str, str] = {}
    for evidence in markers:
        if evidence.clause:
            marker_by_clause.setdefault(evidence.clause, evidence.raw_marker)
    atom_by_clause: dict[str, str] = {}
    for atom in atoms:
        for token in _atom_clause_tokens(atom):
            atom_by_clause.setdefault(token, str(getattr(atom, "atom_id", "") or ""))
        if marker_by_atom.get(str(getattr(atom, "atom_id", "") or "")):
            for token in _atom_clause_tokens(atom):
                atom_by_clause.setdefault(token, str(getattr(atom, "atom_id", "") or ""))

    sources: list[tuple[str, str, str, str, str]] = []
    for atom in atoms:
        atom_id = str(getattr(atom, "atom_id", "") or "")
        marker = marker_by_atom.get(atom_id, "")
        if not marker:
            continue
        sources.append(
            (
                atom_id,
                marker,
                str(getattr(atom, "source_text", "") or ""),
                "ATOM",
                str(getattr(atom, "source_clause_id", "") or ""),
            )
        )
    known_parents = {source[0] for source in sources}
    for evidence in markers:
        if not evidence.clause or not evidence.raw_marker:
            continue
        parent = atom_by_clause.get(evidence.clause, "")
        # A marked table row may carry the reference where the indexed atom only
        # carries the cross-reference to the 前附表, so both are mined.
        sources.append(
            (
                parent,
                evidence.raw_marker,
                evidence.source_text,
                "MARKER_ROW",
                evidence.clause,
            )
        )

    links: list[ReferenceLink] = []
    seen: set[tuple[str, str]] = set()
    for parent_atom_id, marker, text, source_kind, parent_clause in sources:
        for target in _reference_targets(text):
            tokens = _target_section_tokens(target)
            children: list[str] = []
            target_kind = "UNRESOLVED_REFERENCE"
            hits: list[str] = []
            for atom in atoms:
                other_id = str(getattr(atom, "atom_id", "") or "")
                if other_id == parent_atom_id:
                    continue
                section = _normalize(getattr(atom, "source_section", "") or "")
                body = _normalize(getattr(atom, "source_text", "") or "")
                if any(token and (token in section or token in body) for token in tokens):
                    hits.append(other_id)
            if hits:
                children = list(hits)
                target_kind = "SECTION_MATCH"
                for hit in hits:
                    for child in _section_range_children(hit, atoms):
                        if child and child != parent_atom_id and child not in children:
                            children.append(child)
            else:
                chapter_children, _locator = _chapter_children(
                    target,
                    chapters,
                    atoms,
                    parent_atom_id=parent_atom_id,
                )
                if chapter_children:
                    children = chapter_children
                    target_kind = "CHAPTER_MATCH"
            key = (parent_atom_id, target)
            if key in seen:
                continue
            seen.add(key)
            links.append(
                ReferenceLink(
                    parent_atom_id=parent_atom_id,
                    parent_clause=parent_clause,
                    marker=marker,
                    target=target,
                    target_atom_ids=tuple(children),
                    target_kind=target_kind,
                )
            )
    return tuple(links)


# --------------------------------------------------------------------------- #
# index
# --------------------------------------------------------------------------- #


@dataclass
class CriticalityIndex:
    """The document's criticality model, queried per atom / per concern."""

    labels: dict[str, dict[str, Any]] = field(default_factory=dict)
    markers: tuple[SourceMarkerEvidence, ...] = ()
    substantive_rules: tuple[SubstantiveRule, ...] = ()
    rejection_rules: tuple[RejectionRule, ...] = ()
    reference_links: tuple[ReferenceLink, ...] = ()
    criticalities: dict[str, SourceRequirementCriticality] = field(default_factory=dict)
    atom_text: dict[str, str] = field(default_factory=dict)

    # -- queries ---------------------------------------------------------- #

    @property
    def marker_by_clause(self) -> dict[str, SourceMarkerEvidence]:
        out: dict[str, SourceMarkerEvidence] = {}
        for evidence in self.markers:
            if evidence.clause and evidence.clause not in out:
                out[evidence.clause] = evidence
        return out

    @property
    def general_rejection_rules(self) -> tuple[RejectionRule, ...]:
        return tuple(
            rule
            for rule in self.rejection_rules
            if rule.trigger == REJECTION_TRIGGER_SUBSTANTIVE
        )

    @property
    def explicit_rejection_rules(self) -> tuple[RejectionRule, ...]:
        return tuple(
            rule
            for rule in self.rejection_rules
            if rule.trigger == REJECTION_TRIGGER_SPECIFIC_CLAUSE
        )

    def for_atom(self, atom: Any) -> SourceRequirementCriticality:
        atom_id = str(getattr(atom, "atom_id", "") or "")
        return self.criticalities.get(atom_id) or SourceRequirementCriticality(
            source_atom_id=atom_id
        )

    def for_atoms(self, atoms: Sequence[Any]) -> SourceRequirementCriticality:
        """Aggregate owned atoms: keep the strongest source-backed status."""

        records = [self.for_atom(atom) for atom in atoms]
        records = [record for record in records if record.source_atom_id]
        if not records:
            return SourceRequirementCriticality(source_atom_id="")
        strength = {
            BASIS_SOURCE_MARKER: 0,
            BASIS_EXPLICIT_WORDING: 1,
            BASIS_LEGAL_RULE: 2,
            BASIS_REFERENCE_PROPAGATION: 3,
            BASIS_OTHER: 4,
            "": 5,
        }
        ordered = sorted(
            records,
            key=lambda record: (
                0 if record.marker_present else 1,
                strength.get(record.substantive_basis_kind, 5),
            ),
        )
        marked = [record for record in ordered if record.marker_present]
        substantive = [record for record in ordered if record.substantive_requirement]
        explicit = [record for record in ordered if record.explicit_rejection_consequence]
        derived = [record for record in ordered if record.derived_rejection_consequence]
        basis_atoms: list[str] = []
        basis_texts: list[str] = []
        basis_kinds: list[str] = []
        for record in substantive:
            basis_atoms.extend(record.substantive_basis_atom_ids)
            if record.substantive_basis_text:
                basis_texts.append(record.substantive_basis_text)
            if record.substantive_basis_kind and record.substantive_basis_kind not in basis_kinds:
                basis_kinds.append(record.substantive_basis_kind)
        basis_kind = basis_kinds[0] if basis_kinds else ""
        rejection_atoms: list[str] = []
        rejection_texts: list[str] = []
        for record in [*explicit, *derived]:
            rejection_atoms.extend(record.rejection_basis_atom_ids)
            if record.rejection_consequence_text:
                rejection_texts.append(record.rejection_consequence_text)
        primary = marked[0] if marked else records[0]
        parent = next(
            (record.reference_parent_atom_id for record in records if record.reference_parent_atom_id),
            "",
        )
        reference_target = next(
            (record.reference_target for record in records if record.reference_target), ""
        )
        governing = next(
            (record.governing_clause_atom_id for record in records if record.governing_clause_atom_id),
            "",
        )
        semantics = next(
            (
                record.marker_semantics
                for record in ordered
                if record.marker_present
                and record.marker_semantics != SEMANTICS_UNESTABLISHED
            ),
            SEMANTICS_UNESTABLISHED,
        )
        if explicit:
            level = CRITICALITY_SUBSTANTIVE_REJECTION
        elif substantive:
            level = CRITICALITY_SUBSTANTIVE
        elif marked and semantics in (SEMANTICS_PROOF, SEMANTICS_SCORING):
            level = CRITICALITY_MANDATORY
        else:
            level = CRITICALITY_ORDINARY
        reason_parts: list[str] = []
        if marked:
            reason_parts.append(
                f"源标记 {primary.raw_source_marker}（{primary.marker_source_location}）"
            )
            reason_parts.append(f"标记含义={semantics}")
        if substantive:
            reason_parts.append(f"实质性要求依据={basis_kind or BASIS_OTHER}")
        if explicit:
            reason_parts.append("明示否决后果")
        elif derived:
            reason_parts.append("推导否决后果（实质性要求不满足）")
        return SourceRequirementCriticality(
            source_atom_id=primary.source_atom_id,
            raw_source_marker=primary.raw_source_marker if marked else "",
            marker_present=bool(marked),
            marker_source_location=primary.marker_source_location if marked else "",
            marker_source_text=primary.marker_source_text if marked else "",
            marker_evidence_id=primary.marker_evidence_id if marked else "",
            marker_semantics=semantics,
            substantive_requirement=True if substantive else (False if records else None),
            substantive_basis_kind=basis_kind,
            substantive_basis_atom_ids=tuple(dict.fromkeys(basis_atoms)),
            substantive_basis_text=" ".join(dict.fromkeys(basis_texts))[:400],
            explicit_rejection_consequence=bool(explicit),
            derived_rejection_consequence=bool(derived) and not explicit,
            rejection_basis_atom_ids=tuple(dict.fromkeys(rejection_atoms)),
            rejection_consequence_text=" ".join(dict.fromkeys(rejection_texts))[:400],
            criticality_level=level,
            criticality_reason="；".join(reason_parts),
            reference_parent_atom_id=parent,
            reference_target=reference_target,
            governing_clause_atom_id=governing,
        )

    # -- evidence --------------------------------------------------------- #

    def as_dict(self) -> dict[str, Any]:
        counts: dict[str, int] = {
            "marker_count": len(self.markers),
            "substantive_rule_count": len(self.substantive_rules),
            "rejection_rule_count": len(self.rejection_rules),
            "reference_link_count": len(self.reference_links),
            "classified_atom_count": len(self.criticalities),
        }
        for level in (
            CRITICALITY_ORDINARY,
            CRITICALITY_SUBSTANTIVE,
            CRITICALITY_SUBSTANTIVE_REJECTION,
            CRITICALITY_MANDATORY,
        ):
            counts[f"atom_level_{level.lower()}_count"] = sum(
                1 for record in self.criticalities.values() if record.criticality_level == level
            )
        counts["marker_atom_count"] = sum(
            1 for record in self.criticalities.values() if record.marker_present
        )
        counts["substantive_atom_count"] = sum(
            1 for record in self.criticalities.values() if record.substantive_requirement
        )
        counts["rejection_atom_count"] = sum(
            1 for record in self.criticalities.values() if record.rejection_consequence
        )
        return {
            "schema": SCHEMA,
            "counts": counts,
            "markers": [evidence.as_dict() for evidence in self.markers],
            "substantive_rules": [rule.as_dict() for rule in self.substantive_rules],
            "rejection_rules": [rule.as_dict() for rule in self.rejection_rules],
            "reference_links": [link.as_dict() for link in self.reference_links],
            "clause_labels": {
                clause: {
                    "label": record.get("label", ""),
                    "marker": record.get("marker", ""),
                }
                for clause, record in sorted(self.labels.items())
            },
        }


def _atom_clause_tokens(atom: Any) -> list[str]:
    """Clause numbers an atom can be about, most specific first."""

    tokens: list[str] = []
    text = str(getattr(atom, "source_text", "") or "").lstrip()
    match = re.match(rf"[{MARKER_CLASS}]?\s*({_CLAUSE_NUMBER})", text)
    if match:
        tokens.append(match.group(1))
    for reference in _CLAUSE_REFERENCE_RE.finditer(str(getattr(atom, "source_text", "") or "")):
        tokens.append(reference.group(1))
    return list(dict.fromkeys(tokens))


def _label_head_pattern(label: str) -> re.Pattern[str]:
    """A clause that *is* the labelled requirement, not one that mentions it.

    ``5、最高限价：3100000 元`` and ``响应保证金的形式：银行转账方式`` state the
    labelled requirement itself, so they inherit the marked clause's marker.
    ``3.2.2 …项目最高限价自主进行报价`` merely mentions the label and does not.
    """

    return re.compile(
        rf"^\s*(?:[（(]?\s*\d[\d.、]*\s*[、.．)）]?\s*)?{re.escape(_normalize(label))}\s*[：:]"
    )


def _chapter_spans(chapters: Sequence[Mapping[str, Any]]) -> list[tuple[int, int, str]]:
    """(start_page, end_page, chapter_key) for each discovered chapter."""

    ordered = sorted(chapters, key=lambda item: int(item.get("page") or 0))
    spans: list[tuple[int, int, str]] = []
    for position, chapter in enumerate(ordered):
        start = int(chapter.get("page") or 0)
        later = [int(item.get("page") or 0) for item in ordered[position + 1 :]]
        end = later[0] if later else 10**6
        key = str(chapter.get("number") or chapter.get("title") or "")
        spans.append((start, end, key))
    return spans


def _chapter_of(spans: Sequence[tuple[int, int, str]], page: Any) -> str:
    if page is None:
        return ""
    try:
        number = int(page)
    except (TypeError, ValueError):
        return ""
    for start, end, key in spans:
        if start <= number < end:
            return key
    return ""


def _marker_for_atom(
    atom: Any,
    *,
    labels: Mapping[str, Mapping[str, Any]],
    marker_by_clause: Mapping[str, SourceMarkerEvidence],
    marker_chapter: Mapping[str, str] | None = None,
    chapter_spans: Sequence[tuple[int, int, str]] = (),
) -> SourceMarkerEvidence | None:
    """Attach a source marker only when the atom *is* the marked clause."""

    text = str(getattr(atom, "source_text", "") or "")
    leading = _LEADING_MARKER_RE.match(text)
    if leading:
        raw = leading.group(1)
        clause_match = _LEADING_MARKER_CLAUSE_RE.match(text)
        clause = clause_match.group(2) if clause_match else ""
        known = marker_by_clause.get(clause)
        if known is not None and known.raw_marker == raw:
            return known
        return SourceMarkerEvidence(
            evidence_id=f"MK-INLINE-{clause or _normalize(text)[:12]}",
            raw_marker=raw,
            normalized_marker=VISIBLE_MARKER,
            clause=clause,
            label="",
            page=getattr(atom, "source_page", None),
            locator=_locator_text(
                getattr(atom, "source_locator", None),
                getattr(atom, "source_page", None),
            ),
            source_text=text[:400],
            source_kind=MARKER_SOURCE_INLINE,
            scope="BODY_TEXT",
        )
    atom_chapter = _chapter_of(chapter_spans, getattr(atom, "source_page", None))
    for token in _atom_clause_tokens(atom):
        clause = token if token in labels else ""
        if clause and clause in marker_by_clause:
            # A clause number is only unique *inside* its chapter: the 前附表's
            # 3.4.1 (响应保证金) must not mark the 评审办法 chapter's own 3.4.1.
            marker_chapter_key = (marker_chapter or {}).get(clause, "")
            if atom_chapter and marker_chapter_key and atom_chapter != marker_chapter_key:
                continue
            return marker_by_clause[clause]
    # A marked clause row may be quoted by a different source table (a 报价表
    # restating "5、最高限价：…"), so the labelled requirement is matched by its
    # label at the head of the clause text.
    flat = _normalize(text)
    for clause, record in labels.items():
        marker = str(record.get("marker") or "")
        label = str(record.get("label") or "")
        if not marker:
            continue
        if len(_normalize(label)) >= 2 and _label_head_pattern(label).match(flat):
            evidence = marker_by_clause.get(clause)
            if evidence is not None:
                return replace(evidence, scope="TABLE_LABEL_INHERITED")
        # …or by reproducing one of the marked row's own content cells (the row
        # and its continuation rows), which is what makes a restated requirement
        # the same source requirement.
        for cell_text in record.get("content_cells") or ():
            for piece in str(cell_text).split("\n"):
                cell_flat = _normalize(piece)
                if len(cell_flat) < 6:
                    continue
                if flat.startswith(cell_flat) or (
                    cell_flat.startswith(flat) and len(flat) >= 6
                ):
                    evidence = marker_by_clause.get(clause)
                    if evidence is not None:
                        return replace(evidence, scope="TABLE_ROW_CONTENT")
    return None


def build_criticality_index(
    document: Any,
    atoms: Sequence[Any],
    *,
    labels: Mapping[str, Mapping[str, Any]] | None = None,
) -> CriticalityIndex:
    """Build the document-wide source-criticality model."""

    label_index = dict(labels or discover_clause_labels(document))
    markers = discover_marker_evidence(document, label_index)
    marker_by_clause = {}
    for evidence in markers:
        if evidence.clause and evidence.clause not in marker_by_clause:
            marker_by_clause[evidence.clause] = evidence
    substantive_rules = discover_substantive_rules(atoms, document=document)
    rejection_rules = discover_rejection_rules(atoms, labels=label_index)
    chapters = discover_chapters(document)
    chapter_spans = _chapter_spans(chapters)
    marker_chapter = {
        clause: _chapter_of(chapter_spans, evidence.page)
        for clause, evidence in marker_by_clause.items()
    }

    marker_rules = [rule for rule in substantive_rules if rule.kind == BASIS_SOURCE_MARKER]
    wording_rules = [rule for rule in substantive_rules if rule.kind == BASIS_EXPLICIT_WORDING]
    legal_rules = [rule for rule in substantive_rules if rule.kind == BASIS_LEGAL_RULE]
    marker_vocabulary = {
        marker for rule in marker_rules for marker in rule.markers
    } or set(MARKER_CHARS)
    wording_vocabulary = tuple(
        dict.fromkeys(word for rule in wording_rules for word in rule.words)
    )

    # per-atom marker evidence first: reference propagation depends on it
    marker_by_atom: dict[str, str] = {}
    for atom in atoms:
        atom_id = str(getattr(atom, "atom_id", "") or "")
        evidence = _marker_for_atom(
            atom,
            labels=label_index,
            marker_by_clause=marker_by_clause,
            marker_chapter=marker_chapter,
            chapter_spans=chapter_spans,
        )
        if evidence is not None:
            marker_by_atom[atom_id] = evidence.raw_marker
    reference_links = discover_reference_links(
        atoms,
        marker_by_atom=marker_by_atom,
        markers=markers,
        labels=label_index,
        chapters=chapters,
    )
    propagated: dict[str, ReferenceLink] = {}
    for link in reference_links:
        for child in link.target_atom_ids:
            propagated.setdefault(child, link)

    general_rules = tuple(
        rule for rule in rejection_rules if rule.trigger == REJECTION_TRIGGER_SUBSTANTIVE
    )
    specific_rules = tuple(
        rule for rule in rejection_rules if rule.trigger == REJECTION_TRIGGER_SPECIFIC_CLAUSE
    )

    criticalities: dict[str, SourceRequirementCriticality] = {}
    atom_text: dict[str, str] = {}
    for atom in atoms:
        atom_id = str(getattr(atom, "atom_id", "") or "")
        text = str(getattr(atom, "source_text", "") or "")
        atom_text[atom_id] = text
        flat = _normalize(text)
        evidence = _marker_for_atom(
            atom,
            labels=label_index,
            marker_by_clause=marker_by_clause,
            marker_chapter=marker_chapter,
            chapter_spans=chapter_spans,
        )
        clause_tokens = set(_atom_clause_tokens(atom))

        # ---- substantive requirement ------------------------------------ #
        substantive = False
        basis_kind = ""
        basis_atom_ids: list[str] = []
        basis_text = ""
        governing_atom = ""
        marker_semantics = SEMANTICS_UNESTABLISHED
        if evidence is not None and evidence.raw_marker in marker_vocabulary:
            rule = next(
                (
                    item
                    for item in marker_rules
                    if evidence.raw_marker in item.markers
                ),
                None,
            )
            marker_semantics = (
                rule.semantics if rule is not None else SEMANTICS_UNESTABLISHED
            )
            if marker_semantics == SEMANTICS_SUBSTANTIVE:
                # The document itself says this marker marks substantive
                # requirements (CASE001 10.8 / CASE003 1.12.2).
                substantive = True
                basis_kind = BASIS_SOURCE_MARKER
                if rule is not None:
                    if rule.governing_atom_id:
                        basis_atom_ids.append(rule.governing_atom_id)
                    basis_text = rule.governing_text
                    governing_atom = rule.governing_atom_id
                if not basis_atom_ids:
                    # the marker's own atom is the evidence when the marker is
                    # the starred clause itself
                    basis_atom_ids.append(atom_id)
            # SEMANTICS_PROOF / SEMANTICS_SCORING / unestablished: the marker is
            # visible data but does *not* make the clause substantive, so no
            # rejection consequence may be derived from it either.
        if not substantive and wording_vocabulary:
            hit = next(
                (word for word in wording_vocabulary if word and word in flat),
                "",
            )
            if hit:
                substantive = True
                basis_kind = BASIS_EXPLICIT_WORDING
                rule = next(
                    (item for item in wording_rules if hit in item.words),
                    None,
                )
                if rule is not None:
                    basis_atom_ids.append(rule.governing_atom_id)
                    basis_text = rule.governing_text
                    governing_atom = rule.governing_atom_id
        if not substantive and legal_rules:
            for rule in legal_rules:
                if rule.governing_atom_id == atom_id:
                    substantive = True
                    basis_kind = BASIS_LEGAL_RULE
                    basis_atom_ids.append(rule.governing_atom_id)
                    basis_text = rule.governing_text
                    governing_atom = rule.governing_atom_id
                    break
        reference_parent = ""
        reference_target = ""
        if not substantive and atom_id in propagated:
            link = propagated[atom_id]
            substantive = True
            basis_kind = BASIS_REFERENCE_PROPAGATION
            reference_parent = link.parent_atom_id
            reference_target = link.target
            basis_atom_ids.append(link.parent_atom_id)

        # ---- rejection consequence -------------------------------------- #
        explicit = False
        rejection_atoms: list[str] = []
        rejection_text = ""
        if any(rule.governing_atom_id == atom_id for rule in specific_rules):
            rule = next(rule for rule in specific_rules if rule.governing_atom_id == atom_id)
            explicit = True
            rejection_atoms.append(rule.governing_atom_id)
            rejection_text = rule.governing_text
        else:
            for rule in specific_rules:
                if rule.target_clauses and clause_tokens & set(rule.target_clauses):
                    explicit = True
                    rejection_atoms.append(rule.governing_atom_id)
                    rejection_text = rule.governing_text
                    break
        derived = False
        if substantive and not explicit and general_rules:
            rule = general_rules[0]
            derived = True
            rejection_atoms.append(rule.governing_atom_id)
            rejection_text = rule.governing_text

        if explicit:
            level = CRITICALITY_SUBSTANTIVE_REJECTION
        elif substantive:
            level = CRITICALITY_SUBSTANTIVE
        elif evidence is not None and marker_semantics in (
            SEMANTICS_PROOF,
            SEMANTICS_SCORING,
        ):
            # marked, and the document says the marker means "must supply
            # materials" / "scored": a real review obligation, but neither a
            # substantive requirement nor a rejection consequence.
            level = CRITICALITY_MANDATORY
        else:
            level = CRITICALITY_ORDINARY
        reason_parts: list[str] = []
        if evidence is not None:
            reason_parts.append(
                f"源标记 {evidence.raw_marker}（{evidence.source_kind}，{evidence.locator}）"
            )
            reason_parts.append(f"标记含义={marker_semantics}")
        if substantive:
            reason_parts.append(f"实质性要求依据={basis_kind}")
        if explicit:
            reason_parts.append("明示否决后果")
        elif derived:
            reason_parts.append("推导否决后果（实质性要求不满足）")
        criticalities[atom_id] = SourceRequirementCriticality(
            source_atom_id=atom_id,
            raw_source_marker=evidence.raw_marker if evidence is not None else "",
            marker_present=evidence is not None,
            marker_source_location=evidence.locator if evidence is not None else "",
            marker_source_text=evidence.source_text if evidence is not None else "",
            marker_evidence_id=evidence.evidence_id if evidence is not None else "",
            marker_semantics=marker_semantics,
            substantive_requirement=substantive,
            substantive_basis_kind=basis_kind,
            substantive_basis_atom_ids=tuple(dict.fromkeys(basis_atom_ids)),
            substantive_basis_text=basis_text,
            explicit_rejection_consequence=explicit,
            derived_rejection_consequence=derived,
            rejection_basis_atom_ids=tuple(dict.fromkeys(rejection_atoms)),
            rejection_consequence_text=rejection_text,
            criticality_level=level,
            criticality_reason="；".join(reason_parts),
            reference_parent_atom_id=reference_parent,
            reference_target=reference_target,
            governing_clause_atom_id=governing_atom,
        )

    return CriticalityIndex(
        labels=label_index,
        markers=markers,
        substantive_rules=substantive_rules,
        rejection_rules=rejection_rules,
        reference_links=reference_links,
        criticalities=criticalities,
        atom_text=atom_text,
    )


__all__ = [
    "BASIS_EXPLICIT_WORDING",
    "BASIS_KINDS",
    "BASIS_LEGAL_RULE",
    "BASIS_OTHER",
    "BASIS_REFERENCE_PROPAGATION",
    "BASIS_SOURCE_MARKER",
    "COVERAGE_BACKGROUND_ROW",
    "COVERAGE_DELIVERED_ROW",
    "COVERAGE_REFERENCE_CHILD",
    "COVERAGE_REFERENCE_PARENT",
    "COVERAGE_UNCOVERED",
    "CRITICALITY_MANDATORY",
    "CRITICALITY_ORDINARY",
    "CRITICALITY_SUBSTANTIVE",
    "CRITICALITY_SUBSTANTIVE_REJECTION",
    "CriticalityIndex",
    "MANDATORY_TYPE_LEGAL",
    "MANDATORY_TYPE_PROOF",
    "MANDATORY_TYPE_REFERENCE",
    "MANDATORY_TYPE_REJECTION",
    "MANDATORY_TYPE_SCORED",
    "MANDATORY_TYPE_STARRED",
    "MANDATORY_TYPE_UNCLASSIFIED",
    "MANDATORY_TYPE_WORDING",
    "MARKER_CHARS",
    "MARKER_CLASS",
    "MARKER_SOURCE_INLINE",
    "MARKER_SOURCE_TABLE_CELL",
    "REJECTION_CUES",
    "REJECTION_DERIVED",
    "REJECTION_EXPLICIT",
    "REJECTION_TRIGGER_GENERAL",
    "REJECTION_TRIGGER_SPECIFIC_CLAUSE",
    "REJECTION_TRIGGER_SUBSTANTIVE",
    "ReferenceLink",
    "RejectionRule",
    "SCHEMA",
    "SEMANTICS_PROOF",
    "SEMANTICS_SCORING",
    "SEMANTICS_SUBSTANTIVE",
    "SEMANTICS_UNESTABLISHED",
    "SourceMarkerEvidence",
    "SourceRequirementCriticality",
    "SubstantiveRule",
    "VISIBLE_MARKER",
    "build_criticality_index",
    "discover_clause_labels",
    "discover_marker_evidence",
    "discover_marker_semantics",
    "discover_reference_links",
    "discover_rejection_rules",
    "discover_substantive_rules",
]
