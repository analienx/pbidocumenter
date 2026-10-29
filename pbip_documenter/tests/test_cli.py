"""End-to-end checks for public CLI behavior."""

import typing
from pathlib import Path

from copiloter import PbipProject, build_project_summary
from pbip_documenter.cli import main

EXAMPLE_DIR = Path(__file__).parents[2] / "examples" / "contoso-retail"


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



def test_default_output_is_written_under_current_directory(tmp_path: Path, monkeypatch: typing.Any) -> None:
    monkeypatch.chdir(tmp_path)
    assert main([str(EXAMPLE_DIR), "--mode", "default"]) == 0
    documents = list((tmp_path / "Exported Documents").rglob("*.docx"))
    assert len(documents) == 1
    assert documents[0].stat().st_size > 10_000


def test_multi_project_explicit_filename_fails_before_overwrite(tmp_path: Path, monkeypatch: typing.Any) -> None:
    from pbip_documenter import cli

    project_root = tmp_path / "projects"
    (project_root / "First").mkdir(parents=True)
    (project_root / "Second").mkdir()

    class FakeProject:
        def __init__(self, path: Path) -> None:
            self.name = path.name
            self.is_valid = self.name in {"First", "Second"}

    monkeypatch.setattr(cli, "PbipProject", FakeProject)
    output = tmp_path / "existing.docx"
    original = b"preserve-user-file"
    output.write_bytes(original)

    assert cli.main([str(project_root), "--output", str(output)]) == 2
    assert output.read_bytes() == original



def test_generated_scope_does_not_invent_business_exclusions(tmp_path: Path) -> None:
    from docx import Document

    output = tmp_path / "scope.docx"
    assert main([str(EXAMPLE_DIR), "--output", str(output)]) == 0
    doc = Document(str(output))
    content = "\n".join(p.text for p in doc.paragraphs)

    assert "These exclusions cannot be established from PBIP source alone." in content
    assert "No budget/forecast comparisons" not in content
    assert "No real-time or streaming refresh" not in content

    from docx.oxml.ns import qn

    linked = {
        anchor
        for node in doc.element.body.xpath(".//w:hyperlink")
        if (anchor := node.get(qn("w:anchor"))) and anchor.startswith("toc_")
    }
    targets = {node.get(qn("w:name")) for node in doc.element.body.xpath(".//w:bookmarkStart")}
    required = {
        "toc_control", "toc_scope", "toc_operations", "toc_technical", "toc_support", "toc_revision"
    }
    assert required <= targets
    if linked:
        assert required <= linked
