"""Hybrid star-schema relationship diagrams for Word.

Editable layout guide:
- `_build_layout()` decides which lane each table node uses and where the node center is placed.
- `_render_focus()` assembles the final DrawingML canvas: internal title, connectors, nodes,
  grouped-summary cards, legend, canvas height and caption.
- `_hidden()` creates the grouped-summary cards such as Related fact / domain and Helper summary.
- `_legend()` controls the legend labels, swatch position, item width and item height.
- `config.py` controls how many diagrams, tables and relationships are shown.

Coordinate system:
- All diagram positions use `_emu(inches)`, so `_emu(1.0)` means one inch from the top-left
  of the diagram canvas.
- Small layout edits should usually be 0.05 to 0.20 inches.

Pagination rule:
- The schema canvas must fit within a landscape page together with the section heading
  and caption. Oversized canvases can create blank pages even if the XML compiles.
"""

from __future__ import annotations

import re
import textwrap
from collections import Counter, defaultdict, deque

from pbip_documenter.config import (
    _SCHEMA_EDGE_RENDER_LIMIT,
    _SCHEMA_FOCUS_MAX_NODES,
    _SCHEMA_MAX_ANCHORS,
    _SCHEMA_MAX_DIAGRAMS,
    _SCHEMA_SUMMARY_GROUPS,
    C,
)
from pbip_documenter.docx_render.diagrams import _box_edge_point, _dml_connector, _dml_shape, _emu, _insert_diagram
from pbip_documenter.docx_render.typography import callout

LIGHT = {C.BLIGHT, C.LGRAY, C.SUBTLE, C.TAN, C.MARIGOLD}
FILL = {"fact": C.PACIFIC, "dim": C.EVERGREEN, "date": C.TAN, "plan": C.RUBINE, "domain": C.SKY, "helper": C.BLIGHT}
DOMAIN = {"fact", "plan", "domain"}

# SCHEMA LAYOUT TUNING CONSTANTS
# All values below are inches unless noted otherwise. Values are converted with _emu(value).
SCHEMA_TITLE_SZ = 20  # Diagram title font size in DrawingML half-points. 16 = 8 pt minimum.
SCHEMA_CANVAS_W_IN = 10.10  # Whole diagram canvas width. Increase only if landscape page width/margins allow it.
SCHEMA_CANVAS_H_IN = 6.43  # Whole diagram canvas height. This is the main setting for total diagram height.
SCHEMA_SAFE_AVAILABLE_H_IN = 7.2  # Estimated safe vertical budget for heading + diagram + caption on landscape page.
SCHEMA_EST_SECTION_HEADING_H_IN = (
    0.32  # Estimated height consumed by the "Semantic model relationship diagrams" heading.
)
SCHEMA_EST_CAPTION_H_IN = 0.22  # Estimated height consumed by the figure caption below the diagram.
SCHEMA_TITLE_Y_IN = 0  # Vertical position of the internal "Schema relationship focus" title inside the canvas.
SCHEMA_TOP_NODE_Y_IN = 0.78  # Vertical position of the top row of table nodes.
SCHEMA_ANCHOR_Y_IN = 2.65  # Vertical position of the central anchor/fact table node.
SCHEMA_BOTTOM_NODE_Y_IN = 4.67  # Vertical position of the bottom row of table nodes.
SCHEMA_DIM_LANE_TOP_IN = 0.88  # Top y-boundary for dimension/date lanes on the left and right.
SCHEMA_DIM_LANE_BOTTOM_IN = 4.75  # Bottom y-boundary for dimension/date lanes on the left and right.
SCHEMA_MID_LANE_TOP_IN = 1.6  # Top y-boundary for extra mid-lane fact/domain/planning nodes.
SCHEMA_MID_LANE_BOTTOM_IN = 3.95  # Bottom y-boundary for extra mid-lane fact/domain/planning nodes.
SCHEMA_GROUP_Y_IN = 5.6  # Vertical position of hidden-table summary cards, e.g. Related fact / domain, Helper summary.
SCHEMA_GROUP_CARD_W_IN = 2.90  # Width of each hidden-table summary card.
SCHEMA_GROUP_CARD_H_IN = 0.34  # Height of each hidden-table summary card.
SCHEMA_GROUP_GAP_IN = 0.08  # Horizontal gap between hidden-table summary cards.
SCHEMA_LEGEND_Y_IN = 6.1  # Vertical position of the legend row.
SCHEMA_LEGEND_ITEM_W_IN = 1.5  # Width of each legend item box.
SCHEMA_LEGEND_ITEM_H_IN = 0.25  # Height of each legend item box.
SCHEMA_LEGEND_GAP_IN = 0.05  # Gap between legend item boxes.
SCHEMA_LEGEND_SWATCH_SIZE_IN = 0.13  # Size of the colored legend square.
SCHEMA_NODE_CLAMP_TOP_IN = 0.60  # Highest allowed node center after overlap-relief nudging.
SCHEMA_NODE_CLAMP_BOTTOM_IN = 5  # Lowest allowed node center; keep above SCHEMA_GROUP_Y_IN to avoid card overlap.


