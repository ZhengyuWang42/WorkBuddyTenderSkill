"""Round-3 source typography gate: the source's own typography, delivered.

The manual Word review of the Round-2/P21 build found eight defects that are all
one thing: typography the *source* carries and the delivery does not.  This gate
measures that contract directly, from the source PDF's own model and the
delivered document, and it names each family it checks:

``HARD_BREAK_FIDELITY``
    A delivered ``w:br`` must be a *source* line break.  A source element whose
    rows all lie in one source visual row must be delivered as one row; a break
    inside it is text the builder invented.

    One further case exists and is reported separately rather than hidden: a
    source *natural wrap* the delivery had to express as a Word paragraph
    boundary because the frozen source geometry of that row cannot otherwise be
    held.  Such a boundary is admissible **only** when it satisfies the
    :data:`STRUCTURAL_DEVIATION_CONDITIONS` contract below, and even then it is
    reported as a reviewed deviation - never as container fidelity, and never as
    a source break.  The family's status becomes
    ``PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION``, which is not ``PASS``.

``PARAGRAPH_ALIGNMENT``
    A paragraph is justified only when the source's own wrapped rows show the
    glyph advance a justified line stretches to.  Every other paragraph keeps the
    source's plain left alignment.

``TABLE_CELL_LINE_STRUCTURE``
    A cell whose source text spans several source visual rows keeps exactly those
    rows: one break between consecutive rows, and no row merged into another.

``SOURCE_BOLD_FIDELITY``
    Text the source drew in bold is delivered bold.

``SOURCE_UNDERLINE_FIDELITY``
    A rule the source drew *under its own glyphs* is delivered as an underline on
    exactly those glyphs.

``FIXED_BLANK_FIDELITY``
    A rule the source drew through clear space is delivered as a blank at the
    rule's own measured span, and the delivered render paints that span.

Nothing here is keyed to a case name, a page number, a rule id or a reported
string: every check iterates the source model and the delivered document, and
the geometry follows from the source itself.  Usage::

    .venv/Scripts/python.exe scripts/v1_source_typography_round3_gate.py \
        --build acceptance/workspace/case_001/<build> \
        --source-pdf acceptance/private/<file>.pdf \
        --out acceptance/reports/v1_generalization/case001_source_typography_round3.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import docx  # noqa: E402
import pymupdf  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from v1_manual_review_p21_diagnostic import _source_rules  # noqa: E402

from tender_basic.geometry_rule_qa import page_rules  # noqa: E402
from tender_basic.page_layout import (  # noqa: E402
    RULE_TEXT_OCCUPANCY_GAP,
    RULE_TEXT_OCCUPANCY_UNDERLINE,
    rule_text_occupancy,
    source_visual_rows,
)

SCHEMA = "v1_source_typography_round3_gate/1"

#: A delivered blank may differ from the source rule's span by this much.
SPAN_TOLERANCE_PT = 1.5
#: Shortest source run whose boldness is worth joining to the delivery: shorter
#: text collides with unrelated occurrences and would measure the join, not the
#: typography.
MIN_JOIN_CHARS = 4
#: A painted rule's width may differ from the source span by a glyph's rounding:
#: a blank painted by repeated figure spaces lands within a space of the span.
PAINTED_WIDTH_TOLERANCE_PT = 3.0
#: ... and on a long blank a single figure space of error is proportional, so
#: the band is the wider of the two.  A rule painted at a *different* width -
#: a lost blank, or one painted over the wrong span - stays outside it.
PAINTED_WIDTH_RATIO = 0.12
#: A painted rule is matched to the source row it decorates within this band.
RULE_LINE_TOLERANCE_PT = 8.0
#: A rule that stands on a wrapped row of one Word paragraph has no line origin
#: of its own: the flow decides where it starts, so only one of its two source
#: endpoints can be held.  This is the band that endpoint must land in.
FLOW_PLACED_ENDPOINT_TOLERANCE_PT = 2.0
#: ... and the rule the delivery paints must still be recognisable as that rule:
#: a leader tab carries the anchored endpoint, so the painted span may be
#: shorter than the source's, but not a fraction of it and not many times it.
FLOW_PLACED_MIN_WIDTH_RATIO = 0.3
FLOW_PLACED_MAX_WIDTH_RATIO = 2.0
#: Policies whose executed representation is a resolved value the owner anchors at
#: the rule's own source x0.  Such a rule is measured as a value run (the frozen
#: closure gate and the underline inventory both do that) and is not a blank the
#: flow places, so the flow-placed endpoint diagnostic excludes it by contract.
VALUE_INSERTING_POLICIES = frozenset(
    {"RESOLVED_VALUE_IN_FIXED_SLOT", "PLACEHOLDER_REPLACED_BY_VALUE"}
)
#: ``w:jc`` values that carry the source's justified body alignment.
JUSTIFIED_VALUES = frozenset({"both", "justify", "distribute"})
#: A source element is "split" only when its neighbours reconstruct most of it.
SPLIT_COVERAGE_RATIO = 0.8
#: The delivered contents region is emitted under the builder's own contents
#: styles; its entries are navigational, not body typography, so the body
#: boldness check does not join them.
CONTENTS_STYLE_PREFIX = "Tender TOC"
VISIBLE_UNDERLINES = frozenset(
    {
        "single", "words", "double", "thick", "dotted", "dottedheavy", "dash",
        "dashedheavy", "dotdash", "dotdashheavy", "dotdotdash", "dotdotdashheavy",
        "wave", "wavyheavy", "wavydouble",
    }
)


def _compact(text) -> str:
    """Visible characters only: the join key between source and delivery."""

    return "".join(str(text or "").split())


# --------------------------------------------------------------------------- #
# delivered side
# --------------------------------------------------------------------------- #


def _run_record(run) -> dict:
    return {
        "text": run.text,
        "bold": _run_is_bold(run),
        "underline": _run_underline_value(run),
    }


def _paragraph_record(paragraph) -> dict:
    style_paragraph_format = None
    try:
        if paragraph.style is not None:
            style_paragraph_format = paragraph.style.paragraph_format
    except (AttributeError, KeyError):
        style_paragraph_format = None

    def _spacing(attribute):
        direct = getattr(paragraph.paragraph_format, attribute, None)
        if direct is not None:
            return float(direct.pt)
        if style_paragraph_format is not None:
            inherited = getattr(style_paragraph_format, attribute, None)
            if inherited is not None:
                return float(inherited.pt)
        return 0.0

    return {
        "text": paragraph.text,
        "style": None if paragraph.style is None else paragraph.style.name,
        "justified": _paragraph_is_justified(paragraph),
        # The horizontal alignment the delivered cell paragraph actually carries.
        "jc": (
            None
            if paragraph._p.find(qn("w:pPr") + "/" + qn("w:jc")) is None
            else str(
                paragraph._p.find(qn("w:pPr") + "/" + qn("w:jc")).get(qn("w:val"))
            )
        ),
        "breaks": len(paragraph._p.findall(".//" + qn("w:br"))),
        # ``w:cr`` is a second, older way Word spells a hard line break; a
        # hard-break check that only counts ``w:br`` would miss it.
        "cr": len(paragraph._p.findall(".//" + qn("w:cr"))),
        "compact": _compact(paragraph.text),
        "space_before_pt": _spacing("space_before"),
        "space_after_pt": _spacing("space_after"),
        "runs": [_run_record(run) for run in paragraph.runs],
    }


def _delivered_paragraphs(build_dir: Path) -> list[dict]:
    document = docx.Document(str(build_dir / "基础投标文件.docx"))
    records = [_paragraph_record(paragraph) for paragraph in document.paragraphs]
    for index, record in enumerate(records):
        record["index"] = index
    return records


def _delivered_cells(build_dir: Path) -> list[dict]:
    """Every delivered table cell with its own paragraphs, runs and breaks."""

    document = docx.Document(str(build_dir / "基础投标文件.docx"))
    cells = []
    for table_index, table in enumerate(document.tables):
        for row_index, row in enumerate(table.rows):
            for column_index, cell in enumerate(row.cells):
                paragraphs = [
                    _paragraph_record(paragraph) for paragraph in cell.paragraphs
                ]
                text = "\n".join(paragraph["text"] for paragraph in paragraphs)
                cells.append(
                    {
                        "table_index": table_index,
                        "row_index": row_index,
                        "column_index": column_index,
                        "paragraphs": paragraphs,
                        "text": text,
                        "compact": _compact(text),
                        "breaks": sum(
                            paragraph["breaks"] for paragraph in paragraphs
                        ),
                        "runs": [
                            run
                            for paragraph in paragraphs
                            for run in paragraph["runs"]
                        ],
                    }
                )
    return cells


def _paragraph_is_justified(paragraph) -> bool:
    element = paragraph._p.find(qn("w:pPr") + "/" + qn("w:jc"))
    if element is None:
        return False
    return str(element.get(qn("w:val")) or "").lower() in JUSTIFIED_VALUES


def _run_is_bold(run) -> bool:
    if run.bold is not None:
        return bool(run.bold)
    return run._r.find(qn("w:rPr") + "/" + qn("w:b")) is not None


def _run_underline_value(run) -> str | None:
    element = run._r.find(qn("w:rPr") + "/" + qn("w:u"))
    if element is None:
        return None
    return str(element.get(qn("w:val")) or "single")


def _visible_underline(value) -> bool:
    return value is not None and str(value).lower() in VISIBLE_UNDERLINES


# --------------------------------------------------------------------------- #
# source side
# --------------------------------------------------------------------------- #


def _source_model(source_pdf: Path):
    from tender_basic.bid_document_builder import build_repaired_source_model
    from tender_basic.document_parser import parse_document
    from tender_basic.format_extractor import extract_bid_format

    document = parse_document(source_pdf)
    template = extract_bid_format(document)
    model, _qa = build_repaired_source_model(document, template)
    return model


def _element_runs(element) -> list:
    """The source spans of a reconstructed paragraph, in reading order."""

    runs = []
    for line in element.source_lines:
        runs.extend(line.spans)
    return runs


def _element_record(page, element) -> dict:
    rows = source_visual_rows(element.source_lines)
    alignment = getattr(element, "source_alignment", None)
    runs = _element_runs(element)
    return {
        "source_page": page.page,
        "kind": type(element).__name__,
        "text": element.logical_text,
        "compact": _compact(element.logical_text),
        "row_count": len(rows),
        "row_texts": [
            _compact("".join(span.text for line in row for span in line.spans))
            for row in rows
        ],
        "justified": bool(getattr(alignment, "justified", False)),
        "glyph_advance_ratio": _advance_ratio(rows),
        "runs": [
            {
                "text": run.text,
                "compact": _compact(run.text),
                "bold": bool(run.bold),
                "characters": run.characters,
                "bbox": [round(float(value), 2) for value in run.bbox],
            }
            for run in runs
        ],
    }


def _source_elements(model) -> list[dict]:
    """Every source layout element that is delivered as a paragraph."""

    from tender_basic.page_layout import build_page_layout

    elements = []
    for page in model.source_pages:
        layout = build_page_layout(page)
        for element in layout.elements:
            if type(element).__name__ not in ("LogicalParagraph", "List"):
                continue
            elements.append(_element_record(page, element))
    return elements


def _advance_ratio(rows) -> float | None:
    """The widest glyph-advance stretch the source's own wrapped rows show."""

    from tender_basic.source_paragraph_alignment import row_glyph_advance_ratio

    wrapped = rows[:-1] or rows
    ratios = [
        ratio
        for ratio in (row_glyph_advance_ratio(row) for row in wrapped)
        if ratio
    ]
    return round(max(ratios), 4) if ratios else None


