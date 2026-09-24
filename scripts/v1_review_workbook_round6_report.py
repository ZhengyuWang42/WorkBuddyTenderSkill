"""Round-6 source-visible criticality report (REVIEW WORKBOOK ROUND 6).

The round-5 review workbook was still losing the source's own emphasis markers,
and it treated three different source questions as one:

* which requirements does the *source* mark (``*`` / ``★`` / ...)?
* which requirements does the *source* call 实质性要求 (or 必备证明材料)?
* which requirements does the *source* attach a 否决/无效 consequence to?

Round 6 keeps those three dimensions apart.  ``tender_basic.source_criticality``
discovers, per document, the marker vocabulary, the marker's *meaning* as the
document states it, the governing substantive-requirement clause, the
consequence rules and the explicit references between clauses.  This report
audits the rendered workbook against that model and persists the per-row chain
(source atom -> marker evidence -> governing basis -> concern -> review point ->
final cell) for a human reviewer.

Usage::

    python -X utf8 scripts/v1_review_workbook_round6_report.py --case case_001
    python -X utf8 scripts/v1_review_workbook_round6_report.py --three-case
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from openpyxl import load_workbook  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from tender_basic.source_criticality import (  # noqa: E402
    BASIS_REFERENCE_PROPAGATION,
    BASIS_SOURCE_MARKER,
    COVERAGE_BACKGROUND_ROW,
    COVERAGE_DELIVERED_ROW,
    COVERAGE_KIND_BACKGROUND,
    COVERAGE_KIND_DIRECT_DELIVERED,
    COVERAGE_KIND_REFERENCE_PARENT,
    COVERAGE_KIND_UNRESOLVED,
    COVERAGE_REFERENCE_CHILD,
    COVERAGE_REFERENCE_PARENT,
    COVERAGE_UNCOVERED,
    MARKER_CHARS,
    MANDATORY_TYPE_STARRED,
)
from v1_review_workbook_round4_report import MANDATORY_SHEET, Round4Report  # noqa: E402
from v1_review_workbook_round5_report import Round5Report  # noqa: E402

CASES = {
    "case_001": {
        "build": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook6",
        "source": "v1_manual_fidelity_round4_date_rhythm_closure8",
        "before": "v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook5",
        "marker_fixtures": (
            "1.4.1",
            "1.4.4",
            "1.4.5",
            "1.4.6",
            "1.4.7",
            "1.4.8",
            "1.5.1",
            "1.5.2",
            "3.3.1",
            "3.4.1",
            "10.1",
            "流量计",
        ),
        "row_fixtures": (
            "DR001",
            "DR002",
            "DR003",
            "DR004",
            "DR012",
            "DR017",
            "DR018",
            "DR019",
            "DR020",
            "DR030",
            "DR047",
        ),
    },
    "case_002": {
        "build": "v1_round4_closure8_review_workbook6",
        "source": "v1_round4_closure8",
        "before": "v1_round4_closure8_review_workbook5",
    },
    "case_003": {
        "build": "v1_round4_closure8_review_workbook6",
        "source": "v1_round4_closure8",
        "before": "v1_round4_closure8_review_workbook5",
    },
}

CASES_SPECIAL = None

REPORTS = ROOT / "acceptance/reports/v1_generalization"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    evidence: dict

    def as_dict(self) -> dict:
        return {
            "check": self.name,
            "ok": bool(self.ok),
            "detail": self.detail,
            "evidence": self.evidence,
        }


class Round6Report:
    def __init__(
        self,
        case: str,
        *,
        case_dir: Path | None = None,
        stage: str = "initial",
    ) -> None:
        spec = CASES[case]
        self.case = case
        self.stage = stage
        self.case_dir = case_dir or (ROOT / "acceptance/workspace" / case)
        build_name = spec["build"]
        if stage == "marker_closure":
            # the round-6 successor build: the initial build stays on disk as the
            # preserved FAILED evidence and is never overwritten
            build_name = f"{build_name}_marker_closure"
        self.build = self.case_dir / build_name
        self.source_build = self.case_dir / spec["source"]
        self.before = self.case_dir / spec["before"]
        self.r4 = Round4Report(self.build, case)
        self.plan = self.r4.plan
        self.document = self.r4.document
        self.facts = self.r4.facts
        self.items = list(self.r4.items)
        self.background = list(self.r4.background)
        self.criticality = self.plan.criticality
        self.checks: list[Check] = []
        self.marker_records: list[dict] = []
        self.marker_dispositions: dict[str, int] = {}
        self.marker_ledger_counts: dict[str, int] = {}
        self.criticality_counts: dict[str, int] = {}
        self.marker_false_positive_count = 0
        self.marker_unattributed_count = 0
        self.marker_unresolved_count = 0
        self.direct_marker_visibility_failures = 0
        self.reference_parent_coverage_failures = 0
        self.uncovered_substantive_count = 0
        self.uncovered_actionable_substantive_count = 0
        self.dashboard_metrics: dict[str, dict] = {}
        self.row_records: list[dict] = []
        self.fixtures: dict[str, dict] = {}
        self.coverage_records: list[dict] = []

    # -- helpers ---------------------------------------------------------- #

    def check(self, name: str, ok: bool, detail: str, evidence: dict | None = None) -> None:
        self.checks.append(Check(name, bool(ok), detail, evidence or {}))

    def _sheet_rows(self, title: str) -> list[dict]:
        workbook = load_workbook(self.build / "投标项目复核表.xlsx", data_only=True, read_only=True)
        try:
            worksheet = workbook[title]
            headers = [
                str(cell.value or "").strip()
                for cell in next(worksheet.iter_rows(min_row=1, max_row=1))
            ]
            rows = []
            for row in worksheet.iter_rows(min_row=2, values_only=True):
                if not any(value not in (None, "") for value in row):
                    continue
                rows.append({headers[i]: row[i] for i in range(min(len(headers), len(row)))})
            return rows
        finally:
            workbook.close()

    def _item(self, item_id: str):
        return next((item for item in self.items if item.item_id == item_id), None)

    def marker_lost_count(self) -> int:
        """Source markers that never reached a review row.

        Round-6 closure: this counts *occurrences* that are neither delivered nor
        explicitly accounted for -- an occurrence that was discovered but
        attributed to no atom is a loss, not an invisible record.
        """

        lost_states = {
            COVERAGE_KIND_UNRESOLVED,
            "LOST_DELIVERED_ROW_WITHOUT_STAR",
            "ATTRIBUTED_WITHOUT_OWNER",
        }

        return sum(1 for record in self.marker_records if record["status"] in lost_states)

    # -- marker fidelity -------------------------------------------------- #

    def _atom_owners(self) -> dict[str, list[str]]:
        atom_owner: dict[str, list[str]] = {}
        for item in [*self.items, *self.background]:
            for atom_id in getattr(item.review_point, "owned_atom_ids", ()) or ():
                atom_owner.setdefault(str(atom_id), []).append(item.item_id)
        return atom_owner

    def _attribution_routes(self, occurrence, atom_ids: list[str]) -> list[str]:
        """How each attributed atom carries the occurrence's marker.

        ``CLAUSE``  - the atom's own source clause is the marked clause;
        ``MARKER_IN_ATOM`` - the marked fragment (marker character included) is
        visible inside the atom text (mid-text / mid-cell attribution);
        ``CONTINUATION`` - the atom is the wrapped continuation of the marked
        line (the extractor broke the clause and kept the marker on line 1);
        ``ATOM_IN_OCCURRENCE`` - the atom text is quoted inside the marked text.
        """

        index = self.criticality
        fragment = occurrence.marked_fragment
        occurrence_text = occurrence.continuation_text or occurrence.source_text
        flat_occurrence = re.sub(r"[\s\u3000]+", "", str(occurrence_text or ""))
        flat_source = re.sub(r"[\s\u3000]+", "", str(occurrence.source_text or ""))
        routes: list[str] = []
        for atom_id in atom_ids:
            flat = re.sub(r"[\s\u3000]+", "", str(index.atom_text.get(atom_id, "") or ""))
            record = index.criticalities.get(atom_id)
            if fragment and fragment in flat:
                routes.append("MARKER_IN_ATOM")
            elif flat and flat in flat_occurrence:
                routes.append("CONTINUATION")
            elif flat and flat in flat_source:
                routes.append("ATOM_IN_OCCURRENCE")
            elif record is not None and record.marker_evidence_id == occurrence.evidence_id:
                routes.append("CLAUSE")
            else:
                routes.append("CLAUSE")
        return list(dict.fromkeys(routes))

    def audit_markers(self) -> None:
        """Per-occurrence ledger over the complete discovered marker universe.

        The audit starts from *every* de-duplicated discovered occurrence
        (``index.occurrences``) and gives each one a disposition.  It never
        iterates the atoms that already claim a marker: a discovered marker that
        was attributed to nothing used to be invisible to this check, which is
        exactly the round-6 defect this closure fixes.
        """

        index = self.criticality
        atom_owner = self._atom_owners()
        starred = {
            str(row.get("requirement_id")): str(row.get("★") or "").strip()
            for row in self._sheet_rows(MANDATORY_SHEET)
        }
        delivered_ids = {item.item_id for item in self.items}
        background_ids = {item.item_id for item in self.background}
        background_reason = {
            item.item_id: {
                "concern_id": getattr(item, "concern_id", ""),
                "module": getattr(item, "module", ""),
                "reason": (
                    f"NON_BIDDER_FACING_CONCERN:"
                    f"{getattr(item, 'concern_id', '') or 'UNCLASSIFIED'}"
                ),
                "policy": "round-4/5 non-bidder-facing concern kept in plan.background_items",
            }
            for item in self.background
        }
        reference_parents = index.reference_parent_atom_ids()

        counts = {
            "source_marker_occurrence_count": index.source_marker_occurrence_count,
            "raw_source_marker_discovery_count": index.raw_source_marker_discovery_count,
            "duplicate_source_marker_record_count": (
                index.duplicate_source_marker_record_count
            ),
            "source_marker_evidence_count": len(index.markers),
        }
        dispositions: dict[str, int] = {}
        unattributed: list[dict] = []
        unresolved: list[dict] = []
        visibility_failures: list[dict] = []
        reference_failures: list[dict] = []
        false_positive: list[dict] = []

        for occurrence in index.occurrences:
            atom_ids = list(index.atoms_for_occurrence(occurrence.occurrence_id))
            owner_items = sorted(
                {owner for atom_id in atom_ids for owner in atom_owner.get(atom_id, [])}
            )
            delivered_owners = [item_id for item_id in owner_items if item_id in delivered_ids]
            background_owners = [item_id for item_id in owner_items if item_id in background_ids]
            visible_rows = [
                item_id for item_id in delivered_owners if starred.get(item_id) == "★"
            ]
            is_reference_parent = any(atom_id in reference_parents for atom_id in atom_ids)
            routes = self._attribution_routes(occurrence, atom_ids)
            continuation_only = bool(atom_ids) and "MARKER_IN_ATOM" not in routes and "CLAUSE" not in routes

            if atom_ids and delivered_owners and visible_rows:
                status = COVERAGE_KIND_DIRECT_DELIVERED
                reason = "delivered review row visibly carries the source marker"
            elif atom_ids and delivered_owners:
                status = "LOST_DELIVERED_ROW_WITHOUT_STAR"
                reason = "the delivering review row does not show the source marker"
            elif atom_ids and is_reference_parent:
                status = COVERAGE_KIND_REFERENCE_PARENT
                reason = "marked clause is a reference parent; its meaning reaches the children"
            elif atom_ids and background_owners:
                status = COVERAGE_KIND_BACKGROUND
                reason = background_reason.get(background_owners[0], {}).get(
                    "reason", "NON_BIDDER_FACING_CONCERN"
                )
            elif atom_ids:
                status = "ATTRIBUTED_WITHOUT_OWNER"
                reason = "no review point owns the marked atom"
            else:
                status = COVERAGE_KIND_UNRESOLVED
                reason = "discovered occurrence was attributed to no source atom"

            record = {
                "occurrence_id": occurrence.occurrence_id,
                "marker_evidence_id": occurrence.evidence_id,
                "raw_source_marker": occurrence.raw_marker,
                "page": occurrence.page,
                "locator": occurrence.locator,
                "clause": occurrence.clause,
                "scope": occurrence.scope,
                "source_kind": occurrence.source_kind,
                "source_text": occurrence.source_text[:200],
                "continuation_text": occurrence.continuation_text[:200],
                "extractor_record_count": occurrence.extractor_record_count,
                "source_atom_ids": atom_ids[:8],
                "owner_items": owner_items[:8],
                "delivered_owner_items": delivered_owners[:8],
                "background_owner_items": background_owners[:8],
                "starred_rows": visible_rows[:8],
                "reference_parent": is_reference_parent,
                "attribution_routes": routes,
                "continuation_only": continuation_only,
                "disposition": status,
                "disposition_reason": reason,
                "status": status,
            }
            self.marker_records.append(record)
            dispositions[status] = dispositions.get(status, 0) + 1

            if status == COVERAGE_KIND_UNRESOLVED:
                unresolved.append(
                    {
                        "occurrence_id": occurrence.occurrence_id,
                        "raw_source_marker": occurrence.raw_marker,
                        "locator": occurrence.locator,
                        "source_text": occurrence.source_text[:120],
                    }
                )
            if status in (COVERAGE_KIND_UNRESOLVED, "ATTRIBUTED_WITHOUT_OWNER"):
                unattributed.append(
                    {
                        "occurrence_id": occurrence.occurrence_id,
                        "raw_source_marker": occurrence.raw_marker,
                        "locator": occurrence.locator,
                        "source_atom_ids": atom_ids[:4],
                        "disposition": status,
                    }
                )
            if status == "LOST_DELIVERED_ROW_WITHOUT_STAR":
                visibility_failures.append(
                    {
                        "occurrence_id": occurrence.occurrence_id,
                        "raw_source_marker": occurrence.raw_marker,
                        "delivered_owner_items": delivered_owners[:4],
                        "starred_rows": visible_rows[:4],
                    }
                )
            if status == COVERAGE_KIND_REFERENCE_PARENT and not any(
                link.parent_atom_id in atom_ids for link in index.reference_links
            ):
                reference_failures.append(
                    {"occurrence_id": occurrence.occurrence_id, "source_atom_ids": atom_ids[:4]}
                )
            # a marker may only exist where the source evidence says so
            if occurrence.raw_marker and occurrence.raw_marker not in (
                occurrence.source_text or ""
            ):
                false_positive.append(
                    {
                        "occurrence_id": occurrence.occurrence_id,
                        "raw_source_marker": occurrence.raw_marker,
                        "source_text": occurrence.source_text[:120],
                    }
                )

        # every ★ in the sheet must be backed by a marked row
        sheet_starred = {
            str(row.get("requirement_id"))
            for row in self._sheet_rows(MANDATORY_SHEET)
            if str(row.get("★") or "").strip() == "★"
        }
        unbacked = sorted(
            item_id
            for item_id in sheet_starred
            if item_id and not (self._item(item_id) and self._item(item_id).marker_present)
        )
        false_positive.extend(
            {"item_id": item_id, "reason": "★ without marker atom"} for item_id in unbacked
        )

        marked_atoms = [
            atom_id
            for atom_id, record in index.criticalities.items()
            if record.marker_present
        ]
        self.marker_dispositions = dispositions
        self.marker_ledger_counts = counts
        self.marker_false_positive_count = len(false_positive)
        self.marker_unattributed_count = len(unattributed)
        self.marker_unresolved_count = len(unresolved)
        self.direct_marker_visibility_failures = len(visibility_failures)
        self.reference_parent_coverage_failures = len(reference_failures)

        self.check(
            "marker occurrences discovered, attributed and resolved",
            not unattributed and not unresolved,
            (
                f"occurrences={counts['source_marker_occurrence_count']} "
                f"unattributed={len(unattributed)} unresolved={len(unresolved)}"
            ),
            {
                **counts,
                "dispositions": dispositions,
                "unattributed": unattributed[:10],
                "unresolved": unresolved[:10],
            },
        )
        self.check(
            "direct delivered markers are visible in the workbook",
            not visibility_failures,
            f"direct_delivered_marker_visibility_failures={len(visibility_failures)}",
            {"failures": visibility_failures[:10], "marker_atom_count": len(marked_atoms)},
        )
        self.check(
            "reference parents keep their propagation coverage",
            not reference_failures,
            f"reference_parent_coverage_failures={len(reference_failures)}",
            {"failures": reference_failures[:10], "reference_parent_count": len(reference_parents)},
        )
        self.check(
            "marker false positives",
            not false_positive,
            f"marker_false_positive_count={len(false_positive)}",
            {"false_positives": false_positive[:10]},
        )
        self.check(
            "marker preserved (no source marker is lost)",
            self.marker_lost_count() == 0,
            f"marker_lost_count={self.marker_lost_count()}",
            {"dispositions": dispositions},
        )
        count_atoms = sum(
            1 for record in index.criticalities.values() if record.marker_present
        )
        self.criticality_counts = {
            **counts,
            "direct_source_marked_review_row_count": len(
                {item_id for item_id in sheet_starred if item_id}
            ),
            "substantive_review_row_count": len(
                [
                    item
                    for item in self.items
                    if getattr(item, "substantive_requirement", False)
                ]
            ),
            "marker_carrying_source_atom_count": count_atoms,
        }

    def check_marker_fixtures(self) -> None:
        rows = self._sheet_rows(MANDATORY_SHEET)
        star_by_item = {
            row.get("requirement_id"): str(row.get("★") or "").strip() for row in rows
        }
        index = self.criticality
        delivered_ids = {item.item_id for item in self.items}
        spec = CASES[self.case]
        clause_fixtures = tuple(spec.get("marker_fixtures") or ()) or tuple(
            dict.fromkeys(marker.clause for marker in index.markers if marker.clause)
        )[:12]
        row_fixtures = tuple(spec.get("row_fixtures") or ()) or tuple(
            item.item_id for item in self.items if item.marker_present
        )[:20]
        atom_owner: dict[str, list[str]] = {}
        for item in [*self.items, *self.background]:
            for atom_id in getattr(item.review_point, "owned_atom_ids", ()) or ():
                atom_owner.setdefault(str(atom_id), []).append(item.item_id)
        for fixture in clause_fixtures:
            evidence = [
                marker for marker in index.markers if marker.clause == fixture
            ] or [
                marker for marker in index.markers if fixture in marker.source_text
            ]
            evidence_ids = {marker.evidence_id for marker in evidence}
            is_clause = bool(re.fullmatch(r"\d+(?:\.\d+)*", fixture))
            atoms = [
                atom_id
                for atom_id, record in index.criticalities.items()
                if record.marker_present
                and (
                    record.marker_evidence_id in evidence_ids
                    or (not is_clause and fixture in index.atom_text.get(atom_id, ""))
                )
            ]
            owners = sorted(
                {owner for atom_id in atoms for owner in atom_owner.get(atom_id, [])}
            )
            delivered_rows = [owner for owner in owners if owner in delivered_ids]
            starred_rows = [owner for owner in delivered_rows if star_by_item.get(owner) == "★"]
            ok = bool(evidence) and bool(atoms) and (not delivered_rows or bool(starred_rows))
            self.fixtures[f"marker:{fixture}"] = {
                "expectation": f"source marker on {fixture} reaches the workbook",
                "status": "PASS" if ok else "FAIL",
                "evidence": {
                    "marker_evidence_ids": sorted(evidence_ids)[:4],
                    "marker_atoms": atoms[:6],
                    "owner_items": owners[:6],
                    "delivered_rows": delivered_rows[:6],
                    "starred_rows": starred_rows[:6],
                },
            }
        for fixture in row_fixtures:
            item = self._item(fixture)
            self.fixtures[f"row:{fixture}"] = {
                "expectation": f"{fixture} keeps its source marker in the workbook",
                "status": "PASS" if item is not None and star_by_item.get(fixture) == "★" else "FAIL",
                "evidence": {
                    "raw_source_markers": list(getattr(item, "raw_source_markers", ()) or ()),
                    "star": star_by_item.get(fixture, ""),
                },
            }
        failed = [key for key, value in self.fixtures.items() if value["status"] != "PASS"]
        self.check(
            "known source-marker fixtures",
            not failed,
            f"{len(self.fixtures) - len(failed)}/{len(self.fixtures)} fixture(s) marked",
            {"failed": failed},
        )

    # -- semantics -------------------------------------------------------- #

    def check_semantics(self) -> None:
        rules = [rule for rule in self.criticality.substantive_rules if rule.markers]
        vocabularies = sorted({marker for rule in rules for marker in rule.markers})
        semantics = sorted({rule.semantics for rule in rules})
        unknown = [
            rule.rule_id for rule in rules if not rule.semantics or rule.semantics == "UNESTABLISHED"
        ]
        marked_rows = [item for item in self.items if item.marker_present]
        unclassified = [
            item.item_id
            for item in marked_rows
            if not item.substantive_requirement
            and item.marker_semantics in ("", "UNESTABLISHED")
        ]
        self.check(
            "source marker vocabulary is discovered per document",
            bool(vocabularies),
            f"vocabulary={vocabularies}",
            {"rules": [rule.as_dict() for rule in rules]},
        )
        self.check(
            "marker meaning comes from the document's own statement",
            bool(semantics) and all(value and value != "UNESTABLISHED" for value in semantics),
            f"semantics={semantics}",
            {"unestablished_rules": unknown},
        )
        self.check(
            "no marker is promoted to a rejection consequence by itself",
            all(
                not (item.marker_present and item.rejection_consequence)
                or bool(item.rejection_basis_atom_ids)
                for item in self.items
            ),
            f"unclassified_marked_rows={unclassified}",
            {"marked_rows": [(item.item_id, item.marker_semantics) for item in marked_rows]},
        )

    def check_governing_clause(self) -> None:
        """SOURCE MARKER -> substantive rule -> consequence rule -> row."""

        rules = list(self.criticality.substantive_rules)
        marker_rules = [rule for rule in rules if rule.markers]
        governed = [rule for rule in marker_rules if rule.governing_clause]
        anchored = [
            rule
            for rule in marker_rules
            if rule.governing_clause or rule.semantics != "UNESTABLISHED"
        ]
        unanchored = [rule.rule_id for rule in marker_rules if rule not in anchored]
        unclassified_rows: list[dict] = []
        for item in self.items:
            if not item.marker_present:
                continue
            record = self.criticality.criticalities.get(
                next(
                    (
                        atom_id
                        for atom_id in item.review_point.owned_atom_ids
                        if self.criticality.criticalities.get(str(atom_id), None)
                        is not None
                        and self.criticality.criticalities[str(atom_id)].marker_present
                    ),
                    "",
                )
            )
            semantics = record.marker_semantics if record is not None else item.marker_semantics
            if not item.substantive_requirement and semantics == "UNESTABLISHED":
                unclassified_rows.append(
                    {"item_id": item.item_id, "marker": item.raw_source_markers}
                )
        rejection_rules = list(self.criticality.rejection_rules)
        consequence_backed = [
            item.item_id
            for item in self.items
            if item.rejection_consequence and item.rejection_basis_atom_ids
        ]
        unbacked_consequence = [
            item.item_id
            for item in self.items
            if item.rejection_consequence and not item.rejection_basis_atom_ids
        ]
        self.check(
            "the tender's own substantive-requirement rule is discovered and linked",
            bool(marker_rules) and not unanchored and not unclassified_rows,
            f"{len(anchored)}/{len(marker_rules)} marker rule(s) anchored in the source "
            f"({len(governed)} via a governing clause), "
            f"{len(unclassified_rows)} unclassified marked row(s)",
            {
                "governing_clauses": sorted({rule.governing_clause for rule in governed}),
                "semantics": sorted({rule.semantics for rule in marker_rules}),
                "unanchored": unanchored,
                "unclassified_rows": unclassified_rows,
                "rule_kinds": sorted({rule.kind for rule in rules}),
            },
        )
        self.check(
            "every rejection claim traces to a source consequence rule",
            bool(consequence_backed) and not unbacked_consequence,
            f"{len(consequence_backed)} consequence-backed row(s), "
            f"{len(rejection_rules)} source consequence rule(s)",
            {
                "unbacked": unbacked_consequence,
                "rules": [rule.rule_id for rule in rejection_rules][:10],
            },
        )

    # -- reference propagation -------------------------------------------- #

    def check_references(self) -> None:
        links = list(self.criticality.reference_links)
        resolved = [link for link in links if link.target_atom_ids]
        unresolved = [link for link in links if not link.target_atom_ids]
        chains = [
            {
                "parent_atom_id": link.parent_atom_id,
                "parent_clause": link.parent_clause,
                "marker": link.marker,
                "target": link.target,
                "target_kind": link.target_kind,
                "child_count": len(link.target_atom_ids),
                "child_atom_ids": list(link.target_atom_ids[:8]),
            }
            for link in links
        ]
        propagated_children = [
            item.item_id
            for item in self.items
            if item.substantive_basis_kind == BASIS_REFERENCE_PROPAGATION
        ]
        child_items = [
            item
            for item in self.items
            if item.substantive_basis_kind == BASIS_REFERENCE_PROPAGATION
        ]
        self.check(
            "explicit source references propagate the starred parent's meaning",
            not unresolved and (not links or bool(propagated_children)),
            f"{len(resolved)} resolved reference link(s), {len(unresolved)} unresolved, "
            f"{len(propagated_children)} propagated row(s)",
            {"chains": chains},
        )
        self.check(
            "reference children are marked as propagated, never as starred",
            all(
                MANDATORY_TYPE_STARRED not in item.mandatory_types
                or item.marker_present
                for item in self.items
            ),
            f"propagated_rows={propagated_children}",
            {
                "rows": [
                    {
                        "item_id": item.item_id,
                        "types": list(item.mandatory_types),
                        "star": item.marker_present,
                        "reference_parent_atom_id": item.reference_parent_atom_id,
                        "reference_target": item.reference_target,
                    }
                    for item in child_items
                ]
            },
        )

    # -- consequence rules ------------------------------------------------- #

    def check_consequences(self) -> None:
        index = self.criticality
        explicit = [item for item in self.items if item.rejection_kind == "EXPLICIT"]
        derived = [item for item in self.items if item.rejection_kind == "DERIVED"]
        unbacked = [
            item.item_id
            for item in [*explicit, *derived]
            if not item.rejection_basis_atom_ids
        ]
        rules = [rule.as_dict() for rule in index.rejection_rules]
        self.check(
            "rejection consequence is a separate, source-backed dimension",
            not unbacked,
            f"explicit={len(explicit)} derived={len(derived)} unbacked={len(unbacked)}",
            {"unbacked": unbacked, "rules": rules[:8]},
        )

    # -- workbook columns -------------------------------------------------- #

    def check_sheet_surface(self) -> None:
        """The reviewer surface must keep its filters, columns and freedom.

        Round-6 closure: the successor workbook is a *new* artifact, so the
        surface of the mandatory sheet (the human's working sheet) is verified
        again: the automatic filter covers the printed columns, the sheet is not
        protected, and the three criticality columns stay plain (no colour fill
        that would imply a precedence between ★ / 否决性 / 强制性类型).
        """

        workbook = load_workbook(self.build / "投标项目复核表.xlsx", data_only=False)
        try:
            sheet = workbook[MANDATORY_SHEET]
            headers = [
                str(cell.value or "").strip()
                for cell in next(sheet.iter_rows(min_row=1, max_row=1))
            ]
            expected_headers = ["★", "否决性", "强制性类型", "源标记", "实质性依据", "否决依据"]
            missing_headers = [name for name in expected_headers if name not in headers]
            filter_ref = str(getattr(sheet.auto_filter, "ref", "") or "")
            fill_columns = []
            for name in ("★", "否决性", "强制性类型"):
                if name not in headers:
                    continue
                column = headers.index(name) + 1
                for row in range(2, sheet.max_row + 1):
                    fill = sheet.cell(row=row, column=column).fill
                    if fill is not None and fill.fill_type not in (None, "none"):
                        fill_columns.append(f"{name}{row}")
                        break
            last_column = get_column_letter(len(headers))
            self.check(
                "the reviewer surface keeps its filters and free columns",
                not missing_headers
                and filter_ref == f"A1:{last_column}{sheet.max_row}"
                and not sheet.protection.sheet
                and not fill_columns,
                f"filter={filter_ref or '-'} protection={sheet.protection.sheet} "
                f"filled={fill_columns}",
                {
                    "headers": headers,
                    "missing_headers": missing_headers,
                    "auto_filter": filter_ref,
                    "protected": bool(sheet.protection.sheet),
                    "filled_criticality_cells": fill_columns[:6],
                    "row_count": sheet.max_row,
                },
            )
        finally:
            workbook.close()

    def check_sheet_columns(self) -> None:
        rows = self._sheet_rows(MANDATORY_SHEET)
        marked = [
            row for row in rows if self._item(str(row.get("requirement_id") or "")) is not None
            and self._item(str(row.get("requirement_id"))).marker_present
        ]
        blank_star = [row.get("requirement_id") for row in marked if str(row.get("★") or "").strip() != "★"]
        starred = {row.get("requirement_id") for row in rows if str(row.get("★") or "").strip() == "★"}
        vetoed = {row.get("requirement_id") for row in rows if str(row.get("否决性") or "").strip() == "是"}
        types = {str(row.get("强制性类型") or "") for row in rows}
        self.check(
            "every source-marked row shows ★",
            not blank_star,
            f"{len(marked)} marked row(s), {len(blank_star)} blank",
            {"blank_marked_rows": blank_star[:10]},
        )
        self.check(
            "★, 否决性 and 强制性类型 are independent columns",
            starred != vetoed or not starred,
            f"starred={len(starred)} vetoed={len(vetoed)} symmetric_difference={len(starred ^ vetoed)}",
            {
                "starred_only": sorted(starred - vetoed)[:10],
                "vetoed_only": sorted(vetoed - starred)[:10],
                "mandatory_types": sorted(types),
            },
        )
        self.check(
            "强制性类型 states the source basis instead of the requirement type",
            any("SUBSTANTIVE" in value or value == "MANDATORY" for value in types),
            f"types={sorted(types)}",
            {"row_types": [(row.get("requirement_id"), row.get("强制性类型")) for row in rows[:8]]},
        )
        self.check(
            "raw marker and its basis are carried next to the normalised columns",
            all(
                (str(row.get("★") or "").strip() != "★" or str(row.get("源标记") or "").strip() != "")
                and (
                    "SUBSTANTIVE" not in str(row.get("强制性类型") or "")
                    or str(row.get("实质性依据") or "").strip() != ""
                )
                and (
                    str(row.get("否决性") or "").strip() != "是"
                    or str(row.get("否决依据") or "").strip() != ""
                )
                for row in rows
            ),
            "源标记/实质性依据/否决依据 columns carry the source basis",
            {
                "headers": list(rows[0].keys()) if rows else [],
                "sample": [
                    {
                        "requirement_id": row.get("requirement_id"),
                        "★": row.get("★"),
                        "源标记": row.get("源标记"),
                        "强制性类型": row.get("强制性类型"),
                        "实质性依据": row.get("实质性依据"),
                        "否决依据": row.get("否决依据"),
                    }
                    for row in rows
                    if str(row.get("★") or "").strip() == "★"
                ][:5],
            },
        )

    # -- dashboard --------------------------------------------------------- #

    @staticmethod
    def _sheet_values(rows: list[dict], column: str) -> list[str]:
        return [str(row.get(column) or "").strip() for row in rows]

    @staticmethod
    def _countif_evaluate(formula: str, values: list[str], token: str) -> int:
        """Evaluate a single ``COUNTIF(range, "token")`` exactly as Excel would.

        ``*`` is a trailing wildcard (prefix match); everything else is equality.
        A formula that is *not* a single COUNTIF over the expected range cannot be
        evaluated and must fail the gate instead of being silently accepted.
        """

        if not formula.startswith("=COUNTIF("):
            return -1
        if formula.count("COUNTIF") != 1:
            return -1
        if token.endswith("*"):
            prefix = token[:-1]
            return sum(1 for value in values if value.startswith(prefix))
        return sum(1 for value in values if value == token)

    def _dashboard_values(self) -> tuple[dict[str, str], dict[str, list[str]], dict[str, dict]]:
        workbook = load_workbook(
            self.build / "投标项目复核表.xlsx", data_only=False, read_only=True
        )
        try:
            sheet = workbook["00_复核总览"]
            labels: dict[str, str] = {}
            for row in sheet.iter_rows(values_only=True):
                if row and row[0] and row[1] and str(row[1]).startswith("="):
                    labels[str(row[0])] = str(row[1])
        finally:
            workbook.close()
        rows = self._sheet_rows(MANDATORY_SHEET)
        values = {
            "H": self._sheet_values(rows, "★"),
            "I": self._sheet_values(rows, "否决性"),
            "J": self._sheet_values(rows, "强制性类型"),
            "T": self._sheet_values(rows, "否决依据"),
        }
        independent = {
            "source_marked_review_row_count": sum(1 for value in values["H"] if value == "★"),
            "substantive_review_row_count": sum(
                1 for value in values["J"] if value.startswith("SUBSTANTIVE")
            ),
            "rejection_row_count": sum(1 for value in values["I"] if value == "是"),
            "explicit_rejection_row_count": sum(
                1 for value in values["T"] if value.startswith("EXPLICIT")
            ),
            "derived_rejection_row_count": sum(
                1 for value in values["T"] if value.startswith("DERIVED")
            ),
        }
        return labels, values, independent

    def check_dashboard(self) -> None:
        labels, values, independent = self._dashboard_values()
        expected = {
            "带源标记的复核条目数（★）": ("H", "★", "source_marked_review_row_count"),
            "实质性要求条目数（源依据）": (
                "J",
                "SUBSTANTIVE*",
                "substantive_review_row_count",
            ),
            "明示或可证明否决项数": ("I", "是", "rejection_row_count"),
            "其中：明示否决（源文明确示后果）": (
                "T",
                "EXPLICIT*",
                "explicit_rejection_row_count",
            ),
            "其中：推导否决（源文实质性要求规则）": (
                "T",
                "DERIVED*",
                "derived_rejection_row_count",
            ),
        }
        missing = [label for label in expected if label not in labels]
        conflated = [label for label in labels if "★/一票否决" in label]
        # the source-marker label must not read as a count of source occurrences
        misreadable = [
            label
            for label in labels
            if "源标记条款数" in label
            or ("源文件标记" in label and "出现次数" in label)
            or "源标记出现次数" in label
        ]
        self.check(
            "dashboard reports the three dimensions separately",
            not missing and not conflated and not misreadable,
            f"missing={missing} conflated={conflated} misreadable={misreadable}",
            {"labels": {key: labels.get(key, "") for key in expected}},
        )

        metrics: dict[str, dict] = {}
        failures: list[str] = []
        for label, (column, token, key) in expected.items():
            formula = labels.get(label, "")
            recalculated = self._countif_evaluate(formula, values[column], token)
            independent_value = independent[key]
            ok = (
                recalculated >= 0
                and recalculated == independent_value
                and token in formula
            )
            metrics[label] = {
                "column": column,
                "formula": formula,
                "expected_value": independent_value,
                "formula_token": token,
                "recalculated_value": recalculated,
                "independent_value": independent_value,
                "ok": ok,
            }
            if not ok:
                failures.append(label)
        self.dashboard_metrics = metrics
        self.check(
            "dashboard criticality counters equal the independent recount",
            not failures and not missing,
            f"mismatched={failures}",
            {
                "metrics": metrics,
                "independent_recount": independent,
                "recalculated_scope": MANDATORY_SHEET,
            },
        )

    # -- coverage ---------------------------------------------------------- #

    def check_coverage(self) -> None:
        index = self.criticality
        atom_owner: dict[str, list[str]] = {}
        for item in [*self.items, *self.background]:
            for atom_id in getattr(item.review_point, "owned_atom_ids", ()) or ():
                atom_owner.setdefault(str(atom_id), []).append(item.item_id)
        delivered_ids = {item.item_id for item in self.items}
        reference_parents = {
            link.parent_atom_id for link in index.reference_links if link.target_atom_ids
        }
        reference_children = {
            child for link in index.reference_links for child in link.target_atom_ids
        }
        # the complete source-criticality universe: every substantive *atom* and
        # every marker occurrence must be accounted for, not only the ones that
        # already own a row.
        substantives = [
            (atom_id, record)
            for atom_id, record in index.criticalities.items()
            if record.substantive_requirement
        ]
        occurrence_uncovered: list[dict] = []
        for record in self.marker_records:
            if record["disposition"] in (
                COVERAGE_KIND_UNRESOLVED,
                "ATTRIBUTED_WITHOUT_OWNER",
                "LOST_DELIVERED_ROW_WITHOUT_STAR",
            ):
                occurrence_uncovered.append(
                    {
                        "occurrence_id": record["occurrence_id"],
                        "raw_source_marker": record["raw_source_marker"],
                        "locator": record["locator"],
                        "disposition": record["disposition"],
                    }
                )
        uncovered: list[dict] = []
        for atom_id, record in substantives:
            owners = atom_owner.get(atom_id, [])
            if atom_id in reference_children:
                coverage = COVERAGE_REFERENCE_CHILD
            elif atom_id in reference_parents:
                coverage = COVERAGE_REFERENCE_PARENT
            elif any(owner in delivered_ids for owner in owners):
                coverage = COVERAGE_DELIVERED_ROW
            elif owners:
                coverage = COVERAGE_BACKGROUND_ROW
            else:
                coverage = COVERAGE_UNCOVERED
                uncovered.append(
                    {
                        "source_atom_id": atom_id,
                        "atom_text": index.atom_text.get(atom_id, "")[:160],
                        "basis_kind": record.substantive_basis_kind,
                        "marker_occurrence_ids": list(record.marker_occurrence_ids),
                    }
                )
            self.coverage_records.append(
                {
                    "source_atom_id": atom_id,
                    "atom_text": index.atom_text.get(atom_id, "")[:200],
                    "basis_kind": record.substantive_basis_kind,
                    "basis_atom_ids": list(record.substantive_basis_atom_ids),
                    "owner_items": owners,
                    "coverage": coverage,
                    "rejection_kind": record.rejection_kind,
                    "marker_occurrence_ids": list(record.marker_occurrence_ids),
                }
            )
        actionable_uncovered = [
            item
            for item in uncovered
            if any(
                owner in delivered_ids for owner in atom_owner.get(item["source_atom_id"], [])
            )
        ]
        self.check(
            "every source substantive requirement is covered by the review",
            not uncovered,
            f"source_substantive_requirement_without_review_coverage_count={len(uncovered)}",
            {"uncovered": uncovered[:10], "substantive_atom_count": len(substantives)},
        )
        self.check(
            "every marker occurrence is accounted for by coverage",
            not occurrence_uncovered,
            f"source_marker_occurrence_uncovered_count={len(occurrence_uncovered)}",
            {
                "uncovered": occurrence_uncovered[:10],
                "dispositions": self.marker_dispositions,
            },
        )
        self.uncovered_substantive_count = len(uncovered)
        self.uncovered_actionable_substantive_count = len(actionable_uncovered)

    # -- contract / word artifacts ---------------------------------------- #

    def check_contract(self) -> dict:
        report = Round5Report(build=self.build, case=self.case)
        data = report.run()
        failed = [check["check"] for check in data["checks"] if not check["ok"]]
        contract_failed = failed
        self.check(
            "concern contracts still hold on the round-6 successor",
            not contract_failed and not data.get("fixtures_failed"),
            f"concern contract checks failed={len(contract_failed)}, "
            f"fixtures={data.get('fixtures_passed')}",
            {
                "failed_checks": contract_failed[:6],
                "fixtures_failed": data.get("fixtures_failed"),
                "contract_count": data.get("contract_count"),
            },
        )
        return data

    def check_word_artifacts(self) -> None:
        manifest = json.loads((self.build / "build_manifest.json").read_text(encoding="utf-8"))
        identity = manifest.get("artifact_identity", {})
        self.check(
            "Word artifacts are byte-identical (not re-rendered)",
            bool(identity) and all(entry.get("byte_identical") for entry in identity.values()),
            f"{len(identity)} artifact(s) unchanged",
            {"identity": identity},
        )

    # -- row audit --------------------------------------------------------- #

    def audit_rows(self) -> None:
        rows = {row.get("requirement_id"): row for row in self._sheet_rows(MANDATORY_SHEET)}
        for item in self.items:
            if not (
                item.marker_present or item.substantive_requirement or item.rejection_consequence
            ):
                continue
            row = rows.get(item.item_id)
            atoms = [
                str(atom_id) for atom_id in item.review_point.owned_atom_ids
            ]
            basis_records = [
                self.criticality.criticalities[atom_id].as_dict()
                for atom_id in atoms
                if atom_id in self.criticality.criticalities
                and (
                    self.criticality.criticalities[atom_id].marker_present
                    or self.criticality.criticalities[atom_id].substantive_requirement
                )
            ]
            self.row_records.append(
                {
                    "item_id": item.item_id,
                    "module": item.module,
                    "concern_id": item.concern_id,
                    "concern_label": item.concern_label,
                    "source_atom_ids": atoms,
                    "source_locator": item.source_locator,
                    "source_page": item.source_page,
                    "raw_source_markers": list(item.raw_source_markers),
                    "marker_present": item.marker_present,
                    "marker_semantics": item.marker_semantics,
                    "substantive_requirement": item.substantive_requirement,
                    "substantive_basis_kind": item.substantive_basis_kind,
                    "substantive_basis_atom_ids": list(item.substantive_basis_atom_ids),
                    "rejection_consequence": item.rejection_consequence,
                    "rejection_kind": item.rejection_kind,
                    "rejection_basis_atom_ids": list(item.rejection_basis_atom_ids),
                    "mandatory_types": list(item.mandatory_types),
                    "criticality_level": item.criticality_level,
                    "criticality_reason": item.criticality_reason,
                    "reference_parent_atom_id": item.reference_parent_atom_id,
                    "reference_target": item.reference_target,
                    "review_point_id": getattr(item.review_point, "point_id", ""),
                    "review_point_checks": list(getattr(item.review_point, "review_checks", ()) or ()),
                    "final_row": row.get("序号") if row else None,
                    "cell": {
                        "★": (row or {}).get("★", ""),
                        "否决性": (row or {}).get("否决性", ""),
                        "强制性类型": (row or {}).get("强制性类型", ""),
                        "源标记": (row or {}).get("源标记", ""),
                        "实质性依据": (row or {}).get("实质性依据", ""),
                        "否决依据": (row or {}).get("否决依据", ""),
                    },
                    "delivered_cell_prefix": str(row.get("要求正文") or "")[:40] if row else "",
                    "atom_criticalities": basis_records[:8],
                }
            )

    # -- public ------------------------------------------------------------ #

    def run(self) -> dict:
        self.audit_markers()
        self.check_marker_fixtures()
        self.check_semantics()
        self.check_governing_clause()
        self.check_references()
        self.check_consequences()
        self.check_sheet_columns()
        self.check_dashboard()
        self.check_coverage()
        self.check_sheet_surface()
        self.check_word_artifacts()
        self.audit_rows()
        contract = self.check_contract()
        failed = [check.name for check in self.checks if not check.ok]
        failed_fixtures = [
            key for key, value in self.fixtures.items() if value["status"] != "PASS"
        ]
        verdict = "PASS" if not failed and not failed_fixtures else "FAIL"
        return {
            "schema": "v1_review_workbook_round6/1",
            "case": self.case,
            "stage": self.stage,
            "build_id": self.build.name,
            "workbook": str(self.build / "投标项目复核表.xlsx"),
            "verdict": verdict,
            "check_count": len(self.checks),
            "failed_checks": failed,
            "checks": [check.as_dict() for check in self.checks],
            "fixtures": self.fixtures,
            "fixture_summary": {
                "total": len(self.fixtures),
                "passed": len(self.fixtures) - len(failed_fixtures),
                "failed": failed_fixtures,
            },
            "concern_contract_verdict": (
                "PASS"
                if not [check for check in contract["checks"] if not check["ok"]]
                and not contract.get("fixtures_failed")
                else "FAIL"
            ),
            "concern_contract": {
                "contract_source": contract.get("contract_source"),
                "contract_version": contract.get("contract_version"),
                "contract_count": contract.get("contract_count"),
                "review_row_count": contract.get("review_row_count"),
                "fixtures_passed": contract.get("fixtures_passed"),
                "failed_checks": [
                    check["check"] for check in contract["checks"] if not check["ok"]
                ],
            },
            "criticality_model": {
                "marker_count": len(self.criticality.markers),
                "source_marker_occurrence_count": (
                    self.criticality.source_marker_occurrence_count
                ),
                "raw_source_marker_discovery_count": (
                    self.criticality.raw_source_marker_discovery_count
                ),
                "duplicate_source_marker_record_count": (
                    self.criticality.duplicate_source_marker_record_count
                ),
                "marker_vocabulary": sorted(
                    {record.raw_marker for record in self.criticality.markers}
                ),
                "substantive_rules": [
                    rule.as_dict() for rule in self.criticality.substantive_rules
                ],
                "rejection_rule_count": len(self.criticality.rejection_rules),
                "reference_links": [
                    {
                        "parent_atom_id": link.parent_atom_id,
                        "parent_clause": link.parent_clause,
                        "target": link.target,
                        "target_kind": link.target_kind,
                        "child_count": len(link.target_atom_ids),
                    }
                    for link in self.criticality.reference_links
                ],
            },
            "counts": {
                "source_marker_atom_count": sum(
                    1 for record in self.criticality.criticalities.values() if record.marker_present
                ),
                "source_marked_row_count": sum(1 for item in self.items if item.marker_present),
                "substantive_requirement_row_count": sum(
                    1 for item in self.items if item.substantive_requirement
                ),
                "rejection_consequence_row_count": sum(
                    1 for item in self.items if item.rejection_consequence
                ),
                "explicit_rejection_row_count": sum(
                    1 for item in self.items if item.rejection_kind == "EXPLICIT"
                ),
                "derived_rejection_row_count": sum(
                    1 for item in self.items if item.rejection_kind == "DERIVED"
                ),
                "marker_lost_count": self.marker_lost_count(),
                "marker_false_positive_count": self.marker_false_positive_count,
                "marker_unattributed_count": self.marker_unattributed_count,
                "marker_unresolved_count": self.marker_unresolved_count,
                "direct_delivered_marker_visibility_failures": (
                    self.direct_marker_visibility_failures
                ),
                "reference_parent_coverage_failures": (
                    self.reference_parent_coverage_failures
                ),
                "source_marker_occurrence_count": (
                    self.criticality.source_marker_occurrence_count
                ),
                "raw_source_marker_discovery_count": (
                    self.criticality.raw_source_marker_discovery_count
                ),
                "duplicate_source_marker_record_count": (
                    self.criticality.duplicate_source_marker_record_count
                ),
                "source_marker_evidence_count": len(self.criticality.markers),
                "direct_source_marked_review_row_count": self.criticality_counts.get(
                    "direct_source_marked_review_row_count", 0
                ),
                "substantive_review_row_count": self.criticality_counts.get(
                    "substantive_review_row_count", 0
                ),
                "marker_carrying_source_atom_count": self.criticality_counts.get(
                    "marker_carrying_source_atom_count", 0
                ),
                "source_substantive_requirement_without_review_coverage_count": (
                    self.uncovered_substantive_count
                ),
                "source_substantive_actionable_uncovered_count": (
                    self.uncovered_actionable_substantive_count
                ),
            },
            "marker_dispositions": self.marker_dispositions,
            "dashboard_metrics": self.dashboard_metrics,
            "marker_records": self.marker_records,
            "row_audit": self.row_records,
            "coverage_records": self.coverage_records,
        }


def marker_closure_markdown(data: dict) -> str:
    """A short, human-readable occurrence ledger for one case."""

    counts = data["counts"]
    model = data["criticality_model"]
    lines = [
        f"# Round-6 marker closure -- {data['case']}",
        "",
        f"- build: `{data['build_id']}`",
        f"- verdict: **{data['verdict']}**",
        f"- raw marker discovery records: {model['raw_source_marker_discovery_count']}",
        f"- de-duplicated source marker occurrences: {model['source_marker_occurrence_count']}",
        f"- duplicate extractor records collapsed: {model['duplicate_source_marker_record_count']}",
        f"- round-6 text-deduplicated evidence records: {model['marker_count']}",
        f"- marker-carrying source atoms: {counts['marker_carrying_source_atom_count']}",
        f"- ★ review rows: {counts['direct_source_marked_review_row_count']}",
        f"- substantive review rows (source basis): {counts['substantive_review_row_count']}",
        f"- unattributed occurrences: {counts['marker_unattributed_count']}",
        f"- unresolved occurrences: {counts['marker_unresolved_count']}",
        f"- direct-marker visibility failures: "
        f"{counts['direct_delivered_marker_visibility_failures']}",
        f"- reference-parent coverage failures: "
        f"{counts['reference_parent_coverage_failures']}",
        f"- actionable substantive uncovered: "
        f"{counts['source_substantive_actionable_uncovered_count']}",
        "",
        "## dispositions",
        "",
    ]
    for key, value in sorted(data["marker_dispositions"].items()):
        lines.append(f"- {key}: {value}")
    lines += ["", "## occurrence ledger", "", "| occurrence | marker | page | locator | disposition | rows |", "| --- | --- | --- | --- | --- | --- |"]
    for record in data["marker_records"]:
        rows = ", ".join(record["starred_rows"] or record["delivered_owner_items"]) or "-"
        if not record["delivered_owner_items"] and record["background_owner_items"]:
            rows = "background: " + ", ".join(record["background_owner_items"])
        lines.append(
            f"| {record['occurrence_id']} ({record['marker_evidence_id']}) | "
            f"{record['raw_source_marker']} | {record['page']} | {record['locator']} | "
            f"{record['disposition']} | {rows} |"
        )
    lines += ["", "## dashboard counters", "", "| counter | formula | expected | recalculated | independent | ok |", "| --- | --- | --- | --- | --- | --- |"]
    for label, metric in data["dashboard_metrics"].items():
        lines.append(
            f"| {label} | `{metric['formula']}` | {metric['expected_value']} | "
            f"{metric['recalculated_value']} | {metric['independent_value']} | "
            f"{'yes' if metric['ok'] else 'NO'} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_case_report(
    case: str,
    *,
    case_dir: Path | None = None,
    stage: str = "initial",
) -> dict:
    report = Round6Report(case, case_dir=case_dir, stage=stage)
    data = report.run()
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = (
        f"review_workbook_round6_marker_closure_{case}"
        if stage == "marker_closure"
        else f"review_workbook_round6_criticality_audit_{case}"
    )
    path = REPORTS / f"{stem}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if stage == "marker_closure":
        (REPORTS / f"{stem}.md").write_text(
            marker_closure_markdown(data), encoding="utf-8"
        )
    print(f"{case}: {data['verdict']} ({len(data['failed_checks'])} failed check(s)) -> {path.name}")
    for check in data["checks"]:
        if not check["ok"]:
            print(f"   FAIL {check['check']}: {check['detail']}")
    for key, value in data["fixtures"].items():
        if value["status"] != "PASS":
            print(f"   FIXTURE {key}: {value['status']}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=None)
    parser.add_argument("--three-case", action="store_true")
    parser.add_argument(
        "--stage",
        choices=("initial", "marker_closure"),
        default="initial",
        help="initial = preserved round-6 audit; marker_closure = round-6 successor",
    )
    args = parser.parse_args(argv)
    cases = list(CASES) if args.three_case or not args.case else args.case
    results = {case: write_case_report(case, stage=args.stage) for case in cases}
    if len(results) > 1:
        REPORTS.mkdir(parents=True, exist_ok=True)
        summary = {
            "schema": "v1_review_workbook_round6_generalization/1",
            "stage": args.stage,
            "cases": {
                case: {
                    "verdict": data["verdict"],
                    "failed_checks": data["failed_checks"],
                    "failed_fixtures": data["fixture_summary"]["failed"],
                    "marker_vocabulary": data["criticality_model"]["marker_vocabulary"],
                    "counts": data["counts"],
                }
                for case, data in results.items()
            },
            "verdict": (
                "PASS" if all(data["verdict"] == "PASS" for data in results.values()) else "FAIL"
            ),
        }
        name = (
            "review_workbook_round6_generalization_marker_closure.json"
            if args.stage == "marker_closure"
            else "review_workbook_round6_generalization.json"
        )
        path = REPORTS / name
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"generalization: {summary['verdict']} -> {path.name}")
    return 0 if all(data["verdict"] == "PASS" for data in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
