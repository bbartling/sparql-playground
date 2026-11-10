# Day 20 (SQL): Day 14's FC1 rule as window SQL, on growing data.
# Run from the repo root (once: uv run python lessons/course.py setup):
#     uv run python lessons/unit2-python/day20_sql.py

import sqlite3
import time

import pandas as pd

conn = sqlite3.connect("var/lessons.sqlite")

settings = {
    "start_ts": 1_773_619_200,  # the synthetic data's first timestamp (epoch seconds)
    "tolerance_pa": 25,  # how far below setpoint counts as "too low"
    "confirm_rows": 2,  # the fault must last 2 rows in a row
}

# The rule, Day 14's steps, on the rows in the temp table `h`. The answer goes in table `fc1`.
# PARTITION BY equipment_id keeps the AHUs apart (a streak at the end of AHU_1 must not run
# into AHU_2).
fc1_sql = """
CREATE TEMP TABLE fc1 AS
WITH
step1 AS (                -- raw fault: fan on AND static more than 25 Pa below setpoint
  SELECT equipment_id, ts,
         fan_status = 1 AND static_pa < setpoint_pa - :tolerance_pa AS raw_fault
  FROM h
),
step2 AS (                -- mark rows where the value changes (a new streak starts)
  SELECT *,
         raw_fault IS NOT LAG(raw_fault) OVER (PARTITION BY equipment_id ORDER BY ts)
           AS new_streak
  FROM step1
),
step3 AS (                -- a running total of those marks numbers each streak
  SELECT *, SUM(new_streak) OVER (PARTITION BY equipment_id ORDER BY ts) AS streak_id
  FROM step2
)
SELECT *,                 -- count rows inside each streak
       ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY ts) AS row_in_streak
FROM step3
"""

totals_sql = """
SELECT SUM(raw_fault = 1 AND row_in_streak >= :confirm_rows),  -- confirmed fault rows
       SUM(raw_fault = 1 AND row_in_streak = :confirm_rows)    -- episodes
FROM fc1
"""

# 1-2. The showdown: AHU_1's first n rows (rowid 1 to n), 1,000 to 500,000 rows
sizes = []
for n in [1_000, 10_000, 100_000, 500_000]:
    conn.execute("DROP TABLE IF EXISTS temp.h")  # the temp tables from the last round
    conn.execute("DROP TABLE IF EXISTS temp.fc1")
    conn.execute("CREATE TEMP TABLE h AS SELECT * FROM synthetic WHERE rowid <= ?", [n])

    start = time.perf_counter()
    conn.execute(fc1_sql, settings)
    fault_rows, episodes = conn.execute(totals_sql, settings).fetchone()
    sql_seconds = time.perf_counter() - start

    print("rows:", n, "| fault rows:", fault_rows, "| episodes:", episodes)
    print("  seconds: window SQL", round(sql_seconds, 4))
    sizes.append({"rows": n, "fault_rows": fault_rows, "episodes": episodes})
totals_by_size = pd.DataFrame(sizes)

# 3. The first confirmed fault in AHU_1's first 200,000 rows. SQL has no "stop at the first
#    one" here: every row's streak is computed before MIN can look at them.
conn.execute("DROP TABLE temp.h")
conn.execute("DROP TABLE temp.fc1")
conn.execute("CREATE TEMP TABLE h AS SELECT * FROM synthetic WHERE rowid <= 200000")
start = time.perf_counter()
conn.execute(fc1_sql, settings)
first_sql = "SELECT MIN(ts) FROM fc1 WHERE raw_fault = 1 AND row_in_streak >= :confirm_rows"
first_fault_ts = conn.execute(first_sql, settings).fetchone()[0]
first_seconds = time.perf_counter() - start
print("\nFirst confirmed fault in 200,000 rows: ts", first_fault_ts)
print("  seconds: window SQL", round(first_seconds, 4))

# 4. Week 4 challenge: the longest confirmed episode per AHU, in the first 20,000 rows of each.
#    GROUP BY a streak gives its size; HAVING keeps the streaks long enough to confirm.
conn.execute("DROP TABLE temp.h")
conn.execute("DROP TABLE temp.fc1")
first_rows_sql = "CREATE TEMP TABLE h AS SELECT * FROM synthetic WHERE ts < :start_ts + 20000 * 300"
conn.execute(first_rows_sql, settings)
conn.execute(fc1_sql, settings)
longest_sql = """
SELECT equipment_id, MAX(rows) AS longest_rows, MAX(rows) * 5 AS longest_min
FROM (
  SELECT equipment_id, streak_id, COUNT(*) AS rows
  FROM fc1
  WHERE raw_fault = 1
  GROUP BY equipment_id, streak_id
  HAVING COUNT(*) >= :confirm_rows
)
GROUP BY equipment_id
"""
longest_episode = pd.read_sql_query(longest_sql, conn, params=settings)

print("\nLongest confirmed episode per AHU (20,000 rows each):")
print(longest_episode.to_string(index=False))

# For the course's automatic checker (tests/test_lesson_scripts.py)
RESULTS = {
    "totals_by_size": totals_by_size,
    "first_fault_ts": first_fault_ts,
    "longest_episode": longest_episode,
}
