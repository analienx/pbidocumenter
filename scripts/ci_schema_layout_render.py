"""Render every synthetic and Contoso schema pair on GitHub's LibreOffice runner.

Capture actual output PDF pages as JPGs, create a before/after contact sheet,
and verify no blank pages or out-of-page text blocks. Does not certify
Microsoft Word-exact pagination.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args()
    folder = args.dir.resolve()
    metadata = json.loads((folder / "schema-layout-comparison.json").read_text(encoding="utf-8"))
    renders: dict[str, dict] = {}
    for case in metadata:
        for kind in ("before", "after"):
            name = f"{case}-{kind}"
            document = folder / f"{name}.docx"
            assert document.is_file()
            with tempfile.TemporaryDirectory(prefix="schema-lo-") as profile:
                p = subprocess.run(
                    [
                        "libreoffice",
                        f"-env:UserInstallation={Path(profile).as_uri()}",
                        "--headless",
                        "--convert-to",
                        "pdf:writer_pdf_Export",
                        "--outdir",
                        str(folder),
                        str(document),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
            pdf = folder / f"{name}.pdf"
            assert p.returncode == 0 and pdf.is_file(), (
                f"Failed to render {name}: {p.stdout[-1000:]} {p.stderr[-1000:]}"
            )
            with pymupdf.open(pdf) as doc:
                assert 1 <= len(doc) <= 3, f"Schema diagram unexpectedly spans {len(doc)} pages"
                target = next(
                    (i for i, page in enumerate(doc) if "Schema relationship focus" in page.get_text()),
                    0,
                )
                page = doc[target]
                assert page.get_text().strip(), f"Blank diagram page: {name}"
                escaped = []
                for block in page.get_text("blocks"):
                    x0, y0, x1, y1 = block[:4]
                    if x0 < -3 or y0 < -3 or x1 > page.rect.width + 3 or y1 > page.rect.height + 3:
                        escaped.append([x0, y0, x1, y1])
                assert not escaped, f"Text geometry outside rendered page for {name}: {escaped}"
                pix = page.get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25), alpha=False)
                shot = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                shot.save(folder / f"{name}.jpg", quality=86, optimize=True)
                renders[name] = {
                    "pdf_pages": len(doc),
                    "diagram_page": target + 1,
                    "source": document.name,
                    "preview": f"{name}.jpg",
                    "width": shot.width,
                    "height": shot.height,
                    "escaped_text_blocks": escaped,
                }
                print("RENDERED",name,"PDF pages",len(doc),"diagram at",target+1,flush=True)

    w, h = 670, 525
    sheet = Image.new("RGB", (w*2, len(metadata)*h), (235, 240, 247))
    draw = ImageDraw.Draw(sheet)
    for idx, case in enumerate(metadata):
        for side, kind in enumerate(("before", "after")):
            image = Image.open(folder / f"{case}-{kind}.jpg").convert("RGB")
            image.thumbnail((w-14, h-30), Image.Resampling.LANCZOS)
            x = side*w+(w-image.width)//2
            y = idx*h+26
            sheet.paste(image, (x,y))
            draw.text((side*w+20,idx*h+7), f"{case.upper()}  /  {kind.upper()}", fill=(15, 30, 52))
    sheet.save(folder / "comparison-contact-sheet.jpg", quality=86, optimize=True)
    (folder / "pdf-render-report.json").write_text(json.dumps(renders,indent=2)+"\n",encoding="utf-8")
    print("FINISHED",len(renders),"real PDF renders with image evidence")


if __name__ == "__main__":
    main()
