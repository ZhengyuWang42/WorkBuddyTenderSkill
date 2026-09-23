"""Strict semantic source-slot policy, independent of any DOCX emitter."""
from dataclasses import dataclass, field as dataclass_field
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


@dataclass(frozen=True)
class SlotValuePresentation:
    """One emitted slot value, split into the components that are visible in it.

    The value is what Word receives; ``components`` is provenance, and it always
    spells out which characters came from a resolved fact, which came from the
    source text, and which are the source form's own marker for a component that
    has no fact behind it.  A marker component is never a fact.
    """

    value: str
    method: str
    components: tuple = dataclass_field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "value": self.value,
            "method": self.method,
            "components": [dict(component) for component in self.components],
            "fact_components": [
                component["field"]
                for component in self.components
                if component["kind"] == COMPONENT_FACT_VALUE
            ],
            "marker_components": [
                component["field"]
                for component in self.components
                if component["kind"] == COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER
            ],
        }

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


# ---------------------------------------------------------------------------
# Composite slot PRESENTATION
# ---------------------------------------------------------------------------

#: Provenance kinds of the visible components of one emitted slot value.  A
#: component is either FACT_VALUE (a real ProjectFacts value), a source literal
#: the source itself prints, or the source's own form marker for a component
#: that is structurally expected but has no fact behind it.
COMPONENT_FACT_VALUE = "FACT_VALUE"
COMPONENT_SOURCE_TEMPLATE_LITERAL = "SOURCE_TEMPLATE_LITERAL"
COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER = "SOURCE_FORM_NOT_APPLICABLE_MARKER"

#: The source's own marker for a composite component that the form structurally
#: expects but which has no fact to carry.  The marker is NOT a value and is
#: never written back to ProjectFacts: the field keeps its own NOT_FOUND status.
SOURCE_FORM_NOT_APPLICABLE_MARKER = "/"

#: Written between the visible components of a composite slot when the source
#: hint does not itself carry a separator.
DEFAULT_COMPOSITE_SEPARATOR = "、"


def _component_separator(hint: str, leading_label: str, trailing_label: str) -> str:
    """The separator the source itself prints between two composite halves.

    Read from the slot's own hint text between the two named halves; when the
    source prints none, the repository's enumeration separator is used so the
    two components stay distinguishable.  Nothing here is keyed to a case, a
    page or a literal project value.
    """

    start = hint.find(leading_label)
    end = hint.find(trailing_label)
    if start >= 0 and end > start:
        between = re.sub(r"\s+", "", hint[start + len(leading_label):end])
        between = between.strip("（）()【】[]")
        if between:
            return between
    return DEFAULT_COMPOSITE_SEPARATOR


#: The bracket pairs a source may print around a form field.  Only a *matched*
#: pair qualifies as a frame: an unmatched opening is prose, not a field.
SOURCE_FRAME_PAIRS: tuple[tuple[str, str], ...] = (
    ("（", "）"),
    ("(", ")"),
    ("【", "】"),
    ("[", "]"),
    ("〔", "〕"),
    ("〈", "〉"),
    ("《", "》"),
)


def source_placeholder_frame(slot) -> tuple[str, str] | None:
    """The source's own bracket literals that frame a placeholder.

    ``original_text`` is the source's own printing of the placeholder and
    ``semantic_hint`` is the text the placeholder names, so the difference
    between them is exactly the source's frame - this is read from the source
    artifact rather than assumed, which is why a half-width ``(`` and a
    full-width ``（`` are never conflated.  Returns ``None`` unless the
    remainder is a matched bracket pair, so a placeholder the source printed
    inside running prose keeps the accepted plain substitution.

    Nothing here is keyed to a page, a rule id, a case or a literal value.
    """

    original = str(getattr(slot, "original_text", "") or "")
    hint = str(getattr(slot, "semantic_hint", "") or "")
    if not original or not hint:
        return None
    at = original.find(hint)
    if at <= 0:
        return None
    opening = original[:at]
    closing = original[at + len(hint):]
    if (opening, closing) not in SOURCE_FRAME_PAIRS:
        return None
    return opening, closing


def source_literal_component(text: str) -> dict:
    """One visible character of the source's own form text, as provenance."""

    return {
        "kind": COMPONENT_SOURCE_TEMPLATE_LITERAL,
        "field": None,
        "text": text,
        "source": "SOURCE_PLACEHOLDER_TEXT",
    }


def composite_placeholder_ends_its_source_line(slot) -> bool:
    """Whether the source prints a composite placeholder at the end of its line.

    This is the source's own structural evidence, read from the slot's suffix -
    the source text that follows the placeholder:

    * the suffix begins a new source line, so the placeholder is the whole of its
      own source visual line.  It is a *line-level form field*: the form asks for
      both named halves on that line and nothing else, so printing the
      not-applicable marker for a half with no fact behind it completes the field
      the source itself wrote.
    * the suffix continues on the same source line, so the placeholder is one
      word inside a sentence the source printed.  There the form does not ask a
      standalone question, and inserting a marker would invent content inside
      that sentence.

    Nothing here is keyed to a page, a rule id or a literal value.
    """

    suffix = str(getattr(slot, "suffix_text", "") or "")
    stripped = suffix.lstrip("\u00a0 \t\f\v")
    if not stripped:
        return True
    return stripped[0] in "\r\n\u2028\u2029"


