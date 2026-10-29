# Screenshot provenance

[← Output gallery](../EXAMPLES.md) · [← Repository](../../README.md)

This directory contains **real, checked-in visual evidence from PBIP Documenter**, not AI-generated document mockups.

| Asset | Meaning |
| :--- | :--- |
| [`social-preview.png`](social-preview.png) | Designed repository banner combining **two actual document page renders** (relationship diagram and report wireframe) with decorative typography |
| [`showcase/*.jpg`](showcase/) | Complete source-derived document page screenshots |
| [`showcase-provenance.json`](showcase-provenance.json) | Precise CI run, source commit, PDF SHA-256, screenshot page references and image SHA-256 |

## Verification boundary

- Inputs: fictional public [Contoso Retail PBIP project](../../examples/contoso-retail/).
- Producer: installed-package CI in [`main` run 40870433647](https://github.com/analienx/pbidocumenter/actions/runs/40870433647).
- Renderer: headless **LibreOffice → PDF**, then PyMuPDF → JPEG. These are **Word-document renders**, **not** screenshots of the live Power BI report.
- Pages are reproduced without synthesizing report content. The banner is a composition of real rendered pages; its surrounding background and text are graphic design, not an assertion about a specific application UI.
- Screenshot images are committed because temporary GitHub Actions artifacts expire.

## Regeneration

```bash
gh run download 40870433647 -R analienx/pbidocumenter \
  --name contoso-rendered-word-review-evidence \
  --dir /path/to/evidence

python -m pip install pillow pymupdf
python scripts/build_readme_showcase.py --evidence-dir /path/to/evidence
python scripts/ci_readme_showcase.py
```

The screenshot builder checks that the referenced artifact has the expected 12 tables, 55 measures, 19 relationships, 5 pages and 54 visuals. If the fixture changes, regenerate the proof images from the **new matching run** and update the verified inventory rather than reusing a misleading old screenshot.

**Do not replace these images with concept art** without explicitly relabeling them as illustrations.
