"""Apply a constrained WorkBuddy resolution override to ProjectFacts."""

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

from tender_basic.models import ProjectFacts, ResolutionOverrides
from tender_basic.resolution import apply_resolution_overrides, build_resolution_audit


EXIT_OK = 0
EXIT_INPUT_ERROR = 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply SELECT_CANDIDATE or KEEP_UNRESOLVED to ProjectFacts."
    )
    parser.add_argument("project_facts", type=Path, help="Original project_facts.json")
    parser.add_argument("resolution_overrides", type=Path, help="Resolution override JSON")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Reviewed ProjectFacts JSON output path",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        help="Audit JSON output path; defaults beside --output",
    )
    parser.add_argument("--verbose", action="store_true", help="Print traceback on failure")
    return parser


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        original = ProjectFacts.model_validate(_load_json(args.project_facts))
        overrides = ResolutionOverrides.model_validate(_load_json(args.resolution_overrides))
        reviewed, entries = apply_resolution_overrides(original, overrides)
        audit_path = args.audit or args.output.with_name("resolution_audit.json")
        _write_json(args.output, reviewed.model_dump(mode="json"))
        _write_json(audit_path, build_resolution_audit(original, entries))
        print("Status: OK")
        print(f"Reviewed facts: {args.output}")
        print(f"Resolution audit: {audit_path}")
        return EXIT_OK
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        print(f"Resolution application failed: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_INPUT_ERROR
    except Exception as exc:  # pragma: no cover - defensive CLI boundary.
        print(f"Resolution application failed: {exc}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
