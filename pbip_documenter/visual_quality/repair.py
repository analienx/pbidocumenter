"""Conservative PBIR geometry repair; chart semantics always require a specialist."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


def align_kpi_rows(report: Path, apply: bool = False) -> list[dict]:
    changes: list[dict] = []
    for page_dir in sorted((report / "definition" / "pages").iterdir()):
        if not page_dir.is_dir() or not (page_dir / "page.json").is_file():
            continue
        page = json.loads((page_dir / "page.json").read_text(encoding="utf-8-sig"))
        visuals = [(file, json.loads(file.read_text(encoding="utf-8-sig")))
                   for file in sorted((page_dir / "visuals").glob("*/visual.json"))]
        cards = [(path, value) for path, value in visuals
                 if value.get("visual", {}).get("visualType") in {"card", "cardVisual"}]
        if len(cards) != 4:
            continue
        positions = [v["position"] for _, v in cards]
        ys = [p["y"] for p in positions]
        if max(ys) - min(ys) > 48:
            continue  # This may be an intentional, multi-row design.
        target = max(ys)
        if target + max(p["height"] for p in positions) > page["height"] - 24:
            continue
        for path, value in cards:
            old = value["position"]["y"]
            if abs(old - target) <= 1:
                continue
            moved = {**value["position"], "y": target}
            collision = any(other not in [v for _, v in cards] and
                            min(moved["x"] + moved["width"], other["position"]["x"] + other["position"]["width"]) -
                            max(moved["x"], other["position"]["x"]) > 1 and
                            min(moved["y"] + moved["height"], other["position"]["y"] + other["position"]["height"]) -
                            max(moved["y"], other["position"]["y"]) > 1
                            for _, other in visuals)
            if collision:
                continue  # Do not trade alignment for an overlapping chart.
            changes.append({"page": page["name"], "visual": value["name"],
                            "file": str(path), "old_y": old, "new_y": target})
            if apply:
                value["position"]["y"] = target
                content = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                                 dir=path.parent, suffix=".visual-tmp") as handle:
                    handle.write(content)
                    temp = Path(handle.name)
                os.replace(temp, path)
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Conservative Power BI geometry-only fixer")
    parser.add_argument("report", type=Path)
    parser.add_argument("--apply", action="store_true", help="Explicitly modify PBIR; default is dry run")
    args = parser.parse_args()
    changes = align_kpi_rows(args.report, apply=args.apply)
    print(json.dumps({"applied": args.apply, "changes": changes}, indent=2))
    return 0 if changes else 2  # No safe fix: escalate rather than pretend success.


if __name__ == "__main__":
    raise SystemExit(main())
