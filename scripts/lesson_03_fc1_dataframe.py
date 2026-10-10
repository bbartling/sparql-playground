#!/usr/bin/env python3
"""Lesson 3 — pull one month of samples and build a pandas DataFrame for FC1.

Builds on lesson 2 (SPARQL point discovery). Still no CLI args.

  uv run python scripts/lesson_03_fc1_dataframe.py

Steps:
  1) SPARQL → three point ids (lesson 2)
  2) GET /api/points/{id}/timeseries?start=&end= for each
  3) Align into a DataFrame with Open-FDD column names
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lesson_01_mech_summary import client  # noqa: E402
from lesson_02_fc1_points import find_fc1_points  # noqa: E402
from lesson_config import BASE_URL, END_ISO, EQUIPMENT, START_ISO  # noqa: E402


def iso_to_unix(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp())


def fetch_series(http, point_id: str, start: int, end: int) -> pd.Series:
    r = http.get(
        f"/api/points/{point_id}/timeseries",
        params={"start": start, "end": end},
    )
    r.raise_for_status()
    samples = r.json()["samples"]
    idx = pd.to_datetime([s["ts"] for s in samples], unit="s", utc=True)
    return pd.Series([s["value"] for s in samples], index=idx, name=point_id)


def build_fc1_dataframe(http) -> pd.DataFrame:
    start = iso_to_unix(START_ISO)
    end = iso_to_unix(END_ISO)
    print(f"Window: {START_ISO} → {END_ISO}  (unix {start} … {end})")

    points = find_fc1_points(http)
    series = {}
    for role, info in points.items():
        pid = info["point_id"]
        s = fetch_series(http, pid, start, end)
        print(f"  {role:28s} {pid}: {len(s)} samples")
        series[role] = s

    df = pd.DataFrame(series).sort_index()
    df.attrs["equipment_id"] = EQUIPMENT
    df.attrs["equipment_type"] = "ahu"
    return df


def main() -> None:
    print(f"BASE_URL = {BASE_URL}")
    print(f"EQUIPMENT = {EQUIPMENT}")

    with client() as http:
        df = build_fc1_dataframe(http)

    print("\nDataFrame ready for FC1:")
    print(f"  shape = {df.shape}")
    print(f"  columns = {list(df.columns)}")
    print(f"  attrs = {dict(df.attrs)}")
    print("\nhead():")
    print(df.head())
    print("\ndescribe():")
    print(df.describe())

    print("\nNext: uv run python scripts/lesson_04_run_fc1.py")


if __name__ == "__main__":
    main()
