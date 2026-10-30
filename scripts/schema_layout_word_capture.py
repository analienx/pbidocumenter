"""Render synthetic before/after DOCX figures using actual Microsoft Word.

Windows-only diagnostic script. Runs Word in a separate invisible COM instance,
opens read-only documents, and never modifies user documents. Produces PDFs,
PNGs, and a visual contact sheet for human review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

try:
    import pymupdf
except ImportError:
    vendor = Path(r"C:\Workspace\scratch\pbipdoc-premium-render-vendor")
    sys.path.insert(0, str(vendor))
    import pymupdf

import win32com.client  # type: ignore[import-not-found]


def word_to_pdf(source: Path, dest: Path) -> None:
    app = win32com.client.DispatchEx("Word.Application")
    app.Visible = False
    app.DisplayAlerts = 0
    try:
        app.AutomationSecurity = 3
        doc = app.Documents.Open(
            FileName=str(source.resolve()),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
        )
        try:
            doc.ExportAsFixedFormat(OutputFileName=str(dest.resolve()), ExportFormat=17)
        finally:
            doc.Close(SaveChanges=0)
    finally:
        app.Quit(SaveChanges=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    a = parser.parse_args()
    directory = a.dir.resolve()
    metadata = json.loads((directory / "schema-layout-comparison.json").read_text(encoding="utf-8"))
    results = {}
    for case in metadata:
        for suffix in ("before", "after"):
            source = directory / f"{case}-{suffix}.docx"
            pdf = directory / f"{case}-{suffix}.pdf"
            word_to_pdf(source, pdf)
            with pymupdf.open(pdf) as document:
                pages = len(document)
                target = 0
                # Find the page that actually contains the schema diagram.
                for i, page in enumerate(document):
                    if "Schema relationship focus" in page.get_text():
                        target = i
                        break
                page = document[target]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(1.15, 1.15), alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                screenshot = directory / f"{case}-{suffix}.png"
                img.save(screenshot, optimize=True)
                results[f"{case}-{suffix}"] = {
                    "pdf": str(pdf),
                    "png": str(screenshot),
                    "pdf_pages": pages,
                    "diagram_page": target + 1,
                    "width": img.width,
                    "height": img.height,
                    "text_chars": len(page.get_text()),
                }
                print("RENDERED",case,suffix,pages,"pages","diagram page",target+1,flush=True)
    # Two columns before/after; each row a model size.
    width, cell_height = 1050, 800
    mosaic = Image.new("RGB", (2 * width, len(metadata) * cell_height), (224, 231, 240))
    draw = ImageDraw.Draw(mosaic)
    for row, case in enumerate(metadata):
        for col, suffix in enumerate(("before", "after")):
            shot = Image.open(directory / f"{case}-{suffix}.png").convert("RGB")
            shot.thumbnail((width - 20, cell_height - 48), Image.Resampling.LANCZOS)
            x, y = col * width + (width - shot.width) // 2, row * cell_height + 42
            mosaic.paste(shot, (x, y))
            draw.text((col*width+22, row*cell_height+12),f"{case.upper()} — {suffix.upper()}",fill=(16, 32, 55))
    mosaic.save(directory / "before-after-word-contact-sheet.jpg",quality=85,optimize=True)
    (directory / "word-render-results.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf-8")
    print("WORD RENDER COMPLETED",len(results),"documents",flush=True)


if __name__ == "__main__":
    main()
