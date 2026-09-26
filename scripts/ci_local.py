"""Local replica of the GitHub CI test job.

Runs the same gates as ``.github/workflows/ci.yml`` (pytest, ruff,
mypy) against a project-local ``.venv``, creating and provisioning it
on first run. Use it whenever hosted CI is unavailable or before
pushing::

    python scripts/ci_local.py
    python scripts/ci_local.py --skip-install   # reuse the current .venv
    python scripts/ci_local.py --pytest-only    # skip ruff/mypy

Exit code is 0 only when every selected gate passes. The script never
touches the system interpreter: with no ``.venv`` it creates one via
``uv`` when available, else ``python -m venv``.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                          timeout=600, **kwargs)


def ensure_env(skip_install: bool) -> Path:
    """Create .venv (if missing) and install .[all]; return its python."""
    python = _venv_python()
    if not python.is_file():
        if shutil.which("uv") is not None:
            created = _run(["uv", "venv", str(VENV)])
            if created.returncode != 0:
                raise SystemExit(f"uv venv failed:\n{created.stderr}")
        else:
            created = _run([sys.executable, "-m", "venv", str(VENV)])
            if created.returncode != 0:
                raise SystemExit(f"venv creation failed:\n{created.stderr}")
    if not skip_install:
        pip = ["uv", "pip", "install", "--python", str(python), ".[all]"]
        if shutil.which("uv") is None:
            pip = [str(python), "-m", "pip", "install", ".[all]"]
        installed = _run(pip)
        if installed.returncode != 0:
            raise SystemExit(f"dependency install failed:\n{installed.stderr}")
    return python


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CI gates locally.")
    parser.add_argument("--skip-install", action="store_true",
                        help="Reuse the current .venv without reinstalling.")
    parser.add_argument("--pytest-only", action="store_true",
                        help="Run pytest only, skip ruff and mypy.")
    args = parser.parse_args(argv)

    python = ensure_env(args.skip_install)
    gates = [["-m", "pytest", "pbip_documenter/tests", "-q"]]
    if not args.pytest_only:
        gates += [[ "-m", "ruff", "check", "."],
                  ["-m", "mypy", "pbip_documenter"]]
    failed = []
    for gate in gates:
        print(f"$ {python.name} {' '.join(gate)}", flush=True)
        result = _run([str(python), *gate])
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-6:])
        print(tail, flush=True)
        if result.returncode != 0:
            failed.append(gate[1])
    if failed:
        print(f"LOCAL CI FAILED: {', '.join(failed)}")
        return 1
    print("LOCAL CI PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
