"""Upload page for loading event log data into session state."""

from pathlib import Path

import pandas as pd
import streamlit as st

from src.process_investigation_copilot.data_loader import (
    REQUIRED_COLUMN_ORDER,
    REQUIRED_COLUMNS,
    apply_column_mapping,
    prepare_event_log,
)
from src.process_investigation_copilot.validation import ValidationReport, validate_event_log

st.title("Upload Event Log")
st.write(
    "Load a CSV file and map your column names to required fields "
    "(`case_id`, `activity`, `timestamp`)."
)


def _render_validation_report(report_payload: dict, source_label: str | None) -> None:
    st.subheader("Validation Summary")
    if source_label:
        st.caption(f"Validation source: {source_label}")

    if report_payload.get("is_valid", False):
        st.success("No blocking validation errors.")
    else:
        st.error("Blocking validation errors found. Fix these before continuing.")

    blocking = report_payload.get("blocking_errors", [])
    warnings = report_payload.get("warnings", [])
    metrics = report_payload.get("metrics", {})

    st.markdown("**Blocking Errors**")
    if blocking:
        for issue in blocking:
            st.write(f"- {issue['message']}")
    else:
        st.write("- None")

    st.markdown("**Warnings**")
    if warnings:
        for issue in warnings:
            st.write(f"- {issue['message']}")
    else:
        st.write("- None")

    st.markdown("**Dataset Profile**")
    summary_metrics = {
        "Analyzability": metrics.get("analyzability_status", "N/A"),
        "Rows": metrics.get("row_count"),
        "Columns": metrics.get("column_count"),
        "Cases": metrics.get("case_count"),
        "Activities": metrics.get("activity_count"),
        "Duplicate Rows": metrics.get("duplicate_row_count"),
        "Timestamp Parse Success": (
            f"{metrics.get('timestamp_parse_success_rate', 0.0):.1%}"
            if metrics.get("timestamp_total") is not None
            else "N/A"
        ),
        "Date Range Start": metrics.get("date_range_start"),
        "Date Range End": metrics.get("date_range_end"),
    }
    st.json(summary_metrics)


def _validate_and_store(
    raw_dataframe: pd.DataFrame,
    column_mapping: dict[str, str] | None,
    include_extra_attributes: bool,
    source_label: str,
) -> None:
    mapped_dataframe = apply_column_mapping(raw_dataframe, column_mapping)
    report: ValidationReport = validate_event_log(
        mapped_dataframe, required_columns=REQUIRED_COLUMNS
    )
    st.session_state["validation_report"] = report.to_dict()
    st.session_state["validation_source"] = source_label

    if report.is_valid:
        st.session_state["event_log"] = prepare_event_log(
            raw_dataframe,
            column_mapping=column_mapping,
            include_extra_attributes=include_extra_attributes,
        )
        st.session_state["active_event_log_source"] = source_label
        st.success(f"Loaded {source_label}")
    else:
        st.session_state.pop("event_log", None)
        st.session_state.pop("active_event_log_source", None)


include_extra_attributes = st.checkbox(
    "Include extra attributes in analysis (columns beyond case_id/activity/timestamp)",
    value=True,
)

active_source = st.session_state.get("active_event_log_source")
if active_source:
    st.info(f"Active dataset: {active_source}")
else:
    st.info("Active dataset: none")

if st.button("Load bundled sample CSV", type="primary"):
    sample_path = Path("data/sample_event_log.csv")
    try:
        raw_sample = pd.read_csv(sample_path)
        _validate_and_store(
            raw_dataframe=raw_sample,
            column_mapping=None,
            include_extra_attributes=include_extra_attributes,
            source_label=f"sample file: {sample_path}",
        )
    except Exception as error:  # noqa: BLE001
        st.error(f"Failed to load sample CSV: {error}")

uploaded_file = st.file_uploader("Upload event log CSV", type=["csv"])
if uploaded_file is not None:
    try:
        raw_dataframe = pd.read_csv(uploaded_file)
        available_columns = list(raw_dataframe.columns)

        st.subheader("Column Mapping")
        st.caption(
            "Select which uploaded columns represent each required field. "
            "Mappings are auto-selected when names match."
        )

        mapping: dict[str, str] = {}
        mapping_options = ["-- select column --", *available_columns]

        for required in REQUIRED_COLUMN_ORDER:
            default_option = "-- select column --"
            for candidate in available_columns:
                if candidate.strip().lower() == required:
                    default_option = candidate
                    break
            default_index = mapping_options.index(default_option)
            selected = st.selectbox(
                f"Map `{required}`",
                options=mapping_options,
                index=default_index,
                key=f"map_{required}",
            )
            if selected != "-- select column --":
                mapping[required] = selected

        selected_sources = list(mapping.values())
        duplicate_sources = sorted(
            {source for source in selected_sources if selected_sources.count(source) > 1}
        )
        if duplicate_sources:
            st.warning(
                "Invalid mapping: the same uploaded column is assigned to multiple "
                f"required fields: {', '.join(duplicate_sources)}"
            )

        if st.button(
            "Load uploaded CSV with mapping",
            disabled=bool(duplicate_sources),
        ):
            _validate_and_store(
                raw_dataframe=raw_dataframe,
                column_mapping=mapping,
                include_extra_attributes=include_extra_attributes,
                source_label=f"uploaded file: {uploaded_file.name}",
            )
    except Exception as error:  # noqa: BLE001
        st.error(f"Failed to load uploaded CSV: {error}")

validation_report = st.session_state.get("validation_report")
validation_source = st.session_state.get("validation_source")
if validation_report is not None:
    _render_validation_report(validation_report, validation_source)

event_log = st.session_state.get("event_log")
if event_log is not None:
    st.subheader("Preview")
    st.dataframe(event_log.head(20), use_container_width=True)
else:
    st.info("No event log loaded yet.")
