"""Day 11, SQL: EXPLAIN QUERY PLAN, and what an index buys.

    uv run python lessons/course.py setup         # once: loads the CSVs into var/lessons.sqlite
    uv run python lessons/unit1-sqlite/day11_sql.py

The same two questions as day11_pandas.py on AHU_1: a time range, and a rare duct static value.
SQLite tells us how it will run each query (EXPLAIN QUERY PLAN). The time range seeks into the
PRIMARY KEY; the value filter has no index, so it scans. We then index a TEMP copy of the table
(the lessons database is left untouched) and time the same query before and after.
Compare the printout with day11_pandas.py: the row counts should match; the timings will not.
"""

import os
import sqlite3
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.environ.get("LESSONS_DB", ROOT / "var" / "lessons.sqlite"))
if not DB.exists():
    raise SystemExit(f"{DB} not found. Run:  uv run python lessons/course.py setup")
conn = sqlite3.connect(DB)

PARAMS = {
    "start": "2026-05-01 00:00:00+00:00",  # the week we want: [start, end)
    "end": "2026-05-08 00:00:00+00:00",
    "high": 1.7,  # a rare duct static pressure (inH2O)
}

# 2. The time range. timestamp_utc is the PRIMARY KEY, so SQLite keeps a B-tree on it.
WEEK_SQL = """
SELECT timestamp_utc, da_p_inwc, discharge_air_temp_f
FROM ahu_1
WHERE timestamp_utc >= :start AND timestamp_utc < :end
"""
WEEK_SUMMARY_SQL = """
SELECT count(*) AS rows, avg(da_p_inwc) AS avg_static_inwc
FROM ahu_1
WHERE timestamp_utc >= :start AND timestamp_utc < :end
"""

# 3. A rare value in a column nobody indexed.
HIGH_SQL = """
SELECT timestamp_utc, da_p_inwc, discharge_air_temp_f
FROM ahu_1
WHERE da_p_inwc > :high
"""
# The same filter on a TEMP copy, which is where we will build an index.
COPY_SQL = """
CREATE TEMP TABLE ahu_1_copy AS
SELECT timestamp_utc, da_p_inwc, discharge_air_temp_f FROM ahu_1
"""
HIGH_COPY_SQL = HIGH_SQL.replace("FROM ahu_1", "FROM ahu_1_copy")
INDEX_SQL = "CREATE INDEX temp.copy_da_p ON ahu_1_copy (da_p_inwc)"


def best_ms(fn, repeat=7):
    """Best of `repeat` runs, in milliseconds (the minimum is the least noisy)."""
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return min(times)


def plan(sql, params=()):
    """EXPLAIN QUERY PLAN as text lines: SEARCH = index seek, SCAN = every row."""
    return [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params)]


print(f"AHU_1: {conn.execute('SELECT count(*) FROM ahu_1').fetchone()[0]:,} rows")

print("\nPlan, one week by timestamp_utc (the PRIMARY KEY):")
week_plan = plan(WEEK_SQL, PARAMS)
print("  " + "\n  ".join(week_plan))
week = pd.read_sql_query(WEEK_SQL, conn, params=PARAMS)
t_range = best_ms(lambda: conn.execute(WEEK_SQL, PARAMS).fetchall())
print(f"One week of rows: {len(week)}  ({t_range:.3f} ms)")

print(f"\nPlan, da_p_inwc > {PARAMS['high']} (no index on that column):")
high_plan = plan(HIGH_SQL, PARAMS)
print("  " + "\n  ".join(high_plan))
high = pd.read_sql_query(HIGH_SQL, conn, params=PARAMS)
print(f"Rows with duct static > {PARAMS['high']} inH2O: {len(high)}")

# 4. Index the TEMP copy and run the same query again.
conn.execute(COPY_SQL)
t_before = best_ms(lambda: conn.execute(HIGH_COPY_SQL, PARAMS).fetchall())
plan_before = plan(HIGH_COPY_SQL, PARAMS)
t_build = best_ms(
    lambda: (conn.execute("DROP INDEX IF EXISTS temp.copy_da_p"), conn.execute(INDEX_SQL)), 5
)
t_after = best_ms(lambda: conn.execute(HIGH_COPY_SQL, PARAMS).fetchall())
plan_after = plan(HIGH_COPY_SQL, PARAMS)
high_indexed = pd.read_sql_query(HIGH_COPY_SQL, conn, params=PARAMS)

print("\nTEMP copy, before the index:")
print("  " + "\n  ".join(plan_before))
print("TEMP copy, after CREATE INDEX:")
print("  " + "\n  ".join(plan_after))
print(f"Same rows with the index: {len(high_indexed)}")
print(
    f"  scan {t_before:.3f} ms | indexed lookup {t_after:.3f} ms | build the index {t_build:.3f} ms"
)

# 5. Break-even: how many queries until the one-time build cost is paid back?
saving = t_before - t_after
if saving > 0:
    print(f"  the index pays for itself after about {t_build / saving:.1f} queries")
else:
    print("  at this size the scan is already so cheap that the index never pays for itself")

conn.execute("DROP INDEX temp.copy_da_p")
conn.execute("DROP TABLE temp.ahu_1_copy")  # nothing was written to the lessons database

week_summary = pd.read_sql_query(WEEK_SUMMARY_SQL, conn, params=PARAMS)
RESULTS = {
    "week_rows": week,
    "week_summary": week_summary,
    "high_static_rows": high,
    "plans": {"week": week_plan, "high": high_plan, "before": plan_before, "after": plan_after},
}
