# Changelog

## v0.3.0 - 2026-03-09

### Added
- Curated PDF report export with a single user-facing workflow from Dashboard.
- Business-readable report sections: Executive Summary, Data Readiness, Performance Summary, Delay Drivers, Process Snapshot, Investigation, and Next Steps.
- Compact DFG-style process snapshot rendering in exported reports.
- Active dataset persistence and automatic restore after refresh.

### Improved
- Cross-page UX consistency across Upload, Dashboard, Process View, and Investigation.
- Report formatting consistency (numbers, labels, status wording, and section hierarchy).
- Report export resilience with conditional section inclusion when data is missing.

### Notes
- Deterministic analysis-first architecture is preserved.
- No autonomous root-cause claims were introduced.
