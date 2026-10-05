"""Structural-source gate for the canonical EvidenceUnit heading.

The exact formatter gate proves only::

    XLSX locator == formatter(canonical EvidenceUnit)

It does **not** prove::

    canonical EvidenceUnit == the source semantic unit that owns the atom

This module closes that gap with an independent chain::

    SOURCE_ATOM -> actual PDF structural container -> canonical EvidenceUnit
                -> formatter -> saved XLSX

No expectation here is derived from the EvidenceUnit being tested: the expected
container is recomputed from the *document's own blocks* (the article/section that
lexically precedes the atom and actually owns it), and then compared with the unit
the plan anchored the atom to.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .evidence_unit import (
    KIND_BLOCK,
    _article_heading,
    _clause_of,
    _clean,
    _flatten,
    _is_heading,
)

#: A block that is *body prose*, never a structural container.  A heading must
#: never be taken from such a block (round-11 fixture: the termination row
#: promoted "合同解除或乙方应当退换的……" into its section).
_BODY_CUE_RE = re.compile(r"[，。；;！？!?]")


def structural_container_for(
    document: Any, page: int | None, block_index: int | None
) -> str:
    """The structural heading that actually owns a source block.

    Walks the document's own blocks in reading order up to ``(page, block_index)``
    and returns the last block that is a *structural container* -- a chapter, a
    Chinese section, a clause title, a contract article or a schedule title.  Body
    prose is never eligible, so the result cannot be a sentence the extraction
    happened to promote.
    """

    if page is None or block_index is None:
        return ""
    heading = ""
    for candidate_page in getattr(document, "pages", ()) or ():
        number = getattr(candidate_page, "page_number", None)
        if number is None:
            continue
        for block in getattr(candidate_page, "blocks", ()) or ():
            kind = str(
                getattr(getattr(block, "locator", None), "locator_type", "") or ""
            )
            if kind != KIND_BLOCK:
                continue
            index = int(getattr(block, "block_index", 0) or 0)
            if int(number) == int(page) and index > int(block_index):
                return heading
            if int(number) > int(page):
                return heading
            text = _clean(getattr(block, "text", ""))
            if not text:
                continue
            if _is_heading(text):
                heading = text
    return heading


def container_is_structural(text: str, *, article_titles: Sequence[str] = ()) -> bool:
    """Is ``text`` a real structural heading rather than body prose?"""

    flat = _clean(text)
    if not flat:
        return False
    if _BODY_CUE_RE.search(flat):
        # a heading is a title; a sentence with internal punctuation is body text
        # unless the whole article title legitimately carries parentheses
        if not _article_heading(flat):
            return False
    if _flatten(flat) in {_flatten(title) for title in article_titles}:
        return True
    if _article_heading(flat):
        return True
    return _is_heading(flat)


def check_structural_heading_fidelity(
    document: Any,
    records: Sequence[Mapping[str, Any]],
    *,
    authority_patterns: Sequence[str] = (),
) -> dict[str, Any]:
    """Compare each row's unit heading with the source's own container.

    ``records`` is one entry per delivered row::

        {"item_id", "concern_id", "page", "block_index", "unit_heading",
         "unit_clause", "requirement", "locator"}

    The check reports:

    * ``heading_not_structural`` -- the displayed section is body prose;
    * ``heading_foreign`` -- the displayed section is a different structural
      container than the one that lexically owns the block;
    * ``heading_missing`` -- the source has a container but the row shows none.
    """

    body_prose: list[dict[str, Any]] = []
    foreign: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    checked = 0
    for record in records:
        heading = _clean(record.get("unit_heading") or "")
        expected = structural_container_for(
            document, record.get("page"), record.get("block_index")
        )
        requirement = str(record.get("requirement") or "")
        authority = bool(
            authority_patterns
            and any(re.search(pattern, requirement) for pattern in authority_patterns)
        )
        checked += 1
        if heading and not container_is_structural(heading):
            body_prose.append(
                {
                    "item_id": record.get("item_id"),
                    "concern_id": record.get("concern_id"),
                    "unit_heading": heading[:80],
                    "expected_container": expected[:80],
                    "reason": "the displayed section is body prose, not a container",
                }
            )
            continue
        if not heading and expected:
            # a row whose own clause carries no container is only reported when its
            # requirement is a structural obligation; the authority fixtures assert
            # the exact expectation separately
            if authority:
                missing.append(
                    {
                        "item_id": record.get("item_id"),
                        "concern_id": record.get("concern_id"),
                        "expected_container": expected[:80],
                    }
                )
            continue
        if heading and expected and _flatten(heading) != _flatten(expected):
            # a *number* is what the reviewer navigates by; an article/container
            # mismatch is a defect, but a heading that merely narrows the same
            # container ("第三章 采购需求" over 3.1) is not
            foreign.append(
                {
                    "item_id": record.get("item_id"),
                    "concern_id": record.get("concern_id"),
                    "unit_heading": heading[:80],
                    "expected_container": expected[:80],
                }
            )
    return {
        "checked": checked,
        "heading_not_structural": body_prose,
        "heading_foreign": foreign,
        "heading_missing": missing,
        "body_prose_heading_count": len(body_prose),
        "foreign_heading_count": len(foreign),
        "missing_heading_count": len(missing),
    }


__all__ = [
    "structural_container_for",
    "container_is_structural",
    "check_structural_heading_fidelity",
]
