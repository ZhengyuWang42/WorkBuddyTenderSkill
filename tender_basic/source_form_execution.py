"""Runtime execution provenance for planned source-form fields.

Two strictly downstream layers live here, and neither one feeds back into
transformation policy, geometry intent or planned fact binding:

``SourceFormExecutionOwner``
    Renderer execution scheduling/provenance.  An owner record exists only when
    the renderer ACTUALLY established an active representation that can carry a
    value.  It is not a second semantic model: it never decides what a source
    field means, only whether the renderer currently owns a place to execute the
    value the plan already resolved.

``SourceFillApplication``
    What ACTUALLY happened at the real write event.  Applications are recorded
    at emission; they are never reconstructed afterwards by joining
    ProjectFacts to the plan.

The dependency is one-way:

    SourceFormPlan -> active representation -> execution ownership
        -> Word emission -> SourceFillApplication -> QA
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

APPLICATION_KIND_PLACEHOLDER_REPLACEMENT = "PLACEHOLDER_REPLACEMENT"
APPLICATION_KIND_VALUE_IN_FIXED_SLOT = "VALUE_IN_FIXED_SLOT"

#: Renderer execution-owner kinds.  Generic representation concepts only: no
#: owner kind is keyed to a source page, a rule id or a literal string.
OWNER_KIND_ANCHORED_VALUE = "ANCHORED_VALUE_OWNER"
OWNER_KIND_LEGACY_SLOT = "LEGACY_SLOT_OWNER"
OWNER_KIND_SOURCE_FORM_LINE = "SOURCE_FORM_LINE_OWNER"
OWNER_KIND_NONE = "NONE"

#: Representation types that can actually carry a value write.
VALUE_INSERTING_REPRESENTATIONS = frozenset(
    {
        "SOURCE_ANCHORED_VALUE_RUN",
        "SOURCE_FILL_SLOT",
        "SOURCE_FORM_LINE_PARAGRAPH",
        "SOURCE_RULE_COMPOSITION",
    }
)


def canonical_field_key(value: Any) -> str | None:
    """The one canonical key for a ProjectFacts/FieldName identity.

    Accepts a FieldName member, its ``name``, its ``value``, or a plain string,
    and returns a single normalized token.  Every plan/application comparison
    goes through here.
    """

    if value is None:
        return None
    for attribute in ("name", "value"):
        candidate = getattr(value, attribute, None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().lower()
    text = str(value).strip()
    if not text:
        return None
    if "." in text and text.rsplit(".", 1)[-1].isupper():
        text = text.rsplit(".", 1)[-1]
    return text.lower()


def canonical_field_keys(values: Iterable[Any] | None) -> tuple[str, ...]:
    keys = [canonical_field_key(value) for value in values or ()]
    return tuple(key for key in keys if key)


def stable_field_id(
    *, source_page: Any, source_rule_ids: Iterable[str] | None, geometry: Any
) -> str:
    """Deterministic, source-derived field identity (never a random UUID)."""

    rule_part = "+".join(sorted(str(item) for item in (source_rule_ids or ())))
    x0, x1 = float(geometry[0]), float(geometry[1])
    y = float(geometry[2]) if len(geometry) > 2 else 0.0
    return "SFF%s|%s|%.1f-%.1f@%.1f" % (
        source_page if source_page is not None else "?",
        rule_part or "?",
        x0,
        x1,
        y,
    )


def field_id_for_rule(rule: dict | None) -> str | None:
    """The deterministic field identity of one source rule record."""

    if not rule:
        return None
    if rule.get("source_form_field_id"):
        return str(rule["source_form_field_id"])
    if not rule.get("source_rule_id"):
        return None
    geometry = (
        float(rule.get("x0", 0.0)),
        float(rule.get("x1", 0.0)),
        float(rule.get("y", 0.0)),
    )
    return stable_field_id(
        source_page=rule.get("source_page"),
        source_rule_ids=[str(rule["source_rule_id"])],
        geometry=geometry,
    )


# ---------------------------------------------------------------------------
# Slot -> FieldName bridge
# ---------------------------------------------------------------------------

#: The repository's authoritative slot-type -> fact-field bridge, mirrored from
#: the source fill policy so a legacy slot identity can always be resolved to
#: canonical ProjectFacts field names.  It is data, not a second policy: the
#: policy itself stays in ``source_fill_policy``.
SLOT_TYPE_FACT_FIELDS: dict[str, tuple[str, ...]] = {
    "PROJECT_NAME_SLOT": ("project_name",),
    "PROJECT_AND_LOT_SLOT": ("project_name", "lot_name"),
    "PROJECT_NUMBER_SLOT": ("project_number",),
    "TENDER_NUMBER_SLOT": ("tender_number",),
    "PURCHASER_SLOT": ("purchaser",),
    "AGENCY_SLOT": ("tender_agency",),
    "DURATION_SLOT": ("duration",),
    "QUALITY_SLOT": ("quality_target",),
    "MAX_PRICE_SLOT": ("max_price",),
    "BID_DEADLINE_SLOT": ("bid_deadline",),
    "BID_OPEN_TIME_SLOT": ("bid_open_time",),
    "BID_BOND_AMOUNT_SLOT": ("bid_bond_amount",),
    "BID_BOND_FORM_SLOT": ("bid_bond_form",),
    "CONSORTIUM_SLOT": ("consortium_allowed",),
    "PROJECT_LOCATION_SLOT": ("project_location",),
    "BID_OPEN_LOCATION_SLOT": ("bid_open_location",),
    "BID_VALIDITY_SLOT": ("bid_validity",),
    "ELECTRONIC_PLATFORM_SLOT": ("electronic_platform",),
}


def canonical_fact_fields_for_slot_type(slot_type: Any) -> tuple[str, ...]:
    """Canonical fact fields a legacy slot type is allowed to fill."""

    return SLOT_TYPE_FACT_FIELDS.get(str(slot_type or "").strip().upper(), ())


def canonical_fact_fields_for_slot(slot: Any) -> tuple[str, ...]:
    """Canonical fact fields of one source fill slot.

    The slot's own ``allowed_fact_fields`` is authoritative; the slot type is
    the fallback when a legacy copy lost them.
    """

    declared = canonical_field_keys(getattr(slot, "allowed_fact_fields", None))
    if declared:
        return declared
    return canonical_fact_fields_for_slot_type(getattr(slot, "slot_type", None))


def canonical_fact_fields_for_slot_id(
    slot_id: Any, registry: Iterable[Any] | None = None
) -> tuple[str, ...]:
    """Canonical fact fields of a slot referenced by its id.

    ``registry`` is any iterable of slot-like objects or slot records; the
    lookup is by identity only, never by position.
    """

    if not slot_id:
        return ()
    for slot in registry or ():
        if isinstance(slot, dict):
            if str(slot.get("slot_id")) != str(slot_id):
                continue
            declared = canonical_field_keys(slot.get("allowed_fact_fields"))
            if declared:
                return declared
            return canonical_fact_fields_for_slot_type(slot.get("slot_type"))
        if str(getattr(slot, "slot_id", "")) != str(slot_id):
            continue
        return canonical_fact_fields_for_slot(slot)
    return ()


def facts_actually_written(text: Any, candidates: Iterable[Any] | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Which of the candidate facts the emitted text actually carries.

    Matching is literal-substring based on the real emitted characters - the
    longest value wins so a value cannot be attributed to a shorter, unrelated
    field - and returns ``(fact_keys, values)`` in canonical form.  It never
    invents a field that is not a candidate and never reports a candidate the
    text does not literally contain.
    """

    emitted = str(text or "")
    if not emitted:
        return (), ()
    known = []
    for item in candidates or ():
        key = canonical_field_key(item)
        if not key:
            continue
        value = getattr(item, "resolved_value", None)
        text_value = str(value).strip() if value is not None else ""
        if text_value and text_value in emitted:
            known.append((key, text_value))
    ordered = sorted(set(known), key=lambda item: (-len(item[1]), item[0]))
    matched: list[tuple[str, str]] = []
    for key, value in ordered:
        if any(value in existing for _k, existing in matched):
            continue
        matched.append((key, value))
    if not matched:
        return (), ()
    matched.sort(key=lambda item: emitted.find(item[1]))
    return tuple(key for key, _value in matched), tuple(value for _key, value in matched)


