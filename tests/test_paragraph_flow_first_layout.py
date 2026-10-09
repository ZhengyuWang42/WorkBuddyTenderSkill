"""PARAGRAPH-FLOW-FIRST: the generic Word layout contract and its emission rules.

Architectural rule under test (``docs/V1_DECISIONS.md``, PARAGRAPH_FLOW_FIRST):

    Native Word paragraph formatting is the PRIMARY layout mechanism for
    paragraph-like content.  A tab stop is the EXCEPTION mechanism, reserved for
    a genuinely discrete source field.

Nothing in this module is keyed to a case, a page, a paragraph index, a rule id
or a literal string: every fixture is source geometry expressed in points, and
the two artifact checks at the bottom follow the *current build pointer* rather
than a frozen build id, so they describe whatever build is current.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tender_basic.source_paragraph_layout import (  # noqa: E402
    ALIGNMENT_CENTER,
    ALIGNMENT_JUSTIFY,
    ALIGNMENT_LEFT,
    ALIGNMENT_RIGHT,
    CENTER_HACK_COUNT,
    FIRST_LINE_TAB_HACK_COUNT,
    INDENT_CLASS_CHARACTERS,
    INDENT_CLASS_MEASURED,
    INDENT_CLASS_NONE,
    LINE_SPACING_ONE_POINT_FIVE,
    LINE_SPACING_SINGLE,
    POSITIONING_TAB_COUNT,
    RIGHT_HACK_COUNT,
    SourceParagraphLayoutContract,
    apply_source_paragraph_layout,
    audit_docx_paragraph_positioning,
    classify_line_spacing_semantics,
    classify_source_character_indent,
    classify_source_paragraph_alignment_geometry,
)
from tender_basic.word_safe_source_builder import new_word_safe_document  # noqa: E402

from test_round60_form_line_hard_break import (  # noqa: E402
    PAGE_LEFT_PT,
    ROW,
    emit_row,
    reach_of,
)

#: A page frame the fixture rows are measured in.  It is a plain source frame -
#: no case identity, no document type and no font name takes part.
FRAME_X0 = 70.8
FRAME_X1 = 524.4
FRAME_WIDTH = FRAME_X1 - FRAME_X0

GENERALIZATION = ROOT / "acceptance/reports/v1_generalization"


def _frame_paragraph(contract: SourceParagraphLayoutContract):
    """A fresh Word paragraph carrying exactly one layout contract."""

    document = new_word_safe_document()
    paragraph = document.add_paragraph()
    apply_source_paragraph_layout(paragraph.paragraph_format, contract)
    return document, paragraph


def _paragraph_prefix(document) -> tuple[int, float]:
    """Leading tabs and leading whitespace units of the document's first line."""

    text = document.paragraphs[0].text
    tabs = 0
    units = 0.0
    for character in text:
        if character == "\t":
            tabs += 1
        elif character == "\u3000":
            units += 1.0
        elif character.isspace():
            units += 0.25
        else:
            break
    return tabs, units


# --------------------------------------------------------------------------- #
# 1-4: the contract carries the page frame, the indents and their semantics
# --------------------------------------------------------------------------- #


def test_section_margins_establish_the_usable_page_frame():
    contract = SourceParagraphLayoutContract(
        page_width=595.3,
        page_height=841.9,
        section_left_margin=70.8,
        section_right_margin=70.9,
        section_top_margin=42.0,
        section_bottom_margin=42.0,
        paragraph_body_x0=70.8,
        paragraph_body_x1=524.4,
        first_line_x0=70.8,
    )
    assert contract.usable_text_width_pt == pytest.approx(453.6, abs=0.05)
    # The frame is a bound the paragraph lives inside, and it is the section that
    # states it - not the paragraph's own text extent.
    assert contract.paragraph_body_x0 > 0.0
    assert (
        contract.paragraph_body_x0 + contract.usable_text_width_pt
    ) == pytest.approx(contract.paragraph_body_x1, abs=0.05)