def _source_cells(model) -> list[dict]:
    cells = []
    seen = set()
    for page in model.source_pages:
        for table in page.tables:
            for row in table.rows:
                for cell in row.cells:
                    rows = source_visual_rows(cell.runs)
                    bbox = tuple(float(value) for value in (cell.bbox or ())) if cell.bbox else None
                    key = (page.page, _compact(cell.text), bbox)
                    if key in seen:
                        # A merged cell is reported once per row it spans.
                        continue
                    seen.add(key)
                    cells.append(
                        {
                            "source_page": page.page,
                            "text": cell.text,
                            "compact": _compact(cell.text),
                            "bbox": bbox,
                            "row_count": len(rows),
                            "row_texts": [
                                _compact("".join(run.text for run in source_row))
                                for source_row in rows
                            ],
                            "rows": [
                                {
                                    "text": _compact(
                                        "".join(run.text for run in source_row)
                                    ),
                                    "right": max(
                                        float(run.bbox[2]) for run in source_row
                                    ),
                                    "size": max(
                                        float(run.font_size or 0.0)
                                        for run in source_row
                                    ),
                                }
                                for source_row in rows
                            ],
                            "runs": [
                                {
                                    "text": run.text,
                                    "compact": _compact(run.text),
                                    "bold": bool(run.bold),
                                    "bbox": [
                                        round(float(value), 2) for value in run.bbox
                                    ],
                                }
                                for run in cell.runs
                            ],
                        }
                    )
    return cells


def _source_page_runs(model) -> dict[int, list]:
    """Every source run on each page, for the rule-occupancy classification."""

    runs: dict[int, list] = {}
    for page in model.source_pages:
        collected = []
        for paragraph in getattr(page, "paragraphs", ()):
            for line in getattr(paragraph, "lines", ()):
                collected.extend(line.spans)
        for table in getattr(page, "tables", ()):
            for row in table.rows:
                for cell in row.cells:
                    collected.extend(cell.runs)
        runs[page.page] = collected
    return runs


# --------------------------------------------------------------------------- #
# joins
# --------------------------------------------------------------------------- #


def _match(entry: dict, candidates: list[dict]) -> dict | None:
    """The delivered container a source element's own text was emitted into.

    The join is the source's visible characters: they survive into the delivery
    (a filled slot replaces characters, and the join simply does not find those),
    so containment identifies the delivery without any case-specific key.  The
    smallest containing delivered text wins, which keeps a short source element
    from matching a longer paragraph that merely contains its words.
    """

    key = entry["compact"]
    if len(key) < 3:
        return None
    best = None
    for candidate in candidates:
        if key in candidate["compact"]:
            if best is None or len(candidate["compact"]) < len(best["compact"]):
                best = candidate
    return best


def _coverage(runs, text: str, field: str) -> list:
    """One field of the delivered runs that cover ``text``, per character."""

    values = []
    cursor = 0
    for run in runs:
        key = _compact(run.get("text"))
        if not key:
            continue
        at = text.find(key, cursor)
        if at < 0:
            continue
        values.extend([run.get(field)] * len(key))
        cursor = at + len(key)
    return values


# --------------------------------------------------------------------------- #
# character geometry
# --------------------------------------------------------------------------- #


def _character_offsets(run) -> list[int]:
    """Each recorded source character's own offset inside the run's text."""

    characters = list(_run_characters(run))
    text = str(_run_text(run) or "")
    if not characters or not text:
        return []
    offsets = []
    cursor = 0
    for char in characters:
        glyph = str(getattr(char, "character", "") or "")
        if not glyph:
            return []
        at = text.find(glyph, cursor)
        if at < 0:
            return []
        offsets.append(at)
        cursor = at + len(glyph)
    return offsets


def _char_box(char) -> tuple[float, float]:
    """A source character's own left/right edges, whichever model carries it."""

    if hasattr(char, "x0"):
        return float(char.x0), float(char.x1)
    bbox = getattr(char, "bbox")
    return float(bbox[0]), float(bbox[2])


def _majority_overlap(char, x0, x1) -> bool:
    left, right = _char_box(char)
    width = right - left
    if width <= 0:
        return False
    return (min(right, x1) - max(left, x0)) >= width / 2.0


def _covered_text(run, x0, x1) -> str:
    """The run's own characters a rule drawn from ``x0`` to ``x1`` covers."""

    characters = list(_run_characters(run))
    offsets = _character_offsets(run)
    text = str(_run_text(run) or "")
    if characters and offsets:
        return _compact(
            "".join(
                str(getattr(char, "character", ""))
                for char, _offset in zip(characters, offsets)
                if _majority_overlap(char, x0, x1)
            )
        )
    run_x0, _y0, run_x1, _y1 = (float(value) for value in _run_bbox(run))
    if run_x1 <= run_x0 or not text:
        return ""
    start = max(0.0, min(1.0, (x0 - run_x0) / (run_x1 - run_x0)))
    end = max(0.0, min(1.0, (x1 - run_x0) / (run_x1 - run_x0)))
    return _compact(text[round(start * len(text)):round(end * len(text))])


def _run_text(run) -> str:
    return run["text"] if isinstance(run, dict) else str(getattr(run, "text", "") or "")


def _run_bbox(run):
    return run["bbox"] if isinstance(run, dict) else run.bbox


def _run_characters(run):
    if isinstance(run, dict):
        return run.get("characters") or ()
    return getattr(run, "characters", ()) or ()


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #


#: How a delivered paragraph boundary inside one source element is classified.
#: The classification is read from the source's own structure and from the
#: delivered OOXML, never from the build's own claim about itself.
NATURAL_WRAP = "NATURAL_WRAP"
SOURCE_EXPLICIT_BREAK = "SOURCE_EXPLICIT_BREAK"
BUILDER_FORCED_BREAK = "BUILDER_FORCED_BREAK"
STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW = (
    "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW"
)

#: Classifications that may legally separate one source element's own text.
AUTHORISED_CLASSIFICATIONS = frozenset({SOURCE_EXPLICIT_BREAK})


def _classify_split(element, piece_index: int) -> tuple[str, str]:
    """Why one delivered paragraph boundary inside a source element exists.

    The source's own structure answers this, in the authority order the project
    already uses:

    ``SOURCE_EXPLICIT_BREAK``
        The element is a source list whose items the source itself printed as
        separate paragraphs/steps.  The boundary is the source's own.

    ``NATURAL_WRAP``
        The element is ONE source logical paragraph that the source printed as
        several wrapped visual rows.  The source never broke a line there, so a
        delivered paragraph boundary at that point is not a wrap - it is an
        invented break inside one continuous sentence, whatever reason the build
        recorded for it.

    ``BUILDER_FORCED_BREAK``
        The element is a single source visual row, so the source has no internal
        boundary at all and the builder created one.

    ``STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW``
        As ``BUILDER_FORCED_BREAK``, but the build's own record states that the
        resolved value's reflow made the row's frozen source anchors unreachable
        in continuous flow.  A proven necessity, and still not a source break.
    """

    if str(element.get("kind")) == "List":
        return (
            SOURCE_EXPLICIT_BREAK,
            "the source element is a list whose own items are separate source rows",
        )
    if int(element.get("row_count") or 1) > 1:
        return (
            NATURAL_WRAP,
            "one source logical paragraph printed as %d wrapped visual rows"
            % int(element["row_count"]),
        )
    return (
        BUILDER_FORCED_BREAK,
        "the source element is a single visual row with no internal boundary",
    )


