"""Independent, versioned visual-quality evaluation of Power BI and Word outputs."""

from .runner import audit, iterate, request, snapshot

__all__ = ["audit", "iterate", "request", "snapshot"]
