"""Regression for crossing-aware Word relationship layouts across model sizes."""

from __future__ import annotations

from pathlib import Path

import pytest

from copiloter import PbipProject, build_project_summary
from pbip_documenter.analysis import schema
from pbip_documenter.analysis.schema_layout import optimize_layout
from scripts.schema_layout_comparison import SIZES, scenario


@pytest.mark.parametrize("size", list(SIZES))
def test_layout_improves_or_preserves_geometric_quality(size: str) -> None:
    summary = scenario(SIZES[size])
    analysis, views = schema.plan_schema_views(summary)
    assert views
    view = views[0]
    base, _, _ = schema._build_layout_legacy(view, analysis["table_map"])
    coords = {n: (x / schema._emu(1), y / schema._emu(1))
              for n, (x, y, _) in base.items()}
    roles = {n: schema._role(analysis["table_map"][n]) for n in coords}
    edges = [(r["from_table"], r["to_table"]) for r in schema._prioritized_relationships(view)]
    selected, audit = optimize_layout(coords, edges, view["anchor"], roles)
    assert audit["selected_cost"] <= audit["baseline_cost"], size
    assert audit["selected_metrics"]["node_overlaps"] == 0, size
    assert audit["selected_metrics"]["connector_box_hits"] == 0, size
    assert audit["selected_metrics"]["out_of_bounds"] == 0, size
    assert selected == optimize_layout(coords, edges, view["anchor"], roles)[0]
    if size == "medium":
        assert audit["selected_metrics"]["connector_crossings"] < audit["baseline_metrics"]["connector_crossings"]


def test_contoso_layout_reduces_connector_crossings() -> None:
    root = Path(__file__).resolve().parents[2]
    summary = build_project_summary(PbipProject(root / "examples" / "contoso-retail"))
    analysis, views = schema.plan_schema_views(summary)
    assert views
    view = views[0]
    base, _, _ = schema._build_layout_legacy(view, analysis["table_map"])
    points = {n: (x / schema._emu(1), y / schema._emu(1))
              for n, (x, y, _) in base.items()}
    roles = {n: schema._role(analysis["table_map"][n]) for n in points}
    edges = [(e["from_table"], e["to_table"]) for e in schema._prioritized_relationships(view)]
    _, score = optimize_layout(points, edges, view["anchor"], roles)
    assert score["selected_cost"] < score["baseline_cost"]
    assert score["selected_metrics"]["connector_crossings"] < score["baseline_metrics"]["connector_crossings"]
    assert score["selected_metrics"]["node_overlaps"] == 0


def test_schema_source_does_not_mutate_existing_files() -> None:
    # Fixture generation and layout are pure functions; serialization
    # never writes to a PBIP source directory.
    import hashlib

    root = Path(__file__).resolve().parents[2]
    fixture = root / "examples" / "contoso-retail"
    source = next(fixture.rglob("*.json"))
    old = hashlib.sha256(source.read_bytes()).hexdigest()
    summary = build_project_summary(PbipProject(fixture))
    analysis, views = schema.plan_schema_views(summary)
    schema._build_layout(views[0], analysis["table_map"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == old
