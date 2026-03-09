"""PDF export utilities for combined process investigation reports."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from collections import defaultdict
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Line, Rect, String


def build_mvp_pdf_report(
    *,
    dataset_label: str | None,
    validation_report: dict[str, Any] | None,
    dashboard_payload: dict[str, Any],
    process_view_payload: dict[str, Any] | None,
    investigation_payload: dict[str, Any] | None,
) -> bytes:
    """Build a legacy MVP PDF report (kept for backward compatibility)."""
    return build_curated_pdf_report(
        dataset_label=dataset_label,
        validation_report=validation_report,
        dashboard_payload=dashboard_payload,
        process_view_payload=process_view_payload,
        investigation_payload=investigation_payload,
    )


def build_curated_pdf_report(
    *,
    dataset_label: str | None,
    validation_report: dict[str, Any] | None,
    dashboard_payload: dict[str, Any],
    process_view_payload: dict[str, Any] | None,
    investigation_payload: dict[str, Any] | None,
) -> bytes:
    """Build a curated report-style PDF summary for stakeholder reading."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Process Investigation Copilot Report",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = _build_report_styles()
    story: list[Any] = []

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    cover_rows = [
        ["Dataset", dataset_label or "Unknown dataset"],
        ["Exported at", generated_at],
    ]
    story.extend(
        [
            Paragraph("Process Investigation Copilot", styles["ReportTitle"]),
            Spacer(1, 6),
            Paragraph("Investigation Report", styles["ReportSubtitle"]),
            Spacer(1, 12),
            _kv_table(cover_rows, label_bg="#eef2ff", widths=[110 * mm, 65 * mm]),
            Spacer(1, 10),
            Paragraph(
                "This report summarizes deterministic analysis outputs for process performance and delay investigation.",
                styles["Body"],
            ),
        ]
    )

    sections: list[list[Any]] = []

    executive_section: list[Any] = []
    _append_executive_summary(
        executive_section,
        styles,
        dashboard_payload,
        investigation_payload,
        validation_report,
    )
    sections.append(executive_section)

    data_section: list[Any] = []
    if _append_data_readiness(data_section, styles, validation_report, dashboard_payload):
        sections.append(data_section)

    performance_section: list[Any] = []
    if _append_performance_summary(performance_section, styles, dashboard_payload):
        sections.append(performance_section)

    delay_section: list[Any] = []
    if _append_delay_drivers(delay_section, styles, dashboard_payload):
        sections.append(delay_section)

    process_section: list[Any] = []
    if _append_process_view_summary(process_section, styles, process_view_payload):
        sections.append(process_section)

    investigation_section: list[Any] = []
    if _append_investigation_summary(investigation_section, styles, investigation_payload):
        sections.append(investigation_section)

    next_steps_section: list[Any] = []
    if _append_next_steps(
        next_steps_section,
        styles,
        dashboard_payload=dashboard_payload,
        process_view_payload=process_view_payload,
        validation_report=validation_report,
    ):
        sections.append(next_steps_section)

    for section in sections:
        story.append(CondPageBreak(72))
        story.append(Spacer(1, 14))
        story.extend(section)

    doc.build(
        story,
        onFirstPage=_draw_page_chrome,
        onLaterPages=_draw_page_chrome,
    )
    return buffer.getvalue()


def _build_report_styles() -> StyleSheet1:
    base = getSampleStyleSheet()
    styles = StyleSheet1()
    for name in base.byName:
        styles.add(base[name])

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#111827"),
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Heading2"],
            fontName="Helvetica",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#374151"),
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#111827"),
            spaceBefore=0,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubsectionTitle",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1f2937"),
            spaceBefore=0,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Muted",
            parent=styles["Body"],
            textColor=colors.HexColor("#6b7280"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportBullet",
            parent=styles["Body"],
            leftIndent=10,
            bulletIndent=0,
            spaceAfter=2,
        )
    )
    return styles


