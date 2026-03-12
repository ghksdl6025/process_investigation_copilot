"""Render typed report objects into markdown."""

from __future__ import annotations

from src.process_investigation_copilot.reporting.report_model import (
    InvestigationReport,
    ReportSection,
    ReportTablePreview,
)


def render_report_markdown(report: InvestigationReport) -> str:
    """Render a typed report object as markdown text."""

    lines: list[str] = [
        f"# {report.metadata.title}",
        "",
        f"**{report.metadata.product_name}**",
        "",
        f"- Dataset: {report.metadata.dataset_label}",
        f"- Generated at: {report.metadata.generated_at}",
        "",
    ]

    if report.metadata.subtitle:
        lines.extend([report.metadata.subtitle, ""])

    for section in report.sections:
        _append_section(lines, section, level=2)

    if report.appendix:
        lines.extend(["## Appendix", ""])
        for section in report.appendix:
            _append_section(lines, section, level=3)

    return "\n".join(lines).strip() + "\n"


def _append_section(lines: list[str], section: ReportSection, level: int) -> None:
    lines.extend([f"{'#' * level} {section.title}", ""])

    if section.summary:
        lines.extend([section.summary, ""])

    if section.key_values:
        for row in section.key_values:
            lines.append(f"- **{row.label}:** {row.value}")
        lines.append("")

    if section.paragraphs:
        for paragraph in section.paragraphs:
            lines.extend([paragraph, ""])

    if section.bullets:
        for bullet in section.bullets:
            lines.append(f"- {bullet}")
        lines.append("")

    if section.tables:
        for table in section.tables:
            _append_table(lines, table)

    if section.visuals:
        lines.append("Visuals:")
        for visual in section.visuals:
            caption = f" - {visual.caption}" if visual.caption else ""
            lines.append(f"- {visual.title} ({visual.visual_type}){caption}")
        lines.append("")


def _append_table(lines: list[str], table: ReportTablePreview) -> None:
    lines.extend([f"**{table.title}**", ""])
    if not table.columns:
        lines.extend(["_No columns available_", ""])
        return

    header = "| " + " | ".join(table.columns) + " |"
    separator = "| " + " | ".join("---" for _ in table.columns) + " |"
    lines.extend([header, separator])
    for row in table.rows:
        padded = row + [""] * max(0, len(table.columns) - len(row))
        lines.append("| " + " | ".join(padded[: len(table.columns)]) + " |")
    lines.append("")

    if table.note:
        lines.extend([f"_Note: {table.note}_", ""])