def test_body_paragraph_uses_paragraph_indent_and_never_a_leading_tab():
    contract = SourceParagraphLayoutContract(
        left_indent_pt=0.0,
        first_line_indent_pt=24.0,
        alignment=ALIGNMENT_LEFT,
        line_spacing_kind=LINE_SPACING_SINGLE,
    )
    document, paragraph = _frame_paragraph(contract)
    formatting = paragraph.paragraph_format
    # Word's own indentation states the first-line offset; the run text carries
    # no tab, because a tab would move the cursor rather than the paragraph.
    assert formatting.first_line_indent.pt == pytest.approx(24.0, abs=1e-6)
    assert formatting.left_indent.pt == pytest.approx(0.0, abs=1e-6)
    prefix = document.add_paragraph().add_run("正文段落").text
    document.paragraphs[0].add_run("正文段落")
    assert document.paragraphs[0].text == "正文段落"
    assert prefix == "正文段落"
    tabs, units = _paragraph_prefix(document)
    assert (tabs, units) == (0, 0.0)


def test_first_line_indent_source_delta_maps_to_native_paragraph_indentation():
    body_left_x = 72.0
    first_line_x = 96.0
    delta = first_line_x - body_left_x
    contract = SourceParagraphLayoutContract(
        paragraph_body_x0=body_left_x,
        first_line_x0=first_line_x,
        left_indent_pt=0.0,
        first_line_indent_pt=delta,
        continuation_x0=body_left_x,
        font_size=12.0,
    )
    document, paragraph = _frame_paragraph(contract)
    assert paragraph.paragraph_format.first_line_indent.pt == pytest.approx(delta)
    assert paragraph.paragraph_format.left_indent.pt == pytest.approx(0.0)


def test_two_character_chinese_indent_is_a_semantic_character_indent():
    indent = classify_source_character_indent(24.0, 12.0)
    assert indent.classification == INDENT_CLASS_CHARACTERS
    assert indent.is_character_indent
    assert indent.characters == pytest.approx(2.0, abs=1e-6)
    # The rule is measured, never assumed: not every paragraph is two characters.
    assert classify_source_character_indent(21.0, 12.0).classification == (
        INDENT_CLASS_MEASURED
    )
    assert classify_source_character_indent(0.0, 12.0).classification == (
        INDENT_CLASS_NONE
    )
    assert classify_source_character_indent(36.0, 12.0).characters == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# 5-7: alignment is inferred from source geometry and written as w:jc
# --------------------------------------------------------------------------- #


def test_centered_title_uses_paragraph_alignment():
    title = [(240.0, 360.0)]
    alignment = classify_source_paragraph_alignment_geometry(
        title, frame_x0=FRAME_X0, frame_x1=FRAME_X1
    )
    assert alignment.classification == ALIGNMENT_CENTER
    assert alignment.word_alignment == "center"
    document, paragraph = _frame_paragraph(
        SourceParagraphLayoutContract(alignment=ALIGNMENT_CENTER)
    )
    assert paragraph.alignment is not None
    assert int(paragraph.alignment) == 1
    tabs, units = _paragraph_prefix(document)
    assert tabs == 0, "a centred line must not be centred with tabs"
    assert units == 0.0, "a centred line must not be centred with spaces"


def test_right_aligned_signature_uses_paragraph_alignment():
    signature = [(300.0, FRAME_X1)]
    alignment = classify_source_paragraph_alignment_geometry(
        signature, frame_x0=FRAME_X0, frame_x1=FRAME_X1
    )
    assert alignment.classification == ALIGNMENT_RIGHT
    assert alignment.word_alignment == "right"
    _document, paragraph = _frame_paragraph(
        SourceParagraphLayoutContract(alignment=ALIGNMENT_RIGHT)
    )
    assert int(paragraph.alignment) == 2


