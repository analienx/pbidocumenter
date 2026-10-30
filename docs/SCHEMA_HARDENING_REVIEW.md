# Native Word schema-layout hardening review

Status: review findings addressed in the code changes accompanying this report. Scope is **PBIPDocumenter only**; no VQS dependency, no PBIP source rewrite and no new layout engine.

## Review findings

| Severity | Finding | Resolution and regression |
| :-- | :-- | :-- |
| P2 | Relationship display order depended on source-file order when the anchor/starting-table sort priorities tied. This can change which edges survive the 24-relationship display limit. | Stable tie-break using both table names, columns, relationship name, activity and filtering settings; input-order permutation test, including 36 relationships. |
| P2 | The baseline-versus-optimized DOCX comparison temporarily replaced the module-level `schema._build_layout`, risking cross-test/process interference in concurrent use. | Dependency injection for `_render_focus(layout_builder=...)`; no module-global substitution; test verifies baseline and optimized DOCX output and unchanged global function identity. |
| P2 | Single-token or underscore-separated long semantic-model table identifiers could exceed Word node-label boxes: wrapping deliberately disabled word breaks, and the truncated second line could exceed the allotted width. | Bounded two-line wrapping with safe truncation and explicit tests for long ASCII, underscore-separated and Unicode labels. |
| P3 | Connected components of identical score could change presentation order if table insertion order changed. | Stable lexical tie-break using sorted component membership, tested on reversed table and relationship input. |
| P3 | The original regression suite concentrated on four fixed model sizes and Contoso, without edge-order permutations, role extremes or duplicate relationships. | Added graph-slot boundary checks for 1–19 non-anchor nodes, sparse/all-fact/all-dimension cases, duplicate-edge geometry and deterministic layout tests. |

## Review boundaries

- **Retained:** native DrawingML diagram shapes, relationship topology and labels, width/height constants, existing layout objective and legacy-layout fallback, the main example's original source.
- **Verified in source:** connector endpoints are placed on table boxes and the optimizer evaluates the same prioritized edge set that the DOCX renderer draws.
- **Measured separately:** the 209 combinations of 1–19 non-anchor nodes and dimension/fact counts have collision-free and in-bounds candidate slots; star, chain and dense graph checks up to 20 visible nodes completed.
- **Known limitations:** very dense graph structures can still contain unavoidable connector crossings; metric-based scoring does not guarantee perfect Word rendering or capture live Power BI layout. The 20-explicit-node focused view limit remains intentionally unchanged.

## Acceptance gates

1. All existing tests and new adversarial regression cases; lint and type checks.
2. Four simulated model sizes plus source-derived Contoso diagrams rendered and page-validated in GitHub-hosted CI.
3. Installed-wheel native DrawingML smoke acceptance and the existing DOCX/PDF source-fidelity gate.
4. Python 3.10, 3.11, 3.12 and 3.13.
5. No modification to the original local checkout or to private model sources.

The [layout-quality review](SCHEMA_LAYOUT_QUALITY.md) contains the already-published real Microsoft Word before/after captures and the source-to-document comparison methodology.

## Remaining risks and follow-up threshold

The original global search is deterministic for the evaluated graph, but dense nonplanar graphs can still need an improved edge-routing strategy. Do not expand this scope without demonstrated clipping, unreadable text or crossing regressions in actual Word output. The existing original-layout fallback remains available when the new scoring does not improve the diagram.
