"""Architecture tests for the Word render-authority classifier.

The classifier is the piece that decides whether a headless-render divergence is a
delivery defect or a proven font substitution.  These tests exercise it with
measured-style evidence, including the negative controls the fidelity round
requires: a wrong requested font, a wrong frame, insufficient evidence, and a
substitution whose prediction does not explain the observation.
"""

from __future__ import annotations

import pytest

from tender_basic.word_render_authority import (
    DOCX_TYPOGRAPHY_MISMATCH,
    HEADLESS_FONT_SUBSTITUTION_ONLY,
    HOST_FONT_ABSENT,
    HOST_FONT_INSTALLED,
    SOURCE_FONT_METRIC_DIFFERENCE,
    TRUE_LAYOUT_GEOMETRY_DEFECT,
    UNKNOWN_RENDER_DIVERGENCE,
    SourceFidelityProofs,
    SourceRowMeasurement,
    SourceTypographyEvidence,
    classify_renderer_divergence,
    families_are_same,
)


def _proven() -> SourceFidelityProofs:
    return SourceFidelityProofs(
        docx_geometry_matches_source=True,
        row_ownership_correct=True,
        text_complete_and_ordered=True,
        source_slots_preserved=True,
        no_true_geometry_defect=True,
    )


def _case002_typography(**overrides) -> SourceTypographyEvidence:
    """The measured CASE002 authorization typography, as evidence."""

    values = dict(
        source_family="FangSong_GB2312",
        source_size_pt=12.0,
        docx_east_asia="仿宋",
        docx_ascii="仿宋",
        docx_hansi="仿宋",
        docx_size_pt=12.0,
        docx_character_spacing_twips=None,
        host_font_state=HOST_FONT_ABSENT,
        headless_family="FangSong",
        headless_size_pt=12.0,
    )
    values.update(overrides)
    return SourceTypographyEvidence(**values)


def _case002_row(**overrides) -> SourceRowMeasurement:
    """The measured CASE002 authorization row, as evidence."""

    values = dict(
        row_id="S149-L3",
        source_char_count=36,
        source_used_width_pt=426.36,
        source_available_width_pt=426.36,
        headless_char_count=35,
        headless_used_width_pt=420.0,
    )
    values.update(overrides)
    return SourceRowMeasurement(**values)


def test_family_aliases_match_source_subset_and_requested_name():
    # The source embeds a subset of the GB2312 font; the DOCX requests the modern
    # family name.  They are the same typeface lineage.
    assert families_are_same("FangSong_GB2312", "仿宋")
    assert families_are_same("NREKVL+FangSong_GB2312", "FangSong")
    assert families_are_same("TimesNewRomanPSMT", "Times New Roman")
    assert not families_are_same("仿宋", "黑体")


def test_docx_typography_matches_source_when_family_and_size_agree():
    assert _case002_typography().docx_matches_source is True


def test_character_spacing_override_is_not_a_typography_match():
    # Compensating for a renderer with w:spacing is distortion, not fidelity.
    assert _case002_typography(docx_character_spacing_twips=-8).docx_matches_source is False


def test_typography_size_mismatch_is_not_a_match():
    assert _case002_typography(docx_size_pt=10.5).docx_matches_source is False


def test_substitution_is_proven_only_when_host_lacks_the_font():
    assert _case002_typography().substitution_proven is True
    assert (
        _case002_typography(host_font_state=HOST_FONT_INSTALLED).substitution_proven
        is False
    )


def test_rendering_with_the_requested_family_name_still_substitutes_when_absent():
    # LibreOffice reports the family it resolved to, which can carry the requested
    # name while being a different font *file*.  The proof is the host: when the
    # requested family is not installed, what was rendered cannot be that font.
    evidence = _case002_typography(headless_family="仿宋")
    assert evidence.resolved_family_is_requested is True
    assert evidence.substitution_proven is True

    # With the font actually installed and that family rendered, there is no
    # substitution - the divergence is then a source-vs-installed metric property.
    installed = _case002_typography(
        headless_family="仿宋", host_font_state=HOST_FONT_INSTALLED
    )
    assert installed.substitution_proven is False


