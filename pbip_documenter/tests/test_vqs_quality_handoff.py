"""Confirm agent-driven VQS candidate fixes cannot silently bypass evidence."""
import json
import subprocess
from pathlib import Path

import pytest

from pbip_documenter import quality


@pytest.fixture
def report(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    p = project / "Sales.Report"
    (p / "definition").mkdir(parents=True)
    (project / "Sales.pbip").write_text("{}", encoding="utf8")
    return p


def test_sources(report: Path) -> None:
    assert quality.resolve_report(report) == report
    assert quality.resolve_report(report.parent / "Sales.pbip") == report
    assert quality.resolve_report(report.parent) == report


@pytest.mark.parametrize("scope,pid", [("desktop", None), ("static", 22)])
def test_wrong_runtime_is_blocked(
    report: Path, tmp_path: Path, scope: str, pid: int | None
) -> None:
    result = quality.quality(report, tmp_path / "evidence", scope=scope, pid=pid)
    assert result["verdict"] == "blocked"
    assert result["promotion_performed"] is False


def test_never_writes_inside_original(report: Path, tmp_path: Path) -> None:
    assert quality.quality(report, report / "evidence")["verdict"] == "blocked"
    assert quality.quality(report, report.parent / "private")["verdict"] == "blocked"
    used = tmp_path / "evidence" / "reused"
    used.mkdir(parents=True)
    assert quality.quality(report, used.parent, run_id="reused")["verdict"] == "blocked"


def test_missing_engine_is_blocked(report: Path, tmp_path: Path) -> None:
    result = quality.quality(report, tmp_path / "runs", python=str(tmp_path / "unknown.exe"))
    assert result["verdict"] == "blocked"
    assert not result.get("evidence_verified")


@pytest.mark.parametrize("fault", ["", "exit", "run_id", "source_sha", "chain", "candidate"])
def test_bounded_sealed_vqs_bridge(
    monkeypatch: pytest.MonkeyPatch, report: Path, tmp_path: Path, fault: str
) -> None:
    root, rid = tmp_path / "runs", "abc01"
    manifest = {
        "pipeline": "vqs.run/1", "sealed": True, "status": "blocked",
        "run_id": rid, "sealed_sha256": "a" * 64, "events_sha256": "b" * 64,
        "params": {
            "mode": "repair", "scope": "static", "report_dir": str(report),
            "candidate_root": str(root / "candidates" / rid),
            "source_sha256": "broken" if fault == "source_sha" else "c" * 64,
        },
    }

    def fake(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[3] == "run":
            directory = root / rid
            directory.mkdir(parents=True)
            (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf8")
            payload = {
                "verdict": "blocked", "run_id": "wrong" if fault == "run_id" else rid,
                "run_dir": str(directory),
                "summary": {"candidate": str(report) if fault == "candidate" else None},
            }
            return subprocess.CompletedProcess(
                args, 0 if fault == "exit" else 2, json.dumps(payload), "",
            )
        if args[3] == "run-status":
            sealed = json.loads(json.dumps(manifest))
            if fault == "chain":
                sealed["events_sha256"] = "e" * 64
            data = {"verdict": "blocked", "run_id": rid, "run_dir": str(root / rid),
                    "provenance": {"manifest": sealed}}
            return subprocess.CompletedProcess(args, 2, json.dumps(data), "")
        raise AssertionError("unexpected action")

    monkeypatch.setattr(quality.subprocess, "run", fake)
    result = quality.quality(report, root, run_id=rid)
    assert result["verdict"] == "blocked"
    assert bool(result.get("evidence_verified")) == (fault == "")
    assert result["promotion_performed"] is False


def test_missing_report_cli_fails_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = quality.main([str(tmp_path / "missing.pbip"), "--private-root",
                           str(tmp_path / "runs")])
    assert status == 2
    assert json.loads(capsys.readouterr().out)["verdict"] == "blocked"
