"""Load the Building 50 CSV exports into one SQLite file for the SQL half of the lessons.

    uv run python lessons/setup_db.py            # writes var/lessons.sqlite (a few seconds)

The pandas scripts read the CSVs directly; the SQL scripts read the same rows from this database.
Nothing is transformed on the way in: one table per CSV, the same column names, the same values.

    ahu_1, ahu_2   <- data/BUILDING_50/AHU_*/history_wide.csv  (one row per 5-minute timestamp)
    fdd_events     <- data/BUILDING_50/AHU_*/fdd_events.csv    (Open-FDD's fault episodes)

Set LESSONS_DB to write (and later read) somewhere else; the tests do that.
"""

from __future__ import annotations

import csv
import os
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "BUILDING_50"
DEFAULT_DB = ROOT / "var" / "lessons.sqlite"
SYNTHETIC_CSV = ROOT / "var" / "synthetic_ahu.csv"  # Week 4's big fake dataset
WEATHER_CSV = ROOT / "var" / "synthetic_weather.csv"  # Day 19's fake hourly weather


def db_path() -> Path:
    return Path(os.environ.get("LESSONS_DB", DEFAULT_DB))


def _number(text: str) -> float | None:
    return float(text) if text != "" else None


def load_wide_csv(conn: sqlite3.Connection, table: str, path: Path) -> int:
    """One table per CSV: timestamp_utc TEXT primary key, other columns REAL (empty -> NULL)."""
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        cols = ", ".join(f'"{c}" REAL' for c in header[1:])
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute(f'CREATE TABLE "{table}" ("{header[0]}" TEXT PRIMARY KEY, {cols})')
        marks = ", ".join("?" * len(header))
        rows = ([r[0], *map(_number, r[1:])] for r in reader)
        conn.executemany(f'INSERT INTO "{table}" VALUES ({marks})', rows)
    return conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]


def load_events(conn: sqlite3.Connection, paths: list[Path]) -> int:
    """Open-FDD's fault episodes for both AHUs in one table, columns as in the CSVs."""
    conn.execute("DROP TABLE IF EXISTS fdd_events")
    conn.execute(
        """CREATE TABLE fdd_events (
            start_time_utc TEXT, end_time_utc TEXT, hvac_system TEXT, rule_name TEXT,
            label TEXT, duration_min REAL, sample_count INTEGER)"""
    )
    for path in paths:
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            conn.executemany(
                "INSERT INTO fdd_events VALUES (?,?,?,?,?,?,?)",
                (
                    (
                        r["start_time_utc"],
                        r["end_time_utc"],
                        r["hvac_system"],
                        r["rule_name"],
                        r["label"],
                        float(r["duration_min"]),
                        int(r["sample_count"]),
                    )
                    for r in reader
                ),
            )
    return conn.execute("SELECT count(*) FROM fdd_events").fetchone()[0]


def write_synthetic_csvs(rows_per_ahu: int = 500_000) -> None:
    """Week 4's fake data: two AHUs x 500,000 rows (about 40 MB) plus hourly weather.

    Made once with a fixed random seed, so every run (and every student) gets identical numbers.
    var/synthetic_ahu.csv      equipment_id, ts, fan_status, static_pa, setpoint_pa, oat_c
    var/synthetic_weather.csv  ts, temp_c   (one row per hour, a few hours missing)
    """
    rng = np.random.default_rng(7)  # the seed
    t0 = 1_773_619_200  # 2026-03-16 00:00 UTC, the first day of Building 50
    n = rows_per_ahu
    pieces = []
    for number in (1, 2):
        row = np.arange(n)
        ts = t0 + row * 300  # one row every 5 minutes (epoch seconds)
        hour = (ts % 86_400) / 3600  # hour of the day, 0-24
        # fan schedule: on from 06:00 to 18:00
        fan_status = ((hour >= 6) & (hour < 18)).astype(int)
        # duct static tracks a 375 Pa setpoint, with noise, while the fan runs;
        # about 0 when it is off
        setpoint_pa = np.full(n, 375.0)
        static_pa = np.where(
            fan_status == 1, setpoint_pa + rng.normal(0, 8, n), rng.normal(0, 2, n)
        )
        # "weak fan": in every 7-day block (2016 rows) the static sags 60 Pa for about 1.7 days
        # (AHU_2's window starts 97 rows later than AHU_1's)
        row_in_week = row % 2016
        weak = (row_in_week >= 300 + (number - 1) * 97) & (row_in_week < 800 + (number - 1) * 97)
        static_pa = np.where(weak & (fan_status == 1), static_pa - 60, static_pa)
        # outside air temperature: a daily wave plus noise (the same wave as the weather below)
        oat_c = 10 + 8 * np.sin((hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.3, n)
        # "sun on the sensor": the reading runs 6 C high for 100 rows in every 2016
        oat_c = np.where((row_in_week >= 1000) & (row_in_week < 1100), oat_c + 6, oat_c)
        pieces.append(
            pd.DataFrame(
                {
                    "equipment_id": f"AHU_{number}",
                    "ts": ts,
                    "fan_status": fan_status,
                    "static_pa": static_pa.round(2),
                    "setpoint_pa": setpoint_pa,
                    "oat_c": oat_c.round(2),
                }
            )
        )
    SYNTHETIC_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(pieces).to_csv(SYNTHETIC_CSV, index=False)

    # Hourly weather: the same daily wave plus noise. 12% of the hours are missing at random,
    # and six hours in a row are missing near the start, like a weather feed with outages.
    hours = n * 300 // 3600 + 1
    weather_ts = t0 + np.arange(hours) * 3600
    hour_of_day = (weather_ts % 86_400) / 3600
    temp_c = 10 + 8 * np.sin((hour_of_day - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.5, hours)
    weather = pd.DataFrame({"ts": weather_ts, "temp_c": temp_c.round(2)})
    keep = rng.random(hours) >= 0.12
    keep[100:106] = False
    weather[keep].to_csv(WEATHER_CSV, index=False)


def load_synthetic(conn: sqlite3.Connection) -> None:
    """Load the two synthetic CSVs as tables `synthetic` and `synthetic_weather` (with indexes)."""
    for table, path in (("synthetic", SYNTHETIC_CSV), ("synthetic_weather", WEATHER_CSV)):
        pd.read_csv(path).to_sql(table, conn, if_exists="replace", index=False, chunksize=100_000)
    conn.execute("CREATE INDEX synthetic_idx ON synthetic (equipment_id, ts)")
    conn.execute("CREATE INDEX synthetic_weather_idx ON synthetic_weather (ts)")


def build(path: Path | None = None) -> Path:
    path = Path(path) if path else db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        for equip in ("AHU_1", "AHU_2"):
            n = load_wide_csv(conn, equip.lower(), DATA / equip / "history_wide.csv")
            print(f"{equip.lower()}: {n:,} rows")
        n = load_events(conn, sorted(DATA.glob("AHU_*/fdd_events.csv")))
        print(f"fdd_events: {n:,} rows")
        write_synthetic_csvs()
        load_synthetic(conn)
        for table in ("synthetic", "synthetic_weather"):
            n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"{table}: {n:,} rows")
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    print(f"wrote {build()}")
    sys.exit(0)
