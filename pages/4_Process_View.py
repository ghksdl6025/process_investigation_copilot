"""Process view page with lightweight Directly-Follows Graph visualization."""

import streamlit as st

from src.process_investigation_copilot.analysis.process_view import (
    build_directly_follows_graph,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    build_slow_case_comparison,
)

st.title("Process View")
st.write(
    "Explore process flow patterns using a Directly-Follows Graph (DFG). "
    "Use subsets and analysis modes to compare dominant paths, slow-case paths, "
    "and potential delay hotspots within the analyzed event population."
)

event_log = st.session_state.get("event_log")
if event_log is None:
    st.warning("No event log found in session. Go to Upload page first.")
    st.stop()

slow_case_result = build_slow_case_comparison(event_log)

mode = st.selectbox(
    "Analysis mode",
    options=["frequency", "bottleneck"],
    index=0,
    help=(
        "`frequency`: emphasize commonly observed transitions. "
        "`bottleneck`: emphasize transitions with higher average transition time "
        "for investigation (descriptive signal, not causal proof)."
    ),
)

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
subset_label = st.selectbox("Case subset", options=list(subset_options.keys()), index=0)
view = subset_options[subset_label]

st.caption(
    "Subset guide: `majority_cases` selects top variants until cumulative case "
    "coverage reaches at least 50%. `top_variant`, `top_3_variants`, and "
    "`top_5_variants` focus on the most frequent variant paths."
)

col_cfg1, _, col_cfg3 = st.columns(3)
layout_direction = col_cfg1.selectbox(
    "Layout direction",
    options=["TB", "LR"],
    index=0,
    help="`TB` (top-to-bottom) is generally easier for dense graphs.",
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

st.caption(
    "Edge thickness represents transition frequency. Edge labels show frequency "
    "(and average transition minutes when enabled). "
    "In bottleneck mode, time-based edge color highlights relatively slower transitions "
    "to support investigation. "
    "Dense graphs are automatically rendered in a compact style for readability."
)

if dfg.edges.empty:
    st.info("No transitions match the current DFG filter settings.")
else:
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
    st.subheader("Transition Table")
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
    st.dataframe(transition_table, use_container_width=True)