def _append_executive_summary(
    story: list[Any],
    styles: StyleSheet1,
    dashboard_payload: dict[str, Any],
    investigation_payload: dict[str, Any] | None,
    validation_report: dict[str, Any] | None,
) -> None:
    head = [Paragraph("Executive Summary", styles["SectionTitle"])]
    story.append(KeepTogether(head))

    paragraph = _build_executive_paragraph(dashboard_payload, validation_report)
    summary_block: list[Any] = [Paragraph(paragraph, styles["Body"])]

    findings_block: list[Any] = [Paragraph("Top findings", styles["SubsectionTitle"])]
    findings = _build_top_findings(dashboard_payload)
    if not findings and investigation_payload:
        findings = [f.get("title", "N/A") for f in investigation_payload.get("top_suspicious_factors", [])]
    if not findings:
        findings = ["No strong findings were available at export time."]
    for finding in findings[:3]:
        findings_block.append(Paragraph(f"- {finding}", styles["ReportBullet"]))

    story.append(_two_column_layout(summary_block, findings_block))


def _append_data_readiness(
    story: list[Any], styles: StyleSheet1, validation_report: dict[str, Any] | None, dashboard_payload: dict[str, Any]
) -> bool:
    if not validation_report:
        return False

    story.append(KeepTogether([Paragraph("Data Readiness", styles["SectionTitle"])]))

    overview = dashboard_payload.get("overview_metrics", {})
    metrics = validation_report.get("metrics", {})
    if validation_report.get("is_valid", False):
        status = "Ready with limitations" if validation_report.get("warnings") else "Ready for analysis"
    else:
        status = "Action needed"

    rows = [
        ["Dataset status", status],
        ["Events", _fmt_int(overview.get("events", metrics.get("row_count")))],
        ["Cases", _fmt_int(metrics.get("case_count"))],
        ["Activities", _fmt_int(metrics.get("activity_count"))],
        ["Timestamp parse success", _fmt_pct(metrics.get("timestamp_parse_success_rate"))],
        [
            "Parsed timestamp date range",
            _date_range(metrics.get("date_range_start"), metrics.get("date_range_end")),
        ],
    ]
    story.append(_kv_table(rows))
    story.append(Spacer(1, 6))

    limitation_messages = _normalize_messages(validation_report.get("blocking_errors", []))
    limitation_messages.extend(_normalize_messages(validation_report.get("warnings", [])))

    if limitation_messages:
        story.append(Paragraph("Important limitations", styles["SubsectionTitle"]))
        for message in limitation_messages[:4]:
            story.append(Paragraph(f"- {_with_data_impact(message, metrics)}", styles["ReportBullet"]))
    else:
        story.append(Paragraph("No critical data-quality limitations were detected.", styles["Body"]))

    return True


def _append_performance_summary(story: list[Any], styles: StyleSheet1, payload: dict[str, Any]) -> bool:
    if not payload:
        return False

    story.append(KeepTogether([Paragraph("Performance Summary", styles["SectionTitle"])]))

    period_metrics = payload.get("period_metrics", {})
    recent = period_metrics.get("recent", {})
    previous = period_metrics.get("previous", {})
    percent = period_metrics.get("percent_diff", {})
    slow_case_ratio = _resolve_slow_case_ratio(payload)
    slow_case_count = payload.get("slow_case_count")
    if slow_case_ratio is None and _to_float(slow_case_count) is not None:
        slow_case_ratio_text = "N/A (insufficient total-case context)"
    else:
        slow_case_ratio_text = _fmt_pct(slow_case_ratio)

    avg_delta = percent.get("avg_duration_hours")
    rows = [
        ["Recent average duration", _fmt_duration_hours(recent.get("avg_duration_hours"))],
        ["Previous average duration", _fmt_duration_hours(previous.get("avg_duration_hours"))],
        ["Average duration change", _fmt_pct(avg_delta, signed=True)],
        ["Recent median duration", _fmt_duration_hours(recent.get("median_duration_hours"))],
        ["Median duration change", _fmt_pct(percent.get("median_duration_hours"), signed=True)],
        ["Recent P90 duration", _fmt_duration_hours(recent.get("p90_duration_hours"))],
        ["P90 duration change", _fmt_pct(percent.get("p90_duration_hours"), signed=True)],
        ["Slow-case ratio", slow_case_ratio_text],
        ["Slow-case count", _fmt_int(payload.get("slow_case_count"))],
    ]
    story.append(_kv_table(rows))
    story.append(Spacer(1, 6))

    story.append(Paragraph(f"Summary: {_build_performance_takeaway(avg_delta)}", styles["Body"]))

    period_note = payload.get("period_note")
    if period_note:
        story.append(Paragraph(f"Period context: {period_note}", styles["Muted"]))

    return True


