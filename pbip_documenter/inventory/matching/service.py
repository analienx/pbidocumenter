"""Cached-artifact matching service for Power BI and Jira outputs."""

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from pbip_documenter.inventory.matching.scoring import ScoreDetail, score_match
from pbip_documenter.inventory.matching.text import (
    build_search_context,
    calculate_token_overlap,
    extract_keywords,
    normalize_text,
    sanitize_for_display,
)

logger = logging.getLogger(__name__)


def _safe_get(series, key, default=""):
    """Safely get a value from a pandas Series, handling pd.NA values.

    Unlike .get() with `or` which fails on pd.NA (boolean value of NA is ambiguous),
    this function converts pd.NA to the default value.
    """
    value = series.get(key)
    # Check for pandas NA explicitly since pd.NA | default raises TypeError
    if value is None or (isinstance(value, type(pd.NA)) and pd.isna(value)):
        return default
    return value


@dataclass
class MatchResult:
    """Ranked match result linking a report query to cached artifacts."""

    report_name: str
    normalized_query: str
    score: float
    confidence: str
    jira_issue_key: str | None
    jira_summary: str | None
    jira_url: str | None
    workspace_name: str | None
    workspace_id: str | None
    workspace_url: str | None
    app_name: str | None
    app_id: str | None
    app_url: str | None
    report_id: str | None
    web_url: str | None
    embed_url: str | None
    evidence: list[str]


