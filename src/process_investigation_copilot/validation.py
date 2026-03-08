"""Validation and profiling utilities for event log datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ValidationIssue:
    """Single validation issue entry."""

    code: str
    message: str


@dataclass
class ValidationReport:
    """Structured report that separates blocking errors from warnings."""

    blocking_errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Return True when no blocking errors exist."""
        return len(self.blocking_errors) == 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        payload = asdict(self)
        payload["is_valid"] = self.is_valid
        return payload


def validate_event_log(
    dataframe: pd.DataFrame, required_columns: set[str]
) -> ValidationReport:
    """Validate event log shape/content and profile basic dataset metrics."""
    report = ValidationReport()
    row_count = int(len(dataframe))
    metrics: dict[str, Any] = {
        "row_count": row_count,
        "column_count": int(len(dataframe.columns)),
    }

    if row_count == 0:
        report.blocking_errors.append(
            ValidationIssue(
                code="empty_dataset",
                message="Dataset has zero rows and cannot be analyzed.",
            )
        )

    missing_required = sorted(required_columns - set(dataframe.columns))
    if missing_required:
        report.blocking_errors.append(
            ValidationIssue(
                code="missing_required_columns",
                message=(
                    "Missing required columns: "
                    f"{', '.join(missing_required)}."
                ),
            )
        )

    duplicate_rows = int(dataframe.duplicated().sum())
    metrics["duplicate_row_count"] = duplicate_rows
    if duplicate_rows > 0:
        report.warnings.append(
            ValidationIssue(
                code="duplicate_rows",
                message=f"Detected {duplicate_rows} fully duplicated rows.",
            )
        )

    for column in sorted(required_columns & set(dataframe.columns)):
        missing_values = int(_missing_required_value_mask(dataframe[column]).sum())
        missing_rate = float(missing_values / row_count) if row_count else 0.0
        metrics[f"missing_{column}"] = missing_values
        metrics[f"missing_{column}_rate"] = missing_rate
        if missing_values > 0:
            report.warnings.append(
                ValidationIssue(
                    code=f"missing_values_{column}",
                    message=(
                        f"Column `{column}` has {missing_values} missing values "
                        f"({missing_rate:.1%})."
                    ),
                )
            )

    if "timestamp" in dataframe.columns:
        parsed_timestamp = pd.to_datetime(
            dataframe["timestamp"], errors="coerce", format="mixed"
        )
        total_timestamp = int(len(parsed_timestamp))
        parsed_count = int(parsed_timestamp.notna().sum())
        invalid_count = int(total_timestamp - parsed_count)
        metrics["timestamp_total"] = total_timestamp
        metrics["timestamp_parsed_count"] = parsed_count
        metrics["timestamp_invalid_count"] = invalid_count
        metrics["timestamp_parse_success_rate"] = (
            float(parsed_count / total_timestamp) if total_timestamp else 0.0
        )

        if total_timestamp > 0 and parsed_count == 0:
            report.blocking_errors.append(
                ValidationIssue(
                    code="timestamp_parse_failed",
                    message="No timestamp values could be parsed.",
                )
            )
        elif invalid_count > 0:
            report.warnings.append(
                ValidationIssue(
                    code="timestamp_parse_partial",
                    message=f"{invalid_count} timestamp values could not be parsed.",
                )
            )

        valid_timestamps = parsed_timestamp.dropna()
        if len(valid_timestamps) > 0:
            metrics["date_range_start"] = valid_timestamps.min().isoformat()
            metrics["date_range_end"] = valid_timestamps.max().isoformat()
        else:
            metrics["date_range_start"] = None
            metrics["date_range_end"] = None

    if "activity" in dataframe.columns:
        activity_valid = ~_missing_required_value_mask(dataframe["activity"])
        activity_count = int(dataframe.loc[activity_valid, "activity"].nunique())
        metrics["activity_count"] = activity_count
        if activity_count == 0:
            report.blocking_errors.append(
                ValidationIssue(
                    code="activity_count_zero",
                    message="No distinct activities found in `activity`; dataset is not analyzable.",
                )
            )

    if "case_id" in dataframe.columns:
        case_valid = ~_missing_required_value_mask(dataframe["case_id"])
        case_count = int(dataframe.loc[case_valid, "case_id"].nunique())
        metrics["case_count"] = case_count
        if case_count == 0:
            report.blocking_errors.append(
                ValidationIssue(
                    code="case_count_zero",
                    message="No distinct cases found in `case_id`; dataset is not analyzable.",
                )
            )

    timestamp_invalid_count = int(metrics.get("timestamp_invalid_count", 0))
    if report.blocking_errors:
        metrics["analyzability_status"] = "not_analyzable"
    elif timestamp_invalid_count > 0:
        metrics["analyzability_status"] = "partially_analyzable"
    else:
        metrics["analyzability_status"] = "fully_analyzable"

    metrics["has_blocking_errors"] = len(report.blocking_errors) > 0
    metrics["warning_count"] = len(report.warnings)

    report.metrics = metrics
    return report


def _missing_required_value_mask(values: pd.Series) -> pd.Series:
    mask = values.isna()
    if pd.api.types.is_string_dtype(values) or values.dtype == object:
        mask = mask | values.astype(str).str.strip().eq("")
    return mask
