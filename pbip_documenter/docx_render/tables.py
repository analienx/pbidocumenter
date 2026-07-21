"""Table and card widgets for the Word document."""

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Pt

from pbip_documenter.config import _COMPACT_ROWS_PER_PAGE, BEAUTIFY, CW, FONT, FONT_CODE, C
from pbip_documenter.docx_render.styles import (
    _margins,
    _no_borders,
    _set_borders,
    _set_table_borders,
    _set_w,
    _shading,
)
from pbip_documenter.docx_render.typography import _run, h4, page_break

# Mutable counters (module-level state)
_OBS_CARD_COUNTER = [0]


def doc_control_table(doc, pairs):
    t = doc.add_table(rows=len(pairs), cols=2)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(pairs):
        c0, c1 = t.rows[i].cells
        _set_w(c0, 3312)
        _set_w(c1, 6768)
        _margins(c0, 40, 40, 80, 60)
        _margins(c1, 40, 40, 60, 80)
        _run(c0.paragraphs[0], str(k), size=9, bold=True, color=C.CHARCOAL)
        val = str(v or "")
        if val.startswith("[To be confirmed]") or val.startswith("[Enter"):
            _run(c1.paragraphs[0], val, size=9, bold=True, color=C.RUBINE, italic=True)
        else:
            _run(c1.paragraphs[0], val, size=9, color=C.CHARCOAL)
    return t


def kpi_strip(doc, metrics):
    n = len(metrics)
    w = CW // n
    t = doc.add_table(rows=1, cols=n)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, m in enumerate(metrics):
        cell = t.rows[0].cells[i]
        _shading(cell, m["color"])
        _set_w(cell, w)
        _margins(cell, 100, 100, 80, 80)
        _no_borders(cell)
        p1 = cell.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p1, m["value"], size=14, bold=True, color=C.WHITE)
        p2 = cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p2, m["label"], size=8, color=C.WHITE)
    return t


def _add_hyperlink(paragraph, text, url, size=9, bold=False, color=C.CHARCOAL):
    """Add a clickable hyperlink to a paragraph.

    Returns the run with the hyperlink.
    """
    # Create the hyperlink element
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

    # Create the w:hyperlink element
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(docx.oxml.ns.qn("r:id"), r_id)

    # Create the w:r element
    run_element = OxmlElement("w:r")

    # Create the rPr element (run properties)
    rPr = OxmlElement("w:rPr")

    # Add color
    color_elem = OxmlElement("w:color")
    color_elem.set(docx.oxml.ns.qn("w:val"), color)
    rPr.append(color_elem)

    # Add underline style for hyperlinks
    u_elem = OxmlElement("w:u")
    u_elem.set(docx.oxml.ns.qn("w:val"), "single")
    rPr.append(u_elem)

    # Add font size
    sz_elem = OxmlElement("w:sz")
    sz_elem.set(docx.oxml.ns.qn("w:val"), str(size * 2))  # size in half-points
    rPr.append(sz_elem)

    # Add bold if needed
    if bold:
        b_elem = OxmlElement("w:b")
        rPr.append(b_elem)

    run_element.append(rPr)

    # Add the text content
    t_elem = OxmlElement("w:t")
    t_elem.text = text
    run_element.append(t_elem)

    hyperlink.append(run_element)
    paragraph._p.append(hyperlink)

    return hyperlink


