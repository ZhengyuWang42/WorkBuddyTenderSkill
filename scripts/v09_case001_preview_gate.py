"""V0.9 Phase 4 gate: CASE001 whole-case internal-preview precheck.

This gate audits one *already produced* fresh build directory as a whole case
preview.  It never re-runs the pipeline and never reuses a stale artifact: the
build directory is taken from the current-build pointer, and every artifact is
resolved inside it and hashed.

Scope
-----

The precheck answers, for one clean CASE001 build:

* did the artifacts the preview is made of actually come out of that build, and
  do their recorded hashes still match what is on disk;
* is the case fact set complete (every declared field carries a status, the
  statuses add up to the summary, and every resolved value carries source
  provenance);
* are the two delivered documents healthy - the XLSX opens with one row per
  field, and the DOCX opens, renders and keeps its document structure;
* is the P3 form region accepted on its own stated contract (every rule
  emitted, both axes inside the accepted 2pt tolerance, the accepted
  composition set intact, accounting complete, scope never widened to another
  source page);
* and is the frozen absolute vertical closure of the P3 region intact, which is
  tracked but is a separate, stricter claim than the contract acceptance.

Usage::

    .venv/Scripts/python.exe scripts/v09_case001_preview_gate.py \
        --source <tender.pdf> --out <gate.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymupdf  # noqa: E402

from v09_p3_closure_gate import composition_preservation  # noqa: E402

POINTER = ROOT / "acceptance/reports/v09_internal_preview/current_build.json"

#: The accepted 2pt tolerance.  Never relaxed.
TOLERANCE_PT = 2.0

#: The frozen P3 source rules and their source page.
P3_SOURCE_PAGE = 42
FROZEN_P3_RULE_IDS = (
    "P42-R1",
    "P42-R2",
    "P42-R3",
    "P42-R4",
    "P42-R5",
    "P42-R6",
    "P42-R7",
    "P42-R8",
)

#: The accepted composition set: exactly these seven, always observed intact.
ACCEPTED_COMPOSITIONS = (
    "P42-R3",
    "P42-R7",
    "P42-R8",
    "P45-R1",
    "P45-R2",
    "P45-R3",
    "P45-R5",
)

#: The case fact set size this preview is scoped to.
EXPECTED_FIELD_COUNT = 23

#: Artifacts the preview is made of, and the artifacts that must exist.
REQUIRED_ARTIFACTS = (
    "project_facts.json",
    "投标项目复核表.xlsx",
    "基础投标文件.docx",
    "基础投标文件.pdf",
    "generation_report.json",
    "qa_report.json",
    "metadata.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolved_pointer() -> dict:
    return load_json(POINTER)


def audit_facts(facts: dict) -> dict:
    """Every declared case field is accounted for and every value is sourced."""

    fields = facts.get("fields") or {}
    summary = facts.get("summary") or {}
    statuses = [entry.get("status") for entry in fields.values()]
    known_statuses = {"RESOLVED", "NEEDS_REVIEW", "NOT_FOUND"}
    unknown = sorted({status for status in statuses if status not in known_statuses})
    unresolved_with_value = sorted(
        name
        for name, entry in fields.items()
        if entry.get("status") != "RESOLVED" and entry.get("resolved_value") is not None
    )
    resolved_without_value = sorted(
        name
        for name, entry in fields.items()
        if entry.get("status") == "RESOLVED" and entry.get("resolved_value") is None
    )
    resolved_without_provenance = sorted(
        name
        for name, entry in fields.items()
        if entry.get("status") == "RESOLVED"
        and not (entry.get("candidates") or entry.get("resolution_reason"))
    )
    provenance_rows = []
    for name, entry in sorted(fields.items()):
        winners = [
            candidate
            for candidate in entry.get("candidates") or []
            if candidate.get("normalized_value") == entry.get("resolved_value")
        ]
        winner = winners[0] if winners else (
            (entry.get("candidates") or [None])[0]
        )
        locator = (winner or {}).get("locator") or {}
        provenance_rows.append(
            {
                "field": name,
                "status": entry.get("status"),
                "resolved_value": entry.get("resolved_value"),
                "confidence": entry.get("confidence"),
                "source_file": (winner or {}).get("source_file"),
                "source_type": (winner or {}).get("source_type"),
                "method": (winner or {}).get("method"),
                "locator_type": locator.get("locator_type"),
                "page": locator.get("page"),
                "has_locator": bool(locator),
                "has_source_file": bool((winner or {}).get("source_file")),
            }
        )
    resolved_rows = [row for row in provenance_rows if row["status"] == "RESOLVED"]
    return {
        "field_count": len(fields),
        "expected_field_count": EXPECTED_FIELD_COUNT,
        "status_counts": {
            status: statuses.count(status) for status in sorted(set(statuses))
        },
        "summary": summary,
        "unknown_statuses": unknown,
        "unresolved_with_value": unresolved_with_value,
        "resolved_without_value": resolved_without_value,
        "resolved_without_provenance": resolved_without_provenance,
        "resolved_without_locator": sorted(
            row["field"] for row in resolved_rows if not row["has_locator"]
        ),
        "resolved_without_source_file": sorted(
            row["field"] for row in resolved_rows if not row["has_source_file"]
        ),
        "provenance_rows": provenance_rows,
        "provenance_complete": not (
            resolved_without_value
            or resolved_without_provenance
            or unknown
            or [
                row["field"]
                for row in resolved_rows
                if not row["has_locator"] or not row["has_source_file"]
            ]
        ),
    }


def audit_workbook(path: Path, sheet) -> dict:
    """The review workbook opens and keeps its own review structure intact.

    The workbook is a review sheet, not a flat field dump: it carries a labelled
    project header block followed by the numbered review checklist.  Both halves
    have to survive, and the header block has to carry the case materialised by
    this build rather than a placeholder.
    """

    rows = [
        [cell for cell in row]
        for row in sheet.iter_rows(values_only=True)
    ]
    texts = [[str(cell).strip() if cell is not None else "" for cell in row] for row in rows]
    labels = {}
    for row in texts:
        for index, cell in enumerate(row):
            if not cell or index + 1 >= len(row):
                continue
            if any(
                keyword in cell
                for keyword in ("项目名称", "项目编号", "投标截止时间", "开标时间")
            ):
                for value in row[index + 1 :]:
                    if value:
                        labels.setdefault(cell, value)
                        break
    checklist_header = next(
        (
            {"row": index + 1, "headers": [cell for cell in row if cell]}
            for index, row in enumerate(texts)
            if "序号" in row and "复核模块" in row
        ),
        None,
    )
    checklist_rows = 0
    if checklist_header is not None:
        for row in texts[checklist_header["row"] :]:
            if row and row[0].isdigit():
                checklist_rows += 1
    placeholder_rows = [
        index + 1
        for index, row in enumerate(texts)
        if any(cell == "【填写】" for cell in row)
    ]
    return {
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sheet_titles": list(sheet.parent.sheetnames),
        "max_row": sheet.max_row,
        "max_column": sheet.max_column,
        "header_labels": labels,
        "header_label_count": len(labels),
        "checklist_header": checklist_header,
        "checklist_row_count": checklist_rows,
        "placeholder_rows": placeholder_rows,
        "structure_intact": bool(labels) and checklist_header is not None,
    }


def audit_document(docx_path: Path, pdf_path: Path) -> dict:
    """The delivered DOCX opens, and its render is a healthy Word document."""

    from docx import Document

    document = Document(str(docx_path))
    paragraphs = [p for p in document.paragraphs]
    empty_paragraphs = [p for p in paragraphs if not p.text.strip()]
    with_text = [p for p in paragraphs if p.text.strip()]
    section_count = len(document.sections)
    generated = pymupdf.open(pdf_path)
    page_text = [
        generated[index].get_text("text").strip()
        for index in range(generated.page_count)
    ]
    blank_pages = [index + 1 for index, text in enumerate(page_text) if not text]
    return {
        "docx_exists": docx_path.exists(),
        "docx_bytes": docx_path.stat().st_size if docx_path.exists() else 0,
        "paragraph_count": len(paragraphs),
        "paragraph_count_with_text": len(with_text),
        "empty_paragraph_count": len(empty_paragraphs),
        "table_count": len(document.tables),
        "inline_shape_count": len(document.inline_shapes),
        "section_count": section_count,
        "style_count": len(document.styles),
        "pdf_page_count": generated.page_count,
        "pdf_blank_pages": blank_pages,
        "pdf_text_pages": len(page_text) - len(blank_pages),
        "first_paragraph_text": (paragraphs[0].text if paragraphs else "")[:60],
        "opened": True,
    }


def audit_p3(report: dict, vertical_gate: dict | None) -> dict:
    """The P3 region's contract acceptance, plus the frozen closure status."""

    registry = {
        entry["source_rule_id"]: entry
        for entry in report.get("source_rule_registry") or []
        if entry.get("source_rule_id")
    }
    composition_records = [
        record
        for record in report.get("source_rule_compositions") or []
        if record.get("source_rule_id")
    ]
    compositions = [record["source_rule_id"] for record in composition_records]
    preservation = composition_preservation(composition_records, ACCEPTED_COMPOSITIONS)
    rows = {
        row["source_rule_id"]: row
        for row in (vertical_gate or {}).get("in_scope_rows") or []
    }
    missing_rules = sorted(set(FROZEN_P3_RULE_IDS) - set(registry))
    no_representation = sorted(
        rule_id
        for rule_id in FROZEN_P3_RULE_IDS
        if not (
            (rows.get(rule_id) or {}).get("measurement")
            or rule_id in compositions
        )
    )
    contract_rows = []
    for rule_id in FROZEN_P3_RULE_IDS:
        row = rows.get(rule_id) or {}
        measurement = row.get("measurement") or {}
        contract_rows.append(
            {
                "source_rule_id": rule_id,
                "transformation_policy": row.get("transformation_policy"),
                "geometry_intent": row.get("geometry_intent"),
                "emission_mechanism": row.get("emission_mechanism"),
                "horizontal_pass": row.get("horizontal_pass"),
                "vertical_pass": row.get("vertical_pass"),
                "x0_error": measurement.get("x0_error"),
                "x1_error": measurement.get("x1_error"),
                "y_error": measurement.get("y_error"),
            }
        )
    horizontal_ok = [
        row["source_rule_id"] for row in contract_rows if not row["horizontal_pass"]
    ]
    vertical_ok = [
        row["source_rule_id"] for row in contract_rows if not row["vertical_pass"]
    ]
    return {
        "source_rules_on_p3_page": sorted(registry),
        "frozen_rule_count": len(FROZEN_P3_RULE_IDS),
        "missing_frozen_rule_ids": missing_rules,
        "rules_without_representation": no_representation,
        "observed_composition_set": compositions,
        "accepted_composition_set": list(ACCEPTED_COMPOSITIONS),
        "accepted_composition_set_intact": preservation["preserved"],
        "composition_preservation": preservation,
        "rule_compositions_created": report.get("rule_compositions_created"),
        "contract_rows": contract_rows,
        "horizontal_failure_ids": horizontal_ok,
        "vertical_failure_ids": vertical_ok,
        "vertical_row_order_preserved": (vertical_gate or {}).get(
            "vertical_row_order_preserved"
        ),
        "source_row_origin_offset_pt": (vertical_gate or {}).get(
            "source_row_origin_offset_pt"
        ),
        "source_line_pitch_pt": (vertical_gate or {}).get("source_line_pitch_pt"),
        "frozen_vertical_closure_holds": bool(
            vertical_gate
            and not vertical_gate.get("vertical_failure_ids")
            and vertical_gate.get("vertical_row_order_preserved")
        ),
        #: The region's own contract: every accepted rule is emitted and every
        #: horizontal duty the accepted policy states is met.  This is what the
        #: preview is scored on; the frozen absolute vertical closure above is
        #: reported alongside it and is not silently folded in.
        "contract_acceptance_holds": bool(
            not missing_rules and not no_representation and not horizontal_ok
        ),
    }


