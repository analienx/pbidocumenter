"""Wireframe page layout diagram generation."""

import typing

from pbip_documenter.analysis.registries import (
    _BTN_VTS,
    _DECO_VTS,
    _SLICER_VTS,
    _TYPE_ABBREV,
    _UNKNOWN,
    _VD,
)
from pbip_documenter.config import C
from pbip_documenter.docx_render.diagrams import (
    _dml_shape,
    _emu,
    _insert_diagram,
)
from pbip_documenter.docx_render.typography import body

# Mutable counter (module-level state)
_DIAGRAM_ID_COUNTER: list[typing.Any] = [1000]


def _pick_rep_field(fields: typing.Any, vt: typing.Any) -> typing.Any:
    IS_SLICER = vt in _SLICER_VTS
    IS_CHART = vt in {
        "barChart",
        "columnChart",
        "clusteredBarChart",
        "clusteredColumnChart",
        "lineChart",
        "areaChart",
        "stackedBarChart",
        "stackedColumnChart",
        "lineClusteredColumnComboChart",
        "lineStackedColumnComboChart",
        "ribbonChart",
        "waterfallChart",
        "funnelChart",
        "scatterChart",
        "donutChart",
        "pieChart",
        "treemap",
        "decompositionTreeVisual",
    }

    def _lbl(f: typing.Any) -> typing.Any:
        ent = (f.get("entity", "") or "").strip()
        prop = (f.get("property", "") or "").strip()
        if not prop or prop == ".":
            return None
        return f"{ent}.{prop}"[:28] if ent and ent != "." else prop[:28]

    if IS_SLICER:
        for f in fields:
            prop = (f.get("property", "") or "").strip()
            if prop and prop != ".":
                return prop[:28]
        return None
    if IS_CHART:
        VALUE_ROLES: set[typing.Any] = {"Y", "Values", "Value", "Measure", "Size", "Y Axis"}
        return next((l for f in fields if f.get("role", "") in VALUE_ROLES for l in [_lbl(f)] if l), None) or next(
            (l for f in fields for l in [_lbl(f)] if l), None
        )
    return next((l for f in fields for l in [_lbl(f)] if l), None)


def _infer_custom_visual_type(vis: typing.Any) -> typing.Any:
    roles = {(f.get("role", "") or "").lower() for f in vis.get("fields", [])}
    if roles & {"category", "series", "values", "y", "x", "legend"}:
        return "Custom Chart"
    if roles & {"rows", "columns", "values"}:
        return "Custom Pivot"
    if roles & {"geography", "latitude", "longitude", "location"}:
        return "Custom Map"
    if roles & {"value", "target", "status"}:
        return "Custom KPI"
    if roles & {"field", "fields", "data"}:
        return "Custom Table"
    return "Custom Visual"


def _classify_slicer_readability(width_emu: typing.Any, full_w_emu: typing.Any) -> typing.Any:
    """Classify slicer label readability as 'full', 'abbr', or 'tiny'."""
    if width_emu >= full_w_emu:
        return "full"
    if width_emu >= _emu(0.30):
        return "abbr"
    return "tiny"


def _donate_to_rescue_slicers(
    row: typing.Any, adj_widths: typing.Any, readable_w_emu: typing.Any, donor_floors: typing.Any
) -> typing.Any:
    """Donate width from oversized non-slicer visuals to unreadable slicers."""
    unreadable = sorted(
        [
            (i, readable_w_emu - adj_widths[i])
            for i, it in enumerate(row)
            if it["cat"] == "slicer" and adj_widths[i] < readable_w_emu
        ],
        key=lambda x: x[1],
    )
    if not unreadable:
        return adj_widths

    new_widths = list(adj_widths)
    cap: dict[typing.Any, typing.Any] = {}
    for i, it in enumerate(row):
        cat = it["cat"]
        if cat in ("slicer", "button"):
            continue
        floor = donor_floors.get(cat)
        if floor is not None and adj_widths[i] > floor:
            cap[i] = adj_widths[i] - floor

    pool = sum(cap.values())
    if pool <= 0:
        return adj_widths

    for slicer_idx, deficit in unreadable:
        if pool <= 0:
            break
        need = min(int(deficit), pool)
        if need <= 0:
            continue
        given = 0
        for d_idx in sorted(cap, key=lambda i: -cap[i]):
            if cap[d_idx] <= 0 or given >= need:
                break
            take = min(cap[d_idx], need - given)
            new_widths[d_idx] -= take
            cap[d_idx] -= take
            given += take
        new_widths[slicer_idx] += given
        pool -= given

    return new_widths


