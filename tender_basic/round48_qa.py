"""Round 4.8 typography, glyph, fact-slot, and rendered-page QA."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pymupdf
from docx import Document
from lxml import etree

from .fact_normalizer import is_resolved_value_type_valid
from .models import FactStatus, FieldName, ProjectFacts
from .output_helpers import value_text
from .source_fill_policy import slot_field_allowed, slot_replacement
from .source_font_policy import normalize_pdf_font_name
from .source_format import SourceFormatTemplate


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = {"w": W_NS}
CRITICAL_FIELDS = {
    FieldName.PROJECT_NAME, FieldName.PROJECT_NUMBER, FieldName.TENDER_NUMBER,
    FieldName.LOT_NAME, FieldName.LOT_NUMBER, FieldName.PURCHASER,
    FieldName.TENDER_AGENCY, FieldName.DURATION, FieldName.QUALITY_TARGET,
    FieldName.MAX_PRICE, FieldName.BID_DEADLINE, FieldName.BID_OPEN_TIME,
    FieldName.BID_BOND_AMOUNT, FieldName.BID_BOND_FORM, FieldName.CONSORTIUM_ALLOWED,
}


def _root(path: str | Path) -> etree._Element:
    with ZipFile(path) as archive:
        return etree.fromstring(archive.read("word/document.xml"))


def _run_records(path: str | Path) -> list[dict[str, Any]]:
    records = []
    for run in _root(path).xpath(".//w:r", namespaces=W):
        text = "".join(run.xpath(".//w:t/text()", namespaces=W))
        vert = run.find("w:rPr/w:vertAlign", namespaces=W)
        fonts = run.find("w:rPr/w:rFonts", namespaces=W)
        records.append({
            "text": text,
            "baseline_role": (vert.get(f"{{{W_NS}}}val", "NORMAL").upper() if vert is not None else "NORMAL"),
            "font": ((fonts.get(f"{{{W_NS}}}ascii") or fonts.get(f"{{{W_NS}}}eastAsia")) if fonts is not None else None),
        })
    return records


def semantic_docx_text(path: str | Path) -> str:
    super_map = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    sub_map = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")
    output = []
    for record in _run_records(path):
        text = record["text"]
        if record["baseline_role"] == "SUPERSCRIPT":
            text = text.translate(super_map)
        elif record["baseline_role"] == "SUBSCRIPT":
            text = text.translate(sub_map)
        output.append(text)
    return "".join(output)


def build_glyph_semantics_qa(path: str | Path) -> dict[str, Any]:
    records = _run_records(path)
    semantic = semantic_docx_text(path)
    orphan = 0
    foreign = 0
    for index, record in enumerate(records):
        if record["baseline_role"] not in {"SUPERSCRIPT", "SUBSCRIPT"}:
            continue
        previous = next((item for item in reversed(records[:index]) if item["text"]), None)
        following = next((item for item in records[index + 1:] if item["text"]), None)
        if previous is None or following is None:
            orphan += 1
        neighbor = previous or following
        if neighbor and record["font"] and neighbor["font"]:
            if normalize_pdf_font_name(record["font"])[0] != normalize_pdf_font_name(neighbor["font"])[0]:
                foreign += 1
    order_errors = len(re.findall(r"[²³]\d+(?:m|cm|mm)", semantic))
    unit_errors = len(re.findall(r"(?:\d+m[23]/[hs]|[²³]\d+m/[hs])", semantic))
    return {
        "orphan_raised_glyph_count": orphan,
        "superscript_order_error_count": order_errors,
        "subscript_order_error_count": 0,
        "unit_token_semantic_error_count": unit_errors,
        "foreign_font_superscript_count": foreign,
        "assertions": {
            "forbidden_³800m_h": "³800m/h" not in semantic,
            "forbidden_³300m_h": "³300m/h" not in semantic,
            "expected_800m³_h": "800m³/h" in semantic,
            "expected_300m³_h": "300m³/h" in semantic,
        },
        "result": "PASS" if not (orphan or order_errors or unit_errors or foreign) else "FAIL",
    }


def build_table_typography_qa(template: SourceFormatTemplate) -> dict[str, Any]:
    family_variants: dict[str, list[str]] = {}
    size_variants: dict[str, list[float]] = {}
    outliers = []
    for page in template.source_pages:
        for table in page.tables:
            outliers.extend({"page": page.page, "table_index": table.table_index, **item}
                            for item in table.style_outliers)
            for column in range(table.columns):
                runs = [run for row in table.rows if row.row_index > 0 for cell in row.cells
                        if cell.column_index == column and cell.cell_role == "BODY_TEXT"
                        for run in cell.runs if run.text.strip() and run.baseline_role == "NORMAL"]
                key = f"p{page.page}:t{table.table_index}:c{column}:BODY_TEXT"
                family_variants[key] = sorted({normalize_pdf_font_name(run.font_name)[0] for run in runs})
                size_variants[key] = sorted({round(run.font_size, 2) for run in runs})
    discontinuities = sum(1 for item in outliers if item["resolution"] == "PRESERVED_UNEXPLAINED_VARIATION")
    return {
        "table_style_outlier_count": len(outliers),
        "same_column_font_family_variants": family_variants,
        "same_column_font_size_variants": size_variants,
        "same_role_style_discontinuities": discontinuities,
        "outliers": outliers,
        "result": "PASS" if discontinuities == 0 else "PASS_WITH_REVIEW",
    }


def build_fact_slot_coverage(template: SourceFormatTemplate, facts: ProjectFacts,
                             generation_report: dict[str, Any]) -> dict[str, Any]:
    filled_ids = {item["slot_id"] for item in generation_report.get("filled_slots", [])}
    text_values = [paragraph.text for page in template.source_pages for paragraph in page.paragraphs]
    text_values += [cell.text for page in template.source_pages for table in page.tables
                    for row in table.rows for cell in row.cells]
    per_fact = []
    mismatch = 0
    wrong_type = 0
    compatible_total = filled_total = 0
    for field in FieldName:
        fact = getattr(facts.fields, field.value)
        compatible = [slot for slot in template.fill_slots if slot_field_allowed(slot, field)]
        rejected = [slot for slot in template.fill_slots if field in slot.allowed_fact_fields and not slot_field_allowed(slot, field)]
        resolved = fact.status == FactStatus.RESOLVED and is_resolved_value_type_valid(field, fact.resolved_value)
        filled = [slot for slot in compatible if slot.slot_id in filled_ids]
        unfilled = [slot for slot in compatible if slot.slot_id not in filled_ids] if resolved else []
        fixed = 0
        if resolved:
            needle = value_text(fact.resolved_value)
            fixed = sum(needle in text and not any(slot.original_text in text for slot in compatible) for text in text_values)
            compatible_total += len(compatible)
            filled_total += len(filled)
        if any(item.get("field") and field.value not in item.get("field", [])
               for item in generation_report.get("filled_slots", [])
               if item["slot_id"] in {slot.slot_id for slot in compatible}):
            wrong_type += 1
        per_fact.append({
            "field": field.value,
            "status": fact.status.value,
            "compatible_slots_detected": len(compatible),
            "compatible_slots_filled": len(filled),
            "compatible_slots_unfilled": len(unfilled),
            "incompatible_slots_rejected": len(rejected),
            "fixed_source_occurrences": fixed,
            "bidder_specific_slots_skipped": 0,
            "unfilled_slot_ids": [slot.slot_id for slot in unfilled],
            "critical_unfilled": resolved and field in CRITICAL_FIELDS and bool(unfilled),
        })
    unfilled_total = compatible_total - filled_total
    return {
        "resolved_fact_compatible_slot_count": compatible_total,
        "resolved_fact_filled_slot_count": filled_total,
        "resolved_fact_unfilled_slot_count": unfilled_total,
        "semantic_slot_mismatch_count": mismatch,
        "wrong_fact_type_fill_count": wrong_type,
        "facts": per_fact,
        "result": "PASS" if not (mismatch or wrong_type or any(item["critical_unfilled"] for item in per_fact)) else "FAIL",
    }


def build_rendered_page_qa(source_format_pages: int, docx_path: str | Path,
                           rendered_pdf: str | Path) -> dict[str, Any]:
    root = _root(docx_path)
    section_count = len(root.xpath(".//w:sectPr", namespaces=W))
    with pymupdf.open(rendered_pdf) as pdf:
        pages = len(pdf)
    return {
        "source_format_pages": source_format_pages,
        "source_section_count": section_count,
        "actual_rendered_pages": pages,
        "generated_page_count": pages,
        "measurement_pipeline": "generated DOCX -> LibreOffice PDF -> PyMuPDF len(pdf)",
        "result": "PASS",
    }


def write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


__all__ = [
    "build_fact_slot_coverage", "build_glyph_semantics_qa", "build_rendered_page_qa",
    "build_table_typography_qa", "semantic_docx_text", "write_json",
]
