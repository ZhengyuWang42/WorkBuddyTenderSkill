"""Strict semantic source-slot policy, independent of any DOCX emitter."""
from .models import FactStatus, FieldName
from .fact_normalizer import is_resolved_value_type_valid
from .output_helpers import value_text
import re


_ALLOWED_BY_SLOT_TYPE = {
    "PROJECT_NAME_SLOT": {FieldName.PROJECT_NAME},
    "PROJECT_AND_LOT_SLOT": {FieldName.PROJECT_NAME, FieldName.LOT_NAME},
    "PROJECT_NUMBER_SLOT": {FieldName.PROJECT_NUMBER},
    "TENDER_NUMBER_SLOT": {FieldName.TENDER_NUMBER},
    "PURCHASER_SLOT": {FieldName.PURCHASER},
    "AGENCY_SLOT": {FieldName.TENDER_AGENCY},
    "DURATION_SLOT": {FieldName.DURATION},
    "QUALITY_SLOT": {FieldName.QUALITY_TARGET},
    "MAX_PRICE_SLOT": {FieldName.MAX_PRICE},
    "BID_DEADLINE_SLOT": {FieldName.BID_DEADLINE},
    "BID_OPEN_TIME_SLOT": {FieldName.BID_OPEN_TIME},
    "BID_BOND_AMOUNT_SLOT": {FieldName.BID_BOND_AMOUNT},
    "BID_BOND_FORM_SLOT": {FieldName.BID_BOND_FORM},
    "CONSORTIUM_SLOT": {FieldName.CONSORTIUM_ALLOWED},
    "PROJECT_LOCATION_SLOT": {FieldName.PROJECT_LOCATION},
    "BID_OPEN_LOCATION_SLOT": {FieldName.BID_OPEN_LOCATION},
    "BID_VALIDITY_SLOT": {FieldName.BID_VALIDITY},
    "ELECTRONIC_PLATFORM_SLOT": {FieldName.ELECTRONIC_PLATFORM},
}


def slot_field_allowed(slot, field):
    """Reject unknown or cross-type fills; geometry never grants permission."""
    slot_type = getattr(slot, "slot_type", "UNKNOWN_SLOT")
    exact = {
            "项目名称": "PROJECT_NAME_SLOT", "采购项目名称": "PROJECT_NAME_SLOT",
            "项目名称、标段": "PROJECT_AND_LOT_SLOT", "项目名称及标段": "PROJECT_AND_LOT_SLOT",
            # A composite written 项目名称（标段名称） names the same fact pair.
            "项目名称（标段名称）": "PROJECT_AND_LOT_SLOT", "项目名称(标段名称)": "PROJECT_AND_LOT_SLOT",
            "项目名称（标段）": "PROJECT_AND_LOT_SLOT", "项目名称(标段)": "PROJECT_AND_LOT_SLOT",
            "项目编号": "PROJECT_NUMBER_SLOT", "采购编号": "PROJECT_NUMBER_SLOT", "采购项目编号": "PROJECT_NUMBER_SLOT",
            "招标编号": "TENDER_NUMBER_SLOT", "代理项目编号": "TENDER_NUMBER_SLOT", "招标代理项目编号": "TENDER_NUMBER_SLOT",
            "招标人": "PURCHASER_SLOT", "招标人名称": "PURCHASER_SLOT", "采购人": "PURCHASER_SLOT", "采购人名称": "PURCHASER_SLOT",
            "采购代理机构": "AGENCY_SLOT", "招标代理机构": "AGENCY_SLOT", "代理机构": "AGENCY_SLOT",
            "供货期": "DURATION_SLOT", "工期": "DURATION_SLOT", "服务期": "DURATION_SLOT",
            "质量标准": "QUALITY_SLOT", "质量目标": "QUALITY_SLOT", "服务质量要求": "QUALITY_SLOT",
    }
    explicit = re.fullmatch(r"[（(]\s*([^()（）]+?)\s*[）)]", slot.original_text.strip())
    if explicit:
        # Visible source semantics outrank a contradictory nearby label.
        slot_type = exact.get(re.sub(r"\s+", "", explicit.group(1)), "UNKNOWN_SLOT")
    elif slot_type == "UNKNOWN_SLOT":
        hint = re.sub(r"\s+", "", slot.semantic_hint).strip("()（）：:")
        slot_type = exact.get(hint, "UNKNOWN_SLOT")
    allowed = _ALLOWED_BY_SLOT_TYPE.get(slot_type, set())
    return field in allowed and field in slot.allowed_fact_fields