def _append_delay_drivers(story: list[Any], styles: StyleSheet1, payload: dict[str, Any]) -> bool:
    top_delayed = payload.get("top_delayed_activities", [])
    rework_note = payload.get("rework_signal")
    if not top_delayed and not rework_note:
        return False

    story.append(KeepTogether([Paragraph("Delay Drivers", styles["SectionTitle"])]))

    if top_delayed:
        story.append(Paragraph("Key delay signals", styles["SubsectionTitle"]))
        for row in top_delayed[:3]:
            story.append(
                Paragraph(
                    f"- {row.get('activity', 'N/A')}: {_fmt_minutes(row.get('absolute_increase_minutes'))} increase "
                    f"(support volume: {_fmt_int(row.get('support_volume'))}).",
                    styles["ReportBullet"],
                )
            )

        table_rows = [["Activity", "Delay change", "Support"]]
        for row in top_delayed[:5]:
            table_rows.append(
                [
                    str(row.get("activity", "N/A")),
                    _fmt_minutes(row.get("absolute_increase_minutes")),
                    _fmt_int(row.get("support_volume")),
                ]
            )
        story.append(Spacer(1, 4))
        story.append(_simple_table(table_rows))

    if rework_note:
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Rework signal: {rework_note}", styles["Body"]))

    return True


def _append_process_view_summary(story: list[Any], styles: StyleSheet1, payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False

    story.append(KeepTogether([Paragraph("Process Snapshot", styles["SectionTitle"])]))

    summary_block: list[Any] = [_compact_process_meta_table(payload)]
    graph_block: list[Any] = []
    dfg_edges = payload.get("dfg_edges", [])
    top_edges = payload.get("top_edges", [])
    if dfg_edges:
        graph_block.append(Paragraph("Directly-follows graph snapshot", styles["SubsectionTitle"]))
        graph_block.append(_build_dfg_graph_drawing(dfg_edges))
    elif top_edges:
        graph_block.append(Paragraph("Transition intensity snapshot", styles["SubsectionTitle"]))
        graph_block.append(_build_transition_snapshot_chart(top_edges))

    if graph_block:
        story.append(_two_column_layout(summary_block, graph_block))
    else:
        story.extend(summary_block)

    insights = payload.get("insights", {})
    lines: list[str] = []
    mapping = {
        "most_frequent": "Most frequent transition",
        "slowest_average": "Slowest average transition",
        "bottleneck_candidate": "Bottleneck candidate",
    }
    for key, label in mapping.items():
        insight = insights.get(key)
        if not insight:
            continue
        lines.append(f"- {label}: {_fmt_text(insight.get('transition'))} ({_fmt_text(insight.get('value'))})")

    if lines:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Transition highlights", styles["SubsectionTitle"]))
        for line in lines:
            story.append(Paragraph(line, styles["ReportBullet"]))

    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            "Note: Bottleneck indicators are descriptive signals, not proof of root cause.",
            styles["Muted"],
        )
    )

    return True


