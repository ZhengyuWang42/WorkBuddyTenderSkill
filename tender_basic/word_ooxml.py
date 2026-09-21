"""Read-only OOXML package checks used by the Word acceptance gate.

The source-format DOCX builder intentionally emits a small amount of direct
OOXML because ``python-docx`` has no public API for positioned text boxes.
This module keeps package checks independent of LibreOffice and of the Word
COM gate.  A package can still require Word review when this scanner finds no
issue, but a known schema-order or relationship defect is never hidden behind
a successful LibreOffice render.
"""

from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path
from typing import Any
from collections import Counter
from docx import Document
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPE_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def _q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def _relationship_source(relationship_part: str) -> str:
    if relationship_part == "_rels/.rels":
        return ""
    parent, leaf = relationship_part.rsplit("/_rels/", 1)
    return f"{parent}/{leaf[:-5]}"


def _resolve_target(source: str, target: str) -> str:
    if not source:
        return posixpath.normpath(target).lstrip("/")
    return posixpath.normpath(
        posixpath.join(posixpath.dirname(source), target)
    ).lstrip("/")


def _xml_parts(
    zipped: zipfile.ZipFile,
) -> tuple[dict[str, ET.Element], list[dict[str, str]]]:
    trees: dict[str, ET.Element] = {}
    errors: list[dict[str, str]] = []
    for name in sorted(zipped.namelist()):
        if not (name.endswith(".xml") or name.endswith(".rels")):
            continue
        try:
            trees[name] = ET.fromstring(zipped.read(name))
        except Exception as exc:  # pragma: no cover - depends on corrupt input
            errors.append({"part": name, "error": str(exc)})
    return trees, errors


