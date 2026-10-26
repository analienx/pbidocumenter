"""Agent-facing VQS quality bridge; no DOCX generation or report promotion."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

EXIT = {"pass": 0, "fail": 1, "blocked": 2}


def blocked(reason: str, run_id: str | None) -> dict[str, Any]:
    return {"verdict": "blocked", "reason": reason, "run_id": run_id,
            "candidate": None, "promotion_performed": False}


def resolve_report(source: Path) -> Path:
    source = source.resolve(strict=True)
    if source.is_file() and source.suffix.lower() == ".pbip":
        report = source.with_name(source.stem + ".Report")
    elif source.is_dir() and source.name.endswith(".Report"):
        report = source
    elif source.is_dir():
        projects = list(source.glob("*.pbip"))
        if len(projects) != 1:
            raise ValueError("directory must contain exactly one PBIP")
        report = source / (projects[0].stem + ".Report")
    else:
        raise ValueError("expected a PBIP, project directory or .Report folder")
    report = report.resolve(strict=True)
    if not report.is_dir() or not (report / "definition").is_dir():
        raise ValueError("invalid .Report definition")
    return report


def quality(
    source: Path, private_root: Path, *, mode: str = "repair",
    run_id: str | None = None, scope: str = "static",
    pid: int | None = None, timeout: int = 240,
    python: str | None = None,
) -> dict[str, Any]:
    """Delegate to VQS and verify its signed-in-source sealed run status."""
    rid = run_id or "quality-" + uuid.uuid4().hex[:16]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", rid):
        return blocked("invalid run ID", rid)
    if mode not in ("repair", "review") or scope not in ("static", "desktop"):
        return blocked("invalid quality mode/scope", rid)
    if (scope == "desktop" and (pid is None or pid < 1)
            or scope == "static" and pid is not None):
        return blocked("Desktop PID required only for desktop mode", rid)
    try:
        report = resolve_report(Path(source))
        root = Path(private_root).resolve()
        # The source boundary is the *whole PBIP project*, not only its
        # .Report child. Otherwise evidence could land beside the model.
        project_root = report.parent
        if (root == project_root or root.is_relative_to(project_root)
                or report.is_relative_to(root)):
            raise ValueError("private evidence must be outside source project")
        run_dir = root / rid
        candidate_root = root / "candidates" / rid
        if (run_dir.exists() or run_dir.is_symlink()
                or candidate_root.exists() or candidate_root.is_symlink()):
            raise ValueError("existing run/candidate path; generate a new run ID")
        root.mkdir(parents=True, exist_ok=True)
        executable = python or sys.executable
        args = [executable, "-m", "vqs", "run", str(report),
                "--mode", mode, "--scope", scope, "--run-root", str(root),
                "--run-id", rid]
        if mode == "repair":
            args += ["--candidate-root", str(candidate_root)]
        if pid is not None:
            args += ["--pid", str(pid)]
        primary = subprocess.run(
            args, capture_output=True, text=True, shell=False,
            timeout=timeout, check=False,
        )
        result = json.loads(primary.stdout)
        verdict = result["verdict"]
        if (verdict not in EXIT or primary.returncode != EXIT[verdict]
                or result.get("run_id") != rid
                or Path(result["run_dir"]).resolve() != run_dir):
            raise ValueError("VQS return code/run identity mismatch")
        manifest_file = run_dir / "manifest.json"
        if manifest_file.is_symlink():
            raise ValueError("symlinked evidence not accepted")
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        params = manifest["params"]
        if (manifest.get("sealed") is not True
                or manifest.get("pipeline") != "vqs.run/1"
                or manifest.get("run_id") != rid
                or manifest.get("status") != {
                    "pass": "completed", "fail": "failed",
                    "blocked": "blocked",
                }[verdict]
                or params.get("mode") != mode or params.get("scope") != scope
                or Path(params["report_dir"]).resolve() != report):
            raise ValueError("sealed VQS manifest does not match source")
        sha = params.get("source_sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("missing source digest")
        if (mode == "repair"
                and Path(params["candidate_root"]).resolve() != candidate_root):
            raise ValueError("candidate root escaped private workspace")

        verified = subprocess.run(
            [executable, "-m", "vqs", "run-status", str(root), rid],
            capture_output=True, text=True, shell=False,
            timeout=timeout, check=False,
        )
        status = json.loads(verified.stdout)
        sealed = status.get("provenance", {}).get("manifest", {})
        if (verified.returncode != EXIT[verdict]
                or status.get("verdict") != verdict
                or status.get("run_id") != rid
                or Path(status["run_dir"]).resolve() != run_dir
                or sealed.get("sealed_sha256") != manifest.get("sealed_sha256")
                or sealed.get("events_sha256") != manifest.get("events_sha256")
                or sealed.get("params", {}).get("source_sha256") != sha):
            raise ValueError("VQS event-chain verification mismatch")
        summary = result.get("summary", {})
        if not isinstance(summary, dict):
            raise ValueError("missing quality summary")
        candidate = summary.get("candidate")
        if candidate and not Path(candidate).resolve().is_relative_to(candidate_root):
            raise ValueError("candidate escaped its private root")
        return {"verdict": verdict, "run_id": rid, "run_dir": str(run_dir),
                "report": str(report), "source_sha256": sha,
                "candidate": candidate, "summary": summary,
                "blocked_reasons": result.get("blocked_reasons", []),
                "evidence_verified": True, "promotion_performed": False,
                "engine": "vqs.run/1"}
    except (OSError, ValueError, KeyError, TypeError,
            subprocess.TimeoutExpired) as exc:
        return blocked(f"VQS evidence unavailable: {type(exc).__name__}: {exc}", rid)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fix supported Power BI issues in an isolated VQS candidate"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("repair", "review"), default="repair")
    parser.add_argument("--scope", choices=("static", "desktop"), default="static")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--timeout", type=int, default=240)
    opts = parser.parse_args(argv)
    if opts.timeout < 1:
        result = blocked("timeout must be positive", opts.run_id)
    else:
        result = quality(
            opts.source, opts.private_root, mode=opts.mode, scope=opts.scope,
            pid=opts.pid, run_id=opts.run_id, timeout=opts.timeout,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return EXIT[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())

