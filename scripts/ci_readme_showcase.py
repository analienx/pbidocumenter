"""Fail CI if public showcase evidence or README images become stale/broken."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "images"
PROVENANCE = IMAGES / "showcase-provenance.json"
EXPECTED_SHOTS = {
    "contents.jpg",
    "semantic-model.jpg",
    "model-lineage.jpg",
    "power-query.jpg",
    "dax-measures.jpg",
    "report-wireframe.jpg",
    "technical-observations.jpg",
}


def verify() -> None:
    meta = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    assert meta["fixture"] == "examples/contoso-retail"
    expected_tree = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD:examples/contoso-retail"],
        text=True,
    ).strip()
    assert meta["fixture_git_tree"] == expected_tree, "Screenshots are stale: Contoso fixture changed"

    shots = {Path(path).name for path in meta["images"] if path.startswith("showcase/")}
    assert shots == EXPECTED_SHOTS, f"Unexpected gallery image inventory: {shots}"
    for relative, info in meta["images"].items():
        path = IMAGES / relative
        assert path.is_file(), f"Missing proof image: {relative}"
        assert path.stat().st_size < 600_000, f"Image too large: {relative}"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info["sha256"], (
            f"Image provenance mismatch: {relative}"
        )
        if path.suffix == ".jpg":
            assert path.read_bytes()[:3] == b"\xff\xd8\xff", f"Invalid JPEG: {relative}"
        elif path.suffix == ".png":
            assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG: {relative}"

    preview = IMAGES / "social-preview.png"
    assert preview.stat().st_size < 1_000_000, "Social preview exceeds GitHub's 1MB guidance"
    image_bytes = preview.read_bytes()
    dims = (int.from_bytes(image_bytes[16:20], "big"), int.from_bytes(image_bytes[20:24], "big"))
    assert dims == (1280, 640), f"Unexpected social-preview dimensions: {dims}"

    for file in (ROOT / "README.md", ROOT / "docs" / "EXAMPLES.md"):
        markdown = file.read_text(encoding="utf-8")
        # Check relative local screenshot links used by Markdown/HTML. GitHub
        # anchors and external URLs are not file paths.
        links = re.findall(r'(?:!\[[^\]]*\]\(|src=")([^)"\s]+)', markdown)
        for link in links:
            if not (link.startswith("docs/images/") or link.startswith("images/")):
                continue
            absolute = (file.parent / link).resolve()
            assert absolute.is_file(), f"Broken local screenshot link: {file.name} → {link}"

    print(f"OK: 7 authentic screenshots, social-preview 1280×640, fixture {expected_tree[:12]}")


if __name__ == "__main__":
    verify()
