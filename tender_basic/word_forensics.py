"""Deep, read-only OOXML forensics for DOCX packages.

The source-format builder intentionally writes a small amount of direct
WordprocessingML.  This module audits the package before a human Word open
test.  It is deliberately independent from LibreOffice and does not repair
or resave the document.
"""

from __future__ import annotations

import io
import posixpath
import re
import struct
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
V = "urn:schemas-microsoft-com:vml"
O = "urn:schemas-microsoft-com:office:office"
XML = "http://www.w3.org/XML/1998/namespace"


def q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


def namespace_uri(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def attr(element: ET.Element | None, namespace: str, local: str) -> str | None:
    if element is None:
        return None
    return element.attrib.get(q(namespace, local))


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _positive_int(value: str | None) -> bool:
    parsed = _int(value)
    return parsed is not None and parsed > 0


def _nonnegative_int(value: str | None) -> bool:
    parsed = _int(value)
    return parsed is not None and parsed >= 0


def _relationship_part(source: str) -> str:
    if not source:
        return "_rels/.rels"
    parent, leaf = source.rsplit("/", 1) if "/" in source else ("", source)
    return f"{parent}/_rels/{leaf}.rels" if parent else f"_rels/{leaf}.rels"


def _relationship_source(relationship_part: str) -> str:
    if relationship_part == "_rels/.rels":
        return ""
    parent, leaf = relationship_part.rsplit("/_rels/", 1)
    return f"{parent}/{leaf[:-5]}"


def _resolve_target(source: str, target: str) -> str:
    target = target.split("#", 1)[0]
    if not source:
        return posixpath.normpath(target).lstrip("/")
    return posixpath.normpath(
        posixpath.join(posixpath.dirname(source), target)
    ).lstrip("/")


_ORDER = {
    q(W, "pPr"): (
        "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
        "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd",
        "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
        "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
        "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
        "suppressOverlap", "jc", "textDirection", "textAlignment",
        "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
        "pPrChange",
    ),
    q(W, "rPr"): (
        "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps",
        "strike", "dstrike", "outline", "shadow", "emboss", "imprint",
        "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
        "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
        "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
        "eastAsianLayout", "specVanish", "oMath", "rPrChange",
    ),
    q(W, "tblPr"): (
        "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
        "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
        "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
        "tblDescription", "tblPrChange",
    ),
    q(W, "tcPr"): (
        "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
        "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
        "headers", "cellIns", "cellDel", "cellMerge", "tcPrChange",
    ),
    q(W, "tcBorders"): (
        "top", "left", "bottom", "right", "insideH", "insideV", "tl2br", "tr2bl",
    ),
    q(W, "tcMar"): ("top", "left", "bottom", "right"),
    q(W, "trPr"): (
        "cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter",
        "cantSplit", "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden",
        "ins", "del", "trPrChange",
    ),
    q(W, "tblGrid"): ("gridCol", "tblGridChange"),
    q(W, "sectPr"): (
        "headerReference", "footerReference", "footnotePr", "endnotePr", "type",
        "pgSz", "pgMar", "paperSrc", "pgBorders", "lnNumType", "pgNumType",
        "cols", "formProt", "vAlign", "noEndnote", "titlePg", "textDirection",
        "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange",
    ),
    q(WPS, "wsp"): ("cNvSpPr", "spPr", "txbx", "bodyPr", "extLst"),
    q(WP, "anchor"): (
        "simplePos", "positionH", "positionV", "extent", "effectExtent",
        "wrapNone", "wrapSquare", "wrapTight", "wrapThrough", "wrapTopAndBottom",
        "docPr", "cNvGraphicFramePr", "graphic",
    ),
    q(WP, "inline"): (
        "extent", "effectExtent", "docPr", "cNvGraphicFramePr", "graphic",
    ),
    q(A, "graphicData"): ("pic", "wsp", "wgp", "w14:contentPart"),
    q(A, "graphic"): ("graphicData",),
    q(A, "spPr"): (
        "xfrm", "custGeom", "prstGeom", "noFill", "solidFill", "gradFill",
        "blipFill", "pattFill", "grpFill", "ln", "effectLst", "effectDag",
        "scene3d", "sp3d", "extLst",
    ),
    q(A, "xfrm"): ("off", "chOff", "ext", "chExt"),
    q(A, "prstGeom"): ("avLst",),
    q(A, "ln"): (
        "noFill", "solidFill", "gradFill", "pattFill", "prstDash", "round",
        "bevel", "miter", "headEnd", "tailEnd", "extLst",
    ),
    q(WP, "positionH"): ("align", "posOffset"),
    q(WP, "positionV"): ("align", "posOffset"),
    q(WPS, "bodyPr"): (
        "noAutofit", "normAutofit", "spAutoFit", "prstTxWarp", "scene3d",
        "sp3d", "flatTx", "extLst",
    ),
}

_KNOWN_NAMESPACE_URIS = {
    W, R, PKG_REL, CT, MC, WP, A, WPS, PIC, V, O, XML,
    "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "http://schemas.microsoft.com/office/mac/office/2008/main",
    "urn:schemas-microsoft-com:office:word",
    "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "http://schemas.microsoft.com/office/word/2006/wordml",
    "http://schemas.microsoft.com/office/word/2010/wordml",
}


def _issue(category: str, message: str, part: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"category": category, "part": part, "message": message}
    result.update(details)
    return result


def _check_order(
    element: ET.Element,
    part: str,
    issues: list[dict[str, Any]],
) -> None:
    sequence = _ORDER.get(element.tag)
    if sequence is None:
        return
    ranks = {name: index for index, name in enumerate(sequence)}
    children = list(element)
    names = [local_name(child.tag) for child in children]
    values: list[int] = []
    for child, name in zip(children, names):
        if name not in ranks:
            if namespace_uri(child.tag) == W:
                issues.append(
                    _issue(
                        "schema_order",
                        f"unknown {local_name(element.tag)} child {name}",
                        part,
                        parent=local_name(element.tag),
                        children=names,
                    )
                )
            values.append(len(sequence))
        else:
            values.append(ranks[name])
    for index in range(len(values) - 1):
        if values[index] > values[index + 1]:
            issues.append(
                _issue(
                    "schema_order",
                    f"{local_name(element.tag)} children are not schema ordered",
                    part,
                    parent=local_name(element.tag),
                    children=names,
                    inversion=[names[index], names[index + 1]],
                )
            )


def _iter_word_story_parts(trees: dict[str, ET.Element]) -> Iterable[tuple[str, ET.Element]]:
    for part, tree in trees.items():
        if not part.endswith(".xml"):
            continue
        if part == "word/document.xml" or re.match(
            r"word/(header|footer|footnotes|endnotes|comments)\d*\.xml$", part
        ):
            yield part, tree


def _image_dimensions(data: bytes) -> tuple[int, int] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(data):
                break
            length = struct.unpack(">H", data[index:index + 2])[0]
            if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
                if index + 7 <= len(data):
                    height, width = struct.unpack(">HH", data[index + 3:index + 7])
                    return width, height
            if length < 2:
                break
            index += length
    return None


def _validate_package(
    names: list[str],
    trees: dict[str, ET.Element],
    raw_parts: dict[str, bytes],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    mandatory = ["[Content_Types].xml", "_rels/.rels", "word/document.xml"]
    missing = [part for part in mandatory if part not in names]
    for part in missing:
        issues.append(_issue("missing_package_part", f"missing mandatory part {part}", "package"))

    content_types = trees.get("[Content_Types].xml")
    content_type_info: dict[str, Any] = {"duplicate_defaults": [], "duplicate_overrides": []}
    if content_types is None:
        issues.append(_issue("content_types", "missing [Content_Types].xml", "package"))
    else:
        defaults: dict[str, int] = Counter()
        overrides: dict[str, int] = Counter()
        for child in content_types:
            name = local_name(child.tag)
            if name == "Default":
                defaults[child.attrib.get("Extension", "")] += 1
            elif name == "Override":
                overrides[child.attrib.get("PartName", "")] += 1
        content_type_info["duplicate_defaults"] = [k for k, v in defaults.items() if k and v > 1]
        content_type_info["duplicate_overrides"] = [k for k, v in overrides.items() if k and v > 1]
        for extension in content_type_info["duplicate_defaults"]:
            issues.append(_issue("content_types", f"duplicate Default for .{extension}", "[Content_Types].xml"))
        for part in content_type_info["duplicate_overrides"]:
            issues.append(_issue("content_types", f"duplicate Override for {part}", "[Content_Types].xml"))
        default_extensions = set(defaults)
        override_parts = {part.lstrip("/") for part in overrides}
        for part in names:
            if part == "[Content_Types].xml" or part.endswith(".rels"):
                continue
            extension = part.rsplit(".", 1)[-1] if "." in part else ""
            if part not in override_parts and extension not in default_extensions:
                issues.append(_issue("content_types", f"part has no content type: {part}", "[Content_Types].xml"))
    return content_type_info


def _validate_relationships(
    names: set[str],
    trees: dict[str, ET.Element],
    issues: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    relationship_ids: dict[str, set[str]] = {}
    relations: list[dict[str, Any]] = []
    for part, tree in trees.items():
        if not part.endswith(".rels"):
            continue
        source = _relationship_source(part)
        seen: set[str] = set()
        for relation in tree.findall(q(PKG_REL, "Relationship")):
            relation_id = relation.attrib.get("Id", "")
            target = relation.attrib.get("Target", "")
            if not relation_id:
                issues.append(_issue("relationship", "relationship has no Id", part))
            if relation_id in seen:
                issues.append(_issue("relationship", f"duplicate relationship Id {relation_id}", part, id=relation_id))
            seen.add(relation_id)
            external = relation.attrib.get("TargetMode") == "External"
            resolved = _resolve_target(source, target)
            record = {
                "part": part,
                "source": source,
                "id": relation_id,
                "type": relation.attrib.get("Type", ""),
                "target": target,
                "resolved_target": resolved,
                "external": external,
            }
            relations.append(record)
            if not external and resolved not in names:
                issues.append(_issue("relationship", f"dangling relationship target {resolved}", part, id=relation_id, target=target))
        relationship_ids[part] = seen
    return relationship_ids, relations


def _validate_namespace_usage(
    part: str,
    raw: bytes,
    tree: ET.Element | None,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    control_positions = [
        index for index, value in enumerate(raw)
        if value < 0x20 and value not in {0x09, 0x0A, 0x0D}
    ]
    for index in control_positions[:20]:
        issues.append(_issue("xml_control_character", f"invalid control character at byte {index}", part, byte=index))
    if tree is None:
        return
    try:
        namespace_events = ET.iterparse(io.BytesIO(raw), events=("start-ns",))
        declared = {prefix or "": uri for _event, (prefix, uri) in namespace_events}
    except Exception:
        declared = {}
    prefixes = set(re.findall(rb"(?:<|\s)([A-Za-z_][A-Za-z0-9_.-]*):[A-Za-z_][A-Za-z0-9_.-]*", raw))
    declared_prefixes = {prefix.encode("utf-8") for prefix in declared}
    # ``xmlns:foo`` is a namespace declaration, not a use of a namespace
    # prefix.  The lexical scan must not report ``xmlns`` itself as an
    # undeclared prefix (a false positive on nearly every python-docx file).
    for prefix in sorted(prefixes - declared_prefixes - {b"xml", b"xmlns"}):
        issues.append(_issue("namespace", f"prefix {prefix.decode('ascii', 'replace')} is not declared", part))
    ignorable = attr(tree, MC, "Ignorable")
    if ignorable:
        for prefix in ignorable.split():
            if prefix not in declared:
                issues.append(_issue("namespace", f"mc:Ignorable prefix {prefix} is not declared", part))
    unknown = sorted(
        {
            namespace_uri(element.tag)
            for element in tree.iter()
            if namespace_uri(element.tag) and namespace_uri(element.tag) not in _KNOWN_NAMESPACE_URIS
        }
    )
    if unknown:
        warnings.append(_issue("namespace", "extension namespace retained", part, namespaces=unknown))


def _validate_alternate_content(part: str, tree: ET.Element, issues: list[dict[str, Any]]) -> None:
    for alternate in tree.iter(q(MC, "AlternateContent")):
        choices = [child for child in alternate if child.tag == q(MC, "Choice")]
        fallbacks = [child for child in alternate if child.tag == q(MC, "Fallback")]
        if not choices or len(fallbacks) > 1 or any(child.tag not in {q(MC, "Choice"), q(MC, "Fallback")} for child in alternate):
            issues.append(_issue("alternate_content", "malformed mc:AlternateContent children", part))
        for choice in choices:
            if not choice.attrib.get("Requires", "").strip():
                issues.append(_issue("alternate_content", "mc:Choice has no Requires", part))


def _validate_schema_orders(part: str, tree: ET.Element, issues: list[dict[str, Any]]) -> None:
    for element in tree.iter():
        _check_order(element, part, issues)


def _validate_paragraph_children(part: str, tree: ET.Element, issues: list[dict[str, Any]]) -> None:
    """Catch run content accidentally emitted directly under w:p.

    ``w:br``, ``w:tab``, ``w:t`` and drawing content are all run content in
    WordprocessingML.  LibreOffice is willing to repair some malformed
    paragraph trees while Word may refuse to load the package at all.
    """

    run_only = {q(W, "br"), q(W, "tab"), q(W, "t"), q(W, "drawing"), q(W, "rPr")}
    for paragraph in tree.iter(q(W, "p")):
        for child in paragraph:
            if child.tag in run_only:
                issues.append(
                    _issue(
                        "paragraph_structure",
                        f"{local_name(child.tag)} must be inside w:r",
                        part,
                        parent="p",
                        child=local_name(child.tag),
                    )
                )


def _validate_word_parent_structures(part: str, tree: ET.Element, issues: list[dict[str, Any]]) -> None:
    """Validate the small parent/child topology used by WordprocessingML."""

    def check_single_first(parent: ET.Element, tag: str, label: str) -> None:
        children = [child for child in parent if child.tag == q(W, tag)]
        if len(children) > 1:
            issues.append(_issue("document_structure", f"{label} has duplicate {tag}", part))
        if children and list(parent).index(children[0]) != 0:
            issues.append(_issue("document_structure", f"{tag} must be the first {label} child", part))

    for paragraph in tree.iter(q(W, "p")):
        check_single_first(paragraph, "pPr", "w:p")
    for run in tree.iter(q(W, "r")):
        check_single_first(run, "rPr", "w:r")
    for table in tree.iter(q(W, "tbl")):
        check_single_first(table, "tblPr", "w:tbl")
        children = list(table)
        grid_positions = [index for index, child in enumerate(children) if child.tag == q(W, "tblGrid")]
        if len(grid_positions) > 1:
            issues.append(_issue("table_structure", "table has duplicate tblGrid", part))
        if grid_positions and not any(child.tag == q(W, "tblPr") for child in children[:grid_positions[0]]):
            issues.append(_issue("table_structure", "tblGrid must follow tblPr", part))
        for child in children:
            if child.tag not in {q(W, "tblPr"), q(W, "tblGrid"), q(W, "tr"), q(W, "sdt"), q(W, "customXml"), q(W, "altChunk") }:
                issues.append(_issue("table_structure", f"unsupported direct table child {local_name(child.tag)}", part))
    for row in tree.iter(q(W, "tr")):
        check_single_first(row, "trPr", "w:tr")
        for child in row:
            if child.tag not in {q(W, "trPr"), q(W, "tblPrEx"), q(W, "tc"), q(W, "sdt"), q(W, "customXml"), q(W, "altChunk") }:
                issues.append(_issue("table_row", f"unsupported direct row child {local_name(child.tag)}", part))
    for cell in tree.iter(q(W, "tc")):
        check_single_first(cell, "tcPr", "w:tc")
        content = [
            child
            for child in cell
            if child.tag not in {q(W, "tcPr"), q(W, "customXml"), q(W, "sdt"), q(W, "altChunk")}
        ]
        if not content:
            issues.append(_issue("table_cell", "table cell has no block content", part))
        for child in content:
            if child.tag not in {q(W, "p"), q(W, "tbl"), q(W, "customXml"), q(W, "sdt"), q(W, "altChunk") }:
                issues.append(_issue("table_cell", f"unsupported direct cell child {local_name(child.tag)}", part))


def _validate_unique_xml_ids(trees: dict[str, ET.Element], issues: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Check ids that Word uses as package/story-wide drawing identifiers."""

    drawing_ids: dict[str, list[str]] = {}
    nonvisual_ids: dict[str, list[str]] = {}
    for part, tree in trees.items():
        if not part.endswith(".xml"):
            continue
        for element in tree.iter(q(WP, "docPr")):
            value = element.attrib.get("id")
            if value:
                drawing_ids.setdefault(value, []).append(part)
        for element in tree.iter(q(PIC, "cNvPr")):
            value = element.attrib.get("id")
            if value:
                nonvisual_ids.setdefault(value, []).append(part)
        for element in tree.iter(q(W, "bookmarkStart")):
            value = attr(element, W, "id")
            if value is not None and _int(value) is None:
                issues.append(_issue("bookmark", f"bookmark id is not an integer: {value}", part))
        for element in tree.iter(q(W, "bookmarkEnd")):
            value = attr(element, W, "id")
            if value is not None and _int(value) is None:
                issues.append(_issue("bookmark", f"bookmark id is not an integer: {value}", part))
    for value, parts in drawing_ids.items():
        if len(parts) > 1:
            issues.append(_issue("drawing_id", f"duplicate wp:docPr id {value}", "package", ids=[value], parts=parts))
    for value, parts in nonvisual_ids.items():
        if len(parts) > 1:
            issues.append(_issue("drawing_id", f"duplicate pic:cNvPr id {value}", "package", ids=[value], parts=parts))
    return {
        "docPr_ids": sorted(drawing_ids),
        "pic_cNvPr_ids": sorted(nonvisual_ids),
    }


def _validate_sect_pr(part: str, tree: ET.Element, issues: list[dict[str, Any]]) -> dict[str, Any]:
    if part != "word/document.xml":
        return {"body_sectPr": 0, "paragraph_sectPr": 0}
    bodies = list(tree.findall(q(W, "body")))
    stats = {"body_sectPr": 0, "paragraph_sectPr": 0}
    if len(bodies) != 1:
        issues.append(_issue("document_structure", "document must contain exactly one w:body", part))
        return stats
    body = bodies[0]
    direct = list(body)
    body_sect = [element for element in direct if element.tag == q(W, "sectPr")]
    stats["body_sectPr"] = len(body_sect)
    if len(body_sect) != 1:
        issues.append(_issue("sectPr", "w:body must contain exactly one final w:sectPr", part, count=len(body_sect)))
    elif direct[-1] is not body_sect[0]:
        issues.append(_issue("sectPr", "body w:sectPr must be the last body child", part))
    for child in direct:
        if child.tag == q(W, "tc"):
            issues.append(_issue("document_structure", "orphan w:tc directly under body", part))
        if child.tag not in {q(W, "p"), q(W, "tbl"), q(W, "sdt"), q(W, "customXml"), q(W, "altChunk"), q(W, "sectPr")}:
            issues.append(_issue("document_structure", f"unsupported direct body child {local_name(child.tag)}", part))
    for ppr in tree.iter(q(W, "pPr")):
        sect = [child for child in ppr if child.tag == q(W, "sectPr")]
        if sect:
            stats["paragraph_sectPr"] += len(sect)
            if ppr[-1] is not sect[-1]:
                issues.append(_issue("sectPr", "paragraph w:sectPr must be the last pPr child", part))
    for sect in tree.iter(q(W, "sectPr")):
        if sect is not body_sect[0] if body_sect else False:
            parent = None
            for candidate in tree.iter():
                if sect in list(candidate):
                    parent = candidate
                    break
            if parent is not None and parent.tag != q(W, "pPr"):
                issues.append(_issue("sectPr", "non-body w:sectPr must be inside paragraph properties", part))
    return stats


def _tc_properties(tc: ET.Element) -> ET.Element | None:
    return next((child for child in tc if child.tag == q(W, "tcPr")), None)


def _property_child(properties: ET.Element | None, name: str) -> ET.Element | None:
    if properties is None:
        return None
    return next((child for child in properties if child.tag == q(W, name)), None)


def _grid_value(element: ET.Element | None, name: str = "val") -> int:
    if element is None:
        return 0
    return _int(attr(element, W, name)) or 0


def _validate_tables(part: str, tree: ET.Element, issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    tables = list(tree.iter(q(W, "tbl")))
    stats = {"tables": len(tables), "nested_tables": 0, "rows": 0, "cells": 0, "merged_cells": 0}
    for table_index, table in enumerate(tables):
        parent = None
        for candidate in tree.iter():
            if table in list(candidate):
                parent = candidate
                break
        if parent is not None and parent.tag == q(W, "tc"):
            stats["nested_tables"] += 1
        tbl_pr = next((child for child in table if child.tag == q(W, "tblPr")), None)
        tbl_grid = next((child for child in table if child.tag == q(W, "tblGrid")), None)
        if tbl_pr is None or tbl_grid is None:
            issues.append(_issue("table_structure", "table must contain tblPr and tblGrid", part, table_index=table_index))
            continue
        grid_cols = [child for child in tbl_grid if child.tag == q(W, "gridCol")]
        if not grid_cols:
            issues.append(_issue("table_grid", "table has zero grid columns", part, table_index=table_index))
            continue
        widths: list[int] = []
        for column_index, column in enumerate(grid_cols):
            value = _int(attr(column, W, "w"))
            if value is None or value <= 0:
                issues.append(_issue("table_grid", "gridCol width must be positive", part, table_index=table_index, column_index=column_index))
                widths.append(0)
            else:
                widths.append(value)
        grid_count = len(grid_cols)
        table_width_element = _property_child(tbl_pr, "tblW")
        table_width = _int(attr(table_width_element, W, "w"))
        table_type = attr(table_width_element, W, "type") if table_width_element is not None else None
        if table_type == "dxa" and table_width is not None and abs(sum(widths) - table_width) > 80:
            issues.append(_issue("table_width", "tblW differs materially from tblGrid width", part, table_index=table_index, tblW=table_width, grid_width=sum(widths)))
        active_merges: dict[int, bool] = {}
        rows = [child for child in table if child.tag == q(W, "tr")]
        if not rows:
            issues.append(_issue("table_structure", "table has no rows", part, table_index=table_index))
        stats["rows"] += len(rows)
        for row_index, row in enumerate(rows):
            tr_pr = next((child for child in row if child.tag == q(W, "trPr")), None)
            grid_before = _grid_value(_property_child(tr_pr, "gridBefore"))
            grid_after = _grid_value(_property_child(tr_pr, "gridAfter"))
            cells = [child for child in row if child.tag == q(W, "tc")]
            if not cells:
                issues.append(_issue("table_row", "row has no cells", part, table_index=table_index, row_index=row_index))
            offset = grid_before
            stats["cells"] += len(cells)
            occupied: set[int] = set()
            for cell_index, cell in enumerate(cells):
                if cell.tag != q(W, "tc"):
                    issues.append(_issue("table_structure", "non-cell child in row", part, table_index=table_index, row_index=row_index))
                    continue
                tc_pr = _tc_properties(cell)
                span_element = _property_child(tc_pr, "gridSpan")
                span = _grid_value(span_element)
                if span_element is not None and span <= 0:
                    issues.append(_issue("merge", "gridSpan must be positive", part, table_index=table_index, row_index=row_index, cell_index=cell_index))
                    span = 1
                span = max(1, span)
                if span > 1:
                    stats["merged_cells"] += 1
                if offset + span > grid_count:
                    issues.append(_issue("table_grid", "row cells exceed tblGrid", part, table_index=table_index, row_index=row_index, cell_index=cell_index, offset=offset, span=span, grid_count=grid_count))
                for column in range(offset, min(grid_count, offset + span)):
                    occupied.add(column)
                v_merge = _property_child(tc_pr, "vMerge")
                if v_merge is not None:
                    value = attr(v_merge, W, "val") or "continue"
                    if value not in {"restart", "continue"}:
                        issues.append(_issue("merge", f"invalid vMerge value {value}", part, table_index=table_index, row_index=row_index, cell_index=cell_index))
                    elif value == "continue" and not all(active_merges.get(column, False) for column in range(offset, offset + span)):
                        issues.append(_issue("merge", "vMerge continue has no active restart above", part, table_index=table_index, row_index=row_index, cell_index=cell_index))
                    elif value == "restart":
                        for column in range(offset, offset + span):
                            active_merges[column] = True
                else:
                    for column in range(offset, offset + span):
                        active_merges.pop(column, None)
                h_merge = _property_child(tc_pr, "hMerge")
                if h_merge is not None:
                    value = attr(h_merge, W, "val") or "continue"
                    if value not in {"restart", "continue"}:
                        issues.append(_issue("merge", f"invalid hMerge value {value}", part, table_index=table_index, row_index=row_index, cell_index=cell_index))
                tc_width = _property_child(tc_pr, "tcW")
                cell_width = _int(attr(tc_width, W, "w"))
                cell_type = attr(tc_width, W, "type") if tc_width is not None else None
                expected = sum(widths[offset:min(grid_count, offset + span)])
                if cell_type == "dxa" and cell_width is not None and expected and abs(cell_width - expected) > 120:
                    warnings.append(_issue("table_width", "tcW differs from its grid span", part, table_index=table_index, row_index=row_index, cell_index=cell_index, tcW=cell_width, grid_span_width=expected))
                for nested in cell.iter(q(W, "tc")):
                    if nested is cell:
                        continue
                    parent_tag = None
                    for candidate in cell.iter():
                        if nested in list(candidate):
                            parent_tag = candidate.tag
                            break
                    if parent_tag != q(W, "tr"):
                        issues.append(_issue("table_structure", "orphan nested table cell", part, table_index=table_index, row_index=row_index, cell_index=cell_index))
                offset += span
            if offset + grid_after != grid_count:
                issues.append(_issue("table_grid", "row gridBefore/gridAfter and cells do not match tblGrid", part, table_index=table_index, row_index=row_index, grid_count=grid_count, occupied=offset + grid_after))
    return stats


def _validate_drawings(
    part: str,
    tree: ET.Element,
    raw_parts: dict[str, bytes],
    relations: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    drawings = list(tree.iter(q(W, "drawing")))
    anchors = list(tree.iter(q(WP, "anchor")))
    inlines = list(tree.iter(q(WP, "inline")))
    doc_pr_ids: list[str] = []
    relation_by_id = {(item["part"], item["id"]): item for item in relations}
    local_relations = {item["id"]: item for item in relations if item["source"] == part}
    for drawing in drawings:
        children = [child for child in drawing if child.tag in {q(WP, "anchor"), q(WP, "inline")}]
        if len(children) != 1:
            issues.append(_issue("drawing", "w:drawing must contain exactly one wp:anchor or wp:inline", part))
    for container in [*anchors, *inlines]:
        extent = next((child for child in container if child.tag == q(WP, "extent")), None)
        if extent is None or not _positive_int(extent.attrib.get("cx")) or not _positive_int(extent.attrib.get("cy")):
            issues.append(_issue("drawing", "drawing extent must have positive cx/cy", part))
        doc_pr = next((child for child in container if child.tag == q(WP, "docPr")), None)
        if doc_pr is None or not _positive_int(doc_pr.attrib.get("id")) or not doc_pr.attrib.get("name"):
            issues.append(_issue("drawing", "drawing docPr requires positive id and name", part))
        else:
            doc_pr_ids.append(doc_pr.attrib["id"])
        for position_name in ("positionH", "positionV"):
            position = next((child for child in container if child.tag == q(WP, position_name)), None)
            if position is not None:
                if position.attrib.get("relativeFrom") not in {"page", "margin", "column", "character", "line", "paragraph"}:
                    issues.append(_issue("drawing", f"invalid {position_name} relativeFrom", part, value=position.attrib.get("relativeFrom")))
                offset = next((child for child in position if local_name(child.tag) == "posOffset"), None)
                if offset is None or _int(offset.text) is None:
                    issues.append(_issue("drawing", f"{position_name} requires integer posOffset", part))
        graphic_data = next((child for child in container.iter(q(A, "graphicData"))), None)
        if graphic_data is not None:
            uri = graphic_data.attrib.get("uri", "")
            expected = q(WPS, "wsp") if "word/2010/wordprocessingShape" in uri else None
            if expected is not None and not any(child.tag == expected for child in graphic_data):
                issues.append(_issue("drawing", "graphicData URI does not match its child", part, uri=uri))
        for blip in container.iter(q(A, "blip")):
            for relation_attribute in ("embed", "link"):
                relation_id = attr(blip, R, relation_attribute)
                if relation_id:
                    relation = local_relations.get(relation_id)
                    if relation is None:
                        issues.append(_issue("drawing_relationship", f"drawing references unknown r:{relation_attribute} {relation_id}", part))
                    elif not relation["external"]:
                        data = raw_parts.get(relation["resolved_target"])
                        if data is None:
                            issues.append(_issue("drawing_relationship", "image relationship target missing", part, id=relation_id, target=relation["resolved_target"]))
                        elif _image_dimensions(data) is None:
                            warnings.append(_issue("drawing", "image dimensions could not be decoded", part, target=relation["resolved_target"]))
    duplicate_ids = sorted(value for value, count in Counter(doc_pr_ids).items() if count > 1)
    if duplicate_ids:
        issues.append(_issue("drawing_id", "duplicate wp:docPr ids", part, ids=duplicate_ids))
    return {"drawings": len(drawings), "anchors": len(anchors), "inlines": len(inlines), "docPr_ids": doc_pr_ids}


def _validate_bookmarks_hyperlinks_fields(part: str, tree: ET.Element, relationship_ids: set[str], issues: list[dict[str, Any]]) -> dict[str, Any]:
    starts = list(tree.iter(q(W, "bookmarkStart")))
    ends = list(tree.iter(q(W, "bookmarkEnd")))
    start_ids = [attr(element, W, "id") for element in starts]
    end_ids = [attr(element, W, "id") for element in ends]
    start_set = {value for value in start_ids if value is not None}
    end_set = {value for value in end_ids if value is not None}
    for value, count in Counter(start_ids).items():
        if value is not None and count > 1:
            issues.append(_issue("bookmark", f"duplicate bookmarkStart id {value}", part))
    for value, count in Counter(end_ids).items():
        if value is not None and count > 1:
            issues.append(_issue("bookmark", f"duplicate bookmarkEnd id {value}", part))
    if start_set != end_set:
        issues.append(_issue("bookmark", "bookmark starts and ends do not pair", part, orphan_starts=sorted(start_set - end_set), orphan_ends=sorted(end_set - start_set)))
    names = {attr(element, W, "name") for element in starts if attr(element, W, "name")}
    for hyperlink in tree.iter(q(W, "hyperlink")):
        relation_id = attr(hyperlink, R, "id")
        anchor = attr(hyperlink, W, "anchor")
        if not relation_id and not anchor:
            issues.append(_issue("hyperlink", "hyperlink has neither relationship nor anchor", part))
        if relation_id and relation_id not in relationship_ids:
            issues.append(_issue("hyperlink", f"hyperlink references unknown relationship {relation_id}", part))
        if anchor and anchor not in names and not anchor.startswith("_"):
            issues.append(_issue("hyperlink", f"internal hyperlink anchor {anchor} has no bookmark", part))
    stack: list[str] = []
    field_counts = Counter()
    for element in tree.iter():
        if element.tag != q(W, "fldChar"):
            continue
        field_type = attr(element, W, "fldCharType")
        field_counts[field_type or ""] += 1
        if field_type == "begin":
            stack.append("begin")
        elif field_type == "separate":
            if not stack:
                issues.append(_issue("field_code", "field separator without begin", part))
        elif field_type == "end":
            if not stack:
                issues.append(_issue("field_code", "field end without begin", part))
            else:
                stack.pop()
        else:
            issues.append(_issue("field_code", f"invalid fldCharType {field_type}", part))
    if stack:
        issues.append(_issue("field_code", "field begin is not closed", part, open_fields=len(stack)))
    for field in tree.iter(q(W, "fldSimple")):
        if not attr(field, W, "instr") and not any(child.tag == q(W, "instrText") for child in field.iter()):
            issues.append(_issue("field_code", "fldSimple has no instruction", part))
    return {"bookmark_starts": len(starts), "bookmark_ends": len(ends), "hyperlinks": sum(1 for _ in tree.iter(q(W, "hyperlink"))), "field_chars": sum(field_counts.values())}


def _validate_styles(trees: dict[str, ET.Element], issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    styles = trees.get("word/styles.xml")
    if styles is None:
        warnings.append(_issue("styles", "word/styles.xml is absent", "word/styles.xml"))
        return {"style_count": 0, "style_ids": []}
    style_elements = list(styles.iter(q(W, "style")))
    style_ids = [attr(style, W, "styleId") for style in style_elements]
    valid_ids = {value for value in style_ids if value}
    for value, count in Counter(style_ids).items():
        if value and count > 1:
            issues.append(_issue("styles", f"duplicate styleId {value}", "word/styles.xml"))
    allowed_types = {"paragraph", "character", "table", "numbering"}
    for style in style_elements:
        style_id = attr(style, W, "styleId") or ""
        style_type = attr(style, W, "type")
        if style_type not in allowed_types:
            issues.append(_issue("styles", f"invalid style type {style_type}", "word/styles.xml", style_id=style_id))
        for reference_name in ("basedOn", "next", "link"):
            reference = _property_child(style, reference_name)
            value = attr(reference, W, "val")
            if value and value not in valid_ids:
                issues.append(_issue("styles", f"style {style_id} references missing {reference_name} {value}", "word/styles.xml"))
    defaults = [style for style in style_elements if attr(style, W, "default") in {"1", "true", "on"}]
    default_types = [attr(style, W, "type") for style in defaults]
    for style_type, count in Counter(default_types).items():
        if style_type and count > 1:
            issues.append(_issue("styles", f"duplicate default style type {style_type}", "word/styles.xml"))
    latent = styles.find(q(W, "latentStyles"))
    if latent is not None:
        for exception in latent.findall(q(W, "lsdException")):
            if not attr(exception, W, "name"):
                issues.append(_issue("styles", "latent style exception has no name", "word/styles.xml"))
    for part, tree in _iter_word_story_parts(trees):
        for element in tree.iter():
            if element.tag in {q(W, "pStyle"), q(W, "rStyle"), q(W, "tblStyle")}:
                value = attr(element, W, "val")
                if value and value not in valid_ids:
                    issues.append(_issue("styles", f"story references missing style {value}", part))
    return {"style_count": len(style_elements), "style_ids": sorted(valid_ids)}


def _validate_numbering(trees: dict[str, ET.Element], issues: list[dict[str, Any]]) -> dict[str, Any]:
    numbering = trees.get("word/numbering.xml")
    if numbering is None:
        return {"abstract_num_count": 0, "num_count": 0}
    abstract = list(numbering.iter(q(W, "abstractNum")))
    nums = list(numbering.iter(q(W, "num")))
    abstract_ids = {attr(element, W, "abstractNumId") for element in abstract if attr(element, W, "abstractNumId") is not None}
    num_ids = {attr(element, W, "numId") for element in nums if attr(element, W, "numId") is not None}
    for group, label in (([attr(element, W, "abstractNumId") for element in abstract], "abstractNumId"), ([attr(element, W, "numId") for element in nums], "numId")):
        for value, count in Counter(group).items():
            if value is not None and count > 1:
                issues.append(_issue("numbering", f"duplicate {label} {value}", "word/numbering.xml"))
    for num in nums:
        reference = _property_child(num, "abstractNumId")
        value = attr(reference, W, "val")
        if value not in abstract_ids:
            issues.append(_issue("numbering", f"num references missing abstractNumId {value}", "word/numbering.xml"))
    for part, tree in _iter_word_story_parts(trees):
        for num_pr in tree.iter(q(W, "numPr")):
            num_id_element = _property_child(num_pr, "numId")
            num_id = attr(num_id_element, W, "val")
            if num_id not in num_ids:
                issues.append(_issue("numbering", f"story references missing numId {num_id}", part))
            ilvl = _property_child(num_pr, "ilvl")
            if ilvl is not None and not _nonnegative_int(attr(ilvl, W, "val")):
                issues.append(_issue("numbering", "numPr ilvl must be nonnegative", part))
    return {"abstract_num_count": len(abstract), "num_count": len(nums)}


def _validate_story_relationship_attributes(
    trees: dict[str, ET.Element],
    relationship_ids: dict[str, set[str]],
    issues: list[dict[str, Any]],
) -> dict[str, int]:
    references = 0
    for part, tree in _iter_word_story_parts(trees):
        expected = relationship_ids.get(_relationship_part(part), set())
        for element in tree.iter():
            for namespace, local in ((R, "id"), (R, "embed"), (R, "link")):
                value = attr(element, namespace, local)
                if value:
                    references += 1
                    if value not in expected:
                        issues.append(_issue("relationship", f"dangling r:{local} {value}", part, id=value))
    return {"relationship_attributes": references}


def _validate_headers_footers(
    trees: dict[str, ET.Element],
    relationships: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, int]:
    by_source_id = {(item["source"], item["id"]): item for item in relationships}
    section_references = 0
    for element in trees.get("word/document.xml", ET.Element("empty")).iter(q(W, "headerReference")):
        section_references += 1
        value = attr(element, R, "id")
        relation = by_source_id.get(("word/document.xml", value or ""))
        if relation is None or not relation["resolved_target"].startswith("word/header"):
            issues.append(_issue("header_footer", "headerReference does not target a header part", "word/document.xml", id=value))
    for element in trees.get("word/document.xml", ET.Element("empty")).iter(q(W, "footerReference")):
        section_references += 1
        value = attr(element, R, "id")
        relation = by_source_id.get(("word/document.xml", value or ""))
        if relation is None or not relation["resolved_target"].startswith("word/footer"):
            issues.append(_issue("header_footer", "footerReference does not target a footer part", "word/document.xml", id=value))
    return {"section_references": section_references, "header_parts": sum(name.startswith("word/header") for name in trees), "footer_parts": sum(name.startswith("word/footer") for name in trees)}


def inspect_docx_ooxml(path: str | Path) -> dict[str, Any]:
    """Return a detailed forensic report for one DOCX package."""

    package_path = Path(path)
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "path": str(package_path),
        "package": {
            "zip_integrity": "FAIL",
            "duplicate_zip_entries": [],
            "missing_required_parts": [],
            "content_types": {},
            "relationship_parts": 0,
            "xml_parts": 0,
        },
        "xml": {"well_formed": "FAIL", "parts": [], "parse_errors": [], "namespace_errors": [], "control_character_errors": []},
        "structure": {"schema_order_errors": [], "sectPr": {}, "tables": {}, "drawings": {}, "bookmarks_hyperlinks_fields": {}, "unique_ids": {}},
        "styles": {},
        "numbering": {},
        "headers_footers": {},
        "relationships": {"errors": [], "references": 0},
        "warnings": [],
        "errors": [],
        "result": "FAIL",
    }
    if not package_path.is_file():
        report["errors"].append(_issue("package", f"DOCX does not exist: {package_path}", "package"))
        return report
    try:
        archive = zipfile.ZipFile(package_path)
    except Exception as exc:
        report["errors"].append(_issue("package", f"not a ZIP package: {exc}", "package"))
        return report
    with archive:
        entries = archive.infolist()
        names_list = [entry.filename for entry in entries]
        names = set(names_list)
        duplicate_names = sorted(name for name, count in Counter(names_list).items() if count > 1)
        report["package"]["duplicate_zip_entries"] = duplicate_names
        if duplicate_names:
            report["errors"].append(_issue("package", "duplicate ZIP entries", "package", entries=duplicate_names))
        bad_entry = archive.testzip()
        report["package"]["zip_integrity"] = "PASS" if bad_entry is None else "FAIL"
        if bad_entry is not None:
            report["errors"].append(_issue("package", f"ZIP CRC failure: {bad_entry}", "package"))
        raw_parts = {name: archive.read(name) for name in names}
        trees: dict[str, ET.Element] = {}
        for name in sorted(names):
            if not (name.endswith(".xml") or name.endswith(".rels")):
                continue
            report["xml"]["parts"].append(name)
            try:
                tree = ET.fromstring(raw_parts[name])
            except Exception as exc:
                report["xml"]["parse_errors"].append({"part": name, "error": str(exc)})
                report["errors"].append(_issue("xml", str(exc), name))
                # Still scan the raw bytes when parsing fails.  This makes an
                # illegal XML control character explicit instead of hiding it
                # behind the generic parser exception.
                _validate_namespace_usage(name, raw_parts[name], None, report["errors"], report["warnings"])
                continue
            trees[name] = tree
            _validate_namespace_usage(name, raw_parts[name], tree, report["errors"], report["warnings"])
            _validate_alternate_content(name, tree, report["errors"])
        report["package"]["xml_parts"] = sum(name.endswith(".xml") for name in trees)
        report["package"]["relationship_parts"] = sum(name.endswith(".rels") for name in trees)
        report["xml"]["well_formed"] = "PASS" if not report["xml"]["parse_errors"] else "FAIL"
        report["xml"]["namespace_errors"] = [item for item in report["errors"] if item["category"] == "namespace"]
        report["xml"]["control_character_errors"] = [item for item in report["errors"] if item["category"] == "xml_control_character"]
        report["package"]["missing_required_parts"] = [part for part in ("[Content_Types].xml", "_rels/.rels", "word/document.xml") if part not in names]
        report["package"]["content_types"] = _validate_package(names_list, trees, raw_parts, report["errors"], report["warnings"])
        relationship_ids, relations = _validate_relationships(names, trees, report["errors"])
        report["relationships"]["errors"] = [item for item in report["errors"] if item["category"] == "relationship"]
        report["relationships"]["references"] = _validate_story_relationship_attributes(trees, relationship_ids, report["errors"])["relationship_attributes"]
        for part, tree in trees.items():
            _validate_schema_orders(part, tree, report["errors"])
            _validate_paragraph_children(part, tree, report["errors"])
            _validate_word_parent_structures(part, tree, report["errors"])
        report["structure"]["schema_order_errors"] = [item for item in report["errors"] if item["category"] == "schema_order"]
        report["structure"]["unique_ids"] = _validate_unique_xml_ids(trees, report["errors"])
        document = trees.get("word/document.xml")
        if document is not None:
            report["structure"]["sectPr"] = _validate_sect_pr("word/document.xml", document, report["errors"])
        table_stats: dict[str, Any] = {}
        drawing_stats: dict[str, Any] = {}
        link_stats: dict[str, Any] = {}
        for part, tree in _iter_word_story_parts(trees):
            table_stats[part] = _validate_tables(part, tree, report["errors"], report["warnings"])
            drawing_stats[part] = _validate_drawings(part, tree, raw_parts, relations, report["errors"], report["warnings"])
            link_stats[part] = _validate_bookmarks_hyperlinks_fields(part, tree, relationship_ids.get(_relationship_part(part), set()), report["errors"])
        report["structure"]["tables"] = table_stats
        report["structure"]["drawings"] = drawing_stats
        report["structure"]["bookmarks_hyperlinks_fields"] = link_stats
        report["styles"] = _validate_styles(trees, report["errors"], report["warnings"])
        report["numbering"] = _validate_numbering(trees, report["errors"])
        report["headers_footers"] = _validate_headers_footers(trees, relations, report["errors"])
        # Header/footer parts must exist as XML when an internal relationship
        # targets them; the general relationship check covers the target, but
        # this gives the report a Word-specific diagnostic.
        for relation in relations:
            if relation["external"]:
                continue
            target = relation["resolved_target"]
            if target.startswith("word/header") or target.startswith("word/footer"):
                if target not in trees:
                    report["errors"].append(_issue("header_footer", f"header/footer target is not XML: {target}", relation["part"]))
    report["errors"] = list(report["errors"])
    report["result"] = "PASS" if not report["errors"] else "FAIL"
    report["summary"] = {
        "error_count": len(report["errors"]),
        "warning_count": len(report["warnings"]),
        "error_categories": dict(Counter(item["category"] for item in report["errors"])),
        "warning_categories": dict(Counter(item["category"] for item in report["warnings"])),
    }
    return report


__all__ = ["inspect_docx_ooxml"]
