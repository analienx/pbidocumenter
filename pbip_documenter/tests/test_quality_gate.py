"""Executable geometry and screenshot-provenance regression checks."""

import json
import shutil
from pathlib import Path

from pbip_documenter.quality_gate import inspect_report, source_digest

ROOT = Path(__file__).parents[2] / "examples" / "contoso-retail"
REPORT = ROOT / "Contoso Retail.Report"


def test_contoso_canvas_passes_geometry_but_is_not_release_approved() -> None:
    result = inspect_report(REPORT)
    assert result["geometry_pass"], result["findings"]
    assert len(result["pages"]) == 5
    assert sum(item["visuals"] for item in result["pages"]) == 54
    assert not result["captures_pass"] and not result["release_ready"]
    assert result["source_sha256"] == source_digest(REPORT)


def test_misaligned_cards_fail(tmp_path: Path) -> None:
    clone = tmp_path / REPORT.name
    shutil.copytree(REPORT / "definition" / "pages", clone / "definition" / "pages")
    target = clone / "definition" / "pages" / "Executive_performance" / "visuals" / "card-096ca6e7" / "visual.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["position"]["y"] -= 32
    target.write_text(json.dumps(payload), encoding="utf-8")
    finding = inspect_report(clone)
    assert not finding["geometry_pass"]
    assert any(f["rule"] == "card_row_misaligned" for f in finding["findings"])


def test_unbound_screenshots_are_not_accepted(tmp_path: Path) -> None:
    result = inspect_report(REPORT, tmp_path)
    assert result["geometry_pass"]
    assert not result["captures_pass"] and not result["release_ready"]
    assert any(f["rule"] == "missing_or_stale_capture_manifest" for f in result["findings"])


def test_source_change_invalidates_existing_screenshots(tmp_path: Path) -> None:
    clone = tmp_path / REPORT.name
    shutil.copytree(REPORT, clone)
    shutil.copytree(ROOT / "Contoso Retail.SemanticModel", tmp_path / "Contoso Retail.SemanticModel")
    assert source_digest(clone) == source_digest(REPORT)
    original = ROOT / "screenshots"
    assert inspect_report(REPORT, original)["captures_pass"]
    target = clone / "definition" / "pages" / "Executive_performance" / "visuals" / "card-096ca6e7" / "visual.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["position"]["x"] += 1
    target.write_text(json.dumps(payload), encoding="utf-8")
    finding = inspect_report(clone, original)
    assert finding["geometry_pass"]
    assert not finding["captures_pass"]
    assert any(f["rule"] == "missing_or_stale_capture_manifest" for f in finding["findings"])


def test_image_change_invalidates_capture_manifest(tmp_path: Path) -> None:
    shots = tmp_path / "screenshots"
    shutil.copytree(ROOT / "screenshots", shots)
    image = shots / "03-products-brands.png"
    image.write_bytes(image.read_bytes() + b"trailing-untrusted-data")
    finding = inspect_report(REPORT, shots)
    assert not finding["captures_pass"]
    assert any(f["rule"] == "stale_or_unbound_capture" for f in finding["findings"])


def test_populated_images_do_not_override_open_visual_review() -> None:
    result = inspect_report(REPORT, ROOT / "screenshots")
    assert result["geometry_pass"] and result["captures_pass"]
    assert not result["visual_review_pass"] and not result["release_ready"]
    assert len(result["visual_review"]) == 5
    assert all(item["status"] == "needs_changes" and item["issues"]
               for item in result["visual_review"])
