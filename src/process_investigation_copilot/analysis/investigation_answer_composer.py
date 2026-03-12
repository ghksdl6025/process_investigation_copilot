"""Unified investigation answer payload composer."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


NO_MEANINGFUL_CHANGE_THRESHOLD_PCT = 5.0


@dataclass
class InvestigationAnswerSection:
    """Simple text section with optional evidence references."""

    title: str
    text: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class InvestigationAnswerTrace:
    """Lightweight trace payload for rendered investigation answers."""

    analysesUsed: list[str] = field(default_factory=list)
    subsetsUsed: list[str] = field(default_factory=list)
    metricsUsed: list[str] = field(default_factory=list)


@dataclass
class InvestigationAnswerPayload:
    """Stable composed payload for Investigation panel rendering."""

    questionType: str
    directAnswer: str
    overallChangeState: str = "insufficient_evidence"
    answerStatus: str = "insufficient"
    observations: list[InvestigationAnswerSection] = field(default_factory=list)
    evidence: list[InvestigationAnswerSection] = field(default_factory=list)
    interpretations: list[InvestigationAnswerSection] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    followUpQuestions: list[str] = field(default_factory=list)
    trace: InvestigationAnswerTrace = field(default_factory=InvestigationAnswerTrace)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe payload for debugging/UI rendering."""
        return asdict(self)


def compose_investigation_answer(
    *,
    question_type: str,
    answer_blocks: list[Any],
    evidence_tables: dict[str, Any] | None = None,
    summary_payload: Any = None,
    limitations: list[str],
    follow_up_questions: list[str],
    metrics_used: list[str],
    selected_context: dict[str, Any],
    trace: dict[str, Any],
) -> InvestigationAnswerPayload:
    """Compose a unified answer payload from existing raw investigation outputs."""

    if question_type == "why_slower":
        return _compose_why_slower_answer(
            summary_payload=summary_payload,
            answer_blocks=answer_blocks,
            evidence_tables=evidence_tables or {},
            limitations=limitations,
            follow_up_questions=follow_up_questions,
            metrics_used=metrics_used,
            selected_context=selected_context,
            trace=trace,
        )

    observations: list[InvestigationAnswerSection] = []
    evidence_sections: list[InvestigationAnswerSection] = []
    interpretations: list[InvestigationAnswerSection] = []
    normalized_limitations = list(limitations)

    for index, block in enumerate(answer_blocks):
        title = str(getattr(block, "title", "") or f"Block {index + 1}")
        text = str(getattr(block, "text", "") or "").strip()
        refs = list(getattr(block, "evidence_refs", []) or [])
        if not text:
            continue

        section = InvestigationAnswerSection(title=title, text=text, evidence_refs=refs)
        normalized_title = title.lower()
        if "observ" in normalized_title:
            observations.append(section)
        elif "evid" in normalized_title:
            evidence_sections.append(section)
        elif "interpret" in normalized_title:
            interpretations.append(section)
        elif "limit" in normalized_title or "uncert" in normalized_title:
            normalized_limitations.append(text)
        elif not observations:
            observations.append(section)
        else:
            interpretations.append(section)

    direct_answer = (
        observations[0].text
        if observations
        else evidence_sections[0].text
        if evidence_sections
        else interpretations[0].text
        if interpretations
        else "No direct answer is available."
    )

    subsets_used: list[str] = []
    selected_subset = selected_context.get("selected_subset")
    trace_subset = trace.get("selected_subset")
    for candidate in [selected_subset, trace_subset]:
        if candidate is None:
            continue
        value = str(candidate)
        if value and value not in subsets_used:
            subsets_used.append(value)

    analyses_used = [str(item) for item in trace.get("analysis_functions_executed", [])]

    deduped_limitations: list[str] = []
    seen: set[str] = set()
    for item in normalized_limitations:
        if item not in seen:
            seen.add(item)
            deduped_limitations.append(item)

    return InvestigationAnswerPayload(
        questionType=question_type,
        directAnswer=direct_answer,
        overallChangeState="insufficient_evidence",
        answerStatus="mixed" if observations or evidence_sections or interpretations else "insufficient",
        observations=observations,
        evidence=evidence_sections,
        interpretations=interpretations,
        limitations=deduped_limitations,
        followUpQuestions=list(follow_up_questions),
        trace=InvestigationAnswerTrace(
            analysesUsed=analyses_used,
            subsetsUsed=subsets_used,
            metricsUsed=list(metrics_used),
        ),
    )


