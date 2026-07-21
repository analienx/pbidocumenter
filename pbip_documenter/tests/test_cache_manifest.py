"""Tests for persisted source-cache metadata."""

from datetime import datetime, timezone

from pbip_documenter.cache.manifest import Manifest, ManifestStatus


def test_source_manifest_round_trip(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    now = datetime.now(timezone.utc)
    manifest = Manifest(
        source="powerbi",
        generated_at=now,
        last_success_at=now,
        last_attempt_at=now,
        status=ManifestStatus.SUCCESS,
        freshness_threshold_hours=24,
        record_count=3,
    )

    manifest.save(path)
    loaded = Manifest.load(path)

    assert loaded is not None
    assert loaded.source == "powerbi"
    assert loaded.record_count == 3
    assert loaded.is_fresh()
