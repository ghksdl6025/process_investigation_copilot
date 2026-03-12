# Process Investigation Copilot

Process Investigation Copilot is a Streamlit MVP for investigating operational event logs.  
It helps users validate data quality, compare recent vs previous performance, inspect delay drivers, explore process paths, and export a shareable investigation report.

## Why This Project

Event-log investigation is often repetitive: load data, validate quality, compute case metrics, compare slow vs normal behavior, then inspect process flow.  
This project packages that workflow into a lightweight, process-aware investigation app.

## Current MVP Features

- Event-log upload with column mapping (`case_id`, `activity`, `timestamp`)
- Active dataset persistence across browser refresh:
  - restores active dataset source, mapping, and validation/session context when available
- Validation and profiling:
  - required-column checks
  - missing values and rates
  - duplicate rows
  - timestamp parsing quality
  - date range, case count, activity count
- Case-level metrics:
  - start/end timestamps
  - duration hours
  - event count
  - unique activity count
  - rework count and rework flag
- Slow-case analysis:
  - slow cases = top 10% by valid duration
  - slow vs non-slow comparison on activities, rework, and variants
- Period and delay analysis:
  - recent vs previous period performance comparison
  - activity-level delay comparison between periods
- Process View (DFG):
  - subsets: all, slow, non-slow, majority cases, top variant, top 3 variants, top 5 variants
  - layouts: top-to-bottom (default) and left-to-right
  - modes: frequency and bottleneck-oriented
  - dense-graph compact rendering and adaptive edge labels
- Investigation report export (PDF):
  - single user-facing export action from Dashboard
  - curated multi-section report (Executive Summary, Data Readiness, Performance Summary, Delay Drivers, Process Snapshot, Investigation, Next Steps)
  - business-readable formatting and compact process snapshot graphic
- Investigation answer composition:
  - unified answer payload between analysis and UI
  - benchmark-question contradiction handling
  - follow-up questions and readable trace summary
- Report architecture migration (in progress):
  - typed report model
  - report composer
  - markdown renderer
  - existing ReportLab PDF exporter still active

## App Pages

- **Home**: guided start and workflow orientation
- **Upload**: load, validate, and restore active datasets
- **Dashboard**: summary KPIs, period comparison, delay signals, and report export
- **Investigation**: grounded explanation blocks and evidence-driven findings
- **Process View**: DFG-based process exploration across subsets/modes

## Quickstart

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Testing

```bash
python -m pytest -q
```

## Project Structure

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
|   |-- persistence.py
|   |-- ui.py
|   |-- validation.py
|   |-- reporting/
|   |   |-- markdown_renderer.py
|   |   |-- pdf_export.py
|   |   |-- report_composer.py
|   |   |-- report_model.py
|   |   `-- __init__.py
|   `-- analysis/
|       |-- activity_delay_analysis.py
|       |-- dashboard_metrics.py
|       |-- explanation_formatter.py
|       |-- case_metrics.py
|       |-- investigation_panel.py
|       |-- investigation_answer_composer.py
|       |-- investigation_summary.py
|       |-- period_comparison.py
|       |-- process_view.py
|       |-- slow_case_analysis.py
|       |-- summary.py
|       `-- investigation.py
|-- tests/
|   |-- test_activity_delay_analysis.py
|   |-- test_case_metrics.py
|   |-- test_explanation_formatter.py
|   |-- test_investigation_answer_composer.py
|   |-- test_investigation_panel.py
|   |-- test_investigation_summary.py
|   |-- test_period_comparison.py
|   |-- test_process_view.py
|   |-- test_report_markdown_pipeline.py
|   `-- test_slow_case_analysis.py
|-- data/sample_event_log.csv
`-- requirements.txt
```

## Recent Updates (2026-03-12)

- Added `InvestigationAnswerPayload` and `Investigation Answer Composer` for unified investigation rendering.
- Improved benchmark-question handling with contradiction-aware direct answers and cautious phrasing.
- Added readable trace summaries and evidence-driven follow-up questions in the Investigation panel.
- Started report-model / markdown-first export migration while preserving the current PDF export path.
- Continued iterating on report process snapshot rendering for a more curated static-report visual.

## Status

This repository is an MVP/portfolio project focused on process-aware investigation workflows, not production deployment.
