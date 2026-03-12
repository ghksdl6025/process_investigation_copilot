from types import SimpleNamespace

from src.process_investigation_copilot.analysis.investigation_answer_composer import (
    compose_investigation_answer,
)


def _summary_payload(
    *,
    pct_change: float | None,
    processing_time_increased: bool | None,
    is_comparable: bool,
    factors: list[dict] | None = None,
    top_delayed_activities: list[dict] | None = None,
):
    return SimpleNamespace(
        overall_change_summary={
            "avg_duration_percent_change": pct_change,
            "processing_time_increased": processing_time_increased,
            "is_comparable": is_comparable,
        },
        top_suspicious_factors=factors or [],
        activity_delay_findings={
            "top_delayed_activities": top_delayed_activities or [],
            "uncertainty_flags": [],
        },
        variant_or_rework_findings={},
        cannot_determine=False,
    )


def test_why_slower_payload_reframes_when_overall_duration_decreases():
    payload = compose_investigation_answer(
        question_type="why_slower",
        answer_blocks=[],
        evidence_tables={},
        summary_payload=_summary_payload(
            pct_change=-12.4,
            processing_time_increased=False,
            is_comparable=True,
            factors=[{"title": "Activity delay", "confidence": "medium"}],
            top_delayed_activities=[{"activity": "Review", "absolute_increase_minutes": 8.2, "support_volume": 7}],
        ),
        limitations=[],
        follow_up_questions=[],
        metrics_used=["avg_duration_hours"],
        selected_context={"missing_optional_attributes": ["resource", "department"]},
        trace={"analysis_functions_executed": ["compare_period_case_performance"]},
    )

    assert payload.overallChangeState == "decrease"
    assert payload.answerStatus == "premise_not_supported"
    assert "did not increase overall" in payload.directAnswer.lower()
    assert payload.limitations


def test_why_slower_payload_handles_no_meaningful_overall_change():
    payload = compose_investigation_answer(
        question_type="why_slower",
        answer_blocks=[],
        evidence_tables={},
        summary_payload=_summary_payload(
            pct_change=1.8,
            processing_time_increased=True,
            is_comparable=True,
            factors=[],
        ),
        limitations=[],
        follow_up_questions=[],
        metrics_used=["avg_duration_hours"],
        selected_context={"optional_attributes_available": []},
        trace={"analysis_functions_executed": ["compare_period_case_performance"]},
    )

    assert payload.overallChangeState == "no_meaningful_overall_change"
    assert payload.answerStatus == "premise_not_supported"
    assert "did not materially increase" in payload.directAnswer.lower()
