"""Public operational commands for inventory refresh and status."""

import logging
import typing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pbip_documenter.cache.manifest import Manifest, ManifestStatus
from pbip_documenter.cache.paths import CachePaths
from pbip_documenter.inventory.config import InventoryConfig
from pbip_documenter.inventory.jira.auth import JiraAuth
from pbip_documenter.inventory.jira.service import JiraService
from pbip_documenter.inventory.powerbi.auth import PowerBIAuth
from pbip_documenter.inventory.powerbi.service import PowerBIService

logger = logging.getLogger(__name__)


@dataclass
class SourceStatus:
    """Status information for a single source."""

    source: str
    available: bool
    is_fresh: bool
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    record_count: int
    error_summary: str | None
    manifest_path: Path | None


@dataclass
class CombinedStatus:
    """Combined status for all sources."""

    timestamp: datetime
    sources: list[SourceStatus]
    overall_ready: bool


def _get_source_status(cache_paths: CachePaths, source: str) -> typing.Any:
    """Get status for a single source from its manifest."""
    manifest_path = cache_paths.get_manifest_path(source)
    manifest = Manifest.load(manifest_path)

    if not manifest:
        return SourceStatus(
            source=source,
            available=False,
            is_fresh=False,
            last_success_at=None,
            last_attempt_at=None,
            record_count=0,
            error_summary="No manifest found",
            manifest_path=manifest_path if manifest_path.exists() else None,
        )

    return SourceStatus(
        source=source,
        available=manifest.status == ManifestStatus.SUCCESS,
        is_fresh=manifest.is_fresh(),
        last_success_at=manifest.last_success_at,
        last_attempt_at=manifest.last_attempt_at,
        record_count=manifest.record_count,
        error_summary=manifest.error_summary,
        manifest_path=manifest_path,
    )


def status(config: InventoryConfig | None = None) -> typing.Any:
    """
    Get combined status of all inventory sources.

    Args:
        config: Inventory configuration. Uses env defaults if not provided.

    Returns:
        CombinedStatus with all source statuses and overall readiness.
    """
    if config is None:
        config = InventoryConfig.from_env()

    cache_paths = CachePaths(config.cache_root)

    sources: list[typing.Any] = [
        _get_source_status(cache_paths, "powerbi"),
        _get_source_status(cache_paths, "jira"),
    ]

    overall_ready = all(s.available and s.is_fresh for s in sources)

    return CombinedStatus(
        timestamp=datetime.now(timezone.utc),
        sources=sources,
        overall_ready=overall_ready,
    )


def _format_status_result(result: dict[str, Any]) -> typing.Any:
    """Normalize refresh result for consistent output."""
    return {
        "source": result.get("source", "unknown"),
        "success": result.get("success", False),
        "records_fetched": result.get("records_fetched", 0),
        "records_normalized": result.get("records_normalized", 0),
        "files_created_count": len(result.get("files_created", [])),
        "error": result.get("error"),
    }


def refreshPbi(
    force: bool = False,
    config: InventoryConfig | None = None,
) -> typing.Any:
    """
    Refresh Power BI inventory cache.

    Args:
        force: Force refresh even if cache is fresh.
        config: Inventory configuration. Uses env defaults if not provided.

    Returns:
        Dict with refresh result summary.
    """
    if config is None:
        config = InventoryConfig.from_env()

    auth = PowerBIAuth(
        key_vault_url=config.key_vault_url,
        tenant_id=config.pbi_tenant_id,
        client_id=config.pbi_client_id,
        secret_name=config.pbi_secret_name,
    )

    cache_paths = CachePaths(config.cache_root)
    service = PowerBIService(
        auth=auth,
        cache_paths=cache_paths,
        freshness_threshold_hours=config.freshness_threshold_hours,
    )

    result = service.refresh(force=force)
    logger.info(f"Power BI refresh complete: success={result['success']}")
    return _format_status_result(result)


