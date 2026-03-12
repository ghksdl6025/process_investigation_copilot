"""Question-driven investigation panel routing and output assembly.

This module keeps routing deterministic and lightweight for the MVP:
- classify user question into a small set of supported types
- route to existing analysis outputs (period/slow-case/activity/process-view)
- return a stable structured payload for Streamlit rendering
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import pandas as pd

from src.process_investigation_copilot.analysis.explanation_formatter import (
    ExplanationBlock,
)
from src.process_investigation_copilot.analysis.investigation_answer_composer import (
    InvestigationAnswerPayload,
    compose_investigation_answer,
)
from src.process_investigation_copilot.analysis.investigation import (
    InvestigationOutput,
    build_investigation_output,
)
from src.process_investigation_copilot.analysis.process_view import (
    build_directly_follows_graph,
    build_transition_insights,
)

QuestionType = Literal[
    "why_slower",
    "period_comparison",
    "slow_vs_normal",
    "bottleneck",
    "variant",
    "unsupported",
]

QUESTION_TEMPLATES: list[str] = [
    "Why did processing time increase this month?",
    "Which step got slower recently?",
    "How are slow cases different from non-slow cases?",
    "Which variant appears most associated with slow cases?",
]


@dataclass
class InvestigationPanelResult:
    """Structured output for a single investigation question."""

    question: str
    question_type: QuestionType
    is_supported: bool
    answer_blocks: list[ExplanationBlock]
    evidence_tables: dict[str, pd.DataFrame]
    evidence_charts: dict[str, pd.DataFrame]
    metrics_used: list[str]
    selected_context: dict[str, Any]
    limitations: list[str]
    follow_up_questions: list[str]
    trace: dict[str, Any]
    summary_payload: Any | None = None
    answer_payload: InvestigationAnswerPayload | None = None

    def __post_init__(self) -> None:
        """Populate unified answer payload for forward-compatible rendering."""
        if self.answer_payload is None:
            self.answer_payload = compose_investigation_answer(
                question_type=self.question_type,
                answer_blocks=self.answer_blocks,
                evidence_tables=self.evidence_tables,
                summary_payload=self.summary_payload,
                limitations=self.limitations,
                follow_up_questions=self.follow_up_questions,
                metrics_used=self.metrics_used,
                selected_context=self.selected_context,
                trace=self.trace,
            )

    def to_dict(self) -> dict[str, Any]:
        """Return machine-readable payload metadata for UI/debug output."""
        payload = asdict(self)
        if self.answer_payload is not None:
            payload["answer_payload"] = self.answer_payload.to_dict()
        payload["evidence_tables"] = {
            name: {"rows": int(len(table)), "columns": list(table.columns)}
            for name, table in self.evidence_tables.items()
        }
        payload["evidence_charts"] = {
            name: {"rows": int(len(table)), "columns": list(table.columns)}
            for name, table in self.evidence_charts.items()
        }
        return payload


def classify_question_type(question: str) -> QuestionType:
    """Classify question into a supported deterministic analysis type."""
    normalized = question.strip().lower()
    if not normalized:
        return "why_slower"

    if any(token in normalized for token in ["bottleneck", "transition", "dfg", "flow edge"]):
        return "bottleneck"
    if "variant" in normalized or "path" in normalized:
        return "variant"
    if (
        "slow cases" in normalized
        or "slow vs" in normalized
        or "different from normal" in normalized
        or "different from non-slow" in normalized
    ):
        return "slow_vs_normal"
    if any(token in normalized for token in ["why", "which step", "got slower"]):
        return "why_slower"
    if any(token in normalized for token in ["period", "month", "recent", "previous", "increase"]):
        return "period_comparison"
    return "unsupported"


def build_investigation_panel_result(
    event_log: pd.DataFrame,
    question: str,
    investigation_output: InvestigationOutput | None = None,
) -> InvestigationPanelResult:
    """Route a question to deterministic analysis outputs and return structured UI payload."""
    resolved_question = question.strip() or QUESTION_TEMPLATES[0]
    question_type = classify_question_type(resolved_question)
    if question_type == "unsupported":
        return _build_unsupported_result(resolved_question)
    if question_type == "bottleneck":
        return _build_bottleneck_result(resolved_question, event_log)

    investigation = investigation_output or build_investigation_output(event_log)
    if question_type == "why_slower":
        return _build_why_slower_result(resolved_question, investigation, event_log)
    if question_type == "period_comparison":
        return _build_period_result(resolved_question, investigation)
    if question_type == "slow_vs_normal":
        return _build_slow_vs_normal_result(resolved_question, investigation)
    if question_type == "variant":
        return _build_variant_result(resolved_question, investigation)
    return _build_unsupported_result(resolved_question)


def build_core_scenario_result(
    event_log: pd.DataFrame,
    investigation_output: InvestigationOutput | None = None,
) -> InvestigationPanelResult:
    """Return the best-supported MVP scenario result.

    Core benchmark scenario:
    "Why did processing time increase this month?"
    """
    return build_investigation_panel_result(
        event_log=event_log,
        question=QUESTION_TEMPLATES[0],
        investigation_output=investigation_output,
    )


def _build_why_slower_result(
    question: str, investigation: InvestigationOutput, event_log: pd.DataFrame
) -> InvestigationPanelResult:
    explanation = investigation.grounded_explanation
    blocks = [
        explanation.observation,
        explanation.evidence,
        explanation.interpretation,
        explanation.limitations,
    ]
    return InvestigationPanelResult(
        question=question,
        question_type="why_slower",
        is_supported=True,
        answer_blocks=blocks,
        evidence_tables={
            "Activity Delay Comparison": investigation.activity_delay_comparison.ranked_table,
            "Slow vs Non-slow Activity Comparison": investigation.slow_case_comparison.activity_comparison,
            "Slow vs Non-slow Rework Comparison": investigation.slow_case_comparison.rework_comparison,
        },
        evidence_charts={"Period Trend": investigation.period_comparison.trend_data},
        metrics_used=[
            "avg_duration_hours",
            "median_duration_hours",
            "p90_duration_hours",
            "avg_event_count",
            "activity_delay_proxy_minutes",
            "rework_case_ratio",
            "variant_distribution",
        ],
        selected_context={
            "period_strategy": investigation.period_comparison.strategy,
            "selected_time_window": _time_window_label(investigation.period_comparison),
            "selected_subset": "all_analyzed_cases",
            "optional_attributes_available": [
                column for column in ["resource", "department", "cost"] if column in event_log.columns
            ],
            "missing_optional_attributes": [
                column for column in ["resource", "department"] if column not in event_log.columns
            ],
        },
        limitations=list(investigation.summary_payload.limitations),
        follow_up_questions=_follow_ups_for("why_slower"),
        trace=_build_trace(
            question_type="why_slower",
            selected_time_window=_time_window_label(investigation.period_comparison),
            selected_subset="all_analyzed_cases",
            analysis_functions_executed=[
                "compare_period_case_performance",
                "compare_activity_delay_between_periods",
                "build_slow_case_comparison",
                "build_investigation_summary_payload",
                "build_grounded_explanation",
            ],
            evidence_used=[
                "period_comparison.trend_data",
                "activity_delay_comparison.ranked_table",
                "slow_case_comparison.activity_comparison",
                "slow_case_comparison.rework_comparison",
                "slow_case_comparison.variant_comparison",
            ],
            confidence_label=_confidence_from_summary(investigation.summary_payload),
        ),
        summary_payload=investigation.summary_payload,
    )


def _build_period_result(
    question: str, investigation: InvestigationOutput
) -> InvestigationPanelResult:
    period = investigation.period_comparison
    pct = period.percent_diff.get("avg_duration_hours")
    if period.is_comparable and period.processing_time_increased:
        text = (
            "Recent period average duration is higher than previous period "
            f"({float(pct):.1f}% change)." if pct is not None else "Recent period average duration is higher."
        )
    elif period.is_comparable and period.processing_time_increased is False:
        text = "Recent period average duration is not higher than previous period."
    else:
        text = period.message

    blocks = [
        ExplanationBlock("Observation", text, ["period_comparison"]),
        ExplanationBlock(
            "Evidence",
            period.message,
            ["period_comparison.strategy", "period_comparison.absolute_diff", "period_comparison.percent_diff"],
        ),
        ExplanationBlock(
            "Interpretation",
            "This comparison identifies outcome change by period; it does not by itself identify specific drivers.",
            ["period_comparison"],
        ),
        ExplanationBlock(
            "Limitations",
            "Period splits may be constrained by available completion timestamps and case volume.",
            ["period_comparison.message"],
        ),
    ]
    summary_df = _period_summary_table(period)
    return InvestigationPanelResult(
        question=question,
        question_type="period_comparison",
        is_supported=True,
        answer_blocks=blocks,
        evidence_tables={"Period KPI Comparison": summary_df},
        evidence_charts={"Period Trend": period.trend_data},
        metrics_used=[
            "case_count",
            "avg_duration_hours",
            "median_duration_hours",
            "p90_duration_hours",
            "avg_event_count",
        ],
        selected_context={
            "period_strategy": period.strategy,
            "selected_time_window": _time_window_label(period),
            "selected_subset": "all_analyzed_cases",
        },
        limitations=[period.message, blocks[-1].text],
        follow_up_questions=_follow_ups_for("period_comparison"),
        trace=_build_trace(
            question_type="period_comparison",
            selected_time_window=_time_window_label(period),
            selected_subset="all_analyzed_cases",
            analysis_functions_executed=["compare_period_case_performance"],
            evidence_used=["period_comparison.absolute_diff", "period_comparison.percent_diff"],
            confidence_label="medium" if period.is_comparable else "low",
        ),
    )


def _build_slow_vs_normal_result(
    question: str, investigation: InvestigationOutput
) -> InvestigationPanelResult:
    summary = investigation.slow_case_comparison.summary
    blocks = [
        ExplanationBlock(
            "Observation",
            (
                f"Slow cases represent {float(summary.get('slow_case_ratio', 0.0)):.1%} "
                f"of analyzed cases ({int(summary.get('slow_case_count', 0))}/"
                f"{int(summary.get('total_case_count', 0))})."
            ),
            ["slow_case_summary"],
        ),
        ExplanationBlock(
            "Evidence",
            "Differences are shown across activity frequency, rework, and variant distribution.",
            ["activity_comparison", "rework_comparison", "variant_comparison"],
        ),
        ExplanationBlock(
            "Interpretation",
            "These differences indicate how slow cases are associated with different process behavior.",
            ["slow_case_comparison"],
        ),
        ExplanationBlock(
            "Limitations",
            "Slow-case definition is rank-based (top 10% by duration) and association-based.",
            ["slow_case_definition"],
        ),
    ]
    return InvestigationPanelResult(
        question=question,
        question_type="slow_vs_normal",
        is_supported=True,
        answer_blocks=blocks,
        evidence_tables={
            "Slow vs Non-slow Activity Comparison": investigation.slow_case_comparison.activity_comparison,
            "Slow vs Non-slow Rework Comparison": investigation.slow_case_comparison.rework_comparison,
            "Slow vs Non-slow Variant Comparison": investigation.slow_case_comparison.variant_comparison,
        },
        evidence_charts={},
        metrics_used=[
            "slow_case_ratio",
            "activity_event_share_delta",
            "rework_case_ratio",
            "variant_case_count",
        ],
        selected_context={
            "slow_case_threshold_hours": summary.get("slow_case_duration_threshold_hours"),
            "selected_time_window": "all_available_data",
            "selected_subset": "slow_vs_non_slow",
        },
        limitations=[blocks[-1].text],
        follow_up_questions=_follow_ups_for("slow_vs_normal"),
        trace=_build_trace(
            question_type="slow_vs_normal",
            selected_time_window="all_available_data",
            selected_subset="slow_vs_non_slow",
            analysis_functions_executed=["build_slow_case_comparison"],
            evidence_used=[
                "slow_case_comparison.activity_comparison",
                "slow_case_comparison.rework_comparison",
                "slow_case_comparison.variant_comparison",
            ],
            confidence_label="medium",
        ),
    )


def _build_variant_result(
    question: str, investigation: InvestigationOutput
) -> InvestigationPanelResult:
    variants = investigation.slow_case_comparison.variant_comparison
    if variants.empty:
        observation = "No analyzable variant distribution is available."
    else:
        top = variants.iloc[0]
        observation = (
            f"Top variant by case volume is `{top['variant']}` "
            f"({int(top['total_case_count'])} cases)."
        )

    blocks = [
        ExplanationBlock("Observation", observation, ["variant_comparison"]),
        ExplanationBlock(
            "Evidence",
            "Variant table shows slow/non-slow case counts by ordered activity sequence.",
            ["variant_comparison"],
        ),
        ExplanationBlock(
            "Interpretation",
            "Variant concentration can guide where to inspect dominant paths and slow-case concentration.",
            ["variant_comparison"],
        ),
        ExplanationBlock(
            "Limitations",
            "Variant frequency does not by itself explain root cause of delay.",
            ["variant_comparison"],
        ),
    ]
    return InvestigationPanelResult(
        question=question,
        question_type="variant",
        is_supported=True,
        answer_blocks=blocks,
        evidence_tables={"Slow vs Non-slow Variant Comparison": variants},
        evidence_charts={},
        metrics_used=["variant_case_count", "slow_case_count", "non_slow_case_count"],
        selected_context={
            "selected_time_window": "all_available_data",
            "selected_subset": "all_analyzed_cases",
        },
        limitations=[blocks[-1].text],
        follow_up_questions=_follow_ups_for("variant"),
        trace=_build_trace(
            question_type="variant",
            selected_time_window="all_available_data",
            selected_subset="all_analyzed_cases",
            analysis_functions_executed=["build_slow_case_comparison"],
            evidence_used=["slow_case_comparison.variant_comparison"],
            confidence_label="medium" if not variants.empty else "low",
        ),
    )


def _build_bottleneck_result(question: str, event_log: pd.DataFrame) -> InvestigationPanelResult:
    dfg = build_directly_follows_graph(
        event_log=event_log,
        case_group="all",
        layout_direction="TB",
        visual_mode="bottleneck",
        min_edge_frequency=1,
        top_n_edges=20,
        edge_label_mode="full",
    )
    insights = build_transition_insights(dfg.edges)
    blocks = [
        ExplanationBlock(
            "Observation",
            f"Computed bottleneck-oriented transition view on {dfg.case_count} cases.",
            ["dfg_summary"],
        ),
        ExplanationBlock(
            "Evidence",
            (
                f"Most frequent: {insights['most_frequent']['transition']} | "
                f"Slowest average: {insights['slowest_average']['transition']} ({insights['slowest_average']['value']})."
            ),
            ["dfg_edges.avg_transition_minutes", "dfg_edges.transition_frequency"],
        ),
        ExplanationBlock(
            "Interpretation",
            "Slower transitions are investigation candidates based on average transition time and volume.",
            ["dfg_edges"],
        ),
        ExplanationBlock(
            "Limitations",
            "Bottleneck mode is heuristic and descriptive; it does not establish causal bottlenecks.",
            ["dfg_edges"],
        ),
    ]
    return InvestigationPanelResult(
        question=question,
        question_type="bottleneck",
        is_supported=True,
        answer_blocks=blocks,
        evidence_tables={"Bottleneck Transition Table": dfg.edges},
        evidence_charts={},
        metrics_used=["transition_frequency", "avg_transition_minutes", "bottleneck_score_heuristic"],
        selected_context={
            "selected_time_window": "all_available_data",
            "selected_subset": "all",
            "visual_mode": "bottleneck",
        },
        limitations=[blocks[-1].text],
        follow_up_questions=_follow_ups_for("bottleneck"),
        trace=_build_trace(
            question_type="bottleneck",
            selected_time_window="all_available_data",
            selected_subset="all",
            analysis_functions_executed=[
                "build_slow_case_comparison",
                "build_slow_case_event_population",
                "build_directly_follows_graph",
                "build_transition_insights",
            ],
            evidence_used=["dfg.edges.transition_frequency", "dfg.edges.avg_transition_minutes"],
            confidence_label="medium" if not dfg.edges.empty else "low",
        ),
    )


def _build_unsupported_result(question: str) -> InvestigationPanelResult:
    limitation = (
        "This question is not yet supported by the MVP router. Try a period, slow-case, variant, "
        "or bottleneck-focused question."
    )
    return InvestigationPanelResult(
        question=question,
        question_type="unsupported",
        is_supported=False,
        answer_blocks=[
            ExplanationBlock(
                "Observation",
                "The request could not be mapped to a supported deterministic analysis flow.",
                ["question_routing"],
            ),
            ExplanationBlock(
                "Evidence",
                "Current router supports period comparison, why-slower, bottleneck, slow-vs-normal, and variant questions.",
                ["question_routing.supported_types"],
            ),
            ExplanationBlock(
                "Interpretation",
                "A supported template question is needed to provide grounded evidence.",
                ["question_routing"],
            ),
            ExplanationBlock("Limitations", limitation, ["question_routing"]),
        ],
        evidence_tables={},
        evidence_charts={},
        metrics_used=[],
        selected_context={},
        limitations=[limitation],
        follow_up_questions=QUESTION_TEMPLATES[:],
        trace=_build_trace(
            question_type="unsupported",
            selected_time_window="not_selected",
            selected_subset="not_selected",
            analysis_functions_executed=["classify_question_type"],
            evidence_used=[],
            confidence_label="low",
        ),
    )


def _period_summary_table(period_result: Any) -> pd.DataFrame:
    rows = [
        {"period": "recent", **(period_result.recent.to_dict() if period_result.recent else {})},
        {"period": "previous", **(period_result.previous.to_dict() if period_result.previous else {})},
    ]
    return pd.DataFrame(rows)


def _time_window_label(period_result: Any) -> str:
    trend = period_result.trend_data
    if isinstance(trend, pd.DataFrame) and not trend.empty and "period" in trend.columns:
        labels = trend["period"].astype(str).tolist()
        if period_result.strategy == "monthly_complete_months" and len(labels) >= 2:
            return f"{labels[-2]} -> {labels[-1]}"
        if period_result.strategy == "equal_recent_windows":
            return "previous_window -> recent_window"
    return str(period_result.strategy)


def _follow_ups_for(question_type: QuestionType) -> list[str]:
    follow_ups: dict[QuestionType, list[str]] = {
        "why_slower": [
            "Which step got slower recently?",
            "How are slow cases different from normal cases?",
            "Which variant appears most associated with slow cases?",
        ],
        "period_comparison": [
            "Why did processing time increase this month?",
            "Which step got slower recently?",
            "How are slow cases different from normal cases?",
        ],
        "slow_vs_normal": [
            "Which variant appears most associated with slow cases?",
            "Which step got slower recently?",
            "Why did processing time increase this month?",
        ],
        "bottleneck": [
            "Which step got slower recently?",
            "How are slow cases different from normal cases?",
            "Why did processing time increase this month?",
        ],
        "variant": [
            "How are slow cases different from normal cases?",
            "Why did processing time increase this month?",
            "Which step got slower recently?",
        ],
        "unsupported": QUESTION_TEMPLATES[:],
    }
    return follow_ups.get(question_type, QUESTION_TEMPLATES[:])


def _confidence_from_summary(summary_payload: Any) -> str:
    factors = summary_payload.top_suspicious_factors if summary_payload else []
    if not factors:
        return "low"
    highest = factors[0].get("confidence", "low")
    return str(highest)


def _build_trace(
    question_type: QuestionType,
    selected_time_window: str,
    selected_subset: str,
    analysis_functions_executed: list[str],
    evidence_used: list[str],
    confidence_label: str,
) -> dict[str, Any]:
    return {
        "question_type": question_type,
        "selected_time_window": selected_time_window,
        "selected_subset": selected_subset,
        "analysis_functions_executed": analysis_functions_executed,
        "evidence_used": evidence_used,
        "confidence_label": confidence_label,
    }
