"""User-facing narrative summaries.

This module converts already-computed structured analysis outputs into concise,
human-readable text. Core computations belong in modules like:
- `dashboard_metrics.py`
- `case_metrics.py`
- `slow_case_analysis.py`
"""

from __future__ import annotations

import pandas as pd


def summarize_slow_case_overview(
    slow_case_summary: dict[str, float | int],
) -> str:
    """Build a concise sentence from slow-case summary metrics."""
    slow_count = int(slow_case_summary.get("slow_case_count", 0))
    total_count = int(slow_case_summary.get("total_case_count", 0))
    ratio = float(slow_case_summary.get("slow_case_ratio", 0.0))
    threshold = float(slow_case_summary.get("slow_case_duration_threshold_hours", 0.0))
    if total_count == 0:
        return "No analyzable cases are available for slow-case profiling."

    return (
        f"{slow_count}/{total_count} cases ({ratio:.1%}) are flagged as slow "
        "using a top-10%-by-duration ranking; "
        f"{threshold:.2f}h is the descriptive cutoff among selected slow cases."
    )


def summarize_top_activity_shift(activity_comparison: pd.DataFrame) -> str:
    """Describe the largest activity-share shift between slow and non-slow cases."""
    if activity_comparison.empty:
        return "No activity event-share comparison is available."

    if "activity" not in activity_comparison.columns or "share_delta" not in activity_comparison.columns:
        return "Activity comparison data is incomplete."

    top_row = activity_comparison.iloc[0]
    activity = str(top_row["activity"])
    delta_value = top_row["share_delta"]
    if pd.isna(delta_value):
        return "Activity event-share differences are not available."

    delta = float(delta_value)
    direction = "higher" if delta >= 0 else "lower"
    return (
        f"Largest event-share shift: `{activity}` is {abs(delta):.1%} {direction} "
        "in slow-case events vs non-slow-case events."
    )
