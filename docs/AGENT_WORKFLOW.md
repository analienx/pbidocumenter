# Run PBIP Documenter with an AI agent

[← Repository overview](../README.md) · [CLI options](CLI.md) · [Real screenshots](EXAMPLES.md)

PBIP Documenter works well with agents because its core task has a **deterministic file input and output**. The agent does not need to navigate Power BI Desktop, impersonate a user or infer undocumented business requirements. Give it a PBIP project path, an output DOCX path and an explicit verification checklist.

## Copyable agent instruction

```text
You are documenting the Power BI project at:
  <ABSOLUTE_PATH_TO_PBIP_PROJECT>

1. Confirm this path contains a valid PBIP project. Do not edit any
   PBIP, PBIR, TMDL, source report or dataset files.
2. Run:
   pbip-documenter "<ABSOLUTE_PATH_TO_PBIP_PROJECT>"
     --mode full --output "<OUTPUT_DIRECTORY>/design-specification.docx"
3. Treat a nonzero exit code or missing output as failure.
4. Verify the DOCX opens and has substantive section headings, a
   semantic-model inventory, measures, relationships and report pages
   corresponding to the input.
5. Report extracted facts separately from generated recommendations
   and human-confirmation fields. Never invent scope, owners, RLS,
   classification, business impact or refresh SLAs.
6. Return the exact file path and a concise completeness summary.
   Do not publish source project or generated documents externally.
```

Run the command on **one project at a time** when passing `--output`. The CLI refuses an explicit single DOCX filename if it discovers multiple valid projects; without `--output`, each project gets a separate path beneath `Exported Documents/` in the working directory.

## Minimal terminal workflow

```bash
# Optional installation (normal project dependencies are installed explicitly)
pipx install pbip-documenter

# Generate the full design specification
pbip-documenter "path/to/YourProject" --mode full \
  --output "output/YourProject-design-specification.docx"
```

If you want the exact behavior in [the current repository screenshots](EXAMPLES.md), install from the matching Git commit rather than assuming the latest PyPI version includes unreleased changes.

## Recommended agent acceptance

| Gate | Expected behavior |
| :--- | :--- |
| **Source integrity** | Input PBIP/PBIR/TMDL files are not modified |
| **Command** | Installed `pbip-documenter` exits successfully |
| **DOCX** | Valid ZIP/OOXML, nonempty heading structure, substantive tables and diagrams |
| **Completeness** | Table, measure, relationship, page and visual counts are consistent with source |
| **Business certainty** | Suggested requirements and unverified metadata are explicitly flagged |
| **Privacy** | Source projects, DOCX files and logs remain in approved local/private locations |
| **Handoff** | Exact output path, mode, input revision and any warnings are provided |

The repository's own [CI](../.github/workflows/ci.yml) proves this for the fictional public Contoso fixture using installed-wheel generation, structured comparisons and rendered-page evidence. It cannot certify your customer's domain requirements or pixel-perfect Microsoft Word pagination.

## What the components do

```text
PBIP project directory
    |
    |--- report definition (PBIR: pages, visuals, bindings)
    |--- semantic model (TMDL: tables, measures, relationships)
    |
    v
copiloter.py                 Extract normalized source facts
    |
    v
pbip_documenter/cli.py      Select project, mode and output
    |
    v
services/document_service.py  Assemble Word specification
    |
    v
docx_render/                Apply headings, tables, diagrams, navigation
    |
    v
editable .docx              Agent checks and hands off to owner
```

See [architecture](ARCHITECTURE.md) for the code boundaries. For optional Power BI report-quality review, [VQS integration](VQS_OPTIONAL.md) is separate; it is **not** part of the document generator's success criteria.
