"""Stable source section/page frame derivation.

A page's own content bounding box is **not** a page frame.  A sparse page whose
only content is a short centred title has a narrow bounding box; a table wider
than the body frame has a wide one.  Deriving a Word section margin from either
makes the left/right margin jump from page to page, which shifts every centred
heading on the affected pages and falsely narrows the column until headings that
the source keeps on one line wrap.

This module separates the two concepts:

``SourceSectionPageFrame``
    The *document/section* page frame: page size, orientation, left/right body
    frame, top/bottom body frame.  One frame is derived per source page group
    (page size + orientation) and every page in the group resolves to it, so a
    sparse page can never inflate the margin and a wide table can never
    contract it.

per-element geometry
    Source x/y positions that differ from the frame are represented on the
    element itself - paragraph indent, tab stops, table indent, positioned
    blanks, source-form-line geometry, paragraph spacing - never by moving the
    section margin.

Evidence
--------
The frame is derived from *repeated* source geometry, never from a single page:

* repeated paragraph/table/rule anchors: every page votes at most once for each
  distinct x anchor it carries, anchors are clustered with a source-geometry
  tolerance, and the cluster with the most page support wins;
* the modal first-content y of pages that carry emittable content;
* when a side has no repeated anchor, the median body bound of the pages whose
  content actually spans the body frame (the ``spanning`` test rejects sparse
  and title-only pages);
* centred content symmetry, used only as a fallback for a side with no repeated
  anchor at all.

Nothing here is case-specific: no page number, no document identity and no
literal margin constant appears in the derivation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import median

#: Source PDF geometry quantisation.  Anchors closer than this are one anchor.
PAGE_FRAME_ANCHOR_TOLERANCE_PT = 1.0

#: An anchor needs this many distinct pages behind it to be frame evidence.
MIN_FRAME_ANCHOR_SUPPORT = 2

#: ...and this fraction of the group's pages.
MIN_FRAME_ANCHOR_SUPPORT_RATIO = 0.2

#: A page only evidences the body frame when its content actually spans it.
MIN_SPANNING_FRAME_RATIO = 0.55

#: A frame must leave at least this fraction of the page as usable width.
MIN_FRAME_BODY_WIDTH_RATIO = 0.5

#: Hard floor for a margin: narrower than this is not a printable body.
MIN_FRAME_MARGIN_PT = 18.0

#: The body frame must keep at least this much height below the top margin.
MIN_FRAME_BODY_HEIGHT_PT = 72.0

#: Anchor kinds.  Text anchors outrank rule/table anchors at equal support.
TEXT_ANCHOR_KINDS = ("text_left", "text_right")
LEFT_ANCHOR_KINDS = ("text_left", "table_left", "rule_left")
RIGHT_ANCHOR_KINDS = ("text_right", "table_right", "rule_right")


@dataclass(frozen=True)
class FrameAnchor:
    """One repeated source x anchor and the pages that carry it."""

    x: float
    kind: str
    pages: tuple[int, ...]
    support: int = 0
    cluster: tuple[float, ...] = ()

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["pages"] = list(self.pages)
        payload["cluster"] = list(self.cluster)
        return payload


@dataclass(frozen=True)
class SourceSectionPageFrame:
    """The stable page frame of one source page group."""

    frame_id: str
    page_width: float
    page_height: float
    orientation: str
    left_margin: float
    right_margin: float
    top_body_frame: float
    bottom_body_frame: float
    usable_text_width: float
    pages: tuple[int, ...]
    method: str
    confidence: float
    left_anchor: FrameAnchor | None = None
    right_anchor: FrameAnchor | None = None
    top_frame: dict = field(default_factory=dict)
    spanning_pages: tuple[int, ...] = ()
    first_content_pages: tuple[int, ...] = ()
    centered_symmetry: dict | None = None
    notes: tuple[str, ...] = ()

    @property
    def body_x0(self) -> float:
        return self.left_margin

    @property
    def body_x1(self) -> float:
        return self.page_width - self.right_margin

    def page_geometry(self, source_page: int) -> dict:
        """The per-page geometry record this frame implies for one page."""

        return {
            "page": int(source_page),
            "frame_id": self.frame_id,
            "page_width": round(self.page_width, 2),
            "page_height": round(self.page_height, 2),
            "orientation": self.orientation,
            "left_margin": round(self.left_margin, 2),
            "right_margin": round(self.right_margin, 2),
            "top_margin": round(self.top_body_frame, 2),
            "bottom_margin": round(self.bottom_body_frame, 2),
            "body_x0": round(self.body_x0, 2),
            "body_x1": round(self.body_x1, 2),
            "body_y0": round(self.top_body_frame, 2),
            "usable_text_width": round(self.usable_text_width, 2),
            "method": self.method,
        }

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["pages"] = list(self.pages)
        payload["spanning_pages"] = list(self.spanning_pages)
        payload["first_content_pages"] = list(self.first_content_pages)
        payload["notes"] = list(self.notes)
        payload["left_anchor"] = self.left_anchor.as_dict() if self.left_anchor else None
        payload["right_anchor"] = self.right_anchor.as_dict() if self.right_anchor else None
        payload["usable_text_width"] = round(self.usable_text_width, 2)
        for key in ("left_margin", "right_margin", "top_body_frame", "bottom_body_frame",
                    "page_width", "page_height"):
            payload[key] = round(float(payload[key]), 2)
        return payload


def _span_extent(line) -> tuple[float, float] | None:
    boxes = [
        (float(span.bbox[0]), float(span.bbox[2]))
        for span in getattr(line, "spans", []) or []
        if str(getattr(span, "text", "") or "").strip()
        and len(getattr(span, "bbox", ()) or ()) >= 4
    ]
    if not boxes:
        return None
    x0 = min(box[0] for box in boxes)
    x1 = max(box[1] for box in boxes)
    return (x0, x1) if x1 > x0 else None


def _page_line_extents(source_page) -> list[tuple[float, float]]:
    extents: list[tuple[float, float]] = []
    for paragraph in getattr(source_page, "paragraphs", []) or []:
        for line in getattr(paragraph, "lines", []) or []:
            extent = _span_extent(line)
            if extent is not None:
                extents.append(extent)
    return extents


def _is_centered(item) -> bool:
    hint = str(getattr(item, "alignment_hint", "") or "").lower()
    role = str(getattr(getattr(item, "alignment_role", ""), "value",
                       getattr(item, "alignment_role", "")) or "").upper()
    return hint == "center" or "CENTER" in role


def page_frame_evidence(source_page, layout=None) -> dict:
    """All frame evidence one source page contributes, without any decision."""

    if layout is None:
        from .page_layout import build_page_layout

        layout = build_page_layout(source_page)
    elements = list(getattr(layout, "elements", []) or [])
    line_extents = _page_line_extents(source_page)

    left_anchors: list[float] = []
    right_anchors: list[float] = []
    for x0, x1 in line_extents:
        left_anchors.append(x0)
        right_anchors.append(x1)

    table_boxes = []
    for table in getattr(source_page, "tables", []) or []:
        bbox = getattr(table, "bbox", None)
        if bbox is None or len(bbox) < 4:
            continue
        box = (float(bbox[0]), float(bbox[2]))
        if box[1] > box[0]:
            table_boxes.append(box)
    rule_boxes = []
    for rule in getattr(layout, "horizontal_rules", []) or []:
        bbox = getattr(rule, "bbox", None)
        if bbox is None or len(bbox) < 4:
            continue
        box = (float(bbox[0]), float(bbox[2]))
        if box[1] > box[0]:
            rule_boxes.append(box)

    element_count = len(elements)
    if line_extents:
        visible_x0 = min(x0 for x0, _ in line_extents)
        visible_x1 = max(x1 for _, x1 in line_extents)
    else:
        visible_x0 = visible_x1 = None
    if table_boxes:
        visible_x0 = min([visible_x0] + [b[0] for b in table_boxes]) if visible_x0 is not None else min(b[0] for b in table_boxes)
        visible_x1 = max([visible_x1] + [b[1] for b in table_boxes]) if visible_x1 is not None else max(b[1] for b in table_boxes)

    page_width = float(source_page.width)
    span = (visible_x1 - visible_x0) if (visible_x0 is not None and visible_x1 is not None) else 0.0
    spanning = bool(
        element_count >= 3
        and page_width > 0
        and span >= page_width * MIN_SPANNING_FRAME_RATIO
    )

    # A single-element page whose only element is centred is a title-only page.
    centred_only = bool(
        element_count == 1 and elements and _is_centered(elements[0])
    )

    first_element = elements[0] if elements else None
    first_content_y = float(first_element.bbox[1]) if first_element is not None else None
    # A table has no Word space-before of its own, so a page whose first element
    # is a table cannot carry a page-top paragraph gap.
    first_can_carry_gap = bool(
        first_element is not None and type(first_element).__name__ != "SourceTable"
        and not hasattr(first_element, "rows")
    )

    widest = "none"
    if table_boxes and (visible_x1 is None or max(b[1] for b in table_boxes) >= (visible_x1 or 0) - 0.01):
        widest = "table"
    elif line_extents:
        widest = "paragraph"

    centered_center = None
    if centred_only and visible_x0 is not None:
        centered_center = (visible_x0 + visible_x1) / 2.0

    return {
        "source_page": int(source_page.page),
        "page_width": round(page_width, 2),
        "page_height": round(float(source_page.height), 2),
        "left_anchors": [round(v, 2) for v in left_anchors],
        "right_anchors": [round(v, 2) for v in right_anchors],
        "table_boxes": [[round(b[0], 2), round(b[1], 2)] for b in table_boxes],
        "rule_boxes": [[round(b[0], 2), round(b[1], 2)] for b in rule_boxes],
        "visible_x0": None if visible_x0 is None else round(visible_x0, 2),
        "visible_x1": None if visible_x1 is None else round(visible_x1, 2),
        "visible_y0": None if first_content_y is None else round(first_content_y, 2),
        "element_count": element_count,
        "widest_element_type": widest,
        "spans_body_frame": spanning,
        "title_only": centred_only,
        "first_content_y": None if first_content_y is None else round(first_content_y, 2),
        "first_element_kind": type(first_element).__name__ if first_element is not None else None,
        "first_element_can_carry_page_gap": first_can_carry_gap,
        "centered_content_center_x": None if centered_center is None else round(centered_center, 2),
    }


def _group_key(evidence: dict) -> tuple:
    width = round(float(evidence["page_width"]), 1)
    height = round(float(evidence["page_height"]), 1)
    orientation = "PORTRAIT" if height >= width else "LANDSCAPE"
    return (orientation, width, height)


def _vote(evidence_rows: list[dict], side: str) -> dict[float, dict]:
    """``anchor value -> {pages carrying it, anchor kinds seen there}``.

    Exactly one vote per page per value, so a page that draws the same edge ten
    times counts once.  The anchor's *kind* travels with the vote: a text body
    edge and a table edge are different evidence, and a table that overhangs the
    body must never be mistaken for the body frame when both repeat equally.
    """

    votes: dict[float, dict] = {}

    def record(value: float, kind: str, page: int) -> None:
        entry = votes.setdefault(round(float(value), 1), {"pages": set(), "kinds": set()})
        entry["pages"].add(int(page))
        entry["kinds"].add(kind)

    for row in evidence_rows:
        page = int(row["source_page"])
        for x0, x1 in zip(row["left_anchors"], row["right_anchors"]):
            if side == "left":
                record(x0, "text_left", page)
            else:
                record(x1, "text_right", page)
        for box in row["table_boxes"]:
            if side == "left":
                record(box[0], "table_left", page)
            else:
                record(box[1], "table_right", page)
        for box in row["rule_boxes"]:
            if side == "left":
                record(box[0], "rule_left", page)
            else:
                record(box[1], "rule_right", page)
    return votes


def _cluster_votes(votes: dict[float, dict]) -> list[tuple[float, tuple[float, ...], list[int], int, bool]]:
    """Cluster anchor values.

    Returns ``(value, cluster, pages, support, text_backed)``; ``text_backed``
    says whether the winning cluster carries at least one text body edge.
    """

    ordered = sorted(votes)
    clusters: list[list[float]] = []
    for value in ordered:
        if clusters and value - clusters[-1][0] <= PAGE_FRAME_ANCHOR_TOLERANCE_PT:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    out = []
    for cluster in clusters:
        per_value = {value: votes[value] for value in cluster}
        support = len({page for entry in per_value.values() for page in entry["pages"]})
        kinds = {kind for entry in per_value.values() for kind in entry["kinds"]}
        values = tuple(round(value, 2) for value in cluster)
        mode = max(per_value, key=lambda value: (len(per_value[value]["pages"]), -abs(value)))
        pages = sorted({page for entry in per_value.values() for page in entry["pages"]})
        out.append((
            round(float(mode), 2),
            values,
            pages,
            support,
            bool(kinds.intersection(TEXT_ANCHOR_KINDS)),
        ))
    return out


def _pick_anchor(
    votes: dict[float, dict],
    *,
    side: str,
    group_size: int,
) -> FrameAnchor | None:
    clusters = _cluster_votes(votes)
    if not clusters:
        return None
    min_support = max(MIN_FRAME_ANCHOR_SUPPORT, int(-(-group_size * MIN_FRAME_ANCHOR_SUPPORT_RATIO // 1)))
    eligible = [c for c in clusters if c[3] >= min_support]
    if not eligible:
        return None
    if side == "left":
        # Widest body wins a tie: the frame is a bound, not a content box.  A
        # repeated text edge outranks a repeated table/rule edge at equal support,
        # because a table that overhangs the body is not the body frame.
        best = max(eligible, key=lambda c: (c[3], c[4], -c[0]))
        kind = "text_left" if best[4] else "table_left"
    else:
        best = max(eligible, key=lambda c: (c[3], c[4], c[0]))
        kind = "text_right" if best[4] else "table_right"
    value, cluster, pages, support, _text = best
    return FrameAnchor(x=value, kind=kind, pages=tuple(pages), support=support, cluster=cluster)


def _median_body_bounds(rows: list[dict]) -> tuple[float | None, float | None]:
    lefts = [r["visible_x0"] for r in rows if r["visible_x0"] is not None]
    rights = [r["visible_x1"] for r in rows if r["visible_x1"] is not None]
    if not lefts or not rights:
        return None, None
    return float(median(lefts)), float(median(rights))


def derive_source_section_page_frames(source_pages, layouts=None) -> dict[int, SourceSectionPageFrame]:
    """Derive one stable page frame per source page group.

    Returns ``{source_page_number: SourceSectionPageFrame}``.
    """

    pages = list(source_pages)
    if layouts is None:
        layouts = [None] * len(pages)
    layouts = list(layouts)
    if len(layouts) != len(pages):
        raise ValueError("layouts must be aligned with source_pages")

    rows = [
        page_frame_evidence(page, layout)
        for page, layout in zip(pages, layouts)
    ]
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault(_group_key(row), []).append(row)

    frames: dict[int, SourceSectionPageFrame] = {}
    for group_index, (key, members) in enumerate(sorted(groups.items())):
        orientation, width, height = key
        group_size = len(members)
        notes: list[str] = []
        spanning = [r for r in members if r["spans_body_frame"]]
        fallback_rows = spanning or [r for r in members if r["visible_x0"] is not None]

        left_anchor = _pick_anchor(_vote(members, "left"),
                                  side="left", group_size=group_size)
        right_anchor = _pick_anchor(_vote(members, "right"),
                                   side="right", group_size=group_size)

        med_left, med_right = _median_body_bounds(fallback_rows)
        if left_anchor is not None:
            body_x0 = left_anchor.x
        elif med_left is not None:
            body_x0 = med_left
            notes.append("left frame from the median body bound of body-spanning pages")
        else:
            body_x0 = MIN_FRAME_MARGIN_PT
            notes.append("left frame from the printable floor: no page evidence")

        symmetry = None
        if right_anchor is not None:
            body_x1 = right_anchor.x
        else:
            centers = [r["centered_content_center_x"] for r in members
                       if r["centered_content_center_x"] is not None]
            if centers:
                center = float(median(centers))
                body_x1 = 2.0 * center - body_x0
                symmetry = {
                    "centered_page_count": len(centers),
                    "center_x": round(center, 2),
                    "derived_body_x1": round(body_x1, 2),
                    "reason": "no repeated right anchor: centred content symmetry",
                }
                notes.append("right frame from centred-content symmetry")
            elif med_right is not None:
                body_x1 = med_right
                notes.append("right frame from the median body bound of body-spanning pages")
            else:
                body_x1 = width - MIN_FRAME_MARGIN_PT
                notes.append("right frame from the printable floor: no page evidence")

        # A page frame is a bound: never let the clamp manufacture a margin that
        # is wider than the printable floor or narrower than the usable minimum.
        body_x0 = max(MIN_FRAME_MARGIN_PT, min(body_x0, width - MIN_FRAME_MARGIN_PT))
        body_x1 = min(width - MIN_FRAME_MARGIN_PT, max(body_x1, MIN_FRAME_MARGIN_PT))
        if body_x1 - body_x0 < width * MIN_FRAME_BODY_WIDTH_RATIO:
            body_x0 = max(MIN_FRAME_MARGIN_PT, min(body_x0, width - MIN_FRAME_MARGIN_PT))
            body_x1 = min(width - MIN_FRAME_MARGIN_PT,
                          max(body_x1, body_x0 + width * MIN_FRAME_BODY_WIDTH_RATIO))
            notes.append("body width widened to the minimum usable width")

        top_rows = [
            r for r in members
            if r["first_content_y"] is not None and r["first_element_can_carry_page_gap"]
        ]
        if not top_rows:
            top_rows = [r for r in members if r["first_content_y"] is not None]
            if top_rows:
                notes.append("page-top frame uses pages whose first element is a table")
        if top_rows:
            counts: dict[float, int] = {}
            for row in top_rows:
                counts[round(float(row["first_content_y"]), 2)] = counts.get(
                    round(float(row["first_content_y"]), 2), 0) + 1
            modal_y = max(counts, key=lambda y: (counts[y], -y))
            # The frame top is a *lower bound* on first content: every page's
            # own first-content y is then reached by a non-negative
            # paragraph-space-before, so no page needs its own top margin.
            top_y = min(float(r["first_content_y"]) for r in top_rows)
            top_frame = {
                "modal_first_content_y": round(modal_y, 2),
                "modal_support": counts[modal_y],
                "min_first_content_y": round(top_y, 2),
                "pages": sorted(int(r["source_page"]) for r in top_rows),
            }
        else:
            top_y = MIN_FRAME_MARGIN_PT
            top_frame = {"modal_first_content_y": None, "modal_support": 0,
                         "min_first_content_y": None, "pages": []}
            notes.append("page-top frame from the printable floor: no page evidence")
        top_y = max(MIN_FRAME_MARGIN_PT,
                    min(top_y, max(MIN_FRAME_MARGIN_PT, height - MIN_FRAME_BODY_HEIGHT_PT)))

        frame = SourceSectionPageFrame(
            frame_id=f"{orientation}_{int(round(width))}x{int(round(height))}_{group_index + 1}",
            page_width=float(width),
            page_height=float(height),
            orientation=orientation,
            left_margin=round(body_x0, 2),
            right_margin=round(width - body_x1, 2),
            top_body_frame=round(top_y, 2),
            bottom_body_frame=MIN_FRAME_MARGIN_PT,
            usable_text_width=round(body_x1 - body_x0, 2),
            pages=tuple(sorted(int(r["source_page"]) for r in members)),
            method=(
                "repeated source anchors (page-weighted, clustered) for the body "
                "frame; minimum first-content y for the top body frame"
            ),
            confidence=round(len(spanning) / group_size, 3) if group_size else 0.0,
            left_anchor=left_anchor,
            right_anchor=right_anchor,
            top_frame=top_frame,
            spanning_pages=tuple(sorted(int(r["source_page"]) for r in spanning)),
            first_content_pages=tuple(sorted(int(r["source_page"]) for r in top_rows)),
            centered_symmetry=symmetry,
            notes=tuple(notes),
        )
        for row in members:
            frames[int(row["source_page"])] = frame
    return frames


__all__ = [
    "FrameAnchor",
    "SourceSectionPageFrame",
    "derive_source_section_page_frames",
    "page_frame_evidence",
    "MIN_FRAME_BODY_HEIGHT_PT",
    "MIN_FRAME_ANCHOR_SUPPORT",
    "MIN_FRAME_ANCHOR_SUPPORT_RATIO",
    "MIN_FRAME_BODY_WIDTH_RATIO",
    "MIN_FRAME_MARGIN_PT",
    "MIN_SPANNING_FRAME_RATIO",
    "PAGE_FRAME_ANCHOR_TOLERANCE_PT",
]