# ---------------------------------------------------------------------------
# Plan lookup
# ---------------------------------------------------------------------------


def field_plan_index(rule_field_plans: dict | None) -> dict:
    """``{rule_key: plan}`` lookup built from the compiler's tuple keys."""

    index: dict[str, Any] = {}
    for key, plan in (rule_field_plans or {}).items():
        if not isinstance(key, tuple) or len(key) < 4:
            continue
        index[_rule_key(key[0], key[1], key[2], key[3])] = plan
    return index


def _tenth(value: Any) -> float:
    """One deterministic tenth-precision rendering of a coordinate.

    ``round`` is banker's rounding, so a coordinate sitting exactly on a
    half-tenth rounds away from the float literal that produced it.  Both the
    index and the lookup use this single function, which keeps plan resolution a
    pure identity match instead of an epsilon search.
    """

    import math

    return math.floor(float(value) * 10.0 + 0.5) / 10.0


def _rule_key(page: Any, x0: float, x1: float, y: float) -> str:
    return "%s|%.1f|%.1f|%.1f" % (page, _tenth(x0), _tenth(x1), _tenth(y))


def resolve_field_plan(rule_field_plans: dict | None, *, page, x0, x1, y):
    """Resolve one rule to exactly one plan; a missing plan fails closed.

    The registry a rule actually arrives with has already been rounded for
    serialization, so the lookup is addressed by the same tenth-precision key
    and falls back to a bounded identity neighbourhood in declared, ascending
    distance order.  More than one reachable plan is ambiguous and resolves to
    none.
    """

    index = field_plan_index(rule_field_plans)
    if not index:
        return None
    exact = index.get(_rule_key(page, x0, x1, y))
    if exact is not None:
        return exact
    target = (page, _tenth(x0), _tenth(x1), _tenth(y))
    reachable = []
    for other_page, ox0, ox1, oy in (
        (
            key[0],
            _tenth(key[1]),
            _tenth(key[2]),
            _tenth(key[3]),
        )
        for key in (rule_field_plans or {})
        if isinstance(key, tuple) and len(key) >= 4
    ):
        if other_page != target[0]:
            continue
        if abs(ox0 - target[1]) > 0.2 or abs(ox1 - target[2]) > 0.2:
            continue
        if abs(oy - target[3]) > 0.2:
            continue
        reachable.append((ox0, ox1, oy))
    if len(reachable) != 1:
        return None
    ox0, ox1, oy = reachable[0]
    return index.get(_rule_key(page, ox0, ox1, oy))