def _authorized_isolation_paragraphs(build_dir: Path) -> dict:
    """Paragraphs the build itself isolated to hold the frozen rule geometry.

    A source element delivered as several paragraphs is only admissible when the
    build states why, and the authorised reason is the one the frozen horizontal
    contract requires: the row's own source anchors are unreachable in continuous
    flow, so the row gets its own paragraph context with zero before/after
    spacing and no ``<w:br/>``.  The record is the build's own statement, read by
    the generated paragraph index it names.

    A recorded reason is *evidence about the build*, not a verdict: the
    hard-break check still classifies the boundary from the source's own
    structure, so a recorded isolation can never authorise a break the source
    itself printed as a wrap.
    """

    report_path = build_dir / "generation_report.json"
    if not report_path.exists():
        return {}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    authorized = {}
    for key in ("structural_isolation_rows", "source_form_line_paragraphs"):
        for record in report.get(key) or []:
            index = record.get("generated_paragraph_index")
            if index is None:
                continue
            reason = str(
                record.get("isolation_reason")
                or record.get("reason")
                or ""
            )
            if "STRUCTURAL_ISOLATION" not in reason:
                continue
            authorized[int(index)] = {
                "reason": reason,
                "space_before_pt": record.get("space_before_pt"),
                "space_after_pt": record.get("space_after_pt"),
                "source_rule_ids": record.get("source_rule_ids"),
            }
    return authorized


def _hard_break_fidelity(elements, delivered, values=(), isolated=None, artifacts=None):
    """One source element reaches the reader without an invented hard break.

    The contract is what the reader sees, never the paragraph count.  The
    source's own wrapping is not a line break, so an element that owns several
    visual rows may legitimately arrive as one paragraph that wraps; and when the
    frozen horizontal contract requires a row's own line geometry, the build may
    isolate that row in its own paragraph (zero before/after spacing, no
    ``<w:br/>``) - the authority order puts the rule's source geometry above Word
    paragraph continuity.  What may never happen is an *unstated* split, a
    ``<w:br/>`` inside the element's own prose, an empty paragraph between the
    fragments, or a fragment that carries paragraph spacing a reader would see.

    A split that is *stated* and independently evidenced is not thereby a
    success.  It is reported as a **reviewed structural deviation**: the source
    semantics and the generated representation are kept apart, the fidelity
    difference is named, and the boundary moves from
    ``unexplained_structural_splits`` into ``reviewed_structural_deviations``
    without ever being called container fidelity.  ``artifacts`` carries the
    deviation evidence; when it is absent or incomplete the boundary stays an
    unexplained split and the family fails.
    """

    isolated = isolated or {}
    evidence = _structural_deviation_evidence() if artifacts is None else artifacts
    admissible, evidence_problems = _admissible_deviation_artifact(
        evidence, source_semantics=NATURAL_WRAP_SEMANTICS
    )
    failures = []
    reviewed_deviations = []
    checked = 0
    authorized_splits = 0
    classifications: dict[str, int] = {}
    # Paragraphs whose breaks the source's own row structure accounts for.
    row_break_paragraphs: dict[int, int] = {}
    accounting = {key: 0 for key in HARD_BREAK_ACCOUNTING_KEYS}
    accounting["generated_w_br"] = sum(
        int(paragraph.get("breaks") or 0) for paragraph in delivered
    )
    accounting["generated_w_cr"] = sum(
        int(paragraph.get("cr") or 0) for paragraph in delivered
    )
    delivered_text = "".join(paragraph["compact"] for paragraph in delivered)
    for element in elements:
        key = _literal_key(element["compact"], delivered_text)
        if len(key) < MIN_JOIN_CHARS:
            continue
        checked += 1
        pieces = _split_pieces(key, delivered, values)
        covered = sum(len(piece["literal"]) for piece in pieces)
        if len(pieces) > 1 and covered >= SPLIT_COVERAGE_RATIO * len(key):
            indexes = [int(piece["index"]) for piece in pieces]
            first, last = min(indexes), max(indexes)
            accounting["generated_paragraph_boundaries"] += len(pieces) - 1
            blank_between = [
                paragraph["index"]
                for paragraph in delivered
                if first < paragraph["index"] < last and not paragraph["compact"]
            ]
            breaks_inside = [
                {
                    "generated_paragraph_index": piece["index"],
                    "breaks": piece["breaks"],
                }
                for piece in pieces
                if piece["breaks"]
            ]
            spacing = [
                {
                    "generated_paragraph_index": piece["index"],
                    "space_before_pt": piece.get("space_before_pt") or 0.0,
                    "space_after_pt": piece.get("space_after_pt") or 0.0,
                }
                for piece in pieces[1:]
                if (piece.get("space_before_pt") or 0.0)
                or (piece.get("space_after_pt") or 0.0)
            ]
            unauthorized = [
                piece["index"]
                for piece in pieces[1:]
                if int(piece["index"]) not in isolated
            ]
            classification, classification_reason = _classify_split(
                element, max(indexes)
            )
            classifications[classification] = classifications.get(classification, 0) + 1
            if classification == SOURCE_EXPLICIT_BREAK:
                accounting["source_explicit_breaks"] += 1
            elif classification == NATURAL_WRAP_SEMANTICS:
                accounting["source_natural_wrap_boundaries"] += 1
            elif classification == BUILDER_FORCED_BREAK:
                accounting["builder_forced_breaks"] += 1
            if breaks_inside:
                failures.append(
                    {
                        "kind": "BUILDER_HARD_BREAK_INSIDE_ELEMENT",
                        "source_page": element["source_page"],
                        "text": key[:60],
                        "paragraphs": breaks_inside,
                    }
                )
            elif blank_between:
                failures.append(
                    {
                        "kind": "SPLIT_INTRODUCES_VISIBLE_GAP",
                        "source_page": element["source_page"],
                        "text": key[:60],
                        "empty_paragraph_indexes": blank_between,
                    }
                )
            elif spacing:
                failures.append(
                    {
                        "kind": "SPLIT_INTRODUCES_PARAGRAPH_SPACING",
                        "source_page": element["source_page"],
                        "text": key[:60],
                        "paragraphs": spacing,
                    }
                )
            elif classification in AUTHORISED_CLASSIFICATIONS:
                # The source itself printed this boundary, so the delivered
                # paragraphs follow the source's own structure.
                authorized_splits += 1
            else:
                # TEXT-FLOW CONTINUITY.  The source printed one continuous
                # sentence here; a delivered paragraph boundary at this point is
                # an invented break even when the build recorded a structural
                # isolation for it, because that record states what the builder
                # needed, not what the source did.  The reader-visible evidence
                # is stated field by field so the classification is auditable.
                #
                # The boundary is only *reviewed and accepted* when the separate
                # deviation contract is fully evidenced; otherwise it stays an
                # unexplained split and the family fails.
                isolation_record = isolated.get(int(pieces[-1]["index"]))
                deviation = _deviation_condition_report(
                    element=element,
                    element_key=key,
                    classification=classification,
                    classification_reason=classification_reason,
                    pieces=pieces,
                    breaks_inside=breaks_inside,
                    blank_between=blank_between,
                    spacing=spacing,
                    isolation_record=isolation_record,
                    artifact=admissible,
                    delivered=delivered,
                )
                entry = {
                    "kind": "SOURCE_ELEMENT_SPLIT_ACROSS_PARAGRAPHS",
                    "source_page": element["source_page"],
                    "source_element_kind": element.get("kind"),
                    "source_row_count": element["row_count"],
                    "source_row_texts": element.get("row_texts"),
                    "delivered_paragraphs": len(pieces),
                    "unauthorized_paragraph_indexes": unauthorized,
                    "classification": classification,
                    "classification_reason": classification_reason,
                    # The source semantics and the generated representation are
                    # separate fields on purpose: nothing here may collapse them
                    # into one PASS/FAIL string.
                    "source_semantics": classification,
                    "generated_representation": PARAGRAPH_BOUNDARY_REPRESENTATION,
                    "container_fidelity": deviation["container_fidelity"],
                    "fidelity_difference": deviation["fidelity_difference"],
                    "deviation_kind": deviation["deviation_kind"],
                    "deviation_state": deviation["deviation_state"],
                    "deviation_conditions": deviation["conditions"],
                    "deviation_missing_conditions": deviation["missing_conditions"],
                    "deviation_evidence_path": (admissible or {}).get("evidence_path"),
                    "deviation_evidence_problems": evidence_problems,
                    "same_word_paragraph": False,
                    "generated_paragraph_boundary": True,
                    "w_br_between_tokens": len(breaks_inside),
                    "w_cr_between_tokens": sum(
                        int(piece.get("cr") or 0) for piece in pieces
                    ),
                    "empty_paragraph_between_tokens": len(blank_between),
                    "authorised_structural_split_between_tokens": False,
                    "recorded_isolation_reason": (
                        (isolation_record or {}).get("reason")
                    ),
                    "text": key[:60],
                }
                if deviation["deviation_state"] == DEVIATION_STATE_REVIEWED_ACCEPTED:
                    # Disclosed, counted, and moved out of the failure list - but
                    # still not called fidelity.  The human review item stays open.
                    entry["unexplained_structural_split"] = False
                    entry["reviewed_structural_deviation"] = True
                    accounting["reviewed_structural_deviations"] += 1
                    reviewed_deviations.append(entry)
                else:
                    entry["unexplained_structural_split"] = True
                    entry["reviewed_structural_deviation"] = False
                    accounting["unexplained_structural_splits"] += 1
                    failures.append(entry)
            continue
        match = _match(element, delivered)
        if match is None:
            continue
        # A delivered paragraph the gate matched to this source element carries
        # the element's own rows, so its breaks are the source's row separation
        # rather than an invention - but only up to the number of rows the
        # element's own text has.  Anything beyond that is disclosed separately.
        if int(element.get("row_count") or 1) > 1:
            existing = row_break_paragraphs.get(int(match["index"]), 0)
            row_break_paragraphs[int(match["index"])] = max(
                existing, int(element["row_count"])
            )
        if match["breaks"] > element["row_count"]:
            failures.append(
                {
                    "kind": "DELIVERED_BREAKS_EXCEED_SOURCE_ROWS",
                    "source_page": element["source_page"],
                    "source_row_count": element["row_count"],
                    "delivered_breaks": match["breaks"],
                    "text": key[:60],
                }
            )
    accounting.update(
        _hard_break_accounting(delivered, isolated, row_break_paragraphs)
    )
    return {
        "checked": checked,
        "split": 0,
        "authorized_splits": authorized_splits,
        "authorized_classifications": sorted(AUTHORISED_CLASSIFICATIONS),
        "split_classifications": classifications,
        "isolated_paragraphs": sorted(isolated),
        "accounting": accounting,
        "reviewed_deviations": reviewed_deviations,
        "hard_break_disclosure": _break_disclosure(
            delivered, isolated, row_break_paragraphs
        ),
        "note": (
            "a recorded structural isolation is evidence about the build, not a "
            "verdict: only a boundary the SOURCE itself printed is an authorised "
            "split.  A split of one source logical paragraph's wrapped rows is "
            "reported as NATURAL_WRAP; it is a reviewed structural deviation only "
            "when the separate deviation contract is fully evidenced, and it is "
            "never reported as container fidelity"
        ),
    }, failures