def test_justified_paragraph_uses_paragraph_alignment():
    # A wrapped paragraph whose own glyph advances prove the lines were stretched
    # to the measure.  The stretch measurement is supplied as evidence; a short
    # final row alone is never read as justification.
    rows = [(FRAME_X0, FRAME_X1), (FRAME_X0, FRAME_X1), (FRAME_X0, 300.0)]
    alignment = classify_source_paragraph_alignment_geometry(
        rows,
        frame_x0=FRAME_X0,
        frame_x1=FRAME_X1,
        wrapped_rows_stretched=True,
    )
    assert alignment.classification == ALIGNMENT_JUSTIFY
    assert alignment.word_alignment == "both"
    # Without the stretch evidence the same rows are an ordinary left paragraph:
    # reaching the right edge is implied by justification, never proof of it.
    plain = classify_source_paragraph_alignment_geometry(
        rows, frame_x0=FRAME_X0, frame_x1=FRAME_X1
    )
    assert plain.classification == ALIGNMENT_LEFT


def test_a_paragraph_inside_its_own_column_is_left_not_centered():
    """A paragraph's own body boundary explains its rows, so it stays flush left.

    The rows here sit well inside the page frame and *look* centred in it, which
    is exactly the false positive a page-frame-only test would make: an indented
    body column is not a centred line.
    """

    rows = [(134.0, 480.0), (110.0, 480.0)]
    naive = classify_source_paragraph_alignment_geometry(
        rows, frame_x0=FRAME_X0, frame_x1=FRAME_X1
    )
    assert naive.classification == ALIGNMENT_CENTER, "the frame alone cannot tell"
    explained = classify_source_paragraph_alignment_geometry(
        rows, frame_x0=FRAME_X0, frame_x1=FRAME_X1, body_x0=110.0
    )
    assert explained.classification == ALIGNMENT_LEFT


# --------------------------------------------------------------------------- #
# 8: line spacing is a Word semantic first
# --------------------------------------------------------------------------- #


def test_one_and_a_half_line_source_rhythm_maps_to_native_word_spacing():
    kind, value, evidence = classify_line_spacing_semantics(12.0, 24.0)
    assert kind == LINE_SPACING_ONE_POINT_FIVE
    assert value == pytest.approx(1.5)
    assert "1.5" in evidence or "ONE_POINT_FIVE" in evidence
    document, paragraph = _frame_paragraph(
        SourceParagraphLayoutContract(
            alignment=ALIGNMENT_LEFT, line_spacing_kind=LINE_SPACING_ONE_POINT_FIVE
        )
    )
    assert paragraph.paragraph_format.line_spacing == pytest.approx(1.5)
    # A single-spaced source stays single, and no exact height is ever invented.
    assert classify_line_spacing_semantics(12.0, 0.0)[0] == LINE_SPACING_SINGLE
    assert classify_line_spacing_semantics(12.0, 12.0)[0] == LINE_SPACING_SINGLE
    for pitch in (0.0, 12.0, 18.0, 24.0, 30.0):
        assert classify_line_spacing_semantics(12.0, pitch)[0] not in (
            "EXACT",
            "AT_LEAST",
        )


# --------------------------------------------------------------------------- #
# 9-10: one source paragraph stays one Word paragraph
# --------------------------------------------------------------------------- #


def test_natural_wrapping_remains_one_word_paragraph(tmp_path):
    from tender_basic.layout_qa import docx_layout_counts
    from tender_basic.word_safe_source_builder import build_source_format_docx
    from test_page_layout import geometry
    from test_review_builder import make_project_facts
    from test_source_format_fidelity import _paragraph_template

    paragraph = geometry(["本单位决定参", "加本次采购活动。"], [96, 72])
    output, _report = build_source_format_docx(
        make_project_facts(), _paragraph_template(paragraph), tmp_path / "wrap.docx"
    )
    document = Document(output)
    assert len(document.paragraphs) == 1, "a PDF row ending is not a paragraph ending"
    counts = docx_layout_counts(output)
    assert counts["word_manual_breaks"] == 0
    # A multi-line source paragraph is not a stack of positioned lines.
    assert counts["layout_tab_hack"] == 0


