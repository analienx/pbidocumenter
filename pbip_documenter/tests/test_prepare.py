"""Tests for combined cache preparation."""

from unittest.mock import Mock, patch

from pbip_documenter.inventory.config import InventoryConfig
from pbip_documenter.prepare import (
    PrepareResult,
    prepare_all,
    prepare_downloads,
    prepare_inventory,
    prepare_status,
)


class TestPrepareInventory:
    """Tests for prepare_inventory function."""

    @patch("pbip_documenter.prepare.refreshAll")
    def test_calls_refresh_all(self, mock_refresh_all, tmp_path):
        mock_refresh_all.return_value = {
            "overall_success": True,
            "powerbi": {"success": True},
            "jira": {"success": True},
        }

        config = InventoryConfig(
            key_vault_url="<INTERNAL_URL_020>",
            pbi_tenant_id="tenant",
            pbi_client_id="client",
            pbi_secret_name="pbi-secret",
            jira_base_url="https://jira.example.com",
            jira_user="<EMAIL_ADDRESS_004>",
            jira_secret_name="jira-secret",
            cache_root=tmp_path,
        )

        result = prepare_inventory(force=True, config=config)

        assert result["overall_success"] is True
        mock_refresh_all.assert_called_once_with(force=True, config=config)


class TestPrepareDownloads:
    """Tests for prepare_downloads function."""

    @patch("pbip_documenter.prepare.DownloadService")
    @patch("pbip_documenter.prepare.DownloadConfig")
    def test_downloads_files(self, mock_config_class, mock_service_class):
        mock_config = Mock()
        mock_config_class.from_env.return_value = mock_config

        mock_service = Mock()
        mock_service.download_all_targets.return_value = {
            "report_inventory": {"downloaded": "file1.json", "cached": "cache1.json"},
            "jira_details": {"downloaded": "file2.xlsx", "cached": "cache2.xlsx"},
        }
        mock_service_class.return_value = mock_service

        result = prepare_downloads()

        assert len(result) == 2
        assert "report_inventory" in result
        assert "jira_details" in result
        mock_service.download_all_targets.assert_called_once()

    @patch("pbip_documenter.prepare.DownloadConfig")
    def test_returns_empty_dict_when_config_missing(self, mock_config_class):
        mock_config_class.from_env.side_effect = KeyError("SHAREPOINT_SITE_URL")

        result = prepare_downloads()

        assert result == {}


class TestPrepareAll:
    """Tests for prepare_all orchestration."""

    @patch("pbip_documenter.prepare.prepare_downloads")
    @patch("pbip_documenter.prepare.prepare_inventory")
    def test_runs_both_preparations(self, mock_prep_inv, mock_prep_dl, tmp_path):
        mock_prep_inv.return_value = {
            "overall_success": True,
            "powerbi": {"success": True},
            "jira": {"success": True},
        }
        mock_prep_dl.return_value = {
            "report_inventory": {"cached": "file1.json"},
        }

        config = InventoryConfig(
            key_vault_url="<INTERNAL_URL_020>",
            pbi_tenant_id="tenant",
            pbi_client_id="client",
            pbi_secret_name="pbi-secret",
            jira_base_url="https://jira.example.com",
            jira_user="<EMAIL_ADDRESS_004>",
            jira_secret_name="jira-secret",
            cache_root=tmp_path,
        )

        result = prepare_all(inventory_config=config)

        assert isinstance(result, PrepareResult)
        assert result.overall_success is True
        assert result.inventory_result["overall_success"] is True
        assert result.downloads_result is not None
        assert "report_inventory" in result.downloads_result
        mock_prep_inv.assert_called_once()
        mock_prep_dl.assert_called_once()

    @patch("pbip_documenter.prepare.prepare_downloads")
    @patch("pbip_documenter.prepare.prepare_inventory")
    def test_continues_after_inventory_failure(self, mock_prep_inv, mock_prep_dl, tmp_path):
        """Downloads should still run even if inventory fails."""
        mock_prep_inv.return_value = {
            "overall_success": False,
            "powerbi": {"success": False, "error": "Auth failed"},
            "jira": {"success": True},
        }
        mock_prep_dl.return_value = {
            "report_inventory": {"cached": "file1.json"},
        }

        config = InventoryConfig(
            key_vault_url="<INTERNAL_URL_020>",
            pbi_tenant_id="tenant",
            pbi_client_id="client",
            pbi_secret_name="pbi-secret",
            jira_base_url="https://jira.example.com",
            jira_user="<EMAIL_ADDRESS_004>",
            jira_secret_name="jira-secret",
            cache_root=tmp_path,
        )

        result = prepare_all(inventory_config=config)

        assert result.overall_success is False
        assert result.downloads_result is not None
        mock_prep_dl.assert_called_once()

    @patch("pbip_documenter.prepare.prepare_downloads")
    @patch("pbip_documenter.prepare.prepare_inventory")
    def test_handles_inventory_exception(self, mock_prep_inv, mock_prep_dl, tmp_path):
        mock_prep_inv.side_effect = Exception("Connection timeout")
        mock_prep_dl.return_value = {}

        config = InventoryConfig(
            key_vault_url="<INTERNAL_URL_020>",
            pbi_tenant_id="tenant",
            pbi_client_id="client",
            pbi_secret_name="pbi-secret",
            jira_base_url="https://jira.example.com",
            jira_user="<EMAIL_ADDRESS_004>",
            jira_secret_name="jira-secret",
            cache_root=tmp_path,
        )

        result = prepare_all(inventory_config=config)

        assert result.overall_success is False
        assert result.error is not None
        assert "Connection timeout" in result.error

    @patch("pbip_documenter.prepare.prepare_downloads")
    @patch("pbip_documenter.prepare.prepare_inventory")
    def test_handles_downloads_exception(self, mock_prep_inv, mock_prep_dl, tmp_path):
        mock_prep_inv.return_value = {"overall_success": True}
        mock_prep_dl.side_effect = Exception("SharePoint unavailable")

        config = InventoryConfig(
            key_vault_url="<INTERNAL_URL_020>",
            pbi_tenant_id="tenant",
            pbi_client_id="client",
            pbi_secret_name="pbi-secret",
            jira_base_url="https://jira.example.com",
            jira_user="<EMAIL_ADDRESS_004>",
            jira_secret_name="jira-secret",
            cache_root=tmp_path,
        )

        result = prepare_all(inventory_config=config)

        assert result.overall_success is False
        assert result.error is not None
        assert "SharePoint unavailable" in result.error