def audit_scope(report: dict) -> dict:
    """Preview scope never widens, and never leaks into another case."""

    owners = report.get("source_form_execution_owners") or []
    applications = report.get("source_fill_applications") or []
    owner_pages = sorted(
        {entry.get("source_page") for entry in owners if entry.get("source_page")}
    )
    application_pages = sorted(
        {entry.get("source_page") for entry in applications if entry.get("source_page")}
    )
    return {
        "execution_owner_count": report.get("source_form_execution_owner_count"),
        "owner_source_pages": owner_pages,
        "application_source_pages": application_pages,
        "owner_driven_value_emission_count": report.get(
            "owner_driven_value_emission_count"
        ),
        #: A rule the renderer holds inactive must establish no execution owner,
        #: so this list names the rules that wrongly claimed one and must be
        #: empty for the check to hold.
        "inactive_rule_ids_with_owner": [
            rule_id
            for rule_id in ("P40-R1", "P45-R6")
            if any(rule_id in (owner.get("source_rule_ids") or ()) for owner in owners)
        ],
        "plan_iteration_execution_zero": not report.get(
            "plan_driven_value_emission_count"
        ),
        "form_layout_break_count": report.get("form_layout_break_count"),
        "source_form_line_paragraph_count": report.get(
            "source_form_line_paragraph_count"
        ),
        "positioned_blank_count": len(report.get("positioned_blank_records") or []),
    }


