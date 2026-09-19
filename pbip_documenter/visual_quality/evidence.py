"""Evidence contract shared by Power BI canvases and rendered Word pages."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

from .policy import CRITERIA, OPTIONAL, POLICY_VERSION, REQUIRED, SEVERITIES, STATUSES


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    """Validate PNG chunk boundaries and CRCs, not merely a forged header."""
    with path.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Invalid PNG signature: {path}")
        size = None
        seen_data = seen_end = False
        for _ in range(100000):
            header = handle.read(8)
            if len(header) != 8:
                break
            length, tag = struct.unpack(">I4s", header)
            if length > 100_000_000:
                raise ValueError(f"Oversized PNG chunk: {path}")
            payload, check = handle.read(length), handle.read(4)
            if len(payload) != length or len(check) != 4:
                raise ValueError(f"Truncated PNG chunk: {path}")
            if zlib.crc32(tag + payload) != struct.unpack(">I", check)[0]:
                raise ValueError(f"Corrupt PNG chunk: {path}")
            if tag == b"IHDR":
                if size is not None or length != 13:
                    raise ValueError(f"Invalid PNG header: {path}")
                size = struct.unpack(">II", payload[:8])
            if tag == b"IDAT":
                seen_data = True
            if tag == b"IEND":
                seen_end = True
                break
        if size is None or not seen_data or not seen_end or not all(1 <= x <= 20000 for x in size):
            raise ValueError(f"Incomplete PNG image: {path}")
        return size


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def image_evidence(images: Path, source_sha: str, page_ids: list[str]) -> tuple[list[dict], list[dict]]:
    """Check that the renderer's manifest binds every page to this source revision."""
    manifest_path = images / "capture-manifest.json"
    if not manifest_path.is_file():
        return [], [{"rule": "render_manifest_missing", "path": str(manifest_path)}]
    manifest = load(manifest_path)
    issues: list[dict] = []
    if manifest.get("source_sha256") != source_sha:
        issues.append({"rule": "render_source_stale"})
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        return [], issues + [{"rule": "render_manifest_invalid"}]
    pages: list[dict] = []
    for page_id in page_ids:
        name = page_id if page_id.lower().endswith(".png") else page_id + ".png"
        path = images / name
        if not path.is_file():
            issues.append({"rule": "page_render_missing", "page": page_id})
            continue
        try:
            size = png_size(path)
            if min(size) < 450:
                raise ValueError("image too small to review")
            sha = digest(path)
        except ValueError as exc:
            issues.append({"rule": "page_render_invalid", "page": page_id, "detail": str(exc)})
            continue
        if files.get(name) != sha:
            issues.append({"rule": "page_render_unbound", "page": page_id})
        pages.append({"id": page_id, "image": name, "sha256": sha, "pixels": size})
    return pages, issues


def review_template(kind: str, source_sha: str, pages: list[dict], fixer_id: str) -> dict:
    """Unapproved checklist: missing judgments can never pass by default."""
    return {"schema": 1, "policy_version": POLICY_VERSION, "surface": kind,
            "source_sha256": source_sha, "fixer_id": fixer_id,
            "reviewer": {"id": "", "role": "independent_visual_reviewer"},
            "pages": [{"id": page["id"], "image": page["image"], "image_sha256": page["sha256"],
                       "visual_inventory": page.get("visual_inventory", []),
                       "observations": [{"id": check, "criterion": CRITERIA[check], "status": "pending", "reason": "",
                                         "severity": None, "region": None, "visual_id": "page", "proposed_fix": ""}
                                        for check in REQUIRED[kind]]} for page in pages]}


def verify_review(kind: str, source_sha: str, pages: list[dict], review: dict,
                  fixer_id: str) -> list[dict]:
    findings: list[dict] = []
    if (review.get("schema") != 1 or review.get("policy_version") != POLICY_VERSION or
            review.get("surface") != kind or review.get("source_sha256") != source_sha):
        return [{"rule": "review_policy_or_source_mismatch"}]
    reviewer = review.get("reviewer", {})
    reviewer_id = reviewer.get("id", "") if isinstance(reviewer, dict) else ""
    if (not reviewer_id or reviewer_id == fixer_id or
            reviewer.get("role") != "independent_visual_reviewer"):
        findings.append({"rule": "independent_reviewer_required"})
    rows = review.get("pages", [])
    if not isinstance(rows, list) or len(rows) != len(pages):
        return findings + [{"rule": "review_page_inventory_mismatch"}]
    observed = {p.get("id"): p for p in rows if isinstance(p, dict)}
    if len(observed) != len(pages):
        return findings + [{"rule": "review_duplicate_page"}]
    for page in pages:
        item = observed.get(page["id"])
        if not item or item.get("image_sha256") != page["sha256"]:
            findings.append({"rule": "review_image_stale", "page": page["id"]})
            continue
        answers = item.get("observations", [])
        if not isinstance(answers, list):
            findings.append({"rule": "review_observations_invalid", "page": page["id"]})
            continue
        by_id = {a.get("id"): a for a in answers if isinstance(a, dict)}
        expected = set(REQUIRED[kind])
        if len(by_id) != len(answers) or set(by_id) != expected:
            findings.append({"rule": "review_observations_incomplete", "page": page["id"]})
            continue
        for check in expected:
            answer = by_id[check]
            status, reason = answer.get("status"), answer.get("reason")
            if status not in STATUSES or not isinstance(reason, str) or len(reason.strip()) < 32:
                findings.append({"rule": "observation_unsubstantiated", "page": page["id"], "check": check})
            elif status == "not_applicable" and check not in OPTIONAL[kind]:
                findings.append({"rule": "mandatory_observation_skipped", "page": page["id"], "check": check})
            elif status == "fail":
                region = answer.get("region")
                located = (isinstance(region, list) and len(region) == 4 and
                           all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in region) and
                           region[0] < region[2] and region[1] < region[3])
                valid_ids = {"page"} | {v["id"] for v in page.get("visual_inventory", [])}
                if (answer.get("severity") not in SEVERITIES or not located or
                        answer.get("visual_id") not in valid_ids or
                        len(str(answer.get("proposed_fix", "")).strip()) < 12):
                    findings.append({"rule": "issue_lacks_location_or_repair", "page": page["id"], "check": check})
                else:
                    findings.append({"rule": "visual_defect", "page": page["id"], "check": check,
                                     "severity": answer["severity"], "region": region, "visual_id": answer["visual_id"],
                                     "detail": reason, "proposed_fix": answer["proposed_fix"]})
    return findings