# --------------------------------------------------------------------------- #
# Reviewed structural deviation (the frozen-geometry case)
# --------------------------------------------------------------------------- #
#
# An accepted deviation is a *fidelity difference*, never a fidelity success: the
# source says one thing and the container says another.  It may only be recorded
# when the difference is forced by a contract that already existed before the
# difference was introduced, and is covered by independent, re-derivable
# evidence - never by the build's own claim about itself.
#
# Nothing below is keyed to a case name, a page number, a rule id, a build id or
# a literal.  Evidence is discovered by walking a declared evidence root and is
# matched to a delivered boundary by what Word itself defines: the paragraph
# *after* the boundary, plus the reason the build recorded for that paragraph.

#: How a generated container can fail to match the source's own semantics.
NATURAL_WRAP_SEMANTICS = NATURAL_WRAP
PARAGRAPH_BOUNDARY_REPRESENTATION = "PARAGRAPH_BOUNDARY"
SOURCE_CONTAINER_MISMATCH = "SOURCE_CONTAINER_MISMATCH"
FIDELITY_DIFFERENCE_CONTAINER = "CONTAINER_IDENTITY"
#: The only accepted cause of a paragraph-boundary deviation: the row's own
#: frozen source geometry outranks the generated container's identity.
STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY = (
    "STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY"
)
DEVIATION_STATE_REVIEWED_ACCEPTED = "REVIEWED_ACCEPTED"
DEVIATION_STATE_NONE = "NONE"
#: The pass-with-disclosure status the family reports when every deviation on a
#: build is reviewed and accepted.  It is deliberately not ``PASS``.
PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION = "PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION"
#: The cause a build must record for a boundary to be treated as the reviewed
#: frozen-geometry deviation rather than as an unexplained split.
FROZEN_GEOMETRY_RECORDED_REASONS = (
    STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY,
    "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW",
)

#: The review state an artifact must declare before its deviation may be admitted.
#: The deviation is accepted by **project policy** - a human decision recorded in
#: the artifact - never by the check that reads it.
DEVIATION_REVIEW_STATE_ACCEPTED_BY_PROJECT_POLICY = "ACCEPTED_BY_PROJECT_POLICY"
DEVIATION_REVIEW_AUTHORITY_PROJECT_POLICY = "PROJECT_POLICY"

#: Where independently re-derivable deviation evidence lives.  The gate walks
#: this root and reads every ``*.json`` carrying a
#: ``structural_deviation_evidence/*`` schema; a build with no such evidence can
#: never have a deviation accepted.
STRUCTURAL_DEVIATION_EVIDENCE_DIRS = (
    Path("acceptance/evidence/structural_deviations"),
)
STRUCTURAL_DEVIATION_EVIDENCE_SCHEMA_PREFIX = "structural_deviation_evidence/"

#: The conditions an accepted structural paragraph deviation must satisfy.  Every
#: one is evaluated below; a missing one leaves the boundary an unexplained
#: split, which fails.
STRUCTURAL_DEVIATION_CONDITIONS = (
    "source_evidence_proves_one_logical_paragraph",
    "source_boundary_classification_is_natural_wrap",
    "generated_structure_is_a_native_paragraph_boundary",
    "generated_boundary_has_no_w_br_no_w_cr_no_empty_paragraph",
    "generated_boundary_spacing_is_zero_or_source_equivalent",
    "no_visible_blank_row_is_introduced",
    "reading_order_is_unchanged",
    "text_content_is_unchanged",
    "split_occurs_at_a_source_visual_row_transition",
    "same_w_p_rendering_experimentally_tested",
    "experiment_fails_an_independently_frozen_source_geometry_contract",
    "the_violated_geometry_contract_predates_the_deviation",
    "no_permitted_native_inline_construct_satisfies_both",
    "preserving_geometry_requires_no_tolerance_weakening",
    "no_source_geometry_rebaseline_is_performed",
    "deviation_is_surfaced_explicitly",
    "a_human_review_item_remains_open",
)

#: The accounting keys the hard-break family reports, so the difference between
#: a source break, an unauthorised split and a reviewed deviation is never
#: collapsed into one number.
HARD_BREAK_ACCOUNTING_KEYS = (
    "source_natural_wrap_boundaries",
    "source_explicit_breaks",
    "generated_w_br",
    "generated_w_cr",
    "generated_paragraph_boundaries",
    "unexplained_structural_splits",
    "reviewed_structural_deviations",
    "builder_forced_breaks",
)


def _sha256_of_json(payload) -> str:
    """A stable digest of an evidence payload, so it cannot be edited in place."""

    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _contract_rules_digest(rules) -> str:
    """The digest that pins a frozen source-geometry contract."""

    normalized = [
        {
            "source_rule_id": str(rule.get("source_rule_id")),
            "transformation_policy": str(rule.get("transformation_policy")),
            "geometry_intent": str(rule.get("geometry_intent")),
            "source_x0": round(float(rule.get("source_x0")), 4),
            "source_x1": round(float(rule.get("source_x1")), 4),
            "source_y": round(float(rule.get("source_y")), 4),
        }
        for rule in rules
    ]
    normalized.sort(key=lambda rule: rule["source_rule_id"])
    return _sha256_of_json(normalized)


def _structural_deviation_evidence(root: Path | None = None) -> list[dict]:
    """Every declared structural-deviation evidence artifact under the root.

    The gate never invents evidence and never accepts the build's own record as
    proof: it reads artifacts that state, in their own right, that a merged
    representation was *measured* to fail a contract frozen before the deviation
    existed.  A malformed artifact is dropped rather than trusted.
    """

    root = ROOT if root is None else root
    found: list[dict] = []
    for relative in STRUCTURAL_DEVIATION_EVIDENCE_DIRS:
        directory = root / relative
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            schema = str(payload.get("schema") or "")
            if not schema.startswith(STRUCTURAL_DEVIATION_EVIDENCE_SCHEMA_PREFIX):
                continue
            payload = dict(payload)
            payload["evidence_path"] = str(path.relative_to(root)).replace("\\", "/")
            found.append(payload)
    return found


def _admissible_deviation_artifact(
    evidence: list[dict],
    *,
    source_semantics: str,
) -> tuple[dict | None, list[str]]:
    """The artifact that may adjudicate a boundary of this source semantics.

    The artifact must state the same source semantics, the frozen-geometry cause,
    a reviewed-and-accepted state, a paragraph-boundary representation, and a
    merge experiment measured against a contract whose digest still matches the
    rules it publishes.
    """

    problems: list[str] = []
    admissible: list[dict] = []
    for artifact in evidence:
        deviation = artifact.get("deviation") or {}
        source = artifact.get("source") or {}
        generated = artifact.get("generated") or {}
        experiment = artifact.get("same_word_paragraph_experiment") or {}
        contract = artifact.get("predecessor_geometry_contract") or {}
        review = artifact.get("review") or {}
        if str(source.get("break_semantics")) != source_semantics:
            continue
        if str(deviation.get("kind")) != STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY:
            continue
        if str(deviation.get("state")) != DEVIATION_STATE_REVIEWED_ACCEPTED:
            continue
        # The acceptance has to name its authority: it is a recorded project-policy
        # decision, not an inference this check is allowed to make.
        if str(review.get("state")) != DEVIATION_REVIEW_STATE_ACCEPTED_BY_PROJECT_POLICY:
            continue
        if str(review.get("authority")) != DEVIATION_REVIEW_AUTHORITY_PROJECT_POLICY:
            continue
        if review.get("accepted_by_automation") is not False:
            continue
        if not review.get("reviewed_by") or not review.get("reviewed_at"):
            continue
        if not review.get("open_review_item"):
            continue
        if str(generated.get("representation")) != PARAGRAPH_BOUNDARY_REPRESENTATION:
            continue
        if generated.get("same_word_paragraph") is not False:
            continue
        if str(experiment.get("outcome")) != "SAME_WORD_PARAGRAPH_UNAVAILABLE":
            continue
        if not experiment.get("geometry_rule_ids_failed"):
            continue
        if not contract.get("rules"):
            continue
        if str(contract.get("tolerance_pt")) != "2.0":
            continue
        if contract.get("rebaselined") is not False:
            continue
        if _contract_rules_digest(contract["rules"]) != str(
            contract.get("contract_sha256")
        ):
            problems.append("PREDECESSOR_CONTRACT_DIGEST_MISMATCH")
            continue
        admissible.append(artifact)
    if not admissible:
        return None, problems or ["NO_ADMISSIBLE_STRUCTURAL_DEVIATION_EVIDENCE"]
    return admissible[0], problems


