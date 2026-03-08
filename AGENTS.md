# AGENTS.md

Project: Process Investigation Copilot

Goal:
Build a small product-style AI-assisted investigation tool for event-log data.

Tech constraints:
- Python
- Streamlit
- pandas
- Keep architecture simple
- Prefer deterministic Python analysis over LLM-heavy logic

Coding rules:
- Separate data loading, validation, analysis, and UI
- Add docstrings to public functions
- Prefer small, testable functions
- Do not introduce unnecessary frameworks
- Use clear error messages in the UI

Definition of done:
- Features must run locally
- Include at least one simple test when adding analysis logic
- Update README when adding major capabilities