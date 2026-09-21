"""Repoint a case's current-build pointer at a build that already exists.

Cross-case build isolation requires that building one case cannot repoint
another case's frozen build.  This tool is the explicit, opt-in way to point a
pointer file at an existing build directory that carries a valid
``build_manifest.json``; it never rebuilds anything, and it verifies every
recorded hash before writing so a pointer can never address a stale or tampered
artifact.

Usage::

    .venv/Scripts/python.exe scripts/v1_point_build.py \
        --manifest acceptance/workspace/case_001/v09_build_5/build_manifest.json \
        --pointer acceptance/reports/v09_internal_preview/current_build.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pointer", required=True, type=Path)
    args = parser.parse_args(argv)

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    pointer_path = args.pointer if args.pointer.is_absolute() else ROOT / args.pointer
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "FRESH_BUILD":
        raise SystemExit(f"manifest is not a FRESH_BUILD: {manifest.get('status')!r}")

    generated = manifest["generated"]
    checks = [
        (Path(generated["docx"]), generated["docx_sha256"]),
        (Path(generated["pdf"]), generated["pdf_sha256"]),
        (Path(generated["generation_report"]), generated["generation_report_sha256"]),
        (Path(manifest["source"]["path"]), manifest["source"]["sha256"]),
    ]
    for path, expected in checks:
        if not path.exists():
            raise SystemExit(f"pointer target missing: {path}")
        actual = sha256(path)
        if actual != expected:
            raise SystemExit(f"hash mismatch for {path}: {actual} != {expected}")

    pointer = {
        "schema": "v09_current_build_pointer/1",
        "build_id": manifest["build_id"],
        "build_dir": str(manifest_path.parent),
        "manifest": str(manifest_path),
        "source_pdf": manifest["source"]["path"],
        "generated_docx": generated["docx"],
        "generated_docx_sha256": generated["docx_sha256"],
        "generated_pdf": generated["pdf"],
        "generated_pdf_sha256": generated["pdf_sha256"],
        "generation_report": generated["generation_report"],
    }
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_path.write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"written": str(pointer_path), **pointer}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
