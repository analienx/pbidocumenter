# PBIP Documenter

[![CI](https://github.com/analienx/pbidocumenter/actions/workflows/ci.yml/badge.svg)](https://github.com/analienx/pbidocumenter/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pbip-documenter)](https://pypi.org/project/pbip-documenter/)
[![Python](https://img.shields.io/pypi/pyversions/pbip-documenter)](https://pypi.org/project/pbip-documenter/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

![PBIP Documenter social preview](docs/images/social-preview.png)

Turn a Power BI PBIP or PBIR project into a review-ready Word design
specification: semantic model, DAX, relationships, report pages, wireframes,
lineage, and maintainability observations.

## Install and run

```powershell
pipx install pbip-documenter
pbip-documenter examples/contoso-retail --mode full -o contoso-retail.docx
```

`pip install pbip-documenter` works too. The CLI never installs dependencies
into your environment at runtime.

The included **Contoso Retail** project is fictional and safe to use in demos.
Open the generated `.docx` in Word and update its table-of-contents fields.

## AI-agent quality and safe automatic fixes (optional VQS)

**PBIPDocumenter generates Word specifications; [Visual Quality System](https://github.com/analienx/visual-quality-system) checks and repairs Power BI reports.** You can use both without merging their parsers or making Word mandatory for Power BI quality.

Install VQS **into the same Python environment** as PBIPDocumenter. For the `pipx` installation shown above:

```powershell
pipx inject pbip-documenter "git+https://github.com/analienx/visual-quality-system.git@ab3185d86a6d4caa77e671a1d773630529c360df"
pbip-quality examples/contoso-retail --private-root ./private-vqs-evidence --mode repair
```

`pbip-quality` invokes the existing `vqs run --mode repair` orchestrator, applies **only supported allowlisted edits in an isolated candidate**, checks VQS's sealed event chain using `vqs run-status`, and returns structured JSON with **verdict, candidate, findings summary, source digest and evidence location**. It never promotes or overwrites your original PBIP, never publishes reports, and never treats a blocked native check as success.

For an agent, the recommended instruction is: *“Use `pbip-quality` to fix supported Power BI layout and design defects in a private candidate, verify the evidence, then give me Fixed / Verified / Blocked and the candidate path. Do not modify or publish my original.”*

**Codes:** `0` pass, `1` fail, `2` blocked. Static checks are not visual/interaction release acceptance. Native Desktop scope requires an explicitly authorized `--pid`; see the VQS [agent quickstart](https://github.com/analienx/visual-quality-system/blob/main/docs/AI_AGENT_QUICKSTART.md) and [component architecture](https://github.com/analienx/visual-quality-system/blob/main/docs/AGENT_AUTOFIX_ARCHITECTURE.md).

Both commands are separate: `pbip-documenter` still generates DOCX **without** installing or invoking VQS, while `pbip-quality` delegates quality decisions to VQS. Keep evidence roots outside your source tree and off public GitHub.

## What it documents

- Semantic-model tables, columns, measures, DAX, relationships, roles, and partitions.
- Report pages, visuals, filters, bookmarks, drill-through, themes, and bindings.
- Native Word schema, lineage, and page-wireframe diagrams.
- Actionable naming, dependency, privacy, and maintainability observations.

## Commands

```powershell
# Concise document (the default)
pbip-documenter path\to\report

# Full document
pbip-documenter path\to\report --mode full

# Check the installed version
pbip-documenter --version
```

See the [CLI reference](docs/CLI.md), [sample output gallery](docs/EXAMPLES.md),
and [advanced inventory guide](docs/INVENTORY.md).

## Privacy and scope

PBIP Documenter reads project files and writes a `.docx`; it does not alter
source reports. The core workflow is local-only. Power BI, Jira, SharePoint,
and cache-backed augmentation are advanced, opt-in integrations and may need
their optional dependencies and credentials.

Do not commit client PBIP projects, generated documents, credentials, or cache
contents. Use the synthetic sample for public issues and pull requests.

## Contributing

Issues and pull requests are welcome. Start with
[Contributing](CONTRIBUTING.md), use [GitHub Discussions](https://github.com/analienx/pbidocumenter/discussions)
for questions, and report vulnerabilities through the private process in
[Security](SECURITY.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