def test_advance_ratio_and_prediction_are_derived_from_measurements():
    row = _case002_row()
    assert row.source_per_char_pt == pytest.approx(426.36 / 36, rel=1e-9)
    assert row.headless_per_char_pt == pytest.approx(12.0, rel=1e-9)
    assert row.advance_ratio == pytest.approx(1.0132, rel=1e-3)
    # 36 source characters at the rendered advance overflow the source row end.
    assert row.predicted_overflow_pt() > 0.0
    assert row.source_fill_ratio == pytest.approx(1.0, rel=1e-9)


def test_control_a_correct_source_and_docx_with_proven_substitution_is_non_blocking():
    result = classify_renderer_divergence(
        typography=_case002_typography(), row=_case002_row(), proofs=_proven()
    )
    assert result.divergence_class == HEADLESS_FONT_SUBSTITUTION_ONLY
    assert result.blocking is False
    assert result.is_substitution_only is True


def test_control_b_wrong_docx_font_is_a_typography_mismatch():
    result = classify_renderer_divergence(
        typography=_case002_typography(docx_east_asia="黑体"),
        row=_case002_row(),
        proofs=_proven(),
    )
    assert result.divergence_class == DOCX_TYPOGRAPHY_MISMATCH
    assert result.blocking is True


def test_control_c_correct_font_but_wrong_geometry_is_a_true_defect():
    proofs = _proven()
    proofs.docx_geometry_matches_source = False
    result = classify_renderer_divergence(
        typography=_case002_typography(), row=_case002_row(), proofs=proofs
    )
    assert result.divergence_class == TRUE_LAYOUT_GEOMETRY_DEFECT
    assert result.blocking is True


def test_control_d_insufficient_evidence_is_unknown_and_blocking():
    proofs = _proven()
    proofs.text_complete_and_ordered = None
    proofs.notes.append("text completeness not measured")
    result = classify_renderer_divergence(
        typography=_case002_typography(), row=_case002_row(), proofs=proofs
    )
    assert result.divergence_class == UNKNOWN_RENDER_DIVERGENCE
    assert result.blocking is True


def test_control_e_prediction_that_does_not_explain_the_overflow_is_not_excused():
    # A row whose observed shortfall is far larger than the substitute advance can
    # account for must not be waved through as substitution.
    row = _case002_row(headless_used_width_pt=300.0, headless_char_count=25)
    result = classify_renderer_divergence(
        typography=_case002_typography(), row=row, proofs=_proven()
    )
    assert result.divergence_class == UNKNOWN_RENDER_DIVERGENCE
    assert result.blocking is True


def test_substitution_without_any_predicted_overflow_is_unknown():
    row = _case002_row(source_char_count=10, source_used_width_pt=120.0)
    result = classify_renderer_divergence(
        typography=_case002_typography(), row=row, proofs=_proven()
    )
    assert result.divergence_class == UNKNOWN_RENDER_DIVERGENCE
    assert result.blocking is True


def test_requested_family_rendered_with_different_advance_is_a_source_font_metric_difference():
    result = classify_renderer_divergence(
        typography=_case002_typography(
            headless_family="仿宋", host_font_state=HOST_FONT_INSTALLED
        ),
        row=_case002_row(),
        proofs=_proven(),
    )
    assert result.divergence_class == SOURCE_FONT_METRIC_DIFFERENCE
    assert result.blocking is True


def test_incomplete_typography_evidence_is_unknown():
    result = classify_renderer_divergence(
        typography=SourceTypographyEvidence(),
        row=_case002_row(),
        proofs=_proven(),
    )
    assert result.divergence_class == UNKNOWN_RENDER_DIVERGENCE
    assert result.blocking is True


def test_classification_persists_the_measured_evidence():
    result = classify_renderer_divergence(
        typography=_case002_typography(), row=_case002_row(), proofs=_proven()
    )
    assert result.evidence["advance_ratio"] == pytest.approx(1.0132, rel=1e-3)
    assert result.evidence["prediction_residual_pt"] >= 0.0
    assert result.reasons
    assert "divergence_class" in result.as_dict()
