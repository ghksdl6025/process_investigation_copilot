"""Slow-case detection and slow-vs-normal comparison utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src.process_investigation_copilot.analysis.case_metrics import compute_case_metrics


@dataclass
class SlowCaseComparisonResult:
    """Container for slow-case detection and comparison outputs."""

    case_metrics_with_flags: pd.DataFrame
    summary: dict[str, float | int]
    activity_comparison: pd.DataFrame
    rework_comparison: pd.DataFrame
    variant_comparison: pd.DataFrame


def build_slow_case_comparison(
    event_log: pd.DataFrame, case_metrics: pd.DataFrame | None = None
) -> SlowCaseComparisonResult:
    """Compute slow-case flags and compare slow vs non-slow groups.

    When `case_metrics` is provided, it is reused to avoid recomputation.
    """
    case_metrics = (
        case_metrics.copy()
        if case_metrics is not None
        else compute_case_metrics(event_log)
    )
    case_metrics_with_flags, threshold = _flag_slow_cases(case_metrics)

    events_with_group = build_slow_case_event_population(
        event_log=event_log,
        case_metrics_with_flags=case_metrics_with_flags,
    )

    summary = {
        "slow_case_count": int(case_metrics_with_flags["is_slow_case"].sum()),
        "total_case_count": int(len(case_metrics_with_flags)),
        "slow_case_ratio": float(
            case_metrics_with_flags["is_slow_case"].mean()
            if len(case_metrics_with_flags) > 0
            else 0.0
        ),
        "slow_case_duration_threshold_hours": float(threshold)
        if threshold is not None
        else 0.0,
    }

    return SlowCaseComparisonResult(
        case_metrics_with_flags=case_metrics_with_flags,
        summary=summary,
        activity_comparison=_activity_frequency_comparison(events_with_group),
        rework_comparison=_rework_comparison(case_metrics_with_flags),
        variant_comparison=_variant_distribution_comparison(events_with_group),
    )


def build_slow_case_event_population(
    event_log: pd.DataFrame, case_metrics_with_flags: pd.DataFrame
) -> pd.DataFrame:
    """Return event rows aligned to analyzed cases with slow/non-slow group labels."""
    analyzed_case_ids = set(case_metrics_with_flags["case_id"].tolist())
    slow_case_ids = set(
        case_metrics_with_flags.loc[case_metrics_with_flags["is_slow_case"], "case_id"]
    )
    return _attach_slow_group(
        event_log=event_log,
        analyzed_case_ids=analyzed_case_ids,
        slow_case_ids=slow_case_ids,
    )


def _flag_slow_cases(case_metrics: pd.DataFrame) -> tuple[pd.DataFrame, float | None]:
    """Flag slow cases as top 10% of valid-duration cases by rank.

    Slow-case selection is rank-based (`nlargest(top_k)`), where
    `top_k = ceil(10% of valid-duration cases)` with a minimum of 1.
    The reported threshold is descriptive (minimum duration among selected slow
    cases) and not a strict `>= threshold` inclusion rule when ties occur.
    """
    flagged = case_metrics.copy()
    flagged["is_slow_case"] = False

    valid_duration_mask = flagged["duration_hours"].notna()
    valid_durations = flagged.loc[valid_duration_mask, ["case_id", "duration_hours"]]
    if len(valid_durations) == 0:
        return flagged, None

    top_k = max(1, math.ceil(len(valid_durations) * 0.10))
    slow_candidates = valid_durations.nlargest(top_k, "duration_hours")
    slow_case_ids = set(slow_candidates["case_id"].tolist())
    flagged["is_slow_case"] = flagged["case_id"].isin(slow_case_ids)
    threshold = float(slow_candidates["duration_hours"].min())
    return flagged, threshold


def _attach_slow_group(
    event_log: pd.DataFrame, analyzed_case_ids: set, slow_case_ids: set
) -> pd.DataFrame:
    # Align event-level comparison population with analyzed case-level population.
    # This excludes events with missing/unseen case_id values from comparison views.
    grouped = event_log[event_log["case_id"].isin(analyzed_case_ids)].copy()
    grouped["case_group"] = grouped["case_id"].apply(
        lambda case_id: "slow" if case_id in slow_case_ids else "non_slow"
    )
    grouped["timestamp"] = pd.to_datetime(
        grouped["timestamp"], errors="coerce", format="mixed"
    )
    return grouped


def _activity_frequency_comparison(events_with_group: pd.DataFrame) -> pd.DataFrame:
    # Keep missing activities explicit in output instead of silently dropping them.
    with_activity = events_with_group.copy()
    with_activity["activity_label"] = with_activity["activity"].fillna(
        "<missing_activity>"
    )
    counts = (
        with_activity.groupby(["activity_label", "case_group"], dropna=False)
        .size()
        .reset_index(name="event_count")
    )
    pivoted = (
        counts.pivot(index="activity_label", columns="case_group", values="event_count")
        .fillna(0)
        .reset_index()
    )
    if "slow" not in pivoted.columns:
        pivoted["slow"] = 0
    if "non_slow" not in pivoted.columns:
        pivoted["non_slow"] = 0

    result = pivoted.rename(
        columns={
            "activity_label": "activity",
            "slow": "slow_event_count",
            "non_slow": "non_slow_event_count",
        }
    )
    slow_total = float(result["slow_event_count"].sum())
    non_slow_total = float(result["non_slow_event_count"].sum())
    result["slow_event_share"] = (
        result["slow_event_count"] / slow_total if slow_total > 0 else 0.0
    )
    result["non_slow_event_share"] = (
        result["non_slow_event_count"] / non_slow_total if non_slow_total > 0 else 0.0
    )
    result["share_delta"] = result["slow_event_share"] - result["non_slow_event_share"]
    return result.sort_values(
        ["share_delta", "slow_event_count"], ascending=[False, False]
    ).reset_index(drop=True)


def _rework_comparison(case_metrics_with_flags: pd.DataFrame) -> pd.DataFrame:
    rework = (
        case_metrics_with_flags.groupby("is_slow_case", dropna=False)
        .agg(
            case_count=("case_id", "size"),
            avg_rework_event_count=("rework_event_count", "mean"),
            rework_case_ratio=("has_rework", "mean"),
            avg_duration_hours=("duration_hours", "mean"),
        )
        .reset_index()
    )
    rework["case_group"] = rework["is_slow_case"].map(
        {True: "slow", False: "non_slow"}
    )
    ordered = [
        "case_group",
        "case_count",
        "avg_duration_hours",
        "avg_rework_event_count",
        "rework_case_ratio",
    ]
    return rework[ordered].sort_values("case_group").reset_index(drop=True)


def _variant_distribution_comparison(events_with_group: pd.DataFrame) -> pd.DataFrame:
    # Variant = ordered sequence of activities within a case.
    ordered_events = events_with_group.sort_values(
        ["case_id", "timestamp"], ascending=[True, True], na_position="last"
    )
    variants = (
        ordered_events.groupby(["case_id", "case_group"], dropna=False)["activity"]
        .apply(lambda series: " > ".join(series.fillna("<missing>").astype(str).tolist()))
        .reset_index(name="variant")
    )
    distribution = (
        variants.groupby(["variant", "case_group"], dropna=False)
        .size()
        .reset_index(name="case_count")
    )
    pivoted = (
        distribution.pivot(index="variant", columns="case_group", values="case_count")
        .fillna(0)
        .reset_index()
    )
    if "slow" not in pivoted.columns:
        pivoted["slow"] = 0
    if "non_slow" not in pivoted.columns:
        pivoted["non_slow"] = 0

    result = pivoted.rename(
        columns={"slow": "slow_case_count", "non_slow": "non_slow_case_count"}
    )
    result["total_case_count"] = (
        result["slow_case_count"] + result["non_slow_case_count"]
    )
    return result.sort_values(
        ["total_case_count", "slow_case_count"], ascending=[False, False]
    ).reset_index(drop=True)
