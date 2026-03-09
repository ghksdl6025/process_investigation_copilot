"""Process view page with lightweight Directly-Follows Graph visualization."""

import streamlit as st

from src.process_investigation_copilot.analysis.process_view import (
    build_transition_insights,
    build_directly_follows_graph,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    build_slow_case_comparison,
)
from src.process_investigation_copilot.ui import (
    apply_global_ui,
    ensure_active_dataset_restored,
    render_sidebar_branding,
)

apply_global_ui()
render_sidebar_branding()
ensure_active_dataset_restored()

st.title("Process View")
st.write(
    "Inspect process structure with a Directly-Follows Graph (DFG) and compare case subsets "
    "to identify dominant paths and delay candidates."
)
st.caption("Best used after Dashboard: read the graph first, then validate details.")

event_log = st.session_state.get("event_log")
if event_log is None:
    st.warning("No event log found in session. Go to Upload page first.")
    st.stop()

slow_case_result = build_slow_case_comparison(event_log)

# Keep subset selection values backend-compatible while making UI labels easy to extend.
subset_options = {
    "All analyzed cases": "all",
    "Slow cases only": "slow",
    "Non-slow cases only": "non_slow",
    "Majority cases (top variants to 50%)": "majority_cases",
    "Top variant": "top_variant",
    "Top 3 variants": "top_3_variants",
    "Top 5 variants": "top_5_variants",
}

with st.expander("View Settings", expanded=False):
    mode = st.selectbox(
        "Comparison mode",
        options=["frequency", "bottleneck"],
        index=0,
        help=(
            "`frequency`: emphasize common transitions. "
            "`bottleneck`: emphasize slower transitions for investigation "
            "(descriptive, not causal proof)."
        ),
    )
    subset_label = st.selectbox("Current subset", options=list(subset_options.keys()), index=0)
    st.caption(
        "Subset guide: `majority_cases` uses top variants up to 50% cumulative case coverage. "
        "`top_variant`, `top_3_variants`, and `top_5_variants` focus on dominant paths."
    )

    col_cfg1, _, col_cfg3 = st.columns(3)
    layout_direction = col_cfg1.selectbox(
        "Layout direction",
        options=["TB", "LR"],
        index=0,
        help="`TB` is usually easier to read for denser graphs.",
    )
    edge_label_mode = col_cfg3.selectbox(
        "Edge labels",
        options=["frequency_only", "full", "none"],
        index=0 if mode == "frequency" else 1,
    )

    default_min_freq = 2 if mode == "frequency" else 1
    default_top_n = 15 if mode == "frequency" else 12
    col_filter1, col_filter2 = st.columns(2)
    min_edge_frequency = col_filter1.number_input(
        "Minimum edge frequency",
        min_value=1,
        value=default_min_freq,
        step=1,
    )
    top_n_edges = col_filter2.number_input(
        "Top N edges (0 = no limit)",
        min_value=0,
        value=default_top_n,
        step=1,
    )

view = subset_options[subset_label]
top_n_value = None if int(top_n_edges) == 0 else int(top_n_edges)

dfg = build_directly_follows_graph(
    event_log=event_log,
    case_group=view,
    slow_case_result=slow_case_result,
    min_edge_frequency=int(min_edge_frequency),
    top_n_edges=top_n_value,
    layout_direction=layout_direction,
    visual_mode=mode,
    edge_label_mode=edge_label_mode,
)

col1, col2, col3 = st.columns(3)
col1.metric("Cases in view", dfg.case_count)
col2.metric("Events in view", dfg.event_count)
col3.metric("DFG edges", int(len(dfg.edges)))
st.markdown("### Current View")
sum_col1, sum_col2, sum_col3 = st.columns(3)
sum_col1.metric("Comparison Mode", "Frequency" if mode == "frequency" else "Bottleneck")
sum_col2.metric("Current Subset", subset_label)
sum_col3.metric(
    "Edge Filter",
    f"min {int(min_edge_frequency)} | top {'all' if top_n_value is None else int(top_n_value)}",
)
st.caption("Quick read: use Transition Insights to identify what to inspect in the graph.")

insights = build_transition_insights(dfg.edges)
st.subheader("Transition Insights")
st.caption("Top transition signals for this current view.")
ins_col1, ins_col2, ins_col3 = st.columns(3)
ins_col1.metric("Most Frequent", insights["most_frequent"]["value"])
ins_col1.write(f"Transition: `{insights['most_frequent']['transition']}`")

slowest_card_title = (
    "Slowest Avg (Focus)"
    if mode == "bottleneck"
    else "Slowest Avg"
)
ins_col2.metric(slowest_card_title, insights["slowest_average"]["value"])
ins_col2.write(f"Transition: `{insights['slowest_average']['transition']}`")

ins_col3.metric("Bottleneck Candidate", insights["bottleneck_candidate"]["value"])
ins_col3.write(f"Transition: `{insights['bottleneck_candidate']['transition']}`")

st.caption(
    "How to read the DFG: thicker edges indicate more frequent transitions. "
    "Labels show frequency (and average minutes when enabled)."
)
if mode == "bottleneck":
    st.warning(
        "Bottleneck mode is descriptive. Slower edges are investigation leads, not proof of root cause."
    )

if dfg.edges.empty:
    st.info("No transitions match the current DFG filter settings.")
else:
    st.subheader("Directly-Follows Graph")
    st.graphviz_chart(dfg.graphviz_dot, use_container_width=True)
    if view in {"majority_cases", "top_variant", "top_3_variants", "top_5_variants"}:
        total_cases = int(slow_case_result.summary.get("total_case_count", 0))
        coverage = (dfg.case_count / total_cases) if total_cases else 0.0
        subset_label_text = {
            "majority_cases": "Majority-cases subset",
            "top_variant": "Top-variant subset",
            "top_3_variants": "Top-3-variants subset",
            "top_5_variants": "Top-5-variants subset",
        }[view]
        st.caption(f"{subset_label_text} covers {dfg.case_count}/{total_cases} cases ({coverage:.1%}).")
    st.subheader("Transition Details")
    st.caption(
        "Supporting detail table for exact values. "
        "Sorted by average transition time in bottleneck mode, otherwise by transition frequency."
    )
    transition_table = dfg.edges.copy()
    if mode == "bottleneck":
        transition_table = transition_table.sort_values(
            ["avg_transition_minutes", "transition_frequency"],
            ascending=[False, False],
            na_position="last",
        )
    else:
        transition_table = transition_table.sort_values(
            ["transition_frequency", "avg_transition_minutes"],
            ascending=[False, False],
            na_position="last",
        )
    with st.expander("Show transition detail table", expanded=False):
        st.dataframe(transition_table, use_container_width=True)

st.divider()
st.subheader("Next Step")
st.caption("Use this view to inspect structure, then move to focused investigation.")
next_col1, next_col2 = st.columns(2)
if next_col1.button("Open Investigation", use_container_width=True):
    st.switch_page("pages/3_Investigation.py")
if next_col2.button("Return to Dashboard", use_container_width=True):
    st.switch_page("pages/2_Dashboard.py")
