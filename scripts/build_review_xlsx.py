"""CLI for building the V1 tender review workbook from project_facts.json."""

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

from tender_basic.models import ProjectFacts
from tender_basic.review_builder import build_review_workbook


EXIT_OK = 0
EXIT_INPUT_ERROR = 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the V1 tender review workbook from project_facts.json."
    )
    parser.add_argument("input", type=Path, help="Path to project_facts.json")
    parser.add_argument("--output", required=True, type=Path, help="Output .xlsx path")
    parser.add_argument("--verbose", action="store_true", help="Print a traceback on failure")
    return parser


def _load_project_facts(path: Path) -> ProjectFacts:
    with path.open("r", encoding="utf-8") as handle:
        return ProjectFacts.model_validate(json.load(handle))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project_facts = _load_project_facts(args.input)
        output_path = build_review_workbook(project_facts, args.output)
        print("Status: OK")
        print(f"Output: {output_path}")
        print(f"Fields: {project_facts.summary.total_fields}")
        print(f"Needs review: {project_facts.summary.needs_review}")
        print(f"Not found: {project_facts.summary.not_found}")
        return EXIT_OK
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        print(f"XLSX generation failed: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_INPUT_ERROR
    except Exception as exc:  # pragma: no cover - defensive CLI boundary.
        print(f"XLSX generation failed: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
