# Contributing to PBIP Documenter

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install ".[all]"
```

Or let the local CI replica provision it for you (see below).

## Gates (must pass before review)

Hosted CI runs pytest, ruff, and mypy. Run the same locally:

```powershell
python scripts/ci_local.py
```

This creates `.venv` on first run, installs `.[all]`, and runs the
full gate set. `python scripts/ci_local.py --pytest-only` skips
ruff/mypy for a quick check.

## PR rules

- Keep public history clean: one concern per PR, rebase on `main`
  before requesting review.
- Tests for behavior changes; docs for user-visible changes.
- Never commit client PBIP projects, generated `.docx` files,
  credentials, or cache contents. Use `examples/contoso-retail`
  (fictional, safe) for public issues and pull requests.

## Releasing

Releases are cut from `main` via version tags; `release.yml`
publishes to PyPI and attaches the built distributions to the
GitHub release. Bump the version in
`pbip_documenter/version.py` and add a `CHANGELOG.md` entry first.
