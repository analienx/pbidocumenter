# Agent instructions — `analienx/pbidocumenter`

## Source locality — read this first

You are operating in a **LOCAL** checkout of `analienx/pbidocumenter`.

The canonical Supervisor ↔ Executor control plane is **EXTERNAL_GITHUB**:

- private GitHub repository: `analienx/config`
- canonical ref: `main`
- protocol: `skills/supervisor-executor/SKILL.md`
- registry: `supervisor/projects.yaml`

Notation such as `analienx/config:skills/supervisor-executor/SKILL.md` means **GitHub repository + repository path**, not a path inside this LOCAL checkout. Never assume `analienx/config` is already cloned locally.

Before meaningful supervised work, verify authenticated GitHub access and fetch the latest external canonical files. Preferred direct reads:

```sh
gh api -H "Accept: application/vnd.github.raw+json" "repos/analienx/config/contents/skills/supervisor-executor/SKILL.md?ref=main"
gh api -H "Accept: application/vnd.github.raw+json" "repos/analienx/config/contents/supervisor/projects.yaml?ref=main"
```

An authenticated `analienx/config` checkout may be used instead, but fetch/verify `origin/main` first. If canonical GitHub access is unavailable, do not claim policy is current and do not begin a newly authorized mutation; report `BLOCKED`. Bounded read-only orientation may continue if safe.

## Mandatory Supervisor ↔ Executor bootstrap

Before supervising or executing supervised work in this repository, load context in this order:

1. latest **EXTERNAL_GITHUB** `analienx/config/main:skills/supervisor-executor/SKILL.md`;
2. latest **EXTERNAL_GITHUB** `analienx/config/main:supervisor/projects.yaml`;
3. LOCAL `.supervisor/project.yaml`;
4. this LOCAL file;
5. LOCAL `SUPERVISOR.md` or `EXECUTOR.md` according to role;
6. LOCAL `PROJECT_STATUS.md`;
7. LOCAL project-specific design/architecture docs named by the active issue;
8. the assigned **EXTERNAL_GITHUB** issue and its **newest comments**;
9. referenced PR/commit/CI/rendered evidence.

Do not rely on cached global workflow text when GitHub access is available.

The canonical external skill governs coordination. This repository specializes it for PBIP/PBIR engineering. An Executor task may explicitly delegate implementation through local tools such as SemanticOps or PBIR Toolkit; when delegated, read current state first, use required tool APIs rather than bypassing them silently, validate each meaningful batch, preserve unrelated local work, and report exact evidence.

The repository default branch is currently `feature/expand-contoso-pbip`. Never silently assume `main` is the authoritative project target branch; use the task/PR base explicitly. This does **not** change the canonical control-plane ref, which remains external `analienx/config` `main`.

`.` means the canonical `supervise_latest` operation: resolve the active PBIP Documenter stream from context/external registry, fetch newest external issue comments, inspect referenced implementation/CI/rendered output, take the necessary supervisory action, and return a compact status without asking the user to relay Executor messages.

## Project Structure & Module Organization

`pbip_documenter/` contains the Python package and CLI. Core parsing and analysis live in `analysis/`; Word generation is in `docx_render/`; Power BI/Jira inventory integrations and matching logic are under `inventory/`; higher-level orchestration belongs in `services/`. Keep shared helpers in `utils/` and dependency/configuration wiring in the existing top-level modules. Tests are colocated in `pbip_documenter/tests/` and named `test_*.py`.

User PBIP inputs go in `Reports/`; generated `.docx` files go in `Exported Documents/`. Documentation and screenshots live in `docs/`, Word templates in `Templates/`, and Windows build helpers in `scripts/`. Treat `build/`, `dist/`, and generated documents as outputs, not source.

## Build, Test, and Development Commands

- `python -m pip install -e ".[all]"` installs the package in editable mode with inventory and development dependencies.
- `python -m pbip_documenter` runs concise documentation generation against `Reports/`.
- `python -m pbip_documenter --mode full` generates the expanded document variant.
- `python -m pytest pbip_documenter/tests` runs the complete test suite.
- `python -m pytest --cov=pbip_documenter pbip_documenter/tests` reports coverage.
- `ruff check .` checks imports, modernization, and style; `mypy pbip_documenter` performs strict type checks.
- `powershell -ExecutionPolicy Bypass -File scripts\build-exe.ps1` builds the Windows executable in `dist/` with PyInstaller.

## Coding Style & Naming Conventions

Target Python 3.10+, use four-space indentation, type every function, and keep lines at or below 120 characters. Ruff enforces `E`, `F`, `I`, `W`, `UP`, `B`, `C4`, and `SIM`; use Google-style docstrings where documentation adds value. Name modules, functions, and variables `snake_case`, classes `PascalCase`, and constants `UPPER_SNAKE_CASE`. Keep parsing, analysis, and rendering concerns separated.

## Testing Guidelines

Use pytest and add focused tests beside the existing suite. Name files `test_<feature>.py` and tests `test_<behavior>()`. Cover normal input, malformed or missing PBIP artifacts, and normalization edge cases. No fixed coverage threshold is configured; avoid reducing coverage in changed code.

## Commit & Pull Request Guidelines

No formal commit-message policy is configured. Use short, imperative subjects such as `Add Jira normalization fallback`, and keep each commit scoped to one logical change. Pull requests should explain purpose and behavior changes, list validation commands, link relevant issues, and include sample output or screenshots when generated Word layout changes. Do not commit real client reports, credentials, tokens, cache contents, or generated build/private artifacts.
