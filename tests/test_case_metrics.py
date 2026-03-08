"""Basic tests for case-level metrics computation."""

from pathlib import Path

import pandas as pd

from src.process_investigation_copilot.analysis.case_metrics import compute_case_metrics


def test_compute_case_metrics_on_sample_csv() -> None:
    sample_path = Path("data/sample_event_log.csv")
    event_log = pd.read_csv(sample_path)
    event_log["timestamp"] = pd.to_datetime(
        event_log["timestamp"], errors="coerce", format="mixed"
    )

    result = compute_case_metrics(event_log)

    expected_columns = {
        "case_id",
        "start_time",
        "end_time",
        "duration_hours",
        "event_count",
        "unique_activity_count",
        "rework_event_count",
        "has_rework",
    }
    assert expected_columns.issubset(result.columns)

    # In bundled sample data, case C-002 repeats "Review" once.
    c002 = result[result["case_id"] == "C-002"].iloc[0]
    assert int(c002["event_count"]) == 5
    assert int(c002["unique_activity_count"]) == 4
    assert int(c002["rework_event_count"]) == 1
    assert bool(c002["has_rework"]) is True


def test_compute_case_metrics_excludes_blank_case_ids() -> None:
    event_log = pd.DataFrame(
        {
            "case_id": ["C-1", "", "   ", None],
            "activity": ["A", "B", "C", "D"],
            "timestamp": [
                "2026-01-01T10:00:00",
                "2026-01-01T11:00:00",
                "2026-01-01T12:00:00",
                "2026-01-01T13:00:00",
            ],
        }
    )
    result = compute_case_metrics(event_log)
    assert result["case_id"].tolist() == ["C-1"]
