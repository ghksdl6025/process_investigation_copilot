"""Shared UI polish helpers for consistent cross-page presentation."""

from __future__ import annotations

import streamlit as st
from src.process_investigation_copilot.persistence import restore_persisted_dataset


def apply_global_ui() -> None:
    """Apply lightweight, reusable visual styling across app pages."""
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2.0rem;
        }
        h1, h2, h3 {
            letter-spacing: 0.1px;
        }
        h2 {
            margin-top: 1.0rem;
        }
        h3 {
            margin-top: 0.8rem;
        }
        div[data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 0.55rem 0.7rem 0.65rem 0.7rem;
        }
        div[data-testid="stAlert"] {
            border-radius: 10px;
        }
        div[data-testid="stExpander"] {
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            background: #ffffff;
        }
        div[data-testid="stSidebar"] {
            border-right: 1px solid #e5e7eb;
        }
        div[data-testid="stSidebar"] h3 {
            margin-top: 0.2rem;
            margin-bottom: 0.2rem;
        }
        button[kind] {
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_branding() -> None:
    """Render consistent sidebar branding across all pages."""
    st.sidebar.markdown("### Process Investigation Copilot")
    st.sidebar.caption("Deterministic event-log investigation")


def ensure_active_dataset_restored() -> None:
    """Restore active dataset from local persistence when session state is empty."""
    if st.session_state.get("_restore_attempted", False):
        return
    st.session_state["_restore_attempted"] = True

    if st.session_state.get("event_log") is not None:
        return

    restored = restore_persisted_dataset()
    status = restored.get("status")
    if status == "missing":
        return
    if status == "error":
        st.warning(
            "Could not restore the previous active dataset. "
            "Please load the dataset again."
        )
        return

    event_log = restored["event_log"]
    metadata = restored["metadata"]
    st.session_state["event_log"] = event_log
    st.session_state["active_event_log_source"] = metadata.get("source_label")
    st.session_state["active_dataset_identifier"] = metadata.get("dataset_identifier")
    st.session_state["active_dataset_name"] = metadata.get("dataset_name")
    st.session_state["active_dataset_file_path"] = metadata.get("persisted_file_path")
    st.session_state["active_column_mapping"] = metadata.get("column_mapping", {})
    if metadata.get("validation_report") is not None:
        st.session_state["validation_report"] = metadata["validation_report"]
    if metadata.get("validation_source") is not None:
        st.session_state["validation_source"] = metadata["validation_source"]
    st.info(f"Restored active dataset: {metadata.get('dataset_name', 'dataset')}")
