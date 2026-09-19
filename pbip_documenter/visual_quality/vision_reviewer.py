"""Optional image-review adapter for an explicitly configured vision model.

No endpoint, credentials or model are provisioned by PBIPDocumenter. Report
images leave the computer ONLY if the user configures a non-local endpoint.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .evidence import digest, load, png_size, verify_review
from .policy import CRITERIA, OPTIONAL, POLICY_VERSION, REQUIRED

SYSTEM_PROMPT = """You are an INDEPENDENT visual QA reviewer, not the report generator.
Examine the supplied rendered page at its actual intended display size, not
just metadata. Every required observation must be judged using visible evidence.
If labels, ticks or figures cannot be read, mark FAIL rather than guessing.
Evaluate color meaning, contrast, hierarchy, spacing, inner padding, chart
appropriateness, axis tick count and distinctness, useful/nonredundant axis
titles, clipping, unnecessary scrollbars, table fit, consistency and narrative.
A semantically wrong but attractive graphic FAILS. Empty charts FAIL.
Return exactly JSON {"observations": [{"id":..., "status":"pass|fail|not_applicable",
"reason":..., "severity":"critical|high|medium|low" or null,
"region":[x0,y0,x1,y1] or null, "visual_id":..., "proposed_fix":...}]}.
Regions are fractions of the IMAGE (0..1); for page-wide issues use
[0,0,1,1]. Use visual_id from inventory if available, otherwise 'page'.
Every reason MUST cite a specific visible aspect, >=32 characters. For each
FAIL, include severity, valid region, and a concrete proposed fix >=12 chars.
Use not_applicable only for explicitly optional observations. Do not claim
that code, geometry or a screenshot hash proves visual quality.
"""


def _image(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode("ascii"), "detail": "high"}}


def review_with_model(request_file: Path, renders: Path, output: Path, *,
                      endpoint: str, model: str, reviewer_id: str, api_key_env: str = "",
                      allow_remote: bool = False, timeout: int = 180) -> dict:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("An explicit HTTP(S) vision endpoint is required")
    local = parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
    if not local and (not allow_remote or parsed.scheme != "https"):
        raise ValueError("Remote image transfer requires HTTPS and --allow-remote")
    renders = renders.resolve()
    template = load(request_file)
    surface = template["surface"]
    if template["policy_version"] != POLICY_VERSION or surface not in REQUIRED:
        raise ValueError("Unsupported visual review policy")
    if reviewer_id == template["fixer_id"] or not reviewer_id.strip():
        raise ValueError("The visual reviewer must be separate from the repair executor")
    key = os.environ.get(api_key_env, "") if api_key_env else ""
    headers = {"Content-Type": "application/json"}
    if api_key_env:
        if not key:
            raise ValueError("Configured API-key environment variable is empty")
        headers["Authorization"] = "Bearer " + key
    manifest = load(renders / "capture-manifest.json")
    if manifest.get("source_sha256") != template["source_sha256"]:
        raise ValueError("Rendered pages do not match the source revision")
    pages = template["pages"]
    results: list[dict] = []
    for index, page in enumerate(pages):
        name = page["image"]
        target = renders / name
        if (Path(name).name != name or not target.is_file() or target.resolve().parent != renders
                or digest(target) != page["image_sha256"] or manifest.get("files", {}).get(name) != page["image_sha256"]):
            raise ValueError(f"No source-bound rendered page for {page['id']}")
        png_size(target)
        tasks = [{"id": x["id"], "criterion": CRITERIA[x["id"]],
                  "optional": x["id"] in OPTIONAL[surface]} for x in page["observations"]]
        details = {"surface": surface, "page_id": page["id"], "checks": tasks,
                   "visual_inventory": page.get("visual_inventory", []),
                   "response_format": "JSON observations only"}
        content = [{"type": "text", "text": json.dumps(details, ensure_ascii=False)}, _image(target)]
        if index and len(pages) > 1:
            first_sha = pages[0]["image_sha256"]
            first = pages[0]["image"]
            if Path(first).name != first or digest(renders / first) != first_sha:
                raise ValueError("Reference style image is stale or invalid")
            content += [{"type": "text", "text": "First-page reference for cross-page theme consistency:"},
                        _image(renders / first)]
        payload = {"model": model, "temperature": 0,
                   "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": content}]}
        wire = json.dumps(payload).encode("utf-8")
        api_request = urllib.request.Request(endpoint, data=wire, headers=headers, method="POST")
        with urllib.request.urlopen(api_request, timeout=timeout) as response:
            reply = json.load(response)
        raw = reply["choices"][0]["message"]["content"]
        if isinstance(raw, list):
            raw = "".join(part.get("text", "") for part in raw if isinstance(part, dict))
        answer = json.loads(raw)
        results.append({"id": page["id"], "image_sha256": page["image_sha256"],
                        "observations": answer["observations"]})
    finished = {"schema": 1, "policy_version": POLICY_VERSION, "surface": surface,
                "source_sha256": template["source_sha256"], "fixer_id": template["fixer_id"],
                "reviewer": {"id": reviewer_id, "role": "independent_visual_reviewer",
                             "model": model, "reviewed_at_utc": datetime.now(timezone.utc).isoformat()},
                "pages": results}
    inventory = [{"id": p["id"], "sha256": p["image_sha256"],
                  "visual_inventory": p.get("visual_inventory", [])} for p in pages]
    failures = verify_review(surface, template["source_sha256"], inventory,
                             finished, template["fixer_id"])
    malformed = [f for f in failures if f["rule"] != "visual_defect"]
    if malformed:
        raise ValueError(f"Vision model returned incomplete or invalid observations: {malformed[:3]}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(finished, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return finished


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicitly configured vision-model page reviewer")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--renders", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--api-key-env", default="")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    result = review_with_model(args.request, args.renders, args.review, endpoint=args.endpoint,
                               model=args.model, reviewer_id=args.reviewer_id,
                               api_key_env=args.api_key_env, allow_remote=args.allow_remote)
    print(json.dumps({"reviewed_pages": len(result["pages"]),
                      "failed_observations": sum(o["status"] == "fail" for p in result["pages"]
                                                 for o in p["observations"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