def test_inline_blank_after_a_label_stays_in_one_paragraph(tmp_path):
    from tender_basic.word_safe_source_builder import build_source_format_docx
    from test_review_builder import make_project_facts
    from test_round46_form_layout import _paragraph, _template
    from tender_basic.source_format import SourceLine

    label = _paragraph("供应商：", bbox=(72, 80, 140, 92))
    document_text = _paragraph("投标人：", block=1, bbox=(72, 120, 140, 132))
    template = _template(
        [label, document_text], lines=[SourceLine(bbox=(145, 97, 300, 97))]
    )
    output, report = build_source_format_docx(
        make_project_facts(), template, tmp_path / "inline.docx"
    )
    document = Document(output)
    # The drawn rule belongs to the label's own paragraph: label, blank and the
    # rest stay one container rather than being split by the blank.
    assert len(document.paragraphs) == 2
    assert document.paragraphs[0].text.startswith("供应商")
    assert report["visible_rule_blanks"] == 1
    assert report["editable_blanks"][0]["width_pt"] == pytest.approx(155.0, abs=0.25)


# --------------------------------------------------------------------------- #
# 11-19: where a tab is allowed, where it is forbidden, and what owns the span
# --------------------------------------------------------------------------- #


def test_blank_at_the_cursor_emits_without_a_redundant_anchor_tab():
    emitted = emit_row(**ROW)
    assert emitted.tab_stops == [round(ROW["blank"][1] - PAGE_LEFT_PT, 2)]
    assert emitted.underlined_runs == ["\t"]
    assert emitted.blank_emitted
    assert emitted.paragraph_count == 1


def test_blank_behind_the_cursor_is_never_dropped():
    emitted = emit_row(label="委托期限：", blank=(120.00, 232.80))
    assert emitted.blank_emitted, "a source blank may never be silently dropped"
    assert emitted.builder.unreachable_positioned_blank_count == 0
    assert emitted.form_line_break_count == 1


def test_no_backward_tab_is_ever_emitted():
    """A tab only ever moves the cursor forward on the line it is emitted on.

    A row whose rule the cursor has already passed re-bases on the source form
    line the emitter opens for it, so its stops are forward from *that* line's
    origin - never from the line the break ended.
    """

    for label, blank, indent in (
        ("委托期限：", (120.00, 232.80), 24.0),
        ("委托期限：", ROW["blank"], 24.0),
        ("我方已充分研究了", (198.10, 375.70), 0.0),
    ):
        emitted = emit_row(label=label, blank=blank, first_line_indent=indent)
        cursor = reach_of(label, first_line_indent=indent)
        assert emitted.tab_stops == sorted(emitted.tab_stops)
        assert all(stop >= 0.0 for stop in emitted.tab_stops)
        if emitted.form_line_break_count == 0:
            for stop in emitted.tab_stops:
                assert stop + PAGE_LEFT_PT >= cursor - 1.0, (label, stop)
        else:
            # The break re-bases the row on the paragraph's own left-indent
            # column, which is the only reason the stops move left at all.
            assert min(emitted.tab_stops) + PAGE_LEFT_PT >= PAGE_LEFT_PT
            assert emitted.blank_emitted


def test_one_blank_has_exactly_one_horizontal_owner():
    emitted = emit_row(**ROW)
    # One leader owns the blank's span, so one underlined run paints it.
    assert emitted.underlined_runs == ["\t"]
    assert len(emitted.tab_stops) == 1
    record = emitted.records[0]
    assert record["source_span_pt"] == pytest.approx(
        ROW["blank"][1] - ROW["blank"][0], abs=0.01
    )
    assert emitted.builder.consecutive_blank_double_ownership_count == 0


def test_blank_width_and_suffix_are_preserved():
    emitted = emit_row(**ROW)
    record = emitted.records[0]
    assert (record["source_x0"], record["source_x1"]) == ROW["blank"]
    assert emitted.builder.blank_width_errors == [0.0]
    # The label survives verbatim next to the blank.
    assert emitted.text.startswith(ROW["label"])


