"""Manifest tracking for inventory cache."""

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pbip_documenter.cache.atomic_write import atomic_write_json


class ManifestStatus(str, Enum):
    """Status of a manifest entry."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUCCESS = "completed"
    FAILED = "failed"
    STALE = "stale"


class ManifestEntry:
    """Single entry in the manifest."""

    def __init__(
        self,
        key: str,
        status: ManifestStatus,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.key = key
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "key": self.key,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManifestEntry":
        """Create entry from dictionary."""
        return cls(
            key=data["key"],
            status=ManifestStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )


class Manifest:
    """Manifest for tracking cached inventory data."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        source: str | None = None,
        generated_at: datetime | None = None,
        last_success_at: datetime | None = None,
        last_attempt_at: datetime | None = None,
        status: ManifestStatus | None = None,
        freshness_threshold_hours: int = 24,
        record_count: int = 0,
        error_summary: str | None = None,
    ) -> None:
        """Initialize manifest.

        Args:
            path: Path to manifest file. Defaults to .pbip_cache/manifest.json
        """
        self.path = path or Path(".pbip_cache/manifest.json")
        self.entries: dict[str, ManifestEntry] = {}
        self.source = source
        self.generated_at = generated_at
        self.last_success_at = last_success_at
        self.last_attempt_at = last_attempt_at
        self.status = status
        self.freshness_threshold_hours = freshness_threshold_hours
        self.record_count = record_count
        self.error_summary = error_summary
        self._load()

    def _load(self) -> None:
        """Load manifest from disk."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.source = data.get("source", self.source)
                self.generated_at = _parse_datetime(data.get("generated_at"))
                self.last_success_at = _parse_datetime(data.get("last_success_at"))
                self.last_attempt_at = _parse_datetime(data.get("last_attempt_at"))
                raw_status = data.get("status")
                self.status = ManifestStatus(raw_status) if raw_status else self.status
                self.freshness_threshold_hours = data.get("freshness_threshold_hours", self.freshness_threshold_hours)
                self.record_count = data.get("record_count", self.record_count)
                self.error_summary = data.get("error_summary", self.error_summary)
                for key, entry_data in data.get("entries", {}).items():
                    self.entries[key] = ManifestEntry.from_dict(entry_data)
            except (json.JSONDecodeError, KeyError, ValueError):
                # Reset if corrupted
                self.entries = {}

    def save(self, path: Path | None = None) -> None:
        """Save manifest to disk."""
        if path is not None:
            self.path = path
        data: dict[str, Any] = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
        }
        if self.source:
            data.update(
                {
                    "source": self.source,
                    "generated_at": self.generated_at.isoformat() if self.generated_at else None,
                    "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
                    "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
                    "status": self.status.value if self.status else None,
                    "freshness_threshold_hours": self.freshness_threshold_hours,
                    "record_count": self.record_count,
                    "error_summary": self.error_summary,
                }
            )
        atomic_write_json(self.path, data)

    @classmethod
    def load(cls, path: Path) -> "Manifest | None":
        """Load a source manifest when it exists."""
        return cls(path) if path.exists() else None

    def get(self, key: str) -> ManifestEntry | None:
        """Get entry by key."""
        return self.entries.get(key)

    def set(
        self,
        key: str,
        status: ManifestStatus,
        metadata: dict[str, Any] | None = None,
    ) -> ManifestEntry:
        """Set entry status."""
        now = datetime.now(timezone.utc)
        if key in self.entries:
            entry = self.entries[key]
            entry.status = status
            entry.updated_at = now
            if metadata:
                entry.metadata.update(metadata)
        else:
            entry = ManifestEntry(
                key=key,
                status=status,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
            )
            self.entries[key] = entry
        return entry

    def is_fresh(self, key: str | None = None, max_age_hours: int = 24) -> bool:
        """Check if entry exists and is fresh."""
        if key is None and self.source:
            if self.status != ManifestStatus.SUCCESS or self.last_success_at is None:
                return False
            age = datetime.now(timezone.utc).replace(tzinfo=None) - self.last_success_at.replace(tzinfo=None)
            return age.total_seconds() < self.freshness_threshold_hours * 3600
        entry = self.entries.get(key) if key is not None else None
        if not entry or entry.status != ManifestStatus.COMPLETED:
            return False

        age = datetime.now(timezone.utc).replace(tzinfo=None) - entry.updated_at.replace(tzinfo=None)
        return age.total_seconds() < (max_age_hours * 3600)

    def list_by_status(self, status: ManifestStatus) -> list[ManifestEntry]:
        """List all entries with given status."""
        return [e for e in self.entries.values() if e.status == status]

    def clear(self) -> None:
        """Clear all entries."""
        self.entries = {}
        if self.path.exists():
            self.path.unlink()


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
