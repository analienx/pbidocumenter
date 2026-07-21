"""Power BI refresh service with raw persistence and cache preservation."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from pbip_documenter.cache.atomic_write import atomic_write_json, atomic_write_parquet
from pbip_documenter.cache.manifest import Manifest, ManifestStatus
from pbip_documenter.cache.paths import CachePaths
from pbip_documenter.inventory.powerbi.auth import PowerBIAuth
from pbip_documenter.inventory.powerbi.client import PowerBIClient
from pbip_documenter.inventory.powerbi.normalize import PowerBINormalizer

logger = logging.getLogger(__name__)


class PowerBIService:
    """
    Service for refreshing Power BI inventory cache.
    Handles raw page persistence, normalization, export, and manifest.
    Preserves last-known-good cache on failure.
    """

    SOURCE_NAME = "powerbi"

    def __init__(
        self,
        auth: PowerBIAuth,
        cache_paths: CachePaths,
        freshness_threshold_hours: int = 24,
    ):
        self.auth = auth
        self.cache_paths = cache_paths
        self.client = PowerBIClient(auth)
        self.normalizer = PowerBINormalizer()
        self.freshness_threshold_hours = freshness_threshold_hours
        self._failed = False
        self._previous_cache_dir: Path | None = None

    def _backup_existing_cache(self) -> Path | None:
        """Backup existing cache before refresh."""
        source_dir = self.cache_paths.get_source_dir(self.SOURCE_NAME)
        if not source_dir.exists():
            return None

        backup_dir = source_dir.with_suffix(".backup")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        shutil.copytree(source_dir, backup_dir)
        logger.info(f"Backed up existing cache to {backup_dir}")
        return backup_dir

    def _restore_backup(self, backup_dir: Path) -> None:
        """Restore backup on failure."""
        source_dir = self.cache_paths.get_source_dir(self.SOURCE_NAME)
        logger.warning(f"Restoring cache from {backup_dir}")
        if source_dir.exists():
            shutil.rmtree(source_dir)
        shutil.copytree(backup_dir, source_dir)
        logger.info("Cache restored successfully")

    def _cleanup_backup(self, backup_dir: Path | None) -> None:
        """Remove backup after successful refresh."""
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)
            logger.info(f"Cleaned up backup: {backup_dir}")

    def _save_raw_page(
        self,
        data: list[dict[str, Any]],
        page_number: int,
        endpoint: str,
    ) -> Path:
        """Save raw API response page."""
        raw_dir = self.cache_paths.get_raw_pages_dir(self.SOURCE_NAME)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{endpoint.replace('/', '_')}_page{page_number:04d}_{timestamp}.json"
        filepath = raw_dir / filename

        atomic_write_json(filepath, {"data": data, "timestamp": timestamp})
        logger.debug(f"Saved raw page: {filepath}")
        return filepath

    def _save_curated_export(self, df: pd.DataFrame) -> Path:
        """Save normalized DataFrame to parquet."""
        curated_path = self.cache_paths.get_curated_path(self.SOURCE_NAME, "reports.parquet")
        atomic_write_parquet(curated_path, df)
        logger.info(f"Saved curated data: {curated_path} ({len(df)} records)")
        return curated_path

    def _save_json_export(
        self,
        data: Any,
        filename: str,
    ) -> Path:
        """Save JSON export."""
        export_path = self.cache_paths.get_export_path(self.SOURCE_NAME, filename)
        atomic_write_json(export_path, data)
        return export_path

    def _write_manifest(
        self,
        status: ManifestStatus,
        record_count: int,
        error_summary: str | None = None,
    ) -> Path:
        """Write manifest file."""
        now = datetime.now(timezone.utc)
        manifest_path = self.cache_paths.get_manifest_path(self.SOURCE_NAME)

        # Load existing to preserve last_success_at on failure
        existing = Manifest.load(manifest_path)
        last_success = existing.last_success_at if existing else None

        if status == ManifestStatus.SUCCESS:
            last_success = now

        manifest = Manifest(
            source=self.SOURCE_NAME,
            generated_at=now,
            last_success_at=last_success,
            last_attempt_at=now,
            status=status,
            freshness_threshold_hours=self.freshness_threshold_hours,
            record_count=record_count,
            error_summary=error_summary,
        )
        manifest.save(manifest_path)
        logger.info(f"Wrote manifest: {manifest_path} (status={status.value})")
        return manifest_path

    def refresh(self, force: bool = False) -> dict[str, Any]:
        """
        Execute full Power BI refresh pipeline.

        Returns:
            Dict with status, record counts, file paths.
        """
        result = {
            "source": self.SOURCE_NAME,
            "force": force,
            "success": False,
            "records_fetched": 0,
            "records_normalized": 0,
            "files_created": [],
            "manifest_path": None,
            "error": None,
        }

        backup_dir = None
        try:
            # Step 1: Backup existing cache
            backup_dir = self._backup_existing_cache()

            # Step 2: Fetch all data (raw page persistence happens in client callbacks if needed)
            logger.info("Starting Power BI inventory refresh")

            raw_reports = self.client.get_reports()
            self._save_raw_page(raw_reports, 0, "reports")
            result["records_fetched"] = len(raw_reports)

            raw_groups = self.client.get_groups()
            self._save_raw_page(raw_groups, 0, "groups")

            raw_apps = self.client.get_apps()
            self._save_raw_page(raw_apps, 0, "apps")

            # Step 3: Normalize
            df = self.normalizer.normalize_reports(raw_reports, raw_groups, raw_apps)
            result["records_normalized"] = len(df)

            # Step 4: Save curated export
            curated_path = self._save_curated_export(df)
            result["files_created"].append(str(curated_path))

            # Step 5: Save JSON exports
            export_reports_path = self._save_json_export(raw_reports, "reports_raw.json")
            result["files_created"].append(str(export_reports_path))

            export_groups_path = self._save_json_export(raw_groups, "groups_raw.json")
            result["files_created"].append(str(export_groups_path))

            export_apps_path = self._save_json_export(raw_apps, "apps_raw.json")
            result["files_created"].append(str(export_apps_path))

            # Step 6: Write manifest
            manifest_path = self._write_manifest(
                status=ManifestStatus.SUCCESS,
                record_count=len(df),
            )
            result["manifest_path"] = str(manifest_path)
            result["success"] = True

            # Cleanup backup on success
            self._cleanup_backup(backup_dir)

        except Exception as e:
            logger.exception("Power BI refresh failed")
            result["error"] = str(e)

            # Restore backup if available
            if backup_dir:
                try:
                    self._restore_backup(backup_dir)
                except Exception as restore_error:
                    logger.error(f"Failed to restore backup: {restore_error}")
                    result["error"] += f" | Restore error: {restore_error}"
            else:
                # No backup to restore, write failure manifest
                manifest_path = self._write_manifest(
                    status=ManifestStatus.FAILED,
                    record_count=0,
                    error_summary=str(e)[:500],
                )
                result["manifest_path"] = str(manifest_path)

        return result

    def get_status(self) -> Manifest | None:
        """Get current cache status."""
        manifest_path = self.cache_paths.get_manifest_path(self.SOURCE_NAME)
        return Manifest.load(manifest_path)
