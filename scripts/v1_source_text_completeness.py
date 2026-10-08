"""Source-text completeness gate for one Word build.

The saved/reopened DOCX is the machine authority for text completeness, and the
product measures it during the build (``source_format_qa.json``).  This gate reads
that authoritative measurement and turns it into a verdict plus a durable report:
every in-scope source text atom must have exactly one emission owner.

Default mode consumes the build's own QA record.  ``--recompute`` rebuilds the
ledger from the build's saved ``normalized_document.json``; that path exists for
negative-control work on historical builds that predate the provenance fields, and
it is explicitly *not* the authority, because re-extracting the format can
re-introduce source artifacts the build pipeline filtered.

Usage::

    python scripts/v1_source_text_completeness.py \
        --build acceptance/workspace/case_003/v1_word_source_fidelity_arch2 \
        --json acceptance/reports/v1_generalization/source_text_completeness_case_003_arch2.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_ZERO_KEYS = (
    "MISSING_ATOM_COUNT",
    "DUPLICATED_ATOM_COUNT",
    "source_text_atoms_with_zero_owner_count",
    "source_text_atoms_with_multiple_owner_count",
)


def _load_saved(build: Path) -> dict:
    qa_path = build / "source_format_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    return {
        "mode": "SAVED_BUILD_QA",
        "source_text_missing": qa.get("source_text_missing"),
        "SOURCE_COMPLETENESS_SCOPE_ATOM_COUNT": qa.get(
            "SOURCE_COMPLETENESS_SCOPE_ATOM_COUNT"
        ),
        "DELIVERED_ATOM_COUNT": qa.get("DELIVERED_ATOM_COUNT"),
        "MISSING_ATOM_COUNT": qa.get("MISSING_ATOM_COUNT", qa.get("source_text_missing")),
        "DUPLICATED_ATOM_COUNT": qa.get("DUPLICATED_ATOM_COUNT"),
        "OUT_OF_ORDER_ATOM_COUNT": qa.get("OUT_OF_ORDER_ATOM_COUNT"),
        "source_text_atoms_with_zero_owner_count": qa.get(
            "source_text_atoms_with_zero_owner_count", qa.get("source_text_missing")
        ),
        "source_text_atoms_with_multiple_owner_count": qa.get(
            "source_text_atoms_with_multiple_owner_count"
        ),
        "source_text_missing_atoms": qa.get("source_text_missing_atoms") or [],
        "source_text_duplicate_atoms": qa.get("source_text_duplicate_atoms") or [],
    }


def _recompute(build: Path) -> dict:
    from tender_basic.document_models import NormalizedDocument
    from tender_basic.format_extractor import extract_bid_format
    from tender_basic.models import ProjectFacts
    from tender_basic.source_format import build_source_format_model
    from tender_basic.source_format_qa import build_source_format_qa

    document = NormalizedDocument.model_validate(
        json.loads((build / "normalized_document.json").read_text(encoding="utf-8"))
    )
    facts = ProjectFacts.model_validate(
        json.loads((build / "project_facts.json").read_text(encoding="utf-8"))
    )
    report = json.loads((build / "generation_report.json").read_text(encoding="utf-8"))
    template = build_source_format_model(document, extract_bid_format(document))
    qa = build_source_format_qa(
        template, facts, build / "基础投标文件.docx", generation_report=report
    )
    result = {"mode": "RECOMPUTED_LEDGER"}
    for key in (
        "source_text_missing",
        "SOURCE_COMPLETENESS_SCOPE_ATOM_COUNT",
        "DELIVERED_ATOM_COUNT",
        "MISSING_ATOM_COUNT",
        "DUPLICATED_ATOM_COUNT",
        "OUT_OF_ORDER_ATOM_COUNT",
        "source_text_atoms_with_zero_owner_count",
        "source_text_atoms_with_multiple_owner_count",
        "source_text_missing_atoms",
        "source_text_duplicate_atoms",
    ):
        result[key] = qa.get(key)
    return result


def build_report(build: Path, *, recompute: bool) -> dict:
    build = build.resolve()
    data = _recompute(build) if recompute else _load_saved(build)
    missing = [atom.get("atom_id") for atom in data["source_text_missing_atoms"]]
    passes = all(int(data.get(key) or 0) == 0 for key in REQUIRED_ZERO_KEYS)
    return {
        "schema": "v1_source_text_completeness/1",
        "build": (
            str(build.relative_to(ROOT)).replace("\\", "/")
            if build.is_relative_to(ROOT)
            else str(build)
        ),
        "measurement_mode": data["mode"],
        "authority": "SAVED_REOPENED_DOCX",
        "SOURCE_TEXT_COMPLETENESS": "PASS" if passes else "FAIL",
        "counts": {key: data.get(key) for key in REQUIRED_ZERO_KEYS},
        "expected_atom_count": data.get("SOURCE_COMPLETENESS_SCOPE_ATOM_COUNT"),
        "delivered_atom_count": data.get("DELIVERED_ATOM_COUNT"),
        "out_of_order_atom_count": data.get("OUT_OF_ORDER_ATOM_COUNT"),
        "missing_atom_ids": missing,
        "missing_atoms": data["source_text_missing_atoms"],
        "duplicate_atoms": data["source_text_duplicate_atoms"],
        "note": (
            "out-of-order atoms are reported separately and are not a completeness "
            "failure: the delivered DOCX legitimately interleaves editable tables "
            "between source text, and the historical passing builds show the same "
            "count as the failing ones"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--md", type=Path, default=None)
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="rebuild the ledger instead of reading the build's own QA record",
    )
    args = parser.parse_args(argv)

    report = build_report(args.build, recompute=args.recompute)
    print(f"measurement_mode = {report['measurement_mode']}")
    for key, value in report["counts"].items():
        print(f"{key} = {value}")
    print(f"expected_atom_count = {report['expected_atom_count']}")
    print(f"delivered_atom_count = {report['delivered_atom_count']}")
    print(f"out_of_order_atom_count = {report['out_of_order_atom_count']}")
    for identifier in report["missing_atom_ids"]:
        print(f"  missing atom: {identifier}")
    print(f"SOURCE_TEXT_COMPLETENESS = {report['SOURCE_TEXT_COMPLETENESS']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", args.json)
    if args.md:
        lines = [
            "# Source text completeness",
            "",
            f"- build = `{report['build']}`",
            f"- measurement mode = {report['measurement_mode']}",
            f"- authority = {report['authority']}",
            f"- **SOURCE_TEXT_COMPLETENESS = {report['SOURCE_TEXT_COMPLETENESS']}**",
            "",
            "| counter | value |",
            "| --- | --- |",
        ]
        lines += [f"| {key} | {value} |" for key, value in report["counts"].items()]
        lines += [
            "",
            f"- expected atoms = {report['expected_atom_count']}",
            f"- delivered atoms = {report['delivered_atom_count']}",
            f"- out-of-order atoms = {report['out_of_order_atom_count']} (diagnostic)",
        ]
        if report["missing_atoms"]:
            lines += ["", "## Missing atoms", ""]
            for atom in report["missing_atoms"]:
                lines += [
                    f"- `{atom.get('atom_id')}` page {atom.get('source_page')} "
                    f"({atom.get('role')})",
                    f"  - text: `{atom.get('text')}`",
                    f"  - last present stage: {atom.get('last_present_stage')}",
                    f"  - first missing stage: {atom.get('first_missing_stage')}",
                    f"  - neighbours: {atom.get('neighboring_atom_before')} / "
                    f"{atom.get('neighboring_atom_after')}",
                ]
        lines += ["", report["note"], ""]
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("wrote", args.md)
    return 0 if report["SOURCE_TEXT_COMPLETENESS"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
