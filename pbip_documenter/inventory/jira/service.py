"""Jira refresh service with raw persistence and cache preservation."""

import logging
import shutil
import typing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from pbip_documenter.cache.atomic_write import atomic_write_json, atomic_write_parquet
from pbip_documenter.cache.manifest import Manifest, ManifestStatus
from pbip_documenter.cache.paths import CachePaths
from pbip_documenter.inventory.jira.auth import JiraAuth
from pbip_documenter.inventory.jira.client import JiraClient
from pbip_documenter.inventory.jira.normalize import JiraNormalizer

logger = logging.getLogger(__name__)


class JiraService:
    """
    Service for refreshing Jira inventory cache.
    Handles raw page persistence, normalization, export, and manifest.
    Preserves last-known-good cache on failure.
    """

    SOURCE_NAME = "jira"

    def __init__(
        self: typing.Any,
        auth: JiraAuth,
        cache_paths: CachePaths,
        freshness_threshold_hours: int = 24,
        jql: str | None = None,
        fields: list[str] | None = None,
    ) -> None:
        self.auth = auth
        self.cache_paths = cache_paths
        self.client = JiraClient(auth)
        self.normalizer = JiraNormalizer()
        self.freshness_threshold_hours = freshness_threshold_hours
        self.jql = jql
        self.fields = fields
        self._failed = False
        self._previous_cache_dir: Path | None = None

    def _backup_existing_cache(self: typing.Any) -> typing.Any:
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

    def _restore_backup(self: typing.Any, backup_dir: Path) -> typing.Any:
        """Restore backup on failure."""
        source_dir = self.cache_paths.get_source_dir(self.SOURCE_NAME)
        logger.warning(f"Restoring cache from {backup_dir}")
        if source_dir.exists():
            shutil.rmtree(source_dir)
        shutil.copytree(backup_dir, source_dir)
        logger.info("Cache restored successfully")

    def _cleanup_backup(self: typing.Any, backup_dir: Path | None) -> typing.Any:
        """Remove backup after successful refresh."""
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)
            logger.info(f"Cleaned up backup: {backup_dir}")

    def _save_raw_page(
        self: typing.Any,
        data: list[dict[str, Any]],
        page_number: int,
        endpoint: str,
    ) -> typing.Any:
        """Save raw API response page."""
        raw_dir = self.cache_paths.get_raw_pages_dir(self.SOURCE_NAME)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{endpoint}_page{page_number:04d}_{timestamp}.json"
        filepath = raw_dir / filename

        atomic_write_json(filepath, {"data": data, "timestamp": timestamp})
        logger.debug(f"Saved raw page: {filepath}")
        return filepath

    def _save_curated_export(self: typing.Any, df: pd.DataFrame) -> typing.Any:
        """Save normalized DataFrame to parquet."""
        curated_path = self.cache_paths.get_curated_path(self.SOURCE_NAME, "issues.parquet")
        atomic_write_parquet(curated_path, df)
        logger.info(f"Saved curated data: {curated_path} ({len(df)} records)")
        return curated_path

    def _save_json_export(
        self: typing.Any,
        data: Any,
        filename: str,
    ) -> typing.Any:
        """Save JSON export."""
        export_path = self.cache_paths.get_export_path(self.SOURCE_NAME, filename)
        atomic_write_json(export_path, data)
        return export_path

    def _write_manifest(
        self: typing.Any,
        status: ManifestStatus,
        record_count: int,
        error_summary: str | None = None,
    ) -> typing.Any:
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

    def refresh(self: typing.Any, force: bool = False) -> typing.Any:
        """
        Execute full Jira refresh pipeline.

        Returns:
            Dict with status, record counts, file paths.
        """
        result: dict[typing.Any, typing.Any] = {
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

            # Step 2: Fetch all issues
            logger.info("Starting Jira inventory refresh")

            raw_issues = self.client.search_issues(
                jql=self.jql,
                fields=self.fields,
            )
            self._save_raw_page(raw_issues, 0, "issues")
            result["records_fetched"] = len(raw_issues)

            # Step 3: Normalize
            df = self.normalizer.normalize_issues(raw_issues)
            result["records_normalized"] = len(df)

            # Step 4: Save curated export
            curated_path = self._save_curated_export(df)
            result["files_created"].append(str(curated_path))

            # Step 5: Save JSON export
            export_path = self._save_json_export(raw_issues, "issues_raw.json")
            result["files_created"].append(str(export_path))

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
            logger.exception("Jira refresh failed")
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

    def get_status(self: typing.Any) -> typing.Any:
        """Get current cache status."""
        manifest_path = self.cache_paths.get_manifest_path(self.SOURCE_NAME)
        return Manifest.load(manifest_path)