def _compose_why_slower_answer(
    *,
    summary_payload: Any,
    answer_blocks: list[Any],
    evidence_tables: dict[str, Any],
    limitations: list[str],
    follow_up_questions: list[str],
    metrics_used: list[str],
    selected_context: dict[str, Any],
    trace: dict[str, Any],
) -> InvestigationAnswerPayload:
    overall = getattr(summary_payload, "overall_change_summary", {}) or {}
    factors = list(getattr(summary_payload, "top_suspicious_factors", []) or [])
    activity_findings = getattr(summary_payload, "activity_delay_findings", {}) or {}
    variant_rework = getattr(summary_payload, "variant_or_rework_findings", {}) or {}
    cannot_determine = bool(getattr(summary_payload, "cannot_determine", False))
    uncertainty_flags = list(activity_findings.get("uncertainty_flags", []) or [])
    overall_state = _classify_overall_change_state(overall)
    answer_status = _derive_answer_status(
        overall_state=overall_state,
        factors=factors,
        cannot_determine=cannot_determine,
    )
    direct_answer = _guard_text(
        _build_direct_answer(
            overall=overall,
            overall_state=overall_state,
            factors=factors,
            cannot_determine=cannot_determine,
            activity_findings=activity_findings,
            variant_rework=variant_rework,
        )
    )

    observations: list[InvestigationAnswerSection] = []
    evidence_sections: list[InvestigationAnswerSection] = []
    interpretations: list[InvestigationAnswerSection] = []

    if overall_state == "insufficient_evidence":
        observations.append(
            InvestigationAnswerSection(
                title="Overall process conclusion",
                text=_guard_text(
                    "The available recent-versus-previous comparison does not support a strong overall conclusion."
                ),
                evidence_refs=["overall_change_summary.is_comparable", "overall_change_summary.message"],
            )
        )
    elif overall_state == "increase":
        observations.append(
            InvestigationAnswerSection(
                title="Overall process conclusion",
                text=_guard_text(
                    f"Average processing time increased in the recent period by {_format_pct(overall.get('avg_duration_percent_change'))}."
                ),
                evidence_refs=[
                    "overall_change_summary.processing_time_increased",
                    "overall_change_summary.avg_duration_percent_change",
                ],
            )
        )
    elif overall_state == "decrease":
        observations.append(
            InvestigationAnswerSection(
                title="Overall process conclusion",
                text=_guard_text(
                    f"Average processing time did not increase overall. It decreased by {_format_pct(abs(_safe_float(overall.get('avg_duration_percent_change'))))} in the recent period."
                ),
                evidence_refs=[
                    "overall_change_summary.processing_time_increased",
                    "overall_change_summary.avg_duration_percent_change",
                ],
            )
        )
    else:
        observations.append(
            InvestigationAnswerSection(
                title="Overall process conclusion",
                text=_guard_text(
                    f"Average processing time did not materially increase or decrease overall ({_format_signed_pct(overall.get('avg_duration_percent_change'))})."
                ),
                evidence_refs=[
                    "overall_change_summary.processing_time_increased",
                    "overall_change_summary.avg_duration_percent_change",
                ],
            )
        )

    for factor in factors[:3]:
        factor_text = _summarize_factor(factor)
        if not factor_text:
            continue
        observations.append(
            InvestigationAnswerSection(
                title=str(factor.get("title", "Investigation signal")),
                text=_guard_text(factor_text),
                evidence_refs=[f"top_suspicious_factors.{factor.get('title', 'signal')}"],
            )
        )

    top_delayed = list(activity_findings.get("top_delayed_activities", []) or [])
    if top_delayed:
        top_activity = top_delayed[0]
        activity_name = _clean_text_fragment(top_activity.get("activity", "An activity"))
        delay_minutes = _safe_float(top_activity.get("absolute_increase_minutes", 0.0))
        support_volume = _safe_int(top_activity.get("support_volume", 0))
        evidence_sections.append(
            InvestigationAnswerSection(
                title="Activity delay signal",
                text=_guard_text(
                    f"{activity_name} shows the largest observed delay increase "
                    f"({_format_minutes(delay_minutes)} additional average delay across {support_volume} supporting cases)."
                ),
                evidence_refs=["activity_delay_findings.top_delayed_activities"],
            )
        )

    rework_delta = variant_rework.get("rework_case_ratio_delta")
    if rework_delta is not None:
        evidence_sections.append(
            InvestigationAnswerSection(
                title="Rework difference",
                text=_guard_text(
                    f"Slow cases have a {_format_percentage_points(rework_delta)} higher rework ratio "
                    "than non-slow cases."
                ),
                evidence_refs=["variant_or_rework_findings.rework_case_ratio_delta"],
            )
        )

    variant_row = variant_rework.get("top_variant_row")
    if variant_row:
        variant_name = _shorten_variant_name(variant_row.get("variant", "N/A"))
        slow_case_count = _safe_int(variant_row.get("slow_case_count", 0))
        total_case_count = _safe_int(variant_row.get("total_case_count", 0))
        evidence_sections.append(
            InvestigationAnswerSection(
                title="Process-mix shift",
                text=_guard_text(
                    f"The path {variant_name} is prominent in the current slow-case mix "
                    f"({slow_case_count} slow cases out of {total_case_count} total cases for that path)."
                ),
                evidence_refs=["variant_or_rework_findings.top_variant_row"],
            )
        )

    interpretations.append(
        InvestigationAnswerSection(
            title="Interpretation",
            text=_guard_text(
                _build_interpretation_text(
                    overall=overall,
                    overall_state=overall_state,
                    factors=factors,
                    cannot_determine=cannot_determine,
                    has_local_signals=bool(evidence_sections),
                )
            ),
            evidence_refs=["top_suspicious_factors", "overall_change_summary"],
        )
    )

    trace_payload = _build_trace_payload(
        metrics_used=metrics_used,
        selected_context=selected_context,
        trace=trace,
    )

    normalized_limitations = list(limitations or [])
    normalized_limitations.extend(_resource_department_limitations(selected_context))
    normalized_limitations.extend(_comparison_strength_limitations(overall, factors, uncertainty_flags))
    if not normalized_limitations:
        normalized_limitations.append("Available evidence is limited and should be interpreted cautiously.")

    return InvestigationAnswerPayload(
        questionType="why_slower",
        directAnswer=direct_answer,
        overallChangeState=overall_state,
        answerStatus=answer_status,
        observations=_guard_sections(observations),
        evidence=_guard_sections(evidence_sections),
        interpretations=_guard_sections(interpretations),
        limitations=[_guard_text(item) for item in _dedupe_preserve_order(normalized_limitations)],
        followUpQuestions=_build_why_slower_follow_ups(
            overall_state=overall_state,
            factors=factors,
            activity_findings=activity_findings,
            variant_rework=variant_rework,
            existing_follow_ups=follow_up_questions,
        ),
        trace=trace_payload,
    )


