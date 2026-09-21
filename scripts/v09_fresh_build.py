"""V0.9 fresh current-build render and manifest.

Runs one clean CASE001 pipeline build into a brand-new build directory, renders
the produced DOCX with a brand-new isolated LibreOffice profile, and writes a
build manifest that pairs the source PDF, the generated DOCX and the generated
PDF by content hash.  Every later gate is fed these exact paths, so a gate can
never measure a stale artifact.

Usage::

    .venv/Scripts/python.exe scripts/v09_fresh_build.py \
        --source acceptance/private/<tender>.pdf \
        --out acceptance/workspace/case_001/<build_id>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from render_case57 import SOFFICE, new_profile, soffice_argv  # noqa: E402

BUILD_SCHEMA = "v09_fresh_build_manifest/1"

#: The frozen case001 pointer location read by ``tests/build_under_test.py``.
DEFAULT_POINTER = ROOT / "acceptance/reports/v09_internal_preview/current_build.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_pipeline(source: Path, outdir: Path) -> dict:
    argv = [
        sys.executable,
        "-X",
        "utf8",
        str(ROOT / "scripts/run_pipeline.py"),
        str(source),
        "--output",
        str(outdir),
    ]
    started = time.time()
    completed = subprocess.run(
        argv, cwd=str(ROOT), capture_output=True, shell=False
    )
    return {
        "argv": argv,
        "returncode": completed.returncode,
        "elapsed_s": round(time.time() - started, 2),
        "stdout_tail": (completed.stdout or b"").decode("utf-8", "replace")[-4000:],
        "stderr_tail": (completed.stderr or b"").decode("utf-8", "replace")[-4000:],
    }


def render(docx: Path, outdir: Path) -> dict:
    profile_dir, profile_uri = new_profile(outdir)
    target = outdir / (docx.stem + ".pdf")
    if target.exists():
        target.unlink()
    argv = soffice_argv(docx, outdir, profile_uri)
    started = time.time()
    completed = subprocess.run(
        argv,
        shell=False,
        capture_output=True,
        timeout=900,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {
        "executable": str(SOFFICE),
        "argv": argv,
        "profile": str(profile_dir),
        "returncode": completed.returncode,
        "elapsed_s": round(time.time() - started, 2),
        "stderr_tail": (completed.stderr or b"").decode("utf-8", "replace")[-2000:],
        "pdf": str(target),
        "pdf_exists": target.exists(),
        "pdf_bytes": target.stat().st_size if target.exists() else 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--skip-pipeline", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument(
        "--pointer",
        type=Path,
        default=DEFAULT_POINTER,
        help=(
            "Explicit current-build pointer to write.  A build only ever writes "
            "this one pointer, so building another case can never repoint the "
            "frozen case001 build."
        ),
    )
    parser.add_argument(
        "--allow-default-pointer",
        action="store_true",
        help="Permit writing the frozen case001 pointer when rebuilding case001.",
    )
    args = parser.parse_args(argv)

    source = args.source.resolve()
    outdir = args.out.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    build_id = outdir.name
    started = time.time()

    pipeline = {"skipped": True}
    if not args.skip_pipeline:
        pipeline = run_pipeline(source, outdir)
        if pipeline["returncode"] != 0:
            payload = {
                "schema": BUILD_SCHEMA,
                "build_id": build_id,
                "status": "PIPELINE_FAILED",
                "pipeline": pipeline,
            }
            (outdir / "build_manifest.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2

    docx = outdir / "基础投标文件.docx"
    report = outdir / "generation_report.json"
    if not docx.exists() or not report.exists():
        payload = {
            "schema": BUILD_SCHEMA,
            "build_id": build_id,
            "status": "BUILD_ARTIFACT_MISSING",
            "docx_exists": docx.exists(),
            "report_exists": report.exists(),
        }
        (outdir / "build_manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 3

    render_record = {"skipped": True}
    if not args.skip_render:
        render_record = render(docx, outdir)
        if render_record["returncode"] != 0 or not render_record["pdf_exists"]:
            payload = {
                "schema": BUILD_SCHEMA,
                "build_id": build_id,
                "status": "RENDER_FAILED",
                "pipeline": pipeline,
                "render": render_record,
            }
            (outdir / "build_manifest.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 4

    pdf = Path(render_record.get("pdf") or (outdir / (docx.stem + ".pdf")))
    import pymupdf

    generation = json.loads(report.read_text(encoding="utf-8"))
    payload = {
        "schema": BUILD_SCHEMA,
        "build_id": build_id,
        "status": "FRESH_BUILD",
        "source": {
            "path": str(source),
            "sha256": sha256(source),
            "page_count": pymupdf.open(source).page_count,
        },
        "generated": {
            "docx": str(docx),
            "docx_sha256": sha256(docx),
            "docx_bytes": docx.stat().st_size,
            "pdf": str(pdf),
            "pdf_sha256": sha256(pdf),
            "pdf_bytes": pdf.stat().st_size,
            "pdf_page_count": pymupdf.open(pdf).page_count,
            "generation_report": str(report),
            "generation_report_sha256": sha256(report),
            "qa_report": str(outdir / "qa_report.json"),
        },
        "pipeline": pipeline,
        "render": render_record,
        "build_contract": {
            "source_and_pdf_hashes_recorded": True,
            "stale_artifact_reuse_forbidden": True,
            "gates_require_explicit_generated_pdf": True,
        },
        "frozen_rule_evidence": {
            "source_form_execution_owner_count": generation.get(
                "source_form_execution_owner_count"
            ),
            "owner_driven_value_emission_count": generation.get(
                "owner_driven_value_emission_count"
            ),
            "rule_compositions_created": generation.get("rule_compositions_created"),
        },
        "elapsed_s": round(time.time() - started, 2),
    }
    (outdir / "build_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pointer = {
        "schema": "v09_current_build_pointer/1",
        "build_id": build_id,
        "build_dir": str(outdir),
        "manifest": str(outdir / "build_manifest.json"),
        "source_pdf": payload["source"]["path"],
        "generated_docx": payload["generated"]["docx"],
        "generated_docx_sha256": payload["generated"]["docx_sha256"],
        "generated_pdf": payload["generated"]["pdf"],
        "generated_pdf_sha256": payload["generated"]["pdf_sha256"],
        "generation_report": payload["generated"]["generation_report"],
    }
    # Cross-case build isolation: one build writes exactly one pointer.  The
    # default is now to write no pointer at all, so a build for another case can
    # never repoint the frozen case001 build that
    # ``tests/build_under_test.py`` measures.  Callers that do own a case
    # pointer pass ``--pointer`` explicitly; only an explicit
    # ``--allow-default-pointer`` may rewrite the frozen case001 pointer.
    pointer_path = Path(args.pointer)
    if not pointer_path.is_absolute():
        pointer_path = ROOT / pointer_path
    if pointer_path.resolve() == DEFAULT_POINTER.resolve() and not args.allow_default_pointer:
        payload["pointer"] = {
            "written": False,
            "reason": (
                "the frozen case001 pointer is only written when "
                "--allow-default-pointer is passed"
            ),
            "requested_pointer": str(pointer_path),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_path.write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    payload["pointer"] = {"written": True, "path": str(pointer_path)}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
