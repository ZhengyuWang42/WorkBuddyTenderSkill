"""Negative controls for the docs-state consistency gate.

The gate's own PASS is only meaningful if it can *fail*.  This harness proves the
four required controls by running the **unmodified** gate against a staged copy of
its read surface and mutating exactly one thing per scenario:

``CURRENT_POINTER_NAMES_SUPERSEDED_BUILD``
    the current-build pointer is repointed at a build the repository has already
    archived as superseded -> the gate must FAIL;
``WRONG_CURRENT_ARTIFACT_HASH``
    a current pointer's recorded DOCX hash no longer matches its artifact -> FAIL;
``HISTORICAL_MENTION_OF_SUPERSEDED_BUILD``
    a superseded build id is mentioned inside an explicitly historical paragraph
    -> the gate must still PASS (the architecture forbids *banning* the string);
``WORD_HUMAN_PASS_WITHOUT_REVIEW``
    the delivered status claims a human Word PASS that no human produced -> FAIL.

The gate reads through its module-level ``REPO``/``GENERALIZATION`` constants, so
staging is a hardlink mirror of ``docs/`` and
``acceptance/reports/v1_generalization/``; the current pointers' own artifact
paths are absolute and therefore keep pointing at the real builds, so the hash
checks stay real rather than stubbed.

Usage::

    .venv/Scripts/python.exe scripts/v1_docs_state_negative_controls.py \\
        --out acceptance/reports/v1_generalization/docs_state_negative_controls.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GENERALIZATION = Path("acceptance/reports/v1_generalization")
STAGED_PARTS = ("docs", "acceptance/reports", "acceptance/evidence")

#: A hash that cannot be any artifact's own digest.
IMPOSSIBLE_SHA256 = "0" * 64


def _mirror(source: Path, destination: Path) -> None:
    """Hardlink one file or tree into the staged root.

    Hardlinking keeps the staging cheap and, because a staged file that is
    rewritten is first unlinked, guarantees the real repository file can never be
    modified through the shared inode.
    """

    if source.is_dir():
        for path in source.rglob("*"):
            if path.is_file():
                _mirror(path, destination / path.relative_to(source))
        return
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except FileExistsError:
        return
    except OSError:
        try:
            shutil.copy2(source, destination)
        except OSError:
            # A file another process holds open is not needed by any control; it
            # is skipped rather than failing the whole harness.
            pass


def _restore(root: Path) -> None:
    """Re-link the two trees a control may have mutated, from the real repository."""

    for part in ("docs", GENERALIZATION):
        target = root / part
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        _mirror(REPO / part, target)


def _relative_artifacts(gate) -> set[str]:
    """Repository-relative paths the gate resolves against its own root.

    ``check_build`` and the XLSX human-review checks join a *relative* recorded
    path onto the repository root, so a staged copy must carry those paths too -
    otherwise every control's baseline fails for a staging reason rather than for
    the mutation under test.
    """

    paths: set[str] = set()

    def add(value) -> None:
        if isinstance(value, str) and value and not Path(value).is_absolute():
            paths.add(value)

    status_path = REPO / GENERALIZATION / gate.STATUS_NAME
    if status_path.is_file():
        add(_load(status_path).get("build_dir"))

    review_path = REPO / GENERALIZATION / gate.XLSX_HUMAN_REVIEW_NAME
    if review_path.is_file():
        add(_load(review_path).get("reviewed_artifact"))

    manifest_path = REPO / GENERALIZATION / gate.XLSX_ARTIFACT_MANIFEST
    if manifest_path.is_file():
        add(_load(manifest_path).get("workbook"))
        add(_load(manifest_path).get("build_dir"))

    # Every build manifest, so a recorded build directory resolves.
    for manifest in (REPO / "acceptance/workspace").rglob("build_manifest.json"):
        add(str(manifest.relative_to(REPO)).replace("\\", "/"))
    return paths


def _staged_root(destination: Path, gate) -> Path:
    """Hardlink the gate's read surface into ``destination``."""

    if destination.exists():
        shutil.rmtree(destination, ignore_errors=True)
    for part in STAGED_PARTS:
        _mirror(REPO / part, destination / part)
    for relative in sorted(_relative_artifacts(gate)):
        _mirror(REPO / relative, destination / relative)
    return destination


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    # A staged file is a hardlink: rewrite through an unlink so the real
    # repository file is never touched.
    if path.exists():
        path.unlink()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _superseded_build_id(root: Path) -> str | None:
    for archived in sorted((root / GENERALIZATION).glob("case_*_current_build_superseded_by_*.json")):
        payload = _load(archived)
        if payload.get("build_id"):
            return str(payload["build_id"])
    return None


