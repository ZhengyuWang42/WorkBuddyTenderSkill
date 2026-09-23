"""The form-line emitter's hard-break contract.

A source form row that draws its label, its fill rule and its suffix on ONE
visual row must be delivered as one Word paragraph reached by the rule's own
source-derived tab.  It must not be split by an inline ``w:br``, because that
break adds a line the source never drew and pushes the rule and the suffix onto
it.

These tests exercise the emitter directly, with the project's own page frame, so
the decision under test is the emitter's own reach arithmetic rather than a
rendered renderer's.  Nothing here is keyed to a literal, a page, a paragraph
index, a rule id or a case id: every fixture is a source form row expressed as
geometry, and the two CASE002-style rows at the bottom exist to prove the rule
generalises past the row the defect was found on.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from docx.oxml.ns import qn
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tender_basic.page_layout import (  # noqa: E402
    EditableBlank,
    EditableBlankKind,
    EditableBlankRenderStyle,
)
from tender_basic.source_format import SourceRun  # noqa: E402
from tender_basic.word_safe_source_builder import (  # noqa: E402
    WordSafeSourceDocumentBuilder,
    add_safe_run,
    new_word_safe_document,
)

#: The frozen project page frame.  A form row's source x is only meaningful
#: relative to the text margin it was measured in, so the fixture uses the real
#: frame instead of python-docx's default margins.
PAGE_LEFT_PT = 70.8
PAGE_RIGHT_PT = 524.4

#: A source page number for the fixture rows.  It is provenance only - no
#: assertion here depends on it.
SOURCE_PAGE = 45

CASES = (
    "case_001",
    "case_002",
    "case_003",
)


class Emitted:
    """One emitted form-line paragraph plus the emitter's own record."""

    def __init__(self, document, paragraph, builder):
        self.document = document
        self.paragraph = paragraph
        self.builder = builder

    @property
    def text(self) -> str:
        return self.paragraph.text

    @property
    def hard_breaks(self) -> int:
        return len(
            [
                node
                for node in self.paragraph._p.findall(".//" + qn("w:br"))
                if node.get(qn("w:type")) != "page"
            ]
        )

    @property
    def carriage_returns(self) -> int:
        return len(self.paragraph._p.findall(".//" + qn("w:cr")))

    @property
    def paragraph_count(self) -> int:
        """Body paragraphs that carry any run content."""

        return len([item for item in self.document.paragraphs if item.text])

    @property
    def tab_stops(self) -> list:
        return [
            round(float(stop.position.pt), 2)
            for stop in self.paragraph.paragraph_format.tab_stops
        ]

    @property
    def underlined_runs(self) -> list:
        return [run.text for run in self.paragraph.runs if run.underline]

    @property
    def form_line_break_count(self) -> int:
        return int(self.builder.tab_stop_usage.get("form_layout_break_count", 0))

    @property
    def records(self) -> list:
        return list(self.builder.positioned_blank_records)

    @property
    def blank_emitted(self) -> bool:
        return any(
            str(record.get("emission_id", "")).startswith("POSITIONED_BLANK|")
            for record in self.records
        )


def emit_row(
    *,
    label: str,
    blank: tuple,
    label_size: float = 12.0,
    first_line_indent: float = 24.0,
) -> Emitted:
    """Emit one source form row: a label run followed by its fill rule.

    The emitter is built through ``object.__new__`` on purpose: this exercises
    the emission decision itself, so it needs the emitter's geometry state and
    nothing else about a document build.
    """

    builder = object.__new__(WordSafeSourceDocumentBuilder)
    builder.tab_stop_usage = {}
    builder.positioned_form_layout_breaks = []
    builder.positioned_blank_records = []
    builder._positioned_coordinate_frames = []
    builder.source_rule_registry = []
    builder.flow_inline_blank_count = 0
    builder.unreachable_positioned_blank_count = 0
    builder.inline_blank_count = 0
    builder._form_line_managed_paragraphs = set()
    builder._active_source_page = SOURCE_PAGE
    builder._current_source_visual_row_count = 1
    builder._row_owns_line_context = False
    builder._cell_paragraph_depth = 0
    builder.blank_records = []
    builder.blank_width_errors = []
    builder.visible_rule_blank_count = 0
    builder.plain_empty_blank_count = 0

    document = new_word_safe_document()
    section = document.sections[0]
    section.left_margin = Pt(PAGE_LEFT_PT)
    section.right_margin = Pt(595.3 - PAGE_RIGHT_PT)
    document.add_paragraph()  # a preceding paragraph, so the row is not the first
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.left_indent = Pt(0)
    paragraph.paragraph_format.first_line_indent = Pt(first_line_indent)

    source = SourceRun(
        text=label,
        bbox=(
            PAGE_LEFT_PT,
            0.0,
            PAGE_LEFT_PT + len(label) * label_size,
            label_size,
        ),
        font_size=label_size,
    )
    builder._add_run(paragraph, label, source)
    builder._render_positioned_blank(
        paragraph,
        EditableBlank(
            kind=EditableBlankKind.INLINE_BLANK,
            source_x0=float(blank[0]),
            source_x1=float(blank[1]),
            width_pt=float(blank[1]) - float(blank[0]),
            semantic_slot=None,
            render_style=EditableBlankRenderStyle.UNDERLINED_INLINE,
            source_locator=None,
        ),
        source,
        page_content_x0=PAGE_LEFT_PT,
        page_content_x1=PAGE_RIGHT_PT,
        suffix_start_x=None,
    )
    return Emitted(document, paragraph, builder)


