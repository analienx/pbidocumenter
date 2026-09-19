"""PBIR metadata/geometry checks complemented by independent rendered-image review."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pbip_documenter.quality_gate import inspect_report

from .evidence import png_size


def inspect_report_surface(report: Path, renders: Path | None = None) -> dict:
    result = inspect_report(report, renders)
    findings = list(result["findings"])
    advisories: list[dict] = []
    pages: list[dict] = []
    for page in result["pages"]:
        record = {"id": page["id"]}
        if page["screenshot"]:
            shot = page["screenshot"]
            try:
                if png_size(renders / shot["name"]) != (shot["width"], shot["height"]):
                    raise ValueError("PNG dimensions do not agree with PBIR capture metadata")
            except ValueError as exc:
                findings.append({"rule": "invalid_png_image", "page": page["id"], "detail": str(exc)})
            record.update(image=shot["name"], sha256=shot["sha256"],
                          pixels=[shot["width"], shot["height"]])
        pages.append(record)
        visual_root = report / "definition" / "pages" / page["id"] / "visuals"
        palette: set[str] = set()
        inventory: list[dict] = []
        for folder in visual_root.iterdir():
            visual = json.loads((folder / "visual.json").read_text(encoding="utf-8-sig"))
            vtype, pos = visual.get("visual", {}).get("visualType", ""), visual["position"]
            inventory.append({"id": visual["name"], "type": vtype, "position": pos,
                              "roles": sorted(visual.get("visual", {}).get("query", {}).get("queryState", {}))})
            payload = json.dumps(visual.get("visual", {}), ensure_ascii=False)
            palette.update(x.upper() for x in re.findall(r"#[0-9A-Fa-f]{6}\b", payload))
            if vtype in {"scatterChart", "lineChart"} and pos["width"] < 430:
                advisories.append({"page": page["id"], "visual": visual["name"],
                                   "rule": "axis_label_density_risk", "details": "Inspect rendered ticks and axis titles."})
            if vtype == "tableEx" and pos["height"] > 230:
                advisories.append({"page": page["id"], "visual": visual["name"],
                                   "rule": "table_area_review", "details": "Verify visible rows use allocated area."})
            if vtype in {"scatterChart", "lineChart"} and pos["height"] < 145:
                advisories.append({"page": page["id"], "visual": visual["name"],
                                   "rule": "small_chart_plot_area", "details": "Inspect label visibility and plot area."})
        record["visual_inventory"] = inventory
        if len(palette) > 12:
            advisories.append({"page": page["id"], "rule": "page_palette_complexity",
                               "colors": sorted(palette)})
    return {"surface": "report", "source_sha256": result["source_sha256"],
            "pages": pages, "static_findings": findings, "advisories": advisories,
            "static_pass": result["geometry_pass"],
            "render_pass": result["captures_pass"] and
            not any(f["rule"] == "invalid_png_image" for f in findings)}
