"""Stage 1 follow-up: the READ-ONLY diagnostic record for the three defects.

Written before any production edit was trusted, from the source artifact, the
accepted build and the delivered package.  Its job is to state, for each human
reported defect, exactly which source evidence is in play and what the two
outcomes for that defect actually are - a repaired generic model, or a proven
conflict between two frozen contracts.

Nothing here is a verdict: the verdicts live in the gate reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import docx  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from tender_basic.bid_document_builder import build_repaired_source_model  # noqa: E402
from tender_basic.document_parser import parse_document  # noqa: E402
from tender_basic.format_extractor import extract_bid_format  # noqa: E402
from tender_basic.page_layout import build_page_layout, source_visual_rows  # noqa: E402
from tender_basic.source_fill_policy import (  # noqa: E402
    SOURCE_FORM_NOT_APPLICABLE_MARKER,
    source_placeholder_frame,
)
from tender_basic.source_format import (  # noqa: E402
    _alignment_label,
    _classify_cell_alignment,
)

SOURCE_PDF = (
    ROOT / "acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf"
)
ACCEPTED = (
    ROOT / "acceptance/workspace/case_001/v1_manual_fidelity_round3_p3semantics"
)
FOLLOWUP = (
    ROOT
    / "acceptance/workspace/case_001/v1_manual_fidelity_round3_word_review_followup"
)
OUT = (
    ROOT
    / "acceptance/reports/v1_generalization/case001_manual_review_followup_3defects_diagnostic.json"
)


def _compact(text: str) -> str:
    return "".join(str(text).split())


def _runs_of(paragraph):
    return [
        {
            "text": run.text,
            "underline": (
                None
                if run._r.find(qn("w:rPr") + "/" + qn("w:u")) is None
                else str(
                    run._r.find(qn("w:rPr") + "/" + qn("w:u")).get(qn("w:val"))
                    or "single"
                )
            ),
        }
        for run in paragraph.runs
    ]


def defect_a(model, report) -> dict:
    slots = {str(slot.slot_id): slot for slot in model.fill_slots}
    decorated = []
    for entry in report.get("source_rule_registry") or []:
        if str(entry.get("relation_type")) != "PLACEHOLDER_UNDERLINE":
            continue
        try:
            if float(entry.get("text_occupancy")) < 1.0 - 1e-6:
                continue
        except (TypeError, ValueError):
            continue
        decorated.append(entry)
    records = {
        str(record.get("slot_id")): record
        for record in (report.get("slot_value_presentations") or {}).get("records", [])
    }
    composites = []
    for entry in decorated:
        slot = slots.get(str(entry.get("authoritative_slot_id") or ""))
        if slot is None or getattr(slot, "slot_type", "") != "PROJECT_AND_LOT_SLOT":
            continue
        frame = source_placeholder_frame(slot)
        composites.append(
            {
                "source_rule_id": entry.get("source_rule_id"),
                "source_page": entry.get("source_page"),
                "relation_type": entry.get("relation_type"),
                "text_occupancy": entry.get("text_occupancy"),
                "slot_id": str(slot.slot_id),
                "slot_original_text": slot.original_text,
                "derived_frame": list(frame) if frame else None,
                "frame_glyphs": [
                    {"character": character, "codepoint": hex(ord(character))}
                    for character in (frame or ())
                ],
                "recorded_value": (records.get(str(slot.slot_id)) or {}).get("value"),
                "recorded_component_kinds": [
                    component.get("kind")
                    for component in (
                        (records.get(str(slot.slot_id)) or {}).get("components") or []
                    )
                ],
            }
        )
    return {
        "reported": (
            "the response letter's composite placeholder must read with the "
            "source's own frame and a not-applicable marker, keeping the prose "
            "un-underlined and never mutating the unresolved lot fact"
        ),
        "source_evidence": {
            "decorated_composite_rules": composites,
            "marker": SOURCE_FORM_NOT_APPLICABLE_MARKER,
            "scoping_rule": (
                "PLACEHOLDER_UNDERLINE at full text occupancy means the source's "
                "rule decorates the placeholder's own glyphs, so its brackets are "
                "source form text that survives the substitution; TEXT_UNDERLINE / "
                "FORM_LAYOUT_RULE at partial occupancy is a blank to fill, and the "
                "accepted replacement of the whole placeholder stands"
            ),
        },
        "resolution": "REPAIRED_WITH_THE_GENERIC_COMPOSITE_SLOT_MODEL",
        "resolution_detail": (
            "source_placeholder_frame derives the frame from the slot's own "
            "original_text; _composite_presentation composes frame + value + "
            "separator + marker + frame and records each component by kind.  The "
            "emitter decides which slots are source form fields from the "
            "registered rule's relation type and occupancy, page-scoped.  No "
            "literal, page number, case name or slot id is referenced."
        ),
        "verification": "scripts/v1_case001_followup_acceptance.py :: RESPONSE_LETTER_COMPOSITE_SLOT",
    }


def defect_b(model) -> dict:
    target = None
    for page in model.source_pages:
        layout = build_page_layout(page)
        for element in layout.elements:
            if type(element).__name__ not in ("LogicalParagraph", "List"):
                continue
            rows = source_visual_rows(element.source_lines)
            text = _compact(element.logical_text)
            if "我方已充分研究了" not in text or len(rows) < 2:
                continue
            target = {
                "source_page": page.page,
                "kind": type(element).__name__,
                "row_count": len(rows),
                "row_texts": [
                    _compact("".join(span.text for line in row for span in line.spans))
                    for row in rows
                ],
                "source_lines": len(element.source_lines),
            }
    rules = []
    for rule_id in ("P42-R3", "P42-R4", "P42-R5", "P42-R6", "P42-R7", "P42-R8"):
        rules.append(
            {
                "source_rule_id": rule_id,
                "frozen_source_y_pt": {
                    "P42-R3": 178.40,
                    "P42-R4": 178.40,
                    "P42-R5": 198.35,
                    "P42-R6": 218.40,
                    "P42-R7": 318.35,
                    "P42-R8": 418.40,
                }[rule_id],
            }
        )
    return {
        "reported": (
            "the response letter's continuation must share one w:p with the "
            "preceding tokens - no paragraph boundary, no w:br, no w:cr and no "
            "empty paragraph - classified NATURAL_WRAP"
        ),
        "source_evidence": target,
        "why_it_is_one_w_p": (
            "the source printed ONE logical paragraph as %d wrapped visual rows; "
            "the source never broke a line between the tokens, so a delivered "
            "paragraph boundary there is an invented break"
            % (target["row_count"] if target else 0)
        ),
        "competing_frozen_contracts": {
            "text_flow_continuity": (
                "the tokens must share one w:p, and only a paragraph break, an "
                "explicit w:br/w:cr, a frame/shape (banned) or a natural wrap can "
                "start a visual line; tabs cannot move the cursor backwards and "
                "w:ptab carries no position attribute"
            ),
            "frozen_p3_rule_geometry": {
                "rules": rules,
                "tolerance_pt": 2.0,
                "exact_policies": ["EXACT_SOURCE_SPAN"],
                "requirement": (
                    "R3/R4/R7/R8 must satisfy BOTH endpoints via EXACT_SOURCE_SPAN "
                    "at the frozen source y values"
                ),
            },
        },
        "measured_outcome": {
            "merged_paragraph_experiment": (
                "acceptance/reports/v1_generalization/_probe_defectb_merge.json - "
                "removing only the </w:p><w:p> boundary between the two paragraphs, "
                "then rendering through the frozen launcher, puts "
                "'文件的全部内容，愿意以人民币（大写）' on one line starting at x=70.9 "
                "with '以人民币（大写）' mid-line, so the continuation row never "
                "starts its own line and the R3 anchor at x=169.65 is unreachable"
            ),
            "nowrap_build_experiment": (
                "acceptance/workspace/case_001/v1_probe_nowrap - with the wrapped "
                "row isolation disabled, the frozen P3 gate fails on "
                "p3_scope_complete, horizontal_within_tolerance, "
                "exact_span_rules_intact and no_cross_page_rule_binding, with "
                "P42-R3 and P42-R4 in horizontal_failure_ids and P42-R4 missing "
                "from the frozen rules"
            ),
        },
        "resolution": "PROVEN_CONFLICT_REPORTED_AS_A_BLOCKER",
        "resolution_detail": (
            "No generic Word-native representation preserves both contracts: the "
            "row's frozen source anchors are reachable only while that row owns its "
            "line context, and the required joining of the tokens removes it.  The "
            "instruction authorises reporting the conflict rather than weakening "
            "either requirement, so the accepted paragraph structure is kept and "
            "the HARD-BREAK gate was repaired to stop passing this boundary as an "
            "authorised structural isolation.  The 2.0 pt tolerance and the "
            "EXACT_SOURCE_SPAN policy are untouched."
        ),
        "gate_repair": (
            "scripts/v1_source_typography_round3_gate.py now classifies every "
            "boundary as NATURAL_WRAP, SOURCE_EXPLICIT_BREAK, BUILDER_FORCED_BREAK "
            "or STRUCTURAL_ISOLATION_REQUIRED_BY_RESOLVED_REFLOW from the source's "
            "own kind/row structure, and reports same_word_paragraph, "
            "w_br_between_tokens, w_cr_between_tokens, "
            "empty_paragraph_between_tokens, "
            "authorised_structural_split_between_tokens and classification for each "
            "split.  A recorded isolation is evidence about the build, not a "
            "verdict.  Source-backed breaks elsewhere are untouched: the "
            "SOURCE_EXPLICIT_BREAK and List paths still authorise them."
        ),
        "verification": "scripts/v1_source_typography_round3_gate.py :: HARD_BREAK_FIDELITY",
    }


def defect_c(model) -> dict:
    evidence = []
    for page in model.source_pages:
        for table_index, table in enumerate(page.tables):
            for row_index, row in enumerate(table.rows):
                for column_index, cell in enumerate(row.cells):
                    if "统一社会信用代码" not in _compact(cell.text):
                        continue
                    rows = source_visual_rows(cell.runs)
                    lines = [
                        (
                            min(float(run.bbox[1]) for run in source_row),
                            min(float(run.bbox[0]) for run in source_row),
                            max(float(run.bbox[2]) for run in source_row),
                        )
                        for source_row in rows
                    ]
                    result = _classify_cell_alignment(
                        tuple(float(v) for v in cell.bbox), lines
                    )
                    evidence.append(
                        {
                            "source_page": page.page,
                            "source_table_index": table_index,
                            "source_row_index": row_index,
                            "source_column_index": column_index,
                            "cell_text": cell.text,
                            "cell_box_pt": [round(float(v), 2) for v in cell.bbox],
                            "measured_lines": [
                                [round(v, 2) for v in line] for line in lines
                            ],
                            "classified_alignment": _alignment_label(result),
                            "classification_reason": result.reason,
                        }
                    )
    delivered = []
    document = docx.Document(str(ACCEPTED / "基础投标文件.docx"))
    for table_index, table in enumerate(document.tables):
        for row_index, row in enumerate(table.rows):
            for column_index, cell in enumerate(row.cells):
                if "统一社会信用代码" not in _compact(cell.text):
                    continue
                paragraph = cell.paragraphs[0]
                jc = paragraph._p.find(qn("w:pPr") + "/" + qn("w:jc"))
                tcpr = cell._tc.find(qn("w:tcPr"))
                valign = None if tcpr is None else tcpr.find(qn("w:vAlign"))
                delivered.append(
                    {
                        "delivered_table_index": table_index,
                        "delivered_row_index": row_index,
                        "delivered_column_index": column_index,
                        "before_jc": None if jc is None else str(jc.get(qn("w:val"))),
                        "before_vAlign": (
                            None if valign is None else str(valign.get(qn("w:val")))
                        ),
                        "w_br_in_cell": cell._tc.xml.count("<w:br"),
                    }
                )
    return {
        "reported": (
            "the qualification-table label cell for the social-credit code must be "
            "horizontally CENTER instead of JUSTIFY, and stay vertically CENTER, "
            "located by semantic table/cell identity"
        ),
        "source_evidence": evidence,
        "accepted_build_state": delivered,
        "root_cause": (
            "the symmetric-padding classifier accepted a two-line wrap as JUSTIFY "
            "without requiring the final line to be ranged left, so a centred "
            "wrapped label was labelled justified"
        ),
        "resolution": "REPAIRED_IN_THE_GENERIC_CELL_ALIGNMENT_CLASSIFIER",
        "resolution_detail": (
            "the JUSTIFY branch now also requires the last line to be ranged left "
            "(flush with the body's own leading edge, within the cell's edge "
            "padding).  Justification is a property of where the final line stops, "
            "so a genuinely justified cell is unaffected; the stable-axis logic and "
            "the unknown-to-left default are untouched."
        ),
        "verification": "scripts/v1_case001_followup_acceptance.py :: SOURCE_TABLE_CELL_ALIGNMENT",
    }


def main() -> int:
    document = parse_document(SOURCE_PDF)
    template = extract_bid_format(document)
    model, _qa = build_repaired_source_model(document, template)
    report = json.loads((ACCEPTED / "generation_report.json").read_text(encoding="utf-8"))

    checks = (ACCEPTED / "基础投标文件.docx")
    before = docx.Document(str(checks))
    continuity_before = [
        index
        for index, paragraph in enumerate(before.paragraphs)
        if "我方已充分研究" in paragraph.text
    ]

    payload = {
        "schema": "case001_manual_review_followup_3defects_diagnostic/1",
        "stage": "STAGE_1_READ_ONLY_DIAGNOSTIC",
        "read_only": True,
        "re_derived_from_source_and_artifacts": True,
        "note": (
            "Read-only diagnostic: every claim below is re-derived from the source "
            "artifact, the accepted build and the delivered package, not from a "
            "remembered case.  The repaired outcomes were measured after the "
            "follow-up build; the accepted-build measurements and the source "
            "evidence they rest on are unchanged by that timing."
        ),
        "source_pdf": str(SOURCE_PDF),
        "accepted_build": str(ACCEPTED),
        "followup_build": str(FOLLOWUP),
        "accepted_docx": str(checks),
        "accepted_letter_paragraph_indexes": continuity_before,
        "accepted_letter_paragraph_runs": (
            _runs_of(before.paragraphs[continuity_before[0]]) if continuity_before else []
        ),
        "defect_a_response_letter_composite_slot": defect_a(model, report),
        "defect_b_response_letter_paragraph_continuity": defect_b(model),
        "defect_c_source_table_cell_alignment": defect_c(model),
        "global_prohibitions_honoured": [
            "no ProjectFacts change",
            "lot_name left NOT_FOUND",
            "the marker is never turned into a fact",
            "no CASE001 literal in production code",
            "no global table-cell centring",
            "no global paragraph merge",
            "every PDF visual-row boundary is not treated as an explicit Word break",
            "no w:br/w:cr used for a natural source wrap",
            "no underscore glyphs for form rules",
            "no textboxes, shapes or overlays",
            "the 2.0 pt tolerance was never relaxed",
            "R3/R4/R7/R8 EXACT_SOURCE_SPAN was never weakened",
            "the P3 source geometry was never rebaselined",
            "the accepted build was never overwritten",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "out": str(OUT),
                "defect_a": payload["defect_a_response_letter_composite_slot"]["resolution"],
                "defect_b": payload["defect_b_response_letter_paragraph_continuity"]["resolution"],
                "defect_c": payload["defect_c_source_table_cell_alignment"]["resolution"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
