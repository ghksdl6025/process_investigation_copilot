"""Period-based case performance comparison for investigation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class PeriodMetrics:
    """Summary metrics for a single period."""

    case_count: int
    avg_duration_hours: float | None
    median_duration_hours: float | None
    p90_duration_hours: float | None
    avg_event_count: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "avg_duration_hours": self.avg_duration_hours,
            "median_duration_hours": self.median_duration_hours,
            "p90_duration_hours": self.p90_duration_hours,
            "avg_event_count": self.avg_event_count,
        }


@dataclass
class PeriodComparisonResult:
    """Structured output for recent-vs-previous case performance comparison."""

    is_comparable: bool
    strategy: str
    message: str
    recent: PeriodMetrics | None
    previous: PeriodMetrics | None
    absolute_diff: dict[str, float | None]
    percent_diff: dict[str, float | None]
    processing_time_increased: bool | None
    trend_data: pd.DataFrame
    recent_case_ids: list[str]
    previous_case_ids: list[str]


def compare_period_case_performance(
    case_metrics: pd.DataFrame, min_cases_per_period: int = 3
) -> PeriodComparisonResult:
    """Compare recent vs previous case performance from case completion timestamps.

    Strategy:
    1) Prefer monthly comparison on complete months:
       most recent complete month vs the immediately previous complete month.
    2) If monthly is not feasible, fall back to two equal recent windows by
       case end timestamp order.
    """
    usable = _usable_case_rows(case_metrics)
    if len(usable) < max(2, min_cases_per_period * 2):
        return _insufficient_result(
            "insufficient_data",
            "Not enough completed cases to compare two periods.",
        )

    monthly_split = _monthly_period_split(usable, min_cases_per_period=min_cases_per_period)
    if monthly_split is not None:
        previous_df, recent_df, trend_data = monthly_split
        return _build_result(
            previous_df=previous_df,
            recent_df=recent_df,
            strategy="monthly_complete_months",
            message="Compared most recent complete month vs previous complete month.",
            trend_data=trend_data,
        )

    window_split = _equal_recent_windows_split(usable, min_cases_per_period=min_cases_per_period)
    if window_split is None:
        return _insufficient_result(
            "insufficient_data",
            "Could not form two stable periods with enough cases.",
        )

    previous_df, recent_df, trend_data = window_split
    return _build_result(
        previous_df=previous_df,
        recent_df=recent_df,
        strategy="equal_recent_windows",
        message="Monthly split not feasible; compared two equal recent windows.",
        trend_data=trend_data,
    )


def _usable_case_rows(case_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = case_metrics.copy()
    rows["end_time"] = pd.to_datetime(rows["end_time"], errors="coerce", format="mixed")
    rows = rows.dropna(subset=["end_time"]).copy()
    rows = rows[rows["duration_hours"].notna()].copy()
    return rows.sort_values("end_time").reset_index(drop=True)


def _monthly_period_split(
    usable: pd.DataFrame, min_cases_per_period: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    with_month = usable.copy()
    with_month["completion_month"] = with_month["end_time"].dt.to_period("M")
    months = sorted(with_month["completion_month"].dropna().unique())
    if len(months) < 3:
        return None

    latest_month = months[-1]
    complete_months = [month for month in months if month < latest_month]
    if len(complete_months) < 2:
        return None

    previous_month = complete_months[-2]
    recent_month = complete_months[-1]
    previous_df = with_month[with_month["completion_month"] == previous_month].copy()
    recent_df = with_month[with_month["completion_month"] == recent_month].copy()
    if len(previous_df) < min_cases_per_period or len(recent_df) < min_cases_per_period:
        return None

    monthly_trend = (
        with_month.groupby("completion_month")
        .agg(
            case_count=("case_id", "size"),
            avg_duration_hours=("duration_hours", "mean"),
            median_duration_hours=("duration_hours", "median"),
        )
        .reset_index()
    )
    monthly_trend["period"] = monthly_trend["completion_month"].astype(str)
    return previous_df, recent_df, monthly_trend[
        ["period", "case_count", "avg_duration_hours", "median_duration_hours"]
    ]


def _equal_recent_windows_split(
    usable: pd.DataFrame, min_cases_per_period: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None:
    ordered = usable.sort_values("end_time").reset_index(drop=True)
    window_size = len(ordered) // 2
    if window_size < min_cases_per_period:
        return None

    recent_df = ordered.tail(window_size).copy()
    previous_df = ordered.iloc[-(window_size * 2) : -window_size].copy()
    if len(previous_df) < min_cases_per_period or len(recent_df) < min_cases_per_period:
        return None

    trend_data = pd.DataFrame(
        [
            {
                "period": "previous_window",
                "case_count": int(len(previous_df)),
                "avg_duration_hours": float(previous_df["duration_hours"].mean()),
                "median_duration_hours": float(previous_df["duration_hours"].median()),
            },
            {
                "period": "recent_window",
                "case_count": int(len(recent_df)),
                "avg_duration_hours": float(recent_df["duration_hours"].mean()),
                "median_duration_hours": float(recent_df["duration_hours"].median()),
            },
        ]
    )
    return previous_df, recent_df, trend_data


def _period_metrics(period_df: pd.DataFrame) -> PeriodMetrics:
    return PeriodMetrics(
        case_count=int(len(period_df)),
        avg_duration_hours=_safe_float(period_df["duration_hours"].mean()),
        median_duration_hours=_safe_float(period_df["duration_hours"].median()),
        p90_duration_hours=_safe_float(period_df["duration_hours"].quantile(0.90)),
        avg_event_count=_safe_float(period_df["event_count"].mean()),
    )


def _build_result(
    previous_df: pd.DataFrame,
    recent_df: pd.DataFrame,
    strategy: str,
    message: str,
    trend_data: pd.DataFrame,
) -> PeriodComparisonResult:
    previous_metrics = _period_metrics(previous_df)
    recent_metrics = _period_metrics(recent_df)

    absolute_diff, percent_diff = _diffs(
        recent=recent_metrics.to_dict(),
        previous=previous_metrics.to_dict(),
    )
    increased = (
        absolute_diff["avg_duration_hours"] is not None
        and absolute_diff["avg_duration_hours"] > 0
    )
    return PeriodComparisonResult(
        is_comparable=True,
        strategy=strategy,
        message=message,
        recent=recent_metrics,
        previous=previous_metrics,
        absolute_diff=absolute_diff,
        percent_diff=percent_diff,
        processing_time_increased=increased,
        trend_data=trend_data,
        recent_case_ids=[str(value) for value in recent_df["case_id"].astype(str).tolist()],
        previous_case_ids=[str(value) for value in previous_df["case_id"].astype(str).tolist()],
    )


def _insufficient_result(strategy: str, message: str) -> PeriodComparisonResult:
    return PeriodComparisonResult(
        is_comparable=False,
        strategy=strategy,
        message=message,
        recent=None,
        previous=None,
        absolute_diff={},
        percent_diff={},
        processing_time_increased=None,
        trend_data=pd.DataFrame(
            columns=["period", "case_count", "avg_duration_hours", "median_duration_hours"]
        ),
        recent_case_ids=[],
        previous_case_ids=[],
    )


def _diffs(
    recent: dict[str, float | int | None], previous: dict[str, float | int | None]
) -> tuple[dict[str, float | None], dict[str, float | None]]:
    keys = [
        "case_count",
        "avg_duration_hours",
        "median_duration_hours",
        "p90_duration_hours",
        "avg_event_count",
    ]
    absolute: dict[str, float | None] = {}
    percent: dict[str, float | None] = {}

    for key in keys:
        recent_value = recent.get(key)
        previous_value = previous.get(key)
        if recent_value is None or previous_value is None:
            absolute[key] = None
            percent[key] = None
            continue

        abs_delta = float(recent_value) - float(previous_value)
        absolute[key] = abs_delta
        if float(previous_value) == 0:
            percent[key] = None
        else:
            percent[key] = (abs_delta / float(previous_value)) * 100.0

    return absolute, percent


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
