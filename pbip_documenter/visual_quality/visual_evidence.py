"""Source-bound, per-visual crops for high-resolution image diagnosis.

Optional dependency: Pillow. The report/document preflight remains dependency-free.
A crop is *derived evidence*; it cannot replace the full-page review.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .evidence import digest, load
from .report import inspect_report_surface


def crop_report_visuals(report: Path, renders: Path, *, padding_px: int = 8) -> dict:
    """Produce visual crops from fresh, source-bound canvas images only."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Install pbip-documenter[visual] for visual crops") from exc
    if not 0 <= padding_px <= 32:
        raise ValueError("padding_px must be between 0 and 32")
    state = inspect_report_surface(report, renders)
    if not state["static_pass"] or not state["render_pass"]:
        raise ValueError("A complete, current canvas capture and clean geometry are required")
    pages_root = report / "definition" / "pages"
    manifest = {"schema": 1, "source_sha256": state["source_sha256"],
                "padding_px": padding_px, "pages": []}
    target_root = renders / "visual-crops"
    for page in state["pages"]:
        page_id, shot_name = page["id"], page["image"]
        shot = renders / shot_name
        expected = page["sha256"]
        if Path(shot_name).name != shot_name or digest(shot) != expected:
            raise ValueError(f"Stale or unsafe page image: {page_id}")
        definition = load(pages_root / page_id / "page.json")
        canvas_w, canvas_h = definition["width"], definition["height"]
        directory = target_root / hashlib.sha256(page_id.encode()).hexdigest()[:12]
        directory.mkdir(parents=True, exist_ok=True)
        page_record = {"id": page_id, "image_sha256": expected, "visuals": []}
        with Image.open(shot) as image:
            image.load()
            width, height = image.size
            if abs(width / height - canvas_w / canvas_h) > 0.015:
                raise ValueError(f"Screenshot is not a canvas-only crop: {page_id}")
            scale_x, scale_y = width / canvas_w, height / canvas_h
            visuals_dir = pages_root / page_id / "visuals"
            for index, visual_path in enumerate(sorted(visuals_dir.glob("*/visual.json"))):
                visual = load(visual_path)
                pos = visual["position"]
                box = [max(0, int(pos["x"] * scale_x) - padding_px),
                       max(0, int(pos["y"] * scale_y) - padding_px),
                       min(width, int((pos["x"] + pos["width"]) * scale_x) + padding_px),
                       min(height, int((pos["y"] + pos["height"]) * scale_y) + padding_px)]
                if box[0] >= box[2] or box[1] >= box[3]:
                    raise ValueError(f"Invalid crop bounds for {visual['name']}")
                filename = f"{index:02d}-{hashlib.sha256(visual['name'].encode()).hexdigest()[:12]}.png"
                target = directory / filename
                image.crop(tuple(box)).save(target, format="PNG")
                roles = visual.get("visual", {}).get("query", {}).get("queryState", {})
                binding = {role: [p.get("queryRef", "") for p in value.get("projections", [])]
                           for role, value in roles.items()}
                page_record["visuals"].append({
                    "id": visual["name"], "type": visual.get("visual", {}).get("visualType", ""),
                    "pbir_file": str(visual_path.relative_to(report)).replace("\\", "/"),
                    "position": pos, "roles": binding, "crop": str(target.relative_to(renders)).replace("\\", "/"),
                    "crop_sha256": digest(target), "crop_box_px": box,
                    "crop_box_normalized": [round(v / divisor, 6) for v, divisor in
                                            zip(box, (width, height, width, height), strict=True)],
                })
        manifest["pages"].append(page_record)
    out = renders / "visual-crops.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def verified_visuals(renders: Path, source_sha: str, page_id: str, image_sha: str) -> list[dict]:
    """Reject stale crops and path traversal before sending images to a reviewer."""
    path = renders / "visual-crops.json"
    if not path.is_file():
        return []
    manifest = load(path)
    if manifest.get("source_sha256") != source_sha:
        return []
    for page in manifest.get("pages", []):
        if page.get("id") != page_id or page.get("image_sha256") != image_sha:
            continue
        verified = []
        for item in page.get("visuals", []):
            crop = item.get("crop", "")
            target = (renders / crop).resolve()
            if not target.is_relative_to(renders.resolve()) or not target.is_file():
                raise ValueError("Unsafe or missing visual crop")
            if digest(target) != item.get("crop_sha256"):
                raise ValueError("Visual crop hash mismatch")
            verified.append(item)
        return verified
    return []


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Create source-bound, per-visual PNG crops")
    parser.add_argument("--source", type=Path, required=True, help="*.Report project directory")
    parser.add_argument("--renders", type=Path, required=True, help="Existing fresh canvas PNG directory")
    parser.add_argument("--padding", type=int, default=8)
    args = parser.parse_args()
    result = crop_report_visuals(args.source, args.renders, padding_px=args.padding)
    print(json.dumps({"source_sha256": result["source_sha256"],
                      "pages": len(result["pages"]),
                      "visual_crops": sum(len(p["visuals"]) for p in result["pages"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
