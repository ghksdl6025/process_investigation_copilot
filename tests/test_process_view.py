"""Tests for lightweight DFG process view outputs."""

from pathlib import Path

import pandas as pd

from src.process_investigation_copilot.analysis.process_view import (
    build_transition_insights,
    build_directly_follows_graph,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    build_slow_case_comparison,
)


def _synthetic_variant_event_log() -> pd.DataFrame:
    """Build deterministic variant frequencies for subset selection tests.

    Variant frequencies:
    - A > B > C : 4 cases
    - A > D > E : 3 cases
    - F > G > H : 2 cases
    - I > J > K : 1 case
    """
    variant_cases = {
        "A > B > C": 4,
        "A > D > E": 3,
        "F > G > H": 2,
        "I > J > K": 1,
    }
    rows: list[dict[str, str]] = []
    case_index = 1
    for variant, num_cases in variant_cases.items():
        activities = variant.split(" > ")
        for _ in range(num_cases):
            case_id = f"S-{case_index:03d}"
            for step_idx, activity in enumerate(activities):
                rows.append(
                    {
                        "case_id": case_id,
                        "activity": activity,
                        "timestamp": f"2026-01-01T00:{case_index:02d}:{step_idx:02d}",
                    }
                )
            case_index += 1
    return pd.DataFrame(rows)


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


def test_majority_cases_subset_selection() -> None:
    event_log = _synthetic_variant_event_log()
    view = build_directly_follows_graph(event_log, case_group="majority_cases")
    # Majority should include top variants until >=50% coverage: 4 + 3 = 7/10 cases.
    assert view.case_count == 7


def test_top_variant_subset_selection() -> None:
    event_log = _synthetic_variant_event_log()
    view = build_directly_follows_graph(event_log, case_group="top_variant")
    assert view.case_count == 4


def test_top_3_variants_subset_selection() -> None:
    event_log = _synthetic_variant_event_log()
    view = build_directly_follows_graph(event_log, case_group="top_3_variants")
    assert view.case_count == 9


def test_top_5_variants_subset_selection() -> None:
    event_log = _synthetic_variant_event_log()
    view = build_directly_follows_graph(event_log, case_group="top_5_variants")
    # Only 4 variants exist, so top-5 should include all.
    assert view.case_count == 10


def test_bottleneck_mode_uses_transition_time_coloring() -> None:
    event_log = _synthetic_variant_event_log()
    frequency_view = build_directly_follows_graph(event_log, visual_mode="frequency")
    bottleneck_view = build_directly_follows_graph(event_log, visual_mode="bottleneck")

    # In frequency mode, default edge color is neutral.
    assert 'color="#666666"' in frequency_view.graphviz_dot
    # In bottleneck mode with valid durations, at least one edge gets a time-based color.
    assert 'color="#666666"' not in bottleneck_view.graphviz_dot


def test_density_aware_rendering_simplifies_dense_graph_labels() -> None:
    rows: list[dict[str, str]] = []
    # Create many distinct edges so the graph is treated as very dense.
    for i in range(60):
        case_id = f"D-{i:03d}"
        rows.append(
            {
                "case_id": case_id,
                "activity": f"SRC_{i}",
                "timestamp": f"2026-01-01T00:00:{i % 60:02d}",
            }
        )
        rows.append(
            {
                "case_id": case_id,
                "activity": f"TGT_{i}",
                "timestamp": f"2026-01-01T00:01:{i % 60:02d}",
            }
        )
    event_log = pd.DataFrame(rows)
    view = build_directly_follows_graph(
        event_log,
        case_group="all",
        top_n_edges=60,
        edge_label_mode="full",
    )
    # Very dense mode uses compact spacing.
    assert "ranksep=0.30" in view.graphviz_dot
    # Full labels are adaptively simplified; transition-time suffix should be absent.
    assert " | " not in view.graphviz_dot


def test_build_transition_insights_from_edges() -> None:
    edges = pd.DataFrame(
        [
            {
                "source_activity": "A",
                "target_activity": "B",
                "transition_frequency": 10,
                "avg_transition_minutes": 2.0,
            },
            {
                "source_activity": "B",
                "target_activity": "C",
                "transition_frequency": 3,
                "avg_transition_minutes": 20.0,
            },
        ]
    )
    insights = build_transition_insights(edges)
    assert insights["most_frequent"]["transition"] == "A -> B"
    assert insights["most_frequent"]["value"] == "10"
    assert insights["slowest_average"]["transition"] == "B -> C"
    assert insights["slowest_average"]["value"] == "20.0m"
    # score: A->B = 20, B->C = 60
    assert insights["bottleneck_candidate"]["transition"] == "B -> C"


def test_build_transition_insights_empty_edges() -> None:
    empty_edges = pd.DataFrame(
        columns=[
            "source_activity",
            "target_activity",
            "transition_frequency",
            "avg_transition_minutes",
        ]
    )
    insights = build_transition_insights(empty_edges)
    assert insights["most_frequent"]["transition"] == "N/A"
    assert insights["slowest_average"]["transition"] == "N/A"
    assert insights["bottleneck_candidate"]["transition"] == "N/A"
