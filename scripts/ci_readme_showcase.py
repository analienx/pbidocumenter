"""CI gate for README link integrity, authentic visual evidence and sample files."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs/images"
PROVENANCE = IMAGES / "showcase-provenance.json"

EXPECTED_SHOTS = {
    "contents.jpg",
    "semantic-model.jpg",
    "model-lineage.jpg",
    "power-query.jpg",
    "dax-measures.jpg",
    "report-wireframe.jpg",
    "technical-observations.jpg",
    "detail-lineage.jpg",
    "detail-wireframe.jpg",
}
EXPECTED_SAMPLES = {
    "docs/samples/Contoso-Retail-full.docx",
    "docs/samples/Contoso-Retail-concise.docx",
    "docs/samples/Contoso-Retail-full.pdf",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG file: {path}"
    return (
        int.from_bytes(data[16:20], "big"),
        int.from_bytes(data[20:24], "big"),
    )


def verify() -> None:
    meta = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    assert meta["fixture"] == "examples/contoso-retail"
    tree = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD:examples/contoso-retail"],
        text=True,
    ).strip()
    assert tree == meta["fixture_git_tree"], "Contoso fixture changed; regenerate screenshots/samples"

    shots = {Path(path).name for path in meta["images"] if path.startswith("showcase/")}
    assert shots == EXPECTED_SHOTS, f"Unexpected source-derived screenshot inventory: {shots}"
    assert set(meta["samples"]) == EXPECTED_SAMPLES

    for relative, info in meta["images"].items():
        path = IMAGES / relative
        assert path.is_file(), f"Missing gallery image: {relative}"
        assert path.stat().st_size < 750_000, f"Unoptimized image: {relative}"
        assert sha256(path) == info["sha256"], f"Tampered screenshot: {relative}"
        if path.suffix == ".jpg":
            assert path.read_bytes()[:3] == b"\xff\xd8\xff", f"Invalid JPEG: {relative}"
        if path.suffix == ".png":
            assert dimensions(path)[0] > 1000

    assert dimensions(IMAGES / "social-preview.png") == (1280, 640)
    assert dimensions(IMAGES / "hero-product.png") == (1440, 720)
    assert (IMAGES / "social-preview.png").stat().st_size < 1_000_000

    for relative, info in meta["samples"].items():
        path = ROOT / relative
        assert path.is_file(), f"Missing committed sample: {relative}"
        assert sha256(path) == info["sha256"], f"Sample was altered without updating evidence: {relative}"
        if path.suffix == ".pdf":
            assert path.read_bytes()[:5] == b"%PDF-"
            assert meta["pdf_sha256"]["contoso-full.pdf"] == info["sha256"]
        elif path.suffix == ".docx":
            with ZipFile(path) as archive:
                assert archive.testzip() is None
                assert "word/document.xml" in archive.namelist()

    for file in (
        ROOT / "README.md",
        ROOT / "docs/EXAMPLES.md",
        ROOT / "docs/AGENT_WORKFLOW.md",
        ROOT / "docs/images/README.md",
    ):
        text = file.read_text(encoding="utf-8")
        links = re.findall(r'(?:!\[[^\]]*\]\(|src=")([^)"\s]+)', text)
        for link in links:
            if link.startswith(("docs/images/", "images/")):
                assert (file.parent / link).is_file(), f"Broken screenshot: {file.name} -> {link}"

    print(
        f"OK: 9 authentic page images/crops, 2 banners, 3 permanent samples, "
        f"verified source tree {tree[:12]}"
    )


if __name__ == "__main__":
    verify()
