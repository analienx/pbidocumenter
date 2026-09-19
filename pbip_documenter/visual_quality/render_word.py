"""Portable Word-to-PNG evidence adapter using LibreOffice and Poppler.

Requires external `soffice` and `pdftoppm` executables. Failure is a hard gate;
never substitute DOCX text extraction for page-image verification.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .evidence import digest, png_size


def render_word(source: Path, renders: Path, soffice: str = "soffice",
                pdftoppm: str = "pdftoppm") -> dict:
    source, renders = source.resolve(), renders.resolve()
    if source.suffix.lower() != ".docx" or not source.is_file():
        raise ValueError("Expected an existing Word .docx")
    renders.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pbip-word-review-") as directory:
        temp = Path(directory)
        profile = (temp / "lo-profile").as_uri()
        subprocess.run([soffice, "--headless", f"-env:UserInstallation={profile}",
                        "--convert-to", "pdf", "--outdir", str(temp), str(source)],
                       check=True, timeout=240, capture_output=True)
        pdf = temp / f"{source.stem}.pdf"
        if not pdf.is_file() or pdf.stat().st_size < 100:
            raise RuntimeError("Word rendering produced no valid PDF intermediary")
        subprocess.run([pdftoppm, "-f", "1", "-r", "150", "-png",
                        str(pdf), str(temp / "page")],
                       check=True, timeout=360, capture_output=True)
        images = sorted(temp.glob("page-*.png"), key=lambda p: int(re.search(r"-(\d+)$", p.stem)[1]))
        if not images:
            raise RuntimeError("Word rendering returned no page PNGs")
        files: dict[str, str] = {}
        page_order: list[str] = []
        for index, original in enumerate(images, start=1):
            png_size(original)
            name = f"page-{index:04d}.png"
            target = renders / name
            target.write_bytes(original.read_bytes())
            page_order.append(name)
            files[name] = digest(target)
    manifest = {"schema": 1, "surface": "document", "source_sha256": digest(source),
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "renderer": "LibreOffice + pdftoppm (150 dpi)",
                "page_order": page_order, "files": files}
    (renders / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Word pages for visual QA")
    parser.add_argument("source", type=Path)
    parser.add_argument("renders", type=Path)
    parser.add_argument("--soffice", default="soffice")
    parser.add_argument("--pdftoppm", default="pdftoppm")
    args = parser.parse_args()
    evidence = render_word(args.source, args.renders, args.soffice, args.pdftoppm)
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
