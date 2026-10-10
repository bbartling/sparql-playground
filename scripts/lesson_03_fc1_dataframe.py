#!/usr/bin/env python3
"""Lesson 3 — month of samples → pandas DataFrame for FC1.

  1) SPARQL → three point ids (lesson 2)
  2) GET /api/points/{id}/timeseries?start=&end=
  3) Join into columns named for open-fdd roles

  uv run python scripts/lesson_03_fc1_dataframe.py
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from lesson_02_fc1_points import find_fc1_points  # noqa: E402
from lesson_config import (  # noqa: E402
    END_ISO,
    EQUIPMENT,
    START_ISO,
    banner,
    client,
)


def _unix(iso: str) -> int:
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


def build_fc1_dataframe(http, *, quiet: bool = False) -> pd.DataFrame:
    start, end = _unix(START_ISO), _unix(END_ISO)
    if not quiet:
        print(f"\nWindow  {START_ISO}  →  {END_ISO}")

    points = find_fc1_points(http, quiet=quiet)
    series = {}
    for role, pid in points.items():
        s = fetch_series(http, pid, start, end)
        if not quiet:
            print(f"  {role:26s}  {pid:20s}  {len(s):>6} samples")
        series[role] = s

    df = pd.DataFrame(series).sort_index()
    df.attrs.update(equipment_id=EQUIPMENT, equipment_type="ahu")
    return df


def main() -> None:
    banner("Lesson 3 — build FC1 DataFrame")

    with client() as http:
        df = build_fc1_dataframe(http)

    print(f"\nDataFrame  shape={df.shape}  columns={list(df.columns)}")
    print(df.head())
    print()
    print(df.describe().round(3))

    print("\nNext →  uv run python scripts/lesson_04_run_fc1.py")


if __name__ == "__main__":
    main()
