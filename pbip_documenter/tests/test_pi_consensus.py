"""Independent model comparison is diagnostic; disagreement requires adjudication."""
import copy
from pathlib import Path

import pytest

from pbip_documenter.visual_quality.consensus import compare_diagnostics
from pbip_documenter.visual_quality.runner import request

ROOT = Path(__file__).parents[2] / "examples" / "contoso-retail"


def _review_pair():
    request_data = request("report", ROOT / "Contoso Retail.Report",
                           ROOT / "screenshots", "repairer")
    page = request_data["pages"][2]
    base = {"schema": 2, "scope": "diagnostic_page_only", "policy_version": request_data["policy_version"],
            "surface": "report", "source_sha256": request_data["source_sha256"],
            "fixer_id": "repairer", "reviewer": {"id": "vision-a", "role": "independent_visual_reviewer",
                                                  "model": "cline-pass/qwen3.7-plus"},
            "pages": [{"id": page["id"], "image_sha256": page["image_sha256"],
                       "observations": [{"id": check["id"], "status": "pass",
                                         "reason": "This observation was checked on the actual source-bound image."}
                                        for check in page["observations"]]}]}
    alternate = copy.deepcopy(base)
    alternate["reviewer"].update(id="vision-b", model="cline-pass/minimax-m3")
    inventory = {"id": page["id"], "sha256": page["image_sha256"],
                 "visual_inventory": page["visual_inventory"]}
    return base, alternate, inventory


def test_conflicting_vision_models_require_adjudication() -> None:
    first, second, page = _review_pair()
    second["pages"][0]["observations"][0].update(
        status="fail", severity="medium", visual_id="page", region=[0.1, 0.1, 0.9, 0.9],
        proposed_fix="Remove the redundant technical axis title from the visual.",
        reason="An unnecessary technical measure label is clearly visible on the horizontal axis.")
    comparison = compare_diagnostics(first, second, page)
    assert not comparison["can_auto_approve"]
    assert comparison["findings"][0]["rule"] == "needs_adjudication"


def test_same_model_or_stale_image_cannot_be_called_independent() -> None:
    first, second, page = _review_pair()
    second["reviewer"]["model"] = first["reviewer"]["model"]
    with pytest.raises(ValueError, match="different reviewer"):
        compare_diagnostics(first, second, page)
    second["reviewer"]["model"] = "cline-pass/minimax-m3"
    second["pages"][0]["image_sha256"] = "stale"
    with pytest.raises(ValueError, match="same rendered page"):
        compare_diagnostics(first, second, page)
