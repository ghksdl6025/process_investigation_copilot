"""Lightweight process-view utilities (Directly-Follows Graph for MVP)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd

from src.process_investigation_copilot.analysis.slow_case_analysis import (
    SlowCaseComparisonResult,
    build_slow_case_comparison,
    build_slow_case_event_population,
)

CaseSubset = Literal[
    "all",
    "slow",
    "non_slow",
    "majority_cases",
    "top_variant",
    "top_3_variants",
    "top_5_variants",
]
# Backward-compatible alias for existing call sites/type hints.
CaseGroup = CaseSubset
LayoutDirection = Literal["TB", "LR"]
EdgeLabelMode = Literal["full", "frequency_only", "none"]
VisualMode = Literal["frequency", "bottleneck"]
MISSING_ACTIVITY_LABEL = "<missing_activity>"


@dataclass
class DFGResult:
    """Structured directly-follows graph output for UI rendering."""

    case_group: CaseSubset
    edges: pd.DataFrame
    graphviz_dot: str
    case_count: int
    event_count: int


def build_transition_insights(edges: pd.DataFrame) -> dict[str, dict[str, str]]:
    """Build lightweight transition insight summaries from filtered DFG edges."""
    empty_insight = {"transition": "N/A", "value": "N/A", "detail": "No transitions in view."}
    if edges.empty:
        return {
            "most_frequent": empty_insight,
            "slowest_average": empty_insight,
            "bottleneck_candidate": empty_insight,
        }

    most_frequent_row = (
        edges.sort_values(
            ["transition_frequency", "avg_transition_minutes"],
            ascending=[False, False],
            na_position="last",
        )
        .iloc[0]
    )
    most_frequent = {
        "transition": _transition_label(most_frequent_row),
        "value": str(int(most_frequent_row["transition_frequency"])),
        "detail": "Transition frequency",
    }

    timed_edges = edges.dropna(subset=["avg_transition_minutes"]).copy()
    if timed_edges.empty:
        slowest_average = {
            "transition": "N/A",
            "value": "N/A",
            "detail": "No valid transition times.",
        }
    else:
        slowest_row = timed_edges.sort_values(
            ["avg_transition_minutes", "transition_frequency"],
            ascending=[False, False],
            na_position="last",
        ).iloc[0]
        slowest_average = {
            "transition": _transition_label(slowest_row),
            "value": f"{float(slowest_row['avg_transition_minutes']):.1f}m",
            "detail": "Highest average transition time",
        }

    scoring_edges = edges.copy()
    scoring_edges["avg_transition_minutes_filled"] = scoring_edges[
        "avg_transition_minutes"
    ].fillna(0.0)
    scoring_edges["bottleneck_score"] = (
        scoring_edges["transition_frequency"] * scoring_edges["avg_transition_minutes_filled"]
    )
    bottleneck_row = scoring_edges.sort_values(
        ["bottleneck_score", "transition_frequency"],
        ascending=[False, False],
    ).iloc[0]
    bottleneck_candidate = {
        "transition": _transition_label(bottleneck_row),
        "value": f"{float(bottleneck_row['bottleneck_score']):.1f}",
        "detail": "Heuristic score = frequency x avg minutes",
    }

    return {
        "most_frequent": most_frequent,
        "slowest_average": slowest_average,
        "bottleneck_candidate": bottleneck_candidate,
    }


def build_directly_follows_graph(
    event_log: pd.DataFrame,
    case_group: CaseSubset = "all",
    slow_case_result: SlowCaseComparisonResult | None = None,
    min_edge_frequency: int = 1,
    top_n_edges: int | None = None,
    layout_direction: LayoutDirection = "TB",
    visual_mode: VisualMode = "frequency",
    color_edges_by_avg_time: bool | None = None,
    edge_label_mode: EdgeLabelMode = "full",
    subset_filter: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    optimize_for_density: bool = True,
) -> DFGResult:
    """Build DFG edges from the analyzed slow-case population."""
    if color_edges_by_avg_time is None:
        color_edges_by_avg_time = visual_mode == "bottleneck"

    slow_case_result = slow_case_result or build_slow_case_comparison(event_log)
    events_with_group = build_slow_case_event_population(
        event_log=event_log,
        case_metrics_with_flags=slow_case_result.case_metrics_with_flags,
    )
    events_filtered = _filter_events_by_group(
        events_with_group,
        case_group=case_group,
        subset_filter=subset_filter,
    )
    edges = _build_dfg_edges(
        events_filtered,
        min_edge_frequency=max(1, int(min_edge_frequency)),
        top_n_edges=top_n_edges,
    )
    return DFGResult(
        case_group=case_group,
        edges=edges,
        graphviz_dot=_build_graphviz_dot(
            edges,
            case_group=case_group,
            layout_direction=layout_direction,
            visual_mode=visual_mode,
            color_edges_by_avg_time=color_edges_by_avg_time,
            edge_label_mode=edge_label_mode,
            optimize_for_density=optimize_for_density,
        ),
        case_count=int(events_filtered["case_id"].nunique()) if len(events_filtered) else 0,
        event_count=int(len(events_filtered)),
    )


def _filter_events_by_group(
    events_with_group: pd.DataFrame,
    case_group: CaseSubset,
    subset_filter: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if subset_filter is not None:
        return subset_filter(events_with_group.copy())

    if case_group == "all":
        return events_with_group.copy()
    if case_group in {"slow", "non_slow"}:
        return events_with_group[events_with_group["case_group"] == case_group].copy()

    selected_case_ids = _subset_case_ids(events_with_group, case_subset=case_group)
    return events_with_group[events_with_group["case_id"].isin(selected_case_ids)].copy()


def _subset_case_ids(events_with_group: pd.DataFrame, case_subset: CaseSubset) -> set:
    subset_id_builders: dict[CaseSubset, Callable[[pd.DataFrame], set]] = {
        "majority_cases": _majority_case_ids,
        "top_variant": lambda events: _top_variant_case_ids(events, top_n_variants=1),
        "top_3_variants": lambda events: _top_variant_case_ids(events, top_n_variants=3),
        "top_5_variants": lambda events: _top_variant_case_ids(events, top_n_variants=5),
    }
    builder = subset_id_builders.get(case_subset)
    return builder(events_with_group) if builder else set()


def _majority_case_ids(events_with_group: pd.DataFrame) -> set:
    """Select case IDs from top variants until cumulative coverage reaches >= 50%."""
    if events_with_group.empty:
        return set()

    variants, variant_counts = _variant_tables(events_with_group)
    total_cases = int(variants["case_id"].nunique())
    target = total_cases * 0.5

    covered = 0
    selected_variants: list[str] = []
    for _, row in variant_counts.iterrows():
        selected_variants.append(str(row["variant"]))
        covered += int(row["case_count"])
        if covered >= target:
            break

    return set(variants[variants["variant"].isin(selected_variants)]["case_id"].tolist())


def _top_variant_case_ids(events_with_group: pd.DataFrame, top_n_variants: int) -> set:
    if events_with_group.empty or top_n_variants <= 0:
        return set()
    variants, variant_counts = _variant_tables(events_with_group)
    selected_variants = set(variant_counts.head(top_n_variants)["variant"].tolist())
    return set(variants[variants["variant"].isin(selected_variants)]["case_id"].tolist())


def _variant_tables(events_with_group: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = events_with_group.copy()
    working["_event_order"] = range(len(working))
    working["activity"] = working["activity"].fillna(MISSING_ACTIVITY_LABEL).astype(str)
    ordered = working.sort_values(
        ["case_id", "timestamp", "_event_order"], na_position="last"
    )
    variants = (
        ordered.groupby("case_id", dropna=False)["activity"]
        .apply(lambda series: " > ".join(series.tolist()))
        .reset_index(name="variant")
    )
    variant_counts = (
        variants.groupby("variant", dropna=False)
        .size()
        .reset_index(name="case_count")
        .sort_values(["case_count", "variant"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return variants, variant_counts


def _build_dfg_edges(
    events: pd.DataFrame, min_edge_frequency: int, top_n_edges: int | None
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(
            columns=[
                "source_activity",
                "target_activity",
                "transition_frequency",
                "avg_transition_minutes",
            ]
        )

    working = events.copy()
    working["_event_order"] = range(len(working))
    working["activity"] = working["activity"].fillna(MISSING_ACTIVITY_LABEL).astype(str)
    ordered = working.sort_values(
        ["case_id", "timestamp", "_event_order"], na_position="last"
    ).copy()
    ordered["target_activity"] = ordered.groupby("case_id")["activity"].shift(-1)
    ordered["target_timestamp"] = ordered.groupby("case_id")["timestamp"].shift(-1)
    ordered["transition_minutes"] = (
        ordered["target_timestamp"] - ordered["timestamp"]
    ).dt.total_seconds() / 60

    transitions = ordered.dropna(subset=["target_activity"]).copy()
    grouped = (
        transitions.groupby(["activity", "target_activity"], dropna=False)
        .agg(
            transition_frequency=("target_activity", "size"),
            avg_transition_minutes=("transition_minutes", "mean"),
        )
        .reset_index()
        .rename(columns={"activity": "source_activity"})
    )

    filtered = grouped[grouped["transition_frequency"] >= min_edge_frequency].copy()
    filtered = filtered.sort_values(
        ["transition_frequency", "source_activity", "target_activity"],
        ascending=[False, True, True],
    )
    if top_n_edges is not None and top_n_edges > 0:
        filtered = filtered.head(int(top_n_edges))
    filtered["avg_transition_minutes"] = filtered["avg_transition_minutes"].round(2)
    return filtered.reset_index(drop=True)


def _build_graphviz_dot(
    edges: pd.DataFrame,
    case_group: CaseSubset,
    layout_direction: LayoutDirection,
    visual_mode: VisualMode,
    color_edges_by_avg_time: bool,
    edge_label_mode: EdgeLabelMode,
    optimize_for_density: bool,
) -> str:
    density_level = _graph_density_level(edges) if optimize_for_density else "normal"
    effective_label_mode = _effective_edge_label_mode(
        requested=edge_label_mode,
        density_level=density_level,
    )
    style = _graphviz_style(density_level)

    title = f"DFG ({case_group}, {visual_mode})"
    lines = [
        "digraph DFG {",
        f"  rankdir={layout_direction};",
        f"  graph [overlap=false, splines=true, concentrate=true, pad={style['pad']}, margin={style['margin']}, size=\"{style['size']}\"];",
        f"  graph [ranksep={style['rank_sep']}, nodesep={style['node_sep']}];",
        f'  labelloc="t"; label="{title}";',
        f'  node [shape=box, style="rounded,filled", fillcolor="#F7F7F7", fontsize={style["node_font_size"]}];',
    ]
    edge_colors = _edge_colors_from_avg_time(edges) if color_edges_by_avg_time else {}
    label_budget = _label_budget(len(edges), density_level)
    for edge_rank, (_, row) in enumerate(edges.iterrows()):
        source = _escape_label(str(row["source_activity"]))
        target = _escape_label(str(row["target_activity"]))
        freq = int(row["transition_frequency"])
        avg_min = row["avg_transition_minutes"]
        label = _edge_label(
            edge_rank=edge_rank,
            label_budget=label_budget,
            effective_label_mode=effective_label_mode,
            frequency=freq,
            avg_transition_minutes=avg_min,
        )
        penwidth = max(1.0, min(6.0, 1.0 + (freq / 2.0)))
        edge_key = (source, target)
        color = edge_colors.get(edge_key, "#666666")
        lines.append(
            f'  "{source}" -> "{target}" [label="{label}", penwidth={penwidth:.2f}, color="{color}", fontsize={style["edge_font_size"]}];'
        )
    lines.append("}")
    return "\n".join(lines)


def _graphviz_style(
    density_level: Literal["normal", "dense", "very_dense"],
) -> dict[str, str | int]:
    dense_graph = density_level != "normal"
    return {
        "node_font_size": 8 if density_level == "very_dense" else 9 if dense_graph else 10,
        "edge_font_size": 7 if density_level == "very_dense" else 8 if dense_graph else 9,
        "rank_sep": "0.30" if density_level == "very_dense" else "0.45" if dense_graph else "0.7",
        "node_sep": "0.18" if density_level == "very_dense" else "0.25" if dense_graph else "0.4",
        "pad": "0.01" if dense_graph else "0.05",
        "margin": "0.02" if dense_graph else "0.06",
        # Keep height compact for viewport fit; Graphviz will scale layout to size.
        "size": "10,7.2" if density_level == "very_dense" else "11,8" if dense_graph else "12,9",
    }


def _edge_label(
    edge_rank: int,
    label_budget: int,
    effective_label_mode: EdgeLabelMode,
    frequency: int,
    avg_transition_minutes: float,
) -> str:
    show_label = edge_rank < label_budget
    if effective_label_mode == "none" or not show_label:
        return ""
    if effective_label_mode == "frequency_only" or pd.isna(avg_transition_minutes):
        return f"{frequency}"
    return f"{frequency} | {float(avg_transition_minutes):.1f}m"


def _effective_edge_label_mode(
    requested: EdgeLabelMode, density_level: Literal["normal", "dense", "very_dense"]
) -> EdgeLabelMode:
    if density_level == "normal":
        return requested
    if density_level == "dense" and requested == "full":
        return "frequency_only"
    if density_level == "very_dense" and requested != "none":
        return "frequency_only"
    return requested


def _graph_density_level(edges: pd.DataFrame) -> Literal["normal", "dense", "very_dense"]:
    if edges.empty:
        return "normal"
    node_count = int(
        pd.unique(
            pd.concat([edges["source_activity"], edges["target_activity"]], ignore_index=True)
        ).size
    )
    edge_count = int(len(edges))
    if node_count > 24 or edge_count > 50:
        return "very_dense"
    if node_count > 15 or edge_count > 30:
        return "dense"
    return "normal"


def _label_budget(edge_count: int, density_level: Literal["normal", "dense", "very_dense"]) -> int:
    if density_level == "very_dense":
        return min(edge_count, 18)
    if density_level == "dense":
        return min(edge_count, 28)
    return edge_count


def _edge_colors_from_avg_time(edges: pd.DataFrame) -> dict[tuple[str, str], str]:
    if edges.empty:
        return {}

    valid = edges.dropna(subset=["avg_transition_minutes"]).copy()
    if valid.empty:
        return {}

    min_time = float(valid["avg_transition_minutes"].min())
    max_time = float(valid["avg_transition_minutes"].max())

    def _color_for(avg_time: float) -> str:
        if max_time <= min_time:
            ratio = 0.5
        else:
            ratio = (avg_time - min_time) / (max_time - min_time)
        # Green (faster) -> Red (slower) gradient.
        red = int(80 + ratio * 175)
        green = int(170 - ratio * 130)
        blue = int(100 - ratio * 60)
        return f"#{red:02x}{green:02x}{blue:02x}"

    mapping: dict[tuple[str, str], str] = {}
    for _, row in edges.iterrows():
        source = _escape_label(str(row["source_activity"]))
        target = _escape_label(str(row["target_activity"]))
        avg = row["avg_transition_minutes"]
        if pd.isna(avg):
            mapping[(source, target)] = "#888888"
        else:
            mapping[(source, target)] = _color_for(float(avg))
    return mapping


def _escape_label(value: str) -> str:
    return value.replace('"', '\\"')


def _transition_label(row: pd.Series) -> str:
    return f"{row['source_activity']} -> {row['target_activity']}"
