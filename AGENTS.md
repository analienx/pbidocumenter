# Repository Guidelines

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

No formal commit-message policy is configured. Use short, imperative subjects such as `Add Jira normalization fallback`, and keep each commit scoped to one logical change. Pull requests should explain purpose and behavior changes, list validation commands, link relevant issues, and include sample output or screenshots when generated Word layout changes. Do not commit real client reports, credentials, tokens, or generated build artifacts.
