"""Constrained chart-area repair triggered by an observed internal scrollbar."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pbip_documenter.quality_gate import inspect_report, source_digest

from .evidence import load
from .repair_actions import _visual_path


def plan_fit_chart(report: Path, findings: dict, *, page_id: str, visual_id: str,
                   extra_height: int = 36, min_lower_height: int = 150) -> dict:
    before = source_digest(report)
    if findings.get("source_sha256") != before:
        raise ValueError("Stale source for chart-resize proposal")
    defects = [f for f in findings.get("findings", [])
               if f.get("rule") == "visual_defect" and f.get("page") == page_id
               and f.get("visual_id") == visual_id and f.get("check") == "scrollbars_in_key_visuals"]
    if not defects:
        raise ValueError("A verified, visual-specific internal-scrollbar observation is required")
    if not 8 <= extra_height <= 80 or not 100 <= min_lower_height <= 320:
        raise ValueError("Unsafe chart-size request")
    page_dir = report / "definition" / "pages" / page_id
    canvas = load(page_dir / "page.json")
    target_path = _visual_path(report, page_id, visual_id)
    target = load(target_path)
    pos = target["position"]
    if target["visual"]["visualType"] in {"slicer", "textbox", "card", "cardVisual"}:
        raise ValueError("This resize recipe applies only to analytical charts")
    siblings = [(p, load(p)) for p in (page_dir / "visuals").glob("*/visual.json")
                if p != target_path]
    row = [(target_path, target)] + [(path, v) for path, v in siblings
                                      if abs(v["position"]["y"] - pos["y"]) < 2]
    cards = [(path, v) for path, v in siblings
             if v.get("visual", {}).get("visualType") in {"card", "cardVisual"}]
    if len(cards) != 4 or len({v["position"]["y"] for _, v in cards}) != 1:
        raise ValueError("This conservative recipe requires one aligned four-card row")
    card_y = cards[0][1]["position"]["y"]
    card_bottom = max(v["position"]["y"] + v["position"]["height"] for _, v in cards)
    if pos["y"] - card_bottom < 20:
        raise ValueError("Insufficient chart-to-KPI spacing to reallocate")
    shift = extra_height - 4
    if shift < 4 or card_y - shift < 80 or pos["y"] - extra_height < card_bottom - shift + 16:
        raise ValueError("No safe vertical space above the chart")
    slicers = [(path, v) for path, v in siblings
               if v.get("visual", {}).get("visualType") == "slicer"
               and v["position"]["y"] < card_y]
    if not slicers or any(v["position"]["height"] - shift < 88 for _, v in slicers):
        raise ValueError("Filter controls cannot be compressed without risking clipping")
    next_y = min((v["position"]["y"] for _, v in siblings
                  if v["position"]["y"] > pos["y"] + 2), default=None)
    if next_y is None or next_y - (pos["y"] + pos["height"]) < 16:
        raise ValueError("There is no protected lower row or safe chart gutter")
    if pos["y"] + pos["height"] > canvas["height"] - 24:
        raise ValueError("Invalid report canvas")
    def key(path):
        return str(path.relative_to(report)).replace("\\", "/")
    changes = {key(path): {"y": v["position"]["y"] - extra_height,
                           "height": v["position"]["height"] + extra_height}
               for path, v in row}
    changes.update({key(path): {"y": v["position"]["y"] - shift,
                                 "height": v["position"]["height"]} for path, v in cards})
    changes.update({key(path): {"y": v["position"]["y"],
                                 "height": v["position"]["height"] - shift} for path, v in slicers})
    return {"schema": 1, "source_sha256": before, "operation": "fit_internal_scroll",
            "page_id": page_id, "visual_id": visual_id, "changes": changes,
            "addresses": ["scrollbars_in_key_visuals"], "required_review_after": True}


def apply_fit_plan(report: Path, plan: dict, *, apply: bool = False) -> dict:
    if (plan.get("schema") != 1 or plan.get("operation") != "fit_internal_scroll" or
            plan.get("source_sha256") != source_digest(report) or
            plan.get("required_review_after") is not True):
        raise ValueError("Unsupported or stale fit plan")
    page_id, visual_id = plan["page_id"], plan["visual_id"]
    anchor = _visual_path(report, page_id, visual_id)
    page_root = (report / "definition" / "pages" / page_id / "visuals").resolve()
    if str(anchor.relative_to(report)).replace("\\", "/") not in plan["changes"]:
        raise ValueError("The target visual is absent from the fit plan")
    revisions = []
    for relative, position in plan["changes"].items():
        path = (report / relative).resolve()
        if not path.is_relative_to(page_root) or path.name != "visual.json" or not path.is_file():
            raise ValueError("Fit plan addresses an unsafe or missing PBIR file")
        visual = load(path)
        if (set(position) != {"y", "height"} or not all(isinstance(v, (int, float)) for v in position.values())
                or position["height"] < (80 if visual.get("visual", {}).get("visualType") == "slicer" else 100) or position["y"] < 0):
            raise ValueError("Fit plan contains invalid geometry")
        old = path.read_bytes()
        visual = json.loads(old.decode("utf-8-sig"))
        visual["position"].update(position)
        revisions.append((path, old, json.dumps(visual, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"))
    result = {"applied": False, "operation": "fit_internal_scroll",
              "visual_id": visual_id, "files": [str(p.relative_to(report)) for p, _, _ in revisions],
              "before_source_sha256": plan["source_sha256"],
              "required_next_gate": "fresh populated Desktop render and independent visual review"}
    if not apply:
        return result
    written = []
    try:
        for path, old, updated in revisions:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".visual-tmp", delete=False) as fh:
                fh.write(updated)
                temporary = Path(fh.name)
            try:
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            written.append((path, old))
        gate = inspect_report(report)
        if not gate["geometry_pass"]:
            raise ValueError(f"Proposed fit breaks PBIR geometry: {gate['findings'][:3]}")
    except Exception:
        for path, original in reversed(written):
            path.write_bytes(original)
        raise
    result.update(applied=True, after_source_sha256=source_digest(report))
    return result