def _norm(n):
    return re.sub(r"[^a-z0-9]+", " ", (n or "").lower()).strip()


def _role(t):
    n = _norm(t.get("name", ""))
    m = len(t.get("measures", []) or [])
    if any(
        x in n
        for x in (
            "rls",
            "security",
            "selector",
            "param",
            "threshold",
            "refresh",
            "freshness",
            "mapping",
            "datasource",
            "landing page",
        )
    ):
        return "helper"
    if (
        n.startswith("dim date")
        or n.startswith("table date")
        or "calendar" in n
        or n in ("_cal", "_cal cm", "cal comarketing")
    ):
        return "date"
    if n.startswith("dim ") or n.startswith("dim") or "dimension" in n:
        return "dim"
    if "fact" in n or n.startswith("fct") or m >= 15:
        return "fact"
    if any(x in n for x in ("deviation", "table new", "forecast", "plan", "pot")):
        return "plan"
    return "domain"


def _usage(summary):
    c = Counter()
    for p in (summary.get("report") or {}).get("pages", []) or []:
        for v in p.get("visuals", []) or []:
            for f in v.get("fields", []) or []:
                if f.get("entity"):
                    c[f["entity"]] += 1
    return c


def _score(n, tm, g, u):
    t = tm[n]
    r = _role(t)
    bonus = {"fact": 45, "plan": 32, "domain": 24, "dim": -34, "date": -22, "helper": -30}[r]
    return len(g[n]) * 20 + len(t.get("measures", []) or []) * 8 + u.get(n, 0) * 2 + bonus


def _components(g):
    seen = set()
    out = []
    for n in g:
        if n in seen:
            continue
        q = [n]
        seen.add(n)
        comp = []
        while q:
            x = q.pop()
            comp.append(x)
            for y in g[x]:
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        out.append(sorted(comp))
    return out


def analyze_relationship_landscape(summary):
    sm = summary.get("semantic_model") or {}
    tables = sm.get("tables", []) or []
    rels = sm.get("relationships", []) or []
    tm = {t.get("name"): t for t in tables if t.get("name")}
    g = {n: set() for n in tm}
    pc = Counter()
    u = _usage(summary)
    for r in rels:
        a, b = r.get("from_table"), r.get("to_table")
        if a in g and b in g:
            g[a].add(b)
            g[b].add(a)
            pc[tuple(sorted((a, b)))] += 1
    comps = []
    for c in _components(g):
        e = sum(1 for r in rels if r.get("from_table") in c and r.get("to_table") in c)
        comps.append(
            {
                "nodes": c,
                "size": len(c),
                "edges": e,
                "is_large": e > 0 and len(c) >= 2,
                "score": sum(_score(n, tm, g, u) for n in c) + e * 20,
            }
        )
    comps.sort(key=lambda x: (-x["is_large"], -x["score"]))
    return {
        "table_map": tm,
        "relationships": rels,
        "graph": g,
        "pair_counts": dict(pc),
        "components": comps,
        "usage": dict(u),
    }


