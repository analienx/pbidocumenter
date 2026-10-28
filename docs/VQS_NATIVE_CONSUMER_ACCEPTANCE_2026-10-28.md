# Power BI native consumer acceptance
*Engineering verification · 28 October 2026 · NOT a production release certificate*

## At a glance

The installed `pbip-quality` consumer now supports **both** source-only static repair and a fully bounded **Windows Desktop capture** through VQS. It does not replace the Word documenter, publish PBIPs or self-approve a quality release. Every run is isolated and reports **Fixed / Verified / Failed / Blocked** truthfully.

| Control | Verified result | What it does **not** certify |
|---|---|---|
| Static original-safe auto-fix | A separate full fictional Contoso PBIP with an intentionally introduced 6px chart overlap received one bounded `spacing.adjust` and a remeasured candidate; original unchanged, Microsoft authoring 0/0 | Full quality acceptance; two unrelated design observations remain |
| Native installed capture | Windows installed CLI, exact saved PID/path, 5/5 real native Contoso pages, independent SHA-256 for each PNG | That a reviewer actually inspected/approved the pages |
| Local semantic-model readiness | Modeling MCP automatically connected and reported `status=ready` in the native manifest | Source-bound interactive DAX parity by this consumer (separate VQS G4 evidence exists) |
| Reviewer acceptance | **BLOCKED**, no external ReviewPort configured | Formal distinct-human reviewer or owner G6 |
| Rollback | Wheel baseline → upgrade → rollback → re-upgrade, four verified stages | A production PyPI publication or rollback of a G6-approved release |

## Exact installed native invocation

Install **both packages in one Python 3.11+ environment**. Pin the reviewed VQS **commit**, not just the pre-alpha version number:

```powershell
python -m pip install "git+https://github.com/analienx/visual-quality-system.git@4f51f89f255a6a1798c4baaba3d7b916beb74b94"
python -m pip install pbip-documenter
```

Create `C:\private\desktop-authorized.json` **outside** the PBIP and its semantic model:

```json
{
  "schema_version": "vqs.config/1",
  "data_permissions": {
    "allow_desktop": true,
    "allow_cloud": false
  }
}
```

With the **exact** already-open and saved report PID, invoke:

```powershell
pbip-quality "C:\PBIP\Contoso Retail.pbip" `
  --private-root "C:\private\vqs-evidence" `
  --scope desktop --mode review --pid 12345 `
  --config "C:\private\desktop-authorized.json"
```

The PID is illustrative: resolve it from an authorized Desktop session; never use a guessed PID or an arbitrary currently open report. The consumer does **not** open, save, or switch Desktop files behind your back. It enables **local** Modeling MCP only for the explicitly authorized Desktop mode. Missing permissions, wrong source/PID, stale or dirty Desktop, missing Modeling capability, absent PNG, invalid checksum, or unsealed VQS result all block instead of passing.

The installed consumer returns these **distinct** fields:

- `verdict`: overall VQS release-workflow outcome. **Do not** infer G2/G4/G6 from this alone.
- `evidence_verified`: sealed VQS run-status, matching inputs and source hash rechecked after execution.
- `desktop_capture_verified`: independent read-back found a VQS-passed baseline stage with exact PID/PBIP, clean saved state, all pages and SHA-256 checksums. Does **not** mean a visual reviewer passed.
- `desktop_modeling_ready`: native capture's local Modeling evidence explicitly reported `ready`.
- `desktop_capture.page_count`: number of SHA-verified native PNGs.
- `summary.visual_acceptance`: true *review outcome*, still **BLOCKED** without a configured provider.
- `candidate` and `promotion_performed`: only source-safe proposed edits under the private root; this consumer **never promotes**.

An optional, explicitly installed and trusted VQS typed visual ReviewPort can be supplied through `--reviewer module:object`. The consumer never generates fictional review observations. A local reviewer is still **not** a human distinct from the implementation team nor owner/publisher G6 authorization.

## Actual Windows G2 native integration run

**One** fictional, previously validated Saffron & Spruce Dark Contoso candidate was copied into disposable scratch and opened once. The Microsoft authoring validator returned **0 errors / 0 warnings**. A real UIA Save witnessed exact Windows Desktop PID and same PBIP path; native Save left the Desktop Bridge `hasUnsavedChanges=false`.

Evidence sequence, all with the **same opened PID**:

1. Initial installed consumer captured after Desktop became dirty during startup and correctly blocked the saved-source capture. No flag bypass.
2. A single genuine native `Save.InvokePattern` returned strict source/model agreement and clean Bridge state.
3. Subsequent installed consumer captured **all five** real pages; a missing local Modeling opt-in prevented data-readiness review and remained BLOCKED, not upgraded to success.
4. With the local Modeling port explicitly enabled, captured **5/5** source-bound real pages with model readiness `ready`; the review handoff correctly **blocked because no independent reviewer provider was supplied**.
5. The final updated installed consumer automatically enabled local Modeling only for opted-in Desktop mode, independently verified **all five native image hashes, the exact source hash, PID, current PBIP and clean saved state**, and returned `desktop_capture_verified=true`, `desktop_modeling_ready=true`, `page_count=5`, `evidence_verified=true`, **`verdict=blocked`**, and `promotion_performed=false`.

Real image files, semantic cache, screenshots, source paths, runtime DAX receipts, and project-specific hashes are **private local evidence** and were never added to GitHub or public CI artifacts. The installed CLI native outcome is more powerful than static tests, but the reviewer gate is intentionally not fabricated.

## Reproducible wheel upgrade and rollback

From two **separate exact Git trees**, two same-version (`5.13.0`) wheels were built. This matters: version strings **do not identify the code change**, so both the wheels' SHA-256 and installed `quality.quality` feature signature were checked at each step.

| Stage | Installed code | Explicit Desktop config support | Static installed-CLI parity |
|---|---|---|---|
| Baseline | PBIPDocumenter `c01afe8` | No | PASS |
| Upgrade | Consumer P1 candidate | Yes | PASS |
| Rollback | Exact baseline wheel | No | PASS |
| Re-upgrade | Exact candidate wheel | Yes | PASS |

For all four cases the fictional Contoso **source/model digest matched**, the sealed VQS manifest and event-chain verification succeeded, the original PBIP was unchanged, and no candidate or promotion was manufactured. The expected source-only verdict was **FAIL** for the existing design observations, with process exit `1`; that is **correct** result propagation, not a test failure.

This is an **isolated package upgrade/rollback test**, not a release deployment or rollback of production reports. Packaging is held at `powerbi-core` engineering preview until its accepted VQS SHA and the separately approved product release have been signed.

## Remaining independent acceptance decisions

The existing VQS G2/G4 engineering packets provide a separate real Contoso Year/Region and independent Corporate Spend Sales Region/DAX evidence. These were **not re-run** merely to establish consumer packaging. The supported feature matrix must explicitly distinguish:

- **Supported in current engineering scope:** PBIR static review, safe bounded candidate repair, native page capture with local data readiness, classic slicer state and DAX parity where independently measured.
- **Still unproven:** generalized Shape Map country-specific clicks, real hover-context on a hidden Tooltip page, any untested Microsoft visual interaction, and the final distinct-human visual reviewer and separate G6 owner/publisher decision.
- **Remaining Contoso observations:** Overview-versus-Deep-dive Region-grain reuse and inherited/explicit typography; the repair engine must not guess a semantic deletion or a font default.

See [VQS release gate #16](https://github.com/analienx/visual-quality-system/issues/16) and [consumer integration #17](https://github.com/analienx/visual-quality-system/issues/17). A protected CI pass or agent self-review is **not** G6 authorization.
