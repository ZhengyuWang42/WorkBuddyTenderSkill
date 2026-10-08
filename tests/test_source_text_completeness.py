"""Architecture tests for source-text completeness and exact-once text ownership.

The completeness ledger is the delivery-side half of the rule that a geometry
consumer may *position* source text but may never *own or consume* it.  These
tests cover the ledger's three distinct failures (missing, duplicated,
out-of-order), the rules that keep its comparison honest, and the two slot
shapes the adjacent-rule ownership pass must treat differently.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from tender_basic.models import PdfLocator
from tender_basic.source_format import (
    RULE_OWNERSHIP_MATCH_KINDS,
    SourceFillSlot,
    _own_adjacent_source_rule,
)
from tender_basic.source_format_qa import (
    ROLE_PARAGRAPH_TEXT,
    SourceTextAtom,
    _source_text_completeness,
)


def atom(atom_id: str, text: str, *, page: int = 70, order: int = 0) -> SourceTextAtom:
    return SourceTextAtom(
        atom_id=atom_id,
        source_page=page,
        source_container_id=f"paragraph:{order}",
        source_order_index=order,
        text=text,
        role=ROLE_PARAGRAPH_TEXT,
    )


@dataclass
class FakeRule:
    """The only two attributes the ownership pass reads from a source line."""

    orientation: str
    bbox: tuple[float, float, float, float]


def slot(
    *,
    match_kind: str,
    geometry: tuple[float, float, float, float],
    slot_id: str = "slot-1-1",
    hint: str = "项目名称",
) -> SourceFillSlot:
    return SourceFillSlot(
        slot_id=slot_id,
        semantic_hint=hint,
        source_page=1,
        source_locator=PdfLocator(page=1, block_index=0),
        container_type="paragraph",
        original_text=" ",
        text_start=8,
        text_end=9,
        geometry=geometry,
        match_kind=match_kind,
    )


# --------------------------------------------------------------------------- #
# Ledger semantics
# --------------------------------------------------------------------------- #


def test_present_atom_has_exactly_one_owner() -> None:
    ledger = _source_text_completeness(
        [atom("A", "委托期限：年月日；按合同约定实施")],
        "委托期限：年月日；按合同约定实施",
    )
    assert ledger.exact_once is True
    assert ledger.missing_count == 0
    assert ledger.records[0].text_emission_owner_count == 1


def test_missing_atom_reports_zero_owner_with_locator() -> None:
    ledger = _source_text_completeness(
        [atom("P70-PARA5", "工程质量：合格标准。", page=70, order=29)],
        "unrelated delivered text",
    )
    assert ledger.missing_count == 1
    missing = ledger.missing[0]
    assert missing.text_emission_owner_count == 0
    record = missing.as_dict()
    assert record["atom_id"] == "P70-PARA5"
    assert record["source_page"] == 70
    assert record["first_missing_stage"] == "STAGE_5_IN_MEMORY_DOCX"
    assert record["text"] == "工程质量：合格标准。"


def test_missing_atom_names_its_neighbouring_atoms() -> None:
    ledger = _source_text_completeness(
        [
            atom("A", "第一段完整交付的文字内容", order=0),
            atom("B", "第二段完全没有交付", order=1),
            atom("C", "第三段完整交付的文字内容", order=2),
        ],
        "第一段完整交付的文字内容第三段完整交付的文字内容",
    )
    assert [record.atom.atom_id for record in ledger.missing] == ["B"]
    record = ledger.missing[0].as_dict()
    assert record["neighboring_atom_before"] == "A"
    assert record["neighboring_atom_after"] == "C"


def test_line_wrap_and_whitespace_normalization_do_not_hide_missing_characters() -> None:
    # The same sentence delivered across a wrapped line is present...
    wrapped = _source_text_completeness(
        [atom("A", "按合同约定实施和完成承包工程")],
        "按合同约定实施\n和完成承包工程",
    )
    assert wrapped.missing_count == 0
    # ...but a missing character inside it is still missing.
    truncated = _source_text_completeness(
        [atom("A", "按合同约定实施和完成承包工程")],
        "按合同约定实施和完成承包",
    )
    assert truncated.missing_count == 1


def test_out_of_order_is_reported_separately_from_missing() -> None:
    ledger = _source_text_completeness(
        [
            atom("A", "第一段完整交付的文字内容", order=0),
            atom("B", "第二段完整交付的文字内容", order=1),
        ],
        "第二段完整交付的文字内容第一段完整交付的文字内容",
    )
    assert ledger.missing_count == 0
    assert len(ledger.out_of_order) == 1
    assert ledger.out_of_order[0].atom.atom_id == "B"


def test_duplicate_emission_is_reported_separately_from_missing() -> None:
    ledger = _source_text_completeness(
        [atom("A", "工程质量达到合格标准")],
        "工程质量达到合格标准工程质量达到合格标准",
    )
    assert ledger.missing_count == 0
    assert len(ledger.multiple_owner) == 1
    assert ledger.multiple_owner[0].text_emission_owner_count == 2


def test_source_own_repetition_is_not_a_duplicate() -> None:
    # The source prints the same label in two cells; delivering both is correct.
    ledger = _source_text_completeness(
        [atom("A", "项目负责人签字盖章", order=0), atom("B", "项目负责人签字盖章", order=1)],
        "项目负责人签字盖章项目负责人签字盖章",
    )
    assert ledger.missing_count == 0
    assert ledger.multiple_owner == []


def test_short_atom_cannot_establish_a_second_owner() -> None:
    # A bare '1' or '年月日' recurs by design and must not be called a duplicate.
    ledger = _source_text_completeness(
        [atom("A", "1")],
        "1 1 1 1 1",
    )
    assert ledger.multiple_owner == []
    assert ledger.missing_count == 0


def test_executed_renderer_value_is_not_counted_as_missing_source_text() -> None:
    # The source line prints a blank; the renderer executed a value into it.  The
    # presence diagnostic removes exactly that executed value from the delivered
    # text, so the source's own wording is found and nothing reads as missing.
    ledger = _source_text_completeness(
        [atom("A", "项目名称为标段")],
        "项目名称为示例项目标段",
        executed_values=["示例项目"],
    )
    assert ledger.missing_count == 0


def test_blank_geometry_is_not_counted_as_missing_text() -> None:
    # A source gap is format, not absent text: an expectation built from the
    # source's own text already carries the gap as whitespace, and the ledger
    # compares compacted text, so the gap can never read as a loss.
    ledger = _source_text_completeness(
        [atom("A", "委托期限：   年   月   日")],
        "委托期限：年月日",
    )
    assert ledger.missing_count == 0


def test_ledger_summary_exposes_the_required_counters() -> None:
    ledger = _source_text_completeness(
        [atom("A", "第一段完整交付的文字内容")], "第一段完整交付的文字内容"
    )
    summary = ledger.as_dict()
    for key in (
        "SOURCE_COMPLETENESS_SCOPE_ATOM_COUNT",
        "EXPECTED_ATOM_COUNT",
        "DELIVERED_ATOM_COUNT",
        "MISSING_ATOM_COUNT",
        "DUPLICATED_ATOM_COUNT",
        "OUT_OF_ORDER_ATOM_COUNT",
        "source_text_atoms_with_zero_owner_count",
        "source_text_atoms_with_multiple_owner_count",
        "source_text_missing_atoms",
    ):
        assert key in summary
    assert summary["EXPECTED_ATOM_COUNT"] == 1
    assert summary["MISSING_ATOM_COUNT"] == 0


# --------------------------------------------------------------------------- #
# Adjacent-rule ownership must not consume source text
# --------------------------------------------------------------------------- #


def test_blank_shaped_slot_may_own_an_adjacent_rule() -> None:
    # slot text starts at 304.92; the rule ends at 304.90 - it is the slot's blank.
    rule = FakeRule("horizontal", (196.90, 138.80, 304.90, 138.80))
    promoted = _own_adjacent_source_rule(
        slot(match_kind="whitespace", geometry=(304.92, 127.14, 520.92, 139.14)),
        paragraph=None,
        lines=[rule],
    )
    assert promoted.match_kind == "underline"
    assert promoted.underline is True
    assert promoted.owned_source_rule is not None
    assert promoted.geometry[:2] == (196.90, 138.80)


def test_date_signature_slot_is_never_promoted_to_a_blank() -> None:
    # The exact CASE003 regression: a date/signature run is source *text*, so an
    # adjacent rule may not reclassify it onto the placeholder-consumption path.
    rule = FakeRule("horizontal", (75.85, 258.97, 91.62, 259.72))
    unchanged = _own_adjacent_source_rule(
        slot(
            match_kind="date_signature",
            geometry=(91.625, 248.11, 491.47, 259.74),
            hint="签字日期",
        ),
        paragraph=None,
        lines=[rule],
    )
    assert unchanged.match_kind == "date_signature"
    assert unchanged.owned_source_rule is None


def test_rule_ownership_is_limited_to_blank_shaped_match_kinds() -> None:
    assert set(RULE_OWNERSHIP_MATCH_KINDS) == {"whitespace", "underline"}
    for match_kind in ("date_signature", "parenthetical", "table_blank"):
        assert match_kind not in RULE_OWNERSHIP_MATCH_KINDS


def test_geometry_evidence_does_not_consume_the_text_it_measures() -> None:
    # The promotion records the rule's span as *presentation* evidence and leaves
    # the slot's own text range untouched.
    rule = FakeRule("horizontal", (196.90, 138.80, 304.90, 138.80))
    original = slot(match_kind="whitespace", geometry=(304.92, 127.14, 520.92, 139.14))
    promoted = _own_adjacent_source_rule(original, paragraph=None, lines=[rule])
    assert promoted.text_start == original.text_start
    assert promoted.text_end == original.text_end


def test_distant_rule_does_not_become_the_slots_blank() -> None:
    far = FakeRule("horizontal", (10.0, 500.0, 40.0, 500.0))
    unchanged = _own_adjacent_source_rule(
        slot(match_kind="whitespace", geometry=(304.92, 127.14, 520.92, 139.14)),
        paragraph=None,
        lines=[far],
    )
    assert unchanged.match_kind == "whitespace"
    assert unchanged.owned_source_rule is None


# --------------------------------------------------------------------------- #
# The second-owner test measures the SOURCE, not the atom list
# --------------------------------------------------------------------------- #


def test_a_phrase_the_source_prints_twice_is_not_a_duplicate() -> None:
    """A repeated source phrase is one atom here and part of a longer atom there.

    Counting *equal atoms* sees the phrase once and would report its second,
    faithful delivery as a second owner.  The source's own text prints it twice,
    so the delivered text may print it twice.
    """

    atoms = [
        atom("A", "规格说明。", order=0),
        atom("B", "详见规格说明。并附检测证明。", order=1),
    ]
    delivered = "规格说明。详见规格说明。并附检测证明。"
    ledger = _source_text_completeness(atoms, delivered, executed_values=())
    assert ledger.missing_count == 0
    assert [record.atom.atom_id for record in ledger.multiple_owner] == []


def test_a_genuine_second_emission_is_still_a_duplicate() -> None:
    """The measurement change must not stop the ledger detecting a real repeat."""

    atoms = [
        atom("A", "独特条款内容甲项", order=0),
        atom("B", "另一段不同的正文内容乙", order=1),
    ]
    delivered = "独特条款内容甲项另一段不同的正文内容乙独特条款内容甲项"
    ledger = _source_text_completeness(atoms, delivered, executed_values=())
    assert ledger.missing_count == 0
    assert [record.atom.atom_id for record in ledger.multiple_owner] == ["A"]
