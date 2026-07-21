"""Matching and enrichment layer for Power BI and Jira data."""

from pbip_documenter.inventory.matching.scoring import ScoreDetail
from pbip_documenter.inventory.matching.service import MatchingService, MatchResult

__all__ = [
    "MatchingService",
    "MatchResult",
    "ScoreDetail",
]