def resolve_field_plan_for_rule(rule: dict | None, rule_field_plans: dict | None):
    """The compiled plan of one source rule record, or ``None``."""

    if not rule:
        return None
    return resolve_field_plan(
        rule_field_plans,
        page=rule.get("source_page"),
        x0=float(rule.get("x0", 0.0)),
        x1=float(rule.get("x1", 0.0)),
        y=float(rule.get("y", 0.0)),
    )


def plan_policy(plan: Any) -> str | None:
    if isinstance(plan, tuple) and plan:
        return str(plan[0]) or None
    return getattr(plan, "transformation_policy", None)


def plan_keys(rule_field_plans: dict | None) -> list:
    """Every compiler key, rendered through the same lookup key function."""

    return [
        _rule_key(key[0], key[1], key[2], key[3])
        for key in (rule_field_plans or {})
        if isinstance(key, tuple) and len(key) >= 4
    ]


def plan_fact_fields(plan: Any) -> tuple[str, ...]:
    if isinstance(plan, tuple) and len(plan) > 1:
        return canonical_field_keys(plan[1])
    return canonical_field_keys(getattr(plan, "planned_fact_fields", None))


# ---------------------------------------------------------------------------
# Renderer execution ownership
# ---------------------------------------------------------------------------


@dataclass
class SourceFormExecutionOwner:
    """Renderer execution scheduling/provenance for one source form field.

    Registered only when the renderer actually establishes the active
    representation that can carry the value.  It never carries semantics of its
    own: the plan supplies what the field means, the owner records where the
    renderer can execute it.
    """

    source_form_field_id: str
    source_rule_ids: tuple[str, ...] = ()
    owner_kind: str = OWNER_KIND_NONE
    representation_type: str | None = None
    source_page: Any = None
    source_slot_id: str | None = None
    accepts_value_insertion: bool = False
    paragraph_index: int | None = None
    emitter_identity: str | None = None
    transformation_policy: str | None = None
    geometry_intent: str | None = None
    planned_fact_fields: tuple[str, ...] = ()
    source_geometry: tuple[float, float, float] | None = None
    registration_reason: str | None = None

    @property
    def eligible_for_value_emission(self) -> bool:
        return bool(self.accepts_value_insertion) and bool(
            self.representation_type in VALUE_INSERTING_REPRESENTATIONS
        )

    def as_dict(self) -> dict:
        return {
            "source_form_field_id": self.source_form_field_id,
            "source_rule_ids": list(self.source_rule_ids),
            "owner_kind": self.owner_kind,
            "representation_type": self.representation_type,
            "source_page": self.source_page,
            "source_slot_id": self.source_slot_id,
            "accepts_value_insertion": bool(self.accepts_value_insertion),
            "eligible_for_value_emission": self.eligible_for_value_emission,
            "paragraph_index": self.paragraph_index,
            "emitter_identity": self.emitter_identity,
            "transformation_policy": self.transformation_policy,
            "geometry_intent": self.geometry_intent,
            "planned_fact_fields": list(self.planned_fact_fields),
            "source_geometry": list(self.source_geometry)
            if self.source_geometry
            else None,
            "registration_reason": self.registration_reason,
        }


