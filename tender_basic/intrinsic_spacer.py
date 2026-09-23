"""Intrinsic source-measured spacer widths.

Some source geometry cannot be reproduced by counting characters.  A date row
``____年____月____日`` separates its three labels by distances the source drew
but never wrote: the PDF text layer holds no space glyph there, so the gap is a
*width*, not a string.  A count of U+2007 figure spaces reproduces such a width
only if the spacer's own advance happens to divide it - at the measured 6.00 pt
quantisation a 21.96 pt gap lands on 18.00 or 24.00, a 2.04 pt error that is
already outside the 2.0 pt geometry tolerance before anything else goes wrong.

The representation that does work is one ordinary space whose *character
tracking* is chosen so the run's rendered width is the source width.  Its width
is intrinsic to the run, so a ``w:jc=center`` paragraph can centre it as a unit
- which an absolute margin-relative tab stop cannot do, because centring
chooses the line start after the stop is fixed.

The model is ``rendered = base_space_advance + tracking`` and it is *affine*,
so the required tracking is a subtraction rather than a search.  Two constants
carry it, both measured rather than assumed:

``space_advance_em``
    One untracked space, as a ratio of the em.  Measured ``0.500`` exactly:
    at 12.0 pt a space renders 6.00 pt and at 11.5 pt it renders 5.75 pt, held
    to the hundredth of a point across every emitted spacer in the document.
    The earlier ``5.618 / 10.5`` (= 0.535 em) came from back-solving a
    two-row probe, and that sample could not separate the base advance from a
    *negative* tracking value in the same row; see ``NEGATIVE_TRACKING_ROUNDS``.

``tracking_response_ratio``
    Rendered width gained per point of requested tracking.  Measured as exactly
    ``1.0``, spread 0.0.

``NEGATIVE_TRACKING_ROUNDS``
    ``False``, and this is a *measured* renderer fact, not a preference.  The
    delivered renderer does not shorten a space by a condensed (negative)
    ``w:spacing``: a run carrying ``w:spacing=-48`` renders at the full base
    advance, while the same run with ``w:spacing=231`` renders 11.55 pt wider.
    Four independent date rows prove it - in each, the gap predicted with the
    negative value applied was short by exactly the condensed amount, and the
    gap predicted with it dropped matched to the hundredth of a point.

    The consequence is the representation's real floor: **one space with zero
    tracking**, i.e. the base advance.  A target below it is not expressible by
    this mechanism.  ``intrinsic_spacer_widths`` therefore rounds tracking up to
    zero rather than emitting a value the renderer discards, so what the caller
    is told is what the page will show.  Callers that must not inflate a
    construct compare ``rendered`` against ``target_width_pt``.

This module is the single place those measured constants live.  It is
calibration metadata, not business logic: the builder reads it and never
launches a renderer.  The probes that produced the numbers are
``scripts/v1_date_intrinsic_spacing_calibration.py`` (the original two-point
probe) and ``scripts/v1_intrinsic_spacer_multisegment_probe.py`` (the
marker-bracketed, zero-spacer-controlled chain probe that replaced its fit).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from docx.oxml.ns import qn

#: Twentieths of a point - the unit ``w:spacing`` is expressed in.
TWIPS_PER_PT = 20.0

#: One untracked space of 仿宋, as a ratio of the em.  Measured 0.500 exactly;
#: see the module docstring for the evidence and for why the previous
#: ``5.618 / 10.5`` was an over-estimate.
MEASURED_SPACE_ADVANCE_EM = 0.500

#: Rendered width gained per point of requested tracking.  Measured as exactly
#: 1.0, with a spread of 0.0 across the calibration sample.
TRACKING_RESPONSE_RATIO = 1.0

#: Whether the renderer applies a condensed (negative) ``w:spacing``.  Measured
#: ``False``: see the module docstring.  This is what makes the base advance the
#: mechanism's floor.
NEGATIVE_TRACKING_ROUNDS = False

#: The narrowest intrinsic spacer this representation can express: one space
#: with zero tracking.
MIN_INTRINSIC_WIDTH_FACTOR = MEASURED_SPACE_ADVANCE_EM


@dataclass(frozen=True)
class IntrinsicSpacerCalibration:
    """Measured typography facts for one font family, as a ratio of the em."""

    font_family: str
    space_advance_em: float = MEASURED_SPACE_ADVANCE_EM
    tracking_response_ratio: float = TRACKING_RESPONSE_RATIO

    def base_advance_pt(self, font_size_pt: float) -> float:
        return max(0.1, float(font_size_pt)) * self.space_advance_em

    def tracking_pt(self, target_width_pt: float, font_size_pt: float) -> float:
        """Tracking that makes one space render ``target_width_pt`` wide.

        Never negative: a condensed value is discarded by the renderer, so
        asking for one would put a number in the document that does not
        describe the page.
        """

        base = self.base_advance_pt(font_size_pt)
        wanted = (float(target_width_pt) - base) / self.tracking_response_ratio
        return wanted if NEGATIVE_TRACKING_ROUNDS else max(0.0, wanted)

    def tracking_twips(self, target_width_pt: float, font_size_pt: float) -> int:
        """The same value in ``w:spacing`` units, rounded to the representable."""

        return int(round(self.tracking_pt(target_width_pt, font_size_pt) * TWIPS_PER_PT))

    def rendered_width_pt(self, target_width_pt: float, font_size_pt: float) -> float:
        """What the emitted run will actually measure for ``target_width_pt``."""

        base = self.base_advance_pt(font_size_pt)
        return base + (
            self.tracking_twips(target_width_pt, font_size_pt) / TWIPS_PER_PT
        ) * self.tracking_response_ratio

    def representable(self, target_width_pt: float, font_size_pt: float) -> bool:
        """False when the target is narrower than one untracked space.

        Such a target is a *representation conflict*: it cannot be expressed by
        this mechanism, and shrinking it to fit would report a width the source
        never drew.  The caller decides what to do; this module never silently
        clamps the *width*, only the tracking it would have to ask for.
        """

        return float(target_width_pt) >= self.base_advance_pt(font_size_pt) - 1e-6


#: One entry per typography the project has actually measured.  A family that is
#: not listed still gets a usable spacer: the space/em ratio is a property of
#: the em, and the probe confirmed tracking responds one-for-one, so the ratio
#: carries across families while remaining an explicitly measured constant
#: rather than a guess hidden in an emitter branch.
CALIBRATIONS: dict[str, IntrinsicSpacerCalibration] = {
    "仿宋": IntrinsicSpacerCalibration(font_family="仿宋"),
    "FangSong": IntrinsicSpacerCalibration(font_family="FangSong"),
}

DEFAULT_CALIBRATION = IntrinsicSpacerCalibration(font_family="*")


def calibration_for(font_family: str | None) -> IntrinsicSpacerCalibration:
    """The measured calibration for ``font_family``, or the measured default."""

    name = (font_family or "").strip()
    if name in CALIBRATIONS:
        return CALIBRATIONS[name]
    for key, value in CALIBRATIONS.items():
        if key.lower() == name.lower():
            return value
    return DEFAULT_CALIBRATION


def intrinsic_spacer_widths(
    target_width_pt: float, font_family: str | None, font_size_pt: float
) -> tuple[int, float]:
    """``(w:spacing twips, rendered width pt)`` for a target source width.

    The rendered width is what the twips will actually produce after rounding
    *and* after the renderer's treatment of condensed spacing, so a caller can
    sum emitted widths and check them against the source gap before anything
    is rendered.  When the target is below the base advance the returned
    rendered width is the base advance and the caller can see the difference.
    """

    calibration = calibration_for(font_family)
    twips = calibration.tracking_twips(target_width_pt, font_size_pt)
    rendered = calibration.rendered_width_pt(target_width_pt, font_size_pt)
    return twips, rendered


def spacer_floor_pt(font_family: str | None, font_size_pt: float) -> float:
    """The narrowest width one intrinsic spacer can render."""

    return calibration_for(font_family).base_advance_pt(font_size_pt)


#: ``w:spacing`` sits between ``w:color`` and ``w:sz`` in the ``CT_RPr``
#: sequence, so it has to be inserted before the first child the schema places
#: after it.  Appending it last put it behind ``w:u`` and the build's own OOXML
#: gate rejected the document - correctly, because Word is entitled to reject a
#: part whose children are out of order.
_TRAILING_RPR_CHILDREN = (
    'sz', 'szCs', 'highlight', 'u', 'effect', 'bdr', 'shd', 'fitText',
    'vertAlign', 'rtl', 'cs', 'em', 'lang', 'eastAsianLayout',
    'specVanish', 'oMath',
)


def apply_spacing(run, twips: int) -> None:
    """Write ``w:spacing`` onto ``run`` at its schema-correct position.

    This is the *one* place the placement rule lives, so the calibration probe
    and the production builder emit byte-identical spacer runs and a measured
    probe result transfers to the document.
    """

    rpr = run._r.get_or_add_rPr()
    element = rpr.makeelement(qn('w:spacing'), {})
    element.set(qn('w:val'), str(int(twips)))
    for child in list(rpr):
        if child.tag.split('}')[-1] in _TRAILING_RPR_CHILDREN:
            child.addprevious(element)
            return
    rpr.append(element)


def selftest() -> int:
    """Reproduce the calibration evidence from the stored constants."""

    calibration = calibration_for("仿宋")
    failures = 0
    # (font size, expected untracked rendered width, provenance)
    for size, expected, why in (
        (12.0, 6.00, "date rows ¶45/50/57/64/76/86/91 at w:sz=24"),
        (11.5, 5.75, "cover date row ¶6 at w:sz=23"),
    ):
        rendered = calibration.rendered_width_pt(expected, size)
        ok = abs(rendered - expected) <= 0.001
        failures += 0 if ok else 1
        print(
            f"  base size={size:>5} rendered={rendered:.3f} "
            f"expected={expected:.3f} ok={ok}  [{why}]"
        )
    # A target below the base advance is reported honestly, not clamped.
    for size, target in ((12.0, 5.79), (12.0, 3.00)):
        rendered = calibration.rendered_width_pt(target, size)
        representable = calibration.representable(target, size)
        ok = (not representable) and abs(rendered - 6.00) <= 0.001
        failures += 0 if ok else 1
        print(
            f"  sub-base size={size:>5} target={target:>5} rendered={rendered:.3f} "
            f"representable={representable} ok={ok}"
        )
    # Tracking still responds one-for-one above the floor.
    twips, rendered = intrinsic_spacer_widths(21.96, "仿宋", 12.0)
    ok = abs(rendered - 21.96) <= 0.026
    failures += 0 if ok else 1
    print(f"  track   target=21.96 twips={twips} rendered={rendered:.3f} ok={ok}")
    print("selftest", "PASS" if not failures else "FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(selftest())