def _deviation_condition_report(
    *,
    element: dict,
    element_key: str,
    classification: str,
    classification_reason: str,
    pieces: list[dict],
    breaks_inside: list[dict],
    blank_between: list[int],
    spacing: list[dict],
    isolation_record: dict | None,
    artifact: dict | None,
    delivered: list[dict],
) -> dict:
    """Evaluate the deviation contract for one candidate boundary.

    Conditions describing the *boundary* are read from the delivered document.
    Conditions describing the *proof* are read from the artifact and from the
    predecessor contract it pins.  Keeping the two apart is exactly the confusion
    this reconciliation removes: a recorded isolation states what the builder
    needed, never what the source did.
    """

    generated = (artifact or {}).get("generated") or {}
    experiment = (artifact or {}).get("same_word_paragraph_experiment") or {}
    contract = (artifact or {}).get("predecessor_geometry_contract") or {}
    review = (artifact or {}).get("review") or {}
    predecessor = (artifact or {}).get("predecessor_artifact") or {}
    deviation = (artifact or {}).get("deviation") or {}

    recorded_reason = str((isolation_record or {}).get("reason") or "")
    indexes = sorted(int(piece["index"]) for piece in pieces)
    first_index, last_index = indexes[0], indexes[-1]
    # The build's isolation record names the paragraph context it created to hold
    # the frozen rule.  Which side of the boundary that paragraph sits on is the
    # build's own choice, so the boundary is the isolation index or the paragraph
    # immediately before it - never a position this check assumes.
    isolation_index = None if isolation_record is None else int(
        isolation_record.get("generated_paragraph_index", last_index)
    )
    # The boundary the build isolated is the isolated paragraph itself or the one
    # it follows; which side the build chose is the build's own decision.
    resolved_indexes = (
        set()
        if isolation_index is None
        else {isolation_index, isolation_index - 1} & set(indexes)
    )
    merged_text = "".join(
        paragraph["compact"]
        for paragraph in delivered
        if first_index <= int(paragraph["index"]) <= last_index
    )
    # The element's own text is compared with the prompts a resolved value
    # replaced taken out, because those characters came from the facts and never
    # stood in the source's own sentence.
    source_text = "".join(str(element_key or "").split())
    # The delivered pieces are only one split of the element when they are a
    # contiguous run of paragraphs that reconstruct the element's own characters
    # in the source's order.  Corresponding characters one-for-one is the
    # strongest available reading-order statement: nothing was reordered, nothing
    # was dropped and nothing was inserted.
    contiguous = indexes == list(range(first_index, last_index + 1))
    order_preserved = bool(source_text) and _is_subsequence(source_text, merged_text)

    conditions = {
        # 1-2: the source's own semantics, proven by the source model.
        "source_evidence_proves_one_logical_paragraph": (
            str(element.get("kind")) == "LogicalParagraph"
            and int(element.get("row_count") or 1) > 1
        ),
        "source_boundary_classification_is_natural_wrap": (
            classification == NATURAL_WRAP_SEMANTICS
        ),
        # 3-5: the generated container, read from the delivered OOXML.
        "generated_structure_is_a_native_paragraph_boundary": (
            len(pieces) > 1
            and contiguous
            and order_preserved
            and bool(resolved_indexes)
        ),
        "generated_boundary_has_no_w_br_no_w_cr_no_empty_paragraph": (
            not breaks_inside
            and not blank_between
            and not any(int(piece.get("cr") or 0) for piece in pieces)
        ),
        "generated_boundary_spacing_is_zero_or_source_equivalent": not spacing,
        # 6-8: what the reader is shown.
        "no_visible_blank_row_is_introduced": not blank_between,
        "reading_order_is_unchanged": (
            bool(generated.get("reading_order_unchanged")) and order_preserved
        ),
        "text_content_is_unchanged": (
            bool(generated.get("text_content_unchanged"))
            and order_preserved
            and contiguous
        ),
        # 9: the split sits on a real source visual-row transition.
        "split_occurs_at_a_source_visual_row_transition": (
            bool(experiment.get("boundary_row_transition"))
            and int(element.get("row_count") or 1) > 1
        ),
        # 10-15: the proof that no allowed representation holds both contracts.
        "same_w_p_rendering_experimentally_tested": (
            experiment.get("same_word_paragraph_attempted") is True
            and str(experiment.get("outcome")) == "SAME_WORD_PARAGRAPH_UNAVAILABLE"
        ),
        "experiment_fails_an_independently_frozen_source_geometry_contract": (
            bool(experiment.get("geometry_rule_ids_failed"))
            and str(experiment.get("frozen_geometry_gate_outcome")) == "FAIL"
        ),
        "the_violated_geometry_contract_predates_the_deviation": (
            contract.get("rebaselined") is False
            and bool(contract.get("contract_sha256"))
            and bool(predecessor.get("exists"))
        ),
        "no_permitted_native_inline_construct_satisfies_both": bool(
            experiment.get("permitted_native_constructs_exhausted")
        ),
        "preserving_geometry_requires_no_tolerance_weakening": (
            str(contract.get("tolerance_pt")) == "2.0"
            and contract.get("tolerance_weakened") is False
        ),
        "no_source_geometry_rebaseline_is_performed": (
            contract.get("rebaselined") is False
        ),
        # 16-17: the deviation is disclosed and still owed to a human.
        "deviation_is_surfaced_explicitly": (
            bool(deviation.get("surfaced_in_qa")) and bool(recorded_reason)
        ),
        "a_human_review_item_remains_open": bool(review.get("open_review_item")),
    }

    missing = [name for name, ok in conditions.items() if not ok]
    # The build's own recorded reason must name the accepted cause, otherwise the
    # evidence is describing a different boundary than the one measured.
    if recorded_reason not in FROZEN_GEOMETRY_RECORDED_REASONS:
        missing.append("recorded_isolation_reason_matches_the_accepted_cause")

    return {
        "conditions": conditions,
        "missing_conditions": missing,
        "classification_reason": classification_reason,
        "recorded_isolation_reason": recorded_reason or None,
        "fidelity_difference": FIDELITY_DIFFERENCE_CONTAINER,
        "container_fidelity": SOURCE_CONTAINER_MISMATCH,
        "deviation_kind": STRUCTURAL_ISOLATION_REQUIRED_BY_FROZEN_GEOMETRY,
        "deviation_state": (
            DEVIATION_STATE_REVIEWED_ACCEPTED if not missing else DEVIATION_STATE_NONE
        ),
    }


def _hard_break_accounting(delivered, isolated, row_break_paragraphs) -> dict:
    """Reader-visible hard breaks, split into accounted and unaccounted.

    The gate's own row model decides what a delivered break means: a ``w:br``
    inside a delivered paragraph the gate matched to one of the source's own
    multi-row elements *is* that source's row separation, and an isolated
    frozen-geometry paragraph carries none by contract.  A break beyond the count
    the source's own rows explain is a break the reader sees that the source's
    structure does not account for, so it is counted and disclosed rather than
    tolerated.
    """

    explained = {int(index): int(rows) for index, rows in row_break_paragraphs.items()}
    total_br = 0
    total_cr = 0
    unexpected_br = 0
    unexpected_cr = 0
    for paragraph in delivered:
        index = int(paragraph["index"])
        br = int(paragraph.get("breaks") or 0)
        cr = int(paragraph.get("cr") or 0)
        total_br += br
        total_cr += cr
        if index in explained:
            # The source's own row separation: Word needs exactly one break per
            # additional source row, so the first N-1 breaks are the source's and
            # anything beyond them is the builder's.
            allowed = max(0, explained[index] - 1)
            unexpected_br += max(0, br - allowed)
            unexpected_cr += cr
        else:
            unexpected_br += br
            unexpected_cr += cr
    return {
        "generated_w_br": total_br,
        "generated_w_cr": total_cr,
        "unexpected_w_br_count": unexpected_br,
        "unexpected_w_cr_count": unexpected_cr,
    }


def _break_disclosure(delivered, isolated, row_break_paragraphs) -> list[dict]:
    """Every delivered hard break the source's own row model does not explain.

    Counted separately from the deviation so the two can never be confused: a
    reviewed structural deviation is a *paragraph boundary*, while this lists the
    inline ``w:br``/``w:cr`` a reader also sees.  Each is reported with the text
    it sits in, so a human can adjudicate it instead of it passing silently.
    """

    explained = {int(index): int(rows) for index, rows in row_break_paragraphs.items()}
    disclosed = []
    for paragraph in delivered:
        index = int(paragraph["index"])
        br = int(paragraph.get("breaks") or 0)
        cr = int(paragraph.get("cr") or 0)
        if index in explained:
            allowed = max(0, explained[index] - 1)
            br = max(0, br - allowed)
        if not br and not cr:
            continue
        disclosed.append(
            {
                "generated_paragraph_index": index,
                "w_br": br,
                "w_cr": cr,
                "source_row_count": explained.get(index),
                "in_an_isolated_frozen_geometry_row": index in isolated,
                "text": str(paragraph.get("text") or "")[:60],
                "review": (
                    "source form layout for a single-row source element; the "
                    "source form carries the break, so the human Word review "
                    "adjudicates it - it is never counted as a reviewed "
                    "structural deviation"
                ),
            }
        )
    return disclosed


