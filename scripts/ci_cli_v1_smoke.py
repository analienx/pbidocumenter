"""Installed wheel CLI smoke executed on GitHub-hosted Linux and Windows runners."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "contoso-retail"


def run(executable: str, cwd: Path, *args: str) -> tuple[int, dict]:
    process = subprocess.run(
        [executable, *args, "--json"], cwd=cwd, capture_output=True, text=True,
        check=False, timeout=180,
    )
    assert not process.stderr.strip(), f"Unexpected stderr on JSON CLI: {process.stderr[-800:]}"
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(f"Expected one JSON payload, got {process.stdout[:800]}") from error
    assert payload["schema_version"] == "1.0"
    assert payload["exit_code"] == process.returncode
    assert payload["command"] == args[0]
    return process.returncode, payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-wheel", action="store_true")
    args = parser.parse_args()
    if args.install_wheel:
        wheels = list((Path(__file__).resolve().parents[1] / "dist").glob("*.whl"))
        assert len(wheels) == 1, f"Expected exactly one built wheel, got {wheels}"
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheels[0])],
            check=True, timeout=180,
        )
    executable = shutil.which("pbip-documenter")
    assert executable, "Console script was not installed"

    with tempfile.TemporaryDirectory(prefix="pbip-cli-installed-") as temp:
        root = Path(temp)
        code, doctor = run(executable, root, "doctor")
        assert code == 0 and all(check["ok"] for check in doctor["checks"])

        code, result = run(executable, root, "validate", str(EXAMPLE), "--strict")
        assert code == 0 and result["projects"][0]["valid"]

        code, result = run(executable, root, "inspect", str(EXAMPLE), "--details")
        assert code == 0
        summary = result["projects"][0]["inventory"]
        for key, expected in [
            ("tables", 12), ("measures", 55), ("relationships", 19),
            ("report_pages", 5), ("report_visuals", 54),
        ]:
            assert summary[key] == expected, (key, summary)
        assert len(result["projects"][0]["source_sha256"]) == 64

        destination = root / "contoso-cli.docx"
        code, preview = run(
            executable, root, "generate", str(EXAMPLE),
            "--mode", "default", "--strict", "--output", str(destination), "--dry-run", "--manifest",
        )
        assert code == 0 and preview["dry_run"]
        assert preview["planned_outputs"] == [str(destination.resolve())]
        assert not destination.exists() and not destination.with_suffix(".manifest.json").exists()
        code, result = run(
            executable, root, "generate", str(EXAMPLE),
            "--mode", "default", "--strict", "--output", str(destination),
            "--manifest", "--no-overwrite",
        )
        assert code == 0, result
        assert result["outputs"] == [str(destination.resolve())]
        assert destination.stat().st_size > 10_000
        sidecar = destination.with_suffix(".manifest.json")
        assert sidecar.exists()
        manifest = json.loads(sidecar.read_text(encoding="utf-8"))
        assert manifest["document_sha256"] == result["artifacts"][0]["document_sha256"]
        assert manifest["source_sha256"] == result["projects"][0]["source_sha256"]
        assert len(manifest["document_sha256"]) == 64
        code, replay = run(
            executable, root, "generate", str(EXAMPLE),
            "--mode", "default", "--strict", "--output", str(destination),
            "--manifest", "--no-overwrite",
        )
        assert code == 2
        assert any(d["code"] == "OUTPUT_EXISTS" for d in replay["diagnostics"])
        assert json.loads(sidecar.read_text(encoding="utf-8")) == manifest
        with ZipFile(destination) as archive:
            assert archive.testzip() is None
            assert "word/document.xml" in archive.namelist()
            xml = archive.read("word/document.xml")
            assert b"wpg:wgp" in xml and b"wps:wsp" in xml, "Native editable Word diagrams missing"

        broken_project = root / "Broken"
        bad = broken_project / "Broken.SemanticModel" / "definition" / "tables"
        bad.mkdir(parents=True)
        (bad / "Invalid.tmdl").write_text("there is no table declaration here", encoding="utf-8")
        code, result = run(executable, root, "validate", str(broken_project), "--strict")
        assert code == 3
        assert "TMDL_TABLE_UNPARSED" in [
            d["code"] for d in result["projects"][0]["diagnostics"]
        ]
        forbidden = root / "must-not-write.docx"
        code, result = run(
            executable, root, "generate", str(broken_project),
            "--strict", "--output", str(forbidden),
        )
        assert code == 3 and not forbidden.exists()
        code, result = run(executable, root, "validate", "--unknown-option")
        assert code == 2 and result["diagnostics"][0]["code"] == "ARGUMENT_INVALID"

        print(f"OK: installed CLI on {sys.platform}; doctor/validate/inspect/generate JSON and DOCX verified")


if __name__ == "__main__":
    main()
