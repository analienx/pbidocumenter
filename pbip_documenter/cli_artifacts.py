"""Provenance evidence for completed, local, editable Word artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pbip_documenter.config import VERSION


def file_sha256(path: Path) -> str:
    """Hash a generated document without copying contents into JSON results."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(docx: Path) -> Path:
    return docx.with_suffix(".manifest.json")


def artifact_record(
    docx: Path, *, project: str, source_sha256: str, mode: str,
    parser: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generator": "pbip-documenter",
        "generator_version": VERSION,
        "project": project,
        "mode": mode,
        "document": str(docx.resolve()),
        "document_sha256": file_sha256(docx),
        "source_sha256": source_sha256,
        "bytes": docx.stat().st_size,
        "parser": parser,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_manifest(path: Path, content: dict[str, Any], *, no_overwrite: bool = False) -> None:
    """Publish the JSON evidence atomically beside its document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pbipdoc-manifest-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(content, stream, ensure_ascii=True, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if no_overwrite:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
