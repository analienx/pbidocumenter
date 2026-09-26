# Supervisor Agent — Data-Model Expansion Brief

Status: **Draft** (expand Contoso sample before the repo goes public)

## Mission

Before `analienx/pbidocumenter` is switched to public, significantly upgrade the
**Contoso Retail** example semantic model so it demonstrates a production-grade
data model for the documentation generator. Target: **at least twelve tables**,
richer relationships, and **more complex DAX measures and M (Power Query) queries**
than the current five-table sample. This is the acceptance bar for the public release.

## Why

A public repository is the project's calling card. The bundled sample is the first
thing a reviewer opens, and it sets the expectation for what PBIP documentation
quality looks like. Today the sample is too small to exercise the documenter's
relationship rendering, measure-expression output, or query-group handling.

## Current state (authoritative, verify with git/gh before assuming)

- Upstream repo: `analienx/pbidocumenter` (private). Remote pushed from the
  `feature/expand-contoso-pbip` branch.
- Sample lives in `examples/contoso-retail/` (PBIR/PBIP project format).
- Recent history on that branch:
  - `Expand Contoso model to twelve tables` — twelve tables are already present
    in principle; this brief is about making them *meaningful* (relations, measures).
  - `Replace legacy Contoso fixture with modern PBIR`
  - `Strengthen Contoso star schema sample`
- Uncommitted local work exists (additional pages, a handover zip). Treat as
  work-in-progress; do not destroy.

## Work to direct

The supervisor should issue concrete, verifiable instructions covering:

### 1. Data model (via SemanticOps MCP)
- Enumerate the current tables (`list tables`), confirm the count, and map each
  to a role: fact vs. dimension vs. date/support.
- Ensure the star schema is coherent: every fact table joins to dimensions, keys
  are consistent, no dangling or duplicate relationships. Add relationships
  (`create_relationship`) where missing.
- Expand toward "at least twelve tables" with a mix that exercises the documenter:
  - Multiple fact tables (sales, returns, inventory, promotions) so the doc shows
    several relationship clusters.
  - Shared dimensions (date, geography, product) re-used across facts.
  - A slow-changing dimension or support/hidden table to test hidden-artifact handling.
- Add a proper date table marked as the model's date table.

### 2. DAX measures
- Add **complex**, idiomatic DAX across measures: time intelligence
  (`CALCULATE`, `DATESYTD`, `SAMEPERIODLASTYEAR`, `TOTALYTD`), `filter` context
  with `ALL`/`FILTER`, iterators (SUMX/AVERAGEX), and variables (`VAR`/`RETURN`).
  Keep expressions readable so the documenter's code-rendering looks good.
- Add formatted measures (`format_string`) and a couple of loosely/deprecation-tagged
  annotations to show they surface in documentation.
- Include a measure with `format` differences (currency vs. percent) to validate the
  doc layout for number formatting.

### 3. M / Power Query queries
- Where tables are calculated or imported, author real M in named expressions /
  query groups: use `let ... in` chains, `Table.TransformColumnTypes`, `Date`/`Text`
  transforms, `Table.AddColumn` for computed fields, and a parameterized step.
- Ensure query groups are organically organized so the documenter renders query
  groups (not a flat soup).

### 4. Relationship & metadata hygiene
- Name relationships descriptively (`FactSales-to-DimDate`).
- Confirm `crossFilteringBehavior` and single active relationship per path where
  appropriate.
- Fill `description` on tables, columns, and measures — documentation is only as
  good as the descriptions it prints. Reject any instruction to add lorem-ipsum;
  use realistic retail copy.

## How work should proceed

1. **Connect** to the model via SemanticOps (`manage_model_connection`), then
   read state before writing anything.
2. **Dry-run / preview** changesets before mutating the model, and validate before
   starting a new batch (per the tool's own guidance).
3. Every model change must be **verifiable**: re-list tables/measures/relationships
   afterward and diff against the target.
4. After model changes, regenerate the sample documentation through the pipeline
   (`python -m pbip_documenter ...` against `examples/contoso-retail/`) to confirm
   the new model renders — this is the real acceptance test.

## Out of scope for the supervisor

- Word-template styling, CLI flags, packaging/build (`scripts/build-exe.ps1`).
- Publishing the repo to public (a human step, later).
- Any real client data, credentials, or tokens.

## Definition of done

- Twelve (or more) tables form a coherent star schema with descriptive
  relationships and a marked date table.
- Measure suite includes non-trivial time-intelligence and iterator DAX with
  `VAR/RETURN`, plus varied format strings.
- Named expressions / query groups use realistic, structured M.
- Descriptions present on the key tables/columns/measures.
- The documentation generator consumes the expanded sample without error, and the
  rendered output reflects the twelve-table model.
- All model edits were made through SemanticOps tools and validated after each batch.