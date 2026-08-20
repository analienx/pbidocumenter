# Executor operating instructions

The Executor may be an implementation agent when the assigned issue explicitly delegates PBIP/PBIR/model/report changes.

Read the latest canonical skill, `AGENTS.md`, `.supervisor/project.yaml`, this file, `PROJECT_STATUS.md`, then the assigned issue and newest comments.

## Startup

Before implementation:

1. confirm exact repo/ref/base branch;
2. preserve/classify unrelated local work;
3. inventory the current semantic model/report using the required tools;
4. record relevant before-state evidence;
5. follow the issue's required implementation order;
6. validate after each meaningful batch.

Do not silently switch to hand editing when SemanticOps/PBIR Toolkit exposes the required operation. If the tool lacks a capability, report the exact limitation and use only a narrowly justified fallback.

## Completion evidence

A completion report should identify:

- branch/commit/PR;
- exact model/report mutations;
- required tool calls/workflows used;
- tests/validation;
- generated PBIP Documenter output command/result;
- visual before/after evidence when report design changed;
- remaining limitations/tool gaps.

## Privacy

No client data, credentials, cache secrets or generated private artifacts in Git. Keep the bundled sample synthetic.

Unexpected source state, broken required tool, ambiguous model/report mutation, or validation failure => `BLOCKED`/`PARTIAL`; do not force PASS by weakening checks.
