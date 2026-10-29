"""Build authentic repository showcase images from CI-rendered Contoso Word PDFs.

Screenshots are rendered directly from generated documentation; no chart,
report, value or document text is synthesized. Requires Pillow and PyMuPDF:
    python -m pip install Pillow pymupdf
    python scripts/build_readme_showcase.py --evidence-dir <CI artifact directory>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "tables_verified": 12,
    "measures_verified": 55,
    "relationships_verified": 19,
    "pages_verified": 5,
    "visuals_verified": 54,
}
CAPTURES = {
    "contents.jpg": ("full", 1),
    "semantic-model.jpg": ("full", 4),
    "model-lineage.jpg": ("full", 5),
    "power-query.jpg": ("full", 14),
    "dax-measures.jpg": ("full", 18),
    "report-wireframe.jpg": ("full", 21),
    "technical-observations.jpg": ("full", 26),
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = (
        (r"C:\Windows\Fonts\seguisb.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
         else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def pdf_page(pdf: Path, page_1based: int, scale: float = 2.15) -> Image.Image:
    with pymupdf.open(str(pdf)) as document:
        page = document[page_1based - 1]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def cover_background(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height))
    data = image.load()
    for y in range(height):
        for x in range(width):
            t = min(1.0, 0.65 * (x / width) + 0.35 * (y / height))
            data[x, y] = (
                int(9 + 10 * t),
                int(16 + 20 * t),
                int(35 + 33 * t),
            )
    return image


def paper_card(base: Image.Image, screenshot: Image.Image, box: tuple[int, int, int, int]) -> None:
    x, y, width, height = box
    margin = 11
    screenshot = screenshot.copy()
    screenshot.thumbnail((width - margin * 2, height - margin * 2))
    w, h = screenshot.size
    paste_x = x + (width - w) // 2
    paste_y = y + (height - h) // 2

    shadow = Image.new("RGBA", base.size)
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x + 13, y + 16, x + width + 11, y + height + 18), 15, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    base.paste(shadow, mask=shadow.getchannel("A"))

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((x, y, x + width, y + height), 13, fill=(249, 251, 255))
    base.paste(screenshot, (paste_x, paste_y))


def make_cover(artifacts: Path, dest: Path) -> None:
    width, height = 1280, 640
    image = cover_background(width, height)
    draw = ImageDraw.Draw(image)
    for n in range(6):
        x = 760 + n * 105
        draw.line((x, 0, x - 230, height), fill=(25, 50, 80), width=1)

    draw.rounded_rectangle((58, 60, 327, 99), 16, fill=(32, 58, 92))
    draw.text((77, 69), "POWER BI  /  PBIP + PBIR", font=font(19, True), fill=(119, 217, 244))

    draw.text((57, 151), "PBIP", font=font(97, True), fill=(255, 255, 255))
    draw.text((57, 257), "Documenter", font=font(83, True), fill=(255, 255, 255))
    draw.line((59, 382, 651, 382), fill=(58, 219, 194), width=5)
    draw.line((418, 382, 651, 382), fill=(227, 57, 153), width=5)

    draw.text((60, 413), "Your Power BI source, distilled into", font=font(27), fill=(226, 235, 247))
    draw.text((60, 451), "review-ready Word specifications.", font=font(27), fill=(226, 235, 247))
    draw.text((61, 558), "ACTUAL CONTOSO RETAIL OUTPUT  |  CI-RENDERED", font=font(16, True), fill=(141, 177, 208))

    lineage = pdf_page(artifacts / "contoso-full.pdf", 5, scale=1.35)
    wireframe = pdf_page(artifacts / "contoso-full.pdf", 21, scale=1.35)
    paper_card(image, lineage, (790, 70, 310, 462))
    paper_card(image, wireframe, (1030, 153, 236, 390))
    draw.rounded_rectangle((796, 558, 1241, 592), 9, fill=(18, 35, 62))
    draw.text((813, 567), "Real document pages. No mockups.", font=font(17, True), fill=(211, 234, 247))

    # GitHub supports <1 MB social preview PNG; use an optimized palette.
    image.quantize(colors=192).save(dest, format="PNG", optimize=True)
    assert dest.stat().st_size < 1_000_000, f"GitHub social preview must be <1MB: {dest}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence-dir", type=Path, required=True)
    p.add_argument("--run-id", default="40870433647")
    p.add_argument("--source-commit", default="ac6700c5d2c6adafcb784b2db4416c4d9fe99c9a")
    p.add_argument("--out-dir", type=Path, default=ROOT / "docs" / "images")
    args = p.parse_args()
    artifacts = args.evidence_dir.resolve()
    output = args.out_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shots = output / "showcase"
    shots.mkdir(exist_ok=True)

    report = json.loads((artifacts / "word-render-acceptance.json").read_text(encoding="utf-8"))
    assert report["source_project"] == "examples/contoso-retail"
    for mode in ("default", "full"):
        for key, value in EXPECTED.items():
            assert report["documents"][mode]["inventory"][key] == value, f"{mode}: wrong {key}"
        assert report["documents"][mode]["render"]["outside_page_blocks"] == 0

    fixture_tree = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD:examples/contoso-retail"],
        text=True,
    ).strip()
    provenance = {
        "fixture": report["source_project"],
        "fixture_git_tree": fixture_tree,
        "github_workflow_run": args.run_id,
        "source_commit": args.source_commit,
        "render_engine": "LibreOffice headless PDF generated by installed-wheel acceptance CI",
        "screenshot_truth": "Unmodified page images rendered from the generated document PDF; not Power BI Desktop screenshots.",
        "inventory": EXPECTED,
        "pdf_sha256": {},
        "images": {},
    }
    for mode in ("default", "full"):
        pdf = artifacts / f"contoso-{mode}.pdf"
        provenance["pdf_sha256"][pdf.name] = hashlib.sha256(pdf.read_bytes()).hexdigest()

    for name, (mode, page) in CAPTURES.items():
        screenshot = pdf_page(artifacts / f"contoso-{mode}.pdf", page)
        path = shots / name
        screenshot.save(path, format="JPEG", quality=84, optimize=True, progressive=True, subsampling=0)
        provenance["images"][f"showcase/{name}"] = {
            "generated_document": f"contoso-{mode}.docx",
            "render_pdf": f"contoso-{mode}.pdf",
            "pdf_page_1based": page,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    cover = output / "social-preview.png"
    make_cover(artifacts, cover)
    provenance["images"]["social-preview.png"] = {
        "note": "Composed banner using actual document PDF page 5 and page 21; typography/background are decorative.",
        "source_pages": [5, 21],
        "sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
    }
    (output / "showcase-provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("GENERATED", len(CAPTURES) + 1, "images")
    for file in [cover, *sorted(shots.iterdir())]:
        print(file.relative_to(ROOT), file.stat().st_size)


if __name__ == "__main__":
    main()
