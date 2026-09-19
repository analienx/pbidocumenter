"""Opt-in Pi/Cline Pass image reviewer; never gives a model file-editing tools.

The source-bound report image is reviewed as a whole, with selected high-resolution
visual crops as secondary evidence. A partial page run is diagnostic ONLY.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .evidence import digest, load, png_size, verify_review
from .policy import CRITERIA, OPTIONAL, POLICY_VERSION
from .vision_reviewer import SYSTEM_PROMPT
from .visual_evidence import verified_visuals

BRIDGE = Path(__file__).with_name("pi_rpc_bridge.mjs")


def parse_model_json(raw: str) -> dict:
    """Only unadorned JSON or a single fenced JSON object is accepted."""
    text = raw.strip()
    match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.S | re.I)
    if match:
        text = match.group(1)
    value = json.loads(text)
    if not isinstance(value, dict) or not isinstance(value.get("observations"), list):
        raise ValueError("Model did not return a JSON observations object")
    return value


def invoke_pi(payload: dict, *, node: str = "node") -> str:
    binary = shutil.which(node)
    if not binary or not BRIDGE.is_file():
        raise RuntimeError("Node.js/Pi image reviewer transport is not installed")
    with tempfile.TemporaryDirectory(prefix="pbip-vision-") as folder:
        input_path = Path(folder) / "request.json"
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([binary, str(BRIDGE), str(input_path)], shell=False,
                                capture_output=True, text=True, timeout=payload["timeout_seconds"] + 15,
                                check=False)
    try:
        envelope = json.loads(result.stdout.strip())
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Pi image reviewer did not return a valid transport envelope") from exc
    if result.returncode or not envelope.get("ok") or envelope.get("model") != payload["model"]:
        raise RuntimeError(f"Pi image reviewer failed: {envelope.get('error', 'transport failure')}")
    if envelope.get("image_count") != len(payload["images"]):
        raise RuntimeError("Pi reviewer image count mismatch")
    return envelope["content"]


def _review_page(template: dict, page: dict, renders: Path, *, profile: Path,
                 model: str, reviewer_id: str, focus_id: str | None, node: str,
                 timeout: int) -> dict:
    name = page["image"]
    image = (renders / name).resolve()
    manifest = load(renders / "capture-manifest.json")
    if (Path(name).name != name or image.parent != renders.resolve()
            or not image.is_file() or digest(image) != page["image_sha256"]
            or manifest.get("files", {}).get(name) != page["image_sha256"]):
        raise ValueError("Source-bound full-page image is missing or stale")
    png_size(image)
    crops = verified_visuals(renders, template["source_sha256"],
                             page["id"], page["image_sha256"])
    if focus_id:
        crops = [item for item in crops if item["id"] == focus_id]
        if not crops:
            raise ValueError(f"No verified crop for visual {focus_id} on page {page['id']}")
    else:
        risk = {"scatterChart": 0, "lineChart": 1, "tableEx": 2}
        crops = sorted(crops, key=lambda item: risk.get(item["type"], 10))[:3]
    tasks = [{"id": item["id"], "criterion": CRITERIA[item["id"]],
              "optional": item["id"] in OPTIONAL[template["surface"]]}
             for item in page["observations"]]
    prompt = (SYSTEM_PROMPT + "\nYou are viewing the actual page PNG first, followed by its"
              " high-resolution chart crops. Do NOT make assumptions from metadata alone."
              " All region coordinates must refer to the FULL PAGE, not a crop."
              " Return exactly the complete 25-or-23-observation JSON object; no extra prose.\n"
              + json.dumps({"page_id": page["id"], "surface": template["surface"],
                            "checks": tasks, "visual_inventory": page.get("visual_inventory", []),
                            "focused_crops": [{"id": item["id"], "type": item["type"],
                                                "bindings": item["roles"], "source_context": item.get("source_context"),
                                                "page_region": item["crop_box_normalized"]}
                                               for item in crops]}, ensure_ascii=False))
    images = [{"path": str(image), "sha256": page["image_sha256"]}]
    for item in crops:
        target = (renders / item["crop"]).resolve()
        if not target.is_relative_to(renders.resolve()) or digest(target) != item["crop_sha256"]:
            raise ValueError("Invalid source-bound visual crop")
        images.append({"path": str(target), "sha256": item["crop_sha256"]})
    payload = {"provider": "cline-pass", "model": model, "agent_dir": str(profile),
               "timeout_seconds": timeout, "prompt": prompt, "images": images}
    for attempt in range(2):
        answer = parse_model_json(invoke_pi(payload, node=node))
        candidate = {"schema": 1, "policy_version": POLICY_VERSION,
                     "surface": template["surface"], "source_sha256": template["source_sha256"],
                     "fixer_id": template["fixer_id"],
                     "reviewer": {"id": reviewer_id, "role": "independent_visual_reviewer"},
                     "pages": [{"id": page["id"], "image_sha256": page["image_sha256"],
                                "observations": answer["observations"]}]}
        evidence = [{"id": page["id"], "sha256": page["image_sha256"],
                     "visual_inventory": page.get("visual_inventory", [])}]
        problems = verify_review(template["surface"], template["source_sha256"],
                                 evidence, candidate, template["fixer_id"])
        malformed = [problem for problem in problems if problem["rule"] != "visual_defect"]
        if not malformed:
            return candidate["pages"][0]
        if attempt == 1:
            raise ValueError(f"Pi reviewer returned invalid observations: {malformed[:4]}")
        payload["prompt"] += ("\nYour previous reply was incomplete or invalid. Reinspect the"
                              " images; return the FULL observation array with all criteria"
                              " and detailed evidence. Contract failures: "
                              + json.dumps(malformed[:8], ensure_ascii=False))
    raise RuntimeError("Unreachable reviewer state")


def review_with_pi(source: Path, request_file: Path, renders: Path, output: Path, *,
                   profile: Path, model: str, reviewer_id: str, allow_cloud_images: bool,
                   page_id: str | None = None, visual_id: str | None = None,
                   node: str = "node", timeout: int = 240) -> dict:
    if not allow_cloud_images:
        raise ValueError("Cline Pass uploads report images; --allow-cloud-images is required")
    if not 30 <= timeout <= 600 or not reviewer_id.strip():
        raise ValueError("Reviewer identifier or timeout is invalid")
    from .runner import request as fresh_request

    expected = fresh_request("report", source, renders, load(request_file)["fixer_id"])
    submitted = load(request_file)
    if submitted != expected or submitted.get("policy_version") != POLICY_VERSION:
        raise ValueError("Review request is stale, modified, or no longer source-bound")
    if reviewer_id == submitted["fixer_id"]:
        raise ValueError("The independent reviewer cannot also be the repair executor")
    selected = [page for page in expected["pages"] if page_id in (None, page["id"])]
    if not selected or (visual_id and not page_id):
        raise ValueError("Focused diagnostics require a valid page and visual")
    pages = [_review_page(expected, page, renders, profile=profile, model=model,
                          reviewer_id=reviewer_id, focus_id=visual_id, node=node,
                          timeout=timeout) for page in selected]
    diagnostic = page_id is not None
    result = {"schema": 2 if diagnostic else 1,
              "scope": "diagnostic_page_only" if diagnostic else "complete_report",
              "policy_version": POLICY_VERSION, "surface": "report",
              "source_sha256": expected["source_sha256"], "fixer_id": expected["fixer_id"],
              "reviewer": {"id": reviewer_id, "role": "independent_visual_reviewer",
                           "transport": "pi_rpc", "model": model,
                           "reviewed_at_utc": datetime.now(timezone.utc).isoformat()},
              "pages": pages}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in Pi Cline Pass image reviewer (no editing tools)")
    parser.add_argument("--source", type=Path, required=True, help="*.Report directory")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--renders", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--model", required=True, help="Explicitly chosen image-capable Cline Pass model")
    parser.add_argument("--profile", type=Path, required=True, help="Existing authenticated Pi agent profile")
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--allow-cloud-images", action="store_true")
    parser.add_argument("--page-id", help="Diagnostic-only review of one page; cannot approve full report")
    parser.add_argument("--visual-id", help="Focus high-resolution evidence on this visual")
    parser.add_argument("--node", default="node")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args(argv)
    if not args.model.startswith("cline-pass/"):
        parser.error("This adapter accepts Cline Pass subscription models only; use the generic adapter otherwise")
    result = review_with_pi(args.source, args.request, args.renders, args.review,
                            profile=args.profile, model=args.model, reviewer_id=args.reviewer_id,
                            allow_cloud_images=args.allow_cloud_images, page_id=args.page_id,
                            visual_id=args.visual_id, node=args.node, timeout=args.timeout)
    print(json.dumps({"scope": result["scope"], "model": args.model,
                      "reviewed_pages": len(result["pages"]),
                      "failed_observations": sum(item["status"] == "fail" for page in result["pages"]
                                                 for item in page["observations"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