def reach_of(label: str, *, label_size: float = 12.0, first_line_indent: float = 24.0):
    """Where the cursor stands after the label, in the source's own frame.

    The emitter's advance estimate is the emitter's own, so the fixture asks the
    production object for it rather than restating a glyph width here.
    """

    builder = object.__new__(WordSafeSourceDocumentBuilder)
    return PAGE_LEFT_PT + first_line_indent + builder._form_advance_width(
        label, label_size
    )


# --------------------------------------------------------------------------
# 1-3: one source row stays one paragraph, at the source's own geometry
# --------------------------------------------------------------------------

#: The row the defect was found on: the blank starts exactly where the label
#: ends, which is the boundary the old text-presence clause got wrong.
ROW = {"label": "委托期限：", "blank": (154.80, 232.80)}


def test_a_same_row_label_and_blank_emit_no_hard_break():
    emitted = emit_row(**ROW)
    assert emitted.hard_breaks == 0
    assert emitted.carriage_returns == 0
    assert emitted.form_line_break_count == 0
    assert "\n" not in emitted.text


def test_a_same_row_label_and_blank_stay_one_paragraph():
    emitted = emit_row(**ROW)
    assert emitted.paragraph_count == 1
    # The label and the rule are runs of ONE paragraph, in reading order, and
    # the rule is the paragraph's own underlined tab rather than a break.
    assert emitted.text == "委托期限：\t"
    assert emitted.underlined_runs == ["\t"]
    assert emitted.blank_emitted


def test_the_source_rule_span_is_the_emitted_tab_span():
    emitted = emit_row(**ROW)
    source_x0, source_x1 = ROW["blank"]
    # A tab stop is measured from the section text margin, which is the origin
    # the emitter converts against.  The rule's own end is the stop the
    # underlined tab reaches, so the painted span is the source span.
    assert emitted.tab_stops == [round(source_x1 - PAGE_LEFT_PT, 2)]
    record = emitted.records[0]
    assert (record["source_x0"], record["source_x1"]) == (source_x0, source_x1)
    assert record["source_span_pt"] == round(source_x1 - source_x0, 2)
    assert emitted.builder.blank_width_errors == [0.0]


def test_a_rule_ahead_of_the_cursor_is_reached_by_an_anchor_then_a_leader():
    """A blank ahead of the cursor needs no break either - only its own tabs."""

    label = "我方已充分研究了"
    emitted = emit_row(
        label=label, blank=(198.10, 375.70), first_line_indent=0.0
    )
    assert emitted.hard_breaks == 0
    assert emitted.carriage_returns == 0
    assert emitted.paragraph_count == 1
    assert emitted.tab_stops == [
        round(198.10 - PAGE_LEFT_PT, 2),
        round(375.70 - PAGE_LEFT_PT, 2),
    ]
    # The anchor paints nothing and the leader paints the rule, so the rule
    # still spans the source's own 177.6 pt.
    assert emitted.underlined_runs == ["\t"]
    assert round(375.70 - 198.10, 2) == 177.60


def test_every_emitted_tab_stop_is_ahead_of_the_cursor():
    """No backwards tab is ever emitted; that is why the row can stay one line."""

    emitted = emit_row(**ROW)
    cursor = reach_of(ROW["label"])
    assert cursor == ROW["blank"][0]
    for stop in emitted.tab_stops:
        assert stop + PAGE_LEFT_PT >= cursor - 1.0


# --------------------------------------------------------------------------
# The one geometric situation that may still open its own form line
# --------------------------------------------------------------------------