def test_a_true_discrete_source_field_may_use_its_own_tab_stops():
    """A blank genuinely ahead of the cursor is a discrete field: anchor + leader."""

    label = "我方已充分研究了"
    emitted = emit_row(label=label, blank=(198.10, 375.70), first_line_indent=0.0)
    assert emitted.tab_stops == [
        round(198.10 - PAGE_LEFT_PT, 2),
        round(375.70 - PAGE_LEFT_PT, 2),
    ]
    assert emitted.underlined_runs == ["\t"], "only the leader paints the rule"
    assert emitted.blank_emitted
    assert emitted.paragraph_count == 1


def test_no_default_tab_fallthrough_in_an_emitted_document(tmp_path):
    from tender_basic.word_safe_source_builder import build_source_format_docx
    from test_review_builder import make_project_facts
    from test_round46_form_layout import _paragraph, _template
    from tender_basic.source_format import SourceLine

    rows = [
        _paragraph("供应商名称：____", bbox=(72, 80, 260, 92)),
        _paragraph("单位性质：____", block=1, bbox=(72, 105, 260, 117)),
        _paragraph("地址：____", block=2, bbox=(72, 130, 260, 142)),
    ]
    template = _template(
        rows,
        lines=[
            SourceLine(bbox=(160, 94, 300, 94)),
            SourceLine(bbox=(160, 119, 300, 119)),
            SourceLine(bbox=(160, 144, 300, 144)),
        ],
    )
    output, report = build_source_format_docx(
        make_project_facts(), template, tmp_path / "grid.docx"
    )
    # The emitter's own counter proves no tab was ever left to Word's default
    # interval; the artifact audit proves the same thing on the delivered bytes.
    assert report["tab_stop_usage"].get("tabs_without_explicit_stop_count", 0) == 0
    audit = report["paragraph_positioning_tab_audit"]
    assert audit["status"] == "PASS", audit["records"]
    assert audit[POSITIONING_TAB_COUNT] == 0
    assert audit[FIRST_LINE_TAB_HACK_COUNT] == 0
    assert audit[CENTER_HACK_COUNT] == 0
    assert audit[RIGHT_HACK_COUNT] == 0


def test_visible_rule_and_plain_empty_are_different_deliveries(tmp_path):
    from tender_basic.word_safe_source_builder import build_source_format_docx
    from test_review_builder import make_project_facts
    from test_round46_form_layout import _paragraph, _template
    from tender_basic.source_format import SourceLine

    template = _template(
        [
            _paragraph("供应商：", bbox=(72, 80, 140, 92)),
            _paragraph("投标人：", block=1, bbox=(72, 120, 140, 132)),
        ],
        lines=[SourceLine(bbox=(145, 97, 300, 97))],
    )
    output, report = build_source_format_docx(
        make_project_facts(), template, tmp_path / "plain.docx"
    )
    assert report["visible_rule_blanks"] == 1
    assert report["plain_empty_blanks"] == 1
    visible = [blank for blank in report["editable_blanks"] if blank["visible"]]
    invisible = [blank for blank in report["editable_blanks"] if not blank["visible"]]
    assert len(visible) == 1 and len(invisible) == 1
    assert visible[0]["render_style"] == "BOTTOM_RULE"
    assert invisible[0]["render_style"] == "PLAIN_EMPTY"
    # A source-drawn rule is painted by underlined glyph coverage; a plain empty
    # source region invents no rule at all and stays unpainted.
    document = Document(output)
    text = "".join(paragraph.text for paragraph in document.paragraphs)
    assert "_" not in text and "\u00a0" not in text
    painted = [
        run
        for paragraph in document.paragraphs
        for run in paragraph.runs
        if run.underline
    ]
    assert painted, "the drawn rule must be painted"
    assert all(run.text == "\u2007" * len(run.text) for run in painted), [
        run.text for run in painted
    ]
    plain_paragraph = next(
        paragraph
        for paragraph in document.paragraphs
        if paragraph.text.startswith("投标人")
    )
    assert not [run for run in plain_paragraph.runs if run.underline], (
        "a plain empty source region acquires no invented rule"
    )


