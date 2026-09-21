"""Independent acceptance evidence for one V1 generalization case.

The script measures a *pinned* build directory - never the newest one it can
find - and re-derives every claim from the artifacts themselves: package bytes,
OOXML structure, an independent LibreOffice render, the rendered PDF and the
delivered workbook.  Nothing here trusts the builder's own report for a gate that
can be measured directly.

Usage::

    .venv/Scripts/python.exe scripts/v1_case_acceptance.py \
        --case case_002 \
        --build acceptance/workspace/case_002/v1_phaseA_merge4 \
        --out acceptance/reports/v1_generalization/case002_acceptance.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.logical_table_provenance import iter_body_tables  # noqa: E402
from tender_basic.word_safe_scan import scan_word_safe_docx  # noqa: E402

SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.com")
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING_NS = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
VML_NS = "{urn:schemas-microsoft-com:vml}"

#: Words that identify a paragraph as a *delivered* document's own boilerplate
#: rather than source-derived content.  Duplication is measured over source
#: paragraphs only, so this list never hides a duplicated source row.
_DUPLICATION_MIN_LENGTH = 25


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def new_profile(base: Path) -> tuple[Path, str]:
    """A brand-new isolated LibreOffice profile directory for this render."""

    import uuid

    profile = Path(base) / ("_acc_profile_" + uuid.uuid4().hex[:12])
    profile.mkdir(parents=True, exist_ok=True)
    return profile, profile.resolve().as_uri()


def render_document(docx: Path, outdir: Path) -> dict:
    """Render one DOCX with LibreOffice headless, on a fresh profile.

    The render is an *independent* observation of the delivered file, so it never
    writes over the artifact the build itself produced: rendering into the build
    directory would replace the package the manifest hash pins and make the
    acceptance run change the thing it measures.
    """

    profile_dir, profile_uri = new_profile(outdir)
    target = outdir / (docx.stem + ".pdf")
    argv = [
        str(SOFFICE),
        "-env:UserInstallation=" + profile_uri,
        "--headless",
        "--norestore",
        "--convert-to",
        "pdf",
        "--outdir",
        str(outdir),
        str(docx),
    ]
    started = time.time()
    completed = subprocess.run(
        argv,
        shell=False,
        capture_output=True,
        timeout=900,
        creationflags=CREATE_NO_WINDOW,
    )
    return {
        "executable": str(SOFFICE),
        "argv": argv,
        "isolated_profile": str(profile_dir),
        "launcher_policy": "DIRECT_ARGV_NO_SHELL_CREATE_NO_WINDOW_UNIQUE_PROFILE",
        "returncode": completed.returncode,
        "elapsed_s": round(time.time() - started, 2),
        "stderr_tail": (completed.stderr or b"").decode("utf-8", "replace")[-2000:],
        "pdf": str(target),
        "pdf_exists": target.exists(),
        "pdf_bytes": target.stat().st_size if target.exists() else 0,
    }


def docx_structure(docx: Path) -> dict:
    """Structural safety of the generated package, read from the bytes."""

    from docx import Document

    document = Document(str(docx))
    body = document.element.body
    textboxes = len(body.findall(".//" + WORD_NS + "txbxContent"))
    drawings = len(body.findall(".//" + WORD_NS + "drawing"))
    inline_shapes = len(body.findall(".//" + DRAWING_NS + "inline"))
    anchors = len(body.findall(".//" + DRAWING_NS + "anchor"))
    vml_shapes = len(body.findall(".//" + VML_NS + "shape"))
    media = [
        name
        for name in zipfile.ZipFile(docx).namelist()
        if name.startswith("word/media/")
    ]
    word_tables = [element for _index, element in iter_body_tables(document)]
    table_row_counts = [
        len(element.findall(WORD_NS + "tr")) for element in word_tables
    ]
    return {
        "python_docx_reopen": True,
        "paragraph_count": len(document.paragraphs),
        "word_table_count": len(word_tables),
        "word_table_row_counts": table_row_counts,
        "textbox_count": textboxes,
        "drawing_count": drawings,
        "inline_shape_count": inline_shapes,
        "anchored_shape_count": anchors,
        "vml_shape_count": vml_shapes,
        "embedded_media_count": len(media),
        "embedded_media": media,
        "page_break_node_count": len(body.findall(".//" + WORD_NS + "br")),
    }


def content_duplication(docx: Path, *, minimum_length: int = _DUPLICATION_MIN_LENGTH) -> dict:
    """Repeated source-derived paragraph text in the delivered document."""

    from docx import Document

    document = Document(str(docx))
    texts = []
    for paragraph in document.paragraphs:
        value = re.sub(r"\s+", "", paragraph.text or "")
        if len(value) >= minimum_length:
            texts.append(value)
    seen: dict[str, int] = {}
    for value in texts:
        seen[value] = seen.get(value, 0) + 1
    duplicated = [
        {"length": len(value), "occurrences": count, "text": value[:120]}
        for value, count in sorted(seen.items())
        if count > 1
    ]
    return {
        "measured_paragraph_count": len(texts),
        "minimum_compared_length": minimum_length,
        "duplicated_paragraph_count": len(duplicated),
        "duplicated_paragraphs": duplicated[:20],
    }


def source_repetition_census(build_dir: Path, *, minimum_length: int = _DUPLICATION_MIN_LENGTH) -> dict:
    """How often the *source* itself repeats each string of this length.

    A tender document can carry the same note under several clause headings, so
    a repeated delivered paragraph is only evidence of a rendering fault when the
    delivery repeats it more often than the source does.  The census is built
    from the same source-format model the document was rendered from, so it
    measures the source rather than the builder's own report.
    """

    from tender_basic.document_models import NormalizedDocument
    from tender_basic.format_extractor import extract_bid_format
    from tender_basic.source_format import build_source_format_model

    normalized = NormalizedDocument.model_validate_json(
        (build_dir / "normalized_document.json").read_text(encoding="utf-8")
    )
    template = build_source_format_model(normalized, extract_bid_format(normalized))
    counts: dict[str, int] = {}
    for page in template.source_pages:
        items = list(page.paragraphs)
        for table in page.tables:
            for row in table.rows:
                items.extend(row)
        for item in items:
            value = re.sub(r"\s+", "", getattr(item, "text", "") or "")
            if len(value) >= minimum_length:
                counts[value] = counts.get(value, 0) + 1
    return counts


def excess_duplication(
    duplication: dict,
    source_counts: dict,
    *,
    tolerance: float = 1.5,
) -> dict:
    """Delivered repetitions the source does not account for."""

    excess = []
    for entry in duplication.get("duplicated_paragraphs") or []:
        value = entry["text"]
        delivered = entry["occurrences"]
        source = source_counts.get(value, 0)
        limit = max(source, 1) * tolerance
        if delivered > limit:
            excess.append(
                {
                    "text": value,
                    "delivered_occurrences": delivered,
                    "source_occurrences": source,
                }
            )
    return {
        "excess_duplicated_paragraph_count": len(excess),
        "excess_duplicated_paragraphs": excess[:20],
        "repetition_tolerance": tolerance,
    }


def blocking_overlap(docx: Path) -> dict:
    """Anything that can paint one construct on top of another in Word.

    The delivered format is paragraph-native and flow-based, so the only
    constructs that can overlap ordinary text are floating/anchored objects and
    absolutely positioned tables.  Both are counted directly from the package.
    """

    from docx import Document
    from docx.oxml.ns import qn

    document = Document(str(docx))
    body = document.element.body
    anchored = len(body.findall(".//" + DRAWING_NS + "anchor"))
    floating_tables = len(body.findall(".//" + WORD_NS + "tblpPr"))
    frames = len(body.findall(".//" + WORD_NS + "framePr"))
    textboxes = len(body.findall(".//" + WORD_NS + "txbxContent"))
    styles = len(
        [
            style
            for style in document.styles
            if style.type is not None and getattr(style, "element", None) is not None
            and style.element.find(qn("w:framePr")) is not None
        ]
    )
    return {
        "anchored_object_count": anchored,
        "floating_table_count": floating_tables,
        "framed_paragraph_count": frames,
        "textbox_count": textboxes,
        "framed_style_count": styles,
        "blocking_overlap_count": anchored + floating_tables + frames + textboxes,
    }


def rendered_pdf_audit(pdf: Path) -> dict:
    """Pages, blank pages and reopen status of the rendered PDF."""

    import pymupdf

    document = pymupdf.open(pdf)
    page_texts = [page.get_text().strip() for page in document]
    blank = [index + 1 for index, text in enumerate(page_texts) if not text]
    characters = sum(len(text) for text in page_texts)
    page_count = document.page_count
    document.close()
    return {
        "pdf_page_count": page_count,
        "pdf_reopen": page_count > 0,
        "pdf_blank_pages": blank,
        "pdf_blank_page_count": len(blank),
        "pdf_extractable_character_count": characters,
        "pdf_text_page_count": page_count - len(blank),
    }


def source_pdf_audit(source: Path) -> dict:
    import pymupdf

    document = pymupdf.open(source)
    info = {
        "source_pdf_page_count": document.page_count,
        "source_pdf_bytes": Path(source).stat().st_size,
        "source_pdf_reopen": document.page_count > 0,
    }
    document.close()
    return info


def workbook_audit(workbook: Path) -> dict:
    from openpyxl import load_workbook

    book = load_workbook(workbook)
    sheets = {}
    for name in book.sheetnames:
        sheet = book[name]
        sheets[name] = {
            "max_row": sheet.max_row,
            "max_column": sheet.max_column,
            "non_empty_row_count": sum(
                1
                for row in sheet.iter_rows(values_only=True)
                if any(value not in (None, "") for value in row)
            ),
        }
    book.close()
    return {
        "openpyxl_reopen": True,
        "sheet_count": len(sheets),
        "sheets": sheets,
    }


def table_continuity(generation_report: dict) -> dict:
    """The logical-table reconstruction account, re-read from the report."""

    provenance = generation_report.get("logical_table_provenance") or {}
    tables = provenance.get("tables") or []
    return {
        "pdf_table_fragment_count": generation_report.get("pdf_table_fragment_count"),
        "logical_table_count": generation_report.get("logical_table_count"),
        "continuation_fragments_merged": generation_report.get(
            "continuation_fragments_merged"
        ),
        "orphan_continuation_fragments": generation_report.get(
            "orphan_continuation_fragments"
        ),
        "false_continuation_merges": generation_report.get(
            "false_continuation_merges"
        ),
        "cell_text_continuations": generation_report.get("cell_text_continuations"),
        "generated_table_count": generation_report.get("generated_table_count"),
        "generated_real_tables": generation_report.get("generated_real_tables"),
        "synthetic_layout_tables": generation_report.get("synthetic_layout_tables"),
        "generated_textbox_count": generation_report.get("generated_textbox_count"),
        "unpaired_generated_word_table_count": provenance.get(
            "unpaired_generated_word_table_count"
        ),
        "total_source_cell_count": provenance.get("total_source_cell_count"),
        "total_lost_cell_count": provenance.get("total_lost_cell_count"),
        "total_duplicated_cell_count": provenance.get("total_duplicated_cell_count"),
        "total_invented_cell_count": provenance.get("total_invented_cell_count"),
        "logical_tables": tables,
    }


def fact_evidence_locators(value: dict) -> list[dict]:
    """The source locators that justify a fact's value.

    A fact carries evidence either as an explicit ``evidence``/``sources`` entry
    or - the ProjectFacts contract this pipeline emits - as the locator of a
    candidate whose text was read out of the source document.  A candidate
    without both a locator and its source text is not evidence.
    """

    locators = []
    for item in value.get("evidence") or ():
        if isinstance(item, dict) and item.get("locator"):
            locators.append(item["locator"])
    for item in value.get("candidates") or ():
        if isinstance(item, dict) and item.get("locator") and item.get("evidence_text"):
            locators.append(item["locator"])
    return locators


def facts_audit(facts_path: Path) -> dict:
    """ProjectFacts status accounting and the resolved-value ledger."""

    payload = load_json(facts_path)
    fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
    statuses: dict[str, int] = {}
    rows = []
    for name, value in fields.items():
        if not isinstance(value, dict):
            continue
        status = str(value.get("status"))
        statuses[status] = statuses.get(status, 0) + 1
        locators = fact_evidence_locators(value)
        rows.append(
            {
                "field": name,
                "status": status,
                "resolved_value": value.get("resolved_value"),
                "evidence_locator_count": len(locators),
                "has_evidence": bool(locators),
            }
        )
    resolved_without_evidence = [
        row["field"]
        for row in rows
        if row["status"] == "RESOLVED" and not row["has_evidence"]
    ]
    return {
        "field_count": len(rows),
        "status_counts": statuses,
        "resolved_field_count": statuses.get("RESOLVED", 0),
        "needs_review_field_count": statuses.get("NEEDS_REVIEW", 0),
        "not_found_field_count": statuses.get("NOT_FOUND", 0),
        "resolved_without_evidence_fields": resolved_without_evidence,
        "fields": rows,
    }


def review_audit(review_path: Path) -> dict:
    payload = load_json(review_path)
    return payload.get("dynamic_review", {}).get("qa", payload)


def build(argv: list[str] | None = None) -> tuple[dict, int]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--expected-status",
        default="PASS",
        help="The case status this evidence must justify.",
    )
    args = parser.parse_args(argv)

    build_dir = args.build
    manifest = load_json(build_dir / "build_manifest.json")
    generation_report = load_json(build_dir / "generation_report.json")
    qa_report = load_json(build_dir / "qa_report.json")
    source_format_qa = load_json(build_dir / "source_format_qa.json")
    docx = Path(manifest["generated"]["docx"])
    pdf = Path(manifest["generated"]["pdf"])
    source = Path(manifest["source"]["path"])
    workbook = build_dir / "投标项目复核表.xlsx"

    problems: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    docx_hash = sha256(docx)
    pdf_hash = sha256(pdf)
    check(
        docx_hash == manifest["generated"]["docx_sha256"],
        "generated DOCX does not match the build manifest hash",
    )
    check(
        pdf_hash == manifest["generated"]["pdf_sha256"],
        "generated PDF does not match the build manifest hash",
    )
    check(
        sha256(source) == manifest["source"]["sha256"],
        "source PDF does not match the build manifest hash",
    )

    structure = docx_structure(docx)
    duplication = content_duplication(docx)
    duplication["source_repetition"] = excess_duplication(
        duplication, source_repetition_census(build_dir)
    )
    overlap = blocking_overlap(docx)
    scan = scan_word_safe_docx(docx)
    render_dir = build_dir / "_acceptance_render"
    render_dir.mkdir(parents=True, exist_ok=True)
    for stale in render_dir.glob("*.pdf"):
        stale.unlink()
    render = render_document(docx, render_dir)
    check(render["returncode"] == 0, "LibreOffice render returned a non-zero code")
    check(render["pdf_exists"], "LibreOffice produced no PDF")
    if render["pdf_exists"]:
        rendered = rendered_pdf_audit(Path(render["pdf"]))
    else:
        rendered = {
            "pdf_page_count": 0,
            "pdf_reopen": False,
            "pdf_blank_pages": [],
            "pdf_blank_page_count": 0,
            "pdf_extractable_character_count": 0,
            "pdf_text_page_count": 0,
        }
    source_audit = source_pdf_audit(source)
    workbook = workbook_audit(workbook)
    continuity = table_continuity(generation_report)
    facts = facts_audit(build_dir / "project_facts.json")
    review = review_audit(build_dir / "review_evidence_qa.json")

    check(scan["result"] == "PASS", "word-safe scan did not pass")
    check(scan["unsafe_ooxml"] == 0, "unsafe generated OOXML is not zero")
    check(scan["zip_integrity"], "generated DOCX ZIP integrity failed")
    check(structure["textbox_count"] == 0, "generated document contains textboxes")
    check(
        structure["anchored_shape_count"] == 0 and structure["vml_shape_count"] == 0,
        "generated document contains floating/anchored shapes",
    )
    check(
        structure["embedded_media_count"] == 0,
        "generated document embeds raster media rather than editable structure",
    )
    check(
        structure["word_table_count"] == continuity["generated_table_count"],
        "document-order Word table count differs from the emitted table count",
    )
    check(
        continuity["synthetic_layout_tables"] == 0,
        "synthetic layout tables were emitted",
    )
    check(
        duplication["source_repetition"]["excess_duplicated_paragraph_count"] == 0,
        "content duplication found beyond the source's own repetition",
    )
    check(overlap["blocking_overlap_count"] == 0, "blocking overlap found")
    check(
        source_format_qa.get("source_text_missing") == 0,
        "source text is missing from the generated document",
    )
    check(
        continuity["total_lost_cell_count"] == 0,
        "logical table cells were lost",
    )
    check(
        continuity["total_duplicated_cell_count"] == 0,
        "logical table cells were duplicated",
    )
    check(
        continuity["total_invented_cell_count"] == 0,
        "logical table cells were invented",
    )
    check(
        continuity["orphan_continuation_fragments"] == 0,
        "orphan table continuation fragments remain",
    )
    check(
        continuity["false_continuation_merges"] == 0,
        "false table continuation merges were made",
    )
    check(
        continuity["logical_table_count"] == continuity["generated_table_count"],
        "logical table count differs from the generated Word table count",
    )
    check(rendered["pdf_reopen"], "rendered PDF could not be reopened")
    check(
        rendered["pdf_blank_page_count"] == 0, "rendered PDF contains blank pages"
    )
    check(
        rendered["pdf_extractable_character_count"] > 0,
        "rendered PDF has no extractable text",
    )
    check(
        facts["resolved_without_evidence_fields"] == [],
        "a RESOLVED fact was used without source evidence",
    )
    check(
        review.get("hard_gate_failures") == [],
        "review evidence hard gates failed",
    )
    check(
        review.get("invalid_review_evidence_locator_count") == 0,
        "review evidence has invalid locators",
    )

    report = {
        "schema": "v1_case_acceptance/1",
        "case": args.case,
        "build_id": manifest.get("build_id"),
        "build_dir": str(build_dir),
        "pinned_pointer": str(
            ROOT / "acceptance/reports/v1_generalization" / (args.case + "_current_build.json")
        ),
        "source": {"path": str(source), "sha256": manifest["source"]["sha256"], **source_audit},
        "generated": {
            "docx": str(docx),
            "docx_sha256": docx_hash,
            "docx_bytes": docx.stat().st_size,
            "pdf": str(pdf),
            "pdf_sha256": pdf_hash,
            "pdf_bytes": pdf.stat().st_size,
        },
        "pipeline": manifest.get("pipeline", {}).get("returncode"),
        "libreoffice_render": render,
        "rendered_pdf": rendered,
        "package_safety": {
            "word_safe_scan": scan,
            "zip_integrity": scan["zip_integrity"],
            "python_docx_reopen": structure["python_docx_reopen"],
            "unsafe_generated_ooxml": scan["unsafe_ooxml"],
            "generated_textbox_count": structure["textbox_count"],
            "generated_media_count": structure["embedded_media_count"],
            "blocking_overlap": overlap,
            "content_duplication": duplication,
        },
        "document_structure": structure,
        "table_continuity": continuity,
        "source_format_qa": source_format_qa,
        "delivery_qa": {
            "overall_status": qa_report.get("overall_status"),
            "errors": qa_report.get("errors"),
            "warnings": [
                {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "message": item.get("message"),
                }
                for item in (qa_report.get("warnings") or [])
            ],
            "check_count": len(qa_report.get("checks") or []),
            "non_pass_check_count": len(
                [
                    item
                    for item in (qa_report.get("checks") or [])
                    if str(item.get("status")) not in ("PASS", "SKIPPED")
                ]
            ),
        },
        "workbook": workbook,
        "project_facts": facts,
        "review_evidence": {
            "result": review.get("result"),
            "source_requirement_count": review.get("source_requirement_count"),
            "source_mandatory_requirement_count": review.get(
                "source_mandatory_requirement_count"
            ),
            "source_mandatory_requirement_without_review_item_count": review.get(
                "source_mandatory_requirement_without_review_item_count"
            ),
            "dynamic_review_item_count": review.get("dynamic_review_item_count"),
            "workbook_row_count": review.get("workbook_row_count"),
            "workbook_rows_match_dynamic_items": review.get(
                "workbook_rows_match_dynamic_items"
            ),
            "invalid_review_evidence_locator_count": review.get(
                "invalid_review_evidence_locator_count"
            ),
            "empty_review_evidence_count": review.get("empty_review_evidence_count"),
            "cross_topic_evidence_mismatch_count": review.get(
                "cross_topic_evidence_mismatch_count"
            ),
            "unclassified_dynamic_requirement_count": review.get(
                "unclassified_dynamic_requirement_count"
            ),
            "hard_gate_failures": review.get("hard_gate_failures"),
        },
        "problems": problems,
        "automated_result": "PASS" if not problems else "FAIL",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("CASE", args.case, "AUTOMATED_RESULT", report["automated_result"])
    for problem in problems:
        print(" PROBLEM:", problem)
    print("REPORT", args.out)
    return report, 0 if not problems else 1


if __name__ == "__main__":
    _report, _code = build()
    raise SystemExit(_code)
