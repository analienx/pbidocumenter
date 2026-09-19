# Independent Power BI image review with Pi + Cline Pass

This is an **opt-in cloud-image reviewer**, separate from the PBIR repair executor.
No default model, account, OAuth token, or pay-as-you-go API key is shipped.
The model must advertise `image` as an input modality in Pi's live model state;
text-only models fail before any image is sent. Install Pi and its Cline provider
in an authenticated profile separately. Never commit profile files or client PNGs.

## Evidence and operation

The report's full-page PNG and high-resolution visual crops are bound to the
exact PBIR **and** companion semantic-model digest. Crop metadata maps image
regions to stable visual IDs, role bindings and specific `visual.json` paths.
The reviewer sees the whole page plus up to three prioritized crops; the visual
and repair executor never share an agent identity or an editable tool session.
An image diagnosis describes **visible symptoms**, not a proven DAX/M root cause.

From the repository root, using a synthetic or explicitly approved report:

```powershell
$sample = 'examples/contoso-retail'
$report = "$sample/Contoso Retail.Report"
$renders = "$sample/screenshots"
python -m pbip_documenter.visual_quality.visual_evidence --source $report --renders $renders
python -m pbip_documenter.visual_quality request-review report $report --renders $renders --fixer-id pbir-repair-executor --output .visual-quality/request.json
```

The images must already have been freshly rendered by Power BI Desktop, and
`capture-manifest.json` must agree with the current report/model source digest.
A report modified after capture must be rendered again before review.
A focused diagnostic reviews one page and chart and **cannot approve the whole
report**. Replace the profile and model with an authorized image-capable Cline
Pass subscription route (for example `cline-pass/qwen3.7-plus`):

```powershell
python -m pbip_documenter.visual_quality.pi_reviewer --source $report --renders $renders --request .visual-quality/request.json --review .visual-quality/products-diagnostic.json --profile "$HOME/.pi/supervisor-accounts/account-1/agent" --model cline-pass/qwen3.7-plus --reviewer-id independent-image-qa --page-id Products_brands --visual-id product-quality-growth --allow-cloud-images
python -m pbip_documenter.visual_quality.handoff --source $report --renders $renders --diagnostic .visual-quality/products-diagnostic.json --output .visual-quality/repair-findings.json
```

`--allow-cloud-images` explicitly authorizes transmitting the selected PNGs
to the configured subscription provider. The transport starts a temporary Pi
RPC session with **all editing/tools disabled**. Credentials remain inside the
existing Pi profile and are never written into output files. The returned
review must address every versioned criterion with image-grounded reasons;
invalid, incomplete or stale results fail closed.

For a full report review, omit `--page-id` and `--visual-id` and use a separate
output filename. The resulting full review may be supplied to the independent
`visual_quality verify` gate. The focused diagnostic is schema 2 and can never
pass that gate, even if all its individual checks say `pass`.

## Repair handoff and acceptance

The handoff binds each failure to the page PNG, crop, PBIR file and field roles.
It labels candidate remedies but **does not trust an image model's speculation
about why DAX or a relationship is wrong**. A specialist must inspect the model
before selecting a measure or changing chart semantics. The built-in constrained
scatter-to-ranked-bar and layout-fit recipes require a source-bound defect and
support dry-run; all changes require a fresh populated Desktop render.

A full loop needs a Windows Desktop renderer and a policy-controlled PBIR repair
executor configured separately. This Pi adapter supplies the independent image
analysis stage, not an unrestricted self-approving agent. An unchanged source,
new regression, unavailable model or exhausted iteration budget remains blocked.

## Text-only source repair planning (GLM / DeepSeek)

Pi's currently configured `cline/z-ai/glm-5.3-flash` and
`cline-pass/deepseek-v4.1-flash` routes advertise **text input only**. Both
failed the image-review capability gate before pixel upload in the live test.
They can instead receive the verified *textual* visual diagnosis and PBIR role
bindings to propose a reversible edit, without receiving any PNGs or being able
to mark the image visually approved. Select the installed/authenticated model
explicitly; **no fallback between subscriptions or accounts occurs here**.

```powershell
python -m pbip_documenter.visual_quality.pi_repair_planner --source $report --renders $renders --diagnostic .visual-quality/products-diagnostic.json --output .visual-quality/repair-plan.json --profile "$HOME/.pi/supervisor-accounts/account-1/agent" --model cline/z-ai/glm-5.3-flash --allow-cloud-context
# Or choose cline-pass/deepseek-v4.1-flash with an authorized subscription profile.
```

`--allow-cloud-context` separately authorizes transmitting the report's
field names, visual issue descriptions and PBIR paths. This stage sends **zero
images** and marks its proposals `auto_apply=false` and `visual_approval=false`.
Any DAX/metric-choice recommendation is provisional until validated against
the actual model. The independent rendered-image reviewer must still confirm
that no defects remain after a repair.

A second vision-capable reviewer can be invoked on the same screenshot to
investigate disagreement; compare source-bound diagnostic files with
`python -m pbip_documenter.visual_quality.consensus`. Agreement is not semantic
proof, and contradictory findings trigger adjudication rather than silently
approving the page or averaging model opinions.

For API-first source context and native Power BI Desktop capture, see
[Desktop Bridge integration](VQS_DESKTOP_BRIDGE.md). A Desktop Bridge raw PNG
may contain editing chrome; its calibrated canvas-only image is the review input.