def scan_docx_package(path: str | Path) -> dict[str, Any]:
    """Scan one DOCX package without opening or rewriting it."""

    package_path = Path(path)
    result: dict[str, Any] = {
        "path": str(package_path),
        "zip_integrity": "FAIL",
        "xml_well_formed": "FAIL",
        "content_types": "FAIL",
        "relationship_targets": "FAIL",
        "dangling_relationship_ids": [],
        "duplicate_relationship_ids": [],
        "missing_package_parts": [],
        "schema_order_errors": [],
        "drawing_id_errors": [],
        "bookmark_id_errors": [],
        "parts": [],
        "counts": {},
        "errors": [],
        "zip_valid": False,
        "xml_valid": False,
        "relationship_targets_missing": [],
        "content_type_targets_missing": [],
        "missing_style_refs": [],
        "missing_numbering_refs": [],
        "missing_header_footer_parts": [],
        "invalid_note_settings": [],
        "dangling_relationships": [],
        "duplicate_ids": [],
        "unsafe_ooxml": 1,
        "python_docx_reopen": False,
        "result": "FAIL",
    }
    if not package_path.is_file():
        result["errors"].append(f"DOCX does not exist: {package_path}")
        return result

    try:
        zipped = zipfile.ZipFile(package_path)
    except Exception as exc:
        result["errors"].append(f"DOCX is not a ZIP package: {exc}")
        return result

    with zipped:
        bad_entry = zipped.testzip()
        result["zip_integrity"] = "PASS" if bad_entry is None else "FAIL"
        result["zip_valid"] = bad_entry is None
        if bad_entry is not None:
            result["errors"].append(f"ZIP CRC failure: {bad_entry}")
        names = set(zipped.namelist())
        result["parts"] = sorted(names)
        trees, xml_errors = _xml_parts(zipped)
        result["errors"].extend(
            f"{item['part']}: {item['error']}" for item in xml_errors
        )
        result["xml_well_formed"] = "PASS" if not xml_errors else "FAIL"
        result["xml_valid"] = not xml_errors

        content_types = trees.get("[Content_Types].xml")
        if content_types is None:
            result["errors"].append("Missing [Content_Types].xml")
        else:
            overrides = {
                item.attrib.get("PartName", "").lstrip("/")
                for item in content_types.findall(_q(CONTENT_TYPE_NS, "Override"))
            }
            defaults = {
                item.attrib.get("Extension", "")
                for item in content_types.findall(_q(CONTENT_TYPE_NS, "Default"))
            }
            missing_override_targets = sorted(part for part in overrides if part not in names)
            result["content_type_targets_missing"] = missing_override_targets
            missing_types = []
            for part in sorted(names):
                if part in {"[Content_Types].xml"} or part.endswith(".rels"):
                    continue
                extension = part.rsplit(".", 1)[-1] if "." in part else ""
                if part not in overrides and extension not in defaults:
                    missing_types.append(part)
            if missing_types:
                result["missing_package_parts"].extend(
                    {"kind": "content_type", "part": part}
                    for part in missing_types
                )
            result["content_types"] = "PASS" if not missing_types and not missing_override_targets else "FAIL"

        all_rel_ids: dict[str, set[str]] = {}
        relationship_targets_by_source: dict[tuple[str, str], str] = {}
        relationship_types_by_source: dict[str, set[str]] = {}
        relationship_errors: list[dict[str, str]] = []
        for relationship_part, rel_root in trees.items():
            if not relationship_part.endswith(".rels"):
                continue
            source = _relationship_source(relationship_part)
            seen: set[str] = set()
            rel_ids: set[str] = set()
            for relation in rel_root.findall(_q(PKG_REL_NS, "Relationship")):
                relation_id = relation.attrib.get("Id", "")
                if relation_id in seen:
                    result["duplicate_relationship_ids"].append(
                        {"part": relationship_part, "id": relation_id}
                    )
                seen.add(relation_id)
                rel_ids.add(relation_id)
                target = relation.attrib.get("Target", "")
                if relation.attrib.get("TargetMode") == "External":
                    continue
                resolved = _resolve_target(source, target)
                relationship_targets_by_source[(source, relation_id)] = resolved
                relationship_types_by_source.setdefault(source, set()).add(
                    relation.attrib.get("Type", "")
                )
                if resolved not in names:
                    missing = {
                        "kind": "relationship_target",
                        "part": relationship_part,
                        "id": relation_id,
                        "target": resolved,
                    }
                    result["missing_package_parts"].append(missing)
                    relationship_errors.append(missing)
            all_rel_ids[relationship_part] = rel_ids
        result["relationship_targets"] = "PASS" if not relationship_errors else "FAIL"
        result["relationship_targets_missing"] = relationship_errors

        dangling: list[dict[str, str]] = []
        for part, tree in trees.items():
            referenced_ids = {
                value
                for element in tree.iter()
                for attribute, value in element.attrib.items()
                if attribute == _q(R_NS, "id")
            }
            if not referenced_ids or part.endswith(".rels"):
                continue
            if part == "word/document.xml":
                relationship_part = "word/_rels/document.xml.rels"
            elif part.endswith(".xml"):
                parent = part.rsplit("/", 1)[0] if "/" in part else ""
                leaf = part.rsplit("/", 1)[-1]
                relationship_part = (
                    f"{parent}/_rels/{leaf}.rels" if parent else f"_rels/{leaf}.rels"
                )
            else:
                continue
            known_ids = all_rel_ids.get(relationship_part, set())
            for relation_id in sorted(referenced_ids - known_ids):
                dangling.append(
                    {"part": part, "id": relation_id, "rels": relationship_part}
                )
        result["dangling_relationship_ids"] = dangling
        result["dangling_relationships"] = dangling

        document = trees.get("word/document.xml")
        if document is not None:
            all_elements = list(document.iter())
            doc_pr_ids = [
                element.attrib.get("id")
                for element in all_elements
                if element.tag == _q(WP_NS, "docPr")
            ]
            duplicate_doc_pr_ids = sorted(
                {value for value in doc_pr_ids if doc_pr_ids.count(value) > 1}
            )
            if duplicate_doc_pr_ids:
                result["drawing_id_errors"].append(
                    {"kind": "duplicate_docPr_id", "ids": duplicate_doc_pr_ids}
                )
            bookmark_starts = {
                element.attrib.get(_q(W_NS, "id"))
                for element in all_elements
                if element.tag == _q(W_NS, "bookmarkStart")
            }
            bookmark_ends = {
                element.attrib.get(_q(W_NS, "id"))
                for element in all_elements
                if element.tag == _q(W_NS, "bookmarkEnd")
            }
            orphan_starts = sorted(bookmark_starts - bookmark_ends)
            orphan_ends = sorted(bookmark_ends - bookmark_starts)
            if orphan_starts or orphan_ends:
                result["bookmark_id_errors"].append(
                    {
                        "orphan_starts": orphan_starts,
                        "orphan_ends": orphan_ends,
                    }
                )

            table_pr_order: list[dict[str, Any]] = []
            tables = [
                element for element in all_elements if element.tag == _q(W_NS, "tbl")
            ]
            for table_index, table in enumerate(tables):
                tbl_pr = next(
                    (child for child in list(table) if child.tag == _q(W_NS, "tblPr")),
                    None,
                )
                if tbl_pr is None:
                    continue
                children = [child.tag.rsplit("}", 1)[-1] for child in list(tbl_pr)]
                if "tblpPr" in children and "tblW" in children:
                    if children.index("tblpPr") > children.index("tblW"):
                        table_pr_order.append(
                            {
                                "table_index": table_index,
                                "children": children,
                                "issue": "w:tblpPr must precede w:tblW in w:tblPr",
                            }
                        )
                if "tblpPr" in children and "tblLook" in children:
                    if children.index("tblpPr") > children.index("tblLook"):
                        table_pr_order.append(
                            {
                                "table_index": table_index,
                                "children": children,
                                "issue": "w:tblpPr must precede w:tblLook in w:tblPr",
                            }
                        )
            result["schema_order_errors"] = table_pr_order
            result["counts"] = {
                "tables": len(tables),
                "drawings": sum(
                    element.tag == _q(W_NS, "drawing") for element in all_elements
                ),
                "paragraphs": sum(
                    element.tag == _q(W_NS, "p") for element in all_elements
                ),
                "textboxes": sum(
                    element.tag
                    == _q(
                        "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
                        "wsp",
                    )
                    for element in all_elements
                ),
                "docPr_count": len(doc_pr_ids),
                "docPr_unique": len(set(doc_pr_ids)),
            }

        styles = trees.get("word/styles.xml")
        style_ids: set[str] = set()
        if styles is not None:
            style_values = [
                element.attrib.get(_q(W_NS, "styleId"), "")
                for element in styles.findall(_q(W_NS, "style"))
            ]
            style_ids = {value for value in style_values if value}
            for value, count in Counter(style_values).items():
                if value and count > 1:
                    result["duplicate_ids"].append({"kind": "styleId", "id": value})
        for part, tree in trees.items():
            if part.endswith(".rels") or part == "word/styles.xml":
                continue
            for local in ("pStyle", "rStyle", "tblStyle"):
                for element in tree.iter(_q(W_NS, local)):
                    value = element.attrib.get(_q(W_NS, "val"), "")
                    if value and value not in style_ids:
                        result["missing_style_refs"].append(
                            {"part": part, "type": local, "style_id": value}
                        )

        numbering = trees.get("word/numbering.xml")
        abstract_ids: set[str] = set()
        num_ids: set[str] = set()
        if numbering is not None:
            abstract_values = [
                element.attrib.get(_q(W_NS, "abstractNumId"), "")
                for element in numbering.findall(_q(W_NS, "abstractNum"))
            ]
            num_values = [
                element.attrib.get(_q(W_NS, "numId"), "")
                for element in numbering.findall(_q(W_NS, "num"))
            ]
            abstract_ids = {value for value in abstract_values if value}
            num_ids = {value for value in num_values if value}
            for kind, values in (("abstractNumId", abstract_values), ("numId", num_values)):
                for value, count in Counter(values).items():
                    if value and count > 1:
                        result["duplicate_ids"].append({"kind": kind, "id": value})
            for num in numbering.findall(_q(W_NS, "num")):
                num_id = num.attrib.get(_q(W_NS, "numId"), "")
                reference = num.find(_q(W_NS, "abstractNumId"))
                value = reference.attrib.get(_q(W_NS, "val"), "") if reference is not None else ""
                if value and value not in abstract_ids:
                    result["missing_numbering_refs"].append(
                        {"part": "word/numbering.xml", "num_id": num_id, "abstract_num_id": value}
                    )
        for part, tree in trees.items():
            if part.endswith(".rels") or part == "word/numbering.xml":
                continue
            for num_id_element in tree.iter(_q(W_NS, "numId")):
                value = num_id_element.attrib.get(_q(W_NS, "val"), "")
                if value and value != "0" and value not in num_ids:
                    result["missing_numbering_refs"].append({"part": part, "num_id": value})

        if document is not None:
            for local, prefix in (("headerReference", "word/header"), ("footerReference", "word/footer")):
                for reference in document.iter(_q(W_NS, local)):
                    rel_id = reference.attrib.get(_q(R_NS, "id"), "")
                    target = relationship_targets_by_source.get(("word/document.xml", rel_id))
                    if not target or not target.startswith(prefix) or target not in names:
                        result["missing_header_footer_parts"].append(
                            {"type": local, "relationship_id": rel_id, "target": target}
                        )

        settings = trees.get("word/settings.xml")
        if settings is not None:
            for kind in ("footnote", "endnote"):
                declarations = list(settings.iter(_q(W_NS, f"{kind}Pr")))
                if not declarations:
                    continue
                part = f"word/{kind}s.xml"
                rel_suffix = f"/{kind}s"
                has_relationship = any(
                    relation_type.endswith(rel_suffix)
                    for relation_type in relationship_types_by_source.get("word/document.xml", set())
                )
                if part not in names or not has_relationship:
                    result["invalid_note_settings"].append({
                        "kind": kind,
                        "settings_references": len(declarations),
                        "part_present": part in names,
                        "relationship_present": has_relationship,
                    })

        result["duplicate_ids"].extend(
            {"kind": "relationship", **item}
            for item in result["duplicate_relationship_ids"]
        )
        try:
            Document(package_path)
            result["python_docx_reopen"] = True
        except Exception as exc:
            result["errors"].append(f"python-docx reopen failed: {exc}")

        result["unsafe_ooxml"] = int(any((
            result["schema_order_errors"],
            result["drawing_id_errors"],
            result["bookmark_id_errors"],
            result["invalid_note_settings"],
        )))

        fatal = (
            result["zip_integrity"] != "PASS"
            or result["xml_well_formed"] != "PASS"
            or result["content_types"] != "PASS"
            or result["relationship_targets"] != "PASS"
            or bool(result["dangling_relationship_ids"])
            or bool(result["duplicate_relationship_ids"])
            or bool(result["schema_order_errors"])
            or bool(result["drawing_id_errors"])
            or bool(result["bookmark_id_errors"])
            or bool(result["content_type_targets_missing"])
            or bool(result["missing_style_refs"])
            or bool(result["missing_numbering_refs"])
            or bool(result["missing_header_footer_parts"])
            or bool(result["invalid_note_settings"])
            or not result["python_docx_reopen"]
        )
        result["result"] = "FAIL" if fatal else "PASS"
    return result


__all__ = ["scan_docx_package"]
