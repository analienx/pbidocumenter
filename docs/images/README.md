# Visual evidence, not mockups

[← Example gallery](../EXAMPLES.md) · [← Repository](../../README.md)

Everything here is traceable to actual generated Contoso Retail documentation. **The JPEG/PNG files are only GitHub preview assets: the Word generator builds native editable DrawingML diagrams rather than inserting these images into the DOCX.**

| Asset | What you're viewing |
| :-- | :-- |
| [`hero-product.png`](hero-product.png) | Editorial banner composed from **actual** Word model-lineage and PBIR-wireframe excerpts |
| [`social-preview.png`](social-preview.png) | 1280×640 social banner using the same source screenshots |
| [`showcase/detail-*.jpg`](showcase/) | **Cropped excerpts** of two rendered full document pages, for legibility in GitHub |
| [`showcase/*.jpg`](showcase/) | Seven **full, unmodified PDF-page renders** plus the two excerpts |
| [`showcase-provenance.json`](showcase-provenance.json) | Git tree, CI run, rendered PDF source pages, SHA-256 hashes and permanent sample checksums |

**Source:** fictional public [Contoso Retail PBIP](../../examples/contoso-retail/). **Capture:** installed-package CI run [40870433647](https://github.com/analienx/pbidocumenter/actions/runs/40870433647), LibreOffice PDF conversion and PyMuPDF page extraction. The source diagrams were not recreated or retouched.

The hero adds **presentation only**: typography, framing, background and image crops. It is not an application screenshot. The wireframe is a source-derived PBIR layout diagram, **not** a screenshot of a live Power BI dashboard.

## Reproduce and verify

```bash
gh run download 40870433647 -R analienx/pbidocumenter \
  --name contoso-rendered-word-review-evidence \
  --dir /path/to/evidence

python -m pip install Pillow pymupdf
python scripts/build_readme_showcase.py --evidence-dir /path/to/evidence
python scripts/ci_readme_showcase.py
```

The regeneration script produces all nine page screenshots/crops and both banners. The verification script checks image hashes, fixture provenance, Markdown image links and the real [sample Word/PDF files](../samples/README.md). Artifacts eventually expire, but the committed images and examples remain available.

Never replace evidence images with synthetic documents while presenting them as generated output.