def _literal_key(key: str, delivered_text: str) -> str:
    """The source's own text, without the prompts a value replaced.

    A tender source prints an instructional prompt where a value belongs - the
    project name and number on a letter's first line - and the delivery prints
    the value there instead.  That prompt is not part of the delivered line, so
    it is not part of the text a delivered paragraph is matched against; a
    bracketed run the delivery never shows is one of those prompts.
    """

    for match in re.finditer(r"[（(][^（()）]{1,24}[)）]", key):
        prompt = match.group(0)
        if prompt and prompt not in delivered_text:
            key = key.replace(prompt, "")
    return key


def _split_pieces(key: str, delivered, values=()) -> list[dict]:
    """The longest run of consecutive paragraphs that reconstructs ``key``.

    A source element a builder broke apart arrives as neighbouring paragraphs,
    each carrying one part of the element's characters.  The element's own text
    is the reference: a delivered paragraph counts as one of its pieces when the
    paragraph's characters appear in it in order, with the values a filled slot
    put in place left out, because those characters come from the facts and not
    from the source's own line.  The run that covers the most of the element is
    the split, if there is one.
    """

    best: list[dict] = []
    best_covered = 0
    index = 0
    while index < len(delivered):
        pieces: list[dict] = []
        covered = 0
        position = index
        matched_until = 0
        while position < len(delivered):
            candidate = delivered[position]
            literal = _literal_text(candidate["compact"], values)
            if not literal:
                # An empty paragraph between two fragments is part of the run's
                # evidence, not the end of it: the reader sees it as a blank line,
                # and the run has to stay together for that to be detected.
                position += 1
                continue
            if len(literal) < MIN_JOIN_CHARS:
                break
            matched = _subsequence_match(literal, key, matched_until)
            if matched is None:
                break
            if covered + len(literal) > len(key) + MIN_JOIN_CHARS:
                break
            pieces.append({**candidate, "literal": literal})
            covered += len(literal)
            matched_until = matched
            position += 1
        if covered > best_covered:
            best, best_covered = pieces, covered
        index = position + 1 if position > index else index + 1
    return best


def _literal_text(text: str, values=()) -> str:
    """The characters of ``text`` the source itself carries.

    A value a fill slot resolved into the delivered paragraph comes from the
    project facts, not from the source's line, so it is removed before the
    paragraph is compared with the source's own text.
    """

    literal = text
    for value in sorted({str(item) for item in values if item}, key=len, reverse=True):
        if value:
            literal = literal.replace(value, "")
    return literal


def _is_subsequence(part: str, whole: str) -> bool:
    """``part``'s characters appear in ``whole`` in order, gaps allowed."""

    return _subsequence_match(part, whole, 0) is not None


def _subsequence_match(part: str, whole: str, start: int) -> int | None:
    """Where ``part``'s characters end inside ``whole``, read from ``start``.

    A delivered fragment of one source element continues where the previous
    fragment stopped: the characters are consumed in order, so two paragraphs that
    merely repeat the same text cannot both count as pieces of one element.
    """

    if not part:
        return None
    cursor = start
    for character in part:
        found = whole.find(character, cursor)
        if found < 0:
            return None
        cursor = found + 1
    return cursor


def _paragraph_alignment(elements, delivered):
    """Justification is the source's own - never added, never dropped."""

    failures = []
    checked = 0
    for element in elements:
        match = _match(element, delivered)
        if match is None:
            continue
        checked += 1
        if element["justified"] and not match["justified"]:
            failures.append(
                {
                    "kind": "SOURCE_JUSTIFIED_NOT_DELIVERED",
                    "source_page": element["source_page"],
                    "glyph_advance_ratio": element["glyph_advance_ratio"],
                    "text": match["text"][:60],
                }
            )
        elif not element["justified"] and match["justified"]:
            failures.append(
                {
                    "kind": "DELIVERED_JUSTIFIED_NOT_IN_SOURCE",
                    "source_page": element["source_page"],
                    "glyph_advance_ratio": element["glyph_advance_ratio"],
                    "text": match["text"][:60],
                }
            )
    return {
        "checked": checked,
        "justified_delivered": sum(1 for item in delivered if item["justified"]),
    }, failures


def _table_cell_line_structure(source_cells, delivered_cells):
    """A cell keeps every source line the source drew inside it.

    The source's rows inside a cell are the cell's own lines - the writer's
    Enter and the source's wrap alike arrive as a row, and the delivery keeps
    them as that cell's own lines.  A cell is one editable Word cell, so the
    lines are compared inside it rather than as paragraphs.

    A line separator may be *native* in either of the two ways Word has: a
    ``w:br`` inside a paragraph, or a paragraph boundary inside the cell.  Both
    are ordinary editable text in one cell; neither merges two source lines into
    one delivered line, which is what the source's own structure forbids.  The
    check therefore counts the separators the cell actually carries - not one
    particular spelling of them - and still fails when a source line is dropped,
    merged or reordered.
    """

    failures = []
    checked = 0
    for cell in source_cells:
        expected_rows = [text for text in cell["row_texts"] if text]
        if not expected_rows:
            continue
        match = _match(cell, delivered_cells)
        if match is None:
            continue
        checked += 1
        delivered_rows = [
            _compact(line) for line in match["text"].split("\n") if _compact(line)
        ]
        paragraph_boundaries = max(0, len(match.get("paragraphs") or ()) - 1)
        native_line_separators = int(match["breaks"]) + paragraph_boundaries
        if (
            native_line_separators != len(expected_rows) - 1
            or delivered_rows != expected_rows
        ):
            failures.append(
                {
                    "source_page": cell["source_page"],
                    "source_rows": expected_rows[:4],
                    "delivered_rows": delivered_rows[:4],
                    "delivered_breaks": match["breaks"],
                    "delivered_paragraph_boundaries": paragraph_boundaries,
                    "delivered_line_separators": native_line_separators,
                    "expected_breaks": len(expected_rows) - 1,
                    "expected_line_separators": len(expected_rows) - 1,
                }
            )
    return checked, failures


def _source_bold_fidelity(elements, source_cells, delivered, delivered_cells):
    """Text the source drew bold reaches the delivery bold."""

    failures = []
    checked = 0
    contents_entries = 0
    jobs = [(element, delivered) for element in elements]
    jobs += [(cell, delivered_cells) for cell in source_cells]
    for source, candidates in jobs:
        match = _match(source, candidates)
        if match is None:
            continue
        if str(match.get("style") or "").startswith(CONTENTS_STYLE_PREFIX):
            contents_entries += 1
            continue
        text = _compact(match["text"])
        for run in source["runs"]:
            key = run["compact"]
            if not run["bold"] or len(key) < MIN_JOIN_CHARS or key not in text:
                continue
            coverage = _coverage(match["runs"], key, "bold")
            if not coverage:
                continue
            checked += 1
            if not all(coverage):
                failures.append(
                    {
                        "source_page": source["source_page"],
                        "source_run": key[:40],
                        "delivered_bold": coverage,
                    }
                )
    return checked, contents_entries, failures


def _source_underline_fidelity(source_pdf: Path, elements, delivered):
    """A rule under the source's own glyphs underlines exactly those glyphs."""

    failures = []
    checked = 0
    with pymupdf.open(str(source_pdf)) as document:
        for page in document:
            page_number = page.number + 1
            rules = _source_rules(page)
            if not rules:
                continue
            for rule in rules:
                for element in elements:
                    if element["source_page"] != page_number:
                        continue
                    owner = _owner_run(element, rule)
                    if owner is None:
                        continue
                    covered = _covered_text_from_bbox(owner, rule)
                    if len(covered) < 2:
                        continue
                    match = _match(element, delivered)
                    if match is None:
                        continue
                    checked += 1
                    joined = "".join(
                        _compact(run.get("text"))
                        for run in match["runs"]
                        if _compact(run.get("text"))
                    )
                    if covered not in joined:
                        failures.append(
                            {
                                "kind": "COVERED_TEXT_NOT_DELIVERED",
                                "source_page": page_number,
                                "covered": covered[:40],
                                "delivered": joined[:40],
                            }
                        )
                        continue
                    underlines = _coverage(match["runs"], covered, "underline")
                    if not underlines or not any(
                        _visible_underline(value) for value in underlines
                    ):
                        failures.append(
                            {
                                "kind": "UNDERLINE_NOT_DELIVERED",
                                "source_page": page_number,
                                "covered": covered[:40],
                            }
                        )
    return checked, failures


def _owner_run(element, rule):
    """The source run a rule's extent is mostly drawn beneath."""

    x0, x1 = float(rule["x0"]), float(rule["x1"])
    y = float(rule["y"])
    width = max(0.01, x1 - x0)
    for run in element["runs"]:
        rx0, ry0, rx1, ry1 = (float(value) for value in run["bbox"])
        if rx1 <= rx0:
            continue
        if not (ry0 - RULE_LINE_TOLERANCE_PT <= y <= ry1 + RULE_LINE_TOLERANCE_PT):
            continue
        overlap = min(rx1, x1) - max(rx0, x0)
        if overlap / width >= RULE_TEXT_OCCUPANCY_UNDERLINE:
            return run
    return None


def _resolved_values(build_dir: Path) -> tuple:
    """The values this build filled into the source's own slots."""

    report = json.loads(
        (build_dir / "generation_report.json").read_text(encoding="utf-8")
    )
    values = []
    for key in (
        "filled_slots",
        "source_form_line_value_runs",
        "source_anchored_value_runs",
        "source_fill_applications",
    ):
        for record in report.get(key, []) or ():
            for field in ("value", "resolved_value", "text"):
                value = record.get(field)
                if isinstance(value, str) and len(value.strip()) >= 2:
                    values.append(value.strip())
            for value in record.get("resolved_values", []) or ():
                if isinstance(value, str) and len(value.strip()) >= 2:
                    values.append(value.strip())
    return tuple(dict.fromkeys(values))