def execution_owners(builder: Any) -> list:
    """The renderer's own owner registry, created lazily per build."""

    owners = getattr(builder, "source_form_execution_owners", None)
    if owners is None:
        owners = []
        builder.source_form_execution_owners = owners
    return owners


def register_source_form_execution_owner(
    builder: Any,
    *,
    rule: dict | None,
    owner_kind: str,
    representation_type: str,
    accepts_value_insertion: bool,
    source_slot_id: str | None = None,
    paragraph_index: int | None = None,
    emitter_identity: str | None = None,
    transformation_policy: str | None = None,
    geometry_intent: str | None = None,
    planned_fact_fields: Iterable[Any] | None = None,
    registration_reason: str | None = None,
):
    """Register the active representation the renderer just established.

    Returns ``(owner, blocked_by)``.  A field may have at most one eligible
    value-emission owner: a second claim on the same field fails closed and the
    new claim is refused, so no value is executed twice and no execution
    decision is ever taken by scanning the final text.
    """

    field_id = field_id_for_rule(rule)
    if not field_id:
        return None, None
    owners = execution_owners(builder)
    existing = next(
        (owner for owner in owners if owner.source_form_field_id == field_id), None
    )
    if existing is not None and existing.eligible_for_value_emission:
        if not accepts_value_insertion:
            return existing, existing
        return existing, existing
    geometry = (
        float((rule or {}).get("x0", 0.0)),
        float((rule or {}).get("x1", 0.0)),
        float((rule or {}).get("y", 0.0)),
    )
    rule_ids = (
        (str(rule["source_rule_id"]),) if (rule or {}).get("source_rule_id") else ()
    )
    owner = SourceFormExecutionOwner(
        source_form_field_id=field_id,
        source_rule_ids=rule_ids,
        owner_kind=owner_kind,
        representation_type=representation_type,
        source_page=(rule or {}).get("source_page"),
        source_slot_id=source_slot_id,
        accepts_value_insertion=bool(accepts_value_insertion),
        paragraph_index=paragraph_index,
        emitter_identity=emitter_identity,
        transformation_policy=transformation_policy,
        geometry_intent=geometry_intent,
        planned_fact_fields=canonical_field_keys(planned_fact_fields),
        source_geometry=geometry,
        registration_reason=registration_reason,
    )
    if existing is None:
        owners.append(owner)
    else:
        owners[owners.index(existing)] = owner
    return owner, None


def owners_by_field(builder: Any) -> dict:
    return {
        owner.source_form_field_id: owner for owner in execution_owners(builder)
    }


def resolve_execution_owner(builder: Any, rule: dict | None):
    """The active owner the renderer registered for this exact rule."""

    field_id = field_id_for_rule(rule)
    if not field_id:
        return None
    return owners_by_field(builder).get(field_id)


