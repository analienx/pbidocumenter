"""Cache path management for PBIP Documenter."""

import typing
from pathlib import Path


class CachePaths:
    """Manages cache directory paths for the documenter."""

    def __init__(self: typing.Any, base_dir: Path | None = None) -> None:
        """Initialize cache paths.

        Args:
            base_dir: Base directory for cache. Defaults to .pbip_cache in current directory.
        """
        self.base_dir = base_dir or Path(".pbip_cache")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_inventory_path(self: typing.Any) -> typing.Any:
        """Get path for inventory cache."""
        path = self.base_dir / "inventory"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_source_dir(self: typing.Any, source: str) -> typing.Any:
        """Get the root directory for one inventory source."""
        path = self.get_inventory_path() / source
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_raw_pages_dir(self: typing.Any, source: str) -> typing.Any:
        """Get the directory containing raw API response pages."""
        path = self.get_source_dir(source) / "raw"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_curated_path(self: typing.Any, source: str, filename: str) -> typing.Any:
        """Get a normalized cache artifact path."""
        directory = self.get_source_dir(source) / "curated"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / filename

    def get_export_path(self: typing.Any, source: str, filename: str) -> typing.Any:
        """Get a human-readable export artifact path."""
        directory = self.get_source_dir(source) / "exports"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / filename

    def get_manifest_path(self: typing.Any, source: str) -> typing.Any:
        """Get the source refresh manifest path."""
        return self.get_source_dir(source) / "manifest.json"

    def get_matching_path(self: typing.Any) -> typing.Any:
        """Get path for matching results cache."""
        path = self.base_dir / "matching"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_augmentation_path(self: typing.Any) -> typing.Any:
        """Get path for augmentation cache."""
        path = self.base_dir / "augmentation"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def clear(self: typing.Any) -> typing.Any:
        """Clear all cache directories."""
        import shutil

        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)
            self.base_dir.mkdir(parents=True, exist_ok=True)
