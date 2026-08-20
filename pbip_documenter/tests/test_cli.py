"""End-to-end checks for public CLI behavior."""

import typing
from pathlib import Path

from copiloter import PbipProject, build_project_summary
from pbip_documenter.cli import main

EXAMPLE_DIR = Path(__file__).parents[2] / "examples" / "contoso-retail"
# Temporary base-SHA refresh marker; removed immediately.


def test_generates_document_for_direct_project_path(tmp_path: Path) -> typing.Any:
    output = tmp_path / "contoso.docx"

    assert main([str(EXAMPLE_DIR), "--mode", "default", "--output", str(output)]) == 0
    assert output.is_file()
    assert output.stat().st_size > 10_000


def test_contoso_sample_models_a_star_schema() -> typing.Any:
    summary = build_project_summary(PbipProject(EXAMPLE_DIR))
    model = summary["semantic_model"]
    table_names = {table["name"] for table in model["tables"]}

    # The showcase model intentionally expands beyond the original five-table
    # star schema. Keep the core-star regression while allowing new dimensions
    # and facts to be added by the active Contoso expansion work.
    assert None not in table_names
    assert {
        "Dim Customer",
        "Dim Date",
        "Dim Product",
        "Dim Store",
        "Fact Sales",
    } <= table_names
    assert model["relationship_count"] >= 4
    assert model["total_measures"] >= 6


def test_returns_error_for_empty_directory(tmp_path: Path) -> typing.Any:
    assert main([str(tmp_path)]) == 2
