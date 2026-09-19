# Contoso Retail Power BI sample

A self-contained PBIP sample with an import-mode star schema, synthetic Contoso-style retail data for 2023–2025, reusable DAX measures, and **five** PBIR report pages.

## Run it

Open `Contoso Retail.pbip` in Power BI Desktop using **File → Open**. The project has no external data-source dependency or sign-in requirement. If Desktop reports incomplete tables after opening, verify the actual partition states and refresh results before judging the report from blank visuals.

## Report quality evidence

From the repository root:

```powershell
python -m pbip_documenter.quality_gate "examples/contoso-retail/Contoso Retail.Report" --screenshots "examples/contoso-retail/screenshots"
```

The checker verifies canvas bounds, a minimum 24-pixel bottom margin, overlap, KPI-row alignment, and one PNG per page. `screenshots/capture-manifest.json` binds the five captured **report canvases** to exact SHA-256 digests of the screenshots and the report plus semantic-model source files. Re-render and regenerate the manifest after **any** PBIR or model edit; old captures fail the provenance gate.

The CLI also requires a SHA-256-bound per-page `screenshots/visual-review.json` with **approved** status and no outstanding issues. The current report records open readability and visual-semantic defects, so the CLI deliberately exits nonzero despite geometry and render-provenance passes. After addressing them, re-render, review each page, and update the evidence. Data freshness, DAX behavior, mobile behavior and the generated Word document still need separate acceptance; `release_ready` remains false until those gates are implemented and verified.

For the independent, reusable **report + Word visual-quality loop** (including
strict per-page image observations and automatic repair adapters), see
[Visual Quality System](../../docs/VISUAL_QUALITY_SYSTEM.md). This new gate
does not convert the sample's outstanding visual-review findings into approval.
For the complete run and repository guide, see the [root README](../../README.md).

## Included synthetic data snapshot

The sample includes `Contoso Retail.SemanticModel/.pbi/cache.abf` (about 201 KB), a
Power BI Desktop import snapshot containing **only this sample's synthetic data**.
It was independently checked by opening the original PBIR/TMDL with **only this
cache added**: all five report pages became populated immediately. Removing
only the cache reproduces Desktop's empty-first-open state on the tested build.
`sample-model-cache-manifest.json` binds the snapshot to its semantic definition;
the fixture test fails if the model source changes without regenerating it.
This binary is a sample bootstrap, **not a portable substitute for refresh**:
Power BI versions can invalidate caches, and Desktop bulk refresh still reports
cyclic-reference errors on this test setup. Individual partition refresh via
SemanticOps has loaded all 12 tables successfully. Do not use this synthetic
cache or any cached business data as a general-purpose report distribution
strategy; verify source connectivity, freshness and repeatable refresh separately.