# --------------------------------------------------------------------------- #
# 20-21: the emitter audits itself, and the audit is a measured gate
# --------------------------------------------------------------------------- #


def test_paragraph_flow_first_audit_counts_a_tab_positioned_paragraph(tmp_path):
    """The audit is a real gate: a manufactured hack must be counted."""

    from docx.enum.text import WD_TAB_ALIGNMENT
    from tender_basic.word_safe_scan import scan_word_safe_docx

    # A hand-positioned paragraph: an ideographic-space prefix carries the title
    # to the frame's centre, and a leading tab whose own stop sits *behind* the
    # paragraph's declared first-line indent cannot move the cursor at all - Word
    # skips it and resolves against its own default interval.  Both are exactly
    # the mechanisms the architecture forbids, so the audit must name them rather
    # than trust the emitter's intent.
    size = 10.5
    title = "居中标题"

    document = new_word_safe_document()
    section = document.sections[0]
    frame_width = (
        section.page_width.pt - section.left_margin.pt - section.right_margin.pt
    )
    # The prefix is sized from the document's own frame, so the fixture states a
    # placement attempt rather than a magic number.
    spaces = int(round((frame_width - size * len(title)) / 2.0 / size))
    hack = document.add_paragraph()
    hack.paragraph_format.first_line_indent = Pt(72.0)
    hack.paragraph_format.tab_stops.add_tab_stop(Pt(24.0), WD_TAB_ALIGNMENT.LEFT)
    hack.add_run("\u3000" * spaces)
    hack.add_run("\t")
    hack.add_run(title)
    clean = document.add_paragraph()
    clean.add_run("普通正文")
    path = tmp_path / "audit.docx"
    document.save(path)
    audit = audit_docx_paragraph_positioning(path)
    counters = audit["counters"]
    assert counters[FIRST_LINE_TAB_HACK_COUNT] == 1
    assert counters[POSITIONING_TAB_COUNT] == 1
    assert counters[CENTER_HACK_COUNT] == 1
    assert counters[RIGHT_HACK_COUNT] == 0
    assert audit["positioning_tab_free"] is False
    assert scan_word_safe_docx(path)["result"] == "PASS"


def test_production_paragraph_positioning_is_owned_by_formatting(tmp_path):
    """The audit passes on a document the production builder emits."""

    from tender_basic.word_safe_source_builder import build_source_format_docx
    from test_review_builder import make_project_facts
    from test_round46_form_layout import _paragraph, _template

    template = _template(
        [
            _paragraph("本项目采用公开招标方式，详见招标文件。", bbox=(72, 80, 480, 92)),
            _paragraph("投标人应当按照招标文件的要求编制投标文件。", block=1, bbox=(72, 110, 480, 122)),
        ]
    )
    output, report = build_source_format_docx(
        make_project_facts(), template, tmp_path / "positions.docx"
    )
    audit = audit_docx_paragraph_positioning(output)
    assert audit["positioning_tab_free"] is True
    assert audit["alignment_property_owned"] is True
    # The derived contract is recorded for every emitted paragraph-like item.
    assert report["source_paragraph_layout_contract_count"] >= 1
    for contract in report["source_paragraph_layout_contracts"]:
        assert contract["paragraph_positioning_owned_by"] == (
            "WORD_PARAGRAPH_FORMATTING"
        )


# --------------------------------------------------------------------------- #
# 22-25: the frozen case invariants, resolved through the CURRENT pointer
# --------------------------------------------------------------------------- #


def _current_build(case: str) -> dict:
    pointer = GENERALIZATION / f"{case}_current_build.json"
    if not pointer.is_file():
        pytest.skip(f"{case} has no current build pointer in this checkout")
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    build_dir = Path(payload.get("build_dir", ""))
    if not build_dir.is_absolute():
        build_dir = ROOT / build_dir
    if not build_dir.is_dir():
        pytest.skip(f"{case} current build is not materialised in this checkout")
    return {"pointer": payload, "build_dir": build_dir}


