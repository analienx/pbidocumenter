# PBIP Documenter project status

Lifecycle: **active**

Canonical workflow: `analienx/config:skills/supervisor-executor/SKILL.md`.

## Current supervised stream

- Issue #4 — Contoso semantic-model expansion and report redesign.
- Current repository default branch: `feature/expand-contoso-pbip`.
- `docs/supervisor-agent.md` remains useful historical/project context but is not the runtime control ledger.

CI-health issues #6 and #8 were resolved before this bootstrap rollout was finalized. The repair made the Windows Registry dependency platform-scoped, corrected TMDL table-name parsing after documentation comments, updated the expanded Contoso regression, and kept the Python 3.10 mypy target compatible with development dependencies. The integrated repair passed package, pytest, Ruff and mypy on Python 3.10–3.13 before merge.

The task issue and its newest comments are authoritative for the current objective, tool requirements and acceptance criteria.

## Supervisor acceptance rule

Do not accept completion from source edits alone. Where required by the task, verify:

1. model/report before-after inventories;
2. semantic/PBIR validation;
3. tests/CI;
4. successful PBIP Documenter generation;
5. rendered report/page screenshots;
6. generated document/wireframe output.

`.` resolves to issue #4 while that stream is the active context, unless a newer registered stream supersedes it.
