"""Reviewed compatibility helpers; no arbitrary element factory is exposed.

Only East Asian font attributes and removal of the unused bibliography part
shipped in python-docx's default template require private API access.
Borders use the built-in Table Grid style, merges use cell.merge().
"""
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def set_east_asian_font(target, name):
    target.font.name = name
    target._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), name)


def set_run_fonts(target, east_asia, latin=None):
    """Set destination-owned East Asian and Latin faces on one safe run."""
    latin = latin or east_asia
    target.font.name = latin
    fonts = target._element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:ascii"), latin)
    fonts.set(qn("w:hAnsi"), latin)
    fonts.set(qn("w:eastAsia"), east_asia)


def get_run_fonts(target):
    """Read the safe rFonts attributes written by :func:`set_run_fonts`."""
    fonts = target._element.get_or_add_rPr().get_or_add_rFonts()
    return fonts.get(qn("w:eastAsia")), fonts.get(qn("w:ascii"))


def set_table_indent(table, indent_pt: float) -> None:
    """Set a left table indent with schema-ordered, dependency-free OOXML.

    OOXML measures ``w:tblInd`` from the section's left text margin to the
    leading edge of the table.  A source table can legitimately start left of
    that margin (the source text body is often indented relative to the source
    table), so a negative indent is meaningful and is preserved rather than
    clamped to zero: clamping it was what pushed a whole table object sideways.
    """

    table_properties = table._tbl.tblPr
    table_indent = table_properties.find(qn("w:tblInd"))
    if table_indent is None:
        table_indent = OxmlElement("w:tblInd")
        children = list(table_properties)
        insert_at = next(
            (
                index
                for index, child in enumerate(children)
                if child.tag.rsplit("}", 1)[-1]
                in {"tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook"}
            ),
            len(children),
        )
        table_properties.insert(insert_at, table_indent)
    table_indent.set(qn("w:w"), str(int(round(float(indent_pt) * 20))))
    table_indent.set(qn("w:type"), "dxa")


def set_table_width(table, width_pt: float) -> None:
    """Declare the table's preferred width so the renderer cannot re-fit it."""

    table_properties = table._tbl.tblPr
    table_width = table_properties.find(qn("w:tblW"))
    if table_width is None:
        table_width = OxmlElement("w:tblW")
        table_properties.insert(0, table_width)
    table_width.set(qn("w:w"), str(max(0, int(round(float(width_pt) * 20)))))
    table_width.set(qn("w:type"), "dxa")


def set_table_cell_margins(table, *, left_pt: float, right_pt: float) -> None:
    """Set the table's default cell margins in twips (schema-ordered)."""

    table_properties = table._tbl.tblPr
    margins = table_properties.find(qn("w:tblCellMar"))
    if margins is None:
        margins = OxmlElement("w:tblCellMar")
        children = list(table_properties)
        insert_at = next(
            (
                index
                for index, child in enumerate(children)
                if child.tag.rsplit("}", 1)[-1] in {"tblLook", "tblCaption", "tblDescription"}
            ),
            len(children),
        )
        table_properties.insert(insert_at, margins)
    for tag, value in (("w:top", 0.0), ("w:left", left_pt), ("w:bottom", 0.0), ("w:right", right_pt)):
        element = margins.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            margins.append(element)
        element.set(qn("w:w"), str(max(0, int(round(float(value) * 20)))))
        element.set(qn("w:type"), "dxa")


def clean_bootstrap(document):
    # Drop the default template's unused bibliography relationship. Package
    # serialization then omits unreachable parts; never author a relationship.
    for key, rel in list(document.part.rels.items()):
        if rel.reltype.endswith('/customXml'):
            document.part.drop_rel(key)


def set_cell_bottom_border(cell, width_pt=0.6, color='000000'):
    """Set one schema-safe bottom rule on a form value cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn('w:tcBorders'))
    if borders is None:
        borders = OxmlElement('w:tcBorders')
        # tcBorders follows gridSpan/vMerge in the CT_TcPr sequence.
        insert_at = len(tc_pr)
        for index, child in enumerate(tc_pr):
            if child.tag in {qn('w:shd'), qn('w:tcMar'), qn('w:textDirection'), qn('w:tcFitText'), qn('w:noWrap'), qn('w:vAlign'), qn('w:tcPrChange')}:
                insert_at = index
                break
        tc_pr.insert(insert_at, borders)
    for child in list(borders):
        if child.tag == qn('w:bottom'):
            borders.remove(child)
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), str(max(2, int(round(float(width_pt) * 8.0)))))
    bottom.set(qn('w:space'), '0')
    bottom.set(qn('w:color'), color)
    borders.append(bottom)
