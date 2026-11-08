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

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "BUILDING_50"
DEFAULT_DB = ROOT / "var" / "lessons.sqlite"


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
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    print(f"wrote {build()}")
    sys.exit(0)
