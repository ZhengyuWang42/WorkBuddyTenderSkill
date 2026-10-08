"""Word source-fidelity render authority: three evidence layers, one classifier.

A delivered Word artifact is judged through three *separate* layers, and the
headless renderer is never allowed to silently redefine either of the first two:

``SOURCE``
    the tender PDF's own glyph boxes, rule extents and row geometry.  This is the
    authority for what the document must look like.

``DOCX``
    the intended Microsoft Word typography and geometry the builder emits.  This
    is the authority for what Word will actually lay out; it is a deliverable in
    its own right, not a means of pleasing a particular renderer.

``HEADLESS``
    a LibreOffice render used as *diagnostic* evidence.  The frozen repository
    decision ``docs/V1_DECISIONS.md`` W9 states that static checks and
    LibreOffice rendering cannot replace opening the deliverable in desktop
    Microsoft Word, and ``docs/V1_PROJECT_STATE.md`` §7 already banks CJK
    fallback-font metric drift as a known non-defect (§7.3, ``FONT_METRIC_ONLY``).

Because the headless layer is diagnostic, a divergence between it and the DOCX is
not automatically a defect - but it is never *assumed* to be harmless either.  It
is classified from evidence, and the only non-blocking class
(``HEADLESS_FONT_SUBSTITUTION_ONLY``) requires every one of the proofs below.  An
unclassifiable divergence is ``UNKNOWN_RENDER_DIVERGENCE``, which is a blocker.

Nothing here is case-, page- or text-specific: the classifier reads only measured
geometry and typography evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Authority roles (frozen contract)
# --------------------------------------------------------------------------- #

SOURCE_GEOMETRY_AUTHORITY = "AUTHORITATIVE_FOR_SOURCE_AND_DOCX_FIDELITY"

DOCX_TYPOGRAPHY_AUTHORITY = "AUTHORITATIVE_INTENDED_WORD_TYPOGRAPHY"

#: The headless renderer is evidence, never the truth the DOCX must imitate.
HEADLESS_RENDERER_ROLE = "DIAGNOSTIC"

#: The final Word authority is a person opening the artifact in Word.
WORD_DESKTOP_ROLE = "FINAL_WORD_DELIVERY_AUTHORITY"

#: Whether the intended font is installed on the build host decides whether a
#: rendered family change is *substitution* at all.
HOST_FONT_INSTALLED = "INSTALLED"
HOST_FONT_ABSENT = "ABSENT"
HOST_FONT_UNKNOWN = "UNKNOWN"

# --------------------------------------------------------------------------- #
# Divergence classes
# --------------------------------------------------------------------------- #

#: The DOCX asks for the wrong family/size for this source text.
DOCX_TYPOGRAPHY_MISMATCH = "DOCX_TYPOGRAPHY_MISMATCH"

#: The DOCX typography is right but the delivered geometry does not reproduce the
#: source's own frame/indent/row extents.
TRUE_LAYOUT_GEOMETRY_DEFECT = "TRUE_LAYOUT_GEOMETRY_DEFECT"

#: The DOCX is source-faithful and the rendered difference is explained by a
#: proven font substitution whose measured advance predicts the observation.
HEADLESS_FONT_SUBSTITUTION_ONLY = "HEADLESS_FONT_SUBSTITUTION_ONLY"

#: The rendered font *is* the requested font, yet advances differ from the
#: source's embedded subset: a metric property of the fonts, not of the DOCX.
SOURCE_FONT_METRIC_DIFFERENCE = "SOURCE_FONT_METRIC_DIFFERENCE"

#: Not classifiable from the available evidence.  A blocker, by policy.
UNKNOWN_RENDER_DIVERGENCE = "UNKNOWN_RENDER_DIVERGENCE"

DIVERGENCE_CLASSES = (
    DOCX_TYPOGRAPHY_MISMATCH,
    TRUE_LAYOUT_GEOMETRY_DEFECT,
    HEADLESS_FONT_SUBSTITUTION_ONLY,
    SOURCE_FONT_METRIC_DIFFERENCE,
    UNKNOWN_RENDER_DIVERGENCE,
)

#: Only this class may be reported as a warning instead of a failure.
NON_BLOCKING_DIVERGENCE_CLASSES = (HEADLESS_FONT_SUBSTITUTION_ONLY,)

#: A family name is the same family when its normalized forms agree.  The source
#: embeds ``FangSong_GB2312`` while a document normally requests ``仿宋``; the two
#: name the same typeface lineage, and the size is the real discriminator.
FAMILY_ALIASES = {
    "fangsong": ("fangsong", "仿宋", "fangsong_gb2312", "仿宋_gb2312"),
    "simsun": ("simsun", "宋体", "songti", "nsimsun"),
    "simhei": ("simhei", "黑体", "heiti"),
    "kaiti": ("kaiti", "楷体", "kai_ti"),
    "timesnewroman": ("timesnewroman", "times new roman", "timesnewromanpsmt"),
}

#: Typeface size must agree this closely, in points.
TYPOGRAPHY_SIZE_TOLERANCE_PT = 0.5

#: How close the predicted overflow must be to the observed overflow.  The
#: prediction is a per-character average applied to a whole row, so the band is a
#: fraction of one glyph advance rather than an absolute constant.
PREDICTION_RESIDUAL_GLYPH_FRACTION = 0.5


def _normalize_family(name: str | None) -> str:
    """Normalize a font family name for comparison, without guessing new ones."""

    if not name:
        return ""
    compact = "".join(str(name).split()).lower().replace("-", "_")
    for canonical, aliases in FAMILY_ALIASES.items():
        for alias in aliases:
            if compact == "".join(alias.split()).lower().replace("-", "_"):
                return canonical
    # A subset prefix such as ``NREKVL+FangSong_GB2312`` names the same family.
    if "+" in compact:
        compact = compact.split("+", 1)[1]
    for canonical, aliases in FAMILY_ALIASES.items():
        for alias in aliases:
            if "".join(alias.split()).lower().replace("-", "_") in compact:
                return canonical
    return compact


def families_are_same(left: str | None, right: str | None) -> bool:
    """Whether two font names name the same typeface family."""

    first, second = _normalize_family(left), _normalize_family(right)
    return bool(first) and first == second


@dataclass
class SourceTypographyEvidence:
    """The typography of one row as three separate measurements.

    ``source_*`` comes from the tender PDF, ``docx_*`` from the delivered OOXML,
    and ``headless_*`` from the render.  Keeping them apart is the point: a
    mismatch must be attributable to a named layer.
    """

    source_family: str | None = None
    source_size_pt: float | None = None
    docx_east_asia: str | None = None
    docx_ascii: str | None = None
    docx_hansi: str | None = None
    docx_cs: str | None = None
    docx_size_pt: float | None = None
    docx_character_spacing_twips: int | None = None
    host_font_state: str = HOST_FONT_UNKNOWN
    headless_family: str | None = None
    headless_size_pt: float | None = None

    @property
    def docx_requested_family(self) -> str | None:
        """The family the DOCX actually asks Word for."""

        for candidate in (self.docx_east_asia, self.docx_hansi, self.docx_ascii, self.docx_cs):
            if candidate:
                return candidate
        return None

    @property
    def evidence_complete(self) -> bool:
        """Whether both the source and the DOCX typography were actually read."""

        return bool(
            self.source_family
            and self.source_size_pt
            and self.docx_requested_family
            and self.docx_size_pt
        )

    @property
    def docx_matches_source(self) -> bool:
        """Whether the intended DOCX typography reproduces the source's.

        The family must name the same typeface and the size must agree.  A
        character-spacing override is *not* accepted as a typography match: it
        would mean the document is compensating for a renderer rather than
        stating the source's typography.
        """

        if not self.evidence_complete:
            return False
        if self.docx_character_spacing_twips not in (None, 0):
            return False
        if not families_are_same(self.source_family, self.docx_requested_family):
            return False
        return (
            abs(float(self.docx_size_pt) - float(self.source_size_pt))
            <= TYPOGRAPHY_SIZE_TOLERANCE_PT
        )

    @property
    def substitution_proven(self) -> bool:
        """Whether the render used a *different font file* than the DOCX asked for.

        A renderer's reported family name cannot prove this on its own: LibreOffice
        resolves an unavailable family to its own bundled font and still reports the
        requested family name (``仿宋`` renders as ``FangSong``).  What does prove it
        is the host: when the requested family is **not installed** on the build
        host, whatever was rendered cannot be the requested font file, so a
        substitution necessarily happened.  A render on a host that *does* provide
        the font is not substitution, whatever its metrics do.
        """

        if not self.docx_requested_family or not self.headless_family:
            return False
        return self.host_font_state == HOST_FONT_ABSENT

    @property
    def resolved_family_is_requested(self) -> bool:
        """Whether the render used the family the DOCX asked for."""

        return bool(
            self.docx_requested_family
            and self.headless_family
            and families_are_same(self.docx_requested_family, self.headless_family)
        )


@dataclass
class SourceRowMeasurement:
    """One source visual row's own geometry, and what the render did with it."""

    row_id: str = ""
    available_width_pt: float | None = None
    source_char_count: int | None = None
    source_used_width_pt: float | None = None
    headless_char_count: int | None = None
    headless_used_width_pt: float | None = None
    source_available_width_pt: float | None = None
    headless_available_width_pt: float | None = None

    @property
    def source_fill_ratio(self) -> float | None:
        if not self.source_available_width_pt or self.source_used_width_pt is None:
            return None
        return float(self.source_used_width_pt) / float(self.source_available_width_pt)

    @property
    def source_per_char_pt(self) -> float | None:
        if not self.source_char_count or self.source_used_width_pt is None:
            return None
        return float(self.source_used_width_pt) / float(self.source_char_count)

    @property
    def headless_per_char_pt(self) -> float | None:
        if not self.headless_char_count or self.headless_used_width_pt is None:
            return None
        return float(self.headless_used_width_pt) / float(self.headless_char_count)

    @property
    def advance_ratio(self) -> float | None:
        """How much wider (or narrower) the rendered glyph advance is."""

        source_per_char = self.source_per_char_pt
        headless_per_char = self.headless_per_char_pt
        if not source_per_char or not headless_per_char:
            return None
        return headless_per_char / source_per_char

    def predicted_headless_width_pt(self) -> float | None:
        """The source row's own character count at the rendered advance."""

        headless_per_char = self.headless_per_char_pt
        if not headless_per_char or not self.source_char_count:
            return None
        return float(self.source_char_count) * headless_per_char

    def predicted_overflow_pt(self) -> float | None:
        """How far the predicted rendered row exceeds the source's own row end."""

        predicted = self.predicted_headless_width_pt()
        if predicted is None or self.source_used_width_pt is None:
            return None
        return predicted - float(self.source_used_width_pt)

    def observed_overflow_pt(self) -> float | None:
        """How far the observed rendered row falls short of the source row.

        The rendered row keeps only the characters that still fit, so the shortfall
        against the source's own used width *is* the overflow that had to move.
        """

        if self.headless_used_width_pt is None or self.source_used_width_pt is None:
            return None
        return float(self.source_used_width_pt) - float(self.headless_used_width_pt)


