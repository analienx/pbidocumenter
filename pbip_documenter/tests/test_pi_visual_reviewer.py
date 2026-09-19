"""Pi vision transport and provenance tests; no live model or OAuth required."""
import json
from pathlib import Path

import pytest

from pbip_documenter.visual_quality.evidence import verify_review
from pbip_documenter.visual_quality.pi_reviewer import parse_model_json, review_with_pi
from pbip_documenter.visual_quality.runner import request

ROOT = Path(__file__).parents[2] / "examples" / "contoso-retail"
REPORT = ROOT / "Contoso Retail.Report"
RENDERS = ROOT / "screenshots"


def test_parse_model_json_only_one_object() -> None:
    assert parse_model_json('```json\n{"observations": []}\n```') == {"observations": []}
    assert parse_model_json('{"observations": []}') == {"observations": []}
    with pytest.raises(ValueError):
        parse_model_json('Explanation: {"observations": []}')
    with pytest.raises(ValueError):
        parse_model_json('{"other": []}')


def test_pi_review_cloud_upload_requires_opt_in(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="allow-cloud-images"):
        review_with_pi(REPORT, tmp_path / "missing.json", RENDERS, tmp_path / "review.json",
                       profile=tmp_path, model="cline-pass/qwen3.7-plus", reviewer_id="reviewer",
                       allow_cloud_images=False)


def test_pi_review_rejects_stale_source_without_contacting_provider(tmp_path: Path) -> None:
    stale = request("report", REPORT, RENDERS, "fixer")
    stale["source_sha256"] = "stale"
    path = tmp_path / "request.json"
    path.write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        review_with_pi(REPORT, path, RENDERS, tmp_path / "review.json", profile=tmp_path,
                       model="cline-pass/qwen3.7-plus", reviewer_id="reviewer", allow_cloud_images=True)


def test_single_page_review_is_not_full_report_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pbip_documenter.visual_quality import pi_reviewer

    template = request("report", REPORT, RENDERS, "fixer")
    path = tmp_path / "request.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    expected = template["pages"][2]
    answers = [{"id": item["id"], "status": "pass",
                "reason": "This specific observation was checked against the rendered page image."}
               for item in expected["observations"]]
    monkeypatch.setattr(pi_reviewer, "invoke_pi", lambda *_args, **_kwargs: json.dumps({"observations": answers}))
    output = tmp_path / "diagnostic.json"
    outcome = review_with_pi(REPORT, path, RENDERS, output, profile=tmp_path,
                             model="cline-pass/qwen3.7-plus", reviewer_id="separate-reviewer",
                             allow_cloud_images=True, page_id="Products_brands", timeout=60)
    assert outcome["schema"] == 2 and outcome["scope"] == "diagnostic_page_only"
    assert len(outcome["pages"]) == 1 and output.is_file()
    full_pages = [{"id": p["id"], "sha256": p["image_sha256"],
                   "visual_inventory": p["visual_inventory"]} for p in template["pages"]]
    issues = verify_review("report", template["source_sha256"], full_pages, outcome, "fixer")
    assert any(i["rule"] == "review_policy_or_source_mismatch" for i in issues)


def test_same_reviewer_and_fixer_is_rejected(tmp_path: Path) -> None:
    payload = request("report", REPORT, RENDERS, "same-person")
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="independent reviewer"):
        review_with_pi(REPORT, path, RENDERS, tmp_path / "review.json", profile=tmp_path,
                       model="cline-pass/qwen3.7-plus", reviewer_id="same-person", allow_cloud_images=True)
