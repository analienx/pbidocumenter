"""Refresh policy for inventory cache."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

from pbip_documenter.cache.manifest import Manifest, ManifestEntry, ManifestStatus


class RefreshDecision(Enum):
    """Decision for cache refresh."""

    USE_CACHE = "use_cache"
    REFRESH = "refresh"
    FORCE_REFRESH = "force_refresh"


@dataclass
class RefreshPolicy:
    """Policy for determining when to refresh cached data."""

    max_age_hours: int = 24
    force_refresh: bool = False
    prefer_cache: bool = False

    def decide(
        self,
        entry: Optional[ManifestEntry],
        cache_file: Optional[Path] = None,
    ) -> RefreshDecision:
        """Decide whether to use cache or refresh.

        Args:
            entry: Manifest entry for the cached data
            cache_file: Path to the cached file

        Returns:
            RefreshDecision indicating what action to take
        """
        if self.force_refresh:
            return RefreshDecision.FORCE_REFRESH

        if not entry or entry.status != ManifestStatus.COMPLETED:
            return RefreshDecision.REFRESH

        # Check if cache file exists
        if cache_file and not cache_file.exists():
            return RefreshDecision.REFRESH

        # Check age
        age = datetime.utcnow() - entry.updated_at
        if age > timedelta(hours=self.max_age_hours):
            return RefreshDecision.REFRESH

        if self.prefer_cache:
            return RefreshDecision.USE_CACHE

        # Default: use cache if fresh
        return RefreshDecision.USE_CACHE

    def should_refresh(
        self,
        entry: Optional[ManifestEntry],
        cache_file: Optional[Path] = None,
    ) -> bool:
        """Check if refresh is needed.

        Args:
            entry: Manifest entry for the cached data
            cache_file: Path to the cached file

        Returns:
            True if refresh is needed
        """
        return self.decide(entry, cache_file) != RefreshDecision.USE_CACHE
