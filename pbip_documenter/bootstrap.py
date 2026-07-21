"""Application bootstrap."""

from __future__ import annotations

import typing
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> typing.Any:
    """Hand control to the installed CLI without modifying the environment."""
    from pbip_documenter.cli import main as cli_main

    result = cli_main(argv)
    return result if isinstance(result, int) else 0