def _covered_text_from_bbox(owner, rule):
    """The covered characters of a delivered-side run record."""

    return _covered_text(owner, float(rule["x0"]), float(rule["x1"]))


def _fixed_blank_fidelity(build_dir: Path, rendered_pdf: Path):
    """Every source blank the build registered is delivered as that blank.

    The registry is the build's own statement of which source rules it read as
    blanks - a table border and a source line's underscore are not blanks - and
    each registered rule is then required to appear as a delivered blank record
    over the same source span, and to have painted a rule of that width.
    """

    report = json.loads(
        (build_dir / "generation_report.json").read_text(encoding="utf-8")
    )
    registry = report.get("source_rule_registry", [])
    records = list(report.get("positioned_blank_records", []))
    records += list(report.get("blank_representation_records", []))
    failures = []
    checked = 0
    rendered = pymupdf.open(str(rendered_pdf)) if rendered_pdf.exists() else None
    try:
        for rule in registry:
            # A blank the source leaves blank: the rule is a fillable gap, and
            # its own line carries no text for it. A form-layout rule that runs
            # through the line's text is that line's own decoration, not a blank.
            if str(rule.get("transformation_policy") or "") != "FIXED_EMPTY_SLOT":
                continue
            if str(rule.get("relation_type") or "") == "FORM_LAYOUT_RULE":
                continue
            page_number = int(rule.get("source_page") or 0)
            span = (float(rule["x0"]), float(rule["x1"]))
            checked += 1
            matched = _matching_blank(records, page_number, span)
            if not matched:
                failures.append(
                    {
                        "kind": "REGISTERED_GAP_RULE_NOT_DELIVERED_AS_BLANK",
                        "source_page": page_number,
                        "source_rule_id": rule.get("source_rule_id"),
                        "source_span": [round(value, 2) for value in span],
                    }
                )
                continue
            if rendered is not None and _painted_width(rendered, matched, span) is None:
                failures.append(
                    {
                        "kind": "BLANK_NOT_PAINTED_IN_RENDER",
                        "source_page": page_number,
                        "source_rule_id": rule.get("source_rule_id"),
                        "source_span": [round(value, 2) for value in span],
                    }
                )
    finally:
        if rendered is not None:
            rendered.close()
    return checked, failures


def _flow_placed_rule_ids(build_dir: Path):
    """The source rules the emitter itself placed by flow, and why.

    When an element owns several source rows and stays one Word paragraph, a row
    the flow carries has no line origin of its own, so a rule standing on it can
    no longer be tabbed to at its source ``x0``.  The emitter states which rows
    those are - in its assembly gaps and in the blank records it chose a flow
    representation for - and this gate reads that statement instead of guessing
    from geometry.
    """

    report = json.loads(
        (build_dir / "generation_report.json").read_text(encoding="utf-8")
    )
    registry = {
        str(rule.get("source_rule_id")): rule
        for rule in report.get("source_rule_registry", [])
    }
    reasons: dict[str, str] = {}
    for gap in report.get("source_visual_line_assembly_gaps") or []:
        if "wrapped row" not in str(gap.get("reason") or ""):
            continue
        for rule_id in gap.get("source_rule_ids") or []:
            reasons.setdefault(str(rule_id), str(gap.get("reason")))
    for record in report.get("positioned_blank_records") or []:
        if str(record.get("emission_mechanism")) != "SOURCE_INLINE_BLANK_AT_FLOW_CURSOR":
            continue
        rule_id = record.get("source_rule_id")
        if rule_id:
            reasons.setdefault(
                str(rule_id),
                "blank emitted at the flow cursor: its source row wrapped",
            )
    entries = [registry[rule_id] for rule_id in reasons if rule_id in registry]
    return entries, reasons


def match_flow_placed_rule(source_span, painted):
    """The painted rule that best answers a flow-placed source rule.

    Only one endpoint can be held, so the best candidate is the one whose nearer
    endpoint is nearest the source's own - and only candidates of a plausible
    width compete, so a short segment of the same line cannot claim the rule.
    """

    source_x0, source_x1 = float(source_span[0]), float(source_span[1])
    width = source_x1 - source_x0
    best = None
    for segment in painted:
        span = float(segment["x1"]) - float(segment["x0"])
        if span < FLOW_PLACED_MIN_WIDTH_RATIO * width:
            continue
        if span > FLOW_PLACED_MAX_WIDTH_RATIO * width:
            continue
        start = abs(float(segment["x0"]) - source_x0)
        end = abs(float(segment["x1"]) - source_x1)
        anchored = "START" if start <= end else "END"
        deviation = min(start, end)
        if best is None or deviation < best["anchored_deviation_pt"]:
            best = {
                "source_span": [round(source_x0, 2), round(source_x1, 2)],
                "painted_span": [
                    round(float(segment["x0"]), 2),
                    round(float(segment["x1"]), 2),
                ],
                "anchored_endpoint": anchored,
                "anchored_deviation_pt": round(deviation, 2),
                "start_deviation_pt": round(start, 2),
                "end_deviation_pt": round(end, 2),
                "painted_width_pt": round(span, 2),
                "source_width_pt": round(width, 2),
            }
    return best


def _flow_placed_rule_endpoints(build_dir: Path, rendered: Path):
    """Every flow-placed rule keeps one of its own source endpoints.

    The source rule's ``x0``/``x1`` are its identity, and a rule the flow moved
    cannot keep both: Word's cursor decides where on the line it starts.  What
    the delivery still owes is that the rule it paints is *this* rule - so its
    anchored endpoint lands on the source's, and the painted span is of the right
    order.  Both endpoint deviations are reported, not only the passing one.
    """

    rules, reasons = _flow_placed_rule_ids(build_dir)
    # A rule the source's own text covers is that text's decoration: the delivery
    # keeps it by keeping the text's underline, and the text is placed by the
    # flow, so neither endpoint is the delivery's to hold.  Only a rule drawn
    # through clear space is a blank whose geometry the emitter owns.
    blanks = []
    decorations = []
    value_representations = []
    anchor_records = {
        str(record.get("source_rule_id")): record
        for record in (
            json.loads((build_dir / "generation_report.json").read_text(encoding="utf-8")).get(
                "source_form_line_value_runs"
            )
            or []
        )
    }
    for rule in rules:
        try:
            occupancy = float(rule.get("text_occupancy") or 0.0)
        except (TypeError, ValueError):
            occupancy = 0.0
        if occupancy > RULE_TEXT_OCCUPANCY_UNDERLINE:
            decorations.append(
                {
                    "source_rule_id": rule.get("source_rule_id"),
                    "source_page": int(rule.get("source_page") or 0),
                    "text_occupancy": round(occupancy, 3),
                    "transformation_policy": rule.get("transformation_policy"),
                    "reason": (
                        "the source's own text covers this rule, so it is that "
                        "text's decoration and moves with it"
                    ),
                }
            )
            continue
        if str(rule.get("transformation_policy")) in VALUE_INSERTING_POLICIES:
            # A resolved value in a fixed slot is not a blank left to the flow: the
            # owner anchors it at the rule's own source x0 (the build records the
            # anchor mechanism), so this family - which measures the one endpoint a
            # *flow-placed empty blank* can still hold - does not apply.  The frozen
            # closure gate and the underline inventory measure the value run itself.
            anchor = anchor_records.get(str(rule.get("source_rule_id"))) or {}
            value_representations.append(
                {
                    "source_rule_id": rule.get("source_rule_id"),
                    "source_page": int(rule.get("source_page") or 0),
                    "transformation_policy": rule.get("transformation_policy"),
                    "geometry_intent": rule.get("geometry_intent"),
                    "anchor_x": anchor.get("anchor_x"),
                    "anchor_mechanism": anchor.get("anchor_mechanism"),
                    "resolved_values": list(anchor.get("resolved_values") or ()),
                    "reason": (
                        "a resolved value in a fixed slot: the owner anchors the value "
                        "at the source x0, so the rule's start is held by an anchor "
                        "rather than by the flow"
                    ),
                }
            )
            continue
        blanks.append(rule)
    rules = blanks
    measurements = {
        "text_decoration_rules": decorations,
        "value_representation_rules": value_representations,
    }
    if not rules:
        return 0, [], measurements
    painted: list[dict] = []
    document = pymupdf.open(str(rendered)) if rendered.exists() else None
    try:
        if document is not None:
            for page in document:
                painted.extend(page_rules(page, include_underlines=True))
    finally:
        if document is not None:
            document.close()
    checked = 0
    observations = []
    failures = []
    for rule in rules:
        rule_id = str(rule.get("source_rule_id"))
        source_x0 = float(rule["x0"])
        source_x1 = float(rule["x1"])
        width = source_x1 - source_x0
        checked += 1
        best = match_flow_placed_rule((source_x0, source_x1), painted)
        if best is not None:
            best["source_rule_id"] = rule_id
            best["source_page"] = int(rule.get("source_page") or 0)
            best["placement"] = "FLOW_PLACED_WRAPPED_ROW"
            best["reason"] = reasons.get(rule_id)
        if best is None:
            failures.append(
                {
                    "kind": "FLOW_PLACED_RULE_NOT_PAINTED",
                    "source_rule_id": rule_id,
                    "source_page": int(rule.get("source_page") or 0),
                    "source_span": [round(source_x0, 2), round(source_x1, 2)],
                    "reason": reasons.get(rule_id),
                }
            )
            continue
        observations.append(best)
        if best["anchored_deviation_pt"] > FLOW_PLACED_ENDPOINT_TOLERANCE_PT:
            failures.append(
                {
                    "kind": "FLOW_PLACED_RULE_LOST_BOTH_ENDPOINTS",
                    "source_rule_id": rule_id,
                    "source_page": best["source_page"],
                    "source_span": best["source_span"],
                    "painted_span": best["painted_span"],
                    "start_deviation_pt": best["start_deviation_pt"],
                    "end_deviation_pt": best["end_deviation_pt"],
                    "tolerance_pt": FLOW_PLACED_ENDPOINT_TOLERANCE_PT,
                    "reason": reasons.get(rule_id),
                }
            )
    return checked, failures, {
        "observations": observations,
        "text_decoration_rules": decorations,
    }