def _build_direct_answer(
    *,
    overall: dict[str, Any],
    overall_state: str,
    factors: list[dict[str, Any]],
    cannot_determine: bool,
    activity_findings: dict[str, Any],
    variant_rework: dict[str, Any],
) -> str:
    pct = overall.get("avg_duration_percent_change")
    lead_title = _lead_signal_title(factors)
    has_local_signals = _has_local_delay_signals(activity_findings, variant_rework, factors)

    if overall_state == "insufficient_evidence":
        return (
            "The available comparison does not support a strong conclusion about whether processing time increased overall. "
            "Local delay signals can still be reviewed, but they should not be treated as evidence of an overall increase."
        )
    if overall_state == "decrease":
        if has_local_signals:
            return (
                f"Processing time did not increase overall. It decreased by {_format_pct(abs(_safe_float(pct)))}. "
                f"However, some local signals still warrant review, especially {lead_title}."
            )
        return f"Processing time did not increase overall. It decreased by {_format_pct(abs(_safe_float(pct)))}."
    if overall_state == "no_meaningful_overall_change":
        if has_local_signals:
            return (
                "Processing time did not materially increase overall. "
                f"However, some local signals still shifted, especially {lead_title}."
            )
        return "Processing time did not materially increase or decrease overall in the current comparison."
    if cannot_determine or not factors:
        return "Processing time increased in the recent period, but the current evidence is too weak to identify a clear likely contributing factor."

    confidence = str(factors[0].get("confidence", "low")).lower()
    if confidence == "low":
        return (
            f"Processing time increased in the recent period by {_format_pct(_safe_float(pct))}. "
            f"The strongest available signal is associated with {lead_title}, but current evidence is still weak."
        )
    return (
        f"Processing time increased in the recent period by {_format_pct(_safe_float(pct))}. "
        f"The strongest current evidence suggests {lead_title} is a likely contributing factor."
    )


