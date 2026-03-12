"""Typed report model for report composition and rendering."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReportMetadata:
    """Top-level report metadata."""

    title: str
    subtitle: str
    dataset_label: str
    generated_at: str
    product_name: str = "Process Investigation Copilot"


@dataclass
class ReportKeyValue:
    """Simple key-value row for report summaries."""

    label: str
    value: str


@dataclass
class ReportTablePreview:
    """Compact table preview used for report sections."""

    title: str
    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    note: str | None = None


@dataclass
class ReportVisualReference:
    """Reference to a visual artifact rendered outside markdown."""

    title: str
    visual_type: str
    caption: str | None = None


@dataclass
class ReportSection:
    """Structured report section."""

    key: str
    title: str
    summary: str | None = None
    key_values: list[ReportKeyValue] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    tables: list[ReportTablePreview] = field(default_factory=list)
    visuals: list[ReportVisualReference] = field(default_factory=list)


@dataclass
class InvestigationReport:
    """Unified typed report object for markdown/PDF export pipelines."""

    metadata: ReportMetadata
    sections: list[ReportSection] = field(default_factory=list)
    appendix: list[ReportSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation of the report."""
        return asdict(self)
