"""Orchestrate preparation of all cache sources (inventory + downloads)."""

import logging
import typing
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pbip_documenter.downloads.config import DownloadConfig, DownloadConfigError
from pbip_documenter.downloads.service import DownloadService
from pbip_documenter.inventory.commands import refreshAll, status
from pbip_documenter.inventory.config import InventoryConfig

logger = logging.getLogger(__name__)


@dataclass
class PrepareResult:
    """Result of preparing all caches."""

    timestamp: datetime
    inventory_result: dict[str, Any]
    downloads_result: dict[str, dict[str, Any]] | None
    overall_success: bool
    error: str | None = None


def prepare_inventory(
    force: bool = False,
    config: InventoryConfig | None = None,
) -> typing.Any:
    """
    Prepare inventory caches (Power BI + Jira from APIs).

    Args:
        force: Force refresh even if caches are fresh.
        config: Inventory configuration. Uses env defaults if not provided.

    Returns:
        Dict with refresh results.
    """
    logger.info("Preparing inventory caches (Power BI + Jira)...")
    result = refreshAll(force=force, config=config)
    logger.info(f"Inventory preparation complete: success={result['overall_success']}")
    return result


def prepare_downloads(
    config: DownloadConfig | None = None,
) -> typing.Any:
    """
    Prepare download caches (SharePoint files).

    Args:
        config: Download configuration. Uses env defaults if not provided.

    Returns:
        Dict with download results.
    """
    if config is None:
        try:
            config = DownloadConfig.from_env()
        except (KeyError, TypeError, DownloadConfigError) as e:
            logger.warning(f"Download config not available: {e}")
            logger.warning("Skipping downloads. Configure inventory.settings.json to enable.")
            return {}

    logger.info("Preparing download caches (SharePoint files)...")

    service = DownloadService(config)
    result = service.download_all_targets()
    logger.info(f"Downloads preparation complete: {len(result)} files")
    return result


def prepare_all(
    force_inventory: bool = False,
    inventory_config: InventoryConfig | None = None,
    download_config: DownloadConfig | None = None,
) -> typing.Any:
    """
    Prepare all caches: inventory (API) + downloads (SharePoint).

    This orchestrates both:
    - Inventory refresh: Power BI + Jira via REST APIs
    - Downloads: Pre-exported files from SharePoint

    Args:
        force_inventory: Force refresh inventory even if fresh.
        inventory_config: Inventory configuration. Uses env defaults if not provided.
        download_config: Download configuration. Uses env defaults if not provided.

    Returns:
        PrepareResult with combined status.
    """
    timestamp = datetime.now(timezone.utc)
    overall_success = True
    error = None

    # Step 1: Prepare inventory (API data)
    try:
        inventory_result = prepare_inventory(
            force=force_inventory,
            config=inventory_config,
        )
        if not inventory_result.get("overall_success", False):
            overall_success = False
    except Exception as e:
        logger.exception("Inventory preparation failed")
        inventory_result = {
            "overall_success": False,
            "error": str(e),
        }
        overall_success = False
        error = f"Inventory failed: {e}"

    # Step 2: Prepare downloads (SharePoint files)
    downloads_result = None
    try:
        downloads_result = prepare_downloads(config=download_config)
        # If downloads returned empty dict, it means config not available (not a failure)
        if downloads_result == {}:
            logger.info("Downloads skipped (no configuration)")
    except Exception as e:
        logger.exception("Downloads preparation failed")
        overall_success = False
        if error:
            error += f"; Downloads failed: {e}"
        else:
            error = f"Downloads failed: {e}"

    return PrepareResult(
        timestamp=timestamp,
        inventory_result=inventory_result,
        downloads_result=downloads_result,
        overall_success=overall_success,
        error=error,
    )


def prepare_status(
    inventory_config: InventoryConfig | None = None,
) -> typing.Any:
    """
    Generate human-readable status report for all caches.

    Args:
        inventory_config: Inventory configuration. Uses env defaults if not provided.

    Returns:
        Formatted status report string.
    """
    if inventory_config is None:
        inventory_config = InventoryConfig.from_env()

    # Get inventory status
    inventory_status = status(inventory_config)

    # Check for downloads
    downloads_cache = inventory_config.cache_root / "downloads"
    downloads_available = downloads_cache.exists() and any(downloads_cache.iterdir())

    lines: list[typing.Any] = [
        "=" * 60,
        "Combined Cache Status Report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Cache root: {inventory_config.cache_root}",
        "=" * 60,
        "",
        "INVENTORY CACHES (API Data)",
        "-" * 60,
    ]

    for src in inventory_status.sources:
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

    lines.extend(
        [
            "DOWNLOAD CACHES (SharePoint Files)",
            "-" * 60,
        ]
    )

    if downloads_available:
        lines.append("✓ DOWNLOADS")
        lines.append("   Available: True")
        lines.append(f"   Location: {downloads_cache}")

        # List files
        files = list(downloads_cache.iterdir())
        lines.append(f"   Files: {len(files)}")
        for f in files:
            lines.append(f"      - {f.name}")
    else:
        lines.append("✗ DOWNLOADS")
        lines.append("   Available: False")
        lines.append("   Note: Run prepare_downloads() or configure inventory.settings.json")

    lines.append("")

    # Overall readiness
    overall_ready = inventory_status.overall_ready and downloads_available
    ready_icon = "✓" if overall_ready else "✗"
    lines.append(f"{ready_icon} Overall ready: {overall_ready}")
    lines.append("   Inventory: " + ("✓" if inventory_status.overall_ready else "✗"))
    lines.append("   Downloads: " + ("✓" if downloads_available else "✗"))
    lines.append("=" * 60)

    return "\n".join(lines)
