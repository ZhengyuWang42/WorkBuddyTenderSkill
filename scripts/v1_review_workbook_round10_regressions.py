"""Re-run the banked round-5/6/7 gates against the round-10 successor workbooks.

Round 10 separates bid response from contract risk.  The banked gates had passed
on the round-9r2 successor, so they have to be shown to still hold on the
*round-10* successor -- and on that successor only.  The round-8/round-9 report
files stay as evidence of what those rounds concluded and are never rewritten:
every run here is written under its own round-10 stem.

Usage::

    .venv/Scripts/python.exe scripts/v1_review_workbook_round10_regressions.py --three-case
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from v1_review_workbook_round8_regressions import run_case  # noqa: E402
from v1_review_workbook_round8_report import REPORTS  # noqa: E402
from v1_review_workbook_round10_report import BUILDS  # noqa: E402

SCHEMA = "v1_review_workbook_round10_banked_regressions/1"
STEM = "review_workbook_round10"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=None)
    parser.add_argument("--three-case", action="store_true")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=(
            "write this invocation's reports here instead of the shared historical "
            "report directory; workbook selection and every gate contract are unchanged"
        ),
    )
    args = parser.parse_args(argv)
    out_dir = args.out_dir
    if out_dir is not None:
        out_dir = Path(out_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise SystemExit(f"cannot use --out-dir {out_dir}: {error}") from error
    cases = list(BUILDS) if args.three_case or not args.case else args.case

    results = {
        case: run_case(case, build_name=BUILDS[case], stem=STEM, out_dir=out_dir)
        for case in cases
    }
    summary = {
        "schema": SCHEMA,
        "current_round": 10,
        "cases": results,
        "verdict": (
            "PASS"
            if all(
                entry[round_name]["verdict"] == "PASS"
                for entry in results.values()
                for round_name in ("round5", "round6", "round7")
            )
            else "FAIL"
        ),
    }
    path = (REPORTS if out_dir is None else out_dir) / "review_workbook_round10_banked_regressions.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for case, entry in results.items():
        print(
            f"{case}: round5={entry['round5']['verdict']} "
            f"round6={entry['round6']['verdict']} round7={entry['round7']['verdict']}"
        )
    print(f"banked regressions: {summary['verdict']} -> {path.name}")
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
