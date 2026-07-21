"""Configuration for SharePoint downloads."""

import json
import os
import typing
from dataclasses import dataclass
from pathlib import Path


class DownloadConfigError(ValueError):
    """Raised when download configuration is missing or invalid."""


def _load_settings_json(settings_path: Path = Path("inventory.settings.json")) -> typing.Any:
    """Load settings from JSON file if present."""
    if not settings_path.exists():
        return {}

    return json.loads(settings_path.read_text(encoding="utf-8"))


@dataclass
class DownloadTarget:
    """Single download target configuration."""

    name: str
    file_id: str
    prefix: str
    suffix: str | None
    cache_name: str


@dataclass
class DownloadConfig:
    """Configuration for SharePoint file downloads.

    Note: Reuses inventory.settings.json for configuration to maintain
    consistency with InventoryConfig. Add downloads settings to the same
    inventory.settings.json file.
    """

    sharepoint_site_url: str
    report_inventory_file_id: str
    report_inventory_prefix: str
    report_inventory_suffix: str
    report_inventory_cache_name: str
    jira_details_file_id: str
    jira_details_prefix: str
    jira_details_suffix: str | None
    jira_details_cache_name: str
    timeout_seconds: int = 180
    poll_seconds: int = 2
    cache_root: Path = Path("cache")

    @classmethod
    def from_env(cls: typing.Any, settings_path: Path = Path("inventory.settings.json")) -> typing.Any:
        """
        Create config from settings file and environment variables.

        Load order:
        1. Load inventory.settings.json if present
        2. Environment variables override file values

        Note: Reuses same inventory.settings.json as InventoryConfig for consistency.

        Args:
            settings_path: Path to JSON settings file (default: inventory.settings.json)
        """
        # Load from JSON file first
        settings = _load_settings_json(settings_path)

        # Environment variables override file values
        def get_value(key: str, default: typing.Any = None) -> typing.Any:
            return os.environ.get(key, settings.get(key, default))

        missing = [
            key
            for key in (
                "SHAREPOINT_SITE_URL",
                "REPORT_INVENTORY_FILE_ID",
                "JIRA_DETAILS_FILE_ID",
            )
            if not get_value(key)
        ]
        if missing:
            raise DownloadConfigError("Missing required download configuration: " + ", ".join(missing))

        return cls(
            sharepoint_site_url=get_value("SHAREPOINT_SITE_URL"),
            report_inventory_file_id=get_value("REPORT_INVENTORY_FILE_ID"),
            report_inventory_prefix=get_value("REPORT_INVENTORY_PREFIX", "ReportInventory_Full"),
            report_inventory_suffix=get_value("REPORT_INVENTORY_SUFFIX", ".json"),
            report_inventory_cache_name=get_value("REPORT_INVENTORY_CACHE_NAME", "report-links.json"),
            jira_details_file_id=get_value("JIRA_DETAILS_FILE_ID"),
            jira_details_prefix=get_value("JIRA_DETAILS_PREFIX", "JiraDetails_<JIRA_PROJECT_KEY>"),
            jira_details_suffix=get_value("JIRA_DETAILS_SUFFIX"),  # None for any extension
            jira_details_cache_name=get_value("JIRA_DETAILS_CACHE_NAME", "jira-details-odna"),
            timeout_seconds=int(get_value("DOWNLOADS_TIMEOUT_SECONDS", "180")),
            poll_seconds=int(get_value("DOWNLOADS_POLL_SECONDS", "2")),
            cache_root=Path(get_value("CACHE_ROOT", "cache")),
        )

    def get_targets(self: typing.Any) -> typing.Any:
        """Build download targets from configuration."""
        return [
            DownloadTarget(
                name="report_inventory",
                file_id=self.report_inventory_file_id,
                prefix=self.report_inventory_prefix,
                suffix=self.report_inventory_suffix,
                cache_name=self.report_inventory_cache_name,
            ),
            DownloadTarget(
                name="jira_details",
                file_id=self.jira_details_file_id,
                prefix=self.jira_details_prefix,
                suffix=self.jira_details_suffix,
                cache_name=self.jira_details_cache_name,
            ),
        ]

    def build_download_url(self: typing.Any, file_id: str) -> typing.Any:
        """Build SharePoint download URL from file ID."""
        base_url = self.sharepoint_site_url.rstrip("/")
        return f"{base_url}/_layouts/15/download.aspx?UniqueId={file_id}"

    def __post_init__(self: typing.Any) -> typing.Any:
        """Convert cache_root to Path if it's a string."""
        if isinstance(self.cache_root, str):
            self.cache_root = Path(self.cache_root)
