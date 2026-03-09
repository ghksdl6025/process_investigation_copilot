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
from src.process_investigation_copilot.persistence import (
    clear_persisted_dataset,
    persist_active_dataset,
)
from src.process_investigation_copilot.validation import ValidationReport, validate_event_log
from src.process_investigation_copilot.ui import (
    apply_global_ui,
    ensure_active_dataset_restored,
    render_sidebar_branding,
)

apply_global_ui()
render_sidebar_branding()
ensure_active_dataset_restored()

st.title("Upload Dataset")
st.write(
    "Start by loading an event log CSV and mapping required fields "
    "(`case_id`, `activity`, `timestamp`)."
)
st.caption("Workflow: Upload -> Dashboard -> Investigation -> Process View")


def _warning_with_impact(issue: dict) -> str:
    message = issue["message"]
    code = issue.get("code", "")
    if code == "timestamp_parse_partial":
        message += " Impact: time-based comparisons and bottleneck views may be less reliable."
    elif code == "duplicate_rows":
        message += " Impact: counts and frequency-based metrics may be inflated."
    elif code.startswith("missing_values_"):
        message += " Impact: some rows may be excluded from downstream calculations."
    return message


def _render_validation_report(report_payload: dict, source_label: str | None) -> None:
    st.subheader("Validation Summary")
    if source_label:
        st.caption(f"Dataset source: {source_label}")

    blocking = report_payload.get("blocking_errors", [])
    warnings = report_payload.get("warnings", [])
    metrics = report_payload.get("metrics", {})
    is_valid = bool(report_payload.get("is_valid", False))
    timestamp_success = float(metrics.get("timestamp_parse_success_rate", 0.0))

    has_material_limitation = (
        len(warnings) > 0
        and (
            timestamp_success < 0.9
            or metrics.get("duplicate_row_count", 0) > 0
            or any(
                int(metrics.get(f"missing_{column}", 0)) > 0
                for column in REQUIRED_COLUMNS
            )
        )
    )

    if not is_valid:
        overall_status = "Action Needed"
        status_message = "Blocking data issues must be fixed before analysis."
        status_renderer = st.error
    elif has_material_limitation:
        overall_status = "Ready With Limitations"
        status_message = "Analysis can run, but quality limitations may affect results."
        status_renderer = st.warning
    else:
        overall_status = "Ready For Analysis"
        status_message = "Dataset passed core analyzability checks."
        status_renderer = st.success

    top_issue = None
    if blocking:
        top_issue = blocking[0]["message"]
    elif warnings:
        top_issue = _warning_with_impact(warnings[0])

    status_text = f"**Dataset status:** {overall_status}\n\n{status_message}"
    if top_issue:
        status_text += f"\n\n**Most important issue:** {top_issue}"
    status_renderer(status_text)

    st.markdown("**Required fixes**")
    if blocking:
        for issue in blocking:
            st.write(f"- {issue['message']}")
    else:
        st.write("- None")

    st.markdown("**Quality notes**")
    if warnings:
        for issue in warnings:
            st.write(f"- {_warning_with_impact(issue)}")
    else:
        st.write("- None")

    st.markdown("**Dataset Profile**")
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("Rows", metrics.get("row_count", "N/A"))
    mcol2.metric("Cases", metrics.get("case_count", "N/A"))
    mcol3.metric("Activities", metrics.get("activity_count", "N/A"))
    mcol4.metric(
        "Timestamp Parse",
        (
            f"{metrics.get('timestamp_parse_success_rate', 0.0):.1%}"
            if metrics.get("timestamp_total") is not None
            else "N/A"
        ),
    )

    dcol1, dcol2 = st.columns(2)
    dcol1.write(f"**Date range start:** {metrics.get('date_range_start', 'N/A')}")
    dcol2.write(f"**Date range end:** {metrics.get('date_range_end', 'N/A')}")
    with st.expander("Additional profile details"):
        st.write(f"- Duplicate rows: {metrics.get('duplicate_row_count', 0)}")
        st.write(f"- Total columns: {metrics.get('column_count', 'N/A')}")
        for column in sorted(REQUIRED_COLUMNS):
            missing_count = metrics.get(f"missing_{column}")
            missing_rate = metrics.get(f"missing_{column}_rate")
            if missing_count is not None:
                rate_text = (
                    f" ({float(missing_rate):.1%})"
                    if missing_rate is not None
                    else ""
                )
                st.write(f"- Missing `{column}`: {missing_count}{rate_text}")

    st.markdown("**Next step**")
    if not is_valid:
        st.info(
            "Fix required issues, then reload this dataset. "
            "When status changes to ready, continue to Dashboard."
        )
    elif has_material_limitation:
        st.info(
            "You can continue to Dashboard and Investigation. "
            "Use extra caution for time-based findings until quality issues are improved."
        )
    else:
        st.info(
            "Continue to Dashboard for KPI review, then open Investigation for delay analysis."
        )


