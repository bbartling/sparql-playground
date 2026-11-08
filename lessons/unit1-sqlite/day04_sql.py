"""Day 4, SQL: COUNT, MIN, MAX, AVG, SUM, NULL handling and fan run hours.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day04_sql.py

An aggregate folds many rows into one value. All the aggregates in one SELECT are computed in the
same pass over the rows, and one row comes back. SQLite does all the work; pandas only turns the
result rows into a table for printing.
Compare the printout with day04_pandas.py: the numbers should match.
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


def q(sql, params=None, db=conn):
    """Run one SELECT with its parameters and return a DataFrame."""
    return pd.read_sql_query(sql, db, params=params or {})


# 1. Nothing to load: the tables `ahu_1` and `ahu_2` hold the same rows as the CSVs.

# 2. AHU_1 outside air temperature, whole dataset. count(*) counts rows; count(col) skips NULLs.
OAT_SUMMARY_SQL = """
SELECT count(*)                  AS n,
       count(outside_air_temp_f) AS n_values,
       min(outside_air_temp_f)   AS min_f,
       max(outside_air_temp_f)   AS max_f,
       avg(outside_air_temp_f)   AS avg_f
FROM ahu_1
"""

# 3. The same for one day: a half-open range in the WHERE (Day 2), then the same aggregates.
OAT_DAY_SQL = """
SELECT min(outside_air_temp_f) AS min_f,
       max(outside_air_temp_f) AS max_f,
       avg(outside_air_temp_f) AS avg_f
FROM ahu_1
WHERE timestamp_utc >= :start AND timestamp_utc < :end
"""

# 4. Run hours of the supply fan, per AHU: sum of a 0/1 column x 5 minutes / 60.0.
# Use 60.0, not 60: with two integers SQL divides as integers and drops the remainder.
RUN_HOURS_SQL = """
SELECT 'AHU_1' AS equipment_id,
       sum(supply_fan_status) * 5 / 60.0 AS run_hours,
       avg(supply_fan_status)            AS fraction_running
FROM ahu_1
UNION ALL
SELECT 'AHU_2', sum(supply_fan_status) * 5 / 60.0, avg(supply_fan_status)
FROM ahu_2
"""

# 5. Averages that mislead: static pressure averaged over ALL hours, fan on and off.
AVERAGES_SQL = """
SELECT avg(da_p_inwc)          AS static_inwc,
       avg(da_p_setpoint_inwc) AS static_setpoint_inwc
FROM ahu_1
"""

# 6. NULLs: a three-row table in a throwaway in-memory database. Aggregates skip the NULL.
mem = sqlite3.connect(":memory:")
mem.execute("CREATE TABLE t (value REAL)")
mem.executemany("INSERT INTO t VALUES (?)", [(1.0,), (None,), (3.0,)])
NULL_DEMO_SQL = "SELECT count(*) AS n_rows, count(value) AS n_values, avg(value) AS mean FROM t"

# 7. Integer division: 7 * 5 / 60 is 0 in SQL (integers), 7 * 5 / 60.0 is 0.5833.
DIVISION_SQL = "SELECT 7 * 5 / 60 AS floor_div, 7 * 5 / 60.0 AS true_div"

START, END = "2026-07-01 00:00:00+00:00", "2026-07-02 00:00:00+00:00"
oat_summary = q(OAT_SUMMARY_SQL)
oat_july_1 = q(OAT_DAY_SQL, {"start": START, "end": END})
run_hours = q(RUN_HOURS_SQL)
averages = q(AVERAGES_SQL)
null_demo = q(NULL_DEMO_SQL, db=mem)
division = q(DIVISION_SQL)

RESULTS = {
    "oat_summary": oat_summary,
    "oat_july_1": oat_july_1,
    "run_hours": run_hours,
    "averages": averages,
    "null_demo": null_demo,
    "division": division,
}

print("AHU_1 outside air temperature, whole dataset:")
print(oat_summary.round({"min_f": 2, "max_f": 2, "avg_f": 3}).to_string(index=False))
print("\nthe same for 2026-07-01:")
print(oat_july_1.round(1).to_string(index=False))
print("\nsupply fan run hours (readings with the fan on x 5 min / 60):")
print(run_hours.round(3).to_string(index=False))
print("\nAHU_1 duct static and its setpoint, averaged over every hour (inH2O):")
print(averages.round(3).to_string(index=False))
print("\nthree values, one missing:")
print(null_demo.round(3).to_string(index=False))
print("\n7 * 5 / 60 two ways (floor, true):", division.iloc[0].round(4).tolist())