class TestPrepareStatus:
    """Tests for prepare_status reporting."""

    @patch("pbip_documenter.prepare.status")
    def test_generates_combined_report(self, mock_status, tmp_path):
        from datetime import datetime, timezone

        from pbip_documenter.inventory.commands import CombinedStatus, SourceStatus

        mock_status.return_value = CombinedStatus(
            timestamp=datetime.now(timezone.utc),
            sources=[
                SourceStatus(
                    source="powerbi",
                    available=True,
                    is_fresh=True,
                    last_success_at=datetime.now(timezone.utc),
                    last_attempt_at=datetime.now(timezone.utc),
                    record_count=100,
                    error_summary=None,
                    manifest_path=None,
                ),
                SourceStatus(
                    source="jira",
                    available=True,
                    is_fresh=True,
                    last_success_at=datetime.now(timezone.utc),
                    last_attempt_at=datetime.now(timezone.utc),
                    record_count=50,
                    error_summary=None,
                    manifest_path=None,
                ),
            ],
            overall_ready=True,
        )

        # Create fake downloads
        downloads_dir = tmp_path / "downloads"
        downloads_dir.mkdir()
        (downloads_dir / "report.json").write_text("{}")

        config = InventoryConfig(
            key_vault_url="<INTERNAL_URL_020>",
            pbi_tenant_id="tenant",
            pbi_client_id="client",
            pbi_secret_name="pbi-secret",
            jira_base_url="https://jira.example.com",
            jira_user="<EMAIL_ADDRESS_004>",
            jira_secret_name="jira-secret",
            cache_root=tmp_path,
        )

        report = prepare_status(config)

        assert "Combined Cache Status Report" in report
        assert "INVENTORY CACHES" in report
        assert "DOWNLOAD CACHES" in report
        assert "POWERBI" in report
        assert "JIRA" in report
        assert "DOWNLOADS" in report
        assert "Overall ready: True" in report

    @patch("pbip_documenter.prepare.status")
    def test_shows_downloads_unavailable(self, mock_status, tmp_path):
        from pbip_documenter.inventory.commands import CombinedStatus

        mock_status.return_value = CombinedStatus(
            timestamp=None,
            sources=[],
            overall_ready=True,
        )

        config = InventoryConfig(
            key_vault_url="<INTERNAL_URL_020>",
            pbi_tenant_id="tenant",
            pbi_client_id="client",
            pbi_secret_name="pbi-secret",
            jira_base_url="https://jira.example.com",
            jira_user="<EMAIL_ADDRESS_004>",
            jira_secret_name="jira-secret",
            cache_root=tmp_path,
        )

        report = prepare_status(config)

        assert "DOWNLOADS" in report
        assert "Available: False" in report
        assert "Overall ready: False" in report
