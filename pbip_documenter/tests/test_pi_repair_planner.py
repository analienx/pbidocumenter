"""Text-only GLM/DeepSeek planner must never impersonate image review or apply fixes."""
import json
from pathlib import Path

import pytest

from pbip_documenter.visual_quality.pi_repair_planner import plan_with_text_model

ROOT = Path(__file__).parents[2] / "examples" / "contoso-retail"
REPORT = ROOT / "Contoso Retail.Report"
RENDERS = ROOT / "screenshots"


def test_text_planner_requires_opt_in(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow-cloud-context"):
        plan_with_text_model(REPORT, RENDERS, tmp_path / "no.json", tmp_path / "out.json",
                             profile=tmp_path, model="cline/z-ai/glm-5.3-flash",
                             allow_cloud_context=False)


def test_text_planner_rejects_non_bound_diagnosis(tmp_path: Path) -> None:
    diagnostic = tmp_path / "diagnostic.json"
    diagnostic.write_text(json.dumps({"schema": 2, "source_sha256": "stale"}), encoding="utf-8")
    with pytest.raises(ValueError, match="exact-source"):
        plan_with_text_model(REPORT, RENDERS, diagnostic, tmp_path / "out.json",
                             profile=tmp_path, model="cline-pass/deepseek-v4.1-flash",
                             allow_cloud_context=True)


def test_model_output_is_non_executable_proposal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pbip_documenter.visual_quality import pi_repair_planner

    # Fixed synthetic handoff: the model receives source-bound descriptions, not raw PNGs.
    monkeypatch.setattr(pi_repair_planner, "build_handoff", lambda *_args: {
        "source_sha256": "abc", "page": "Products_brands", "reviewer": {"id": "vision-a"},
        "findings": [{"check": "axis_precision", "detail": "Two X-axis ticks display 10%.",
                      "page": "Products_brands", "visual_id": "chart-a", "repair_candidate": "inspect_axis"}]})
    seen = {}

    def responder(payload: dict) -> str:
        seen.update(payload)
        return json.dumps({"observed_symptoms": [], "not_verified": ["underlying DAX"],
                           "proposed_chart_recipe": {}, "chosen_value_role": "deferred",
                           "semantic_guardrails": [], "fresh_render_checks": []})

    monkeypatch.setattr(pi_repair_planner, "invoke_pi", responder)
    output = tmp_path / "proposal.json"
    result = plan_with_text_model(REPORT, RENDERS, tmp_path / "unused.json", output,
                                  profile=tmp_path, model="cline/z-ai/glm-5.3-flash",
                                  allow_cloud_context=True)
    assert seen["task"] == "repair_planning" and seen["images"] == []
    assert result["image_count_sent_to_planner"] == 0
    assert not result["auto_apply"] and not result["visual_approval"]
    assert output.is_file()
