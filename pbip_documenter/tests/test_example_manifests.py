"""Example PBIP manifests must carry the Fabric $schema (pbir requires it).

Note: Power BI Desktop strips $schema when it saves definition.pbism
(verified: a save of a file that had $schema wrote it back without).
Re-apply before committing; this test guards the committed state.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PBISM_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel"
    "/definitionProperties/1.0.0/schema.json"
)


def test_example_pbism_files_declare_schema() -> None:
    pbism_files = sorted(REPO_ROOT.joinpath("examples").rglob("*.pbism"))
    assert pbism_files, "No example *.pbism files found"
    for path in pbism_files:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        assert manifest.get("$schema") == PBISM_SCHEMA, f"{path}: missing $schema"
        assert manifest.get("version"), f"{path}: missing version"
