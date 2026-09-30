"""Round-9 evidence-unit locator contract: parser locality and exact comparison.

The round-9 acceptance rule is

    canonical EvidenceUnit
    -> deterministic production locator formatter
    -> expected visible locator
    -> SAVED/REOPENED XLSX
    -> EXACT equality

and it was almost lost twice: a ``unit_heading.startswith(section)`` tolerance was
tried and rejected as gate weakening, and the clause parser was reading a
``第…条`` phrase that appears *later* in unrelated trailing text instead of the
unit's own structural position.

These tests pin both halves with a synthetic document (no PDF is parsed), so they
run in the ordinary suite:

* the clause/section a unit is keyed by comes from the unit's **own** leading
  structural token -- numeric clauses (``3.4.2``), Chinese section labels
  (``五、`` / ``十五、``) and article titles (``第三条``) -- and a later
  ``第…条`` elsewhere in the text is never promoted to the unit's clause;
* a sentence may not become a carried heading, and a heading may not travel into
  a unit of another clause family;
* the locator formatter is single-source, and its comparison is equality -- a
  prefix, substring, ``startswith`` or fuzzy variant of the expected locator is
  rejected.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tender_basic.evidence_unit import (  # noqa: E402
    KIND_BLOCK,
    build_evidence_units,
    expected_locator_for_unit,
    format_locator_section_for_display,
    locators_match_exactly,
    printable_clause_label,
    _article_heading,
    _clause_of,
    _is_heading,
    _locator_text,
)


def _block(text: str, index: int = 0) -> Any:
    return SimpleNamespace(
        text=text,
        block_index=index,
        bbox=(0.0, 0.0, 100.0, 20.0),
        locator=SimpleNamespace(locator_type=KIND_BLOCK),
        lines=(),
    )


def _page(number: int, texts: Sequence[str]) -> Any:
    return SimpleNamespace(
        page_number=number,
        blocks=tuple(_block(text, index) for index, text in enumerate(texts)),
    )


def _units(*pages: Any) -> list[Any]:
    document = SimpleNamespace(pages=tuple(pages), tables=())
    return build_evidence_units(document)


# -- the unit's own structural token ----------------------------------------- #


def test_numeric_clause_comes_from_the_units_own_leading_token() -> None:
    units = _units(
        _page(
            18,
            [
                "3.4.2 供应商不按本章第3.4.1项要求提交响应保证金的，评审小组将否决其响应",
            ],
        )
    )
    assert units[0].clause_number == "3.4.2"
    assert "3.4.1" not in units[0].clause_number


def test_numeric_clause_is_read_for_every_nested_form() -> None:
    units = _units(_page(1, ["7.3.1 成交供应商不能按本章第7.3项要求提交履约保证金的。"]))
    assert units[0].clause_number == "7.3.1"


def test_later_article_phrase_is_never_promoted_to_the_clause() -> None:
    """The parser reads the local structural position, not the first 第…条."""

    text = "供应商应遵守第三条验收方法及技术要求，并不得违反第七条规定。"
    assert _clause_of(text) == ""
    units = _units(_page(5, [text]))
    assert units[0].clause_number == ""
    locator, section, clause, source, _clip = expected_locator_for_unit(
        units[0], units[0].text_span
    )
    # the only handle the source offers is the unit's own opening words; no clause
    # number is invented out of 第三条 / 第七条, and no token is picked from the
    # middle of the string
    assert clause == ""
    assert source == "opening_handle"
    assert section.startswith("供应商应遵守第三条验收方法及技术要求")
    assert locator == f"第5页 / {section} / （pdf_block）"
    # no clause slot is printed at all: 第三条 / 第七条 stayed part of the sentence
    assert re.search(r"第[\d.]+条 / （pdf_block）$", locator) is None


def test_the_locally_leading_token_wins_over_a_later_one() -> None:
    text = "3.4.2 供应商不按本章第3.4.1项要求提交响应保证金的，评审小组将否决其响应"
    assert _clause_of(text) == "3.4.2"
    units = _units(_page(18, [text]))
    locator, _section, clause, _source, _clip = expected_locator_for_unit(
        units[0], units[0].text_span
    )
    assert clause == "3.4.2"
    assert locator.endswith("第3.4.2条 / （pdf_block）")


def test_article_title_is_a_section_never_a_clause() -> None:
    assert _article_heading("第三条验收方法及技术要求")
    assert _clause_of("第三条验收方法及技术要求") == ""
    assert printable_clause_label("第三条") == ""


def test_chinese_section_label_is_never_printed_as_a_clause() -> None:
    assert printable_clause_label("五、质量要求") == ""
    assert printable_clause_label("十五、其他资料") == ""
    assert printable_clause_label("（4）") == ""
    assert printable_clause_label("3.4.2") == "3.4.2"


def test_chinese_section_label_governs_its_own_units_without_a_clause() -> None:
    units = _units(
        _page(
            7,
            [
                "五、质量要求",
                "设备应符合国家标准。",
                "十五、其他资料",
                "供应商应提交下列资料。",
            ],
        )
    )
    assert [unit.clause_number for unit in units] == ["", "", "", ""]
    assert units[0].heading == "五、质量要求"
    assert units[1].heading == "五、质量要求"
    assert units[2].heading == "十五、其他资料"
    assert units[3].heading == "十五、其他资料"


# -- headings ----------------------------------------------------------------- #


def test_a_sentence_body_is_not_a_heading() -> None:
    """The extraction emits clause *bodies* as blocks; they must not title rows."""

    sentence = "3.4.1招标人在投标人须知前附表中要求投标人提交投标保证金的，"
    assert not _is_heading(sentence)
    units = _units(_page(31, [sentence, "未按要求提交的，其投标将被否决。"]))
    assert [unit.heading for unit in units] == ["", ""]


def test_a_heading_does_not_travel_into_another_clause_family() -> None:
    units = _units(
        _page(
            33,
            [
                "3.1 供应商提供设备应遵照下列要求",
                "5.2 设备单价中含安装调试费用，不另计。",
            ],
        )
    )
    assert units[0].heading == "3.1 供应商提供设备应遵照下列要求"
    assert units[1].clause_number == "5.2"
    assert units[1].heading == ""


# -- the locator formatter is single-source ----------------------------------- #


def test_expected_locator_is_the_one_production_formatter() -> None:
    units = _units(_page(10, ["3.3 响应保证金"]))
    unit = units[0]
    locator, section, clause, source, clip = expected_locator_for_unit(
        unit, unit.text_span
    )
    assert source == "unit.heading"
    assert clip is None
    assert locator == _locator_text(unit.page, section, clause, unit.kind)
    assert locator == unit.locator
    assert locator == "第10页 / 3.3 响应保证金 / 第3.3条 / （pdf_block）"


def test_no_heading_unit_uses_its_own_numbered_item_and_blanks_the_clause() -> None:
    units = _units(_page(12, ["5、最高限价：3100000 元（不含税）"]))
    unit = units[0]
    locator, section, clause, source, clip = expected_locator_for_unit(
        unit, unit.text_span
    )
    assert source == "numbered_item"
    assert clip == 40
    assert clause == ""
    assert section.startswith("5、最高限价")
    assert "第5条" not in locator


def test_section_formatter_is_the_only_visible_transformation() -> None:
    assert format_locator_section_for_display("  3.3.1 响应保证金  ") == "3.3.1 响应保证金"
    assert _locator_text(3, "3.3.1 响应保证金", "3.3.1", KIND_BLOCK) == (
        "第3页 / 3.3.1 响应保证金 / 第3.3.1条 / （pdf_block）"
    )


# -- the comparison is exact -------------------------------------------------- #


def test_locator_comparison_accepts_only_exact_equality() -> None:
    expected = "第10页 / 供应商须知前附表 / 第3.3.1条 / （pdf_table_cell）"
    assert locators_match_exactly(expected, expected)
    # a prefix, a substring, a startswith variant and a fuzzy variant are all
    # different locators
    assert not locators_match_exactly(expected, "第10页 / 供应商须知前附表")
    assert not locators_match_exactly(expected, expected[:20])
    assert not locators_match_exactly("供应商须知前附表", expected)
    assert not locators_match_exactly(expected, expected.replace("第10页", "第1页"))
    assert not locators_match_exactly(expected, expected + " 附注")


def test_the_corrected_clause_section_parser_is_local_not_greedy() -> None:
    """A regression guard for the rejected ``unit_heading.startswith(...)`` shape.

    The round-9 audit must use the production comparer and must not reintroduce a
    prefix/fuzzy tolerance for a clipped locator section.
    """

    source = (ROOT / "scripts/v1_review_workbook_round9_report.py").read_text(
        encoding="utf-8"
    )
    assert "locators_match_exactly" in source
    assert "expected_locator_for_unit" in source
    assert "unit_heading.startswith" not in source
    assert "startswith(section" not in source
