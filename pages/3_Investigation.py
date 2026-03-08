"""Investigation page with placeholder case-level analyses."""

import streamlit as st

from src.process_investigation_copilot.analysis.investigation import (
    build_investigation_output,
)

st.title("Investigation")

event_log = st.session_state.get("event_log")
if event_log is None:
    st.warning("No event log found in session. Go to Upload page first.")
    st.stop()

investigation = build_investigation_output(event_log)

st.subheader("Case Metrics")
st.dataframe(investigation.case_metrics, use_container_width=True)

st.subheader("Case Durations (hours)")
st.dataframe(investigation.case_durations, use_container_width=True)

st.subheader("Placeholder Flags")
st.dataframe(investigation.flags, use_container_width=True)