def _append_investigation_summary(
    story: list[Any], styles: StyleSheet1, payload: dict[str, Any] | None
) -> bool:
    if not payload:
        return False

    answer_blocks = payload.get("answer_blocks", [])
    follow_ups = payload.get("follow_up_questions", [])
    top_factors = payload.get("top_suspicious_factors", [])
    limitations = payload.get("limitations", [])
    if not any([answer_blocks, follow_ups, top_factors, limitations]):
        return False

    story.append(KeepTogether([Paragraph("Investigation Answer", styles["SectionTitle"])]))

    question_type = _fmt_text(payload.get("question_type"))
    support_text = "Supported" if payload.get("is_supported") else "Partially supported"
    story.append(Paragraph(f"Question category: {question_type} | Evidence status: {support_text}", styles["Body"]))

    if answer_blocks:
        story.append(Spacer(1, 5))
        for block in answer_blocks:
            title = _fmt_text(block.get("title", "Section"))
            text = _fmt_text(block.get("text", "N/A")).replace("\n", " ")
            story.append(Paragraph(f"<b>{title}:</b> {text}", styles["Body"]))

    if top_factors:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Top investigation signals", styles["SubsectionTitle"]))
        for factor in top_factors[:3]:
            title = _fmt_text(factor.get("title"))
            evidence = _fmt_text(factor.get("evidence"))
            story.append(Paragraph(f"- {title}: {evidence}", styles["ReportBullet"]))

    if limitations:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Limitations", styles["SubsectionTitle"]))
        for limitation in limitations[:4]:
            story.append(Paragraph(f"- {_fmt_text(limitation)}", styles["ReportBullet"]))

    if follow_ups:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Suggested next questions", styles["SubsectionTitle"]))
        for question in follow_ups[:3]:
            story.append(Paragraph(f"- {_fmt_text(question)}", styles["ReportBullet"]))

    return True


def _append_next_steps(
    story: list[Any],
    styles: StyleSheet1,
    *,
    dashboard_payload: dict[str, Any],
    process_view_payload: dict[str, Any] | None,
    validation_report: dict[str, Any] | None,
) -> bool:
    story.append(KeepTogether([Paragraph("Next Steps", styles["SectionTitle"])]))

    actions: list[str] = []
    top_delayed = dashboard_payload.get("top_delayed_activities", [])
    if top_delayed:
        top_names = ", ".join(str(row.get("activity", "N/A")) for row in top_delayed[:2])
        actions.append(f"Investigate the highest-delay activities first ({top_names}).")

    if process_view_payload and process_view_payload.get("insights", {}).get("bottleneck_candidate"):
        actions.append("Review bottleneck candidate transitions in Process View before operational changes.")

    limitation = _extract_main_data_limitation(validation_report)
    if limitation:
        actions.append("Validate timestamp and data quality limitations before final business decisions.")

    if not actions:
        actions.append("Review investigation findings and prioritize one measurable process improvement experiment.")
        actions.append("Re-run the report after the next period to confirm whether key delays are improving.")

    for action in actions[:3]:
        story.append(Paragraph(f"- {action}", styles["ReportBullet"]))
    return True


