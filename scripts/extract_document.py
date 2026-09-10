"""CLI for the V1 document-normalization stage."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.document_parser import (  # noqa: E402
    EXIT_PARSE_ERROR,
    exit_code_for_status,
    parse_document,
    write_normalized_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize one text PDF or DOCX into JSON and a lines view."
    )
    parser.add_argument("input_file", type=Path, help="Input PDF or DOCX path")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        dest="output_dir",
        help="Directory for normalized_document.json and document.lines.txt",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print warnings and traceback for an output failure",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    document = parse_document(args.input_file)

    try:
        json_path, lines_path = write_normalized_outputs(document, args.output_dir)
    except Exception as exc:
        print(f"Status: {document.status.value}", file=sys.stderr)
        print(f"Error: could not write normalized outputs: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_PARSE_ERROR

    print(f"Status: {document.status.value}")
    print(f"Source: {document.source_file}")
    print(f"Elements: {len(document.elements)}")
    print(f"Text length: {document.text_length}")
    print(f"Normalized JSON: {json_path}")
    print(f"Lines: {lines_path}")
    if document.warnings:
        print("Warnings:")
        for warning in document.warnings:
            print(f"- {warning}")

    return exit_code_for_status(document.status)


if __name__ == "__main__":
    raise SystemExit(main())
