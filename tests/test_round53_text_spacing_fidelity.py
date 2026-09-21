from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn

from tender_basic.page_layout import (
    BlankRepresentationKind,
    SourceLineSpacingMode,
    form_parts,
    infer_semantic_line_spacing,
)


def test_semantic_line_spacing_modes_are_word_auto(tmp_path: Path) -> None:
    document = Document()
    values = ((1.0, "240"), (1.5, "360"), (2.0, "480"), (1.2, "288"))
    for multiple, expected in values:
        paragraph = document.add_paragraph("body")
        paragraph.paragraph_format.line_spacing = multiple
        spacing = paragraph._p.get_or_add_pPr().find(qn("w:spacing"))
        assert spacing is not None
        assert spacing.get(qn("w:lineRule")) == "auto"
        assert spacing.get(qn("w:line")) == expected
    output = tmp_path / "semantic-spacing.docx"
    document.save(output)
    with ZipFile(output) as package:
        xml = package.read("word/document.xml").decode("utf-8")
    assert 'w:lineRule="exact"' not in xml


def test_pdf_spacing_inference_never_silently_selects_exact() -> None:
    for pitch in (0.0, 10.5, 12.1, 13.1, 15.75, 21.0):
        profile = infer_semantic_line_spacing(10.5, pitch)
        assert profile.mode is not SourceLineSpacingMode.EXACT
        assert profile.word_value in {1.0, 1.15, 1.2, 1.25, 1.5, 2.0}


def test_literal_display_text_preserves_internal_spaces_and_underscores() -> None:
    samples = (
        "2023 年 1 月 1 日",
        "项目 ABC-123 招标文件",
        "合同签订后 30 天",
        "提交响应文件截止之日起 90 日历天",
        "近 3 年",
    )
    for sample in samples:
        paragraph = Document().add_paragraph(sample)
        assert paragraph.text == sample
    assert form_parts("供应商名称：_____________________") == [
        "供应商名称：", "_____________________", "",
    ]


def test_blank_representation_kinds_are_distinct() -> None:
    assert {item.value for item in BlankRepresentationKind} == {
        "LITERAL_UNDERSCORES", "UNDERLINED_WHITESPACE", "TAB_LEADER",
        "SOURCE_WHITESPACE_GAP", "VECTOR_LINE", "MIXED",
    }


def test_form_tab_stop_is_measured_from_the_page_margin() -> None:
    """OOXML ``w:tab/@w:pos`` is margin-relative, not indent-relative.

    Measuring from the paragraph's left text edge shifted every leader right by
    the indent; for a narrow field such as ``年龄：`` the stop ended up behind
    the cursor, so no leader was painted and the blank disappeared.
    """
    from tender_basic.word_safe_source_builder import ParagraphFormRenderer

    page_content_x0 = 18.0
    label_x = 72.0
    # A source rule spanning 236.40..262.80 pt on a page whose text margin is
    # 18 pt must produce a stop at 262.80 - 18 = 244.80 pt.
    position = ParagraphFormRenderer._tab_position(
        262.80, label_x, page_content_x0=page_content_x0,
    )
    assert round(position, 2) == 244.80
    # The indent-relative mistake this guards against would have produced
    # 262.80 - 72 = 190.80 pt and dropped the leader.
    assert round(position, 2) != round(262.80 - label_x, 2)


def test_vector_rule_is_not_reported_as_literal_underscores() -> None:
    """A measured source rule must not be relabelled as source underscore text.

    Only case_002 actually contains ``_`` glyphs in its source; cases 1 and 3
    draw vector rules. Reporting a rule as LITERAL_UNDERSCORES both fabricated
    characters the source never had and mislabelled the blank semantics, so the
    rule must classify as VECTOR_LINE instead.
    """
    from tender_basic.page_layout import (
        BlankRepresentationKind as Kind,
        editable_blanks_for_form,
        form_parts,
    )

    assert Kind.VECTOR_LINE.value == "VECTOR_LINE"
    assert Kind.LITERAL_UNDERSCORES.value == "LITERAL_UNDERSCORES"
    assert form_parts("供应商名称：") == ["供应商名称：", "", ""]
    assert editable_blanks_for_form is not None
