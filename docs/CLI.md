# CLI reference — agent-first initial release

[← Product](../README.md) · [AI-agent workflow](AGENT_WORKFLOW.md) · [Actual Word output](EXAMPLES.md)

**One executable, one extraction engine, native editable Word diagrams.** The CLI makes it straightforward to inspect a Power BI project, detect source problems, generate its specification, and hand the result to an AI agent or CI pipeline.

## Get started

Install the current source:

    pipx install "git+https://github.com/analienx/pbidocumenter.git@main"

Run the four core commands:

    pbip-documenter inspect "./MyReport" --details --json
    pbip-documenter validate "./MyReport" --strict --json
    pbip-documenter generate "./MyReport" --mode full --output "./output/MyReport.docx" --strict --dry-run --json
    pbip-documenter generate "./MyReport" --mode full --output "./output/MyReport.docx" --strict --manifest --no-overwrite --json
    pbip-documenter doctor --json

**Existing scripts still work:** the historical direct command, for example `pbip-documenter ./MyReport --mode full -o document.docx`, remains supported.

## Commands and capabilities

| Command | Purpose | Main options |
| :--- | :--- | :--- |
| **generate** | Preflight PBIP/PBIR/TMDL and produce editable Word specifications using the established renderer | --mode default/full, --output, --output-dir, --dry-run, --manifest, --no-overwrite, --template, --logo, --strict, --json |
| **validate** | Diagnose recognizable malformed source files, including invalid PBIR pages/visuals and basic TMDL structural errors | --strict, --json |
| **inspect** | Return counts of tables, measures, relationships, roles, report pages and visuals | --details, --strict, --json |
| **doctor** | Check local runtime dependencies and optional template | --template, --json |

A project path may identify one PBIP project or a directory of projects. When an explicit single output filename is supplied, exactly one project must be selected. Without an explicit output, documents go under the working directory's **Exported Documents / ProjectName** tree.

Generation is read-only to PBIP source files, rejects nonexistent explicit templates and logos, and atomically replaces finished DOCX files. Saved diagrams are native Word DrawingML objects, not flattened screenshots.

## Preview, generate, verify

**1. Preview before writing.** The `--dry-run` option performs source validation and predicts output paths without creating directories or files:

    pbip-documenter generate "./MyReport" --mode full --strict --dry-run --output "./docs/spec.docx" --json

Inspect `planned_outputs`, `projects[].diagnostics` and `source_sha256`. A successful preview is not a guarantee that later Word generation will succeed.

**2. Generate with guardrails.** Write a complete editable DOCX with an opt-in handoff manifest:

    pbip-documenter generate "./MyReport" --mode full --strict --manifest --no-overwrite --output "./docs/spec.docx" --json

`--no-overwrite` refuses existing files, including the sidecar when requested. The DOCX and manifest use atomic no-clobber publication on supported local filesystems. A concurrent writer cannot silently replace their destination.

**3. Verify provenance.** The CLI returns `artifacts` with each document's SHA-256, source revision SHA-256, size, generator version, parser limitations and UTC generation time. With `--manifest`, it also writes `spec.manifest.json` alongside `spec.docx`. The manifest excludes raw DAX, connection strings and document contents.

**4. Process a portfolio.** For a parent directory of PBIP projects, use `--output-dir`:

    pbip-documenter generate "./Portfolio" --strict --mode full --output-dir "./Generated" --dry-run --json
    pbip-documenter generate "./Portfolio" --strict --mode full --output-dir "./Generated" --manifest --no-overwrite --json

Each project gets its own directory, document and optional manifest. Any source-validation error prevents all generation from starting. Later runtime failure can leave preceding successful documents: always inspect `outputs`, `artifacts` and `exit_code` before retrying.

Explicit templates must be valid Word DOCX archives; unsupported logo file extensions and invalid output extensions are rejected early. The historical command remains compatible.

## Stable machine-readable output

With --json, each command prints **exactly one JSON object** on stdout. No banner, progress output or human prose contaminates the machine result. Every result has:

| Field | Meaning |
| :--- | :--- |
| schema_version | Versioned contract, initially **1.0** |
| command | generate, validate, inspect or doctor |
| status | ok or error |
| exit_code | Numeric process result |
| projects | Per-project validation, diagnostics, parser mode and safe inventory when requested |
| outputs | Generated DOCX paths for successful generation |
| diagnostics | Command-level errors with stable codes, severities and remediation hints |
| planned_outputs | Predicted Word paths for generate, including dry-run |
| artifacts | Source and DOCX hash evidence for each successfully generated file |

Example inventory from the public fictional Contoso fixture (the digest is a placeholder):

    {
      "schema_version": "1.0",
      "command": "inspect",
      "status": "ok",
      "exit_code": 0,
      "projects": [{
        "project": "contoso-retail",
        "valid": true,
        "strict": false,
        "parser": {"mode": "python_fallback", "confidence": "high", "full_tmdl_grammar_verified": false},
        "inventory": {"tables": 12, "measures": 55, "relationships": 19, "roles": 0, "report_pages": 5, "report_visuals": 54, "completeness": "11/12"},
        "source_sha256": "<source-fingerprint>"
      }],
      "outputs": [],
      "diagnostics": []
    }

The optional --details includes table and page names, but never exports raw DAX expressions, source connection strings or credential secrets. [Formal JSON Schema](../schemas/cli-result-v1.schema.json). Diagnostic messages use stable codes (for example **TMDL_TABLE_UNPARSED**) and severity (**error**, **warning**, **info**).

## Exit codes

| Code | Meaning |
| ---: | :--- |
| 0 | Success; source passed the requested validation |
| 2 | Invalid source path or CLI configuration, including missing template/logo or multiple projects with one output |
| 3 | Structural source validation failed; strict mode also blocks parser warnings |
| 4 | Doctor found a required dependency or template unavailable |
| 5 | Unexpected processing/output-verification failure |

**Strict is not a Microsoft TMDL compiler.** The current lightweight Python parser reports its own mode and uncertainty. It detects missing, empty or obviously unparsed source artifacts, but cannot prove support for every TMDL grammar feature. Agents should not infer business requirements or tenant-level access from PBIP metadata.

## Recommended workflow

1. Run validate with --strict --json and review diagnostics.
2. Run inspect with --json and record the source fingerprint and inventory.
3. Run generate with --strict --json for the same project.
4. Verify the returned DOCX opens, contains Word native diagrams, and preserves expected source inventories.
5. Hand off the exact file, provenance and any outstanding confirmation items to the owner.

The [GitHub CI](../.github/workflows/ci.yml) verifies installed-package CLI commands on Linux and Windows. Existing acceptance also tests DOCX shape/connector integrity and actual PDF rendering. These tests validate the fictional public Contoso example, not arbitrary private projects.

**Release boundary:** This initial CLI work does not imply that PyPI has been published. Protected tagged publication remains tracked by [issue #31](https://github.com/analienx/pbidocumenter/issues/31).
