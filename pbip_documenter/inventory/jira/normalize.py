"""Normalization and field mapping for Jira <JIRA_PROJECT_KEY> issues."""

import logging
import typing
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class NormalizedIssue:
    """Normalized Jira issue record."""

    issue_key: str
    issue_id: str
    project_key: str
    issue_type: str
    summary: str
    description: str | None
    status: str
    priority: str | None
    assignee_email: str | None
    assignee_name: str | None
    reporter_email: str | None
    reporter_name: str | None
    created_at: datetime | None
    updated_at: datetime | None
    resolved_at: datetime | None
    labels: list[str]
    components: list[str]
    # Custom fields for <JIRA_PROJECT_KEY>
    story_points: float | None
    epic_link: str | None
    epic_name: str | None
    # Searchable text for matching
    searchable_text: str


class JiraNormalizer:
    """Normalizes and deduplicates Jira API responses."""

    # Default field mappings for common custom fields
    # These can be overridden via config
    DEFAULT_CUSTOM_FIELDS: dict[typing.Any, typing.Any] = {
        "story_points": ["customfield_10016", "customfield_10004"],  # Common story point fields
        "epic_link": ["customfield_10014", "customfield_10008"],  # Common epic link fields
        "epic_name": ["customfield_10015", "customfield_10011"],  # Common epic name fields
    }

    def __init__(self: typing.Any, custom_field_mappings: dict[str, list[str]] | None = None) -> None:
        """
        Initialize normalizer with optional custom field mappings.

        Args:
            custom_field_mappings: Dict mapping normalized field names to
                                   lists of possible custom field IDs.
        """
        self.custom_field_mappings = custom_field_mappings or self.DEFAULT_CUSTOM_FIELDS

    def normalize_issues(
        self: typing.Any,
        issues: list[dict[str, Any]],
    ) -> typing.Any:
        """
        Normalize issues and extract key fields.

        Handles:
        - Deduplication
        - Field normalization
        - Custom field extraction
        - Searchable text generation
        """
        logger.info(f"Normalizing {len(issues)} Jira issues")

        seen_ids: set[str] = set()
        normalized: list[NormalizedIssue] = []

        for issue in issues:
            record = self._normalize_single_issue(issue, seen_ids)
            if record:
                normalized.append(record)

        logger.info(f"Normalized {len(normalized)} unique issues")
        return self._to_dataframe(normalized)

    def _normalize_single_issue(
        self: typing.Any,
        issue: dict[str, Any],
        seen_ids: set[str],
    ) -> typing.Any:
        """Normalize a single issue record."""
        issue_id = issue.get("id")
        issue_key = issue.get("key")

        if not issue_id or not issue_key:
            return None

        # Deduplication
        if issue_id in seen_ids:
            logger.debug(f"Skipping duplicate issue: {issue_key}")
            return None
        seen_ids.add(issue_id)

        fields = issue.get("fields", {})

        # Extract standard fields
        project = fields.get("project", {})
        issue_type = fields.get("issuetype", {})
        status = fields.get("status", {})
        priority = fields.get("priority", {})
        assignee = fields.get("assignee") or {}
        reporter = fields.get("reporter") or {}

        # Parse timestamps
        created_at = self._parse_datetime(fields.get("created"))
        updated_at = self._parse_datetime(fields.get("updated"))
        resolution_date = fields.get("resolutiondate")
        resolved_at = self._parse_datetime(resolution_date) if resolution_date else None

        # Extract labels and components
        labels = fields.get("labels", [])
        components = [c.get("name", "") for c in fields.get("components", []) if c.get("name")]

        # Extract custom fields
        story_points = self._extract_custom_field_float(fields, "story_points")
        epic_link = self._extract_custom_field_str(fields, "epic_link")
        epic_name = self._extract_custom_field_str(fields, "epic_name")

        # Build searchable text
        description = self._extract_description(fields.get("description"))
        searchable_text = self._build_searchable_text(
            summary=fields.get("summary", ""),
            description=description,
            labels=labels,
            components=components,
        )

        return NormalizedIssue(
            issue_key=issue_key,
            issue_id=issue_id,
            project_key=project.get("key", ""),
            issue_type=issue_type.get("name", ""),
            summary=fields.get("summary", "").strip(),
            description=description,
            status=status.get("name", ""),
            priority=priority.get("name") if priority else None,
            assignee_email=assignee.get("emailAddress"),
            assignee_name=assignee.get("displayName"),
            reporter_email=reporter.get("emailAddress"),
            reporter_name=reporter.get("displayName"),
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            labels=labels,
            components=components,
            story_points=story_points,
            epic_link=epic_link,
            epic_name=epic_name,
            searchable_text=searchable_text,
        )

    def _parse_datetime(self: typing.Any, value: str | None) -> typing.Any:
        """Parse ISO datetime string."""
        if not value:
            return None
        try:
            # Handle Jira's format: "2024-01-15T10:30:00.000+0000"
            value = value.replace(".000", "").replace("+0000", "+00:00")
            if "+" not in value and "Z" not in value:
                value = value + "+00:00"
            value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse datetime: {value}, error: {e}")
            return None

    def _extract_description(self: typing.Any, description: Any) -> typing.Any:
        """Extract plain text from Jira'sAtlassian Document Format."""
        if not description:
            return None

        if isinstance(description, str):
            return description

        # Try to extract text from ADF format
        if isinstance(description, dict):
            return self._extract_text_from_adf(description)

        return None

    def _extract_text_from_adf(self: typing.Any, node: dict[str, Any]) -> typing.Any:
        """Recursively extract text from Atlassian Document Format."""
        texts: list[typing.Any] = []

        if "text" in node:
            texts.append(node["text"])

        content = node.get("content", [])
        if isinstance(content, list):
            for child in content:
                if isinstance(child, dict):
                    texts.append(self._extract_text_from_adf(child))

        return " ".join(filter(None, texts))

    def _extract_custom_field_str(
        self: typing.Any,
        fields: dict[str, Any],
        normalized_name: str,
    ) -> typing.Any:
        """Extract string value from custom field."""
        field_ids = self.custom_field_mappings.get(normalized_name, [])
        for field_id in field_ids:
            value = fields.get(field_id)
            if value is not None:
                if isinstance(value, str):
                    return value
                if isinstance(value, dict):
                    return value.get("value") or value.get("name")
                return str(value)
        return None

    def _extract_custom_field_float(
        self: typing.Any,
        fields: dict[str, Any],
        normalized_name: str,
    ) -> typing.Any:
        """Extract float/numeric value from custom field."""
        field_ids = self.custom_field_mappings.get(normalized_name, [])
        for field_id in field_ids:
            value = fields.get(field_id)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None

    def _build_searchable_text(
        self: typing.Any,
        summary: str,
        description: str | None,
        labels: list[str],
        components: list[str],
    ) -> typing.Any:
        """Build combined searchable text from issue fields."""
        parts: list[typing.Any] = [summary]

        if description:
            parts.append(description)

        if labels:
            parts.append(" ".join(labels))

        if components:
            parts.append(" ".join(components))

        return " ".join(filter(None, parts))

    def _to_dataframe(self: typing.Any, records: list[NormalizedIssue]) -> typing.Any:
        """Convert normalized records to DataFrame."""
        if not records:
            return pd.DataFrame(
                columns=[
                    "issue_key",
                    "issue_id",
                    "project_key",
                    "issue_type",
                    "summary",
                    "description",
                    "status",
                    "priority",
                    "assignee_email",
                    "assignee_name",
                    "reporter_email",
                    "reporter_name",
                    "created_at",
                    "updated_at",
                    "resolved_at",
                    "labels",
                    "components",
                    "story_points",
                    "epic_link",
                    "epic_name",
                    "searchable_text",
                ]
            )

        data = [asdict(r) for r in records]
        df = pd.DataFrame(data)

        # Optimize types
        for col in [
            "issue_key",
            "issue_id",
            "project_key",
            "issue_type",
            "summary",
            "status",
            "priority",
            "assignee_email",
            "assignee_name",
            "reporter_email",
            "reporter_name",
            "epic_link",
            "epic_name",
        ]:
            if col in df.columns:
                df[col] = df[col].astype("string")

        # Reorder columns
        column_order: list[typing.Any] = [
            "issue_key",
            "summary",
            "issue_type",
            "status",
            "project_key",
            "priority",
            "assignee_name",
            "reporter_name",
            "labels",
            "components",
            "epic_link",
            "epic_name",
            "story_points",
            "created_at",
            "updated_at",
            "resolved_at",
            "assignee_email",
            "reporter_email",
            "issue_id",
            "description",
            "searchable_text",
        ]
        available_cols = [c for c in column_order if c in df.columns]
        remaining_cols = [c for c in df.columns if c not in available_cols]
        df = df[available_cols + remaining_cols]

        return df