def _build_transition_snapshot_chart(top_edges: list[dict[str, Any]], chart_width: float = 86 * mm) -> Drawing:
    edges = top_edges[:5]
    width = chart_width
    row_height = 11 * mm
    chart_height = max(34 * mm, (len(edges) + 1) * row_height)
    drawing = Drawing(width, chart_height)

    left = 8 * mm
    top = chart_height - 8 * mm
    bar_x = width * 0.54
    bar_w = width * 0.34
    max_freq = max((_to_float(edge.get("transition_frequency")) or 0 for edge in edges), default=1.0)
    if max_freq <= 0:
        max_freq = 1.0

    drawing.add(Rect(0, 0, width, chart_height, fillColor=colors.white, strokeColor=colors.HexColor("#e5e7eb")))
    drawing.add(String(left, top + 2 * mm, "Top transitions by frequency", fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#111827")))

    y = top - 7 * mm
    for edge in edges:
        src = _fmt_text(edge.get("source_activity"))
        tgt = _fmt_text(edge.get("target_activity"))
        label = f"{src} -> {tgt}"
        freq = _to_float(edge.get("transition_frequency")) or 0.0
        minutes = _fmt_minutes(edge.get("avg_transition_minutes"))

        drawing.add(String(left, y, _truncate(label, 44), fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#1f2937")))
        drawing.add(String(left, y - 3.8 * mm, f"Avg: {minutes}", fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#6b7280")))

        drawing.add(Rect(bar_x, y - 1.5 * mm, bar_w, 2.8 * mm, fillColor=colors.HexColor("#f3f4f6"), strokeColor=None))
        fill_w = max(1.5 * mm, (freq / max_freq) * bar_w)
        drawing.add(Rect(bar_x, y - 1.5 * mm, fill_w, 2.8 * mm, fillColor=colors.HexColor("#4f46e5"), strokeColor=None))
        drawing.add(String(bar_x + bar_w + 1.5 * mm, y - 0.8 * mm, _fmt_int(freq), fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#111827")))

        y -= row_height

    drawing.add(Line(bar_x, 5 * mm, bar_x + bar_w, 5 * mm, strokeColor=colors.HexColor("#d1d5db"), strokeWidth=0.6))
    drawing.add(String(bar_x, 1.5 * mm, "Lower", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#6b7280")))
    drawing.add(String(bar_x + bar_w - 9 * mm, 1.5 * mm, "Higher", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#6b7280")))
    return drawing


def _build_executive_paragraph(
    dashboard_payload: dict[str, Any], validation_report: dict[str, Any] | None
) -> str:
    period_metrics = dashboard_payload.get("period_metrics", {})
    avg_delta = period_metrics.get("percent_diff", {}).get("avg_duration_hours")

    top_delay = dashboard_payload.get("top_delayed_activity") or {}
    delay_activity = top_delay.get("activity")
    delay_increase = top_delay.get("absolute_increase_minutes")

    slow_ratio = dashboard_payload.get("slow_case_ratio")

    change_sentence = _build_performance_takeaway(avg_delta)

    if delay_activity:
        delay_sentence = (
            f"The strongest delay signal is {delay_activity}, with an estimated {_fmt_minutes(delay_increase)} increase."
        )
    else:
        delay_sentence = "No single activity-level delay signal was strong enough to rank clearly."

    resolved_ratio = _resolve_slow_case_ratio(dashboard_payload)
    if resolved_ratio is None:
        slow_sentence = "Slow-case share could not be estimated from available totals."
    else:
        slow_sentence = f"Slow cases account for {_fmt_pct(resolved_ratio)} of analyzed cases."

    limitation_sentence = ""
    limitation = _extract_main_data_limitation(validation_report)
    if limitation:
        limitation_sentence = f" Main data-quality limitation: {limitation}."

    return f"{change_sentence} {delay_sentence} {slow_sentence}{limitation_sentence}".replace("..", ".")


def _build_top_findings(dashboard_payload: dict[str, Any]) -> list[str]:
    findings: list[str] = []

    period_metrics = dashboard_payload.get("period_metrics", {})
    avg_delta = period_metrics.get("percent_diff", {}).get("avg_duration_hours")
    if avg_delta is not None:
        findings.append(f"Average processing time changed by {_fmt_pct(avg_delta, signed=True)} in the recent period.")

    slow_ratio = dashboard_payload.get("slow_case_ratio")
    if slow_ratio is not None:
        findings.append(f"Slow-case share is {_fmt_pct(slow_ratio)}.")

    top_delayed = dashboard_payload.get("top_delayed_activity")
    if top_delayed:
        findings.append(
            f"Largest delay signal: {top_delayed.get('activity', 'N/A')} ({_fmt_minutes(top_delayed.get('absolute_increase_minutes'))})."
        )

    return findings


def _build_performance_takeaway(avg_delta: Any) -> str:
    delta = _to_float(avg_delta)
    if delta is None:
        return "Period comparison is available, but the overall change in processing time could not be quantified."
    if delta > 0:
        return f"Processing time increased by {_fmt_pct(delta)} versus the previous period."
    if delta < 0:
        return f"Processing time decreased by {_fmt_pct(abs(delta))} versus the previous period."
    return "Processing time remained stable versus the previous period."


def _extract_main_data_limitation(validation_report: dict[str, Any] | None) -> str | None:
    if not validation_report:
        return None

    messages = _normalize_messages(validation_report.get("blocking_errors", []))
    messages.extend(_normalize_messages(validation_report.get("warnings", [])))
    if not messages:
        return None

    metrics = validation_report.get("metrics", {})
    for message in messages:
        if "timestamp" in message.lower():
            return _with_data_impact(message, metrics)

    return messages[0]


def _normalize_messages(items: list[Any]) -> list[str]:
    messages: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            text = item.get("message")
        else:
            text = str(item)
        text = str(text).strip()
        if text:
            messages.append(text)
    return messages


def _with_data_impact(message: str, metrics: dict[str, Any]) -> str:
    lower = message.lower()
    if "timestamp" not in lower:
        return message

    rate = _to_float(metrics.get("timestamp_parse_success_rate"))
    if rate is None:
        return message

    if rate < 0.8:
        return (
            f"{message} This can reduce confidence in time-based comparisons because only {_fmt_pct(rate)} of timestamps were parsed."
        )
    if rate < 0.95:
        return (
            f"{message} Time-based metrics may be partially affected because timestamp parsing succeeded for {_fmt_pct(rate)} of rows."
        )
    return message


def _kv_table(rows: list[list[str]], label_bg: str = "#f3f4f6", widths: list[float] | None = None) -> Table:
    table = Table(rows, colWidths=widths or [60 * mm, 115 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(label_bg)),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _compact_process_meta_table(payload: dict[str, Any]) -> Table:
    rows = [
        ["Mode", _fmt_text(payload.get("mode")), "Subset", _fmt_text(payload.get("subset"))],
        ["Cases", _fmt_int(payload.get("case_count")), "Events", _fmt_int(payload.get("event_count"))],
        ["Visible transitions", _fmt_int(payload.get("edge_count")), "", ""],
    ]
    table = Table(rows, colWidths=[26 * mm, 30 * mm, 26 * mm, 30 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef2ff")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("SPAN", (0, 2), (0, 2)),
                ("SPAN", (1, 2), (3, 2)),
            ]
        )
    )
    return table


def _simple_table(rows: list[list[str]]) -> Table:
    table = Table(rows, colWidths=[85 * mm, 45 * mm, 40 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _two_column_layout(
    left_block: list[Any],
    right_block: list[Any],
    widths: tuple[float, float] = (86 * mm, 86 * mm),
) -> Table:
    table = Table([[left_block, right_block]], colWidths=[widths[0], widths[1]])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _draw_page_chrome(canvas: Any, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    page_width, page_height = A4

    canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, page_height - doc.topMargin + 4 * mm, page_width - doc.rightMargin, page_height - doc.topMargin + 4 * mm)
    canvas.line(doc.leftMargin, doc.bottomMargin - 4 * mm, page_width - doc.rightMargin, doc.bottomMargin - 4 * mm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(doc.leftMargin, doc.bottomMargin - 7.5 * mm, "Process Investigation Copilot")
    canvas.drawRightString(page_width - doc.rightMargin, doc.bottomMargin - 7.5 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _build_dfg_graph_drawing(dfg_edges: list[dict[str, Any]]) -> Drawing:
    edges_df = pd.DataFrame(dfg_edges).head(28).copy()
    if edges_df.empty:
        return Drawing(86 * mm, 48 * mm)

    edges_df["source_activity"] = edges_df["source_activity"].astype(str)
    edges_df["target_activity"] = edges_df["target_activity"].astype(str)
    edges_df["transition_frequency"] = pd.to_numeric(
        edges_df["transition_frequency"], errors="coerce"
    ).fillna(0.0)
    edges_df = edges_df.sort_values("transition_frequency", ascending=False)

    nodes = sorted(set(edges_df["source_activity"]).union(set(edges_df["target_activity"])))
    layers = _build_graph_layers(edges_df, nodes)
    layer_nodes: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        layer_nodes[layers.get(node, 0)].append(node)

    width = 86 * mm
    height = 72 * mm
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.white, strokeColor=colors.HexColor("#e5e7eb")))

    box_w = 20 * mm
    box_h = 6.5 * mm
    margin_x = 6 * mm
    margin_y = 6 * mm
    max_layer = max(layer_nodes.keys(), default=0)
    x_gap = (width - 2 * margin_x - box_w) / max(max_layer, 1)

    node_pos: dict[str, tuple[float, float]] = {}
    for layer_idx in range(max_layer + 1):
        members = sorted(layer_nodes.get(layer_idx, []))
        if not members:
            continue
        y_gap = (height - 2 * margin_y - box_h) / max(len(members), 1)
        for i, node in enumerate(members):
            x = margin_x + layer_idx * x_gap
            y = height - margin_y - box_h - i * y_gap
            node_pos[node] = (x, y)

    max_freq = float(edges_df["transition_frequency"].max()) if not edges_df.empty else 1.0
    max_freq = max(max_freq, 1.0)
    for _, row in edges_df.iterrows():
        src = row["source_activity"]
        tgt = row["target_activity"]
        if src not in node_pos or tgt not in node_pos:
            continue
        sx, sy = node_pos[src]
        tx, ty = node_pos[tgt]
        x1 = sx + box_w
        y1 = sy + (box_h / 2)
        x2 = tx
        y2 = ty + (box_h / 2)
        freq = float(row["transition_frequency"])
        stroke_w = 0.4 + (freq / max_freq) * 1.8
        drawing.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#94a3b8"), strokeWidth=stroke_w))
        if freq > 0:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            drawing.add(String(mx + 1.2 * mm, my + 0.5 * mm, _fmt_int(freq), fontName="Helvetica", fontSize=5.8, fillColor=colors.HexColor("#475569")))

    for node, (x, y) in node_pos.items():
        drawing.add(Rect(x, y, box_w, box_h, fillColor=colors.HexColor("#eef2ff"), strokeColor=colors.HexColor("#c7d2fe"), strokeWidth=0.6))
        drawing.add(String(x + 1.1 * mm, y + 2.1 * mm, _truncate(node, 18), fontName="Helvetica", fontSize=6.1, fillColor=colors.HexColor("#1f2937")))

    drawing.add(String(2.5 * mm, height - 4.4 * mm, "DFG", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor("#111827")))
    return drawing


def _build_graph_layers(edges_df: pd.DataFrame, nodes: list[str]) -> dict[str, int]:
    indegree: dict[str, int] = {node: 0 for node in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for _, row in edges_df.iterrows():
        src = str(row["source_activity"])
        tgt = str(row["target_activity"])
        outgoing[src].append(tgt)
        indegree[tgt] = indegree.get(tgt, 0) + 1
        indegree.setdefault(src, 0)

    roots = [node for node in nodes if indegree.get(node, 0) == 0]
    if not roots:
        roots = nodes[:1]

    layers: dict[str, int] = {node: 0 for node in roots}
    changed = True
    iterations = 0
    while changed and iterations < 8:
        changed = False
        iterations += 1
        for src, targets in outgoing.items():
            src_layer = layers.get(src, 0)
            for tgt in targets:
                new_layer = src_layer + 1
                if layers.get(tgt, -1) < new_layer:
                    layers[tgt] = new_layer
                    changed = True
    for node in nodes:
        layers.setdefault(node, 0)
    return layers


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "..."


def _fmt_text(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    return text if text else "N/A"


def _fmt_int(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "N/A"
    return f"{int(round(number)):,}"


def _fmt_pct(value: Any, signed: bool = False) -> str:
    number = _to_float(value)
    if number is None:
        return "N/A"
    if abs(number) <= 1:
        number *= 100
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:.1f}%"


def _fmt_duration_hours(value: Any) -> str:
    hours = _to_float(value)
    if hours is None:
        return "N/A"
    if hours >= 1:
        return f"{hours:.1f} h"
    minutes = hours * 60
    return f"{minutes:.0f} min"


def _fmt_minutes(value: Any) -> str:
    minutes = _to_float(value)
    if minutes is None:
        return "N/A"
    if abs(minutes) >= 60:
        return f"{minutes / 60:.1f} h"
    return f"{minutes:.1f} min"


def _date_range(start: Any, end: Any) -> str:
    start_text = _fmt_text(start)
    end_text = _fmt_text(end)
    if start_text == "N/A" and end_text == "N/A":
        return "N/A"
    return f"{start_text} to {end_text}"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1]
            try:
                return float(cleaned) / 100.0
            except ValueError:
                return None
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_slow_case_ratio(payload: dict[str, Any]) -> float | None:
    ratio = _to_float(payload.get("slow_case_ratio"))
    if ratio is not None:
        return ratio

    slow_case_count = _to_float(payload.get("slow_case_count"))
    total_cases = _to_float(payload.get("overview_metrics", {}).get("cases"))
    if slow_case_count is None or total_cases is None or total_cases <= 0:
        return None
    return slow_case_count / total_cases


def short_dashboard_payload(
    *,
    overview_metrics: dict[str, Any],
    slow_case_summary: dict[str, Any],
    period_comparison: Any,
    activity_delay: Any,
    activity_comparison: pd.DataFrame | None = None,
    rework_comparison: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Build concise dashboard payload for report export."""
    period_note = None
    period_metrics: dict[str, Any] = {}
    if period_comparison is not None:
        avg_change = period_comparison.percent_diff.get("avg_duration_hours")
        avg_change_text = (
            f"{float(avg_change):+.1f}%"
            if avg_change is not None
            else "N/A"
        )
        period_note = f"{period_comparison.message} Average duration change: {avg_change_text}."
        period_metrics = {
            "recent": period_comparison.recent.to_dict() if period_comparison.recent else {},
            "previous": period_comparison.previous.to_dict() if period_comparison.previous else {},
            "percent_diff": period_comparison.percent_diff,
        }

    top_delayed_activity: dict[str, Any] | None = None
    top_delayed_activities: list[dict[str, Any]] = []
    if activity_delay is not None and getattr(activity_delay, "is_comparable", False):
        ranked = getattr(activity_delay, "ranked_table", pd.DataFrame())
        if not ranked.empty:
            row = ranked.iloc[0]
            top_delayed_activity = {
                "activity": str(row.get("activity", "N/A")),
                "absolute_increase_minutes": (
                    round(float(row.get("absolute_increase_minutes", 0.0)), 2)
                    if pd.notna(row.get("absolute_increase_minutes"))
                    else "N/A"
                ),
            }
            top_delayed_activities = ranked.head(5)[
                ["activity", "absolute_increase_minutes", "support_volume"]
            ].to_dict(orient="records")

    top_findings: list[str] = []
    avg_change = period_metrics.get("percent_diff", {}).get("avg_duration_hours")
    if avg_change is not None:
        top_findings.append(f"Average duration changed by {avg_change:.1f}% in the recent period.")
    top_findings.append(
        f"Slow-case ratio is {float(slow_case_summary.get('slow_case_ratio', 0.0)):.1%}."
    )
    if top_delayed_activity:
        top_findings.append(
            f"Top delay signal: {top_delayed_activity['activity']} "
            f"({top_delayed_activity['absolute_increase_minutes']} min)."
        )

    rework_signal = None
    if rework_comparison is not None and not rework_comparison.empty:
        slow_row = rework_comparison[rework_comparison["case_group"] == "slow"]
        non_row = rework_comparison[rework_comparison["case_group"] == "non_slow"]
        if not slow_row.empty and not non_row.empty:
            delta = float(slow_row.iloc[0]["rework_case_ratio"]) - float(non_row.iloc[0]["rework_case_ratio"])
            rework_signal = f"Slow vs non-slow rework ratio delta: {delta:+.1%}."

    executive_summary = " ".join(top_findings[:3]) if top_findings else None

    return {
        "overview_metrics": overview_metrics,
        "slow_case_ratio": float(slow_case_summary.get("slow_case_ratio", 0.0)),
        "slow_case_count": int(slow_case_summary.get("slow_case_count", 0)),
        "period_note": period_note,
        "period_metrics": period_metrics,
        "top_delayed_activity": top_delayed_activity,
        "top_delayed_activities": top_delayed_activities,
        "top_findings": top_findings[:3],
        "executive_summary": executive_summary,
        "rework_signal": rework_signal,
    }