_COMPOSITE_COMPONENT_RE = re.compile(r"[^（()）]+")
_COMPONENT_FIELD = (
    ("项目名称", FieldName.PROJECT_NAME),
    ("采购项目名称", FieldName.PROJECT_NAME),
    ("工程名称", FieldName.PROJECT_NAME),
    ("标段名称", FieldName.LOT_NAME),
    ("标段", FieldName.LOT_NAME),
)


def _composite_components(hint: str) -> list[tuple[str, FieldName]]:
    """Split a composite hint such as 项目名称（标段名称） into its components.

    The source nests one placeholder inside another; each half names a different
    fact and must be filled independently, so neither half is silently dropped.
    """
    components: list[tuple[str, FieldName]] = []
    for part in _COMPOSITE_COMPONENT_RE.findall(hint):
        compact = re.sub(r"\s+", "", part).strip("()（）：:")
        if not compact:
            continue
        for label, field in _COMPONENT_FIELD:
            if compact == re.sub(r"\s+", "", label):
                components.append((part, field))
                break
    return components


def _resolved_component_value(facts, field: FieldName) -> str | None:
    fact = getattr(facts.fields, field.value, None)
    if fact is None or fact.status != FactStatus.RESOLVED:
        return None
    if not is_resolved_value_type_valid(field, fact.resolved_value):
        return None
    matching = [
        candidate
        for candidate in fact.candidates
        if candidate.evidence_text.strip()
        and value_text(
            candidate.normalized_value if candidate.normalized_value is not None else candidate.value
        ) == value_text(fact.resolved_value)
    ]
    if not matching:
        return None
    return value_text(fact.resolved_value)


def _composite_replacement(slot, facts):
    """Fill each component of a composite placeholder, preserving the rest.

    When every component resolves, the result is the joined values.  When only
    some resolve, the resolved halves are substituted in place and the
    unresolved halves keep their original source placeholder text, so the
    document never silently loses an unresolved component.
    """
    hint = slot.semantic_hint
    components = _composite_components(hint)
    if not components:
        return None
    values = {field: _resolved_component_value(facts, field) for _part, field in components}
    if not any(value is not None for value in values.values()):
        return None
    if all(value is not None for value in values.values()):
        ordered: list[str] = []
        for field in (FieldName.PROJECT_NAME, FieldName.LOT_NAME):
            value = values.get(field)
            if value is not None and value not in ordered:
                ordered.append(value)
        return "、".join(ordered), "source_slot"
    rendered = slot.original_text
    for part, field in components:
        value = values.get(field)
        if value is None:
            continue
        rendered = rendered.replace(part, value, 1)
    return rendered, "source_slot_partial"


def slot_replacement(slot, facts):
    if getattr(slot, "slot_type", "UNKNOWN_SLOT") == "PROJECT_AND_LOT_SLOT":
        if _COMPOSITE_COMPONENT_RE.findall(slot.semantic_hint) and "（" in slot.semantic_hint:
            composite = _composite_replacement(slot, facts)
            if composite is not None:
                return composite
        values = []
        methods = []
        for field in (FieldName.PROJECT_NAME, FieldName.LOT_NAME):
            if field not in slot.allowed_fact_fields:
                continue
            fact = getattr(facts.fields, field.value)
            if fact.status != FactStatus.RESOLVED or not is_resolved_value_type_valid(field, fact.resolved_value):
                continue
            values.append(value_text(fact.resolved_value))
            methods.extend(candidate.method for candidate in fact.candidates)
        if values:
            method = "derived_cross_reference" if "derived_cross_reference" in methods else "source_slot"
            return "、".join(values), method
    for field in slot.allowed_fact_fields:
        if not slot_field_allowed(slot,field):
            continue
        fact = getattr(facts.fields, field.value)
        if fact.status != FactStatus.RESOLVED or not is_resolved_value_type_valid(field, fact.resolved_value):
            continue
        matching = [c for c in fact.candidates if c.evidence_text.strip() and
                    value_text(c.normalized_value if c.normalized_value is not None else c.value) == value_text(fact.resolved_value)]
        if not matching:
            continue
        value = value_text(fact.resolved_value)
        if field == FieldName.PROJECT_NAME and value.endswith("项目") and slot.suffix_text.lstrip().startswith("项目"):
            # The fixed suffix contributes the semantic word once; avoid
            # emitting ``项目项目招标文件`` while preserving the full name in
            # the resulting sentence.
            value = value[:-2]
        if slot.match_kind == 'whitespace':
            for unit in ('日历天', '个月', '天', '月', '年'):
                if value.endswith(unit) and slot.suffix_text.lstrip().startswith(unit):
                    value = value[:-len(unit)]
                    break
        method = 'derived_cross_reference' if any(c.method == 'derived_cross_reference' for c in matching) else 'source_slot'
        return value, method
    return None
