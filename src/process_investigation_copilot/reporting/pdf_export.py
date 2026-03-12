"""PDF export utilities for combined process investigation reports."""

from __future__ import annotations

import re
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
    _append_data_readiness(data_section, styles, validation_report, dashboard_payload)
    sections.append(data_section)

    performance_section: list[Any] = []
    _append_performance_summary(performance_section, styles, dashboard_payload)
    sections.append(performance_section)

    delay_section: list[Any] = []
    _append_delay_drivers(delay_section, styles, dashboard_payload)
    sections.append(delay_section)

    process_section: list[Any] = []
    _append_process_view_summary(process_section, styles, process_view_payload)
    sections.append(process_section)

    investigation_section: list[Any] = []
    _append_investigation_summary(investigation_section, styles, investigation_payload)
    sections.append(investigation_section)

    limitations_section: list[Any] = []
    _append_limitations_uncertainty(
        limitations_section,
        styles,
        validation_report=validation_report,
        investigation_payload=investigation_payload,
    )
    sections.append(limitations_section)

    next_steps_section: list[Any] = []
    _append_next_steps(
        next_steps_section,
        styles,
        dashboard_payload=dashboard_payload,
        process_view_payload=process_view_payload,
        validation_report=validation_report,
    )
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
    story.append(KeepTogether([Paragraph("Data Readiness", styles["SectionTitle"])]))
    if not validation_report:
        story.append(Paragraph("Validation details were not available at export time.", styles["Body"]))
        return True

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
    story.append(KeepTogether([Paragraph("Performance Summary", styles["SectionTitle"])]))
    if not payload:
        story.append(Paragraph("Performance comparison was not available at export time.", styles["Body"]))
        return True

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

    story.append(KeepTogether([Paragraph("Delay Drivers", styles["SectionTitle"])]))
    if not top_delayed and not rework_note:
        story.append(Paragraph("No strong delay-driver signal was available in the current export window.", styles["Body"]))
        return True

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
    story.append(KeepTogether([Paragraph("Process Snapshot", styles["SectionTitle"])]))
    if not payload:
        story.append(Paragraph("Process snapshot data was not available at export time.", styles["Body"]))
        return True
    dfg_edges = payload.get("dfg_edges", [])
    top_edges = payload.get("top_edges", [])
    if dfg_edges:
        story.append(Paragraph("Top 5 variant process snapshot", styles["SubsectionTitle"]))
        story.append(_build_report_process_snapshot(payload))
    elif top_edges:
        story.append(Paragraph("Transition intensity snapshot", styles["SubsectionTitle"]))
        story.append(_build_transition_snapshot_chart(top_edges))
    else:
        story.append(_compact_process_meta_table(payload))

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
        lines.append(f"- {label}: {_format_transition_insight(label, insight)}")

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
    story.append(KeepTogether([Paragraph("Investigation Answer", styles["SectionTitle"])]))
    if not payload:
        story.append(Paragraph("A composed investigation answer was not available at export time.", styles["Body"]))
        return True

    answer_payload = payload.get("answer_payload") or {}
    question_type = _fmt_text(payload.get("question_type"))
    support_text = _investigation_support_text(payload, answer_payload)
    story.append(Paragraph(f"Question category: {question_type} | Evidence status: {support_text}", styles["Body"]))

    direct_answer = _fmt_text(answer_payload.get("directAnswer"))
    if direct_answer != "N/A":
        story.append(Spacer(1, 5))
        story.append(Paragraph("Direct answer", styles["SubsectionTitle"]))
        story.append(Paragraph(direct_answer, styles["Body"]))
    else:
        answer_blocks = list(payload.get("answer_blocks", []) or [])
        if answer_blocks:
            first_block = answer_blocks[0]
            story.append(Spacer(1, 5))
            story.append(Paragraph("Direct answer", styles["SubsectionTitle"]))
            story.append(Paragraph(_fmt_text(first_block.get("text", "N/A")), styles["Body"]))

    observations = list(answer_payload.get("observations", []) or [])
    if observations:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Key observations", styles["SubsectionTitle"]))
        for item in observations[:4]:
            story.append(Paragraph(f"- {_section_sentence(item)}", styles["ReportBullet"]))

    evidence_items = list(answer_payload.get("evidence", []) or [])
    if evidence_items:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Supporting evidence", styles["SubsectionTitle"]))
        for item in evidence_items[:4]:
            story.append(Paragraph(f"- {_section_sentence(item)}", styles["ReportBullet"]))

    interpretations = list(answer_payload.get("interpretations", []) or [])
    if interpretations:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Interpretation", styles["SubsectionTitle"]))
        for item in interpretations[:2]:
            story.append(Paragraph(_fmt_text(item.get("text")), styles["Body"]))

    if not any([direct_answer != "N/A", observations, evidence_items, interpretations]):
        story.append(Paragraph("No composed investigation explanation was available for this export.", styles["Body"]))

    return True


