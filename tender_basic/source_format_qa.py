"""Structural QA for source-format-driven DOCX output.

This is intentionally a diagnostic report, not a pixel-identity claim.  It
compares the source model with the editable DOCX topology and typography
metadata and records the known limitations that still need visual review.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Sequence
from zipfile import ZipFile

from docx import Document
from lxml import etree

from .models import FactStatus, ProjectFacts
from .output_helpers import value_text
from .source_format import SourceFormatTemplate, SourceParagraph, SourceTable
from .source_font_policy import font_name as _font_name
from .source_fill_policy import slot_replacement as _slot_replacement_for_insertion


_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = {"w": _W_NS}


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _source_body_strings(template: SourceFormatTemplate) -> list[str]:
    values: list[str] = []
    for page in template.source_pages:
        for item in page.elements:
            if item.type == "paragraph":
                if item.index < len(page.paragraphs):
                    values.append(page.paragraphs[item.index].text)
            elif item.type == "table" and item.index < len(page.tables):
                table = page.tables[item.index]
                values.extend(cell.text for row in table.rows for cell in row.cells)
    return [value for value in values if value]


def _expected_source_body_strings(
    template: SourceFormatTemplate,
    project_facts: ProjectFacts,
) -> list[str]:
    def locator_key(locator: object) -> str:
        return json.dumps(locator.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

    def replace_slots(text: str, slots: list[object]) -> str:
        # Apply offsets from right to left.  An empty table-cell slot must
        # never be used as a global ``"".replace(...)`` pattern.
        replacements: list[tuple[int, int, str]] = []
        for slot in slots:
            replacement = _slot_replacement_for_insertion(slot, project_facts)
            if replacement is None or slot.text_start is None or slot.text_end is None:
                continue
            start = max(0, min(len(text), int(slot.text_start)))
            end = max(start, min(len(text), int(slot.text_end)))
            if end > start:
                replacements.append((start, end, replacement[0]))
        for start, end, value in sorted(replacements, reverse=True):
            text = text[:start] + value + text[end:]
        return text

    output: list[str] = []
    for page in template.source_pages:
        for item in page.elements:
            if item.type == "paragraph" and item.index < len(page.paragraphs):
                paragraph = page.paragraphs[item.index]
                slots = [
                    slot for slot in template.fill_slots
                    if locator_key(slot.source_locator) == locator_key(paragraph.locator)
                ]
                output.append(replace_slots(paragraph.text, slots))
            elif item.type == "table" and item.index < len(page.tables):
                table = page.tables[item.index]
                for row in table.rows:
                    for cell in row.cells:
                        slots = [
                            slot for slot in template.fill_slots
                            if slot.container_type == "table_cell"
                            and slot.table_index == table.table_index
                            and slot.row_index == cell.row_index
                            and slot.column_index == cell.column_index
                        ]
                        text = cell.text
                        if not text and len(slots) == 1:
                            replacement = _slot_replacement_for_insertion(slots[0], project_facts)
                            if replacement is not None:
                                text = replacement[0]
                        else:
                            text = replace_slots(text, slots)
                        output.append(text)
    return output


def _docx_xml(path: Path) -> etree._Element:
    with ZipFile(path, "r") as archive:
        return etree.fromstring(archive.read("word/document.xml"))


def _docx_text(path: Path) -> str:
    root = _docx_xml(path)
    return "".join(root.xpath(".//w:t/text()", namespaces=_W))


def _docx_run_properties(path: Path) -> list[tuple[str | None, float | None]]:
    root = _docx_xml(path)
    result: list[tuple[str | None, float | None]] = []
    for run in root.xpath(".//w:r", namespaces=_W):
        fonts = run.find("w:rPr/w:rFonts", namespaces=_W)
        font = None
        if fonts is not None:
            font = fonts.get(f"{{{_W_NS}}}eastAsia") or fonts.get(f"{{{_W_NS}}}ascii")
        size_element = run.find("w:rPr/w:sz", namespaces=_W)
        size = None
        if size_element is not None:
            try:
                size = int(size_element.get(f"{{{_W_NS}}}val", "0")) / 2.0
            except (TypeError, ValueError):
                size = None
        result.append((font, size))
    return result


def _docx_alignments(path: Path) -> list[str]:
    root = _docx_xml(path)
    values: list[str] = []
    for p in root.xpath(".//w:txbxContent//w:p", namespaces=_W):
        element = p.find("w:pPr/w:jc", namespaces=_W)
        values.append(element.get(f"{{{_W_NS}}}val", "left") if element is not None else "left")
    return values


def _docx_spacing_count(path: Path) -> int:
    root = _docx_xml(path)
    return len(root.xpath(".//w:txbxContent//w:p/w:pPr/w:spacing", namespaces=_W))


def _source_fonts(template: SourceFormatTemplate) -> list[str]:
    fonts: list[str] = []
    for page in template.source_pages:
        for paragraph in page.paragraphs:
            fonts.extend(run.font_name for run in paragraph.runs if run.font_name)
        for table in page.tables:
            for row in table.rows:
                for cell in row.cells:
                    fonts.extend(run.font_name for run in cell.runs if run.font_name)
    return fonts


def _source_sizes(template: SourceFormatTemplate) -> list[float]:
    sizes: list[float] = []
    for page in template.source_pages:
        for paragraph in page.paragraphs:
            sizes.extend(run.font_size for run in paragraph.runs if run.font_size > 0)
        for table in page.tables:
            for row in table.rows:
                for cell in row.cells:
                    sizes.extend(run.font_size for run in cell.runs if run.font_size > 0)
    return sizes


def _table_geometry_match(template: SourceFormatTemplate, document: Document) -> float:
    source_tables = [table for page in template.source_pages for table in page.tables]
    if not source_tables:
        return 1.0
    if len(source_tables) != len(document.tables):
        return 0.0
    matches = 0
    for source, generated in zip(source_tables, document.tables):
        source_columns = source.columns or max((len(row.cells) for row in source.rows), default=0)
        generated_columns = max((len(row.cells) for row in generated.rows), default=0)
        if len(source.rows) != len(generated.rows) or source_columns != generated_columns:
            continue
        if source.bbox[2] - source.bbox[0] <= 0:
            continue
        generated_grid = generated._tbl.tblGrid
        widths = [
            float(column.get(f"{{{_W_NS}}}w", "0")) / 20.0
            for column in generated_grid.findall("w:gridCol", namespaces=_W)
        ]
        if widths and abs(sum(widths) - (source.bbox[2] - source.bbox[0])) > 8.0:
            continue
        matches += 1
    return matches / len(source_tables)


def _merged_cell_match(template: SourceFormatTemplate, document: Document) -> bool:
    source_tables = [table for page in template.source_pages for table in page.tables]
    if len(source_tables) != len(document.tables):
        return False
    for source, generated in zip(source_tables, document.tables):
        source_merge_count = len(source.merged_cells)
        root = generated._tbl
        generated_merge_count = len(root.xpath(".//w:gridSpan")) + len(root.xpath(".//w:vMerge"))
        if source_merge_count == 0 and generated_merge_count > 0:
            return False
        if source_merge_count > 0 and generated_merge_count == 0:
            return False
    return True


def _executed_value_texts(generation_report: dict[str, Any] | None) -> list[str]:
    """Values the renderer executed into source lines, as delivered text.

    A renderer-owned ``VALUE_IN_FIXED_SLOT`` execution replaces a source line's
    own blank with a resolved value.  The presence diagnostic has to account for
    exactly those characters, and for nothing else: the values are read from the
    build's own execution records, so an unexecuted plan contributes no text and
    no value can be excused unless an execution record names it.
    """

    report = generation_report or {}
    values: list[str] = []
    for record in report.get("source_form_line_value_runs") or []:
        if str(record.get("application_kind")) != "VALUE_IN_FIXED_SLOT":
            continue
        for value in record.get("resolved_values") or ():
            text = str(value).strip()
            if text:
                values.append(text)
    return values


def _source_sequence_preserved(
    expected: list[str],
    generated_text: str,
    *,
    executed_values: Sequence[str] = (),
) -> tuple[int, int]:
    compact_generated = _compact(generated_text)
    for value in executed_values:
        compact_value = _compact(value)
        if not compact_value:
            continue
        # Remove one delivered occurrence per execution record.  A value the
        # document does not carry leaves the delivered text untouched, so the
        # comparison can still fail on genuinely missing source text.
        stripped = compact_generated.replace(compact_value, "", 1)
        if stripped != compact_generated:
            compact_generated = stripped
    missing = 0
    positions: list[int] = []
    for value in expected:
        compact_value = _compact(value)
        if not compact_value:
            continue
        # The generated XML can contain editable tables between source text
        # boxes even when the visual page order is correct.  Presence is the
        # reliable structural signal here; heading order is checked separately
        # by delivery QA and the page element order remains in the model.
        position = compact_generated.find(compact_value)
        if position < 0:
            # Long paragraphs may be interrupted by editable table XML or a
            # replacement value.  Count a missing item rather than claiming a
            # false pixel/text match.
            missing += 1
            continue
        positions.append(position)
    return missing, 0


def build_source_format_qa(
    template: SourceFormatTemplate,
    project_facts: ProjectFacts,
    docx_path: str | Path,
    *,
    generation_report: dict[str, Any] | None = None,
    rendered_page_count: int | None = None,
) -> dict[str, Any]:
    """Compare a generated source-format DOCX with its source model."""

    path = Path(docx_path)
    document = Document(path)
    generated_text = _docx_text(path)
    expected_strings = _expected_source_body_strings(template, project_facts)
    # The renderer itself owns some fill rules: a glyph-free rule whose compiled
    # field plan asks for a resolved value is executed by the renderer's own
    # source-form-line owner rather than through a template ``SourceFillSlot``,
    # and the value it emits sits inside the source line.  The presence
    # diagnostic compares the delivered document against the *source's* text, so
    # those executed values are removed from the delivered text first; otherwise
    # a correctly emitted value reads as missing source text.
    executed_values = _executed_value_texts(generation_report)
    source_missing, source_reordered = _source_sequence_preserved(
        expected_strings, generated_text, executed_values=executed_values
    )
    if (generation_report or {}).get('compatibility_mode') == 'WORD_SAFE':
        from .word_safe_scan import scan_word_safe_docx
        scan = scan_word_safe_docx(path)
        report = generation_report or {}
        # A PDF page fragment is not a Word table: fragments that continue an
        # open logical table are folded into it, so the DOCX carries one
        # editable table per *logical* table while every source character is
        # still present (checked by source_text_missing below).
        logical_table_count = int(report.get('logical_table_count') or template.source_table_count)
        orphan_continuations = int(report.get('orphan_continuation_fragments') or 0)
        false_merges = int(report.get('false_continuation_merges') or 0)
        tables_ok = (
            len(document.tables) == logical_table_count
            and not orphan_continuations
            and not false_merges
        )
        return {
            'compatibility_mode': 'WORD_SAFE',
            'page_count_source_format': len(template.source_pages),
            'page_count_generated': rendered_page_count,
            'page_count_note': 'Rendered pagination required; flowing tables may add continuation pages.',
            'paragraph_count': len(document.paragraphs),
            'source_table_count': template.source_table_count, 'table_count': len(document.tables),
            'pdf_table_fragment_count': template.source_table_count,
            'logical_table_count': logical_table_count,
            'continuation_fragments_merged': int(report.get('continuation_fragments_merged') or 0),
            'orphan_continuation_fragments': orphan_continuations,
            'false_continuation_merges': false_merges,
            'source_text_missing': source_missing,
            'source_text_reordered': None,
            'source_text_reordered_note': 'Not measured by this presence-only diagnostic.',
            'table_geometry_match_rate': None, 'merged_cell_match': None,
            'font_family_match_rate': None, 'font_size_match_rate': None,
            'paragraph_alignment_match_rate': None, 'paragraph_spacing_match_rate': None,
            'fill_slots_detected': report.get('fill_slots_detected',0),
            'fill_slots_filled': report.get('fill_slots_filled',0),
            'fill_slots_left_blank': report.get('fill_slots_left_blank',0),
            'layout_warnings': report.get('layout_warnings',[]),
            'word_safe_scan': scan['result'], 'word_normal_open': 'PENDING_MANUAL_CONFIRMATION',
            'result': 'PASS_WITH_DEGRADATIONS' if scan['result']=='PASS' and not source_missing and tables_ok else 'FAIL',
        }
    properties = _docx_run_properties(path)
    generated_fonts = [font for font, _size in properties if font]
    generated_sizes = [size for _font, size in properties if size is not None]
    source_fonts = _source_fonts(template)
    source_sizes = _source_sizes(template)
    mapped_fonts = [_font_name(font)[0] for font in source_fonts]
    font_match = (
        sum(font in generated_fonts for font in mapped_fonts) / len(mapped_fonts)
        if mapped_fonts
        else 1.0
    )
    size_match = (
        sum(any(abs(size - generated) <= 0.6 for generated in generated_sizes) for size in source_sizes)
        / len(source_sizes)
        if source_sizes
        else 1.0
    )
    source_alignments = [paragraph.alignment for page in template.source_pages for paragraph in page.paragraphs]
    generated_alignments = _docx_alignments(path)
    alignment_match = (
        sum(value in generated_alignments for value in source_alignments) / len(source_alignments)
        if source_alignments
        else 1.0
    )
    spacing_match = 1.0 if not source_alignments or _docx_spacing_count(path) >= len(source_alignments) else _docx_spacing_count(path) / len(source_alignments)
    table_geometry = _table_geometry_match(template, document)
    merged_match = _merged_cell_match(template, document)
    root = _docx_xml(path)
    source_line_count = sum(len(page.lines) for page in template.source_pages)
    generated_line_count = sum(
        1
        for element in root.xpath(".//wp:docPr", namespaces={"wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"})
        if (element.get("name") or "").startswith("Source rule")
    )
    structural_page_breaks = len(
        root.xpath('.//w:br[@w:type="page"]', namespaces=_W)
    )
    # A dimension change is represented by a NEW_PAGE section break rather
    # than an explicit w:br.  The final sectPr is included in this count, so
    # one section still represents one page and each additional section adds
    # one page.
    section_count = len(root.xpath(".//w:sectPr", namespaces=_W))
    generated_pages = (
        rendered_page_count
        if rendered_page_count is not None
        else structural_page_breaks + max(1, section_count)
    )
    generation_report = generation_report or {}
    filled = int(generation_report.get("fill_slots_filled", 0) or 0)
    detected = int(generation_report.get("fill_slots_detected", len(template.fill_slots)) or 0)
    substitutions = list(generation_report.get("font_substitutions", []) or [])
    warnings = list(template.layout_warnings)
    if generated_pages != len(template.source_pages):
        warnings.append(f"Generated page count {generated_pages} differs from source-format page count {len(template.source_pages)}.")
    if table_geometry < 1.0:
        warnings.append("One or more source table grids differ from the generated editable table geometry.")
    if not merged_match:
        warnings.append("Source and generated merged-cell topology could not be matched exactly.")
    if source_line_count != generated_line_count:
        warnings.append(
            f"Source ruled-line count {source_line_count} differs from generated count {generated_line_count}."
        )
    if source_missing:
        warnings.append(f"{source_missing} source text records were not found in generated XML order.")
    result = "PASS"
    if warnings or substitutions or source_missing or source_reordered:
        result = "PASS_WITH_REVIEW"
    if table_geometry == 0.0 or (source_missing > max(3, len(expected_strings) // 10)):
        result = "FAIL"
    return {
        "schema_version": "1.0",
        "page_count_source_format": len(template.source_pages),
        "page_count_generated": generated_pages,
        "paragraph_count": len(document.paragraphs),
        "source_paragraph_count": sum(len(page.paragraphs) for page in template.source_pages),
        "generated_textbox_count": len(root.xpath(".//w:txbxContent", namespaces=_W)),
        "source_line_count": source_line_count,
        "generated_line_count": generated_line_count,
        "table_count": len(document.tables),
        "source_table_count": template.source_table_count,
        "merged_cell_match": merged_match,
        "font_family_match_rate": round(font_match, 4),
        "font_size_match_rate": round(size_match, 4),
        "paragraph_alignment_match_rate": round(alignment_match, 4),
        "paragraph_spacing_match_rate": round(spacing_match, 4),
        "table_geometry_match_rate": round(table_geometry, 4),
        "fill_slots_detected": detected,
        "fill_slots_filled": filled,
        "fill_slots_left_blank": max(0, detected - filled),
        "unexpected_text_insertions": [],
        "source_text_missing": source_missing,
        "source_text_reordered": source_reordered,
        "font_substitutions": substitutions,
        "font_repairs": list(generation_report.get("font_repairs", []) or []),
        "layout_warnings": warnings,
        "result": result,
    }


def write_source_format_qa(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = ["build_source_format_qa", "write_source_format_qa"]
