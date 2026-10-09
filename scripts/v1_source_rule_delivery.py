"""Source-rule delivery gate for one Word build.

SOURCE TEXT COMPLETENESS AND SOURCE BLANK COMPLETENESS ARE DISTINCT.  This gate
measures the second: every physical rule the source drew inside the delivery scope
must reach a visible, editable native Word representation, or be recorded as
not-applicable with the source evidence that says so.

A rule that a label vocabulary failed to recognise is still a rule: discovery here
is geometric, from the source's own drawing primitives, and label recognition only
supplies a field's meaning.

Usage::

    .venv/Scripts/python.exe scripts/v1_source_rule_delivery.py \
        --build acceptance/workspace/case_002/v1_word_source_fidelity_arch4 \
        --source-pdf acceptance/private/<tender>.pdf \
        --json acceptance/reports/v1_generalization/source_rule_delivery_case_002_arch4.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.source_rule_delivery import (  # noqa: E402
    DELIVERED_VISIBLE_EDITABLE,
    NOT_DELIVERED,
    build_source_rule_ledger,
)


def build_report(build: Path, source_pdf: Path | None) -> dict:
    build = build.resolve()
    ledger = build_source_rule_ledger(
        build,
        source_pdf=(source_pdf.resolve() if source_pdf is not None else None),
    )
    problems = [
        {
            "canonical_rule_id": record.atom.canonical_rule_id,
            "source_rule_id": record.atom.source_rule_id,
            "source_page": record.atom.source_page,
            "source_x0": round(record.atom.source_x0, 2),
            "source_x1": round(record.atom.source_x1, 2),
            "source_y": round(record.atom.source_y, 2),
            "source_label": record.atom.source_label,
            "verdict": record.verdict,
            "first_missing_stage": record.first_missing_stage,
            "visible_coverage_ratio": (
                None
                if record.visible_coverage_ratio is None
                else round(record.visible_coverage_ratio, 4)
            ),
            "reasons": record.reasons,
            "docx_evidence": record.docx_evidence,
        }
        for record in ledger.records
        if record.atom.applicable and record.verdict != DELIVERED_VISIBLE_EDITABLE
    ]
    report = {
        "schema": "v1_source_rule_delivery_gate/1",
        "build": (
            str(build.relative_to(ROOT)).replace("\\", "/")
            if build.is_relative_to(ROOT)
            else str(build)
        ),
        "source_pdf": ledger.source_pdf,
        "authority": {
            "source": "presentation evidence",
            "docx": "machine structural and editability authority",
            "headless": "diagnostic renderer only",
            "word_desktop": "final delivery authority (this gate never grants it)",
        },
        "counters": ledger.counters(),
        "SOURCE_BLANK_COMPLETENESS": (
            "PASS" if not problems else "FAIL"
        ),
        "problems": problems,
        "records": [record.as_dict() for record in ledger.records],
        "notes": ledger.notes,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    report = build_report(args.build, args.source_pdf)
    for key, value in report["counters"].items():
        print(f"{key} = {value}")
    print(f"SOURCE_BLANK_COMPLETENESS = {report['SOURCE_BLANK_COMPLETENESS']}")
    for problem in report["problems"]:
        print(
            "  "
            f"{problem['source_rule_id']} p{problem['source_page']} "
            f"{problem['source_x0']}->{problem['source_x1']} "
            f"{problem['verdict']} first_missing={problem['first_missing_stage']}"
        )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", args.json)
    return 0 if report["SOURCE_BLANK_COMPLETENESS"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
