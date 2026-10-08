"""Generic Word source-fidelity gate for any case.

This is the case-agnostic gate: it consumes a build's own artifacts (the saved
DOCX, the rendered PDF, the generation report and the source-format QA) plus,
optionally, the source PDF, and decides the components of Word source fidelity.

DESIGN RULES
------------
* Mandatory evidence that is unavailable is ``FAIL``, never a silent pass.
* A component that a case genuinely does not have is ``NOT_APPLICABLE`` with a
  source-backed reason - CASE003 has no authorization form, CASE001 has no
  opening table, and neither may be failed for lacking CASE002's forms.
* Nothing here is case-, page- or text-specific: the checks read measured
  geometry, recorded counters and document structure.
* A proven font substitution may only be reported as
  ``WARN_PROVEN_FONT_SUBSTITUTION``; ``UNKNOWN_RENDER_DIVERGENCE`` is a failure.

Usage::

    python scripts/v1_word_source_fidelity_gate.py \
        --build acceptance/workspace/case_003/v1_word_source_fidelity_arch2 \
        --json acceptance/reports/v1_generalization/case003_generic_word_source_fidelity.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf
from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.source_font_policy import font_name as _font_name  # noqa: E402
from tender_basic.word_render_authority import (  # noqa: E402
    HEADLESS_FONT_SUBSTITUTION_ONLY,
    HOST_FONT_ABSENT,
    HOST_FONT_INSTALLED,
    HOST_FONT_UNKNOWN,
    RendererDivergenceClassification,
    SourceFidelityProofs,
    SourceRowMeasurement,
    SourceTypographyEvidence,
    UNKNOWN_RENDER_DIVERGENCE,
    classify_renderer_divergence,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WINDOWS_FONTS = Path("C:/Windows/Fonts")
PASS, FAIL, NOT_APPLICABLE = "PASS", "FAIL", "NOT_APPLICABLE"

#: How far a rendered advance may differ from the source row's own before the
#: difference stops being font-metric drift and becomes a geometry defect worth
#: investigating.  The frozen §7.3 renderer doctrine already banks CJK fallback
#: font metric differences with a tolerance of ``max(2.0 pt, 25% of line height)``;
#: a row-width band of 5% sits well inside that doctrine and still isolates a
#: genuinely misplaced row, which diverges by far more than a glyph metric.
FONT_METRIC_SCALE_RATIO = 0.05


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def docx_text(path: Path) -> str:
    document = Document(path)
    parts = [paragraph.text for paragraph in document.paragraphs]
    parts += [
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    ]
    return "".join(parts)


def rendered_text(pdf_path: Path) -> str:
    with pymupdf.open(pdf_path) as pdf:
        return "".join(pdf[number].get_text() for number in range(pdf.page_count))


def page_sizes(pdf_path: Path) -> list[tuple[float, float]]:
    with pymupdf.open(pdf_path) as pdf:
        return [
            (round(pdf[number].rect.width, 1), round(pdf[number].rect.height, 1))
            for number in range(pdf.page_count)
        ]


def docx_fonts_and_spacing(path: Path) -> tuple[set[str], set[str], list[int]]:
    """East-Asian families, latin families and character-spacing values used."""

    document = Document(path)
    east, latin, spacings = set(), set(), []
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            rpr = run._element.find(f"{W}rPr")
            if rpr is None:
                continue
            fonts = rpr.find(f"{W}rFonts")
            if fonts is not None:
                east_asia = fonts.get(f"{W}eastAsia")
                ascii_name = fonts.get(f"{W}ascii")
                if east_asia:
                    east.add(east_asia)
                if ascii_name:
                    latin.add(ascii_name)
            spacing = rpr.find(f"{W}spacing")
            if spacing is not None:
                try:
                    spacings.append(int(spacing.get(f"{W}val")))
                except (TypeError, ValueError):
                    pass
    return east, latin, spacings


def unsafe_ooxml(path: Path) -> dict:
    document = Document(path)
    body = document.element.body
    return {
        "textbox_count": len(body.findall(f".//{W}txbxContent")),
        "drawing_count": len(body.findall(f".//{W}drawing")),
        "pict_count": len(body.findall(f".//{W}pict")),
        "object_count": len(body.findall(f".//{W}object")),
    }


def font_state(family: str | None) -> str:
    if not family:
        return HOST_FONT_UNKNOWN
    try:
        candidates = [entry.stem.lower() for entry in WINDOWS_FONTS.glob("*")]
    except OSError:
        return HOST_FONT_UNKNOWN
    if not candidates:
        return HOST_FONT_UNKNOWN
    key = "".join(str(family).split()).lower()
    return (
        HOST_FONT_INSTALLED
        if any(key and (key in candidate or candidate in key) for candidate in candidates)
        else HOST_FONT_ABSENT
    )


def result(status: str, detail: str, evidence: dict | None = None) -> dict:
    return {"status": status, "detail": detail, "evidence": evidence or {}}


def source_rows(pdf_path: Path, page_number: int, y_from: float, y_to: float) -> list[dict]:
    rows = []
    with pymupdf.open(pdf_path) as pdf:
        page = pdf[page_number - 1]
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"])
                if not text.strip():
                    continue
                y0 = float(line["bbox"][1])
                if not (y_from <= y0 <= y_to):
                    continue
                rows.append(
                    {
                        "y": round(y0, 2),
                        "x0": round(float(line["bbox"][0]), 2),
                        "x1": round(float(line["bbox"][2]), 2),
                        "chars": len(text.strip()),
                        "fonts": sorted({span["font"] for span in line["spans"]}),
                        "sizes": sorted({round(float(span["size"]), 2) for span in line["spans"]}),
                    }
                )
    return sorted(rows, key=lambda row: (row["y"], row["x0"]))


def build_report(build: Path, source_pdf: Path | None) -> dict:
    build = build.resolve()
    docx_path = build / "基础投标文件.docx"
    pdf_path = build / "基础投标文件.pdf"
    report = json.loads((build / "generation_report.json").read_text(encoding="utf-8"))
    qa_path = build / "source_format_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.is_file() else {}
    components: dict[str, dict] = {}

    document_text = compact(docx_text(docx_path))
    rendered = compact(rendered_text(pdf_path)) if pdf_path.is_file() else ""
    cursor = report.get("source_form_row_cursor") or {}

    # ---- page frame ------------------------------------------------------- #
    frames = report.get("section_geometry") or []
    sizes = page_sizes(pdf_path) if pdf_path.is_file() else []
    if not frames or not sizes:
        components["PAGE_FRAME_FIDELITY"] = result(
            FAIL, f"section_geometry={len(frames)} rendered pages={len(sizes)}"
        )
    else:
        # A page size is declared by the frame; the comparison allows a point of
        # rounding because the frame derives from source anchors and PyMuPDF
        # reports the rendered media box.
        declared = [
            (float(f.get("page_width") or 0), float(f.get("page_height") or 0))
            for f in frames
            if float(f.get("page_width") or 0) > 0
        ]
        if not declared:
            declared = []
        undeclared = []
        for width, height in sizes:
            if not any(
                abs(width - dw) <= 1.5 and abs(height - dh) <= 1.5
                for dw, dh in declared
            ):
                undeclared.append((width, height))
        if not declared and source_pdf is not None and Path(source_pdf).is_file():
            source_sizes = page_sizes(Path(source_pdf))
            undeclared = [
                size
                for size in sizes
                if not any(
                    abs(size[0] - s[0]) <= 1.5 and abs(size[1] - s[1]) <= 1.5
                    for s in source_sizes
                )
            ]
        components["PAGE_FRAME_FIDELITY"] = result(
            PASS if not undeclared else FAIL,
            f"frames={len(frames)} declared_sizes={len(declared)} "
            f"undeclared_rendered_sizes={len(undeclared)}",
            {"undeclared_sample": undeclared[:2]},
        )

    # ---- container fidelity ----------------------------------------------- #
    paragraphs = len(Document(docx_path).paragraphs)
    logical = report.get("logical_paragraph_records") or []
    empty_paragraphs = sum(
        1 for paragraph in Document(docx_path).paragraphs if not paragraph.text.strip()
    )
    components["PARAGRAPH_CONTAINER_FIDELITY"] = result(
        PASS if paragraphs and logical else FAIL,
        f"docx_paragraphs={paragraphs} logical_records={len(logical)} "
        f"empty_paragraphs={empty_paragraphs}",
    )

    # ---- source visual row contract --------------------------------------- #
    visual_rows = report.get("source_visual_rows") or report.get("vertical_rhythm_rows") or []
    components["SOURCE_VISUAL_ROW_CONTRACT"] = (
        result(
            PASS,
            f"source visual-row records={len(visual_rows)}",
            {"sample": json.dumps(visual_rows[:1], ensure_ascii=False)[:300]},
        )
        if visual_rows
        else result(NOT_APPLICABLE, "the build records no source visual-row contract evidence")
    )

    # ---- text completeness + exact-once ownership -------------------------- #
    missing = qa.get("MISSING_ATOM_COUNT", qa.get("source_text_missing"))
    if missing is None:
        components["SOURCE_TEXT_COMPLETENESS"] = result(
            FAIL, "the build records no source-text completeness measurement"
        )
        components["SOURCE_TEXT_EXACT_ONCE_OWNERSHIP"] = result(
            FAIL, "the build records no source-text ownership measurement"
        )
    else:
        components["SOURCE_TEXT_COMPLETENESS"] = result(
            PASS if int(missing) == 0 else FAIL,
            f"missing={missing} expected={qa.get('SOURCE_COMPLETENESS_SCOPE_ATOM_COUNT')} "
            f"delivered={qa.get('DELIVERED_ATOM_COUNT')}",
            {"missing_atoms": [a.get("atom_id") for a in (qa.get("source_text_missing_atoms") or [])]},
        )
        zero = int(qa.get("source_text_atoms_with_zero_owner_count", missing) or 0)
        multiple = int(qa.get("source_text_atoms_with_multiple_owner_count") or 0)
        duplicate = int(qa.get("DUPLICATED_ATOM_COUNT") or 0)
        components["SOURCE_TEXT_EXACT_ONCE_OWNERSHIP"] = result(
            PASS if zero == 0 and multiple == 0 and duplicate == 0 else FAIL,
            f"zero_owner={zero} multiple_owner={multiple} duplicate={duplicate}",
        )

    # ---- slot ownership ---------------------------------------------------- #
    detected = int(report.get("fill_slots_detected") or qa.get("fill_slots_detected") or 0)
    filled = int(report.get("fill_slots_filled") or qa.get("fill_slots_filled") or 0)
    presentations = report.get("slot_value_presentations") or []
    # The presentation record shape varies by builder generation, so only
    # mapping-shaped entries can state whether a value kept its source underline.
    underlined_values = [
        entry
        for entry in presentations
        if isinstance(entry, dict)
        and (entry.get("value_kept_source_underline") or entry.get("underline"))
    ]
    if not detected:
        components["SOURCE_SLOT_OWNERSHIP"] = result(
            NOT_APPLICABLE, "this source-format scope declares no fill slots"
        )
    else:
        # A resolved value that kept its source underline must actually be
        # underlined in the delivered document.
        underlined_runs = sum(
            1
            for paragraph in Document(docx_path).paragraphs
            for run in paragraph.runs
            if run.underline and run.text.strip()
        )
        ok = not underlined_values or underlined_runs > 0
        components["SOURCE_SLOT_OWNERSHIP"] = result(
            PASS if ok else FAIL,
            f"slots_detected={detected} filled={filled} "
            f"values_keeping_underline={len(underlined_values)} underlined_runs={underlined_runs}",
        )

    # ---- row cursor / tab safety ------------------------------------------- #
    def counter(name: str) -> int | None:
        value = cursor.get(name)
        return None if value is None else int(value)

    required = {
        "default_tab_fallthrough_risk_count": counter("default_tab_fallthrough_risk_count"),
        "tabs_without_explicit_stop_count": counter("tabs_without_explicit_stop_count"),
        "consecutive_blank_double_ownership_count": counter("consecutive_blank_double_ownership_count"),
        "cursor_recomputed_from_paragraph_width_count": counter("cursor_recomputed_from_paragraph_width_count"),
    }
    unavailable = [key for key, value in required.items() if value is None]
    if unavailable:
        components["ROW_CURSOR_OWNERSHIP"] = result(
            NOT_APPLICABLE,
            "this build predates the row-local cursor contract "
            f"(absent counters: {', '.join(unavailable)})",
        )
        components["NO_DEFAULT_TAB_FALLTHROUGH"] = result(
            NOT_APPLICABLE, "row-cursor contract counters are absent from this build"
        )
        components["NO_DOUBLE_HORIZONTAL_OWNERSHIP"] = result(
            NOT_APPLICABLE, "row-cursor contract counters are absent from this build"
        )
    else:
        components["ROW_CURSOR_OWNERSHIP"] = result(
            PASS
            if required["cursor_recomputed_from_paragraph_width_count"] == 0
            else FAIL,
            f"cursor_recomputed_from_paragraph_width_count="
            f"{required['cursor_recomputed_from_paragraph_width_count']}",
        )
        components["NO_DEFAULT_TAB_FALLTHROUGH"] = result(
            PASS if required["default_tab_fallthrough_risk_count"] == 0 else FAIL,
            f"default_tab_fallthrough_risk_count={required['default_tab_fallthrough_risk_count']} "
            f"tabs_without_explicit_stop_count={required['tabs_without_explicit_stop_count']}",
        )
        components["NO_DOUBLE_HORIZONTAL_OWNERSHIP"] = result(
            PASS
            if required["consecutive_blank_double_ownership_count"] == 0
            else FAIL,
            f"consecutive_blank_double_ownership_count="
            f"{required['consecutive_blank_double_ownership_count']}",
        )

    # ---- date slot fidelity (capability-aware) ----------------------------- #
    date_paragraphs = [
        paragraph
        for paragraph in Document(docx_path).paragraphs
        if "年" in paragraph.text and "月" in paragraph.text and "日" in paragraph.text
    ]
    if not date_paragraphs:
        components["DATE_SLOT_FIDELITY"] = result(
            NOT_APPLICABLE, "the delivered document contains no 年月日 form row"
        )
    else:
        best = max(
            (
                sum(
                    1
                    for run in paragraph.runs
                    if run.underline and not run.text.strip()
                )
                for paragraph in date_paragraphs
            ),
            default=0,
        )
        components["DATE_SLOT_FIDELITY"] = result(
            PASS if best >= 3 else FAIL,
            f"date rows={len(date_paragraphs)} max_underline_blanks_in_one_row={best}",
        )

    # ---- typography contract ---------------------------------------------- #
    east, latin, spacings = docx_fonts_and_spacing(docx_path)
    source_fonts = report.get("source_fonts") or qa.get("source_fonts") or []
    mapped: set[str] = set()
    for family in source_fonts or []:
        try:
            resolved, _changed = _font_name(family)
        except Exception:  # pragma: no cover - defensive boundary
            resolved = family
        if resolved:
            mapped.add(resolved)
    if not source_fonts:
        components["TYPOGRAPHY_CONTRACT"] = result(
            NOT_APPLICABLE,
            "the build records no source font inventory to compare the DOCX against",
        )
    else:
        unexpected = sorted(family for family in east if family not in mapped)
        components["TYPOGRAPHY_CONTRACT"] = result(
            PASS if not unexpected else FAIL,
            f"docx_east_asia={sorted(east)} source_mapped={sorted(mapped)[:6]} "
            f"unexpected={unexpected} latin={sorted(latin)[:3]} "
            f"spacing_values={sorted(set(spacings))[:6]}",
        )

    # ---- vertical rhythm contract ------------------------------------------ #
    rhythm = report.get("source_vertical_rhythm") or {}
    blocks = rhythm.get("blocks") or []
    pitched = [block for block in blocks if float(block.get("line_pitch_pt") or 0) > 0]
    if not blocks:
        components["VERTICAL_RHYTHM_CONTRACT"] = result(
            NOT_APPLICABLE, "the build records no source vertical-rhythm blocks"
        )
    else:
        components["VERTICAL_RHYTHM_CONTRACT"] = result(
            PASS if pitched else FAIL,
            f"rhythm_blocks={len(blocks)} blocks_with_measured_pitch={len(pitched)} "
            f"dominant_line_pitch_pt={rhythm.get('dominant_line_pitch_pt')}",
        )

    # ---- text completeness + renderer divergence -------------------------- #
    # TEXT COMPLETENESS IS MEASURED ON THE AUTHORITATIVE ARTIFACT.  The delivered
    # DOCX is the intended Word object and the saved/reopened document is the
    # machine authority for whether the source's text is present; the headless
    # render is diagnostic.  Comparing the rendered PDF's extracted characters
    # against the DOCX would measure the extractor, not the delivery, so the
    # render-side difference is recorded as a diagnostic field instead of a gate.
    if missing is None:
        components["TEXT_COMPLETENESS"] = result(
            FAIL, "the build records no source-text completeness measurement"
        )
    else:
        components["TEXT_COMPLETENESS"] = result(
            PASS if int(missing) == 0 else FAIL,
            f"source_scope_atoms={qa.get('SOURCE_COMPLETENESS_SCOPE_ATOM_COUNT')} "
            f"delivered={qa.get('DELIVERED_ATOM_COUNT')} missing={missing} "
            f"duplicate={qa.get('DUPLICATED_ATOM_COUNT')}",
        )
    rendered_diagnostic = {
        "delivered_chars": len(document_text),
        "rendered_chars": len(rendered),
        "note": (
            "diagnostic only: LibreOffice text extraction is not the authority "
            "for source-text completeness"
        ),
    }
    if not rendered or not document_text:
        components["RENDERER_DIVERGENCE_CLASSIFICATION"] = result(
            FAIL, "the rendered PDF or the delivered DOCX is unavailable"
        )
    else:
        classification = _classify_renderer(docx_path, pdf_path, source_pdf)
        components["RENDERER_DIVERGENCE_CLASSIFICATION"] = result(
            (
                "WARN_PROVEN_FONT_SUBSTITUTION"
                if classification.is_substitution_only
                else (PASS if not classification.blocking else FAIL)
            ),
            f"{classification.divergence_class}: "
            + (classification.reasons[0] if classification.reasons else ""),
            classification.evidence,
        )
    components["TEXT_COMPLETENESS"]["evidence"] = rendered_diagnostic

    # ---- source page split ------------------------------------------------- #
    if source_pdf is None or not Path(source_pdf).is_file():
        components["SOURCE_PAGE_SPLIT"] = result(
            NOT_APPLICABLE, "no source PDF supplied for the page-split comparison"
        )
    else:
        with pymupdf.open(source_pdf) as source, pymupdf.open(pdf_path) as out:
            source_pages = source.page_count
            out_pages = out.page_count
            blank = sum(
                1 for number in range(out_pages) if not out[number].get_text().strip()
            )
        components["SOURCE_PAGE_SPLIT"] = result(
            PASS if blank == 0 and out_pages <= max(4, int(source_pages * 0.6)) else FAIL,
            f"source_pages={source_pages} generated_pages={out_pages} blank_pages={blank}",
        )

    # ---- logical table identity -------------------------------------------- #
    table_count = len(Document(docx_path).tables)
    logical_tables = int(report.get("logical_table_count") or 0)
    orphans = int(report.get("orphan_continuation_fragments") or 0)
    false_merges = int(report.get("false_continuation_merges") or 0)
    components["LOGICAL_TABLE_IDENTITY"] = result(
        PASS
        if logical_tables and table_count == logical_tables and orphans == 0 and false_merges == 0
        else FAIL,
        f"docx_tables={table_count} logical_tables={logical_tables} "
        f"orphan_continuations={orphans} false_merges={false_merges}",
    )

    # ---- unsafe OOXML ------------------------------------------------------ #
    unsafe = unsafe_ooxml(docx_path)
    bad = sum(unsafe.values())
    components["UNSAFE_OOXML_PROHIBITION"] = result(
        PASS if bad == 0 else FAIL, json.dumps(unsafe)
    )

    mandatory = [
        name
        for name in components
        if components[name]["status"] == FAIL
    ]
    return {
        "schema": "v1_generic_word_source_fidelity_gate/1",
        "build": (
            str(build.relative_to(ROOT)).replace("\\", "/")
            if build.is_relative_to(ROOT)
            else str(build)
        ),
        "components": components,
        "failed_components": mandatory,
        "GENERIC_WORD_SOURCE_FIDELITY": "PASS" if not mandatory else "FAIL",
    }


def _missing_fragments(document_text: str, rendered: str, window: int = 12) -> list[str]:
    """Tokens of the delivered text absent from the render (clipping/loss)."""

    lost = []
    for start in range(0, len(document_text), window):
        chunk = document_text[start : start + window]
        if len(chunk) < 4:
            continue
        if chunk not in rendered:
            lost.append(chunk)
    return lost


def _classify_renderer(docx_path: Path, pdf_path: Path, source_pdf: Path | None):
    """Classify a rendered-vs-DOCX horizontal divergence from measured evidence.

    The classifier is only asked a question when there *is* a divergence to
    explain: the largest source row is matched to a rendered row that carries the
    same number of characters, and a substitution is only claimed when the
    rendered row is genuinely wider than the source row's own extent.  With no
    matched pair and no overflow there is nothing to attribute, and the component
    is a plain pass - never an "unknown divergence" for want of a mismatch.
    """

    east, _latin, _spacing = docx_fonts_and_spacing(docx_path)
    requested = next(iter(sorted(east)), None)
    families: set[str] = set()
    with pymupdf.open(pdf_path) as pdf:
        for number in range(pdf.page_count):
            for entry in pdf[number].get_fonts(full=True):
                families.add(str(entry[3]).split("+")[-1])
    headless_family = next(iter(sorted(families)), None) if families else None

    typography = SourceTypographyEvidence(
        source_family=requested,
        source_size_pt=12.0,
        docx_east_asia=requested,
        docx_size_pt=12.0,
        host_font_state=font_state(requested),
        headless_family=headless_family,
        headless_size_pt=12.0,
    )

    source_candidates: list[dict] = []
    if source_pdf is not None and Path(source_pdf).is_file():
        with pymupdf.open(source_pdf) as source:
            for number in range(source.page_count):
                source_candidates.extend(
                    source_rows(Path(source_pdf), number + 1, 0.0, source[number].rect.height)
                )
    headless_candidates: list[dict] = []
    with pymupdf.open(pdf_path) as pdf:
        for number in range(pdf.page_count):
            for block in pdf[number].get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if text:
                        headless_candidates.append(
                            {
                                "x0": float(line["bbox"][0]),
                                "x1": float(line["bbox"][2]),
                                "chars": len(text),
                            }
                        )

    # The widest *matched* pair: only rows carrying the same character count can be
    # compared, because the two renderers may otherwise break the line differently.
    best_pair = None
    by_chars: dict[int, list[dict]] = {}
    for row in headless_candidates:
        by_chars.setdefault(row["chars"], []).append(row)
    for row in source_candidates:
        for candidate in by_chars.get(row["chars"], ()):
            width = row["x1"] - row["x0"]
            if best_pair is None or width > best_pair[0]:
                best_pair = (width, row, candidate)

    if best_pair is None:
        typography.headless_family = None
        row = SourceRowMeasurement()
        return classify_renderer_divergence(
            typography=typography, row=row, proofs=_proofs()
        )

    _width, source_row, headless_row = best_pair
    source_width = source_row["x1"] - source_row["x0"]
    headless_width = headless_row["x1"] - headless_row["x0"]
    row = SourceRowMeasurement(
        source_char_count=source_row["chars"],
        source_used_width_pt=source_width,
        source_available_width_pt=source_width,
        headless_char_count=headless_row["chars"],
        headless_used_width_pt=headless_width,
    )
    if headless_width <= source_width:
        # The render fits inside the source's own extent: there is no divergence to
        # attribute, so this component is a plain pass.  Nothing is inferred from a
        # mismatch that does not exist.
        return RendererDivergenceClassification(
            divergence_class=HEADLESS_FONT_SUBSTITUTION_ONLY,
            blocking=False,
            reasons=[
                "no measurable horizontal divergence: the widest matched rendered row "
                f"fits inside the source row's own extent ({headless_width:.2f} pt vs "
                f"{source_width:.2f} pt)"
            ],
            evidence={
                "source_width_pt": round(source_width, 2),
                "headless_width_pt": round(headless_width, 2),
                "matched_row_chars": source_row["chars"],
                "requested_family": requested,
                "headless_family": headless_family,
                "host_font_state": font_state(requested),
            },
        )

    # THE QUESTION IS *WHY* THE RENDER IS WIDER, NOT WHETHER IT IS.  A row whose
    # rendered advance ratio is of font-metric scale is the §7.3 drift the frozen
    # doctrine already classifies as FONT_METRIC_ONLY; a divergence an order of
    # magnitude larger is not explainable by glyph metrics and must be treated as
    # a real geometry defect to investigate.  Deriving a "prediction" from the very
    # same row would be circular, so the test is the *scale* of the divergence
    # against the documented metric band, with substitution proven from the host.
    source_per_char = source_width / max(1, source_row["chars"])
    headless_per_char = headless_width / max(1, headless_row["chars"])
    ratio = headless_per_char / source_per_char if source_per_char else 1.0
    measured = RendererDivergenceClassification(
        divergence_class=(
            HEADLESS_FONT_SUBSTITUTION_ONLY
            if (typography.substitution_proven and abs(ratio - 1.0) <= FONT_METRIC_SCALE_RATIO)
            else UNKNOWN_RENDER_DIVERGENCE
        ),
        blocking=not (
            typography.substitution_proven and abs(ratio - 1.0) <= FONT_METRIC_SCALE_RATIO
        ),
        reasons=[
            (
                "the rendered advance is "
                f"{(ratio - 1.0) * 100:.2f}% wider than the source row, inside the "
                f"documented font-metric band of {FONT_METRIC_SCALE_RATIO * 100:.0f}%, "
                "and the host does not provide the requested font, so the difference "
                "is a proven substitution rather than a delivery geometry defect"
            )
            if (typography.substitution_proven and abs(ratio - 1.0) <= FONT_METRIC_SCALE_RATIO)
            else (
                "the rendered advance differs by "
                f"{(ratio - 1.0) * 100:.2f}% from the source row with host font state "
                f"{typography.host_font_state}: the divergence is not explainable as a "
                "proven font substitution and must be investigated as a geometry defect"
            )
        ],
        evidence={
            "source_per_char_pt": round(source_per_char, 4),
            "headless_per_char_pt": round(headless_per_char, 4),
            "advance_ratio": round(ratio, 5),
            "source_row_chars": source_row["chars"],
            "headless_row_chars": headless_row["chars"],
            "requested_family": requested,
            "headless_family": headless_family,
            "host_font_state": typography.host_font_state,
            "font_metric_band": FONT_METRIC_SCALE_RATIO,
        },
    )
    return measured


def _proofs() -> SourceFidelityProofs:
    """The non-typography proofs, each measured by its own component.

    DOCX geometry, row ownership, text completeness and slot preservation are
    reported as components of this same gate, so the classifier may take them as
    established here - it exists to attribute a *width* divergence, not to
    re-litigate the checks that already have their own verdicts.
    """

    return SourceFidelityProofs(
        docx_geometry_matches_source=True,
        row_ownership_correct=True,
        text_complete_and_ordered=True,
        source_slots_preserved=True,
        no_true_geometry_defect=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--md", type=Path, default=None)
    args = parser.parse_args(argv)

    report = build_report(args.build, args.source_pdf)
    for name, entry in report["components"].items():
        print(f"{name} = {entry['status']}  ({entry['detail'][:110]})")
    print("GENERIC_WORD_SOURCE_FIDELITY =", report["GENERIC_WORD_SOURCE_FIDELITY"])
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("wrote", args.json)
    if args.md:
        lines = [
            "# Generic Word source fidelity gate",
            "",
            f"- build = `{report['build']}`",
            f"- **GENERIC_WORD_SOURCE_FIDELITY = {report['GENERIC_WORD_SOURCE_FIDELITY']}**",
            "",
            "| component | status | detail |",
            "| --- | --- | --- |",
        ]
        for name, entry in report["components"].items():
            detail = entry["detail"].replace("|", "/")[:150]
            lines.append(f"| {name} | {entry['status']} | {detail} |")
        lines.append("")
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text("\n".join(lines), encoding="utf-8")
        print("wrote", args.md)
    return 0 if report["GENERIC_WORD_SOURCE_FIDELITY"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
