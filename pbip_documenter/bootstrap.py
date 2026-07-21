"""Application bootstrap."""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Hand control to the installed CLI without modifying the environment."""
    from pbip_documenter.cli import main as cli_main

    result = cli_main(argv)
    return result if isinstance(result, int) else 0