def _build_interpretation_text(
    *,
    overall: dict[str, Any],
    overall_state: str,
    factors: list[dict[str, Any]],
    cannot_determine: bool,
    has_local_signals: bool,
) -> str:
    if overall_state == "insufficient_evidence":
        return (
            "The comparison window is too weak to support a strong overall conclusion. "
            "Any local signals should be treated as exploratory rather than decisive."
        )
    if overall_state == "decrease":
        if has_local_signals:
            return (
                "The overall process improved over the comparison window, but some individual activities or paths still became slower. "
                "That pattern is consistent with localized friction rather than a broad process slowdown."
            )
        return "The overall process improved over the comparison window. The current evidence does not support a broader slowdown narrative."
    if overall_state == "no_meaningful_overall_change":
        if has_local_signals:
            return (
                "The overall process looks broadly stable, while some local activity or path-level signals still shifted. "
                "Those signals are useful for targeted follow-up, but they do not support a claim of overall deterioration."
            )
        return "The overall process looks broadly stable in the current comparison."
    if cannot_determine or not factors:
        return (
            "The observed increase is real enough to investigate further, but the available evidence is not yet strong "
            "enough to point to one trustworthy likely driver."
        )

    lead = factors[0]
    lead_title = str(lead.get("title", "the leading signal"))
    supporting_titles = [str(item.get("title", "")) for item in factors[1:3] if item.get("title")]
    if supporting_titles:
        support_text = ", with supporting signals from " + " and ".join(supporting_titles)
    else:
        support_text = ""

    return (
        f"The increase is most consistent with {lead_title.lower()}{support_text}. "
        "These are association-based investigation signals and should not be treated as evidence of causality."
    )


def _classify_overall_change_state(overall: dict[str, Any]) -> str:
    if not overall or overall.get("is_comparable") is not True:
        return "insufficient_evidence"

    pct = _safe_float(overall.get("avg_duration_percent_change"))
    increased = overall.get("processing_time_increased")
    if pct is None or increased is None:
        return "insufficient_evidence"

    if abs(pct) < NO_MEANINGFUL_CHANGE_THRESHOLD_PCT:
        return "no_meaningful_overall_change"
    if increased is True and pct > 0:
        return "increase"
    if increased is False and pct < 0:
        return "decrease"
    return "insufficient_evidence"


def _derive_answer_status(
    *,
    overall_state: str,
    factors: list[dict[str, Any]],
    cannot_determine: bool,
) -> str:
    if overall_state == "insufficient_evidence":
        return "insufficient"
    if overall_state in {"decrease", "no_meaningful_overall_change"}:
        return "premise_not_supported"
    if cannot_determine or not factors:
        return "insufficient"
    confidence = str(factors[0].get("confidence", "low")).lower()
    if confidence == "high":
        return "supported"
    return "mixed"


