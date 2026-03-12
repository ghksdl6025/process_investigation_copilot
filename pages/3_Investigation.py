"""Question-driven investigation page for deterministic analysis outputs."""

import re

import streamlit as st

from src.process_investigation_copilot.analysis.investigation_panel import (
    QUESTION_TEMPLATES,
    InvestigationPanelResult,
    build_core_scenario_result,
    build_investigation_panel_result,
)
from src.process_investigation_copilot.ui import (
    apply_global_ui,
    ensure_active_dataset_restored,
    render_sidebar_branding,
)

apply_global_ui()
render_sidebar_branding()
ensure_active_dataset_restored()


def _humanize_label(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _clean_wrapped_numbers(text: str) -> str:
    cleaned = re.sub(r"np\.float\d+\(([^)]+)\)", r"\1", text)
    cleaned = re.sub(r"np\.int\d+\(([^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"float\d+\(([^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"int\d+\(([^)]+)\)", r"\1", cleaned)
    return cleaned


def _round_long_decimals(text: str) -> str:
    def _round_match(match: re.Match[str]) -> str:
        value = float(match.group(0))
        return f"{value:.2f}"

    return re.sub(r"-?\d+\.\d{3,}", _round_match, text)


def _clean_answer_text(text: str) -> str:
    cleaned = _clean_wrapped_numbers(text)
    cleaned = _round_long_decimals(cleaned)
    cleaned = cleaned.replace(" | ", "\n\n")
    cleaned = cleaned.replace("None", "N/A")
    return cleaned


def _friendly_confidence(label: str) -> str:
    mapping = {
        "high": "Strong signal",
        "medium": "Moderate signal",
        "low": "Early signal",
    }
    return mapping.get(str(label).lower(), _humanize_label(str(label)))


def _friendly_answer_status(value: str) -> str:
    mapping = {
        "supported": "Premise supported",
        "mixed": "Mixed evidence",
        "premise_not_supported": "Premise not supported",
        "insufficient": "Insufficient evidence",
    }
    return mapping.get(str(value).lower(), _humanize_label(str(value)))


def _friendly_overall_change_state(value: str) -> str:
    mapping = {
        "increase": "Increase",
        "decrease": "Decrease",
        "no_meaningful_overall_change": "No meaningful overall change",
        "insufficient_evidence": "Insufficient evidence",
    }
    return mapping.get(str(value).lower(), _humanize_label(str(value)))


def _friendly_trace_label(value: str) -> str:
    mapping = {
        "compare_period_case_performance": "Recent vs previous period comparison",
        "compare_activity_delay_between_periods": "Activity-level delay analysis",
        "build_slow_case_comparison": "Slow vs non-slow subset comparison",
        "build_investigation_summary_payload": "Suspicious factor summary",
        "build_grounded_explanation": "Grounded explanation assembly",
        "build_directly_follows_graph": "Process transition analysis",
        "build_transition_insights": "Transition insight summary",
        "avg_duration_hours": "Average case duration",
        "median_duration_hours": "Median case duration",
        "p90_duration_hours": "P90 case duration",
        "avg_event_count": "Average event count",
        "activity_delay_proxy_minutes": "Activity delay proxy",
        "rework_case_ratio": "Rework rate",
        "variant_distribution": "Variant distribution",
        "case_count": "Case count",
        "activity_event_share_delta": "Activity share difference",
        "variant_case_count": "Variant case count",
        "transition_frequency": "Transition frequency",
        "avg_transition_minutes": "Average transition time",
        "bottleneck_score_heuristic": "Bottleneck heuristic score",
        "all_analyzed_cases": "All analyzed cases",
        "slow_vs_non_slow": "Slow vs non-slow cases",
        "all": "All cases",
    }
    normalized = str(value).strip()
    return mapping.get(normalized, _humanize_label(normalized))


def _render_trace_summary(result: InvestigationPanelResult) -> None:
    payload = result.answer_payload
    if payload is None:
        st.write("No trace summary is available.")
        return

    sections = [
        ("Analyses used", [_friendly_trace_label(item) for item in payload.trace.analysesUsed]),
        ("Subsets used", [_friendly_trace_label(item) for item in payload.trace.subsetsUsed]),
        ("Metrics used", [_friendly_trace_label(item) for item in payload.trace.metricsUsed]),
    ]
    populated = [(title, items) for title, items in sections if items]
    if not populated:
        st.write("No trace summary is available.")
        return

    columns = st.columns(len(populated))
    for index, (title, items) in enumerate(populated):
        with columns[index]:
            st.markdown(f"**{title}**")
            for item in items:
                st.write(f"- {item}")


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:,.2f}{suffix}"


def _extract_summary_signals(result: InvestigationPanelResult) -> list[tuple[str, str, str]]:
    signals: list[tuple[str, str, str]] = []

    period_table = result.evidence_tables.get("Period KPI Comparison")
    if period_table is not None and not period_table.empty:
        recent_row = period_table[period_table["period"] == "recent"]
        previous_row = period_table[period_table["period"] == "previous"]
        if not recent_row.empty and not previous_row.empty:
            recent_avg = _safe_float(recent_row.iloc[0].get("avg_duration_hours"))
            previous_avg = _safe_float(previous_row.iloc[0].get("avg_duration_hours"))
            if recent_avg is not None and previous_avg is not None and previous_avg != 0:
                pct = ((recent_avg - previous_avg) / previous_avg) * 100.0
                signals.append(
                    (
                        "Processing Time Change",
                        f"{pct:+.1f}%",
                        "Recent vs previous average case duration",
                    )
                )

    activity_table = result.evidence_tables.get("Activity Delay Comparison")
    if activity_table is not None and not activity_table.empty:
        row = activity_table.iloc[0]
        activity_name = str(row.get("activity", "N/A"))
        increase = _safe_float(row.get("absolute_increase_minutes"))
        signals.append(
            (
                "Most Delayed Activity",
                activity_name,
                f"Avg proxy delay change: {_format_number(increase, ' min')}",
            )
        )

    rework_table = result.evidence_tables.get("Slow vs Non-slow Rework Comparison")
    if rework_table is not None and not rework_table.empty:
        slow = rework_table[rework_table["case_group"] == "slow"]
        non_slow = rework_table[rework_table["case_group"] == "non_slow"]
        if not slow.empty and not non_slow.empty:
            slow_ratio = _safe_float(slow.iloc[0].get("rework_case_ratio"))
            non_ratio = _safe_float(non_slow.iloc[0].get("rework_case_ratio"))
            if slow_ratio is not None and non_ratio is not None:
                delta = (slow_ratio - non_ratio) * 100.0
                signals.append(
                    (
                        "Rework Difference",
                        f"{delta:+.1f} pp",
                        "Slow-case rework ratio minus non-slow ratio",
                    )
                )

    return signals[:3]


def _friendly_steps(trace: dict[str, object]) -> list[str]:
    question_type = _humanize_label(str(trace.get("question_type", "N/A")))
    time_window = _clean_answer_text(str(trace.get("selected_time_window", "N/A")))
    subset = _clean_answer_text(str(trace.get("selected_subset", "N/A")))
    evidence_items = trace.get("evidence_used", [])
    evidence_count = len(evidence_items) if isinstance(evidence_items, list) else 0
    return [
        f"Interpreted your question as: {question_type}.",
        f"Selected analysis window: {time_window}.",
        f"Used comparison population: {subset}.",
        f"Built answer from {evidence_count} evidence source(s).",
    ]


def _finding_based_follow_ups(result: InvestigationPanelResult) -> list[str]:
    suggestions: list[str] = []

    period_table = result.evidence_tables.get("Period KPI Comparison")
    if period_table is not None and len(period_table) >= 2:
        suggestions.append("Why did processing time increase this month?")

    activity_table = result.evidence_tables.get("Activity Delay Comparison")
    if activity_table is not None and not activity_table.empty:
        top_activity = str(activity_table.iloc[0].get("activity", "")).strip()
        if top_activity:
            suggestions.append(f"Why is {top_activity} slower in the recent period?")
        suggestions.append("Which step got slower recently?")

    rework_table = result.evidence_tables.get("Slow vs Non-slow Rework Comparison")
    if rework_table is not None and not rework_table.empty:
        suggestions.append("How are slow cases different from non-slow cases?")

    variant_table = result.evidence_tables.get("Slow vs Non-slow Variant Comparison")
    if variant_table is not None and not variant_table.empty:
        suggestions.append("Which variant appears most associated with slow cases?")

    suggestions.extend(result.follow_up_questions)
    deduped: list[str] = []
    seen: set[str] = set()
    for suggestion in suggestions:
        if suggestion not in seen:
            seen.add(suggestion)
            deduped.append(suggestion)
    return deduped[:4]


def _display_table(frame, max_rows: int | None = None) -> None:
    display = frame.copy()
    numeric_columns = display.select_dtypes(include=["number"]).columns
    if len(numeric_columns) > 0:
        display[numeric_columns] = display[numeric_columns].round(2)
    if max_rows is not None:
        display = display.head(max_rows)
    st.dataframe(display, use_container_width=True)


def _format_context_value(value: object) -> str:
    if isinstance(value, (list, tuple, set)):
        parts = [_clean_answer_text(str(item)) for item in value if str(item).strip()]
        return ", ".join(parts) if parts else "N/A"
    return _clean_answer_text(str(value))


st.title("Investigation")
st.write(
    "Ask a question and review a grounded answer with supporting evidence."
)
st.caption("Use the benchmark question to understand what changed, what supports it, and what remains uncertain.")

event_log = st.session_state.get("event_log")
if event_log is None:
    st.warning("No event log found in session. Go to Upload page first.")
    st.stop()

current_signature = (
    int(len(event_log)),
    tuple(str(column) for column in event_log.columns),
)
previous_signature = st.session_state.get("investigation_result_signature")
if previous_signature != current_signature:
    st.session_state.pop("investigation_result", None)

if "investigation_question_input" not in st.session_state:
    st.session_state["investigation_question_input"] = QUESTION_TEMPLATES[0]

st.subheader("Quick Start Questions")
st.caption("Start with a common investigation question, or enter your own below.")
template_columns = st.columns(2)
selected_template: str | None = None
for index, template in enumerate(QUESTION_TEMPLATES):
    if template_columns[index % 2].button(template):
        selected_template = template

if selected_template is not None:
    st.session_state["investigation_question_input"] = selected_template

question = st.text_input(
    "Ask a question",
    key="investigation_question_input",
    placeholder="Why did processing time increase this month?",
)
run_investigation = st.button("Analyze", type="primary")

if run_investigation or selected_template is not None:
    st.session_state["investigation_result"] = build_investigation_panel_result(
        event_log=event_log,
        question=question,
    )
    st.session_state["investigation_result_signature"] = current_signature

if "investigation_result" not in st.session_state:
    st.session_state["investigation_result"] = build_core_scenario_result(event_log=event_log)
    st.session_state["investigation_result_signature"] = current_signature
    st.caption("Default benchmark loaded: Why did processing time increase this month?")

result: InvestigationPanelResult | None = st.session_state.get("investigation_result")
if result is None:
    st.info("Run an investigation question to view results.")
    st.stop()

answer_payload = result.answer_payload

st.subheader("Investigation Answer")
st.caption("This answer is composed from deterministic analyses and supporting evidence.")
if not result.is_supported:
    st.warning("This question is not currently supported. Try one of the suggested questions.")

summary_signals = _extract_summary_signals(result)
if summary_signals:
    st.markdown("**Key Signals**")
    signal_columns = st.columns(len(summary_signals))
    for index, (label, value, help_text) in enumerate(summary_signals):
        signal_columns[index].metric(label, value, help=help_text)

if answer_payload is not None:
    st.markdown("**Direct Answer**")
    st.info(_clean_answer_text(answer_payload.directAnswer))

    section_groups = [
        ("Key Observations", answer_payload.observations),
        ("Supporting Evidence", answer_payload.evidence),
        ("Interpretation", answer_payload.interpretations),
    ]
    for label, sections in section_groups:
        if not sections:
            continue
        st.markdown(f"**{label}**")
        for section in sections:
            st.markdown(f"**{section.title}**")
            st.write(_clean_answer_text(section.text))
else:
    for block in result.answer_blocks:
        st.markdown(f"**{block.title}**")
        cleaned_text = _clean_answer_text(block.text)
        if block.title.lower() == "observation":
            st.info(cleaned_text)
        else:
            st.write(cleaned_text)

with st.expander("Evidence references", expanded=False):
    if answer_payload is not None:
        for section in (
            answer_payload.observations
            + answer_payload.evidence
            + answer_payload.interpretations
        ):
            refs = ", ".join(section.evidence_refs) if section.evidence_refs else "None"
            st.write(f"- {section.title}: {refs}")
    else:
        for block in result.answer_blocks:
            refs = ", ".join(block.evidence_refs) if block.evidence_refs else "None"
            st.write(f"- {block.title}: {refs}")

st.markdown("**Limitations and uncertainty**")
limitations = answer_payload.limitations if answer_payload is not None else result.limitations
if limitations:
    for limitation in limitations:
        st.write(f"- {limitation}")
else:
    st.write("- No explicit limitations were returned.")

st.markdown("**Suggested Next Questions**")
st.caption("Use these to verify or narrow the likely delay drivers.")
adaptive_follow_ups = _finding_based_follow_ups(result)
if answer_payload is not None and answer_payload.followUpQuestions:
    adaptive_follow_ups = answer_payload.followUpQuestions
follow_up_columns = st.columns(1 if len(adaptive_follow_ups) <= 1 else 2)
for index, follow_up in enumerate(adaptive_follow_ups):
    if follow_up_columns[index % len(follow_up_columns)].button(
        f"Use: {follow_up}", key=f"follow_up_{index}_{follow_up}"
    ):
        st.session_state["investigation_question_input"] = follow_up
        st.session_state["investigation_result"] = build_investigation_panel_result(
            event_log=event_log,
            question=follow_up,
        )
        st.session_state["investigation_result_signature"] = current_signature
        st.rerun()

st.divider()
st.subheader("Evidence")
st.caption("Review the strongest supporting tables and comparisons behind the answer.")
if not result.evidence_tables and not result.evidence_charts:
    st.info("No structured evidence is available for this question.")

st.markdown("**Key Evidence**")
for chart_name, chart_data in result.evidence_charts.items():
    if chart_data.empty:
        continue
    st.markdown(f"**{_humanize_label(chart_name)}**")
    if {"period", "avg_duration_hours"}.issubset(set(chart_data.columns)):
        chart_frame = chart_data[["period", "avg_duration_hours"]].set_index("period")
        if len(chart_frame) == 2:
            st.caption("Average case duration: previous vs recent period")
            st.bar_chart(chart_frame)
        else:
            st.caption("Average case duration trend by period")
            st.line_chart(chart_frame)
    else:
        _display_table(chart_data)

priority_tables = [
    "Activity Delay Comparison",
    "Period KPI Comparison",
    "Slow vs Non-slow Rework Comparison",
]
for table_name in priority_tables:
    table_data = result.evidence_tables.get(table_name)
    if table_data is None or table_data.empty:
        continue
    st.markdown(f"**{_humanize_label(table_name)}**")
    _display_table(table_data, max_rows=10)

with st.expander("Detailed Evidence Tables"):
    for table_name, table_data in result.evidence_tables.items():
        if table_name in priority_tables:
            continue
        st.markdown(f"**{_humanize_label(table_name)}**")
        _display_table(table_data)

st.divider()
st.subheader("How This Answer Was Produced")
st.caption("A concise trace of the evidence path used for the current answer.")
trace = result.trace
trace_col1, trace_col2, trace_col3, trace_col4 = st.columns(4)
question_type_label = (
    answer_payload.questionType if answer_payload is not None else str(trace.get("question_type", "N/A"))
)
trace_col1.metric("Question Type", _humanize_label(str(question_type_label)))
trace_col2.metric("Time Window", _clean_answer_text(str(trace.get("selected_time_window", "N/A"))))
overall_change_state = (
    answer_payload.overallChangeState if answer_payload is not None else "insufficient_evidence"
)
answer_status = (
    answer_payload.answerStatus
    if answer_payload is not None
    else ("supported" if result.is_supported else "insufficient")
)
trace_col3.metric("Overall Change", _friendly_overall_change_state(str(overall_change_state)))
trace_col4.metric("Answer Status", _friendly_answer_status(str(answer_status)))
st.caption(f"Current subset: {_clean_answer_text(str(trace.get('selected_subset', 'N/A')))}")
st.markdown("**Evidence path**")
for step in _friendly_steps(trace):
    st.write(f"- {step}")

st.markdown("**Readable trace**")
_render_trace_summary(result)

context_items = result.selected_context or {}
if context_items:
    st.markdown("**Analysis context**")
    for key, value in context_items.items():
        st.write(f"- **{_humanize_label(str(key))}:** {_format_context_value(value)}")

with st.expander("Detailed analysis trace", expanded=False):
    st.markdown("**Analysis Functions Executed**")
    for function_name in trace.get("analysis_functions_executed", []):
        st.write(f"- {_friendly_trace_label(function_name)}")
    st.markdown("**Evidence Sources Used**")
    evidence_used = trace.get("evidence_used", [])
    if evidence_used:
        for evidence_name in evidence_used:
            st.write(f"- {_humanize_label(str(evidence_name))}")
    else:
        st.write("- None")

st.subheader("Next Step")
st.caption("Use the follow-up suggestions above, or continue to process exploration.")
next_col1, next_col2 = st.columns(2)
if next_col1.button("Open Process View", use_container_width=True):
    st.switch_page("pages/4_Process_View.py")
if next_col2.button("Return to Dashboard", use_container_width=True):
    st.switch_page("pages/2_Dashboard.py")

with st.expander("Technical Details (Raw Payload)"):
    st.json(result.to_dict())
