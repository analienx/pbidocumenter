"""Clean-host PBIPDocumenter + pinned VQS consumer integration smoke.

Runs in a GitHub-hosted ephemeral environment; never uploads report/model files.
A blocked quality verdict is valid evidence and is never promoted to pass.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

REPORT = Path("examples/contoso-retail").resolve()
EXIT = {"pass": 0, "fail": 1, "blocked": 2}


def source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        name = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def main() -> None:
    if not (REPORT / "Contoso Retail.pbip").is_file():
        raise RuntimeError("expected exact public synthetic PBIP sample")
    source_before = source_fingerprint(REPORT)
    with tempfile.TemporaryDirectory(prefix="pbip-vqs-clean-contract-") as location:
        root = Path(location)
        for mode in ("review", "repair"):
            command = [
                "pbip-quality", str(REPORT), "--private-root", str(root),
                "--mode", mode, "--scope", "static",
                "--run-id", "clean-" + mode,
            ]
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=240, check=False, shell=False)
            try:
                result = json.loads(process.stdout)
            except ValueError as exc:
                raise RuntimeError("installed CLI did not return JSON") from exc
            verdict = result.get("verdict")
            if verdict not in EXIT or process.returncode != EXIT[verdict]:
                raise RuntimeError("exit/verdict mismatch from installed CLI")
            if (result.get("evidence_verified") is not True
                    or result.get("engine") != "vqs.run/1"
                    or result.get("promotion_performed") is not False):
                raise RuntimeError("unverified, unknown or promoted result")
            if result.get("run_id") != "clean-" + mode:
                raise RuntimeError("run identity mismatch")
            report_sha = result.get("source_sha256")
            if not isinstance(report_sha, str) or len(report_sha) != 64:
                raise RuntimeError("source digest missing")
            evidence_dir = Path(result["run_dir"]).resolve()
            if not evidence_dir.is_relative_to(root.resolve()):
                raise RuntimeError("private evidence escaped ephemeral root")
            candidate = result.get("candidate")
            if candidate and not Path(candidate).resolve().is_relative_to(
                (root / "candidates").resolve()
            ):
                raise RuntimeError("candidate escaped ephemeral root")
            print(f"Verified installed PBIP + VQS {mode}: {verdict}; no promotion")
    if source_fingerprint(REPORT) != source_before:
        raise RuntimeError("the original PBIP was changed by a quality check")


if __name__ == "__main__":
    main()