# TWEAK: anchor selection
# Selects tables that deserve their own focused diagram. Scoring favors fact/planning/domain
# tables with many relationships, many measures and report usage. Increase _SCHEMA_MAX_ANCHORS
# in config.py if more focused views are needed.
def _anchors(comp, tm, g, u):
    cand = [n for n in comp["nodes"] if _role(tm[n]) in DOMAIN and g[n]] or [n for n in comp["nodes"] if g[n]]
    return sorted(cand, key=lambda n: (-_score(n, tm, g, u), n))[:_SCHEMA_MAX_ANCHORS]


def _anchor(comp, tm, g, u):
    anchors = _anchors(comp, tm, g, u)
    return anchors[0] if anchors else comp["nodes"][0]


def _dist(a, nodes, g):
    d = {a: 0}
    q = deque([a])
    nodes = set(nodes)
    while q:
        x = q.popleft()
        for y in g[x]:
            if y in nodes and y not in d:
                d[y] = d[x] + 1
                q.append(y)
    return d


# TWEAK: hidden-table summary card labels
# Tables that do not fit into a focused diagram are grouped here. The resulting labels
# become the summary cards below the diagram, for example "Related fact / domain" and
# "Helper summary". Their position and size are controlled by SCHEMA_GROUP_* constants.
def _hidden(hidden, tm):
    lab = {
        "dim": "Dimensions",
        "date": "Calendar / date",
        "plan": "Planning / deviation",
        "domain": "Related fact / domain",
        "fact": "Fact tables",
        "helper": "Helper summary",
    }
    d = defaultdict(list)
    for n in hidden:
        d[lab[_role(tm[n])]].append(n)
    rows = [
        {"label": k, "count": len(v), "sample": ", ".join(v[:2]) + ("..." if len(v) > 2 else "")} for k, v in d.items()
    ]
    return sorted(rows, key=lambda r: -r["count"])[:_SCHEMA_SUMMARY_GROUPS]


# TWEAK: explicit tables per focused view
# Chooses visible tables for a focused diagram: anchor first, then direct neighbors, then
# nearby/high-scoring tables until _SCHEMA_FOCUS_MAX_NODES. Hidden tables become summary cards.
def _view(comp, analysis, anchor=None):
    tm, g, u, rels = analysis["table_map"], analysis["graph"], Counter(analysis["usage"]), analysis["relationships"]
    a = anchor or _anchor(comp, tm, g, u)
    direct = sorted(
        [n for n in g[a] if n in comp["nodes"]],
        key=lambda n: (_role(tm[n]) not in ("dim", "date"), -_score(n, tm, g, u)),
    )
    visible = [a] + direct[: _SCHEMA_FOCUS_MAX_NODES - 1]
    if len(visible) < _SCHEMA_FOCUS_MAX_NODES:
        d = _dist(a, comp["nodes"], g)
        extra = sorted(
            [n for n in comp["nodes"] if n not in visible], key=lambda n: (d.get(n, 9), -_score(n, tm, g, u))
        )
        visible += extra[: _SCHEMA_FOCUS_MAX_NODES - len(visible)]
    visible = list(dict.fromkeys(visible))
    vs = set(visible)
    hidden = [n for n in comp["nodes"] if n not in vs]
    return {
        "kind": "focus",
        "title": f"{a} - focused schema",
        "anchor": a,
        "visible": visible,
        "relationships": [r for r in rels if r.get("from_table") in vs and r.get("to_table") in vs],
        "hidden": hidden,
        "groups": _hidden(hidden, tm),
        "component_size": comp["size"],
    }


def _remainder(comps):
    members = sum([c["nodes"] for c in comps], [])
    return {
        "kind": "remainder",
        "title": "Grouped helper and disconnected tables",
        "groups": [
            {
                "label": "Other / disconnected tables",
                "count": len(members),
                "sample": ", ".join(members[:2]) + "..." if len(members) > 2 else ", ".join(members),
            }
        ],
        "component_count": len(comps),
        "table_count": len(members),
    }


