"""Tests for structured investigation summary payload builder."""

from pathlib import Path

import pandas as pd

from src.process_investigation_copilot.analysis.activity_delay_analysis import (
    compare_activity_delay_between_periods,
)
from src.process_investigation_copilot.analysis.case_metrics import compute_case_metrics
from src.process_investigation_copilot.analysis.investigation_summary import (
    build_investigation_summary_payload,
)
from src.process_investigation_copilot.analysis.period_comparison import (
    compare_period_case_performance,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    build_slow_case_comparison,
)


def test_build_investigation_summary_payload_shape() -> None:
    event_log = pd.read_csv(Path("data/sample_event_log.csv"))
    case_metrics = compute_case_metrics(event_log)
    period_result = compare_period_case_performance(case_metrics, min_cases_per_period=1)
    activity_delay = compare_activity_delay_between_periods(
        event_log=event_log, case_metrics=case_metrics, min_activity_occurrences=1
    )
    slow_case = build_slow_case_comparison(event_log, case_metrics=case_metrics)

    payload = build_investigation_summary_payload(
        period_result=period_result,
        activity_delay_result=activity_delay,
        slow_case_result=slow_case,
    )
    assert "is_comparable" in payload.overall_change_summary
    assert isinstance(payload.top_suspicious_factors, list)
    assert isinstance(payload.activity_delay_findings, dict)
    assert isinstance(payload.slow_case_findings, dict)
    assert isinstance(payload.variant_or_rework_findings, dict)
    assert isinstance(payload.limitations, list)


def test_build_investigation_summary_payload_cannot_determine() -> None:
    event_log = pd.DataFrame(
        [
            {"case_id": "C1", "activity": "A", "timestamp": "2026-03-01T00:00:00"},
            {"case_id": "C1", "activity": "B", "timestamp": "2026-03-01T00:05:00"},
        ]
    )
    case_metrics = compute_case_metrics(event_log)
    period_result = compare_period_case_performance(case_metrics, min_cases_per_period=2)
    activity_delay = compare_activity_delay_between_periods(event_log=event_log, case_metrics=case_metrics)
    slow_case = build_slow_case_comparison(event_log, case_metrics=case_metrics)
    payload = build_investigation_summary_payload(
        period_result=period_result,
        activity_delay_result=activity_delay,
        slow_case_result=slow_case,
    )
    assert payload.cannot_determine is True
    assert "insufficient" in " ".join(payload.limitations).lower()
