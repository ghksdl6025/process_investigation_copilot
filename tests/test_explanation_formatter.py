"""Tests for grounded explanation formatter."""

from src.process_investigation_copilot.analysis.explanation_formatter import (
    build_grounded_explanation,
)
from src.process_investigation_copilot.analysis.investigation_summary import (
    InvestigationSummaryPayload,
)


def test_build_grounded_explanation_with_evidence() -> None:
    payload = InvestigationSummaryPayload(
        overall_change_summary={
            "is_comparable": True,
            "processing_time_increased": True,
            "avg_duration_percent_change": 25.0,
            "message": "Compared periods.",
        },
        top_suspicious_factors=[
            {
                "title": "Activity delay increase: Review",
                "metric_evidence": {"absolute_increase_minutes": 15.0},
                "explanation": "Review appears slower.",
                "confidence": "medium",
                "limitation": "Proxy metric.",
            }
        ],
        activity_delay_findings={"top_delayed_activities": [{"activity": "Review"}]},
        slow_case_findings={},
        variant_or_rework_findings={"rework_case_ratio_delta": 0.1},
        limitations=["Findings are association-based."],
        cannot_determine=False,
    )
    explanation = build_grounded_explanation(payload)
    assert "increased" in explanation.observation.text.lower()
    assert "associated" in explanation.interpretation.text.lower() or "linked" in explanation.interpretation.text.lower()
    assert explanation.cannot_determine is False
    assert "observation" in explanation.to_dict()


def test_build_grounded_explanation_cannot_determine() -> None:
    payload = InvestigationSummaryPayload(
        overall_change_summary={
            "is_comparable": False,
            "processing_time_increased": None,
            "avg_duration_percent_change": None,
            "message": "Insufficient data.",
        },
        top_suspicious_factors=[],
        activity_delay_findings={"top_delayed_activities": []},
        slow_case_findings={},
        variant_or_rework_findings={},
        limitations=["Insufficient data."],
        cannot_determine=True,
    )
    explanation = build_grounded_explanation(payload)
    assert explanation.cannot_determine is True
    assert "not currently comparable" in explanation.observation.text.lower()
    assert "not sufficient" in explanation.interpretation.text.lower()
