# Desktop Bridge: API-first capture and PBIR-grounded review

The Desktop Bridge preview is a **capture/reload/state** interface, not a
per-visual formatting or semantic-model API. Discover the methods advertised by
`powerbi-desktop manifest --pid <PID>`; do not assume undocumented operations.
The report's source facts come from PBIR and its companion semantic model.
Desktop pixels remain necessary to judge readability, overflow and composition.

## Acquire a Windows-native capture

Install the official CLI in a user-selected tools directory, or use an existing
installation. This project does not install a global binary or start Desktop:

```powershell
npm install --prefix <tools-dir> @microsoft/powerbi-desktop-bridge-cli
<tools-dir>/node_modules/.bin/powerbi-desktop status
<tools-dir>/node_modules/.bin/powerbi-desktop manifest --pid <PID>
```

Choose the PID whose `currentFilePath` is your exact disposable `.pbip`; do not
pick the first Desktop window. Source must be saved, with no unsaved Desktop
changes. Refresh and model-query correctness remain separate acceptance gates.

Bridge screenshots can include a filter pane and blank Desktop workspace, even
when the capture call succeeds. Never send those raw images to the VQS reviewer
or assign them the PBIR canvas's coordinates. Inspect one native page image and
calibrate the **canvas** pixel rectangle at the intended Desktop viewport.

For example, create a local calibration JSON for **your** exact screenshot:

```json
{"native_pixels": [3915, 2394], "rect": [0, 330, 3074, 1730], "scale_one_canvas_pixels": [1537, 865]}
```

These are measured example coordinates, NOT portable defaults. `rect` is
`[left, top, width, height]` in the native Bridge PNG. Recalibrate after a
resolution, window, zoom, filter-pane or Desktop layout change. The adapter
requires an independently measured full-canvas size at scale 1; the crop at scale N must match N times those dimensions to within 2 pixels. A proportional partial crop can still have the correct 16:9 aspect ratio, so aspect ratio alone is insufficient. The adapter also requires the crop's aspect ratio to match the PBIR page to within 1% and the
full native PNG to match the calibrated size on **every** captured page.

```powershell
python -m pbip_documenter.visual_quality.desktop_bridge `
  --source "<project>/Report.Report" --pbip "<project>/Report.pbip" `
  --renders "<run>/canvases" --pid <PID> `
  --cli "<tools-dir>/node_modules/.bin/powerbi-desktop.cmd" `
  --calibration "<run>/canvas-calibration.json" --scale 2
```

The adapter checks source digest before/after, explicit Desktop file and PID,
unsaved state before/after, exact page inventory, PNG integrity and crop size.
Only after all pages pass does it write the usual VQS `capture-manifest.json`.
The report and its semantic model must live next to the passed `.pbip` file.

## Ground the reviewer in source facts

`pbip_documenter.visual_quality.structured_evidence` extracts exact PBIR
visual IDs, types, positions, bindings, sort definitions and explicitly
configured formatting literals. The visual-crop manifest embeds this source
context; both the Pi and OpenAI-compatible reviewers receive it alongside the
real page image and focused crop. An **absent** formatting property may come
from the theme or a Power BI default; absence is not evidence of its value.

Semantic correctness and precise data distribution require live SemanticOps
queries, not claims guessed from the image or from DAX measure names. A source
finding identifies an intended property; only a fresh rendered image verifies
that the corresponding visual is readable on screen.

## Verified limitations

A fresh, source-identical disposable PBIP with the synthetic import cache was
opened without manual refresh. The Desktop Bridge captured **all five populated
Contoso pages** at scale 2. Its raw output includes Desktop chrome: an early
partial-width crop falsely made the rightmost slicer and KPI look clipped. The
corrected 3074-by-1730 canvas was visually inspected and bound to the exact
report/model source digest; the capture adapter now requires an independently
measured scale-one canvas width and height as well as a valid aspect ratio.
This catches that observed undersized-crop regression but cannot replace checking
the calibration visually after viewport changes. The existing per-page visual
review is intentionally stale and blocks release; Desktop bulk refresh remains
unresolved even though the bundled synthetic cache restores first-open data.

Power BI Desktop Bridge is a preview and may change its method manifest or
capture behavior. Inspect the actual build rather than relying on package or
Desktop version numbers alone.

When using the standalone `visual_quality iterate` runner, set
`"crop_visuals": true` in the report workflow. After **every** renderer round,
the runner regenerates the derived, hash-bound visual crops and PBIR context
before it requests an independent review. It never reuses old crop coordinates
or a previous round's images after a PBIR edit.

The Windows Bridge renderer must be configured explicitly in the workflow's
`renderer.argv` with the verified `--pbip`, `--pid`, `--cli` and
`--calibration` arguments. The reviewer and repair executor remain separate
configured adapters; the presence of this capture module does not silently
provision a cloud reviewer or authorize model/source edits.