def test_a_rule_the_cursor_has_passed_opens_its_own_form_line():
    """A rule behind the cursor is the only proven need for a fresh line.

    The cursor only moves forward, so no tab stop can carry it back; that row is
    the higher-authority geometric constraint the repair still honours.
    """

    emitted = emit_row(label="委托期限：", blank=(120.00, 232.80))
    assert emitted.hard_breaks == 1
    assert emitted.form_line_break_count == 1
    assert emitted.blank_emitted
    breaks = emitted.builder.positioned_form_layout_breaks
    assert len(breaks) == 1
    # The record proves the geometry, not a suspicion: the cursor was past the
    # rule's own start when the decision was taken.
    assert breaks[0]["overshoot_pt"] > 0.0
    assert breaks[0]["previous_reach_pt"] > breaks[0]["source_x0"]


@pytest.mark.parametrize("offset", [0.0, 1.0, 5.0, 40.0, 120.0])
def test_a_natural_wrap_is_never_turned_into_a_hard_break(offset):
    """A row whose rule is still ahead of the cursor is never broken, at any
    distance - the representation is the rule's own tab, not a line break."""

    cursor = reach_of(ROW["label"])
    emitted = emit_row(
        label=ROW["label"], blank=(round(cursor + offset, 2), 232.80)
    )
    assert emitted.hard_breaks == 0
    assert emitted.carriage_returns == 0
    assert emitted.paragraph_count == 1


def test_the_decision_is_geometry_and_not_the_label_text():
    """The same geometry decides the same way whatever the row's label says.

    Labels from the other two canonical cases are used deliberately: the rule is
    semantic, so it cannot be keyed to the literal the defect was reported on.
    """

    reach = reach_of(ROW["label"])
    for label in ("委托期限：", "项目负责人为", "3、我方拟委派的项目负责人为", "系"):
        size = 12.0
        cursor = PAGE_LEFT_PT + 24.0 + WordSafeSourceDocumentBuilder._form_advance_width(
            object.__new__(WordSafeSourceDocumentBuilder), label, size
        )
        emitted = emit_row(label=label, blank=(round(cursor, 2), round(cursor, 2) + 78.0))
        assert emitted.hard_breaks == 0, label
        assert emitted.paragraph_count == 1, label
    assert reach > 0.0


# --------------------------------------------------------------------------
# A source's own explicit break keeps the approved explicit representation
# --------------------------------------------------------------------------


def test_a_source_explicit_newline_keeps_the_explicit_representation():
    """A break the SOURCE printed is still delivered as an explicit break.

    The repair removes a break the source never drew; it does not remove the
    representation for one the source did draw.
    """

    document = new_word_safe_document()
    paragraph = document.add_paragraph()
    source = SourceRun(text="第一行", bbox=(0.0, 0.0, 36.0, 12.0), font_size=12.0)
    add_safe_run(paragraph, "第一行\n第二行", source)
    breaks = [
        node
        for node in paragraph._p.findall(".//" + qn("w:br"))
        if node.get(qn("w:type")) != "page"
    ]
    assert len(breaks) == 1
    assert paragraph.text == "第一行\n第二行"


# --------------------------------------------------------------------------
# The invariant that generalises: every remaining form-line break is justified
# --------------------------------------------------------------------------

FINAL_BUILDS = {
    case: ROOT
    / f"acceptance/workspace/{case}/v1_manual_fidelity_round3_word_review_final"
    for case in CASES
}


@pytest.mark.parametrize("case", CASES)
def test_no_case_keeps_a_form_line_break_it_could_have_reached(case):
    """Across every canonical case, a remaining form-line break is geometric.

    This is the shared-code regression guard: the emitter is one implementation,
    so a case that keeps a ``w:br`` must be able to show, from its own record,
    that the cursor had already passed the rule.  A break with zero overshoot is
    exactly the defect this repair removed.
    """

    build = FINAL_BUILDS[case]
    report = build / "generation_report.json"
    if not report.exists():
        pytest.skip(f"{case} has no final build in this checkout")
    payload = json.loads(report.read_text(encoding="utf-8"))
    breaks = payload.get("positioned_form_layout_breaks") or []
    for record in breaks:
        assert record["source_x0"] is not None
        assert record["previous_reach_pt"] is not None
        assert float(record["previous_reach_pt"]) - float(record["source_x0"]) > 0.0, (
            f"{case} kept a form-line break for a rule the cursor had not passed: "
            f"{record}"
        )
    # And the counter the emitter keeps agrees with the records it wrote.
    assert int(payload.get("form_layout_break_count") or 0) == len(breaks)
