"""Visual-specific evidence and reversible, evidence-bound repair tests."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pbip_documenter.quality_gate import source_digest
from pbip_documenter.visual_quality.evidence import digest
from pbip_documenter.visual_quality.repair_actions import execute_plan, plan_scatter_to_bar
from pbip_documenter.visual_quality.visual_evidence import crop_report_visuals, verified_visuals

ROOT = Path(__file__).parents[2] / "examples" / "contoso-retail"
REPORT = ROOT / "Contoso Retail.Report"
SHOTS = ROOT / "screenshots"
VISUAL = "product-quality-growth"
PAGE = "Products_brands"


def _candidate(tmp_path: Path) -> Path:
    target = tmp_path / "Contoso Retail.Report"
    shutil.copytree(REPORT, target)
    shutil.copytree(ROOT / "Contoso Retail.SemanticModel", tmp_path / "Contoso Retail.SemanticModel")
    return target


def _diagnosis(report: Path) -> dict:
    return {"source_sha256": source_digest(report), "findings": [
        {"rule": "visual_defect", "page": PAGE, "visual_id": VISUAL,
         "check": "axis_precision", "detail": "Indistinguishable X-axis labels at the rendered size."}]}


def test_visual_crops_are_source_bound_and_resolve_to_pbir(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    for name in ["capture-manifest.json", *[f"{i:02d}-{slug}.png" for i, slug in enumerate(
            ["executive-performance", "markets-stores", "products-brands", "customers-value",
             "operations-risk"], start=1)]]:
        shutil.copy2(SHOTS / name, tmp_path / name)
    manifest = crop_report_visuals(REPORT, tmp_path)
    assert len(manifest["pages"]) == 5
    assert sum(len(p["visuals"]) for p in manifest["pages"]) == 54
    p = next(p for p in manifest["pages"] if p["id"] == PAGE)
    crops = verified_visuals(tmp_path, source_digest(REPORT), PAGE, p["image_sha256"])
    target = next(v for v in crops if v["id"] == VISUAL)
    assert target["type"] == "scatterChart"
    assert target["roles"]["Y"] == ["Fact Sales.Reporting Year GM %"]
    assert digest(tmp_path / target["crop"]) == target["crop_sha256"]
    (tmp_path / target["crop"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        verified_visuals(tmp_path, source_digest(REPORT), PAGE, p["image_sha256"])


def test_repair_requires_live_defect_and_exact_source(tmp_path: Path) -> None:
    report = _candidate(tmp_path)
    with pytest.raises(ValueError, match="visual-specific"):
        plan_scatter_to_bar(report, {"source_sha256": source_digest(report), "findings": []},
                            page_id=PAGE, visual_id=VISUAL, title="Margin by brand")
    diagnosis = _diagnosis(report)
    plan = plan_scatter_to_bar(report, diagnosis, page_id=PAGE, visual_id=VISUAL,
                               title="Gross margin by brand")
    target = report / "definition" / "pages" / PAGE / "visuals" / VISUAL / "visual.json"
    before = target.read_bytes()
    dry = execute_plan(report, plan)
    assert not dry["applied"] and target.read_bytes() == before
    done = execute_plan(report, plan, apply=True)
    assert done["applied"] and done["before_source_sha256"] != done["after_source_sha256"]
    visual = json.loads(target.read_text(encoding="utf-8"))
    assert visual["visual"]["visualType"] == "clusteredBarChart"
    state = visual["visual"]["query"]["queryState"]
    assert set(state) == {"Category", "Y", "Tooltips"}
    assert state["Y"]["projections"][0]["queryRef"] == "Fact Sales.Reporting Year GM %"
    assert state["Category"]["projections"][0]["queryRef"] == "Dim Product.Brand"
    assert {v["queryRef"] for v in state["Tooltips"]["projections"]} == {
        "Fact Sales.Reporting Year Sales YoY %", "Fact Sales.Reporting Year Sales"}
    with pytest.raises(ValueError, match="stale"):
        execute_plan(report, plan, apply=True)


def test_repair_rejects_unrecognized_visual_and_source(tmp_path: Path) -> None:
    report = _candidate(tmp_path)
    diagnosis = _diagnosis(report)
    with pytest.raises(ValueError, match="visual-specific"):
        plan_scatter_to_bar(report, diagnosis, page_id=PAGE,
                            visual_id="untrusted-visual", title="Margin by brand")
    diagnosis["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="does not match"):
        plan_scatter_to_bar(report, diagnosis, page_id=PAGE,
                            visual_id=VISUAL, title="Margin by brand")


def test_chart_fit_preserves_lower_panels_and_card_legibility(tmp_path: Path) -> None:
    from pbip_documenter.quality_gate import inspect_report
    from pbip_documenter.visual_quality.fit_layout import apply_fit_plan, plan_fit_chart

    report = _candidate(tmp_path)
    initial = _diagnosis(report)
    chart = plan_scatter_to_bar(report, initial, page_id=PAGE, visual_id=VISUAL,
                                title="Gross margin by brand")
    execute_plan(report, chart, apply=True)
    lower = report / "definition" / "pages" / PAGE / "visuals" / "product-action-list" / "visual.json"
    prior_table = lower.read_bytes()
    scroll = {"source_sha256": source_digest(report), "findings": [
        {"rule": "visual_defect", "page": PAGE, "visual_id": VISUAL,
         "check": "scrollbars_in_key_visuals", "detail": "A fifth brand is hidden behind the scrollbar."}]}
    proposal = plan_fit_chart(report, scroll, page_id=PAGE, visual_id=VISUAL)
    assert len(proposal["changes"]) == 8
    assert lower.read_bytes() == prior_table
    complete = apply_fit_plan(report, proposal, apply=True)
    assert complete["applied"] and lower.read_bytes() == prior_table
    visuals = report / "definition" / "pages" / PAGE / "visuals"
    card = json.loads((visuals / "card-00f9592e" / "visual.json").read_text())
    slicer = json.loads((visuals / "product-year" / "visual.json").read_text())
    chart = json.loads((visuals / VISUAL / "visual.json").read_text())
    assert (card["position"]["y"], card["position"]["height"]) == (104, 140)
    assert slicer["position"]["height"] == 88
    assert (chart["position"]["y"], chart["position"]["height"]) == (264, 216)
    assert inspect_report(report)["geometry_pass"]
    with pytest.raises(ValueError, match="stale"):
        apply_fit_plan(report, proposal, apply=True)
