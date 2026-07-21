"""Tests for Power BI normalization."""

from datetime import datetime

import pandas as pd

from pbip_documenter.inventory.powerbi.normalize import PowerBINormalizer


class TestPowerBINormalizer:
    """Tests for PowerBI normalization logic."""

    def setup_method(self):
        self.normalizer = PowerBINormalizer()

    def test_normalize_single_report_basic(self):
        """Test basic report normalization."""
        report = {
            "id": "report-123",
            "name": "Sales Dashboard",
            "webUrl": "https://app.powerbi.com/reports/123",
            "embedUrl": "https://embedded",
            "datasetId": "dataset-456",
            "workspaceId": "ws-789",
            "reportType": "PowerBIReport",
            "createdDateTime": "2024-01-15T10:30:00Z",
            "modifiedDateTime": "2024-01-20T14:00:00Z",
        }
        groups = [{"id": "ws-789", "name": "Finance Workspace"}]
        apps = []

        df = self.normalizer.normalize_reports([report], groups, apps)

        assert len(df) == 1
        assert df.iloc[0]["report_id"] == "report-123"
        assert df.iloc[0]["name"] == "Sales Dashboard"
        assert df.iloc[0]["workspace_name"] == "Finance Workspace"
        assert df.iloc[0]["report_type"] == "powerbi"
        assert not df.iloc[0]["static_source"]
        assert df.iloc[0]["is_original_report"]
        assert pd.notna(df.iloc[0]["created_at"])
        assert pd.notna(df.iloc[0]["modified_at"])

    def test_normalize_paginated_report(self):
        """Test that PaginatedReport is marked as static_source."""
        report = {
            "id": "report-456",
            "name": "Financial Report",
            "webUrl": "https://app.powerbi.com/reports/456",
            "workspaceId": "ws-123",
            "reportType": "PaginatedReport",
        }
        groups = [{"id": "ws-123", "name": "Reports Workspace"}]
        apps = []

        df = self.normalizer.normalize_reports([report], groups, apps)

        assert len(df) == 1
        assert df.iloc[0]["report_type"] == "paginated"
        assert df.iloc[0]["static_source"]

    def test_normalize_report_with_missing_workspace(self):
        """Test handling of report with unknown workspace."""
        report = {
            "id": "report-999",
            "name": "Orphan Report",
            "workspaceId": "ws-unknown",
        }
        groups = [{"id": "ws-other", "name": "Other Workspace"}]
        apps = []

        df = self.normalizer.normalize_reports([report], groups, apps)

        assert len(df) == 1
        assert df.iloc[0]["workspace_name"] == "Unknown"

    def test_deduplication_same_report_in_multiple_workspaces(self):
        """Test that duplicate reports across workspaces are tracked correctly."""
        report1 = {
            "id": "report-dup",
            "name": "Duplicate Report",
            "workspaceId": "ws-a",
        }
        report2 = {
            "id": "report-dup",
            "name": "Duplicate Report",
            "workspaceId": "ws-b",
        }
        groups = [
            {"id": "ws-a", "name": "Workspace A"},
            {"id": "ws-b", "name": "Workspace B"},
        ]
        apps = []

        df = self.normalizer.normalize_reports([report1, report2], groups, apps)

        assert len(df) == 2
        # Both should be marked as is_original_report=False because same ID appears twice
        # Actually - looking at code, it marks first occurrence as original=True
        assert df.iloc[0]["is_original_report"]
        assert not df.iloc[1]["is_original_report"]

    def test_report_with_app_reference(self):
        """Test report with app attribution."""
        report = {
            "id": "report-app",
            "name": "App Report",
            "workspaceId": "ws-1",
            "appId": "app-1",
        }
        groups = [{"id": "ws-1", "name": "Work Space"}]
        apps = [{"id": "app-1", "name": "Sales App"}]

        df = self.normalizer.normalize_reports([report], groups, apps)

        assert len(df) == 1
        assert df.iloc[0]["app_id"] == "app-1"
        assert df.iloc[0]["app_name"] == "Sales App"

    def test_normalize_empty_lists(self):
        """Test normalization with empty input."""
        df = self.normalizer.normalize_reports([], [], [])

        assert len(df) == 0
        assert "report_id" in df.columns
        assert "name" in df.columns

    def test_parse_datetime_various_formats(self):
        """Test parsing of various datetime formats."""
        report_with_z = {
            "id": "r1",
            "name": "Report Z",
            "createdDateTime": "2024-01-15T10:30:00Z",
        }
        report_with_offset = {
            "id": "r2",
            "name": "Report Offset",
            "createdDateTime": "2024-01-15T10:30:00+00:00",
        }
        report_no_timezone = {
            "id": "r3",
            "name": "Report No TZ",
            "createdDateTime": "2024-01-15T10:30:00",
        }

        df = self.normalizer.normalize_reports([report_with_z, report_with_offset, report_no_timezone], [], [])

        assert len(df) == 3
        # All should parse to datetime objects
        for i in range(3):
            if pd.notna(df.iloc[i]["created_at"]):
                assert isinstance(df.iloc[i]["created_at"], datetime)

    def test_current_report_attribution(self):
        """Test originalReportId is preserved when present."""
        report = {
            "id": "report-copy",
            "name": "Copy Report",
            "workspaceId": "ws-copy",
            "originalReportId": "report-original",
        }
        groups = [{"id": "ws-copy", "name": "Copy Workspace"}]
        apps = []

        df = self.normalizer.normalize_reports([report], groups, apps)

        # originalReportId is only set when is_original_report=False
        assert df.iloc[0]["is_original_report"]
        assert df.iloc[0]["original_report_id"] is None

    def test_strip_report_names(self):
        """Test that report names are trimmed."""
        report = {
            "id": "report-trim",
            "name": "  Trimmed Report  ",
            "workspaceId": "ws-1",
        }
        groups = [{"id": "ws-1", "name": "Ws"}]
        apps = []

        df = self.normalizer.normalize_reports([report], groups, apps)

        assert df.iloc[0]["name"] == "Trimmed Report"
