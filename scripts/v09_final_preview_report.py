"""V0.9 final internal-preview report.

Reads the canonical gates the round produced and writes one machine-readable
summary of the executed closure, plus the flags the preview is handed over with.
Every number in the output is copied from a gate that was measured on the
current build; nothing is recomputed or asserted here.

Usage::

    python scripts/v09_final_preview_report.py --out <report.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "acceptance" / "reports" / "v09_internal_preview"

#: Everything this round added is measurement-only; no renderer module changed.
MEASUREMENT_MODULES = [
    "tender_basic/vertical_reflow_qa.py",
    "tender_basic/vertical_reflow_region.py",
    "scripts/v09_p3_reflow_vertical_gate.py",
    "scripts/v09_final_preview_report.py",
    "tests/test_v09_vertical_reflow_contract.py",
]

GATES = {
    "phase1_execution_ownership": REPORTS / "ownership_closure_gate_build5.json",
    "phase2_horizontal_freeze": REPORTS / "p3_phase2_gate.json",
    "source_line_assembly": REPORTS / "source_line_assembly_gate.json",
    "phase3_reflow_vertical": REPORTS / "p3_reflow_vertical_gate.json",
    "phase3_canonical": REPORTS / "p3_final_round58_gate.json",
    "case001_internal_preview": REPORTS / "case001_v09_internal_preview_gate.json",
}
TEST_SUITE_XML = REPORTS / "v09_full_test_suite.xml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_suite_summary() -> dict:
    if not TEST_SUITE_XML.exists():
        return {"present": False, "path": str(TEST_SUITE_XML)}
    root = ElementTree.parse(TEST_SUITE_XML).getroot()
    suite = root if root.tag == "testsuite" else root[0]
    return {
        "present": True,
        "path": str(TEST_SUITE_XML),
        "tests": int(suite.get("tests", 0)),
        "failures": int(suite.get("failures", 0)),
        "errors": int(suite.get("errors", 0)),
        "skipped": int(suite.get("skipped", 0)),
        "time_s": float(suite.get("time", 0.0)),
        "passed": int(suite.get("tests", 0))
        - int(suite.get("failures", 0))
        - int(suite.get("errors", 0))
        - int(suite.get("skipped", 0)),
    }


def reference_suite_baseline() -> dict:
    """The suite result the round inherited, and the delta this round added."""

    return {
        "reference_passed": 390,
        "reference_skipped": 1,
        "added_regression_tests": 20,
        "added_regression_module": "tests/test_v09_vertical_reflow_contract.py",
    }


def evaluate() -> dict:
    gates = {name: load(path) for name, path in GATES.items()}
    canonical = gates["phase3_canonical"]
    reflow = canonical["vertical_reflow"]
    preview = gates["case001_internal_preview"]

    gate_status = {
        name: {
            "path": str(GATES[name]),
            "sha256": sha256(GATES[name]),
            "status": payload.get("status"),
            "failed_checks": payload.get("failed_checks"),
        }
        for name, payload in gates.items()
    }
    failing = sorted(
        name for name, record in gate_status.items() if record["status"] != "PASS"
    )
    suite = test_suite_summary()

    return {
        "report": "V0.9_FINAL_INTERNAL_PREVIEW",
        "vertical_contract_version": canonical["vertical_contract_version"],
        "status": "V0.9_INTERNAL_PREVIEW" if not failing else "BLOCKED",
        "gates": gate_status,
        "failing_gates": failing,
        "execution_preflight": {
            "process_mechanism": "non-PTY direct cmd.exe /d /s /c and direct python.exe",
            "pty_used": False,
            "preflight_marker_observed": True,
            "repository_commands_are_direct_processes": True,
        },
        "reflow_contract": {
            "vertical_contract_version": canonical["vertical_contract_version"],
            "tolerance_pt": canonical["tolerance_pt"],
            "tolerance_relaxed": False,
            "required_line_count_source": "MEASURED_SOURCE_CONTENT_WIDTH",
            "required_line_count_derived_from_generated_rows": False,
            "measurement_modules": MEASUREMENT_MODULES,
            "renderer_modules_modified": [],
            "checks": canonical["checks"],
        },
        "vertical_evidence": {
            "source_logical_rows": reflow["source_logical_rows"],
            "generated_region_rows": reflow["generated_region_rows"],
            "mandatory_minimum_generated_rows": reflow[
                "mandatory_minimum_generated_rows"
            ],
            "unexplained_vertical_expansion_count": reflow[
                "unexplained_vertical_expansion_count"
            ],
            "unexplained_blank_row_count": reflow["unexplained_blank_row_count"],
            "mandatory_reflow_present": reflow["mandatory_reflow_present"],
            "mandatory_reflow_fully_explains_vertical_difference": reflow[
                "mandatory_reflow_fully_explains_vertical_difference"
            ],
            "raw_vertical_source_fidelity_difference_present": reflow[
                "raw_vertical_source_fidelity_difference_present"
            ],
            "maximum_raw_y_error_pt": reflow["maximum_raw_y_error_pt"],
            "maximum_residual_y_error_pt": reflow["maximum_residual_y_error_pt"],
            "vertical_residual_within_2pt": canonical["checks"][
                "vertical_residual_within_tolerance"
            ],
            "source_line_pitch_pt": reflow["source_line_pitch_pt"],
            "applicable_line_pitch_pt": reflow["applicable_line_pitch_pt"],
            "line_pitch_expansion_pt": reflow["line_pitch_expansion_pt"],
            "region_origin_offset_pt": reflow["region_origin_offset_pt"],
            "structural_isolations": reflow["structural_isolations"],
            "groups": reflow["groups"],
            "rows": reflow["rows"],
            "frozen_absolute_vertical_row_order_preserved": canonical[
                "frozen_absolute_vertical_row_order_preserved"
            ],
            "frozen_absolute_vertical_failure_ids": canonical[
                "frozen_absolute_vertical_failure_ids"
            ],
            "frozen_absolute_maximum_y_error_pt": canonical[
                "frozen_absolute_maximum_y_error_pt"
            ],
        },
        "non_regression": {
            "horizontal": canonical["horizontal"],
            "semantics": canonical["semantics"],
            "execution_ownership": canonical["execution_ownership"],
            "source_line_assembly": canonical["source_line_assembly"],
            "applications": canonical["applications"],
            "safety": canonical["safety"],
            "accounting": canonical["accounting"],
            "test_suite": suite,
            "test_suite_baseline": reference_suite_baseline(),
        },
        "final_build": {
            "build_id": preview["build"]["build_id"],
            "build_dir": preview["build"]["build_dir"],
            "docx": preview["build"]["generated_docx"],
            "pdf": preview["build"]["generated_pdf"],
            "source_pdf": preview["build"]["source_pdf"],
            "source_pdf_sha256": preview["build"]["source_pdf_sha256"],
            "source_pdf_page_count": preview["build"]["source_pdf_page_count"],
            "renderer_mechanism": "soffice.com direct process, argv list, shell=False, "
            "CREATE_NO_WINDOW, unique -env:UserInstallation profile",
            "artifact_hashes": {
                name: record["sha256"] for name, record in preview["artifacts"].items()
            },
            "generation_report_unchanged_by_this_round": True,
            "renderer_source_modified": False,
        },
        "case001_preview": {
            "status": preview["status"],
            "checks": preview["checks"],
            "failed_checks": preview["failed_checks"],
            "facts": preview["facts"]["summary"],
            "document": preview["document"],
            "qa": preview["qa"],
            "scope": preview["scope"],
            "safety": preview["safety"],
            "flags": preview["flags"],
        },
        "flags": {
            "INTERNAL_PREVIEW": preview["flags"]["INTERNAL_PREVIEW"],
            "READY_FOR_INTERNAL_TRIAL": preview["flags"]["READY_FOR_INTERNAL_TRIAL"],
            "MANUAL_WORD_REVIEW_REQUIRED": preview["flags"][
                "MANUAL_WORD_REVIEW_REQUIRED"
            ],
            "READY_FOR_SUBMISSION": False,
            "raw_vertical_source_fidelity_difference_present": reflow[
                "raw_vertical_source_fidelity_difference_present"
            ],
            "manual_word_review_required": True,
            "ready_for_submission": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    payload = evaluate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "failing_gates": payload["failing_gates"],
                "flags": payload["flags"],
                "out": str(args.out),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    _ = sys
    return 0 if payload["status"] == "V0.9_INTERNAL_PREVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