def refreshJira(
    force: bool = False,
    config: InventoryConfig | None = None,
) -> typing.Any:
    """
    Refresh Jira inventory cache.

    Args:
        force: Force refresh even if cache is fresh.
        config: Inventory configuration. Uses env defaults if not provided.

    Returns:
        Dict with refresh result summary.
    """
    if config is None:
        config = InventoryConfig.from_env()

    auth = JiraAuth(
        key_vault_url=config.key_vault_url,
        secret_name=config.jira_secret_name,
        email=config.jira_user,
        base_url=config.jira_base_url,
    )

    cache_paths = CachePaths(config.cache_root)

    # Build JQL for project
    jql = f"project = {config.jira_project_key}"
    fields = config.jira_fields.split(",") if config.jira_fields else None

    service = JiraService(
        auth=auth,
        cache_paths=cache_paths,
        freshness_threshold_hours=config.freshness_threshold_hours,
        jql=jql,
        fields=fields,
    )

    result = service.refresh(force=force)
    logger.info(f"Jira refresh complete: success={result['success']}")
    return _format_status_result(result)


def refreshAll(
    force: bool = False,
    config: InventoryConfig | None = None,
) -> typing.Any:
    """
    Refresh all inventory sources (Power BI and Jira).

    Runs refreshes independently so failure of one doesn't affect the other.

    Args:
        force: Force refresh even if caches are fresh.
        config: Inventory configuration. Uses env defaults if not provided.

    Returns:
        Dict with combined results for all sources.
    """
    if config is None:
        config = InventoryConfig.from_env()

    results: dict[typing.Any, typing.Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "force": force,
        "powerbi": None,
        "jira": None,
        "overall_success": True,
    }

    # Run Power BI refresh
    try:
        results["powerbi"] = refreshPbi(force=force, config=config)
        if not results["powerbi"]["success"]:
            results["overall_success"] = False
    except Exception as e:
        logger.exception("Power BI refresh failed")
        results["powerbi"] = {
            "source": "powerbi",
            "success": False,
            "error": str(e),
        }
        results["overall_success"] = False

    # Run Jira refresh (independent of Power BI result)
    try:
        results["jira"] = refreshJira(force=force, config=config)
        if not results["jira"]["success"]:
            results["overall_success"] = False
    except Exception as e:
        logger.exception("Jira refresh failed")
        results["jira"] = {
            "source": "jira",
            "success": False,
            "error": str(e),
        }
        results["overall_success"] = False

    logger.info(f"refreshAll complete: overall_success={results['overall_success']}")
    return results


def status_report(config: InventoryConfig | None = None) -> typing.Any:
    """
    Generate a human-readable status report.

    Args:
        config: Inventory configuration. Uses env defaults if not provided.

    Returns:
        Formatted status report string.
    """
    if config is None:
        config = InventoryConfig.from_env()

    combined = status(config)
    lines: list[typing.Any] = [
        "=" * 50,
        "Inventory Cache Status Report",
        f"Generated: {combined.timestamp.isoformat()}",
        f"Cache root: {config.cache_root}",
        "=" * 50,
        "",
    ]

    for src in combined.sources:
        status_icon = "✓" if src.available and src.is_fresh else "✗"
        freshness = "fresh" if src.is_fresh else "stale"

        lines.append(f"{status_icon} {src.source.upper()}")
        lines.append(f"   Available: {src.available}")
        lines.append(f"   Status: {freshness}")

        if src.last_success_at:
            lines.append(f"   Last success: {src.last_success_at.isoformat()}")
        if src.last_attempt_at:
            lines.append(f"   Last attempt: {src.last_attempt_at.isoformat()}")

        lines.append(f"   Records: {src.record_count}")

        if src.error_summary:
            lines.append(f"   Error: {src.error_summary}")

        lines.append("")

    ready_icon = "✓" if combined.overall_ready else "✗"
    lines.append(f"{ready_icon} Overall ready: {combined.overall_ready}")
    lines.append("=" * 50)

    return "\n".join(lines)