def execution_owner_for_field(
    builder: Any, *, page, x0, x1, y
) -> Any:
    return resolve_execution_owner(
        builder,
        {
            "source_page": page,
            "x0": x0,
            "x1": x1,
            "y": y,
        },
    )


def resolve_planned_value_execution(builder: Any, rule: dict | None, plan: Any) -> dict:
    """Whether an active owner may execute this plan, and with what value.

    The generic execution scope rule, with no page, rule-id or case branch:

    1. the renderer actually owns an active representation for this field;
    2. the plan resolves to this same rule provenance;
    3. the representation supports value insertion;
    4. no other owner already owns the value;
    5. the plan requires a resolved value in a fixed slot;
    6. the planned fact is RESOLVED with a real resolved value.
    """

    result = {
        "execute": False,
        "reason": None,
        "owner": None,
        "fact_fields": (),
        "values": (),
    }
    owner = resolve_execution_owner(builder, rule)
    if owner is None or not owner.eligible_for_value_emission:
        result["reason"] = "NO_ACTIVE_OWNER"
        return result
    result["owner"] = owner
    policy = plan_policy(plan)
    if policy != "RESOLVED_VALUE_IN_FIXED_SLOT":
        result["reason"] = "PLAN_NOT_RESOLVED_FIXED_SLOT"
        return result
    fact_fields = plan_fact_fields(plan)
    if not fact_fields:
        result["reason"] = "PLAN_HAS_NO_FACT_FIELD"
        return result
    resolved = resolved_fact_values(builder)
    values = tuple(resolved[key] for key in fact_fields if key in resolved)
    if not values:
        result["reason"] = "PLANNED_FACT_NOT_RESOLVED"
        return result
    written_keys = tuple(key for key in fact_fields if key in resolved)
    result.update(
        {
            "execute": True,
            "reason": "ACTIVE_OWNER_EXECUTES_RESOLVED_PLAN",
            "fact_fields": written_keys,
            "values": values,
        }
    )
    return result


def resolved_fact_values(builder: Any) -> dict:
    """Resolved fact field -> resolved value, read from ProjectFacts.

    The one value authority: a fact that is not RESOLVED, or whose resolved
    value is empty, is absent here and can never be executed.
    """

    facts = getattr(builder, "facts", None)
    fields = getattr(facts, "fields", None)
    values: dict[str, str] = {}
    for name in dir(fields) if fields is not None else []:
        if name.startswith("_"):
            continue
        try:
            fact = getattr(fields, name)
        except Exception:
            continue
        value = getattr(fact, "resolved_value", None)
        status = getattr(getattr(fact, "status", None), "value", None)
        if status != "RESOLVED" or value is None:
            continue
        text = str(value).strip()
        if text:
            values[name.lower()] = text
    return values


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


@dataclass
class SourceFillApplication:
    """Execution proof for one planned source-form field."""

    application_id: str
    source_form_field_id: str
    source_rule_ids: tuple[str, ...]
    application_kind: str
    representation_type: str
    fact_fields: tuple[str, ...] = ()
    resolved_values: tuple[str, ...] = ()
    source_slot_id: str | None = None
    source_page: Any = None
    generated_paragraph_index: int | None = None
    generated_run_index: int | None = None
    planned_fact_fields: tuple[str, ...] = ()
    transformation_policy: str | None = None
    geometry_intent: str | None = None
    source_geometry: tuple[float, float, float] | None = None
    owner_kind: str | None = None
    execution_owner_id: str | None = None

    def as_dict(self) -> dict:
        return {
            "application_id": self.application_id,
            "source_form_field_id": self.source_form_field_id,
            "source_rule_ids": list(self.source_rule_ids),
            "application_kind": self.application_kind,
            "representation_type": self.representation_type,
            "fact_fields": list(self.fact_fields),
            "resolved_values": list(self.resolved_values),
            "source_slot_id": self.source_slot_id,
            "source_page": self.source_page,
            "generated_paragraph_index": self.generated_paragraph_index,
            "generated_run_index": self.generated_run_index,
            "planned_fact_fields": list(self.planned_fact_fields),
            "transformation_policy": self.transformation_policy,
            "geometry_intent": self.geometry_intent,
            "source_geometry": list(self.source_geometry)
            if self.source_geometry
            else None,
            "owner_kind": self.owner_kind,
            "execution_owner_id": self.execution_owner_id,
        }


