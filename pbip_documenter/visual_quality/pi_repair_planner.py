"""Text-only repair planning from independently verified, source-bound image diagnoses.

GLM/DeepSeek see structured findings and field bindings, NEVER page pixels.
Their output is a proposal requiring semantic checks and fresh image review.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .handoff import build_handoff
from .pi_reviewer import invoke_pi


def plan_with_text_model(source: Path, renders: Path, diagnostic: Path, output: Path, *,
                         profile: Path, model: str, allow_cloud_context: bool,
                         timeout: int = 180) -> dict:
    if not allow_cloud_context:
        raise ValueError("--allow-cloud-context is required to send report metadata to Cline")
    if not 30 <= timeout <= 600 or not model.startswith(("cline/", "cline-pass/")):
        raise ValueError("Choose a configured Cline or Cline Pass text model and bounded timeout")
    validated = build_handoff(source, renders, diagnostic)
    if not validated["findings"]:
        raise ValueError("No verified visual defects need repair planning")
    observations = [{"check": item["check"], "visible_symptom": item["detail"],
                     "page": item["page"], "visual_id": item["visual_id"],
                     "binding_roles": item.get("binding_roles", {}),
                     "pbir_file": item.get("pbir_file"),
                     "candidate": item["repair_candidate"]}
                    for item in validated["findings"][:25]]
    message = ("You are a TEXT-ONLY Power BI source repair planner. You have NOT seen the"
               " rendered image. The observations below come from an independent vision"
               " reviewer; treat descriptions and proposed fixes as evidence/hypotheses, not"
               " proven DAX/model faults. Return ONLY a JSON object with fields"
               " observed_symptoms, not_verified, proposed_chart_recipe, chosen_value_role,"
               " semantic_guardrails, fresh_render_checks. Identify safe reversible PBIR"
               " changes first. Before changing chart type or DAX, verify the field bindings,"
               " business question and grouped data. Never claim to have seen pixels."
               " You cannot approve visual quality or execute edits.\n"
               + json.dumps({"source_sha256": validated["source_sha256"],
                             "page": validated["page"], "findings": observations}, ensure_ascii=False))
    payload = {"task": "repair_planning", "provider": model.split("/", 1)[0],
               "model": model, "agent_dir": str(profile.resolve()),
               "timeout_seconds": timeout, "prompt": message, "images": []}
    raw = invoke_pi(payload)
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1)
    candidate = json.loads(text)
    expected_keys = {"observed_symptoms", "not_verified", "proposed_chart_recipe",
                     "chosen_value_role", "semantic_guardrails", "fresh_render_checks"}
    if not isinstance(candidate, dict) or not expected_keys.issubset(candidate):
        raise ValueError("Text model did not return the required repair-planning fields")
    result = {"schema": 1, "source_sha256": validated["source_sha256"],
              "page": validated["page"], "vision_reviewer": validated["reviewer"],
              "planning_model": model, "planning_input": "verified_visual_findings_and_bindings_no_images",
              "image_count_sent_to_planner": 0, "verified_defect_count": len(validated["findings"]),
              "proposal": candidate, "auto_apply": False, "visual_approval": False,
              "required_next_steps": ["Verify the proposed change against PBIR and the semantic model",
                                      "Apply only an allowlisted repair in a disposable worktree",
                                      "Refresh, rerender, and independently reinspect the full page"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in GLM/DeepSeek text-only PBIR repair planner")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--renders", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--allow-cloud-context", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    result = plan_with_text_model(args.source, args.renders, args.diagnostic, args.output,
                                  profile=args.profile, model=args.model,
                                  allow_cloud_context=args.allow_cloud_context, timeout=args.timeout)
    print(json.dumps({"source_sha256": result["source_sha256"],
                      "model": args.model, "image_count_sent": 0,
                      "approval": False, "auto_apply": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
