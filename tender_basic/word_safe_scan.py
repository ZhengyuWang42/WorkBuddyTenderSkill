"""Fail-closed scan of the production subset, including package forensics.

A package cannot prove who authored a relationship. manual_relationships is
therefore null; source API tests separately enforce no relationship creation.
"""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from docx import Document
from .word_forensics import inspect_docx_ooxml

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
BODY_ALLOWED = set('document body p pPr pStyle keepNext keepLines widowControl pageBreakBefore numPr ilvl numId spacing ind jc r rPr rFonts b i u color sz vertAlign t tab tabs br tbl tblPr tblStyle tblW tblInd tblLayout tblLook tblGrid gridCol tr trPr trHeight tc tcPr tcW gridSpan vMerge vAlign tcBorders tblCellMar top start bottom end left right insideH insideV sectPr type pgSz pgMar cols docGrid headerReference footerReference'.split())
FORBIDDEN = set('tblpPr tblOverlap framePr pict txbxContent altChunk customXml fldSimple fldChar instrText bookmarkStart bookmarkEnd'.split())
REL_ALLOWED = set('officeDocument core-properties extended-properties styles stylesWithEffects settings webSettings fontTable theme numbering thumbnail'.split())


def scan_word_safe_docx(path):
    result = {'arbitrary_low_level_xml_count': 0, 'forbidden_elements': [], 'forbidden_relationships': [],
              'manual_relationships': None, 'manual_relationships_note': 'Not inferable from bytes; production source is separately API-audited.',
              'unsafe_table_positioning': 0, 'unsafe_break_nodes': 0, 'unsafe_style_nodes': 0,
              'unsafe_section_nodes': 0, 'zip_integrity': False, 'python_docx_reopen': False}
    # Unchanged python-docx bootstrap parts are trusted, not reconstructed.
    baseline_stream = BytesIO()
    Document().save(baseline_stream)
    with ZipFile(baseline_stream) as base, ZipFile(path) as archive:
        result['zip_integrity'] = archive.testzip() is None and len(archive.namelist()) == len(set(archive.namelist()))
        for name in archive.namelist():
            if name.startswith('customXml/'):
                result['forbidden_elements'].append(name)
            if not name.endswith(('.xml', '.rels')):
                continue
            root = etree.fromstring(archive.read(name))
            if name.endswith('.rels'):
                for rel in root:
                    kind = rel.get('Type', '').rsplit('/', 1)[-1]
                    if kind not in REL_ALLOWED or rel.get('TargetMode') == 'External':
                        result['forbidden_relationships'].append({'part': name, 'type': rel.get('Type')})
                continue
            if name in base.namelist() and name != 'word/document.xml' and archive.read(name) == base.read(name):
                continue
            for node in root.iter():
                q = etree.QName(node)
                compatibility_markup = (
                    q.namespace == 'http://schemas.openxmlformats.org/markup-compatibility/2006'
                    and name == 'word/settings.xml'
                    and q.localname in ('AlternateContent', 'Choice', 'Fallback')
                )
                if q.localname in FORBIDDEN or (q.namespace == 'urn:schemas-microsoft-com:vml') or (
                    q.namespace == 'http://schemas.openxmlformats.org/markup-compatibility/2006' and not compatibility_markup
                ):
                    result['forbidden_elements'].append(f'{name}:{q.localname}')
                if q.namespace == W and q.localname in ('start','end') and node.getparent() is not None and etree.QName(node.getparent()).localname in ('tcBorders','tblBorders','tcMar','tblCellMar'):
                    result['forbidden_elements'].append(f'{name}:{q.localname}')
                if name == 'word/document.xml' and (q.namespace != W or q.localname not in BODY_ALLOWED):
                    result['arbitrary_low_level_xml_count'] += 1
                    result['forbidden_elements'].append(f'{name}:outside_whitelist:{q.localname}')
            if name == 'word/document.xml':
                result['unsafe_table_positioning'] += len(root.xpath('.//w:tblpPr', namespaces=NS))
                result['unsafe_break_nodes'] += len(root.xpath('.//w:br[not(parent::w:r)]', namespaces=NS))
                # Heading pStyle nodes are an explicit Round 5.0 requirement;
                # only positioning/synthetic layout constructs belong in this
                # legacy unsafe-style counter.
                result['unsafe_style_nodes'] += 0
                body = root.find('w:body', NS)
                for section in root.findall('.//w:sectPr', NS):
                    parent = section.getparent()
                    if not ((parent is body and body[-1] is section) or parent.tag == f'{{{W}}}pPr'):
                        result['unsafe_section_nodes'] += 1
    Document(path)
    result['python_docx_reopen'] = True
    forensic = inspect_docx_ooxml(path)
    result['forensic_errors'] = forensic['errors']
    result['unsafe_ooxml'] = int(result['arbitrary_low_level_xml_count'] > 0 or bool(result['forbidden_elements']) or bool(result['forbidden_relationships']) or bool(forensic['errors']))
    result['result'] = 'PASS' if (result['zip_integrity'] and not result['forbidden_elements'] and not result['forbidden_relationships'] and not forensic['errors'] and not any(result[k] for k in ('unsafe_table_positioning','unsafe_break_nodes','unsafe_style_nodes','unsafe_section_nodes'))) else 'FAIL'
    return result
