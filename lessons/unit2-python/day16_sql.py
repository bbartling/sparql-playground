# Day 16 (SQL): count FC1 raw faults and fan run hours with one SQL aggregate.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day16_sql.py

import sqlite3
import time

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

# One query does the loop inside the database; only one row comes back.
# (A comparison like fan_status = 1 is 1 or 0 in SQLite, so SUM counts the rows.)
# rowid <= :n means "the first n rows of the table".
sql = """
SELECT SUM(fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa) AS fault_rows,
       SUM(fan_status = 1) * :hours_per_row AS run_hours
FROM synthetic
WHERE rowid <= :n
"""

results = []
for n in [10_000, 100_000, 1_000_000]:
    settings = {"n": n, "tolerance_pa": 25, "hours_per_row": 5 / 60}

    # 1. The aggregate
    start = time.perf_counter()
    fault_rows, run_hours = conn.execute(sql, settings).fetchone()
    sql_seconds = time.perf_counter() - start

    # 2. For comparison: just getting the n rows out of SQLite into a DataFrame
    start = time.perf_counter()
    df = pd.read_sql_query("SELECT * FROM synthetic WHERE rowid <= :n", conn, params={"n": n})
    read_seconds = time.perf_counter() - start

    print("rows:", n)
    print("  fault rows:", fault_rows)
    print("  run hours: ", round(run_hours, 1))
    print(
        "  seconds: SQL aggregate",
        round(sql_seconds, 4),
        "| read rows into pandas",
        round(read_seconds, 3),
    )

    results.append({"rows": n, "fault_rows": fault_rows, "run_hours": run_hours})

fault_by_size = pd.DataFrame(results)

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {"fault_by_size": fault_by_size}
