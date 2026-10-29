"""Editorial repository hero composed only from authentic generated Word screenshots.

Requires Pillow. The screenshot cards use cropped parts of real pages from
docs/images/showcase; all non-document elements are decorative presentation.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parents[1] / "docs" / "images"
NAVY = (10, 19, 37)
TEXT = (244, 248, 253)
MUTED = (180, 204, 222)
MINT = (64, 218, 198)
BLUE = (70, 139, 229)
PINK = (235, 69, 165)


def typography(size: int, bold: bool = False) -> ImageFont.ImageFont:
    paths = (
        [r"C:\Windows\Fonts\seguisb.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold else
        [r"C:\Windows\Fonts\segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for candidate in paths:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def detail_images(root: Path = BASE) -> dict[str, Path]:
    shots = root / "showcase"
    inputs = {
        "detail-lineage.jpg": ("model-lineage.jpg", (0.045, 0.113, 0.963, 0.733)),
        "detail-wireframe.jpg": ("report-wireframe.jpg", (0.069, 0.077, 0.934, 0.475)),
    }
    result = {}
    for target, (source, fractions) in inputs.items():
        im = Image.open(shots / source).convert("RGB")
        w, h = im.size
        bounds = (
            round(w * fractions[0]), round(h * fractions[1]),
            round(w * fractions[2]), round(h * fractions[3]),
        )
        out = shots / target
        im.crop(bounds).save(out, "JPEG", quality=87, subsampling=0, optimize=True)
        result[target] = out
    return result


def gradient(w: int, h: int) -> Image.Image:
    base = Image.new("RGB", (w, h))
    pixels = base.load()
    for y in range(h):
        fy = y / h
        for x in range(w):
            fx = x / w
            glow = max(0, 1.0 - ((fx - 0.88) ** 2 + (fy - 0.25) ** 2) * 1.8)
            pixels[x, y] = (
                int(8 + 9 * fx + 6 * glow),
                int(18 + 12 * fx + 12 * glow),
                int(37 + 27 * fx + 27 * glow),
            )
    return base


def card(base: Image.Image, source: Path, rect: tuple[int, int, int, int],
         title: str) -> None:
    x, y, w, h = rect
    layer = Image.new("RGBA", base.size)
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((x + 6, y + 12, x + w + 9, y + h + 13),
                         radius=20, fill=(0, 0, 0, 115))
    layer = layer.filter(ImageFilter.GaussianBlur(18))
    base.paste(layer, mask=layer.getchannel("A"))

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=(249, 251, 254))
    header = 45
    draw.rounded_rectangle((x, y, x + w, y + header),
                           radius=14, fill=(231, 237, 246))
    draw.rectangle((x, y + 24, x + w, y + header), fill=(231, 237, 246))
    draw.ellipse((x + 21, y + 17, x + 32, y + 28), fill=MINT)
    draw.text((x + 46, y + 10), title, font=typography(17, True), fill=(25, 47, 78))
    shot = Image.open(source).convert("RGB")
    inner = (w - 24, h - header - 19)
    shot.thumbnail(inner, Image.Resampling.LANCZOS)
    xo = x + (w - shot.width) // 2
    yo = y + header + (h - header - shot.height) // 2
    base.paste(shot, (xo, yo))


def create(root: Path = BASE) -> dict[str, Path]:
    details = detail_images(root)
    width, height = (1440, 720)
    canvas = gradient(width, height)
    draw = ImageDraw.Draw(canvas)

    # Subtle grid on the graphic side; do not imply a fabricated software UI.
    for x in range(675, 1450, 105):
        draw.line((x, 0, x - 190, 720), fill=(28, 50, 79), width=1)
    draw.rounded_rectangle((77, 75, 338, 115), radius=11, fill=(29, 56, 79))
    draw.text((97, 85), "POWER BI  /  PBIP + PBIR", font=typography(17, True), fill=(144, 231, 222))
    draw.text((74, 176), "PBIP", font=typography(91, True), fill=TEXT)
    draw.text((74, 287), "Documenter", font=typography(76, True), fill=TEXT)
    draw.rectangle((78, 395, 470, 401), fill=MINT)
    draw.rectangle((470, 395, 592, 401), fill=PINK)
    draw.text((77, 431), "Source-generated diagrams.", font=typography(28), fill=(229, 239, 250))
    draw.text((77, 472), "Native, editable Word shapes.", font=typography(28), fill=(229, 239, 250))
    draw.text((77, 568), "MODEL   /   DAX   /   LINEAGE   /   PBIR WIREFRAMES",
              font=typography(15, True), fill=MUTED)
    draw.text((77, 624), "REAL GENERATED CONTOSO RETAIL OUTPUT", font=typography(15, True), fill=MINT)

    card(canvas, details["detail-lineage.jpg"], (670, 84, 708, 393), "01  /  SEMANTIC MODEL RELATIONSHIPS")
    card(canvas, details["detail-wireframe.jpg"], (869, 403, 500, 258), "02  /  REPORT-PAGE WIREFRAME")

    hero = root / "hero-product.png"
    # Use indexed PNG: sharp UI typography, small repo download, no external assets.
    canvas.quantize(colors=255, method=Image.Quantize.MEDIANCUT).save(
        hero, optimize=True,
    )
    social = root / "social-preview.png"
    canvas.resize((1280, 640), Image.Resampling.LANCZOS).quantize(
        colors=224, method=Image.Quantize.MEDIANCUT
    ).save(social, optimize=True)
    return {"hero-product.png": hero, "social-preview.png": social,
            **{f"showcase/{name}": path for name, path in details.items()}}


if __name__ == "__main__":
    for name, path in create().items():
        print(name, path.stat().st_size)
