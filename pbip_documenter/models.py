"""
Data models for the PBIP documenter pipeline.

This module defines dataclasses that represent core entities
in a Power BI project (PBIP) structure.
"""

from dataclasses import dataclass, field


@dataclass
class DataSource:
    """
    Represents a detected data source connector from M/Power Query code.

    Attributes:
        fn: The connector function name (e.g., "Sql.Database")
        label: Human-readable label for the connector
        cat: Category classification (e.g., "SQL", "Azure", "Cloud")
        server: Server URL or identifier
        table_count: Number of tables using this source
        table_names: List of table names consuming this source
    """

    fn: str
    label: str
    cat: str
    server: str
    table_count: int = 0
    table_names: list[str] = field(default_factory=list)


@dataclass
class Observation:
    """
    A single technical observation about model/report quality.

    Observations are categorized by severity/type and rendered
    as observation cards in the generated document.

    Attributes:
        title: Short observation title/summary
        detail: Detailed explanation of the observation
        color: Hex color code for visual accent
        category: Classification ("Risks", "Warnings", "Info", "Good Practices")
    """

    title: str
    detail: str
    color: str
    category: str  # "Risks", "Warnings", "Info", "Good Practices"


@dataclass
class RenderState:
    """
    Tracks mutable state during document rendering.

    This maintains counters and identifiers that need to persist
    across multiple rendering operations within a single document.

    Attributes:
        obs_card_counter: Running count of observation cards rendered
        diagram_id_counter: Unique ID generator for diagram elements
        figure_number: Current figure number for captions
    """

    obs_card_counter: int = 0
    diagram_id_counter: int = 1000
    figure_number: int = 3
