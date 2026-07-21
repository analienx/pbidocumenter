"""Tests for Jira normalization and deduplication."""

from datetime import datetime

import pandas as pd
import pytest

from pbip_documenter.inventory.jira.normalize import JiraNormalizer


class TestJiraNormalizer:
    """Test cases for JiraNormalizer."""

    @pytest.fixture
    def normalizer(self):
        """Create a JiraNormalizer instance."""
        return JiraNormalizer()

    @pytest.fixture
    def sample_issue(self):
        """Create a sample Jira issue."""
        return {
            "id": "10001",
            "key": "<JIRA_PROJECT_KEY>-123",
            "fields": {
                "project": {"key": "<JIRA_PROJECT_KEY>"},
                "issuetype": {"name": "Story"},
                "summary": "Test issue summary",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Test description"}]}],
                },
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "assignee": {"emailAddress": "<EMAIL_ADDRESS_001>", "displayName": "Test User"},
                "reporter": {"emailAddress": "<EMAIL_ADDRESS_002>", "displayName": "Reporter User"},
                "created": "2024-01-15T10:30:00.000+0000",
                "updated": "2024-01-16T14:45:00.000+0000",
                "labels": ["label1", "label2"],
                "components": [{"name": "Component A"}],
            },
        }

    def test_normalize_single_issue(self, normalizer, sample_issue):
        """Test normalizing a single issue."""
        seen_ids = set()
        result = normalizer._normalize_single_issue(sample_issue, seen_ids)

        assert result is not None
        assert result.issue_key == "<JIRA_PROJECT_KEY>-123"
        assert result.issue_id == "10001"
        assert result.project_key == "<JIRA_PROJECT_KEY>"
        assert result.issue_type == "Story"
        assert result.summary == "Test issue summary"
        assert result.status == "In Progress"
        assert result.priority == "High"
        assert result.assignee_email == "<EMAIL_ADDRESS_001>"
        assert result.assignee_name == "Test User"
        assert result.reporter_email == "<EMAIL_ADDRESS_002>"
        assert result.reporter_name == "Reporter User"
        assert result.labels == ["label1", "label2"]
        assert result.components == ["Component A"]
        assert "Test issue summary" in result.searchable_text
        assert "Test description" in result.searchable_text

    def test_deduplication(self, normalizer, sample_issue):
        """Test that duplicate issues are deduplicated."""
        seen_ids = set()

        # First issue should be normalized
        result1 = normalizer._normalize_single_issue(sample_issue, seen_ids)
        assert result1 is not None

        # Duplicate should be skipped
        result2 = normalizer._normalize_single_issue(sample_issue, seen_ids)
        assert result2 is None

    def test_normalize_issues_empty_list(self, normalizer):
        """Test normalizing an empty list."""
        df = normalizer.normalize_issues([])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_normalize_issues_with_data(self, normalizer, sample_issue):
        """Test normalizing a list with issues."""
        df = normalizer.normalize_issues([sample_issue])

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["issue_key"] == "<JIRA_PROJECT_KEY>-123"

    def test_parse_datetime(self, normalizer):
        """Test datetime parsing."""
        # Standard Jira format
        dt = normalizer._parse_datetime("2024-01-15T10:30:00.000+0000")
        assert isinstance(dt, datetime)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

        # ISO format
        dt = normalizer._parse_datetime("2024-01-15T10:30:00+00:00")
        assert isinstance(dt, datetime)

        # None input
        assert normalizer._parse_datetime(None) is None

        # Invalid input
        assert normalizer._parse_datetime("invalid") is None

    def test_extract_description_adf(self, normalizer):
        """Test extracting description from ADF format."""
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Line 1"},
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Line 2"},
                    ],
                },
            ],
        }

        result = normalizer._extract_description(adf)
        assert "Line 1" in result
        assert "Line 2" in result

    def test_extract_description_string(self, normalizer):
        """Test extracting description from string."""
        result = normalizer._extract_description("Plain text description")
        assert result == "Plain text description"

    def test_extract_description_none(self, normalizer):
        """Test extracting description from None."""
        result = normalizer._extract_description(None)
        assert result is None

    def test_build_searchable_text(self, normalizer):
        """Test building searchable text."""
        text = normalizer._build_searchable_text(
            summary="Report Issue",
            description="This is a report about sales",
            labels=["sales", "q1"],
            components=["Reports", "Sales"],
        )

        assert "Report Issue" in text
        assert "sales" in text
        assert "Reports" in text

    def test_custom_field_extraction(self, normalizer):
        """Test custom field extraction."""
        fields = {
            "customfield_10016": 5.0,  # Story points
            "customfield_10014": "<JIRA_PROJECT_KEY>-100",  # Epic link
            "customfield_10015": "Epic Name",  # Epic name
        }

        story_points = normalizer._extract_custom_field_float(fields, "story_points")
        assert story_points == 5.0

        epic_link = normalizer._extract_custom_field_str(fields, "epic_link")
        assert epic_link == "<JIRA_PROJECT_KEY>-100"

        epic_name = normalizer._extract_custom_field_str(fields, "epic_name")
        assert epic_name == "Epic Name"

    def test_custom_field_not_found(self, normalizer):
        """Test custom field extraction when field not present."""
        fields = {}

        story_points = normalizer._extract_custom_field_float(fields, "story_points")
        assert story_points is None

        epic_link = normalizer._extract_custom_field_str(fields, "epic_link")
        assert epic_link is None

    def test_custom_field_mappings_override(self):
        """Test custom field mappings can be overridden."""
        custom_mappings = {
            "story_points": ["customfield_99999"],
        }
        normalizer = JiraNormalizer(custom_field_mappings=custom_mappings)

        fields = {
            "customfield_99999": 8.0,
        }

        story_points = normalizer._extract_custom_field_float(fields, "story_points")
        assert story_points == 8.0

    def test_issue_without_assignee(self, normalizer):
        """Test normalizing issue without assignee."""
        issue = {
            "id": "10002",
            "key": "<JIRA_PROJECT_KEY>-124",
            "fields": {
                "project": {"key": "<JIRA_PROJECT_KEY>"},
                "issuetype": {"name": "Bug"},
                "summary": "Bug without assignee",
                "status": {"name": "Open"},
                "assignee": None,
                "reporter": {"emailAddress": "<EMAIL_ADDRESS_003>", "displayName": "Rep"},
                "created": "2024-01-15T10:30:00.000+0000",
                "updated": "2024-01-15T10:30:00.000+0000",
                "labels": [],
                "components": [],
            },
        }

        seen_ids = set()
        result = normalizer._normalize_single_issue(issue, seen_ids)

        assert result is not None
        assert result.assignee_email is None
        assert result.assignee_name is None
