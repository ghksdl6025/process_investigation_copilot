# Process Investigation Copilot

AI-assisted process investigation tool for event-log data.

This project is a Streamlit-based MVP for exploring delays, slow-case behavior, dominant process paths, and transition bottlenecks from event logs. It combines structured backend analysis with process-oriented DFG views to support investigation workflows on sequential operational data.

## Features

- CSV upload with manual column mapping for:
  - `case_id`
  - `activity`
  - `timestamp`
- Dataset validation and profiling:
  - required columns
  - missing values
  - duplicate rows
  - timestamp parsing quality
  - date range
  - case and activity counts
- Reusable case-level metrics:
  - start and end time
  - duration
  - event count
  - unique activity count
  - rework count and rework flag
- Slow-case analysis:
  - top 10% longest valid cases by duration
  - slow vs non-slow comparison on activity frequency, rework, and variants
- Process View with directly-follows graphs (DFGs):
  - all analyzed cases
  - slow cases
  - non-slow cases
  - majority cases
  - top variant
  - top 3 variants
  - top 5 variants
- Process exploration options:
  - top-to-bottom or left-to-right layout
  - frequency mode
  - bottleneck-oriented mode
  - adaptive edge labels
  - compact rendering for denser graphs

## Why this project

Event logs contain rich signals about how work actually flows, where delays accumulate, and which paths dominate. Investigating these patterns often requires repeated manual slicing, aggregation, and process-view inspection.

This project explores a lightweight, product-style workflow for that investigation process. The focus is on **process-aware analysis**, not on building a generic chatbot.

## App pages

- **Upload**: load and validate event logs
- **Dashboard**: inspect high-level metrics and slow-case comparisons
- **Investigation**: review case-level outputs and heuristic flags
- **Process View**: explore DFGs across different subsets and modes

## Example workflow

1. Upload and validate an event log
2. Review high-level dashboard metrics
3. Inspect slow-case ratio and comparison outputs
4. Explore dominant and slow-case process behavior in the DFG view
5. Use bottleneck mode to surface slower transitions for investigation

## Project structure

```text
.
|-- app.py
|-- pages/
|   |-- 1_Upload.py
|   |-- 2_Dashboard.py
|   |-- 3_Investigation.py
|   `-- 4_Process_View.py
|-- src/process_investigation_copilot/
|   |-- data_loader.py
|   |-- validation.py
|   `-- analysis/
|       |-- dashboard_metrics.py
|       |-- case_metrics.py
|       |-- process_view.py
|       |-- slow_case_analysis.py
|       |-- summary.py
|       `-- investigation.py
|-- tests/
|   |-- test_case_metrics.py
|   |-- test_process_view.py
|   `-- test_slow_case_analysis.py
|-- data/sample_event_log.csv
`-- requirements.txt