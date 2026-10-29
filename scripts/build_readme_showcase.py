"""Regenerate public, provenance-hashed screenshots from real CI document renders.

Run with Pillow and PyMuPDF installed, after downloading the corresponding
GitHub Actions DOCX-render-acceptance artifact. Never synthesize report data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pymupdf
from build_readme_hero import create as build_hero
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "tables_verified": 12,
    "measures_verified": 55,
    "relationships_verified": 19,
    "pages_verified": 5,
    "visuals_verified": 54,
}
PAGES = {
    "contents.jpg": ("full", 1),
    "semantic-model.jpg": ("full", 4),
    "model-lineage.jpg": ("full", 5),
    "power-query.jpg": ("full", 14),
    "dax-measures.jpg": ("full", 18),
    "report-wireframe.jpg": ("full", 21),
    "technical-observations.jpg": ("full", 26),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_pdf_page(pdf: Path, page: int) -> Image.Image:
    with pymupdf.open(pdf) as document:
        pixmap = document[page - 1].get_pixmap(matrix=pymupdf.Matrix(2.15, 2.15), alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--run-id", default="40870433647")
    parser.add_argument("--source-commit", default="ac6700c5d2c6adafcb784b2db4416c4d9fe99c9a")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs/images")
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve()
    out = args.out_dir.resolve()
    images = out / "showcase"
    images.mkdir(parents=True, exist_ok=True)

    report = json.loads((evidence / "word-render-acceptance.json").read_text(encoding="utf-8"))
    assert report["source_project"] == "examples/contoso-retail"
    for mode in ("full", "default"):
        inventory = report["documents"][mode]["inventory"]
        for key, value in EXPECTED.items():
            assert inventory[key] == value, f"{mode}: {key} changed; do not reuse historical screenshots"
        assert report["documents"][mode]["render"]["outside_page_blocks"] == 0

    tree = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD:examples/contoso-retail"],
        text=True,
    ).strip()
    provenance = {
        "fixture": "examples/contoso-retail",
        "fixture_git_tree": tree,
        "github_workflow_run": args.run_id,
        "source_commit": args.source_commit,
        "render_engine": "LibreOffice PDF from installed-wheel DOCX CI",
        "screenshot_truth": "Full pages: unmodified PDF renders; detail crops: original rendered page pixels; hero: decorative layout composed from real Word excerpts, not a Power BI Desktop screenshot.",
        "inventory": EXPECTED,
        "pdf_sha256": {},
        "images": {},
        "samples": {},
    }
    for mode in ("default", "full"):
        pdf = evidence / f"contoso-{mode}.pdf"
        provenance["pdf_sha256"][pdf.name] = digest(pdf)

    for name, (mode, page) in PAGES.items():
        path = images / name
        render_pdf_page(evidence / f"contoso-{mode}.pdf", page).save(
            path, "JPEG", quality=84, subsampling=0, optimize=True, progressive=True
        )
        provenance["images"][f"showcase/{name}"] = {
            "generated_document": f"contoso-{mode}.docx",
            "render_pdf": f"contoso-{mode}.pdf",
            "pdf_page_1based": page,
            "sha256": digest(path),
        }

    created = build_hero(out)
    for relative, path in created.items():
        provenance["images"][relative] = {
            "note": (
                "Authentic source-page crop"
                if relative.startswith("showcase/") else
                "Decorative layout composed from real generated Word-page crops"
            ),
            "source_pdf_pages_1based": [5, 21] if relative.endswith(".png") else (
                [5] if "lineage" in relative else [21]
            ),
            "sha256": digest(path),
        }

    sample_files = {
        "Contoso-Retail-full.docx": ("full", "docx"),
        "Contoso-Retail-concise.docx": ("default", "docx"),
        "Contoso-Retail-full.pdf": ("full", "pdf"),
    }
    for name, (mode, kind) in sample_files.items():
        sample = ROOT / "docs/samples" / name
        assert sample.is_file(), f"Missing verified, committed sample: {sample}"
        if kind == "pdf":
            assert digest(sample) == provenance["pdf_sha256"][f"contoso-{mode}.pdf"]
        provenance["samples"][f"docs/samples/{name}"] = {
            "mode": mode,
            "format": kind,
            "sha256": digest(sample),
            "byte_size": sample.stat().st_size,
        }

    (out / "showcase-provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("Generated 7 full document pages, 2 cropped excerpts, hero and social preview")
    print("Verified 3 real example documents and Git fixture", tree[:12])


if __name__ == "__main__":
    main()