def source_fill_applications(builder: Any) -> list:
    applications = getattr(builder, "source_fill_applications", None)
    if applications is None:
        applications = []
        builder.source_fill_applications = applications
    return applications


def record_source_fill_application(
    builder: Any,
    *,
    rule: dict,
    fact_fields: Iterable[Any] | None,
    values: Iterable[Any] | None,
    application_kind: str,
    representation_type: str,
    generated_paragraph_index: int | None = None,
    generated_run_index: int | None = None,
    source_slot_id: str | None = None,
    source_page: Any = None,
    owner_kind: str | None = None,
    execution_owner_id: str | None = None,
) -> SourceFillApplication:
    """Record one application at the actual write event.

    Called from the renderer's real emission paths.  It never influences what
    gets rendered.
    """

    facts = canonical_field_keys(fact_fields)
    emitted = tuple(str(value) for value in (values or ()) if value is not None)
    page = source_page if source_page is not None else rule.get("source_page")
    geometry = (
        float(rule.get("x0", 0.0)),
        float(rule.get("x1", 0.0)),
        float(rule.get("y", 0.0)),
    )
    rule_ids = tuple(
        item
        for item in (
            [str(rule["source_rule_id"])] if rule.get("source_rule_id") else []
        )
    )
    # Semantic plan and the renderer's own execution ownership: the plan supplies
    # what the field means, the owner record says whether the renderer owns a
    # place to execute it.  Neither is re-derived from the final text.
    plan = resolve_field_plan(
        getattr(builder, "_rule_field_plans", None),
        page=page,
        x0=geometry[0],
        x1=geometry[1],
        y=geometry[2],
    )
    planned_facts = plan_fact_fields(plan)
    if not planned_facts:
        planned_facts = canonical_field_keys(
            getattr(plan, "planned_fact_fields", None) if plan is not None else None
        )
    owner = resolve_execution_owner(builder, rule)
    policy = plan_policy(plan) or getattr(owner, "transformation_policy", None)
    intent = (getattr(builder, "_rule_geometry_intents", {}) or {}).get(
        str(rule.get("source_rule_id"))
    ) or getattr(owner, "geometry_intent", None)
    applications = source_fill_applications(builder)
    application = SourceFillApplication(
        application_id="SFA%d" % (len(applications) + 1),
        source_form_field_id=stable_field_id(
            source_page=page, source_rule_ids=rule_ids, geometry=geometry
        ),
        source_rule_ids=rule_ids,
        application_kind=application_kind,
        representation_type=representation_type,
        fact_fields=facts,
        resolved_values=emitted,
        source_slot_id=source_slot_id or getattr(owner, "source_slot_id", None),
        source_page=page,
        generated_paragraph_index=generated_paragraph_index,
        generated_run_index=generated_run_index,
        planned_fact_fields=planned_facts,
        transformation_policy=policy,
        geometry_intent=intent,
        source_geometry=geometry,
        owner_kind=owner_kind or getattr(owner, "owner_kind", None),
        execution_owner_id=(
            execution_owner_id or getattr(owner, "source_form_field_id", None)
        ),
    )
    applications.append(application)
    return application


def attach_application_to_owner(builder: Any, owner: Any, application: Any) -> None:
    """Note the application on its owner record (provenance cross-reference)."""

    if owner is None or application is None:
        return
    owner.emitter_identity = owner.emitter_identity or application.representation_type


# ---------------------------------------------------------------------------
# QA metrics
# ---------------------------------------------------------------------------


def _application_field_ids(applications: Iterable[Any]) -> list[str]:
    ids: list[str] = []
    for item in applications:
        record = item.as_dict() if hasattr(item, "as_dict") else dict(item)
        if record.get("source_form_field_id"):
            ids.append(str(record["source_form_field_id"]))
    return ids