def _append_limitations_uncertainty(
    story: list[Any],
    styles: StyleSheet1,
    *,
    validation_report: dict[str, Any] | None,
    investigation_payload: dict[str, Any] | None,
) -> bool:
    story.append(KeepTogether([Paragraph("Limitations / Uncertainty", styles["SectionTitle"])]))

    bullets: list[str] = []
    if investigation_payload:
        answer_payload = investigation_payload.get("answer_payload") or {}
        bullets.extend(_fmt_text(item) for item in list(answer_payload.get("limitations", []) or [])[:4])
        bullets.extend(_fmt_text(item) for item in list(investigation_payload.get("limitations", []) or [])[:4])

    if validation_report:
        bullets.extend(_normalize_messages(validation_report.get("blocking_errors", []))[:2])
        bullets.extend(_normalize_messages(validation_report.get("warnings", []))[:2])

    bullets = _dedupe_texts([item for item in bullets if item and item != "N/A"])
    if not any("causal" in item.lower() or "causality" in item.lower() for item in bullets):
        bullets.append("These findings show association-based investigation signals and should not be treated as proof of causality.")

    for bullet in bullets[:3]:
        story.append(Paragraph(f"- {bullet}", styles["ReportBullet"]))

    if not bullets:
        story.append(Paragraph("- No major limitations were recorded at export time.", styles["ReportBullet"]))
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
        ["View", _fmt_text(payload.get("mode"))],
        ["Subset", _fmt_text(payload.get("subset"))],
        ["Cases", _fmt_int(payload.get("case_count"))],
        ["Events", _fmt_int(payload.get("event_count"))],
        ["Transitions", _fmt_int(payload.get("edge_count"))],
    ]
    table = Table(rows, colWidths=[18 * mm, 34 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
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


def _build_report_process_snapshot(payload: dict[str, Any]) -> Drawing:
    dfg_edges = payload.get("dfg_edges", []) or []
    width = 172 * mm
    height = 84 * mm
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.white, strokeColor=colors.HexColor("#e5e7eb")))

    snapshot = _build_report_process_snapshot_data(dfg_edges)
    if not snapshot["path"]:
        drawing.add(
            String(
                8 * mm,
                height / 2,
                "No simplified process snapshot was available.",
                fontName="Helvetica",
                fontSize=8,
                fillColor=colors.HexColor("#6b7280"),
            )
        )
        return drawing

    meta_x = 6 * mm
    meta_y = height - 34 * mm
    meta_w = 34 * mm
    meta_h = 24 * mm
    drawing.add(
        Rect(
            meta_x,
            meta_y,
            meta_w,
            meta_h,
            fillColor=colors.HexColor("#f8fafc"),
            strokeColor=colors.HexColor("#d1d5db"),
            strokeWidth=0.7,
        )
    )
    _add_inset_meta_table(drawing, payload, x=meta_x, y=meta_y, width=meta_w, height=meta_h)

    drawing.add(
        String(
            6 * mm,
            height - 5 * mm,
            "Top 5 variant process snapshot",
            fontName="Helvetica-Bold",
            fontSize=7.2,
            fillColor=colors.HexColor("#111827"),
        )
    )

    path = snapshot["path"]
    branches = snapshot["branches"]
    node_count = len(path)
    box_w = 24 * mm
    box_h = 9.5 * mm
    arrow_gap = 5 * mm
    left = 46 * mm
    right = 7 * mm
    available_w = width - left - right
    if node_count > 1:
        total_boxes = node_count * box_w
        total_arrows = (node_count - 1) * arrow_gap
        start_x = left + max((available_w - total_boxes - total_arrows) / 2, 0)
    else:
        start_x = width / 2 - box_w / 2
    main_y = height * 0.54

    node_positions: dict[str, tuple[float, float]] = {}
    for idx, node in enumerate(path):
        x = start_x + idx * (box_w + arrow_gap)
        y = main_y
        node_positions[node] = (x, y)
        _add_snapshot_node(
            drawing,
            x=x,
            y=y,
            width=box_w,
            height=box_h,
            label=_shorten_report_label(node, 22),
            fill="#eef2ff",
            stroke="#c7d2fe",
        )

        if idx < node_count - 1:
            next_x = start_x + (idx + 1) * (box_w + arrow_gap)
            _add_arrow(
                drawing,
                x1=x + box_w,
                y1=y + box_h / 2,
                x2=next_x,
                y2=y + box_h / 2,
                stroke="#64748b",
                width=1.2,
            )

    for edge in snapshot["path_edges"][:3]:
        src = edge["source_activity"]
        tgt = edge["target_activity"]
        if src not in node_positions or tgt not in node_positions:
            continue
        sx, sy = node_positions[src]
        tx, ty = node_positions[tgt]
        label_x = (sx + box_w + tx) / 2
        label_y = sy + box_h / 2 + 3.2 * mm
        drawing.add(
            String(
                label_x - 2 * mm,
                label_y,
                _fmt_int(edge.get("transition_frequency")),
                fontName="Helvetica-Bold",
                fontSize=6.1,
                fillColor=colors.HexColor("#475569"),
            )
        )

    branch_slots = [height * 0.77, height * 0.23]
    for idx, branch in enumerate(branches[:2]):
        anchor = branch["anchor"]
        target = branch["target"]
        if anchor not in node_positions:
            continue
        anchor_x, anchor_y = node_positions[anchor]
        branch_y = branch_slots[idx]
        branch_x = min(anchor_x + box_w + 10 * mm, width - right - box_w)
        _add_arrow(
            drawing,
            x1=anchor_x + box_w / 2,
            y1=anchor_y + box_h / 2,
            x2=branch_x,
            y2=branch_y + box_h / 2,
            stroke="#94a3b8",
            width=0.9,
        )
        _add_snapshot_node(
            drawing,
            x=branch_x,
            y=branch_y,
            width=box_w,
            height=box_h,
            label=_shorten_report_label(target, 22),
            fill="#f8fafc",
            stroke="#cbd5e1",
        )
        label = branch.get("label")
        if label:
            drawing.add(
                String(
                    branch_x,
                    branch_y - 3 * mm,
                    _truncate(label, 20),
                    fontName="Helvetica",
                    fontSize=5.8,
                    fillColor=colors.HexColor("#64748b"),
                )
            )

    if snapshot["summary_note"]:
        drawing.add(
            String(
                46 * mm,
                6 * mm,
                _truncate(snapshot["summary_note"], 90),
                fontName="Helvetica",
                fontSize=6.2,
                fillColor=colors.HexColor("#6b7280"),
            )
        )

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


