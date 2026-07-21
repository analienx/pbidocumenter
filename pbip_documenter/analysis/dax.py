"""
DAX pattern detection and M-code transform helpers.

This module provides lightweight analysis of DAX measures and M code
to identify common patterns for summary documentation.
"""

import typing

# Transform keywords for summarizing M code operations
_TRANSFORM_KEYWORDS: list[typing.Any] = [
    ("NestedJoin", "merge"),
    ("Pivot", "pivot"),
    ("ExpandListColumn", "expand"),
    ("SelectRows", "filter"),
    ("AddColumn", "add col"),
    ("RenameColumns", "rename"),
    ("RemoveColumns", "remove cols"),
    ("Group", "group"),
    ("SplitColumn", "split"),
]

# DAX function patterns for categorizing measures
_DAX_KEYWORDS: list[typing.Any] = [
    ("CALCULATE", "CALCULATE"),
    ("DATEADD", "Time Intel"),
    ("DIVIDE", "DIVIDE"),
    ("DISTINCTCOUNT", "Distinct Count"),
    ("AVERAGEX", "AVERAGEX"),
    ("DATEDIFF", "DATEDIFF"),
    ("SELECTEDVALUE", "SELECTEDVALUE"),
    ("NAMEOF", "Field Param"),
    ("ALLEXCEPT", "ALLEXCEPT"),
]


def _transforms(m_code: str | None) -> typing.Any:
    """
    Summarize M code transforms into a comma-separated list.

    Identifies common data transformation operations in Power Query M code
    for quick reference in documentation tables.

    Args:
        m_code: Raw M code string from a partition/expression

    Returns:
        Comma-separated list of detected transforms, or em-dash if none

    Example:
        >>> _transforms('Table.NestedJoin(...)')
        'merge'
        >>> _transforms('Table.SelectRows(Table.AddColumn(...))')
        'filter, add col'
    """
    if not m_code:
        return "\u2014"

    detected = [label for kw, label in _TRANSFORM_KEYWORDS if kw in m_code]

    return ", ".join(detected)[:50] or "\u2014"


def _dax_pattern(dax_expr: str | None) -> typing.Any:
    """
    Classify DAX expression by its primary pattern category.

    Identifies common DAX patterns for quick categorization in
    measure summary tables.

    Args:
        dax_expr: DAX measure expression

    Returns:
        Comma-separated list of detected patterns, or "Basic" if none

    Example:
        >>> _dax_pattern('CALCULATE(SUM(Sales[Amount]), ...)')
        'CALCULATE'
        >>> _dax_pattern('DISTINCTCOUNT(Customers[ID])')
        'Distinct Count'
    """
    if not dax_expr:
        return "\u2014"

    upper = dax_expr.upper()
    detected = [label for kw, label in _DAX_KEYWORDS if kw in upper]

    return ", ".join(detected)[:40] or "Basic"