def plan_schema_views(summary):
    a = analyze_relationship_landscape(summary)
    comps = a["components"]
    tm = a["table_map"]
    g = a["graph"]
    u = Counter(a["usage"])
    views = []
    for c in [x for x in comps if x["is_large"]]:
        for anchor in _anchors(c, tm, g, u):
            if len(views) >= _SCHEMA_MAX_DIAGRAMS:
                break
            v = _view(c, a, anchor)
            if v["relationships"]:
                views.append(v)
        if len(views) >= _SCHEMA_MAX_DIAGRAMS:
            break
    return a, views


def _wrap(s, w):
    lines = textwrap.wrap(str(s).replace("_", " "), width=w, break_long_words=False) or [""]
    return lines[:1] + ([lines[1][: w - 1] + "..."] if len(lines) > 2 else lines[1:])


def _txt(fill):
    return C.DGRAY if fill in LIGHT else C.WHITE


def _span(count, start, end):
    if count <= 0:
        return []
    if count == 1:
        return [int((start + end) / 2)]
    step = (end - start) / max(count - 1, 1)
    return [int(start + i * step) for i in range(count)]


def _build_layout(view, tm):
    # TWEAK: node placement inside the schema diagram canvas.
    # Layout lanes: anchor center, dimensions/date left/right, facts/domain/planning top/bottom/middle.
    anchor = view["anchor"]
    dims = [n for n in view["visible"] if n != anchor and _role(tm[n]) in ("dim", "date")]
    facts = [n for n in view["visible"] if n != anchor and n not in dims]
    pos = {anchor: (_emu(5.10), _emu(SCHEMA_ANCHOR_Y_IN), True)}
    left = dims[0::2]
    right = dims[1::2]
    for n, y in zip(left, _span(len(left), _emu(SCHEMA_DIM_LANE_TOP_IN), _emu(SCHEMA_DIM_LANE_BOTTOM_IN)), strict=False):
        pos[n] = (_emu(1.15), y, False)
    for n, y in zip(right, _span(len(right), _emu(SCHEMA_DIM_LANE_TOP_IN), _emu(SCHEMA_DIM_LANE_BOTTOM_IN)), strict=False):
        pos[n] = (_emu(9.05), y, False)
    top = facts[:6]
    bottom = facts[6:12]
    mid = facts[12:]
    for n, x in zip(top, _span(len(top), _emu(2.15), _emu(8.05)), strict=False):
        pos[n] = (x, _emu(SCHEMA_TOP_NODE_Y_IN), False)
    for n, x in zip(bottom, _span(len(bottom), _emu(2.15), _emu(8.05)), strict=False):
        pos[n] = (x, _emu(SCHEMA_BOTTOM_NODE_Y_IN), False)
    mid_left = mid[0::2]
    mid_right = mid[1::2]
    for n, y in zip(mid_left, _span(len(mid_left), _emu(SCHEMA_MID_LANE_TOP_IN), _emu(SCHEMA_MID_LANE_BOTTOM_IN)), strict=False):
        pos[n] = (_emu(2.85), y, False)
    for n, y in zip(mid_right, _span(len(mid_right), _emu(SCHEMA_MID_LANE_TOP_IN), _emu(SCHEMA_MID_LANE_BOTTOM_IN)), strict=False):
        pos[n] = (_emu(7.35), y, False)
    widths = {n: _emu(1.62 if n == anchor else 1.16) for n in view["visible"]}
    heights = {n: _emu(0.56 if n == anchor else 0.45) for n in view["visible"]}
    coords = {n: [pos[n][0], pos[n][1]] for n in view["visible"]}
    names = list(view["visible"])
    for _ in range(6):
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                dx = coords[b][0] - coords[a][0]
                dy = coords[b][1] - coords[a][1]
                nx = widths[a] / 2 + widths[b] / 2 + _emu(0.12)
                ny = heights[a] / 2 + heights[b] / 2 + _emu(0.10)
                if abs(dx) < nx and abs(dy) < ny:
                    push = (ny - abs(dy)) / 2 + _emu(0.02)
                    coords[a][1] -= push if dy >= 0 else -push
                    coords[b][1] += push if dy >= 0 else -push
        for n in names:
            coords[n][0] = max(_emu(0.55), min(_emu(9.65), coords[n][0]))
            coords[n][1] = max(_emu(SCHEMA_NODE_CLAMP_TOP_IN), min(_emu(SCHEMA_NODE_CLAMP_BOTTOM_IN), coords[n][1]))
    return {n: (coords[n][0], coords[n][1], pos[n][2]) for n in names}, widths, heights


