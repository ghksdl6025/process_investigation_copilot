"""Structured investigation summary builder from deterministic analysis outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import pandas as pd

from src.process_investigation_copilot.analysis.activity_delay_analysis import (
    ActivityDelayComparisonResult,
)
from src.process_investigation_copilot.analysis.period_comparison import (
    PeriodComparisonResult,
)
from src.process_investigation_copilot.analysis.slow_case_analysis import (
    SlowCaseComparisonResult,
)

ConfidenceLevel = Literal["low", "medium", "high"]


@dataclass
class SuspiciousFactor:
    """Compact suspicious-factor evidence record."""

    title: str
    metric_evidence: dict[str, Any]
    explanation: str
    confidence: ConfidenceLevel
    limitation: str
    score: float


@dataclass
class InvestigationSummaryPayload:
    """Stable summary payload for downstream UI rendering."""

    overall_change_summary: dict[str, Any]
    top_suspicious_factors: list[dict[str, Any]]
    activity_delay_findings: dict[str, Any]
    slow_case_findings: dict[str, Any]
    variant_or_rework_findings: dict[str, Any]
    limitations: list[str]
    cannot_determine: bool


def build_investigation_summary_payload(
    period_result: PeriodComparisonResult,
    activity_delay_result: ActivityDelayComparisonResult,
    slow_case_result: SlowCaseComparisonResult,
) -> InvestigationSummaryPayload:
    """Build conservative, evidence-based investigation summary payload.

    Payload shape (stable fields):
    - overall_change_summary
    - top_suspicious_factors
    - activity_delay_findings
    - slow_case_findings
    - variant_or_rework_findings
    - limitations
    - cannot_determine
    """
    overall_summary = _overall_change_summary(period_result)
    activity_findings = _activity_delay_findings(activity_delay_result)
    slow_findings = _slow_case_findings(slow_case_result)
    variant_rework_findings = _variant_or_rework_findings(slow_case_result)

    factors = _suspicious_factors(
        period_result=period_result,
        activity_delay_result=activity_delay_result,
        slow_case_result=slow_case_result,
    )
    factors = sorted(factors, key=lambda item: item.score, reverse=True)
    top_factors = [asdict(item) for item in factors[:5]]
    for item in top_factors:
        item.pop("score", None)

    limitations = _limitations(
        period_result=period_result,
        activity_delay_result=activity_delay_result,
    )
    high_or_medium_present = any(
        factor.get("confidence") in {"medium", "high"} for factor in top_factors
    )
    cannot_determine = (
        not period_result.is_comparable
        or not activity_delay_result.is_comparable
        or len(top_factors) == 0
        or not high_or_medium_present
    )
    if cannot_determine:
        limitations.append(
            "Current evidence is insufficient to determine likely delay drivers with confidence."
        )

    return InvestigationSummaryPayload(
        overall_change_summary=overall_summary,
        top_suspicious_factors=top_factors,
        activity_delay_findings=activity_findings,
        slow_case_findings=slow_findings,
        variant_or_rework_findings=variant_rework_findings,
        limitations=limitations,
        cannot_determine=cannot_determine,
    )


def _overall_change_summary(period_result: PeriodComparisonResult) -> dict[str, Any]:
    pct_change = period_result.percent_diff.get("avg_duration_hours")
    return {
        "is_comparable": period_result.is_comparable,
        "strategy": period_result.strategy,
        "processing_time_increased": period_result.processing_time_increased,
        "avg_duration_percent_change": pct_change,
        "message": period_result.message,
    }


def _activity_delay_findings(
    activity_delay_result: ActivityDelayComparisonResult,
) -> dict[str, Any]:
    return {
        "is_comparable": activity_delay_result.is_comparable,
        "message": activity_delay_result.message,
        "top_delayed_activities": activity_delay_result.top_delayed_activities[:5],
        "uncertainty_flags": activity_delay_result.uncertainty_flags,
    }


def _slow_case_findings(slow_case_result: SlowCaseComparisonResult) -> dict[str, Any]:
    summary = slow_case_result.summary
    return {
        "slow_case_ratio": summary.get("slow_case_ratio"),
        "slow_case_count": summary.get("slow_case_count"),
        "total_case_count": summary.get("total_case_count"),
        "duration_threshold_hours": summary.get("slow_case_duration_threshold_hours"),
    }


def _variant_or_rework_findings(
    slow_case_result: SlowCaseComparisonResult,
) -> dict[str, Any]:
    rework_delta = _rework_ratio_delta(slow_case_result.rework_comparison)
    top_variant = (
        slow_case_result.variant_comparison.iloc[0].to_dict()
        if not slow_case_result.variant_comparison.empty
        else None
    )
    return {
        "rework_case_ratio_delta": rework_delta,
        "top_variant_row": top_variant,
    }


def _suspicious_factors(
    period_result: PeriodComparisonResult,
    activity_delay_result: ActivityDelayComparisonResult,
    slow_case_result: SlowCaseComparisonResult,
) -> list[SuspiciousFactor]:
    factors: list[SuspiciousFactor] = []

    pct_change = period_result.percent_diff.get("avg_duration_hours")
    if period_result.is_comparable and period_result.processing_time_increased and pct_change is not None:
        magnitude = abs(float(pct_change))
        confidence = _confidence_from_magnitude_and_support(
            magnitude=magnitude, support=period_result.recent.case_count if period_result.recent else 0
        )
        factors.append(
            SuspiciousFactor(
                title="Overall processing-time increase",
                metric_evidence={
                    "avg_duration_percent_change": pct_change,
                    "recent_case_count": period_result.recent.case_count if period_result.recent else None,
                },
                explanation=(
                    "Recent-period average case duration is higher than previous period."
                ),
                confidence=confidence,
                limitation="This indicates change in outcome, not the specific causal driver.",
                score=_score(confidence, magnitude),
            )
        )

    if activity_delay_result.is_comparable and not activity_delay_result.ranked_table.empty:
        top = activity_delay_result.ranked_table.iloc[0]
        abs_increase = top["absolute_increase_minutes"]
        support = int(top["support_volume"])
        if pd.notna(abs_increase) and float(abs_increase) > 0:
            magnitude = float(abs_increase)
            confidence = _confidence_from_magnitude_and_support(
                magnitude=magnitude, support=support
            )
            factors.append(
                SuspiciousFactor(
                    title=f"Activity delay increase: {top['activity']}",
                    metric_evidence={
                        "activity": top["activity"],
                        "absolute_increase_minutes": abs_increase,
                        "percent_increase": top["percent_increase"],
                        "support_volume": support,
                    },
                    explanation=(
                        "This activity shows the largest increase in transition-time proxy."
                    ),
                    confidence=confidence,
                    limitation="Proxy combines waiting and service effects; it is not pure service time.",
                    score=_score(confidence, magnitude),
                )
            )

    rework_delta = _rework_ratio_delta(slow_case_result.rework_comparison)
    if rework_delta is not None and rework_delta > 0:
        confidence = _confidence_from_magnitude_and_support(
            magnitude=rework_delta * 100.0,
            support=int(slow_case_result.summary.get("slow_case_count", 0)),
        )
        factors.append(
            SuspiciousFactor(
                title="Higher rework concentration in slow cases",
                metric_evidence={"rework_case_ratio_delta": rework_delta},
                explanation="Slow cases show a higher proportion of rework than non-slow cases.",
                confidence=confidence,
                limitation="Association with slow cases does not prove rework is the root cause.",
                score=_score(confidence, rework_delta * 100.0),
            )
        )

    variant_signal = _variant_mix_signal(slow_case_result.variant_comparison)
    if variant_signal is not None:
        confidence = _confidence_from_magnitude_and_support(
            magnitude=variant_signal["slow_share_percent"],
            support=variant_signal["slow_case_count"],
        )
        factors.append(
            SuspiciousFactor(
                title="Slow-case concentration in dominant variant",
                metric_evidence=variant_signal,
                explanation=(
                    "A dominant variant appears frequently in slow cases and may be worth investigation."
                ),
                confidence=confidence,
                limitation="Variant concentration can reflect case mix, not necessarily a process defect.",
                score=_score(confidence, variant_signal["slow_share_percent"]),
            )
        )

    return factors


def _rework_ratio_delta(rework_comparison: pd.DataFrame) -> float | None:
    if rework_comparison.empty:
        return None
    slow = rework_comparison[rework_comparison["case_group"] == "slow"]
    non = rework_comparison[rework_comparison["case_group"] == "non_slow"]
    if slow.empty or non.empty:
        return None
    return float(slow.iloc[0]["rework_case_ratio"]) - float(non.iloc[0]["rework_case_ratio"])


def _variant_mix_signal(variant_comparison: pd.DataFrame) -> dict[str, Any] | None:
    if variant_comparison.empty:
        return None
    row = variant_comparison.iloc[0]
    slow_count = float(row.get("slow_case_count", 0))
    total = float(row.get("total_case_count", 0))
    if total <= 0:
        return None
    return {
        "variant": row.get("variant"),
        "slow_case_count": int(slow_count),
        "total_case_count": int(total),
        "slow_share_percent": (slow_count / total) * 100.0,
    }


def _confidence_from_magnitude_and_support(magnitude: float, support: int) -> ConfidenceLevel:
    if magnitude >= 30 and support >= 10:
        return "high"
    if magnitude >= 10 and support >= 5:
        return "medium"
    return "low"


def _score(confidence: ConfidenceLevel, magnitude: float) -> float:
    weight = {"high": 3.0, "medium": 2.0, "low": 1.0}[confidence]
    return weight * max(0.0, magnitude)


def _limitations(
    period_result: PeriodComparisonResult,
    activity_delay_result: ActivityDelayComparisonResult,
) -> list[str]:
    limitations: list[str] = []
    if not period_result.is_comparable:
        limitations.append("Period comparison is not fully comparable due to data volume/time coverage.")
    limitations.extend(activity_delay_result.uncertainty_flags)
    limitations.append("Findings are investigation signals and do not establish causality.")
    # Deduplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for item in limitations:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
