"""Cross-check independent vision diagnoses without confusing confidence with truth.

Agreement is image evidence, not semantic proof. Disagreement blocks automated
acceptance/repair until independently adjudicated against the rendered visual.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence import load, verify_review
from .policy import POLICY_VERSION, REQUIRED


def compare_diagnostics(first: dict, second: dict, page: dict) -> dict:
    required = {"schema": 2, "scope": "diagnostic_page_only",
                "policy_version": POLICY_VERSION, "surface": "report"}
    for item in (first, second):
        if any(item.get(key) != value for key, value in required.items()):
            raise ValueError("Independent review has an invalid diagnostic contract")
        if item.get("source_sha256") != first.get("source_sha256") or len(item.get("pages", [])) != 1:
            raise ValueError("Independent reviews must cover one identical source revision")
        if (item["pages"][0].get("id") != page["id"]
                or item["pages"][0].get("image_sha256") != page["sha256"]):
            raise ValueError("Independent reviewers must assess the exact same rendered page")
        trial = {**item, "schema": 1}
        findings = verify_review("report", item["source_sha256"], [page], trial, item["fixer_id"])
        if any(f["rule"] != "visual_defect" for f in findings):
            raise ValueError("Independent reviewer did not satisfy the observation contract")
    left, right = first["reviewer"], second["reviewer"]
    if (left.get("id") == right.get("id") or left.get("model") == right.get("model")
            or not left.get("model") or not right.get("model")):
        raise ValueError("Independent review requires two different reviewer identities and models")
    a = {item["id"]: item for item in first["pages"][0]["observations"]}
    b = {item["id"]: item for item in second["pages"][0]["observations"]}
    if set(a) != set(REQUIRED["report"]) or set(b) != set(REQUIRED["report"]):
        raise ValueError("The reviews do not cover every required observation")
    findings = []
    for check in REQUIRED["report"]:
        one, two = a[check], b[check]
        if one["status"] == two["status"] == "pass":
            continue
        kind = "shared_visual_defect" if one["status"] == two["status"] == "fail" else "needs_adjudication"
        findings.append({"rule": kind, "check": check,
                         "reviewers": [{"id": left["id"], "model": left["model"], **one},
                                       {"id": right["id"], "model": right["model"], **two}]})
    return {"schema": 1, "source_sha256": first["source_sha256"],
            "page": page["id"], "page_image_sha256": page["sha256"],
            "reviewed_models": [left["model"], right["model"]],
            "findings": findings, "can_auto_approve": False,
            "semantic_validation_required": True,
            "note": "A diagnostic comparison never approves the entire report; disagreements require adjudication."}


def main() -> int:
    from .report import inspect_report_surface

    parser = argparse.ArgumentParser(description="Compare two independent source-bound visual diagnoses")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--renders", type=Path, required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = inspect_report_surface(args.source, args.renders)
    if not state["static_pass"] or not state["render_pass"]:
        raise ValueError("Current source-bound screenshots are required")
    first, second = load(args.first), load(args.second)
    page_id = first["pages"][0]["id"]
    page = next((entry for entry in state["pages"] if entry["id"] == page_id), None)
    if page is None or state["source_sha256"] != first.get("source_sha256"):
        raise ValueError("Independent review source does not match report")
    result = compare_diagnostics(first, second, page)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"page": result["page"], "shared": sum(f["rule"] == "shared_visual_defect"
                      for f in result["findings"]), "disputed": sum(f["rule"] == "needs_adjudication"
                      for f in result["findings"]), "auto_approval": False}))
    return 2 if result["findings"] else 0  # Exit 0 means diagnostics agree, never report approval.


if __name__ == "__main__":
    raise SystemExit(main())
