"""Compare original vs optimized schema placement on four reproducible models.

Generate one *real native-DrawingML* Word page for each baseline/optimized
model, plus JSON geometry evidence for both versions. Fixture seed is fixed.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.shared import Inches

from copiloter import PbipProject, build_project_summary
from pbip_documenter.analysis import schema
from pbip_documenter.analysis.schema_layout import optimize_layout

SIZES = {"small": 6, "medium": 14, "large": 48, "very-large": 160}


def scenario(count: int, seed: int = 73) -> dict:
    rng = random.Random(seed + count)
    facts = max(1, (count + 6) // 9)
    names = [f"Fact {i+1:02d}" for i in range(facts)]
    names += [f"Dim {i+1:03d}" for i in range(count - facts)]
    tables = [{
        "name": n,
        "columns": [{"name": "Key"}, {"name": "Amount"}],
        "measures": [{"name": f"Sales_{j}"} for j in range(5)] if n.startswith("Fact") else [],
    } for n in names]
    rels: list[dict] = []
    pairs: set[tuple[str, str]] = set()

    def add(a: str, b: str) -> None:
        if a == b or ((a, b) if a < b else (b, a)) in pairs:
            return
        pairs.add((a, b) if a < b else (b, a))
        rels.append({"from_table": a, "to_table": b, "is_active": True, "cross_filtering": "single"})

    # Fact 01 is a high-degree hub; other facts connect through overlapping
    # dimensions, plus some low-density bridge and secondary relationships.
    for n in names[1:]:
        if n.startswith("Dim") and (rng.random() < 0.83 or count < 15):
            add(names[0], n)
        else:
            add(rng.choice(names[:facts]), n)
    for fact in names[1:facts]:
        add(names[0], fact)
    dim = names[facts:]
    for fact in names[1:facts]:
        for n in rng.sample(dim, min(len(dim), max(2, round(0.19 * len(dim))))):
            add(fact, n)
    for n in dim[:max(0, min(10, len(dim) // 7))]:
        add(n, dim[(dim.index(n) + 3) % len(dim)])
    return {"semantic_model": {"tables": tables, "relationships": rels}, "report": {"pages": []}}


def word_figure(destination: Path, view: dict, analysis: dict, legacy: bool) -> None:
    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Inches(11.69)
    section.page_height = Inches(8.27)
    section.left_margin = Inches(0.55)
    section.right_margin = Inches(0.55)
    section.top_margin = Inches(0.36)
    section.bottom_margin = Inches(0.32)
    doc.add_heading(("Baseline" if legacy else "Optimized") + f" relationship diagram — {destination.stem}", 2)
    orig = schema._build_layout
    try:
        if legacy:
            schema._build_layout = schema._build_layout_legacy
        schema._render_focus(doc, view, analysis, 2)
    finally:
        schema._build_layout = orig
    doc.save(str(destination))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.out_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    for name, n in [*SIZES.items(), ("contoso", 0)]:
        print(f"SIMULATING {name} ({n} tables)" if n else "ANALYZING actual Contoso PBIP", flush=True)
        summary = scenario(n) if n else build_project_summary(
            PbipProject(Path(__file__).resolve().parents[1] / "examples" / "contoso-retail")
        )
        analysis, views = schema.plan_schema_views(summary)
        assert views, name
        view = views[0]
        tm = analysis["table_map"]
        base, _, _ = schema._build_layout_legacy(view, tm)
        points = {k: (v[0] / schema._emu(1), v[1] / schema._emu(1)) for k, v in base.items()}
        roles = {t: schema._role(tm[t]) for t in view["visible"]}
        edges = [(e["from_table"], e["to_table"]) for e in view["relationships"][:24]]
        after, evidence = optimize_layout(points, edges, view["anchor"], roles)
        assert evidence["selected_cost"] <= evidence["baseline_cost"]
        # Deterministic output, fallback and geometry contract.
        again, evidence2 = optimize_layout(points, edges, view["anchor"], roles)
        assert after == again and evidence == evidence2
        report[name] = {
            "source_tables": n or len(summary["semantic_model"]["tables"]),
            "source_relationships": len(summary["semantic_model"]["relationships"]),
            "visible_tables": len(view["visible"]),
            "visible_relationships": len(edges),
            "hidden_tables": len(view["hidden"]),
            "score": evidence,
        }
        for legacy, kind in ((True, "before"), (False, "after")):
            word_figure(output / f"{name}-{kind}.docx", view, analysis, legacy=legacy)
        print("DONE",name,"cost",evidence["baseline_cost"],"->",evidence["selected_cost"],
              "crossings",evidence["baseline_metrics"]["connector_crossings"],
              "->",evidence["selected_metrics"]["connector_crossings"],flush=True)
    (output / "schema-layout-comparison.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("DONE ALL",output,flush=True)


if __name__ == "__main__":
    main()