def _gap_rule(rule, runs):
    """``None`` unless the source drew this rule through clear space."""

    from types import SimpleNamespace

    entry = SimpleNamespace(
        bbox=(float(rule["x0"]), float(rule["y"]), float(rule["x1"]), float(rule["y"])),
        orientation="horizontal",
    )
    occupancy = rule_text_occupancy(entry, runs)
    if occupancy > RULE_TEXT_OCCUPANCY_GAP:
        return None
    return "GAP_FILL_RULE"


def _record_page(record) -> int:
    """The source page a delivered blank record came from.

    A positioned blank record carries the page it emitted on; a representation
    record carries the locator it was read from.  Either is the emitter's own
    statement, so the identity is read, never re-derived.
    """

    page = record.get("source_page")
    if page in (None, ""):
        page = (record.get("source_locator") or {}).get("page")
    try:
        return int(page or 0)
    except (TypeError, ValueError):
        return 0


def _matching_blank(records, page_number: int, span):
    """The delivered blank records whose own source span is this rule's span.

    The record's fields are strings/numbers written by the emitter, so the
    comparison is numeric and the page is the source page the rule came from -
    the identity the emitter recorded, not a re-derived one.
    """

    found = []
    for record in records:
        if _record_page(record) != int(page_number):
            continue
        try:
            x0 = float(record.get("source_x0", 0.0))
            x1 = float(record.get("source_x1", 0.0))
        except (TypeError, ValueError):
            continue
        if abs(x0 - span[0]) <= SPAN_TOLERANCE_PT and abs(x1 - span[1]) <= SPAN_TOLERANCE_PT:
            found.append(record)
    return found


def _painted_width(rendered, records, span):
    """A rendered rule the delivered blank actually paints, at the source width.

    The delivered document reflows, so the *x* a blank lands at belongs to the
    delivery; the width the source's blank spans is the contract.  Every rule
    the delivered page paints is considered - a drawn segment and an underlined
    run alike - so a blank whose underline never reached the page, or reached it
    at the wrong width, is caught.
    """

    want = float(span[1]) - float(span[0])
    widths = {round(want, 2)}
    for record in records:
        for key in ("source_span_pt", "width_pt", "rendered_width_pt"):
            try:
                value = float(record.get(key) or 0.0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                widths.add(round(value, 2))
        try:
            anchor = float(record.get("anchor_tab_position_pt") or 0.0)
            leader = float(record.get("leader_tab_position_pt") or 0.0)
        except (TypeError, ValueError):
            continue
        if leader > anchor:
            widths.add(round(leader - anchor, 2))
    for page in rendered:
        for rule in page_rules(page, include_underlines=True):
            painted = float(rule["x1"]) - float(rule["x0"])
            for width in widths:
                if width <= 0:
                    continue
                if abs(painted - width) <= max(
                    PAINTED_WIDTH_TOLERANCE_PT, PAINTED_WIDTH_RATIO * width
                ):
                    return (round(float(rule["x0"]), 2), round(float(rule["x1"]), 2))
    return None


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--label", default=None)
    args = parser.parse_args(argv)

    def _resolve(path: Path) -> Path:
        return path if path.is_absolute() else ROOT / path

    build_dir = _resolve(args.build)
    source_pdf = _resolve(args.source_pdf)
    out_path = _resolve(args.out)
    rendered = build_dir / "基础投标文件.pdf"

    model = _source_model(source_pdf)
    elements = _source_elements(model)
    source_cells = _source_cells(model)
    delivered = _delivered_paragraphs(build_dir)
    delivered_cells = _delivered_cells(build_dir)

    measurements = {}
    failures = {}

    counts, found = _hard_break_fidelity(
        elements,
        delivered,
        _resolved_values(build_dir),
        _authorized_isolation_paragraphs(build_dir),
    )
    accounting = counts["accounting"]
    reviewed_deviations = counts["reviewed_deviations"]
    # The family status separates the accounting instead of collapsing it: a
    # reviewed deviation is disclosed and counted, never reported as PASS.
    if found:
        hard_break_status = "FAIL"
    elif reviewed_deviations:
        hard_break_status = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION
    else:
        hard_break_status = "PASS"
    measurements["hard_break_fidelity"] = {
        "status": hard_break_status,
        "checked": counts["checked"],
        "failed": len(found),
        "authorized_splits": counts["authorized_splits"],
        "authorized_classifications": counts["authorized_classifications"],
        "split_classifications": counts["split_classifications"],
        "isolated_paragraphs": counts["isolated_paragraphs"],
        # Separate accounting, one counter per thing a reader could see.
        **accounting,
        "documented_structural_deviation_count": len(reviewed_deviations),
        "reviewed_structural_deviations": reviewed_deviations,
        "hard_break_disclosure": counts["hard_break_disclosure"],
        "classification_model": {
            "NATURAL_WRAP": counts["note"],
            "SOURCE_EXPLICIT_BREAK": "the source's own list items / source-authored rows",
            "BUILDER_FORCED_BREAK": "one source visual row the builder split",
            "STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW": (
                "a builder split the build recorded as forced by the resolved "
                "value's reflow; recorded, never authorised on its own"
            ),
            "REVIEWED_STRUCTURAL_DEVIATION": (
                "a source natural wrap the container expresses as a paragraph "
                "boundary because a contract frozen before the deviation makes the "
                "merged representation unreachable; admissible only under the "
                "%d-condition deviation contract, reported and never called fidelity"
                % len(STRUCTURAL_DEVIATION_CONDITIONS)
            ),
        },
    }
    failures["HARD_BREAK_FIDELITY"] = found

    counts, found = _paragraph_alignment(elements, delivered)
    measurements["paragraph_alignment"] = {
        "checked": counts["checked"],
        "justified_delivered": counts["justified_delivered"],
        "failed": len(found),
    }
    failures["PARAGRAPH_ALIGNMENT"] = found

    checked, found = _table_cell_line_structure(source_cells, delivered_cells)
    measurements["table_cell_line_structure"] = {
        "checked": checked,
        "failed": len(found),
    }
    failures["TABLE_CELL_LINE_STRUCTURE"] = found

    checked, contents_entries, found = _source_bold_fidelity(
        elements, source_cells, delivered, delivered_cells
    )
    measurements["source_bold_fidelity"] = {
        "checked": checked,
        "failed": len(found),
        "contents_entries_excluded": contents_entries,
    }
    failures["SOURCE_BOLD_FIDELITY"] = found

    checked, found = _source_underline_fidelity(source_pdf, elements, delivered)
    measurements["source_underline_fidelity"] = {
        "checked": checked,
        "failed": len(found),
    }
    failures["SOURCE_UNDERLINE_FIDELITY"] = found

    checked, found = _fixed_blank_fidelity(build_dir, rendered)
    measurements["fixed_blank_fidelity"] = {"checked": checked, "failed": len(found)}
    failures["FIXED_BLANK_FIDELITY"] = found

    # DIAGNOSTIC METADATA ONLY.  A row placed by flow is not a contract: the frozen
    # horizontal contract is measured by the P3 closure gate and by the underline
    # inventory, on both endpoints of every EXACT_SOURCE_SPAN rule.  This family
    # records which rules are still placed by flow and how their endpoints landed,
    # so the accounting is disclosed without letting a second, weaker endpoint
    # model stand in for the frozen contract.
    checked, found, observations = _flow_placed_rule_endpoints(build_dir, rendered)
    measurements["flow_placed_rule_endpoints"] = {
        "checked": checked,
        "failed": len(found),
        "diagnostic_only": True,
        "rules": observations.get("observations", []),
        "text_decoration_rules": observations.get("text_decoration_rules", []),
        "value_representation_rules": observations.get("value_representation_rules", []),
    }

    if any(failures.values()):
        status = "FAIL"
    elif reviewed_deviations:
        status = PASS_WITH_REVIEWED_STRUCTURAL_DEVIATION
    else:
        status = "PASS"
    report = {
        "schema": SCHEMA,
        "gate": "CASE001_SOURCE_TYPOGRAPHY_ROUND3",
        "label": args.label,
        "build_dir": str(build_dir),
        "source_pdf": str(source_pdf),
        "status": status,
        "failed_checks": [name for name, items in failures.items() if items],
        "measurements": measurements,
        "failures": {name: items[:20] for name, items in failures.items()},
        "reviewed_structural_deviations": reviewed_deviations,
        "note": (
            "Typography the source carries and the delivery must keep, measured "
            "from the source model and the delivered document. A pass here is "
            "automation evidence only: MANUAL_WORD_REVIEW_REQUIRED stays true. "
            "A reviewed structural deviation is disclosed and counted; it is "
            "never reported as container fidelity, and it leaves a human review "
            "item open."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": status,
                "failed": report["failed_checks"],
                "reviewed_structural_deviations": [
                    {
                        "source_page": item["source_page"],
                        "deviation_kind": item["deviation_kind"],
                        "deviation_state": item["deviation_state"],
                        "source_semantics": item["source_semantics"],
                        "generated_representation": item["generated_representation"],
                    }
                    for item in reviewed_deviations
                ],
                "measurements": {
                    "hard_break_fidelity": measurements["hard_break_fidelity"],
                },
            },
            ensure_ascii=False,
        )
    )
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
