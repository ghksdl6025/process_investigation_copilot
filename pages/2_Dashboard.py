"""Dashboard page with high-level summary metrics."""

from datetime import datetime

import streamlit as st

from src.process_investigation_copilot.analysis.dashboard_metrics import (
    build_dashboard_activity_frequency_table,
    build_dashboard_overview_metrics,
)
from src.process_investigation_copilot.analysis.activity_delay_analysis import (
    compare_activity_delay_between_periods,
)
from src.process_investigation_copilot.analysis.period_comparison import (
    compare_period_case_performance,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    build_slow_case_comparison,
)
from src.process_investigation_copilot.analysis.process_view import (
    build_directly_follows_graph,
    build_transition_insights,
)
from src.process_investigation_copilot.analysis.summary import (
    summarize_slow_case_overview,
    summarize_top_activity_shift,
)
from src.process_investigation_copilot.reporting.pdf_export import (
    build_curated_pdf_report,
    short_dashboard_payload,
)
from src.process_investigation_copilot.ui import (
    apply_global_ui,
    ensure_active_dataset_restored,
    render_sidebar_branding,
)

apply_global_ui()
render_sidebar_branding()
ensure_active_dataset_restored()


def _fmt_num(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{float(value):,.{digits}f}"


def _render_period_chart() -> None:
    chart_data = period_comparison.trend_data.set_index("period")[
        ["avg_duration_hours", "median_duration_hours"]
    ]
    if len(chart_data) == 2:
        st.caption("Period comparison chart (Previous vs Recent)")
        st.bar_chart(chart_data, use_container_width=True)
    else:
        st.caption("Period trend chart")
        st.line_chart(chart_data, use_container_width=True)


st.title("Dashboard")
st.caption("Summary view of process performance and risk signals before deeper investigation.")

event_log = st.session_state.get("event_log")
if event_log is None:
    st.warning("No event log found in session. Go to Upload page first.")
    st.stop()

metrics = build_dashboard_overview_metrics(event_log)
slow_analysis = build_slow_case_comparison(event_log)
base_case_metrics = slow_analysis.case_metrics_with_flags.copy()
period_comparison = compare_period_case_performance(base_case_metrics)
activity_delay = compare_activity_delay_between_periods(
    event_log=event_log,
    case_metrics=base_case_metrics,
)

case_metrics = base_case_metrics.copy()
if "is_slow_case" in case_metrics.columns:
    case_metrics["is_slow_case"] = case_metrics["is_slow_case"].map(
        {True: "slow", False: "non_slow"}
    )

st.markdown("### Report Export")
st.caption("Create a shareable PDF summary of the current analysis.")

report_bytes = st.session_state.get("export_pdf_bytes")
report_name = st.session_state.get("export_pdf_name", "process_investigation_report.pdf")
report_ready = bool(report_bytes)

if not report_ready:
    if st.button("Generate PDF report", type="primary"):
        try:
            with st.spinner("Generating report..."):
                process_dfg = build_directly_follows_graph(
                    event_log=event_log,
                    case_group="all",
                    slow_case_result=slow_analysis,
                    min_edge_frequency=2,
                    top_n_edges=15,
                    layout_direction="TB",
                    visual_mode="frequency",
                    edge_label_mode="frequency_only",
                )
                process_payload = {
                    "mode": "frequency",
                    "subset": "All analyzed cases",
                    "case_count": process_dfg.case_count,
                    "event_count": process_dfg.event_count,
                    "edge_count": int(len(process_dfg.edges)),
                    "insights": build_transition_insights(process_dfg.edges),
                    "dfg_edges": process_dfg.edges.head(40)[
                        [
                            "source_activity",
                            "target_activity",
                            "transition_frequency",
                            "avg_transition_minutes",
                        ]
                    ].to_dict(orient="records"),
                    "top_edges": process_dfg.edges.head(8)[
                        [
                            "source_activity",
                            "target_activity",
                            "transition_frequency",
                            "avg_transition_minutes",
                        ]
                    ].to_dict(orient="records"),
                }

                investigation_result = st.session_state.get("investigation_result")
                investigation_payload = (
                    investigation_result.to_dict()
                    if investigation_result is not None and hasattr(investigation_result, "to_dict")
                    else None
                )
                dashboard_payload = short_dashboard_payload(
                    overview_metrics=metrics,
                    slow_case_summary=slow_analysis.summary,
                    period_comparison=period_comparison,
                    activity_delay=activity_delay,
                    activity_comparison=slow_analysis.activity_comparison,
                    rework_comparison=slow_analysis.rework_comparison,
                )
                report_bytes = build_curated_pdf_report(
                    dataset_label=st.session_state.get("active_event_log_source"),
                    validation_report=st.session_state.get("validation_report"),
                    dashboard_payload=dashboard_payload,
                    process_view_payload=process_payload,
                    investigation_payload=investigation_payload,
                )
                st.session_state["export_pdf_bytes"] = report_bytes
                st.session_state["export_pdf_name"] = (
                    f"process_investigation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                )
            st.success("Report is ready.")
            st.rerun()
        except Exception as error:  # noqa: BLE001
            st.error(f"Report generation failed: {error}")
else:
    st.download_button(
        "Download PDF report",
        data=report_bytes,
        file_name=report_name,
        mime="application/pdf",
        type="primary",
    )
    if st.button("Regenerate report"):
        st.session_state.pop("export_pdf_bytes", None)
        st.session_state.pop("export_pdf_name", None)
        st.rerun()

col1, col2, col3 = st.columns(3)
col1.metric("Events", metrics["events"])
col2.metric("Cases", metrics["cases"])
col3.metric("Activities", metrics["activities"])

col4, col5 = st.columns(2)
col4.metric("Slow Cases", slow_analysis.summary["slow_case_count"])
col5.metric(
    "Slow Case Ratio",
    f"{slow_analysis.summary['slow_case_ratio']:.1%}",
)
st.caption(summarize_slow_case_overview(slow_analysis.summary))

st.markdown("### Key Findings")
finding_cols = st.columns(4)

period_delta = period_comparison.percent_diff.get("avg_duration_hours")
period_value = (
    f"{period_delta:+.1f}%"
    if period_comparison.is_comparable and period_delta is not None
    else "N/A"
)
finding_cols[0].metric(
    "Processing-Time Change",
    period_value,
    help="Recent vs previous average case duration.",
)

finding_cols[1].metric(
    "Slow-Case Share",
    f"{slow_analysis.summary['slow_case_ratio']:.1%}",
    help="Top 10% longest cases by duration.",
)

if activity_delay.is_comparable and not activity_delay.ranked_table.empty:
    top_delay = activity_delay.ranked_table.iloc[0]
    finding_cols[2].metric(
        "Largest Delay Increase",
        str(top_delay.get("activity", "N/A")),
        help=f"Avg delay proxy change: {_fmt_num(top_delay.get('absolute_increase_minutes'))} min",
    )
else:
    finding_cols[2].metric("Largest Delay Increase", "N/A")

if not slow_analysis.activity_comparison.empty:
    top_shift = slow_analysis.activity_comparison.iloc[0]
    finding_cols[3].metric(
        "Strongest Slow-Case Shift",
        str(top_shift.get("activity", "N/A")),
        help=f"Share delta: {_fmt_num(top_shift.get('share_delta'), 3)}",
    )
else:
    finding_cols[3].metric("Strongest Slow-Case Shift", "N/A")
st.caption(
    "Quick read: confirm period change, identify delay hotspots, and compare slow vs non-slow behavior."
)

st.divider()

st.subheader("Period Performance: Recent vs Previous")
st.caption("Check whether overall case duration shifted between the two most relevant periods.")
if not period_comparison.is_comparable:
    st.info(period_comparison.message)
else:
    p_recent = period_comparison.recent
    p_previous = period_comparison.previous
    assert p_recent is not None and p_previous is not None

    colp1, colp2, colp3, colp4 = st.columns(4)
    colp1.metric(
        "Recent Avg Duration (h)",
        f"{p_recent.avg_duration_hours:.2f}" if p_recent.avg_duration_hours is not None else "N/A",
        delta=(
            f"{period_comparison.percent_diff['avg_duration_hours']:.1f}%"
            if period_comparison.percent_diff.get("avg_duration_hours") is not None
            else None
        ),
    )
    colp2.metric(
        "Recent Median Duration (h)",
        f"{p_recent.median_duration_hours:.2f}" if p_recent.median_duration_hours is not None else "N/A",
        delta=(
            f"{period_comparison.percent_diff['median_duration_hours']:.1f}%"
            if period_comparison.percent_diff.get("median_duration_hours") is not None
            else None
        ),
    )
    colp3.metric(
        "Recent P90 Duration (h)",
        f"{p_recent.p90_duration_hours:.2f}" if p_recent.p90_duration_hours is not None else "N/A",
        delta=(
            f"{period_comparison.percent_diff['p90_duration_hours']:.1f}%"
            if period_comparison.percent_diff.get("p90_duration_hours") is not None
            else None
        ),
    )
    colp4.metric("Recent Case Count", p_recent.case_count, delta=p_recent.case_count - p_previous.case_count)

    direction = (
        "increased"
        if period_comparison.processing_time_increased
        else "did not increase"
    )
    st.info(f"Takeaway: Average processing time {direction} in the recent period.")
    st.caption(period_comparison.message)
    _render_period_chart()

st.divider()
st.subheader("Delay Signals by Activity")
st.caption("Highlights activities with the largest increase in elapsed-time proxy between periods.")
if not activity_delay.is_comparable:
    st.info(activity_delay.message)
else:
    evidence_table = activity_delay.ranked_table.head(15).copy()
    top_row = evidence_table.iloc[0] if not evidence_table.empty else None
    if top_row is not None:
        st.info(
            "Takeaway: "
            f"`{top_row['activity']}` shows the largest delay increase "
            f"({_fmt_num(top_row['absolute_increase_minutes'])} min)."
        )
    chart_data = evidence_table[
        ["activity", "absolute_increase_minutes"]
    ].set_index("activity")
    st.bar_chart(chart_data, use_container_width=True)
    with st.expander("View activity delay evidence table"):
        st.dataframe(evidence_table, use_container_width=True)
    if activity_delay.methodology_notes:
        st.caption("Method note: " + " ".join(activity_delay.methodology_notes))
    if activity_delay.uncertainty_flags:
        st.caption("Data caution: " + " ".join(activity_delay.uncertainty_flags))

st.divider()
st.subheader("Slow-Case Signals")
st.caption("Compare behavior differences between slow and non-slow cases.")
st.markdown("**Activity Share Difference**")
activity_delta_chart = slow_analysis.activity_comparison[
    ["activity", "share_delta"]
].set_index("activity")
st.bar_chart(activity_delta_chart, use_container_width=True)
st.info("Takeaway: " + summarize_top_activity_shift(slow_analysis.activity_comparison))
with st.expander("View activity-share comparison table"):
    st.dataframe(slow_analysis.activity_comparison, use_container_width=True)

st.markdown("**Variant Distribution Difference**")
st.caption("Highlights path differences between slow and non-slow populations.")
variant_chart = slow_analysis.variant_comparison.head(20)[
    ["variant", "slow_case_count", "non_slow_case_count"]
].set_index("variant")
st.bar_chart(variant_chart, use_container_width=True)
if len(slow_analysis.variant_comparison) > 20:
    st.caption("Showing top 20 variants in chart. Full table is shown below.")
with st.expander("View full variant distribution table"):
    st.dataframe(slow_analysis.variant_comparison, use_container_width=True)

st.markdown("**Rework Difference**")
st.caption("Compares rework intensity across slow and non-slow case groups.")
if not slow_analysis.rework_comparison.empty:
    slow_row = slow_analysis.rework_comparison[
        slow_analysis.rework_comparison["case_group"] == "slow"
    ]
    non_row = slow_analysis.rework_comparison[
        slow_analysis.rework_comparison["case_group"] == "non_slow"
    ]
    if not slow_row.empty and not non_row.empty:
        delta = float(slow_row.iloc[0]["rework_case_ratio"]) - float(non_row.iloc[0]["rework_case_ratio"])
        st.info(f"Takeaway: Slow cases show {delta:+.1%} rework-ratio difference vs non-slow cases.")
with st.expander("View rework comparison table"):
    st.dataframe(slow_analysis.rework_comparison, use_container_width=True)

st.divider()
st.subheader("Drill Down")
st.caption("Move from summary to targeted analysis.")
next_col1, next_col2, next_col3 = st.columns(3)
if next_col1.button("Investigate delay drivers", use_container_width=True):
    st.switch_page("pages/3_Investigation.py")
if next_col2.button("Inspect bottleneck candidates", use_container_width=True):
    st.switch_page("pages/4_Process_View.py")
if next_col3.button("Explore slow-case differences", use_container_width=True):
    st.switch_page("pages/3_Investigation.py")

with st.expander("Additional Tables"):
    st.markdown("**Activity Frequency (Reference)**")
    st.dataframe(build_dashboard_activity_frequency_table(event_log), use_container_width=True)
    st.markdown("**Case Metrics (Reference)**")
    st.dataframe(case_metrics, use_container_width=True)