def _current_report(case: str) -> dict:
    build = _current_build(case)
    report_path = build["build_dir"] / "generation_report.json"
    if not report_path.is_file():
        pytest.skip(f"{case} current build has no generation report")
    return json.loads(report_path.read_text(encoding="utf-8"))


def test_no_positioned_source_blank_is_unreachable_in_the_current_builds():
    """The Round-60 invariant, measured on every current canonical build."""

    seen = 0
    for case in ("case_001", "case_002", "case_003"):
        build = _current_build(case)
        report_path = build["build_dir"] / "generation_report.json"
        if not report_path.is_file():
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        seen += 1
        assert int(report.get("unreachable_positioned_blank_count") or 0) == 0, case
        # Every remaining form-line break is geometric: the cursor had passed
        # the rule's own start, which is the only situation a tab cannot repair.
        for record in report.get("positioned_form_layout_breaks") or []:
            assert float(record["previous_reach_pt"]) > float(record["source_x0"])
    assert seen >= 1, "no current canonical build was materialised"


def test_case001_p3_reviewed_deviation_is_unchanged():
    """The P3 slot semantics of the reviewed build are frozen, not re-decided."""

    for name in ("p3_gate_arch3.json", "p3_gate_arch2.json", "p3_gate_arch1.json"):
        path = GENERALIZATION / name
        if path.is_file():
            break
    else:
        pytest.skip("no P3 gate report is present in this checkout")
    payload = json.loads(path.read_text(encoding="utf-8"))
    # The substantive P3 evidence: every frozen rule keeps its policy, its
    # geometry intent, its horizontal position and its own rule accounting.
    assert payload["semantic_policy_match"] == "8/8"
    assert payload["semantic_intent_match"] == "8/8"
    assert payload["p3_horizontal"] == "8/8"
    accounting = payload["p3_rule_accounting"]
    assert accounting["matched"] == 8
    assert accounting["lost"] == 0
    assert accounting["invented"] == 0
    assert accounting["out_of_tolerance"] == 0
    # The reviewed deviation stays a recorded disclosure with its own authority,
    # and no P3 semantic check is among the failures.
    assert any(
        disclosure["authority"] == "REFLOW_AWARE_V1"
        for disclosure in payload.get("disclosures") or []
    )
    assert set(payload.get("failed_checks") or []) <= {"gates_measured_the_same_build"}


def test_case002_source_form_invariants_hold():
    for name in (
        "case002_word_source_form_fidelity_arch2.json",
        "case002_word_source_form_fidelity.json",
    ):
        path = GENERALIZATION / name
        if path.is_file():
            break
    else:
        pytest.skip("no CASE002 source-form fidelity report is present")
    payload = json.loads(path.read_text(encoding="utf-8"))
    verdict = payload.get("CASE002_WORD_SOURCE_FORM_FIDELITY") or payload.get("result")
    assert verdict == "PASS", payload.get("failed_components") or payload.get("components")


def test_case003_source_text_completeness_and_lot_name():
    for name in (
        "source_text_completeness_case_003_arch2.json",
        "source_text_completeness_case_003.json",
    ):
        path = GENERALIZATION / name
        if path.is_file():
            break
    else:
        pytest.skip("no CASE003 source-text completeness report is present")
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or payload
    assert int(payload.get("source_text_missing", summary.get("source_text_missing", 0))) == 0
    assert int(payload.get("source_text_duplicate", summary.get("source_text_duplicate", 0))) == 0
    lot = payload.get("lot_name") or summary.get("lot_name")
    if lot is not None:
        assert lot == "三标段", lot


def test_current_case002_quotation_table_remains_one_logical_table():
    report = _current_report("case_002")
    tables = report.get("logical_tables") or []
    assert tables, "CASE002 must expose its logical tables"
    # A cross-page quotation table is ONE logical table however many PDF
    # fragments carried it, so no logical table may be a bare fragment.
    assert report.get("logical_table_count") == len(tables)
    for table in tables:
        assert table["fragment_count"] >= 1
    assert int(report.get("generated_real_tables") or 0) == int(
        report.get("logical_table_count") or 0
    )
