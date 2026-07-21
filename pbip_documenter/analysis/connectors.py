"""
Data source connector scanning and detection from M/Power Query code.

This module parses M code expressions to identify:
- Data source connectors (SQL, SharePoint, cloud services, etc.)
- Connection parameters and server references
- Table-to-source mappings
"""

import re as _re
import typing

from pbip_documenter.analysis.registries import _NON_CONN, _NS_CAT, CONNECTOR_MAP


def _is_conn(fn: str) -> typing.Any:
    """
    Check if a function name represents a data connector (vs. transform).

    Args:
        fn: Function name from M code

    Returns:
        True if this is a data source connector function
    """
    return not any(fn.startswith(p) for p in _NON_CONN)


def _label_from_fn(fn: str) -> typing.Any:
    """
    Get friendly label and category for a connector function.

    Args:
        fn: Connector function name

    Returns:
        Tuple of (friendly_label, category)
    """
    if fn in CONNECTOR_MAP:
        return CONNECTOR_MAP[fn]
    ns = fn.split(".")[0]
    return (fn, _NS_CAT.get(ns, "Other"))


def _scan_all_sources(exprs: list[dict], tables: list[dict]) -> typing.Any:
    """
    Scan all M code to identify data sources and their usage.

    Parses both standalone expressions and table partition M code
    to build a comprehensive view of data connections.

    Args:
        exprs: List of expression objects from semantic model
        tables: List of table objects with partition definitions

    Returns:
        List of source dictionaries with keys:
        - fn: Connector function name
        - label: Human-readable label
        - cat: Category (SQL, Azure, Cloud, etc.)
        - server: Server/URL reference
        - table_count: Number of consuming tables
        - table_names: List of consuming table names
    """
    # Extract parameter values for reference resolution
    param_vals: dict[str, str] = {}
    for e in exprs:
        et = e.get("expression", "") or ""
        if "IsParameterQuery=true" in et:
            m = _re.match(r'\s*"([^"]+)"', et)
            if m:
                param_vals[e.get("name", "")] = m.group(1)

    # Collect all M code chunks with their source identifiers
    chunks: list[tuple[str, str]] = []
    chunks.extend(("expr:" + e.get("name", "?"), e.get("expression", "") or "") for e in exprs)
    for t in tables:
        for p in t.get("partitions", []):
            mc = p.get("m_expression", "") or ""
            if mc:
                chunks.append(("tbl:" + (t.get("name") or "?"), mc))

    # Pattern: Source = ConnectorFunction("server", ...)
    pat = _re.compile(r"Source\s*=\s*([A-Za-z][\w]*\.[A-Za-z][\w]*)\s*\(([^)]*)")
    sources: dict[tuple[str, str], set[str]] = {}

    for src_name, code in chunks:
        for m in pat.finditer(code):
            fn = m.group(1)
            if not _is_conn(fn):
                continue

            raw = m.group(2).strip()

            # Extract first parameter (usually server/URL)
            lit = _re.match(r'"([^"]*)"', raw)
            first = lit.group(1) if lit else "(auto-detect)"

            # Check for parameter references
            if not lit:
                par = _re.match(r'#?"([^"]+)"', raw)
                if par:
                    first = param_vals.get(par.group(1), "#" + par.group(1))

            sources.setdefault((fn, first), set()).add(src_name)

    # Sort by category priority, then alphabetically by label
    cat_order: dict[typing.Any, typing.Any] = {
        "SharePoint": 0,
        "SQL": 1,
        "Azure": 2,
        "Cloud": 3,
        "Web": 4,
        "File": 5,
        "Other": 6,
    }

    result: list[typing.Any] = []
    for (fn, server), users in sources.items():
        label, cat = _label_from_fn(fn)
        result.append(
            {
                "fn": fn,
                "label": label,
                "cat": cat,
                "server": server,
                "table_count": len(users),
                "table_names": sorted(users),
            }
        )

    result.sort(key=lambda x: (cat_order.get(x["cat"], 9), x["label"]))
    return result


def _detect_connectors(exprs: list[dict], tables: list[dict]) -> typing.Any:
    """
    Quick scan for connector presence (lightweight check).

    Args:
        exprs: List of expression objects
        tables: List of table objects

    Returns:
        Set of (function_name, label, category) tuples found in code
    """
    combined = " ".join((e.get("expression", "") or "") for e in exprs)
    combined += " ".join((p.get("m_expression", "") or "") for t in tables for p in t.get("partitions", []))

    return {(fn, lbl, cat) for fn, (lbl, cat) in CONNECTOR_MAP.items() if fn + "(" in combined}