def _build_trace_payload(
    *,
    metrics_used: list[str],
    selected_context: dict[str, Any],
    trace: dict[str, Any],
) -> InvestigationAnswerTrace:
    subsets_used: list[str] = []
    for candidate in [selected_context.get("selected_subset"), trace.get("selected_subset")]:
        if candidate is None:
            continue
        value = str(candidate)
        if value and value not in subsets_used:
            subsets_used.append(value)

    return InvestigationAnswerTrace(
        analysesUsed=[str(item) for item in trace.get("analysis_functions_executed", [])],
        subsetsUsed=subsets_used,
        metricsUsed=list(metrics_used),
    )


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _format_pct(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "N/A"
    return f"{abs(number):.1f}%"


def _format_signed_pct(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "N/A"
    return f"{number:+.1f}%"


def _format_minutes(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "N/A"
    return f"{number:.1f} min"


def _format_percentage_points(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "N/A"
    return f"{number * 100.0:+.1f} percentage points"


def _clean_text_fragment(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"np\.float\d+\(([^)]+)\)", r"\1", text)
    text = re.sub(r"np\.int\d+\(([^)]+)\)", r"\1", text)
    text = re.sub(r"-?\d+\.\d{3,}", lambda m: f"{float(m.group(0)):.2f}", text)
    return text or "N/A"


def _shorten_variant_name(value: Any, max_len: int = 72) -> str:
    text = _clean_text_fragment(value)
    text = text.replace(">", " -> ")
    text = text.replace("|", " -> ")
    if len(text) <= max_len:
        return text
    parts = [part.strip() for part in re.split(r"->", text) if part.strip()]
    if len(parts) >= 4:
        return f"{parts[0]} -> {parts[1]} -> ... -> {parts[-1]}"
    return text[: max_len - 3].rstrip() + "..."


def _summarize_factor(factor: dict[str, Any]) -> str:
    title = _clean_text_fragment(factor.get("title", "Investigation signal"))
    confidence = str(factor.get("confidence", "low")).lower()
    metric_evidence = factor.get("metric_evidence", {}) if isinstance(factor.get("metric_evidence", {}), dict) else {}
    support_volume = _safe_int(metric_evidence.get("support_volume"))
    if support_volume > 0:
        return f"{title} appears as a {confidence} confidence signal with support from {support_volume} comparison cases."
    explanation = factor.get("explanation")
    if isinstance(explanation, str) and explanation.strip() and "{" not in explanation:
        return _clean_text_fragment(explanation)
    return f"{title} appears as a {confidence} confidence signal in the current comparison."


def _lead_signal_title(factors: list[dict[str, Any]]) -> str:
    if not factors:
        return "local delay signals"
    return _clean_text_fragment(factors[0].get("title", "local delay signals")).lower()


def _has_local_delay_signals(
    activity_findings: dict[str, Any],
    variant_rework: dict[str, Any],
    factors: list[dict[str, Any]],
) -> bool:
    return bool(
        list(activity_findings.get("top_delayed_activities", []) or [])
        or variant_rework.get("rework_case_ratio_delta") is not None
        or variant_rework.get("top_variant_row")
        or factors
    )


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _guard_text(text: str) -> str:
    guarded = text
    replacements = {
        "caused by": "associated with",
        "due to": "associated with",
        "proves that": "suggests",
        "proves ": "suggests ",
        "proof of": "evidence of",
    }
    lowered = guarded.lower()
    for source, target in replacements.items():
        if source in lowered:
            guarded = _replace_case_insensitive(guarded, source, target)
            lowered = guarded.lower()
    guarded = guarded.replace("`", "")
    guarded = re.sub(r"\{[^{}]*\}", "", guarded)
    guarded = re.sub(r"\s{2,}", " ", guarded).strip()
    return guarded


def _replace_case_insensitive(text: str, old: str, new: str) -> str:
    start = 0
    lowered = text.lower()
    old_lower = old.lower()
    parts: list[str] = []
    while True:
        index = lowered.find(old_lower, start)
        if index == -1:
            parts.append(text[start:])
            break
        parts.append(text[start:index])
        parts.append(new)
        start = index + len(old)
    return "".join(parts)


def _guard_sections(
    sections: list[InvestigationAnswerSection],
) -> list[InvestigationAnswerSection]:
    return [
        InvestigationAnswerSection(
            title=section.title,
            text=_guard_text(section.text),
            evidence_refs=section.evidence_refs,
        )
        for section in sections
    ]


def _resource_department_limitations(selected_context: dict[str, Any]) -> list[str]:
    missing = selected_context.get("missing_optional_attributes")
    if isinstance(missing, list) and missing:
        labels = ", ".join(str(item) for item in missing)
        return [f"{labels} data is unavailable, so this answer does not assess those dimensions."]

    available = selected_context.get("optional_attributes_available")
    if available == []:
        return [
            "Resource and department data are unavailable, so this answer is limited to timing, activity, rework, and variant signals."
        ]

    return []


def _comparison_strength_limitations(
    overall: dict[str, Any],
    factors: list[dict[str, Any]],
    uncertainty_flags: list[str],
) -> list[str]:
    limitations: list[str] = []
    if not overall.get("is_comparable", False):
        limitations.append("The recent-versus-previous comparison is weak, so any explanation should be treated cautiously.")
    if uncertainty_flags:
        limitations.extend(str(item) for item in uncertainty_flags)
    if not factors:
        limitations.append("The current evidence is incomplete and does not isolate a strong likely contributing factor.")
    elif str(factors[0].get("confidence", "low")) == "low":
        limitations.append("The strongest current signal is based on limited support and should be treated as an early indication, not a firm conclusion.")

    top_factor = factors[0] if factors else None
    metric_evidence = top_factor.get("metric_evidence", {}) if isinstance(top_factor, dict) else {}
    support_volume = metric_evidence.get("support_volume")
    recent_case_count = metric_evidence.get("recent_case_count")
    for candidate in [support_volume, recent_case_count]:
        try:
            if candidate is not None and float(candidate) < 5:
                limitations.append("Sample size is small for at least one key comparison, which reduces confidence in the explanation.")
                break
        except (TypeError, ValueError):
            continue
    return limitations


def _build_why_slower_follow_ups(
    *,
    overall_state: str,
    factors: list[dict[str, Any]],
    activity_findings: dict[str, Any],
    variant_rework: dict[str, Any],
    existing_follow_ups: list[str],
) -> list[str]:
    suggestions: list[str] = []

    top_delayed = list(activity_findings.get("top_delayed_activities", []) or [])
    if overall_state == "increase":
        suggestions.append("Which activity got slower the most?")
    elif overall_state == "decrease":
        suggestions.append("Which activities still became slower even though the overall process improved?")
    elif overall_state == "no_meaningful_overall_change":
        suggestions.append("Which activities changed the most even though overall processing time stayed stable?")
    else:
        suggestions.append("Is the recent vs previous period comparison strong enough to support an overall conclusion?")

    if top_delayed:
        top_activity = str(top_delayed[0].get("activity", "")).strip()
        if top_activity:
            suggestions.append(f"Why is {top_activity} slower in the recent period?")

    rework_delta = variant_rework.get("rework_case_ratio_delta")
    if rework_delta is not None:
        suggestions.append("Did rework increase this month?")
        suggestions.append("Are slow cases more likely to involve rework?")

    variant_row = variant_rework.get("top_variant_row")
    if variant_row:
        variant_name = str(variant_row.get("variant", "")).strip()
        if variant_name:
            suggestions.append(f"Are delays concentrated in the variant {variant_name}?")
        suggestions.append("Are slow cases clustered in a specific path?")

    factor_titles = " ".join(str(item.get("title", "")).lower() for item in factors)
    if overall_state == "increase" or "processing-time increase" in factor_titles or "overall processing-time increase" in factor_titles:
        suggestions.append("How does the recent period compare with the previous period by case duration?")
    if "rework" not in factor_titles and rework_delta is None:
        suggestions.append("Did rework increase this month?")
    if "variant" not in factor_titles and not variant_row:
        suggestions.append("Did the process mix change in the recent period?")

    suggestions.extend(existing_follow_ups)

    deduped: list[str] = []
    seen: set[str] = set()
    for suggestion in suggestions:
        normalized = suggestion.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)

    return deduped[:5]
