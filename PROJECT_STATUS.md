# PBIP Documenter project status

Lifecycle: **active**

Canonical workflow: `analienx/config:skills/supervisor-executor/SKILL.md`.

## Current supervised streams

- Issue #4 — Contoso semantic-model expansion and report redesign.
- Issue #6 — Linux CI collection failure from unconditional Windows-only `winreg` import.
- Current repository default branch: `feature/expand-contoso-pbip`.
- `docs/supervisor-agent.md` remains useful historical/project context but is not the runtime control ledger.

Issue #6 was discovered while validating the coordination-only bootstrap PR. It is intentionally separate because the bootstrap PR changes no Python production/test code. Until #6 is fixed, Linux test jobs fail before `ruff`/`mypy`, although the package job succeeds.

The relevant task issue and its newest comments are authoritative for each objective, tool requirement and acceptance criterion.

## Supervisor acceptance rule

Do not accept completion from source edits alone. Where required by the task, verify:

1. model/report before-after inventories;
2. semantic/PBIR validation;
3. tests/CI;
4. successful PBIP Documenter generation;
5. rendered report/page screenshots;
6. generated document/wireframe output.

`.` resolves from current conversation context/newest actionable Executor activity across the registered streams rather than assuming issue #4 unconditionally.
