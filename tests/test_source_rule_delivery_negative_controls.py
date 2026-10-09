"""Negative controls for source-rule delivery.

EVERY CONTROL EXERCISES THE REAL PRODUCTION VALIDATOR.  Each builds a small
source document, a saved DOCX and the emitter records that describe them, then
runs ``build_source_rule_ledger`` - the same function ``scripts/v1_source_rule_delivery.py``
uses - and asserts the exact failure class it must report.  Nothing here mocks a
verdict, and nothing here is specific to a case, a page or a Chinese label: the
source evidence is drawn by the fixture, and the rule's identity comes from that
geometry.

Each bad fixture has a positive counterpart, so a control that "passes" because
the validator rejects everything would fail the corresponding positive case.
"""

from __future__ import annotations

import json

import pymupdf
import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from lxml import etree

from tender_basic.source_rule_delivery import (
    DELIVERED_STRUCTURALLY_BUT_NOT_VISIBLE,
    DELIVERED_VISIBLE_EDITABLE,
    NOT_DELIVERED,
    build_source_rule_ledger,
)
from tender_basic.word_safe_source_builder import add_run_tabbed_text

PAGE_WIDTH, PAGE_HEIGHT = 595.0, 842.0
#: The fixture's label is ASCII on purpose: the source PDF is drawn with the
#: library's default font, which cannot embed CJK, so a CJK label would extract as
#: placeholder glyphs and the control would be measuring the font, not the rule.
LABEL = "FIELD-A:"
RULE_X0, RULE_X1 = 100.0, 212.0
RULE_WIDTH = RULE_X1 - RULE_X0
RULE_Y = 240.0
FONT_PT = 14.0
FIGURE = "\u2007"
#: A figure space carries a digit advance, half an em, so one glyph is this wide.
GLYPH_PT = FONT_PT * 0.5
FULL_COUNT = int(RULE_WIDTH / GLYPH_PT)  # 16


def write_source(path, *, draw_rule=True, y=RULE_Y, rule_ys=None):
    """A one-page source with (or without) drawn horizontal rules.

    The label is drawn clear of the rule's own start, as a source label is, so the
    validator can read it from the source's glyphs.
    """

    document = pymupdf.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_text((40.0, y), LABEL, fontsize=12)
    for rule_y in ((y,) if rule_ys is None else rule_ys):
        if not draw_rule:
            break
        page.draw_line(pymupdf.Point(RULE_X0, rule_y), pymupdf.Point(RULE_X1, rule_y))
    document.save(str(path))
    document.close()


def _bottom_border(paragraph):
    properties = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "8")
    borders.append(bottom)
    properties.append(borders)


def _inline_picture(paragraph):
    run = paragraph.add_run()
    pict = OxmlElement("w:pict")
    run._r.append(pict)


def write_docx(
    path,
    *,
    glyphs=FULL_COUNT,
    border=False,
    picture=False,
    label=LABEL,
    residue=None,
    extra_runs=(),
):
    """A saved DOCX whose paragraphs present the rule exactly as asked."""

    document = Document()
    if border or picture or residue is not None or not glyphs:
        paragraph = document.add_paragraph()
        if label:
            paragraph.add_run(label)
        if glyphs:
            run = paragraph.add_run(FIGURE * glyphs)
            run.underline = True
            run.font.size = Pt(FONT_PT)
        if residue is not None:
            paragraph.add_run(residue)
        if border:
            _bottom_border(paragraph)
        if picture:
            _inline_picture(paragraph)
    else:
        paragraph = document.add_paragraph()
        if label:
            paragraph.add_run(label)
        run = paragraph.add_run(FIGURE * glyphs)
        run.underline = True
        run.font.size = Pt(FONT_PT)
    for text in extra_runs:
        extra = document.add_paragraph()
        extra_run = extra.add_run(FIGURE * text)
        extra_run.underline = True
        extra_run.font.size = Pt(FONT_PT)
    document.save(str(path))