def _composite_presentation(slot, facts, *, source_form_field=False):
    """The visible composition of a composite slot, component by component.

    A composite source slot such as ``（项目名称、标段）`` names two facts and
    prints one separator between them.  When the first resolves and the second
    is structurally absent the source's own second component is still part of
    the form, so the emitted value is ``<resolved fact> <separator> <source
    not-applicable marker>`` and every component is recorded separately.

    Two independent kinds of source evidence can establish that the placeholder
    *is* a form field:

    ``source_form_field``
        The source's own rule is drawn beneath the placeholder's own glyphs
        (full text occupancy), so the placeholder's characters - its brackets
        included - are the source's form text.  The composition then keeps the
        source's own frame, read from the placeholder's own printing.
    the placeholder ending its source line
        The form asks for both named halves on that line and nothing else.

    Returns a :class:`SlotValuePresentation` or ``None``.  The marker is never a
    fact: ``lot_name`` keeps its own ProjectFacts status, no candidate is
    created for it and no fact count changes.
    """

    if getattr(slot, "slot_type", "UNKNOWN_SLOT") != "PROJECT_AND_LOT_SLOT":
        return None
    hint = slot.semantic_hint or ""
    leading, trailing = "项目名称", "标段"
    if leading not in hint or trailing not in hint:
        return None
    frame = source_placeholder_frame(slot) if source_form_field else None
    if frame is None and not composite_placeholder_ends_its_source_line(slot):
        return None
    project = _resolved_component_value(facts, FieldName.PROJECT_NAME)
    lot = _resolved_component_value(facts, FieldName.LOT_NAME)
    if project is None or lot is not None:
        # Either there is no fact to print at all, or both halves resolved and
        # the ordinary join already carries the source's full composition.
        return None
    lot_fact = getattr(facts.fields, FieldName.LOT_NAME.value, None)
    if lot_fact is not None and lot_fact.status == FactStatus.RESOLVED:
        # The fact is resolved; an empty resolved value is a different defect and
        # must not be papered over with a presentation marker.
        return None
    separator = _component_separator(hint, leading, trailing)
    opening, closing = frame if frame is not None else ("", "")
    components = []
    if opening:
        components.append(source_literal_component(opening))
    components.append(
        {
            "kind": COMPONENT_FACT_VALUE,
            "field": FieldName.PROJECT_NAME.value,
            "text": project,
            "source": "ProjectFacts",
        }
    )
    components.append(
        {
            "kind": COMPONENT_SOURCE_TEMPLATE_LITERAL,
            "field": None,
            "text": separator,
            "source": "SOURCE_SLOT_HINT",
        }
    )
    components.append(
        {
            "kind": COMPONENT_SOURCE_FORM_NOT_APPLICABLE_MARKER,
            "field": FieldName.LOT_NAME.value,
            "text": SOURCE_FORM_NOT_APPLICABLE_MARKER,
            "source": "SOURCE_FORM_STRUCTURE",
        }
    )
    if closing:
        components.append(source_literal_component(closing))
    return SlotValuePresentation(
        value=opening
        + project
        + separator
        + SOURCE_FORM_NOT_APPLICABLE_MARKER
        + closing,
        method="source_slot_composite_presentation",
        components=tuple(components),
    )


#: Slot id -> the presentation record of the value actually emitted for it.
#: Rendering provenance only: it records what was written, it never decides it.
_SLOT_PRESENTATIONS: dict[str, dict] = {}


def recorded_slot_presentation(slot):
    """The recorded presentation of the value emitted for ``slot``, if any."""

    slot_id = getattr(slot, "slot_id", None)
    if not slot_id:
        return None
    return _SLOT_PRESENTATIONS.get(str(slot_id))


def reset_recorded_slot_presentations() -> None:
    _SLOT_PRESENTATIONS.clear()



def slot_replacement(slot, facts, *, source_form_field=False):
    """The value written for ``slot``, or ``None`` to leave it blank.

    ``source_form_field`` is the emitter's source-evidence claim that this
    placeholder's own glyphs are the source's form text: the source's rule is
    drawn beneath exactly those characters rather than across a wider blank.
    The claim never changes *which* fact a slot may carry - it only decides
    whether the source's own bracketed frame survives the substitution.
    """

    if getattr(slot, "slot_type", "UNKNOWN_SLOT") == "PROJECT_AND_LOT_SLOT":
        if _COMPOSITE_COMPONENT_RE.findall(slot.semantic_hint) and "（" in slot.semantic_hint:
            composite = _composite_replacement(slot, facts)
            if composite is not None:
                return composite
        presentation = _composite_presentation(
            slot, facts, source_form_field=source_form_field
        )
        if presentation is not None:
            # PRESENTATION COMPOSITION.  The source's combined slot prints both
            # of its components; when the second has no fact behind it, the
            # source's own not-applicable marker is emitted in its place and the
            # fact itself is left exactly as ProjectFacts reports it.
            _SLOT_PRESENTATIONS[str(slot.slot_id)] = presentation.as_dict()
            return presentation.value, presentation.method
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
    frame = source_placeholder_frame(slot) if source_form_field else None
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
        if frame is None:
            return value, method
        # FRAMED FORM FIELD.  The source's rule decorates this placeholder's own
        # glyphs, so its brackets are the source's form text: the value is
        # substituted *inside* the frame the source itself printed instead of
        # replacing the frame with the value.
        presentation = SlotValuePresentation(
            value=frame[0] + value + frame[1],
            method=method,
            components=(
                source_literal_component(frame[0]),
                {
                    "kind": COMPONENT_FACT_VALUE,
                    "field": field.value,
                    "text": value,
                    "source": "ProjectFacts",
                },
                source_literal_component(frame[1]),
            ),
        )
        _SLOT_PRESENTATIONS[str(slot.slot_id)] = presentation.as_dict()
        return presentation.value, presentation.method
    return None
