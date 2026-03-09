"""Investigation orchestration layer.

This module coordinates investigation flows and assembles structured outputs
for UI consumption. Core computations remain in dedicated modules (for example
`case_metrics.py` and `slow_case_analysis.py`), while this layer handles:
- composing outputs for an investigation view
- lightweight routing hooks for future question-driven analysis
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.process_investigation_copilot.analysis.activity_delay_analysis import (
    ActivityDelayComparisonResult,
    compare_activity_delay_between_periods,
)
from src.process_investigation_copilot.analysis.case_metrics import compute_case_metrics
from src.process_investigation_copilot.analysis.investigation_summary import (
    InvestigationSummaryPayload,
    build_investigation_summary_payload,
)
from src.process_investigation_copilot.analysis.explanation_formatter import (
    GroundedExplanation,
    build_grounded_explanation,
)
from src.process_investigation_copilot.analysis.period_comparison import (
    PeriodComparisonResult,
    compare_period_case_performance,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    SlowCaseComparisonResult,
    build_slow_case_comparison,
)


@dataclass
class InvestigationOutput:
    """Structured payload for investigation page rendering."""

    case_metrics: pd.DataFrame
    case_durations: pd.DataFrame
    flags: pd.DataFrame
    slow_case_comparison: SlowCaseComparisonResult
    period_comparison: PeriodComparisonResult
    activity_delay_comparison: ActivityDelayComparisonResult
    summary_payload: InvestigationSummaryPayload
    grounded_explanation: GroundedExplanation


def build_investigation_output(event_log: pd.DataFrame) -> InvestigationOutput:
    """Assemble default investigation outputs from reusable analysis modules."""
    case_metrics = compute_case_metrics(event_log)
    durations = case_metrics[
        ["case_id", "start_time", "end_time", "duration_hours"]
    ].sort_values("duration_hours", ascending=False)
    flags = _build_placeholder_flags(case_metrics)
    slow_case = build_slow_case_comparison(event_log, case_metrics=case_metrics)
    period_comparison = compare_period_case_performance(case_metrics=case_metrics)
    activity_delay = compare_activity_delay_between_periods(
        event_log=event_log, case_metrics=case_metrics
    )
    summary_payload = build_investigation_summary_payload(
        period_result=period_comparison,
        activity_delay_result=activity_delay,
        slow_case_result=slow_case,
    )
    grounded_explanation = build_grounded_explanation(summary_payload)
    return InvestigationOutput(
        case_metrics=case_metrics,
        case_durations=durations,
        flags=flags,
        slow_case_comparison=slow_case,
        period_comparison=period_comparison,
        activity_delay_comparison=activity_delay,
        summary_payload=summary_payload,
        grounded_explanation=grounded_explanation,
    )


def route_investigation_request(query: str) -> str:
    """Future-oriented routing hook (not a full routing engine)."""
    normalized = query.lower()
    if "slow" in normalized or "duration" in normalized:
        return "slow_case_analysis"
    if "rework" in normalized:
        return "case_rework_analysis"
    if "variant" in normalized:
        return "variant_analysis"
    return "default_overview"


def case_durations(event_log: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible accessor for case durations with minimal computation."""
    case_metrics = compute_case_metrics(event_log)
    return case_metrics[["case_id", "start_time", "end_time", "duration_hours"]].sort_values(
        "duration_hours", ascending=False
    )


def placeholder_flags(event_log: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible accessor for temporary heuristic flags."""
    return _build_placeholder_flags(compute_case_metrics(event_log))


def _build_placeholder_flags(case_metrics: pd.DataFrame) -> pd.DataFrame:
    # Temporary MVP heuristic logic; replace with richer flagging later.
    flags = case_metrics[
        ["case_id", "event_count", "unique_activity_count", "rework_event_count"]
    ].copy()
    flags["flag_reason"] = flags.apply(
        lambda row: (
            "Rework detected (placeholder)"
            if row["rework_event_count"] > 0
            else "High event volume (placeholder)"
            if row["event_count"] > 5
            else "None"
        ),
        axis=1,
    )
    return flags
