"""The synthetic Contoso PBIP must open with usable data, not empty visuals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2] / "examples" / "contoso-retail"
MODEL = ROOT / "Contoso Retail.SemanticModel"
CACHE = MODEL / ".pbi" / "cache.abf"
MANIFEST = ROOT / "sample-model-cache-manifest.json"


def test_synthetic_model_cache_matches_semantic_revision() -> None:
    record = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert record["schema"] == 1 and record["fixture"] == "Contoso Retail synthetic demo"
    assert CACHE.is_file() and 100_000 < CACHE.stat().st_size < 2_000_000
    assert record["cache_bytes"] == CACHE.stat().st_size
    assert hashlib.sha256(CACHE.read_bytes()).hexdigest() == record["cache_sha256"]
    digest = hashlib.sha256()
    for path in sorted(MODEL.rglob("*")):
        if path.is_file() and ".pbi" not in path.parts and path.suffix.lower() in {".json", ".tmdl", ".pbism"}:
            digest.update(path.relative_to(MODEL).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    assert digest.hexdigest() == record["source_sha256"], "Regenerate cache after changing sample model"
    assert record["imported_tables"] == len(list((MODEL / "definition" / "tables").glob("*.tmdl")))
