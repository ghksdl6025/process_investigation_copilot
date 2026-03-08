"""Data loading helpers for event logs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMN_ORDER = ["case_id", "activity", "timestamp"]
REQUIRED_COLUMNS = set(REQUIRED_COLUMN_ORDER)


def load_event_log_csv(
    path: str | Path,
    column_mapping: dict[str, str] | None = None,
    include_extra_attributes: bool = True,
) -> pd.DataFrame:
    """Load a CSV and prepare it into the canonical event-log shape."""
    dataframe = pd.read_csv(path)
    return prepare_event_log(
        dataframe,
        column_mapping=column_mapping,
        include_extra_attributes=include_extra_attributes,
    )


def load_uploaded_event_log(
    uploaded_file,
    column_mapping: dict[str, str] | None = None,
    include_extra_attributes: bool = True,
) -> pd.DataFrame:
    """Load an uploaded CSV-like object and prepare canonical event-log data."""
    dataframe = pd.read_csv(uploaded_file)
    return prepare_event_log(
        dataframe,
        column_mapping=column_mapping,
        include_extra_attributes=include_extra_attributes,
    )


def prepare_event_log(
    dataframe: pd.DataFrame,
    column_mapping: dict[str, str] | None = None,
    include_extra_attributes: bool = True,
) -> pd.DataFrame:
    """Apply mapping + canonicalization for downstream analysis.

    Responsibility boundary:
    - This function performs preparation concerns only (mapping, required-column
      structural checks, timestamp dtype conversion, and column ordering).
    - Rich analyzability checks and reporting (warnings/errors/metrics) belong
      in `validation.py` via `validate_event_log`.
    """
    prepared = dataframe.copy()
    prepared = apply_column_mapping(prepared, column_mapping)
    _assert_required_columns(prepared)
    prepared = _convert_timestamp_column(prepared)
    return _reorder_columns(
        prepared, include_extra_attributes=include_extra_attributes
    )


def apply_column_mapping(
    dataframe: pd.DataFrame, column_mapping: dict[str, str] | None
) -> pd.DataFrame:
    """Map source columns to canonical event log names."""
    if not column_mapping:
        return dataframe

    _validate_column_mapping(column_mapping, available_columns=set(dataframe.columns))

    renamed = dataframe.copy()
    source_columns_to_drop: set[str] = set()
    for required_column, source_column in column_mapping.items():
        if required_column in REQUIRED_COLUMNS and source_column in renamed.columns:
            if required_column != source_column:
                renamed[required_column] = renamed[source_column]
                # Keep canonical names only in the prepared event log.
                source_columns_to_drop.add(source_column)

    # Drop source columns that were mapped into required canonical names.
    safe_to_drop = [
        column
        for column in source_columns_to_drop
        if column not in REQUIRED_COLUMNS and column in renamed.columns
    ]
    return renamed.drop(columns=safe_to_drop)


def _validate_column_mapping(
    column_mapping: dict[str, str], available_columns: set[str]
) -> None:
    invalid_required = sorted(set(column_mapping.keys()) - REQUIRED_COLUMNS)
    if invalid_required:
        raise ValueError(
            "Column mapping contains unsupported required fields: "
            f"{', '.join(invalid_required)}."
        )

    missing_sources = sorted(
        source for source in column_mapping.values() if source not in available_columns
    )
    if missing_sources:
        raise ValueError(
            "Column mapping references columns not found in data: "
            f"{', '.join(missing_sources)}."
        )

    selected_sources = list(column_mapping.values())
    duplicate_sources = sorted(
        {source for source in selected_sources if selected_sources.count(source) > 1}
    )
    if duplicate_sources:
        raise ValueError(
            "Invalid column mapping: a source column is mapped to multiple required "
            f"fields: {', '.join(duplicate_sources)}."
        )


def _assert_required_columns(dataframe: pd.DataFrame) -> None:
    missing_columns = REQUIRED_COLUMNS - set(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"Event log is missing required columns: {missing}. "
            f"Required columns are: {', '.join(REQUIRED_COLUMN_ORDER)}."
        )


def _convert_timestamp_column(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convert timestamp to datetime dtype for prepared data.

    Invalid values are coerced to `NaT` during preparation. Whether this is
    acceptable for analysis should be decided by `validation.py`.
    """
    converted = dataframe.copy()
    converted["timestamp"] = pd.to_datetime(
        converted["timestamp"], errors="coerce", format="mixed"
    )
    return converted


def _reorder_columns(
    dataframe: pd.DataFrame, include_extra_attributes: bool = True
) -> pd.DataFrame:
    required = [column for column in REQUIRED_COLUMN_ORDER if column in dataframe.columns]
    if not include_extra_attributes:
        return dataframe[required].copy()

    extras = [column for column in dataframe.columns if column not in REQUIRED_COLUMNS]
    return dataframe[required + extras].copy()
