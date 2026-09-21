"""DIAGNOSTIC ONLY: historical page-positioned DOCX reconstruction.

Desktop Microsoft Word rejected this emitter's real outputs. Production
must use word_safe_source_builder; retain this module only for forensic
fixtures and historical comparisons, never as a release renderer.

The implementation intentionally uses direct OOXML formatting instead of
Word Heading styles.  Text is placed in editable VML text boxes at the source
PDF coordinates, while detected source tables are emitted as real floating
DOCX tables with fixed grids and explicit cell formatting.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Inches
from lxml import etree

from .fact_normalizer import is_resolved_value_type_valid
from .models import CandidateFact, FactStatus, ProjectFacts
from .output_helpers import value_text
from .source_format import (
    SourceCell,
    SourceFillSlot,
    SourceFormatTemplate,
    SourcePage,
    SourceParagraph,
    SourceRun,
    SourceLine,
    SourceTable,
    repair_pdf_font_name,
)


_VML_NS = "urn:schemas-microsoft-com:vml"
_OFFICE_NS = "urn:schemas-microsoft-com:office:office"
_WORD10_NS = "urn:schemas-microsoft-com:office:word"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_WPS_NS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
_WPS_URI = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"

# WordprocessingML uses schema-ordered child sequences.  lxml's append()
# method does not know those sequences, and desktop Word is substantially
# less forgiving than LibreOffice when a hand-authored property child is out
# of order.  Keep the small set of containers emitted by this builder in one
# place so every direct OOXML insertion is deterministic and Word-safe.
_PPR_CHILD_ORDER = (
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd",
    "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
)
_RPR_CHILD_ORDER = (
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps",
    "strike", "dstrike", "outline", "shadow", "emboss", "imprint",
    "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
    "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
    "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
    "eastAsianLayout", "specVanish", "oMath", "rPrChange",
)
_TBLPR_CHILD_ORDER = (
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
    "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
    "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
    "tblDescription", "tblPrChange",
)
_TCPR_CHILD_ORDER = (
    "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
    "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
    "headers", "cellIns", "cellDel", "cellMerge", "tcPrChange",
)
_TRPR_CHILD_ORDER = (
    "cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter",
    "cantSplit", "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden",
    "ins", "del", "trPrChange",
)
_TC_BORDERS_CHILD_ORDER = (
    # Transitional WordprocessingML uses left/right.  The newer start/end
    # aliases are not accepted by the older schema used by desktop Word.
    "top", "left", "bottom", "right", "insideH", "insideV", "tl2br", "tr2bl",
)


def _insert_ordered(
    parent: etree._Element,
    child: etree._Element,
    order: tuple[str, ...],
) -> etree._Element:
    """Insert a child according to the WordprocessingML schema order."""

    child_name = etree.QName(child).localname
    child_rank = order.index(child_name) if child_name in order else len(order)
    for index, existing in enumerate(parent):
        existing_name = etree.QName(existing).localname
        existing_rank = order.index(existing_name) if existing_name in order else len(order)
        if existing_rank > child_rank:
            parent.insert(index, child)
            return child
    parent.append(child)
    return child


def _new_ordered(
    parent: etree._Element,
    tag: str,
    order: tuple[str, ...],
) -> etree._Element:
    return _insert_ordered(parent, etree.Element(tag), order)

_FONT_FALLBACKS = {
    # Use installed Windows family names for the editable output.  The PDF
    # source name is retained in SourceRun.raw_font_name; aliases such as
    # SimSun/FangSong are not universally registered under their PostScript
    # names and can otherwise lose Chinese glyphs in LibreOffice.
    "宋体": "宋体",
    "SimSun": "宋体",
    "SimSun-ExtB": "宋体",
    "黑体": "黑体",
    "SimHei": "黑体",
    "仿宋": "仿宋",
    "FangSong": "仿宋",
    "FangSong_GB2312": "仿宋",
    "楷体": "楷体",
    "KaiTi": "楷体",
    "Arial": "Arial",
    "Calibri": "Calibri",
    "Times New Roman": "Times New Roman",
    "TimesNewRomanPSMT": "Times New Roman",
}


def _twips(points: float) -> int:
    return max(0, int(round(float(points) * 20.0)))


def _emu(points: float) -> int:
    return max(1, int(round(float(points) * 12700.0)))


def _font_name(source_name: str) -> tuple[str, bool]:
    name = source_name or "宋体"
    if name in _FONT_FALLBACKS:
        mapped = _FONT_FALLBACKS[name]
        return mapped, mapped != name
    # A repaired Chinese family name can still be represented by a stable
    # installed fallback.  The source name remains in the source model and is
    # listed in generation_report.font_substitutions.
    if "黑体" in name or "Hei" in name:
        return "SimHei", True
    if "仿宋" in name or "Fang" in name:
        return "FangSong", True
    if "楷体" in name or "Kai" in name:
        return "KaiTi", True
    return "SimSun", True


def _color_hex(color: int | None) -> str | None:
    if color is None:
        return None
    try:
        return f"{int(color) & 0xFFFFFF:06X}"
    except (TypeError, ValueError):
        return None


def _set_textbox_paragraph_format(
    paragraph: etree._Element,
    source_paragraph: SourceParagraph,
) -> None:
    ppr = etree.SubElement(paragraph, qn("w:pPr"))
    jc = _new_ordered(ppr, qn("w:jc"), _PPR_CHILD_ORDER)
    jc.set(qn("w:val"), source_paragraph.alignment)
    spacing = _new_ordered(ppr, qn("w:spacing"), _PPR_CHILD_ORDER)
    spacing.set(qn("w:before"), str(_twips(source_paragraph.space_before)))
    spacing.set(qn("w:after"), str(_twips(source_paragraph.space_after)))
    base_size = next(
        (run.font_size for run in source_paragraph.runs if run.font_size > 0),
        10.5,
    )
    line = source_paragraph.line_spacing + base_size * 1.05
    spacing.set(qn("w:line"), str(max(120, _twips(line))))
    spacing.set(qn("w:lineRule"), "atLeast")
    if source_paragraph.first_line_indent > 0:
        indentation = _new_ordered(ppr, qn("w:ind"), _PPR_CHILD_ORDER)
        indentation.set(qn("w:firstLine"), str(_twips(source_paragraph.first_line_indent)))
    if source_paragraph.page_break_before:
        _new_ordered(ppr, qn("w:pageBreakBefore"), _PPR_CHILD_ORDER)


def _append_run(
    parent: etree._Element,
    text: str,
    source_run: SourceRun | None,
    *,
    underline_override: bool | None = None,
) -> None:
    if text == "":
        return
    run = etree.SubElement(parent, qn("w:r"))
    rpr = etree.SubElement(run, qn("w:rPr"))
    source_font = source_run.font_name if source_run is not None else "宋体"
    font, _substituted = _font_name(source_font)
    fonts = _new_ordered(rpr, qn("w:rFonts"), _RPR_CHILD_ORDER)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), font)
    size = source_run.font_size if source_run is not None and source_run.font_size > 0 else 10.5
    if source_run is not None and source_run.bold:
        _new_ordered(rpr, qn("w:b"), _RPR_CHILD_ORDER)
    if source_run is not None and source_run.italic:
        _new_ordered(rpr, qn("w:i"), _RPR_CHILD_ORDER)
    color = None
    if source_run is not None:
        color = _color_hex(source_run.color)
    if color:
        _new_ordered(rpr, qn("w:color"), _RPR_CHILD_ORDER).set(qn("w:val"), color)
    _new_ordered(rpr, qn("w:sz"), _RPR_CHILD_ORDER).set(
        qn("w:val"), str(max(2, int(round(size * 2))))
    )
    _new_ordered(rpr, qn("w:szCs"), _RPR_CHILD_ORDER).set(
        qn("w:val"), str(max(2, int(round(size * 2))))
    )
    underline = (
        underline_override
        if underline_override is not None
        else bool(source_run.underline) if source_run is not None else False
    )
    if underline:
        u = _new_ordered(rpr, qn("w:u"), _RPR_CHILD_ORDER)
        u.set(qn("w:val"), "single")
    if text == "\t":
        etree.SubElement(run, qn("w:tab"))
        return
    text_element = etree.SubElement(run, qn("w:t"))
    if text[:1].isspace() or text[-1:].isspace():
        text_element.set(f"{{{_XML_NS}}}space", "preserve")
    text_element.text = text


def _best_source_run(runs: Iterable[SourceRun]) -> SourceRun | None:
    return next(iter(runs), None)


def _slot_replacement(
    slot: SourceFillSlot,
    project_facts: ProjectFacts,
) -> tuple[str, str] | None:
    for field in slot.allowed_fact_fields:
        fact = getattr(project_facts.fields, field.value)
        if fact.status != FactStatus.RESOLVED:
            continue
        if not is_resolved_value_type_valid(field, fact.resolved_value):
            continue
        method = "source_slot"
        if any(candidate.method == "derived_cross_reference" for candidate in fact.candidates):
            method = "derived_cross_reference"
        return value_text(fact.resolved_value), method
    return None


def _slot_replacement_for_insertion(
    slot: SourceFillSlot,
    project_facts: ProjectFacts,
) -> tuple[str, str] | None:
    """Return the exact text to insert while retaining a source suffix.

    Some forms reserve only a whitespace slot before a fixed unit, for
    example ``供货期        日历天``.  ProjectFacts stores the stable value
    ``90日历天``; insert only ``90`` when the source already supplies the
    matching unit so the output remains ``供货期 90 日历天``.
    """

    replacement = _slot_replacement(slot, project_facts)
    if replacement is None:
        return None
    value, method = replacement
    if slot.match_kind == "whitespace":
        suffix = (slot.suffix_text or "").lstrip()
        for unit in ("日历天", "个月", "天", "月", "年"):
            if value.endswith(unit) and suffix.startswith(unit):
                value = value[: -len(unit)]
                break
    return value, method


def _slot_key(slot: SourceFillSlot) -> str:
    return json.dumps(slot.source_locator.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def _slot_map(
    slots: Iterable[SourceFillSlot],
    project_facts: ProjectFacts,
) -> tuple[dict[str, list[SourceFillSlot]], list[dict[str, object]], list[str]]:
    by_locator: dict[str, list[SourceFillSlot]] = {}
    filled: list[dict[str, object]] = []
    substitutions: list[str] = []
    for slot in slots:
        by_locator.setdefault(_slot_key(slot), []).append(slot)
        if slot.font_name:
            _mapped, substituted = _font_name(slot.font_name)
            if substituted:
                marker = f"{slot.font_name} -> {_mapped}"
                if marker not in substitutions:
                    substitutions.append(marker)
        replacement = _slot_replacement_for_insertion(slot, project_facts)
        if replacement is None:
            continue
        value, method = replacement
        filled.append(
            {
                "slot_id": slot.slot_id,
                "field": [field.value for field in slot.allowed_fact_fields],
                "value": value,
                "source_page": slot.source_page,
                "source_locator": slot.source_locator.model_dump(mode="json"),
                "method": method,
                "original_text": slot.original_text,
            }
        )
    return by_locator, filled, substitutions


def _template_font_audit(
    template: SourceFormatTemplate,
) -> tuple[list[str], list[str]]:
    """Record every source font that needs repair or deterministic fallback."""

    substitutions: list[str] = []
    repairs: list[str] = []

    def record(run: SourceRun) -> None:
        source_name = (run.font_name or "").strip()
        if not source_name:
            return
        raw_name = (run.raw_font_name or "").strip()
        if raw_name and raw_name != source_name:
            marker = f"{raw_name} -> {source_name} (FONT_NAME_REPAIRED)"
            if marker not in repairs:
                repairs.append(marker)
        mapped_name, substituted = _font_name(source_name)
        if substituted:
            marker = f"{source_name} -> {mapped_name} (FONT_SUBSTITUTION_REQUIRED)"
            if marker not in substitutions:
                substitutions.append(marker)

    for page in template.source_pages:
        for paragraph in page.paragraphs:
            for run in paragraph.runs:
                record(run)
            for line in paragraph.lines:
                for span in line.spans:
                    record(
                        SourceRun(
                            text=span.text,
                            bbox=span.bbox,
                            font_name=repair_pdf_font_name(span.font_name),
                            raw_font_name=span.font_name,
                            font_size=span.font_size,
                        )
                    )
        for table in page.tables:
            for row in table.rows:
                for cell in row.cells:
                    for run in cell.runs:
                        record(run)
    return substitutions, repairs


def _replacement_ranges(
    text: str,
    slots: Iterable[SourceFillSlot],
    project_facts: ProjectFacts,
) -> list[tuple[int, int, str, SourceFillSlot]]:
    result: list[tuple[int, int, str, SourceFillSlot]] = []
    for slot in slots:
        if slot.text_start is None or slot.text_end is None:
            continue
        replacement = _slot_replacement_for_insertion(slot, project_facts)
        if replacement is None:
            continue
        start = max(0, min(len(text), int(slot.text_start)))
        end = max(start, min(len(text), int(slot.text_end)))
        if end <= start:
            continue
        result.append((start, end, replacement[0], slot))
    return sorted(result, key=lambda item: (item[0], item[1]))


def _append_replaced_run(
    parent: etree._Element,
    text: str,
    global_start: int,
    source_run: SourceRun,
    slots: list[SourceFillSlot],
    project_facts: ProjectFacts,
) -> None:
    global_end = global_start + len(text)
    # The previous helper operates on the container text, so use direct slot
    # coordinates here.  Slots crossing run boundaries are rare in PDF spans;
    # the overlap guard keeps the original source text if they are ambiguous.
    active = []
    for slot in slots:
        if slot.text_start is None or slot.text_end is None:
            continue
        replacement = _slot_replacement_for_insertion(slot, project_facts)
        if replacement is None:
            continue
        if int(slot.text_start) >= global_start and int(slot.text_end) <= global_end:
            active.append((int(slot.text_start), int(slot.text_end), replacement[0], slot))
    if not active:
        _append_run(parent, text, source_run)
        return
    cursor = global_start
    for start, end, replacement, slot in sorted(active):
        local_start = start - global_start
        local_end = end - global_start
        if local_start > cursor - global_start:
            _append_run(parent, text[cursor - global_start:local_start], source_run)
        _append_run(
            parent,
            replacement,
            source_run,
            underline_override=True if slot.match_kind == "underline" else None,
        )
        cursor = global_start + local_end
    if cursor < global_end:
        _append_run(parent, text[cursor - global_start:], source_run)


def _paragraph_lines(source_paragraph: SourceParagraph) -> list[tuple[str, list[SourceRun]]]:
    direct_text = "\n".join(line.text for line in source_paragraph.lines)
    # Use span-level runs only when their line stream accounts for the exact
    # source block text.  Otherwise a PDF's image-backed glyphs would cause
    # the reconstructed paragraph to lose source text.  The fallback still
    # retains the source paragraph and its known fill-slot coordinates.
    if source_paragraph.lines and direct_text.strip() == source_paragraph.text.strip():
        # PyMuPDF can expose text spans on one visual baseline as separate
        # ``lines`` when a form has a large horizontal gap (label, underline,
        # signature note).  Preserve the source newline as a one-character
        # tab separator so fill-slot offsets remain valid while the emitted
        # Word paragraph stays on the intended visual line.
        groups: list[list[object]] = []
        for line in source_paragraph.lines:
            if groups and abs(line.bbox[1] - groups[-1][0].bbox[1]) <= 2.5:
                groups[-1].append(line)
            else:
                groups.append([line])
        result: list[tuple[str, list[SourceRun]]] = []
        for group in groups:
            line_text_parts: list[str] = []
            line_runs: list[SourceRun] = []
            for line_index, line in enumerate(group):
                if line_index:
                    previous = group[line_index - 1]
                    previous_span = previous.spans[-1] if previous.spans else None
                    separator_bbox = (
                        previous.bbox[2],
                        line.bbox[1],
                        line.bbox[0],
                        line.bbox[3],
                    )
                    line_runs.append(
                        SourceRun(
                            text="\t",
                            bbox=separator_bbox,
                            font_name=(previous_span.font_name if previous_span else ""),
                            font_size=(previous_span.font_size if previous_span else 10.5),
                        )
                    )
                    line_text_parts.append("\t")
                for span in line.spans:
                    line_runs.append(_source_run(span))
                    line_text_parts.append(span.text)
            result.append(("".join(line_text_parts), line_runs))
        return result
    if source_paragraph.runs:
        # Table cells are represented by SourceCell.runs rather than full
        # SourceParagraph.lines. Reconstruct their visual lines from span
        # baselines when the source text contains explicit line breaks; this
        # preserves multi-line quotation/notes cells without flattening them
        # into one Word line.
        if "\n" in source_paragraph.text:
            groups: list[list[SourceRun]] = []
            for run in source_paragraph.runs:
                if groups and abs(run.bbox[1] - groups[-1][0].bbox[1]) <= 2.5:
                    groups[-1].append(run)
                else:
                    groups.append([run])
            if len(groups) > 1:
                grouped_text = "\n".join(
                    "".join(run.text for run in group)
                    for group in groups
                )
                if grouped_text.replace("\n", "") == source_paragraph.text.replace("\n", ""):
                    return [
                        ("".join(run.text for run in group), group)
                        for group in groups
                    ]
        return [(source_paragraph.text, source_paragraph.runs)]
    return [(source_paragraph.text, [])]


def _source_run(span) -> SourceRun:
    return SourceRun(
        text=span.text,
        bbox=span.bbox,
        font_name=repair_pdf_font_name(span.font_name),
        raw_font_name=span.font_name,
        font_size=span.font_size,
        bold=span.bold,
        italic=span.italic,
        underline=span.underline,
        color=span.color,
        source_order=span.source_order,
    )


def _paragraph_xml(
    source_paragraph: SourceParagraph,
    slots: list[SourceFillSlot],
    project_facts: ProjectFacts,
) -> etree._Element:
    paragraph = etree.Element(qn("w:p"))
    _set_textbox_paragraph_format(paragraph, source_paragraph)
    lines = _paragraph_lines(source_paragraph)
    global_start = 0
    for line_index, (line_text, line_runs) in enumerate(lines):
        if line_index:
            # A break is a run child in WordprocessingML.  LibreOffice also
            # renders a paragraph-level w:br, but desktop Word can reject the
            # whole package when it encounters that non-schema child.
            break_run = etree.SubElement(paragraph, qn("w:r"))
            etree.SubElement(break_run, qn("w:br"))
            global_start += 1
        cursor = global_start
        if line_runs:
            for source_run in line_runs:
                run_text = source_run.text
                _append_replaced_run(
                    paragraph,
                    run_text,
                    cursor,
                    source_run,
                    slots,
                    project_facts,
                )
                cursor += len(run_text)
        elif line_text:
            fallback = SourceRun(
                text=line_text,
                bbox=source_paragraph.bbox,
                font_name="宋体",
                font_size=10.5,
            )
            _append_replaced_run(
                paragraph,
                line_text,
                cursor,
                fallback,
                slots,
                project_facts,
            )
        global_start += len(line_text)
    return paragraph


def _table_cell_text_and_slots(
    cell: SourceCell,
    slots: list[SourceFillSlot],
    project_facts: ProjectFacts,
) -> tuple[str, list[SourceFillSlot]]:
    relevant = [
        slot for slot in slots
        if slot.table_index == cell.locator.table_index
        and slot.row_index == cell.row_index
        and slot.column_index == cell.column_index
    ]
    if not relevant:
        return cell.text, []
    text = cell.text
    if not text and len(relevant) == 1:
        replacement = _slot_replacement_for_insertion(relevant[0], project_facts)
        return (replacement[0] if replacement else text), []
    return text, relevant


def _clear_cell(cell) -> None:
    tc = cell._tc
    for child in list(tc):
        if child.tag != qn("w:tcPr"):
            tc.remove(child)
    etree.SubElement(tc, qn("w:p"))


def _append_cell_content(
    cell,
    source_cell: SourceCell,
    slots: list[SourceFillSlot],
    project_facts: ProjectFacts,
) -> None:
    _clear_cell(cell)
    tc = cell._tc
    existing_paragraph = next((child for child in tc if child.tag == qn("w:p")), None)
    if existing_paragraph is not None:
        tc.remove(existing_paragraph)
    text, embedded_slots = _table_cell_text_and_slots(source_cell, slots, project_facts)
    source_paragraph = SourceParagraph(
        paragraph_id=f"cell-{source_cell.locator.table_index}-{source_cell.row_index}-{source_cell.column_index}",
        page=source_cell.locator.page,
        bbox=source_cell.bbox or (0.0, 0.0, 10.0, 10.0),
        text=text,
        runs=source_cell.runs or [
            SourceRun(
                text=text,
                bbox=source_cell.bbox or (0.0, 0.0, 10.0, 10.0),
                font_name="宋体",
                font_size=10.5,
            )
        ],
        locator=source_cell.locator,
        alignment="center",
        line_spacing=0.0,
    )
    paragraph = _paragraph_xml(source_paragraph, embedded_slots, project_facts)
    tc.append(paragraph)
    tc_pr = tc.get_or_add_tcPr()
    v_align = tc_pr.first_child_found_in("w:vAlign")
    if v_align is None:
        v_align = _new_ordered(tc_pr, qn("w:vAlign"), _TCPR_CHILD_ORDER)
    v_align.set(qn("w:val"), "center")


def _set_cell_borders(cell, width: float) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = _new_ordered(tc_pr, qn("w:tcBorders"), _TCPR_CHILD_ORDER)
    size = str(max(2, min(16, int(round(max(0.25, width) * 8)))))
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = _new_ordered(
                borders,
                qn(f"w:{edge}"),
                _TC_BORDERS_CHILD_ORDER,
            )
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "000000")
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = _new_ordered(tc_pr, qn("w:tcMar"), _TCPR_CHILD_ORDER)
    for edge in ("top", "left", "bottom", "right"):
        element = margins.find(qn(f"w:{edge}"))
        if element is None:
            element = etree.SubElement(margins, qn(f"w:{edge}"))
        element.set(qn("w:w"), str(_twips(1.5)))
        element.set(qn("w:type"), "dxa")


def _set_row_height(row, height: float) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    height_element = tr_pr.find(qn("w:trHeight"))
    if height_element is None:
        height_element = _new_ordered(tr_pr, qn("w:trHeight"), _TRPR_CHILD_ORDER)
    height_element.set(qn("w:val"), str(max(1, _twips(height))))
    # atLeast protects long source text from being clipped by an approximate
    # PDF row rectangle.
    height_element.set(qn("w:hRule"), "atLeast")


def _table_columns(source_table: SourceTable) -> list[float]:
    columns = source_table.columns or max((len(row.cells) for row in source_table.rows), default=0)
    if columns <= 0:
        return []
    edges: set[float] = set()
    for row in source_table.rows:
        for cell in row.cells:
            if cell.bbox is not None:
                edges.add(round(cell.bbox[0], 2))
                edges.add(round(cell.bbox[2], 2))
    ordered_edges = sorted(edges)
    if len(ordered_edges) == columns + 1:
        values = [ordered_edges[i + 1] - ordered_edges[i] for i in range(columns)]
        if all(value > 0 for value in values):
            return values
    values = list(source_table.column_widths[:columns])
    if len(values) < columns:
        fallback = (source_table.bbox[2] - source_table.bbox[0]) / columns
        values.extend([fallback] * (columns - len(values)))
    total = sum(value for value in values)
    desired = max(1.0, source_table.bbox[2] - source_table.bbox[0])
    if total > 0 and abs(total - desired) > 0.5:
        values = [value * desired / total for value in values]
    return values


def _merge_ranges(table, source_table: SourceTable) -> None:
    for row_start, row_end, col_start, col_end in sorted(
        source_table.merged_cells,
        key=lambda item: (item[0], item[2], item[1], item[3]),
    ):
        if row_start == row_end and col_start == col_end:
            continue
        try:
            table.cell(row_start, col_start).merge(table.cell(row_end, col_end))
        except (IndexError, ValueError):
            # The source detector can expose overlapping rectangles for
            # complex merges.  Retain an editable rectangular table and report
            # the topology warning in the generation report.
            continue


def _merged_anchor(source_table: SourceTable, row: int, column: int) -> tuple[int, int]:
    for row_start, row_end, col_start, col_end in source_table.merged_cells:
        if row_start <= row <= row_end and col_start <= column <= col_end:
            return row_start, col_start
    return row, column


def _floating_table(
    document: Document,
    source_table: SourceTable,
    slots: list[SourceFillSlot],
    project_facts: ProjectFacts,
) -> object:
    columns = _table_columns(source_table)
    if not columns or not source_table.rows:
        return None
    table = document.add_table(rows=len(source_table.rows), cols=len(columns))
    table.autofit = False
    _set_floating_table_position(table, source_table)
    _set_table_grid(table, columns)
    _merge_ranges(table, source_table)
    for row_index, source_row in enumerate(source_table.rows):
        _set_row_height(
            table.rows[row_index],
            source_row.height or (
                source_table.row_heights[row_index]
                if row_index < len(source_table.row_heights)
                else 18.0
            ),
        )
        for column_index, source_cell in enumerate(source_row.cells[: len(columns)]):
            anchor_row, anchor_column = _merged_anchor(source_table, row_index, column_index)
            if (anchor_row, anchor_column) != (row_index, column_index):
                continue
            output_cell = table.cell(row_index, column_index)
            _append_cell_content(output_cell, source_cell, slots, project_facts)
            output_cell.width = Inches(max(0.05, columns[column_index] / 72.0))
            _set_cell_borders(output_cell, source_table.border_width)
    _set_table_grid(table, columns)
    return table


def _set_table_grid(table, columns: list[float]) -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_width = tbl_pr.first_child_found_in("w:tblW")
    if tbl_width is None:
        tbl_width = _new_ordered(tbl_pr, qn("w:tblW"), _TBLPR_CHILD_ORDER)
    tbl_width.set(qn("w:w"), str(_twips(sum(columns))))
    tbl_width.set(qn("w:type"), "dxa")
    layout = tbl_pr.first_child_found_in("w:tblLayout")
    if layout is None:
        layout = _new_ordered(tbl_pr, qn("w:tblLayout"), _TBLPR_CHILD_ORDER)
    layout.set(qn("w:type"), "fixed")
    grid = tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in columns:
        column = etree.SubElement(grid, qn("w:gridCol"))
        column.set(qn("w:w"), str(_twips(width)))


def _set_floating_table_position(table, source_table: SourceTable) -> None:
    tbl_pr = table._tbl.tblPr
    tblp = tbl_pr.first_child_found_in("w:tblpPr")
    if tblp is None:
        # CT_TblPr has a schema-ordered child sequence.  Appending tblpPr
        # after python-docx's tblW/tblLook is tolerated by LibreOffice but can
        # make desktop Word reject the package.  Insert it before the first
        # existing property so the normal tblpPr/tblW/tblLook order is kept.
        tblp = _new_ordered(tbl_pr, qn("w:tblpPr"), _TBLPR_CHILD_ORDER)
    tblp.set(qn("w:tblpX"), str(_twips(source_table.bbox[0])))
    tblp.set(qn("w:tblpY"), str(_twips(source_table.bbox[1])))
    tblp.set(qn("w:horzAnchor"), "page")
    tblp.set(qn("w:vertAnchor"), "page")
    tblp.set(qn("w:leftFromText"), "0")
    tblp.set(qn("w:rightFromText"), "0")
    tblp.set(qn("w:topFromText"), "0")
    tblp.set(qn("w:bottomFromText"), "0")


def _text_box(
    source_paragraph: SourceParagraph,
    slots: list[SourceFillSlot],
    project_facts: ProjectFacts,
    shape_id: int,
) -> etree._Element:
    drawing = etree.Element(qn("w:drawing"))
    anchor = etree.SubElement(
        drawing,
        f"{{{_WP_NS}}}anchor",
        nsmap={"wp": _WP_NS, "a": _A_NS, "wps": _WPS_NS},
    )
    for name, value in {
        "distT": "0",
        "distB": "0",
        "distL": "0",
        "distR": "0",
        "simplePos": "0",
        "relativeHeight": "1",
        "behindDoc": "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        anchor.set(name, value)
    x0, y0, x1, y1 = source_paragraph.bbox
    width = max(1.0, x1 - x0)
    lines = _paragraph_lines(source_paragraph)
    base_size = next(
        (run.font_size for _line, runs in lines for run in runs if run.font_size > 0),
        10.5,
    )
    line_height = source_paragraph.line_spacing + base_size * 1.05
    height = max(
        4.0,
        y1 - y0 + 2.0,
        line_height * max(1, len(lines)) + 2.0,
    )
    simple_pos = etree.SubElement(anchor, f"{{{_WP_NS}}}simplePos")
    simple_pos.set("x", "0")
    simple_pos.set("y", "0")
    position_h = etree.SubElement(anchor, f"{{{_WP_NS}}}positionH")
    position_h.set("relativeFrom", "page")
    etree.SubElement(position_h, f"{{{_WP_NS}}}posOffset").text = str(_emu(x0))
    position_v = etree.SubElement(anchor, f"{{{_WP_NS}}}positionV")
    position_v.set("relativeFrom", "page")
    etree.SubElement(position_v, f"{{{_WP_NS}}}posOffset").text = str(_emu(y0))
    extent = etree.SubElement(anchor, f"{{{_WP_NS}}}extent")
    extent.set("cx", str(_emu(width)))
    extent.set("cy", str(_emu(height)))
    effect = etree.SubElement(anchor, f"{{{_WP_NS}}}effectExtent")
    for side in ("l", "t", "r", "b"):
        effect.set(side, "0")
    etree.SubElement(anchor, f"{{{_WP_NS}}}wrapNone")
    doc_pr = etree.SubElement(anchor, f"{{{_WP_NS}}}docPr")
    doc_pr.set("id", str(shape_id))
    doc_pr.set("name", f"Source text {shape_id}")
    c_nv = etree.SubElement(anchor, f"{{{_WP_NS}}}cNvGraphicFramePr")
    etree.SubElement(c_nv, f"{{{_A_NS}}}graphicFrameLocks").set("noChangeAspect", "1")
    graphic = etree.SubElement(anchor, f"{{{_A_NS}}}graphic")
    graphic_data = etree.SubElement(graphic, f"{{{_A_NS}}}graphicData")
    graphic_data.set("uri", _WPS_URI)
    shape = etree.SubElement(graphic_data, f"{{{_WPS_NS}}}wsp")
    etree.SubElement(shape, f"{{{_WPS_NS}}}cNvSpPr").set("txBox", "1")
    sp_pr = etree.SubElement(shape, f"{{{_WPS_NS}}}spPr")
    xfrm = etree.SubElement(sp_pr, f"{{{_A_NS}}}xfrm")
    off = etree.SubElement(xfrm, f"{{{_A_NS}}}off")
    off.set("x", "0")
    off.set("y", "0")
    ext = etree.SubElement(xfrm, f"{{{_A_NS}}}ext")
    ext.set("cx", str(_emu(width)))
    ext.set("cy", str(_emu(height)))
    prst_geom = etree.SubElement(sp_pr, f"{{{_A_NS}}}prstGeom")
    prst_geom.set("prst", "rect")
    etree.SubElement(prst_geom, f"{{{_A_NS}}}avLst")
    etree.SubElement(sp_pr, f"{{{_A_NS}}}noFill")
    line = etree.SubElement(sp_pr, f"{{{_A_NS}}}ln")
    etree.SubElement(line, f"{{{_A_NS}}}noFill")
    textbox = etree.SubElement(shape, f"{{{_WPS_NS}}}txbx")
    content = etree.SubElement(textbox, qn("w:txbxContent"))
    content.append(_paragraph_xml(source_paragraph, slots, project_facts))
    body_pr = etree.SubElement(shape, f"{{{_WPS_NS}}}bodyPr")
    for attr in ("lIns", "tIns", "rIns", "bIns"):
        body_pr.set(attr, "0")
    body_pr.set("wrap", "none")
    etree.SubElement(body_pr, f"{{{_A_NS}}}noAutofit")
    return drawing


def _page_canvas(
    document: Document,
    page: SourcePage,
    *,
    add_page_break: bool,
) -> object:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = 0
    paragraph.paragraph_format.space_after = 0
    paragraph.paragraph_format.line_spacing = 0.1
    if add_page_break:
        paragraph.add_run().add_break(WD_BREAK.PAGE)
    return paragraph


def _floating_line(source_line: SourceLine, shape_id: int) -> etree._Element:
    """Emit a thin editable DrawingML rule at its source-page coordinates."""

    drawing = etree.Element(qn("w:drawing"))
    anchor = etree.SubElement(
        drawing,
        f"{{{_WP_NS}}}anchor",
        nsmap={"wp": _WP_NS, "a": _A_NS, "wps": _WPS_NS},
    )
    for name, value in {
        "distT": "0",
        "distB": "0",
        "distL": "0",
        "distR": "0",
        "simplePos": "0",
        "relativeHeight": "2",
        "behindDoc": "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        anchor.set(name, value)
    x0, y0, x1, y1 = source_line.bbox
    width = max(1.0, x1 - x0)
    height = max(0.6, y1 - y0, source_line.width)
    simple_pos = etree.SubElement(anchor, f"{{{_WP_NS}}}simplePos")
    simple_pos.set("x", "0")
    simple_pos.set("y", "0")
    position_h = etree.SubElement(anchor, f"{{{_WP_NS}}}positionH")
    position_h.set("relativeFrom", "page")
    etree.SubElement(position_h, f"{{{_WP_NS}}}posOffset").text = str(_emu(x0))
    position_v = etree.SubElement(anchor, f"{{{_WP_NS}}}positionV")
    position_v.set("relativeFrom", "page")
    etree.SubElement(position_v, f"{{{_WP_NS}}}posOffset").text = str(_emu(y0))
    extent = etree.SubElement(anchor, f"{{{_WP_NS}}}extent")
    extent.set("cx", str(_emu(width)))
    extent.set("cy", str(_emu(height)))
    effect = etree.SubElement(anchor, f"{{{_WP_NS}}}effectExtent")
    for side in ("l", "t", "r", "b"):
        effect.set(side, "0")
    etree.SubElement(anchor, f"{{{_WP_NS}}}wrapNone")
    doc_pr = etree.SubElement(anchor, f"{{{_WP_NS}}}docPr")
    doc_pr.set("id", str(shape_id))
    doc_pr.set("name", f"Source rule {shape_id}")
    c_nv = etree.SubElement(anchor, f"{{{_WP_NS}}}cNvGraphicFramePr")
    etree.SubElement(c_nv, f"{{{_A_NS}}}graphicFrameLocks").set("noChangeAspect", "1")
    graphic = etree.SubElement(anchor, f"{{{_A_NS}}}graphic")
    graphic_data = etree.SubElement(graphic, f"{{{_A_NS}}}graphicData")
    graphic_data.set("uri", _WPS_URI)
    shape = etree.SubElement(graphic_data, f"{{{_WPS_NS}}}wsp")
    etree.SubElement(shape, f"{{{_WPS_NS}}}cNvSpPr")
    sp_pr = etree.SubElement(shape, f"{{{_WPS_NS}}}spPr")
    xfrm = etree.SubElement(sp_pr, f"{{{_A_NS}}}xfrm")
    off = etree.SubElement(xfrm, f"{{{_A_NS}}}off")
    off.set("x", "0")
    off.set("y", "0")
    ext = etree.SubElement(xfrm, f"{{{_A_NS}}}ext")
    ext.set("cx", str(_emu(width)))
    ext.set("cy", str(_emu(height)))
    prst_geom = etree.SubElement(sp_pr, f"{{{_A_NS}}}prstGeom")
    prst_geom.set("prst", "rect")
    etree.SubElement(prst_geom, f"{{{_A_NS}}}avLst")
    etree.SubElement(sp_pr, f"{{{_A_NS}}}noFill")
    line = etree.SubElement(sp_pr, f"{{{_A_NS}}}ln")
    line.set("w", str(_emu(max(0.25, source_line.width))))
    solid_fill = etree.SubElement(line, f"{{{_A_NS}}}solidFill")
    etree.SubElement(solid_fill, f"{{{_A_NS}}}srgbClr").set(
        "val", _color_hex(source_line.color) or "000000"
    )
    etree.SubElement(line, f"{{{_A_NS}}}prstDash").set("val", "solid")
    return drawing


def _page_text_and_table_maps(page: SourcePage):
    paragraphs = {index: paragraph for index, paragraph in enumerate(page.paragraphs)}
    tables = {index: table for index, table in enumerate(page.tables)}
    return paragraphs, tables


def _source_textbox_paragraph_count(document: Document) -> int:
    return sum(1 for _element in document.element.body.iter(qn("w:txbxContent")))


def build_source_format_docx(
    project_facts: ProjectFacts,
    template: SourceFormatTemplate,
    output_path: str | Path,
    *,
    generation_report_path: str | Path | None = None,
) -> tuple[Path, dict[str, object]]:
    """Build a source-page-positioned editable DOCX and its generation audit."""

    if not template.source_pages:
        raise ValueError("SourceFormatTemplate has no source pages")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    first_page = template.source_pages[0]
    section = document.sections[0]
    section.page_width = Inches(first_page.width / 72.0)
    section.page_height = Inches(first_page.height / 72.0)
    section.top_margin = Inches(0)
    section.bottom_margin = Inches(0)
    section.left_margin = Inches(0)
    section.right_margin = Inches(0)
    section.header_distance = Inches(0)
    section.footer_distance = Inches(0)
    normal = document.styles["Normal"]
    normal.font.name = "SimSun"
    normal.font.color.rgb = None
    normal.paragraph_format.space_before = 0
    normal.paragraph_format.space_after = 0
    normal.paragraph_format.line_spacing = 0.1
    document.core_properties.title = "基础投标文件"
    document.core_properties.subject = "format_source=SOURCE_DOCUMENT"
    document.core_properties.keywords = "format_source=SOURCE_DOCUMENT; source_format_fidelity=round4"

    slot_map, filled_slots, slot_substitutions = _slot_map(template.fill_slots, project_facts)
    substitutions, font_repairs = _template_font_audit(template)
    substitutions = sorted(set(substitutions + slot_substitutions))
    shape_id = 1024
    table_count = 0
    page_textboxes: list[int] = []
    table_topology_warnings: list[str] = []
    current_width = first_page.width
    current_height = first_page.height
    for page_index, page in enumerate(template.source_pages):
        page_break_required = page_index > 0
        dimensions_changed = (
            abs(page.width - current_width) > 0.1
            or abs(page.height - current_height) > 0.1
        )
        if page_index and dimensions_changed:
            # Real cases use A4 portrait/landscape pages.  A section break is
            # required when page dimensions change; it is inserted before the
            # page canvas and keeps the page-local absolute coordinates valid.
            section = document.add_section()
            section.page_width = Inches(page.width / 72.0)
            section.page_height = Inches(page.height / 72.0)
            section.top_margin = Inches(0)
            section.bottom_margin = Inches(0)
            section.left_margin = Inches(0)
            section.right_margin = Inches(0)
            section.header_distance = Inches(0)
            section.footer_distance = Inches(0)
            # add_section() with its default NEW_PAGE start already advances
            # to the next source page.  A second explicit page break would
            # create an unintentional blank page.
            page_break_required = False
            current_width = page.width
            current_height = page.height
        page_paragraphs, page_tables = _page_text_and_table_maps(page)
        page_started = False
        for item in page.elements:
            if item.type == "paragraph":
                source_paragraph = page_paragraphs.get(item.index)
                if source_paragraph is None:
                    continue
                slots = slot_map.get(_slot_key_for_locator(source_paragraph.locator), [])
                canvas = _page_canvas(
                    document,
                    page,
                    add_page_break=page_break_required if not page_started else False,
                )
                page_started = True
                page_break_required = False
                run = canvas.add_run()
                run._r.append(_text_box(source_paragraph, slots, project_facts, shape_id))
                shape_id += 1
                page_textboxes.append(page.page)
            elif item.type == "table":
                source_table = page_tables.get(item.index)
                if source_table is None:
                    continue
                if not page_started:
                    _page_canvas(document, page, add_page_break=page_break_required)
                    page_started = True
                    page_break_required = False
                _floating_table(document, source_table, template.fill_slots, project_facts)
                table_count += 1
                if any(
                    row_end > row_start or col_end > col_start
                    for row_start, row_end, col_start, col_end in source_table.merged_cells
                ):
                    table_topology_warnings.append(
                        f"page={source_table.page},table={source_table.table_index}: merge topology reconstructed from repeated cell rectangles"
                    )
        for source_line in page.lines:
            if not page_started:
                host = _page_canvas(document, page, add_page_break=page_break_required)
                page_started = True
                page_break_required = False
            else:
                host = document.add_paragraph()
                host.paragraph_format.space_before = 0
                host.paragraph_format.space_after = 0
                host.paragraph_format.line_spacing = 0.1
            host.add_run()._r.append(_floating_line(source_line, shape_id))
            shape_id += 1
        if not page_started:
            # Preserve intentionally blank source pages in the generated
            # document rather than collapsing them out of the page sequence.
            _page_canvas(document, page, add_page_break=page_break_required)

    document.save(output)
    reopened = Document(output)
    if not reopened.paragraphs:
        raise ValueError("Source-format DOCX has no body paragraphs")
    report: dict[str, object] = {
        "format_source": "SOURCE_DOCUMENT",
        "source_heading": template.source_heading,
        "source_page_count": len(template.source_pages),
        "source_table_count": template.source_table_count,
        "generated_table_count": len(reopened.tables),
        "generated_body_paragraph_count": len(reopened.paragraphs),
        "generated_textbox_count": _source_textbox_paragraph_count(reopened),
        "source_line_count": sum(len(page.lines) for page in template.source_pages),
        "generated_line_count": sum(
            1
            for element in reopened.element.body.iter(f"{{{_WP_NS}}}docPr")
            if (element.get("name") or "").startswith("Source rule")
        ),
        "fill_slots_detected": len(template.fill_slots),
        "fill_slots_filled": len(filled_slots),
        "fill_slots_left_blank": max(0, len(template.fill_slots) - len(filled_slots)),
        "filled_slots": filled_slots,
        "font_substitutions": substitutions,
        "font_repairs": font_repairs,
        "layout_warnings": [*template.layout_warnings, *table_topology_warnings],
        "source_page_numbers": [page.page for page in template.source_pages],
    }
    if generation_report_path is not None:
        report_path = Path(generation_report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output, report


def _slot_key_for_locator(locator) -> str:
    return json.dumps(locator.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


__all__ = ["build_source_format_docx"]
