"""PDF font normalization and conservative Word font mapping."""

from __future__ import annotations

import re


_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
_ALIASES = {
    "宋体": "宋体",
    "simsun": "宋体",
    "simsun-extb": "宋体",
    "仿宋": "仿宋",
    "fangsong": "仿宋",
    "fangsong_gb2312": "仿宋",
    "黑体": "黑体",
    "simhei": "黑体",
    "楷体": "楷体",
    "kaiti": "楷体",
    "arial": "Arial",
    "calibri": "Calibri",
    "timesnewroman": "Times New Roman",
    "timesnewromanpsmt": "Times New Roman",
}


def normalize_pdf_font_name(source_name: str | None) -> tuple[str, bool]:
    """Strip PDF subset prefixes and canonicalize known family aliases."""

    raw = (source_name or "").strip()
    stripped = _SUBSET_PREFIX.sub("", raw)
    compact = stripped.replace(" ", "").lower()
    canonical = _ALIASES.get(stripped.lower()) or _ALIASES.get(compact)
    if canonical:
        return canonical, canonical != raw
    lowered = stripped.lower()
    for hints, canonical in (
        (("黑体", "simhei", "hei"), "黑体"),
        (("仿宋", "fangsong", "fang"), "仿宋"),
        (("楷体", "kaiti", "kai"), "楷体"),
        (("宋体", "simsun", "song"), "宋体"),
    ):
        if any(hint in lowered for hint in hints):
            return canonical, True
    return stripped or "宋体", bool(raw and stripped != raw)


def font_name(source_name: str | None) -> tuple[str, bool]:
    """Return a Word-safe family without treating subset names as styles."""

    canonical, changed = normalize_pdf_font_name(source_name)
    if canonical in set(_ALIASES.values()):
        return canonical, changed
    return "宋体", True


__all__ = ["font_name", "normalize_pdf_font_name"]
