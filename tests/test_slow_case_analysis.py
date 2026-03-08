"""Tests for slow-case detection and comparison outputs."""

from pathlib import Path

import pandas as pd

from src.process_investigation_copilot.analysis.slow_case_analysis import (
    build_slow_case_comparison,
)


def test_slow_case_comparison_on_sample_csv() -> None:
    event_log = pd.read_csv(Path("data/sample_event_log.csv"))
    result = build_slow_case_comparison(event_log)

    assert 0.0 <= result.summary["slow_case_ratio"] <= 1.0
    assert int(result.summary["total_case_count"]) == 3
    assert int(result.summary["slow_case_count"]) >= 1

    assert "activity" in result.activity_comparison.columns
    assert "share_delta" in result.activity_comparison.columns

    assert "case_group" in result.rework_comparison.columns
    assert "avg_rework_event_count" in result.rework_comparison.columns

    assert "variant" in result.variant_comparison.columns
    assert "slow_case_count" in result.variant_comparison.columns


def test_slow_case_comparison_excludes_missing_case_rows() -> None:
    event_log = pd.read_csv(Path("data/sample_event_log.csv"))
    orphan_row = pd.DataFrame(
        [{"case_id": None, "activity": "ORPHAN_ACTIVITY", "timestamp": "2026-01-06T10:00:00"}]
    )
    event_log = pd.concat([event_log, orphan_row], ignore_index=True)

    result = build_slow_case_comparison(event_log)

    assert int(result.summary["total_case_count"]) == 3
    assert "ORPHAN_ACTIVITY" not in set(result.activity_comparison["activity"].tolist())
