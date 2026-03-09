"""Activity-level delay comparison between recent and previous periods."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.process_investigation_copilot.analysis.period_comparison import (
    compare_period_case_performance,
)


@dataclass
class ActivityDelayComparisonResult:
    """Structured activity-level delay comparison output."""

    is_comparable: bool
    message: str
    strategy: str
    ranked_table: pd.DataFrame
    top_delayed_activities: list[dict[str, Any]]
    methodology_notes: list[str]
    uncertainty_flags: list[str]


def compare_activity_delay_between_periods(
    event_log: pd.DataFrame,
    case_metrics: pd.DataFrame,
    min_activity_occurrences: int = 2,
    drop_consecutive_duplicates: bool = True,
) -> ActivityDelayComparisonResult:
    """Compare activity delay proxy metrics between recent and previous periods.

    Proxy definition:
    - For each event, use elapsed time from previous event in the same case.
    - Attribute that elapsed time to the current activity.
    """
    period_result = compare_period_case_performance(case_metrics=case_metrics)
    if not period_result.is_comparable:
        return ActivityDelayComparisonResult(
            is_comparable=False,
            message=period_result.message,
            strategy=period_result.strategy,
            ranked_table=_empty_ranked_table(),
            top_delayed_activities=[],
            methodology_notes=_methodology_notes(drop_consecutive_duplicates),
            uncertainty_flags=["Period comparison is not currently feasible."],
        )

    recent_case_ids = set(period_result.recent_case_ids)
    previous_case_ids = set(period_result.previous_case_ids)
    if not recent_case_ids or not previous_case_ids:
        return ActivityDelayComparisonResult(
            is_comparable=False,
            message="Could not resolve period case IDs for activity comparison.",
            strategy=period_result.strategy,
            ranked_table=_empty_ranked_table(),
            top_delayed_activities=[],
            methodology_notes=_methodology_notes(drop_consecutive_duplicates),
            uncertainty_flags=["Missing period case IDs."],
        )

    prepared = _prepare_events_for_delay_proxy(
        event_log, drop_consecutive_duplicates=drop_consecutive_duplicates
    )
    if prepared.empty:
        return ActivityDelayComparisonResult(
            is_comparable=False,
            message="No valid events available for activity delay comparison.",
            strategy=period_result.strategy,
            ranked_table=_empty_ranked_table(),
            top_delayed_activities=[],
            methodology_notes=_methodology_notes(drop_consecutive_duplicates),
            uncertainty_flags=["No valid event timestamps after cleaning."],
        )

    previous_stats = _activity_period_stats(prepared, case_ids=previous_case_ids).rename(
        columns={
            "avg_proxy_minutes": "previous_avg_proxy_minutes",
            "median_proxy_minutes": "previous_median_proxy_minutes",
            "occurrence_count": "previous_occurrence_count",
            "affected_case_count": "previous_affected_case_count",
        }
    )
    recent_stats = _activity_period_stats(prepared, case_ids=recent_case_ids).rename(
        columns={
            "avg_proxy_minutes": "recent_avg_proxy_minutes",
            "median_proxy_minutes": "recent_median_proxy_minutes",
            "occurrence_count": "recent_occurrence_count",
            "affected_case_count": "recent_affected_case_count",
        }
    )

    merged = previous_stats.merge(recent_stats, on="activity", how="outer")
    ranked = _rank_activity_differences(
        merged,
        min_activity_occurrences=min_activity_occurrences,
    )

    top_delayed = ranked.head(5).to_dict(orient="records")
    uncertainty = _uncertainty_flags(ranked, min_activity_occurrences=min_activity_occurrences)
    return ActivityDelayComparisonResult(
        is_comparable=True,
        message="Computed activity delay proxy differences between recent and previous periods.",
        strategy=period_result.strategy,
        ranked_table=ranked,
        top_delayed_activities=top_delayed,
        methodology_notes=_methodology_notes(drop_consecutive_duplicates),
        uncertainty_flags=uncertainty,
    )


def _prepare_events_for_delay_proxy(
    event_log: pd.DataFrame, drop_consecutive_duplicates: bool
) -> pd.DataFrame:
    events = event_log.copy()
    events["case_id"] = events["case_id"].astype(str).str.strip()
    events = events[(events["case_id"] != "") & events["case_id"].notna()].copy()
    events["activity"] = events["activity"].fillna("<missing_activity>").astype(str)
    events["timestamp"] = pd.to_datetime(events["timestamp"], errors="coerce", format="mixed")
    events = events.dropna(subset=["timestamp"]).copy()
    events["_event_order"] = range(len(events))
    events = events.sort_values(["case_id", "timestamp", "_event_order"], na_position="last")

    events["prev_activity"] = events.groupby("case_id")["activity"].shift(1)
    if drop_consecutive_duplicates:
        duplicate_step = events["activity"] == events["prev_activity"]
        events = events[~duplicate_step].copy()

    events["prev_timestamp"] = events.groupby("case_id")["timestamp"].shift(1)
    events["proxy_minutes"] = (
        events["timestamp"] - events["prev_timestamp"]
    ).dt.total_seconds() / 60
    events = events[events["proxy_minutes"].notna()].copy()
    return events


def _activity_period_stats(events: pd.DataFrame, case_ids: set[str]) -> pd.DataFrame:
    period_events = events[events["case_id"].isin(case_ids)].copy()
    if period_events.empty:
        return pd.DataFrame(
            columns=[
                "activity",
                "avg_proxy_minutes",
                "median_proxy_minutes",
                "occurrence_count",
                "affected_case_count",
            ]
        )

    return (
        period_events.groupby("activity", dropna=False)
        .agg(
            avg_proxy_minutes=("proxy_minutes", "mean"),
            median_proxy_minutes=("proxy_minutes", "median"),
            occurrence_count=("proxy_minutes", "size"),
            affected_case_count=("case_id", "nunique"),
        )
        .reset_index()
    )


def _rank_activity_differences(
    merged: pd.DataFrame, min_activity_occurrences: int
) -> pd.DataFrame:
    ranked = merged.copy()
    for column in [
        "previous_occurrence_count",
        "recent_occurrence_count",
        "previous_affected_case_count",
        "recent_affected_case_count",
    ]:
        ranked[column] = ranked[column].fillna(0).astype(int)

    ranked["recent_avg_proxy_minutes"] = pd.to_numeric(
        ranked["recent_avg_proxy_minutes"], errors="coerce"
    )
    ranked["previous_avg_proxy_minutes"] = pd.to_numeric(
        ranked["previous_avg_proxy_minutes"], errors="coerce"
    )
    ranked["absolute_increase_minutes"] = (
        ranked["recent_avg_proxy_minutes"] - ranked["previous_avg_proxy_minutes"]
    )
    ranked["percent_increase"] = ranked.apply(
        lambda row: (
            None
            if pd.isna(row["previous_avg_proxy_minutes"]) or row["previous_avg_proxy_minutes"] == 0
            else ((row["absolute_increase_minutes"] / row["previous_avg_proxy_minutes"]) * 100.0)
        ),
        axis=1,
    )
    ranked["support_volume"] = (
        ranked["recent_occurrence_count"] + ranked["previous_occurrence_count"]
    )
    ranked["period_presence"] = ranked.apply(
        lambda row: (
            "both"
            if row["recent_occurrence_count"] > 0 and row["previous_occurrence_count"] > 0
            else "recent_only"
            if row["recent_occurrence_count"] > 0
            else "previous_only"
        ),
        axis=1,
    )
    ranked["low_support_flag"] = ranked["support_volume"] < min_activity_occurrences

    ranked = ranked.sort_values(
        ["absolute_increase_minutes", "support_volume"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)
    return ranked[
        [
            "activity",
            "recent_avg_proxy_minutes",
            "previous_avg_proxy_minutes",
            "absolute_increase_minutes",
            "percent_increase",
            "recent_median_proxy_minutes",
            "previous_median_proxy_minutes",
            "recent_occurrence_count",
            "previous_occurrence_count",
            "recent_affected_case_count",
            "previous_affected_case_count",
            "support_volume",
            "period_presence",
            "low_support_flag",
        ]
    ]


def _uncertainty_flags(
    ranked_table: pd.DataFrame, min_activity_occurrences: int
) -> list[str]:
    flags: list[str] = []
    if ranked_table.empty:
        flags.append("No comparable activity transitions were found.")
        return flags
    if (ranked_table["period_presence"] != "both").any():
        flags.append("Some activities appear in only one period.")
    if (ranked_table["low_support_flag"]).any():
        flags.append(
            f"Some activities have low support volume (< {min_activity_occurrences} occurrences)."
        )
    return flags


def _methodology_notes(drop_consecutive_duplicates: bool) -> list[str]:
    duplicate_note = (
        "Consecutive duplicate activities per case are excluded before proxy calculation."
        if drop_consecutive_duplicates
        else "Consecutive duplicate activities are retained."
    )
    return [
        "Delay proxy uses elapsed minutes from previous event to current event within the same case.",
        "Proxy is descriptive and may reflect waiting + handoff + service effects combined.",
        duplicate_note,
    ]


def _empty_ranked_table() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "activity",
            "recent_avg_proxy_minutes",
            "previous_avg_proxy_minutes",
            "absolute_increase_minutes",
            "percent_increase",
            "recent_median_proxy_minutes",
            "previous_median_proxy_minutes",
            "recent_occurrence_count",
            "previous_occurrence_count",
            "recent_affected_case_count",
            "previous_affected_case_count",
            "support_volume",
            "period_presence",
            "low_support_flag",
        ]
    )
