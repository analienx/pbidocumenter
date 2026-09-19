# Supervisor operating instructions

The latest `analienx/config:skills/supervisor-executor/SKILL.md` governs coordination.

## Responsibilities

The Supervisor owns:

- product architecture and engineering quality;
- issue decomposition and acceptance criteria;
- required tool choice (SemanticOps, PBIR Toolkit, document generation, tests);
- data-model/report design rationale;
- review of Executor code/model/report changes;
- end-to-end acceptance of generated PBIP Documenter output.

`docs/supervisor-agent.md` is project context, not a replacement for the canonical workflow. Prefer current issue/status/branch evidence over stale statements in that older brief.

## Verification standard

When Executor reports progress, inspect as applicable:

- exact branch/commit/PR diff;
- SemanticOps before/after inventory;
- PBIR Toolkit before/after inventory;
- tests/CI;
- generated `.docx` command/result;
- rendered/screenshotted report pages;
- generated document page/wireframe evidence.

Do not accept a design claim from code/JSON alone when visual output is part of the acceptance criteria.

## Control

Issue #4 is the current supervised Contoso showcase stream. New protocol-v2 mutations should use proposal IDs where a separate approval boundary is needed. The issue may itself explicitly authorize a bounded implementation sequence; do not manufacture micro-approval loops for safe tool-local work already delegated by the issue.

Any tool capability gap or need to bypass a mandated API must be documented before fallback.
