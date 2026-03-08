"""Core dashboard computations (structured metrics/tables, no narrative text)."""

from __future__ import annotations

import pandas as pd


def build_dashboard_overview_metrics(event_log: pd.DataFrame) -> dict[str, int]:
    """Return top-level dashboard KPIs from the raw prepared event log.

    Population basis:
    - Input should be the prepared uploaded event log (post-mapping/parsing).
    - This function intentionally does not use case-level or slow-case outputs.
    """
    return {
        "events": int(len(event_log)),
        "cases": int(event_log["case_id"].nunique()),
        "activities": int(event_log["activity"].nunique()),
    }


def build_dashboard_activity_frequency_table(event_log: pd.DataFrame) -> pd.DataFrame:
    """Return an activity-frequency table from the raw prepared event log.

    Population basis:
    - Computed directly from event rows in `event_log`.
    - Use `case_metrics.py` or `slow_case_analysis.py` for case-level/slow-case views.
    """
    return (
        event_log.groupby("activity", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )


def build_summary_metrics(event_log: pd.DataFrame) -> dict[str, int]:
    """Backward-compatible wrapper for dashboard overview metrics."""
    return build_dashboard_overview_metrics(event_log)


def activity_frequency(event_log: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible wrapper for activity frequency table."""
    return build_dashboard_activity_frequency_table(event_log)