def _find_unreadable_slicer_groups(row: typing.Any, adj_widths: typing.Any, readable_w_emu: typing.Any) -> typing.Any:
    """Return lists of consecutive indices where slicers are below readable width."""
    groups: list[list[typing.Any]] = []
    current: list[typing.Any] = []
    for i, (it, w) in enumerate(zip(row, adj_widths, strict=False)):
        if it["cat"] == "slicer" and w < readable_w_emu:
            current.append(i)
        else:
            if current:
                groups.append(current)
                current = []
    if current:
        groups.append(current)
    return groups


def _should_collapse_group(
    group_indices: typing.Any,
    row: typing.Any,
    adj_widths: typing.Any,
    gap_emu: typing.Any,
    min_group: typing.Any,
    area_title_w_emu: typing.Any,
) -> typing.Any:
    """Return True only when grouped rendering is clearly more informative."""
    if len(group_indices) < min_group:
        return False
    combined_w = sum(adj_widths[i] for i in group_indices) + (len(group_indices) - 1) * gap_emu
    if combined_w < area_title_w_emu:
        return False
    return any(
        (f.get("property") or "").strip() not in ("", ".")
        for i in group_indices
        for f in row[i]["vis"].get("fields", [])
    )


def _collapse_slicer_group(
    row: typing.Any, adj_widths: typing.Any, group_indices: typing.Any, gap_emu: typing.Any
) -> typing.Any:
    """Collapse exactly one consecutive slicer group into a Slicer Area box."""
    seen, merged_fields = set(), []
    for i in group_indices:
        for f in row[i]["vis"].get("fields", []):
            prop = (f.get("property") or "").strip()
            if prop and prop != "." and prop not in seen:
                seen.add(prop)
                merged_fields.append(prop)

    combined_w = int(sum(adj_widths[i] for i in group_indices) + (len(group_indices) - 1) * gap_emu)
    synthetic = dict(row[group_indices[0]])
    synthetic.update({"name": "Slicer Area", "_area_fields": merged_fields})

    group_set = set(group_indices)
    new_row, new_widths, inserted = [], [], False
    for i, (it, w) in enumerate(zip(row, adj_widths, strict=False)):
        if i in group_set:
            if not inserted:
                new_row.append(synthetic)
                new_widths.append(combined_w)
                inserted = True
        else:
            new_row.append(it)
            new_widths.append(w)

    return new_row, new_widths


def _optimize_row(row: typing.Any, inner_w_in: typing.Any, min_box_w_in: typing.Any = 0.50) -> typing.Any:
    """Merge overcrowded slicers + cap oversized custom visuals."""
    if not row:
        return row

    result = [dict(it) for it in row]

    # 1. Custom visual cap
    n = len(result)
    avg_w_in = (sum(it["fw"] for it in result) * inner_w_in) / max(n, 1)
    if avg_w_in < 0.60 and n > 1:
        CAP_FRAC = 0.20
        total_fw2 = sum(it["fw"] for it in result)
        excess = 0.0
        for it in result:
            is_custom = it["cat"] == "other" or len(it.get("vt", "")) > 20
            if is_custom and (it["fw"] / max(total_fw2, 0.001)) > 0.25:
                cap = total_fw2 * CAP_FRAC
                if it["fw"] > cap:
                    excess += it["fw"] - cap
                    it["fw"] = cap
        if excess > 0:
            priority = [it for it in result if it["cat"] in ("slicer", "card") and it["cat"] != "other"]
            recipients = priority or [it for it in result if it.get("cat") != "other"]
            if recipients:
                share = excess / len(recipients)
                for it in recipients:
                    it["fw"] += share

    # 2. Minimum width enforcement
    min_fw = min_box_w_in / inner_w_in
    for it in result:
        if it["cat"] not in ("button",) and it["fw"] < min_fw:
            it["fw"] = min_fw

    return result


