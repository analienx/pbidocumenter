"""Low-level Word XML cell/table styling helpers."""

from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn

from pbip_documenter.config import C


def _shading(cell, color):
    cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}" w:val="clear"/>'))


def _margins(cell, t=40, b=40, l=80, r=80):
    pr = cell._tc.get_or_add_tcPr()
    old = pr.find(qn("w:tcMar"))
    if old is not None:
        pr.remove(old)
    pr.append(
        parse_xml(
            f"<w:tcMar {nsdecls('w')}>"
            f'<w:top w:w="{t}" w:type="dxa"/><w:bottom w:w="{b}" w:type="dxa"/>'
            f'<w:left w:w="{l}" w:type="dxa"/><w:right w:w="{r}" w:type="dxa"/>'
            f"</w:tcMar>"
        )
    )


def _set_w(cell, w):
    pr = cell._tc.get_or_add_tcPr()
    old = pr.find(qn("w:tcW"))
    if old is not None:
        pr.remove(old)
    pr.append(parse_xml(f'<w:tcW {nsdecls("w")} w:w="{w}" w:type="dxa"/>'))


def _no_borders(cell):
    pr = cell._tc.get_or_add_tcPr()
    old = pr.find(qn("w:tcBorders"))
    if old is not None:
        pr.remove(old)
    pr.append(
        parse_xml(
            f"<w:tcBorders {nsdecls('w')}>"
            f'<w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            f'<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            f'<w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            f'<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            f"</w:tcBorders>"
        )
    )


def _set_borders(cell, top=None, left=None, bottom=None, right=None):
    """Set individual cell borders. Each param: (val, sz, color) or None=none."""

    def _edge(name, spec):
        if spec is None:
            return f'<w:{["top", "left", "bottom", "right"][["top", "left", "bottom", "right"].index(name)]} w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        v, s, c = spec
        return f'<w:{name} w:val="{v}" w:sz="{s}" w:space="0" w:color="{c}"/>'

    pr = cell._tc.get_or_add_tcPr()
    old = pr.find(qn("w:tcBorders"))
    if old is not None:
        pr.remove(old)
    pr.append(
        parse_xml(
            f"<w:tcBorders {nsdecls('w')}>"
            + "".join(_edge(n, s) for n, s in [("top", top), ("left", left), ("bottom", bottom), ("right", right)])
            + "</w:tcBorders>"
        )
    )


def _set_table_borders(table, color=None):
    c = color or C.BORDER
    tbl = table._tbl
    tpr = tbl.tblPr if tbl.tblPr is not None else parse_xml(f"<w:tblPr {nsdecls('w')}/>")
    old = tpr.find(qn("w:tblBorders"))
    if old is not None:
        tpr.remove(old)
    tpr.append(
        parse_xml(
            f"<w:tblBorders {nsdecls('w')}>"
            + "".join(
                f'<w:{e} w:val="single" w:sz="4" w:space="0" w:color="{c}"/>'
                for e in ("top", "left", "bottom", "right", "insideH", "insideV")
            )
            + "</w:tblBorders>"
        )
    )
