# Day 11 (SQL): the query plan for one week of rows, and what CREATE INDEX does to a scan.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit1-sqlite/day11_sql.py

import sqlite3
import time

conn = sqlite3.connect("var/lessons.sqlite")

# The week we want: from May 1 up to (not including) May 8
settings = {"start": "2026-05-01 00:00:00+00:00", "end": "2026-05-08 00:00:00+00:00"}

# 1. A temporary copy of the table. A copy has no PRIMARY KEY, so it has no index at all.
conn.execute("CREATE TEMP TABLE copy AS SELECT timestamp_utc, da_p_inwc FROM ahu_1")

week_query = """
SELECT COUNT(*), AVG(da_p_inwc)
FROM copy
WHERE timestamp_utc >= :start AND timestamp_utc < :end
"""

# 2. Scan: the plan says SCAN, and the week is found by testing every row
scan_plan = conn.execute("EXPLAIN QUERY PLAN " + week_query, settings).fetchall()
t0 = time.perf_counter()
week_rows, week_avg = conn.execute(week_query, settings).fetchone()
scan_ms = (time.perf_counter() - t0) * 1000

# 3. Index: build one on timestamp_utc, then ask the same question again
t0 = time.perf_counter()
conn.execute("CREATE INDEX temp.copy_time ON copy (timestamp_utc)")
build_ms = (time.perf_counter() - t0) * 1000

index_plan = conn.execute("EXPLAIN QUERY PLAN " + week_query, settings).fetchall()
t0 = time.perf_counter()
week_rows_indexed = conn.execute(week_query, settings).fetchone()[0]
lookup_ms = (time.perf_counter() - t0) * 1000

# 4. A rare value in a column nobody indexed
high_rows = conn.execute("SELECT COUNT(*) FROM copy WHERE da_p_inwc > 1.7").fetchone()[0]

print("Rows in the week:", week_rows)
print("Rows in the week (index lookup):", week_rows_indexed)
print("Average duct static in the week (inH2O):", round(week_avg, 4))
print("Rows with duct static above 1.7 inH2O:", high_rows)
print("Scan time (ms):", round(scan_ms, 3))
print("Index lookup time (ms):", round(lookup_ms, 3))
print("Time to build the index once (ms):", round(build_ms, 3))
print("Plan before the index:", scan_plan[0][3])
print("Plan after the index: ", index_plan[0][3])

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "week_rows": week_rows,
    "week_rows_indexed": week_rows_indexed,
    "week_avg_static_inwc": week_avg,
    "high_static_rows": high_rows,
}
