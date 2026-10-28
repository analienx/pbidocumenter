"""Runtime consumer attestation: never confuse native pixels with G2/G6."""
from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from pbip_documenter import quality

MAGIC = b"\x89PNG\r\n\x1a\n"


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str, dict[str, Any]]:
    report = tmp_path / "source" / "Example.Report"
    (report / "definition").mkdir(parents=True)
    (report.parent / "Example.pbip").write_text("{}", encoding="utf8")
    root = tmp_path / "evidence" / "run-one"
    folder = root / "renders-baseline"
    folder.mkdir(parents=True)
    png = MAGIC + b"x" * 2048
    (folder / "P1.png").write_bytes(png)
    source = "a" * 64
    receipt = {
        "source_sha256": source,
        "desktop": {"pid": 32, "report": str(report.parent / "Example.pbip"),
                    "save_state": {"reported_unsaved": False}},
        "page_images": {"P1": "P1.png"},
        "files": {"P1.png": hashlib.sha256(png).hexdigest()},
        "modeling": {"status": "ready"},
    }
    (folder / "capture-manifest.json").write_text(json.dumps(receipt), encoding="utf8")
    evidence = types.ModuleType("vqs.evidence")
    evidence.png_size = lambda _: (2560, 1440)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "vqs.evidence", evidence)
    return root, report, source, receipt


def _verify(root: Path, report: Path, source: str) -> dict[str, Any]:
    return quality.verify_desktop_capture(
        root, report, source, 32,
        [{"stage": "baseline_capture", "status": "pass"}],
    )


def test_desktop_capture_source_pid_saved_identity_and_image_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, report, source, _ = _fixture(tmp_path, monkeypatch)
    result = _verify(root, report, source)
    assert result == {
        "status": "source_bound", "page_count": 1, "pid": 32,
        "local_model_ready": True, "visual_review_approved": False,
    }


@pytest.mark.parametrize("breakage", [
    "wrong_pid", "dirty", "wrong_pbip", "wrong_source",
    "mismatched_hash", "wrong_png", "escaped_filename",
    "missing_capture", "wrong_stage",
])
def test_corrupt_or_unavailable_native_capture_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, breakage: str,
) -> None:
    root, report, source, manifest = _fixture(tmp_path, monkeypatch)
    path = root / "renders-baseline" / "capture-manifest.json"
    stage = [{"stage": "baseline_capture", "status": "pass"}]
    if breakage == "wrong_pid":
        manifest["desktop"]["pid"] = 34
    elif breakage == "dirty":
        manifest["desktop"]["save_state"]["reported_unsaved"] = True
    elif breakage == "wrong_pbip":
        manifest["desktop"]["report"] = str(report.parent / "Other.pbip")
    elif breakage == "wrong_source":
        manifest["source_sha256"] = "0" * 64
    elif breakage == "mismatched_hash":
        manifest["files"]["P1.png"] = "0" * 64
    elif breakage == "wrong_png":
        (root / "renders-baseline" / "P1.png").write_bytes(b"not a PNG" * 350)
    elif breakage == "escaped_filename":
        manifest["page_images"]["P1"] = "../outside.png"
    elif breakage == "missing_capture":
        path.unlink()
    elif breakage == "wrong_stage":
        stage[0]["status"] = "blocked"
    if breakage not in ("missing_capture",):
        path.write_text(json.dumps(manifest), encoding="utf8")
    if breakage == "wrong_stage":
        assert quality.verify_desktop_capture(root, report, source, 32, stage) == (
            {"status": "not_verified", "page_count": 0})
    else:
        with pytest.raises((ValueError, OSError)):
            _verify(root, report, source)


def test_desktop_requires_explicit_permission_config_and_exact_pid(
    tmp_path: Path,
) -> None:
    report = tmp_path / "source" / "Example.Report"
    (report / "definition").mkdir(parents=True)
    assert quality.quality(report, tmp_path / "evidence", scope="desktop",
                           pid=1)["verdict"] == "blocked"
    assert "explicit authorized --config" in quality.quality(
        report, tmp_path / "evidence", scope="desktop", pid=1)["reason"]
    assert "PID" in quality.quality(
        report, tmp_path / "evidence", scope="desktop")["reason"]


def test_desktop_capture_does_not_convert_missing_reviewer_to_release_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, report, source, _ = _fixture(tmp_path, monkeypatch)
    record = _verify(root, report, source)
    assert record["status"] == "source_bound"
    assert record["visual_review_approved"] is False
    assert record["local_model_ready"] is True
