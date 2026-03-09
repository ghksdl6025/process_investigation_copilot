"""Tests for question routing and structured investigation panel outputs."""

from pathlib import Path

import pandas as pd

from src.process_investigation_copilot.analysis.investigation_panel import (
    build_core_scenario_result,
    build_investigation_panel_result,
    classify_question_type,
)


def _sample_event_log() -> pd.DataFrame:
    return pd.read_csv(Path("data/sample_event_log.csv"))


def test_classify_question_type_routes_supported_queries() -> None:
    assert classify_question_type("Why did processing time increase this month?") == "why_slower"
    assert classify_question_type("Compare recent vs previous period performance") == "period_comparison"
    assert classify_question_type("Show bottleneck transitions in the flow") == "bottleneck"
    assert classify_question_type("Which variant is linked to slow cases?") == "variant"
    assert classify_question_type("How are slow cases different from normal cases?") == "slow_vs_normal"


def test_investigation_panel_result_for_why_slower_contains_evidence() -> None:
    result = build_investigation_panel_result(
        event_log=_sample_event_log(),
        question="Why did processing time increase this month?",
    )

    assert result.is_supported is True
    assert result.question_type == "why_slower"
    assert len(result.answer_blocks) == 4
    assert "Activity Delay Comparison" in result.evidence_tables
    assert "Period Trend" in result.evidence_charts
    assert "avg_duration_hours" in result.metrics_used
    assert len(result.follow_up_questions) >= 1
    assert result.trace["question_type"] == "why_slower"
    assert "build_grounded_explanation" in result.trace["analysis_functions_executed"]
    assert len(result.trace["evidence_used"]) >= 1


def test_core_scenario_runner_uses_benchmark_question() -> None:
    result = build_core_scenario_result(event_log=_sample_event_log())
    assert result.question == "Why did processing time increase this month?"
    assert result.question_type == "why_slower"
    assert result.is_supported is True
    assert "Activity Delay Comparison" in result.evidence_tables


def test_investigation_panel_result_for_bottleneck_has_transition_metrics() -> None:
    result = build_investigation_panel_result(
        event_log=_sample_event_log(),
        question="Where are the bottlenecks?",
    )

    assert result.is_supported is True
    assert result.question_type == "bottleneck"
    assert "Bottleneck Transition Table" in result.evidence_tables
    bottleneck_table = result.evidence_tables["Bottleneck Transition Table"]
    assert "transition_frequency" in bottleneck_table.columns
    assert "avg_transition_minutes" in bottleneck_table.columns
    assert "avg_transition_minutes" in result.metrics_used
    assert result.trace["selected_subset"] == "all"
    assert "build_directly_follows_graph" in result.trace["analysis_functions_executed"]


def test_investigation_panel_result_handles_unsupported_question() -> None:
    result = build_investigation_panel_result(
        event_log=_sample_event_log(),
        question="Write me a poem about process excellence.",
    )

    assert result.is_supported is False
    assert result.question_type == "unsupported"
    assert len(result.limitations) >= 1
    assert "not yet supported" in " ".join(result.limitations).lower()
    assert len(result.follow_up_questions) >= 1
    assert result.trace["question_type"] == "unsupported"


def test_why_slower_handles_insufficient_data_gracefully() -> None:
    tiny_event_log = pd.DataFrame(
        [
            {"case_id": "C1", "activity": "A", "timestamp": "2026-03-01T00:00:00"},
            {"case_id": "C1", "activity": "B", "timestamp": "2026-03-01T00:03:00"},
        ]
    )
    result = build_investigation_panel_result(
        event_log=tiny_event_log,
        question="Why did processing time increase this month?",
    )
    assert result.question_type == "why_slower"
    assert result.is_supported is True
    assert len(result.limitations) >= 1
    assert "insufficient" in " ".join(result.limitations).lower()


def test_unsupported_question_does_not_require_full_event_log_schema() -> None:
    minimal = pd.DataFrame([{"foo": 1}])
    result = build_investigation_panel_result(
        event_log=minimal,
        question="Tell me something unrelated",
    )
    assert result.question_type == "unsupported"
    assert result.is_supported is False