def insert_page_layout(
    doc: typing.Any, page: typing.Any, fig_num: typing.Any = 3, dry_run: typing.Any = False
) -> typing.Any:
    """Zone-based wireframe with proportional sizing.

    Left-sidebar Filters zone when slicers are detected in a left panel.
    Button groups collapse to 'Buttons (N)' area when too many to label.

    When dry_run=True the full geometry is computed but nothing is written to
    the document.  Returns the canvas height in EMU so the caller can make
    accurate pagination decisions before committing any content to the page.
    """
    E = _emu

    CANVAS_W_IN = 6.4
    CANVAS_W = E(CANVAS_W_IN)
    PAD = E(0.06)
    INNER_W = CANVAS_W - 2 * PAD
    GAP = E(0.05)
    ZONE_HDR_H = E(0.17)
    ZONE_GAP = E(0.10)

    CAT_MIN_H: dict[typing.Any, typing.Any] = {
        "table": 1.20,
        "chart": 0.70,
        "card": 0.32,
        "slicer": 0.35,
        "button": 0.26,
        "other": 0.45,
    }
    CAT_MAX_H: dict[typing.Any, typing.Any] = {
        "table": 3.50,
        "chart": 1.10,
        "card": 0.45,
        "slicer": 0.45,
        "button": 0.30,
        "other": 0.65,
    }
    MIN_BOX_W_IN = 0.44
    MIN_BOX_H_IN = 0.26
    SLICER_FULL_LABEL_W_IN = 0.46
    SLICER_AREA_TITLE_W_IN = 0.85
    SLICER_AREA_MIN_GROUP = 2
    BTN_READABLE_W_IN = 0.40  # buttons narrower than this get compact treatment
    BTN_AREA_MIN_GROUP = 3  # min consecutive narrow buttons to collapse
    DONOR_FLOOR_OTHER_W_IN = 0.75
    DONOR_FLOOR_CHART_W_IN = 0.75
    DONOR_FLOOR_CARD_W_IN = 0.62

    # Left-sidebar layout constants
    SIDEBAR_MIN_W_IN = 1.0
    SIDEBAR_MAX_W_IN = 1.6
    SIDEBAR_GAP_EMU = E(0.08)

    GRID = 9525

    def _snap(v: typing.Any) -> typing.Any:
        return round(v / GRID) * GRID

    _CHART_VTS = {
        k
        for k, v in _VD.items()
        if any(
            w in v[0]
            for w in (
                "Chart",
                "Waterfall",
                "Funnel",
                "Scatter",
                "Treemap",
                "Decomp",
                "Area",
                "Ribbon",
                "Flow",
                "Map",
                "Q&A",
                "Combo",
                "Donut",
                "Pie",
            )
        )
    }
    _TABLE_VTS: set[typing.Any] = {"pivotTable", "tableEx"}
    _CARD_VTS: set[typing.Any] = {"card", "cardVisual", "multiRowCard", "kpi", "gauge", "scorecard"}

    def _cat(vt: typing.Any) -> typing.Any:
        if vt in _SLICER_VTS:
            return "slicer"
        if vt in _BTN_VTS:
            return "button"
        if vt in _CARD_VTS:
            return "card"
        if vt in _TABLE_VTS:
            return "table"
        if vt in _DECO_VTS:
            return None
        if not vt:
            return None
        if vt in _CHART_VTS:
            return "chart"
        entry = _VD.get(vt)
        if entry:
            if "Chart" in entry[0] or "Map" in entry[0]:
                return "chart"
            if "Table" in entry[0]:
                return "table"
        return "other"

    def _colors(cat: typing.Any) -> typing.Any:
        if cat == "slicer":
            return C.RUBINE, "FCEEF5"
        if cat == "table":
            return C.EVERGREEN, "EDF8EB"
        if cat in ("card", "chart"):
            return C.PACIFIC, "EDF0F8"
        if cat == "button":
            return C.MARIGOLD, "FFFDE7"
        return C.DGRAY, "F5F5F5"

    # ── 1. Collect visuals ────────────────────────────────────────────────
    pw_pg = max(page.get("width", 1280) or 1280, 1)
    ph_pg = max(page.get("height", 720) or 720, 1)

    items: list[typing.Any] = []
    for vis in page.get("visuals", []):
        if vis.get("is_hidden"):
            continue
        pos = vis.get("position", {})
        if not pos or pos.get("x") is None:
            continue
        vt = (vis.get("visual_type", "") or "").strip()
        cat = _cat(vt)
        if cat is None:
            continue

        entry = _VD.get(vt)
        if entry:
            name = entry[0]
        elif len(vt) > 20 or vt.lower() in _UNKNOWN:
            name = _infer_custom_visual_type(vis)
        else:
            name = vt[:22]

        items.append(
            {
                "vis": vis,
                "vt": vt,
                "cat": cat,
                "name": name,
                "px": pos.get("x", 0),
                "py": pos.get("y", 0),
                "pw": pos.get("width", 100),
                "ph": pos.get("height", 50),
                "fx": pos.get("x", 0) / pw_pg,
                "fy": pos.get("y", 0) / ph_pg,
                "fw": pos.get("width", 100) / pw_pg,
                "fh": pos.get("height", 50) / ph_pg,
            }
        )

    if not items:
        if not dry_run:
            body(doc, f"No data visuals on '{page.get('display_name', '?')}'.", italic=True, color=C.DGRAY)
        return int(E(0.5))

    # ── 2. Zone classification ────────────────────────────────────────────
    if len(items) <= 5:
        header: list[typing.Any] = []
        left_sl: list[typing.Any] = []
        content: list[typing.Any] = items[:]
        footer: list[typing.Any] = []
    else:
        header, left_sl, content, footer = [], [], [], []
        for it in items:
            cy = it["fy"] + it["fh"] / 2
            cx = it["fx"] + it["fw"] / 2
            if cy < 0.18:
                header.append(it)
            elif cy > 0.83:
                footer.append(it)
            elif it["cat"] == "slicer" and cx < 0.28 and it["fw"] < 0.30:
                left_sl.append(it)
            else:
                content.append(it)

        if len(left_sl) < 2:
            content.extend(left_sl)
            left_sl = []
        for lst in (header, left_sl, content, footer):
            lst.sort(key=lambda v: (v["fy"], v["fx"]))

    # Left-sidebar mode: Filters rendered as a left panel beside Content
    left_sidebar_mode = bool(left_sl)
    if left_sidebar_mode:
        max_right_fx = max((it["fx"] + it["fw"]) for it in left_sl)
        sidebar_w_in = max(
            min(max_right_fx * CANVAS_W_IN * 1.15, SIDEBAR_MAX_W_IN),
            SIDEBAR_MIN_W_IN,
        )
        SIDEBAR_W = E(sidebar_w_in)
        CONTENT_X = PAD + SIDEBAR_W + SIDEBAR_GAP_EMU
        CONTENT_W = INNER_W - SIDEBAR_W - SIDEBAR_GAP_EMU
    else:
        SIDEBAR_W = CONTENT_X = CONTENT_W = 0  # unused

    # ── 3. Row-building helper ────────────────────────────────────────────
    def _build_rows(zitems: typing.Any) -> typing.Any:
        """Group items into visual rows by y-proximity (8% of page height)."""
        rows, used = [], set()
        sorted_items = sorted(zitems, key=lambda v: (v["fy"], v["fx"]))
        for i, it in enumerate(sorted_items):
            if i in used:
                continue
            row: list[typing.Any] = [it]
            used.add(i)
            for j, other in enumerate(sorted_items):
                if j in used:
                    continue
                if abs(other["fy"] - it["fy"]) < 0.08:
                    row.append(other)
                    used.add(j)
            row.sort(key=lambda v: v["fx"])
            rows.append(row)
        return rows

    # ── 4. Row-rendering helper ───────────────────────────────────────────
    def _render_rows(rows: typing.Any, x_start: typing.Any, avail_w_emu: typing.Any, y_start: typing.Any) -> typing.Any:
        """Render rows of visuals into shape dicts. Returns (shapes, end_y)."""
        row_shapes: list[typing.Any] = []
        y = y_start
        avail_w_in = avail_w_emu / 914400

        for raw_row in rows:
            # Dense-row split: very crowded rows split slicers into sub-rows
            avg_w_in = avail_w_in / max(len(raw_row), 1)
            if len(raw_row) >= 9 and avg_w_in < 0.35:
                others_r = [it for it in raw_row if it["cat"] != "slicer"]
                slicers_r = [it for it in raw_row if it["cat"] == "slicer"]
                mid = (len(slicers_r) + 1) // 2
                sub_rows: list[typing.Any] = [others_r + slicers_r[:mid], slicers_r[mid:]]
                sub_rows = [sr for sr in sub_rows if sr]
                is_split = True
            else:
                sub_rows = [raw_row]
                is_split = False

            for row in sub_rows:
                row = _optimize_row(row, avail_w_in, MIN_BOX_W_IN)
                total_fw = sum(it["fw"] for it in row)
                available_w = avail_w_emu - (len(row) - 1) * GAP

                # Proportional widths from original page fractions
                raw_widths: list[typing.Any] = []
                for it in row:
                    w = max(it["fw"] * CANVAS_W_IN, MIN_BOX_W_IN) if total_fw > 0 else 1.0
                    raw_widths.append(w)
                total_raw = sum(raw_widths)
                avail_in = available_w / 914400
                if total_raw > avail_in:
                    sf = avail_in / total_raw
                    raw_widths = [w * sf for w in raw_widths]

                # Cap oversized items in dense rows
                if len(raw_widths) >= 5:
                    max_item_w = avail_in * 0.50
                    excess = 0.0
                    for i in range(len(raw_widths)):
                        if raw_widths[i] > max_item_w:
                            excess += raw_widths[i] - max_item_w
                            raw_widths[i] = max_item_w
                    if excess > 0:
                        uncapped = [i for i in range(len(raw_widths)) if raw_widths[i] < max_item_w]
                        if uncapped:
                            share = excess / len(uncapped)
                            for i in uncapped:
                                raw_widths[i] += share

                adj_widths = [max(int(w * 914400), E(0.20)) for w in raw_widths]
                remainder = int(available_w) - sum(adj_widths)
                if remainder != 0 and adj_widths:
                    wi = max(range(len(adj_widths)), key=lambda i: adj_widths[i])
                    adj_widths[wi] = max(adj_widths[wi] + remainder, E(0.20))

                # ── Slicer readability rescue ─────────────────────────
                SLICER_READABLE_W = E(SLICER_FULL_LABEL_W_IN)
                if any(it["cat"] == "slicer" and adj_widths[k] < SLICER_READABLE_W for k, it in enumerate(row)):
                    donor_floors: dict[typing.Any, typing.Any] = {
                        "other": E(DONOR_FLOOR_OTHER_W_IN),
                        "chart": E(DONOR_FLOOR_CHART_W_IN),
                        "card": E(DONOR_FLOOR_CARD_W_IN),
                        "table": E(DONOR_FLOOR_CHART_W_IN),
                    }
                    adj_widths = _donate_to_rescue_slicers(row, adj_widths, SLICER_READABLE_W, donor_floors)
                    _groups = _find_unreadable_slicer_groups(row, adj_widths, SLICER_READABLE_W)
                    for _group in reversed(_groups):
                        if _should_collapse_group(
                            _group, row, adj_widths, GAP, SLICER_AREA_MIN_GROUP, E(SLICER_AREA_TITLE_W_IN)
                        ):
                            row, adj_widths = _collapse_slicer_group(row, adj_widths, _group, GAP)

                # ── Button group collapse ─────────────────────────────
                # Consecutive buttons too narrow to show name → "Buttons (N)"
                BTN_READABLE_W = E(BTN_READABLE_W_IN)
                btn_groups: list[list[typing.Any]] = []
                btn_cur: list[typing.Any] = []
                for k, (it, w) in enumerate(zip(row, adj_widths, strict=False)):
                    if it["cat"] == "button" and w < BTN_READABLE_W and not it.get("_btn_count"):
                        btn_cur.append(k)
                    else:
                        if btn_cur:
                            btn_groups.append(btn_cur)
                        btn_cur = []
                if btn_cur:
                    btn_groups.append(btn_cur)

                for _group in reversed(btn_groups):
                    if len(_group) < BTN_AREA_MIN_GROUP:
                        continue
                    combined_w = sum(adj_widths[k] for k in _group) + (len(_group) - 1) * GAP
                    combined_w = min(combined_w, available_w)
                    if combined_w < E(0.70):
                        continue
                    n_btns = len(_group)
                    synthetic = dict(row[_group[0]])
                    synthetic.update(
                        {
                            "name": f"Buttons ({n_btns})",
                            "_btn_count": n_btns,
                        }
                    )
                    group_set = set(_group)
                    new_row, new_widths, inserted = [], [], False
                    for k, (it, w) in enumerate(zip(row, adj_widths, strict=False)):
                        if k in group_set:
                            if not inserted:
                                new_row.append(synthetic)
                                new_widths.append(combined_w)
                                inserted = True
                        else:
                            new_row.append(it)
                            new_widths.append(w)
                    row, adj_widths = new_row, new_widths

                # ── Final row-width guard ─────────────────────────────
                # After slicer rescue and button collapse, ensure the whole
                # row (boxes + inter-box gaps) does not exceed the canvas.
                total_boxes = sum(adj_widths)
                total_gaps = (len(row) - 1) * GAP
                if total_boxes + total_gaps > avail_w_emu:
                    safe_w = avail_w_emu - total_gaps
                    if safe_w < 0:
                        safe_w = 0
                    sf = safe_w / total_boxes if total_boxes > 0 else 1
                    adj_widths = [max(int(w * sf), E(0.10)) for w in adj_widths]
                    # re-normalize once more after integer rounding
                    total_boxes2 = sum(adj_widths)
                    if total_boxes2 > 0 and total_boxes2 + total_gaps > avail_w_emu:
                        sf2 = (avail_w_emu - total_gaps) / total_boxes2
                        adj_widths = [max(int(w * sf2), E(0.10)) for w in adj_widths]

                # ── Row height ────────────────────────────────────────
                LINE_H = 0.15
                PAD_H = 0.06
                n_lines = 2 if len(row) <= 2 else 1
                text_h = n_lines * LINE_H + PAD_H
                cmin = max(CAT_MIN_H.get(it["cat"], MIN_BOX_H_IN) for it in row)
                cmax = max(CAT_MAX_H.get(it["cat"], 2.0) for it in row)
                row_h_in = max(cmin, min(text_h, cmax))
                if is_split:
                    row_h_in = max(row_h_in * 0.5, 0.22)
                row_h = E(row_h_in)

                # ── Shape rendering ───────────────────────────────────
                rx = x_start
                for idx, it in enumerate(row):
                    bw = adj_widths[idx]
                    # Individual buttons (not collapsed) capped at 0.50"
                    if it["cat"] == "button" and not it.get("_btn_count"):
                        bw = min(bw, E(0.50))
                    bh = row_h

                    border, fill = _colors(it["cat"])
                    bw_in = bw / 914400
                    bh_in = bh / 914400

                    sz_offset = -2 if is_split else 0
                    full_name = it["name"]
                    abbrev = _TYPE_ABBREV.get(full_name, full_name[:6])

                    area_fields = it.get("_area_fields")
                    btn_count = it.get("_btn_count")

                    lines: list[typing.Any]
                    if area_fields is not None:
                        # Slicer Area: grouped slicers with field list
                        max_chars = max(int(bw_in / 0.055), 10)
                        type_sz = (14 if bw_in >= 1.0 else 13) + sz_offset
                        lines = [{"text": "Slicer Area", "sz": type_sz, "bold": True, "color": border}]
                        field_lines, cur = [], ""
                        for fld in area_fields:
                            candidate = (cur + ", " + fld) if cur else fld
                            if len(candidate) <= max_chars:
                                cur = candidate
                            else:
                                field_lines.append(cur)
                                cur = fld
                                if len(field_lines) == 2:
                                    break
                        if cur and len(field_lines) < 2:
                            field_lines.append(cur)
                        for fl in field_lines:
                            lines.append({"text": fl, "sz": 9, "color": "AAAAAA"})

                    elif btn_count:
                        # Button Area: grouped buttons
                        type_sz = (13 if bw_in >= 1.0 else 12) + sz_offset
                        lines = [{"text": full_name, "sz": type_sz, "bold": True, "color": border}]

                    elif bw_in >= 1.0:
                        type_sz = (16 if bw_in > 1.4 else 14) + sz_offset
                        lines = [{"text": full_name, "sz": type_sz, "bold": True, "color": border}]
                        vis_title = (it["vis"].get("title") or "").strip()
                        if vis_title:
                            lines.append({"text": vis_title, "sz": 12 if bw_in > 1.2 else 11, "color": C.DGRAY})
                        elif it["cat"] not in ("button",):
                            rep = _pick_rep_field(it["vis"].get("fields", []), it["vt"])
                            if rep:
                                lines.append({"text": rep, "sz": 10, "color": "AAAAAA"})

                    elif bw_in >= 0.55:
                        lines = [{"text": full_name, "sz": 13 + sz_offset, "bold": True, "color": border}]
                        vis_title = (it["vis"].get("title") or "").strip()
                        if vis_title:
                            lines.append({"text": vis_title, "sz": 10, "color": C.DGRAY})
                        elif it["cat"] not in ("button",):
                            rep = _pick_rep_field(it["vis"].get("fields", []), it["vt"])
                            if rep:
                                lines.append({"text": rep, "sz": 9, "color": "AAAAAA"})

                    elif bw_in >= 0.30:
                        lines = [{"text": abbrev, "sz": 12 + sz_offset, "bold": True, "color": border}]
                        if it["cat"] not in ("button",):
                            rep = _pick_rep_field(it["vis"].get("fields", []), it["vt"])
                            if rep:
                                lines.append({"text": rep, "sz": 8, "color": "AAAAAA"})

                    else:
                        lines = [{"text": abbrev, "sz": 10, "bold": True, "color": border}]

                    area = bw_in * bh_in
                    bw_s = "12700" if area > 3.0 else "9525" if area > 1.0 else "6350" if area > 0.3 else "4762"

                    row_shapes.append(
                        _dml_shape(
                            _snap(rx),
                            _snap(y),
                            _snap(bw),
                            _snap(bh),
                            fill,
                            lines,
                            border_color=border,
                            border_w=bw_s,
                            lIns="27000",
                            rIns="27000",
                            tIns="18000",
                            bIns="18000",
                            autofit=False,
                            anchor="ctr",
                        )
                    )

                    rx += bw + GAP

                y += row_h + (int(GAP * 0.4) if is_split else GAP)

        return row_shapes, y

    # ── 5. Zone header helper ─────────────────────────────────────────────
    def _zone_hdr(
        x: typing.Any, y: typing.Any, w: typing.Any, label: typing.Any, count: typing.Any, color: typing.Any
    ) -> typing.Any:
        return _dml_shape(
            _snap(x),
            _snap(y),
            _snap(w),
            _snap(ZONE_HDR_H),
            None,
            [{"text": f"{label}  ({count})", "sz": 13, "bold": True, "color": color, "opacity": 0.65}],
            border_color=color,
            border_w="4762",
            geom="rect",
            adj=None,
            lIns="45000",
            rIns="36000",
            tIns="9000",
            bIns="9000",
            anchor="ctr",
        )

    # ── 6. Render ─────────────────────────────────────────────────────────
    shapes: list[typing.Any] = []
    y_cursor = PAD

    def _render_full_zone(zitems: typing.Any, label: typing.Any, color: typing.Any) -> typing.Any:
        nonlocal y_cursor
        shapes.append(_zone_hdr(PAD, y_cursor, INNER_W, label, len(zitems), color))
        y_cursor += ZONE_HDR_H + GAP
        rs, y_cursor = _render_rows(_build_rows(zitems), PAD, INNER_W, y_cursor)
        shapes.extend(rs)
        y_cursor += ZONE_GAP - GAP

    if not left_sidebar_mode:
        # All zones stacked top-to-bottom
        if header:
            _render_full_zone(header, "Header", C.DGRAY)
        if content:
            _render_full_zone(content, "Content", C.PACIFIC)
        if footer:
            _render_full_zone(footer, "Footer", C.DGRAY)
    else:
        # Header and Footer span full width; Filters + Content side by side
        if header:
            _render_full_zone(header, "Header", C.DGRAY)

        # Two-column zone headers at the same y
        col_y = y_cursor
        shapes.append(_zone_hdr(PAD, col_y, SIDEBAR_W, "Filters", len(left_sl), C.RUBINE))
        shapes.append(_zone_hdr(CONTENT_X, col_y, CONTENT_W, "Content", len(content), C.PACIFIC))
        col_y += ZONE_HDR_H + GAP

        # Render both columns independently
        filt_shapes, filt_end = _render_rows(_build_rows(left_sl), PAD, SIDEBAR_W, col_y)
        cont_shapes, cont_end = _render_rows(_build_rows(content), CONTENT_X, CONTENT_W, col_y)
        shapes.extend(filt_shapes)
        shapes.extend(cont_shapes)
        y_cursor = max(filt_end, cont_end) + ZONE_GAP

        if footer:
            _render_full_zone(footer, "Footer", C.DGRAY)

    # ── 7. Page info bar ──────────────────────────────────────────────────
    pg_tp = page.get("type", "Standard")
    n_deco = len(page.get("visuals", [])) - len(items)
    parts: list[typing.Any] = [f"{pw_pg}x{ph_pg}px"]
    if pg_tp and pg_tp.lower() != "standard":
        parts.append(pg_tp)
    if n_deco > 0:
        parts.append(f"{n_deco} decorative omitted")

    INFO_H = E(0.14)
    shapes.append(
        _dml_shape(
            _snap(PAD),
            _snap(y_cursor),
            _snap(INNER_W),
            _snap(INFO_H),
            None,
            [{"text": "  \u2022  ".join(parts), "sz": 11, "italic": True, "color": "AAAAAA"}],
            geom="rect",
            adj=None,
            lIns="45000",
            rIns="36000",
            tIns="0",
            bIns="0",
            anchor="ctr",
        )
    )

    total_h = y_cursor + INFO_H + PAD

    # ── 8. Canvas border + insert ─────────────────────────────────────────
    shapes.insert(
        0,
        _dml_shape(
            0,
            0,
            _snap(CANVAS_W),
            _snap(total_h),
            None,
            [],
            border_color="BBBBBB",
            border_w="6350",
            geom="rect",
            adj=None,
        ),
    )

    if dry_run:
        return int(_snap(total_h))

    _DIAGRAM_ID_COUNTER[0] += 1
    _insert_diagram(
        doc,
        shapes,
        _snap(CANVAS_W),
        _snap(total_h),
        f"Figure {fig_num} \u2014 {page.get('display_name', '')} page layout",
    )
    return int(_snap(total_h))
