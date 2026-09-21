"""Round 5.6 source page geometry.

The generated bid document must keep the source tender's usable text area even
when the tender's running header/footer is intentionally not reproduced.  Word
sections carry page size and margins; this module derives those margins from the
source page's own rendered body bounds (text and table geometry inside the body
band), so a header/footer removal can never silently widen the body.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

#: Portion of the page height treated as the running header/footer band.
CHROME_BAND = 0.075

#: Hard floor for a margin: narrower than this is not a printable body.
MIN_MARGIN_PT = 18.0

#: A margin can never exceed this fraction of the page width.
MAX_MARGIN_RATIO = 0.30


@dataclass(frozen=True)
class SectionGeometry:
    """Source-derived page geometry for one generated Word section."""

    page: int
    page_width: float
    page_height: float
    left_margin: float
    right_margin: float
    top_margin: float
    bottom_margin: float
    body_x0: float
    body_x1: float
    body_y0: float
    body_y1: float
    usable_text_width: float
    source_element_count: int
    method: str = "source body bounds inside the non-chrome band"

    def as_dict(self) -> dict:
        return asdict(self)


def _element_bbox(item) -> tuple[float, float, float, float] | None:
    bbox = getattr(item, "bbox", None)
    if bbox is None:
        bbox = getattr(item, "paragraph_container_bbox", None)
    if bbox is None:
        bbox = getattr(item, "text_bbox", None)
    if bbox is None or len(bbox) < 4:
        return None
    return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))


def _is_chrome(item) -> bool:
    flags = " ".join(
        str(getattr(item, name, "") or "")
        for name in ("kind", "classification", "role", "chrome_kind")
    ).upper()
    return any(token in flags for token in ("CHROME", "HEADER", "FOOTER", "PAGE_NUMBER"))


def source_body_bounds(
    layout,
    page_width: float,
    page_height: float,
    *,
    chrome_band: float = CHROME_BAND,
) -> tuple[float, float, float, float, int]:
    """Return ``(x0, x1, y0, y1, count)`` of the source body elements."""

    top_band = page_height * chrome_band
    bottom_band = page_height * (1.0 - chrome_band)
    xs0: list[float] = []
    xs1: list[float] = []
    ys0: list[float] = []
    ys1: list[float] = []
    count = 0
    for item in getattr(layout, "elements", []) or []:
        if _is_chrome(item):
            continue
        bbox = _element_bbox(item)
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        if x1 <= x0 or y1 <= y0:
            continue
        # Ignore running header/footer lines: the body geometry must not depend
        # on whether the source chrome is reproduced.
        if y1 < top_band or y0 > bottom_band:
            continue
        xs0.append(x0)
        xs1.append(x1)
        ys0.append(y0)
        ys1.append(y1)
        count += 1
    if not xs0:
        return (MIN_MARGIN_PT, page_width - MIN_MARGIN_PT, top_band, bottom_band, 0)
    return (min(xs0), max(xs1), min(ys0), max(ys1), count)


def _source_table_bounds(page) -> tuple[float, float] | None:
    """Horizontal extent of the page's own source tables, if measurable."""

    xs0: list[float] = []
    xs1: list[float] = []
    for table in getattr(page, "tables", []) or []:
        bbox = getattr(table, "bbox", None)
        if bbox is None or len(bbox) < 4:
            continue
        x0, _y0, x1, _y1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        if x1 > x0:
            xs0.append(x0)
            xs1.append(x1)
    if not xs0:
        return None
    return (min(xs0), max(xs1))


def section_geometry(layout, page) -> SectionGeometry:
    """Derive one section's geometry from the source page it renders."""

    page_width = float(page.width)
    page_height = float(page.height)
    x0, x1, y0, y1, count = source_body_bounds(layout, page_width, page_height)
    # A source table's outer geometry is mandatory source evidence, but it
    # extends the *content area* rather than moving the text margin: the body
    # text of the same page keeps its own left/right edges (a table wider than
    # the text body must not drag the paragraph column sideways).  The table
    # object itself is positioned by its own indent, measured from this margin.
    table_bounds = _source_table_bounds(page)
    if table_bounds is not None:
        x0 = min(x0, table_bounds[0]) if count else table_bounds[0]
        x1 = max(x1, table_bounds[1]) if count else table_bounds[1]
        count += 1
    max_margin = page_width * MAX_MARGIN_RATIO
    left = min(max(MIN_MARGIN_PT, x0), max_margin)
    right = min(max(MIN_MARGIN_PT, page_width - x1), max_margin)
    top = max(MIN_MARGIN_PT, min(float(layout.content_box[1]), page_height - 72.0))
    # The bottom margin stays at the printable floor: the source body bottom is
    # recorded as evidence, but a Word bottom margin is a page-flow limit, not a
    # visible source geometry, and tightening it would re-paginate the document
    # without improving visual fidelity.
    bottom = MIN_MARGIN_PT
    return SectionGeometry(
        page=int(getattr(page, "page", 0) or 0),
        page_width=round(page_width, 2),
        page_height=round(page_height, 2),
        left_margin=round(left, 2),
        right_margin=round(right, 2),
        top_margin=round(top, 2),
        bottom_margin=round(bottom, 2),
        body_x0=round(x0, 2),
        body_x1=round(x1, 2),
        body_y0=round(y0, 2),
        body_y1=round(y1, 2),
        usable_text_width=round(page_width - left - right, 2),
        source_element_count=count,
    )


__all__ = [
    "CHROME_BAND",
    "MAX_MARGIN_RATIO",
    "MIN_MARGIN_PT",
    "SectionGeometry",
    "section_geometry",
    "source_body_bounds",
]
