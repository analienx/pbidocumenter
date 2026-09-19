"""PBIR canvas geometry and rendered-evidence gate; no Power BI Desktop dependency.

A screenshot is evidence of a render, not proof of readable labels or correct data.
Human visual review and a separately verified live data refresh remain release gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from itertools import combinations
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _overlap(a: dict, b: dict) -> bool:
    return (min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]) > 1
            and min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]) > 1)


def _screenshot(path: Path) -> dict:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("not a PNG with an IHDR header")
    width, height = struct.unpack(">II", header[16:24])
    if width < 1280 or height < 720:
        raise ValueError(f"screenshot too small: {width}x{height}")
    return {"width": width, "height": height, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def source_digest(report: Path) -> str:
    """Bind captured renders to both the report and its companion semantic model."""
    root = report.parent
    model = sorted(root.glob("*.SemanticModel"))
    sources = [report, *model]
    digest = hashlib.sha256()
    for source in sources:
        for path in sorted(source.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".json", ".tmdl", ".pbism", ".pbir"}:
                digest.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
    return digest.hexdigest()


def inspect_report(report: Path, screenshots: Path | None = None) -> dict:
    """Inspect PBIR geometry and optionally confirm one fresh render file per page."""
    pages_root = report / "definition" / "pages"
    ids = _load(pages_root / "pages.json")["pageOrder"]
    findings: list[dict] = []
    digest = source_digest(report)
    manifest = None
    if screenshots is not None:
        path = screenshots / "capture-manifest.json"
        if path.is_file():
            manifest = _load(path)
        if manifest is None or manifest.get("source_sha256") != digest:
            findings.append({"rule": "missing_or_stale_capture_manifest", "source_sha256": digest})
    page_results: list[dict] = []
    for ordinal, page_id in enumerate(ids, start=1):
        page_dir = pages_root / page_id
        page = _load(page_dir / "page.json")
        width, height = page["width"], page["height"]
        visuals: list[dict] = []
        for folder in sorted((page_dir / "visuals").iterdir()):
            item = _load(folder / "visual.json")
            position = item["position"]
            obj = {"name": item["name"], "type": item["visual"]["visualType"], **position}
            visuals.append(obj)
            if position["width"] <= 0 or position["height"] <= 0:
                findings.append({"page": page_id, "visual": obj["name"], "rule": "nonpositive_size"})
            elif (position["x"] < 16 or position["y"] < 0 or
                  position["x"] + position["width"] > width + 0.1 or
                  position["y"] + position["height"] > height - 24 + 0.1):
                findings.append({"page": page_id, "visual": obj["name"], "rule": "canvas_margin_or_bounds"})
        for a, b in combinations(visuals, 2):
            if _overlap(a, b):
                findings.append({"page": page_id, "visual": f"{a['name']} | {b['name']}", "rule": "visual_overlap"})
        cards = [v for v in visuals if v["type"] in {"cardVisual", "card"}]
        if len(cards) == 4 and max(v["y"] for v in cards) - min(v["y"] for v in cards) < 48:
            if max(v["y"] for v in cards) - min(v["y"] for v in cards) > 2:
                findings.append({"page": page_id, "visual": "KPI row", "rule": "card_row_misaligned"})

        evidence = None
        if screenshots is not None:
            slug = re.sub(r"[^a-z0-9]+", "-", page["displayName"].lower()).strip("-")
            image = screenshots / f"{ordinal:02d}-{slug}.png"
            if not image.is_file():
                findings.append({"page": page_id, "rule": "missing_render", "path": str(image)})
            else:
                try:
                    evidence = {"name": image.name, **_screenshot(image)}
                    if manifest is None or manifest.get("files", {}).get(image.name) != evidence["sha256"]:
                        findings.append({"page": page_id, "rule": "stale_or_unbound_capture", "path": str(image)})
                except ValueError as exc:
                    findings.append({"page": page_id, "rule": "invalid_render", "detail": str(exc)})
        page_results.append({"id": page_id, "name": page["displayName"],
                             "visuals": len(visuals), "canvas": [width, height], "screenshot": evidence})
    reviewed: dict = {}
    if screenshots is not None:
        review_path = screenshots / "visual-review.json"
        if review_path.is_file():
            review = _load(review_path)
            if review.get("source_sha256") == digest:
                reviewed = {item["id"]: item for item in review.get("pages", [])}
    review_status = []
    for page in page_results:
        item = reviewed.get(page["id"], {})
        evidence = page["screenshot"]
        bound = evidence is not None and item.get("image_sha256") == evidence["sha256"]
        status = item.get("status", "missing") if bound else "missing_or_stale"
        issues = item.get("issues", []) if bound else []
        review_status.append({"page": page["id"], "status": status, "issues": issues})
    visual_review_pass = (screenshots is not None and len(review_status) == len(ids)
                          and all(item["status"] == "approved" and not item["issues"]
                                  for item in review_status))
    return {"schema": 1, "report": str(report), "source_sha256": digest, "pages": page_results,
            "geometry_pass": not any(f["rule"] not in {"missing_render", "invalid_render", "missing_or_stale_capture_manifest", "stale_or_unbound_capture"} for f in findings),
            "captures_pass": screenshots is not None and manifest is not None and not any(f["rule"] in {"missing_render", "invalid_render", "missing_or_stale_capture_manifest", "stale_or_unbound_capture"} for f in findings),
            "findings": findings,
            "visual_review": review_status,
            "visual_review_pass": visual_review_pass,
            "release_ready": False,
            "release_note": "A clean geometry/capture check is not semantic, data-refresh or visual-design approval."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check PBIR geometry and optional Desktop screenshots")
    parser.add_argument("report", type=Path, help="path to the *.Report project directory")
    parser.add_argument("--screenshots", type=Path, help="folder of numbered PNG screenshots in report page order")
    parser.add_argument("--output", type=Path, help="JSON evidence output (optional)")
    args = parser.parse_args(argv)
    result = inspect_report(args.report, args.screenshots)
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["geometry_pass"] and (args.screenshots is None or (result["captures_pass"] and result["visual_review_pass"])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
