"""CLI for disk-artifact Delivery QA."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.delivery_qa import qa_exit_code, run_delivery_qa, write_qa_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reload and QA project_facts.json, the review XLSX, and the bid DOCX."
    )
    parser.add_argument("--facts", required=True, type=Path, help="Path to project_facts.json")
    parser.add_argument("--xlsx", required=True, type=Path, help="Path to the review workbook")
    parser.add_argument("--docx", required=True, type=Path, help="Path to the bid document")
    parser.add_argument("--output", required=True, type=Path, help="Path to qa_report.json")
    parser.add_argument("--verbose", action="store_true", help="Print a traceback on program error")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_delivery_qa(args.facts, args.xlsx, args.docx)
        report_path = write_qa_report(report, args.output)
        print(f"Status: {report['overall_status']}")
        print(f"Checks: {report['summary']['check_count']}")
        print(f"Errors: {report['summary']['error_count']}")
        print(f"Warnings: {report['summary']['warning_count']}")
        print(f"QA report: {report_path}")
        return qa_exit_code(report["overall_status"])
    except Exception as exc:  # pragma: no cover - defensive CLI boundary.
        print(f"Delivery QA failed to run: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