def _validate_and_store(
    raw_dataframe: pd.DataFrame,
    column_mapping: dict[str, str] | None,
    include_extra_attributes: bool,
    source_label: str,
    original_filename: str | None = None,
) -> None:
    mapped_dataframe = apply_column_mapping(raw_dataframe, column_mapping)
    report: ValidationReport = validate_event_log(
        mapped_dataframe, required_columns=REQUIRED_COLUMNS
    )
    st.session_state["validation_report"] = report.to_dict()
    st.session_state["validation_source"] = source_label

    if report.is_valid:
        prepared_event_log = prepare_event_log(
            raw_dataframe,
            column_mapping=column_mapping,
            include_extra_attributes=include_extra_attributes,
        )
        st.session_state["event_log"] = prepared_event_log
        st.session_state["active_event_log_source"] = source_label
        persisted_meta = persist_active_dataset(
            event_log=prepared_event_log,
            source_label=source_label,
            original_filename=original_filename,
            column_mapping=column_mapping,
            validation_report=report.to_dict(),
            validation_source=source_label,
        )
        st.session_state["active_dataset_identifier"] = persisted_meta.get("dataset_identifier")
        st.session_state["active_dataset_name"] = persisted_meta.get("dataset_name")
        st.session_state["active_dataset_file_path"] = persisted_meta.get("persisted_file_path")
        st.session_state["active_column_mapping"] = column_mapping or {}
        st.success(f"Loaded {source_label}")
    else:
        st.session_state.pop("event_log", None)
        st.session_state.pop("active_event_log_source", None)
        st.session_state.pop("active_dataset_identifier", None)
        st.session_state.pop("active_dataset_name", None)
        st.session_state.pop("active_dataset_file_path", None)
        st.session_state.pop("active_column_mapping", None)
        clear_persisted_dataset()


include_extra_attributes = st.checkbox(
    "Include extra attributes in analysis (columns beyond case_id/activity/timestamp)",
    value=True,
)

active_source = st.session_state.get("active_event_log_source")
st.markdown("### Current Status")
if active_source:
    st.info(f"Active dataset: {active_source}")
    if st.button("Clear active dataset"):
        st.session_state.pop("event_log", None)
        st.session_state.pop("active_event_log_source", None)
        st.session_state.pop("active_dataset_identifier", None)
        st.session_state.pop("active_dataset_name", None)
        st.session_state.pop("active_dataset_file_path", None)
        st.session_state.pop("active_column_mapping", None)
        st.session_state.pop("validation_report", None)
        st.session_state.pop("validation_source", None)
        clear_persisted_dataset()
        st.success("Active dataset cleared.")
        st.rerun()
else:
    st.info("Active dataset: none")

st.markdown("**Primary action: upload your dataset**")
uploaded_file = st.file_uploader("Upload event log CSV", type=["csv"])
st.caption("Recommended for real analysis.")

st.markdown("**Secondary action: use bundled sample data**")
if st.button("Load bundled sample CSV"):
    sample_path = Path("data/sample_event_log.csv")
    try:
        raw_sample = pd.read_csv(sample_path)
        _validate_and_store(
            raw_dataframe=raw_sample,
            column_mapping=None,
            include_extra_attributes=include_extra_attributes,
            source_label=f"sample file: {sample_path}",
            original_filename=sample_path.name,
        )
    except Exception as error:  # noqa: BLE001
        st.error(f"Failed to load sample CSV: {error}")

if st.session_state.pop("load_sample_from_home", False):
    sample_path = Path("data/sample_event_log.csv")
    try:
        raw_sample = pd.read_csv(sample_path)
        _validate_and_store(
            raw_dataframe=raw_sample,
            column_mapping=None,
            include_extra_attributes=include_extra_attributes,
            source_label=f"sample file: {sample_path}",
            original_filename=sample_path.name,
        )
    except Exception as error:  # noqa: BLE001
        st.error(f"Failed to auto-load sample CSV: {error}")
st.caption("Useful for a quick product walkthrough.")

st.divider()
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
            type="primary",
        ):
            _validate_and_store(
                raw_dataframe=raw_dataframe,
                column_mapping=mapping,
                include_extra_attributes=include_extra_attributes,
                source_label=f"uploaded file: {uploaded_file.name}",
                original_filename=uploaded_file.name,
            )
    except Exception as error:  # noqa: BLE001
        st.error(f"Failed to load uploaded CSV: {error}")

validation_report = st.session_state.get("validation_report")
validation_source = st.session_state.get("validation_source")
if validation_report is not None:
    st.divider()
    _render_validation_report(validation_report, validation_source)

event_log = st.session_state.get("event_log")
if event_log is not None:
    st.divider()
    st.subheader("Preview")
    st.caption("Quick data check. Validation status above is the main readiness signal.")
    st.dataframe(event_log.head(8), use_container_width=True)
    with st.expander("Show full preview (first 20 rows)", expanded=False):
        st.dataframe(event_log.head(20), use_container_width=True)
else:
    st.info("No event log loaded yet.")
