# Visual Quality System (VQS) — report + Word document

VQS is an **independent, opt-in release gate**, not a claim that PBIR JSON validity
or a PNG hash proves visual quality. It works on any `*.Report` project and any
`.docx` produced by PBIPDocumenter (or another Word generator).

## What is assessed

| Evidence plane | Report | Word specification |
|---|---|---|
| Structure | PBIR canvas, bounds, collisions, KPI grid | OOXML section margins, text size, table and figure width |
| Render | All report page canvases in PNG | Every paginated Word page in PNG |
| Independent visual review | 25 mandatory/conditionally applicable observations per page | 23 observations per page |
| Corrective action | PBIR/model/code changes in isolated worktree | Generator/template/code changes and regenerated DOCX |

The [versioned rubric](../pbip_documenter/visual_quality/policy.py) requires
specific judgments about legibility, axis density and precision, redundant axis
titles, chart selection, color semantics, contrast, theming, card/panel padding,
alignment, whitespace, tables, overflow and storytelling. Word-specific checks
include heading hierarchy, diagrams and screenshots, page breaks, widows/orphans,
figures, captions, pagination and document/report consistency.

The original `pbip_documenter.quality_gate` geometry check remains available.
VQS adds independent image-based review and a separate DOCX surface; neither
alone authorizes a production release or certifies data/model correctness.

## Standalone CLI (no model or external service required for preflight)

```bash
python -m pbip_documenter.visual_quality preflight report "path/to/Example.Report" --renders path/to/report-pngs
python -m pbip_documenter.visual_quality request-review report "path/to/Example.Report" --renders path/to/report-pngs --fixer-id repair-agent --output review-request.json
python -m pbip_documenter.visual_quality verify report "path/to/Example.Report" --renders path/to/report-pngs --review independent-review.json --fixer-id repair-agent --output result.json
```

A missing independent review, missing image, stale source, skipped mandatory
observation or any unresolved visual defect returns exit code **2**. A valid
preflight alone does not approve a report. JSON findings identify the page,
visual/check, severity, normalized image region and requested corrective action.

## Word page rendering

The portable Word adapter requires LibreOffice (`soffice`) and Poppler
(`pdftoppm`) installed and available on PATH. This is **not** a Python/OOXML-only
quality shortcut: it renders the real paginated document to 150-dpi page PNGs.

```bash
python -m pbip_documenter.visual_quality.render_word generated.docx word-renders/
python -m pbip_documenter.visual_quality preflight document generated.docx --renders word-renders/
python -m pbip_documenter.visual_quality request-review document generated.docx --renders word-renders/ --fixer-id document-generator --output word-review-request.json
```

Every render manifest includes the exact DOCX SHA-256, a numbered page inventory,
individual PNG SHA-256 values and the renderer used. A DOCX edit, image edit,
missing page or unrendered output invalidates the evidence. Only source-bound
page images may be reviewed; extracting DOCX text alone never clears this gate.

## Independent image reviewer

A reviewer consumes the review-request JSON **and actual PNGs**, and emits a
separate JSON response. VQS validates every observation ID, rationale, source
and image digest, and distinct reviewer/executor IDs. A failure must include a
severity, an image-normalized bounding rectangle and an actionable repair.
Passing the metadata contract is not proof that a model really understood an
image: use a trustworthy independent reviewer and retain its evaluation trace.

For users with an explicitly configured, **vision-capable** local model exposing
an OpenAI-compatible chat endpoint, a model-agnostic adapter is supplied:

```bash
python -m pbip_documenter.visual_quality.vision_reviewer --request review-request.json --renders path/to/report-pngs --review independent-review.json --endpoint http://127.0.0.1:11434/v1/chat/completions --model YOUR_VISION_MODEL --reviewer-id independent-visual-qa
```

The endpoint/model are **not** supplied or started by PBIPDocumenter. Remote
image transmission requires HTTPS plus `--allow-remote`; authentication is read
from `--api-key-env ENV_VAR` without logging the key. Do not send proprietary
or personal report screenshots to a remote provider without authorization.
The API adapter fails closed if the model cannot process images, returns invalid
JSON, omits observations or cannot justify its findings. No OCR-derived or
self-generated `approved` flag is accepted in place of a real image review.

## Iteration adapter contract

The orchestrator expects three explicit **argv arrays, not shell strings**:
`renderer` (source → fresh PNGs + capture manifest), `reviewer` (request + PNGs →
independent review JSON), and `fixer` (current findings → source changes).
Available placeholder arguments: `{source}`, `{renders}`, `{review}`, `{request}`,
`{findings}`, `{workspace}`, `{round}`. An adapter's process must exit nonzero
when it cannot do its advertised job; VQS does not synthesize missing results.

```bash
python -m pbip_documenter.visual_quality iterate my-workflow.json
python -m pbip_documenter.visual_quality.repair "path/to/Example.Report"        # dry run
python -m pbip_documenter.visual_quality.repair "path/to/Example.Report" --apply
```

The built-in fixer only aligns four-card rows after checking geometry. It **never**
changes DAX/M logic, drops data, changes chart type, hides axes or rewrites Word
pagination without a specialist. Use a project-specific executor for those
operations, working in a separate checkout and with reversible edits.

Each round: source-bound render → deterministic preflight → independent image
review → issue JSON → source repair → **new render** → independent re-review.
Unchanged source, missing adapter, invalid review and exhausted iteration budget
are explicit **blocked** outcomes in `iteration-history.json`, never success.
Resume after fixing the blocker; set a bounded per-run budget to control costs
rather than launching an unbounded, unauditable process. Stale evidence from an
older source revision is rejected. The review adapter must not be the executor.

## Scope and release boundaries

This is a reusable quality framework, not a claim that every chart can be
repaired by numeric geometry rules. An image reviewer must decide whether an
axis title is necessary, whether labels are actually readable, whether a visual
is semantically justified and whether the document has awkward page breaks.
Current deterministic metadata lint produces *advisories* for possible chart
label-density and table-size problems; only actual rendered observations
resolve them. A false or generic model review is a reviewer-quality failure,
not a reason to weaken thresholds.

**Current integration boundary:** Desktop report rendering requires a Windows
Power BI-capable renderer adapter (for example an authorized Desktop capture
service). The repository does not secretly start a Windows GUI from Linux or
claim a PBIR geometry diagram is a Desktop screenshot. The portable Word
adapter requires the external tools described above. Report-model refresh,
SemanticOps/PBIR schema validation, Word-content fidelity and merge approval
remain separate release gates in addition to VQS.
