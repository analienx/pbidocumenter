"""Tests for inventory cache path construction."""

import typing

from pbip_documenter.cache.paths import CachePaths


def test_source_cache_paths_are_created_under_inventory(tmp_path: typing.Any) -> typing.Any:
    paths = CachePaths(tmp_path)

    assert paths.get_raw_pages_dir("powerbi") == tmp_path / "inventory" / "powerbi" / "raw"
    assert paths.get_curated_path("powerbi", "reports.parquet") == (
        tmp_path / "inventory" / "powerbi" / "curated" / "reports.parquet"
    )
    assert paths.get_export_path("jira", "issues.json") == (tmp_path / "inventory" / "jira" / "exports" / "issues.json")
    assert paths.get_manifest_path("jira") == tmp_path / "inventory" / "jira" / "manifest.json"

    assert paths.get_raw_pages_dir("powerbi").is_dir()
