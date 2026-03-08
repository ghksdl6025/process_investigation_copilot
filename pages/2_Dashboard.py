"""Dashboard page with high-level summary metrics."""

import streamlit as st

from src.process_investigation_copilot.analysis.dashboard_metrics import (
    build_dashboard_activity_frequency_table,
    build_dashboard_overview_metrics,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    build_slow_case_comparison,
)
from src.process_investigation_copilot.analysis.summary import (
    summarize_slow_case_overview,
    summarize_top_activity_shift,
)

st.title("Dashboard")

event_log = st.session_state.get("event_log")
if event_log is None:
    st.warning("No event log found in session. Go to Upload page first.")
    st.stop()

metrics = build_dashboard_overview_metrics(event_log)
slow_analysis = build_slow_case_comparison(event_log)
case_metrics = slow_analysis.case_metrics_with_flags.copy()
if "is_slow_case" in case_metrics.columns:
    case_metrics["is_slow_case"] = case_metrics["is_slow_case"].map(
        {True: "slow", False: "non_slow"}
    )

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

st.subheader("Activity Frequency")
st.dataframe(build_dashboard_activity_frequency_table(event_log), use_container_width=True)

st.subheader("Case Metrics")
st.dataframe(case_metrics, use_container_width=True)

st.subheader("Slow vs Non-Slow: Activity Share Delta")
activity_delta_chart = slow_analysis.activity_comparison[
    ["activity", "share_delta"]
].set_index("activity")
st.bar_chart(activity_delta_chart, use_container_width=True)
st.caption(summarize_top_activity_shift(slow_analysis.activity_comparison))
st.dataframe(slow_analysis.activity_comparison, use_container_width=True)

st.subheader("Slow vs Non-Slow: Variant Distribution")
variant_chart = slow_analysis.variant_comparison.head(20)[
    ["variant", "slow_case_count", "non_slow_case_count"]
].set_index("variant")
st.bar_chart(variant_chart, use_container_width=True)
if len(slow_analysis.variant_comparison) > 20:
    st.caption("Showing top 20 variants in chart. Full table is shown below.")
st.dataframe(slow_analysis.variant_comparison, use_container_width=True)

st.subheader("Slow vs Non-Slow: Rework Comparison")
st.dataframe(slow_analysis.rework_comparison, use_container_width=True)
