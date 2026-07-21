"""Minimal block-aware pagination helpers.

We decide page breaks BEFORE rendering the heading of each block because
compact blocks (wireframes, small tables, figures) must stay with their
heading whenever they fit on one page.

The core rule:
  if block_height <= usable_page_height and block_height > remaining_height:
      insert page break before the block heading
"""

import math

# Approximate rendered heights for common element types (inches).
# Derived from space_before + font size + space_after in typography.py.
_H3_IN = 0.26  # h3: 10pt before + 9.5pt font + 3pt after
_H4_IN = 0.20  # h4:  8pt before + 8.5pt font + 1pt after
_BODY_IN = 0.16  # single body line
_BLOCK_BUFFER_IN = 0.12  # breathing room after a block

_TABLE_COMPACT_HDR_IN = 0.16
_TABLE_COMPACT_ROW_IN = 0.13
_TABLE_STD_HDR_IN = 0.24
_TABLE_STD_ROW_IN = 0.20

# Safety buffer subtracted from raw page content area.
_SAFETY_IN = 0.22


def usable_page_height_in(doc):
    """Return usable content height in inches from the document's first section."""
    sec = doc.sections[0]
    return sec.page_height.inches - sec.top_margin.inches - sec.bottom_margin.inches - _SAFETY_IN


def should_page_break(remaining_in, block_h_in, usable_in):
    """Return True when a block fits on one page but not in the remaining space.

    If the block is bigger than a full page we do not force a break — let it
    flow naturally instead.
    """
    return block_h_in <= usable_in and block_h_in > remaining_in


def estimate_wireframe_h_emu(page):
    """Quick wireframe canvas height estimate from visual count (no layout work).

    Used for preflight decisions only.  The cursor is updated with the actual
    height returned by insert_page_layout() after rendering.
    """
    n = page.get("visual_count", len(page.get("visuals", [])))
    n_rows = max(1, math.ceil(n / 4))
    EMU = 914400
    return int(
        2 * int(0.06 * EMU)  # top + bottom pad
        + int(0.17 * EMU)  # zone header
        + int(0.10 * EMU)  # zone gap
        + n_rows * int(0.43 * EMU)  # row height + row gap (avg)
        + int(0.14 * EMU)  # info footer
    )


def estimate_wireframe_block_h(wireframe_h_emu):
    """Total block height: h3 + h4 (Wireframe label) + diagram + buffer."""
    return _H3_IN + _H4_IN + (wireframe_h_emu / 914400) + _BLOCK_BUFFER_IN


def estimate_table_block_h(n_rows, compact=True, has_heading=True, has_title=False):
    """Total block height: optional h4 + optional title + header + N rows + buffer.

    Small-table algorithm: if this fits on one page but not in remaining space,
    insert a page break before the heading.

    Large-table algorithm: when n_rows is high enough that the total exceeds the
    usable page height, the caller should treat the table as flow content and only
    break if there is too little space for a sensible start (heading + header + 2 rows).
    """
    hdr = _TABLE_COMPACT_HDR_IN if compact else _TABLE_STD_HDR_IN
    row = _TABLE_COMPACT_ROW_IN if compact else _TABLE_STD_ROW_IN
    total = hdr + n_rows * row
    if has_title:
        total += _BODY_IN
    if has_heading:
        total += _H4_IN
    return total + _BLOCK_BUFFER_IN


def estimate_large_table_start_h(compact=True, has_heading=True):
    """Minimum sensible start height for a large (multi-page) table.

    Used for the large-table algorithm: do not start a table if remaining
    space is less than this (heading + header + 2 rows).
    """
    return estimate_table_block_h(2, compact=compact, has_heading=has_heading)


def estimate_figure_block_h(figure_h_emu, has_heading=True, has_caption=True):
    """Total block height: optional h3 + figure + optional caption + buffer."""
    total = figure_h_emu / 914400 + _BLOCK_BUFFER_IN
    if has_heading:
        total += _H3_IN
    if has_caption:
        total += _BODY_IN
    return total
