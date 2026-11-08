"""Day 2, SQL: SELECT, WHERE, ORDER BY, LIMIT on a few AHU_1 columns, values as parameters.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day02_sql.py

The same questions as day02_pandas.py, answered by SQLite on the same rows. SQLite does all the
work; pandas only turns the result rows into a table for printing.
Every value reaches SQL as a named parameter (:limit), never pasted in with an f-string.
Compare the printout with day02_pandas.py: the numbers should match.
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)


def q(sql, params=None):
    """Run one SELECT with its parameters and return a DataFrame."""
    return pd.read_sql_query(sql, conn, params=params or {})


# 1. The table is `ahu_1` (the CSV, unchanged). SELECT names the columns; FROM names the table.

# 2. SELECT a few columns, ORDER BY time, LIMIT 3: the first three outside air readings.
FIRST3_SQL = """
SELECT timestamp_utc, outside_air_temp_f
FROM ahu_1
ORDER BY timestamp_utc
LIMIT 3
"""

# 3. Hottest and coldest reading: sort by value, keep one row. The second sort key breaks ties.
HOTTEST_SQL = """
SELECT timestamp_utc, outside_air_temp_f
FROM ahu_1
ORDER BY outside_air_temp_f DESC, timestamp_utc
LIMIT 1
"""
COLDEST_SQL = """
SELECT timestamp_utc, outside_air_temp_f
FROM ahu_1
ORDER BY outside_air_temp_f, timestamp_utc
LIMIT 1
"""

# 4. WHERE with the limit bound as a parameter: static above 1.5 inH2O.
HIGH_STATIC_SQL = "SELECT count(*) AS n FROM ahu_1 WHERE da_p_inwc > :limit"

# 5. Two conditions: fan running AND hot outside. Hottest five such rows.
HOT_RUNNING_SQL = """
SELECT timestamp_utc, outside_air_temp_f, da_p_inwc
FROM ahu_1
WHERE supply_fan_status = 1 AND outside_air_temp_f > :min_oat
ORDER BY outside_air_temp_f DESC, timestamp_utc
LIMIT 5
"""

# 6. A time range. timestamp_utc is the PRIMARY KEY, so SQLite finds `>= :start` with a B-tree
# seek and reads on to `< :end`: O(log n + k). A pandas mask compares every row: O(n).
JULY_1_SQL = """
SELECT count(*) AS n FROM ahu_1
WHERE timestamp_utc >= :start AND timestamp_utc < :end
"""

# 7. Hostile input is just a string that matches nothing: it travels beside the SQL, not inside it.
HOSTILE_SQL = "SELECT count(*) AS n FROM ahu_1 WHERE timestamp_utc = :ts"

# 8. Which values does a status point take? (DISTINCT)
FAN_VALUES_SQL = """
SELECT DISTINCT supply_fan_status AS fan_status FROM ahu_1 ORDER BY fan_status
"""

START, END = "2026-07-01 00:00:00+00:00", "2026-07-02 00:00:00+00:00"
first3 = q(FIRST3_SQL)
hottest = q(HOTTEST_SQL)
coldest = q(COLDEST_SQL)
high_static = q(HIGH_STATIC_SQL, {"limit": 1.5})
hot_running = q(HOT_RUNNING_SQL, {"min_oat": 95.0})
july_1 = q(JULY_1_SQL, {"start": START, "end": END})
hostile = q(HOSTILE_SQL, {"ts": "x' OR '1'='1"})
fan_values = q(FAN_VALUES_SQL)

# What did SQLite plan for the time range? SEARCH ... USING INDEX is a seek; SCAN reads every row.
plan = conn.execute("EXPLAIN QUERY PLAN " + JULY_1_SQL, {"start": START, "end": END}).fetchall()

RESULTS = {
    "first3": first3,
    "hottest": hottest,
    "coldest": coldest,
    "high_static": high_static,
    "hot_running": hot_running,
    "july_1": july_1,
    "hostile": hostile,
    "fan_values": fan_values,
}

print("first three outside air readings:")
print(first3.to_string(index=False))
print("\nhottest / coldest reading:")
print(pd.concat([hottest, coldest]).round(2).to_string(index=False))
print("\nreadings with duct static above 1.5 inH2O:", high_static["n"][0])
print("\nhottest five readings above 95.0 F with the fan on:")
print(hot_running.round(3).to_string(index=False))
print("\nreadings on 2026-07-01 (UTC):", july_1["n"][0])
print("query plan for that range:", plan[0][-1])
print("rows matching a hostile string:", hostile["n"][0])
print("fan status takes the values:", fan_values["fan_status"].tolist())
