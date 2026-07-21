"""Atomic file write operations for cache."""

import contextlib
import json
import os
import tempfile
import typing
from pathlib import Path
from typing import Any

import pandas as pd


def atomic_write_json(path: Path, data: dict[str, Any]) -> typing.Any:
    """Write JSON data atomically to avoid corruption.

    Args:
        path: Target file path
        data: Data to serialize as JSON
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first
    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        # Atomic rename
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        with contextlib.suppress(OSError):
            os.unlink(temp_path)
        raise


def atomic_write_parquet(path: Path, df: pd.DataFrame) -> typing.Any:
    """Write DataFrame to parquet atomically.

    Args:
        path: Target file path
        df: DataFrame to write
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first
    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    os.close(fd)  # parquet writes directly to path
    try:
        df.to_parquet(temp_path, index=False)
        # Atomic rename
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        with contextlib.suppress(OSError):
            os.unlink(temp_path)
        raise