class MatchingService:
    """Builds explainable matches using cached Power BI and Jira artifacts only."""

    # Base URLs for constructing links
    POWER_BI_BASE_URL = "https://app.powerbi.com"
    DEFAULT_JIRA_BASE_URL = ""

    def __init__(
        self,
        powerbi_reports: pd.DataFrame,
        jira_issues: pd.DataFrame,
        jira_base_url: str | None = None,
    ):
        self.powerbi_reports = powerbi_reports.copy()
        self.jira_issues = jira_issues.copy()
        self.jira_base_url = (jira_base_url or self.DEFAULT_JIRA_BASE_URL).rstrip("/")

    def _build_powerbi_url(
        self,
        workspace_id: str | None,
        report_id: str | None,
        existing_url: str | None,
    ) -> str | None:
        """Construct Power BI report URL from IDs or return existing URL."""
        # Use existing URL if available
        if existing_url and existing_url.startswith("http"):
            return existing_url

        # Construct URL from workspace and report IDs
        if workspace_id and report_id:
            return f"{self.POWER_BI_BASE_URL}/groups/{workspace_id}/reports/{report_id}"

        return None

    def _build_workspace_url(self, workspace_id: str | None) -> str | None:
        """Construct Power BI workspace URL from ID."""
        if workspace_id:
            return f"{self.POWER_BI_BASE_URL}/groups/{workspace_id}"
        return None

    def _build_app_url(self, app_id: str | None) -> str | None:
        """Construct Power BI app URL from ID."""
        if app_id:
            return f"{self.POWER_BI_BASE_URL}/apps/{app_id}"
        return None

    def _build_jira_url(self, issue_key: str | None) -> str | None:
        """Construct Jira issue URL from issue key."""
        if issue_key and self.jira_base_url:
            return f"{self.jira_base_url}/browse/{issue_key}"
        return None

    def match_report(self, report_name: str, limit: int = 5) -> list[MatchResult]:
        """Find likely Jira matches for a report using cached artifacts."""
        import time

        start_time = time.time()

        normalized_query = normalize_text(report_name)
        query_tokens = extract_keywords(report_name)

        if not query_tokens:
            return []

        logger.debug(
            f"Matching report '{report_name}' against {len(self.powerbi_reports)} Power BI reports and {len(self.jira_issues)} Jira issues"
        )

        report_rows = self._find_report_rows(normalized_query, query_tokens)

        if report_rows.empty:
            report_rows = pd.DataFrame([{"name": report_name, "workspace_name": None, "app_name": None}])

        # Pre-compute Jira issue tokens once to avoid repeated extraction
        jira_data = []
        for _, issue_row in self.jira_issues.iterrows():
            issue_text = _safe_get(issue_row, "searchable_text") or _safe_get(issue_row, "summary")
            issue_tokens = extract_keywords(str(issue_text), include_report_stopwords=False)
            jira_data.append((issue_row, issue_tokens))

        results: list[MatchResult] = []

        # Limit report rows to prevent explosion - take only top match
        report_row = report_rows.iloc[0] if not report_rows.empty else None

        if report_row is not None:
            report_context = build_search_context(
                report_name=_safe_get(report_row, "name", report_name),
                workspace_name=_safe_get(report_row, "workspace_name"),
                app_name=_safe_get(report_row, "app_name"),
            )
            context_tokens = extract_keywords(report_context)
            effective_query_tokens = sorted(set(query_tokens) | set(context_tokens))

            for issue_row, issue_tokens in jira_data:
                score_detail = score_match(
                    query_tokens=effective_query_tokens,
                    candidate_tokens=issue_tokens,
                    query_name=_safe_get(report_row, "name", report_name),
                    candidate_name=_safe_get(issue_row, "summary"),
                )
                results.append(
                    self._build_result(
                        report_row=report_row,
                        issue_row=issue_row,
                        report_name=report_name,
                        normalized_query=normalized_query,
                        score_detail=score_detail,
                    )
                )

        deduped_results = self._dedupe_results(results)
        deduped_results.sort(key=lambda item: item.score, reverse=True)

        total_time = time.time() - start_time
        logger.debug(
            f"Matched report '{report_name}' in {total_time:.2f}s - found {len(deduped_results)} unique results"
        )

        return deduped_results[:limit]

    def _find_report_rows(self, normalized_query: str, query_tokens: list[str]) -> pd.DataFrame:
        """Find Power BI rows relevant to the requested report using fuzzy matching.

        Matches against report name, workspace name, and app name with scoring.
        Returns rows ranked by relevance score.
        """
        if self.powerbi_reports.empty or "name" not in self.powerbi_reports.columns:
            return pd.DataFrame()

        # Build search fields for each row
        def build_search_fields(row: pd.Series) -> dict[str, str]:
            """Extract searchable fields from a report row."""
            return {
                "name": normalize_text(str(_safe_get(row, "name"))),
                "workspace_name": normalize_text(str(_safe_get(row, "workspace_name"))),
                "app_name": normalize_text(str(_safe_get(row, "app_name"))),
            }

        # Score each row based on fuzzy matching across all fields
        scored_rows: list[tuple[float, pd.Series]] = []
        for _, row in self.powerbi_reports.iterrows():
            fields = build_search_fields(row)

            # Calculate match scores for each field
            name_score = self._calculate_field_match_score(fields["name"], normalized_query, query_tokens)
            workspace_score = self._calculate_field_match_score(
                fields["workspace_name"], normalized_query, query_tokens
            )
            app_score = self._calculate_field_match_score(fields["app_name"], normalized_query, query_tokens)

            # Weighted combination: report name is most important
            total_score = (name_score * 0.6) + (workspace_score * 0.25) + (app_score * 0.15)

            if total_score > 0:
                scored_rows.append((total_score, row))

        if not scored_rows:
            return pd.DataFrame()

        # Sort by score descending and return top matches
        scored_rows.sort(key=lambda x: x[0], reverse=True)

        # Include rows with score above threshold (0.3) or at least the top match
        threshold = 0.3
        top_score = scored_rows[0][0] if scored_rows else 0
        filtered_rows = [row for score, row in scored_rows if score >= threshold or score == top_score]

        if not filtered_rows:
            filtered_rows = [scored_rows[0][1]] if scored_rows else []

        return pd.DataFrame(filtered_rows)

    def _calculate_field_match_score(self, field_value: str, normalized_query: str, query_tokens: list[str]) -> float:
        """Calculate fuzzy match score between a field value and query.

        Uses multiple strategies:
        - Exact normalized match (highest score)
        - Substring containment
        - Token overlap (Jaccard similarity)
        """
        if not field_value or not normalized_query:
            return 0.0

        scores = []

        # Exact normalized match
        if field_value == normalized_query:
            scores.append(1.0)

        # Substring match (query contained in field)
        if normalized_query in field_value:
            scores.append(0.8)

        # Field contained in query
        if field_value in normalized_query and len(field_value) > 3:
            scores.append(0.6)

        # Token overlap using Jaccard similarity
        field_tokens = extract_keywords(field_value, include_report_stopwords=False)
        if field_tokens and query_tokens:
            token_score = calculate_token_overlap(field_tokens, query_tokens)
            if token_score > 0:
                scores.append(token_score * 0.7)

        # Partial word matching (e.g., "Sales" matches "SalesPipeline")
        for query_token in query_tokens:
            if len(query_token) >= 3:
                for field_token in field_tokens:
                    if query_token in field_token or field_token in query_token:
                        scores.append(0.5)
                        break

        return max(scores) if scores else 0.0

    def _dedupe_results(self, results: list[MatchResult]) -> list[MatchResult]:
        """Keep the highest-scoring result per Jira issue key."""
        deduped: dict[tuple[str | None, str | None], MatchResult] = {}
        for result in results:
            key = (result.jira_issue_key, result.jira_summary)
            existing = deduped.get(key)
            if existing is None or result.score > existing.score:
                deduped[key] = result
        return list(deduped.values())

    def _build_result(
        self,
        report_row: dict[str, Any],
        issue_row: dict[str, Any],
        report_name: str,
        normalized_query: str,
        score_detail: ScoreDetail,
    ) -> MatchResult:
        """Create final result object with concise evidence."""
        evidence = list(score_detail.evidence)

        # Safely extract values, handling pandas NaN
        workspace_name = self._safe_get_str(report_row, "workspace_name")
        app_name = self._safe_get_str(report_row, "app_name")
        workspace_id = self._safe_get_str(report_row, "workspace_id")
        app_id = self._safe_get_str(report_row, "app_id")
        report_id = self._safe_get_str(report_row, "report_id")
        web_url = self._safe_get_str(report_row, "web_url")
        embed_url = self._safe_get_str(report_row, "embed_url")
        jira_issue_key = self._safe_get_str(issue_row, "issue_key")
        jira_summary = self._safe_get_str(issue_row, "summary")

        # Build URLs for linked items
        jira_url = self._build_jira_url(jira_issue_key)
        report_url = self._build_powerbi_url(workspace_id, report_id, web_url)
        workspace_url = self._build_workspace_url(workspace_id)
        app_url = self._build_app_url(app_id)

        if workspace_name:
            evidence.append(f"Workspace: {workspace_name}")
        if app_name:
            evidence.append(f"App: {app_name}")
        if jira_issue_key:
            evidence.append(f"Jira issue: {jira_issue_key}")

        return MatchResult(
            report_name=report_name,
            normalized_query=normalized_query,
            score=score_detail.final_score,
            confidence=score_detail.confidence,
            jira_issue_key=jira_issue_key,
            jira_summary=sanitize_for_display(jira_summary),
            jira_url=jira_url,
            workspace_name=workspace_name,
            workspace_id=workspace_id,
            workspace_url=workspace_url,
            app_name=app_name,
            app_id=app_id,
            app_url=app_url,
            report_id=report_id,
            web_url=report_url,  # Use reconstructed or existing URL
            embed_url=embed_url,
            evidence=evidence,
        )

    def _safe_get_str(self, row: dict[str, Any], key: str) -> str | None:
        """Safely extract string value from row, handling pandas NaN and pd.NA."""
        import math

        value = row.get(key)
        # Handle None, pd.NA, and NaN values
        if value is None:
            return None
        # Handle pandas NA (NAType)
        if isinstance(value, type(pd.NA)) and pd.isna(value):
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        str_value = str(value).strip()
        return str_value if str_value and str_value.lower() != "nan" else None
