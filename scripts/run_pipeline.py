"""Minimal local V1 pipeline from one tender document to reviewed outputs."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.bid_document_builder import build_bid_document, build_repaired_source_model
from tender_basic.delivery_qa import run_delivery_qa, write_qa_report
from tender_basic.document_models import DocumentStatus
from tender_basic.dynamic_review import build_dynamic_review_plan, dynamic_review_qa
from tender_basic.document_parser import (
    exit_code_for_status,
    parse_document,
    write_normalized_outputs,
)
from tender_basic.fact_extractor import extract_candidates
from tender_basic.fact_normalizer import normalize_candidates
from tender_basic.fact_resolver import build_review_packet, resolve_project_facts
from tender_basic.format_extractor import extract_bid_format
from tender_basic.review_builder import build_review_workbook
from tender_basic.review_builder import count_stray_review_rows
from tender_basic.review_builder import read_dynamic_review_rows
from tender_basic.review_evidence import (
    retrieve_review_evidence,
    review_evidence_qa,
    validate_review_evidence,
)
from tender_basic.source_format import build_source_format_model
from tender_basic.source_format_qa import build_source_format_qa, write_source_format_qa
from tender_basic.semantic_candidates import (
    apply_semantic_candidate_proposals,
    build_fact_gap_packet,
)


EXIT_PIPELINE_FAILED = 2
EXIT_PROGRAM_ERROR = 3

_DOWNSTREAM_ARTIFACTS = (
    "normalized_document.json",
    "document.lines.txt",
    "project_facts.json",
    "facts_review_packet.json",
    "fact_gap_packet.json",
    "semantic_candidate_results.json",
    "generation_report.json",
    "source_format_qa.json",
    "review_evidence_packet.json",
    "review_evidence_qa.json",
    "metadata.json",
    "投标项目复核表.xlsx",
    "基础投标文件.docx",
    "qa_report.json",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the minimal V1 tender normalization, facts, output, and QA pipeline."
    )
    parser.add_argument("input_file", type=Path, help="Input PDF or DOCX path")
    parser.add_argument("--output", required=True, type=Path, dest="output_dir")
    parser.add_argument("--verbose", action="store_true", help="Print traceback on program error")
    parser.add_argument(
        "--semantic-proposals",
        type=Path,
        help="Optional WorkBuddy SemanticCandidateProposal JSON input",
    )
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _clear_downstream_artifacts(output_dir: Path) -> None:
    """Remove only known V1 downstream outputs to avoid stale success artifacts."""

    for name in _DOWNSTREAM_ARTIFACTS:
        path = output_dir / name
        if path.is_file():
            path.unlink()


def _print_artifacts(output_dir: Path) -> None:
    print("Artifacts:")
    for name in _DOWNSTREAM_ARTIFACTS:
        print(f"  {name}")


def _load_semantic_proposals(path: Path | None) -> list[object]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("proposals", [])
    if not isinstance(payload, list):
        raise ValueError("Semantic proposals must be a JSON list or {proposals: [...]} object")
    return payload


def run_pipeline(
    input_file: str | Path,
    output_dir: str | Path,
    *,
    semantic_proposals_path: str | Path | None = None,
) -> int:
    """Run the six V1 stages without invoking subprocesses or an external model."""

    input_path = Path(input_file)
    # Round 5.6: the builder measures rendered source glyph weight and page
    # geometry from the real source file, so it needs the document it renders.
    source_path = str(input_path.resolve())
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _clear_downstream_artifacts(output_path)

    document = parse_document(input_path)
    normalized_path, lines_path = write_normalized_outputs(document, output_path)
    if document.status != DocumentStatus.PARSED:
        print(f"Status: {document.status.value}")
        print(f"Normalized JSON: {normalized_path}")
        print(f"Lines: {lines_path}")
        if document.status == DocumentStatus.OCR_REQUIRED:
            print("Pipeline stopped: source document requires OCR before fact extraction.")
        return exit_code_for_status(document.status)

    try:
        raw_candidates = extract_candidates(
            document,
            aliases_path=ROOT / "rules" / "field_aliases.yaml",
        )
        normalized_candidates = normalize_candidates(raw_candidates)
        project_facts = resolve_project_facts(
            document,
            normalized_candidates,
            source_priority_path=ROOT / "rules" / "source_priority.yaml",
        )
        _write_json(output_path / "fact_gap_packet.json", build_fact_gap_packet(project_facts))
        semantic_proposals = _load_semantic_proposals(
            Path(semantic_proposals_path) if semantic_proposals_path is not None else None
        )
        project_facts, semantic_result = apply_semantic_candidate_proposals(
            document,
            project_facts,
            semantic_proposals,
            source_priority_path=str(ROOT / "rules" / "source_priority.yaml"),
        )
        project_facts_path = output_path / "project_facts.json"
        _write_json(project_facts_path, project_facts.model_dump(mode="json"))
        _write_json(output_path / "facts_review_packet.json", build_review_packet(project_facts))
        _write_json(output_path / "semantic_candidate_results.json", semantic_result)

        format_template = extract_bid_format(document)
        # The source-format QA must compare the DOCX with the same repaired model
        # the builder emitted, otherwise a geometry-backed glyph repair reads as
        # missing source text.
        source_format_model, _source_text_qa = build_repaired_source_model(document, format_template)
        review_items, review_packet = retrieve_review_evidence(
            document,
            format_template=format_template,
        )
        review_validation = validate_review_evidence(document, review_items)

        # Round 5.5: the delivered workbook's substantive rows are generated
        # from the real source requirements, not from the fixed 1..64 taxonomy.
        # The dynamic payload rides the review QA artifact, so the frozen
        # 14-artifact contract and the array-shaped evidence packet are intact.
        dynamic_plan = build_dynamic_review_plan(document, project_facts)

        xlsx_path = output_path / "投标项目复核表.xlsx"
        docx_path = output_path / "基础投标文件.docx"
        build_review_workbook(
            project_facts,
            xlsx_path,
            normalized_document=document,
            format_template=format_template,
            review_evidence=review_items,
            dynamic_plan=dynamic_plan,
        )
        review_qa = review_evidence_qa(
            review_items,
            review_validation,
            stray_rows=count_stray_review_rows(xlsx_path),
        )
        dynamic_review_qa_result = dynamic_review_qa(
            dynamic_plan,
            document,
            project_facts,
            workbook_rows=read_dynamic_review_rows(xlsx_path),
        )
        review_qa = {
            **review_qa,
            "dynamic_review": {
                "architecture": "SOURCE_FORMAT_FIRST_DYNAMIC_REVIEW_ITEMS",
                "row_contract": "review rows are generated from the tender document",
                "source_requirement_index": {
                    "source_fragment_count": dynamic_plan.index.scanned_fragments,
                    "source_requirement_count": dynamic_plan.source_requirement_count,
                    "source_requirement_by_type": dynamic_plan.index.by_type(),
                    "merged_duplicate_count": dynamic_plan.dropped_duplicate_count,
                    "dropped_navigation_fragment_count": dynamic_plan.index.dropped_navigation,
                    "dropped_heading_fragment_count": dynamic_plan.index.dropped_heading,
                    "dropped_short_fragment_count": dynamic_plan.index.dropped_short,
                    "dropped_procedural_fragment_count": dynamic_plan.index.dropped_procedural,
                },
                "dynamic_item_count": len(dynamic_plan.items),
                "items_by_module": dynamic_plan.module_counts(),
                "items": [
                    item.model_dump(mode="json") for item in dynamic_plan.items
                ],
                "qa": dynamic_review_qa_result,
            },
        }
        _write_json(output_path / "review_evidence_packet.json", review_packet)
        _write_json(output_path / "review_evidence_qa.json", review_qa)
        build_bid_document(
            project_facts,
            docx_path,
            normalized_document=document,
            format_template=format_template,
            generation_report_path=output_path / "generation_report.json",
            source_path=source_path,
        )

        generation_report_path = output_path / "generation_report.json"
        generation_report = (
            json.loads(generation_report_path.read_text(encoding="utf-8"))
            if generation_report_path.is_file()
            else {}
        )
        if source_format_model.source_pages:
            source_format_qa = build_source_format_qa(
                source_format_model,
                project_facts,
                docx_path,
                generation_report=generation_report,
            )
        else:
            source_format_qa = {
                "schema_version": "1.0",
                "page_count_source_format": 0,
                "page_count_generated": None,
                "paragraph_count": 0,
                "source_paragraph_count": 0,
                "generated_textbox_count": 0,
                "table_count": 0,
                "source_table_count": 0,
                "merged_cell_match": True,
                "font_family_match_rate": None,
                "font_size_match_rate": None,
                "paragraph_alignment_match_rate": None,
                "paragraph_spacing_match_rate": None,
                "table_geometry_match_rate": None,
                "fill_slots_detected": 0,
                "fill_slots_filled": 0,
                "fill_slots_left_blank": 0,
                "unexpected_text_insertions": [],
                "source_text_missing": 0,
                "source_text_reordered": 0,
                "font_substitutions": [],
                "font_repairs": [],
                "layout_warnings": ["No usable source-format page model was found."],
                "result": "NOT_APPLICABLE",
            }
        write_source_format_qa(source_format_qa, output_path / "source_format_qa.json")

        # The logical table contract travels with the format metadata so Delivery
        # QA can require one editable DOCX table per logical table instead of one
        # per PDF page fragment.
        format_metadata = dict(format_template.metadata())
        for key in (
            "logical_table_count",
            "pdf_table_fragment_count",
            "continuation_fragments_merged",
            "orphan_continuation_fragments",
            "false_continuation_merges",
        ):
            if key in generation_report:
                format_metadata[key] = generation_report[key]
        report = run_delivery_qa(
            project_facts_path,
            xlsx_path,
            docx_path,
            format_source=format_template.format_source,
            format_metadata=format_metadata,
            review_evidence_qa=review_qa,
        )
        report_path = write_qa_report(report, output_path / "qa_report.json")
        _write_json(
            output_path / "metadata.json",
            {
                "schema_version": "1.0",
                "pipeline_run": "run_4_1",
                "source_file": document.source_file,
                "source_type": document.source_type.value if document.source_type else None,
                "format_source": format_template.format_source,
                "format_metadata": format_template.metadata(),
                "source_format_model": {
                    "page_count": source_format_model.page_count,
                    "source_table_count": source_format_model.source_table_count,
                    "fill_slots_detected": len(source_format_model.fill_slots),
                    "chrome_items_excluded": len(source_format_model.chrome_items),
                },
                "artifacts": list(_DOWNSTREAM_ARTIFACTS),
            },
        )
    except Exception as exc:
        print("Status: DELIVERY_FAILED")
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_PROGRAM_ERROR

    summary = project_facts.summary
    pipeline_status = {
        "PASS": "READY_FOR_REVIEW",
        "PASS_WITH_REVIEW": "REVIEW_REQUIRED",
        "FAIL": "DELIVERY_FAILED",
    }[report["overall_status"]]
    print(f"Status: {pipeline_status}")
    print(f"Source: {document.source_file}")
    print()
    print("Fields:")
    print(f"  RESOLVED:     {summary.resolved}")
    print(f"  NEEDS_REVIEW: {summary.needs_review}")
    print(f"  NOT_FOUND:    {summary.not_found}")
    print()
    print(f"QA: {report['overall_status']}")
    print(f"Format source: {report.get('format_source', 'UNKNOWN')}")
    print(f"QA report: {report_path}")
    _print_artifacts(output_path)
    return 0 if report["overall_status"] in {"PASS", "PASS_WITH_REVIEW"} else EXIT_PIPELINE_FAILED


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run_pipeline(
            args.input_file,
            args.output_dir,
            semantic_proposals_path=args.semantic_proposals,
        )
    except Exception as exc:  # pragma: no cover - defensive CLI boundary.
        print("Status: DELIVERY_FAILED")
        print(f"Error: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_PROGRAM_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
