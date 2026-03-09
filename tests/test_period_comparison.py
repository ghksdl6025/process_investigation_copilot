"""Tests for period-based case performance comparison."""

import pandas as pd

from src.process_investigation_copilot.analysis.period_comparison import (
    compare_period_case_performance,
)


def _case_metrics_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["start_time"] = pd.to_datetime(frame["start_time"], errors="coerce")
    frame["end_time"] = pd.to_datetime(frame["end_time"], errors="coerce")
    return frame


def test_period_comparison_prefers_monthly_complete_months() -> None:
    rows = []
    # Jan (previous complete): shorter durations
    for i in range(3):
        rows.append(
            {
                "case_id": f"JAN-{i}",
                "start_time": "2026-01-01T00:00:00",
                "end_time": f"2026-01-{10+i:02d}T00:00:00",
                "duration_hours": 20.0,
                "event_count": 4,
            }
        )
    # Feb (recent complete): longer durations
    for i in range(3):
        rows.append(
            {
                "case_id": f"FEB-{i}",
                "start_time": "2026-02-01T00:00:00",
                "end_time": f"2026-02-{10+i:02d}T00:00:00",
                "duration_hours": 40.0,
                "event_count": 5,
            }
        )
    # Mar (latest month, treated as incomplete and excluded from monthly pair)
    rows.append(
        {
            "case_id": "MAR-1",
            "start_time": "2026-03-01T00:00:00",
            "end_time": "2026-03-05T00:00:00",
            "duration_hours": 10.0,
            "event_count": 3,
        }
    )
    case_metrics = _case_metrics_frame(rows)
    result = compare_period_case_performance(case_metrics, min_cases_per_period=2)

    assert result.is_comparable is True
    assert result.strategy == "monthly_complete_months"
    assert result.processing_time_increased is True
    assert result.recent is not None and result.previous is not None
    assert result.recent.case_count == 3
    assert result.previous.case_count == 3


def test_period_comparison_falls_back_to_equal_windows() -> None:
    rows = []
    for i in range(8):
        rows.append(
            {
                "case_id": f"C-{i}",
                "start_time": "2026-03-01T00:00:00",
                "end_time": f"2026-03-{i+1:02d}T00:00:00",
                "duration_hours": float(i + 1),
                "event_count": 3 + (i % 2),
            }
        )
    case_metrics = _case_metrics_frame(rows)
    result = compare_period_case_performance(case_metrics, min_cases_per_period=2)

    assert result.is_comparable is True
    assert result.strategy == "equal_recent_windows"
    assert result.recent is not None and result.previous is not None
    assert result.recent.case_count == result.previous.case_count == 4


def test_period_comparison_handles_insufficient_data() -> None:
    case_metrics = _case_metrics_frame(
        [
            {
                "case_id": "ONE",
                "start_time": "2026-03-01T00:00:00",
                "end_time": "2026-03-02T00:00:00",
                "duration_hours": 10.0,
                "event_count": 3,
            }
        ]
    )
    result = compare_period_case_performance(case_metrics, min_cases_per_period=2)
    assert result.is_comparable is False
    assert result.processing_time_increased is None
