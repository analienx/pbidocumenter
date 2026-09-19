"""Structural regression checks for the shipped Contoso PBIP showcase."""

import json
from pathlib import Path

EXAMPLE = Path(__file__).parents[2] / "examples" / "contoso-retail"
REPORT_PAGES = EXAMPLE / "Contoso Retail.Report" / "definition" / "pages"
MODEL_PROPERTIES = EXAMPLE / "Contoso Retail.SemanticModel" / "definition.pbism"
SCHEMA_URL = (
    "https://developer.microsoft.com/json-schemas/fabric/item/"
    "semanticModel/definitionProperties/1.0.0/schema.json"
)


def test_showcase_pages_and_visual_folders_are_complete() -> None:
    metadata = json.loads((REPORT_PAGES / "pages.json").read_text(encoding="utf-8"))
    page_ids = metadata["pageOrder"]
    assert len(page_ids) >= 5
    assert len(page_ids) == len(set(page_ids))
    assert {item.name for item in REPORT_PAGES.iterdir() if item.is_dir()} == set(page_ids)

    visual_count = 0
    for page_id in page_ids:
        page = REPORT_PAGES / page_id
        definition = json.loads((page / "page.json").read_text(encoding="utf-8"))
        assert definition["name"] == page_id
        visual_names: set[str] = set()
        visuals = page / "visuals"
        assert visuals.is_dir()
        for visual in visuals.iterdir():
            assert visual.is_dir(), f"Unexpected visual artifact: {visual}"
            payload = visual / "visual.json"
            assert payload.is_file(), f"Empty visual folder: {visual}"
            item = json.loads(payload.read_text(encoding="utf-8"))
            assert isinstance(item["name"], str) and item["name"]
            assert item["name"] not in visual_names
            visual_names.add(item["name"])
            visual_count += 1

    assert visual_count >= 50


def test_showcase_semantic_model_declares_schema() -> None:
    metadata = json.loads(MODEL_PROPERTIES.read_text(encoding="utf-8-sig"))
    assert metadata["$schema"] == SCHEMA_URL
    assert metadata["version"]