def _build_report_process_snapshot_data(dfg_edges: list[dict[str, Any]]) -> dict[str, Any]:
    edges_df = pd.DataFrame(dfg_edges)
    required = {"source_activity", "target_activity", "transition_frequency", "avg_transition_minutes"}
    if edges_df.empty or not required.issubset(edges_df.columns):
        return {"path": [], "path_edges": [], "branches": [], "summary_note": ""}

    edges_df = edges_df.copy()
    edges_df["source_activity"] = edges_df["source_activity"].astype(str)
    edges_df["target_activity"] = edges_df["target_activity"].astype(str)
    edges_df["transition_frequency"] = pd.to_numeric(edges_df["transition_frequency"], errors="coerce").fillna(0.0)
    edges_df["avg_transition_minutes"] = pd.to_numeric(edges_df["avg_transition_minutes"], errors="coerce").fillna(0.0)
    edges_df = edges_df.sort_values(["transition_frequency", "avg_transition_minutes"], ascending=[False, False])

    indegree: dict[str, int] = defaultdict(int)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in edges_df.to_dict(orient="records"):
        src = row["source_activity"]
        tgt = row["target_activity"]
        outgoing[src].append(row)
        indegree[tgt] += 1
        indegree.setdefault(src, 0)

    roots = [node for node in outgoing if indegree.get(node, 0) == 0]
    if roots:
        root = max(roots, key=lambda node: sum(edge["transition_frequency"] for edge in outgoing.get(node, [])))
    else:
        top_edge = edges_df.iloc[0].to_dict()
        root = str(top_edge["source_activity"])

    path = [root]
    path_edges: list[dict[str, Any]] = []
    branches: list[dict[str, Any]] = []
    visited = {root}
    current = root

    while len(path) < 5:
        candidates = [edge for edge in outgoing.get(current, []) if edge["target_activity"] not in visited]
        if not candidates:
            break
        main_edge = candidates[0]
        path_edges.append(main_edge)
        current = str(main_edge["target_activity"])
        path.append(current)
        visited.add(current)

        alt_candidates = [edge for edge in candidates[1:] if edge["target_activity"] not in visited]
        if alt_candidates and len(branches) < 2:
            alt = alt_candidates[0]
            branches.append(
                {
                    "anchor": main_edge["source_activity"],
                    "target": alt["target_activity"],
                    "label": f"{_fmt_int(alt['transition_frequency'])} cases",
                }
            )

    summary_note = ""
    if path_edges:
        strongest = path_edges[0]
        summary_note = (
            f"This snapshot uses the top 5 variants and follows the highest-volume path through that subset."
        )
        if branches:
            summary_note += " A small number of side branches are shown for context."

    return {
        "path": path,
        "path_edges": path_edges,
        "branches": branches,
        "summary_note": summary_note,
    }


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "..."


