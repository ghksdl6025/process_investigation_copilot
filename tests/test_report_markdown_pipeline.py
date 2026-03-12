from src.process_investigation_copilot.reporting.markdown_renderer import (
    render_report_markdown,
)
from src.process_investigation_copilot.reporting.report_composer import (
    compose_investigation_report,
)


def test_report_composer_and_markdown_renderer_produce_structured_output():
    report = compose_investigation_report(
        dataset_label="sample_event_log.csv",
        validation_report={
            "is_valid": True,
            "warnings": [{"message": "Some timestamps required fallback parsing."}],
            "blocking_errors": [],
            "metrics": {
                "row_count": 120,
                "case_count": 20,
                "activity_count": 8,
                "timestamp_parse_success_rate": 0.94,
                "date_range_start": "2025-01-01",
                "date_range_end": "2025-02-28",
            },
        },
        dashboard_payload={
            "overview_metrics": {"events": 120, "cases": 20},
            "slow_case_ratio": 0.1,
            "slow_case_count": 2,
            "period_note": "Compared previous and recent periods.",
            "period_metrics": {
                "recent": {"avg_duration_hours": 15.0, "median_duration_hours": 12.0, "p90_duration_hours": 25.0},
                "previous": {"avg_duration_hours": 10.0, "median_duration_hours": 9.0, "p90_duration_hours": 18.0},
                "percent_diff": {"avg_duration_hours": 50.0, "median_duration_hours": 33.0, "p90_duration_hours": 38.0},
            },
            "top_delayed_activity": {"activity": "Review", "absolute_increase_minutes": 18.5},
            "top_delayed_activities": [
                {"activity": "Review", "absolute_increase_minutes": 18.5, "support_volume": 10},
            ],
            "top_findings": ["Average duration changed by 50.0% in the recent period."],
            "rework_signal": "Slow vs non-slow rework ratio delta: +10.0%.",
        },
        process_view_payload={
            "mode": "frequency",
            "subset": "All analyzed cases",
            "case_count": 20,
            "event_count": 120,
            "edge_count": 15,
            "insights": {
                "most_frequent": {"transition": "Start -> Review", "value": "40 cases"},
            },
        },
        investigation_payload={
            "answer_payload": {
                "directAnswer": "Processing time increased in the recent period.",
                "observations": [{"title": "Overall process conclusion", "text": "Average processing time increased."}],
                "evidence": [{"title": "Activity delay signal", "text": "Review slowed the most."}],
                "interpretations": [{"title": "Interpretation", "text": "The increase is associated with slower review work."}],
                "limitations": ["Resource data is unavailable."],
                "followUpQuestions": ["Which activity got slower the most?"],
            },
            "trace": {"question_type": "why_slower", "selected_time_window": "2025-01 -> 2025-02", "selected_subset": "all_analyzed_cases"},
        },
    )

    markdown = render_report_markdown(report)

    assert report.sections
    assert "# Investigation Report" in markdown
    assert "## Executive Summary" in markdown
    assert "## Investigation Answer" in markdown
    assert "## Process Snapshot" in markdown
    assert "Which activity got slower the most?" in markdown