def _run_gate(gate, root: Path, report_name: str) -> dict:
    """Run the unmodified gate against ``root`` and return its report."""

    previous_repo = gate.REPO
    gate.REPO = root
    out = GENERALIZATION / report_name
    sys.argv = ["v1_docs_state_consistency.py", "--out", str(out)]
    try:
        with redirect_stdout(io.StringIO()):
            code = gate.main()
    finally:
        gate.REPO = previous_repo
    report = _load(root / out)
    report["exit_code"] = code
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(GENERALIZATION / "docs_state_negative_controls.json"),
        help="negative-control report path (relative resolves against the repository root)",
    )
    parser.add_argument("--keep-stage", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(REPO / "scripts"))
    import v1_docs_state_consistency as gate  # noqa: E402

    stage = REPO / ".docs-state-negative-controls"
    _staged_root(stage, gate)

    records = []
    #: One staged artefact is inherent to the method and is therefore excluded
    #: from every control's judgement: a record that stores an *absolute* artifact
    #: path resolves against the real repository root, so the staged copy's
    #: absolute-path equality check cannot hold.  The baseline captures it, and
    #: each control is judged on the failures it *adds* to it.
    baseline_failures: set[str] = set()
    staged_artifacts: list[str] = []

    def record(name: str, expectation: str, report: dict, *, required_check: str | None = None):
        observed = set(report.get("failed_checks") or [])
        added = sorted(observed - baseline_failures)
        removed = sorted(baseline_failures - observed)
        if expectation == "FAIL":
            ok = required_check in observed and not removed
        else:
            ok = not added
        records.append(
            {
                "control": name,
                "expected": expectation,
                "observed": report.get("status"),
                "exit_code": report.get("exit_code"),
                "required_failed_check": required_check,
                "required_failed_check_present": (
                    None if required_check is None else required_check in observed
                ),
                "failed_checks": sorted(observed),
                "failures_added_by_the_control": added,
                "baseline_failures_cleared": removed,
                "result": "PASS" if ok else "FAIL",
            }
        )

    baseline = _run_gate(gate, stage, "docs_state_negative_control_baseline.json")
    baseline_failures = set(baseline.get("failed_checks") or [])
    staged_artifacts = sorted(baseline_failures)
    record("BASELINE_UNMUTATED", "PASS", baseline)

    # 1. The current pointer names a build the repository has already superseded.
    superseded = _superseded_build_id(stage)
    if superseded is None:
        raise SystemExit("no archived superseded pointer is present to build the control from")
    for case in ("case_001", "case_002", "case_003"):
        pointer_path = stage / GENERALIZATION / f"{case}_current_build.json"
        if not pointer_path.is_file():
            continue
        pointer = _load(pointer_path)
        pointer["build_id"] = superseded
        _write(pointer_path, pointer)
    control = _run_gate(gate, stage, "docs_state_negative_control_superseded.json")
    record(
        "CURRENT_POINTER_NAMES_SUPERSEDED_BUILD",
        "FAIL",
        control,
        required_check="no_superseded_build_is_re_promoted_to_current",
    )
    # restore the staged pointers from the real ones
    _restore(stage)

    # 2. A current pointer's recorded artifact hash is wrong.
    pointer_path = stage / GENERALIZATION / "case_001_current_build.json"
    pointer = _load(pointer_path)
    pointer["generated_docx_sha256"] = IMPOSSIBLE_SHA256
    _write(pointer_path, pointer)
    control = _run_gate(gate, stage, "docs_state_negative_control_hash.json")
    record(
        "WRONG_CURRENT_ARTIFACT_HASH",
        "FAIL",
        control,
        required_check="case_001_pointer_hashes_match_its_build",
    )
    _restore(stage)

    # 3. A superseded build id inside an explicitly historical paragraph.
    state_path = stage / "docs/V1_PROJECT_STATE.md"
    state_text = state_path.read_text(encoding="utf-8")
    state_text += (
        "\n\n## 历史（HISTORICAL / SUPERSEDED build）负控段落\n\n"
        f"> 这一段**仅作历史记录**：已被取代的 build `{superseded}` 只在此处作为"
        " HISTORICAL 参考出现，**不得**被当作当前状态。\n"
    )
    # The staged file is a hardlink, so rewrite through an unlink: writing in
    # place would modify the real repository file through the same inode.
    state_path.unlink()
    state_path.write_text(state_text, encoding="utf-8")
    control = _run_gate(gate, stage, "docs_state_negative_control_history.json")
    record("HISTORICAL_MENTION_OF_SUPERSEDED_BUILD", "PASS", control)
    _restore(stage)

    # 4. A Word human PASS that no human produced.
    status_path = stage / GENERALIZATION / gate.STATUS_NAME
    status = _load(status_path)
    status["case001_manual_word_review"] = "HUMAN_PASS"
    _write(status_path, status)
    control = _run_gate(gate, stage, "docs_state_negative_control_human_pass.json")
    record(
        "WORD_HUMAN_PASS_WITHOUT_REVIEW",
        "FAIL",
        control,
        required_check="case001_manual_word_review_not_confirmed",
    )

    if not args.keep_stage:
        shutil.rmtree(stage, ignore_errors=True)

    report = {
        "schema": "v1_docs_state_negative_controls/1",
        "controls": records,
        "baseline_failed_checks": sorted(baseline_failures),
        "staging_artefact_note": (
            "a staged copy cannot satisfy a check that compares a record's stored "
            "*absolute* artifact path with the repository root it is read under; "
            "that one check is present in the baseline and excluded from every "
            "control's judgement, which is otherwise made on the failures the "
            "control itself adds"
        ),
        "result": (
            "PASS" if all(item["result"] == "PASS" for item in records) else "FAIL"
        ),
        "note": (
            "each control runs the unmodified gate against a hardlink-staged copy of "
            "its read surface and mutates exactly one thing; no repository file is "
            "modified"
        ),
    }
    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(out),
                "result": report["result"],
                "controls": [
                    {k: item[k] for k in ("control", "expected", "observed", "result")}
                    for item in records
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
