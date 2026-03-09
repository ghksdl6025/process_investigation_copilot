"""Grounded explanation formatter for investigation outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.process_investigation_copilot.analysis.investigation_summary import (
    InvestigationSummaryPayload,
)


@dataclass
class ExplanationBlock:
    """Display-ready explanation block with explicit evidence references."""

    title: str
    text: str
    evidence_refs: list[str]


@dataclass
class GroundedExplanation:
    """Structured explanation payload for UI and machine-readable reuse."""

    observation: ExplanationBlock
    evidence: ExplanationBlock
    interpretation: ExplanationBlock
    limitations: ExplanationBlock
    cannot_determine: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_grounded_explanation(
    summary_payload: InvestigationSummaryPayload,
) -> GroundedExplanation:
    """Build strict Observation/Evidence/Interpretation/Limitations blocks.

    Guardrails:
    - only use computed fields from summary payload
    - use association language (no causal claims)
    - include evidence references in each non-empty block
    """
    overall = summary_payload.overall_change_summary
    increased = overall.get("processing_time_increased")
    pct = overall.get("avg_duration_percent_change")

    if not overall.get("is_comparable", False):
        observation_text = "Recent vs previous period comparison is not currently comparable."
        obs_refs = ["overall_change_summary.is_comparable", "overall_change_summary.message"]
    elif increased is True:
        pct_text = f"{float(pct):.1f}%" if pct is not None else "an observed amount"
        observation_text = (
            f"Average processing time increased in the recent period ({pct_text} vs previous period)."
        )
        obs_refs = [
            "overall_change_summary.processing_time_increased",
            "overall_change_summary.avg_duration_percent_change",
        ]
    elif increased is False:
        observation_text = "Average processing time did not increase in the recent period."
        obs_refs = ["overall_change_summary.processing_time_increased"]
    else:
        observation_text = "A clear period-over-period processing-time change cannot be determined."
        obs_refs = ["overall_change_summary.processing_time_increased"]

    top_factors = summary_payload.top_suspicious_factors
    if top_factors:
        evidence_lines = []
        for idx, factor in enumerate(top_factors[:3], start=1):
            evidence_lines.append(
                f"{idx}. {factor['title']} ({factor['confidence']} confidence): {factor['metric_evidence']}"
            )
        evidence_text = " | ".join(evidence_lines)
    else:
        evidence_text = "No strong suspicious-factor evidence passed current confidence rules."
    evidence_refs = [
        "top_suspicious_factors",
        "activity_delay_findings.top_delayed_activities",
        "variant_or_rework_findings.rework_case_ratio_delta",
    ]

    if summary_payload.cannot_determine:
        interpretation_text = (
            "Current signals are not sufficient for a strong interpretation of likely delay drivers."
        )
    elif top_factors:
        leading = top_factors[0]
        interpretation_text = (
            f"{leading['title']} appears linked to slower outcomes in this period comparison. "
            "This is an association-based investigation signal, not proof of causality."
        )
    else:
        interpretation_text = (
            "The available signals are mixed; a reliable interpretation of delay drivers is not yet available."
        )
    interpretation_refs = [
        "overall_change_summary",
        "top_suspicious_factors",
    ]

    limitations_list = summary_payload.limitations or ["No explicit limitations were provided."]
    limitations_text = " | ".join(f"- {item}" for item in limitations_list)
    limitation_refs = ["limitations"]

    explanation = GroundedExplanation(
        observation=ExplanationBlock(
            title="Observation",
            text=_apply_wording_guardrails(observation_text),
            evidence_refs=obs_refs,
        ),
        evidence=ExplanationBlock(
            title="Evidence",
            text=_apply_wording_guardrails(evidence_text),
            evidence_refs=evidence_refs,
        ),
        interpretation=ExplanationBlock(
            title="Interpretation",
            text=_apply_wording_guardrails(interpretation_text),
            evidence_refs=interpretation_refs,
        ),
        limitations=ExplanationBlock(
            title="Limitations",
            text=_apply_wording_guardrails(limitations_text),
            evidence_refs=limitation_refs,
        ),
        cannot_determine=bool(summary_payload.cannot_determine),
    )
    return explanation


def _apply_wording_guardrails(text: str) -> str:
    # Simple unsupported-claim prevention at formatting time.
    guarded = text.replace("caused by", "associated with")
    guarded = guarded.replace("proves", "suggests")
    guarded = guarded.replace("proof", "evidence")
    return guarded
