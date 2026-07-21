"""
Configuration and brand constants for the PBIP Documenter.

This module defines:
- Version information
- Typography settings (fonts, content width)
- Feature flags (BEAUTIFY, WIREFRAME_V2)
- Default brand color palette
- Layout thresholds for diagrams and tables
"""

import typing

from docx.shared import RGBColor

from pbip_documenter.version import __version__

# ═══════════════════════════════════════════════════════════════════════════
# Version and Build Info
# ═══════════════════════════════════════════════════════════════════════════
VERSION = __version__

# ═══════════════════════════════════════════════════════════════════════════
# Typography Constants
# ═══════════════════════════════════════════════════════════════════════════
FONT = "Arial"  # Primary document font
FONT_CODE = "Courier New"  # Monospace font for code blocks
CW = 10034  # Content width in DXA (A4, 0.70"/0.60" margins)

# ═══════════════════════════════════════════════════════════════════════════
# Feature Flags
# ═══════════════════════════════════════════════════════════════════════════
BEAUTIFY = True  # Enable enhanced visual styling
WIREFRAME_V2 = True  # Use v2 wireframe rendering engine

# ═══════════════════════════════════════════════════════════════════════════
# Layout Thresholds
# ═══════════════════════════════════════════════════════════════════════════
# SCHEMA DIAGRAM TUNING NOTES
# These values control diagram volume and density, not physical placement.
# - _SCHEMA_MAX_DIAGRAMS: hard cap for schema figures in the Word document.
# - _SCHEMA_MAX_ANCHORS: number of focused anchor tables promoted from a connected component.
# - _SCHEMA_FOCUS_MAX_NODES: maximum explicit table boxes in one focused diagram.
# - _SCHEMA_EDGE_RENDER_LIMIT: maximum relationship lines drawn in one diagram.
# If diagrams become too dense, lower _SCHEMA_FOCUS_MAX_NODES or _SCHEMA_EDGE_RENDER_LIMIT first.
# If important areas are missing, increase _SCHEMA_MAX_ANCHORS or _SCHEMA_MAX_DIAGRAMS.
# Physical layout, summary-card placement, legend sizing, and safe canvas height are tuned
# in pbip_documenter/analysis/schema.py near the SCHEMA LAYOUT TUNING CONSTANTS block.
_COMPACT_ROWS_PER_PAGE = 35  # Max rows before forcing page break
_LINEAGE_MAX_ROWS = 20  # Max rows in lineage tables
_SCHEMA_SCALE_THRESHOLD = 10  # Tables before schema scaling kicks in
_SCHEMA_SIMPLIFY_THRESHOLD = 12  # Tables before schema simplification
_SCHEMA_MAX_DIAGRAMS = 5  # Maximum schema figures rendered into the Word document
_SCHEMA_MAX_ANCHORS = 5  # Max focused anchors promoted from a large connected component
_SCHEMA_FOCUS_MAX_NODES = 20  # Max explicit nodes in a focused schema view
_SCHEMA_SUMMARY_GROUPS = 3  # Max grouped summary cards shown beneath a focused schema
_SCHEMA_EDGE_RENDER_LIMIT = 24  # Soft cap for rendered visible edges in a single schema view
_SCHEMA_LANDSCAPE_MARGIN_CM = 1.20  # Margins for landscape schema pages


# ═══════════════════════════════════════════════════════════════════════════
# Default Brand Colour Palette
# ═══════════════════════════════════════════════════════════════════════════
class C:
    """
    Default brand colours for consistent document styling.

    Primary Palette:
        RUBINE:     Brand primary (pink/magenta)
        PACIFIC:    Secondary blue
        EVERGREEN:  Success/positive indicators
        SKY:        Info/callouts

    Accent Palette:
        MARIGOLD:   Warnings/attention
        TEAL:       Tertiary accent

    Neutral Palette:
        CHARCOAL:   Primary text
        DGRAY:      Secondary text
        LGRAY:      Light backgrounds
        SUBTLE:     Very light backgrounds
        ALT:        Alternate row highlighting
        BORDER:     Table borders
        BLIGHT:     Light borders/dividers
        WHITE:      Pure white

    Semantic Colors:
        CARD_BG:    Observation card backgrounds
        CALLOUT:    Info callout backgrounds
        WARN_BG:    Warning callout backgrounds
        TAN:        Deprecated/unused
        GREEN:      Success indicators
    """

    # Primary brand colors
    RUBINE = "E20177"
    PACIFIC = "1B4298"
    EVERGREEN = "54B948"
    SKY = "009DDC"

    # Accent colors
    MARIGOLD = "FEDB00"
    TEAL = "3CDBC0"

    # Neutral palette
    CHARCOAL = "171717"
    DGRAY = "4A4A4A"
    LGRAY = "F5F5F5"
    SUBTLE = "F8F9FA"
    ALT = "EDF4FC"
    BORDER = "D0D0D0"
    BLIGHT = "EEEEEE"
    WHITE = "FFFFFF"

    # Semantic colors
    CARD_BG = "FAFAFA"
    CALLOUT = "F0F8FF"
    WARN_BG = "FFFDE7"
    TAN = "DDD9C3"
    GREEN = "00B294"

    @staticmethod
    def rgb(hex_color: str) -> typing.Any:
        """
        Convert hex color string to RGBColor object.

        Args:
            hex_color: 6-character hex string (e.g., "E20177")

        Returns:
            RGBColor object for python-docx
        """
        return RGBColor(int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16))
