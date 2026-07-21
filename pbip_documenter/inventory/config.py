"""Configuration for inventory refresh operations."""

import json
import os
import typing
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(dotenv_path: Path = Path(".env")) -> typing.Any:
    """Load simple KEY=VALUE pairs from a local .env file if present."""
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def _load_settings_json(settings_path: Path = Path("inventory.settings.json")) -> typing.Any:
    """Load JSON settings into environment if present."""
    if not settings_path.exists():
        return

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    for key, value in settings.items():
        if key not in os.environ and value is not None:
            os.environ[key] = str(value)


@dataclass
class InventoryConfig:
    """Configuration for Power BI and Jira inventory refresh."""

    key_vault_url: str
    pbi_tenant_id: str
    pbi_client_id: str
    pbi_secret_name: str
    jira_base_url: str
    jira_user: str
    jira_secret_name: str
    jira_project_key: str = "<JIRA_PROJECT_KEY>"
    jira_page_size: int = 100
    jira_fields: str = "summary,status,created,updated,assignee,reporter,labels,components,issuetype"
    jira_expand: str = "renderedFields"
    freshness_threshold_hours: int = 24
    cache_root: Path = Path("cache")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls: typing.Any) -> typing.Any:
        """Create config from settings file and environment variables."""
        _load_settings_json()
        _load_dotenv()
        return cls(
            key_vault_url=os.environ["KEY_VAULT_URL"],
            pbi_tenant_id=os.environ["PBI_TENANT_ID"],
            pbi_client_id=os.environ["PBI_CLIENT_ID"],
            pbi_secret_name=os.environ["PBI_SECRET_NAME"],
            jira_base_url=os.environ["JIRA_BASE_URL"],
            jira_user=os.environ["JIRA_USER"],
            jira_secret_name=os.environ["JIRA_SECRET_NAME"],
            jira_project_key=os.environ.get("JIRA_PROJECT_KEY", "<JIRA_PROJECT_KEY>"),
            jira_page_size=int(os.environ.get("JIRA_PAGE_SIZE", "100")),
            jira_fields=os.environ.get(
                "JIRA_FIELDS", "summary,status,created,updated,assignee,reporter,labels,components,issuetype"
            ),
            jira_expand=os.environ.get("JIRA_EXPAND", "renderedFields"),
            freshness_threshold_hours=int(os.environ.get("FRESHNESS_THRESHOLD_HOURS", "24")),
            cache_root=Path(os.environ.get("CACHE_ROOT", "cache")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
