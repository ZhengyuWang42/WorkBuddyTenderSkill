"""Re-run the banked round-5/6/7 gates against the round-8 successor workbooks.

Round 7's manual review failed the delivered text; the banked machine gates had
passed, so they have to be shown to still hold on the *new* successor -- and on
the new successor only.  Pointing them at the frozen round-7 build (as the first
round-8 attempt did) re-audits the preserved evidence and reports a stale
"37/49 rows audited" as if it were a live regression.

The round-7 *report files* are evidence of what round 7 concluded and are never
rewritten: each run here is written under its own round-8 stem.

Usage::

    .venv/Scripts/python.exe scripts/v1_review_workbook_round8_regressions.py --three-case
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from v1_review_workbook_round5_report import Round5Report  # noqa: E402
from v1_review_workbook_round6_report import Round6Report  # noqa: E402
from v1_review_workbook_round7_report import Round7Report, markdown  # noqa: E402
from v1_review_workbook_round8_report import BUILDS, REPORTS  # noqa: E402

SCHEMA = "v1_review_workbook_round8_banked_regressions/1"


def _case_dir(case: str) -> Path:
    return ROOT / "acceptance/workspace" / case


def _report_dir(out_dir: Path | None) -> Path:
    """The directory this invocation's reports belong in."""

    return REPORTS if out_dir is None else Path(out_dir)


def _write(stem: str, data: dict[str, Any], *, out_dir: Path | None = None) -> Path:
    """Write one report, to the requested directory when one is given.

    OUTPUT ISOLATION.  A diagnostic run must be able to keep its reports away from
    the frozen historical ones, so the destination is an explicit per-invocation
    parameter rather than a rewritten module global.  The default is unchanged:
    with no ``out_dir`` the report lands exactly where it always has.
    """

    target = REPORTS if out_dir is None else Path(out_dir)
    if out_dir is not None:
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise SystemExit(f"cannot use --out-dir {target}: {error}") from error
    path = target / f"{stem}.json"
    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as error:
        raise SystemExit(f"cannot write report {path}: {error}") from error
    return path


def run_case(
    case: str,
    *,
    build_name: str | None = None,
    stem: str = "review_workbook_round8",
    out_dir: Path | None = None,
) -> dict[str, Any]:
    build_name = build_name or BUILDS[case]
    build = _case_dir(case) / build_name
    workbook = build / "投标项目复核表.xlsx"

    r5 = Round5Report(build=build, case=case).run()
    r5_failed = [check["check"] for check in r5["checks"] if not check["ok"]]
    _write(
        f"{stem}_{case}_round5",
        {
            "schema": "v1_review_workbook_round8_banked/1",
            "round": 5,
            "case": case,
            "build_id": build_name,
            "workbook": str(workbook),
            "workbook_sha256": r5["workbook_sha256"],
            "verdict": "PASS" if not r5_failed else "FAIL",
            "failed_checks": r5_failed,
            "fixtures": r5["fixtures_passed"],
            "fixtures_failed": r5["fixtures_failed"],
            "checks": r5["checks"],
        },
        out_dir=out_dir,
    )

    r6 = Round6Report(case, case_dir=_case_dir(case), build_name=build_name).run()
    _write(
        f"{stem}_{case}_round6",
        {
            "schema": "v1_review_workbook_round8_banked/1",
            "round": 6,
            "case": case,
            "build_id": build_name,
            "workbook": str(workbook),
            "workbook_sha256": r5["workbook_sha256"],
            "verdict": r6["verdict"],
            "failed_checks": r6["failed_checks"],
            "fixture_summary": r6["fixture_summary"],
            "counts": r6["counts"],
            "checks": r6["checks"],
        },
        out_dir=out_dir,
    )

    report7 = Round7Report(case, case_dir=_case_dir(case), build_name=build_name)
    r7 = report7.audit()
    _write(f"{stem}_{case}_round7", r7, out_dir=out_dir)
    _report_dir(out_dir).joinpath(f"{stem}_{case}_round7.md").write_text(
        markdown(r7), encoding="utf-8"
    )

    return {
        "build_id": build_name,
        "workbook": str(workbook),
        "round5": {
            "verdict": "PASS" if not r5_failed else "FAIL",
            "failed_checks": r5_failed,
            "fixtures": r5["fixtures_passed"],
            # per-fixture verdicts, so a later round can name a single banked
            # fixture (round 12 gates ``ROUND5_FIXTURE_F``) without re-running the
            # round-5 report a second time
            "fixtures_detail": r5["fixtures"],
        },
        "round6": {
            "verdict": r6["verdict"],
            "failed_checks": r6["failed_checks"],
            "failed_fixtures": r6["fixture_summary"]["failed"],
        },
        "round7": {
            "verdict": r7["verdict"],
            "failed_checks": r7["failed_checks"],
            "failed_fixtures": r7["fixture_summary"]["failed"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=None)
    parser.add_argument("--three-case", action="store_true")
    args = parser.parse_args(argv)
    cases = list(BUILDS) if args.three_case or not args.case else args.case

    results = {case: run_case(case) for case in cases}
    summary = {
        "schema": SCHEMA,
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
    path = REPORTS / "review_workbook_round8_banked_regressions.json"
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
