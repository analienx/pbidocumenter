"""Technical observation engine — generates obs_card items."""

import re
import typing
from collections import Counter as _Ctr

from pbip_documenter.config import C


def generate_observations(sm: typing.Any, rpt: typing.Any) -> typing.Any:
    obs: list[typing.Any] = []
    seen = set()
    tables = sm.get("tables", [])
    rels = sm.get("relationships", [])
    exprs = sm.get("expressions", [])
    pages = rpt.get("pages", [])
    all_m = [{**m, "table": t.get("name") or "?"} for t in tables for m in t.get("measures", [])]

    fact_names = {
        t.get("name")
        for t in tables
        if any((t.get("name", "") or "").lower().startswith(p) for p in ("fact_", "fct_", "fact", "fct"))
    }
    dim_names = {
        t.get("name")
        for t in tables
        if any(
            (t.get("name", "") or "").lower().startswith(p) for p in ("dim_", "dimension_", "dim", "date", "calendar")
        )
    }

    def _o(title: typing.Any, detail: typing.Any, color: typing.Any, cat: typing.Any) -> typing.Any:
        key = (title, detail)
        if key not in seen:
            seen.add(key)
            obs.append((title, detail, color, cat))

    # ------------------------------------------------------------------
    # Relationship checks
    # ------------------------------------------------------------------
    for r in rels:
        if r.get("cross_filtering") == "bothDirections":
            _o(
                "Bi-directional cross-filtering",
                f"{r.get('from_table', '?')} → {r.get('to_table', '?')}.",
                C.RUBINE,
                "Risks",
            )
        if r.get("is_active") is False:
            _o(
                "Inactive relationship",
                f"{r.get('from_table', '?')}.{r.get('from_field', '?')} → {r.get('to_table', '?')}.{r.get('to_field', '?')} — likely role-playing.",
                C.SKY,
                "Info",
            )
        if r.get("from_table") in fact_names and r.get("to_table") in fact_names:
            _o(
                "Fact-to-fact relationship",
                f"{r.get('from_table', '?')} → {r.get('to_table', '?')}. Filter propagation needs testing.",
                C.MARIGOLD,
                "Warnings",
            )
        if (
            (r.get("cardinality") or "").lower().startswith("many")
            and r.get("from_table") in dim_names
            and r.get("to_table") in dim_names
        ):
            _o(
                "Many-to-many dimension relationship",
                f"{r.get('from_table', '?')} ↔ {r.get('to_table', '?')} appears many-to-many. Consider a bridge/factless fact table.",
                C.MARIGOLD,
                "Warnings",
            )
        if (r.get("security_filtering") or "").lower() not in ("", "oneDirection", "bothDirections"):
            _o(
                "Non-default relationship security filtering",
                f"{r.get('from_table', '?')} → {r.get('to_table', '?')} uses {r.get('security_filtering')}. Confirm this is intentional.",
                C.SKY,
                "Info",
            )

    inactive_count = sum(1 for r in rels if r.get("is_active") is False)
    if inactive_count >= 3:
        _o(
            "Multiple inactive relationships",
            f"{inactive_count} inactive relationships detected. Consider whether role-playing dimensions or alternate models would simplify authoring.",
            C.MARIGOLD,
            "Warnings",
        )

    # ------------------------------------------------------------------
    # Column checks
    # ------------------------------------------------------------------
    likely_date_dim = False
    visible_key_cols: list[typing.Any] = []
    month_without_sort: list[typing.Any] = []
    uncategorized_semantic_cols: list[typing.Any] = []
    for t in tables:
        tname = t.get("name") or "?"
        if t.get("data_category") == "Time" or any(x in tname.lower() for x in ("date", "calendar")):
            likely_date_dim = True
        for c in t.get("columns", []):
            cname = c.get("name", "")
            cl = cname.lower()
            if "sumbission" in cl or "submisson" in cl:
                _o("Column naming typo", f"'{cname}' in {tname} — likely 'Submission'.", C.RUBINE, "Risks")
            if (
                not c.get("is_hidden")
                and re.search(r"(^|[_\s])(id|key)$|(_id$|_key$|key$)", cl)
                and not c.get("sort_by_column")
            ):
                visible_key_cols.append(f"{tname}.{cname}")
            if (
                any(m in cl for m in ("month", "month name", "monthname", "quarter", "qtr"))
                and not c.get("sort_by_column")
                and not c.get("is_hidden")
            ):
                month_without_sort.append(f"{tname}.{cname}")
            if not c.get("data_category") and any(
                tok in cl
                for tok in (
                    "country",
                    "city",
                    "state",
                    "province",
                    "postal",
                    "zip",
                    "url",
                    "website",
                    "email",
                    "image",
                    "photo",
                    "latitude",
                    "longitude",
                )
            ):
                uncategorized_semantic_cols.append(f"{tname}.{cname}")

    if visible_key_cols:
        _o(
            "Visible technical key columns",
            f"{len(visible_key_cols)} technical key column(s) visible to report authors: {', '.join(visible_key_cols[:5])}{'...' if len(visible_key_cols) > 5 else ''}.",
            C.MARIGOLD,
            "Warnings",
        )
    if month_without_sort:
        _o(
            "Date labels without Sort By",
            f"{len(month_without_sort)} month/quarter label column(s) may sort alphabetically: {', '.join(month_without_sort[:5])}{'...' if len(month_without_sort) > 5 else ''}.",
            C.MARIGOLD,
            "Warnings",
        )
    if uncategorized_semantic_cols:
        _o(
            "Likely semantic columns missing data categories",
            f"Columns that look like geography/URL/email/image fields have no data category: {', '.join(uncategorized_semantic_cols[:5])}{'...' if len(uncategorized_semantic_cols) > 5 else ''}.",
            C.SKY,
            "Info",
        )
    if not likely_date_dim and (all_m or rels):
        _o(
            "No clear date dimension detected",
            "No table clearly identified as a date/calendar dimension. Review time-intelligence readiness.",
            C.MARIGOLD,
            "Warnings",
        )

    # ------------------------------------------------------------------
    # Measure / DAX checks
    # ------------------------------------------------------------------
    str_m = [
        m
        for m in all_m
        if not m.get("format_string")
        and any(k in (m.get("expression", "") or "") for k in ['& " days', '& "D ', "Not Approved", "Not Posted"])
    ]
    if str_m:
        _o(
            "String-returning measures",
            f"{', '.join(m['name'] for m in str_m[:3])} return text.",
            C.MARIGOLD,
            "Warnings",
        )

    unfmt = [
        m
        for m in all_m
        if not m.get("format_string")
        and m.get("expression", "")
        and not any(
            k in m.get("expression", "")
            for k in ['& " days', '& "D ', "Not Approved", "Not Posted", "BLANK()", '""', "IF("]
        )
    ]
    if len(unfmt) > 3:
        _o(
            "Measures without format strings",
            f"{len(unfmt)} measures lack format strings (e.g. {', '.join(m['name'] for m in unfmt[:3])}).",
            C.MARIGOLD,
            "Warnings",
        )

    no_folder = [m for m in all_m if not m.get("display_folder")]
    if len(all_m) >= 12 and len(no_folder) / max(len(all_m), 1) > 0.8:
        _o(
            "Large measure set without display folders",
            f"{len(no_folder)} of {len(all_m)} measures are not organized into display folders.",
            C.SKY,
            "Info",
        )

    divide_ops: list[typing.Any] = []
    filter_antipatterns: list[typing.Any] = []
    count_antipatterns: list[typing.Any] = []
    selectedvalue_legacy: list[typing.Any] = []
    blank_to_zero: list[typing.Any] = []
    no_var_complex: list[typing.Any] = []
    for m in all_m:
        expr = m.get("expression", "") or ""
        upper = expr.upper()
        name = f"{m.get('table', '?')}[{m.get('name', '?')}]"
        if "/" in expr and "DIVIDE(" not in upper and not re.search(r"/\s*\d+(\.\d+)?", expr):
            divide_ops.append(name)
        if re.search(r"CALCULATE\s*\([^\)]*FILTER\s*\(", upper):
            filter_antipatterns.append(name)
        if re.search(r"COUNT\s*\(", upper) and "COUNTROWS(" not in upper:
            count_antipatterns.append(name)
        if "HASONEVALUE(" in upper and "VALUES(" in upper:
            selectedvalue_legacy.append(name)
        if re.search(r"DIVIDE\s*\([^\)]*,[^\)]*,\s*0\s*\)", upper) or re.search(
            r"IF\s*\(\s*ISBLANK\s*\([^\)]*\)\s*,\s*0\s*,", upper
        ):
            blank_to_zero.append(name)
        if (
            len(expr) > 180
            and "VAR " not in upper
            and upper.count("CALCULATE(") + upper.count("IF(") + upper.count("SWITCH(") >= 2
        ):
            no_var_complex.append(name)

    if divide_ops:
        _o(
            "Potential unsafe division pattern",
            f"Use DIVIDE() instead of '/' where the denominator can be zero or BLANK (e.g. {', '.join(divide_ops[:4])}).",
            C.MARIGOLD,
            "Warnings",
        )
    if filter_antipatterns:
        _o(
            "FILTER used as simple filter argument",
            f"Consider Boolean filter arguments in CALCULATE where possible (e.g. {', '.join(filter_antipatterns[:4])}).",
            C.MARIGOLD,
            "Warnings",
        )
    if count_antipatterns:
        _o(
            "COUNT used where COUNTROWS may be intended",
            f"Review row-counting measures such as {', '.join(count_antipatterns[:4])}.",
            C.SKY,
            "Info",
        )
    if selectedvalue_legacy:
        _o(
            "Legacy VALUES/HASONEVALUE pattern",
            f"Consider SELECTEDVALUE() for measures such as {', '.join(selectedvalue_legacy[:4])}.",
            C.SKY,
            "Info",
        )
    if blank_to_zero:
        _o(
            "Dense measure pattern (BLANK → 0)",
            f"Measures such as {', '.join(blank_to_zero[:4])} convert BLANKs to zero, which can increase visual density and reduce performance.",
            C.MARIGOLD,
            "Warnings",
        )
    if len(no_var_complex) >= 2:
        _o(
            "Complex DAX without variables",
            f"Long measures without VAR/RETURN detected (e.g. {', '.join(no_var_complex[:4])}).",
            C.SKY,
            "Info",
        )

    # ------------------------------------------------------------------
    # Query / source checks
    # ------------------------------------------------------------------
    ht = [t.get("name") or "?" for t in tables if t.get("is_hidden")]
    if ht:
        _o(
            "Hidden tables (correct pattern)",
            f"{', '.join(ht)} hidden from report view.",
            C.EVERGREEN,
            "Good Practices",
        )
    stg = [e.get("name", "?") for e in exprs if e.get("result_type") == "Table"]
    if stg:
        _o("Disabled-load staging queries", f"Not loaded: {', '.join(stg)}.", C.SKY, "Info")
    hlp = [e.get("name", "?") for e in exprs if e.get("result_type") in ("Function", "Binary")]
    if hlp:
        _o("Helper/function queries", f"{', '.join(hlp)}. Verify still in use.", C.SKY, "Info")

    all_code = " ".join((e.get("expression", "") or "") for e in exprs)
    all_code += " ".join((p.get("m_expression", "") or "") for t in tables for p in t.get("partitions", []))
    if 'Implementation="2.0"' in all_code and "ApiVersion = 15" in all_code:
        _o("Mixed SharePoint API versions", "Both Implementation 2.0 and ApiVersion 15 used.", C.MARIGOLD, "Warnings")
    if "Snowflake.Databases" in all_code and "Role=" not in all_code and "role=" not in all_code:
        _o(
            "Snowflake connection without explicit Role",
            "Snowflake.Databases() calls lack explicit Role parameter.",
            C.MARIGOLD,
            "Warnings",
        )
    if "PowerPlatform.Dataflows" in all_code:
        _o(
            "Power Platform Dataflows dependency",
            "Dataflow refresh must complete before this model refreshes.",
            C.SKY,
            "Info",
        )

    for t in tables:
        if t.get("data_category") == "Time":
            dr = [r for r in rels if r.get("to_table") == t.get("name")]
            if dr:
                jc = dr[0].get("from_field", "")
                for p in t.get("partitions", []):
                    if "Submission" in (p.get("m_expression", "") or "") and jc and "Posting" in jc:
                        _o(
                            "Date range vs relationship mismatch",
                            f"Calendar from Submission Date but relationship uses {jc}.",
                            C.RUBINE,
                            "Risks",
                        )

    # ------------------------------------------------------------------
    # RLS checks
    # ------------------------------------------------------------------
    roles = sm.get("roles", []) or []
    if roles:
        fact_rls: list[typing.Any] = []
        true_false_roles: list[typing.Any] = []
        dynamic_roles = 0
        for role in roles:
            perms = role.get("table_permissions", []) or []
            for tp in perms:
                tbl = tp.get("table")
                expr = (tp.get("expression", "") or "").upper()
                if tbl in fact_names:
                    fact_rls.append(f"{role.get('name', '?')}:{tbl}")
                if "USERPRINCIPALNAME(" in expr or "USERNAME(" in expr:
                    dynamic_roles += 1
                if expr in ("TRUE()", "FALSE()"):
                    true_false_roles.append(f"{role.get('name', '?')}={expr}")
        if fact_rls:
            _o(
                "RLS applied to fact-like tables",
                f"RLS is often more efficient on dimensions than facts (e.g. {', '.join(fact_rls[:4])}).",
                C.MARIGOLD,
                "Warnings",
            )
        if len(roles) >= 6 and dynamic_roles == 0:
            _o(
                "Potential static RLS role explosion",
                f"{len(roles)} roles detected with no obvious dynamic identity function usage. Consider a data-driven dynamic RLS design.",
                C.MARIGOLD,
                "Warnings",
            )
        if true_false_roles:
            _o(
                "Trivial RLS role logic detected",
                f"Roles with always-true/false filters found: {', '.join(true_false_roles[:4])}.",
                C.SKY,
                "Info",
            )

    # ------------------------------------------------------------------
    # Metadata-driven model curation / usage checks
    # ------------------------------------------------------------------
    measure_index: dict[typing.Any, typing.Any] = {}
    visible_column_index: dict[typing.Any, typing.Any] = {}
    all_column_index: dict[typing.Any, typing.Any] = {}
    for t in tables:
        tname = t.get("name") or "?"
        for m in t.get("measures", []):
            measure_index[(tname, m.get("name") or "?")] = m
        for c in t.get("columns", []):
            key = (tname, c.get("name") or "?")
            all_column_index[key] = c
            if not c.get("is_hidden"):
                visible_column_index[key] = c

    used_measure_refs = set()
    used_column_refs = set()
    page_binding_mix: dict[typing.Any, typing.Any] = {}
    visual_type_counter: _Ctr[str] = _Ctr()
    custom_visuals: list[typing.Any] = []
    generic_page_names: list[typing.Any] = []
    core_visual_types: set[typing.Any] = {
        "barChart",
        "clusteredBarChart",
        "stackedBarChart",
        "100StackedBarChart",
        "columnChart",
        "clusteredColumnChart",
        "stackedColumnChart",
        "100StackedColumnChart",
        "lineChart",
        "areaChart",
        "comboChart",
        "lineClusteredColumnComboChart",
        "lineStackedColumnComboChart",
        "pieChart",
        "donutChart",
        "scatterChart",
        "bubbleChart",
        "waterfallChart",
        "funnel",
        "treemap",
        "tableEx",
        "matrix",
        "pivotTable",
        "card",
        "multiRowCard",
        "kpi",
        "gauge",
        "map",
        "filledMap",
        "shapeMap",
        "azureMap",
        "arcGisMap",
        "decompositionTreeVisual",
        "slicer",
        "advancedSlicerVisual",
        "qnaVisual",
        "smartNarrativeVisual",
        "scorecardVisual",
        "textbox",
        "image",
        "shape",
        "basicShape",
        "actionButton",
        "blank",
    }

    for pg in pages:
        pg_name = pg.get("display_name", "?")
        if re.match(r"^(page|report section)\s*\d+$", (pg_name or "").strip(), re.IGNORECASE):
            generic_page_names.append(pg_name)
        measure_refs_on_page = set()
        column_refs_on_page = set()
        custom_on_page = set()
        for v in pg.get("visuals", []):
            vtype = (v.get("visual_type", "") or "").strip()
            if vtype:
                visual_type_counter[vtype] += 1
                if vtype not in core_visual_types:
                    custom_visuals.append((pg_name, vtype))
                    custom_on_page.add(vtype)
            for f in v.get("fields", []):
                entity = (f.get("entity", "") or "").strip("' ")
                prop = (f.get("property", "") or "").strip("' ")
                if not entity or not prop or entity == "." or prop == ".":
                    continue
                ref = (entity, prop)
                if ref in measure_index:
                    used_measure_refs.add(ref)
                    measure_refs_on_page.add(ref)
                elif ref in all_column_index:
                    used_column_refs.add(ref)
                    column_refs_on_page.add(ref)
        page_binding_mix[pg_name] = {
            "measure_refs": len(measure_refs_on_page),
            "column_refs": len(column_refs_on_page),
            "custom_visuals": len(custom_on_page),
        }

    unused_measures = [f"{tbl}[{name}]" for (tbl, name) in measure_index if (tbl, name) not in used_measure_refs]
    if len(measure_index) >= 8 and len(unused_measures) >= max(4, int(len(measure_index) * 0.3)):
        _o(
            "Unused measures exposed in the model",
            f"{len(unused_measures)} measure(s) are not referenced by any report visual metadata (e.g. {', '.join(unused_measures[:5])}{'...' if len(unused_measures) > 5 else ''}). Review whether they should be hidden, grouped, or removed.",
            C.MARIGOLD,
            "Warnings",
        )

    unused_visible_columns: list[typing.Any] = []
    for (tbl, col), meta in visible_column_index.items():
        cl = (col or "").lower()
        if (tbl, col) in used_column_refs:
            continue
        if re.search(r"(^|[_\s])(id|key)$|(_id$|_key$|key$)", cl):
            continue
        if meta.get("sort_by_column"):
            continue
        unused_visible_columns.append(f"{tbl}.{col}")
    if len(unused_visible_columns) >= 10:
        _o(
            "Visible columns not used in the report",
            f"{len(unused_visible_columns)} visible column(s) are not referenced by visual metadata (e.g. {', '.join(unused_visible_columns[:6])}{'...' if len(unused_visible_columns) > 6 else ''}). Consider hiding technical or author-noise columns.",
            C.SKY,
            "Info",
        )

    unused_tables: list[typing.Any] = []
    for t in tables:
        tname = t.get("name") or "?"
        if t.get("is_hidden"):
            continue
        if any((tname, m.get("name", "?")) in used_measure_refs for m in t.get("measures", [])):
            continue
        if any((tname, c.get("name", "?")) in used_column_refs for c in t.get("columns", [])):
            continue
        if any((tname or "").lower().startswith(p) for p in ("prm_", "param_", "disc_", "sec_", "_")):
            continue
        unused_tables.append(tname)
    if unused_tables:
        _o(
            "Exposed tables not used in report metadata",
            f"{len(unused_tables)} non-hidden table(s) are not referenced by report visuals: {', '.join(unused_tables[:5])}{'...' if len(unused_tables) > 5 else ''}. Confirm whether these belong in the authoring surface.",
            C.SKY,
            "Info",
        )

    raw_column_pages = [
        name for name, stats in page_binding_mix.items() if stats["column_refs"] >= 6 and stats["measure_refs"] == 0
    ]
    if raw_column_pages:
        _o(
            "Pages rely on raw columns without measures",
            f"Page(s) appear to bind directly to columns without any detected measures: {', '.join(raw_column_pages[:4])}{'...' if len(raw_column_pages) > 4 else ''}. Review whether curated measures would improve consistency.",
            C.MARIGOLD,
            "Warnings",
        )

    # ------------------------------------------------------------------
    # Naming / organization consistency checks
    # ------------------------------------------------------------------
    prefixed_tables = [
        t.get("name") or "?"
        for t in tables
        if any((t.get("name", "") or "").lower().startswith(p) for p in ("fact_", "fct_", "dim_", "dimension_"))
    ]
    unprefixed_tables = [
        t.get("name") or "?"
        for t in tables
        if t.get("name") and t.get("name") not in prefixed_tables and not (t.get("name", "") or "").startswith("_")
    ]
    if prefixed_tables and unprefixed_tables and len(tables) >= 4:
        _o(
            "Mixed table naming conventions",
            f"The model mixes prefixed and unprefixed table naming (e.g. prefixed: {', '.join(prefixed_tables[:3])}; unprefixed: {', '.join(unprefixed_tables[:3])}). Consider standardizing fact/dimension naming.",
            C.SKY,
            "Info",
        )

    if generic_page_names:
        _o(
            "Generic page names",
            f"Page names such as {', '.join(generic_page_names[:4])}{'...' if len(generic_page_names) > 4 else ''} are generic. Rename pages to reflect business intent and navigation purpose.",
            C.SKY,
            "Info",
        )

    folders = [m.get("display_folder") for m in all_m if m.get("display_folder")]
    if len(all_m) >= 12 and folders:
        folder_counts = _Ctr(folders)
        partial_organization = len(folders) < len(all_m)
        one_off_folders = [f for f, cnt in folder_counts.items() if cnt == 1]
        if partial_organization:
            _o(
                "Partially organized measure folders",
                f"Only {len(folders)} of {len(all_m)} measures use display folders. Consider organizing the remaining measures for a cleaner authoring experience.",
                C.SKY,
                "Info",
            )
        if len(one_off_folders) >= 4:
            _o(
                "Fragmented display-folder structure",
                f"{len(one_off_folders)} display folder(s) contain only one measure (e.g. {', '.join(str(folder) for folder in one_off_folders[:4])}). Review whether folder structure is too granular.",
                C.SKY,
                "Info",
            )

    technical_role_names = [
        r.get("name", "")
        for r in roles
        if r.get("name") and ("_" in r.get("name", "") or re.search(r"\d", r.get("name", "")))
    ]
    if technical_role_names:
        _o(
            "Role names look technical rather than functional",
            f"Role names such as {', '.join(technical_role_names[:4])}{'...' if len(technical_role_names) > 4 else ''} look file- or code-oriented. Consider functional names that are easier to govern.",
            C.SKY,
            "Info",
        )

    # ------------------------------------------------------------------
    # Front-end dependency / visual-governance checks
    # ------------------------------------------------------------------
    total_visuals = sum(visual_type_counter.values())
    if custom_visuals:
        distinct_custom = sorted({vtype for _, vtype in custom_visuals})
        if len(custom_visuals) >= 3 or (total_visuals and len(custom_visuals) / total_visuals > 0.2):
            _o(
                "Custom visual dependency",
                f"{len(custom_visuals)} visual(s) use non-core visual types across {len(distinct_custom)} distinct type(s) (e.g. {', '.join(distinct_custom[:4])}{'...' if len(distinct_custom) > 4 else ''}). Confirm support, governance, and export/accessibility implications.",
                C.MARIGOLD,
                "Warnings",
            )

    custom_heavy_pages = [name for name, stats in page_binding_mix.items() if stats["custom_visuals"] >= 2]
    if custom_heavy_pages:
        _o(
            "Pages dominated by custom visuals",
            f"Page(s) with multiple custom visuals detected: {', '.join(custom_heavy_pages[:4])}{'...' if len(custom_heavy_pages) > 4 else ''}. Review maintainability and supportability.",
            C.SKY,
            "Info",
        )

    non_decorative_visual_types = {
        vt
        for vt in visual_type_counter
        if vt not in ("shape", "basicShape", "image", "textbox", "actionButton", "blank", "")
    }
    if len(non_decorative_visual_types) >= 10:
        _o(
            "High visual-type diversity",
            f"The report uses {len(non_decorative_visual_types)} distinct non-decorative visual types. High visual variety can reduce consistency and increase support complexity.",
            C.SKY,
            "Info",
        )

    # ------------------------------------------------------------------
    # Interactive features: visual links, bookmarks, custom visuals
    # ------------------------------------------------------------------
    action_types: _Ctr[str] = _Ctr()
    for pg in pages:
        for v in pg.get("visuals", []):
            act = v.get("action")
            if act:
                action_types[act.get("type", "?")] += 1

    if action_types.get("PageNavigation", 0) > 0:
        _o(
            "Page navigation buttons present",
            f"{action_types['PageNavigation']} visual(s) trigger page navigation. Document the target pages and user flow.",
            C.SKY,
            "Info",
        )
    if action_types.get("Bookmark", 0) > 0:
        _o(
            "Bookmark navigation present",
            f"{action_types['Bookmark']} visual(s) trigger bookmarks. Ensure bookmark states are documented and tested.",
            C.SKY,
            "Info",
        )
    if action_types.get("DataFunction", 0) > 0:
        _o(
            "Data functions present",
            f"{action_types['DataFunction']} visual(s) invoke data functions (write-back / alerting). See Section 3.4.3 for full details.",
            C.SKY,
            "Info",
        )
    if action_types.get("ClearAllSlicers", 0) > 0:
        _o(
            "Clear-all-slicers buttons present",
            f"{action_types['ClearAllSlicers']} visual(s) reset all slicers. Good UX practice for filter reset.",
            C.EVERGREEN,
            "Good Practices",
        )

    bookmarks = rpt.get("bookmarks", [])
    if bookmarks:
        group_count = sum(1 for bm in bookmarks if bm.get("is_group"))
        _o(
            "Bookmark navigation configured",
            f"{len(bookmarks)} bookmark(s) configured ({group_count} group(s)). Bookmarks control visual state and filter context.",
            C.SKY,
            "Info",
        )

    public_custom_visuals = rpt.get("public_custom_visuals", [])
    if public_custom_visuals:
        _o(
            "Report uses custom visuals",
            f"{len(public_custom_visuals)} third-party custom visual(s): {', '.join(public_custom_visuals)}. Verify licensing, support, and accessibility compliance.",
            C.SKY,
            "Info",
        )

    # ------------------------------------------------------------------
    # Report / page checks
    # ------------------------------------------------------------------
    for pg in pages:
        nf = sum(1 for v in pg.get("visual_interactions", []) if v.get("type") == "NoFilter")
        if nf > 10:
            _o(
                f"Heavy NoFilter on '{pg.get('display_name', '?')}'",
                f"{nf} NoFilter rules.",
                C.EVERGREEN,
                "Good Practices",
            )

    conn = set()
    for r in rels:
        conn.add(r.get("from_table", ""))
        conn.add(r.get("to_table", ""))
    disc = [(t.get("name") or "?") for t in tables if t.get("name") not in conn]
    if disc:
        _o("Disconnected tables", f"{', '.join(disc)} — measure containers or parameters.", C.SKY, "Info")

    for t in tables:
        for c in t.get("columns", []):
            if c.get("sort_by_column"):
                _o(
                    "Sort column configuration",
                    f"{t.get('name') or '?'}.{c['name']} sorted by {c['sort_by_column']}.",
                    C.SKY,
                    "Info",
                )
                break

    params = [e.get("name", "?") for e in exprs if "IsParameterQuery=true" in (e.get("expression", "") or "")]
    if params:
        _o("Parameter-driven connections", f"Binary parameters: {', '.join(params)}.", C.SKY, "Info")

    conn_tbls = set()
    for r in rels:
        conn_tbls.add(r.get("from_table", ""))
        conn_tbls.add(r.get("to_table", ""))
    orphan = [
        t.get("name") or "?"
        for t in tables
        if t.get("name", "") not in conn_tbls
        and not t.get("measures")
        and not any((t.get("name", "") or "").lower().startswith(p) for p in ("prm_", "param_", "disc_", "sec_", "_"))
    ]
    if orphan:
        _o(
            "Potentially orphan tables",
            f"{len(orphan)} table(s) with no relationships or measures: {', '.join(orphan[:5])}{'...' if len(orphan) > 5 else ''}.",
            C.MARIGOLD,
            "Warnings",
        )

    for name, ncols in [
        (t.get("name") or "?", len(t.get("columns", [])))
        for t in tables
        if len(t.get("columns", [])) > 30
        and any((t.get("name", "") or "").lower().startswith(p) for p in ("fact_", "fct_"))
    ]:
        _o("Wide fact table", f"{name} has {ncols} columns.", C.MARIGOLD, "Warnings")

    for col_ref, cnt in _Ctr(
        f"{r.get('from_table', '')}.{r.get('from_field', '')}" for r in rels if r.get("is_active", True)
    ).items():
        if cnt > 1:
            _o(
                "Column in multiple active relationships",
                f"{col_ref} is from-side of {cnt} active relationships.",
                C.RUBINE,
                "Risks",
            )

    multi = [(t.get("name") or "?", len(t.get("partitions", []))) for t in tables if len(t.get("partitions", [])) > 1]
    if multi:
        _o(
            "Multiple partitions detected",
            f"{len(multi)} table(s) with >1 partition: {', '.join(f'{n}({c})' for n, c in multi[:4])}.",
            C.SKY,
            "Info",
        )

    nav = [
        pg.get("display_name", "?")
        for pg in pages
        if pg.get("visual_count", 0) > 0
        and sum(
            1
            for v in pg.get("visuals", [])
            if v.get("visual_type", "") not in ("shape", "basicShape", "image", "textbox", "actionButton", "")
        )
        == 0
    ]
    if nav:
        _o(
            "Non-data pages",
            f"{len(nav)} page(s) contain only decorative visuals: {', '.join(nav[:4])}.",
            C.SKY,
            "Info",
        )

    unguarded = [
        m["name"]
        for m in all_m
        if "SELECTEDVALUE" in (m.get("expression", "") or "").upper()
        and not any(k in (m.get("expression", "") or "").upper() for k in ("IFERROR", "IF(", "ISBLANK"))
    ]
    if len(unguarded) > 2:
        _o(
            "SELECTEDVALUE without guard",
            f"{len(unguarded)} measures use SELECTEDVALUE without guard.",
            C.MARIGOLD,
            "Warnings",
        )

    if (rpt.get("dataset_mode", "") or "").lower() == "directquery":
        visual_count = sum(len(p.get("visuals", [])) for p in pages)
        slicer_count = sum(
            1
            for p in pages
            for v in p.get("visuals", [])
            if v.get("visual_type", "") in ("slicer", "advancedSlicerVisual")
        )
        if visual_count >= 35 or slicer_count >= 8:
            _o(
                "Dense report on DirectQuery",
                f"DirectQuery report has {visual_count} visuals and {slicer_count} slicer(s). Review page density and performance.",
                C.MARIGOLD,
                "Warnings",
            )

    parser_warnings = sm.get("parser_warnings") or []
    if parser_warnings:
        _o(
            "Metadata parsing warnings",
            f"{len(parser_warnings)} parser warning(s) detected. Review full-mode parsing notes section.",
            C.SKY,
            "Info",
        )

    return obs