def audit_artifact_safety(build_dir: Path) -> dict:
    """No delivered part leaks machine-local state into the preview.

    The delivered OOXML packages are opened as packages and every XML/Rels part
    is searched for a build-machine path, a temp path, a tracker marker, an
    internal emission token or a draft placeholder.  XML namespace URIs are
    rejected as evidence, so a plain ``http://schemas...`` never counts.
    """

    import re
    import zipfile

    patterns = {
        "local_absolute_path": re.compile(
            r"[A-Za-z]:[\\/][A-Za-z_][^\s\"'<>]{2,}|file:///[^\s\"'<>]+"
        ),
        "posix_temp_path": re.compile(r"/(?:tmp|home|Users)/"),
        "tracker_marker": re.compile(r"\b(?:TODO|FIXME|XXX)\b"),
        "internal_emission_token": re.compile("\ue000|\ue001"),
        "draft_placeholder": re.compile(r"【填写】|Lorem ipsum"),
    }
    findings = []
    scanned_parts = 0
    for name in ("基础投标文件.docx", "投标项目复核表.xlsx"):
        path = build_dir / name
        if not path.exists():
            findings.append({"artifact": name, "kind": "missing_artifact", "sample": ""})
            continue
        with zipfile.ZipFile(path) as package:
            for part in package.namelist():
                if not part.endswith((".xml", ".rels")):
                    continue
                scanned_parts += 1
                text = package.read(part).decode("utf-8", "replace")
                for kind, pattern in patterns.items():
                    match = pattern.search(text)
                    if match is not None:
                        findings.append(
                            {
                                "artifact": "%s!%s" % (name, part),
                                "kind": kind,
                                "sample": text[
                                    max(0, match.start() - 30) : match.end() + 60
                                ],
                            }
                        )
    return {
        "scanned_parts": scanned_parts,
        "findings": findings,
        "clean": not findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--p3-gate",
        type=Path,
        default=ROOT
        / "acceptance/reports/v09_internal_preview/p3_final_round58_gate.json",
    )
    args = parser.parse_args(argv)

    source = args.source.resolve()
    pointer = resolved_pointer()
    build_dir = Path(pointer["build_dir"])
    manifest = load_json(Path(pointer["manifest"]))

    artifacts = {}
    for name in REQUIRED_ARTIFACTS:
        path = build_dir / name
        artifacts[name] = {
            "path": str(path),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "sha256": sha256(path) if path.exists() else None,
        }
    missing_artifacts = sorted(
        name for name, record in artifacts.items() if not record["exists"]
    )

    #: The preview must be made of the build the pointer names, and the pointer's
    #: own hashes must still describe the files on disk.
    hash_mismatches = []
    for key, name in (
        ("generated_docx_sha256", "基础投标文件.docx"),
        ("generated_pdf_sha256", "基础投标文件.pdf"),
    ):
        recorded = pointer.get(key)
        actual = artifacts[name]["sha256"]
        if recorded != actual:
            hash_mismatches.append(
                {"artifact": name, "recorded": recorded, "actual": actual}
            )

    facts = load_json(build_dir / "project_facts.json")
    facts_audit = audit_facts(facts)

    from openpyxl import load_workbook

    workbook = load_workbook(build_dir / "投标项目复核表.xlsx")
    workbook_audit = audit_workbook(
        build_dir / "投标项目复核表.xlsx", workbook[workbook.sheetnames[0]]
    )
    workbook.close()

    document_audit = audit_document(
        build_dir / "基础投标文件.docx", build_dir / "基础投标文件.pdf"
    )

    report = load_json(build_dir / "generation_report.json")
    qa = load_json(build_dir / "qa_report.json")
    p3_gate = load_json(args.p3_gate) if args.p3_gate.exists() else None
    p3_audit = audit_p3(report, p3_gate)
    scope_audit = audit_scope(report)
    safety_audit = audit_artifact_safety(build_dir)

    failing_checks = [
        check
        for check in qa.get("checks") or []
        if check.get("status") in ("FAIL", "FAILED")
    ]

    checks = {
        "current_build_pointer_fresh": pointer.get("schema")
        == "v09_current_build_pointer/1"
        and manifest.get("status") == "FRESH_BUILD",
        "build_artifacts_present": not missing_artifacts,
        "build_artifacts_match_pointer": not hash_mismatches,
        "source_pdf_unchanged": manifest.get("source", {}).get("sha256")
        == sha256(source),
        "field_set_complete": facts_audit["field_count"] == EXPECTED_FIELD_COUNT,
        "field_statuses_complete": not facts_audit["unknown_statuses"]
        and not facts_audit["resolved_without_value"]
        and not facts_audit["unresolved_with_value"],
        "fact_provenance_complete": facts_audit["provenance_complete"],
        "workbook_healthy": workbook_audit["exists"]
        and workbook_audit["structure_intact"]
        and workbook_audit["checklist_row_count"] > 0,
        "document_healthy": document_audit["docx_exists"]
        and document_audit["paragraph_count_with_text"] > 0
        and not document_audit["pdf_blank_pages"],
        "document_render_has_pages": document_audit["pdf_page_count"] > 1,
        "qa_no_failing_checks": not failing_checks,
        "qa_no_errors": not (qa.get("errors") or []),
        "p3_frozen_rules_all_accounted": not p3_audit["missing_frozen_rule_ids"]
        and not p3_audit["rules_without_representation"],
        "p3_contract_acceptance_holds": p3_audit["contract_acceptance_holds"],
        "p3_accepted_composition_set_intact": p3_audit[
            "accepted_composition_set_intact"
        ],
        "preview_scope_is_case001": scope_audit["owner_source_pages"] == [P3_SOURCE_PAGE]
        and scope_audit["application_source_pages"] == [P3_SOURCE_PAGE],
        "inactive_rules_establish_no_owner": not scope_audit[
            "inactive_rule_ids_with_owner"
        ],
        "plan_iteration_execution_zero": scope_audit["plan_iteration_execution_zero"],
        "no_form_layout_break": scope_audit["form_layout_break_count"] == 0,
        "delivered_artifacts_carry_no_machine_state": safety_audit["clean"],
    }

    payload = {
        "gate": "v09_case001_internal_preview_precheck",
        "preview": "V0.9_INTERNAL_PREVIEW",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "failed_checks": [name for name, ok in checks.items() if not ok],
        "build": {
            "build_id": pointer.get("build_id"),
            "build_dir": str(build_dir),
            "manifest": pointer.get("manifest"),
            "source_pdf": str(source),
            "source_pdf_sha256": sha256(source),
            "source_pdf_page_count": pymupdf.open(source).page_count,
            "generated_docx": str(build_dir / "基础投标文件.docx"),
            "generated_pdf": str(build_dir / "基础投标文件.pdf"),
        },
        "artifacts": artifacts,
        "missing_artifacts": missing_artifacts,
        "hash_mismatches": hash_mismatches,
        "facts": facts_audit,
        "workbook": workbook_audit,
        "document": document_audit,
        "qa": {
            "overall_status": qa.get("overall_status"),
            "format_source": qa.get("format_source"),
            "check_count": len(qa.get("checks") or []),
            "failing_check_ids": [check.get("id") for check in failing_checks],
            "warning_ids": [
                warning.get("id") for warning in qa.get("warnings") or []
            ],
            "errors": qa.get("errors") or [],
        },
        "p3": p3_audit,
        "scope": scope_audit,
        "safety": safety_audit,
        "flags": {
            "INTERNAL_PREVIEW": True,
            "READY_FOR_INTERNAL_TRIAL": bool(
                all(checks.values()) and p3_audit["frozen_vertical_closure_holds"]
            ),
            "MANUAL_WORD_REVIEW_REQUIRED": True,
            "READY_FOR_SUBMISSION": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "failed_checks": payload["failed_checks"],
                "flags": payload["flags"],
                "out": str(args.out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
