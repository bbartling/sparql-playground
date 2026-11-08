"""Day 23, SQL: stable UUIDs, the long `samples` table, and pivoting AHU_1's FC1 inputs to wide.

    uv run python lessons/course.py setup         # once: var/lessons.sqlite (the CSVs)
    uv run python lessons/unit3-modeling/day23_sql.py

Needs var/timeseries.sqlite (the API's database: `uv run bldgts model build && uv run bldgts
bootstrap`). The same computation as day23_pandas.py, done by SQLite: the point list becomes a
TEMP table, long -> wide is MAX(CASE ...) and the CSV comparison is a join across two attached
database files. Compare the printout with day23_pandas.py: the numbers should match."""

import csv
import os
import sqlite3
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POINTS = ROOT / "model" / "points" / "BUILDING_50__AHU_1.csv"
SAMPLES_DB = ROOT / "var" / "timeseries.sqlite"
LESSONS_DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not SAMPLES_DB.exists():
    raise SystemExit(
        f"{SAMPLES_DB} not found. Run:  uv run bldgts model build && uv run bldgts bootstrap"
    )
if not LESSONS_DB.exists():
    raise SystemExit(f"{LESSONS_DB} not found. Run:  uv run python lessons/course.py setup")

ROLE_NAMES = {  # FC1's input contract: role -> the column name the rule uses
    "fan-status": "fan_status",
    "duct-static-pressure": "duct_static_inwc",
    "duct-static-pressure-sp": "duct_static_sp_inwc",
}


def mint(building: str, equipment: str, source_column: str) -> str:
    """UUIDv5 (RFC 9562): SHA-1 of a namespace and a name. SQLite has none, so lend it Python's."""
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"urn:openfdd:{building}:{equipment}:{source_column}")
    )


def quote_ident(name: str, allowed: set[str]) -> str:
    """Identifiers can't be bound (Day 21): accept a name that really exists, then quote it."""
    if name not in allowed:
        raise ValueError(f"unknown column {name!r}")
    return '"' + name.replace('"', '""') + '"'


# Open the API's database read-only; attach the lessons database (the CSV rows) next to it.
conn = sqlite3.connect(f"file:{SAMPLES_DB.as_posix()}?mode=ro", uri=True)
conn.execute("ATTACH DATABASE ? AS les", (f"file:{LESSONS_DB.as_posix()}?mode=ro",))
conn.create_function("uuid5_urn", 3, mint, deterministic=True)

# 1. The point list: which UUID is which role, and which CSV column it came from.
building_id, equipment_id = POINTS.stem.split("__", 1)
conn.execute(
    """CREATE TEMP TABLE point (building_id TEXT, equipment_id TEXT, role TEXT,
                                source_column TEXT, timeseries_id TEXT PRIMARY KEY, col TEXT)"""
)
with open(POINTS, encoding="utf-8", newline="") as f:
    conn.executemany(
        "INSERT INTO point VALUES (?,?,?,?,?,?)",
        [
            (
                building_id,
                equipment_id,
                r["openfdd_role"],
                r["source_column"],
                r["timeseries_id"],
                ROLE_NAMES[r["openfdd_role"]],
            )
            for r in csv.DictReader(f)
            if r["openfdd_role"] in ROLE_NAMES
        ],
    )

# 2. Where did those UUIDs come from? Mint them again from their names and compare.
UUID_SQL = """
SELECT role, source_column, timeseries_id,
       uuid5_urn(building_id, equipment_id, source_column) AS recomputed_uuid,
       timeseries_id = uuid5_urn(building_id, equipment_id, source_column) AS matches
FROM point
ORDER BY role
"""
uuid_check = pd.read_sql_query(UUID_SQL, conn)

# 3. The long table: one row per (timeseries_id, ts). The primary key (timeseries_id, ts) makes
#    "all of one series" a range scan, and WITHOUT ROWID stores the rows in that order.
LONG_SQL = """
SELECT p.role, count(*) AS rows, min(s.ts) AS first_ts, max(s.ts) AS last_ts
FROM samples s
JOIN point p ON p.timeseries_id = s.timeseries_id
GROUP BY p.role
ORDER BY p.role
"""
long_counts = pd.read_sql_query(LONG_SQL, conn)

# 4. Long -> wide: one row per timestamp, one column per role (conditional aggregation, Day 9).
WIDE_SQL = "CREATE TEMP TABLE wide (ts INTEGER PRIMARY KEY, {cols_def}) WITHOUT ROWID"
PIVOT_SQL = """
INSERT INTO wide
SELECT s.ts, {cols}
FROM samples s
JOIN point p ON p.timeseries_id = s.timeseries_id
GROUP BY s.ts
"""
names = list(ROLE_NAMES.values())
conn.execute(WIDE_SQL.format(cols_def=", ".join(f"{n} REAL" for n in names)))
conn.execute(
    PIVOT_SQL.format(
        cols=", ".join(f"MAX(CASE WHEN p.col = '{n}' THEN s.value END)" for n in names)
    )
)
wide = pd.read_sql_query("SELECT * FROM wide ORDER BY ts", conn)

# 5. Compare with the CSV the history came from (table les.ahu_1): same timestamps, same values?
#    The CSV column names come from the point list, so they are whitelisted and quoted.
real = {row[1] for row in conn.execute("PRAGMA les.table_info(ahu_1)")}
role_rows = conn.execute("SELECT role, source_column, col FROM point ORDER BY role").fetchall()
MATCH_SQL = """
SELECT :role AS role, :source_column AS source_column,
       count(*) AS rows_compared,
       sum(c.{src} = w.{col}) AS rows_equal,
       max(abs(c.{src} - w.{col})) AS max_abs_diff
FROM les.ahu_1 c
JOIN wide w ON w.ts = unixepoch(c.timestamp_utc)
"""
parts = [
    pd.read_sql_query(
        MATCH_SQL.format(src=quote_ident(src, real), col=quote_ident(col, set(names))),
        conn,
        params={"role": role, "source_column": src},
    )
    for role, src, col in role_rows
]
csv_match = pd.concat(parts, ignore_index=True)

RESULTS = {
    "uuid_check": uuid_check,
    "long_counts": long_counts,
    "wide": wide,
    "csv_match": csv_match,
}

print("The UUID of each FC1 input, and the same UUID minted again from its name:")
print(uuid_check.to_string(index=False))
print(f"\nLong table: {int(long_counts['rows'].sum()):,} rows for {len(long_counts)} series.")
print(long_counts.to_string(index=False))
print(f"\nWide table: {len(wide):,} rows, one per timestamp. First rows:")
print(wide.head(3).to_string(index=False))
print("\nCompared with the CSV's own columns:")
print(csv_match.to_string(index=False))
