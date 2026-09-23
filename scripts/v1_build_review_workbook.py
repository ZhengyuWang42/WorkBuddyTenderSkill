"""Build a successor review-workbook build from an accepted build's artifacts.

The Word artifact and the review workbook have different change cadences: the
workbook is a *review surface* over data the Word build already produced.  This
tool therefore never re-renders Word.  It

1. reads the source build's own artifacts (facts, normalized source, review
   evidence, generation report),
2. copies the DOCX, the PDF and the reports **byte-identically** into a new
   successor build directory,
3. appends the reviewer views to the carried-over ``投标项目复核表.xlsx``
   without touching the delivered sheet's values, and
4. writes the successor's ``build_manifest.json`` recording the copied hashes.

The DOCX and PDF hashes of an accepted build are therefore unchanged by a
workbook round, and the source build is never written to.

Usage::

    .venv/Scripts/python.exe -X utf8 scripts/v1_build_review_workbook.py \
        --build acceptance/workspace/case_001/v1_manual_fidelity_round4_date_rhythm_closure8 \
        --build-id v1_manual_fidelity_round4_date_rhythm_closure8_review_workbook1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tender_basic.document_models import NormalizedDocument  # noqa: E402
from tender_basic.dynamic_review import build_dynamic_review_plan  # noqa: E402
from tender_basic.format_extractor import extract_bid_format  # noqa: E402
from tender_basic.models import ProjectFacts  # noqa: E402
from tender_basic.review_workbook_views import augment_review_workbook  # noqa: E402

#: Artifacts copied unchanged so the successor build is self-describing.
COPIED_ARTIFACTS = (
    "基础投标文件.docx",
    "基础投标文件.pdf",
    "投标项目复核表.xlsx",
    "generation_report.json",
    "qa_report.json",
    "project_facts.json",
    "normalized_document.json",
    "review_evidence_packet.json",
    "review_evidence_qa.json",
    "metadata.json",
    "source_format_qa.json",
    "fact_gap_packet.json",
    "facts_review_packet.json",
    "semantic_candidate_results.json",
    "document.lines.txt",
)

#: Artifacts whose bytes must be identical in the successor build.
PINNED = ("基础投标文件.docx", "基础投标文件.pdf", "generation_report.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, help="source (accepted) build directory")
    parser.add_argument("--build-id", required=True, help="successor build id")
    parser.add_argument("--case-dir", help="parent directory for the successor build")
    parser.add_argument("--out", help="report path")
    args = parser.parse_args()

    source_build = Path(args.build)
    if not source_build.is_absolute():
        source_build = REPO / source_build
    if not source_build.is_dir():
        print(f"source build not found: {source_build}", file=sys.stderr)
        return 2
    case_dir = Path(args.case_dir) if args.case_dir else source_build.parent
    if not case_dir.is_absolute():
        case_dir = REPO / case_dir
    target = case_dir / args.build_id
    if target.exists():
        print(f"refusing to overwrite an existing build: {target}", file=sys.stderr)
        return 3
    target.mkdir(parents=True)

    copied: dict[str, dict] = {}
    for name in COPIED_ARTIFACTS:
        origin = source_build / name
        if not origin.is_file():
            continue
        destination = target / name
        shutil.copy2(origin, destination)
        copied[name] = {"sha256": sha256(destination), "bytes": destination.stat().st_size}

    identical = {
        name: copied[name]["sha256"] == sha256(source_build / name)
        for name in PINNED
        if name in copied
    }
    if not all(identical.values()):
        print(f"copied artifact differs from the source build: {identical}", file=sys.stderr)
        return 4

    source_manifest = json.loads((source_build / "build_manifest.json").read_text(encoding="utf-8"))
    source = dict(source_manifest.get("source") or {})

    facts = ProjectFacts.model_validate(
        json.loads((target / "project_facts.json").read_text(encoding="utf-8"))
    )
    document = NormalizedDocument.model_validate(
        json.loads((target / "normalized_document.json").read_text(encoding="utf-8"))
    )
    format_template = extract_bid_format(document)
    packet = json.loads((target / "review_evidence_packet.json").read_text(encoding="utf-8"))
    plan = build_dynamic_review_plan(document, facts)

    workbook_path = target / "投标项目复核表.xlsx"
    delivered_before = copied["投标项目复核表.xlsx"]["sha256"]
    # The delivered sheet is carried over exactly as accepted; the reviewer
    # views are appended on top of it.
    views = augment_review_workbook(
        workbook_path,
        project_facts=facts,
        dynamic_plan=plan,
        normalized_document=document,
        format_template=format_template,
        review_evidence=packet,
        build_meta={
            "build_id": args.build_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_file": Path(str(source.get("path") or "")).name,
            "source_pdf_sha256": source.get("sha256") or "",
            "workbook_name": workbook_path.name,
        },
    )

    manifest = {
        "schema": "v09_fresh_build_manifest/1",
        "build_id": args.build_id,
        "status": "REVIEW_WORKBOOK_SUCCESSOR",
        "successor_of": source_manifest.get("build_id"),
        "successor_reason": (
            "review workbook round: the DOCX, PDF and generation report are copied "
            "byte-identically from the accepted build; the delivered sheet of "
            "投标项目复核表.xlsx is carried over unchanged and the reviewer views are "
            "appended, so no Word rendering is repeated"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "generated": {
            "docx": str(target / "基础投标文件.docx"),
            "docx_sha256": copied.get("基础投标文件.docx", {}).get("sha256"),
            "docx_bytes": copied.get("基础投标文件.docx", {}).get("bytes"),
            "pdf": str(target / "基础投标文件.pdf"),
            "pdf_sha256": copied.get("基础投标文件.pdf", {}).get("sha256"),
            "pdf_bytes": copied.get("基础投标文件.pdf", {}).get("bytes"),
            "pdf_page_count": (source_manifest.get("generated") or {}).get("pdf_page_count"),
            "generation_report": str(target / "generation_report.json"),
            "generation_report_sha256": copied.get("generation_report.json", {}).get("sha256"),
            "qa_report": str(target / "qa_report.json"),
            "review_workbook": str(workbook_path),
            "review_workbook_sha256": sha256(workbook_path),
            "review_workbook_bytes": workbook_path.stat().st_size,
            "review_workbook_carried_sheet_sha256": delivered_before,
        },
        "pipeline": {
            "argv": [
                "v1_build_review_workbook",
                "--build",
                str(source_build),
                "--build-id",
                args.build_id,
            ],
            "returncode": 0,
            "word_render_repeated": False,
        },
        "artifact_identity": {
            name: {
                "source_build_sha256": sha256(source_build / name),
                "successor_sha256": copied[name]["sha256"],
                "byte_identical": identical.get(name, False),
            }
            for name in PINNED
            if name in copied
        },
    }
    (target / "build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    report = {
        "schema": "v1_review_workbook_build/1",
        "source_build": str(source_build),
        "build_id": args.build_id,
        "build_dir": str(target),
        "word_render_repeated": False,
        "artifact_identity": manifest["artifact_identity"],
        "workbook": manifest["generated"]["review_workbook"],
        "workbook_sha256": manifest["generated"]["review_workbook_sha256"],
        "workbook_bytes": manifest["generated"]["review_workbook_bytes"],
        "views": views,
    }
    out = Path(args.out) if args.out else None
    if out is not None:
        if not out.is_absolute():
            out = REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
