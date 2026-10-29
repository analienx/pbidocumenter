# Optional report-quality checks

**PBIPDocumenter generates Word specifications; [Visual Quality System](https://github.com/analienx/visual-quality-system) checks and repairs Power BI reports.** You can use both without merging their parsers or making Word mandatory for Power BI quality.

Install VQS **into the same Python environment** as PBIPDocumenter. VQS requires **Python 3.11 or newer** (PBIPDocumenter alone supports Python 3.10). If your existing `pipx` installation uses Python 3.10, first reinstall PBIPDocumenter with a newer interpreter (for example, `pipx install --python python3.12 pbip-documenter`). For the `pipx` installation shown above:

```powershell
pipx inject pbip-documenter "git+https://github.com/analienx/visual-quality-system.git@v0.1.0"
pbip-quality examples/contoso-retail --private-root ./private-vqs-evidence --mode repair
```

`pbip-quality` invokes the existing `vqs run --mode repair` orchestrator, applies **only supported allowlisted edits in an isolated candidate**, checks VQS's sealed event chain using `vqs run-status`, and returns structured JSON with **verdict, candidate, findings summary, source digest and evidence location**. It never promotes or overwrites your original PBIP, never publishes reports, and never treats a blocked native check as success.

For an agent, the recommended instruction is: *“Use `pbip-quality` to fix supported Power BI layout and design defects in a private candidate, verify the evidence, then give me Fixed / Verified / Blocked and the candidate path. Do not modify or publish my original.”*

**Codes:** `0` pass, `1` fail, `2` blocked. Static checks are not visual/interaction release acceptance. For an actual Desktop run, use the **exact PID and explicit local-only permission**:

```powershell
# Store this JSON outside the PBIP project (never commit credentials or data).
# { "schema_version": "vqs.config/1",
#   "data_permissions": { "allow_desktop": true, "allow_cloud": false } }
pbip-quality "C:\\PBIP\\Contoso Retail.pbip" --mode review --scope desktop `
  --pid 12345 --config "C:\\private\\desktop-authorized.json" `
  --private-root "C:\\private\\vqs-evidence"
```

The Desktop consumer enables **local** Modeling readiness, verifies the sealed event chain and native page PNG hashes against the exact report/PID/source, and reports `desktop_capture_verified`, `desktop_modeling_ready`, and `desktop_capture.page_count`. These prove **engineering capture only**, not perceptual acceptance. Without a configured external reviewer provider, visual acceptance correctly returns **BLOCKED** (exit `2`). An independently authorized reviewer can be supplied with `--reviewer package.module:reviewer` using VQS's typed ReviewPort contract; **that provider alone is not G6 or a distinct-human certification**.

[Read the Windows native verification and tested upgrade/rollback matrix](docs/VQS_NATIVE_CONSUMER_ACCEPTANCE_2026-10-28.md), the VQS [agent quickstart](https://github.com/analienx/visual-quality-system/blob/main/docs/AI_AGENT_QUICKSTART.md), and the [component architecture](https://github.com/analienx/visual-quality-system/blob/main/docs/AGENT_AUTOFIX_ARCHITECTURE.md).

Both commands are separate: `pbip-documenter` still generates DOCX **without** installing or invoking VQS, while `pbip-quality` delegates quality decisions to VQS. Keep evidence roots outside your source tree and off public GitHub.
