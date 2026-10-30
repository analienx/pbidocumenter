"""Adversarial hardening coverage for native Word semantic relationship layouts."""

from __future__ import annotations

import itertools
import random
from pathlib import Path

import pytest

from pbip_documenter.analysis import schema
from pbip_documenter.analysis.schema_layout import _slots, layout_metrics, optimize_layout
from scripts.schema_layout_comparison import scenario, word_figure


def test_long_unbroken_identifiers_fit_native_word_box() -> None:
    names = (
        "Fact_ExtremelyLongCustomerTransactionsWithoutAnyNaturalWordBreak",
        "全部没有空格的连续表名非常长非常长",
        "Dim_Long_Name_Using_Several_Underscore_Sections_With_No_Breaks",
        "X" * 1500,
    )
    for name in names:
        for width in (14, 18):
            lines = schema._wrap(name, width)
            assert 1 <= len(lines) <= 2
            assert all(len(line) <= width for line in lines)
            assert lines[1].endswith("...") if len(name.replace("_", " ")) > width * 2 else True


def test_relationship_order_invariant_when_priorities_tie() -> None:
    # 36 relationships exceed the 24-line cap. Input order must not alter
    # which relationships the user sees, or the graph fed to optimization.
    edges = [
        {
            "from_table": "Fact Sales",
            "to_table": f"Dim {i:02}",
            "from_column": "Id",
            "to_column": "SalesId",
            "name": f"Sales_to_Dim_{i:02}",
            "is_active": i % 2 == 0,
        }
        for i in range(36)
    ]
    view = {"anchor": "Fact Sales", "relationships": edges}
    expected = schema._prioritized_relationships(view)
    assert len(expected) == 24
    for seed in (0, 1, 2, 83, 131):
        shuffled = list(edges)
        random.Random(seed).shuffle(shuffled)
        assert schema._prioritized_relationships({**view, "relationships": shuffled}) == expected


def test_component_order_independent_of_source_table_order() -> None:
    tables: list[dict[str, object]] = [
        {"name": n, "columns": [], "measures": []}
        for n in ("Fact A", "Dim A", "Fact B", "Dim B")
    ]
    rels = [
        {"from_table": "Fact A", "to_table": "Dim A"},
        {"from_table": "Fact B", "to_table": "Dim B"},
    ]
    original = {"semantic_model": {"tables": tables, "relationships": rels}}
    inverted = {"semantic_model": {"tables": list(reversed(tables)), "relationships": list(reversed(rels))}}
    a, views_a = schema.plan_schema_views(original)
    b, views_b = schema.plan_schema_views(inverted)
    assert [v["anchor"] for v in views_a] == [v["anchor"] for v in views_b]
    assert [c["nodes"] for c in a["components"]] == [c["nodes"] for c in b["components"]]


@pytest.mark.parametrize("nodes,dims", [(1, 0), (5, 0), (5, 5), (12, 6), (19, 0), (19, 10), (19, 19)])
def test_slot_coverage_and_page_safety_for_role_extremes(nodes: int, dims: int) -> None:
    slots = _slots(dims, nodes - dims)
    assert len(slots) == nodes
    points = {"Fact Anchor": (5.1, 2.65)}
    roles = {"Fact Anchor": "fact"}
    for i, pos in enumerate(slots):
        name = f"Table {i}"
        points[name] = pos
        roles[name] = "dim" if i < dims else "fact"
    metrics = layout_metrics(points, [], "Fact Anchor", roles)
    assert metrics["out_of_bounds"] == 0
    assert metrics["node_overlaps"] == 0


def test_duplicate_and_reversed_relationships_do_not_inflate_geometry() -> None:
    points = {"Fact A": (5.1, 2.65), "Dim B": (1.1, 2.65)}
    roles = {"Fact A": "fact", "Dim B": "dim"}
    once = layout_metrics(points, [("Fact A", "Dim B")], "Fact A", roles)
    repeats = layout_metrics(
        points,
        [("Fact A", "Dim B"), ("Dim B", "Fact A"), ("Fact A", "Dim B")],
        "Fact A",
        roles,
    )
    assert repeats == once


def test_comparison_render_avoids_global_monkeypatch(tmp_path: Path) -> None:
    summary = scenario(6)
    analysis, views = schema.plan_schema_views(summary)
    original = schema._build_layout
    before = tmp_path / "before.docx"
    after = tmp_path / "after.docx"
    word_figure(before, views[0], analysis, legacy=True)
    assert schema._build_layout is original
    word_figure(after, views[0], analysis, legacy=False)
    assert schema._build_layout is original
    assert before.stat().st_size > 2000
    assert after.stat().st_size > 2000


def test_optimizer_stable_under_input_reordering() -> None:
    nodes = {"Fact Hub": (5.1, 2.65)}
    roles = {"Fact Hub": "fact"}
    for i in range(9):
        n = f"Dim {i:02}"
        nodes[n] = (1.15 if i % 2 else 9.05, 0.9 + i * 0.43)
        roles[n] = "dim"
    edges = [("Fact Hub", n) for n in nodes if n != "Fact Hub"]
    edges.extend(itertools.combinations((n for n in nodes if n != "Fact Hub"), 2))
    a, ea = optimize_layout(nodes, edges, "Fact Hub", roles)
    b, eb = optimize_layout(dict(reversed(list(nodes.items()))), list(reversed(edges)), "Fact Hub", roles)
    assert a == b
    assert ea == eb
