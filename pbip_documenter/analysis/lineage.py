"""Data lineage diagram generation."""

import math
import typing

from pbip_documenter.analysis.connectors import _scan_all_sources
from pbip_documenter.config import _LINEAGE_MAX_ROWS, C
from pbip_documenter.docx_render.diagrams import (
    _diagram_legend,
    _dml_connector,
    _dml_header_label,
    _dml_shape,
    _emu,
    _insert_diagram,
)
from pbip_documenter.docx_render.typography import page_break


def _lineage_one_slice(
    doc: typing.Any,
    src_slice: typing.Any,
    stg_slice: typing.Any,
    tbl_slice: typing.Any,
    caption: typing.Any,
    part_label: typing.Any = None,
    src_tbl_map: typing.Any = None,
    tbl_pg_map: typing.Any = None,
    pg_slice: typing.Any = None,
) -> typing.Any:
    E = _emu
    LW = E(6.5)
    BADGE_W = E(0.55)
    row_h = E(0.34)
    row_gap = E(0.07)
    hdr_h = E(0.22)
    banner_h = (E(0.20) + E(0.05)) if part_label else 0
    y_start = banner_h + hdr_h + E(0.08)
    PIPE: list[typing.Any] = [
        ("Data Sources", C.RUBINE, src_slice),
        ("Staging Queries", C.MARIGOLD, stg_slice),
        ("Loaded Tables", C.PACIFIC, tbl_slice),
    ]
    active = [(lbl, clr, data) for lbl, clr, data in PIPE if data]
    if not active:
        return
    n_cols = len(active)
    col_gap = E(0.28)
    pipe_w = LW - BADGE_W - E(0.12)
    col_bw = (pipe_w - (n_cols - 1) * col_gap) // n_cols
    col_x = [i * (col_bw + col_gap) for i in range(n_cols)]
    badge_x = pipe_w + E(0.12)
    max_rows = max(len(d) for _, _, d in active)
    LH = y_start + max_rows * (row_h + row_gap) + E(0.1)
    shapes: list[typing.Any] = []
    if part_label:
        shapes.append(_dml_header_label(0, 0, LW, E(0.20), part_label, C.DGRAY))
    for i, (lbl, clr, _) in enumerate(active):
        shapes.append(_dml_header_label(col_x[i], banner_h, col_bw, hdr_h, lbl, clr))
    shapes.append(_dml_header_label(badge_x, banner_h, BADGE_W, hdr_h, "# Pages", C.DGRAY))
    col_pts: list[typing.Any] = []
    col_lbls: list[typing.Any] = []
    for ci, (lbl, color, data) in enumerate(active):
        pts: list[typing.Any] = []
        lbls: list[typing.Any] = []
        for ri, item in enumerate(data):
            y = y_start + ri * (row_h + row_gap)
            if lbl == "Data Sources":
                text = item
                lines = [{"text": text[:24], "sz": 16, "bold": True}]
                bc = color
            elif lbl == "Staging Queries":
                text = item
                lines = [{"text": item[:24], "sz": 14, "bold": True, "color": C.CHARCOAL}]
                bc = color
            else:
                t, tc = item
                text = t.get("name") or "?"
                lines = [{"text": text[:24], "sz": 14, "bold": True}]
                bc = tc
                pg_count = len(tbl_pg_map.get(text, set())) if tbl_pg_map else 0
                bf = "DDDDDD" if not pg_count else C.SKY
                bcol = "AAAAAA" if not pg_count else C.WHITE
                shapes.append(
                    _dml_shape(
                        badge_x,
                        y,
                        BADGE_W,
                        row_h,
                        bf,
                        [{"text": str(pg_count) if pg_count else "\u2014", "sz": 16, "bold": True, "color": bcol}],
                        lIns="18000",
                        rIns="18000",
                        tIns="9000",
                        bIns="9000",
                        anchor="ctr",
                    )
                )
            shapes.append(_dml_shape(col_x[ci], y, col_bw, row_h, bc, lines))
            pts.append((col_x[ci] + col_bw, y + row_h // 2))
            lbls.append(text)
        col_pts.append(pts)
        col_lbls.append(lbls)
    ag = E(0.03)
    for ci in range(n_cols - 1):
        lpts = col_pts[ci]
        llbls = col_lbls[ci]
        rpts = col_pts[ci + 1]
        rlbls = col_lbls[ci + 1]
        lname = active[ci][0]
        rx_start = col_x[ci + 1]
        if not rpts:
            continue
        cmap: dict[typing.Any, typing.Any] = {}
        if lname == "Data Sources" and src_tbl_map:
            for src_lbl in llbls:
                for fn, tbl_set in src_tbl_map.items():
                    if fn.split(".")[0].lower() in src_lbl.lower() or src_lbl.lower() in fn.split(".")[0].lower():
                        cmap[src_lbl] = tbl_set
                        break
        elif lname == "Staging Queries":
            cmap = {s: {s} for s in llbls}
        connected = set()
        if cmap:
            for li, (lx, ly) in enumerate(lpts):
                lbl = llbls[li] if li < len(llbls) else ""
                for ri, (_, ry) in enumerate(rpts):
                    if (rlbls[ri] if ri < len(rlbls) else "") in cmap.get(lbl, set()):
                        shapes.append(_dml_connector(lx + ag, ly, rx_start - ag, ry))
                        connected.add(li)
        for li, (lx, ly) in enumerate(lpts):
            if li not in connected:
                ti = min(li, len(rpts) - 1)
                shapes.append(_dml_connector(lx + ag, ly, rx_start - ag, rpts[ti][1]))
    _insert_diagram(doc, shapes, LW, LH, caption)


def insert_lineage_diagram(doc: typing.Any, summary: typing.Any) -> typing.Any:
    sm = summary.get("semantic_model") or {}
    rpt = summary.get("report") or {}
    tables = sm.get("tables", [])
    pages = rpt.get("pages", [])
    all_sources_data = _scan_all_sources(sm.get("expressions", []), tables)
    src_label_map: dict[typing.Any, typing.Any] = {}
    for s in all_sources_data:
        lbl = s["label"]
        srv = s["server"]
        if srv and srv != "(auto-detect)":
            if "fabric.microsoft.com" in srv:
                hint = "Fabric"
            elif "snowflakecomputing.com" in srv:
                hint = srv.split(".")[0][:10]
            elif "powerplatform" in srv.lower() or "dataflow" in srv.lower():
                hint = ""
            else:
                hint = srv.split(".")[0][:10]
            if hint:
                lbl = f"{lbl} ({hint})"
        display = lbl[:28]
        src_label_map[display] = {n.replace("tbl:", "").replace("expr:", "") for n in s["table_names"]}
    src_labels = list(src_label_map.keys())
    staging = [e["name"] for e in sm.get("expressions", []) if e.get("result_type") == "Table"]
    facts = [t for t in tables if (t.get("name") or "").lower().startswith(("fact_", "fct_"))]
    dims = [t for t in tables if (t.get("name") or "").lower().startswith(("dim_", "dimension_"))]
    others = [t for t in tables if t not in facts and t not in dims]
    all_t = [(t, C.PACIFIC) for t in facts] + [(t, C.EVERGREEN) for t in dims] + [(t, C.TEAL) for t in others]
    tbl_pg_map: dict[typing.Any, typing.Any] = {}
    for pg in pages:
        for v in pg.get("visuals", []):
            for f in v.get("fields", []):
                ent = f.get("entity", "")
                if ent and ent != ".":
                    tbl_pg_map.setdefault(ent, set()).add(pg.get("display_name", "?"))
    max_rows = max(len(src_labels), len(staging) or 1, len(all_t), 1)
    if max_rows <= _LINEAGE_MAX_ROWS:
        _lineage_one_slice(
            doc,
            src_labels,
            staging,
            all_t,
            caption="Figure 1 \u2014 Data lineage: source systems to loaded tables",
            src_tbl_map=src_label_map,
            tbl_pg_map=tbl_pg_map,
        )
    else:
        n = math.ceil(max_rows / _LINEAGE_MAX_ROWS)
        slices = [
            (
                src_labels[i * _LINEAGE_MAX_ROWS : (i + 1) * _LINEAGE_MAX_ROWS],
                staging[i * _LINEAGE_MAX_ROWS : (i + 1) * _LINEAGE_MAX_ROWS],
                all_t[i * _LINEAGE_MAX_ROWS : (i + 1) * _LINEAGE_MAX_ROWS],
            )
            for i in range(n)
        ]
        slices = [s for s in slices if any(s)]
        for si, (ss, st, stbl) in enumerate(slices):
            tn = ", ".join((t.get("name") or "?") for t, _ in stbl[:3])
            if len(stbl) > 3:
                tn += f" ... +{len(stbl) - 3}"
            cap = f"Figure 1.{si + 1} \u2014 Data lineage part {si + 1}/{len(slices)}"
            if stbl:
                cap += f" | tables: {tn}"
            _lineage_one_slice(
                doc,
                ss,
                st,
                stbl,
                caption=cap,
                part_label=f"Lineage diagram \u2014 part {si + 1} / {len(slices)}",
                src_tbl_map=src_label_map,
                tbl_pg_map=tbl_pg_map,
            )
            if si < len(slices) - 1:
                page_break(doc)
    _diagram_legend(
        doc,
        [
            ("\u25a0 Sources", C.RUBINE),
            ("\u25a0 Staging", C.MARIGOLD),
            ("\u25a0 Facts", C.PACIFIC),
            ("\u25a0 Dims", C.EVERGREEN),
            ("\u25a0 Utility", C.TEAL),
            ("\u25a0 # Pages", C.SKY),
        ],
    )
