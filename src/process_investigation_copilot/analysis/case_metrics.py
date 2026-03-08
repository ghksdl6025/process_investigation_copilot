"""Reusable case-level metrics for process investigation."""

from __future__ import annotations

import pandas as pd


def compute_case_metrics(event_log: pd.DataFrame) -> pd.DataFrame:
    """Transform an event log into case-level metrics.

    Handling rules:
    - Rows with missing `case_id` are excluded from case-level aggregation.
    - `timestamp` is parsed with coercion; invalid timestamps become `NaT`.
      Duration is computed from available valid timestamps per case.
    - Rework is computed only from non-missing activity values.
    """
    working = event_log.copy()
    # Exclude rows that cannot be assigned to a concrete case.
    valid_case_mask = _valid_case_id_mask(working["case_id"])
    working = working[valid_case_mask].copy()
    working["timestamp"] = pd.to_datetime(
        working["timestamp"], errors="coerce", format="mixed"
    )

    case_metrics = (
        working.groupby("case_id", dropna=False)
        .agg(
            start_time=("timestamp", "min"),
            end_time=("timestamp", "max"),
            event_count=("case_id", "size"),
            unique_activity_count=("activity", lambda series: series.dropna().nunique()),
        )
        .reset_index()
    )

    case_metrics["duration_hours"] = (
        case_metrics["end_time"] - case_metrics["start_time"]
    ).dt.total_seconds() / 3600

    # Rework is based only on valid activity labels.
    rework_base = working.dropna(subset=["activity"]).copy()
    rework_counts = (
        rework_base.groupby(["case_id", "activity"], dropna=False)
        .size()
        .reset_index(name="activity_occurrence_count")
    )
    rework_counts["rework_events"] = (
        rework_counts["activity_occurrence_count"] - 1
    ).clip(lower=0)
    rework_per_case = (
        rework_counts.groupby("case_id", dropna=False)["rework_events"].sum().reset_index()
    )

    case_metrics = case_metrics.merge(
        rework_per_case, on="case_id", how="left", validate="one_to_one"
    )
    case_metrics["rework_event_count"] = (
        case_metrics["rework_events"].fillna(0).astype(int)
    )
    case_metrics["has_rework"] = case_metrics["rework_event_count"] > 0
    case_metrics = case_metrics.drop(columns=["rework_events"])

    ordered_columns = [
        "case_id",
        "start_time",
        "end_time",
        "duration_hours",
        "event_count",
        "unique_activity_count",
        "rework_event_count",
        "has_rework",
    ]
    return case_metrics[ordered_columns].sort_values("case_id").reset_index(drop=True)


def _valid_case_id_mask(case_ids: pd.Series) -> pd.Series:
    as_text = case_ids.astype(str).str.strip()
    return case_ids.notna() & as_text.ne("")