def _shorten_activity_label(value: str, limit: int) -> str:
    text = str(value).strip()
    if len(text) <= limit:
        return text

    separators = [" -> ", ">", "|", "/"]
    for separator in separators:
        if separator in text:
            parts = [part.strip() for part in text.split(separator) if part.strip()]
            if len(parts) >= 2:
                candidate = f"{parts[0][:8]} ... {parts[-1][:8]}"
                if len(candidate) <= limit:
                    return candidate

    words = text.split()
    if len(words) >= 2:
        candidate = " ".join(word[: min(len(word), 7)] for word in words[:2])
        if len(candidate) <= limit:
            return candidate

    return _truncate(text, limit)


def _shorten_report_label(value: str, limit: int) -> str:
    text = str(value).strip().replace("_", " ")
    if len(text) <= limit:
        return text

    words = [word for word in re.split(r"[\s_/>\-|]+", text) if word]
    if len(words) >= 2:
        candidate = f"{words[0][:12]} {words[-1][:8]}"
        if len(candidate) <= limit:
            return candidate
    if len(words) >= 3:
        candidate = f"{words[0][:8]} {words[1][:7]} {words[2][:7]}"
        if len(candidate) <= limit:
            return candidate
    if len(words) >= 2:
        candidate = f"{words[0][:10]} {words[1][:8]}"
        if len(candidate) <= limit:
            return candidate

    return _truncate(text, limit)


