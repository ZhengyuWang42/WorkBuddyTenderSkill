"""Small shared presentation helpers for the V1 XLSX and DOCX builders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from .models import CandidateFact, FactStatus, FieldName, Locator, ResolvedFact


_DEFAULT_OUTPUT_FIELDS_PATH = (
    Path(__file__).resolve().parents[1] / "rules" / "output_fields.yaml"
)

STATUS_LABELS: Mapping[FactStatus, str] = {
    FactStatus.RESOLVED: "已解析",
    FactStatus.NEEDS_REVIEW: "需复核",
    FactStatus.NOT_FOUND: "未找到",
}


@dataclass(frozen=True)
class OutputField:
    field: str
    category: str
    label: str


def load_output_fields(path: str | Path | None = None) -> tuple[OutputField, ...]:
    """Load and validate the fixed output order for the current V1 fields."""

    config_path = Path(path) if path is not None else _DEFAULT_OUTPUT_FIELDS_PATH
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    raw_fields = payload.get("fields")
    if not isinstance(raw_fields, list):
        raise ValueError("output_fields.yaml fields must be a list")

    result: list[OutputField] = []
    seen: set[str] = set()
    for item in raw_fields:
        if not isinstance(item, dict):
            raise ValueError("Each output field definition must be a mapping")
        field = str(item.get("field", ""))
        category = str(item.get("category", "")).strip()
        label = str(item.get("label", "")).strip()
        if not field or not category or not label:
            raise ValueError("Output field definitions require field, category, and label")
        if field in seen:
            raise ValueError(f"Duplicate output field: {field}")
        try:
            FieldName(field)
        except ValueError as exc:
            raise ValueError(f"Unknown output field: {field}") from exc
        seen.add(field)
        result.append(OutputField(field=field, category=category, label=label))

    expected = {field.value for field in FieldName}
    if seen != expected or len(result) != len(expected):
        missing = sorted(expected - seen)
        extra = sorted(seen - expected)
        raise ValueError(f"Output field catalog mismatch; missing={missing}, extra={extra}")
    return tuple(result)


def field_label(field: str | FieldName, fields: Iterable[OutputField] | None = None) -> str:
    field_name = field.value if isinstance(field, FieldName) else str(field)
    for spec in fields or load_output_fields():
        if spec.field == field_name:
            return spec.label
    raise KeyError(field_name)


def field_category(
    field: str | FieldName,
    fields: Iterable[OutputField] | None = None,
) -> str:
    field_name = field.value if isinstance(field, FieldName) else str(field)
    for spec in fields or load_output_fields():
        if spec.field == field_name:
            return spec.category
    raise KeyError(field_name)


def status_display(status: FactStatus) -> str:
    return f"{STATUS_LABELS[status]} ({status.value})"


def value_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def _best_candidate(fact: ResolvedFact) -> CandidateFact | None:
    if not fact.candidates:
        return None
    return max(enumerate(fact.candidates), key=lambda item: (item[1].confidence, -item[0]))[1]


def format_locator(locator: Locator) -> str:
    data = locator.model_dump(mode="json")
    locator_type = data["locator_type"]
    if locator_type == "pdf_block":
        page = data["page"]
        block = data.get("block_index")
        return f"PDF:P:{page}:B:{block}" if block is not None else f"PDF:P:{page}"
    if locator_type == "pdf_table_cell":
        return (
            f"PDF:T:{data['page']}:T:{data['table_index']}"
            f":R:{data['row_index']}:C:{data['column_index']}"
        )
    if locator_type == "docx_paragraph":
        return f"DOCX:P:{data['paragraph_index']}"
    if locator_type == "docx_table_cell":
        return (
            f"DOCX:T:{data['table_index']}:R:{data['row_index']}"
            f":C:{data['cell_index']}"
        )
    raise ValueError(f"Unsupported locator type: {locator_type}")


def summary_locator(fact: ResolvedFact) -> str:
    if fact.status == FactStatus.NOT_FOUND:
        return ""
    if fact.status == FactStatus.RESOLVED:
        candidate = _best_candidate(fact)
        return format_locator(candidate.locator) if candidate else ""
    return "; ".join(format_locator(candidate.locator) for candidate in fact.candidates)


def xlsx_value(fact: ResolvedFact) -> str:
    if fact.status == FactStatus.RESOLVED:
        return value_text(fact.resolved_value)
    if fact.status == FactStatus.NEEDS_REVIEW:
        return "【存在冲突，见字段证据】"
    return "【未找到】"


def template_value(fact: ResolvedFact) -> str:
    """Render one ProjectFacts value for the supplied review template."""

    if fact.status == FactStatus.RESOLVED:
        return value_text(fact.resolved_value)
    if fact.status == FactStatus.NEEDS_REVIEW:
        return "【待核对】"
    return "【待补充】"


def combine_template_facts(
    facts: Iterable[tuple[str, ResolvedFact]],
    *,
    empty_value: str = "【待补充】",
) -> str:
    """Combine independent facts without substituting one field for another."""

    parts = [
        f"{label}：{template_value(fact)}"
        for label, fact in facts
        if fact.status != FactStatus.NOT_FOUND
    ]
    return "；".join(parts) if parts else empty_value


def docx_value(fact: ResolvedFact) -> str:
    if fact.status == FactStatus.RESOLVED:
        return value_text(fact.resolved_value)
    if fact.status == FactStatus.NEEDS_REVIEW:
        return "【待人工确认】"
    return "【待补充】"


def candidate_value_summary(fact: ResolvedFact) -> str:
    if not fact.candidates:
        return "无可信候选"
    return "；".join(value_text(candidate.value) for candidate in fact.candidates)


def candidate_locator_json(candidate: CandidateFact) -> str:
    """Keep a deterministic JSON form available for debugging/tests."""

    return json.dumps(
        candidate.locator.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )


__all__ = [
    "OutputField",
    "STATUS_LABELS",
    "candidate_locator_json",
    "candidate_value_summary",
    "combine_template_facts",
    "docx_value",
    "field_category",
    "field_label",
    "format_locator",
    "load_output_fields",
    "status_display",
    "summary_locator",
    "template_value",
    "value_text",
    "xlsx_value",
]