def write_report(
    path,
    *,
    rules=((RULE_X0, RULE_X1, RULE_Y),),
    owner_paragraph=0,
    blank=True,
    owner_record=True,
    resolved_fields=(),
    blocks=None,
):
    """The emitter records that describe the fixture, as the real build does."""

    registry = []
    for index, (x0, x1, y) in enumerate(rules):
        registry.append(
            {
                "source_rule_id": f"NEG-R{index + 1}",
                "source_page": 1,
                "x0": x0,
                "x1": x1,
                "y": y,
                "relation_type": "GAP_FILL_RULE",
                "text_occupancy": 0.0,
                "bearing": True,
                "transformation_policy": "FIXED_EMPTY_SLOT",
                "geometry_intent": "EXACT_SOURCE_SPAN",
                "authoritative_slot_id": None,
                "authoritative_slot_binding": "NO_AUTHORITATIVE_SLOT",
                "allowed_fact_fields": [],
                "resolved_fact_fields": list(resolved_fields),
            }
        )
    payload = {
        "source_rule_registry": registry,
        "editable_blanks": (
            [
                {
                    "kind": "FORM_BLANK",
                    "source_x0": rules[0][0],
                    "source_x1": rules[0][1],
                    "width_pt": rules[0][1] - rules[0][0],
                    "rendered_width_pt": rules[0][1] - rules[0][0],
                    "render_style": "BOTTOM_RULE",
                    "representation_kind": "VECTOR_LINE",
                    "semantic_slot": LABEL,
                    "visible": True,
                    "source_locator": {"page": 1, "block_index": 0},
                }
            ]
            if blank
            else []
        ),
        "positioned_blank_records": [],
        "source_form_line_paragraphs": (
            [
                {
                    "source_page": 1,
                    "source_line_x0": rules[0][0],
                    "source_line_x1": rules[0][1],
                    "source_line_y": rules[0][2],
                    "source_rule_id": "NEG-R1",
                    "source_rule_ids": [f"NEG-R{index + 1}" for index in range(len(rules))],
                    "source_rule_x0": rules[0][0],
                    "source_rule_x1": rules[0][1],
                    "generated_paragraph_index": owner_paragraph,
                }
            ]
            if owner_record
            else []
        ),
        "source_visual_line_emission_plans": list(blocks or []),
        "source_rule_compositions": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def evaluate(tmp_path, *, draw_rule=True, rule_ys=None, **docx_kwargs):
    """Build one synthetic build and run the real validator over it."""

    build = tmp_path / "build"
    build.mkdir(exist_ok=True)
    source = tmp_path / "source.pdf"
    write_source(source, draw_rule=draw_rule, rule_ys=rule_ys)
    report_kwargs = {
        key: docx_kwargs.pop(key)
        for key in ("rules", "owner_paragraph", "blank", "owner_record", "resolved_fields")
        if key in docx_kwargs
    }
    write_docx(build / "基础投标文件.docx", **docx_kwargs)
    write_report(build / "generation_report.json", **report_kwargs)
    (build / "project_facts.json").write_text(
        json.dumps({"fields": {}}, ensure_ascii=False), encoding="utf-8"
    )
    return build_source_rule_ledger(build, source_pdf=source)


def record_for(ledger, rule_id="NEG-R1"):
    return next(
        record for record in ledger.records if record.atom.source_rule_id == rule_id
    )


# --------------------------------------------------------------------------- #
# Positive counterpart: every control's fixture must be able to pass
# --------------------------------------------------------------------------- #


def test_positive_counterpart_is_delivered_visible_editable(tmp_path):
    ledger = evaluate(tmp_path)
    record = record_for(ledger)
    assert record.verdict == DELIVERED_VISIBLE_EDITABLE, record.as_dict()
    assert ledger.verdict == "SOURCE_BLANK_COMPLETENESS = PASS", ledger.counters()
    assert record.visible_coverage_ratio == pytest.approx(1.0, abs=0.06)
    assert ledger.extraneous_rule_count == 0
    assert ledger.not_editable_rule_count == 0


# --------------------------------------------------------------------------- #
# CONTROL 1 — the mandatory rule is absent from the delivery
# --------------------------------------------------------------------------- #


def test_control_1_missing_mandatory_rule_is_not_delivered(tmp_path):
    ledger = evaluate(tmp_path, blank=False, owner_record=False)
    record = record_for(ledger)
    assert record.verdict == NOT_DELIVERED, record.as_dict()
    assert record.first_missing_stage == "STAGE_2_PAGE_LAYOUT"
    assert ledger.missing_rule_count == 1
    assert ledger.verdict != "SOURCE_BLANK_COMPLETENESS = PASS"


# --------------------------------------------------------------------------- #
# CONTROL 2 — the underline property survives but paints too little
# --------------------------------------------------------------------------- #


def test_control_2_short_painted_coverage_is_rejected(tmp_path):
    ledger = evaluate(tmp_path, glyphs=4)
    record = record_for(ledger)
    assert record.verdict == DELIVERED_STRUCTURALLY_BUT_NOT_VISIBLE, record.as_dict()
    assert "INSUFFICIENT_PAINTED_COVERAGE" in record.reasons
    assert record.visible_coverage_ratio < 0.9
    assert ledger.invisible_rule_count == 1


def test_control_2_exactly_enough_coverage_is_accepted(tmp_path):
    """The same fixture at full coverage passes, so the check is a threshold."""

    ledger = evaluate(tmp_path, glyphs=FULL_COUNT)
    assert record_for(ledger).verdict == DELIVERED_VISIBLE_EDITABLE


# --------------------------------------------------------------------------- #
# CONTROL 3 — visible, but not an editable field
# --------------------------------------------------------------------------- #


def test_control_3_border_only_rule_is_visible_but_not_editable(tmp_path):
    ledger = evaluate(tmp_path, glyphs=0, border=True)
    record = record_for(ledger)
    assert record.verdict != DELIVERED_VISIBLE_EDITABLE, record.as_dict()
    assert "SOURCE_FORM_EDITABILITY" in record.reasons
    assert ledger.not_editable_rule_count == 1
    assert ledger.verdict != "SOURCE_BLANK_COMPLETENESS = PASS"


def test_control_3_picture_only_rule_is_rejected(tmp_path):
    ledger = evaluate(tmp_path, glyphs=0, picture=True)
    record = record_for(ledger)
    assert record.verdict != DELIVERED_VISIBLE_EDITABLE, record.as_dict()


# --------------------------------------------------------------------------- #
# CONTROL 4 — a rule the source never drew
# --------------------------------------------------------------------------- #


def test_control_4_invented_rule_is_rejected(tmp_path):
    # The extra run paints 8 glyphs = 56 pt, which no canonical rule covers.
    ledger = evaluate(tmp_path, extra_runs=(8,))
    assert ledger.extraneous_rule_count >= 1, ledger.as_dict()["extraneous_rules"]
    assert ledger.verdict != "SOURCE_BLANK_COMPLETENESS = PASS"
    assert ledger.extraneous_rules[0]["reason"] == "EXTRANEOUS_SOURCE_RULE"


def test_control_4_plain_gap_gains_no_rule(tmp_path):
    """A source with no drawn rule must not report one as delivered."""

    ledger = evaluate(tmp_path, draw_rule=False)
    record = record_for(ledger)
    assert record.verdict != DELIVERED_VISIBLE_EDITABLE, record.as_dict()


# --------------------------------------------------------------------------- #
# CONTROL 5 — the rule was delivered to the wrong owner
# --------------------------------------------------------------------------- #


def test_control_5_rule_delivered_to_the_wrong_owner(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    source = tmp_path / "source.pdf"
    write_source(source)
    # Paragraph 0 is another row entirely; the rule was painted into paragraph 1.
    document = Document()
    document.add_paragraph("FIELD-B:")
    painted = document.add_paragraph()
    run = painted.add_run(FIGURE * FULL_COUNT)
    run.underline = True
    run.font.size = Pt(FONT_PT)
    document.save(str(build / "基础投标文件.docx"))
    write_report(build / "generation_report.json", owner_paragraph=0)
    (build / "project_facts.json").write_text('{"fields": {}}', encoding="utf-8")

    ledger = build_source_rule_ledger(build, source_pdf=source)
    record = record_for(ledger)
    assert "WRONG_OWNER" in record.reasons, record.as_dict()
    assert record.verdict != DELIVERED_VISIBLE_EDITABLE
    assert ledger.wrong_owner_count == 1
    assert ledger.verdict != "SOURCE_BLANK_COMPLETENESS = PASS"


# --------------------------------------------------------------------------- #
# CONTROL 6 — two canonical rules, one delivered owner
# --------------------------------------------------------------------------- #


def test_control_6_two_rules_share_one_delivery_owner(tmp_path):
    # Same x span, different source y: two distinct physical rules.
    rules = ((RULE_X0, RULE_X1, RULE_Y), (RULE_X0, RULE_X1, RULE_Y + 40.0))
    ledger = evaluate(
        tmp_path,
        rules=rules,
        rule_ys=(RULE_Y, RULE_Y + 40.0),
        glyphs=FULL_COUNT,
    )
    # Only one delivered paragraph exists, so at most one rule can own it.
    delivered = [
        record
        for record in ledger.records
        if record.verdict == DELIVERED_VISIBLE_EDITABLE
    ]
    assert len(delivered) <= 1, [record.atom.source_rule_id for record in delivered]
    assert ledger.verdict != "SOURCE_BLANK_COMPLETENESS = PASS"


# --------------------------------------------------------------------------- #
# CONTROL 7 — an invented value in a bidder-owned slot
# --------------------------------------------------------------------------- #


def test_control_7_invented_bidder_fact_is_rejected(tmp_path):
    ledger = evaluate(
        tmp_path,
        glyphs=0,
        residue="GAMMA-CONSTRUCTION-LTD",
    )
    record = record_for(ledger)
    assert "SOURCE_SLOT_OWNERSHIP" in record.reasons, record.as_dict()
    assert ledger.slot_ownership_violation_count == 1
    assert ledger.verdict != "SOURCE_BLANK_COMPLETENESS = PASS"


# --------------------------------------------------------------------------- #
# CONTROL 8 — the rule and its own row were separated
# --------------------------------------------------------------------------- #


def test_control_8_rule_separated_from_its_row(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    source = tmp_path / "source.pdf"
    write_source(source)
    # The label keeps its own paragraph; the rule was pushed into another one.
    document = Document()
    document.add_paragraph(LABEL)
    painted = document.add_paragraph()
    run = painted.add_run(FIGURE * FULL_COUNT)
    run.underline = True
    run.font.size = Pt(FONT_PT)
    document.save(str(build / "基础投标文件.docx"))
    write_report(build / "generation_report.json", owner_paragraph=0)
    (build / "project_facts.json").write_text('{"fields": {}}', encoding="utf-8")

    ledger = build_source_rule_ledger(build, source_pdf=source)
    record = record_for(ledger)
    assert "SOURCE_FORM_STRUCTURE" in record.reasons, record.as_dict()
    assert record.verdict != DELIVERED_VISIBLE_EDITABLE


def test_control_8_single_paragraph_row_is_accepted(tmp_path):
    ledger = evaluate(tmp_path)
    assert record_for(ledger).verdict == DELIVERED_VISIBLE_EDITABLE


# --------------------------------------------------------------------------- #
# Native tab semantics: a declared stop is not a tab, and a literal tab is not
# a tab either
# --------------------------------------------------------------------------- #


def test_real_w_tab_is_emitted_for_a_tab_character():
    document = Document()
    paragraph = document.add_paragraph()
    run = paragraph.add_run()
    add_run_tabbed_text(run, "A\tB")
    assert paragraph.text == "A\tB"
    assert len(run._r.findall(qn("w:tab"))) == 1
    literal = "".join(
        element.text or ""
        for element in run._r.findall(qn("w:t"))
    )
    assert "\t" not in literal


def test_declared_tab_stop_without_a_tab_element_moves_nothing():
    document = Document()
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.tab_stops.add_tab_stop(Pt(72.0))
    run = paragraph.add_run()
    add_run_tabbed_text(run, "A\tB")
    stops = paragraph._p.findall(".//" + qn("w:tabs") + "/" + qn("w:tab"))
    assert stops, "the paragraph declares a stop"
    assert len(run._r.findall(qn("w:tab"))) == 1, "and the run still performs the tab"
    xml = etree.tostring(paragraph._p, encoding="unicode")
    assert "<w:tab/>" in xml


def test_literal_tab_in_w_t_is_not_a_tab_element():
    document = Document()
    paragraph = document.add_paragraph()
    run = paragraph.add_run()
    # ``add_text`` writes the character into ``w:t``; the paragraph reads back the
    # same, and Word does not move on it.
    run.add_text("A\tB")
    assert paragraph.text == "A\tB"
    assert run._r.findall(qn("w:tab")) == []
    assert "\t" in "".join(element.text or "" for element in run._r.findall(qn("w:t")))
