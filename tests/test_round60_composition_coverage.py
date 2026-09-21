"""Round 6.0 regression: a composition's covered range must name its own glyphs.

A ``SOURCE_RULE_COMPOSITION`` consumes the source characters its TEXT segments
carry and re-emits them positioned.  The rule's covered range is therefore the
*only* thing that removes them from the surrounding text: if that range is
expressed in a different coordinate space than the characters it names, the
consumed characters and the re-emitted ones disagree and the source's own words
are duplicated in the delivered document.

The range and the character evidence are both expressed as an index into the
container text the renderer slices.  A run's own visible-character ordinal
inside that container is *not* that index unless the run begins the container,
so pairing character records with the ordinal makes every atom inherit the
number of visible characters that precede its run.  These tests lock the
container-text coordinate and the paragraph ownership of the re-emitted tail.
"""

from __future__ import annotations

from docx import Document

from tender_basic.page_layout import (
    character_composition_segments,
    inline_rule_composition_token,
    parse_inline_rule_composition_token,
)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class _Character:
    def __init__(self, character, x0, x1, index, kind="EXACT_PDF_CHAR"):
        self.character = character
        self.x0 = x0
        self.x1 = x1
        self.index = index
        self.evidence_kind = kind


class _Run:
    def __init__(self, text, characters, bbox=(85.08, 192.42, 367.08, 204.42)):
        self.text = text
        self.characters = characters
        self.bbox = bbox
        self.font_size = 10.5
        self.origin = None


class _Rule:
    def __init__(self, bbox):
        self.bbox = bbox
        self.orientation = "horizontal"


def _glyphs(text, x0, *, advance=10.0, index_base=0):
    """Character records for ``text``'s visible glyphs, laid out from ``x0``."""

    records = []
    x = x0
    for index, character in enumerate(text):
        if character.isspace():
            continue
        records.append(_Character(character, x, x + advance, index_base + index))
        x += advance
    return records


def _container_paragraph():
    """A paragraph whose run starts part-way into its own container text."""

    text = "本人       （姓名）系        （投标人名称）的法定代表人，现委托        （姓名）为我方代"
    prefix = len("本人")
    run_text = text[prefix:]
    return text, _Run(run_text, _glyphs(run_text, 24.0, advance=10.0)), prefix


def _segments_text(segments):
    return "".join(
        segment["source_text"] or ""
        for segment in segments
        if segment["segment_type"] == "TEXT_RULE_SEGMENT"
    )


def test_covered_range_is_the_container_text_index_of_the_glyphs_it_names():
    """A run that does not begin the container still reports container indices."""

    text, run, prefix = _container_paragraph()
    run_x0 = float(run.characters[0].x0)
    # The glyph ordinal of the first ``（姓名）`` inside the run, which is the
    # order the character records are laid out in.
    in_run = run.text.index("（姓名）")
    glyph = sum(1 for character in run.text[:in_run] if not character.isspace())
    # The rule covers exactly those four glyphs: it opens where the first starts
    # and closes where the last one ends.
    rule = _Rule(
        (
            run_x0 + glyph * 10.0,
            204.2,
            run_x0 + (glyph + 4) * 10.0,
            204.2,
        )
    )

    composition = character_composition_segments(
        rule, [(run, 0, len(run.text))], self_offsets={id(run): prefix}
    )
    assert composition is not None
    segments, start, end = composition[0], composition[1], composition[2]
    assert _segments_text(segments) == "（姓名）"
    # The covered range is a container text index, so the run's offset inside the
    # container shifts it away from the run's own character indices.
    assert start >= prefix
    assert len(_segments_text(segments)) <= end - start


def test_a_run_shortened_by_the_container_offset_moves_the_covered_range():
    """The run's own character index is not the container text index."""

    text, run, prefix = _container_paragraph()
    in_run = run.text.index("（姓名）")
    glyph = sum(1 for character in run.text[:in_run] if not character.isspace())
    run_x0 = float(run.characters[0].x0)
    rule = _Rule(
        (
            run_x0 + glyph * 10.0,
            204.2,
            run_x0 + (glyph + 4) * 10.0,
            204.2,
        )
    )

    with_container = character_composition_segments(
        rule, [(run, 0, len(run.text))], self_offsets={id(run): prefix}
    )
    without_container = character_composition_segments(
        rule, [(run, 0, len(run.text))], self_offsets={id(run): 0}
    )
    assert with_container is not None and without_container is not None
    assert with_container[1] == without_container[1] + prefix


def test_covered_range_is_contiguous_and_lies_in_the_container_text():
    """The covered range names real container characters, never past its end."""

    text, run, prefix = _container_paragraph()
    run_x0 = float(run.characters[0].x0)
    visible = sum(1 for character in run.text if not character.isspace())
    for start_glyph, length in ((0, 4), (5, 7), (visible - 6, 4)):
        rule = _Rule(
            (
                run_x0 + start_glyph * 10.0,
                204.2,
                run_x0 + (start_glyph + length) * 10.0,
                204.2,
            )
        )
        composition = character_composition_segments(
            rule, [(run, 0, len(run.text))], self_offsets={id(run): prefix}
        )
        if composition is None:
            continue
        segments, covered_start, covered_end = (
            composition[0], composition[1], composition[2]
        )
        assert 0 <= covered_start < covered_end <= len(text)
        # The range carries the segments' own characters, which is what the
        # emitter's slice replaces and re-emits positioned.
        emitted = _segments_text(segments)
        assert emitted
        assert len(emitted) * 2 >= covered_end - covered_start


def test_re_emitted_tail_stays_in_the_compositions_own_paragraph():
    """The rule's own characters exist once in the paragraph it owns."""

    document = Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("系")
    paragraph.add_run("\t")
    paragraph.add_run("（投标人名称）")
    paragraph.add_run("                       （投标人名称）的法定代表人。 ")
    # The rule's tab and its re-emitted characters live in the one paragraph the
    # composition owns, in source order.
    assert [run.text for run in paragraph.runs] == [
        "系",
        "\t",
        "（投标人名称）",
        "                       （投标人名称）的法定代表人。 ",
    ]
    assert paragraph.text.count("（投标人名称）") == 2
    assert paragraph.text.startswith("系\t（投标人名称）")


def test_restore_replaces_the_rule_characters_with_one_token():
    """Restoring a composition leaves every character outside the rule alone."""

    text = "系                              （投标人名称）的法定代表人。 "
    start = text.index("（投标人名称）")
    segments = [
        {
            "segment_type": "EMPTY_RULE_SEGMENT",
            "source_text": None,
            "source_x0": 86.35,
            "source_x1": 244.08,
        },
        {
            "segment_type": "TEXT_RULE_SEGMENT",
            "source_text": "（投标人名称）",
            "source_x0": 244.08,
            "source_x1": 317.65,
        },
    ]
    token = inline_rule_composition_token("R", segments)
    restored = text[:start] + token + text[start + len("（投标人名称）"):]
    assert restored.count("\ue002") == 1
    parsed = parse_inline_rule_composition_token(
        restored[restored.index("\ue002") + 1:restored.index("\ue003")]
    )
    assert parsed is not None
    assert parsed[1][1]["source_text"] == "（投标人名称）"
    before, after = restored[:restored.index("\ue002")], restored[restored.index("\ue003") + 1:]
    assert before + "（投标人名称）" + after == (
        "系                              （投标人名称）的法定代表人。 "
    )
