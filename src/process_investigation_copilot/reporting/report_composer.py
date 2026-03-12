"""Compose a unified report model from existing analysis payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.process_investigation_copilot.reporting.report_model import (
    InvestigationReport,
    ReportKeyValue,
    ReportMetadata,
    ReportSection,
    ReportTablePreview,
    ReportVisualReference,
)


def compose_investigation_report(
    *,
    dataset_label: str | None,
    validation_report: dict[str, Any] | None,
    dashboard_payload: dict[str, Any],
    process_view_payload: dict[str, Any] | None,
    investigation_payload: dict[str, Any] | None,
    generated_at: str | None = None,
) -> InvestigationReport:
    """Build a typed report object from existing export payloads."""

    metadata = ReportMetadata(
        title="Investigation Report",
        subtitle="Curated summary of deterministic process findings",
        dataset_label=dataset_label or "Unknown dataset",
        generated_at=generated_at or datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    sections: list[ReportSection] = [
        _compose_executive_summary(dashboard_payload, validation_report),
    ]

    data_section = _compose_data_readiness(validation_report, dashboard_payload)
    if data_section is not None:
        sections.append(data_section)

    performance_section = _compose_performance_summary(dashboard_payload)
    if performance_section is not None:
        sections.append(performance_section)

    delay_section = _compose_delay_drivers(dashboard_payload)
    if delay_section is not None:
        sections.append(delay_section)

    process_section = _compose_process_snapshot(process_view_payload)
    if process_section is not None:
        sections.append(process_section)

    investigation_section = _compose_investigation_answer(investigation_payload)
    if investigation_section is not None:
        sections.append(investigation_section)

    sections.append(
        _compose_limitations_section(
            validation_report=validation_report,
            investigation_payload=investigation_payload,
        )
    )

    next_steps_section = _compose_next_steps(
        dashboard_payload=dashboard_payload,
        process_view_payload=process_view_payload,
        validation_report=validation_report,
    )
    if next_steps_section is not None:
        sections.append(next_steps_section)

    appendix = _compose_appendix(investigation_payload)

    return InvestigationReport(metadata=metadata, sections=sections, appendix=appendix)


def _compose_executive_summary(
    dashboard_payload: dict[str, Any],
    validation_report: dict[str, Any] | None,
) -> ReportSection:
    top_findings = list(dashboard_payload.get("top_findings", []) or [])
    avg_change = dashboard_payload.get("period_metrics", {}).get("percent_diff", {}).get("avg_duration_hours")
    top_activity = dashboard_payload.get("top_delayed_activity") or {}
    limitation = _extract_primary_limitation(validation_report)

    sentences: list[str] = [_build_change_sentence(avg_change)]
    if top_activity:
        sentences.append(
            f"The strongest delay signal is {_fmt_text(top_activity.get('activity'))} "
            f"({_fmt_minutes(top_activity.get('absolute_increase_minutes'))})."
        )
    slow_ratio = _to_float(dashboard_payload.get("slow_case_ratio"))
    if slow_ratio is not None:
        sentences.append(f"Slow cases account for {_fmt_pct(slow_ratio)} of analyzed cases.")
    if limitation:
        sentences.append(f"Main limitation: {limitation}.")

    return ReportSection(
        key="executive_summary",
        title="Executive Summary",
        summary=" ".join(sentences),
        bullets=top_findings[:3],
    )


def _compose_data_readiness(
    validation_report: dict[str, Any] | None,
    dashboard_payload: dict[str, Any],
) -> ReportSection | None:
    if not validation_report:
        return None

    metrics = validation_report.get("metrics", {})
    overview = dashboard_payload.get("overview_metrics", {})
    if validation_report.get("is_valid", False):
        status = "Ready with limitations" if validation_report.get("warnings") else "Ready for analysis"
    else:
        status = "Action needed"

    section = ReportSection(
        key="data_readiness",
        title="Data Readiness",
        key_values=[
            ReportKeyValue("Dataset status", status),
            ReportKeyValue("Events", _fmt_int(overview.get("events", metrics.get("row_count")))),
            ReportKeyValue("Cases", _fmt_int(metrics.get("case_count"))),
            ReportKeyValue("Activities", _fmt_int(metrics.get("activity_count"))),
            ReportKeyValue("Timestamp parse success", _fmt_pct(metrics.get("timestamp_parse_success_rate"))),
            ReportKeyValue(
                "Parsed timestamp date range",
                _date_range(metrics.get("date_range_start"), metrics.get("date_range_end")),
            ),
        ],
    )

    section.bullets.extend(_normalize_messages(validation_report.get("blocking_errors", []))[:2])
    section.bullets.extend(_normalize_messages(validation_report.get("warnings", []))[:2])
    return section


def _compose_performance_summary(payload: dict[str, Any]) -> ReportSection | None:
    if not payload:
        return None

    period_metrics = payload.get("period_metrics", {})
    recent = period_metrics.get("recent", {})
    previous = period_metrics.get("previous", {})
    percent = period_metrics.get("percent_diff", {})

    return ReportSection(
        key="performance_summary",
        title="Performance Summary",
        summary=_build_change_sentence(percent.get("avg_duration_hours")),
        key_values=[
            ReportKeyValue("Recent average duration", _fmt_duration_hours(recent.get("avg_duration_hours"))),
            ReportKeyValue("Previous average duration", _fmt_duration_hours(previous.get("avg_duration_hours"))),
            ReportKeyValue("Average duration change", _fmt_pct(percent.get("avg_duration_hours"), signed=True)),
            ReportKeyValue("Recent median duration", _fmt_duration_hours(recent.get("median_duration_hours"))),
            ReportKeyValue("Median duration change", _fmt_pct(percent.get("median_duration_hours"), signed=True)),
            ReportKeyValue("Recent P90 duration", _fmt_duration_hours(recent.get("p90_duration_hours"))),
            ReportKeyValue("P90 duration change", _fmt_pct(percent.get("p90_duration_hours"), signed=True)),
            ReportKeyValue("Slow-case ratio", _fmt_pct(_resolve_slow_case_ratio(payload))),
            ReportKeyValue("Slow-case count", _fmt_int(payload.get("slow_case_count"))),
        ],
        paragraphs=[_fmt_text(payload.get("period_note"))] if payload.get("period_note") else [],
    )


def _compose_delay_drivers(payload: dict[str, Any]) -> ReportSection | None:
    top_delayed = list(payload.get("top_delayed_activities", []) or [])
    rework_signal = payload.get("rework_signal")
    if not top_delayed and not rework_signal:
        return None

    section = ReportSection(
        key="delay_drivers",
        title="Delay Drivers",
    )

    for row in top_delayed[:3]:
        section.bullets.append(
            f"{_fmt_text(row.get('activity'))}: {_fmt_minutes(row.get('absolute_increase_minutes'))} increase "
            f"(support {_fmt_int(row.get('support_volume'))})"
        )

    if top_delayed:
        section.tables.append(
            ReportTablePreview(
                title="Top delayed activities",
                columns=["Activity", "Delay change", "Support"],
                rows=[
                    [
                        _fmt_text(row.get("activity")),
                        _fmt_minutes(row.get("absolute_increase_minutes")),
                        _fmt_int(row.get("support_volume")),
                    ]
                    for row in top_delayed[:5]
                ],
            )
        )

    if rework_signal:
        section.paragraphs.append(f"Rework signal: {_fmt_text(rework_signal)}")
    return section


def _compose_process_snapshot(payload: dict[str, Any] | None) -> ReportSection | None:
    if not payload:
        return None

    section = ReportSection(
        key="process_snapshot",
        title="Process Snapshot",
        key_values=[
            ReportKeyValue("View", _fmt_text(payload.get("mode"))),
            ReportKeyValue("Subset", _fmt_text(payload.get("subset"))),
            ReportKeyValue("Cases", _fmt_int(payload.get("case_count"))),
            ReportKeyValue("Events", _fmt_int(payload.get("event_count"))),
            ReportKeyValue("Transitions", _fmt_int(payload.get("edge_count"))),
        ],
        visuals=[
            ReportVisualReference(
                title="Top 5 variant process snapshot",
                visual_type="process_snapshot",
                caption="Curated static process-flow visual rendered separately in the PDF.",
            )
        ],
    )

    insights = payload.get("insights", {})
    for key, label in {
        "most_frequent": "Most frequent transition",
        "slowest_average": "Slowest average transition",
        "bottleneck_candidate": "Bottleneck candidate",
    }.items():
        insight = insights.get(key)
        if insight:
            section.bullets.append(f"{label}: {_fmt_text(insight.get('transition'))} ({_fmt_text(insight.get('value'))})")
    return section


def _compose_investigation_answer(payload: dict[str, Any] | None) -> ReportSection | None:
    if not payload:
        return None

    answer_blocks = list(payload.get("answer_blocks", []) or [])
    answer_payload = payload.get("answer_payload") or {}
    top_factors = list(payload.get("top_suspicious_factors", []) or [])
    limitations = list(payload.get("limitations", []) or [])
    follow_ups = list(payload.get("follow_up_questions", []) or [])

    section = ReportSection(
        key="investigation_answer",
        title="Investigation Answer",
        summary=_fmt_text(answer_payload.get("directAnswer")) if answer_payload else None,
    )

    if answer_payload:
        section.paragraphs.extend(_section_lines("Observations", answer_payload.get("observations", [])))
        section.paragraphs.extend(_section_lines("Evidence", answer_payload.get("evidence", [])))
        section.paragraphs.extend(_section_lines("Interpretation", answer_payload.get("interpretations", [])))
        if answer_payload.get("limitations"):
            section.paragraphs.append("Limitations:")
            section.bullets.extend(_fmt_text(item) for item in answer_payload.get("limitations", [])[:4])
        if answer_payload.get("followUpQuestions"):
            section.paragraphs.append("Suggested next questions:")
            section.bullets.extend(_fmt_text(item) for item in answer_payload.get("followUpQuestions", [])[:3])
    else:
        for block in answer_blocks:
            section.paragraphs.append(f"{_fmt_text(block.get('title'))}: {_fmt_text(block.get('text'))}")

    for factor in top_factors[:3]:
        title = _fmt_text(factor.get("title"))
        evidence = _fmt_text(factor.get("evidence"))
        if title != "N/A":
            section.bullets.append(f"{title}: {evidence}")

    for limitation in limitations[:4]:
        if _fmt_text(limitation) not in section.bullets:
            section.bullets.append(_fmt_text(limitation))
    for follow_up in follow_ups[:3]:
        if _fmt_text(follow_up) not in section.bullets:
            section.bullets.append(_fmt_text(follow_up))

    if not any([section.summary, section.bullets, section.paragraphs]):
        return None
    return section


def _compose_limitations_section(
    *,
    validation_report: dict[str, Any] | None,
    investigation_payload: dict[str, Any] | None,
) -> ReportSection:
    section = ReportSection(
        key="limitations_uncertainty",
        title="Limitations / Uncertainty",
    )

    if investigation_payload:
        answer_payload = investigation_payload.get("answer_payload") or {}
        section.bullets.extend(_fmt_text(item) for item in list(answer_payload.get("limitations", []) or [])[:4])
        section.bullets.extend(_fmt_text(item) for item in list(investigation_payload.get("limitations", []) or [])[:4])

    if validation_report:
        section.bullets.extend(_normalize_messages(validation_report.get("blocking_errors", []))[:2])
        section.bullets.extend(_normalize_messages(validation_report.get("warnings", []))[:2])

    section.bullets = _dedupe_texts([item for item in section.bullets if item != "N/A"])
    if not any("causal" in item.lower() or "causality" in item.lower() for item in section.bullets):
        section.bullets.append("These findings show association-based investigation signals and should not be treated as proof of causality.")
    return section


def _compose_next_steps(
    *,
    dashboard_payload: dict[str, Any],
    process_view_payload: dict[str, Any] | None,
    validation_report: dict[str, Any] | None,
) -> ReportSection | None:
    section = ReportSection(key="next_steps", title="Next Steps")

    top_delayed = list(dashboard_payload.get("top_delayed_activities", []) or [])
    if top_delayed:
        top_names = ", ".join(_fmt_text(row.get("activity")) for row in top_delayed[:2])
        section.bullets.append(f"Investigate the highest-delay activities first ({top_names}).")

    if process_view_payload and process_view_payload.get("insights", {}).get("bottleneck_candidate"):
        section.bullets.append("Review bottleneck candidate transitions in Process View before operational changes.")

    limitation = _extract_primary_limitation(validation_report)
    if limitation:
        section.bullets.append("Validate timestamp and data quality limitations before final business decisions.")

    if not section.bullets:
        section.bullets.extend(
            [
                "Review the current findings and prioritize one measurable process improvement experiment.",
                "Re-run the report after the next period to confirm whether key delays are improving.",
            ]
        )
    return section


def _compose_appendix(investigation_payload: dict[str, Any] | None) -> list[ReportSection]:
    if not investigation_payload:
        return []

    trace = investigation_payload.get("trace") or {}
    if not trace:
        return []

    appendix = ReportSection(
        key="appendix_trace",
        title="Appendix: Trace",
        bullets=[
            f"Question type: {_fmt_text(trace.get('question_type'))}",
            f"Time window: {_fmt_text(trace.get('selected_time_window'))}",
            f"Subset: {_fmt_text(trace.get('selected_subset'))}",
            f"Confidence label: {_fmt_text(trace.get('confidence_label'))}",
        ],
    )
    appendix.bullets.extend(
        f"Analysis: {_fmt_text(item)}" for item in list(trace.get("analysis_functions_executed", []) or [])[:5]
    )
    return [appendix]


def _section_lines(label: str, items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return []
    lines = [f"{label}:"]
    for item in items[:4]:
        title = _fmt_text(item.get("title"))
        text = _fmt_text(item.get("text"))
        lines.append(f"- {title}: {text}")
    return lines


def _build_change_sentence(avg_delta: Any) -> str:
    delta = _to_float(avg_delta)
    if delta is None:
        return "The available comparison does not support a strong overall duration conclusion."
    if delta > 0:
        return f"Processing time increased by {_fmt_pct(delta)} versus the previous period."
    if delta < 0:
        return f"Processing time decreased by {_fmt_pct(abs(delta))} versus the previous period."
    return "Processing time remained broadly stable versus the previous period."


def _extract_primary_limitation(validation_report: dict[str, Any] | None) -> str | None:
    if not validation_report:
        return None
    messages = _normalize_messages(validation_report.get("blocking_errors", []))
    messages.extend(_normalize_messages(validation_report.get("warnings", [])))
    return messages[0] if messages else None


def _normalize_messages(items: list[Any]) -> list[str]:
    messages: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            text = item.get("message")
        else:
            text = str(item)
        text = _fmt_text(text)
        if text != "N/A":
            messages.append(text)
    return messages


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


def _date_range(start: Any, end: Any) -> str:
    start_text = _fmt_text(start)
    end_text = _fmt_text(end)
    if start_text == "N/A" and end_text == "N/A":
        return "N/A"
    return f"{start_text} to {end_text}"


def _resolve_slow_case_ratio(payload: dict[str, Any]) -> float | None:
    ratio = _to_float(payload.get("slow_case_ratio"))
    if ratio is not None:
        return ratio

    slow_case_count = _to_float(payload.get("slow_case_count"))
    total_cases = _to_float(payload.get("overview_metrics", {}).get("cases"))
    if slow_case_count is None or total_cases is None or total_cases <= 0:
        return None
    return slow_case_count / total_cases


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
    return f"{hours * 60:.0f} min"


def _fmt_minutes(value: Any) -> str:
    minutes = _to_float(value)
    if minutes is None:
        return "N/A"
    if abs(minutes) >= 60:
        return f"{minutes / 60:.1f} h"
    return f"{minutes:.1f} min"


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
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