def _section_sentence(item: dict[str, Any]) -> str:
    title = _fmt_text(item.get("title"))
    text = _fmt_text(item.get("text"))
    if title == "N/A":
        return text
    return f"{title}: {text}"


def _investigation_support_text(payload: dict[str, Any], answer_payload: dict[str, Any]) -> str:
    status = _fmt_text(answer_payload.get("answerStatus"))
    mapping = {
        "supported": "Supported",
        "mixed": "Mixed evidence",
        "premise_not_supported": "Premise not supported",
        "insufficient": "Insufficient evidence",
    }
    if status in mapping:
        return mapping[status]
    return "Supported" if payload.get("is_supported") else "Partially supported"


def _format_transition_insight(label: str, insight: dict[str, Any]) -> str:
    transition = _fmt_text(insight.get("transition"))
    value = _fmt_text(insight.get("value"))
    if label == "Bottleneck candidate":
        qualitative = _qualitative_bottleneck_label(value)
        return f"{transition} ({qualitative})"
    return f"{transition} ({value})"


def _qualitative_bottleneck_label(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "Candidate"
    if number >= 500:
        return "High bottleneck signal"
    if number >= 150:
        return "Medium bottleneck signal"
    return "Low bottleneck signal"


def _dedupe_texts(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item.strip())
    return result


def _add_snapshot_node(
    drawing: Drawing,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    label: str,
    fill: str,
    stroke: str,
) -> None:
    drawing.add(
        Rect(
            x,
            y,
            width,
            height,
            fillColor=colors.HexColor(fill),
            strokeColor=colors.HexColor(stroke),
            strokeWidth=0.8,
        )
    )
    drawing.add(
        String(
            x + 1.5 * mm,
            y + 3.0 * mm,
            label,
            fontName="Helvetica",
            fontSize=6.4,
            fillColor=colors.HexColor("#1f2937"),
        )
    )


def _add_arrow(
    drawing: Drawing,
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    stroke: str,
    width: float,
) -> None:
    drawing.add(
        Line(
            x1,
            y1,
            x2,
            y2,
            strokeColor=colors.HexColor(stroke),
            strokeWidth=width,
        )
    )
    head = 1.3 * mm
    drawing.add(
        Line(
            x2,
            y2,
            x2 - head,
            y2 + head / 2,
            strokeColor=colors.HexColor(stroke),
            strokeWidth=width,
        )
    )
    drawing.add(
        Line(
            x2,
            y2,
            x2 - head,
            y2 - head / 2,
            strokeColor=colors.HexColor(stroke),
            strokeWidth=width,
        )
    )


def _add_inset_meta_table(
    drawing: Drawing,
    payload: dict[str, Any],
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    rows = [
        ("Subset", _fmt_text(payload.get("subset"))),
        ("Cases", _fmt_int(payload.get("case_count"))),
        ("Events", _fmt_int(payload.get("event_count"))),
        ("Edges", _fmt_int(payload.get("edge_count"))),
    ]
    drawing.add(
        String(
            x + 1.5 * mm,
            y + height - 3.8 * mm,
            "Snapshot context",
            fontName="Helvetica-Bold",
            fontSize=6.6,
            fillColor=colors.HexColor("#111827"),
        )
    )
    row_y = y + height - 8.5 * mm
    for label, value in rows:
        drawing.add(
            String(
                x + 1.5 * mm,
                row_y,
                label,
                fontName="Helvetica-Bold",
                fontSize=5.8,
                fillColor=colors.HexColor("#475569"),
            )
        )
        drawing.add(
            String(
                x + 12.5 * mm,
                row_y,
                _truncate(value, 16),
                fontName="Helvetica",
                fontSize=5.8,
                fillColor=colors.HexColor("#1f2937"),
            )
        )
        row_y -= 4.6 * mm


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
