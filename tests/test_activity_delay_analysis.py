"""Tests for activity-level delay comparison between recent and previous periods."""

import pandas as pd

from src.process_investigation_copilot.analysis.activity_delay_analysis import (
    compare_activity_delay_between_periods,
)
from src.process_investigation_copilot.analysis.case_metrics import compute_case_metrics


def _build_activity_delay_event_log() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    # Previous window (first 4 cases): Review delay proxy ~10 minutes.
    for i in range(4):
        case_id = f"P-{i}"
        rows.extend(
            [
                {"case_id": case_id, "activity": "Register", "timestamp": f"2026-03-01T00:{i:02d}:00"},
                {"case_id": case_id, "activity": "Review", "timestamp": f"2026-03-01T00:{10+i:02d}:00"},
                {"case_id": case_id, "activity": "Approve", "timestamp": f"2026-03-01T00:{15+i:02d}:00"},
            ]
        )
    # Recent window (last 4 cases): Review delay proxy ~40 minutes.
    for i in range(4):
        case_id = f"R-{i}"
        rows.extend(
            [
                {"case_id": case_id, "activity": "Register", "timestamp": f"2026-03-02T00:{i:02d}:00"},
                {"case_id": case_id, "activity": "Review", "timestamp": f"2026-03-02T00:{40+i:02d}:00"},
                {"case_id": case_id, "activity": "Approve", "timestamp": f"2026-03-02T00:{45+i:02d}:00"},
            ]
        )
    return pd.DataFrame(rows)


def test_compare_activity_delay_between_periods_ranks_slowed_step() -> None:
    event_log = _build_activity_delay_event_log()
    case_metrics = compute_case_metrics(event_log)
    result = compare_activity_delay_between_periods(
        event_log=event_log,
        case_metrics=case_metrics,
        min_activity_occurrences=2,
    )

    assert result.is_comparable is True
    assert not result.ranked_table.empty
    top_activity = str(result.ranked_table.iloc[0]["activity"])
    assert top_activity == "Review"
    assert float(result.ranked_table.iloc[0]["absolute_increase_minutes"]) > 0
    assert len(result.top_delayed_activities) > 0


def test_compare_activity_delay_between_periods_insufficient_data() -> None:
    event_log = pd.DataFrame(
        [
            {"case_id": "ONE", "activity": "Register", "timestamp": "2026-03-01T00:00:00"},
            {"case_id": "ONE", "activity": "Review", "timestamp": "2026-03-01T00:10:00"},
        ]
    )
    case_metrics = compute_case_metrics(event_log)
    result = compare_activity_delay_between_periods(event_log=event_log, case_metrics=case_metrics)
    assert result.is_comparable is False
