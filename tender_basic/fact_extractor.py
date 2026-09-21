"""Deterministic candidate discovery from a NormalizedDocument.

This module deliberately stops at candidate facts.  It does not decide which
candidate is the final value for a ProjectFacts field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from .document_models import (
    NormalizedDocument,
    ParagraphElement,
    PdfBlockElement,
    PdfTableElement,
    TableElement,
)
from .models import (
    CandidateFact,
    FieldName,
    Locator,
    SourceType,
)
from .fact_normalizer import normalize_money, normalize_text_value
from .fact_normalizer import MONEY_FIELDS


BASE_CONFIDENCE: Mapping[str, float] = {
    "table_label_exact": 0.98,
    "label_value_same_line": 0.95,
    "label_value_next_line": 0.85,
    "labeled_multiline_value": 0.90,
    "standalone_title_candidate": 0.68,
    "platform_phrase": 0.80,
    "keyword_window": 0.70,
    # Round 5.5: a lot/section name is stated through value labels or section
    # headings far more often than through a "标段名称：" label.
    "lot_value_context": 0.94,
    "lot_section_heading": 0.90,
    "lot_cover_title": 0.75,
}

_DEFAULT_ALIASES_PATH = Path(__file__).resolve().parents[1] / "rules" / "field_aliases.yaml"
_MAX_TABLE_VALUE_DISTANCE = 3
_TRAILING_LABEL_PUNCTUATION = " \t\r\n:："
_VALUE_EDGE_PUNCTUATION = " \t\r\n,，;；。.!！？!?"
_QUOTE_PAIRS = {
    ("“", "”"),
    ("\"", "\""),
    ("'", "'"),
    ("‘", "’"),
    ("「", "」"),
    ("『", "』"),
    ("（", "）"),
    ("(", ")"),
}


@dataclass(frozen=True)
class _TextRecord:
    """One ordered source item used by the four small extraction rules."""

    text: str
    source_file: str
    locator: Locator
    source_type: SourceType
    section: str | None
    kind: str
    style_name: str | None = None


def load_field_aliases(path: str | Path | None = None) -> dict[str, list[str]]:
    """Load the fixed V1 alias catalog and reject ambiguous field definitions."""

    aliases_path = Path(path) if path is not None else _DEFAULT_ALIASES_PATH
    with aliases_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    result: dict[str, list[str]] = {field.value: [] for field in FieldName}
    for field in FieldName:
        raw_aliases = payload.get(field.value, [])
        if not isinstance(raw_aliases, list):
            raise ValueError(f"Aliases for {field.value} must be a list")
        cleaned = []
        for alias in raw_aliases:
            normalized = _label_key(str(alias))
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        result[field.value] = cleaned

    # A generic alias such as "编号" would make project_number and
    # tender_number impossible to distinguish.  Keep only unambiguous aliases.
    ownership: dict[str, set[str]] = {}
    for field, field_aliases in result.items():
        for alias in field_aliases:
            ownership.setdefault(alias, set()).add(field)
    ambiguous = {alias for alias, owners in ownership.items() if len(owners) > 1}
    if ambiguous:
        for field in result:
            result[field] = [alias for alias in result[field] if alias not in ambiguous]
    return result


def _label_key(value: str) -> str:
    """Return a conservative exact-label representation."""

    return normalize_text_value(value).rstrip(_TRAILING_LABEL_PUNCTUATION)


def _aliases_by_length(aliases: Mapping[str, list[str]]) -> list[tuple[str, str]]:
    pairs = [
        (alias, field)
        for field, field_aliases in aliases.items()
        for alias in field_aliases
    ]
    return sorted(pairs, key=lambda item: len(item[0]), reverse=True)


def _alias_pattern(aliases: Mapping[str, list[str]]) -> str:
    return "|".join(
        re.escape(alias)
        for alias, _field in _aliases_by_length(aliases)
    )


def _field_for_exact_label(text: str, aliases: Mapping[str, list[str]]) -> str | None:
    label = _label_key(text)
    for field, field_aliases in aliases.items():
        if label in field_aliases:
            return field
    return None


def _field_for_label_prefix(text: str, aliases: Mapping[str, list[str]]) -> str | None:
    """Match a field label followed only by a colon, with no value."""

    normalized = normalize_text_value(text)
    for alias, field in _aliases_by_length(aliases):
        if re.fullmatch(re.escape(alias) + r"\s*[：:]?", normalized):
            return field
    return None


def _field_at_text_start(text: str, aliases: Mapping[str, list[str]]) -> str | None:
    """Match a label at the start of a record, whether it already has a value."""

    normalized = normalize_text_value(text)
    for alias, field in _aliases_by_length(aliases):
        if re.match(re.escape(alias) + r"\s*[：:]", normalized):
            return field
    return None


def _looks_like_heading(text: str, style_name: str | None = None) -> bool:
    normalized = normalize_text_value(text)
    style = normalize_text_value(style_name or "").lower()
    if not normalized:
        return False
    if "heading" in style or style.startswith("标题"):
        return True
    if re.fullmatch(r"第[^：:]{1,30}[章节篇部分条]", normalized):
        return True
    if normalized in {"招标公告", "采购公告", "投标人须知前附表", "采购公告"}:
        return True
    return False


def _clean_extracted_value(value: str) -> str:
    cleaned = value.strip().strip(_VALUE_EDGE_PUNCTUATION).strip()
    changed = True
    while changed and len(cleaned) >= 2:
        changed = False
        for opening, closing in _QUOTE_PAIRS:
            if cleaned.startswith(opening) and cleaned.endswith(closing):
                cleaned = (
                    cleaned[len(opening) : -len(closing)]
                    .strip()
                    .strip(_VALUE_EDGE_PUNCTUATION)
                    .strip()
                )
                changed = True
                break
    return cleaned


def _is_non_value_reference(
    field: str,
    value: str,
    aliases: Mapping[str, list[str]] | None = None,
) -> bool:
    """Reject layout placeholders and definition text as field values."""

    compact = normalize_text_value(value).replace(" ", "")
    if not compact:
        return True
    if compact in {
        "见供应商须知前附表",
        "见投标人须知前附表",
        "采购人名称",
        "投标人名称",
        "投标总价（元）",
        "功能要求",
        "名",
        "供应商",
        "投标人",
        "小写",
        "大写",
    }:
        return True
    if compact.rstrip("：:") in {"供应商", "投标人", "法定代表人", "授权代表"}:
        return True
    if compact.startswith(("见", "符合第二章", "符合第五章")):
        return True
    # PDF table detectors may leave an opening bracket at the end of a text
    # block.  Treat that as a truncated fragment rather than a competing fact.
    if compact.count("(") > compact.count(")") or compact.count("（") > compact.count("）"):
        return True
    if field in {FieldName.PURCHASER.value, FieldName.TENDER_AGENCY.value}:
        if compact.startswith(
            ("联系人", "联系方式", "地址", "电话", "电子邮件", "邮编", "名", "称")
        ):
            return True
    if field == FieldName.PROJECT_LOCATION.value and compact in {
        "招标人指定地点",
        "供应商指定地点",
        "见招标人指定地点",
    }:
        return True
    if field == FieldName.PROJECT_LOCATION.value and any(
        marker in compact
        for marker in (
            "开发周期",
            "试运行时间",
            "质保期",
            "验收合格",
            "安装及调试",
            "交易平台",
            "招采平台",
            "电子平台",
        )
    ):
        return True
    if field == FieldName.BID_OPEN_LOCATION.value and any(
        marker in compact for marker in ("上传", "加密", "签章", "电子响应文件")
    ):
        return True
    if field == FieldName.PROCUREMENT_SCOPE.value and "功能要求" in compact:
        return True
    lines = [line.strip() for line in value.replace("\r", "").split("\n") if line.strip()]
    small_tokens = [
        re.sub(r"[：:，,。；;、()（）]", "", token)
        for token in re.split(r"\s+", value.strip())
        if token.strip()
    ]
    if (
        field not in MONEY_FIELDS
        and len(lines) >= 3
        and sum(len(line.replace(" ", "")) <= 3 for line in lines) >= 2
    ):
        return True
    if (
        field not in MONEY_FIELDS
        and len(value) >= 20
        and sum(len(token) <= 2 for token in small_tokens) >= 2
    ):
        return True
    if field == FieldName.PROJECT_NAME.value and any(
        marker in compact
        for marker in ("投标总价", "投标人名称", "采购人名称", "法定代表人", "授权代表")
    ):
        return True
    if field == FieldName.PROJECT_NAME.value and (":" in compact or "：" in compact):
        return True
    if field == FieldName.PURCHASER.value and compact.startswith("归集和发布采购需求"):
        return True
    if field == FieldName.TENDER_AGENCY.value and compact.startswith("受采购人委托组织采购活动"):
        return True
    # An unfilled layout placeholder is not a fact value.  Two generic shapes
    # occur in real tender PDFs: a run of private-use/blank glyphs used as a
    # fill-in rule (the text extractor sees glyphs where the page shows blanks),
    # and an instruction enclosed in brackets such as "招标人：(盖单位章)".
    if _is_blank_glyph_run(compact):
        return True
    if _is_bracketed_instruction(compact):
        return True
    # A value assembled by concatenating several unrelated labels is a table
    # header row the PDF laid out one label per line, not any of those facts.
    if _is_concatenated_label_list(value, aliases):
        return True
    # An entity field must name an entity; a bare organisational role is a
    # layout label, not a party name.
    if field in {
        FieldName.PROJECT_NAME.value,
        FieldName.PURCHASER.value,
        FieldName.TENDER_AGENCY.value,
    } and _is_bare_role_noun(value):
        return True
    # A bare measurement unit is the empty answer row of a blank form; a
    # text/entity field never legitimately holds one.
    if _is_bare_measurement_unit(field, value):
        return True
    return False


def _is_blank_glyph_run(value: str) -> bool:
    """True when a value is only private-use/blank glyphs used as a fill rule."""
    stripped = value.strip()
    if not stripped:
        return False
    blank_like = sum(
        1
        for character in stripped
        if character.isspace()
        or character == "\u2007"
        or character in "_＿"
        or 0xE000 <= ord(character) <= 0xF8FF
        or ord(character) in {0x25A1, 0x2610, 0x3000}
    )
    return blank_like == len(stripped)


_BRACKETED_INSTRUCTION_RE = re.compile(r"^[（(][^（()）]{1,24}[）)]$")
_INSTRUCTION_MARKERS = (
    "盖章",
    "盖单位章",
    "签字",
    "公章",
    "签章",
    "电子印章",
    "加盖",
    "手写",
    "填写",
    "说明",
    "如有",
    "若无",
    "可选",
    "示例",
)


def _is_bracketed_instruction(value: str) -> bool:
    """True for a bracketed layout instruction such as '（盖单位章）'."""
    stripped = value.strip()
    if not _BRACKETED_INSTRUCTION_RE.match(stripped):
        return False
    inner = stripped[1:-1].strip()
    return any(marker in inner for marker in _INSTRUCTION_MARKERS)


def _is_concatenated_label_list(value: str, aliases: Mapping[str, list[str]] | None = None) -> bool:
    """True when a value is several short lines that each look like a bare label.

    A PDF table header laid out one label per line concatenates into something
    like '承包单位合同主要内容合同金额'.  Each source line is a label with no
    value, so the joined text cannot be a fact value.  When the field-alias
    vocabulary is available it is used as an independent label source, so a
    single stray label line is rejected as well.
    """
    lines = [line.strip() for line in value.replace("\r", "").split("\n") if line.strip()]
    if not lines:
        return False
    # A single line is only a label when it is an exact field alias.  Length
    # alone must never decide this: a real institution name can be as short as
    # the labels around it.
    if len(lines) == 1:
        if aliases is None:
            return False
        return _field_for_exact_label(lines[0].rstrip(_TRAILING_LABEL_PUNCTUATION).strip(), aliases) is not None
    label_like = 0
    for line in lines:
        body = line.rstrip(_TRAILING_LABEL_PUNCTUATION).strip()
        if not body:
            continue
        # A line carrying its own label/value separator is not a bare label.
        if "：" in line or ":" in line:
            return False
        if aliases is not None and _field_for_exact_label(body, aliases) is not None:
            label_like += 1
            continue
        if len(body) <= 12 and not re.search(r"[。！？，、；\d]", body):
            label_like += 1
    return label_like == len(lines)


def _normalize_entity_value(field: str, value: str) -> str:
    """Take the named institution from a multi-line contact cell."""

    if field not in {FieldName.PURCHASER.value, FieldName.TENDER_AGENCY.value}:
        return value
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    match = re.search(r"名\s*称\s*[：:]\s*([^\n]+)", normalized)
    if match:
        return match.group(1).strip()
    return value


def _evidence_is_label_header_block(
    evidence: str,
    aliases: Mapping[str, list[str]] | None,
    field: str | None = None,
) -> bool:
    """True when the evidence is a table header row, not a label/value pair.

    PDF table extraction often returns a header row as one text block with one
    label per line.  For a header row such as ``项目名称\\n承包单位\\n合同主要内容``
    the extractor would read the first line as the label and the remaining
    header cells as its value, inventing a fact that does not exist.

    Two shapes are rejected:

    * every line is itself a known field label (so nothing here is a value); and
    * the first line is this field's own label while two or more further short,
      punctuation-free lines follow -- those are the remaining header cells.

    A genuine label/value pair such as ``质量目标\\n合格`` is never rejected: it
    has a single following line, which is not a field label.
    """
    if aliases is None:
        return False
    lines = [line.strip() for line in evidence.replace("\r", "").split("\n") if line.strip()]
    if len(lines) < 2:
        return False
    for line in lines:
        # A real label/value line carries a separator and is not a bare label.
        if "：" in line or ":" in line:
            return False
    if all(
        _field_for_exact_label(line.rstrip(_TRAILING_LABEL_PUNCTUATION).strip(), aliases) is not None
        for line in lines
    ):
        return True
    if field is None:
        return False
    head = _field_for_exact_label(lines[0].rstrip(_TRAILING_LABEL_PUNCTUATION).strip(), aliases)
    if head != field:
        return False
    tail = lines[1:]
    return len(tail) >= 2 and all(
        len(line) <= 12 and not re.search(r"[。！？，、；：\d]", line) for line in tail
    )


# Organisational roles name a position in the contract, never a specific party.
# A value that is only a role noun is a layout label the extractor mis-read, not
# an entity name; a real party always carries a distinguishing name.
_ROLE_NOUNS = frozenset(
    {
        "招标人",
        "投标人",
        "采购人",
        "供应商",
        "中标人",
        "发包人",
        "承包人",
        "委托人",
        "被委托人",
        "建设单位",
        "施工单位",
        "监理单位",
        "设计单位",
        "勘察单位",
        "承包单位",
        "分包单位",
        "承包方",
        "发包方",
        "招标代理机构",
        "采购代理机构",
        "代理机构",
        "甲方",
        "乙方",
        "丙方",
    }
)


def _is_bare_role_noun(value: str) -> bool:
    """True when a value is only an organisational role label."""
    compact = value.strip().strip(_VALUE_EDGE_PUNCTUATION).strip()
    compact = compact.rstrip(_TRAILING_LABEL_PUNCTUATION).strip()
    return compact in _ROLE_NOUNS


# A measured quantity is a number plus its unit.  A bare unit is the empty
# answer row of a blank form, not a value.
_BARE_UNIT_VALUES = frozenset(
    {
        "日历天",
        "天",
        "日",
        "月",
        "年",
        "个",
        "项",
        "套",
        "台",
        "元",
        "万元",
        "人民币",
        "%",
        "％",
        "平方米",
        "立方米",
    }
)


def _is_bare_measurement_unit(field: str, value: str) -> bool:
    compact = value.strip().strip(_VALUE_EDGE_PUNCTUATION).strip()
    if compact in _BARE_UNIT_VALUES:
        return True
    # A value that is only digits plus a unit carries no quantity for a text
    # field such as project_name; those fields never legitimately hold a
    # measurement.
    if field == FieldName.PROJECT_NAME.value and re.fullmatch(
        r"\d+(?:\.\d+)?\s*(?:日历天|天|个月|月|年|元|万元|%|％|项|套|台)", compact
    ):
        return True
    return False


def _primary_label_in_evidence(
    field: str,
    evidence: str,
    aliases: Mapping[str, list[str]] | None = None,
) -> bool:
    compact = normalize_text_value(evidence).replace(" ", "")
    if _evidence_is_label_header_block(evidence, aliases, field):
        return False
    if field == FieldName.QUALITY_TARGET.value:
        return any(
            marker in compact
            for marker in ("质量要求", "质量标准", "质量目标", "供货质量", "服务质量要求")
        )
    if field == FieldName.PROCUREMENT_SCOPE.value:
        return any(
            marker in compact
            for marker in ("招标范围", "采购范围", "采购内容", "项目内容", "服务范围", "建设内容", "采购需求")
        )
    if field in {FieldName.PURCHASER.value, FieldName.TENDER_AGENCY.value}:
        # A signature-block instruction such as "招标人：(盖单位章)" names no
        # institution.  Require the evidence to carry an actual organisation
        # after the label instead of a bracketed layout instruction.
        for label in ("招标人名称", "采购人名称", "招标代理机构", "采购代理机构", "招标人", "采购人"):
            position = compact.find(label)
            if position < 0:
                continue
            tail = compact[position + len(label):].lstrip("：:")
            if not tail:
                return False
            if _is_bracketed_instruction(tail) or _is_blank_glyph_run(tail):
                return False
            return True
    return True


def _record_from_paragraph(
    element: ParagraphElement,
    source_file: str,
    section: str | None,
) -> _TextRecord:
    paragraph = element.paragraph
    return _TextRecord(
        text=paragraph.text,
        source_file=source_file,
        locator=paragraph.locator,
        source_type=SourceType.DOCX,
        section=section,
        kind="paragraph",
        style_name=paragraph.style_name,
    )


def _record_from_pdf_block(
    element: PdfBlockElement,
    source_file: str,
    section: str | None,
) -> _TextRecord:
    block = element.block
    return _TextRecord(
        text=block.text,
        source_file=source_file,
        locator=block.locator,
        source_type=SourceType.PDF,
        section=section,
        kind="pdf_block",
    )


def _iter_ordered_records(document: NormalizedDocument) -> Iterable[_TextRecord]:
    """Yield PDF blocks and DOCX body items in normalized source order."""

    section: str | None = None
    for element in document.elements:
        if isinstance(element, ParagraphElement):
            paragraph = element.paragraph
            if paragraph.text and _looks_like_heading(paragraph.text, paragraph.style_name):
                section = normalize_text_value(paragraph.text)
            yield _record_from_paragraph(element, document.source_file, section)
        elif isinstance(element, PdfBlockElement):
            if element.block.text and _looks_like_heading(element.block.text):
                section = normalize_text_value(element.block.text)
            yield _record_from_pdf_block(element, document.source_file, section)
        elif isinstance(element, TableElement):
            table = element.table
            for row in table.rows:
                for cell in row.cells:
                    yield _TextRecord(
                        text=cell.text,
                        source_file=document.source_file,
                        locator=cell.locator,
                        source_type=SourceType.DOCX,
                        section=section,
                        kind="table_cell",
                    )
        elif isinstance(element, PdfTableElement):
            table = element.table
            for row in table.rows:
                for cell in row.cells:
                    yield _TextRecord(
                        text=cell.text,
                        source_file=document.source_file,
                        locator=cell.locator,
                        source_type=SourceType.PDF,
                        section=section,
                        kind="table_cell",
                    )


def _text_records(records: Iterable[_TextRecord]) -> list[_TextRecord]:
    expanded: list[_TextRecord] = []
    for record in records:
        lines = record.text.splitlines() or [record.text]
        expanded.extend(
            _TextRecord(
                text=line,
                source_file=record.source_file,
                locator=record.locator,
                source_type=record.source_type,
                section=record.section,
                kind=record.kind,
            )
            for line in lines
        )
    return expanded


def _make_candidate(
    *,
    field: str,
    value: str,
    record: _TextRecord,
    method: str,
    evidence_text: str,
    confidence: float | None = None,
    locator: Locator | None = None,
    aliases: Mapping[str, list[str]] | None = None,
) -> CandidateFact | None:
    cleaned_value = _normalize_entity_value(field, _clean_extracted_value(value))
    evidence = evidence_text.strip()
    if (
        not cleaned_value
        or not evidence
        or _is_non_value_reference(field, cleaned_value, aliases)
        or not _primary_label_in_evidence(field, evidence, aliases)
    ):
        return None
    return CandidateFact(
        value=cleaned_value,
        confidence=confidence if confidence is not None else BASE_CONFIDENCE[method],
        method=method,
        source_file=record.source_file,
        source_type=record.source_type,
        locator=locator or record.locator,
        section=record.section,
        evidence_text=evidence,
    )


def _with_source_file(candidate: CandidateFact, source_file: str) -> CandidateFact:
    return candidate.model_copy(update={"source_file": source_file})


def _table_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    candidates = {field.value: [] for field in FieldName}
    section: str | None = None
    for element in document.elements:
        if isinstance(element, ParagraphElement):
            paragraph = element.paragraph
            if paragraph.text and _looks_like_heading(paragraph.text, paragraph.style_name):
                section = normalize_text_value(paragraph.text)
            continue
        if not isinstance(element, (TableElement, PdfTableElement)):
            if isinstance(element, PdfBlockElement) and element.block.text:
                if _looks_like_heading(element.block.text):
                    section = normalize_text_value(element.block.text)
            continue

        table = element.table
        for row in table.rows:
            cells = row.cells
            for cell_position, label_cell in enumerate(cells):
                field = _field_for_exact_label(label_cell.text, aliases)
                if field is None:
                    continue
                value_cell = None
                for offset in range(1, _MAX_TABLE_VALUE_DISTANCE + 1):
                    candidate_position = cell_position + offset
                    if candidate_position >= len(cells):
                        break
                    candidate_cell = cells[candidate_position]
                    if not normalize_text_value(candidate_cell.text):
                        continue
                    if _field_for_exact_label(candidate_cell.text, aliases) is not None:
                        break
                    value_cell = candidate_cell
                    break
                if value_cell is None:
                    continue
                evidence = " | ".join(cell.text.strip() for cell in cells if cell.text.strip())
                record = _TextRecord(
                    text=value_cell.text,
                    source_file=document.source_file,
                    locator=value_cell.locator,
                    source_type=(
                        SourceType.PDF
                        if isinstance(element, PdfTableElement)
                        else SourceType.DOCX
                    ),
                    section=section,
                    kind="table_cell",
                )
                candidate = _make_candidate(
                    field=field,
                    value=value_cell.text,
                    record=record,
                    method="table_label_exact",
                    evidence_text=evidence,
                    locator=value_cell.locator,
                    aliases=aliases,
                )
                if candidate is not None:
                    candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def _same_line_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    candidates = {field.value: [] for field in FieldName}
    alias_pattern = _alias_pattern(aliases)
    if not alias_pattern:
        return candidates
    label_pattern = re.compile(rf"(?P<label>{alias_pattern})\s*[：:]\s*")
    next_label_pattern = re.compile(rf"(?:{alias_pattern})\s*[：:]")

    for record in _text_records(_iter_ordered_records(document)):
        text = record.text
        for match in label_pattern.finditer(text):
            field = _field_for_exact_label(match.group("label"), aliases)
            if field is None:
                continue
            if (
                field == FieldName.PROJECT_LOCATION.value
                and _label_key(match.group("label")) == "建设地点"
                and match.start() > 0
                and re.match(r"[\u4e00-\u9fff]", text[match.start() - 1])
            ):
                # Do not treat the substring in a compound label such as
                # “系统建设地点” as the generic project-location label.
                continue
            tail = text[match.end() :]
            next_label = next_label_pattern.search(tail)
            if next_label is not None:
                tail = tail[: next_label.start()]
            value = _clean_extracted_value(tail)
            if not value or _field_for_exact_label(value, aliases) is not None:
                continue
            candidate = _make_candidate(
                field=field,
                value=value,
                record=record,
                method="label_value_same_line",
                evidence_text=text,
                aliases=aliases,
            )
            if candidate is not None:
                candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def _next_line_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    candidates = {field.value: [] for field in FieldName}
    records = list(_iter_ordered_records(document))
    expanded_records: list[_TextRecord] = []
    for record in records:
        if record.kind in {"paragraph", "pdf_block"}:
            lines = record.text.splitlines() or [record.text]
            expanded_records.extend(
                _TextRecord(
                    text=line,
                    source_file=record.source_file,
                    locator=record.locator,
                    source_type=record.source_type,
                    section=record.section,
                    kind=record.kind,
                )
                for line in lines
            )
        else:
            expanded_records.append(record)
    records = expanded_records
    for index, record in enumerate(records):
        if record.kind not in {"paragraph", "pdf_block"}:
            continue
        field = _field_for_label_prefix(record.text, aliases)
        if field is None:
            continue
        next_record = None
        for following in records[index + 1 :]:
            if following.kind not in {"paragraph", "pdf_block"}:
                break
            if following.text.strip():
                next_record = following
                break
        if next_record is None:
            continue
        next_value = _clean_extracted_value(next_record.text)
        if not next_value:
            continue
        if (
            _field_for_label_prefix(next_record.text, aliases) is not None
            or _field_at_text_start(next_record.text, aliases) is not None
        ):
            continue
        if _looks_like_heading(next_record.text):
            continue
        evidence = f"{record.text.strip()}\n{next_record.text.strip()}"
        candidate = _make_candidate(
            field=field,
            value=next_value,
            record=next_record,
            method="label_value_next_line",
            evidence_text=evidence,
            aliases=aliases,
        )
        if candidate is not None:
            candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def _split_label_value(
    text: str,
    aliases: Mapping[str, list[str]],
) -> tuple[str, str] | None:
    """Split a complete label record into ``(field, tail)`` conservatively."""

    raw = text.strip()
    if not raw:
        return None
    for alias, field in _aliases_by_length(aliases):
        match = re.match(
            rf"^{re.escape(alias)}\s*(?:(?:：|:)\s*(?P<tail>.*))?$",
            raw,
        )
        if match is not None:
            return field, (match.group("tail") or "").strip()
    return None


def _looks_like_section_heading(text: str) -> bool:
    compact = normalize_text_value(text).replace(" ", "").lstrip("*＊")
    if not compact:
        return False
    return bool(
        re.match(r"^第[一二三四五六七八九十百千万零〇0-9]+[章节篇部分条]", compact)
        or re.match(r"^(?:[一二三四五六七八九十百千万]+、|\d+(?:\.\d+)*[、.．)])", compact)
    )


def _join_multiline_parts(parts: list[str]) -> str:
    cleaned: list[str] = []
    for part in parts:
        value = _clean_extracted_value(part)
        if value.startswith(("名称：", "名称:")):
            value = value[3:].strip()
        if value:
            cleaned.append(value)
    return "".join(cleaned)


def _labeled_multiline_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    """Collect a label followed by one to three safely bounded source lines."""

    candidates = {field.value: [] for field in FieldName}
    records = [
        record
        for record in _iter_ordered_records(document)
        if record.kind in {"paragraph", "pdf_block"}
    ]
    multiline_fields = {
        FieldName.PROJECT_NAME.value,
        FieldName.PURCHASER.value,
        FieldName.TENDER_AGENCY.value,
        FieldName.PROJECT_LOCATION.value,
        FieldName.PROCUREMENT_SCOPE.value,
        FieldName.DURATION.value,
        FieldName.QUALITY_TARGET.value,
        FieldName.BID_OPEN_LOCATION.value,
        FieldName.ELECTRONIC_PLATFORM.value,
    }

    for index, record in enumerate(records):
        source_lines = record.text.splitlines() or [record.text]
        for line_index, line in enumerate(source_lines):
            split = _split_label_value(line, aliases)
            if split is None or split[0] not in multiline_fields:
                continue
            field, tail = split
            parts: list[str] = [tail] if tail else []
            evidence_lines = [line.strip()]
            value_record = record

            # First consume continuation lines within the same PDF block.
            for continuation in source_lines[line_index + 1 :]:
                continuation = continuation.strip()
                if not continuation:
                    break
                if (
                    _split_label_value(continuation, aliases) is not None
                    or _looks_like_section_heading(continuation)
                ):
                    break
                parts.append(continuation)
                evidence_lines.append(continuation)
                if len(parts) >= 3:
                    break

            # A label-only block is common after PDF layout extraction.  Walk
            # at most three following source blocks and stop at a new label or
            # heading, so a whole document tail cannot be swallowed.
            if not parts:
                for following in records[index + 1 : index + 4]:
                    following_text = following.text.strip()
                    if not following_text:
                        break
                    if (
                        _split_label_value(following_text, aliases) is not None
                        or _looks_like_section_heading(following_text)
                    ):
                        break
                    parts.extend(following_text.splitlines()[: 3])
                    evidence_lines.append(following_text)
                    value_record = following
                    if len(parts) >= 3:
                        break

            value = _join_multiline_parts(parts)
            if not value or len(parts) < 1:
                continue
            # A single same-line value is already represented by the exact
            # method.  This method is reserved for a visibly split value.
            if tail and "\n" not in record.text:
                continue
            candidate = _make_candidate(
                field=field,
                value=value,
                record=value_record,
                method="labeled_multiline_value",
                evidence_text="\n".join(evidence_lines),
                aliases=aliases,
            )
            if candidate is not None:
                candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def _standalone_title_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    """Emit low-confidence project-name candidates for obvious standalone titles."""

    candidates = {field.value: [] for field in FieldName}
    for record in _iter_ordered_records(document):
        if record.kind not in {"paragraph", "pdf_block"}:
            continue
        text = normalize_text_value(record.text).replace(" ", "")
        if not 8 <= len(text) <= 120 or "\n" in record.text:
            continue
        if (
            record.kind == "pdf_block"
            and getattr(record.locator, "page", 99) > 3
            and not record.style_name
        ):
            continue
        if any(mark in text for mark in ("：", ":", "。", "；", ";", "，", ",")):
            continue
        if _looks_like_section_heading(text) or _field_for_label_prefix(text, aliases):
            continue
        if any(
            marker in text
            for marker in (
                "本项目",
                "应当",
                "须知",
                "以下简称",
                "根据",
                "包括但不限于",
                "拒绝",
                "成交",
                "供应商",
                "合同",
                "不得",
                "按照",
                "符合",
            )
        ):
            continue
        context = normalize_text_value(record.section or "")
        style = normalize_text_value(record.style_name or "").lower()
        obvious_context = (
            "title" in style
            or "标题" in style
            or any(marker in context for marker in ("公告", "投标文件格式", "响应文件格式"))
            or text.endswith(("项目", "工程", "采购"))
        )
        if not obvious_context:
            continue
        candidate = _make_candidate(
            field=FieldName.PROJECT_NAME.value,
            value=text,
            record=record,
            method="standalone_title_candidate",
            evidence_text=record.text,
            confidence=BASE_CONFIDENCE["standalone_title_candidate"],
            aliases=aliases,
        )
        if candidate is not None:
            candidates[FieldName.PROJECT_NAME.value].append(
                _with_source_file(candidate, document.source_file)
            )
    return candidates


def _keyword_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    candidates = {field.value: [] for field in FieldName}
    alias_pattern = _alias_pattern(aliases)
    if not alias_pattern:
        return candidates

    relation_pattern = re.compile(
        rf"(?P<label>{alias_pattern})\s*(?:为|是|包括|指(?!定))\s*"
        rf"(?P<value>[^\n，,。；;、]+)"
    )
    boolean_pattern = re.compile(
        rf"(?<![是否])(?P<value>不接受|不允许|不得|禁止|接受|允许|可以|是|否)"
        rf"\s*(?P<label>{alias_pattern})"
    )

    for record in _text_records(_iter_ordered_records(document)):
        for pattern in (relation_pattern, boolean_pattern):
            for match in pattern.finditer(record.text):
                field = _field_for_exact_label(match.group("label"), aliases)
                if field is None:
                    continue
                value = match.group("value")
                # The boolean phrase rule is intentionally narrow.  It exists
                # to preserve the explicit negative in "不接受联合体投标";
                # it is not a general semantic classifier.
                if pattern is boolean_pattern and field != FieldName.CONSORTIUM_ALLOWED.value:
                    continue
                candidate = _make_candidate(
                    field=field,
                    value=value,
                    record=record,
                    method="keyword_window",
                    evidence_text=record.text,
                    aliases=aliases,
                )
                if candidate is not None:
                    candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


_LOT_TOKEN_PATTERN = (
    r"(?<!同)(?<!每)(?<!各)(?:第[一二三四五六七八九十百零〇\d]{1,3}标段"
    r"|[一二三四五六七八九十百零〇\d]{1,3}标段)"
)

#: Labels whose value is the lot/section this tender document belongs to.
_LOT_VALUE_LABELS = (
    "合同估算价",
    "最高投标限价",
    "招标控制价",
    "最高限价",
    "控制价",
    "预算金额",
    "投标保证金的金额",
    "投标保证金金额",
    "投标保证金",
    "响应保证金",
)

#: Headings that carry the lot token as their subject.
_LOT_HEADING_TAILS = (
    "投标人资格要求",
    "供应商资格要求",
    "技术标定性评审",
    "定性评审",
    "评审标准",
    "评审办法",
    "工程量清单",
    "招标范围",
)

_LOT_VALUE_RE = re.compile(
    "(?:" + "|".join(re.escape(label) for label in _LOT_VALUE_LABELS) + ")"
    r"\s*[为是]?\s*[:：]?\s*(" + _LOT_TOKEN_PATTERN + ")"
)
_LOT_HEADING_RE = re.compile(
    "(" + _LOT_TOKEN_PATTERN + r")\s*(?:"
    + "|".join(re.escape(tail) for tail in _LOT_HEADING_TAILS)
    + ")"
)
_LOT_BARE_RE = re.compile(r"^" + _LOT_TOKEN_PATTERN + r"$")
_PROJECT_NAME_LABEL_RE = re.compile(r"(?:招标)?项目名称\s*[:：]")
_LOT_CLAUSE_NUMBER_PREFIX_RE = re.compile(r"^\d+(?=[一二三四五六七八九十百零〇]标段$)")


def _clean_lot_value(value: str) -> str:
    """Strip a clause number that the token pattern swallowed ("3.1三标段")."""

    return _LOT_CLAUSE_NUMBER_PREFIX_RE.sub("", value.strip())


def _lot_candidates(
    document: NormalizedDocument,
    aliases: Mapping[str, list[str]],
) -> dict[str, list[CandidateFact]]:
    """Resolve the lot/section name from value labels, headings, or the cover.

    A single-lot tender states its lot through project-specific wording such as
    "合同估算价：三标段……万元", "3.1 三标段投标人资格要求", or the cover title,
    and this must not be inferred from the file name or a case identifier.
    """

    candidates = {field.value: [] for field in FieldName}
    field = FieldName.LOT_NAME.value
    records = list(_iter_ordered_records(document))
    labeled_pages: dict[int, bool] = {}
    for record in records:
        page = getattr(record.locator, "page", None)
        if page is None:
            continue
        if _PROJECT_NAME_LABEL_RE.search(re.sub(r"\s+", "", record.text)):
            labeled_pages[page] = True

    for record in records:
        if record.kind not in {"paragraph", "pdf_block", "table_cell"}:
            continue
        text = normalize_text_value(record.text)
        if "标段" not in text:
            continue
        compact = re.sub(r"\s+", "", text)
        evidence = text if len(text) <= 160 else text[:157].rstrip() + "..."
        page = getattr(record.locator, "page", None)

        rules: list[tuple[str, str]] = []
        value_match = _LOT_VALUE_RE.search(compact)
        if value_match:
            rules.append(("lot_value_context", _clean_lot_value(value_match.group(1))))
        heading_match = _LOT_HEADING_RE.search(compact)
        if heading_match:
            rules.append(("lot_section_heading", _clean_lot_value(heading_match.group(1))))
        if (
            page is not None
            and page <= 3
            and labeled_pages.get(page)
            and _LOT_BARE_RE.match(compact)
        ):
            rules.append(("lot_cover_title", _clean_lot_value(compact)))

        for method, value in rules:
            if not value:
                continue
            candidate = _make_candidate(
                field=field,
                value=value,
                record=record,
                method=method,
                evidence_text=evidence,
                aliases=aliases,
            )
            if candidate is None:
                continue
            if any(
                existing.value == candidate.value
                and existing.locator == candidate.locator
                for existing in candidates[field]
            ):
                continue
            candidates[field].append(_with_source_file(candidate, document.source_file))
    return candidates


def _platform_candidates(
    document: NormalizedDocument,
) -> dict[str, list[CandidateFact]]:
    """Find explicit electronic-platform names without borrowing procurement_method."""

    candidates = {field.value: [] for field in FieldName}
    quoted_pattern = re.compile(r"[“\"「](?P<value>[^”\"」]{2,100}平台[^”\"」]*)[”\"」]")
    plain_pattern = re.compile(
        r"(?P<value>[\u4e00-\u9fffA-Za-z0-9·_（）()、-]{2,80}平台"
        r"(?:（[^）]{0,40}平台）)?)"
    )
    equivalent_short_names: set[str] = set()
    for record in _iter_ordered_records(document):
        if record.kind not in {"paragraph", "pdf_block", "table_cell"}:
            continue
        search_text = re.sub(r"\s+", "", record.text)
        paired = re.search(
            r"(?P<main>[\u4e00-\u9fffA-Za-z0-9·_]{3,60}平台)"
            r"[（(](?P<short>[\u4e00-\u9fffA-Za-z0-9·_]{2,30}平台)[）)]",
            search_text,
        )
        if paired:
            equivalent_short_names.add(paired.group("short"))
        matches = list(quoted_pattern.finditer(search_text))
        for segment in re.split(r"[，,。；;：:（）()\n]", search_text):
            matches.extend(plain_pattern.finditer(segment))
        for match in matches:
            value = match.group("value").strip()
            value = re.split(r"[（(]", value, maxsplit=1)[0].strip()
            compact_value = normalize_text_value(value).replace(" ", "")
            if compact_value in {"电子平台", "交易平台", "电子交易平台", "平台"}:
                continue
            if any(
                marker in compact_value
                for marker in (
                    "上传",
                    "缴纳",
                    "服务费",
                    "发票",
                    "疑问",
                    "操作手册",
                    "完成注册",
                    "通过",
                    "按照",
                    "请到",
                    "是否到账",
                    "供应商及采购人",
                )
            ):
                continue
            evidence_compact = normalize_text_value(record.text).replace(" ", "")
            if any(
                marker in evidence_compact
                for marker in ("操作手册", "电子签章", "短信平台", "投标保证金", "缴费凭证")
            ):
                continue
            if (
                compact_value in equivalent_short_names
                or not compact_value.endswith("平台")
                or re.match(r"^[0-9一二三四五六七八九十]", compact_value)
                or compact_value.startswith(("过", "请", "须", "应", "将", "在", "到", "由", "和"))
                or re.search(r"[0-9:：]", compact_value)
            ):
                continue
            if not any(marker in value for marker in ("电子", "交易", "招采", "招标", "采购", "公共资源")):
                continue
            candidate = _make_candidate(
                field=FieldName.ELECTRONIC_PLATFORM.value,
                value=value,
                record=record,
                method="platform_phrase",
                evidence_text=record.text,
                confidence=BASE_CONFIDENCE["platform_phrase"],
            )
            if candidate is not None:
                candidates[FieldName.ELECTRONIC_PLATFORM.value].append(
                    _with_source_file(candidate, document.source_file)
                )
    # A short name in parentheses is a deterministic alias of the full
    # platform name in that same source phrase.  Remove repeated short-name
    # candidates only after the whole document has been scanned, so a paired
    # occurrence later in the document also cleans earlier occurrences.
    deduplicated: dict[str, CandidateFact] = {}
    for candidate in candidates[FieldName.ELECTRONIC_PLATFORM.value]:
        key = normalize_text_value(candidate.value).replace(" ", "")
        if key in equivalent_short_names:
            continue
        previous = deduplicated.get(key)
        if previous is None or candidate.confidence > previous.confidence:
            deduplicated[key] = candidate
    candidates[FieldName.ELECTRONIC_PLATFORM.value] = list(deduplicated.values())
    return candidates


def _reroute_bond_form_candidates(
    candidates: dict[str, list[CandidateFact]],
) -> None:
    """Keep non-numeric guarantee-form evidence out of the amount field."""

    amount_key = FieldName.BID_BOND_AMOUNT.value
    form_key = FieldName.BID_BOND_FORM.value
    retained: list[CandidateFact] = []
    for candidate in candidates[amount_key]:
        evidence = normalize_text_value(candidate.evidence_text)
        value = normalize_text_value(candidate.value)
        is_form_phrase = any(
            marker in evidence or marker in value
            for marker in ("保证金的形式", "保证金形式", "保证金缴纳方式", "提交形式")
        )
        if is_form_phrase and normalize_money(candidate.value) is None:
            if not any(
                existing.locator == candidate.locator
                and existing.value == candidate.value
                for existing in candidates[form_key]
            ):
                candidates[form_key].append(candidate)
            continue
        retained.append(candidate)
    candidates[amount_key] = retained


def extract_candidates(
    document: NormalizedDocument,
    aliases_path: str | Path | None = None,
) -> dict[str, list[CandidateFact]]:
    """Extract raw candidates without choosing final ProjectFacts values."""

    if document.status.value != "PARSED":
        raise ValueError(f"Fact extraction requires PARSED input, got {document.status.value}")
    if document.source_type is None:
        raise ValueError("Fact extraction requires a PDF or DOCX source type")

    aliases = load_field_aliases(aliases_path)
    candidates = {field.value: [] for field in FieldName}
    for discovered in (
        _table_candidates(document, aliases),
        _same_line_candidates(document, aliases),
        _next_line_candidates(document, aliases),
        _labeled_multiline_candidates(document, aliases),
        _standalone_title_candidates(document, aliases),
        _keyword_candidates(document, aliases),
        _lot_candidates(document, aliases),
        _platform_candidates(document),
    ):
        for field in FieldName:
            candidates[field.value].extend(discovered[field.value])
    strong_project_name_methods = {
        "table_label_exact",
        "label_value_same_line",
        "label_value_next_line",
        "labeled_multiline_value",
    }
    if any(
        candidate.method in strong_project_name_methods
        for candidate in candidates[FieldName.PROJECT_NAME.value]
    ):
        candidates[FieldName.PROJECT_NAME.value] = [
            candidate
            for candidate in candidates[FieldName.PROJECT_NAME.value]
            if candidate.method != "standalone_title_candidate"
        ]
    _reroute_bond_form_candidates(candidates)
    return candidates


__all__ = [
    "BASE_CONFIDENCE",
    "extract_candidates",
    "load_field_aliases",
]