@dataclass
class SourceFidelityProofs:
    """The non-typography facts the substitution-only class additionally needs."""

    docx_geometry_matches_source: bool | None = None
    row_ownership_correct: bool | None = None
    text_complete_and_ordered: bool | None = None
    source_slots_preserved: bool | None = None
    no_true_geometry_defect: bool | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def all_proven(self) -> bool:
        return all(
            value is True
            for value in (
                self.docx_geometry_matches_source,
                self.row_ownership_correct,
                self.text_complete_and_ordered,
                self.source_slots_preserved,
                self.no_true_geometry_defect,
            )
        )

    @property
    def any_unavailable(self) -> bool:
        return any(
            value is None
            for value in (
                self.docx_geometry_matches_source,
                self.row_ownership_correct,
                self.text_complete_and_ordered,
                self.source_slots_preserved,
                self.no_true_geometry_defect,
            )
        )


@dataclass
class RendererDivergenceClassification:
    """One classified divergence, with the evidence that produced it."""

    divergence_class: str
    blocking: bool
    reasons: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    @property
    def is_substitution_only(self) -> bool:
        return self.divergence_class == HEADLESS_FONT_SUBSTITUTION_ONLY

    def as_dict(self) -> dict:
        return {
            "divergence_class": self.divergence_class,
            "blocking": self.blocking,
            "reasons": list(self.reasons),
            "evidence": dict(self.evidence),
        }


