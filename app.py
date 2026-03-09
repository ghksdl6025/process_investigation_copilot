"""Streamlit entry point for Process Investigation Copilot."""

import streamlit as st
from src.process_investigation_copilot.ui import (
    apply_global_ui,
    ensure_active_dataset_restored,
    render_sidebar_branding,
)

st.set_page_config(
    page_title="Process Investigation Copilot",
    page_icon=":mag:",
    layout="wide",
)

apply_global_ui()
render_sidebar_branding()
ensure_active_dataset_restored()

st.title("Process Investigation Copilot")
st.write(
    "Investigate processing-time increases, identify delay signals, and explore "
    "process bottlenecks from event-log data."
)
st.caption("Purpose: summary-first process investigation from event-log data.")

cta_col1, cta_col2 = st.columns(2)
if cta_col1.button("Upload event log", type="primary", use_container_width=True):
    st.switch_page("pages/1_Upload.py")

if cta_col2.button("Try sample dataset", use_container_width=True):
    st.session_state["load_sample_from_home"] = True
    st.switch_page("pages/1_Upload.py")

st.markdown("#### Quick Start")
step_col1, step_col2, step_col3 = st.columns(3)
step_col1.markdown("**1. Upload event log**")
step_col1.caption("Map case ID, activity, and timestamp columns.")
step_col2.markdown("**2. Review dashboard metrics**")
step_col2.caption("Check period changes, slow-case ratio, and key comparisons.")
step_col3.markdown("**3. Investigate delays and bottlenecks**")
step_col3.caption("Use guided questions, evidence, and process views.")

st.info("Next step: upload your dataset (or try sample data) to start the workflow.")
