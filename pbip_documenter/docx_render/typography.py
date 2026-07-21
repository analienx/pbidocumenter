"""Typography: headings, body text, callouts, page breaks."""

import re
import typing
from io import BytesIO

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt

from pbip_documenter.config import BEAUTIFY, FONT, C


def _run(
    p: typing.Any,
    text: typing.Any,
    font: typing.Any = FONT,
    size: typing.Any = 9,
    bold: typing.Any = False,
    italic: typing.Any = False,
    color: typing.Any = None,
) -> typing.Any:
    r = p.add_run(text)
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    if color:
        r.font.color.rgb = C.rgb(color)
    return r


def _hr(p: typing.Any, text: typing.Any, size: typing.Any, color: typing.Any, bold: typing.Any = True) -> typing.Any:
    """Add a styled heading run."""
    r = p.add_run(text)
    r.font.name = FONT
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.underline = False
    r.font.color.rgb = C.rgb(color)
    return r


def _split_num(text: typing.Any) -> typing.Any:
    m = re.match(r"^(\d[\d.]*)\s+(.+)", str(text))
    return (m.group(1), m.group(2)) if m else ("", text)


def h1(doc: typing.Any, text: typing.Any) -> typing.Any:
    p = doc.add_heading("", level=1)
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(4)
    if BEAUTIFY:
        p._p.get_or_add_pPr().append(
            parse_xml(
                f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="8" w:space="2" w:color="{C.RUBINE}"/></w:pBdr>'
            )
        )
        num, rest = _split_num(text)
        if num:
            _hr(p, num + "  ", 13, C.PACIFIC)
        _hr(p, rest or text, 13, C.PACIFIC)
    else:
        _hr(p, text, 11, C.PACIFIC)
    return p


def h2(doc: typing.Any, text: typing.Any) -> typing.Any:
    p = doc.add_heading("", level=2)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    num, rest = _split_num(text)
    if BEAUTIFY and num:
        _hr(p, num + " ", 11, C.RUBINE)
    _hr(p, rest or text, 11, C.PACIFIC)
    return p


def h3(doc: typing.Any, text: typing.Any) -> typing.Any:
    p = doc.add_heading("", level=3)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(3)
    num, rest = _split_num(text)
    if BEAUTIFY and num:
        _hr(p, num + " ", 9.5, C.RUBINE)
    _hr(p, rest or text, 9.5, C.PACIFIC)
    return p


def h4(doc: typing.Any, text: typing.Any) -> typing.Any:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(1)
    if BEAUTIFY:
        m = re.match(r"^(\[[^\]]+\])\s+(.+?)\s*(\([^)]+\)|\[[^\]]+\])?$", text.strip())
        if m:
            _run(p, m.group(1) + "  ", size=7.5, italic=True, color=C.RUBINE)
            _run(p, m.group(2), size=8.5, bold=True, color=C.PACIFIC)
            if m.group(3):
                _run(p, "  " + m.group(3), size=7.5, italic=True, color=C.DGRAY)
            return p
    _run(p, text, size=8.5, bold=True, color=C.PACIFIC)
    return p


def body(
    doc: typing.Any, text: typing.Any, bold: typing.Any = False, italic: typing.Any = False, color: typing.Any = None
) -> typing.Any:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(0)
    _run(p, text, bold=bold, italic=italic, color=color or C.CHARCOAL)
    return p


def bullet_item(doc: typing.Any, text: typing.Any) -> typing.Any:
    p = doc.add_paragraph(style="List Bullet")
    p.clear()
    _run(p, text, color=C.CHARCOAL)
    return p


def _tagged_para(doc: typing.Any, tag: typing.Any, text: typing.Any, style: typing.Any = None) -> typing.Any:
    """[TAG] italic-gray text paragraph."""
    p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    if style:
        p.clear()
    _run(p, tag + " ", size=9, bold=True, color=C.RUBINE)
    _run(p, text, size=9, italic=True, color=C.DGRAY)
    return p


def suggested(doc: typing.Any, text: typing.Any) -> typing.Any:
    return _tagged_para(doc, "[SUGGESTED]", text)


def suggested_bullet(doc: typing.Any, text: typing.Any) -> typing.Any:
    return _tagged_para(doc, "[SUGGESTED]", text, style="List Bullet")


def placeholder(doc: typing.Any, text: typing.Any) -> typing.Any:
    return _tagged_para(doc, "[To be confirmed]", text)


def page_break(doc: typing.Any) -> typing.Any:
    p = doc.add_paragraph()
    r = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    r.append(br)
    p._p.append(r)


def _is_page_break_paragraph(p: typing.Any) -> typing.Any:
    """Check if paragraph contains only a page break."""
    for r in p._element.iter(qn("w:r")):
        for br in r.iter(qn("w:br")):
            if br.get(qn("w:type")) == "page":
                text_runs = list(r.iter(qn("w:t")))
                if not text_runs:
                    return True
    return False


def _remove_unnecessary_breaks(doc: typing.Any) -> typing.Any:
    """Smart removal of blank-page-creating breaks."""
    paras = list(doc.paragraphs)
    to_remove = set()

    # 1. Consecutive breaks: keep first, mark rest for removal
    for i in range(len(paras) - 1):
        if _is_page_break_paragraph(paras[i]) and _is_page_break_paragraph(paras[i + 1]):
            to_remove.add(i + 1)

    # 2. Trailing breaks: remove last N breaks if at end
    for i in range(len(paras) - 1, max(len(paras) - 5, 0), -1):
        if _is_page_break_paragraph(paras[i]):
            to_remove.add(i)
        else:
            break

    # 3. Orphaned breaks: break followed by only heading + 1-2 short lines
    for i in range(len(paras) - 3):
        if i in to_remove:
            continue
        if _is_page_break_paragraph(paras[i]):
            next_paras = paras[i + 1 : i + 4]
            content_length = sum(len((p.text or "").strip()) for p in next_paras if not _is_page_break_paragraph(p))
            if content_length < 80 and i > 0:
                prev_style = (paras[i - 1].style.name or "") if paras[i - 1].style else ""
                if not prev_style.startswith("Heading"):
                    to_remove.add(i)

    for i in sorted(to_remove, reverse=True):
        p = paras[i]._element
        p.getparent().remove(p)


def callout(doc: typing.Any, text: typing.Any, kind: typing.Any = "info") -> typing.Any:
    bc = C.SKY if kind == "info" else C.MARIGOLD
    bg = C.CALLOUT if kind == "info" else C.WARN_BG
    p = doc.add_paragraph()
    p._p.get_or_add_pPr().append(
        parse_xml(f'<w:pBdr {nsdecls("w")}><w:left w:val="single" w:sz="24" w:space="6" w:color="{bc}"/></w:pBdr>')
    )
    p._p.get_or_add_pPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}" w:val="clear"/>'))
    _run(p, text, size=9, color=C.CHARCOAL)


def add_image(
    doc: typing.Any, png_bytes: typing.Any, width_inches: typing.Any = 5.5, caption_text: typing.Any = None
) -> typing.Any:
    doc.add_picture(BytesIO(png_bytes), width=Inches(width_inches))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption_text:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, caption_text, size=8, italic=True, color=C.DGRAY)
