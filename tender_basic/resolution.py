"""Apply constrained semantic-review selections to ProjectFacts."""

from __future__ import annotations

from typing import Any

from .models import (
    FactStatus,
    ProjectFacts,
    ProjectFields,
    ResolutionAction,
    ResolutionOverrides,
    ResolvedFact,
)


def apply_resolution_overrides(
    project_facts: ProjectFacts,
    overrides: ResolutionOverrides,
) -> tuple[ProjectFacts, list[dict[str, Any]]]:
    """Return reviewed facts and an audit trail without mutating the input.

    Every instruction must target a current NEEDS_REVIEW field.  A selection
    can only point at an existing candidate, so this function cannot create a
    new fact value or alter candidate evidence.
    """

    if not isinstance(project_facts, ProjectFacts):
        raise TypeError("apply_resolution_overrides requires ProjectFacts")
    if not isinstance(overrides, ResolutionOverrides):
        raise TypeError("apply_resolution_overrides requires ResolutionOverrides")

    updated_fields = {
        field_name: getattr(project_facts.fields, field_name)
        for field_name in ProjectFields.model_fields
    }
    audit_entries: list[dict[str, Any]] = []

    for instruction in overrides.resolutions:
        field_name = instruction.field.value
        current = updated_fields[field_name]
        if current.status != FactStatus.NEEDS_REVIEW:
            raise ValueError(
                f"Resolution can only target NEEDS_REVIEW fields: {field_name}"
            )

        selected_candidate: dict[str, Any] | None = None
        if instruction.action == ResolutionAction.SELECT_CANDIDATE:
            assert instruction.candidate_index is not None
            if instruction.candidate_index >= len(current.candidates):
                raise ValueError(
                    f"Candidate index out of range for {field_name}: "
                    f"{instruction.candidate_index}"
                )
            candidate = current.candidates[instruction.candidate_index]
            if candidate.value is None or (
                isinstance(candidate.value, str) and not candidate.value.strip()
            ):
                raise ValueError(
                    f"Selected candidate has no value for field: {field_name}"
                )
            selected_candidate = {
                "candidate_index": instruction.candidate_index,
                "value": candidate.value,
                "normalized_value": candidate.normalized_value,
                "locator": candidate.locator.model_dump(mode="json"),
            }
            updated_fields[field_name] = ResolvedFact(
                field=current.field,
                resolved_value=candidate.value,
                status=FactStatus.RESOLVED,
                confidence=candidate.confidence,
                candidates=current.candidates,
                resolution_reason=f"Reviewed selection: {instruction.reason}",
            )
        else:
            # KEEP_UNRESOLVED intentionally leaves the complete deterministic
            # fact, including all candidates and evidence, untouched.
            updated_fields[field_name] = current

        audit_entries.append(
            {
                "field": field_name,
                "selected_candidate": selected_candidate,
                "reason": instruction.reason,
                "previous_status": current.status.value,
                "new_status": updated_fields[field_name].status.value,
            }
        )

    reviewed = ProjectFacts.from_fields(
        source_document=project_facts.source_document,
        fields=ProjectFields(**updated_fields),
        schema_version=project_facts.schema_version,
    )
    return reviewed, audit_entries


def build_resolution_audit(
    project_facts: ProjectFacts,
    audit_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Wrap audit entries with stable context without changing ProjectFacts."""

    return {
        "schema_version": project_facts.schema_version,
        "source_document": project_facts.source_document.source_file,
        "resolutions": audit_entries,
    }


__all__ = ["apply_resolution_overrides", "build_resolution_audit"]
