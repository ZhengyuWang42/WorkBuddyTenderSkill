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

from tender_basic.bid_document_builder import build_bid_document
from tender_basic.delivery_qa import run_delivery_qa, write_qa_report
from tender_basic.document_models import DocumentStatus
from tender_basic.document_parser import (
    exit_code_for_status,
    parse_document,
    write_normalized_outputs,
)
from tender_basic.fact_extractor import extract_candidates
from tender_basic.fact_normalizer import normalize_candidates
from tender_basic.fact_resolver import build_review_packet, resolve_project_facts
from tender_basic.review_builder import build_review_workbook


EXIT_PIPELINE_FAILED = 2
EXIT_PROGRAM_ERROR = 3

_DOWNSTREAM_ARTIFACTS = (
    "project_facts.json",
    "facts_review_packet.json",
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
    for name in (
        "normalized_document.json",
        "document.lines.txt",
        "project_facts.json",
        "facts_review_packet.json",
        "投标项目复核表.xlsx",
        "基础投标文件.docx",
        "qa_report.json",
    ):
        print(f"  {name}")


def run_pipeline(input_file: str | Path, output_dir: str | Path) -> int:
    """Run the six V1 stages without invoking subprocesses or an external model."""

    input_path = Path(input_file)
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
        project_facts_path = output_path / "project_facts.json"
        _write_json(project_facts_path, project_facts.model_dump(mode="json"))
        _write_json(output_path / "facts_review_packet.json", build_review_packet(project_facts))

        xlsx_path = output_path / "投标项目复核表.xlsx"
        docx_path = output_path / "基础投标文件.docx"
        build_review_workbook(project_facts, xlsx_path)
        build_bid_document(project_facts, docx_path)

        report = run_delivery_qa(project_facts_path, xlsx_path, docx_path)
        report_path = write_qa_report(report, output_path / "qa_report.json")
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
    print(f"QA report: {report_path}")
    _print_artifacts(output_path)
    return 0 if report["overall_status"] in {"PASS", "PASS_WITH_REVIEW"} else EXIT_PIPELINE_FAILED


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return run_pipeline(args.input_file, args.output_dir)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary.
        print("Status: DELIVERY_FAILED")
        print(f"Error: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_PROGRAM_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