def _node(shapes, n, t, cx, cy, w, h, sid, anchor=False):
    fill = FILL[_role(t)]
    color = _txt(fill)
    lines = [
        {"text": x, "sz": 14 if anchor and i == 0 else 11, "bold": True, "color": color}
        for i, x in enumerate(_wrap(n, 18 if anchor else 14))
    ]
    meta = f"{len(t.get('columns', []) or [])} col" + (
        f" · {len(t.get('measures', []) or [])} meas" if t.get("measures") else ""
    )
    lines.append({"text": meta, "sz": 8, "color": color})
    shapes.append(
        _dml_shape(
            int(cx - w / 2),
            int(cy - h / 2),
            w,
            h,
            fill,
            lines,
            border_color="D6D6D6",
            border_w="38100" if anchor else "25400",
            adj="9000",
            shape_id=sid,
            shape_name=n,
        )
    )


def _idx(p, q):
    sx, sy = p
    tx, ty = q
    if abs(tx - sx) >= abs(ty - sy):
        return ("3", "1") if tx >= sx else ("1", "3")
    return ("2", "0") if ty >= sy else ("0", "2")


# TWEAK: legend row labels and sizing
# These are the legend labels and colors. Vertical position is SCHEMA_LEGEND_Y_IN.
# Legend item box size is SCHEMA_LEGEND_ITEM_W_IN x SCHEMA_LEGEND_ITEM_H_IN.
def _legend(shapes, y):
    items = [
        ("Fact / anchor", FILL["fact"]),
        ("Dimension", FILL["dim"]),
        ("Planning / deviation", FILL["plan"]),
        ("Related fact / domain", FILL["domain"]),
        ("Helper", FILL["helper"]),
    ]
    x = _emu(0.55)
    for lab, col in items:
        shapes.append(
            _dml_shape(
                x,
                y,
                _emu(SCHEMA_LEGEND_ITEM_W_IN),
                _emu(SCHEMA_LEGEND_ITEM_H_IN),
                "F2F2F2",
                [{"text": lab, "sz": 12, "bold": True, "color": C.DGRAY}],
                border_color="D6D6D6",
                border_w="19050",
                adj="8000",
                lIns="26000",
            )
        )
        shapes.append(
            _dml_shape(
                x + _emu(0.06),
                y + _emu(0.045),
                _emu(SCHEMA_LEGEND_SWATCH_SIZE_IN),
                _emu(SCHEMA_LEGEND_SWATCH_SIZE_IN),
                col,
                [],
                border_color=C.DGRAY,
                border_w="12700",
                adj="8000",
            )
        )
        x += _emu(SCHEMA_LEGEND_ITEM_W_IN + SCHEMA_LEGEND_GAP_IN)


