"""Round 5.6 source visual typography.

Visual weight is measured from the *rendered* source page, never from PDF font
flags alone: a tender PDF can carry an emphatic heading in a regular font face
(``flags`` say regular) while the rendered glyphs are clearly heavier than the
document body.  For each semantic role this module samples the rendered ink of
its source glyphs and compares it with the document body measured the same way.

``weight_index`` = ink pixels / (CJK glyph count * font size in points^2), so it
is comparable across font sizes for the same font family.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median

#: A role is visually bold when its rendered ink per glyph exceeds the body by
#: this factor; it is visibly regular below the second factor.
BOLD_RATIO = 1.25
REGULAR_RATIO = 1.15

#: Glyphs sampled per span; CJK-only windows keep the comparison clean.
SAMPLE_GLYPHS = 8
ZOOM = 6.0
INK_THRESHOLD = 160

ROLE_LABELS: dict[str, str] = {
    "CHAPTER_TITLE": "COVER_CHAPTER",
    "COVER_PROJECT_TITLE": "COVER_PROJECT_TITLE",
    "DOCUMENT_TITLE": "COVER_DOCUMENT_TITLE",
    "TOC_TITLE": "TOC_TITLE",
    "HEADING_1": "HEADING_LEVEL_1",
    "HEADING_2": "HEADING_LEVEL_2",
    "HEADING_3": "HEADING_LEVEL_3",
    "BODY": "BODY",
    "FORM_LABEL": "FORM_LABEL",
    "SIGNATURE_BLOCK": "SIGNATURE_LABEL",
}

BODY_ROLES = frozenset(
    {"BODY", "BODY_FIRST_LINE", "BODY_CENTER", "BODY_RIGHT", "BODY_NO_INDENT"}
)


def is_cjk(character: str) -> bool:
    code = ord(character)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x3000 <= code <= 0x303F
        or 0xFF00 <= code <= 0xFFEF
    )


def cjk_prefix(text: str, limit: int = SAMPLE_GLYPHS) -> str:
    """Leading CJK/punctuation glyphs of ``text`` (spaces and Latin skipped)."""

    collected = []
    for character in text:
        if character.isspace():
            continue
        if is_cjk(character):
            collected.append(character)
        elif collected:
            break
        if len(collected) >= limit:
            break
    return "".join(collected)


@dataclass
class VisualWeightSample:
    """One rendered-glyph weight measurement."""

    role: str
    text: str
    page: int
    font: str
    size_pt: float
    glyphs: int
    ink_ratio: float
    weight_index: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class TypographyRoleProfile:
    """Rendered weight verdict for one semantic role."""

    role: str
    public_role: str
    samples: int
    median_weight: float
    baseline_weight: float
    ratio: float
    bold: bool | None
    font: str
    size_pt: float
    confidence: float
    evidence: list[str] = field(default_factory=list)
    method: str = "rendered glyph ink per sampled CJK glyph vs document body"

    def as_dict(self) -> dict:
        return asdict(self)


def measure_span_weight(page, bbox, size_pt: float, *, glyphs: int, zoom: float = ZOOM) -> dict:
    """Return the rendered ink metrics for a CJK glyph window of one span."""

    import pymupdf

    if glyphs <= 0 or size_pt <= 0:
        return {"ink_ratio": 0.0, "weight_index": 0.0}
    clip = pymupdf.Rect(
        float(bbox[0]) - 0.5,
        float(bbox[1]) - 0.5,
        float(bbox[0]) + glyphs * size_pt + 0.5,
        float(bbox[3]) + 0.5,
    )
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom), clip=clip, colorspace=pymupdf.csGRAY
    )
    samples = pixmap.samples
    ink = sum(1 for value in samples if value < INK_THRESHOLD)
    area = max(1, len(samples))
    # CJK glyphs advance one em; the sampled window is glyphs * size wide.
    normaliser = glyphs * float(size_pt) * float(size_pt) * zoom * zoom
    return {
        "ink_ratio": round(ink / area, 5),
        "weight_index": round(ink / normaliser, 5),
    }


def _span_evidence(item, limit: int = 3) -> list[tuple[str, float, tuple[float, float, float, float], str]]:
    """Sampled (text, size, bbox, font) windows from one logical paragraph."""

    found: list[tuple[str, float, tuple[float, float, float, float], str]] = []
    lines = list(getattr(item, "source_lines", []) or [])
    for line in lines:
        for run in getattr(line, "runs", []) or []:
            text = str(getattr(run, "text", "") or "")
            window = cjk_prefix(text)
            if len(window) < 2:
                continue
            size = float(getattr(run, "font_size", 0.0) or 0.0)
            bbox = getattr(run, "bbox", None) or getattr(line, "bbox", None)
            if not size or bbox is None:
                continue
            found.append((window, size, tuple(float(v) for v in bbox), str(getattr(run, "font_name", "") or "")))
            if len(found) >= limit:
                return found
    if not found:
        for line in lines[:1]:
            text = str(getattr(line, "text", "") or "")
            window = cjk_prefix(text)
            size = float(getattr(line, "font_size", 0.0) or getattr(item, "font_size_pt", 0.0) or 0.0)
            bbox = getattr(line, "bbox", None) or getattr(item, "bbox", None)
            if len(window) >= 2 and size and bbox is not None:
                found.append((window, size, tuple(float(v) for v in bbox), ""))
    return found


def infer_visual_typography(
    source_pdf: str | Path | None,
    template,
    layouts: list | None = None,
) -> dict:
    """Measure rendered visual weight per semantic role.

    Returns ``{"roles": {...}, "samples": [...], "baseline_weight": float,
    "source_pdf": str, "status": str}``.  ``status`` is ``MEASURED`` when the
    rendered page was available and ``UNAVAILABLE`` otherwise, so callers can
    fall back to PDF metadata without inventing visual evidence.
    """

    result: dict = {
        "status": "UNAVAILABLE",
        "source_pdf": str(source_pdf or ""),
        "baseline_weight": None,
        "roles": {},
        "samples": [],
        "reason": "",
    }
    if not source_pdf:
        result["reason"] = "no source document path was provided to the builder"
        return result
    path = Path(source_pdf)
    if not path.is_file():
        result["reason"] = "source document is not readable from this working directory"
        return result
    if template is None or not getattr(template, "source_pages", None):
        result["reason"] = "source format has no pages"
        return result

    import pymupdf

    from .style_architecture import _records_for

    if layouts is None:
        from .page_layout import build_page_layout

        layouts = [build_page_layout(page) for page in template.source_pages]

    records = _records_for(template, layouts)
    samples: list[VisualWeightSample] = []
    with pymupdf.open(path) as document:
        for semantic, item, page in records:
            role = str(getattr(semantic, "role", "") or "")
            if not role:
                continue
            if role == "HEADING":
                level = int(getattr(semantic, "heading_level", 0) or 0)
                role = f"HEADING_{max(1, level)}"
            page_number = int(getattr(page, "page", 0) or 0)
            if page_number < 1 or page_number > document.page_count:
                continue
            pymupdf_page = document[page_number - 1]
            for window, size, bbox, font in _span_evidence(item):
                metrics = measure_span_weight(
                    pymupdf_page, bbox, size, glyphs=len(window)
                )
                if metrics["weight_index"] <= 0:
                    continue
                samples.append(
                    VisualWeightSample(
                        role=role,
                        text=window,
                        page=page_number,
                        font=font,
                        size_pt=round(size, 2),
                        glyphs=len(window),
                        ink_ratio=metrics["ink_ratio"],
                        weight_index=metrics["weight_index"],
                    )
                )
    if not samples:
        result["reason"] = "no rendered glyph window could be sampled"
        return result

    body_weights = [sample.weight_index for sample in samples if sample.role in BODY_ROLES]
    baseline = median(body_weights) if body_weights else median(
        sample.weight_index for sample in samples
    )
    grouped: dict[str, list[VisualWeightSample]] = {}
    for sample in samples:
        grouped.setdefault(sample.role, []).append(sample)

    roles: dict[str, TypographyRoleProfile] = {}
    for role, role_samples in grouped.items():
        weight = median(sample.weight_index for sample in role_samples)
        ratio = weight / baseline if baseline else 0.0
        if role in BODY_ROLES:
            bold: bool | None = False
        elif ratio >= BOLD_RATIO:
            bold = True
        elif ratio <= REGULAR_RATIO:
            bold = False
        else:
            bold = None
        dominant = max(role_samples, key=lambda sample: sample.size_pt)
        # More repeated evidence and a larger weight gap raise confidence.
        spread = min(1.0, len(role_samples) / 4.0)
        contrast = min(1.0, abs(ratio - 1.0) / 0.6) if ratio else 0.0
        roles[role] = TypographyRoleProfile(
            role=role,
            public_role=ROLE_LABELS.get(role, role),
            samples=len(role_samples),
            median_weight=round(weight, 5),
            baseline_weight=round(baseline, 5),
            ratio=round(ratio, 3),
            bold=bold,
            font=dominant.font,
            size_pt=dominant.size_pt,
            confidence=round(0.35 * spread + 0.65 * contrast, 3),
            evidence=[
                f"p{sample.page} {sample.size_pt:g}pt {sample.text}" for sample in role_samples[:3]
            ],
        )

    result.update(
        {
            "status": "MEASURED",
            "baseline_weight": round(baseline, 5),
            "roles": {role: profile.as_dict() for role, profile in roles.items()},
            "samples": [sample.as_dict() for sample in samples],
        }
    )
    return result


def bold_overrides(typography: dict) -> dict[str, bool]:
    """Semantic-role bold overrides for the style profile inference."""

    overrides: dict[str, bool] = {}
    for role, profile in (typography.get("roles") or {}).items():
        bold = profile.get("bold")
        if bold is None:
            continue
        overrides[role] = bool(bold)
    return overrides


__all__ = [
    "BOLD_RATIO",
    "REGULAR_RATIO",
    "ROLE_LABELS",
    "TypographyRoleProfile",
    "VisualWeightSample",
    "bold_overrides",
    "cjk_prefix",
    "infer_visual_typography",
    "measure_span_weight",
]
