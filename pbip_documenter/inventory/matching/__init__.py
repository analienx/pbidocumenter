"""Matching and enrichment layer for Power BI and Jira data."""

import typing

from pbip_documenter.inventory.matching.scoring import ScoreDetail
from pbip_documenter.inventory.matching.service import MatchingService, MatchResult

__all__: list[typing.Any] = [
    "MatchingService",
    "MatchResult",
    "ScoreDetail",
]