def _render_focus(doc, view, analysis, fig):
    # TWEAK: per-diagram rendering. Assembles title, connectors, nodes, summary cards, legend and caption.
    tm = analysis["table_map"]
    pos, w, h = _build_layout(view, tm)
    base = fig * 10000
    ids = {n: base + 1000 + i for i, n in enumerate(view["visible"], 1)}
    shapes = []
    defaultdict(int)
    shapes.append(
        _dml_shape(
            _emu(0.55),
            _emu(SCHEMA_TITLE_Y_IN),
            _emu(9.0),
            _emu(0.30),
            None,
            [
                {
                    "text": f"Schema relationship focus: {view['anchor']}",
                    "sz": max(SCHEMA_TITLE_SZ, 16),
                    "bold": True,
                    "color": C.PACIFIC,
                }
            ],
            border_color=None,
            border_w="0",
            geom="rect",
            adj=None,
            lIns="0",
            rIns="0",
            tIns="0",
            bIns="0",
        )
    )
    rels = sorted(
        view["relationships"],
        key=lambda r: (0 if view["anchor"] in (r.get("from_table"), r.get("to_table")) else 1, r.get("from_table", "")),
    )[:_SCHEMA_EDGE_RENDER_LIMIT]
    for i, r in enumerate(rels, 1):
        a, b = r.get("from_table"), r.get("to_table")
        if a not in pos or b not in pos:
            continue
        x1, y1, _ = pos[a]
        x2, y2, _ = pos[b]
        sx, sy = _box_edge_point(x1, y1, w[a] // 2, h[a] // 2, x2, y2)
        ex, ey = _box_edge_point(x2, y2, w[b] // 2, h[b] // 2, x1, y1)
        si, ei = _idx((x1, y1), (x2, y2))
        both = (r.get("cross_filtering") or "").lower() in ("both", "bi", "bidirectional")
        shapes.append(
            _dml_connector(
                sx,
                sy,
                ex,
                ey,
                color="8A8A8A",
                dashed=not r.get("is_active", True),
                start_arrow=both,
                end_arrow=True,
                connector_id=base + 2000 + i,
                start_shape_id=ids[a],
                end_shape_id=ids[b],
                start_idx=si,
                end_idx=ei,
            )
        )
    for n in view["visible"]:
        x, y, anch = pos[n]
        _node(shapes, n, tm[n], x, y, w[n], h[n], ids[n], anch)
    if view.get("groups"):
        x = _emu(0.55)
        y = _emu(SCHEMA_GROUP_Y_IN)
        gap = _emu(SCHEMA_GROUP_GAP_IN)
        cw = _emu(SCHEMA_GROUP_CARD_W_IN)
        for g in view["groups"][:3]:
            shapes.append(
                _dml_shape(
                    x,
                    y,
                    cw,
                    _emu(SCHEMA_GROUP_CARD_H_IN),
                    "F2F2F2",
                    [
                        {"text": g["label"], "sz": 16, "bold": True, "color": C.DGRAY},
                        {"text": f"{g['count']} table(s) - {g['sample']}", "sz": 10, "color": C.DGRAY},
                    ],
                    border_color="D6D6D6",
                    border_w="19050",
                    adj="8000",
                )
            )
            x += cw + gap
    estimated_block_h = SCHEMA_EST_SECTION_HEADING_H_IN + SCHEMA_CANVAS_H_IN + SCHEMA_EST_CAPTION_H_IN
    if estimated_block_h > SCHEMA_SAFE_AVAILABLE_H_IN:
        callout(
            doc,
            f"Schema diagram height budget exceeded ({estimated_block_h:.2f} in > {SCHEMA_SAFE_AVAILABLE_H_IN:.2f} in). Reduce SCHEMA_CANVAS_H_IN or heading/caption spacing.",
            kind="warn",
        )
    _legend(shapes, _emu(SCHEMA_LEGEND_Y_IN))
    _insert_diagram(
        doc,
        shapes,
        _emu(SCHEMA_CANVAS_W_IN),
        _emu(SCHEMA_CANVAS_H_IN),
        caption=f"Figure {fig} - {view['title']} ({view['component_size']} tables, {len(rels)} prioritized relationships).",
    )


def _render_remainder(doc, view, fig):
    shapes = []
    _legend(shapes, _emu(4.25))
    _insert_diagram(doc, shapes, _emu(10.1), _emu(4.8), caption=f"Figure {fig} - {view['title']}.")


def insert_star_schema(doc, summary):
    analysis, views = plan_schema_views(summary)
    if not analysis["table_map"]:
        callout(doc, "No semantic model tables found - relationship diagram cannot be generated.")
        return "Schema views unavailable (no tables)"
    if not views:
        callout(doc, "No connected components detected - relationship diagram cannot be generated.")
        return "Schema views unavailable (no relationships)"
    rendered = 0
    for i, v in enumerate(views, 2):
        if v.get("kind") != "focus":
            continue
        _render_focus(doc, v, analysis, i)
        rendered += 1
    if rendered == 0:
        callout(
            doc,
            "No non-empty schema focus diagrams were rendered. Details remain in inventory and relationship tables.",
            kind="info",
        )
    return f"Semantic model relationship diagrams ({rendered} diagram(s))"