def _blocking(divergence_class: str) -> bool:
    return divergence_class not in NON_BLOCKING_DIVERGENCE_CLASSES


def classify_renderer_divergence(
    *,
    typography: SourceTypographyEvidence,
    row: SourceRowMeasurement,
    proofs: SourceFidelityProofs,
) -> RendererDivergenceClassification:
    """Classify one headless-vs-DOCX divergence from measured evidence.

    The checks run in the order that keeps blame attributable: an unavailable
    measurement is ``UNKNOWN``, a wrong requested font is a DOCX typography
    mismatch, a wrong frame/indent is a true geometry defect, and only a
    completely proven substitution may be excused.  The prediction residual test
    is what stops "the fonts are different" from being used as a blanket excuse:
    a substitution that does *not* account for the observed overflow leaves the
    divergence unclassified, and unclassified is a blocker.
    """

    evidence = {
        "source_family": typography.source_family,
        "source_size_pt": typography.source_size_pt,
        "docx_requested_family": typography.docx_requested_family,
        "docx_size_pt": typography.docx_size_pt,
        "docx_character_spacing_twips": typography.docx_character_spacing_twips,
        "host_font_state": typography.host_font_state,
        "headless_family": typography.headless_family,
        "headless_size_pt": typography.headless_size_pt,
        "advance_ratio": row.advance_ratio,
        "source_fill_ratio": row.source_fill_ratio,
        "predicted_overflow_pt": row.predicted_overflow_pt(),
        "observed_overflow_pt": row.observed_overflow_pt(),
    }

    if proofs.any_unavailable:
        return RendererDivergenceClassification(
            divergence_class=UNKNOWN_RENDER_DIVERGENCE,
            blocking=True,
            reasons=[
                "a mandatory source/DOCX fidelity measurement is unavailable: "
                + ", ".join(proofs.notes or ["unspecified"])
            ],
            evidence=evidence,
        )

    if not typography.evidence_complete:
        return RendererDivergenceClassification(
            divergence_class=UNKNOWN_RENDER_DIVERGENCE,
            blocking=True,
            reasons=[
                "source or DOCX typography evidence is incomplete, so the "
                "divergence cannot be attributed to a layer"
            ],
            evidence=evidence,
        )

    if not typography.docx_matches_source:
        return RendererDivergenceClassification(
            divergence_class=DOCX_TYPOGRAPHY_MISMATCH,
            blocking=True,
            reasons=[
                "the DOCX does not request the source's own typography: "
                f"source={typography.source_family!r}@{typography.source_size_pt} "
                f"docx={typography.docx_requested_family!r}@{typography.docx_size_pt} "
                f"spacing={typography.docx_character_spacing_twips}"
            ],
            evidence=evidence,
        )

    if not proofs.docx_geometry_matches_source:
        return RendererDivergenceClassification(
            divergence_class=TRUE_LAYOUT_GEOMETRY_DEFECT,
            blocking=True,
            reasons=[
                "the DOCX typography matches the source but the delivered "
                "frame/indent/row geometry does not"
            ],
            evidence=evidence,
        )

    if not (
        proofs.row_ownership_correct
        and proofs.text_complete_and_ordered
        and proofs.source_slots_preserved
        and proofs.no_true_geometry_defect
    ):
        return RendererDivergenceClassification(
            divergence_class=TRUE_LAYOUT_GEOMETRY_DEFECT,
            blocking=True,
            reasons=[
                "source/DOCX ownership, text completeness or source-slot "
                "preservation is not proven, so the divergence is a delivery defect"
            ],
            evidence=evidence,
        )

    ratio = row.advance_ratio
    if ratio is None:
        return RendererDivergenceClassification(
            divergence_class=UNKNOWN_RENDER_DIVERGENCE,
            blocking=True,
            reasons=["the rendered and source glyph advances could not both be measured"],
            evidence=evidence,
        )

    if not typography.substitution_proven:
        if typography.resolved_family_is_requested:
            # The render used the family the DOCX asked for, on a host that has it:
            # no substitution occurred, so an advance difference is a metric property
            # of the source's embedded subset versus the installed font.  The DOCX
            # must not compensate for that by distorting its own typography.
            if ratio is not None and abs(ratio - 1.0) <= 1e-9:
                return RendererDivergenceClassification(
                    divergence_class=HEADLESS_FONT_SUBSTITUTION_ONLY,
                    blocking=False,
                    reasons=[
                        "no measurable divergence; the rendered row matches the source"
                    ],
                    evidence=evidence,
                )
            return RendererDivergenceClassification(
                divergence_class=SOURCE_FONT_METRIC_DIFFERENCE,
                blocking=True,
                reasons=[
                    "the renderer used the requested family, so no substitution "
                    "occurred; the advance difference is a font metric property that "
                    "the DOCX must not compensate for by distorting its typography"
                ],
                evidence=evidence,
            )
        return RendererDivergenceClassification(
            divergence_class=UNKNOWN_RENDER_DIVERGENCE,
            blocking=True,
            reasons=[
                "a family change was observed but substitution is not proven: the "
                "host font state is "
                f"{typography.host_font_state} for requested family "
                f"{typography.docx_requested_family!r}"
            ],
            evidence=evidence,
        )

    predicted = row.predicted_overflow_pt()
    observed = row.observed_overflow_pt()
    if predicted is None or observed is None:
        return RendererDivergenceClassification(
            divergence_class=UNKNOWN_RENDER_DIVERGENCE,
            blocking=True,
            reasons=["the predicted or observed overflow could not be measured"],
            evidence=evidence,
        )

    if predicted <= 0.0 or observed <= 0.0:
        # The substitution does not even predict an overflow, yet one was seen (or
        # vice versa): something else moved the row.
        return RendererDivergenceClassification(
            divergence_class=UNKNOWN_RENDER_DIVERGENCE,
            blocking=True,
            reasons=[
                "the measured substitute advance does not predict the observed "
                f"overflow (predicted={predicted:.2f} pt, observed={observed:.2f} pt)"
            ],
            evidence=evidence,
        )

    glyph = row.headless_per_char_pt or 0.0
    residual = abs(predicted - observed)
    evidence["prediction_residual_pt"] = round(residual, 3)
    evidence["prediction_residual_glyph_fraction"] = (
        round(residual / glyph, 4) if glyph else None
    )
    if glyph and residual > glyph * PREDICTION_RESIDUAL_GLYPH_FRACTION:
        return RendererDivergenceClassification(
            divergence_class=UNKNOWN_RENDER_DIVERGENCE,
            blocking=True,
            reasons=[
                "the substitution prediction does not account for the observed "
                f"overflow within {PREDICTION_RESIDUAL_GLYPH_FRACTION:g} of one glyph "
                f"(predicted={predicted:.2f} pt, observed={observed:.2f} pt, "
                f"residual={residual:.2f} pt)"
            ],
            evidence=evidence,
        )

    return RendererDivergenceClassification(
        divergence_class=HEADLESS_FONT_SUBSTITUTION_ONLY,
        blocking=False,
        reasons=[
            "the DOCX requests the source's own family and size, the delivered "
            "geometry and ownership reproduce the source, the text is complete and "
            "the source slots survive, and the measured substitute advance predicts "
            "the observed overflow within "
            f"{PREDICTION_RESIDUAL_GLYPH_FRACTION:g} of one glyph"
        ],
        evidence=evidence,
    )
