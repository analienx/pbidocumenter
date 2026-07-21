"""Normalization and deduplication for Power BI data."""

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class NormalizedReport:
    """Normalized Power BI report record."""

    report_id: str
    name: str
    web_url: str | None
    embed_url: str | None
    dataset_id: str | None
    workspace_id: str
    workspace_name: str
    app_id: str | None
    app_name: str | None
    report_type: str | None
    created_at: datetime | None
    modified_at: datetime | None
    is_original_report: bool
    original_report_id: str | None
    static_source: bool


class PowerBINormalizer:
    """Normalizes and deduplicates Power BI admin API responses."""

    REPORT_TYPE_MAPPINGS = {
        "PaginatedReport": "paginated",
        "PowerBIReport": "powerbi",
        "": None,
    }

    def normalize_reports(
        self,
        reports: list[dict[str, Any]],
        groups: list[dict[str, Any]],
        apps: list[dict[str, Any]],
    ) -> pd.DataFrame:
        """
        Normalize reports and join with workspace/app context.

        Handles:
        - Deduplication (report copies in multiple workspaces)
        - Workspace/app attribution
        - Field normalization
        - Type mapping
        """
        logger.info(f"Normalizing {len(reports)} reports from {len(groups)} workspaces")

        # Build lookup maps
        group_map = {g.get("id"): g.get("name", "Unknown") for g in groups}
        app_map = {a.get("id"): a.get("name", "Unknown") for a in apps}

        # Track seen reports for deduplication
        seen_ids: set[str] = set()
        normalized: list[NormalizedReport] = []

        for report in reports:
            record = self._normalize_single_report(report, group_map, app_map, seen_ids)
            if record:
                normalized.append(record)

        logger.info(f"Normalized {len(normalized)} unique reports")
        return self._to_dataframe(normalized)

    def _normalize_single_report(
        self,
        report: dict[str, Any],
        group_map: dict[str, str],
        app_map: dict[str, str],
        seen_ids: set[str],
    ) -> NormalizedReport | None:
        """Normalize a single report record."""
        report_id = report.get("id")
        if not report_id:
            return None

        # Determine workspace
        workspace_id = report.get("groupId") or report.get("workspaceId", "")
        workspace_name = group_map.get(workspace_id, "Unknown")

        # Check for duplicates
        is_original = report_id not in seen_ids
        seen_ids.add(report_id)

        # Extract report type
        raw_type = report.get("reportType", "")
        report_type = self.REPORT_TYPE_MAPPINGS.get(raw_type, str(raw_type).lower() if raw_type else None)

        # Parse timestamps
        created_at = self._parse_datetime(report.get("createdDateTime"))
        modified_at = self._parse_datetime(report.get("modifiedDateTime"))

        # Synthetic app attribution (reports don't have appId directly; apps reference reports)
        app_id = report.get("appId")
        app_name = app_map.get(app_id) if app_id else None

        return NormalizedReport(
            report_id=report_id,
            name=report.get("name", "").strip(),
            web_url=report.get("webUrl"),
            embed_url=report.get("embedUrl"),
            dataset_id=report.get("datasetId"),
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            app_id=app_id,
            app_name=app_name,
            report_type=report_type,
            created_at=created_at,
            modified_at=modified_at,
            is_original_report=is_original,
            original_report_id=report.get("originalReportId") if not is_original else None,
            static_source=self._is_static_report(report),
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        if not value:
            return None
        try:
            # Handle both with and without timezone
            value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse datetime: {value}, error: {e}")
            return None

    def _is_static_report(self, report: dict[str, Any]) -> bool:
        """Determine if this is a static/Paginated report."""
        report_type = report.get("reportType", "")
        return report_type == "PaginatedReport"

    def _to_dataframe(self, records: list[NormalizedReport]) -> pd.DataFrame:
        """Convert normalized records to DataFrame."""
        if not records:
            return pd.DataFrame(
                columns=[
                    "report_id",
                    "name",
                    "web_url",
                    "embed_url",
                    "dataset_id",
                    "workspace_id",
                    "workspace_name",
                    "app_id",
                    "app_name",
                    "report_type",
                    "created_at",
                    "modified_at",
                    "is_original_report",
                    "original_report_id",
                    "static_source",
                ]
            )

        data = [asdict(r) for r in records]
        df = pd.DataFrame(data)

        # Optimize types
        for col in [
            "name",
            "web_url",
            "embed_url",
            "dataset_id",
            "workspace_id",
            "workspace_name",
            "app_id",
            "app_name",
        ]:
            if col in df.columns:
                df[col] = df[col].astype("string")

        # Reorder columns for readability
        column_order = [
            "report_id",
            "name",
            "workspace_name",
            "app_name",
            "report_type",
            "static_source",
            "dataset_id",
            "workspace_id",
            "app_id",
            "web_url",
            "embed_url",
            "created_at",
            "modified_at",
            "is_original_report",
            "original_report_id",
        ]
        available_cols = [c for c in column_order if c in df.columns]
        remaining_cols = [c for c in df.columns if c not in available_cols]
        df = df[available_cols + remaining_cols]

        return df
