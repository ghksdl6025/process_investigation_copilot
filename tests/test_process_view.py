"""Tests for lightweight DFG process view outputs."""

from pathlib import Path

import pandas as pd

from src.process_investigation_copilot.analysis.process_view import (
    build_directly_follows_graph,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    build_slow_case_comparison,
)


def test_build_dfg_for_all_and_case_groups() -> None:
    event_log = pd.read_csv(Path("data/sample_event_log.csv"))
    slow_case_result = build_slow_case_comparison(event_log)

    all_view = build_directly_follows_graph(
        event_log, case_group="all", slow_case_result=slow_case_result
    )
    slow_view = build_directly_follows_graph(
        event_log, case_group="slow", slow_case_result=slow_case_result
    )
    non_slow_view = build_directly_follows_graph(
        event_log, case_group="non_slow", slow_case_result=slow_case_result
    )
    majority_view = build_directly_follows_graph(
        event_log, case_group="majority_cases", slow_case_result=slow_case_result
    )
    top_variant_view = build_directly_follows_graph(
        event_log, case_group="top_variant", slow_case_result=slow_case_result
    )
    top_3_view = build_directly_follows_graph(
        event_log, case_group="top_3_variants", slow_case_result=slow_case_result
    )
    top_5_view = build_directly_follows_graph(
        event_log, case_group="top_5_variants", slow_case_result=slow_case_result
    )

    assert {"source_activity", "target_activity", "transition_frequency"}.issubset(
        all_view.edges.columns
    )
    assert all_view.case_count == 3
    assert all_view.event_count == len(event_log)
    assert slow_view.case_count + non_slow_view.case_count == all_view.case_count
    assert 0 < majority_view.case_count <= all_view.case_count
    assert 0 < top_variant_view.case_count <= top_3_view.case_count <= top_5_view.case_count


def test_build_dfg_supports_layout_direction() -> None:
    event_log = pd.read_csv(Path("data/sample_event_log.csv"))
    result_tb = build_directly_follows_graph(event_log, case_group="all", layout_direction="TB")
    result_lr = build_directly_follows_graph(event_log, case_group="all", layout_direction="LR")
    assert "rankdir=TB;" in result_tb.graphviz_dot
    assert "rankdir=LR;" in result_lr.graphviz_dot


def test_build_dfg_supports_visual_modes() -> None:
    event_log = pd.read_csv(Path("data/sample_event_log.csv"))
    frequency_view = build_directly_follows_graph(
        event_log, case_group="all", visual_mode="frequency"
    )
    bottleneck_view = build_directly_follows_graph(
        event_log, case_group="all", visual_mode="bottleneck"
    )
    assert "DFG (all, frequency)" in frequency_view.graphviz_dot
    assert "DFG (all, bottleneck)" in bottleneck_view.graphviz_dot
