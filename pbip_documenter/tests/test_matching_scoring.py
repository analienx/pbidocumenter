"""Tests for matching scoring and service behavior."""

import pandas as pd

from pbip_documenter.inventory.matching.scoring import score_match
from pbip_documenter.inventory.matching.service import MatchingService


class TestMatchingScoring:
    def test_score_match_exact_name_gives_high_confidence(self):
        detail = score_match(
            query_tokens=["sales", "pipeline"],
            candidate_tokens=["sales", "pipeline", "weekly"],
            query_name="Sales Pipeline",
            candidate_name="Sales Pipeline",
        )

        assert detail.exact_name_match is True
        assert detail.final_score > 0.75
        assert detail.confidence == "high"
        assert any("Exact name match" in item for item in detail.evidence)

    def test_score_match_no_overlap_gives_low_confidence(self):
        detail = score_match(
            query_tokens=["sales"],
            candidate_tokens=["finance"],
            query_name="Sales",
            candidate_name="Finance",
        )

        assert detail.final_score == 0.0
        assert detail.confidence == "low"


class TestMatchingService:
    def test_match_report_returns_ranked_results(self):
        powerbi_reports = pd.DataFrame(
            [
                {
                    "name": "Sales Pipeline Report",
                    "workspace_name": "Commercial Workspace",
                    "app_name": "Executive App",
                }
            ]
        )
        jira_issues = pd.DataFrame(
            [
                {
                    "issue_key": "<JIRA_PROJECT_KEY>-1",
                    "summary": "Sales pipeline automation",
                    "searchable_text": "sales pipeline automation weekly forecasting",
                },
                {
                    "issue_key": "<JIRA_PROJECT_KEY>-2",
                    "summary": "Finance close tracker",
                    "searchable_text": "finance month end close controls",
                },
            ]
        )

        service = MatchingService(powerbi_reports=powerbi_reports, jira_issues=jira_issues)
        results = service.match_report("Sales Pipeline Report")

        assert len(results) == 2
        assert results[0].jira_issue_key == "<JIRA_PROJECT_KEY>-1"
        assert results[0].score >= results[1].score
        assert results[0].workspace_name == "Commercial Workspace"
        assert any("Workspace: Commercial Workspace" in item for item in results[0].evidence)

    def test_match_report_dedupes_same_issue_across_multiple_report_rows(self):
        powerbi_reports = pd.DataFrame(
            [
                {
                    "name": "Sales Pipeline Report",
                    "workspace_name": "Commercial Workspace",
                    "app_name": "Executive App",
                },
                {
                    "name": "Sales Pipeline Report",
                    "workspace_name": "Commercial Workspace Copy",
                    "app_name": "Executive App",
                },
            ]
        )
        jira_issues = pd.DataFrame(
            [
                {
                    "issue_key": "<JIRA_PROJECT_KEY>-1",
                    "summary": "Sales pipeline automation",
                    "searchable_text": "sales pipeline automation weekly forecasting",
                }
            ]
        )

        service = MatchingService(powerbi_reports=powerbi_reports, jira_issues=jira_issues)
        results = service.match_report("Sales Pipeline Report")

        assert len(results) == 1
        assert results[0].jira_issue_key == "<JIRA_PROJECT_KEY>-1"

    def test_match_report_fuzzy_matches_workspace_name(self):
        """Test that matching works when query matches workspace name."""
        powerbi_reports = pd.DataFrame(
            [
                {
                    "name": "Quarterly Review",
                    "workspace_name": "Finance Workspace",
                    "app_name": "Finance App",
                    "web_url": "https://app.powerbi.com/groups/ws-123/reports/rpt-456",
                }
            ]
        )
        jira_issues = pd.DataFrame(
            [
                {
                    "issue_key": "FIN-1",
                    "summary": "Finance quarterly reporting",
                    "searchable_text": "finance quarterly reporting review",
                }
            ]
        )

        service = MatchingService(powerbi_reports=powerbi_reports, jira_issues=jira_issues)
        # Query matches workspace name, not report name
        results = service.match_report("Finance Workspace")

        assert len(results) == 1
        assert results[0].jira_issue_key == "FIN-1"
        assert results[0].workspace_name == "Finance Workspace"
        assert results[0].app_name == "Finance App"

    def test_match_report_fuzzy_matches_app_name(self):
        """Test that matching works when query matches app name."""
        powerbi_reports = pd.DataFrame(
            [
                {
                    "name": "Executive Summary",
                    "workspace_name": "Sales Workspace",
                    "app_name": "Executive Dashboard App",
                    "web_url": "https://app.powerbi.com/groups/ws-789/reports/rpt-012",
                }
            ]
        )
        jira_issues = pd.DataFrame(
            [
                {
                    "issue_key": "EXEC-1",
                    "summary": "Executive dashboard requirements",
                    "searchable_text": "executive dashboard requirements sales",
                }
            ]
        )

        service = MatchingService(powerbi_reports=powerbi_reports, jira_issues=jira_issues)
        # Query matches app name
        results = service.match_report("Executive Dashboard App")

        assert len(results) == 1
        assert results[0].jira_issue_key == "EXEC-1"
        assert results[0].app_name == "Executive Dashboard App"

    def test_match_report_fuzzy_partial_match(self):
        """Test fuzzy matching with partial token overlap."""
        powerbi_reports = pd.DataFrame(
            [
                {
                    "name": "Sales Pipeline Analytics",
                    "workspace_name": "Commercial Team",
                    "app_name": "Sales Hub",
                },
                {
                    "name": "Marketing Dashboard",
                    "workspace_name": "Marketing Team",
                    "app_name": "Marketing Hub",
                },
            ]
        )
        jira_issues = pd.DataFrame(
            [
                {
                    "issue_key": "SALES-1",
                    "summary": "Sales pipeline tracking",
                    "searchable_text": "sales pipeline tracking commercial",
                }
            ]
        )

        service = MatchingService(powerbi_reports=powerbi_reports, jira_issues=jira_issues)
        # Partial match - "Sales Pipeline" should match first report
        results = service.match_report("Sales Pipeline")

        assert len(results) == 1
        assert results[0].jira_issue_key == "SALES-1"
        # Should match the sales report, not marketing
        assert results[0].workspace_name == "Commercial Team"

    def test_match_report_returns_best_match_across_all_fields(self):
        """Test that best match is selected across report, workspace, and app names."""
        powerbi_reports = pd.DataFrame(
            [
                {
                    "name": "Inventory Report",
                    "workspace_name": "Supply Chain Workspace",
                    "app_name": "Operations App",
                },
                {
                    "name": "Shipping Dashboard",
                    "workspace_name": "Inventory Management",
                    "app_name": "Logistics App",
                },
            ]
        )
        jira_issues = pd.DataFrame(
            [
                {
                    "issue_key": "INV-1",
                    "summary": "Inventory management system",
                    "searchable_text": "inventory management supply chain",
                }
            ]
        )

        service = MatchingService(powerbi_reports=powerbi_reports, jira_issues=jira_issues)
        # "Inventory" appears in first report name and second workspace name
        results = service.match_report("Inventory")

        assert len(results) == 1
        assert results[0].jira_issue_key == "INV-1"
        # First report should win due to name match having higher weight
        assert results[0].workspace_name == "Supply Chain Workspace"

    def test_match_report_handles_nan_values_gracefully(self):
        """Test that NaN values in DataFrame don't propagate as 'nan' strings."""
        import math

        powerbi_reports = pd.DataFrame(
            [
                {
                    "name": "Sales Report",
                    "workspace_name": "Sales Workspace",
                    "app_name": math.nan,  # NaN value
                    "workspace_id": "ws-123",
                    "web_url": "https://example.com",
                }
            ]
        )
        jira_issues = pd.DataFrame(
            [
                {
                    "issue_key": "SALES-1",
                    "summary": "Sales reporting",
                    "searchable_text": "sales reporting",
                }
            ]
        )

        service = MatchingService(powerbi_reports=powerbi_reports, jira_issues=jira_issues)
        results = service.match_report("Sales Report")

        assert len(results) == 1
        # NaN values should be converted to None, not "nan" strings
        assert results[0].workspace_name == "Sales Workspace"
        assert results[0].app_name is None  # NaN should become None
        assert results[0].workspace_id == "ws-123"
        assert results[0].web_url == "https://example.com"
