"""Local persistence helpers for restoring active dataset across refresh."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

PERSIST_DIR = Path("data")
PERSIST_DATA_PATH = PERSIST_DIR / ".active_event_log.csv"
PERSIST_META_PATH = PERSIST_DIR / ".active_event_log_meta.json"


def persist_active_dataset(
    *,
    event_log: pd.DataFrame,
    source_label: str,
    original_filename: str | None,
    column_mapping: dict[str, str] | None,
    validation_report: dict[str, Any] | None,
    validation_source: str | None,
) -> dict[str, Any]:
    """Persist active dataset and metadata for cross-refresh restoration."""
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    event_log.to_csv(PERSIST_DATA_PATH, index=False)
    metadata = {
        "dataset_identifier": str(uuid4()),
        "dataset_name": original_filename or source_label,
        "original_filename": original_filename,
        "source_label": source_label,
        "persisted_file_path": str(PERSIST_DATA_PATH),
        "column_mapping": column_mapping or {},
        "validation_report": validation_report,
        "validation_source": validation_source,
    }
    PERSIST_META_PATH.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")
    return metadata


def clear_persisted_dataset() -> None:
    """Clear persisted dataset and metadata if present."""
    if PERSIST_DATA_PATH.exists():
        PERSIST_DATA_PATH.unlink()
    if PERSIST_META_PATH.exists():
        PERSIST_META_PATH.unlink()


def restore_persisted_dataset() -> dict[str, Any]:
    """Restore persisted dataset payload with status.

    Returns:
    - {"status": "missing"} when nothing persisted
    - {"status": "restored", "event_log": DataFrame, "metadata": {...}} on success
    - {"status": "error", "message": "..."} on failure
    """
    if not PERSIST_DATA_PATH.exists() or not PERSIST_META_PATH.exists():
        return {"status": "missing"}
    try:
        metadata = json.loads(PERSIST_META_PATH.read_text(encoding="utf-8"))
        event_log = pd.read_csv(PERSIST_DATA_PATH)
        if "timestamp" in event_log.columns:
            event_log["timestamp"] = pd.to_datetime(event_log["timestamp"], errors="coerce", format="mixed")
        return {"status": "restored", "event_log": event_log, "metadata": metadata}
    except Exception as error:  # noqa: BLE001
        return {"status": "error", "message": str(error)}
