# Day 17 (SQL): the same counts as an aggregate, and what pulling the rows out of SQLite costs.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day17_sql.py

import sqlite3
import tracemalloc

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

N = 100_000  # rows of AHU_1
settings = {"n": N, "tolerance_pa": 25, "hours_per_row": 5 / 60}

# tracemalloc.start() ... get_traced_memory() measures the peak Python memory in between.

# 1. The aggregate: SQLite scans the rows, Python only receives one row
sql = """
SELECT SUM(fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa) AS fault_rows,
       SUM(fan_status = 1) * :hours_per_row AS run_hours
FROM synthetic
WHERE rowid <= :n
"""
tracemalloc.start()
fault_rows, run_hours = conn.execute(sql, settings).fetchone()
peak_aggregate = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()

# 2. Pulling the rows out instead (no maths, just the transfer): fetchall() makes a list
rows_sql = "SELECT fan_status, static_pa, setpoint_pa FROM synthetic WHERE rowid <= :n"
tracemalloc.start()
rows = conn.execute(rows_sql, settings).fetchall()
peak_fetchall = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
del rows

# 3. A stream: loop over the cursor, one row at a time
tracemalloc.start()
count = 0
for _ in conn.execute(rows_sql, settings):  # _ : we only count the rows, we don't use them
    count = count + 1
peak_stream = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()

# 4. The whole result as a DataFrame
tracemalloc.start()
whole = pd.read_sql_query(rows_sql, conn, params=settings)
peak_whole = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()

# 5. The DataFrame in chunks of 10,000 rows
tracemalloc.start()
for chunk in pd.read_sql_query(rows_sql, conn, params=settings, chunksize=10_000):
    count = count + len(chunk)
peak_chunked = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()

print("AHU_1, first", N, "rows")
print("  fault rows:", fault_rows)
print("  run hours: ", round(run_hours, 1))
print("Peak Python memory (MiB)")
print("  SQL aggregate: ", round(peak_aggregate / 2**20, 3))
print("  fetchall list: ", round(peak_fetchall / 2**20, 2))
print("  cursor stream: ", round(peak_stream / 2**20, 2))
print("  whole DataFrame:", round(peak_whole / 2**20, 2))
print("  chunked read:  ", round(peak_chunked / 2**20, 2))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fault_rows": fault_rows, "run_hours": run_hours}
