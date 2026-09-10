"""CLI for extracting deterministic ProjectFacts from normalized JSON."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from tender_basic.document_models import DocumentStatus, NormalizedDocument
from tender_basic.fact_extractor import extract_candidates
from tender_basic.fact_normalizer import normalize_candidates
from tender_basic.fact_resolver import build_review_packet, resolve_project_facts


EXIT_OK = 0
EXIT_INPUT_ERROR = 3
EXIT_OCR_REQUIRED = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract V1 ProjectFacts from normalized_document.json."
    )
    parser.add_argument("input", type=Path, help="Path to normalized_document.json")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a traceback for development errors",
    )
    return parser


def _load_document(path: Path) -> NormalizedDocument:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return NormalizedDocument.model_validate(payload)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        document = _load_document(args.input)
        if document.status == DocumentStatus.OCR_REQUIRED:
            print("Source document requires OCR before fact extraction.", file=sys.stderr)
            return EXIT_OCR_REQUIRED
        if document.status != DocumentStatus.PARSED or document.source_type is None:
            print(
                f"Cannot extract facts from document status {document.status.value}.",
                file=sys.stderr,
            )
            return EXIT_INPUT_ERROR

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
        review_packet = build_review_packet(project_facts)

        args.output.mkdir(parents=True, exist_ok=True)
        project_facts_path = args.output / "project_facts.json"
        review_packet_path = args.output / "facts_review_packet.json"
        _write_json(project_facts_path, project_facts.model_dump(mode="json"))
        _write_json(review_packet_path, review_packet)

        summary = project_facts.summary
        print("Status: OK")
        print(f"Source: {document.source_file}")
        print()
        print("Fields:")
        print(f"  RESOLVED:     {summary.resolved}")
        print(f"  NEEDS_REVIEW: {summary.needs_review}")
        print(f"  NOT_FOUND:    {summary.not_found}")
        print()
        print(f"ProjectFacts: {project_facts_path}")
        print(f"Review packet: {review_packet_path}")
        return EXIT_OK
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        print(f"Fact extraction failed: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_INPUT_ERROR
    except Exception as exc:  # pragma: no cover - defensive CLI boundary.
        print(f"Fact extraction failed: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
