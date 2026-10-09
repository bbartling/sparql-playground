from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from brickts.settings import Settings
from brickts.store.base import Sample
from brickts.store.sqlite import SqliteTimeseriesStore

log = logging.getLogger(__name__)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_datasets(settings: Settings) -> list[dict]:
    path = settings.datasets_path
    return json.loads(path.read_text())


def load_mapping(mapping_path: Path) -> dict[str, str]:
    """source_column -> timeseries_id"""
    out: dict[str, str] = {}
    with mapping_path.open(newline="") as f:
        for row in csv.DictReader(f):
            out[row["source_column"]] = row["timeseries_id"]
    return out


def wide_csv_to_samples(
    csv_path: Path,
    column_to_ts: dict[str, str],
    *,
    nrows: int | None = None,
) -> tuple[dict[str, list[Sample]], int]:
    df = pd.read_csv(csv_path, nrows=nrows)
    if "timestamp_utc" not in df.columns:
        raise ValueError("timestamp_utc column required")
    ts_col = pd.to_datetime(df["timestamp_utc"], utc=True)
    epoch = (ts_col.astype("int64") // 1_000_000_000).astype(int)
    series: dict[str, list[Sample]] = {tid: [] for tid in column_to_ts.values()}
    cell_count = 0
    for col, tid in column_to_ts.items():
        if col not in df.columns:
            raise ValueError(f"column {col} missing from CSV")
        values = df[col]
        for i, val in enumerate(values):
            if pd.isna(val):
                continue
            series[tid].append(Sample(ts=int(epoch.iloc[i]), value=float(val)))
            cell_count += 1
    return series, cell_count


def bootstrap_dataset(
    store: SqliteTimeseriesStore,
    *,
    dataset_key: str,
    csv_path: Path,
    mapping_path: Path,
    force: bool = False,
    nrows: int | None = None,
) -> str:
    digest = _sha256_file(csv_path)
    prev = store.ingest_log_get(dataset_key)
    if prev and prev[0] == digest and not force:
        log.info("bootstrap skipped", extra={"dataset": dataset_key, "sha256": digest})
        return "skipped"
    mapping = load_mapping(mapping_path)
    series, cell_count = wide_csv_to_samples(csv_path, mapping, nrows=nrows)
    for tid, samples in series.items():
        store.write(tid, samples)
    now = datetime.now(UTC).isoformat()
    store.ingest_log_set(dataset_key, digest, cell_count, now)
    log.info(
        "bootstrap complete",
        extra={"dataset": dataset_key, "cells": cell_count, "sha256": digest},
    )
    return "loaded"


def bootstrap_all(
    settings: Settings, *, force: bool = False, nrows: int | None = None
) -> list[str]:
    store = SqliteTimeseriesStore(settings.db_path)
    try:
        results: list[str] = []
        for ds in load_datasets(settings):
            key = f"{ds['building']}/{ds['equipment']}"
            root = settings.data_dir.parent
            csv_path = Path(ds["csv"])
            if not csv_path.is_absolute():
                csv_path = root / csv_path
            mapping_path = Path(ds["mapping"])
            if not mapping_path.is_absolute():
                mapping_path = root / mapping_path
            results.append(
                bootstrap_dataset(
                    store,
                    dataset_key=key,
                    csv_path=csv_path,
                    mapping_path=mapping_path,
                    force=force,
                    nrows=nrows,
                )
            )
        return results
    finally:
        store.close()
