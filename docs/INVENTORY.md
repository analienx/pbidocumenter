# Inventory, Caching & Matching

Advanced documentation for inventory refreshes, cache management, and report-to-Jira matching.

## Configure inventory refresh

Inventory configuration is loaded by `InventoryConfig.from_env()`.

Load order:
- local `inventory.settings.json`
- already-set environment variables override file values

Use either shell environment variables or `inventory.settings.json`.

Required:

```powershell
$env:KEY_VAULT_URL = "https://<your-vault>.vault.azure.net"
$env:PBI_TENANT_ID = "<tenant-id>"
$env:PBI_CLIENT_ID = "<client-id>"
$env:PBI_SECRET_NAME = "<powerbi-secret-name>"
$env:JIRA_BASE_URL = "https://<your-org>.atlassian.net"
$env:JIRA_USER = "<EMAIL_ADDRESS_005>"
$env:JIRA_SECRET_NAME = "<jira-secret-name>"
```

Example `inventory.settings.json`:

```json
{
  "KEY_VAULT_URL": "https://<your-vault>.vault.azure.net",
  "PBI_TENANT_ID": "<tenant-id>",
  "PBI_CLIENT_ID": "<client-id>",
  "PBI_SECRET_NAME": "<powerbi-secret-name>",
  "JIRA_BASE_URL": "https://<your-org>.atlassian.net",
  "JIRA_USER": "<EMAIL_ADDRESS_005>",
  "JIRA_SECRET_NAME": "<jira-secret-name>",
  "SHAREPOINT_SITE_URL": "https://<your-org>.sharepoint.com/sites/pbi",
  "REPORT_INVENTORY_FILE_ID": "<report-file-id>",
  "JIRA_DETAILS_FILE_ID": "<jira-file-id>"
}
```

Optional `inventory.settings.json` values:

```json
{
  "JIRA_PROJECT_KEY": "<JIRA_PROJECT_KEY>",
  "JIRA_PAGE_SIZE": 100,
  "JIRA_FIELDS": "summary,status,created,updated,assignee,reporter,labels,components,issuetype",
  "JIRA_EXPAND": "renderedFields",
  "FRESHNESS_THRESHOLD_HOURS": 24,
  "CACHE_ROOT": "cache",
  "LOG_LEVEL": "INFO",
  "REPORT_INVENTORY_PREFIX": "ReportInventory_Full",
  "REPORT_INVENTORY_SUFFIX": ".json",
  "JIRA_DETAILS_PREFIX": "JiraDetails_<JIRA_PROJECT_KEY>",
  "DOWNLOADS_TIMEOUT_SECONDS": 180
}
```

## Prepare all caches (inventory + downloads)

The `prepare` module orchestrates both inventory (API) and downloads (SharePoint files):

```powershell
# Prepare everything (inventory + downloads)
python -c "from pbip_documenter.prepare import prepare_all; print(prepare_all())"

# Check status of all caches
python -c "from pbip_documenter.prepare import prepare_status; print(prepare_status())"

# Prepare inventory only (Power BI + Jira APIs)
python -c "from pbip_documenter.prepare import prepare_inventory; print(prepare_inventory())"

# Prepare downloads only (SharePoint files)
python -c "from pbip_documenter.prepare import prepare_downloads; print(prepare_downloads())"
```

## Run inventory commands (API only)

Inventory operations are exposed via `pbip_documenter/inventory/commands.py`:

```powershell
python -c "from pbip_documenter.inventory.commands import refreshAll; print(refreshAll())"
python -c "from pbip_documenter.inventory.commands import refreshAll; print(refreshAll(force=True))"
python -c "from pbip_documenter.inventory.commands import refreshPbi; print(refreshPbi())"
python -c "from pbip_documenter.inventory.commands import refreshJira; print(refreshJira())"
python -c "from pbip_documenter.inventory.commands import status; print(status())"
python -c "from pbip_documenter.inventory.commands import status_report; print(status_report())"
```

Behavior:
- Power BI and Jira refresh independently
- manifests track success, failure, and freshness
- last-known-good cache is preserved on failure

## Use the matching layer

The matching layer is exposed through `MatchingService`.

```python
import pandas as pd
from pbip_documenter.inventory.matching.service import MatchingService

powerbi_reports = pd.DataFrame([
    {
        "name": "Sales Pipeline Report",
        "workspace_name": "Commercial Workspace",
        "app_name": "Executive App",
    }
])

jira_issues = pd.DataFrame([
    {
        "issue_key": "<JIRA_PROJECT_KEY>-1",
        "summary": "Sales pipeline automation",
        "searchable_text": "sales pipeline automation weekly forecasting",
    }
])

service = MatchingService(powerbi_reports=powerbi_reports, jira_issues=jira_issues)
results = service.match_report("Sales Pipeline Report")
print(results)
```

## Testing

Run all tests:

```powershell
python -m pytest pbip_documenter/tests
```

Run targeted tests:

```powershell
python -m pytest pbip_documenter/tests/test_status_command.py
python -m pytest pbip_documenter/tests/test_powerbi_normalize.py
python -m pytest pbip_documenter/tests/test_jira_normalize.py
python -m pytest pbip_documenter/tests/test_matching_text.py pbip_documenter/tests/test_matching_scoring.py
```

## Best practices

- store secrets in Azure Key Vault, not in source control
- use a separate cache root per environment when needed
- check `status_report()` before relying on cached data
- validate source-specific refreshes before using `refreshAll()`
- treat matching results as heuristic guidance, not authoritative linkage