def plan_application_metrics(
    *,
    planned: Iterable[dict],
    applications: Iterable[Any],
    resolved_status: str = "RESOLVED",
) -> dict:
    """Plan-versus-actual QA, compared on semantic FACT COVERAGE.

    ``planned`` is a sequence of ``{"field_id", "fact_fields", "values"}``
    descriptions of the resolved planned fields; ``applications`` is the
    recorded execution evidence.  Coverage is compared per fact, so a composite
    write recorded as one logical application covers both of its facts.
    """

    planned_list = list(planned or ())
    actual = [
        item.as_dict() if hasattr(item, "as_dict") else dict(item)
        for item in (applications or ())
    ]
    resolved_actual = [
        item
        for item in actual
        if item.get("application_kind")
        in (
            APPLICATION_KIND_PLACEHOLDER_REPLACEMENT,
            APPLICATION_KIND_VALUE_IN_FIXED_SLOT,
        )
        and item.get("resolved_values")
    ]

    actual_field_ids = {
        item.get("source_form_field_id") for item in resolved_actual
    }
    planned_field_ids = {item.get("field_id") for item in planned_list}

    missing = sorted(
        item_id for item_id in planned_field_ids if item_id not in actual_field_ids
    )
    unexpected = sorted(
        item_id for item_id in actual_field_ids if item_id not in planned_field_ids
    )

    planned_fact_set = set()
    actual_fact_set = set()
    for entry in planned_list:
        planned_fact_set |= set(canonical_field_keys(entry.get("fact_fields")))
    for item in resolved_actual:
        actual_fact_set |= set(canonical_field_keys(item.get("fact_fields")))

    by_id: dict[Any, list[dict]] = {}
    for item in resolved_actual:
        by_id.setdefault(item.get("source_form_field_id"), []).append(item)

    fact_mismatch = value_mismatch = field_mismatch = 0
    for entry in planned_list:
        apps = by_id.get(entry.get("field_id")) or []
        planned_facts = set(canonical_field_keys(entry.get("fact_fields")))
        planned_values = {str(v) for v in (entry.get("values") or ())}
        actual_facts: set[str] = set()
        actual_values: set[str] = set()
        for app in apps:
            actual_facts |= set(canonical_field_keys(app.get("fact_fields")))
            actual_values |= {str(v) for v in (app.get("resolved_values") or ())}
        if planned_facts != actual_facts:
            fact_mismatch += 1
        if planned_values != actual_values:
            value_mismatch += 1
        declared = set(canonical_field_keys(entry.get("declared_fact_fields")))
        if declared and not actual_facts <= declared:
            field_mismatch += 1

    return {
        "planned_resolved_application_count": len(planned_list),
        "actual_resolved_application_count": len(resolved_actual),
        "logical_application_record_count": len(actual),
        "missing_planned_application_count": len(missing),
        "unexpected_application_count": len(unexpected),
        "application_fact_mismatch_count": fact_mismatch,
        "application_value_mismatch_count": value_mismatch,
        "application_field_mismatch_count": field_mismatch,
        "planned_resolved_fact_count": len(planned_fact_set),
        "actual_covered_resolved_fact_count": len(
            planned_fact_set & actual_fact_set
        ),
        "missing_planned_field_ids": missing,
        "unexpected_field_ids": unexpected,
    }


def execution_owner_metrics(builder: Any) -> dict:
    """Owner-registry summary, including zero-owner fields."""

    owners = [owner.as_dict() for owner in execution_owners(builder)]
    eligible = [owner for owner in owners if owner["eligible_for_value_emission"]]
    per_field: dict[str, int] = {}
    for owner in eligible:
        per_field[owner["source_form_field_id"]] = (
            per_field.get(owner["source_form_field_id"], 0) + 1
        )
    return {
        "source_form_execution_owner_count": len(owners),
        "eligible_value_owner_count": len(eligible),
        "multiple_eligible_owner_conflicts": sorted(
            field_id for field_id, count in per_field.items() if count > 1
        ),
        "owner_kind_counts": {
            kind: sum(1 for owner in owners if owner["owner_kind"] == kind)
            for kind in (
                OWNER_KIND_ANCHORED_VALUE,
                OWNER_KIND_LEGACY_SLOT,
                OWNER_KIND_SOURCE_FORM_LINE,
                OWNER_KIND_NONE,
            )
        },
    }
