"""Read-only consistency gate for the V1 current-state documentation.

The durable docs are only useful if they cannot silently drift away from the
artifacts they describe.  This gate cross-checks the *current-state* statements
in

* ``docs/V1_PROJECT_STATE.md``
* ``docs/V1_DECISIONS.md``
* ``acceptance/reports/v1_generalization/v1_manual_review_checklist.md``

against the artifacts those statements are about:

* the CASE001 manual-review status JSON and the build it names,
* the three per-case current-build pointers,
* the three-case regression report,
* the JUnit XML record of the latest full-suite run.

It never writes to the artifacts and never changes a verdict: it reports where
the documentation and the machine state disagree, so a stale claim is caught
rather than trusted.  No page numbers, corpus literals, rule ids or case-specific
exceptions are used; every check is derived from the artifacts.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_docs_state_consistency.py \
        --out acceptance/reports/v1_generalization/v1_docs_state_consistency.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GENERALIZATION = Path("acceptance/reports/v1_generalization")
STATUS_NAME = "case001_manual_word_review_final_status.json"
THREE_CASE_NAME = "v1_three_case_regression_final.json"
CHECKLIST_NAME = "v1_manual_review_checklist.md"
FULL_SUITE_XML = "case001_full_test_suite_round4_closure8.xml"

CASES = ("case_001", "case_002", "case_003")

#: Statements that must never appear in a current-state document.
FORBIDDEN_CLAIMS = (
    "READY_FOR_SUBMISSION = true",
    "READY_FOR_SUBMISSION=true",
    "V1_PRODUCTION_CANDIDATE = true",
    "V1_PRODUCTION_CANDIDATE=true",
)

#: A line that *forbids* a claim is not the claim.  D8 exists precisely to say
#: "never assert READY_FOR_SUBMISSION = true", so the prohibition wording is
#: expected and allowed; only an assertion is a defect.
PROHIBITION_MARKERS = ("不得", "禁止", "永不", "绝", "never", "not allowed")


def asserts_claim(text: str) -> list[str]:
    """Forbidden claims that are *asserted* somewhere in ``text``."""

    found = []
    for line in text.splitlines():
        if any(marker in line for marker in PROHIBITION_MARKERS):
            continue
        stripped = re.sub(r"`[^`]*`", "", line)
        for claim in FORBIDDEN_CLAIMS:
            if claim in line and claim in stripped:
                found.append(f"{claim} :: {line.strip()[:120]}")
    return found


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Gate:
    """Collects named checks so the report says what was and was not verified."""

    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.problems: list[str] = []

    def check(self, name: str, ok: bool, **evidence) -> bool:
        entry = {"check": name, "status": "PASS" if ok else "FAIL"}
        entry.update(evidence)
        self.checks.append(entry)
        if not ok:
            self.problems.append(name)
        return ok


def check_build(gate: Gate, status: dict) -> dict:
    build_id = status.get("build_id")
    build_dir = REPO / str(status.get("build_dir", ""))
    manifest_path = build_dir / "build_manifest.json"
    gate.check(
        "documented_build_id_resolves",
        bool(build_id) and manifest_path.is_file(),
        build_id=build_id,
        build_dir=status.get("build_dir"),
    )
    if not manifest_path.is_file():
        return {}
    manifest = load(manifest_path)
    generated = manifest["generated"]
    docx = Path(generated["docx"])
    pdf = Path(generated["pdf"])
    docx_actual = sha256(docx) if docx.is_file() else ""
    pdf_actual = sha256(pdf) if pdf.is_file() else ""
    documented = status.get("manifest", {})
    gate.check(
        "documented_docx_hash_is_the_build_hash",
        docx_actual == generated["docx_sha256"] == documented.get("docx_sha256"),
        recomputed=docx_actual,
        manifest=generated["docx_sha256"],
        documented=documented.get("docx_sha256"),
    )
    gate.check(
        "documented_pdf_hash_is_the_build_hash",
        pdf_actual == generated["pdf_sha256"] == documented.get("pdf_sha256"),
        recomputed=pdf_actual,
        manifest=generated["pdf_sha256"],
        documented=documented.get("pdf_sha256"),
    )
    return {
        "build_id": build_id,
        "docx_sha256": docx_actual,
        "pdf_sha256": pdf_actual,
    }


def check_flags(gate: Gate, status: dict) -> dict:
    flags = {
        "manual_word_review_required": status.get("manual_word_review_required"),
        "case001_manual_word_review": status.get("case001_manual_word_review"),
        "v1_production_candidate": status.get("v1_production_candidate"),
        "ready_for_submission": status.get("ready_for_submission"),
    }
    gate.check(
        "manual_review_still_required",
        flags["manual_word_review_required"] is True,
        **{"manual_word_review_required": flags["manual_word_review_required"]},
    )
    gate.check(
        "case001_manual_word_review_not_confirmed",
        str(flags["case001_manual_word_review"]).upper() == "NOT_YET_CONFIRMED",
        case001_manual_word_review=flags["case001_manual_word_review"],
    )
    gate.check(
        "not_a_production_candidate",
        flags["v1_production_candidate"] is False,
        v1_production_candidate=flags["v1_production_candidate"],
    )
    gate.check(
        "never_ready_for_submission",
        flags["ready_for_submission"] is False,
        ready_for_submission=flags["ready_for_submission"],
    )
    return flags


def check_full_suite(gate: Gate, status: dict) -> dict:
    xml_path = REPO / GENERALIZATION / FULL_SUITE_XML
    recorded = str((status.get("gates") or {}).get("full_suite") or "")
    if not xml_path.is_file():
        gate.check("full_suite_evidence_exists", False, path=str(xml_path))
        return {}
    import xml.etree.ElementTree as ET

    root = ET.parse(xml_path).getroot()
    suite = next(root.iter("testsuite"))
    counts = {
        "tests": int(suite.get("tests")),
        "failures": int(suite.get("failures")),
        "errors": int(suite.get("errors")),
        "skipped": int(suite.get("skipped")),
    }
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    gate.check(
        "full_suite_is_green",
        counts["failures"] == 0 and counts["errors"] == 0,
        **counts,
    )
    pattern = re.compile(
        rf"{counts['passed']} passed,\s*{counts['skipped']} skipped,\s*"
        rf"{counts['failures']} failed,\s*{counts['errors']} errors"
    )
    gate.check(
        "documented_full_suite_count_matches_the_run",
        bool(pattern.search(recorded)),
        documented=recorded,
        evidence_counts=counts,
    )
    return counts


def check_pointers(gate: Gate) -> dict:
    pointers = {}
    regression_path = REPO / GENERALIZATION / THREE_CASE_NAME
    regression = load(regression_path) if regression_path.is_file() else {}
    gate.check(
        "three_case_regression_present_and_pass",
        str(regression.get("result") or regression.get("status") or "").startswith("PASS")
        or regression.get("result") == "PASS",
        result=regression.get("result") or regression.get("status"),
    )
    for case in CASES:
        pointer_path = REPO / GENERALIZATION / f"{case}_current_build.json"
        if not pointer_path.is_file():
            gate.check(f"{case}_pointer_exists", False, path=str(pointer_path))
            continue
        pointer = load(pointer_path)
        build_dir = Path(pointer["build_dir"])
        docx = Path(pointer["generated_docx"])
        pdf = Path(pointer["generated_pdf"])
        docx_ok = docx.is_file() and sha256(docx) == pointer["generated_docx_sha256"]
        pdf_ok = pdf.is_file() and sha256(pdf) == pointer["generated_pdf_sha256"]
        gate.check(
            f"{case}_pointer_hashes_match_its_build",
            docx_ok and pdf_ok,
            build_id=pointer.get("build_id"),
            build_dir_exists=build_dir.is_dir(),
            docx_ok=docx_ok,
            pdf_ok=pdf_ok,
        )
        pointers[case] = {
            "build_id": pointer.get("build_id"),
            "docx_sha256": pointer.get("generated_docx_sha256"),
            "pdf_sha256": pointer.get("generated_pdf_sha256"),
        }
    return pointers


def check_docs(gate: Gate, state_text: str, decisions_text: str, checklist_text: str) -> dict:
    state = REPO / "docs/V1_PROJECT_STATE.md"
    decisions = REPO / "docs/V1_DECISIONS.md"
    gate.check(
        "current_state_docs_exist",
        state.is_file() and decisions.is_file(),
        state=str(state),
        decisions=str(decisions),
    )
    asserted = asserts_claim(state_text) + asserts_claim(decisions_text)
    gate.check(
        "forbidden_readiness_claims_absent",
        not asserted,
        forbidden=list(FORBIDDEN_CLAIMS),
        asserted=asserted,
        note="a line that forbids the claim is not the claim",
    )
    gate.check(
        "state_doc_marks_manual_review_not_confirmed",
        "NOT_YET_CONFIRMED" in state_text,
    )
    gate.check(
        "state_doc_marks_not_ready_for_submission",
        "READY_FOR_SUBMISSION" in state_text and "false" in state_text.lower(),
    )
    gate.check(
        "state_doc_has_the_recovery_map",
        "RECOVERY MAP" in state_text,
    )
    checkboxes = len(re.findall(r"^\s*[-*]\s*\[[xX]\]", checklist_text, flags=re.MULTILINE))
    gate.check(
        "human_review_boxes_unticked",
        checkboxes == 0,
        ticked_boxes=checkboxes,
    )
    return {
        "checked_human_boxes": checkboxes,
        "state_doc_bytes": len(state_text.encode("utf-8")),
        "decisions_doc_bytes": len(decisions_text.encode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(GENERALIZATION / "v1_docs_state_consistency.json"),
        help="report path (relative paths resolve against the repository root)",
    )
    args = parser.parse_args()

    status_path = REPO / GENERALIZATION / STATUS_NAME
    gate = Gate()
    if not status_path.is_file():
        print(f"missing current-state status: {status_path}", file=sys.stderr)
        return 2
    status = load(status_path)

    build = check_build(gate, status)
    flags = check_flags(gate, status)
    counts = check_full_suite(gate, status)
    pointers = check_pointers(gate)
    docs = check_docs(
        gate,
        (REPO / "docs/V1_PROJECT_STATE.md").read_text(encoding="utf-8"),
        (REPO / "docs/V1_DECISIONS.md").read_text(encoding="utf-8"),
        (REPO / GENERALIZATION / CHECKLIST_NAME).read_text(encoding="utf-8"),
    )

    report = {
        "schema": "v1_docs_state_consistency/1",
        "status": "PASS" if not gate.problems else "FAIL",
        "documented_build": build,
        "flags": flags,
        "full_suite": counts,
        "pointers": pointers,
        "docs": docs,
        "checks": gate.checks,
        "failed_checks": gate.problems,
        "note": (
            "read-only: the gate compares the durable docs with the artifacts they "
            "describe and never changes a verdict or an artifact"
        ),
    }
    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out), "status": report["status"], "failed": gate.problems}, ensure_ascii=False))
    return 0 if not gate.problems else 1


if __name__ == "__main__":
    sys.exit(main())
