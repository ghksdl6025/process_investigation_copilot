"""Streamlit entry point for Process Investigation Copilot."""

import streamlit as st

st.set_page_config(
    page_title="Process Investigation Copilot",
    page_icon=":mag:",
    layout="wide",
)

st.title("Process Investigation Copilot")
st.write(
    "Use the pages in the sidebar to upload an event log, review dashboard metrics, "
    "and inspect placeholder investigation insights."
)

st.info("Start on the **Upload** page to load the bundled sample CSV or your own file.")
