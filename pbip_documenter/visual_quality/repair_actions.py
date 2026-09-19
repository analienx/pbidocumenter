"""Evidence-bound, explicit Power BI visual-repair recipes.

No arbitrary Python, shell or model-provided JSONPath is executed. Changes
require a source digest, an existing defect and an allowlisted operation.
Apply only in an isolated worktree; Desktop must render the result again.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from pathlib import Path

from pbip_documenter.quality_gate import source_digest as source_fingerprint

from .evidence import load


def plan_scatter_to_bar(report: Path, findings: dict, *, page_id: str, visual_id: str,
                        title: str, value_role: str = "Y") -> dict:
    """Propose a ranked comparison only when a visual defect identifies it."""
    expected = source_fingerprint(report)
    if findings.get("source_sha256") != expected:
        raise ValueError("Repair evidence does not match the current report/model source")
    defects = [i for i in findings.get("findings", []) if i.get("rule") == "visual_defect"
               and i.get("page") == page_id and i.get("visual_id") == visual_id]
    if not defects:
        raise ValueError("A source-bound, visual-specific defect is required")
    if not 3 <= len(title.strip()) <= 90 or "'" in title:
        raise ValueError("Provide a short chart title without single quotes")
    path = _visual_path(report, page_id, visual_id)
    item = load(path)
    if item.get("visual", {}).get("visualType") != "scatterChart":
        raise ValueError("Only a scatter visual can use this recipe")
    roles = item["visual"]["query"]["queryState"]
    if value_role not in {"X", "Y"} or not roles.get("Category") or not roles.get(value_role):
        raise ValueError("The selected comparison and category must both be bound")
    return {"schema": 1, "source_sha256": expected, "operation": "scatter_to_ranked_bar",
            "page_id": page_id, "visual_id": visual_id, "value_role": value_role,
            "title": title, "addresses": sorted({d["check"] for d in defects}),
            "required_review_after": True}


def _visual_path(report: Path, page_id: str, visual_id: str) -> Path:
    pages = report / "definition" / "pages"
    order = load(pages / "pages.json")["pageOrder"]
    if page_id not in order:
        raise ValueError("Page ID is absent from report page inventory")
    paths = [p for p in (pages / page_id / "visuals").glob("*/visual.json")
             if load(p).get("name") == visual_id]
    if len(paths) != 1:
        raise ValueError("Visual ID must resolve uniquely within its page")
    return paths[0]


def _transform(item: dict, plan: dict) -> dict:
    value = copy.deepcopy(item)
    visual = value["visual"]
    if visual.get("visualType") != "scatterChart":
        raise ValueError("Stale repair: visual is no longer a scatter plot")
    state = visual["query"]["queryState"]
    category = copy.deepcopy(state["Category"])
    metric = copy.deepcopy(state[plan["value_role"]])
    if not category.get("projections") or not metric.get("projections"):
        raise ValueError("Cannot replace a chart with unbound comparison fields")
    tooltips = []
    for role in ("X", "Y", "Size", "Tooltips"):
        if role != plan["value_role"]:
            tooltips.extend(copy.deepcopy(state.get(role, {}).get("projections", [])))
    visual["visualType"] = "clusteredBarChart"
    visual["query"]["queryState"] = {"Category": category, "Y": metric,
                                     "Tooltips": {"projections": tooltips}}
    visual["query"]["sortDefinition"] = {"sort": [
        {"field": copy.deepcopy(metric["projections"][0]["field"]),
         "direction": "Descending"}], "isDefaultSort": True}
    title = visual["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]
    title["Value"] = "'" + plan["title"] + "'"
    return value


def execute_plan(report: Path, plan: dict, *, apply: bool = False) -> dict:
    expected = source_fingerprint(report)
    if (plan.get("schema") != 1 or plan.get("source_sha256") != expected or
            plan.get("operation") != "scatter_to_ranked_bar" or
            plan.get("required_review_after") is not True or not plan.get("addresses")):
        raise ValueError("Unsupported or stale evidence-bound repair plan")
    path = _visual_path(report, plan["page_id"], plan["visual_id"])
    original = load(path)
    patched = _transform(original, plan)
    result = {"operation": plan["operation"], "visual_id": plan["visual_id"],
              "before_type": original["visual"]["visualType"],
              "after_type": patched["visual"]["visualType"],
              "before_source_sha256": expected, "applied": False,
              "required_next_gate": "fresh Desktop render and independent visual review"}
    if not apply:
        return result
    with tempfile.NamedTemporaryFile(mode="w", suffix=".visual-tmp", dir=path.parent,
                                     encoding="utf-8", delete=False) as handle:
        json.dump(patched, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    result.update(applied=True, after_source_sha256=source_fingerprint(report))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply an allowlisted, source-bound PBIR repair")
    parser.add_argument("report", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = execute_plan(args.report, load(args.plan), apply=args.apply)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
