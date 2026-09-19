"""Bind independent image diagnoses to exact PBIR source and repair candidates.

A diagnostic review is never converted into a release approval. Model-proposed
root causes are hypotheses; the repair executor must inspect fields/data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pbip_documenter.quality_gate import source_digest

from .evidence import load, verify_review
from .policy import POLICY_VERSION
from .report import inspect_report_surface
from .visual_evidence import verified_visuals


def build_handoff(report: Path, renders: Path, diagnostic: Path) -> dict:
    review = load(diagnostic)
    state = inspect_report_surface(report, renders)
    if not state["static_pass"] or not state["render_pass"]:
        raise ValueError("A current, complete report render is required")
    if (review.get("schema") != 2 or review.get("scope") != "diagnostic_page_only"
            or review.get("policy_version") != POLICY_VERSION or review.get("surface") != "report"
            or review.get("source_sha256") != source_digest(report)
            or len(review.get("pages", [])) != 1):
        raise ValueError("Expected an exact-source, single-page diagnostic review")
    reviewed = review["pages"][0]
    page = next((item for item in state["pages"] if item["id"] == reviewed.get("id")), None)
    if page is None or reviewed.get("image_sha256") != page["sha256"]:
        raise ValueError("Reviewer page/image identity does not match current capture")
    isolated = {**review, "schema": 1, "pages": [reviewed]}
    findings = verify_review("report", state["source_sha256"], [page],
                             isolated, review["fixer_id"])
    invalid = [item for item in findings if item["rule"] != "visual_defect"]
    if invalid:
        raise ValueError(f"Diagnostic is invalid: {invalid[:3]}")
    crops = {item["id"]: item for item in verified_visuals(
        renders, state["source_sha256"], page["id"], page["sha256"])}
    records = []
    for finding in findings:
        entry = {**finding, "source_sha256": state["source_sha256"],
                 "page_image_sha256": page["sha256"], "diagnostic_only": True}
        match = crops.get(finding["visual_id"])
        if match:
            entry.update(pbir_file=match["pbir_file"], binding_roles=match["roles"],
                         crop=match["crop"], crop_sha256=match["crop_sha256"])
            if finding["check"] in {"chart_type_suitability", "axis_precision"} and match["type"] == "scatterChart":
                entry["repair_candidate"] = "scatter_to_ranked_bar_requires_metric_choice"
            elif finding["check"] == "scrollbars_in_key_visuals":
                entry["repair_candidate"] = "fit_internal_scroll_requires_sibling_layout_check"
            else:
                entry["repair_candidate"] = "specialist_review_required"
        else:
            entry["repair_candidate"] = "page_level_review_required"
        records.append(entry)
    return {"schema": 1, "source_sha256": state["source_sha256"],
            "page": page["id"], "page_image_sha256": page["sha256"],
            "reviewer": review["reviewer"], "diagnostic_only": True,
            "findings": records, "release_ready": False,
            "root_cause_policy": "Image observations are symptoms; inspect PBIR and data before applying a repair."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create source-bound PBIR repair handoff from visual diagnosis")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--renders", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_handoff(args.source, args.renders, args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"page": result["page"], "defects": len(result["findings"]),
                      "visuals": sorted({item["visual_id"] for item in result["findings"]})}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