def prop_table(doc, pairs):
    """Build a property table with optional hyperlinks.

    Each value in pairs can be:
    - A string: rendered as plain text
    - A tuple (link_text, url): rendered as a clickable hyperlink
    - A list of strings/tuples: each on a new line
    """

    t = doc.add_table(rows=len(pairs), cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(pairs):
        c0, c1 = t.rows[i].cells
        bg = C.SUBTLE if i % 2 == 0 else C.WHITE
        for c in (c0, c1):
            _shading(c, bg)
            _set_borders(c, bottom=("single", 4, C.BLIGHT))
        _set_w(c0, 3000)
        _set_w(c1, CW - 3000)
        _margins(c0, 50, 50, 120, 60)
        _margins(c1, 50, 50, 60, 120)
        _run(c0.paragraphs[0], str(k), size=9, bold=True, color=C.DGRAY)

        # Handle value - could be string, tuple (text, url), or list of either
        cell_paragraph = c1.paragraphs[0]
        cell_paragraph.clear()  # Clear default paragraph

        values = v if isinstance(v, list) else [v]

        for idx, val in enumerate(values):
            if idx > 0:
                # Add line break between items
                cell_paragraph.add_run().add_break()

            if isinstance(val, tuple) and len(val) == 2:
                # It's a hyperlink tuple: (text, url)
                link_text, url = val
                _add_hyperlink(cell_paragraph, link_text, url, size=9, color=C.PACIFIC)
            else:
                # Plain text
                _run(cell_paragraph, str(val or ""), size=9, color=C.CHARCOAL)
    return t


def obs_card(doc, title, detail, accent=None):
    accent = accent or C.RUBINE
    if BEAUTIFY:
        _OBS_CARD_COUNTER[0] += 1
        BADGE_W = 520
        CONTENT_W = CW - BADGE_W
        t = doc.add_table(rows=1, cols=2)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        tpr = t._tbl.tblPr if t._tbl.tblPr is not None else parse_xml(f"<w:tblPr {nsdecls('w')}/>")
        for old in [tpr.find(qn(x)) for x in ("w:tblW", "w:tblBorders")]:
            if old is not None:
                tpr.remove(old)
        tpr.append(parse_xml(f'<w:tblW {nsdecls("w")} w:w="{CW}" w:type="dxa"/>'))
        cb, cc = t.rows[0].cells
        _set_w(cb, BADGE_W)
        _shading(cb, accent)
        _margins(cb, 80, 80, 30, 30)
        _set_borders(cb, bottom=("single", 4, accent))
        pb = cb.paragraphs[0]
        pb.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pb.paragraph_format.space_before = pb.paragraph_format.space_after = Pt(0)
        r = pb.add_run(str(_OBS_CARD_COUNTER[0]))
        r.font.name = FONT
        r.font.size = Pt(10)
        r.font.bold = True
        r.font.color.rgb = C.rgb(C.WHITE)
        _set_w(cc, CONTENT_W)
        _shading(cc, C.SUBTLE)
        _margins(cc, 70, 70, 160, 120)
        _set_borders(cc, left=("single", 18, accent), bottom=("single", 4, C.BORDER))
        pt = cc.paragraphs[0]
        pt.paragraph_format.space_before = Pt(0)
        pt.paragraph_format.space_after = Pt(3)
        rt = pt.add_run(title)
        rt.font.name = FONT
        rt.font.size = Pt(9)
        rt.font.bold = True
        rt.font.color.rgb = C.rgb(C.CHARCOAL)
        pd = cc.add_paragraph()
        pd.paragraph_format.space_before = pd.paragraph_format.space_after = Pt(0)
        rd = pd.add_run(detail)
        rd.font.name = FONT
        rd.font.size = Pt(8.5)
        rd.font.color.rgb = C.rgb(C.DGRAY)
        return t
    # plain style
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    tpr = t._tbl.tblPr if t._tbl.tblPr is not None else parse_xml(f"<w:tblPr {nsdecls('w')}/>")
    old_w = tpr.find(qn("w:tblW"))
    if old_w is not None:
        tpr.remove(old_w)
    tpr.append(parse_xml(f'<w:tblW {nsdecls("w")} w:w="{CW}" w:type="dxa"/>'))
    cell = t.rows[0].cells[0]
    _shading(cell, C.CARD_BG)
    _margins(cell, 80, 80, 200, 140)
    _set_borders(cell, left=("single", 36, accent), bottom=("single", 4, C.BLIGHT))
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(3)
    _run(p, title, size=9, bold=True, color=C.CHARCOAL)
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_before = Pt(0)
    _run(p2, detail, size=9, color=C.DGRAY)
    return t


def _section_break_after_table(doc, rows, force=False):
    if force or (rows is not None and rows > _COMPACT_ROWS_PER_PAGE):
        page_break(doc)


def data_table(doc, headers, rows, widths=None, compact=False, repeat_header=False, title=None):
    if title:
        tp = doc.add_paragraph()
        tp.paragraph_format.space_before = Pt(0)
        tp.paragraph_format.space_after = Pt(2)
        tr = tp.add_run(title)
        tr.font.name = FONT
        tr.font.size = Pt(7.5)
        tr.font.italic = True
        tr.font.color.rgb = C.rgb(C.DGRAY)
    ws = widths or [CW // len(headers)] * len(headers)
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders(t)
    htb = 20 if compact else 50
    rtb = 10 if compact else 40
    plr = 40 if compact else 70
    fsz = (7 if BEAUTIFY else 8) if compact else 9
    hr = t.rows[0]
    if repeat_header:
        trPr = hr._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:tblHeader"))
    for i, hdr in enumerate(headers):
        c = hr.cells[i]
        _shading(c, C.PACIFIC)
        _set_w(c, ws[i])
        _margins(c, htb, htb, plr, plr)
        p = c.paragraphs[0]
        p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        _run(p, hdr, size=fsz, bold=True, color=C.WHITE)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            c = t.rows[ri + 1].cells[ci]
            if ri % 2 == 1:
                _shading(c, C.ALT)
            _set_w(c, ws[ci])
            _margins(c, rtb, rtb, plr, plr)
            p = c.paragraphs[0]
            p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            _run(p, str(val or ""), size=fsz, color=C.CHARCOAL)
    return t


def code_block(doc, code, label=None):
    if label:
        h4(doc, label)
    for line in code.strip().split("\n"):
        p = doc.add_paragraph()
        pPr = p._p.get_or_add_pPr()
        pPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{C.LGRAY}" w:val="clear"/>'))
        pPr.append(
            parse_xml(
                f'<w:pBdr {nsdecls("w")}><w:left w:val="single" w:sz="16" w:space="4" w:color="{C.BORDER}"/></w:pBdr>'
            )
        )
        _run(p, line, font=FONT_CODE, size=8, color=C.CHARCOAL)
        p.paragraph_format.space_after = p.paragraph_format.space_before = Pt(0)
