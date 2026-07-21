"""End-to-end checks for public CLI behavior."""

from pathlib import Path

from pbip_documenter.cli import main

EXAMPLE_DIR = Path(__file__).parents[2] / "examples" / "contoso-retail"


def test_generates_document_for_direct_project_path(tmp_path: Path) -> None:
    output = tmp_path / "contoso.docx"

    assert main([str(EXAMPLE_DIR), "--mode", "default", "--output", str(output)]) == 0
    assert output.is_file()
    assert output.stat().st_size > 10_000


def test_returns_error_for_empty_directory(tmp_path: Path) -> None:
    assert main([str(tmp_path)]) == 2
